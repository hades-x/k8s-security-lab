#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Configure only disposable OpenBao, using local init token without logging it."""
import json,pathlib,subprocess,time,urllib.request,urllib.error
R=pathlib.Path('/data/k8s-lab');token=json.loads((R/'.secrets/p3/openbao-init.json').read_text())['root_token']
pf=subprocess.Popen([str(R/'bin/kubectl'),'-n','secrets','port-forward','svc/openbao','18200:8200'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def api(method,path,data=None):
 req=urllib.request.Request('http://127.0.0.1:18200/v1/'+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'X-Vault-Token':token,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=10) as r:b=r.read();return json.loads(b) if b else {}
 except urllib.error.HTTPError as e:
  if e.code==404 and method=='GET':return None
  raise RuntimeError(f'OpenBao {method} {path} HTTP {e.code}; response withheld') from None
try:
 for _ in range(60):
  try:api('GET','sys/health');break
  except (OSError,RuntimeError):time.sleep(1)
 else:raise RuntimeError('OpenBao port-forward failed')
 mounts=api('GET','sys/mounts');mounts=mounts.get('data',mounts)
 if 'kv/' not in mounts:api('POST','sys/mounts/kv',{'type':'kv','options':{'version':'2'}})
 auth=api('GET','sys/auth');auth=auth.get('data',auth)
 if 'kubernetes/' not in auth:api('POST','sys/auth/kubernetes',{'type':'kubernetes'})
 ca=subprocess.check_output([str(R/'bin/kubectl'),'-n','secrets','exec','openbao-0','--','cat','/var/run/secrets/kubernetes.io/serviceaccount/ca.crt']).decode()
 # Omitted token_reviewer_jwt uses the OpenBao pod SA and periodically refreshed local token.
 api('POST','auth/kubernetes/config',{'kubernetes_host':'https://kubernetes.default.svc:443','kubernetes_ca_cert':ca,'disable_local_ca_jwt':False})
 api('PUT','sys/policies/acl/eso-demo',{'policy':'path "kv/data/demo" { capabilities = ["read"] }\npath "kv/metadata/demo" { capabilities = ["read"] }'})
 api('POST','auth/kubernetes/role/eso-demo',{'bound_service_account_names':['eso-openbao'],'bound_service_account_namespaces':['secrets'],'audience':'openbao','policies':['eso-demo'],'token_ttl':'1h'})
 if api('GET','kv/data/demo') is None:api('POST','kv/data/demo',{'data':{'message':'lab-demo-not-a-production-secret'}})
 print('PASS: KV v2, Kubernetes auth, least-privilege ESO policy and demo configured')
finally:pf.terminate();pf.wait(timeout=10)
