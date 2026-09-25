"""Audit and report one complete 500-pair Q3 full baseline."""
import csv
import json
from pathlib import Path
import sys
from fractions import Fraction
from run_problem3_pair import sha
from run_problem2 import save

SOLUTION=Path(__file__).resolve().parents[1]


def main():
    out=Path(sys.argv[1])
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    summary=json.loads((out/'summary.json').read_text(encoding='utf-8'))
    selection=json.loads((out/'source/selection.json').read_text(encoding='utf-8'))
    rows=list(csv.DictReader((out/'comparison.csv').open(encoding='utf-8-sig')))
    assert manifest['status']=='completed' and len(rows)==500 and not summary['failures']
    assert manifest['hashes_before']==manifest['hashes_after']
    for path,digest in manifest['hashes_before'].items():assert sha(path)==digest
    for rel,digest in manifest['archive_hashes'].items():assert sha(out/rel)==digest
    expected={(i['case'],n) for i in selection['cases'] if i['role']=='full' for n in range(1,6)}
    assert {(r['case'],int(r['cores'])) for r in rows}==expected
    assert len({(r['case'],r['cores']) for r in rows})==500
    origin=SOLUTION/'outputs/09_problem2/raw/problem_2/v011/exp109_20260926_active_full'
    old=list(csv.DictReader((SOLUTION/'outputs/09_problem2/v011_summary_20260926/comparison.csv').open(encoding='utf-8-sig')))
    old_map={(r['case'],int(r['cores'])):r for r in old}
    events=[];records=0;equal_full=0;input_hashes={}
    for item in manifest['items']:
        stem=f"{item['case']}_n{item['cores']}"
        assert sha(out/'plans'/f'{stem}.json')==item['plan_sha256']==sha(item['plan_source'])
        current={mode:[r for r in item['attempts'] if r['mode']==mode][-1] for mode in ('no_l2','cache')}
        records+=len(item['attempts'])
        for r in current.values():
            assert r['status']=='success' and sha(out/r['result'])==r['result_sha256']
            assert r['plan_sha256']==item['plan_sha256']
            input_hashes[str(out/r['result'])]=sha(out/r['result'])
        a,b=[json.loads((out/current[mode]['result']).read_text(encoding='utf-8')) for mode in ('no_l2','cache')]
        if item['cores']>1:
            old_path=origin/'metrics'/f'{stem}.json'
            old_result=json.loads(old_path.read_text(encoding='utf-8'))
            assert a==old_result
            equal_full+=1
            input_hashes[str(old_path)]=sha(old_path)
        else:
            assert a['makespan']==int(old_map[item['case'],2]['single_makespan'])
        row=next(r for r in rows if r['case']==item['case'] and int(r['cores'])==item['cores'])
        assert int(row['no_l2_makespan'])==a['makespan'] and int(row['cache_makespan'])==b['makespan']
        assert float(row['byte_hit_rate'])==b['cache_stats']['hit_rate']
        assert a['data_movement_bytes']==b['data_movement_bytes']
        assert all(t['copy_in_start']-t['copy_out_end']>=500 for t in b['cross_core_transfers'])
        assert b['cache_capacity_bytes']==1048576
        for record in current.values():
            if record.get('reused'):
                assert sha(record['source'])==record['result_sha256']
                assert sha(record['source_manifest'])==record['source_manifest_sha256']
        diagnosis=json.loads((out/'metrics'/f'{stem}_diagnosis.json').read_text(encoding='utf-8'))
        for event in diagnosis['hit_completion_insert_events']:
            events.append({'case':item['case'],'cores':item['cores'],**event})
    for n in range(1,6):
        part=[r for r in rows if int(r['cores'])==n]
        exact=sum((Fraction(int(r['no_l2_makespan']),int(r['cache_makespan'])) for r in part),Fraction(0))/100
        assert float(exact)==summary['by_cores'][n-1]['mean_speedup']
    save(out/'reinsertion_events.json',events)
    save(out/'audit.json',{'status':'passed','pairs':500,'evaluator_attempts':records,
        'official_inputs_sources_and_archives_unchanged':True,'same_plan_hashes_checked':True,
        'q2_full_result_matches':equal_full,'q2_single_reference_matches':100,
        'summary_fraction_recomputed':True,'fixed_config_hit_completion_insertions':len(events),
        'checked_result_hashes':input_hashes,'report_script_sha256':sha(__file__)})
    print(json.dumps({'audit':'passed','pairs':500,'reinsertion_events':len(events)}))

if __name__=='__main__':main()
