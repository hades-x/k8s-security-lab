#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# Shared lab-only runtime helpers. Sourcing this performs no network calls.
set -Eeuo pipefail
umask 077
export LC_ALL=C
ROOT=/data/k8s-lab
source "$ROOT/infra/k3s/env.sh"
export PATH="$ROOT/bin:$PATH"
export KUBECONFIG="$ROOT/.secrets/kubeconfig"
SECRET_DIR="$ROOT/.secrets/p3"
require_lab() {
  [[ "${P3_ALLOW_DEPLOY:-}" == "yes" ]] || { echo 'Set P3_ALLOW_DEPLOY=yes only when the disposable cluster is ready.' >&2; exit 2; }
  [[ -f "$KUBECONFIG" ]] || { echo 'Missing lab kubeconfig' >&2; exit 2; }
  local server
  server=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
  case "$server" in https://192.168.150.10:6443|https://192.168.150.11:6443|https://192.168.150.12:6443|https://192.168.150.13:6443) ;; *) echo "Refusing non-lab API endpoint" >&2; exit 2;; esac
}
ns() { kubectl create namespace "$1" --dry-run=client -o yaml | kubectl apply -f -; }
secret_files() { local namespace=$1 name=$2; shift 2; kubectl -n "$namespace" create secret generic "$name" "$@" --dry-run=client -o yaml | kubectl apply -f -; }
chart() {
  local key=$1 release=$2 namespace=$3 values=$4 package
  package=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))[sys.argv[2]]["package"])' "$ROOT/evidence/p3-prep/versions.json" "$key")
  [[ -f "$ROOT/$package" ]] || { echo "Missing cached pinned chart $package; run evidence/p3-prep/fetch-charts.py" >&2; exit 2; }
  python3 -c 'import json,hashlib,pathlib,sys;root=pathlib.Path("/data/k8s-lab");v=json.load(open(root/"evidence/p3-prep/versions.json"))[sys.argv[1]];assert hashlib.sha256((root/v["package"]).read_bytes()).hexdigest()==v["sha256"],"chart checksum mismatch"' "$key"
  helm upgrade --install "$release" "$ROOT/$package" -n "$namespace" -f "$values" --wait --timeout 10m
}
wait_deploy() { kubectl -n "$1" rollout status "deployment/$2" --timeout=600s; }
