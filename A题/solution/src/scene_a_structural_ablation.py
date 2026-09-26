"""Q1 v012: matched order/placement/partition ablation, no evaluator calls.

A fixes partition and cores; B fixes partition; C changes partition. All use
the same four global list-scheduler settings and the same static duration
proxy. Graph IDs never enter the algorithm. Tensor boundary traffic is counted
once per producing/consuming task, not once per op edge; spills are not modeled.
"""
from collections import defaultdict
import heapq

from graph_analysis import Graph
from region_scheduler import BoundaryTraffic, topological
from scene_a_critical_local import diagnose
from scene_b_window_components import make_plan as window_plan
from evaluation_validation import validate_task_order
from stub_multicore_cut_and_schedule import derive_multicore_plan

VERSION = 'v012'
SETTINGS = (('rank', 1), ('rank', 2), ('work', 1), ('work', 2))


def quotient(graph, mapping):
    groups = defaultdict(list)
    for n in graph.order: groups[mapping[n]].append(n)
    preds, succs = {t:set() for t in groups}, {t:set() for t in groups}
    for n in graph.order:
        for p in graph.preds[n]:
            a,b = mapping[p],mapping[n]
            if a != b: preds[b].add(a); succs[a].add(b)
    topological(preds,succs)
    return groups,preds,succs


def task_estimates(graph, groups, bandwidth):
    traffic=BoundaryTraffic(graph,groups)
    byte_counts={t:0 for t in groups}
    for tensor,size in traffic.sizes.items():
        producers,consumers=traffic.producers[tensor],traffic.consumers[tensor]
        for t in consumers-producers: byte_counts[t]+=size
        for t in producers:
            if tensor in traffic.copy_out or not consumers or consumers-{t}:
                byte_counts[t]+=size
    weights={}
    for t,nodes in groups.items():
        pipes=defaultdict(int)
        for n in nodes: pipes[graph.ops[n]['pipe']]+=max(1,graph.ops[n]['cycles'])
        weights[t]=max(pipes.values(),default=0)+byte_counts[t]/bandwidth
    assert sum(byte_counts.values())==traffic.total()
    return weights,byte_counts


def schedule(data,mapping,cores,setting,same_wait,cross_wait,bandwidth,fixed_cores=None):
    """Topological list scheduling; appended core queues cannot create a cycle.

cross_factor is only a scheduling proxy. Actual evaluations always use the
unchanged original config. A and B have identical task weights and priorities.
"""
    graph=Graph(data)
    groups,preds,succs=quotient(graph,mapping)
    weights,byte_counts=task_estimates(graph,groups,bandwidth)
    priority,cross_factor=setting
    rank={}
    for t in reversed(topological(preds,succs)):
        rank[t]=weights[t]+max((rank[s]+cross_wait*cross_factor for s in succs[t]),default=0)
    degree={t:len(p) for t,p in preds.items()}
    key=lambda t: (-(rank[t] if priority=='rank' else weights[t]),t)
    ready=[key(t) for t in groups if not degree[t]];heapq.heapify(ready)
    orders=[[] for _ in range(cores)];ends=[0]*cores;finishes={};assigned={}
    while ready:
        _,t=heapq.heappop(ready)
        available=[fixed_cores[t]] if fixed_cores is not None else range(cores)
        choices=[]
        for c in available:
            start=ends[c]+(same_wait if orders[c] else 0)
            for p in preds[t]:
                start=max(start,finishes[p]+(cross_wait*cross_factor if assigned[p]!=c else 0))
            choices.append((start+weights[t],c))
        end,c=min(choices)
        orders[c].append(t);ends[c]=end;finishes[t]=end;assigned[t]=c
        for nxt in sorted(succs[t]):
            degree[nxt]-=1
            if not degree[nxt]: heapq.heappush(ready,key(nxt))
    plan={'node_to_subgraph':{str(n):mapping[n] for n in sorted(mapping)},'core_schedules':orders}
    validate_task_order(derive_multicore_plan(data,plan))
    return plan,{'tasks':len(groups),'boundary_bytes_proxy':sum(byte_counts.values()),'estimated_makespan':max(ends)}


def convex_closure(members,preds,succs):
    """Include nodes lying on any directed path between proposed members."""
    def reach(adjacency):
        seen=set(members);stack=list(members)
        while stack:
            for nxt in adjacency[stack.pop()]:
                if nxt not in seen: seen.add(nxt);stack.append(nxt)
        return seen
    return reach(preds)&reach(succs)


def regroup(data,old_plan,result):
    graph=Graph(data)
    original={int(n):t for n,t in old_plan['node_to_subgraph'].items()}
    mapping=dict(original)
    diagnostic=diagnose({**result,'step3_by_task':{str(k):v for k,v in result['step3_by_task'].items()}})
    breakdown=diagnostic['chain_breakdown']; total=result['makespan']
    groups,preds,succs=quotient(graph,mapping)
    before=BoundaryTraffic(graph,groups).total()
    if diagnostic['largest_chain_task_fraction']>=0.6 and breakdown['compute_only']/total>=0.5:
        # Reuse the existing MIT-attributed depth-window/weak-component method.
        # Its placement is discarded: matched scheduler below determines cores.
        mapping={int(n):t for n,t in window_plan(data,result['num_cores'],window=10,sticky=0.5)['node_to_subgraph'].items()}
        route='global_branch_windows'; decisions=[{'window':10}]
    elif breakdown['transfer_only']/total>=0.5:
        route='shared_tensor_groups';decisions=[]
        traffic=BoundaryTraffic(graph,groups)
        tensor_order=sorted(traffic.sizes,key=lambda t:(-traffic.sizes[t]*max(0,len(traffic.consumers[t])-1),t))
        used=set()
        # Limit inspection as well as evaluations. Group up to four consumers
        # sharing a tensor across any cores; no old core-order constraint.
        for tensor in tensor_order[:32]:
            groups,preds,succs=quotient(graph,mapping)
            consumers={mapping[n] for n in graph.consumers[tensor]}
            order=topological(preds,succs);pos={t:i for i,t in enumerate(order)}
            available=sorted(consumers-used,key=lambda t:pos[t])
            for i in range(0,len(available),4):
                selected=set(available[i:i+4])
                if len(selected)<2: continue
                groups,preds,succs=quotient(graph,mapping)
                if not selected<=groups.keys(): continue
                if convex_closure(selected,preds,succs)!=selected:
                    decisions.append({'tensor':tensor,'tasks':sorted(selected),'status':'rejected_nonconvex'});continue
                saving=BoundaryTraffic(graph,groups).saving(selected,min(selected))
                if saving<=0: continue
                root=min(selected)
                mapping={n:root if t in selected else t for n,t in mapping.items()}
                quotient(graph,mapping)
                used.update(selected)
                decisions.append({'tensor':tensor,'tasks':sorted(selected),'saved_bytes':saving,'status':'merged'})
    else:
        route='critical_chain_groups';decisions=[]
        # Jointly contract consecutive blocks of four tasks along the observed
        # critical chain. Convex closure includes bypass paths, preventing cycles.
        total_work=sum(max(1,o['cycles']) for o in graph.ops.values())
        cap=2*total_work/result['num_cores']
        representatives={t:nodes[0] for t,nodes in groups.items()}
        chain=diagnostic['chain']
        for i in range(0,len(chain),4):
            groups,preds,succs=quotient(graph,mapping)
            selected={mapping[representatives[t]] for t in chain[i:i+4]}
            if len(selected)<2: continue
            closure=convex_closure(selected,preds,succs)
            work=sum(max(1,graph.ops[n]['cycles']) for t in closure for n in groups[t])
            if work>cap or len(closure)>12:
                decisions.append({'tasks':sorted(closure),'status':'rejected_size'});continue
            traffic=BoundaryTraffic(graph,groups);root=min(closure)
            saving=traffic.saving(closure,root)
            mapping={n:root if t in closure else t for n,t in mapping.items()}
            quotient(graph,mapping)
            decisions.append({'tasks':sorted(closure),'saved_bytes':saving,'status':'merged'})
    new_groups,_,_=quotient(graph,mapping)
    return mapping,{'route':route,'old_tasks':len(set(original.values())),'new_tasks':len(new_groups),
        'boundary_bytes_before':before,'boundary_bytes_after':BoundaryTraffic(graph,new_groups).total(),'decisions':decisions}


def make_candidate(data,old_plan,result,arm,index):
    if arm not in ('A','B','C') or index not in range(4): raise ValueError('invalid arm or setting')
    original={int(n):t for n,t in old_plan['node_to_subgraph'].items()}
    if arm=='C': mapping,metadata=regroup(data,old_plan,result)
    else: mapping,metadata=original,{'route':'old_partition'}
    fixed={t:c for c,order in enumerate(old_plan['core_schedules']) for t in order} if arm=='A' else None
    plan,estimates=schedule(data,mapping,result['num_cores'],SETTINGS[index],result['task_same_core_wait_cycles'],
        result['task_cross_core_wait_cycles'],result['bandwidth_bytes_per_cycle'],fixed)
    if arm in ('A','B'): assert plan['node_to_subgraph']==old_plan['node_to_subgraph']
    if arm=='A': assert all(set(new)==set(old) for new,old in zip(plan['core_schedules'],old_plan['core_schedules']))
    return plan,{'arm':arm,'setting_index':index,'setting':SETTINGS[index],**metadata,**estimates}
