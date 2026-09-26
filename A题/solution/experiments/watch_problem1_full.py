"""Read-only live display of Q1 exp137 checkpoint files; never starts evaluation."""
import argparse
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1] / 'outputs/09_future/raw/problem_1/v012/exp137_20260926_structural_full'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def display(clear=True):
    manifest = read(ROOT / 'manifest.json')
    records = []
    for path in (ROOT / 'runs').glob('*/*/status.json'):
        try:
            records.append((path.stat().st_mtime, read(path)))
        except (OSError, ValueError):
            continue
    counts = Counter(r['status'] for _, r in records)
    total = manifest['candidate_slots']
    finished = sum(n for status, n in counts.items() if status != 'running')
    if clear:
        os.system('cls' if os.name == 'nt' else 'clear')
    print('Q1 v012 - LIVE PROGRESS (read-only)', flush=True)
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ' Refresh: 5s | Ctrl+C closes viewer only')
    print(f"Experiment: {manifest['experiment']} | {manifest['status']}")
    print(f'Finished: {finished}/{total} ({finished/total:.1%}) | Success: {counts["success"]} | Failed/timeout: {finished-counts["success"]}')
    print('\nACTIVE:')
    active = [r for _, r in records if r['status'] == 'running']
    for r in active:
        print(f"  {r['case']}  cores={r['cores']}  candidate={r['candidate']}")
    if not active:
        print('  No running checkpoint at this instant.')
    print('\nLATEST CHECKPOINTS:')
    for stamp, r in sorted(records, key=lambda item: item[0], reverse=True)[:12]:
        print(f"  {datetime.fromtimestamp(stamp):%H:%M:%S}  {r['case']}  n{r['cores']}  {r['candidate']}  {r['status']:<20} makespan={r.get('makespan', '-')}" )
    print('\nSTATUS COUNTS:', dict(counts))
    print('This viewer reads checkpoint files, not process stdout.')
    print('If timestamps stop changing, that alone does not prove the evaluator is still alive.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    try:
        while True:
            display(clear=not args.once)
            if args.once:
                break
            time.sleep(5)
    except KeyboardInterrupt:
        print('\nViewer closed. Evaluation was not stopped.')
