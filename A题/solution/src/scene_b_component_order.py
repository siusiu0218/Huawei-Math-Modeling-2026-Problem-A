"""Problem 2 v005: preserve v002 placement; prioritize whole components locally."""
from collections import defaultdict

from graph_analysis import Graph
from component_scheduler import independent_components
from region_scheduler import make_plan as region_plan
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

VERSION = 'v005'


def make_plan(data, num_cores, blocks_per_core=4, same_core_wait=0, cross_core_wait=500):
    base = region_plan(data, num_cores, blocks_per_core, same_core_wait, cross_core_wait)
    graph = Graph(data)
    components = independent_components(graph)
    if len(components) <= 1:
        return base
    # The existing multiple-component route keeps each whole component in one
    # subgroup. Split the subgroup priorities, keeping core assignment exactly.
    by_group = defaultdict(list)
    for nodes in components:
        group_ids = {base['node_to_subgraph'][str(node)] for node in nodes}
        if len(group_ids) != 1:
            raise ValueError('base method split a weak component')
        by_group[next(iter(group_ids))].append(nodes)
    orders, mapping = [[] for _ in range(num_cores)], {}
    next_group = 0
    for core, groups in enumerate(base['core_schedules']):
        for old_group in groups:
            for nodes in sorted(by_group[old_group], key=min):
                orders[core].append(next_group)
                mapping.update({str(node): next_group for node in nodes})
                next_group += 1
    plan = {'node_to_subgraph': mapping, 'core_schedules': orders}
    validate_task_order(derive_multicore_plan(data, plan))
    return plan
