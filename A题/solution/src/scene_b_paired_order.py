"""Problem 2 v007: interleave pairs of independent components on each core."""
from graph_analysis import Graph
from component_scheduler import independent_components
from region_scheduler import make_plan as region_plan
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

VERSION = 'v007'


def make_plan(data, num_cores, blocks_per_core=4, same_core_wait=0, cross_core_wait=500):
    base = region_plan(data, num_cores, blocks_per_core, same_core_wait, cross_core_wait)
    graph = Graph(data)
    components = independent_components(graph)
    if len(components) <= 1:
        return base
    positions = {node: i for i, node in enumerate(graph.order)}
    by_group = {}
    for nodes in components:
        groups = {base['node_to_subgraph'][str(node)] for node in nodes}
        if len(groups) != 1:
            raise ValueError('base method split a weak component')
        by_group.setdefault(next(iter(groups)), []).append(sorted(nodes, key=positions.get))
    mapping, orders = {}, [[] for _ in range(num_cores)]
    group = 0
    for core, old_groups in enumerate(base['core_schedules']):
        sequences = [seq for old in old_groups for seq in sorted(by_group[old], key=min)]
        for i in range(0, len(sequences), 2):
            pair = sequences[i:i+2]
            for depth in range(max(map(len, pair))):
                for seq in pair:
                    if depth < len(seq):
                        node = seq[depth]
                        mapping[str(node)] = group
                        orders[core].append(group)
                        group += 1
    plan = {'node_to_subgraph': mapping, 'core_schedules': orders}
    validate_task_order(derive_multicore_plan(data, plan))
    return plan
