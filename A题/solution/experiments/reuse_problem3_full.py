"""Reuse only hash-verified results from identical inputs and original evaluators."""
import json
import shutil
from pathlib import Path
from run_problem3_pair import sha

def reuse(manifest, out, selection):
    for item in manifest['items']:
        for record in selection['reuse'].get(f"{item['case']}_n{item['cores']}", []):
            source=Path(record['source'])
            assert sha(source)==record['result_sha256']
            assert sha(record['source_manifest'])==record['source_manifest_sha256']
            assert record['plan_sha256']==item['plan_sha256']
            target=out/'metrics'/f"{item['case']}_n{item['cores']}_{record['mode']}_attempt1.json"
            shutil.copy2(source,target)
            item['attempts'].append(dict(record,status='success',reused=True,
                seconds=0,result=str(target.relative_to(out))))
