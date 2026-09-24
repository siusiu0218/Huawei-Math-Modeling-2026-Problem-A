"""Run a pre-frozen v009 selection; keep both successful and failed candidates."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

import run_baseline as archive
from portfolio_scheduler import CANDIDATES, VERSION, solve_configuration, digest, read_json, write_json


def validate_freeze(freeze, source, split):
    if freeze['version'] != VERSION or freeze['policy']['candidates'] != list(CANDIDATES):
        raise ValueError('unsupported portfolio version or candidate order')
    policy = freeze['policy']
    if policy != {'candidates': list(CANDIDATES), 'blocks_per_core': 4,
                  'plan_timeout_seconds': 30, 'evaluation_timeout_seconds': 180,
                  'workers': 1, 'tie_break': 'v001', 'retries': 0}:
        raise ValueError('policy differs from fixed v009 policy')
    for relative, expected in freeze['source_hashes'].items():
        if digest(source / relative) != expected:
            raise ValueError(f'frozen source changed: {relative}')
    if archive.protected_hashes() != freeze['protected_hashes']:
        raise ValueError('protected inputs differ from freeze')
    selected = freeze['splits'][split]
    cores = freeze['cores'][split]
    if not cores or len(cores) != len(set(cores)) or any(type(k) is not int or k not in range(2, 6) for k in cores):
        raise ValueError('cores must be unique integers in 2..5')
    if not selected or len({r['case'] for r in selected}) != len(selected):
        raise ValueError('selection must be nonempty and unique')
    for item in selected:
        if digest(archive.A_ROOT / 'data' / f"{item['case']}.json") != item['graph_sha256']:
            raise ValueError('graph differs from freeze')
    if set(r['case'] for r in freeze['splits']['holdout']) & set(freeze['excluded_seen_cases']):
        raise ValueError('holdout overlaps seen cases')
    return selected


def report(exp, rows, candidates):
    complete = [r for r in rows if r['status'] == 'ok']
    wins = Counter(r['selected_candidate'] for r in complete)
    faster = sum(r['makespan'] < r['v001_makespan'] for r in complete)
    lines = ['# v009 固定双候选试验', '', f'实验：`{exp.name}`；配置 {len(rows)} 项；候选评估 {len(candidates)} 项。', '',
             f'两个候选均成功：{len(complete)} 项；单候选可用：{sum(r["status"] == "degraded" for r in rows)} 项；无可用候选：{sum(r["status"] == "failed" for r in rows)} 项。', '',
             f'完整配置选择 v001：{wins["v001"]} 项，v008：{wins["v008"]} 项；相对本次同预算 v001 更快：{faster} 项，其余完整配置持平。', '',
             '每配置依次生成并评估 v001、v008，固定每核块数倍率 4。各候选生成最多 30 秒、评估最多 180 秒，无重试；分阶段子进程预算共 420 秒，进程清理、验证及归档开销另计。', '',
             '相对 v001 的不退步来自多评估一个候选后取较小值，不是单一启发式的独立改进证据。评估调用是算法搜索成本的一部分，不能与只评估一次的 v001 宣称等预算。', '',
             '| 用例 | 核数 | v001 cycles | v008 cycles | 选择 | 状态 | 总耗时 s |',
             '|---|---:|---:|---:|---|---|---:|']
    for r in rows:
        lines.append(f"| {r['case']} | {r['cores']} | {r['v001_makespan']} | {r['v008_makespan']} | {r['selected_candidate']} | {r['status']} | {r['total_wall_seconds']:.3f} |")
    lines += ['', f"方案生成子进程合计 {sum(r['plan_seconds'] for r in rows):.3f} 秒；评估子进程合计 {sum(r['evaluation_seconds'] for r in rows):.3f} 秒；配置总耗时 {sum(r['total_wall_seconds'] for r in rows):.3f} 秒。", '',
              '所有候选（包括未选中、失败或超时）保留在 candidates/。选中方案和结果逐字节复制，哈希保存在 metrics/summary.csv。', '',
              '本次为限定样本的流程检验；不代表全部 100 张图、400 个多核配置或第一问已经完成。未计算新的单核参考，不报告平均单核加速比。', '', '## 失败和超时', '']
    lines += [f"- {r['case']} n{r['cores']} {r['candidate']}: {r['status']} / {r['failure_phase']} / {r['error']}" for r in candidates if r['status'] != 'ok'] or ['- 无。']
    (exp / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--split', choices=('development', 'holdout'), required=True)
    args = parser.parse_args()
    if not args.experiment or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in args.experiment):
        parser.error('invalid experiment name')
    freeze_path = args.freeze.resolve()
    freeze = read_json(freeze_path)
    selected = validate_freeze(freeze, archive.SOURCE, args.split)
    # Archive helper snapshots source/data without altering any frozen algorithm.
    archive.VERSION = VERSION
    args.freeze = str(freeze_path)
    args.mode = 'fixed_portfolio'
    exp, manifest = archive.prepare(args)
    write_json(exp / 'selection.json', freeze)
    started = time.perf_counter()
    rows, candidates = [], []
    manifest.update(policy=freeze['policy'], selection_sha256=digest(freeze_path),
                    cases=[r['case'] for r in selected], cores=freeze['cores'][args.split],
                    planned_configurations=len(selected) * len(freeze['cores'][args.split]),
                    reproduce_note='Run source/experiments/run_portfolio.py --freeze selection.json --split SAME_SPLIT --experiment NEW_NAME from this experiment directory; source/input hashes must match.')
    write_json(exp / 'manifest.json', manifest)
    try:
        for item in selected:
            for cores in freeze['cores'][args.split]:
                row, outcomes = solve_configuration(exp, item['case'], args.split, cores,
                                                    freeze['policy'], exp / 'source/src/portfolio_scheduler.py')
                rows.append(row)
                candidates.extend({'problem': 1, 'algorithm_version': VERSION, 'experiment': exp.name,
                                   'case': item['case'], 'split': args.split, 'cores': cores, **r} for r in outcomes)
                archive.write_csv(exp / 'metrics/summary.csv', rows)
                archive.write_csv(exp / 'metrics/candidates.csv', candidates)
                print(f"{len(rows)}/{manifest['planned_configurations']} {item['case']} n{cores}: {row['status']}, selected {row['selected_candidate']}", flush=True)
        report(exp, rows, candidates)
        manifest['status'] = 'completed' if all(r['status'] == 'ok' for r in rows) else 'completed_with_failures'
    except BaseException as exc:
        manifest.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                        error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        manifest.update(ended_utc=archive.stamp(), elapsed_seconds=time.perf_counter() - started,
                        configuration_status_counts=dict(Counter(r['status'] for r in rows)),
                        candidate_status_counts=dict(Counter(r['status'] for r in candidates)),
                        completed_configurations=len(rows), candidate_count=len(candidates),
                        protected_inputs_unchanged=archive.protected_hashes() == manifest['protected_hashes_before'])
        if not manifest['protected_inputs_unchanged']:
            manifest['status'] = 'invalid_inputs_changed'
        manifest['artifact_hashes'] = {str(p.relative_to(exp)): digest(p)
                                       for folder in ('candidates', 'plans', 'metrics', 'logs')
                                       for p in sorted((exp / folder).rglob('*')) if p.is_file()}
        write_json(exp / 'manifest.json', manifest)
        archive.register(exp, args.mode, manifest['status'])
    return 0 if manifest['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
