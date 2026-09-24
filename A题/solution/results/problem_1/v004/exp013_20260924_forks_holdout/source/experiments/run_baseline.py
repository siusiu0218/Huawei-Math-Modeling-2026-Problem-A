"""Reproducible read-only profiling and bounded problem-1 baseline experiments."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / 'src'))
from graph_analysis import A_ROOT, analyze_graph, select_cases
from baseline import VERSION, make_plan
import component_scheduler
import branch_scheduler
import fork_preserving_scheduler
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_1 import read_scene_a_config
from singlecore_evaluate import build_singlecore_plan
from contest_io import _read_json

SOLUTION = A_ROOT / 'solution'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def protected_hashes():
    return {str(p.relative_to(A_ROOT)): digest(p)
            for folder in ('code', 'data', 'docs')
            for p in sorted((A_ROOT / folder).rglob('*')) if p.is_file()}


def register(exp, mode, status):
    path = SOLUTION / 'experiments/INDEX.md'
    if not path.exists():
        path.write_text('# 实验目录\n\n记录包含原型、失败及中断，不表示第一问全量完成。\n\n', encoding='utf-8')
    rel = exp.relative_to(SOLUTION).as_posix()
    with path.open('a', encoding='utf-8') as stream:
        stream.write(f'- {stamp()} | `{VERSION}` | [{exp.name}](../{rel}/manifest.json) | {mode} | {status}\n')


def prepare(args):
    exp = SOLUTION / 'results/problem_1' / VERSION / args.experiment
    exp.mkdir(parents=True, exist_ok=False)
    for name in ('source', 'plans', 'metrics', 'logs', 'figures'):
        (exp / name).mkdir()
    for name in ('src', 'experiments', 'tests'):
        shutil.copytree(SOURCE / name, exp / 'source' / name,
                        ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('AGENTS.md', 'CONTEXT.md', 'README.md'):
        source = SOURCE / name
        if source.exists():
            shutil.copy2(source, exp / 'source' / name)
    manifest = {
        'problem': 1, 'algorithm_version': VERSION, 'experiment': args.experiment,
        'mode': args.mode, 'status': 'running', 'started_utc': stamp(),
        'python': sys.version, 'platform': platform.platform(), 'random_seed': None,
        'parameters': vars(args), 'evaluation_config': read_evaluation_config(A_ROOT / 'data/config.txt'),
        'wait_config': read_scene_a_config(A_ROOT / 'data/config.txt'),
        'protected_hashes_before': protected_hashes(),
        'source_hashes': {str(p.relative_to(exp / 'source')): digest(p)
                          for p in (exp / 'source').rglob('*.py')},
        'invocation': [sys.executable, '-B', *sys.argv],
        'reproduce_note': 'Use source/experiments/run_baseline.py with the same arguments and a NEW --experiment name. Original evaluator/data must match saved hashes.',
    }
    write_json(exp / 'manifest.json', manifest)
    register(exp, args.mode, 'running')
    return exp, manifest


def profile(exp, manifest):
    rows = []
    for index, path in enumerate(sorted((A_ROOT / 'data').glob('case_*.json')), 1):
        start = time.perf_counter()
        row = {'problem': 1, 'algorithm_version': VERSION, 'experiment': exp.name,
               'case': path.stem, 'input_sha256': digest(path)}
        row.update(analyze_graph(_read_json(str(path))))
        row['analysis_seconds'] = time.perf_counter() - start
        rows.append(row)
        if index % 20 == 0:
            print(f'profile {index} graphs', flush=True)
    write_csv(exp / 'metrics/graph_features.csv', rows)
    selected = select_cases(rows)
    write_json(exp / 'metrics/selected_cases.json', selected)
    manifest.update(cases=[r['case'] for r in rows], selected_cases=selected,
                    selection_rule='Sort by non-COPY count into quartiles. Anchor smallest in Q1-Q3 and largest in Q4; pick furthest structural case within each quartile. Anchor=tune, other=holdout. No performance outcomes used.')
    by_case = {r['case']: r for r in rows}
    lines = ['# 100 张图的静态特征与试验用例', '',
             f'版本 `{VERSION}`；实验 `{exp.name}`。成功读取并通过原始图校验：{len(rows)} 张。', '',
             '按非 COPY 操作数分为四个大小区间，每区间选一个大小锚点和一个结构差异较大的图。锚点用于调参，另一张留作检验；选择不使用运行成绩。', '',
             '| 用例 | 用途 | 大小区间 | 非 COPY 操作 | 计算量/最长链 | 最大层宽 |',
             '|---|---|---:|---:|---:|---:|']
    for item in selected:
        r = by_case[item['case']]
        lines.append(f"| {item['case']} | {item['split']} | {item['size_quartile']} | {r['compute_ops']} | {r['work_to_critical_ratio']:.2f} | {r['max_level_width']} |")
    lines += ['', '字段含义与边界：', '',
              '- `compute_ops`：全部非 COPY_IN/COPY_OUT 操作；`compute_cycles` 为它们的周期和。',
              '- `critical_compute_cycles`：保留经 COPY 传递的依赖，但仅累计非 COPY 周期的最长链。不是实际 Makespan。',
              '- `max_level_width`：按最长前驱层级分层的最大节点数；不是精确最大并发数。',
              '- `shared_input_tensors`：被多个非 COPY 操作直接使用的张量数量，含中间结果，不限于原始 DDR 输入。',
              '- `shared_input_bytes`：上述张量大小各计一次；不是预测的重复搬运量。',
              '- `tensor_bytes_sum`：图中全部张量大小之和，不是同时驻留内存峰值。',
              '- 这些特征用来选代表图和解释结构，不能证明多核加速效果。', '']
    (exp / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')


def evaluate_one(exp, item, cores, args, waits):
    case = item['case']
    key = f'{case}_n{cores}'
    graph_path = A_ROOT / 'data' / f'{case}.json'
    row = {'problem': 1, 'algorithm_version': VERSION, 'experiment': exp.name,
           'case': case, 'split': item['split'], 'cores': cores,
           'method': 'singlecore' if cores == 1 else args.algorithm,
           'status': 'pending', 'candidate_count': 1, 'plan_seconds': 0,
           'evaluation_seconds': 0, 'subgraphs': '', 'used_cores': '',
           'makespan': '', 'speedup': '', 'added_copy_bytes': '',
           'partition_added_copy_bytes': '', 'spill_added_copy_bytes': '',
           'scheduled_copy_bytes': '', 'task_busy_fraction': '', 'error': ''}
    try:
        data = _read_json(str(graph_path))
        start = time.perf_counter()
        plan = build_singlecore_plan(data) if cores == 1 else make_plan(
            data, cores, args.blocks_per_core,
            waits['task_same_core_wait_cycles'], waits['task_cross_core_wait_cycles'])
        row['plan_seconds'] = time.perf_counter() - start
        row['subgraphs'] = len(set(plan['node_to_subgraph'].values()))
        row['used_cores'] = sum(bool(order) for order in plan['core_schedules'])
        plan_path = exp / 'plans' / f'{key}.json'
        write_json(plan_path, plan)
        result_path = exp / 'metrics' / f'{key}_result.json'
        script = 'singlecore_evaluate.py' if cores == 1 else 'multicore_cut_evaluate_problem_1.py'
        command = [sys.executable, '-B', str(A_ROOT / 'code' / script), str(graph_path)]
        if cores != 1:
            command.append(str(plan_path))
        command += ['--config', str(A_ROOT / 'data/config.txt'), '-o', str(result_path),
                    '--trace-output', str(exp / 'logs' / f'{key}_trace.json'),
                    '--log-output', str(exp / 'logs' / f'{key}_evaluation.log')]
        write_json(exp / 'logs' / f'{key}_command.json', command)
        start = time.perf_counter()
        with (exp / 'logs' / f'{key}_process.log').open('w', encoding='utf-8') as log:
            try:
                completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                           timeout=args.timeout, check=False)
            finally:
                row['evaluation_seconds'] = time.perf_counter() - start
        if completed.returncode:
            raise RuntimeError(f'evaluator exit {completed.returncode}; see {key}_process.log')
        result = _read_json(str(result_path))
        movement = result['data_movement_bytes']
        if result['makespan'] <= 0:
            raise ValueError('nonpositive makespan cannot form a speedup')
        if result['num_cores'] != cores:
            raise ValueError('wrong core count in result')
        for peak in result['memory_peak_by_core'].values():
            if any(peak[pos] > result['capacity_bytes'][pos] for pos in peak):
                raise ValueError('reported memory peak exceeds capacity')
        latest = max((o['end'] for core in result['per_core_timeline'] for o in core['ops']), default=0)
        if abs(latest - result['makespan']) > 1e-6:
            raise ValueError('timeline end differs from makespan')
        busy = sum(task['end'] - task['start'] for core in result['per_core_timeline']
                   for task in core['tasks'])
        row.update(status='ok', makespan=result['makespan'],
                   task_busy_fraction=busy / (cores * result['makespan']))
        for field in ('added_copy_bytes', 'partition_added_copy_bytes',
                      'spill_added_copy_bytes', 'scheduled_copy_bytes'):
            row[field] = movement[field]
    except subprocess.TimeoutExpired:
        row.update(status='timeout', error=f'evaluator exceeded {args.timeout} seconds')
    except Exception as error:
        row.update(status='failed', error=f'{type(error).__name__}: {error}')
    write_json(exp / 'metrics' / f'{key}_status.json', row)
    return row


def benchmark(exp, manifest, args):
    selection_path = Path(args.selection).resolve()
    selected = _read_json(str(selection_path))
    if args.cases:
        missing = set(args.cases) - {r['case'] for r in selected}
        if missing:
            raise ValueError(f'cases not in saved selection: {sorted(missing)}')
        selected = [r for r in selected if r['case'] in args.cases]
    cases = [r['case'] for r in selected]
    if len(set(cases)) != len(cases) or not cases:
        raise ValueError('selection must contain unique nonempty cases')
    available = {p.stem for p in (A_ROOT / 'data').glob('case_*.json')}
    if any(c not in available for c in cases):
        raise ValueError('selection includes unknown case')
    manifest.update(cases=cases, cores=args.cores, selection=selected,
                    selection_sha256=digest(selection_path),
                    scope=f'small-sample {args.algorithm} experiment; no all-case performance claim')
    write_json(exp / 'manifest.json', manifest)
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(evaluate_one, exp, item, k, args, manifest['wait_config'])
                for item in selected for k in args.cores]
        for job in as_completed(jobs):
            row = job.result()
            rows.append(row)
            print(f"{len(rows)}/{len(jobs)} {row['case']} n{row['cores']} {row['status']} T={row['makespan']}", flush=True)
    rows.sort(key=lambda r: (r['case'], r['cores']))
    single = {r['case']: r['makespan'] for r in rows if r['cores'] == 1 and r['status'] == 'ok'}
    if args.single_reference:
        reference = Path(args.single_reference).resolve()
        origin = _read_json(str(reference.parent.parent / 'manifest.json'))
        if origin['protected_hashes_before'] != manifest['protected_hashes_before'] or not origin['protected_inputs_unchanged']:
            raise ValueError('single-core reference used different input/evaluator files')
        with reference.open(encoding='utf-8-sig', newline='') as stream:
            for r in csv.DictReader(stream):
                if r['cores'] == '1' and r['status'] == 'ok':
                    single.setdefault(r['case'], float(r['makespan']))
        manifest['single_reference'] = {'path': str(reference), 'sha256': digest(reference)}
    for row in rows:
        if row['status'] == 'ok' and row['case'] in single:
            row['speedup'] = single[row['case']] / row['makespan']
    write_csv(exp / 'metrics/summary.csv', rows)
    summary = []
    for split in ('all', 'tune', 'holdout'):
        for cores in args.cores:
            group = [r for r in rows if r['cores'] == cores and (split == 'all' or r['split'] == split)]
            good = [r for r in group if r['status'] == 'ok' and r['speedup'] != '']
            summary.append({'problem': 1, 'algorithm_version': VERSION, 'experiment': exp.name,
                            'split': split, 'cores': cores, 'expected': len(group), 'scored': len(good),
                            'mean_speedup': statistics.mean(r['speedup'] for r in good) if len(good) == len(group) and good else '',
                            'faster_than_single': sum(r['speedup'] > 1 for r in good),
                            'status': ('not_in_scope' if not group else
                                       'complete' if len(good) == len(group) else 'incomplete')})
    write_csv(exp / 'metrics/aggregate.csv', summary)
    manifest['job_status_counts'] = {s: sum(r['status'] == s for r in rows) for s in ('ok', 'failed', 'timeout')}
    manifest['planned_jobs'] = len(jobs)
    lines = ['# 第一问小范围调度试验', '', f'算法 `{VERSION}` / `{args.algorithm}`；实验 `{exp.name}`。', '',
             '仅评估选定用例，不代表第一问完成。参数预先固定，检验用例没有用于按成绩选择参数。', '',
             f'每核目标块数倍率：{args.blocks_per_core}；每配置 1 个候选；评估超时：{args.timeout} 秒；并发评估进程上限：{args.workers}。', '',
             '| 核数 | 完成评分 / 计划 | 平均加速比 | 比单核快的用例数 |', '|---:|---:|---:|---:|']
    for item in summary:
        if item['split'] == 'all':
            mean = f"{item['mean_speedup']:.4f}" if item['mean_speedup'] != '' else '未完整，暂不汇总'
            lines.append(f"| {item['cores']} | {item['scored']} / {item['expected']} | {mean} | {item['faster_than_single']} |")
    lines += ['', '查看 `metrics/summary.csv` 获取逐用例成绩和状态；`logs/*_trace.json` 可查看执行时间线。', '',
              '`task_busy_fraction` 是各核 Task 时间段占总核时间的比例，包含搬运和等待，不等于计算单元利用率。', '',
              '失败与超时：', '']
    failed = [r for r in rows if r['status'] != 'ok']
    lines += [f"- {r['case']} n{r['cores']}: {r['status']} — {r['error']}" for r in failed] or ['- 无。']
    (exp / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    global VERSION, make_plan
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('profile', 'benchmark'))
    parser.add_argument('--experiment', required=True)
    parser.add_argument('--selection')
    parser.add_argument('--blocks-per-core', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--cases', nargs='+', help='Optional subset of the frozen selected cases')
    parser.add_argument('--cores', nargs='+', type=int, default=[1, 2, 3, 4, 5])
    parser.add_argument('--algorithm', choices=('baseline', 'components', 'branches', 'forks'), default='baseline')
    parser.add_argument('--single-reference', help='Frozen summary CSV containing original single-core references')
    args = parser.parse_args()
    if not args.experiment or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in args.experiment):
        parser.error('experiment must use lowercase ASCII letters, digits, underscore or hyphen')
    if args.timeout <= 0 or args.workers < 1 or args.blocks_per_core < 1:
        parser.error('timeout, workers and blocks-per-core must be positive')
    if len(set(args.cores)) != len(args.cores) or any(k not in range(1, 6) for k in args.cores):
        parser.error('cores must be distinct values from 1 to 5')
    if args.mode == 'benchmark' and not args.selection:
        parser.error('benchmark requires --selection')
    if args.algorithm == 'components':
        VERSION, make_plan = component_scheduler.VERSION, component_scheduler.make_plan
    elif args.algorithm == 'branches':
        VERSION, make_plan = branch_scheduler.VERSION, branch_scheduler.make_plan
    elif args.algorithm == 'forks':
        VERSION, make_plan = fork_preserving_scheduler.VERSION, fork_preserving_scheduler.make_plan
    exp, manifest = prepare(args)
    start = time.perf_counter()
    try:
        if args.mode == 'profile':
            profile(exp, manifest)
        else:
            benchmark(exp, manifest, args)
        counts = manifest.get('job_status_counts', {})
        manifest['status'] = 'completed_with_failures' if counts.get('failed', 0) + counts.get('timeout', 0) else 'completed'
    except BaseException as error:
        manifest.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                        error=f'{type(error).__name__}: {error}')
        raise
    finally:
        after = protected_hashes()
        manifest.update(ended_utc=stamp(), elapsed_seconds=time.perf_counter() - start,
                        protected_inputs_unchanged=after == manifest['protected_hashes_before'])
        if not manifest['protected_inputs_unchanged']:
            manifest['status'] = 'invalid_inputs_changed'
        write_json(exp / 'manifest.json', manifest)
        register(exp, args.mode, manifest['status'])
    print(str(exp), flush=True)
    return 0 if manifest['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
