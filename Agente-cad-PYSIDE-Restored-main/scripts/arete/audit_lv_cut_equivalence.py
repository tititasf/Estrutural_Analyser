"""Compara inventário bruto e agrupado; verifica vínculos por unidade, sem DB writes."""
import importlib.util
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from portal.app.ficha_reader import ler_estado_pavimento, listar_itens_n1
from portal.app.lv_ficha import montar_ficha_lv

if len(sys.argv) > 3:
    spec = importlib.util.spec_from_file_location('src.core.staged_equivalence', sys.argv[3])
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    group_equivalent_cuts = module.group_equivalent_cuts
else:
    from src.core.lv_cut_equivalence import group_equivalent_cuts

obra, output = Path(sys.argv[1]), Path(sys.argv[2])
estado = ler_estado_pavimento(obra, '13_PAV')
rows = []
for behavior in ('para', 'passa'):
    beams = sorted({i['beam_name'] for side in ('a', 'b')
                    for i in listar_itens_n1(estado, f'lateral_{side}_{behavior}')})
    for beam in beams:
        ficha = montar_ficha_lv(obra, '13_PAV', beam, behavior, estado, include_svgs=False)
        cuts = ficha['cut_views']
        grouped = group_equivalent_cuts(cuts)
        old_pairs = [p for c in cuts for p in c.get('pairs') or []]
        new_pairs = [p for c in grouped for p in c.get('pairs') or []]
        key = lambda p: json.dumps(p, sort_keys=True)
        assert set(map(key, old_pairs)) == set(map(key, new_pairs)), (beam, 'pares perdidos')
        old_ids = {e for c in cuts for e in c.get('evidence_ids') or []}
        new_ids = {e for c in grouped for e in c.get('evidence_ids') or []}
        assert old_ids == new_ids, (beam, 'evidências perdidas')
        rows.append(dict(beam=beam, behavior=behavior, before=len(cuts), after=len(grouped),
                         pairs=len(new_pairs), groups=[dict(id=c['id'], members=c.get('section_members'),
                         aliases=c.get('slab_aliases')) for c in grouped]))
result = dict(before=sum(r['before'] for r in rows), after=sum(r['after'] for r in rows), rows=rows)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
print({k: v for k, v in result.items() if k != 'rows'})
print([r for r in rows if r['beam']=='V301'])
