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
python3 - <<'PY'
import subprocess,xml.etree.ElementTree as ET,tempfile,os,pathlib
root=pathlib.Path('/data/k8s-lab')
xml=ET.fromstring(subprocess.check_output(['virsh','-c','qemu:///system','net-dumpxml','k8slab']))
assert xml.find('bridge').get('name')=='virbr-k8slab'
assert xml.find('forward').attrib=={'mode':'nat','dev':'REPLACE_WITH_LAB_UPLINK'}
assert xml.find('ip').get('address')=='192.168.150.1'
assert len(xml.findall('ip/dhcp/host'))==5
for name,ram,disk in [('lab-s1',8192,40),('lab-s2',8192,40),('lab-s3',8192,40),('lab-a1',10240,60),('lab-a2',10240,60)]:
 d=ET.fromstring(subprocess.check_output(['virsh','-c','qemu:///system','dumpxml',name]))
 assert int(d.find('memory').text)==ram*1024
 assert int(d.find('vcpu').text)==6
 assert d.find('devices/interface/source').get('network')=='k8slab'
 assert all((src.get('file','').startswith('/data/k8s-lab/vms/')) for src in d.findall('devices/disk/source'))
 print(f'PASS: {name} memory={ram}MiB vCPU=6 disks under /data/k8s-lab/vms')
print('PASS: k8slab NAT restricted to REPLACE_WITH_LAB_UPLINK, expected bridge/subnet/static DHCP')
with tempfile.TemporaryDirectory(dir=root/'vms',prefix='guard-test-') as temp:
 df=pathlib.Path(temp)/'df';df.write_text('#!/bin/sh\nprintf "Avail\\n1024\\n"\n');df.chmod(0o755)
 p=subprocess.run([str(root/'infra/libvirt/guard.sh')],env={**os.environ,'PATH':temp+':'+os.environ['PATH']},capture_output=True,text=True)
 assert p.returncode!=0
 assert 'less than 30 GiB' in p.stderr
 print('PASS: low-free-space guard refuses create/start (isolated df probe)')
p=subprocess.run([str(root/'infra/libvirt/down.sh'),'unrelated-workload-forbidden-probe'],capture_output=True,text=True)
assert p.returncode!=0 and 'REFUSED' in p.stderr
print('PASS: down.sh refuses non-k8slab name before invoking virsh')
PY
