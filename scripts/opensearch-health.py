#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Read-only OpenSearch health report: cluster health, red/yellow indices, unassigned shard reasons, sizes."""
import sys, json
sys.path.insert(0, "/data/k8s-lab/soc/opensearch")
from api_client import OpenSearch, APIError
with OpenSearch() as a:
    h = a.request("GET", "/_cluster/health")
    print("health", {k: h[k] for k in ["status", "number_of_nodes", "active_shards", "unassigned_shards", "initializing_shards"]})
    total_mb = 0.0
    for x in a.request("GET", "/_cat/indices?format=json&bytes=mb&s=index"):
        if x["index"].startswith("."): continue
        size = float(x.get("store.size") or 0); total_mb += size
        if x["health"] != "green" or "-v" in sys.argv:
            print("index", x["health"], x["index"], "docs=" + str(x.get("docs.count")), f"{size:.0f}MB")
    print(f"total_log_indices_MB={total_mb:.0f}")
    for s in a.request("GET", "/_cat/shards?format=json"):
        if s["state"] == "UNASSIGNED":
            print("unassigned", s["index"], "shard=" + s["shard"], s["prirep"], s.get("unassigned.reason", ""))
    if h["unassigned_shards"]:
        try:
            e = a.request("GET", "/_cluster/allocation/explain")
            print("explain", e.get("index"), e.get("shard"), e.get("can_allocate"), (e.get("allocate_explanation") or "")[:300])
        except APIError as err:
            print("explain error", str(err)[:200])
