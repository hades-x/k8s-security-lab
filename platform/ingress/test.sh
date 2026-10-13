#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source /data/k8s-lab/infra/k3s/env.sh
[[ $(kubectl -n kube-system get svc traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}') == 192.168.150.200 ]]
kubectl -n kube-system get svc traefik -o wide
kubectl -n demo get gateway,httproute
curl -fsS --resolve gateway-demo.192.168.150.200.sslip.io:80:192.168.150.200 http://gateway-demo.192.168.150.200.sslip.io/ >/dev/null
