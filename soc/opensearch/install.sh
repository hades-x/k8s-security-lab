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
source soc/opensearch/VERSIONS
cache_chart() {
  local target="$1"
  mkdir -p "$ROOT/bin/p4-prep-a"
  if [[ ! -s "$target" ]]; then curl -fsSL --retry 3 "$CHART_URL" -o "$target"; fi
  printf '%s  %s\n' "$CHART_SHA256" "$target" | sha256sum --check --status
}
soc/opensearch/generate-secrets.sh
kubectl create namespace opensearch --dry-run=client -o yaml | kubectl apply -f -
for item in 'admin:admin:soc-admin-credentials' 'dashboards:kibanaserver:soc-dashboards-credentials' 'soc-indexer:soc-indexer:soc-indexer-credentials' 'soc-analyst:soc-analyst:soc-analyst-credentials'; do
 IFS=: read -r file user secret <<< "$item"
 kubectl -n opensearch create secret generic "$secret" --from-literal=username="$user" --from-file=password="$ROOT/.secrets/opensearch-$file.password" --dry-run=client -o yaml | kubectl apply -f -
done
cache_chart "$ROOT/bin/p4-prep-a/operator-3.0.14.tgz"
helm upgrade --install soc-opensearch-operator "$ROOT/bin/p4-prep-a/operator-3.0.14.tgz" -n opensearch -f soc/opensearch/values.yaml --wait --timeout 10m
kubectl wait --for=condition=Established crd/opensearchclusters.opensearch.org --timeout=120s
kubectl apply -f soc/opensearch/cluster.yaml -f soc/opensearch/ingress.yaml
# The CR uses status.phase (RUNNING), not a universally available Ready condition.
for ((i=0;i<180;i++)); do
 [[ "$(kubectl -n opensearch get opensearchcluster soc -o jsonpath='{.status.phase}')" == RUNNING ]] && break
 sleep 5
done
[[ "$(kubectl -n opensearch get opensearchcluster soc -o jsonpath='{.status.phase}')" == RUNNING ]] || { printf '%s\n' 'OpenSearch did not become RUNNING within 15m' >&2; exit 1; }
# RUNNING is a reconciliation phase, not proof that child resources exist yet.
wait_resource() {
 local target="$1"
 for ((i=0;i<180;i++)); do
  kubectl -n opensearch get "$target" >/dev/null 2>&1 && return 0
  sleep 5
 done
 printf 'Timed out waiting for managed resource %s\n' "$target" >&2
 return 1
}
wait_resource statefulset/soc-nodes
# The operator deliberately uses OnDelete, for which rollout status is unsupported.
kubectl -n opensearch wait statefulset/soc-nodes --for=jsonpath='{.status.readyReplicas}'=3 --timeout=10m
wait_resource deployment/soc-dashboards
kubectl -n opensearch rollout status deployment/soc-dashboards --timeout=10m
soc/opensearch/configure.sh
soc/opensearch/test.sh
