"""Run frozen scene-B full evaluation in non-overwriting batches."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
SOLUTION = Path(__file__).resolve().parents[1]
WORKSPACE = SOLUTION.parent.parent
sys.path.insert(0, str(SOLUTION / 'experiments'))
from result_paths import result_path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)


def verify(frozen):
    for relative, expected in frozen.items():
        if digest(WORKSPACE / relative) != expected:
            raise ValueError(f'frozen file changed: {relative}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    freeze = read(SOLUTION / 'experiments/problem2_v007_selection.json')
    verify(freeze['hashes'])
    cases = sorted((SOLUTION.parent / 'data').glob('case_*.json'))
    if len(cases) != 100:
        raise ValueError('expected exactly 100 case files')
    out = result_path('problem_2/v007/full_suite_20260925')
    progress = out / 'progress.json'
    if args.resume:
        state = read(progress)
        if state['driver_sha256'] != digest(Path(__file__)):
            raise ValueError('driver changed; cannot resume this suite')
        verify(state['frozen_hashes'])
    else:
        out.mkdir(parents=True,exist_ok=False)
        frozen = dict(freeze['hashes'])
        frozen.update({str(p.relative_to(WORKSPACE)):digest(p) for p in cases})
        batches = []
        for algorithm, version, first, cores in [
            ('paired_order','v007',66,[2,3,4,5]),
            ('regions_b','v002',76,[2,3,4,5]),
            ('single','single_v001',86,[1]),
        ]:
            for i in range(10):
                batches.append({'algorithm':algorithm,'version':version,
                                'experiment':f'exp{first+i:03}_20260925_full_{algorithm}_{i+1:02}',
                                'cases':[p.stem for p in cases[i*10:(i+1)*10]],
                                'cores':cores,'status':'pending'})
        state = {'problem':2,'selected_version':'v007','status':'running',
                 'started_utc':datetime.now(timezone.utc).isoformat(),
                 'driver_sha256':digest(Path(__file__)), 'frozen_hashes':frozen,
                 'parameters':{'generation_timeout':30,'evaluation_timeout':180,
                               'candidates_per_method':1,'automatic_retries':0},
                 'batches':batches}
        (out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
        save(progress,state)
    try:
        for batch in state['batches']:
            verify(state['frozen_hashes'])
            folder = result_path(Path('problem_2')/batch['version']/batch['experiment'])
            if batch['status'] in ('completed','partial'):
                m=read(folder/'manifest.json')
                if m['status']!=batch['status'] or not m['protected_unchanged']:
                    raise ValueError('saved batch state differs')
                continue
            if folder.exists():
                raise ValueError(f'partial directory requires separate recovery experiment: {folder}')
            batch['status']='running'
            state['status']='running'
            save(progress,state)
            print('BATCH',batch['experiment'],flush=True)
            command=[sys.executable,'-B',str(SOLUTION/'experiments/run_problem2.py'),
                     '--experiment',batch['experiment'],'--algorithm',batch['algorithm'],
                     '--cases',*batch['cases'],'--cores',*map(str,batch['cores']),
                     '--generation-timeout','30','--evaluation-timeout','180']
            process=subprocess.run(command,cwd=WORKSPACE,check=False)
            manifest=read(folder/'manifest.json')
            batch['returncode']=process.returncode
            batch['status']=manifest['status']
            batch['success_count']=sum(r['status']=='success' for r in manifest['items'])
            batch['total_count']=len(manifest['items'])
            save(progress,state)
            if manifest['status'] not in ('completed','partial') or not manifest['protected_unchanged']:
                raise ValueError('batch did not finish with stable materials')
        verify(state['frozen_hashes'])
        state['status']='completed' if all(b['status']=='completed' for b in state['batches']) else 'partial'
    except BaseException:
        state['status']='interrupted'
        raise
    finally:
        state['updated_utc']=datetime.now(timezone.utc).isoformat()
        save(progress,state)
    return 0 if state['status']=='completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
