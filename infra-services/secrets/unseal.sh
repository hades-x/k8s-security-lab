#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
source /data/k8s-lab/infra-services/common.sh
require_lab
file="$SECRET_DIR/openbao-init.json"
# Never regenerate init material for an already initialized instance.
status=''
for attempt in $(seq 1 60); do
  if status=$(kubectl -n secrets exec openbao-0 -- bao status -format=json 2>/dev/null || [[ $? == 2 ]]) && [[ -n "$status" ]] && jq -e 'has("initialized") and has("sealed")' <<< "$status" >/dev/null 2>&1; then break; fi
  sleep 2
done
[[ -n "$status" ]] && jq -e 'has("initialized") and has("sealed")' <<< "$status" >/dev/null || { echo 'OpenBao status unavailable' >&2; exit 2; }
if [[ $(jq -r '.initialized' <<< "$status") != true ]]; then
  [[ ! -e "$file" ]] || { echo 'Uninitialized server but existing init file: reconcile storage before proceeding' >&2; exit 2; }
  kubectl -n secrets exec openbao-0 -- bao operator init -key-shares=1 -key-threshold=1 -format=json > "$file.tmp"
  jq -e 'has("root_token") and has("unseal_keys_b64")' "$file.tmp" >/dev/null
  chmod 600 "$file.tmp"
  mv "$file.tmp" "$file"
fi
[[ -s "$file" ]] || { echo 'Missing init file for initialized instance; do not re-init' >&2; exit 2; }
if [[ $(jq -r '.sealed' <<< "$status") == true ]]; then
  jq -r '.unseal_keys_b64[0]' "$file" | kubectl -n secrets exec -i openbao-0 -- sh -c 'read -r key; bao operator unseal "$key" >/dev/null'
fi
kubectl -n secrets wait pod/openbao-0 --for=condition=Ready --timeout=180s
echo 'PASS: OpenBao initialized and unsealed (no keys printed)'
