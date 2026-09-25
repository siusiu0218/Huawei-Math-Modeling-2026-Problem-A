"""Independently verify v003 artifacts and calculate paired comparisons."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys
from fractions import Fraction

from run_problem3_pair import sha, fingerprint
from run_problem2 import save
from run_problem3_baseline import cache_diagnosis

S = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(S.parent/'code')]
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def report(out):
    manifest = read(out/'manifest.json'); frozen = read(out/'selection.json')
    assert manifest['status'] == 'complete'
    assert sha(out/'selection.json') == manifest['frozen_selection_sha256']
    assert fingerprint([Path(p) for p in frozen['source_hashes']]) == frozen['source_hashes']
    assert fingerprint([Path(p) for p in frozen['input_hashes']]) == frozen['input_hashes']
    for original, digest in frozen['source_hashes'].items():
        assert sha(out/'source'/Path(original).relative_to(S.parent)) == digest
    expected = {(c['case'], n) for c in frozen['cases'] if c['role'] == manifest['role'] for n in range(1, 6)}
    assert {(i['case'], i['cores']) for i in manifest['items']} == expected
    assert len(manifest['items']) == len(expected)
    rows = []; reinserts = []; costs = {'generation_seconds': 0, 'evaluation_seconds': 0, 'new_evaluations': 0}
    (out/'selected_plans').mkdir(exist_ok=True)
    for item in manifest['items']:
        case, cores = item['case'], item['cores']
        graph = read(S.parent/'data'/f'{case}.json'); results = {}
        baseline = read(out/item['candidates']['baseline']['plan'])
        assert sha(out/item['candidates']['baseline']['plan']) == sha(item['candidates']['baseline']['generation']['source'])
        for name, record in item['candidates'].items():
            assert sha(out/record['plan']) == record['plan_sha256']
            plan = read(out/record['plan'])
            assert plan['node_to_subgraph'] == baseline['node_to_subgraph']
            assert [set(c) for c in plan['core_schedules']] == [set(c) for c in baseline['core_schedules']]
            validate_task_order(derive_multicore_plan(graph, plan))
            costs['generation_seconds'] += record['generation']['seconds']
            values = {}
            for mode, ev in record['evaluations'].items():
                assert ev['status'] == 'success' and sha(out/ev['result']) == ev['sha256']
                result = read(out/ev['result'])
                assert result['num_cores'] == cores and result['makespan'] > 0
                values[mode] = result
                if 'duplicate_of' not in record:
                    costs['evaluation_seconds'] += ev['seconds']; costs['new_evaluations'] += 1
            assert values['no_l2']['data_movement_bytes'] == values['cache']['data_movement_bytes']
            cache = values['cache']; stats = cache['cache_stats']
            assert cache['cache_capacity_bytes'] == 1048576
            assert all(t['copy_in_start']-t['copy_out_end'] >= 500 for t in cache['cross_core_transfers'])
            assert stats['hit_rate'] == (stats['hit_bytes']/(stats['hit_bytes']+stats['miss_bytes']) if stats['hit_bytes']+stats['miss_bytes'] else 0)
            diag = cache_diagnosis(cache)
            assert diag['cache_peak_bytes'] <= 1048576
            if diag['hit_completion_insert_events']:
                reinserts.append({'case': case, 'cores': cores, 'candidate': name, 'count': len(diag['hit_completion_insert_events'])})
            results[name] = values
        primary = min(['baseline', 'width1'], key=lambda name: results[name]['cache']['makespan'])
        control = min(['baseline', 'width2'], key=lambda name: results[name]['cache']['makespan'])
        b = results['baseline']['cache']['makespan']; best = results[primary]
        row = {'problem': 3, 'version': 'v003', 'experiment': out.name, 'role': manifest['role'],
               'case': case, 'cores': cores, 'baseline_cache': b,
               'width1_cache': results['width1']['cache']['makespan'], 'width2_cache': results['width2']['cache']['makespan'],
               'selected': primary, 'selected_cache': best['cache']['makespan'], 'selected_no_l2': best['no_l2']['makespan'],
               'control': control, 'control_cache': results[control]['cache']['makespan'],
               'schedule_speedup': float(Fraction(b, best['cache']['makespan'])),
               'cache_speedup_same_plan': float(Fraction(best['no_l2']['makespan'], best['cache']['makespan'])),
               'time_reduction_percent': 100*(b-best['cache']['makespan'])/b,
               'baseline_spill_bytes': results['baseline']['cache']['data_movement_bytes']['spill_added_copy_bytes'],
               'selected_spill_bytes': best['cache']['data_movement_bytes']['spill_added_copy_bytes'],
               'selected_added_copy_bytes': best['cache']['data_movement_bytes']['added_copy_bytes'],
               'selected_hit_rate': best['cache']['cache_stats']['hit_rate'],
               'baseline_no_l2': results['baseline']['no_l2']['makespan'],
               'selected_plan_sha256': item['candidates'][primary]['plan_sha256']}
        rows.append(row)
        shutil.copy2(out/item['candidates'][primary]['plan'], out/'selected_plans'/f'{case}_n{cores}.json')
    assert abs(costs['generation_seconds']-manifest['generation_seconds']) < 1e-6
    assert abs(costs['evaluation_seconds']-manifest['evaluation_seconds']) < 1e-6
    def counts(field):
        return {'faster': sum(r[field] < r['baseline_cache'] for r in rows),
                'equal': sum(r[field] == r['baseline_cache'] for r in rows),
                'slower': sum(r[field] > r['baseline_cache'] for r in rows)}
    summary = {'role': manifest['role'], 'configurations': len(rows), 'direct_width1': counts('width1_cache'),
               'direct_width2': counts('width2_cache'), 'selected': counts('selected_cache'),
               'control': counts('control_cache'), 'costs': costs, 'wall_seconds': manifest['wall_seconds'],
               'hit_completion_insertions': reinserts, 'audit': 'passed', 'by_cores': []}
    for n in range(1, 6):
        group = [r for r in rows if r['cores'] == n]
        summary['by_cores'].append({'cores': n,
            'schedule_speedup': float(sum((Fraction(r['baseline_cache'], r['selected_cache']) for r in group), Fraction())/len(group)),
            'cache_speedup_same_plan': float(sum((Fraction(r['selected_no_l2'], r['selected_cache']) for r in group), Fraction())/len(group)),
            'control_speedup': float(sum((Fraction(r['baseline_cache'], r['control_cache']) for r in group), Fraction())/len(group))})
    save(out/'metrics/audit_summary.json', summary)
    with (out/'metrics/selected_comparison.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    lines = [f"# 第三问 v003：{manifest['role']}检验", '', f"实验：{out.name}；{len(rows)}个配置，全部完成，无失败/超时，文件哈希、固定分核、合法性、Cache口径及选择规则审计通过。", '',
        '主组：baseline + width1；等预算对照：baseline + width2。各组两个候选，Cache耗时最小者入选，平局保留baseline。精确相同方案去重。该方法包含评估器择优，不能将保留基线后的不退步视为候选本身普遍有效。', '',
        f"直接width1：{summary['direct_width1']}；选优后：{summary['selected']}；等预算对照：{summary['control']}。", '',
        '|核数|调度加速比（原Cache/新Cache）|同方案Cache加速比（无L2/Cache）|对照调度加速比|', '|---|---:|---:|---:|']
    for r in summary['by_cores']:
        lines.append(f"|{r['cores']}|{r['schedule_speedup']:.6f}|{r['cache_speedup_same_plan']:.6f}|{r['control_speedup']:.6f}|")
    lines += ['', '以上均为逐图比值的算术平均，不混淆调度优化与Cache贡献。', '', '## 改善配置', '', '|用例|核数|原Cache|新Cache|耗时减少|', '|---|---:|---:|---:|---:|']
    for r in rows:
        if r['selected'] != 'baseline':
            lines.append(f"|{r['case']}|{r['cores']}|{r['baseline_cache']}|{r['selected_cache']}|{r['time_reduction_percent']:.3f}%|")
    lines += ['', f"运行成本：60个新候选生成累计{costs['generation_seconds']:.3f}秒；{costs['new_evaluations']}次实际评估累计{costs['evaluation_seconds']:.3f}秒；批次墙钟{manifest['wall_seconds']:.3f}秒（不含本报告审计）。复用Q2基线的上游成本不为零，不声称这是冷启动总成本。", '',
        f"原评估器保持不变。命中读取完成后重新插入事件的配置/候选记录数：{len(reinserts)}，详见audit_summary.json；原始added_copy_bytes不是Cache后实际DDR流量。", '',
        '局限：新检验组仅对第三问调参未使用，所有图曾用于第一/二问；按结构确定6图而非随机抽样。本报告不代表100图×1～5核全量完成。完整逐候选结果见metrics/comparison.csv，选优及同方案配对见metrics/selected_comparison.csv。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    save(out/'report_provenance.json', {'reporter_sha256': sha(Path(__file__)), 'manifest_sha256': sha(out/'manifest.json'),
                                    'report_sha256': sha(out/'REPORT.md')})
    shutil.copy2(Path(__file__), out/'source/report_problem3_bounded.py')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('out'); args = p.parse_args(); report(Path(args.out).resolve())
