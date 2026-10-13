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
kubectl -n falco rollout status daemonset/falco --timeout=300s
export LAB_TRIGGER=1
# Prepare the unprivileged helper before snapshotting offsets; no startup delay can lose the proof.
bash soc/detection/triggers/audit-exec.sh
export FALCO_PROOF=K8S_LAB_FALCO_$(date +%s)_$RANDOM
mkdir -p evidence/p4
printf '%s\n' "$FALCO_PROOF" >evidence/p4/falco-proof-marker.txt
kubectl -n kafka create configmap falco-kafka-acceptance --from-file=soc/falco/kafka-consume.sh --dry-run=client -o yaml | kubectl apply -f -
kubectl -n kafka delete pod falco-kafka-acceptance --ignore-not-found --wait=true >/dev/null
cleanup() {
 code=$?
 if (( code != 0 )); then
  kubectl -n kafka get pod falco-kafka-acceptance -o json | python3 -c 'import json,sys;d=json.load(sys.stdin);print("Failed proof pod phase:",d["status"]["phase"]);print("Container states:",[(c["name"],c.get("state"),c.get("lastState")) for c in d["status"].get("containerStatuses",[])])' || true
  kubectl -n kafka logs falco-kafka-acceptance || true
 fi
 kubectl -n kafka delete pod falco-kafka-acceptance --ignore-not-found >/dev/null || true
}
trap cleanup EXIT
# Render a unique marker into this one acceptance pod, never into a tracked credential file.
python3 - "$FALCO_PROOF" <<'PY' | kubectl apply -f -
from pathlib import Path
import sys
print(Path('soc/falco/kafka-acceptance-pod.yaml').read_text().replace('REPLACED_BY_TEST_SCRIPT',sys.argv[1]))
PY
kubectl -n kafka wait --for=condition=Ready pod/falco-kafka-acceptance --timeout=120s
bash soc/detection/triggers/falco-shell.sh
kubectl -n kafka wait --for=jsonpath='{.status.phase}'=Succeeded pod/falco-kafka-acceptance --timeout=180s
kubectl -n kafka logs falco-kafka-acceptance
