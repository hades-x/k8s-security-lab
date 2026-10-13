#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Fix lab offline key attestors; use existing CA issuer for prod, no exemption."""
import os,pathlib,yaml,subprocess
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
p=pathlib.Path('devsecops/test-recovery.py');text=p.read_text();marker='    def test_grpc_signing_key_is_declared_as_secret_reference(self):'
test='''    def test_offline_lab_attestor_opts_out_of_unpublished_sct(self):
        policy = yaml.safe_load(Path('devsecops/lab-prod-signatures.yaml').read_text())
        keys = policy['spec']['rules'][0]['verifyImages'][0]['attestors'][0]['entries'][0]['keys']
        self.assertTrue(keys.get('ctlog', {}).get('ignoreSCT'), 'Private-key lab signatures have no SCT')
        self.assertTrue(keys['rekor']['ignoreTlog'])
'''
if test not in text:p.write_text(text.replace(marker,test+marker))
r=subprocess.run(['python3','devsecops/test-recovery.py'],capture_output=True,text=True);pathlib.Path('evidence/p6/24-offline-attestor-red.log').write_text(r.stdout+r.stderr);print(r.stdout+r.stderr);assert r.returncode!=0
p=pathlib.Path('devsecops/install-signature-gate.py');text=p.read_text();old="for image in rule['verifyImages']:image['imageRegistryCredentials']={'secrets':['p6-zot-auth']}"
new="for image in rule['verifyImages']:\n  image['imageRegistryCredentials']={'secrets':['p6-zot-auth']}\n  for attestor in image['attestors']:\n   for entry in attestor['entries']:\n    if 'keys' in entry: entry['keys']['ctlog']={'ignoreSCT':True}"
assert old in text;p.write_text(text.replace(old,new))
subprocess.run(['python3','devsecops/install-signature-gate.py','Enforce'],check=True)
subprocess.run(['python3','devsecops/test-recovery.py'],check=True)
# Prod verifies every pod image, so an upstream unsigned ACME solver must not bypass policy.
# Existing lab-ca issuer signs via API without a solver pod. Dev/staging keep ACME.
p=pathlib.Path('app/chart/templates/workloads.yaml');text=p.read_text();old='cert-manager.io/cluster-issuer: lab-acme';new='cert-manager.io/cluster-issuer: {{ .Values.certificateIssuer | default "lab-acme" }}';assert old in text;p.write_text(text.replace(old,new))
p=pathlib.Path('app/chart/values-prod.yaml');v=yaml.safe_load(p.read_text());v['certificateIssuer']='lab-ca';p.write_text(yaml.safe_dump(v))
print('PASS SCT offline attestor fix; prod chart can use lab-ca issuer without unsigned ACME pod')
