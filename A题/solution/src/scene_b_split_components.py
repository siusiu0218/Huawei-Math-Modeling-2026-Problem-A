"""Q2 v008: split oversized components before global list scheduling.

One candidate, no evaluator-based selection. Balanced multi-component graphs
and single-component graphs retain v007. The threshold is a compute proxy.
"""
from graph_analysis import Graph
from component_scheduler import independent_components
from scene_b_paired_order import make_plan as previous_plan
from region_scheduler import (
    chain_contract, BoundaryTraffic, merge_small_arms, topological,
    find_region, region_cost, merge_region, schedule, MAX_PASSES,
)
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

VERSION = 'v008'
IMBALANCE_THRESHOLD = 1.25


def make_plan(data, num_cores, blocks_per_core=4, same_core_wait=0, cross_core_wait=500):
    for name, value in [('num_cores', num_cores), ('blocks_per_core', blocks_per_core)]:
        if type(value) is not int or value < 1:
            raise ValueError(f'{name} must be a positive integer')
    graph = Graph(data)
    components = independent_components(graph)
    work = [sum(max(1, graph.ops[n]['cycles']) for n in comp) for comp in components]
    if len(components) <= 1 or max(work) <= IMBALANCE_THRESHOLD * sum(work) / num_cores:
        return previous_plan(data, num_cores, blocks_per_core, same_core_wait, cross_core_wait)
    cap = sum(work) / (num_cores * blocks_per_core)
    groups, preds, succs = chain_contract(graph, cap)
    weights = {t: sum(graph.ops[n]['cycles'] for n in members) for t, members in groups.items()}
    traffic = BoundaryTraffic(graph, groups)
    wait = min(same_core_wait, cross_core_wait)
    merge_small_arms(groups, preds, succs, weights, traffic, cap, wait)
    for _ in range(MAX_PASSES):
        order = topological(preds, succs)
        positions = {t: i for i, t in enumerate(order)}
        accepted = 0
        for root in order:
            if root not in groups:
                continue
            region = find_region(root, preds, succs, weights, positions, cap)
            if region is None:
                continue
            cost = region_cost(region, preds, weights, traffic, wait)
            if cost['compute_loss'] >= cost['saved_wait_proxy'] + cost['transfer_cycles_proxy']:
                continue
            merge_region(region, groups, preds, succs, weights, traffic)
            accepted += 1
        if not accepted:
            break
    plan = schedule(groups, preds, succs, weights, num_cores, same_core_wait, cross_core_wait)
    validate_task_order(derive_multicore_plan(data, plan))
    return plan
