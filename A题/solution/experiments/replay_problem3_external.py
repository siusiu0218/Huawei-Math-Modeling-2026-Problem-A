"""Bounded external-plan replay; no third-party Python is executed."""
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import time
import urllib.request
from collections import defaultdict

sys.dont_write_bytecode = True
from process_runner import run_command

S = Path(__file__).resolve().parents[1]
ROOT = S.parent
COMMIT = '4bebdda48585cb751466b504e05865cb39673593'
URL = 'https://raw.githubusercontent.com/zhuangzhuangaiyutingya/2026_match_model_A_openproject/' + COMMIT + '/'
EXPERIMENT = 'exp122_20260926_external_replay'
OUT = S/'outputs/10_problem3/raw/problem_3/v003'/EXPERIMENT
BASE = S/'outputs/10_problem3/raw/problem_3/v003/exp121_20260926_v003_full'
CASES = {'case_054':'external_faster_large', 'case_069':'external_faster_small',
         'case_001':'equal', 'case_013':'near_equal',
         'case_026':'ours_faster', 'case_044':'ours_faster'}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def get(rel, dest):
    dest.write_bytes(urllib.request.urlopen(URL+rel, timeout=60).read())


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    for d in ('inputs','plans','metrics','logs','source','external'):
        (OUT/d).mkdir()
    get('results/report/all_results.csv', OUT/'external/all_results.csv')
    for name in ('LICENSE', 'src/scheduler.py', 'docs/OPTIMIZATION_NOTES.md'):
        get(name, OUT/'external'/Path(name).name)
    rows = list(csv.DictReader((OUT/'external/all_results.csv').open(encoding='utf-8-sig')))
    remote = {r['case']:r for r in rows if r['problem']=='3' and r['cores']=='5'}
    local = {r['case']:r for r in csv.DictReader((BASE/'comparison.csv').open(encoding='utf-8-sig')) if r['cores']=='5'}
    originals = list((ROOT/'code').glob('*.py'))+[ROOT/'data/config.txt']
    for case in CASES:
        originals.append(ROOT/'data'/f'{case}.json')
        shutil.copy2(originals[-1], OUT/'inputs'/f'{case}.json')
        shutil.copy2(BASE/'selected_plans'/f'{case}_n5.json', OUT/'plans'/f'{case}_ours.json')
        get(f'results/best_plans/{case}_p3_k5.json', OUT/'plans'/f'{case}_external.json')
    shutil.copy2(ROOT/'data/config.txt', OUT/'inputs/config.txt')
    for p in [Path(__file__), S/'experiments/process_runner.py', S/'experiments/run_problem3_pair.py', *list((ROOT/'code').glob('*.py'))]:
        shutil.copy2(p, OUT/'source'/p.name)
    m = {'experiment':EXPERIMENT, 'version':'v003 versus external pinned plans', 'commit':COMMIT,
         'purpose':'post-hoc diagnostic, not a new algorithm or held-out validation',
         'cases':CASES,'cores':5,'modes':['cache','no_l2'], 'timeout_seconds':180,
         'selection':'two largest gaps (one >9000 ops, one <=1500), equal/near-equal controls, two largest reverse gaps',
         'hypotheses':['published gap survives local replay', 'placement workload lower bound falls on external winners',
                       'remaining savings accompany reduced movement or scheduling waits; no causal attribution without trace'],
         'hashes_before':{str(p):sha(p) for p in originals},
         'archive_hashes':{str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file()},
         'upstream_search_cost':'external plans reused; search not repeated and cost not zero',
         'command':[sys.executable,*sys.argv], 'attempts':[], 'status':'running'}
    save(OUT/'manifest.json',m)
    start = time.perf_counter()
    for case in CASES:
        for owner in ('ours','external'):
            for mode in ('cache','no_l2'):
                stem=f'{case}_{owner}_{mode}'
                cmd=[sys.executable,str(S/'experiments/run_problem3_pair.py'),'--worker',mode,
                     '--graph',str(OUT/'inputs'/f'{case}.json'),'--plan',str(OUT/'plans'/f'{case}_{owner}.json'),
                     '--config',str(OUT/'inputs/config.txt'),'--result',str(OUT/'metrics'/f'{stem}.json')]
                rec=run_command(cmd,OUT/'logs'/f'{stem}.txt',180)
                rec.update(case=case,owner=owner,mode=mode)
                result=OUT/'metrics'/f'{stem}.json'
                if rec['status']=='success':
                    data=json.loads(result.read_text(encoding='utf-8'))
                    assert data['makespan']>0 and data['num_cores']==5
                    rec.update(result=str(result.relative_to(OUT)),result_sha256=sha(result),makespan=data['makespan'])
                m['attempts'].append(rec);save(OUT/'manifest.json',m)
                print(stem,rec['status'],rec.get('makespan'),flush=True)
    m['seconds']=time.perf_counter()-start
    m['hashes_after']={str(p):sha(p) for p in originals}
    assert m['hashes_before']==m['hashes_after']
    assert all(sha(OUT/p)==h for p,h in m['archive_hashes'].items())
    m['status']='completed' if all(x['status']=='success' for x in m['attempts']) else 'incomplete'
    save(OUT/'manifest.json',m)
    if m['status']!='completed':
        raise SystemExit('incomplete; failed attempts retained')
    results=[]
    for case in CASES:
        graph=json.loads((OUT/'inputs'/f'{case}.json').read_text(encoding='utf-8'))
        for owner in ('ours','external'):
            plan=json.loads((OUT/'plans'/f'{case}_{owner}.json').read_text(encoding='utf-8'))
            cores={g:c for c,order in enumerate(plan['core_schedules']) for g in order}
            work=defaultdict(int)
            for op in graph['ops']:
                if op['op'] not in ('COPY_IN','COPY_OUT'):
                    work[cores[plan['node_to_subgraph'][str(op['id'])]],op['pipe']]+=op['cycles']
            cache=json.loads((OUT/'metrics'/f'{case}_{owner}_cache.json').read_text())
            no=json.loads((OUT/'metrics'/f'{case}_{owner}_no_l2.json').read_text())
            reported=int(remote[case]['makespan']) if owner=='external' else int(local[case]['C_selected_cache'])
            results.append({'case':case,'owner':owner,'reported_cache':reported,'cache':cache['makespan'],
                'matches_reported':reported==cache['makespan'],'no_l2':no['makespan'],
                'same_plan_cache_speedup':no['makespan']/cache['makespan'],
                'compute_bound':max(work.values()), 'core_pipe_work':{f'{c}:{p}':v for (c,p),v in work.items()},
                'subgraphs':len(cores),'movement':cache['data_movement_bytes'],'cache_stats':cache['cache_stats'],
                'external_label':remote[case]['label'] if owner=='external' else local[case]['selected']})
    save(OUT/'comparison.json',results)
    print(json.dumps(results,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
