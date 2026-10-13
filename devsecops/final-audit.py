#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Bounded final readback, resource measurement and private secret-leak check."""
import os,pathlib,json,subprocess,time,ast,requests,base64,yaml
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
def run(cmd):
 r=subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=90);return r.stdout

def get(ns,kind,name=None):return json.loads(run(['kubectl','-n',ns,'get',kind]+([name] if name else [])+['-o','json']))
def memory(q):
 units={'Ki':1024,'Mi':1024**2,'Gi':1024**3,'Ti':1024**4}
 for unit,scale in units.items():
  if str(q).endswith(unit):return int(float(str(q)[:-len(unit)])*scale)
 return int(q)

pods=[];quota=0
for ns in ['ci','dev','staging','prod']:
 q=get(ns,'resourcequota')['items'];quota+=sum(memory(x['spec']['hard']['limits.memory']) for x in q)
 for p in get(ns,'pods')['items']:
  if p.get('status',{}).get('phase') in ['Succeeded','Failed']:continue
  spec=p['spec'];containers=spec.get('containers',[]);inits=spec.get('initContainers',[])
  assert all(c.get('resources',{}).get('limits',{}).get('memory') for c in containers+inits)
  effective=max(sum(memory(c['resources']['limits']['memory']) for c in containers),max((memory(c['resources']['limits']['memory']) for c in inits),default=0))
  pods.append({'namespace':ns,'pod':p['metadata']['name'],'effectiveMemoryLimitBytes':effective})
op=get('cnpg-system','deployment','cnpg-cloudnative-pg');container=op['spec']['template']['spec']['containers'][0];operator_memory=memory(container['resources']['limits']['memory']);total_max=quota+operator_memory
assert total_max<=5*1024**3
pods.append({'namespace':'cnpg-system','pod':'operator','effectiveMemoryLimitBytes':operator_memory})
agent=get('ci','statefulset','woodpecker-agent');env={e['name']:e.get('value') for e in agent['spec']['template']['spec']['containers'][0]['env']};assert env['WOODPECKER_MAX_WORKFLOWS']=='1' and env['WOODPECKER_BACKEND_K8S_POD_NODE_SELECTOR']=='kubernetes.io/hostname: lab-a1'
server=get('ci','statefulset','woodpecker-server');refs=[x['secretRef']['name'] for x in server['spec']['template']['spec']['containers'][0]['envFrom'] if 'secretRef' in x];assert 'woodpecker-grpc' in refs
log=run(['kubectl','-n','ci','logs','woodpecker-server-0']);assert 'generated a temporary random secret' not in log
expected=next(e['value'] for e in container['env'] if e['name']=='OPERATOR_IMAGE_NAME');assert expected==container['image'] and '@sha256:' in expected
before={ns:get(ns,'pod','demo-db-1')['metadata']['uid'] for ns in ['dev','staging','prod']}
print('Measured P6 quota max plus operator MiB',total_max/1024**2,'GiB',total_max/1024**3)
print('Active effective limits MiB',sum(p['effectiveMemoryLimitBytes'] for p in pods)/1024**2)
print('PASS CI capacity=1; build node=a1; durable gRPC secret reference; no ephemeral warning; immutable CNPG bootstrap')
# Save the live env references for the orchestration repo's reproducible chart.
s=requests.Session();s.verify='.secrets/pki/root_ca.crt';s.headers['Authorization']='token '+pathlib.Path('.secrets/p6/forgejo-token').read_text().strip()
for ns in ['dev','staging','prod']:
 u='https://forgejo.192.168.150.200.sslip.io/api/v1/repos/lab/demo-app-deploy/contents/chart/values-'+ns+'.yaml';r=s.get(u,timeout=30);r.raise_for_status();data=base64.b64decode(r.json()['content']);pathlib.Path('app/chart/values-'+ns+'.yaml').write_bytes(data)
 values=yaml.safe_load(data);assert values['buildRevision']==json.loads(pathlib.Path('evidence/p6/acceptance-pipeline.json').read_text())['commit']
 rendered=run(['helm','template','demo-app','app/chart','-f','app/chart/values-'+ns+'.yaml','--namespace',ns])
 docs=list(yaml.safe_load_all(rendered));assert len(docs)==10 and all(d.get('kind') for d in docs)
 print('PASS Helm rendered',ns,len(docs),'objects at accepted digest')
# Validate every Python source, shell script and all recovery/unit tests.
for directory in ['devsecops','app']:
 for p in pathlib.Path(directory).rglob('*.py'):
  if '__pycache__' not in str(p):ast.parse(p.read_text())
run(['bash','-n','tests/phase-p6.sh']);run(['python3','devsecops/test-recovery.py']);print(subprocess.run(['python3','-m','unittest','discover','-s','tests','-v'],cwd='app',check=True,capture_output=True,text=True).stderr)
print(run(['tests/phase-p6.sh','--read-only']))
# Give CNPG time to demonstrate no recreated-primary loop.
time.sleep(30)
after={ns:get(ns,'pod','demo-db-1')['metadata']['uid'] for ns in ['dev','staging','prod']};assert before==after
for ns in before:
 db=get(ns,'cluster','demo-db');assert db['status']['phase']=='Cluster in healthy state'
 print('PASS stable database UID',ns,before[ns])
secret_paths=['.secrets/p6/forgejo-token','.secrets/p6/woodpecker-token','.secrets/p6/woodpecker-grpc-secret','.secrets/p3/zot-password','.secrets/cosign.password','.secrets/cosign.key','.secrets/forgejo-admin-password']
secrets=[pathlib.Path(p).read_bytes().strip() for p in secret_paths if pathlib.Path(p).exists()]
if pathlib.Path('.secrets/p6/oauth.json').exists():secrets.append(json.loads(pathlib.Path('.secrets/p6/oauth.json').read_text())['client_secret'].encode())
files=[p for directory in ['app','devsecops','evidence/p6'] for p in pathlib.Path(directory).rglob('*') if p.is_file() and '__pycache__' not in str(p)]
leaks=[str(p) for p in files if any(len(secret)>=16 and secret in p.read_bytes() for secret in secrets)]
assert not leaks,'SECRET LEAK detected in paths '+','.join(leaks)
print('PASS private-value secret scan; no values emitted; files checked',len(files))
resource={'quotaPlusOperatorMaximumBytes':total_max,'quotaPlusOperatorMaximumGiB':total_max/1024**3,'activeEffectiveLimitsMiB':sum(p['effectiveMemoryLimitBytes'] for p in pods)/1024**2,'pods':pods,'databaseUidsStableOver30Seconds':before,'maxConcurrentWorkflows':1,'nodeSelector':env['WOODPECKER_BACKEND_K8S_POD_NODE_SELECTOR'],'secretValueLeakCount':len(leaks)}
pathlib.Path('evidence/p6/resource-audit.json').write_text(json.dumps(resource,indent=2)+'\n')
for cmd in [['kubectl','get','nodes'],['kubectl','top','nodes'],['kubectl','-n','argocd','get','applications'],['free','-g'],['uptime'],['date']]:print(run(cmd))
print('PASS final runtime/config/security/resource audit')
