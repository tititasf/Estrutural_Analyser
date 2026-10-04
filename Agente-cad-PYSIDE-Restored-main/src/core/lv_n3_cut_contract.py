"""Seções executivas derivadas exclusivamente do inventário SA/N1.

Não lê fichas reversas. A largura representada das lajes é um trecho de corte,
não sua extensão em planta. Toda medida de concreto vem da seção SA.
"""
from __future__ import annotations
from hashlib import sha256
import json
from .lv_cut_inventory import number


class CutContractError(ValueError):
    pass


def _positive(value, field):
    result = number(value)
    if result is None or result <= 0:
        raise CutContractError(f'{field}: medida positiva ausente')
    return result


def build_cut_contract(cut):
    semantics = cut.get('section_semantics') or (cut.get('source_cut') or {}).get('section_semantics') or {}
    inverted = semantics.get('confirmed') is True and semantics.get('beam_type') == 'inverted'
    warnings = [cut['attention']] if cut.get('attention') else []
    warnings.extend(w for member in cut.get('section_members') or [] for w in member.get('warnings') or [])
    slabs = {'A': [], 'B': []}
    if cut['kind'] == 'calculated':
        width = _positive(cut.get('width_cm'), 'width_cm')
        height = _positive(cut.get('beam_height_cm'), 'beam_height_cm')
        profiles = cut['profiles']
        levels = [number(profiles[s].get('level')) for s in ('A','B')]
        if None in levels:
            raise CutContractError('profiles.level: nível ausente')
        # O SA separa a referência da viga das cotas regionais das lajes.
        # Uma laje acima dessa referência exige revisão, nunca eleva a viga.
        datum = max(levels)
        if inverted:
            from .beam_vertical_context import inverted_profile_levels
            try:
                vertical = inverted_profile_levels(height, profiles, semantics)
            except ValueError as exc:
                raise CutContractError(str(exc)) from exc
            datum = vertical['top_level_m']
        for side in ('A','B'):
            for slab in profiles[side]['slabs']:
                thick = _positive(slab.get('height_cm'), f'{side}.{slab.get("name")}.height_cm')
                level = number(slab.get('level'))
                if level is None:
                    raise CutContractError(f'{side}.{slab.get("name")}.level: nível ausente')
                slabs[side].append({'name':slab.get('name'), 'height_cm':thick,
                                    'drop_cm':round((datum-level)*100, 4)})
    else:
        raw = cut.get('source_cut') or {}
        ficha = raw.get('ficha') or {}
        width = _positive(raw.get('beam_w') or ficha.get('beam_bottom_dim'), 'beam_w')
        height = _positive(raw.get('beam_h') or ficha.get('beam_height'), 'beam_h')
        own = raw.get('own_laje')
        # own_* pertence à ficha que mediu o polígono. A união de evidências
        # pode conservar own_laje do registro da outra laje; não inverter suas
        # medidas por causa dessa identidade externa. Convenção SA: direção
        # Norte/Leste => proprietário A; Sul/Oeste => proprietário B.
        direction = str(ficha.get('direction') or '').strip().casefold()
        owner_side = {'norte':'A','leste':'A','east':'A','north':'A',
                      'sul':'B','oeste':'B','south':'B','west':'B'}.get(direction)
        own_side = owner_side or ('A' if own == ficha.get('side_a_laje_name') else 'B' if own == ficha.get('side_b_laje_name') else None)
        if not own_side:
            raise CutContractError('ficha.side_a/b_laje_name: orientação da laje ausente')
        other_side = 'B' if own_side == 'A' else 'A'
        owner_name = ficha.get('side_'+own_side.lower()+'_laje_name') or own
        neighbor_name = ficha.get('side_'+other_side.lower()+'_laje_name') or raw.get('neigh_laje')
        if owner_side and own and own != owner_name:
            warnings.append('Evidências de duas lajes reunidas; medidas orientadas pela direção da ficha')
        for prefix, side, name in [('own',own_side,owner_name),('neighbor',other_side,neighbor_name)]:
            if str(ficha.get('beam_lajes_side_'+side.lower())) == '0':
                if name: warnings.append(f'Lado {side}: ficha declara ausência de laje; associação {name} não usada')
                continue
            if not name or str(name).casefold() in ('nulo', 'null', 'none'):
                continue
            slab_field = 'own_slab_height' if prefix == 'own' else 'neigh_slab_height'
            thick = _positive(ficha.get(slab_field), slab_field)
            drop = number(ficha.get(prefix+'_dist_top'))
            bottom = number(ficha.get(prefix+'_dist_bottom'))
            if drop is None or bottom is None or abs(drop+thick+bottom-height) > .5:
                raise CutContractError(f'{prefix}: topo + laje + fundo não fecha a altura da viga')
            declared = number(ficha.get('side_'+side.lower()+'_laje_height'))
            if declared is not None and abs(declared-thick) > .5:
                rule = 'espessura regional do corte invertido preservada' if inverted else f'espessura anotada {declared:g} cm usada'
                warnings.append(f'Laje {name}: símbolo mede {thick:g} cm; anotação {declared:g} cm; {rule}')
            # Mesma precedência do preenchimento SA: anotação da laje é
            # medida primária; o T geométrico é fallback. O desnível vem do
            # corte e o resíduo inferior será recalculado pelo desenhador.
            if declared is not None and declared > 0 and not inverted:
                thick = declared
            slabs[side].append({'name':name,'height_cm':thick,'drop_cm':drop})
    for side in ('A','B'):
        sections = {(s['drop_cm'],s['height_cm']) for s in slabs[side]}
        if len(sections) > 1:
            raise CutContractError(f'{side}.slabs: mais de um perfil de laje no mesmo trecho')
        for slab in slabs[side]:
            outside = (slab['drop_cm'] >= height if inverted else
                       slab['drop_cm']+slab['height_cm'] > height+.5)
            if slab['drop_cm'] < -.5 or outside:
                raise CutContractError(f'{side}.slabs: laje fora da altura da viga')
    # A slab reaching the beam soffit is a lower slab, rather than an upper
    # flange. Derive mounting profiles from the same measured section, never
    # from the total beam height or a reverse-engineered N2.
    mounting = {}
    for side in ('A','B'):
        slab = slabs[side][0] if slabs[side] else None
        lower = bool(slab and abs(height-slab['drop_cm']-slab['height_cm']) <= .5)
        above_slab = bool(inverted and slab)
        base = height-slab['drop_cm']+2 if lower or above_slab else -4.
        top = height if not slab or lower or above_slab else height-slab['drop_cm']-slab['height_cm']-2
        if top <= base:
            raise CutContractError(f'{side}: altura do painel sob/sobre a laje não positiva')
        mounting[side] = {'lower_slab':lower,'panel_base_cm':base,
                          'panel_top_cm':top,'h1_cm':top-base}
        if above_slab:
            mounting[side]['below_slab_concrete_cm'] = max(0.,height-slab['drop_cm']-slab['height_cm'])
    for side in ('A', 'B'):
        aliases = (cut.get('slab_aliases') or {}).get(side) or []
        if aliases and slabs[side]:
            slabs[side] = [{**slabs[side][0], 'name': ', '.join(aliases)}]
    contract = {'schema':'cad.sa.lv_n3_cut/v1', 'id':cut['id'], 'beam':cut['beam'],
                'source':'N1', 'kind':cut['kind'], 'width_cm':width,'height_cm':height,
                'slabs':slabs,'mounting':mounting,'warnings':list(dict.fromkeys(warnings)),
                'rules':{'face_allowance_cm':4.,'panel_cm':2.,'wood_cm':14.,'cap_cm':4.4},
                'pairs':cut.get('pairs') or [],'evidence_ids':cut.get('evidence_ids') or []}
    if inverted:
        contract['beam_type'] = 'inverted'
        contract['form_role'] = 'top_cap'
        contract['section_semantics'] = semantics
        if cut['kind'] == 'calculated':
            contract.update(vertical)
    elif cut['kind'] == 'calculated':
        # Absolute context belongs to this physical pair, never to the first
        # member of a group of equal relative section shapes.
        confirmed = [number(p.get('level')) for p in profiles.values()
                     if p.get('level_source') in ('lv_cell_slabs', 'paired_touching_slabs')]
        if confirmed and max(confirmed) >= datum-.005:
            contract.update(base_level_m=round(datum-height/100, 6),
                            top_level_m=round(datum, 6),
                            vertical_datum_source='local_sa_profiles')
    contract['fingerprint'] = sha256(json.dumps(contract,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return contract
