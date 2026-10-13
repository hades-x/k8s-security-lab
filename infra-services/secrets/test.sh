#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
source /data/k8s-lab/infra-services/common.sh
require_lab
kubectl wait clustersecretstore/lab-openbao --for=condition=Ready --timeout=300s
kubectl -n secrets wait externalsecret/demo --for=condition=Ready --timeout=300s
# Compare only a deliberately public demonstration value; no real credential is output.
value=$(kubectl -n secrets get secret demo-synced -o jsonpath='{.data.message}' | base64 -d)
[[ "$value" == lab-demo-not-a-production-secret ]]
echo 'PASS: ExternalSecret Ready; demo secret matches expected demonstration value (value withheld)'
python3 "$ROOT/infra-services/secrets/verify.py"
