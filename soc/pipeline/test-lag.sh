#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# Controlled drain benchmark. Restore every producer/replica on every exit.
set -euo pipefail
ROOT=/data/k8s-lab
source "$ROOT/infra/k3s/env.sh"
cd "$ROOT"
NORMAL=$(kubectl -n soc-traffic get deployment normal-traffic -o jsonpath='{.spec.replicas}')
BEACON=$(kubectl -n soc-traffic get deployment beacon-traffic -o jsonpath='{.spec.replicas}')
SIDEKICK=$(kubectl -n falco get deployment falcosidekick -o jsonpath='{.spec.replicas}')
export ZEEK_SELECTOR=$(kubectl -n kafka get ds vector-zeek -o json | python3 -c 'import json,sys;print(json.dumps(json.load(sys.stdin)["spec"]["template"]["spec"].get("nodeSelector",{})))')
export AUDIT_SELECTOR=$(kubectl -n kafka get ds vector-audit -o json | python3 -c 'import json,sys;print(json.dumps(json.load(sys.stdin)["spec"]["template"]["spec"].get("nodeSelector",{})))')
restore_shippers() {
 python3 - <<'PY'
import os,json,subprocess
for ds,key in [('vector-zeek','ZEEK_SELECTOR'),('vector-audit','AUDIT_SELECTOR')]:
 selector=json.loads(os.environ[key]);selector['soc.lab/lag-quiesced']=None
 patch={'spec':{'template':{'spec':{'nodeSelector':selector}}}}
 subprocess.run(['kubectl','-n','kafka','patch','ds',ds,'--type=merge','--patch-file=/dev/stdin'],input=json.dumps(patch).encode(),check=True)
PY
}
cleanup() {
 code=$?
 trap - EXIT
 kubectl -n kafka delete pod soc-kafka-lag --ignore-not-found --wait=false >/dev/null || true
 kubectl -n kafka delete configmap soc-kafka-lag --ignore-not-found >/dev/null || true
 restored=1
 kubectl -n falco scale deployment/falcosidekick --replicas="$SIDEKICK" || restored=0
 restore_shippers || restored=0
 kubectl -n falco rollout status deployment/falcosidekick --timeout=180s || restored=0
 kubectl -n kafka rollout status ds/vector-zeek --timeout=300s || restored=0
 kubectl -n kafka rollout status ds/vector-audit --timeout=300s || restored=0
 kubectl -n soc-traffic scale deployment/normal-traffic --replicas="$NORMAL" || restored=0
 kubectl -n soc-traffic scale deployment/beacon-traffic --replicas="$BEACON" || restored=0
 kubectl -n soc-traffic rollout status deployment/normal-traffic --timeout=180s || restored=0
 kubectl -n soc-traffic rollout status deployment/beacon-traffic --timeout=180s || restored=0
 [[ $(kubectl -n soc-traffic get deployment normal-traffic -o jsonpath='{.spec.replicas}') == "$NORMAL" ]] || restored=0
 [[ $(kubectl -n soc-traffic get deployment beacon-traffic -o jsonpath='{.spec.replicas}') == "$BEACON" ]] || restored=0
 [[ $(kubectl -n falco get deployment falcosidekick -o jsonpath='{.spec.replicas}') == "$SIDEKICK" ]] || restored=0
 if (( restored == 0 )); then printf 'FAIL restoring SOC producers\n' >&2; exit 1; fi
 printf 'PASS restored Zeek/audit shippers, sidekick=%s, generators normal=%s beacon=%s\n' "$SIDEKICK" "$NORMAL" "$BEACON"
 exit "$code"
}
trap cleanup EXIT
printf 'Drain benchmark: generators-only pause did not drain the continuous audit/Falco traffic. Temporarily quiescing all Kafka producers; sensors continue writing host logs.\n'
kubectl -n soc-traffic scale deployment/normal-traffic deployment/beacon-traffic --replicas=0
kubectl -n soc-traffic wait --for=delete pod -l app=normal-traffic --timeout=120s
kubectl -n soc-traffic wait --for=delete pod -l app=beacon-traffic --timeout=120s
# This selector changes only these two owned DaemonSets, never node labels.
kubectl get nodes -l soc.lab/lag-quiesced=true -o json | python3 -c 'import json,sys;assert not json.load(sys.stdin)["items"]'
for ds in vector-zeek vector-audit; do
 kubectl -n kafka patch ds "$ds" --type=merge -p '{"spec":{"template":{"spec":{"nodeSelector":{"soc.lab/lag-quiesced":"true"}}}}}'
done
kubectl -n falco scale deployment/falcosidekick --replicas=0
kubectl -n kafka wait --for=delete pod -l app=vector-zeek --timeout=180s
kubectl -n kafka wait --for=delete pod -l app=vector-audit --timeout=180s
kubectl -n falco wait --for=delete pod -l app.kubernetes.io/name=falcosidekick --timeout=180s
kubectl -n kafka delete pod soc-kafka-lag --ignore-not-found --wait=true >/dev/null
kubectl -n kafka create configmap soc-kafka-lag --from-file=soc/kafka/client-lag.sh --dry-run=client -o yaml | kubectl apply -f -
python3 - <<'PY' | kubectl apply -f -
from pathlib import Path
import yaml,json
pod=yaml.safe_load(Path('soc/kafka/client-pod.yaml').read_text().replace('soc-kafka-proof','soc-kafka-lag'))
pod['spec']['containers'][0]['command']=['bash','/proof/client-lag.sh']
print(json.dumps(pod))
PY
# Pod lifecycle observation avoids long-lived exec streams through the API VIP.
phase=''
for ((i=0;i<210;i++)); do
 phase=$(kubectl -n kafka get pod soc-kafka-lag -o jsonpath='{.status.phase}' 2>/dev/null || true)
 [[ "$phase" == Succeeded || "$phase" == Failed ]] && break
 sleep 2
done
kubectl -n kafka logs soc-kafka-lag | tee evidence/p4/drain-proof.txt
[[ "$phase" == Succeeded ]] || { printf 'FAIL lag proof pod phase=%s\n' "$phase" >&2; exit 1; }
