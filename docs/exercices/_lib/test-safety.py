#!/usr/bin/env python3
"""Offline negative tests. No kubectl API access, no node/host changes."""
import importlib.util
from pathlib import Path
import subprocess
import unittest

LIB=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('gate', LIB/'gate.py')
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

def ready_nodes():
    return {'items':[{'metadata':{'name':name}, 'status':{'conditions':[{'type':'Ready','status':'True'}]}} for name in gate.EXPECTED]}

class SafetyTests(unittest.TestCase):
    def test_not_ready_or_unknown_is_rejected(self):
        nodes=ready_nodes()
        nodes['items'][0]['status']['conditions'][0]['status']='False'
        with self.assertRaisesRegex(ValueError,'NotReady'):
            gate.check(nodes,8*1024*1024)
        nodes['items'][0]['status']['conditions']=[]
        with self.assertRaises(ValueError):
            gate.check(nodes,8*1024*1024)

    def test_inventory_and_exact_memory_threshold(self):
        with self.assertRaises(ValueError):
            gate.check({'items':[]},8*1024*1024)
        with self.assertRaisesRegex(ValueError,'RAM'):
            gate.check(ready_nodes(),4*1024*1024-1)
        gate.check(ready_nodes(),4*1024*1024)

    def test_api_failure_is_not_successful_cleanup(self):
        text=(LIB/'common.sh').read_text()
        helpers=text[text.index('ns_exists()'):text.index('setup_ns()')]
        command='set -u; NS=ex-debug; step(){ :; }; kubectl(){ return 1; };\n'+helpers+'\ncleanup_ns\n'
        result=subprocess.run(['bash','-c',command],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('PASS cleanup',result.stdout)

    def test_foreign_namespace_is_not_deleted(self):
        text=(LIB/'common.sh').read_text()
        helpers=text[text.index('ns_exists()'):text.index('setup_ns()')]
        command='set -u; NS=ex-debug; step(){ :; }; kubectl(){ case "$*" in *--ignore-not-found*) printf namespace/ex-debug;; *jsonpath*) printf foreign-owner;; *delete*) printf MUTATION; return 0;; esac; };\n'+helpers+'\ncleanup_ns\n'
        result=subprocess.run(['bash','-c',command],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('MUTATION',result.stdout)

    def test_uncordon_guard_does_not_hold_exercise_lock(self):
        import tempfile
        script=(LIB.parent/'02-lifecycle/run.sh').read_text()
        line=next(line for line in script.splitlines() if line.startswith('setsid bash -c '))
        # Exercise the real redirections/process shape without any API call.
        line=line.replace('sleep 20; kubectl --request-timeout=5s uncordon lab-a2','sleep 1; :')
        with tempfile.TemporaryDirectory(dir=LIB) as path:
            root=Path(path)
            (root/'evidence/exercices').mkdir(parents=True)
            command=f'ROOT={path}; exec 9>"$ROOT/lock"; flock -n 9;\n'+line+'\npid=$!; sleep 0.1; kill "$pid"; wait "$pid" 2>/dev/null; exec 9>&-; flock -n "$ROOT/lock" true\n'
            result=subprocess.run(['bash','-c',command],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,'watchdog child retained FD9/exercise lock')

if __name__=='__main__':
    unittest.main()
