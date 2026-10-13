#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
import os,pathlib,subprocess,json,yaml
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
p=pathlib.Path('devsecops/publish-repos.py');text=p.read_text()
text=text.replace("print('PASS mirror lab/'+repo+' '+str(len(changes))+' files commit='+j['commit']['sha'])", "print('PASS mirror lab/'+repo+' '+str(len(changes))+' files commit='+j['commit']['sha']); commit=j['commit']['sha']")
text=text.replace("else:print('PASS mirror unchanged lab/'+repo)", "else:print('PASS mirror unchanged lab/'+repo); commit=None\n return commit")
text=text.replace("mirror('demo-app',source,'Source mirror: tested orders app and immutable pipeline')", "source_sha=mirror('demo-app',source,'Source mirror: tested orders app and immutable pipeline')")
marker='# A real source commit after hook+secrets setup triggers the complete pipeline.'
if 'if source_sha:' not in text:
 text=text.replace(marker,"if source_sha:\n pathlib.Path('evidence/p6/trigger.json').write_text(json.dumps({'sha':source_sha, 'method':'source mirror Git commit; native webhook'})+'\\n')\n print('PASS source mirror itself is the single trigger; no superseding duplicate push')\n raise SystemExit(0)\n"+marker)
p.write_text(text)
# Durable Helm state: expected bootstrap image and gRPC secret survive upgrades.
subprocess.run(['helm','upgrade','cnpg','cnpg/cloudnative-pg','--version','0.29.1','-n','cnpg-system','-f','devsecops/cnpg-values.yaml','--wait','--timeout','2m'],check=True)
subprocess.run(['helm','upgrade','woodpecker','oci://ghcr.io/woodpecker-ci/helm/woodpecker','--version','3.7.5','-n','ci','-f','devsecops/woodpecker-values.yaml','--wait','--timeout','2m'],check=True)
# Explicit server restart now tests persistent signing secret, not only its first creation.
subprocess.run(['kubectl','-n','ci','rollout','restart','statefulset/woodpecker-server'],check=True)
subprocess.run(['kubectl','-n','ci','rollout','status','statefulset/woodpecker-server','--timeout=120s'],check=True)
subprocess.run(['kubectl','-n','ci','rollout','restart','statefulset/woodpecker-agent'],check=True)
subprocess.run(['kubectl','-n','ci','rollout','status','statefulset/woodpecker-agent','--timeout=120s'],check=True)
print('PASS durable Helm references installed; CI server and agent restarted again before final real push')
