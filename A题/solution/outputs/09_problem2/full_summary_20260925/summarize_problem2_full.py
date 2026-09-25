"""Audit all frozen scene-B full batches and export reproducible paper outputs."""
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import zipfile

SOLUTION = Path(__file__).resolve().parents[1]
WORKSPACE = SOLUTION.parent.parent
ROOT = SOLUTION / 'outputs/09_problem2/raw/problem_2'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_write(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def audit_suite():
    state = read(ROOT / 'v007/full_suite_20260925/progress.json')
    if state['status'] not in ('completed', 'partial'):
        raise ValueError('full suite is still running or interrupted')
    for relative, expected in state['frozen_hashes'].items():
        if digest(WORKSPACE / relative) != expected:
            raise ValueError(f'current frozen materials differ: {relative}')
    rows, manifests, bad = [], [], []
    for batch in state['batches']:
        folder = ROOT / batch['version'] / batch['experiment']
        m = read(folder / 'manifest.json')
        if m['status'] not in ('completed','partial') or not m['protected_unchanged']:
            raise ValueError(f'incomplete or invalid run: {folder}')
        expected_keys = {(case,n) for case in batch['cases'] for n in batch['cores']}
        keys = {(r['case'],r['cores']) for r in m['items']}
        if keys != expected_keys or len(keys) != len(m['items']):
            raise ValueError('missing or duplicate configurations')
        if (m['parameters']['generation_timeout'],m['parameters']['evaluation_timeout']) != (30,180):
            raise ValueError('budget changed')
        for rel, expected in m['source_hashes'].items():
            if digest(folder/'source'/rel) != expected:
                raise ValueError(f'source snapshot corrupt: {rel}')
            parts=Path(rel).parts
            origin=None
            if parts[0]=='src': origin=SOLUTION/rel
            elif parts[0]=='code': origin=SOLUTION.parent/rel
            elif rel=='run_problem2.py': origin=SOLUTION/'experiments'/rel
            elif rel=='config.txt': origin=SOLUTION.parent/'data/config.txt'
            if origin is not None:
                frozen_key=str(origin.relative_to(WORKSPACE))
                if state['frozen_hashes'].get(frozen_key)!=expected:
                    raise ValueError(f'snapshot differs from frozen source: {rel}')
        for rel, expected in m['output_hashes'].items():
            if digest(folder/rel) != expected:
                raise ValueError(f'output corrupt: {rel}')
        for rel, expected in m['protected_hashes_before'].items():
            current = SOLUTION.parent / rel
            if digest(current) != expected:
                raise ValueError(f'protected input/config/code mismatch: {rel}')
        for item in m['items']:
            row = {'problem':2,'version':batch['version'],'experiment':batch['experiment'],
                   'case':item['case'],'cores':item['cores'],'status':item['status'],
                   'makespan':None, 'added_copy_bytes':None,'partition_added_copy_bytes':None,
                   'spill_added_copy_bytes':None,'cross_task_traffic':None,
                   'generation_seconds':item.get('generate',{}).get('seconds',0),
                   'evaluation_seconds':item.get('evaluate',{}).get('seconds',0),
                   'plan':str((folder/'plans'/f"{item['case']}_n{item['cores']}.json").relative_to(SOLUTION)),
                   'result':str((folder/'metrics'/f"{item['case']}_n{item['cores']}.json").relative_to(SOLUTION))}
            if item['status']=='success':
                result = read(SOLUTION/row['result'])
                if result['makespan'] != item['makespan'] or result['makespan'] <= 0:
                    raise ValueError('invalid makespan')
                if result['num_cores'] != item['cores'] or result['scene'] != 'B':
                    raise ValueError('wrong evaluation scene/core count')
                for peak in result['memory_peak_by_core'].values():
                    if any(peak[k] > result['capacity_bytes'][k] for k in peak):
                        raise ValueError('capacity violated')
                for link in result['cross_core_transfers']:
                    if link['copy_in_start'] < link['copy_out_end']+500:
                        raise ValueError('cross-core delay violated')
                row.update(makespan=result['makespan'],cross_task_traffic=result['cross_task_traffic'])
                row.update({k:result['data_movement_bytes'][k] for k in
                            ('added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes')})
                plan = read(SOLUTION/row['plan'])
                data = read(SOLUTION.parent/'data'/f"{item['case']}.json")
                expected_ops = {str(o['id']) for o in data['ops'] if o['op'] not in ('COPY_IN','COPY_OUT')}
                if set(plan['node_to_subgraph']) != expected_ops or len(plan['core_schedules']) != item['cores']:
                    raise ValueError('plan coverage mismatch')
            else:
                bad.append(row)
            rows.append(row)
        manifests.append({'path':str((folder/'manifest.json').relative_to(SOLUTION)),
                          'sha256':digest(folder/'manifest.json')})
    keyset={(r['version'],r['case'],r['cores']) for r in rows}
    if len(keyset)!=900 or len(rows)!=900:
        raise ValueError('expected exactly 900 unique attempts')
    return rows,bad,manifests


def summarize(rows):
    lookup={(r['version'],r['case'],r['cores']):r for r in rows}
    means, comparisons, slower = [],[],[]
    single_count=sum(r['version']=='single_v001' and r['status']=='success' for r in rows)
    for version in ('v002','v007'):
        means.append({'version':version,'cores':1,'count':single_count,
                      'mean_speedup':1.0 if single_count==100 else None,
                      'median_speedup':1.0 if single_count else None,
                      'min_speedup':1.0 if single_count else None,'max_speedup':1.0 if single_count else None,
                      'faster_than_single':0,'equal_to_single':single_count,'slower_than_single':0})
        for n in (2,3,4,5):
            ratios=[]
            for i in range(1,101):
                case=f'case_{i:03}'
                r,s=lookup[(version,case,n)],lookup[('single_v001',case,1)]
                if r['status']==s['status']=='success':
                    ratios.append(s['makespan']/r['makespan'])
                    if version=='v007' and r['makespan']>s['makespan']:
                        slower.append({'case':case,'cores':n,'single_makespan':s['makespan'],
                                       'v007_makespan':r['makespan'],'speedup':ratios[-1]})
            means.append({'version':version,'cores':n,'count':len(ratios),
                          'mean_speedup':statistics.mean(ratios) if len(ratios)==100 else None,
                          'median_speedup':statistics.median(ratios) if ratios else None,
                          'min_speedup':min(ratios) if ratios else None,'max_speedup':max(ratios) if ratios else None,
                          'faster_than_single':sum(r>1 for r in ratios),
                          'equal_to_single':sum(r==1 for r in ratios),'slower_than_single':sum(r<1 for r in ratios)})
    for i in range(1,101):
        for n in (2,3,4,5):
            case=f'case_{i:03}'
            a,b=lookup[('v002',case,n)],lookup[('v007',case,n)]
            valid=a['status']==b['status']=='success'
            outcome=('faster' if b['makespan']<a['makespan'] else 'slower' if b['makespan']>a['makespan'] else 'equal') if valid else 'unavailable'
            comparisons.append({'case':case,'cores':n,'v002_status':a['status'],'v007_status':b['status'],
                                'v002_makespan':a['makespan'],'v007_makespan':b['makespan'],'outcome':outcome,
                                'makespan_reduction_pct':100*(1-b['makespan']/a['makespan']) if valid else None,
                                'v002_added_copy_bytes':a['added_copy_bytes'],'v007_added_copy_bytes':b['added_copy_bytes'],
                                'v002_spill_bytes':a['spill_added_copy_bytes'],'v007_spill_bytes':b['spill_added_copy_bytes']})
    return means,comparisons,slower


def figure(out, means):
    if any(r['mean_speedup'] is None for r in means):
        return []
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','pdf.fonttype':42})
    fig,ax=plt.subplots(figsize=(7.2,4.5),layout='constrained')
    for version,color,style,marker in [('v007','#176EAC','-','o'),('v002','#B67523','--','s')]:
        series=[r for r in means if r['version']==version]
        ax.plot([r['cores'] for r in series],[r['mean_speedup'] for r in series],
                color=color,linestyle=style,marker=marker,linewidth=1.8,label=version)
        final=series[-1]
        ax.annotate(f"{version}: {final['mean_speedup']:.3f}",(5,final['mean_speedup']),
                    xytext=(8,8 if version=='v007' else -13),textcoords='offset points',color=color)
    ax.axhline(1,color='#666666',linewidth=.8)
    ax.set(xlabel='Number of cores',ylabel='Mean speedup (single-core / multi-core)',
           title='Problem 2 · Scene B · 100 graphs',xticks=[1,2,3,4,5],xlim=(.85,5.9),ylim=(0,None))
    ax.grid(axis='y',alpha=.18)
    ax.spines[['top','right']].set_visible(False)
    ax.legend(frameon=False,loc='upper left')
    fig.text(.5,-.035,'Arithmetic mean of 100 per-graph ratios; one candidate per method and configuration.',ha='center',fontsize=8)
    files=[]
    for extension in ('png','svg','pdf'):
        path=out/f'mean_speedup.{extension}'
        fig.savefig(path,dpi=200,bbox_inches='tight')
        files.append(path.name)
    plt.close(fig)
    return files


def main():
    out=SOLUTION/'outputs/09_problem2/full_summary_20260925'
    if out.exists():
        raise FileExistsError(out)
    rows,bad,manifests=audit_suite()
    # Q2 defines speedup using the same whole-graph single-core reference as Q1.
    # Check all current inputs/config against the archived Q1 freeze and compare
    # the newly simulated B/one-core values to those official-entry references.
    old_freeze=read(SOLUTION/'experiments/v009_full_selection.json')
    for rel,expected in old_freeze['protected_hashes'].items():
        if rel.startswith('data') and digest(SOLUTION.parent/rel)!=expected:
            raise ValueError('Q1 single reference inputs/config no longer match')
    single_reference_path=SOLUTION/'outputs/08_full/single_references.csv'
    with single_reference_path.open(encoding='utf-8-sig',newline='') as stream:
        historical=list(csv.DictReader(stream))
    reference={r['case']:r for r in historical}
    if len(reference)!=100 or len(historical)!=100:
        raise ValueError('invalid archived official single-reference coverage')
    single_matches=0
    for row in rows:
        if row['version']=='single_v001' and row['status']=='success':
            old=reference[row['case']]
            if old['status']!='ok' or float(old['makespan'])!=row['makespan']:
                raise ValueError(f"single-reference mismatch: {row['case']}")
            single_matches+=1
    means,comparison,slower=summarize(rows)
    out.mkdir()
    csv_write(out/'all_results.csv',rows)
    csv_write(out/'mean_speedup.csv',means)
    csv_write(out/'comparison.csv',comparison)
    if bad: csv_write(out/'failed_attempts.csv',bad)
    if slower: csv_write(out/'slower_than_single.csv',slower)
    selected=[r for r in rows if r['version']=='v007' and r['status']=='success']
    archive_name='v007_plans.zip' if len(selected)==400 else 'v007_partial_plans.zip'
    with zipfile.ZipFile(out/archive_name,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for row in selected:
            archive.write(SOLUTION/row['plan'],f"{row['case']}_n{row['cores']}.json")
    with zipfile.ZipFile(out/archive_name) as archive:
        if len(archive.namelist())!=len(selected):
            raise ValueError('duplicate plan archive names')
        for row in selected:
            data=archive.read(f"{row['case']}_n{row['cores']}.json")
            if hashlib.sha256(data).hexdigest()!=digest(SOLUTION/row['plan']):
                raise ValueError('plan archive mismatch')
    charts=figure(out,means)
    counts={k:sum(r['outcome']==k for r in comparison) for k in ('faster','equal','slower','unavailable')}
    lines=['# 第二问全量评估', '',
           f"共 900 个评估配置：v007 400 个、v002 对照 400 个、场景 B 单核 100 个。成功 {900-len(bad)}，失败/超时 {len(bad)}。", '',
           'v007 保持原区域方法的分核，多分量图每次交错安排两个独立分量；单连通图沿用原方法。两方法每配置均只生成并评估一个候选，生成/评估预算 30/180 秒，无自动重试。', '',
           '| 核数 | v007 平均加速比 | v002 平均加速比 | v007 比单核快 / 平 / 慢 |',
           '|---|---:|---:|---|']
    for n in (1,2,3,4,5):
        a=next(r for r in means if r['version']=='v007' and r['cores']==n)
        b=next(r for r in means if r['version']=='v002' and r['cores']==n)
        av=f"{a['mean_speedup']:.4f}" if a['mean_speedup'] is not None else f"未齐（{a['count']}/100）"
        bv=f"{b['mean_speedup']:.4f}" if b['mean_speedup'] is not None else f"未齐（{b['count']}/100）"
        lines.append(f"| {n} | {av} | {bv} | {a['faster_than_single']} / {a['equal_to_single']} / {a['slower_than_single']} |")
    lines+=['','平均加速比先按每张图计算“单核时间 / 多核时间”，再对全部 100 张图取算术平均。分母缺失时不报告完整均值。', '',
            f"v007 相对 v002：{counts['faster']} 快、{counts['equal']} 平、{counts['slower']} 慢、{counts['unavailable']} 不可比较。全量退步配置不能被开发集和新检验集的改善掩盖。",'']
    if charts: lines.append('![全量平均加速比](mean_speedup.png)')
    regressions=sorted((r for r in comparison if r['outcome']=='slower'),
                       key=lambda r:r['makespan_reduction_pct'])
    if regressions:
        lines+=['','## 相对 v002 退步最大的配置','',
                '| 图 | 核数 | v002 Makespan | v007 Makespan | 耗时增加 |',
                '|---|---:|---:|---:|---:|']
        for r in regressions[:5]:
            lines.append(f"| {r['case']} | {r['cores']} | {r['v002_makespan']} | {r['v007_makespan']} | {-r['makespan_reduction_pct']:.2f}% |")
    lines+=['',f'v007 共 {len(slower)} 个配置慢于对应单核参考；详细记录单列，不将这些配置从均值中剔除。']
    lines+=['','## 求解成本','','| 方法 | 生成秒数 | 评估秒数 |','|---|---:|---:|']
    for version in ('v007','v002','single_v001'):
        group=[r for r in rows if r['version']==version]
        lines.append(f"| {version} | {sum(r['generation_seconds'] for r in group):.3f} | {sum(r['evaluation_seconds'] for r in group):.3f} |")
    lines+=['','## 完整性与边界','',
            '- 100 张图及全部核数组合覆盖、输入/配置/代码冻结哈希、方案/结果/日志和源码快照哈希均已核对。',
            f'- 本轮场景 B 一核结果中 {single_matches} 项与第一问归档的官方单核入口成绩逐图一致；对应原始输入和配置哈希一致。加速比分母按题目两问相同定义使用；这项数值核对不主张两个评估器在任意输入上等价。',
            '- 成功结果逐项检查操作覆盖、核数、正 Makespan、内存容量峰值和跨核 COPY 等待至少 500 cycles；这些检查不代替对整个评估器的形式证明。',
            '- 完整逐图表为 all_results.csv；比较及搬运量为 comparison.csv；图的数据源为 mean_speedup.csv。',
            '- 每项方案和完整原始结果的路径列在 all_results.csv；原始实验保留于上一级 raw/problem_2/。',
            f'- [{archive_name}]({archive_name}) 包含 {len(selected)} 个成功的 v007 方案，逐文件核对与原始方案相同。',
            '- v007 比单核慢的项列在 slower_than_single.csv（如有）；失败/超时列在 failed_attempts.csv（如有）。',
            '- 全量包含此前的开发与检验图，不能作为另一份独立检验证据；仅对本题固定配置下的模拟结果作结论。']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    shutil.copy2(Path(__file__),out/Path(__file__).name)
    audit={'status':'complete' if not bad else 'partial','attempts':len(rows),'success':900-len(bad),
           'failures':len(bad),'comparisons':counts,'source_manifests':manifests,
           'official_single_reference_matches':single_matches,
           'historical_single_reference_sha256':digest(single_reference_path),
           'files':{p.name:digest(p) for p in out.iterdir() if p.is_file()}}
    (out/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'success':900-len(bad),'failed':len(bad),'comparison':counts}))


if __name__=='__main__':
    main()
