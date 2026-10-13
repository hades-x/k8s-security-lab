#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source /data/k8s-lab/infra/k3s/env.sh
cd "$ROOT"
version=v1.36.5+k3s1
mkdir -p vms/downloads evidence/p1
base=https://github.com/k3s-io/k3s/releases/download/$version
[[ -f vms/downloads/k3s ]] || curl -fL --retry 2 "$base/k3s" -o vms/downloads/k3s
curl -fsSL "$base/sha256sum-amd64.txt" -o vms/downloads/k3s-sha256sum-amd64.txt
(cd vms/downloads; grep '  k3s$' k3s-sha256sum-amd64.txt | sha256sum -c -) | tee evidence/p1/04-k3s-checksum.txt
# Download the install script from the same immutable release tag, not get.k3s.io.
if [[ ! -f infra/k3s/install-k3s.sh ]]; then curl -fsSL "https://raw.githubusercontent.com/k3s-io/k3s/$version/install.sh" -o infra/k3s/install-k3s.sh; sha256sum infra/k3s/install-k3s.sh >infra/k3s/install-k3s.sha256; fi
sha256sum -c infra/k3s/install-k3s.sha256 | tee -a evidence/p1/04-k3s-checksum.txt
printf 'k3s=%s
kube-vip=v1.2.4
' "$version" >infra/k3s/VERSIONS
if [[ ! -f .secrets/k3s-token ]]; then (umask 077; openssl rand -hex 32 >.secrets/k3s-token); fi
for suffix in s1 s2 s3 a1 a2; do
 node=lab-$suffix; ip=$(node_ip "$node")
 if scripts/ssh-node.sh "$node" 'test -x /usr/local/bin/k3s && sudo systemctl is-active --quiet k3s' 2>/dev/null || scripts/ssh-node.sh "$node" 'test -x /usr/local/bin/k3s && sudo systemctl is-active --quiet k3s-agent' 2>/dev/null; then continue; fi
 "${SCP[@]}" vms/downloads/k3s infra/k3s/install-k3s.sh .secrets/k3s-token "lab@$ip:/home/lab/"
 scripts/ssh-node.sh "$node" 'sudo install -m 755 /home/lab/k3s /usr/local/bin/k3s; sudo mkdir -p /etc/rancher/k3s; sudo install -m 600 /home/lab/k3s-token /etc/rancher/k3s/token; rm /home/lab/k3s-token /home/lab/k3s'
 config="$ROOT/vms/seeds/$node-k3s.yaml"
 cat >"$config" <<EOF
node-name: $node
node-ip: $ip
token-file: /etc/rancher/k3s/token
EOF
 if [[ $suffix == s* ]]; then
  cat >>"$config" <<'EOF'
flannel-backend: none
disable-network-policy: true
disable-kube-proxy: true
disable: [servicelb]
secrets-encryption: true
write-kubeconfig-mode: '0600'
tls-san: [192.168.150.10]
etcd-snapshot-schedule-cron: '0 */6 * * *'
kubelet-arg:
  - pod-manifest-path=/var/lib/rancher/k3s/agent/pod-manifests
  - system-reserved=cpu=500m,memory=768Mi
  - kube-reserved=cpu=500m,memory=512Mi
  - eviction-hard=memory.available<500Mi,nodefs.available<10%
  - eviction-soft=memory.available<1Gi
  - eviction-soft-grace-period=memory.available=1m30s
  - eviction-max-pod-grace-period=30
kube-apiserver-arg:
  - audit-policy-file=/etc/rancher/k3s/audit-policy.yaml
  - audit-log-path=/var/lib/rancher/k3s/server/logs/audit.log
  - audit-log-maxsize=100
  - audit-log-maxbackup=3
EOF
  if [[ $suffix == s1 ]]; then echo 'cluster-init: true' >>"$config"; else echo 'server: https://192.168.150.10:6443' >>"$config"; fi
  "${SCP[@]}" infra/k3s/audit-policy.yaml infra/k3s/kube-vip.yaml "lab@$ip:/home/lab/"
  scripts/ssh-node.sh "$node" 'sudo install -m 644 /home/lab/audit-policy.yaml /etc/rancher/k3s/audit-policy.yaml; sudo mkdir -p /var/lib/rancher/k3s/server/logs /var/lib/rancher/k3s/agent/pod-manifests; sudo install -m 644 /home/lab/kube-vip.yaml /var/lib/rancher/k3s/agent/pod-manifests/kube-vip.yaml'
  role=server
 else
  echo 'server: https://192.168.150.10:6443' >>"$config"; role=agent
 fi
 "${SCP[@]}" "$config" "lab@$ip:/home/lab/config.yaml"
 scripts/ssh-node.sh "$node" "sudo install -m 600 /home/lab/config.yaml /etc/rancher/k3s/config.yaml; rm /home/lab/config.yaml; sudo env INSTALL_K3S_SKIP_DOWNLOAD=true INSTALL_K3S_VERSION='$version' INSTALL_K3S_EXEC='$role' sh /home/lab/install-k3s.sh"
 if [[ $suffix == s1 ]]; then
  for i in {1..90}; do if scripts/ssh-node.sh "$node" "sudo k3s kubectl get --raw /readyz" 2>/dev/null; then break; fi; sleep 3; done
  (umask 077; scripts/ssh-node.sh "$node" 'sudo cat /etc/rancher/k3s/k3s.yaml' >.secrets/kubeconfig)
  python3 - <<'PY'
p='/data/k8s-lab/.secrets/kubeconfig'
s=open(p).read().replace('127.0.0.1','192.168.150.10');open(p,'w').write(s)
PY
  chmod 600 .secrets/kubeconfig
  for i in {1..90}; do if kubectl --request-timeout=4s get --raw /readyz 2>/dev/null; then break; fi; sleep 3; done
  kubectl --request-timeout=10s get --raw /readyz
 fi
done
kubectl get nodes -o wide
