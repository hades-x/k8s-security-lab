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
source "$DIR/snapshot-lib.sh"
launch "$DIR/run.sh" 04
extra_cleanup() { snapshot_cleanup; }
init_module
step 'Membres etcd réels : endpoint K3s local /db/info (MemberList)'
"$ROOT/scripts/ssh-node.sh" lab-s1 'sudo curl --fail --silent --show-error --max-time 10 --cacert /var/lib/rancher/k3s/server/tls/server-ca.crt https://127.0.0.1:6443/db/info' | tee "$ROOT/evidence/exercices/04-etcd-members.json"
python3 - "$ROOT/evidence/exercices/04-etcd-members.json" <<'PY'
import json,sys
from pathlib import Path
members=json.loads(Path(sys.argv[1]).read_text())['members']
expected={'https://192.168.150.11:2380','https://192.168.150.12:2380','https://192.168.150.13:2380'}
peers={url for member in members for url in member.get('peerURLs',[])}
if len(members)!=3 or peers!=expected or any(m.get('isLearner') for m in members):
    raise SystemExit('FAIL unexpected etcd membership')
for member in members:
    print(f"ETCD_MEMBER name={member['name']} ID={member['ID']} peers={member['peerURLs']}")
print('PASS etcd MemberList: 3 voting members, expected peer URLs')
PY
step 'Santé API et etcd : readyz verbose'
kubectl --request-timeout=15s get --raw '/readyz?verbose' | tee "$ROOT/evidence/exercices/04-readyz.txt"
python3 - "$ROOT/evidence/exercices/04-readyz.txt" <<'PY'
import sys
from pathlib import Path
text=Path(sys.argv[1]).read_text()
for line in ('[+]etcd ok','[+]etcd-readiness ok','readyz check passed'):
    if line not in text: raise SystemExit('FAIL missing health line: '+line)
print('PASS API/etcd readyz')
PY

step 'Préserver les snapshots existants; refuser un préfixe non possédé'
snapshot_cleanup
listing=$(snapshot_ls)
printf '%s\n' "$listing" | tee "$ROOT/evidence/exercices/04-snapshots-before.txt"
[[ -z $(printf '%s\n' "$listing" | snapshot_names) ]] || { echo 'FAIL foreign ex-snapshot exists, not overwritten/deleted'; exit 1; }
printf 'phase-f-on-lab-s1\n' >"$SNAPSHOT_STATE"
step 'Snapshot à la demande, sans restauration : sudo k3s etcd-snapshot save --name ex-snapshot'
timeout 120 "$ROOT/scripts/ssh-node.sh" lab-s1 'sudo k3s etcd-snapshot save --name ex-snapshot'
listing=$(snapshot_ls)
printf '%s\n' "$listing" | tee "$ROOT/evidence/exercices/04-snapshots-after-save.txt"
python3 - "$ROOT/evidence/exercices/04-snapshots-after-save.txt" <<'PY'
import sys
from pathlib import Path
rows=[line.split() for line in Path(sys.argv[1]).read_text().splitlines() if line.startswith('ex-snapshot-lab-s1-')]
if len(rows)!=1 or len(rows[0])<4 or int(rows[0][2])<=0 or not rows[0][1].startswith('file:///var/lib/rancher/k3s/server/db/snapshots/ex-snapshot-lab-s1-'):
    raise SystemExit('FAIL snapshot not listed with expected location/positive size')
row=rows[0]
print(f'PASS snapshot: name={row[0]} size_bytes={row[2]} location={row[1]} created={row[3]}')
PY
step 'Restauration : documentation seulement, aucune commande cluster-reset exécutée'
echo 'NOT_EXECUTED restore: consulter FICHE.md; token original requis, jamais affiché/copié dans les preuves.'
step 'Suppression ex-snapshot et read-back du catalogue'
snapshot_cleanup
step 'Comparer les noms des snapshots antérieurs'
snapshot_ls >"$ROOT/evidence/exercices/04-snapshots-after-cleanup.txt"
python3 - "$ROOT/evidence/exercices/04-snapshots-before.txt" "$ROOT/evidence/exercices/04-snapshots-after-cleanup.txt" <<'PY'
import sys
from pathlib import Path
def names(path):
    return {row.split()[0] for row in Path(path).read_text().splitlines() if 'file://' in row}
before,after=map(names,sys.argv[1:])
if not before.issubset(after): raise SystemExit('FAIL a pre-existing snapshot disappeared')
print(f'PASS preserved existing snapshots: {len(before)} still present')
PY
kubectl --request-timeout=15s get --raw '/readyz?verbose'
echo 'PASS control-plane snapshot saved/listed/deleted; 3 members; restore NOT executed'
