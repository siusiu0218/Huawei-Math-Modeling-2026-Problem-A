"""Q3 v002 fixed-placement development: Cache-affinity vs matched-budget control."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from fractions import Fraction
from datetime import datetime, timezone
from run_problem2 import run_command,save
from run_problem3_pair import sha,fingerprint,valid_record

SOLUTION=Path(__file__).resolve().parents[1]
MODES=('cache_affinity','critical_path')


def canonical(plan):
    return hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def worker(args):
    sys.path.insert(0,str(SOLUTION/'src'))
    from scene_b_cache_order import reorder
    graph=json.loads(Path(args.graph).read_text(encoding='utf-8'))
    base=json.loads(Path(args.plan).read_text(encoding='utf-8'))
    save(Path(args.result),reorder(graph,base,args.worker))


def evaluate(plan,graph,config,mode,out,stem):
    result=out/'metrics'/f'{stem}_{mode}.json'
    command=[sys.executable,'-B',str(Path(__file__).with_name('run_problem3_pair.py')),
        '--worker',mode,'--graph',str(graph),'--plan',str(plan),'--config',str(config),'--result',str(result)]
    record=run_command(command,out/'logs'/f'{stem}_{mode}.txt',180)
    record.update(mode=mode,result=str(result.relative_to(out)),command=command,plan_sha256=sha(plan),reused=False)
    if record['status']=='success':
        if result.exists():record['result_sha256']=sha(result)
        if not valid_record(record,out):record['status']='invalid_result'
    return record


def summarize(manifest,out):
    rows=[];candidate_rows=[]
    for item in manifest['items']:
        candidates=item['candidates']
        base=candidates['baseline']
        def success(c):return c.get('status')=='success' and all(valid_record(r,out) for r in c['evaluations'].values())
        assert success(base)
        def result(c,mode):return json.loads((out/c['evaluations'][mode]['result']).read_text(encoding='utf-8'))
        def time_of(name):return result(candidates[name],'cache')['makespan']
        available={m:success(candidates.get(m,{})) for m in MODES}
        # Each arm gets one additional candidate; ties keep the shared baseline.
        picks={m:m if available[m] and time_of(m)<time_of('baseline') else 'baseline' for m in MODES}
        best=min(['baseline']+[m for m in MODES if available[m]],key=lambda m:(time_of(m),m!='baseline',m))
        a,b=result(base,'no_l2'),result(base,'cache')
        c,d=result(candidates[picks['cache_affinity']],'cache'),result(candidates[picks['cache_affinity']],'no_l2')
        rows.append({'problem':3,'version':'v002','experiment':out.name,'case':item['case'],'cores':item['cores'],
            'A_old_no_l2':a['makespan'],'B_old_cache':b['makespan'],
            'C_affinity_selected_cache':c['makespan'],'D_affinity_selected_no_l2':d['makespan'],
            'affinity_pick':picks['cache_affinity'],'control_pick':picks['critical_path'],
            'control_selected_cache':time_of(picks['critical_path']),
            'all_candidates_best':best,'all_candidates_cache':time_of(best),
            'affinity_available':available['cache_affinity'],'control_available':available['critical_path'],
            'cache_scheduling_speedup':b['makespan']/c['makespan'],
            'cache_effect_old':a['makespan']/b['makespan'],'cache_effect_new':d['makespan']/c['makespan'],
            'general_no_l2_speedup':a['makespan']/d['makespan'],
            'old_byte_hit_rate':b['cache_stats']['hit_rate'],'new_byte_hit_rate':c['cache_stats']['hit_rate']})
        for name,candidate in candidates.items():
            record={'case':item['case'],'cores':item['cores'],'candidate':name,'status':candidate['status'],
                'generation_seconds':candidate.get('generation',{}).get('seconds',0),
                'canonical_plan_sha256':candidate.get('canonical_plan_sha256')}
            for mode in ('no_l2','cache'):
                r=candidate.get('evaluations',{}).get(mode,{})
                record[mode+'_evaluation_status']=r.get('status')
                record[mode+'_seconds']=0 if r.get('reused') else r.get('seconds',0)
                record[mode+'_reused']=r.get('reused')
                if valid_record(r,out):record[mode+'_makespan']=result(candidate,mode)['makespan']
            candidate_rows.append(record)
    for name,values in [('comparison.csv',rows),('candidates.csv',candidate_rows)]:
        keys=list(dict.fromkeys(k for row in values for k in row))
        with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(values)
    summary=[]
    for n in range(1,6):
        part=[r for r in rows if r['cores']==n]
        if not part:continue
        summary.append({'cores':n,'count':len(part),
            'affinity_improved':sum(r['C_affinity_selected_cache']<r['B_old_cache'] for r in part),
            'control_improved':sum(r['control_selected_cache']<r['B_old_cache'] for r in part),
            'affinity_beats_control':sum(r['C_affinity_selected_cache']<r['control_selected_cache'] for r in part),
            'control_beats_affinity':sum(r['control_selected_cache']<r['C_affinity_selected_cache'] for r in part),
            'affinity_mean_speedup':float(sum((Fraction(r['B_old_cache'],r['C_affinity_selected_cache']) for r in part),Fraction(0))/len(part)),
            'control_mean_speedup':float(sum((Fraction(r['B_old_cache'],r['control_selected_cache']) for r in part),Fraction(0))/len(part))})
    save(out/'summary.json',{'by_cores':summary,'generation_seconds':sum(r['generation_seconds'] for r in candidate_rows),
        'new_evaluation_seconds':sum(r['no_l2_seconds']+r['cache_seconds'] for r in candidate_rows),
        'new_evaluations':sum(not r.get(mode+'_reused',True) and r.get(mode+'_evaluation_status') is not None for r in candidate_rows for mode in ('no_l2','cache')),
        'candidate_failures':[r for r in candidate_rows if r['status']!='success'],
        'scope':'development; affinity and control each receive baseline plus one candidate; combined best has more search budget'})
    return rows,summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--worker',choices=MODES);p.add_argument('--graph');p.add_argument('--plan');p.add_argument('--result')
    p.add_argument('--baseline');p.add_argument('--experiment');p.add_argument('--selection')
    args=p.parse_args()
    if args.worker:worker(args);return
    if not args.experiment or Path(args.experiment).name!=args.experiment:p.error('experiment name required')
    baseline=Path(args.baseline).resolve();selection_path=Path(args.selection).resolve()
    selection=json.loads(selection_path.read_text(encoding='utf-8'))
    for path,digest in selection['source_hashes'].items():
        if sha(path)!=digest:raise ValueError('frozen source changed: '+path)
    bm=json.loads((baseline/'manifest.json').read_text(encoding='utf-8'))
    assert bm['status']=='completed'
    for path,digest in bm['hashes_after'].items():assert sha(path)==digest
    for rel,digest in bm['archive_hashes'].items():assert sha(baseline/rel)==digest
    out=Path('D:/workspace/HuaWei/A题/solution/outputs/10_problem3/raw/problem_3/v002')/args.experiment
    out.mkdir(parents=True,exist_ok=False)
    for folder in ('plans','inputs','metrics','logs','source'):(out/folder).mkdir()
    sources=[Path(path) for path in selection['source_hashes']]
    for source in sources:shutil.copy2(source,out/'source'/source.name)
    shutil.copy2(selection_path,out/'source/selection.json')
    shutil.copy2(baseline/'inputs/config.txt',out/'inputs/config.txt')
    cases={x['case'] for x in bm['items']}
    for case in cases:shutil.copy2(baseline/'inputs'/f'{case}.json',out/'inputs'/f'{case}.json')
    manifest={'problem':3,'version':'v002','status':'running','items':[],
        'created_utc':datetime.now(timezone.utc).isoformat(),'command':[sys.executable,*sys.argv],
        'baseline':str(baseline),'baseline_manifest_sha256':sha(baseline/'manifest.json'),
        'source_hashes_before':fingerprint(sources),'selection_sha256':sha(selection_path),
        'budgets':selection['budgets'],'upstream_cost_note':'Q2 plan search and Q3 baseline reused; not zero-cost cold start'}
    save(out/'manifest.json',manifest)
    with (SOLUTION/'experiments/INDEX.md').open('a',encoding='utf-8') as f:f.write(f'\n- 问题3 v002 | {args.experiment} | running | fixed placement ordering\n')
    start=time.perf_counter()
    for source_item in bm['items']:
        case,n=source_item['case'],source_item['cores'];stem=f'{case}_n{n}'
        base_plan=baseline/'plans'/f'{stem}.json'
        shutil.copy2(base_plan,out/'plans'/f'{stem}_baseline.json')
        bp=json.loads(base_plan.read_text(encoding='utf-8'))
        base={'status':'success','canonical_plan_sha256':canonical(bp),'evaluations':{},'plan':f'plans/{stem}_baseline.json'}
        for mode in ('no_l2','cache'):
            old=[r for r in source_item['attempts'] if r['mode']==mode][-1]
            assert valid_record(old,baseline)
            target=out/'metrics'/f'{stem}_baseline_{mode}.json';shutil.copy2(baseline/old['result'],target)
            base['evaluations'][mode]={'status':'success','reused':True,'seconds':0,
                'source':str(baseline/old['result']),'source_sha256':old['result_sha256'],
                'result':str(target.relative_to(out)),'result_sha256':sha(target)}
        item={'case':case,'cores':n,'candidates':{'baseline':base}}
        manifest['items'].append(item)
        for mode in MODES:
            plan=out/'plans'/f'{stem}_{mode}.json'
            command=[sys.executable,'-B',str(Path(__file__).resolve()),'--worker',mode,
                '--graph',str(out/'inputs'/f'{case}.json'),'--plan',str(out/'plans'/f'{stem}_baseline.json'),'--result',str(plan)]
            generation=run_command(command,out/'logs'/f'{stem}_{mode}_generate.txt',30)
            candidate={'status':generation['status'],'generation':generation,'command':command,
                'plan':str(plan.relative_to(out)),'evaluations':{}}
            item['candidates'][mode]=candidate
            if generation['status']=='success':
                generated=json.loads(plan.read_text(encoding='utf-8'))
                assert generated['node_to_subgraph']==bp['node_to_subgraph']
                assert [set(x) for x in generated['core_schedules']]==[set(x) for x in bp['core_schedules']]
                candidate['canonical_plan_sha256']=canonical(generated)
                duplicate=next((c for name,c in item['candidates'].items() if name!=mode and c.get('status')=='success' and c.get('canonical_plan_sha256')==candidate['canonical_plan_sha256']),None)
                for condition in ('no_l2','cache'):
                    if duplicate:
                        candidate['evaluations'][condition]={**duplicate['evaluations'][condition],'reused':True,'seconds':0}
                    else:
                        candidate['evaluations'][condition]=evaluate(plan,out/'inputs'/f'{case}.json',out/'inputs/config.txt',condition,out,f'{stem}_{mode}')
                    save(out/'manifest.json',manifest)
                candidate['status']='success' if all(valid_record(r,out) for r in candidate['evaluations'].values()) else 'evaluation_failed'
            save(out/'manifest.json',manifest)
        print(stem,{k:v['status'] for k,v in item['candidates'].items()},flush=True)
    manifest['wall_seconds']=time.perf_counter()-start
    manifest['source_hashes_after']=fingerprint(sources)
    assert manifest['source_hashes_before']==manifest['source_hashes_after']
    assert sha(baseline/'manifest.json')==manifest['baseline_manifest_sha256']
    rows,summary=summarize(manifest,out)
    manifest['status']='completed' if all(c['status']=='success' for i in manifest['items'] for c in i['candidates'].values()) else 'completed_with_candidate_failures'
    manifest['artifact_hashes']={str(path.relative_to(out)):sha(path) for folder in ('plans','inputs','metrics','source') for path in (out/folder).glob('*')}
    save(out/'manifest.json',manifest)
    with (SOLUTION/'experiments/INDEX.md').open('a',encoding='utf-8') as f:f.write(f"\n- 问题3 v002 | {args.experiment} | {manifest['status']} | {len(rows)} configurations\n")
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
