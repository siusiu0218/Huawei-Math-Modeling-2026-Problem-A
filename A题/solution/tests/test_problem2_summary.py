"""Mean speedups require every single-core denominator; failures stay visible."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from summarize_problem2_full import summarize


def fixture():
    rows=[]
    for i in range(1,101):
        for version,cores in [('single_v001',[1]),('v002',[2,3,4,5]),('v007',[2,3,4,5])]:
            for n in cores:
                rows.append({'version':version,'case':f'case_{i:03}','cores':n,
                             'status':'success','makespan':100/n,
                             'added_copy_bytes':0,'spill_added_copy_bytes':0})
    return rows


class SummaryTests(unittest.TestCase):
    def test_known_mean_speedups(self):
        means,comparison,slower=summarize(fixture())
        self.assertTrue(all(r['mean_speedup']==r['cores'] for r in means))
        self.assertEqual(len(comparison),400)
        self.assertTrue(all(r['outcome']=='equal' for r in comparison))
        self.assertFalse(slower)

    def test_missing_single_prevents_full_average(self):
        rows=fixture()
        rows[0]['status']='evaluate_timeout'
        rows[0]['makespan']=None
        means,comparison,_=summarize(rows)
        self.assertTrue(all(r['count']==99 and r['mean_speedup'] is None for r in means))
        self.assertEqual(len(comparison),400)

    def test_failed_candidate_remains_in_comparison(self):
        rows=fixture()
        failed=next(r for r in rows if r['version']=='v007' and r['cores']==2)
        failed.update(status='generate_failed',makespan=None)
        means,comparison,_=summarize(rows)
        self.assertEqual(sum(r['outcome']=='unavailable' for r in comparison),1)
        self.assertIsNone(next(r for r in means if r['version']=='v007' and r['cores']==2)['mean_speedup'])


if __name__=='__main__':
    unittest.main()
