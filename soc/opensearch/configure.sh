#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
export LC_ALL=C
ROOT=/data/k8s-lab
export PATH="$ROOT/bin:$PATH"
export KUBECONFIG="$ROOT/.secrets/kubeconfig"
cd "$ROOT"
[[ -s "$KUBECONFIG" ]] || { printf '%s\n' 'Missing lab kubeconfig; install only after cluster creation.' >&2; exit 1; }
umask 077
kubectl -n opensearch get secret soc-http-cert -o jsonpath='{.data.ca\.crt}' | base64 -d > .secrets/opensearch-ca.crt
[[ -s .secrets/opensearch-ca.crt ]]
PORT="${SOC_OS_LOCAL_PORT:-19200}"
kubectl -n opensearch port-forward --address 127.0.0.1 svc/soc "$PORT:9200" > .secrets/opensearch-portforward.log 2>&1 &
PF_PID=$!
trap 'kill "$PF_PID" 2>/dev/null || true; wait "$PF_PID" 2>/dev/null || true' EXIT
export SOC_OS_URL="https://127.0.0.1:$PORT"
python3 soc/opensearch/configure.py
