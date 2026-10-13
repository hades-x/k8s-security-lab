#!/usr/bin/env bash

# Public candidate: runtime requires separately provisioned disposable lab.
if [[ ${LAB_ALLOW_RUNTIME:-} != yes ]]; then
  printf "%s\n" "BLOCKED: set LAB_ALLOW_RUNTIME=yes only after tools/DEPENDENCIES.md review" >&2
  return 2 2>/dev/null || exit 2
fi
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
export KUBECONFIG=${KUBECONFIG:-/data/k8s-lab/.secrets/kubeconfig}
export PATH="$ROOT/bin:$PATH"
cd "$ROOT"
# No implicit deployment: imports require explicit endpoint and secret file.
: "${OPENSEARCH_URL:?Set the lab OpenSearch URL}"
: "${OPENSEARCH_NETRC:?Set a chmod-600 netrc file containing generated lab credentials}"
: "${OPENSEARCH_CA:?Set the lab OpenSearch CA certificate path}"
python3 - "$OPENSEARCH_URL" "$OPENSEARCH_NETRC" <<'PY'
import urllib.parse,sys,pathlib,stat
assert urllib.parse.urlsplit(sys.argv[1]).scheme=='https', 'OpenSearch requires HTTPS'
assert pathlib.Path(sys.argv[2]).stat().st_mode & 0o077 == 0, 'Credential netrc must be private'
PY
# Idempotently update named monitors; disabled by default, enable only after a verified hit.
for body in soc/detection/monitors/*.json; do
 name=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["name"])' "$body")
 search=$(python3 -c 'import json,sys;print(json.dumps({"size":1000,"query":{"match_phrase":{"monitor.name":sys.argv[1]}}}))' "$name")
 response=$(curl -fsS --netrc-file "$OPENSEARCH_NETRC" --cacert "$OPENSEARCH_CA" -H 'Content-Type: application/json' -d "$search" "$OPENSEARCH_URL/_plugins/_alerting/monitors/_search")
 id=$(printf '%s' "$response" | python3 -c 'import json,sys;d=json.load(sys.stdin);hits=d["hits"];total=hits["total"];total=total["value"] if isinstance(total,dict) else total;assert total<=1000;h=[x for x in hits["hits"] if x["_source"].get("monitor",x["_source"]).get("name")==sys.argv[1]];assert len(h)<=1;print(h[0]["_id"] if h else "")' "$name")
 method=POST; path=_plugins/_alerting/monitors; [[ -z "$id" ]] || { method=PUT; path=$path/$id; }
 result=$(curl -fsS --netrc-file "$OPENSEARCH_NETRC" --cacert "$OPENSEARCH_CA" -X "$method" -H 'Content-Type: application/json' --data-binary "@$body" "$OPENSEARCH_URL/$path")
 id=$(printf '%s' "$result" | python3 -c 'import json,sys;print(json.load(sys.stdin)["_id"])')
 curl -fsS --netrc-file "$OPENSEARCH_NETRC" --cacert "$OPENSEARCH_CA" "$OPENSEARCH_URL/_plugins/_alerting/monitors/$id" | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["monitor"]["enabled"] is False;print("Verified disabled monitor",d["monitor"]["name"])'
done
