"""Hand-computable scene-B boundaries, using the unmodified evaluator."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT.parent / 'code'), str(ROOT / 'tests')]
from test_baseline_boundaries import chain
from multicore_cut_evaluate_problem_2 import evaluate_scene_b


def evaluate(data, mapping, orders, capacity=131072, delay=500):
    return evaluate_scene_b(data, {'node_to_subgraph': mapping, 'core_schedules': orders},
                            60, {'L1': 524288, 'UB': capacity}, delay)


class SceneBTests(unittest.TestCase):
    def test_same_core_reuses_across_subgraphs(self):
        for mapping, orders in [({'2': 0, '3': 0}, [[0]]),
                                ({'2': 0, '3': 1}, [[0, 1]])]:
            r = evaluate(chain(), mapping, orders)
            # 1 input + 10 compute + 20 compute + 1 output.
            self.assertEqual(r['makespan'], 32)
            self.assertEqual(r['data_movement_bytes']['added_copy_bytes'], 0)

    def test_cross_core_transfer_and_wait(self):
        for delay in (0, 500):
            r = evaluate(chain(), {'2': 0, '3': 1}, [[0], [1]], delay=delay)
            # Original 32 + 1 boundary COPY_OUT + 1 COPY_IN + delay.
            self.assertEqual(r['makespan'], 34 + delay)
            self.assertEqual(r['data_movement_bytes']['added_copy_bytes'], 120)
            self.assertEqual(len(r['cross_core_transfers']), 1)
            transfer = r['cross_core_transfers'][0]
            self.assertEqual(transfer['copy_in_start'] - transfer['copy_out_end'], delay)

    def test_infeasible_operation_working_set_is_rejected(self):
        # ADD needs its 60-byte input and 60-byte output simultaneously.
        with self.assertRaises((RuntimeError, ValueError)):
            evaluate(chain(), {'2': 0, '3': 0}, [[0]], capacity=60)

    def test_reversed_same_core_dependency_is_rejected(self):
        with self.assertRaisesRegex((RuntimeError, ValueError), 'dependency|topo|cycle'):
            evaluate(chain(), {'2': 0, '3': 1}, [[1, 0]])

    def test_live_tensor_spill(self):
        data = {
            'ops': [{'id': i, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10}
                    for i in range(1, 5)],
            'tensors': [{'id': i, 'pos': 'UB', 'size': 60} for i in (11, 12, 13)],
            'edges': [{'source': a, 'target': b} for a, b in
                      [(1, 11), (2, 12), (12, 3), (3, 13), (11, 4), (13, 4)]],
        }
        mapping = {str(i): i for i in range(1, 5)}
        roomy = evaluate(data, mapping, [[1, 2, 3, 4]], capacity=180)
        tight = evaluate(data, mapping, [[1, 2, 3, 4]], capacity=120)
        self.assertEqual(roomy['data_movement_bytes']['spill_added_copy_bytes'], 0)
        # Retain tensor 11 for op 4 while op 3 needs 12+13: evict and reload 60 bytes.
        self.assertEqual(tight['data_movement_bytes']['spill_added_copy_bytes'], 120)
        for peak in tight['memory_peak_by_core'].values():
            self.assertLessEqual(peak['UB'], 120)

    def test_cross_core_fifo_wait_cycle_is_rejected(self):
        # Two independent chains 1->2 and 3->4; each core prioritizes the
        # consumer waiting for the other core's later producer.
        data = {
            'ops': [{'id': i, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10}
                    for i in range(1, 5)],
            'tensors': [{'id': i, 'pos': 'UB', 'size': 60} for i in (11, 12)],
            'edges': [{'source': a, 'target': b} for a, b in
                      [(1, 11), (11, 2), (3, 12), (12, 4)]],
        }
        with self.assertRaisesRegex((RuntimeError, ValueError), 'cycle'):
            evaluate(data, {str(i): i for i in range(1, 5)}, [[2, 3], [4, 1]])


if __name__ == '__main__':
    unittest.main()
