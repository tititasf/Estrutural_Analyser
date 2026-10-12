"""Bind a cut's semantic section to its measured, locally witnessed beam run.

The rendered depth remains evidence of the drawing, independently from the
declared depth. Callers supply scenes from ``build_scene_runs``; source
LWPOLYLINE walls must be included along with LINE entities.
"""
from __future__ import annotations

from shapely.geometry import Polygon

from .beam_section_texts import dimension_texts


def declared_section_for_cut(points, direction, geometric_width, runs, texts, beams=None):
    """Return numeric section proof, or None when ownership is ambiguous.

    Orthogonal cuts only. Require the entire rectangular stem to lie on the
    own-label run, both structural walls at that stem, a matching local section
    zone, and a source annotation aligned with that same physical corridor.
    """
    d = str(direction or '').lower()
    if d.startswith(('n', 's')):
        horizontal = True
    elif d.startswith(('l', 'e', 'o', 'w')):
        horizontal = False
    else:
        return None
    try:
        poly = Polygon(points)
        width = float(geometric_width)
    except (TypeError, ValueError):
        return None
    if not poly.is_valid or poly.is_empty or width <= 0:
        return None
    bounds = poly.bounds
    depth = bounds[2] - bounds[0] if horizontal else bounds[3] - bounds[1]
    source_pairs = dimension_texts(texts or [])
    beam_map = {b.get('name'): b for b in beams or []}
    matches = []
    for scenes in (runs or {}).values():
        for scene in scenes:
            if scene.angle or scene.is_horizontal != horizontal:
                continue
            if scene.provenance.get('band_source') != 'dxf_edges_from_own_label':
                continue
            if not scene.labels or abs(scene.width - width) > .25:
                continue
            stem = poly.intersection(scene.world_band())
            if stem.geom_type != 'Polygon' or stem.is_empty:
                continue
            lo, hi = scene.axis_bounds(stem)
            # Full depth and full width: wing contact alone cannot bind a cut.
            area_tolerance = .25 * depth
            if abs(hi-lo-depth) > .25 or abs(stem.area-depth*width) > area_tolerance:
                continue
            if stem.symmetric_difference(scene.rect(lo, hi, scene.t_lo, scene.t_hi)).area > area_tolerance:
                continue
            if any(scene.line_coverage(side, lo, hi) < .99 or
                   scene.dimension_overlap(side, lo, hi) > .05 for side in ('A', 'B')):
                continue
            physical_fund = None
            if beams is not None:
                for key, value in (beam_map.get(scene.beam_name, {}).get('links') or {}).items():
                    if not (str(key).startswith('viga_fundo_seg_') and str(key).endswith('_area_segs')):
                        continue
                    for contour in (value or {}).get('contour') or []:
                        try:
                            fund = Polygon(contour.get('points') or [])
                        except (ValueError, TypeError):
                            continue
                        if not fund.is_valid or fund.is_empty:
                            continue
                        bound_stem = poly.intersection(fund)
                        if (bound_stem.geom_type == 'Polygon' and
                                abs(bound_stem.area-depth*width) <= area_tolerance and
                                stem.difference(fund).area <= area_tolerance):
                            physical_fund, stem = fund, bound_stem
                            break
                    if physical_fund is not None:
                        break
                if physical_fund is None:
                    continue
            zones = [z for z in scene.sections if z['start'] <= lo+.25 and z['end'] >= hi-.25
                     and abs(float(z['width'])-width) <= .25]
            if len(zones) != 1:
                continue
            zone = zones[0]
            candidates = []
            for source in texts or []:
                pos = source.get('pos') if isinstance(source, dict) else None
                if not pos or not source.get('handle'):
                    continue
                pair = next((p for p in source_pairs if tuple(p['pos']) == tuple(pos[:2])
                             and p['text'] == str(source.get('text') or '').strip()), None)
                if not pair or abs(pair['width']-width) > .25 or abs(pair['height']-zone['depth']) > .25:
                    continue
                rotation = float(source.get('rotation') or 0) % 180
                if abs(rotation-(0 if horizontal else 90)) > 1:
                    continue
                axis, transverse = (pos[0], pos[1]) if horizontal else (pos[1], pos[0])
                distance = max(scene.t_lo-transverse, transverse-scene.t_hi, 0)
                if not (zone['start'] <= axis <= zone['end']) or distance > max(25, 4*float(source.get('height') or 1)):
                    continue
                candidates.append((abs(axis-(lo+hi)/2), source))
            if not candidates:
                continue
            source = min(candidates, key=lambda pair: pair[0])[1]
            matches.append({
                'source': 'declared_section_bound_to_physical_run',
                'binding_method': 'own_label_two_source_walls_aligned_section',
                'height_cm': float(zone['depth']), 'width_cm': width,
                'geometry_depth_cm': float(depth), 'axis_deg': 0 if horizontal else 90,
                'beam_name': scene.beam_name,
                'source_text': {k: source.get(k) for k in ('handle', 'text', 'pos', 'rotation')},
                'run_footprint': [list(p) for p in (physical_fund if physical_fund is not None
                                                   else scene.world_band()).exterior.coords],
                'stem_footprint': [list(p) for p in stem.exterior.coords],
                'wall_coverage': {side: scene.line_coverage(side, lo, hi) for side in ('A','B')},
            })
    return matches[0] if len(matches) == 1 else None


def apply_declared_section(window, link, geometric_section, direction):
    """Apply a proven declaration last, after geometric/cota autofill.

    Cache only source scenes on this window and DXF object, never globally.
    Current FV ownership is checked afresh for every cut.
    """
    from .lv_beam_scene import build_scene_runs
    # Provenance belongs to the current source and current FV owner only.
    # Reanalysis must not retain a proof when its run/contact disappeared.
    (link.get('ficha') or {}).pop('beam_height_evidence', None)
    data = getattr(window, 'dxf_data', None) or {}
    beams = getattr(window, 'beams_found', None) or []
    if not data or not beams or not geometric_section:
        return None
    cached = getattr(window, '_cut_declared_section_scene_cache', None)
    if cached is None or cached[0] is not data or cached[1] is not beams:
        source_geometry = list(data.get('lines') or []) + list(data.get('polylines') or [])
        runs = build_scene_runs(beams, data.get('texts') or [], source_geometry,
                                getattr(window, 'pavimento_pillar_report', None) or {})
        window._cut_declared_section_scene_cache = (data, beams, runs)
    else:
        runs = cached[2]
    evidence = declared_section_for_cut(link.get('points') or [], direction,
        geometric_section.get('bw') or geometric_section.get('beam_bottom_dim'),
        runs, data.get('texts') or [], beams)
    if evidence is None:
        return None
    ficha = link.setdefault('ficha', {})
    declared_height = evidence['height_cm']
    ficha['beam_height'] = str(declared_height)
    ficha['beam_bottom_dim'] = str(evidence['width_cm'])
    ficha['beam_name'] = evidence['beam_name']
    ficha['beam_height_evidence'] = evidence
    if ficha.get('beam_height_label') is not None:
        link.setdefault('cut_dimension_debug', {})['overridden_height_label'] = {
            'drawing_label_cm': ficha.pop('beam_height_label'),
            'authoritative_height_cm': declared_height,
            'reason': 'declared_section_bound_to_physical_run',
        }
    for prefix, slab_key in (('own', 'own_slab_height'), ('neighbor', 'neigh_slab_height')):
        try:
            slab_height = float(ficha.get(slab_key) or 0)
            top = float(ficha.get(prefix+'_dist_top') or 0)
        except (TypeError, ValueError):
            continue
        if slab_height > 0:
            ficha[prefix+'_dist_bottom'] = str(round(declared_height-slab_height-top, 1))
            ficha[prefix+'_position'] = window._infer_slab_position(top, slab_height, declared_height)
    fl = link.setdefault('ficha_links', {})
    if fl.get('beam_height_label'):
        link.setdefault('cut_dimension_debug', {})['overridden_height_label_links'] = fl.pop('beam_height_label')
    for key in ('beam_bottom_dim', 'beam_height'):
        fl[key] = [dict(evidence['source_text'], role='Ficha_'+key)]
    labels = [t for t in data.get('texts') or [] if
              str(t.get('text') or '').strip() == evidence['beam_name']]
    if labels:
        # Name metadata must refer to a label that generated this scene.
        witnesses = [scene.labels for scenes in runs.values() for scene in scenes
                     if scene.beam_name == evidence['beam_name']]
        positions = {tuple(label['pos']) for group in witnesses for label in group}
        own = [t for t in labels if tuple(t.get('pos') or []) in positions]
        if own:
            fl['beam_name'] = [dict(own[0], role='Ficha_beam_name')]
    return evidence


def refresh_declared_sections(window):
    """Reconcile existing cut fichas after the physical FV ownership pass.

    Slabs precede FV in the normal analyzer, so their initial autofill cannot
    prove beam ownership. Reuse the complete autofill only for cuts now bound
    to an own FV footprint; this also refreshes formulas and source metadata.
    """
    slabs = getattr(window, 'slabs_found', None) or []
    poly_map = window._slab_polygon_map(slabs)
    updated = []
    for slab in slabs:
        cuts = (slab.get('links') or {}).get('laje_visao_corte') or {}
        for link in cuts.get('cut_view_geom') or []:
            if not isinstance(link, dict) or not link.get('points'):
                continue
            direction = (link.get('ficha') or {}).get('direction') or window._slab_cut_direction(slab, link['points'])
            geo = window._parse_cut_poly_sections(link['points'], direction)
            if apply_declared_section(window, link, geo, direction) is None:
                continue
            window._auto_fill_cut_view_ficha(slab, link, slabs, poly_map)
            updated.append({'slab': slab.get('name'), 'beam': link['ficha']['beam_name'],
                            'height_cm': float(link['ficha']['beam_height'])})
    return updated
