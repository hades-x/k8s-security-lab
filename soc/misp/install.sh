#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
export KUBECONFIG=${KUBECONFIG:-/data/k8s-lab/.secrets/kubeconfig}
export PATH="$ROOT/bin:$PATH"
cd "$ROOT"
umask 077
mkdir -p .secrets
exec 9>.secrets/misp-install.lock
flock 9
python3 - <<'PY'
from pathlib import Path
import secrets
p=Path('.secrets/misp.env')
if not p.exists():
 keys=['ADMIN_PASSWORD','ADMIN_KEY','MYSQL_PASSWORD','MYSQL_ROOT_PASSWORD','REDIS_PASSWORD'];p.write_text(''.join(k+'='+secrets.token_hex(20 if k=="ADMIN_KEY" else 32)+'\n' for k in keys));p.chmod(0o600)
p.chmod(0o600)
d=dict(line.split('=',1) for line in p.read_text().splitlines())
for name,key in [('misp-api-key','ADMIN_KEY'),('misp-admin-password','ADMIN_PASSWORD')]:
 f=Path('.secrets',name);f.write_text(d[key]);f.chmod(0o600)
PY
kubectl create namespace misp --dry-run=client -o yaml | kubectl apply -f -
kubectl -n misp create secret generic misp-credentials --from-env-file=.secrets/misp.env --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f soc/misp/manifests.yaml
kubectl -n soc-sensors create secret generic misp-export-credentials --from-file=api-key=.secrets/misp-api-key --dry-run=client -o yaml | kubectl apply -f -
kubectl -n soc-sensors create configmap misp-export-scripts --from-file=soc/misp/misp-to-zeek-intel.py --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f soc/misp/intel-cronjob.yaml
for app in misp-db misp-cache misp-core misp; do kubectl -n misp rollout status deployment/"$app" --timeout=900s; done
