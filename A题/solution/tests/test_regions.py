"""Hand-counted traffic and closed-region cases, including external consumers."""
import unittest
import random
import copy
from test_branches import graph
from test_baseline_boundaries import chain
from graph_analysis import Graph
from region_scheduler import (BoundaryTraffic, find_region, region_cost, merge_region,
                              make_plan, topological, edge_cost, merge_small_arms)
from multicore_cut_evaluate_problem_1 import evaluate_scene_a
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan


def singleton(data):
    g = Graph(data)
    groups = {n: [n] for n in g.order}
    return g, groups, {n: set(g.preds[n]) for n in g.order}, {n: set(g.succs[n]) for n in g.order}


class RegionTests(unittest.TestCase):
    def test_small_random_dags_keep_coverage_order_and_input(self):
        rng = random.Random(20260924)
        for _ in range(25):
            data = graph([(a, b) for a in range(12) for b in range(a + 1, 12)
                          if rng.random() < .25], 12)
            for op in data['ops']:
                op['cycles'] = rng.choice([1, 10, 1000])
            original = copy.deepcopy(data)
            plan = make_plan(data, 4, 1)
            self.assertEqual(set(plan['node_to_subgraph']), {str(n) for n in range(12)})
            validate_task_order(derive_multicore_plan(data, plan))
            self.assertEqual(plan, make_plan(data, 4, 1))
            self.assertEqual(data, original)

    def test_long_branch_loss_is_not_the_smaller_endpoint(self):
        data = graph([(0, 1), (0, 2), (1, 3), (2, 3)], 4)
        g, groups, preds, succs = singleton(data)
        weights = {0: 1, 1: 5000, 2: 5000, 3: 1}
        traffic = BoundaryTraffic(g, groups)
        self.assertEqual(edge_cost(0, 1, preds, succs, weights, traffic, 100)['compute_loss_bound'], 5000)
        self.assertEqual(edge_cost(1, 3, preds, succs, weights, traffic, 100)['compute_loss_bound'], 5000)
        accepted, _ = merge_small_arms(groups, preds, succs, weights, traffic, 100000, 100)
        self.assertEqual(accepted, [])

    def test_small_reduction_tree_merges_while_large_branches_stay(self):
        data = graph([(0, 4), (1, 4), (2, 5), (3, 5), (4, 6), (5, 6)], 7)
        g, groups, preds, succs = singleton(data)
        weights = {n: 5000 if n < 4 else 5 for n in groups}
        traffic = BoundaryTraffic(g, groups)
        accepted, _ = merge_small_arms(groups, preds, succs, weights, traffic, 100000, 100)
        self.assertEqual(len(accepted), 2)
        self.assertEqual(sorted(map(sorted, groups.values())), [[0], [1], [2], [3], [4, 5, 6]])
        self.assertEqual(len(topological(preds, succs)), 5)

    def test_second_merge_uses_removed_member_tensor(self):
        data = graph([(0, 1), (1, 2)], 3)
        data['tensors'][1]['size'] = 120
        g, groups, preds, succs = singleton(data)
        weights = {n: 5000 for n in g.order}
        traffic = BoundaryTraffic(g, groups)
        self.assertEqual(traffic.total(), 360)
        self.assertEqual(traffic.saving({0, 1}, 0), 120)
        merge_region([0, 1], groups, preds, succs, weights, traffic)
        self.assertEqual(traffic.saving({0, 2}, 0), 240)
        merge_region([0, 2], groups, preds, succs, weights, traffic)
        self.assertEqual(traffic.total(), 0)

    def test_shared_tensor_external_consumer_prevents_full_saving(self):
        data = graph([(0, 1)], 3)
        data['edges'].append({'source': 1000, 'target': 2})
        g, groups, preds, succs = singleton(data)
        weights = {n: 5000 for n in g.order}
        traffic = BoundaryTraffic(g, groups)
        self.assertEqual(traffic.total(), 180)
        self.assertEqual(traffic.saving({0, 1}, 0), 60)
        merge_region([0, 1], groups, preds, succs, weights, traffic)
        self.assertEqual(traffic.total(), 120)
        self.assertEqual(traffic.saving({0, 2}, 0), 120)
        for mapping, orders, expected in [
                ({'0': 0, '1': 1, '2': 2}, [[0, 1, 2]], 180),
                ({'0': 0, '1': 0, '2': 2}, [[0, 2]], 120)]:
            result = evaluate_scene_a(data, {'node_to_subgraph': mapping, 'core_schedules': orders},
                                      bandwidth=60, capacity={'L1': 524288, 'UB': 131072},
                                      same_core_wait=100, cross_core_wait=1000)
            self.assertEqual(result['data_movement_bytes']['scheduled_copy_bytes'], expected)

    def test_original_copy_output_stays_after_merge(self):
        data = chain()
        g, groups, preds, succs = singleton(data)
        traffic = BoundaryTraffic(g, groups)
        self.assertEqual(traffic.total(), 240)
        self.assertEqual(traffic.saving({2, 3}, 2), 120)
        traffic.merge({2, 3}, 2)
        self.assertEqual(traffic.total(), 120)

    def test_small_diamond_profitable_large_compute_diamond_rejected(self):
        for cycles, should_merge in [(10, True), (5000, False)]:
            data = graph([(0, 1), (0, 2), (1, 3), (2, 3)], 4)
            for op in data['ops']:
                op['cycles'] = cycles
            g, groups, preds, succs = singleton(data)
            weights = {n: cycles for n in g.order}
            region = find_region(0, preds, succs, weights, {n: n for n in g.order}, 100000)
            self.assertEqual(region, [0, 1, 2, 3])
            cost = region_cost(region, preds, weights, BoundaryTraffic(g, groups), 100)
            self.assertEqual(cost['saved_boundary_bytes'], 480)
            self.assertEqual(cost['compute_loss'], cycles)
            self.assertEqual(cost['saved_wait_proxy'], 200)
            self.assertEqual(cost['compute_loss'] < cost['saved_wait_proxy'] + cost['transfer_cycles_proxy'], should_merge)
            for cores in (2, 4):
                validate_task_order(derive_multicore_plan(data, make_plan(data, cores)))

    def test_external_entry_or_multiple_exits_cannot_be_contracted(self):
        for edges, count in [([(0, 1), (0, 2), (1, 3), (2, 3), (4, 2)], 5),
                             ([(0, 1), (0, 2), (1, 3)], 4)]:
            g, _, preds, succs = singleton(graph(edges, count))
            order = topological(preds, succs)
            self.assertIsNone(find_region(0, preds, succs, {n: 10 for n in order},
                                          {n: i for i, n in enumerate(order)}, 100000))


if __name__ == '__main__':
    unittest.main()
