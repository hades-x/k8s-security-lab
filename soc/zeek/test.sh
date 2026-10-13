#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
export KUBECONFIG=${KUBECONFIG:-/data/k8s-lab/.secrets/kubeconfig}
export PATH="$ROOT/bin:$PATH"
cd "$ROOT"
kubectl -n soc-sensors get ds zeek -o json | python3 -c 'import json,sys; s=json.load(sys.stdin)["status"]; assert s["desiredNumberScheduled"]==5 and s["numberReady"]==5, s'
while read -r pod; do
 kubectl -n soc-sensors exec "$pod" -c log-merger -- python3 -c 'from pathlib import Path; assert any(p.stat().st_size for p in Path("/var/log/zeek/current").glob("*.log"))'
done < <(kubectl -n soc-sensors get pods -l app=zeek -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')
