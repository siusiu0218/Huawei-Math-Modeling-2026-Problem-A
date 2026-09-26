from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S/'experiments'))
from run_problem3_v003_full import valid_success, run_lock
from run_problem3_pair import sha
from process_runner import run_command
import subprocess


class CheckpointTests(unittest.TestCase):
    def test_changed_success_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p = root/'result.json'; p.write_text('{"makespan": 1}')
            record = {'status': 'success', 'file': p.name, 'sha256': sha(p)}
            self.assertTrue(valid_success(record, root))
            p.write_text('{"makespan": 2}')
            with self.assertRaises(ValueError): valid_success(record, root)

    def test_concurrent_runner_lock_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with run_lock(Path(tmp)):
                with self.assertRaises(OSError):
                    with run_lock(Path(tmp)): pass

    def test_keyboard_interrupt_cleans_process_log(self):
        real_wait = subprocess.Popen.wait
        first = [True]
        def interrupt_once(process, timeout=None):
            if first[0]:
                first[0] = False
                raise KeyboardInterrupt()
            return real_wait(process, timeout=timeout)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'interrupt.txt'
            with patch.object(subprocess.Popen, 'wait', interrupt_once):
                with self.assertRaises(KeyboardInterrupt):
                    run_command([sys.executable, '-c', 'import time;time.sleep(10)'], path, 5)
            path.rename(Path(tmp)/'released.txt')


if __name__ == '__main__': unittest.main()
