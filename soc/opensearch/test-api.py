
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
from pathlib import Path
import os,ssl,urllib.request,urllib.error,base64,json,time
S=Path('/data/k8s-lab/.secrets');ctx=ssl.create_default_context(cafile=str(S/'opensearch-ca.crt'));ctx.check_hostname=False
URL=os.environ.get('SOC_OS_URL','https://127.0.0.1:19200')
def get(path,user=None):
 headers={}
 if user:headers['Authorization']='Basic '+base64.b64encode((user+':'+(S/('opensearch-'+user+'.password')).read_text()).encode()).decode()
 try:
  with urllib.request.urlopen(urllib.request.Request(URL+path,headers=headers),context=ctx,timeout=15) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,None
for _ in range(60):
 try:status,_=get('/') ;break
 except OSError:time.sleep(1)
else:raise SystemExit('Port-forward did not start')
assert status==401,status
print('PASS OpenSearch unauthenticated HTTP 401')
status,health=get('/_cluster/health','admin');assert status==200 and health['status'] in ['green','yellow'],(status,health)
assert health['number_of_nodes']==3,health['number_of_nodes']
print('PASS OpenSearch authenticated HTTP 200, 3 nodes, '+health['status'])
status,_=get('/','soc-analyst');assert status==200,status
print('PASS analyst authenticated HTTP 200')
if os.environ.get('SOC_REQUIRE_DATA')=='1':
 for topic in ['zeek-conn','zeek-dns','zeek-http','zeek-notice','zeek-intel','audit-k8s','falco-alerts']:
  status,count=get('/'+topic+'-*/_count','soc-analyst');assert status==200 and count['count']>0,(topic,status,count)
  print('PASS indexed '+topic+': '+str(count['count']))
