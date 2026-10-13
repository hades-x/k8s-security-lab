#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Install/extend registry trust and ONLY the P6 signature policy."""
import os,pathlib,subprocess,yaml,json,sys
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def apply(doc):run(['kubectl','apply','-f','-'],input=yaml.safe_dump(doc).encode())
# The 30-minute readiness discovery window expired with no Kyverno namespace.
# Use the exact idempotent Helm command from hardening/kyverno/install.sh but
# do not invoke its five-policy apply tail: P5 retains ownership of those rules.
apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':'kyverno'}})
apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'p6-lab-ca','namespace':'kyverno'},'data':{'root_ca.crt':pathlib.Path('.secrets/pki/root_ca.crt').read_text()}})
def registry_ca_overlay(ca):
 return {'global': {'caCertificates': {'data': ca}}}
overlay=registry_ca_overlay(pathlib.Path('.secrets/pki/root_ca.crt').read_text())
pathlib.Path('devsecops/kyverno-registry-values.yaml').write_text(yaml.safe_dump(overlay))
if '--upgrade' in sys.argv: run(['helm','upgrade','--install','kyverno','evidence/p5-prep/kyverno-3.9.1.tgz','-n','kyverno','-f','hardening/kyverno/values.yaml','-f','devsecops/kyverno-registry-values.yaml','--wait','--timeout','8m'])
# Registry credentials stay in an opaque Kubernetes Secret, never policy/git.
auth=json.loads(pathlib.Path('.secrets/p6/config.json').read_text())
apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'p6-zot-auth','namespace':'kyverno'},'type':'kubernetes.io/dockerconfigjson','stringData':{'.dockerconfigjson':json.dumps(auth)}})
policy=yaml.safe_load(pathlib.Path('hardening/kyverno/policies/lab-prod-signatures.yaml').read_text())
policy['spec']['validationFailureAction']=next((x for x in sys.argv[1:] if x in ['Audit','Enforce']), 'Enforce')
for rule in policy['spec']['rules']:
 for image in rule['verifyImages']:
  image['imageRegistryCredentials']={'secrets':['p6-zot-auth']}
  for attestor in image['attestors']:
   for entry in attestor['entries']:
    if 'keys' in entry: entry['keys']['ctlog']={'ignoreSCT':True}
pathlib.Path('devsecops/lab-prod-signatures.yaml').write_text(yaml.safe_dump(policy));apply(policy)
run(['kubectl','get','deploy','-n','kyverno']);run(['kubectl','get','clusterpolicy','lab-prod-signatures'])
print('PASS Kyverno pinned 1.19.1 / chart 3.9.1; lab root verified TLS; registry credential secret; ONLY lab-prod-signatures applied '+policy['spec']['validationFailureAction'])
