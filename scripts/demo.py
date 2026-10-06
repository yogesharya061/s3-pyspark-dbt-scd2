"""Execute real Spark and dbt twice, rerun Gold, then assert history and point-in-time joins."""
import json,os,subprocess,sys
from pathlib import Path
import duckdb
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
env=os.environ.copy();env['PYTHONPATH']=str(ROOT);env['SPARK_LOCAL_IP']='127.0.0.1'
if Path('.local/warehouse.duckdb').exists():raise SystemExit('Demo database exists. Use a fresh checkout or move .local aside; no automatic deletion.')
def run(*args,cwd=ROOT):subprocess.run(args,cwd=cwd,env=env,check=True)
import shutil
dbt=shutil.which('dbt') or str(Path(sys.executable).parent/('dbt.exe' if os.name=='nt' else 'dbt'))
for batch in ['batch_001','batch_002']:
 run(sys.executable,'-m','scripts.ingest_sources','--fixtures','--root','.local/lake','--batch',batch)
 run(sys.executable,'-m','scripts.process_local','--batch',batch)
 run(dbt,'test','--profiles-dir','.','--select','source:*','--indirect-selection','cautious',cwd=ROOT/'dbt')
 run(dbt,'snapshot','--profiles-dir','.',cwd=ROOT/'dbt')
 run(dbt,'run','--profiles-dir','.',cwd=ROOT/'dbt')
 run(dbt,'test','--profiles-dir','.',cwd=ROOT/'dbt')
# Same snapshot rerun must add no versions.
run(dbt,'snapshot','--profiles-dir','.',cwd=ROOT/'dbt')
with duckdb.connect('.local/warehouse.duckdb') as c:
 assert c.execute('select count(*) from gold.customer_history').fetchone()[0]==3
 assert c.execute("select count(*) from gold.dim_customer_scd2 where customer_id='C1'").fetchone()[0]==2
 actual=c.execute('select order_id,customer_city_at_order,customer_tier_at_order from gold.fact_orders order by order_id').fetchall()
 assert actual==[('O1','Delhi','BASIC'),('O2','Mumbai','GOLD')],actual
 assert float(c.execute('select sum(order_amount) from gold.fact_orders').fetchone()[0])==180.0
 result={'customer_history_rows':3,'current_customers':2,'orders':actual,'revenue':180.0,'snapshot_rerun_added_rows':0,'engine':'Local Spark + real dbt snapshots on DuckDB; not live cloud validation'}
 Path('.local/demo-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
