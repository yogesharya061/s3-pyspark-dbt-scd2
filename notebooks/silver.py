# Databricks notebook source
import json,re,sys,hashlib
from pathlib import Path
from pyspark.sql import functions as F
from delta.tables import DeltaTable
sys.path.insert(0,str(Path.cwd().parent))
from lakehouse.contracts import CONTRACTS
from lakehouse.transform import transform,reject_stale_or_conflicting
for name,default in [('lake_root',''),('catalog',''),('silver_schema',''),('batch_id','')]:dbutils.widgets.text(name,default)
root=dbutils.widgets.get('lake_root').rstrip('/');catalog=dbutils.widgets.get('catalog');schema=dbutils.widgets.get('silver_schema');batch=dbutils.widgets.get('batch_id')
assert re.fullmatch(r's3://[a-z0-9.-]+/[A-Za-z0-9_/-]+',root)
assert all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',x) for x in [catalog,schema])
assert schema.startswith('portfolio_')
assert re.fullmatch(r'[A-Za-z0-9_-]+',batch)
spark.conf.set('spark.sql.session.timeZone','UTC')
spark.conf.set('spark.sql.ansi.enabled','false')  # Invalid casts become null, then quarantine.
spark.sql(f'USE CATALOG `{catalog}`')
# Schemas are provisioned by the setup SQL; do not silently create them in another location.
spark.sql(f'DESCRIBE SCHEMA `{catalog}`.`{schema}`').collect()
def bytes_at(path):
 rows=spark.read.format('binaryFile').load(path).select('content').collect()
 if len(rows)!=1:raise ValueError('Expected one manifest/object')
 return bytes(rows[0].content)
manifest=json.loads(bytes_at(f'{root}/bronze/{batch}/manifest.json'))
assert manifest['batch_id']==batch and set(manifest['entities'])==set(CONTRACTS)
prepared={};metrics={}
for entity,c in CONTRACTS.items():
 meta=manifest['entities'][entity]
 assert meta['key']==f'bronze/{batch}/{entity}.jsonl'
 # Fixture-scale checksum validation. Use distributed checksums for large source batches.
 if hashlib.sha256(bytes_at(root+'/'+meta['key'])).hexdigest()!=meta['sha256']:raise ValueError('Checksum mismatch')
 raw=spark.read.schema(', '.join(x+' string' for x in c['fields'])).json(root+'/'+meta['key'])
 if raw.count()!=meta['rows']:raise ValueError('Manifest row count mismatch')
 clean,bad=transform(raw,entity)
 clean=clean.cache()
 bad.write.format('delta').mode('overwrite').save(f'{root}/quarantine/{batch}/{entity}')
 name=f'`{catalog}`.`{schema}`.`{entity}`'
 if spark.catalog.tableExists(f'{catalog}.{schema}.{entity}'):
  reject_stale_or_conflicting(clean,spark.table(name),entity)
 prepared[entity]=clean
 metrics[entity]={'input':meta['rows'],'accepted_unique':clean.count(),'rejected':bad.count()}
# Preflight all sources before writes. Delta commits are per table, not cross-table transactions.
# On failure, retry THIS batch before snapshotting or running a later batch.
for entity,clean in prepared.items():
 key=CONTRACTS[entity]['key'];name=f'`{catalog}`.`{schema}`.`{entity}`'
 if spark.catalog.tableExists(f'{catalog}.{schema}.{entity}'):
  (DeltaTable.forName(spark,name).alias('t').merge(clean.alias('s'),f't.{key}=s.{key}')
   .whenMatchedUpdateAll(condition='s.updated_at > t.updated_at').whenNotMatchedInsertAll().execute())
 else:
  clean.write.format('delta').mode('errorifexists').option('path',f'{root}/silver/{entity}').saveAsTable(name)
 clean.unpersist()
print(json.dumps(metrics,indent=2))
dbutils.notebook.exit(json.dumps({'batch_id':batch,'status':'silver_complete','metrics':metrics}))
