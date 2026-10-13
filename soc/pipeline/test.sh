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
for ds in vector-zeek vector-audit; do
 kubectl -n kafka get ds "$ds" -o json | python3 -c 'import json,sys; d=json.load(sys.stdin)["status"]; assert d["desiredNumberScheduled"]>0; assert d["numberReady"]==d["desiredNumberScheduled"]; print("PASS daemonset desired == ready ==",d["numberReady"])'
done
kubectl -n kafka get deployment vector-indexer -o json | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["spec"]["replicas"]==1; assert d["status"].get("readyReplicas",0)==1; print("PASS indexer 1/1 Ready")'
kubectl -n kafka rollout status deployment/vector-indexer --timeout=2m
