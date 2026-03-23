#!/usr/bin/env python3
"""
validar_lv_stog.py - Automated LV DXF Validation: Generated vs STOG Reference

Compares the GENERATED LV DXF against the STOG REFERENCE DXF for viga V22
(first viga in both files). Runs 8 automated tests covering entity counts,
panel geometry, cross-section elements, SARR patterns, hatches, text,
dimensions, and missing element detection.

Usage:
    python validar_lv_stog.py [--stog PATH] [--gen PATH]
"""

import os
import sys
import glob
import argparse
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any

try:
    import ezdxf
except ImportError:
    print("ERROR: ezdxf not installed. Run: pip install ezdxf")
    sys.exit(1)


# ============================================================================
# CONFIGURATION
# ============================================================================

STOG_DEFAULT = (
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_21"
    r"\Fase-1_Ingestao\Projetos_Finalizados_para_Engenharia_Reversa"
    r"\STOG - NIK SUNSET - LAJE TÉCNICA - LV - R00_R2018_ASCII_ODA.dxf"
)

GEN_DIR = (
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_21\Fase-6_Execucao_CAD"
)

# STOG V22 bounding box (panels area spans wider than cross-section)
STOG_V22_BBOX = {"xmin": -7600, "xmax": -6200, "ymin": 9200, "ymax": 9600}
# STOG V22 cross-section bounding box (narrower, around the section detail)
STOG_V22_SECTION_BBOX = {"xmin": -7200, "xmax": -6900, "ymin": 9250, "ymax": 9450}

# Generated first viga bounding box (V22 when sorted by b desc)
GEN_V2_BBOX = {"xmin": -50, "xmax": 800, "ymin": -150, "ymax": 50}
# Generated first viga cross-section bounding box
GEN_V2_SECTION_BBOX = {"xmin": -20, "xmax": 250, "ymin": -100, "ymax": 50}

# Test result tracking
PASS_COUNT = 0
FAIL_COUNT = 0
MISSING_ELEMENTS = []
EXTRA_ELEMENTS = []
RECOMMENDATIONS = []


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_entity_position(entity) -> Optional[Tuple[float, float]]:
    """Extract approximate center position from any DXF entity."""
    etype = entity.dxftype()

    if etype == "LINE":
        return (
            (entity.dxf.start.x + entity.dxf.end.x) / 2,
            (entity.dxf.start.y + entity.dxf.end.y) / 2,
        )
    elif etype == "LWPOLYLINE":
        pts = list(entity.get_points())
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    elif etype in ("TEXT", "MTEXT"):
        if hasattr(entity.dxf, "insert"):
            return (entity.dxf.insert.x, entity.dxf.insert.y)
    elif etype == "INSERT":
        return (entity.dxf.insert.x, entity.dxf.insert.y)
    elif etype == "DIMENSION":
        if hasattr(entity.dxf, "defpoint"):
            return (entity.dxf.defpoint.x, entity.dxf.defpoint.y)
    elif etype == "HATCH":
        try:
            all_x, all_y = [], []
            for path in entity.paths:
                if hasattr(path, "vertices"):
                    for v in path.vertices:
                        all_x.append(v[0])
                        all_y.append(v[1])
                elif hasattr(path, "edges"):
                    for edge in path.edges:
                        if hasattr(edge, "start"):
                            all_x.append(edge.start[0])
                            all_y.append(edge.start[1])
                        if hasattr(edge, "end"):
                            all_x.append(edge.end[0])
                            all_y.append(edge.end[1])
            if all_x:
                return ((min(all_x) + max(all_x)) / 2, (min(all_y) + max(all_y)) / 2)
        except Exception:
            pass
    return None


def get_entity_bbox(entity) -> Optional[Tuple[float, float, float, float]]:
    """Get bounding box (xmin, ymin, xmax, ymax) for entity."""
    etype = entity.dxftype()

    if etype == "LINE":
        x1, y1 = entity.dxf.start.x, entity.dxf.start.y
        x2, y2 = entity.dxf.end.x, entity.dxf.end.y
        return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    elif etype == "LWPOLYLINE":
        pts = list(entity.get_points())
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))
    elif etype in ("TEXT", "MTEXT"):
        if hasattr(entity.dxf, "insert"):
            x, y = entity.dxf.insert.x, entity.dxf.insert.y
            return (x, y, x, y)
    elif etype == "INSERT":
        x, y = entity.dxf.insert.x, entity.dxf.insert.y
        return (x, y, x, y)
    elif etype == "DIMENSION":
        if hasattr(entity.dxf, "defpoint"):
            x, y = entity.dxf.defpoint.x, entity.dxf.defpoint.y
            return (x, y, x, y)
    elif etype == "HATCH":
        try:
            all_x, all_y = [], []
            for path in entity.paths:
                if hasattr(path, "vertices"):
                    for v in path.vertices:
                        all_x.append(v[0])
                        all_y.append(v[1])
                elif hasattr(path, "edges"):
                    for edge in path.edges:
                        if hasattr(edge, "start"):
                            all_x.append(edge.start[0])
                            all_y.append(edge.start[1])
                        if hasattr(edge, "end"):
                            all_x.append(edge.end[0])
                            all_y.append(edge.end[1])
            if all_x:
                return (min(all_x), min(all_y), max(all_x), max(all_y))
        except Exception:
            pass
    return None


def entity_in_bbox(entity, bbox: dict) -> bool:
    """Check if entity center falls within bounding box."""
    pos = get_entity_position(entity)
    if pos is None:
        return False
    x, y = pos
    return bbox["xmin"] <= x <= bbox["xmax"] and bbox["ymin"] <= y <= bbox["ymax"]


def get_entities_in_bbox(msp, bbox: dict) -> list:
    """Get all entities whose center is within bbox."""
    result = []
    for e in msp:
        if entity_in_bbox(e, bbox):
            result.append(e)
    return result


def normalize_layer(name: str) -> str:
    """Normalize layer name for comparison (handle encoding)."""
    # Common encoding artifacts
    name = name.replace("\x00", "")
    return name.strip()


def fmt_table(headers: list, rows: list, col_widths: Optional[list] = None) -> str:
    """Format data as aligned table."""
    if not col_widths:
        col_widths = []
        for i, h in enumerate(headers):
            w = len(str(h))
            for row in rows:
                if i < len(row):
                    w = max(w, len(str(row[i])))
            col_widths.append(min(w + 2, 45))

    lines = []
    # Header
    header_line = "| " + " | ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    sep_line = "+-" + "-+-".join("-" * col_widths[i] for i in range(len(headers))) + "-+"
    lines.append(sep_line)
    lines.append(header_line)
    lines.append(sep_line)
    for row in rows:
        cells = []
        for i in range(len(headers)):
            val = str(row[i]) if i < len(row) else ""
            cells.append(val.ljust(col_widths[i]))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append(sep_line)
    return "\n".join(lines)


def print_header(test_num: int, title: str):
    """Print test header."""
    print(f"\n{'='*80}")
    print(f"  TEST {test_num}: {title}")
    print(f"{'='*80}")


def record_result(passed: bool, detail: str = ""):
    """Record test result."""
    global PASS_COUNT, FAIL_COUNT
    if passed:
        PASS_COUNT += 1
        print(f"\n  RESULT: PASS {detail}")
    else:
        FAIL_COUNT += 1
        print(f"\n  RESULT: FAIL {detail}")


# ============================================================================
# TEST IMPLEMENTATIONS
# ============================================================================

def test1_entity_count(stog_entities: list, gen_entities: list):
    """TEST 1: Entity Count Comparison per layer."""
    print_header(1, "Entity Count Comparison (per layer)")

    stog_counts = defaultdict(lambda: defaultdict(int))
    for e in stog_entities:
        layer = normalize_layer(e.dxf.layer)
        etype = e.dxftype()
        stog_counts[layer][etype] += 1

    gen_counts = defaultdict(lambda: defaultdict(int))
    for e in gen_entities:
        layer = normalize_layer(e.dxf.layer)
        etype = e.dxftype()
        gen_counts[layer][etype] += 1

    all_layers = sorted(set(list(stog_counts.keys()) + list(gen_counts.keys())))

    rows = []
    total_stog = 0
    total_gen = 0
    has_mismatch = False
    for layer in all_layers:
        stog_etypes = stog_counts.get(layer, {})
        gen_etypes = gen_counts.get(layer, {})
        all_types = sorted(set(list(stog_etypes.keys()) + list(gen_etypes.keys())))
        for etype in all_types:
            sc = stog_etypes.get(etype, 0)
            gc = gen_etypes.get(etype, 0)
            delta = gc - sc
            total_stog += sc
            total_gen += gc
            flag = "" if delta == 0 else ("EXTRA" if delta > 0 else "MISSING")
            if delta != 0:
                has_mismatch = True
            rows.append([layer, etype, sc, gc, f"{delta:+d}", flag])

    rows.append(["--- TOTAL ---", "", total_stog, total_gen, f"{total_gen-total_stog:+d}", ""])

    print(fmt_table(["Layer", "Type", "STOG", "Generated", "DELTA", "Status"], rows))
    record_result(not has_mismatch, f"(STOG={total_stog}, Gen={total_gen}, delta={total_gen-total_stog:+d})")
    return stog_counts, gen_counts


def test2_panel_geometry(stog_entities: list, gen_entities: list):
    """TEST 2: Panel Geometry Validation."""
    print_header(2, "Panel Geometry Validation")

    def find_panel_rects(entities, label: str) -> dict:
        """Find panel rectangles from Paineis layer entities."""
        panels = []
        for e in entities:
            layer = normalize_layer(e.dxf.layer)
            # Match Paineis layer (handles encoding)
            if "pain" not in layer.lower() and "Pain" not in layer:
                continue
            bbox = get_entity_bbox(e)
            if bbox is None:
                continue
            xmin, ymin, xmax, ymax = bbox
            w = abs(xmax - xmin)
            h = abs(ymax - ymin)
            # Only consider rectangles with area (not lines)
            if w > 5 and h > 5:
                panels.append({"bbox": bbox, "w": round(w, 1), "h": round(h, 1)})
        return panels

    stog_panels = find_panel_rects(stog_entities, "STOG")
    gen_panels = find_panel_rects(gen_entities, "GEN")

    # Collect all Paineis LINE entities to find panel outlines
    def find_panel_outlines_from_lines(entities) -> list:
        """Find panel outlines by grouping Paineis LINE entities."""
        h_lines = []
        v_lines = []
        for e in entities:
            layer = normalize_layer(e.dxf.layer)
            if "pain" not in layer.lower() and "Pain" not in layer:
                continue
            if e.dxftype() != "LINE":
                continue
            x1, y1 = e.dxf.start.x, e.dxf.start.y
            x2, y2 = e.dxf.end.x, e.dxf.end.y
            if abs(y2 - y1) < 1:  # horizontal
                h_lines.append((min(x1, x2), y1, max(x1, x2), y2))
            elif abs(x2 - x1) < 1:  # vertical
                v_lines.append((x1, min(y1, y2), x2, max(y1, y2)))

        # Find unique y-values for horizontal lines (panel top/bottom)
        h_ys = sorted(set(round(l[1], 0) for l in h_lines))
        # Find unique x-values for vertical lines (panel left/right edges)
        v_xs = sorted(set(round(l[0], 0) for l in v_lines))

        panels = []
        if len(h_ys) >= 2 and len(v_xs) >= 2:
            ymin, ymax = h_ys[0], h_ys[-1]
            h = abs(ymax - ymin)
            # Each consecutive pair of v_xs is a panel
            for i in range(len(v_xs) - 1):
                w = abs(v_xs[i + 1] - v_xs[i])
                if w > 5:
                    panels.append({"xmin": v_xs[i], "xmax": v_xs[i + 1], "w": round(w, 1), "h": round(h, 1)})
        return panels

    stog_line_panels = find_panel_outlines_from_lines(stog_entities)
    gen_line_panels = find_panel_outlines_from_lines(gen_entities)

    # STOG has V22.A and V22.B face panels (from LINE entities)
    # Group by face: V22.A is the left half, V22.B is the right half
    def split_faces(panels: list) -> Tuple[list, list]:
        if not panels:
            return [], []
        mid_x = (min(p["xmin"] for p in panels) + max(p["xmax"] for p in panels)) / 2
        face_a = [p for p in panels if p["xmax"] <= mid_x + 10]
        face_b = [p for p in panels if p["xmin"] >= mid_x - 10]
        return face_a, face_b

    stog_face_a, stog_face_b = split_faces(stog_line_panels)
    gen_face_a, gen_face_b = split_faces(gen_line_panels)

    rows = []

    def face_summary(panels: list) -> str:
        if not panels:
            return "NO PANELS"
        total_w = sum(p["w"] for p in panels)
        h = panels[0]["h"] if panels else 0
        return f"{total_w:.0f}x{h:.0f} ({len(panels)} panels)"

    stog_a_str = face_summary(stog_face_a)
    gen_a_str = face_summary(gen_face_a)
    stog_b_str = face_summary(stog_face_b)
    gen_b_str = face_summary(gen_face_b)

    match_a = len(stog_face_a) > 0 and len(gen_face_a) > 0 and len(stog_face_a) == len(gen_face_a)
    match_b = len(stog_face_b) > 0 and len(gen_face_b) > 0 and len(stog_face_b) == len(gen_face_b)

    rows.append(["Face A", stog_a_str, gen_a_str, "YES" if match_a else "NO (check count)"])
    rows.append(["Face B", stog_b_str, gen_b_str, "YES" if match_b else "NO (check count)"])

    # Also show individual panel widths
    print(fmt_table(["Face", "STOG", "Generated", "Panel Count Match?"], rows))

    print("\n  Panel detail (individual widths):")
    print("  STOG Face A panels:", [f"{p['w']:.0f}x{p['h']:.0f}" for p in stog_face_a])
    print("  GEN  Face A panels:", [f"{p['w']:.0f}x{p['h']:.0f}" for p in gen_face_a])
    print("  STOG Face B panels:", [f"{p['w']:.0f}x{p['h']:.0f}" for p in stog_face_b])
    print("  GEN  Face B panels:", [f"{p['w']:.0f}x{p['h']:.0f}" for p in gen_face_b])

    # Cross-section LWPOLYLINE panels
    print("\n  Cross-section panels (LWPOLYLINE on Paineis):")
    stog_cs = [e for e in stog_entities
               if normalize_layer(e.dxf.layer).lower().startswith("pain")
               and e.dxftype() == "LWPOLYLINE"]
    gen_cs = [e for e in gen_entities
              if normalize_layer(e.dxf.layer).lower().startswith("pain")
              and e.dxftype() == "LWPOLYLINE"]
    print(f"  STOG: {len(stog_cs)} LWPOLYLINE | GEN: {len(gen_cs)} LWPOLYLINE")

    passed = match_a and match_b
    if not passed:
        RECOMMENDATIONS.append("Panel count mismatch between faces - check panel splitting logic")
    record_result(passed)


def test3_cross_section_audit(stog_entities: list, gen_entities: list,
                               stog_section_entities: list, gen_section_entities: list):
    """TEST 3: Cross-Section Element Audit."""
    print_header(3, "Cross-Section Element Audit")

    def check_element(entities: list, name: str, layer_match: str,
                       etype_match: Optional[str] = None) -> Tuple[bool, int]:
        """Check if element exists and count occurrences."""
        count = 0
        for e in entities:
            layer = normalize_layer(e.dxf.layer).lower()
            if layer_match.lower() not in layer:
                continue
            if etype_match and e.dxftype() != etype_match:
                continue
            count += 1
        return (count > 0, count)

    # Use broader V22 area for panel-level elements, section bbox for cross-section
    elements = [
        # (name, layer_match, etype_filter, use_section_bbox)
        ("barrote", "barrote", "LWPOLYLINE", True),
        ("SCO-LAJ strip", "sco", "LWPOLYLINE", True),
        ("Madeira boards", "madeira", "LWPOLYLINE", True),
        ("Paineis strips (LWPOLY)", "pain", "LWPOLYLINE", True),
        ("CONCRETO L-shape", "concreto", "LWPOLYLINE", True),
        ("TENSOR line", "tensor", "LINE", True),
        ("Holders (LINE on 0)", "0", "LINE", True),
        ("Holders (LWPOLY on 0)", "0", "LWPOLYLINE", True),
        ("Presilha (INSERT)", "presilha", "INSERT", False),
        ("Presilha (LINE)", "presilha", "LINE", False),
        ("Hachura (HATCH)", "hachura", None, False),
        ("Hachura (HATCH on COTA)", "cota", "HATCH", False),
        ("Dimensions (DIMENSION)", "cota", "DIMENSION", False),
        ("Text labels (detalhes)", "detalhes", "TEXT", False),
        ("Text (texto/MTEXT)", "texto", "MTEXT", False),
    ]

    rows = []
    has_missing = False
    for name, layer_match, etype_filter, use_section in elements:
        if use_section:
            s_ents = stog_section_entities
            g_ents = gen_section_entities
        else:
            s_ents = stog_entities
            g_ents = gen_entities

        s_present, s_count = check_element(s_ents, name, layer_match, etype_filter)
        g_present, g_count = check_element(g_ents, name, layer_match, etype_filter)

        status = ""
        if s_present and not g_present:
            status = "MISSING IN GEN"
            has_missing = True
            MISSING_ELEMENTS.append(name)
            RECOMMENDATIONS.append(f"Add {name} to generated DXF (layer={layer_match})")
        elif not s_present and g_present:
            status = "EXTRA IN GEN"
            EXTRA_ELEMENTS.append(name)
        elif s_count != g_count:
            status = f"COUNT DIFF"

        rows.append([
            name,
            "YES" if s_present else "NO",
            "YES" if g_present else "NO",
            s_count,
            g_count,
            status,
        ])

    print(fmt_table(
        ["Element", "STOG?", "Gen?", "STOG #", "Gen #", "Status"],
        rows,
    ))

    record_result(not has_missing, f"({len(MISSING_ELEMENTS)} missing elements)")


def test4_sarr_pattern(stog_entities: list, gen_entities: list):
    """TEST 4: SARR Pattern Validation."""
    print_header(4, "SARR Pattern Validation")

    sarr_layers = ["SARR_3.5x7", "SARR_2.2x7"]

    rows = []
    all_match = True
    for layer in sarr_layers:
        stog_count = sum(1 for e in stog_entities
                         if normalize_layer(e.dxf.layer) == layer and e.dxftype() == "LINE")
        gen_count = sum(1 for e in gen_entities
                        if normalize_layer(e.dxf.layer) == layer and e.dxftype() == "LINE")
        delta = gen_count - stog_count
        # For SARR, generated typically has more (Face A + Face B complete)
        # STOG V22 might show partial. Check ratio
        ratio = gen_count / stog_count if stog_count > 0 else 0
        status = "OK" if stog_count > 0 and gen_count > 0 else "MISSING"
        if stog_count == 0 and gen_count == 0:
            status = "BOTH EMPTY"
        if stog_count > 0 and gen_count == 0:
            all_match = False

        rows.append([layer, stog_count, gen_count, f"{delta:+d}", f"{ratio:.1f}x", status])

    print(fmt_table(["Layer", "STOG lines", "Gen lines", "DELTA", "Ratio", "Status"], rows))

    # Also check for Sarr 2.2x7 (different layer name in STOG)
    stog_alt = sum(1 for e in stog_entities
                   if normalize_layer(e.dxf.layer) == "Sarr 2.2x7" and e.dxftype() == "LINE")
    if stog_alt > 0:
        print(f"\n  NOTE: STOG also has {stog_alt} lines on 'Sarr 2.2x7' layer (alternate naming)")

    record_result(all_match)


def test5_hatch_analysis(stog_entities: list, gen_entities: list):
    """TEST 5: HATCH Analysis."""
    print_header(5, "HATCH Analysis")

    def collect_hatches(entities: list) -> list:
        hatches = []
        for e in entities:
            if e.dxftype() != "HATCH":
                continue
            layer = normalize_layer(e.dxf.layer)
            pattern = e.dxf.pattern_name if hasattr(e.dxf, "pattern_name") else "UNKNOWN"
            bbox = get_entity_bbox(e)
            bbox_str = "N/A"
            if bbox:
                bbox_str = f"({bbox[0]:.0f},{bbox[1]:.0f})-({bbox[2]:.0f},{bbox[3]:.0f})"

            # Check if paths are closed
            closed = "N/A"
            try:
                paths = e.paths
                if paths:
                    if hasattr(paths[0], "is_closed"):
                        closed = "YES" if paths[0].is_closed else "NO"
                    elif hasattr(paths[0], "vertices"):
                        verts = list(paths[0].vertices)
                        if len(verts) >= 3:
                            # Check if first ~= last
                            d = ((verts[0][0]-verts[-1][0])**2 + (verts[0][1]-verts[-1][1])**2)**0.5
                            closed = "YES" if d < 1 else "NO"
            except Exception:
                pass

            hatches.append({
                "layer": layer, "pattern": pattern, "bbox": bbox_str, "closed": closed,
            })
        return hatches

    stog_hatches = collect_hatches(stog_entities)
    gen_hatches = collect_hatches(gen_entities)

    print("  STOG V22 Hatches:")
    if stog_hatches:
        rows = [[h["layer"], h["pattern"], h["bbox"], h["closed"]] for h in stog_hatches]
        print(fmt_table(["Layer", "Pattern", "BBox", "Closed?"], rows))
    else:
        print("    (none)")

    print("\n  Generated V2 Hatches:")
    if gen_hatches:
        rows = [[h["layer"], h["pattern"], h["bbox"], h["closed"]] for h in gen_hatches]
        print(fmt_table(["Layer", "Pattern", "BBox", "Closed?"], rows))
    else:
        print("    (none)")

    stog_count = len(stog_hatches)
    gen_count = len(gen_hatches)
    print(f"\n  STOG hatches: {stog_count} | Generated hatches: {gen_count}")

    if stog_count > 0 and gen_count == 0:
        MISSING_ELEMENTS.append(f"HATCH entities ({stog_count} in STOG)")
        RECOMMENDATIONS.append(f"Add {stog_count} HATCH entities (patterns: {set(h['pattern'] for h in stog_hatches)})")

    # Hatches by pattern summary
    stog_patterns = defaultdict(int)
    for h in stog_hatches:
        stog_patterns[h["pattern"]] += 1
    gen_patterns = defaultdict(int)
    for h in gen_hatches:
        gen_patterns[h["pattern"]] += 1

    all_patterns = sorted(set(list(stog_patterns.keys()) + list(gen_patterns.keys())))
    if all_patterns:
        print("\n  Pattern summary:")
        prows = [[p, stog_patterns.get(p, 0), gen_patterns.get(p, 0)] for p in all_patterns]
        print(fmt_table(["Pattern", "STOG #", "Gen #"], prows))

    passed = gen_count > 0 or stog_count == 0
    record_result(passed, f"(STOG={stog_count}, Gen={gen_count})")


def test6_text_content(stog_entities: list, gen_entities: list):
    """TEST 6: MTEXT/TEXT Content."""
    print_header(6, "MTEXT/TEXT Content Comparison")

    def collect_texts(entities: list) -> list:
        texts = []
        for e in entities:
            if e.dxftype() not in ("TEXT", "MTEXT"):
                continue
            layer = normalize_layer(e.dxf.layer)
            if e.dxftype() == "TEXT":
                content = e.dxf.text if hasattr(e.dxf, "text") else ""
                height = e.dxf.height if hasattr(e.dxf, "height") else 0
            else:
                content = e.text if hasattr(e, "text") else (e.dxf.text if hasattr(e.dxf, "text") else "")
                height = e.dxf.char_height if hasattr(e.dxf, "char_height") else 0
            pos = get_entity_position(e)
            pos_str = f"({pos[0]:.0f},{pos[1]:.0f})" if pos else "N/A"
            # Clean up MTEXT formatting codes
            content_clean = content.replace("\\P", " ").replace("{", "").replace("}", "")
            if "\\Q" in content_clean:
                # Extract visible text after formatting codes
                parts = content_clean.split(";")
                content_clean = parts[-1] if parts else content_clean
            texts.append({
                "content": content_clean[:40],
                "layer": layer,
                "pos": pos_str,
                "height": f"{height:.1f}" if height else "?",
                "type": e.dxftype(),
            })
        return texts

    stog_texts = collect_texts(stog_entities)
    gen_texts = collect_texts(gen_entities)

    print("  STOG V22 Texts:")
    if stog_texts:
        rows = [[t["content"], t["layer"], t["type"], t["pos"], t["height"]] for t in stog_texts]
        print(fmt_table(["Content", "Layer", "Type", "Position", "Height"], rows))
    else:
        print("    (none)")

    print("\n  Generated V2 Texts:")
    if gen_texts:
        rows = [[t["content"], t["layer"], t["type"], t["pos"], t["height"]] for t in gen_texts]
        print(fmt_table(["Content", "Layer", "Type", "Position", "Height"], rows))
    else:
        print("    (none)")

    # Compare content presence
    stog_contents = set(t["content"].strip() for t in stog_texts)
    gen_contents = set(t["content"].strip() for t in gen_texts)
    missing_text = stog_contents - gen_contents
    extra_text = gen_contents - stog_contents

    if missing_text:
        print(f"\n  Text in STOG but NOT in Generated: {sorted(missing_text)}")
        for t in missing_text:
            if t:
                MISSING_ELEMENTS.append(f"Text: '{t}'")
    if extra_text:
        print(f"\n  Text in Generated but NOT in STOG: {sorted(extra_text)}")

    # Check for specific label types
    stog_layers_with_text = set(t["layer"] for t in stog_texts)
    gen_layers_with_text = set(t["layer"] for t in gen_texts)
    missing_text_layers = stog_layers_with_text - gen_layers_with_text
    if missing_text_layers:
        print(f"\n  Text layers in STOG but not in Generated: {sorted(missing_text_layers)}")
        for ml in missing_text_layers:
            RECOMMENDATIONS.append(f"Add text on layer '{ml}' (found in STOG)")

    passed = len(missing_text) <= 2  # Allow some difference
    record_result(passed, f"(missing={len(missing_text)}, extra={len(extra_text)})")


def test7_dimension_analysis(stog_entities: list, gen_entities: list):
    """TEST 7: Dimension (COTA) Analysis."""
    print_header(7, "Dimension (COTA) Analysis")

    def collect_dims(entities: list) -> list:
        dims = []
        for e in entities:
            if e.dxftype() != "DIMENSION":
                continue
            layer = normalize_layer(e.dxf.layer)
            measurement = None
            try:
                measurement = e.dxf.actual_measurement
            except Exception:
                pass
            if measurement is None:
                try:
                    measurement = e.dxf.get("actual_measurement", None)
                except Exception:
                    pass

            # Dimension type
            dim_type = "UNKNOWN"
            try:
                dtype = e.dxf.dimtype if hasattr(e.dxf, "dimtype") else -1
                if dtype == 0 or dtype == 1:
                    dim_type = "LINEAR"
                elif dtype == 2:
                    dim_type = "ANGULAR"
                elif dtype == 3:
                    dim_type = "DIAMETER"
                elif dtype == 4:
                    dim_type = "RADIUS"
            except Exception:
                pass

            # Try to get dimstyle
            style = ""
            try:
                style = e.dxf.dimstyle if hasattr(e.dxf, "dimstyle") else ""
            except Exception:
                pass

            pos = get_entity_position(e)
            pos_str = f"({pos[0]:.0f},{pos[1]:.0f})" if pos else "N/A"

            dims.append({
                "measurement": f"{measurement:.1f}" if measurement is not None else "N/A",
                "type": dim_type,
                "layer": layer,
                "style": style[:20] if style else "",
                "pos": pos_str,
            })
        return dims

    stog_dims = collect_dims(stog_entities)
    gen_dims = collect_dims(gen_entities)

    print("  STOG V22 Dimensions:")
    if stog_dims:
        rows = [[d["measurement"], d["type"], d["layer"], d["style"], d["pos"]] for d in stog_dims]
        print(fmt_table(["Measurement", "Type", "Layer", "Style", "Position"], rows))
    else:
        print("    (none)")

    print(f"\n  Generated V2 Dimensions:")
    if gen_dims:
        # Show first 15 and summary
        display = gen_dims[:15]
        rows = [[d["measurement"], d["type"], d["layer"], d["style"], d["pos"]] for d in display]
        print(fmt_table(["Measurement", "Type", "Layer", "Style", "Position"], rows))
        if len(gen_dims) > 15:
            print(f"    ... and {len(gen_dims)-15} more dimensions")
    else:
        print("    (none)")

    print(f"\n  STOG dimensions: {len(stog_dims)} | Generated dimensions: {len(gen_dims)}")

    # Compare measurement values
    stog_meas = sorted([d["measurement"] for d in stog_dims if d["measurement"] != "N/A"])
    gen_meas = sorted([d["measurement"] for d in gen_dims if d["measurement"] != "N/A"])
    print(f"  STOG measurements: {stog_meas}")
    print(f"  GEN  measurements (first 15): {gen_meas[:15]}")

    passed = len(gen_dims) > 0 or len(stog_dims) == 0
    if len(stog_dims) > 0 and len(gen_dims) == 0:
        MISSING_ELEMENTS.append(f"DIMENSION entities ({len(stog_dims)} in STOG)")
        RECOMMENDATIONS.append("Add DIMENSION entities to generated DXF")

    record_result(passed, f"(STOG={len(stog_dims)}, Gen={len(gen_dims)})")


def test8_missing_elements(stog_entities: list, gen_entities: list):
    """TEST 8: Missing Elements Detection (aggregate)."""
    print_header(8, "Missing Elements Detection (Aggregate)")

    # Layer-level analysis
    stog_layers = defaultdict(int)
    gen_layers = defaultdict(int)
    for e in stog_entities:
        stog_layers[normalize_layer(e.dxf.layer)] += 1
    for e in gen_entities:
        gen_layers[normalize_layer(e.dxf.layer)] += 1

    missing_layers = []
    extra_layers = []
    delta_layers = []

    all_layers = sorted(set(list(stog_layers.keys()) + list(gen_layers.keys())))
    for layer in all_layers:
        sc = stog_layers.get(layer, 0)
        gc = gen_layers.get(layer, 0)
        if sc > 0 and gc == 0:
            missing_layers.append((layer, sc))
        elif sc == 0 and gc > 0:
            extra_layers.append((layer, gc))
        elif sc != gc:
            delta_layers.append((layer, sc, gc))

    print("  MISSING LAYERS (in STOG but NOT in Generated):")
    if missing_layers:
        for layer, count in missing_layers:
            print(f"    - {layer}: {count} entities")
            if layer not in [m for m in MISSING_ELEMENTS if layer in m]:
                MISSING_ELEMENTS.append(f"Layer '{layer}' ({count} entities)")
    else:
        print("    (none)")

    print("\n  EXTRA LAYERS (in Generated but NOT in STOG):")
    if extra_layers:
        for layer, count in extra_layers:
            print(f"    + {layer}: {count} entities")
            if layer not in [m for m in EXTRA_ELEMENTS if layer in m]:
                EXTRA_ELEMENTS.append(f"Layer '{layer}' ({count} entities)")
    else:
        print("    (none)")

    print("\n  LAYERS WITH COUNT DIFFERENCES:")
    if delta_layers:
        rows = [[layer, sc, gc, f"{gc-sc:+d}"] for layer, sc, gc in delta_layers]
        print(fmt_table(["Layer", "STOG", "Gen", "DELTA"], rows))
    else:
        print("    (none - all counts match)")

    # Entity type analysis
    stog_types = defaultdict(int)
    gen_types = defaultdict(int)
    for e in stog_entities:
        stog_types[e.dxftype()] += 1
    for e in gen_entities:
        gen_types[e.dxftype()] += 1

    print("\n  Entity Type Summary:")
    all_types = sorted(set(list(stog_types.keys()) + list(gen_types.keys())))
    rows = []
    for t in all_types:
        sc = stog_types.get(t, 0)
        gc = gen_types.get(t, 0)
        flag = ""
        if sc > 0 and gc == 0:
            flag = "MISSING"
        elif sc == 0 and gc > 0:
            flag = "EXTRA"
        rows.append([t, sc, gc, f"{gc-sc:+d}", flag])
    print(fmt_table(["Entity Type", "STOG", "Gen", "DELTA", "Status"], rows))

    # Specific high-priority missing elements
    priority_missing = []
    if stog_types.get("HATCH", 0) > 0 and gen_types.get("HATCH", 0) == 0:
        priority_missing.append("HATCH (cross-hatching for materials visualization)")
    if stog_types.get("INSERT", 0) > 0 and gen_types.get("INSERT", 0) == 0:
        priority_missing.append("INSERT (block references, e.g. presilha)")
    # Check for detalhes layer text
    stog_detalhes = sum(1 for e in stog_entities if normalize_layer(e.dxf.layer) == "detalhes")
    gen_detalhes = sum(1 for e in gen_entities if normalize_layer(e.dxf.layer) == "detalhes")
    if stog_detalhes > 0 and gen_detalhes == 0:
        priority_missing.append("detalhes layer (labels a, b, c for cross-section)")

    if priority_missing:
        print("\n  HIGH-PRIORITY MISSING:")
        for p in priority_missing:
            print(f"    [!] {p}")
            if p not in RECOMMENDATIONS:
                RECOMMENDATIONS.append(f"Implement {p}")

    passed = len(missing_layers) == 0
    record_result(passed, f"(missing_layers={len(missing_layers)}, extra_layers={len(extra_layers)})")


# ============================================================================
# MAIN
# ============================================================================

def find_latest_gen_dxf(gen_dir: str) -> Optional[str]:
    """Find the most recent LV_stog_*.dxf in generation directory."""
    pattern = os.path.join(gen_dir, "LV_stog_*.dxf")
    candidates = glob.glob(pattern)
    if not candidates:
        return None
    # Sort by modification time, newest first
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description="Validate Generated LV DXF against STOG Reference")
    parser.add_argument("--stog", default=STOG_DEFAULT, help="Path to STOG reference DXF")
    parser.add_argument("--gen", default=None, help="Path to generated DXF (auto-detects latest)")
    args = parser.parse_args()

    stog_path = args.stog
    gen_path = args.gen

    if gen_path is None:
        gen_path = find_latest_gen_dxf(GEN_DIR)
        if gen_path is None:
            print(f"ERROR: No LV_stog_*.dxf found in {GEN_DIR}")
            sys.exit(1)

    print("=" * 80)
    print("  LV DXF VALIDATION: Generated vs STOG Reference")
    print("=" * 80)
    print(f"  STOG Reference : {os.path.basename(stog_path)}")
    print(f"  Generated      : {os.path.basename(gen_path)}")
    print(f"  STOG V22 bbox  : x[{STOG_V22_BBOX['xmin']}..{STOG_V22_BBOX['xmax']}] y[{STOG_V22_BBOX['ymin']}..{STOG_V22_BBOX['ymax']}]")
    print(f"  Gen V2 bbox    : x[{GEN_V2_BBOX['xmin']}..{GEN_V2_BBOX['xmax']}] y[{GEN_V2_BBOX['ymin']}..{GEN_V2_BBOX['ymax']}]")

    # Load DXFs
    print("\n  Loading DXF files...")
    try:
        stog_doc = ezdxf.readfile(stog_path)
    except Exception as e:
        print(f"ERROR: Cannot read STOG DXF: {e}")
        sys.exit(1)

    try:
        gen_doc = ezdxf.readfile(gen_path)
    except Exception as e:
        print(f"ERROR: Cannot read Generated DXF: {e}")
        sys.exit(1)

    stog_msp = stog_doc.modelspace()
    gen_msp = gen_doc.modelspace()

    # Filter entities to V22 / V2 bounding boxes
    print("  Filtering entities to target areas...")

    stog_v22 = get_entities_in_bbox(stog_msp, STOG_V22_BBOX)
    gen_v2 = get_entities_in_bbox(gen_msp, GEN_V2_BBOX)

    stog_v22_section = get_entities_in_bbox(stog_msp, STOG_V22_SECTION_BBOX)
    gen_v2_section = get_entities_in_bbox(gen_msp, GEN_V2_SECTION_BBOX)

    print(f"  STOG V22 entities: {len(stog_v22)} (section: {len(stog_v22_section)})")
    print(f"  Gen V2 entities:   {len(gen_v2)} (section: {len(gen_v2_section)})")

    # Run tests
    test1_entity_count(stog_v22, gen_v2)
    test2_panel_geometry(stog_v22, gen_v2)
    test3_cross_section_audit(stog_v22, gen_v2, stog_v22_section, gen_v2_section)
    test4_sarr_pattern(stog_v22, gen_v2)
    test5_hatch_analysis(stog_v22, gen_v2)
    test6_text_content(stog_v22, gen_v2)
    test7_dimension_analysis(stog_v22, gen_v2)
    test8_missing_elements(stog_v22, gen_v2)

    # Summary
    print(f"\n{'='*80}")
    print(f"  VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"  PASS: {PASS_COUNT} tests")
    print(f"  FAIL: {FAIL_COUNT} tests")

    # Deduplicate
    unique_missing = sorted(set(MISSING_ELEMENTS))
    unique_extra = sorted(set(EXTRA_ELEMENTS))
    unique_recs = []
    seen_recs = set()
    for r in RECOMMENDATIONS:
        if r not in seen_recs:
            unique_recs.append(r)
            seen_recs.add(r)

    print(f"\n  MISSING ELEMENTS ({len(unique_missing)}):")
    if unique_missing:
        for m in unique_missing:
            print(f"    [-] {m}")
    else:
        print("    (none)")

    print(f"\n  EXTRA ELEMENTS ({len(unique_extra)}):")
    if unique_extra:
        for e in unique_extra:
            print(f"    [+] {e}")
    else:
        print("    (none)")

    print(f"\n  RECOMMENDATIONS (prioritized):")
    if unique_recs:
        for i, r in enumerate(unique_recs, 1):
            print(f"    {i}. {r}")
    else:
        print("    (none - all tests passed)")

    print(f"\n{'='*80}")

    return 0 if FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
