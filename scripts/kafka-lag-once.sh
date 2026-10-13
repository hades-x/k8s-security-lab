#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# One-shot (non-looping) consumer-group lag for soc-indexer. Read-only towards Kafka data.
# Creates a short-lived client pod (same spec as soc/kafka/client-pod.yaml), prints per-topic lag, deletes the pod.
set -euo pipefail
ROOT=/data/k8s-lab; cd "$ROOT"; source infra/k3s/env.sh >/dev/null
NAME=soc-kafka-lagcheck
cat > /tmp/lag-once.sh <<'EOS'
#!/usr/bin/env bash
set -euo pipefail
umask 077
password=$(</consumer/password)
printf 'security.protocol=SASL_SSL\nsasl.mechanism=SCRAM-SHA-512\nsasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="soc-indexer" password="%s";\nssl.truststore.type=PEM\nssl.truststore.location=/ca/ca.crt\nssl.endpoint.identification.algorithm=https\n' "$password" >/tmp/p
/opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server soc-kafka-bootstrap.kafka.svc.cluster.local:9093 --command-config /tmp/p --describe --group soc-indexer 2>/dev/null \
 | awk '$1=="soc-indexer" && $6 ~ /^[0-9]+$/ {lag[$2]+=$6; end[$2]+=$5; tot+=$6; n++} END {for (t in lag) printf "topic=%s end_offsets=%d lag=%d\n", t, end[t], lag[t]; printf "TOTAL partitions=%d lag=%d\n", n, tot}'
rm -f /tmp/p
EOS
kubectl -n kafka delete pod $NAME --ignore-not-found --wait=true >/dev/null
kubectl -n kafka create configmap soc-kafka-lagcheck --from-file=client-lag.sh=/tmp/lag-once.sh --dry-run=client -o yaml | kubectl apply -f - >/dev/null
python3 - <<'PY' | kubectl apply -f - >/dev/null
from pathlib import Path
import yaml,json
pod=yaml.safe_load(Path('soc/kafka/client-pod.yaml').read_text().replace('soc-kafka-proof','soc-kafka-lagcheck'))
for v in pod['spec'].get('volumes',[]):
    if v.get('configMap',{}).get('name')=='soc-kafka-lag': v['configMap']['name']='soc-kafka-lagcheck'
pod['spec']['containers'][0]['command']=['bash','/proof/client-lag.sh']
print(json.dumps(pod))
PY
for i in $(seq 1 90); do
  ph=$(kubectl -n kafka get pod $NAME -o jsonpath='{.status.phase}' 2>/dev/null || true)
  [[ $ph == Succeeded || $ph == Failed ]] && break; sleep 2
done
kubectl -n kafka logs $NAME 2>/dev/null | sort
kubectl -n kafka delete pod $NAME --ignore-not-found --wait=false >/dev/null
[[ ${ph:-} == Succeeded ]]
