"""Bounded Q1 diagnosis + six-case local-search pilot; never edits old results."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import zipfile

SOLUTION = Path(__file__).resolve().parents[1]
A_ROOT = SOLUTION.parent
sys.path.insert(0, str(SOLUTION / 'src'))
from scene_a_critical_local import diagnose, candidates, VERSION
from portfolio_scheduler import validate_result
from process_runner import run_command
from result_paths import experiment_path

EXPERIMENT = 'exp131_20260926_critical_local_pilot'
ROOT = experiment_path(VERSION, EXPERIMENT)


def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, value):
    tmp = p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    tmp.replace(p)


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def prepare():
    ROOT.mkdir(parents=True, exist_ok=False)
    for name in ('source','baseline','diagnostics','runs','selected'): (ROOT/name).mkdir()
    rows = list(csv.DictReader((SOLUTION/'outputs/08_full/multicore_comparison.csv').open(encoding='utf-8-sig')))
    low = sorted([r for r in rows if int(r['cores']) == 5 and float(r['speedup']) < 2], key=lambda r:r['case'])
    assert len(low) == 23
    protected = list((A_ROOT/'code').glob('*.py')) + [A_ROOT/'data/config.txt'] + [A_ROOT/f"data/{r['case']}.json" for r in low]
    hashes = {str(p.relative_to(A_ROOT)): sha(p) for p in protected}
    for folder in ('src','experiments'):
        (ROOT/'source'/folder).mkdir()
    for name in ('scene_a_critical_local.py','graph_analysis.py','portfolio_scheduler.py'):
        shutil.copy2(SOLUTION/'src'/name,ROOT/'source/src'/name)
    for name in ('probe_problem1_critical_local.py','process_runner.py','result_paths.py'):
        shutil.copy2(SOLUTION/'experiments'/name,ROOT/'source/experiments'/name)
    diagnostic_rows, origins, line_ending_equivalence = [], [], set()
    archive = SOLUTION/'outputs/08_full/原始运行记录.zip'
    with zipfile.ZipFile(archive) as z:
        for row in low:
            case = row['case']; base = f"problem_1/v009/{row['experiment']}/"
            old_manifest = json.loads(z.read(base+'manifest.json'))
            relevant = [p for p in protected if p.parent.name == 'code' or p.name in ('config.txt',case+'.json')]
            for p in relevant:
                key = str(p.relative_to(A_ROOT))
                expected = old_manifest['protected_hashes_before'][key]
                if sha(p) != expected:
                    # Git checkout converted the archived CRLF sources to LF.
                    # Verify the exact old hash after CRLF reconstruction; no
                    # executable content normalization or changes are allowed.
                    crlf = p.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
                    if p.suffix != '.py' or hashlib.sha256(crlf).hexdigest() != expected:
                        raise ValueError('protected input differs from original evaluation: '+key)
                    line_ending_equivalence.add(key)
            for suffix,destination,expected in [('plans/'+case+'_n5.json',case+'_plan.json',row['selected_plan_sha256']),
                                               ('metrics/'+case+'_n5_result.json',case+'_result.json',row['selected_result_sha256'])]:
                blob = z.read(base+suffix)
                if hashlib.sha256(blob).hexdigest() != expected: raise ValueError('archive hash mismatch')
                (ROOT/'baseline'/destination).write_bytes(blob)
                origins.append({'case':case,'member':base+suffix,'sha256':expected})
            result = read(ROOT/'baseline'/f'{case}_result.json')
            d = diagnose(result); save(ROOT/'diagnostics'/f'{case}.json',d)
            breakdown = d['chain_breakdown']
            diagnostic_rows.append({'problem':1,'algorithm_version':VERSION,'experiment':EXPERIMENT,'case':case,'cores':5,
                'single_makespan':int(row['single_makespan']), 'baseline_makespan':result['makespan'], 'speedup':float(row['speedup']),
                'tasks':len(d['tasks']),'chain_tasks':len(d['chain']), **breakdown,
                'task_busy_fraction':d['task_busy_fraction'],'largest_chain_task_fraction':d['largest_chain_task_fraction'],
                'added_copy_bytes':result['data_movement_bytes']['added_copy_bytes'],
                'partition_added_copy_bytes':result['data_movement_bytes']['partition_added_copy_bytes'],
                'spill_added_copy_bytes':result['data_movement_bytes']['spill_added_copy_bytes']})
    write_csv(ROOT/'diagnosis.csv',diagnostic_rows)
    # Freeze representative selection before any new candidate evaluation.
    selected = []
    for metric in ('cross_wait','transfer_only','compute_only'):
        remaining = [r for r in diagnostic_rows if r['case'] not in {s['case'] for s in selected}]
        ranked = sorted(remaining,key=lambda r:(-r[metric]/r['baseline_makespan'],r['case']))
        for row in ranked[:2]: selected.append({'case':row['case'],'selection_metric':metric})
    manifest = {'problem':1,'algorithm_version':VERSION,'experiment':EXPERIMENT,'status':'prepared',
        'diagnostic_cases':[r['case'] for r in low], 'selected':selected,'cores':[5], 'random_seed':None,
        'policy':'two critical-edge merges, longest critical-task split into 2/4 depth bands and components, two least-busy-core relocations; baseline retained',
        'generation_timeout_seconds':30,'evaluation_timeout_seconds':180,'retries':0,'candidate_limit_per_case':6,
        'scope':'outcome-selected exploratory pilot, not unseen validation or full-suite result',
        'protected_hashes':hashes,'baseline_origins':origins,'archive':str(archive),
        'archived_source_crlf_equivalent':sorted(line_ending_equivalence),
        'frozen_sources':{str(p.relative_to(SOLUTION)):sha(p) for p in [SOLUTION/'src/scene_a_critical_local.py',Path(__file__),SOLUTION/'experiments/process_runner.py']},
        'command':[sys.executable,'-B',str(Path(__file__)),'--run'],
        'diagnostic_boundary':'observed task duration chain; occupancy overlaps separated; transfer pipes not exclusively DDR; no attribution of all contention to DDR'}
    save(ROOT/'manifest.json',manifest)
    print(json.dumps({'root':str(ROOT),'selected':selected,'diagnosis':diagnostic_rows},ensure_ascii=False),flush=True)


def generate(case):
    destination = ROOT/'runs'/case
    started = time.perf_counter()
    rows = []
    for name,plan,edit,error in candidates(read(A_ROOT/f'data/{case}.json'),read(ROOT/'baseline'/f'{case}_plan.json'),read(ROOT/'baseline'/f'{case}_result.json')):
        folder = destination/name; folder.mkdir()
        record = {'candidate':name,'edit':edit,'status':'invalid' if error else 'generated','error':error}
        if plan: save(folder/'plan.json',plan)
        save(folder/'generation.json',record); rows.append(record)
    save(destination/'generation.json',{'seconds':time.perf_counter()-started,'candidates':rows})


def run():
    manifest = read(ROOT/'manifest.json')
    if manifest['status'] != 'prepared': raise ValueError('no automatic restart/overwrite; use a new experiment')
    for relative,digest in manifest['protected_hashes'].items():
        if sha(A_ROOT/relative) != digest: raise ValueError('protected input changed: '+relative)
    for relative,digest in manifest['frozen_sources'].items():
        if sha(SOLUTION/relative) != digest: raise ValueError('source changed: '+relative)
    manifest['status'] = 'running'; save(ROOT/'manifest.json',manifest)
    started = time.perf_counter(); rows = []; selections = []
    low = {r['case']:r for r in csv.DictReader((ROOT/'diagnosis.csv').open(encoding='utf-8-sig'))}
    def evaluate(case,name,plan,folder):
        command = [sys.executable,'-B',str(A_ROOT/'code/multicore_cut_evaluate_problem_1.py'),str(A_ROOT/f'data/{case}.json'),str(plan),
            '--config',str(A_ROOT/'data/config.txt'),'-o',str(folder/'result.json'),'--trace-output',str(folder/'trace.json'),'--log-output',str(folder/'evaluation.log')]
        outcome = run_command(command,folder/'process.log',180)
        record = {'problem':1,'algorithm_version':VERSION,'experiment':EXPERIMENT,'case':case,'cores':5,'candidate':name,**outcome,
                  'makespan':None,'added_copy_bytes':None,'partition_added_copy_bytes':None,'spill_added_copy_bytes':None}
        if outcome['status'] == 'success':
            record.update(validate_result(read(folder/'result.json'),5))
            record.update(plan_sha256=sha(plan), result_sha256=sha(folder/'result.json'))
        save(folder/'evaluation.json',record)
        print(case,name,record['status'],record['makespan'],flush=True)
        rows.append(record); save(ROOT/'evaluations.json',rows)
        return record
    try:
        for selected in manifest['selected']:
            case = selected['case']; destination = ROOT/'runs'/case; destination.mkdir()
            base_dir = destination/'baseline'; base_dir.mkdir()
            base_plan = ROOT/'baseline'/f'{case}_plan.json'
            baseline = evaluate(case,'baseline',base_plan,base_dir)
            if baseline['status'] != 'success' or baseline['makespan'] != int(low[case]['baseline_makespan']):
                raise ValueError('baseline did not reproduce: '+case)
            gen = run_command([sys.executable,'-B',str(Path(__file__)),'--generate',case],destination/'generation.log',30)
            save(destination/'generation_process.json',gen)
            choices = [(baseline,base_plan,base_dir/'result.json')]
            if gen['status'] == 'success':
                seen = {json.dumps(read(base_plan),sort_keys=True):'baseline'}
                for candidate in read(destination/'generation.json')['candidates']:
                    if candidate['status'] != 'generated': continue
                    name = candidate['candidate']; folder = destination/name; plan = folder/'plan.json'
                    signature = json.dumps(read(plan),sort_keys=True)
                    if signature in seen:
                        save(folder/'duplicate.json',{'same_as':seen[signature]}); continue
                    seen[signature] = name
                    record = evaluate(case,name,plan,folder)
                    if record['status'] == 'success': choices.append((record,plan,folder/'result.json'))
            winner,plan,result = min(choices,key=lambda r:(r[0]['makespan'],r[0]['candidate'] != 'baseline',r[0]['candidate']))
            shutil.copy2(plan,ROOT/'selected'/f'{case}_n5.json')
            shutil.copy2(result,ROOT/'selected'/f'{case}_n5_result.json')
            selections.append({'case':case,'cores':5,'baseline_makespan':baseline['makespan'],'selected_candidate':winner['candidate'],
                'makespan':winner['makespan'],'reduction_percent':100*(1-winner['makespan']/baseline['makespan']),
                'baseline_speedup':int(low[case]['single_makespan'])/baseline['makespan'],
                'speedup':int(low[case]['single_makespan'])/winner['makespan'],
                'baseline_added_copy_bytes':baseline['added_copy_bytes'],'added_copy_bytes':winner['added_copy_bytes']})
            save(ROOT/'selection.json',selections)
        manifest['status'] = 'completed'
    except BaseException as exc:
        manifest['status'] = 'failed'; manifest['error'] = repr(exc); raise
    finally:
        manifest['wall_seconds'] = time.perf_counter()-started
        manifest['protected_unchanged'] = all(sha(A_ROOT/p) == h for p,h in manifest['protected_hashes'].items())
        save(ROOT/'manifest.json',manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',action='store_true'); group.add_argument('--run',action='store_true'); group.add_argument('--generate')
    args = parser.parse_args()
    if args.prepare: prepare()
    elif args.run: run()
    else: generate(args.generate)
