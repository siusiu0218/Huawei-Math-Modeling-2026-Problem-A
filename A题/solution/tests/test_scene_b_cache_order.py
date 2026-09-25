"""Q3 fixed-placement ordering: dependencies, locality and unchanged input."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'experiments')]
from scene_b_cache_order import reorder
from probe_problem3_rules import reads
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


class CacheOrderTests(unittest.TestCase):
    def test_locality_can_change_order_without_changing_placement(self):
        graph,base=reads([[1,2,1]],{1:60,2:60})
        original=deepcopy(base)
        result=reorder(graph,base)
        self.assertEqual(result['core_schedules'],[[1,3,2]])
        self.assertEqual(result['node_to_subgraph'],base['node_to_subgraph'])
        self.assertEqual(base,original)
        self.assertEqual(reorder(graph,base,'critical_path')['core_schedules'],[[1,2,3]])

    def test_cross_core_dependencies_and_idle_cores_are_preserved(self):
        graph={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':10} for i in range(1,5)],
            'tensors':[{'id':11,'pos':'UB','size':60},{'id':12,'pos':'UB','size':60}],
            'edges':[{'source':a,'target':b} for a,b in [(1,11),(11,2),(3,12),(12,4)]]}
        base={'node_to_subgraph':{str(i):i for i in range(1,5)},'core_schedules':[[1,4],[3,2],[]]}
        for mode in ('cache_affinity','critical_path'):
            result=reorder(graph,base,mode)
            self.assertEqual([set(x) for x in result['core_schedules']],[set(x) for x in base['core_schedules']])
            validate_task_order(derive_multicore_plan(graph,result))
            self.assertEqual(result,reorder(graph,base,mode))

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):reorder({}, {}, 'unsupported')


if __name__=='__main__':unittest.main()
