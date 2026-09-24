"""Bounded timing/stack probe on independent evaluator and input copies."""
import argparse
import faulthandler
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True


def child(folder):
    sys.path.insert(0, str(folder / 'code'))
    import multicore_cut_evaluate_problem_1 as engine
    import singlecore_evaluate
    faulthandler.dump_traceback_later(8, repeat=True)
    def timed(name, original):
        def call(*args, **kwargs):
            start = time.perf_counter()
            print(f'[stage] {name} start', flush=True)
            result = original(*args, **kwargs)
            print(f'[stage] {name} end seconds={time.perf_counter()-start:.6f}', flush=True)
            return result
        return call
    for name in ('step1_schedule', 'step2_spill_insertion', '_build_extended_graph', 'prepare_step3_execution'):
        setattr(engine, name, timed(name, getattr(engine, name)))
    try:
        return singlecore_evaluate.main([
            str(folder / 'graph.json'), '--config', str(folder / 'config.txt'),
            '-o', str(folder / 'exploratory_result.json'),
            '--trace-output', str(folder / 'trace.json'), '--log-output', str(folder / 'evaluation.log')])
    finally:
        faulthandler.cancel_dump_traceback_later()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--case', default='case_014')
    parser.add_argument('--timeout', type=int, default=45)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    folder = args.output.resolve()
    if args.child:
        return child(folder)
    root = next(p for p in Path(__file__).resolve().parents if (p / 'data/config.txt').exists())
    folder.mkdir(parents=True, exist_ok=False)
    shutil.copytree(root / 'code', folder / 'code', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(root / 'data' / f'{args.case}.json', folder / 'graph.json')
    shutil.copy2(root / 'data/config.txt', folder / 'config.txt')
    shutil.copy2(__file__, folder / 'probe.py')
    originals = [*sorted((root / 'code').glob('*.py')), root / 'data' / f'{args.case}.json', root / 'data/config.txt']
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
    command = [sys.executable, '-B', str(folder / 'probe.py'), '--child', '--output', str(folder)]
    start = time.perf_counter()
    with (folder / 'stacks.log').open('w', encoding='utf-8') as stream:
        try:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=args.timeout)
            status = 'completed' if result.returncode == 0 else 'failed'
        except subprocess.TimeoutExpired:
            status = 'timeout'
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
    record = {'case': args.case, 'kind': 'exploratory_diagnosis_not_official_score',
              'status': status, 'seconds': time.perf_counter()-start, 'timeout_seconds': args.timeout,
              'command': command, 'original_hashes': hashes, 'originals_unchanged': hashes == after}
    (folder / 'manifest.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    raise SystemExit(main())
