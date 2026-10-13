#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import json,pathlib,sys,subprocess,os
p=pathlib.Path(sys.argv[1]);items=json.loads((p/'namespaced-rbac.json').read_text())['items']+json.loads((p/'cluster-rbac.json').read_text())['items'];roles={}
for x in items:
 if x['kind'] in ['Role','ClusterRole']:roles[(x['kind'],x['metadata'].get('namespace',''),x['metadata']['name'])]=x
rows=[]
for b in items:
 if b['kind'] not in ['RoleBinding','ClusterRoleBinding']:continue
 ref=b['roleRef'];ns=b['metadata'].get('namespace','');r=roles.get((ref['kind'],ns if ref['kind']=='Role' else '',ref['name']),{})
 for rule in (r.get('rules') or []):
  if ('' in rule.get('apiGroups',[]) or '*' in rule.get('apiGroups',[])) and set(rule.get('resources',[])) & {'secrets','*'} and set(rule.get('verbs',[])) & {'get','list','watch','*'}:
   for subject in (b.get('subjects') or []):rows.append({'binding':b['metadata']['name'],'namespace':ns or 'ALL','subject':subject,'verbs':rule['verbs'],'resourceNames':rule.get('resourceNames',[]),'aggregatedRole':bool(r.get('aggregationRule'))})
(p/'secret-readers.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
# SARs for concrete serviceaccounts/users supplement static role traversal. Groups require a user with --as-group.
checks=[]
for row in rows:
 s=row['subject'];name=s['name']
 if s['kind']=='Group':continue
 if s['kind']=='ServiceAccount':name='system:serviceaccount:'+s.get('namespace','default')+':'+name
 cmd=['kubectl','auth','can-i','get','secrets','--as='+name,'--request-timeout=15s']
 if os.environ.get('P5_API_SERVER'):cmd+=['--server='+os.environ['P5_API_SERVER']]
 if row['namespace']=='ALL':cmd+=['--all-namespaces']
 else:cmd+=['--namespace='+row['namespace']]
 result=subprocess.run(cmd,capture_output=True,text=True);checks.append({'subject':name,'scope':row['namespace'],'answer':result.stdout.strip(),'exit':result.returncode})
(p/'secret-reader-sar.json').write_text(json.dumps(checks,indent=2))
