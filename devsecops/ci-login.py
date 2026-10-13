#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Complete Forgejo OAuth login and save CI API token, never emit secrets."""
import os,requests,pathlib,re,json
os.chdir('/data/k8s-lab');os.environ['LC_ALL']='C'
F='https://forgejo.192.168.150.200.sslip.io'; C='https://ci.192.168.150.200.sslip.io'
s=requests.Session();s.verify='.secrets/pki/root_ca.crt'
def csrf(text):
 m=re.search(r'name="_csrf"[^>]*value="([^"]+)"',text) or re.search(r'name="_csrf" content="([^"]+)"',text)
 if not m: return ''  # Forgejo 15 uses origin-based CSRF checks.
 return m.group(1)
r=s.get(F+'/user/login');r.raise_for_status()
r=s.post(F+'/user/login',data={'_csrf':csrf(r.text),'user_name':'lab-admin','password':pathlib.Path('.secrets/forgejo-admin-password').read_text().strip()});r.raise_for_status()
assert '/user/login' not in r.url,'Forgejo form login failed'
print('PASS Forgejo authenticated session')
r=s.get(C+'/authorize');r.raise_for_status()
if r.url.startswith(F):
 fields=dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"',r.text))
 fields['_csrf']=csrf(r.text);fields['granted']='true'
 # Forgejo consent grants via its explicit form endpoint.
 r=s.post(F+'/login/oauth/grant',data=fields);r.raise_for_status()
assert r.url.startswith(C),'OAuth did not return to CI'
r=s.get(C+'/api/user');r.raise_for_status();u=r.json();assert u['login']=='lab-admin', 'CI session missing'
print('PASS Woodpecker OAuth authenticated lab-admin; admin='+str(u.get('admin')))
config=s.get(C+'/web-config.js');config.raise_for_status()
s.headers['X-CSRF-TOKEN']=re.search(r'WOODPECKER_CSRF = "([^"]+)"',config.text).group(1)
r=s.post(C+'/api/user/token')
r.raise_for_status(); token=r.json() if 'json' in r.headers.get('Content-Type','') else r.text
if isinstance(token,dict):token=token.get('token')
assert isinstance(token,str) and len(token)>20,'token missing'
p=pathlib.Path('.secrets/p6/woodpecker-token');p.write_text(token);p.chmod(0o600)
print('PASS Woodpecker API token stored privately')
# Validate the saved token, not just the login cookie.
s2=requests.Session();s2.verify=s.verify;s2.headers['Authorization']='Bearer '+token
r=s2.get(C+'/api/user');r.raise_for_status();assert r.json()['login']=='lab-admin'
print('PASS saved Woodpecker API token authenticates')
