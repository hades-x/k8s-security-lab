#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Use verified legacy simple-signing format for this Kyverno version."""
import os,pathlib,subprocess,json,yaml
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C';os.environ['DOCKER_CONFIG']=str(pathlib.Path('.secrets/p6').resolve());os.environ['SSL_CERT_FILE']=str(pathlib.Path('.secrets/pki/root_ca.crt').resolve());os.environ['COSIGN_PASSWORD']=pathlib.Path('.secrets/cosign.password').read_text().strip()
p=pathlib.Path('devsecops/test-recovery.py');text=p.read_text();marker='    def test_grpc_signing_key_is_declared_as_secret_reference(self):';test='''    def test_signer_emits_kyverno_compatible_simple_signing(self):
        self.assertIn('--new-bundle-format=false', Path('app/ci/publish.sh').read_text())
'''
if test not in text:p.write_text(text.replace(marker,test+marker))
r=subprocess.run(['python3','devsecops/test-recovery.py'],capture_output=True,text=True);pathlib.Path('evidence/p6/28-signature-format-red.log').write_text(r.stdout+r.stderr);print(r.stdout+r.stderr);assert r.returncode!=0
for path in ['app/ci/publish.sh','devsecops/pipeline-create.py','devsecops/install-data-platform.py']:
 p=pathlib.Path(path);text=p.read_text()
 if path.endswith('install-data-platform.py'):text=text.replace("'--use-signing-config=false','--registry-referrers-mode=legacy'", "'--use-signing-config=false','--new-bundle-format=false','--registry-referrers-mode=legacy'")
 else:text=text.replace('--use-signing-config=false --registry-referrers-mode=legacy','--use-signing-config=false --new-bundle-format=false --registry-referrers-mode=legacy')
 p.write_text(text)
subprocess.run(['python3','devsecops/test-recovery.py'],check=True)
refs=[v['image'] for v in json.loads(pathlib.Path('devsecops/infra-images.json').read_text()).values()]
for ref in refs:
 subprocess.run(['bin/cosign','sign','--yes','--key','.secrets/cosign.key','--tlog-upload=false','--use-signing-config=false','--new-bundle-format=false','--registry-referrers-mode=legacy',ref],check=True)
 subprocess.run(['bin/cosign','verify','--key','app/ci/cosign.pub','--insecure-ignore-tlog=true',ref],check=True,stdout=subprocess.DEVNULL)
 tag=ref.split('@')[0]+':'+ref.split('@')[1].replace(':','-')+'.sig'
 subprocess.run(['bin/crane','manifest',tag],check=True,stdout=subprocess.DEVNULL)
 print('PASS simple-signing signature exists + cryptographically verified '+ref,flush=True)
# Retry only owned failed prod issuance after changing issuer; no certificate/key deletion.
r=subprocess.run(['kubectl','-n','prod','get','certificaterequest','orders-tls-1','-o','json'],capture_output=True,text=True)
if r.returncode==0 and json.loads(r.stdout)['spec']['issuerRef']['name']=='lab-acme':
 subprocess.run(['kubectl','-n','prod','delete','certificaterequest','orders-tls-1','--wait=true'],check=True)
print('PASS signer compatibility fixed in source + generator; existing infrastructure images re-signed')
