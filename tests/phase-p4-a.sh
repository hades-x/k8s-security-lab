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
soc/kafka/test.sh
soc/opensearch/test.sh
soc/pipeline/test.sh
REPLICAS=$(kubectl -n kafka get deployment vector-indexer -o jsonpath='{.spec.replicas}')
cleanup() {
 kubectl -n kafka delete pod soc-kafka-proof --ignore-not-found --wait=false >/dev/null || true
 kubectl -n kafka delete configmap soc-kafka-proof --ignore-not-found >/dev/null || true
 kubectl -n kafka scale deployment/vector-indexer --replicas="$REPLICAS" >/dev/null || true
}
trap cleanup EXIT
# Avoid stealing partitions from the live indexer with the same least-privilege group.
kubectl -n kafka scale deployment/vector-indexer --replicas=0
kubectl -n kafka wait --for=delete pod -l app=vector-indexer --timeout=180s
kubectl -n kafka delete pod soc-kafka-proof --ignore-not-found --wait=true --timeout=120s
kubectl -n kafka create configmap soc-kafka-proof --from-file=client-proof.sh=soc/kafka/client-proof.sh --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f soc/kafka/client-pod.yaml
kubectl -n kafka wait pod/soc-kafka-proof --for=condition=Ready --timeout=180s
kubectl -n kafka exec soc-kafka-proof -- /bin/bash /proof/client-proof.sh
cleanup
trap - EXIT
kubectl -n kafka rollout status deployment/vector-indexer --timeout=5m
SOC_REQUIRE_DATA=1 soc/opensearch/test.sh
printf '%s\n' 'PASS P4-A deployed acceptance (requires replay/hits/audit/Falco data first)'
