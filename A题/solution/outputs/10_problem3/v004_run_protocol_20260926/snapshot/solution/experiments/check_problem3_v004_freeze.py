"""Read-only check of the frozen v004 full-run protocol; never launches a run."""
import hashlib
import json
from pathlib import Path
import sys

S=Path(__file__).resolve().parents[1]
DEFAULT=S/'outputs/10_problem3/v004_run_protocol_20260926/freeze.json'


def check(path=DEFAULT):
    path=Path(path)
    expected=path.with_suffix('.sha256').read_text(encoding='utf-8').strip()
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise SystemExit('Frozen protocol JSON changed')
    frozen=json.loads(path.read_text(encoding='utf-8'))
    errors=[]
    for name,expected in frozen['file_hashes'].items():
        p=Path(name)
        if not p.is_file():errors.append('missing: '+name)
        elif hashlib.sha256(p.read_bytes()).hexdigest()!=expected:errors.append('changed: '+name)
    pairs={(c,n) for c in frozen['cases'] for n in frozen['cores']}
    expected={(f'case_{i:03}',n) for i in range(1,101) for n in range(1,6)}
    if pairs!=expected or len(frozen['cases'])!=100 or len(frozen['cores'])!=5:
        errors.append('coverage is not exactly 100 x 1--5')
    if frozen['candidates']!=['baseline','w4','w10','w16'] or frozen['sticky']!=0.5:
        errors.append('candidate policy changed')
    result={'status':'passed' if not errors else 'failed','files_checked':len(frozen['file_hashes']),
        'configurations':len(pairs),'experiment':frozen['planned_experiment'],'errors':errors,
        'note':'read-only freeze check; full evaluation not started by this command'}
    print(json.dumps(result,ensure_ascii=False))
    if errors:raise SystemExit(1)
    return result


if __name__=='__main__':check(Path(sys.argv[1]) if len(sys.argv)>1 else DEFAULT)
