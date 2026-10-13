#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
export PATH="$ROOT/bin:$PATH"
export KUBECONFIG="${KUBECONFIG:-$ROOT/.secrets/kubeconfig}"
export LC_ALL=C
helm upgrade --install kyverno "$ROOT/evidence/p5-prep/kyverno-3.9.1.tgz" --namespace kyverno --create-namespace -f "$ROOT/hardening/kyverno/values.yaml" -f "$ROOT/devsecops/kyverno-registry-values.yaml" --wait --timeout 5m
kubectl get deployment -n kyverno
MODE=Audit "$ROOT/hardening/kyverno/apply-policies.sh"
