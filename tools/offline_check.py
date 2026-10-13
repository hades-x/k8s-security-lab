#!/usr/bin/env python3
"""Reviewed offline entrypoints only; never discover and execute arbitrary test scripts."""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parent.parent
SUITES=['tools/test_public_audit.py','tools/test_packaging.py','tests/smoke-unit.py','scenarios/test_unit.py','scenarios/test_report.py','docs/exercices/_lib/test-safety.py']

def main():
    parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group();mode.add_argument('--tests-only',action='store_true');mode.add_argument('--syntax-only',action='store_true');a=parser.parse_args()
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(ROOT/'app')}
    # No inherited operator authorization or default kubeconfig can enter offline suites.
    for key in ('LAB_ALLOW_RUNTIME','LAB_TRIGGER','P3_ALLOW_DEPLOY','KUBECONFIG'):env.pop(key,None)
    counts={'python':0,'shell':0,'json':0,'unit_tests':0,'unit_suites':0}
    if not a.tests_only:
        for p in sorted(ROOT.rglob('*')):
            if not p.is_file() or p.is_symlink() or any(part in ('.git','__pycache__') for part in p.parts):continue
            if p.suffix=='.py':compile(ast.parse(p.read_text(),filename=str(p.relative_to(ROOT))),str(p.relative_to(ROOT)),'exec');counts['python']+=1
            elif p.suffix=='.sh':subprocess.run(['bash','-n',str(p)],check=True,timeout=15);counts['shell']+=1
            elif p.suffix=='.json':json.loads(p.read_text());counts['json']+=1
            elif p.suffix=='.ndjson':
                for line in p.read_text().splitlines():
                    if line:json.loads(line);counts['json']+=1
    if not a.syntax_only:
        commands=[[sys.executable,str(ROOT/p)] for p in SUITES]+[[sys.executable,'-m','unittest','discover','-s','app/tests','-v']]
        for args in commands:
            result=subprocess.run(args,cwd=ROOT,env=env,text=True,capture_output=True,timeout=45)
            sys.stdout.write(result.stdout);sys.stdout.write(result.stderr)
            if result.returncode:return result.returncode
            match=re.search(r'Ran (\d+) tests? in ',result.stderr)
            if not match:raise SystemExit('FAIL: suite did not emit a verified unittest count')
            counts['unit_tests']+=int(match[1]);counts['unit_suites']+=1
    print(json.dumps({'passed':True,'scope':'offline only; no cluster, downloads or containers','counts':counts},sort_keys=True))
    return 0
if __name__=='__main__':raise SystemExit(main())
