"""The experiment driver must distinguish failed and timed-out workers."""
import sys
import tempfile
import unittest
import json
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from run_problem2 import run_command, save


class RunnerTests(unittest.TestCase):
    def test_transient_lock_retries_only_atomic_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'manifest.json'
            original = Path.replace
            calls = []
            def transient(source, target):
                calls.append(source)
                if len(calls) == 1:
                    raise PermissionError('temporary file lock')
                return original(source, target)
            with patch.object(Path, 'replace', transient), patch('run_problem2.time.sleep'):
                save(path, {'status': 'success'})
            self.assertEqual(len(calls), 2)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'status': 'success'})
            self.assertFalse(path.with_suffix('.json.tmp').exists())

    def test_failure_preserves_log_and_exit_code(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'failure.log'
            r = run_command([sys.executable, '-c', 'print("known failure"); raise SystemExit(7)'], log, 10)
            self.assertEqual((r['status'], r['returncode']), ('failed', 7))
            self.assertIn('known failure', log.read_text(encoding='utf-8'))

    def test_timeout_is_distinct_from_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            r = run_command([sys.executable, '-c', 'import time; time.sleep(10)'],
                            Path(folder) / 'timeout.log', 0.1)
            self.assertEqual(r['status'], 'timeout')
            self.assertIsNone(r['returncode'])
            self.assertLess(r['seconds'], 5)


if __name__ == '__main__':
    unittest.main()
