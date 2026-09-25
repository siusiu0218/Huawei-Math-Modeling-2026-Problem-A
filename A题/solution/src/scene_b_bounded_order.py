"""Q3 v003: bound independent component interleaving, preserving placement.

Within each dependency component retain the original subgraph order. Components
spanning cores disable this transformation, so no new cross-core order is added.
Width one is the targeted locality candidate; width two is a budget-matched
pipeline-overlap control. Both are compared to the archived baseline.
"""
from copy import deepcopy
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order

VERSION = 'v003'


def reorder(data, base, width=1):
    if type(width) is not int or width < 1:
        raise ValueError('width must be a positive integer')
    view = derive_multicore_plan(data, base)
    groups = view['subgraph_ids']
    parents = {g: g for g in groups}

    def root(g):
        while parents[g] != g:
            parents[g] = parents[parents[g]]
            g = parents[g]
        return g

    for g in groups:
        for h in view['subgraph_preds'][g]:
            parents[root(h)] = root(g)
    component_cores = {}
    for g in groups:
        component_cores.setdefault(root(g), set()).add(view['core_by_subgraph'][g])
    if any(len(cores) > 1 for cores in component_cores.values()):
        return deepcopy(base)
    orders = []
    for old in base['core_schedules']:
        sequences = {}
        for g in old:
            sequences.setdefault(root(g), []).append(g)
        sequences = list(sequences.values())
        order = []
        for start in range(0, len(sequences), width):
            batch = sequences[start:start + width]
            for depth in range(max(map(len, batch))):
                order.extend(seq[depth] for seq in batch if depth < len(seq))
        orders.append(order)
    result = deepcopy(base)
    result['core_schedules'] = orders
    validate_task_order(derive_multicore_plan(data, result))
    assert result['node_to_subgraph'] == base['node_to_subgraph']
    assert all(set(a) == set(b) for a, b in zip(orders, base['core_schedules']))
    return result
