#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
export LC_ALL=C
ROOT=/data/k8s-lab
export PATH="$ROOT/bin:$PATH" KUBECONFIG="$ROOT/.secrets/kubeconfig"
export HELM_CONFIG_HOME="$ROOT/vms/tools/helm/config" HELM_CACHE_HOME="$ROOT/vms/tools/helm/cache" HELM_DATA_HOME="$ROOT/vms/tools/helm/data"
export XDG_CACHE_HOME="$ROOT/vms/tools/cache" XDG_CONFIG_HOME="$ROOT/vms/tools/config"
# Client-go and some CLIs ignore XDG variables and write below HOME.
export HOME="$ROOT/vms/tools/home"
mkdir -p "$HOME" "$HELM_CONFIG_HOME" "$HELM_CACHE_HOME" "$HELM_DATA_HOME" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME"
node_ip() { case "$1" in lab-s1) echo 192.168.150.11;; lab-s2) echo 192.168.150.12;; lab-s3) echo 192.168.150.13;; lab-a1) echo 192.168.150.21;; lab-a2) echo 192.168.150.22;; *) echo 'Refusing unknown node' >&2; return 1;; esac; }
SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$ROOT/.secrets/known_hosts" -o ConnectTimeout=5 -i "$ROOT/.secrets/lab_ed25519")
SCP=(scp -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$ROOT/.secrets/known_hosts" -o ConnectTimeout=5 -i "$ROOT/.secrets/lab_ed25519")
