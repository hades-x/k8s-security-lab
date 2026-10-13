> Publication candidate: adapted from the October 13, 2026 lab snapshot. Historical PASS statements below are not current health or fresh-clone reproduction. Raw evidence, caches and original trust roots are not distributed. See `tools/DEPENDENCIES.md` from the repository root.

Longhorn 1.13.0, v1 engine, replica count 2, non-default StorageClass.
K3s local-path remains the default.
VM cloud-init installs open-iscsi and nfs-common; no host packages changed.
Run `./install.sh`; `./test.sh` proves write/delete/read persistence.
Namespace limits bound dynamically created storage containers.
Namespace defaults cover Helm jobs/sidecars as well.
