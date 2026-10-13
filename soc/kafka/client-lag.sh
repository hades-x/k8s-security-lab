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
printf 'security.protocol=SASL_SSL\nsasl.mechanism=SCRAM-SHA-512\nsasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="soc-indexer" password="%s";\nssl.truststore.type=PEM\nssl.truststore.location=/ca/ca.crt\nssl.endpoint.identification.algorithm=https\n' "$password" >/tmp/lag.properties
trap 'rm -f /tmp/lag.properties /tmp/lag.txt' EXIT
BOOT=soc-kafka-bootstrap.kafka.svc.cluster.local:9093
DEADLINE=$(( $(date +%s) + 300 ))
previous_committed=-1
while (( $(date +%s) < DEADLINE )); do
 /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server "$BOOT" --command-config /tmp/lag.properties --describe --group soc-indexer > /tmp/lag.txt
 count=0; sum=0; unknown=0; committed=0
 while read -r group topic part current end lag rest; do
  [[ "$group" == soc-indexer && "$part" =~ ^[0-2]$ ]] || continue
  case "$topic" in zeek-conn|zeek-dns|zeek-http|zeek-notice|zeek-intel|audit-k8s|falco-alerts) ;; *) exit 1;; esac
  count=$((count+1))
  [[ ! "$current" =~ ^[0-9]+$ ]] || committed=$((committed+current))
  if [[ "$lag" =~ ^[0-9]+$ ]]; then sum=$((sum+lag));
  elif [[ "$current" == - && "$end" == 0 ]]; then :;
  else unknown=$((unknown+1)); fi
 done < /tmp/lag.txt
 printf 'Kafka group soc-indexer partitions=%s lag=%s unknown=%s committed=%s previous_committed=%s\n' "$count" "$sum" "$unknown" "$committed" "$previous_committed"
 if (( count == 21 && unknown == 0 && (sum == 0 || (sum <= 5 && previous_committed >= 0 && committed > previous_committed)) )); then
  while IFS= read -r line; do printf '%s\n' "$line"; done < /tmp/lag.txt
  printf 'PASS consumer group drain: 21 partitions, lag=%s, committed=%s (zero or <=5 with advancing committed offsets)\n' "$sum" "$committed"
  exit 0
 fi
 previous_committed=$committed
 sleep 2
done
printf 'FAIL consumer group did not drain within five minutes\n' >&2
exit 1
