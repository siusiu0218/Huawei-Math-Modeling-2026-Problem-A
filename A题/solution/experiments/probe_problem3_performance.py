"""Real-evaluator differential performance check; exit 1 on candidate regression."""
import argparse
import json
import sys
from pathlib import Path
from run_problem2 import save
from run_problem3_pair import fingerprint

SOLUTION=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOLUTION.parent/'code'))
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_3 import evaluate_problem_3,read_cache_config,read_scene_b_config


def main():
    p=argparse.ArgumentParser();p.add_argument('--graph',required=True);p.add_argument('--baseline',required=True)
    p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);args=p.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    paths=[Path(args.graph),Path(args.baseline),Path(args.candidate),SOLUTION.parent/'data/config.txt']
    paths+=list((SOLUTION.parent/'code').glob('*.py'))+[Path(__file__)]
    before=fingerprint(paths)
    cfg=read_evaluation_config(paths[3]);cache=read_cache_config(paths[3]);delay=read_scene_b_config(paths[3])['cross_core_copy_delay_cycles']
    graph=json.loads(Path(args.graph).read_text(encoding='utf-8'));values={}
    for name,path in [('baseline',args.baseline),('candidate',args.candidate)]:
        result=evaluate_problem_3(graph,json.loads(Path(path).read_text(encoding='utf-8')),
            cfg['bandwidth'],cfg['capacity'],delay,cache['cache_capacity_bytes'],cache['cache_bandwidth_bytes_per_cycle'])
        save(out/f'{name}.json',result);values[name]=result['makespan']
    assert before==fingerprint(paths)
    passed=values['candidate']<=values['baseline']
    save(out/'verdict.json',{'passed':passed,**values,'hashes_before':before,'hashes_after':fingerprint(paths),
        'command':[sys.executable,*sys.argv]})
    print(json.dumps({'passed':passed,**values}),flush=True)
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':main()
