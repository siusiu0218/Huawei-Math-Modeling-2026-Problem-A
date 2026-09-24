"""Audit v004, preserve first-run timeouts, and measure lost branch parallelism."""
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from graph_analysis import Graph
from branch_scheduler import contract as contract_v3
from fork_preserving_scheduler import contract as contract_v4


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def path_stats(groups, preds, succs, graph):
    degree = {i: len(preds[i]) for i in groups}
    ready = [i for i in groups if not degree[i]]
    longest, levels = {}, {}
    while ready:
        i = ready.pop()
        longest[i] = sum(graph.ops[n]['cycles'] for n in groups[i]) + max((longest[j] for j in preds[i]), default=0)
        levels[i] = 1 + max((levels[j] for j in preds[i]), default=0)
        for j in sorted(succs[i]):
            degree[j] -= 1
            if degree[j] == 0:
                ready.append(j)
    assert len(longest) == len(groups)
    return dict(tasks=len(groups), longest_compute_path=max(longest.values()),
                longest_task_chain=max(levels.values()))


def main():
    target = ROOT / 'results/problem_1/v004/summary_20260924'
    if target.exists():
        raise FileExistsError(target)
    freeze_path = ROOT / 'experiments/v004_selection.json'
    freeze = read(freeze_path)
    evidence = {str(freeze_path): sha(freeze_path)}
    specs = {'development': 'v004/exp012_20260924_forks_development',
             'holdout': 'v004/exp013_20260924_forks_holdout',
             'baseline_dev': 'v001/exp002_20260924_baseline',
             'baseline_holdout': 'v001/exp014_20260924_baseline_holdout',
             'retry': 'v004/exp015_20260924_forks_retry'}
    tables, manifests = {}, {}
    for label, name in specs.items():
        folder = ROOT / 'results/problem_1' / name
        mp, tp = folder / 'manifest.json', folder / 'metrics/summary.csv'
        m = read(mp)
        assert m['status'] in ('completed', 'completed_with_failures') and m['protected_inputs_unchanged']
        assert m['parameters']['blocks_per_core'] == 4
        if m['algorithm_version'] == 'v004':
            for f, h in freeze['source_hashes'].items():
                assert sha(folder / 'source/src' / f) == sha(ROOT / 'src' / f) == h
        manifests[label] = m
        tables[label] = {(r['case'],r['cores']):r for r in table(tp)}
        evidence.update({str(mp):sha(mp), str(tp):sha(tp)})
    reference = manifests['development']
    for m in manifests.values():
        assert m['protected_hashes_before'] == reference['protected_hashes_before']
        assert m['evaluation_config'] == reference['evaluation_config']
        assert m['wait_config'] == reference['wait_config']
    for f,h in reference['protected_hashes_before'].items():
        assert sha(ROOT.parent / f) == h
    assert freeze['utc'] < manifests['holdout']['started_utc']
    assert set(tables['retry']) == {('case_016','2'),('case_016','3')}
    rows = []
    for split in ('development','holdout'):
        base = tables['baseline_dev' if split=='development' else 'baseline_holdout']
        expected = set(freeze['development_cases']) if split=='development' else {r['case'] for r in freeze['holdout_cases']}
        assert set(tables[split]) == {(c,str(k)) for c in expected for k in (2,3,4,5)}
        for key, first in tables[split].items():
            original = base[key]
            retry = tables['retry'].get(key) if split=='development' else None
            selected = first
            if retry is not None:
                assert first['status'] != 'ok', 'do not replace a successful result'
                for tag in (split, 'retry'):
                    plan = ROOT / 'results/problem_1' / specs[tag] / 'plans' / f'{key[0]}_n{key[1]}.json'
                    evidence[str(plan)] = sha(plan)
                a = ROOT / 'results/problem_1' / specs[split] / 'plans' / f'{key[0]}_n{key[1]}.json'
                b = ROOT / 'results/problem_1' / specs['retry'] / 'plans' / a.name
                assert read(a) == read(b), 'retry changed the plan'
                if retry['status']=='ok': selected = retry
            valid = selected['status']==original['status']=='ok'
            assert first['candidate_count']==original['candidate_count']=='1'
            rows.append(dict(split=split,case=key[0],cores=int(key[1]),first_status=first['status'],
                retry_status=retry['status'] if retry else '',final_status=selected['status'],
                source_experiment=selected['experiment'],baseline_cycles=original['makespan'],
                new_cycles=selected['makespan'],reduction_percent=100*(1-int(selected['makespan'])/int(original['makespan'])) if valid else '',
                baseline_added_bytes=original['added_copy_bytes'],new_added_bytes=selected['added_copy_bytes'],
                tasks=selected['subgraphs'],used_cores=selected['used_cores'],
                plan_seconds=selected['plan_seconds'],evaluation_seconds=selected['evaluation_seconds']))
    graph = Graph(read(ROOT.parent/'data/case_016.json'))
    total = sum(o['cycles'] for o in graph.ops.values())
    structure = {'original':path_stats({i:[i] for i in graph.ops},graph.preds,graph.succs,graph)}
    for name,fn in [('v003',contract_v3),('v004',contract_v4)]:
        structure[name] = path_stats(*fn(graph,total/16),graph)
    counts = {}
    for split in ('development','holdout'):
        part = [r for r in rows if r['split']==split]
        counts[split] = dict(planned=len(part),valid=sum(r['final_status']=='ok' for r in part),
             wins=sum(r['reduction_percent']!='' and r['reduction_percent']>0 for r in part),
             losses=sum(r['reduction_percent']!='' and r['reduction_percent']<0 for r in part),
             first_timeouts=sum(r['first_status']=='timeout' for r in part))
    lines = ['# v004：保留分叉的收益与代价', '',
        'v003安全收缩保证了无环，但并不保证保留并行。v004只把“前驱唯一后继且后继唯一前驱”的串行连接合并；关键路径分核、倍率4、其他规则均保留，多分量图仍走v002。没有针对用例编号写规则，没有调参。', '',
        '## case_016四核结构诊断', '',
        '| 图层次 | 节点/Task数 | 最长计算路径cycles | 最长依赖链节点数 |','|---|---:|---:|---:|']
    for name, d in structure.items(): lines.append(f"| {name} | {d['tasks']:,} | {d['longest_compute_path']:,} | {d['longest_task_chain']:,} |")
    lines += ['', 'v003四核20个Task组成完整串行链；v004恢复原最长计算路径，但产生7,015个Task。计算路径只作结构诊断，不是模拟Makespan或可实现加速比。', '',
        '## 原始评估结果', '',
        '开发集沿用case_016/095；新检验前冻结源码和case_024/069选择。两张新图按结构选择，未使用性能结果；case_024是中等大小的层宽12连通图，case_069是较小的宽分支连通图，不代表100图总体。', '',
        '首次各配置60秒预算；case_016的2核和3核超时，保留原记录，在exp015对同一方案顺序重试120秒。重试只填失败项，不替换成功结果。这增加了评估预算，不能称为所有配置均在同一60秒预算内成功。开发行原holdout标签来自历史选例，本报告正确标为development。', '',
        '| 集合 | 完成/计划 | 比基线快 | 比基线慢 | 首次超时 |','|---|---:|---:|---:|---:|']
    for s,c in counts.items(): lines.append(f"| {s} | {c['valid']}/{c['planned']} | {c['wins']} | {c['losses']} | {c['first_timeouts']} |")
    lines += ['', '| 四核图 | 基线cycles | v004 cycles | 耗时减少 | 基线额外bytes | v004额外bytes |','|---|---:|---:|---:|---:|---:|']
    for r in rows:
        if r['cores']==4:
            pct=f"{r['reduction_percent']:.2f}%" if r['reduction_percent']!='' else '缺失'
            lines.append(f"| {r['case']} | {r['baseline_cycles']} | {r['new_cycles']} | {pct} | {r['baseline_added_bytes']} | {r['new_added_bytes']} |")
    lines += ['', '## 判断', '',
        '- case_016首次成功的四核方案实际利用4核，说明v003合并所造成的串行化确实是主要问题之一；但大量Task与额外搬运造成新成本。',
        '- case_024四个核数均改善，case_069四个核数均退步。保护全部分叉不是统一有效的规则，不能直接替换旧方法。case_095沿用v002，收益不能归功于此次改动。',
        '- 下一版应在保留主要并行分支的同时，合并开销占主导的小分支，并考虑边界数据量与100/1000周期等待。阈值尚未选择，不能把此建议说成已验证算法。',
        '- 原始评估器、数据及配置保持不变；15项测试通过。未完成100图性能验证，case_014单核参考仍缺失。当前保留v004为候选，当前新检验图若用于调参将不再是未见证据。', '',
        '明细：[comparison.csv](comparison.csv)。证据和脚本哈希：[manifest.json](manifest.json)。首次失败与重试分别保存在exp012/exp015，不混同首次成功。', '']
    target.mkdir()
    with (target/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (target/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    (target/'source.py').write_bytes(Path(__file__).read_bytes())
    (target/'manifest.json').write_text(json.dumps(dict(status='completed',input_hashes=evidence,
        source_sha256=sha(Path(__file__)),counts=counts,structure=structure,protected_inputs_unchanged=True,
        output_hashes={n:sha(target/n) for n in ('REPORT.md','comparison.csv')},
        invocation=[sys.executable,'-B',*sys.argv]),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(counts));print(target)


if __name__=='__main__':main()
