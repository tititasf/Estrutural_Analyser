import json
from pathlib import Path
d=json.loads(Path('scripts/arete/relatorios/20260930_lv_visao_corte/validated_cut_inventory.json').read_text(encoding='utf8'))
from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError
for r in d['rows']:
    for i,c in enumerate(r['cuts']):
        try: build_cut_contract(c)
        except CutContractError as exc:
            print(r['beam'],i,str(exc),json.dumps(c.get('profiles') or c.get('source_cut'),ensure_ascii=False)[:7000])
