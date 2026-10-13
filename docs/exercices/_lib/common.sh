#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi

# PUBLIC_RUNTIME_DISABLED: reference implementation retained, not an approved runtime.
printf "%s\n" "BLOCKED: automation disabled pending UID/run ownership, exact snapshot ownership and fail-closed API adaptation; see tools/DEPENDENCIES.md" >&2
return 2 2>/dev/null || exit 2
# Shared safety helpers. This file does not run a module when sourced.
set -euo pipefail
export LC_ALL=C
ROOT=/data/k8s-lab
source "$ROOT/infra/k3s/env.sh"
LIB="$ROOT/docs/exercices/_lib"
IMAGE='docker.io/library/busybox:1.37.0@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e'
step() { printf '\n=== %s ===\n' "$*"; }
launch() {
  if [[ ${EX_INNER:-0} != 1 ]]; then
    mkdir -p "$ROOT/evidence/exercices"
    exec 9>"$ROOT/evidence/exercices/.phase-f.lock"
    flock -n 9 || { echo 'FAIL another phase-F exercise is running'; exit 2; }
    set +e
    timeout --signal=TERM --kill-after=20s 550s env EX_INNER=1 bash "$1" 2>&1 | tee -a "$ROOT/evidence/exercices/$2.log"
    local rc=${PIPESTATUS[0]}
    printf 'RUN_EXIT module=%s code=%s\n' "$MODULE" "$rc" | tee -a "$ROOT/evidence/exercices/$2.log"
    exit "$rc"
  fi
  step "$MODULE — $(date --iso-8601=seconds) — plafond 550 s + 20 s de terminaison"
}
k() { kubectl --request-timeout=15s -n "$NS" "$@"; }
preflight() {
  cd "$ROOT"
  step 'Préflight obligatoire, sans mutation'
  timeout 180 make -s status-quick || return 2
  kubectl --request-timeout=15s get nodes -o json | python3 "$LIB/gate.py" || return 2
}
ns_exists() {
  kubectl --request-timeout=15s get namespace "$NS" --ignore-not-found -o name
}
check_owner() {
  local owner
  owner=$(kubectl --request-timeout=15s get namespace "$NS" -o jsonpath='{.metadata.labels.lab\.k8s/exercise}')
  [[ "$owner" == phase-f ]] || { echo "FAIL refusing foreign namespace $NS owner=$owner" >&2; return 1; }
}
cleanup_ns() {
  [[ "$NS" == ex-debug || "$NS" == ex-lifecycle || "$NS" == ex-resources || "$NS" == ex-control-plane ]] || return 1
  local existing
  existing=$(ns_exists) || { echo 'FAIL cleanup: API discovery failed' >&2; return 1; }
  if [[ -n "$existing" ]]; then
    check_owner || return 1
    step "Nettoyage du seul namespace possédé : $NS"
    kubectl --request-timeout=15s delete namespace "$NS" --wait=true --timeout=50s || return 1
  fi
  existing=$(ns_exists) || { echo 'FAIL cleanup: API read-back failed' >&2; return 1; }
  [[ -z "$existing" ]] || { echo "FAIL cleanup: $NS still exists" >&2; return 1; }
  echo "PASS cleanup: namespace $NS absent"
}
setup_ns() {
  # A foreign namespace is never adopted. Remove only a prior phase-f run.
  cleanup_ns
  kubectl --request-timeout=15s create -f "$DIR/manifests/namespace.yaml"
  check_owner
  k get resourcequota,limitrange
  # No LimitRange is installed here: BestEffort is intentional in module 03.
}
apply_manifest() {
  k apply --dry-run=server -f "$DIR/manifests/$1"
  k apply -f "$DIR/manifests/$1"
}
wait_field() {
  local obj=$1 path=$2 expected=$3 seconds=${4:-80} value deadline
  deadline=$((SECONDS + seconds))
  while (( SECONDS < deadline )); do
    value=$(k get "$obj" -o "jsonpath=$path")
    printf '%s %s=%s\n' "$obj" "$path" "$value"
    [[ "$value" == "$expected" ]] && return 0
    sleep 2
  done
  echo "FAIL timeout: $obj expected $expected" >&2
  return 1
}
diagnose() {
  local pod=$1
  step "Diagnostic : $pod (get / describe / logs / events)"
  k get pod "$pod" -o wide
  k describe pod "$pod"
  if ! k logs "$pod" --tail=30 --pod-running-timeout=5s; then
    echo 'Logs indisponibles attendus si aucun conteneur ne démarre.'
  fi
  if ! k logs "$pod" --previous --tail=30 --pod-running-timeout=5s; then
    echo 'Aucun conteneur précédent, ou pod jamais démarré.'
  fi
  k get events --field-selector "involvedObject.name=$pod" --sort-by=.lastTimestamp
}
finish() {
  local rc=$?
  trap - EXIT INT TERM
  set +e
  if declare -F extra_cleanup >/dev/null; then extra_cleanup; local extra_rc=$?; (( extra_rc == 0 )) || rc=1; fi
  cleanup_ns; local clean_rc=$?; (( clean_rc == 0 )) || rc=1
  printf 'RESULT module=%s status=%s elapsed_seconds=%s\n' "$MODULE" "$([[ $rc == 0 ]] && echo PASS || echo FAIL)" "$((SECONDS-START_SECONDS))"
  exit "$rc"
}
init_module() {
  START_SECONDS=$SECONDS
  # Must precede traps and every mutation: a blocked run leaves nothing to clean.
  preflight || { printf 'RESULT module=%s status=FAIL reason=BLOCKED_PREFLIGHT elapsed_seconds=%s\n' "$MODULE" "$((SECONDS-START_SECONDS))"; return 2; }
  trap finish EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  setup_ns
}
