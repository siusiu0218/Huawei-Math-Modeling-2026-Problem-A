"""Audit and report the fixed Q2 v008 five-core experiment against v007."""
import csv
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def main():
    experiment = ROOT / 'outputs/09_problem2/raw/problem_2/v008/exp099_20260925_split_full5'
    manifest = json.loads((experiment / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['status'] == 'completed' and manifest['protected_unchanged']
    items = manifest['items']
    assert len(items) == 100 and all(r['status'] == 'success' and r['cores'] == 5 for r in items)
    assert {r['case'] for r in items} == {f'case_{i:03}' for i in range(1, 101)}
    selection = json.loads((ROOT / 'experiments/problem2_v008_selection.json').read_text(encoding='utf-8'))
    for filename, digest in selection['source_hashes'].items():
        assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == digest
        assert hashlib.sha256((experiment / 'source' / filename).read_bytes()).hexdigest() == digest
    for filename, digest in manifest['output_hashes'].items():
        assert hashlib.sha256((experiment / filename).read_bytes()).hexdigest() == digest
    original = list(csv.DictReader((ROOT / 'outputs/09_problem2/full_summary_20260925/all_results.csv').open(encoding='utf-8-sig')))
    base = {r['case']: r for r in original if r['version'] == 'v007' and r['cores'] == '5'}
    single_rows = {r['case']: r for r in original if r['cores'] == '1'}
    single = {c: int(r['makespan']) for c, r in single_rows.items()}
    result = []
    for row in items:
        case = row['case']
        old = base[case]
        prior = int(old['makespan'])
        current = row['makespan']
        # Confirm the denominator's graph/config have the same hashes.
        expected = manifest['protected_hashes_before']
        old_manifest = json.loads((ROOT / old['result']).parents[1].joinpath('manifest.json').read_text(encoding='utf-8'))
        single_manifest = json.loads((ROOT / single_rows[case]['result']).parents[1].joinpath('manifest.json').read_text(encoding='utf-8'))
        for key in (f'data/{case}.json', 'data/config.txt'):
            get = lambda d: {k.replace('\\', '/'): v for k, v in d.items()}[key]
            assert get(expected) == get(old_manifest['protected_hashes_before'])
            assert get(expected) == get(single_manifest['protected_hashes_before'])
        d = json.loads((experiment / 'metrics' / f'{case}_n5.json').read_text(encoding='utf-8'))
        assert d['makespan'] == current
        result.append({'case': case, 'cores': 5, 'v007_makespan': prior, 'v008_makespan': current,
                       'single_makespan': single[case], 'v007_speedup': single[case] / prior,
                       'v008_speedup': single[case] / current,
                       'time_reduction_pct': 100 * (1 - current / prior),
                       'outcome': 'faster' if current < prior else 'slower' if current > prior else 'equal',
                       'v007_added_copy_bytes': int(old['added_copy_bytes']),
                       'v008_added_copy_bytes': d['data_movement_bytes']['added_copy_bytes'],
                       'v007_spill_bytes': int(old['spill_added_copy_bytes']),
                       'v008_spill_bytes': d['data_movement_bytes']['spill_added_copy_bytes'],
                       'generation_seconds': row['generate']['seconds'],
                       'evaluation_seconds': row['evaluate']['seconds']})
    means = {v: float(sum(Fraction(r['single_makespan'], r[f'{v}_makespan']) for r in result) / 100)
             for v in ('v007', 'v008')}
    counts = {k: sum(r['outcome'] == k for r in result) for k in ('faster', 'equal', 'slower')}
    out = ROOT / 'outputs/09_problem2/v008_summary_20260925'
    out.mkdir(exist_ok=True)
    with (out / 'comparison_5cores.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(result[0])); writer.writeheader(); writer.writerows(result)
    audit = {'problem': 2, 'version': 'v008', 'count': 100, 'cores': 5, 'means': means,
             'outcomes': counts, 'output_hashes_verified': True, 'frozen_source_verified': True,
             'input_config_comparison_verified': True, 'protected_unchanged': True,
             'generation_seconds': sum(r['generation_seconds'] for r in result),
             'evaluation_seconds': sum(r['evaluation_seconds'] for r in result),
             'tests_passed': 54, 'candidates_per_configuration': 1,
             'additional_development_evaluations': 26,
             'limitation': 'Five-core full coverage only; lower-core new-version coverage is 5 graphs x 3 core counts. All old graph scores have been seen.'}
    (out / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    lines = ['# 第二问 v008：大连通块拆分优化', '',
             '## 验证范围', '',
             '五核全部 100 张图（exp099）完成，使用原始评估器与固定配置。每配置一个候选，生成/评估预算 30/180 秒。',
             '此前开发 exp096/097 共 6 项成功；exp098 五图 × 2～5 核共 20 项成功。exp096 写入清单遭遇 Windows 文件锁后中断，三个成功结果保留，剩余三个控制配置另立 exp097；未重跑已成功项。',
             '**本轮尚未覆盖全部 100 图的 2～4 核，不替换旧版完整 400 项交付。** 所有图的旧版成绩已见，本轮检验不属于未见数据验证。', '',
             '## 五核全量实测', '', '| 指标 | v007 | v008 |', '|---|---:|---:|',
             f"| 逐图加速比算术平均 | {means['v007']:.6f} | {means['v008']:.6f} |",
             f"| 中位数 | {statistics.median(r['v007_speedup'] for r in result):.6f} | {statistics.median(r['v008_speedup'] for r in result):.6f} |", '',
             f"相对 v007：{counts['faster']} 快、{counts['equal']} 平、{counts['slower']} 慢。", '',
             '## 逐图变化（包含所有改善和退步）', '',
             '| 图 | v007 加速比 | v008 加速比 | 耗时下降 % |', '|---|---:|---:|---:|']
    for r in sorted(result, key=lambda r: r['time_reduction_pct'], reverse=True):
        if r['outcome'] != 'equal':
            lines.append(f"| {r['case']} | {r['v007_speedup']:.4f} | {r['v008_speedup']:.4f} | {r['time_reduction_pct']:.2f} |")
    lines += ['', '## 方法、成本与限制', '',
              '当最大连通块计算权重超过全图平均每核权重的 1.25 倍时，允许链/区域切分，再按关键路径调度；其余配置沿用 v007。规则不使用用例编号。',
              '这是计算代理指导的启发式；真实共享带宽和内存容量仍由原始评估器执行。未解决所有通信开销和交错引发的溢出。',
              f"exp099 生成累计 {audit['generation_seconds']:.3f} 秒，评估累计 {audit['evaluation_seconds']:.3f} 秒；这不包含之前 26 次开发/检查的额外成本。完整耗时见各 manifest。", '',
              '输入/配置与基线哈希一致，原始材料未变，全部输出归档哈希和冻结源文件已核对。均值使用 Fraction 逐图比值复算。54 项测试通过。', '',
              '结果表：comparison_5cores.csv；核对记录：audit.json。复现：', '', '```powershell',
              "$cases = 1..100 | ForEach-Object { 'case_{0:D3}' -f $_ }",
              'python -B experiments/run_problem2.py --algorithm split_components --experiment expNEW_split_full5 --cases $cases --cores 5', '```', '',
              '必须使用新的实验编号，已有目录拒绝覆盖。下一步根据全量退步分析再决定改法，或保持 v008 冻结补全 2～4 核。']
    (out / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
