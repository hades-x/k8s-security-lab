#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
source /data/k8s-lab/infra-services/common.sh
require_lab
kubectl -n velero wait backupstoragelocation/default --for=jsonpath='{.status.phase}'=Available --timeout=300s
echo 'PASS: Garage-backed Velero BackupStorageLocation Available'
# Deliberately require explicit permission for the destructive lab fixture drill.
if [[ "${P3_VERIFY_EXISTING_DRILL:-}" == yes ]]; then
  python3 "$ROOT/infra-services/backup/verify-drill.py"
else
  "$ROOT/infra-services/backup/drill.sh"
fi
