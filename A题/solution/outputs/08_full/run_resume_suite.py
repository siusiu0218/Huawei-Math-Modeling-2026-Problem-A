"""Resume a user-interrupted v009 suite in a new experiment, preserving all prior evidence."""
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import argparse
import shutil
import sys
import time

import run_baseline as archive
from run_full_suite import checkpoint, run_batch
from run_portfolio import validate_freeze
from portfolio_scheduler import (read_json, write_json, digest, run_phase, validate_result,
                                 choose_candidate, solve_configuration)


def union_csv(path, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    archive.write_csv(path, [{k: r.get(k, '') for k in keys} for r in rows])


def recover_interrupted(exp, old, policy):
    started = time.perf_counter()
    key = 'case_087_n5'
    destination = exp / 'candidates' / key
    shutil.copytree(old / 'candidates' / key / 'v001', destination / 'v001')
    baseline = read_json(destination / 'v001/status.json')
    write_json(destination / 'v001/reuse_provenance.json', {'source': str(old / 'candidates' / key / 'v001'),
               'note': 'Successful candidate reused byte-for-byte; no new planning or evaluation.'})
    folder = destination / 'v008'
    folder.mkdir()
    for name in ('plan.json', 'partition.json'):
        shutil.copy2(old / 'candidates' / key / 'v008' / name, folder / name)
    plan = read_json(folder / 'plan.json')
    candidate = {'candidate': 'v008', 'status': 'pending', 'failure_phase': '', 'error': '',
                 'plan_seconds': None, 'evaluation_seconds': 0., 'wall_seconds': None,
                 'makespan': '', 'added_copy_bytes': '', 'partition_added_copy_bytes': '',
                 'spill_added_copy_bytes': '', 'scheduled_copy_bytes': '',
                 'subgraphs': len(set(plan['node_to_subgraph'].values())),
                 'used_cores': sum(bool(c) for c in plan['core_schedules']),
                 'plan_sha256': digest(folder / 'plan.json'), 'result_sha256': '',
                 'timing_scope': 'evaluation_seconds covers recovery only; original generation and interrupted evaluation are unknown'}
    command = [sys.executable, '-B', str(archive.A_ROOT / 'code/multicore_cut_evaluate_problem_1.py'),
               str(archive.A_ROOT / 'data/case_087.json'), str(folder / 'plan.json'),
               '--config', str(archive.A_ROOT / 'data/config.txt'), '-o', str(folder / 'result.json'),
               '--trace-output', str(folder / 'trace.json'), '--log-output', str(folder / 'evaluation.log')]
    write_json(folder / 'evaluation_command.json', command)
    phase = run_phase(command, policy['evaluation_timeout_seconds'], folder / 'evaluation_process.log')
    candidate.update(status=phase['status'], evaluation_seconds=phase['seconds'], error=phase['error'])
    if phase['status'] == 'ok':
        try:
            candidate.update(validate_result(read_json(folder / 'result.json'), 5))
            candidate['result_sha256'] = digest(folder / 'result.json')
        except Exception as exc:
            candidate.update(status='failed', failure_phase='result_validation', error=str(exc))
    else:
        candidate['failure_phase'] = 'evaluation'
    candidate['resume_wall_seconds'] = time.perf_counter() - started
    write_json(folder / 'status.json', candidate)
    pair = [baseline, candidate]
    winner = choose_candidate(pair)
    row = {'problem': 1, 'algorithm_version': 'v009', 'experiment': exp.name, 'case': 'case_087', 'split': 'full',
           'cores': 5, 'status': 'ok' if candidate['status'] == 'ok' else 'degraded',
           'candidate_count': 2, 'successful_candidates': sum(c['status'] == 'ok' for c in pair),
           'selected_candidate': winner['candidate'], 'makespan': winner['makespan'],
           'added_copy_bytes': winner['added_copy_bytes'], 'plan_seconds': None,
           'evaluation_seconds': None, 'candidate_wall_seconds': None, 'total_wall_seconds': None,
           'selected_plan_sha256': winner['plan_sha256'], 'selected_result_sha256': winner['result_sha256'],
           'recorded_plan_seconds': baseline['plan_seconds'],
           'recorded_evaluation_seconds': baseline['evaluation_seconds'] + candidate['evaluation_seconds'],
           'recorded_total_wall_seconds': baseline['wall_seconds'] + candidate['resume_wall_seconds'],
           'timing_complete': False, 'operational_recovery': True}
    for c in pair:
        row[f"{c['candidate']}_status"] = c['status']
        row[f"{c['candidate']}_makespan"] = c['makespan']
    for filename, target in [('plan.json', exp / 'plans' / f'{key}.json'), ('result.json', exp / 'metrics' / f'{key}_result.json')]:
        shutil.copy2(destination / winner['candidate'] / filename, target)
        assert digest(target) == winner['plan_sha256' if filename == 'plan.json' else 'result_sha256']
    write_json(exp / 'metrics' / f'{key}_status.json', row)
    return row, pair


def recovery_batch(full, recovery):
    archive.VERSION = 'v009'
    exp, manifest = archive.prepare(SimpleNamespace(experiment=recovery['experiment'], mode='operational_recovery'))
    started = time.perf_counter()
    manifest.update(suite_freeze_sha256=recovery['full_freeze_sha256'], recovery_freeze=recovery,
                    planned_configurations=17, policy=full['policy'], cores=[2, 3, 4, 5])
    write_json(exp / 'selection.json', recovery)
    write_json(exp / 'manifest.json', manifest)
    rows, candidates = [], []
    try:
        for item in recovery['remaining_configurations']:
            if item == {'case': 'case_087', 'cores': 5}:
                row, pair = recover_interrupted(exp, archive.SOLUTION / recovery['partial_experiment'], full['policy'])
            else:
                row, pair = solve_configuration(exp, item['case'], 'full', item['cores'], full['policy'], exp / 'source/src/portfolio_scheduler.py')
                row.update(recorded_plan_seconds=row['plan_seconds'], recorded_evaluation_seconds=row['evaluation_seconds'],
                           recorded_total_wall_seconds=row['total_wall_seconds'], timing_complete=True, operational_recovery=False)
                write_json(exp / 'metrics' / f"{item['case']}_n{item['cores']}_status.json", row)
            rows.append(row)
            candidates.extend({'case': item['case'], 'cores': item['cores'], 'experiment': exp.name, **c} for c in pair)
            union_csv(exp / 'metrics/summary.csv', rows)
            union_csv(exp / 'metrics/candidates.csv', candidates)
            checkpoint(exp / 'progress.json', {'utc': archive.stamp(), 'completed': len(rows), 'planned': 17,
                       'statuses': dict(Counter(r['status'] for r in rows)), 'elapsed_seconds': time.perf_counter() - started})
            print(f"RECOVERY {len(rows)}/17 {item['case']} n{item['cores']} {row['status']} T={row['makespan']}", flush=True)
        manifest['status'] = 'completed' if all(r['status'] == 'ok' for r in rows) else 'completed_with_failures'
    except BaseException as exc:
        manifest.update(status='interrupted', error=str(exc))
        raise
    finally:
        manifest.update(ended_utc=archive.stamp(), elapsed_seconds=time.perf_counter() - started,
                        completed_configurations=len(rows), configuration_status_counts=dict(Counter(r['status'] for r in rows)),
                        candidate_status_counts=dict(Counter(r['status'] for r in candidates)),
                        protected_inputs_unchanged=archive.protected_hashes() == full['protected_hashes'])
        manifest['artifact_hashes'] = {str(p.relative_to(exp)): digest(p) for name in ('candidates', 'plans', 'metrics', 'logs')
                                     for p in sorted((exp / name).rglob('*')) if p.is_file()}
        write_json(exp / 'manifest.json', manifest)
        archive.register(exp, 'operational_recovery', manifest['status'])
    return exp, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recovery-freeze', required=True, type=Path)
    args = parser.parse_args()
    recovery = read_json(args.recovery_freeze)
    full_path = archive.SOLUTION / recovery['full_freeze']
    assert digest(full_path) == recovery['full_freeze_sha256']
    assert digest(Path(__file__)) == recovery['driver_sha256']
    full = read_json(full_path)
    validate_freeze(full, archive.SOURCE, 'full')
    for relative, expected in recovery['preexisting_hashes'].items():
        assert digest(archive.SOLUTION / relative) == expected, relative
    partial = archive.SOLUTION / recovery['partial_experiment']
    for relative, expected in read_json(partial / 'manifest.json')['artifact_hashes_at_pause'].items():
        assert digest(partial / relative) == expected, relative
    path = archive.SOLUTION / recovery['progress_path']
    if path.exists():
        raise FileExistsError('Recovery already started; inspect saved state before another continuation')
    progress = {'status': 'running', 'started_utc': archive.stamp(), 'recovery_freeze_sha256': digest(args.recovery_freeze), 'batches': []}
    checkpoint(path, progress)
    exp, manifest = recovery_batch(full, recovery)
    assert manifest['protected_inputs_unchanged']
    progress['batches'].append({'experiment': exp.name, 'version': 'v009', 'manifest_sha256': digest(exp / 'manifest.json')})
    checkpoint(path, progress)
    full['freeze_path'] = str(full_path)
    for batch in full['single_batches']:
        progress['current_batch'] = batch['experiment']
        checkpoint(path, progress)
        exp, manifest = run_batch(full, batch, single=True)
        assert manifest['protected_inputs_unchanged']
        progress['batches'].append({'experiment': exp.name, 'version': 'v001', 'manifest_sha256': digest(exp / 'manifest.json')})
        checkpoint(path, progress)
    progress.update(status='all_batches_finished', ended_utc=archive.stamp(), current_batch=None)
    checkpoint(path, progress)


if __name__ == '__main__':
    main()
