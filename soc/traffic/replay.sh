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
NODE=${NODE:-lab-a2}
[[ "$NODE" =~ ^lab-(s[1-3]|a[1-2])$ ]] || { printf 'Only lab nodes allowed\n' >&2; exit 2; }
# Wait until sensor tap exists. Replace suspended template before creating a bounded Job.
[[ -f soc/traffic/pcaps/lab-scenarios.pcap ]] || .venv-traffic/bin/python soc/traffic/generate-pcaps.py
kubectl -n soc-sensors create configmap lab-pcaps --from-file=soc/traffic/pcaps/lab-scenarios.pcap --dry-run=client -o yaml | kubectl apply -f -
kubectl -n soc-sensors patch cronjob pcap-replay --type=merge -p "{\"spec\":{\"jobTemplate\":{\"spec\":{\"template\":{\"spec\":{\"nodeSelector\":{\"kubernetes.io/hostname\":\"$NODE\"}}}}}}}"
JOB=pcap-replay-$(date +%s)
kubectl -n soc-sensors create job "$JOB" --from=cronjob/pcap-replay
kubectl -n soc-sensors wait --for=condition=complete job/"$JOB" --timeout=200s
kubectl -n soc-sensors logs job/"$JOB"
