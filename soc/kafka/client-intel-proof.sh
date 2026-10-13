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
printf 'security.protocol=SASL_SSL\nsasl.mechanism=SCRAM-SHA-512\nsasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="soc-indexer" password="%s";\nssl.truststore.type=PEM\nssl.truststore.location=/ca/ca.crt\nssl.endpoint.identification.algorithm=https\nenable.auto.commit=false\n' "$password" >/tmp/consumer.properties
trap 'rm -f /tmp/consumer.properties /tmp/events /tmp/offsets' EXIT
BOOT=soc-kafka-bootstrap.kafka.svc:9093
/opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server "$BOOT" --topic zeek-intel --time -1 --command-config /tmp/consumer.properties >/tmp/offsets
[[ $(wc -l </tmp/offsets) == 3 ]]
printf 'Kafka zeek-intel offsets BEFORE replay:\n'
while IFS= read -r line; do printf '%s\n' "$line"; done </tmp/offsets
: >/tmp/events
touch /tmp/consumer-ready
while IFS=: read -r topic partition offset; do
 [[ "$topic" == zeek-intel && "$partition" =~ ^[0-2]$ && "$offset" =~ ^[0-9]+$ ]] || exit 2
 timeout --signal=TERM --kill-after=5s 20s /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server "$BOOT" --topic zeek-intel --partition "$partition" --offset "$offset" --timeout-ms 15000 --max-messages 10000 --command-config /tmp/consumer.properties >>/tmp/events || true
done </tmp/offsets
printf 'Kafka zeek-intel offsets AFTER replay:\n'
/opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server "$BOOT" --topic zeek-intel --time -1 --command-config /tmp/consumer.properties
grep -Fq 'ioc.evil-c2.lab.test' /tmp/events
grep -q '"log_type":"intel"' /tmp/events
printf 'PASS Kafka zeek-intel contains fresh IoC hits after the snapshotted latest offsets\n'
