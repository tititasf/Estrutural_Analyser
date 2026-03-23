#!/usr/bin/env python3
"""
extrair_parametros_viga_v3.py — Extração STOG v3: Painéis + Seção separados
============================================================================
Melhoria fundamental sobre v2:
  - Y-clustering para separar Face A/B (não mais offset fixo)
  - Módulo PAINÉIS: Face A, Face B, sarrafos, labels, reaprov por painel
  - Módulo SEÇÃO: concreto, escoras, tensores, presilhas, barrotes
  - Cobertura alvo: 100% em ambos

Uso:
  python scripts/extrair_parametros_viga_v3.py --all
  python scripts/extrair_parametros_viga_v3.py --obra Obra_TREINO_21 --max 30
"""
import sys, io, json, re, os, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
from collections import defaultdict
import math

import ezdxf

BASE_DIR = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')
PANEL_LAYER_PATTERNS = ['pain', 'painel', 'paineis']  # match Painéis, paineis, etc.


def is_panel_layer(layer):
    """Check if layer is a panel-related layer (handles encoding)."""
    low = layer.lower()
    return any(p in low for p in PANEL_LAYER_PATTERNS)


def is_sarr_layer(layer):
    return 'sarr' in layer.lower()


def is_section_layer(layer):
    low = layer.lower()
    return any(k in low for k in ['concreto', 'cota se', 'texto se'])


def is_laje_layer(layer):
    up = layer.upper()
    return 'LAJ' in up or 'SCO' in up


# ═══════════════════════════════════════════════════════════════════
# ZONE DETECTION (same as v2, proven)
# ═══════════════════════════════════════════════════════════════════

def find_all_inserts(msp):
    vigas = []
    for e in msp:
        if e.dxftype() != 'INSERT' or not hasattr(e, 'attribs'):
            continue
        titulo = secao = reaprov = None
        for att in e.attribs:
            tag = att.dxf.tag.upper()
            val = att.dxf.text.strip()
            if tag in ('TITULO', 'TITULO1'):
                titulo = val
            elif tag in ('SECAO', 'SEÇÃO'):
                secao = val
            elif 'REAPROV' in tag:
                reaprov = val
        if titulo:
            vigas.append({
                'nome': titulo, 'secao': secao or '',
                'reaprov': reaprov or '',
                'x': e.dxf.insert.x, 'y': e.dxf.insert.y,
            })
    vigas.sort(key=lambda v: -v['y'])
    return vigas


def compute_zone(all_vigas, target_name):
    if not all_vigas:
        return None
    zones = []
    current = [all_vigas[0]]
    for i in range(1, len(all_vigas)):
        if current[-1]['y'] - all_vigas[i]['y'] < 150:
            current.append(all_vigas[i])
        else:
            zones.append(current)
            current = [all_vigas[i]]
    zones.append(current)

    for zi, zone in enumerate(zones):
        for v in zone:
            if v['nome'] == target_name:
                y_top = max(z['y'] for z in zone) + 80
                y_bot = max(z['y'] for z in zones[zi + 1]) if zi < len(zones) - 1 else min(z['y'] for z in zone) - 1000
                zone_by_x = sorted(zone, key=lambda z: z['x'])
                idx = next(i for i, z in enumerate(zone_by_x) if z['nome'] == target_name)
                x_left = (zone_by_x[idx]['x'] + zone_by_x[idx - 1]['x']) / 2 if idx > 0 else None
                x_right = (zone_by_x[idx]['x'] + zone_by_x[idx + 1]['x']) / 2 if idx < len(zone_by_x) - 1 else None
                return {
                    'y_top': y_top, 'y_bot': y_bot,
                    'x_left': x_left, 'x_right': x_right,
                    'insert_x': v['x'], 'insert_y': v['y'],
                    'secao': v['secao'], 'reaprov': v['reaprov'],
                    'zone_size': len(zone),
                }
    return None


# ═══════════════════════════════════════════════════════════════════
# ENTITY COLLECTION
# ═══════════════════════════════════════════════════════════════════

def get_entity_coords(e):
    """Get all (x, y) points of an entity."""
    etype = e.dxftype()
    pts = []
    try:
        if etype == 'LINE':
            pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        elif etype == 'LWPOLYLINE':
            pts = [(p[0], p[1]) for p in e.get_points(format='xy')]
        elif etype in ('TEXT', 'MTEXT', 'INSERT'):
            pts = [(e.dxf.insert.x, e.dxf.insert.y)]
        elif etype == 'HATCH':
            for p in e.paths:
                if hasattr(p, 'vertices'):
                    pts.extend([(v[0], v[1]) for v in p.vertices])
                elif hasattr(p, 'edges'):
                    for edge in p.edges:
                        for attr in ('start', 'end', 'center'):
                            if hasattr(edge, attr):
                                v = getattr(edge, attr)
                                try: pts.append((v.x, v.y))
                                except: pass
        elif etype == 'DIMENSION':
            if hasattr(e.dxf, 'defpoint'):
                pts.append((e.dxf.defpoint.x, e.dxf.defpoint.y))
            if hasattr(e.dxf, 'defpoint2'):
                pts.append((e.dxf.defpoint2.x, e.dxf.defpoint2.y))
            if hasattr(e.dxf, 'defpoint3'):
                pts.append((e.dxf.defpoint3.x, e.dxf.defpoint3.y))
        elif etype in ('CIRCLE', 'ARC'):
            pts = [(e.dxf.center.x, e.dxf.center.y)]
        elif etype == 'SOLID':
            for attr in ['vtx0', 'vtx1', 'vtx2', 'vtx3']:
                if hasattr(e.dxf, attr):
                    v = getattr(e.dxf, attr)
                    pts.append((v.x, v.y))
    except Exception:
        pass
    return pts


def entity_in_zone(pts, zone):
    if not pts:
        return False
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if not any(zone['y_bot'] <= y <= zone['y_top'] for y in ys):
        return False
    if zone['x_left'] is not None and max(xs) < zone['x_left']:
        return False
    if zone['x_right'] is not None and min(xs) > zone['x_right']:
        return False
    return True


def collect_zone_entities(msp, zone):
    """Collect all entities in zone, classified by type."""
    result = {
        'panel_h_lines': [],    # Horizontal lines on Painéis layer
        'panel_v_lines': [],    # Vertical lines on Painéis layer
        'sarr_lines': [],       # Lines on SARR_* layers (with Y positions)
        'dimensions': [],       # DIMENSION entities (cotas)
        'hatches': [],          # HATCH entities
        'texts': [],            # TEXT/MTEXT entities
        'section_entities': [], # Entities on section layers (Texto Seção, CONCRETO, etc.)
        'escora_entities': [],  # Entities on Escoras layer
        'tensor_entities': [],  # Entities on TENSOR layer
        'presilha_entities': [],# Entities on presilha layer
        'barrote_entities': [], # Entities on barrote/Madeira layer
        'laje_entities': [],    # Entities on SCO-___-LAJ layer
        # === NOVOS: geometria completa para reconstrução ===
        'concreto_polys': [],   # CONCRETO LWPOLYLINEs (aberturas de pilar/viga + seção)
        'sarr35_polys': [],     # SARR_3.5x7 LWPOLYLINEs (seção transversal)
        'sarr22_polys': [],     # SARR_2.2x7/2.2x10/EDITAR LWPOLYLINEs (sarrafo rectangles)
        'madeira_polys': [],    # Madeira LWPOLYLINEs (barrotes na seção)
        'panel_polys': [],      # Painéis LWPOLYLINEs (contornos laje, perfis sarrafo — raw)
        'inserts': [],          # INSERT blocks (título, blocos especiais)
        'continuation_texts': [],  # Textos "CONT. V###" e "VEM DA V#"
        'panel_dims': [],       # DIMENSION entities no layer Painéis
        'layers_used': defaultdict(int),
        'entity_count': 0,
    }

    for e in msp:
        pts = get_entity_coords(e)
        if not entity_in_zone(pts, zone):
            continue

        etype = e.dxftype()
        layer = e.dxf.layer if hasattr(e.dxf, 'layer') else '0'
        result['layers_used'][layer] += 1
        result['entity_count'] += 1

        xs = [p[0] for p in pts] if pts else []
        ys = [p[1] for p in pts] if pts else []

        # === LINES + LWPOLYLINE on panel layers ===
        if etype == 'LINE':
            dx = abs(e.dxf.end.x - e.dxf.start.x)
            dy = abs(e.dxf.end.y - e.dxf.start.y)

            if is_panel_layer(layer):
                if dx > dy and dx > 5:  # Horizontal (lowered threshold from 10 to 5)
                    result['panel_h_lines'].append({
                        'x1': round(min(e.dxf.start.x, e.dxf.end.x), 1),
                        'x2': round(max(e.dxf.start.x, e.dxf.end.x), 1),
                        'y': round((e.dxf.start.y + e.dxf.end.y) / 2, 1),
                        'len': round(dx, 1),
                    })
                elif dy > dx and dy > 3:  # Vertical (lowered from 5 to 3)
                    result['panel_v_lines'].append({
                        'x': round((e.dxf.start.x + e.dxf.end.x) / 2, 1),
                        'y1': round(min(e.dxf.start.y, e.dxf.end.y), 1),
                        'y2': round(max(e.dxf.start.y, e.dxf.end.y), 1),
                        'len': round(dy, 1),
                    })

            # Sarrafo lines (SARR_* layers) — MUST be inside LINE block
            if is_sarr_layer(layer):
                result['sarr_lines'].append({
                    'layer': layer,
                    'x1': round(min(e.dxf.start.x, e.dxf.end.x), 1),
                    'x2': round(max(e.dxf.start.x, e.dxf.end.x), 1),
                    'y1': round(min(e.dxf.start.y, e.dxf.end.y), 1),
                    'y2': round(max(e.dxf.start.y, e.dxf.end.y), 1),
                    'is_h': dx > dy,
                    'src': 'LINE',
                })

            low = layer.lower()
            if 'escor' in low:
                result['escora_entities'].append({
                    'type': 'LINE', 'layer': layer,
                    'x1': round(e.dxf.start.x, 1), 'y1': round(e.dxf.start.y, 1),
                    'x2': round(e.dxf.end.x, 1), 'y2': round(e.dxf.end.y, 1),
                })
            elif 'tensor' in low:
                result['tensor_entities'].append({
                    'type': 'LINE', 'layer': layer,
                    'x_mid': round((e.dxf.start.x + e.dxf.end.x) / 2, 1),
                    'y_mid': round((e.dxf.start.y + e.dxf.end.y) / 2, 1),
                })
            elif 'presil' in low:
                result['presilha_entities'].append({
                    'type': 'LINE', 'layer': layer,
                    'x_mid': round(sum(xs) / len(xs), 1) if xs else 0,
                    'y_mid': round(sum(ys) / len(ys), 1) if ys else 0,
                })
            elif 'barrote' in low or ('madeir' in low and dy > dx):
                result['barrote_entities'].append({
                    'type': 'LINE', 'layer': layer,
                    'y_mid': round(sum(ys) / len(ys), 1) if ys else 0,
                })

        # === LWPOLYLINE on panel layers (VT vigas use these) ===
        elif etype == 'LWPOLYLINE' and is_panel_layer(layer):
            poly_pts = list(e.get_points(format='xy'))
            if len(poly_pts) >= 2:
                # Capturar polyline RAW (contornos de laje, perfis de sarrafo etc.)
                result['panel_polys'].append({
                    'closed': e.is_closed,
                    'vertices': [(round(p[0], 1), round(p[1], 1)) for p in poly_pts],
                })
                # Também decompor em H/V para análise de painéis
                # Include the closing segment for closed polylines (last→first)
                all_segs = list(poly_pts)
                if e.is_closed and len(all_segs) >= 3:
                    all_segs.append(all_segs[0])
                for i in range(len(all_segs) - 1):
                    p1, p2 = all_segs[i], all_segs[i + 1]
                    dx = abs(p2[0] - p1[0])
                    dy = abs(p2[1] - p1[1])
                    if dx > dy and dx > 5:
                        result['panel_h_lines'].append({
                            'x1': round(min(p1[0], p2[0]), 1),
                            'x2': round(max(p1[0], p2[0]), 1),
                            'y': round((p1[1] + p2[1]) / 2, 1),
                            'len': round(dx, 1),
                        })
                    elif dy > dx and dy > 3:
                        result['panel_v_lines'].append({
                            'x': round((p1[0] + p2[0]) / 2, 1),
                            'y1': round(min(p1[1], p2[1]), 1),
                            'y2': round(max(p1[1], p2[1]), 1),
                            'len': round(dy, 1),
                        })

        # === LWPOLYLINE não-painel: CONCRETO, SARR_3.5x7, Madeira, SARR_2.2x* ===
        elif etype == 'LWPOLYLINE' and not is_panel_layer(layer):
            low = layer.lower()
            poly_pts = list(e.get_points(format='xy'))
            if poly_pts:
                pxs = [p[0] for p in poly_pts]
                pys = [p[1] for p in poly_pts]
                poly_info = {
                    'layer': layer,
                    'n_pts': len(poly_pts),
                    'x_min': round(min(pxs), 1), 'x_max': round(max(pxs), 1),
                    'y_min': round(min(pys), 1), 'y_max': round(max(pys), 1),
                    'width': round(max(pxs) - min(pxs), 1),
                    'height': round(max(pys) - min(pys), 1),
                    'closed': e.is_closed,
                    'vertices': [(round(p[0], 1), round(p[1], 1)) for p in poly_pts],
                }
                if 'concreto' in low:
                    result['concreto_polys'].append(poly_info)
                elif 'sarr' in low and '3.5' in layer:
                    result['sarr35_polys'].append(poly_info)
                elif 'madeir' in low or 'barrote' in low:
                    result['madeira_polys'].append(poly_info)

                # SARR LWPOLYLINE decomposition: SARR_2.2x7, SARR_2.2x10, SARR_EDITAR
                # These are small closed rectangles representing sarrafo cross-sections.
                # Store intact poly for faithful reconstruction, and also decompose each
                # edge into a sarr_line entry so face detection picks them up.
                if is_sarr_layer(layer) and '3.5' not in layer:
                    result['sarr22_polys'].append(poly_info)
                    all_seg_pts = list(poly_pts)
                    if e.is_closed and len(all_seg_pts) >= 3:
                        all_seg_pts.append(all_seg_pts[0])  # close the loop
                    for si in range(len(all_seg_pts) - 1):
                        sp1, sp2 = all_seg_pts[si], all_seg_pts[si + 1]
                        sdx = abs(sp2[0] - sp1[0])
                        sdy = abs(sp2[1] - sp1[1])
                        result['sarr_lines'].append({
                            'layer': layer,
                            'x1': round(min(sp1[0], sp2[0]), 1),
                            'x2': round(max(sp1[0], sp2[0]), 1),
                            'y1': round(min(sp1[1], sp2[1]), 1),
                            'y2': round(max(sp1[1], sp2[1]), 1),
                            'is_h': sdx > sdy,
                            'src': 'POLY',
                        })

        # === DIMENSION ===
        elif etype == 'DIMENSION':
            dp  = e.dxf.defpoint  if hasattr(e.dxf, 'defpoint')  else None
            dp2 = e.dxf.defpoint2 if hasattr(e.dxf, 'defpoint2') else None
            dp3 = e.dxf.defpoint3 if hasattr(e.dxf, 'defpoint3') else None
            tp  = e.dxf.text_midpoint if hasattr(e.dxf, 'text_midpoint') else None
            actual = e.dxf.actual_measurement if hasattr(e.dxf, 'actual_measurement') else 0
            if dp and dp2 and actual is not None and actual > 0:
                dx = abs(dp.x - dp2.x)
                dy = abs(dp.y - dp2.y)
                dim_rec = {
                    'actual': round(actual, 1),
                    'layer': layer,
                    'horizontal': dx > dy,
                    'x_mid': round((dp.x + dp2.x) / 2, 1),
                    'y_mid': round((dp.y + dp2.y) / 2, 1),
                    # defpoint (10): ponto na linha de cota (ref)
                    'x1': round(dp.x, 1), 'y1': round(dp.y, 1),
                    # defpoint2 (13): origem da 1ª linha de extensão
                    'x2': round(dp2.x, 1), 'y2': round(dp2.y, 1),
                }
                # defpoint3 (14): origem da 2ª linha de extensão
                if dp3:
                    dim_rec['x3'] = round(dp3.x, 1)
                    dim_rec['y3'] = round(dp3.y, 1)
                # text_midpoint (11): posição do texto da cota
                if tp:
                    dim_rec['text_x'] = round(tp.x, 1)
                    dim_rec['text_y'] = round(tp.y, 1)
                result['dimensions'].append(dim_rec)
                # Painéis layer dims armazenados separado (usados para posições de painel)
                if is_panel_layer(layer):
                    result['panel_dims'].append(dim_rec)

        # === HATCH ===
        elif etype == 'HATCH':
            try:
                pattern = e.dxf.pattern_name if hasattr(e.dxf, 'pattern_name') else 'SOLID'
                scale = e.dxf.pattern_scale if hasattr(e.dxf, 'pattern_scale') else 1.0
                all_pts = []
                boundary_polys = []
                for p in e.paths:
                    path_pts = []
                    if hasattr(p, 'vertices'):
                        path_pts = [(v[0], v[1]) for v in p.vertices]
                    elif hasattr(p, 'edges'):
                        for edge in p.edges:
                            for attr in ('start', 'end', 'center'):
                                if hasattr(edge, attr):
                                    v = getattr(edge, attr)
                                    try: path_pts.append((v.x, v.y))
                                    except: pass
                    all_pts.extend(path_pts)
                    if path_pts:
                        boundary_polys.append([(round(p[0],1), round(p[1],1)) for p in path_pts])
                if all_pts:
                    result['hatches'].append({
                        'pattern': pattern, 'layer': layer,
                        'scale': round(scale, 3),
                        'x_min': round(min(p[0] for p in all_pts), 1),
                        'x_max': round(max(p[0] for p in all_pts), 1),
                        'y_min': round(min(p[1] for p in all_pts), 1),
                        'y_max': round(max(p[1] for p in all_pts), 1),
                        'boundary_polys': boundary_polys,
                    })
            except Exception:
                pass

        # === TEXT ===
        elif etype in ('TEXT', 'MTEXT'):
            txt = e.dxf.text if etype == 'TEXT' else (e.text if hasattr(e, 'text') else '')
            if etype == 'MTEXT':
                txt = re.sub(r'\{[^}]*?;', '', txt).replace('}', '').replace('{', '')
                txt = re.sub(r'\\[A-Za-z][^;]*;', '', txt)
            txt = txt.strip()
            result['texts'].append({
                'text': txt, 'layer': layer,
                'x': round(e.dxf.insert.x, 1), 'y': round(e.dxf.insert.y, 1),
            })
            # Continuation texts ("CONT. V###" ou "VEM DA V#")
            if 'cont.' in txt.lower() or 'vem da' in txt.lower():
                result['continuation_texts'].append({
                    'text': txt, 'layer': layer,
                    'x': round(e.dxf.insert.x, 1), 'y': round(e.dxf.insert.y, 1),
                })

        # === INSERT (blocks: presilha, barrote, título) ===
        elif etype == 'INSERT':
            low = layer.lower()
            if 'presil' in low:
                result['presilha_entities'].append({
                    'type': 'INSERT', 'layer': layer,
                    'x_mid': round(e.dxf.insert.x, 1),
                    'y_mid': round(e.dxf.insert.y, 1),
                })
            elif 'tensor' in low:
                result['tensor_entities'].append({
                    'type': 'INSERT', 'layer': layer,
                    'x_mid': round(e.dxf.insert.x, 1),
                    'y_mid': round(e.dxf.insert.y, 1),
                })
            # Capturar TODOS os inserts (blocos de título, etc.)
            attribs = {}
            if hasattr(e, 'attribs'):
                for att in e.attribs:
                    attribs[att.dxf.tag.upper()] = att.dxf.text.strip()
            result['inserts'].append({
                'block': e.dxf.name if hasattr(e.dxf, 'name') else '',
                'layer': layer,
                'x': round(e.dxf.insert.x, 1), 'y': round(e.dxf.insert.y, 1),
                'attribs': attribs,
            })

        # === LAJE ===
        if is_laje_layer(layer):
            result['laje_entities'].append({
                'type': etype, 'layer': layer,
                'y_mid': round(sum(ys) / len(ys), 1) if ys else 0,
                'x_mid': round(sum(xs) / len(xs), 1) if xs else 0,
            })

    return result


# ═══════════════════════════════════════════════════════════════════
# MODULE 1: PAINÉIS (Face A + Face B)
# ═══════════════════════════════════════════════════════════════════

def y_cluster(values, gap_threshold=15):
    """Cluster Y values into groups separated by gaps > threshold.
    Returns list of clusters, each cluster = list of original values.
    """
    if not values:
        return []
    sorted_vals = sorted(values)
    clusters = [[sorted_vals[0]]]
    for v in sorted_vals[1:]:
        if v - clusters[-1][-1] > gap_threshold:
            clusters.append([v])
        else:
            clusters[-1].append(v)
    return clusters


def detect_faces_by_clustering(panel_h_lines, panel_v_lines, insert_y,
                                insert_x=None, x_left=None, x_right=None,
                                y_top=None):
    """Detect Face A and Face B using face-rail anchor lines + X-zone pre-filter.

    Strategy:
    1. Pre-filter H-lines to current viga's X zone (eliminates foreign vigas whose
       lines share the same Y-band for edge vigas with x_left=None or x_right=None)
    2. Find 'face rail' anchor lines: H-lines with length >= 30% of max line length.
       Face bottom rails are the longest H-lines; section-detail and label lines are
       much shorter and are excluded by this threshold.
    3. Group close anchors (within 60 units) — multiple rails of the same face
       (e.g. bottom + second rail) form one group.
    4. For each anchor group, collect all filtered H-lines from [group_min_y - 20]
       upward by FACE_HEIGHT_MAX.  FACE_HEIGHT_MAX = 85% of the gap to the next
       anchor group (prevents capturing a higher face), or 600 for the topmost group.
    5. Face A = highest y_mid candidate (closest to insert), Face B = next.
    """
    if not panel_h_lines:
        return None, None

    # === STEP 0: Y proximity pre-filter — keep only lines near the face ===
    # The zone Y range spans two viga rows (y_bot = neighbor's insert_y), so
    # lines from the row below leak into this zone.  The fixed threshold of 350
    # was too aggressive for vigas where insert is close to y_top (V403/TREINO_11:
    # faces at 400+ below y_top, V305/TREINO_1: faces at 380-580 below y_top).
    # Fix: use 750 units below y_top — covers the tallest known face positions
    # (max ~700 DXF units) while still excluding the neighbor row (which is
    # typically 900+ units below y_top in standard STOG layout).
    if y_top is not None:
        y_prefilter_min = y_top - 750
        prefiltered = [l for l in panel_h_lines if l['y'] >= y_prefilter_min]
        if len(prefiltered) >= 2:
            panel_h_lines = prefiltered

    # === STEP 1: Pre-filter H-lines to current viga's X zone ===
    filtered_lines = list(panel_h_lines)

    x_filter_left = None
    x_filter_right = None
    if x_left is not None:
        x_filter_left = x_left - 50
    elif insert_x is not None:
        x_filter_left = max(0.0, insert_x - 400)
    if x_right is not None:
        x_filter_right = x_right + 50
    elif insert_x is not None:
        # Fallback for right-edge vigas: cap at insert_x + 1500 (≈15m max face width)
        x_filter_right = insert_x + 1500

    if x_filter_left is not None:
        if x_left is not None:
            # Explicit left boundary from neighbor: use midpoint to decide ownership.
            # A line whose midpoint is within the zone belongs to this viga, even if
            # its x1 extends beyond x_left (common for wide formwork spanning multiple
            # sections, e.g. V314/TREINO_5 where face spans x=11174→11659 but
            # x_left=11401).  Fall back to x2 check if midpoint filter drops all.
            narrowed = [l for l in filtered_lines
                        if (l['x1'] + l['x2']) / 2 >= x_filter_left]
            if not narrowed:
                narrowed = [l for l in filtered_lines if l['x2'] >= x_filter_left]
        else:
            # Fallback (left-edge viga with no known left neighbor): use x2 to be
            # inclusive — the line must at least END within the zone.
            narrowed = [l for l in filtered_lines if l['x2'] >= x_filter_left]
        if narrowed:
            filtered_lines = narrowed
    if x_filter_right is not None:
        if x_right is not None:
            # Explicit right boundary from neighbor: require that the line START
            # (x1) is within the zone.  The previous x2 filter was too strict —
            # wide face lines that span across zone boundaries (common in multi-
            # section formwork like V203/TREINO_5 with lines from 6603→7574) have
            # their x1 well inside the zone but x2 extends beyond x_right.
            # Using x1 keeps the line if it originates in this viga's zone, which
            # is the correct semantic: "the line belongs to this viga."
            narrowed = [l for l in filtered_lines if l['x1'] <= x_filter_right]
        else:
            # Fallback right cap (right-edge viga): use x_mid to avoid cutting valid
            # wide face lines that extend past the estimate.
            narrowed = [l for l in filtered_lines
                        if (l['x1'] + l['x2']) / 2 <= x_filter_right]
        if narrowed:
            filtered_lines = narrowed

    if not filtered_lines:
        filtered_lines = list(panel_h_lines)  # safety fallback

    # === STEP 2: Find face-rail anchor lines ===
    max_len = max(l['len'] for l in filtered_lines)
    anchor_min_len = max(50, max_len * 0.30)
    anchor_lines = sorted(
        [l for l in filtered_lines if l['len'] >= anchor_min_len],
        key=lambda l: l['y'],
    )
    if not anchor_lines:
        # Fallback: use 3 longest lines as anchors
        anchor_lines = sorted(filtered_lines, key=lambda l: -l['len'])[:3]
        anchor_lines.sort(key=lambda l: l['y'])

    # === STEP 3: Group close anchor lines (same face has close rail lines) ===
    # Gap threshold raised to 220: within a single face the bottom rail and top
    # closure lines can be separated by up to ~200 DXF units (V301=203, V303=125).
    # Actual distinct Face A / Face B pairs are always >250 units apart in the
    # LV drawing layout, so 220 merges within-face rails without merging faces.
    ANCHOR_GROUP_GAP = 220
    anchor_groups = []  # list of (group_min_y, group_max_y)
    g_min = anchor_lines[0]['y']
    g_max = anchor_lines[0]['y']
    for al in anchor_lines[1:]:
        if al['y'] - g_max <= ANCHOR_GROUP_GAP:
            g_max = al['y']
        else:
            anchor_groups.append((g_min, g_max))
            g_min = al['y']
            g_max = al['y']
    anchor_groups.append((g_min, g_max))

    # === STEP 4: Build face candidates, one per anchor group ===
    face_candidates = []
    for i, (g_min_y, g_max_y) in enumerate(anchor_groups):
        # Face bottom starts at g_min_y; extend upward
        face_y_low = g_min_y - 20
        if i + 1 < len(anchor_groups):
            next_g_min = anchor_groups[i + 1][0]
            fhm = max(200, (next_g_min - g_min_y) * 0.85)
        else:
            fhm = 600  # generous default for topmost anchor group
        face_y_high = g_min_y + fhm

        face_lines = [l for l in filtered_lines
                      if face_y_low <= l['y'] <= face_y_high]
        if not face_lines:
            continue
        y_min_f = min(l['y'] for l in face_lines)
        y_max_f = max(l['y'] for l in face_lines)
        max_width = max(l['len'] for l in face_lines)
        if max_width < 50:
            continue
        face_candidates.append({
            'y_min': y_min_f, 'y_max': y_max_f,
            'y_mid': (y_min_f + y_max_f) / 2,
            'lines': face_lines,
            'max_width': max_width,
            'n_lines': len(face_lines),
        })

    if not face_candidates:
        return None, None

    # Sort by y_mid descending (highest = closest to insert/title block)
    face_candidates.sort(key=lambda f: -f['y_mid'])

    face_a_data = face_candidates[0]
    face_b_data = face_candidates[1] if len(face_candidates) >= 2 else None

    # Sanity check: Face A should be closer to insert than Face B
    if face_a_data and face_b_data:
        if abs(face_b_data['y_mid'] - insert_y) < abs(face_a_data['y_mid'] - insert_y):
            face_a_data, face_b_data = face_b_data, face_a_data

    return face_a_data, face_b_data


def extract_panels_from_face(face_data, v_lines, dimensions, hatches, texts, insert_y,
                              insert_x=None, x_right=None, x_left=None):
    """Extract detailed panel data from a face cluster.

    insert_x, x_right, x_left: zone boundaries used to cap X extent and prevent
    capturing panels from neighbouring vigas (critical when x_right is None).
    """
    if not face_data:
        return {
            'height': 0, 'total_width': 0, 'y_min': 0, 'y_max': 0,
            'face_x_min': 0, 'face_x_max': 0,
            'panel_count': 0, 'panel_widths': [],
            'panel_positions': [],
            'panel_labels': [], 'panel_reaprov': [],
            'sarrafo_ys': [],
        }

    lines = face_data['lines']
    y_min = face_data['y_min']
    y_max = face_data['y_max']

    # Height and total width
    height = round(y_max - y_min, 1)
    total_width = round(face_data['max_width'], 1)

    # Get the X extent of the face using only substantial lines to avoid
    # short label/annotation lines (len << max_width) from skewing x bounds.
    all_x1 = [ln['x1'] for ln in lines]
    all_x2 = [ln['x2'] for ln in lines]
    max_line_len = face_data.get('max_width', 1) or 1
    len_thresh = max(20, max_line_len * 0.30)
    long_lines = [ln for ln in lines if ln['len'] >= len_thresh]
    if not long_lines:
        long_lines = lines
    face_x_min = min(ln['x1'] for ln in long_lines)
    face_x_max = max(ln['x2'] for ln in long_lines)

    # === X-CAP: zone bounds + gap-based refinement for edge vigas ===
    # For vigas with both x_left and x_right known, use zone bounds directly.
    # For edge vigas (x_left=None or x_right=None), detect natural gaps between
    # viga groups in the face Y-band to locate this viga's panels precisely.
    if insert_x is not None:
        need_gap = (x_left is None or x_right is None)

        gap_left = gap_right = None
        if need_gap:
            # Use H-line anchor groups for gap detection instead of v_lines.
            # V-line clusters are contaminated by annotation endpoints (span≈65)
            # and sub-section ties (span≈109) in the inter-viga gap area, which
            # cause spurious groups that produce wrong face_x boundaries.
            # Anchor H-lines (len >= 30% of max_width) are exclusively structural
            # rails with clean X extents that directly encode each section boundary.
            max_hlen = face_data.get('max_width', 1) or 1
            anchor_h_thresh = max(50, max_hlen * 0.30)

            # Collect unique (x_min, x_max) extents from anchor H-lines
            seen_ranges: set = set()
            anchor_ranges = []
            for ln in lines:
                if ln['len'] >= anchor_h_thresh:
                    r = (round(ln['x1'], 0), round(ln['x2'], 0))
                    if r not in seen_ranges:
                        seen_ranges.add(r)
                        anchor_ranges.append(r)
            anchor_ranges.sort(key=lambda r: r[0])

            # Group anchor ranges: gap > H_GAP_THRESH means distinct viga sections.
            # H_GAP_THRESH=150: > sub-section internal gap (~109, merges into one
            # face group) but << inter-viga gap (~900+, splits sections correctly).
            H_GAP_THRESH = 150
            h_groups = []
            if anchor_ranges:
                g_min, g_max = anchor_ranges[0]
                for r_min, r_max in anchor_ranges[1:]:
                    if r_min - g_max > H_GAP_THRESH:
                        h_groups.append((g_min, g_max))
                        g_min, g_max = r_min, r_max
                    else:
                        g_max = max(g_max, r_max)
                h_groups.append((g_min, g_max))

            # Target group: first with x_max >= insert_x - 300
            target_idx = None
            for i, (gmin, gmax) in enumerate(h_groups):
                if gmax >= insert_x - 300:
                    target_idx = i
                    break
            if target_idx is None and h_groups:
                target_idx = len(h_groups) - 1

            if target_idx is not None:
                tmin, tmax = h_groups[target_idx]
                if target_idx > 0:
                    # Cap left at the exact start of the target H-line group
                    gap_left = float(tmin)
                if target_idx < len(h_groups) - 1:
                    # Cap right at the exact end of the target H-line group
                    gap_right = float(tmax)

        # Apply zone constraints; gap detection further tightens for edge vigas
        x_cap_left = x_left if x_left is not None else None
        x_cap_right = x_right if x_right is not None else None

        if gap_left is not None:
            # gap detection tightens the missing or known left bound
            x_cap_left = max(gap_left, x_cap_left) if x_cap_left is not None else gap_left
        if gap_right is not None:
            x_cap_right = min(gap_right, x_cap_right) if x_cap_right is not None else gap_right

        # Final fallbacks when gap detection found nothing for edge vigas
        if x_cap_left is None:
            x_cap_left = insert_x - 400
        if x_cap_right is None:
            x_cap_right = insert_x + 2000

        face_x_max = min(face_x_max, x_cap_right)
        face_x_min = max(face_x_min, x_cap_left)

    total_width = (face_x_max - face_x_min) if face_x_max > face_x_min else total_width

    # === PANEL WIDTHS ===
    # Strategy 1: From DIMENSION entities (COTA) in face Y-band
    _x_dim_left = face_x_min - 20
    _x_dim_right = face_x_max + 20
    face_dims = [d for d in dimensions
                 if d['horizontal']
                 and 'cota' in d['layer'].lower()
                 and y_min - 20 <= d['y_mid'] <= y_max + 50
                 and _x_dim_left <= d['x_mid'] <= _x_dim_right
                 and d['actual'] > 30]
    # If no dims found in face bounds, expand search to zone left margin.
    # STOG edge vigas sometimes place panel annotations in a left annotation
    # column (far outside face_x_min) when the face is far from zone x_left.
    if not face_dims and x_left is not None and face_x_min - x_left > 400:
        _x_dim_left = x_left - 100
        face_dims = [d for d in dimensions
                     if d['horizontal']
                     and 'cota' in d['layer'].lower()
                     and y_min - 20 <= d['y_mid'] <= y_max + 50
                     and _x_dim_left <= d['x_mid'] <= _x_dim_right
                     and d['actual'] > 30]

    # STOG panels: max 300cm individual. Anything > 300 is a total/compound.
    MAX_PANEL_W = 300

    # Strategy 0: Y-band grouping — find COTA dims at the SAME Y level that sum
    # to ≈ total_width.  STOG drafters often place all panel COTAs at one horizontal
    # annotation line just outside the face body (common pattern: 4×244 at y=y_min-13).
    # Using set() would collapse duplicates, so we work on the raw list here.
    # factor=2 handles two-section formwork where annotations cover one section only.
    panel_widths_from_group = None
    total_from_group = None
    if face_dims and total_width > 0:
        Y_BAND_TOL = 15
        cota_by_yband: dict = {}
        for d in face_dims:
            yb = round(d['y_mid'] / Y_BAND_TOL) * Y_BAND_TOL
            cota_by_yband.setdefault(yb, []).append(round(d['actual'], 1))
        for yb in sorted(cota_by_yband):
            # Exclude total/compound dims (> MAX_PANEL_W) — keep only panel widths
            vals = [v for v in cota_by_yband[yb] if 20 < v <= MAX_PANEL_W]
            if not vals:
                continue
            s = round(sum(vals), 1)
            # Try factor=1 (normal single-section), then factor=2 (two-section formwork
            # where annotations annotate only one symmetric sub-section)
            for factor in (1, 2):
                fs = round(s * factor, 1)
                if 0.88 <= fs / total_width <= 1.12 and 1 <= len(vals) * factor <= 12:
                    panel_widths_from_group = sorted(vals * factor)
                    total_from_group = fs
                    break
            if panel_widths_from_group is not None:
                break  # lowest-y band that matches → main panel annotation row

    # Strategy 1: dedup-based COTA matching (handles cases where a total dim exists)
    all_dim_values = sorted(set(round(d['actual'], 1) for d in face_dims))
    total_dim = max(all_dim_values) if all_dim_values else 0

    # Panel widths = values <= MAX_PANEL_W and < total (with 5% tolerance)
    panel_widths_from_dims = [v for v in all_dim_values if v <= MAX_PANEL_W and (total_dim == 0 or v < total_dim * 0.95)]

    # Strategy 2: From vertical panel divider lines in face Y-band
    face_vlines = [vl for vl in v_lines
                   if vl['y1'] <= y_max + 5 and vl['y2'] >= y_min - 5
                   and face_x_min - 5 <= vl['x'] <= face_x_max + 5]

    panel_widths_from_vlines = []
    if face_vlines:
        # Sort vertical lines by X
        vline_xs = sorted(set(round(vl['x'], 0) for vl in face_vlines))
        # Add face edges
        all_dividers = [face_x_min] + list(vline_xs) + [face_x_max]
        # Remove duplicates (within tolerance 3)
        clean_dividers = [all_dividers[0]]
        for x in all_dividers[1:]:
            if x - clean_dividers[-1] > 3:
                clean_dividers.append(x)
        # Compute widths between dividers (cap at MAX_PANEL_W=300)
        for i in range(len(clean_dividers) - 1):
            w = round(clean_dividers[i + 1] - clean_dividers[i], 1)
            if 20 < w <= MAX_PANEL_W:  # Min 20, max 300 (STOG standard)
                panel_widths_from_vlines.append(w)

    # Choose best panel widths source (priority: S0 > S1 > S2 > fallback)
    if panel_widths_from_group:
        # Strategy 0 winner: Y-band COTAs sum to total_width
        panel_widths = panel_widths_from_group
        total_width_final = total_from_group
    elif panel_widths_from_dims and total_dim > 0:
        # Strategy 1: dedup COTA with total-dim ratio test
        s = sum(panel_widths_from_dims)
        if 0.85 <= s / total_dim <= 1.15:
            panel_widths = panel_widths_from_dims
            total_width_final = total_dim
        elif panel_widths_from_vlines:
            panel_widths = panel_widths_from_vlines
            total_width_final = round(sum(panel_widths_from_vlines), 1)
        else:
            panel_widths = panel_widths_from_dims
            total_width_final = total_dim
    elif panel_widths_from_vlines:
        panel_widths = panel_widths_from_vlines
        total_width_final = round(sum(panel_widths_from_vlines), 1)
    elif all_dim_values:
        # Fallback: use all dim values as potential panels
        panel_widths = [v for v in all_dim_values if 40 <= v <= 300]
        total_width_final = total_width
    else:
        panel_widths = []
        total_width_final = total_width

    # === OVER-EXTRACTION CAP ===
    # STOG vigas typically have 1-12 panels per face.
    # If we extracted more, attempt to select the subset summing to total_width.
    MAX_PANELS_PER_FACE = 12
    if len(panel_widths) > MAX_PANELS_PER_FACE:
        if total_width_final > 0:
            # Greedy: pick largest panels that fit within total_width_final
            sorted_w = sorted(panel_widths, reverse=True)
            sel, rem = [], total_width_final
            for w in sorted_w:
                if w <= rem + 5 and rem > 10:
                    sel.append(w)
                    rem -= w
            if sel and total_width_final > 0 and abs(sum(sel) - total_width_final) / total_width_final < 0.25:
                panel_widths = sorted(sel)
            else:
                panel_widths = panel_widths[:MAX_PANELS_PER_FACE]
        else:
            panel_widths = panel_widths[:MAX_PANELS_PER_FACE]

    # === PANEL LABELS (P1, P2, ...) ===
    face_texts = [t for t in texts
                  if y_min - 20 <= t['y'] <= y_max + 30
                  and face_x_min - 10 <= t['x'] <= face_x_max + 10
                  and re.match(r'^P?\d+$', t['text'])
                  and t['layer'] in ('5', 'texto', 'NOMENCLATURA')]
    panel_labels = sorted([t['text'] for t in face_texts],
                          key=lambda t: int(re.sub(r'\D', '', t) or '0'))

    # === REAPROVEITAMENTO PER PANEL ===
    reaprov_hatches = [h for h in hatches
                       if 'reaprov' in h['layer'].lower()
                       and h['y_min'] >= y_min - 5 and h['y_max'] <= y_max + 5
                       and h['x_min'] >= face_x_min - 5 and h['x_max'] <= face_x_max + 5]
    panel_reaprov = []
    if reaprov_hatches and panel_widths:
        # Map each hatch to a panel index by X position
        cum_x = face_x_min
        for i, pw in enumerate(panel_widths):
            has_reaprov = any(
                h['x_min'] < cum_x + pw and h['x_max'] > cum_x
                for h in reaprov_hatches
            )
            if has_reaprov:
                panel_reaprov.append(i + 1)  # 1-indexed
            cum_x += pw

    # === PANEL POSITIONS: absolute X para cada painel ===
    # Tenta extrair dos endpoints dos COTAs no layer Painéis (mais preciso que v-lines).
    # Cada COTA H na face tem defpoint.x e defpoint2.x = bordas exatas do painel.
    panel_positions = _compute_panel_positions(
        panel_widths, face_x_min, face_x_max, dimensions, y_min, y_max
    )

    # === FACE H-LINES: todas as linhas horizontais na face ===
    # Necessário para reconstrução idêntica: cada H-line é uma linha DXF em y com x1..x2.
    # Inclui TODAS as linhas (curtas e longas) — o gerador precisa de cada uma.
    # Filtramos apenas anotações duplas: se duas linhas têm exatamente y+dx < 3 e len < 20,
    # é ruído de duplicatas de anotação.
    seen_hline = set()
    face_hlines = []
    for ln in sorted(lines, key=lambda l: l['y']):
        key = (round(ln['y'], 0), round(ln['x1'], 0), round(ln['x2'], 0))
        if key in seen_hline:
            continue
        seen_hline.add(key)
        face_hlines.append({
            'y': round(ln['y'], 1),
            'x1': round(ln['x1'], 1),
            'x2': round(ln['x2'], 1),
            'len': round(ln['len'], 1),
        })

    # === SARRAFOS + V-LINES DESTA FACE ===
    face_sarr_xs = []
    seen_vline = set()
    face_vlines = []
    for vl in v_lines:
        if (vl['y1'] <= y_max + 5 and vl['y2'] >= y_min - 5 and
                face_x_min - 5 <= vl['x'] <= face_x_max + 5):
            face_sarr_xs.append(round(vl['x'], 1))
            key = (round(vl['x'], 0), round(vl['y1'], 0), round(vl['y2'], 0))
            if key not in seen_vline:
                seen_vline.add(key)
                face_vlines.append({
                    'x': round(vl['x'], 1),
                    'y1': round(vl['y1'], 1),
                    'y2': round(vl['y2'], 1),
                    'len': round(abs(vl['y2'] - vl['y1']), 1),
                })
    face_sarr_xs_unique = sorted(set(face_sarr_xs))
    face_vlines.sort(key=lambda v: (v['x'], v['y1']))

    return {
        'height': height,
        'total_width': round(total_width_final, 1),
        'face_x_min': round(face_x_min, 1),
        'face_x_max': round(face_x_max, 1),
        'y_min': round(y_min, 1),
        'y_max': round(y_max, 1),
        'panel_count': len(panel_widths),
        'panel_widths': [round(w, 1) for w in panel_widths],
        'panel_positions': panel_positions,  # [{x_start, x_end, width}] absolutos
        'face_hlines': face_hlines,          # H-lines exatas para reconstrução
        'face_vlines': face_vlines,          # V-lines exatas para reconstrução
        'face_sarr_xs': face_sarr_xs_unique, # X positions dos sarrafos (SARR lines)
        'panel_labels': panel_labels,
        'panel_reaprov': panel_reaprov,  # list of 1-indexed panel IDs with reaprov
    }


def _compute_panel_positions(panel_widths, face_x_min, face_x_max, dimensions, y_min, y_max):
    """Compute absolute X position for each panel.

    Strategy A: Use COTA dimension endpoints in the face Y-band — each horizontal
    COTA in the Painéis layer has its measurement endpoints at the exact panel edges.
    Group COTAs by actual measurement value and align with panel_widths.

    Strategy B (fallback): Evenly space panels from face_x_min using panel_widths.
    """
    if not panel_widths:
        return []

    # Strategy A: COTAs with horizontal orientation in face Y-band
    cota_h = [d for d in dimensions
               if d['horizontal'] and d['actual'] > 20
               and y_min - 30 <= d['y_mid'] <= y_max + 60
               and face_x_min - 10 <= d['x_mid'] <= face_x_max + 10]

    # Build candidate (x_start, x_end) pairs from dim endpoints
    cota_edges = []
    for d in cota_h:
        xs = sorted([d['x1'], d['x2']])
        if xs[1] - xs[0] > 20:  # real measurement, not annotation spike
            cota_edges.append((round(xs[0], 1), round(xs[1], 1), round(d['actual'], 1)))

    # Match to panel_widths: for each panel width, find a cota_edge with matching actual
    positions = []
    used = set()
    for pw in panel_widths:
        best = None
        for i, (xs, xe, act) in enumerate(cota_edges):
            if i in used:
                continue
            if abs(act - pw) <= 3:  # within 3 DXF units tolerance
                if best is None or abs(act - pw) < abs(cota_edges[best][2] - pw):
                    best = i
        if best is not None:
            used.add(best)
            xs, xe, act = cota_edges[best]
            positions.append({'x_start': xs, 'x_end': xe, 'width': round(xe - xs, 1)})

    # If cota matching gave us all panels in order, validate they tile correctly
    if len(positions) == len(panel_widths):
        positions.sort(key=lambda p: p['x_start'])
        # Validate: adjacent panels must share edges (within 5 units)
        valid = True
        for i in range(len(positions) - 1):
            gap = abs(positions[i + 1]['x_start'] - positions[i]['x_end'])
            if gap > 5:
                valid = False
                break
        if valid:
            return positions

    # Strategy B: evenly space from face_x_min
    positions = []
    x = face_x_min
    for pw in panel_widths:
        positions.append({'x_start': round(x, 1), 'x_end': round(x + pw, 1), 'width': round(pw, 1)})
        x += pw
    return positions


def extract_aberturas(ents, zone, face_a, face_b):
    """Extrai aberturas de pilar/viga da zona.

    No STOG, aberturas são representadas por LWPOLYLINEs no layer CONCRETO.
    Cada CONCRETO poly dentro do y-range de uma face = abertura de pilar/viga
    que intersecta a fôrma.

    Classifica como:
    - 'pilar': poly dentro do y-range da face (abertura lateral da fôrma)
    - 'seccao': poly na região da seção transversal (próxima ao INSERT)
    """
    aberturas = []
    insert_x = zone['insert_x']
    insert_y = zone['insert_y']
    # Limite inferior: zona abaixo da linha de vigas vizinhas (exclui seções da linha de baixo)
    y_floor = zone.get('y_bot', 0) + 20  # polys no limite inferior pertencem à linha abaixo

    for poly in ents.get('concreto_polys', []):
        # Excluir polys que pertencem à linha de vigas abaixo (y_max <= y_floor)
        if poly['y_max'] <= y_floor:
            continue
        abertura = {
            'type': 'concreto',
            'layer': poly['layer'],
            'x_min': poly['x_min'],
            'x_max': poly['x_max'],
            'y_min': poly['y_min'],
            'y_max': poly['y_max'],
            'width': poly['width'],
            'height': poly['height'],
            'subtype': 'desconhecido',
        }

        # Classificar pela posição X relativa à face:
        # - À ESQUERDA da face (x_max < face_x_min): seção transversal (pillar section view)
        # - DENTRO da face (overlaps face X range): abertura real no painel
        face_x_min_a = face_a.get('face_x_min', insert_x) if face_a and face_a.get('face_x_min', 0) > 0 else insert_x
        face_x_max_a = face_a.get('face_x_max', insert_x + 2000) if face_a else insert_x + 2000

        poly_in_face_x = (poly['x_max'] >= face_x_min_a - 30 and poly['x_min'] <= face_x_max_a + 30)

        if not poly_in_face_x:
            # À esquerda (ou direita) da face — é seção transversal
            abertura['subtype'] = 'seccao_transversal'
        else:
            # Dentro do X range da face — é abertura de pilar/viga no painel
            in_face_a_y = (face_a and face_a.get('y_min', 0) > 0 and
                           poly['y_min'] <= face_a['y_max'] + 30 and
                           poly['y_max'] >= face_a['y_min'] - 30)
            in_face_b_y = (face_b and face_b.get('y_min', 0) > 0 and
                           poly['y_min'] <= face_b['y_max'] + 30 and
                           poly['y_max'] >= face_b['y_min'] - 30)
            if in_face_a_y:
                abertura['subtype'] = 'pilar_face_a'
            elif in_face_b_y:
                abertura['subtype'] = 'pilar_face_b'
            else:
                abertura['subtype'] = 'pilar'

        aberturas.append(abertura)

    return aberturas


def extract_section_geometry(ents, zone, face_a):
    """Extrai geometria exata da seção transversal.

    A seção transversal fica à esquerda dos painéis (próxima ao INSERT).
    Contém:
    - CONCRETO poli (seção do concreto: b_alma x h_total)
    - SARR_3.5x7 polys (sarrafo cross-section rectangles)
    - Madeira polys (barrotes/boards cross-section)
    - INSERT bloco título (titulo1)
    """
    insert_x = zone['insert_x']
    insert_y = zone['insert_y']

    # Seção transversal: region próxima ao insert, à esquerda dos painéis
    face_x_min = face_a.get('face_x_min', insert_x) if face_a else insert_x
    sect_x_max = face_x_min + 50  # pequena margem à direita da seção
    sect_x_min = insert_x - 400   # região à esquerda

    # CONCRETO poly da seção (o mais próximo do INSERT)
    seccao_concreto = None
    sect_concreto = [p for p in ents.get('concreto_polys', [])
                     if p['x_min'] <= sect_x_max and p['x_max'] >= sect_x_min - 50
                     and p['y_min'] <= insert_y + 10 and p['y_max'] >= insert_y - 200]
    if sect_concreto:
        # Mais próximo do INSERT
        sect_concreto.sort(key=lambda p: abs(p['x_min'] - insert_x))
        seccao_concreto = sect_concreto[0]

    # SARR_3.5x7 polys na região da seção
    sarr35_polys = [p for p in ents.get('sarr35_polys', [])
                    if p['x_max'] <= sect_x_max + 200]

    # Madeira (barrote) polys na região da seção
    madeira_polys = [p for p in ents.get('madeira_polys', [])
                     if p['x_max'] <= sect_x_max + 200]

    # INSERT titulo1 (o bloco de título da viga)
    titulo_insert = None
    for ins in ents.get('inserts', []):
        if abs(ins['x'] - insert_x) < 20 and abs(ins['y'] - insert_y) < 20:
            titulo_insert = {
                'block': ins['block'],
                'x': ins['x'], 'y': ins['y'],
                'titulo': ins['attribs'].get('TITULO', ''),
                'secao': ins['attribs'].get('SEÇÃO', ins['attribs'].get('SECAO', '')),
                'reaproveitamento': ins['attribs'].get('REAPROVEITAMENTO', ins['attribs'].get('REAPROV', '')),
            }
            break

    return {
        'seccao_concreto': seccao_concreto,
        'sarrafos_35x7': sarr35_polys,
        'barrotes_madeira': madeira_polys,
        'titulo_insert': titulo_insert,
    }


def extract_sarrafos(sarr_lines, face_a, face_b):
    """Extract sarrafo positions and spacing per face.

    STOG sarrafos are VERTICAL lines in the DXF drawing.
    They represent the cross-section of horizontal wooden beams.
    Pattern: [inset 15cm] [before/after each divider] [inset 15cm from right]
    We extract their X positions within each face.
    """
    result = {'layers': [], 'face_a_xs': [], 'face_b_xs': [], 'spacing': [], 'count': 0}

    if not sarr_lines:
        return result

    result['layers'] = sorted(set(sl['layer'] for sl in sarr_lines))

    # Vertical sarrafos (is_h=False) have X positions
    v_sarrs = [sl for sl in sarr_lines if not sl['is_h']]
    # Also include very short horizontal ones (might be misclassified)
    if not v_sarrs:
        v_sarrs = sarr_lines  # fallback: use all

    result['count'] = len(v_sarrs)

    if face_a and face_a.get('y_min', 0) > 0:
        fa_sarrs = [sl for sl in v_sarrs
                    if (face_a['y_min'] - 10 <= sl['y1'] <= face_a['y_max'] + 10
                        or face_a['y_min'] - 10 <= sl['y2'] <= face_a['y_max'] + 10)]
        fa_xs = sorted(set(round((sl['x1'] + sl['x2']) / 2, 1) for sl in fa_sarrs))
        result['face_a_xs'] = fa_xs

    if face_b and face_b.get('y_min', 0) > 0:
        fb_sarrs = [sl for sl in v_sarrs
                    if (face_b['y_min'] - 10 <= sl['y1'] <= face_b['y_max'] + 10
                        or face_b['y_min'] - 10 <= sl['y2'] <= face_b['y_max'] + 10)]
        fb_xs = sorted(set(round((sl['x1'] + sl['x2']) / 2, 1) for sl in fb_sarrs))
        result['face_b_xs'] = fb_xs

    # Compute spacing from longest X list
    xs = result['face_a_xs'] if len(result['face_a_xs']) >= len(result['face_b_xs']) else result['face_b_xs']
    if len(xs) >= 2:
        spacings = [round(xs[i + 1] - xs[i], 1) for i in range(len(xs) - 1)]
        result['spacing'] = spacings

    return result


# ═══════════════════════════════════════════════════════════════════
# MODULE 2: SECAO TRANSVERSAL
# ═══════════════════════════════════════════════════════════════════

def extract_section(ents, zone, b_alma, h_total):
    """Extract section transversal detail.

    The section is typically positioned to the LEFT of the face panels,
    near the INSERT position. Contains:
    - Concrete rectangle (b_alma x h_total) with AR-CONC hatch
    - Escoras (diagonal lines below)
    - Tensors (red lines)
    - Presilhas (blocks)
    - Barrotes (horizontal lines)
    """
    result = {
        'b_alma': b_alma,
        'h_total': h_total,
        'concrete_hatch': None,
        'arconc_scale': 0,
        'escoras': {'count': 0, 'positions': []},
        'tensores': {'count': 0, 'positions': []},
        'presilhas': {'count': 0, 'positions': []},
        'barrotes': {'count': 0, 'positions': []},
        'section_dims': [],
    }

    # AR-CONC hatches = concrete section
    arconc = [h for h in ents['hatches'] if h['pattern'] == 'AR-CONC']
    if arconc:
        # The concrete section hatch is usually the one closest to insert
        insert_x = zone['insert_x']
        insert_y = zone['insert_y']
        arconc.sort(key=lambda h: abs(h['x_min'] - insert_x) + abs(h['y_max'] - insert_y))
        main_hatch = arconc[0]
        result['concrete_hatch'] = {
            'x_min': main_hatch['x_min'], 'x_max': main_hatch['x_max'],
            'y_min': main_hatch['y_min'], 'y_max': main_hatch['y_max'],
            'width': round(main_hatch['x_max'] - main_hatch['x_min'], 1),
            'height': round(main_hatch['y_max'] - main_hatch['y_min'], 1),
        }
        result['arconc_scale'] = main_hatch.get('scale', 0)

    # Section DIMENSION entities (vertical dims near section)
    sec_dims = [d for d in ents['dimensions']
                if not d['horizontal']
                and ('se' in d['layer'].lower() or 'cota' in d['layer'].lower())]
    result['section_dims'] = sorted(set(d['actual'] for d in sec_dims))

    # Escoras
    result['escoras']['count'] = len(ents['escora_entities'])
    result['escoras']['positions'] = [
        {'x': e['x1'], 'y': e['y1']} for e in ents['escora_entities'][:10]
    ] if ents['escora_entities'] else []

    # Tensores
    result['tensores']['count'] = len(ents['tensor_entities'])
    result['tensores']['positions'] = [
        {'x': e['x_mid'], 'y': e['y_mid']} for e in ents['tensor_entities'][:10]
    ]

    # Presilhas
    result['presilhas']['count'] = len(ents['presilha_entities'])
    result['presilhas']['positions'] = [
        {'x': e['x_mid'], 'y': e['y_mid']} for e in ents['presilha_entities'][:10]
    ]

    # Barrotes
    result['barrotes']['count'] = len(ents['barrote_entities'])
    barrote_ys = sorted(set(e['y_mid'] for e in ents['barrote_entities']))
    result['barrotes']['positions'] = [round(y, 1) for y in barrote_ys[:15]]

    return result


# ═══════════════════════════════════════════════════════════════════
# MAIN EXTRACTION
# ═══════════════════════════════════════════════════════════════════

def extract_viga_v3(doc, viga_name, zone):
    """Full v3 extraction: Painéis + Seção separated."""
    msp = doc.modelspace()
    insert_y = zone['insert_y']

    # Parse section — handles compound formats like (19x55/120)
    secao_str = zone.get('secao', '')
    b_alma = h_total = 0
    m = re.search(r'\((\d+)[xX](\d+)(?:/(\d+))?', secao_str)
    if m:
        b_alma = int(m.group(1))
        h2 = int(m.group(2))
        h3 = int(m.group(3)) if m.group(3) else 0
        h_total = max(h2, h3) if h3 > 0 else h2

    # Collect all zone entities
    ents = collect_zone_entities(msp, zone)

    # === MODULE 1: PAINÉIS ===
    face_a_data, face_b_data = detect_faces_by_clustering(
        ents['panel_h_lines'], ents['panel_v_lines'], insert_y,
        insert_x=zone['insert_x'],
        x_left=zone.get('x_left'),
        x_right=zone.get('x_right'),
        y_top=zone.get('y_top'),
    )

    face_a = extract_panels_from_face(
        face_a_data, ents['panel_v_lines'], ents['dimensions'],
        ents['hatches'], ents['texts'], insert_y,
        insert_x=zone['insert_x'], x_right=zone.get('x_right'), x_left=zone.get('x_left'),
    )
    face_b = extract_panels_from_face(
        face_b_data, ents['panel_v_lines'], ents['dimensions'],
        ents['hatches'], ents['texts'], insert_y,
        insert_x=zone['insert_x'], x_right=zone.get('x_right'), x_left=zone.get('x_left'),
    )

    sarrafos = extract_sarrafos(ents['sarr_lines'], face_a, face_b)

    # === MODULE 2: SECAO TRANSVERSAL ===
    section = extract_section(ents, zone, b_alma, h_total)

    # === MODULE 3: ABERTURAS DE PILAR/VIGA ===
    aberturas = extract_aberturas(ents, zone, face_a, face_b)

    # === MODULE 4: GEOMETRIA DA SEÇÃO (para reconstrução) ===
    section_geometry = extract_section_geometry(ents, zone, face_a)

    # === HATCHES SUMMARY ===
    all_hatches = ents['hatches']
    reaprov_hatches = [h for h in all_hatches if 'reaprov' in h['layer'].lower()]
    concrete_hatches = [h for h in all_hatches if h['pattern'] == 'AR-CONC']
    ansi31_hatches = [h for h in all_hatches if h['pattern'] == 'ANSI31']

    # === LAJE ===
    laje_position = 'none'
    if ents['laje_entities']:
        laje_ys = [le['y_mid'] for le in ents['laje_entities'] if le['y_mid'] != 0]
        if laje_ys:
            avg_y = sum(laje_ys) / len(laje_ys)
            if avg_y > insert_y - 50:
                laje_position = 'superior'
            elif face_b_data and avg_y < face_b_data['y_min']:
                laje_position = 'inferior'
            else:
                laje_position = 'central'

    # === PANEL TEXTS com posições ===
    panel_texts_pos = [
        {'text': t['text'], 'x': t['x'], 'y': t['y'], 'layer': t['layer']}
        for t in ents['texts']
        if re.match(r'^P?\d+$', t['text'])
        and t['layer'] in ('5', 'texto', 'NOMENCLATURA')
    ]

    # === CONTINUATION TEXTS ===
    continuacoes = [
        {'text': t['text'], 'x': t['x'], 'y': t['y']}
        for t in ents.get('continuation_texts', [])
    ]

    # === ALL COTA DIMS (for debugging) ===
    all_h_dims = sorted(set(d['actual'] for d in ents['dimensions'] if d['horizontal']))

    return {
        'viga': viga_name,
        'secao': secao_str,
        'b_alma': b_alma,
        'h_total': h_total,
        'insert': {'x': round(zone['insert_x'], 1), 'y': round(zone['insert_y'], 1)},
        'zone': {
            'y_top': round(zone['y_top'], 1), 'y_bot': round(zone['y_bot'], 1),
            'x_left': round(zone['x_left'], 1) if zone['x_left'] else None,
            'x_right': round(zone['x_right'], 1) if zone['x_right'] else None,
        },
        # MODULE 1: PAINEIS
        'face_a': face_a,
        'face_b': face_b,
        'sarrafos': sarrafos,
        # MODULE 2: SECAO
        'section': section,
        # MODULE 3: ABERTURAS DE PILAR/VIGA
        'aberturas': aberturas,
        # MODULE 4: GEOMETRIA SECAO TRANSVERSAL (reconstrução)
        'section_geometry': section_geometry,
        # HATCHES
        'hatches': {
            'total': len(all_hatches),
            'reaproveitamento': len(reaprov_hatches),
            'concrete_arconc': len(concrete_hatches),
            'ansi31': len(ansi31_hatches),
            'patterns': sorted(set(h['pattern'] for h in all_hatches)),
        },
        # HATCHES COMPLETOS (para reconstrução)
        'hatches_data': [
            {'pattern': h['pattern'], 'layer': h['layer'], 'scale': h['scale'],
             'boundary_polys': h.get('boundary_polys', [])}
            for h in all_hatches
        ],
        # COTAS COMPLETAS (para reconstrução — defpoint, defpoint2, defpoint3, text_midpoint)
        'cota_dims': ents['dimensions'],
        # SARR_2.2x7 e SARR_EDITAR (marcas de sarrafo nos painéis — excluir SARR_3.5x7)
        'sarr22_lines': [
            s for s in ents['sarr_lines']
            if '3.5' not in s['layer'] and '35' not in s['layer'].replace('.','')
        ],
        # LWPOLYLINEs RAW por layer (para reconstrução fiel — sem perda de geometria)
        'panel_polys':       ents.get('panel_polys', []),
        'all_concreto_polys': ents['concreto_polys'],
        'all_madeira_polys':  ents['madeira_polys'],
        'all_sarr35_polys':   ents['sarr35_polys'],
        'all_sarr22_polys':   ents.get('sarr22_polys', []),  # SARR_2.2x7/x10 intact rectangles
        # LAJE
        'laje': {
            'position': laje_position,
            'entity_count': len(ents['laje_entities']),
        },
        # META
        'panel_texts': [t['text'] for t in panel_texts_pos],  # backward compat
        'panel_texts_positioned': panel_texts_pos,  # com coordenadas
        'continuacoes': continuacoes,
        'all_cota_h_dims': all_h_dims,
        'entity_count': ents['entity_count'],
        'layers_used': dict(sorted(ents['layers_used'].items(), key=lambda x: -x[1])),
        'reaprov': zone.get('reaprov', ''),
    }


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Extrai parametros v3 (Paineis + Secao)')
    parser.add_argument('--catalog', default='D:/Agente-cad-PYSIDE/ANALISE_LV/catalog_rendered.json')
    parser.add_argument('--output', default='D:/Agente-cad-PYSIDE/ANALISE_LV/params')
    parser.add_argument('--obra', help='Specific obra')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--max', type=int, default=9999)
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.catalog, 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    targets = catalog[:args.max]
    if args.obra:
        targets = [e for e in catalog if e['obra'] == args.obra][:args.max]

    print(f'=== EXTRACAO v3 (Paineis + Secao) === {len(targets)} vigas')

    by_dxf = defaultdict(list)
    for t in targets:
        by_dxf[(t['obra'], t.get('dxf_source', ''))].append(t)

    all_params = []
    total_ok = total_fail = 0

    # Stats
    fa_ok = fb_ok = sec_ok = sarr_ok = 0

    for (obra, dxf_name), entries in sorted(by_dxf.items()):
        if args.obra and obra != args.obra:
            continue

        ref_dir = BASE_DIR / obra / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'
        dxf_path = ref_dir / dxf_name
        if not dxf_path.exists():
            found = False
            try:
                for f in os.listdir(str(ref_dir)):
                    if f.endswith('.dxf') and 'LV' in f:
                        key_parts = dxf_name.split(' - ')[:3]
                        if all(kp in f for kp in key_parts if len(kp) > 3):
                            dxf_path = ref_dir / f
                            found = True
                            break
            except Exception:
                pass
            if not found:
                print(f'\n  SKIP: {dxf_path}')
                total_fail += len(entries)
                continue

        try:
            doc = ezdxf.readfile(str(dxf_path))
        except Exception as ex:
            print(f'\n  LOAD ERROR: {dxf_path.name} -- {ex}')
            total_fail += len(entries)
            continue

        msp = doc.modelspace()
        all_vigas = find_all_inserts(msp)
        print(f'\n{obra} / {dxf_path.name[:55]}  ({len(all_vigas)} vigas)')

        for entry in entries:
            viga_name = entry['viga']
            zone = compute_zone(all_vigas, viga_name)
            if not zone:
                print(f'  {viga_name:25s} NO ZONE')
                total_fail += 1
                continue

            params = extract_viga_v3(doc, viga_name, zone)
            params['obra'] = obra
            params['dxf_source'] = dxf_name
            params['png'] = entry.get('png', '')
            all_params.append(params)

            fa = params['face_a']
            fb = params['face_b']
            sec = params['section']
            sarr = params['sarrafos']

            if fa['panel_widths']:
                fa_ok += 1
            if fb['panel_widths']:
                fb_ok += 1
            if sec['concrete_hatch'] or sec['section_dims']:
                sec_ok += 1
            if sarr['count'] > 0 or sarr['layers']:
                sarr_ok += 1

            pw_a = ','.join(str(int(w)) for w in fa['panel_widths'][:4])
            pw_b = ','.join(str(int(w)) for w in fb['panel_widths'][:4])
            esc = sec['escoras']['count']
            ten = sec['tensores']['count']
            pre = sec['presilhas']['count']
            print(f'  {viga_name:25s} FA[{fa["panel_count"]:2d}]={pw_a:20s} '
                  f'FB[{fb["panel_count"]:2d}]={pw_b:20s} '
                  f'E={esc} T={ten} P={pre}')
            total_ok += 1

    # Save — merge with existing params (don't overwrite other obras)
    params_path = output_dir / 'viga_params_v3.json'
    if params_path.exists() and args.obra:
        # When filtering by obra, preserve params from other obras
        existing = json.load(open(params_path, 'r', encoding='utf-8'))
        other_obras = [p for p in existing if p.get('obra') != args.obra]
        all_params = other_obras + all_params
        print(f'  Merged: {len(other_obras)} existing + {total_ok} new = {len(all_params)} total')
    with open(params_path, 'w', encoding='utf-8') as f:
        json.dump(all_params, f, indent=2, ensure_ascii=False)

    n = len(all_params)
    print(f'\n{"=" * 60}')
    print(f'RESULTADO: {total_ok} OK / {total_fail} FAIL')
    print(f'Salvo: {params_path}')
    if n > 0:
        print(f'\n=== COBERTURA v3 ===')
        print(f'  Face A panels: {fa_ok:3d}/{n} ({fa_ok/n*100:.0f}%)')
        print(f'  Face B panels: {fb_ok:3d}/{n} ({fb_ok/n*100:.0f}%)')
        print(f'  Secao detail:  {sec_ok:3d}/{n} ({sec_ok/n*100:.0f}%)')
        print(f'  Sarrafos:      {sarr_ok:3d}/{n} ({sarr_ok/n*100:.0f}%)')


if __name__ == '__main__':
    main()
