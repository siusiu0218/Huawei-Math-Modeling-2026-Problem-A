"""Compare two archived scene-B runs, including failures and spill traffic."""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def audit(folder):
    manifest = read(folder / 'manifest.json')
    if manifest['status'] not in ('completed', 'partial') or not manifest['protected_unchanged']:
        raise ValueError('run incomplete or protected materials changed')
    for relative, digest in manifest['output_hashes'].items():
        if hashlib.sha256((folder / relative).read_bytes()).hexdigest() != digest:
            raise ValueError(f'output hash mismatch: {relative}')
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    a, b = audit(args.baseline), audit(args.candidate)
    if a['protected_hashes_before'] != b['protected_hashes_before']:
        raise ValueError('different input/config/evaluator materials')
    for key in ('cores', 'generation_timeout', 'evaluation_timeout'):
        if a['parameters'][key] != b['parameters'][key]:
            raise ValueError(f'comparison parameter mismatch: {key}')
    ar = {(r['case'],r['cores']):r for r in a['items']}
    br = {(r['case'],r['cores']):r for r in b['items']}
    if set(ar) != set(br) or len(ar) != len(a['items']) or len(br) != len(b['items']):
        raise ValueError('case coverage mismatch or duplicate rows')
    counts = {'faster':0,'equal':0,'slower':0,'unavailable':0}
    rows = []
    lines = ['# 第二问同条件比较', '',
             f"基线：{a['algorithm_version']} / {a['experiment']}；候选：{b['algorithm_version']} / {b['experiment']}。", '',
             '| 图 | 核数 | 基线 Makespan | 候选 Makespan | 变化 | 基线 spill bytes | 候选 spill bytes |',
             '|---|---:|---:|---:|---|---:|---:|']
    for key in sorted(ar):
        x, y = ar[key], br[key]
        valid = x['status'] == y['status'] == 'success'
        verdict = ('faster' if y['makespan'] < x['makespan'] else
                   'slower' if y['makespan'] > x['makespan'] else 'equal') if valid else 'unavailable'
        counts[verdict] += 1
        row = {'case':key[0],'cores':key[1],'verdict':verdict,
               'baseline':x,'candidate':y}
        rows.append(row)
        xs = x.get('data_movement_bytes',{}).get('spill_added_copy_bytes','NA')
        ys = y.get('data_movement_bytes',{}).get('spill_added_copy_bytes','NA')
        lines.append(f"| {key[0]} | {key[1]} | {x.get('makespan', x['status'])} | {y.get('makespan', y['status'])} | {verdict} | {xs} | {ys} |")
    lines += ['', '全部配置计数：'+json.dumps(counts), '',
              '输入、配置、评估代码、方案、结果和日志哈希核对通过。每配置一个候选；生成/评估预算相同。失败或超时保留在计数中。']
    for label, m in [('baseline',a),('candidate',b)]:
        g = sum(r.get('generate',{}).get('seconds',0) for r in m['items'])
        e = sum(r.get('evaluate',{}).get('seconds',0) for r in m['items'])
        lines.append(f'\n{label}：生成 {g:.3f} 秒，评估 {e:.3f} 秒。')
    if args.output.exists() or args.output.with_suffix('.json').exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    args.output.with_suffix('.json').write_text(json.dumps({'counts':counts,'rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
