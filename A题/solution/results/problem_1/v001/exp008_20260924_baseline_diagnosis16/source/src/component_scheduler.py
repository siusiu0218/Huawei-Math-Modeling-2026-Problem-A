"""v002: keep weakly connected operation components intact; balance whole groups."""
from graph_analysis import Graph
from baseline import make_plan as baseline_plan
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

VERSION = 'v002'


def independent_components(graph):
    seen, components = set(), []
    for root in graph.order:
        if root in seen:
            continue
        pending, group = [root], []
        seen.add(root)
        while pending:
            node = pending.pop()
            group.append(node)
            for other in sorted(graph.preds[node] | graph.succs[node]):
                if other not in seen:
                    seen.add(other)
                    pending.append(other)
        components.append(sorted(group))
    return components


def make_plan(data, num_cores, blocks_per_core=4, same_core_wait=100, cross_core_wait=1000):
    for name, value in [('num_cores', num_cores), ('blocks_per_core', blocks_per_core)]:
        if type(value) is not int or value < 1:
            raise ValueError(f'{name} must be a positive integer')
    graph = Graph(data)
    groups = independent_components(graph)
    if len(groups) <= 1:
        # No independent whole groups to exploit: explicitly retain the frozen baseline.
        return baseline_plan(data, num_cores, blocks_per_core, same_core_wait, cross_core_wait)
    count = min(len(groups), num_cores * blocks_per_core)
    bins = [[] for _ in range(count)]
    weights = [0] * count
    ranked = sorted(groups, key=lambda group: (-sum(graph.ops[i]['cycles'] for i in group), min(group)))
    for group in ranked:
        target = min(range(count), key=lambda b: (weights[b], len(bins[b]), b))
        bins[target].extend(group)
        weights[target] += sum(graph.ops[i]['cycles'] for i in group)
    orders = [[] for _ in range(num_cores)]
    ends = [0] * num_cores
    for task in sorted(range(count), key=lambda b: (-weights[b], b)):
        core = min(range(num_cores), key=lambda c: (
            ends[c] + (same_core_wait if orders[c] else 0), len(orders[c]), c))
        ends[core] += weights[task] + (same_core_wait if orders[core] else 0)
        orders[core].append(task)
    plan = {'node_to_subgraph': {str(i): task for task, group in enumerate(bins) for i in sorted(group)},
            'core_schedules': orders}
    validate_task_order(derive_multicore_plan(data, plan))
    return plan
