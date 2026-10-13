#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import sys,json,re
allowed=['fatal','panic','failed','error','shutdown','shutting down','stopped','stopping','terminated','exit','leader','quorum']
for line in sys.stdin:
 try:d=json.loads(line);m=d.get('MESSAGE','')
 except (ValueError,TypeError):continue
 if not isinstance(m,str):continue
 lower=m.lower()
 if any(x in lower for x in ['token','secret','password','private key','authorization','bearer']):continue
 if not any(x in lower for x in allowed):continue
 # Reject opaque credential-like strings, even if a message happens to contain them.
 if re.search(r'[A-Za-z0-9_+/=-]{70,}',m):continue
 print(m[:1400])
