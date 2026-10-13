#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi

# PUBLIC_RUNTIME_DISABLED: reference implementation retained, not an approved runtime.
printf "%s\n" "BLOCKED: automation disabled pending UID/run ownership, exact snapshot ownership and fail-closed API adaptation; see tools/DEPENDENCIES.md" >&2
return 2 2>/dev/null || exit 2
set -euo pipefail
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MODULE=02-lifecycle; NS=ex-lifecycle
source "$DIR/../_lib/common.sh"
launch "$DIR/run.sh" 02
ARMED=0; WATCHDOG_PID=''; PROBE_PID=''
extra_cleanup() {
  local failed=0 state
  if [[ "$ARMED" == 1 ]]; then
    step 'Trap de sûreté : uncordon lab-a2'
    kubectl --request-timeout=8s uncordon lab-a2 || failed=1
    state=$(kubectl --request-timeout=8s get node lab-a2 -o jsonpath='{.spec.unschedulable}') || failed=1
    [[ "$state" == false || -z "$state" ]] || failed=1
    [[ $failed == 0 ]] && { ARMED=0; echo 'PASS trap: lab-a2 schedulable'; }
  fi
  if [[ -n "$WATCHDOG_PID" && "$ARMED" == 0 ]]; then kill "$WATCHDOG_PID" 2>/dev/null || true; wait "$WATCHDOG_PID" 2>/dev/null || true; fi
  if [[ -n "$PROBE_PID" ]]; then kill "$PROBE_PID" 2>/dev/null || true; wait "$PROBE_PID" 2>/dev/null || true; fi
  return "$failed"
}
init_module
step 'Deployment v1, deux replicas sur a2, maxUnavailable=0 / maxSurge=1'
[[ $(kubectl get node lab-a2 -o jsonpath='{.spec.unschedulable}') != true ]] || { echo 'FAIL a2 already cordoned, refusing to change foreign state'; exit 1; }
apply_manifest client-service.yaml
apply_manifest v1.yaml
k rollout status deployment/lifecycle --timeout=70s
k wait --for=condition=Ready pod/client --timeout=40s
k get deployment lifecycle -o jsonpath='{.spec.strategy.rollingUpdate}{"\n"}'
k exec client -- wget -T 3 -qO- http://lifecycle:8080/ | tee "$ROOT/evidence/exercices/02-v1.txt"
[[ $(k exec client -- wget -T 3 -qO- http://lifecycle:8080/) == v1 ]]

step 'Rolling update v2'
apply_manifest v2.yaml
k rollout status deployment/lifecycle --timeout=70s
[[ $(k exec client -- wget -T 3 -qO- http://lifecycle:8080/) == v2 ]]
k get pods -l app=lifecycle -o wide
echo 'PASS v1 -> v2 rolling update'

step 'v3 : readiness /unready = 404; observer sans interrompre v2'
PROBE_LOG="$ROOT/evidence/exercices/02-http-probe.txt"
k exec client -- sh -c 'i=0; failed=0; while [ "$i" -lt 75 ]; do i=$((i+1)); if body=$(wget -T 2 -qO- http://lifecycle:8080/); then printf "HTTP_SAMPLE %s OK %s\n" "$i" "$body"; else printf "HTTP_SAMPLE %s FAIL\n" "$i"; failed=1; fi; sleep 1; done; exit "$failed"' >"$PROBE_LOG" 2>&1 &
PROBE_PID=$!
apply_manifest v3.yaml
if k rollout status deployment/lifecycle --timeout=45s; then echo 'FAIL v3 unexpectedly Ready'; exit 1; fi
wait_field deployment/lifecycle '{.status.conditions[?(@.type=="Progressing")].reason}' ProgressDeadlineExceeded 15
k get deployment,replicaset,pod -o wide
k describe deployment lifecycle
for pod in $(k get pods -l app=lifecycle -o jsonpath='{.items[*].metadata.name}'); do diagnose "$pod"; done
[[ $(k get deployment lifecycle -o jsonpath='{.status.availableReplicas}') -ge 2 ]]
[[ $(k exec client -- wget -T 3 -qO- http://lifecycle:8080/) == v2 ]]
echo 'PASS failed v3 rollout: >=2 available replicas, v2 still served'
step 'Rollback explicite vers la révision précédente'
k rollout undo deployment/lifecycle
k rollout status deployment/lifecycle --timeout=70s
[[ $(k exec client -- wget -T 3 -qO- http://lifecycle:8080/) == v2 ]]
k rollout history deployment/lifecycle
wait "$PROBE_PID"; PROBE_PID=''
python3 - "$PROBE_LOG" <<'PY'
import sys
from pathlib import Path
lines=Path(sys.argv[1]).read_text().splitlines()
samples=[x for x in lines if x.startswith('HTTP_SAMPLE ')]
if len(samples)!=75 or any(' FAIL' in x or not x.endswith(' OK v2') for x in samples):
    raise SystemExit('FAIL availability sampling: incomplete/failure/unexpected version')
print(f'PASS HTTP availability sampled: {len(samples)} requests, 0 failures, all v2')
PY

echo 'PASS rollout undo: v2 restored'
step 'PDB minAvailable=2 : disruptionsAllowed doit valoir 0'
apply_manifest pdb.yaml
wait_field pdb/lifecycle '{.status.disruptionsAllowed}' 0 30
wait_field pdb/lifecycle '{.status.currentHealthy}' 2 30
k get pdb lifecycle -o wide
k describe pdb lifecycle
# Before a node-level command, verify its selector selects only owned pods.
kubectl get pods -A -l exercise=phase-f-lifecycle-server -o json | python3 -c 'import json,sys; d=json.load(sys.stdin); ns={p["metadata"]["namespace"] for p in d["items"]}; sys.exit(0 if ns=={"ex-lifecycle"} else "FAIL foreign pods selected")'
step 'Drain UNIQUEMENT dry-run=server, ciblé sur nos pods'
set +e
kubectl --request-timeout=15s drain lab-a2 --dry-run=server --pod-selector=exercise=phase-f-lifecycle-server --ignore-daemonsets --delete-emptydir-data --force --timeout=15s >"$ROOT/evidence/exercices/02-drain-dry-run.txt" 2>&1
drain_rc=$?
set -e
python3 - "$ROOT/evidence/exercices/02-drain-dry-run.txt" "$drain_rc" <<'PY'
from pathlib import Path
import sys
text=Path(sys.argv[1]).read_text(); print(text)
rc=int(sys.argv[2])
if rc != 0 and 'Cannot evict pod as it would violate' not in text:
    raise SystemExit('FAIL drain dry-run failed for a reason other than the intended PDB')
print(f'PASS drain dry-run observed: exit={rc}; PDB_block={"Cannot evict pod as it would violate" in text}')
PY
# Some kubectl drain dry-runs only enumerate would-evict operations. Prove the PDB
# via a separate admission request with DeleteOptions.dryRun=All, never real eviction.
pod=$(k get pods -l app=lifecycle -o jsonpath='{.items[0].metadata.name}')
step 'Preuve PDB complémentaire : POST Eviction avec dryRun=All'
set +e
response=$(printf '{"apiVersion":"policy/v1","kind":"Eviction","metadata":{"name":"%s","namespace":"ex-lifecycle"},"deleteOptions":{"dryRun":["All"]}}' "$pod" | kubectl --request-timeout=15s create --raw "/api/v1/namespaces/ex-lifecycle/pods/$pod/eviction?dryRun=All" -f - 2>&1)
rc=$?
set -e
printf '%s\n' "$response"
[[ $rc != 0 && "$response" == *disruption*budget* ]] || { echo 'FAIL dry-run eviction did not show a PDB rejection'; exit 1; }
k get pod "$pod"
echo 'PASS PDB: dry-run eviction rejected; pod still present'

step 'Cordon autorisé, cinq secondes; trap + garde indépendante à 20 s'
[[ $(kubectl get node lab-a2 -o jsonpath='{.spec.unschedulable}') != true ]] || { echo 'FAIL a2 became cordoned by another session'; exit 1; }
ARMED=1
CORDON_STARTED=$SECONDS
# Detached guard survives a timeout of this run; no host/VM configuration is changed.
setsid bash -c 'sleep 20; kubectl --request-timeout=5s uncordon lab-a2' 9>&- >"$ROOT/evidence/exercices/02-uncordon-watchdog.txt" 2>&1 < /dev/null &
WATCHDOG_PID=$!
timeout 8 kubectl --request-timeout=7s cordon lab-a2
[[ $(kubectl --request-timeout=5s get node lab-a2 -o jsonpath='{.spec.unschedulable}') == true ]]
sleep 5
extra_cleanup
cordon_window=$((SECONDS-CORDON_STARTED))
printf 'CORDON_WINDOW_SECONDS=%s\n' "$cordon_window"
[[ $cordon_window -le 30 ]] || { echo 'FAIL cordon window exceeded 30 s'; exit 1; }
kubectl get node lab-a2 -o custom-columns='NAME:.metadata.name,UNSCHEDULABLE:.spec.unschedulable'
echo 'PASS cordon/uncordon: node schedulable again; no real drain performed'
