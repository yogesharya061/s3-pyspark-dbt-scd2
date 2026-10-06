"""Bounded extraction adapters; secrets are read by the CLI, never written to manifests."""
import csv,json,time
from urllib.parse import urlparse
import requests

def csv_rows(path):
 with open(path,newline='',encoding='utf-8-sig') as f:
  reader=csv.DictReader(f)
  if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):
   raise ValueError('Missing or duplicate CSV header')
  return list(reader)

def api_rows(url,token=None,max_pages=100,allow_local=False):
 origin=urlparse(url)
 if origin.scheme!='https' and not (allow_local and origin.hostname in ('127.0.0.1','localhost')):
  raise ValueError('API requires HTTPS except the explicit local fixture server')
 headers={'Authorization':f'Bearer {token}'} if token else {}
 rows=[];seen=set()
 for _ in range(max_pages):
  if url in seen:raise ValueError('Pagination cycle')
  seen.add(url)
  # Never follow a redirect or a cross-origin next link with credentials.
  if (urlparse(url).scheme,urlparse(url).netloc)!=(origin.scheme,origin.netloc):raise ValueError('Cross-origin pagination')
  for attempt in range(4):
   r=requests.get(url,headers=headers,timeout=30,allow_redirects=False)
   if r.status_code not in (429,500,502,503,504):break
   if attempt==3:r.raise_for_status()
   time.sleep(max(1,int(r.headers.get('Retry-After',2**attempt))))
  if 300<=r.status_code<400:raise ValueError('API redirects are not followed')
  r.raise_for_status();body=r.json()
  if not isinstance(body.get('data'),list):raise ValueError('Expected API data array')
  rows.extend(body['data']);url=body.get('next')
  if not url:return rows
 raise ValueError('API page limit exceeded; no partial extraction will be committed')

def postgres_products(dsn):
 import psycopg
 from psycopg.rows import dict_row
 # Narrow, fixed query. Repeatable-read snapshot of the demo product source.
 with psycopg.connect(dsn,row_factory=dict_row) as conn:
  with conn.transaction():
   conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
   return [dict(r) for r in conn.execute('SELECT product_id, product_name, category, updated_at FROM public.products ORDER BY product_id')]
