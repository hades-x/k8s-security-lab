#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import os,pathlib,subprocess,yaml,json,hashlib,requests
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
def write(p,s):p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
cranehash=hashlib.sha256(pathlib.Path('bin/crane').read_bytes()).hexdigest();cosignhash=hashlib.sha256(pathlib.Path('bin/cosign').read_bytes()).hexdigest()
write('app/ci/tools.py','''"""Pinned upstream static tools; refuse checksum mismatch before executing."""
import urllib.request, pathlib, tarfile, hashlib, io
P=pathlib.Path(".ci-bin");P.mkdir(exist_ok=True)
tools=[("crane","https://github.com/google/go-containerregistry/releases/download/v0.22.1/go-containerregistry_Linux_x86_64.tar.gz","CRANEHASH"),
       ("cosign","https://github.com/sigstore/cosign/releases/download/v3.1.3/cosign-linux-amd64","COSIGNHASH")]
for name,url,expected in tools:
    p=P/name
    if not p.exists():
        with urllib.request.urlopen(url,timeout=120) as r:
            if name=="crane":
                with tarfile.open(fileobj=r,mode="r|gz") as t:
                    for member in t:
                        if member.name in ("crane", "./crane"):
                            with t.extractfile(member) as source, p.open("wb") as out:
                                while chunk := source.read(1024*1024): out.write(chunk)
                            break
                    else: raise RuntimeError("Missing crane archive member")
            else:
                with p.open("wb") as out:
                    while chunk := r.read(1024*1024): out.write(chunk)
    h=hashlib.sha256()
    with p.open("rb") as source:
        while chunk := source.read(1024*1024): h.update(chunk)
    assert h.hexdigest()==expected,"Checksum mismatch: "+name
    p.chmod(0o755)
    print("PASS pinned binary checksum "+name+" "+expected)
'''.replace('CRANEHASH',cranehash).replace('COSIGNHASH',cosignhash))
write('app/ci/publish.sh','''#!/bin/sh
set -eu
apk add --no-cache python3 py3-yaml ca-certificates >/dev/null
python3 - <<'PY'
import os,pathlib,base64,json
p=pathlib.Path('.ci-auth');p.mkdir(exist_ok=True);p.chmod(0o700)
(p/'config.json').write_text(json.dumps({'auths':{'zot.192.168.150.200.sslip.io':{'auth':base64.b64encode(('lab:'+os.environ['ZOT_PASSWORD']).encode()).decode()}}}))
(p/'cosign.key').write_text(os.environ['COSIGN_KEY']);(p/'cosign.key').chmod(0o600)
pathlib.Path('/usr/local/share/ca-certificates/lab.crt').write_text(os.environ['LAB_CA'])
PY
trap 'rm -rf .ci-auth' EXIT
update-ca-certificates >/dev/null
python3 ci/tools.py
export DOCKER_CONFIG="$PWD/.ci-auth"
ref="zot.192.168.150.200.sslip.io/lab/demo-app:$CI_COMMIT_SHA"
.ci-bin/crane push image-oci "$ref"
digest=$(.ci-bin/crane digest "$ref")
test "$digest" = "$(tr -d '\\n' < image.digest)"
ref="zot.192.168.150.200.sslip.io/lab/demo-app@$digest"
.ci-bin/cosign sign --yes --key .ci-auth/cosign.key --tlog-upload=false --use-signing-config=false --new-bundle-format=false --registry-referrers-mode=legacy "$ref"
.ci-bin/cosign verify --key ci/cosign.pub --insecure-ignore-tlog=true "$ref" >/dev/null
export IMAGE_DIGEST="$digest"
python3 ci/update-gitops.py
printf 'PASS pushed scanned signed verified image %s\\n' "$ref"
''')
write('app/ci/update-gitops.py','''"""Commit a verified digest to DEV only. Promotion is a separate Git change."""
import urllib.request,json,os,base64,yaml,time
F="https://forgejo.192.168.150.200.sslip.io/api/v1/repos/lab/demo-app-deploy/contents/chart/values-dev.yaml"
headers={"Authorization":"token "+os.environ["FORGEJO_TOKEN"],"Content-Type":"application/json"}
with urllib.request.urlopen(urllib.request.Request(F,headers=headers),timeout=30) as r:old=json.load(r)
v=yaml.safe_load(base64.b64decode(old["content"]).decode());v["image"]={"repository":"zot.192.168.150.200.sslip.io/lab/demo-app","digest":os.environ["IMAGE_DIGEST"]}
v["buildRevision"]=os.environ["CI_COMMIT_SHA"]
body={"branch":"main","sha":old["sha"],"content":base64.b64encode(yaml.safe_dump(v).encode()).decode(),
      "message":"dev: deploy scanned + signed image "+os.environ["CI_COMMIT_SHA"]}
req=urllib.request.Request(F,data=json.dumps(body).encode(),headers=headers,method="PUT")
with urllib.request.urlopen(req,timeout=30) as r:new=json.load(r)
with urllib.request.urlopen(urllib.request.Request(F,headers=headers),timeout=30) as r:check=json.load(r)
assert yaml.safe_load(base64.b64decode(check["content"]))["image"]["digest"]==os.environ["IMAGE_DIGEST"]
print("PASS GitOps DEV digest committed and read back; commit="+new["commit"]["sha"])
''')
write('app/ci/cosign.pub',pathlib.Path('hardening/kyverno/cosign.pub').read_text())
alpine='alpine:3.23.4@sha256:5b10f432ef3da1b8d4c7eb6c487f2f5a8f096bc91145e68878dd4a5019afde11'
python='python:3.14.8-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83'
kaniko='gcr.io/kaniko-project/executor:v1.24.0-debug@sha256:2562c4fe551399514277ffff7dcca9a3b1628c4ea38cb017d7286dc6ea52f4cd'
trivy='aquasec/trivy:0.75.0@sha256:af6acf9a6b85dfe389a1941505c0ce9efef52a4719635e1a962f022a3d855daa'
def backend(memory,cpu='1'):
 return {'kubernetes':{'securityContext':{'runAsUser':0,'runAsGroup':0,'allowPrivilegeEscalation':False,'seccompProfile':{'type':'RuntimeDefault'}},'resources':{'requests':{'cpu':'100m','memory':'64Mi'},'limits':{'cpu':cpu,'memory':memory}}}}
pipeline={'when':[{'event':'push','branch':'main'}],'skip_clone':True,'steps':[
 {'name':'clone','image':alpine,'environment':{'LAB_CA':{'from_secret':'lab_ca'}},'commands':['apk add --no-cache git ca-certificates >/dev/null',"printf '%s' \"$LAB_CA\" > /usr/local/share/ca-certificates/lab.crt",'update-ca-certificates >/dev/null','git init .','git remote add origin https://forgejo.192.168.150.200.sslip.io/lab/demo-app.git','git fetch --depth=1 origin "$CI_COMMIT_SHA"','git checkout --detach FETCH_HEAD'],'backend_options':backend('192Mi')},
 {'name':'unit-test','image':python,'commands':['python -m unittest discover -s tests -v'],'backend_options':backend('128Mi')},
 {'name':'daemonless-build','image':kaniko,'commands':['/kaniko/executor --context "$PWD" --dockerfile "$PWD/Dockerfile" --destination "zot.192.168.150.200.sslip.io/lab/demo-app:$CI_COMMIT_SHA" --build-arg "BUILD_REVISION=$CI_COMMIT_SHA" --no-push --tar-path "$PWD/image.tar" --oci-layout-path "$PWD/image-oci" --digest-file "$PWD/image.digest" --snapshot-mode=redo --use-new-run --cache=false'],'backend_options':backend('768Mi','2')},
 {'name':'trivy-critical-gate','image':trivy,'commands':['trivy image --input image.tar --scanners vuln --parallel 1 --severity CRITICAL --ignore-unfixed --exit-code 1 --format json --output trivy.json','trivy image --input image.tar --scanners vuln --parallel 1 --severity CRITICAL --ignore-unfixed --exit-code 1'],'backend_options':backend('768Mi','2')},
 {'name':'push-sign-gitops-dev','image':alpine,'environment':{'LAB_CA':{'from_secret':'lab_ca'},'ZOT_PASSWORD':{'from_secret':'zot_password'},'COSIGN_KEY':{'from_secret':'cosign_key'},'COSIGN_PASSWORD':{'from_secret':'cosign_password'},'FORGEJO_TOKEN':{'from_secret':'forgejo_token'}},'commands':['sh ci/publish.sh'],'backend_options':backend('768Mi')}]}
write('app/.woodpecker.yaml',yaml.safe_dump(pipeline,sort_keys=False))
# A default LimitRange also limits the Kubernetes backend workspace-permission init container.
for doc in [{'apiVersion':'v1','kind':'LimitRange','metadata':{'name':'ci-limits','namespace':'ci'},'spec':{'limits':[{'type':'Container','default':{'cpu':'500m','memory':'128Mi'},'defaultRequest':{'cpu':'25m','memory':'32Mi'}}]}},{'apiVersion':'v1','kind':'ResourceQuota','metadata':{'name':'ci-budget','namespace':'ci'},'spec':{'hard':{'limits.memory':'1536Mi','requests.memory':'1Gi','limits.cpu':'4','pods':'8','requests.storage':'8Gi'}}}]:
 subprocess.run(['kubectl','apply','-f','-'],input=yaml.safe_dump(doc).encode(),check=True)
# No build step inherits the agent's API permissions.
subprocess.run(['kubectl','-n','ci','patch','serviceaccount','default','-p','{"automountServiceAccountToken":false}'],check=True)
print('PASS pipeline generated: unit -> daemonless tar build -> CRITICAL/fixed scan -> push -> cosign -> DEV Git commit')
