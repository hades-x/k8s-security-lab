import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('public_audit',Path(__file__).with_name('public_audit.py'))
class AuditTests(unittest.TestCase):
    def test_symlink_is_rejected_without_following(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'link').symlink_to('/does/not/exist')
            self.assertTrue(SPEC and SPEC.loader, 'Public audit implementation missing')
            module=importlib.util.module_from_spec(SPEC)
            try: SPEC.loader.exec_module(module)
            except FileNotFoundError: self.fail('Public audit implementation missing')
            self.assertIn('symlink',str(module.audit(root)))

def load():
    module=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(module); return module

def probe(self, name, content):
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); p=root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(content)
        self.assertTrue(load().audit(root), 'Forbidden fixture passed: '+name)

FIXTURES={
 'private_key':('key.txt',b'-----BEGIN '+b'PRIVATE KEY-----'),
 'certificate':('trust.yaml',b'-----BEGIN '+b'CERTIFICATE-----'),
 'github_token':('new-untracked.txt',b'ghp_'+b'A'*36),
 'aws_key':('new.txt',b'AKIA'+b'A'*16),
 'jwt':('new.txt',b'eyJ'+b'A'*25+b'.'+b'B'*30+b'.'+b'C'*30),
 'home_path':('doc.md',b'/ho'+b'me/private-user/data'),
 'tailnet':('config.txt',b'100.'+b'101.5.74'),
 'original_host':('doc.txt',b'PC-'+b'host-test'),
 'original_vm':('config.txt',b'k8slab-'+b's1'),
 'credential_url':('config.txt',b'https'+b'://user:'+b'actual-password@example.test'),
 'literal_password':('config.yaml',b'password: '+b'not-a-placeholder-value'),
 'secret_filename':('.secrets/password',b'anything'),
 'kubeconfig':('kubeconfig',b'anything'),
 'private_evidence':('evidence/proof.txt',b'anything'),
 'vendor':('component/vendor/raw.txt',b'anything'),
 'binary':('capture.pcap',b'\x00\xff\x01'),
 'non_utf8':('file.txt',b'\xff'),
 'encoded_key':('config.yaml',__import__('base64').b64encode(b'-----BEGIN '+b'PRIVATE KEY-----')),
 'nested_encoding':('config.json',__import__('base64').b64encode(__import__('base64').b64encode(b'ghp_'+b'A'*36))),
 'inline_json_password':('config.json',b'{"password":"actual-secret-value"}'),
 'broken_link':('doc.md',b'[missing](absent.md)'),
 'missing_reference_link':('doc.md',b'[missing][ref]\n\n[ref]: absent.md'),
 'missing_anchor':('doc.md',b'# Existing\n[bad](#absent)'),
 'unpinned_action':('.github/workflows/check.yml',b'permissions:\n  contents: read\njobs:\n  check:\n    timeout-minutes: 5\n    steps:\n      - uses: actions/checkout@v4\n'),
}
for label,(name,content) in FIXTURES.items():
    setattr(AuditTests,'test_reject_'+label,lambda self,n=name,c=content:probe(self,n,c))

def clean(self):
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); (root/'doc.md').write_text('# Hello World\n[local](doc.md#hello-world)\n[external](https://example.test)\n')
        (root/'config.txt').write_text('192.168.150.0/24 10.42.0.0/16 ioc.lab.test\npassword: ${LAB_PASSWORD}\n')
        self.assertEqual(load().audit(root),[])
AuditTests.test_clean_synthetic_topology=clean

def symlink_link(self):
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); outside=root/'donor';outside.mkdir();(outside/'read.md').write_text('# X')
        (root/'shortcut').symlink_to(outside,target_is_directory=True)
        with patch.object(Path,'read_text',side_effect=AssertionError('link target opened')):
            self.assertTrue(load().markdown_links(root,root/'doc.md','[link](shortcut/read.md#x)'))
AuditTests.test_markdown_never_reads_symlink_ancestor=symlink_link

def special_files(self):
    import os
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);(root/'donor.txt').write_text('safe');os.link(root/'donor.txt',root/'hardlink.txt');os.mkfifo(root/'fifo')
        rules={rule for _,rule in load().audit(root)}
        self.assertIn('hardlink',rules);self.assertIn('special-file',rules)
AuditTests.test_special_files_fail_closed=special_files

def encoded_json(self):
    import base64,json
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);(root/'secret.json').write_text(json.dumps({'data':{'key':base64.b64encode(b'AKIA'+b'A'*16).decode()}}))
        self.assertTrue(load().audit(root))
AuditTests.test_encoded_manifest_payload_is_scanned=encoded_json

if __name__=='__main__':unittest.main()
