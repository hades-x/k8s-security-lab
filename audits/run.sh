#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export PATH="$ROOT/bin:$PATH"
export KUBECONFIG="${KUBECONFIG:-$ROOT/.secrets/kubeconfig}"
export LC_ALL=C
phase=${1:?before or after}; [[ $phase == before || $phase == after ]]
if [[ $phase == before ]]; then
 printf 'Refusing to overwrite history: no complete pre-hardening baseline exists. Use paired p4 seed-file reconstruction; see docs/hardening-report.md.\n' >&2
 exit 2
fi
python3 "$ROOT/audits/collect-safe.py" kube-bench
python3 "$ROOT/audits/collect-safe.py" kubescape
if [[ ${TRIVY_COLLECTION_CONFIRM:-} != six-namespaces-ca-reviewed ]]; then
 printf 'Fresh Trivy vulnerability collection is blocked by registry CA trust. Review trust/configuration, then explicitly set TRIVY_COLLECTION_CONFIRM=six-namespaces-ca-reviewed for a bounded retry.\n' >&2
 exit 2
fi
python3 "$ROOT/audits/collect-safe.py" trivy
"$ROOT/hardening/rbac/audit-secrets.sh" "$ROOT/evidence/p5/after/rbac"
kubectl get policyreports -A -o json > "$ROOT/evidence/p5/after/kyverno-reports.json"
python3 "$ROOT/audits/summarize.py" "$ROOT/evidence/p5/after"
