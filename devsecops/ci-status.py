#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import os,pathlib,requests,json,subprocess,sys
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
s=requests.Session();s.verify='.secrets/pki/root_ca.crt';s.headers['Authorization']='Bearer '+pathlib.Path('.secrets/p6/woodpecker-token').read_text().strip();C='https://ci.192.168.150.200.sslip.io'
def get(path):
 r=s.get(C+path,timeout=30);r.raise_for_status();return r.json()
for p in get('/api/repos/1/pipelines')[:3]:
 d=get('/api/repos/1/pipelines/'+str(p['number']));pathlib.Path('evidence/p6/ci-'+str(p['number'])+'-status.json').write_text(json.dumps(d,indent=2));print('Pipeline',d['number'],d['commit'],d['status'])
 for w in d.get('workflows',[]):
  for step in w.get('children',[]):
   print(' ',step['name'],step['state'],step.get('exit_code'),step.get('error'))
   r=s.get(C+'/api/repos/1/logs/'+str(p['number'])+'/'+str(step['id'])+'/download',timeout=30)
   if r.status_code==200:
    pathlib.Path('evidence/p6/ci-'+str(p['number'])+'-'+step['name']+'.log').write_text(r.text)
    if step['state']=='failure' or step['name']=='push-sign-gitops-dev':print(r.text[-10000:])
print('Agents', [{k:x.get(k) for k in ['name','last_contact','capacity','no_schedule']} for x in get('/api/agents')])
for cmd in [['kubectl','-n','ci','get','pods'],['kubectl','-n','dev','get','pods,cluster'],['kubectl','get','applications','-n','argocd'],['free','-g'],['date']]:subprocess.run(cmd,check=True)
