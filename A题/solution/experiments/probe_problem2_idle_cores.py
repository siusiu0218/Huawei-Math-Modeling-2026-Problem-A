"""Exploratory five-core evaluation of archived two-active-core plans.

This is a three-case mechanism check, not a general algorithm or full benchmark.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

from run_problem2 import run_command, save

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from portfolio_scheduler import validate_result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline = ROOT / 'outputs/09_problem2/raw/problem_2/v010/exp107_20260925_portfolio_full'
    full = json.loads((baseline / 'manifest.json').read_text(encoding='utf-8'))
    assert full['status'] == 'completed', 'run only after the full baseline finishes'
    out = ROOT / 'outputs/09_problem2/raw/scratch/idle_cores_probe_20260925'
    out.mkdir(exist_ok=False)
    cases = ('case_005', 'case_086', 'case_044')
    protected = list((ROOT.parent / 'code').glob('*.py')) + [ROOT.parent / 'data/config.txt']
    protected += [ROOT.parent / 'data' / f'{case}.json' for case in cases]
    before = {str(p): sha(p) for p in protected}
    shutil.copy2(__file__, out / Path(__file__).name)
    rows = []
    manifest = {'purpose': 'three-case exploratory five-core validation of two active cores',
                'started_utc': datetime.now(timezone.utc).isoformat(), 'items': rows,
                'protected_hashes_before': before, 'status': 'running'}
    save(out / 'manifest.json', manifest)
    for case in cases:
        source = baseline / 'plans' / f'{case}_n2.json'
        shutil.copy2(source, out / f'{case}_original_n2.json')
        plan = json.loads(source.read_text(encoding='utf-8'))
        assert len(plan['core_schedules']) == 2
        plan['core_schedules'] += [[], [], []]
        target = out / f'{case}_n5.json'
        result = out / f'{case}_n5_result.json'
        save(target, plan)
        row = {'case': case, 'source': str(source.relative_to(ROOT)), 'source_sha256': sha(source)}
        row['evaluation'] = run_command([
            sys.executable, '-B', str(ROOT / 'experiments/run_problem2.py'), '--worker', 'evaluate',
            '--input', str(ROOT.parent / 'data' / f'{case}.json'), '--config', str(ROOT.parent / 'data/config.txt'),
            '--plan', str(target), '--result', str(result), '--n', '5'], out / f'{case}.log', 180)
        row['status'] = row['evaluation']['status']
        if row['status'] == 'success':
            row.update(validate_result(json.loads(result.read_text(encoding='utf-8')), 5))
            old = next(r for r in full['items'] if r['case'] == case and r['cores'] == 5)
            row['baseline_five_core_makespan'] = old['makespan']
            row['time_reduction_percent'] = 100 * (1 - row['makespan'] / old['makespan'])
        rows.append(row)
        save(out / 'manifest.json', manifest)
    manifest['protected_unchanged'] = all(sha(p) == before[str(p)] for p in protected)
    manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
    manifest['status'] = 'completed' if all(r['status'] == 'success' for r in rows) else 'partial'
    manifest['output_hashes'] = {p.name: sha(p) for p in out.iterdir() if p.is_file() and p.name != 'manifest.json'}
    save(out / 'manifest.json', manifest)
    with (ROOT / 'experiments/INDEX.md').open('a', encoding='utf-8') as stream:
        stream.write('\n- 问题 2 探索性机制检验 | idle_cores_probe_20260925 | ' + manifest['status'] +
                     ' | 三图、五核配置保留三个空闲核；不计为新算法全量成绩。\n')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
