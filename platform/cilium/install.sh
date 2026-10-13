#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source /data/k8s-lab/infra/k3s/env.sh
cd "$ROOT"
helm repo add cilium https://helm.cilium.io
helm repo update cilium
if [[ ! -f platform/cilium/VERSIONS ]]; then helm search repo cilium/cilium -o json | python3 -c 'import sys,json;print(json.load(sys.stdin)[0]["version"])' >platform/cilium/VERSIONS; fi
version=$(cat platform/cilium/VERSIONS)
helm upgrade --install cilium cilium/cilium --version "$version" --namespace kube-system -f platform/cilium/values.yaml --wait --timeout 10m
cilium status --wait --wait-duration 5m
kubectl wait node --all --for=condition=Ready --timeout=300s
