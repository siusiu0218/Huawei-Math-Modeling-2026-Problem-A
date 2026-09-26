"""Frozen six-case Q1 v012 ablation: 3 arms x 4 paired settings, max 72 scores."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

from probe_problem1_critical_local import A_ROOT,SOLUTION,ROOT as PREVIOUS,read,save,sha
from process_runner import run_command
from result_paths import experiment_path
from portfolio_scheduler import validate_result
from scene_a_structural_ablation import make_candidate,SETTINGS

VERSION='v012'
EXPERIMENT='exp133_20260926_structural_ablation'
ROOT=experiment_path(VERSION,EXPERIMENT)


def signature(plan):
    return hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify_frozen(manifest):
    for path,digest in manifest['frozen_files'].items():
        if sha(A_ROOT/path)!=digest: raise ValueError('frozen file changed: '+path)


def prepare():
    ROOT.mkdir(parents=True,exist_ok=False)
    for name in ('source','references','runs','selected'): (ROOT/name).mkdir()
    old=read(PREVIOUS/'manifest.json')
    cases=[s['case'] for s in old['selected']]
    assert len(cases)==6
    # Confirm current official code/config/inputs match the just-audited pilot.
    for path,digest in old['protected_hashes'].items():
        if sha(A_ROOT/path)!=digest: raise ValueError('pilot protected input changed: '+path)
    prior=list(csv.DictReader((SOLUTION/'outputs/11_problem1_local_pilot/comparison.csv').open(encoding='utf-8-sig')))
    baseline_rows=list(csv.DictReader((SOLUTION/'outputs/08_full/multicore_comparison.csv').open(encoding='utf-8-sig')))
    refs=[]
    for case in cases:
        plan_path=PREVIOUS/'baseline'/f'{case}_plan.json'
        result_path=PREVIOUS/'runs'/case/'baseline/result.json'
        evaluation=read(PREVIOUS/'runs'/case/'baseline/evaluation.json')
        assert sha(plan_path)==evaluation['plan_sha256'] and sha(result_path)==evaluation['result_sha256']
        plan_copy=ROOT/'references'/f'{case}_plan.json';result_copy=ROOT/'references'/f'{case}_result.json'
        shutil.copy2(plan_path,plan_copy);shutil.copy2(result_path,result_copy)
        row=next(r for r in baseline_rows if r['case']==case and r['cores']=='5')
        prior_row=next(r for r in prior if r['case']==case)
        previous_best_plan=SOLUTION/'outputs/11_problem1_local_pilot/plans'/f'{case}_n5.json'
        audit=read(SOLUTION/'outputs/11_problem1_local_pilot/audit.json')
        assert next(r for r in audit['selected'] if r['case']==case)['makespan']==int(prior_row['makespan'])
        # Check previous-best plan against its original successful evaluation.
        if prior_row['candidate']=='baseline': origin=PREVIOUS/'runs'/case/'baseline'
        elif prior_row['algorithm_version']=='v011': origin=experiment_path('v011','exp132_20260926_critical_neighbour_merge')/case/prior_row['candidate']
        else: origin=PREVIOUS/'runs'/case/prior_row['candidate']
        prior_evaluation=read(origin/'evaluation.json')
        assert sha(previous_best_plan)==prior_evaluation['plan_sha256']
        assert sha(origin/'result.json')==prior_evaluation['result_sha256']
        shutil.copy2(previous_best_plan,ROOT/'references'/f'{case}_previous_best_plan.json')
        shutil.copy2(origin/'result.json',ROOT/'references'/f'{case}_previous_best_result.json')
        refs.append({'case':case,'single_makespan':int(row['single_makespan']),'baseline_makespan':evaluation['makespan'],
            'previous_best_makespan':int(prior_row['makespan']),'baseline_plan_source':str(plan_path),'baseline_result_source':str(result_path),
            'plan_sha256':sha(plan_copy),'result_sha256':sha(result_copy),
            'previous_best_plan_sha256':sha(previous_best_plan),'previous_best_result_sha256':sha(origin/'result.json')})
    files=list((A_ROOT/'code').glob('*.py'))+[A_ROOT/'data/config.txt']+[A_ROOT/f'data/{c}.json' for c in cases]
    files+=list((SOLUTION/'src').glob('*.py'))+list((SOLUTION/'src').glob('*.LICENSE'))
    files+=[Path(__file__)]+[SOLUTION/'experiments'/n for n in ('process_runner.py','result_paths.py','probe_problem1_critical_local.py')]
    files+=[SOLUTION/'tests/test_scene_a_structural_ablation.py',SOLUTION/'tests/test_branches.py']
    files+=list((ROOT/'references').glob('*.json'))
    frozen={str(p.relative_to(A_ROOT)):sha(p) for p in files}
    for p in files:
        if ROOT in p.parents: continue
        target=ROOT/'source'/p.relative_to(A_ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    manifest={'problem':1,'algorithm_version':VERSION,'experiment':EXPERIMENT,'status':'prepared','cases':cases,'cores':[5],
        'arms':{'A':'fixed partition, fixed cores, global ordering','B':'fixed partition, global placement and ordering',
                'C':'structural regrouping, same global placement and ordering'},
        'settings':[{'priority':p,'cross_wait_proxy_multiplier':m} for p,m in SETTINGS],
        'structure_policy':{'compute_route':'largest chain task fraction >=0.6 and compute-only >=0.5: full graph depth-window components width 10',
            'transfer_route':'otherwise transfer-only >=0.5: up to four consumers per group; top 32 shared tensors; positive tensor-boundary saving and convexity',
            'remaining_route':'critical-chain blocks of four, convex closure <=12 tasks and work <=2*total/cores'},
        'selection_scope':'same six development graphs, post-pilot hypotheses; no unseen generalization claim',
        'candidate_slots':72,'slots_per_arm_per_case':4,'generation_timeout_seconds':30,'evaluation_timeout_seconds':180,
        'random_seed':None,'retries':0,'references':refs,'frozen_files':frozen,
        'command':[sys.executable,'-B',str(Path(__file__)),'--run'],
        'reused_cost_boundary':'previous v009 and pilot reference search/evaluation costs are not included in this run'}
    save(ROOT/'manifest.json',manifest)
    (ROOT/'PROTOCOL.md').write_text('''# 第一问三组对照冻结方案

六张开发图，五核。A固定切分与分核，只改顺序；B固定切分，改分核与顺序；C按结构特征成组重切分，再用与B完全相同的调度器。每组使用rank/work优先级×1/2倍跨核等待估计的四种设置。实际评估配置从不修改。

所有组用同一静态任务耗时代理：最大单管线计算工作量+按张量及任务去重的边界搬运量/带宽。代理不代表实测耗时，不含spill，不因保留旧切分就使用旧实测任务耗时。

C组每图仅一个预先确定的结构变换，四个设置共享该切分。计算集中型采用全图深度窗口10+窗口内弱连通分量，复用已有MIT归属的窗口实现；搬运型按共享张量正节约合并至多四个消费者任务，保留凸性；其余按关键链四任务成组、加入凸闭包，限制组工作量和节点数。没有按用例编号策略。

每图每组最多四个逻辑候选，共72槽位。完全相同方案按哈希去重并保留每槽来源，不凑足重复评估。每候选生成30秒、评估180秒，不重试；失败、非法、超时均保留。旧正式方案为共同基线，上一轮最好方案为额外参照，不混入各组直接候选最优。每组分别报告直接结果与保留共同基线后的结果。

以Makespan判断收益，同报新增搬运、spill、内存峰值、生成/评估时间。比较A对基线、B对A、C对B，但只描述这些固定候选策略与预算；旧组不同分核会改变最优排序，不能声称普适因果分解。C在相同设置下优于B，才有配对的重切分增益证据。

数据已用于开发。此轮只做六图诊断性对照，不自动扩至其余17图或100图全量。完成后核验全部方案、哈希、分组约束、选择、参数及原材料未改，再更新上下文。
''',encoding='utf-8')
    print(str(ROOT),flush=True)


def generate(case,arm,index):
    folder=ROOT/'runs'/case/f'{arm}{index}'
    started=time.perf_counter()
    plan,metadata=make_candidate(read(A_ROOT/f'data/{case}.json'),read(ROOT/'references'/f'{case}_plan.json'),
        read(ROOT/'references'/f'{case}_result.json'),arm,index)
    save(folder/'plan.json',plan)
    save(folder/'generation.json',{'seconds':time.perf_counter()-started,**metadata})


def run():
    manifest=read(ROOT/'manifest.json')
    if manifest['status']!='prepared': raise ValueError('existing experiment cannot be restarted or overwritten')
    verify_frozen(manifest)
    manifest['status']='running';save(ROOT/'manifest.json',manifest)
    start=time.perf_counter();rows=[]
    try:
        for ref in manifest['references']:
            case=ref['case'];(ROOT/'runs'/case).mkdir()
            base_plan=ROOT/'references'/f'{case}_plan.json';base_result=ROOT/'references'/f'{case}_result.json'
            cache={signature(read(base_plan)):{'result_path':str(base_result),'result_sha256':sha(base_result),'source':'baseline'}}
            for arm in ('A','B','C'):
                for index in range(4):
                    name=f'{arm}{index}';folder=ROOT/'runs'/case/name;folder.mkdir()
                    row={'problem':1,'algorithm_version':VERSION,'experiment':EXPERIMENT,'case':case,'cores':5,
                        'arm':arm,'setting_index':index,'candidate':name,'status':'pending','generation_seconds':0.,'evaluation_seconds':0.,
                        'evaluation_reused':False,'makespan':None}
                    gen=run_command([sys.executable,'-B',str(Path(__file__)),'--generate',case,arm,str(index)],folder/'generation.log',30)
                    save(folder/'generation_process.json',gen);row['generation_seconds']=gen['seconds']
                    if gen['status']!='success': row.update(status='generation_'+gen['status'])
                    else:
                        plan=read(folder/'plan.json');sig=signature(plan)
                        row['plan_sha256']=sha(folder/'plan.json');row['signature']=sig
                        if sig in cache:
                            cached=cache[sig]
                            assert sha(Path(cached['result_path']))==cached['result_sha256']
                            row.update(status='success',evaluation_reused=True,result_path=cached['result_path'],
                                       result_sha256=cached['result_sha256'],reuse_source=cached['source'])
                        else:
                            command=[sys.executable,'-B',str(A_ROOT/'code/multicore_cut_evaluate_problem_1.py'),str(A_ROOT/f'data/{case}.json'),str(folder/'plan.json'),
                                '--config',str(A_ROOT/'data/config.txt'),'-o',str(folder/'result.json'),'--trace-output',str(folder/'trace.json'),'--log-output',str(folder/'evaluation.log')]
                            evaluated=run_command(command,folder/'evaluation_process.log',180)
                            save(folder/'evaluation_process.json',evaluated)
                            row.update(status=evaluated['status'],evaluation_seconds=evaluated['seconds'])
                            if evaluated['status']=='success':
                                row.update(result_path=str(folder/'result.json'),result_sha256=sha(folder/'result.json'))
                                cache[sig]={'result_path':row['result_path'],'result_sha256':row['result_sha256'],'source':name}
                        if row['status']=='success':
                            row.update(validate_result(read(Path(row['result_path'])),5))
                            row['generation_metadata']=read(folder/'generation.json')
                    rows.append(row);save(folder/'status.json',row);save(ROOT/'candidates.json',rows)
                    print(case,name,row['status'],row['makespan'],'reused' if row['evaluation_reused'] else '',flush=True)
        manifest['status']='completed' if all(r['status']=='success' for r in rows) else 'completed_with_failures'
    except BaseException as exc:
        manifest['status']='interrupted_or_failed';manifest['error']=repr(exc);raise
    finally:
        manifest['wall_seconds']=time.perf_counter()-start
        manifest['frozen_unchanged']=all(sha(A_ROOT/p)==h for p,h in manifest['frozen_files'].items())
        save(ROOT/'manifest.json',manifest)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',action='store_true');group.add_argument('--run',action='store_true');group.add_argument('--generate',nargs=3)
    args=parser.parse_args()
    if args.prepare:prepare()
    elif args.run:run()
    else:generate(args.generate[0],args.generate[1],int(args.generate[2]))
