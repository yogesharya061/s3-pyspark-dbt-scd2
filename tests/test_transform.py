import pytest
from pyspark.sql import SparkSession
from lakehouse.contracts import CONTRACTS
from lakehouse.transform import transform,reject_stale_or_conflicting

@pytest.fixture(scope='module')
def spark():
 s=SparkSession.builder.master('local[2]').config('spark.sql.shuffle.partitions','2').config('spark.sql.session.timeZone','UTC').getOrCreate();s.sparkContext.setLogLevel('ERROR');yield s;s.stop()

def customer_frame(spark,rows):
 return spark.createDataFrame(rows,', '.join(x+' string' for x in CONTRACTS['customers']['fields']))

def test_customer_normalization_quarantine_and_conflicts(spark):
 row=('C1',' Asha ','ASHA@example.com','delhi','basic','false','2026-01-01 00:00:00')
 good,bad=transform(customer_frame(spark,[row,('X','Bad','broken','Delhi','basic','false','2026-01-01 00:00:00')]),'customers')
 assert good.count()==1 and bad.count()==1
 assert good.first().email=='asha@example.com' and good.first().city=='Delhi'
 conflict=('C1','Asha','ASHA@example.com','mumbai','basic','false','2026-01-01 00:00:00')
 with pytest.raises(ValueError):transform(customer_frame(spark,[row,conflict]),'customers')

def test_stale_and_equal_time_change_rejected(spark):
 old=('C1','Asha','asha@example.com','Delhi','BASIC','false','2026-01-01 00:00:00')
 new=('C1','Asha','asha@example.com','Mumbai','GOLD','false','2026-01-02 00:00:00')
 a,_=transform(customer_frame(spark,[old]),'customers');b,_=transform(customer_frame(spark,[new]),'customers')
 with pytest.raises(ValueError):reject_stale_or_conflicting(a,b,'customers')
 reject_stale_or_conflicting(b,b,'customers')
 reject_stale_or_conflicting(b,a,'customers')
