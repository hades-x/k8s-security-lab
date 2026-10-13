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
bash soc/traffic/replay.sh
POD=$(kubectl -n soc-sensors get pods -l app=zeek --field-selector spec.nodeName="${NODE:-lab-a2}" -o jsonpath='{.items[0].metadata.name}')
kubectl -n soc-sensors exec -i "$POD" -c log-merger -- python3 - <<'PY'
from pathlib import Path
import json
path=Path('/var/log/zeek/current')
for typ in ['dns','conn','http','notice']:
 rows=[json.loads(line) for line in (path/(typ+'.log')).read_text().splitlines()]
 assert any(row.get('capture_source')=='tap' for row in rows), 'Missing tap entries: '+typ
 print('PASS replay '+typ+' entries')
PY
