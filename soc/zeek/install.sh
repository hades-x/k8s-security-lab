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
kubectl apply -f soc/zeek/manifests.yaml --dry-run=client -o yaml >/dev/null
kubectl apply -f <(printf 'apiVersion: v1\nkind: Namespace\nmetadata:\n  name: soc-sensors\n  labels:\n    pod-security.kubernetes.io/enforce: privileged\n')
kubectl -n soc-sensors create configmap zeek-scripts --from-file=soc/zeek/scripts/ --from-file=soc/zeek/merge-logs.py --dry-run=client -o yaml | kubectl apply -f -
if ! kubectl -n soc-sensors get configmap zeek-intel >/dev/null 2>&1; then
 kubectl -n soc-sensors create configmap zeek-intel --from-file=misp.intel=soc/zeek/intel-empty.tsv --dry-run=client -o yaml | kubectl apply -f -
fi
# Render the configurable NIC before applying: avoid resetting it on subsequent installs.
NODE_INTERFACE=${NODE_INTERFACE:-eth0}
[[ "$NODE_INTERFACE" =~ ^[a-zA-Z0-9_.:-]+$ ]] || exit 2
python3 - "$NODE_INTERFACE" <<'PY' | kubectl apply -f -
import sys
from pathlib import Path
print(Path('soc/zeek/manifests.yaml').read_text().replace('value: enp1s0', 'value: '+sys.argv[1]))
PY
kubectl -n soc-sensors rollout status ds/zeek --timeout=300s
