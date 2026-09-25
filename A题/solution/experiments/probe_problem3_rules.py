"""Reproducible diagnostic graphs evaluated by untouched official evaluators."""
import json
import sys
from pathlib import Path

SOLUTION = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(SOLUTION.parent / 'code'), str(SOLUTION / 'tests')]
from multicore_cut_evaluate_problem_3 import evaluate_problem_3
from multicore_cut_evaluate_problem_2 import evaluate_scene_b


def reads(sequences, sizes):
    """Each core consumes its listed input tensors in subgraph priority order."""
    tensors = [{'id': 1000+t, 'pos': 'UB', 'size': s} for t, s in sizes.items()]
    ops, edges, mapping, orders = [], [], {}, []
    for seq in sequences:
        order = []
        for t in seq:
            oid = len(ops)+1
            ops.append({'id': oid, 'op': 'ADD', 'pipe': 'PIPE_V', 'cycles': 1})
            edges.append({'source': 1000+t, 'target': oid})
            mapping[str(oid)] = oid
            order.append(oid)
        orders.append(order)
    return {'ops': ops, 'tensors': tensors, 'edges': edges}, {
        'node_to_subgraph': mapping, 'core_schedules': orders}


def evaluate(graph, plan, cache_capacity=1048576, cache_bw=250):
    args = (graph, plan, 60, {'L1': 524288, 'UB': 131072}, 500)
    return evaluate_scene_b(*args), evaluate_problem_3(*args, cache_capacity, cache_bw)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    cases = {
        'simultaneous': ([[1], [1]], {1: 600}, 1048576, 250),
        'delayed_hit': ([[1], [2, 1]], {1: 600, 2: 6000}, 1048576, 250),
        'oversize': ([[1], [2, 1]], {1: 600, 2: 6000}, 500, 250),
        'fifo': ([[1, 2], [3, 1, 4]], {1: 600, 2: 1200, 3: 6000, 4: 600}, 1800, 250),
        'zero': ([[1]], {1: 0}, 1048576, 250),
        'empty_access': ([[]], {}, 1048576, 250),
    }
    summary = {}
    for name, (seq, sizes, cap, bw) in cases.items():
        graph, plan = reads(seq, sizes)
        a, b = evaluate(graph, plan, cap, bw)
        payload = {'graph': graph, 'plan': plan, 'diagnostic_cache_capacity': cap,
                   'diagnostic_cache_bandwidth': bw, 'no_l2': a, 'cache': b}
        (out / f'{name}.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
        summary[name] = {'no_l2': a['makespan'], 'cache': b['makespan'],
                         'stats': b['cache_stats'], 'events': b['cache_events'],
                         'movement_equal': a['data_movement_bytes'] == b['data_movement_bytes']}
    (out/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
