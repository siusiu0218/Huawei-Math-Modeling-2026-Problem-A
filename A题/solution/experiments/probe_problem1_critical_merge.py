"""Post-pilot transfer-specific refinement, separately frozen as Q1 v011."""
import json
from pathlib import Path
import shutil
import sys
import time
from probe_problem1_critical_local import A_ROOT, SOLUTION, ROOT as PREVIOUS, read, save, sha
from result_paths import experiment_path
from process_runner import run_command
from portfolio_scheduler import validate_result
from scene_a_critical_merge import candidates

EXPERIMENT = 'exp132_20260926_critical_neighbour_merge'
ROOT = experiment_path('v011',EXPERIMENT)


def generate(case):
    rows = []; started = time.perf_counter()
    for name,plan,edit,error in candidates(read(A_ROOT/f'data/{case}.json'),read(PREVIOUS/'baseline'/f'{case}_plan.json'),read(PREVIOUS/'baseline'/f'{case}_result.json')):
        folder = ROOT/case/name; folder.mkdir()
        if plan: save(folder/'plan.json',plan)
        rows.append({'candidate':name,'edit':edit,'error':error,'status':'invalid' if error else 'generated'})
    save(ROOT/case/'generation.json',{'seconds':time.perf_counter()-started,'candidates':rows})


def run():
    ROOT.mkdir(parents=True,exist_ok=False)
    previous = read(PREVIOUS/'manifest.json')
    selected = [s['case'] for s in previous['selected'] if s['selection_metric'] == 'transfer_only']
    sources = [SOLUTION/'src'/n for n in ('scene_a_critical_merge.py','scene_a_critical_local.py','graph_analysis.py','region_scheduler.py')]
    sources += [Path(__file__),SOLUTION/'experiments/probe_problem1_critical_local.py',SOLUTION/'experiments/process_runner.py',SOLUTION/'experiments/result_paths.py']
    manifest = {'problem':1,'algorithm_version':'v011','experiment':EXPERIMENT,'status':'running','cases':selected,'cores':[5],
        'policy':'top two positive-boundary-saving same-core consecutive critical-chain pairs; baseline retained',
        'scope':'post-hoc development refinement on the same two transfer representatives; not independent validation',
        'generation_timeout_seconds':30,'evaluation_timeout_seconds':180,'random_seed':None,'retries':0,
        'baseline_experiment':str(PREVIOUS),'protected_hashes':previous['protected_hashes'],
        'source_hashes':{str(p.relative_to(SOLUTION)):sha(p) for p in sources},
        'command':[sys.executable,'-B',str(Path(__file__))]}
    for p in sources:
        target = ROOT/'source'/p.relative_to(SOLUTION); target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,target)
    for path,digest in manifest['protected_hashes'].items(): assert sha(A_ROOT/path)==digest
    save(ROOT/'manifest.json',manifest)
    started = time.perf_counter(); evaluations = []; selections = []
    try:
        for case in selected:
            (ROOT/case).mkdir()
            baseline_path = PREVIOUS/'runs'/case/'baseline/result.json'
            baseline = read(baseline_path)
            baseline_eval = read(PREVIOUS/'runs'/case/'baseline/evaluation.json')
            assert sha(baseline_path)==baseline_eval['result_sha256']
            assert sha(PREVIOUS/'baseline'/f'{case}_plan.json')==baseline_eval['plan_sha256']
            # Explicitly reuses the fresh baseline evaluation in exp131.
            save(ROOT/case/'baseline_provenance.json',baseline_eval)
            outcome = run_command([sys.executable,'-B',str(Path(__file__)),'--generate',case],ROOT/case/'generation.log',30)
            save(ROOT/case/'generation_process.json',outcome)
            options = [(baseline['makespan'],'baseline',PREVIOUS/'baseline'/f'{case}_plan.json',baseline_path)]
            if outcome['status']=='success':
                for candidate in read(ROOT/case/'generation.json')['candidates']:
                    if candidate['status']!='generated': continue
                    name=candidate['candidate']; folder=ROOT/case/name
                    command=[sys.executable,'-B',str(A_ROOT/'code/multicore_cut_evaluate_problem_1.py'),str(A_ROOT/f'data/{case}.json'),str(folder/'plan.json'),
                        '--config',str(A_ROOT/'data/config.txt'),'-o',str(folder/'result.json'),'--trace-output',str(folder/'trace.json'),'--log-output',str(folder/'evaluation.log')]
                    record={'problem':1,'algorithm_version':'v011','experiment':EXPERIMENT,'case':case,'cores':5,'candidate':name,
                        **run_command(command,folder/'process.log',180)}
                    if record['status']=='success':
                        result=read(folder/'result.json'); record.update(validate_result(result,5))
                        record.update(plan_sha256=sha(folder/'plan.json'),result_sha256=sha(folder/'result.json'))
                        assert baseline['data_movement_bytes']['partition_added_copy_bytes']-record['partition_added_copy_bytes']==candidate['edit']['predicted_partition_byte_saving']
                        options.append((record['makespan'],name,folder/'plan.json',folder/'result.json'))
                    evaluations.append(record); save(folder/'evaluation.json',record); save(ROOT/'evaluations.json',evaluations)
                    print(case,name,record['status'],record.get('makespan'),flush=True)
            makespan,name,plan,result=min(options,key=lambda x:(x[0],x[1]!='baseline',x[1]))
            shutil.copy2(plan,ROOT/case/'selected_plan.json'); shutil.copy2(result,ROOT/case/'selected_result.json')
            selections.append({'case':case,'baseline_makespan':baseline['makespan'],'makespan':makespan,'candidate':name,
                'reduction_percent':100*(1-makespan/baseline['makespan'])})
            save(ROOT/'selection.json',selections)
        manifest['status']='completed'
    except BaseException as exc:
        manifest['status']='failed'; manifest['error']=repr(exc); raise
    finally:
        manifest['wall_seconds']=time.perf_counter()-started
        manifest['protected_unchanged']=all(sha(A_ROOT/p)==h for p,h in manifest['protected_hashes'].items())
        save(ROOT/'manifest.json',manifest)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--generate': generate(sys.argv[2])
    else: run()
