"""Audit matched v008 comparisons; preserve missing/failed configurations."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--comparators', required=True, type=Path, nargs='+')
    parser.add_argument('--freeze', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--split', choices=['development', 'holdout'], required=True)
    args = parser.parse_args()
    paths = [args.candidate, *args.comparators]
    manifests, rows, input_hashes = {}, {}, {}
    reference = read_json(args.candidate / 'manifest.json')
    expected = {(c, int(k)) for c in reference['cases'] for k in reference['cores']}
    freeze = read_json(args.freeze)
    for path in paths:
        manifest = read_json(path / 'manifest.json')
        version = manifest['algorithm_version']
        if version in manifests:
            raise ValueError('duplicate algorithm version')
        if manifest['protected_hashes_before'] != reference['protected_hashes_before'] or not manifest['protected_inputs_unchanged']:
            raise ValueError(f'protected input mismatch: {path}')
        for param in ['blocks_per_core', 'timeout', 'workers', 'cores']:
            if manifest['parameters'][param] != reference['parameters'][param]:
                raise ValueError(f'parameter mismatch: {param}')
        for source in ['baseline.py', 'component_scheduler.py', 'fork_preserving_scheduler.py', 'graph_analysis.py', 'region_scheduler.py']:
            target = path / 'source/src' / source
            recorded = next(v for k, v in freeze['source_hashes'].items() if k.replace('\\', '/') == 'src/' + source)
            if sha(target) != recorded:
                raise ValueError(f'frozen source mismatch: {target}')
        with (path / 'metrics/summary.csv').open(encoding='utf-8-sig', newline='') as stream:
            all_rows = list(csv.DictReader(stream))
        data = {(r['case'], int(r['cores'])): r for r in all_rows}
        if len(data) != len(all_rows) or set(data) != expected:
            raise ValueError('missing or duplicate configurations')
        for (case, cores), row in data.items():
            if row['split'] != args.split or int(row['candidate_count']) != 1:
                raise ValueError('incorrect scope or candidate budget')
            if row['status'] == 'ok':
                result = read_json(path / 'metrics' / f'{case}_n{cores}_result.json')
                if float(row['makespan']) != result['makespan'] or float(row['added_copy_bytes']) != result['data_movement_bytes']['added_copy_bytes']:
                    raise ValueError('CSV differs from evaluator result')
                for suffix in ['result.json', 'status.json']:
                    f = path / 'metrics' / f'{case}_n{cores}_{suffix}'
                    input_hashes[str(f.resolve())] = sha(f)
                f = path / 'plans' / f'{case}_n{cores}.json'
                input_hashes[str(f.resolve())] = sha(f)
        for f in [path / 'manifest.json', path / 'metrics/summary.csv']:
            input_hashes[str(f.resolve())] = sha(f)
        manifests[version], rows[version] = manifest, data
    candidate_version = reference['algorithm_version']
    comparisons, boundary_checks = [], []
    for key in sorted(expected):
        current = rows[candidate_version][key]
        stat_path = args.candidate / 'metrics' / f'{key[0]}_n{key[1]}_partition.json'
        stats = read_json(stat_path) if stat_path.exists() else {}
        if stats:
            input_hashes[str(stat_path.resolve())] = sha(stat_path)
        if stats.get('route') == 'regions' and current['status'] == 'ok':
            actual = float(current['scheduled_copy_bytes']) - float(current['spill_added_copy_bytes'])
            if actual != stats['final_boundary_bytes']:
                raise ValueError('boundary model differs from original evaluator')
            if 'v004' in rows and rows['v004'][key]['status'] == 'ok':
                old = rows['v004'][key]
                predicted = stats['initial_boundary_bytes'] - stats['final_boundary_bytes']
                actual_saved = float(old['partition_added_copy_bytes']) - float(current['partition_added_copy_bytes'])
                if predicted != actual_saved:
                    raise ValueError('predicted partition saving differs from original evaluator')
            boundary_checks.append({'case': key[0], 'cores': key[1], 'exact_bytes_match': True,
                                    'initial_tasks': stats['initial_tasks'], 'final_tasks': stats['final_tasks'],
                                    'initial_compute_span': stats['initial_compute_span'], 'final_compute_span': stats['final_compute_span'],
                                    'accepted_arms': len(stats['accepted_arms']), 'accepted_regions': len(stats['accepted_regions'])})
        for version, data in rows.items():
            if version == candidate_version:
                continue
            old = data[key]
            ok = current['status'] == old['status'] == 'ok'
            comparisons.append({'split': args.split, 'case': key[0], 'cores': key[1],
                                'candidate': candidate_version, 'comparator': version,
                                'candidate_status': current['status'], 'comparator_status': old['status'],
                                'candidate_cycles': current['makespan'], 'comparator_cycles': old['makespan'],
                                'reduction_pct': 100 * (1 - float(current['makespan']) / float(old['makespan'])) if ok else '',
                                'candidate_tasks': current['subgraphs'], 'comparator_tasks': old['subgraphs'],
                                'candidate_extra_bytes': current['added_copy_bytes'], 'comparator_extra_bytes': old['added_copy_bytes'],
                                'candidate_used_cores': current['used_cores'], 'comparator_used_cores': old['used_cores'],
                                'candidate_plan_seconds': current['plan_seconds'], 'comparator_plan_seconds': old['plan_seconds'],
                                'candidate_eval_seconds': current['evaluation_seconds'], 'comparator_eval_seconds': old['evaluation_seconds']})
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    lines = [f'# v008 {args.split} 对照', '', '相同原始评估器、输入、固定配置、倍率4、180秒预算、单进程；每配置各1个方案。无单核加速比或全量结论。', '',
             '| 比较对象 | 计划配置 | 快 | 平 | 慢 | 无完整成绩 |', '|---|---:|---:|---:|---:|---:|']
    counts = {}
    for version in rows:
        if version == candidate_version:
            continue
        subset = [r for r in comparisons if r['comparator'] == version]
        good = [r for r in subset if r['reduction_pct'] != '']
        counts[version] = {'faster': sum(r['reduction_pct'] > 0 for r in good), 'equal': sum(r['reduction_pct'] == 0 for r in good),
                           'slower': sum(r['reduction_pct'] < 0 for r in good), 'missing': len(subset) - len(good)}
        c = counts[version]
        lines.append(f"| {version} | {len(subset)} | {c['faster']} | {c['equal']} | {c['slower']} | {c['missing']} |")
    lines += ['', '| 用例 | 核数 | 对照 | 对照cycles | v008 cycles | 耗时减少% | 对照额外bytes | v008额外bytes |',
              '|---|---:|---|---:|---:|---:|---:|---:|']
    for r in comparisons:
        pct = f"{r['reduction_pct']:.2f}" if r['reduction_pct'] != '' else '缺失'
        lines.append(f"| {r['case']} | {r['cores']} | {r['comparator']} | {r['comparator_cycles']} | {r['candidate_cycles']} | {pct} | {r['comparator_extra_bytes']} | {r['candidate_extra_bytes']} |")
    lines += ['', f'张量边界字节模型与原始评估器逐配置精确一致：{len(boundary_checks)} 项（不含溢出搬运）。计算损失、等待与共享带宽时间仍是筛选代理，不能代替模拟。',
              '完整方案、源码快照、失败日志在各实验目录；输入及结果哈希见 manifest.json，细表见 comparison.csv。', '']
    (output / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    shutil.copy2(__file__, output / 'summarize_regions.py')
    audit = {'created_utc': datetime.now(timezone.utc).isoformat(), 'split': args.split, 'counts': counts,
             'runs': [str(p.resolve()) for p in paths], 'freeze_sha256': sha(args.freeze),
             'inputs_sha256': input_hashes, 'boundary_checks': boundary_checks,
             'summary_script_sha256': sha(Path(__file__)), 'comparison_sha256': sha(output / 'comparison.csv')}
    (output / 'manifest.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(counts, ensure_ascii=False))
    print(output)


if __name__ == '__main__':
    main()
