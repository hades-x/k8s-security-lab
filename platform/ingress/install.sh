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
mkdir -p evidence/p2
kubectl apply -f platform/ingress/lb.yaml
version=v1.6.3
curl -fsSL "https://github.com/kubernetes-sigs/gateway-api/releases/download/$version/standard-install.yaml" -o platform/ingress/gateway-api-standard.yaml
sha256sum platform/ingress/gateway-api-standard.yaml >platform/ingress/gateway-api-standard.sha256
kubectl apply --server-side --force-conflicts -f platform/ingress/gateway-api-standard.yaml
kubectl apply -f platform/ingress/traefik-config.yaml
kubectl apply -f platform/ingress/hubble.yaml
printf 'gateway-api=%s
' "$version" >platform/ingress/VERSIONS
kubectl -n kube-system get helmchart traefik -o jsonpath='{.spec.chart}{"\n"}{.spec.version}{"\n"}' >>platform/ingress/VERSIONS
for i in {1..120}; do
 if [[ $(kubectl -n kube-system get svc traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}') == 192.168.150.200 ]]; then break; fi
 sleep 3
done
kubectl -n kube-system rollout status deploy/traefik --timeout=300s
kubectl -n kube-system get svc traefik -o wide
kubectl -n kube-system get deploy traefik -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}' >>platform/ingress/VERSIONS
