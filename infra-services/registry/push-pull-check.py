#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Push/pull/export a real scratch OCI image; credentials stay in .secrets."""
import pathlib,subprocess,os,tarfile,io,hashlib,json
R=pathlib.Path('/data/k8s-lab');D=R/'.secrets/p3/registry-proof';D.mkdir(mode=0o700,exist_ok=True)
env=os.environ|{'DOCKER_CONFIG':str(D),'SSL_CERT_FILE':str(R/'.secrets/pki/root_ca.crt')}
crane=str(R/'bin/crane');host='zot.192.168.150.200.sslip.io';image=host+'/lab/p3-proof:v1'
def run(args,input=None):
 p=subprocess.run([crane]+args,input=input,text=True,capture_output=True,env=env)
 if p.returncode:raise RuntimeError('crane '+args[0]+' failed (output withheld)')
 return p.stdout.strip()
run(['auth','login',host,'-u','lab','--password-stdin'],(R/'.secrets/p3/zot-password').read_text().strip())
for p in D.glob('*'):p.chmod(0o600)
payload=b'K8S-LAB P3 authenticated registry roundtrip\n';layer=D/'layer.tar'
with tarfile.open(layer,'w') as t:
 info=tarfile.TarInfo('proof.txt');info.size=len(payload);info.mode=0o444;t.addfile(info,io.BytesIO(payload))
run(['append','--new_layer',str(layer),'--new_tag',image,'--oci-empty-base'])
digest=run(['digest',image]);assert digest.startswith('sha256:')
run(['pull',image,str(D/'pulled-image.tar')])
run(['export',image,str(D/'export.tar')])
with tarfile.open(D/'export.tar') as t:recovered=t.extractfile('proof.txt').read()
before=hashlib.sha256(payload).hexdigest();after=hashlib.sha256(recovered).hexdigest();assert before==after
for p in D.glob('*'):p.chmod(0o600)
print(f'PASS: authenticated OCI scratch image push + pull + filesystem export\nimage={image}\ndigest={digest}\nbefore_sha256={before}\nafter_sha256={after}\nchecksum_equal=true')
