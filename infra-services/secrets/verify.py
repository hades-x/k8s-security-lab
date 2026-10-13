#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Read-back verification; no credential, Secret value or token is printed."""
import json,pathlib,subprocess,time,urllib.request
R=pathlib.Path('/data/k8s-lab');k=str(R/'bin/kubectl')
def obj(args):return json.loads(subprocess.check_output([k]+args+['-o','json']))
s=obj(['-n','secrets','get','secret','demo-synced']);assert sorted(s['data'])==['message']
store=obj(['get','clustersecretstore','lab-openbao']);assert any(c['type']=='Ready' and c['status']=='True' for c in store['status']['conditions'])
es=obj(['-n','secrets','get','externalsecret','demo']);assert any(c['type']=='Ready' and c['status']=='True' for c in es['status']['conditions'])
status=json.loads(subprocess.check_output([k,'-n','secrets','exec','openbao-0','--','bao','status','-format=json']));assert status['initialized'] and not status['sealed']
token=json.loads((R/'.secrets/p3/openbao-init.json').read_text())['root_token']
p=subprocess.Popen([k,'-n','secrets','port-forward','svc/openbao','18200:8200'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def get(path):
 req=urllib.request.Request('http://127.0.0.1:18200/v1/'+path,headers={'X-Vault-Token':token})
 return json.load(urllib.request.urlopen(req,timeout=10))
try:
 for _ in range(30):
  try:mounts=get('sys/mounts');break
  except OSError:time.sleep(1)
 mounts=mounts.get('data',mounts);assert mounts['kv/']['type']=='kv' and mounts['kv/']['options']['version']=='2'
 auth=get('sys/auth');auth=auth.get('data',auth);assert auth['kubernetes/']['type']=='kubernetes'
 kv=get('kv/data/demo')['data']['data'];assert sorted(kv)==sorted(s['data'])
 print(f'PASS: OpenBao initialized={status["initialized"]} sealed={status["sealed"]} storage={status["storage_type"]}; KV v2 and Kubernetes auth enabled')
 print('PASS: ClusterSecretStore lab-openbao Ready=True; ExternalSecret demo Ready=True; Kubernetes Secret demo-synced exists; matching source/target key names=[message]; values withheld')
finally:p.terminate();p.wait(timeout=10)
