#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source /data/k8s-lab/infra/k3s/env.sh
cd "$ROOT"
infra/libvirt/guard.sh
mkdir -p vms/base vms/seeds vms/disks .secrets evidence/p1
chmod 755 vms vms/base vms/seeds vms/disks
chmod 700 .secrets
if [[ ! -f .secrets/lab_ed25519 ]]; then ssh-keygen -q -t ed25519 -N '' -f .secrets/lab_ed25519; fi
chmod 600 .secrets/lab_ed25519
if ! virsh -c qemu:///system net-info k8slab >/dev/null 2>&1; then
  { ip -4 route; for n in $(virsh -c qemu:///system net-list --all --name); do virsh -c qemu:///system net-dumpxml "$n"; done; } >evidence/p1/00-network-preflight.txt
  python3 - <<'PY'
import ipaddress,subprocess,xml.etree.ElementTree as ET
candidate=ipaddress.ip_network('192.168.150.0/24')
for line in subprocess.check_output(['ip','-4','route'],text=True).splitlines():
 token=line.split()[0]
 if token=='default':continue
 try: net=ipaddress.ip_network(token,strict=False)
 except ValueError:continue
 if candidate.overlaps(net):raise SystemExit('REFUSED: overlapping host route '+line)
for name in subprocess.check_output(['virsh','-c','qemu:///system','net-list','--all','--name'],text=True).split():
 xml=ET.fromstring(subprocess.check_output(['virsh','-c','qemu:///system','net-dumpxml',name]))
 for ip in xml.findall('ip'):
  if ip.get('family','ipv4')!='ipv4':continue
  net=ipaddress.ip_network(ip.get('address')+'/'+(ip.get('prefix') or ip.get('netmask') or '32'),strict=False)
  if candidate.overlaps(net):raise SystemExit('REFUSED: overlapping libvirt network '+name)
print('Subnet overlap checks PASS')
PY
  virsh -c qemu:///system net-define infra/libvirt/network.xml
fi
virsh -c qemu:///system net-autostart k8slab
if ! virsh -c qemu:///system net-info k8slab | grep 'Active:.*yes' >/dev/null; then virsh -c qemu:///system net-start k8slab; fi
image=noble-server-cloudimg-amd64.img
if [[ ! -f vms/base/$image ]]; then curl -fL --retry 2 https://cloud-images.ubuntu.com/noble/current/$image -o vms/base/$image; fi
if [[ ! -f vms/base/SHA256SUMS ]]; then curl -fsSL https://cloud-images.ubuntu.com/noble/current/SHA256SUMS -o vms/base/SHA256SUMS; fi
(cd vms/base; grep "[ *]$image$" SHA256SUMS | sha256sum -c -) | tee evidence/p1/01-image-sha256.txt
cp vms/base/SHA256SUMS infra/libvirt/ubuntu-SHA256SUMS
os=ubuntu22.04
if osinfo-query os | grep -q ubuntu24.04; then os=ubuntu24.04; fi
pub=$(cat .secrets/lab_ed25519.pub)
for suffix in s1 s2 s3 a1 a2; do
 name=lab-$suffix; ip=$(node_ip "$name"); last=${ip##*.}; mac=52:54:00:15:00:$last
 if [[ $suffix == s* ]]; then ram=10240; disk=40; else ram=10240; disk=60; fi
 if ! virsh -c qemu:///system dominfo "$name" >/dev/null 2>&1; then
  [[ -f vms/disks/$name.qcow2 ]] || qemu-img create -f qcow2 -F qcow2 -b "$ROOT/vms/base/$image" "vms/disks/$name.qcow2" "${disk}G"
  cat >"vms/seeds/$name-user.yaml" <<EOF
#cloud-config
hostname: $name
manage_etc_hosts: true
users:
  - name: lab
    groups: [sudo]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
    ssh_authorized_keys:
      - $pub
ssh_pwauth: false
disable_root: true
package_update: true
packages: [qemu-guest-agent, chrony, open-iscsi, nfs-common]
bootcmd:
  - [swapoff, -a]
runcmd:
  - [systemctl, enable, --now, qemu-guest-agent]
  - [systemctl, enable, --now, chrony]
  - [systemctl, enable, --now, iscsid]
  - [sh, -c, "swapoff -a; sed -i '/swap/d' /etc/fstab"]
EOF
  printf 'instance-id: %s
local-hostname: %s
' "$name" "$name" >"vms/seeds/$name-meta.yaml"
  cat >"vms/seeds/$name-network.yaml" <<EOF
version: 2
ethernets:
  eth0:
    match: {macaddress: '$mac'}
    set-name: eth0
    dhcp4: true
    dhcp6: false
EOF
  cloud-localds --network-config="vms/seeds/$name-network.yaml" "vms/seeds/$name.iso" "vms/seeds/$name-user.yaml" "vms/seeds/$name-meta.yaml"
  infra/libvirt/guard.sh
  virt-install --connect qemu:///system --name "$name" --memory "$ram" --vcpus 6 --cpu host-passthrough --os-variant "$os" --import --disk path="$ROOT/vms/disks/$name.qcow2",bus=virtio,format=qcow2,cache=none,discard=unmap --disk path="$ROOT/vms/seeds/$name.iso",device=cdrom --network network=k8slab,model=virtio,mac="$mac" --graphics none --noautoconsole --rng /dev/urandom
 else
  if [[ $(virsh -c qemu:///system domstate "$name") != running ]]; then infra/libvirt/guard.sh; virsh -c qemu:///system start "$name"; fi
 fi
 virsh -c qemu:///system autostart --disable "$name"  # D12: never autostart a large lab beside unrelated workloads; operator capacity review is required
done
virsh -c qemu:///system net-dumpxml k8slab >evidence/p1/02-network.xml
virsh -c qemu:///system list --all >evidence/p1/03-domains.txt
for suffix in s1 s2 s3 a1 a2; do
 node=lab-$suffix
 for i in {1..100}; do if scripts/ssh-node.sh "$node" true 2>/dev/null; then break; fi; sleep 3; done
 scripts/ssh-node.sh "$node" 'export LC_ALL=C; sudo cloud-init status --wait; ip -4 addr show eth0; free -h; swapon --show; systemctl is-active chrony qemu-guest-agent iscsid'
done
