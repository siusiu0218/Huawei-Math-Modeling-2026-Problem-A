"""Known answers at existing graph-analysis and plan/evaluator boundaries."""
import copy
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from graph_analysis import Graph, analyze_graph, select_cases
from baseline import make_plan
from multicore_cut_evaluate_problem_1 import evaluate_scene_a
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan


def chain():
    return {
        'ops': [
            {'id': 1, 'op': 'COPY_IN', 'pipe': 'PIPE_MTE2', 'cycles': 1},
            {'id': 2, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10},
            {'id': 3, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 20},
            {'id': 4, 'op': 'COPY_OUT', 'pipe': 'PIPE_MTE3', 'cycles': 1}],
        'tensors': [{'id': i, 'pos': 'DDR' if i in (11, 15) else 'UB', 'size': 60}
                    for i in range(11, 16)],
        'edges': [{'source': a, 'target': b} for a, b in
                  [(11, 1), (1, 12), (12, 2), (2, 13), (13, 3), (3, 14), (14, 4), (4, 15)]],
    }


class BoundaryTests(unittest.TestCase):
    def test_known_transfer_and_wait_costs(self):
        data = chain()
        for mapping, orders, expected, extra in [
            ({'2': 0, '3': 0}, [[0]], 32, 0),
            ({'2': 0, '3': 1}, [[0, 1]], 134, 120),
            ({'2': 0, '3': 1}, [[0], [1]], 1034, 120),
        ]:
            with self.subTest(orders=orders):
                result = evaluate_scene_a(
                    data, {'node_to_subgraph': mapping, 'core_schedules': orders},
                    bandwidth=60, capacity={'L1': 524288, 'UB': 131072},
                    same_core_wait=100, cross_core_wait=1000)
                self.assertEqual(result['makespan'], expected)
                self.assertEqual(result['data_movement_bytes']['added_copy_bytes'], extra)

    def test_baseline_covers_ops_preserves_input_and_is_deterministic(self):
        data = chain()
        original = copy.deepcopy(data)
        for cores in range(2, 6):
            plan = make_plan(data, cores)
            self.assertEqual(set(plan['node_to_subgraph']), {'2', '3'})
            self.assertEqual(len(plan['core_schedules']), cores)
            validate_task_order(derive_multicore_plan(data, plan))
            self.assertEqual(make_plan(data, cores), plan)
        self.assertEqual(data, original)

    def test_copy_bridge_keeps_dependency(self):
        data = chain()
        # Turn the first compute operation into an excluded copy bridge.
        data['ops'][1]['op'] = 'COPY_IN'
        data['ops'][1]['pipe'] = 'PIPE_MTE2'
        data['ops'].insert(0, {'id': 0, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 7})
        data['edges'].insert(0, {'source': 0, 'target': 11})
        graph = Graph(data)
        self.assertEqual(graph.preds[3], {0})
        self.assertEqual(analyze_graph(data)['critical_compute_cycles'], 27)

    def test_selection_is_disjoint_and_includes_size_extremes(self):
        rows = [{'case': f'case_{i:03}', 'compute_ops': i,
                 'work_to_critical_ratio': i % 3, 'shared_input_bytes': i * 10,
                 'max_level_width': i % 4} for i in range(1, 101)]
        selected = select_cases(rows)
        self.assertEqual(len({r['case'] for r in selected}), 8)
        self.assertEqual(sum(r['split'] == 'holdout' for r in selected), 4)
        self.assertTrue({'case_001', 'case_100'} <= {r['case'] for r in selected})


if __name__ == '__main__':
    unittest.main()
