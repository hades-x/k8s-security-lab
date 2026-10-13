#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source /data/k8s-lab/infra/k3s/env.sh
curl -fsS --resolve forgejo.192.168.150.200.sslip.io:80:192.168.150.200 http://forgejo.192.168.150.200.sslip.io/api/healthz
curl -fsS --resolve forgejo.192.168.150.200.sslip.io:80:192.168.150.200 http://forgejo.192.168.150.200.sslip.io/api/v1/repos/lab/gitops | python3 -c 'import sys,json;r=json.load(sys.stdin);assert r["full_name"]=="lab/gitops";print("PASS: Forgejo repository "+r["full_name"])'
