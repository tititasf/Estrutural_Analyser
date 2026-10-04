"""Audit every published pair footprint on the actual structural transform."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if len(sys.argv) > 3:
    import importlib.util
    spec=importlib.util.spec_from_file_location('portal.app.lv_cut_map',sys.argv[3])
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    sys.modules[spec.name]=module
from portal.app import ficha_reader, lv_ficha
from portal.app.lv_cut_map import structural_payload
obra=Path(sys.argv[1]); state=ficha_reader.ler_estado_pavimento(obra,'13_PAV')
rows=[]
for behavior in ('para','passa'):
    names=sorted({i['beam_name'] for side in ('a','b') for i in ficha_reader.listar_itens_n1(state,f'lateral_{side}_{behavior}')})
    for beam in names:
        data=lv_ficha.montar_ficha_lv(obra,'13_PAV',beam,behavior,state,include_svgs=False)
        try:
            payload=structural_payload(obra,'13_PAV','5aecf77e-e593-485f-8f8e-7244799fc3e8',state,beam,behavior,data)
            expected=sum(len(c.get('pairs') or []) for c in data['cut_views'])
            assert payload and payload['mapped_pairs']==expected
            assert len(payload['highlights']) == expected+sum(len(s['segments']) for s in data['sides'].values())
            assert all(len(h['points'])==4 for h in payload['highlights'] if h['kind']=='cut_pair')
            rows.append(dict(beam=beam,behavior=behavior,pairs=expected,segments=len(payload['highlights'])-expected,unlocated=payload['unlocated_cuts'],verdict='PASS'))
        except Exception as exc:
            rows.append(dict(beam=beam,behavior=behavior,verdict='FAIL',reason=str(exc)))
result=dict(rows=rows,failures=[r for r in rows if r['verdict']=='FAIL'])
Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('rows',len(rows),'failures',result['failures'],'pairs',sum(r.get('pairs',0) for r in rows))
