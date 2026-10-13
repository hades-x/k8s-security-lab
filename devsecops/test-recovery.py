#!/usr/bin/env python3
"""Regression checks for the P6 recovery generator contracts."""
import ast
from pathlib import Path
import unittest
import yaml

class RecoveryTests(unittest.TestCase):
    def test_ca_generator_uses_chart_data_not_directory_volume(self):
        tree = ast.parse(Path('devsecops/install-signature-gate.py').read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'registry_ca_overlay']
        self.assertEqual(len(functions), 1, 'Installer needs testable registry_ca_overlay')
        scope = {}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<overlay>', 'exec'), scope)
        self.assertEqual(scope['registry_ca_overlay']('PUBLIC CA'), {'global': {'caCertificates': {'data': 'PUBLIC CA'}}})
    def test_publisher_has_memory_headroom_within_ci_quota(self):
        pipeline = yaml.safe_load(Path('app/.woodpecker.yaml').read_text())
        step = next(s for s in pipeline['steps'] if s['name'] == 'push-sign-gitops-dev')
        memory = int(step['backend_options']['kubernetes']['resources']['limits']['memory'].removesuffix('Mi'))
        self.assertGreaterEqual(memory, 512)
        self.assertLessEqual(memory + 256 + 128 + 128, 1536)
    def test_zot_publisher_preserves_oci_manifest(self):
        pipeline = yaml.safe_load(Path('app/.woodpecker.yaml').read_text())
        build = next(s for s in pipeline['steps'] if s['name'] == 'daemonless-build')
        self.assertIn('--oci-layout-path', ' '.join(build['commands']))
        self.assertIn('crane push image-oci', Path('app/ci/publish.sh').read_text())
    def test_offline_lab_attestor_opts_out_of_unpublished_sct(self):
        policy = yaml.safe_load(Path('devsecops/lab-prod-signatures.yaml').read_text())
        keys = policy['spec']['rules'][0]['verifyImages'][0]['attestors'][0]['entries'][0]['keys']
        self.assertTrue(keys.get('ctlog', {}).get('ignoreSCT'), 'Private-key lab signatures have no SCT')
        self.assertTrue(keys['rekor']['ignoreTlog'])
    def test_signer_emits_kyverno_compatible_simple_signing(self):
        self.assertIn('--new-bundle-format=false', Path('app/ci/publish.sh').read_text())
    def test_cnpg_bootstrap_reference_is_immutable(self):
        v = yaml.safe_load(Path('devsecops/cnpg-values.yaml').read_text())
        self.assertIn('@sha256:', v['image']['tag'])
    def test_grpc_signing_key_is_declared_as_secret_reference(self):
        values = yaml.safe_load(Path('devsecops/woodpecker-values.yaml').read_text())
        self.assertIn('woodpecker-grpc', values['server']['extraSecretNamesForEnvFrom'])
        self.assertNotIn('WOODPECKER_GRPC_SECRET', values['server']['env'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
