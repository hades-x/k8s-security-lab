#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
trap 'kubectl -n soc-detection delete secret lab-dummy --ignore-not-found >/dev/null' EXIT
kubectl -n soc-detection create secret generic lab-dummy --from-literal=marker=not-a-secret --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n soc-detection get secret lab-dummy -o json >/dev/null
