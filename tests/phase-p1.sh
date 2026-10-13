#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source /data/k8s-lab/infra/k3s/env.sh
cd "$ROOT"
mkdir -p evidence/p1
exec > >(tee evidence/p1/10-acceptance.txt) 2>&1
kubectl wait nodes --all --for=condition=Ready --timeout=300s
kubectl get nodes -o wide
kubectl get nodes -o json >evidence/p1/11-nodes.json
python3 - <<'PY'
import json
nodes=json.load(open('evidence/p1/11-nodes.json'))['items']
assert len(nodes)==5
assert sum('node-role.kubernetes.io/control-plane' in n['metadata']['labels'] for n in nodes)==3
assert sum('node-role.kubernetes.io/etcd' in n['metadata']['labels'] for n in nodes)==3
assert all(any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions']) for n in nodes)
print('PASS: 5 Ready nodes, 3 control-plane, 3 etcd nodes')
PY
kubectl get --raw '/readyz?verbose' | tee evidence/p1/12-readyz.txt
grep '\[+\]etcd ok' evidence/p1/12-readyz.txt
scripts/ssh-node.sh lab-s2 'sudo k3s secrets-encrypt status' | tee evidence/p1/13-encryption.txt
grep 'Encryption Status: Enabled' evidence/p1/13-encryption.txt
# Download a pinned compatible diagnostic etcdctl and verify the release checksum.
if [[ ! -x vms/downloads/etcd-v3.6.6-linux-amd64/etcdctl ]]; then
 curl -fsSL https://github.com/etcd-io/etcd/releases/download/v3.6.6/etcd-v3.6.6-linux-amd64.tar.gz -o vms/downloads/etcd-v3.6.6-linux-amd64.tar.gz
 curl -fsSL https://github.com/etcd-io/etcd/releases/download/v3.6.6/SHA256SUMS -o vms/downloads/etcd-SHA256SUMS
 (cd vms/downloads; grep 'etcd-v3.6.6-linux-amd64.tar.gz$' etcd-SHA256SUMS | sha256sum -c -)
 tar -C vms/downloads -xzf vms/downloads/etcd-v3.6.6-linux-amd64.tar.gz
fi
"${SCP[@]}" vms/downloads/etcd-v3.6.6-linux-amd64/etcdctl lab@192.168.150.12:/home/lab/etcdctl
etcd="sudo /home/lab/etcdctl --endpoints=https://127.0.0.1:2379 --cacert=/var/lib/rancher/k3s/server/tls/etcd/server-ca.crt --cert=/var/lib/rancher/k3s/server/tls/etcd/server-client.crt --key=/var/lib/rancher/k3s/server/tls/etcd/server-client.key"
scripts/ssh-node.sh lab-s2 "$etcd endpoint health --cluster; $etcd member list -w table; $etcd member list -w json" | tee evidence/p1/14-etcd.txt
scripts/ssh-node.sh lab-s2 "$etcd member list -w json" >evidence/p1/15-etcd-members.json
python3 - <<'PY'
import json
assert len(json.load(open('evidence/p1/15-etcd-members.json'))['members'])==3
print('PASS: 3 embedded-etcd members')
PY
for suffix in s1 s2 s3; do
 node=lab-$suffix
 kubectl get nodes >/dev/null
 scripts/ssh-node.sh "$node" 'sudo test -s /var/lib/rancher/k3s/server/logs/audit.log; sudo stat -c "audit.log: %s bytes, modified %y" /var/lib/rancher/k3s/server/logs/audit.log'
done | tee evidence/p1/16-audit.txt
cilium status --wait --wait-duration 5m | tee evidence/p1/17-cilium.txt
# Identify the ARP VIP leader and make s1 the leader before testing its reboot.
leader=$(kubectl -n kube-system get lease plndr-cp-lock -o jsonpath='{.spec.holderIdentity}')
printf 'API VIP leader before test: %s\n' "$leader"
if [[ $leader != lab-s1* ]]; then
 restore_vip_candidates() {
  for node in lab-s2 lab-s3; do
   scripts/ssh-node.sh "$node" 'if sudo test -f /var/lib/rancher/k3s/agent/kube-vip-hold.yaml; then sudo mv /var/lib/rancher/k3s/agent/kube-vip-hold.yaml /var/lib/rancher/k3s/agent/pod-manifests/kube-vip.yaml; fi' || true
  done
 }
 trap restore_vip_candidates EXIT
 for node in lab-s2 lab-s3; do
  scripts/ssh-node.sh "$node" 'sudo mv /var/lib/rancher/k3s/agent/pod-manifests/kube-vip.yaml /var/lib/rancher/k3s/agent/kube-vip-hold.yaml'
 done
 for i in {1..60}; do
  leader=$(kubectl --request-timeout=3s -n kube-system get lease plndr-cp-lock -o jsonpath='{.spec.holderIdentity}' 2>/dev/null || true)
  [[ $leader == lab-s1* ]] && break
  sleep 2
 done
 restore_vip_candidates
 trap - EXIT
 [[ $leader == lab-s1* ]] || { echo 'Unable to make s1 the VIP holder' >&2; exit 1; }
 echo 's1 elected VIP holder; other candidates restored before reboot'
fi
before=$(scripts/ssh-node.sh lab-s1 'cat /proc/sys/kernel/random/boot_id')
(scripts/ssh-node.sh lab-s1 'sudo systemctl reboot' || true) &
reboot_pid=$!
python3 - <<'PY'
import subprocess,time,json
samples=[]; start=time.monotonic(); deadline=start+180
while time.monotonic()<deadline:
 t=time.monotonic(); p=subprocess.run(['kubectl','--request-timeout=3s','get','--raw','/readyz'],capture_output=True,text=True)
 row={'seconds':round(t-start,2),'ok':p.returncode==0 and p.stdout.strip()=='ok','message':(p.stdout+p.stderr).strip()[:250]}
 samples.append(row)
 print(json.dumps(row),flush=True)
 time.sleep(1)
json.dump(samples,open('evidence/p1/18-vip-reboot-samples.json','w'),indent=2)
success=sum(r['ok'] for r in samples)
assert success>0
bad_start=None;max_gap=0
for r in samples:
 if not r['ok'] and bad_start is None:bad_start=r['seconds']
 if r['ok'] and bad_start is not None:max_gap=max(max_gap,r['seconds']-bad_start);bad_start=None
if bad_start is not None:max_gap=max(max_gap,samples[-1]['seconds']-bad_start)
assert max_gap<=20,(max_gap,'API unavailable too long')
print(f'PASS: VIP API reboot samples successful={success}/{len(samples)}, max observed failover gap={max_gap:.2f}s')
PY
wait "$reboot_pid"
for i in {1..80}; do if after=$(scripts/ssh-node.sh lab-s1 'cat /proc/sys/kernel/random/boot_id' 2>/dev/null) && [[ $after != "$before" ]]; then break; fi; sleep 3; done
[[ $after != "$before" ]]
kubectl wait node lab-s1 --for=condition=Ready --timeout=300s
printf 'PASS: s1 reboot verified by changed boot_id, returned Ready\n'
kubectl get nodes -o wide
printf 'API VIP leader after reboot: '; kubectl -n kube-system get lease plndr-cp-lock -o jsonpath='{.spec.holderIdentity}'; echo
scripts/ssh-node.sh lab-s2 "$etcd endpoint health --cluster"
infra/libvirt/guard.sh
# The orchestrator authorizes these phase marker paths explicitly.
mkdir -p state
date -Is >state/ready-p1
printf 'P1 PASS %s\n' "$(cat state/ready-p1)"
