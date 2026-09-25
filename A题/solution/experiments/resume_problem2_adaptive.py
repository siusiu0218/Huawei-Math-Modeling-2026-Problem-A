"""Resume the verified pause checkpoint without repeating successful work."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from run_problem2 import save, run_command

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/09_problem2/raw/problem_2/v009'
OLD = ['exp102_20260925_adaptive_full_a', 'exp103_20260925_adaptive_full_b']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_pause():
    frozen = json.loads((ROOT / 'experiments/problem2_v009_selection.json').read_text(encoding='utf-8'))
    for rel, digest in frozen['source_hashes'].items():
        assert sha(ROOT / rel) == digest, rel
    complete = set()
    for name in OLD:
        folder = BASE / name
        m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        assert m['status'] == 'paused_by_user'
        for rel, digest in m['protected_hashes_before'].items():
            assert sha(ROOT.parent / rel) == digest, rel
        for rel, digest in m['output_hashes_at_pause'].items():
            assert sha(folder / rel) == digest, rel
        for rel, digest in frozen['source_hashes'].items():
            assert sha(folder / 'source' / rel) == digest, rel
        for row in m['items']:
            if row['status'] == 'success':
                complete.add((row['case'], row['cores']))
    checkpoint = json.loads((BASE / 'pause_checkpoint_20260925.json').read_text(encoding='utf-8'))
    remaining = checkpoint['remaining']
    keys = {(r['case'], r['cores']) for r in remaining}
    assert len(complete) == 100 and len(keys) == len(remaining) == 300
    assert not (complete & keys)
    assert complete | keys == {(f'case_{i:03}', n) for i in range(1, 101) for n in range(2, 6)}
    return remaining


def run_batch(name, entries, generation_timeout, workers):
    folder = BASE / name
    folder.mkdir(exist_ok=False)
    for sub in ('plans', 'metrics', 'logs', 'source'):
        (folder / sub).mkdir()
    for sub in ('src', 'tests'):
        shutil.copytree(ROOT / sub, folder / 'source' / sub, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT.parent / 'code', folder / 'source/code', ignore=shutil.ignore_patterns('__pycache__'))
    for p in (Path(__file__), ROOT / 'experiments/run_problem2.py', ROOT.parent / 'data/config.txt'):
        shutil.copy2(p, folder / 'source' / p.name)
    protected = sorted((ROOT.parent / 'code').glob('*.py')) + [ROOT.parent / 'data/config.txt']
    protected += [ROOT.parent / 'data' / f'{case}.json' for case in sorted({r['case'] for r in entries})]
    m = {'problem': 2, 'algorithm_version': 'v009', 'experiment': name, 'status': 'running',
         'started_utc': datetime.now(timezone.utc).isoformat(), 'parameters': {
             'generation_timeout': generation_timeout, 'evaluation_timeout': 180, 'max_workers': workers},
         'invocation': [sys.executable, '-B', *sys.argv],
         'protected_hashes_before': {str(p.relative_to(ROOT.parent)): sha(p) for p in protected},
         'source_hashes': {str(p.relative_to(folder / 'source')): sha(p) for p in (folder / 'source').rglob('*') if p.is_file()},
         'items': []}
    lock = threading.Lock()
    def checkpoint():
        save(folder / 'manifest.json', m)
    def register(status):
        with (ROOT / 'experiments/INDEX.md').open('a', encoding='utf-8') as f:
            f.write(f'\n- 问题 2 v009 | {name} | {status} | [清单](../{folder.relative_to(ROOT).as_posix()}/manifest.json)\n')
    checkpoint(); register('running')
    def execute(entry):
        c, n = entry['case'], entry['cores']; key = f'{c}_n{n}'
        row = {'problem': 2, 'algorithm_version': 'v009', 'experiment': name, 'case': c, 'cores': n, 'status': 'running'}
        with lock:
            m['items'].append(row); checkpoint()
        command = [sys.executable, '-B', str(ROOT / 'experiments/run_problem2.py'), '--algorithm', 'adaptive',
                   '--input', str(ROOT.parent / 'data' / f'{c}.json'), '--config', str(ROOT.parent / 'data/config.txt'),
                   '--n', str(n), '--plan', str(folder / 'plans' / f'{key}.json'),
                   '--result', str(folder / 'metrics' / f'{key}.json')]
        if entry.get('existing_plan'):
            source = ROOT / entry['existing_plan']
            assert sha(source) == entry['plan_sha256']
            shutil.copy2(source, folder / 'plans' / source.name)
            shutil.copy2(ROOT / entry['selection'], folder / 'plans' / f'{key}.selection.json')
            row['generate'] = {'status': 'success', 'seconds': 0, 'returncode': 0,
                               'reused_from': entry['existing_plan'], 'cost_note': 'Original generation cost remains in paused manifest.'}
        else:
            row['generate'] = run_command(command + ['--worker', 'generate'], folder / 'logs' / f'{key}_generate.log', generation_timeout)
        with lock: checkpoint()
        if row['generate']['status'] != 'success':
            row['status'] = 'generate_' + row['generate']['status']
        else:
            row['evaluate'] = run_command(command + ['--worker', 'evaluate'], folder / 'logs' / f'{key}_evaluate.log', 180)
            if row['evaluate']['status'] != 'success':
                row['status'] = 'evaluate_' + row['evaluate']['status']
            else:
                result = json.loads((folder / 'metrics' / f'{key}.json').read_text(encoding='utf-8'))
                row.update(status='success', makespan=result['makespan'], data_movement_bytes=result['data_movement_bytes'])
        with lock:
            checkpoint()
            print(name, key, row['status'], row.get('makespan', ''), flush=True)
        return row
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            rows = list(executor.map(execute, entries))
        m['status'] = 'completed' if all(r['status'] == 'success' for r in rows) else 'partial'
    except BaseException:
        m['status'] = 'interrupted'
        raise
    finally:
        m['protected_hashes_after'] = {str(p.relative_to(ROOT.parent)): sha(p) for p in protected}
        m['protected_unchanged'] = m['protected_hashes_before'] == m['protected_hashes_after']
        m['finished_utc'] = datetime.now(timezone.utc).isoformat()
        m['output_hashes'] = {str(p.relative_to(folder)): sha(p) for sub in ('plans', 'metrics', 'logs') for p in (folder / sub).glob('*') if p.is_file()}
        checkpoint(); register(m['status'])
    return rows


def main():
    remaining = verify_pause()
    names = ['exp104_20260925_adaptive_resume', 'exp105_20260925_adaptive_timeouts']
    record_path = ROOT / 'experiments/problem2_v009_recovery.json'
    assert not record_path.exists() and all(not (BASE / n).exists() for n in names)
    record = {'status': 'running', 'experiments': [names[0]], 'paused_successes_preserved': 100,
              'resume_configurations': 300, 'generation_timeout_initial': 60,
              'generation_timeout_recovery': 300, 'evaluation_timeout': 180,
              'interrupted_evaluation_seconds': None, 'cost_is_lower_bound': True}
    save(record_path, record)
    regular = sorted([r for r in remaining if r['reason'] != 'generate_timeout'], key=lambda r: (not bool(r.get('existing_plan')), r['case'], r['cores']))
    print('Verified 100 old successes; resuming', len(regular), 'and retaining three initial timeouts.', flush=True)
    rows = run_batch(names[0], regular, 60, 2)
    retry = [r for r in remaining if r['reason'] == 'generate_timeout']
    retry += [{'case': r['case'], 'cores': r['cores']} for r in rows if r['status'] == 'generate_timeout']
    if retry:
        record['experiments'].append(names[1]); save(record_path, record)
        retries = run_batch(names[1], retry, 300, 1)
    else:
        retries = []
    record['status'] = 'completed' if all(r['status'] in ('success', 'generate_timeout') for r in rows) and all(r['status'] == 'success' for r in retries) else 'partial'
    save(record_path, record)
    return int(record['status'] != 'completed')


if __name__ == '__main__':
    raise SystemExit(main())
