"""Q3 v004 prototype: depth-window components with predecessor affinity.

Adapted from bandcomp_partition (MIT), zhuangzhuangaiyutingya/
2026_match_model_A_openproject, commit 4bebdda48585cb751466b504e05865cb39673593.
Uses our existing contracted Graph and explicit deterministic tie breaks.
The upstream license is retained in scene_b_window_components.LICENSE.
This is a borrowed method candidate, not a claim of original invention.
"""
from collections import defaultdict
from graph_analysis import Graph
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

VERSION = 'v004'


def make_plan(data, num_cores, window=10, sticky=0.5):
    if type(num_cores) is not int or num_cores < 1 or type(window) is not int or window < 1:
        raise ValueError('num_cores and window must be positive integers')
    if not 0 <= sticky <= 1:
        raise ValueError('sticky must be between zero and one')
    graph = Graph(data)
    depth, bands = {}, defaultdict(list)
    pos = {op:i for i,op in enumerate(graph.order)}
    for op in graph.order:
        depth[op] = 1 + max((depth[p] for p in graph.preds[op]), default=-1)
        bands[depth[op]//window].append(op)
    mapping, assigned = {}, {}
    orders = [[] for _ in range(num_cores)]
    loads = [defaultdict(int) for _ in range(num_cores)]
    group_id = 0
    for band in sorted(bands):
        members, seen, components = set(bands[band]), set(), []
        for root in bands[band]:
            if root in seen:
                continue
            stack, group = [root], []
            seen.add(root)
            while stack:
                op = stack.pop()
                group.append(op)
                for other in sorted(graph.preds[op] | graph.succs[op]):
                    if other in members and other not in seen:
                        seen.add(other);stack.append(other)
            components.append(sorted(group,key=pos.get))
        components.sort(key=lambda group:(-sum(graph.ops[o]['cycles'] for o in group), pos[group[0]]))
        for group in components:
            affinity = defaultdict(int)
            for op in group:
                for parent in graph.preds[op]:
                    if parent in assigned:
                        affinity[assigned[parent]] += graph.ops[parent]['cycles']
            def score(core):
                load = max(loads[core].values(),default=0)
                return load-sticky*min(affinity[core],load),core
            core = min(range(num_cores),key=score)
            for op in group:
                mapping[str(op)] = group_id
                assigned[op] = core
                loads[core][graph.ops[op]['pipe']] += graph.ops[op]['cycles']
            orders[core].append(group_id)
            group_id += 1
    plan = {'node_to_subgraph':mapping,'core_schedules':orders}
    validate_task_order(derive_multicore_plan(data,plan))
    return plan
