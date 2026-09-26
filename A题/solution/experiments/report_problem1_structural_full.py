"""Audit all exp137 slots and publish full-scope results without altering v009."""
from collections import Counter
import csv
from pathlib import Path
import shutil
from run_problem1_structural_full import (SOLUTION, A_ROOT, read, save, sha,
    signature, checked, verify_frozen, validate_row, experiment_path)
from scene_a_structural_ablation import Graph, quotient, BoundaryTraffic, SETTINGS
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

ROOT=experiment_path('v012','exp137_20260926_structural_full')
OUT=SOLUTION/'outputs/16_problem1_structural_full'


def table(name, rows):
    if not rows:
        return
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    m=read(ROOT/'manifest.json');verify_frozen(m)
    assert m['status'] in ('completed','completed_with_failures')
    rows=read(ROOT/'candidates.json'); selections=read(ROOT/'selection.json')
    expected={(c,n,a+str(i)) for c in m['cases'] for n in m['cores'] for a in ('B','C') for i in range(4)}
    assert len(rows)==len(expected)==3200
    assert {(r['case'],r['cores'],r['candidate']) for r in rows}==expected
    assert len(selections)==400 and len({(r['case'],r['cores']) for r in selections})==400
    reuse=read(ROOT/'reuse_index.json')
    for item in reuse.values():
        for field in ('source_manifest','source_plan','result_path'):
            digest={'source_manifest':'source_manifest_sha256','source_plan':'source_plan_sha256','result_path':'result_sha256'}[field]
            checked(item[field],item[digest])
    OUT.mkdir(exist_ok=True);(OUT/'plans').mkdir(exist_ok=True)
    comparisons=[];failures=[];graph=None;previous=None
    for ref in m['references']:
        case,n,key=ref['case'],ref['cores'],ref['key']
        if case!=previous:
            graph=Graph(read(A_ROOT/f'data/{case}.json'));previous=case
        old=read(ROOT/'references'/f'{key}_plan.json')
        old_result=read(ROOT/'references'/f'{key}_result.json')
        validate_task_order(derive_multicore_plan(graph.data,old))
        before=BoundaryTraffic(graph,quotient(graph,{int(k):v for k,v in old['node_to_subgraph'].items()})[0]).total()
        group=[r for r in rows if r['case']==case and r['cores']==n]
        cache={signature(old):str(ROOT/'references'/f'{key}_result.json')}
        cache.update({k.split(':',1)[1]:v['result_path'] for k,v in reuse.items() if k.startswith(key+':')})
        partitions=[];routes=set();seen={}
        for row in group:
            folder=ROOT/'runs'/key/row['candidate']
            assert read(folder/'status.json')==row
            if row['status'].startswith('generation_'):
                failures.append(row);continue
            plan=read(folder/'plan.json');meta=read(folder/'generation.json')
            checked(folder/'plan.json',row['plan_sha256']);assert signature(plan)==row['signature']
            assert tuple(meta['setting'])==SETTINGS[row['setting_index']]
            if row['signature'] not in seen:
                validate_task_order(derive_multicore_plan(graph.data,plan))
                seen[row['signature']]=BoundaryTraffic(graph,quotient(graph,{int(k):v for k,v in plan['node_to_subgraph'].items()})[0]).total()
            if row['arm']=='B':assert plan['node_to_subgraph']==old['node_to_subgraph']
            else:partitions.append(plan['node_to_subgraph']);routes.add(meta['route'])
            if row['status']=='success':
                validate_row(folder,row,n)
                assert old_result['data_movement_bytes']['partition_added_copy_bytes']-row['partition_added_copy_bytes']==before-seen[row['signature']]
                if row['evaluation_reused']:assert cache[row['signature']]==row['result_path']
                cache[row['signature']]=row['result_path']
            else:failures.append(row)
        assert not partitions or all(p==partitions[0] for p in partitions)
        good=[r for r in group if r['status']=='success']
        best=min([ref['baseline_makespan']]+[r['makespan'] for r in good])
        selected=next(s for s in selections if s['case']==case and s['cores']==n)
        assert selected['makespan']==best
        source=ROOT/'references'/f'{key}_plan.json' if selected['candidate']=='baseline' else ROOT/'runs'/key/selected['candidate']/'plan.json'
        checked(ROOT/'selected'/f'{key}.json',sha(source));checked(source,selected['selected_plan_sha256'])
        shutil.copy2(source,OUT/'plans'/f'{key}.json')
        record=dict(case=case,cores=n,route=';'.join(sorted(routes)),baseline_makespan=ref['baseline_makespan'],makespan=best,
            baseline_speedup=ref['single_makespan']/ref['baseline_makespan'],speedup=ref['single_makespan']/best,
            reduction_percent=100*(1-best/ref['baseline_makespan']),selected_candidate=selected['candidate'],failed_slots=8-len(good))
        for arm in ('B','C'):
            armgood=[r['makespan'] for r in good if r['arm']==arm]
            record[arm+'_best']=min(armgood) if armgood else None
            record[arm+'_protected']=min([ref['baseline_makespan']]+armgood)
        comparisons.append(record)
        if n==5:print(case,'audited',flush=True)
    summary=[]
    for n in m['cores']:
        group=[r for r in comparisons if r['cores']==n]
        old=sum(r['baseline_speedup'] for r in group)/100;new=sum(r['speedup'] for r in group)/100
        summary.append(dict(cores=n,cases=100,baseline_mean_speedup=old,mean_speedup=new,relative_gain_percent=100*(new/old-1),
            improved=sum(r['reduction_percent']>0 for r in group),meaningful_ge_1_percent=sum(r['reduction_percent']>=1 for r in group),
            unchanged=sum(r['reduction_percent']==0 for r in group),mean_time_reduction_percent=sum(r['reduction_percent'] for r in group)/100))
        assert abs(new-read(ROOT/'summary.json')[str(n)]['mean_speedup'])<1e-12
    routes=[]
    for route in sorted({r['route'] for r in comparisons}):
        group=[r for r in comparisons if r['route']==route and r['cores']==5]
        if group:routes.append(dict(route=route,cases=len(group),improved=sum(r['reduction_percent']>0 for r in group),
            mean_time_reduction_percent=sum(r['reduction_percent'] for r in group)/len(group),
            C_worse_than_baseline=sum(r['C_best'] is not None and r['C_best']>r['baseline_makespan'] for r in group)))
    counts=Counter(r['status'] for r in rows)
    costs=dict(wall_seconds=sum(s['seconds'] for s in m['sessions']),generation_seconds=sum(r['generation_seconds'] for r in rows),
        evaluation_seconds=sum(r['evaluation_seconds'] for r in rows),reused_slots=sum(r['evaluation_reused'] for r in rows),
        new_successful_evaluations=sum(r['status']=='success' and not r['evaluation_reused'] for r in rows),
        evaluation_attempts=sum(r['evaluation_seconds']>0 for r in rows))
    table('comparison.csv',comparisons);table('mean_speedup.csv',summary);table('routes_n5.csv',routes)
    table('candidates.csv',[{k:r.get(k) for k in ('case','cores','candidate','arm','status','makespan','generation_seconds','evaluation_seconds','evaluation_reused','spill_added_copy_bytes')} for r in rows])
    save(OUT/'failures.json',failures);save(OUT/'audit.json',dict(passed=True,status_counts=dict(counts),configurations=400,slots=3200,
        coverage=True,source_hashes=True,plan_legality=True,memory=True,tensor_boundary_difference=True,selection=True,reuse_provenance=True,costs=costs))
    save(OUT/'selection.json',selections)
    lines=['# 第一问 v012 全量结果（exp137）','',
        f"100图×2～5核全部覆盖，3200候选槽状态完整：{dict(counts)}。400组均有合法保底/入选方案，但存在失败候选，不称候选全部通过。",'',
        '|核数|旧平均加速比|新平均加速比|相对提升|改善/持平|耗时下降≥1%的图|','|---|---:|---:|---:|---:|---:|']
    for r in summary:lines.append(f"|{r['cores']}|{r['baseline_mean_speedup']:.6f}|{r['mean_speedup']:.6f}|{r['relative_gain_percent']:.2f}%|{r['improved']}/{r['unchanged']}|{r['meaningful_ge_1_percent']}|")
    lines+=['','平均加速比是100张图逐图single_makespan/makespan的算术平均；均值的相对提升不等同于逐图耗时平均下降。保留v009保证最终不退步，不意味着B/C直接候选不会变差。','',
        '## 五核结构路线','', '|路线|图数|最终改善|逐图耗时平均下降|C直接最优仍比基线慢|','|---|---:|---:|---:|---:|']
    for r in routes:lines.append(f"|{r['route']}|{r['cases']}|{r['improved']}|{r['mean_time_reduction_percent']:.2f}%|{r['C_worse_than_baseline']}|")
    lines+=['','## 失败与成本','',f"完整失败明细见failures.json；共{len(failures)}槽，对应{len({(r['case'],r['cores']) for r in failures})}个图/核数组合。失败的图未从均值分母剔除，均可保留基线。生成30秒、评估180秒，无终态失败自动重试。",'',
        f"执行墙钟{costs['wall_seconds']/3600:.3f}小时；生成{costs['generation_seconds']:.3f}秒，评估{costs['evaluation_seconds']:.3f}秒，{costs['evaluation_attempts']}次新增评估尝试、{costs['new_successful_evaluations']}次成功、{costs['reused_slots']}复用槽。不含历史基线搜索、准备与本次审计。",'',
        '## 判断与边界','',
        '五核3.413601→3.583728，优化有可保留的全量收益，但仍未达到4倍。应保留旧基线+B/C择优组合；不能用C单独替换旧方案。进一步优化应先分析失败候选的成本与收益、C仍退化的路线及五核低分图，不宜仅增加相同局部搜索次数。',
        '本轮算法/参数沿用exp133冻结v012。23张五核低分图已有开发/后续检验及历史复用，全量不是100张完全独立的新测试。未将仅开发六图探索的v010/v011局部方案混入统一组合；case_046需与上一轮局部最优单独比较。',
        '本轮全部3200槽覆盖/来源哈希、方案合法性、B固定分区、C同配置各设置分区一致、成功结果容量/时间/哈希、按张量边界搬运差值、复用来源与400组择优通过核验。原08_full结果保留，未覆盖原评估器、输入和配置。', '',
        'plans/保存400份入选方案；comparison.csv为逐配置对照；mean_speedup.csv为分核均值；candidates.csv/ failures.json包括负候选和失败；audit.json记录成本和审计。',
        '复现审计：python -B A题/solution/experiments/report_problem1_structural_full.py','']
    lines += ['', '补充说明：路线空白的一图为case_085，C全部生成超时，无法从生成记录归类；其五核改善来自B。',
        'case_046五核本轮统一组合保留140604 cycles，上一轮局部最优为131924 cycles；两套选择池不同，本轮没有取代这份更快的历史局部方案。',
        '五核仅baseline+B平均3.430631，仅baseline+C为3.574712，全部择优3.583728。主要增益来自重切分，B仍提供互补。',
        '41个超时槽的生成加评估耗时4894.463秒，约占执行墙钟33.6%；24次评估超时只有8个不同图/核数/方案组合。下一轮可先处理重复超时成本，再决定是否追加大图预算，不改变本轮已冻结结果。', '']
    (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    shutil.copy2(Path(__file__),OUT/Path(__file__).name)
    print({'summary':summary,'counts':dict(counts),'costs':costs,'routes':routes},flush=True)


if __name__=='__main__':main()
