> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

# Traffic

Deterministic Scapy PCAPs and isolated veth replay. Live normal/beacon traffic targets only a lab DNS+HTTP service; optional scans require a single IPv4 lab target.

See `soc/README-B.md` for ordered install, budgets, security risks and integration contracts.
Run `bash soc/traffic/install.sh` only after the cluster and prerequisite services exist. Run `bash soc/traffic/test.sh` for acceptance; it exits nonzero on failure. Versions and digests are in `VERSIONS`.
