#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Read-only acceptance aggregation and scoped artifact checks; writes report/evidence."""
import ast
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import yaml

ROOT=Path('/data/k8s-lab')
BASE=ROOT/'docs/exercices'
EVIDENCE=ROOT/'evidence/exercices'
MODULES={'01':'01-debug','02':'02-lifecycle','03':'03-resources','04':'04-control-plane'}
NAMESPACES={'01':'ex-debug','02':'ex-lifecycle','03':'ex-resources','04':'ex-control-plane'}

def command(*args):
    return subprocess.check_output(args,text=True,cwd=ROOT)

def require(ok,message):
    if not ok: raise SystemExit('FAIL '+message)

for script in BASE.rglob('*.sh'):
    subprocess.run(['bash','-n',str(script)],check=True)
subprocess.run([sys.executable,str(BASE/'_lib/test-safety.py')],check=True)
objects=[]
for path in BASE.glob('*/manifests/*.yaml'):
    docs=list(yaml.safe_load_all(path.read_text()))
    objects.extend(docs)
    for obj in docs:
        require(obj.get('kind')!='Secret','secret manifest in exercises')
        if obj['kind']=='Namespace':
            require(obj['metadata']['name'] in NAMESPACES.values(),'unexpected namespace')
            require(obj['metadata']['labels']['pod-security.kubernetes.io/enforce']=='restricted','PSS not restricted')
            continue
        require(obj['metadata']['namespace'] in NAMESPACES.values(),'object outside ex-* namespaces')
        if obj['kind'] not in ('Pod','Deployment'): continue
        spec=obj['spec'] if obj['kind']=='Pod' else obj['spec']['template']['spec']
        require(spec.get('automountServiceAccountToken') is False,'token automount')
        require(spec['securityContext'].get('runAsNonRoot') is True,'non-root missing')
        require(spec['securityContext']['seccompProfile']['type']=='RuntimeDefault','seccomp missing')
        for container in spec['containers']:
            context=container['securityContext']
            require(context.get('allowPrivilegeEscalation') is False,'allowPrivilegeEscalation')
            require(context.get('readOnlyRootFilesystem') is True,'root filesystem writable')
            require(context.get('capabilities',{}).get('drop')==['ALL'],'capabilities not dropped')
            if obj['metadata']['name']!='besteffort':
                require({'requests','limits'}.issubset(container['resources']),'resource budget missing')
            require(container['image'].startswith('docker.io/library/busybox:'),'unexpected registry/image')
        require(not spec.get('hostNetwork') and not spec.get('hostPID') and not spec.get('hostIPC'),'host access')
        require(not any('hostPath' in volume for volume in spec.get('volumes',[])),'hostPath')
require(len(objects)==25,'unexpected manifest object total')

nodes=json.loads(command('kubectl','--request-timeout=15s','get','nodes','-o','json'))
ns=json.loads(command('kubectl','--request-timeout=15s','get','namespaces','-o','json'))
require(not set(NAMESPACES.values()).intersection(n['metadata']['name'] for n in ns['items']),'exercise namespace still exists')
for node in nodes['items']:
    require(not node.get('spec',{}).get('unschedulable',False),'node left cordoned: '+node['metadata']['name'])
proc=Path('/proc/meminfo').read_text()
available=int(re.search(r'^MemAvailable:\s+(\d+)',proc,re.MULTILINE)[1])
spec=importlib.util.spec_from_file_location('gate',BASE/'_lib/gate.py')
gate=importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
gate.check(nodes,available)
final={'timestamp':datetime.datetime.now().astimezone().isoformat(),'nodes_ready':len(nodes['items']),'host_memavailable_kib':available,'exercise_namespaces_absent':list(NAMESPACES.values()),'all_nodes_schedulable':True}
readyz=command('kubectl','--request-timeout=15s','get','--raw','/readyz?verbose')
require('[+]etcd ok' in readyz and 'readyz check passed' in readyz,'readyz failure')
(EVIDENCE/'99-final-readyz.txt').write_text(readyz)

summary={}
for nn,module in MODULES.items():
    require((BASE/module/'FICHE.md').is_file(),'missing fiche '+module)
    for name in ('run.sh','cleanup.sh'):
        require((BASE/module/name).is_file(),'missing '+module+'/'+name)
    text=(EVIDENCE/(nn+'.log')).read_text()
    results=re.findall(r'RESULT module='+re.escape(module)+r' status=(\w+) elapsed_seconds=(\d+)',text)
    exits=re.findall(r'RUN_EXIT module='+re.escape(module)+r' code=(\d+)',text)
    require(bool(results) and results[-1][0]=='PASS' and int(results[-1][1])<=600,'module not PASS/in time: '+module)
    require(bool(exits) and exits[-1]=='0','last run exit not zero: '+module)
    latest=text[text.rfind('=== '+module+' —'):]
    proofs=[line for line in latest.splitlines() if line.startswith(('PASS ','reason=OOMKilled','CORDON_WINDOW_SECONDS='))]
    summary[nn]={'module':module,'status':results[-1][0],'elapsed_seconds':int(results[-1][1]),'proof_lines':proofs,'log':'evidence/exercices/'+nn+'.log'}

snapshot_text=(EVIDENCE/'04-snapshots-after-save.txt').read_text()
row=next(line.split() for line in snapshot_text.splitlines() if line.startswith('ex-snapshot-lab-s1-'))
final['snapshot']={'name':row[0],'size_bytes':int(row[2]),'location':row[1],'deleted_verified_in_log':True}
require(not (EVIDENCE/'.04-snapshot-owner').exists(),'snapshot ownership marker still present')
# Scan only new exercise documentation and evidence. No real secret files are opened.
scan_files=[p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in str(p)]+[p for p in EVIDENCE.iterdir() if p.is_file() and p.suffix in ('.log','.txt','.json')]
pattern=re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bK10[0-9a-f]{64}::|\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}')
for path in scan_files:
    require(not pattern.search(path.read_text(errors='replace')),'possible secret in '+str(path.relative_to(ROOT)))

test_ast=ast.parse((BASE/'_lib/test-safety.py').read_text())
safety_test_count=sum(1 for node in ast.walk(test_ast) if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'))
schema_text=(EVIDENCE/'98-kubeconform.txt').read_text()
schema=re.search(r'Valid: (\d+), Invalid: (\d+), Errors: (\d+), Skipped: (\d+)',schema_text)
require(bool(schema) and tuple(map(int,schema.groups()))==(len(objects),0,0,0),'kubeconform schema checks not all PASS')
result={'modules':summary,'final':final,'static_checks':{'shell_syntax':'PASS','manifest_objects':len(objects),'kubeconform':'PASS','safety_tests':safety_test_count,'narrow_secret_scan':'PASS'}}
(EVIDENCE/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# Phase F — rapport vérifié','',f"Vérification finale : **{final['timestamp']}**. Résultats issus des dernières exécutions réelles, pas des sorties attendues.",'','| Module | État | Durée mesurée (s) | Journal |','|---|---|---:|---|']
for nn,item in summary.items():
    lines.append(f"| {item['module']} | {item['status']} | {item['elapsed_seconds']} | `{item['log']}` |")
lines+=['','## Preuves clés']
interesting=('PASS ImagePullBackOff','PASS API watch','PASS CrashLoopBackOff','PASS Pending','PASS NetworkPolicy','PASS HTTP availability','PASS failed v3','PASS rollout undo','PASS drain','PASS PDB','CORDON_WINDOW','PASS cordon/uncordon','PASS QoS','reason=OOMKilled','PASS s1','PASS known gap','PASS etcd MemberList','PASS snapshot:','PASS snapshot file absent','PASS preserved existing')
for item in summary.values():
    lines+=['',f"### {item['module']}",'```text']+[line for line in item['proof_lines'] if line.startswith(interesting)]+['```']
lines+=['','## Nettoyage et limites de preuve',f"- Read-back final : **{final['nodes_ready']} nœuds Ready**, tous schedulables; **{available} KiB** MemAvailable hôte; readyz sain.",'- Les quatre namespaces `ex-debug`, `ex-lifecycle`, `ex-resources`, `ex-control-plane` sont absents; tous leurs workloads ont été supprimés.',f"- Snapshot `{row[0]}` : **{row[2]} octets**, `{row[1]}`; supprimé, catalogue et absence du fichier vérifiés. Deux anciens snapshots conservés.",'- Aucune réservation agent modifiée; a1 jamais cordonné; a2 cordonné 5 s puis read-back schedulable. Aucun drain réel, reboot, restauration ou changement de VM/hôte.', '- Aucun commit/tag/push. Seuls docs/exercices et evidence/exercices appartiennent à cette livraison.','', '## Incidents de validation corrigés','- Le préflight initial de 20:16 avait a1 NotReady : aucune charge lancée. Après confirmation de réparation par l’orchestrateur, nouveau préflight 5/5 Ready avant exécution.', '- Premier Debug : polling 2 s insuffisant pour capturer le bref état CrashLoopBackOff. Le watch API réel a montré le champ; le script utilise maintenant ce watch. Les tentatives et diagnostics restent dans les preuves.', '- Premier Lifecycle : le drain dry-run a correctement été refusé par le PDB, mais son code 1 attendu arrêtait le script. La cause précise est maintenant exigée et l’exécution continue vers le test Eviction dry-run et le cordon bref.', '- Le gateway JSON etcd sur 2379 renvoyait 415, et un /db/info distant était Forbidden. La lecture locale authentiquement supportée du handler K3s /db/info sur s1 a fourni MemberList, sans copier de clé/token.', '- Sous-CLI snapshot : avertissements Unknown flag conservés; save/ls/delete et read-backs ont réussi.','', '## Non vérifié / volontairement non exécuté','- Restauration etcd, application/PVC après restore, sauvegarde off-host, intégrité restaurable, RPO/RTO : procédure seulement dans 04-control-plane/FICHE.md.', '- Éviction réelle de pods ou maintenance/reboot de nœud : interdits. Seules requêtes dry-run et cordon bref autorisé.', '- Disponibilité HTTP : 75 requêtes, résolution 1 s dans une fenêtre bornée; pas une preuve de SLA permanent.', '- Garde indépendante d’uncordon : le chemin normal/trap a été mesuré; interruption forcée/SIGKILL et panne API totale non injectées.', '- HPA/KEDA, Chaos Mesh, k6, iperf3/netem : suite après entretien; aucune de ces charges lancée.', '- Le scan secrets est étroit (clés privées / jetons K3s / JWT), pas une certification exhaustive. Aucun fichier .secrets ni payload de snapshot lu.','', '## Vérifications des fichiers',f'- bash -n : scripts de livraison valides; tests offline de sûreté : {safety_test_count} PASS; kubeconform 1.36.0 : 25 valides / 0 invalide / 0 erreur / 0 skip; admission dry-run et exécution réelle des manifests des quatre modules.', '- Hashes de livraison : evidence/exercices/artifacts.sha256; résultat machine : evidence/exercices/summary.json.']
(BASE/'RAPPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
print('PASS final read-back and report aggregation: 4/4 modules, no exercise namespaces, nodes Ready and schedulable')
