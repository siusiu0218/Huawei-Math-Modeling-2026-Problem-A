"""Q2 v011: actual-evaluation portfolio over active-core counts."""
from copy import deepcopy
import math

VERSION = 'v011'


def candidate_specs(n):
    if type(n) is not int or not 2 <= n <= 5:
        raise ValueError('target cores must be 2..5')
    return [('single', 1)] + [(v, k) for k in range(2, n + 1) for v in ('v007', 'v009')]


def pad_plan(plan, n):
    if type(n) is not int or not len(plan['core_schedules']) <= n <= 5:
        raise ValueError('cannot remove or exceed available cores')
    padded = deepcopy(plan)
    padded['core_schedules'].extend([] for _ in range(n - len(padded['core_schedules'])))
    return padded


def select_candidate(rows, n):
    expected = set(candidate_specs(n))
    if len(rows) != len(expected) or {(r['candidate'], r['active_budget']) for r in rows} != expected:
        raise ValueError('incomplete or duplicate candidate set')
    valid = [r for r in rows if r['status'] == 'success']
    for r in valid:
        t = r['makespan']
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t <= 0:
            raise ValueError('invalid makespan')
    # Prefer unchanged full-core baseline on ties, then higher active budget.
    return min(valid, key=lambda r: (r['makespan'], -r['active_budget'], r['candidate'] == 'v009')) if valid else None
