"""Q1 v012 frozen portfolio. Explicit prepare/run, resumable per-slot records."""
import argparse
from contextlib import contextmanager
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import zipfile

from run_problem1_structural_ablation import (
    A_ROOT, SOLUTION, ROOT as DEVELOPMENT, read, save, sha, signature,
    verify_frozen, run_command, validate_result, make_candidate,
)
from result_paths import experiment_path


@contextmanager
def lock(root):
    import msvcrt
    with (root / '.run.lock').open('a+b') as handle:
        handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def checked(path, digest):
    if sha(Path(path)) != digest:
        raise ValueError('artifact changed: ' + str(path))


def prepare(root, cases, cores):
    development = read(DEVELOPMENT / 'manifest.json')
    verify_frozen(development)
    # Input numbering is obtained from the formal table, not assumed.
    table = SOLUTION / 'outputs/08_full/multicore_comparison.csv'
    all_rows = list(csv.DictReader(table.open(encoding='utf-8-sig')))
    cases = sorted(cases or {r['case'] for r in all_rows})
    if len(set(cases)) != len(cases) or not set(cores) <= {2, 3, 4, 5}:
        raise ValueError('invalid scope')
    rows = [r for r in all_rows if r['case'] in cases and int(r['cores']) in cores]
    if len(rows) != len(cases) * len(cores):
        raise ValueError('missing formal references')
    root.mkdir(parents=True, exist_ok=False)
    for name in ('references', 'source', 'runs', 'selected'):
        (root / name).mkdir()
    refs = []
    normalized = []
    archive = SOLUTION / 'outputs/08_full/原始运行记录.zip'
    with zipfile.ZipFile(archive) as z:
        verified = set()
        for r in sorted(rows, key=lambda r: (r['case'], int(r['cores']))):
            prefix = f"problem_1/v009/{r['experiment']}/"
            if prefix not in verified:
                old = json.loads(z.read(prefix + 'manifest.json'))
                for rel, digest in old['protected_hashes_before'].items():
                    path = A_ROOT / rel
                    # Only executable evaluator/config/input dependencies govern score reuse.
                    if Path(rel).parts[0] not in ('code', 'data'):
                        continue
                    raw = path.read_bytes()
                    if hashlib.sha256(raw).hexdigest() != digest:
                        crlf = raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
                        if path.suffix != '.py' or hashlib.sha256(crlf).hexdigest() != digest:
                            raise ValueError('formal input changed: ' + rel)
                        normalized.append(rel)
                verified.add(prefix)
            key = f"{r['case']}_n{r['cores']}"
            for kind, member, digest in (
                ('plan', 'plans/' + key + '.json', r['selected_plan_sha256']),
                ('result', 'metrics/' + key + '_result.json', r['selected_result_sha256']),
            ):
                target = root / 'references' / f'{key}_{kind}.json'
                target.write_bytes(z.read(prefix + member)); checked(target, digest)
            result = read(root / 'references' / f'{key}_result.json')
            if validate_result(result, int(r['cores']))['makespan'] != int(r['makespan']):
                raise ValueError('baseline score mismatch')
            refs.append(dict(case=r['case'], cores=int(r['cores']), key=key,
                baseline_makespan=int(r['makespan']), single_makespan=int(r['single_makespan']),
                baseline_experiment=r['experiment']))
    sources = list((A_ROOT / 'code').glob('*.py')) + [A_ROOT / 'data/config.txt']
    sources += [A_ROOT / f'data/{c}.json' for c in cases]
    sources += list((SOLUTION / 'src').glob('*.py')) + list((SOLUTION / 'src').glob('*.LICENSE'))
    sources += [Path(__file__), table] + [SOLUTION / 'experiments' / n for n in
        ('run_problem1_structural_ablation.py', 'probe_problem1_critical_local.py', 'process_runner.py', 'result_paths.py')]
    frozen = {}
    for p in sources:
        rel = p.relative_to(A_ROOT); frozen[str(rel)] = sha(p)
        target = root / 'source' / rel; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    for p in (root / 'references').glob('*.json'):
        frozen[str(p.relative_to(A_ROOT))] = sha(p)
    reuse = {}
    for previous in (DEVELOPMENT, experiment_path('v012', 'exp134_20260926_structural_transfer')):
        old = read(previous / 'manifest.json'); verify_frozen(old)
        for item in read(previous / 'candidates.json'):
            if item['status'] != 'success' or item['arm'] not in ('B', 'C'):
                continue
            if item['case'] not in cases or 5 not in cores:
                continue
            plan = previous / 'runs' / item['case'] / item['candidate'] / 'plan.json'
            checked(plan, item['plan_sha256']); checked(item['result_path'], item['result_sha256'])
            if signature(read(plan)) != item['signature']:
                raise ValueError('historical signature mismatch')
            reuse[f"{item['case']}_n5:{item['signature']}"] = {
                'result_path': item['result_path'], 'result_sha256': item['result_sha256'],
                'source': str(previous), 'source_plan': str(plan), 'source_plan_sha256': sha(plan),
                'source_manifest': str(previous / 'manifest.json'), 'source_manifest_sha256': sha(previous / 'manifest.json')}
    save(root / 'reuse_index.json', reuse)
    frozen[str((root / 'reuse_index.json').relative_to(A_ROOT))] = sha(root / 'reuse_index.json')
    save(root / 'manifest.json', dict(problem=1, algorithm_version='v012', experiment=root.name,
        status='prepared', cases=cases, cores=cores, references=refs, candidate_slots=len(refs)*8,
        frozen_files=frozen, settings=development['settings'], structure_policy=development['structure_policy'],
        generation_timeout_seconds=30, evaluation_timeout_seconds=180, retries=0,
        line_endings_verified_against_old_crlf=sorted(set(normalized)),
        selection='formal v009 + B0..B3 + C0..C3; ties retain baseline; prior local v010/v011 not in uniform portfolio',
        historical_search_cost_excluded=True, sessions=[]))
    print({'prepared': str(root), 'slots': len(refs)*8, 'historical_unique_plans': len(reuse)}, flush=True)


def generate(root, key, arm, index):
    ref = next(r for r in read(root / 'manifest.json')['references'] if r['key'] == key)
    folder = root / 'runs' / key / f'{arm}{index}'
    plan, meta = make_candidate(read(A_ROOT / f"data/{ref['case']}.json"),
        read(root / 'references' / f'{key}_plan.json'),
        read(root / 'references' / f'{key}_result.json'), arm, index)
    save(folder / 'plan.json', plan); save(folder / 'generation.json', meta)


def validate_row(folder, row, cores):
    if row['status'] == 'success':
        checked(folder / 'plan.json', row['plan_sha256'])
        if signature(read(folder / 'plan.json')) != row['signature']:
            raise ValueError('signature mismatch')
        checked(row['result_path'], row['result_sha256'])
        if validate_result(read(Path(row['result_path'])), cores)['makespan'] != row['makespan']:
            raise ValueError('score mismatch')


def run(root, stop_after=0):
    with lock(root):
        manifest = read(root / 'manifest.json'); verify_frozen(manifest)
        reuse = read(root / 'reuse_index.json')
        for item in reuse.values():
            checked(item['source_manifest'], item['source_manifest_sha256'])
            checked(item['source_plan'], item['source_plan_sha256'])
            checked(item['result_path'], item['result_sha256'])
        manifest['status'] = 'running'; save(root / 'manifest.json', manifest)
        started = time.perf_counter(); rows = []; processed = 0
        try:
            for ref in manifest['references']:
                key = ref['key']; cores = ref['cores']
                bp = root / 'references' / f'{key}_plan.json'
                br = root / 'references' / f'{key}_result.json'
                cache = {signature(read(bp)): dict(result_path=str(br), result_sha256=sha(br), source='baseline')}
                cache.update({k.split(':', 1)[1]: v for k, v in reuse.items() if k.startswith(key + ':')})
                for arm in ('B', 'C'):
                    for index in range(4):
                        folder = root / 'runs' / key / f'{arm}{index}'; folder.mkdir(parents=True, exist_ok=True)
                        status = folder / 'status.json'
                        row = read(status) if status.exists() else None
                        if row and row['status'] != 'running':
                            validate_row(folder, row, cores)
                        else:
                            attempt = len(list(folder.glob('interrupted_*.json')))
                            if row:
                                row['status'] = 'interrupted'
                                save(folder / f'interrupted_{attempt:03d}.json', row)
                            row = dict(problem=1, algorithm_version='v012', experiment=root.name,
                                case=ref['case'], cores=cores, candidate=f'{arm}{index}', arm=arm,
                                setting_index=index, status='running', generation_seconds=0., evaluation_seconds=0., evaluation_reused=False)
                            save(status, row)
                            cmd = [sys.executable, '-B', str(Path(__file__)), '--experiment', root.name,
                                '--generate', key, arm, str(index)]
                            outcome = run_command(cmd, folder / f'generation_{attempt}.log', 30)
                            row['generation_seconds'] = outcome['seconds']; save(folder / f'generation_process_{attempt}.json', outcome)
                            if outcome['status'] != 'success':
                                row['status'] = 'generation_' + outcome['status']
                            else:
                                plan = read(folder / 'plan.json'); sig = signature(plan)
                                row.update(signature=sig, plan_sha256=sha(folder / 'plan.json'))
                                if sig in cache:
                                    item = cache[sig]; checked(item['result_path'], item['result_sha256'])
                                    row.update(status='success', evaluation_reused=True,
                                        result_path=item['result_path'], result_sha256=item['result_sha256'], reuse_source=item['source'])
                                else:
                                    cmd = [sys.executable, '-B', str(A_ROOT / 'code/multicore_cut_evaluate_problem_1.py'),
                                        str(A_ROOT / f"data/{ref['case']}.json"), str(folder / 'plan.json'),
                                        '--config', str(A_ROOT / 'data/config.txt'), '-o', str(folder / 'result.json'),
                                        '--trace-output', str(folder / 'trace.json'), '--log-output', str(folder / 'evaluation.log')]
                                    outcome = run_command(cmd, folder / f'evaluation_{attempt}.log', 180)
                                    save(folder / f'evaluation_process_{attempt}.json', outcome)
                                    row.update(status=outcome['status'], evaluation_seconds=outcome['seconds'])
                                    if outcome['status'] == 'success':
                                        row.update(result_path=str(folder / 'result.json'), result_sha256=sha(folder / 'result.json'))
                                if row['status'] == 'success':
                                    row.update(validate_result(read(Path(row['result_path'])), cores))
                            save(status, row); processed += 1
                            print(key, row['candidate'], row['status'], row.get('makespan'), flush=True)
                        rows.append(row)
                        if row['status'] == 'success':
                            cache[row['signature']] = dict(result_path=row['result_path'], result_sha256=row['result_sha256'], source=row['candidate'])
                        if stop_after and processed >= stop_after:
                            manifest['status'] = 'checkpoint_stopped'; return
            if len(rows) != manifest['candidate_slots']:
                raise ValueError('incomplete coverage')
            save(root / 'candidates.json', rows)
            selection = []
            for ref in manifest['references']:
                key = ref['key']; best = dict(ref, candidate='baseline', makespan=ref['baseline_makespan'],
                    plan_path=str(root / 'references' / f'{key}_plan.json'))
                for row in rows:
                    if row['case'] == ref['case'] and row['cores'] == ref['cores'] and row['status'] == 'success' and row['makespan'] < best['makespan']:
                        best.update(candidate=row['candidate'], makespan=row['makespan'],
                            plan_path=str(root / 'runs' / key / row['candidate'] / 'plan.json'))
                target = root / 'selected' / f'{key}.json'; shutil.copy2(best['plan_path'], target)
                best.update(selected_plan_sha256=sha(target), speedup=ref['single_makespan']/best['makespan'])
                selection.append(best)
            save(root / 'selection.json', selection)
            save(root / 'summary.json', {str(n): dict(configurations=sum(r['cores']==n for r in selection),
                mean_speedup=sum(r['speedup'] for r in selection if r['cores']==n)/sum(r['cores']==n for r in selection)) for n in manifest['cores']})
            manifest['status'] = 'completed' if all(r['status']=='success' for r in rows) else 'completed_with_failures'
        except BaseException as exc:
            manifest['status'] = 'interrupted_or_failed'; manifest['last_error'] = repr(exc); raise
        finally:
            manifest['sessions'].append(dict(seconds=time.perf_counter()-started, new_slots=processed))
            manifest['frozen_unchanged'] = all(sha(A_ROOT/p)==h for p,h in manifest['frozen_files'].items())
            save(root / 'manifest.json', manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--experiment', required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', action='store_true'); group.add_argument('--run', action='store_true')
    group.add_argument('--generate', nargs=3)
    parser.add_argument('--cases', nargs='+'); parser.add_argument('--cores', nargs='+', type=int, default=[2,3,4,5])
    parser.add_argument('--stop-after', type=int, default=0)
    args = parser.parse_args()
    if not args.experiment.startswith('exp') or any(c in args.experiment for c in '/\\:'):
        parser.error('invalid experiment name')
    root = experiment_path('v012', args.experiment)
    if args.prepare: prepare(root, args.cases, sorted(set(args.cores)))
    elif args.run: run(root, args.stop_after)
    else: generate(root, args.generate[0], args.generate[1], int(args.generate[2]))
