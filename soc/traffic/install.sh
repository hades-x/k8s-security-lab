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
kubectl apply -f <(printf 'apiVersion: v1\nkind: Namespace\nmetadata:\n  name: soc-traffic\n')
kubectl -n soc-traffic create configmap traffic-scripts --from-file=soc/traffic/live.py --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f soc/traffic/manifests.yaml
kubectl apply -f soc/traffic/replay-cronjob.yaml
for app in lab-web normal-traffic beacon-traffic; do kubectl -n soc-traffic rollout status deployment/"$app" --timeout=180s; done
