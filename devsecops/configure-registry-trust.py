#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Trust/auth only the lab zot registry, rolling agents before servers."""
import json, pathlib, subprocess, time, yaml, os
os.environ['LC_ALL']='C'
root=pathlib.Path('/data/k8s-lab'); os.chdir(root)
p=root/'.secrets/p6'; p.mkdir(exist_ok=True); p.chmod(0o700)
registry='zot.192.168.150.200.sslip.io'
config={'mirrors':{registry:{'endpoint':['https://'+registry]}}, 'configs':{registry:{'auth':{'username':'lab','password':(root/'.secrets/p3/zot-password').read_text().strip()},'tls':{'ca_file':'/var/lib/rancher/k3s/lab-root-ca.crt'}}}}
private=p/'registries.yaml'; private.write_text(yaml.safe_dump(config)); private.chmod(0o600)
def run(args,**kw): return subprocess.run(args,check=True,**kw)
ssh=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(root/'.secrets/known_hosts'),'-i',str(root/'.secrets/lab_ed25519')]
scp=['scp','-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(root/'.secrets/known_hosts'),'-i',str(root/'.secrets/lab_ed25519')]
for suffix,ip in [('a1','21'),('a2','22'),('s1','11'),('s2','12'),('s3','13')]:
 node='lab-'+suffix; dest='lab@192.168.150.'+ip
 existing=run(ssh+[dest,'sudo test ! -f /etc/rancher/k3s/registries.yaml || sudo cat /etc/rancher/k3s/registries.yaml'],capture_output=True,text=True).stdout
 merged=yaml.safe_load(existing) or {}
 for key in config: merged.setdefault(key,{}).update(config[key])
 private.write_text(yaml.safe_dump(merged))
 run(scp+[str(private),dest+':/home/lab/p6-registries.yaml'],stdout=subprocess.DEVNULL)
 run(scp+[str(root/'.secrets/pki/root_ca.crt'),dest+':/home/lab/p6-root.crt'],stdout=subprocess.DEVNULL)
 service='k3s-agent' if suffix.startswith('a') else 'k3s'
 print('Rolling registry trust:',node,service,flush=True)
 run(ssh+[dest,'sudo install -d /etc/rancher/k3s /var/lib/rancher/k3s; sudo install -m 600 /home/lab/p6-registries.yaml /etc/rancher/k3s/registries.yaml; sudo install -m 644 /home/lab/p6-root.crt /var/lib/rancher/k3s/lab-root-ca.crt; rm /home/lab/p6-registries.yaml; sudo systemctl restart '+service])
 # Node Ready can remain true through a brief restart: prove new process AND guest API ready.
 time.sleep(8)
 run(ssh+[dest,'sudo systemctl is-active '+service])
 run(['kubectl','wait','node/'+node,'--for=condition=Ready','--timeout=300s'])
 run(['kubectl','get','--raw','/readyz?verbose'])
 if suffix.startswith('s'):
  run(['scripts/ssh-node.sh','lab-s2','sudo /home/lab/etcdctl --endpoints=https://127.0.0.1:2379 --cacert=/var/lib/rancher/k3s/server/tls/etcd/server-ca.crt --cert=/var/lib/rancher/k3s/server/tls/etcd/server-client.crt --key=/var/lib/rancher/k3s/server/tls/etcd/server-client.key endpoint health --cluster'])
 print('PASS trust rollout',node,flush=True)
run(['kubectl','get','nodes','-o','wide']); run(['free','-g'])
