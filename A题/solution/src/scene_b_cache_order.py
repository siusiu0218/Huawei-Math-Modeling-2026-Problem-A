"""Q3 v002: reorder existing subgraphs, preserving their membership and cores.

The shared FIFO and per-core recency sets are cheap priority proxies, not a
prediction of the official COPY issue times or measured cache hit rate.
"""
from collections import OrderedDict, defaultdict
from copy import deepcopy
import heapq

from graph_analysis import Graph
from stub_multicore_cut_and_schedule import derive_multicore_plan
from evaluation_validation import validate_task_order

VERSION='v002'
WINDOW=32


def reorder(data, base, mode='cache_affinity', capacity=1048576):
    if mode not in ('cache_affinity','critical_path'):
        raise ValueError('unknown ordering mode')
    view=derive_multicore_plan(data,base)
    graph=Graph(data)
    mapping=view['mapping']; cores=view['core_by_subgraph']
    groups=view['subgraph_ids']; n=view['num_cores']
    position={g:i for order in base['core_schedules'] for i,g in enumerate(order)}
    weight={g:sum(graph.ops[o]['cycles'] for o in view['nodes_by_subgraph'][g]) for g in groups}
    operands={g:set() for g in groups}
    sizes={t['id']:t['size'] for t in data['tensors']}
    for tid,consumers in graph.consumers.items():
        for op in consumers:operands[mapping[op]].add(tid)
    # Deterministic dependency-only topological order for bottom-level priority.
    degree={g:len(view['subgraph_preds'][g]) for g in groups}
    queue=[g for g in groups if degree[g]==0];heapq.heapify(queue);topo=[]
    while queue:
        g=heapq.heappop(queue);topo.append(g)
        for nxt in sorted(view['subgraph_succs'][g]):
            degree[nxt]-=1
            if degree[nxt]==0:heapq.heappush(queue,nxt)
    bottom={}
    for g in reversed(topo):
        bottom[g]=weight[g]+max((bottom[h] for h in view['subgraph_succs'][g]),default=0)
    degree={g:len(view['subgraph_preds'][g]) for g in groups}
    ready=[[] for _ in range(n)]
    for g in groups:
        if degree[g]==0:heapq.heappush(ready[cores[g]],(position[g],g))
    orders=[[] for _ in range(n)];clock=[0]*n
    fifo=OrderedDict();used=0
    local=[OrderedDict() for _ in range(n)];local_used=[0]*n
    count=0
    while count<len(groups):
        active=[c for c in range(n) if ready[c]]
        if not active:raise ValueError('subgraph dependency cycle')
        core=min(active,key=lambda c:(clock[c],c))
        candidates=[heapq.heappop(ready[core]) for _ in range(min(WINDOW,len(ready[core])))]
        def priority(pair):
            _,g=pair
            if mode=='critical_path':return (-bottom[g],position[g],g)
            local_bytes=sum(sizes[t] for t in operands[g] if t in local[core])
            shared_bytes=sum(sizes[t] for t in operands[g] if t in fifo and t not in local[core])
            # Integer saving proxy: local saves DDR; Cache saves DDR minus Cache read.
            saving=250*local_bytes+190*shared_bytes
            return (-saving,-bottom[g],position[g],g)
        chosen=min(candidates,key=priority);g=chosen[1]
        for pair in candidates:
            if pair!=chosen:heapq.heappush(ready[core],pair)
        orders[core].append(g);count+=1;clock[core]+=weight[g]
        for tid in sorted(operands[g]):
            size=sizes[tid]
            if tid not in fifo and size<=capacity:
                while fifo and used+size>capacity:
                    _,evicted=fifo.popitem(last=False);used-=evicted
                fifo[tid]=size;used+=size
            # This local set only breaks priority ties through estimated locality.
            # It is not the evaluator's L1/UB residency model.
            if tid in local[core]:local[core].move_to_end(tid)
            elif size<=131072:
                while local[core] and local_used[core]+size>131072:
                    _,evicted=local[core].popitem(last=False);local_used[core]-=evicted
                local[core][tid]=size;local_used[core]+=size
        for nxt in sorted(view['subgraph_succs'][g]):
            degree[nxt]-=1
            if degree[nxt]==0:heapq.heappush(ready[cores[nxt]],(position[nxt],nxt))
    result=deepcopy(base);result['core_schedules']=orders
    validate_task_order(derive_multicore_plan(data,result))
    assert result['node_to_subgraph']==base['node_to_subgraph']
    assert all(set(a)==set(b) for a,b in zip(orders,base['core_schedules']))
    return result
