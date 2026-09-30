"""Source-only endpoint evidence. Proximity is never a PARA/PASSA decision."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from scripts.arete.jev_calibration.cad_source import DxfParserCadSource
from scripts.arete.jev_calibration.hashing import sha256_json

def boundary_distance(at, points, closed=False):
    """Euclidean distance to entity edges, not its bounding box/interior."""
    if not points: return None
    if not all(math.isfinite(float(x)) for p in [at,*points] for x in p[:2]):
        raise ValueError('Nonfinite CAD coordinate')
    segments=list(zip(points,points[1:]))
    if closed and len(points)>2 and points[-1]!=points[0]:segments.append((points[-1],points[0]))
    if not segments:return math.dist(at[:2],points[0][:2])
    best=float('inf')
    for a,b in segments:
        dx,dy=b[0]-a[0],b[1]-a[1];length=dx*dx+dy*dy
        t=max(0,min(1,((at[0]-a[0])*dx+(at[1]-a[1])*dy)/length)) if length else 0
        best=min(best,math.hypot(at[0]-a[0]-t*dx,at[1]-a[1]-t*dy))
    return best

def run(folder:Path, inventory:Path):
    source=DxfParserCadSource(folder/'source/14_PAV_VPS.dxf')
    inv=json.loads(inventory.read_text(encoding='utf8'))
    if inv['source_dxf_sha256']!=source.dxf_sha256:raise ValueError('Different source inventory')
    check=dict(inv);check.pop('inventory_sha256',None)
    if sha256_json(check)!=inv['inventory_sha256']:raise ValueError('Inventory tampered')
    rows=[]
    for enc in inv['encounters']:
        if enc.get('beam') not in ('V409','V420'):continue
        at=enc['at'];wall=source.by_handle(enc['wall_handle'])
        if wall is None:raise ValueError('Missing source wall')
        # Exact source endpoints must agree; labels/ownership remain hypotheses.
        identity_valid=any(math.dist(at[:2],p[:2])<=0.002 for p in (wall.points[:1]+wall.points[-1:]))
        nearby=source.entities_near(*at[:2],80)
        entities=[]
        for entity in sorted(nearby,key=lambda e:e.handle):
            item=asdict(entity)
            item['boundary_distance']=boundary_distance(at,entity.points,entity.closed)
            item['touches_endpoint']=item['boundary_distance'] is not None and item['boundary_distance']<=0.01
            entities.append(item)
        rows.append({'encounter_id':enc['encounter_id'],'beam_locator':enc['beam'],
            'face_locator':enc.get('face'),'locator_ownership_validated':False,
            'at':at,'wall_handle':enc['wall_handle'],'wall':asdict(wall),
            'exact_source_endpoint':identity_valid,'entities':entities,
            'query_radius_cad_units':80,'truncated':False,
            'semantics':{'pillar_face':None,'short_face':None,'miolo':None,'cede_para':None},
            'semantic_verdict':None,'status':'SOURCE_GEOMETRY_ONLY'})
    result={'schema':'jev_source_endpoint_evidence/v9','source_dxf_sha256':source.dxf_sha256,
        'source_inventory_sha256':inv['inventory_sha256'],'n1_used':False,
        'source_inventory_is_frozen_locator':True,'records':rows,
        'counts':dict(Counter(r['beam_locator'] for r in rows)),
        'note':'Neighbourhood evidence; no proof of beam ownership or pillar semantics. No API calls.'}
    result['sha256']=sha256_json(result)
    target=folder/'SOURCE-EVENTS.json'
    if target.exists():raise FileExistsError(target)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return {'records':len(rows),'counts':result['counts'],
        'endpoint_mismatches':sum(not r['exact_source_endpoint'] for r in rows),
        'source_only':True,'bytes':target.stat().st_size,'api_calls':0}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('folder',type=Path);ap.add_argument('inventory',type=Path)
    args=ap.parse_args();print(json.dumps(run(args.folder,args.inventory),indent=2))
