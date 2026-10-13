#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import os,pathlib,json,yaml,subprocess,time
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
p=pathlib.Path('devsecops/test-recovery.py');text=p.read_text();marker='    def test_grpc_signing_key_is_declared_as_secret_reference(self):';test='''    def test_cnpg_bootstrap_reference_is_immutable(self):
        v = yaml.safe_load(Path('devsecops/cnpg-values.yaml').read_text())
        self.assertIn('@sha256:', v['image']['tag'])
'''
if test not in text:p.write_text(text.replace(marker,test+marker))
r=subprocess.run(['python3','devsecops/test-recovery.py'],capture_output=True,text=True);pathlib.Path('evidence/p6/32-cnpg-digest-red.log').write_text(r.stdout+r.stderr);print(r.stdout+r.stderr);assert r.returncode!=0
image=json.loads(pathlib.Path('devsecops/infra-images.json').read_text())['cloudnative-pg'];tag=image['tag']+'@'+image['image'].split('@')[1];ref=image['image'].split('@')[0]+':'+tag
p=pathlib.Path('devsecops/cnpg-values.yaml');v=yaml.safe_load(p.read_text());v['image']['tag']=tag;p.write_text(yaml.safe_dump(v))
p=pathlib.Path('devsecops/install-data-platform.py');text=p.read_text().replace("'tag':'1.30.1'},'resources'", "'tag':versions['cloudnative-pg']['tag']+'@'+versions['cloudnative-pg']['image'].split('@')[1]},'resources'");p.write_text(text)
subprocess.run(['kubectl','-n','cnpg-system','set','env','deploy/cnpg-cloudnative-pg','OPERATOR_IMAGE_NAME='+ref],check=True)
subprocess.run(['kubectl','-n','cnpg-system','rollout','status','deploy/cnpg-cloudnative-pg','--timeout=120s'],check=True)
subprocess.run(['python3','devsecops/test-recovery.py'],check=True)
for ns in ['dev','staging','prod']:
 subprocess.run(['kubectl','-n',ns,'wait','--for=condition=Ready','cluster/demo-db','--timeout=120s'],check=True)
print('PASS CNPG expected bootstrap image pinned to signed digest; no admission mutation restart loop')
