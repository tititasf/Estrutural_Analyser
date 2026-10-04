"""Read-only QA of current inventory: overlap, openings, contracts and grouping."""
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
if len(sys.argv) > 3:
    import importlib.util
    spec=importlib.util.spec_from_file_location('src.core.lv_cut_inventory',sys.argv[3])
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[spec.name]=module
from portal.app.ficha_reader import ler_estado_pavimento,listar_itens_n1
from portal.app.lv_ficha import montar_ficha_lv
from src.core.lv_n3_cut_contract import build_cut_contract
from src.core.lv_cut_equivalence import section_signature

obra,output=Path(sys.argv[1]),Path(sys.argv[2])
state=ler_estado_pavimento(obra,'13_PAV')
rows=[]; errors=[]; pair_count=0; exclusion_count=0
for behavior in ('para','passa'):
    beams=sorted({i['beam_name'] for s in ('a','b') for i in listar_itens_n1(state,f'lateral_{s}_{behavior}')})
    for beam in beams:
        f=montar_ficha_lv(obra,'13_PAV',beam,behavior,state,include_svgs=False)
        segments={s['id']:s for d in f['sides'].values() for s in d['segments']}
        signatures=[]
        for cut in f['cut_views']:
            try:
                contract=build_cut_contract(cut)
                cut['qa_contract']=contract
                signatures.append(section_signature(contract))
            except ValueError as exc:
                errors.append(dict(beam=beam,cut=cut['id'],reason=str(exc)))
            for pair in cut['pairs']:
                pair_count+=1
                start,end=pair['start'],pair['end']; length=math.dist(start,end)
                axis=[(end[i]-start[i])/length for i in (0,1)]
                project=lambda p:sum(p[i]*axis[i] for i in (0,1))
                ranges=[sorted(project(p) for p in segments[pair[s+'_id']]['points']) for s in ('a','b')]
                lo,hi=max(r[0] for r in ranges),min(r[-1] for r in ranges)
                if hi-lo<=.5 or min(project(start),project(end))<lo-.01 or max(project(start),project(end))>hi+.01:
                    errors.append(dict(beam=beam,cut=cut['id'],reason='pair_outside_common_interval'))
                for side in ('a','b'):
                    segment=segments[pair[side+'_id']]
                    pts=segment['points']
                    # Independent audit for straight polylines; fail explicitly
                    # instead of pretending an envelope proves a bent interval.
                    origin,last=pts[0],pts[-1]; full=math.dist(origin,last)
                    if abs(sum(math.dist(a,b) for a,b in zip(pts,pts[1:]))-full)>.01:
                        errors.append(dict(beam=beam,reason='bent_segment_requires_edge_audit'))
                        continue
                    direction=[(last[i]-origin[i])/full for i in (0,1)]
                    pp=sorted(sum((p[i]-origin[i])*direction[i] for i in (0,1)) for p in (start,end))
                    for opening in segment.get('beam_openings') or []:
                        position,width=opening.get('position_cm'),opening.get('width_cm')
                        if position is None or width is None: continue
                        overlap=min(pp[1],position+width)-max(pp[0],position)
                        if overlap>.5:
                            errors.append(dict(beam=beam,cut=cut['id'],reason='pair_inside_opening',overlap_cm=overlap))
        if len(signatures)!=len(set(signatures)):
            errors.append(dict(beam=beam,reason='duplicate_section'))
        diag=f['cut_inventory']; exclusion_count+=len(diag.get('opening_exclusions') or [])
        rows.append(dict(beam=beam,behavior=behavior,cuts=f['cut_views'],diagnostics=diag,segments=segments))
result=dict(rows=rows,errors=errors,pairs=pair_count,opening_exclusions=exclusion_count,
            cuts=sum(len(r['cuts']) for r in rows))
output.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf8')
print({k:v for k,v in result.items() if k!='rows'})
if errors: raise SystemExit(1)
