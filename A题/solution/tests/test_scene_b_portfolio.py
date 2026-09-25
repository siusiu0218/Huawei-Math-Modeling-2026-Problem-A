import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'experiments')]
from scene_b_portfolio import choose_candidate,plan_digest
from run_problem2_portfolio import solve


class PortfolioBTests(unittest.TestCase):
    def test_minimum_and_stable_tie(self):
        rows=[{'candidate':'v009','status':'success','makespan':20},
              {'candidate':'v007','status':'success','makespan':20}]
        self.assertEqual(choose_candidate(rows)['candidate'],'v007')
        rows[0]['makespan']=19
        self.assertEqual(choose_candidate(rows)['candidate'],'v009')

    def test_failures_and_bad_scores(self):
        rows=[{'candidate':'v007','status':'generate_timeout'}, {'candidate':'v009','status':'success','makespan':10}]
        self.assertEqual(choose_candidate(rows)['candidate'],'v009')
        rows[1]['makespan']=float('nan')
        with self.assertRaises(ValueError): choose_candidate(rows)
        rows[1]['status']='evaluate_failed'
        self.assertIsNone(choose_candidate(rows))

    def test_hash_ignores_dictionary_order_but_preserves_schedule_order(self):
        self.assertEqual(plan_digest({'a':1,'b':[2,3]}),plan_digest({'b':[2,3],'a':1}))
        self.assertNotEqual(plan_digest({'b':[2,3]}),plan_digest({'b':[3,2]}))

    def fake_solve(self, fail_first=False):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            for sub in ['plans','metrics','records','candidates']: (out/sub).mkdir()
            calls=[]
            def fake(command, log, timeout):
                stage=command[-1]; calls.append(stage)
                if fail_first and len(calls)==1:
                    return {'status':'timeout','seconds':30,'returncode':None}
                path=Path(command[command.index('--plan' if stage=='generate' else '--result')+1])
                path.write_text(json.dumps({'same_plan':True} if stage=='generate' else {'makespan':10}))
                return {'status':'success','seconds':1,'returncode':0}
            with patch('run_problem2_portfolio.run_command',side_effect=fake), patch('run_problem2_portfolio.validate_result',return_value={'makespan':10}):
                row=solve('case_test',2,out)
            return calls,row

    def test_identical_plans_share_one_real_evaluation(self):
        calls,row=self.fake_solve()
        self.assertEqual(calls,['generate','evaluate','generate'])
        self.assertEqual(row['selected'],'v007')
        self.assertEqual(row['status'],'success')
        self.assertEqual(row['candidates'][1]['evaluate']['reused_from'],'v007')

    def test_failed_candidate_does_not_hide_degraded_status(self):
        calls,row=self.fake_solve(True)
        self.assertEqual(calls,['generate','generate','evaluate'])
        self.assertEqual(row['status'],'degraded')
        self.assertEqual(row['selected'],'v009')
