"""Baseline coverage and corrupt-pair handling, using saved evaluator evidence."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

SOLUTION=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOLUTION/'experiments'))
from run_problem3_baseline import summarize,cache_diagnosis
from run_problem3_pair import sha


class DevelopmentBaselineTests(unittest.TestCase):
    def test_selection_coverage_disjointness_and_no_seen_reserve(self):
        selection=json.loads((SOLUTION/'experiments/problem3_v001_selection.json').read_text(encoding='utf-8'))
        dev={x['case'] for x in selection['cases'] if x['role']=='development'}
        reserve={x['case'] for x in selection['cases'] if x['role']=='reserve'}
        self.assertEqual((len(dev),len(reserve)),(6,6))
        self.assertFalse(dev & reserve)
        self.assertNotIn('case_001',reserve)
        for role in ('development','reserve'):
            cells={(x['connected'],x['size_tertile']) for x in selection['cases'] if x['role']==role}
            self.assertEqual(len(cells),6)
        for case in dev|reserve:
            self.assertEqual({x['cores'] for x in selection['plans'] if x['case']==case},set(range(1,6)))

    def test_corrupted_result_is_missing_not_a_success(self):
        source=SOLUTION/'outputs/10_problem3/raw/problem_3/v001/exp110_20260926_pair_smoke'
        item={'case':'case_001','cores':2,'plan_sha256':'same-plan','attempts':[]}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);(out/'metrics').mkdir()
            for mode in ('no_l2','cache'):
                path=out/'metrics'/f'{mode}.json'
                shutil.copy2(source/'metrics'/f'{mode}_attempt1.json',path)
                item['attempts'].append({'mode':mode,'status':'success','result':str(path.relative_to(out)),
                    'result_sha256':sha(path),'seconds':0.1})
            rows,summary,failed=summarize({'items':[item]},out)
            self.assertEqual((len(rows),len(failed)),(1,0))
            self.assertEqual(summary[1]['mean_speedup'],1)
            (out/'metrics/cache.json').write_text('{}',encoding='utf-8')
            rows,summary,failed=summarize({'items':[item]},out)
            self.assertEqual((len(rows),len(failed)),(0,1))

    def test_reinsertion_diagnostic_identifies_hit_completion(self):
        source=SOLUTION/'outputs/10_problem3/raw/scratch/rules_v002_20260926/hit_reinsert.json'
        result=json.loads(source.read_text(encoding='utf-8'))['cache']
        diagnosis=cache_diagnosis(result)
        self.assertEqual(len(diagnosis['hit_completion_insert_events']),1)
        self.assertEqual(diagnosis['hit_completion_insert_events'][0]['time'],213)


if __name__=='__main__':unittest.main()
