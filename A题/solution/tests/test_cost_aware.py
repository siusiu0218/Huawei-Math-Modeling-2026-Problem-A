import unittest

from test_branches import graph
from graph_analysis import Graph
from cost_aware_scheduler import contract, make_plan
from cost_boundary_scheduler import contract as indexed_contract
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan


class CostAwareTests(unittest.TestCase):
    def test_merge_requires_cost_advantage(self):
        data = graph([(0, 1)], 2)
        g = Graph(data)
        groups, _, _ = contract(g, cap=10000, num_cores=4)
        self.assertEqual(len(groups), 2)  # no transfer benefit; flexibility loss dominates

    def test_branch_boundaries_remain_parallel(self):
        data = graph([(0,1),(0,2),(1,3),(2,4),(3,5),(4,5)], 6)
        groups, preds, succs = contract(Graph(data), cap=100000, num_cores=2)
        self.assertGreaterEqual(len(groups), 3)
        plan = make_plan(data, 2, 1)
        self.assertEqual(sum(bool(c) for c in plan['core_schedules']), 2)
        validate_task_order(derive_multicore_plan(data, plan))

    def test_indexed_boundary_bytes_are_preserved(self):
        data = graph([(0, 1), (1, 2)], 3)
        g = Graph(data)
        groups, _, _ = indexed_contract(g, cap=10000, num_cores=2)
        self.assertEqual(sum(map(len, groups.values())), 3)
        self.assertEqual(g.boundary_bytes[(0, 1)], 60)
        self.assertEqual(g.boundary_bytes[(1, 2)], 60)


if __name__ == '__main__':
    unittest.main()
