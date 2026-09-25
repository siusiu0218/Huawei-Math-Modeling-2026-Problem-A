"""Audit and report one complete 30-pair Q3 development baseline."""
import csv
import json
from pathlib import Path
import sys
from fractions import Fraction
from run_problem3_pair import sha
from run_problem2 import save

SOLUTION=Path(__file__).resolve().parents[1]


def main():
    out=Path(sys.argv[1])
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    selection=json.loads((out/'source/selection.json').read_text(encoding='utf-8'))
    rows=list(csv.DictReader((out/'comparison.csv').open(encoding='utf-8-sig')))
    assert manifest['status']=='completed' and len(rows)==30 and not summary['failures']
    assert manifest['hashes_before']==manifest['hashes_after']
    for path,digest in manifest['hashes_before'].items():assert sha(path)==digest
    for rel,digest in manifest['archive_hashes'].items():assert sha(out/rel)==digest
    expected={(i['case'],n) for i in selection['cases'] if i['role']=='development' for n in range(1,6)}
    assert {(r['case'],int(r['cores'])) for r in rows}==expected
    assert len({(r['case'],r['cores']) for r in rows})==30
    origin=SOLUTION/'outputs/09_problem2/raw/problem_2/v011/exp109_20260926_active_full'
    old=list(csv.DictReader((SOLUTION/'outputs/09_problem2/v011_summary_20260926/comparison.csv').open(encoding='utf-8-sig')))
    old_map={(r['case'],int(r['cores'])):r for r in old}
    events=[];records=0;equal_full=0;input_hashes={}
    for item in manifest['items']:
        stem=f"{item['case']}_n{item['cores']}"
        assert sha(out/'plans'/f'{stem}.json')==item['plan_sha256']==sha(item['plan_source'])
        current={mode:[r for r in item['attempts'] if r['mode']==mode][-1] for mode in ('no_l2','cache')}
        records+=len(item['attempts'])
        for r in current.values():
            assert r['status']=='success' and sha(out/r['result'])==r['result_sha256']
            assert r['plan_sha256']==item['plan_sha256']
            input_hashes[str(out/r['result'])]=sha(out/r['result'])
        a,b=[json.loads((out/current[mode]['result']).read_text(encoding='utf-8')) for mode in ('no_l2','cache')]
        if item['cores']>1:
            old_path=origin/'metrics'/f'{stem}.json'
            old_result=json.loads(old_path.read_text(encoding='utf-8'))
            assert a==old_result
            equal_full+=1
            input_hashes[str(old_path)]=sha(old_path)
        else:
            assert a['makespan']==int(old_map[item['case'],2]['single_makespan'])
        diagnosis=json.loads((out/'metrics'/f'{stem}_diagnosis.json').read_text(encoding='utf-8'))
        for event in diagnosis['hit_completion_insert_events']:
            events.append({'case':item['case'],'cores':item['cores'],**event})
    for n in range(1,6):
        part=[r for r in rows if int(r['cores'])==n]
        exact=sum((Fraction(int(r['no_l2_makespan']),int(r['cache_makespan'])) for r in part),Fraction(0))/6
        assert float(exact)==summary['by_cores'][n-1]['mean_speedup']
    save(out/'reinsertion_events.json',events)
    save(out/'audit.json',{'status':'passed','pairs':30,'evaluator_attempts':records,
        'official_inputs_sources_and_archives_unchanged':True,'same_plan_hashes_checked':True,
        'q2_full_result_matches':equal_full,'q2_single_reference_matches':6,
        'summary_fraction_recomputed':True,'fixed_config_hit_completion_insertions':len(events),
        'checked_result_hashes':input_hashes,'report_script_sha256':sha(__file__)})
    lines=['# 第三问 v001：开发集成对基线','',
        'exp111_20260926_development：6 张开发图 × 1～5 核，30 对、60 次原始评估全部成功；没有失败或超时。当前是基线结果，未实施第三问调度优化，也不是 100 图全量成绩。','',
        '方案来自第二问冻结 v011，单核使用同轮归档的 single 方案。每对评估使用完全相同方案与固定配置。用户已确认沿用原始评估器，并披露命中完成后的重新插入行为。','',
        '| 核数 | 平均 Cache 加速比 | 快 / 平 / 慢 | 平均逐图字节命中率 | 汇总字节命中率 |',
        '|---|---:|---|---:|---:|']
    for row in summary['by_cores']:
        lines.append(f"| {row['cores']} | {row['mean_speedup']:.6f} | {row['faster']} / {row['same']} / {row['slower']} | {row['mean_case_byte_hit_rate']:.2%} | {row['pooled_byte_hit_rate']:.2%} |")
    lines+=['','加速比先按每张图计算无 L2 / Cache Makespan，再按核数取六图算术平均。两种命中率分别为逐图平均与全部字节加权，不能混用。无 L2 命中率不适用。','',
        '## 具体发现','', '| 用例 | 核数 | 无 L2 cycles | Cache cycles | 耗时变化 | 字节命中率 |','|---|---:|---:|---:|---:|---:|']
    for row in rows:
        if row['case'] in ('case_039','case_072') or (row['case'],row['cores']) in (('case_051','2'),('case_078','3')):
            a,b=int(row['no_l2_makespan']),int(row['cache_makespan'])
            lines.append(f"| {row['case']} | {row['cores']} | {a} | {b} | {(b-a)/a:+.2%} | {float(row['byte_hit_rate']):.2%} |")
    lines+=['','命中率不直接决定 Makespan：case_078 三核存在命中但总耗时不变；case_039 多核缩短明显。事件统计可以定位重复读取与淘汰，但尚未完成关键路径消融，不能把全部收益归因于某一类事件。','',
        f'固定配置下发现 **{len(events)} 次**命中完成后插入事件，逐条列在 reinsertion_events.json；这些是对原实现的观测，未测量修正该行为的反事实影响。官方额外搬运量在同方案 A/B 间保持一致，不解释为实际 DDR 流量相同。','',
        '## 选择、成本与验证','',
        '- 开发图：'+', '.join(x['case'] for x in selection['cases'] if x['role']=='development')+'。',
        '- 预留图：'+', '.join(x['case'] for x in selection['cases'] if x['role']=='reserve')+'；本轮未读取其第三问性能。',
        '- 按单/多连通与规模三分位分六层，偏向共享输入较多的开发图；非随机样本，不代表全部100图。所有图已参与前两问，预留只表示未用于第三问调参。',
        f"- 评估累计 {summary['evaluation_seconds']:.3f} 秒；首轮批次墙钟 {manifest['invocations'][0]['wall_seconds']:.3f} 秒。顺序执行，单次180秒，无自动重试。",
        '- 本轮复用30个既有方案，未重新生成。上游 v011/v010 的生成及候选搜索成本不为零，详见第二问 v011 报告；本轮耗时不能称为冷启动总耗时。',
        '- 30个方案配对哈希、冻结选择、原配置/源码前后哈希、完整结果文件、容量及跨核等待已核对；24个多核无L2完整结果与第二问原JSON一致，6个单核分母一致。均值用 Fraction 独立复算。',
        '- 13项第三问测试通过；3个新增机制诊断通过。核内非DDR COPY边界未独立验证，因此不提供据此推导的实际DDR总流量。',
        '', '## 下一步','',
        '在同一开发集上先尝试固定分核的子图顺序调整，检查实际读取是否改变及 Makespan 是否改善；保留当前方案作为候选，并报告候选评估成本。冻结优化后再打开预留组，最后开展全量。此处仅为后续方向，本轮未执行。','',
        '## 复现','',
        '在主工作目录运行，使用新的实验编号：','', '```powershell',
        "& 'A题/.venv/Scripts/python.exe' -B 'A题/solution/experiments/run_problem3_baseline.py' --selection 'A题/solution/experiments/problem3_v001_selection.json' --experiment exp_new_problem3_development",
        '```','',
        '恢复原实验时使用原编号并添加 --resume；输入或源码改变时必须新建实验。comparison.csv 保存30项指标，metrics/ 保存完整结果及逐项事件诊断；source/ 保存冻结来源。','']
    (out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    import shutil
    shutil.copy2(__file__,out/'report_problem3_baseline.py')
    print(json.dumps({'audit':'passed','pairs':30,'reinsertion_events':len(events),'report':str(out/'REPORT.md')},ensure_ascii=False))


if __name__=='__main__':main()
