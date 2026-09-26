"""Frozen Q1 v012 follow-up on all 17 remaining low-speedup five-core cases.

Only the runner and case set change. The exp133 algorithm and all settings are
hash-checked before preparation and execution; no result-dependent retuning.
"""
import argparse
import csv
from pathlib import Path
import shutil
import sys
import time

from run_problem1_structural_ablation import (
    A_ROOT,SOLUTION,ROOT as DEVELOPMENT,PREVIOUS,read,save,sha,
    signature,verify_frozen,run_command,validate_result,make_candidate,SETTINGS,
)
from result_paths import experiment_path

VERSION='v012'
EXPERIMENT='exp134_20260926_structural_transfer'
ROOT=experiment_path(VERSION,EXPERIMENT)


def prepare():
    development=read(DEVELOPMENT/'manifest.json')
    assert development['status']=='completed'
    verify_frozen(development)
    old=read(PREVIOUS/'manifest.json')
    for p,h in old['protected_hashes'].items():
        if sha(A_ROOT/p)!=h: raise ValueError('original code/config/input changed: '+p)
    original_csv=SOLUTION/'outputs/08_full/multicore_comparison.csv'
    rows=list(csv.DictReader(original_csv.open(encoding='utf-8-sig')))
    low={r['case']:r for r in rows if r['cores']=='5' and float(r['speedup'])<2}
    cases=sorted(set(low)-set(development['cases']))
    assert len(low)==23 and len(cases)==17 and not set(cases)&set(development['cases'])
    ROOT.mkdir(parents=True,exist_ok=False)
    for name in ('source','references','runs','selected'): (ROOT/name).mkdir()
    references=[]
    for case in cases:
        row=low[case]
        plan=PREVIOUS/'baseline'/f'{case}_plan.json';result=PREVIOUS/'baseline'/f'{case}_result.json'
        assert sha(plan)==row['selected_plan_sha256']
        assert sha(result)==row['selected_result_sha256']
        scored=read(result)
        assert validate_result(scored,5)['makespan']==int(row['makespan'])
        for source in (plan,result): shutil.copy2(source,ROOT/'references'/source.name)
        references.append({'case':case,'single_makespan':int(row['single_makespan']),'baseline_makespan':int(row['makespan']),
            'baseline_plan_source':str(plan),'baseline_result_source':str(result),
            'plan_sha256':sha(plan),'result_sha256':sha(result),'baseline_experiment':row['experiment']})
    files=list((A_ROOT/'code').glob('*.py'))+[A_ROOT/'data/config.txt']+[A_ROOT/f'data/{c}.json' for c in cases]
    files+=list((SOLUTION/'src').glob('*.py'))+list((SOLUTION/'src').glob('*.LICENSE'))
    files+=[Path(__file__)]+[SOLUTION/'experiments'/n for n in ('run_problem1_structural_ablation.py','process_runner.py','result_paths.py','probe_problem1_critical_local.py')]
    files+=[original_csv,SOLUTION/'tests/test_scene_a_structural_ablation.py',SOLUTION/'tests/test_branches.py']
    files+=list((ROOT/'references').glob('*.json'))
    frozen={str(p.relative_to(A_ROOT)):sha(p) for p in files}
    for path in files:
        if ROOT in path.parents: continue
        target=ROOT/'source'/path.relative_to(A_ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    # All imported algorithm files must be byte-identical to the development freeze.
    algorithm_hashes={p:h for p,h in development['frozen_files'].items() if Path(p).parts[:2]==('solution','src')}
    assert algorithm_hashes and all(sha(A_ROOT/p)==h for p,h in algorithm_hashes.items())
    manifest={'problem':1,'algorithm_version':VERSION,'experiment':EXPERIMENT,'status':'prepared','cases':cases,'cores':[5],
        'excluded_development_cases':development['cases'],'arms':{'B':'fixed old partition; global placement and ordering',
            'C':'frozen structural regrouping; same global placement and ordering'},
        'settings':development['settings'],'structure_policy':development['structure_policy'],
        'candidate_slots':136,'slots_per_arm_per_case':4,'generation_timeout_seconds':30,'evaluation_timeout_seconds':180,
        'random_seed':None,'retries':0,'frozen_files':frozen,'algorithm_hashes_from_exp133':algorithm_hashes,
        'references':references,'source_development':str(DEVELOPMENT),
        'selection_scope':'all 17 remaining baseline-speedup<2 cases after excluding six v012 development cases; baseline diagnosis already seen, not wholly unseen data',
        'command':[sys.executable,'-B',str(Path(__file__)),'--run'],
        'evaluation_rule':'keep baseline; evaluate four B and four C settings; exact plan deduplication; no retuning or retries',
        'reused_cost_boundary':'baseline v009 generation/search and earlier diagnosis costs are excluded; source hashes verified'}
    save(ROOT/'manifest.json',manifest)
    (ROOT/'PROTOCOL.md').write_text('''# 第一问 v012 冻结后续检验

范围：原100图五核成绩低于2倍的23图，排除exp133的六张开发图，剩余17图全部纳入，不挑图。旧基线诊断已看过，因此称后续检验，不称完全未见数据独立验证。

方法：v012算法源码及参数与exp133字节一致，不因后续成绩调整。共同参照为原v009。B固定切分、全局重新分核和排序；C沿用计算集中型全图深度窗口10、搬运型最多四消费者共享张量合并、其余关键链四任务凸分组，再用相同调度器。仍保留搬运型潜在退化，不悄悄删除负候选。

预算：每图B/C各四个rank/work×跨核等待估计1/2设置，共136逻辑槽；每候选生成30秒、原评估器评估180秒，不重试。完全相同方案去重，记录实际独立方案和新增评估数。原评估config始终不变。失败、超时、非法候选均列入结果。

报告：各组直接最优、各组保留基线最优、合并择优，按图配对C/B和分结构路线汇总；报告Makespan、加速比、搬运、spill、内存、生成及评估成本。预先以逐图Makespan下降>=1%作为有实际幅度改善的描述门槛，不把任意1-cycle变化包装为明显收益。是否值得全量根据覆盖、幅度、退化和成本共同判断，不预设必须通过。

只授权这17图五核后续检验，结束后审计并报告；不自动重跑100图2～5核全量，不更新正式v009均值。
''',encoding='utf-8')
    print({'root':str(ROOT),'cases':cases,'slots':136},flush=True)


def generate(case,arm,index):
    folder=ROOT/'runs'/case/f'{arm}{index}'
    started=time.perf_counter()
    plan,metadata=make_candidate(read(A_ROOT/f'data/{case}.json'),read(ROOT/'references'/f'{case}_plan.json'),
        read(ROOT/'references'/f'{case}_result.json'),arm,index)
    save(folder/'plan.json',plan);save(folder/'generation.json',{'seconds':time.perf_counter()-started,**metadata})


def run():
    manifest=read(ROOT/'manifest.json')
    if manifest['status']!='prepared': raise ValueError('do not restart or overwrite an existing experiment')
    verify_frozen(manifest)
    manifest['status']='running';save(ROOT/'manifest.json',manifest)
    started=time.perf_counter();rows=[]
    try:
        for ref in manifest['references']:
            case=ref['case'];(ROOT/'runs'/case).mkdir()
            base_plan=ROOT/'references'/f'{case}_plan.json';base_result=ROOT/'references'/f'{case}_result.json'
            cache={signature(read(base_plan)):{'result_path':str(base_result),'result_sha256':sha(base_result),'source':'baseline'}}
            for arm in ('B','C'):
                for index in range(4):
                    name=f'{arm}{index}';folder=ROOT/'runs'/case/name;folder.mkdir()
                    row={'problem':1,'algorithm_version':VERSION,'experiment':EXPERIMENT,'case':case,'cores':5,
                        'arm':arm,'setting_index':index,'candidate':name,'status':'pending','generation_seconds':0.,'evaluation_seconds':0.,
                        'evaluation_reused':False,'makespan':None}
                    generated=run_command([sys.executable,'-B',str(Path(__file__)),'--generate',case,arm,str(index)],folder/'generation.log',30)
                    save(folder/'generation_process.json',generated);row['generation_seconds']=generated['seconds']
                    if generated['status']!='success': row['status']='generation_'+generated['status']
                    else:
                        plan=read(folder/'plan.json');sig=signature(plan)
                        row.update(plan_sha256=sha(folder/'plan.json'),signature=sig)
                        row['generation_metadata']=read(folder/'generation.json')
                        if sig in cache:
                            cached=cache[sig];assert sha(Path(cached['result_path']))==cached['result_sha256']
                            row.update(status='success',evaluation_reused=True,result_path=cached['result_path'],
                                result_sha256=cached['result_sha256'],reuse_source=cached['source'])
                        else:
                            command=[sys.executable,'-B',str(A_ROOT/'code/multicore_cut_evaluate_problem_1.py'),str(A_ROOT/f'data/{case}.json'),str(folder/'plan.json'),
                                '--config',str(A_ROOT/'data/config.txt'),'-o',str(folder/'result.json'),'--trace-output',str(folder/'trace.json'),'--log-output',str(folder/'evaluation.log')]
                            outcome=run_command(command,folder/'evaluation_process.log',180);save(folder/'evaluation_process.json',outcome)
                            row.update(status=outcome['status'],evaluation_seconds=outcome['seconds'])
                            if outcome['status']=='success':
                                row.update(result_path=str(folder/'result.json'),result_sha256=sha(folder/'result.json'))
                                cache[sig]={'result_path':row['result_path'],'result_sha256':row['result_sha256'],'source':name}
                        if row['status']=='success': row.update(validate_result(read(Path(row['result_path'])),5))
                    rows.append(row);save(folder/'status.json',row);save(ROOT/'candidates.json',rows)
                    print(case,name,row['status'],row['makespan'],'reused' if row['evaluation_reused'] else '',flush=True)
        manifest['status']='completed' if all(r['status']=='success' for r in rows) else 'completed_with_failures'
    except BaseException as exc:
        manifest['status']='interrupted_or_failed';manifest['error']=repr(exc);raise
    finally:
        manifest['wall_seconds']=time.perf_counter()-started
        manifest['frozen_unchanged']=all(sha(A_ROOT/p)==h for p,h in manifest['frozen_files'].items())
        save(ROOT/'manifest.json',manifest)


if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',action='store_true');group.add_argument('--run',action='store_true');group.add_argument('--generate',nargs=3)
    args=parser.parse_args()
    if args.prepare:prepare()
    elif args.run:run()
    else:generate(args.generate[0],args.generate[1],int(args.generate[2]))
