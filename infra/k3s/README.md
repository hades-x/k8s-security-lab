> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

Pinned k3s HA embedded-etcd, audit logging and ARP API VIP.
Run `./install.sh` after libvirt up.
Kube-vip static pods use the local API to avoid VIP bootstrap cycles.
Credentials remain in `.secrets`, mode 600.
Verify with `../../tests/phase-p1.sh`.
Installer sourced from the immutable k3s release and SHA256 checked.
