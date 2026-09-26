"""Post-run verification and reporting for the bounded Q1 critical-chain pilot."""
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import shutil
import sys
from probe_problem1_critical_local import A_ROOT, SOLUTION, ROOT as PILOT, read, save, sha, write_csv
from probe_problem1_critical_merge import ROOT as REFINEMENT
from scene_a_critical_local import diagnose
from portfolio_scheduler import validate_result
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan


def ddr_detail(result):
    """Identify DDR operations from evaluator issue logs, not COPY names."""
    issued = [(e['issued']['task_id'],e['issued']['op_id']) for e in result['ddr_contention_log']]
    assert len(issued) == len(set(issued))
    ddr = set(issued)
    diagnostic = diagnose(result)
    by_task = defaultdict(list)
    global_events = defaultdict(int)
    observed = set()
    for c in result['per_core_timeline']:
        for op in c['ops']:
            key = (op['task_id'],op['op_id']); observed.add(key)
            kind = 1 if op['pipe'] in ('PIPE_M','PIPE_V') else 2 if key in ddr else 4
            by_task[op['task_id']].append((op['start'],op['end'],kind))
            if key in ddr:
                global_events[op['start']] += 1; global_events[op['end']] -= 1
    assert ddr <= observed
    totals = Counter()
    for task in diagnostic['chain']:
        events = defaultdict(lambda:Counter())
        t = diagnostic['tasks'][task]
        events[t['start']];events[t['end']]
        for start,end,kind in by_task[task]:
            events[start][kind]+=1;events[end][kind]-=1
        active=Counter(); previous=t['start']
        for time in sorted(events):
            mask=sum(k for k,v in active.items() if v>0)
            totals[mask]+=time-previous
            active.update(events[time]); previous=time
    active=0;previous=0;busy=0;contended=0
    for time,delta in sorted(global_events.items()):
        if active: busy+=time-previous
        if active>1: contended+=time-previous
        active+=delta;previous=time
    assert active==0
    assert sum(totals.values()) + diagnostic['chain_breakdown']['cross_wait'] + diagnostic['chain_breakdown']['same_wait']==result['makespan']
    return {'compute_only':totals[1],'ddr_only':totals[2],'other_transfer_only':totals[4],
        'compute_ddr_overlap':totals[3],'compute_other_overlap':totals[5],'ddr_other_overlap':totals[6],
        'all_overlap':totals[7],'inactive':totals[0],
        'cross_wait':diagnostic['chain_breakdown']['cross_wait'],'same_wait':diagnostic['chain_breakdown']['same_wait'],
        'global_ddr_busy_cycles':busy,'global_ddr_contended_cycles':contended}


def check_local_scope(base,candidate,edit):
    if 'merged_tasks' in edit: changed=set(edit['merged_tasks'])
    else: changed={edit.get('split_task',edit.get('moved_task'))}
    for n,t in base['node_to_subgraph'].items():
        if t not in changed: assert candidate['node_to_subgraph'][n]==t
    untouched=set(base['node_to_subgraph'].values())-changed
    for old,new in zip(base['core_schedules'],candidate['core_schedules']):
        assert [t for t in old if t in untouched]==[t for t in new if t in untouched]


def main():
    records=read(PILOT/'evaluations.json')
    refined=read(REFINEMENT/'evaluations.json')
    for root in (PILOT,REFINEMENT):
        manifest=read(root/'manifest.json')
        assert manifest['status']=='completed' and manifest['protected_unchanged']
        for p,h in manifest['protected_hashes'].items(): assert sha(A_ROOT/p)==h
        source_hashes=manifest.get('frozen_sources',manifest.get('source_hashes'))
        for p,h in source_hashes.items(): assert sha(SOLUTION/p)==h
    baseline={r['case']:r for r in records if r['candidate']=='baseline'}
    for root in (PILOT/'runs',REFINEMENT):
        for folder in root.iterdir():
            if folder.is_dir() and (folder/'generation_process.json').exists():
                assert read(folder/'generation_process.json')['status']=='success'
                assert all(c['status']=='generated' for c in read(folder/'generation.json')['candidates'])
    for case in baseline:
        archived=read(PILOT/'baseline'/f'{case}_result.json')
        fresh=read(PILOT/'runs'/case/'baseline/result.json')
        # CLI records the plan basename; exported baseline has a different name.
        assert {k:v for k,v in archived.items() if k!='input_plan'}=={k:v for k,v in fresh.items() if k!='input_plan'}
    candidate_counts=Counter(); outcomes=Counter(); all_records=[]
    for root,items in ((PILOT,records),(REFINEMENT,refined)):
        for record in items:
            case,name=record['case'],record['candidate']
            folder=(root/'runs'/case/name) if root==PILOT else root/case/name
            plan_path=PILOT/'baseline'/f'{case}_plan.json' if name=='baseline' else folder/'plan.json'
            plan=read(plan_path); result=read(folder/'result.json')
            assert sha(plan_path)==record['plan_sha256']
            assert sha(folder/'result.json')==record['result_sha256']
            assert record['status']=='success'
            assert validate_result(result,5)['makespan']==record['makespan']
            validate_task_order(derive_multicore_plan(read(A_ROOT/f'data/{case}.json'),plan))
            if name!='baseline':
                generation=read(folder.parent/'generation.json')
                edit=next(c['edit'] for c in generation['candidates'] if c['candidate']==name)
                check_local_scope(read(PILOT/'baseline'/f'{case}_plan.json'),plan,edit)
                delta=record['makespan']-baseline[case]['makespan']
                outcomes['faster' if delta<0 else 'slower' if delta>0 else 'equal']+=1
                candidate_counts[str(root.name)]+=1
            all_records.append({k:record.get(k,'') for k in ('problem','algorithm_version','experiment','case','cores','candidate','status','makespan','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes','seconds')})
    for root,items in ((PILOT,records),(REFINEMENT,refined)):
        for selected in read(root/'selection.json'):
            case=selected['case']
            expected=min([baseline[case]['makespan']]+[r['makespan'] for r in items if r['case']==case])
            assert selected['makespan']==expected
            selected_result=(root/'selected'/f'{case}_n5_result.json') if root==PILOT else root/case/'selected_result.json'
            assert read(selected_result)['makespan']==expected
    rows=list(csv.DictReader((PILOT/'diagnosis.csv').open(encoding='utf-8-sig')))
    details=[]
    for row in rows:
        case=row['case'];d=ddr_detail(read(PILOT/'baseline'/f'{case}_result.json'))
        details.append({'case':case,'cores':5,'makespan':int(row['baseline_makespan']),**d})
    write_csv(PILOT/'ddr_diagnosis.csv',details)
    # Combine only experimentally evaluated choices; do not invent untested scores.
    combined=[]
    for case,base in baseline.items():
        choices=[r for r in records+refined if r['case']==case]
        winner=min(choices,key=lambda r:(r['makespan'],r['candidate']!='baseline',r['candidate']))
        old=next(r for r in rows if r['case']==case)
        combined.append({'case':case,'cores':5,'baseline_makespan':base['makespan'],'makespan':winner['makespan'],
            'candidate':winner['candidate'],'algorithm_version':winner['algorithm_version'],
            'reduction_percent':100*(1-winner['makespan']/base['makespan']),
            'baseline_speedup':int(old['single_makespan'])/base['makespan'],'speedup':int(old['single_makespan'])/winner['makespan'],
            'baseline_added_copy_bytes':base['added_copy_bytes'],'added_copy_bytes':winner['added_copy_bytes']})
    destination=SOLUTION/'outputs/11_problem1_local_pilot'
    destination.mkdir(exist_ok=True)
    write_csv(destination/'comparison.csv',combined)
    write_csv(destination/'all_evaluations.csv',all_records)
    shutil.copy2(PILOT/'diagnosis.csv',destination/'diagnosis.csv')
    shutil.copy2(PILOT/'ddr_diagnosis.csv',destination/'ddr_diagnosis.csv')
    final_dir=destination/'plans';final_dir.mkdir(exist_ok=True)
    for row in combined:
        case,name=row['case'],row['candidate']
        origin=PILOT/'baseline'/f'{case}_plan.json' if name=='baseline' else (
            REFINEMENT/case/name/'plan.json' if row['algorithm_version']=='v011' else PILOT/'runs'/case/name/'plan.json')
        shutil.copy2(origin,final_dir/f'{case}_n5.json')
        assert sha(origin)==sha(final_dir/f'{case}_n5.json')
    generation_seconds=sum(read(folder/'generation.json')['seconds'] for root in (PILOT/'runs',REFINEMENT)
        for folder in root.iterdir() if folder.is_dir() and (folder/'generation.json').exists())
    audit={'passed':True,'diagnosed_cases':len(rows),'pilot_cases':len(baseline),'baseline_json_reproduced_except_input_plan_basename':len(baseline),
        'new_evaluations':len(records)+len(refined),'new_candidates':sum(candidate_counts.values()),'direct_outcomes':dict(outcomes),
        'candidate_counts':dict(candidate_counts),'generation_seconds':generation_seconds,
        'evaluation_seconds':sum(r['seconds'] for r in records+refined),'protected_unchanged':True,
        'local_edit_scope_verified':True,'selected':combined,
        'boundary':'6 outcome-selected five-core cases; post-hoc refinement; no unseen validation or 100-graph re-evaluation; historical baseline search costs excluded'}
    save(destination/'audit.json',audit)
    lines=['# 第一问：关键路径诊断与局部切图小试验','',
        '结论：方向有局部实测收益，但本轮提升有限，不支持宣称全量可达到4倍。第一问正式全量仍为v009、五核平均3.413600911。','',
        '## 范围与方法','',
        '- 从正式结果中取五核加速比<2的23图，核验归档方案/结果哈希并重建任务关键链。链包含数据依赖、同核顺序以及1000/100周期等待；实测任务持续时间带有带宽争用影响，不是无争用下界。',
        '- 从关键链跨核等待、仅搬运、仅计算占比三项各选两图，选样在新候选评估前冻结；为按旧结果选择的开发样本，不是独立测试集。',
        '- exp131/v010：关键依赖边合并、最大关键任务局部拆分、迁移到较空闲核，共28个实际候选。保持其余任务归属、分核与相对顺序。',
        '- 首轮搬运型图未改善，发现关键同核相邻任务不一定有直接依赖；exp132/v011针对原两张搬运图补测3个相邻合并候选，按可节约的切分COPY字节排序。属于事后开发修正，单独保留版本。',
        '- 每个候选均用原始第一问评估器及固定config，5核，生成30秒/评估180秒预算，不重试；保留旧方案。','',
        '## 代表图结果','',
        '| 图 | 原Makespan | 新Makespan | 耗时降幅 | 五核加速比变化 | 入选操作 |',
        '|---|---:|---:|---:|---:|---|']
    for r in combined:
        lines.append(f"| {r['case']} | {r['baseline_makespan']} | {r['makespan']} | {r['reduction_percent']:.4f}% | {r['baseline_speedup']:.4f} → {r['speedup']:.4f} | {r['candidate']} |")
    lines += ['', 'case_046首轮split_4仅减少1 cycle，同时增加40960 bytes额外搬运，不视为有意义改善；补测合并后出现实际收益。所有持平与退化候选均保留在all_evaluations.csv。', '',
        '## 瓶颈证据与限制','']
    for case in baseline:
        d=next(r for r in details if r['case']==case);old=next(r for r in rows if r['case']==case)
        lines.append(f"- {case}：基线关键链跨核等待 {d['cross_wait']/d['makespan']:.2%}，仅DDR搬运 {d['ddr_only']/d['makespan']:.2%}，仅计算 {d['compute_only']/d['makespan']:.2%}；五核任务占用率 {float(old['task_busy_fraction']):.2%}。")
    lines += ['',
        'DDR操作通过原评估器ddr_contention_log的发射ID与真实时间线匹配识别，不把所有MTE操作都当作DDR。ddr_diagnosis.csv按计算/DDR/其他搬运的互斥组合计时；重叠时间另列。全局DDR争用时间表示同时有多个DDR操作在飞，不等于可以消除的耗时。',
        '低核占用并不证明任务可以无代价拆开。局部候选改变了切分粒度、内存复用与等待，效果必须看总Makespan；不是搬运字节越少就一定越快。',
        '本轮没有等预算随机/非关键路径对照，不能把观察到的收益唯一归因于关键路径引导，也不是某篇指定论文算法的复现。未对其余17张低分图实施搜索，未更新100图正式均值。','',
        '## 验证与成本','',
        f"- 6份旧基线重新计算后，除input_plan文件名外全部JSON字段与归档完全一致；共{audit['new_evaluations']}次新增评估，全部成功，无生成或评估超时。",
        f"- {audit['new_candidates']}个新候选直接对比旧基线：{outcomes['faster']}快、{outcomes['equal']}平、{outcomes['slower']}慢。最终不退步来自保留基线，不代表新操作单独不退步。",
        f"- 候选生成内计时累计{generation_seconds:.3f}秒；新增评估子进程累计{audit['evaluation_seconds']:.3f}秒。包含6次基线复算，不含历史v009搜索、初次诊断与审计耗时。",
        '- 核验原始代码/配置/23图输入未改、源文件冻结哈希、候选合法性、局部修改范围、内存容量、指标哈希、逐图最优选择及交付方案。',
        '- 4项针对性测试通过：占用重叠不重复累计、关键链等待与未解释间隙、非凸合并成环拒绝、无直接依赖的相邻任务共享输入合并。',
        '- exp130初次准备因原归档CRLF与当前LF源码字节哈希不同而停止，未运行评估；重建CRLF后所有原代码哈希完全匹配。exp131记录这一等价核验，并复算基线，不把差异悄悄忽略。','',
        '## 下一步','',
        '先冻结候选策略，再从剩余17张低分图中按同类结构选择后续检验图；优先改进等待密集图的多任务协同合并，以及大任务内部的分支切分。当前一次修改一个局部区域的搜索幅度小，不能承诺将3.41提高到4以上。','',
        '## 复现与原始记录','',
        f'- 首轮：`{PILOT}`',f'- 补测：`{REFINEMENT}`',
        '- 入口：`experiments/probe_problem1_critical_local.py --prepare`，然后`--run`；补测入口`experiments/probe_problem1_critical_merge.py`。再次实验必须使用新的实验编号，现有入口拒绝覆盖。',
        '- 审计：`python -B experiments/audit_problem1_critical_pilot.py`。统一使用`A题/.venv/Scripts/python.exe`。','']
    (destination/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
