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
[[ $(kubectl get ns demo -o jsonpath='{.metadata.labels.pod-security\.kubernetes\.io/enforce}') == restricted ]]
result=$(mktemp "$ROOT/evidence/p5-prep/pss-reject.XXXXXX")
trap 'rm -f "$result"' EXIT
if kubectl create --dry-run=server -f "$ROOT/hardening/pss/privileged-negative.yaml" >"$result" 2>&1; then
  printf 'FAIL: privileged pod was admitted\n' >&2; exit 1
fi
if ! grep -q 'violates PodSecurity' "$result"; then cat "$result" >&2; exit 1; fi
cat "$result"
printf 'PASS: PSS restricted rejects privileged pod\n'
