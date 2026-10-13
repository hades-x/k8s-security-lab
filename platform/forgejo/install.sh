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
kubectl create namespace forgejo --dry-run=client -o yaml | kubectl apply -f -
if [[ ! -f .secrets/forgejo-admin-password ]]; then (umask 077; openssl rand -hex 24 | tr -d '\n' >.secrets/forgejo-admin-password); fi
chmod 600 .secrets/forgejo-admin-password
# Secrets do not enter command args or printed output.
kubectl -n forgejo create secret generic forgejo-admin --from-literal=username=lab-admin --from-file=password=.secrets/forgejo-admin-password --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install forgejo oci://code.forgejo.org/forgejo-helm/forgejo --version 17.2.0 -n forgejo -f platform/forgejo/values.yaml --wait --timeout 10m
