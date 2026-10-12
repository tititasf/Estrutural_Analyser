"""Real engine checks against approved native CAD geometry."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import ezdxf
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from scripts.gerar_pl_dxf_stog import setup_doc,generate_pilar_zone
from scripts.visual_modes import apply_visual_mode
from src.core.formascia_design import filled,fv_sarrafo,split_fv_openings

OUT=ROOT/'scripts/arete/relatorios/20261005_formascia_integracao_vps/local'
OUT.mkdir(parents=True,exist_ok=True)
payload=json.loads((ROOT/'scripts/arete/relatorios/20261004_formascia_abcd_experimento/payload_SA_P1.json').read_text(encoding='utf8'))
results=[]
for width in (19,29,30,40):
    p=dict(payload,largura=width,nome=f'P-EX{width}')
    for zone in ('abcd','cima','grades'):
        d=setup_doc();m=d.modelspace()
        generate_pilar_zone(m,p,zone,visual_mode='MOLDE_1');apply_visual_mode(d,'MOLDE_1','PL')
        audit=d.audit();assert not audit.errors and not audit.fixes,(zone,width,audit.errors,audit.fixes)
        path=OUT/f'PL_{zone}_{width}.dxf';d.saveas(path)
        if zone=='abcd':
            assert len(m.query('MLINE'))>0
            assert len(m.query('LWPOLYLINE[layer=="FORMASCIA-FOLGA"]'))==4
            assert not any(e.dxf.text.startswith(('PD:','CHEGADA','SAÍDA')) for e in m.query('TEXT'))
            cd=[e for e in m.query('MLINE') if e.dxf.style_name=='SAR15']
            assert cd and all((len(e.vertices)==2)==(width>=30) for e in cd)
        if zone=='grades':
            triangles=m.query('LWPOLYLINE[layer=="FORMASCIA-REFORCOS"]')
            assert len(triangles)==4 and all(e.dxf.color==7 for e in triangles)
        results.append({'case':f'PL/{zone}/{width}','audit_errors':0,'audit_fixes':0,'entities':len(m)})

for label,pts,height in [
    ('rectangle',[(0,0),(305.5,0),(305.5,19),(0,19)],19),
    ('L',[(0,0),(325,0),(325,62),(300,62),(300,19),(0,19)],19),
    ('bevel',[(6,0),(87,0),(87,19),(0,19)],19),
    ('opening1',[(0,0),(180,0),(180,13),(100,13),(100,40),(0,40)],40),
    ('opening2',[(80,0),(205.5,0),(205.5,40),(0,40),(0,27),(80,27)],40)]:
    d=ezdxf.new('R2018');d.layers.new('NOMENCLATURA');m=d.modelspace()
    poly=Polygon(pts)
    fv_sarrafo(m,0,0,height,[poly.bounds[2]],[[{'x':x,'y':y} for x,y in pts]])
    strips=[filled(e) for e in m.query('MLINE')]
    overflow=sum(p.difference(poly).area for p in strips)
    assert overflow<1e-5,(label,overflow)
    if label.startswith('opening'):assert len(strips)==8
    d.saveas(OUT/f'FV_{label}.dxf')
    results.append({'case':f'FV/{label}','mlines':len(strips),'overflow_cm2':overflow})

shape=box(0,0,305.5,40).difference(box(100,13,180,27));parts=split_fv_openings(shape)
assert len(parts)==2 and all(not p.interiors for p in parts)
assert parts[0].intersection(parts[1]).area<1e-6
assert unary_union(parts).symmetric_difference(shape).area<1e-6
(OUT/'checks.json').write_text(json.dumps(results,indent=2),encoding='utf8')
print(json.dumps(results,indent=2))
