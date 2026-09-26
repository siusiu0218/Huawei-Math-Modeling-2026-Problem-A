"""Integrity and concurrent-writer safeguards for the full Q1 runner."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

EXPERIMENTS = Path(__file__).resolve().parents[1] / 'experiments'
sys.path.insert(0, str(EXPERIMENTS))
from run_problem1_structural_full import checked, lock, sha


class RunnerSafety(unittest.TestCase):
    def test_modified_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            path.write_text('{"makespan":100}')
            digest = sha(path)
            checked(path, digest)
            path.write_text('{"makespan":99}')
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                checked(path, digest)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows runner lock')
    def test_second_process_rejected_and_lock_released(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = ('import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); '
                    'from run_problem1_structural_full import lock; '
                    'guard=lock(Path(sys.argv[2])); guard.__enter__(); guard.__exit__(None,None,None)')
            command = [sys.executable, '-B', '-c', code, str(EXPERIMENTS), str(root)]
            with lock(root):
                blocked = subprocess.run(command, capture_output=True, timeout=10)
                self.assertNotEqual(blocked.returncode, 0)
                self.assertIn(b'PermissionError', blocked.stderr)
            available = subprocess.run(command, capture_output=True, timeout=10)
            self.assertEqual(available.returncode, 0, available.stderr)


if __name__ == '__main__':
    unittest.main()
