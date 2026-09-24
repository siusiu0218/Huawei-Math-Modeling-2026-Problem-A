"""Static graph features; no feature here is a simulated execution time."""
import heapq
from collections import Counter, defaultdict
from pathlib import Path
import sys

sys.dont_write_bytecode = True
A_ROOT = next(p for p in Path(__file__).resolve().parents
              if (p / 'code').is_dir() and (p / 'data/config.txt').is_file())
sys.path.insert(0, str(A_ROOT / 'code'))
from evaluation_validation import validate_graph
from stub_multicore_cut_and_schedule import (
    _build_op_adjacency, _contract_excluded_copy_nodes, EXCLUDED_COPY_TYPES,
)


class Graph:
    def __init__(self, data):
        validate_graph(data)
        self.data = data
        self.ops = {o['id']: o for o in data['ops']
                    if o['op'] not in EXCLUDED_COPY_TYPES}
        _, all_succs = _build_op_adjacency(data)
        self.preds, self.succs = _contract_excluded_copy_nodes(
            sorted(self.ops), all_succs)
        degree = {i: len(p) for i, p in self.preds.items()}
        ready = [i for i in degree if not degree[i]]
        heapq.heapify(ready)
        self.order = []
        while ready:
            i = heapq.heappop(ready)
            self.order.append(i)
            for j in sorted(self.succs[i]):
                degree[j] -= 1
                if not degree[j]:
                    heapq.heappush(ready, j)
        if len(self.order) != len(self.ops):
            raise ValueError('cycle in contracted operation graph')
        self.producers, self.consumers = defaultdict(set), defaultdict(set)
        tensor_ids = {t['id'] for t in data['tensors']}
        for edge in data['edges']:
            a, b = edge['source'], edge['target']
            if a in self.ops and b in tensor_ids:
                self.producers[b].add(a)
            if a in tensor_ids and b in self.ops:
                self.consumers[a].add(b)


def analyze_graph(data):
    graph = Graph(data)
    path, level = {}, {}
    for i in graph.order:
        path[i] = graph.ops[i]['cycles'] + max(
            (path[p] for p in graph.preds[i]), default=0)
        level[i] = 1 + max((level[p] for p in graph.preds[i]), default=0)
    cycles = sum(o['cycles'] for o in graph.ops.values())
    critical = max(path.values(), default=0)
    shared = [t for t in data['tensors'] if len(graph.consumers[t['id']]) > 1]
    # Input means an operand of an operation, not exclusively a DDR graph input.
    return {
        'total_ops': len(data['ops']), 'compute_ops': len(graph.ops),
        'tensors': len(data['tensors']), 'original_edges': len(data['edges']),
        'compute_edges': sum(map(len, graph.succs.values())),
        'compute_cycles': cycles,
        'pipe_m_cycles': sum(o['cycles'] for o in graph.ops.values() if o['pipe'] == 'PIPE_M'),
        'pipe_v_cycles': sum(o['cycles'] for o in graph.ops.values() if o['pipe'] == 'PIPE_V'),
        'critical_compute_cycles': critical,
        'work_to_critical_ratio': cycles / critical if critical else 0,
        'max_level_width': max(Counter(level.values()).values(), default=0),
        'fork_ops': sum(len(s) > 1 for s in graph.succs.values()),
        'join_ops': sum(len(p) > 1 for p in graph.preds.values()),
        'shared_input_tensors': len(shared),
        'shared_input_bytes': sum(t['size'] for t in shared),
        'max_tensor_bytes': max((t['size'] for t in data['tensors']), default=0),
        'tensor_bytes_sum': sum(t['size'] for t in data['tensors']),
    }


def select_cases(rows):
    """Two cases per size quartile, alternating tune/holdout; no outcomes used."""
    ordered = sorted(rows, key=lambda r: (r['compute_ops'], r['case']))
    if len(ordered) < 8:
        raise ValueError('representative selection requires at least eight cases')
    chosen = []
    for q in range(4):
        band = ordered[len(ordered)*q//4:len(ordered)*(q+1)//4]
        # First quartile includes the smallest; fourth includes the largest.
        anchor = band[-1] if q == 3 else band[0]
        keys = ('work_to_critical_ratio', 'shared_input_bytes', 'max_level_width')
        ranges = {k: max(r[k] for r in band) - min(r[k] for r in band) for k in keys}
        def distance(row):
            return sum(abs(row[k] - anchor[k]) / (ranges[k] or 1) for k in keys)
        other = max((r for r in band if r['case'] != anchor['case']),
                    key=lambda r: (distance(r), r['case']))
        for n, row in enumerate((anchor, other)):
            chosen.append({
                'case': row['case'], 'split': 'tune' if n == 0 else 'holdout',
                'size_quartile': q + 1,
                'reason': 'size anchor' if n == 0 else 'largest normalized structural distance from anchor',
            })
    return chosen
