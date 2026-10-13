> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

Native-routing Cilium replaces kube-proxy and enables Hubble.
Current stable chart is resolved once and pinned in VERSIONS.
Run `./install.sh`; verify `./test.sh`.
No overlay: cross-node packets carry real pod IPs on eth0.
