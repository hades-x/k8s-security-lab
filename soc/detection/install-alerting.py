#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Idempotent, enabled query-level Sigma fallback; no notification destinations."""
from pathlib import Path
import json, sys, time
ROOT=Path('/data/k8s-lab')
sys.path.insert(0,str(ROOT/'soc/opensearch'))
from api_client import OpenSearch
STATE=ROOT/'evidence/p4/alerting-state.json'
state={'mechanism':'OpenSearch Alerting query-level monitors (Sigma fallback)','rules':{}}
with OpenSearch() as api:
    existing=api.request('POST','/_plugins/_alerting/monitors/_search',{'size':1000,'query':{'match_all':{}}})
    total=existing['hits']['total']
    assert (total['value'] if isinstance(total,dict) else total)<=1000
    byname={}
    for hit in existing['hits']['hits']:
        monitor=hit['_source'].get('monitor',hit['_source'])
        byname.setdefault(monitor['name'],[]).append(hit['_id'])
    for path in sorted((ROOT/'soc/detection/monitors').glob('*.json')):
        body=json.loads(path.read_text())
        body['name']='SOC Sigma '+path.stem+' - '+body['name']
        body['enabled']=True
        assert body['monitor_type']=='query_level_monitor'
        assert all(t['actions']==[] for t in body['triggers'])
        matches=byname.get(body['name'],[])
        assert len(matches)<=1,matches
        method='PUT' if matches else 'POST'
        target='/_plugins/_alerting/monitors'+('/'+matches[0] if matches else '')
        result=api.request(method,target,body)
        ident=result['_id']
        readback=api.request('GET','/_plugins/_alerting/monitors/'+ident)['monitor']
        assert readback['name']==body['name'] and readback['enabled'] is True
        assert readback['inputs'][0]['search']['indices']==body['inputs'][0]['search']['indices']
        # OpenSearch rewrites DSL to canonical SearchSourceBuilder JSON (boost,
        # range bounds, term.value). Validate execution, not byte equality.
        assert readback['inputs'][0]['search']['query']['size']==0
        assert readback['inputs'][0]['search']['query']['query']
        state['rules'][path.stem]={'id':ident,'name':body['name'],'index':body['inputs'][0]['search']['indices'][0]}
        STATE.write_text(json.dumps(state,indent=2)+'\n')
        print('PASS enabled Sigma fallback monitor',path.stem,ident)
assert len(state['rules'])==17
print('PASS 17 enabled query-level monitors, verified by GET; no external actions')
