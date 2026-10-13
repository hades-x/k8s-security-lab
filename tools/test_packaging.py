#!/usr/bin/env python3
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
class PackagingTests(unittest.TestCase):
    def test_runtime_shells_refuse_without_authorization(self):
        for rel in ['infra/k3s/env.sh','infra/libvirt/up.sh','scripts/lab-status.sh','docs/exercices/01-debug/run.sh']:
            self.assertIn('LAB_ALLOW_RUNTIME', (ROOT/rel).read_text(),rel)
    def test_smoke_missing_monitor_registry_fails_before_tunnel(self):
        spec=importlib.util.spec_from_file_location('smoke',ROOT/'tests/smoke-test.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with patch.object(m.Path,'is_file',return_value=False):
            with self.assertRaisesRegex(m.CheckError,'prerequisite'):
                m.os_check('monitors')
    def test_unsafe_lifecycle_not_exported(self):
        for rel in ['scripts/lab-start.sh','scripts/lab-stop.sh','scripts/repair-a1-os.sh','scripts/kafka-reset-broker-data.sh']:
            self.assertFalse((ROOT/rel).exists(),rel)
    def test_disabled_scenario_actions_cannot_reach_helpers(self):
        spec=importlib.util.spec_from_file_location('runner',ROOT/'scenarios/runner.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with patch.object(m,'command',side_effect=AssertionError('runtime helper reached')),patch.object(m,'load_state',side_effect=AssertionError('runtime state reached')):
            for action in ('generate','detect','respond','verify','cleanup'):
                with self.subTest(action=action),self.assertRaisesRegex(RuntimeError,'disabled'):
                    getattr(m,action)('01')
    def test_snapshot_and_native_importer_are_disabled(self):
        for rel in ['docs/exercices/_lib/common.sh','docs/exercices/04-control-plane/snapshot-lib.sh','soc/detection/install-security-analytics.py']:
            self.assertIn('PUBLIC_RUNTIME_DISABLED',(ROOT/rel).read_text(),rel)

    def test_exporter_fixture_mode_needs_no_runtime_authorization(self):
        import sys,tempfile
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'intel.tsv';env=dict(os.environ);env.pop('LAB_ALLOW_RUNTIME',None)
            result=subprocess.run([sys.executable,str(ROOT/'soc/misp/misp-to-zeek-intel.py'),'--from-json',str(ROOT/'soc/misp/fixtures/lab-event.json'),'--output',str(out)],env=env,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(len(out.read_text().splitlines()),5)

    def test_unsafe_scenario_helpers_are_unconditionally_blocked(self):
        import ast
        tree=ast.parse((ROOT/'scenarios/runner.py').read_text())
        functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        for name in ('namespace','apply','alert_detection'):
            self.assertIsInstance(functions[name].body[0],ast.Raise,name)

if __name__=='__main__':unittest.main()
