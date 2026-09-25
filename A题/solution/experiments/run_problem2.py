"""Bounded scene-B experiments with per-item checkpoints and full results."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.dont_write_bytecode = True
SOLUTION = Path(__file__).resolve().parents[1]
A_ROOT = SOLUTION.parent
sys.path[:0] = [str(SOLUTION / 'src'), str(A_ROOT / 'code')]
from result_paths import result_path


def save(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Antivirus/indexing on Windows can transiently hold the destination open.
    # Retry only the atomic metadata write, never an algorithm/evaluator run.
    for attempt in range(6):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def hashes(paths):
    return {str(p.relative_to(A_ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}


def run_command(command, log, timeout):
    start = time.perf_counter()
    with log.open('w', encoding='utf-8') as stream:
        try:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=timeout, check=False)
            status = 'success' if result.returncode == 0 else 'failed'
            return {'status': status, 'returncode': result.returncode,
                    'seconds': time.perf_counter() - start}
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'returncode': None,
                    'seconds': time.perf_counter() - start}


def worker(args):
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config
    data = json.loads(Path(args.input).read_text(encoding='utf-8'))
    cfg = read_evaluation_config(args.config)
    delay = read_scene_b_config(args.config)['cross_core_copy_delay_cycles']
    if args.worker == 'generate':
        if args.algorithm == 'adaptive':
            from scene_b_adaptive import make_plan_with_stats
            plan, stats = make_plan_with_stats(data, args.n, bandwidth=cfg['bandwidth'],
                                              capacity=cfg['capacity'], cross_core_wait=delay)
            save(Path(args.plan).with_suffix('.selection.json'), stats)
        elif args.algorithm == 'single':
            from singlecore_evaluate import build_singlecore_plan
            plan = build_singlecore_plan(data)
        else:
            if args.algorithm.startswith('baseline'):
                from baseline import make_plan
            elif args.algorithm == 'component_order':
                from scene_b_component_order import make_plan
            elif args.algorithm == 'operation_order':
                from scene_b_operation_order import make_plan
            elif args.algorithm == 'paired_order':
                from scene_b_paired_order import make_plan
            elif args.algorithm == 'split_components':
                from scene_b_split_components import make_plan
            else:
                from region_scheduler import make_plan
            waits = {} if args.algorithm.endswith('_a') else {
                'same_core_wait': 0, 'cross_core_wait': delay}
            plan = make_plan(data, args.n, blocks_per_core=4, **waits)
        save(Path(args.plan), plan)
    else:
        plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
        result = evaluate_scene_b(data, plan, cfg['bandwidth'], cfg['capacity'], delay)
        save(Path(args.result), result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', choices=['generate', 'evaluate'])
    parser.add_argument('--input')
    parser.add_argument('--config', default=str(A_ROOT / 'data/config.txt'))
    parser.add_argument('--plan')
    parser.add_argument('--result')
    parser.add_argument('--n', type=int)
    parser.add_argument('--algorithm', choices=['baseline_a', 'baseline_b', 'regions_a', 'regions_b', 'component_order', 'operation_order', 'paired_order', 'split_components', 'adaptive', 'single'], default='baseline_b')
    parser.add_argument('--experiment')
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--cores', nargs='+', type=int, default=[2, 3, 4, 5])
    parser.add_argument('--generation-timeout', type=float, default=30)
    parser.add_argument('--evaluation-timeout', type=float, default=180)
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    if not args.experiment or Path(args.experiment).name != args.experiment or not args.cases:
        parser.error('provide --experiment (directory name) and --cases')
    if any(n not in range(1, 6) for n in args.cores) or min(args.generation_timeout, args.evaluation_timeout) <= 0:
        parser.error('cores must be 1..5 and timeouts positive')
    if args.algorithm == 'single' and args.cores != [1]:
        parser.error('single requires --cores 1')
    inputs = [A_ROOT / 'data' / f'{case}.json' for case in args.cases]
    if any(p.parent != A_ROOT / 'data' or not p.is_file() for p in inputs):
        parser.error('invalid case')
    # Versions identify the exact method + wait proxy, independently of Q1.
    version = {'baseline_a': 'v001', 'regions_b': 'v002', 'baseline_b': 'v003',
               'regions_a': 'v004', 'component_order': 'v005', 'operation_order': 'v006', 'paired_order': 'v007', 'split_components': 'v008', 'adaptive': 'v009', 'single': 'single_v001'}[args.algorithm]
    out = result_path(Path('problem_2') / version / args.experiment)
    out.mkdir(parents=True, exist_ok=False)
    for directory in ('plans', 'metrics', 'logs', 'source'):
        (out / directory).mkdir()
    for directory in ('src', 'tests'):
        shutil.copytree(SOLUTION / directory, out / 'source' / directory,
                        ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(A_ROOT / 'code', out / 'source/code', ignore=shutil.ignore_patterns('__pycache__'))
    for p in (Path(__file__), Path(__file__).with_name('result_paths.py'), Path(args.config)):
        shutil.copy2(p, out / 'source' / p.name)
    protected = inputs + sorted((A_ROOT / 'code').glob('*.py')) + [Path(args.config)]
    before = hashes(protected)
    manifest = {'problem': 2, 'algorithm_version': version, 'experiment': args.experiment,
                'parameters': vars(args), 'status': 'running', 'random_seed': None,
                'started_utc': datetime.now(timezone.utc).isoformat(),
                'invocation': [sys.executable, '-B', *sys.argv],
                'protected_hashes_before': before,
                'source_hashes': {str(p.relative_to(out / 'source')): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (out / 'source').rglob('*') if p.is_file()}, 'items': []}
    index = SOLUTION / 'experiments/INDEX.md'
    def register(status):
        with index.open('a', encoding='utf-8') as stream:
            stream.write(f'\n- 问题 2 `{version}` | `{args.experiment}` | {status} | [记录](../{out.relative_to(SOLUTION).as_posix()}/manifest.json)\n')
    save(out / 'manifest.json', manifest)
    register('running')
    try:
        for source in inputs:
            for n in args.cores:
                key = f'{source.stem}_n{n}'
                row = {'problem': 2, 'algorithm_version': version, 'experiment': args.experiment,
                       'case': source.stem, 'cores': n, 'status': 'running'}
                manifest['items'].append(row)
                save(out / 'manifest.json', manifest)
                common = [sys.executable, '-B', str(Path(__file__)), '--input', str(source),
                          '--config', args.config, '--plan', str(out / 'plans' / f'{key}.json'),
                          '--result', str(out / 'metrics' / f'{key}.json'),
                          '--algorithm', args.algorithm, '--n', str(n)]
                for stage, budget in [('generate', args.generation_timeout), ('evaluate', args.evaluation_timeout)]:
                    row[stage] = run_command(common + ['--worker', stage], out / 'logs' / f'{key}_{stage}.log', budget)
                    save(out / 'manifest.json', manifest)
                    if row[stage]['status'] != 'success':
                        row['status'] = stage + '_' + row[stage]['status']
                        break
                else:
                    result = json.loads((out / 'metrics' / f'{key}.json').read_text(encoding='utf-8'))
                    row.update(status='success', makespan=result['makespan'],
                               data_movement_bytes=result['data_movement_bytes'])
                save(out / 'manifest.json', manifest)
                print(key, row['status'], row.get('makespan', ''), flush=True)
        manifest['status'] = 'completed' if all(r['status'] == 'success' for r in manifest['items']) else 'partial'
    except BaseException:
        manifest['status'] = 'interrupted'
        raise
    finally:
        manifest['protected_hashes_after'] = hashes(protected)
        manifest['protected_unchanged'] = before == manifest['protected_hashes_after']
        if not manifest['protected_unchanged']:
            manifest['status'] = 'invalid_materials_changed'
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        manifest['output_hashes'] = {
            str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('plans', 'metrics', 'logs')
            for p in (out / folder).glob('*') if p.is_file()}
        save(out / 'manifest.json', manifest)
        register(manifest['status'])
    return 0 if manifest['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
