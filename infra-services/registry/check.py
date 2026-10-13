#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Allow ingress propagation delay without ever skipping TLS verification."""
import pathlib,requests,time
R=pathlib.Path('/data/k8s-lab');url='https://zot.192.168.150.200.sslip.io/v2/';root=str(R/'.secrets/pki/root_ca.crt')
pw=(R/'.secrets/p3/zot-password').read_text().strip()
for attempt in range(60):
 try:
  r=requests.get(url,verify=root,timeout=10);assert r.status_code==401
  r=requests.get(url,auth=('lab',pw),verify=root,timeout=10);assert r.status_code==200
  break
 except (requests.RequestException,AssertionError):
  if attempt==59:raise RuntimeError('Registry trusted-TLS/auth acceptance failed; transport details withheld') from None
  time.sleep(2)
print('PASS: zot TLS trusted; anonymous /v2/ denied; authenticated /v2/ succeeds; image roundtrip checked separately.')
