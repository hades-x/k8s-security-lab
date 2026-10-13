#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""D13: set number_of_replicas for SOC log indices + their index templates (default 1)."""
import sys
sys.path.insert(0, "/data/k8s-lab/soc/opensearch")
from api_client import OpenSearch
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1
with OpenSearch() as a:
    for pat in ["zeek-*", "audit-k8s-*", "falco-alerts-*"]:
        print(pat, a.request("PUT", f"/{pat}/_settings", {"index": {"number_of_replicas": N}}))
    for it in a.request("GET", "/_index_template")["index_templates"]:
        body = it["index_template"]
        if not any(p.startswith(("zeek", "audit", "falco")) for p in body["index_patterns"]): continue
        s = body.setdefault("template", {}).setdefault("settings", {})
        if "index" in s and isinstance(s["index"], dict): s["index"]["number_of_replicas"] = N; s.pop("number_of_replicas", None)
        else: s["number_of_replicas"] = N
        print("template", it["name"], a.request("PUT", "/_index_template/" + it["name"], body).get("acknowledged"))
