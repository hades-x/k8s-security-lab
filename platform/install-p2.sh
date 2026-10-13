#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source /data/k8s-lab/infra/k3s/env.sh
cd "$ROOT"
test -f state/ready-p1
platform/budget.sh
platform/ingress/install.sh
platform/storage/install.sh
platform/argocd/install.sh
platform/forgejo/install.sh
python3 platform/forgejo/seed.py
kubectl apply -f platform/argocd/application.yaml
kubectl create namespace demo --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f platform/ingress/gateway.yaml
