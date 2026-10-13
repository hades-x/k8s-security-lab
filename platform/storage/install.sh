#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
source /data/k8s-lab/infra/k3s/env.sh
cd "$ROOT"
test -f state/ready-p1
for suffix in s1 s2 s3 a1 a2; do scripts/ssh-node.sh lab-$suffix 'export LC_ALL=C; dpkg-query -W open-iscsi nfs-common; systemctl is-active iscsid; sudo modprobe iscsi_tcp'; done
kubectl create namespace longhorn-system --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f platform/storage/limits.yaml
helm repo add longhorn https://charts.longhorn.io
helm repo update longhorn
helm upgrade --install longhorn longhorn/longhorn --version 1.13.0 -n longhorn-system -f platform/storage/values.yaml --wait --timeout 10m
kubectl annotate storageclass local-path storageclass.kubernetes.io/is-default-class=true --overwrite
kubectl annotate storageclass longhorn storageclass.kubernetes.io/is-default-class=false --overwrite
kubectl get sc
