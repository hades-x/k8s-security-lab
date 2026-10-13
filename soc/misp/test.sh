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
bash soc/misp/bootstrap.sh
bash soc/traffic/replay.sh
POD=$(kubectl -n soc-sensors get pods -l app=zeek --field-selector spec.nodeName="${NODE:-lab-a2}" -o jsonpath='{.items[0].metadata.name}')
for i in {1..30}; do
 if kubectl -n soc-sensors exec "$POD" -c log-merger -- python3 -c 'import json;from pathlib import Path;assert any(json.loads(x).get("seen.indicator")=="ioc.evil-c2.lab.test" or "ioc.evil-c2.lab.test" in x for x in Path("/var/log/zeek/current/intel.log").read_text().splitlines())'; then exit 0; fi
 sleep 2
done
exit 1
