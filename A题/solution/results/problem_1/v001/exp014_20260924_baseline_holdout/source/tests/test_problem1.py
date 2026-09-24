"""Known-answer examples at the graph-analysis and plan-output boundaries."""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT.parent / 'code')]
from graph_analysis import analyze_graph, Graph
from baseline import make_plan
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan


def diamond():
    # A(10) -> B(20), C(30) -> D(40). Longest compute chain = 80.
    return {
        'ops': [{'id': i, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': c}
                for i, c in [(1, 10), (2, 20), (3, 30), (4, 40)]],
        'tensors': [{'id': i, 'pos': 'UB', 'size': 16} for i in [11, 12, 13]],
        'edges': [{'source': a, 'target': b} for a, b in
                  [(1, 11), (11, 2), (11, 3), (2, 12), (3, 13), (12, 4), (13, 4)]],
    }


class AnalysisTests(unittest.TestCase):
    def test_diamond_known_features(self):
        row = analyze_graph(diamond())
        self.assertEqual(row['compute_ops'], 4)
        self.assertEqual(row['critical_compute_cycles'], 80)
        self.assertEqual(row['max_level_width'], 2)
        self.assertEqual(row['shared_input_tensors'], 1)
        self.assertEqual(row['compute_cycles'], 100)


if __name__ == '__main__':
    unittest.main()
