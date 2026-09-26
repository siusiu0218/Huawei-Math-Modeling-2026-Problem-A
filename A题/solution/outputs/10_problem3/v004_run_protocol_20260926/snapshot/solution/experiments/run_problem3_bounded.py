"""Frozen v003 bounded-interleaving experiment; original evaluator subprocesses."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys
import time
from datetime import datetime, timezone

from run_problem2 import save, run_command
from run_problem3_pair import sha, fingerprint
from result_paths import result_path

S = Path(__file__).resolve().parents[1]
Q2 = S/'outputs/09_problem2/raw/problem_2/v011/exp109_20260926_active_full'
SELECTION = S/'experiments/problem3_v003_selection.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def base_path(case, cores):
    return Q2/(f'generated/{case}_k1_single/plan.json' if cores == 1 else f'plans/{case}_n{cores}.json')


def sources():
    return sorted((S.parent/'code').glob('*.py')) + sorted((S/'src').glob('*.py')) + [
        Path(__file__), S/'experiments/run_problem2.py', S/'experiments/run_problem3_pair.py',
        S/'experiments/result_paths.py', S/'tests/test_scene_b_bounded_order.py', S.parent/'data/config.txt']


def freeze():
    if SELECTION.exists():
        raise ValueError('selection already frozen')
    old = read(S/'experiments/problem3_v001_selection.json')
    excluded = {c['case'] for c in old['cases']} | {'case_001'}
    fresh = []
    for connected in [True, False]:
        pool = sorted([f for f in old['features'] if f['case'] not in excluded and (f['components'] == 1) == connected],
                      key=lambda f: (f['compute_ops'], f['case']))
        for i in range(3):
            block = pool[len(pool)*i//3:len(pool)*(i+1)//3]
            chosen = block[(len(block)-1)//2]
            fresh.append({'case': chosen['case'], 'role': 'validation', 'connected': connected, 'size_tertile': i+1})
    cases = [{'case': c['case'], 'role': 'development'} for c in old['cases'] if c['role'] == 'development'] + fresh
    inputs = [S.parent/'data'/f"{c['case']}.json" for c in cases]
    inputs += [base_path(c['case'], n) for c in cases for n in range(1, 6)]
    save(SELECTION, {'version': 'v003', 'created_utc': datetime.now(timezone.utc).isoformat(), 'cases': cases,
        'excluded_from_validation': sorted(excluded), 'rule': 'remaining single/multiple component strata; size tertiles; lower median by compute_ops then case id; no Q3 timings used',
        'limitations': 'Q3-unused validation only; all graphs previously used by Q1/Q2; deterministic structural sample',
        'candidate_rule': 'baseline plus width1; matched control baseline plus width2; choose lowest Cache makespan, ties baseline',
        'budget': {'generation_timeout': 30, 'evaluation_timeout': 180, 'candidates_per_arm': 2, 'retries': 0},
        'evaluator_policy': 'unchanged original evaluator, including hit-completion reinsertion',
        'source_hashes': fingerprint(sources()), 'input_hashes': fingerprint(inputs)})
    print(json.dumps(cases), flush=True)


def run(role, experiment):
    frozen = read(SELECTION)
    assert frozen['source_hashes'] == fingerprint(sources())
    assert frozen['input_hashes'] == fingerprint([Path(p) for p in frozen['input_hashes']])
    out = result_path(Path('problem_3')/'v003'/experiment)
    out.mkdir(parents=True, exist_ok=False)
    for folder in ['source', 'plans', 'metrics', 'logs']:
        (out/folder).mkdir()
    for source in sources():
        relative = source.relative_to(S.parent)
        target = out/'source'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(SELECTION, out/'selection.json')
    manifest = {'problem': 3, 'version': 'v003', 'experiment': experiment, 'role': role,
                'status': 'running', 'command': [sys.executable, *sys.argv], 'items': [],
                'frozen_selection_sha256': sha(SELECTION), 'upstream_cost': 'Q2 archived plans reused; upstream cost not zero; no cold-start total claimed'}
    start = time.perf_counter()
    rows = []
    for entry in frozen['cases']:
        if entry['role'] != role:
            continue
        case = entry['case']; graph = S.parent/'data'/f'{case}.json'
        for cores in range(1, 6):
            item = {'case': case, 'cores': cores, 'candidates': {}}
            canonical = {}
            for name, width in [('baseline', 0), ('width1', 1), ('width2', 2)]:
                key = f'{case}_n{cores}_{name}'; plan = out/'plans'/f'{key}.json'
                rec = {'plan': str(plan.relative_to(out))}
                if width == 0:
                    shutil.copy2(base_path(case, cores), plan)
                    rec['generation'] = {'status': 'reused', 'seconds': 0, 'source': str(base_path(case, cores))}
                else:
                    command = [sys.executable, '-B', str(Path(__file__)), '--worker', '--graph', str(graph),
                               '--base', str(base_path(case, cores)), '--plan', str(plan), '--width', str(width)]
                    rec['generation'] = run_command(command, out/'logs'/f'{key}_generation.txt', 30)
                rec['evaluations'] = {}
                if plan.exists() and rec['generation']['status'] in ['success', 'reused']:
                    rec['plan_sha256'] = sha(plan)
                    signature = json.dumps(read(plan), sort_keys=True)
                    if signature in canonical:
                        rec['duplicate_of'] = canonical[signature]
                        rec['evaluations'] = item['candidates'][canonical[signature]]['evaluations']
                    else:
                        canonical[signature] = name
                        for mode in ['no_l2', 'cache']:
                            result = out/'metrics'/f'{key}_{mode}.json'
                            command = [sys.executable, '-B', str(S/'experiments/run_problem3_pair.py'), '--worker', mode,
                                       '--graph', str(graph), '--plan', str(plan), '--result', str(result)]
                            ev = run_command(command, out/'logs'/f'{key}_{mode}.txt', 180)
                            ev['result'] = str(result.relative_to(out))
                            if ev['status'] == 'success':
                                ev['sha256'] = sha(result)
                            rec['evaluations'][mode] = ev
                item['candidates'][name] = rec
                if len(rec['evaluations']) == 2 and all(e['status'] == 'success' for e in rec['evaluations'].values()):
                    a, b = [read(out/rec['evaluations'][m]['result']) for m in ['no_l2', 'cache']]
                    rows.append({'problem': 3, 'version': 'v003', 'experiment': experiment, 'role': role,
                        'case': case, 'cores': cores, 'candidate': name, 'no_l2': a['makespan'], 'cache': b['makespan'],
                        'cache_speedup': a['makespan']/b['makespan'], 'hit_rate': b['cache_stats']['hit_rate'],
                        'spill_bytes': b['data_movement_bytes']['spill_added_copy_bytes'],
                        'added_copy_bytes': b['data_movement_bytes']['added_copy_bytes']})
            manifest['items'].append(item)
            save(out/'manifest.json', manifest)
            print(f'{role} {case} n{cores} complete', flush=True)
    manifest['wall_seconds'] = time.perf_counter()-start
    assert frozen['source_hashes'] == fingerprint(sources())
    assert frozen['input_hashes'] == fingerprint([Path(p) for p in frozen['input_hashes']])
    manifest['hashes_after_verified'] = True
    manifest['status'] = 'complete' if len(rows) == len(manifest['items'])*3 else 'incomplete'
    manifest['generation_seconds'] = sum(r['generation'].get('seconds', 0) for it in manifest['items'] for r in it['candidates'].values())
    manifest['evaluation_seconds'] = sum(e.get('seconds', 0) for it in manifest['items'] for r in it['candidates'].values() if 'duplicate_of' not in r for e in r['evaluations'].values())
    save(out/'manifest.json', manifest)
    with (out/'metrics/comparison.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({'out': str(out), 'status': manifest['status'], 'seconds': manifest['wall_seconds']}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true'); parser.add_argument('--worker', action='store_true')
    parser.add_argument('--role', choices=['development', 'validation']); parser.add_argument('--experiment')
    for name in ['graph', 'base', 'plan']:
        parser.add_argument('--'+name)
    parser.add_argument('--width', type=int)
    args = parser.parse_args()
    if args.worker:
        sys.path[:0] = [str(S/'src'), str(S.parent/'code')]
        from scene_b_bounded_order import reorder
        save(Path(args.plan), reorder(read(args.graph), read(args.base), args.width))
    elif args.freeze:
        freeze()
    else:
        if not args.role or not args.experiment or Path(args.experiment).name != args.experiment:
            parser.error('role and plain experiment name required')
        run(args.role, args.experiment)


if __name__ == '__main__':
    main()
