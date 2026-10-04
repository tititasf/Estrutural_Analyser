"""Fotografa inventário publicado e contratos, sem gerar desenhos ou alterar SA."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from portal.app.ficha_reader import ler_estado_pavimento,listar_itens_n1
from portal.app.lv_ficha import montar_ficha_lv
from src.core.lv_n3_cut_contract import build_cut_contract
obra=Path(sys.argv[1]); estado=ler_estado_pavimento(obra,'13_PAV'); rows=[]
for behavior in ('para','passa'):
    beams=sorted({i['beam_name'] for side in ('a','b') for i in listar_itens_n1(estado,f'lateral_{side}_{behavior}')})
    for beam in beams:
        ficha=montar_ficha_lv(obra,'13_PAV',beam,behavior,estado,include_svgs=False)
        row={'beam':beam,'behavior':behavior,'cuts':ficha['cut_views'],'counts':{k:v for k,v in ficha.items() if 'count' in k or 'diagnos' in k}}
        for cut in row['cuts']:
            try: cut['qa_contract']=build_cut_contract(cut)
            except Exception as exc: cut['qa_error']=str(exc)
        rows.append(row); print(behavior,beam,len(row['cuts']),flush=True)
Path(sys.argv[2]).write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str),encoding='utf8')
