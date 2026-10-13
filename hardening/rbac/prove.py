#!/usr/bin/env python3

if __name__ == '__main__':
    import os as _runtime_os
    if _runtime_os.environ.get('LAB_ALLOW_RUNTIME') != 'yes':
        raise SystemExit('BLOCKED: runtime requires LAB_ALLOW_RUNTIME=yes and tools/DEPENDENCIES.md review')
"""Read-only impersonation proofs of the three training RBAC roles."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'evidence/p5/rbac'
OUT.mkdir(parents=True, exist_ok=True)
results = []
roles = [('lab-viewer', 'lab-viewer-test', 'lab-viewers'),
         ('lab-dev', 'lab-dev-test', 'lab-developers'),
         ('soc-analyst', 'soc-analyst-test', 'soc-analysts')]
for role, user, group in roles:
    for ns in ['dev', 'staging', 'prod']:
        cases = [('get', 'pods', ns != 'prod'),
                 ('get', 'pods/log', ns != 'prod'),
                 ('patch', 'deployments.apps', role == 'lab-dev' and ns != 'prod'),
                 ('get', 'secrets', False),
                 ('create', 'rolebindings.rbac.authorization.k8s.io', False),
                 ('create', 'pods/exec', False)]
        if role == 'soc-analyst':
            cases.append(('get', 'policyreports.wgpolicyk8s.io', ns != 'prod'))
        for verb, resource, expected in cases:
            base_resource, sep, subresource = resource.partition('/')
            args = ['kubectl', 'auth', 'can-i', verb, base_resource, '--namespace=' + ns,
                    '--as=' + user, '--as-group=' + group, '--request-timeout=15s']
            if sep:
                args += ['--subresource=' + subresource]
            if os.environ.get('P5_API_SERVER'):
                args += ['--server=' + os.environ['P5_API_SERVER']]
            p = subprocess.run(args, text=True, capture_output=True, timeout=20)
            answer = p.stdout.strip()
            passed = answer == ('yes' if expected else 'no') and p.returncode == (0 if expected else 1)
            row = {'role': role, 'user': user, 'group': group, 'namespace': ns, 'verb': verb,
                   'resource': resource, 'expected': 'yes' if expected else 'no', 'answer': answer,
                   'exit': p.returncode, 'pass': passed, 'command': args}
            results.append(row)
            print(('PASS' if passed else 'FAIL') + f': {role} {verb} {resource} -n {ns}: {answer}', flush=True)
            if not passed:
                print(p.stderr, flush=True)
(OUT / 'impersonation-results.json').write_text(json.dumps(results, indent=2))
passed = sum(x['pass'] for x in results)
print(f'RBAC: {passed}/{len(results)} expectations passed')
sys.exit(0 if passed == len(results) else 1)
