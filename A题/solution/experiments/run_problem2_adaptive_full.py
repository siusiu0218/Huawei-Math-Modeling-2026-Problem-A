"""Two independent sequential workers for frozen Q2 v009, 100 graphs x 4 cores."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/09_problem2/raw/problem_2/v009'
BATCHES = [('exp102_20260925_adaptive_full_a', 1, 50),
           ('exp103_20260925_adaptive_full_b', 51, 100)]


def main():
    frozen = json.loads((ROOT / 'experiments/problem2_v009_selection.json').read_text(encoding='utf-8'))
    for path, expected in frozen['source_hashes'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
    for name, _, _ in BATCHES:
        if (BASE / name).exists():
            raise FileExistsError(f'existing batch must not be overwritten: {name}')
    driver = BASE / 'full_driver_20260925'
    driver.mkdir(parents=True, exist_ok=False)
    processes, streams = [], []
    try:
        for name, first, last in BATCHES:
            command = [sys.executable, '-B', str(ROOT / 'experiments/run_problem2.py'),
                       '--algorithm', 'adaptive', '--experiment', name, '--cases',
                       *[f'case_{i:03}' for i in range(first, last + 1)], '--cores', '2', '3', '4', '5',
                       '--generation-timeout', '60', '--evaluation-timeout', '180']
            stream = (driver / f'{name}.log').open('w', encoding='utf-8')
            streams.append(stream)
            processes.append(subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT))
        (driver / 'driver.json').write_text(json.dumps({'max_workers': 2, 'pids': [p.pid for p in processes],
            'batches': [b[0] for b in BATCHES], 'generation_timeout': 60, 'evaluation_timeout': 180,
            'timing_note': 'Two workers may contend for resources; timings are not equal-budget speed comparisons.'}, indent=2), encoding='utf-8')
        previous = None
        while any(p.poll() is None for p in processes):
            state = []
            for name, _, _ in BATCHES:
                path = BASE / name / 'manifest.json'
                if path.exists():
                    d = json.loads(path.read_text(encoding='utf-8'))
                    rows = d['items']
                    state.append((name, sum(r['status'] == 'success' for r in rows),
                                  sum(r['status'] not in ('success', 'running') for r in rows), d['status']))
            if state != previous:
                print(state, flush=True); previous = state
            time.sleep(5)
        codes = [p.wait() for p in processes]
        print('exit_codes', codes, flush=True)
        return int(any(c != 0 for c in codes))
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
        for stream in streams:
            stream.close()


if __name__ == '__main__':
    raise SystemExit(main())
