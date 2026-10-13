#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Repeatable live defensive proofs; never inspect real Secret values."""
from pathlib import Path
import subprocess,json,copy,time,sys,shlex
ROOT=Path('/data/k8s-lab');OUT=ROOT/'evidence/p5';OUT.mkdir(exist_ok=True)
IMAGE='docker.io/library/busybox:1.37.0@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e'
results=[]
def run(args,check=True,input=None,timeout=120):
 p=subprocess.run(args,input=input,text=True,capture_output=True,timeout=timeout)
 if check and p.returncode:raise RuntimeError(' '.join(args)+'\n'+p.stdout+p.stderr)
 return p

def k(*args,**kw):
 # Retry only a kubectl exec transport reset; policy denials/timeouts are not retried.
 for attempt in range(2):
  r=run(['kubectl',*args],**dict(kw,check=False))
  if not (args and args[0]=='exec' and r.returncode and 'connection reset by peer' in r.stderr and attempt==0):break
  print('RETRY: exec API stream reset (not a dataplane verdict)',flush=True);time.sleep(1)
 if kw.get('check',True) and r.returncode:raise RuntimeError('kubectl '+' '.join(args)+'\n'+r.stdout+r.stderr)
 return r
def apply(d):return k('apply','-f','-',input=json.dumps(d))
def proof(name,fn):
 try:detail=fn();results.append({'name':name,'pass':True,'detail':detail});print('PASS: '+name+' '+str(detail),flush=True)
 except Exception as e:results.append({'name':name,'pass':False,'detail':str(e)});print('FAIL: '+name+' '+str(e),flush=True)

def pod(name,ns='demo',labels=None,server=False):
 c={'name':'app','image':IMAGE,'command':['sleep','3600'],'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']},'readOnlyRootFilesystem':True},'resources':{'requests':{'cpu':'10m','memory':'16Mi'},'limits':{'cpu':'100m','memory':'64Mi'}}}
 spec={'automountServiceAccountToken':False,'restartPolicy':'Never','securityContext':{'runAsNonRoot':True,'runAsUser':10001,'runAsGroup':10001,'seccompProfile':{'type':'RuntimeDefault'}},'containers':[c]}
 if server:
  c['command']=['sh','-c','printf "# p5-ok\\np5_proof 1\\n" > /tmp/index.html; cp /tmp/index.html /tmp/metrics; httpd -p 9090 -h /tmp; exec httpd -f -p 5432 -h /tmp']
  c['volumeMounts']=[{'name':'tmp','mountPath':'/tmp'}];spec['volumes']=[{'name':'tmp','emptyDir':{}}]
 return {'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':ns,'labels':labels or {'p5-proof':'true'}},'spec':spec}

def rejected(d,needle,filename):
 r=k('create','--dry-run=server','-f','-',input=json.dumps(d),check=False)
 output=r.stdout+r.stderr;(OUT/filename).write_text(output)
 assert r.returncode!=0,'Unexpected admission success'
 assert needle in output,'Wrong rejection, expected '+needle+': '+output
 print(output.strip(),flush=True);return needle

def pss():
 d=pod('p5-privileged');d['spec']['containers'][0]['securityContext']['privileged']=True;d['spec']['containers'][0]['securityContext'].pop('allowPrivilegeEscalation',None)
 return rejected(d,'violates PodSecurity','negative-privileged-pss.log')
def kyvhost():
 d=pod('p5-privileged');d['spec']['containers'][0]['securityContext']['privileged']=True;d['spec']['containers'][0]['securityContext'].pop('allowPrivilegeEscalation',None)
 # PSA rejects Pods before validating webhooks. Exercise the same Pod template
 # through Deployment admission to independently prove Kyverno, no PSS relaxation.
 dep={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'p5-privileged','namespace':'demo'},'spec':{'replicas':1,'selector':{'matchLabels':{'p5-proof':'true'}},'template':{'metadata':{'labels':{'p5-proof':'true'}},'spec':d['spec']}}}
 dep['spec']['template']['spec']['restartPolicy']='Always'
 return rejected(dep,'lab-host-isolation','negative-privileged-kyverno.log')
def limits():
 # demo LimitRange defaults omitted limits before Kyverno. Use the isolated
 # P5 target namespace without a LimitRange to test actual missing-budget denial.
 apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':'scen-p5-target','labels':{'pod-security.kubernetes.io/enforce':'restricted','pod-security.kubernetes.io/enforce-version':'v1.36'}}})
 d=pod('p5-no-limits',ns='scen-p5-target');d['spec']['containers'][0]['resources'].pop('limits')
 return rejected(d,'lab-resource-budget','negative-limits.log')
def tags():
 d=pod('p5-latest');d['spec']['containers'][0]['image']='docker.io/library/busybox:latest'
 return rejected(d,'lab-image-tags','negative-latest.log')
def token():
 d=pod('p5-default-token');d['spec'].pop('automountServiceAccountToken')
 return rejected(d,'lab-no-default-token','negative-token.log')

def fixtures():
 apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':'scen-p5-target','labels':{'pod-security.kubernetes.io/enforce':'restricted','pod-security.kubernetes.io/enforce-version':'v1.36'}}})
 for d in [pod('p5-net-client',labels={'app':'app','p5-proof':'true'}),pod('p5-net-db',labels={'app':'db','p5-proof':'true','lab.k8s/metrics':'true'},server=True),pod('p5-net-target',ns='scen-p5-target',labels={'p5-proof':'target'},server=True)]:
  apply(d);k('wait','--for=condition=Ready','pod/'+d['metadata']['name'],'-n',d['metadata']['namespace'],'--timeout=120s',timeout=150)
 for ns,name,selector in [('demo','p5-db',{'app':'db','p5-proof':'true'}),('scen-p5-target','p5-target',{'p5-proof':'target'})]:
  apply({'apiVersion':'v1','kind':'Service','metadata':{'name':name,'namespace':ns},'spec':{'selector':selector,'ports':[{'port':5432,'targetPort':5432}]}})
 return 'three Ready low-resource Pods, two ClusterIP services'

def allowed():
 dns=k('exec','-n','demo','p5-net-client','--','nslookup','p5-target.scen-p5-target.svc.cluster.local')
 db=k('exec','-n','demo','p5-net-client','--','wget','-q','-T','5','-O','-','http://p5-db.demo.svc.cluster.local:5432')
 assert 'p5-ok' in db.stdout,db.stdout
 healthy=k('exec','-n','scen-p5-target','p5-net-target','--','wget','-q','-T','5','-O','-','http://127.0.0.1:5432');assert 'p5-ok' in healthy.stdout
 (OUT/'allowed-flows.log').write_text(dns.stdout+'app -> db TCP/5432: '+db.stdout+'target local health: '+healthy.stdout)
 return 'DNS resolution and same-namespace app -> db TCP/5432 succeed; destination healthy'
def blocked():
 r=k('exec','-n','demo','p5-net-client','--','wget','-q','-T','3','-O','-','http://p5-target.scen-p5-target.svc.cluster.local:5432',check=False,timeout=15)
 (OUT/'blocked-flow.log').write_text(r.stdout+r.stderr)
 assert r.returncode!=0,'cross-namespace request unexpectedly succeeded'
 assert 'timed out' in r.stderr.lower(),r.stderr
 return 'cross-namespace service request timed out (healthy destination, DNS allowed)'
def hubble():
 r=run(['hubble','observe','--port-forward','--port-forward-port','0','--from-pod','demo/p5-net-client','--verdict','DROPPED','--since','2m','--last','50','-o','json'],timeout=40)
 (OUT/'hubble-dropped.jsonl').write_text(r.stdout)
 flows=[json.loads(x).get('flow',{}) for x in r.stdout.splitlines() if x.strip()]
 matches=[x for x in flows if x.get('verdict')=='DROPPED' and x.get('drop_reason_desc')=='POLICY_DENIED' and x.get('source',{}).get('pod_name')=='p5-net-client' and x.get('l4',{}).get('TCP',{}).get('destination_port')==5432]
 assert matches,'No correlated Hubble policy-denied flow found'
 return str(len(matches))+' correlated DROPPED/POLICY_DENIED flows to TCP/5432'
def ingress():
 r=run(['curl','--noproxy','*','-sS','--max-time','10','-o','/dev/null','-w','%{http_code}','http://demo.192.168.150.200.sslip.io'])
 assert r.stdout=='200',r.stdout;(OUT/'demo-http.log').write_text('HTTP '+r.stdout+'\n');return 'HTTP 200'
def metrics():
 import socket,urllib.request
 apply({'apiVersion':'v1','kind':'Service','metadata':{'name':'p5-metrics','namespace':'demo','labels':{'p5-proof':'metrics'}},'spec':{'selector':{'app':'db','p5-proof':'true'},'ports':[{'name':'metrics','port':9090,'targetPort':9090}]}})
 apply({'apiVersion':'monitoring.coreos.com/v1','kind':'ServiceMonitor','metadata':{'name':'p5-metrics','namespace':'demo'},'spec':{'fallbackScrapeProtocol':'PrometheusText0.0.4','namespaceSelector':{'matchNames':['demo']},'selector':{'matchLabels':{'p5-proof':'metrics'}},'endpoints':[{'port':'metrics','path':'/metrics','interval':'5s'}]}})
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
 log=open(OUT/'prometheus-portforward.log','w');p=subprocess.Popen(['kubectl','-n','monitoring','port-forward','svc/monitoring-kube-prometheus-prometheus',str(port)+':9090'],stdout=log,stderr=log)
 try:
  for i in range(60):
   time.sleep(2)
   try:
    d=json.load(urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/api/v1/targets',timeout=3))
    targets=[x for x in d['data']['activeTargets'] if 'p5-metrics' in x.get('scrapePool','')]
    (OUT/'prometheus-last-targets.json').write_text(json.dumps(targets,indent=2))
    targets=[x for x in targets if x.get('health')=='up']
    if targets:
     (OUT/'prometheus-allowed.json').write_text(json.dumps(targets,indent=2));return 'actual Prometheus scrape of demo ServiceMonitor p5-metrics is UP (TCP/9090)'
   except (OSError,ValueError):pass
  raise RuntimeError('Prometheus did not report the P5 metrics target UP in 120s')
 finally:
  p.terminate();p.wait(timeout=10);log.close()

def encryption():
 k('create','secret','generic','p5-encryption-proof','-n','demo','--from-literal=dummy=p5-only-not-a-real-secret','--dry-run=client','-o','json')
 d=json.loads(k('create','secret','generic','p5-encryption-proof','-n','demo','--from-literal=dummy=p5-only-not-a-real-secret','--dry-run=client','-o','json').stdout);apply(d)
 verifier='import sys;v=sys.stdin.buffer.read();p=b"k8s:enc:aescbc:v1:";assert v.startswith(p),"Missing AES-CBC ciphertext prefix";print("PREFIX: "+p.decode());print("FIRST40_HEX: "+v[:40].hex())'
 cmd='set -euo pipefail; export LC_ALL=C; sudo k3s secrets-encrypt status; sudo /home/lab/etcdctl --endpoints=https://127.0.0.1:2379 --cacert=/var/lib/rancher/k3s/server/tls/etcd/server-ca.crt --cert=/var/lib/rancher/k3s/server/tls/etcd/server-client.crt --key=/var/lib/rancher/k3s/server/tls/etcd/server-client.key get /registry/secrets/demo/p5-encryption-proof --print-value-only | python3 -c '+shlex.quote(verifier)
 try:
  r=run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(ROOT/'.secrets/known_hosts'),'-i',str(ROOT/'.secrets/lab_ed25519'),'lab@192.168.150.12','bash -c '+shlex.quote(cmd)],timeout=30)
  assert 'PREFIX: k8s:enc:aescbc:v1:' in r.stdout;rout=r.stdout;(OUT/'etcd-encryption.log').write_text(rout);print(rout.strip(),flush=True)
  return 'raw etcd dummy-Secret value begins k8s:enc:aescbc:v1:; only 40-byte ciphertext header printed'
 finally:k('delete','secret','p5-encryption-proof','-n','demo','--ignore-not-found',check=False)
def cleanup():
 for ns,names in [('demo',['p5-net-client','p5-net-db']),('scen-p5-target',['p5-net-target'])]:k('delete','pod',*names,'-n',ns,'--ignore-not-found','--wait=true',check=False)
 for ns,name in [('demo','p5-db'),('demo','p5-metrics'),('scen-p5-target','p5-target')]:k('delete','svc',name,'-n',ns,'--ignore-not-found',check=False)
 k('delete','servicemonitor','p5-metrics','-n','demo','--ignore-not-found',check=False)

if __name__=='__main__':
 names={'encryption':encryption,'fixtures':fixtures,'allowed':allowed,'blocked':blocked,'hubble':hubble,'ingress':ingress,'metrics':metrics,'pss':pss,'kyverno-host':kyvhost,'limits':limits,'tags':tags,'token':token}
 requested=sys.argv[1:] or list(names)
 try:
  for name in requested:proof(name,names[name])
 finally:
  if not sys.argv[1:]:cleanup()
 (OUT/'proof-results.json').write_text(json.dumps(results,indent=2))
 sys.exit(0 if all(x['pass'] for x in results) else 1)
