"""Audit the bounded rehearsal and prepared (unexecuted) full experiment."""
import csv
from pathlib import Path
import shutil

from run_problem1_structural_full import (
    SOLUTION, DEVELOPMENT, experiment_path, read, save, sha, checked, verify_frozen, validate_row,
)


def main():
    pilot = experiment_path('v012', 'exp136_20260926_full_preflight')
    full = experiment_path('v012', 'exp137_20260926_structural_full')
    m = read(pilot / 'manifest.json'); f = read(full / 'manifest.json')
    verify_frozen(m); verify_frozen(f)
    assert m['status'] == 'completed' and f['status'] == 'prepared'
    rows = read(pilot / 'candidates.json')
    expected = {(c, n, a+str(i)) for c in m['cases'] for n in m['cores'] for a in ('B','C') for i in range(4)}
    assert len(rows) == len(expected) == 32
    assert {(r['case'], r['cores'], r['candidate']) for r in rows} == expected
    for r in rows:
        assert r['status'] == 'success'
        validate_row(pilot / 'runs' / f"{r['case']}_n{r['cores']}" / r['candidate'], r, r['cores'])
    assert [s['new_slots'] for s in m['sessions']] == [3,29,0]
    selections = read(pilot / 'selection.json')
    for r in selections:
        assert r['makespan'] == min([r['baseline_makespan']] + [x['makespan'] for x in rows if x['case']==r['case'] and x['cores']==r['cores']])
        checked(pilot / 'selected' / f"{r['key']}.json", r['selected_plan_sha256'])
    assert len(f['cases']) == 100 and f['cores'] == [2,3,4,5]
    assert len(f['references']) == 400 and f['candidate_slots'] == 3200
    assert not list((full / 'runs').iterdir()) and f['sessions'] == []
    oldrows = []
    for p in (DEVELOPMENT, experiment_path('v012','exp134_20260926_structural_transfer')):
        oldrows += [r for r in read(p / 'candidates.json') if r['arm'] in ('B','C')]
    assert len(oldrows) == 184
    old_seconds = sum(r['generation_seconds'] + r['evaluation_seconds'] for r in oldrows)
    budget = dict(historical_slots=184, historical_process_seconds=old_seconds,
        naive_full_hours=old_seconds/184*3200/3600,
        double_observed_rate_hours=old_seconds/184*3200/3600*2,
        per_slot_timeout_upper_hours=3200*(30+180)/3600,
        historical_unique_reuse_plans=len(read(full/'reuse_index.json')),
        exclusions='historical baseline search, preparation, audit; 23 low-score five-core cases are not representative of full suite',
        total_timeout_note='186.67h sums child process timeouts only, not a wall-clock guarantee or recommended budget')
    report = SOLUTION / 'outputs/15_problem1_full_preparation'; report.mkdir(exist_ok=True)
    save(report / 'budget.json', budget)
    save(report / 'verification.json', dict(status='passed', full_evaluations_started=False,
        full_configurations=400, full_candidate_slots=3200, preflight_slots=32,
        preflight_new_evaluations=sum(not r['evaluation_reused'] for r in rows),
        preflight_reused_slots=sum(r['evaluation_reused'] for r in rows),
        checkpoint_new_slots=[s['new_slots'] for s in m['sessions']], frozen_unchanged=True,
        tests='2 unittest tests: altered artifact rejected; competing process blocked and lock released',
        limits='checkpoint boundary resume tested; no OS-kill/power-failure injection; algorithm unchanged'))
    with (report/'preflight_comparison.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['case','cores','baseline_makespan','makespan','candidate','reduction_percent'])
        writer.writeheader()
        for r in selections:
            writer.writerow({**{k:r[k] for k in ('case','cores','baseline_makespan','makespan','candidate')},
                'reduction_percent':100*(1-r['makespan']/r['baseline_makespan'])})
    lines = '\n'.join(f"|{r['case']}|{r['cores']}|{r['baseline_makespan']:,}|{r['makespan']:,}|{100*(1-r['makespan']/r['baseline_makespan']):.2f}%|" for r in selections)
    (report/'REPORT.md').write_text(f'''# 第一问 v012 全量入口与预算准备

已完成入口、400组旧基线/单核参考核对、32槽演练和基础运行保护。**全量exp137仅prepared，0候选已运行；正式五核均值仍为v009的3.413600911。**

## 冻结方案与范围

100图×2～5核，每配置B/C各四设置，共3200逻辑候选槽。算法和参数与exp133一致：B旧切分全局分核排序，C按既有诊断路线重切分并使用相同调度器。真实评估器/config不变。每候选生成30秒、评估180秒，成功候选按方案内容去重；终态失败/超时不自动重试。以原v009为保底，平分保留旧方案。

这是统一的v009+B/C组合，不将仅六开发图探索得到的v010/v011方案单独塞入选择池。故case_046可能仍不如先前局部最优；全量报告需另列此差异，不把它隐去。

原400组方案和结果从08_full归档按正式CSV哈希提取；原代码仅CRLF/LF差异按重建CRLF验证旧哈希，原文件未改。复用只校验决定运行结果的code/data依赖，不以历史说明文档的字节差异拒绝复用。所有当前源码/输入/基线快照冻结。exp133/134共{budget['historical_unique_reuse_plans']}个不同历史方案可在生成完全相同方案后复用；184历史逻辑槽不能视为184独立方案。

## 演练结果

exp136：case_001/056×2/5核，32槽全部成功，7新增评估、25复用（包括基线/历史及本次重复方案），无超时。第一段3槽停靠，第二段29槽完成，第三次重入新增0槽。两段执行墙钟合计{sum(s['seconds'] for s in m['sessions'][:2]):.3f}秒；重入审计{m['sessions'][2]['seconds']:.3f}秒，不含准备/测试。

|图|核数|旧Makespan|新Makespan|下降|
|---|---:|---:|---:|---:|
{lines}

case_056五核沿用历史结果，不是新增效果证据；其二核有18.18%左右收益。case_001两个核数收益均不足1%，符合已有高分图提升较小的可能性，但两图不具代表性，不据此推算全100图新均值。

哈希变更拒绝、跨进程排他锁和锁释放两项测试通过。32槽覆盖、结果/方案哈希、评估容量及Makespan检查、选择最小值和冻结源核对通过。验证了槽边界续跑，未做断电/操作系统强杀注入。进程超时清理由既有process_runner负责；意外中断的running槽重做时保留中断记录，终态失败不自动重试。

## 成本预算

exp133/134的B/C合计184槽，生成加评估进程耗时{old_seconds:.3f}秒，直接按3200槽线性外推约**{budget['naive_full_hours']:.2f}小时**。若平均每槽耗时是已测样本两倍，则约{budget['double_observed_rate_hours']:.2f}小时。这是条件情景，**不是完成时间承诺**：历史样本只含23张低分图五核，既有复用和其他核数/图规模会改变成本；历史基线搜索、准备和最终审计另计。

每槽30+180秒的超时总和为186.67小时，只是最坏子进程预算求和，不是建议耗时或整体墙钟上限。采用单进程与逐槽状态，可随时在保留记录的前提下恢复；失败不能悄悄剔除，全量结果必须列出全部3200槽状态及400组选择和分核均值。exp137当前已准备，不会因生成本报告而启动。

## 复现命令

在仓库根目录运行下述命令会真正启动已准备的全量评估；本阶段没有执行：

```powershell
python -B A题/solution/experiments/run_problem1_structural_full.py --experiment exp137_20260926_structural_full --run
```

中断后使用同一命令恢复，已成功槽核对哈希后跳过，失败/超时保留。最终结果位于`outputs/09_future/raw/problem_1/v012/exp137_20260926_structural_full`，不会覆盖08_full。完成后仍须审计候选合法性/失败、分路线退化和成本，才能报告新的正式全量成绩。

## 准备阶段异常

exp135准备时把历史docs也纳入执行依赖核验，因旧文档哈希差异停止，0生成/评估；保留失败目录。修正范围为code/data后新建exp136，不覆盖失败记录。锁测试初次误期待父类异常名OSError，实际PermissionError正确拦截；测试按实际子类改正后两项通过，运行器未因此改动。
''', encoding='utf-8')
    shutil.copy2(Path(__file__),report/Path(__file__).name)
    print(budget)


if __name__ == '__main__':
    main()
