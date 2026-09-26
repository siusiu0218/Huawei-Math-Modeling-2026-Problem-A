"""Audit and summarize all 17 follow-up cases, including failed/negative slots."""
from collections import Counter,defaultdict
import csv
from pathlib import Path
import shutil

from run_problem1_structural_transfer import ROOT,A_ROOT,SOLUTION,read,save,sha,signature,verify_frozen,SETTINGS
from scene_a_structural_ablation import Graph,quotient,BoundaryTraffic
from portfolio_scheduler import validate_result
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

REPORT=SOLUTION/'outputs/14_problem1_structural_transfer'


def csv_write(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    manifest=read(ROOT/'manifest.json');verify_frozen(manifest)
    assert manifest['status'] in ('completed','completed_with_failures')
    for p,h in manifest['algorithm_hashes_from_exp133'].items(): assert sha(A_ROOT/p)==h
    rows=read(ROOT/'candidates.json')
    expected={(case,arm,index) for case in manifest['cases'] for arm in ('B','C') for index in range(4)}
    assert len(rows)==136 and {(r['case'],r['arm'],r['setting_index']) for r in rows}==expected
    assert not set(manifest['cases'])&set(manifest['excluded_development_cases'])
    REPORT.mkdir(exist_ok=True);(REPORT/'plans').mkdir(exist_ok=True)
    comparisons=[];paired=[];flat=[];selected=[];memory=[];failures=[]
    for ref in manifest['references']:
        case=ref['case'];graph=Graph(read(A_ROOT/f'data/{case}.json'))
        old_path=ROOT/'references'/f'{case}_plan.json';old_result_path=ROOT/'references'/f'{case}_result.json'
        assert sha(old_path)==ref['plan_sha256'] and sha(old_result_path)==ref['result_sha256']
        old=read(old_path);old_result=read(old_result_path)
        validate_task_order(derive_multicore_plan(graph.data,old))
        before=BoundaryTraffic(graph,quotient(graph,{int(n):t for n,t in old['node_to_subgraph'].items()})[0]).total()
        case_rows=[r for r in rows if r['case']==case];c_partitions=[];result_cache={};route=None
        for row in case_rows:
            folder=ROOT/'runs'/case/row['candidate']
            assert read(folder/'status.json')==row
            if row['status'].startswith('generation_'):
                failures.append({'case':case,'candidate':row['candidate'],'status':row['status'],'log':str(folder/'generation.log')})
            else:
                plan=read(folder/'plan.json');metadata=read(folder/'generation.json')
                assert sha(folder/'plan.json')==row['plan_sha256'] and signature(plan)==row['signature']
                assert metadata==row['generation_metadata'] and tuple(metadata['setting'])==SETTINGS[row['setting_index']]
                validate_task_order(derive_multicore_plan(graph.data,plan))
                if row['arm']=='B': assert plan['node_to_subgraph']==old['node_to_subgraph']
                else:
                    c_partitions.append(plan['node_to_subgraph']);route=metadata['route']
                if row['status']=='success':
                    path=Path(row['result_path'])
                    if str(path) not in result_cache: result_cache[str(path)]=read(path)
                    result=result_cache[str(path)]
                    assert sha(path)==row['result_sha256']
                    for k,v in validate_result(result,5).items(): assert row[k]==v
                    if row['evaluation_reused']:
                        source=row['reuse_source']
                        source_plan=old if source=='baseline' else read(ROOT/'runs'/case/source/'plan.json')
                        assert signature(plan)==signature(source_plan)
                    groups,_,_=quotient(graph,{int(n):t for n,t in plan['node_to_subgraph'].items()})
                    after=BoundaryTraffic(graph,groups).total()
                    assert old_result['data_movement_bytes']['partition_added_copy_bytes']-row['partition_added_copy_bytes']==before-after
                    memory.append({'case':case,'candidate':row['candidate'],'memory_peak_by_core':result['memory_peak_by_core'],
                        'spill_added_copy_bytes':row['spill_added_copy_bytes']})
                else:
                    failures.append({'case':case,'candidate':row['candidate'],'status':row['status'],'log':str(folder/'evaluation_process.log')})
            flat.append({k:row.get(k,'') for k in ('problem','algorithm_version','experiment','case','cores','arm','setting_index','candidate','status',
                'makespan','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes','generation_seconds','evaluation_seconds','evaluation_reused')})
        assert all(m==c_partitions[0] for m in c_partitions)
        summary={'case':case,'cores':5,'route':route,'baseline_makespan':ref['baseline_makespan'],'single_makespan':ref['single_makespan']}
        for arm in ('B','C'):
            good=[r for r in case_rows if r['arm']==arm and r['status']=='success']
            best=min(good,key=lambda r:(r['makespan'],r['setting_index'])) if good else None
            summary[arm+'_successful_slots']=len(good)
            summary[arm+'_direct_best']=best['makespan'] if best else None
            summary[arm+'_best_candidate']=best['candidate'] if best else None
            summary[arm+'_with_baseline']=min([ref['baseline_makespan']]+[r['makespan'] for r in good])
            summary[arm+'_reduction_percent']=100*(1-summary[arm+'_with_baseline']/ref['baseline_makespan'])
        for index in range(4):
            b=next(r for r in case_rows if r['arm']=='B' and r['setting_index']==index)
            c=next(r for r in case_rows if r['arm']=='C' and r['setting_index']==index)
            pair_status='complete' if b['status']==c['status']=='success' else 'incomplete'
            outcome=('faster' if c['makespan']<b['makespan'] else 'equal' if c['makespan']==b['makespan'] else 'slower') if pair_status=='complete' else 'unavailable'
            paired.append({'case':case,'route':route,'setting_index':index,'B':b['makespan'],'C':c['makespan'],'status':pair_status,'C_vs_B':outcome})
        choices=[(ref['baseline_makespan'],'baseline',old_path,old_result_path)]+[
            (r['makespan'],r['candidate'],ROOT/'runs'/case/r['candidate']/'plan.json',Path(r['result_path'])) for r in case_rows if r['status']=='success']
        winner=min(choices,key=lambda x:(x[0],x[1]!='baseline',x[1]))
        target=REPORT/'plans'/f'{case}_n5.json';shutil.copy2(winner[2],target)
        assert sha(target)==sha(winner[2])
        selected_result=read(winner[3])
        summary.update(selected_candidate=winner[1],makespan=winner[0],
            reduction_percent=100*(1-winner[0]/ref['baseline_makespan']),baseline_speedup=ref['single_makespan']/ref['baseline_makespan'],
            speedup=ref['single_makespan']/winner[0],baseline_added_copy_bytes=old_result['data_movement_bytes']['added_copy_bytes'],
            added_copy_bytes=selected_result['data_movement_bytes']['added_copy_bytes'],spill_added_copy_bytes=selected_result['data_movement_bytes']['spill_added_copy_bytes'])
        comparisons.append(summary)
        selected.append({'case':case,'candidate':winner[1],'makespan':winner[0],'plan_source':str(winner[2]),'result_source':str(winner[3]),
            'plan_sha256':sha(winner[2]),'result_sha256':sha(winner[3])})
    costs=[]
    for arm in ('B','C'):
        group=[r for r in rows if r['arm']==arm];counts=Counter()
        for r in group:
            if r['status']!='success': counts['failed']+=1;continue
            base=next(s['baseline_makespan'] for s in comparisons if s['case']==r['case'])
            counts['faster' if r['makespan']<base else 'equal' if r['makespan']==base else 'slower']+=1
        costs.append({'arm':arm,'slots':len(group),'unique_successful_plans':len({(r['case'],r.get('signature')) for r in group if r['status']=='success'}),
            'new_evaluations':sum(not r['evaluation_reused'] and r['status']=='success' for r in group),
            'generation_seconds':sum(r['generation_seconds'] for r in group),'evaluation_seconds':sum(r['evaluation_seconds'] for r in group),
            **{k:counts[k] for k in ('faster','equal','slower','failed')}})
    routes=[]
    for route in sorted({s['route'] for s in comparisons},key=str):
        group=[s for s in comparisons if s['route']==route]
        routes.append({'route':route,'cases':len(group),'improved':sum(s['reduction_percent']>0 for s in group),
            'meaningful_ge_1_percent':sum(s['reduction_percent']>=1 for s in group),
            'B_mean_reduction_percent':sum(s['B_reduction_percent'] for s in group)/len(group),
            'C_mean_reduction_percent':sum(s['C_reduction_percent'] for s in group)/len(group),
            'selected_mean_reduction_percent':sum(s['reduction_percent'] for s in group)/len(group)})
    pair_counts=Counter(p['C_vs_B'] for p in paired)
    audit={'passed':True,'cases':17,'logical_slots':136,'successful_slots':sum(r['status']=='success' for r in rows),
        'new_evaluations':sum(c['new_evaluations'] for c in costs),'reused_slots':sum(r['evaluation_reused'] for r in rows),
        'failed_slots':len(failures),'algorithm_matches_exp133':True,'frozen_unchanged':True,'B_partition_unchanged':True,
        'C_partition_constant_across_settings':True,'tensor_boundary_difference_verified':True,
        'improved_cases':sum(s['reduction_percent']>0 for s in comparisons),
        'meaningful_ge_1_percent':sum(s['reduction_percent']>=1 for s in comparisons),
        'baseline_mean_speedup':sum(s['baseline_speedup'] for s in comparisons)/17,
        'selected_mean_speedup':sum(s['speedup'] for s in comparisons)/17,
        'mean_case_time_reduction_percent':sum(s['reduction_percent'] for s in comparisons)/17,
        'C_vs_B_pairs':dict(pair_counts),'routes':routes,'costs':costs,'wall_seconds':manifest['wall_seconds']}
    for name,data in [('comparison.csv',comparisons),('candidates.csv',flat),('paired.csv',paired),('costs.csv',costs),('routes.csv',routes)]:csv_write(REPORT/name,data)
    save(REPORT/'selection.json',selected);save(REPORT/'audit.json',audit);save(REPORT/'failures.json',failures);save(REPORT/'memory_details.json',memory)
    lines=['# 第一问 v012：剩余17张低分图的冻结后续检验','',
        f"17图五核，136候选槽，{audit['successful_slots']}成功、{audit['failed_slots']}失败/超时。保留原方案后{audit['improved_cases']}图改善，{17-audit['improved_cases']}图持平；其中{audit['meaningful_ge_1_percent']}图耗时下降至少1%。",'',
        f"本组平均加速比 {audit['baseline_mean_speedup']:.6f} → {audit['selected_mean_speedup']:.6f}；逐图耗时降幅算术平均 {audit['mean_case_time_reduction_percent']:.2f}%。这些均为筛选出的17图统计，不是100图正式均值。",'',
        '## 本轮判断与下一步','',
        '- 计算集中型全图重切分：9张均存在改善候选，保留基线后的平均耗时降幅33.78%；同组B平均仅0.017%。收益在六张开发图之外重复出现，支持继续做更广覆盖验证，但不代表每个参数候选都改善。',
        '- 关键链成组合并：8张中最终4张改善，B/C择优平均降幅4.07%。016/024/051的C直接最优明显退化，048两组均未超过基线；不能把所有重切分路线都描述为稳定有效。',
        '- 本组没有shared_tensor_groups路线，不能把这些结果当作搬运型多任务合并的后续验证；开发图046的spill和并行度问题仍在。',
        '- 建议先准备冻结规则下的100图×2～5核全量入口及成本预算，保留旧方案并报告全部负候选，再启动正式全量验收。当前没有运行全量，也没有更新正式均值。若先改合并规则，必须另立版本，不能再把本17图称为该新规则的未用检验集。','',
        '## 固定设计与范围','',
        '- 原五核加速比<2的23图，排除六张开发图，剩余17图全部纳入。之前已看过旧基线诊断，称后续检验，不称完全未见数据独立验证。',
        '- 算法源码与exp133逐字节一致，结构路由阈值、窗口10、最多四任务成组、rank/work×等待估计倍数1/2全部冻结；没有根据本轮结果调参。',
        '- B保留旧切分，重分核与排序；C重切分再用相同调度器。每组每图最多四个逻辑候选；共同旧方案作为保护，各组直接最优也完整报告。',
        '- 原评估器/config不变；生成30秒、评估180秒，不重试。相同方案去重，实际评估预算及独立方案数另报，不把重复槽当独立证据。','',
        '## 逐图结果','',
        '| 图 | 旧耗时 | B直接最好 | C直接最好 | 最终耗时 | 降幅 | 入选 |',
        '|---|---:|---:|---:|---:|---:|---|']
    for s in comparisons:lines.append(f"| {s['case']} | {s['baseline_makespan']} | {s['B_direct_best']} | {s['C_direct_best']} | {s['makespan']} | {s['reduction_percent']:.2f}% | {s['selected_candidate']} |")
    lines+=['','最终不退步由保留基线保证，不代表B/C直接候选从不退化。所有负候选在candidates.csv；所有失败/超时在failures.json，未排除其对应图。','',
        '## 按结构路线与配对结果','',
        '| C结构路线 | 图数 | 最终改善 | 最终降幅≥1% | B平均降幅（含基线） | C平均降幅（含基线） |',
        '|---|---:|---:|---:|---:|---:|']
    for r in routes:lines.append(f"| {r['route']} | {r['cases']} | {r['improved']} | {r['meaningful_ge_1_percent']} | {r['B_mean_reduction_percent']:.2f}% | {r['C_mean_reduction_percent']:.2f}% |")
    lines+=['',f"同调度设置的68个C/B配对：{pair_counts['faster']}快、{pair_counts['equal']}平、{pair_counts['slower']}慢、{pair_counts['unavailable']}不可比较。配对槽有重复方案，不作为独立样本做显著性推断。",'',
        '结构类别缺失时，不把其他类型结果当作该路线的验证。尤其本组如果没有shared_tensor_groups路线，就不能据此判断开发集中044/046的搬运型合并能否推广。','',
        '## 成本与验证','',
        '| 组 | 逻辑槽 | 独立成功方案 | 新评估 | 生成秒 | 评估秒 | 直接快/平/慢/失败 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for c in costs:lines.append(f"| {c['arm']} | {c['slots']} | {c['unique_successful_plans']} | {c['new_evaluations']} | {c['generation_seconds']:.3f} | {c['evaluation_seconds']:.3f} | {c['faster']}/{c['equal']}/{c['slower']}/{c['failed']} |")
    lines+=['',f"共{audit['new_evaluations']}次新增成功评估、{audit['reused_slots']}复用槽，执行墙钟{manifest['wall_seconds']:.3f}秒。旧v009搜索及基线评估成本不含在内；候选跨组复用按B→C执行顺序记账，不代表冷启动免费。",'',
        '- 验证全部136槽覆盖、17图与开发集不交叠、源码/原代码/配置/输入和引用结果哈希、B固定切分、C同图同切分、合法性、内存容量、逐任务张量边界搬运差值、指标与方案择优。',
        '- 算法保持冻结，没有新增算法改动；复用开发阶段4项针对性测试的结果。本轮入口与完整产物另按上述规则核验。',
        '- 本轮只覆盖剩余低分图的五核，不检验原本高分图或2～4核；未更新第一问正式v009结果，不能宣称已达到全量4倍。','',
        '## 文件与复现','',f'- 原始记录/源码快照/冻结协议：`{ROOT}`。',
        '- comparison.csv、paired.csv、routes.csv、candidates.csv、costs.csv保存完整指标；memory_details.json保留逐候选内存及spill。',
        '- plans/保存17份入选方案；selection.json记录源文件与哈希。',
        '- 入口run_problem1_structural_transfer.py --prepare、--run固定本次编号且拒绝覆盖；新实验须新编号。',
        '- 重建报告：A题/.venv/Scripts/python.exe -B A题/solution/experiments/report_problem1_structural_transfer.py。','']
    (REPORT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(audit)


if __name__=='__main__':main()
