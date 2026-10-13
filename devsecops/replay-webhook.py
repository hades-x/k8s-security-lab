#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Diagnostic replay of a real source commit; not automatic push acceptance."""
import requests,pathlib,os,json
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
s=requests.Session();s.verify='.secrets/pki/root_ca.crt';s.headers['Authorization']='token '+pathlib.Path('.secrets/p6/forgejo-token').read_text().strip()
F='https://forgejo.192.168.150.200.sslip.io';repo=s.get(F+'/api/v1/repos/lab/demo-app').json();sha=s.get(F+'/api/v1/repos/lab/demo-app/branches/main').json()['commit']['id'];commit=s.get(F+'/api/v1/repos/lab/demo-app/git/commits/'+sha).json();user=s.get(F+'/api/v1/users/lab-admin').json();hooks=s.get(F+'/api/v1/repos/lab/demo-app/hooks').json();url=next(x['config']['url'] for x in hooks if x['type']=='forgejo')
head={'id':sha,'message':commit['commit']['message'],'url':commit['html_url'],'timestamp':commit['commit']['committer']['date'],'author':commit['commit']['author'],'committer':commit['commit']['committer'],'added':[],'removed':[],'modified':['BUILD_TRIGGER']}
for name in ['author','committer']:head[name]['username']='lab-admin'
payload={'ref':'refs/heads/main','before':commit['parents'][0]['sha'],'after':sha,'compare_url':repo['html_url']+'/compare/'+commit['parents'][0]['sha']+'...'+sha,'commits':[head],'head_commit':head,'repository':repo,'pusher':user,'sender':user}
r=requests.post(url,json=payload,headers={'X-Gitea-Event':'push','X-Forgejo-Event':'push','Content-Type':'application/json'},verify=s.verify,timeout=45)
print('Diagnostic real-commit webhook replay',r.status_code,'commit='+sha);r.raise_for_status()
