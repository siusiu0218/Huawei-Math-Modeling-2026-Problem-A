"""Q2 v010: fixed v007/v009 candidates, selected by actual scene-B makespan."""
import hashlib
import json
import math

VERSION = 'v010'
CANDIDATES = ('v007', 'v009')


def plan_digest(plan):
    """Dictionary order is irrelevant; core and operation order is preserved."""
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def choose_candidate(rows):
    if len(rows) != 2 or {r['candidate'] for r in rows} != set(CANDIDATES):
        raise ValueError('one row per fixed candidate is required')
    valid = [r for r in rows if r['status'] == 'success']
    for row in valid:
        value = row['makespan']
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
            raise ValueError('invalid makespan')
    return min(valid, key=lambda r: (r['makespan'], CANDIDATES.index(r['candidate']))) if valid else None
