"""Frozen Q3 reserve baseline: original evaluators, archived Q2 plans."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys
import time
from datetime import datetime, timezone
from fractions import Fraction
from run_problem2 import save, run_command
from run_problem3_pair import sha, fingerprint, valid_record

SOLUTION=Path(__file__).resolve().parents[1]
OUTPUT=Path('D:/workspace/HuaWei/A题/solution/outputs/10_problem3')


def cache_diagnosis(result):
    inserted, requested=set(),set()
    miss_counts={'first_request':0,'repeat_before_first_fill':0,'after_prior_fill':0}
    miss_bytes={k:0 for k in miss_counts}
    hit_ops=set()
    reinsertions=[]
    for event in result['cache_events']:
        tid=event['tensor_id']
        key=(event['core_id'],event['op_id'])
        if event['event']=='miss':
            kind='after_prior_fill' if tid in inserted else 'repeat_before_first_fill' if tid in requested else 'first_request'
            miss_counts[kind]+=1;miss_bytes[kind]+=event['size_bytes'];requested.add(tid)
        elif event['event']=='hit':
            hit_ops.add(key);requested.add(tid)
        elif event['event']=='insert':
            inserted.add(tid)
            if key in hit_ops:reinsertions.append(event)
    return {'miss_event_counts':miss_counts,'miss_event_bytes':miss_bytes,
        'hit_completion_insert_events':reinsertions,
        'evicted_entries':sum(len(e.get('evicted_tensor_ids',[])) for e in result['cache_events']),
        'cache_peak_bytes':max((e.get('used_bytes',0) for e in result['cache_events']),default=0),
        'scope':'event descriptions, not proof of critical-path performance causes; after_prior_fill may include oversize/eviction edge cases'}


def summarize(manifest,out):
    rows=[];failed=[]
    for item in manifest['items']:
        records={mode:[r for r in item['attempts'] if r['mode']==mode][-1]
                 for mode in ('no_l2','cache') if any(r['mode']==mode for r in item['attempts'])}
        if len(records)!=2 or not all(valid_record(r,out) for r in records.values()):
            failed.append({'case':item['case'],'cores':item['cores'],'records':records});continue
        a,b=[json.loads((out/records[mode]['result']).read_text(encoding='utf-8')) for mode in ('no_l2','cache')]
        assert a['num_cores']==b['num_cores']==item['cores']
        assert a['data_movement_bytes']==b['data_movement_bytes']
        assert all(t['copy_in_start']-t['copy_out_end']>=500 for t in b['cross_core_transfers'])
        diag=cache_diagnosis(b)
        assert diag['cache_peak_bytes']<=b['cache_capacity_bytes']
        save(out/'metrics'/f"{item['case']}_n{item['cores']}_diagnosis.json",diag)
        stats=b['cache_stats']
        assert stats['hit_rate']==(stats['hit_bytes']/(stats['hit_bytes']+stats['miss_bytes']) if stats['hit_bytes']+stats['miss_bytes'] else 0)
        rows.append({'problem':3,'version':'v001','experiment':out.name,'case':item['case'],'cores':item['cores'],
            'no_l2_makespan':a['makespan'],'cache_makespan':b['makespan'],
            'speedup':a['makespan']/b['makespan'] if b['makespan'] else None,
            'hit_bytes':stats['hit_bytes'],'miss_bytes':stats['miss_bytes'],'byte_hit_rate':stats['hit_rate'],
            'copy_in_hits':stats['hits'],'copy_in_accesses':stats['accesses'],
            'official_added_copy_bytes':b['data_movement_bytes']['added_copy_bytes'],
            'cache_peak_bytes':diag['cache_peak_bytes'],'evicted_entries':diag['evicted_entries'],
            'hit_completion_insertions':len(diag['hit_completion_insert_events']),
            'no_l2_eval_seconds':records['no_l2']['seconds'],'cache_eval_seconds':records['cache']['seconds'],
            'plan_sha256':item['plan_sha256']})
    if rows:
        with (out/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=[]
    for n in range(1,6):
        subset=[r for r in rows if r['cores']==n]
        summary.append({'cores':n,'successful_pairs':len(subset),
            'mean_speedup':float(sum((Fraction(r['no_l2_makespan'],r['cache_makespan']) for r in subset),Fraction(0))/len(subset)) if subset else None,
            'faster':sum(r['cache_makespan']<r['no_l2_makespan'] for r in subset),
            'same':sum(r['cache_makespan']==r['no_l2_makespan'] for r in subset),
            'slower':sum(r['cache_makespan']>r['no_l2_makespan'] for r in subset),
            'mean_case_byte_hit_rate':sum(r['byte_hit_rate'] for r in subset)/len(subset) if subset else None,
            'pooled_byte_hit_rate':sum(r['hit_bytes'] for r in subset)/sum(r['hit_bytes']+r['miss_bytes'] for r in subset) if sum(r['hit_bytes']+r['miss_bytes'] for r in subset) else 0})
    save(out/'summary.json',{'rows':len(rows),'failures':failed,'by_cores':summary,
        'evaluation_seconds':sum(a['seconds'] for item in manifest['items'] for a in item['attempts'])})
    return rows,summary,failed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selection',required=True)
    p.add_argument('--experiment',required=True)
    p.add_argument('--resume',action='store_true')
    args=p.parse_args()
    if Path(args.experiment).name!=args.experiment:p.error('experiment must be one directory name')
    selection_path=Path(args.selection).resolve()
    selection=json.loads(selection_path.read_text(encoding='utf-8'))
    for path,digest in selection['source_hashes'].items():
        if sha(path)!=digest:raise ValueError('selection source changed: '+path)
    config=SOLUTION.parent/'data/config.txt'
    assert sha(config)==selection['config_sha256']
    selected={x['case'] for x in selection['cases'] if x['role']=='reserve'}
    plans=[x for x in selection['plans'] if x['case'] in selected]
    assert len(plans)==len(selected)*5 and len(selected)==6
    features={x['case']:x for x in selection['features']}
    for item in plans:
        assert sha(item['path'])==item['sha256']
        assert sha(SOLUTION.parent/'data'/f"{item['case']}.json")==features[item['case']]['graph_sha256']
    sources=list((SOLUTION.parent/'code').glob('*.py')) + [Path(__file__),Path(__file__).with_name('run_problem3_pair.py'),Path(__file__).with_name('run_problem2.py'),Path(__file__).with_name('result_paths.py')]
    hashes=fingerprint(sources+[selection_path,config]+[Path(x['path']) for x in plans]+[SOLUTION.parent/'data'/f'{case}.json' for case in sorted(selected)])
    out=OUTPUT/'raw/problem_3/v001'/args.experiment
    if args.resume:
        manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
        if manifest['hashes_before']!=hashes:raise ValueError('resume source/input mismatch')
        for rel,digest in manifest['archive_hashes'].items():
            if sha(out/rel)!=digest:raise ValueError('archive changed: '+rel)
    else:
        out.mkdir(parents=True,exist_ok=False)
        for folder in ('plans','inputs','metrics','logs','source'):(out/folder).mkdir()
        for source in sources:shutil.copy2(source,out/'source'/source.name)
        shutil.copy2(selection_path,out/'source/selection.json')
        shutil.copy2(config,out/'inputs/config.txt')
        for case in selected:shutil.copy2(SOLUTION.parent/'data'/f'{case}.json',out/'inputs'/f'{case}.json')
        items=[]
        for item in plans:
            stem=f"{item['case']}_n{item['cores']}"
            shutil.copy2(item['path'],out/'plans'/f'{stem}.json')
            items.append({'case':item['case'],'cores':item['cores'],'plan_source':item['path'],
                          'plan_sha256':item['sha256'],'attempts':[]})
        archives=[path for folder in ('plans','inputs','source') for path in (out/folder).glob('*')]
        manifest={'problem':3,'version':'v001','purpose':'frozen reserve A/B baseline',
            'policy':'original evaluator; disclosed hit-completion reinsertion; user approved 2026-09-26',
            'created_utc':datetime.now(timezone.utc).isoformat(),'hashes_before':hashes,
            'archive_hashes':{str(x.relative_to(out)):sha(x) for x in archives},
            'items':items,'status':'running','timeout':180,'automatic_retries':0,
            'plan_generation_seconds':None,'generation_note':'reuse Q2 v011 final plans / archived single; upstream search cost not zero, see Q2 v011 REPORT.md; cold-start cost not measured',
            'command':[sys.executable,*sys.argv],'invocations':[]}
        save(out/'manifest.json',manifest)
        with (SOLUTION/'experiments/INDEX.md').open('a',encoding='utf-8') as f:
            f.write(f'\n- 问题 3 v001 | {args.experiment} | running | 6 预留图 × 1～5 核 A/B 固定基线\n')
    start=time.perf_counter()
    for item in manifest['items']:
        stem=f"{item['case']}_n{item['cores']}"
        for mode in ('no_l2','cache'):
            previous=[r for r in item['attempts'] if r['mode']==mode]
            if previous and valid_record(previous[-1],out):continue
            number=len(previous)+1
            result=out/'metrics'/f'{stem}_{mode}_attempt{number}.json'
            command=[sys.executable,'-B',str(Path(__file__).with_name('run_problem3_pair.py')),
                '--worker',mode,'--graph',str(out/'inputs'/f"{item['case']}.json"),
                '--plan',str(out/'plans'/f'{stem}.json'),'--config',str(out/'inputs/config.txt'),
                '--result',str(result)]
            record=run_command(command,out/'logs'/f'{stem}_{mode}_attempt{number}.txt',180)
            record.update(mode=mode,result=str(result.relative_to(out)),command=command,plan_sha256=sha(out/'plans'/f'{stem}.json'))
            if record['status']=='success':
                if result.exists():record['result_sha256']=sha(result)
                if not valid_record(record,out):record['status']='invalid_result'
            item['attempts'].append(record)
            save(out/'manifest.json',manifest)
        print(stem,[(r['mode'],r['status']) for r in item['attempts']],flush=True)
    manifest['invocations'].append({'wall_seconds':time.perf_counter()-start,'resume':args.resume})
    manifest['hashes_after']=fingerprint([Path(x) for x in hashes])
    assert manifest['hashes_after']==hashes
    assert all(sha(out/rel)==digest for rel,digest in manifest['archive_hashes'].items())
    rows,summary,failed=summarize(manifest,out)
    manifest['status']='completed' if not failed else 'incomplete'
    save(out/'manifest.json',manifest)
    with (SOLUTION/'experiments/INDEX.md').open('a',encoding='utf-8') as f:
        f.write(f"\n- 问题 3 v001 | {args.experiment} | {manifest['status']} | {len(rows)}/30 pairs | outputs/10_problem3/raw/problem_3/v001/{args.experiment}\n")
    print(json.dumps(summary,indent=2),flush=True)
    if failed:raise SystemExit(1)


if __name__=='__main__':main()
