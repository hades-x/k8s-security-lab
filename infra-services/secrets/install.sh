#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
source /data/k8s-lab/infra-services/common.sh
require_lab
D="$ROOT/infra-services/secrets"
ns secrets
# OpenBao starts sealed; --wait would deadlock on sealed readiness.
package=$(python3 -c 'import json;print(json.load(open("/data/k8s-lab/evidence/p3-prep/versions.json"))["openbao"]["package"])')
python3 -c 'import json,hashlib,pathlib;r=pathlib.Path("/data/k8s-lab");v=json.load(open(r/"evidence/p3-prep/versions.json"))["openbao"];assert hashlib.sha256((r/v["package"]).read_bytes()).hexdigest()==v["sha256"],"OpenBao chart checksum mismatch"'
helm upgrade --install openbao "$ROOT/$package" -n secrets -f "$D/openbao-values.yaml" --timeout 10m
kubectl -n secrets wait pod/openbao-0 --for=jsonpath='{.status.phase}'=Running --timeout=600s
"$D/unseal.sh"
chart eso external-secrets secrets "$D/eso-values.yaml"
kubectl apply -f "$D/external-secrets.yaml"
python3 "$D/configure.py"
"$D/test.sh"
