#!/usr/bin/env python3

raise SystemExit('PUBLIC_RUNTIME_DISABLED: native importer disabled; rule 18 lacks monitor input and the old 17-rule assertions need an explicit catalogue')

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Try native Sigma custom rules/detectors before considering the Alerting fallback."""
from pathlib import Path
import json, sys, time
import yaml
ROOT=Path('/data/k8s-lab')
sys.path.insert(0,str(ROOT/'soc/opensearch'))
from api_client import OpenSearch, APIError
STATE=ROOT/'evidence/p4/security-analytics-state.json'
state=json.loads(STATE.read_text()) if STATE.exists() else {'rules':{},'detectors':{},'errors':[]}
with OpenSearch() as api:
    for path in sorted((ROOT/'soc/detection/rules').glob('*.yaml')):
        name=path.stem
        sigma=yaml.safe_load(path.read_text())
        monitor=json.loads((ROOT/'soc/detection/monitors'/f'{name}.json').read_text())
        index=monitor['inputs'][0]['search']['indices'][0]
        category='dns' if index=='zeek-dns-*' else ('linux' if index=='falco-alerts-*' else ('others_application' if index=='audit-k8s-*' else 'network'))
        try:
            if name not in state['rules']:
                # Preserve the authored UUID and selectors; normalize dates only for the plugin parser.
                sigma['date']=str(sigma['date']).replace('-','/')
                raw=yaml.safe_dump(sigma,sort_keys=False).encode()
                result=api.request('POST','/_plugins/_security_analytics/rules?category='+category,raw)
                rid=result['_id']
                verify=api.request('POST','/_plugins/_security_analytics/rules/_search?pre_packaged=false',{'size':1000,'query':{'ids':{'values':[rid]}}})
                # Rule config indexing is asynchronous; wait for the exact ID, not just the create reply.
                for _ in range(20):
                    if verify['hits']['hits']:break
                    time.sleep(1)
                    verify=api.request('POST','/_plugins/_security_analytics/rules/_search?pre_packaged=false',{'size':1000,'query':{'ids':{'values':[rid]}}})
                assert len(verify['hits']['hits'])==1,verify
                state['rules'][name]={'id':rid,'sigma_id':sigma['id'],'index':index,'category':category,'title':sigma['title']}
                print('PASS custom Sigma rule',name,rid)
            STATE.write_text(json.dumps(state,indent=2)+'\n')
        except Exception as e:
            state['errors'].append({'rule':name,'error':str(e),'time':time.time()})
            STATE.write_text(json.dumps(state,indent=2)+'\n')
            print('FAIL custom Sigma rule',name,str(e))
    if '--rules-only' in sys.argv:
        print('Native custom rules imported:',len(state['rules']))
        assert len(state['rules']) == 17
        raise SystemExit(0)
    groups={}
    for name,rule in state['rules'].items():
        groups.setdefault(rule['index'],[]).append(rule)
    for index,rules in groups.items():
        if index in state['detectors']:continue
        category=rules[0]['category']
        resolved=api.request('GET','/_resolve/index/'+index)['indices']
        assert resolved,index
        concrete=sorted(x['name'] for x in resolved)[-1]
        rid=[{'id':r['id']} for r in rules]
        body={'name':'SOC '+index.replace('*','all'),'enabled':True,'detector_type':category,'type':'detector','schedule':{'period':{'interval':1,'unit':'MINUTES'}},'inputs':[{'detector_input':{'description':'Native lab fields; custom experimental Sigma rules','custom_rules':rid,'pre_packaged_rules':[],'indices':[concrete]}}],'triggers':[{'id':'soc-lab-hit','name':'SOC candidate hit','severity':'3','ids':[r['id'] for r in rules],'sev_levels':[],'tags':[],'actions':[]}]}
        try:
            result=api.request('POST','/_plugins/_security_analytics/detectors',body)
            did=result['_id']
            verify=api.request('GET','/_plugins/_security_analytics/detectors/'+did)
            assert verify['detector']['name']==body['name'],verify
            state['detectors'][index]={'id':did,'name':body['name'],'category':category,'rules':[r['id'] for r in rules]}
            print('PASS Security Analytics detector',index,did)
        except Exception as e:
            state['errors'].append({'index':index,'error':str(e),'time':time.time()})
            print('FAIL Security Analytics detector',index,str(e))
        STATE.write_text(json.dumps(state,indent=2)+'\n')
print('Native import:',len(state['rules']),'rules;',len(state['detectors']),'detectors')
assert len(state['rules'])==17 and len(state['detectors'])==7, 'Native Security Analytics incomplete; inspect errors before choosing fallback.'
