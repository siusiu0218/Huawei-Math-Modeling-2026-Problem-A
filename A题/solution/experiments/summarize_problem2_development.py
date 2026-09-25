"""Audit fixed scene-B development runs and summarize all selected cases."""
import hashlib
import json
from pathlib import Path

SOLUTION = Path(__file__).resolve().parents[1]
BASE = SOLUTION / 'outputs/09_problem2/raw/problem_2'
RUNS = {
    'baseline': BASE / 'v003/exp058_20260925_development_baseline',
    'regions': BASE / 'v002/exp059_20260925_development_regions',
    'single': BASE / 'single_v001/exp060_20260925_development_single',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    selection = read(BASE / 'design_v001/exp057_20260925_static_selection/selection.json')
    cases = [r['case'] for r in selection['selected'] if r['split'] == 'development']
    runs, manifests = {}, {}
    reference_inputs = None
    for name, folder in RUNS.items():
        manifest = read(folder / 'manifest.json')
        assert manifest['status'] in ('completed', 'partial'), manifest['status']
        assert manifest['protected_unchanged']
        inputs = {k: v for k, v in manifest['protected_hashes_before'].items() if k.startswith(('data', 'code'))}
        if reference_inputs is None:
            reference_inputs = inputs
        else:
            assert inputs == reference_inputs, 'materials differ between methods'
        for path, expected in manifest['output_hashes'].items():
            assert hashlib.sha256((folder / path).read_bytes()).hexdigest() == expected, path
        expected_keys = {(case, n) for case in cases for n in ([1] if name == 'single' else [2,3,4,5])}
        rows = {(r['case'], r['cores']): r for r in manifest['items']}
        assert len(rows) == len(manifest['items']) and set(rows) == expected_keys
        runs[name], manifests[name] = rows, manifest
    output = SOLUTION / 'outputs/09_problem2/开发集基线.md'
    if output.exists():
        raise FileExistsError(output)
    lines = ['# 第二问开发集基线', '',
             '范围：冻结选择的 4 张开发图 × 2～5 核；每方法每配置一个候选。新检验图尚未评估。', '',
             '| 图 | 核数 | 简单切分 | 区域切分 | 区域相对简单 | 区域相对单核加速比 | 区域跨核传输数 |',
             '|---|---:|---:|---:|---|---:|---:|']
    comparisons = {'faster': 0, 'equal': 0, 'slower': 0, 'unavailable': 0}
    details = []
    for case in cases:
        single = runs['single'][(case, 1)]
        for n in (2,3,4,5):
            a, b = runs['baseline'][(case,n)], runs['regions'][(case,n)]
            comparable = a['status'] == b['status'] == 'success'
            change = ('faster' if b['makespan'] < a['makespan'] else
                      'slower' if b['makespan'] > a['makespan'] else 'equal') if comparable else 'unavailable'
            comparisons[change] += 1
            speedup = single['makespan']/b['makespan'] if single['status'] == b['status'] == 'success' else None
            transfer_count, extra = None, None
            if b['status'] == 'success':
                result = read(RUNS['regions'] / 'metrics' / f'{case}_n{n}.json')
                transfer_count = len(result['cross_core_transfers'])
                extra = result['data_movement_bytes']
            speedup_text = f'{speedup:.4f}' if speedup is not None else '不可计算'
            lines.append(f"| {case} | {n} | {a.get('makespan', a['status'])} | {b.get('makespan', b['status'])} | {change} | {speedup_text} | {transfer_count} |")
            details.append({'case':case, 'cores':n, 'comparison':change,
                            'regions_speedup':speedup, 'regions_transfers':transfer_count,
                            'regions_data_movement_bytes':extra})
    lines += ['', '比较计数：' + json.dumps(comparisons, ensure_ascii=False), '',
              '## 求解成本与失败', '', '| 方法 | 成功 / 总数 | 生成秒数 | 评估秒数 |', '|---|---:|---:|---:|']
    for name, rows in runs.items():
        values = list(rows.values())
        generation = sum(r.get('generate', {}).get('seconds', 0) for r in values)
        evaluation = sum(r.get('evaluate', {}).get('seconds', 0) for r in values)
        lines.append(f"| {name} | {sum(r['status']=='success' for r in values)} / {len(values)} | {generation:.3f} | {evaluation:.3f} |")
        for row in values:
            if row['status'] != 'success':
                lines.append(f"\n失败或超时：{name} {row['case']} n={row['cores']} {row['status']}。")
    lines += ['', '审计：配置、输入和原始代码在三组实验间一致，各次运行前后哈希一致；方案、日志及完整结果文件哈希均核对通过。', '',
              '这些图用于开发，结果不能充当新检验或全量结论；没有根据成绩排除失败配置。跨核传输数为评估器生成的 COPY 依赖记录数，不等于传输字节。', '',
              '输入选择、参数与预算见 `experiments/problem2_PLAN.md`。完整记录位于 `raw/problem_2/` 下的 exp058、exp059、exp060；本报告由 `experiments/summarize_problem2_development.py` 生成。']
    output.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    (output.with_suffix('.json')).write_text(json.dumps({'comparisons':comparisons, 'details':details}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(comparisons))


if __name__ == '__main__':
    main()
