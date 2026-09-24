"""v001: deterministic topological chunks and append-only earliest-finish placement."""
from graph_analysis import Graph
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

VERSION = 'v001'


def make_plan(data, num_cores, blocks_per_core=4, same_core_wait=100, cross_core_wait=1000):
    if type(num_cores) is not int or num_cores < 1:
        raise ValueError('num_cores must be a positive integer')
    if type(blocks_per_core) is not int or blocks_per_core < 1:
        raise ValueError('blocks_per_core must be a positive integer')
    graph = Graph(data)
    if not graph.order:
        return {'node_to_subgraph': {}, 'core_schedules': [[] for _ in range(num_cores)]}
    count = min(len(graph.order), num_cores * blocks_per_core)
    # Unit floor is only a partition weight: zero-cycle operations still get assigned.
    total = sum(max(1, o['cycles']) for o in graph.ops.values())
    target = total / count
    chunks, current, weight = [], [], 0
    for i in graph.order:
        if current and weight >= target and len(chunks) < count - 1:
            chunks.append(current)
            current, weight = [], 0
        current.append(i)
        weight += max(1, graph.ops[i]['cycles'])
    chunks.append(current)
    mapping = {i: s for s, chunk in enumerate(chunks) for i in chunk}
    task_preds = [set() for _ in chunks]
    for i in graph.order:
        task_preds[mapping[i]].update(mapping[p] for p in graph.preds[i] if mapping[p] != mapping[i])
    orders = [[] for _ in range(num_cores)]
    ends = [0] * num_cores
    assigned, finishes = {}, {}
    for s, chunk in enumerate(chunks):
        # Deliberately simple proxy: sum of compute cycles. Actual score uses evaluator.
        duration = sum(graph.ops[i]['cycles'] for i in chunk)
        candidates = []
        for core in range(num_cores):
            release = ends[core] + same_core_wait if orders[core] else 0
            for pred in task_preds[s]:
                release = max(release, finishes[pred] +
                              (cross_core_wait if assigned[pred] != core else 0))
            candidates.append((release + duration, core))
        end, core = min(candidates)
        orders[core].append(s)
        ends[core] = finishes[s] = end
        assigned[s] = core
    plan = {'node_to_subgraph': {str(i): mapping[i] for i in sorted(mapping)},
            'core_schedules': orders}
    validate_task_order(derive_multicore_plan(data, plan))
    return plan
