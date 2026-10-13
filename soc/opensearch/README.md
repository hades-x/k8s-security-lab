> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# OpenSearch SOC indices and analyst UI

Pinned operator chart 3.0.14 (app 3.0.0), OpenSearch/Dashboards 3.9.0, v1 API group
opensearch.org. Three combined cluster_manager/data/ingest nodes, 2Gi/1g heap each,
20Gi local-path PVCs, and one 768Mi-limit Dashboards replica. The operator does
not support the single-node alternative. No host sysctl changes: mmap is disabled.

Security, Security Analytics, Alerting and ISM are in the official distribution;
`evidence/p4-prep-a/upstream/opensearch-build-3.9.0.yml` and release notes verify
these components without executing Docker. `configure.py` additionally verifies
actual runtime plugin names through `_cat/plugins` before bootstrapping.

Install with `bash soc/opensearch/install.sh`. Password generation is install-time,
never shown, chmod 600 in `.secrets/`. Secrets are rendered with kubectl dry-run
piped directly to apply; no credential manifests in Git. `api/` holds templates,
ISM policy and role definitions (no passwords). `configure.py` performs idempotent
REST updates and reads back each exact target. `test.sh` validates 401/200 and
3-node green/yellow; `SOC_REQUIRE_DATA=1` requires all seven topic indices >0 docs.

Do not modify reserved demo users/roles through REST; do not use a whole-directory
securityadmin import after REST bootstrapping. Apply only `-f config.yml -t config`
for an authentication backend change, then reconcile controlled users as needed.
Read `../README-A.md` for HTTP ingress caveats and other known pitfalls.
