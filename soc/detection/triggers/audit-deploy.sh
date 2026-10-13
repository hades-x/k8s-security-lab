#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
kubectl -n soc-detection delete pod lab-trigger --ignore-not-found >/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_pod.sh"
