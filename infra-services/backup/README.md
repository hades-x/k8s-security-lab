> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Single-node S3 and real PVC restore drill

Garage is a maintained small single-binary S3 store, pinned image+digest, one PVC
for SQLite metadata + object data. Compared with SeaweedFS it needs no separate
master/filer/volume deployments. Garage 2.4.1's documented `--single-node
--default-bucket` bootstrap creates `velero` with random host-generated access
credentials without parsing/logging generated keys. No S3 Ingress is exposed.
It has replication_factor=1: this is **not off-node/offsite disaster recovery**.
Losing its local-path node destroys the backup destination as well.

Velero official Helm chart and compatible AWS plugin 1.14.x / Velero 1.18.x;
path-style S3 endpoint + region garage; optional AWS checksum behavior set to
when_required for S3 compatibility. Uses node-agent and Kopia file-system backup,
not CSI/EBS snapshots. Privileged node-agents mount kubelet pod-volume directories
on every node (including servers). Verify `nodeAgent.podVolumePath` against P1's
actual kubelet root-dir before deployment; the stock /var/lib/kubelet/pods is set.
Kopia repository maintenance jobs have a bounded resource configuration.

Run install with `P3_ALLOW_DEPLOY=yes`; run test.sh with
`P3_ALLOW_DEPLOY=yes P3_ALLOW_DRILL_DELETE=yes` to authorize the restore drill. The explicit
second gate authorizes ONLY fixture namespace deletion. Drill refuses an existing
namespace `drill`; creates a Deployment/PVC, writes random data, records SHA-256,
requires Backup Completed AND completed PodVolumeBackup, deletes that namespace,
restores, requires Restore Completed AND PodVolumeRestore, compares hashes.
Fixture never writes/initializes on restart, so a fake fresh file cannot pass.
Evidence: `evidence/p3/drill-*.txt` and `05-backup-drill.log`.
Read-only re-verification: `P3_ALLOW_DEPLOY=yes P3_VERIFY_EXISTING_DRILL=yes ./test.sh`.
This mode checks the real restored payload against the original recorded checksum,
the fixture label, and completed Backup/Restore/PodVolumeBackup/PodVolumeRestore.
It does not run or claim a new destructive drill. Restored namespace is kept for inspection;
remove it manually before rerunning. No real cluster backup or deletion is made
by preparation/static validation. Smoke readiness without drill: wait for the
`default` BackupStorageLocation Available. This cannot substitute for restore proof.

Velero 1.18 uses extra data-mover pods for FSB. node-agent-config.yaml explicitly
bounds each mover to 192Mi and one load per node, while daemon controllers have
64Mi limits. Maintenance jobs also have 192Mi caps, using documented scalar
podResources fields (not Kubernetes requests/limits syntax). Drill peak budget
assumes one mover and one maintenance job; arbitrary parallel multi-node backups
can create up to five movers and exceed 6Gi. This is an explicit lab scaling risk. Current steady P3 limits are 6088Mi
(including the retained fixture); a simultaneous 192Mi mover plus 192Mi maintenance
job raises the ceiling to 6472Mi (6.32Gi), a documented transient budget deviation.
Velero was raised from 192Mi to 384Mi after the first repository-initialization
backup killed the server. The successful drill used the adjusted limits.
Backup/Restore payload JSON fixtures are statically schema-validated before jq
sets the unique run name at runtime.
