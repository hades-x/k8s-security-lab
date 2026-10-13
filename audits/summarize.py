#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import json,pathlib,sys
root=pathlib.Path(sys.argv[1]);counts={}
def load(name):
 text=(root/name).read_text();start=text.find('{');return json.loads(text[start:])
for role in ['server','agent']:
 d=load('kube-bench-'+role+'.json');tot={x:0 for x in ['pass','fail','warn','info']}
 controls=d.get('Controls',d.get('controls',[])) if isinstance(d,dict) else d
 for c in controls:
  for key in tot:tot[key]+=int(c.get('total_'+key,0))
 if not sum(tot.values()):
  for c in controls:
   for group in c.get('tests',[]):
    for result in group.get('results',[]):
     status=result.get('status','').lower()
     if status in tot:tot[status]+=1
 if not sum(tot.values()):raise SystemExit('Missing kube-bench counts: '+role)
 counts['kube-bench-'+role]=tot
for type in ['vulnerabilityreports','configauditreports','rbacassessmentreports']:
 d=load('trivy-'+type+'.json');items=d['items']
 if type=='rbacassessmentreports':items+=load('trivy-clusterrbacassessmentreports.json')['items']
 if not items:raise SystemExit('No Trivy reports for '+type+'; wait for scanners')
 fail=passed=0
 for item in items:
  report=item.get('report',{});checks=report.get('checks',[])
  if type=='vulnerabilityreports':fail+=len(report.get('vulnerabilities',[]))
  else:
   fail+=sum(x.get('success') is False for x in checks);passed+=sum(x.get('success') is True for x in checks)
 counts['trivy-'+type]={'pass':None,'recorded_pass_checks':None if type=='vulnerabilityreports' else passed,'fail':fail,'unit':'vulnerabilities' if type=='vulnerabilityreports' else 'checks','reports':len(items),'namespace_reports':{ns:sum(x['metadata'].get('namespace','CLUSTER')==ns for x in items) for ns in sorted(set(x['metadata'].get('namespace','CLUSTER') for x in items))}}
for framework in ['nsa','mitre','cis']:
 d=load('kubescape-'+framework+'.json');controls=d.get('summaryDetails',{}).get('controls',[])
 if isinstance(controls,dict):controls=list(controls.values())
 if not controls:raise SystemExit('Kubescape summaryDetails.controls missing: '+framework)
 tot={'pass':0,'fail':0,'excluded':0,'unknown':0}
 for control in controls:
  status=control.get('status',{});status=status.get('status',status) if isinstance(status,dict) else status
  status=str(status).lower()
  if status in ['passed','pass']:tot['pass']+=1
  elif status in ['failed','fail']:tot['fail']+=1
  elif status in ['excluded','skipped']:tot['excluded']+=1
  else:tot['unknown']+=1
 if not tot['pass']+tot['fail']:raise SystemExit('No evaluated Kubescape controls: '+framework)
 tot['compliance_score']=d.get('summaryDetails',{}).get('complianceScore')
 tot['scan_coverage']={k:v for k,v in d.get('scanCoverage',{}).items() if k in ['coverageScore','evaluatedControls','totalControls','degraded']}
 counts['kubescape-'+framework]=tot
d=load('trivy-configauditreports.json');appitems=[x for x in d['items'] if x['metadata'].get('namespace') in ['demo','dev','staging','prod']]
counts['trivy-app-config-severity']={'pass':None,'fail':sum(x['report']['summary'].get('criticalCount',0)+x['report']['summary'].get('highCount',0) for x in appitems),'critical':sum(x['report']['summary'].get('criticalCount',0) for x in appitems),'high':sum(x['report']['summary'].get('highCount',0) for x in appitems),'reports':len(appitems)}
kyv=load('kyverno-reports.json')['items'];counts['kyverno']={'pass':sum(x.get('summary',{}).get('pass',0) for x in kyv),'fail':sum(x.get('summary',{}).get('fail',0) for x in kyv),'reports':len(kyv)}
(root/'summary.json').write_text(json.dumps(counts,indent=2));print(json.dumps(counts,indent=2))
