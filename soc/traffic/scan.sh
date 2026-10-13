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
TARGET=${TARGET:?Set a single IPv4 lab node or pod target}
python3 - "$TARGET" <<'PY'
import ipaddress,sys
ip=ipaddress.ip_address(sys.argv[1]);assert ip in ipaddress.ip_network('10.42.0.0/16') or ip in ipaddress.ip_network('192.168.150.0/24'), 'Not a lab target'
PY
JOB=$(python3 -c 'import datetime;print("lab-scan-"+datetime.datetime.now().strftime("%Y%m%d%H%M%S"))')
python3 - "$TARGET" "$JOB" <<'PY' | kubectl apply -f -
import ipaddress,sys,json
from pathlib import Path
ip=ipaddress.ip_address(sys.argv[1]);assert ip in ipaddress.ip_network('10.42.0.0/16') or ip in ipaddress.ip_network('192.168.150.0/24'), 'Not a lab target'
data=json.loads(Path('soc/traffic/scan-job.json').read_text());data['metadata']['name']=sys.argv[2];data['spec']['template']['spec']['containers'][0]['env'][0]['value']=sys.argv[1];print(json.dumps(data))
PY
kubectl -n soc-traffic wait --for=condition=complete job/"$JOB" --timeout=150s
kubectl -n soc-traffic logs job/"$JOB"
