#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Install a pinned checksum-verified crane into lab-local bin only."""
import pathlib,urllib.request,hashlib,tarfile,io
R=pathlib.Path('/data/k8s-lab');V='v0.22.1';ASSET='go-containerregistry_Linux_x86_64.tar.gz';SHA='0ab7a1d6932a213aed964ce97666c3077fe691c8606413674a8b3e0b9ec4cda0';BIN_SHA='8e75c326adb43b053cfd78b9b987663f8f4fe4557f4d3915905643f25c730992';p=R/'bin/crane'
if p.exists():
 assert hashlib.sha256(p.read_bytes()).hexdigest()==BIN_SHA, 'Existing crane differs from pin; inspect manually'
 print('PASS: installed crane '+V+' binary SHA-256 verified')
else:
 base='https://github.com/google/go-containerregistry/releases/download/'+V+'/'
 with urllib.request.urlopen(base+ASSET,timeout=60) as f:b=f.read()
 with urllib.request.urlopen(base+'checksums.txt',timeout=30) as f:checks=f.read().decode()
 official=next(l.split()[0] for l in checks.splitlines() if l.split()[-1].lstrip('*')==ASSET)
 assert official==SHA==hashlib.sha256(b).hexdigest()
 with tarfile.open(fileobj=io.BytesIO(b)) as t:p.write_bytes(t.extractfile('crane').read())
 assert hashlib.sha256(p.read_bytes()).hexdigest()==BIN_SHA;p.chmod(0o755)
 print('PASS: downloaded crane '+V+' archive and binary SHA-256 verified')
