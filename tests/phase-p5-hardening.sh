#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
saved_kubeconfig=${KUBECONFIG:-}
source "$ROOT/infra/k3s/env.sh"
[[ -z $saved_kubeconfig ]] || export KUBECONFIG=$saved_kubeconfig
kubectl get --raw=/readyz --request-timeout=15s
mode=$(kubectl get ns demo -o jsonpath='{.metadata.labels.pod-security\.kubernetes\.io/enforce}')
[[ $mode == restricted ]] || { printf 'FAIL: demo PSS enforce=%s, expected restricted\n' "$mode"; exit 1; }
kubectl wait -n kyverno --for=condition=Available deployment/kyverno-admission-controller --timeout=60s
for policy in lab-host-isolation lab-resource-budget lab-image-tags lab-no-default-token; do
 mode=$(kubectl get clusterpolicy "$policy" -o jsonpath='{.spec.validationFailureAction}')
 [[ $mode == Enforce ]] || { printf 'FAIL: %s is %s, expected Enforce\n' "$policy" "$mode"; exit 1; }
done
python3 -E "$ROOT/hardening/prove.py"
"$ROOT/hardening/rbac/test.sh"
"$ROOT/hardening/netpol/test.sh"
