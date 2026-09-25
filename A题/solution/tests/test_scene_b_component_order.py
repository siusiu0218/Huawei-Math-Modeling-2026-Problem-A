"""Component priorities must preserve placement and cover every compute op."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from region_scheduler import make_plan as base_plan
from scene_b_component_order import make_plan


def placement(plan):
    cores = {group: core for core, groups in enumerate(plan['core_schedules']) for group in groups}
    return {node: cores[group] for node, group in plan['node_to_subgraph'].items()}


class ComponentOrderTests(unittest.TestCase):
    def test_many_components_keep_cores_but_get_separate_priorities(self):
        data = {'ops': [], 'tensors': [], 'edges': []}
        for i in range(20):
            a, b, t = i * 2, i * 2 + 1, 100 + i
            data['ops'] += [{'id': n, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10} for n in (a,b)]
            data['tensors'].append({'id': t, 'pos': 'UB', 'size': 60})
            data['edges'] += [{'source': a, 'target': t}, {'source': t, 'target': b}]
        original = copy.deepcopy(data)
        base = base_plan(data, 2, same_core_wait=0, cross_core_wait=500)
        result = make_plan(data, 2)
        self.assertEqual(placement(base), placement(result))
        self.assertEqual(len(set(result['node_to_subgraph'].values())), 20)
        for i in range(20):
            self.assertEqual(result['node_to_subgraph'][str(2*i)], result['node_to_subgraph'][str(2*i+1)])
        self.assertEqual(data, original)
        self.assertEqual(result, make_plan(data, 2))

    def test_single_component_is_unchanged(self):
        from test_baseline_boundaries import chain
        self.assertEqual(make_plan(chain(), 3), base_plan(chain(), 3, same_core_wait=0, cross_core_wait=500))

    def test_operation_priorities_preserve_placement_and_topology(self):
        from scene_b_operation_order import make_plan as operation_plan
        from test_problem1 import diamond
        data = diamond()
        data['ops'].append({'id': 50, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 5})
        base = base_plan(data, 2, same_core_wait=0, cross_core_wait=500)
        result = operation_plan(data, 2)
        self.assertEqual(placement(base), placement(result))
        self.assertEqual(len(set(result['node_to_subgraph'].values())), len(data['ops']))
        from test_problem2 import evaluate
        r = evaluate(data, result['node_to_subgraph'], result['core_schedules'])
        self.assertGreater(r['makespan'], 0)

    def test_paired_order_preserves_cores_and_local_dependencies(self):
        from scene_b_paired_order import make_plan as paired_plan
        from test_problem1 import diamond
        from test_problem2 import evaluate
        data = diamond()
        # Three more independent chains ensure at least two components/core.
        for a, b, t in [(30,31,130), (40,41,140), (50,51,150)]:
            data['ops'] += [{'id': n, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10} for n in (a,b)]
            data['tensors'].append({'id':t, 'pos':'UB', 'size':16})
            data['edges'] += [{'source':a, 'target':t}, {'source':t, 'target':b}]
        result = paired_plan(data, 2)
        self.assertEqual(placement(result), placement(base_plan(data, 2, same_core_wait=0, cross_core_wait=500)))
        self.assertEqual(len(result['node_to_subgraph']), len(data['ops']))
        self.assertGreater(evaluate(data,result['node_to_subgraph'],result['core_schedules'])['makespan'], 0)


if __name__ == '__main__':
    unittest.main()
