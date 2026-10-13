#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# Memory remediation after control-plane OOM spiral (13/10 ~14:00):
#  - servers 8 -> 10 GiB (VM config, needs power cycle)
#  - kubelet reservations + eviction thresholds so the kubelet evicts pods before the kernel OOM-kills k3s/etcd
#  - inotify limits raised inside the (disposable) guests
# Only touches lab-* domains. Idempotent.
set -euo pipefail
export LC_ALL=C
cd "$(dirname "$0")/../.."
URI=qemu:///system
SERVERS=(lab-s1 lab-s2 lab-s3)
AGENTS=(lab-a1 lab-a2)
SERVER_MEM_KIB=$((10 * 1024 * 1024))
SSH() { timeout 60 scripts/ssh-node.sh "$@"; }

guest_patch() { # $1 node  $2 service
  SSH "$1" "sudo python3 - <<'EOF'
import re
p='/etc/rancher/k3s/config.yaml'; s=open(p).read()
args=['system-reserved=cpu=500m,memory=768Mi','kube-reserved=cpu=500m,memory=512Mi',
      'eviction-hard=memory.available<500Mi,nodefs.available<10%','eviction-soft=memory.available<1Gi',
      'eviction-soft-grace-period=memory.available=1m30s','eviction-max-pod-grace-period=30']
for a in args:
    key=a.split('=')[0]
    if '- '+key+'=' not in s:
        s=s.replace('kubelet-arg:\n','kubelet-arg:\n  - '+a+'\n',1)
open(p,'w').write(s)
EOF
printf 'fs.inotify.max_user_instances=1024\nfs.inotify.max_user_watches=1048576\n' | sudo tee /etc/sysctl.d/90-lab-inotify.conf >/dev/null
sudo sysctl -q --system"
}

[[ "$(df -BG --output=avail /data | tail -1 | tr -dc 0-9)" -ge 30 ]] || { echo "disk guard: <30G free on /data"; exit 1; }

# 1. servers: patch what we can reach, then power-cycle all three together with more RAM
for n in "${SERVERS[@]}"; do guest_patch "$n" k3s && echo "patched $n" || echo "WARN: could not patch $n now (will retry after boot)"; done
for n in "${SERVERS[@]}"; do virsh -c $URI shutdown "$n" >/dev/null || true; done
for i in $(seq 1 24); do
  left=0; for n in "${SERVERS[@]}"; do [[ $(virsh -c $URI domstate "$n") == "shut off" ]] || left=$((left+1)); done
  (( left == 0 )) && break; sleep 5
done
for n in "${SERVERS[@]}"; do
  [[ $(virsh -c $URI domstate "$n") == "shut off" ]] || { echo "force power-off $n (lab VM)"; virsh -c $URI destroy "$n" >/dev/null; }
  virsh -c $URI setmaxmem "$n" $SERVER_MEM_KIB --config
  virsh -c $URI setmem "$n" $SERVER_MEM_KIB --config
done
for n in "${SERVERS[@]}"; do virsh -c $URI start "$n" >/dev/null; done
for n in "${SERVERS[@]}"; do
  for i in $(seq 1 40); do SSH "$n" true 2>/dev/null && break; sleep 5; done
  guest_patch "$n" k3s; SSH "$n" "sudo systemctl restart k3s" || true
done
# 2. agents: patch + restart k3s-agent one at a time (no reboot needed)
for n in "${AGENTS[@]}"; do guest_patch "$n" k3s-agent; SSH "$n" "sudo systemctl restart k3s-agent"; sleep 20; done
for n in "${SERVERS[@]}" "${AGENTS[@]}"; do echo "$n $(virsh -c $URI dominfo $n | awk '/Max memory/{print $3/1048576 " GiB"}')"; done
