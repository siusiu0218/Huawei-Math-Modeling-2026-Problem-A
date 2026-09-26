"""Audit full v004 coverage, independently choose plans and summarize A/B/C/D."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys
from fractions import Fraction

from run_problem2 import save
from run_problem3_pair import sha, fingerprint
from problem3_v004_support import S, read
from run_problem3_baseline import cache_diagnosis

sys.path.insert(0, str(S.parent/'code'))
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order


def audit(out):
    m = read(out/'manifest.json')
    assert fingerprint([Path(p) for p in m['hashes_before']]) == m['hashes_before']
    assert all(sha(out/rel) == digest for rel, digest in m['archive_hashes'].items())
    expected = {(c, n) for c in m['cases'] for n in m['cores']}
    assert len(m['items']) == len(expected) and {(i['case'], i['cores']) for i in m['items']} == expected
    if m['scope'] == 'full':
        assert expected == {(f'case_{i:03}', n) for i in range(1, 101) for n in range(1, 6)}
    rows, failures, events = [], [], []
    costs = {'generation_seconds': 0, 'evaluation_seconds': 0, 'new_evaluations': 0,
             'external_reuses': 0, 'internal_duplicates': 0, 'candidate_generations': 0}
    for item in m['items']:
        case, n = item['case'], item['cores']; values = {}; plans = {}
        graph = read(out/'inputs'/f'{case}.json')
        for name, candidate in item['candidates'].items():
            for a in candidate['generation']:
                costs['generation_seconds'] += a['seconds']
                costs['candidate_generations'] += a['kind'] == 'execute'
            for attempts in candidate['evaluations'].values():
                for a in attempts:
                    costs['evaluation_seconds'] += a['seconds']
                    costs['new_evaluations'] += a['kind'] == 'execute' and 'returncode' in a
                    costs['external_reuses'] += a['kind'] == 'reuse' and a['status'] == 'success'
                    costs['internal_duplicates'] += a['kind'] == 'copy' and a['status'] == 'success'
            generations = candidate['generation']
            if not generations or generations[-1]['status'] != 'success':
                failures.append({'case': case, 'cores': n, 'candidate': name, 'stage': 'generation'}); continue
            gen = generations[-1]; assert sha(out/gen['file']) == gen['sha256']
            plan = read(out/gen['file']); plans[name] = plan
            validate_task_order(derive_multicore_plan(graph, plan))
            if name == 'baseline':
                assert gen['sha256'] == sha(item['baseline_source'])
            assert len(plan['core_schedules']) == n
            pair = {}
            for mode, attempts in candidate['evaluations'].items():
                if not attempts or attempts[-1]['status'] != 'success':
                    failures.append({'case': case, 'cores': n, 'candidate': name, 'stage': mode,
                                     'status': attempts[-1]['status'] if attempts else 'missing'}); continue
                ev = attempts[-1]; assert sha(out/ev['file']) == ev['sha256']
                origin = ev.get('origin', ev.get('deduplicated_from'))
                if origin:
                    assert sha(origin['source']) == origin['sha256'] == ev['sha256']
                    assert sha(origin['source_plan']) == origin['source_plan_sha256']
                    assert read(origin['source_plan']) == plan
                    if 'source_manifest' in origin:
                        assert sha(origin['source_manifest']) == origin['source_manifest_sha256']
                result = read(out/ev['file'])
                assert result['num_cores'] == n and result['makespan'] > 0
                assert all(t['copy_in_start']-t['copy_out_end'] >= 500 for t in result['cross_core_transfers'])
                pair[mode] = result
            if len(pair) != 2:
                continue
            assert pair['no_l2']['data_movement_bytes'] == pair['cache']['data_movement_bytes']
            b = pair['cache']; stats = b['cache_stats']
            assert b['cache_capacity_bytes'] == 1048576
            assert stats['hit_rate'] == (stats['hit_bytes']/(stats['hit_bytes']+stats['miss_bytes']) if stats['hit_bytes']+stats['miss_bytes'] else 0)
            diag = cache_diagnosis(b); assert diag['cache_peak_bytes'] <= 1048576
            if diag['hit_completion_insert_events']:
                events.append({'case': case, 'cores': n, 'candidate': name, 'count': len(diag['hit_completion_insert_events'])})
            values[name] = pair
        if len(values) != 4:
            continue
        selected = min(('baseline', 'w4', 'w10', 'w16'), key=lambda x: values[x]['cache']['makespan'])
        a = values['baseline']['no_l2']['makespan']; b = values['baseline']['cache']['makespan']
        selected_pair = values[selected]; c = selected_pair['cache']['makespan']; d = selected_pair['no_l2']['makespan']
        stats = selected_pair['cache']['cache_stats']; movement = selected_pair['cache']['data_movement_bytes']
        record = item['candidates'][selected]; plan = record['generation'][-1]
        shutil.copy2(out/plan['file'], out/'selected_plans'/f'{case}_n{n}.json')
        rows.append({'problem': 3, 'version': 'v004', 'experiment': out.name, 'case': case, 'cores': n,
            'A_baseline_no_l2': a, 'B_baseline_cache': b, 'C_selected_cache': c, 'D_selected_no_l2': d,
            **{f'{w}_cache': values[w]['cache']['makespan'] for w in ('w4','w10','w16')}, 'selected': selected,
            'baseline_cache_speedup': a/b, 'schedule_speedup': b/c, 'cache_speedup_same_plan': d/c,
            'schedule_reduction_percent': 100*(b-c)/b, 'hit_bytes': stats['hit_bytes'], 'miss_bytes': stats['miss_bytes'],
            'byte_hit_rate': stats['hit_rate'], 'official_added_copy_bytes': movement['added_copy_bytes'],
            'spill_added_copy_bytes': movement['spill_added_copy_bytes'], 'plan_sha256': plan['sha256'],
            'selected_no_l2_result': record['evaluations']['no_l2'][-1]['file'],
            'selected_cache_result': record['evaluations']['cache'][-1]['file']})
        if len(rows) % 25 == 0:
            print('audited', len(rows), flush=True)
    by_cores = []
    for n in m['cores']:
        group = [r for r in rows if r['cores'] == n]
        def mean_ratio(top, bottom):
            return float(sum((Fraction(r[top], r[bottom]) for r in group), Fraction())/len(group)) if group else None
        traffic = sum(r['hit_bytes']+r['miss_bytes'] for r in group)
        by_cores.append({'cores': n, 'count': len(group),
            'baseline_cache_speedup': mean_ratio('A_baseline_no_l2', 'B_baseline_cache'),
            'schedule_speedup': mean_ratio('B_baseline_cache', 'C_selected_cache'),
            'cache_speedup_same_plan': mean_ratio('D_selected_no_l2', 'C_selected_cache'),
            'schedule_faster': sum(r['C_selected_cache'] < r['B_baseline_cache'] for r in group),
            'cache_faster': sum(r['C_selected_cache'] < r['D_selected_no_l2'] for r in group),
            'cache_equal': sum(r['C_selected_cache'] == r['D_selected_no_l2'] for r in group),
            'cache_slower': sum(r['C_selected_cache'] > r['D_selected_no_l2'] for r in group),
            'mean_case_byte_hit_rate': sum(r['byte_hit_rate'] for r in group)/len(group) if group else None,
            'pooled_byte_hit_rate': sum(r['hit_bytes'] for r in group)/traffic if traffic else 0})
    direct = {label: sum(compare(r[f'{w}_cache'], r['B_baseline_cache']) for r in rows for w in ('w4','w10','w16')) for label, compare in
              [('faster', lambda a,b:a<b), ('equal', lambda a,b:a==b), ('slower', lambda a,b:a>b)]}
    summary = {'audit': 'passed' if len(rows) == len(expected) and not failures else 'incomplete', 'scope': m['scope'],
        'expected_configurations': len(expected), 'successful_configurations': len(rows), 'failures': failures,
        'direct_candidates': direct, 'selected_faster': sum(r['selected'] != 'baseline' for r in rows),
        'costs': costs, 'invocation_wall_seconds': sum(i.get('wall_seconds', 0) for i in m['invocations']),
        'by_cores': by_cores, 'hit_completion_insertions': events,
        'max_direct_regression_percent': max([0]+[100*(r[f'{w}_cache']-r['B_baseline_cache'])/r['B_baseline_cache'] for r in rows for w in ('w4','w10','w16')])}
    save(out/'summary.json', summary)
    if rows:
        with (out/'comparison.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    lines = [f'# 第三问 v004 {m["scope"]}：{out.name}', '',
        f'覆盖 {len(rows)}/{len(expected)} 配置；审计状态：{summary["audit"]}。主方法为baseline+w4/w10/w16，以Cache Makespan择优、平局保留baseline。', '',
        f'直接候选快/平/慢：{direct["faster"]}/{direct["equal"]}/{direct["slower"]}；择优后{summary["selected_faster"]}项改善，其余持平。候选退化最大{summary["max_direct_regression_percent"]:.3f}%。', '',
        '|核数|配对数|原方案Cache加速比 A/B|调度加速比 B/C|入选方案Cache加速比 D/C|调度改善数|Cache快/平/慢|',
        '|---|---:|---:|---:|---:|---:|---|']
    for r in by_cores:
        if r['count']:
            lines.append(f'|{r["cores"]}|{r["count"]}|{r["baseline_cache_speedup"]:.6f}|{r["schedule_speedup"]:.6f}|{r["cache_speedup_same_plan"]:.6f}|{r["schedule_faster"]}|{r["cache_faster"]}/{r["cache_equal"]}/{r["cache_slower"]}|')
    lines += ['', '比值先逐图计算，再按核数取算术平均；A/B与D/C分别使用完全相同方案的无L2、Cache结果。B/C单列调度收益，不将二者相减解释为因果贡献。', '',
        '## 成本与限制', '', f'本次累计记录：{json.dumps(costs, ensure_ascii=False)}。执行循环墙钟累计{summary["invocation_wall_seconds"]:.3f}秒，不含归档初始化、复用索引构建与审计。', '',
        '复用已有Q2/Q3结果与基线计划的上游成本不为零；外部复用记录保留来源及哈希。候选预算为每配置baseline+w4/w10/w16，不根据全量成绩改参数。候选生成30秒、单次评估180秒；失败、超时不自动重试，终止进程树后保留日志。', '',
        f'未完成项：{json.dumps(failures, ensure_ascii=False)}。逐配置完整指标见comparison.csv，入选调度见selected_plans，全部候选与原始结果见plans和metrics。', '',
        '原始评估器未修改。继续披露FIFO命中读取完成后重新插入行为，summary.json保留逐候选事件计数。官方额外搬运量不解释为Cache后实际DDR字节。Cache也可能让部分固定方案变慢，已单列，不删去反例。', '',
        'v004借鉴开源bandcomp，来源及MIT许可见源代码快照。窗口4/10/16、sticky=0.5固定。全部100图曾用于v003，不称未见测试集；本次配对评估全部候选，比原型仅配对入选候选的评估成本更高。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    save(out/'audit_provenance.json', {'manifest_sha256': sha(out/'manifest.json'), 'reporter_sha256': sha(Path(__file__)),
                                     'comparison_sha256': sha(out/'comparison.csv') if rows else None})
    print(json.dumps({k:v for k,v in summary.items() if k != 'hit_completion_insertions'}), flush=True)
    if failures or len(rows) != len(expected):
        raise SystemExit(1)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('out'); args = p.parse_args(); audit(Path(args.out).resolve())
