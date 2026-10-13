#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Idempotently import and export a real six-panel SOC dashboard via saved objects."""
from pathlib import Path
import base64, json, urllib.request, urllib.error, uuid

ROOT = Path('/data/k8s-lab')
OUT = ROOT/'soc/opensearch/dashboards'
HOST = 'dashboards.192.168.150.200.sslip.io'
URL = 'http://192.168.150.200'
auth = 'Basic '+base64.b64encode(('admin:'+(ROOT/'.secrets/opensearch-admin.password').read_text()).encode()).decode()
def call(method,path,body=None,content_type='application/json'):
    if body is not None and not isinstance(body, bytes):
        body=json.dumps(body).encode()
    req=urllib.request.Request(URL+path,data=body,method=method,headers={'Host':HOST,'Authorization':auth,'osd-xsrf':'true','Content-Type':content_type,'securitytenant':'global'})
    with urllib.request.urlopen(req,timeout=60) as response:
        return response.read()

objects=[]
for ident,pattern in [('soc-zeek','zeek-*'),('soc-falco','falco-alerts-*'),('soc-audit','audit-k8s-*')]:
    field_info=json.loads(call('GET','/api/index_patterns/_fields_for_wildcard?pattern='+pattern))
    assert any(f['name']=='@timestamp' for f in field_info['fields']),pattern
    objects.append({'type':'index-pattern','id':ident,'attributes':{'title':pattern,'timeFieldName':'@timestamp','fields':json.dumps(field_info['fields'])},'references':[]})
panels=[]
for n,(slug,title,pattern,field) in enumerate([
    ('talkers','Top talkers','soc-zeek','id.orig_h'),
    ('dns','DNS queries','soc-zeek','query'),
    ('notices','Notices','soc-zeek','note'),
    ('intel','Intel hits','soc-zeek','seen.indicator'),
    ('falco','Falco events','soc-falco','rule'),
    ('audit','Kubernetes audit','soc-audit','verb')]):
    vis={'title':title,'type':'table','params':{'perPage':10,'showPartialRows':False,'showMetricsAtAllLevels':False,'sort':{'columnIndex':1,'direction':'desc'},'showTotal':False,'totalFunc':'sum'},'aggs':[{'id':'1','enabled':True,'type':'count','schema':'metric','params':{}},{'id':'2','enabled':True,'type':'terms','schema':'bucket','params':{'field':field,'size':10,'order':'desc','orderBy':'1'}}]}
    ident='soc-'+slug
    objects.append({'type':'visualization','id':ident,'attributes':{'title':title,'visState':json.dumps(vis),'uiStateJSON':'{}','description':'Synthetic training lab observations, not a production security verdict.','kibanaSavedObjectMeta':{'searchSourceJSON':json.dumps({'query':{'query':'','language':'kuery'},'filter':[],'indexRefName':'kibanaSavedObjectMeta.searchSourceJSON.index'})}},'references':[{'name':'kibanaSavedObjectMeta.searchSourceJSON.index','type':'index-pattern','id':pattern}]})
    panels.append({'panelIndex':str(n+1),'version':'3.9.0','type':'visualization','panelRefName':'panel_'+str(n),'embeddableConfig':{},'gridData':{'x':(n%2)*24,'y':(n//2)*15,'w':24,'h':15,'i':str(n+1)}})
objects.append({'type':'dashboard','id':'soc-overview','attributes':{'title':'SOC overview','description':'Zeek → Kafka → OpenSearch, MISP Intel, Falco and Kubernetes audit. Lab-only signals.','panelsJSON':json.dumps(panels),'optionsJSON':json.dumps({'useMargins':True,'hidePanelTitles':False}),'version':1,'timeRestore':True,'timeFrom':'now-1h','timeTo':'now','kibanaSavedObjectMeta':{'searchSourceJSON':json.dumps({'query':{'query':'','language':'kuery'},'filter':[]})}},'references':[{'name':'panel_'+str(n),'type':'visualization','id':'soc-'+slug} for n,slug in enumerate(['talkers','dns','notices','intel','falco','audit'])]})
OUT.mkdir(parents=True,exist_ok=True)
source=''.join(json.dumps(o)+'\n' for o in objects).encode()
(OUT/'soc-overview-source.ndjson').write_bytes(source)
boundary='p4-'+uuid.uuid4().hex
body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="soc.ndjson"\r\nContent-Type: application/x-ndjson\r\n\r\n'.encode()+source+f'\r\n--{boundary}--\r\n'.encode())
result=json.loads(call('POST','/api/saved_objects/_import?overwrite=true',body,'multipart/form-data; boundary='+boundary))
assert result['success'] is True,result
assert result['successCount']==len(objects),result
print('PASS saved objects import:',result['successCount'])
readback=json.loads(call('GET','/api/saved_objects/dashboard/soc-overview'))
assert readback['attributes']['title']=='SOC overview'
assert len(json.loads(readback['attributes']['panelsJSON']))==6
for ident in ['soc-zeek','soc-falco','soc-audit']:
    assert json.loads(call('GET','/api/saved_objects/index-pattern/'+ident))['id']==ident
export=call('POST','/api/saved_objects/_export',{'objects':[{'type':'dashboard','id':'soc-overview'}],'includeReferencesDeep':True,'excludeExportDetails':True})
rows=[json.loads(line) for line in export.splitlines() if line.strip()]
assert len(rows)==len(objects),(len(rows),len(objects))
assert { (x['type'],x['id']) for x in rows }=={ (x['type'],x['id']) for x in objects }
(OUT/'soc-overview.ndjson').write_bytes(export)
print('PASS SOC overview, six panels, three index patterns, exported objects:',len(rows))
