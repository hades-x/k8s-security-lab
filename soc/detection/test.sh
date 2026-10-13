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
bash soc/detection/validate.sh
python3 - <<'PY'
from pathlib import Path
import json
rules=list(Path('soc/detection/rules').glob('*.yaml'));assert len(rules)>=10
for r in rules:
 assert Path('soc/detection/triggers',r.stem+'.sh').exists()
 assert json.loads(Path('soc/detection/queries',r.stem+'.json').read_text())['query']
 assert Path('soc/detection/lucene',r.stem+'.txt').read_text().strip()
print('PASS',len(rules),'rules, triggers, fallback queries, Lucene outputs')
PY
