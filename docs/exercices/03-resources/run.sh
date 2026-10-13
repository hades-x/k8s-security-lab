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
MODULE=03-resources; NS=ex-resources
source "$DIR/../_lib/common.sh"
launch "$DIR/run.sh" 03
init_module
step 'Requests / limits et trois classes QoS (exception BestEffort volontaire)'
apply_manifest qos.yaml
k wait --for=condition=Ready pod/guaranteed pod/burstable pod/besteffort --timeout=70s
k get pods -o custom-columns='NAME:.metadata.name,QOS:.status.qosClass,CPU_REQ:.spec.containers[0].resources.requests.cpu,CPU_LIMIT:.spec.containers[0].resources.limits.cpu,MEM_REQ:.spec.containers[0].resources.requests.memory,MEM_LIMIT:.spec.containers[0].resources.limits.memory'
wait_field pod/guaranteed '{.status.qosClass}' Guaranteed 5
wait_field pod/burstable '{.status.qosClass}' Burstable 5
wait_field pod/besteffort '{.status.qosClass}' BestEffort 5
echo 'PASS QoS: Guaranteed / Burstable / BestEffort observed'

step 'OOM de conteneur, un seul pod limité à 64Mi (jamais de stress de nœud)'
apply_manifest oom.yaml
wait_field pod/oom '{.status.containerStatuses[0].state.terminated.reason}' OOMKilled 70
wait_field pod/oom '{.status.containerStatuses[0].state.terminated.exitCode}' 137 5
diagnose oom
k get pod oom -o jsonpath='reason={.status.containerStatuses[0].state.terminated.reason} exitCode={.status.containerStatuses[0].state.terminated.exitCode} memoryLimit={.spec.containers[0].resources.limits.memory}{"\n"}'
echo 'PASS OOM container: reason=OOMKilled exitCode=137 memoryLimit=64Mi'
step 'Correction : supprimer le memory hog, conserver la limite 64Mi'
k delete pod oom --wait=true --timeout=30s
apply_manifest oom-fixed.yaml
wait_field pod/oom '{.status.containerStatuses[0].state.terminated.reason}' Completed 60
wait_field pod/oom '{.status.containerStatuses[0].state.terminated.exitCode}' 0 5
k logs oom

step 'Incident réel D11 : extraire uniquement les réservations et seuils de s1'
# Never dump config.yaml: it may contain a cluster token. Filter in the VM first.
"$ROOT/scripts/ssh-node.sh" lab-s1 "sudo python3 -c 'from pathlib import Path; lines=Path(\"/etc/rancher/k3s/config.yaml\").read_text().splitlines(); print(\"\\n\".join(s.strip() for s in lines if any(k in s for k in (\"system-reserved=\",\"kube-reserved=\",\"eviction-hard=\",\"eviction-soft=\",\"eviction-soft-grace-period=\"))))'" | tee "$ROOT/evidence/exercices/03-s1-kubelet.txt"
python3 - "$ROOT/evidence/exercices/03-s1-kubelet.txt" <<'PY'
import sys
from pathlib import Path
text=Path(sys.argv[1]).read_text()
for key in ('system-reserved=', 'kube-reserved=', 'eviction-hard='):
    if key not in text: raise SystemExit('FAIL missing observed s1 setting: '+key)
print('PASS s1 reservations and hard eviction thresholds read from config.yaml')
PY
step 'Agents : vérifier le gap connu, sans rien modifier'
for node in lab-a1 lab-a2; do
  printf '%s ' "$node"
  "$ROOT/scripts/ssh-node.sh" "$node" "sudo python3 -c 'from pathlib import Path; s=Path(\"/etc/rancher/k3s/config.yaml\").read_text(); keys=[k for k in (\"system-reserved=\",\"kube-reserved=\") if k in s]; print(\"reservation_keys=\"+str(keys)); raise SystemExit(1 if keys else 0)'"
done
echo 'PASS known gap confirmed: agents have NO kubelet reservations; unchanged'
step 'Santé des cinq nœuds après OOM limité'
kubectl get nodes -o json | python3 "$LIB/gate.py"
echo 'PASS resource module: cgroup OOM isolated, D11 node-level incident not replayed'
