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
exec > >(tee evidence/p2/10-acceptance.txt) 2>&1
platform/argocd/test.sh | tee evidence/p2/11-argocd.txt
kubectl -n demo rollout status deployment/demo --timeout=300s
host=demo.192.168.150.200.sslip.io
if curl --noproxy '*' -fsS --max-time 15 -o evidence/p2/12-demo-response.html -w '%{http_code}\n' "http://$host/" >evidence/p2/12-demo-status.txt; then
 echo 'Host DNS resolves sslip.io; direct curl succeeded'
else
 echo 'Host wildcard DNS unavailable; using curl --resolve (no host DNS change)' | tee evidence/p2/12-dns-fallback.txt
 curl --noproxy '*' -fsS --resolve "$host:80:192.168.150.200" --max-time 15 -o evidence/p2/12-demo-response.html -w '%{http_code}\n' "http://$host/" >evidence/p2/12-demo-status.txt
fi
[[ $(cat evidence/p2/12-demo-status.txt) == 200 ]]
echo 'PASS: host demo ingress HTTP 200'
platform/storage/test.sh | tee evidence/p2/13-persistence.txt
[[ $(kubectl -n kube-system get svc traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}') == 192.168.150.200 ]]
kubectl -n kube-system get svc traefik -o wide | tee evidence/p2/14-loadbalancer.txt
kubectl get ciliuml2announcementpolicy,ciliumloadbalancerippool | tee -a evidence/p2/14-loadbalancer.txt
kubectl get sc | tee evidence/p2/15-storageclasses.txt
[[ $(kubectl get sc local-path -o jsonpath='{.metadata.annotations.storageclass\.kubernetes\.io/is-default-class}') == true ]]
[[ $(kubectl get sc longhorn -o jsonpath='{.metadata.annotations.storageclass\.kubernetes\.io/is-default-class}') == false ]]
platform/ingress/test.sh | tee evidence/p2/16-gateway.txt
kubectl -n demo get gateway lab -o json >evidence/p2/16-gateway.json
kubectl -n demo get httproute gateway-demo -o json >evidence/p2/16-httproute.json
python3 - <<'PY'
import json
g=json.load(open('evidence/p2/16-gateway.json'))
r=json.load(open('evidence/p2/16-httproute.json'))
assert any(c['type']=='Accepted' and c['status']=='True' for c in g['status']['conditions'])
assert any(c['type']=='Programmed' and c['status']=='True' for c in g['status']['conditions'])
assert all(any(c['type']=='Accepted' and c['status']=='True' for c in p['conditions']) for p in r['status']['parents'])
print('PASS: Gateway Accepted/Programmed, HTTPRoute Accepted; host curl succeeded')
PY
platform/forgejo/test.sh | tee evidence/p2/17-forgejo.txt
for svc in argocd forgejo hubble; do
 curl --noproxy '*' -fsS --resolve "$svc.192.168.150.200.sslip.io:80:192.168.150.200" --max-time 15 -o /dev/null -w "$svc ingress HTTP %{http_code}\n" "http://$svc.192.168.150.200.sslip.io/"
done | tee evidence/p2/18-ui-ingresses.txt
kubectl -n kube-system port-forward --address 127.0.0.1 svc/hubble-relay 4245:80 >evidence/p2/19-hubble-port-forward.txt 2>&1 &
pf=$!
trap 'kill "$pf" 2>/dev/null || true; wait "$pf" 2>/dev/null || true' EXIT
for i in {1..30}; do if hubble status --server 127.0.0.1:4245 >/dev/null 2>&1; then break; fi; sleep 1; done
hubble status --server 127.0.0.1:4245 | tee evidence/p2/20-hubble-status.txt
curl --noproxy '*' -fsS --resolve "$host:80:192.168.150.200" "http://$host/" >/dev/null
hubble observe --server 127.0.0.1:4245 --last 20 | tee evidence/p2/21-hubble-flows.txt
[[ $(wc -l <evidence/p2/21-hubble-flows.txt) -ge 20 ]]
echo 'PASS: Hubble observed at least 20 real flows'
kubectl get pods -A -o json >evidence/p2/22-pods.json
python3 - <<'PY'
import json
missing=[]; count=0
for p in json.load(open('evidence/p2/22-pods.json'))['items']:
 if p.get('status',{}).get('phase') in ['Succeeded','Failed']:continue
 for c in p['spec'].get('containers',[])+p['spec'].get('initContainers',[]):
  count+=1;r=c.get('resources',{})
  if any(k not in r.get(v,{}) for k in ['cpu','memory'] for v in ['requests','limits']):missing.append(p['metadata']['namespace']+'/'+p['metadata']['name']+':'+c['name'])
assert not missing,missing
print(f'PASS: requests/limits cpu+memory on all {count} active/init containers')
PY
kubectl get nodes -o wide | tee evidence/p2/23-nodes.txt
kubectl top nodes | tee evidence/p2/24-node-usage.txt
kubectl -n argocd get application lab-demo -o wide | tee evidence/p2/25-application.txt
infra/libvirt/guard.sh
mkdir -p state
date -Is >state/ready-p2
printf 'P2 PASS %s\n' "$(cat state/ready-p2)"
