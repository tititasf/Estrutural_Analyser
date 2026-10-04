"""Agrupa seções executivas iguais sem descartar suas evidências N1."""
from copy import deepcopy

from .lv_n3_cut_contract import build_cut_contract, CutContractError


def section_signature(contract):
    # A/B são orientados: espelhar uma seção assimétrica não é equivalência.
    # Nomes, origem, nível absoluto e quantidade de vínculos não são geometria.
    return (contract['beam'], contract['width_cm'], contract['height_cm'],
            tuple(tuple(sorted({(s['height_cm'], s['drop_cm'])
                                for s in contract['slabs'][side]})) for side in ('A', 'B')))


def group_equivalent_cuts(cuts):
    result, groups = [], {}
    for source in cuts:
        try:
            contract = build_cut_contract(source)
            signature = section_signature(contract)
        except CutContractError:
            # Medidas incompletas ou conflitantes não provam igualdade.
            result.append(deepcopy(source))
            continue
        cut = groups.get(signature)
        if cut is None:
            cut = deepcopy(source)
            cut['section_members'] = []
            cut['slab_aliases'] = {'A': [], 'B': []}
            groups[signature] = cut
            result.append(cut)
        cut['section_members'].append({
            'id': source['id'], 'kind': source['kind'],
            'origins': deepcopy(source.get('origins') or []),
            'evidence_ids': deepcopy(source.get('evidence_ids') or []),
            'warnings': contract['warnings'],
        })
        for field in ('origins', 'evidence_ids', 'pairs'):
            values = cut.setdefault(field, [])
            for value in source.get(field) or []:
                if value not in values:
                    values.append(deepcopy(value))
        for side in ('A', 'B'):
            for slab in contract['slabs'][side]:
                name = slab.get('name')
                if name and name not in cut['slab_aliases'][side]:
                    cut['slab_aliases'][side].append(name)
        attention = list(dict.fromkeys([cut.get('attention') or '', source.get('attention') or '',
                                      *contract['warnings']]))
        cut['attention'] = '; '.join(value for value in attention if value)
    for cut in groups.values():
        cut['own_slab'] = ', '.join(cut['slab_aliases']['A']) or None
        cut['neighbor_slab'] = ', '.join(cut['slab_aliases']['B']) or None
    return result
