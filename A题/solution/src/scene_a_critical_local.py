"""Q1 v010 exploratory local search guided by an observed task critical chain.

Task durations are measured under the baseline's shared bandwidth contention.
The reconstructed chain is explanatory, not a counterfactual lower bound.
Compute/transfer occupancy overlaps are kept separate; MTE is not all DDR.
"""
from collections import defaultdict
import heapq

from graph_analysis import Graph
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

VERSION = 'v010'


def occupancy(ops, start, end):
    events = defaultdict(lambda: [0, 0])
    events[start]; events[end]
    for op in ops:
        kind = 0 if op['pipe'] in ('PIPE_M', 'PIPE_V') else 1
        events[op['start']][kind] += 1
        events[op['end']][kind] -= 1
    active, previous = [0, 0], start
    totals = dict(compute_only=0, transfer_only=0, overlap=0, inactive=0)
    for t in sorted(events):
        label = ('overlap' if all(active) else 'compute_only' if active[0]
                 else 'transfer_only' if active[1] else 'inactive')
        totals[label] += t - previous
        active = [active[i] + events[t][i] for i in range(2)]
        previous = t
    assert sum(totals.values()) == end - start
    return totals


def diagnose(result):
    tasks, incoming, ops = {}, defaultdict(list), defaultdict(list)
    same = result['task_same_core_wait_cycles']
    cross = result['task_cross_core_wait_cycles']
    for core in result['per_core_timeline']:
        previous = None
        for t in core['tasks']:
            tid = t['task_id']
            tasks[tid] = {**t, 'core': core['core_id']}
            if previous is not None:
                incoming[tid].append((previous, same, 'same_core_order'))
            previous = tid
        for op in core['ops']:
            ops[op['task_id']].append(op)
    for e in result['task_dependencies']:
        a, b = e['source'], e['target']
        incoming[b].append((a, cross if tasks[a]['core'] != tasks[b]['core'] else 0,
                            'cross_core_dependency' if tasks[a]['core'] != tasks[b]['core'] else 'same_core_dependency'))
    parents = {}
    for tid, task in tasks.items():
        options = [(tasks[a]['end'] + delay, a, delay, kind) for a, delay, kind in incoming[tid]]
        best = max(options, default=(0, -1, 0, 'origin'))
        if abs(task['start'] - best[0]) > 1e-6:
            raise ValueError(f'unexplained task activation gap: {tid}')
        parents[tid] = best
        task['occupancy'] = occupancy(ops[tid], task['start'], task['end'])
        task['local_makespan'] = result['step3_by_task'][str(tid)]['local_makespan']
    current = max(tasks, key=lambda t: (tasks[t]['end'], -t))
    chain, edges = [], []
    while current != -1:
        chain.append(current)
        _, parent, delay, kind = parents[current]
        if parent != -1:
            edges.append({'source': parent, 'target': current, 'delay': delay, 'kind': kind})
        current = parent
    chain.reverse(); edges.reverse()
    totals = {k: sum(tasks[t]['occupancy'][k] for t in chain) for k in ('compute_only', 'transfer_only', 'overlap', 'inactive')}
    totals['cross_wait'] = sum(e['delay'] for e in edges if e['kind'] == 'cross_core_dependency')
    totals['same_wait'] = sum(e['delay'] for e in edges if e['kind'] == 'same_core_order')
    assert abs(sum(totals.values()) - result['makespan']) < 1e-6
    core_busy = [sum(t['duration'] for t in core['tasks']) for core in result['per_core_timeline']]
    return {'makespan': result['makespan'], 'chain': chain, 'edges': edges, 'chain_breakdown': totals,
            'tasks': tasks, 'core_task_busy': core_busy,
            'task_busy_fraction': sum(core_busy)/(result['num_cores']*result['makespan']),
            'largest_chain_task_fraction': max(tasks[t]['duration'] for t in chain)/result['makespan']}


def repack(graph, old_plan, result, mapping, mutable, pinned=None):
    """Change only selected tasks; preserve core and relative order of others.

Mutable tasks are inserted using a compute proxy. Baseline observed durations
are used for untouched tasks. A combined DAG catches cyclic local merges.
"""
    pinned = pinned or {}
    old_core = {t: c for c, order in enumerate(old_plan['core_schedules']) for t in order}
    old_tasks = {t['task_id']: t for c in result['per_core_timeline'] for t in c['tasks']}
    groups = defaultdict(list)
    for n, t in mapping.items(): groups[t].append(n)
    preds, succs = {t: set() for t in groups}, {t: set() for t in groups}
    for n in graph.order:
        for p in graph.preds[n]:
            a, b = mapping[p], mapping[n]
            if a != b: preds[b].add(a); succs[a].add(b)
    for order in old_plan['core_schedules']:
        fixed = [t for t in order if t in groups and t not in mutable]
        for a, b in zip(fixed, fixed[1:]): preds[b].add(a); succs[a].add(b)
    weights, priority = {}, {}
    for t, nodes in groups.items():
        loads = defaultdict(int)
        for n in nodes: loads[graph.ops[n]['pipe']] += graph.ops[n]['cycles']
        weights[t] = max(loads.values(), default=0) if t in mutable else old_tasks[t]['duration']
        priority[t] = min(old_tasks[int(old_plan['node_to_subgraph'][str(n)])]['start'] for n in nodes)
    degree = {t: len(p) for t,p in preds.items()}
    ready = [(priority[t], t) for t in groups if degree[t] == 0]
    heapq.heapify(ready)
    orders = [[] for _ in old_plan['core_schedules']]
    ends, assigned, finishes = [0]*len(orders), {}, {}
    while ready:
        _, t = heapq.heappop(ready)
        cores = [pinned[t]] if t in pinned else range(len(orders)) if t in mutable else [old_core[t]]
        choices = []
        for c in cores:
            start = ends[c] + (result['task_same_core_wait_cycles'] if orders[c] else 0)
            for p in preds[t]:
                start = max(start, finishes[p] + (result['task_cross_core_wait_cycles'] if assigned[p] != c else 0))
            choices.append((start+weights[t], c))
        end,c = min(choices)
        orders[c].append(t); ends[c] = end; finishes[t] = end; assigned[t] = c
        for n in sorted(succs[t]):
            degree[n] -= 1
            if not degree[n]: heapq.heappush(ready, (priority[n], n))
    if len(assigned) != len(groups): raise ValueError('local edit creates a task/order cycle')
    plan = {'node_to_subgraph': {str(n): t for n,t in sorted(mapping.items())}, 'core_schedules': orders}
    validate_task_order(derive_multicore_plan(graph.data, plan))
    return plan


def candidates(data, plan, result):
    """At most six candidates: two critical merges, two splits, two moves.

No graph IDs or outcomes enter the policy. Merge keeps unaffected core order;
split acts on the longest observed critical-chain task only, using depth bands
and within-band weak components (local graph construction, no global retuning).
"""
    graph, diagnostic = Graph(data), diagnose(result)
    original = {int(n): t for n,t in plan['node_to_subgraph'].items()}
    tasks = diagnostic['tasks']
    target = max(diagnostic['chain'], key=lambda t:(tasks[t]['duration'], -t))
    specs = []
    # Prefer a critical chain dependency with high transfer occupancy or wait.
    dependencies = {(e['source'], e['target']) for e in result['task_dependencies']}
    pairs = [e for e in diagnostic['edges'] if (e['source'],e['target']) in dependencies]
    if pairs:
        edge = max(pairs, key=lambda e:(e['delay'] + sum(tasks[t]['occupancy']['transfer_only'] for t in (e['source'],e['target'])), -e['source']))
        a,b = edge['source'],edge['target']
        for label,c in [('source',tasks[a]['core']),('target',tasks[b]['core'])]:
            mapping = {n: a if t == b else t for n,t in original.items()}
            specs.append((f'merge_{label}', mapping, {a}, {a:c}, {'merged_tasks':[a,b]}))
    members = {n for n,t in original.items() if t == target}
    depth = {}
    for n in graph.order:
        if n in members: depth[n] = 1+max((depth[p] for p in graph.preds[n] if p in members), default=-1)
    for bands in (2,4):
        width = max(1, (max(depth.values())+bands)//bands)
        mapping, seen, next_id = dict(original), set(), max(original.values())+1
        new_tasks = set()
        for root in graph.order:
            if root not in members or root in seen: continue
            stack, group = [root], []; seen.add(root)
            while stack:
                n = stack.pop(); group.append(n)
                for other in sorted(graph.preds[n] | graph.succs[n]):
                    if other in members and other not in seen and depth[other]//width == depth[root]//width:
                        seen.add(other); stack.append(other)
            for n in group: mapping[n] = next_id
            new_tasks.add(next_id); next_id += 1
        specs.append((f'split_{bands}', mapping, new_tasks, {}, {'split_task':target,'new_tasks':len(new_tasks),'depth_width':width}))
    core_busy = diagnostic['core_task_busy']
    alternatives = sorted((c for c in range(len(core_busy)) if c != tasks[target]['core']), key=lambda c:(core_busy[c], c))[:2]
    for rank,c in enumerate(alternatives):
        specs.append((f'move_{rank+1}', original, {target}, {target:c}, {'moved_task':target,'destination_core':c}))
    for name,mapping,mutable,pinned,edit in specs:
        try:
            candidate = repack(graph,plan,result,mapping,mutable,pinned)
            yield name, candidate, edit, None
        except ValueError as exc:
            yield name, None, edit, str(exc)
