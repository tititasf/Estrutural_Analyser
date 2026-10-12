"""Approved Formascia drawing rules for Vigas Laterais (LV).
All structural measures come from the caller's SA contract.
Reuses proven NOVA geometry segmentation while applying Formascia anatomy:
  - Green panels (ACI 3, layer VIGAS)
  - Red sarrafos (ACI 1, layer ACABAMENTO with MLINE style EEEEEEEE for sarrafeadas)
  - Grade chords and upright posts spaced 30 cm (layers Sarrafos / Meio_pont.)
  - White panel numbers (h=12, ACI 7) inside red circles (r=10, ACI 1, layer NUMERAÇÃO DAS CHAPAS)
  - Cyan dimensions (ACI 4, layer cotas, dimstyle FORMASCIA-PAINEL with _Oblique arrows)
  - White titles and texts (h=16.5 / 10.0, ACI 7, layer BNC_TEXTO)
  - Gray AR-CONC hatch (ACI 8, layer BNC_HACHURA DE CONCRETO)
"""
from __future__ import annotations

import math
from pathlib import Path
from copy import deepcopy

import ezdxf
from ezdxf.addons import Importer
from ezdxf.enums import TextEntityAlignment
from ezdxf.math import Vec3
from shapely.geometry import box, LineString
from shapely.ops import unary_union

DESIGN_VERSION = 'formascia-lv-v1'
ROOT = Path(__file__).resolve().parents[2]
FORMASCIA_ASSET = ROOT / 'config/formascia/details.dxf'


def panel_spans(length):
    """Preserve length; avoid a short remainder by splitting the preceding 244."""
    length = float(length)
    if not math.isfinite(length) or length <= 0:
        raise ValueError('length: positive finite measure required')
    spans, start = [], 0.
    while start < length - 1e-8:
        remaining = length - start
        width = remaining if remaining <= 244 + 1e-8 else 122 if remaining - 244 < 60 - 1e-8 else 244
        spans.append((start, min(length, start + width)))
        start += width
    return spans


def pontalete_count(start, end, openings):
    """Count useful width once, including overlaps between different openings."""
    intervals = sorted((max(start, a), min(end, b)) for a, b in openings if b > start and a < end)
    covered, last = 0., start
    for a, b in intervals:
        covered += max(0., b - max(a, last))
        last = max(last, b)
    return math.floor(max(0., end - start - covered) / 30 + .5 + 1e-10)


def setup_formascia_resources(doc):
    """Ensure Formascia styles, blocks, layers, and dimstyles are present in doc."""
    # Layers
    def _layer(name, color, linetype='Continuous'):
        if name not in doc.layers:
            doc.layers.new(name, dxfattribs={'color': color, 'linetype': linetype})
        else:
            layer_ent = doc.layers.get(name)
            layer_ent.dxf.color = color
            if linetype != 'Continuous':
                layer_ent.dxf.linetype = linetype

    _layer('0', 7)
    _layer('VIGAS', 3)
    _layer('ACABAMENTO', 1)
    _layer('Sarrafos', 1)
    _layer('Meio_pont.', 43)
    _layer('NUMERAÇÃO DAS CHAPAS', 7)
    _layer('cotas', 4)
    _layer('BNC_TEXTO', 7)
    _layer('BNC_HACHURA DE CONCRETO', 8)
    _layer('BNC_HACHURA MADEIRAS', 1)
    _layer('BNC_COMPENSADO', 7)
    _layer('presilha', 1)
    _layer('Sarrafo de pressão', 1, linetype='HIDDEN')

    # Dimstyle FORMASCIA-PAINEL
    if 'FORMASCIA-PAINEL' not in doc.dimstyles:
        # Import _Oblique if asset exists
        if FORMASCIA_ASSET.exists():
            try:
                src = ezdxf.readfile(FORMASCIA_ASSET)
                imp = Importer(src, doc)
                if '_Oblique' in src.blocks and '_Oblique' not in doc.blocks:
                    imp.import_block('_Oblique')
                imp.finalize()
            except Exception:
                pass
        
        # If _Oblique not in doc, create it
        if '_Oblique' not in doc.blocks:
            blk = doc.blocks.new(name='_Oblique')
            blk.add_line((-0.5, -0.5), (0.5, 0.5), dxfattribs={'color': 256})

        ds = doc.dimstyles.new('FORMASCIA-PAINEL')
        ds.dxf.dimtxt = 10.0
        ds.dxf.dimasz = 3.0
        ds.dxf.dimclrd = 4
        ds.dxf.dimclre = 4
        ds.dxf.dimclrt = 240
        ds.dxf.dimblk1 = '_Oblique'
        ds.dxf.dimblk2 = '_Oblique'
        ds.dxf.dimdec = 1
        ds.dxf.dimzin = 8
        ds.dxf.dimdsep = 44
        ds.dxf.dimgap = 2.0

    # Dimstyle SECAO
    if 'SECAO' not in doc.dimstyles:
        ds_sec = doc.dimstyles.new('SECAO')
        ds_sec.dxf.dimtxt = 12.0
        ds_sec.dxf.dimasz = 4.0
        ds_sec.dxf.dimclrd = 4
        ds_sec.dxf.dimclre = 4
        ds_sec.dxf.dimclrt = 30
        ds_sec.dxf.dimblk1 = '_Oblique'
        ds_sec.dxf.dimblk2 = '_Oblique'
        ds_sec.dxf.dimdec = 1
        ds_sec.dxf.dimzin = 8
        ds_sec.dxf.dimdsep = 44
        ds_sec.dxf.dimgap = 2.0

    # MLINE style EEEEEEEE (offset 0.0 and 7.0, width 7 cm)
    if 'EEEEEEEE' not in doc.mline_styles:
        st = doc.mline_styles.new('EEEEEEEE')
        st.dxf.flags = 1  # fill
        st.dxf.fill_color = 256  # bylayer
        st.elements.elements.clear()
        st.elements.append(0.0, 256, 'BYLAYER')
        st.elements.append(7.0, 256, 'BYLAYER')

    for layer in doc.layers:
        layer.dxf.discard('material_handle')
        layer.dxf.discard('plotstyle_handle')


def _parts(geometry):
    return list(geometry.geoms) if hasattr(geometry, 'geoms') else [geometry]


def _text(m, value, x, y, height=10.0, layer='BNC_TEXTO', color=7, centered=False):
    t = m.add_text(str(value), dxfattribs={'layer': layer, 'height': height, 'color': color, 'style': 'Standard'})
    if centered:
        t.set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    else:
        t.dxf.insert = (x, y)
    return t


def _hatch_concrete(m, points):
    hatch = m.add_hatch(dxfattribs={'layer': 'BNC_HACHURA DE CONCRETO', 'color': 8})
    hatch.set_pattern_fill('AR-CONC', scale=1.0)
    hatch.paths.add_polyline_path(points, is_closed=True)
    return hatch


def legacy_draw_ab(contract):
    """Draw contiguous local segments in approved Formascia style."""
    assembly = contract.get('assembly_variant', 'sarrafeadas')
    doc = ezdxf.new('R2018')
    setup_formascia_resources(doc)
    m = doc.modelspace()

    body = float(contract['body_cm'])
    height = float(contract['total_cm'])

    from shapely.geometry import box as raw_box
    active_y = 0.
    def sbox(x1, y1, x2, y2, offset=None):
        dy = active_y if offset is None else offset
        return raw_box(x1, y1 + dy, x2, y2 + dy)

    segments, start, voids = [], 0., []
    for source in contract['segments']:
        active_y = float(source.get('y_offset_cm', 0))
        seg_body = float(source.get('body_cm', contract['body_cm']))
        seg_height = float(source.get('total_cm', contract['total_cm']))
        length = float(source['length'])
        if length <= 0 or seg_body <= 0 or seg_height < seg_body:
            raise ValueError('Invalid AB local dimensions')
        end = start + length
        beam_openings = source.get('beam_openings', [source['beam_opening']] if source.get('beam_opening') else [])
        columns = source.get('column_openings', [source['column_opening']] if source.get('column_opening') else [])
        beam_openings = [(max(0., a), min(length, b), max(0., min(seg_body, y)))
                         for a, b, y in beam_openings if b > 0 and a < length and b > a]
        columns = [(max(0., a), min(length, b)) for a, b in columns if b > 0 and a < length and b > a]
        segments.append((start, end, source, beam_openings, columns))
        voids.extend(sbox(start + a, y, start + b, seg_height) for a, b, y in beam_openings)
        if seg_height > seg_body:
            voids.append(sbox(start, seg_body, end, seg_height))
        start = end
    total = start

    void_geometry = unary_union(voids).simplify(1e-7, preserve_topology=True)
    # Hatch concrete for voids
    for part in _parts(void_geometry):
        if part.geom_type == 'Polygon' and part.area > 1e-4:
            pts = [(round(p[0], 4), round(p[1], 4)) for p in part.exterior.coords[:-1]]
            if len(pts) >= 3:
                _hatch_concrete(m, pts)

    def measure(p1, p2, base, angle=0):
        p1_off = (p1[0], p1[1] + active_y)
        p2_off = (p2[0], p2[1] + active_y)
        base_off = (base[0], base[1] + active_y)
        d = m.add_linear_dim(base=base_off, p1=p1_off, p2=p2_off, angle=angle,
                             dimstyle='FORMASCIA-PAINEL', dxfattribs={'layer': 'cotas', 'color': 4})
        d.render()

    def mline_sarrafo(x1, y1, x2, y2):
        """Draw an MLINE in ACABAMENTO layer with style EEEEEEEE."""
        m.add_mline([(x1, y1 + active_y), (x2, y2 + active_y)],
                    dxfattribs={'layer': 'ACABAMENTO', 'style_name': 'EEEEEEEE',
                                'scale_factor': 1.0, 'justification': 0, 'color': 256})

    dimension_floor = min(float(s[2].get('y_offset_cm', 0)) for s in segments)
    panel_number = 1

    for index, (sx, end, source, openings, columns) in enumerate(segments, 1):
        active_y = float(source.get('y_offset_cm', 0))
        seg_body = float(source.get('body_cm', contract['body_cm']))
        seg_height = float(source.get('total_cm', contract['total_cm']))
        
        # Panel spans (e.g. 244, 122, remainder)
        spans = [(sx + a, sx + b) for a, b in panel_spans(end - sx)]
        
        # Draw Panel Contours in layer VIGAS (color 3)
        for x, stop in spans:
            pts = [(x, active_y), (stop, active_y), (stop, seg_body + active_y), (x, seg_body + active_y)]
            m.add_lwpolyline(pts, close=True, dxfattribs={'layer': 'VIGAS', 'color': 3})
            
            # Bottom panel dimension
            measure((x, 0), (stop, 0), (x, dimension_floor - 25.0 - active_y))
            
            # Panel Numbering: CIRCLE (r=10, layer NUMERAÇÃO DAS CHAPAS, color 1) + TEXT (h=12, color 7)
            cx = (x + stop) / 2.0
            cy = seg_body / 2.0 + active_y
            m.add_circle((cx, cy), 10.0, dxfattribs={'layer': 'NUMERAÇÃO DAS CHAPAS', 'color': 1})
            _text(m, str(panel_number), cx, cy, height=12.0, layer='NUMERAÇÃO DAS CHAPAS', color=7, centered=True)
            panel_number += 1

        # Title on first segment: V302A (or V302.A)
        if index == 1:
            side_str = contract.get("side", "A")
            beam_str = contract["beam"]
            label = f"{beam_str}.{side_str} ({assembly.upper()})"
            _text(m, label, sx + 5, seg_height + 15 + active_y, height=16.5, layer='BNC_TEXTO', color=7)

        # Pillar annotations
        for a, b in columns:
            col_x = (sx + a + sx + b) / 2.0
            _text(m, "PILAR", col_x, seg_body + 5 + active_y, height=10.0, layer='BNC_TEXTO', color=7, centered=True)

        # Dimensions for openings
        for a, b, y in openings:
            a_w, b_w = sx + a, sx + b
            measure((a_w, y), (b_w, y), (a_w, seg_height + 25))
            q = a_w + 25 if abs(a_w - sx) < 1e-6 else b_w - 25
            measure((q, y), (q, seg_height), (q, y), 90)

        # Sarrafos Drawing
        if assembly == 'sarrafeadas':
            # Rails distribution (7cm MLINE)
            n_rails = max(2, math.ceil((seg_body - 7) / 30) + 1)
            rails = [(0, 7), (seg_body - 7, seg_body)] + [
                ((seg_body - 7) * i / (n_rails - 1), (seg_body - 7) * i / (n_rails - 1) + 7)
                for i in range(1, n_rails - 1)
            ]
            for low, high in rails:
                # Draw horizontal MLINE across segment
                mline_sarrafo(sx, low, end, low)

            # Vertical sarrafos at beam ends & openings
            if sx == 0:
                m.add_mline([(0, active_y), (0, seg_body + active_y)],
                            dxfattribs={'layer': 'ACABAMENTO', 'style_name': 'EEEEEEEE',
                                        'scale_factor': 1.0, 'justification': 0, 'color': 256})
            if end == total:
                m.add_mline([(total - 7, active_y), (total - 7, seg_body + active_y)],
                            dxfattribs={'layer': 'ACABAMENTO', 'style_name': 'EEEEEEEE',
                                        'scale_factor': 1.0, 'justification': 0, 'color': 256})
            for a, b, y in openings:
                m.add_mline([(sx + a, y - 7 + active_y), (sx + a, seg_body + active_y)],
                            dxfattribs={'layer': 'ACABAMENTO', 'style_name': 'EEEEEEEE',
                                        'scale_factor': 1.0, 'justification': 0, 'color': 256})
                m.add_mline([(sx + b, y - 7 + active_y), (sx + b, seg_body + active_y)],
                            dxfattribs={'layer': 'ACABAMENTO', 'style_name': 'EEEEEEEE',
                                        'scale_factor': 1.0, 'justification': 0, 'color': 256})

        elif assembly == 'gradeadas':
            # Top and bottom chords in layer Sarrafos (ACI 1)
            pts_top = [(sx, seg_body - 2.2 + active_y), (end, seg_body - 2.2 + active_y),
                       (end, seg_body + active_y), (sx, seg_body + active_y)]
            m.add_lwpolyline(pts_top, close=True, dxfattribs={'layer': 'Sarrafos', 'color': 1})

            pts_bot = [(sx, active_y), (end, active_y),
                       (end, 2.2 + active_y), (sx, 2.2 + active_y)]
            m.add_lwpolyline(pts_bot, close=True, dxfattribs={'layer': 'Sarrafos', 'color': 1})

            # Upright chords/pontaletes (3.5 cm width) spaced ~30 cm in layer Meio_pont. (ACI 43)
            intervals = [(sx + a, sx + b) for a, b, y in openings] + [(sx + a, sx + b) for a, b in columns]
            
            # Posts along spans
            p_cursor = sx
            while p_cursor <= end - 3.5 + 1e-4:
                # check if inside column or opening
                in_void = any(v0 - 1e-4 <= p_cursor <= v1 + 1e-4 for v0, v1 in intervals)
                if not in_void:
                    post_pts = [(p_cursor, 2.2 + active_y), (p_cursor + 3.5, 2.2 + active_y),
                                (p_cursor + 3.5, seg_body - 2.2 + active_y), (p_cursor, seg_body - 2.2 + active_y)]
                    m.add_lwpolyline(post_pts, close=True, dxfattribs={'layer': 'Meio_pont.', 'color': 43})
                p_cursor += 30.0

            # Annotation for pontaletes count
            for x, stop in spans:
                count = pontalete_count(x, stop, intervals)
                if count > 0:
                    lbl = f'{count} pontalete' if count == 1 else f'{count} pontaletes'
                    _text(m, lbl, (x + stop) / 2.0, seg_body / 2.0 - 18.0 + active_y,
                          height=5.0, layer='BNC_TEXTO', color=7, centered=True)

    # Total beam dimension below
    active_y = 0.
    measure((0, float(segments[0][2].get('y_offset_cm', 0))),
            (total, float(segments[-1][2].get('y_offset_cm', 0))),
            (0, dimension_floor - 60.0))

    if assembly == 'gradeadas':
        _text(m, "UTILIZAR GRADE SOLTA", total / 2.0, dimension_floor - 90.0,
              height=10.0, layer='cotas', color=1, centered=True)

    # Height dimensions on the right end (no duplicate if no rebate)
    last_body = float(segments[-1][2].get('body_cm', contract['body_cm']))
    last_height = float(segments[-1][2].get('total_cm', contract['total_cm']))
    last_y = float(segments[-1][2].get('y_offset_cm', 0))
    if last_height > last_body + 1e-3:
        measure((total, 0), (total, last_body), (total + 30.0, 0), 90)
        measure((total, last_body), (total, last_height), (total + 30.0, last_body), 90)
        measure((total, 0), (total, last_height), (total + 60.0, 0), 90)
    else:
        measure((total, 0), (total, last_body), (total + 30.0, 0), 90)

    doc.header['$INSUNITS'] = 5
    return doc


def legacy_draw_cut(contract):
    """Draw cross section in approved Formascia style."""
    assembly = contract.get('assembly_variant', 'sarrafeadas')
    doc = ezdxf.new('R2018')
    setup_formascia_resources(doc)
    m = doc.modelspace()

    b, h = float(contract['width_cm']), float(contract['height_cm'])
    if not all(math.isfinite(v) and v > 0 for v in (b, h)):
        raise ValueError('width_cm/height_cm: positive finite measures required')

    slabs = {s: sorted([(float(v['height_cm']), float(v['drop_cm']))
                        for v in contract.get('slabs', {}).get(s, [])], key=lambda v: v[1]) for s in 'AB'}

    # 1. Concrete Beam & Slabs Outline in layer VIGAS (color 3)
    reach = max(35.0, b)
    concrete_polys = [box(0, 0, b, h)]
    for side, edge, sign in [('A', 0, -1), ('B', b, 1)]:
        for thickness, drop in slabs[side]:
            top, bottom = h - drop, h - drop - thickness
            sx1, sx2 = sorted((edge, edge + sign * reach))
            concrete_polys.append(box(sx1, bottom, sx2, top))

    concrete_union = unary_union(concrete_polys)
    for part in _parts(concrete_union):
        if part.geom_type == 'Polygon':
            pts = [(round(p[0], 4), round(p[1], 4)) for p in part.exterior.coords[:-1]]
            m.add_lwpolyline(pts, close=True, dxfattribs={'layer': 'VIGAS', 'color': 3, 'lineweight': 35})
            _hatch_concrete(m, pts)

    # 2. Formwork on sides (Panels A and B)
    for side, edge, sign in [('A', 0, -1), ('B', b, 1)]:
        side_drop = slabs[side][0][1] if slabs[side] else 0.0
        panel_top = h - side_drop
        px1, px2 = sorted((edge, edge + sign * 2.2))
        
        # Panel board outline in layer VIGAS (color 3)
        pts_panel = [(px1, -2.2), (px2, -2.2), (px2, panel_top), (px1, panel_top)]
        m.add_lwpolyline(pts_panel, close=True, dxfattribs={'layer': 'VIGAS', 'color': 3})
        
        # Red top cap in layer ACABAMENTO (color 1)
        pts_cap = [(px1, panel_top), (px2, panel_top), (px2, panel_top + 2.2), (px1, panel_top + 2.2)]
        m.add_lwpolyline(pts_cap, close=True, dxfattribs={'layer': 'ACABAMENTO', 'color': 1})

        # Panel side letter (A or B) centered inside panel
        cx = (px1 + px2) / 2.0
        cy = max(panel_top / 2.0, 15.0)
        _text(m, side, cx, cy, height=7.0, layer='cotas', color=4, centered=True)

        # Battens / Posts representation on the exterior
        if assembly == 'sarrafeadas':
            wx1, wx2 = sorted((px1 + sign * 2.2, px1)) if sign < 0 else sorted((px2, px2 + sign * 2.2))
            n_batt = max(2, math.ceil(panel_top / 30) + 1)
            for i in range(n_batt):
                yc = i * (panel_top - 7.0) / max(1, n_batt - 1)
                pts_batt = [(wx1, yc), (wx2, yc), (wx2, yc + 7.0), (wx1, yc + 7.0)]
                m.add_lwpolyline(pts_batt, close=True, dxfattribs={'layer': 'ACABAMENTO', 'color': 1})
        elif assembly == 'gradeadas':
            wx1, wx2 = sorted((px1 + sign * 3.5, px1)) if sign < 0 else sorted((px2, px2 + sign * 3.5))
            pts_grade = [(wx1, -2.2), (wx2, -2.2), (wx2, panel_top), (wx1, panel_top)]
            m.add_lwpolyline(pts_grade, close=True, dxfattribs={'layer': 'Meio_pont.', 'color': 43})

    # 3. Fundo de viga at bottom
    pts_fundo = [(0, -2.2), (b, -2.2), (b, 0), (0, 0)]
    m.add_lwpolyline(pts_fundo, close=True, dxfattribs={'layer': 'VIGAS', 'color': 3})
    _text(m, "c", b / 2.0, -1.1, height=4.0, layer='cotas', color=4, centered=True)

    # Gravata / support bar under fundo
    grav_y = -3.5
    m.add_line((-5.0, grav_y), (b + 5.0, grav_y), dxfattribs={'layer': 'ACABAMENTO', 'color': 1, 'lineweight': 25})
    m.add_line((-5.0, grav_y), (-5.0, grav_y + 3.0), dxfattribs={'layer': 'ACABAMENTO', 'color': 1})
    m.add_line((b + 5.0, grav_y), (b + 5.0, grav_y + 3.0), dxfattribs={'layer': 'ACABAMENTO', 'color': 1})

    # Barra de ancoragem (tie rod with nuts)
    tie_y = min(20.0, max(12.0, h * 0.35))
    m.add_line((-5.0, tie_y), (b + 5.0, tie_y), dxfattribs={'layer': 'ACABAMENTO', 'color': 1})
    m.add_line((-3.5, tie_y - 2.0), (-3.5, tie_y + 2.0), dxfattribs={'layer': 'ACABAMENTO', 'color': 1})
    m.add_line((b + 3.5, tie_y - 2.0), (b + 3.5, tie_y + 2.0), dxfattribs={'layer': 'ACABAMENTO', 'color': 1})

    # 4. Leaders and assembly notes under beam
    lbl_assembly = "GRADE SOLTA" if assembly == 'gradeadas' else "SARRAFEADA"
    
    # Leader Panel A (left)
    pa_x = -1.1
    m.add_leader(vertices=[(pa_x, -2.2), (pa_x, -28.0), (pa_x - 55.0, -28.0)],
                 dxfattribs={'layer': 'cotas', 'color': 4})
    _text(m, lbl_assembly, pa_x - 55.0, -26.0, height=6.0, layer='BNC_TEXTO', color=2)

    # Leader Panel B (right)
    pb_x = b + 1.1
    m.add_leader(vertices=[(pb_x, -2.2), (pb_x, -28.0), (pb_x + 55.0, -28.0)],
                 dxfattribs={'layer': 'cotas', 'color': 4})
    _text(m, lbl_assembly, pb_x + 5.0, -26.0, height=6.0, layer='BNC_TEXTO', color=2)

    # Leader Fundo (bottom - anchored off-center to avoid width dimension)
    fundo_x = b * 0.2
    m.add_leader(vertices=[(fundo_x, -3.5), (fundo_x, -42.0), (pa_x - 55.0, -42.0)],
                 dxfattribs={'layer': 'cotas', 'color': 4})
    _text(m, "FUNDO ERGUIDO", pa_x - 55.0, -40.0, height=6.0, layer='cotas', color=4)

    # 5. Dimensions
    def dim_cut(p1, p2, base, angle=0):
        d = m.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle,
                             dimstyle='SECAO', dxfattribs={'layer': 'cotas', 'color': 4})
        d.render()

    # Beam width dimension below
    dim_cut((0, -2.2), (b, -2.2), (0, -12.0))

    # Right side height dimension
    sb_drop = slabs['B'][0][1] if slabs['B'] else 0.0
    if sb_drop > 0:
        dim_cut((b + 10.0, 0), (b + 10.0, h - sb_drop), (b + 18.0, 0), 90)
        dim_cut((b + 10.0, h - sb_drop), (b + 10.0, h), (b + 18.0, h - sb_drop), 90)
        dim_cut((b + 10.0, 0), (b + 10.0, h), (b + 32.0, 0), 90)
    else:
        dim_cut((b + 10.0, 0), (b + 10.0, h), (b + 22.0, 0), 90)

    # Left side height dimension (only if slab drop exists on A)
    sa_drop = slabs['A'][0][1] if slabs['A'] else 0.0
    if sa_drop > 0:
        dim_cut((-10.0, 0), (-10.0, h - sa_drop), (-18.0, 0), 90)
        dim_cut((-10.0, h - sa_drop), (-10.0, h), (-18.0, h - sa_drop), 90)
        dim_cut((-10.0, 0), (-10.0, h), (-32.0, 0), 90)

    # 6. Titles
    beam_label = contract.get('beam') or 'Corte'
    _text(m, beam_label, b / 2.0, h + 30.0, height=14.0, layer='BNC_TEXTO', color=7, centered=True)
    _text(m, f"({b:g}x{h:g})", b / 2.0, h + 16.0, height=10.0, layer='BNC_TEXTO', color=7, centered=True)

    doc.header['$INSUNITS'] = 5
    return doc


def normalize_resources(doc):
    """Remove foreign table handles before CAD serialization."""
    for layer in doc.layers:
        for attr,kind in (('material_handle','MATERIAL'),('plotstyle_handle','ACDBPLACEHOLDER')):
            handle=layer.dxf.get(attr);entity=doc.entitydb.get(handle) if handle else None
            if handle and (entity is None or entity.dxftype()!=kind):layer.dxf.discard(attr)
        layer.set_required_attributes()
    for entity in doc.entitydb.values():
        if entity.is_alive and entity.xdata:
            for appid in entity.xdata.data:
                if appid not in doc.appids:doc.appids.new(appid)

def draw_ab(contract):
    from .lv_formascia_panels import draw_ab as approved
    doc=approved(contract);normalize_resources(doc);return doc

def draw_cut(contract):
    from .lv_formascia_cut import draw_cut as approved
    doc=approved(contract);normalize_resources(doc);return doc

def renderer_fingerprint():
    from hashlib import sha256
    from .lv_nova_design import renderer_fingerprint as nova_fingerprint
    paths=['lv_formascia_design.py','lv_formascia_panels.py','lv_formascia_cut.py','lv_formascia_grades.py','lv_formascia_sa_adapter.py']
    return sha256(nova_fingerprint().encode()+b''.join((Path(__file__).parent/p).read_bytes() for p in paths)).hexdigest()
