#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Create the stable lab event and fill missing attributes, idempotently."""
import argparse,json,os,pathlib,urllib.request,urllib.error,uuid
p=argparse.ArgumentParser();p.add_argument('--url',default=os.getenv('MISP_URL','http://127.0.0.1:18080'));p.add_argument('--key-file',default='.secrets/misp-api-key');p.add_argument('--fixture',default='soc/misp/fixtures/lab-event.json');a=p.parse_args();key=pathlib.Path(a.key_file).read_text().strip();event_uuid=str(uuid.uuid5(uuid.NAMESPACE_DNS,'k8s-lab.p4.synthetic-event'))
def call(path,data=None):
 req=urllib.request.Request(a.url.rstrip('/')+path,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':key,'Content-Type':'application/json','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
fixture=json.loads(pathlib.Path(a.fixture).read_text())['Event']
try:existing=call('/events/view/'+event_uuid)['Event']
except urllib.error.HTTPError as e:
 if e.code!=404:raise
 body=dict(fixture,uuid=event_uuid,distribution=0,threat_level_id=4,analysis=2,published=False)
 existing=call('/events/add',{'Event':body})['Event']
seen={(x['type'],x['value']) for x in existing.get('Attribute',[])}
for attr in fixture['Attribute']:
 if (attr['type'],attr['value']) not in seen:call('/attributes/add/'+str(existing['id']),{'Attribute':attr})
verified=call('/events/view/'+event_uuid)['Event'];assert all((x['type'],x['value']) in {(i['type'],i['value']) for i in verified['Attribute']} for x in fixture['Attribute'])
print(json.dumps({'event_uuid':event_uuid,'attributes':len(verified['Attribute']),'verified':True}))
