"""Translate confirmed SA fabrication panels into the approved NOVA contract.

This adapter does not read N2 examples or change SA sources. Opening coordinates
retain the certified panel corner convention before panel lengths are regrouped.
"""
from copy import deepcopy
import math


def attach_pillar_faces(contracts, pillars):
    """Enrich loaded N3 copies with the SA face along the measured lateral.

    The physical lateral must run along an edge, not merely touch its end.
    Source SA records and the Para/Passa segmentation remain unchanged.
    """
    from shapely.geometry import LineString
    from .pillar_special_faces import physical_ring, special_l_face_segments
    result = deepcopy(contracts)
    by_name = {p.get('name'): p for p in pillars}
    for contract in result.values():
        for segment in contract.get('structural_segments') or []:
            points = segment.get('opening_source_points') or segment.get('points') or []
            if len(points) < 2:
                continue
            line = LineString(points)
            for opening in (segment.get('lv_cell') or {}).get('pillar_openings') or []:
                pillar = by_name.get(opening.get('name'))
                if not pillar or opening.get('pillar_face'):
                    continue
                ring = physical_ring(pillar.get('points'))
                faces = special_l_face_segments(ring)
                if len(ring) == 4:
                    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
                    x0,x1,y0,y1 = min(xs),max(xs),min(ys),max(ys)
                    vertical = y1-y0 > x1-x0
                    corners = ([(x0,y0),(x0,y1)],[(x1,y0),(x1,y1)],
                               [(x0,y1),(x1,y1)],[(x0,y0),(x1,y0)]) if vertical else (
                               [(x0,y0),(x1,y0)],[(x0,y1),(x1,y1)],
                               [(x0,y0),(x0,y1)],[(x1,y0),(x1,y1)])
                    faces = {f:dict(p0=a,p1=b) for f,(a,b) in zip('ABCD',corners)}
                # Special SA tables can supply the approved physical face edges.
                stored = pillar.get('pilar_especial') or pillar.get('special_geometry') or {}
                faces = stored.get('face_segments') or faces
                candidates = []
                dx,dy = points[-1][0]-points[0][0],points[-1][1]-points[0][1]
                for face,edge in faces.items():
                    a,b = edge['p0'],edge['p1']
                    ex,ey = b[0]-a[0],b[1]-a[1]
                    if abs(dx*ey-dy*ex) > .001*math.hypot(dx,dy)*math.hypot(ex,ey):
                        continue
                    edge_line = LineString([a,b])
                    overlap = edge_line.intersection(line.buffer(.1,cap_style=2)).length
                    if overlap > .5:
                        candidates.append((overlap,face))
                if candidates:
                    opening['pillar_face'] = max(candidates)[1]
                    opening['pillar_face_source'] = 'sa_physical_edge_overlap'
    return result


def ab_runs(source):
    if source.get('vertical_pending') or not source.get('panels'):
        raise ValueError('Lateral N3 sem montagem local confirmada')
    assembly = source.get('assembly_variant', 'sarrafeadas')
    if assembly not in ('gradeadas', 'sarrafeadas'):
        raise ValueError('Montagem lateral inválida')
    groups = []
    for raw in source['panels']:
        panel = deepcopy(raw)
        height = float(panel['height1'])
        body = float(panel.get('body_height_cm', height))
        width = float(panel['width'])
        if height <= 0 or body <= 0 or body > height or width <= 0 or float(panel['height2']) != height:
            raise ValueError('Painel local sem dimensões confirmadas')
        segment = panel.get('structural_segment_index', panel.get('segment_index'))
        physical = panel.get('physical_segment_index', segment)
        key = (physical, segment, height, body)
        if not groups or groups[-1]['key'] != key:
            groups.append(dict(key=key, segment_index=segment, length=0.,
                               beam_openings=[], column_openings=[]))
        group = groups[-1]
        offset = group['length']
        for hole in panel.get('holes') or []:
            if not hole.get('active', True):
                continue
            w, h = float(hole.get('width', 0)), float(hole.get('height', 0))
            if w <= 0 or h <= 0:
                raise ValueError('Abertura SA ativa sem dimensões')
            corner = str(hole.get('corner') or 'TL').upper()
            distance = float(hole.get('position', 0))
            left = offset + (0. if corner.endswith('L') else width-w)
            bottom = body-distance-h if corner.startswith('T') else distance
            top = bottom+h
            # Approved voids connect to the slab band. An isolated bottom void
            # needs its own reviewed rule; never silently turn it into a top cut.
            if top < body-.001:
                raise ValueError('Abertura isolada abaixo do topo: falta regra NOVA aprovada')
            group['beam_openings'].append((left, left+w, max(0., bottom)))
        group['length'] += width

    structural = source.get('structural_segments') or []
    for group in groups:
        matching = [s for s in structural if
                    s.get('physical_segment_index', s.get('segment_index')) == group['key'][0]
                    and s.get('segment_index') == group['segment_index']]
        if matching:
            group['points'] = matching[0].get('points') or []
            section = matching[0].get('section_contract') or {}
            mounting = section.get('mounting', {}).get(source.get('side', 'A'), {})
            if section.get('base_level_m') is not None:
                group['panel_base_level_m'] = (float(section['base_level_m']) +
                                             float(mounting.get('panel_base_cm', 0))/100)
        for target in matching:
            points = target.get('points') or []
            origin_points = target.get('opening_source_points') or points
            measured = len(points) == 2 and len(origin_points) == 2
            trim = -float(target.get('start_adjustment',
                source.get('start_adjustment') if target is structural[0] else 0) or 0)
            # A partition keeps openings measured from the original physical
            # segment. Project them onto its executable piece, just as beam
            # openings are projected by the generation contract.
            if measured:
                length = math.dist(points[0], points[1])
                original_length = math.dist(origin_points[0], origin_points[1])
                if not length or not original_length:
                    raise ValueError('Abertura de pilar SA sem eixo medido')
                axis = [(points[1][i]-points[0][i])/length for i in (0, 1)]
                original_axis = [(origin_points[1][i]-origin_points[0][i])/original_length
                                 for i in (0, 1)]
            for opening in (target.get('lv_cell') or {}).get('pillar_openings') or []:
                face = str(opening.get('pillar_face') or opening.get('face_pilar') or opening.get('face') or '').upper()
                if face in ('C', 'D') or opening.get('face_lateral_curta') is True:
                    continue
                a = opening.get('dist_abertura_inicio', opening.get('pos_inicio'))
                b = opening.get('pos_fim')
                if opening.get('abertura') is not None and a is not None:
                    b = float(a)+float(opening['abertura'])
                if b is None and a is not None and opening.get('largura') is not None:
                    b = float(a)+float(opening['largura'])
                if a is None or b is None:
                    raise ValueError('Abertura de pilar SA sem intervalo medido')
                if measured:
                    a, b = sorted(sum((origin_points[0][i]+original_axis[i]*float(t)
                                       -points[0][i])*axis[i] for i in (0, 1))-trim
                                  for t in (a, b))
                else:
                    a, b = float(a)-trim, float(b)-trim
                a, b = max(0., a), min(group['length'], b)
                if b-a > .001:
                    interval = (a, b)
                    if interval not in group['column_openings']:
                        group['column_openings'].append(interval)

    runs = []
    previous = None
    for group in groups:
        _, _, height, body = group['key']
        points = group.get('points') or []
        gap = (math.dist(previous['points'][-1], points[0])
               if previous and previous.get('points') and points else 0.)
        # A full-height void is an obstacle. Keep its footprint out of both
        # the panel and slab hatch, and start a separate fabrication run.
        obstacles = sorted((a, b) for a, b, y in group['beam_openings'] if y <= .001)
        pieces, cursor = [], 0.
        for a, b in obstacles:
            if a > cursor + .001:
                pieces.append((cursor, a))
            cursor = max(cursor, b)
        if cursor < group['length'] - .001:
            pieces.append((cursor, group['length']))
        for piece_index, (left, right) in enumerate(pieces):
            separated = not runs or gap > .05 or left > .001 or piece_index > 0
            if previous and previous.get('obstacle_at_end'):
                separated = True
            if separated:
                runs.append(dict(beam=source['beam_name'], side=source.get('side', 'A'),
                                 assembly_variant=assembly, total_cm=height, body_cm=body,
                                 segments=[]))
            segment = {k: v for k, v in group.items() if k not in ('key', 'points')}
            segment.update(length=right-left, total_cm=height, body_cm=body)
            segment['beam_openings'] = [(max(a,left)-left, min(b,right)-left, y)
                for a,b,y in group['beam_openings'] if y > .001 and b > left and a < right]
            segment['column_openings'] = [(max(a,left)-left, min(b,right)-left)
                for a,b in group['column_openings'] if b > left and a < right]
            runs[-1]['segments'].append(segment)
            gap = 0.
        group['obstacle_at_end'] = any(b >= group['length']-.001 for a,b in obstacles)
        previous = group
    levels = [g['panel_base_level_m'] for g in groups if 'panel_base_level_m' in g]
    tops = [float(s['section_contract']['top_level_m']) for s in structural
            if (s.get('section_contract') or {}).get('top_level_m') is not None]
    reference = max(tops) if tops else (max(levels) if levels else None)
    for run_index, run in enumerate(runs):
        run['continuation'] = run_index > 0
        base = run['segments'][0].get('panel_base_level_m')
        if base is not None and reference is not None:
            run['datum_y_cm'] = (reference-base)*100
            for segment in run['segments']:
                if segment.get('panel_base_level_m') is None:
                    raise ValueError('Segmento contíguo sem nível de montagem confirmado')
                segment['y_offset_cm'] = (segment['panel_base_level_m']-base)*100
    return runs


def generate_ab(source, path, behavior='PARA'):
    import json
    from hashlib import sha256
    from pathlib import Path
    import ezdxf
    from ezdxf.xref import load_modelspace
    from ezdxf.math import Matrix44
    from ezdxf import bbox
    from .lv_nova_design import draw_ab
    from scripts.drawing_mode_config import apply_config
    runs = ab_runs(source)
    doc = ezdxf.new('R2018')
    unit_dir = Path(path).with_suffix('.units')
    unit_dir.mkdir(parents=True, exist_ok=True)
    units = []
    top = None
    for index, run in enumerate(runs, 1):
        local = draw_ab(run)
        apply_config(local, 'NOVA', 'LV', behavior)
        local.header['$INSUNITS'] = 5
        unit_path = unit_dir / f'AB_{index:03d}.dxf'
        local.saveas(unit_path)
        units.append(dict(file=unit_path.name, kind='AB', beam=run['beam'],
                          side=run['side'], segments=[s['segment_index'] for s in run['segments']],
                          contract=run, sha256=sha256(unit_path.read_bytes()).hexdigest()))
        bounds = bbox.extents(local.modelspace())
        # Only physical obstacles break runs; local height changes stay joined.
        dy = 0. if top is None else top-bounds.extmax.y
        existing = {e.dxf.handle for e in doc.modelspace()}
        # The resource loader preserves dimension geometry blocks and XDATA
        # overrides. Importer drops the geometry after a source-side transform.
        load_modelspace(local, doc)
        for entity in doc.modelspace():
            if entity.dxf.handle not in existing and dy:
                entity.transform(Matrix44.translate(0, dy, 0))
        top = bounds.extmin.y+dy-60.
    doc.header['$INSUNITS'] = 5
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)
    (unit_dir / 'manifest.json').write_text(json.dumps(dict(
        mode='NOVA', behavior=behavior, assembly_variant=source.get('assembly_variant','sarrafeadas'),
        source_hash=sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(), units=units
    ), ensure_ascii=False, indent=2), encoding='utf8')
    return runs
