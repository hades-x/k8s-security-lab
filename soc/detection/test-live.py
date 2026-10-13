#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Execute guarded triggers and verify fresh documents AND persisted real alerts."""
from pathlib import Path
from datetime import datetime,timezone
import copy,json,os,subprocess,sys,time
import yaml
ROOT=Path('/data/k8s-lab')
sys.path.insert(0,str(ROOT/'soc/opensearch'))
from api_client import OpenSearch,APIError
assert os.environ.get('LAB_TRIGGER')=='1','LAB_TRIGGER=1 is required'
state=json.loads((ROOT/'evidence/p4/alerting-state.json').read_text())
assert len(state['rules'])==17
OUT=ROOT/'evidence/p4'
(OUT/'trigger-logs').mkdir(exist_ok=True)
records={}
with OpenSearch() as api:
    for name,entry in state['rules'].items():
        start=datetime.now(timezone.utc).isoformat()
        rule=yaml.safe_load((ROOT/'soc/detection/rules'/f'{name}.yaml').read_text())
        body=json.loads((ROOT/'soc/detection/monitors'/f'{name}.json').read_text())
        with open(OUT/'trigger-logs'/f'{name}.txt','w') as log:
            try:
                run=subprocess.run(['bash',str(ROOT/'soc/detection/triggers'/f'{name}.sh')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=260)
                code=run.returncode
            except subprocess.TimeoutExpired:
                code=124
        record={'sigma_id':rule['id'],'attack':[t.removeprefix('attack.').upper() for t in rule.get('tags',[]) if t.startswith('attack.t')],'trigger_exit':code,'trigger_started':start,'fresh_docs':0,'monitor_id':entry['id'],'execution_triggered':False,'alert_ids':[]}
        try:
            fresh=copy.deepcopy(body['inputs'][0]['search']['query'])
            fresh['query']={'bool':{'filter':[fresh['query'],{'range':{'@timestamp':{'gte':start,'lte':'now'}}}]}}
            for _ in range(30):
                result=api.request('POST','/'+entry['index']+'/_search',fresh)
                total=result['hits']['total']
                record['fresh_docs']=total['value'] if isinstance(total,dict) else total
                if record['fresh_docs']>0:break
                time.sleep(1)
            assert code==0,'Guarded trigger failed'
            assert record['fresh_docs']>0,'No matching documents newer than the trigger start'
            verify=api.request('GET','/_plugins/_alerting/monitors/'+entry['id'])['monitor']
            assert verify['enabled'] is True and all(t.get('query_level_trigger',t).get('actions',[])==[] for t in verify['triggers'])
            result=api.request('POST','/_plugins/_alerting/monitors/'+entry['id']+'/_execute',{'dryrun':False})
            (OUT/'trigger-logs'/f'{name}-execution.json').write_text(json.dumps(result,indent=2)+'\n')
            triggers=result.get('trigger_results',{})
            record['execution_triggered']=bool(triggers) and any(t.get('triggered') is True and not t.get('error') for t in triggers.values())
            assert record['execution_triggered'],'OpenSearch monitor did not trigger'
            for _ in range(15):
                alerts=api.request('GET','/_plugins/_alerting/monitors/alerts?monitorId='+entry['id']+'&size=100')
                active=[a for a in alerts['alerts'] if a.get('monitor_id')==entry['id'] and a.get('state')=='ACTIVE']
                record['alert_ids']=[a.get('id',a.get('_id')) for a in active]
                if record['alert_ids']:break
                time.sleep(1)
            assert record['alert_ids'],'No persisted ACTIVE alert returned by the alerts API'
            record['pass']=True
            print('PASS Sigma',name,'fresh_docs='+str(record['fresh_docs']),'alert='+','.join(record['alert_ids']),flush=True)
        except Exception as error:
            record['pass']=False
            record['error']=str(error)
            print('FAIL Sigma',name,str(error),flush=True)
        records[name]=record
        (OUT/'detections.json').write_text(json.dumps({'mechanism':state['mechanism'],'rules':records},indent=2)+'\n')
        table=['# P4 detection acceptance','',f'Mechanism: **{state["mechanism"]}**. Each PASS requires a successful guarded trigger, matching documents with `@timestamp` after its start, monitor `_execute` with `dryrun=false`, and an ACTIVE alert read back from the alerts API. No external notification actions.','', '| Rule | ATT&CK | Triggered? | Fresh matching documents | Persisted alert ID(s) |','|---|---|---|---:|---|']
        for n,r in records.items():
            table.append('| '+n+' | '+', '.join(r['attack'])+' | '+('PASS' if r['pass'] else 'FAIL')+' | '+str(r['fresh_docs'])+' | '+(', '.join(r['alert_ids']) or r.get('error','None').replace('|','/'))+' |')
        (OUT/'detections.md').write_text('\n'.join(table)+'\n')
passed=sum(r['pass'] for r in records.values())
print('Detection acceptance:',passed,'/',len(records),'rules produced verified real alerts')
assert len(records)==17 and passed>=10,(passed,len(records))
assert records['intel-hit']['pass'],'The end-to-end MISP/Zeek Intel alert is mandatory'
