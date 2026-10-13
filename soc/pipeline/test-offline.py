
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Exercise the real Vector file reader/remap/console offline, no network."""
from pathlib import Path
import json,os,tempfile,subprocess,time,yaml
R=Path('/data/k8s-lab');E=R/'evidence/p4-prep-a';os.chdir(R)
root=Path(tempfile.mkdtemp(prefix='file-tail-',dir=E));env={**os.environ,'VECTOR_NODE_NAME':'validation-node'}
results=[]
cases={
 'zeek': ('conn.log', [{'ts':1760000000.125,'uid':'offline-test','id.orig_h':'192.168.150.11','id.resp_h':'192.168.150.12','id.orig_p':12345,'id.resp_p':443}]),
 'audit':('audit.log',[{'objectRef':{'resource':'secrets'},'requestObject':{'data':{'test':'offline-redaction-marker'}},'responseObject':{'data':{'test':'offline-redaction-marker'}},'requestReceivedTimestamp':'2026-10-13T07:00:00Z','auditID':'offline-test'}])}
for role,(name,records) in cases.items():
 log=root/name;log.write_text(''.join(json.dumps(x)+'\n' for x in records))
 cfg=yaml.safe_load((R/f'soc/pipeline/config/vector-{role}.yaml').read_text());cfg.pop('tests',None);cfg['api']={'enabled':False};data=root/(role+'-data');data.mkdir();cfg['data_dir']=str(data)
 source=cfg['sources'][role];source['include']=[str(log)];source['glob_minimum_cooldown_ms']=100
 cfg['sinks']={'console':{'type':'console','inputs':['parse_'+role],'encoding':{'codec':'json'},'buffer':cfg['sinks']['kafka']['buffer'],'acknowledgements':{'enabled':True}}}
 p=root/(role+'-config.yaml');p.write_text(yaml.safe_dump(cfg,sort_keys=False))
 proc=subprocess.Popen([str(R/'bin/vector'),'--config',str(p)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  time.sleep(3)
  proc.terminate();out,err=proc.communicate(timeout=15)
 except BaseException:
  proc.kill();proc.communicate();raise
 (root/(role+'-stdout.jsonl')).write_text(out);(root/(role+'-stderr.txt')).write_text(err)
 assert proc.returncode==0,(role,proc.returncode,err)
 events=[json.loads(x) for x in out.splitlines() if x.strip()];assert len(events)==1,(role,events,err)
 event=events[0];assert event['node']=='validation-node' and '@timestamp' in event
 if role=='zeek':assert event['log_type']=='conn' and event['id']['orig_h']=='192.168.150.11'
 else:assert 'requestObject' not in event and 'responseObject' not in event and 'offline-redaction-marker' not in out
 results.append({'role':role,'emitted_events':len(events),'exit_code':proc.returncode,'result':'PASS'})
summary={'mode':'REAL_VECTOR_FILE_TAIL_NO_NETWORK_NO_CLUSTER','fixtures':str(root.relative_to(R)),'results':results}
(E/'10-vector-file-tail.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
