#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
source /data/k8s-lab/infra-services/common.sh
require_lab
D="$ROOT/infra-services/identity"
ns identity
secret_files identity ldap-admin --from-file="ldap-admin-password=$SECRET_DIR/ldap-admin-password"
secret_files identity ldap-bootstrap --from-file="entries.ldif=$SECRET_DIR/entries.ldif"
secret_files identity keycloak-env --from-file="KC_BOOTSTRAP_ADMIN_PASSWORD=$SECRET_DIR/keycloak-admin-password" --from-file="LDAP_BIND_PASSWORD=$SECRET_DIR/ldap-admin-password" --from-file="GRAFANA_CLIENT_SECRET=$SECRET_DIR/grafana-client-secret" --from-file="ARGOCD_CLIENT_SECRET=$SECRET_DIR/argocd-client-secret" --from-file="FORGEJO_CLIENT_SECRET=$SECRET_DIR/forgejo-client-secret" --from-file="OPENSEARCH_DASHBOARDS_CLIENT_SECRET=$SECRET_DIR/opensearch-dashboards-client-secret"

kubectl apply -f "$D/workloads.yaml"
wait_deploy identity openldap
wait_deploy identity keycloak
kubectl -n identity wait certificate/keycloak --for=condition=Ready --timeout=600s
"$D/test.sh"
