"""Q1 v011 pilot refinement: critical same-core neighbour merges.

Unlike v010, considers consecutive tasks without a data-dependency edge.
Ranks by exact boundary COPY byte saving (excluding spills) before evaluating.
Only two positive-saving pairs on the observed critical chain are attempted.
"""
from collections import defaultdict
from scene_a_critical_local import Graph, diagnose, repack
from region_scheduler import BoundaryTraffic

VERSION = 'v011'


def candidates(data, plan, result):
    graph = Graph(data)
    mapping = {int(n):t for n,t in plan['node_to_subgraph'].items()}
    groups = defaultdict(list)
    for n,t in mapping.items(): groups[t].append(n)
    traffic = BoundaryTraffic(graph, groups)
    diagnosis = diagnose(result)
    choices = []
    for edge in diagnosis['edges']:
        a,b = edge['source'],edge['target']
        if edge['kind'] != 'same_core_order': continue
        saving = traffic.saving({a,b},a)
        if saving > 0: choices.append((-saving,a,b))
    for rank,(negative_saving,a,b) in enumerate(sorted(choices)[:2],1):
        updated = {n:a if t == b else t for n,t in mapping.items()}
        edit = {'merged_tasks':[a,b],'predicted_partition_byte_saving':-negative_saving}
        try:
            merged = repack(graph,plan,result,updated,{a},{a:diagnosis['tasks'][a]['core']})
            yield f'neighbour_merge_{rank}',merged,edit,None
        except ValueError as exc:
            yield f'neighbour_merge_{rank}',None,edit,str(exc)
