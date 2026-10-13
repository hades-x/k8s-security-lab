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
args=(--mode "${MODE:-Audit}")
if [[ ${SIGNATURES:-false} == true ]]; then args+=(--signatures); fi
python3 "$ROOT/hardening/kyverno/render.py" "${args[@]}" | kubectl apply -f -
kubectl get clusterpolicies -o custom-columns=NAME:.metadata.name,MODE:.spec.validationFailureAction
