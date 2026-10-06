import argparse,json,os
from pathlib import Path
from lakehouse.connectors import csv_rows,api_rows,postgres_products
from lakehouse.landing import land
p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--root',required=True);p.add_argument('--fixtures',action='store_true');a=p.parse_args()
if a.fixtures:
 folder=Path('fixtures')/a.batch
 entities={'customers':csv_rows(folder/'customers.csv'),'orders':json.loads((folder/'orders.json').read_text()),'products':csv_rows(folder/'products.csv')}
else:
 entities={'customers':csv_rows(os.environ['CUSTOMERS_CSV']),'orders':api_rows(os.environ['ORDERS_API_URL'],os.environ.get('ORDERS_API_TOKEN')),'products':postgres_products(os.environ['POSTGRES_DSN'])}
print(json.dumps(land(a.root,a.batch,entities),indent=2))
