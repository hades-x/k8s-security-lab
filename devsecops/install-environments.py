#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import os,json,pathlib,subprocess,yaml,base64,time
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
def cmd(args,**kw):return subprocess.run(['kubectl']+args,check=True,**kw)
def apply(doc):cmd(['apply','-f','-'],input=yaml.safe_dump(doc).encode())
def write(path,data):p=pathlib.Path(path);p.parent.mkdir(exist_ok=True,parents=True);p.write_text(data)
images=json.loads(pathlib.Path('devsecops/infra-images.json').read_text())
values=yaml.safe_load(pathlib.Path('app/chart/values.yaml').read_text());values['postgresImage']=images['postgresql']['image'];values['valkeyImage']=images['valkey']['image'];write('app/chart/values.yaml',yaml.safe_dump(values))
topic={'apiVersion':'kafka.strimzi.io/v1','kind':'KafkaTopic','metadata':{'name':'demo-orders','namespace':'kafka','labels':{'strimzi.io/cluster':'soc'}},'spec':{'partitions':1,'replicas':3,'config':{'retention.ms':86400000,'min.insync.replicas':2}}}
user={'apiVersion':'kafka.strimzi.io/v1','kind':'KafkaUser','metadata':{'name':'demo-app','namespace':'kafka','labels':{'strimzi.io/cluster':'soc'}},'spec':{'authentication':{'type':'scram-sha-512'},'authorization':{'type':'simple','acls':[{'resource':{'type':'topic','name':'demo-orders','patternType':'literal'},'operations':['Read','Write','Describe'],'host':'*'},{'resource':{'type':'group','name':'demo-app-','patternType':'prefix'},'operations':['Read','Describe'],'host':'*'}]}}}
write('devsecops/kafka.yaml',yaml.safe_dump_all([topic,user]));cmd(['apply','-f','devsecops/kafka.yaml']);cmd(['-n','kafka','wait','kafkauser/demo-app','--for=condition=Ready','--timeout=180s']);cmd(['-n','kafka','wait','kafkatopic/demo-orders','--for=condition=Ready','--timeout=180s'])
ksecret=json.loads(cmd(['-n','kafka','get','secret','demo-app','-o','json'],capture_output=True,text=True).stdout)
ca=json.loads(cmd(['-n','kafka','get','secret','soc-cluster-ca-cert','-o','json'],capture_output=True,text=True).stdout)
for ns in ['dev','staging','prod']:
 r=subprocess.run(['kubectl','get','ns',ns],capture_output=True)
 if r.returncode:apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns,'labels':{'pod-security.kubernetes.io/enforce':'restricted','pod-security.kubernetes.io/enforce-version':'latest'}}})
 # Only create quota/limits when the hardening worker has not already supplied any.
 for kind,name,spec in [('ResourceQuota','p6-budget',{'hard':{'limits.memory':'1Gi','requests.memory':'600Mi','limits.cpu':'3','requests.cpu':'1','pods':'15','persistentvolumeclaims':'3','requests.storage':'4Gi'}}),('LimitRange','p6-defaults',{'limits':[{'type':'Container','default':{'memory':'256Mi','cpu':'500m'},'defaultRequest':{'memory':'32Mi','cpu':'25m'}}]})]:
  existing=json.loads(cmd(['-n',ns,'get',kind,'-o','json'],capture_output=True,text=True).stdout)['items']
  if not existing:apply({'apiVersion':'v1','kind':kind,'metadata':{'name':name,'namespace':ns},'spec':spec})
 apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'demo-kafka','namespace':ns},'data':{'password':ksecret['data']['password']}})
 apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'demo-kafka-ca','namespace':ns},'data':{'ca.crt':ca['data']['ca.crt']}})
 policies=[]
 def np(name,selector,ingress=None,egress=None):
  spec={'podSelector':{'matchLabels':selector},'policyTypes':[]}
  if ingress is not None:spec.update(ingress=ingress);spec['policyTypes'].append('Ingress')
  if egress is not None:spec.update(egress=egress);spec['policyTypes'].append('Egress')
  policies.append({'apiVersion':'networking.k8s.io/v1','kind':'NetworkPolicy','metadata':{'name':name,'namespace':ns},'spec':spec})
 def peer(label):return {'podSelector':{'matchLabels':{'app':label}}}
 def npeer(namespace,labels=None):
  p={'namespaceSelector':{'matchLabels':{'kubernetes.io/metadata.name':namespace}}}
  if labels:p['podSelector']={'matchLabels':labels}
  return p
 dns={'to':[npeer('kube-system',{'k8s-app':'kube-dns'})],'ports':[{'port':53,'protocol':'UDP'},{'port':53,'protocol':'TCP'}]}
 np('p6-default-deny',{},[],[])
 np('p6-dns',{},egress=[dns])
 np('p6-web',{'app':'web'},[{'from':[npeer('kube-system',{'app.kubernetes.io/name':'traefik'})],'ports':[{'port':8080}]}],[{'to':[peer('orders-api')],'ports':[{'port':8080}]}])
 np('p6-api',{'app':'orders-api'},[{'from':[peer('web')],'ports':[{'port':8080}]}],[{'to':[{'podSelector':{'matchLabels':{'cnpg.io/cluster':'demo-db'}}}],'ports':[{'port':5432}]},{'to':[peer('valkey')],'ports':[{'port':6379}]},{'to':[npeer('kafka')],'ports':[{'port':9093}]}])
 np('p6-worker',{'app':'orders-worker'},[],[{'to':[peer('valkey')],'ports':[{'port':6379}]},{'to':[npeer('kafka')],'ports':[{'port':9093}]}])
 np('p6-valkey',{'app':'valkey'},[{'from':[peer('orders-api'),peer('orders-worker')],'ports':[{'port':6379}]}],[])
 np('p6-postgres',{'cnpg.io/cluster':'demo-db'},[{'from':[peer('orders-api')],'ports':[{'port':5432}]},{'from':[npeer('cnpg-system')],'ports':[{'port':8000},{'port':5432}]}],[{'to':[{'ipBlock':{'cidr':'10.43.0.1/32'}},{'ipBlock':{'cidr':'192.168.150.0/24'}}],'ports':[{'port':443},{'port':6443}]}])
 write('devsecops/netpol/'+ns+'.yaml',yaml.safe_dump_all(policies));cmd(['apply','-f','devsecops/netpol/'+ns+'.yaml'])
print('PASS topic/user Ready; per-environment auth secrets and restricted network allow graph installed')
cmd(['get','resourcequota,limitrange','-A']);cmd(['get','nodes'])
