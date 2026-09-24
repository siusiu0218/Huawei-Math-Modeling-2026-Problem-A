"""Combine the already-audited development/holdout summaries without pooling claims."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

S = Path(__file__).resolve().parents[1]
R = S / 'outputs/06_regions/raw/problem_1/v008'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    freeze_path = S / 'experiments/v008_selection.json'
    holdout_path = S / 'experiments/v008_holdout_selection.json'
    freeze, selection = read(freeze_path), read(holdout_path)
    for name, digest in freeze['source_hashes'].items():
        assert sha(S / name) == digest, name
    assert not ({x['case'] for x in selection['selected']} & set(selection['excluded_seen_cases']))
    phases, combined, inputs, manifests, structures = {}, [], {}, [], []
    for split in ['development', 'holdout']:
        summary = R / f'{split}_summary_20260924'
        audit = read(summary / 'manifest.json')
        assert sha(summary / 'comparison.csv') == audit['comparison_sha256']
        for name, digest in audit['inputs_sha256'].items():
            assert sha(Path(name)) == digest, name
        with (summary / 'comparison.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        phases[split] = audit['counts']
        combined.extend(rows)
        structures.extend({'split': split, **x} for x in audit['boundary_checks'])
        for p in [summary / 'manifest.json', summary / 'comparison.csv']:
            inputs[str(p.relative_to(S))] = sha(p)
        for run in audit['runs']:
            manifest = read(Path(run) / 'manifest.json')
            assert manifest['status'] == 'completed'
            assert manifest['job_status_counts'] == {'ok': 8, 'failed': 0, 'timeout': 0}
            assert manifest['protected_inputs_unchanged']
            assert datetime.fromisoformat(manifest['started_utc']) > datetime.fromisoformat(freeze['utc'])
            if split == 'holdout':
                assert datetime.fromisoformat(manifest['started_utc']) > datetime.fromisoformat(selection['utc'])
            manifests.append(manifest)
    assert all(m['protected_hashes_before'] == manifests[0]['protected_hashes_before'] for m in manifests)
    assert len(structures) == 16 and all(x['exact_bytes_match'] for x in structures)
    output = R / 'summary_20260924'
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'comparison.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(combined[0]))
        writer.writeheader()
        writer.writerows(combined)
    lines = ['# v008：短分叉与汇合合并的验证结果', '',
             '结论：保留v008为候选。开发8项、新检验8项均快于v004，Task数和额外搬运均减少；与v001相比仍有5项退步，不能统一替代简单切分。第一问尚未全量完成。', '',
             '## 比较范围与结果', '',
             '开发：已看过成绩的case_016/069；新检验：case_071/075，按此前未测、单连通、非COPY操作不超过8000的最小/最大规模选择。新检验不是随机代表样本。',
             '每张图2–5核，v008/v004/v001各1个完整方案，均用相同原始评估器及固定配置，180秒预算、单进程。六个实验exp022–027共48次原始评估全部成功，无超时或重试。', '',
             '| 集合 | 配置数 | 相对v004快/平/慢 | 相对v001快/平/慢 |', '|---|---:|---|---|']
    for split in ['development', 'holdout']:
        a, b = phases[split]['v004'], phases[split]['v001']
        lines.append(f"| {split} | 8 | {a['faster']}/{a['equal']}/{a['slower']} | {b['faster']}/{b['equal']}/{b['slower']} |")
    lines += ['', '## 四核代表结果', '',
              '| 用例 | 集合 | v004 cycles | v008 cycles | 减少% | Task数 v004→v008 | 额外bytes v004→v008 |',
              '|---|---|---:|---:|---:|---|---|']
    for row in combined:
        if row['cores'] == '4' and row['comparator'] == 'v004':
            lines.append(f"| {row['case']} | {row['split']} | {int(float(row['comparator_cycles'])):,} | {int(float(row['candidate_cycles'])):,} | {float(row['reduction_pct']):.2f} | {row['comparator_tasks']} → {row['candidate_tasks']} | {int(float(row['comparator_extra_bytes'])):,} → {int(float(row['candidate_extra_bytes'])):,} |")
    lines += ['', 'case_016四核的计算路径代理655,140→682,895 cycles，仍保留主并行结构；额外搬运仅减少12,200 bytes，重复输入搬运仍是未解决成本。case_075为182,300→187,400 cycles。小图允许更多计算串行化以减少Task开销，因此路径增长不能单独当作失败或收益判断。', '',
              '## 相对v001的全部负结果', '',
              '| 集合 | 用例/核数 | v001 cycles | v008 cycles | 耗时增加% |', '|---|---|---:|---:|---:|']
    for row in combined:
        if row['comparator'] == 'v001' and float(row['reduction_pct']) < 0:
            lines.append(f"| {row['split']} | {row['case']} n{row['cores']} | {row['comparator_cycles']} | {row['candidate_cycles']} | {-float(row['reduction_pct']):.2f} |")
    times = [float(r['candidate_plan_seconds']) for r in combined if r['comparator'] == 'v004']
    lines += ['', '## 实现与核对', '',
              '- 从v004分区出发，按当前Task的生产/消费张量集合计算合并前后边界差值。连续合并不会丢失被吸收操作的输出，共享输入/外部消费者/原有COPY_OUT均被计入。',
              '- 安全依赖边只在“源唯一后继或目标唯一前驱”时合并；计算路径损失按方向取源或目标的工作量，避免旧规则用较小端点误吸收长计算分支。另实现有边界的闭合区域搜索。',
              '- 16个v008配置的边界搬运总量及相对v004的差值与原始评估器逐项精确一致；这不包含溢出预测。48次评估均通过原始方案及运行检查，受保护输入哈希前后一致。',
              '- 26项测试通过，含手算搬运、共享张量、连续合并、长/短分支、汇合树、外部入口、随机DAG。未重跑400项全图方案检查，不继承v003的400项通过声明。',
              f'- 16个候选方案的生成时间为{min(times):.3f}–{max(times):.3f}秒，每配置只评估一个完整方案。静态合并尝试并非额外模拟候选；详细计数保存在各metrics/*_partition.json。',
              '- 新检验前冻结的代码与参数未按新检验成绩修改。原始材料、旧算法与旧实验未改；本轮文件在当前worktree，源工作区未写入。', '',
              '## 解释边界与下一步', '',
              '局部等待收益和字节/带宽时间仅为筛选代理，可能与其他等待、计算重叠；内存溢出和共享带宽争用由原始评估器处理。比较包含合并后重新调度的整体效果，没有独立识别每一项收益来源，也不证明最优切分。',
              '当前可推进不依赖用例编号的方法选择：在小图上比较v001与v008的适用条件，固定规则或双候选预算后再安排新的检验。case_016重复输入搬运仍需独立研究。本轮四张图已全部看过性能，后续不能继续称作未见检验。',
              '100图性能、case_014正式单核参考及第二/三问仍未完成，当前不报告完整平均单核加速比。', '',
              '历史更正：case_048 n4的v005保存方案与v004重生成方案完全相同，1728个操作得到1245个Task；上轮“未合并任何链边”应改为“未得到区别于v004的方案”。证据及规则见experiments/v008_DESIGN.md。', '',
              '详细逐配置结果：comparison.csv。开发及新检验分别见上级development_summary_20260924、holdout_summary_20260924。冻结决策、哈希及验证范围见manifest.json。', '']
    (output / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    for p in [freeze_path, holdout_path, S / 'experiments/v008_DESIGN.md']:
        inputs[str(p.relative_to(S))] = sha(p)
    shutil.copy2(__file__, output / 'report_v008.py')
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'phase_counts': phases,
                'successful_evaluator_runs': 48, 'candidate_configurations': 16,
                'tests_passed': 26, 'boundary_checks': structures, 'input_hashes': inputs,
                'script_sha256': sha(Path(__file__)), 'comparison_sha256': sha(output / 'comparison.csv'),
                'report_sha256': sha(output / 'REPORT.md')}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(output / 'REPORT.md')
    print(json.dumps(phases, ensure_ascii=False))


if __name__ == '__main__':
    main()
