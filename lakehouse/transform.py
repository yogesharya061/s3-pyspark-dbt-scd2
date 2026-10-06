"""Shared Spark transformations, usable locally and on Databricks."""
from pyspark.sql import functions as F,Window
from lakehouse.contracts import CONTRACTS

def transform(df,entity):
 fields=CONTRACTS[entity]['fields'];key=CONTRACTS[entity]['key']
 df=df.select(*fields)
 for name in fields:df=df.withColumn(name,F.trim(F.col(name)))
 df=df.withColumn('updated_at',F.to_timestamp('updated_at'))
 valid=F.col(key).isNotNull() & (F.col(key)!='') & F.col('updated_at').isNotNull()
 if entity=='customers':
  df=df.withColumn('email',F.lower('email')).withColumn('city',F.initcap('city')).withColumn('tier',F.upper('tier'))
  df=df.withColumn('is_deleted',F.when(F.lower('is_deleted').isin('true','1'),True).when(F.lower('is_deleted').isin('false','0'),False))
  valid=valid & F.col('email').rlike(r'^[^@\s]+@[^@\s]+\.[^@\s]+$') & F.col('tier').isin('BASIC','GOLD','PLATINUM') & F.col('is_deleted').isNotNull()
 elif entity=='orders':
  df=df.withColumn('quantity',F.when(F.col('quantity').rlike(r'^[1-9][0-9]*$'),F.col('quantity').cast('int'))).withColumn('unit_price',F.col('unit_price').cast('decimal(18,2)')).withColumn('ordered_at',F.to_timestamp('ordered_at'))
  valid=valid & (F.col('quantity')>0) & (F.col('unit_price')>=0) & F.col('ordered_at').isNotNull() & (F.length('customer_id')>0) & (F.length('product_id')>0)
  df=df.withColumn('order_amount',(F.col('quantity')*F.col('unit_price')).cast('decimal(20,2)'))
 elif entity=='products':valid=valid & (F.length('product_name')>0) & (F.length('category')>0)
 df=df.withColumn('_valid',F.coalesce(valid,F.lit(False)))
 rejected=df.filter(~F.col('_valid')).drop('_valid').withColumn('reject_reason',F.lit('contract_validation_failed'))
 good=df.filter('_valid').drop('_valid')
 # Same key/time with different attributes is ambiguous; fail instead of choosing randomly.
 attrs=[c for c in good.columns if c not in [key,'updated_at']]
 good=good.withColumn('_hash',F.sha2(F.to_json(F.struct(*[F.col(c) for c in attrs])),256))
 if good.groupBy(key,'updated_at').agg(F.countDistinct('_hash').alias('n')).filter('n>1').limit(1).count():raise ValueError('Conflicting versions at identical timestamp')
 w=Window.partitionBy(key).orderBy(F.desc('updated_at'))
 clean=good.withColumn('_rn',F.row_number().over(w)).filter('_rn=1').drop('_rn')
 return clean,rejected

def reject_stale_or_conflicting(incoming,current,entity):
 key=CONTRACTS[entity]['key']
 conflict=incoming.alias('s').join(current.alias('t'),key).filter((F.col('s.updated_at')<F.col('t.updated_at')) | ((F.col('s.updated_at')==F.col('t.updated_at')) & (F.col('s._hash')!=F.col('t._hash'))))
 if conflict.limit(1).count():raise ValueError(f'{entity}: stale or equal-timestamp conflicting update; resolve before Gold')
