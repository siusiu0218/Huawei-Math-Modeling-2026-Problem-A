"""Compare a frozen v001 CSV against all scheduled configurations of frozen v002 runs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--runs', required=True, nargs='+', type=Path)
    parser.add_argument('--selection-decision', required=True, type=Path)
    args = parser.parse_args()
    baseline = args.baseline.resolve()
    runs = [p.resolve() for p in args.runs]
    decision = read_json(args.selection_decision)
    origin = read_json(baseline.parent.parent / 'manifest.json')
    base = {(r['case'], int(r['cores'])): r for r in read_csv(baseline) if r['cores'] != '1'}
    rows, seen = [], set()
    code_hashes = None
    sources = {str(baseline): sha(baseline), str(args.selection_decision.resolve()): sha(args.selection_decision)}
    for run in runs:
        manifest = read_json(run / 'manifest.json')
        if not manifest['protected_inputs_unchanged'] or manifest['protected_hashes_before'] != origin['protected_hashes_before']:
            raise ValueError('original inputs differ across experiments')
        if manifest['parameters']['blocks_per_core'] != decision['blocks_per_core']:
            raise ValueError('not the frozen parameter choice')
        hashes = {k.replace('\\', '/'): v for k, v in manifest['source_hashes'].items()}
        relevant = {k: hashes[k] for k in ('src/component_scheduler.py', 'src/graph_analysis.py', 'src/baseline.py')}
        if code_hashes is not None and relevant != code_hashes:
            raise ValueError('algorithm code changed after tuning')
        code_hashes = relevant
        if relevant['src/component_scheduler.py'] != decision['component_scheduler_sha256']:
            raise ValueError('code differs from pre-holdout freeze')
        summary = run / 'metrics/summary.csv'
        sources[str(summary)] = sha(summary)
        for new in read_csv(summary):
            key = new['case'], int(new['cores'])
            if key in seen or key not in base:
                raise ValueError(f'duplicate or unexpected comparison {key}')
            seen.add(key)
            old = base[key]
            valid = new['status'] == old['status'] == 'ok'
            row = {'case': key[0], 'cores': key[1], 'split': new['split'],
                   'baseline_version': old['algorithm_version'], 'new_version': new['algorithm_version'],
                   'baseline_experiment': old['experiment'], 'new_experiment': new['experiment'],
                   'baseline_status': old['status'], 'new_status': new['status'],
                   'baseline_makespan': old['makespan'], 'new_makespan': new['makespan'],
                   'baseline_over_new': float(old['makespan']) / float(new['makespan']) if valid else '',
                   'time_reduction_percent': 100 * (1-float(new['makespan']) / float(old['makespan'])) if valid else '',
                   'baseline_added_bytes': old['added_copy_bytes'], 'new_added_bytes': new['added_copy_bytes'],
                   'baseline_used_cores': old['used_cores'], 'new_used_cores': new['used_cores'],
                   'new_plan_seconds': new['plan_seconds'], 'new_evaluation_seconds': new['evaluation_seconds']}
            rows.append(row)
    if seen != set(base):
        raise ValueError('comparison must cover every originally planned multicore configuration')
    rows.sort(key=lambda r: (r['split'], r['case'], r['cores']))
    target = runs[-1]
    output = target / 'metrics/version_comparison.csv'
    if output.exists():
        raise FileExistsError(output)
    with output.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    aggregate = []
    for split in ('tune', 'holdout', 'all'):
        for core in (2, 3, 4, 5):
            group = [r for r in rows if r['cores'] == core and (split == 'all' or r['split'] == split)]
            valid = [r for r in group if r['baseline_over_new'] != '']
            aggregate.append({'split': split, 'cores': core, 'expected': len(group), 'valid': len(valid),
                              'wins': sum(r['baseline_over_new'] > 1 for r in valid),
                              'mean_baseline_over_new': statistics.mean(r['baseline_over_new'] for r in valid) if valid and len(valid) == len(group) else None})
    (target / 'metrics/version_aggregate.json').write_text(json.dumps(aggregate, indent=2)+'\n', encoding='utf-8')
    snapshot = target / 'source/version_comparison.py'
    if snapshot.exists():
        raise FileExistsError(snapshot)
    shutil.copy2(__file__, snapshot)
    manifest = read_json(target / 'manifest.json')
    manifest['source_hashes']['version_comparison.py'] = sha(snapshot)
    manifest['version_comparison'] = {'inputs_sha256': sources, 'command': [sys.executable, '-B', *sys.argv],
                                       'configurations': len(rows), 'scope': '8 selected graphs only'}
    (target / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    lines = ['# v002 与冻结 v001 的同核比较', '',
             'v002 保留操作依赖图的完整弱连通分量，然后按计算量均衡分组与分核。单连通图回退 v001；尚未实现一般分叉汇合切分、通信感知合并或局部搜索。', '',
             '调参：4 张图分别试每核 4、16 个目标 Task。倍率 4 在 case_014 的四个配置均超时；倍率 16 在调参结果出来后冻结，再应用于另外 4 张检验图。每次每配置 1 个候选，调参阶段共尝试 32 个方案，检验阶段 16 个；v001 基线每配置仅 1 个候选，搜索预算不相等。', '',
             '两版均使用原始评估器和固定配置，评估超时 60 秒、最多两个并发进程。调参倍率改变本身也可能影响成绩，当前是整套方法的比较，未完成同倍率消融，不能将收益全部归因于连通分组。', '',
             '**下表比值为 v001 时间 / v002 时间，越大越好；不是题目要求的单核 / 多核加速比。case_014 的单核分母仍缺失，但其同核版本比较可以进行。**', '',
             '| 集合 | 核数 | 有效 / 计划 | 更快配置数 | 平均 v001/v002 时间比 |', '|---|---:|---:|---:|---:|']
    for r in aggregate:
        mean = f"{r['mean_baseline_over_new']:.3f}" if r['mean_baseline_over_new'] is not None else '不完整，不汇总'
        lines.append(f"| {r['split']} | {r['cores']} | {r['valid']}/{r['expected']} | {r['wins']} | {mean} |")
    lines += ['', '逐配置结果：[version_comparison.csv](metrics/version_comparison.csv)。所有失败和超时均保留；此结果不代表全部 100 张图。', '',
              '搬运量必须与完成时间分别解读：并行变快不意味着 DDR 字节数一定下降。求解与评估墙钟时间也分别记录，不把它们当作模拟周期。', '']
    (target / 'COMPARISON.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
