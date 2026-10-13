#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source /data/k8s-lab/infra/k3s/env.sh
for i in {1..120}; do
 state=$(kubectl -n argocd get application lab-demo -o jsonpath='{.status.sync.status}/{.status.health.status}')
 [[ $state == Synced/Healthy ]] && { echo "PASS: Argo CD lab-demo $state"; exit 0; }
 sleep 3
done
kubectl -n argocd get application lab-demo -o yaml
exit 1
