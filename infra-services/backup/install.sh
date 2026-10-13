#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
source /data/k8s-lab/infra-services/common.sh
require_lab
D="$ROOT/infra-services/backup"
ns s3; ns velero
secret_files s3 garage-config --from-file="garage.toml=$SECRET_DIR/garage.toml"
secret_files s3 garage-credentials --from-file="access-key=$SECRET_DIR/garage-access-key" --from-file="secret-key=$SECRET_DIR/garage-secret-key"
kubectl apply -f "$D/garage.yaml"
wait_deploy s3 garage
# No CLI key creation output; auto bootstrap is stable and reuses host-secret credentials.
kubectl -n s3 exec deployment/garage -- /garage bucket info velero >/dev/null
secret_files velero velero-s3 --from-file="cloud=$SECRET_DIR/velero-credentials"
kubectl apply -f "$D/node-agent-config.yaml"
chart velero velero velero "$D/velero-values.yaml"
kubectl -n velero wait backupstoragelocation/default --for=jsonpath='{.status.phase}'=Available --timeout=300s
echo 'PASS: S3-backed BackupStorageLocation Available; run test.sh for destructive restore drill'
