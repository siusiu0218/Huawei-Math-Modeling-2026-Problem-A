"""Combine an initial baseline run with failed-job retries, retaining provenance."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys
import shutil


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def summarize(original, retry):
    first, second = read(original / 'manifest.json'), read(retry / 'manifest.json')
    for field in ('problem', 'algorithm_version', 'protected_hashes_before', 'evaluation_config', 'wait_config'):
        if first[field] != second[field]:
            raise ValueError(f'cannot combine differing {field}')
    if not first['protected_inputs_unchanged'] or not second['protected_inputs_unchanged']:
        raise ValueError('input files changed during a run')
    if first['parameters']['blocks_per_core'] != second['parameters']['blocks_per_core']:
        raise ValueError('partition parameter changed across runs')
    # Algorithm code must match; a retry runner may add subset/timeout options.
    first_sources = {k.replace('\\', '/'): v for k, v in first['source_hashes'].items()}
    second_sources = {k.replace('\\', '/'): v for k, v in second['source_hashes'].items()}
    for field in ('src/baseline.py', 'src/graph_analysis.py'):
        if first_sources[field] != second_sources[field]:
            raise ValueError('algorithm changed across runs')
    expected = {(case, core) for case in first['cases'] for core in first['cores']}
    rows = {}
    replaced = []
    attempts = []
    input_hashes = {}
    for run in (original, retry):
        for path in sorted((run / 'metrics').glob('*_status.json')):
            item = read(path)
            key = item['case'], item['cores']
            if key not in expected:
                raise ValueError(f'unexpected retry job {key}')
            input_hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            if key in rows:
                if rows[key]['status'] == 'ok':
                    raise ValueError(f'retry must not replace successful result {key}')
                attempts.append({'case': key[0], 'cores': key[1], 'status': item['status'],
                                 'error': item.get('error', ''), 'experiment': item['experiment']})
                if item['status'] != 'ok':
                    continue
                replaced.append({'case': key[0], 'cores': key[1], 'old_status': rows[key]['status'],
                                 'old_experiment': rows[key]['experiment'], 'new_experiment': item['experiment']})
            item['source_result'] = str(run / 'metrics' / f'{key[0]}_n{key[1]}_result.json')
            rows[key] = item
    if set(rows) != expected:
        raise ValueError('missing job status records')
    baselines = {case: r['makespan'] for (case, k), r in rows.items() if k == 1 and r['status'] == 'ok'}
    ordered = [rows[key] for key in sorted(rows)]
    for row in ordered:
        row['speedup'] = (baselines[row['case']] / row['makespan']
                          if row['status'] == 'ok' and row['case'] in baselines else '')
    output = retry / 'metrics/combined_summary.csv'
    if output.exists():
        raise FileExistsError(output)
    snapshot = retry / 'source/recovery_summary.py'
    if snapshot.exists():
        raise FileExistsError(snapshot)
    shutil.copy2(Path(__file__), snapshot)
    second['source_hashes']['recovery_summary.py'] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    with output.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(ordered[0]))
        writer.writeheader()
        writer.writerows(ordered)
    aggregates = []
    for split in ('all', 'tune', 'holdout'):
        for k in first['cores']:
            group = [r for r in ordered if r['cores'] == k and (split == 'all' or r['split'] == split)]
            valid = [r for r in group if r['speedup'] != '']
            aggregates.append({'split': split, 'cores': k, 'expected': len(group), 'scored': len(valid),
                               'mean_speedup': statistics.mean(r['speedup'] for r in valid) if group and len(valid) == len(group) else None,
                               'faster_than_single': sum(r['speedup'] > 1 for r in valid)})
    (retry / 'metrics/combined_aggregate.json').write_text(
        json.dumps(aggregates, indent=2) + '\n', encoding='utf-8')
    second['recovery_rollup'] = {'original_experiment': str(original), 'replacements': replaced,
                                 'retry_attempts': attempts,
                                 'input_status_sha256': input_hashes, 'combined_jobs': len(ordered),
                                 'complete_scored_jobs': sum(r['speedup'] != '' for r in ordered),
                                 'command': [sys.executable, '-B', *sys.argv]}
    (retry / 'manifest.json').write_text(json.dumps(second, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# 第一问 v001 基线：首轮与超时重试合并结果', '',
             f'原实验 `{original.name}`；重试实验 `{retry.name}`。算法和原始评估材料哈希一致。', '',
             '只用成功重试补充此前失败项；原始失败记录未覆盖。各行 `experiment` 和 `source_result` 标明结果来源。', '',
             '仅覆盖选定的 8 张图，不代表全部 100 张图，也没有与改进算法比较。', '',
             '| 核数 | 完整评分 / 计划 | 平均加速比 | 比单核快的用例数 |', '|---:|---:|---:|---:|']
    for row in aggregates:
        if row['split'] == 'all':
            mean = f"{row['mean_speedup']:.4f}" if row['mean_speedup'] is not None else '未完整，暂不汇总'
            lines.append(f"| {row['cores']} | {row['scored']} / {row['expected']} | {mean} | {row['faster_than_single']} |")
    lines += ['', '重试记录：', '']
    lines += [f"- {r['case']} n{r['cores']}: {r['status']}。{r['error']}" for r in attempts]
    lines += ['', '逐用例结果：[combined_summary.csv](metrics/combined_summary.csv)。分组汇总：[combined_aggregate.json](metrics/combined_aggregate.json)。', '',
              '并发数、超时预算不同，因此只合并相同算法的模拟周期与搬运量；不将各次墙钟时间混合后用于比较运行效率。', '']
    (retry / 'COMBINED_REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(aggregates[:len(first['cores'])], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: summarize_recovery.py <original_run_dir> <retry_run_dir>')
    summarize(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
