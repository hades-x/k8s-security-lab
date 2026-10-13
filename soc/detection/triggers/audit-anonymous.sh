#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d >.secrets/lab-trigger-ca.crt
chmod 600 .secrets/lab-trigger-ca.crt
STATUS=$(curl -sS --cacert .secrets/lab-trigger-ca.crt -o /dev/null -w '%{http_code}' "$SERVER/api/v1/namespaces/soc-detection/pods")
[[ "$STATUS" == 401 || "$STATUS" == 403 ]] || { printf 'Unexpected anonymous status %s\n' "$STATUS" >&2; exit 1; }

