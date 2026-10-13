#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=/data/k8s-lab
source "$ROOT/infra/k3s/env.sh"
cd "$ROOT"
: "${LAB_TRIGGER:?Set LAB_TRIGGER=1}"
[[ "$LAB_TRIGGER" == 1 ]]
mkdir -p evidence/p4
export INTEL_PROOF_STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '%s\n' "$INTEL_PROOF_STARTED" >evidence/p4/intel-proof-start.txt
cleanup() {
 code=$?
 if (( code != 0 )); then kubectl -n kafka logs intel-kafka-acceptance || true; fi
 kubectl -n kafka delete pod intel-kafka-acceptance --ignore-not-found --wait=false >/dev/null || true
 kubectl -n kafka delete configmap intel-kafka-acceptance --ignore-not-found >/dev/null || true
}
trap cleanup EXIT
kubectl -n kafka delete pod intel-kafka-acceptance --ignore-not-found --wait=true >/dev/null
kubectl -n kafka create configmap intel-kafka-acceptance --from-file=kafka-consume.sh=soc/kafka/client-intel-proof.sh --dry-run=client -o yaml | kubectl apply -f -
python3 - <<'PY' | kubectl apply -f -
from pathlib import Path
import yaml,json
pod=yaml.safe_load(Path('soc/falco/kafka-acceptance-pod.yaml').read_text())
pod['metadata']['name']='intel-kafka-acceptance'
c=pod['spec']['containers'][0]
c['env']=[e for e in c['env'] if e['name']!='FALCO_PROOF']
for v in pod['spec']['volumes']:
 if v['name']=='scripts':v['configMap']['name']='intel-kafka-acceptance'
print(json.dumps(pod))
PY
kubectl -n kafka wait pod/intel-kafka-acceptance --for=condition=Ready --timeout=180s
bash soc/detection/triggers/intel-hit.sh
kubectl -n kafka wait pod/intel-kafka-acceptance --for=jsonpath='{.status.phase}'=Succeeded --timeout=120s
kubectl -n kafka logs intel-kafka-acceptance | tee evidence/p4/intel-kafka-proof.txt
python3 soc/misp/test-hops.py
