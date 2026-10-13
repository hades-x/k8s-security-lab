> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Deployed SOC training chain (P4)

This stack is a disposable, defensive interview-preparation lab, not a production
security deployment. Historical offline preparation is documented in `README-A.md`
and `README-B.md`. Runtime evidence and deviations are in
`../evidence/p4/worker-report.md`.

## Topology and pins

- Strimzi 1.3.0 / Kafka 4.3.1: three combined KRaft controller/brokers, TLS and
  SCRAM-SHA-512 only, seven RF=3 topics, least-privilege producer/consumer ACLs.
- OpenSearch operator 3.0.0 (chart 3.0.14), OpenSearch and Dashboards 3.9.0:
  three nodes, authenticated HTTPS backend, generated CA, local-path storage.
- Vector 0.59.0: five Zeek shippers, three audit shippers, one acknowledged indexer.
- Zeek 9.0.0: two sensors per node on **eth0** and the isolated **zeektap0** veth.
- MISP 2.5.50: four synthetic IoCs, an exporter and five-minute refresh CronJob.
- Falco 0.45.0 modern eBPF and Falcosidekick 2.35.0: Kafka `falco-alerts` output.
- Seventeen experimental Sigma rules imported as Security Analytics custom rules.
  The deployed detection mechanism is **17 enabled OpenSearch Alerting query-level
  monitors**, with no external notification actions. Native detector creation
  returned HTTP 500 on both wildcard and concrete-index attempts.

The pipeline lives in `kafka`; other owned namespaces are `opensearch`,
`soc-sensors`, `soc-traffic`, `misp`, `falco`, and `soc-detection` (guarded triggers).
Only `soc-sensors` and `falco` have the documented privileged PSS exemptions.
Restrictive namespace PSS labels from the preparation were removed; enforcement
and Kyverno are deliberately deferred.

## Install / verify

On lab controller:

```bash
export LC_ALL=C
cd /data/k8s-lab
source infra/k3s/env.sh
bash soc/kafka/install.sh
bash soc/opensearch/install.sh
bash soc/pipeline/install.sh
NODE_INTERFACE=eth0 bash soc/zeek/install.sh
bash soc/traffic/install.sh
bash soc/misp/install.sh
bash soc/misp/bootstrap.sh
bash soc/falco/install.sh
# Preserve native custom-rule provenance, even though native detectors failed.
python3 soc/detection/install-security-analytics.py --rules-only
python3 soc/detection/install-alerting.py
python3 soc/opensearch/dashboards/import.py
bash tests/phase-p4.sh
# Read-only Kubernetes health and retained evidence, not fresh attack simulation:
bash tests/phase-p4.sh --read-only
```

Generated credentials remain exclusively in private `.secrets/` files and Kubernetes
Secrets. Do not copy their values into evidence or command arguments. The analyst
account is `soc-analyst`; use its private generated password file for access.

- Dashboards: `http://dashboards.192.168.150.200.sslip.io`, global tenant,
  dashboard **SOC overview**. Six panel aggregations are also checked against real
  data by `soc/opensearch/acceptance.py`.
- MISP: `http://misp.192.168.150.200.sslip.io`, lab-only HTTP.
- Backend OpenSearch and Kafka are not publicly exposed.

## Acceptance side effects

Default P4 acceptance performs guarded, benign in-lab triggers. It briefly pauses
and restores the indexer for the authenticated Kafka round trip and ACL denial.
MISP bootstrap explicitly rolls Zeek to load the exported Intel table before replay.
The 328-packet pcap is transmitted only on `zeektap0-in`, using OTHERHOST destination
MACs; no IP address or route is assigned to the test veth.

The drain benchmark is a **controlled quiet-window test**, not a zero-lag claim
under continuous ingestion. Pausing only the two traffic generators did not drain
ongoing audit/Falco traffic. The benchmark therefore briefly quiesces the two Vector
shipper DaemonSets and Falcosidekick as well, observes the committed group offsets,
and restores all selectors/replica counts with read-back and readiness checks on
both success and failure. Zeek keeps writing host logs and audit files keep growing
for subsequent shipper catch-up. Falco HTTP events during the receiver pause may be
missed: this deliberate test window is not a lossless-production guarantee.

## Runtime fixes and boundaries

- Vector 0.59 requires explicit environment-variable interpolation opt-in. Its
  process-health endpoint does not prove Kafka/SCRAM or OpenSearch authentication.
- The OpenSearch CR `RUNNING` phase can precede child creation. Its OnDelete
  StatefulSet must be checked with `readyReplicas`, not `rollout status`.
- Arbitrary non-secret Kubernetes audit request/response bodies are archived as
  JSON strings to avoid dotted-label / FieldsV1 mapping conflicts. Secret bodies
  are removed by both the shipper and indexer. Metadata fields remain queryable.
- Zeek imports use explicit `.zeek` filenames and `set(...)` syntax; the actual
  pinned compiler is exercised by `soc/zeek/check-syntax.sh`. Notice suppression
  is zero for deterministic lab triggers, not a production noise-control setting.
- Falco config-file watching is disabled after inotify initialization failed on
  one node. Apply rule changes with a rollout; no sysctl was changed.
- Manual Kafka partition proof readers have no `group.id`, disable auto-commit,
  snapshot latest offsets, and use a wall-clock timeout. They never join or steal
  partitions from the live indexer group.
- The Kubernetes exec rule covers both POST/create and GET/WebSocket streaming.
- An anonymous API attempt is rejected, but no matching audit event was observed.
  This one negative rule must be reported honestly; authentication is not weakened.
- Initial pre-fix audit mapping rejections were not backfilled. Delivery is
  at-least-once, not exactly-once; historical loss/duplicates are not ruled out.
- First Intel-table reload via rolling restart is tested. Seamless projected-file
  hot reload, indicator revocation, long-duration expiry, failure recovery, SSO,
  ingress TLS, backups/restores, browser-rendered panels, and production sizing
  are not acceptance claims in this phase.
