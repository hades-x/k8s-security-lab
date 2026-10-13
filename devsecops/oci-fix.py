#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import os,pathlib,subprocess,yaml
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
p=pathlib.Path('devsecops/test-recovery.py');text=p.read_text();marker='    def test_grpc_signing_key_is_declared_as_secret_reference(self):'
test='''    def test_zot_publisher_preserves_oci_manifest(self):
        pipeline = yaml.safe_load(Path('app/.woodpecker.yaml').read_text())
        build = next(s for s in pipeline['steps'] if s['name'] == 'daemonless-build')
        self.assertIn('--oci-layout-path', ' '.join(build['commands']))
        self.assertIn('crane push image-oci', Path('app/ci/publish.sh').read_text())
'''
if test not in text:p.write_text(text.replace(marker,test+marker))
r=subprocess.run(['python3','devsecops/test-recovery.py'],capture_output=True,text=True);pathlib.Path('evidence/p6/16-oci-red.log').write_text(r.stdout+r.stderr);print(r.stdout+r.stderr);assert r.returncode!=0
p=pathlib.Path('app/.woodpecker.yaml');v=yaml.safe_load(p.read_text())
for step in v['steps']:
 if step['name']=='daemonless-build':step['commands']=[x.replace('--tar-path "$PWD/image.tar"','--tar-path "$PWD/image.tar" --oci-layout-path "$PWD/image-oci"') for x in step['commands']]
p.write_text(yaml.safe_dump(v,sort_keys=False))
for path in ['app/ci/publish.sh','devsecops/pipeline-create.py']:
 p=pathlib.Path(path);text=p.read_text().replace('crane push image.tar','crane push image-oci')
 if path.endswith('pipeline-create.py'):text=text.replace('--tar-path "$PWD/image.tar"','--tar-path "$PWD/image.tar" --oci-layout-path "$PWD/image-oci"')
 p.write_text(text)
for path in ['app/.gitignore','app/.dockerignore']:
 p=pathlib.Path(path);text=p.read_text()
 for line in ['image-oci/','.ci-bin/','.ci-auth/']:
  if line not in text:text+=line+'\n'
 p.write_text(text)
subprocess.run(['python3','devsecops/test-recovery.py'],check=True)
print('PASS zot compatibility fixed at artifact boundary; no registry settings changed')
