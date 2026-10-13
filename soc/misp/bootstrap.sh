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
kubectl -n misp port-forward service/misp 18080:8080 >.secrets/misp-port-forward.log 2>&1 &
PF=$!; trap 'kill "$PF" 2>/dev/null || true' EXIT
for i in {1..30}; do curl -fsS http://127.0.0.1:18080/users/login >/dev/null && break; sleep 1; done
python3 soc/misp/bootstrap.py
JOB=misp-intel-$(date +%s)
kubectl -n soc-sensors create job "$JOB" --from=cronjob/misp-intel-refresh
kubectl -n soc-sensors wait --for=condition=complete job/"$JOB" --timeout=180s
kubectl -n soc-sensors get configmap zeek-intel -o json | python3 -c 'import json,sys;d=json.load(sys.stdin);assert "ioc.evil-c2.lab.test" in d["data"]["misp.intel"];print("Intel ConfigMap verified")'
# Projected volumes refresh asynchronously; exporter cannot hot-swap a subPath.
sleep 90
kubectl -n soc-sensors rollout restart daemonset/zeek
kubectl -n soc-sensors rollout status daemonset/zeek --timeout=300s
