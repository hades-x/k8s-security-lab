#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
source /data/k8s-lab/infra-services/common.sh
require_lab
D="$ROOT/infra-services/observability"
ns monitoring
secret_files monitoring grafana-admin --from-file="admin-user=$SECRET_DIR/grafana-admin-user" --from-file="admin-password=$SECRET_DIR/grafana-admin-password"
secret_files monitoring grafana-oidc --from-file="GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET=$SECRET_DIR/grafana-client-secret"
kubectl create configmap lab-root -n monitoring --from-file="root_ca.crt=$ROOT/.secrets/pki/root_ca.crt" --dry-run=client -o yaml | kubectl apply -f -
chart prometheus monitoring monitoring "$D/prometheus-values.yaml"
chart loki loki monitoring "$D/loki-values.yaml"
chart alloy alloy monitoring "$D/alloy-values.yaml"
kubectl apply -f "$D/manifests.yaml" -f "$D/dashboards.yaml"
kubectl -n monitoring wait certificate/grafana --for=condition=Ready --timeout=600s
"$D/test.sh"
