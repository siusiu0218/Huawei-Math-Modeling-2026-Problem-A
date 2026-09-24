"""A missing single-core denominator must be recovered without selecting winners."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from summarize_recovery import summarize


class RecoveryTests(unittest.TestCase):
    def test_recovery_preserves_failure_and_computes_mean_of_ratios(self):
        with tempfile.TemporaryDirectory() as directory:
            first, retry = (Path(directory) / name for name in ('first', 'retry'))
            common = {'problem': 1, 'algorithm_version': 'v001', 'protected_hashes_before': {},
                      'protected_inputs_unchanged': True, 'evaluation_config': {}, 'wait_config': {},
                      'source_hashes': {'src\\baseline.py': 'a', 'src\\graph_analysis.py': 'b'},
                      'parameters': {'blocks_per_core': 4}}
            for run in (first, retry):
                (run / 'metrics').mkdir(parents=True)
                (run / 'source').mkdir()
                manifest = dict(common, cases=['a', 'b'], cores=[1, 2])
                (run / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            for run, case, core, status, value in [
                (first, 'a', 1, 'ok', 100), (first, 'a', 2, 'ok', 50),
                (first, 'b', 1, 'timeout', ''), (first, 'b', 2, 'ok', 100),
                (retry, 'b', 1, 'ok', 150),
            ]:
                row = {'case': case, 'cores': core, 'status': status, 'makespan': value,
                       'speedup': '', 'experiment': run.name, 'split': 'tune' if case == 'a' else 'holdout'}
                (run / 'metrics' / f'{case}_n{core}_status.json').write_text(json.dumps(row), encoding='utf-8')
            failed = first / 'metrics/b_n1_status.json'
            before = failed.read_bytes()
            with redirect_stdout(io.StringIO()):
                summarize(first, retry)
            result = json.loads((retry / 'metrics/combined_aggregate.json').read_text(encoding='utf-8'))
            all_two = next(r for r in result if r['split'] == 'all' and r['cores'] == 2)
            self.assertEqual(all_two['mean_speedup'], 1.75)
            self.assertEqual(all_two['scored'], 2)
            self.assertEqual(failed.read_bytes(), before)
            retry_manifest = json.loads((retry / 'manifest.json').read_text(encoding='utf-8'))
            retry_manifest['parameters']['blocks_per_core'] = 8
            (retry / 'manifest.json').write_text(json.dumps(retry_manifest), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'partition parameter changed'):
                summarize(first, retry)
            with self.assertRaises(ValueError):
                # Successful results cannot be replaced with potentially better reruns.
                summarize(first, first)


if __name__ == '__main__':
    unittest.main()
