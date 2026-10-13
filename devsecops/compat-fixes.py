#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Apply verified compatibility fixes: CNPG needs version tag plus digest."""
import pathlib,json,yaml,os,subprocess
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
p=pathlib.Path('app/chart/values.yaml');v=yaml.safe_load(p.read_text());images=json.loads(pathlib.Path('devsecops/infra-images.json').read_text());pg=images['postgresql'];v['postgresImage']=pg['image'].split('@')[0]+':'+pg['tag']+'@'+pg['image'].split('@')[1];p.write_text(yaml.safe_dump(v))
# Preserve the app traffic graph; allow only Traefik -> HTTP-01 solver port.
for ns in ['dev','staging','prod']:
 policy={'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':'p6-acme-solver','namespace':ns},'spec':{'podSelector':{'matchLabels':{'acme.cert-manager.io/http01-solver':'true'}},'policyTypes':['Ingress'],'ingress':[{'from':[{'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':'kube-system'}},'podSelector':{'matchLabels':{'app.kubernetes.io/name':'traefik'}}}],'ports':[{'port':8089}]}]}}
 q=pathlib.Path('devsecops/netpol/'+ns+'-acme.yaml');q.write_text(yaml.safe_dump(policy));subprocess.run(['kubectl','apply','-f',str(q)],check=True)
values=pathlib.Path('devsecops/woodpecker-values.yaml');w=yaml.safe_load(values.read_text());w['agent']['env']['WOODPECKER_BACKEND_K8S_POD_NODE_SELECTOR']='kubernetes.io/hostname: lab-a1';values.write_text(yaml.safe_dump(w,sort_keys=False))
subprocess.run(['helm','upgrade','woodpecker','oci://ghcr.io/woodpecker-ci/helm/woodpecker','--version','3.7.5','-n','ci','-f',str(values),'--wait','--timeout','3m'],check=True)
print('PASS CI pods pinned to a1; CNPG tag+digest; limited ACME solver ingress')
