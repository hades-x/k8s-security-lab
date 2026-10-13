#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Bound all Helm-rendered containers, including init jobs and sidecars."""
import sys,yaml
for obj in yaml.safe_load_all(sys.stdin):
 if not obj: continue
 kind=obj.get('kind')
 if kind=='Pod': spec=obj.get('spec',{})
 elif kind in ('Deployment','StatefulSet','DaemonSet','Job','ReplicaSet'): spec=obj.get('spec',{}).get('template',{}).get('spec',{})
 elif kind=='CronJob': spec=obj.get('spec',{}).get('jobTemplate',{}).get('spec',{}).get('template',{}).get('spec',{})
 else: spec={}
 for c in spec.get('containers',[])+spec.get('initContainers',[]):
  r=c.setdefault('resources',{});q=r.setdefault('requests',{});l=r.setdefault('limits',{})
  q.setdefault('cpu','50m');q.setdefault('memory','64Mi');l.setdefault('cpu','1');l.setdefault('memory','512Mi')
 print('---');yaml.safe_dump(obj,sys.stdout,sort_keys=False)
