#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
# make status: read-only health summary. --quick skips the Kafka lag pod (~40 s).
export LC_ALL=C
ROOT=/data/k8s-lab; cd "$ROOT"; source infra/k3s/env.sh >/dev/null
URI=qemu:///system
QUICK=1; [[ ${1:-} == --quick ]] && QUICK=1
h() { printf '\n== %s\n' "$*"; }
h "Host lab controller ($(date '+%F %T'))"
awk '/MemTotal/{t=$2} /MemAvailable/{a=$2} END{printf "RAM: %d GiB total, %d GiB available\n", t/1048576, a/1048576}' /proc/meminfo
df -BG --output=target,avail / /data | tail -2 | awk '{print "disk "$1": "$2" free"}'
echo "load: $(cut -d' ' -f1-3 /proc/loadavg)"
h "VMs"
virsh -c $URI list --all | grep -E 'lab-[sa][123]'
h "Nodes"
timeout 20 kubectl get nodes -o wide --no-headers 2>&1 | awk '{print $1, $2, $3, $6}'
h "etcd / API"
timeout 20 kubectl get --raw '/readyz?verbose' 2>&1 | grep -E 'etcd|readyz check' || echo "API not reachable"
h "Pods not Ready (excluding Completed jobs)"
timeout 30 kubectl get pods -A --no-headers 2>/dev/null | awk '$4!="Completed" && ($4!="Running" || $3 ~ /^0\//) {print $1, $2, $3, $4}' | head -40
n=$(timeout 30 kubectl get pods -A --no-headers 2>/dev/null | awk '$4!="Completed" && ($4!="Running" || $3 ~ /^0\//)' | wc -l); echo "count: $n"
h "Argo CD applications"
timeout 20 kubectl -n argocd get applications --no-headers 2>/dev/null | awk '{print $1, $2, $3}'
h "OpenSearch"
timeout 120 python3 scripts/opensearch-health.py 2>&1 | grep -E '^(health|index|total|unassigned)' | head -12
h "Kafka"
timeout 20 kubectl -n kafka get kafka soc -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}' 2>/dev/null
timeout 20 kubectl -n kafka get pods -l strimzi.io/broker-role=true --no-headers 2>/dev/null | awk '{print $1, $2, $3}'
if (( QUICK == 0 )); then timeout 150 scripts/kafka-lag-once.sh 2>&1 | grep -E '^(TOTAL|topic)'; else echo "(lag skipped: make status without --quick)"; fi
h "Lab OpenBao"
timeout 20 kubectl -n secrets get pod openbao-0 --no-headers 2>/dev/null | awk '{print "openbao-0 "$2" "$3" (0/1 = sealed -> make unseal)"}'
h "VM guests (mem available MiB / load / iowait%)"
for n in lab-s1 lab-s2 lab-s3 lab-a1 lab-a2; do
  printf '%s ' $n; timeout 10 scripts/ssh-node.sh $n "free -m | awk '/Mem/{printf \"mem_avail=%s \", \$7}'; cut -d' ' -f1 /proc/loadavg | tr '\n' ' '; top -bn1 | awk -F, '/Cpu\\(s\\)/{for(i=1;i<=NF;i++) if(\$i ~ / wa/) print \"iowait=\"\$i}'" 2>/dev/null || echo unreachable
done
