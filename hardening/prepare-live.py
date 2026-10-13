
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
from pathlib import Path
import yaml
root=Path('/data/k8s-lab')
# Narrow scans to applications, never SOC workloads.
p=root/'audits/trivy-operator/values.yaml'
d=yaml.safe_load(p.read_text());d['targetNamespaces']='demo,dev,staging,prod';p.write_text(yaml.safe_dump(d,sort_keys=False))
p=root/'audits/run.sh';s=p.read_text();s=s.replace('kubectl get policyreports -A -o json >"$out/kyverno-reports.json"','if kubectl api-resources --api-group=wgpolicyk8s.io -o name | python3 -c \'import sys;sys.exit(0 if "policyreports.wgpolicyk8s.io" in sys.stdin.read().split() else 1)\'; then\n kubectl get policyreports -A -o json >"$out/kyverno-reports.json"\nelse\n printf \'{"apiVersion":"v1","kind":"List","items":[],"collectionNote":"Kyverno not installed at baseline"}\\n\' >"$out/kyverno-reports.json"\nfi');p.write_text(s)
# Preserve prepared checks, but positively scope Enforce policies.
apps=['demo','dev','staging','prod','scen-*']
for p in (root/'hardening/kyverno/policies').glob('*.yaml'):
 d=yaml.safe_load(p.read_text());name=d['metadata']['name']
 if name=='lab-prod-signatures':continue
 for r in d['spec']['rules']:
  if name=='lab-image-registries':
   r['match']['any'][0]['resources'].pop('namespaces',None)
  else:
   for m in r['match']['any']:m['resources']['namespaces']=apps
 p.write_text(yaml.safe_dump(d,sort_keys=False))
# Never create or enforce PSS/NetworkPolicies in SOC namespaces.
p=root/'hardening/pss/namespaces.yaml';docs=list(yaml.safe_load_all(p.read_text()));docs=[d for d in docs if d['metadata']['name'] in apps];p.write_text(yaml.safe_dump_all(docs,sort_keys=False))
p=root/'hardening/netpol/policies.yaml';docs=list(yaml.safe_load_all(p.read_text()));docs=[d for d in docs if d['metadata']['namespace'] in apps]
for d in docs:
 if d['metadata']['name']=='allow-traefik' and d['metadata']['namespace']=='demo':d['spec']['podSelector']={'matchLabels':{'app':'demo'}}
p.write_text(yaml.safe_dump_all(docs,sort_keys=False))
# Quotas need capacity for parallel P6 and one scan job, but stay bounded.
quotas=[]
for ns in apps[:4]:
 quotas += [{'apiVersion':'v1','kind':'ResourceQuota','metadata':{'name':'workload-budget','namespace':ns},'spec':{'hard':{'requests.cpu':'4','requests.memory':'4Gi','limits.cpu':'8','limits.memory':'8Gi','pods':'30','persistentvolumeclaims':'10'}}}, {'apiVersion':'v1','kind':'LimitRange','metadata':{'name':'workload-budget','namespace':ns},'spec':{'limits':[{'type':'Container','max':{'cpu':'2','memory':'2Gi'},'min':{'cpu':'5m','memory':'8Mi'}}]}}]
# No default requests/limits: negative admission proof must not be silently defaulted.
(root/'hardening/pss/budgets.yaml').write_text(yaml.safe_dump_all(quotas,sort_keys=False))
p=root/'hardening/pss/install.sh';p.write_text('''#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
source "$ROOT/infra/k3s/env.sh"
kubectl apply -f "$ROOT/hardening/pss/namespaces.yaml"
kubectl apply -f "$ROOT/hardening/pss/budgets.yaml"
# Required node-facing components; Audit/Warn only otherwise, no SOC restriction.
for ns in kube-system longhorn-system soc-sensors falco audits; do
 kubectl label namespace "$ns" pod-security.kubernetes.io/enforce=privileged pod-security.kubernetes.io/enforce-version=v1.36 pod-security.kubernetes.io/audit=restricted pod-security.kubernetes.io/audit-version=v1.36 --overwrite
done
''')
p=root/'hardening/netpol/test.sh';s=p.read_text().replace('dev staging prod demo scenario-s1 scenario-s2 scenario-target scenario-s3 scenario-s4 scenario-s5','dev staging prod demo');p.write_text(s)
print('Prepared scripts narrowed to owned application namespaces; BEFORE audits remain first.')
