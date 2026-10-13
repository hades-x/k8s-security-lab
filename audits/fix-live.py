
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
from pathlib import Path
p=Path('/data/k8s-lab/audits/run.sh');s=p.read_text();s=s.replace('rbacassessmentreports; do','rbacassessmentreports clusterrbacassessmentreports; do');s=s.replace('kubescape scan framework "$framework"','scan_framework=$framework; [[ $framework != cis ]] || scan_framework=cis-v1.12.0\n kubescape scan framework "$scan_framework"');p.write_text(s)
p=Path('/data/k8s-lab/audits/summarize.py');s=p.read_text().replace("d=load('trivy-'+type+'.json');items=d['items']","d=load('trivy-'+type+'.json');items=d['items']\n if type=='rbacassessmentreports':items+=load('trivy-clusterrbacassessmentreports.json')['items']")
s=s.replace("counts['kubescape-'+framework]=tot","tot['compliance_score']=d.get('summaryDetails',{}).get('complianceScore')\n tot['scan_coverage']=d.get('scanCoverage')\n counts['kubescape-'+framework]=tot")
s=s.replace("kyv=load('kyverno-reports.json')", "d=load('trivy-configauditreports.json');appitems=[x for x in d['items'] if x['metadata'].get('namespace') in ['demo','dev','staging','prod']]\ncounts['trivy-app-config-severity']={'pass':None,'fail':sum(x['report']['summary'].get('criticalCount',0)+x['report']['summary'].get('highCount',0) for x in appitems),'critical':sum(x['report']['summary'].get('criticalCount',0) for x in appitems),'high':sum(x['report']['summary'].get('highCount',0) for x in appitems),'reports':len(appitems)}\nkyv=load('kyverno-reports.json')")
p.write_text(s)
print('Fixed CIS framework name, cluster RBAC report coverage and severity/compliance summaries.')
