#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest

class EvidenceGate(unittest.TestCase):
    def test_verified_flag_alone_is_not_a_pass(self):
        path = Path(__file__).with_name('report.py')
        self.assertTrue(path.exists(), 'Missing evidence-backed reporting')
        spec = importlib.util.spec_from_file_location('report', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parent)) as directory:
            for number in ['01','02','03','04','05']:
                result = mod.certify(number, Path(directory), {'detected': True, 'responded': 'now', 'verified': 'now', 'cleaned': 'now'})
                self.assertEqual(result['result'], 'FAIL')
                self.assertTrue(result['errors'])

if __name__ == '__main__':
    unittest.main()
