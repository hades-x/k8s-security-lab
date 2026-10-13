> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# P4-A: Kafka → OpenSearch SOC pipeline (offline preparation)

Prepared on 2026-10-13. Nothing was applied to Kubernetes during this phase. No
host Docker, libvirt, host network/sysctl changes, VM changes or Git commits were used.
Manifests and scripts are ready for the integrator's **first deployment and runtime tests**;
static success is not a claim of broker availability or end-to-end delivery.

## Ordered installation

Run on lab controller after K3s/Cilium, Traefik and the `local-path` StorageClass are ready:

```bash
export LC_ALL=C
cd /data/k8s-lab
export PATH="/data/k8s-lab/bin:$PATH"
export KUBECONFIG=/data/k8s-lab/.secrets/kubeconfig
bash soc/kafka/install.sh
bash soc/opensearch/install.sh
bash soc/pipeline/install.sh
# Integrator: deploy part B sensors/audit/Falco and replay the expected data.
# Produce at least one conn/dns/http/notice/intel hit, Kubernetes audit event
# and Falco alert. Empty quiet topics deliberately FAIL the data acceptance.
bash tests/phase-p4-a.sh
```

The phase test briefly scales the indexer to zero to run a TLS/SCRAM round-trip
with its exact, least-privilege consumer group, then restores its previous replicas
even on failure. The console consumer has auto-commit disabled: it must not steal
committed offsets from the indexer. Acceptance also requires an explicit topic ACL
denial for the authenticated **read-only** indexer attempting to produce.

`helm upgrade --install` is idempotent for these pinned initial chart versions;
this is not a general major-version upgrade procedure. Upgrading Strimzi CRDs or
OpenSearch schemas requires upstream upgrade guidance. Each script has bounded waits.
A missing kubeconfig stops the installer before any apply.

## Pins and API differences

| Component | Pin | Notes |
|---|---|---|
| Strimzi operator/chart | 1.3.0 | Released October 12; **kafka.strimzi.io/v1**, not v1beta2 |
| Kafka | 4.3.1 | Newest Kafka supported in the selected Strimzi stable release; KRaft only |
| OpenSearch operator chart | 3.0.14 | Operator app version is **3.0.0**, not 3.0.14 |
| OpenSearch + Dashboards | 3.9.0 | **opensearch.org/v1**, not deprecated opensearch.opster.io/v1 |
| Vector | 0.59.0 | Ignore GitHub's unrelated `vdev-*` latest-release response |

Versions and sources are in each component's `VERSIONS`. Workload images include
registry/release manifest SHA-256 digests. Helm archives are SHA-256 checked before
rendering or installation. `bin/vector` was downloaded as the static x86_64-musl
binary, with its archive hash verified against the official release asset metadata.
`bin/p4-prep-a/` and tool binaries are gitignored caches, not tracked deliverables.

## Resources and storage

These are **configured requests/limits**, not measured RSS or performance claims.

| Component | Memory requests | Memory limits | Disk |
|---|---:|---:|---|
| Kafka combined controller+broker, three | 3 × 1 GiB | 3 × 1.5 GiB | 3 × 10 GiB local-path |
| Strimzi operator + topic/user operators | 384 + 128 + 128 MiB | 512 + 256 + 256 MiB | ephemeral |
| OpenSearch, three combined nodes | 3 × 2 GiB | 3 × 2 GiB | 3 × 20 GiB local-path |
| OpenSearch bootstrap, temporary | 2 GiB | 2 GiB | 2 GiB local-path, temporary |
| OpenSearch operator | 256 MiB | 512 MiB | ephemeral |
| Dashboards, one replica | 512 MiB | 768 MiB | ephemeral |
| Vector Zeek, each eligible node | 64 MiB | 192 MiB | 256 MiB bounded sink buffer + checkpoints |
| Vector audit, each control-plane node | 64 MiB | 192 MiB | 256 MiB bounded sink buffer + checkpoints |
| Vector indexer, one replica | 128 MiB | 384 MiB | 3 GiB local-path; seven × 256 MiB buffers |

Kafka heap is 768m per node; OpenSearch heap is 1g. Keep three OpenSearch nodes:
the selected operator explicitly does not support a single-node cluster. Both Kafka
and OpenSearch require distinct hosts for their own three replicas via hard pod
anti-affinity; tolerations allow placement on control-plane nodes. The temporary
OpenSearch bootstrap and security-update Job add peak memory during initialization.
At the planned five-node/three-server topology: requests total 11 GiB, steady
memory-limit sum 14.625 GiB; bootstrap + security-update peak limit sum 17.125 GiB.
`evidence/p4-prep-a/11-memory-budget.json` derives these totals from the manifests.
This excludes node OS/K3s and all workloads owned by other preparation workers.
Vector disk buffers require at least **268435488 bytes each**; all nine sinks
meet this minimum. `--no-environment` alone does not instantiate buffers, so the
validation additionally checks this contract and the offline runtime test exercises
real disk-buffer initialization. Seven indexer buffers fit in its 3Gi PVC.

`local-path` volumes are **node-bound**, not Longhorn-replicated. Application-level
Kafka RF=3 and OpenSearch index replicas=1 survive some node failures, but replacing
a lost node/PVC is manual. Local-path capacity requests do not impose filesystem
quotas. Check VM disk capacity: Kafka retention.bytes is **per partition**, so the
seven topics' data caps are not a single cluster-wide 256 MiB limit. The 24h
retention plus 64 MiB segments are deliberately small lab defaults, not sizing for
production traffic. Retention deletion is asynchronous.

## Security and trust boundaries

- Kafka has only an internal 9093 TLS listener, SCRAM-SHA-512, and simple ACLs.
  There is no plaintext listener and no public broker Ingress/LoadBalancer.
- The seven topics use three partitions, RF=3, min.insync.replicas=2 and 24h
  retention with a per-partition cap of 256 MiB. Producers require `acks=all`.
- Each Strimzi KafkaUser produces a Secret with the **same name** in `kafka`,
  containing its SCRAM `password` (and convenience `sasl.jaas.config`). These
  are operator-generated; do not store their decoded contents in Git or evidence.
- Consumers mount only `ca.crt` from **soc-cluster-ca-cert**. Never mount/export
  `soc-cluster-ca` (the CA private key). Vector pods use their own KafkaUser and
  least-privilege ACLs; `soc-indexer` can read exactly the seven topics and use
  exactly the `soc-indexer` group, but cannot produce. The shippers cannot read.
- Kafka idempotent producer mode is disabled rather than granting a broader
  cluster `IdempotentWrite` ACL. File-source acknowledgements + disk buffering + retries give at-least-once,
  **not exactly-once** delivery; duplicates remain possible.
- OpenSearch Security is enabled with generated transport/HTTP TLS. Passwords
  are generated at install time into `.secrets/opensearch-*.password` under
  umask 077/chmod 600 and are never printed. Only runtime Secret payloads hold them.
- Admin/Dashboards credentials are supplied before the cluster CR. Separate
  non-reserved `soc-indexer` and `soc-analyst` users/roles are created by REST;
  SOC index write permissions belong only to the indexer, analyst access is read.
  A separate Dashboards role allows only its `.kibana*`/`.opensearch_dashboards*`
  saved-object index scope, while SOC indices stay read-only for the analyst.
- OpenSearch CA material is only `ca.crt` extracted from `soc-http-cert`; no server
  private key is copied to Kafka. Pipeline installation copies this **public CA**
  and the indexer credential to `kafka`. Repeat pipeline installation following
  CA/credential rotation; mounts/Secret env are not a cross-namespace auto-sync.
- Bootstrap/testing port-forward binds 127.0.0.1. Its Python client verifies the
  CA chain, but disables hostname checking **only for the loopback tunnel**, whose
  address is not the service SAN. Vector verifies both CA and hostname normally.
- Dashboards is reachable at `http://dashboards.192.168.150.200.sslip.io` through
  Traefik. The HTTP Ingress and insecure cookie flag are lab-only: credentials
  travel in cleartext on the ingress segment until cert-manager TLS is added.
- Optional OpenSearch operator admission webhooks are disabled because they
  default to cert-manager and P4 cannot assume it exists. The operator's core
  reconciliation and TLS generation do not depend on that optional webhook.
- Do not edit reserved demo users/roles through REST: those endpoints reject it.
  If adjusting security authentication backends manually, run securityadmin with
  **`-f config.yml -t config`**, not `-cd <whole-directory>` on an established
  cluster. A full-directory import can erase REST-created users/roles/mappings.
  The operator initializes its generated security config; rerun `configure.sh`
  after intentional security-config/admin-password changes that reapply defaults.
- `general.setVMMaxMapCount: false` and `node.store.allow_mmap: false` avoid the
  operator's privileged sysctl mutation entirely. This trades mmap performance
  for compliance with the no-host-sysctl rule; only the PVC chown init runs root.

## Data contracts and retention

Zeek writes one JSON record per line to `/var/log/zeek/current/{conn,dns,http,notice,intel}.log`.
The Vector Zeek agent reads the directory read-only and uses a separate persistent
host buffer at `/var/lib/vector-soc/zeek`. It derives log_type from the basename,
adds node/sensor, renames **scalar** `id` → `zeek_id`, and normalizes dotted Zeek
`id.orig_h`/`id.resp_h`/ports to a nested `id` object. Missing or invalid JSON/ts
records are dropped with Vector errors; unknown log types such as files/ssl are
intentionally dropped, never sent to a nonexistent `zeek-other` topic.

Audit agents run only on `node-role.kubernetes.io/control-plane=true`, tail the
k3s audit path read-only, and remove requestObject/responseObject when objectRef
resource is `secrets`, before encoding the event. Metadata audit policy remains
the primary protection; this guard is defense in depth, not full DLP.

All Vector roles live in `kafka`. Their Kubernetes API service-account tokens are
disabled. Agents run UID 0 only to read host logs/write host buffers; all Linux
capabilities are dropped and no privileged or hostNetwork setting is used. The
indexer runs UID/fsGroup 1000 against its PVC. Liveness/readiness use the internal
Vector API health endpoint; this is process health, not guaranteed sink delivery.

The indexer reads all seven topics, uses source-owned Kafka topic metadata, and
routes to seven literal-prefix bulk sinks. Indices are `<topic>-YYYY.MM.dd` using
Vector's event timestamp/Kafka timestamp (UTC), falling back to ingestion time.
Literal prefixes avoid Vector 0.59's template confinement rejection without the
unsafe `dangerously_allow_unconfined_template_resolution` opt-out. OpenSearch
uses the compatible v7 bulk protocol, no type metadata, and retries partial bulk
failures. End-to-end acknowledgements are enabled: Vector stores Kafka offsets
only after successful sink delivery; its normal periodic auto-commit remains
on and automatic offset-store remains off. There is no forced offset commit
before OpenSearch receives the record.

Templates map Zeek ts as epoch_second, @timestamp as date, addresses as IP, scalar
zeek_id/strings as keyword; date_detection is off so unlisted strings remain
keyword. Audit and Falco templates also use one primary shard and one replica.
`soc-retention` ISM transitions hot → retained at index age 1d → delete at age 3d.
This is **index creation age**, not event age; ISM execution is asynchronous.
ISM templates attach to newly created matching indices. Existing indices created
before bootstrap need an explicit ISM add operation. Run OpenSearch install
before the indexer to avoid missing templates/retention.

## Static validation and evidence

```bash
cd /data/k8s-lab
python3 soc/pipeline/validate-static.py
```

The validation program is offline with respect to Kubernetes (it does retrieve
upstream JSON schemas if not cached). It renders both pinned Helm charts, validates
all resources with kubeconform strict plus the requested datree catalog, augments
missing schemas with actual pinned-release CRD schemas, compiles/tests the three
Vector configs using the checksum-verified static binary, checks shell/Python/JSON
syntax and asserts resource/security/topic contracts. It never changes authored configs or contacts the Kubernetes API. After editing
standalone configs, explicitly run `python3 soc/pipeline/render-configmaps.py`
to update ConfigMap data and hashes before validating.

Evidence is in `evidence/p4-prep-a/`: command exit codes, rendered manifests,
upstream release/index/image metadata, official plugin build manifest, Vector
unit outputs and `09-static-summary.json`. With release schemas: **72 resources,
52 valid, 0 invalid/errors, 20 skipped**. The skipped items are upstream CRD
**definitions**, for which kubeconform's default catalog has no meta-schema;
all 14 authored custom resources are validated against their pinned CRD schemas.
The ordinary default+datree pass alone leaves the new OpenSearchCluster schema
unavailable (21 skipped). Fourteen Vector regression tests passed. Real file-tail → remap → console tests also
passed for Zeek and audit, including Secret-object redaction (no network/cluster). The unmatched
route warning is expected; upstream topic whitelist makes that output unreachable.

**Not verified in this phase:** scheduling/PVC permissions, JVM RSS or throughput,
cluster formation, actual Kafka authentication/ACL rejection, operator/plugin
runtime behavior, ingress reachability, or per-topic indexed document counts.
`tests/phase-p4-a.sh` supplies these runtime gates for deployment, not fabricated
results. High-risk first-run points are JVM memory pressure (especially bootstrap),
local-path disk/placement, actual host log permissions, and quiet notice/intel topics.
