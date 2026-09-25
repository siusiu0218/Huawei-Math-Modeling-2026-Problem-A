"""Audit v011 full results and disclose incremental plus prerequisite costs."""
from collections import Counter
import csv
from datetime import datetime
from fractions import Fraction
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from scene_b_active_cores import select_candidate,pad_plan
from scene_b_portfolio import plan_digest
from portfolio_scheduler import validate_result
from run_problem2_portfolio import sha
from run_problem2_active_cores import verify_cache
EXP=ROOT/'outputs/09_problem2/raw/problem_2/v011/exp109_20260926_active_full'
OUT=ROOT/'outputs/09_problem2/v011_summary_20260926'


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def csvout(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    m=read(EXP/'manifest.json')
    assert m['status']=='completed' and m['protected_unchanged']
    assert len(m['items'])==400 and {(r['case'],r['cores']) for r in m['items']}=={(f'case_{i:03}',n) for i in range(1,101) for n in range(2,6)}
    for rel,d in read(ROOT/'experiments/problem2_v011_selection.json')['source_hashes'].items():assert sha(ROOT/rel)==d,rel
    for rel,d in m['protected_hashes_before'].items():assert sha(ROOT.parent/rel)==d,rel
    for rel,d in m['source_hashes'].items():assert sha(EXP/'source'/rel)==d,rel
    for rel,d in m['output_hashes'].items():assert sha(EXP/rel)==d,rel
    cache=Path(m['cache']['path'])
    assert sha(cache/'manifest.json')==m['cache']['manifest_sha256']
    verify_cache(cache,m['parameters']['cases'])
    old=read(cache/'manifest.json')
    olditems={(r['case'],r['cores']):r for r in old['items']}
    refs={(r['case'],int(r['cores'])):r for r in csv.DictReader((ROOT/'outputs/09_problem2/v010_summary_20260925/comparison.csv').open(encoding='utf-8-sig'))}
    for rel,d in m['protected_hashes_before'].items():assert old['protected_hashes_before'][rel]==d
    comparisons=[];candidates=[];generation=[]
    fresh_eval=0;reused_eval=0;dedup=0;eval_seconds=0
    for r in sorted(m['items'],key=lambda r:(r['case'],r['cores'])):
        c,n=r['case'],r['cores'];ref=refs[c,n]
        assert r['status']=='success'
        winner=select_candidate(r['candidates'],n)
        assert (r['selected'],r['active_budget'],r['makespan'])==(winner['candidate'],winner['active_budget'],winner['makespan'])
        assert r['makespan']<=olditems[c,n]['makespan']==int(ref['v010_makespan'])
        for x in r['candidates']:
            assert x['status']=='success'
            plan=read(EXP/x['plan']);gen=read(EXP/x['generation_record'])
            assert plan==pad_plan(read(EXP/gen['plan']),n)
            assert x['canonical_plan_sha256']==plan_digest(plan)
            checked=validate_result(read(EXP/x['result']),n)
            assert checked['makespan']==x['makespan']
            if x['candidate']=='single':
                assert x['makespan']==int(ref['single_makespan']), (c,n,'single-core reference mismatch')
            e=x['evaluate'];eval_seconds+=e['seconds']
            if 'reused_from' in e:
                reused_eval+=1;assert sha(Path(e['reused_from']))==sha(EXP/x['result'])==e['source_sha256']
                origin=next(a for a in olditems[c,n]['candidates'] if a['candidate']==x['candidate'])
                assert x['active_budget']==n and plan_digest(read(cache/origin['plan']))==plan_digest(plan)
            elif 'deduplicated_from' in e:
                dedup+=1
                other=next(a for a in r['candidates'] if a['result']==e['deduplicated_from'])
                assert plan_digest(read(EXP/other['plan']))==plan_digest(plan)
                assert sha(EXP/other['result'])==sha(EXP/x['result'])
            else:fresh_eval+=1
            if x['active_budget']==n:
                original=next(a for a in olditems[c,n]['candidates'] if a['candidate']==x['candidate'])
                assert x['makespan']==original['makespan']
            candidates.append({'problem':2,'version':'v011','experiment':EXP.name,'case':c,'cores':n,
                               'candidate':x['candidate'],'active_budget':x['active_budget'],'used_cores':x['used_cores'],
                               'makespan':x['makespan'],'evaluation_seconds':e['seconds'],
                               'reuse':e.get('reused_from',e.get('deduplicated_from','')),'plan':x['plan'],'result':x['result']})
        target=EXP/'plans'/f'{c}_n{n}.json';metric=EXP/'metrics'/f'{c}_n{n}.json'
        assert sha(target)==sha(EXP/winner['plan']) and sha(metric)==sha(EXP/winner['result'])
        comparisons.append({'problem':2,'version':'v011','experiment':EXP.name,'case':c,'cores':n,
            'single_makespan':int(ref['single_makespan']),'v010_makespan':int(ref['v010_makespan']),
            'v011_makespan':r['makespan'],'v011_speedup':int(ref['single_makespan'])/r['makespan'],
            'selected':r['selected'],'active_budget':r['active_budget'],'used_cores':r['used_cores'],
            **{k:winner[k] for k in ('added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes','scheduled_copy_bytes')}})
    for path in sorted((EXP/'generated').glob('*/record.json')):
        g=read(path);assert g['status']=='success' and sha(EXP/g['plan'])==g['plan_sha256']
        e=g['generate']
        if 'reused_from' in e:assert sha(Path(e['reused_from']))==e['source_sha256']==g['plan_sha256']
        generation.append({'problem':2,'version':'v011','experiment':EXP.name,'key':path.parent.name,
                           'candidate':g['candidate'],'active_budget':g['active_budget'],
                           'generation_seconds':e['seconds'],'reuse':e.get('reused_from',''),'original_seconds':e.get('original_seconds',''),'plan':g['plan']})
    assert len(generation)==900 and len(candidates)==2400
    means=[]
    for n in range(2,6):
        group=[r for r in comparisons if r['cores']==n]
        means.append({'cores':n,'count':100,
            **{v:float(sum(Fraction(r['single_makespan'],r[v+'_makespan']) for r in group)/100) for v in ('v010','v011')},
            'improved':sum(r['v011_makespan']<r['v010_makespan'] for r in group),
            'equal':sum(r['v011_makespan']==r['v010_makespan'] for r in group),
            'worse':sum(r['v011_makespan']>r['v010_makespan'] for r in group)})
    OUT.mkdir(exist_ok=False)
    csvout(OUT/'comparison.csv',comparisons);csvout(OUT/'candidates.csv',candidates)
    csvout(OUT/'generation.csv',generation);csvout(OUT/'mean_speedup.csv',means)
    with zipfile.ZipFile(OUT/'v011_plans.zip','w',zipfile.ZIP_DEFLATED) as z:
        for r in comparisons:
            p=EXP/'plans'/f"{r['case']}_n{r['cores']}.json";z.write(p,p.name)
    import hashlib
    with zipfile.ZipFile(OUT/'v011_plans.zip') as z:
        assert len(z.namelist())==400
        for name in z.namelist():assert hashlib.sha256(z.read(name)).hexdigest()==sha(EXP/'plans'/name)
    audit={'version':'v011','configurations':400,'candidate_records':2400,'unique_generation_records':900,
           'new_generations':sum(not r['reuse'] for r in generation),'cached_generations':sum(bool(r['reuse']) for r in generation),
           'new_full_evaluations':fresh_eval,'cached_evaluation_records':reused_eval,'deduplicated_evaluation_records':dedup,
           'new_generation_seconds':sum(r['generation_seconds'] for r in generation),'new_evaluation_seconds':eval_seconds,
           'run_wall_seconds':(datetime.fromisoformat(m['finished_utc'])-datetime.fromisoformat(m['started_utc'])).total_seconds(),
           'shared_v010_prerequisite':m['cache'],'means':means,'tests_passed':69,'failures':0,'degraded':0,
           'active_budget_counts_five':dict(Counter(r['active_budget'] for r in comparisons if r['cores']==5)),
           'hashes_candidates_final_selection_and_zip_verified':True,'cold_start_runtime_measured':False}
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
    lines=['# 第二问 v011：活跃核数自动选择全量结果','','100 张图 × 2～5 核共 400 项全部成功。统一比较 1..N 个活跃核预算；空闲核作为正式 N 核方案的一部分。固定单核原始方案，以及每个 k>=2 的 v007/v009 两候选。新方案均经原始场景 B 评估器验证；没有按用例编号选择。','','| 核数 | v010 均值 | v011 均值 | 改善 / 持平 / 退步 |','|---|---:|---:|---|']
    for r in means:lines.append(f"| {r['cores']} | {r['v010']:.6f} | {r['v011']:.6f} | {r['improved']} / {r['equal']} / {r['worse']} |")
    lines+=['','均值为 100 个逐图单核/多核比值的算术平均，以 Fraction 复算。v010 候选包含在本次搜索中，平局保留较高核预算，再选 v007。实际非空核数与活跃核预算分别记录。','','## 成本与复用', '',
      f"900 个唯一生成记录：新生成 {audit['new_generations']} 个，复用 {audit['cached_generations']} 个；2400 个候选记录：新增完整评估 {fresh_eval} 次、复用旧同核数成绩 {reused_eval} 次、同方案去重 {dedup} 次。",
      f"新增生成阶段累计 {audit['new_generation_seconds']:.3f} 秒、评估阶段累计 {eval_seconds:.3f} 秒；两图并发，批次墙钟 {audit['run_wall_seconds']:.3f} 秒（不含启动前缓存哈希检查）。",
      '共享前置 v010 成本：800 个候选生成、613 次完整评估；生成累计 3773.795 秒、评估累计 1406.661 秒、批次墙钟 2613.376 秒。复用不等于从零生成免费，不能把本轮新增时间作为冷启动总时间；冷启动全量耗时未实测。exp108 的 16 项开发成本另计。',
      '候选数随核数增长：3/5/7/9，所有核预算下生成只做一次。生成预算 single/v007/v009=30/30/300 秒；评估180秒，无重试。未实测提前筛选规则，与 v010 不是等搜索预算比较。',
      '', '## 验证与限制','','69 项测试通过；400 配置无缺失、无失败、无降级；全部候选、归档、输入/配置、源码冻结、选优、最终文件与 ZIP 哈希核对通过。每个同核数 v010 候选与旧成绩一致。所有图旧成绩均已查看，不称未见数据泛化检验。',
      '此版本完成活跃核数选择；分支放置与切分结构优化尚未实施。v010 及更早归档保持不变。',
      '', '## 文件','','comparison.csv：400 配置；candidates.csv：2400 候选；generation.csv：900 生成记录；mean_speedup.csv：均值；v011_plans.zip：400 方案；audit.json：核对与成本。',
      '入口 experiments/run_problem2_active_cores.py；冻结 experiments/problem2_v011_selection.json；设计 experiments/problem2_v011_DESIGN.md。全量原始记录 raw/problem_2/v011/exp109_20260926_active_full/。复现须另立实验编号；省略缓存参数可从原图冷启动。']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    shutil.copy2(__file__,OUT/Path(__file__).name)
    print(json.dumps(audit,indent=2))


if __name__=='__main__':main()
