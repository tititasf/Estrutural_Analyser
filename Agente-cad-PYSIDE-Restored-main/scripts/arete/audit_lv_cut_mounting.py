"""Read live SA, audit each generated mounting in a separate derived folder."""
from pathlib import Path
import sys,json,importlib.util
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from portal.app.ficha_reader import ler_estado_pavimento,listar_itens_n1
from portal.app.lv_ficha import montar_ficha_lv

def staged(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

if len(sys.argv)>3:
    builder=staged('src.core.lv_n3_cut_contract',sys.argv[3]).build_cut_contract
    draw=staged('scripts.arete.lv_n3_cut_draw',sys.argv[4])
    # Resolve shared motor/style assets in the installed tree, while running
    # the staged source. Never replace the active renderer during queued jobs.
    draw.__file__=str(Path(__file__).parent/'lv_n3_cut_draw.py')
    renderer=draw.generate
else:
    from src.core.lv_n3_cut_contract import build_cut_contract as builder
    from scripts.arete.lv_n3_cut_draw import generate as renderer
obra=Path(sys.argv[1]);root=Path(sys.argv[2]);root.mkdir(parents=True,exist_ok=True)
state=ler_estado_pavimento(obra,'13_PAV');rows=[]
for behavior in ('para','passa'):
    beams=sorted({i['beam_name'] for side in ('a','b') for i in listar_itens_n1(state,f'lateral_{side}_{behavior}')})
    for beam in beams:
        cuts=montar_ficha_lv(obra,'13_PAV',beam,behavior,state,include_svgs=False)['cut_views']
        for index,cut in enumerate(cuts,1):
            row={'beam':beam,'behavior':behavior,'vc':index,'id':cut['id']}
            try:
                c=builder(cut);doc=renderer(c,root/behavior/beam/f'VC{index}.dxf')
                assert not doc.audit().has_errors,'DXF audit'
                li=any(p['lower_slab'] for p in c['mounting'].values())
                levels=[] if li else [v for t,v in [(40,25),(90,75)] if all(p['h1_cm']>t for p in c['mounting'].values())]
                names=Counter(e.dxf.name for e in doc.modelspace().query('INSERT'))
                assert names['PAR_FUNDO_ESQ']==names['PAR_FUNDO_DIR']==(0 if li else 1)
                assert names['PAR_ESQ']==names['par_int_esq']==names['par_int_dir']==len(levels)
                row.update(status='generated',mounting=c['mounting'],central_axes_cm=levels,
                           hardware=dict(names),warnings=c['warnings'])
            except Exception as exc:row.update(status='blocked',reason=str(exc))
            rows.append(row)
result={'counts':dict(Counter(r['status'] for r in rows)),'rows':rows}
(root/'mounting_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(result['counts'],flush=True)
if any(r['status']=='blocked' for r in rows):sys.exit(1)
