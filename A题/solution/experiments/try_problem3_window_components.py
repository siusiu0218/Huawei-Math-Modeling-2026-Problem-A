"""Frozen, three-candidate v004 development pilot on six disclosed cases."""
import csv
import json
from pathlib import Path
import shutil
import sys
import time

sys.dont_write_bytecode = True
S = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(S/'src'))
from scene_b_window_components import make_plan
from process_runner import run_command
from replay_problem3_external import CASES, sha, save, OUT as REPLAY

OUT=S/'outputs/10_problem3/raw/problem_3/v004/exp123_20260926_window_pilot'


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    for d in ('inputs','plans','metrics','logs','source'):
        (OUT/d).mkdir()
    sources=[Path(__file__),S/'src/scene_b_window_components.py',S/'src/scene_b_window_components.LICENSE',
             S/'src/graph_analysis.py',S/'experiments/process_runner.py',S/'experiments/replay_problem3_external.py',
             S/'experiments/run_problem3_pair.py',S/'experiments/run_problem2.py',S/'experiments/result_paths.py',
             *list((S.parent/'code').glob('*.py'))]
    for p in sources:
        shutil.copy2(p,OUT/'source'/p.name)
    for p in (REPLAY/'inputs').glob('*'):
        shutil.copy2(p,OUT/'inputs'/p.name)
    manifest={'problem':3,'version':'v004','experiment':OUT.name,'status':'running',
        'scope':'six-case post-hoc development only; not independent validation or full result',
        'cases':CASES,'cores':5,'windows':[4,10,16],'sticky':0.5,
        'selection':'minimum Cache Makespan among v003 baseline and three windows; ties baseline then smaller window',
        'external_source':'4bebdda48585cb751466b504e05865cb39673593; MIT; attributed adaptation',
        'command':[sys.executable,*sys.argv], 'attempts':[], 'generation':[],
        'hashes_before':{str(p):sha(p) for p in sources+list((OUT/'inputs').glob('*'))},
        'replay_manifest_sha256':sha(REPLAY/'manifest.json'), 'upstream_cost':'v003 and external search costs excluded, not zero'}
    save(OUT/'manifest.json',manifest)
    records=[]
    def evaluate(case,label,mode,plan):
        stem=f'{case}_{label}_{mode}'
        result=OUT/'metrics'/f'{stem}.json'
        command=[sys.executable,str(S/'experiments/run_problem3_pair.py'),'--worker',mode,
                 '--graph',str(OUT/'inputs'/f'{case}.json'),'--plan',str(plan),
                 '--config',str(OUT/'inputs/config.txt'),'--result',str(result)]
        rec=run_command(command,OUT/'logs'/f'{stem}.txt',180)
        rec.update(case=case,label=label,mode=mode)
        if rec['status']=='success':
            data=json.loads(result.read_text());assert data['makespan']>0 and data['num_cores']==5
            rec.update(makespan=data['makespan'],result_sha256=sha(result),result=str(result.relative_to(OUT)))
        manifest['attempts'].append(rec);save(OUT/'manifest.json',manifest)
        print(stem,rec['status'],rec.get('makespan'),flush=True)
        return rec
    for case in CASES:
        graph=json.loads((OUT/'inputs'/f'{case}.json').read_text())
        baseline=json.loads((REPLAY/'metrics'/f'{case}_ours_cache.json').read_text())
        best=(baseline['makespan'],0,'baseline')
        shutil.copy2(REPLAY/'plans'/f'{case}_ours.json',OUT/'plans'/f'{case}_baseline.json')
        for window in (4,10,16):
            start=time.perf_counter()
            plan=make_plan(graph,5,window,0.5)
            path=OUT/'plans'/f'{case}_w{window}.json';save(path,plan)
            manifest['generation'].append({'case':case,'window':window,'seconds':time.perf_counter()-start,'plan_sha256':sha(path)})
            rec=evaluate(case,f'w{window}','cache',path)
            if rec['status']=='success':
                records.append({'case':case,'window':window,'baseline':baseline['makespan'],'candidate':rec['makespan']})
                best=min(best,(rec['makespan'],window,f'w{window}'))
        label=best[2]
        if label=='baseline':
            no=json.loads((REPLAY/'metrics'/f'{case}_ours_no_l2.json').read_text())['makespan']
        else:
            no=evaluate(case,label,'no_l2',OUT/'plans'/f'{case}_{label}.json').get('makespan')
        manifest.setdefault('selected',[]).append({'case':case,'label':label,'cache':best[0],
            'baseline_cache':baseline['makespan'],'no_l2':no,'same_plan_cache_speedup':no/best[0] if no else None,
            'reduction_percent':100*(1-best[0]/baseline['makespan'])})
        save(OUT/'manifest.json',manifest)
    manifest['hashes_after']={p:sha(Path(p)) for p in manifest['hashes_before']}
    assert manifest['hashes_after']==manifest['hashes_before']
    assert sha(REPLAY/'manifest.json')==manifest['replay_manifest_sha256']
    manifest['status']='completed' if all(r['status']=='success' for r in manifest['attempts']) else 'incomplete'
    save(OUT/'manifest.json',manifest)
    save(OUT/'comparison.json',records)
    print(json.dumps(manifest['selected'],ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
