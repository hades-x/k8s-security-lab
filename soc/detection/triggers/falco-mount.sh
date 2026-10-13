#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
source "$(dirname "${BASH_SOURCE[0]}")/_pod.sh"
# Unprivileged mount is expected to fail with EPERM, never mount a host path.
kubectl -n soc-detection exec lab-trigger -- /bin/sh -c "mkdir -p /tmp/lab-mount; mount -t tmpfs none /tmp/lab-mount; umount /tmp/lab-mount" || true
