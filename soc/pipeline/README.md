> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Vector SOC data plane

Pinned Vector 0.59.0 image by digest, statically tested with the checksum-verified
musl binary under `bin/vector` (no Docker). All roles are in namespace kafka.

- vector-zeek DaemonSet: `/var/log/zeek/current/*.log`, JSON parsing, node/sensor,
  basename topic routing, scalar id rename, dotted-IP normalization, 256Mi disk buffer.
  Only conn/dns/http/notice/intel are retained. Unknown types intentionally drop.
- vector-audit DaemonSet: only control-plane=true nodes, k3s audit.log,
  Secret request/response redaction, independent SCRAM credential and disk buffer.
- vector-indexer Deployment: seven topics, exact group soc-indexer, compatible
  OpenSearch bulk, seven topic/day sinks and bounded PVC buffers; acks propagate
  to Kafka offset storage only after delivery. At-least-once, possible duplicates.

Install last: `bash soc/pipeline/install.sh`. Agents tolerate control-plane taints
but use root only for hostPath log/buffer ownership. Indexer runs UID/fsGroup 1000.
Re-run installation after CA/credential rotation; it copies only the public
OpenSearch CA and restarts Secret-env consumers. Kafka CA is mounted directly from
soc-cluster-ca-cert, never the signing-key Secret. See `../README-A.md` for limits.

Run `python3 soc/pipeline/validate-static.py` to render/check/test without a cluster.
After edits, run `python3 soc/pipeline/render-configmaps.py` to sync standalone
`config/` YAML and ConfigMap data, with config hash annotations for rollouts.
`python3 soc/pipeline/test-offline.py` additionally exercises actual file tails
using local fixtures and console sinks, never Kafka/OpenSearch or host networking. `test.sh` is a deployed readiness check;
`tests/phase-p4-a.sh` is the data/security acceptance gate after sensors flow.
