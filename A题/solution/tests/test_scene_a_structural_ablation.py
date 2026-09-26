import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from scene_a_structural_ablation import Graph,quotient,task_estimates,convex_closure,make_candidate
from multicore_cut_evaluate_problem_1 import evaluate_scene_a
from test_branches import graph


class StructuralAblationTests(unittest.TestCase):
    def test_shared_input_counted_per_task_not_per_consumer_op(self):
        data=graph([],3)
        data['tensors']=[{'id':1000,'pos':'UB','size':120}]
        data['edges']=[{'source':1000,'target':i} for i in range(3)]
        g=Graph(data)
        groups,_,_=quotient(g,{0:0,1:0,2:1})
        _,traffic=task_estimates(g,groups,60)
        self.assertEqual(traffic,{0:120,1:120})

    def test_convex_merge_includes_bypass(self):
        p={0:set(),1:{0},2:{0},3:{1,2}}
        s={0:{1,2},1:{3},2:{3},3:set()}
        self.assertEqual(convex_closure({0,1,3},p,s),{0,1,2,3})

    def test_controls_keep_partition_and_A_keeps_cores(self):
        data=graph([(0,2),(1,3),(2,4),(3,4)],5)
        plan={'node_to_subgraph':{str(i):i for i in range(5)},'core_schedules':[[0,2,4],[1,3]]}
        result=evaluate_scene_a(data,plan,60,{'L1':524288,'UB':131072},1000,100)
        old=copy.deepcopy((data,plan,result))
        for arm in ('A','B','C'):
            for index in range(4):
                generated,meta=make_candidate(data,plan,result,arm,index)
                self.assertEqual(generated,make_candidate(data,plan,result,arm,index)[0])
                if arm in ('A','B'): self.assertEqual(generated['node_to_subgraph'],plan['node_to_subgraph'])
                if arm=='A': self.assertEqual([set(x) for x in generated['core_schedules']],[set(x) for x in plan['core_schedules']])
                scored=evaluate_scene_a(data,generated,60,{'L1':524288,'UB':131072},1000,100)
                self.assertGreater(scored['makespan'],0)
        self.assertEqual((data,plan,result),old)

    def test_shared_tensor_grouping_removes_repeated_boundary_copy(self):
        data=graph([],4)
        for op in data['ops']: op['cycles']=1
        data['tensors']=[{'id':1000,'pos':'UB','size':60000}]
        data['edges']=[{'source':1000,'target':i} for i in range(4)]
        plan={'node_to_subgraph':{str(i):i for i in range(4)},'core_schedules':[[0,2],[1,3]]}
        result=evaluate_scene_a(data,plan,60,{'L1':524288,'UB':131072},1000,100)
        merged,meta=make_candidate(data,plan,result,'C',0)
        self.assertEqual(meta['route'],'shared_tensor_groups')
        self.assertLess(meta['boundary_bytes_after'],meta['boundary_bytes_before'])
        new=evaluate_scene_a(data,merged,60,{'L1':524288,'UB':131072},1000,100)
        self.assertEqual(result['data_movement_bytes']['partition_added_copy_bytes']-new['data_movement_bytes']['partition_added_copy_bytes'],meta['boundary_bytes_before']-meta['boundary_bytes_after'])


if __name__=='__main__':unittest.main()
