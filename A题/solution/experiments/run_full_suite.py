"""Sequential full-coverage orchestration around the unchanged frozen v009 solver."""
import argparse
from collections import Counter
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

import run_baseline as archive
from run_portfolio import validate_freeze
from portfolio_scheduler import solve_configuration, read_json, write_json, digest
from result_paths import experiment_path, result_path


def checkpoint(path, data):
    temporary = path.with_suffix('.tmp')
    write_json(temporary, data)
    temporary.replace(path)


def run_batch(freeze, batch, single=False):
    archive.VERSION = 'v001' if single else 'v009'
    args = SimpleNamespace(experiment=batch['experiment'], mode='full_single_reference' if single else 'full_portfolio',
                           timeout=freeze['single_timeout_seconds'] if single else 180,
                           blocks_per_core=4, workers=1, algorithm='baseline', cores=[1] if single else [2, 3, 4, 5])
    exp, manifest = archive.prepare(args)
    started = time.perf_counter()
    rows, candidates = [], []
    manifest.update(suite_freeze_sha256=digest(Path(freeze['freeze_path'])),
                    policy=freeze['policy'], cases=batch['cases'], cores=args.cores,
                    scope='full coverage batch, not an independent holdout',
                    planned_configurations=len(batch['cases']) * len(args.cores))
    write_json(exp / 'selection.json', freeze)
    write_json(exp / 'manifest.json', manifest)
    try:
        for case in batch['cases']:
            for cores in args.cores:
                if single:
                    row = archive.evaluate_one(exp, {'case': case, 'split': 'full'}, cores, args, manifest['wait_config'])
                else:
                    row, outcomes = solve_configuration(exp, case, 'full', cores, freeze['policy'], exp / 'source/src/portfolio_scheduler.py')
                    candidates.extend({'problem': 1, 'algorithm_version': 'v009', 'experiment': exp.name,
                                       'case': case, 'split': 'full', 'cores': cores, **r} for r in outcomes)
                    archive.write_csv(exp / 'metrics/candidates.csv', candidates)
                rows.append(row)
                archive.write_csv(exp / 'metrics/summary.csv', rows)
                checkpoint(exp / 'progress.json', {'utc': archive.stamp(), 'completed': len(rows),
                           'planned': manifest['planned_configurations'], 'last_case': case, 'last_cores': cores,
                           'statuses': dict(Counter(r['status'] for r in rows)),
                           'elapsed_seconds': time.perf_counter() - started})
                print(f"{exp.name} {len(rows)}/{manifest['planned_configurations']}: {case} n{cores} {row['status']} T={row['makespan']}", flush=True)
        manifest['status'] = 'completed' if all(r['status'] == 'ok' for r in rows) else 'completed_with_failures'
    except BaseException as exc:
        manifest.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        manifest.update(ended_utc=archive.stamp(), elapsed_seconds=time.perf_counter() - started,
                        completed_configurations=len(rows), configuration_status_counts=dict(Counter(r['status'] for r in rows)),
                        candidate_status_counts=dict(Counter(r['status'] for r in candidates)),
                        protected_inputs_unchanged=archive.protected_hashes() == manifest['protected_hashes_before'])
        if not manifest['protected_inputs_unchanged']:
            manifest['status'] = 'invalid_inputs_changed'
        manifest['artifact_hashes'] = {str(p.relative_to(exp)): digest(p)
                for folder in ('candidates', 'plans', 'metrics', 'logs') for p in sorted((exp / folder).rglob('*')) if p.is_file()}
        write_json(exp / 'manifest.json', manifest)
        archive.register(exp, args.mode, manifest['status'])
    return exp, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', type=Path, required=True)
    args = parser.parse_args()
    freeze_path = args.freeze.resolve()
    freeze = read_json(freeze_path)
    first_run = freeze['multicore_batches'][0]['experiment']
    validate_freeze(freeze, experiment_path('v009', first_run) / 'source', 'full')
    previous_freeze = archive.SOLUTION / 'experiments/v009_selection.json'
    if digest(previous_freeze) != freeze['previous_freeze_sha256']:
        raise ValueError('original v009 freeze changed')
    progress_path = result_path(freeze['progress_path'])
    previous = read_json(progress_path) if progress_path.exists() else {'batches': []}
    progress = {'started_utc': previous.get('started_utc', archive.stamp()), 'freeze_sha256': digest(freeze_path), 'status': 'running', 'batches': previous['batches']}
    if previous.get('freeze_sha256', digest(freeze_path)) != digest(freeze_path):
        raise ValueError('progress belongs to another freeze')
    freeze['freeze_path'] = str(freeze_path)
    done = {b['experiment'] for b in progress['batches']}
    for kind in ('multicore_batches', 'single_batches'):
        for batch in freeze[kind]:
            version = 'v001' if kind == 'single_batches' else 'v009'
            exp_path = experiment_path(version, batch['experiment'])
            if batch['experiment'] in done:
                manifest = read_json(exp_path / 'manifest.json')
                if manifest['status'] not in ('completed', 'completed_with_failures') or not manifest['protected_inputs_unchanged']:
                    raise ValueError('previous batch is not complete and valid')
                continue
            if exp_path.exists():
                raise FileExistsError(f'Incomplete/unregistered batch retained; use a separately frozen recovery run: {exp_path}')
            progress.update(current_batch=batch['experiment'], current_kind=kind, updated_utc=archive.stamp())
            checkpoint(progress_path, progress)
            exp, manifest = run_batch(freeze, batch, single=kind == 'single_batches')
            progress['batches'].append({'experiment': exp.name, 'version': version, 'status': manifest['status'],
                                        'manifest_sha256': digest(exp / 'manifest.json')})
            checkpoint(progress_path, progress)
            if not manifest['protected_inputs_unchanged']:
                raise ValueError('protected input changed; stopping suite')
    progress.update(status='all_batches_finished', ended_utc=archive.stamp(), current_batch=None)
    checkpoint(progress_path, progress)


if __name__ == '__main__':
    main()
