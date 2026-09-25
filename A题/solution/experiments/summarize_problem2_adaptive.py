"""Audit Q2 v009 coverage, frozen sources, protected inputs and all outcomes."""
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
from collections import Counter
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/09_problem2/raw/problem_2/v009'
EXPERIMENTS = ['exp102_20260925_adaptive_full_a', 'exp103_20260925_adaptive_full_b']
OUT = ROOT / 'outputs/09_problem2/v009_summary_20260925'


def normalized(values):
    return {key.replace('\\', '/'): value for key, value in values.items()}


def main():
    old = list(csv.DictReader((ROOT / 'outputs/09_problem2/full_summary_20260925/all_results.csv').open(encoding='utf-8-sig')))
    reference = {(r['case'], int(r['cores'])): r for r in old if r['version'] == 'v007'}
    single_rows = {r['case']: r for r in old if r['cores'] == '1'}
    single = {c: int(r['makespan']) for c, r in single_rows.items()}
    frozen = json.loads((ROOT / 'experiments/problem2_v009_selection.json').read_text(encoding='utf-8'))
    rows, plans, selections, hashes, failures = [], [], Counter(), {}, []
    attempts = []
    recovery_path = ROOT / 'experiments/problem2_v009_recovery.json'
    recovery = json.loads(recovery_path.read_text(encoding='utf-8')) if recovery_path.exists() else {'experiments': []}
    old_manifests = {}
    for name in EXPERIMENTS + recovery['experiments']:
        folder = BASE / name
        m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        assert m['status'] in ('completed', 'partial', 'paused_by_user') and m['protected_unchanged']
        for path, expected in frozen['source_hashes'].items():
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
            assert hashlib.sha256((folder / 'source' / path).read_bytes()).hexdigest() == expected
        for path, expected in m['source_hashes'].items():
            assert hashlib.sha256((folder / 'source' / path).read_bytes()).hexdigest() == expected
        for path, expected in m.get('output_hashes', m.get('output_hashes_at_pause', {})).items():
            assert hashlib.sha256((folder / path).read_bytes()).hexdigest() == expected
        for path, expected in normalized(m['protected_hashes_before']).items():
            assert hashlib.sha256((ROOT.parent / path).read_bytes()).hexdigest() == expected
        for r in m['items']:
            case, n = r['case'], r['cores']; key = (case, n)
            if key in hashes:
                assert name in recovery['experiments'] and key not in {(x['case'], x['cores']) for x in rows}
            hashes[key] = name
            attempts.append(r)
            if r['status'] != 'success':
                failures.append(r)
                continue
            old_row = reference[key]
            for archived_row in (old_row, single_rows[case]):
                mf = (ROOT / archived_row['result']).parents[1] / 'manifest.json'
                if mf not in old_manifests:
                    old_manifests[mf] = json.loads(mf.read_text(encoding='utf-8'))
                for path in (f'data/{case}.json', 'data/config.txt'):
                    assert normalized(m['protected_hashes_before'])[path] == normalized(old_manifests[mf]['protected_hashes_before'])[path]
            d = json.loads((folder / 'metrics' / f'{case}_n{n}.json').read_text(encoding='utf-8'))
            selected = json.loads((folder / 'plans' / f'{case}_n{n}.selection.json').read_text(encoding='utf-8'))
            assert len(selected['candidates']) <= 4
            assert d['makespan'] == r['makespan']
            base = int(old_row['makespan']); current = r['makespan']
            row = {'case': case, 'cores': n, 'v007_makespan': base, 'v009_makespan': current,
                   'single_makespan': single[case], 'v007_speedup': single[case] / base,
                   'v009_speedup': single[case] / current,
                   'time_reduction_pct': 100 * (1 - current / base),
                   'outcome': 'faster' if current < base else 'slower' if current > base else 'equal',
                   'selected': selected['selected'], 'local_preparations': selected['local_preparations'],
                   'local_failures': sum(x['status'] != 'success' for x in selected['candidates']),
                   'v007_added_copy_bytes': int(old_row['added_copy_bytes']),
                   'v009_added_copy_bytes': d['data_movement_bytes']['added_copy_bytes'],
                   'v009_spill_bytes': d['data_movement_bytes']['spill_added_copy_bytes'],
                   'generation_seconds': r['generate']['seconds'], 'evaluation_seconds': r['evaluate']['seconds'],
                   'generation_reused_from': r['generate'].get('reused_from', ''),
                   'plan': str((folder / 'plans' / f'{case}_n{n}.json').relative_to(ROOT)),
                   'result': str((folder / 'metrics' / f'{case}_n{n}.json').relative_to(ROOT))}
            selections[selected['selected']] += 1
            rows.append(row); plans.append(folder / 'plans' / f'{case}_n{n}.json')
    assert set(hashes) == {(f'case_{i:03}', n) for i in range(1, 101) for n in range(2, 6)}
    OUT.mkdir(exist_ok=True)
    (OUT / 'failures.json').write_text(json.dumps(failures, indent=2) + '\n', encoding='utf-8')
    (OUT / 'attempts.json').write_text(json.dumps(attempts, indent=2) + '\n', encoding='utf-8')
    if len(rows) != 400:
        raise RuntimeError(f'{400-len(rows)} unresolved configurations; failures retained; no complete-suite mean published')
    rows.sort(key=lambda r: (r['case'], r['cores']))
    with (OUT / 'comparison.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    means = []
    for n in range(2, 6):
        group = [r for r in rows if r['cores'] == n]
        means.append({'cores': n, 'count': len(group), **{v: float(sum(Fraction(r['single_makespan'], r[f'{v}_makespan']) for r in group) / 100) for v in ('v007', 'v009')},
                      **{k: sum(r['outcome'] == k for r in group) for k in ('faster', 'equal', 'slower')}})
    with (OUT / 'mean_speedup.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(means[0])); writer.writeheader(); writer.writerows(means)
    with zipfile.ZipFile(OUT / 'v009_plans.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for plan in plans:
            z.write(plan, plan.name)
    with zipfile.ZipFile(OUT / 'v009_plans.zip') as z:
        assert len(z.namelist()) == 400
        for p in plans:
            assert hashlib.sha256(z.read(p.name)).digest() == hashlib.sha256(p.read_bytes()).digest()
    timeouts = sum(r['status'] == 'generate_timeout' for r in failures)
    pauses = sum(r['status'] == 'paused_by_user' for r in failures)
    audit = {'problem': 2, 'version': 'v009', 'coverage': 400, 'unresolved_failures': 0,
             'generation_timeouts': timeouts, 'user_paused_evaluations': pauses,
             'cost_is_lower_bound': bool(pauses), 'incomplete_attempts': len(failures), 'total_attempts': len(attempts), 'means': means,
             'selections': dict(selections), 'local_preparations': sum(r['local_preparations'] for r in rows),
             'local_preparations_scope': 'Final 400 successful configurations only; incomplete generation preparation counts are unknown.',
             'local_candidate_failures': sum(r['local_failures'] for r in rows),
             'generation_seconds': sum(r.get('generate', {}).get('seconds', 0) for r in attempts),
             'evaluation_seconds': sum(r.get('evaluate', {}).get('seconds', 0) for r in attempts),
             'originals_hashes_verified': True, 'frozen_and_archived_source_verified': True,
             'baseline_denominator_hashes_verified': True, 'zip_and_outputs_verified': True,
             'tests_passed': 60, 'max_parallel_workers': 2, 'max_candidates_per_config': 4,
             'generation_timeout_initial': 60, 'generation_timeout_recovery': 300 if recovery['experiments'] else None, 'evaluation_timeout': 180}
    audit['posthoc_two_method_five_core_mean_not_official'] = float(sum(
        Fraction(r['single_makespan'], min(r['v007_makespan'], r['v009_makespan']))
        for r in rows if r['cores'] == 5) / 100)
    (OUT / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    text = ['# 第二问 v009 全量优化结果', '', '## 结果', '',
            f"全部 100 图 × 2～5 核取得 400 项成功结果；保留 {timeouts} 次生成超时及 {pauses} 次用户暂停记录，续跑/补测后完成。原始评估器、固定配置和原单核参考保持一致。加速比为 100 个逐图比值的算术平均，用有理数复算。", '',
            '| 核数 | v007 平均加速比 | v009 平均加速比 | 快 / 平 / 慢 |', '|---|---:|---:|---|']
    for r in means:
        text.append(f"| {r['cores']} | {r['v007']:.6f} | {r['v009']:.6f} | {r['faster']} / {r['equal']} / {r['slower']} |")
    v8 = json.loads((ROOT / 'outputs/09_problem2/v008_summary_20260925/audit.json').read_text(encoding='utf-8'))
    text += ['', f"上一轮 v008 仅五核全量，均值 {v8['means']['v008']:.6f}；本轮五核为 {means[-1]['v009']:.6f}。", '',
             '## 方法与成本', '',
             '单连通图保留原区域方案；多连通图比较不交错、两路交错，以及大块拆分或四/八路交错。最多四个候选，经原始核内准备流程取得核内排布和搬运量；以最大核内耗时 + 总搬运字节/带宽选择，最后执行一次完整场景 B 评估。',
             '**这是代理分数筛选，不是全局 Makespan 最优选择，不能保证每张图改善。**',
             f"400 个最终成功配置的选择记录包含 {audit['local_preparations']} 次核内候选准备，内部失败 {audit['local_candidate_failures']} 次；超时生成中的未落盘准备次数未知。成功完整评估 400 次，另有 {pauses} 次评估被用户中断。生成阶段（含筛选和超时）已记录 {audit['generation_seconds']:.3f} 秒；全局评估已记录 {audit['evaluation_seconds']:.3f} 秒。中断阶段耗时未知，因此总求解成本只报下界。",
             f"首轮和正常续跑使用两个工作进程，单配置生成预算 60 秒、全局评估预算 180 秒。{timeouts} 项超时另立恢复实验，生成预算放宽至 300 秒、顺序执行；所有已记录失败时间计入成本。两项已生成方案直接复用，其生成成本计于旧清单，不重复计算。耗时受并发资源竞争影响；相对旧版单候选不是等搜索预算比较。开发/检查另有 exp100 六项与 exp101 二十四项，费用未计入上述成本。", '',
             '## 退步（按耗时增幅排序，最多列前 20 项）', '',
             '| 图 | 核数 | v007 周期 | v009 周期 | 耗时增加 % |', '|---|---:|---:|---:|---:|']
    for r in sorted((r for r in rows if r['outcome'] == 'slower'), key=lambda r: r['time_reduction_pct'])[:20]:
        text.append(f"| {r['case']} | {r['cores']} | {r['v007_makespan']} | {r['v009_makespan']} | {-r['time_reduction_pct']:.2f} |")
    text += ['', '所有 400 项均在 comparison.csv，包含改善、持平、退步、搬运量、求解耗时和原始路径。', '',
             '## 下一步的诊断线索（不是新算法成绩）', '',
             f"若事后逐图取 v007/v009 两个已知结果中更快者，五核均值为 {audit['posthoc_two_method_five_core_mean_not_official']:.6f}。这只说明现有两套方案的选择损失；本轮未实现或验证新的双候选全局择优算法，不能将该数替换正式的 v009 均值。真正采用双候选评估还需披露增加的全局评估成本。", '',
             '## 证据边界与复现', '',
             '此前已经看过全部图的旧成绩，因此本轮是已知题库上的优化，不能称为未见数据泛化验证。60 项测试通过；原始材料、输入/配置/单核参考、冻结源码、归档输出、ZIP 逐文件哈希均已核对。',
             '冻结记录：experiments/problem2_v009_selection.json；恢复预算与实验清单：experiments/problem2_v009_recovery.json；源代码：src/scene_b_adaptive.py；首轮实验：exp102/103。运行入口：experiments/run_problem2_adaptive_full.py（已有目录拒绝覆盖）。逐配置可用 run_problem2.py --algorithm adaptive --generation-timeout 60；已超时项的恢复预算为 300 秒，每次使用新的实验编号。',
             '原 v007/v008 结果保留。本报告没有删除失败或按用例编号选择方案。']
    (OUT / 'REPORT.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
    shutil.copy2(__file__, OUT / Path(__file__).name)
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
