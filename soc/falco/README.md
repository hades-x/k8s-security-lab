> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Falco

Pinned modern-eBPF Falco and separate Falcosidekick release, four standalone rules, TLS+SCRAM Kafka producer and authenticated manual-partition acceptance reader.

See `soc/README-B.md` for ordered install, budgets, security risks and integration contracts.
Run `bash soc/falco/install.sh` only after the cluster and prerequisite services exist. Run `bash soc/falco/test.sh` for acceptance; it exits nonzero on failure. Versions and digests are in `VERSIONS`.
