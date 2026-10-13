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
# Kafka and OpenSearch installers must already have completed.
kubectl -n kafka wait kafka/soc --for=condition=Ready --timeout=2m
[[ -s .secrets/opensearch-soc-indexer.password ]] || { printf '%s\n' 'Missing generated indexer password' >&2; exit 1; }
umask 077
kubectl -n opensearch get secret soc-http-cert -o jsonpath='{.data.ca\.crt}' | base64 -d > .secrets/opensearch-ca.crt
kubectl -n kafka create secret generic soc-opensearch-ca --from-file=ca.crt=.secrets/opensearch-ca.crt --dry-run=client -o yaml | kubectl apply -f -
kubectl -n kafka create secret generic soc-opensearch-indexer --from-literal=username=soc-indexer --from-file=password=.secrets/opensearch-soc-indexer.password --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f soc/pipeline/manifests.yaml
kubectl -n kafka rollout restart daemonset/vector-zeek daemonset/vector-audit deployment/vector-indexer
for ds in vector-zeek vector-audit; do kubectl -n kafka rollout status "daemonset/$ds" --timeout=5m; done
kubectl -n kafka rollout status deployment/vector-indexer --timeout=5m
soc/pipeline/test.sh
