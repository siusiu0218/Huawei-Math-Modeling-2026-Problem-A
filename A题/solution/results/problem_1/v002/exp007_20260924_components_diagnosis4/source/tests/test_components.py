"""Preserve whole independent branches through the public plan interface."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from component_scheduler import make_plan
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


def independent_chains():
    # ID order intentionally interleaves four independent two-operation chains.
    return {'ops': [{'id': i, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10} for i in range(8)],
            'tensors': [{'id': 100+i, 'pos': 'UB', 'size': 60} for i in range(4)],
            'edges': [e for i in range(4) for e in
                      [{'source': i, 'target': 100+i}, {'source': 100+i, 'target': i+4}]]}


class ComponentTests(unittest.TestCase):
    def test_independent_chains_stay_whole_and_use_cores(self):
        graph = independent_chains()
        for cores in (2, 3, 4, 5):
            plan = make_plan(graph, cores)
            view = derive_multicore_plan(graph, plan)
            validate_task_order(view)
            self.assertEqual(len(view['dependency_pairs']), 0)
            self.assertEqual(sum(bool(c) for c in plan['core_schedules']), min(cores, 4))
            for i in range(4):
                self.assertEqual(plan['node_to_subgraph'][str(i)], plan['node_to_subgraph'][str(i+4)])
            self.assertEqual(plan, make_plan(graph, cores))

    def test_connected_graph_fallback_stays_legal(self):
        graph = independent_chains()
        graph['edges'] += [{'source': 100, 'target': i} for i in (1, 2, 3)]
        plan = make_plan(graph, 3)
        validate_task_order(derive_multicore_plan(graph, plan))
        self.assertEqual(set(plan['node_to_subgraph']), {str(i) for i in range(8)})


if __name__ == '__main__':
    unittest.main()
