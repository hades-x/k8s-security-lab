#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Bounded, read-only K8S-LAB smoke checks (stdlib only)."""

import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
CA = ROOT / '.secrets/pki/root_ca.crt'
INGRESS = '192.168.150.200'
NODES = {'lab-s1', 'lab-s2', 'lab-s3', 'lab-a1', 'lab-a2'}
SERVERS = {'lab-s1': '192.168.150.11', 'lab-s2': '192.168.150.12', 'lab-s3': '192.168.150.13'}
NAMESPACES = ('demo', 'dev', 'staging', 'prod')
TOTAL_BUDGET = 150  # Time to start all workers AND finish them; no 3-minute wait chains.

# (group, immutable check ID, label, hard per-check timeout in seconds)
CHECKS = [
    ('P1', 'nodes', '5 nodes Ready', 15),
    ('P1', 'etcd', '3 etcd voters + each server readyz', 30),
    ('P1', 'vip', 'API through VIP 192.168.150.10', 15),
    ('P1', 'encryption', 'k3s secrets-encryption enabled', 15),
    ('P2', 'cilium', 'Cilium DaemonSet ready', 20),
    ('P2', 'traefik', 'Traefik LB IP 192.168.150.200', 15),
    ('P2', 'demo', 'demo URL HTTP 200', 15),
    ('P2', 'longhorn', 'Longhorn volumes healthy', 15),
    ('P2', 'argocd', 'Argo CD apps Synced/Healthy', 15),
    ('P3', 'issuers', 'ClusterIssuers Ready', 15),
    ('P3', 'certificates', 'certificates Ready', 15),
    ('P3', 'grafana', 'Grafana HTTPS with lab root CA', 15),
    ('P3', 'keycloak', 'Keycloak HTTPS with lab root CA', 15),
    ('P3', 'openbao', 'lab OpenBao unsealed (pod Ready)', 15),
    ('P3', 'external', 'ExternalSecret synced', 15),
    ('P3', 'velero', 'Velero BSL Available', 15),
    ('P3', 'zot-anonymous', 'zot anonymous HTTP 401', 15),
    ('P4', 'kafka', 'Kafka CR Ready', 15),
    ('P4', 'brokers', '3 Kafka brokers Ready', 15),
    ('P4', 'opensearch', 'OpenSearch green/yellow', 25),
    ('P4', 'misp', 'MISP login page HTTP 200', 15),
    ('P5', 'kyverno', '6 Kyverno policies Ready', 15),
    ('P6', 'woodpecker', 'Woodpecker server ready', 15),
    ('P6', 'zot', 'zot registry reachable', 15),
    *[('P6', 'app-' + n, 'demo-app-' + n + ' Synced/Healthy', 15) for n in ('dev', 'staging', 'prod')],
    ('P6', 'prod-policy', 'lab-prod-signatures Enforce', 15),
    ('SOC', 'fresh', 'zeek-conn documents fresh (<10 min)', 25),
    ('SOC', 'monitors', '17 Alerting monitors enabled', 30),
    ('SOC', 'zeek', 'Zeek DaemonSet 5/5', 20),
    ('SOC', 'falco', 'Falco DaemonSet ready', 20),
    *[('security', 'pss-' + n, 'PSS restricted: ' + n, 15) for n in NAMESPACES],
    *[('security', 'netpol-' + n, 'default-deny NetworkPolicy: ' + n, 15) for n in NAMESPACES],
]


def ready(obj, condition='Ready'):
    generation = obj.get('metadata', {}).get('generation', 0)
    return any(c.get('type') == condition and c.get('status') == 'True'
               and c.get('observedGeneration', generation) >= generation
               for c in obj.get('status', {}).get('conditions', []))


def all_ready(items):
    if not items:
        return False, 'no resources found'
    bad = [x['metadata']['name'] for x in items if not ready(x)]
    return not bad, f'{len(items) - len(bad)}/{len(items)} Ready' + ('; not Ready: ' + ', '.join(bad) if bad else '')


def daemonset_result(ds, nodes, pods, expected=None):
    s = ds.get('status', {})
    desired = s.get('desiredNumberScheduled', 0)
    ready_nodes = {n['metadata']['name'] for n in nodes if ready(n)}
    healthy = {p.get('spec', {}).get('nodeName') for p in pods
               if ready(p) and not p['metadata'].get('deletionTimestamp')
               and p.get('spec', {}).get('nodeName') in ready_nodes}
    ok = desired > 0 and (expected is None or desired == expected)
    ok = ok and s.get('observedGeneration', 0) >= ds['metadata'].get('generation', 0)
    ok = ok and all(s.get(k, 0) == desired for k in ('numberReady', 'updatedNumberScheduled', 'numberAvailable'))
    ok = ok and len(healthy) == desired
    return ok, f'{len(healthy)}/{desired} Ready on Ready nodes (DS reports {s.get("numberReady", 0)}/{desired})'


def is_default_deny(obj):
    s = obj.get('spec', {})
    return s.get('podSelector') == {} and set(s.get('policyTypes', [])) == {'Ingress', 'Egress'} and not s.get('ingress') and not s.get('egress')


class CheckError(Exception):
    """Only explicitly sanitized operational messages may reach the report."""


def command(args, timeout=10):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise CheckError('command timeout') from None
    if p.returncode:
        # Do not leak CLI output, credentials, API response bodies or tracebacks.
        raise CheckError(f'{Path(args[0]).name} failed (exit {p.returncode}; output withheld)')
    return p.stdout


def kget(kind, name=None, namespace=None, extra=()):
    args = ['kubectl', '--request-timeout=8s', 'get', kind]
    if name:
        args.append(name)
    if namespace:
        args += ['-n', namespace]
    args += list(extra) + ['-o', 'json']
    return json.loads(command(args))


def api_ready(ip, verbose=False):
    path = '/readyz?verbose' if verbose else '/readyz'
    return command(['kubectl', '--request-timeout=8s', '--server=https://' + ip + ':6443', 'get', '--raw', path])


def http(service, path='/', scheme='https', verified=False, expected=(200,)):
    host = service + '.' + INGRESS + '.sslip.io'
    port = '443' if scheme == 'https' else '80'
    args = ['curl', '-s', '--noproxy', '*', '--connect-timeout', '3', '--max-time', '10',
            '--resolve', host + ':' + port + ':' + INGRESS, '-o', '/dev/null', '-w', '%{http_code}']
    args += ['--cacert', str(CA)] if verified else ['-k']
    code = command(args + [scheme + '://' + host + path], timeout=12).strip()
    return code.isdigit() and int(code) in expected, 'HTTP ' + code + (' (CA verified)' if verified else '')


def ds_check(namespace, name, expected=5):
    ds = kget('ds', name, namespace)
    selector = ds['spec']['selector']
    if selector.get('matchExpressions'):
        raise CheckError('unsupported DaemonSet selector')
    labels = ','.join(k + '=' + v for k, v in selector['matchLabels'].items())
    pods = kget('pods', namespace=namespace, extra=('-l', labels))['items']
    nodes = kget('nodes')['items']
    return daemonset_result(ds, nodes, pods, expected)


def app_result(app):
    s = app.get('status', {})
    sync = s.get('sync', {}).get('status', 'Unknown')
    health = s.get('health', {}).get('status', 'Unknown')
    return sync == 'Synced' and health == 'Healthy', app['metadata']['name'] + ': ' + sync + '/' + health


def os_check(check):
    if check == 'monitors' and not (ROOT / 'evidence/p4/alerting-state.json').is_file():
        raise CheckError('Runtime prerequisite missing: create a fresh operator monitor registry via soc/detection/install-alerting.py; historical monitor IDs are not distributed')
    # The existing client opens a local read-only tunnel; no probe pod or resource write.
    sys.path.insert(0, str(ROOT / 'soc/opensearch'))
    from api_client import OpenSearch
    with OpenSearch() as api:
        if check == 'fresh':
            query = {'query': {'range': {'@timestamp': {'gte': 'now-10m', 'lte': 'now'}}}}
            path = '/zeek-conn-*/_count?source=' + quote(json.dumps(query)) + '&source_content_type=application/json'
            count = api.request('GET', path)['count']
            return count > 0, f'{count} documents in last 10 minutes'
        rules = json.loads((ROOT / 'evidence/p4/alerting-state.json').read_text())['rules']
        ids = [entry['id'] for entry in rules.values()]
        if len(ids) != 17 or len(set(ids)) != 17:
            return False, f'{len(set(ids))}/17 distinct registered monitors'
        enabled = sum(api.request('GET', '/_plugins/_alerting/monitors/' + ident)['monitor'].get('enabled') is True for ident in ids)
        return enabled == 17, f'{enabled}/17 registered monitors enabled (live GET read-back)'


def check_one(check):
    if check == 'nodes':
        items = kget('nodes')['items']
        ok, detail = all_ready(items)
        names = {x['metadata']['name'] for x in items}
        return ok and names == NODES, detail + ('; expected lab node set differs' if names != NODES else '')
    if check == 'etcd':
        items = kget('nodes')['items']
        members = [n for n in items if 'node-role.kubernetes.io/etcd' in n['metadata'].get('labels', {})]
        voters = {n['metadata']['name'] for n in members if ready(n, 'EtcdIsVoter')}
        good = []
        for name, ip in SERVERS.items():
            if '[+]etcd ok' in api_ready(ip, verbose=True):
                good.append(name)
        return voters == set(SERVERS) and len(good) == 3, f'{len(voters)}/3 EtcdIsVoter; {len(good)}/3 server readyz etcd ok (not etcdctl member-list)'
    if check == 'vip':
        out = api_ready('192.168.150.10')
        return out.strip() == 'ok', 'VIP readyz=' + ('ok' if out.strip() == 'ok' else 'not ok')
    if check == 'encryption':
        out = command([str(ROOT / 'scripts/ssh-node.sh'), 'lab-s1', 'sudo k3s secrets-encrypt status'], timeout=12)
        ok = 'Encryption Status: Enabled' in out
        return ok, 'Enabled' if ok else 'not Enabled (status output withheld)'
    if check in ('cilium', 'zeek', 'falco'):
        namespace = {'cilium': 'kube-system', 'zeek': 'soc-sensors', 'falco': 'falco'}[check]
        return ds_check(namespace, check)
    if check == 'traefik':
        entries = kget('svc', 'traefik', 'kube-system').get('status', {}).get('loadBalancer', {}).get('ingress', [])
        ips = [x.get('ip', '') for x in entries]
        return INGRESS in ips, ', '.join(ips) or 'no LB IP'
    if check == 'demo':
        return http('demo', scheme='http')
    if check == 'longhorn':
        items = kget('volumes.longhorn.io', namespace='longhorn-system')['items']
        bad = [x['metadata']['name'] + '=' + x.get('status', {}).get('robustness', 'Unknown') for x in items if x.get('status', {}).get('robustness') != 'healthy']
        return bool(items) and not bad, f'{len(items) - len(bad)}/{len(items)} healthy' + ('; ' + ', '.join(bad) if bad else '')
    if check == 'argocd':
        items = kget('applications.argoproj.io', namespace='argocd')['items']
        results = [app_result(x) for x in items]
        bad = [detail for ok, detail in results if not ok]
        return bool(items) and not bad, f'{len(items) - len(bad)}/{len(items)} Synced/Healthy' + ('; ' + '; '.join(bad) if bad else '')
    if check == 'issuers':
        items = kget('clusterissuers')['items']
        ok, detail = all_ready(items)
        names = {x['metadata']['name'] for x in items}
        return ok and {'lab-acme', 'lab-ca'} <= names, detail
    if check == 'certificates':
        return all_ready(kget('certificates', extra=('-A',))['items'])
    if check in ('grafana', 'keycloak'):
        return http(check, '/login' if check == 'grafana' else '/realms/master', verified=True)
    if check == 'openbao':
        pod = kget('pod', 'openbao-0', 'secrets')
        return ready(pod) and not pod['metadata'].get('deletionTimestamp'), 'Ready=True (unsealed readiness probe)' if ready(pod) else 'Ready=False (sealed/unavailable)'
    if check == 'external':
        obj = kget('externalsecret', 'demo', 'secrets')
        ok = ready(obj) and any(c.get('type') == 'Ready' and c.get('reason') == 'SecretSynced' for c in obj.get('status', {}).get('conditions', []))
        return ok, 'Ready/SecretSynced' if ok else 'not Ready/SecretSynced'
    if check == 'velero':
        items = kget('backupstoragelocations', namespace='velero')['items']
        phases = [x['metadata']['name'] + '=' + x.get('status', {}).get('phase', 'Unknown') for x in items]
        return bool(items) and all(x.get('status', {}).get('phase') == 'Available' for x in items), ', '.join(phases) or 'no BSL found'
    if check in ('zot-anonymous', 'zot'):
        return http('zot', '/v2/', expected=(401,))
    if check == 'kafka':
        obj = kget('kafka', 'soc', 'kafka')
        return ready(obj), 'Ready=True' if ready(obj) else 'Ready=False/Unknown'
    if check == 'brokers':
        items = kget('pods', namespace='kafka', extra=('-l', 'strimzi.io/broker-role=true'))['items']
        items = [p for p in items if not p['metadata'].get('deletionTimestamp')]
        nodes = {n['metadata']['name'] for n in kget('nodes')['items'] if ready(n)}
        good = sum(ready(p) and p['spec'].get('nodeName') in nodes for p in items)
        return len(items) == good == 3, f'{good}/{len(items)} Ready brokers on Ready nodes; expected 3'
    if check == 'opensearch':
        out = command([sys.executable, str(ROOT / 'scripts/opensearch-health.py')], timeout=23)
        line = next((x for x in out.splitlines() if x.startswith('health ')), '')
        health = ast.literal_eval(line[len('health '):])
        status = health.get('status', 'Unknown')
        return status in ('green', 'yellow'), status + '; nodes=' + str(health.get('number_of_nodes', 'Unknown'))
    if check == 'misp':
        return http('misp', '/users/login', scheme='http')
    if check == 'kyverno':
        items = kget('clusterpolicies.kyverno.io')['items']
        expected = {'lab-host-isolation', 'lab-image-registries', 'lab-image-tags', 'lab-no-default-token', 'lab-prod-signatures', 'lab-resource-budget'}
        ok, detail = all_ready(items)
        return ok and {x['metadata']['name'] for x in items} == expected, detail + '; expected 6 lab policies'
    if check == 'woodpecker':
        obj = kget('sts', 'woodpecker-server', 'ci')
        s = obj.get('status', {})
        replicas = obj['spec'].get('replicas', 1)
        pod = kget('pod', 'woodpecker-server-0', 'ci')
        node = kget('node', pod.get('spec', {}).get('nodeName'))
        ok = replicas > 0 and s.get('readyReplicas', 0) == replicas and s.get('observedGeneration', 0) >= obj['metadata'].get('generation', 0) and ready(pod) and ready(node)
        return ok, f'{s.get("readyReplicas", 0)}/{replicas} ready; pod Ready={ready(pod)}; node Ready={ready(node)}'
    if check.startswith('app-'):
        return app_result(kget('applications.argoproj.io', 'demo-app-' + check[4:], 'argocd'))
    if check == 'prod-policy':
        obj = kget('clusterpolicy', 'lab-prod-signatures')
        mode = obj['spec'].get('validationFailureAction', 'Unknown')
        return mode == 'Enforce', 'validationFailureAction=' + mode
    if check in ('fresh', 'monitors'):
        return os_check(check)
    if check.startswith('pss-'):
        obj = kget('namespace', check[4:])
        label = obj['metadata'].get('labels', {}).get('pod-security.kubernetes.io/enforce', 'missing')
        return label == 'restricted', 'enforce=' + label
    if check.startswith('netpol-'):
        items = kget('networkpolicies', namespace=check[7:])['items']
        names = [x['metadata']['name'] for x in items if is_default_deny(x)]
        return bool(names), ', '.join(names) + ' (all pods; deny ingress + egress)' if names else 'no all-pod ingress+egress default-deny policy'
    raise CheckError('unknown check')


def bounded_command(args, seconds):
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=seconds)
        return subprocess.CompletedProcess(args, p.returncode, out, '')
    except subprocess.TimeoutExpired:
        return None
    finally:
        # Kill the session on success too: a terminated health helper may leave a tunnel.
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait(timeout=2)
        if p.stdout is not None:
            p.stdout.close()


def run_one(entry, deadline):
    start = time.monotonic()
    budget = min(entry[3], deadline - start)
    if budget <= 0:
        return False, 'global 150s budget exhausted; not checked', 0.0
    try:
        p = bounded_command([sys.executable, str(Path(__file__).resolve()), '--check', entry[1]], budget)
        if p is None:
            result = False, f'check timeout ({budget:.1f}s)'
        elif p.returncode:
            result = False, f'check worker failed (exit {p.returncode}; output withheld)'
        else:
            data = json.loads(p.stdout)
            if not isinstance(data['passed'], bool) or not isinstance(data['detail'], str):
                raise ValueError('invalid worker output')
            result = data['passed'], data['detail']
    except Exception as exc:
        result = False, 'check runner error: ' + type(exc).__name__
    return *result, time.monotonic() - start


def report(results, elapsed):
    group = None
    for entry, (ok, detail, seconds) in zip(CHECKS, results):
        if group != entry[0]:
            group = entry[0]
            print('\n== ' + group)
            print('RESULT CHECK                                          TIME  DETAIL')
        detail = ' '.join(detail.split())[:500]
        print(f'{"PASS" if ok else "FAIL":6} {entry[2]:46} {seconds:5.1f}s  {detail}')
    fails = sum(not r[0] for r in results)
    print('\nNOTE Kafka lag skipped: optional ~40s probe creates/updates a ConfigMap and pod; excluded from strict read-only make test.')
    print(f'SUMMARY checks={len(results)} PASS={len(results) - fails} FAIL={fails} elapsed={elapsed:.2f}s exit={fails}')
    return fails


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--check':
        try:
            passed, detail = check_one(sys.argv[2])
        except CheckError as exc:
            passed, detail = False, str(exc)
        except Exception as exc:
            passed, detail = False, type(exc).__name__ + ' (details withheld)'
        print(json.dumps({'passed': bool(passed), 'detail': detail}))
        return 0
    if len(sys.argv) != 1:
        print('Usage: tests/smoke-test.sh', file=sys.stderr)
        return 1
    start = time.monotonic()
    print('K8S-LAB read-only smoke | ' + datetime.now().astimezone().isoformat(timespec='seconds'), flush=True)
    print('4 bounded workers; per-check 15-30s; global 150s; no cluster resource writes.', flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda entry: run_one(entry, start + TOTAL_BUDGET), CHECKS))
    return report(results, time.monotonic() - start)


if __name__ == '__main__':
    sys.exit(main())
