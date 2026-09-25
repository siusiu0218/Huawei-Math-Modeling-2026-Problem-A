"""Read archived A/B/C/D traces; measure memory traffic and per-core pipe work."""
import json
from pathlib import Path
import sys
from collections import defaultdict
from run_problem2 import save
from run_problem3_pair import sha

SOLUTION=Path(__file__).resolve().parents[1]


def union_length(intervals):
    end=0;total=0
    for a,b in sorted(intervals):
        if b>end:total+=b-max(a,end);end=b
    return total


def metrics(result):
    cores=[]
    for core in result['per_core_timeline']:
        by_pipe=defaultdict(list);compute=defaultdict(int);copies=defaultdict(int)
        for op in core['ops']:
            by_pipe[op['pipe']].append((op['start'],op['end']))
            if op['op'] in ('COPY_IN','COPY_OUT'):copies[op.get('memory_path','unknown')]+=1
            else:compute[op['pipe']]+=op['duration']
        finish=max((o['end'] for o in core['ops']),default=0)
        cores.append({'core':core['core_id'],'finish':finish,'compute_pipe_cycles':dict(compute),
            'busy_union_by_pipe':{k:union_length(v) for k,v in by_pipe.items()},
            'any_pipe_busy':union_length([x for v in by_pipe.values() for x in v]),'copy_counts_by_path':dict(copies)})
    bound=max((cycles for core in cores for cycles in core['compute_pipe_cycles'].values()),default=0)
    return {'makespan':result['makespan'],'movement':result['data_movement_bytes'],'cache_stats':result.get('cache_stats'),
        'per_core':cores,'compute_pipe_work_lower_bound':bound,
        'gap_above_compute_bound':result['makespan']-bound,'cross_transfers':len(result['cross_core_transfers'])}


def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    run=SOLUTION/'outputs/10_problem3/raw/problem_3/v002/exp112_20260926_order_development'
    manifest=json.loads((run/'manifest.json').read_text(encoding='utf-8'))
    rows=[];hashes={}
    for item in manifest['items']:
        if item['case'] not in ('case_039','case_072','case_078') or item['cores'] not in (2,4):continue
        for name in ('baseline','cache_affinity','critical_path'):
            c=item['candidates'][name]
            if c['status']!='success':continue
            for condition in ('no_l2','cache'):
                path=run/c['evaluations'][condition]['result'];hashes[str(path)]=sha(path)
                result=json.loads(path.read_text(encoding='utf-8'))
                rows.append({'case':item['case'],'cores':item['cores'],'candidate':name,'condition':condition,**metrics(result)})
    save(out/'diagnosis.json',rows);save(out/'sources.json',hashes)
    print(json.dumps([{k:r[k] for k in ('case','cores','candidate','condition','makespan','compute_pipe_work_lower_bound','gap_above_compute_bound','cross_transfers')}|{'spill':r['movement']['spill_added_copy_bytes']} for r in rows],indent=2))


if __name__=='__main__':main()
