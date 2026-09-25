"""Verify bounded local candidate selection without global-score selection."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from scene_b_adaptive import make_plan_with_stats, interleave
from graph_analysis import Graph
from component_scheduler import independent_components
from region_scheduler import make_plan as base_plan
from test_problem2 import evaluate
from test_scene_b_component_order import placement


def many_components():
    data = {'ops': [], 'tensors': [], 'edges': []}
    for i in range(20):
        a, b, t = 2*i, 2*i+1, 100+i
        data['ops'] += [{'id': n, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 20} for n in (a, b)]
        data['tensors'].append({'id': t, 'pos': 'UB', 'size': 16})
        data['edges'] += [{'source': a, 'target': t}, {'source': t, 'target': b}]
    return data


class AdaptiveTests(unittest.TestCase):
    def test_wide_batches_keep_assignment_coverage_and_dependencies(self):
        data = many_components(); original = copy.deepcopy(data)
        graph = Graph(data); components = independent_components(graph)
        base = base_plan(data, 2, same_core_wait=0, cross_core_wait=500)
        for width in (2, 4, 8):
            plan = interleave(graph, components, base, width)
            self.assertEqual(placement(plan), placement(base))
            self.assertEqual(set(plan['node_to_subgraph']), {str(x) for x in graph.ops})
            self.assertGreater(evaluate(data, plan['node_to_subgraph'], plan['core_schedules'])['makespan'], 0)
        self.assertEqual(data, original)

    def test_selection_records_all_local_costs_and_uses_minimum(self):
        data = many_components()
        plan, stats = make_plan_with_stats(data, 2)
        self.assertLessEqual(stats['local_preparations'], 4)
        valid = [r for r in stats['candidates'] if r['status'] == 'success']
        self.assertEqual(stats['selected'], min(valid, key=lambda r: r['score'])['name'])
        self.assertEqual((plan, stats), make_plan_with_stats(data, 2))
        self.assertGreater(evaluate(data, plan['node_to_subgraph'], plan['core_schedules'])['makespan'], 0)

    def test_connected_fallback_does_not_run_candidate_preparations(self):
        from test_problem1 import diamond
        with patch('scene_b_adaptive._build_scene_b_tasks', side_effect=AssertionError('unexpected scoring')):
            _, stats = make_plan_with_stats(diamond(), 3)
        self.assertEqual(stats['local_preparations'], 0)

    def test_local_failure_is_disclosed_and_other_candidates_can_succeed(self):
        import scene_b_adaptive
        real = scene_b_adaptive._build_scene_b_tasks
        attempts = []
        def failing_first(*args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise ValueError('candidate invalid')
            return real(*args, **kwargs)
        with patch('scene_b_adaptive._build_scene_b_tasks', side_effect=failing_first):
            _, stats = make_plan_with_stats(many_components(), 2)
        self.assertEqual(stats['candidates'][0]['status'], 'failed')
        self.assertNotEqual(stats['selected'], stats['candidates'][0]['name'])
