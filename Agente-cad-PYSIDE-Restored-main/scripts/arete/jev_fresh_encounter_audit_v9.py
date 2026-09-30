"""Compare encounter identity against a new isolated SA run, never score truth."""
import json
import sys
from pathlib import Path
from collections import Counter
from scripts.arete.jev_calibration.adapters_lv_v8 import extract_four_contracts, match_encounter
from scripts.arete.jev_calibration.hashing import sha256_json
from scripts.arete.jev_calibration.catalog_v6 import PAVEMENT_SPECS_V6

def main():
    folder=Path(sys.argv[1]);baseline=json.loads((folder/'BASELINE-N1.json').read_text(encoding='utf8'))
    status=json.loads((folder/'BASELINE-STATUS.json').read_text(encoding='utf8'))
    if not all(status.get(k) for k in ('source_hash_match','snapshot_unchanged')) or status.get('isolation_leak_count')!=0:
        raise ValueError('Baseline execution provenance failed')
    inv=json.loads(Path(PAVEMENT_SPECS_V6['14_PAV']['inventory']).read_text(encoding='utf-8-sig'))
    check=dict(inv);check.pop('inventory_sha256',None)
    if sha256_json(check)!=inv['inventory_sha256']:raise ValueError('Inventory integrity failed')
    if inv['source_dxf_sha256']!=status['source_sha256_after']:raise ValueError('Source identity failed')
    beams={b['name']:b for b in baseline['beams_found']};records=[]
    for enc in inv['encounters']:
        if enc.get('beam') not in ('V409','V420'):continue
        # This locator is attached to a new run of exactly the same CAD bytes.
        # Do not claim the new experiment project is the persisted VPS project.
        source={**enc,'pavimento':'14_PAV','project_id':beams[enc['beam']]['project_id']}
        result=match_encounter(source=source,n1_contracts=extract_four_contracts(beams[enc['beam']]),
                              other_source_encounters=inv['encounters'])
        records.append({'source':source,'match':result})
    result={'schema':'jev_fresh_encounter_identity/v9','source_dxf_sha256':inv['source_dxf_sha256'],
        'same_cad_source':True,'n1_run':'BASELINE-N1.json','records':records,
        'counts':dict(Counter(r['match']['status'] for r in records)),
        'pack_ready_count':sum(bool(r['match'].get('pack_ready')) for r in records),
        'api_calls':0,'quality_gain_measured':False,
        'note':'Identity/eligibility only. Locator ownership remains unvalidated; pack_ready alone is not release authorization.'}
    result['sha256']=sha256_json(result)
    (folder/'FRESH-ENCOUNTER-AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))

if __name__=='__main__':main()
