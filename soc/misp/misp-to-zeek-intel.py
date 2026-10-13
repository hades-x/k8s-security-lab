#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    import sys as _runtime_sys
    _fixture_only = '--from-json' in _runtime_sys.argv and '--update-configmap' not in _runtime_sys.argv
    if not _fixture_only and _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""MISP REST to atomic Zeek TSV. Offline fixture mode needs no credentials."""
import argparse,json,os,pathlib,urllib.request,urllib.parse,ipaddress
p=argparse.ArgumentParser();p.add_argument('--from-json');p.add_argument('--output',required=True);p.add_argument('--url',default=os.getenv('MISP_URL','http://misp.misp.svc:8080'));p.add_argument('--key-file');p.add_argument('--update-configmap',action='store_true');a=p.parse_args()
def request(url,body,key,method='POST',context=None):
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':key,'Accept':'application/json','Content-Type':'application/json'},method=method)
 with urllib.request.urlopen(req,timeout=45,context=context) as r:return json.load(r)
if a.from_json:data=json.loads(pathlib.Path(a.from_json).read_text())
else:
 key=pathlib.Path(a.key_file).read_text().strip() if a.key_file else os.environ['MISP_KEY']
 data=request(a.url.rstrip('/')+'/attributes/restSearch',{'returnFormat':'json','to_ids':True,'deleted':False},key)
def attrs(x):
 if isinstance(x,list):
  for i in x:yield from attrs(i)
 elif isinstance(x,dict):
  if 'type' in x and 'value' in x:yield x
  else:
   for k in ('response','Event','Attribute','Object'):
    if k in x:yield from attrs(x[k])
def clean(x):return str(x).replace('\t',' ').replace('\r',' ').replace('\n',' ')
rows=set()
for attr in attrs(data):
 typ=attr['type'];value=str(attr['value']).strip();kind=None
 if str(attr.get('to_ids',True)).lower() in ('false','0'):continue
 if typ in ('domain','hostname'):kind='Intel::DOMAIN';value=value.lower().rstrip('.')
 elif typ in ('ip-src','ip-dst'):kind='Intel::ADDR';value=str(ipaddress.ip_address(value))
 elif typ=='url':
  kind='Intel::URL';u=urllib.parse.urlsplit(value);value=(u.netloc+u.path+('?' +u.query if u.query else '')) if u.scheme else value
 if kind and value:rows.add((clean(value),kind,'MISP-LAB',clean(attr.get('comment','Synthetic lab indicator')),'T'))
header='#fields\tindicator\tindicator_type\tmeta.source\tmeta.desc\tmeta.do_notice\n'
output=pathlib.Path(a.output);output.parent.mkdir(parents=True,exist_ok=True);tmp=output.with_suffix('.tmp');tmp.write_text(header+''.join('\t'.join(r)+'\n' for r in sorted(rows)));tmp.replace(output)
if a.update_configmap:
 import ssl
 sa=pathlib.Path('/var/run/secrets/kubernetes.io/serviceaccount');token=(sa/'token').read_text();context=ssl.create_default_context(cafile=str(sa/'ca.crt'))
 endpoint='https://kubernetes.default.svc/api/v1/namespaces/soc-sensors/configmaps/zeek-intel'
 req=urllib.request.Request(endpoint,data=json.dumps({'data':{'misp.intel':output.read_text()}}).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/merge-patch+json'},method='PATCH')
 with urllib.request.urlopen(req,context=context,timeout=30) as r:assert r.status==200
print(json.dumps({'indicators':len(rows),'output':str(output),'configmap_updated':a.update_configmap}))
