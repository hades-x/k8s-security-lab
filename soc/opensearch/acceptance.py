#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Final read-back gates and counted evidence for the deployed SOC chain."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path('/data/k8s-lab')
sys.path.insert(0,str(ROOT/'soc/opensearch'))
from api_client import OpenSearch
nodes=json.loads(subprocess.check_output(['kubectl','get','nodes','-o','json']))['items']
expected={n['metadata']['name'] for n in nodes}
assert len(expected)==5
snapshot={'nodes':sorted(expected),'versions':{}}
with OpenSearch() as api:
    snapshot['versions']['opensearch']=api.request('GET','/')['version']['number']
    health=api.request('GET','/_cluster/health')
    assert health['number_of_nodes']==3 and health['status'] in ['green','yellow']
    snapshot['opensearch_health']=health
    query={'size':0,'aggs':{'log_types':{'terms':{'field':'log_type','size':10}},'nodes':{'terms':{'field':'node','size':10}},'capture_sources':{'terms':{'field':'capture_source','size':10}}}}
    result=api.request('POST','/zeek-*/_search',query)
    log_types={b['key']:b['doc_count'] for b in result['aggregations']['log_types']['buckets']}
    sources={b['key']:b['doc_count'] for b in result['aggregations']['nodes']['buckets']}
    assert {'conn','dns','http','notice','intel'}<=log_types.keys(),log_types
    assert all(log_types[t]>0 for t in ['conn','dns','http','notice','intel'])
    assert expected<=sources.keys(),sources
    snapshot['zeek_documents_by_log_type']=log_types
    snapshot['zeek_documents_by_node']=sources
    snapshot['capture_sources']={b['key']:b['doc_count'] for b in result['aggregations']['capture_sources']['buckets']}
    assert snapshot['capture_sources'].get('tap',0)>0
    snapshot['dashboard_panel_buckets']={}
    for title,index,field in [('Top talkers','zeek-*','id.orig_h'),('DNS queries','zeek-dns-*','query'),('Notices','zeek-notice-*','note'),('Intel hits','zeek-intel-*','seen.indicator'),('Falco events','falco-alerts-*','rule'),('Kubernetes audit','audit-k8s-*','verb')]:
        panel=api.request('POST','/'+index+'/_search',{'size':0,'aggs':{'values':{'terms':{'field':field,'size':10}}}})
        buckets=panel['aggregations']['values']['buckets']
        assert buckets,title
        snapshot['dashboard_panel_buckets'][title]=buckets
        print('PASS dashboard panel data:',title,len(buckets),'buckets')
    for topic in ['zeek-conn','zeek-dns','zeek-http','zeek-notice','zeek-intel','audit-k8s','falco-alerts']:
        count=api.request('GET','/'+topic+'-*/_count')['count']
        assert count>0,topic
        snapshot.setdefault('topic_index_counts',{})[topic]=count
        print('PASS indexed',topic,count)
    marker=(ROOT/'evidence/p4/falco-proof-marker.txt').read_text().strip()
    proof=api.request('POST','/falco-alerts-*/_search',{'size':10,'query':{'bool':{'filter':[{'term':{'rule':'Lab Shell In Container'}},{'wildcard':{'output_fields.proc.cmdline':'*'+marker+'*'}}]}}})
    assert proof['hits']['total']['value']>0
    snapshot['falco_fresh_proof']={'marker':marker,'documents':proof['hits']['total']['value'],'ids':[h['_id'] for h in proof['hits']['hits']]}
    print('PASS fresh Falco marker indexed:',proof['hits']['total']['value'])
    custom=api.request('POST','/_plugins/_security_analytics/rules/_search?pre_packaged=false',{'size':1000,'query':{'match_all':{}}})
    authored=json.loads((ROOT/'evidence/p4/security-analytics-state.json').read_text())['rules']
    assert len(authored)==17
    ids={h['_id'] for h in custom['hits']['hits']}
    assert {r['id'] for r in authored.values()}<=ids
    snapshot['custom_sigma_rules_verified']=len(authored)
    monitors=json.loads((ROOT/'evidence/p4/alerting-state.json').read_text())
    assert len(monitors['rules'])==17
    for entry in monitors['rules'].values():
        readback=api.request('GET','/_plugins/_alerting/monitors/'+entry['id'])['monitor']
        assert readback['enabled'] is True and readback['monitor_type']=='query_level_monitor'
    detections=json.loads((ROOT/'evidence/p4/detections.json').read_text())
    assert len(detections['rules'])==17
    passed=sum(r['pass'] for r in detections['rules'].values())
    assert passed>=10 and detections['rules']['intel-hit']['pass']
    snapshot['detection_mechanism']=monitors['mechanism']
    snapshot['verified_triggered_rules']=passed
    print('PASS real detections:',passed,'of',len(detections['rules']))
for ns in ['soc-sensors','falco']:
    labels=json.loads(subprocess.check_output(['kubectl','get','namespace',ns,'-o','json']))['metadata']['labels']
    assert labels['pod-security.kubernetes.io/enforce']=='privileged'
    print('PASS documented privileged namespace exemption:',ns)
for ns in ['kafka','opensearch','misp','soc-traffic','soc-detection']:
    labels=json.loads(subprocess.check_output(['kubectl','get','namespace',ns,'-o','json']))['metadata'].get('labels',{})
    assert not labels.get('pod-security.kubernetes.io/enforce'),(ns,labels)
mem={k:int(v.split()[0]) for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
snapshot['host_available_memory_gib']=mem['MemAvailable']/1024/1024
assert snapshot['host_available_memory_gib']>4
print('PASS host memory available GiB:',round(snapshot['host_available_memory_gib'],2))
(ROOT/'evidence/p4/acceptance-snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
print('PASS documents from all five nodes:',json.dumps(sources,sort_keys=True))
print('PASS documents by log_type:',json.dumps(log_types,sort_keys=True))
