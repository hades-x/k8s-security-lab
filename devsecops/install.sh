#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# Reconcile an already bootstrapped P6 lab. No source generation or Git publication.
set -Eeuo pipefail
export LC_ALL=C
cd /data/k8s-lab
source infra/k3s/env.sh
exec 9> .pipeline.lock
flock -n 9 || { printf 'FAIL another acceptance/reconcile owns .pipeline.lock\n' >&2; exit 1; }
python3 - <<'PY'
import runpy
m=runpy.run_path('devsecops/acceptance.py')
print('PASS resource preflight availableGiB=',m['guard']())
p=m['api'](m['cs'],'GET',m['C']+'/api/repos/'+str(m['RID'])+'/pipelines')
assert not any(x['status'] in ['pending','running','blocked'] for x in p), 'Stop: CI work is active'
PY
python3 devsecops/recovery-fixes.py
python3 devsecops/install-signature-gate.py Enforce
helm upgrade cnpg cnpg/cloudnative-pg --version 0.29.1 -n cnpg-system \
  -f devsecops/cnpg-values.yaml --wait --timeout 2m
helm upgrade woodpecker oci://ghcr.io/woodpecker-ci/helm/woodpecker --version 3.7.5 -n ci \
  -f devsecops/woodpecker-values.yaml --wait --timeout 2m
python3 devsecops/test-recovery.py
python3 devsecops/acceptance.py --read-only --timeout 120
printf 'PASS owned P6 recovery objects reconciled; no Git push/build triggered\n'
