#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Inspect audit structure without printing any event payload."""
import json
from collections import Counter
from pathlib import Path
counts=Counter();levels=Counter()
for line in Path('/var/lib/rancher/k3s/server/logs/audit.log').open():
 try:e=json.loads(line)
 except json.JSONDecodeError:continue
 ref=e.get('objectRef',{});resource=ref.get('resource');sub=ref.get('subresource')
 if resource in ('secrets','configmaps'):
  assert e.get('level')=='Metadata'
  assert 'requestObject' not in e and 'responseObject' not in e,'Sensitive object bodies found in audit event'
  counts[resource]+=1
 if resource=='pods' and sub in ('exec','attach'):
  assert e.get('level')=='RequestResponse'
  levels[sub]+=1
assert counts['secrets']>0
print('PASS: audit secrets/configmaps Metadata without request/response bodies; counts='+str(dict(counts)))
print('Audit exec/attach RequestResponse events='+str(dict(levels)))
