"""Frozen v004 transfer check: structural selection, 2--5 cores, no tuning."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from collections import defaultdict

sys.dont_write_bytecode=True
S=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(S/'src'))
from graph_analysis import Graph
from component_scheduler import independent_components
from scene_b_window_components import make_plan
from process_runner import run_command
from result_paths import result_path
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

BASE=result_path('problem_3/v003/exp121_20260926_v003_full')
PILOT=result_path('problem_3/v004/exp123_20260926_window_pilot')
OUT=result_path('problem_3/v004/exp124_20260926_window_transfer')
EXCLUDE={'case_054','case_069','case_001','case_013','case_026','case_044'}


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')


def sources():
    return [Path(__file__),S/'src/scene_b_window_components.py',S/'src/scene_b_window_components.LICENSE',
        S/'src/graph_analysis.py',S/'src/component_scheduler.py',S/'src/baseline.py',
        *[S/'experiments'/p for p in ('process_runner.py','result_paths.py','run_problem3_pair.py','run_problem2.py')],
        *sorted((S.parent/'code').glob('*.py'))]


def prepare():
    # Fail before selection/evaluation if frozen algorithm or Graph changed.
    old=read(PILOT/'manifest.json')
    for p in (S/'src/scene_b_window_components.py',S/'src/graph_analysis.py'):
        assert sha(p)==old['hashes_before'][str(p)]
    OUT.mkdir(parents=True,exist_ok=False)
    for name in ('inputs','source','plans','metrics','logs','selected_plans'):(OUT/name).mkdir()
    features=[]
    for path in sorted((S.parent/'data').glob('case_*.json')):
        g=Graph(read(path));depth={}
        for op in g.order:depth[op]=1+max((depth[p] for p in g.preds[op]),default=0)
        features.append({'case':path.stem,'ops':len(g.ops),'components':len(independent_components(g)),
            'depth':max(depth.values()),'max_tensor_bytes':max(t['size'] for t in g.data['tensors'])})
    # Size quartiles of eligible cases, then connected/disconnected median-size representative.
    eligible=sorted((r for r in features if r['case'] not in EXCLUDE),key=lambda r:(r['ops'],r['case']))
    selected=[]
    for q in range(4):
        band=eligible[len(eligible)*q//4:len(eligible)*(q+1)//4]
        for connected in (True,False):
            group=[r for r in band if (r['components']==1)==connected]
            if group:
                row=dict(group[len(group)//2]);row.update(size_quartile=q+1,connected=connected)
                selected.append(row)
        # If one connectivity stratum is empty, select the other size extreme as a second representative.
        if sum(r['size_quartile']==q+1 for r in selected)==1:
            other=max((r for r in band if r['case'] not in {x['case'] for x in selected}),key=lambda r:(r['max_tensor_bytes'],r['case']))
            row=dict(other);row.update(size_quartile=q+1,connected=row['components']==1,fallback='largest tensor in quartile')
            selected.append(row)
    assert len(selected)==8 and len({r['case'] for r in selected})==8
    save(OUT/'features.json',features)
    for p in sources():shutil.copy2(p,OUT/'source'/p.name)
    bm=read(BASE/'manifest.json')
    assert read(BASE/'summary.json')['audit']=='passed'
    for p,h in bm['hashes_before'].items():
        path=Path(p)
        if path.parent==S.parent/'code' or path.name=='config.txt':assert sha(path)==h
    rows={(r['case'],int(r['cores'])):r for r in csv.DictReader((BASE/'comparison.csv').open(encoding='utf-8-sig'))}
    items={(r['case'],r['cores']):r for r in bm['items']}
    manifest={'problem':3,'version':'v004','experiment':OUT.name,'status':'prepared','selected_cases':selected,
        'excluded_pilot':sorted(EXCLUDE),'scope':'post-hoc structural transfer check; all 100 cases were previously evaluated with v003',
        'selection_rule':'remaining cases size quartiles x connectivity; median size per stratum, largest tensor fallback',
        'cores':[2,3,4,5],'windows':[4,10,16],'sticky':0.5,'seed':None,
        'candidate_rule':'minimum Cache makespan among v003 and 3 windows; ties baseline then smaller window',
        'gate':'all 32 configurations complete and audit passes; >=4 configurations improve >=1%, spanning >=2 size quartiles and >=2 core counts',
        'generation_timeout_seconds':30,'evaluation_timeout_seconds':180,
        'upstream_cost':'baseline and prior tuning costs excluded, not zero',
        'base_manifest_sha256':sha(BASE/'manifest.json'),'base_comparison_sha256':sha(BASE/'comparison.csv'),
        'items':[],'invocations':[],'hashes_before':{str(p):sha(p) for p in sources()}}
    shutil.copy2(S.parent/'data/config.txt',OUT/'inputs/config.txt')
    for row in selected:
        case=row['case'];graph=S.parent/'data'/f'{case}.json'
        assert sha(graph)==sha(BASE/'inputs'/graph.name)
        shutil.copy2(graph,OUT/'inputs'/graph.name)
        manifest['hashes_before'][str(graph)]=sha(graph)
        for n in manifest['cores']:
            r=rows[case,n];old=items[case,n]['candidates'][r['selected']]
            stem=f'{case}_n{n}_baseline';plan=BASE/'selected_plans'/f'{case}_n{n}.json'
            assert sha(plan)==r['plan_sha256']==old['generation'][-1]['sha256']
            shutil.copy2(plan,OUT/'plans'/f'{stem}.json')
            item={'case':case,'cores':n,'size_quartile':row['size_quartile'],'candidates':{},'baseline_origin':r}
            for mode in ('cache','no_l2'):
                rec=old['evaluations'][mode][-1];src=BASE/rec['file']
                assert rec['status']=='success' and sha(src)==rec['sha256']
                shutil.copy2(src,OUT/'metrics'/f'{stem}_{mode}.json')
            manifest['items'].append(item)
    manifest['hashes_before'][str(S.parent/'data/config.txt')]=sha(S.parent/'data/config.txt')
    manifest['archive_hashes']={str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file()}
    save(OUT/'manifest.json',manifest)
    print(json.dumps({'selected':selected,'output':str(OUT)},ensure_ascii=False),flush=True)


def verify(m):
    assert all(sha(Path(p))==h for p,h in m['hashes_before'].items())
    assert all(sha(OUT/p)==h for p,h in m['archive_hashes'].items())
    for item in m['items']:
        for candidate in item['candidates'].values():
            for rec in candidate.values():
                if rec['status']=='success':assert sha(OUT/rec['file'])==rec['sha256']


def run():
    m=read(OUT/'manifest.json');verify(m)
    m['status']='running';m['invocations'].append([sys.executable,*sys.argv]);save(OUT/'manifest.json',m)
    def launch(item,label,mode):
        candidate=item['candidates'].setdefault(label,{})
        if mode in candidate:return candidate[mode] # Failures retained, no silent retry.
        stem=f"{item['case']}_n{item['cores']}_{label}"
        plan=OUT/'plans'/f'{stem}.json'
        graph=OUT/'inputs'/f"{item['case']}.json"
        if mode=='generate':
            dest=plan
            cmd=[sys.executable,str(Path(__file__)),'--worker','--graph',str(graph),'--plan',str(plan),
                 '--cores',str(item['cores']),'--window',label[1:]]
            timeout=30
        else:
            dest=OUT/'metrics'/f'{stem}_{mode}.json'
            cmd=[sys.executable,str(S/'experiments/run_problem3_pair.py'),'--worker',mode,
                '--graph',str(graph),'--plan',str(plan),'--config',str(OUT/'inputs/config.txt'),'--result',str(dest)]
            timeout=180
        rec=run_command(cmd,OUT/'logs'/f'{stem}_{mode}.txt',timeout)
        if rec['status']=='success':
            rec.update(file=str(dest.relative_to(OUT)),sha256=sha(dest))
            if mode!='generate':rec['makespan']=read(dest)['makespan']
        candidate[mode]=rec;save(OUT/'manifest.json',m)
        return rec
    for item in m['items']:
        case,n=item['case'],item['cores']
        for w in m['windows']:
            if launch(item,f'w{w}','generate')['status']=='success':launch(item,f'w{w}','cache')
        options=[(read(OUT/'metrics'/f'{case}_n{n}_baseline_cache.json')['makespan'],0,'baseline')]
        for w in m['windows']:
            rec=item['candidates'][f'w{w}'].get('cache',{})
            if rec.get('status')=='success':options.append((rec['makespan'],w,f'w{w}'))
        best=min(options)
        if best[2]!='baseline':launch(item,best[2],'no_l2')
        item['selected']=best[2];save(OUT/'manifest.json',m)
        print(case,n,'selected',best[2],'makespan',best[0],flush=True)
    verify(m)
    m['status']='evaluated';save(OUT/'manifest.json',m)


def report():
    m=read(OUT/'manifest.json');verify(m)
    rows=[];direct=[];failures=[]
    assert len(m['items'])==32
    for item in m['items']:
        case,n=item['case'],item['cores'];stem=f'{case}_n{n}'
        base=read(OUT/'metrics'/f'{stem}_baseline_cache.json')
        options=[(base['makespan'],0,'baseline')]
        for w in m['windows']:
            label=f'w{w}';records=item['candidates'][label]
            for mode,rec in records.items():
                if rec['status']!='success':failures.append({'case':case,'cores':n,'label':label,'mode':mode,'status':rec['status']})
            if records.get('cache',{}).get('status')!='success':continue
            plan=read(OUT/'plans'/f'{stem}_{label}.json')
            validate_task_order(derive_multicore_plan(read(OUT/'inputs'/f'{case}.json'),plan))
            value=read(OUT/records['cache']['file'])['makespan']
            options.append((value,w,label));direct.append(value/base['makespan'])
        chosen=min(options);assert item['selected']==chosen[2]
        label=chosen[2]
        cache=read(OUT/'metrics'/f'{stem}_{label}_cache.json')
        no_path=OUT/'metrics'/f'{stem}_{label}_no_l2.json'
        if not no_path.exists():continue
        no=read(no_path)
        assert no['data_movement_bytes']==cache['data_movement_bytes']
        assert cache['num_cores']==n and 0<=cache['cache_stats']['hit_rate']<=1
        plan=OUT/'plans'/f'{stem}_{label}.json'
        validate_task_order(derive_multicore_plan(read(OUT/'inputs'/f'{case}.json'),read(plan)))
        shutil.copy2(plan,OUT/'selected_plans'/f'{stem}.json')
        rows.append({'problem':3,'version':'v004','experiment':OUT.name,'case':case,'cores':n,'size_quartile':item['size_quartile'],
            'selected':label,'baseline_cache':base['makespan'],'selected_cache':cache['makespan'],'selected_no_l2':no['makespan'],
            'reduction_percent':100*(1-cache['makespan']/base['makespan']),
            'schedule_speedup':base['makespan']/cache['makespan'],'cache_speedup':no['makespan']/cache['makespan'],
            'cache_hit_rate':cache['cache_stats']['hit_rate'],'added_copy_bytes':cache['data_movement_bytes']['added_copy_bytes'],
            'spill_bytes':cache['data_movement_bytes']['spill_added_copy_bytes'],'plan_sha256':sha(plan)})
    successes=[r for r in rows if r['reduction_percent']>=1]
    passed=(not failures and len(rows)==32 and len(direct)==96 and len(successes)>=4
        and len({r['size_quartile'] for r in successes})>=2 and len({r['cores'] for r in successes})>=2)
    costs={mode:sum(rec['seconds'] for i in m['items'] for c in i['candidates'].values() for k,rec in c.items() if k==mode) for mode in ('generate','cache','no_l2')}
    summary={'audit':'passed' if not failures and len(rows)==32 and len(direct)==96 else 'incomplete','gate_passed':passed,
        'configurations':len(rows),'improved':sum(r['reduction_percent']>0 for r in rows),'unchanged':sum(r['reduction_percent']==0 for r in rows),
        'direct_fast':sum(v<1 for v in direct),'direct_equal':sum(v==1 for v in direct),'direct_slow':sum(v>1 for v in direct),
        'improved_at_least_1pct':len(successes),'size_quartiles_with_1pct_gain':sorted({r['size_quartile'] for r in successes}),
        'core_counts_with_1pct_gain':sorted({r['cores'] for r in successes}),'failures':failures,'costs':costs,
        'actual_evaluations':sum(k!='generate' for i in m['items'] for c in i['candidates'].values() for k in c),
        'mean_reduction_by_cores':{n:sum(r['reduction_percent'] for r in rows if r['cores']==n)/8 for n in (2,3,4,5)}}
    with (OUT/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    save(OUT/'summary.json',summary)
    lines=['# v004 后续结构分层检验','', '8图×2～5核，共32配置。固定window=4/10/16、sticky=0.5，与原v003方案择优；所有失败及退化候选均保留。',
        '', '这8图不在v004开发六图内；选择只用静态规模/连通性。所有图此前已用于v003全量，因此不是完全独立测试集。',
        '',f"审计：{summary['audit']}；预先规定的全量进入门槛：{passed}。门槛要求全部成功、至少4配置降幅≥1%，覆盖≥2规模组及≥2核数。",
        '',f"择优后{summary['improved']}改善、{summary['unchanged']}持平。96直接候选{summary['direct_fast']}快、{summary['direct_equal']}平、{summary['direct_slow']}慢。",
        '', '|用例|规模四分位|核数|原耗时|择优耗时|耗时下降|候选|','|---|---:|---:|---:|---:|---:|---|']
    lines.extend(f"|{r['case']}|{r['size_quartile']}|{r['cores']}|{r['baseline_cache']}|{r['selected_cache']}|{r['reduction_percent']:.2f}%|{r['selected']}|" for r in rows)
    lines+=['',f"新增评估{summary['actual_evaluations']}次；生成累计{costs['generate']:.3f}秒，Cache评估{costs['cache']:.3f}秒，入选方案无L2评估{costs['no_l2']:.3f}秒。复用64份基线指标，旧搜索成本非零。",'',
        '8图每核降幅均值仅描述本组，不外推100图平均。v004源代码与开发试验快照一致；原始评估器、输入与固定配置哈希一致。源代码及MIT许可均有快照。', '',
        '下一步：通过门槛则具备启动冻结算法全量验收的依据；本轮本身不等于全量验收。', '',
        '复现（仓库根目录，prepare拒绝覆盖历史目录；run可续跑且保留失败）：', '', '```powershell',
        "& 'A题/.venv/Scripts/python.exe' 'A题/solution/experiments/validate_problem3_window_components.py' prepare",
        "& 'A题/.venv/Scripts/python.exe' 'A题/solution/experiments/validate_problem3_window_components.py' run",
        "& 'A题/.venv/Scripts/python.exe' 'A题/solution/experiments/validate_problem3_window_components.py' report",'```']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    save(OUT/'audit.json',{'manifest_sha256':sha(OUT/'manifest.json'),'summary_sha256':sha(OUT/'summary.json'),'status':summary['audit']})
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',nargs='?',choices=['prepare','run','report']);p.add_argument('--worker',action='store_true')
    p.add_argument('--graph');p.add_argument('--plan');p.add_argument('--cores',type=int);p.add_argument('--window',type=int)
    a=p.parse_args()
    if a.worker:save(Path(a.plan),make_plan(read(Path(a.graph)),a.cores,a.window,0.5))
    elif a.action:globals()[a.action]()
    else:p.error('action required')
