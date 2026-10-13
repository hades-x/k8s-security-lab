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
sha256sum --check soc/falco/chart-checksums.sha256
kubectl apply -f soc/falco/namespace.yaml
# Reflect exact Strimzi secrets without printing or persisting their data.
for source in falcosidekick soc-cluster-ca-cert; do
 target=falcosidekick-kafka; [[ "$source" == soc-cluster-ca-cert ]] && target=soc-kafka-ca
 kubectl -n kafka get secret "$source" -o json | python3 -c 'import json,sys;d=json.load(sys.stdin);print(json.dumps({"apiVersion":"v1","kind":"Secret","metadata":{"name":sys.argv[1],"namespace":"falco"},"type":"Opaque","data":{sys.argv[2]:d["data"][sys.argv[2]]}}))' "$target" "$([[ "$source" == falcosidekick ]] && echo password || echo ca.crt)" | kubectl apply -f -
done
helm upgrade --install falcosidekick evidence/p4-prep-b/falcosidekick-0.14.0.tgz -n falco -f soc/falco/sidekick-values.yaml --wait --timeout=5m
helm upgrade --install falco evidence/p4-prep-b/falco-9.2.0.tgz -n falco -f soc/falco/values.yaml --wait --timeout=5m
# Secret updates are environment variables: force a restart, otherwise rotated SCRAM passwords stay stale.
kubectl -n falco rollout restart deployment/falcosidekick
kubectl -n falco rollout status deployment/falcosidekick --timeout=180s
kubectl -n falco get secret falcosidekick-kafka soc-kafka-ca -o name
