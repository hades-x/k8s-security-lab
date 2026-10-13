#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Only create P6 Argo Applications; no shared Argo settings changed."""
import os,pathlib,subprocess,yaml,json,sys
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
nslist=sys.argv[1:] or ['dev']
def run(args,**kw):return subprocess.run(['kubectl']+args,check=True,**kw)
apps=[]
for ns in nslist:
 app={'apiVersion':'argoproj.io/v1alpha1','kind':'Application','metadata':{'name':'demo-app-'+ns,'namespace':'argocd'},'spec':{'project':'default','source':{'repoURL':'http://forgejo-http.forgejo.svc.cluster.local:3000/lab/demo-app-deploy.git','targetRevision':'main','path':'chart','helm':{'valueFiles':['values-'+ns+'.yaml']}},'destination':{'server':'https://kubernetes.default.svc','namespace':ns},'syncPolicy':{'automated':{'prune':True,'selfHeal':True},'syncOptions':['CreateNamespace=false'],'retry':{'limit':10,'backoff':{'duration':'10s','factor':2,'maxDuration':'1m'}}}}}
 apps.append(app)
path=pathlib.Path('devsecops/argocd');path.mkdir(exist_ok=True)
for app in apps:
 p=path/(app['metadata']['name']+'.yaml');p.write_text(yaml.safe_dump(app));run(['apply','-f',str(p)])
run(['-n','argocd','get','applications','-o','wide'])
print('PASS Argo Applications created: '+','.join(nslist)+'; public Git source via internal service, no shared TLS config modification')
