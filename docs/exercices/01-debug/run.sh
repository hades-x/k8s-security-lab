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
MODULE=01-debug; NS=ex-debug
source "$DIR/../_lib/common.sh"
launch "$DIR/run.sh" 01
init_module

step '1/4 : ImagePullBackOff, registre autorisé / tag inexistant'
apply_manifest image-bad.yaml
wait_field pod/image '{.status.containerStatuses[0].state.waiting.reason}' ImagePullBackOff 100
diagnose image
step 'Correction : image BusyBox 1.37.0 épinglée par digest'
k set image pod/image "main=$IMAGE"
k wait --for=condition=Ready pod/image --timeout=80s
k get pod image -o jsonpath='{.spec.containers[0].image}{"\n"}{.status.containerStatuses[0].imageID}{"\n"}'
k logs image
echo 'PASS ImagePullBackOff: corrected image; Ready=True'
k delete pod image --wait=true --timeout=30s

step '2/4 : CrashLoopBackOff, sortie volontaire 1'
apply_manifest crash-bad.yaml
# On this kubelet the waiting status is short-lived: a 2 s poll can miss it.
# Observe the API watch stream rather than pretending Error alone proves the field.
set +e
timeout 40 kubectl --request-timeout=45s -n "$NS" get pod crash --watch -o custom-columns='NAME:.metadata.name,WAITING:.status.containerStatuses[0].state.waiting.reason,TERMINATED:.status.containerStatuses[0].state.terminated.reason,RESTARTS:.status.containerStatuses[0].restartCount' >"$ROOT/evidence/exercices/01-crash-watch.txt" 2>&1
watch_rc=$?
set -e
[[ $watch_rc == 0 || $watch_rc == 124 ]] || { echo 'FAIL watch transport'; exit 1; }
python3 - "$ROOT/evidence/exercices/01-crash-watch.txt" <<'PY'
from pathlib import Path
import sys
text=Path(sys.argv[1]).read_text(); print(text)
if not any(len(row.split())>=2 and row.split()[1]=='CrashLoopBackOff' for row in text.splitlines()):
    raise SystemExit('FAIL CrashLoopBackOff not observed in API watch')
print('PASS API watch: waiting.reason=CrashLoopBackOff observed')
PY
wait_field pod/crash '{.status.containerStatuses[0].lastState.terminated.exitCode}' 1 5
diagnose crash
step 'Correction : remplacer exit 1 par un processus stable'
k delete pod crash --wait=true --timeout=30s
apply_manifest crash-fixed.yaml
k wait --for=condition=Ready pod/crash --timeout=60s
k logs crash
echo 'PASS CrashLoopBackOff: corrected command; Ready=True'
k delete pod crash --wait=true --timeout=30s

step '3/4 : Pending, requests impossibles (1000 CPU / 1 TiB)'
kubectl get nodes -o custom-columns='NAME:.metadata.name,CPU:.status.allocatable.cpu,MEMORY:.status.allocatable.memory'
apply_manifest pending-bad.yaml
wait_field pod/pending '{.status.conditions[?(@.type=="PodScheduled")].reason}' Unschedulable 40
diagnose pending
step 'Correction : requests 10m / 16Mi, limits 100m / 64Mi'
k delete pod pending --wait=true --timeout=30s
apply_manifest pending-fixed.yaml
k wait --for=condition=Ready pod/pending --timeout=60s
k logs pending
echo 'PASS Pending: right-sized requests; Ready=True'
k delete pod pending --wait=true --timeout=30s

step '4/4 : NetworkPolicy, valider la connexion avant de la bloquer'
apply_manifest network.yaml
k wait --for=condition=Ready pod/server pod/client --timeout=70s
SERVER_IP=$(k get pod server -o jsonpath='{.status.podIP}')
k exec client -- wget -T 3 -qO- "http://$SERVER_IP:8080/"
apply_manifest network-deny.yaml
# Cilium applique la policy de manière asynchrone : attendre le premier refus.
deadline=$((SECONDS+30)); blocked=0
while (( SECONDS < deadline )); do
  if k exec client -- wget -T 2 -qO- "http://$SERVER_IP:8080/"; then sleep 1; else blocked=1; break; fi
done
[[ $blocked == 1 ]] || { echo 'FAIL NetworkPolicy did not block'; exit 1; }
diagnose client
diagnose server
k describe networkpolicy server-ingress
k get endpointslice -l kubernetes.io/service-name=server
echo 'Observation : pods Ready et endpoints présents; wget échoue après la policy.'
step 'Correction : autoriser uniquement debug-client vers debug-server TCP/8080'
apply_manifest network-fixed.yaml
deadline=$((SECONDS+30)); reached=0
while (( SECONDS < deadline )); do
  if k exec client -- wget -T 2 -qO- "http://$SERVER_IP:8080/"; then reached=1; break; else sleep 1; fi
done
[[ $reached == 1 ]] || { echo 'FAIL fixed policy still blocks'; exit 1; }
echo 'PASS NetworkPolicy: connection blocked then restored (netpol-ok)'
