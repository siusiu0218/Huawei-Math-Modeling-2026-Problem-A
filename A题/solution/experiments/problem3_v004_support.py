"""Frozen v004 worker and provenance-checked reuse adapters."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S/'src'))
from run_problem2 import save
from result_paths import result_path

BASE = result_path('problem_3/v003/exp121_20260926_v003_full')
PILOT = result_path('problem_3/v004/exp123_20260926_window_pilot')
TRANSFER = result_path('problem_3/v004/exp124_20260926_window_transfer')


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def base_path(case, cores):
    return BASE/'selected_plans'/f'{case}_n{cores}.json'


def source_paths():
    frozen = read(PILOT/'manifest.json')
    for p in (S/'src/scene_b_window_components.py', S/'src/graph_analysis.py'):
        if sha(p) != frozen['hashes_before'][str(p)]:
            raise ValueError('Frozen v004 algorithm changed: '+str(p))
    names = ['problem3_v004_support.py', 'run_problem3_v004_full.py', 'report_problem3_v004_full.py',
             'run_problem2.py', 'run_problem3_pair.py', 'result_paths.py', 'process_runner.py',
             'run_problem3_bounded.py', 'run_problem3_baseline.py']
    return [S/'experiments'/n for n in names] + [
        S/'src/scene_b_window_components.py', S/'src/scene_b_window_components.LICENSE',
        S/'src/graph_analysis.py', S.parent/'data/config.txt',
        S/'tests/test_problem3_v004_runner.py',
        *sorted((S.parent/'code').glob('*.py'))]


def reuse_index(cases, cores):
    index = {}
    official = [*sorted((S.parent/'code').glob('*.py')), S.parent/'data/config.txt']
    def compatible(root, m):
        for p in official:
            # Pilot keeps its copied config in hashes_before rather than the original path.
            key = str(p) if str(p) in m['hashes_before'] else str(root/'inputs/config.txt')
            if m['hashes_before'].get(key) != sha(p):
                raise ValueError('Incompatible reuse provenance: '+str(p))
    def add(root, m, case, n, plan, plan_hash, mode, result, digest, seconds):
        if case not in cases or n not in cores:
            return
        if sha(plan) != plan_hash or sha(result) != digest:
            raise ValueError('Reuse artifact changed')
        graph = S.parent/'data'/f'{case}.json'
        archived = root/'inputs'/graph.name
        expected = m['hashes_before'].get(str(graph),m['hashes_before'].get(str(archived)))
        if expected is None:
            expected = m.get('archive_hashes',{}).get(str(archived.relative_to(root)))
        if expected != sha(graph) or sha(archived) != expected:
            raise ValueError('Reuse graph mismatch')
        signature = hashlib.sha256(json.dumps(read(plan),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        index[f'{case}:{n}:{signature}:{mode}'] = {
            'source':str(result),'sha256':digest,'source_manifest':str(root/'manifest.json'),
            'source_manifest_sha256':sha(root/'manifest.json'),'source_plan':str(plan),
            'source_plan_sha256':plan_hash,'original_seconds':seconds,
            'note':'graph/plan/config/evaluator/result verified; historical cost is not zero'}
    m = read(BASE/'manifest.json');compatible(BASE,m)
    selected = {(r['case'],int(r['cores'])):r for r in csv.DictReader((BASE/'comparison.csv').open(encoding='utf-8-sig'))}
    for item in m['items']:
        case,n = item['case'],item['cores']
        if case not in cases or n not in cores:continue
        row = selected[case,n];candidate = item['candidates'][row['selected']]
        gen = candidate['generation'][-1]
        if sha(base_path(case,n)) != gen['sha256']:raise ValueError('Baseline changed')
        for mode, attempts in candidate['evaluations'].items():
            ev = attempts[-1]
            if ev['status']=='success':
                add(BASE,m,case,n,base_path(case,n),gen['sha256'],mode,BASE/ev['file'],ev['sha256'],ev['seconds'])
    for root in (PILOT,TRANSFER):
        m=read(root/'manifest.json');compatible(root,m)
        if root==PILOT:
            generated={(r['case'],f"w{r['window']}"):r for r in m['generation']}
            for ev in m['attempts']:
                if ev['status']!='success':continue
                case,label=ev['case'],ev['label'];g=generated[case,label]
                add(root,m,case,5,root/'plans'/f'{case}_{label}.json',g['plan_sha256'],
                    ev['mode'],root/ev['result'],ev['result_sha256'],ev['seconds'])
        else:
            for item in m['items']:
                for candidate in item['candidates'].values():
                    gen=candidate['generate']
                    if gen['status']!='success':continue
                    for mode,ev in candidate.items():
                        if mode=='generate' or ev['status']!='success':continue
                        add(root,m,item['case'],item['cores'],root/gen['file'],gen['sha256'],mode,
                            root/ev['file'],ev['sha256'],ev['seconds'])
    return index


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--graph',required=True)
    p.add_argument('--plan',required=True);p.add_argument('--cores',required=True,type=int);p.add_argument('--window',required=True,type=int)
    a=p.parse_args()
    from scene_b_window_components import make_plan
    save(Path(a.plan),make_plan(read(a.graph),a.cores,a.window,0.5))
