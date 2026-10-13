
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
from pathlib import Path
import os,json,yaml,hashlib,copy,subprocess,tarfile,datetime,sys,ast
R=Path('/data/k8s-lab');os.chdir(R);E=R/'evidence/p4-prep-a'
# Read-only for authored configs: only evidence files are regenerated.
# To intentionally sync edited standalone configs into manifest ConfigMaps, run
# python3 soc/pipeline/render-configmaps.py before this validation script.
# Execute independently and save every result (no cluster commands in this script).
results=[]
def run(label,args,env=None,outfile=None):
 proc=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
 (E/(label+'.txt')).write_text('$ '+' '.join(args)+'\n'+proc.stdout+'\nexit_code='+str(proc.returncode)+'\n')
 if outfile:Path(outfile).write_text(proc.stdout)
 print(label,proc.returncode,proc.stdout[-1400:]);results.append((label,proc.returncode))
 if proc.returncode:raise SystemExit('Static validation failed: '+label)
run('01-helm-strimzi',[str(R/'bin/helm'),'template','strimzi',str(R/'bin/p4-prep-a/strimzi-1.3.0.tgz'),'-n','kafka','-f','soc/kafka/values.yaml','--include-crds'],outfile=E/'rendered/strimzi.yaml')
run('02-helm-opensearch',[str(R/'bin/helm'),'template','soc-opensearch-operator',str(R/'bin/p4-prep-a/operator-3.0.14.tgz'),'-n','opensearch','-f','soc/opensearch/values.yaml','--include-crds'],outfile=E/'rendered/opensearch-operator.yaml')
# Current release schemas supplement the CRD catalog (opensearch.org v1 is new).
def strict(schema):
 if isinstance(schema,dict):
  if schema.get('type')=='object' and 'properties' in schema and 'additionalProperties' not in schema and not schema.get('x-kubernetes-preserve-unknown-fields'):schema['additionalProperties']=False
  for v in schema.values():strict(v)
 elif isinstance(schema,list):
  for v in schema:strict(v)
count=0
for f in [E/'upstream/strimzi-crds.yaml',E/'rendered/opensearch-operator.yaml']:
 for d in yaml.safe_load_all(f.read_text()):
  if not d or d.get('kind')!='CustomResourceDefinition':continue
  for v in d['spec']['versions']:
   schema=copy.deepcopy(v['schema']['openAPIV3Schema']);strict(schema)
   schema['properties']['metadata']={'type':'object'};schema['properties']['status']={'type':'object'}
   folder=E/'schemas'/d['spec']['group'];folder.mkdir(exist_ok=True)
   (folder/(d['spec']['names']['kind'].lower()+'_'+v['name']+'.json')).write_text(json.dumps(schema));count+=1
paths=['evidence/p4-prep-a/rendered/strimzi.yaml','evidence/p4-prep-a/rendered/opensearch-operator.yaml','soc/kafka/cluster.yaml','soc/kafka/topics.yaml','soc/kafka/users.yaml','soc/kafka/client-pod.yaml','soc/opensearch/cluster.yaml','soc/opensearch/ingress.yaml','soc/pipeline/manifests.yaml']
base=[str(R/'bin/kubeconform'),'-strict','-ignore-missing-schemas','-summary']
catalog='https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'
run('03-kubeconform-catalog',base+['-schema-location','default','-schema-location',catalog]+paths)
run('04-kubeconform-release-schemas',base+['-verbose','-schema-location','default','-schema-location','evidence/p4-prep-a/schemas/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json','-schema-location',catalog]+paths)
env={**os.environ,'KAFKA_PASSWORD':'static-validation-placeholder','OPENSEARCH_PASSWORD':'static-validation-placeholder','VECTOR_NODE_NAME':'validation-node'}
run('05-vector-version',[str(R/'bin/vector'),'--version'])
for role in ['zeek','audit','indexer']:
 path=f'soc/pipeline/config/vector-{role}.yaml'
 run('06-vector-validate-'+role,[str(R/'bin/vector'),'validate','--no-environment',path],env=env)
 run('07-vector-test-'+role,[str(R/'bin/vector'),'test',path],env=env)
for f in [*Path('soc/kafka').glob('*.sh'),*Path('soc/opensearch').glob('*.sh'),*Path('soc/pipeline').glob('*.sh'),Path('tests/phase-p4-a.sh')]:
 run('08-shell-'+f.parent.name+'-'+f.stem,['bash','-n',str(f)])
for f in Path('soc/opensearch').glob('*.py'):ast.parse(f.read_text(),filename=str(f))
for f in Path('soc/opensearch/api').glob('*.json'):json.loads(f.read_text())
# Static semantic checks complement generic schema validation.
k=list(yaml.safe_load_all(Path('soc/kafka/cluster.yaml').read_text()));pool,cluster=k
assert pool['spec']['replicas']==3 and set(pool['spec']['roles'])=={'broker','controller'}
assert pool['spec']['storage']['class']=='local-path' and pool['spec']['jvmOptions']['-Xmx']=='768m'
assert cluster['spec']['kafka']['listeners'][0]['authentication']['type']=='scram-sha-512'
topics=list(yaml.safe_load_all(Path('soc/kafka/topics.yaml').read_text()));assert len(topics)==7
assert all(t['spec']['partitions']==3 and t['spec']['replicas']==3 and t['spec']['config']['min.insync.replicas']==2 for t in topics)
users=list(yaml.safe_load_all(Path('soc/kafka/users.yaml').read_text()));assert len(users)==4
for u in users:
 assert set(u['spec']['quotas'])=={'producerByteRate','consumerByteRate','requestPercentage'}
 if u['metadata']['name']=='soc-indexer':assert not any('Write' in a['operations'] for a in u['spec']['authorization']['acls'])
oscluster=yaml.safe_load(Path('soc/opensearch/cluster.yaml').read_text());assert oscluster['spec']['nodePools'][0]['replicas']==3
assert oscluster['spec']['general']['setVMMaxMapCount'] is False
build=yaml.safe_load((E/'upstream/opensearch-build-3.9.0.yml').read_text());component_names={x['name'] for x in build['components']};assert {'security','alerting','security-analytics'}<=component_names
manifests=list(yaml.safe_load_all(Path('soc/pipeline/manifests.yaml').read_text()))
for config in Path('soc/pipeline/config').glob('*.yaml'):
 c=yaml.safe_load(config.read_text())
 for sink in c['sinks'].values():
  if sink.get('buffer',{}).get('type')=='disk':assert sink['buffer']['max_size']>=268435488,(config,sink['buffer'])
for d in manifests:
 if d['kind']=='ConfigMap':assert d['data']['vector.yaml']==(Path('soc/pipeline/config')/(d['metadata']['name']+'.yaml')).read_text()
 if d['kind'] in ['Deployment','DaemonSet']:
  for c in d['spec']['template']['spec']['containers']:assert c['resources']['requests'] and c['resources']['limits'] and '@sha256:' in c['image']
for d in manifests:
 if d['metadata']['name']=='vector-audit' and d['kind']=='DaemonSet':assert d['spec']['template']['spec']['nodeSelector']=={'node-role.kubernetes.io/control-plane':'true'}
# Dump exact future integration commands, never invoke them here.
summary={'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mode':'OFFLINE_PREPARATION_NO_CLUSTER_NO_DOCKER_NO_LIBVIRT','release_schemas':count,'checks':results,'semantic_checks':'PASS','plugins_provenance':'official opensearch-build 3.9.0 distribution manifest; image not executed','runtime_acceptance':'NOT_RUN_OFFLINE_PREPARATION'}
(E/'09-static-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
