"""Freeze Q3 development/reserve cases from graph structure, before Q3 scores."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from run_problem3_pair import sha, fingerprint
from run_problem2 import save

SOLUTION=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOLUTION/'src'))
from graph_analysis import Graph
from component_scheduler import independent_components


def features(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    graph=Graph(data)
    tensors={t['id']:t for t in data['tensors']}
    shared=[t for tid,t in tensors.items() if len(graph.consumers[tid])>1]
    shared_inputs=[t for t in shared if not graph.producers[t['id']]]
    work={i:{'UB':0,'L1':0} for i in graph.ops}
    for tid,t in tensors.items():
        for i in graph.producers[tid] | graph.consumers[tid]:
            pos=t['pos'] if t['pos'] in ('UB','L1') else 'UB'
            work[i][pos]+=t['size']
    return {'case':path.stem,'compute_ops':len(graph.ops),
        'components':len(independent_components(graph)),
        'shared_operand_bytes':sum(t['size'] for t in shared),
        'shared_graph_input_bytes':sum(t['size'] for t in shared_inputs),
        'shared_operand_to_l2_ratio':sum(t['size'] for t in shared)/1048576,
        'max_tensor_bytes':max((t['size'] for t in tensors.values()),default=0),
        'max_op_UB_bytes':max((w['UB'] for w in work.values()),default=0),
        'max_op_L1_bytes':max((w['L1'] for w in work.values()),default=0),
        'graph_sha256':sha(path)}


def select(rows):
    selected=[]
    for connected in (True,False):
        group=sorted([r for r in rows if (r['components']==1)==connected and r['case']!='case_001'],
                     key=lambda r:(r['compute_ops'],r['case']))
        for q in range(3):
            band=group[len(group)*q//3:len(group)*(q+1)//3]
            if len(band)<2:
                raise ValueError('insufficient cases for a size/connectivity stratum')
            dev=max(band,key=lambda r:(r['shared_graph_input_bytes'],r['shared_operand_to_l2_ratio'],r['case']))
            keys=('shared_graph_input_bytes','shared_operand_to_l2_ratio','max_op_UB_bytes','max_op_L1_bytes')
            ranges={k:max(r[k] for r in band)-min(r[k] for r in band) for k in keys}
            reserve=max((r for r in band if r!=dev),key=lambda r:(sum(abs(r[k]-dev[k])/(ranges[k] or 1) for k in keys),r['case']))
            for role,row in [('development',dev),('reserve',reserve)]:
                selected.append({'case':row['case'],'role':role,'connected':connected,'size_tertile':q+1})
    return selected


def main():
    out=Path(sys.argv[1])
    if out.exists():raise FileExistsError(out)
    data=SOLUTION.parent/'data'
    rows=[features(path) for path in sorted(data.glob('case_*.json'))]
    assert len(rows)==100
    selected=select(rows)
    origin=SOLUTION/'outputs/09_problem2/raw/problem_2/v011/exp109_20260926_active_full'
    plans=[]
    for item in selected:
        case=item['case']
        for n in range(1,6):
            path=origin/(f'generated/{case}_k1_single/plan.json' if n==1 else f'plans/{case}_n{n}.json')
            plans.append({'case':case,'cores':n,'path':str(path.resolve()),'sha256':sha(path)})
    save(out,{'created_utc':datetime.now(timezone.utc).isoformat(),'version':'v001',
        'rule':'exclude Q3-seen case_001; single/multiple component strata, then size tertiles; maximal shared input dev; farthest normalized sharing and memory-pressure reserve; case id breaks ties only',
        'limitations':'all graphs were used in Q1/Q2; reserve is only unused for Q3 tuning; structural selection is not random; static bytes are not simulated peaks',
        'evaluator_policy':'user approved original evaluator with hit-completion reinsertion disclosed; no evaluator modifications',
        'cases':selected,'features':rows,'plans':plans,'cores':[1,2,3,4,5],
        'groups':{'A':'archived Q2 v011/single plan, no L2','B':'same plan, Cache'},
        'budget':{'candidate_plans_per_configuration':1,'generation':'reuse archived plans, upstream cost not zero','evaluation_timeout_seconds':180,'execution':'sequential','automatic_retries':0},
        'metrics':{'primary':'no_l2_makespan/cache_makespan','aggregation':'arithmetic mean of per-case ratios by cores','hit_rate':'hit_bytes/(hit_bytes+miss_bytes); no L2 null'},
        'config_sha256':sha(data/'config.txt'),'source_hashes':fingerprint(list((SOLUTION.parent/'code').glob('*.py'))+[Path(__file__),SOLUTION/'src/graph_analysis.py',SOLUTION/'src/component_scheduler.py'])})
    print(json.dumps(selected,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
