"""An acyclic quotient can still destroy all branch parallelism."""
import unittest
from test_branches import graph
from graph_analysis import Graph
from branch_scheduler import contract as old_contract
from fork_preserving_scheduler import contract, make_plan
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan


class ForkPreservationTests(unittest.TestCase):
    def test_large_cap_keeps_diamond_parallel(self):
        data = graph([(0,1),(0,2),(1,3),(2,4),(3,5),(4,5)], 6)
        original = Graph(data)
        self.assertEqual(len(old_contract(original, 100000)[0]), 1)
        groups, preds, succs = contract(original, 100000)
        self.assertEqual(sorted(sorted(g) for g in groups.values()), [[0],[1,3],[2,4],[5]])
        self.assertEqual(sorted(map(len,succs.values())), [0,1,1,2])
        plan = make_plan(data, 2, 1)
        self.assertEqual(sum(bool(c) for c in plan['core_schedules']), 2)
        validate_task_order(derive_multicore_plan(data, plan))

    def test_multi_predecessor_join_is_not_absorbed(self):
        data = graph([(0,2),(1,2),(2,3)], 4)
        groups, _, _ = contract(Graph(data),100000)
        self.assertEqual(sorted(sorted(g) for g in groups.values()), [[0],[1],[2,3]])


if __name__ == '__main__':
    unittest.main()
