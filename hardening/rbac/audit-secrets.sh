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
out=${1:-$ROOT/evidence/p5/rbac}; mkdir -p "$out"
kubectl ${P5_API_SERVER:+--server="$P5_API_SERVER"} auth can-i --list >"$out/current-subject-can-i.txt"
kubectl ${P5_API_SERVER:+--server="$P5_API_SERVER"} get roles,rolebindings -A -o json >"$out/namespaced-rbac.json"
kubectl ${P5_API_SERVER:+--server="$P5_API_SERVER"} get clusterroles,clusterrolebindings -o json >"$out/cluster-rbac.json"
python3 "$ROOT/hardening/rbac/audit-secrets.py" "$out"
