#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
source /data/k8s-lab/infra-services/common.sh
require_lab
D="$ROOT/infra-services/pki"
ns cert-manager; ns pki
kubectl apply --server-side -f "$D/gateway-api.yaml"
chart cert-manager cert-manager cert-manager "$D/cert-manager-values.yaml"
kubectl apply -f "$D/step-public.yaml"
secret_files pki step-ca-secrets --from-file="intermediate_ca_key=$ROOT/.secrets/pki/intermediate_ca.key"
secret_files pki step-ca-ca-password --from-file="password=$ROOT/.secrets/pki/intermediate-password"
# CA fallback mounts the issuing intermediate only, never the root key.
cat "$ROOT/.secrets/pki/intermediate_ca.crt" "$ROOT/.secrets/pki/root_ca.crt" > "$ROOT/.secrets/pki/fallback-chain.crt"
chmod 600 "$ROOT/.secrets/pki/fallback-chain.crt"
kubectl -n cert-manager create secret tls lab-ca-intermediate --cert="$ROOT/.secrets/pki/fallback-chain.crt" --key="$ROOT/.secrets/pki/fallback_ca.key" --dry-run=client -o yaml | kubectl apply -f -
chart step-ca step-ca pki "$D/step-ca-values.yaml"
kubectl apply -f "$D/issuers.yaml"
"$D/test.sh"
