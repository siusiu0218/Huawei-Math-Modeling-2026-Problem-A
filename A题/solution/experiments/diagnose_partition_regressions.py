"""Reconstruct a 2x2 partition diagnostic from immutable original-evaluator runs."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

SOLUTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION / 'src'))
from graph_analysis import A_ROOT, Graph, analyze_graph
from component_scheduler import independent_components
from result_paths import result_path

RUNS = {
    ('baseline', 4): 'v001/exp002_20260924_baseline',
    ('baseline', 16): 'v001/exp008_20260924_baseline_diagnosis16',
    ('components', 4): 'v002/exp007_20260924_components_diagnosis4',
    ('components', 16): 'v002/exp006_20260924_components_holdout',
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def union_duration(ops):
    end, duration = 0, 0
    for start, stop in sorted((op['start'], op['end']) for op in ops):
        if start < 0 or stop < start:
            raise ValueError('invalid interval')
        duration += max(0, stop - max(start, end))
        end = max(end, stop)
    return duration


def decompose(result):
    # One latest-finishing core, not sums across cores or a causal attribution model.
    core_id, core = max(enumerate(result['per_core_timeline']),
                       key=lambda item: max((t['end'] for t in item[1]['tasks']), default=0))
    tasks, ops = core['tasks'], core['ops']
    assert max(t['end'] for t in tasks) == result['makespan']
    assert all(o['pipe'] in {'PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3'} for o in ops)
    active = union_duration(tasks)
    assert active == sum(t['duration'] for t in tasks), 'overlapping tasks on one core'
    compute = union_duration([o for o in ops if o['pipe'] in {'PIPE_M', 'PIPE_V'}])
    all_pipes = union_duration(ops)
    values = {
        'last_core': core_id, 'last_core_tasks': len(tasks),
        'compute_union': compute, 'copy_without_compute': all_pipes - compute,
        'active_without_pipe': active - all_pipes,
        'outside_tasks': result['makespan'] - active,
    }
    assert all(values[k] >= 0 for k in ('compute_union', 'copy_without_compute',
                                       'active_without_pipe', 'outside_tasks'))
    assert sum(values[k] for k in ('compute_union', 'copy_without_compute',
                                  'active_without_pipe', 'outside_tasks')) == result['makespan']
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='New directory; never overwrites a diagnosis')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    records, evidence, plans, protected, structures = [], {}, {}, None, {}
    reference_config = None
    for (algorithm, multiplier), name in RUNS.items():
        run = result_path(Path('problem_1') / name)
        manifest_path = run / 'manifest.json'
        manifest = read(manifest_path)
        # A historical run may include unrelated failed single-core references.
        # Every selected cell must independently have status=ok below.
        assert manifest['status'] in {'completed', 'completed_with_failures'} and manifest['protected_inputs_unchanged']
        assert manifest['parameters']['blocks_per_core'] == multiplier
        assert manifest['parameters'].get('algorithm', 'baseline') == algorithm
        if protected is None:
            protected = manifest['protected_hashes_before']
        assert protected == manifest['protected_hashes_before']
        config = (manifest['evaluation_config'], manifest['wait_config'])
        if reference_config is None:
            reference_config = config
        assert config == reference_config, 'evaluation settings differ'
        evidence[str(manifest_path)] = sha(manifest_path)
        for case in ('case_016', 'case_095'):
            for cores in (2, 3, 4, 5):
                key = f'{case}_n{cores}'
                result_path = run / 'metrics' / f'{key}_result.json'
                status_path = run / 'metrics' / f'{key}_status.json'
                plan_path = run / 'plans' / f'{key}.json'
                assert read(status_path)['status'] == 'ok'
                result = read(result_path)
                plans[case, cores, algorithm, multiplier] = read(plan_path)
                for path in (result_path, status_path, plan_path):
                    evidence[str(path)] = sha(path)
                records.append(dict(case=case, cores=cores, algorithm=algorithm,
                                    multiplier=multiplier, source_run=name,
                                    makespan=result['makespan'],
                                    used_cores=sum(bool(c['tasks']) for c in result['per_core_timeline']),
                                    added_bytes=result['data_movement_bytes']['added_copy_bytes'],
                                    scheduled_bytes=result['data_movement_bytes']['scheduled_copy_bytes'],
                                    **decompose(result)))
    for name, digest in protected.items():
        assert sha(A_ROOT / name) == digest, name
    for case in ('case_016', 'case_095'):
        data = read(A_ROOT / 'data' / f'{case}.json')
        structures[case] = dict(components=len(independent_components(Graph(data))),
                                **analyze_graph(data))
    indexed = {(r['case'], r['cores'], r['algorithm'], r['multiplier']): r for r in records}
    for cores in (2, 3, 4, 5):
        for multiplier in (4, 16):
            assert plans['case_016', cores, 'baseline', multiplier] == plans['case_016', cores, 'components', multiplier]
            assert indexed['case_016', cores, 'baseline', multiplier]['makespan'] == indexed['case_016', cores, 'components', multiplier]['makespan']
    with (output / 'factorial.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    lines = ['# 切块退步诊断：case_016 与 case_095', '',
             '这是对已查看检验结果的后续诊断，不是新的独立泛化检验。补跑 exp007（v002、倍率4）与 exp008（v001、倍率16），各8项，均成功。与既有结果组成两种算法 × 两个倍率 × 两张图 × 四个核数的32格对照；新增16次评估。原始程序和固定配置不变，每格1个候选。', '',
             '## 同参数对照', '',
             '| 图 | 核数 | v001 ×4 | v002 ×4 | v001 ×16 | v002 ×16 |',
             '|---|---:|---:|---:|---:|---:|']
    for case in ('case_016', 'case_095'):
        for cores in (2, 3, 4, 5):
            values = [indexed[case, cores, alg, mult]['makespan'] for alg, mult in
                      [('baseline', 4), ('components', 4), ('baseline', 16), ('components', 16)]]
            lines.append(f'| {case} | {cores} | ' + ' | '.join(f'{v:,}' for v in values) + ' |')
    lines += ['', '## 四核时间线分解', '',
              '取最晚完成的核心，将其从0到Makespan的时间分为互不重叠的四类。计算活动按 PIPE_M/PIPE_V 区间并集计；“仅搬运”是搬运活动但没有计算活动的时间；不是搬运持续时间之和，也不等于搬运字节除带宽。', '',
              '| 图 | v002倍率 | Makespan | 计算活动 | 仅搬运 | Task内无流水线活动 | Task外时间 | 额外bytes |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for case in ('case_016', 'case_095'):
        for mult in (4, 16):
            r = indexed[case, 4, 'components', mult]
            lines.append(f'| {case} | {mult} | ' + ' | '.join(f"{r[k]:,}" for k in
                         ('makespan', 'compute_union', 'copy_without_compute', 'active_without_pipe', 'outside_tasks', 'added_bytes')) + ' |')
    lines += ['', '## 已确认与尚不能推出的结论', '',
              '- case_016：相同倍率下，两版全部四种核数的方案内容与Makespan完全一致；退步由此次倍率变化引起，不能归咎于独立分组算法。四核仍只用1核，16个Task变为64个；多出的55,762周期分为Task间隔增加4,800与仅搬运时间增加50,962。切分额外搬运从6,095,228增至27,920,008 bytes。',
              '- case_016 原图有一个连通分量，但最大层宽为12、计算总量/最长计算链约11.78；“连通”不等于“不能并行”。这两个静态指标也不保证能获得对应加速倍数。',
              '- case_095：v002倍率4和16的额外搬运均为0；四核总搬运都为11,355,036 bytes。两者最晚完成核心的计算活动均为523,392周期。细粒度多出的8,616周期中，1,200是任务间隔，7,416是仅搬运活动增加；并非多搬数据，不能直接解释为负载更不均或DDR争用更重。',
              '- case_095 在相同倍率4下，v002四种核数都快于v001；四核只快103周期，三核与五核的改善较大。与原基线相比的退步主要应沿切分粒度解释，而不是认定分组方向失败。',
              '- 时间线分解是精确记账，不是对缓存、带宽争用、任务启动尾部等内部机制的独立因果实验；没有把各流水线持续时间直接相加。', '',
              '## 第三版设计约束', '',
              '1. 不再把统一增大Task数量作为默认改进。多分量图保留完整分量，评估减少Task边界能否维持负载均衡；共享输入应在同一Task内部复用，而非仅放在同核。',
              '2. 单连通图需要内部依赖感知切分：优先保留长计算链与大张量连接，在分叉处寻找并行任务，并检查收缩后的Task图无环；简单恢复倍率4只能消除此次退步，不能解决只用1核。',
              '3. 先做算法×粒度对照，再决定自适应规则；匹配每图候选预算。新版本可使用这两图开发，但不能再把它们称为未见检验图。另留未参与调参的图，并在运行前冻结代码和选择规则。',
              '4. 本阶段未实现v003、未修改原评估器、未补齐case_014单核，也未进行100图全量性能验证。', '',
              '复现：`python -B A题/solution/experiments/diagnose_partition_regressions.py --output <新的输出目录>`。输入实验相对位置固定在脚本 RUNS 中；输入哈希和脚本快照见 manifest.json 与 source/。', '']
    (output / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    (output / 'source').mkdir()
    shutil.copy2(__file__, output / 'source' / Path(__file__).name)
    manifest = dict(status='completed', purpose='post-hoc diagnostic; no new holdout claim',
                    utc=datetime.now(timezone.utc).isoformat(), invocation=[sys.executable, '-B', *sys.argv],
                    input_hashes=evidence, protected_inputs_unchanged=True, structures=structures,
                    script_sha256=sha(Path(__file__)), rows=len(records),
                    output_hashes={name: sha(output / name) for name in ('REPORT.md', 'factorial.csv')})
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Validated {len(records)} cells; matched plans and times; original materials unchanged. {output}')


if __name__ == '__main__':
    main()
