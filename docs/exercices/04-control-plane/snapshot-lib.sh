#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi

# PUBLIC_RUNTIME_DISABLED: reference implementation retained, not an approved runtime.
printf "%s\n" "BLOCKED: automation disabled pending UID/run ownership, exact snapshot ownership and fail-closed API adaptation; see tools/DEPENDENCIES.md" >&2
return 2 2>/dev/null || exit 2
# Snapshot ownership marker is created before save, only after an empty-prefix check.
SNAPSHOT_STATE="$ROOT/evidence/exercices/.04-snapshot-owner"
snapshot_ls() { "$ROOT/scripts/ssh-node.sh" lab-s1 'sudo k3s etcd-snapshot ls'; }
snapshot_names() {
  python3 -c 'import sys; print("\n".join(line.split()[0] for line in sys.stdin if line.split() and line.split()[0].startswith("ex-snapshot-lab-s1-")))'
}
snapshot_cleanup() {
  local listing names name
  if [[ ! -e "$SNAPSHOT_STATE" ]]; then return 0; fi
  [[ $(<"$SNAPSHOT_STATE") == phase-f-on-lab-s1 ]] || { echo 'FAIL invalid snapshot ownership marker'; return 1; }
  listing=$(snapshot_ls) || return 1
  names=$(printf '%s\n' "$listing" | snapshot_names) || return 1
  for name in $names; do
    [[ "$name" =~ ^ex-snapshot-lab-s1-[0-9]+(\.zip)?$ ]] || { echo 'FAIL invalid snapshot name'; return 1; }
    step "Suppression du seul snapshot ex-snapshot : $name"
    "$ROOT/scripts/ssh-node.sh" lab-s1 "sudo k3s etcd-snapshot delete '$name'" || return 1
    "$ROOT/scripts/ssh-node.sh" lab-s1 "sudo test ! -e '/var/lib/rancher/k3s/server/db/snapshots/$name'" || return 1
    echo "PASS snapshot file absent: $name"
  done
  listing=$(snapshot_ls) || return 1
  printf '%s\n' "$listing"
  names=$(printf '%s\n' "$listing" | snapshot_names) || return 1
  [[ -z "$names" ]] || { echo 'FAIL snapshot still listed'; return 1; }
  rm -- "$SNAPSHOT_STATE"
  echo 'PASS cleanup: ex-snapshot absent from fresh k3s etcd-snapshot ls'
}
