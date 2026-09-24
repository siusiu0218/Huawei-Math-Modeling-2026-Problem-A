"""Known selection, failure, subprocess timeout and artifact-copy boundaries."""
import copy
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import portfolio_scheduler as portfolio


def outcomes(first=10, second=20):
    return [{'candidate': name, 'status': 'ok' if score else 'failed', 'makespan': score or ''}
            for name, score in zip(portfolio.CANDIDATES, (first, second))]


def result():
    return {'makespan': 10, 'num_cores': 2, 'memory_peak_by_core': {'0': {'UB': 60}},
            'capacity_bytes': {'UB': 100}, 'per_core_timeline': [{'ops': [{'end': 10}]}],
            'data_movement_bytes': dict.fromkeys(('added_copy_bytes', 'partition_added_copy_bytes',
                                                 'spill_added_copy_bytes', 'scheduled_copy_bytes'), 0)}


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / 'results/scratch'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='portfolio_test_', dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_minimum_successful_makespan_and_tie(self):
        for first, second, winner in [(10, 20, 'v001'), (20, 10, 'v008'), (10, 10, 'v001')]:
            rows = outcomes(first, second)
            before = copy.deepcopy(rows)
            self.assertEqual(portfolio.choose_candidate(list(reversed(rows)))['candidate'], winner)
            self.assertEqual(rows, before)

    def test_one_failure_uses_other_and_two_failures_no_winner(self):
        for first, second, winner in [(None, 20, 'v008'), (10, None, 'v001')]:
            self.assertEqual(portfolio.choose_candidate(outcomes(first, second))['candidate'], winner)
        self.assertIsNone(portfolio.choose_candidate(outcomes(None, None)))

    def test_missing_duplicate_and_invalid_score_rejected(self):
        for rows in [outcomes()[:1], [outcomes()[0]] * 2, outcomes(float('nan'), 10), outcomes(-1, 10)]:
            with self.assertRaises(ValueError):
                portfolio.choose_candidate(rows)

    def test_result_validation_rejects_invalid_metrics(self):
        self.assertEqual(portfolio.validate_result(result(), 2)['makespan'], 10)
        for field, value in [('makespan', 0), ('makespan', float('inf')), ('num_cores', 3),
                             ('capacity_bytes', {'UB': 1}), ('per_core_timeline', [{'ops': [{'end': 11}]}])]:
            bad = result()
            bad[field] = value
            with self.assertRaises(ValueError):
                portfolio.validate_result(bad, 2)

    def test_real_subprocess_success_exit_and_timeout(self):
        for source, limit, expected in [('pass', 5, 'ok'), ('raise SystemExit(7)', 5, 'failed'),
                                        ('import time; time.sleep(5)', .1, 'timeout')]:
            outcome = portfolio.run_phase([sys.executable, '-B', '-c', source], limit, self.root / f'{expected}.log')
            self.assertEqual(outcome['status'], expected)
            self.assertGreater(outcome['seconds'], 0)

    def test_failed_planner_does_not_invoke_evaluator(self):
        policy = {'blocks_per_core': 4, 'plan_timeout_seconds': 30, 'evaluation_timeout_seconds': 180}
        with patch.object(portfolio, 'run_phase', return_value={'status': 'timeout', 'seconds': 30, 'error': 'expired'}) as phase:
            row = portfolio.evaluate_candidate(self.root / 'candidate', Path('unused'), 2, 'v001', policy, Path('unused'))
        self.assertEqual(phase.call_count, 1)
        self.assertEqual(row['failure_phase'], 'plan')
        self.assertEqual(row['evaluation_seconds'], 0)
        self.assertEqual(row['status'], 'timeout')
        self.assertTrue((self.root / 'candidate/status.json').is_file())

    def test_evaluation_timeout_and_malformed_result_preserved(self):
        policy = {'blocks_per_core': 4, 'plan_timeout_seconds': 30, 'evaluation_timeout_seconds': 180}
        for evaluator_status in ('timeout', 'ok'):
            root = self.root / evaluator_status

            def fake_phase(command, timeout, log):
                if log.name == 'plan_process.log':
                    portfolio.write_json(root / 'plan.json', {'node_to_subgraph': {'1': 0}, 'core_schedules': [[0], []]})
                    return {'status': 'ok', 'seconds': 1, 'error': ''}
                if evaluator_status == 'ok':
                    (root / 'result.json').write_text('broken', encoding='utf-8')
                return {'status': evaluator_status, 'seconds': 2, 'error': 'expired' if evaluator_status == 'timeout' else ''}

            with patch.object(portfolio, 'run_phase', side_effect=fake_phase):
                row = portfolio.evaluate_candidate(root, Path('unused'), 2, 'v001', policy, Path('unused'))
            self.assertEqual(row['status'], 'timeout' if evaluator_status == 'timeout' else 'failed')
            self.assertEqual(row['plan_seconds'] + row['evaluation_seconds'], 3)
            self.assertTrue((root / 'plan.json').exists())

    def test_both_candidates_charged_and_selected_files_match(self):
        for statuses in [('ok', 'ok'), ('failed', 'ok'), ('failed', 'failed')]:
            exp = self.root / '_'.join(statuses)
            for folder in ('plans', 'metrics'):
                (exp / folder).mkdir(parents=True)

            def fake_candidate(root, graph, cores, candidate, policy, script):
                root.mkdir(parents=True)
                portfolio.write_json(root / 'plan.json', {'candidate': candidate})
                portfolio.write_json(root / 'result.json', {'candidate': candidate})
                return {'candidate': candidate, 'status': statuses[portfolio.CANDIDATES.index(candidate)],
                        'makespan': 10 if candidate == 'v008' else 20, 'added_copy_bytes': 0,
                        'plan_seconds': 1, 'evaluation_seconds': 2, 'wall_seconds': 3,
                        'plan_sha256': portfolio.digest(root / 'plan.json'), 'result_sha256': portfolio.digest(root / 'result.json')}

            with patch.object(portfolio, 'evaluate_candidate', side_effect=fake_candidate) as evaluate:
                selected, rows = portfolio.solve_configuration(exp, 'case_fake', 'development', 2, {}, Path('unused'))
            self.assertEqual(evaluate.call_count, 2)
            self.assertEqual(selected['plan_seconds'], 2)
            self.assertEqual(selected['evaluation_seconds'], 4)
            self.assertEqual(selected['candidate_wall_seconds'], 6)
            if statuses == ('failed', 'failed'):
                self.assertEqual(selected['status'], 'failed')
                self.assertEqual(list((exp / 'plans').iterdir()), [])
            else:
                self.assertEqual(selected['status'], 'ok' if statuses == ('ok', 'ok') else 'degraded')
                self.assertEqual(selected['selected_candidate'], 'v008')
                self.assertEqual(selected['selected_plan_sha256'], rows[1]['plan_sha256'])


if __name__ == '__main__':
    unittest.main()
