#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# Lab-only I/O tuning: all lab-* disks to cache=unsafe (guest fsync not forwarded to the host),
# discard=unmap (thin qcow2 gives space back). Rationale: 5 VMs on one NVMe running etcd + OpenSearch +
# Kafka + Longhorn produced etcd "slow disk" heartbeats and IO-wait > 45 %. Data-loss risk only on a HOST
# crash, acceptable for a disposable lab (documented in DECISIONS.md). Touches only lab-* domains.
set -euo pipefail
[[ ${LAB_ALLOW_UNSAFE_DISK_CACHE:-} == yes ]] || { echo "BLOCKED: unsafe cache discards fsync durability; separate consent required" >&2; exit 2; }
export LC_ALL=C
URI=qemu:///system
VMS=(lab-a1 lab-a2 lab-s1 lab-s2 lab-s3)
for n in "${VMS[@]}"; do [[ $n =~ ^lab- ]] || exit 1; virsh -c $URI shutdown "$n" >/dev/null 2>&1 || true; done
for i in $(seq 1 30); do
  left=0; for n in "${VMS[@]}"; do [[ $(virsh -c $URI domstate "$n") == "shut off" ]] || left=$((left+1)); done
  (( left == 0 )) && break; sleep 5
done
for n in "${VMS[@]}"; do
  [[ $(virsh -c $URI domstate "$n") == "shut off" ]] || { echo "force power-off $n (lab VM)"; virsh -c $URI destroy "$n" >/dev/null; }
  virt-xml --connect $URI "$n" --edit all --disk cache=unsafe,discard=unmap >/dev/null
  echo "$n: $(virsh -c $URI dumpxml "$n" --inactive | grep -o "<driver name='qemu'[^>]*>" | head -1)"
done
# servers first so etcd regains quorum, then agents
for n in lab-s1 lab-s2 lab-s3; do virsh -c $URI start "$n" >/dev/null; done
sleep 30
for n in lab-a1 lab-a2; do virsh -c $URI start "$n" >/dev/null; done
virsh -c $URI list | grep k8slab
