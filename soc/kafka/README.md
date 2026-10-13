> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Kafka SOC bus

Pinned Strimzi Helm chart 1.3.0 and Kafka 4.3.1. `cluster.yaml` uses v1 CRDs and
three combined broker/controller KafkaNodePool nodes (KRaft); no ZooKeeper.
3 × 768m heap / 1536Mi memory limit, 10Gi local-path PVCs and hard host anti-affinity.

`topics.yaml` defines seven 3-partition/RF3/minISR2 topics. `users.yaml` defines
SCRAM writers, the exact-group read-only indexer, and byte/request quotas. Every
Vector producer uses TLS, SCRAM and acks=all, with idempotence explicitly off.

Run `bash soc/kafka/install.sh` after cluster creation, then `bash soc/kafka/test.sh`.
The full TLS roundtrip/negative ACL proof is in `tests/phase-p4-a.sh` and its
transient client files. See `../README-A.md` for CA/Secret handling, ordered install,
resource/storage caveats and static evidence. Never print KafkaUser passwords.
