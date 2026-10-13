#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_pod.sh"
MARKER=${FALCO_PROOF:-lab-shell-trigger}
[[ "$MARKER" =~ ^[A-Za-z0-9_-]+$ ]] || exit 2
kubectl -n soc-detection exec lab-trigger -- /bin/sh -c "printf '%s' '$MARKER' >/dev/null"
