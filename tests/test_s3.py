import os
import boto3
from botocore.stub import Stubber
from lakehouse.landing import Store

def test_s3_conditional_write_and_retry(monkeypatch):
 client=boto3.client('s3',region_name='us-east-1',aws_access_key_id='test',aws_secret_access_key='test')
 monkeypatch.setattr(boto3,'client',lambda *a,**k:client)
 s=Store('s3://demo-bucket/portfolio/dev')
 with Stubber(client) as stub:
  stub.add_response('put_object',{}, {'Bucket':'demo-bucket','Key':'portfolio/dev/bronze/batch/file','Body':b'content','IfNoneMatch':'*'})
  s.create('bronze/batch/file',b'content')
