"""Problem 2 v006: op-level priorities on the multiple-component route."""
from graph_analysis import Graph
from component_scheduler import independent_components
from region_scheduler import make_plan as region_plan
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

VERSION = 'v006'


def make_plan(data, num_cores, blocks_per_core=4, same_core_wait=0, cross_core_wait=500):
    base = region_plan(data, num_cores, blocks_per_core, same_core_wait, cross_core_wait)
    graph = Graph(data)
    if len(independent_components(graph)) <= 1:
        return base
    members = {}
    for node in graph.order:
        members.setdefault(base['node_to_subgraph'][str(node)], []).append(node)
    mapping, orders = {}, [[] for _ in range(num_cores)]
    group = 0
    for core, old_groups in enumerate(base['core_schedules']):
        for old_group in old_groups:
            for node in members[old_group]:
                mapping[str(node)] = group
                orders[core].append(group)
                group += 1
    plan = {'node_to_subgraph': mapping, 'core_schedules': orders}
    validate_task_order(derive_multicore_plan(data, plan))
    return plan
