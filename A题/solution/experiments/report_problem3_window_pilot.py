"""Independent artifact/legality/selection audit and bounded-pilot report."""
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
S=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(S/'src'))
from scene_b_window_components import make_plan
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan
from replay_problem3_external import sha, save, OUT as R
from try_problem3_window_components import OUT as P


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def main():
    rm,pm=read(R/'manifest.json'),read(P/'manifest.json')
    for root,m in ((R,rm),(P,pm)):
        assert m['status']=='completed'
        assert m['hashes_before']==m['hashes_after']
        assert all(sha(Path(p))==h for p,h in m['hashes_before'].items())
        for rec in m['attempts']:
            assert rec['status']=='success'
            assert sha(root/rec['result'])==rec['result_sha256']
            assert read(root/rec['result'])['makespan']==rec['makespan']
        for p in (root/'plans').glob('*.json'):
            case='_'.join(p.stem.split('_')[:2])
            validate_task_order(derive_multicore_plan(read(root/'inputs'/f'{case}.json'),read(p)))
    assert len(rm['attempts'])==24 and len(pm['attempts'])==20
    assert all(r['matches_reported'] for r in read(R/'comparison.json'))
    assert all(sha(R/p)==h for p,h in rm['archive_hashes'].items())
    for gen in pm['generation']:
        case,w=gen['case'],gen['window']
        path=P/'plans'/f'{case}_w{w}.json'
        assert sha(path)==gen['plan_sha256']
        assert make_plan(read(P/'inputs'/f'{case}.json'),5,w,0.5)==read(path)
    table=[]
    records=read(P/'comparison.json')
    for sel in pm['selected']:
        case=sel['case']
        choices=[(sel['baseline_cache'],0,'baseline')]+[(r['candidate'],r['window'],f"w{r['window']}") for r in records if r['case']==case]
        best=min(choices)
        assert (sel['cache'],sel['label'])==(best[0],best[2])
        ext=read(R/'metrics'/f'{case}_external_cache.json')['makespan']
        table.append(f"|{case}|{sel['baseline_cache']}|{ext}|{sel['cache']}|{sel['reduction_percent']:.2f}%|{sel['label']}|")
    counts={k:sum((r['candidate']<r['baseline'] if k=='faster' else r['candidate']==r['baseline'] if k=='equal' else r['candidate']>r['baseline']) for r in records) for k in ('faster','equal','slower')}
    costs={'replay_evaluation_seconds':sum(r['seconds'] for r in rm['attempts']),
        'pilot_generation_seconds':sum(r['seconds'] for r in pm['generation']),
        'pilot_evaluation_seconds':sum(r['seconds'] for r in pm['attempts'])}
    report='''# 第三问：外部方案复现与 v004 小样本试验

## 结论

6 个用例 × 五核：对方方案与本地 v003 的 12 个 Cache 耗时均精确复现。v004 为借鉴开源 bandcomp 的窗口连通分量候选，试验 window=4/10/16、sticky=0.5，加上原 v003 方案按真实 Cache Makespan 择优。2 图改善、4 图保持原方案。不是全量结果，也不是独立检验。

|用例|我们 v003|对方已提交方案|v004 择优耗时|相对 v003 耗时下降|入选|
|---|---:|---:|---:|---:|---|
'''+ '\n'.join(table)+f'''

全部 18 个新候选：{counts['faster']} 快、{counts['equal']} 平、{counts['slower']} 慢。必须披露择优与搜索成本，不能声称新切分单独普遍有效。用例按已知双方性能差距选取，不能用这 6 图的平均收益外推全部 100 图。

## 定位依据

- case_054：原方案/对方的固定分核计算下界分别为118416/115104，仅相差约2.8%；切分新增搬运分别14458978/3963360 bytes，子图数10573/631，双方spill均为0。单靠计算均衡改善不足以解释耗时差距；切分边界及依赖调度值得优先优化。搬运减少是伴随证据，尚未将所有耗时差异归因于它。
- case_069：对方计算下界反而更高（4131→5430），但总耗时更低（16269→9557），进一步否定“只需更均衡”的解释。
- case_044：对方同方案 Cache 比1.1687，却耗时71418，慢于我们44185；更大的 Cache 比并不等于更好的最终方案。
- 新候选 case_054 的 Cache/无L2耗时为180229/181955，比值1.0096；case_069为9397/10196，比值1.0850。主要观察到的是整体切分调度改善，不是证明平均 Cache 比达到1.15。

## 来源与限制

外部仓库：https://github.com/zhuangzhuangaiyutingya/2026_match_model_A_openproject

固定提交：`4bebdda48585cb751466b504e05865cb39673593`。外部方案、CSV、算法源文件、MIT许可已归档在exp122。v004借鉴其bandcomp方法，使用本项目Graph及确定性排序实现，模块附有来源和许可；不声称原创。没有运行下载的第三方Python。

开发用例：054/069（对方优势大，一大图一小图）、001/013（相等/接近）、026/044（我们优势大）。同一批数据已经用于v003全量；没有未见测试集。本轮未做参数追加搜索、FM细化或全量重跑。

原始代码、图与配置哈希未变化。Cache=1048576 bytes、250 bytes/cycle，DDR=60 bytes/cycle，跨核延迟500，沿用原评估器。全部44次新增评估成功，无超时。方案合法性、指标哈希、18个候选确定性重新生成及择优规则通过独立检查。

新增成本：外部/本地方案配对24次评估累计{costs['replay_evaluation_seconds']:.3f}秒；原型18次生成累计{costs['pilot_generation_seconds']:.3f}秒，20次评估累计{costs['pilot_evaluation_seconds']:.3f}秒。这些是操作累计时间；不含下载、审计及历史候选搜索。

## 下一步

冻结当前3候选规则，先在额外结构分层用例及2～5核上做迁移检验，重点观察连通链、大张量、跨核依赖与少核优势的反例。全部原始图已见过，额外组只能称后续检验，不能称全新独立测试集。通过后再决定全量运行。

## 复现命令

从D:/workspace/HuaWei运行（实验目录必须尚不存在，避免覆盖历史结果）：

```powershell
& 'A题/.venv/Scripts/python.exe' 'A题/solution/experiments/replay_problem3_external.py'
& 'A题/.venv/Scripts/python.exe' 'A题/solution/experiments/try_problem3_window_components.py'
```

现有结果可重复只读审计并重新生成本报告：

```powershell
& 'A题/.venv/Scripts/python.exe' 'A题/solution/experiments/report_problem3_window_pilot.py'
```
'''
    (P/'REPORT.md').write_text(report,encoding='utf-8')
    save(P/'audit.json',{'status':'passed','direct_candidates':counts,'costs':costs,
        'replay_manifest_sha256':sha(R/'manifest.json'),'pilot_manifest_sha256':sha(P/'manifest.json'),
        'audit_script_sha256':sha(Path(__file__))})
    print(json.dumps({'audit':'passed','counts':counts,'costs':costs}),flush=True)


if __name__=='__main__':main()
