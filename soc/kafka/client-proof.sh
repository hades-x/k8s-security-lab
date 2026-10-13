#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
umask 077
make_config() {
 local user="$1" source="$2" target="$3"
 local password
 password=$(<"$source")
 # Strimzi random SCRAM passwords are alphanumeric; escape for Java anyway.
 # Generated Strimzi SCRAM passwords contain no JAAS quote/backslash delimiters.
 [[ "$password" =~ ^[A-Za-z0-9]+$ ]] || { printf "Unexpected SCRAM password character set\n" >&2; exit 1; }
 cat > "$target" <<EOF
security.protocol=SASL_SSL
sasl.mechanism=SCRAM-SHA-512
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="$user" password="$password";
ssl.truststore.type=PEM
ssl.truststore.location=/ca/ca.crt
ssl.endpoint.identification.algorithm=https
acks=all
enable.idempotence=false
request.timeout.ms=10000
delivery.timeout.ms=20000
EOF
}
make_config zeek-shipper /producer/password /tmp/producer.properties
make_config soc-indexer /consumer/password /tmp/consumer.properties
BOOT=soc-kafka-bootstrap.kafka.svc.cluster.local:9093
TOKEN="p4-roundtrip-$(date +%s)-$RANDOM"
# Consumer must use the authorized exact group. Existing indexer shares that group,
# so the phase test pauses its replicas briefly and restores it on every exit.
/opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server "$BOOT" --topic zeek-conn --group soc-indexer --consumer.config /tmp/consumer.properties --consumer-property enable.auto.commit=false --timeout-ms 90000 > /tmp/received 2>/tmp/consumer.log &
CPID=$!
trap 'kill "$CPID" 2>/dev/null || true' EXIT
sleep 5
printf '{"ts":1760000000,"uid":"%s","proof":"p4"}\n' "$TOKEN" | /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server "$BOOT" --topic zeek-conn --producer.config /tmp/producer.properties > /tmp/producer.log 2>&1
for ((i=0;i<60;i++)); do if grep -Fq "$TOKEN" /tmp/received; then break; fi; sleep 1; done
grep -Fq "$TOKEN" /tmp/received || { printf '%s\n' 'FAIL TLS+SCRAM roundtrip'; exit 1; }
printf '%s\n' 'PASS TLS+SCRAM roundtrip'
# soc-indexer is authenticated, but explicitly has no produce ACL.
printf '{"proof":"must-not-produce"}\n' | /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server "$BOOT" --topic zeek-conn --producer.config /tmp/consumer.properties > /tmp/denied.log 2>&1 || true
grep -Eq 'TopicAuthorizationException|Not authorized to access topics|TOPIC_AUTHORIZATION_FAILED' /tmp/denied.log || { printf '%s\n' 'FAIL missing ACL denial proof'; exit 1; }
printf '%s\n' 'PASS unauthorized produce rejected by topic ACL'
