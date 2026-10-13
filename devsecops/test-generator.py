#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Exercise pipeline generation in a file sandbox, with all external writes blocked."""
import ast,pathlib,tempfile,shutil,subprocess,os,json,yaml
root=pathlib.Path('/data/k8s-lab');os.chdir(root);os.environ['LC_ALL']='C'
sandbox=pathlib.Path(tempfile.mkdtemp(prefix='generator-',dir=root/'.secrets/p6'))
(sandbox/'bin').mkdir();(sandbox/'hardening/kyverno').mkdir(parents=True)
for binary in ['crane','cosign']:(sandbox/'bin'/binary).symlink_to(root/'bin'/binary)
shutil.copyfile(root/'hardening/kyverno/cosign.pub',sandbox/'hardening/kyverno/cosign.pub')
source=ast.parse((root/'devsecops/pipeline-create.py').read_text())
changes=0
for n in ast.walk(source):
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='os' and n.func.attr=='chdir':
  assert n.args[0].value==str(root)
  n.args[0]=ast.Constant(value=str(sandbox));changes+=1
assert changes==1
ast.fix_missing_locations(source)
real_run=subprocess.run
class Result:
 returncode=0
try:
 subprocess.run=lambda *a,**k:Result()
 exec(compile(source,'<isolated-pipeline-generator>','exec'),{'__name__':'__p6_generator_check__'})
finally:subprocess.run=real_run;os.chdir(root)
for path in (sandbox/'app/ci').glob('*.py'):ast.parse(path.read_text())
pipeline=yaml.safe_load((sandbox/'app/.woodpecker.yaml').read_text());live=yaml.safe_load((root/'app/.woodpecker.yaml').read_text());assert pipeline==live
for name in ['publish.sh','tools.py','update-gitops.py','cosign.pub']:
 assert (sandbox/'app/ci'/name).read_bytes()==(root/'app/ci'/name).read_bytes(),'Generator mismatch '+name
print('PASS isolated generator reproduces identical tested pipeline + four CI files; no kubectl/Git mutation')
(root/'evidence/p6/40-generator-replay.log').write_text('PASS isolated pipeline generator equals tested pipeline, publisher, tool fetcher, GitOps updater and public key; generated Python parses; external commands suppressed\n')
