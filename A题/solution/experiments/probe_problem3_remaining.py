"""Additional source-grounded Cache diagnostics using original evaluators."""
import json
import sys
from pathlib import Path
from probe_problem3_rules import reads, evaluate, SOLUTION
from run_problem3_pair import fingerprint
from run_problem2 import save
from multicore_cut_evaluate_problem_3 import evaluate_problem_3
from multicore_cut_evaluate_problem_2 import evaluate_scene_b


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    sources = list((SOLUTION.parent/'code').glob('*.py')) + [Path(__file__), Path(__file__).with_name('probe_problem3_rules.py')]
    before = fingerprint(sources)
    graph, plan = reads([[1],[2,1],[3,1]], {1:600,2:6000,3:6000})
    a,b=evaluate(graph,plan)
    assert (a['makespan'],b['makespan']) == (231,217)
    hits=[e for e in b['cache_events'] if e['event']=='hit']
    assert len(hits)==2 and all(e['time']==210 for e in hits)
    save(out/'concurrent_hits.json', {'graph':graph,'plan':plan,'no_l2':a,'cache':b,
        'expectation':'two 600-byte hits at 210 share Cache: each ceil(600/250)=3 units, both finish at 216; compute ends 217'})
    graph={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':10} for i in range(1,4)],
        'tensors':[{'id':i,'pos':'UB','size':60} for i in (11,12,13)],
        'edges':[{'source':a,'target':b} for a,b in [(11,1),(1,12),(12,2),(2,13),(11,3),(13,3)]]}
    plan={'node_to_subgraph':{str(i):i for i in range(1,4)},'core_schedules':[[1,2,3]]}
    common=(graph,plan,60,{'L1':524288,'UB':120},500)
    a,b=evaluate_scene_b(*common),evaluate_problem_3(*common,1048576,250)
    assert [(e['event'],e['tensor_id']) for e in b['cache_events']]==[('miss',11),('insert',11),('hit',11)]
    save(out/'spill_identity.json',{'graph':graph,'plan':plan,'no_l2':a,'cache':b,
        'diagnostic_UB_capacity':120,'expectation':'input 11 is evicted locally to make room for 12+13, reloaded with the same logical id and hits Cache'})
    graph={'ops':[{'id':i,'op':'ADD','pipe':'PIPE_V','cycles':10} for i in range(1,5)],
        'tensors':[{'id':11,'pos':'UB','size':600},{'id':12,'pos':'UB','size':60000}],
        'edges':[{'source':a,'target':b} for a,b in [(1,11),(11,2),(12,3),(11,4)]]}
    plan={'node_to_subgraph':{str(i):i for i in range(1,5)},'core_schedules':[[1],[2],[3,4]]}
    a,b=evaluate(graph,plan)
    assert b['cache_stats']['hits']==1
    assert all(t['copy_in_start']-t['copy_out_end']>=500 for t in b['cross_core_transfers'])
    save(out/'cross_wait_hit.json',{'graph':graph,'plan':plan,'no_l2':a,'cache':b,
        'expectation':'second receiving core hits tensor 11; all cross-core reads respect 500-cycle release delay'})
    import shutil
    (out/'source').mkdir()
    for source in sources:
        shutil.copy2(source,out/'source'/source.name)
    assert before==fingerprint(sources)
    save(out/'manifest.json',{'status':'passed','checks':3,'hashes_before':before,
        'hashes_after':fingerprint(sources),'command':[sys.executable,*sys.argv]})
    print('3 additional graph diagnostics passed')


if __name__=='__main__':
    run(Path(sys.argv[1]))
