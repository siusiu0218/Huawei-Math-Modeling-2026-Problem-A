import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'experiments')]
from scene_b_active_cores import candidate_specs,pad_plan,select_candidate
from run_problem2_active_cores import solve_case
from test_problem2 import evaluate
from test_scene_b_adaptive import many_components
from scene_b_paired_order import make_plan


class ActiveCoreTests(unittest.TestCase):
    def test_padding_preserves_input_and_evaluation(self):
        data=many_components()
        p=make_plan(data,2,same_core_wait=0,cross_core_wait=500)
        original=json.loads(json.dumps(p))
        q=pad_plan(p,5)
        self.assertEqual(q['core_schedules'][-3:],[[],[],[]])
        self.assertEqual(p,original)
        a=evaluate(data,p['node_to_subgraph'],p['core_schedules'])
        b=evaluate(data,q['node_to_subgraph'],q['core_schedules'])
        self.assertEqual(a['makespan'],b['makespan'])
        self.assertEqual(a['data_movement_bytes'],b['data_movement_bytes'])
        with self.assertRaises(ValueError):pad_plan(p,1)

    def test_all_candidates_and_ties(self):
        for n in range(2,6):
            rows=[dict(candidate=v,active_budget=k,status='success',makespan=10) for v,k in candidate_specs(n)]
            self.assertEqual(len(rows),2*n-1)
            winner=select_candidate(rows,n)
            self.assertEqual((winner['candidate'],winner['active_budget']),('v007',n))
            rows[0]['makespan']=9
            self.assertEqual(select_candidate(rows,n)['active_budget'],1)
            with self.assertRaises(ValueError):select_candidate(rows[:-1],n)

    def test_failure_and_invalid_score(self):
        rows=[dict(candidate=v,active_budget=k,status='timeout') for v,k in candidate_specs(2)]
        self.assertIsNone(select_candidate(rows,2))
        rows[0].update(status='success',makespan=float('nan'))
        with self.assertRaises(ValueError):select_candidate(rows,2)

    def test_cold_runner_reuses_generation_and_keeps_failures(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            for sub in ('plans','metrics','records'): (out/sub).mkdir()
            calls=[];records=[]
            def run(command,log,budget):
                stage=command[command.index('--worker')+1];calls.append(stage)
                n=int(command[command.index('--n')+1])
                if stage=='generate':
                    algo=command[command.index('--algorithm')+1]
                    if algo=='single':return dict(status='timeout',seconds=30)
                    p=Path(command[command.index('--plan')+1])
                    p.write_text(json.dumps({'node_to_subgraph':{'1':0},'core_schedules':[[0]]+[[] for _ in range(n-1)]}))
                else:
                    p=Path(command[command.index('--result')+1]);p.write_text(json.dumps({'makespan':10}))
                return dict(status='success',seconds=1)
            with patch('run_problem2_active_cores.run_command',side_effect=run),patch('run_problem2_active_cores.validate_result',return_value={'makespan':10}):
                solve_case('example',[2,3],out,None,{},records.append)
            self.assertEqual(calls.count('generate'),5)
            self.assertEqual(calls.count('evaluate'),2)
            self.assertEqual([r['status'] for r in records],['degraded','degraded'])
            self.assertTrue(all(r['candidates'][0]['status']=='generate_timeout' for r in records))
