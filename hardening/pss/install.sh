#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
saved_kubeconfig=${KUBECONFIG:-}
source "$ROOT/infra/k3s/env.sh"
[[ -z $saved_kubeconfig ]] || export KUBECONFIG=$saved_kubeconfig
kubectl apply -f "$ROOT/hardening/pss/namespaces.yaml"
python3 "$ROOT/hardening/pss/apply-budgets.py"
# Required node-facing components; Audit/Warn only otherwise, no SOC restriction.
for ns in kube-system longhorn-system soc-sensors falco audits; do
 kubectl label namespace "$ns" pod-security.kubernetes.io/enforce=privileged pod-security.kubernetes.io/enforce-version=v1.36 pod-security.kubernetes.io/audit=restricted pod-security.kubernetes.io/audit-version=v1.36 --overwrite
done
