> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

Isolated 192.168.150.0/24 NAT network and five Ubuntu Noble VMs.
Run `./up.sh`; verify `virsh -c qemu:///system list --all`.
All disks and seeds are under `/data/k8s-lab/vms`; official SHA256SUMS checked.
`guard.sh` refuses create/start below 30 GiB free on /data.
`down.sh` removes only k8slab domains/network; disks retained.
Ubuntu 22.04 osinfo hardware profile is used if Noble is unavailable.
