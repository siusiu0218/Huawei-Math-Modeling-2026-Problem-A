"""Freeze scene-B development/check cases using static graph features only."""
import hashlib
import json
import sys
from pathlib import Path

SOLUTION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOLUTION / 'src'))
from graph_analysis import Graph, analyze_graph
from component_scheduler import independent_components
from result_paths import result_path


def main():
    out = result_path('problem_2/design_v001/exp057_20260925_static_selection')
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for path in sorted((SOLUTION.parent / 'data').glob('case_*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        graph = Graph(data)
        row = {'case': path.stem, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               **analyze_graph(data), 'components': len(independent_components(graph))}
        tensors = {t['id']: t for t in data['tensors']}
        incident = {i: set() for i in graph.ops}
        for edge in data['edges']:
            a, b = edge['source'], edge['target']
            if a in incident and b in tensors:
                incident[a].add(b)
            if b in incident and a in tensors:
                incident[b].add(a)
        row['max_op_capacity_ratio'] = max((
            sum(tensors[t]['size'] for t in ids if tensors[t]['pos'] == pos) / cap
            for ids in incident.values() for pos, cap in [('UB', 131072), ('L1', 524288)]), default=0)
        rows.append(row)
    ordered = sorted(rows, key=lambda r: (r['compute_ops'], r['case']))
    rank = {r['case']: i for i, r in enumerate(ordered)}
    groups = {}
    for row in rows:
        label = ('small' if rank[row['case']] < len(rows)//2 else 'large') + (
            '_connected' if row['components'] == 1 else '_components')
        row['stratum'] = label
        if row['case'] not in ('case_093', 'case_078'):
            groups.setdefault(label, []).append(row)
    selected = []
    for label, group in sorted(groups.items()):
        # Within each size/connectivity stratum prioritize capacity pressure,
        # then shared bytes and graph size, with deterministic ID tie-break.
        candidates = sorted(group, key=lambda r: (-r['max_op_capacity_ratio'],
                            -r['shared_input_bytes'], r['compute_ops'], r['case']))
        if len(candidates) < 2:
            raise ValueError(f'insufficient cases in {label}')
        for split, row in zip(('development', 'check'), candidates[:2]):
            selected.append({'case': row['case'], 'split': split, 'stratum': label})
    result = {'problem': 2, 'status': 'frozen_before_new_scene_b_evaluation',
              'selection_rule': 'Size median crossed with one/multiple weak components; top two by maximum per-op capacity ratio, shared input bytes descending, compute_ops and case ascending. First development, second check.',
              'limitation': 'All graphs were already evaluated in Q1. Check means unused for scene-B tuning, not unseen graph data or a fully independent external test.',
              'pilot_development': ['case_093', 'case_078'], 'selected': selected,
              'cores': [2,3,4,5], 'generation_timeout': 30, 'evaluation_timeout': 180,
              'blocks_per_core': 4, 'candidates_per_method': 1, 'automatic_retries': 0,
              'features': rows,
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out / 'selection.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    print(json.dumps(selected, ensure_ascii=False, indent=2))
    for item in selected:
        r = next(r for r in rows if r['case'] == item['case'])
        print(r['case'], r['compute_ops'], r['components'], r['max_op_capacity_ratio'])


if __name__ == '__main__':
    main()
