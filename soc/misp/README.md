> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Misp

Official core plus separate nginx, MariaDB and Valkey, local-path PVCs, generated credentials and fixture-testable Intel exporter.

See `soc/README-B.md` for ordered install, budgets, security risks and integration contracts.
Run `bash soc/misp/install.sh` only after the cluster and prerequisite services exist. Run `bash soc/misp/test.sh` for acceptance; it exits nonzero on failure. Versions and digests are in `VERSIONS`.
