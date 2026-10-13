> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Signed orders demo

Three independently deployed processes share one pinned immutable Python image:
`orders-api` validates orders, commits PostgreSQL rows and publishes to Kafka;
`orders-worker` consumes the shared topic using a per-environment consumer group,
filters by environment and caches orders in Valkey; `web` serves a status page and
same-origin API proxy. TLS+SCRAM protects Kafka; PostgreSQL uses TLS.

Unit tests: `python -m unittest discover -s tests -v`.
End-to-end tests: run `/data/k8s-lab/tests/phase-p6.sh` on the lab controller.

Lab limitations: single-instance databases, ephemeral 24h cache, no HTTP auth,
and no transactional outbox: a Kafka publish failure returns 503 after the row
is committed. Do not model exactly-once business transactions on this example.
Use only synthetic orders; this is not production-ready.
