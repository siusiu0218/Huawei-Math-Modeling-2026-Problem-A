"""Freeze all 500 plans and strictly verified reuse provenance before evaluation."""
import json
from pathlib import Path
from datetime import datetime, timezone
from run_problem3_pair import sha, fingerprint
from run_problem2 import save

S=Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def main():
    q2=S/'outputs/09_problem2/raw/problem_2/v011/exp109_20260926_active_full'
    m=read(q2/'manifest.json')
    assert m['status']=='completed' and m['protected_unchanged']
    for rel,digest in m['protected_hashes_before'].items():
        assert sha(S.parent/rel)==digest,rel
    old=read(S/'experiments/problem3_v001_selection.json')
    plans=[];reuse={}
    for i in range(1,101):
        case=f'case_{i:03}'
        for n in range(1,6):
            stem=f'{case}_n{n}'
            rel=f'generated/{case}_k1_single/plan.json' if n==1 else f'plans/{stem}.json'
            path=q2/rel
            digest=m['output_hashes'][str(Path(rel))]
            assert sha(path)==digest
            plans.append(dict(case=case,cores=n,path=str(path),sha256=digest))
            if n>1:
                result=q2/'metrics'/f'{stem}.json'
                rd=m['output_hashes'][str(result.relative_to(q2))]
                assert sha(result)==rd
                reuse[stem]=[dict(mode='no_l2',source=str(result),result_sha256=rd,
                    source_manifest=str(q2/'manifest.json'),source_manifest_sha256=sha(q2/'manifest.json'),
                    plan_sha256=digest,original_seconds=None,
                    cost_note='Q2 v011 search and its v010 prerequisite: see upstream manifests; reuse is not cold-start zero cost')]
    for name in ('exp111_20260926_development','exp113_20260926_reserve_baseline'):
        root=S/'outputs/10_problem3/raw/problem_3/v001'/name
        prior=read(root/'manifest.json')
        assert prior['status']=='completed'
        for path,digest in prior['hashes_before'].items(): assert sha(path)==digest,path
        for it in prior['items']:
            stem=f"{it['case']}_n{it['cores']}"
            plan=next(x for x in plans if x['case']==it['case'] and x['cores']==it['cores'])
            assert it['plan_sha256']==plan['sha256']
            reuse[stem]=[]
            for mode in ('no_l2','cache'):
                r=[x for x in it['attempts'] if x['mode']==mode][-1]
                result=root/r['result']
                assert r['status']=='success' and sha(result)==r['result_sha256']
                reuse[stem].append(dict(mode=mode,source=str(result),result_sha256=r['result_sha256'],
                    source_manifest=str(root/'manifest.json'),source_manifest_sha256=sha(root/'manifest.json'),
                    plan_sha256=plan['sha256'],original_seconds=r['seconds']))
    scripts=[S/'experiments'/name for name in ('run_problem3_full.py','reuse_problem3_full.py','prepare_problem3_full.py','run_problem3_pair.py','run_problem2.py','result_paths.py')]
    selection=dict(created_utc=datetime.now(timezone.utc).isoformat(),version='v001',
        rule='All 100 graphs; fixed Q2 v011 plans, no Q3 performance-based plan selection; v002 rejected after reserve validation',
        timeout=180,concurrency=1,automatic_retries=0,
        config_sha256=sha(S.parent/'data/config.txt'),features=old['features'],
        cases=[dict(case=f'case_{i:03}',role='full') for i in range(1,101)],plans=plans,reuse=reuse,
        source_hashes=fingerprint(scripts+list((S.parent/'code').glob('*.py'))))
    dest=S/'experiments/problem3_full_selection.json'
    assert not dest.exists(),'Freeze exists; do not overwrite'
    save(dest,selection)
    print('plans',len(plans),'reused',sum(map(len,reuse.values())),'new',1000-sum(map(len,reuse.values())))

if __name__=='__main__': main()
