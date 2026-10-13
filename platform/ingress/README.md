> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

Traefik bundled with k3s uses Cilium LB-IPAM/L2 at 192.168.150.200.
Gateway API standard CRDs pinned to v1.6.3.
Run `./install.sh`; after GitOps demo sync apply `gateway.yaml`.
Hostnames use sslip.io; curl --resolve works without host DNS changes.
Hubble UI is at hubble.192.168.150.200.sslip.io.
Verify `./test.sh`.
