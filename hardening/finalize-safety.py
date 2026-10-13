
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
from pathlib import Path
import yaml
root=Path('/data/k8s-lab')
p=root/'hardening/kyverno/render.py';s=p.read_text();s=s.replace("p['spec']['rules'][0]['verifyImages'][0]['attestors'][0]['entries'][0]['keys']['publicKeys']=key","p['spec']['rules'][0]['verifyImages'][0]['attestors'][0]['entries'][0]['keys']['publicKeys']=key\n  p['spec']['rules'][0]['verifyImages'][0]['mutateDigest']=args.mode=='Enforce'");p.write_text(s)
p=root/'hardening/kyverno/policies/lab-image-registries.yaml';d=yaml.safe_load(p.read_text());d['spec']['failurePolicy']='Ignore';p.write_text(yaml.safe_dump(d,sort_keys=False))
# Quiescing an Audit-only global registry webhook must not block SOC workloads
# if the one admission replica is unavailable. App isolation policies remain Fail.
p=root/'tests/phase-p5-hardening.sh';s=p.read_text().replace('python3 -E "$ROOT/hardening/prove.py"','''kubectl get --raw=/readyz --request-timeout=15s
kubectl wait -n kyverno --for=condition=Available deployment/kyverno-admission-controller --timeout=60s
for policy in lab-host-isolation lab-resource-budget lab-image-tags lab-no-default-token; do
 mode=$(kubectl get clusterpolicy "$policy" -o jsonpath='{.spec.validationFailureAction}')
 [[ $mode == Enforce ]] || { printf 'FAIL: %s is %s, expected Enforce\\n' "$policy" "$mode"; exit 1; }
done
python3 -E "$ROOT/hardening/prove.py"''');p.write_text(s)
p=root/'hardening/pss/EXEMPTIONS.md';s=p.read_text();p.write_text('> Deployment status: the following is the intended scope; P5 demo labels/budgets remain pending control-plane recovery. See docs/hardening-report.md.\n\n'+s)
print('Added fail-fast live acceptance preflight; corrected Audit image-verification mutation compatibility and global Audit availability safety.')
