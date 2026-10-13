> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# P3 offline preparation

No preparation command deploys to or contacts Kubernetes. Install/runtime tests
require BOTH explicit P3_ALLOW_DEPLOY=yes and a lab-only kubeconfig endpoint in
192.168.150.11-.13. Fixed kubeconfig: /data/k8s-lab/.secrets/kubeconfig. Host Docker,
libvirt, host networking and real homelab credentials are not used.

Static: `./tests/phase-p3.sh --static` (Helm render, YAML/JSON/shell validation,
strict kubeconform with exact upstream CRD schemas, pinned-image/resource checks).
Charts cached under evidence/p3-prep/charts with upstream SHA-256 checksums; this
cache is ignored in git. Rebuild with `python3 evidence/p3-prep/fetch-charts.py` (exact VERSIONS pins;
refuses lock/index/checksum drift). discover.py is original discovery evidence,
NOT an installer or a supported refresh command.
Private lab files are generated only in .secrets/p3 and .secrets/pki, mode 600.

Ordered install after P1/P2 are ready:
```
cd /data/k8s-lab
export KUBECONFIG=/data/k8s-lab/.secrets/kubeconfig
export P3_ALLOW_DEPLOY=yes P3_ALLOW_DRILL_DELETE=yes
./infra-services/pki/install.sh
./infra-services/secrets/install.sh
./infra-services/identity/install.sh
./infra-services/observability/install.sh
./infra-services/backup/install.sh
./infra-services/registry/install.sh
./tests/phase-p3.sh
```
Backup install performs S3 readiness only; the final phase test performs the
explicitly gated drill, keeping restored `drill` namespace. Before a phase test
rerun inspect/delete **only that fixture** yourself; tests refuse an existing
drill namespace. All installers are idempotent; the destructive drill is separate.
Each install is state-preserving/idempotent; the destructive drill is explicitly
not a silently repeatable installer action. Realm imports do not update an existing
realm; see identity notes. chart --wait sealed OpenBao startup is intentionally
handled separately. Verify Kubernetes version compatibility and node-agent host
paths on actual P1 nodes; Helm rendering uses Kubernetes 1.35 schema only.

Offline verified: static manifests and locally generated certificate chain.
NOT verified: cluster deployment, image startup, resource usage, OIDC browser SSO,
ACME issuance, ESO sync, scrape/log ingestion, S3 backup/restore, OCI push/pull.
Requests and hard limits are lab-sized; five-node DaemonSets are budgeted. See
evidence/p3-prep/resource-budget.json from static validation for the calculated rather than guessed
RAM total. local-path means node-bound data; Longhorn can be selected explicitly
for RWO workloads later but is not assumed by P3.

Validation scope: kubeconform validates native objects and CRs against the exact
chart CRD schemas. 65 CustomResourceDefinition objects themselves are skipped
because the Kubernetes native schema catalog excludes apiextensions CRD schemas;
CRD YAML/JSON parsing and required names/versions/schema checks still run. This
is NOT Kubernetes server-side admission/structural-schema validation. Helm test
hooks are excluded (`--skip-tests`); installation hooks are validated/resource
bounded. Kubernetes schema 1.35.0 is the selected static target, not a claim about
the not-yet-deployed P1 cluster. Cached chart artifacts are checksum-checked.
The restore drill demonstrates only a tiny payload. Node-agent controllers 128Mi, movers 192Mi, Prometheus
640Mi and Alloy 96Mi limits may OOM under realistic load; raise them after measuring
and account for workload/maintenance concurrency before accepting the budget.
