#!/usr/bin/env python3
"""Offline regression tests; does not contact Kubernetes."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent

class SmokeContract(unittest.TestCase):
    def test_implementation_exists(self):
        self.assertTrue((ROOT / 'smoke-test.py').is_file(), 'smoke implementation is missing')

    def load(self):
        spec = importlib.util.spec_from_file_location('smoke', ROOT / 'smoke-test.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_empty_inventory_and_stale_generation_fail_closed(self):
        m = self.load()
        self.assertTrue(hasattr(m, 'ready'), 'Ready predicate is missing')
        self.assertFalse(m.ready({}))
        self.assertTrue(m.ready({'metadata': {'generation': 2}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True', 'observedGeneration': 2}]}}))
        self.assertFalse(m.ready({'metadata': {'generation': 2}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True', 'observedGeneration': 1}]}}))
        self.assertEqual(m.all_ready([]), (False, 'no resources found'))

    def test_daemonset_stale_ready_on_unready_node_fails(self):
        m = self.load()
        self.assertTrue(hasattr(m, 'daemonset_result'), 'DaemonSet predicate is missing')
        ds = {'metadata': {'generation': 1}, 'status': {'observedGeneration': 1, 'desiredNumberScheduled': 5, 'numberReady': 5, 'updatedNumberScheduled': 5, 'numberAvailable': 5}}
        nodes = [{'metadata': {'name': 'node-' + str(i)}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True' if i < 4 else 'False'}]}} for i in range(5)]
        pods = [{'metadata': {'name': 'pod-' + str(i)}, 'spec': {'nodeName': 'node-' + str(i)}, 'status': {'conditions': [{'type': 'Ready', 'status': 'True'}]}} for i in range(5)]
        passed, detail = m.daemonset_result(ds, nodes, pods, expected=5)
        self.assertFalse(passed)
        self.assertIn('4/5', detail)
        nodes[-1]['status']['conditions'][0]['status'] = 'True'
        self.assertTrue(m.daemonset_result(ds, nodes, pods, expected=5)[0])

    def test_default_deny_validates_semantics_not_name(self):
        m = self.load()
        self.assertTrue(hasattr(m, 'is_default_deny'), 'NetworkPolicy predicate is missing')
        self.assertTrue(m.is_default_deny({'spec': {'podSelector': {}, 'policyTypes': ['Ingress', 'Egress']}}))
        self.assertFalse(m.is_default_deny({'spec': {'podSelector': {}, 'policyTypes': ['Ingress', 'Egress'], 'ingress': [{}]}}))
        self.assertFalse(m.is_default_deny({'spec': {'podSelector': {'matchLabels': {'app': 'web'}}, 'policyTypes': ['Ingress', 'Egress']}}))

    def test_timeout_kills_entire_process_group(self):
        import os
        import sys
        m = self.load()
        self.assertTrue(hasattr(m, 'bounded_command'), 'bounded command runner is missing')
        started = time.monotonic()
        result = m.bounded_command([sys.executable, '-c', 'import subprocess,time; subprocess.Popen(["sleep", "20"]); time.sleep(20)'], 0.15)
        self.assertIsNone(result)
        self.assertLess(time.monotonic() - started, 2)

    def test_report_exit_is_fail_count_and_groups_present(self):
        import contextlib
        import io
        m = self.load()
        self.assertTrue(hasattr(m, 'CHECKS'), 'check registry is missing')
        self.assertEqual({c[0] for c in m.CHECKS}, {'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'SOC', 'security'})
        results = [(i not in (0, 2), 'fixture', 0.01) for i in range(len(m.CHECKS))]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(m.report(results, 0.1), 2)
        self.assertEqual(sum(line.startswith('FAIL') for line in out.getvalue().splitlines()), 2)
        self.assertEqual(sum(line.startswith(('FAIL', 'PASS')) for line in out.getvalue().splitlines()), len(m.CHECKS))

    def test_missing_nodes_fail_without_cluster_access(self):
        from unittest.mock import patch
        m = self.load()
        with patch.object(m, 'kget', return_value={'items': []}):
            self.assertFalse(m.check_one('nodes')[0])
            self.assertFalse(m.check_one('longhorn')[0])
            self.assertFalse(m.check_one('argocd')[0])
            self.assertFalse(m.check_one('issuers')[0])
            self.assertFalse(m.check_one('certificates')[0])
            self.assertFalse(m.check_one('velero')[0])
            self.assertFalse(m.check_one('kyverno')[0])
            self.assertFalse(m.check_one('netpol-dev')[0])

    def test_failed_cli_does_not_expose_output(self):
        import sys
        m = self.load()
        with self.assertRaises(m.CheckError) as caught:
            m.command([sys.executable, '-c', 'import sys; print("sensitive-fixture"); print("sensitive-fixture", file=sys.stderr); sys.exit(3)'])
        self.assertNotIn('sensitive-fixture', str(caught.exception))
        self.assertIn('exit 3', str(caught.exception))

    def test_expired_global_budget_is_fail_and_never_starts_worker(self):
        from unittest.mock import patch
        m = self.load()
        with patch.object(m, 'bounded_command') as runner:
            result = m.run_one(m.CHECKS[0], time.monotonic() - 1)
            self.assertFalse(result[0])
            self.assertIn('global', result[1])
            runner.assert_not_called()

    def test_worker_crash_and_malformed_json_fail_closed(self):
        from unittest.mock import patch
        m = self.load()
        for process in (subprocess.CompletedProcess([], 9, 'sensitive-fixture'), subprocess.CompletedProcess([], 0, 'not JSON')):
            with patch.object(m, 'bounded_command', return_value=process):
                result = m.run_one(m.CHECKS[0], time.monotonic() + 1)
                self.assertFalse(result[0])
                self.assertNotIn('sensitive-fixture', result[1])

    def test_global_deadline_counts_every_timed_out_or_pending_check(self):
        import contextlib
        import io
        import sys
        from unittest.mock import patch
        m = self.load()
        real_runner = m.bounded_command
        def stalled_worker(args, seconds):
            return real_runner([sys.executable, '-c', 'import time; time.sleep(20)'], seconds)
        started = time.monotonic()
        with patch.object(m, 'TOTAL_BUDGET', 0.15), patch.object(m, 'bounded_command', side_effect=stalled_worker), patch.object(sys, 'argv', ['smoke-test.py']), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(m.main(), len(m.CHECKS))
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(sum(line.startswith('FAIL') for line in out.getvalue().splitlines()), len(m.CHECKS))

if __name__ == '__main__':
    unittest.main()
