
if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Verified-CA loopback port-forward client for SOC admin tests.

Only hostname checking is disabled, because the tunnel uses loopback rather than
its Kubernetes service SAN. Credentials are read from private files, never logged.
"""
from pathlib import Path
import base64
import json
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path('/data/k8s-lab')

class APIError(RuntimeError):
    def __init__(self, method, path, status, body):
        self.status = status
        self.body = body
        super().__init__(f'{method} {path}: HTTP {status}: {body[:1600]}')

class OpenSearch:
    def __enter__(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        self.url = f'https://127.0.0.1:{port}'
        self.log = open(ROOT/'.secrets/p4-api-portforward.log', 'ab')
        self.pf = subprocess.Popen(['kubectl','-n','opensearch','port-forward','--address','127.0.0.1','svc/soc',f'{port}:9200'], stdout=self.log, stderr=self.log)
        self.ctx = ssl.create_default_context(cafile=str(ROOT/'.secrets/opensearch-ca.crt'))
        self.ctx.check_hostname = False
        password = (ROOT/'.secrets/opensearch-admin.password').read_text()
        self.auth = 'Basic ' + base64.b64encode(('admin:'+password).encode()).decode()
        for _ in range(60):
            try:
                self.request('GET','/')
                return self
            except OSError:
                time.sleep(1)
            except APIError:
                self.__exit__(None,None,None)
                raise
        self.__exit__(None,None,None)
        raise RuntimeError('OpenSearch port-forward did not become ready')

    def request(self, method, path, data=None, content_type='application/json'):
        payload = data if isinstance(data, bytes) else (None if data is None else json.dumps(data).encode())
        req = urllib.request.Request(self.url+path, data=payload, method=method,
                headers={'Authorization':self.auth,'Content-Type':content_type})
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=90) as response:
                body = response.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as error:
            body = error.read().decode(errors='replace')
            if '/_security/api/' in path:
                body = 'Security API response suppressed'
            raise APIError(method,path,error.code,body) from None

    def __exit__(self, *args):
        self.pf.terminate()
        try:
            self.pf.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.pf.kill()
            self.pf.wait()
        self.log.close()
