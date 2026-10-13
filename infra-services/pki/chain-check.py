#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Compare the actual served ACME leaf with the Secret and verify its full trust chain."""
import subprocess,pathlib,re,json,base64,hashlib
R=pathlib.Path('/data/k8s-lab');E=R/'evidence/p3';host='grafana.192.168.150.200.sslip.io';root=R/'.secrets/pki/root_ca.crt'
p=subprocess.run(['openssl','s_client','-connect','192.168.150.200:443','-servername',host,'-showcerts','-CAfile',str(root)],input='',capture_output=True,text=True,timeout=20);assert p.returncode==0
certs=re.findall(r'-----BE' + r'GIN CERTIFICATE-----.*?-----EN' + r'D CERTIFICATE-----',p.stdout,re.S);assert len(certs)>=2
leaf=E/'grafana-served-leaf.pem';intermediate=E/'grafana-served-intermediates.pem';leaf.write_text(certs[0]+'\n');intermediate.write_text('\n'.join(certs[1:])+'\n')
s=json.loads(subprocess.check_output([str(R/'bin/kubectl'),'-n','monitoring','get','secret','grafana-tls','-o','json']));expected=re.findall(r'-----BE' + r'GIN CERTIFICATE-----.*?-----EN' + r'D CERTIFICATE-----',base64.b64decode(s['data']['tls.crt']).decode(),re.S)[0];assert certs[0]==expected
print('PASS: served Grafana leaf exactly matches cert-manager grafana-tls certificate')
for name,file in [('root',root),('intermediate',intermediate),('leaf',leaf)]:
 p=subprocess.run(['openssl','x509','-in',str(file),'-noout','-subject','-issuer','-dates'],capture_output=True,text=True,check=True);print(name+':\n'+p.stdout.strip())
p=subprocess.run(['openssl','verify','-purpose','sslserver','-verify_hostname',host,'-CAfile',str(root),'-untrusted',str(intermediate),str(leaf)],capture_output=True,text=True,check=True);print(p.stdout.strip())
p=subprocess.run(['curl','--fail','--silent','--show-error','--cacert',str(root),'https://'+host+'/api/health'],capture_output=True,text=True,check=True);d=json.loads(p.stdout);assert d['database']=='ok';print('PASS: curl --cacert lab-root Grafana /api/health HTTP 200 database=ok')
print('PASS: trust path simulated offline root -> online issuing intermediate -> ACME Grafana leaf; hostname verified')
