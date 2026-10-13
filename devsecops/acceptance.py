#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Real P6 acceptance: no fabricated outputs, bounded polling, private credentials."""
import argparse, base64, datetime, json, os, pathlib, re, subprocess, sys, time, uuid
import requests
import yaml
ROOT=pathlib.Path('/data/k8s-lab'); os.chdir(ROOT); os.environ['LC_ALL']='C'
E=ROOT/'evidence/p6'; E.mkdir(exist_ok=True)
F='https://forgejo.192.168.150.200.sslip.io'; C='https://ci.192.168.150.200.sslip.io'
REG='zot.192.168.150.200.sslip.io'; REPO=REG+'/lab/demo-app'
CA=str(ROOT/'.secrets/pki/root_ca.crt')
os.environ['DOCKER_CONFIG']=str(ROOT/'.secrets/p6'); os.environ['SSL_CERT_FILE']=CA
fs=requests.Session();fs.verify=CA;fs.headers['Authorization']='token '+(ROOT/'.secrets/p6/forgejo-token').read_text().strip()
cs=requests.Session();cs.verify=CA;cs.headers['Authorization']='Bearer '+(ROOT/'.secrets/p6/woodpecker-token').read_text().strip()
RID=json.loads((ROOT/'devsecops/ci-repo.json').read_text())['id']

def api(session,method,url,**kw):
    r=session.request(method,url,timeout=45,**kw)
    if r.status_code>=400: raise RuntimeError(f'{method} {url.split("?")[0]} HTTP {r.status_code}')
    return r.json() if r.content else None

def run(cmd,input=None,check=True):
    p=subprocess.run(cmd,input=input,capture_output=True,text=True,timeout=90)
    if check and p.returncode: raise RuntimeError('Command failed: '+' '.join(cmd)+'\n'+p.stderr[-3000:])
    return p

def kget(ns,kind,name=None):
    return json.loads(run(['kubectl','-n',ns,'get',kind]+([name] if name else [])+['-o','json']).stdout)

def evidence(name,obj):
    (E/name).write_text(json.dumps(obj,indent=2)+'\n' if not isinstance(obj,str) else obj)

def guard():
    info=dict(line.split(':',1) for line in pathlib.Path('/proc/meminfo').read_text().splitlines())
    available=int(info['MemAvailable'].split()[0])*1024
    if available<=4*1024**3: raise RuntimeError(f'RESOURCE GUARD: host available {available/1024**3:.2f}GiB <=4GiB; stop new work')
    nodes=kget('default','nodes')['items']
    for n in nodes:
        conditions={x['type']:x['status'] for x in n['status']['conditions']}
        if conditions.get('Ready')!='True' or any(conditions.get(c)=='True' for c in ['MemoryPressure','DiskPressure','PIDPressure']):
            raise RuntimeError('RESOURCE GUARD: unhealthy node '+n['metadata']['name'])
    return round(available/1024**3,2)

def poll(label,fn,timeout=600,interval=5):
    end=time.monotonic()+timeout; last=None; next_guard=0
    while time.monotonic()<end:
        if time.monotonic()>=next_guard:guard();next_guard=time.monotonic()+20
        value=fn()
        if value:return value
        time.sleep(interval)
    raise TimeoutError(label+' did not pass within '+str(timeout)+'s')

def content(env):
    url=F+'/api/v1/repos/lab/demo-app-deploy/contents/chart/values-'+env+'.yaml'
    old=api(fs,'GET',url);return url,old,yaml.safe_load(base64.b64decode(old['content']))

def trigger():
    # A real git push from an isolated Forgejo clone, never the lab's main repo.
    active=api(cs,'GET',C+'/api/repos/'+str(RID)+'/pipelines')
    assert not any(p['status'] in ['pending','running','blocked'] for p in active), 'Another CI build is active; do not queue overlapping acceptance'
    private=ROOT/'.secrets/p6';askpass=private/'git-askpass.py'
    askpass.write_text('#!/usr/bin/env python3\nimport pathlib,sys\nprint("lab-admin" if "username" in sys.argv[1].lower() else pathlib.Path("/data/k8s-lab/.secrets/p6/forgejo-token").read_text().strip())\n')
    askpass.chmod(0o700)
    directory=private/'git-triggers'/uuid.uuid4().hex;directory.parent.mkdir(exist_ok=True)
    git_env=os.environ.copy();git_env.update(GIT_ASKPASS=str(askpass),GIT_TERMINAL_PROMPT='0',GIT_SSL_CAINFO=CA)
    url=F+'/lab/demo-app.git'
    def git(args):
        p=subprocess.run(['git']+args,env=git_env,capture_output=True,text=True,timeout=90)
        if p.returncode:raise RuntimeError('git command failed: '+p.stderr[-2000:])
        return p.stdout
    git(['clone','--quiet','--depth=1','--branch','main',url,str(directory)])
    git(['-C',str(directory),'config','user.name','P6 Acceptance'])
    git(['-C',str(directory),'config','user.email','p6@k8slab.invalid'])
    text='P6 acceptance '+datetime.datetime.now(datetime.timezone.utc).isoformat()+' '+uuid.uuid4().hex
    (directory/'BUILD_TRIGGER').write_text(text)
    git(['-C',str(directory),'add','BUILD_TRIGGER'])
    git(['-C',str(directory),'commit','-m','test: actual git push webhook acceptance'])
    sha=git(['-C',str(directory),'rev-parse','HEAD']).strip()
    git(['-C',str(directory),'push','origin','HEAD:main'])
    remote=git(['-C',str(directory),'ls-remote','origin','refs/heads/main']).split()[0]
    assert remote==sha
    check=api(fs,'GET',F+'/api/v1/repos/lab/demo-app/contents/BUILD_TRIGGER')
    assert base64.b64decode(check['content']).decode()==text
    evidence('trigger.json',{'sha':sha,'method':'Actual git push from isolated private Forgejo clone; native push webhook; NO replay'})
    print('PASS real git push and remote HEAD read back sha='+sha,flush=True)
    return sha

def ci_proof(sha,timeout):
    base=C+'/api/repos/'+str(RID)
    def find():
        return next((p for p in api(cs,'GET',base+'/pipelines') if p['commit']==sha and p['event']=='push'),None)
    pipeline=poll('automatic webhook pipeline',find,120)
    number=pipeline['number'];print('PASS automatic native webhook pipeline='+str(number)+' sha='+sha,flush=True)
    def finished():
        p=api(cs,'GET',base+'/pipelines/'+str(number))
        if p['status'] in ['success','failure','error','killed','declined']:
            evidence('acceptance-pipeline.json',p)
            for w in p.get('workflows',[]):
                for step in w.get('children',[]):
                    r=cs.get(base+'/logs/'+str(number)+'/'+str(step['id'])+'/download',timeout=45)
                    if r.status_code==200:evidence('ci-'+str(number)+'-'+step['name']+'.log',r.text)
            assert p['status']=='success','pipeline '+str(number)+' '+p['status']+'; inspect evidence logs'
            return p
        return None
    p=poll('pipeline completion',finished,timeout)
    steps=[s for w in p['workflows'] for s in w['children']]
    required=['clone','unit-test','daemonless-build','trivy-critical-gate','push-sign-gitops-dev']
    assert [s['name'] for s in steps]==required
    for s in steps:
        assert s['state']=='success' and s['exit_code']==0
        print('PASS CI '+s['name']+' exit=0',flush=True)
    _,_,v=content('dev');assert v['buildRevision']==sha
    digest=v['image']['digest'];assert re.fullmatch('sha256:[a-f0-9]{64}',digest)
    ref=REPO+'@'+digest
    assert run(['bin/crane','digest',REPO+':'+sha]).stdout.strip()==digest
    legacy_signature=REPO+':'+digest.replace(':','-')+'.sig'
    signature_manifest=json.loads(run(['bin/crane','manifest',legacy_signature]).stdout)
    assert any(l.get('annotations',{}).get('dev.cosignproject.cosign/signature') for l in signature_manifest['layers'])
    evidence('acceptance-signature-manifest.json',signature_manifest)
    verify=run(['bin/cosign','verify','--key','app/ci/cosign.pub','--insecure-ignore-tlog=true',ref])
    evidence('acceptance-cosign.json',verify.stdout)
    print('PASS zot scanned signed digest='+digest+'; GitOps dev buildRevision='+sha,flush=True)
    return digest

def sync_proof(env,digest,timeout,refresh=True):
    name='demo-app-'+env
    # Request fresh Git discovery, not an imperative sync or workload patch.
    if refresh:run(['kubectl','-n','argocd','annotate','application',name,'argocd.argoproj.io/refresh=hard','--overwrite'])
    def ready():
        a=kget('argocd','application',name);status=a.get('status',{})
        if status.get('sync',{}).get('status')!='Synced' or status.get('health',{}).get('status')!='Healthy':return None
        pods=kget(env,'pods')['items'];apps=[]
        for role in ['web','orders-api','orders-worker']:
            matches=[p for p in pods if p['metadata'].get('labels',{}).get('app')==role and not p['metadata'].get('deletionTimestamp')]
            ready_pods=[p for p in matches if any(c['type']=='Ready' and c['status']=='True' for c in p.get('status',{}).get('conditions',[]))]
            if not ready_pods:return None
            for p in ready_pods:
                if p['spec']['containers'][0]['image']!=REPO+'@'+digest:return None
                imageid=p['status']['containerStatuses'][0]['imageID']
                if digest not in imageid:return None
                apps.append({'pod':p['metadata']['name'],'role':role,'imageID':imageid})
        return {'environment':env,'sync':status['sync'],'health':status['health'],'pods':apps}
    proof=poll('Argo/live image '+env,ready,timeout);evidence('argocd-'+env+'-proof.json',proof)
    print('PASS Argo '+env+' Synced/Healthy; 3 ready app pods run '+digest,flush=True)
    return proof

def promote(env,digest):
    url,old,v=content(env)
    if v.get('image',{}).get('digest')!=digest:
        _,_,dev=content('dev');v['image']=dict(dev['image']);v['buildRevision']=dev['buildRevision']
        body={'branch':'main','sha':old['sha'],'message':env+': promote verified digest '+digest,'content':base64.b64encode(yaml.safe_dump(v).encode()).decode()}
        new=api(fs,'PUT',url,json=body);commit=new['commit']['sha']
        assert content(env)[2]['image']['digest']==digest
        evidence('promotion-'+env+'.json',{'commit':commit,'digest':digest,'method':'Git content API commit; no imperative image patch'})
        print('PASS Git promotion '+env+' commit='+commit,flush=True)
    else:print('PASS Git promotion '+env+' already at digest',flush=True)

def admission(digest):
    p=kget('default','clusterpolicy','lab-prod-signatures');assert p['spec']['validationFailureAction']=='Enforce'
    nonce=uuid.uuid4().hex[:10];signed_name='p6-signed-'+nonce;unsigned_name='p6-unsigned-'+nonce
    image=json.loads((ROOT/'devsecops/infra-images.json').read_text())['valkey']['image']
    dest=REG+'/lab/unsigned-p6:'+nonce
    run(['bin/crane','copy',image,dest]);unsigned_digest=run(['bin/crane','digest',dest]).stdout.strip();unsigned=REG+'/lab/unsigned-p6@'+unsigned_digest
    verify=run(['bin/cosign','verify','--key','app/ci/cosign.pub','--insecure-ignore-tlog=true',unsigned],check=False)
    assert verify.returncode!=0,'unsigned fixture unexpectedly has a signature'
    def pod(name,ref):
        return {'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'prod','labels':{'app.kubernetes.io/part-of':'demo-app'}},'spec':{'automountServiceAccountToken':False,'restartPolicy':'Never','securityContext':{'runAsNonRoot':True,'runAsUser':10001,'seccompProfile':{'type':'RuntimeDefault'}},'containers':[{'name':'proof','image':ref,'command':['python','-c','import time; time.sleep(120)'],'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}},'resources':{'requests':{'cpu':'10m','memory':'16Mi'},'limits':{'cpu':'100m','memory':'64Mi'}}}]}}
    try:
        good=run(['kubectl','create','-f','-'],input=yaml.safe_dump(pod(signed_name,REPO+'@'+digest)))
        run(['kubectl','-n','prod','wait','--for=condition=Ready','pod/'+signed_name,'--timeout=90s'])
        assert kget('prod','pod',signed_name)['status']['phase']=='Running'
        print('PASS signed prod image admitted and pod Running',flush=True)
        bad=run(['kubectl','create','-f','-'],input=yaml.safe_dump(pod(unsigned_name,unsigned)),check=False)
        evidence('unsigned-prod-rejection.log',bad.stdout+bad.stderr)
        assert bad.returncode!=0 and 'lab-prod-signatures' in bad.stderr and ('signature' in bad.stderr.lower() or 'verify' in bad.stderr.lower()),bad.stderr
        absent=run(['kubectl','-n','prod','get','pod',unsigned_name],check=False);assert absent.returncode!=0 and 'NotFound' in absent.stderr
        print('PASS unsigned zot image REJECTED in prod: '+bad.stderr.strip(),flush=True)
        evidence('admission-proof.json',{'signedImage':REPO+'@'+digest,'signedPodWasRunning':True,'unsignedImage':unsigned,'unsignedPodAbsent':True,'policy':'lab-prod-signatures','action':'Enforce'})
    finally:
        for name in [signed_name,unsigned_name]:run(['kubectl','-n','prod','delete','pod',name,'--ignore-not-found=true','--wait=true'],check=False)
        for name in [signed_name,unsigned_name]:
            assert run(['kubectl','-n','prod','get','pod',name],check=False).returncode!=0

def e2e(env,timeout):
    h='https://orders-'+env+'.192.168.150.200.sslip.io';s=requests.Session();s.verify=CA
    r=s.post(h+'/api/orders',json={'item':'synthetic P6 '+uuid.uuid4().hex,'quantity':2},timeout=45)
    assert r.status_code==201,'POST order HTTP '+str(r.status_code)+' '+r.text
    order=r.json();identifier=order['id'];print('PASS POST order 201 id='+identifier,flush=True)
    def fetched():
        q=s.get(h+'/api/orders/'+identifier,timeout=30)
        if q.status_code==200:
            obj=q.json()
            if obj.get('published') and obj.get('cached') and obj.get('cache',{}).get('id')==identifier:return obj
        return None
    got=poll('published and cached order',fetched,timeout)
    dbcode="import json; from services import database; c=database(); r=c.execute('SELECT id,item,quantity,environment,published FROM orders WHERE id=%s', ('"+identifier+"',)).fetchone(); print(json.dumps(r)); c.close()"
    row=json.loads(run(['kubectl','-n',env,'exec','deploy/orders-api','--','python','-c',dbcode]).stdout)
    assert row==[identifier,order['item'],2,env,True]
    logs=run(['kubectl','-n',env,'logs','deploy/orders-worker','--since=10m']).stdout
    records=[]
    for line in logs.splitlines():
        try:obj=json.loads(line)
        except json.JSONDecodeError:continue
        if obj.get('event')=='cached' and obj.get('id')==identifier:records.append(obj)
    assert records,'worker Kafka offset evidence missing';record=records[-1]
    kafka_code="import json; from services import kafka_options; from kafka import KafkaConsumer, TopicPartition; c=KafkaConsumer(group_id=None,enable_auto_commit=False,consumer_timeout_ms=20000,**kafka_options()); p=TopicPartition('demo-orders',"+str(record['partition'])+"); c.assign([p]); c.seek(p,"+str(record['offset'])+"); r=next(c); print(json.dumps({'topic':r.topic,'partition':r.partition,'offset':r.offset,'value':json.loads(r.value)})); c.close()"
    message=json.loads(run(['kubectl','-n',env,'exec','deploy/orders-api','--','python','-c',kafka_code]).stdout)
    assert message['value']==order and message['offset']==record['offset']
    cached=json.loads(run(['kubectl','-n',env,'exec','deploy/valkey','--','valkey-cli','GET','order:'+env+':'+identifier]).stdout)
    assert cached==order
    proof={'environment':env,'post':order,'postgresRow':row,'kafka':message,'workerCached':record,'valkey':cached,'get':got};evidence('e2e-'+env+'.json',proof)
    print('PASS PostgreSQL row published=true -> Kafka demo-orders partition='+str(record['partition'])+' offset='+str(record['offset'])+' -> worker -> Valkey -> GET cached=true id='+identifier,flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--trigger',action='store_true');parser.add_argument('--sha');parser.add_argument('--ci',action='store_true');parser.add_argument('--promote',action='store_true');parser.add_argument('--admission',action='store_true');parser.add_argument('--e2e',action='store_true');parser.add_argument('--verify-all',action='store_true');parser.add_argument('--read-only',action='store_true');parser.add_argument('--environment',default='dev',choices=['dev','staging','prod']);parser.add_argument('--timeout',type=int,default=600);args=parser.parse_args()
    print('PASS host/node resource preflight availableGiB='+str(guard()),flush=True)
    if args.read_only:
        assert not any([args.trigger,args.promote,args.admission,args.e2e,args.ci]), 'read-only cannot be combined with mutating checks'
        for env in ['dev','staging','prod']:
            sync_proof(env,content(env)[2]['image']['digest'],args.timeout,refresh=False)
            db=kget(env,'cluster','demo-db');assert db['status']['phase']=='Cluster in healthy state'
        p=kget('default','clusterpolicy','lab-prod-signatures');assert p['spec']['validationFailureAction']=='Enforce'
        print('PASS read-only live health, digests, three databases and signature enforcement',flush=True)
        return
    sha=trigger() if args.trigger else args.sha
    if args.trigger or args.ci:
        if not sha:sha=json.loads((E/'trigger.json').read_text())['sha']
        digest=ci_proof(sha,args.timeout);sync_proof('dev',digest,args.timeout)
    else:digest=content('dev')[2]['image']['digest']
    if args.promote:
        for env in ['staging','prod']:
            promote(env,digest)
            run(['python3','devsecops/install-gitops.py',env])
            sync_proof(env,digest,args.timeout)
    if args.verify_all:
        for env in ['dev','staging','prod']:sync_proof(env,content(env)[2]['image']['digest'],args.timeout)
    if args.admission:admission(digest)
    if args.e2e:e2e(args.environment,args.timeout)
    print('PASS requested P6 acceptance checks completed; availableGiB='+str(guard()),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('FAIL '+type(exc).__name__+': '+str(exc),file=sys.stderr,flush=True);sys.exit(1)
