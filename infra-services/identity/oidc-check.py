#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Direct grant is a federation/token smoke test, not Grafana browser SSO proof."""
import json,pathlib,urllib.request,urllib.parse,ssl,base64
R=pathlib.Path('/data/k8s-lab');ctx=ssl.create_default_context(cafile=str(R/'.secrets/pki/root_ca.crt'))
base='https://keycloak.192.168.150.200.sslip.io/realms/lab'
def request(url,data=None):
 with urllib.request.urlopen(urllib.request.Request(url,data=data),context=ctx,timeout=30) as r:return json.load(r)
discovery=request(base+'/.well-known/openid-configuration');assert discovery['issuer']==base
for user,group in [('lab-admin','lab-admins'),('lab-analyst','soc-analysts'),('lab-dev','devs')]:
 data=urllib.parse.urlencode({'grant_type':'password','client_id':'lab-cli','username':user,'password':(R/'.secrets/p3'/f'{user}-password').read_text().strip()}).encode()
 token=request(discovery['token_endpoint'],data);assert token.get('access_token')
 claims=json.loads(base64.urlsafe_b64decode(token['access_token'].split('.')[1]+'=='))
 assert claims['iss']==base and group in claims.get('groups',[]),f'missing group {group}'
 print(f'PASS: LDAP direct grant for {user}; group {group}; discovery issuer matches')
print('Scope: LDAP federation/direct-grant tokens only; completed app SSO is verified separately by sso-session-check.py')
