import argparse,json
from pathlib import Path
import duckdb
from pyspark.sql import SparkSession
from lakehouse.contracts import CONTRACTS
from lakehouse.landing import validate_manifest
from lakehouse.transform import transform,reject_stale_or_conflicting
p=argparse.ArgumentParser();p.add_argument('--batch',required=True);a=p.parse_args()
root=Path('.local/lake');validate_manifest(str(root),a.batch)
s=SparkSession.builder.master('local[2]').appName('multi-source-local').config('spark.sql.shuffle.partitions','2').config('spark.sql.session.timeZone','UTC').getOrCreate();s.sparkContext.setLogLevel('ERROR')
try:
 metrics={};prepared={}
 for entity,c in CONTRACTS.items():
  schema=', '.join(x+' string' for x in c['fields'])
  raw=s.read.schema(schema).json(str(root/f'bronze/{a.batch}/{entity}.jsonl'))
  clean,rejected=transform(raw,entity)
  destination=root/f'silver/{a.batch}/{entity}'
  clean.write.mode('overwrite').parquet(str(destination));rejected.write.mode('overwrite').json(str(root/f'quarantine/{a.batch}/{entity}'))
  prepared[entity]=destination
  metrics[entity]={'input':raw.count(),'accepted_unique':clean.count(),'rejected':rejected.count()}
 # Local adapter bridge: transactional current-state upsert into DuckDB Silver.
 with duckdb.connect('.local/warehouse.duckdb') as conn:
  conn.execute('create schema if not exists silver')
  conn.execute('begin transaction')
  try:
   for entity,path in prepared.items():
    key=CONTRACTS[entity]['key'];scan=str(path/'*.parquet').replace("'","''")
    conn.execute(f"create or replace temp table incoming as select * from read_parquet('{scan}')")
    conn.execute(f'create table if not exists silver.{entity} as select * from incoming where false')
    bad=conn.execute(f"""select count(*) from incoming s join silver.{entity} t using ({key}) where s.updated_at<t.updated_at or (s.updated_at=t.updated_at and s._hash<>t._hash)""").fetchone()[0]
    if bad:raise ValueError('Stale or conflicting version')
    conn.execute(f'delete from silver.{entity} where {key} in (select {key} from incoming)')
    conn.execute(f'insert into silver.{entity} select * from incoming')
   conn.execute('commit')
  except:conn.execute('rollback');raise
 Path('.local/metrics.json').write_text(json.dumps(metrics,indent=2));print(json.dumps(metrics,indent=2))
finally:s.stop()
