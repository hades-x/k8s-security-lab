#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Recover ONLY owned P6 objects, leaving healthy Kyverno untouched."""
import os, pathlib, subprocess, json, yaml, secrets
os.chdir('/data/k8s-lab'); os.environ['LC_ALL']='C'
def run(args, **kw): return subprocess.run(args, check=True, **kw)
def apply(doc): run(['kubectl','apply','-f','-'], input=yaml.safe_dump(doc).encode())
def replace(path, old, new):
    p=pathlib.Path(path); text=p.read_text()
    if new in text: return
    if old in text: p.write_text(text.replace(old,new))
    else: raise RuntimeError('Expected source missing: '+path)
# Root cause: a ConfigMap volume is a directory, chart expects a file source.
replace('devsecops/install-signature-gate.py', "overlay={'global':{'caCertificates':{'volume':{'configMap':{'name':'p6-lab-ca','items':[{'key':'root_ca.crt','path':'ca-certificates.crt'}]}}}}}", "def registry_ca_overlay(ca):\n return {'global': {'caCertificates': {'data': ca}}}\noverlay=registry_ca_overlay(pathlib.Path('.secrets/pki/root_ca.crt').read_text())")
# Skip shared Helm upgrade unless explicitly requested; both overlays mandatory.
replace('devsecops/install-signature-gate.py', "run(['helm','upgrade','--install','kyverno'", "if '--upgrade' in sys.argv: run(['helm','upgrade','--install','kyverno'")
replace('devsecops/install-signature-gate.py', "policy['spec']['validationFailureAction']=sys.argv[1] if len(sys.argv)>1 else 'Audit'", "policy['spec']['validationFailureAction']=next((x for x in sys.argv[1:] if x in ['Audit','Enforce']), 'Enforce')")
pathlib.Path('devsecops/kyverno-registry-values.yaml').write_text(yaml.safe_dump({'global': {'caCertificates': {'data': pathlib.Path('.secrets/pki/root_ca.crt').read_text()}}}))
for ns in ['dev','staging','prod']:
    policy={'apiVersion':'cilium.io/v2','kind':'CiliumNetworkPolicy','metadata':{'name':'p6-cnpg-apiserver','namespace':ns},'spec':{'endpointSelector':{'matchLabels':{'cnpg.io/cluster':'demo-db'}},'egress':[{'toEntities':['kube-apiserver'],'toPorts':[{'ports':[{'port':'6443','protocol':'TCP'},{'port':'443','protocol':'TCP'}]}]}]}}
    p=pathlib.Path('devsecops/netpol/'+ns+'-cnpg-api.yaml'); p.write_text(yaml.safe_dump(policy)); apply(policy)
# Persist JWT gRPC signing key, preserving shared agent authentication key.
p=pathlib.Path('.secrets/p6/woodpecker-grpc-secret')
if not p.exists(): p.write_text(secrets.token_hex(32)); p.chmod(0o600)
apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'woodpecker-grpc','namespace':'ci'},'stringData':{'WOODPECKER_GRPC_SECRET':p.read_text()}})
p=pathlib.Path('devsecops/woodpecker-values.yaml'); values=yaml.safe_load(p.read_text()); values['server']['extraSecretNamesForEnvFrom']=['woodpecker-forgejo','woodpecker-grpc']; p.write_text(yaml.safe_dump(values,sort_keys=False))
replace('devsecops/bootstrap-ci.py', "'extraSecretNamesForEnvFrom':['woodpecker-forgejo']", "'extraSecretNamesForEnvFrom':['woodpecker-forgejo','woodpecker-grpc']")
replace('devsecops/bootstrap-ci.py', "print('PASS Forgejo token stored privately')", "grpc=P/'woodpecker-grpc-secret'\nif not grpc.exists(): grpc.write_text(secrets.token_hex(32)); grpc.chmod(0o600)\nprint('PASS Forgejo token stored privately')")
replace('devsecops/bootstrap-ci.py', "rootca=pathlib.Path('.secrets/pki/root_ca.crt').read_text()", "apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'woodpecker-grpc','namespace':'ci'},'stringData':{'WOODPECKER_GRPC_SECRET':grpc.read_text()}})\nrootca=pathlib.Path('.secrets/pki/root_ca.crt').read_text()")
run(['kubectl','-n','ci','set','env','statefulset/woodpecker-server','--from=secret/woodpecker-grpc'])
run(['kubectl','-n','ci','rollout','status','statefulset/woodpecker-server','--timeout=180s'])
run(['kubectl','-n','ci','rollout','restart','statefulset/woodpecker-agent'])
run(['kubectl','-n','ci','rollout','status','statefulset/woodpecker-agent','--timeout=180s'])
server=json.loads(run(['kubectl','-n','ci','get','sts','woodpecker-server','-o','json'],capture_output=True,text=True).stdout)
assert any(e.get('valueFrom',{}).get('secretKeyRef',{}).get('name')=='woodpecker-grpc' for e in server['spec']['template']['spec']['containers'][0]['env'])
# 768Mi active publisher + server/agent + init <=1536Mi CI quota.
p=pathlib.Path('app/.woodpecker.yaml'); pipeline=yaml.safe_load(p.read_text())
for step in pipeline['steps']:
    if step['name']=='push-sign-gitops-dev': step['backend_options']['kubernetes']['resources']['limits']['memory']='768Mi'
p.write_text(yaml.safe_dump(pipeline,sort_keys=False))
replace('devsecops/pipeline-create.py', "'commands':['sh ci/publish.sh'],'backend_options':backend('256Mi')", "'commands':['sh ci/publish.sh'],'backend_options':backend('768Mi')")
# Stream compressed archive and crane member rather than buffering archive.
old='with tarfile.open(fileobj=io.BytesIO(r.read()),mode="r:gz") as t:p.write_bytes(t.extractfile("crane").read())'
new='with tarfile.open(fileobj=r,mode="r|gz") as t:\n                    for member in t:\n                        if member.name in ("crane", "./crane"):\n                            with t.extractfile(member) as source, p.open("wb") as out:\n                                while chunk := source.read(1024*1024): out.write(chunk)\n                            break\n                    else: raise RuntimeError("Missing crane archive member")'
for path in ['app/ci/tools.py','devsecops/pipeline-create.py']: replace(path,old,new)
run(['python3','devsecops/test-recovery.py'])
# Retry exhausted initdb Job, preserve PVC and all database secrets/data.
result=subprocess.run(['kubectl','-n','dev','get','job','demo-db-1-initdb','-o','json'],capture_output=True,text=True)
if result.returncode and 'NotFound' not in result.stderr: result.check_returncode()
job=json.loads(result.stdout) if result.returncode==0 else {}
if any(c.get('type')=='Failed' and c.get('status')=='True' for c in job.get('status',{}).get('conditions',[])):
    run(['kubectl','-n','dev','delete','job','demo-db-1-initdb','--wait=true'])
print('PASS P6 recovery installed; healthy shared Kyverno deployments not modified')
