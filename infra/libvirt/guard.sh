#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
bytes=$(df -B1 --output=avail /data | tr -d ' ' | tail -1)
if (( bytes < 30 * 1024 * 1024 * 1024 )); then echo 'REFUSED: /data has less than 30 GiB free' >&2; exit 1; fi
printf 'Disk guard PASS: %s bytes available on /data
' "$bytes"
