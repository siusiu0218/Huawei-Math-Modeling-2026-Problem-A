"""Q2 v009: bounded candidates selected by local scheduling + DDR proxy.

At most four distinct plans. Uses the unmodified evaluator's local preparation,
not its global makespan, for selection. The proxy is not a bound or final score.
"""
import json
from graph_analysis import Graph
from component_scheduler import independent_components
from region_scheduler import make_plan as region_plan
from scene_b_paired_order import make_plan as paired_plan
from scene_b_split_components import make_plan as split_plan, IMBALANCE_THRESHOLD
from multicore_cut_evaluate_problem_2 import _build_scene_b_tasks

VERSION = 'v009'


def interleave(graph, components, base, width):
    positions = {node: i for i, node in enumerate(graph.order)}
    by_group = {}
    for nodes in components:
        group_ids = {base['node_to_subgraph'][str(n)] for n in nodes}
        if len(group_ids) != 1:
            raise ValueError('interleaving requires intact components')
        by_group.setdefault(next(iter(group_ids)), []).append(sorted(nodes, key=positions.get))
    mapping, orders = {}, [[] for _ in base['core_schedules']]
    group = 0
    for core, old_groups in enumerate(base['core_schedules']):
        sequences = [seq for old in old_groups for seq in sorted(by_group[old], key=min)]
        for i in range(0, len(sequences), width):
            batch = sequences[i:i + width]
            for depth in range(max(map(len, batch))):
                for seq in batch:
                    if depth < len(seq):
                        mapping[str(seq[depth])] = group
                        orders[core].append(group)
                        group += 1
    return {'node_to_subgraph': mapping, 'core_schedules': orders}


def make_plan_with_stats(data, num_cores, blocks_per_core=4, same_core_wait=0,
                         cross_core_wait=500, bandwidth=60, capacity=None):
    capacity = {'L1': 524288, 'UB': 131072} if capacity is None else capacity
    graph = Graph(data)
    components = independent_components(graph)
    base = region_plan(data, num_cores, blocks_per_core, same_core_wait, cross_core_wait)
    if len(components) <= 1 or num_cores == 1:
        return base, {'selected': 'regions', 'candidates': [], 'local_preparations': 0}
    work = [sum(max(1, graph.ops[n]['cycles']) for n in comp) for comp in components]
    oversized = max(work) > IMBALANCE_THRESHOLD * sum(work) / num_cores
    candidates = [('paired2', interleave(graph, components, base, 2)), ('regions', base)]
    if oversized:
        candidates.append(('split', split_plan(data, num_cores, blocks_per_core, same_core_wait, cross_core_wait)))
    else:
        candidates.extend((f'paired{w}', interleave(graph, components, base, w)) for w in (4, 8))
    seen, records, best_plan, best_key = set(), [], None, None
    for name, plan in candidates:
        key = json.dumps(plan, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        try:
            tasks, links, _, traffic, _ = _build_scene_b_tasks(data, plan, bandwidth, capacity)
            local = max(t['step3']['makespan'] for t in tasks.values())
            score = local + traffic['scheduled_copy_bytes'] / bandwidth
            record = {'name': name, 'status': 'success', 'score': score,
                      'max_local_makespan': local, 'data_movement_bytes': traffic,
                      'cross_core_links': len(links)}
        except (ValueError, RuntimeError) as error:
            records.append({'name': name, 'status': 'failed', 'error': str(error)})
            continue
        records.append(record)
        if best_key is None or score < best_key:
            best_key, best_plan, selected = score, plan, name
    if best_plan is None:
        raise ValueError(f'all local candidates failed: {records}')
    return best_plan, {'selected': selected, 'candidates': records, 'local_preparations': len(records)}


def make_plan(data, num_cores, blocks_per_core=4, same_core_wait=0, cross_core_wait=500):
    return make_plan_with_stats(data, num_cores, blocks_per_core, same_core_wait, cross_core_wait)[0]
