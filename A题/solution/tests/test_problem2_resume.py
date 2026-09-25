"""Resume must reuse plans and keep failed generation separate from evaluation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
import resume_problem2_adaptive as resume


class ResumeTests(unittest.TestCase):
    def run_fake(self, reuse):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'solution'; base = root / 'outputs'
            for path in ('src', 'tests', 'experiments', 'outputs'):
                (root / path).mkdir(parents=True)
            (root.parent / 'code').mkdir(); (root.parent / 'data').mkdir()
            (root.parent / 'data/config.txt').write_text('fixed')
            (root.parent / 'data/case_001.json').write_text('{}')
            (root / 'experiments/run_problem2.py').write_text('# runner')
            entry = {'case': 'case_001', 'cores': 2}; calls = []
            if reuse:
                (root / 'old.json').write_text('{}')
                (root / 'old.selection.json').write_text('{}')
                entry.update(existing_plan='old.json', selection='old.selection.json', plan_sha256=resume.sha(root/'old.json'))
            def fake(command, log, timeout):
                stage = command[-1]; calls.append(stage)
                if stage == 'generate':
                    return {'status': 'timeout', 'seconds': 60, 'returncode': None}
                result = Path(command[command.index('--result')+1])
                result.write_text(json.dumps({'makespan': 12, 'data_movement_bytes': {}}))
                return {'status': 'success', 'seconds': 1, 'returncode': 0}
            with patch.object(resume, 'ROOT', root), patch.object(resume, 'BASE', base), patch.object(resume, 'run_command', fake):
                rows = resume.run_batch('test_batch', [entry], 60, 1)
            return calls, rows[0]

    def test_reuse_skips_generation_and_does_not_double_count_cost(self):
        calls, row = self.run_fake(True)
        self.assertEqual(calls, ['evaluate'])
        self.assertEqual(row['status'], 'success')
        self.assertEqual(row['generate']['seconds'], 0)
        self.assertEqual(row['generate']['reused_from'], 'old.json')

    def test_generation_timeout_is_retained_and_not_evaluated(self):
        calls, row = self.run_fake(False)
        self.assertEqual(calls, ['generate'])
        self.assertEqual(row['status'], 'generate_timeout')
        self.assertNotIn('evaluate', row)
