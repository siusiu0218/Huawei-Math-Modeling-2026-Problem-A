"""Behavioral checks for oversized-component splitting and fallback."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from scene_b_split_components import make_plan
from scene_b_paired_order import make_plan as previous_plan
from test_scene_b_component_order import placement
from test_problem2 import evaluate


class SplitComponentTests(unittest.TestCase):
    def test_large_fork_uses_multiple_cores_and_preserves_input(self):
        data = {'ops': [{'id': 0, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10},
                        {'id': 99, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10}],
                'tensors': [{'id': 100, 'pos': 'UB', 'size': 16}],
                'edges': [{'source': 0, 'target': 100}]}
        for i in range(1, 11):
            data['ops'].append({'id': i, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 2000})
            data['edges'].append({'source': 100, 'target': i})
        original = copy.deepcopy(data)
        plan = make_plan(data, 5)
        self.assertEqual(set(plan['node_to_subgraph']), {str(o['id']) for o in data['ops']})
        self.assertGreater(len({placement(plan)[str(i)] for i in range(1, 11)}), 1)
        result = evaluate(data, plan['node_to_subgraph'], plan['core_schedules'])
        base = previous_plan(data, 5)
        old = evaluate(data, base['node_to_subgraph'], base['core_schedules'])
        self.assertLess(result['makespan'], old['makespan'])
        self.assertEqual(data, original)
        self.assertEqual(plan, make_plan(data, 5))

    def test_balanced_and_single_core_keep_previous_plan(self):
        data = {'ops': [{'id': i, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 20}
                        for i in range(10)], 'tensors': [], 'edges': []}
        for n in (1, 2, 5):
            self.assertEqual(make_plan(data, n), previous_plan(data, n))

    def test_connected_graph_keeps_previous_plan(self):
        from test_problem1 import diamond
        self.assertEqual(make_plan(diamond(), 5), previous_plan(diamond(), 5))

    def test_invalid_core_count(self):
        from test_problem1 import diamond
        for n in (0, -1, True):
            with self.assertRaises(ValueError):
                make_plan(diamond(), n)
