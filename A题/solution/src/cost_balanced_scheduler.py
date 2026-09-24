"""v005: merge serial task boundaries only when a conservative cost rule passes."""
from collections import deque
import heapq
import math

from graph_analysis import Graph
from component_scheduler import independent_components, make_plan as component_plan
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

VERSION = 'v006'
DDR_BYTES_PER_CYCLE = 60
PARALLELISM_LOSS_FACTOR = 1.0


def boundary_bytes(graph, left, right):
    """Bytes on tensors directly produced by left and consumed by right."""
    return sum(t['size'] for t in graph.data['tensors']
               if left in graph.producers[t['id']] and right in graph.consumers[t['id']])


def contract(graph, cap, num_cores, same_core_wait=100, cross_core_wait=1000):
    groups = {i: [i] for i in graph.order}
    weights = {i: max(1, graph.ops[i]['cycles']) for i in graph.order}
    preds = {i: set(graph.preds[i]) for i in graph.order}
    succs = {i: set(graph.succs[i]) for i in graph.order}
    pending = deque((i, j) for i in graph.order for j in sorted(succs[i]))
    expected_wait = (same_core_wait + cross_core_wait * (num_cores - 1)) / num_cores
    while pending:
        a, b = pending.popleft()
        if a not in groups or b not in succs[a]:
            continue
        # Strict chain condition prevents absorbing alternate branch/join paths.
        if len(succs[a]) != 1 or len(preds[b]) != 1:
            continue
        merged_weight = weights[a] + weights[b]
        if merged_weight > cap:
            continue
        transfer_saving = boundary_bytes(graph, a, b) / DDR_BYTES_PER_CYCLE
        avoided_wait = expected_wait
        flexibility_loss = min(weights[a], weights[b]) * PARALLELISM_LOSS_FACTOR
        if transfer_saving + avoided_wait <= flexibility_loss:
            continue
        incoming = (preds[a] | preds[b]) - {a, b}
        outgoing = (succs[a] | succs[b]) - {a, b}
        for node in incoming:
            succs[node].difference_update({a, b})
            succs[node].add(a)
        for node in outgoing:
            preds[node].difference_update({a, b})
            preds[node].add(a)
        groups[a].extend(groups.pop(b))
        weights[a] = merged_weight
        del weights[b], preds[b], succs[b]
        preds[a], succs[a] = incoming, outgoing
        pending.extend((node, a) for node in sorted(incoming))
        pending.extend((a, node) for node in sorted(outgoing))
    return groups, preds, succs


def make_plan(data, num_cores, blocks_per_core=4, same_core_wait=100, cross_core_wait=1000):
    for name, value in [('num_cores', num_cores), ('blocks_per_core', blocks_per_core)]:
        if type(value) is not int or value < 1:
            raise ValueError(f'{name} must be a positive integer')
    graph = Graph(data)
    if len(independent_components(graph)) != 1:
        return component_plan(data, num_cores, blocks_per_core, same_core_wait, cross_core_wait)
    # Limit a merged task to the average per-core compute budget. The cost
    # gate then determines whether fewer, larger tasks are worth their loss
    # of placement flexibility.
    cap = sum(max(1, op['cycles']) for op in graph.ops.values()) / num_cores
    groups, preds, succs = contract(graph, cap, num_cores, same_core_wait, cross_core_wait)
    duration = {i: sum(graph.ops[n]['cycles'] for n in members) for i, members in groups.items()}
    degree = {i: len(preds[i]) for i in groups}
    ready = [i for i in groups if not degree[i]]
    heapq.heapify(ready)
    order = []
    while ready:
        i = heapq.heappop(ready)
        order.append(i)
        for j in sorted(succs[i]):
            degree[j] -= 1
            if degree[j] == 0:
                heapq.heappush(ready, j)
    if len(order) != len(groups):
        raise ValueError('contraction produced a cycle')
    rank = {}
    for i in reversed(order):
        rank[i] = duration[i] + max((rank[j] for j in succs[i]), default=0)
    degree = {i: len(preds[i]) for i in groups}
    ready = [(-rank[i], i) for i in groups if not degree[i]]
    heapq.heapify(ready)
    schedules, ends, placement, finishes = [[] for _ in range(num_cores)], [0] * num_cores, {}, {}
    while ready:
        _, i = heapq.heappop(ready)
        choices = []
        for core in range(num_cores):
            start = ends[core] + (same_core_wait if schedules[core] else 0)
            for pred in preds[i]:
                start = max(start, finishes[pred] + (same_core_wait if placement[pred] == core else cross_core_wait))
            choices.append((start + duration[i], core))
        end, core = min(choices)
        placement[i], finishes[i], ends[core] = core, end, end
        schedules[core].append(i)
        for j in sorted(succs[i]):
            degree[j] -= 1
            if degree[j] == 0:
                heapq.heappush(ready, (-rank[j], j))
    plan = {'node_to_subgraph': {str(n): i for i in sorted(groups) for n in sorted(groups[i])},
            'core_schedules': schedules}
    validate_task_order(derive_multicore_plan(data, plan))
    return plan

