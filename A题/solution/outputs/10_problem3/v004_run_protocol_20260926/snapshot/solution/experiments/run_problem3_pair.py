"""Evaluate one archived plan with and without Cache, with resumable checkpoints."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
SOLUTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION.parent / 'code'))
from run_problem2 import run_command, save
from result_paths import result_path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(paths):
    return {str(p.resolve()): sha(p) for p in paths}


def worker(args):
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config
    from multicore_cut_evaluate_problem_3 import evaluate_problem_3, read_cache_config
    graph = json.loads(Path(args.graph).read_text(encoding='utf-8'))
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    cfg = read_evaluation_config(args.config)
    common = (graph, plan, cfg['bandwidth'], cfg['capacity'],
              read_scene_b_config(args.config)['cross_core_copy_delay_cycles'])
    if args.worker == 'no_l2':
        result = evaluate_scene_b(*common)
    else:
        cache = read_cache_config(args.config)
        result = evaluate_problem_3(*common, cache['cache_capacity_bytes'],
                                    cache['cache_bandwidth_bytes_per_cycle'])
    save(Path(args.result), result)


def valid_record(record, out):
    if record.get('status') != 'success':
        return False
    path = out / record['result']
    if not path.is_file() or sha(path) != record.get('result_sha256'):
        return False
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return isinstance(data.get('makespan'), (int, float)) and data['makespan'] >= 0
    except (ValueError, OSError):
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--worker', choices=['no_l2', 'cache'])
    p.add_argument('--graph', required=True)
    p.add_argument('--plan', required=True)
    p.add_argument('--config', default=str(SOLUTION.parent / 'data/config.txt'))
    p.add_argument('--result')
    p.add_argument('--experiment')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--timeout', type=float, default=180)
    args = p.parse_args()
    if args.worker:
        worker(args)
        return
    if not args.experiment or Path(args.experiment).name != args.experiment or args.timeout <= 0:
        p.error('provide a directory-name experiment and positive timeout')
    paths = [Path(args.graph).resolve(), Path(args.plan).resolve(), Path(args.config).resolve()]
    scripts = [Path(__file__).resolve(), Path(__file__).with_name('run_problem2.py'),
               Path(__file__).with_name('result_paths.py')]
    sources = sorted((SOLUTION.parent/'code').glob('*.py')) + scripts
    hashes = fingerprint(paths + sources)
    out = result_path(Path('problem_3') / 'v001' / args.experiment)
    # All results remain in the main workspace, including calls from worktrees.
    out = Path('D:/workspace/HuaWei/A题/solution/outputs/10_problem3/raw/problem_3/v001') / out.name
    manifest_path = out/'manifest.json'
    if args.resume:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['hashes_before'] != hashes or manifest['timeout'] != args.timeout:
            raise ValueError('resume input/source hashes or timeout changed; use a new experiment')
        for rel, expected in manifest['archive_hashes'].items():
            if sha(out/rel) != expected:
                raise ValueError(f'archive changed: {rel}')
    else:
        out.mkdir(parents=True, exist_ok=False)
        for folder in ('plans', 'inputs', 'metrics', 'logs', 'source'):
            (out/folder).mkdir()
        shutil.copy2(paths[0], out/'inputs/graph.json')
        shutil.copy2(paths[1], out/'plans/plan.json')
        shutil.copy2(paths[2], out/'inputs/config.txt')
        for source in sources:
            shutil.copy2(source, out/'source'/source.name)
        archives = list((out/'inputs').glob('*')) + list((out/'plans').glob('*')) + list((out/'source').glob('*'))
        manifest = {'problem': 3, 'version': 'v001', 'purpose': 'paired infrastructure smoke test',
                    'plan_source': str(paths[1]), 'plan_sha256': sha(paths[1]),
                    'plan_generation_seconds': None, 'plan_generation_note': 'archived plan reused; upstream cost not zero',
                    'hashes_before': hashes, 'timeout': args.timeout, 'attempts': [],
                    'archive_hashes': {str(x.relative_to(out)): sha(x) for x in archives},
                    'status': 'running', 'command': [sys.executable, *sys.argv]}
        save(manifest_path, manifest)
    for mode in ('no_l2', 'cache'):
        previous = [x for x in manifest['attempts'] if x['mode'] == mode]
        if previous and valid_record(previous[-1], out):
            continue
        attempt = len(previous)+1
        result = out/'metrics'/f'{mode}_attempt{attempt}.json'
        command = [sys.executable, str(Path(__file__).resolve()), '--worker', mode,
                   '--graph', str(out/'inputs/graph.json'), '--plan', str(out/'plans/plan.json'),
                   '--config', str(out/'inputs/config.txt'), '--result', str(result)]
        log = out/'logs'/f'{mode}_attempt{attempt}.txt'
        record = run_command(command, log, args.timeout)
        record.update(mode=mode, command=command, result=str(result.relative_to(out)),
                      plan_sha256=sha(out/'plans/plan.json'))
        if record['status'] == 'success' and result.exists():
            record['result_sha256'] = sha(result)
            if not valid_record(record, out):
                record['status'] = 'invalid_result'
        elif record['status'] == 'success':
            record['status'] = 'missing_result'
        manifest['attempts'].append(record)
        save(manifest_path, manifest)
    current = {mode: [x for x in manifest['attempts'] if x['mode'] == mode][-1]
               for mode in ('no_l2', 'cache')}
    manifest['hashes_after'] = fingerprint(paths + sources)
    unchanged = manifest['hashes_after'] == hashes and all(
        sha(out/rel) == expected for rel, expected in manifest['archive_hashes'].items())
    success = unchanged and all(valid_record(x, out) for x in current.values())
    manifest['status'] = 'completed' if success else 'incomplete'
    if success:
        values = {mode: json.loads((out/record['result']).read_text(encoding='utf-8'))
                  for mode, record in current.items()}
        a, b = values['no_l2'], values['cache']
        save(out/'metrics/pair.json', {
            'plan_sha256': manifest['plan_sha256'], 'num_cores': b['num_cores'],
            'no_l2_makespan': a['makespan'], 'cache_makespan': b['makespan'],
            'cache_speedup': a['makespan']/b['makespan'] if b['makespan'] else None,
            'no_l2_hit_rate': None, 'cache_stats': b['cache_stats'],
            'official_no_l2_movement': a['data_movement_bytes'],
            'official_cache_movement': b['data_movement_bytes'],
            'result_records': current})
    save(manifest_path, manifest)
    print(json.dumps({'status': manifest['status'], 'output': str(out)}, ensure_ascii=False))
    if not success:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
