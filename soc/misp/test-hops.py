#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Read each real MISP→Zeek→OpenSearch→Alerting hop without exposing secrets."""
from pathlib import Path
from datetime import datetime
import json,os,subprocess,sys,time,urllib.request
ROOT=Path('/data/k8s-lab')
sys.path.insert(0,str(ROOT/'soc/opensearch'))
from api_client import OpenSearch
start=os.environ['INTEL_PROOF_STARTED']
since=datetime.fromisoformat(start.replace('Z','+00:00')).timestamp()
IOC='ioc.evil-c2.lab.test'
cm=json.loads(subprocess.check_output(['kubectl','-n','soc-sensors','get','configmap','zeek-intel','-o','json']))
rows=cm['data']['misp.intel'].splitlines()
assert IOC in cm['data']['misp.intel'] and len(rows)==5,rows
print('PASS exported Intel ConfigMap:',len(rows)-1,'indicators, resourceVersion',cm['metadata']['resourceVersion'])
event_uuid='e772fc9a-f9ed-558d-a83e-1979f9452706'
req=urllib.request.Request('http://192.168.150.200/events/view/'+event_uuid,headers={'Host':'misp.192.168.150.200.sslip.io','Authorization':(ROOT/'.secrets/misp-api-key').read_text().strip(),'Accept':'application/json'})
with urllib.request.urlopen(req,timeout=60) as response:
    assert response.status==200
    event=json.load(response)['Event']
assert event['uuid']==event_uuid and any(a['value']==IOC for a in event['Attribute'])
print('PASS MISP authenticated lab event:',event_uuid,'attributes',len(event['Attribute']))
pods=json.loads(subprocess.check_output(['kubectl','-n','soc-sensors','get','pods','-l','app=zeek','-o','json']))['items']
assert len(pods)==5
mounted=[]
for pod in pods:
    name=pod['metadata']['name']
    data=subprocess.check_output(['kubectl','-n','soc-sensors','exec',name,'-c','log-merger','--','python3','-c','from pathlib import Path;print(Path("/streams/tap/intel.log").exists())'])
    mounted.append({'node':pod['spec']['nodeName'],'pod':name,'started':pod['status']['startTime'],'intel_stream_exists':data.strip()==b'True'})
node=os.environ.get('NODE','lab-a2')
pod=next(p for p in pods if p['spec']['nodeName']==node)['metadata']['name']
script='import json;from pathlib import Path;rows=[json.loads(x) for x in Path("/var/log/zeek/current/intel.log").read_text().splitlines()];hits=[r for r in rows if r.get("seen.indicator")=="ioc.evil-c2.lab.test" and r.get("capture_source")=="tap" and r["ts"]>='+repr(since)+'];print(json.dumps({"count":len(hits),"uids":[h.get("uid") for h in hits[:3]]}))'
zeek=json.loads(subprocess.check_output(['kubectl','-n','soc-sensors','exec',pod,'-c','log-merger','--','python3','-c',script]))
assert zeek['count']>0,zeek
print('PASS fresh Zeek tap intel.log hits:',zeek['count'])
query={'size':0,'query':{'bool':{'filter':[{'term':{'seen.indicator':IOC}},{'range':{'@timestamp':{'gte':start}}}]}}}
with OpenSearch() as api:
    for _ in range(30):
        result=api.request('POST','/zeek-intel-*/_search',query)
        count=result['hits']['total']['value']
        if count>0:break
        time.sleep(1)
    assert count>0
    print('PASS fresh OpenSearch zeek-intel documents:',count)
    state=json.loads((ROOT/'evidence/p4/alerting-state.json').read_text())
    monitor=state['rules']['intel-hit']['id']
    execution=api.request('POST','/_plugins/_alerting/monitors/'+monitor+'/_execute',{'dryrun':False})
    assert any(t.get('triggered') for t in execution['trigger_results'].values()),execution
    alerts=api.request('GET','/_plugins/_alerting/monitors/alerts?monitorId='+monitor+'&size=100')['alerts']
    active=[a.get('id',a.get('_id')) for a in alerts if a.get('monitor_id')==monitor and a.get('state')=='ACTIVE']
    assert active,alerts
    print('PASS persisted MISP Intel ACTIVE alert:',','.join(active))
proof={'started':start,'misp_event':{'uuid':event_uuid,'id':event['id'],'attributes':len(event['Attribute'])},'intel_configmap':{'indicators':len(rows)-1,'resourceVersion':cm['metadata']['resourceVersion']},'zeek_reload_pods':mounted,'fresh_zeek_hits':zeek,'kafka_proof_log':'evidence/p4/intel-kafka-proof.txt','fresh_opensearch_hits':count,'monitor_id':monitor,'alert_ids':active}
(ROOT/'evidence/p4/intel-hop-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
