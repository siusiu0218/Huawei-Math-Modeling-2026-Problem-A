"""Retain initial timeouts and retry only generation-timeout items at 300 s."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/09_problem2/raw/problem_2/v009'


def main():
    failed = []
    for name in ('exp102_20260925_adaptive_full_a', 'exp103_20260925_adaptive_full_b'):
        d = json.loads((BASE / name / 'manifest.json').read_text(encoding='utf-8'))
        assert d['status'] in ('completed', 'partial') and d['protected_unchanged']
        for row in d['items']:
            if row['status'] != 'success':
                assert row['status'] == 'generate_timeout', row
                failed.append(row)
    path = ROOT / 'experiments/problem2_v009_recovery.json'
    if path.exists():
        raise FileExistsError('Recovery already registered; inspect its records before continuing')
    names = [f'exp{104+i:03}_20260925_adaptive_recovery' for i in range(len(failed))]
    record = {'version': 'v009', 'reason': 'Initial generation exceeded 60 seconds; retain failures and measure at 300 seconds.',
              'generation_timeout': 300, 'evaluation_timeout': 180, 'max_workers': 1,
              'experiments': names, 'initial_failures': failed, 'status': 'planned'}
    path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    codes = []
    for row, name in zip(failed, names):
        codes.append(subprocess.call([sys.executable, '-B', str(ROOT / 'experiments/run_problem2.py'),
             '--algorithm', 'adaptive', '--experiment', name, '--cases', row['case'],
             '--cores', str(row['cores']), '--generation-timeout', '300', '--evaluation-timeout', '180']))
    record.update(status='completed' if not any(codes) else 'partial', exit_codes=codes)
    path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return int(any(codes))


if __name__ == '__main__':
    raise SystemExit(main())
