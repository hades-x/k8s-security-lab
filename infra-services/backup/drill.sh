#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
source /data/k8s-lab/infra-services/common.sh
require_lab
[[ "${P3_ALLOW_DRILL_DELETE:-}" == yes ]] || { echo 'Set P3_ALLOW_DRILL_DELETE=yes to create/delete ONLY the disposable drill namespace.' >&2; exit 2; }
mkdir -p "$ROOT/evidence/p3"
exec 9>"$ROOT/.secrets/p3/drill.lock"; flock -n 9 || { echo 'Another drill is running' >&2; exit 2; }
kubectl get namespace drill >/dev/null 2>&1 && { echo 'Refusing existing drill namespace; inspect it and delete manually if appropriate' >&2; exit 2; }
run="drill-$(date -u +%Y%m%d%H%M%S)"
ns drill
kubectl label namespace drill lab-phase=p3-drill
kubectl apply -f "$ROOT/infra-services/backup/drill-fixture.yaml"
wait_deploy drill data
# Random payload generated INSIDE lab pod, no secret or test-data file on host.
kubectl -n drill exec deployment/data -- sh -c 'dd if=/dev/urandom of=/data/payload bs=1024 count=256 2>/dev/null; sync'
before=$(kubectl -n drill exec deployment/data -- sha256sum /data/payload | cut -d' ' -f1)
jq --arg run "$run" '.metadata.name=$run' "$ROOT/infra-services/backup/drill-backup.json" | kubectl apply -f -
kubectl -n velero wait "backup.velero.io/$run" --for=jsonpath='{.status.phase}'=Completed --timeout=1200s
# Completed metadata alone is insufficient: require a completed pod-volume backup.
kubectl -n velero get podvolumebackups -l "velero.io/backup-name=$run" -o json | jq -e '.items | length > 0 and all(.[]; .status.phase == "Completed")' >/dev/null
[[ $(kubectl get namespace drill -o jsonpath='{.metadata.labels.lab-phase}') == p3-drill ]]
kubectl delete namespace drill --wait=true --timeout=300s
jq --arg run "$run" '.metadata.name=$run | .spec.backupName=$run' "$ROOT/infra-services/backup/drill-restore.json" | kubectl apply -f -
kubectl -n velero wait "restore.velero.io/$run" --for=jsonpath='{.status.phase}'=Completed --timeout=1200s
wait_deploy drill data
kubectl -n velero get podvolumerestores -l "velero.io/restore-name=$run" -o json | jq -e '.items | length > 0 and all(.[]; .status.phase == "Completed")' >/dev/null
after=$(kubectl -n drill exec deployment/data -- sha256sum /data/payload | cut -d' ' -f1)
[[ "$before" == "$after" ]]
printf 'backup=%s phase=Completed\nrestore=%s phase=Completed\nbefore_sha256=%s\nafter_sha256=%s\nchecksum_equal=true\n' "$run" "$run" "$before" "$after" | tee "$ROOT/evidence/p3/$run.txt"
# Keep restored namespace for inspection. Subsequent runs intentionally refuse it.
