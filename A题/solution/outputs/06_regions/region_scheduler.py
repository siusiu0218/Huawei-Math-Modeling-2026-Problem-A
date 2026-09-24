"""v008: contract closed small fork/join regions on top of frozen v004.

Traffic differences are exact for the evaluator's task-boundary construction,
excluding spills. Compute loss and bandwidth time are screening proxies only.
"""
import heapq
from collections import deque

from graph_analysis import Graph
from component_scheduler import independent_components, make_plan as component_plan
from fork_preserving_scheduler import contract as chain_contract
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

VERSION = 'v008'
BANDWIDTH = 60
MAX_REGION_TASKS = 128
MAX_PASSES = 3


class BoundaryTraffic:
    """Mutable tensor hyperedges indexed by CURRENT task, including shared inputs."""
    def __init__(self, graph, groups):
        mapping = {node: task for task, members in groups.items() for node in members}
        self.sizes = {t['id']: t['size'] for t in graph.data['tensors']}
        op_types = {op['id']: op['op'] for op in graph.data['ops']}
        self.copy_out = set()
        for edge in graph.data['edges']:
            if edge['source'] in self.sizes and op_types.get(edge['target']) == 'COPY_OUT':
                self.copy_out.add(edge['source'])
        self.producers = {t: {mapping[n] for n in graph.producers[t]} for t in self.sizes}
        self.consumers = {t: {mapping[n] for n in graph.consumers[t]} for t in self.sizes}
        self.touched = {task: set() for task in groups}
        for tensor in self.sizes:
            for task in self.producers[tensor] | self.consumers[tensor]:
                self.touched[task].add(tensor)

    def tensor_traffic(self, tensor, producers, consumers):
        inputs = len(consumers - producers)
        outputs = sum(tensor in self.copy_out or not consumers or bool(consumers - {p})
                      for p in producers)
        return self.sizes[tensor] * (inputs + outputs)

    def total(self):
        return sum(self.tensor_traffic(t, self.producers[t], self.consumers[t])
                   for t in self.sizes)

    def saving(self, region, root):
        tensors = set().union(*(self.touched[t] for t in region))
        saved = 0
        for tensor in tensors:
            p, c = self.producers[tensor], self.consumers[tensor]
            new_p = (p - region) | ({root} if p & region else set())
            new_c = (c - region) | ({root} if c & region else set())
            saved += self.tensor_traffic(tensor, p, c) - self.tensor_traffic(tensor, new_p, new_c)
        return saved

    def merge(self, region, root):
        tensors = set().union(*(self.touched[t] for t in region))
        for tensor in tensors:
            for view in (self.producers, self.consumers):
                if view[tensor] & region:
                    view[tensor] = (view[tensor] - region) | {root}
        for task in region - {root}:
            del self.touched[task]
        self.touched[root] = tensors


def topological(preds, succs):
    degree = {t: len(p) for t, p in preds.items()}
    ready = [t for t in preds if not degree[t]]
    heapq.heapify(ready)
    order = []
    while ready:
        task = heapq.heappop(ready)
        order.append(task)
        for nxt in sorted(succs[task]):
            degree[nxt] -= 1
            if not degree[nxt]:
                heapq.heappush(ready, nxt)
    if len(order) != len(preds):
        raise ValueError('cyclic task quotient')
    return order


def find_region(root, preds, succs, weights, positions, cap):
    """Expand only nodes whose predecessors are internal, stopping at one exit.

    A sink before reconvergence or an external predecessor prevents closure.
    The closed region is graph-convex, so contracting it cannot create a cycle.
    """
    if len(succs[root]) < 2:
        return None
    members, ordered = {root}, [root]
    frontier = set(succs[root])
    work = weights[root]
    while frontier and len(members) < MAX_REGION_TASKS:
        eligible = [t for t in frontier if preds[t] <= members]
        if not eligible:
            return None
        nxt = min(eligible, key=lambda t: positions[t])
        work += weights[nxt]
        if work > cap:
            return None
        if len(frontier) == 1:
            return ordered + [nxt]
        if not succs[nxt]:
            return None
        members.add(nxt)
        ordered.append(nxt)
        frontier.remove(nxt)
        frontier.update(succs[nxt] - members)
    return None


def region_cost(ordered, preds, weights, traffic, wait):
    members = set(ordered)
    compute, waited = {}, {}
    for task in ordered:
        internal = preds[task] & members
        compute[task] = weights[task] + max((compute[p] for p in internal), default=0)
        waited[task] = weights[task] + max((waited[p] + wait for p in internal), default=0)
    span = max(compute.values())
    work = sum(weights[t] for t in ordered)
    saved = traffic.saving(members, ordered[0])
    return {'tasks': len(ordered), 'compute_work': work, 'compute_span': span,
            'compute_loss': work - span, 'saved_boundary_bytes': saved,
            'saved_wait_proxy': max(waited.values()) - span,
            'transfer_cycles_proxy': saved / BANDWIDTH}


def merge_region(ordered, groups, preds, succs, weights, traffic):
    region, root = set(ordered), ordered[0]
    incoming = set().union(*(preds[t] for t in region)) - region
    outgoing = set().union(*(succs[t] for t in region)) - region
    for t in incoming:
        succs[t].difference_update(region)
        succs[t].add(root)
    for t in outgoing:
        preds[t].difference_update(region)
        preds[t].add(root)
    traffic.merge(region, root)
    members = [node for t in ordered for node in groups[t]]
    work = sum(weights[t] for t in region)
    for t in region - {root}:
        del groups[t], preds[t], succs[t], weights[t]
    groups[root], preds[root], succs[root], weights[root] = members, incoming, outgoing, work


def edge_cost(a, b, preds, succs, weights, traffic, wait):
    """Directional bound on the extra compute span caused by a safe edge merge.

    Absorbing a predecessor into a join delays THAT predecessor until all other
    join inputs arrive (loss <= weight[a]). Absorbing a successor into a fork
    delays other fork outputs by THAT successor (loss <= weight[b]). The OR
    safety condition excludes alternate paths; taking min(weights) is wrong.
    """
    loss = (weights[a] if len(preds[b]) > 1 else 0) + (weights[b] if len(succs[a]) > 1 else 0)
    saved = traffic.saving({a, b}, a)
    return {'compute_loss_bound': loss, 'saved_boundary_bytes': saved,
            'saved_wait_proxy': wait, 'transfer_cycles_proxy': saved / BANDWIDTH}


def merge_small_arms(groups, preds, succs, weights, traffic, cap, wait):
    pending = deque((a, b) for a in topological(preds, succs) for b in sorted(succs[a]))
    accepted, rejected = [], 0
    while pending:
        a, b = pending.popleft()
        if a not in groups or b not in succs[a]:
            continue
        if len(succs[a]) != 1 and len(preds[b]) != 1:
            continue
        if weights[a] + weights[b] > cap:
            continue
        cost = edge_cost(a, b, preds, succs, weights, traffic, wait)
        if cost['compute_loss_bound'] >= cost['saved_wait_proxy'] + cost['transfer_cycles_proxy']:
            rejected += 1
            continue
        accepted.append({'left': a, 'right': b, **cost})
        merge_region([a, b], groups, preds, succs, weights, traffic)
        pending.extend((n, a) for n in sorted(preds[a]))
        pending.extend((a, n) for n in sorted(succs[a]))
    return accepted, rejected


def schedule(groups, preds, succs, weights, num_cores, same_core_wait, cross_core_wait):
    order = topological(preds, succs)
    rank = {}
    for t in reversed(order):
        rank[t] = weights[t] + max((rank[n] for n in succs[t]), default=0)
    degree = {t: len(preds[t]) for t in groups}
    ready = [(-rank[t], t) for t in groups if not degree[t]]
    heapq.heapify(ready)
    schedules, ends = [[] for _ in range(num_cores)], [0] * num_cores
    placement, finishes = {}, {}
    while ready:
        _, task = heapq.heappop(ready)
        choices = []
        for core in range(num_cores):
            start = ends[core] + (same_core_wait if schedules[core] else 0)
            for pred in preds[task]:
                start = max(start, finishes[pred] + (same_core_wait if placement[pred] == core else cross_core_wait))
            choices.append((start + weights[task], core))
        end, core = min(choices)
        schedules[core].append(task)
        ends[core] = finishes[task] = end
        placement[task] = core
        for nxt in sorted(succs[task]):
            degree[nxt] -= 1
            if not degree[nxt]:
                heapq.heappush(ready, (-rank[nxt], nxt))
    return {'node_to_subgraph': {str(n): t for t in sorted(groups) for n in sorted(groups[t])},
            'core_schedules': schedules}


def compute_span(preds, succs, weights):
    span = {}
    for t in topological(preds, succs):
        span[t] = weights[t] + max((span[p] for p in preds[t]), default=0)
    return max(span.values(), default=0)


def make_plan_with_stats(data, num_cores, blocks_per_core=4, same_core_wait=100, cross_core_wait=1000):
    for name, value in [('num_cores', num_cores), ('blocks_per_core', blocks_per_core)]:
        if type(value) is not int or value < 1:
            raise ValueError(f'{name} must be a positive integer')
    graph = Graph(data)
    components = len(independent_components(graph))
    if components != 1:
        return component_plan(data, num_cores, blocks_per_core, same_core_wait, cross_core_wait), {
            'route': 'components', 'components': components, 'accepted_regions': []}
    cap = sum(max(1, op['cycles']) for op in graph.ops.values()) / (num_cores * blocks_per_core)
    groups, preds, succs = chain_contract(graph, cap)
    weights = {t: sum(graph.ops[n]['cycles'] for n in members) for t, members in groups.items()}
    traffic = BoundaryTraffic(graph, groups)
    stats = {'route': 'regions', 'cap': cap, 'initial_tasks': len(groups),
             'initial_compute_span': compute_span(preds, succs, weights),
             'initial_boundary_bytes': traffic.total(), 'accepted_regions': [],
             'closed_regions_examined': 0, 'cost_rejections': 0}
    stats['accepted_arms'], stats['arm_cost_rejections'] = merge_small_arms(
        groups, preds, succs, weights, traffic, cap, min(same_core_wait, cross_core_wait))
    for pass_id in range(MAX_PASSES):
        order = topological(preds, succs)
        positions = {t: i for i, t in enumerate(order)}
        accepted = 0
        for root in order:
            if root not in groups:
                continue
            region = find_region(root, preds, succs, weights, positions, cap)
            if region is None:
                continue
            stats['closed_regions_examined'] += 1
            cost = region_cost(region, preds, weights, traffic, min(same_core_wait, cross_core_wait))
            if cost['compute_loss'] >= cost['saved_wait_proxy'] + cost['transfer_cycles_proxy']:
                stats['cost_rejections'] += 1
                continue
            stats['accepted_regions'].append({'pass': pass_id, 'root': root, **cost})
            merge_region(region, groups, preds, succs, weights, traffic)
            accepted += 1
        if not accepted:
            break
    stats.update(final_tasks=len(groups), final_compute_span=compute_span(preds, succs, weights),
                 final_boundary_bytes=traffic.total())
    plan = schedule(groups, preds, succs, weights, num_cores, same_core_wait, cross_core_wait)
    validate_task_order(derive_multicore_plan(data, plan))
    return plan, stats


def make_plan(data, num_cores, blocks_per_core=4, same_core_wait=100, cross_core_wait=1000):
    return make_plan_with_stats(data, num_cores, blocks_per_core, same_core_wait, cross_core_wait)[0]
