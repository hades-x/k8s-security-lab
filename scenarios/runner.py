#!/usr/bin/env python3
"""Bounded, synthetic, namespace-owned Phase E detection rehearsals."""
import ipaddress
import re
import copy

def scoped_query(query, state, rule):
    result = copy.deepcopy(query)
    filters = result['query']['bool']['filter']
    filters.append({'range': {'@timestamp': {'gte': state['started'], 'lte': 'now'}}})
    if rule == 'falco-shell':
        filters.append({'wildcard': {'output': '*' + state['run_id'] + '*'}})
        filters.append({'term': {'output_fields.container.id': state['container_id'][:12]}})
    elif rule == 'audit-forbidden-secret':
        filters.append({'term': {'objectRef.namespace': state['namespace']}})
        filters.append({'term': {'user.username': 'system:serviceaccount:' + state['namespace'] + ':no-rights'}})
    elif rule == 'notice-scan':
        filters.append({'term': {'src': state['source_ip']}})
    else:
        filters.append({'term': {'id.orig_h': state['source_ip']}})
    return result

IMAGE = 'docker.io/library/python:3.13.9-alpine3.22@sha256:e5fa639e49b85986c4481e28faa2564b45aa8021413f31026c3856e5911618b1'

def owned_namespace(value):
    if not re.fullmatch(r'scen-e0[1-5]-(source|target)', value):
        raise ValueError('Namespace outside Phase E scope')
    return value

def pod_manifest(namespace, name, node, run_id, command=None):
    owned_namespace(namespace)
    return {'apiVersion': 'v1', 'kind': 'Pod',
            'metadata': {'name': name, 'namespace': namespace,
                         'labels': {'phase-e-run': run_id, 'app': name}},
            'spec': {'automountServiceAccountToken': False, 'restartPolicy': 'Never',
                     'nodeSelector': {'kubernetes.io/hostname': node},
                     'activeDeadlineSeconds': 1200,
                     'securityContext': {'runAsNonRoot': True, 'runAsUser': 1000,
                                         'seccompProfile': {'type': 'RuntimeDefault'}},
                     'containers': [{'name': name, 'image': IMAGE,
                         'imagePullPolicy': 'IfNotPresent',
                         'command': command or ['python3', '-c', 'import time; time.sleep(1200)'],
                         'resources': {'requests': {'cpu': '10m', 'memory': '32Mi'},
                                       'limits': {'cpu': '100m', 'memory': '96Mi'}},
                         'securityContext': {'allowPrivilegeEscalation': False,
                             'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}}}]}}

NETWORKS = tuple(ipaddress.ip_network(x) for x in ('192.168.150.0/24', '10.42.0.0/16', '10.43.0.0/16'))

def lab_ip(value):
    address = ipaddress.ip_address(value)
    if value == '192.168.150.1' or not any(address in net for net in NETWORKS):
        raise ValueError('Refusing non-lab or host target')
    return value

import argparse
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import uuid

ROOT = Path(__file__).resolve().parent.parent
NAMES = {'01': '01-port-scan', '02': '02-dns-intel', '03': '03-lateral-netpol',
         '04': '04-shell-admission', '05': '05-forbidden-secret'}
HTTP_SERVER = '''from http.server import HTTPServer, BaseHTTPRequestHandler
class H(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200); self.end_headers(); self.wfile.write(b'synthetic lab only')
 def log_message(self, *args): pass
HTTPServer(('0.0.0.0',8080),H).serve_forever()
'''
DNS_SERVER = '''import socket
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.bind(('0.0.0.0',5353))
while True:
 data,addr=s.recvfrom(4096)
 if len(data)>=12: s.sendto(data[:2]+b'\\x81\\x83'+data[4:6]+b'\\x00'*6+data[12:],addr)
'''
FORBIDDEN_QUERY = {'size': 0, 'query': {'bool': {'filter': [
    {'terms': {'verb': ['get', 'list']}}, {'term': {'objectRef.resource': 'secrets'}},
    {'term': {'responseStatus.code': 403}},
    {'wildcard': {'objectRef.namespace': 'scen-*'}},
    {'range': {'@timestamp': {'gte': 'now-5m', 'lte': 'now'}}}]}}}


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = value if isinstance(value, str) else json.dumps(value, indent=2) + '\n'
    path.write_text(text)


def command(args, *, data=None, check=True, timeout=90):
    p = subprocess.run(args, input=(json.dumps(data) if isinstance(data, dict) else data),
                       text=True, capture_output=True, timeout=timeout, cwd=ROOT)
    if check and p.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(args[:6]) + '\n' + p.stdout + p.stderr)
    return p


def kjson(*args):
    return json.loads(command(['kubectl', *args, '-o', 'json']).stdout)


def preflight():
    result = command(['make', '-s', 'status-quick'], check=False, timeout=150)
    print(result.stdout, flush=True)
    if result.returncode:
        raise RuntimeError('status-quick failed; no scenario load allowed')
    available_kib = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:')))
    if available_kib < 4 * 1024 * 1024:
        raise RuntimeError('Host RAM available < 4 GiB; scenario aborted')
    nodes = kjson('get', 'nodes')['items']
    if len(nodes) != 5 or any(not any(c['type'] == 'Ready' and c['status'] == 'True'
                                    for c in n['status']['conditions']) for n in nodes):
        raise RuntimeError('A node is NotReady or absent; scenario aborted')
    endpoint = command(['kubectl', 'config', 'view', '--minify', '-o',
                        'jsonpath={.clusters[0].cluster.server}']).stdout
    host = urllib.parse.urlsplit(endpoint).hostname
    if host not in ('127.0.0.1', 'localhost'):
        lab_ip(host)
        if ipaddress.ip_address(host) not in NETWORKS[0]:
            raise RuntimeError('Not a lab API endpoint')
    dependencies = {'kafka': ['soc-mixed-'], 'opensearch': ['soc-nodes-'],
                    'pki': ['step-ca-'], 's3': ['garage-'], 'monitoring': ['loki-'],
                    'prod': ['demo-db-']}
    for ns, prefixes in dependencies.items():
        pods = kjson('-n', ns, 'get', 'pods')['items']
        selected = [p for p in pods if any(p['metadata']['name'].startswith(prefix) for prefix in prefixes)]
        if not selected or any(not any(c['type'] == 'Ready' and c['status'] == 'True'
                                      for c in p.get('status', {}).get('conditions', [])) for p in selected):
            raise RuntimeError('Recovery dependency not Ready in ' + ns + '; no events generated')
    print('PASS preflight: five Ready nodes; recovery dependencies Ready; MemAvailable >= 4 GiB; lab API', flush=True)


def apply(obj, evidence, basename):
    raise RuntimeError('PUBLIC_RUNTIME_DISABLED: unsafe scenario mutation helper disabled pending fail-closed ownership/API adaptation')
    ns = obj.get('metadata', {}).get('namespace')
    if ns:
        owned_namespace(ns)
    elif obj['kind'] != 'Namespace':
        raise RuntimeError('Only owned Namespace or namespaced objects may be applied')
    else:
        owned_namespace(obj['metadata']['name'])
    save(evidence / 'manifests' / (basename + '.json'), obj)
    result = command(['kubectl', 'apply', '-f', '-'], data=obj)
    print(result.stdout.strip(), flush=True)
    kind = obj['kind']
    target = command(['kubectl', *(['-n', ns] if ns else []), 'get', kind,
                      obj['metadata']['name'], '-o', 'json'])
    live = json.loads(target.stdout)
    if kind not in ('Secret',):
        save(evidence / 'readback' / (basename + '.json'), live)
    return live


def state_paths(number):
    evidence = ROOT / 'evidence' / 'scenarios' / number
    return evidence, evidence / 'state.json'


def load_state(number):
    evidence, path = state_paths(number)
    state = json.loads(path.read_text())
    owned_namespace(state['namespace'])
    return evidence, state


def assert_owned(state):
    for ns, uid in state['namespaces'].items():
        live = kjson('get', 'namespace', owned_namespace(ns))
        if live['metadata']['uid'] != uid or live['metadata']['labels'].get('phase-e-run') != state['run_id']:
            raise RuntimeError('Namespace ownership changed; refusing mutation')


def namespace(state, name, evidence):
    raise RuntimeError('PUBLIC_RUNTIME_DISABLED: unsafe scenario mutation helper disabled pending fail-closed ownership/API adaptation')
    owned_namespace(name)
    exists = command(['kubectl', 'get', 'namespace', name], check=False)
    if exists.returncode == 0:
        raise RuntimeError('Namespace exists: refuse to adopt ' + name)
    obj = {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': name,
           'labels': {'phase-e-run': state['run_id'],
           'pod-security.kubernetes.io/enforce': 'restricted',
           'pod-security.kubernetes.io/enforce-version': 'v1.36',
           'pod-security.kubernetes.io/audit': 'restricted',
           'pod-security.kubernetes.io/warn': 'restricted'}}}
    live = apply(obj, evidence, name)
    state['namespaces'][name] = live['metadata']['uid']
    save(evidence / 'state.json', state)


def pod(state, namespace_name, name, node, evidence, code=None, api_identity=False):
    manifest = pod_manifest(namespace_name, name, node, state['run_id'],
                            ['python3', '-u', '-c', code] if code else None)
    if api_identity:
        manifest['spec']['serviceAccountName'] = 'no-rights'
        manifest['spec']['automountServiceAccountToken'] = True
    if code == HTTP_SERVER:
        manifest['spec']['containers'][0]['readinessProbe'] = {
            'tcpSocket': {'port': 8080}, 'initialDelaySeconds': 1, 'periodSeconds': 1, 'failureThreshold': 30}
    apply(manifest, evidence, namespace_name + '-' + name)
    command(['kubectl', '-n', namespace_name, 'wait', '--for=condition=Ready',
             'pod/' + name, '--timeout=120s'], timeout=140)
    live = kjson('-n', namespace_name, 'get', 'pod', name)
    lab_ip(live['status']['podIP'])
    return live


def exec_python(state, code, *args, check=True):
    assert_owned(state)
    return command(['kubectl', '-n', state['namespace'], 'exec', 'client', '--',
                    'python3', '-c', code, *args], check=check, timeout=90)


def tcp_probe(state, expected_success):
    target = lab_ip(state['target_ip'])
    code = '''import socket,sys
try:
 s=socket.create_connection((sys.argv[1],8080),timeout=2)
 s.sendall(b'GET /phase-e HTTP/1.0\\r\\n\\r\\n')
 reply=s.recv(1024); s.close()
 if b'200 OK' not in reply: raise OSError('Unexpected HTTP response')
 print('TCP FORWARDED HTTP 200'); sys.exit(0)
except OSError as e:
 print('TCP BLOCKED '+type(e).__name__); sys.exit(1)
'''
    p = exec_python(state, code, target, check=False)
    print(p.stdout.strip(), flush=True)
    actual = p.returncode == 0
    if actual != expected_success:
        raise RuntimeError('TCP probe did not have expected verdict: ' + p.stdout + p.stderr)
    return {'time': utcnow(), 'target': target, 'port': 8080,
            'expected_success': expected_success, 'exit_code': p.returncode, 'output': p.stdout}


@contextlib.contextmanager
def tunnel(namespace_name, service, remote_port):
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(['kubectl', '-n', namespace_name, 'port-forward',
                            '--address', '127.0.0.1', 'svc/' + service,
                            str(port) + ':' + str(remote_port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            if proc.poll() is not None:
                raise RuntimeError('Port-forward failed')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.3):
                    break
            except OSError:
                time.sleep(.5)
        else:
            raise RuntimeError('Port-forward timeout')
        yield port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def flow_matches(flow, state, verdict):
    ip = flow.get('IP', flow.get('ip', {}))
    tcp = flow.get('l4', {}).get('TCP', {})
    return (flow.get('verdict') == verdict and ip.get('source') == state['source_ip']
            and ip.get('destination') == state['target_ip'] and tcp.get('destination_port') == 8080)


def hubble(state, evidence, name, since, verdict):
    target_ns = state['target_namespace']
    with tunnel('kube-system', 'hubble-relay', 80) as port:
        p = command(['hubble', 'observe', '--server', '127.0.0.1:' + str(port),
                     '--since', since, '--from-pod', state['namespace'] + '/client',
                     '--to-pod', target_ns + '/server', '-o', 'json'])
    save(evidence / (name + '.jsonl'), p.stdout)
    flows = []
    for line in p.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        flow = event.get('flow', event)
        if flow_matches(flow, state, verdict):
            flows.append(flow)
    if not flows:
        raise RuntimeError('No exact source/target Hubble ' + verdict + ' proof')
    print('PASS Hubble ' + verdict + ' matches=' + str(len(flows)) + ' time=' + flows[0].get('time', '?'), flush=True)
    return flows


def admission(state, evidence, proof_name):
    obj = pod_manifest(state['namespace'], 'privileged-rejected', 'lab-s1', state['run_id'])
    context = obj['spec']['containers'][0]['securityContext']
    context['privileged'] = True
    context['allowPrivilegeEscalation'] = True
    save(evidence / 'manifests' / 'privileged-rejected.json', obj)
    p = command(['kubectl', 'create', '--dry-run=server', '-f', '-'], data=obj, check=False)
    text = p.stdout + p.stderr
    save(evidence / (proof_name + '.log'), text)
    if p.returncode == 0 or not ('violates PodSecurity' in text or 'no-privileged' in text or 'lab-host-isolation' in text):
        raise RuntimeError('Expected policy-specific privileged admission rejection: ' + text)
    missing = command(['kubectl', '-n', state['namespace'], 'get', 'pod', 'privileged-rejected'], check=False)
    if missing.returncode == 0:
        raise RuntimeError('Privileged fixture unexpectedly exists')
    print('PASS privileged admission REJECTED ' + text.strip(), flush=True)


def misp_snapshot(evidence):
    cm = kjson('-n', 'soc-sensors', 'get', 'configmap', 'zeek-intel')
    intel = cm['data']['misp.intel']
    if 'ioc.evil-c2.lab.test\tIntel::DOMAIN' not in intel:
        raise RuntimeError('Last exported Intel ConfigMap lacks synthetic MISP domain')
    save(evidence / 'last-exported-intel.tsv', intel)
    # The current failure is observed read-only. Never log API credentials or raw HTTP errors.
    status = {'checked': utcnow(), 'domain': 'ioc.evil-c2.lab.test',
              'configmap_resourceVersion': cm['metadata']['resourceVersion'], 'mode': 'last-exported-configmap'}
    key = ROOT / '.secrets' / 'misp-api-key'
    if key.exists():
        try:
            with tunnel('misp', 'misp', 8080) as port:
                event_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, 'k8s-lab.p4.synthetic-event'))
                req = urllib.request.Request('http://127.0.0.1:' + str(port) + '/events/view/' + event_id,
                        headers={'Authorization': key.read_text().strip(), 'Accept': 'application/json'})
                with urllib.request.urlopen(req, timeout=30) as response:
                    event = json.load(response)['Event']
                    status['http_status'] = response.status
                    status['event_uuid'] = event['uuid']
                    status['domain_in_event'] = any(a.get('value') == status['domain'] for a in event.get('Attribute', []))
                    if not status['domain_in_event']:
                        raise RuntimeError('MISP live event is missing exported synthetic domain')
                    status['mode'] = 'live-event-and-configmap'
        except urllib.error.HTTPError as error:
            status['http_status'] = error.code
        except (OSError, KeyError, json.JSONDecodeError) as error:
            status['error_type'] = type(error).__name__
    save(evidence / 'misp-readonly.json', status)
    print('MISP read-only: ' + json.dumps(status), flush=True)


def generate(number):
    raise RuntimeError('PUBLIC_RUNTIME_DISABLED: automated scenarios disabled pending fail-closed namespace/cleanup and SIEM authorization adaptation')
    preflight()
    evidence, state_path = state_paths(number)
    previous = json.loads(state_path.read_text()) if state_path.exists() else {}
    if previous and not previous.get('cleaned'):
        raise RuntimeError('Previous run not cleaned; run cleanup first')
    if previous:
        archive = evidence / 'previous' / previous['run_id']
        archive.mkdir(parents=True, exist_ok=True)
        for path in list(evidence.iterdir()):
            if path.name != 'previous':
                path.rename(archive / path.name)
    ns = 'scen-e' + number + '-source'
    state = {'number': number, 'run_id': 'e' + number + '-' + uuid.uuid4().hex[:10],
             'started': utcnow(), 'namespace': ns, 'namespaces': {}, 'cleaned': False}
    save(state_path, state)
    namespace(state, ns, evidence)
    target_ns = ns if number in ('04', '05') else 'scen-e' + number + '-target'
    if target_ns != ns:
        namespace(state, target_ns, evidence)
    state['target_namespace'] = target_ns
    if number == '05':
        sa = {'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': {'name': 'no-rights', 'namespace': ns}}
        apply(sa, evidence, 'serviceaccount')
        role = {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role',
                'metadata': {'name': 'own-pod-only', 'namespace': ns}, 'rules': [
                {'apiGroups': [''], 'resources': ['pods'], 'resourceNames': ['client'], 'verbs': ['get']}]}
        apply(role, evidence, 'own-pod-role')
        binding = {'apiVersion': role['apiVersion'], 'kind': 'RoleBinding',
                   'metadata': {'name': 'own-pod-only', 'namespace': ns},
                   'roleRef': {'kind': 'Role', 'name': 'own-pod-only', 'apiGroup': 'rbac.authorization.k8s.io'},
                   'subjects': [{'kind': 'ServiceAccount', 'name': 'no-rights', 'namespace': ns}]}
        apply(binding, evidence, 'own-pod-binding')
        # Only metadata is required: an absent Secret still exercises authorization before existence.
        state['secret_name'] = 'synthetic-marker-never-created'
        state['forbidden_query'] = FORBIDDEN_QUERY
    server = pod(state, target_ns, 'server', 'lab-a2', evidence, HTTP_SERVER)
    state['target_ip'] = server['status']['podIP']
    if number == '02':
        dns = pod(state, target_ns, 'dns', 'lab-a2', evidence, DNS_SERVER)
        state['dns_ip'] = dns['status']['podIP']
        misp_snapshot(evidence)
    client = pod(state, ns, 'client', 'lab-s1', evidence, api_identity=(number == '05'))
    state['source_ip'] = client['status']['podIP']
    state['container_id'] = client['status']['containerStatuses'][0]['containerID'].split('://', 1)[-1]
    save(state_path, state)
    save(evidence / 'baseline-connectivity.json', tcp_probe(state, True))
    if number == '01':
        result = exec_python(state, '''import socket,sys,time
for port in range(2000,2020):
 s=socket.socket(); s.settimeout(.7)
 try: s.connect((sys.argv[1],port)); outcome='open'
 except OSError: outcome='closed-or-timeout'
 finally: s.close()
 print('synthetic port='+str(port)+' result='+outcome,flush=True)
 time.sleep(.08)
''', lab_ip(state['target_ip']))
        print(result.stdout, flush=True)
        save(evidence / 'scan-traffic.log', result.stdout)
    elif number == '02':
        result = exec_python(state, '''import socket,struct,time,sys,json
name='ioc.evil-c2.lab.test';q=b''.join(bytes([len(x)])+x.encode() for x in name.split('.'))+b'\\0'
for i in range(8):
 start=time.time();s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(2)
 s.sendto(struct.pack('!HHHHHH',i+1000,256,1,0,0,0)+q+b'\\x00\\x01\\x00\\x01',(sys.argv[1],5353))
 data,_=s.recvfrom(4096);s.close();print(json.dumps({'time':start,'query':name,'rcode':data[3]&15}),flush=True)
 if i<7:time.sleep(3)
''', lab_ip(state['dns_ip']))
        print(result.stdout, flush=True)
        save(evidence / 'periodic-dns.jsonl', result.stdout)
        samples = [json.loads(line) for line in result.stdout.splitlines()]
        if len(samples) != 8 or any(s['rcode'] != 3 for s in samples):
            raise RuntimeError('Expected eight synthetic NXDOMAIN DNS replies')
        gaps = [b['time'] - a['time'] for a, b in zip(samples, samples[1:])]
        periodicity = {'count': len(samples), 'interarrival_seconds': gaps,
                       'mean_seconds': sum(gaps) / len(gaps), 'max_seconds': max(gaps)}
        save(evidence / 'dns-periodicity.json', periodicity)
        if min(gaps) < 2.5 or max(gaps) > 6:
            raise RuntimeError('DNS cadence exceeded bounded synthetic interval')
        print('PASS DNS periodicity ' + json.dumps(periodicity), flush=True)
    elif number == '03':
        deny = {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
                'metadata': {'name': 'default-deny', 'namespace': target_ns},
                'spec': {'podSelector': {}, 'policyTypes': ['Ingress', 'Egress'], 'ingress': [], 'egress': []}}
        apply(deny, evidence, 'default-deny')
        time.sleep(5)
        state['dropped_since'] = utcnow()
        save(evidence / 'default-deny-connectivity.json', tcp_probe(state, False))
    elif number == '04':
        marker = state['run_id']
        p = command(['kubectl', '-n', ns, 'exec', 'client', '--', '/bin/sh', '-c',
                     "printf '%s' '" + marker + "' >/dev/null"])
        save(evidence / 'exec-shell.json', {'time': utcnow(), 'marker': marker, 'exit_code': p.returncode,
                                          'container_id': state['container_id']})
        print('Synthetic kubectl exec shell marker=' + marker, flush=True)
        admission(state, evidence, 'admission-before')
    elif number == '05':
        code = '''import urllib.request,urllib.error,ssl,pathlib,json,sys
sa=pathlib.Path('/var/run/secrets/kubernetes.io/serviceaccount')
context=ssl.create_default_context(cafile=str(sa/'ca.crt'))
request=urllib.request.Request('https://10.43.0.1/api/v1/namespaces/'+sys.argv[1]+'/secrets/'+sys.argv[2],
 headers={'Authorization':'Bearer '+(sa/'token').read_text().strip()})
try:
 with urllib.request.urlopen(request,context=context,timeout=5) as r: code=r.status
except urllib.error.HTTPError as e: code=e.code
print(json.dumps({'status':code,'namespace':sys.argv[1],'resource':'secrets','secret_name':sys.argv[2]}))
sys.exit(0 if code==403 else 1)
'''
        result = exec_python(state, code, ns, state['secret_name'])
        proof = json.loads(result.stdout)
        proof['time'] = utcnow()
        save(evidence / 'rbac-denied.json', proof)
        # This confirms the actual identity has one narrowly revocable non-Secret right.
        actor = 'system:serviceaccount:' + ns + ':no-rights'
        yes = command(['kubectl', '-n', ns, 'auth', 'can-i', 'get', 'pod/client', '--as', actor]).stdout.strip()
        if yes != 'yes':
            raise RuntimeError('Initial own-Pod read privilege missing')
        print('PASS ServiceAccount actual token Secret GET status=403; own-Pod read=yes', flush=True)
    save(state_path, state)
    print('PASS generated scenario=' + number + ' run=' + state['run_id'] + ' started=' + state['started'], flush=True)


def total_hits(result):
    total = result['hits']['total']
    return total['value'] if isinstance(total, dict) else total


def alert_detection(api, state, evidence, rule):
    raise RuntimeError('PUBLIC_RUNTIME_DISABLED: unsafe scenario mutation helper disabled pending fail-closed ownership/API adaptation')
    if rule == 'audit-forbidden-secret':
        query = FORBIDDEN_QUERY
        monitor = {'type': 'monitor', 'name': 'Forbidden secret access', 'monitor_type': 'query_level_monitor',
                   'enabled': False, 'schedule': {'period': {'interval': 1, 'unit': 'MINUTES'}},
                   'inputs': [{'search': {'indices': ['audit-k8s-*'], 'query': query}}],
                   'triggers': [{'name': 'Forbidden Secret GET (403)', 'severity': '2', 'actions': [],
                     'condition': {'script': {'lang': 'painless', 'source': 'return ctx.results[0].hits.total.value > 0;'}}}]}
        source_id = None
    else:
        monitor = json.loads((ROOT / 'soc/detection/monitors' / (rule + '.json')).read_text())
        registry = ROOT / 'evidence/p4/alerting-state.json'
        if not registry.is_file():
            raise RuntimeError('Runtime prerequisite missing: freshly provisioned Alerting monitor registry; historical IDs are not distributed')
        source_id = json.loads(registry.read_text())['rules'][rule]['id']
        # Read the deployed monitor too; the source rule remains unchanged.
        deployed = api.request('GET', '/_plugins/_alerting/monitors/' + source_id)['monitor']
        if not deployed.get('enabled'):
            raise RuntimeError('Existing source monitor is not enabled: ' + rule)
        query = monitor['inputs'][0]['search']['query']
    monitor['name'] = 'Phase E ' + state['run_id'] + ' / ' + rule
    monitor['enabled'] = False  # bounded manual execution; no unbounded scheduling or actions
    for trigger in monitor['triggers']:
        trigger['actions'] = []
    scoped = scoped_query(query, state, rule)
    monitor['inputs'][0]['search']['query'] = scoped
    index = monitor['inputs'][0]['search']['indices'][0]
    sample_query = copy.deepcopy(scoped)
    sample_query.pop('aggs', None)
    sample_query['size'] = 30
    sample_query['_source'] = ['@timestamp', 'ts', 'uid', 'id', 'src', 'dst', 'note', 'msg', 'query',
                               'seen.*', 'sources', 'rule', 'output', 'output_fields', 'verb', 'objectRef',
                               'responseStatus', 'user.username', 'auditID', 'stage']
    deadline = time.monotonic() + 150
    while True:
        result = api.request('POST', '/' + index + '/_search', sample_query)
        if total_hits(result):
            aggregate = api.request('POST', '/' + index + '/_search', scoped)
            if rule != 'conn-scan' or any(s['targets']['buckets'] for s in aggregate['aggregations']['sources']['buckets']):
                break
        if time.monotonic() > deadline:
            save(evidence / (rule + '-no-hit.json'), result)
            raise RuntimeError('No fresh source-correlated detection documents for ' + rule)
        time.sleep(3)
    save(evidence / (rule + '-documents.json'), result)
    save(evidence / (rule + '-query.json'), aggregate)
    monitor_ids = state.setdefault('monitor_ids', {})
    ident = monitor_ids.get(rule)
    created = api.request('PUT' if ident else 'POST',
                          '/_plugins/_alerting/monitors' + ('/' + ident if ident else ''), monitor)
    ident = created['_id']
    monitor_ids[rule] = ident
    save(evidence / 'state.json', state)
    readback = api.request('GET', '/_plugins/_alerting/monitors/' + ident)['monitor']
    if readback['name'] != monitor['name'] or readback['enabled']:
        raise RuntimeError('Run monitor readback mismatch')
    save(evidence / (rule + '-monitor-readback.json'), readback)
    executed = api.request('POST', '/_plugins/_alerting/monitors/' + ident + '/_execute', {'dryrun': False})
    save(evidence / (rule + '-execute.json'), executed)
    results = executed.get('trigger_results', {})
    if not results or not any(r.get('triggered') is True for r in results.values()) or executed.get('error'):
        raise RuntimeError('Alerting trigger did not fire: ' + rule)
    matched = []
    for _ in range(15):
        alerts = api.request('GET', '/_plugins/_alerting/monitors/alerts?monitorId=' + urllib.parse.quote(ident) + '&size=100')
        matched = [a for a in alerts.get('alerts', []) if a.get('monitor_id') == ident and a.get('state') == 'ACTIVE']
        if matched:
            break
        time.sleep(1)
    if not matched:
        raise RuntimeError('No persisted ACTIVE alert for new run monitor ' + ident)
    proof = {'rule': rule, 'source_monitor_id': source_id, 'run_monitor_id': ident,
             'fresh_hits': total_hits(result), 'alerts': [{k: a.get(k) for k in
             ('id', 'monitor_id', 'state', 'start_time', 'last_notification_time', 'trigger_name')} for a in matched],
             'verified_at': utcnow()}
    save(evidence / (rule + '-alerts.json'), proof)
    print('PASS detection ' + rule + ' hits=' + str(proof['fresh_hits']) + ' monitor=' + ident +
          ' alert=' + str(matched[0].get('id')) + ' start_time=' + str(matched[0].get('start_time')), flush=True)
    return proof


def detect(number):
    raise RuntimeError('PUBLIC_RUNTIME_DISABLED: automated scenarios disabled pending fail-closed namespace/cleanup and SIEM authorization adaptation')
    evidence, state = load_state(number)
    assert_owned(state)
    if number == '03':
        hubble(state, evidence, 'hubble-default-deny', state['dropped_since'], 'DROPPED')
        state['detected'] = True
        save(evidence / 'state.json', state)
        return
    sys.path.insert(0, str(ROOT / 'soc/opensearch'))
    from api_client import OpenSearch
    rules = {'01': ['conn-scan', 'notice-scan'], '02': ['dns-c2', 'intel-hit'],
             '04': ['falco-shell'], '05': ['audit-forbidden-secret']}[number]
    with OpenSearch() as api:
        state['detections'] = [alert_detection(api, state, evidence, rule) for rule in rules]
    state['detected'] = True
    save(evidence / 'state.json', state)


def respond(number):
    raise RuntimeError('PUBLIC_RUNTIME_DISABLED: automated scenarios disabled pending fail-closed namespace/cleanup and SIEM authorization adaptation')
    evidence, state = load_state(number)
    assert_owned(state)
    if not state.get('detected'):
        raise RuntimeError('No detection proof; response refused')
    if number == '03':
        allow = {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy',
                 'metadata': {'name': 'allow-scenario-client', 'namespace': state['target_namespace']},
                 'spec': {'podSelector': {'matchLabels': {'app': 'server'}}, 'policyTypes': ['Ingress'],
                          'ingress': [{'from': [{'namespaceSelector': {'matchLabels': {'phase-e-run': state['run_id']}},
                                               'podSelector': {'matchLabels': {'app': 'client'}}}],
                                       'ports': [{'port': 8080, 'protocol': 'TCP'}]}]}}
        apply(allow, evidence, 'explicit-allow')
        time.sleep(5)
        since = utcnow()
        save(evidence / 'explicit-allow-connectivity.json', tcp_probe(state, True))
        hubble(state, evidence, 'hubble-explicit-allow', since, 'FORWARDED')
        command(['kubectl', '-n', state['target_namespace'], 'delete', 'networkpolicy', 'allow-scenario-client'])
        if command(['kubectl', '-n', state['target_namespace'], 'get', 'networkpolicy', 'allow-scenario-client'], check=False).returncode == 0:
            raise RuntimeError('Allow policy deletion not verified')
    if number == '05':
        command(['kubectl', '-n', state['namespace'], 'delete', 'rolebinding', 'own-pod-only'])
        if command(['kubectl', '-n', state['namespace'], 'get', 'rolebinding', 'own-pod-only'], check=False).returncode == 0:
            raise RuntimeError('RoleBinding revocation readback failed')
        print('PASS RBAC revoked owned RoleBinding own-pod-only', flush=True)
    # Reuse the authored quarantine CNP, changing namespace only.
    import yaml
    quarantine = yaml.safe_load((ROOT / 'hardening/netpol/isolate-template.yaml').read_text())
    quarantine['metadata']['namespace'] = state['namespace']
    apply(quarantine, evidence, 'quarantine')
    command(['kubectl', '-n', state['namespace'], 'label', 'pod', 'client', 'quarantine=true', '--overwrite'])
    live = kjson('-n', state['namespace'], 'get', 'pod', 'client')
    if live['metadata']['labels'].get('quarantine') != 'true':
        raise RuntimeError('Quarantine label readback failed')
    save(evidence / 'quarantine-pod-readback.json', live)
    state['responded'] = utcnow()
    save(evidence / 'state.json', state)
    print('PASS response quarantine=true + CiliumNetworkPolicy/quarantine', flush=True)


def quarantine_realized(endpoint):
    status = endpoint.get('status', {})
    return status.get('state') == 'ready' and 'k8s:quarantine=true' in status.get('identity', {}).get('labels', [])


def wait_quarantine(state, evidence):
    deadline = time.monotonic() + 90
    while True:
        endpoint = kjson('-n', state['namespace'], 'get', 'ciliumendpoint', 'client')
        if quarantine_realized(endpoint):
            save(evidence / 'quarantine-endpoint-realized.json', endpoint)
            print('PASS Cilium identity convergence identity=' + str(endpoint['status']['identity']['id']) +
                  ' label=k8s:quarantine=true time=' + utcnow(), flush=True)
            return
        if time.monotonic() >= deadline:
            save(evidence / 'quarantine-endpoint-timeout.json', endpoint)
            raise RuntimeError('Cilium security identity did not realize quarantine label within 90s')
        time.sleep(2)


def verify(number):
    raise RuntimeError('PUBLIC_RUNTIME_DISABLED: automated scenarios disabled pending fail-closed namespace/cleanup and SIEM authorization adaptation')
    evidence, state = load_state(number)
    assert_owned(state)
    if not state.get('responded'):
        raise RuntimeError('Response has not been performed')
    policy = kjson('-n', state['namespace'], 'get', 'ciliumnetworkpolicy', 'quarantine')
    live = kjson('-n', state['namespace'], 'get', 'pod', 'client')
    if policy['spec']['endpointSelector']['matchLabels'] != {'quarantine': 'true'} or live['metadata']['labels'].get('quarantine') != 'true':
        raise RuntimeError('Quarantine selector/label mismatch')
    wait_quarantine(state, evidence)
    time.sleep(1)
    since = utcnow()
    save(evidence / 'response-connectivity.json', tcp_probe(state, False))
    hubble(state, evidence, 'hubble-quarantine', since, 'DROPPED')
    if number == '02':
        result = exec_python(state, '''import socket,sys
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(2)
s.sendto(b'\\x04\\xd2\\x01\\x00\\x00\\x01\\x00\\x00\\x00\\x00\\x00\\x00'+b'\\x03ioc\\x07evil-c2\\x03lab\\x04test\\x00\\x00\\x01\\x00\\x01',(sys.argv[1],5353))
try:s.recvfrom(4096);sys.exit(1)
except TimeoutError:print('PASS DNS stopped by quarantine');sys.exit(0)
''', lab_ip(state['dns_ip']))
        save(evidence / 'dns-quarantined.log', result.stdout)
        print(result.stdout.strip(), flush=True)
    if number == '04':
        admission(state, evidence, 'admission-after')
    if number == '05':
        actor = 'system:serviceaccount:' + state['namespace'] + ':no-rights'
        rights = {}
        for resource in ('pod/client', 'secrets'):
            p = command(['kubectl', '-n', state['namespace'], 'auth', 'can-i', 'get', resource, '--as', actor], check=False)
            if p.stdout.strip() != 'no' or p.returncode != 1:
                raise RuntimeError('RBAC still grants read or API failure: ' + resource)
            rights[resource] = 'no'
        save(evidence / 'rbac-after.json', {'time': utcnow(), 'identity': actor, 'get': rights})
        print('PASS RBAC after: get pod/client=no; get secrets=no', flush=True)
    state['verified'] = utcnow()
    save(evidence / 'state.json', state)
    print('PASS scenario=' + number + ' response verified time=' + state['verified'], flush=True)


def cleanup(number):
    raise RuntimeError('PUBLIC_RUNTIME_DISABLED: automated scenarios disabled pending fail-closed namespace/cleanup and SIEM authorization adaptation')
    evidence, state = load_state(number)
    if state.get('cleaned'):
        print('PASS already cleaned scenario=' + number)
        return
    assert_owned(state)
    for ns in state['namespaces']:
        command(['kubectl', '-n', ns, 'delete', 'pod', '--all', '--wait=true', '--timeout=90s'], timeout=110)
        remaining = kjson('-n', ns, 'get', 'pods')['items']
        if remaining:
            raise RuntimeError('Test pods remain in ' + ns)
        command(['kubectl', 'delete', 'namespace', ns, '--wait=true', '--timeout=90s'], timeout=110)
        if command(['kubectl', 'get', 'namespace', ns], check=False).returncode == 0:
            raise RuntimeError('Namespace cleanup readback failed: ' + ns)
    state['cleaned'] = utcnow()
    save(evidence / 'state.json', state)
    print('PASS cleanup scenario=' + number + '; manifests and persisted disabled monitor/alerts retained', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('number', choices=NAMES)
    parser.add_argument('action', choices=['generate', 'detect', 'respond', 'verify', 'cleanup'])
    args = parser.parse_args()
    if args.action in ('generate', 'detect', 'respond', 'verify', 'cleanup') and os.environ.get('LAB_TRIGGER') != '1':
        print('Set LAB_TRIGGER=1 to authorize isolated synthetic lab actions', file=sys.stderr)
        return 2
    if os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        print('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and operator prerequisites',file=sys.stderr)
        return 2
    try:
        globals()[args.action](args.number)
    except Exception as error:
        print('FAIL scenario=' + args.number + ' action=' + args.action + ': ' + str(error), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
