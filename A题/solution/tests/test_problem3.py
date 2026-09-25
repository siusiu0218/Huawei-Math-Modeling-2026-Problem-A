"""Hand-derived Cache boundary expectations; no official evaluator changes."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'experiments'), str(ROOT/'tests')]
from probe_problem3_rules import reads, evaluate
from test_baseline_boundaries import chain
from run_problem3_pair import sha, valid_record
from run_problem2 import run_command
from result_paths import result_path


class CacheRulesTests(unittest.TestCase):
    def test_simultaneous_first_reads_are_two_misses(self):
        a,b = evaluate(*reads([[1],[1]], {1:600}))
        self.assertEqual((a['makespan'],b['makespan']), (21,21))
        self.assertEqual(b['cache_stats']['miss_bytes'],1200)
        self.assertEqual(b['cache_stats']['hits'],0)

    def test_delayed_hit_and_byte_weighting(self):
        a,b = evaluate(*reads([[1],[2,1]], {1:600,2:6000}))
        self.assertEqual((a['makespan'],b['makespan']), (121,114))
        self.assertEqual(b['cache_stats']['hit_rate'],600/7200)
        self.assertEqual(a['data_movement_bytes'],b['data_movement_bytes'])

    def test_fifo_hit_does_not_refresh(self):
        _,b = evaluate(*reads([[1,2],[3,1,4]],{1:600,2:1200,3:6000,4:600}),1800)
        self.assertEqual(b['cache_events'][-1]['evicted_tensor_ids'],[1001])
        self.assertEqual([x['tensor_id'] for x in b['cache_final_entries']],[1002,1004])

    def test_oversized_input_never_cached(self):
        _,b = evaluate(*reads([[1],[2,1]], {1:600,2:6000}),500)
        self.assertEqual(b['cache_stats']['hits'],0)
        self.assertEqual(b['cache_final_entries'],[])

    def test_hit_reinsertion_is_observed_implementation_behavior(self):
        _,b = evaluate(*reads([[1],[2,1],[3,4]],{1:600,2:6000,3:5940,4:120}),600)
        tail = b['cache_events'][-3:]
        self.assertEqual([(e['time'],e['event']) for e in tail],[(210,'hit'),(211,'insert'),(213,'insert')])
        self.assertEqual(tail[1]['evicted_tensor_ids'],[1001])
        self.assertEqual(tail[2]['evicted_tensor_ids'],[1004])
        # DDR finishes at 211 while Cache is active 210..213: independent pools.
        self.assertEqual(tail[2]['tensor_id'],1001)

    def test_cross_core_wait_and_copy_out_no_fill(self):
        a,b = evaluate(chain(),{'node_to_subgraph':{'2':0,'3':1},'core_schedules':[[0],[1]]})
        self.assertEqual((a['makespan'],b['makespan']),(534,534))
        self.assertEqual(b['cache_stats']['hits'],0)
        link=b['cross_core_transfers'][0]
        self.assertEqual(link['copy_in_start']-link['copy_out_end'],500)

    def test_no_access_and_zero_byte_conventions(self):
        for graph,plan in (reads([[]],{}),reads([[1]],{1:0})):
            _,b=evaluate(graph,plan)
            self.assertEqual(b['cache_stats']['accesses'],0)
            self.assertEqual(b['cache_stats']['hit_rate'],0)


class PairRunnerTests(unittest.TestCase):
    def test_result_hash_and_invalid_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp); path=out/'result.json'
            path.write_text(json.dumps({'makespan':4}),encoding='utf-8')
            record={'status':'success','result':'result.json','result_sha256':sha(path)}
            self.assertTrue(valid_record(record,out))
            path.write_text('{"makespan":5}',encoding='utf-8')
            self.assertFalse(valid_record(record,out))

    def test_controlled_failure_and_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            failure=run_command([sys.executable,'-c','raise SystemExit(3)'],out/'fail.txt',5)
            self.assertEqual(failure['status'],'failed')
            timeout=run_command([sys.executable,'-c','import time; time.sleep(5)'],out/'timeout.txt',0.05)
            self.assertEqual(timeout['status'],'timeout')

    def test_problem3_path(self):
        path=result_path('problem_3/v001/exp110')
        self.assertEqual(path.parts[-5:],('10_problem3','raw','problem_3','v001','exp110'))


if __name__ == '__main__':
    unittest.main()
