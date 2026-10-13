#!/usr/bin/env python3
"""Offline unit tests only: never claim Kubernetes delivery from fixtures."""
import importlib.util
from pathlib import Path
import unittest

class Safety(unittest.TestCase):
    def test_network_targets_are_strictly_inside_lab(self):
        path = Path(__file__).with_name('runner.py')
        self.assertTrue(path.exists(), 'Missing scoped scenario runner')
        spec = importlib.util.spec_from_file_location('phase_e', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for ip in ['192.168.150.22','10.42.4.57','10.43.1.1']:
            self.assertEqual(mod.lab_ip(ip), ip)
        for ip in ['8.8.8.8','192.168.150.1','127.0.0.1','not-an-ip','10.42.1.1;id']:
            with self.assertRaises(ValueError):
                mod.lab_ip(ip)

    def test_fixture_pods_are_restricted_and_budgeted(self):
        path = Path(__file__).with_name('runner.py')
        spec = importlib.util.spec_from_file_location('phase_e', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, 'pod_manifest'), 'Missing restricted fixture manifest')
        pod = mod.pod_manifest('scen-e01-source', 'client', 'lab-s1', 'run-test')
        self.assertFalse(pod['spec']['automountServiceAccountToken'])
        self.assertTrue(pod['spec']['securityContext']['runAsNonRoot'])
        self.assertEqual(pod['spec']['securityContext']['seccompProfile']['type'], 'RuntimeDefault')
        container = pod['spec']['containers'][0]
        self.assertEqual(container['securityContext']['capabilities']['drop'], ['ALL'])
        self.assertFalse(container['securityContext']['allowPrivilegeEscalation'])
        self.assertTrue(container['resources']['limits']['memory'])
        self.assertIn('@sha256:', container['image'])
        with self.assertRaises(ValueError):
            mod.pod_manifest('prod', 'client', 'lab-s1', 'run-test')

    def test_detection_query_is_fresh_and_source_correlated(self):
        import json
        path = Path(__file__).with_name('runner.py')
        spec = importlib.util.spec_from_file_location('phase_e', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, 'scoped_query'), 'Missing source-correlated query')
        query = {'size': 0, 'query': {'bool': {'filter': [{'term': {'proto': 'tcp'}}]}},
                 'aggs': {'sources': {'terms': {'field': 'id.orig_h'}}}}
        state = {'started': '2026-10-13T18:30:00Z', 'source_ip': '10.42.0.7',
                 'namespace': 'scen-e01-source', 'run_id': 'e01-test', 'container_id': 'abc'}
        result = mod.scoped_query(query, state, 'conn-scan')
        text = json.dumps(result)
        self.assertIn(state['started'], text)
        self.assertIn(state['source_ip'], text)
        self.assertIn('aggs', result)
        self.assertNotIn('range', json.dumps(query))

    def test_unguarded_generator_refuses_before_any_cluster_call(self):
        import os
        import subprocess
        env = dict(os.environ)
        env.pop('LAB_TRIGGER', None)
        result = subprocess.run(['python3', str(Path(__file__).with_name('runner.py')), '01', 'generate'],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('LAB_TRIGGER=1', result.stderr)

    def test_dns_fixture_uses_a_zeek_recognized_unprivileged_port(self):
        path = Path(__file__).with_name('runner.py')
        spec = importlib.util.spec_from_file_location('phase_e', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertIn("5353", mod.DNS_SERVER)
        self.assertNotIn("8053", mod.DNS_SERVER)

    def test_hubble_proof_requires_exact_endpoint_port_and_verdict(self):
        path = Path(__file__).with_name('runner.py')
        spec = importlib.util.spec_from_file_location('phase_e', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, 'flow_matches'), 'Missing exact Hubble correlation')
        state = {'source_ip': '10.42.0.7', 'target_ip': '10.42.4.9'}
        flow = {'verdict': 'DROPPED', 'IP': {'source': state['source_ip'], 'destination': state['target_ip']},
                'l4': {'TCP': {'destination_port': 8080}}}
        self.assertTrue(mod.flow_matches(flow, state, 'DROPPED'))
        self.assertFalse(mod.flow_matches(flow, state, 'FORWARDED'))
        flow['l4']['TCP']['destination_port'] = 22
        self.assertFalse(mod.flow_matches(flow, state, 'DROPPED'))
        flow['l4']['TCP']['destination_port'] = 8080
        flow['IP']['source'] = '10.42.0.8'
        self.assertFalse(mod.flow_matches(flow, state, 'DROPPED'))

    def test_quarantine_waits_for_identity_not_just_pod_metadata(self):
        path = Path(__file__).with_name('runner.py')
        spec = importlib.util.spec_from_file_location('phase_e', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, 'quarantine_realized'), 'Missing Cilium identity convergence guard')
        endpoint = {'metadata': {'labels': {'quarantine': 'true'}},
                    'status': {'state': 'ready', 'identity': {'labels': ['k8s:app=client']}}}
        self.assertFalse(mod.quarantine_realized(endpoint))
        endpoint['status']['identity']['labels'].append('k8s:quarantine=true')
        self.assertTrue(mod.quarantine_realized(endpoint))
        endpoint['status']['state'] = 'regenerating'
        self.assertFalse(mod.quarantine_realized(endpoint))

if __name__ == '__main__':
    unittest.main()
