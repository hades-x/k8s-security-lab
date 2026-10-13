
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Commit a verified digest to DEV only. Promotion is a separate Git change."""
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
