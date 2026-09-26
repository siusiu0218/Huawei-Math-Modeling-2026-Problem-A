import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from scene_a_critical_local import occupancy, diagnose, repack
from scene_a_critical_merge import candidates as neighbour_candidates


class CriticalChainTests(unittest.TestCase):
    def test_overlap_is_not_double_counted(self):
        ops = [{'pipe':'PIPE_M','start':0,'end':10},
               {'pipe':'PIPE_MTE2','start':5,'end':15}]
        self.assertEqual(occupancy(ops,0,20),dict(compute_only=5,transfer_only=5,overlap=5,inactive=5))

    def test_observed_chain_contains_core_order_and_dependency_wait(self):
        result = {'task_same_core_wait_cycles':2,'task_cross_core_wait_cycles':10,'makespan':35,'num_cores':2,
                  'task_dependencies':[{'source':0,'target':2}],
                  'step3_by_task':{str(i):{'local_makespan':d} for i,d in [(0,10),(1,5),(2,15)]},
                  'per_core_timeline':[
                      {'core_id':0,'tasks':[{'task_id':0,'start':0,'end':10,'duration':10},{'task_id':1,'start':12,'end':17,'duration':5}],
                       'ops':[{'task_id':0,'pipe':'PIPE_M','start':0,'end':10},{'task_id':1,'pipe':'PIPE_V','start':12,'end':17}]},
                      {'core_id':1,'tasks':[{'task_id':2,'start':20,'end':35,'duration':15}],
                       'ops':[{'task_id':2,'pipe':'PIPE_MTE2','start':20,'end':35}]}]}
        d = diagnose(result)
        self.assertEqual(d['chain'],[0,2])
        self.assertEqual(d['chain_breakdown']['cross_wait'],10)
        self.assertEqual(sum(d['chain_breakdown'].values()),35)
        result['per_core_timeline'][1]['tasks'][0]['start'] = 21
        with self.assertRaisesRegex(ValueError,'activation gap'): diagnose(result)

    def test_nonconvex_merge_is_rejected(self):
        # a -> b -> c: merging a,c would form a task-level cycle.
        class TinyGraph:
            order = [0,1,2]
            preds = {0:set(),1:{0},2:{1}}
            ops = {n:{'pipe':'PIPE_M','cycles':1} for n in order}
        plan = {'node_to_subgraph':{'0':0,'1':1,'2':2},'core_schedules':[[0,1,2],[]]}
        result = {'task_same_core_wait_cycles':0,'task_cross_core_wait_cycles':0,
                  'per_core_timeline':[{'tasks':[{'task_id':i,'start':i,'duration':1} for i in range(3)]}]}
        with self.assertRaisesRegex(ValueError,'cycle'):
            repack(TinyGraph(),plan,result,{0:0,1:1,2:0},{0},{0:0})

    def test_independent_neighbours_can_share_one_boundary_input(self):
        data={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':10} for i in (0,1)],
              'tensors':[{'id':10,'pos':'L1','size':60}],
              'edges':[{'source':10,'target':i} for i in (0,1)]}
        plan={'node_to_subgraph':{'0':0,'1':1},'core_schedules':[[0,1],[]]}
        result={'task_same_core_wait_cycles':2,'task_cross_core_wait_cycles':10,
                'makespan':22,'num_cores':2,'task_dependencies':[],
                'step3_by_task':{'0':{'local_makespan':10},'1':{'local_makespan':10}},
                'per_core_timeline':[
                    {'core_id':0,'tasks':[{'task_id':0,'start':0,'end':10,'duration':10},{'task_id':1,'start':12,'end':22,'duration':10}],
                     'ops':[{'task_id':0,'pipe':'PIPE_V','start':0,'end':10},{'task_id':1,'pipe':'PIPE_V','start':12,'end':22}]},
                    {'core_id':1,'tasks':[],'ops':[]}]}
        generated=list(neighbour_candidates(data,plan,result))
        self.assertEqual(len(generated),1)
        _,candidate,edit,error=generated[0]
        self.assertIsNone(error)
        self.assertEqual(edit['predicted_partition_byte_saving'],60)
        self.assertEqual(candidate['node_to_subgraph'],{'0':0,'1':0})
        self.assertEqual(candidate['core_schedules'],[[0],[]])


if __name__ == '__main__': unittest.main()
