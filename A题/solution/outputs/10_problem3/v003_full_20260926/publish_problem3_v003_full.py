"""Create auditable full-suite figures and a compact local delivery package."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys
import zipfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(raw, out):
    summary = json.loads((raw/'summary.json').read_text(encoding='utf-8'))
    manifest = json.loads((raw/'manifest.json').read_text(encoding='utf-8'))
    assert summary['audit'] == 'passed' and summary['scope'] == 'full'
    assert summary['successful_configurations'] == 500 and not summary['failures']
    with (raw/'comparison.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 500
    out.mkdir(parents=True, exist_ok=False); (out/'figures').mkdir()
    for name in ['comparison.csv', 'summary.json', 'audit_provenance.json']:
        shutil.copy2(raw/name, out/name)
    font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
    plt.rcParams.update({'font.family': font_manager.FontProperties(fname='C:/Windows/Fonts/msyh.ttc').get_name(),
                         'axes.unicode_minus': False, 'font.size': 11, 'svg.fonttype': 'none',
                         'axes.spines.top': False, 'axes.spines.right': False})
    n = list(range(1, 6)); groups = [[r for r in rows if int(r['cores']) == k] for k in n]
    assert all(len(g) == 100 for g in groups)
    d = [statistics.mean(float(r['D_selected_no_l2']) for r in g)/1e6 for g in groups]
    c = [statistics.mean(float(r['C_selected_cache']) for r in g)/1e6 for g in groups]
    by = summary['by_cores']; curve_data = []
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.9))
    axes[0].plot(n, d, marker='o', color='#576574', label='同一入选方案：无L2')
    axes[0].plot(n, c, marker='s', color='#007C83', label='同一入选方案：只读Cache')
    axes[0].set(xlabel='核数', ylabel='100图平均 Makespan（百万cycles）', title='A  入选调度方案的平均完成时间', xticks=n)
    axes[0].legend(frameon=False, fontsize=9)
    axes[1].plot(n, [r['cache_speedup_same_plan'] for r in by], marker='o', color='#007C83', label='同方案 Cache 加速比 D/C')
    axes[1].axhline(1, ls='--', color='#A7A7A7', lw=1)
    for x, r in zip(n, by):
        axes[1].annotate(f"{r['cache_speedup_same_plan']:.4f}", (x, r['cache_speedup_same_plan']), xytext=(0, 9), textcoords='offset points', ha='center', fontsize=9)
    axes[1].set(xlabel='核数', ylabel='逐图加速比的算术平均', title='B  Cache收益：无L2 / Cache', xticks=n)
    axes[1].margins(y=.25)
    for ax in axes: ax.grid(axis='y', alpha=.2)
    fig.suptitle('第三问 v003 · 100图 × 1～5核 · exp121', fontsize=14)
    fig.text(.5, .012, '固定1 MB Cache、250 bytes/cycle；每个核数均含100图。A为时间均值，B为逐图比值均值，两者不能混算。', ha='center', fontsize=9)
    fig.tight_layout(rect=[0, .055, 1, .95])
    for ext in ['png', 'svg', 'pdf']: fig.savefig(out/'figures'/f'cache_curves.{ext}', dpi=240)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.9))
    for field, color, label in [('baseline_cache_speedup', '#74818B', '原方案 Cache 加速比 A/B'),
                                ('cache_speedup_same_plan', '#007C83', '入选方案 Cache 加速比 D/C'),
                                ('schedule_speedup', '#6F4E8B', 'Cache条件下调度加速比 B/C')]:
        axes[0].plot(n, [r[field] for r in by], marker='o', color=color, label=label)
    axes[0].axhline(1, ls='--', color='#A7A7A7', lw=1)
    axes[0].set(xlabel='核数', ylabel='逐图比值的算术平均', title='A  分开报告Cache与调度收益', xticks=n)
    axes[0].legend(frameon=False, fontsize=8)
    fast = [sum(float(r['width1_cache']) < float(r['B_baseline_cache']) for r in g) for g in groups]
    equal = [sum(float(r['width1_cache']) == float(r['B_baseline_cache']) for r in g) for g in groups]
    slow = [100-a-b for a,b in zip(fast, equal)]
    bottom = [0]*5
    for values, color, label in [(fast, '#007C83', '直接候选更快'), (equal, '#BEC5CB', '持平'), (slow, '#BB6528', '更慢')]:
        axes[1].bar(n, values, bottom=bottom, color=color, label=label, width=.65)
        for x, h, y in zip(n, values, bottom):
            if h: axes[1].text(x, y+h/2, str(h), ha='center', va='center', color='white' if color != '#BEC5CB' else '#202428', fontsize=10)
        bottom = [a+b for a,b in zip(bottom, values)]
    axes[1].set(xlabel='核数', ylabel='图数', title='B  保留基线之前：候选有收益也有退化', xticks=n, ylim=(0, 112))
    axes[1].legend(frameon=False, ncol=3, fontsize=8, loc='upper center', bbox_to_anchor=(.5, 1.02))
    axes[0].grid(axis='y', alpha=.2)
    fig.suptitle('第三问 v003 · 全量排序收益与候选适用范围 · exp121', fontsize=14)
    fig.text(.5, .012, '最终方法在原方案与候选中择优，平局保留原方案；择优后的不退步不代表新候选普遍有效。', ha='center', fontsize=9)
    fig.tight_layout(rect=[0, .055, 1, .95])
    for ext in ['png', 'svg', 'pdf']: fig.savefig(out/'figures'/f'scheduling_results.{ext}', dpi=240)
    plt.close(fig)
    for k, nd, nc, br, nf, ne, ns in zip(n, d, c, by, fast, equal, slow):
        curve_data.append({'cores': k, 'cases': 100, 'mean_no_l2_cycles': nd*1e6, 'mean_cache_cycles': nc*1e6,
                           **br, 'direct_faster': nf, 'direct_equal': ne, 'direct_slower': ns})
    with (out/'figure_data.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(curve_data[0])); writer.writeheader(); writer.writerows(curve_data)
    biggest = max(rows, key=lambda r: float(r['schedule_reduction_percent']))
    five_reduction = statistics.mean(float(r['schedule_reduction_percent']) for r in rows if int(r['cores']) == 5)
    costs = summary['costs']; direct = summary['direct_width1']
    text = f'''# 第三问 v003：全100图评估报告

## 完成情况与结论

已覆盖 **100图 × 1～5核，共500个配置**。每个入选方案均有同方案无L2/Cache结果，原方案A/B对照也齐全。全部500配置通过独立审计，无缺失、失败或超时。采用原始评估器与固定配置；算法及候选预算全程冻结。

直接新候选：**{direct['faster']}项更快、{direct['equal']}项持平、{direct['slower']}项更慢**。最终与原方案择优后，**{summary['selected_faster']}项改善、{500-summary['selected_faster']}项持平**。直接候选最差耗时增加{summary['max_direct_regression_percent']:.3f}%，因此不能省略原方案比较。

最大调度改善出现在{biggest['case']}、{biggest['cores']}核：{biggest['B_baseline_cache']}→{biggest['C_selected_cache']} cycles，减少{float(biggest['schedule_reduction_percent']):.3f}%。这只是最大单项，不代表平均收益。

## Cache对照曲线

![同方案Cache对照曲线](figures/cache_curves.png)

左图是100图Makespan的算术平均；右图先计算每图无L2/Cache比值再求平均。二者是不同聚合指标，不能用平均时间之比代替右图。每个核数上的无L2和Cache评估使用完全相同的入选方案。核数指可用核预算，方案允许包含空闲核，不保证所有核都分配工作。

## 调度优化的收益与边界

![调度收益与候选退化](figures/scheduling_results.png)

主方法仍为固定的baseline+width1，两候选按Cache Makespan择优、平局保留baseline；未根据全量成绩改变排序或参数。小规模开发及预留检验的等预算width2对照已保留于exp116/117；本次全量没有追加该对照。

## 计算成本

新增候选生成{costs['candidate_generations']}次，累计{costs['generation_seconds']:.3f}秒；实际新增评估{costs['new_evaluations']}次，累计{costs['evaluation_seconds']:.3f}秒。外部哈希核验复用{costs['external_reuses']}份结果，同方案内部去重{costs['internal_duplicates']}份结果。

执行循环墙钟{summary['invocation_wall_seconds']:.3f}秒，不含归档初始化、索引构建、审计和作图。Q2起点及旧Q3结果的上游搜索/评估成本不为零，来源保留在原始manifest；此处不声称是冷启动总成本。算法求解秒数与Makespan cycles分开报告。

## 核验与已知限制

- 500配置完整覆盖；方案归属与分核、依赖合法性、结果哈希、固定Cache容量、跨核等待和命中率口径均已核对。逐图比较表重新选择最低Cache Makespan，平局保留baseline。
- 新入口已通过超时及手动中断清理、结果篡改拒绝、并发锁、断点恢复和重复启动检查。禁用复用重新计算的四份完整JSON与旧结果一致。旧冻结入口保留原样；本轮使用新进程树清理入口。
- 原评估器命中读取完成后的重新插入行为继续沿用并披露。逐候选事件计数见summary.json。官方额外搬运量不解释为Cache后的实际DDR流量。
- Cache可能使部分固定方案变慢，按核数的快/平/慢计数完整保留。全100图包含开发和预留图，是题目数据集的完整覆盖，不能称新的未见测试集或全局最优证明。

## 交付文件

- `comparison.csv`：500配置的A/B/C/D Makespan、命中率、额外搬运、选择结果与原始结果路径。
- `figure_data.csv`：两组图的全部聚合数据；`figures/`：PNG、SVG、PDF。
- `selected_plans.zip`：500个入选方案，文件名包含用例及核数。
- `summary.json`：覆盖、成本、失败清单、每核数指标与评估器特殊行为计数。
- `METHOD.md`和`PREFLIGHT.md`：算法范围及全量前检查；[事后空间分析](posthoc/REPORT.md)由analyze_problem3_headroom.py单独生成。
- 原始完整目录：`{raw}`，包含全部候选、完整评估JSON、日志、源码快照、来源及复现命令。

五核下逐图耗时降幅的平均值为{five_reduction:.4f}%，说明当前排序改进总体较小。当前保留这版有基线保护、可复现的算法，下一步整理第三问的模型、算法说明与结果分析。若进一步优化，应先从事后分析中筛选仍有空间且具有具体搬运/等待证据的配置，不直接再次进行全图调参。
'''
    (out/'REPORT.md').write_text(text, encoding='utf-8')
    shutil.copy2(raw/'REPORT.md', out/'AUDIT_REPORT.md')
    shutil.copy2(Path(__file__).with_name('problem3_v003_METHOD.md'), out/'METHOD.md')
    preflight = Path(__file__).resolve().parents[1]/'outputs/10_problem3/raw/scratch/full_preflight_20260926/REPORT.md'
    shutil.copy2(preflight, out/'PREFLIGHT.md')
    with zipfile.ZipFile(out/'selected_plans.zip', 'w', compression=zipfile.ZIP_DEFLATED) as z:
        plans = sorted((raw/'selected_plans').glob('*.json')); assert len(plans) == 500
        for p in plans: z.write(p, p.name)
    provenance = {'raw_manifest_sha256': digest(raw/'manifest.json'), 'raw_summary_sha256': digest(raw/'summary.json'),
                  'script_sha256': digest(Path(__file__)), 'matplotlib_version': matplotlib.__version__,
                  'python': sys.version,
                  'files': {str(p.relative_to(out)): digest(p) for p in out.rglob('*') if p.is_file()}}
    (out/'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding='utf-8')
    shutil.copy2(Path(__file__), out/Path(__file__).name)
    print(json.dumps({'out': str(out), 'configs': 500, 'selected_faster': summary['selected_faster']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('raw'); parser.add_argument('out'); args = parser.parse_args()
    main(Path(args.raw).resolve(), Path(args.out).resolve())
