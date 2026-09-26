import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S/'experiments'))
from process_runner import run_command


class ProcessTests(unittest.TestCase):
    def test_original_venv_timeout_releases_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            self.assertEqual(run_command([sys.executable, '-c', 'raise SystemExit(3)'], out/'failed.txt', 5)['status'], 'failed')
            self.assertEqual(run_command([sys.executable, '-c', 'import time;time.sleep(5)'], out/'timeout.txt', .05)['status'], 'timeout')
            (out/'timeout.txt').rename(out/'released.txt')

    def test_timeout_kills_grandchild_before_it_can_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); marker = out/'late.txt'
            child = 'import time;from pathlib import Path;time.sleep(1);Path('+repr(str(marker))+').write_text("alive")'
            parent = 'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(child)+']);print("spawned",flush=True);time.sleep(10)'
            self.assertEqual(run_command([sys.executable, '-c', parent], out/'tree.txt', .4)['status'], 'timeout')
            self.assertIn('spawned', (out/'tree.txt').read_text())
            (out/'tree.txt').rename(out/'released.txt')
            time.sleep(1.1)
            self.assertFalse(marker.exists(), 'descendant survived timeout')


if __name__ == '__main__':
    unittest.main()
