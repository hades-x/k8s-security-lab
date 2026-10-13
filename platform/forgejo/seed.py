#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Seed the local Forgejo through its API; never git-push externally."""
from pathlib import Path
import base64,json,urllib.request,urllib.error,time,hashlib
root=Path('/data/k8s-lab')
password=(root/'.secrets/forgejo-admin-password').read_text().strip()
url='http://192.168.150.200'
auth=base64.b64encode(('lab-admin:'+password).encode()).decode()
def api(method,path,data=None):
 req=urllib.request.Request(url+'/api/v1'+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Authorization':'Basic '+auth,'Content-Type':'application/json','Host':'forgejo.192.168.150.200.sslip.io'})
 with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def exists(path):
 try:return api('GET',path)
 except urllib.error.HTTPError as error:
  if error.code==404:return None
  raise
for attempt in range(8):
 try:
  api('GET','/version')
  break
 except urllib.error.HTTPError as error:
  if error.code not in (502,503,504) or attempt==7:raise
  print('Waiting for Forgejo ingress readiness (HTTP '+str(error.code)+')')
  time.sleep(2)
if not exists('/orgs/lab'):
 api('POST','/orgs',{'username':'lab','full_name':'Kubernetes Lab','visibility':'public'})
if not exists('/repos/lab/gitops'):
 api('POST','/orgs/lab/repos',{'name':'gitops','description':'Local K8S lab GitOps demo','private':False,'auto_init':False,'default_branch':'main'})
for path in sorted((root/'platform/gitops-seed').glob('*.yaml')):
 content=path.read_bytes(); endpoint='/repos/lab/gitops/contents/'+path.name
 old=exists(endpoint)
 if old and base64.b64decode(old['content'])==content:continue
 data={'content':base64.b64encode(content).decode(),'message':'Seed reproducible lab manifests','branch':'main','author':{'name':'Lab automation','email':'lab@k8slab.invalid'}}
 if old:data['sha']=old['sha']
 api('PUT' if old else 'POST',endpoint,data)
 actual=api('GET',endpoint)
 assert base64.b64decode(actual['content'])==content
 print('Verified Forgejo lab/gitops/'+path.name+' sha256='+hashlib.sha256(content).hexdigest())
repo=api('GET','/repos/lab/gitops')
print('Forgejo repository verified: '+repo['full_name']+' branch='+repo['default_branch'])
