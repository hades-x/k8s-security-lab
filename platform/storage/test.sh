#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source /data/k8s-lab/infra/k3s/env.sh
cd "$ROOT"
kubectl -n demo rollout status deployment/demo --timeout=300s
kubectl -n demo get pvc demo-data
stamp="persistence-proof-$(date +%s)"
kubectl -n demo exec deploy/demo -- sh -c 'printf "%s\n" "$1" > /data/proof.txt; sync' sh "$stamp"
old=$(kubectl -n demo get pods -l app=demo -o jsonpath='{.items[0].metadata.uid}')
kubectl -n demo delete pod -l app=demo --wait=true
kubectl -n demo rollout status deployment/demo --timeout=300s
new=$(kubectl -n demo get pods -l app=demo -o jsonpath='{.items[0].metadata.uid}')
[[ "$old" != "$new" ]]
actual=$(kubectl -n demo exec deploy/demo -- cat /data/proof.txt)
[[ "$actual" == "$stamp" ]]
printf 'PASS: Longhorn PVC persistence, old pod=%s new pod=%s value=%s
' "$old" "$new" "$actual"
kubectl -n longhorn-system get volumes.longhorn.io -o custom-columns=NAME:.metadata.name,STATE:.status.state,HEALTH:.status.robustness,REPLICAS:.spec.numberOfReplicas
