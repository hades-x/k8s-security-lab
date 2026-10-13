#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Mirror and sign only prerequisite P6 images into the in-cluster zot."""
import os,pathlib,subprocess,json,yaml,base64
os.chdir('/data/k8s-lab'); os.environ['LC_ALL']='C'
p=pathlib.Path('.secrets/p6');p.mkdir(exist_ok=True);p.chmod(0o700)
registry='zot.192.168.150.200.sslip.io'; password=pathlib.Path('.secrets/p3/zot-password').read_text().strip()
config={'auths':{registry:{'auth':base64.b64encode(('lab:'+password).encode()).decode()}}}
(p/'config.json').write_text(json.dumps(config));(p/'config.json').chmod(0o600)
os.environ['DOCKER_CONFIG']=str(p.resolve());os.environ['SSL_CERT_FILE']=str(pathlib.Path('.secrets/pki/root_ca.crt').resolve());os.environ['COSIGN_PASSWORD']=pathlib.Path('.secrets/cosign.password').read_text().strip()
def run(args,**kw):return subprocess.run(args,check=True,**kw)
versions={}
for name,source,tag in [('cloudnative-pg','ghcr.io/cloudnative-pg/cloudnative-pg','1.30.1'),('postgresql','ghcr.io/cloudnative-pg/postgresql','18.6-202610120828-standard-trixie'),('valkey','valkey/valkey','9.1.2-alpine')]:
 target=registry+'/lab/'+name+':'+tag
 print('Mirroring',source+':'+tag,'->',target,flush=True)
 run(['bin/crane','copy','--platform','linux/amd64',source+':'+tag,target])
 digest=run(['bin/crane','digest',target],capture_output=True,text=True).stdout.strip(); ref=registry+'/lab/'+name+'@'+digest
 run(['bin/cosign','sign','--yes','--key','.secrets/cosign.key','--tlog-upload=false','--use-signing-config=false','--new-bundle-format=false','--registry-referrers-mode=legacy',ref])
 run(['bin/cosign','verify','--key','hardening/kyverno/cosign.pub','--insecure-ignore-tlog=true',ref],stdout=subprocess.DEVNULL)
 versions[name]={'source':source+':'+tag,'image':ref,'tag':tag}; print('PASS mirrored+signed+verified',ref,flush=True)
pathlib.Path('devsecops/infra-images.json').write_text(json.dumps(versions,indent=2)+'\n')
values={'image':{'repository':registry+'/lab/cloudnative-pg','tag':versions['cloudnative-pg']['tag']+'@'+versions['cloudnative-pg']['image'].split('@')[1]},'resources':{'requests':{'cpu':'50m','memory':'64Mi'},'limits':{'cpu':'300m','memory':'192Mi'}},'config':{'maxConcurrentReconciles':2,'data':{'ENABLE_INSTANCE_MANAGER_INPLACE_UPDATES':'false'}}}
pathlib.Path('devsecops/cnpg-values.yaml').write_text(yaml.safe_dump(values))
run(['helm','repo','add','cnpg','https://cloudnative-pg.github.io/charts'])
run(['helm','upgrade','--install','cnpg','cnpg/cloudnative-pg','--version','0.29.1','--namespace','cnpg-system','--create-namespace','-f','devsecops/cnpg-values.yaml','--wait','--timeout','8m'])
print('PASS CNPG 1.30.1 chart 0.29.1 installed')
