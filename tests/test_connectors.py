import json,os,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import pytest
from lakehouse.connectors import api_rows,postgres_products,csv_rows
from lakehouse.landing import land,validate_manifest

def test_paginated_api():
 class Handler(BaseHTTPRequestHandler):
  def do_GET(self):
   page2=self.path.endswith('page=2')
   body={'data':[{'order_id':'O2' if page2 else 'O1'}],'next':None if page2 else f'http://127.0.0.1:{self.server.server_port}/orders?page=2'}
   self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(body).encode())
  def log_message(self,*args):pass
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:assert api_rows(f'http://127.0.0.1:{server.server_port}/orders',allow_local=True)==[{'order_id':'O1'},{'order_id':'O2'}]
 finally:server.shutdown();server.server_close();thread.join()

def fixture_entities():
 folder=Path('fixtures/batch_001')
 return {'customers':csv_rows(folder/'customers.csv'),'products':csv_rows(folder/'products.csv'),'orders':json.loads((folder/'orders.json').read_text())}

def test_immutable_landing_and_manifest(tmp_path):
 rows=fixture_entities();m=land(str(tmp_path),'batch_001',rows)
 assert validate_manifest(str(tmp_path),'batch_001')==m
 assert land(str(tmp_path),'batch_001',rows)==m
 rows['customers'][0]['city']='Changed'
 with pytest.raises(ValueError):land(str(tmp_path),'batch_001',rows)

def test_incomplete_batch_and_corruption(tmp_path):
 with pytest.raises(ValueError):land(str(tmp_path),'batch_x',{'orders':[]})
 land(str(tmp_path),'batch_001',fixture_entities())
 (tmp_path/'bronze/batch_001/orders.jsonl').write_text('tampered')
 with pytest.raises(ValueError):validate_manifest(str(tmp_path),'batch_001')

def test_api_requires_tls():
 with pytest.raises(ValueError):api_rows('http://example.com/orders')

@pytest.mark.skipif(not os.environ.get('POSTGRES_TEST_DSN'),reason='PostgreSQL integration runs in CI service container')
def test_real_postgres_extraction():
 import psycopg
 dsn=os.environ['POSTGRES_TEST_DSN']
 with psycopg.connect(dsn) as conn:
  conn.execute('create table if not exists products (product_id text primary key, product_name text, category text, updated_at timestamp)')
  conn.execute("insert into products values ('P1','Notebook','Stationery','2026-01-01') on conflict (product_id) do nothing")
 rows=postgres_products(dsn)
 assert rows[0]['product_id']=='P1' and rows[0]['category']=='Stationery'
