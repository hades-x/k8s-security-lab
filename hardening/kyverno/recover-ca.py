#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
from pathlib import Path
import json,subprocess,yaml
root=Path('/data/k8s-lab')
cm=json.loads(subprocess.check_output(['kubectl','get','configmap','p6-lab-ca','-n','kyverno','-o','json']))
ca=cm['data']['root_ca.crt'];assert 'BEGIN CERTIFICATE' in ca
p=root/'hardening/kyverno/values.yaml';d=yaml.safe_load(p.read_text());d.setdefault('global',{}).setdefault('caCertificates',{})['data']=ca;p.write_text(yaml.safe_dump(d,sort_keys=False))
# Preserve both requested value files. Chart .data takes precedence over .volume
# and renders subPath: ca-certificates.crt in all controller volumeMounts.
cmd=['helm','upgrade','--install','kyverno',str(root/'evidence/p5-prep/kyverno-3.9.1.tgz'),'--namespace','kyverno','-f',str(root/'hardening/kyverno/values.yaml'),'-f',str(root/'devsecops/kyverno-registry-values.yaml'),'--wait','--timeout','5m']
with (root/'evidence/p5/kyverno-ca-recovery.log').open('w') as log:
 p=subprocess.run(cmd,stdout=log,stderr=log)
print('Kyverno upgrade with BOTH value files, exit='+str(p.returncode))
subprocess.run(['kubectl','get','deployments','-n','kyverno'])
raise SystemExit(p.returncode)
