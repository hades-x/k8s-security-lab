#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -Eeuo pipefail
ROOT=/data/k8s-lab
export LC_ALL=C
if [[ "${1:-}" == --static ]]; then
  exec python3 "$ROOT/evidence/p3-prep/static-validate.py"
fi
source "$ROOT/infra-services/common.sh"
require_lab
mkdir -p "$ROOT/evidence/p3"
for service in pki secrets identity observability backup registry; do
  "$ROOT/infra-services/$service/test.sh" 2>&1 | tee "$ROOT/evidence/p3/$service-test.txt"
done
python3 "$ROOT/infra-services/pki/chain-check.py" 2>&1 | tee "$ROOT/evidence/p3/tls-chain-test.txt"
for app in grafana argocd forgejo; do
  python3 "$ROOT/infra-services/identity/sso-session-check.py" "$app" 2>&1 | tee "$ROOT/evidence/p3/$app-sso-test.txt"
done
printf 'PASS: all P3 infrastructure runtime acceptance checks completed\n'
