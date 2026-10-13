#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Check generated credentials never leaked into sources or evidence."""
from pathlib import Path
import base64,os,stat
root=Path('/data/k8s-lab');patterns=[]
for name in ('k3s-token','forgejo-admin-password','argocd-admin-password','lab_ed25519'):
 p=root/'.secrets'/name
 assert stat.S_IMODE(p.stat().st_mode)==0o600,name+' is not mode 600'
 raw=p.read_bytes().strip()
 assert raw
 patterns.extend([raw,base64.b64encode(raw),base64.b64encode(raw+b'\n')])
p=root/'.secrets/kubeconfig';assert stat.S_IMODE(p.stat().st_mode)==0o600
for line in p.read_text().splitlines():
 if 'client-key-data:' in line:patterns.append(line.split(':',1)[1].strip().encode())
found=[];count=0
for path in root.rglob('*'):
 if not path.is_file() or any(part in ('.git','.secrets','vms','bin') for part in path.relative_to(root).parts):continue
 count+=1
 data=path.read_bytes()
 if any(pattern in data for pattern in patterns):found.append(str(path.relative_to(root)))
assert not found,'Credential leak in files: '+', '.join(found)
print(f'PASS: credential permissions 600; no generated secret values in {count} source/evidence files')
