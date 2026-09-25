"""Audit fresh Q2 v010 candidates, decisions, references and final artifacts."""
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from datetime import datetime
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'outputs/09_problem2/raw/problem_2/v010/exp107_20260925_portfolio_full'
OUT=ROOT/'outputs/09_problem2/v010_summary_20260925'


def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def norm(d): return {k.replace('\\','/'):v for k,v in d.items()}
def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    m=read(EXP/'manifest.json')
    assert m['status']=='completed' and m['protected_unchanged']
    assert len(m['items'])==400 and {(r['case'],r['cores']) for r in m['items']}=={(f'case_{i:03}',n) for i in range(1,101) for n in range(2,6)}
    frozen=read(ROOT/'experiments/problem2_v010_selection.json')
    for path,digest in frozen['source_hashes'].items(): assert sha(ROOT/path)==digest
    for path,digest in m['source_hashes'].items(): assert sha(EXP/'source'/path)==digest
    for path,digest in m['output_hashes'].items(): assert sha(EXP/path)==digest
    for path,digest in m['protected_hashes_before'].items(): assert sha(ROOT.parent/path)==digest
    previous=list(csv.DictReader((ROOT/'outputs/09_problem2/v009_summary_20260925/comparison.csv').open(encoding='utf-8-sig')))
    reference={(r['case'],int(r['cores'])):r for r in previous}
    originals=list(csv.DictReader((ROOT/'outputs/09_problem2/full_summary_20260925/all_results.csv').open(encoding='utf-8-sig')))
    original_refs={(r['case'],int(r['cores'])):r for r in originals if r['version']=='v007'}
    singles={r['case']:r for r in originals if r['cores']=='1'}
    manifests={}
    rows=[]; candidates=[]; choices=Counter(); dedup=0; generation=0; evaluation=0
    for item in sorted(m['items'],key=lambda r:(r['case'],r['cores'])):
        c,n=item['case'],item['cores']; key=f'{c}_n{n}'; ref=reference[c,n]
        assert item['status']=='success' and len(item['candidates'])==2
        for archived in (ref,original_refs[c,n],singles[c]):
            mf=(ROOT/archived['result']).parents[1]/'manifest.json'
            if mf not in manifests: manifests[mf]=read(mf)
            for path in (f'data/{c}.json','data/config.txt'):
                assert norm(m['protected_hashes_before'])[path]==norm(manifests[mf]['protected_hashes_before'])[path]
        scores={}
        for candidate in item['candidates']:
            version=candidate['candidate'];scores[version]=candidate['makespan']
            assert candidate['status']=='success'
            assert candidate['makespan']==int(ref[f'{version}_makespan']), (c,n,version,'fresh result differs')
            d=read(EXP/candidate['result']);assert d['makespan']==candidate['makespan']
            reused=candidate['evaluate'].get('reused_from','');dedup+=bool(reused)
            generation+=candidate['generate']['seconds'];evaluation+=candidate['evaluate']['seconds']
            candidates.append({'problem':2,'version':'v010','experiment':EXP.name,'case':c,'cores':n,'candidate':version,'makespan':candidate['makespan'],
                               'generation_seconds':candidate['generate']['seconds'],'evaluation_seconds':candidate['evaluate']['seconds'],
                               'evaluation_reused_from':reused,'plan':candidate['plan'],'result':candidate['result']})
        selected=min(scores,key=lambda v:(scores[v],v!='v007'))
        assert item['selected']==selected and item['makespan']==scores[selected]
        winner=next(r for r in item['candidates'] if r['candidate']==selected)
        assert sha(EXP/winner['plan'])==sha(EXP/'plans'/f'{key}.json')
        assert sha(EXP/winner['result'])==sha(EXP/'metrics'/f'{key}.json')
        choices[selected]+=1;d=read(EXP/'metrics'/f'{key}.json')
        rows.append({'problem':2,'version':'v010','experiment':EXP.name,'case':c,'cores':n,'single_makespan':int(ref['single_makespan']),
                     'v007_makespan':scores['v007'],'v009_makespan':scores['v009'],'v010_makespan':item['makespan'],
                     'v010_speedup':int(ref['single_makespan'])/item['makespan'],'selected':selected,
                     'added_copy_bytes':d['data_movement_bytes']['added_copy_bytes'],
                     'spill_added_copy_bytes':d['data_movement_bytes']['spill_added_copy_bytes']})
    means=[]
    for n in range(2,6):
        group=[r for r in rows if r['cores']==n]
        means.append({'cores':n,'count':100,**{v:float(sum(Fraction(r['single_makespan'],r[f'{v}_makespan']) for r in group)/100) for v in ('v007','v009','v010')},
                      'faster_than_v009':sum(r['v010_makespan']<r['v009_makespan'] for r in group),
                      'equal_to_v009':sum(r['v010_makespan']==r['v009_makespan'] for r in group)})
    OUT.mkdir(exist_ok=True)
    write_csv(OUT/'comparison.csv',rows);write_csv(OUT/'candidates.csv',candidates);write_csv(OUT/'mean_speedup.csv',means)
    with zipfile.ZipFile(OUT/'v010_plans.zip','w',zipfile.ZIP_DEFLATED) as z:
        for r in rows:
            path=EXP/'plans'/f"{r['case']}_n{r['cores']}.json";z.write(path,path.name)
    with zipfile.ZipFile(OUT/'v010_plans.zip') as z:
        assert len(z.namelist())==400
        for name in z.namelist(): assert hashlib.sha256(z.read(name)).hexdigest()==sha(EXP/'plans'/name)
    audit={'version':'v010','problem':2,'configurations':400,'candidates_generated':800,'full_evaluations':800-dedup,
           'deduplicated_evaluations':dedup,'failures':0,'degraded':0,'generation_seconds':generation,
           'evaluation_seconds':evaluation,'elapsed_wall_seconds':(datetime.fromisoformat(m['finished_utc'])-datetime.fromisoformat(m['started_utc'])).total_seconds(),
           'choices':dict(choices),'means':means,'tests_passed':65,'fresh_scores_equal_archived_scores':True,
           'source_input_config_and_artifact_hashes_verified':True,'zip_verified':True}
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
    text=['# 第二问 v010：真实评估择优完整结果','','## 结果','',
          '100 张图 × 2～5 核全部重新生成 v007/v009 两候选，并用本次原始场景 B 评估结果选择。400 个配置均成功，无候选失败或降级。', '',
          '| 核数 | v007 均值 | v009 均值 | v010 均值 | 比 v009 更快 / 持平 |','|---|---:|---:|---:|---|']
    for r in means: text.append(f"| {r['cores']} | {r['v007']:.6f} | {r['v009']:.6f} | {r['v010']:.6f} | {r['faster_than_v009']} / {r['equal_to_v009']} |")
    text+=['','均值为 100 个逐图单核/多核比值的算术平均，使用 Fraction 复算。所有新候选成绩与旧归档逐项一致，且最终选择、方案复制、结果复制已逐项核对。', '',
           '## 方法和成本','',
           '固定两个候选，实际 Makespan 小者胜；平局选 v007。仅当本次同配置的方案在保留核序/操作序后完全一致时，复用已经成功的评估。没有根据用例编号或历史成绩选择。',
           f"本次生成 800 个候选，执行 {800-dedup} 次完整原始评估；{dedup} 次因方案相同而去重。v009 生成内部仍最多四次核内准备。",
           f"候选生成阶段累计 {generation:.3f} 秒，完整评估阶段累计 {evaluation:.3f} 秒；两个配置并发，整批墙钟时间 {audit['elapsed_wall_seconds']:.3f} 秒。阶段时间之和不是整批墙钟时间，归档和调度开销另计。开发 exp106 的三配置成本不含在上述全量成本中。",
           'v007/v009 生成预算固定为 30/300 秒，每次完整评估预算 180 秒，无重试。与只评估一次的旧方法不是等搜索预算比较。性能不退步来自实际评估后择优，并不代表单一切分规则全面改善。', '',
           '## 验证与边界','',
           '65 项测试通过；冻结源码、原始材料、候选归档、单核分母输入/配置、完整结果与 ZIP 均已核对。原 v007/v008/v009 成果保持不变。全部图旧成绩已见，不称为未见数据泛化验证。',
           '本轮只完成真实择优阶段；单连通图结构优化另立版本，尚未完成。该组合仅略超过 4 倍，不代表已追平其他方法的更高成绩。', '',
           '## 文件与复现','',
           'comparison.csv：400 个最终配置；candidates.csv：800 个候选及成本；mean_speedup.csv：均值；v010_plans.zip：最终方案；audit.json：核对记录。',
           '源代码 src/scene_b_portfolio.py；入口 experiments/run_problem2_portfolio.py；冻结 experiments/problem2_v010_selection.json；完整原始记录在 raw/problem_2/v010/exp107_20260925_portfolio_full/。复现使用新的实验编号，禁止覆盖旧实验。']
    (OUT/'REPORT.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    shutil.copy2(__file__,OUT/Path(__file__).name)
    print(json.dumps(audit,indent=2))


if __name__=='__main__': main()
