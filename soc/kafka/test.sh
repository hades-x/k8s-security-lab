#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
export LC_ALL=C
ROOT=/data/k8s-lab
export PATH="$ROOT/bin:$PATH"
export KUBECONFIG="$ROOT/.secrets/kubeconfig"
cd "$ROOT"
[[ -s "$KUBECONFIG" ]] || { printf '%s\n' 'Missing lab kubeconfig; install only after cluster creation.' >&2; exit 1; }
kubectl -n kafka wait kafka/soc --for=condition=Ready --timeout=2m
kubectl -n kafka get kafkanodepool mixed -o json | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d["spec"]["replicas"]==3; assert len(d["status"]["nodeIds"])==3; print("PASS Kafka Ready and 3 node IDs")'
kubectl -n kafka get pods -l soc.lab/role=kafka-broker -o json | python3 -c 'import sys,json; a=json.load(sys.stdin)["items"]; assert len(a)==3; assert all(any(c["type"]=="Ready" and c["status"]=="True" for c in p["status"]["conditions"]) for p in a); print("PASS 3 broker pods Ready")'
kubectl -n kafka get kafkatopics -o json | python3 -c 'import json,sys; d=json.load(sys.stdin); a={x["metadata"]["name"] for x in d["items"]}; e={"zeek-conn","zeek-dns","zeek-http","zeek-notice","zeek-intel","audit-k8s","falco-alerts"}; assert e<=a; print("PASS all 7 Kafka topics present")'
