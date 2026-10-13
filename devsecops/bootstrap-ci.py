#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import os,json,pathlib,requests,subprocess,secrets,yaml
os.environ['LC_ALL']='C'; os.chdir('/data/k8s-lab')
P=pathlib.Path('.secrets/p6'); P.mkdir(exist_ok=True); P.chmod(0o700)
F='https://forgejo.192.168.150.200.sslip.io'; CI='https://ci.192.168.150.200.sslip.io'
s=requests.Session();s.verify='.secrets/pki/root_ca.crt';s.auth=('lab-admin',pathlib.Path('.secrets/forgejo-admin-password').read_text().strip())
def api(method,path,**kw):
 r=s.request(method,F+'/api/v1'+path,**kw)
 if r.status_code>=400: raise RuntimeError('Forgejo '+method+' '+path+' status '+str(r.status_code))
 return r.json() if r.content else None
if not (P/'forgejo-token').exists():
 j=api('POST','/users/lab-admin/tokens',json={'name':'p6-gitops','scopes':['write:repository','write:organization','write:user']})
 (P/'forgejo-token').write_text(j['sha1']); (P/'forgejo-token').chmod(0o600)
grpc=P/'woodpecker-grpc-secret'
if not grpc.exists(): grpc.write_text(secrets.token_hex(32)); grpc.chmod(0o600)
print('PASS Forgejo token stored privately')
r=s.get(F+'/api/v1/orgs/lab')
if r.status_code==404: api('POST','/orgs',json={'username':'lab','full_name':'Disposable DevSecOps Lab','visibility':'public'})
for repo in ['demo-app','demo-app-deploy']:
 r=s.get(F+'/api/v1/repos/lab/'+repo)
 if r.status_code==404: api('POST','/orgs/lab/repos',json={'name':repo,'private':False,'default_branch':'main','auto_init':False,'description':'P6 disposable lab '+repo})
 print('PASS Forgejo repo lab/'+repo,api('GET','/repos/lab/'+repo)['id'])
if not (P/'oauth.json').exists():
 oauth=api('POST','/user/applications/oauth2',json={'name':'Woodpecker P6','redirect_uris':[CI+'/authorize'],'confidential_client':True})
 (P/'oauth.json').write_text(json.dumps(oauth)); (P/'oauth.json').chmod(0o600)
oauth=json.loads((P/'oauth.json').read_text())
def kubectl(args,**kwargs): return subprocess.run(['kubectl']+args,check=True,**kwargs)
def apply(doc): kubectl(['apply','-f','-'],input=yaml.safe_dump(doc).encode())
apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':'ci'}})
apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'woodpecker-forgejo','namespace':'ci'},'type':'Opaque','stringData':{'WOODPECKER_FORGEJO_CLIENT':oauth['client_id'],'WOODPECKER_FORGEJO_SECRET':oauth['client_secret']}})
apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'woodpecker-grpc','namespace':'ci'},'stringData':{'WOODPECKER_GRPC_SECRET':grpc.read_text()}})
rootca=pathlib.Path('.secrets/pki/root_ca.crt').read_text()
apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'lab-root-ca','namespace':'ci'},'data':{'root_ca.crt':rootca}})
security={'runAsUser':1000,'runAsGroup':1000,'runAsNonRoot':True,'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']},'seccompProfile':{'type':'RuntimeDefault'}}
values={'server':{'image':{'tag':'v3.19.0'},'env':{'WOODPECKER_ADMIN':'lab-admin','WOODPECKER_HOST':CI,'WOODPECKER_FORGEJO':'true','WOODPECKER_FORGEJO_URL':F,'WOODPECKER_OPEN':'false','SSL_CERT_FILE':'/etc/ssl/certs/lab-root.pem'},'extraSecretNamesForEnvFrom':['woodpecker-forgejo','woodpecker-grpc'],'extraVolumes':[{'name':'lab-root','configMap':{'name':'lab-root-ca'}}],'extraVolumeMounts':[{'name':'lab-root','mountPath':'/etc/ssl/certs/lab-root.pem','subPath':'root_ca.crt','readOnly':True}],'resources':{'requests':{'cpu':'100m','memory':'128Mi'},'limits':{'cpu':'500m','memory':'256Mi'}},'persistentVolume':{'size':'1Gi','storageClass':'local-path'},'securityContext':security,'ingress':{'enabled':True,'ingressClassName':'traefik','annotations':{'cert-manager.io/cluster-issuer':'lab-acme'},'hosts':[{'host':'ci.192.168.150.200.sslip.io','paths':[{'path':'/','pathType':'Prefix'}]}],'tls':[{'secretName':'ci-tls','hosts':['ci.192.168.150.200.sslip.io']}]}},'agent':{'replicaCount':1,'image':{'tag':'v3.19.0'},'env':{'WOODPECKER_SERVER':'woodpecker-server:9000','WOODPECKER_BACKEND':'kubernetes','WOODPECKER_BACKEND_K8S_NAMESPACE':'ci','WOODPECKER_BACKEND_K8S_STORAGE_CLASS':'local-path','WOODPECKER_BACKEND_K8S_STORAGE_RWX':'false','WOODPECKER_BACKEND_K8S_VOLUME_SIZE':'2Gi','WOODPECKER_BACKEND_K8S_PERMISSION_INIT_IMAGE':'busybox:1.37.0-musl','WOODPECKER_MAX_WORKFLOWS':'1','WOODPECKER_BACKEND_K8S_SECCTX_NONROOT':'false','SSL_CERT_FILE':'/etc/ssl/certs/lab-root.pem'},'extraVolumes':[{'name':'lab-root','configMap':{'name':'lab-root-ca'}}],'extraVolumeMounts':[{'name':'lab-root','mountPath':'/etc/ssl/certs/lab-root.pem','subPath':'root_ca.crt','readOnly':True}],'resources':{'requests':{'cpu':'100m','memory':'64Mi'},'limits':{'cpu':'300m','memory':'128Mi'}},'securityContext':security,'persistence':{'enabled':True,'size':'1Gi','storageClass':'local-path'}}}
pathlib.Path('devsecops/woodpecker-values.yaml').write_text(yaml.safe_dump(values,sort_keys=False))
print('PASS OAuth registered; secret not in chart values')
subprocess.run(['helm','upgrade','--install','woodpecker','oci://ghcr.io/woodpecker-ci/helm/woodpecker','--version','3.7.5','--namespace','ci','-f','devsecops/woodpecker-values.yaml','--wait','--timeout','8m'],check=True)
print('PASS Woodpecker helm pinned chart 3.7.5; server/agent v3.19.0')
