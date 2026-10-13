#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi

# PUBLIC_RUNTIME_DISABLED: reference implementation retained, not an approved runtime.
printf "%s\n" "BLOCKED: automation disabled pending UID/run ownership, exact snapshot ownership and fail-closed API adaptation; see tools/DEPENDENCIES.md" >&2
return 2 2>/dev/null || exit 2
# Sequential, bounded rehearsal. Cleanup runs even when any proof fails.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export LC_ALL=C
cd "$ROOT"
source infra/k3s/env.sh
[[ "${LAB_TRIGGER:-}" == 1 ]] || { printf 'Set LAB_TRIGGER=1\n' >&2; exit 2; }
ATTEMPTS=${SCENARIO_ATTEMPTS:-1}
[[ "$ATTEMPTS" == 1 || "$ATTEMPTS" == 2 ]] || { printf 'SCENARIO_ATTEMPTS must be 1 or 2\n' >&2; exit 2; }
mkdir -p evidence/scenarios
numbers=("$@")
[[ ${#numbers[@]} -gt 0 ]] || numbers=(01 02 03 04 05)
for number in "${numbers[@]}"; do
 [[ "$number" =~ ^0[1-5]$ ]] || { printf 'Invalid scenario number\n' >&2; exit 2; }
done
# Do not allow two concurrent runs to adopt or clean each other's namespaces.
exec 9>evidence/scenarios/.run.lock
flock -n 9 || { printf 'Another Phase E run is active\n' >&2; exit 2; }
run_scope() (
 number=$1
 cleanup_scope() {
  rc=$?
  trap - EXIT
  if [[ -f "evidence/scenarios/$number/state.json" ]]; then
   python3 scenarios/runner.py "$number" cleanup || rc=1
  fi
  exit "$rc"
 }
 trap cleanup_scope EXIT
 for action in generate detect respond verify; do
  printf '\n=== scenario=%s action=%s ===\n' "$number" "$action"
  python3 scenarios/runner.py "$number" "$action" || exit "$?"
 done
)
failed=0
for number in "${numbers[@]}"; do
 result=FAIL
 attempt_used=0
 for ((attempt=1;attempt<=ATTEMPTS;attempt++)); do
  attempt_used=$attempt
  if [[ -f "evidence/scenarios/$number.log" ]]; then
   stamp=$(date -u +%Y%m%dT%H%M%S)
   cp "evidence/scenarios/$number.log" "evidence/scenarios/$number.$stamp.previous.log"
  fi
  if run_scope "$number" 2>&1 | tee "evidence/scenarios/$number.log"; then
   result=PASS
   break
  fi
  printf 'FAIL scenario=%s attempt=%s (max=%s)\n' "$number" "$attempt" "$ATTEMPTS"
 done
 [[ "$result" == PASS ]] || failed=1
 python3 - "$number" "$result" "$attempt_used" <<'PY'
import datetime,json,pathlib,sys
path=pathlib.Path('evidence/scenarios/results.json')
doc=json.loads(path.read_text()) if path.exists() else {'scenarios':{}}
number,result,attempt=sys.argv[1:]
state_path=pathlib.Path('evidence/scenarios')/number/'state.json'
state=json.loads(state_path.read_text()) if state_path.exists() else {}
log=(path.parent/(number+'.log')).read_text()
errors=[line for line in log.splitlines() if line.startswith('FAIL ')]
doc['scenarios'][number]={'result':result,'attempt':min(int(attempt),2),'run_id':state.get('run_id'),
 'started':state.get('started'),'verified':state.get('verified'),'cleaned':state.get('cleaned'),
 'errors':errors,'detections':state.get('detections',[]),'log':'evidence/scenarios/'+number+'.log'}
doc['updated']=datetime.datetime.now(datetime.timezone.utc).isoformat()
path.write_text(json.dumps(doc,indent=2)+'\n')
print('RESULT scenario='+number+' '+result+' cleaned='+str(state.get('cleaned')))
PY
done
if [[ ${#numbers[@]} -eq 5 ]]; then
 python3 scenarios/report.py || failed=1
fi
exit "$failed"
