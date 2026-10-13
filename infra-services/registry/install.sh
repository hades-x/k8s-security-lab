#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
source /data/k8s-lab/infra-services/common.sh
require_lab
ns zot
secret_files zot zot-auth --from-file="htpasswd=$SECRET_DIR/zot.htpasswd"
kubectl apply -f "$ROOT/infra-services/registry/manifests.yaml"
wait_deploy zot zot
kubectl -n zot wait certificate/zot --for=condition=Ready --timeout=600s
python3 "$ROOT/infra-services/registry/install-crane.py"
"$ROOT/infra-services/registry/test.sh"
