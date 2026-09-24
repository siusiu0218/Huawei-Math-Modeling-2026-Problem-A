"""Audit all frozen batches and produce complete-denominator Q1 tables and figures."""
import argparse
from collections import Counter
import csv
from datetime import datetime
from pathlib import Path
import shutil
import statistics
import sys

SOLUTION = next(p for p in Path(__file__).resolve().parents
                if (p / 'src').is_dir() and (p / 'experiments').is_dir())
sys.path.insert(0, str(SOLUTION / 'experiments'))
import run_baseline as archive
from portfolio_scheduler import choose_candidate, digest, read_json, validate_result, write_json
from result_paths import experiment_path, result_path


def check(condition, message):
    if not condition:
        raise ValueError(message)


def load_batch(root, batch, version, freeze, freeze_hash, expected_keys=None, allow_paused=False):
    exp = experiment_path(version, batch['experiment'])
    m = read_json(exp / 'manifest.json')
    check(m['status'] in ('completed', 'completed_with_failures') or (allow_paused and m['status'] == 'paused_by_user'), f'incomplete {exp}')
    check(m['suite_freeze_sha256'] == freeze_hash, 'wrong suite freeze')
    check(m['protected_hashes_before'] == freeze['protected_hashes'] and m['protected_inputs_unchanged'], 'input drift')
    if 'cases' in batch:
        check(m['cases'] == batch['cases'], 'wrong cases')
    check(datetime.fromisoformat(m['started_utc']) > datetime.fromisoformat(freeze['utc']), 'freeze after run')
    for relative, expected in freeze['source_hashes'].items():
        check(digest(exp / 'source' / relative) == expected, f'source drift {relative}')
    hashes = m['artifact_hashes_at_pause'] if allow_paused else m['artifact_hashes']
    for relative, expected in hashes.items():
        check(digest(exp / relative) == expected, f'artifact drift {relative}')
    cores = [1] if version == 'v001' else [2, 3, 4, 5]
    with (exp / 'metrics/summary.csv').open(encoding='utf-8-sig', newline='') as f:
        csv_rows = list(csv.DictReader(f))
    expected = expected_keys if expected_keys is not None else {(c, k) for c in batch['cases'] for k in cores}
    check(len(csv_rows) == len(expected) and {(r['case'], int(r['cores'])) for r in csv_rows} == expected, 'missing/duplicate rows')
    rows, candidates = [], []
    for csv_row in csv_rows:
        key = f"{csv_row['case']}_n{csv_row['cores']}"
        row = read_json(exp / 'metrics' / f'{key}_status.json')
        check(all(('' if row[k] is None else str(row[k])) == value for k, value in csv_row.items()), 'CSV/status mismatch')
        if version == 'v001':
            check(m['parameters']['timeout'] == freeze['single_timeout_seconds'], 'single timeout changed')
            if row['status'] == 'ok':
                values = validate_result(read_json(exp / 'metrics' / f'{key}_result.json'), 1)
                check(all(row[k] == value for k, value in values.items()), 'single score mismatch')
        else:
            check(m['policy'] == freeze['policy'], 'portfolio policy drift')
            pair = [read_json(exp / 'candidates' / key / c / 'status.json') for c in ('v001', 'v008')]
            winner = choose_candidate(pair)
            check(row['candidate_count'] == 2, 'candidate budget changed')
            expected_status = 'ok' if all(r['status'] == 'ok' for r in pair) else 'degraded' if winner else 'failed'
            check(row['status'] == expected_status, 'selection status mismatch')
            for candidate in pair:
                c = candidate['candidate']
                folder = exp / 'candidates' / key / c
                if candidate['status'] == 'ok':
                    values = validate_result(read_json(folder / 'result.json'), row['cores'])
                    check(all(candidate[k] == value for k, value in values.items()), 'candidate score mismatch')
                    check(digest(folder / 'plan.json') == candidate['plan_sha256'], 'candidate plan mismatch')
                    check(digest(folder / 'result.json') == candidate['result_sha256'], 'candidate result mismatch')
                candidates.append({'case': row['case'], 'cores': row['cores'], 'experiment': exp.name, **candidate})
            if row.get('operational_recovery'):
                check((row['case'], row['cores']) == ('case_087', 5), 'unexpected recovery configuration')
                check(row['plan_seconds'] is None and row['evaluation_seconds'] is None and row['total_wall_seconds'] is None, 'unknown original timing must remain null')
                check(pair[1]['plan_seconds'] is None, 'missing original generation timing hidden')
                check(abs(row['recorded_plan_seconds'] - pair[0]['plan_seconds']) < 1e-7, 'known planning cost mismatch')
                check(abs(row['recorded_evaluation_seconds'] - sum(c['evaluation_seconds'] for c in pair)) < 1e-7, 'known evaluation cost mismatch')
            else:
                for field in ('plan_seconds', 'evaluation_seconds'):
                    check(abs(row[field] - sum(c[field] for c in pair)) < 1e-7, 'cost mismatch')
            if winner:
                check(row['selected_candidate'] == winner['candidate'] and row['makespan'] == winner['makespan'], 'winner mismatch')
                check(row['added_copy_bytes'] == winner['added_copy_bytes'], 'selected movement mismatch')
                check(digest(exp / 'plans' / f'{key}.json') == winner['plan_sha256'], 'selected plan mismatch')
                check(digest(exp / 'metrics' / f'{key}_result.json') == winner['result_sha256'], 'selected result mismatch')
            else:
                check(not (exp / 'plans' / f'{key}.json').exists(), 'failed selection has a plan')
        rows.append(row)
    return rows, candidates, m


def figure(output, aggregate, recovered=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'DejaVu Sans'],
                         'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False,
                         'svg.fonttype': 'none', 'pdf.fonttype': 42})
    fig, ax = plt.subplots(figsize=(6.4, 3.6), layout='constrained')
    plotted = False
    for name, label, color in [('v009', 'v009: best of two candidates', '#2878A0'), ('v001', 'v001: one candidate', '#71797E')]:
        group = [r for r in aggregate if r['algorithm'] == name]
        if len(group) == 5 and all(r['mean_speedup'] != '' for r in group):
            ax.plot([r['cores'] for r in group], [r['mean_speedup'] for r in group], 'o-', color=color, label=label, linewidth=1.5, markersize=4)
            plotted = True
    if not plotted:
        plt.close(fig)
        return []
    ax.axhline(1, color='#aaa', linewidth=.7, linestyle=':')
    ax.set(xlabel='Number of cores', ylabel='Mean single-core / multicore makespan', xticks=range(1, 6))
    ax.set_title('Problem 1 | All 100 graphs', loc='left', fontsize=11)
    ax.legend(loc='upper left', fontsize=8)
    batches = 'Multicore: exp030–039' + (' + exp050' if recovered else '') + '; single reference: exp040–049.'
    fig.supxlabel('Arithmetic mean of 100 per-graph ratios; selection evaluation cost counted separately.\n' + batches, fontsize=7)
    outputs = []
    for extension in ('svg', 'pdf', 'png'):
        p = output / f'mean_speedup.{extension}'
        fig.savefig(p, dpi=220)
        outputs.append(p.name)
    plt.close(fig)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recovery-freeze', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    freeze = read_json(args.freeze)
    freeze_hash = digest(args.freeze)
    check(archive.protected_hashes() == freeze['protected_hashes'], 'current inputs changed')
    for relative, expected in freeze['source_hashes'].items():
        check(digest(experiment_path('v009', freeze['multicore_batches'][0]['experiment']) / 'source' / relative) == expected, f'frozen source changed: {relative}')
    recovery = read_json(args.recovery_freeze) if args.recovery_freeze else None
    if recovery:
        check(recovery['full_freeze_sha256'] == freeze_hash, 'wrong recovery source')
        check(digest(experiment_path('v009', recovery['experiment']) / 'source/experiments/run_resume_suite.py') == recovery['driver_sha256'], 'recovery driver drift')
        for relative, expected in recovery['preexisting_hashes'].items():
            check(digest(result_path(relative) if Path(relative).parts[0] == 'results' else archive.SOURCE / relative) == expected, 'recovery input drift')
        progress = read_json(result_path(recovery['progress_path']))
        check(progress['status'] == 'all_batches_finished' and progress['recovery_freeze_sha256'] == digest(args.recovery_freeze), 'recovery unfinished')
        old_progress = read_json(result_path(freeze['progress_path']))
        stop = read_json(result_path('problem_1/v009/pause_processes_20260924.json'))
        suite_wall = ((datetime.fromisoformat(stop['utc']) - datetime.fromisoformat(old_progress['started_utc'])).total_seconds()
                      + (datetime.fromisoformat(progress['ended_utc']) - datetime.fromisoformat(progress['started_utc'])).total_seconds())
    else:
        progress = read_json(result_path(freeze['progress_path']))
        check(progress['status'] == 'all_batches_finished' and progress['freeze_sha256'] == freeze_hash, 'suite not finished')
        suite_wall = (datetime.fromisoformat(progress['ended_utc']) - datetime.fromisoformat(progress['started_utc'])).total_seconds()
    multi, single, candidates, manifests = [], [], [], {}
    wall = 0.
    for kind, version in [('multicore_batches', 'v009'), ('single_batches', 'v001')]:
        for batch in freeze[kind]:
            partial = recovery and batch['experiment'] == Path(recovery['partial_experiment']).name
            expected = None
            if partial:
                excluded = {(r['case'], r['cores']) for r in recovery['remaining_configurations']}
                expected = {(c, k) for c in batch['cases'] for k in range(2, 6)} - excluded
            rows, cs, manifest = load_batch(archive.SOURCE, batch, version, freeze, freeze_hash, expected_keys=expected, allow_paused=bool(partial))
            (multi if version == 'v009' else single).extend(rows)
            candidates.extend(cs)
            p = experiment_path(version, batch['experiment']) / 'manifest.json'
            manifests[str(p)] = digest(p)
            wall += manifest.get('elapsed_seconds', 0)
    if recovery:
        expected = {(r['case'], r['cores']) for r in recovery['remaining_configurations']}
        batch = {'experiment': recovery['experiment']}
        rows, cs, manifest = load_batch(archive.SOURCE, batch, 'v009', freeze, freeze_hash, expected_keys=expected)
        exp = experiment_path('v009', recovery['experiment'])
        check(manifest['recovery_freeze'] == recovery, 'recovery selection mismatch')
        check(digest(exp / 'source/experiments/run_resume_suite.py') == recovery['driver_sha256'], 'recovery source snapshot mismatch')
        original = result_path(recovery['partial_experiment']) / 'candidates/case_087_n5'
        copied = exp / 'candidates/case_087_n5'
        for name in ('plan.json', 'result.json', 'status.json'):
            check(digest(original / 'v001' / name) == digest(copied / 'v001' / name), 'reused v001 differs')
        check(digest(original / 'v008/plan.json') == digest(copied / 'v008/plan.json'), 'interrupted plan changed')
        multi.extend(rows)
        candidates.extend(cs)
        manifests[str(exp / 'manifest.json')] = digest(exp / 'manifest.json')
        wall += manifest['elapsed_seconds']
    check(len(multi) == 400 and len(single) == 100 and len(candidates) == 800, 'incomplete planned coverage')
    cases = {r['case'] for r in freeze['splits']['full']}
    check({(r['case'], r['cores']) for r in multi} == {(c, k) for c in cases for k in range(2, 6)}, 'multi coverage mismatch')
    check({r['case'] for r in single} == cases, 'single coverage mismatch')
    singles = {r['case']: r for r in single}
    candidate_map = {(r['case'], r['cores'], r['candidate']): r for r in candidates}
    table = []
    for row in multi:
        reference = singles[row['case']]
        available = row['status'] in ('ok', 'degraded') and reference['status'] == 'ok'
        baseline = candidate_map[row['case'], row['cores'], 'v001']
        table.append({**row, 'single_status': reference['status'], 'single_makespan': reference['makespan'],
                      'speedup': reference['makespan'] / row['makespan'] if available else '',
                      'v001_speedup': reference['makespan'] / baseline['makespan'] if reference['status'] == baseline['status'] == 'ok' else '',
                      'reduction_vs_v001_percent': (1 - row['makespan'] / baseline['makespan']) * 100 if row['status'] in ('ok', 'degraded') and baseline['status'] == 'ok' else ''})
    aggregate = []
    for method, column in [('v009', 'speedup'), ('v001', 'v001_speedup')]:
        for k in range(1, 6):
            values = [1 for r in single if r['status'] == 'ok'] if k == 1 else [r[column] for r in table if r['cores'] == k and r[column] != '']
            aggregate.append({'algorithm': method, 'cores': k, 'expected': 100, 'available': len(values),
                              'mean_speedup': statistics.mean(values) if len(values) == 100 else '',
                              'minimum_speedup': min(values) if len(values) == 100 else '',
                              'maximum_speedup': max(values) if len(values) == 100 else '',
                              'faster_than_single': sum(v > 1 for v in values),
                              'equal_to_single': sum(v == 1 for v in values),
                              'slower_than_single': sum(v < 1 for v in values)})
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.output / Path(__file__).name)
    def union_csv(path, items):
        keys = list(dict.fromkeys(k for r in items for k in r))
        archive.write_csv(path, [{k: r.get(k, '') for k in keys} for r in items])
    union_csv(args.output / 'multicore_comparison.csv', table)
    archive.write_csv(args.output / 'single_references.csv', single)
    union_csv(args.output / 'candidates.csv', candidates)
    archive.write_csv(args.output / 'mean_speedup.csv', aggregate)
    failures = [{'case': r['case'], 'cores': r['cores'], 'candidate': r['candidate'], 'status': r['status'], 'phase': r['failure_phase'], 'error': r['error'], 'experiment': r['experiment']} for r in candidates if r['status'] != 'ok']
    failures += [{'case': r['case'], 'cores': 1, 'candidate': 'single_reference', 'status': r['status'], 'phase': 'evaluation', 'error': r['error'], 'experiment': r['experiment']} for r in single if r['status'] != 'ok']
    write_json(args.output / 'failures.json', failures)
    plots = figure(args.output, aggregate, recovered=bool(recovery))
    counts = {'multicore': dict(Counter(r['status'] for r in multi)), 'single': dict(Counter(r['status'] for r in single)),
              'candidates': dict(Counter(r['status'] for r in candidates)), 'selected': dict(Counter(r['selected_candidate'] for r in multi)),
              'faster': sum(r['reduction_vs_v001_percent'] != '' and r['reduction_vs_v001_percent'] > 0 for r in table),
              'equal': sum(r['reduction_vs_v001_percent'] == 0 for r in table),
              'slower': sum(r['reduction_vs_v001_percent'] != '' and r['reduction_vs_v001_percent'] < 0 for r in table)}
    completed = all(r['status'] in ('ok', 'degraded') for r in multi) and all(r['status'] == 'ok' for r in single)
    recorded_cost = {field: sum(r[field] if r[field] is not None else r['recorded_' + field] for r in multi)
                     for field in ('plan_seconds', 'evaluation_seconds', 'total_wall_seconds')}
    lines = ['# 第一问：v009 全量评估', '',
             f"全部 100 张图、400 个多核配置、800 个候选及100个单核参考均已尝试。最终成绩与分母{'完整' if completed else '仍有缺失'}。", '',
             f"多核配置状态：{counts['multicore']}；候选状态：{counts['candidates']}；单核参考：{counts['single']}。", '',
             '## 平均加速比', '', '采用100个逐图单核/多核Makespan比值的算术平均。缺少任一分子或分母时不输出该核数的完整平均值。', '',
             '| 方法 | 核数 | 可用 / 100 | 平均加速比 | 比单核快 / 平 / 慢 |', '|---|---:|---:|---:|---:|']
    for r in aggregate:
        value = f"{r['mean_speedup']:.4f}" if r['mean_speedup'] != '' else '未完整'
        lines.append(f"| {r['algorithm']} | {r['cores']} | {r['available']} | {value} | {r['faster_than_single']} / {r['equal_to_single']} / {r['slower_than_single']} |")
    if plots:
        lines += ['', '![平均加速比](mean_speedup.png)']
    lines += ['', '## 比较与成本', '',
              f"- 选择次数：{counts['selected']}。对有成功v001参考的配置：{counts['faster']}快、{counts['equal']}平、{counts['slower']}慢；失败配对不混入比较。",
              '- v009对v001、v008各运行一次，成功者中按Makespan择优。这包含额外一次评估成本，相对v001不退步是选择规则的性质，不是等预算单算法创新证据。',
              f"- 多核已记录求解耗时 {recorded_cost['total_wall_seconds']:.3f}秒，其中生成 {recorded_cost['plan_seconds']:.3f}秒、评估 {recorded_cost['evaluation_seconds']:.3f}秒。" + ('人工中断配置的原生成/中断评估耗时未最终写出，因此这些累计值是下界，完整耗时字段保留为空。' if recovery else ''),
              f"- 单核参考评估累计 {sum(r['evaluation_seconds'] for r in single):.3f}秒。",
              f"- 驱动活动运行区间约 {suite_wall:.3f}秒（含源码快照与归档；排除人工暂停间隔）。",
              '- 多核每候选生成30秒、评估180秒；单进程；单核参考统一1800秒。全部图按静态规模分批，无新增独立检验声明。',
              '- 人工中断后仅重启case_087_n5的v008评估；其v001直接复用、v008方案不变，其余383个已完成配置未重跑。该额外尝试单独披露。' if recovery else '- 无重试。',
              '- 历史单核记录与当前工作树存在12个换行符导致的原始哈希差异；本轮全部100个单核参考重算，不混用旧分母。',
              '', '## 可追溯产物', '',
              '- multicore_comparison.csv：400项最终成绩、额外搬运、候选成绩、耗时及单核加速比。',
              '- single_references.csv：全部100项单核状态与指标。candidates.csv：全部800候选及失败/超时。',
              '- mean_speedup.csv：平均加速比来源。' + ('已生成SVG/PDF/PNG曲线。' if plots else '完整分母未齐，未生成全量曲线。'),
              '- manifest.json：输入冻结、原批次及恢复记录哈希与本报告产物哈希。各批原始结果、时间线、方案、源快照、命令和日志独立保留。',
              '', '## 失败与未完成事项', '']
    lines += [f"- {r['case']} n{r['cores']} {r['candidate']}: {r['status']} ({r['error']})" for r in failures] or ['- 本轮无失败或超时。']
    if recovery:
        interruption = read_json(result_path(recovery['partial_experiment']) / 'candidates/case_087_n5/v008/interruption.json')
        write_json(args.output / 'operational_interruption.json', interruption)
        lines += ['- 另有1次用户主动暂停导致的评估中断，原记录保留；不列为算法超时或失败。']
    lines += ['', '第二问、第三问不在本轮范围内，尚未开展。算法的数学模型与论文叙述仍需另行整理。', '']
    (args.output / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    write_json(args.output / 'manifest.json', {'utc': archive.stamp(), 'status': 'audited', 'full_scores_complete': completed,
                 'invocation': [sys.executable, '-B', *sys.argv],
                 'counts': counts, 'suite_active_wall_seconds_approx': suite_wall, 'recorded_multicore_cost_lower_bound': recorded_cost,
                 'operational_interruption_count': 1 if recovery else 0,
                 'recovery_freeze_sha256': digest(args.recovery_freeze) if recovery else None,
                 'freeze_sha256': freeze_hash, 'run_manifests': manifests, 'figure_contract': {
                     'claim': 'Mean speedup across all 100 graphs as core count changes; optimization budget reported separately.',
                     'backend': 'Python/matplotlib, matching existing project workflow', 'archetype': 'single quantitative trend',
                     'data': 'mean_speedup.csv', 'statistics': 'arithmetic mean of 100 per-graph ratios, no sampling CI',
                     'exports': plots, 'dimensions_inches': [6.4, 3.6], 'editable_text': True},
                 'output_hashes': {p.name: digest(p) for p in args.output.iterdir() if p.is_file()}})
    print(counts)
    print(args.output)


if __name__ == '__main__':
    main()
