#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Prove TLS/OAuth configuration, targets, dashboards, Loki, rules, and alert delivery."""
import json,subprocess,time,urllib.request,urllib.parse,urllib.error,ssl,pathlib,requests
R=pathlib.Path('/data/k8s-lab');ctx=ssl.create_default_context(cafile=str(R/'.secrets/pki/root_ca.crt'))
pfs=[]
def eventually(fn,attempts=90):
 for _ in range(attempts):
  try:return fn()
  except (OSError,AssertionError,KeyError,requests.RequestException):time.sleep(2)
 raise RuntimeError('Acceptance condition not reached')
def forward(service,port,target):
 p=subprocess.Popen([str(R/'bin/kubectl'),'-n','monitoring','port-forward','svc/'+service,f'{port}:{target}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);pfs.append(p)
def get(url):
 with urllib.request.urlopen(url,timeout=20) as r:return json.load(r)
def oauth():
 r=requests.get('https://grafana.192.168.150.200.sslip.io/login/generic_oauth',verify=str(R/'.secrets/pki/root_ca.crt'),allow_redirects=False,timeout=20)
 assert r.status_code in (302,303,307)
 u=urllib.parse.urlparse(r.headers['Location']);q=urllib.parse.parse_qs(u.query)
 assert u.hostname=='keycloak.192.168.150.200.sslip.io' and q['client_id']==['grafana'] and q['response_type']==['code'] and q['code_challenge_method']==['S256']
 return True
try:
 eventually(oauth);print('PASS: Grafana TLS verified; OAuth redirects to Keycloak with grafana client and PKCE')
 forward('monitoring-kube-prometheus-prometheus',19090,9090);forward('loki',13100,3100);forward('monitoring-kube-prometheus-alertmanager',19093,9093)
 def targets():
  t=get('http://127.0.0.1:19090/api/v1/targets')['data']['activeTargets'];assert t
  down=[x for x in t if x['health']!='up'];assert not down,'one or more scrape targets down'
  return len(t)
 print(f'PASS: {eventually(targets)} active Prometheus targets, all up')
 def dashboards():
  a=((R/'.secrets/p3/grafana-admin-user').read_text().strip(),(R/'.secrets/p3/grafana-admin-password').read_text().strip())
  r=requests.get('https://grafana.192.168.150.200.sslip.io/api/search?type=dash-db',auth=a,verify=str(R/'.secrets/pki/root_ca.crt'),timeout=20);assert r.status_code==200
  ds=r.json();lab=[d for d in ds if d.get('uid') in ['lab-cluster','lab-kafka','lab-cilium-hubble']];assert len(lab)==3
  return len(ds),[(d['uid'],d['title']) for d in lab]
 count,lab=eventually(dashboards);print(f'PASS: {count} Grafana dashboards provisioned; lab dashboards={json.dumps(lab)}')
 def logs():
  q=urllib.parse.urlencode({'query':'{job="kubernetes-pods"}','limit':'5'});d=get('http://127.0.0.1:13100/loki/api/v1/query_range?'+q);assert d['status']=='success';n=sum(len(s.get('values',[])) for s in d['data']['result']);assert n>0;return n
 print(f'PASS: Loki LogQL {{job="kubernetes-pods"}} returned {eventually(logs)} pod log lines from Alloy (content withheld)')
 def rules():
  groups=get('http://127.0.0.1:19090/api/v1/rules')['data']['groups'];lab=next(g for g in groups if g['name']=='lab.rules');names=[x['name'] for x in lab['rules']];assert 'LabP3AcceptanceAlwaysFiring' in names;return names
 print('PASS: lab PrometheusRules loaded: '+','.join(eventually(rules)))
 def firing():
  a=get('http://127.0.0.1:19093/api/v2/alerts');test=next(x for x in a if x['labels'].get('alertname')=='LabP3AcceptanceAlwaysFiring');assert test['status']['state']=='active';return test['labels'],test['status']['state']
 labels,state=eventually(firing);print(f'PASS: intentional test alert firing in Alertmanager: state={state} labels={json.dumps(labels,sort_keys=True)}')
finally:
 for p in pfs:p.terminate();p.wait(timeout=10)
