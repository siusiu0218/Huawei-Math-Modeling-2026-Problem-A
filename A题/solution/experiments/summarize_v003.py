"""Audit and summarize the fixed v003 prototype experiments; no winner selection."""
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
from result_paths import result_path


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    out = result_path('problem_1/v003/summary_20260924')
    out.mkdir(exist_ok=False)
    freeze_path = ROOT / 'experiments/v003_selection.json'
    freeze = read(freeze_path)
    evidence = {str(freeze_path): digest(freeze_path)}
    comparisons = [
        ('development', 'v001/exp002_20260924_baseline', 'v003/exp009_20260924_branches_development'),
        ('holdout', 'v001/exp011_20260924_baseline_holdout', 'v003/exp010_20260924_branches_holdout')]
    rows = []
    for split, old_name, new_name in comparisons:
        old, new = [result_path(Path('problem_1') / name) for name in (old_name, new_name)]
        om, nm = [read(p / 'manifest.json') for p in (old, new)]
        assert all(m['protected_inputs_unchanged'] for m in (om, nm))
        assert om['protected_hashes_before'] == nm['protected_hashes_before']
        for name, expected in nm['protected_hashes_before'].items():
            assert digest(ROOT.parent / name) == expected
        assert om['evaluation_config'] == nm['evaluation_config']
        assert om['wait_config'] == nm['wait_config']
        assert om['parameters']['blocks_per_core'] == nm['parameters']['blocks_per_core'] == 4
        for name, expected in freeze['source_hashes'].items():
            assert digest(new / 'source/src' / name) == expected
            assert digest(ROOT / 'src' / name) == expected
        if split == 'holdout':
            assert freeze['utc'] < nm['started_utc']
        base = {(r['case'], r['cores']): r for r in table(old / 'metrics/summary.csv')}
        new_rows = table(new / 'metrics/summary.csv')
        expected_cases = {'case_016', 'case_095'} if split == 'development' else {r['case'] for r in freeze['holdout_cases']}
        assert {(r['case'],r['cores']) for r in new_rows} == {(c,str(k)) for c in expected_cases for k in (2,3,4,5)}
        for path in [old / 'manifest.json',new / 'manifest.json',old / 'metrics/summary.csv',new / 'metrics/summary.csv']:
            evidence[str(path)] = digest(path)
        for r in new_rows:
            b = base[r['case'],r['cores']]
            assert r['status'] == b['status'] == 'ok'
            assert r['candidate_count'] == b['candidate_count'] == '1'
            rows.append(dict(split=split,case=r['case'],cores=int(r['cores']),
                baseline_run=old_name,new_run=new_name,baseline_cycles=int(b['makespan']),
                new_cycles=int(r['makespan']),reduction_percent=100*(1-int(r['makespan'])/int(b['makespan'])),
                baseline_added_bytes=int(b['added_copy_bytes']),new_added_bytes=int(r['added_copy_bytes']),
                baseline_cores_used=int(b['used_cores']),new_cores_used=int(r['used_cores']),
                new_plan_seconds=float(r['plan_seconds']),new_evaluation_seconds=float(r['evaluation_seconds'])))
    with (out / 'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    counts={s:{'configurations':len([r for r in rows if r['split']==s]),
               'wins':sum(r['new_cycles']<r['baseline_cycles'] for r in rows if r['split']==s),
               'ties':sum(r['new_cycles']==r['baseline_cycles'] for r in rows if r['split']==s),
               'losses':sum(r['new_cycles']>r['baseline_cycles'] for r in rows if r['split']==s),
               'added_bytes_increased':sum(r['new_added_bytes']>r['baseline_added_bytes'] for r in rows if r['split']==s)}
            for s in ('development','holdout')}
    lines=['# v003：依赖收缩与关键路径调度原型', '',
           'v003在单连通操作图上按计算量上限合并依赖边；只在当前前驱唯一后继或后继唯一前驱时合并，排除另一条前驱到后继路径，避免收缩产生环。随后按剩余计算最长路径优先、近似最早完成分核。多连通分量仍使用v002分组方法。计算量与等待是粗略估计，尚无共享输入、张量大小、带宽争用及存储压力成本模型。', '',
           '每核目标倍率固定为4；对收缩算法它是计算量上限参数，不保证最后恰有4×核数个任务。未作参数搜索。开发集case_016/095使用此前诊断图；选择及源码在新检验前冻结。新检验集case_051（层宽12的小连通图）、case_002（层宽199的小连通图）按结构选取，选择时未查看其性能；不是随机代表样本。', '',
           '新增24次原始评估全部成功：第三版开发8项、第三版检验8项及同参数原基线检验8项；每配置每方法1个候选，固定配置和60秒上限。开发结果基于历史基线，同参数比较。', '',
           '| 集合 | 更快 | 相同 | 更慢 | 额外搬运增加 |', '|---|---:|---:|---:|---:|']
    for s,c in counts.items():lines.append(f"| {s} | {c['wins']} | {c['ties']} | {c['losses']} | {c['added_bytes_increased']}/{c['configurations']} |")
    lines+=['', '| 四核用例 | 基线cycles | v003 cycles | 减少比例 | 基线额外bytes | v003额外bytes | 使用核数变化 |', '|---|---:|---:|---:|---:|---:|---|']
    for r in rows:
        if r['cores']==4:
            lines.append(f"| {r['case']} | {r['baseline_cycles']:,} | {r['new_cycles']:,} | {r['reduction_percent']:.2f}% | {r['baseline_added_bytes']:,} | {r['new_added_bytes']:,} | {r['baseline_cores_used']}→{r['new_cores_used']} |")
    lines+=['', '## 结论与限制', '',
            '- case_002 已能利用多个核，提供单连通图内部切分可能有效的实测证据。case_051改善较小；使用多个核不等于负载均衡。',
            '- case_016四种核数均退步且仍只用1核，内部并行问题未解决。case_095沿用v002倍率4，和exp007结果相同，其相对v001改善不能归功于新收缩方法。',
            '- 原型保留作候选，不替代已冻结的v001/v002，也不依据此次检验结果修改v003。下一版应检查case_016收缩后的依赖链是否丢失并行机会，并加入边界搬运成本；新规则需新的验证安排。',
            '- 这不是全部100图性能验证。没有为两个新检验图补单核参考，因此只报告同核版本比较；case_014单核缺失仍未解决。',
            '- 13项测试通过，覆盖连通分叉、多路径收缩边界、30个固定种子的随机DAG、串行链合并和既有测试；没有据此宣称评估器本身完全正确。', '',
            '明细：[comparison.csv](comparison.csv)。代码及输入哈希：[manifest.json](manifest.json)。复现汇总：`python -B A题/solution/experiments/summarize_v003.py`（拒绝覆盖；复跑另存脚本并更换输出目录）。', '']
    (out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    (out/'source.py').write_bytes(Path(__file__).read_bytes())
    (out/'manifest.json').write_text(json.dumps(dict(status='completed',counts=counts,input_hashes=evidence,
        source_sha256=digest(Path(__file__)),protected_inputs_unchanged=True,
        output_hashes={n:digest(out/n) for n in ('REPORT.md','comparison.csv')},
        invocation=[sys.executable,'-B',*sys.argv]),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(counts));print(out)


if __name__=='__main__':
    main()
