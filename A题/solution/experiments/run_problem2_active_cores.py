"""v011 incremental or cold-start experiments. Archived reuse is explicit and verified."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from scene_b_active_cores import candidate_specs, pad_plan, select_candidate
from scene_b_portfolio import plan_digest
from portfolio_scheduler import validate_result
from run_problem2 import run_command, save
from run_problem2_portfolio import sha
from result_paths import result_path


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sources():
    return sorted((ROOT / 'src').glob('*.py')) + [Path(__file__), ROOT/'experiments/run_problem2.py', ROOT/'experiments/run_problem2_portfolio.py', ROOT/'experiments/result_paths.py']


def verify_cache(path, cases):
    m = read(path / 'manifest.json')
    assert m['algorithm_version'] == 'v010' and m['status'] == 'completed' and m['protected_unchanged']
    for rel, digest in m['protected_hashes_before'].items():
        assert sha(ROOT.parent / rel) == digest, rel
    for rel, digest in m['source_hashes'].items():
        archived = path / 'source' / rel
        assert sha(archived) == digest, rel
        current = ROOT / rel if rel.startswith('src') else ROOT/'experiments'/rel
        if current.is_file() and current.suffix == '.py':
            assert sha(current) == digest, rel
    # Verify all cached artifacts, including plan/result and candidate metadata.
    for rel, digest in m['output_hashes'].items():
        assert sha(path / rel) == digest, rel
    items = {(r['case'], r['cores']): r for r in m['items']}
    for c in cases:
        for n in range(2, 6):
            assert items[c, n]['status'] == 'success'
    return items, {'path': str(path), 'manifest_sha256': sha(path/'manifest.json'),
                   'generation_seconds': sum(c['generate']['seconds'] for r in m['items'] for c in r['candidates']),
                   'evaluation_seconds': sum(c['evaluate']['seconds'] for r in m['items'] for c in r['candidates']),
                   'scope': 'entire archived v010 batch; separately report shared prerequisite cost'}


def solve_case(case, cores, out, cache, cached_items, checkpoint):
    generated = {}
    for version, k in candidate_specs(max(cores)):
        name = f'{case}_k{k}_{version}'
        folder = out/'generated'/name
        folder.mkdir(parents=True)
        plan = folder/'plan.json'
        row = {'candidate': version, 'active_budget': k, 'plan': str(plan.relative_to(out)), 'status': 'running'}
        save(folder/'record.json', row)
        if cache and k >= 2:
            original = next(r for r in cached_items[case,k]['candidates'] if r['candidate'] == version)
            shutil.copy2(cache/original['plan'], plan)
            row['generate'] = {'status': 'success', 'seconds': 0, 'reused_from': str(cache/original['plan']),
                               'source_sha256': sha(plan), 'original_seconds': original['generate']['seconds']}
        else:
            algorithm = {'single': 'single', 'v007': 'paired_order', 'v009': 'adaptive'}[version]
            budget = 300 if version == 'v009' else 30
            row['generate'] = run_command([sys.executable,'-B',str(ROOT/'experiments/run_problem2.py'),
                '--worker','generate','--algorithm',algorithm,'--input',str(ROOT.parent/'data'/f'{case}.json'),
                '--config',str(ROOT.parent/'data/config.txt'),'--n',str(k),'--plan',str(plan)],folder/'generate.log',budget)
        row['status'] = row['generate']['status']
        if row['status'] == 'success':
            row['plan_sha256'] = sha(plan)
        save(folder/'record.json', row)
        generated[version,k] = row
    for n in cores:
        rows, evaluated = [], {}
        for version,k in candidate_specs(n):
            folder = out/'candidates'/f'{case}_n{n}'/f'{version}_k{k}'
            folder.mkdir(parents=True)
            plan, result = folder/'plan.json', folder/'result.json'
            g = generated[version,k]
            row = {'candidate': version, 'active_budget': k, 'plan': str(plan.relative_to(out)),
                   'result': str(result.relative_to(out)), 'generation_record': str((out/g['plan']).with_name('record.json').relative_to(out)), 'status':'running'}
            rows.append(row)
            save(folder/'candidate.json',row)
            if g['status'] != 'success':
                row['status'] = 'generate_' + g['status']
            else:
                padded = pad_plan(read(out/g['plan']), n)
                save(plan,padded)
                digest = plan_digest(padded)
                row['canonical_plan_sha256'] = digest
                if digest in evaluated:
                    other = evaluated[digest]
                    shutil.copy2(out/other['result'],result)
                    row['evaluate'] = {'status':'success','seconds':0,'deduplicated_from':other['result']}
                elif cache and k == n:
                    original = next(r for r in cached_items[case,n]['candidates'] if r['candidate'] == version)
                    assert plan_digest(read(cache/original['plan'])) == digest
                    shutil.copy2(cache/original['result'],result)
                    row['evaluate'] = {'status':'success','seconds':0,'reused_from':str(cache/original['result']),
                                       'source_sha256':sha(result),'original_seconds':original['evaluate']['seconds']}
                else:
                    row['evaluate'] = run_command([sys.executable,'-B',str(ROOT/'experiments/run_problem2.py'),
                        '--worker','evaluate','--input',str(ROOT.parent/'data'/f'{case}.json'),
                        '--config',str(ROOT.parent/'data/config.txt'),'--n',str(n),
                        '--plan',str(plan),'--result',str(result)],folder/'evaluate.log',180)
                row['status'] = row['evaluate']['status']
                if row['status'] == 'success':
                    try:
                        row.update(validate_result(read(result),n))
                        row['used_cores'] = sum(bool(x) for x in padded['core_schedules'])
                        evaluated[digest] = row
                    except (ValueError,KeyError,TypeError) as exc:
                        row.update(status='invalid_result',error=str(exc))
            save(folder/'candidate.json',row)
        winner = select_candidate(rows,n)
        record = {'case':case,'cores':n,'candidates':rows,'status':'success' if all(r['status']=='success' for r in rows) else 'degraded' if winner else 'failed'}
        if winner:
            shutil.copy2(out/winner['plan'],out/'plans'/f'{case}_n{n}.json')
            shutil.copy2(out/winner['result'],out/'metrics'/f'{case}_n{n}.json')
            record.update(selected=winner['candidate'],active_budget=winner['active_budget'],used_cores=winner['used_cores'],makespan=winner['makespan'])
        save(out/'records'/f'{case}_n{n}.json',record)
        checkpoint(record)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--experiment',required=True)
    ap.add_argument('--cases',nargs='+',required=True)
    ap.add_argument('--cores',nargs='+',type=int,default=[2,3,4,5])
    ap.add_argument('--generation-cache',type=Path)
    ap.add_argument('--freeze',type=Path)
    args=ap.parse_args()
    assert Path(args.experiment).name == args.experiment
    assert len(set(args.cases)) == len(args.cases) and len(set(args.cores)) == len(args.cores)
    for n in args.cores: candidate_specs(n)
    if args.freeze:
        for rel,d in read(args.freeze)['source_hashes'].items(): assert sha(ROOT/rel)==d,rel
    cache, cache_info = {}, None
    if args.generation_cache:
        print('Verifying archived v010 cache...',flush=True)
        cache,cache_info=verify_cache(args.generation_cache,args.cases)
    out=result_path(Path('problem_2')/'v011'/args.experiment)
    out.mkdir(parents=True,exist_ok=False)
    for sub in ('source','plans','metrics','records','generated','candidates'): (out/sub).mkdir()
    for path in sources():
        dst=out/'source'/path.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dst)
    shutil.copytree(ROOT/'tests',out/'source/tests',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT.parent/'code',out/'source/code',ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT.parent/'data/config.txt',out/'source/config.txt')
    protected=list((ROOT.parent/'code').glob('*.py'))+[ROOT.parent/'data/config.txt']+[ROOT.parent/'data'/f'{c}.json' for c in args.cases]
    before={str(p.relative_to(ROOT.parent)):sha(p) for p in protected}
    m={'problem':2,'algorithm_version':'v011','experiment':args.experiment,'status':'running',
       'started_utc':datetime.now(timezone.utc).isoformat(),'command':sys.argv,
       'parameters':{'cases':args.cases,'cores':args.cores,'workers':2,'generation_budgets':{'single':30,'v007':30,'v009':300},'evaluation_budget':180},
       'cache':cache_info,'protected_hashes_before':before,
       'source_hashes':{str(p.relative_to(out/'source')):sha(p) for p in (out/'source').rglob('*') if p.is_file()},'items':[]}
    lock=threading.Lock()
    def checkpoint(row):
        with lock:
            m['items'].append(row);save(out/'manifest.json',m)
            print(len(m['items']),row['case'],row['cores'],row['status'],row.get('active_budget'),row.get('makespan'),flush=True)
    def register():
        with (ROOT/'experiments/INDEX.md').open('a',encoding='utf-8') as f:
            f.write(f"\n- 问题 2 v011 | {args.experiment} | {m['status']} | {out.relative_to(ROOT)}\n")
    save(out/'manifest.json',m);register()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda c:solve_case(c,args.cores,out,args.generation_cache,cache,checkpoint),args.cases))
        m['status']='completed' if all(r['status']=='success' for r in m['items']) else 'partial'
    except BaseException:
        m['status']='interrupted';raise
    finally:
        m['protected_unchanged']=all(sha(p)==before[str(p.relative_to(ROOT.parent))] for p in protected)
        m['finished_utc']=datetime.now(timezone.utc).isoformat()
        m['output_hashes']={str(p.relative_to(out)):sha(p) for sub in ('plans','metrics','records','generated','candidates') for p in (out/sub).rglob('*') if p.is_file()}
        save(out/'manifest.json',m);register()
    return int(m['status']!='completed')


if __name__=='__main__':
    raise SystemExit(main())
