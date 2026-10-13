#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
export KUBECONFIG=${KUBECONFIG:-/data/k8s-lab/.secrets/kubeconfig}
export PATH="$ROOT/bin:$PATH"
cd "$ROOT"
[[ "${LAB_TRIGGER:-}" == 1 ]] || { printf 'Set LAB_TRIGGER=1 to authorize safe lab triggers\n' >&2; exit 2; }
# Refuse unknown cluster endpoints even if a different kubeconfig is injected.
SERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
python3 - "$SERVER" <<'PY'
import urllib.parse,ipaddress,sys
h=urllib.parse.urlsplit(sys.argv[1]).hostname
assert h in ['127.0.0.1','localhost'] or (ipaddress.ip_address(h) in ipaddress.ip_network('192.168.150.0/24')), 'Not a lab API endpoint'
PY
kubectl create namespace soc-detection --dry-run=client -o yaml | kubectl apply -f - >/dev/null
