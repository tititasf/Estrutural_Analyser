"""Compare current portal and candidate module without modifying server sources."""
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, '/opt/cad-analyzer')
from portal.app.ficha_reader import ler_estado_pavimento, listar_itens_n1
from portal.app.lv_ficha import montar_ficha_lv

obra = Path('/opt/cad-analyzer/DADOS-OBRAS/Obra_TREINO_1')
state = ler_estado_pavimento(obra, '13_PAV')

def inventory():
    result = []
    for behavior in ('para', 'passa'):
        beams = sorted({i['beam_name'] for side in ('a','b')
                        for i in listar_itens_n1(state, f'lateral_{side}_{behavior}')})
        for beam in beams:
            f = montar_ficha_lv(obra,'13_PAV',beam,behavior,state,include_svgs=False)
            result.append(dict(beam=beam,behavior=behavior,cuts=f['cut_views']))
    return result

before = inventory()
spec = importlib.util.spec_from_file_location('src.core.lv_cut_inventory', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.modules[spec.name] = module
after = inventory()
result = dict(before=before,after=after,
              slab_regions={s['name']:s.get('slab_steps') for s in state['slabs'] if s.get('slab_steps')})
Path(sys.argv[2]).write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf8')
for b,a in zip(before,after):
    if len(b['cuts']) != len(a['cuts']):
        print(a['behavior'],a['beam'],len(b['cuts']),'->',len(a['cuts']),flush=True)
print('TOTAL',sum(len(r['cuts']) for r in before),'->',sum(len(r['cuts']) for r in after))
