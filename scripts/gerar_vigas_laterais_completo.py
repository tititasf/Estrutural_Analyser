#!/usr/bin/env python3
"""
gerar_vigas_laterais_completo.py
Gera DXF de faces laterais de vigas (A e B) no mesmo estilo visual dos pilares.

JSON: Fase-4_Sincronizacao/JSON_Vigas_Laterais/V{n}_{side}.json
Layout por célula: elevação horizontal dos painéis (esquerda→direita)
Escala: 1 unidade = 1cm

Uso:
  python scripts/gerar_vigas_laterais_completo.py
  python scripts/gerar_vigas_laterais_completo.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1 --cols 3
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
PANEL_THICK  = 2.2     # espessura compensado (nao desenhado na elevacao lateral)
SARR_W       = 2.2     # largura sarrafo
MARGIN_X     = 15.0    # margem esquerda/direita da célula
MARGIN_Y     = 5.0     # margem inferior (acima do carimbo)
CARIMBO_H    = 40.0    # altura do carimbo
HEADER_H     = 25.0    # espaço do header no topo
DIM_SPACE    = 30.0    # espaço abaixo da face p/ cotas de largura
COTA_RIGHT   = 15.0    # espaço à direita p/ cota de altura
GRID_GAP_X   = 20.0
GRID_GAP_Y   = 20.0
COLS_DEFAULT = 3

# Cores ACI
LAYERS = [
    ("Painéis",       200),   # violeta — outline painel
    ("SARR_2.2x7",    40),    # âmbar — sarrafo horizontal topo/base
    ("SARR_3.5x7",    81),    # pares de linhas verticais espaçadas
    ("NOMENCLATURA",   7),    # branco
    ("COTA",         241),    # pink — cotas
    ("Texto Seção",    7),    # branco — labels
    ("5",              5),    # azul — markers de pilar nos joints
    ("texto",           7),    # branco — MTEXT panel count labels (real ALIMONTI)
    ("CARIMBO",        9),
    ("BORDA_CELULA",   9),
    ("LABEL_ID",       3),
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


# ---------------------------------------------------------------------------
# HATCH helpers (mesmos bugs do ezdxf — fix pós-criação)
# ---------------------------------------------------------------------------
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
    h.dxf.color = color if color is not None else 256   # APÓS set_pattern_fill
    h.paths.add_polyline_path(pts, is_closed=True)
    return h


def draw_closed_poly(msp, pts, layer, color=None):
    attribs = {'layer': layer}
    if color is not None:
        attribs['color'] = color
    return msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)


# ---------------------------------------------------------------------------
# GEOMETRIA
# ---------------------------------------------------------------------------
def total_face_width(panels):
    return sum(float(p['width']) for p in panels)


def calc_cell_size(data):
    """Largura e altura da célula para uma face de viga lateral."""
    total_w = total_face_width(data['panels'])
    h = float(data.get('total_height', 120.0))
    cell_w = MARGIN_X * 2 + total_w + COTA_RIGHT + 10
    cell_h = CARIMBO_H + MARGIN_Y + h + DIM_SPACE + HEADER_H + 10
    return cell_w, cell_h


def calc_sarr_spacing(panel_w):
    """Posições X dos sarrafos dentro do painel (dividem horizontalmente)."""
    n = max(2, int(panel_w / 60) + 1)
    if n == 1:
        return [panel_w / 2.0]
    return [SARR_W / 2 + i * (panel_w - SARR_W) / (n - 1) for i in range(n)]


# ---------------------------------------------------------------------------
# DRAW: face lateral de uma viga
# ---------------------------------------------------------------------------
def draw_face(msp, name, data, cell_ox, cell_oy, pav, max_cell_h=None):
    h = float(data.get('total_height', 120.0))
    total_w = total_face_width(data['panels'])

    # Ancorar pelo TOPO da célula → elemento sempre no topo, espaço vazio fica abaixo
    used_h = max_cell_h if max_cell_h is not None else (CARIMBO_H + MARGIN_Y + DIM_SPACE + h + HEADER_H + 10)
    x0 = cell_ox + MARGIN_X
    y0 = cell_oy + used_h - HEADER_H - 5.0 - h

    # --- Header NOMENCLATURA ---
    pav_ascii = pav.encode('ascii', 'replace').decode('ascii')
    msp.add_text(
        f"{name} -- {pav_ascii}",
        dxfattribs={'layer': 'NOMENCLATURA', 'color': 256, 'height': 5.0,
                    'insert': (cell_ox + MARGIN_X, cell_oy + used_h - HEADER_H / 2)}
    )

    # --- Face: outline + sarrafos no estilo real ALIMONTI ---
    # Real LV: SEM hatch nos painéis de madeira
    # SARR_3.5x7 = pares de linhas VERTICAIS (ao longo da altura da face), espaçadas pela largura
    # SARR_2.2x7 = linha HORIZONTAL no topo da face (sarrafo de pressão superior)
    # Ref: V213-CONJUNTO-A-B.dxf — análise geométrica detalhada

    # Outline completo da face (LINE entities, não LWPOLYLINE — igual real)
    msp.add_line((x0, y0), (x0 + total_w, y0), dxfattribs={'layer': 'Painéis'})        # base
    msp.add_line((x0, y0 + h), (x0 + total_w, y0 + h), dxfattribs={'layer': 'Painéis'})  # topo
    msp.add_line((x0, y0), (x0, y0 + h), dxfattribs={'layer': 'Painéis'})              # esquerda
    msp.add_line((x0 + total_w, y0), (x0 + total_w, y0 + h), dxfattribs={'layer': 'Painéis'})  # direita

    # Divisórias de painéis (linhas verticais internas)
    xc = x0
    panel_x0s = []
    for panel in data['panels']:
        pw = float(panel['width'])
        if pw <= 0:
            continue
        panel_x0s.append((xc, pw))
        xc += pw
    for (px, pw) in panel_x0s[:-1]:
        msp.add_line((px + pw, y0), (px + pw, y0 + h), dxfattribs={'layer': 'Painéis'})

    # SARR_2.2x7: linha horizontal no topo (sarrafo de pressão, 2.2cm abaixo do topo)
    sarr_top_y = y0 + h - SARR_W
    msp.add_line((x0, sarr_top_y), (x0 + total_w, sarr_top_y), dxfattribs={'layer': 'SARR_2.2x7'})
    # Também na base
    msp.add_line((x0, y0 + SARR_W), (x0 + total_w, y0 + SARR_W), dxfattribs={'layer': 'SARR_2.2x7'})

    # SARR_3.5x7: pares de linhas VERTICAIS + conector horizontal no fundo
    # Cada par = 2 linhas verticais (3.5cm apart) + 1 linha horizontal na base (U-shape)
    # Ref: V213-CONJUNTO-A-B.dxf — análise geométrica confirmada
    sarr_spacing = 45.0  # ~45cm entre sarrafos
    sarr_count = max(2, int(total_w / sarr_spacing) + 1)
    sarr_xs = [1.75 + i * (total_w - 3.5) / (sarr_count - 1) for i in range(sarr_count)]
    for sx in sarr_xs:
        xl = x0 + sx - 1.75
        xr = x0 + sx + 1.75
        # 2 linhas verticais (lado esquerdo e direito do sarrafo)
        msp.add_line((xl, y0 + SARR_W), (xl, y0 + h - 1),
                     dxfattribs={'layer': 'SARR_3.5x7'})
        msp.add_line((xr, y0 + SARR_W), (xr, y0 + h - 1),
                     dxfattribs={'layer': 'SARR_3.5x7'})
        # Conector horizontal na base de cada sarrafo (U-shape)
        msp.add_line((xl, y0 + SARR_W), (xr, y0 + SARR_W),
                     dxfattribs={'layer': 'SARR_3.5x7'})

    # Labels de pilar nos joints (layer "5" = ACI 5 = blue, igual real ALIMONTI LV)
    pilar_labels = data.get('pilar_labels', [])
    # Pilar na extremidade esquerda
    p_left = pilar_labels[0] if pilar_labels else data.get('pilar_left', 'P1')
    # Pilar na extremidade direita
    p_right = pilar_labels[-1] if pilar_labels else data.get('pilar_right', 'P2')
    msp.add_text(str(p_left), dxfattribs={'layer': '5', 'color': 5, 'height': 12.0,
                                           'insert': (x0 - 3, y0 + h / 3)})
    msp.add_text(str(p_right), dxfattribs={'layer': '5', 'color': 5, 'height': 12.0,
                                            'insert': (x0 + total_w + 1, y0 + h / 3)})

    # Cotas de largura por painel (abaixo da face)
    dim_y = y0 - 15.0
    for (px, pw) in panel_x0s:
        dim = msp.add_linear_dim(
            base=(px + pw / 2, dim_y),
            p1=(px, y0),
            p2=(px + pw, y0),
            angle=0,
            dimstyle='FACE_DIM',
        )
        dim.render()

    # --- Cota de altura total (à direita) ---
    dim_x = x0 + total_w + 20.0
    dim_v = msp.add_linear_dim(
        base=(dim_x, y0 + h / 2),
        p1=(dim_x - 4, y0),
        p2=(dim_x - 4, y0 + h),
        angle=90,
        dimstyle='FACE_DIM',
        override={'dimtxt': 2.8, 'dimasz': 1.5, 'dimexo': 0.5, 'dimexe': 1.5},
    )
    dim_v.render()
    msp.add_text(
        f"TOTAL_W={total_w:.0f}cm",
        dxfattribs={'layer': 'COTA', 'color': 256, 'height': 3.0,
                    'insert': (x0, y0 + h + 5)}
    )

    # --- Label face ---
    msp.add_text(
        name,
        dxfattribs={'layer': 'Texto Seção', 'color': 256, 'height': 13.0,
                    'insert': (x0 + total_w / 2, y0 - 25)}
    ).set_placement((x0 + total_w / 2, y0 - 25), align=TextEntityAlignment.TOP_CENTER)


# ---------------------------------------------------------------------------
# CARIMBO
# ---------------------------------------------------------------------------
def draw_carimbo(msp, cell_ox, cell_oy, cell_w, obra, pav, num, name):
    cx, cy = cell_ox, cell_oy
    pts = [(cx, cy), (cx + cell_w, cy), (cx + cell_w, cy + CARIMBO_H), (cx, cy + CARIMBO_H)]
    draw_closed_poly(msp, pts, 'CARIMBO')
    rows = [
        ('CLIENTE', obra),
        ('PAVIMENTO', pav.encode('ascii', 'replace').decode('ascii')),
        ('ELEMENTO', name),
    ]
    row_h = CARIMBO_H / len(rows)
    for i, (label, val) in enumerate(rows):
        ry = cy + CARIMBO_H - (i + 1) * row_h
        msp.add_line((cx, ry), (cx + cell_w, ry), dxfattribs={'layer': 'CARIMBO'})
        msp.add_text(label + ':', dxfattribs={'layer': 'CARIMBO', 'height': 3.5, 'color': 9,
                                               'insert': (cx + 3, ry + row_h / 2)})
        msp.add_text(val, dxfattribs={'layer': 'CARIMBO', 'height': 4.0, 'color': 2,
                                       'insert': (cx + 35, ry + row_h / 2)})
    # Número da folha
    msp.add_text(f"{num:02d}", dxfattribs={'layer': 'CARIMBO', 'color': 3, 'height': 7.0,
                                            'insert': (cx + cell_w - 15, cy + 5)})
    # Borda
    draw_closed_poly(msp, [(cx, cy), (cx + cell_w, cy),
                             (cx + cell_w, cy + CARIMBO_H), (cx, cy + CARIMBO_H)],
                     'BORDA_CELULA')


# ---------------------------------------------------------------------------
# GRID
# ---------------------------------------------------------------------------
def build_grid(json_dir, out_path, obra_name, pav, cols, element_type='VIGA_LV'):
    # Ordenar: V101_A, V101_B, V102_A, ...
    files = sorted(json_dir.glob('V*.json'),
                   key=lambda p: (int(''.join(filter(str.isdigit, p.stem.split('_')[0]))),
                                  p.stem.split('_')[-1]))
    if not files:
        print(f"ERRO: Nenhum V*.json em {json_dir}")
        sys.exit(1)

    print(f"  {len(files)} faces de viga encontradas")

    doc, msp = setup_doc()

    # Pré-calcular dimensões de todas as células
    cell_sizes = []
    for jpath in files:
        data = json.loads(jpath.read_text(encoding='utf-8'))
        cw, ch = calc_cell_size(data)
        cell_sizes.append((cw, ch))

    max_cell_w = max(cw for cw, ch in cell_sizes)

    # Agrupar em linhas de `cols` elementos; altura da linha = max da linha
    n = len(files)
    row_heights = []
    for r in range(0, n, cols):
        row_hs = [cell_sizes[j][1] for j in range(r, min(r + cols, n))]
        row_heights.append(max(row_hs) + GRID_GAP_Y)

    # y_cursor acumulado: cada linha usa sua própria altura
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

        cell_ox = col * cell_w
        cell_oy = row_y_starts[r]

        # Borda célula (usa altura da linha, não max global)
        row_cell_h = row_h - GRID_GAP_Y
        draw_closed_poly(msp, [
            (cell_ox, cell_oy), (cell_ox + max_cell_w, cell_oy),
            (cell_ox + max_cell_w, cell_oy + row_cell_h), (cell_ox, cell_oy + row_cell_h),
        ], 'BORDA_CELULA')

        try:
            draw_face(msp, name, data, cell_ox, cell_oy, face_pav, max_cell_h=row_cell_h)
            draw_carimbo(msp, cell_ox, cell_oy, max_cell_w, obra_name, face_pav, i + 1, name)
            total_w = total_face_width(data['panels'])
            print(f"  {name}: total_w={total_w:.0f}cm h={float(data.get('total_height',120)):.0f}cm  [{col},{r}]")
        except Exception as e:
            print(f"  ERRO {name}: {e}")

    total_rows = len(row_heights)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out_path))
    print(f"\n  Salvo: {out_path}")
    print(f"  Grid: {len(files)} faces — {cols} cols × {total_rows} linhas")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='Gera DXF de vigas laterais')
    parser.add_argument('--obra', default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    parser.add_argument('--pav', default='TÉRREO')
    parser.add_argument('--cols', type=int, default=COLS_DEFAULT)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    obra_name = obra_path.name
    json_dir  = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Laterais'

    if not json_dir.exists():
        print(f"ERRO: {json_dir} nao existe")
        sys.exit(1)

    out_path = Path(args.out) if args.out else \
        obra_path / 'Fase-5_Geracao_Scripts' / 'DXF_Vigas' / f'vigas_laterais_{obra_name}.dxf'

    print(f"\n=== GERAR DXF VIGAS LATERAIS ===")
    print(f"  Obra  : {obra_name}")
    print(f"  JSON  : {json_dir}")
    print(f"  Output: {out_path}")
    print(f"  Cols  : {args.cols}\n")

    build_grid(json_dir, out_path, obra_name, args.pav, args.cols)


if __name__ == '__main__':
    main()
