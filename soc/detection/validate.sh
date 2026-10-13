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
EVIDENCE=${SOC_VALIDATION_EVIDENCE:-evidence/p4}
mkdir -p "$EVIDENCE" soc/detection/lucene
.venv-sigma/bin/sigma check soc/detection/rules | tee "$EVIDENCE/sigma-check.txt"
for rule in soc/detection/rules/*.yaml; do
 .venv-sigma/bin/sigma convert -t opensearch_lucene --without-pipeline "$rule" >"soc/detection/lucene/$(basename "$rule" .yaml).txt"
done
.venv-sigma/bin/pip freeze >soc/detection/VERSIONS
