"""v009: fixed, sequential v001/v008 portfolio using the original evaluator."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time

from graph_analysis import A_ROOT

VERSION = 'v009'
CANDIDATES = ('v001', 'v008')


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_phase(command, timeout, log_path):
    """Each child is killed and reaped on timeout; children spawn no descendants."""
    started = time.perf_counter()
    try:
        with log_path.open('w', encoding='utf-8') as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                       timeout=timeout, check=False)
        status = 'ok' if completed.returncode == 0 else 'failed'
        error = '' if status == 'ok' else f'process exit {completed.returncode}'
    except subprocess.TimeoutExpired:
        status, error = 'timeout', f'phase exceeded {timeout} seconds'
    except OSError as exc:
        status, error = 'failed', f'{type(exc).__name__}: {exc}'
    return {'status': status, 'seconds': time.perf_counter() - started, 'error': error}


def validate_result(result, cores):
    makespan = result['makespan']
    if isinstance(makespan, bool) or not isinstance(makespan, (int, float)) or not math.isfinite(makespan) or makespan <= 0:
        raise ValueError('makespan must be finite and positive')
    if result['num_cores'] != cores:
        raise ValueError('wrong core count')
    for peak in result['memory_peak_by_core'].values():
        if any(value > result['capacity_bytes'][position] for position, value in peak.items()):
            raise ValueError('memory peak exceeds capacity')
    latest = max((op['end'] for core in result['per_core_timeline'] for op in core['ops']), default=0)
    if not math.isfinite(latest) or abs(latest - makespan) > 1e-6:
        raise ValueError('timeline end differs from makespan')
    movement = result['data_movement_bytes']
    return {'makespan': makespan, **{key: movement[key] for key in (
        'added_copy_bytes', 'partition_added_copy_bytes', 'spill_added_copy_bytes', 'scheduled_copy_bytes')}}


def choose_candidate(rows):
    """Minimum successful makespan; exact ties prefer v001, independent of row order."""
    if len(rows) != 2 or {r['candidate'] for r in rows} != set(CANDIDATES):
        raise ValueError('exactly one row per fixed candidate is required')
    successful = [r for r in rows if r['status'] == 'ok']
    for row in successful:
        if not math.isfinite(row['makespan']) or row['makespan'] <= 0:
            raise ValueError('invalid candidate score')
    return min(successful, key=lambda r: (r['makespan'], CANDIDATES.index(r['candidate']))) if successful else None


def evaluate_candidate(root, graph_path, cores, candidate, policy, planner_script):
    root.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    row = {'candidate': candidate, 'status': 'pending', 'failure_phase': '', 'error': '',
           'plan_seconds': 0., 'evaluation_seconds': 0., 'wall_seconds': 0.,
           'makespan': '', 'added_copy_bytes': '', 'partition_added_copy_bytes': '',
           'spill_added_copy_bytes': '', 'scheduled_copy_bytes': '', 'subgraphs': '',
           'used_cores': '', 'plan_sha256': '', 'result_sha256': ''}
    phase = 'plan'
    try:
        plan_command = [sys.executable, '-B', str(planner_script), '--candidate', candidate,
                        '--graph', str(graph_path), '--cores', str(cores), '--output', str(root),
                        '--blocks-per-core', str(policy['blocks_per_core'])]
        write_json(root / 'plan_command.json', plan_command)
        outcome = run_phase(plan_command, policy['plan_timeout_seconds'], root / 'plan_process.log')
        row['plan_seconds'] = outcome['seconds']
        if outcome['status'] != 'ok':
            row.update(status=outcome['status'], error=outcome['error'], failure_phase=phase)
        else:
            plan = read_json(root / 'plan.json')
            row.update(plan_sha256=digest(root / 'plan.json'),
                       subgraphs=len(set(plan['node_to_subgraph'].values())),
                       used_cores=sum(bool(order) for order in plan['core_schedules']))
            phase = 'evaluation'
            command = [sys.executable, '-B', str(A_ROOT / 'code/multicore_cut_evaluate_problem_1.py'),
                       str(graph_path), str(root / 'plan.json'), '--config', str(A_ROOT / 'data/config.txt'),
                       '-o', str(root / 'result.json'), '--trace-output', str(root / 'trace.json'),
                       '--log-output', str(root / 'evaluation.log')]
            write_json(root / 'evaluation_command.json', command)
            outcome = run_phase(command, policy['evaluation_timeout_seconds'], root / 'evaluation_process.log')
            row['evaluation_seconds'] = outcome['seconds']
            if outcome['status'] != 'ok':
                row.update(status=outcome['status'], error=outcome['error'], failure_phase=phase)
            else:
                phase = 'result_validation'
                row.update(validate_result(read_json(root / 'result.json'), cores))
                row.update(status='ok', result_sha256=digest(root / 'result.json'))
    except Exception as exc:
        row.update(status='failed', error=f'{type(exc).__name__}: {exc}', failure_phase=phase)
    finally:
        if row['status'] == 'pending':
            row.update(status='interrupted', failure_phase=phase, error='process interrupted')
        row['wall_seconds'] = time.perf_counter() - started
        write_json(root / 'status.json', row)
    return row


def solve_configuration(exp, case, split, cores, policy, planner_script):
    started = time.perf_counter()
    key = f'{case}_n{cores}'
    rows = []
    for candidate in CANDIDATES:
        row = evaluate_candidate(exp / 'candidates' / key / candidate,
                                 A_ROOT / 'data' / f'{case}.json', cores, candidate, policy, planner_script)
        rows.append(row)
        print(f"  {key} {candidate}: {row['status']} T={row['makespan']}", flush=True)
    winner = choose_candidate(rows)
    selected = {'problem': 1, 'algorithm_version': VERSION, 'experiment': exp.name,
                'case': case, 'split': split, 'cores': cores,
                'status': 'ok' if all(r['status'] == 'ok' for r in rows) else 'degraded' if winner else 'failed',
                'candidate_count': 2, 'successful_candidates': sum(r['status'] == 'ok' for r in rows),
                'selected_candidate': winner['candidate'] if winner else '',
                'makespan': winner['makespan'] if winner else '',
                'added_copy_bytes': winner['added_copy_bytes'] if winner else '',
                'plan_seconds': sum(r['plan_seconds'] for r in rows),
                'evaluation_seconds': sum(r['evaluation_seconds'] for r in rows),
                'candidate_wall_seconds': sum(r['wall_seconds'] for r in rows),
                'total_wall_seconds': 0., 'selected_plan_sha256': '', 'selected_result_sha256': ''}
    for row in rows:
        selected[f"{row['candidate']}_status"] = row['status']
        selected[f"{row['candidate']}_makespan"] = row['makespan']
    if winner:
        origin = exp / 'candidates' / key / winner['candidate']
        for filename, destination in (('plan.json', exp / 'plans' / f'{key}.json'),
                                      ('result.json', exp / 'metrics' / f'{key}_result.json')):
            shutil.copy2(origin / filename, destination)
        selected.update(selected_plan_sha256=digest(exp / 'plans' / f'{key}.json'),
                        selected_result_sha256=digest(exp / 'metrics' / f'{key}_result.json'))
        if selected['selected_plan_sha256'] != winner['plan_sha256'] or selected['selected_result_sha256'] != winner['result_sha256']:
            raise ValueError('selected artifact copy differs from winner')
    selected['total_wall_seconds'] = time.perf_counter() - started
    write_json(exp / 'metrics' / f'{key}_status.json', selected)
    return selected, rows


def planner_main():
    parser = argparse.ArgumentParser(description='Isolated fixed portfolio candidate planner')
    parser.add_argument('--candidate', choices=CANDIDATES, required=True)
    parser.add_argument('--graph', type=Path, required=True)
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--blocks-per-core', type=int, required=True)
    args = parser.parse_args()
    from multicore_cut_evaluate_problem_1 import read_scene_a_config
    import baseline
    import region_scheduler
    waits = read_scene_a_config(A_ROOT / 'data/config.txt')
    data = read_json(args.graph)
    parameters = (data, args.cores, args.blocks_per_core,
                  waits['task_same_core_wait_cycles'], waits['task_cross_core_wait_cycles'])
    if args.candidate == 'v001':
        plan = baseline.make_plan(*parameters)
    else:
        plan, stats = region_scheduler.make_plan_with_stats(*parameters)
        write_json(args.output / 'partition.json', stats)
    write_json(args.output / 'plan.json', plan)


if __name__ == '__main__':
    planner_main()
