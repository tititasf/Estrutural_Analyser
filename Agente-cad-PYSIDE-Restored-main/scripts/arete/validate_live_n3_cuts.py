"""Auditoria por corte do estado publicado, sem modificar N1 ou fichas N2."""
import json
from pathlib import Path
import sys
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from portal.app.ficha_reader import ler_estado_pavimento, listar_itens_n1
from portal.app.lv_ficha import montar_ficha_lv
from portal.app.lv_n3_cuts import resolve
from src.core.lv_n3_cut_contract import build_cut_contract

obra = Path(sys.argv[1])
output = Path(sys.argv[2])
estado = ler_estado_pavimento(obra, '13_PAV')
rows = []
for behavior in ('para', 'passa'):
    beams = sorted({i['beam_name'] for side in ('a', 'b')
                    for i in listar_itens_n1(estado, f'lateral_{side}_{behavior}')})
    for beam in beams:
        ficha = montar_ficha_lv(obra, '13_PAV', beam, behavior, estado, include_svgs=False)
        for index, cut in enumerate(ficha['cut_views'], 1):
            row = dict(beam=beam, behavior=behavior, vc=index, id=cut['id'])
            try:
                contract = build_cut_contract(cut)
                layer = resolve(obra, '13_PAV', behavior, cut)
                assert '<svg' in layer['svg'], 'SVG ausente'
                row.update(status='generated', fingerprint=contract['fingerprint'],
                           warnings=contract['warnings'], width=contract['width_cm'],
                           height=contract['height_cm'], slabs=contract['slabs'])
            except Exception as exc:
                row.update(status='blocked', reason=str(exc))
            rows.append(row)
        print(behavior, beam, len(ficha['cut_views']), flush=True)
result = dict(scope='Obra_TREINO_1/13_PAV', counts=dict(Counter(r['status'] for r in rows)), rows=rows)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
print(result['counts'], flush=True)
if any(r['status']=='blocked' for r in rows): sys.exit(1)
