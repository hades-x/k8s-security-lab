
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
from pathlib import Path
import yaml,os
root=Path('/data/k8s-lab')
p=root/'.secrets/p5-kubeconfig';d=yaml.safe_load((root/'.secrets/kubeconfig').read_text())
for c in d['clusters']:c['cluster']['server']='https://192.168.150.13:6443'
p.write_text(yaml.safe_dump(d));p.chmod(0o600)
# Retain a caller's explicit kubeconfig after sourcing the standard lab env.
for f in ['hardening/pss/install.sh','tests/phase-p5-hardening.sh']:
 p=root/f;s=p.read_text().replace('source "$ROOT/infra/k3s/env.sh"','saved_kubeconfig=${KUBECONFIG:-}\nsource "$ROOT/infra/k3s/env.sh"\n[[ -z $saved_kubeconfig ]] || export KUBECONFIG=$saved_kubeconfig');p.write_text(s)
print('Private temporary P5 client config uses server s3 directly; shared kubeconfig unchanged.')
