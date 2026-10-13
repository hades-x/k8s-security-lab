#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# Full acceptance mutates only P6 Git repos/workloads and synthetic lab orders.
set -Eeuo pipefail
export LC_ALL=C
cd /data/k8s-lab
source infra/k3s/env.sh
mkdir -p evidence/p6
exec 9> .pipeline.lock
flock -n 9 || { printf 'FAIL another lab pipeline acceptance owns .pipeline.lock\n' >&2; exit 1; }
if [[ ${1:-} == --read-only ]]; then
  exec python3 -u devsecops/acceptance.py --read-only --timeout 60
fi
if [[ ${1:-} == --demo ]]; then
  exec python3 -u devsecops/acceptance.py --verify-all --admission --e2e --timeout 120
fi
if [[ $# != 0 ]]; then
  printf 'Usage: %s [--read-only|--demo]\n' "$0" >&2
  exit 2
fi
python3 devsecops/test-recovery.py
python3 -u devsecops/acceptance.py --trigger --promote --verify-all --admission --e2e --timeout 600
printf 'PASS phase-p6.sh checks 1/2/3/4 complete exit=0\n'
