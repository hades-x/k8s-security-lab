#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Mirror owned source files into in-cluster Forgejo and configure CI secrets."""
import os,pathlib,requests,json,base64,yaml
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
F='https://forgejo.192.168.150.200.sslip.io';C='https://ci.192.168.150.200.sslip.io';ca='.secrets/pki/root_ca.crt'
f=requests.Session();f.verify=ca;f.headers['Authorization']='token '+pathlib.Path('.secrets/p6/forgejo-token').read_text().strip()
c=requests.Session();c.verify=ca;c.headers['Authorization']='Bearer '+pathlib.Path('.secrets/p6/woodpecker-token').read_text().strip()
def call(s,method,url,**kw):
 r=s.request(method,url,timeout=60,**kw)
 if r.status_code>=400:raise RuntimeError(method+' '+url.split('?')[0]+' status='+str(r.status_code)+' '+r.text[:150])
 return r.json() if r.content else None

def mirror(repo,files,message):
 changes=[]
 for path,source in files.items():
  url=F+'/api/v1/repos/lab/'+repo+'/contents/'+path
  old=f.get(url,timeout=30)
  op={'path':path,'content':base64.b64encode(source).decode(),'operation':'create'}
  if old.status_code==200 and isinstance(old.json(),dict):
   j=old.json()
   if base64.b64decode(j['content'])==source:continue
   op.update(operation='update',sha=j['sha'])
  elif old.status_code not in [200,404]:raise RuntimeError('Forgejo read status='+str(old.status_code))
  changes.append(op)
 if changes:
  j=call(f,'POST',F+'/api/v1/repos/lab/'+repo+'/contents',json={'branch':'main','message':message,'files':changes}); print('PASS mirror lab/'+repo+' '+str(len(changes))+' files commit='+j['commit']['sha']); commit=j['commit']['sha']
  for op in changes:
   j=call(f,'GET',F+'/api/v1/repos/lab/'+repo+'/contents/'+op['path']);assert j['content'].replace('\n','')==op['content'],'mirror readback mismatch'
 else:print('PASS mirror unchanged lab/'+repo); commit=None
 return commit
# Do not overwrite live env digests during source re-mirroring.
deploy={str(p.relative_to('app')):p.read_bytes() for p in pathlib.Path('app/chart').rglob('*') if p.is_file()}
for e in ['dev','staging','prod']:
 path='chart/values-'+e+'.yaml';r=f.get(F+'/api/v1/repos/lab/demo-app-deploy/contents/'+path,timeout=30)
 if r.status_code==200 and isinstance(r.json(),dict):deploy.pop(path,None)
mirror('demo-app-deploy',deploy,'GitOps: add three environment Helm chart')
source={str(p.relative_to('app')):p.read_bytes() for p in pathlib.Path('app').rglob('*') if p.is_file() and '__pycache__' not in str(p) and not p.name.endswith('.pyc')}
# Publish initial source before creating the CI hook, so upload is not a partial build.
source_sha=mirror('demo-app',source,'Source mirror: tested orders app and immutable pipeline')
r=c.get(C+'/api/repos/lookup/lab/demo-app',timeout=30)
if r.status_code==404:repo=call(c,'POST',C+'/api/repos?forge_remote_id=2')
else:r.raise_for_status();repo=r.json()
rid=repo['id']; print('PASS active Woodpecker repo id='+str(rid))
pathlib.Path('devsecops/ci-repo.json').write_text(json.dumps({'id':rid,'full_name':'lab/demo-app'})+'\n')
# Rootless workloads stay separate from isolated CI build pods; permit this lab-only pipeline's security settings.
call(c,'PATCH',C+'/api/repos/'+str(rid),json={'trusted':{'security':True},'timeout':30,'require_approval':'none'})
secret_values={'lab_ca':pathlib.Path(ca).read_text(),'zot_password':pathlib.Path('.secrets/p3/zot-password').read_text().strip(),'cosign_key':pathlib.Path('.secrets/cosign.key').read_text(),'cosign_password':pathlib.Path('.secrets/cosign.password').read_text().strip(),'forgejo_token':pathlib.Path('.secrets/p6/forgejo-token').read_text().strip()}
existing=call(c,'GET',C+'/api/repos/'+str(rid)+'/secrets') or [];names={x['name'] for x in existing}
for name,value in secret_values.items():
 data={'name':name,'value':value,'events':['push'],'images':[],'note':'P6 lab only; never logged/committed'}
 endpoint=C+'/api/repos/'+str(rid)+'/secrets'+('/'+name if name in names else '')
 call(c,'PATCH' if name in names else 'POST',endpoint,json=data)
check=call(c,'GET',C+'/api/repos/'+str(rid)+'/secrets');assert set(secret_values).issubset({x['name'] for x in check});print('PASS five push-only repository secrets stored and metadata read back')
# Forgejo needs lab CA trusted for outbound hooks, and allow-list private lab VIP already configured by P3.
hooks=call(f,'GET',F+'/api/v1/repos/lab/demo-app/hooks');print('PASS Forgejo webhook count='+str(len(hooks)))
if source_sha:
 pathlib.Path('evidence/p6/trigger.json').write_text(json.dumps({'sha':source_sha, 'method':'source mirror Git commit; native webhook'})+'\n')
 print('PASS source mirror itself is the single trigger; no superseding duplicate push')
 raise SystemExit(0)
# A real source commit after hook+secrets setup triggers the complete pipeline.
marker={'path':'BUILD_TRIGGER','content':base64.b64encode(os.environ.get('TRIGGER','p6 initial end-to-end build').encode()).decode(),'operation':'create'}
r=f.get(F+'/api/v1/repos/lab/demo-app/contents/BUILD_TRIGGER',timeout=30)
if r.status_code==200:marker.update(operation='update',sha=r.json()['sha']);marker['content']=base64.b64encode(('p6 rebuild '+__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()).encode()).decode()
j=call(f,'POST',F+'/api/v1/repos/lab/demo-app/contents',json={'branch':'main','message':'Trigger: prove unit build scan sign GitOps','files':[marker]});print('PASS source trigger commit='+j['commit']['sha'])
pathlib.Path('evidence/p6/trigger.json').write_text(json.dumps({'sha':j['commit']['sha']})+'\n')
