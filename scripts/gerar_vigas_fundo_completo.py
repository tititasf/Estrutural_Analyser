#!/usr/bin/env python3
"""
gerar_vigas_fundo_completo.py
Gera DXF de faces de fundo de vigas no mesmo estilo visual dos pilares.

JSON: Fase-4_Sincronizacao/JSON_Vigas_Fundo/V{n}_fundo.json
Layout: elevação horizontal dos painéis de fundo (comprimento da viga)
Escala: 1 unidade = 1cm

Uso:
  python scripts/gerar_vigas_fundo_completo.py
  python scripts/gerar_vigas_fundo_completo.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1 --cols 4
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
DIM_SPACE    = 30.0    # espaço abaixo para cotas de largura de painel
COTA_RIGHT   = 15.0   # espaço à direita para cota de largura total
GRID_GAP_X   = 20.0
GRID_GAP_Y   = 20.0
COLS_DEFAULT = 4

LAYERS = [
    ("Painéis",       200),   # violeta — outline painel
    ("SARR_2.2x7",    40),    # âmbar — sarrafos Continuous (FV: NOT HIDDEN, sem hatch)
    ("NOMENCLATURA",   7),    # branco
    ("COTA",         241),    # pink — cotas
    ("Texto Seção",    7),    # branco — labels
    ("5",              5),    # azul — markers de pilar nos joints (igual real ALIMONTI)
    ("CARIMBO",        9),
    ("BORDA_CELULA",   9),
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


def draw_hatch_pattern(msp, pts, layer, color=None, pattern='ANSI31', scale=5.0, angle=0.0):
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


def total_face_width(panels):
    return sum(float(p['width']) for p in panels)


def calc_cell_size(data):
    total_w = total_face_width(data['panels'])
    # Fundo: largura total_width é a espessura da viga (eixo perpendicular)
    # A altura do desenho = total_width (viga se vê de cima/baixo)
    beam_w = float(data.get('total_width', 15.0))
    cell_w = MARGIN_X * 2 + total_w + COTA_RIGHT + 10
    cell_h = CARIMBO_H + MARGIN_Y + beam_w + DIM_SPACE + HEADER_H + 30
    return cell_w, cell_h


def calc_sarr_spacing(panel_w):
    n = max(2, int(panel_w / 60) + 1)
    if n == 1:
        return [panel_w / 2.0]
    return [2.2 / 2 + i * (panel_w - 2.2) / (n - 1) for i in range(n)]


def draw_fundo_face(msp, name, data, cell_ox, cell_oy, pav, max_cell_h=None):
    """Desenha a face de fundo da viga (vista de baixo, comprimento × espessura)."""
    total_w = total_face_width(data['panels'])
    beam_w  = float(data.get('total_width', 15.0))   # espessura/largura da viga em cm

    # Ancorar pelo TOPO da célula
    used_h = max_cell_h if max_cell_h is not None else (CARIMBO_H + MARGIN_Y + DIM_SPACE + beam_w + HEADER_H + 30)
    x0 = cell_ox + MARGIN_X
    y0 = cell_oy + used_h - HEADER_H - 5.0 - beam_w

    # Header
    pav_ascii = pav.encode('ascii', 'replace').decode('ascii')
    msp.add_text(
        f"{name} [FUNDO] -- {pav_ascii}",
        dxfattribs={'layer': 'NOMENCLATURA', 'color': 256, 'height': 5.0,
                    'insert': (cell_ox + MARGIN_X, cell_oy + used_h - HEADER_H / 2)}
    )

    # Painéis do fundo: largura=panel.width, altura=beam_w (espessura da viga)
    # FV: SEM HATCH (verificado real ALIMONTI — zero entidades Hachura em FV)
    # SARR_2.2x7: 2 linhas HORIZONTAIS por painel (em y0+7 e y0+beam_w-7) + bordas verticais
    # Ref: V201-CONJUNTO.dxf — padrão real ALIMONTI FV confirmado
    SARR_H = 7.0  # altura da faixa de sarrafo (cm)
    xc = x0
    for panel in data['panels']:
        pw = float(panel['width'])
        if pw <= 0:
            continue
        pts = [(xc, y0), (xc + pw, y0), (xc + pw, y0 + beam_w), (xc, y0 + beam_w)]
        draw_closed_poly(msp, pts, 'Painéis')

        # SARR_2.2x7: linha horizontal inferior do sarrafo (topo da faixa inferior)
        sarr_y_bot = y0 + SARR_H
        sarr_y_top = y0 + beam_w - SARR_H
        msp.add_line((xc, sarr_y_bot), (xc + pw, sarr_y_bot),
                     dxfattribs={'layer': 'SARR_2.2x7'})
        # SARR_2.2x7: linha horizontal superior do sarrafo (base da faixa superior)
        msp.add_line((xc, sarr_y_top), (xc + pw, sarr_y_top),
                     dxfattribs={'layer': 'SARR_2.2x7'})
        # Bordas verticais do sarrafo (esquerda e direita do painel)
        msp.add_line((xc, y0), (xc, y0 + beam_w),
                     dxfattribs={'layer': 'SARR_2.2x7'})
        msp.add_line((xc + pw, y0), (xc + pw, y0 + beam_w),
                     dxfattribs={'layer': 'SARR_2.2x7'})

        # Cota largura de cada painel (abaixo)
        dim_y = y0 - 15.0
        dim = msp.add_linear_dim(
            base=(xc + pw / 2, dim_y),
            p1=(xc, y0), p2=(xc + pw, y0),
            angle=0, dimstyle='FACE_DIM',
        )
        dim.render()
        xc += pw

    # Linhas divisórias entre painéis + markers de pilar
    pilar_labels = data.get('pilar_labels', [])  # lista de nomes: ["P1","P2","P3",...]
    xc2 = x0
    for pi, panel in enumerate(data['panels'][:-1]):
        xc2 += float(panel['width'])
        msp.add_line((xc2, y0), (xc2, y0 + beam_w), dxfattribs={'layer': 'Painéis'})
        # Label do pilar neste joint (layer "5" = ACI 5 = blue, igual real ALIMONTI FV)
        if pi < len(pilar_labels):
            lbl = pilar_labels[pi]
        else:
            lbl = f"P{pi+2}"
        msp.add_text(lbl, dxfattribs={'layer': '5', 'color': 5, 'height': 12.0,
                                       'insert': (xc2 - 3, y0 - 15)})

    # Cota de espessura (à direita, vertical)
    dim_x = x0 + total_w + 8.0
    dim_v = msp.add_linear_dim(
        base=(dim_x, y0 + beam_w / 2),
        p1=(dim_x - 4, y0), p2=(dim_x - 4, y0 + beam_w),
        angle=90, dimstyle='FACE_DIM',
        override={'dimtxt': 2.8, 'dimasz': 1.5, 'dimexo': 0.5, 'dimexe': 1.5},
    )
    dim_v.render()
    msp.add_text(
        f"TOTAL_W={total_w:.0f}cm",
        dxfattribs={'layer': 'COTA', 'color': 256, 'height': 3.0,
                    'insert': (x0, y0 + beam_w + 5)}
    )

    # Label
    msp.add_text(
        name,
        dxfattribs={'layer': 'Texto Seção', 'color': 256, 'height': 4.5,
                    'insert': (x0 + total_w / 2, y0 - 25)}
    ).set_placement((x0 + total_w / 2, y0 - 25), align=TextEntityAlignment.TOP_CENTER)


def draw_carimbo(msp, cell_ox, cell_oy, cell_w, obra, pav, num, name):
    cx, cy = cell_ox, cell_oy
    draw_closed_poly(msp, [(cx, cy), (cx + cell_w, cy),
                             (cx + cell_w, cy + CARIMBO_H), (cx, cy + CARIMBO_H)],
                     'BORDA_CELULA')
    rows = [('CLIENTE', obra), ('PAVIMENTO', pav.encode('ascii', 'replace').decode('ascii')), ('ELEMENTO', name)]
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
    files = sorted(json_dir.glob('V*_fundo.json'),
                   key=lambda p: int(''.join(filter(str.isdigit, p.stem.split('_')[0]))))
    if not files:
        print(f"ERRO: Nenhum V*_fundo.json em {json_dir}")
        sys.exit(1)

    print(f"  {len(files)} fundos de viga encontrados")

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
        face_pav = data.get('floor', pav)

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
            draw_fundo_face(msp, name, data, cell_ox, cell_oy, face_pav, max_cell_h=row_cell_h)
            draw_carimbo(msp, cell_ox, cell_oy, max_cell_w, obra_name, face_pav, i + 1, name)
            total_w = total_face_width(data['panels'])
            print(f"  {name}: total_w={total_w:.0f}cm espessura={float(data.get('total_width',15)):.0f}cm  [{col},{r}]")
        except Exception as e:
            print(f"  ERRO {name}: {e}")

    total_rows = len(row_heights)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out_path))
    print(f"\n  Salvo: {out_path}")
    print(f"  Grid: {len(files)} fundos — {cols} cols × {total_rows} linhas")


def main():
    parser = argparse.ArgumentParser(description='Gera DXF de fundos de vigas')
    parser.add_argument('--obra', default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    parser.add_argument('--pav', default='TÉRREO')
    parser.add_argument('--cols', type=int, default=COLS_DEFAULT)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    obra_name = obra_path.name
    json_dir  = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Fundo'

    if not json_dir.exists():
        print(f"ERRO: {json_dir} nao existe")
        sys.exit(1)

    out_path = Path(args.out) if args.out else \
        obra_path / 'Fase-5_Geracao_Scripts' / 'DXF_Vigas' / f'vigas_fundo_{obra_name}.dxf'

    print(f"\n=== GERAR DXF VIGAS FUNDO ===")
    print(f"  Obra  : {obra_name}")
    print(f"  JSON  : {json_dir}")
    print(f"  Output: {out_path}")
    print(f"  Cols  : {args.cols}\n")

    build_grid(json_dir, out_path, obra_name, args.pav, args.cols)


if __name__ == '__main__':
    main()
