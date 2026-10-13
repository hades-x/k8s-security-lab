#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# Run the pinned Zeek compiler with the exact deployed script/intel ConfigMaps.
set -euo pipefail
ROOT=/data/k8s-lab
source "$ROOT/infra/k3s/env.sh"
cd "$ROOT"
kubectl -n soc-sensors delete pod zeek-syntax --ignore-not-found --wait=true >/dev/null
python3 - <<'PY' | kubectl apply -f -
import json,subprocess
spec=json.loads(subprocess.check_output(['kubectl','-n','soc-sensors','get','ds','zeek','-o','json']))['spec']['template']['spec']
c=spec['containers'][0]
c['name']='compiler'
c['command']=['zeek','-a','/scripts/main.zeek']
c['securityContext']['capabilities']={'drop':['ALL']}
pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':'zeek-syntax','namespace':'soc-sensors'},'spec':{'restartPolicy':'Never','automountServiceAccountToken':False,'containers':[c],'volumes':[v for v in spec['volumes'] if v['name'] in ['scripts','intel','streams']]}}
print(json.dumps(pod))
PY
for ((i=0;i<120;i++)); do
 phase=$(kubectl -n soc-sensors get pod zeek-syntax -o jsonpath='{.status.phase}')
 [[ "$phase" == Succeeded || "$phase" == Failed ]] && break
 sleep 1
done
kubectl -n soc-sensors logs zeek-syntax
[[ "$phase" == Succeeded ]]
printf 'PASS pinned Zeek script compiler\n'
kubectl -n soc-sensors delete pod zeek-syntax --wait=false >/dev/null
