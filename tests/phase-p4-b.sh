#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
export LAB_TRIGGER=1
bash soc/zeek/test.sh
bash soc/traffic/test.sh
bash soc/misp/test.sh
bash soc/falco/test.sh
bash soc/detection/test.sh
printf 'PASS phase P4-B live acceptance\n'
