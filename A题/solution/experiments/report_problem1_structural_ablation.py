"""Independent artifact/arm-constraint checks and Q1 v012 experiment report."""
from collections import Counter,defaultdict
import csv
from pathlib import Path
import shutil

from run_problem1_structural_ablation import ROOT,A_ROOT,SOLUTION,read,save,sha,signature,verify_frozen
from portfolio_scheduler import validate_result
from scene_a_structural_ablation import Graph,quotient,BoundaryTraffic,SETTINGS
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

REPORT=SOLUTION/'outputs/13_problem1_structural_ablation'


def csv_write(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    manifest=read(ROOT/'manifest.json');verify_frozen(manifest)
    assert manifest['status'] in ('completed','completed_with_failures')
    rows=read(ROOT/'candidates.json')
    assert len(rows)==72 and len({(r['case'],r['arm'],r['setting_index']) for r in rows})==72
    assert {r['case'] for r in rows}==set(manifest['cases'])
    flat=[];paired=[];summaries=[];details=[];graph_by_case={}
    for ref in manifest['references']:
        case=ref['case']
        graph=Graph(read(A_ROOT/f'data/{case}.json'));graph_by_case[case]=graph
        old=read(ROOT/'references'/f'{case}_plan.json')
        old_result=read(ROOT/'references'/f'{case}_result.json')
        assert sha(ROOT/'references'/f'{case}_plan.json')==ref['plan_sha256']
        assert sha(ROOT/'references'/f'{case}_result.json')==ref['result_sha256']
        original={int(n):t for n,t in old['node_to_subgraph'].items()}
        old_groups,_,_=quotient(graph,original)
        before=BoundaryTraffic(graph,old_groups).total()
        c_partitions=[]
        case_rows=[r for r in rows if r['case']==case]
        for row in case_rows:
            arm,index=row['arm'],row['setting_index'];folder=ROOT/'runs'/case/row['candidate']
            assert row==read(folder/'status.json')
            plan_path=folder/'plan.json'
            if plan_path.exists():
                plan=read(plan_path)
                validate_task_order(derive_multicore_plan(graph.data,plan))
                if arm in ('A','B'): assert plan['node_to_subgraph']==old['node_to_subgraph']
                if arm=='A': assert [set(x) for x in plan['core_schedules']]==[set(x) for x in old['core_schedules']]
                if arm=='C': c_partitions.append(plan['node_to_subgraph'])
                assert sha(plan_path)==row['plan_sha256']
                assert signature(plan)==row['signature']
                metadata=read(folder/'generation.json')
                assert tuple(metadata['setting'])==SETTINGS[index]
            result={}
            if row['status']=='success':
                path=Path(row['result_path']);result=read(path)
                assert sha(path)==row['result_sha256']
                checked=validate_result(result,5)
                for k,v in checked.items(): assert row[k]==v
                if row['evaluation_reused']:
                    source=row['reuse_source']
                    source_plan=old if source=='baseline' else read(ROOT/'runs'/case/source/'plan.json')
                    assert signature(source_plan)==signature(plan)
                mapping={int(n):t for n,t in plan['node_to_subgraph'].items()}
                groups,_,_=quotient(graph,mapping)
                after=BoundaryTraffic(graph,groups).total()
                # Static hyperedge count predicts only boundary traffic, not spill.
                assert old_result['data_movement_bytes']['partition_added_copy_bytes']-row['partition_added_copy_bytes']==before-after
            flat.append({k:row.get(k,'') for k in ('problem','algorithm_version','experiment','case','cores','arm','setting_index','candidate','status',
                'makespan','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes','generation_seconds','evaluation_seconds','evaluation_reused')})
            details.append({'case':case,'arm':arm,'setting_index':index,'status':row['status'],
                'memory_peak_by_core':result.get('memory_peak_by_core'),
                'route':read(folder/'generation.json').get('route') if (folder/'generation.json').exists() else None})
        assert all(mapping==c_partitions[0] for mapping in c_partitions)
        summary={'case':case,'cores':5,'baseline_makespan':ref['baseline_makespan'],'previous_best_makespan':ref['previous_best_makespan'],
                 'single_makespan':ref['single_makespan']}
        for arm in ('A','B','C'):
            candidates=[r for r in case_rows if r['arm']==arm and r['status']=='success']
            direct=min(candidates,key=lambda r:(r['makespan'],r['setting_index'])) if candidates else None
            summary[arm+'_direct_best']=direct['makespan'] if direct else None
            summary[arm+'_best_candidate']=direct['candidate'] if direct else None
            summary[arm+'_with_baseline']=min([ref['baseline_makespan']]+[r['makespan'] for r in candidates])
        for index in range(4):
            triplet={arm:next(r for r in case_rows if r['arm']==arm and r['setting_index']==index) for arm in ('A','B','C')}
            paired.append({'case':case,'setting_index':index,'priority':SETTINGS[index][0],'cross_wait_proxy_multiplier':SETTINGS[index][1],
                'A':triplet['A']['makespan'],'B':triplet['B']['makespan'],'C':triplet['C']['makespan'],
                'C_less_B':triplet['C']['makespan']<triplet['B']['makespan'] if all(triplet[a]['status']=='success' for a in ('B','C')) else None})
        summary['best_current']=min(summary[a+'_with_baseline'] for a in ('A','B','C'))
        summary['best_including_previous']=min(summary['best_current'],ref['previous_best_makespan'])
        summary['reduction_vs_baseline_percent']=100*(1-summary['best_including_previous']/ref['baseline_makespan'])
        summary['baseline_speedup']=ref['single_makespan']/ref['baseline_makespan']
        summary['best_speedup']=ref['single_makespan']/summary['best_including_previous']
        metadata=read(ROOT/'runs'/case/'C0/generation.json') if (ROOT/'runs'/case/'C0/generation.json').exists() else {}
        summary['C_route']=metadata.get('route')
        summary['C_old_tasks']=metadata.get('old_tasks');summary['C_new_tasks']=metadata.get('new_tasks')
        summaries.append(summary)
    REPORT.mkdir(exist_ok=True)
    for dirname in ('best_plans','arm_plans'): (REPORT/dirname).mkdir(exist_ok=True)
    selection=[]
    for ref in manifest['references']:
        case=ref['case'];summary=next(s for s in summaries if s['case']==case)
        choices=[(ref['baseline_makespan'],'baseline',ROOT/'references'/f'{case}_plan.json',ROOT/'references'/f'{case}_result.json'),
            (ref['previous_best_makespan'],'previous_best',ROOT/'references'/f'{case}_previous_best_plan.json',ROOT/'references'/f'{case}_previous_best_result.json')]
        for r in rows:
            if r['case']==case and r['status']=='success':
                choices.append((r['makespan'],r['candidate'],ROOT/'runs'/case/r['candidate']/'plan.json',Path(r['result_path'])))
        winner=min(choices,key=lambda x:(x[0],x[1]!='baseline',x[1]!='previous_best',x[1]))
        assert winner[0]==summary['best_including_previous']
        shutil.copy2(winner[2],REPORT/'best_plans'/f'{case}_n5.json')
        assert sha(winner[2])==sha(REPORT/'best_plans'/f'{case}_n5.json')
        selection.append({'case':case,'makespan':winner[0],'source':winner[1],'plan_source':str(winner[2]),'result_source':str(winner[3]),
            'plan_sha256':sha(winner[2]),'result_sha256':sha(winner[3])})
        for arm in ('A','B','C'):
            name=summary[arm+'_best_candidate']
            if name:
                shutil.copy2(ROOT/'runs'/case/name/'plan.json',REPORT/'arm_plans'/f'{case}_{arm}_n5.json')
    save(REPORT/'selection.json',selection)
    csv_write(REPORT/'comparison.csv',summaries);csv_write(REPORT/'candidates.csv',flat);csv_write(REPORT/'paired.csv',paired)
    save(REPORT/'memory_details.json',details)
    cost=[]
    for arm in ('A','B','C'):
        candidates=[r for r in rows if r['arm']==arm]
        outcomes=Counter()
        for r in candidates:
            if r['status']!='success': outcomes['failed']+=1;continue
            base=next(s['baseline_makespan'] for s in summaries if s['case']==r['case'])
            outcomes['faster' if r['makespan']<base else 'equal' if r['makespan']==base else 'slower']+=1
        cost.append({'arm':arm,'slots':len(candidates),'successful':sum(r['status']=='success' for r in candidates),
            'new_evaluations':sum(r['status']=='success' and not r['evaluation_reused'] for r in candidates),
            'unique_plans_within_arm':len({(r['case'],r.get('signature')) for r in candidates if r['status']=='success'}),
            'generation_seconds':sum(r['generation_seconds'] for r in candidates),
            'evaluation_seconds':sum(r['evaluation_seconds'] for r in candidates),**{k:outcomes[k] for k in ('faster','equal','slower','failed')}})
    csv_write(REPORT/'costs.csv',cost)
    audit={'passed':True,'logical_candidates':72,'successful':sum(r['status']=='success' for r in rows),
        'new_evaluations':sum(r['status']=='success' and not r['evaluation_reused'] for r in rows),
        'reused_slots':sum(r['evaluation_reused'] for r in rows),'costs':cost,
        'frozen_unchanged':True,'arm_constraints_verified':True,'C_partition_constant_within_case':True,
        'tensor_boundary_traffic_verified':True,'paired_C_better_B':sum(r['C_less_B'] is True for r in paired),
        'paired_C_equal_B':sum(r['C']==r['B'] for r in paired if r['C'] is not None and r['B'] is not None),
        'paired_C_worse_B':sum(r['C']>r['B'] for r in paired if r['C'] is not None and r['B'] is not None),
        'selection':selection,'wall_seconds':manifest['wall_seconds']}
    save(REPORT/'audit.json',audit)
    lines=['# 第一问 v012：切分、分核与排序三组对照','',
        '本轮是六张已知开发图的机制对照，全部为五核；没有更新100图正式成绩，也没有使用其余17张低分图检验泛化。','',
        '## 本轮判断','',
        '- 056/049：A、B均未改变原耗时；C四个配对全部胜出，最佳耗时分别下降44.20%和45.02%。支持本轮旧任务边界确实限制可用并行性；不等于已找到最优切分。',
        '- 044：A、B均持平，C下降29.79%，并从比单核慢变为约1.25倍。共享张量成组调整有效，尽管出现spill，总体仍受益。',
        '- 064/069：本轮最佳来自B，分别下降0.47%/6.13%；关键链成组重切分未超过旧方案。当前证据优先支持改善分核，不能宣称等待链合并普遍有效。',
        '- 046：C把8个任务合成2个，只使用2核，新增2591232 bytes spill；虽然总新增搬运减少，耗时仍上升约18.47%。并行度下降和内存压力同时出现，未用反事实实验单独归因。保留上一轮131924 cycles。',
        '- 下一步应先冻结并在其他图检验计算集中型重切分的收益；共享张量组需增加并行度/内存压力约束后另立版本测试。不自动扩大本轮范围。','',
        '## 固定设计','',
        '- A：旧切分、旧分核，全局重新排序。B：旧切分，全局重新分核与排序。C：按结构特征成组重新切分，再使用与B相同的全局调度器。',
        '- 每组同样四个预先冻结设置：rank/work优先级×跨核等待估计倍数1/2。真实评估始终为原题1000/100等待与原始config。三组使用相同的静态耗时代理，不用旧实测耗时偏袒旧切分。',
        '- C每图固定一种切分，四个设置只改变调度。计算集中型采用全图深度窗口10内弱连通分量（复用已有MIT归属实现）；搬运型合并至多四个共享大张量消费者；其他采用连续四任务关键链分组与凸闭包。没有按case编号规则。',
        '- 共同基线为正式v009方案。上一轮局部搜索最优另列，不混入各组直接最优；最终交付方案同时保留这些旧结果作保护。','',
        '## 对照结果（Makespan，越小越好）','',
        '| 图 | 正式旧方案 | 上轮最好 | A仅重排 | B重新分核 | C重切分 |',
        '|---|---:|---:|---:|---:|---:|']
    for s in summaries: lines.append(f"| {s['case']} | {s['baseline_makespan']} | {s['previous_best_makespan']} | {s['A_direct_best']} | {s['B_direct_best']} | {s['C_direct_best']} |")
    lines+=['','表内A/B/C是各组直接候选最优，包含退化值；没有用基线覆盖负结果。comparison.csv另列保留基线后的各组成绩。','',
        '## 对切分的配对检验','',
        f"同一调度设置下，C相对B共{audit['paired_C_better_B']}快、{audit['paired_C_equal_B']}平、{audit['paired_C_worse_B']}慢（24对，详见paired.csv）。不能仅拿两组各自最好的一次结果，声称切分独立产生固定收益。",'']
    for s in summaries:
        cps=[p for p in paired if p['case']==s['case']]
        better=sum(p['C_less_B'] is True for p in cps)
        lines.append(f"- {s['case']}：C为{s['C_route']}，任务数{s['C_old_tasks']}→{s['C_new_tasks']}；四个配对中{better}个C快于B。")
    lines+=['','## 最终保留方案','',
        '| 图 | 最好耗时（含历史保护） | 对正式旧方案降幅 | 五核加速比 | 来源 |',
        '|---|---:|---:|---:|---|']
    for s in summaries:
        chosen=next(c for c in selection if c['case']==s['case'])
        lines.append(f"| {s['case']} | {s['best_including_previous']} | {s['reduction_vs_baseline_percent']:.2f}% | {s['baseline_speedup']:.4f} → {s['best_speedup']:.4f} | {chosen['source']} |")
    lines+=['','## 搬运、内存与成本','',
        '切边数没有被当作搬运量：按张量及生产/消费任务集合计算边界COPY，并逐候选核对与原评估器的切分新增搬运差值一致。筛选模型不含spill；实际spill和内存峰值另从原评估器读取。','',
        '| 图 | 正式旧方案新增搬运 | C组新增搬运 | C组spill字节 | C组最高L1 / UB |',
        '|---|---:|---:|---:|---:|']
    for s in summaries:
        case=s['case'];name=s['C_best_candidate']
        r=next(r for r in rows if r['case']==case and r['candidate']==name)
        scored=read(Path(r['result_path']));old=read(ROOT/'references'/f'{case}_result.json')
        peaks=scored['memory_peak_by_core'].values()
        lines.append(f"| {case} | {old['data_movement_bytes']['added_copy_bytes']} | {r['added_copy_bytes']} | {r['spill_added_copy_bytes']} | {max(p['L1'] for p in peaks)} / {max(p['UB'] for p in scored['memory_peak_by_core'].values())} |")
    lines+=['','三组均最多24个逻辑槽位，但实际独立方案和评估次数不完全相等：重复方案去重，不补入额外参数凑数。因此这是相同候选上限的对照，不是完全相同CPU时间或独立方案数的对照。跨组复用按A→B→C执行顺序记账，某组新增评估较少不代表冷启动免费。','',
        '| 组 | 逻辑槽位 | 组内独立方案 | 新评估 | 生成秒数 | 评估秒数 | 快/平/慢（直接对旧方案） |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for c in cost: lines.append(f"| {c['arm']} | {c['slots']} | {c['unique_plans_within_arm']} | {c['new_evaluations']} | {c['generation_seconds']:.3f} | {c['evaluation_seconds']:.3f} | {c['faster']}/{c['equal']}/{c['slower']} |")
    lines+=['',f"总计{audit['new_evaluations']}次新增评估、{audit['reused_slots']}个复用槽位，执行墙钟{manifest['wall_seconds']:.3f}秒；不含历史基线搜索、准备与审计。生成30秒/评估180秒预算，不重试。",'',
        '## 验证及结论边界','',
        '- 4项针对性小图测试通过：张量计数去重、凸闭包、A/B控制约束及可执行性、共享输入合并与真实搬运差值。',
        '- 核验72槽覆盖、原代码/配置/六图输入及源码快照、引用方案/结果哈希、A/B约束、C同图固定切分、调度合法性、实际内存峰值、搬运差值、配对结果及最优方案复制。',
        '- A/B/C的差异只评价本轮固定启发式和预算。新排序差于旧方案不能证明排序已最优；C失败不能证明所有重切分无效。共享张量合并可能减少字节却延长Makespan，须看实测而非代理。',
        '- 数据为旧成绩筛选的开发集；没有独立检验，没有论文算法独创性或完整复现声明，没有宣称达到全量4倍。','',
        '## 文件与复现','',
        f'- 原始记录、冻结方案、源码快照：`{ROOT}`。',
        '- `comparison.csv`逐图对照，`paired.csv`配对结果，`candidates.csv`全部候选与负结果，`costs.csv`实际成本，`memory_details.json`内存峰值。',
        '- `best_plans/`六份最终保留方案，`arm_plans/`各组直接最佳方案。最终选择来源与哈希见selection.json。',
        '- 入口：`run_problem1_structural_ablation.py --prepare`、`--run`。编号固定，拒绝覆盖或自动重跑；新实验须使用新编号。',
        '- 重建审计与报告：`A题/.venv/Scripts/python.exe -B A题/solution/experiments/report_problem1_structural_ablation.py`。','']
    (REPORT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print({'audit':audit,'comparison':summaries})


if __name__=='__main__':main()
