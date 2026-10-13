#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi

# PUBLIC_RUNTIME_DISABLED: reference implementation retained, not an approved runtime.
printf "%s\n" "BLOCKED: automation disabled pending UID/run ownership, exact snapshot ownership and fail-closed API adaptation; see tools/DEPENDENCIES.md" >&2
return 2 2>/dev/null || exit 2
set -euo pipefail
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MODULE=04-control-plane; NS=ex-control-plane
source "$DIR/../_lib/common.sh"
mkdir -p "$ROOT/evidence/exercices"
exec 9>"$ROOT/evidence/exercices/.phase-f.lock"
flock -n 9 || { echo 'FAIL refusing cleanup while a module is running'; exit 2; }
source "$DIR/snapshot-lib.sh"
snapshot_cleanup
cleanup_ns
