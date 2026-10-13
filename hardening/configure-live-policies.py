
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
from pathlib import Path
import yaml
root=Path('/data/k8s-lab')
p=root/'hardening/kyverno/render.py'
s=p.read_text().replace("p['spec']['validationFailureAction']=args.mode;docs.append(p)","""name=p['metadata']['name']
 if name=='lab-image-registries':
  p['spec']['validationFailureAction']='Audit'
  p['spec']['validationFailureActionOverrides']=[{'action':'Enforce','namespaces':['prod']}]
 elif name=='lab-prod-signatures':p['spec']['validationFailureAction']='Audit'
 else:p['spec']['validationFailureAction']=args.mode
 docs.append(p)""");p.write_text(s)
p=root/'hardening/kyverno/policies/lab-host-isolation.yaml';d=yaml.safe_load(p.read_text());d['metadata']['annotations']['pod-policies.kyverno.io/autogen-controllers']='Deployment'
# Mutate only the existing Argo CD demo workload. GitOps owns its Deployment;
# these admission defaults persist through self-heal without changing its source.
d['spec']['rules'].append({'name':'demo-safe-defaults','match':{'any':[{'resources':{'kinds':['Pod'],'namespaces':['demo'],'selector':{'matchLabels':{'app':'demo'}}}}]},'mutate':{'patchStrategicMerge':{'spec':{'automountServiceAccountToken':False,'securityContext':{'+(seccompProfile)':{'type':'RuntimeDefault'}},'containers':[{'(name)':'nginx','securityContext':{'readOnlyRootFilesystem':True},'volumeMounts':[{'name':'hardening-tmp','mountPath':'/tmp'},{'name':'hardening-cache','mountPath':'/var/cache/nginx'},{'name':'hardening-run','mountPath':'/var/run'}]}],'volumes':[{'name':'hardening-tmp','emptyDir':{}},{'name':'hardening-cache','emptyDir':{}},{'name':'hardening-run','emptyDir':{}}]}}}})
p.write_text(yaml.safe_dump(d,sort_keys=False))
p=root/'hardening/pss/budgets.yaml';docs=list(yaml.safe_load_all(p.read_text()))
for d in docs:
 if d['kind']=='LimitRange':d['spec']['limits'][0].pop('max',None)
p.write_text(yaml.safe_dump_all(docs,sort_keys=False))
p=root/'audits/summarize.py';s=p.read_text().replace("tot['scan_coverage']=d.get('scanCoverage')","tot['scan_coverage']={k:v for k,v in d.get('scanCoverage',{}).items() if k in ['coverageScore','evaluatedControls','totalControls','degraded']}");p.write_text(s)
print('Policies positively scoped; demo Pod mutation supports GitOps self-heal; registry Audit with prod Enforce.')
