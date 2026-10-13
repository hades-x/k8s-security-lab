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
source soc/kafka/VERSIONS
cache_chart() {
  local target="$1"
  mkdir -p "$ROOT/bin/p4-prep-a"
  if [[ ! -s "$target" ]]; then curl -fsSL --retry 3 "$CHART_URL" -o "$target"; fi
  printf '%s  %s\n' "$CHART_SHA256" "$target" | sha256sum --check --status
}
cache_chart "$ROOT/bin/p4-prep-a/strimzi-1.3.0.tgz"
helm upgrade --install strimzi "$ROOT/bin/p4-prep-a/strimzi-1.3.0.tgz" -n kafka --create-namespace -f soc/kafka/values.yaml --wait --timeout 10m
for crd in kafkas kafkanodepools kafkatopics kafkausers; do kubectl wait --for=condition=Established "crd/$crd.kafka.strimzi.io" --timeout=120s; done
kubectl apply -f soc/kafka/cluster.yaml
kubectl wait -n kafka kafka/soc --for=condition=Ready --timeout=20m
kubectl apply -f soc/kafka/topics.yaml -f soc/kafka/users.yaml
kubectl wait -n kafka kafkatopic --all --for=condition=Ready --timeout=5m
kubectl wait -n kafka kafkauser --all --for=condition=Ready --timeout=5m
soc/kafka/test.sh
