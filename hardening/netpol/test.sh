#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
export PATH="$ROOT/bin:$PATH"
export KUBECONFIG="${KUBECONFIG:-$ROOT/.secrets/kubeconfig}"
export LC_ALL=C
for ns in dev staging prod demo; do
 [[ $(kubectl -n "$ns" get networkpolicy default-deny -o jsonpath='{.spec.policyTypes[*]}') == 'Ingress Egress' ]]
 [[ $(kubectl -n "$ns" get ciliumnetworkpolicy quarantine -o jsonpath='{.spec.egressDeny[0].toEntities[0]}') == all ]]
done
printf 'PASS: default deny and overriding quarantine objects exist; run scenarios for dataplane proof\n'
