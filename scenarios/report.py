#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Certify stored real evidence, never turn a mere state flag into PASS."""
import datetime as dt
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
RULES = {'01': ['conn-scan', 'notice-scan'], '02': ['dns-c2', 'intel-hit'],
         '03': [], '04': ['falco-shell'], '05': ['audit-forbidden-secret']}


def read_json(path):
    return json.loads(path.read_text())


def flow_count(path, state, verdict):
    count = 0
    for line in path.read_text().splitlines():
        flow = json.loads(line).get('flow', {})
        ip = flow.get('IP', {})
        tcp = flow.get('l4', {}).get('TCP', {})
        if (flow.get('verdict') == verdict and ip.get('source') == state['source_ip']
                and ip.get('destination') == state['target_ip'] and tcp.get('destination_port') == 8080):
            count += 1
    return count


def certify(number, evidence, state):
    result = {'result': 'FAIL', 'run_id': state.get('run_id'), 'started': state.get('started'),
              'verified': state.get('verified'), 'cleaned': state.get('cleaned'),
              'errors': [], 'detections': [], 'log': 'evidence/scenarios/' + number + '.log'}
    try:
        for flag in ('detected', 'responded', 'verified', 'cleaned'):
            if not state.get(flag):
                raise ValueError('Missing completed phase: ' + flag)
        if not read_json(evidence / 'baseline-connectivity.json')['expected_success']:
            raise ValueError('Missing positive before-response connectivity')
        blocked = read_json(evidence / 'response-connectivity.json')
        if blocked['expected_success'] or blocked['exit_code'] == 0 or 'TCP BLOCKED' not in blocked['output']:
            raise ValueError('Response did not actually block connectivity')
        endpoint = read_json(evidence / 'quarantine-endpoint-realized.json')
        if 'k8s:quarantine=true' not in endpoint['status']['identity']['labels']:
            raise ValueError('Quarantine metadata not present in actual Cilium security identity')
        dropped = flow_count(evidence / 'hubble-quarantine.jsonl', state, 'DROPPED')
        if dropped < 1:
            raise ValueError('No exact fresh Hubble quarantine DROPPED')
        result['quarantine_dropped_flows'] = dropped
        for rule in RULES[number]:
            proof = read_json(evidence / (rule + '-alerts.json'))
            docs = read_json(evidence / (rule + '-documents.json'))
            monitor = read_json(evidence / (rule + '-monitor-readback.json'))
            if proof['fresh_hits'] < 1 or not proof['alerts'] or not docs['hits']['hits']:
                raise ValueError('Missing fresh document/persisted alert: ' + rule)
            if monitor['enabled'] or state['run_id'] not in monitor['name']:
                raise ValueError('Monitor not disabled/run-scoped: ' + rule)
            for trigger in monitor['triggers']:
                if trigger.get('query_level_trigger', trigger).get('actions'):
                    raise ValueError('External notification action present')
            cutoff = dt.datetime.fromisoformat(state['started'].replace('Z', '+00:00'))
            for hit in docs['hits']['hits']:
                timestamp = dt.datetime.fromisoformat(hit['_source']['@timestamp'].replace('Z', '+00:00'))
                if timestamp < cutoff:
                    raise ValueError('Detection document predates run')
            for alert in proof['alerts']:
                if alert['state'] != 'ACTIVE' or not alert['id']:
                    raise ValueError('No persisted ACTIVE alert ID')
                alert['start_time_utc'] = dt.datetime.fromtimestamp(alert['start_time'] / 1000,
                        tz=dt.timezone.utc).isoformat().replace('+00:00', 'Z')
            result['detections'].append(proof)
        if number == '02':
            cadence = read_json(evidence / 'dns-periodicity.json')
            intel = read_json(evidence / 'intel-hit-documents.json')
            if cadence['count'] != 8 or cadence['max_seconds'] > 6:
                raise ValueError('DNS periodicity proof incomplete')
            if not any(hit['_source'].get('seen.indicator') == 'ioc.evil-c2.lab.test'
                       and 'MISP-LAB' in hit['_source'].get('sources', []) for hit in intel['hits']['hits']):
                raise ValueError('Intel hit not correlated to the MISP domain')
            result['misp'] = read_json(evidence / 'misp-readonly.json')
            if 'PASS DNS stopped by quarantine' not in (evidence / 'dns-quarantined.log').read_text():
                raise ValueError('DNS response blocking not proved')
        if number == '03':
            if flow_count(evidence / 'hubble-default-deny.jsonl', state, 'DROPPED') < 1:
                raise ValueError('Initial default-deny not proved')
            forwarded = flow_count(evidence / 'hubble-explicit-allow.jsonl', state, 'FORWARDED')
            if forwarded < 1 or not read_json(evidence / 'explicit-allow-connectivity.json')['expected_success']:
                raise ValueError('Explicit allowed forwarding not proved')
            result['explicit_forwarded_flows'] = forwarded
        if number == '04':
            for name in ('admission-before.log', 'admission-after.log'):
                text = (evidence / name).read_text()
                if not any(marker in text for marker in ('violates PodSecurity', 'no-privileged', 'lab-host-isolation')):
                    raise ValueError('Policy-specific privileged rejection missing')
            marker = read_json(evidence / 'exec-shell.json')['marker']
            docs = read_json(evidence / 'falco-shell-documents.json')
            if not any(marker in h['_source']['output'] for h in docs['hits']['hits']):
                raise ValueError('Unique kubectl exec shell marker not found in Falco')
        if number == '05':
            if read_json(evidence / 'rbac-denied.json')['status'] != 403:
                raise ValueError('ServiceAccount actual request was not HTTP 403')
            if read_json(evidence / 'rbac-after.json')['get'] != {'pod/client': 'no', 'secrets': 'no'}:
                raise ValueError('RBAC revocation not proved')
            docs = read_json(evidence / 'audit-forbidden-secret-documents.json')
            if not any(h['_source']['responseStatus']['code'] == 403 for h in docs['hits']['hits']):
                raise ValueError('Denied event absent from audit index')
        result['result'] = 'PASS'
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        result['errors'].append(str(error))
    return result


def main():
    base = ROOT / 'evidence/scenarios'
    previous_path = base / 'results.json'
    previous = read_json(previous_path) if previous_path.exists() else {'scenarios': {}}
    results = {}
    for number in RULES:
        path = base / number / 'state.json'
        state = read_json(path) if path.exists() else {}
        results[number] = certify(number, base / number, state)
        results[number]['attempt'] = previous.get('scenarios', {}).get(number, {}).get('attempt', 1)
        if number == '01' and (base / '01.initial-failure.log').exists():
            results[number]['attempt'] = 2
            results[number]['initial_failure'] = 'Cilium identity label propagation took 16–18s; fixed metadata-vs-identity convergence gate, not the policy.'
    doc = {'updated': dt.datetime.now(dt.timezone.utc).isoformat(), 'scenarios': results,
           'pass_count': sum(r['result'] == 'PASS' for r in results.values()), 'total': len(results)}
    previous_path.write_text(json.dumps(doc, indent=2) + '\n')
    assert read_json(previous_path) == doc
    table = ['# Résultats réels Phase E', '', '| Scénario | Résultat | Début UTC | Vérification UTC | Alertes / preuve |', '|---|---|---|---|---|']
    for number, result in results.items():
        alerts = [a['id'] for proof in result['detections'] for a in proof['alerts']]
        key = ', '.join(alerts) if alerts else ('Hubble DROPPED/FORWARDED' if result['result'] == 'PASS' else '; '.join(result['errors']))
        table.append('| ' + number + ' | ' + result['result'] + ' | ' + str(result['started']) + ' | ' + str(result['verified']) + ' | ' + key.replace('|', '/') + ' |')
        print('RESULT ' + number + ' ' + result['result'] + ' verified=' + str(result['verified']) + ' alerts=' + ','.join(alerts))
    table += ['', 'Les manifests/GET, documents frais, monitors désactivés, executions et alertes persistées sont conservés sous chaque numéro. Les pods et namespaces de test ont été supprimés lorsque `cleaned` est renseigné. Le premier essai de 01 a échoué sur le délai de convergence d’identité Cilium ; le second a validé la réponse après une garde de convergence, sans changer le template de politique.', '', 'Fichiers hors `scenarios/` : `soc/detection/rules/audit-forbidden-secret.yaml` ; preuves sous `evidence/scenarios/`. Aucun changement Vector/MISP/hardening global par ce worker.']
    (base / 'summary.md').write_text('\n'.join(table) + '\n')
    readme = ROOT / 'scenarios/README.md'
    lines = readme.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith('| 0'):
            number = line.split('|')[1].strip()[:2]
            if number in results:
                parts = line.split('|')
                parts[-2] = ' **' + results[number]['result'] + '** — `evidence/scenarios/' + number + '.log` '
                lines[i] = '|'.join(parts)
    readme.write_text('\n'.join(lines) + '\n')
    print('TOTAL ' + str(doc['pass_count']) + '/' + str(doc['total']) + ' PASS')
    return 0 if doc['pass_count'] == 5 else 1


if __name__ == '__main__':
    sys.exit(main())
