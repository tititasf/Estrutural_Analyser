#!/usr/bin/env python3
"""
gerar_lajes_completo.py
Gera DXF de lajes (planta baixo) no mesmo estilo visual dos pilares.

JSON: Fase-4_Sincronizacao/JSON_Lajes/L{n}.json
Layout por célula: planta da laje com linhas divisórias de painéis
Escala: 1 unidade = 1cm

Uso:
  python scripts/gerar_lajes_completo.py
  python scripts/gerar_lajes_completo.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1 --cols 4
"""
import argparse
import json
import sys
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

# ---------------------------------------------------------------------------
# CONSTANTES (cm)
# ---------------------------------------------------------------------------
MARGIN_X     = 15.0
MARGIN_Y     = 5.0
CARIMBO_H    = 40.0
HEADER_H     = 25.0
DIM_SPACE    = 30.0
GRID_GAP_X   = 25.0
GRID_GAP_Y   = 25.0
COLS_DEFAULT = 4
MAX_CELL_SIDE = 300.0   # limitar escala de lajes muito grandes

LAYERS = [
    ("Painéis",       200),   # violeta — outline laje (LINE+DIMENSION, real LJ)
    ("Hachura",       251),   # cinza — fill SOLID only (LJ: SEM ANSI31)
    ("DIVISAO",       40),    # linhas divisórias internas (âmbar)
    ("NOMENCLATURA",   7),    # branco
    ("COTA",         241),    # pink — cotas
    ("Texto Seção",    7),    # branco — labels
    ("CARIMBO",        9),
    ("BORDA_CELULA",   9),
    ("OBSTACULO",      1),    # obstáculos/vazios
]


def setup_doc():
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    if 'HIDDEN' not in doc.linetypes:
        doc.linetypes.add('HIDDEN', pattern=[0.375, 0.25, -0.125])
    for name, color in LAYERS:
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    if 'FACE_DIM' not in doc.dimstyles:
        ds = doc.dimstyles.new('FACE_DIM')
        ds.dxf.dimtxt  = 3.5
        ds.dxf.dimasz  = 2.0
        ds.dxf.dimexo  = 1.0
        ds.dxf.dimexe  = 2.0
        ds.dxf.dimgap  = 1.0
        ds.dxf.dimdec  = 0
        ds.dxf.dimrnd  = 1.0
        ds.dxf.dimclrd = 4     # cyan (igual real ALIMONTI dimstyle PAINEL)
        ds.dxf.dimclre = 4
        ds.dxf.dimclrt = 4
    return doc, msp


def draw_hatch_solid(msp, pts, layer, color=None):
    h = msp.add_hatch(dxfattribs={'layer': layer})
    h.dxf.color = color if color is not None else 256
    h.paths.add_polyline_path(pts, is_closed=True)
    return h


def draw_hatch_pattern(msp, pts, layer, color=None, pattern='ANSI31', scale=5.0, angle=45.0):
    h = msp.add_hatch(dxfattribs={'layer': layer})
    try:
        h.set_pattern_fill(pattern, scale=scale, angle=angle)
    except Exception:
        h.dxf.solid_fill = 1
    h.dxf.color = color if color is not None else 256
    h.paths.add_polyline_path(pts, is_closed=True)
    return h


def draw_closed_poly(msp, pts, layer, color=None):
    attribs = {'layer': layer}
    if color is not None:
        attribs['color'] = color
    return msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)


def calc_scale(comprimento, largura):
    """Fator de escala para caber na célula."""
    max_side = max(comprimento, largura)
    if max_side <= MAX_CELL_SIDE:
        return 1.0
    return MAX_CELL_SIDE / max_side


def calc_cell_size(data):
    comp = float(data.get('comprimento', 100.0))
    larg = float(data.get('largura', 100.0))
    sc   = calc_scale(comp, larg)
    draw_w = comp * sc
    draw_h = larg * sc
    cell_w = MARGIN_X * 2 + draw_w + DIM_SPACE + 10
    cell_h = CARIMBO_H + MARGIN_Y + draw_h + DIM_SPACE + HEADER_H + 10
    return cell_w, cell_h


def draw_laje(msp, name, data, cell_ox, cell_oy, pav, max_cell_h=None):
    """Desenha a laje em planta (vista de cima) com painéis divididos."""
    comp = float(data.get('comprimento', 100.0))
    larg = float(data.get('largura', 100.0))
    sc   = calc_scale(comp, larg)
    draw_w = comp * sc
    draw_h = larg * sc

    # Ancorar pelo TOPO da célula
    used_h = max_cell_h if max_cell_h is not None else (CARIMBO_H + MARGIN_Y + DIM_SPACE + draw_h + HEADER_H + 10)
    x0 = cell_ox + MARGIN_X
    y0 = cell_oy + used_h - HEADER_H - 5.0 - draw_h

    # Header
    pav_ascii = pav.encode('ascii', 'replace').decode('ascii')
    msp.add_text(
        f"{name} -- {pav_ascii}  ({comp:.0f}x{larg:.0f}cm)",
        dxfattribs={'layer': 'NOMENCLATURA', 'color': 256, 'height': 5.0,
                    'insert': (x0, y0 + draw_h + HEADER_H / 2)}
    )

    # Contorno principal da laje
    # LJ: Hachura SOLID only (SEM ANSI31 — verificado real ALIMONTI)
    coords = data.get('coordenadas', [])
    if len(coords) >= 3:
        poly_pts = [(x0 + c[0] * sc, y0 + c[1] * sc) for c in coords]
        draw_closed_poly(msp, poly_pts, 'Painéis')
        draw_hatch_solid(msp, poly_pts, 'Hachura')
    else:
        # Fallback: retângulo simples
        rect_pts = [(x0, y0), (x0 + draw_w, y0), (x0 + draw_w, y0 + draw_h), (x0, y0 + draw_h)]
        draw_closed_poly(msp, rect_pts, 'Painéis')
        draw_hatch_solid(msp, rect_pts, 'Hachura')

    # Linhas divisórias verticais
    for lv in data.get('linhas_verticais', []):
        xv = float(lv.get('value', 0)) * sc
        if 0 < xv < draw_w:
            msp.add_line((x0 + xv, y0), (x0 + xv, y0 + draw_h),
                         dxfattribs={'layer': 'DIVISAO', 'color': 40})
            # Cota do segmento (à esquerda desta linha)
            dim = msp.add_linear_dim(
                base=(x0 + xv / 2, y0 - 15.0),
                p1=(x0, y0), p2=(x0 + xv, y0),
                angle=0, dimstyle='FACE_DIM',
            )
            dim.render()

    # Linhas divisórias horizontais
    for lh in data.get('linhas_horizontais', []):
        yh = float(lh.get('value', 0)) * sc
        if 0 < yh < draw_h:
            msp.add_line((x0, y0 + yh), (x0 + draw_w, y0 + yh),
                         dxfattribs={'layer': 'DIVISAO', 'color': 40})
            dim = msp.add_linear_dim(
                base=(x0 - 15.0, y0 + yh / 2),
                p1=(x0, y0), p2=(x0, y0 + yh),
                angle=90, dimstyle='FACE_DIM',
                override={'dimtxt': 2.8, 'dimasz': 1.5, 'dimexo': 0.5, 'dimexe': 1.5},
            )
            dim.render()

    # Obstáculos (vazios, escadas, pilares)
    for obs in data.get('obstaculos', []):
        obs_coords = obs.get('coordenadas', [])
        if len(obs_coords) >= 3:
            obs_pts = [(x0 + c[0] * sc, y0 + c[1] * sc) for c in obs_coords]
            draw_closed_poly(msp, obs_pts, 'OBSTACULO', color=1)

    # Cota total comprimento (abaixo)
    dim_comp = msp.add_linear_dim(
        base=(x0 + draw_w / 2, y0 - 20.0),
        p1=(x0, y0), p2=(x0 + draw_w, y0),
        angle=0, dimstyle='FACE_DIM',
    )
    dim_comp.render()

    # Cota total largura (à direita)
    dim_larg = msp.add_linear_dim(
        base=(x0 + draw_w + 12.0, y0 + draw_h / 2),
        p1=(x0 + draw_w, y0), p2=(x0 + draw_w, y0 + draw_h),
        angle=90, dimstyle='FACE_DIM',
        override={'dimtxt': 2.8, 'dimasz': 1.5, 'dimexo': 0.5, 'dimexe': 1.5},
    )
    dim_larg.render()

    # Área
    area = float(data.get('area_cm2', comp * larg))
    msp.add_text(
        f"A={area / 10000:.2f}m²",
        dxfattribs={'layer': 'COTA', 'color': 256, 'height': 3.5,
                    'insert': (x0 + draw_w / 2, y0 + draw_h / 2)}
    ).set_placement((x0 + draw_w / 2, y0 + draw_h / 2), align=TextEntityAlignment.MIDDLE_CENTER)

    # Label
    msp.add_text(
        name,
        dxfattribs={'layer': 'Texto Seção', 'color': 256, 'height': 5.0,
                    'insert': (x0 + draw_w / 2, y0 + draw_h * 0.8)}
    ).set_placement((x0 + draw_w / 2, y0 + draw_h * 0.8), align=TextEntityAlignment.MIDDLE_CENTER)


def draw_carimbo(msp, cell_ox, cell_oy, cell_w, obra, pav, num, name):
    cx, cy = cell_ox, cell_oy
    draw_closed_poly(msp, [(cx, cy), (cx + cell_w, cy),
                             (cx + cell_w, cy + CARIMBO_H), (cx, cy + CARIMBO_H)],
                     'BORDA_CELULA')
    rows = [('CLIENTE', obra), ('PAVIMENTO', pav.encode('ascii', 'replace').decode('ascii')), ('LAJE', name)]
    row_h = CARIMBO_H / len(rows)
    for i, (label, val) in enumerate(rows):
        ry = cy + CARIMBO_H - (i + 1) * row_h
        msp.add_line((cx, ry), (cx + cell_w, ry), dxfattribs={'layer': 'CARIMBO'})
        msp.add_text(label + ':', dxfattribs={'layer': 'CARIMBO', 'height': 3.5, 'color': 9,
                                               'insert': (cx + 3, ry + row_h / 2)})
        msp.add_text(val, dxfattribs={'layer': 'CARIMBO', 'height': 4.0, 'color': 2,
                                       'insert': (cx + 35, ry + row_h / 2)})
    msp.add_text(f"{num:02d}", dxfattribs={'layer': 'CARIMBO', 'color': 3, 'height': 7.0,
                                            'insert': (cx + cell_w - 15, cy + 5)})


def build_grid(json_dir, out_path, obra_name, pav, cols):
    files = sorted(json_dir.glob('L*.json'),
                   key=lambda p: int(''.join(filter(str.isdigit, p.stem)) or '0'))
    if not files:
        print(f"ERRO: Nenhum L*.json em {json_dir}")
        sys.exit(1)

    print(f"  {len(files)} lajes encontradas")

    doc, msp = setup_doc()

    cell_sizes = []
    for jpath in files:
        data = json.loads(jpath.read_text(encoding='utf-8'))
        cw, ch = calc_cell_size(data)
        cell_sizes.append((cw, ch))

    max_cell_w = max(cw for cw, ch in cell_sizes)
    n = len(files)
    row_heights = []
    for r in range(0, n, cols):
        row_hs = [cell_sizes[j][1] for j in range(r, min(r + cols, n))]
        row_heights.append(max(row_hs) + GRID_GAP_Y)

    row_y_starts = []
    y = 0
    for rh in row_heights:
        y -= rh
        row_y_starts.append(y)

    cell_w = max_cell_w + GRID_GAP_X

    for i, jpath in enumerate(files):
        name = jpath.stem
        data = json.loads(jpath.read_text(encoding='utf-8'))
        face_pav = data.get('pavimento', pav)

        r = i // cols
        col = i % cols
        row_h = row_heights[r]
        row_cell_h = row_h - GRID_GAP_Y

        cell_ox = col * cell_w
        cell_oy = row_y_starts[r]

        draw_closed_poly(msp, [
            (cell_ox, cell_oy), (cell_ox + max_cell_w, cell_oy),
            (cell_ox + max_cell_w, cell_oy + row_cell_h), (cell_ox, cell_oy + row_cell_h),
        ], 'BORDA_CELULA')

        try:
            draw_laje(msp, name, data, cell_ox, cell_oy, face_pav, max_cell_h=row_cell_h)
            draw_carimbo(msp, cell_ox, cell_oy, max_cell_w, obra_name, face_pav, i + 1, name)
            comp = data.get('comprimento', 0)
            larg = data.get('largura', 0)
            area = data.get('area_cm2', comp * larg) / 10000
            print(f"  {name}: {comp:.0f}x{larg:.0f}cm  A={area:.2f}m²  [{col},{r}]")
        except Exception as e:
            print(f"  ERRO {name}: {e}")

    total_rows = len(row_heights)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out_path))
    print(f"\n  Salvo: {out_path}")
    print(f"  Grid: {len(files)} lajes — {cols} cols × {total_rows} linhas")


def main():
    parser = argparse.ArgumentParser(description='Gera DXF de lajes (planta)')
    parser.add_argument('--obra', default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    parser.add_argument('--pav', default='TÉRREO')
    parser.add_argument('--cols', type=int, default=COLS_DEFAULT)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    obra_name = obra_path.name
    json_dir  = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Lajes'

    if not json_dir.exists():
        print(f"ERRO: {json_dir} nao existe")
        sys.exit(1)

    out_path = Path(args.out) if args.out else \
        obra_path / 'Fase-5_Geracao_Scripts' / 'DXF_Lajes' / f'lajes_{obra_name}.dxf'

    print(f"\n=== GERAR DXF LAJES ===")
    print(f"  Obra  : {obra_name}")
    print(f"  JSON  : {json_dir}")
    print(f"  Output: {out_path}")
    print(f"  Cols  : {args.cols}\n")

    build_grid(json_dir, out_path, obra_name, args.pav, args.cols)


if __name__ == '__main__':
    main()
