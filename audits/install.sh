#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export PATH="$ROOT/bin:$PATH"
export KUBECONFIG="${KUBECONFIG:-$ROOT/.secrets/kubeconfig}"
export LC_ALL=C
kubectl create namespace audits --dry-run=client -o yaml | kubectl apply -f -
kubectl label ns audits pod-security.kubernetes.io/enforce=privileged --overwrite
helm upgrade --install trivy-operator "$ROOT/evidence/p5-prep/trivy-operator-0.37.0.tgz" --namespace trivy-system --create-namespace -f "$ROOT/audits/trivy-operator/values.yaml" --wait --timeout 5m
kubectl apply -f "$ROOT/audits/trivy-operator/resourcequota.yaml"
kubectl get deployment -n trivy-system
