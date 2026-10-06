"""Immutable deterministic objects and manifest-last commit protocol."""
import hashlib,json,re
from pathlib import Path
from urllib.parse import urlparse
from lakehouse.contracts import CONTRACTS

def encode(rows,entity):
 fields=CONTRACTS[entity]['fields'];normalized=[]
 for row in rows:
  if not set(fields)<=row.keys():raise ValueError(f'{entity}: missing required fields')
  normalized.append({k:None if row[k] is None else str(row[k]) for k in fields})
 # Ignore extraction order, preserve duplicate rows for data quality inspection.
 return ('\n'.join(sorted(json.dumps(r,sort_keys=True) for r in normalized))+'\n').encode() if normalized else b''

class Store:
 def __init__(self,root):
  self.root=root.rstrip('/');u=urlparse(root);self.s3=None
  if u.scheme=='s3':
   import boto3
   self.s3=boto3.client('s3');self.bucket=u.netloc;self.prefix=u.path.strip('/')
  elif u.scheme:raise ValueError('Use local directory or s3://')
 def read(self,key):
  if self.s3:return self.s3.get_object(Bucket=self.bucket,Key=self.prefix+'/'+key)['Body'].read()
  return (Path(self.root)/key).read_bytes()
 def create(self,key,data):
  if self.s3:
   from botocore.exceptions import ClientError
   try:self.s3.put_object(Bucket=self.bucket,Key=self.prefix+'/'+key,Body=data,IfNoneMatch='*')
   except ClientError as e:
    if e.response['Error']['Code'] not in ('PreconditionFailed','412'):raise
    if self.read(key)!=data:raise ValueError('Batch key already exists with different data') from e
  else:
   p=Path(self.root)/key;p.parent.mkdir(parents=True,exist_ok=True)
   try:
    with p.open('xb') as f:f.write(data)
   except FileExistsError:
    if p.read_bytes()!=data:raise ValueError('Batch key already exists with different data')

def land(root,batch,entities):
 if not re.fullmatch(r'[a-zA-Z0-9_-]+',batch):raise ValueError('Unsafe batch ID')
 if set(entities)!=set(CONTRACTS):raise ValueError('Every entity is required before committing a batch')
 store=Store(root);manifest={'batch_id':batch,'entities':{}}
 for entity,rows in sorted(entities.items()):
  content=encode(rows,entity);key=f'bronze/{batch}/{entity}.jsonl'
  store.create(key,content)
  manifest['entities'][entity]={'key':key,'rows':len(rows),'sha256':hashlib.sha256(content).hexdigest()}
 # Consumers read only batches with this complete manifest.
 store.create(f'bronze/{batch}/manifest.json',json.dumps(manifest,sort_keys=True,indent=2).encode())
 return manifest

def validate_manifest(root,batch):
 s=Store(root);m=json.loads(s.read(f'bronze/{batch}/manifest.json'))
 for entity,meta in m['entities'].items():
  b=s.read(meta['key'])
  if hashlib.sha256(b).hexdigest()!=meta['sha256']:raise ValueError('Manifest checksum mismatch')
 return m
