import json,copy
from pathlib import Path
from src.core.beam_corridor_recovery import recover_pillar_beam_corridors,pillar_support_boxes
from src.core.pillar_face_beams import enrich_pillar_report_with_beams,reconcile_beam_fundo_facts
from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar
from scripts.arete.pil_agentic_highlight_draw import render_agentic_svg
from scripts.arete.g2v_harness import rasterizar_svgs
out=Path('scripts/arete/relatorios/20261009_reprocessamento/tag_candidate_audit');out.mkdir(exist_ok=True)
c=json.load(open(out.parent/'tag_context_complete.json',encoding='utf-8'));dxf=out.parent/'review_source_tower.dxf'
beams=copy.deepcopy(c[4]);pillars=copy.deepcopy(c[5]);report={p['name']:p for p in pillars}
reconcile_beam_fundo_facts(beams)
r,m=recover_pillar_beam_corridors(dxf,beams,pillar_support_boxes(pillars))
for b in beams:
 b.pop('_recovered_corridor',None);b.pop('_measured_corridor',None)
 if b['name'] in r:b['_recovered_corridor']=r[b['name']]
 if b['name'] in m:b['_measured_corridor']=m[b['name']]
enrich_pillar_report_with_beams(report,beams)
tables={p['name']:build_abcd_tables_from_pillar(p,slab_height_map=c[1],slab_nivel_map=c[2],slab_points_map=c[3],beams=beams) for p in pillars}
(out/'tables.json').write_text(json.dumps(tables,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'context.json').write_text(json.dumps([str(dxf),c[1],c[2],c[3],beams,pillars],ensure_ascii=False),encoding='utf-8')
for p in pillars:
 path=out/(p['name']+'.svg')
 path.write_text(render_agentic_svg(dxf,p['points'],tables[p['name']],layer='sa'),encoding='utf-8')
 png=rasterizar_svgs([path],lado_maior=2000)
 print(p['name'],tables[p['name']].get('geometry_type'),png,flush=True)
