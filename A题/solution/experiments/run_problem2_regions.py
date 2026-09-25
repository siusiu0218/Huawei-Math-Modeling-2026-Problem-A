"""Scene-B pilot of the existing region partitioner with scene-B waits."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

sys.dont_write_bytecode = True
SOLUTION = Path(__file__).resolve().parents[1]
A_ROOT = SOLUTION.parent
sys.path[:0] = [str(SOLUTION / 'src'), str(A_ROOT / 'code')]
from region_scheduler import make_plan
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config

EXPERIMENT = 'exp052_20260925_scene_b_regions'
CASES = ('case_093', 'case_078')
CORES = (2, 3, 4, 5)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    out = SOLUTION / 'outputs/09_problem2/raw/problem_2/v002' / EXPERIMENT
    out.mkdir(parents=True, exist_ok=False)
    for name in ('source', 'plans', 'metrics'):
        (out / name).mkdir()
    for source in (SOLUTION / 'src/region_scheduler.py', SOLUTION / 'src/graph_analysis.py',
                   SOLUTION / 'src/component_scheduler.py', SOLUTION / 'src/baseline.py',
                   Path(__file__)):
        shutil.copy2(source, out / 'source' / source.name)
    config_path = A_ROOT / 'data/config.txt'
    cfg = read_evaluation_config(config_path)
    delay = read_scene_b_config(config_path)['cross_core_copy_delay_cycles']
    manifest = {'problem': 2, 'algorithm_version': 'v002', 'experiment': EXPERIMENT,
                'status': 'running', 'cases': CASES, 'cores': CORES,
                'parameters': {'blocks_per_core': 4, 'same_core_wait_proxy': 0,
                               'cross_core_wait_proxy': delay,
                               'capacity': cfg['capacity'], 'bandwidth': cfg['bandwidth']},
                'config_sha256': sha(config_path),
                'evaluator_sha256': sha(A_ROOT / 'code/multicore_cut_evaluate_problem_2.py'),
                'source_sha256': {p.name: sha(p) for p in (out / 'source').iterdir()},
                'input_sha256': {},
                'reproduce': 'python -B A题/solution/experiments/run_problem2_regions.py (change EXPERIMENT to a new name)'}
    save(out / 'manifest.json', manifest)
    rows = []
    try:
        for case in CASES:
            path = A_ROOT / 'data' / f'{case}.json'
            manifest['input_sha256'][case] = sha(path)
            data = json.loads(path.read_text(encoding='utf-8'))
            for n in CORES:
                start = time.perf_counter()
                try:
                    plan = make_plan(data, n, same_core_wait=0, cross_core_wait=delay)
                    save(out / 'plans' / f'{case}_n{n}.json', plan)
                    result = evaluate_scene_b(data, plan, cfg['bandwidth'], cfg['capacity'], delay)
                    row = {'problem': 2, 'algorithm_version': 'v002', 'experiment': EXPERIMENT,
                           'case': case, 'cores': n, 'status': 'success',
                           'makespan': result['makespan'],
                           'cross_task_traffic': result['cross_task_traffic'],
                           'data_movement_bytes': json.dumps(result['data_movement_bytes'], ensure_ascii=False),
                           'runtime_seconds': round(time.perf_counter() - start, 6), 'error': ''}
                except Exception as exc:
                    row = {'problem': 2, 'algorithm_version': 'v002', 'experiment': EXPERIMENT,
                           'case': case, 'cores': n, 'status': 'failed',
                           'makespan': '', 'cross_task_traffic': '', 'data_movement_bytes': '',
                           'runtime_seconds': round(time.perf_counter() - start, 6),
                           'error': f'{type(exc).__name__}: {exc}'}
                rows.append(row)
                print(case, n, row['status'], row['makespan'], flush=True)
        with (out / 'metrics/results.csv').open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        manifest['status'] = 'completed' if all(r['status'] == 'success' for r in rows) else 'partial'
        manifest['success_count'] = sum(r['status'] == 'success' for r in rows)
        manifest['total_count'] = len(rows)
    finally:
        save(out / 'manifest.json', manifest)


if __name__ == '__main__':
    main()
