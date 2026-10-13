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
for ns in kube-system longhorn-system forgejo argocd demo; do
 kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f -
 cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: LimitRange
metadata: {name: workload-budget, namespace: $ns}
spec:
  limits:
    - type: Container
      default: {cpu: '2', memory: 1Gi}
      defaultRequest: {cpu: 50m, memory: 64Mi}
EOF
done
# Bound bundled add-ons whose manifests do not ship with all four values.
kubectl -n kube-system set resources deployment/local-path-provisioner --requests=cpu=50m,memory=64Mi --limits=cpu=500m,memory=256Mi
kubectl -n kube-system set resources deployment/metrics-server --requests=cpu=100m,memory=128Mi --limits=cpu=500m,memory=256Mi
kubectl -n kube-system set resources deployment/coredns --requests=cpu=100m,memory=70Mi --limits=cpu=500m,memory=170Mi
kubectl -n kube-system set resources daemonset/cilium-envoy --requests=cpu=50m,memory=64Mi --limits=cpu=1,memory=512Mi
# Namespace defaults apply to future Pods; re-create existing Cilium Pods once.
kubectl -n kube-system rollout restart daemonset/cilium
kubectl -n kube-system rollout status daemonset/cilium --timeout=300s
