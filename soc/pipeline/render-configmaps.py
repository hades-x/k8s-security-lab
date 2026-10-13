
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Explicitly sync standalone Vector configs into their ConfigMaps and hashes."""
from pathlib import Path
import yaml,hashlib
R=Path('/data/k8s-lab');p=R/'soc/pipeline/manifests.yaml'
docs=list(yaml.safe_load_all(p.read_text()))
for d in docs:
 name=d['metadata']['name'];cfg=R/('soc/pipeline/config/'+name+'.yaml')
 if d['kind']=='ConfigMap':d['data']['vector.yaml']=cfg.read_text()
 if d['kind'] in ['Deployment','DaemonSet']:d['spec']['template']['metadata']['annotations']['soc.lab/config-sha256']=hashlib.sha256(cfg.read_bytes()).hexdigest()
p.write_text(yaml.safe_dump_all(docs,sort_keys=False))
print('Synchronized Vector ConfigMaps and rollout hashes; no cluster contacted.')
