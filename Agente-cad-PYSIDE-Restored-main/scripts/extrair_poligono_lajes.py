#!/usr/bin/env python3
"""
extrair_poligono_lajes.py - Extrai coordenadas (poligono) das lajes do LJ DXF.

Fontes (prioridade):
  1. LJ DXF layer "1" LWPOLYLINE - poligono real por proximidade ao label
  2. Paineis grid: H lines (comp) + V dim chains (larg) do layer Paineis
  3. Paineis dim chain: H dim chain (comp) + V dim chain (larg) quando H line falha
  4. AUX00 bounding box de posicoes de paineis (deduplicados)
  5. COTA DIMENSION mais proxima ao label para obter dims
  6. Default: retangulo 100x100

Story: CAD-6.3
Usage: python scripts/extrair_poligono_lajes.py --obra PATH
"""
import argparse, json, math, re, sys
from pathlib import Path
from collections import defaultdict

try:
    import ezdxf
except ImportError:
    print("ERROR: pip install ezdxf")
    sys.exit(1)


# --- Constantes ---------------------------------------------------------------
MATCH_RADIUS   = 5000.0   # Raio para match label <-> poligono
MIN_POLY_AREA  = 50000.0  # Area minima LWPOLYLINE para ser laje (cm2) = 5m² minimo
MAX_SHEET_AREA = 300000.0 # Area maxima plausivel de uma laje
DIM_MIN        = 50.0     # Dim minima para laje (cm)
DIM_MAX        = 3000.0   # Dim maxima para laje (cm)
MIN_LAJE_DIM   = 200.0    # Dimensao minima aceitavel para uma laje (cm)
MIN_PANEL_DIM  = 50.0     # Dimensao minima de painel para considerar (cm)
JUNTA_MAX      = 40.0     # Dimensao maxima de junta (nao contar como painel)
H_LINE_MIN_LEN = 100.0    # Comprimento minimo de H line no layer Paineis


# --- Utilidades ---------------------------------------------------------------
def dist2d(p1, p2):
    return math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

def centroid2d(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (sum(xs)/len(xs), sum(ys)/len(ys))

def poly_area(pts):
    n = len(pts)
    if n < 3: return 0.0
    s = sum(pts[i][0]*pts[(i+1)%n][1] - pts[(i+1)%n][0]*pts[i][1] for i in range(n))
    return abs(s) / 2.0

def normalize_coords(pts):
    if not pts: return pts
    min_x = min(p[0] for p in pts); min_y = min(p[1] for p in pts)
    return [[round(p[0]-min_x, 1), round(p[1]-min_y, 1)] for p in pts]

def bbox_dims(pts):
    if not pts: return None, None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    w = max(xs)-min(xs); h = max(ys)-min(ys)
    return round(max(w,h), 1), round(min(w,h), 1)

def rect_coords(comp, larg):
    return [[0.0,0.0],[comp,0.0],[comp,larg],[0.0,larg],[0.0,0.0]]


# --- Localizacao DXFs ---------------------------------------------------------
def find_lj_dxf(obra_path: Path) -> Path | None:
    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    for f in sorted(fase1.glob("*.dxf")):
        if "LJ" in f.name.upper() and "12" in f.name: return f
    for f in sorted(fase1.glob("*.dxf")):
        if "LJ" in f.name.upper(): return f
    return None


# --- Extracao AUX00 -----------------------------------------------------------
PAT_LAJE_EXACT = re.compile(r'^L(\d+[A-Z]?)$', re.IGNORECASE)
PAT_DIMS       = re.compile(r'(\d+(?:\.\d+)?)\s*[Xx]\s*(\d+(?:\.\d+)?)')

def parse_aux00(text: str):
    """Retorna (lid, dim1, dim2) ou None. Aceita texto bruto MTEXT com formatacao DXF."""
    text = text.replace('\\P', '\n').replace('\r', '\n')
    lines = [re.sub(r'\{?\\[^;]+;', '', l).strip() for l in text.split('\n')]
    lid = None; dim1 = dim2 = None
    for line in lines:
        if not line: continue
        m = PAT_LAJE_EXACT.fullmatch(line)
        if m: lid = "L" + m.group(1).upper(); continue
        m = PAT_DIMS.search(line)
        if m: dim1, dim2 = float(m.group(1)), float(m.group(2))
    return (lid, dim1, dim2) if lid else None


def extract_aux00(msp) -> dict:
    """
    Extrai paineis AUX00 de um unico modelspace, deduplica por posicao (grid 20 units).
    Retorna: {lid: [{"dim1", "dim2", "pos"}]}
    """
    panels = defaultdict(list)
    seen_pos = defaultdict(set)  # lid -> set de (gx, gy)

    for e in msp:
        if e.dxftype() not in ("MTEXT", "TEXT"): continue
        try:
            if e.dxf.layer.upper() != "AUX00": continue
            raw = e.plain_text().strip() if e.dxftype() == "MTEXT" else e.dxf.text.strip()
            pos = (e.dxf.insert.x, e.dxf.insert.y)
        except Exception: continue
        result = parse_aux00(raw)
        if not result: continue
        lid, d1, d2 = result
        # Deduplicar por grid 20 units
        gx = round(pos[0] / 20) * 20; gy = round(pos[1] / 20) * 20
        key = (gx, gy)
        if key in seen_pos[lid]: continue
        seen_pos[lid].add(key)
        if d1 and d2:
            panels[lid].append({"dim1": d1, "dim2": d2, "pos": pos})
        else:
            panels[lid].append({"dim1": None, "dim2": None, "pos": pos})
    return dict(panels)


def panels_to_area_estimate(panel_list: list):
    """
    Estima dimensoes da laje a partir da AREA TOTAL dos paineis.
    Estrategia: total_area / max_dim = comprimento; largura = max_dim.
    A posicao dos labels no DXF nao reflete o tamanho fisico — usamos area.
    Retorna (coords, comp, larg) ou (None, None, None).
    """
    has_dims = [p for p in panel_list if p.get("dim1") and p.get("dim2")]
    if not has_dims: return None, None, None

    total_area = sum(p["dim1"] * p["dim2"] for p in has_dims)
    # Maior dimensao encontrada = altura padrao do painel (tipicamente 244cm)
    max_dim = max(max(p["dim1"], p["dim2"]) for p in has_dims)

    # Assumir que paineis sao dispostos em faixas de largura max_dim
    # comp = total_area / max_dim (quantos paineis cabem na direcao longitudinal)
    larg_est = round(max_dim, 1)
    comp_est = round(total_area / larg_est, 1) if larg_est > 0 else larg_est

    # Garantir comp >= larg
    comp = max(comp_est, larg_est)
    larg = min(comp_est, larg_est)

    coords = rect_coords(comp, larg)
    return coords, comp, larg


# --- Labels -------------------------------------------------------------------
def extract_labels(msp) -> dict:
    """Extrai labels L{n} de layers de texto do LJ DXF. Retorna {lid: (x,y)}."""
    text_layers = {"3", "4", "6", "AUX00", "NOMENCLATURA", "texto", "TEXTO"}
    labels = {}
    pat = re.compile(r'^L(\d+[A-Z]?)$', re.IGNORECASE)
    for e in msp:
        if e.dxftype() not in ("TEXT", "MTEXT"): continue
        try:
            lyr = e.dxf.layer
            if lyr not in text_layers and lyr not in ("3","4","6","7"): continue
            txt = e.plain_text().strip() if e.dxftype() == "MTEXT" else e.dxf.text.strip()
            pos = (e.dxf.insert.x, e.dxf.insert.y)
        except Exception: continue
        for line in txt.split('\n'):
            line = line.strip()
            m = pat.fullmatch(line)
            if m:
                lid = "L" + m.group(1).upper()
                if lid not in labels:
                    labels[lid] = pos


    return labels


# --- LWPOLYLINE ---------------------------------------------------------------
def extract_lwpolys(msp, layer: str, area_min: float, area_max: float) -> list:
    """Extrai LWPOLYLINE de um layer com filtro de area."""
    result = []
    for e in msp:
        if e.dxftype() != "LWPOLYLINE": continue
        try:
            if e.dxf.layer != layer: continue
            pts = [(v[0],v[1]) for v in e.get_points()]
            if len(pts) < 3: continue
            if pts[0] != pts[-1]: pts.append(pts[0])
            area = poly_area(pts)
            if area < area_min or area > area_max: continue
            ctr = centroid2d(pts[:-1])
            result.append({"pts": pts, "area": area, "centroid": ctr})
        except Exception: continue
    return sorted(result, key=lambda x: -x["area"])


# --- COTA DIMENSIONs ----------------------------------------------------------
def extract_cota_dims(msp) -> list:
    """Extrai DIMENSIONs do layer COTA com valores no range DIM_MIN..DIM_MAX."""
    dims = []
    for e in msp:
        if e.dxftype() != "DIMENSION": continue
        try:
            if e.dxf.layer.upper() != "COTA": continue
            val = e.dxf.actual_measurement
            if val < DIM_MIN or val > DIM_MAX: continue
            pos = (e.dxf.defpoint.x, e.dxf.defpoint.y)
            dims.append({"val": round(val, 1), "pos": pos})
        except Exception: continue
    return dims


def find_dims_near_label(label_pos: tuple, dims: list, radius: float = 1500.0) -> list:
    """Retorna dims dentro do raio, ordenados por distancia."""
    near = []
    for d in dims:
        dist = dist2d(label_pos, d["pos"])
        if dist <= radius:
            near.append((dist, d["val"]))
    near.sort()
    return [v for _, v in near]


def dims_to_comp_larg(vals: list):
    """Dado valores de DIMENSION proximos, tenta encontrar comp e larg."""
    if not vals: return None, None
    # Filtrar valores plausíveis para laje
    plausible = sorted([v for v in vals if DIM_MIN <= v <= DIM_MAX], reverse=True)
    if not plausible: return None, None
    if len(plausible) >= 2:
        comp = plausible[0]; larg = plausible[1]
    else:
        comp = larg = plausible[0]
    return round(comp, 1), round(larg, 1)


# --- Match poligono -----------------------------------------------------------
def match_poly(label_pos: tuple, polys: list, used: set, radius: float) -> dict | None:
    candidates = []
    for p in polys:
        if id(p) in used: continue
        d = dist2d(label_pos, p["centroid"])
        if d <= radius:
            candidates.append((d, p))
    if not candidates: return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


# --- Paineis grid extraction --------------------------------------------------
def extract_paineis_hlines(msp) -> list:
    """Extrai LINEs horizontais do layer Paineis (len > H_LINE_MIN_LEN)."""
    result = []
    for e in msp:
        if e.dxftype() != "LINE": continue
        try:
            layer = e.dxf.layer
        except Exception:
            continue
        if "Pain" not in layer and "pain" not in layer and "PAIN" not in layer:
            continue
        sx, sy = e.dxf.start.x, e.dxf.start.y
        ex, ey = e.dxf.end.x, e.dxf.end.y
        if abs(ey - sy) >= 2: continue  # not horizontal
        x_lo = min(sx, ex); x_hi = max(sx, ex)
        length = x_hi - x_lo
        if length < H_LINE_MIN_LEN: continue
        result.append({"xlo": x_lo, "xhi": x_hi, "y": round((sy+ey)/2, 1), "len": round(length, 1)})
    return result


def extract_paineis_dims(msp) -> list:
    """Extrai DIMENSIONs do layer Paineis com orientacao e endpoints."""
    result = []
    for e in msp:
        if e.dxftype() != "DIMENSION": continue
        try:
            layer = e.dxf.layer
        except Exception:
            continue
        if "Pain" not in layer and "pain" not in layer and "PAIN" not in layer:
            continue
        try:
            val = round(e.dxf.actual_measurement, 1)
            p2 = (e.dxf.defpoint2.x, e.dxf.defpoint2.y)
            p3 = (e.dxf.defpoint3.x, e.dxf.defpoint3.y)
            dx = abs(p2[0]-p3[0]); dy = abs(p2[1]-p3[1])
            orient = "H" if dx > dy else "V"
            result.append({
                "val": val, "p2": p2, "p3": p3, "orient": orient,
                "xlo": min(p2[0], p3[0]), "xhi": max(p2[0], p3[0]),
                "ylo": min(p2[1], p3[1]), "yhi": max(p2[1], p3[1]),
                "xmid": (p2[0]+p3[0])/2, "ymid": (p2[1]+p3[1])/2,
            })
        except Exception:
            continue
    return result


def find_containing_hline(lx, ly, h_lines):
    """Find the Paineis H line whose X range contains lx, closest in Y."""
    containing = [h for h in h_lines if h["xlo"] - 5 <= lx <= h["xhi"] + 5]
    if not containing:
        return None
    containing.sort(key=lambda h: abs(h["y"] - ly))
    return containing[0]


def chain_vdims_for_laje(lx, ly, hline, all_dims):
    """
    Chain vertical DIMENSIONs within the laje column (hline X range).
    Start from the V dim closest to the label, then expand by stacking.
    Only include dims with val >= MIN_PANEL_DIM to skip juntas.
    """
    col_vdims = [d for d in all_dims
                 if d["orient"] == "V"
                 and d["val"] >= MIN_PANEL_DIM
                 and d["xlo"] >= hline["xlo"] - 30
                 and d["xhi"] <= hline["xhi"] + 30]

    if not col_vdims:
        return 0, []

    # Sort by distance of Y-center to label Y
    col_vdims.sort(key=lambda d: abs((d["ylo"]+d["yhi"])/2 - ly))

    # Start from closest, chain by stacking
    seed = col_vdims[0]
    chain_ylo = seed["ylo"]
    chain_yhi = seed["yhi"]
    used = {id(seed)}
    chain_vals = [seed["val"]]

    changed = True
    while changed:
        changed = False
        for d in col_vdims:
            if id(d) in used:
                continue
            # Stacks on top?
            if abs(d["ylo"] - chain_yhi) < 5:
                chain_yhi = d["yhi"]
                used.add(id(d))
                chain_vals.append(d["val"])
                changed = True
            # Stacks on bottom?
            elif abs(d["yhi"] - chain_ylo) < 5:
                chain_ylo = d["ylo"]
                used.add(id(d))
                chain_vals.insert(0, d["val"])
                changed = True

    return round(sum(chain_vals), 1), chain_vals


def chain_hdims_for_laje(lx, ly, all_dims, y_tolerance=250):
    """
    Chain horizontal DIMENSIONs to compute laje comprimento.
    Find H dims near the label, chain by connecting endpoints left-to-right.
    Only include dims with val >= MIN_PANEL_DIM.
    """
    # Find H dims on same row (Y within tolerance)
    row_dims = []
    for d in all_dims:
        if d["orient"] != "H": continue
        if d["val"] < MIN_PANEL_DIM: continue
        if abs(d["ymid"] - ly) > y_tolerance: continue
        row_dims.append(d)

    if not row_dims:
        return 0, []

    row_dims.sort(key=lambda d: d["xlo"])

    # Find the dim containing or closest to lx
    containing = [d for d in row_dims if d["xlo"] <= lx + 10 and d["xhi"] >= lx - 10]
    if not containing:
        # Pick closest to lx
        containing = sorted(row_dims, key=lambda d: abs(d["xmid"] - lx))[:1]
    if not containing:
        return 0, []

    seed = containing[0]
    chain = [seed]
    seed_y = seed["ymid"]

    # Expand right
    cur_x = seed["xhi"]
    for _ in range(20):
        nxt = [d for d in row_dims
               if abs(d["xlo"] - cur_x) < 5
               and abs(d["ymid"] - seed_y) < 5
               and d not in chain]
        if not nxt: break
        best = min(nxt, key=lambda d: abs(d["xlo"] - cur_x))
        chain.append(best)
        cur_x = best["xhi"]

    # Expand left
    cur_x = seed["xlo"]
    for _ in range(20):
        nxt = [d for d in row_dims
               if abs(d["xhi"] - cur_x) < 5
               and abs(d["ymid"] - seed_y) < 5
               and d not in chain]
        if not nxt: break
        best = min(nxt, key=lambda d: abs(d["xhi"] - cur_x))
        chain.insert(0, best)
        cur_x = best["xlo"]

    total_w = round(sum(d["val"] for d in chain), 1)
    return total_w, chain


def paineis_grid_dims(lx, ly, h_lines, all_dims):
    """
    Primary method: use Paineis H line for comp + V dim chain for larg.
    Returns (comp, larg, chain_h_vals, chain_v_vals) or None if not found.
    """
    hline = find_containing_hline(lx, ly, h_lines)
    if not hline:
        return None

    comp = round(hline["len"], 1)

    # Check if this H line is implausibly large (e.g. structural line spanning whole building)
    # A single laje should not be wider than ~600cm typically
    if comp > 800:
        return None  # Skip, will use dim chain fallback

    larg, v_chain = chain_vdims_for_laje(lx, ly, hline, all_dims)

    if comp >= MIN_LAJE_DIM and larg >= MIN_PANEL_DIM:
        return comp, larg, [], v_chain

    return None


def paineis_dimchain_dims(lx, ly, h_lines, all_dims):
    """
    Fallback: use H dim chain for comp + V dim chain for larg.
    For lajes where the H line is missing or implausibly large.
    Returns (comp, larg, h_chain_vals, v_chain_vals) or None.
    """
    comp, h_chain = chain_hdims_for_laje(lx, ly, all_dims)
    h_vals = [d["val"] if isinstance(d, dict) else d for d in h_chain]

    # For larg: create synthetic hline from the H chain span to scope V dim search
    if h_chain:
        synth_hline = {"xlo": lx - comp/2 - 50, "xhi": lx + comp/2 + 50}
        larg, v_chain = chain_vdims_for_laje(lx, ly, synth_hline, all_dims)
    else:
        larg = 0
        v_chain = []

    if comp >= MIN_PANEL_DIM and larg >= MIN_PANEL_DIM:
        return comp, larg, h_vals, v_chain

    # Last resort: try with V dims using a wide search
    if comp >= MIN_PANEL_DIM and larg < MIN_PANEL_DIM:
        wide_hline = {"xlo": lx - 500, "xhi": lx + 500}
        larg, v_chain = chain_vdims_for_laje(lx, ly, wide_hline, all_dims)
        if larg >= MIN_PANEL_DIM:
            return comp, larg, h_vals, v_chain

    return None


# --- Main ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='Extrair poligono das lajes LJ DXF')
    parser.add_argument('--obra', required=True)
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    lj_path = find_lj_dxf(obra_path)
    if not lj_path:
        print(f"ERRO: LJ DXF nao encontrado")
        sys.exit(1)

    print(f"LJ DXF: {lj_path.name}")
    doc = ezdxf.readfile(str(lj_path))
    msp = doc.modelspace()

    # 1. AUX00 panels (modelspace apenas — sem duplicar)
    print("AUX00 panels...", end="", flush=True)
    aux00 = extract_aux00(msp)
    total_panels = sum(len(v) for v in aux00.values())
    print(f" {total_panels} panels em {len(aux00)} lajes: {sorted(aux00.keys())}")

    # 2. Labels L{n}
    print("Labels L{n}...", end="", flush=True)
    labels = extract_labels(msp)
    print(f" {len(labels)} labels: {sorted(labels.keys())}")

    # Posicao de cada laje: priorizar label de texto, fallback centroide AUX00
    label_pos = {}
    for lid, panels in aux00.items():
        xs = [p["pos"][0] for p in panels]; ys = [p["pos"][1] for p in panels]
        if xs: label_pos[lid] = (sum(xs)/len(xs), sum(ys)/len(ys))
    for lid, pos in labels.items():
        label_pos[lid] = pos  # Sobrepoe com posicao do label

    # 3. LWPOLYLINE layer "1"
    print("LWPOLYLINE layer '1'...", end="", flush=True)
    polys1 = extract_lwpolys(msp, "1", MIN_POLY_AREA, MAX_SHEET_AREA)
    print(f" {len(polys1)} poligonos | areas: {[str(round(p['area'])) for p in polys1[:5]]}")

    # 4. COTA DIMENSIONs
    print("COTA DIMENSIONs...", end="", flush=True)
    cota_dims = extract_cota_dims(msp)
    print(f" {len(cota_dims)} dims no range {DIM_MIN}-{DIM_MAX}cm")

    # 5. Paineis grid
    print("Paineis H lines...", end="", flush=True)
    paineis_hlines = extract_paineis_hlines(msp)
    print(f" {len(paineis_hlines)} lines (len>{H_LINE_MIN_LEN})")

    print("Paineis DIMENSIONs...", end="", flush=True)
    paineis_dims = extract_paineis_dims(msp)
    print(f" {len(paineis_dims)} dims ({sum(1 for d in paineis_dims if d['orient']=='H')} H, {sum(1 for d in paineis_dims if d['orient']=='V')} V)")

    # 6. Processar cada laje
    all_lids = sorted(set(list(aux00.keys()) + list(labels.keys())),
                      key=lambda x: (len(x), x))
    print(f"\nProcessando {len(all_lids)} lajes...")

    result = {}
    used_polys = set()

    # Determine which lajes are AUX00-only (no TEXT label on proper label layers 4/6/NOMENCLATURA)
    # Extract labels from layer 4 specifically for this check
    labels_layer4 = set()
    for e in msp:
        if e.dxftype() not in ("TEXT", "MTEXT"): continue
        try:
            lyr = e.dxf.layer
            if lyr not in ("4", "6", "NOMENCLATURA"): continue
            txt = e.plain_text().strip() if e.dxftype() == "MTEXT" else e.dxf.text.strip()
        except Exception: continue
        for line in txt.split('\n'):
            m = re.fullmatch(r'L(\d+[A-Z]?)', line.strip(), re.IGNORECASE)
            if m:
                labels_layer4.add("L" + m.group(1).upper())
    aux00_only = set(aux00.keys()) - labels_layer4

    for lid in all_lids:
        lpos = label_pos.get(lid)
        panels = aux00.get(lid, [])
        entry = {"id": lid, "coordenadas": None, "comprimento": None, "largura": None,
                 "confidence": 0.0, "source": "unknown"}

        # -- A: LWPOLYLINE layer "1" (somente se area > MIN_POLY_AREA = laje real) --
        if lpos:
            poly = match_poly(lpos, polys1, used_polys, MATCH_RADIUS)
            if poly:
                pts_local = normalize_coords(poly["pts"])
                comp, larg = bbox_dims(pts_local)
                if comp and comp >= MIN_LAJE_DIM and larg and larg >= MIN_LAJE_DIM:
                    used_polys.add(id(poly))
                    entry.update({
                        "coordenadas": pts_local, "comprimento": comp, "largura": larg,
                        "confidence": 0.75, "source": "lj-layer1-poly",
                        "area_dxf": round(poly["area"], 1),
                        "dist_label": round(dist2d(lpos, poly["centroid"]), 1)
                    })
                    result[lid] = entry; continue
                # Poligono muito pequeno — descartar e usar proximo metodo

        # -- A2: AUX00 FIRST for AUX00-only lajes (scattered panel positions unreliable for grid) --
        if lid in aux00_only and panels:
            coords, comp, larg = panels_to_area_estimate(panels)
            if coords and comp >= DIM_MIN:
                total_a = sum(p["dim1"]*p["dim2"] for p in panels if p.get("dim1") and p.get("dim2"))
                entry.update({
                    "coordenadas": coords, "comprimento": comp, "largura": larg,
                    "confidence": 0.55, "source": "aux00-area-estimate",
                    "n_panels": len(panels),
                    "total_area_cm2": round(total_a, 0)
                })
                result[lid] = entry; continue

        # -- B: Paineis grid (H line comp + V dim chain larg) --
        if lpos and paineis_hlines and paineis_dims:
            grid_result = paineis_grid_dims(lpos[0], lpos[1], paineis_hlines, paineis_dims)
            if grid_result:
                comp, larg, h_chain, v_chain = grid_result
                coords = rect_coords(comp, larg)
                entry.update({
                    "coordenadas": coords, "comprimento": comp, "largura": larg,
                    "confidence": 0.70, "source": "paineis-grid",
                    "v_chain": v_chain,
                })
                result[lid] = entry; continue

        # -- B2: Paineis dim chain fallback (when H line missing or too large) --
        if lpos and paineis_dims:
            chain_result = paineis_dimchain_dims(lpos[0], lpos[1], paineis_hlines, paineis_dims)
            if chain_result:
                comp, larg, h_chain, v_chain = chain_result
                coords = rect_coords(comp, larg)
                h_vals = []
                if h_chain:
                    for item in h_chain:
                        if isinstance(item, dict):
                            h_vals.append(item.get("val", 0))
                        else:
                            h_vals.append(item)
                entry.update({
                    "coordenadas": coords, "comprimento": comp, "largura": larg,
                    "confidence": 0.60, "source": "paineis-dimchain",
                    "h_chain": h_vals,
                    "v_chain": v_chain,
                })
                result[lid] = entry; continue

        # -- C: AUX00 estimativa por area total dos paineis --
        if panels:
            coords, comp, larg = panels_to_area_estimate(panels)
            if coords and comp >= DIM_MIN:
                total_a = sum(p["dim1"]*p["dim2"] for p in panels if p.get("dim1") and p.get("dim2"))
                entry.update({
                    "coordenadas": coords, "comprimento": comp, "largura": larg,
                    "confidence": 0.55, "source": "aux00-area-estimate",
                    "n_panels": len(panels),
                    "total_area_cm2": round(total_a, 0)
                })
                result[lid] = entry; continue

        # -- D: COTA DIMENSIONs proximas --
        if lpos and cota_dims:
            near_vals = find_dims_near_label(lpos, cota_dims, radius=2000.0)
            comp, larg = dims_to_comp_larg(near_vals)
            if comp and comp >= DIM_MIN:
                coords = rect_coords(comp, larg)
                entry.update({
                    "coordenadas": coords, "comprimento": comp, "largura": larg,
                    "confidence": 0.40, "source": "cota-dims",
                    "dims_found": near_vals[:4]
                })
                result[lid] = entry; continue

        # -- Default --
        entry.update({
            "coordenadas": rect_coords(100.0, 100.0),
            "comprimento": 100.0, "largura": 100.0,
            "confidence": 0.05, "source": "default",
            "nota": "Sem dados"
        })
        result[lid] = entry

    # 7. Salvar
    out_path = (Path(args.output) if args.output
                else obra_path / "Fase-3_Interpretacao_Extracao" / "Lajes" / "lajes_poligono.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Relatorio
    src_counts = {}
    for v in result.values():
        s = v.get("source","?"); src_counts[s] = src_counts.get(s,0) + 1

    print(f"\n=== RESULTADO ===")
    print(f"  Total lajes: {len(result)}")
    for s, c in sorted(src_counts.items()):
        tag = {
            "lj-layer1-poly": "(alta)",
            "paineis-grid": "(alta)",
            "paineis-dimchain": "(media-alta)",
            "aux00-area-estimate": "(media)",
            "cota-dims": "(media-baixa)",
            "default": "(baixa)"
        }.get(s, "")
        print(f"  [{s}]: {c} {tag}")
    print(f"  Output: {out_path}")

    print(f"\n{'Laje':<8} {'Comp':<10} {'Larg':<10} {'Conf':<6} {'Fonte'}")
    print("-" * 60)
    for lid, v in sorted(result.items(), key=lambda x: (len(x[0]), x[0])):
        print(f"{lid:<8} {str(v['comprimento']):<10} {str(v['largura']):<10} {v['confidence']:<6.2f} {v['source']}")

    # Detalhe AUX00
    if aux00:
        print(f"\n=== AUX00 panels (dedup) ===")
        for lid in sorted(aux00.keys(), key=lambda x:(len(x),x)):
            pl = aux00[lid]
            dims = " | ".join(f"{p['dim1']}x{p['dim2']}" for p in pl if p.get("dim1"))
            print(f"  {lid}: {len(pl)} panels -> {dims}")


if __name__ == "__main__":
    main()
