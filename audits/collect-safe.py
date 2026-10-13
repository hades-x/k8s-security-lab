#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Bounded P5 audits. No changes to application or SOC workloads."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/data/k8s-lab')
OUT = ROOT / 'evidence/p5/after'
NS = ['demo', 'dev', 'staging', 'prod', 'argocd', 'forgejo']
ENV = dict(os.environ, LC_ALL='C', KUBECONFIG=str(ROOT / '.secrets/kubeconfig'))
ENV['PATH'] = str(ROOT / 'bin') + ':' + ENV['PATH']
OUT.mkdir(parents=True, exist_ok=True)

def cmd(args, timeout=90, input=None):
    candidates = [args]
    if args[0] == 'kubectl':
        candidates = [['kubectl', '--request-timeout=15s', '--server=https://' + ip + ':6443', *args[1:]]
                      for ip in ['192.168.150.12', '192.168.150.13', '192.168.150.11']]
    for candidate in candidates:
        try:
            p = subprocess.run(candidate, env=ENV, cwd=ROOT, text=True, input=input, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            continue
        if not p.returncode:
            return p.stdout
        if not any(x in p.stderr.lower() for x in ['connection reset', 'connection refused', 'no route to host', 'deadline exceeded', 'i/o timeout', 'apiserver not ready']):
            break
    raise RuntimeError(' '.join(candidate) + '\n' + (p.stderr[-3000:] if 'p' in locals() else 'timed out'))

def available_kib():
    return int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))

def guard():
    if available_kib() <= 4 * 1024 * 1024:
        raise RuntimeError('Host available RAM <= 4 GiB: audit stopped')

def bench():
    import yaml
    records = []
    for job in yaml.safe_load_all((ROOT / 'audits/kube-bench/jobs.yaml').read_text()):
        guard()
        name = job['metadata']['name']
        cmd(['kubectl', '-n', 'audits', 'delete', 'job', name, '--ignore-not-found', '--wait=true'])
        cmd(['kubectl', 'apply', '-f', '-'], input=json.dumps(job))
        cmd(['kubectl', '-n', 'audits', 'wait', '--for=condition=complete', 'job/' + name, '--timeout=180s'], timeout=200)
        output = cmd(['kubectl', '-n', 'audits', 'logs', 'job/' + name])
        (OUT / (name + '.json')).write_text(output)
        actual = json.loads(cmd(['kubectl', '-n', 'audits', 'get', 'job', name, '-o', 'json']))
        records.append({'name': name, 'bytes': len(output), 'job': actual, 'availableKiB': available_kib()})
        (OUT / 'kube-bench-execution.json').write_text(json.dumps(records, indent=2))
        print(name, 'completed', 'bytes=' + str(len(output)), flush=True)


def scan():
    records = []
    for scope in ['after', 'reconstructed-before', 'reconstructed-after']:
        out = ROOT / 'evidence/p5' / scope
        out.mkdir(exist_ok=True)
        for label, framework in [('nsa', 'nsa'), ('mitre', 'mitre'), ('cis', 'cis-v1.12.0')]:
            guard()
            args = [str(ROOT / 'bin/kubescape'), 'scan', 'framework', framework]
            if scope != 'after':
                args += [str(out / 'app.yaml')]
            else:
                args += ['--include-namespaces', ','.join(NS)]
            args += ['--keep-local', '--host-scan=false', '--cache-dir', str(ROOT / 'audits/kubescape/cache'),
                     '--use-from', str(ROOT / 'audits/kubescape/cache' / (framework + '.json')),
                     '--scan-timeout=3m', '--control-timeout=30s', '--format=json', '--output', str(out / ('kubescape-' + label + '.json'))]
            start = time.time()
            p = subprocess.run(args, env=ENV, cwd=ROOT, text=True, capture_output=True, timeout=240)
            (out / ('kubescape-' + label + '.log')).write_text(p.stdout + p.stderr)
            records.append({'scope': scope, 'framework': framework, 'command': args, 'exit': p.returncode,
                            'seconds': round(time.time() - start, 2), 'availableKiB': available_kib()})
            (OUT / 'kubescape-execution.json').write_text(json.dumps(records, indent=2))
            print(scope, framework, 'exit=' + str(p.returncode), 'seconds=' + str(records[-1]['seconds']), flush=True)
            if p.returncode:
                print((p.stdout + p.stderr)[-1500:], flush=True)


def trivy():
    samples = []
    types = ['vulnerabilityreports', 'configauditreports', 'rbacassessmentreports', 'clusterrbacassessmentreports']
    deadline = time.monotonic() + 900
    started = time.monotonic()
    idle = 0
    try:
        guard()
        d = json.loads(cmd(['kubectl', '-n', 'trivy-system', 'get', 'deploy', 'trivy-operator', '-o', 'json']))
        env = {x['name']: x.get('value') for x in d['spec']['template']['spec']['containers'][0]['env']}
        if set((env.get('OPERATOR_TARGET_NAMESPACES') or '').split(',')) != set(NS):
            raise RuntimeError('Trivy target namespaces do not match the six allowed namespaces')
        cm = json.loads(cmd(['kubectl', '-n', 'trivy-system', 'get', 'configmap', 'trivy-operator-config', '-o', 'json']))
        (OUT / 'trivy-configmap.json').write_text(json.dumps(cm, indent=2))
        if cm['data'].get('OPERATOR_CONCURRENT_SCAN_JOBS_LIMIT') != '1':
            raise RuntimeError('Trivy scanJobsConcurrentLimit is not 1')
        cmd(['kubectl', 'apply', '-f', str(ROOT / 'audits/trivy-operator/resourcequota.yaml')])
        cmd(['kubectl', '-n', 'trivy-system', 'scale', 'deployment/trivy-operator', '--replicas=1'])
        cmd(['kubectl', '-n', 'trivy-system', 'rollout', 'status', 'deployment/trivy-operator', '--timeout=120s'], timeout=140)
        d = cmd(['kubectl', '-n', 'trivy-system', 'get', 'deploy', 'trivy-operator', '-o', 'json'])
        (OUT / 'trivy-deployment-running.json').write_text(d)
        while time.monotonic() < deadline:
            guard()
            counts = {}
            coverage = {}
            for kind in types:
                d = json.loads(cmd(['kubectl', 'get', kind, '-A', '-o', 'json']))
                if kind != 'clusterrbacassessmentreports':
                    d['items'] = [x for x in d['items'] if x['metadata'].get('namespace') in NS]
                (OUT / ('trivy-' + kind + '.json')).write_text(json.dumps(d, indent=2))
                counts[kind] = len(d['items'])
                coverage[kind] = sorted(set(x['metadata'].get('namespace', 'CLUSTER') for x in d['items']))
            jobs = json.loads(cmd(['kubectl', '-n', 'trivy-system', 'get', 'jobs', '-o', 'json']))
            active = sum(x.get('status', {}).get('active', 0) for x in jobs['items'])
            failed = sum(x.get('status', {}).get('failed', 0) for x in jobs['items'])
            pods = json.loads(cmd(['kubectl', '-n', 'trivy-system', 'get', 'pods', '-o', 'json']))
            scanner_pods = [x for x in pods['items'] if x['metadata']['name'].startswith('scan-')
                            and x.get('status', {}).get('phase') not in ['Succeeded', 'Failed']]
            if len(scanner_pods) > 1:
                raise RuntimeError('More than one nonterminated scanner Pod despite serial quota')
            nodes = cmd(['kubectl', 'top', 'nodes'])
            sample = {'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'elapsedSeconds': round(time.monotonic() - started),
                      'availableKiB': available_kib(), 'reportCounts': counts, 'namespaceCoverage': coverage,
                      'activeScanJobs': active, 'activeScannerPods': len(scanner_pods), 'failedScanJobs': failed, 'nodes': nodes}
            samples.append(sample)
            (OUT / 'resource-samples.json').write_text(json.dumps(samples, indent=2))
            (OUT / 'trivy-scan-jobs.json').write_text(json.dumps(jobs, indent=2))
            print(json.dumps({k: v for k, v in sample.items() if k != 'nodes'}), flush=True)
            complete = all(set(coverage[k]) == set(NS) for k in ['vulnerabilityreports', 'configauditreports'])
            idle = idle + 1 if active == 0 and complete else 0
            if failed and active == 0 and time.monotonic() - started > 180:
                raise RuntimeError('Vulnerability job failed; stop bounded audit and retain partial reports')
            if idle >= 3 and time.monotonic() - started > 180:
                break
            time.sleep(20)
        (OUT / 'trivy-operator.log').write_text(cmd(['kubectl', '-n', 'trivy-system', 'logs', 'deployment/trivy-operator', '--tail=100']))
    finally:
        cmd(['kubectl', '-n', 'trivy-system', 'scale', 'deployment/trivy-operator', '--replicas=0'])
        cmd(['kubectl', '-n', 'trivy-system', 'delete', 'jobs', '-l', 'app.kubernetes.io/managed-by=trivy-operator',
             '--wait=true', '--timeout=60s'])
        d = json.loads(cmd(['kubectl', '-n', 'trivy-system', 'get', 'deploy', 'trivy-operator', '-o', 'json']))
        (OUT / 'trivy-deployment-stopped.json').write_text(json.dumps(d, indent=2))
        if d['spec']['replicas'] != 0:
            raise RuntimeError('Trivy was not scaled back to zero')
        print('VERIFIED: Trivy replicas=0', flush=True)

if __name__ == '__main__':
    {'kube-bench': bench, 'kubescape': scan, 'trivy': trivy}[sys.argv[1]]()
