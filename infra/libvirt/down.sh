#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
export LC_ALL=C
for name in "$@"; do [[ $name =~ ^lab-(s[1-3]|a[1-2])$ ]] || { echo "REFUSED: $name" >&2; exit 1; }; done
names=("$@")
((${#names[@]}>0)) || { echo "REFUSED: explicitly name the disposable lab domains; no discovery-based cleanup" >&2; exit 2; }
for name in "${names[@]}"; do
 [[ $name =~ ^lab-(s[1-3]|a[1-2])$ ]] || exit 1
 if [[ $(virsh -c qemu:///system domstate "$name") == running ]]; then virsh -c qemu:///system destroy "$name"; fi
 virsh -c qemu:///system undefine "$name"
done
if (($#==0)) && virsh -c qemu:///system net-info k8slab >/dev/null 2>&1; then
 if virsh -c qemu:///system net-info k8slab | grep 'Active:.*yes' >/dev/null; then virsh -c qemu:///system net-destroy k8slab; fi
 virsh -c qemu:///system net-undefine k8slab
fi
# Disks/seeds retained; deletion requires a separate explicit decision.
