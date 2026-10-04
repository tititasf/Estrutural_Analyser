import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from portal.app.ficha_reader import ler_estado_pavimento
from portal.app.lv_ficha import montar_ficha_lv
obra=Path('/opt/cad-analyzer/DADOS-OBRAS/Obra_TREINO_1')
state=ler_estado_pavimento(obra,'13_PAV')
ficha=montar_ficha_lv(obra,'13_PAV','V306','para',state,include_svgs=False)
result={'db_path':state.get('db_path'),'cuts':ficha['cut_views'],
        'slabs':[s for s in state['slabs'] if s.get('name') in ('L328','L321','L326','L319')],
        'source':state.get('source_dxf')}
Path('/tmp/live_cut_sources.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('saved',state.get('db_path'))
