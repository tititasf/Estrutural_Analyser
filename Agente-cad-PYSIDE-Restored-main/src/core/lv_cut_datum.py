"""Keep a beam's measured top separate from the regional slab elevations."""
from copy import deepcopy
from .lv_cut_inventory import number, prepare_slab_regions
from .lv_n3_cut_contract import build_cut_contract, CutContractError


def connected_soffit_beams(beam, segments):
    """Only direct concrete continuity may carry a display datum across names."""
    from shapely.geometry import Polygon
    own = [s for s in segments if s.get('beam_name') == beam]
    neighbors = set()
    for source in own:
        points = source.get('points') or []
        if len(points) < 3:
            continue
        polygon = Polygon(points)
        for target in segments:
            name = target.get('beam_name')
            other = target.get('points') or []
            # Clipped diagonal soffits do not retain the nominal section width.
            # Width compatibility is checked against measured cut contracts below.
            if not name or name == beam or len(other) < 3:
                continue
            if polygon.distance(Polygon(other)) <= .2:
                neighbors.add(name)
    return neighbors


def apply_original_datums(sections, originals, slabs, prepared=None, *, neighboring_originals=(), regional_originals=()):
    evidence = []
    regions = prepare_slab_regions(slabs) if prepared is None else prepared
    for original in [*originals, *neighboring_originals]:
        try:
            contract = build_cut_contract(original)
        except (CutContractError, KeyError):
            continue
        if contract.get('beam_type') == 'inverted':
            continue
        for side in ('A', 'B'):
            for measured in contract['slabs'][side]:
                candidates = set()
                for _, _, region in regions:
                    if region.get('name') != measured['name']:
                        continue
                    fields = region.get('fields') or {}
                    height = number(region.get('height') or region.get('laje_dim') or fields.get('laje_dim'))
                    level = number(region.get('nivel') if region.get('nivel') is not None else
                                   region.get('level') or region.get('laje_nivel') or fields.get('laje_nivel'))
                    if level is not None and height is not None and abs(height-measured['height_cm']) <= .5:
                        candidates.add(round(level+measured['drop_cm']/100, 6))
                if len(candidates) == 1:
                    datum = candidates.pop()
                    evidence.append((contract['width_cm'], datum, original['id'],
                                     measured['height_cm'], round(datum-measured['drop_cm']/100, 6),
                                     original in originals))
    result = deepcopy(sections)
    for section in result:
        if (section.get('section_semantics') or {}).get('beam_type') == 'inverted':
            continue
        matched = [(level, uid) for width, level, uid, _, _, own in evidence
                   if own and abs(width-section['width_cm']) <= .5]
        if not matched:
            local_slabs = [slab for profile in (section.get('profiles') or {}).values()
                           for slab in profile.get('slabs') or []]
            matched = [(level, uid) for width, level, uid, height, slab_level, own in evidence
                       if not own and abs(width-section['width_cm']) <= .5 and
                       any(number(s.get('height_cm')) is not None and number(s.get('level')) is not None and
                           abs(float(s['height_cm'])-height) <= .5 and
                           abs(float(s['level'])-slab_level) <= .001 for s in local_slabs)]
        levels = {level for level, _ in matched}
        if len(levels) == 1:
            section['beam_top_level_m'] = levels.pop()
            section['beam_datum_source'] = 'original_cut_datum'
            section['beam_datum_evidence_ids'] = sorted({uid for _, uid in matched})
        elif len(levels) > 1:
            section['attention'] = 'Cortes originais indicam referências de nível diferentes; revisar o trecho'
    # A measured section can prove relative flange elevations without an
    # absolute building datum. Limit propagation to this beam, the same width
    # and height, and identical named slab thicknesses. Conflicts stay pending.
    relative = []
    for original in originals:
        try:
            contract = build_cut_contract(original)
        except (CutContractError, KeyError):
            continue
        if contract.get('beam_type') != 'inverted':
            relative.append((original['id'], contract))
    # Relative slab elevations are shared across beams. Anchor them in this
    # beam's measured cut, then follow only named, thickness-compatible slabs.
    graph = {}
    for original in [*originals, *regional_originals]:
        try:
            measured = build_cut_contract(original)
        except (CutContractError, KeyError):
            continue
        if measured.get('beam_type') == 'inverted':
            continue
        rows = [s for face in measured['slabs'].values() for s in face]
        for a in rows:
            for b in rows:
                ka = (a['name'], round(a['height_cm'], 3))
                kb = (b['name'], round(b['height_cm'], 3))
                graph.setdefault(ka, []).append((kb, a['drop_cm']-b['drop_cm'], original['id']))
    def regional_drop(section, slab):
        target = (slab.get('name'), round(slab['height_cm'], 3))
        anchors = [(uid, c, a) for uid, c in relative
                   if abs(c['width_cm']-section['width_cm']) <= .5
                   and abs(c['height_cm']-section['beam_height_cm']) <= .5
                   for face in c['slabs'].values() for a in face]
        answers = []
        for uid, contract, anchor in anchors:
            start = (anchor['name'], round(anchor['height_cm'], 3))
            elevations = {start: -anchor['drop_cm']}
            proofs = {start: {uid}}
            queue = [start]
            conflicts = set()
            lineage = {start: {start}}
            for node in queue:
                for neighbor, delta, evidence in graph.get(node, []):
                    value = elevations[node]+delta
                    if neighbor in elevations:
                        if abs(elevations[neighbor]-value) > .5:
                            conflicts.update((node, neighbor))
                        continue
                    elevations[neighbor] = value
                    proofs[neighbor] = proofs[node] | {evidence}
                    lineage[neighbor] = lineage[node] | {neighbor}
                    queue.append(neighbor)
            if target in elevations and not (lineage[target] & conflicts):
                answers.append((-elevations[target], proofs[target]))
        drops = {round(d, 4) for d, _ in answers}
        if len(drops) == 1:
            return drops.pop(), set().union(*(ids for _, ids in answers))
        return None, set()
    def measured_profiles(section, profiles):
        matches = [(uid, contract) for uid, contract in relative
                   if abs(contract['width_cm']-section['width_cm']) <= .5 and
                   abs(contract['height_cm']-section['beam_height_cm']) <= .5]
        changed = deepcopy(profiles)
        evidence_ids = set()
        has_measurement = False
        for side in ('A', 'B'):
            for slab in changed[side]['slabs']:
                if number(slab.get('level')) is not None:
                    # Do not mix an absolute region with a relative datum.
                    return profiles
                candidates = [(s['drop_cm'], uid) for uid, c in matches
                              for s in c['slabs'][side]
                              if s['name'] == slab.get('name') and
                              abs(s['height_cm']-slab['height_cm']) <= .5]
                drops = {round(drop, 4) for drop, _ in candidates}
                if len(drops) != 1:
                    drop, ids = regional_drop(section, slab)
                    if drop is None:
                        return profiles
                    drops = {drop}
                    evidence_ids.update(ids)
                slab['measured_drop_cm'] = drops.pop()
                evidence_ids.update(uid for _, uid in candidates)
                has_measurement = True
        if has_measurement:
            for profile in changed.values():
                profile['relative_level_source'] = 'original_cut_relative_profile'
                profile['relative_evidence_ids'] = sorted(evidence_ids)
        return changed
    for section in result:
        if (section.get('section_semantics') or {}).get('beam_type') == 'inverted':
            continue
        section['profiles'] = measured_profiles(section, section['profiles'])
        for pair in section.get('pairs') or []:
            if pair.get('profiles'):
                pair['profiles'] = measured_profiles(section, pair['profiles'])
    return result
