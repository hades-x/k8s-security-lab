> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Zeek

Two JSON sensors per node and a single checkpointed log merger. NIC default enp1s0; override NODE_INTERFACE. Namespace PSS exempt; no fully privileged container.

See `soc/README-B.md` for ordered install, budgets, security risks and integration contracts.
Run `bash soc/zeek/install.sh` only after the cluster and prerequisite services exist. Run `bash soc/zeek/test.sh` for acceptance; it exits nonzero on failure. Versions and digests are in `VERSIONS`.
