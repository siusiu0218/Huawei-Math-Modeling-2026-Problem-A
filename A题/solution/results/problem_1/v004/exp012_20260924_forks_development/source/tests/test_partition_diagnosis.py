"""Timeline accounting must not double-count simultaneous compute and transfers."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from diagnose_partition_regressions import decompose, union_duration


class TimelineAccountingTests(unittest.TestCase):
    def test_overlap_gap_and_empty_intervals(self):
        intervals = [{'start': a, 'end': b} for a, b in [(8, 10), (1, 4), (2, 6), (3, 3)]]
        self.assertEqual(union_duration(intervals), 7)
        self.assertEqual(union_duration([]), 0)

    def test_critical_core_excludes_other_core_and_overlapping_copy(self):
        tasks = [{'start': 0, 'end': 10, 'duration': 10},
                 {'start': 12, 'end': 20, 'duration': 8}]
        ops = [{'start': a, 'end': b, 'pipe': pipe} for a, b, pipe in
               [(0, 4, 'PIPE_MTE2'), (2, 8, 'PIPE_V'), (7, 9, 'PIPE_M'),
                (12, 15, 'PIPE_MTE2'), (15, 19, 'PIPE_V'), (19, 20, 'PIPE_MTE3')]]
        result = {'makespan': 20, 'per_core_timeline': [
            {'tasks': tasks, 'ops': ops},
            {'tasks': [{'start': 0, 'end': 5, 'duration': 5}],
             'ops': [{'start': 0, 'end': 5, 'pipe': 'PIPE_V'}]}]}
        actual = decompose(result)
        self.assertEqual(actual, {'last_core': 0, 'last_core_tasks': 2,
                                'compute_union': 11, 'copy_without_compute': 6,
                                'active_without_pipe': 1, 'outside_tasks': 2})


if __name__ == '__main__':
    unittest.main()
