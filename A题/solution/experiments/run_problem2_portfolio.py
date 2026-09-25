"""Fresh, bounded v010 experiments; no historical result used for selection."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from scene_b_portfolio import choose_candidate, plan_digest
from portfolio_scheduler import validate_result
from run_problem2 import run_command, save


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def solve(case, n, out):
    key = f'{case}_n{n}'
    rows, evaluated = [], {}
    for candidate, algorithm, budget in [('v007', 'paired_order', 30), ('v009', 'adaptive', 300)]:
        folder = out / 'candidates' / key / candidate
        folder.mkdir(parents=True, exist_ok=False)
        plan_path, result_path = folder / 'plan.json', folder / 'result.json'
        common = [sys.executable, '-B', str(ROOT / 'experiments/run_problem2.py'), '--algorithm', algorithm,
                  '--input', str(ROOT.parent / 'data' / f'{case}.json'), '--config', str(ROOT.parent / 'data/config.txt'),
                  '--n', str(n), '--plan', str(plan_path), '--result', str(result_path)]
        row = {'candidate': candidate, 'status': 'running', 'generation_budget': budget,
               'plan': str(plan_path.relative_to(out)), 'result': str(result_path.relative_to(out))}
        rows.append(row)
        save(folder / 'candidate.json', row)
        row['generate'] = run_command(common + ['--worker', 'generate'], folder / 'generate.log', budget)
        save(folder / 'candidate.json', row)
        if row['generate']['status'] != 'success':
            row['status'] = 'generate_' + row['generate']['status']
        else:
            digest = plan_digest(json.loads(plan_path.read_text(encoding='utf-8')))
            row['canonical_plan_sha256'] = digest
            if digest in evaluated:
                previous = evaluated[digest]
                shutil.copy2(out / previous['result'], result_path)
                row['evaluate'] = {'status': 'success', 'seconds': 0, 'reused_from': previous['candidate']}
            else:
                row['evaluate'] = run_command(common + ['--worker', 'evaluate'], folder / 'evaluate.log', 180)
            if row['evaluate']['status'] != 'success':
                row['status'] = 'evaluate_' + row['evaluate']['status']
            else:
                result = json.loads(result_path.read_text(encoding='utf-8'))
                try:
                    row.update(validate_result(result, n))
                    row['status'] = 'success'
                    evaluated[digest] = row
                except (ValueError, KeyError, TypeError) as error:
                    row.update(status='invalid_result', error=str(error))
        save(folder / 'candidate.json', row)
    best = choose_candidate(rows)
    record = {'case': case, 'cores': n, 'candidates': rows,
              'status': 'failed' if best is None else 'success' if all(r['status'] == 'success' for r in rows) else 'degraded'}
    if best:
        shutil.copy2(out / best['plan'], out / 'plans' / f'{key}.json')
        shutil.copy2(out / best['result'], out / 'metrics' / f'{key}.json')
        record.update(selected=best['candidate'], makespan=best['makespan'])
    save(out / 'records' / f'{key}.json', record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', required=True)
    parser.add_argument('--cases', nargs='+', required=True)
    parser.add_argument('--cores', nargs='+', type=int, default=[2, 3, 4, 5])
    parser.add_argument('--workers', type=int, choices=[1, 2], default=2)
    parser.add_argument('--freeze', type=Path)
    args = parser.parse_args()
    if Path(args.experiment).name != args.experiment or any(n not in range(2,6) for n in args.cores):
        parser.error('invalid experiment or core count')
    if len(set(args.cases)) != len(args.cases) or len(set(args.cores)) != len(args.cores):
        parser.error('duplicate configurations')
    if args.freeze:
        frozen = json.loads(args.freeze.read_text(encoding='utf-8'))
        for rel, digest in frozen['source_hashes'].items():
            assert sha(ROOT / rel) == digest, rel
    out = ROOT / 'outputs/09_problem2/raw/problem_2/v010' / args.experiment
    out.mkdir(parents=True, exist_ok=False)
    for sub in ['plans','metrics','records','candidates','source']:
        (out/sub).mkdir()
    for sub in ['src','tests']:
        shutil.copytree(ROOT/sub, out/'source'/sub, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT.parent/'code',out/'source/code',ignore=shutil.ignore_patterns('__pycache__'))
    for path in [Path(__file__), ROOT/'experiments/run_problem2.py', ROOT.parent/'data/config.txt']:
        shutil.copy2(path,out/'source'/path.name)
    protected = sorted((ROOT.parent/'code').glob('*.py'))+[ROOT.parent/'data/config.txt']+[ROOT.parent/'data'/f'{c}.json' for c in args.cases]
    before = {str(p.relative_to(ROOT.parent)):sha(p) for p in protected}
    m={'problem':2,'algorithm_version':'v010','experiment':args.experiment,'status':'running',
       'parameters':{**vars(args),'freeze':str(args.freeze) if args.freeze else None,'generation_budgets':{'v007':30,'v009':300},'evaluation_budget':180},
       'started_utc':datetime.now(timezone.utc).isoformat(),'protected_hashes_before':before,
       'source_hashes':{str(p.relative_to(out/'source')):sha(p) for p in (out/'source').rglob('*') if p.is_file()},'items':[]}
    lock=threading.Lock()
    def register(status):
        with (ROOT/'experiments/INDEX.md').open('a',encoding='utf-8') as f:
            f.write(f'\n- 问题 2 v010 | {args.experiment} | {status} | [清单](../{out.relative_to(ROOT).as_posix()}/manifest.json)\n')
    save(out/'manifest.json',m);register('running')
    def execute(key):
        c,n=key
        row=solve(c,n,out)
        with lock:
            m['items'].append(row);save(out/'manifest.json',m)
            print(len(m['items']),c,n,row['status'],row.get('selected'),row.get('makespan'),flush=True)
        return row
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(execute,[(c,n) for c in args.cases for n in args.cores]))
        m['status']='completed' if all(r['status']=='success' for r in m['items']) else 'partial'
    except BaseException:
        m['status']='interrupted';raise
    finally:
        m['protected_hashes_after']={str(p.relative_to(ROOT.parent)):sha(p) for p in protected}
        m['protected_unchanged']=before==m['protected_hashes_after']
        m['finished_utc']=datetime.now(timezone.utc).isoformat()
        m['output_hashes']={str(p.relative_to(out)):sha(p) for sub in ['plans','metrics','records','candidates'] for p in (out/sub).rglob('*') if p.is_file()}
        save(out/'manifest.json',m);register(m['status'])
    return int(m['status']!='completed')


if __name__=='__main__':
    raise SystemExit(main())
