from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT.parent/'code')]
from scene_b_bounded_order import reorder


class BoundedOrderTests(unittest.TestCase):
    def graph(self):
        return {'ops': [{'id': i, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 10} for i in range(1, 5)],
                'tensors': [{'id': 11, 'pos': 'UB', 'size': 60}, {'id': 12, 'pos': 'UB', 'size': 60}],
                'edges': [{'source': a, 'target': b} for a, b in [(1, 11), (11, 2), (3, 12), (12, 4)]]}

    def test_close_one_chain_before_opening_another(self):
        base = {'node_to_subgraph': {str(i): i for i in range(1, 5)}, 'core_schedules': [[1, 3, 2, 4], []]}
        original = deepcopy(base)
        self.assertEqual(reorder(self.graph(), base)['core_schedules'], [[1, 2, 3, 4], []])
        self.assertEqual(reorder(self.graph(), base, 2), original)
        self.assertEqual(base, original)

    def test_cross_core_component_retains_valid_original(self):
        base = {'node_to_subgraph': {str(i): i for i in range(1, 5)}, 'core_schedules': [[1, 4], [3, 2], []]}
        self.assertEqual(reorder(self.graph(), base), base)

    def test_bad_width_rejected(self):
        for width in [0, -1, True, 1.5]:
            with self.assertRaises(ValueError):
                reorder({}, {}, width)


if __name__ == '__main__':
    unittest.main()
