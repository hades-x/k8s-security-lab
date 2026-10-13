#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
umask 077
password=$(</consumer/password)
[[ "$password" =~ ^[A-Za-z0-9]+$ ]] || exit 2
: "${FALCO_PROOF:?A fresh proof marker is required}"
printf 'security.protocol=SASL_SSL\nsasl.mechanism=SCRAM-SHA-512\nsasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="soc-indexer" password="%s";\nssl.truststore.type=PEM\nssl.truststore.location=/ca/ca.crt\nssl.endpoint.identification.algorithm=https\nenable.auto.commit=false\n' "$password" >/tmp/consumer.properties
trap 'rm -f /tmp/consumer.properties /tmp/events /tmp/offsets' EXIT
BOOT=soc-kafka-bootstrap.kafka.svc:9093
/opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server "$BOOT" --topic falco-alerts --time -1 --command-config /tmp/consumer.properties >/tmp/offsets
[[ $(wc -l </tmp/offsets) == 3 ]] || { printf 'Expected three topic partitions\n' >&2; exit 1; }
: >/tmp/events
touch /tmp/consumer-ready
# Manual assignment from snapshotted latest offsets: no stale messages and no group rebalance.
while IFS=: read -r topic partition offset; do
 [[ "$topic" == falco-alerts && "$partition" =~ ^[0-2]$ && "$offset" =~ ^[0-9]+$ ]] || exit 2
 timeout --signal=TERM --kill-after=5s 20s /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server "$BOOT" --topic falco-alerts --partition "$partition" --offset "$offset" --timeout-ms 15000 --max-messages 10000 --command-config /tmp/consumer.properties >>/tmp/events || true
done </tmp/offsets
if grep -F "$FALCO_PROOF" /tmp/events | grep -q 'Lab Shell In Container'; then printf 'PASS Kafka falco-alerts contains the fresh lab shell proof event\n'; else printf 'FAIL fresh lab shell proof absent from Kafka\n' >&2; exit 1; fi
