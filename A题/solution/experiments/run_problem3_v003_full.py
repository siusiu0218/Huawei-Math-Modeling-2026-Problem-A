"""Resumable full v003 experiment. Frozen algorithm, two candidates, original evaluators."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import time

from run_problem2 import save
from run_problem3_pair import sha, fingerprint
from run_problem3_bounded import base_path, read, S
from result_paths import result_path
from process_runner import run_command

MODES = ('no_l2', 'cache')
OLD = S/'experiments/problem3_v003_selection.json'


def canonical(path):
    import hashlib
    return hashlib.sha256(json.dumps(read(path), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def source_paths():
    frozen = read(OLD)
    for p, digest in frozen['source_hashes'].items():
        if sha(p) != digest:
            raise ValueError('Frozen v003 source changed: '+p)
    return [Path(p) for p in frozen['source_hashes']] + [OLD, Path(__file__),
        S/'experiments/process_runner.py', S/'experiments/report_problem3_v003_full.py',
        S/'tests/test_problem3_full_runner.py', S/'tests/test_problem3_checkpoint_integrity.py']


def reuse_index():
    """Accept only matching graph/plan/config/evaluator provenance; hash results on use."""
    index = {}
    official = fingerprint(sorted((S.parent/'code').glob('*.py')) + [S.parent/'data/config.txt'])
    oldroots = [(S/'outputs/10_problem3/raw/problem_3/v001/exp115_20260926_full', 'baseline')]
    oldroots += [(S/'outputs/10_problem3/raw/problem_3/v003'/name, 'v003') for name in
                 ['exp116_20260926_bounded_development', 'exp117_20260926_bounded_validation']]
    for root, kind in oldroots:
        manifest_path = root/'manifest.json'; m = read(manifest_path)
        if kind == 'v003':
            selection = read(root/'selection.json')
            assert sha(root/'selection.json') == m['frozen_selection_sha256']
            provenance = selection['source_hashes'] | selection['input_hashes']
        else:
            provenance = m['hashes_before']
        assert all(provenance.get(p) == digest for p, digest in official.items())
        for item in m['items']:
            case, cores = item['case'], item['cores']
            graph = S.parent/'data'/f'{case}.json'
            assert provenance[str(graph.resolve())] == sha(graph)
            if kind == 'v003':
                candidates = [(r['plan'], r['plan_sha256'], r['evaluations']) for name, r in item['candidates'].items() if name in ('baseline', 'width1')]
            else:
                candidates = [(f'plans/{case}_n{cores}.json', item['plan_sha256'],
                    {mode: next((r for r in reversed(item['attempts']) if r['mode'] == mode), {}) for mode in MODES})]
            for rel, digest, evaluations in candidates:
                plan = root/rel
                assert sha(plan) == digest
                signature = canonical(plan)
                for mode, ev in evaluations.items():
                    if ev.get('status') != 'success':
                        continue
                    result = root/ev['result']; result_hash = ev.get('sha256', ev.get('result_sha256'))
                    assert result_hash
                    index[f'{case}:{cores}:{signature}:{mode}'] = {
                        'source': str(result), 'sha256': result_hash, 'source_manifest': str(manifest_path),
                        'source_manifest_sha256': sha(manifest_path), 'source_plan': str(plan),
                        'source_plan_sha256': digest, 'original_seconds': ev.get('seconds'),
                        'note': 'hash-verified reuse; upstream search/evaluation cost is not zero'}
    return index


@contextmanager
def run_lock(out):
    with (out/'.run.lock').open('a+b') as handle:
        handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def valid_success(record, out):
    if record.get('status') != 'success':
        return False
    if sha(out/record['file']) != record['sha256']:
        raise ValueError('Successful artifact changed: '+record['file'])
    return True


class CheckpointStop(Exception):
    pass


def run(args):
    out = result_path(Path('problem_3')/'v003'/args.experiment)
    cases = args.cases or [f'case_{i:03}' for i in range(1, 101)]
    cores = args.cores or list(range(1, 6))
    assert len(set(cases)) == len(cases) and all(c in {f'case_{i:03}' for i in range(1, 101)} for c in cases)
    assert len(set(cores)) == len(cores) and all(n in range(1, 6) for n in cores)
    paths = source_paths() + [S.parent/'data'/f'{c}.json' for c in cases] + [base_path(c, n) for c in cases for n in cores]
    hashes = fingerprint(paths)
    if not args.resume:
        out.mkdir(parents=True, exist_ok=False)
    elif not out.is_dir():
        raise ValueError('No archive to resume')
    with run_lock(out):
        if args.resume:
            m = read(out/'manifest.json')
            assert m['hashes_before'] == hashes and m['cases'] == cases and m['cores'] == cores
            assert m['reuse_enabled'] == (not args.no_reuse)
            for rel, digest in m['archive_hashes'].items():
                assert sha(out/rel) == digest, rel
            for item in m['items']:
                for candidate in item['candidates'].values():
                    for attempts in [candidate['generation'], *candidate['evaluations'].values()]:
                        for record in attempts:
                            if record['status'] == 'success':
                                valid_success(record, out)
                            elif record['status'] == 'running':
                                record['status'] = 'interrupted'
        else:
            for folder in ['source', 'inputs', 'plans', 'metrics', 'logs', 'selected_plans']:
                (out/folder).mkdir()
            for source in source_paths():
                target = out/'source'/source.relative_to(S.parent)
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
            shutil.copy2(S.parent/'data/config.txt', out/'inputs/config.txt')
            for case in cases:
                shutil.copy2(S.parent/'data'/f'{case}.json', out/'inputs'/f'{case}.json')
            index = {} if args.no_reuse else reuse_index()
            save(out/'reuse_index.json', index)
            archives = [p for folder in ['source', 'inputs'] for p in (out/folder).rglob('*') if p.is_file()] + [out/'reuse_index.json']
            m = {'problem': 3, 'version': 'v003', 'experiment': args.experiment,
                'scope': 'full' if len(cases) == 100 and cores == list(range(1, 6)) else 'preflight',
                'cases': cases, 'cores': cores, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'hashes_before': hashes, 'archive_hashes': {str(p.relative_to(out)): sha(p) for p in archives},
                'reuse_enabled': not args.no_reuse, 'algorithm_selection_sha256': sha(OLD),
                'policy': 'baseline plus width1; Cache makespan minimum; ties baseline; unchanged original evaluator',
                'budget': {'generation_seconds': 30, 'evaluation_seconds': 180, 'automatic_retries': 0},
                'items': [{'case': c, 'cores': n, 'baseline_source': str(base_path(c, n)),
                    'candidates': {name: {'generation': [], 'evaluations': {mode: [] for mode in MODES}}
                                   for name in ['baseline', 'width1']}} for c in cases for n in cores],
                'invocations': [], 'status': 'prepared'}
            save(out/'manifest.json', m)
        index = read(out/'reuse_index.json')
        invocation = {'started_utc': datetime.now(timezone.utc).isoformat(), 'command': [sys.executable, *sys.argv], 'actions': 0}
        m['invocations'].append(invocation); m['status'] = 'running'
        save(out/'manifest.json', m); start = time.perf_counter()

        def action(attempts, file, command=None, timeout=None, copy=None, origin=None):
            # Failure is retained and not retried by --resume. Interrupted work
            # gets a new attempt/file; a completed artifact is never overwritten.
            if attempts and attempts[-1]['status'] in ('success', 'failed', 'timeout', 'invalid_result'):
                return attempts[-1]
            record = {'status': 'running', 'file': str(file.relative_to(out)), 'seconds': 0,
                      'kind': 'reuse' if origin else 'copy' if copy else 'execute'}
            if origin:
                record['origin'] = origin
            attempts.append(record); save(out/'manifest.json', m)
            try:
                if copy:
                    if origin:
                        assert sha(copy) == origin['sha256']
                        assert sha(origin['source_manifest']) == origin['source_manifest_sha256']
                        assert sha(origin['source_plan']) == origin['source_plan_sha256']
                    shutil.copy2(copy, file); record['status'] = 'success'
                else:
                    record.update(run_command(command, out/'logs'/(file.stem+'.txt'), timeout))
                if record['status'] == 'success':
                    try:
                        value = read(file)
                        if 'metrics' in file.parts:
                            assert type(value['makespan']) in (int, float) and value['makespan'] > 0
                        record['sha256'] = sha(file)
                    except (OSError, ValueError, KeyError, AssertionError):
                        record['status'] = 'invalid_result'
            except BaseException:
                record['status'] = 'interrupted'; save(out/'manifest.json', m); raise
            invocation['actions'] += 1; save(out/'manifest.json', m)
            if args.max_actions and invocation['actions'] >= args.max_actions:
                raise CheckpointStop()
            return record

        try:
            for item in m['items']:
                stem = f"{item['case']}_n{item['cores']}"
                for name, candidate in item['candidates'].items():
                    generations = candidate['generation']
                    number = len(generations)+1
                    plan = out/'plans'/f'{stem}_{name}_attempt{number}.json'
                    if name == 'baseline':
                        gen = action(generations, plan, copy=Path(item['baseline_source']))
                    else:
                        base = item['candidates']['baseline']['generation'][-1]
                        if base['status'] != 'success':
                            continue
                        command = [sys.executable, '-B', str(S/'experiments/run_problem3_bounded.py'), '--worker',
                            '--graph', str(out/'inputs'/f"{item['case']}.json"), '--base', str(out/base['file']), '--plan', str(plan), '--width', '1']
                        gen = action(generations, plan, command, 30)
                    if gen['status'] != 'success':
                        continue
                    plan = out/gen['file']; signature = canonical(plan)
                    for mode in MODES:
                        attempts = candidate['evaluations'][mode]; number = len(attempts)+1
                        result = out/'metrics'/f'{stem}_{name}_{mode}_attempt{number}.json'
                        origin = index.get(f"{item['case']}:{item['cores']}:{signature}:{mode}")
                        # Same-plan deduplication inside this run is also traceable.
                        if name == 'width1':
                            baseline = item['candidates']['baseline']; old = baseline['evaluations'][mode]
                            if old and old[-1]['status'] == 'success' and canonical(out/baseline['generation'][-1]['file']) == signature:
                                origin = {'source': str(out/old[-1]['file']), 'sha256': old[-1]['sha256'],
                                    'source_plan': str(out/baseline['generation'][-1]['file']), 'source_plan_sha256': baseline['generation'][-1]['sha256'],
                                    'note': 'identical baseline plan; internal deduplication'}
                        if origin and 'source_manifest' not in origin:
                            assert sha(origin['source']) == origin['sha256']
                            rec = action(attempts, result, copy=Path(origin['source']))
                            rec['deduplicated_from'] = origin
                        elif origin:
                            action(attempts, result, copy=Path(origin['source']), origin=origin)
                        else:
                            command = [sys.executable, '-B', str(S/'experiments/run_problem3_pair.py'), '--worker', mode,
                                '--graph', str(out/'inputs'/f"{item['case']}.json"), '--plan', str(plan),
                                '--config', str(out/'inputs/config.txt'), '--result', str(result)]
                            action(attempts, result, command, 180)
                        save(out/'manifest.json', m)
                print(stem, 'checkpointed', flush=True)
            m['status'] = 'evaluated'
        except (CheckpointStop, KeyboardInterrupt):
            m['status'] = 'paused'
        except BaseException:
            m['status'] = 'interrupted'; raise
        finally:
            invocation['wall_seconds'] = time.perf_counter()-start
            m['hashes_after'] = fingerprint(paths)
            assert m['hashes_after'] == hashes
            save(out/'manifest.json', m)
        print(json.dumps({'status': m['status'], 'out': str(out), 'actions': invocation['actions']}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--experiment', required=True); p.add_argument('--resume', action='store_true')
    p.add_argument('--cases', nargs='+'); p.add_argument('--cores', nargs='+', type=int)
    p.add_argument('--no-reuse', action='store_true'); p.add_argument('--max-actions', type=int)
    args = p.parse_args()
    if Path(args.experiment).name != args.experiment:
        p.error('plain experiment name required')
    run(args)
