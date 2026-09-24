"""Connected fork/join graphs and contraction cycle boundaries."""
import copy
import random
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from branch_scheduler import make_plan, contract
from graph_analysis import Graph
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan


def graph(edges, n):
    return {'ops': [{'id': i, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 5000} for i in range(n)],
            'tensors': [{'id': 1000+k, 'pos': 'UB', 'size': 60} for k in range(len(edges))],
            'edges': [edge for k, (a, b) in enumerate(edges) for edge in
                      [{'source': a, 'target': 1000+k}, {'source': 1000+k, 'target': b}]]}


class BranchTests(unittest.TestCase):
    def test_connected_fork_uses_two_cores_without_mutating_graph(self):
        data = graph([(0,1),(0,2),(1,3),(2,4),(3,5),(4,5)], 6)
        original = copy.deepcopy(data)
        plan = make_plan(data, 2, 4)
        validate_task_order(derive_multicore_plan(data, plan))
        self.assertEqual(sum(bool(c) for c in plan['core_schedules']), 2)
        self.assertEqual(plan, make_plan(data, 2, 4))
        self.assertEqual(original, data)

    def test_alternate_path_and_random_dags_remain_acyclic(self):
        rng = random.Random(20260924)
        cases = [graph([(0,1),(1,2),(0,2)], 3)]
        for _ in range(30):
            cases.append(graph([(a,b) for a in range(12) for b in range(a+1,12)
                                if rng.random() < .25], 12))
        for data in cases:
            for cores in (2, 4):
                plan = make_plan(data, cores, 1)
                self.assertEqual(set(plan['node_to_subgraph']), {str(i) for i in range(len(data['ops']))})
                validate_task_order(derive_multicore_plan(data, plan))

    def test_chain_merges_to_one_task_when_cap_allows(self):
        data = graph([(i,i+1) for i in range(9)], 10)
        groups, preds, succs = contract(Graph(data), 50000)
        self.assertEqual(len(groups), 1)
        self.assertEqual(sorted(next(iter(groups.values()))), list(range(10)))


if __name__ == '__main__':
    unittest.main()
