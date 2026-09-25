"""Independent audit/report of fixed-placement Q3 ordering reserve evaluation."""
import csv
import json
from pathlib import Path
import shutil
import sys
from fractions import Fraction
from run_problem2 import save
from run_problem3_pair import sha,valid_record


def main():
    out=Path(sys.argv[1])
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['status'].startswith('completed')
    for path,digest in manifest['source_hashes_before'].items():assert sha(path)==digest
    assert manifest['source_hashes_before']==manifest['source_hashes_after']
    for rel,digest in manifest['artifact_hashes'].items():assert sha(out/rel)==digest
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    rows=list(csv.DictReader((out/'comparison.csv').open(encoding='utf-8-sig')))
    assert len(rows)==30 and len({(r['case'],r['cores']) for r in rows})==30
    rowmap={(r['case'],int(r['cores'])):r for r in rows}
    raw={'cache_affinity':{'faster':0,'same':0,'slower':0,'failed':0},'critical_path':{'faster':0,'same':0,'slower':0,'failed':0}}
    changes=[];selected=[];regressions=[]
    (out/'selected_plans').mkdir(exist_ok=True)
    def result(candidate,mode):return json.loads((out/candidate['evaluations'][mode]['result']).read_text(encoding='utf-8'))
    for item in manifest['items']:
        candidates=item['candidates'];base=candidates['baseline'];bp=json.loads((out/base['plan']).read_text(encoding='utf-8'))
        base_time=result(base,'cache')['makespan']
        for name,candidate in candidates.items():
            if candidate['status']!='success':
                if name in raw:raw[name]['failed']+=1
                continue
            plan=json.loads((out/candidate['plan']).read_text(encoding='utf-8'))
            assert plan['node_to_subgraph']==bp['node_to_subgraph']
            assert [set(x) for x in plan['core_schedules']]==[set(x) for x in bp['core_schedules']]
            for rec in candidate['evaluations'].values():assert valid_record(rec,out)
            measured=result(candidate,'cache')['makespan']
            if name in raw:raw[name]['faster' if measured<base_time else 'slower' if measured>base_time else 'same']+=1
            if name=='cache_affinity' and measured>base_time:
                regressions.append({'case':item['case'],'cores':item['cores'],
                    'baseline':base_time,'candidate':measured,'increase_fraction':measured/base_time-1})
        valid=[name for name in ('baseline','cache_affinity') if candidates[name]['status']=='success']
        pick=min(valid,key=lambda name:(result(candidates[name],'cache')['makespan'],name!='baseline'))
        row=rowmap[item['case'],item['cores']]
        assert row['affinity_pick']==pick
        assert int(row['C_affinity_selected_cache'])==result(candidates[pick],'cache')['makespan']
        assert int(row['D_affinity_selected_no_l2'])==result(candidates[pick],'no_l2')['makespan']
        selected_path=out/'selected_plans'/f"{item['case']}_n{item['cores']}.json"
        shutil.copy2(out/candidates[pick]['plan'],selected_path)
        selected.append({'case':item['case'],'cores':item['cores'],'candidate':pick,'path':str(selected_path.relative_to(out)),'sha256':sha(selected_path)})
        if pick!='baseline':
            old,new=result(base,'cache'),result(candidates[pick],'cache')
            def first_reads(r):
                times={}
                for e in r['cache_events']:
                    if e['event'] in ('hit','miss'):times.setdefault((e['core_id'],e['tensor_id']),e['time'])
                return times
            before,after=first_reads(old),first_reads(new)
            common=set(before)&set(after)
            changes.append({'case':item['case'],'cores':item['cores'],
                'old_cache_makespan':old['makespan'],'new_cache_makespan':new['makespan'],
                'common_core_tensor_first_reads':len(common),
                'changed_first_read_times':sum(before[k]!=after[k] for k in common),
                'old_added_copy_bytes':old['data_movement_bytes']['added_copy_bytes'],
                'new_added_copy_bytes':new['data_movement_bytes']['added_copy_bytes'],
                'old_hit_rate':old['cache_stats']['hit_rate'],'new_hit_rate':new['cache_stats']['hit_rate']})
    for n in range(1,6):
        part=[r for r in rows if int(r['cores'])==n]
        mean=float(sum((Fraction(int(r['B_old_cache']),int(r['C_affinity_selected_cache'])) for r in part),Fraction(0))/len(part))
        assert mean==summary['by_cores'][n-1]['affinity_mean_speedup']
    save(out/'selected.json',selected)
    save(out/'timeline_changes.json',changes)
    save(out/'audit.json',{'status':'passed','configurations':30,'raw_candidate_counts':raw,
        'source_archive_and_result_hashes_checked':True,'fixed_placement_checked':True,
        'Cache_only_selection_checked':True,'means_fraction_recomputed':True,
        'selected_plan_hashes':{x['path']:x['sha256'] for x in selected}})
    lines=['# 第三问 v002：固定分核的排序优化（预留检验）','',
        f"实验 {out.name}。30 个预留配置；保留 v001 原方案，只改变各核子图顺序，操作归属与分核不变。第三问原始评估器与固定配置不变。",'',
        '## 方法与公平比较','',
        '每核从依赖已满足的前32个原顺序候选中选择子图。cache_affinity按本核近期操作数复用及共享FIFO中的数据估计搬运节省，critical_path使用剩余依赖计算长度。两者都由全局拓扑顺序投影回各核，保持依赖合法。共享FIFO与本核128KB近期集合均为排序代理，不代表真实读取时刻或精确L1/UB驻留；真实收益由原评估器判断。','',
        '主方案为“原基线 + cache_affinity”，对照为“原基线 + critical_path”：每组两个候选，平局保留基线。候选相同会去重，实际耗时未强行配平。三个候选一起取最优仅作为探索记录，不计为与两候选组等预算的优势。每个候选生成30秒，单次评估180秒，无自动重试。','',
        '| 核数 | 主方案较旧Cache平均加速比 | 主方案改善配置数 | 对照改善配置数 | 主方案胜对照 / 对照胜主方案 |',
        '|---|---:|---:|---:|---|']
    for r in summary['by_cores']:
        lines.append(f"| {r['cores']} | {r['affinity_mean_speedup']:.6f} | {r['affinity_improved']}/{r['count']} | {r['control_improved']}/{r['count']} | {r['affinity_beats_control']} / {r['control_beats_affinity']} |")
    lines+=['','这是相对于旧方案已有Cache时的调度优化比值 B/C，不能与第三问规定的同方案Cache加速比 D/C 混用。A/B、B/C、D/C、A/D 均保存在 comparison.csv。','',
        '## 原始候选退步与选择','']
    for name,counts in raw.items():lines.append(f"- {name}：直接候选 {counts['faster']} 快、{counts['same']} 平、{counts['slower']} 慢、{counts['failed']} 失败。")
    lines+=['','主方案选择后不退步是保留基线并按本图原评估器选优的结果，不能说明新排序单独普遍更好。算法不按用例编号选择，所有生成、失败及退步均保留。','',
        '## 具体改善','', '| 用例 | 核数 | 旧Cache | 新Cache | 耗时下降 | 旧命中率 | 新命中率 |','|---|---:|---:|---:|---:|---:|---:|']
    for r in changes:
        lines.append(f"| {r['case']} | {r['cores']} | {r['old_cache_makespan']} | {r['new_cache_makespan']} | {1-r['new_cache_makespan']/r['old_cache_makespan']:.2%} | {r['old_hit_rate']:.2%} | {r['new_hit_rate']:.2%} |")
    if not changes:
        lines+=['','预留30配置没有选中优于baseline的cache_affinity候选，全部保留原基线。']
    lines+=['','## 直接新排序的最大退步','',
        '| 用例 | 核数 | 原Cache耗时 | 新候选耗时 | 耗时增加 |',
        '|---|---:|---:|---:|---:|']
    for r in sorted(regressions,key=lambda x:-x['increase_fraction'])[:6]:
        lines.append(f"| {r['case']} | {r['cores']} | {r['baseline']} | {r['candidate']} | {r['increase_fraction']:.2%} |")
    lines+=['','实际读取时刻变化及额外搬运量见 timeline_changes.json。命中率和耗时不一定同向变化；排序也会改变本核溢出及流水线，因此不能把全部收益归因于共享Cache。',
        '本轮结果不回用于调整算法。A/B/C/D配对用于区分一般排序变化和同方案Cache效果，不将排序收益全部归因于Cache。','',
        '## 成本与证据','',
        f"- 新候选生成累计 {summary['generation_seconds']:.3f} 秒；新增完整评估 {summary['new_evaluations']} 次，累计 {summary['new_evaluation_seconds']:.3f} 秒；生成/评估阶段墙钟 {manifest['wall_seconds']:.3f} 秒，不含汇总和独立审计。",
        '- 复用先前30对基线及相同候选。上游第二问方案搜索、第三问基线成本不为零，本轮时间不是冷启动总成本。',
        '- 配置、源码与归档哈希、每个候选固定分核、完整结果、只按Cache耗时选优和Fraction均值复算已核对。selected_plans/保存主方案30个选优结果。',
        '- 本轮使用在开发性能前选定的6张预留图；v002算法与预算在打开预留成绩前冻结且未调整。该组此前参加过第一、二问，只表示未用于第三问调参，并非外部验证或100图全量结果。固定配置的命中完成后重新插入行为继续沿用并披露。','',
        '完整候选见 candidates.csv 与 manifest.json；完整有/无Cache结果见 metrics/；源码快照见 source/。','']
    (out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    shutil.copy2(__file__,out/'report_problem3_order.py')
    print(json.dumps({'audit':'passed','raw':raw,'improved_selected':len(changes)},ensure_ascii=False))


if __name__=='__main__':main()
