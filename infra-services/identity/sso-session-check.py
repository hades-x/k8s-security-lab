#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Complete real LDAP-backed authorization-code logins without logging secrets."""
import pathlib,requests,urllib.parse,json,sys
from html.parser import HTMLParser
R=pathlib.Path('/data/k8s-lab');VIP='192.168.150.200.sslip.io'
class Form(HTMLParser):
 def __init__(self):super().__init__();self.action=None;self.fields={}
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='form' and a.get('id')=='kc-form-login':self.action=a.get('action')
  if tag=='input' and a.get('type')=='hidden' and a.get('name'):self.fields[a['name']]=a.get('value','')
def login(app,start,user,proof):
 s=requests.Session();s.verify=str(R/'.secrets/pki/root_ca.crt');s.trust_env=False
 r=s.get(start,timeout=30,allow_redirects=False);assert r.status_code in (302,303,307,308)
 first=urllib.parse.urljoin(start,r.headers['Location']);assert urllib.parse.urlparse(first).hostname=='keycloak.'+VIP
 q=urllib.parse.parse_qs(urllib.parse.urlparse(first).query);assert q['client_id']==[app] and q['response_type']==['code'] and q['code_challenge_method']==['S256'], 'OAuth code/PKCE contract mismatch'
 print(f'PASS: {app} HTTP {r.status_code} authorization redirect to Keycloak; response_type=code')
 r=s.get(first,timeout=30);assert r.status_code==200
 f=Form();f.feed(r.text);assert f.action,'Keycloak login form missing'
 formurl=urllib.parse.urljoin(r.url,f.action);assert urllib.parse.urlparse(formurl).hostname=='keycloak.'+VIP
 fields=f.fields|{'username':user,'password':(R/'.secrets/p3'/f'{user}-password').read_text().strip(),'credentialId':''}
 r=s.post(formurl,data=fields,timeout=30,allow_redirects=False);assert r.status_code in (302,303,307,308),'LDAP login did not redirect'
 for _ in range(12):
  u=urllib.parse.urljoin(r.url,r.headers.get('Location',''));host=urllib.parse.urlparse(u).hostname
  assert host in ['keycloak.'+VIP,app+'.'+VIP], 'unexpected redirect host'
  r=s.get(u,timeout=30,allow_redirects=False)
  if r.status_code not in (302,303,307,308):break
 assert r.status_code==200,'callback did not yield success';print('OAuth callback terminal path: '+urllib.parse.urlparse(r.url).path)
 p=s.get(proof,timeout=30,allow_redirects=False);assert p.status_code==200, f'proof endpoint HTTP {p.status_code}'
 if app=='forgejo':
  assert user in p.text, 'authenticated settings missing LDAP user'
  account=s.get('https://forgejo.'+VIP+'/user/settings/account',timeout=30,allow_redirects=False);assert account.status_code==200 and user+'@k8slab.lab' in account.text, 'authenticated account missing LDAP email'
  print(f'PASS: Forgejo completed LDAP OAuth code flow; authenticated /user/settings HTTP 200 user={user} email={user}@k8slab.lab');return {'login':user}
 d=p.json()
 if app=='grafana':assert d['login']==user, 'wrong Grafana login: '+d['login'];print(f'PASS: Grafana completed LDAP OAuth code flow; /api/user HTTP 200 login={d["login"]} email={d.get("email")}')
 elif app=='forgejo':
  assert d['login']==user, 'wrong Forgejo username';print(f'PASS: Forgejo completed LDAP OAuth code flow; /api/v1/user HTTP 200 login={d["login"]}')
 elif app=='argocd':
  assert d.get('loggedIn') and d.get('username')==user+'@k8slab.lab' and d.get('groups')==['soc-analysts'] and d.get('iss')=='https://keycloak.'+VIP+'/realms/lab';print(f'PASS: Argo CD completed LDAP OAuth code flow; /api/v1/session/userinfo HTTP 200 loggedIn={d["loggedIn"]} username={d["username"]} groups={d["groups"]} issuer={d.get("iss")}')
 return d
if __name__=='__main__':
 try:
  app=sys.argv[1] if len(sys.argv)>1 else 'grafana'
  starts={'forgejo':'/user/oauth2/keycloak','grafana':'/login/generic_oauth','argocd':'/auth/login?return_url=https%3A%2F%2Fargocd.'+VIP+'%2F'}
  proofs={'forgejo':'/user/settings','grafana':'/api/user','argocd':'/api/v1/session/userinfo'}
  login(app,'https://'+app+'.'+VIP+starts[app],'lab-analyst','https://'+app+'.'+VIP+proofs[app])
 except Exception as e:print('FAIL: OAuth code-flow assertion/transport: '+type(e).__name__+(': '+str(e) if isinstance(e,AssertionError) else ' (details withheld)'),file=sys.stderr);sys.exit(1)
