#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# P4 gate. Default mode produces fresh defensive-lab evidence; no external traffic.
set -euo pipefail
ROOT=/data/k8s-lab
source "$ROOT/infra/k3s/env.sh"
cd "$ROOT"
[[ -s "$KUBECONFIG" ]]
mkdir -p evidence/p4
server=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
python3 - "$server" <<'PY'
import ipaddress,sys,urllib.parse
assert ipaddress.ip_address(urllib.parse.urlsplit(sys.argv[1]).hostname) in ipaddress.ip_network('192.168.150.0/24'),'Refusing non-lab Kubernetes API'
PY
case "${1:-}" in
 --read-only)
  # Read-only means no Kubernetes resource changes or trigger traffic. These
  # health checks may write local CA/evidence files and create loopback tunnels.
  bash soc/kafka/test.sh
  SOC_REQUIRE_DATA=1 bash soc/opensearch/test.sh
  bash soc/pipeline/test.sh
  bash soc/zeek/test.sh
  kubectl -n falco rollout status ds/falco --timeout=60s
  python3 soc/opensearch/acceptance.py
  printf 'PASS P4 read-only health and retained evidence; fresh trigger acceptance was not rerun\n'
  exit 0
  ;;
 '') ;;
 *) printf 'Usage: tests/phase-p4.sh [--read-only]\n' >&2; exit 2;;
esac
exec 9>.secrets/phase-p4.lock
flock -n 9 || { printf 'Another P4 acceptance run holds the lab lock\n' >&2; exit 1; }
export LAB_TRIGGER=1
printf 'P4 acceptance started %s\n' "$(date -Is)"
bash tests/phase-p4-a.sh
bash tests/phase-p4-b.sh
python3 soc/detection/test-live.py
bash soc/misp/test-intel.sh
python3 soc/opensearch/dashboards/import.py
bash soc/pipeline/test-lag.sh
python3 soc/opensearch/acceptance.py
printf 'PASS P4 complete end-to-end acceptance %s\n' "$(date -Is)"
