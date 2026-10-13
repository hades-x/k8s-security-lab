
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Idempotent REST bootstrap; no demo-reserved objects are modified."""
from pathlib import Path
import base64,json,os,ssl,time,urllib.request,urllib.error
R=Path('/data/k8s-lab');S=R/'.secrets'
URL=os.environ.get('SOC_OS_URL','https://127.0.0.1:19200')
ctx=ssl.create_default_context(cafile=str(S/'opensearch-ca.crt'))
# Port-forward is loopback, while the cert SAN is the Kubernetes service DNS.
# CA chain validation stays enabled; normal in-cluster clients verify hostname too.
ctx.check_hostname=False
header='Basic '+base64.b64encode(('admin:'+(S/'opensearch-admin.password').read_text()).encode()).decode()
def api(method,path,data=None,allowed=(200,201)):
 req=urllib.request.Request(URL+path,data=None if data is None else json.dumps(data).encode(),method=method,headers={'Authorization':header,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,context=ctx,timeout=20) as r:
   assert r.status in allowed,(method,path,r.status)
   b=r.read();return json.loads(b) if b else {}
 except urllib.error.HTTPError as e:
  # No body echo: security APIs can return sensitive data.
  raise RuntimeError(f'{method} {path}: HTTP {e.code}') from None
for attempt in range(120):
 try:
  health=api('GET','/_cluster/health')
  if health['status'] in ['green','yellow']:break
 except (OSError,RuntimeError):pass
 time.sleep(5)
else:raise SystemExit('OpenSearch API did not become healthy in 10m')
plugins=api('GET','/_cat/plugins?format=json');names={x['component'] for x in plugins}
for plugin in ['opensearch-security','opensearch-alerting','opensearch-security-analytics']:
 if plugin not in names:raise SystemExit('Required plugin absent: '+plugin)
print('Required Security, Alerting and Security Analytics plugins present.')
policy=json.loads((R/'soc/opensearch/api/ism-soc.json').read_text())
try:old=api('GET','/_plugins/_ism/policies/soc-retention')
except RuntimeError as e:
 if 'HTTP 404' not in str(e):raise
 old=None
path='/_plugins/_ism/policies/soc-retention'
if old is not None:path+=f'?if_seq_no={old["_seq_no"]}&if_primary_term={old["_primary_term"]}'
api('PUT',path,policy)
assert api('GET','/_plugins/_ism/policies/soc-retention')['policy']['default_state']=='hot'
for f in sorted((R/'soc/opensearch/api').glob('template-*.json')):
 name='soc-'+f.stem.removeprefix('template-');p='/_index_template/'+name;payload=json.loads(f.read_text())
 api('PUT',p,payload)
 readback=api('GET',p)['index_templates'][0]['index_template']
 assert readback['index_patterns']==payload['index_patterns']
for name in ['soc-indexer','soc-analyst']:
 role=json.loads((R/('soc/opensearch/api/role-'+name+'.json')).read_text())
 p='/_plugins/_security/api/roles/'+name;api('PUT',p,role);assert name in api('GET',p)
 user={'password':(S/('opensearch-'+name+'.password')).read_text(),'backend_roles':[],'attributes':{}}
 p='/_plugins/_security/api/internalusers/'+name;api('PUT',p,user);assert name in api('GET',p)
 mapping={'users':[name],'backend_roles':[],'hosts':[]}
 p='/_plugins/_security/api/rolesmapping/'+name;api('PUT',p,mapping);assert api('GET',p)[name]['users']==[name]
# Built-in kibana_user is not edited. Give the analyst its Dashboards system-index
# permissions through a separate non-reserved role with identical allowed scope.
role={'cluster_permissions':['cluster_composite_ops'],'index_permissions':[{'index_patterns':['.kibana*','.opensearch_dashboards*'],'allowed_actions':['read','write','manage']}],'tenant_permissions':[{'tenant_patterns':['global_tenant'],'allowed_actions':['kibana_all_read']}]}
p='/_plugins/_security/api/roles/soc-dashboards-user';api('PUT',p,role);assert 'soc-dashboards-user' in api('GET',p)
p='/_plugins/_security/api/rolesmapping/soc-dashboards-user';api('PUT',p,{'users':['soc-analyst'],'backend_roles':[],'hosts':[]});assert api('GET',p)['soc-dashboards-user']['users']==['soc-analyst']
print('Verified ISM policy, three templates, lab users and role mappings.')
