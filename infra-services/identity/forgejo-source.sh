#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# Merge one OAuth source into the existing lab Forgejo database.
source /data/k8s-lab/infra-services/common.sh
require_lab
POD=$(kubectl -n forgejo get pods -l app.kubernetes.io/name=forgejo -o jsonpath='{.items[0].metadata.name}')
if kubectl -n forgejo exec -c forgejo "$POD" -- forgejo admin auth list --config /data/gitea/conf/app.ini | python3 -c 'import sys;sys.exit(0 if any(len(p)>1 and p[1]=="keycloak" for p in (l.split() for l in sys.stdin)) else 1)'; then
  echo 'PASS: existing Keycloak OAuth source retained'; exit 0
fi
cat "$SECRET_DIR/forgejo-client-secret" | kubectl -n forgejo exec -i -c forgejo "$POD" -- sh -c 'secret=$(cat); forgejo admin auth add-oauth --config /data/gitea/conf/app.ini --name keycloak --provider openidConnect --key forgejo --secret "$secret" --auto-discover-url https://keycloak.192.168.150.200.sslip.io/realms/lab/.well-known/openid-configuration --scopes openid --scopes profile --scopes email --scopes groups --group-claim-name groups --admin-group lab-admins'
kubectl -n forgejo exec -c forgejo "$POD" -- forgejo admin auth list --config /data/gitea/conf/app.ini
