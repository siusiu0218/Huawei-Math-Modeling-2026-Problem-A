"""Post-hoc fixed-placement compute bound; does not tune or rerun any plan."""
import csv
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main(raw, out):
    m = read(raw/'manifest.json'); summary = read(raw/'summary.json')
    assert summary['audit'] == 'passed' and summary['successful_configurations'] == 500
    with (raw/'comparison.csv').open(encoding='utf-8-sig') as f:
        comparisons = {(r['case'], int(r['cores'])):r for r in csv.DictReader(f)}
    graphs = {}; rows = []
    for item in m['items']:
        case, n = item['case'], item['cores']; r = comparisons[case, n]
        if case not in graphs:
            graphs[case] = read(raw/'inputs'/f'{case}.json')
        selected = item['candidates'][r['selected']]
        plan = read(raw/selected['generation'][-1]['file'])
        by_core = {g:c for c, order in enumerate(plan['core_schedules']) for g in order}
        work = defaultdict(int)
        for op in graphs[case]['ops']:
            if op['op'] not in ('COPY_IN', 'COPY_OUT'):
                work[by_core[plan['node_to_subgraph'][str(op['id'])]], op['pipe']] += op['cycles']
        bound = max(work.values(), default=0); makespan = int(r['C_selected_cache'])
        assert 0 < bound <= makespan, (case, n, bound, makespan)
        candidate = item['candidates']['width1']
        unchanged = all(seq[-1]['kind'] == 'copy' for seq in candidate['evaluations'].values())
        rows.append({'case':case, 'cores':n, 'selected':r['selected'], 'candidate_plan_unchanged':unchanged,
            'compute_pipe_work_bound':bound, 'cache_makespan':makespan,
            'fixed_placement_saving_upper_bound_percent':100*(makespan-bound)/makespan,
            'schedule_reduction_percent':float(r['schedule_reduction_percent']),
            'spill_added_copy_bytes':int(r['spill_added_copy_bytes'])})
    check = next(r for r in rows if r['case']=='case_039' and r['cores']==4)
    assert check['compute_pipe_work_bound'] == 354312  # independently measured timeline regression
    out.mkdir(parents=True, exist_ok=False)
    stats = {'configurations':500, 'candidate_plan_unchanged':sum(r['candidate_plan_unchanged'] for r in rows),
        'within_5pct_of_bound':sum(r['fixed_placement_saving_upper_bound_percent'] <= 5 for r in rows),
        'unchanged_outcomes_within_5pct':sum(r['selected']=='baseline' and r['fixed_placement_saving_upper_bound_percent'] <= 5 for r in rows),
        'more_than_10pct_bound_gap':sum(r['fixed_placement_saving_upper_bound_percent'] > 10 for r in rows),
        'mean_reduction_percent_by_cores':{n:sum(r['schedule_reduction_percent'] for r in rows if r['cores']==n)/100 for n in range(1,6)}}
    with (out/'headroom.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'summary.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
    text=f'''# 全量之后：下一步依据

这是事后诊断，不是新实验或新预留检验；未改变算法、参数或方案。

- {stats['candidate_plan_unchanged']}/500个配置的新候选与原方案完全相同，不能把这些持平都解释为“重新排序没有效果”。
- {stats['within_5pct_of_bound']}/500个入选方案距固定分核下的计算流水线工作量下界不超过5%；其中{stats['unchanged_outcomes_within_5pct']}项保留原方案。
- {stats['more_than_10pct_bound_gap']}/500项距该下界超过10%，可作为后续诊断对象，但这个差距不是可兑现的优化收益。
- 五核逐图耗时减少比例的算术平均为{stats['mean_reduction_percent_by_cores'][5]:.4f}%，与“平均加速比1.004193”是不同聚合指标。

下界为逐核、逐计算流水线的原始非COPY操作cycles之和的最大值。原评估器每条计算流水线只有一个执行槽，因此完成时间不能小于该工作量。case_039四核下界354312与此前真实时间线分析一致。下界不含搬运与依赖等待；允许重新分核后该下界会改变，不能据此声称全局接近最优，也不能把余量都归因于内存。

本轮已完成冻结方法的全量验收。现有排序方法整体改善有限，应保留原方案择优。先把这组可靠结果及局限整理成第三问正文；若继续优化，应从下界差距较大且有具体搬运/等待证据的配置开始，另外冻结新版本和检验方案，不能在这批全量结果上调完参数后仍称独立检验。
'''
    (out/'REPORT.md').write_text(text,encoding='utf-8')
    provenance={'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'manifest_sha256':hashlib.sha256((raw/'manifest.json').read_bytes()).hexdigest(),
        'comparison_sha256':hashlib.sha256((raw/'comparison.csv').read_bytes()).hexdigest(),
        'scope':'post-hoc arithmetic diagnostic; original graph hashes verified by full audit'}
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    print(json.dumps(stats),flush=True)


if __name__=='__main__':main(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
