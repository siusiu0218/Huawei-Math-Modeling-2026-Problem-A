"""Small, reproducible scene-B baseline using the frozen v001 partitioner."""
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
sys.path.insert(0, str(SOLUTION / 'src'))
sys.path.insert(0, str(A_ROOT / 'code'))

from baseline import make_plan
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import evaluate_scene_b, read_scene_b_config

VERSION = 'v001'
EXPERIMENT = 'exp051_20260925_scene_b_baseline'
CASES = ('case_093', 'case_078')
CORES = (2, 3, 4, 5)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    output = SOLUTION / 'outputs/09_problem2/raw/problem_2' / VERSION / EXPERIMENT
    output.mkdir(parents=True, exist_ok=False)
    for subdir in ('source', 'plans', 'metrics', 'logs'):
        (output / subdir).mkdir()
    for source in (SOLUTION / 'src/baseline.py', SOLUTION / 'src/graph_analysis.py',
                   Path(__file__)):
        shutil.copy2(source, output / 'source' / source.name)
    config_path = A_ROOT / 'data/config.txt'
    config = read_evaluation_config(config_path)
    delay = read_scene_b_config(config_path)['cross_core_copy_delay_cycles']
    rows = []
    manifest = {
        'problem': 2, 'algorithm_version': VERSION, 'experiment': EXPERIMENT,
        'status': 'running', 'cases': CASES, 'cores': CORES,
        'parameters': {'blocks_per_core': 4, 'partitioner': 'problem-1 v001',
                       'scene_b_delay': delay, 'capacity': config['capacity'],
                       'bandwidth': config['bandwidth']},
        'config_sha256': digest(config_path),
        'evaluator_sha256': digest(A_ROOT / 'code/multicore_cut_evaluate_problem_2.py'),
        'source_sha256': {p.name: digest(p) for p in (output / 'source').iterdir()},
        'input_sha256': {},
        'reproduce': 'python -B A题/solution/experiments/run_problem2_baseline.py (change EXPERIMENT to a new name)',
    }
    write_json(output / 'manifest.json', manifest)
    try:
        for case in CASES:
            source = A_ROOT / 'data' / f'{case}.json'
            manifest['input_sha256'][case] = digest(source)
            data = json.loads(source.read_text(encoding='utf-8'))
            for n in CORES:
                name = f'{case}_n{n}'
                t0 = time.perf_counter()
                try:
                    # The original evaluator, rather than the partition proxy,
                    # supplies all scene-B performance and transfer measurements.
                    plan = make_plan(data, n)
                    write_json(output / 'plans' / f'{name}.json', plan)
                    result = evaluate_scene_b(data, plan, config['bandwidth'],
                                              config['capacity'], delay)
                    row = {'problem': 2, 'algorithm_version': VERSION,
                           'experiment': EXPERIMENT, 'case': case, 'cores': n,
                           'status': 'success', 'makespan': result['makespan'],
                           'cross_task_traffic': result['cross_task_traffic'],
                           'data_movement_bytes': result['data_movement_bytes'],
                           'runtime_seconds': round(time.perf_counter() - t0, 6),
                           'error': ''}
                except Exception as exc:
                    row = {'problem': 2, 'algorithm_version': VERSION,
                           'experiment': EXPERIMENT, 'case': case, 'cores': n,
                           'status': 'failed', 'makespan': '',
                           'cross_task_traffic': '', 'data_movement_bytes': '',
                           'runtime_seconds': round(time.perf_counter() - t0, 6),
                           'error': f'{type(exc).__name__}: {exc}'}
                rows.append(row)
                print(name, row['status'], row['makespan'], flush=True)
        with (output / 'metrics/results.csv').open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        manifest['status'] = 'completed' if all(r['status'] == 'success' for r in rows) else 'partial'
        manifest['success_count'] = sum(r['status'] == 'success' for r in rows)
        manifest['total_count'] = len(rows)
    finally:
        write_json(output / 'manifest.json', manifest)


if __name__ == '__main__':
    main()
