"""Real bounded atomic Jev contact check with source geometry and withdrawal."""
import argparse
import copy
import json
import statistics
from pathlib import Path
from scripts.arete.jev_sa_second_read import MODEL, validate_request, verify_source_dxf, run as call_jev
from scripts.arete.jev_calibration.hashing import sha256_json
from scripts.arete.jev_calibration.runner import api_payload, sanitize_error
from scripts.arete.jev_source_events_v9 import boundary_distance

CASES=(('V409','2CC',[2099.09,2713.025],'33B'),
       ('V420','2F6',[4708.59,2972.025],'351'),
       ('V420','2F8',[4708.59,3188.025],'770'),
       ('V409','2CC',[2099.09,2393.025],'519'))

def geometry(e):
    return {k:e[k] for k in ('handle','etype','points','closed')}

def prepare(folder):
    events=json.loads((folder/'SOURCE-EVENTS.json').read_text(encoding='utf8'))
    check=dict(events);check.pop('sha256',None)
    if sha256_json(check)!=events['sha256']:raise ValueError('Evidence integrity failed')
    verify_source_dxf(folder/'source/14_PAV_VPS.dxf',events['source_dxf_sha256'])
    items=[]
    for beam,wall,at,handle in CASES:
        row=next(r for r in events['records'] if r['beam_locator']==beam and r['wall_handle'].upper()==wall and r['at']==at)
        entity=next(e for e in row['entities'] if e['handle'].upper()==handle)
        state={'coordinate_system':'Cartesian CAD XY; all coordinates use same units',
               'target_endpoint':at,'candidate':geometry(entity)}
        control=copy.deepcopy(state);control['candidate']['points']=[];control['candidate']['closed']=None
        request={'schema':'jev_sa_second_read_request/1',
            'identity':{'project_id':'jev_v9_baseline_14pav','pavimento':'14_PAV','classe':'LV',
                'item':beam,'campo':'source_endpoint_candidate_contact','source_dxf_sha256':events['source_dxf_sha256']},
            'baseline_sa':None,'use_context':'QA_B1',
            'question':{'instructions':'Determine only whether target_endpoint lies on the boundary or line segments of candidate using its listed XY points. Consecutive points form straight edges; closed true also connects last to first. Touch requires Euclidean distance at most 0.01 CAD units to an edge or point. Being inside a polygon or near an edge does not count as touching. If candidate coordinates are missing, return INSUFFICIENT. Do not infer pillar identity, beam ownership or PARA/PASSA behavior.',
                'criteria':{'TOUCH':'Listed complete coordinates prove boundary distance at most 0.01 CAD units.',
                            'SEPARATE':'Listed complete coordinates prove boundary distance greater than 0.01 CAD units.',
                            'INSUFFICIENT':'Missing or unusable coordinates prevent determining contact.'}},
            'evidence':state,'controls':[{'id':'candidate_geometry_removed','evidence':control,'expected_choice':'INSUFFICIENT'}]}
        validate_request(request)
        distance=boundary_distance(at,entity['points'],entity['closed'])
        items.append({'request':request,'request_sha256':sha256_json(request),
            'payload_sha256':sha256_json(api_payload(request)),'source_encounter_id':row['encounter_id'],
            'candidate_handle':handle,'reference_method':'independent deterministic boundary distance, not SA/Jev',
            'reference_distance':distance,'reference_choice':'TOUCH' if distance<=0.01 else 'SEPARATE'})
    return {'schema':'jev_atomic_contact_freeze/v9','model':MODEL,'cases':items,'max_calls':8,
        'sa_in_state':False,'reference_in_state':False,'selection':'Two contacts and two near-but-separated geometries; purposive diagnostic, not random sample.'}

def relative_coordinates(freeze):
    result=copy.deepcopy(freeze)
    result['cases']=result['cases'][2:]
    for case in result['cases']:
        request=case['request']
        for state in [request['evidence'],*[c['evidence'] for c in request['controls']]]:
            ox,oy=state['target_endpoint']
            state['candidate']['points']=[[round(p[0]-ox,6),round(p[1]-oy,6)] for p in state['candidate']['points']]
            state['target_endpoint']=[0.0,0.0]
            state['coordinate_system']='Cartesian CAD XY translated so target endpoint is origin; original CAD units unchanged'
        validate_request(request)
        case['request_sha256']=sha256_json(request)
        case['payload_sha256']=sha256_json(api_payload(request))
    result['max_calls']=4
    result['selection']='Same two separated candidate entities; coordinates translated to endpoint origin. No new semantic evidence.'
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);ap.add_argument('--execute',action='store_true');ap.add_argument('--relative',action='store_true');args=ap.parse_args()
    dest=args.folder/('atomic_contact_relative' if args.relative else 'atomic_contact');dest.mkdir(exist_ok=True)
    freeze=prepare(args.folder)
    if args.relative:freeze=relative_coordinates(freeze)
    fp=dest/'FREEZE.json'
    if fp.exists() and json.loads(fp.read_text(encoding='utf8'))!=freeze:raise ValueError('Frozen experiment changed')
    fp.write_text(json.dumps(freeze,ensure_ascii=False,indent=2),encoding='utf8')
    if not args.execute:print(f"Frozen {len(freeze['cases'])} requests, maximum {freeze['max_calls']} real calls.");return
    rows=[]
    for i,case in enumerate(freeze['cases'],1):
        path=dest/f'RESULT-{i:02d}.json'
        if path.exists():reply=json.loads(path.read_text(encoding='utf8'))
        else:
            try:reply=call_jev(case['request'])
            except Exception as exc:
                (dest/'ERROR.json').write_text(json.dumps({'case':i,'error':sanitize_error(exc)}),encoding='utf8');raise RuntimeError(sanitize_error(exc)) from None
            path.write_text(json.dumps(reply,ensure_ascii=False,indent=2),encoding='utf8')
        if reply.get('request_sha256')!=case['request_sha256'] or reply.get('model')!=MODEL:
            raise ValueError('Cached response has a different request/model identity')
        rows.append({'case':i,'reference_choice':case['reference_choice'],'response':reply})
    report={'schema':'jev_atomic_contact_results/v9','cases':rows,'max_calls':freeze['max_calls'],
        'quality_gain_measured':False,'scope':'Atomic source-contact arithmetic; not SA interpretation accuracy or end-to-end hybrid gain.'}
    (dest/'RESULTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'cases_saved':len(rows),'model':MODEL,'quality_gain_measured':False}))

if __name__=='__main__':main()
