"""Audit frozen v009 runs against raw artifacts, then create a new summary."""
import argparse
from collections import Counter
import csv
from datetime import datetime
from pathlib import Path
import shutil
import sys

import run_baseline as archive
from portfolio_scheduler import CANDIDATES, choose_candidate, digest, read_json, validate_result, write_json


def audit_run(run, freeze, freeze_hash):
    manifest = read_json(run / 'manifest.json')
    assert manifest['algorithm_version'] == 'v009'
    assert manifest['status'] in ('completed', 'completed_with_failures')
    assert manifest['selection_sha256'] == freeze_hash
    assert digest(run / 'selection.json') == freeze_hash
    assert manifest['policy'] == freeze['policy']
    assert manifest['protected_inputs_unchanged']
    assert manifest['protected_hashes_before'] == freeze['protected_hashes']
    assert datetime.fromisoformat(freeze['utc']) < datetime.fromisoformat(manifest['started_utc'])
    for relative, expected in freeze['source_hashes'].items():
        assert digest(run / 'source' / relative) == expected, relative
    for relative, expected in manifest['artifact_hashes'].items():
        assert digest(run / relative) == expected, relative
    split = manifest['parameters']['split']
    expected_keys = {(r['case'], k) for r in freeze['splits'][split] for k in freeze['cores'][split]}
    with (run / 'metrics/summary.csv').open(encoding='utf-8-sig', newline='') as stream:
        csv_rows = list(csv.DictReader(stream))
    assert len(csv_rows) == len(expected_keys)
    assert {(r['case'], int(r['cores'])) for r in csv_rows} == expected_keys
    comparisons, costs = [], []
    for r in csv_rows:
        key = f"{r['case']}_n{r['cores']}"
        selected = read_json(run / 'metrics' / f'{key}_status.json')
        assert all(str(selected[k]) == value for k, value in r.items())
        assert selected['candidate_count'] == 2
        candidate_rows = []
        for candidate in CANDIDATES:
            root = run / 'candidates' / key / candidate
            row = read_json(root / 'status.json')
            assert row['candidate'] == candidate
            if row['status'] == 'ok':
                raw = read_json(root / 'result.json')
                assert all(row[k] == v for k, v in validate_result(raw, int(r['cores'])).items())
                assert digest(root / 'result.json') == row['result_sha256']
                assert digest(root / 'plan.json') == row['plan_sha256']
            candidate_rows.append(row)
            costs.append({'case': r['case'], 'split': split, 'cores': int(r['cores']), **row})
        winner = choose_candidate(candidate_rows)
        expected_status = 'ok' if all(c['status'] == 'ok' for c in candidate_rows) else 'degraded' if winner else 'failed'
        assert selected['status'] == expected_status
        for field in ('plan_seconds', 'evaluation_seconds'):
            assert abs(selected[field] - sum(c[field] for c in candidate_rows)) < 1e-8
        assert abs(selected['candidate_wall_seconds'] - sum(c['wall_seconds'] for c in candidate_rows)) < 1e-8
        assert selected['total_wall_seconds'] >= selected['candidate_wall_seconds']
        if winner:
            assert selected['selected_candidate'] == winner['candidate']
            assert selected['makespan'] == winner['makespan']
            assert selected['added_copy_bytes'] == winner['added_copy_bytes']
            assert digest(run / 'plans' / f'{key}.json') == winner['plan_sha256']
            assert digest(run / 'metrics' / f'{key}_result.json') == winner['result_sha256']
        else:
            assert not (run / 'plans' / f'{key}.json').exists()
        improvement = (1 - selected['makespan'] / selected['v001_makespan']) * 100 if selected['status'] == 'ok' else ''
        comparisons.append({**selected, 'reduction_vs_v001_percent': improvement})
    assert dict(Counter(r['status'] for r in comparisons)) == manifest['configuration_status_counts']
    assert dict(Counter(r['status'] for r in costs)) == manifest['candidate_status_counts']
    return comparisons, costs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', nargs='+', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    freeze = read_json(args.freeze)
    freeze_hash = digest(args.freeze)
    assert archive.protected_hashes() == freeze['protected_hashes']
    assert not (set(r['case'] for r in freeze['splits']['holdout']) & set(freeze['excluded_seen_cases']))
    for relative, expected in freeze['source_hashes'].items():
        assert digest(archive.SOURCE / relative) == expected, relative
    rows, costs = [], []
    for run in args.runs:
        comparisons, candidates = audit_run(run, freeze, freeze_hash)
        rows.extend(comparisons)
        costs.extend(candidates)
    assert len({(r['case'], r['cores']) for r in rows}) == len(rows)
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.output / Path(__file__).name)
    archive.write_csv(args.output / 'comparison.csv', rows)
    archive.write_csv(args.output / 'candidates.csv', costs)
    scope = {}
    lines = ['# v009 固定双候选：开发流程与新图检验', '',
             '候选 v001、v008 和参数在运行前冻结。每个配置实际生成并评估两个候选，按原始 Makespan 选较小者；完全持平选 v001。', '',
             '这是增加一次评估换取结果选择的组合方法；相对已成功 v001 的不退步是选择规则的直接结果，不作为单一启发式的新优势。', '',
             '| 阶段 | 完整配置 | 选择 v001 / v008 | 相对 v001 更快 / 持平 / 更慢 | 生成合计 s | 评估合计 s | 配置总耗时 s |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for split in ('development', 'holdout'):
        group = [r for r in rows if r['split'] == split]
        complete = [r for r in group if r['status'] == 'ok']
        stat = {'configurations': len(group), 'complete': len(complete),
                'degraded': sum(r['status'] == 'degraded' for r in group),
                'failed': sum(r['status'] == 'failed' for r in group),
                'selected_v001': sum(r['selected_candidate'] == 'v001' for r in complete),
                'selected_v008': sum(r['selected_candidate'] == 'v008' for r in complete),
                'faster': sum(r['makespan'] < r['v001_makespan'] for r in complete),
                'equal': sum(r['makespan'] == r['v001_makespan'] for r in complete),
                'slower': sum(r['makespan'] > r['v001_makespan'] for r in complete),
                **{k: sum(r[k] for r in group) for k in ('plan_seconds', 'evaluation_seconds', 'total_wall_seconds')}}
        scope[split] = stat
        lines.append(f"| {split} | {stat['complete']}/{stat['configurations']} | {stat['selected_v001']} / {stat['selected_v008']} | {stat['faster']} / {stat['equal']} / {stat['slower']} | {stat['plan_seconds']:.3f} | {stat['evaluation_seconds']:.3f} | {stat['total_wall_seconds']:.3f} |")
    lines += ['', '## 新图逐项结果', '', '| 用例 | 核数 | v001 cycles | v008 cycles | 选择 | 相对 v001 减少 | 总耗时 s |', '|---|---:|---:|---:|---|---:|---:|']
    for r in rows:
        if r['split'] == 'holdout':
            reduction = f"{r['reduction_vs_v001_percent']:.2f}%" if r['status'] == 'ok' else '不可完整比较'
            lines.append(f"| {r['case']} | {r['cores']} | {r['v001_makespan']} | {r['v008_makespan']} | {r['selected_candidate']} | {reduction} | {r['total_wall_seconds']:.3f} |")
    lines += ['', '## 成本、失败和证据边界', '',
              f"- 实际候选尝试 {len(costs)} 次，成功 {sum(r['status'] == 'ok' for r in costs)} 次，失败/超时 {sum(r['status'] != 'ok' for r in costs)} 次；没有补跑或重试。",
              '- 每候选生成 30 秒、评估 180 秒；两候选按顺序运行。420 秒为分阶段子进程预算之和，归档和验证另有开销，不是严格总墙钟上限。',
              '- 新图按静态规模选出：此前未做性能观察的单连通图中，非 COPY 操作不超过 8000 的最小/最大图；不是随机样本，也未检验多分量回退路线。',
              '- 34 项测试通过，包括真实子进程超时及单/双候选失败的模拟边界。实际图中未出现故障不等于全部图不会超时。',
              '- 原始程序和输入哈希不变；源快照符合冻结记录；所有候选文件哈希、CSV/JSON 成绩、内存峰值与时间线、选择及复制文件均经审计。',
              '- 本轮没有重新计算单核参考；第一问全量 100 张图 × 2～5 核以及缺失的单核参考仍待完成。',
              '- 下一步固定 v009 进入全量分批评估，逐项保留超时和失败，补全单核参考后才能生成完整平均加速比。', '']
    (args.output / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    write_json(args.output / 'manifest.json', {'version': 'v009', 'utc': archive.stamp(), 'status': 'audited',
                'scope': scope, 'freeze_sha256': freeze_hash,
                'runs': {str(p.resolve()): digest(p / 'manifest.json') for p in args.runs},
                'invocation': [sys.executable, '-B', *sys.argv],
                'output_hashes': {p.name: digest(p) for p in args.output.iterdir() if p.is_file()}})
    print(scope)
    print(args.output)


if __name__ == '__main__':
    main()
