#!/usr/bin/env python3
"""
gerar_pilares_completo.py
Gera DXF completo de pilares com: visao de cima, sarrafos, paineis, nivel markers, carimbo.
Identico ao formato do robot Bolt (ALIMONTI Paraiso).
Escala: 1 unidade = 1cm

Uso:
  python scripts/gerar_pilares_completo.py
  python scripts/gerar_pilares_completo.py --obra "Obra_TREINO_1" --pav "TERREO" --cols 5
  python scripts/gerar_pilares_completo.py --json-dir path/to/jsons --out path/to/output.dxf
"""
import argparse
import json
import math
import sys
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

# ---------------------------------------------------------------------------
# CONSTANTES GEOMETRICAS (cm)
# ---------------------------------------------------------------------------
PANEL_THICK = 2.2        # espessura compensado
SARR_W = 2.2             # largura sarrafo (secao)
SARR_H = 7.0             # altura sarrafo (secao)
CHAPA_SIZE = 2.0          # chapa de canto
GAP_FACES = 8.0           # gap horizontal entre faces
MARGIN_X = 15.0           # margem esquerda dentro da celula
MARGIN_Y = 5.0            # margem inferior acima do carimbo
CARIMBO_H = 40.0          # altura do carimbo
HEADER_H = 30.0           # altura do header no topo
VDC_GAP = 25.0            # gap entre elevacoes e visao de cima
VDC_EXTRA = 40.0          # altura extra da visao de cima
VDC_MARGIN = 10.0         # margem interna
COTA_OFFSET = 12.0        # offset das cotas a direita
GRID_GAP_X = 20.0         # gap horizontal entre celulas no grid
GRID_GAP_Y = 20.0         # gap vertical entre celulas no grid

FACES_ORDER = ['A', 'B', 'C', 'D']

# ---------------------------------------------------------------------------
# LAYERS (nome, ACI color)
# ---------------------------------------------------------------------------
LAYERS = [
    # Cores IDENTICAS ao real ALIMONTI (verificado por engenharia reversa)
    ("Painéis",         200),  # ACI 200 = violet — outlines dos painéis (LINE entities)
    ("SARR_2.2x7",      40),   # ACI 40 = amber — sarrafos verticais (LINE HIDDEN)
    ("SARR_3.5x7",      81),   # ACI 81 — sarrafos horizontais (LINE)
    ("CONCRETO",       251),   # ACI 251 = cinza — outline concreto (entity color=2 sobrepõe)
    ("CHAPA",            1),   # ACI 1 = vermelho
    ("Hachura",        251),   # ACI 251 = cinza médio — fill SOLID + ANSI31
    ("Madeira",        126),   # ACI 126 — painéis de madeira (LWPOLYLINE)
    ("Texto Seção",      7),   # ACI 7 = branco — labels seção
    ("NOMENCLATURA",     7),   # ACI 7 = branco — nome do pilar
    ("COTA",           241),   # ACI 241 = pink — dimensões (DIMENSION + LINE)
    ("Nível",          160),   # ACI 160 — linhas de nível (era 4/cyan, real=160)
    ("CARIMBO",        255),   # ACI 255 = branco claro — title block
    ("TEXTO_GERAL",      7),   # ACI 7
    ("texto",            7),   # ACI 7 — MTEXT labels (real ALIMONTI usa "texto" layer)
    ("BORDA_CELULA",     9),
    ("LABEL_ID",         3),
]


# ---------------------------------------------------------------------------
# SETUP
# ---------------------------------------------------------------------------
def setup_doc():
    """Cria documento ezdxf R2010 com layers e linetypes."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # HIDDEN linetype: period=0.375cm, dash=0.25cm, gap=0.125cm
    if 'HIDDEN' not in doc.linetypes:
        doc.linetypes.add('HIDDEN', pattern=[0.375, 0.25, -0.125])
    if 'DASHED' not in doc.linetypes:
        doc.linetypes.add('DASHED', pattern=[0.5, 0.25, -0.25])
    # DIVIDE2: dash-dot-dot (real ALIMONTI usa para linhas de Nível)
    # pattern: total_len, dash, gap, dot, gap, dot, gap
    if 'DIVIDE2' not in doc.linetypes:
        doc.linetypes.add('DIVIDE2', pattern=[0.25, 0.125, -0.0625, 0.0, -0.0625])

    for name, color in LAYERS:
        if name not in doc.layers:
            doc.layers.add(name, color=color)

    # Configurar text styles
    if 'STANDARD' not in doc.styles:
        doc.styles.new('STANDARD')

    # DIMSTYLE para cotas de face — baseado nos dimstyles reais ALIMONTI:
    # 'PAINEL': dimtxt=10mm, dimasz=3mm, clrd=4(cyan), clrt=240
    # Convertendo para escala cm (1unit=1cm): dividir por 10 → txt=1.0, asz=0.3
    # Mas mantemos valores maiores para legibilidade na escala do DXF
    if 'FACE_DIM' not in doc.dimstyles:
        ds = doc.dimstyles.new('FACE_DIM')
        ds.dxf.dimtxt  = 3.5   # altura do texto (cm) — legível na escala
        ds.dxf.dimasz  = 2.0   # tamanho da seta
        ds.dxf.dimexo  = 1.0   # offset extensão
        ds.dxf.dimexe  = 2.0   # extensão além da seta
        ds.dxf.dimgap  = 1.0   # gap texto/linha
        ds.dxf.dimdec  = 0     # sem casas decimais
        ds.dxf.dimrnd  = 1.0   # arredondar a 1cm
        ds.dxf.dimclrd = 4     # ACI 4 = CYAN (igual real ALIMONTI dimstyle PAINEL)
        ds.dxf.dimclre = 4     # cyan — linhas de extensão
        ds.dxf.dimclrt = 4     # cyan — texto das cotas

    return doc, msp


# ---------------------------------------------------------------------------
# HELPERS GEOMETRICOS
# ---------------------------------------------------------------------------
def face_dims(data, face):
    """Retorna (face_width, h1, h2, h3) para uma face."""
    b = max(data['comprimento'], data['largura'])
    h = min(data['comprimento'], data['largura'])
    w = b if face in ('A', 'C') else h
    h1 = data.get(f'h1_{face}', 0) or 0
    h2 = data.get(f'h2_{face}', 0) or 0
    h3 = data.get(f'h3_{face}', 0) or 0
    return w, h1, h2, h3


def calc_sarr_positions(face_width):
    """Calcula posicoes X dos sarrafos dentro de uma face (cm)."""
    n = max(2, int(face_width / 18) + 1)
    if n == 1:
        return [face_width / 2.0]
    positions = []
    for i in range(n):
        x = SARR_W / 2.0 + i * (face_width - SARR_W) / (n - 1)
        positions.append(x)
    return positions


def calc_vdc_size(data):
    """Calcula dimensoes da visao de cima (total incluindo paineis e sarrafos)."""
    b = max(data['comprimento'], data['largura'])
    h_small = min(data['comprimento'], data['largura'])
    vdc_w = b + 2 * PANEL_THICK + 2 * SARR_H + 2 * CHAPA_SIZE + 10
    vdc_h = h_small + 2 * PANEL_THICK + 2 * SARR_H + 2 * CHAPA_SIZE + VDC_EXTRA
    return vdc_w, vdc_h


def calc_cell_size(data):
    """Calcula largura e altura da celula para um pilar.
    Layout: VDC a ESQUERDA das faces (igual ao ALIMONTI real)."""
    b = max(data['comprimento'], data['largura'])
    h_small = min(data['comprimento'], data['largura'])
    altura = data.get('altura', 280)

    # Largura: VDC + gap + 4 faces (A=b, B=h, C=b, D=h) + gaps + margem + cotas
    vdc_w, _ = calc_vdc_size(data)
    total_faces_w = b + GAP_FACES + h_small + GAP_FACES + b + GAP_FACES + h_small
    cell_w = MARGIN_X + vdc_w + VDC_GAP + total_faces_w + COTA_OFFSET + MARGIN_X + 10

    # Altura: carimbo + margin + max(faces, vdc) + header
    max_h_total = 0
    for face in FACES_ORDER:
        _, h1, h2, h3 = face_dims(data, face)
        ht = h1 + h2 + h3
        if ht > max_h_total:
            max_h_total = ht
    if max_h_total == 0:
        max_h_total = altura

    _, vdc_h = calc_vdc_size(data)
    content_h = max(max_h_total + 40, vdc_h + 20)
    cell_h = CARIMBO_H + MARGIN_Y + content_h + HEADER_H + 10

    return cell_w, cell_h


# ---------------------------------------------------------------------------
# DRAW: HATCH SOLID
# ---------------------------------------------------------------------------
def draw_hatch_solid(msp, pts, layer, color=None):
    """Desenha HATCH SOLID — byLayer color (256).
    NOTA: ezdxf add_hatch() ignora color em dxfattribs (sempre fica 7=white).
    Workaround: setar hatch.dxf.color APOS a criacao."""
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    hatch.dxf.color = color if color is not None else 256  # 256=byLayer
    hatch.paths.add_polyline_path(pts, is_closed=True)
    return hatch


def draw_hatch_pattern(msp, pts, layer, color=None, pattern='ANSI31', scale=0.5, angle=270.0):
    """Desenha HATCH com padrao diagonal (ANSI31 = madeira/compensado no ALIMONTI).
    NOTA: ezdxf add_hatch() ignora color em dxfattribs (sempre fica 7=white).
    Workaround: setar hatch.dxf.color APOS a criacao."""
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    try:
        hatch.set_pattern_fill(pattern, scale=scale, angle=angle)
    except Exception:
        hatch.dxf.solid_fill = 1
    hatch.dxf.color = color if color is not None else 256  # 256=byLayer — APOS set_pattern_fill
    hatch.paths.add_polyline_path(pts, is_closed=True)
    return hatch


# ---------------------------------------------------------------------------
# DRAW: LWPOLYLINE fechado
# ---------------------------------------------------------------------------
def draw_closed_poly(msp, pts, layer, color=None):
    """Desenha LWPOLYLINE fechado."""
    attribs = {'layer': layer}
    if color is not None:
        attribs['color'] = color
    poly = msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)
    return poly


# ---------------------------------------------------------------------------
# DRAW: VISAO DE CIMA (corte transversal horizontal)
# ---------------------------------------------------------------------------
def draw_visao_de_cima(msp, data, cx, y_vdc):
    """
    Desenha corte transversal horizontal acima das faces.
    cx = centro-x da visao de cima
    y_vdc = base-y da visao de cima
    """
    b = max(data['comprimento'], data['largura'])
    h = min(data['comprimento'], data['largura'])

    # Centro da visao de cima
    vdc_cx = cx
    vdc_cy = y_vdc + VDC_EXTRA / 2 + SARR_H + PANEL_THICK

    # Concreto (nucleo)
    concrete_x0 = vdc_cx - b / 2
    concrete_y0 = vdc_cy - h / 2
    concrete_pts = [
        (concrete_x0, concrete_y0),
        (concrete_x0 + b, concrete_y0),
        (concrete_x0 + b, concrete_y0 + h),
        (concrete_x0, concrete_y0 + h),
    ]
    draw_closed_poly(msp, concrete_pts, 'CONCRETO', color=2)
    # Hatch concreto: AR-CONC igual ao real ALIMONTI (layer COTA, scale=0.03)
    draw_hatch_pattern(msp, concrete_pts, 'COTA', pattern='AR-CONC', scale=0.03, angle=0.0)

    # Paineis (4 lados, espessura PANEL_THICK) — byLayer = ACI 200 (violet, igual real)
    # Painel inferior (face A - comprimento)
    panel_bottom = [
        (concrete_x0, concrete_y0 - PANEL_THICK),
        (concrete_x0 + b, concrete_y0 - PANEL_THICK),
        (concrete_x0 + b, concrete_y0),
        (concrete_x0, concrete_y0),
    ]
    draw_closed_poly(msp, panel_bottom, 'Painéis')
    draw_hatch_pattern(msp, panel_bottom, 'Hachura', scale=0.5, angle=270.0)

    # Painel superior (face C - comprimento)
    panel_top = [
        (concrete_x0, concrete_y0 + h),
        (concrete_x0 + b, concrete_y0 + h),
        (concrete_x0 + b, concrete_y0 + h + PANEL_THICK),
        (concrete_x0, concrete_y0 + h + PANEL_THICK),
    ]
    draw_closed_poly(msp, panel_top, 'Painéis')
    draw_hatch_pattern(msp, panel_top, 'Hachura', scale=0.5, angle=270.0)

    # Painel esquerdo (face D - largura)
    panel_left = [
        (concrete_x0 - PANEL_THICK, concrete_y0),
        (concrete_x0, concrete_y0),
        (concrete_x0, concrete_y0 + h),
        (concrete_x0 - PANEL_THICK, concrete_y0 + h),
    ]
    draw_closed_poly(msp, panel_left, 'Painéis')
    draw_hatch_pattern(msp, panel_left, 'Hachura', scale=0.5, angle=270.0)

    # Painel direito (face B - largura)
    panel_right = [
        (concrete_x0 + b, concrete_y0),
        (concrete_x0 + b + PANEL_THICK, concrete_y0),
        (concrete_x0 + b + PANEL_THICK, concrete_y0 + h),
        (concrete_x0 + b, concrete_y0 + h),
    ]
    draw_closed_poly(msp, panel_right, 'Painéis')
    draw_hatch_pattern(msp, panel_right, 'Hachura', scale=0.5, angle=270.0)

    # Sarrafos em secao (pequenos retangulos SARR_W x SARR_H em frente aos paineis)
    # byLayer = ACI 40 (amber), com ANSI31 cross-section (scale=0.5, angle=270)
    # Face A (inferior): sarrafos horizontais abaixo do painel inferior
    sarr_positions_b = calc_sarr_positions(b)
    for sx in sarr_positions_b:
        rx = concrete_x0 + sx - SARR_W / 2
        ry = concrete_y0 - PANEL_THICK - SARR_H
        sarr_pts = [
            (rx, ry), (rx + SARR_W, ry),
            (rx + SARR_W, ry + SARR_H), (rx, ry + SARR_H),
        ]
        draw_closed_poly(msp, sarr_pts, 'SARR_2.2x7')
        draw_hatch_pattern(msp, sarr_pts, 'SARR_2.2x7', scale=0.5, angle=270.0)

    # Face C (superior): sarrafos acima do painel superior
    for sx in sarr_positions_b:
        rx = concrete_x0 + sx - SARR_W / 2
        ry = concrete_y0 + h + PANEL_THICK
        sarr_pts = [
            (rx, ry), (rx + SARR_W, ry),
            (rx + SARR_W, ry + SARR_H), (rx, ry + SARR_H),
        ]
        draw_closed_poly(msp, sarr_pts, 'SARR_2.2x7')
        draw_hatch_pattern(msp, sarr_pts, 'SARR_2.2x7', scale=0.5, angle=270.0)

    # Face D (esquerdo): sarrafos a esquerda do painel esquerdo
    sarr_positions_h = calc_sarr_positions(h)
    for sy in sarr_positions_h:
        rx = concrete_x0 - PANEL_THICK - SARR_H
        ry = concrete_y0 + sy - SARR_W / 2
        sarr_pts = [
            (rx, ry), (rx + SARR_H, ry),
            (rx + SARR_H, ry + SARR_W), (rx, ry + SARR_W),
        ]
        draw_closed_poly(msp, sarr_pts, 'SARR_2.2x7')
        draw_hatch_pattern(msp, sarr_pts, 'SARR_2.2x7', scale=0.5, angle=270.0)

    # Face B (direito): sarrafos a direita do painel direito
    for sy in sarr_positions_h:
        rx = concrete_x0 + b + PANEL_THICK
        ry = concrete_y0 + sy - SARR_W / 2
        sarr_pts = [
            (rx, ry), (rx + SARR_H, ry),
            (rx + SARR_H, ry + SARR_W), (rx, ry + SARR_W),
        ]
        draw_closed_poly(msp, sarr_pts, 'SARR_2.2x7')
        draw_hatch_pattern(msp, sarr_pts, 'SARR_2.2x7', scale=0.5, angle=270.0)

    # CHAPA nos 4 cantos (2x2cm)
    corners = [
        (concrete_x0 - PANEL_THICK - CHAPA_SIZE, concrete_y0 - PANEL_THICK - CHAPA_SIZE),
        (concrete_x0 + b + PANEL_THICK, concrete_y0 - PANEL_THICK - CHAPA_SIZE),
        (concrete_x0 + b + PANEL_THICK, concrete_y0 + h + PANEL_THICK),
        (concrete_x0 - PANEL_THICK - CHAPA_SIZE, concrete_y0 + h + PANEL_THICK),
    ]
    for (cx_ch, cy_ch) in corners:
        chapa_pts = [
            (cx_ch, cy_ch), (cx_ch + CHAPA_SIZE, cy_ch),
            (cx_ch + CHAPA_SIZE, cy_ch + CHAPA_SIZE), (cx_ch, cy_ch + CHAPA_SIZE),
        ]
        draw_closed_poly(msp, chapa_pts, 'CHAPA', color=1)
        draw_hatch_solid(msp, chapa_pts, 'CHAPA', color=1)

    # Labels A/B/C/D nas faces da VDC (igual ao real ALIMONTI)
    txt_h = min(4.0, h / 4.0, b / 4.0)  # tamanho proporcional
    # Face A (inferior) — centralizado abaixo do painel
    a_cx = vdc_cx
    a_cy = concrete_y0 - PANEL_THICK - SARR_H - 3
    msp.add_text("A", dxfattribs={'layer': 'Texto Seção', 'color': 256, 'height': txt_h}).set_placement(
        (a_cx, a_cy), align=TextEntityAlignment.TOP_CENTER)
    # Face C (superior)
    c_cy = concrete_y0 + h + PANEL_THICK + SARR_H + 3
    msp.add_text("C", dxfattribs={'layer': 'Texto Seção', 'color': 256, 'height': txt_h}).set_placement(
        (a_cx, c_cy), align=TextEntityAlignment.BOTTOM_CENTER)
    # Face D (esquerdo)
    d_cx = concrete_x0 - PANEL_THICK - SARR_H - 3
    d_cy = vdc_cy
    msp.add_text("D", dxfattribs={'layer': 'Texto Seção', 'color': 256, 'height': txt_h}).set_placement(
        (d_cx, d_cy), align=TextEntityAlignment.MIDDLE_RIGHT)
    # Face B (direito)
    bx = concrete_x0 + b + PANEL_THICK + SARR_H + 3
    msp.add_text("B", dxfattribs={'layer': 'Texto Seção', 'color': 256, 'height': txt_h}).set_placement(
        (bx, d_cy), align=TextEntityAlignment.MIDDLE_LEFT)

    # Cota dimensao B x H abaixo da VDC
    cota_y = concrete_y0 - PANEL_THICK - SARR_H - txt_h - 8
    b_val = data.get('comprimento', b)
    h_val = data.get('largura', h)
    msp.add_text(
        f"{b_val:.0f}x{h_val:.0f}cm",
        dxfattribs={'layer': 'Cota Secao (2x)', 'color': 4, 'height': txt_h * 0.85}
    ).set_placement((vdc_cx, cota_y), align=TextEntityAlignment.TOP_CENTER)

    # Label "VISAO DE CIMA" no topo
    label_y = concrete_y0 + h + PANEL_THICK + SARR_H + txt_h + 8
    msp.add_text(
        "VISAO DE CIMA",
        dxfattribs={'layer': 'Texto Seção', 'color': 256, 'height': min(4.0, txt_h)},
    ).set_placement((vdc_cx, label_y), align=TextEntityAlignment.BOTTOM_CENTER)


# ---------------------------------------------------------------------------
# DRAW: FACE DE ELEVACAO
# ---------------------------------------------------------------------------
def draw_face_elevation(msp, pid, face, face_w, h1, h2, h3, x0, y0):
    """
    Desenha uma face de elevacao com todos os detalhes.
    x0, y0 = canto inferior esquerdo da face.
    """
    h_total = h1 + h2 + h3
    if h_total <= 0:
        return

    # --- Corpo principal (h1 + h2): ANSI31 only (real ALIMONTI: solid=0, pattern=ANSI31) ---
    h_body = h1 + h2
    if h_body > 0:
        body_pts = [
            (x0, y0), (x0 + face_w, y0),
            (x0 + face_w, y0 + h_body), (x0, y0 + h_body),
        ]
        draw_closed_poly(msp, body_pts, 'Painéis')
        draw_hatch_pattern(msp, body_pts, 'Hachura', scale=5.0, angle=0.0)

    # --- Painel topo (h3): secao de laje ---
    if h3 > 0:
        top_y0 = y0 + h_body
        top_pts = [
            (x0, top_y0), (x0 + face_w, top_y0),
            (x0 + face_w, top_y0 + h3), (x0, top_y0 + h3),
        ]
        draw_closed_poly(msp, top_pts, 'Painéis')
        draw_hatch_pattern(msp, top_pts, 'Hachura', scale=2.5, angle=0.0)
        # Linha dupla na transicao h2/h3
        msp.add_line((x0, top_y0 - 2), (x0 + face_w, top_y0 - 2),
                     dxfattribs={'layer': 'Painéis'})

    # --- Divisao h1/h2: linha horizontal em y = y0 + h1 ---
    if h1 > 0 and h2 > 0:
        div_y = y0 + h1
        msp.add_line(
            (x0, div_y), (x0 + face_w, div_y),
            dxfattribs={'layer': 'Painéis'}
        )

    # --- Sarrafos verticais (HIDDEN, ltscale=30 — igual ao real ALIMONTI) ---
    sarr_xs = calc_sarr_positions(face_w)
    for sx in sarr_xs:
        line_x = x0 + sx
        msp.add_line(
            (line_x, y0), (line_x, y0 + h_total),
            dxfattribs={
                'layer': 'SARR_2.2x7',   # ACI 40 = amber (#ffbf00)
                'linetype': 'HIDDEN',     # HIDDEN tracejado
                'ltscale': 30.0,          # ltscale per-entidade = 30 (igual ao real)
            }
        )

    # --- Label da face (h=13 igual real ALIMONTI "P11.A") ---
    label_text = f"{pid}.{face}"
    label_x = x0 + face_w / 2
    label_y = y0 - 8
    msp.add_text(
        label_text,
        dxfattribs={
            'layer': 'Texto Seção',
            'color': 256,
            'height': 13.0,   # Real ALIMONTI: h=13.0 para label face
            'insert': (label_x, label_y),
        }
    )

    # --- MTEXT "SP" abaixo de cada face (real ALIMONTI: Tahoma, color=4 cyan, h=7.5) ---
    # Ref: P11-ABCD.dxf — 4 MTEXT "SP" na layer "texto", color=2 (yellow)
    sp_x = x0 + face_w / 2
    sp_y = label_y - 15.0
    msp.add_mtext(
        '{\\fTahoma|b0|i0|c0|p34;\\C4;SP}',
        dxfattribs={
            'layer': 'TEXTO_GERAL',
            'color': 4,
            'char_height': 7.5,
            'insert': (sp_x, sp_y),
            'attachment_point': 5,  # middle center
        }
    )

    # --- COTA horizontal: largura da face (DIMENSION entity) ---
    # Posicionada abaixo do label, mostra face_w em cm
    dim_y = y0 - 20.0   # linha de cota 20cm abaixo da base da face
    dim = msp.add_linear_dim(
        base=(x0 + face_w / 2, dim_y),
        p1=(x0, y0),
        p2=(x0 + face_w, y0),
        angle=0,        # horizontal
        dimstyle='FACE_DIM',
    )
    dim.render()

    # --- COTAS horizontais: espacamento entre sarrafos (acima da face) ---
    # Posicionadas ACIMA do topo da face — linhas de extensao sobem do topo para cima,
    # sem atravessar o painel (que causava visual poluido)
    sarr_xs = calc_sarr_positions(face_w)
    if len(sarr_xs) >= 2:
        base_y = y0 + h_total + 15.0   # linha de cota 15cm acima do topo da face
        for i in range(len(sarr_xs) - 1):
            sx1 = x0 + sarr_xs[i]
            sx2 = x0 + sarr_xs[i + 1]
            mid_x = (sx1 + sx2) / 2
            dim_v = msp.add_linear_dim(
                base=(mid_x, base_y),
                p1=(sx1, y0 + h_total),
                p2=(sx2, y0 + h_total),
                angle=0,    # horizontal: mede distancia horizontal entre sarrafos
                dimstyle='FACE_DIM',
            )
            dim_v.render()


# ---------------------------------------------------------------------------
# DRAW: COTAS DE ALTURA
# ---------------------------------------------------------------------------
def draw_cotas(msp, h1, h2, h3, x_cota, y_base):
    """Cotas de altura a direita das faces — usando DIMENSION entities."""
    h_total = h1 + h2 + h3
    if h_total <= 0:
        return

    # Cotas verticais usando DIMENSION entities (igual ao real ALIMONTI)
    # x_cota = posicao X da linha de cota (a direita da ultima face)
    dim_x = x_cota + 4.0   # deslocar um pouco para a direita

    marks = []
    if h1 > 0:
        marks.append((y_base,           y_base + h1,           f"h1={h1:.0f}"))
    if h2 > 0:
        marks.append((y_base + h1,      y_base + h1 + h2,      f"h2={h2:.0f}"))
    if h3 > 0:
        marks.append((y_base + h1 + h2, y_base + h1 + h2 + h3, f"h3={h3:.0f}"))

    for (y_bot, y_top, prefix) in marks:
        mid_y = (y_bot + y_top) / 2
        seg_h = y_top - y_bot
        # DIMENSION vertical: angle=90 mede distancia vertical entre p1 e p2
        dim_v = msp.add_linear_dim(
            base=(dim_x, mid_y),
            p1=(dim_x - 4, y_bot),   # ponto inferior (mesma x, diferente y)
            p2=(dim_x - 4, y_top),   # ponto superior
            angle=90,                # vertical
            dimstyle='FACE_DIM',
            override={
                'dimtxt': 2.8,
                'dimasz': 1.5,
                'dimexo': 0.5,
                'dimexe': 1.5,
            }
        )
        dim_v.render()

    # TOTAL acima de tudo (texto simples — nao e DIMENSION pois e apenas totalizador)
    msp.add_text(
        f"TOTAL={h_total:.0f}",
        dxfattribs={
            'layer': 'COTA',
            'color': 241,
            'height': 3.5,
            'insert': (dim_x + 2, y_base + h_total + 3),
        }
    )


# ---------------------------------------------------------------------------
# DRAW: NIVEL MARKERS (chegada e saida — linhas ciano como no ALIMONTI)
# ---------------------------------------------------------------------------
def draw_nivel_markers(msp, x_start, x_end, y_base, h_total, h_saida_offset):
    """
    Duas linhas ciano nos nivels de chegada e saida, com label e simbolo triangular.
    Sem grades intermediarias (o real ALIMONTI nao tem).
    """
    if h_total <= 0:
        return

    y_saida = y_base + h_saida_offset if h_saida_offset > 0 else y_base + h_total

    for (y_lbl, lbl, pav_lbl) in [
        (y_base,   "NIVEL DE CHEGADA", "1o PAV."),
        (y_saida,  "NIVEL DE SAIDA",   "2o PAV."),
    ]:
        # Linha horizontal DIVIDE2 (real ALIMONTI: layer Nível usa DIVIDE2 linetype)
        msp.add_line(
            (x_start - 8, y_lbl), (x_end + 8, y_lbl),
            dxfattribs={'layer': 'Nível', 'color': 256, 'linetype': 'DIVIDE2', 'ltscale': 40.0}
        )
        # Simbolo triangular (seta descendente: 3 linhas formando V invertido)
        tri_x = x_start - 6
        msp.add_line((tri_x - 3, y_lbl + 5), (tri_x, y_lbl),
                     dxfattribs={'layer': 'Nível', 'color': 256})
        msp.add_line((tri_x + 3, y_lbl + 5), (tri_x, y_lbl),
                     dxfattribs={'layer': 'Nível', 'color': 256})
        # Label do pavimento
        msp.add_text(
            pav_lbl,
            dxfattribs={
                'layer': 'Nível',
                'color': 256,
                'height': 4.0,
                'insert': (tri_x + 5, y_lbl + 1),
            }
        )


# ---------------------------------------------------------------------------
# DRAW: CARIMBO / TITLE BLOCK
# ---------------------------------------------------------------------------
def draw_carimbo(msp, cell_ox, cell_oy, cell_w, obra, pav, num, pid):
    """Title block no rodape da celula."""
    cx = cell_ox
    cy = cell_oy
    cw = cell_w
    ch = CARIMBO_H

    # Borda do carimbo
    carimbo_pts = [
        (cx, cy), (cx + cw, cy),
        (cx + cw, cy + ch), (cx, cy + ch),
    ]
    draw_closed_poly(msp, carimbo_pts, 'CARIMBO', color=40)

    # Linhas divisorias internas (3 linhas horizontais)
    for frac in [0.25, 0.5, 0.75]:
        dy = cy + ch * frac
        msp.add_line(
            (cx, dy), (cx + cw, dy),
            dxfattribs={'layer': 'CARIMBO', 'color': 40}
        )

    # Linha vertical central
    mid_x = cx + cw * 0.35
    msp.add_line(
        (mid_x, cy), (mid_x, cy + ch),
        dxfattribs={'layer': 'CARIMBO', 'color': 40}
    )

    # Textos do carimbo
    text_h = 3.0
    text_x_label = cx + 3
    text_x_value = mid_x + 3

    rows = [
        ("CLIENTE:", "ALIMONTI", 0.875),
        ("OBRA:", obra, 0.625),
        ("PAVIMENTO:", pav, 0.375),
        ("PROJETO:", "PILARES", 0.125),
    ]

    for (lbl, val, frac) in rows:
        ty = cy + ch * frac
        msp.add_text(
            lbl,
            dxfattribs={
                'layer': 'CARIMBO',
                'color': 9,
                'height': text_h,
                'insert': (text_x_label, ty),
            }
        )
        msp.add_text(
            val,
            dxfattribs={
                'layer': 'TEXTO_GERAL',
                'color': 2,
                'height': text_h,
                'insert': (text_x_value, ty),
            }
        )

    # Numero da celula (grande, canto direito inferior)
    num_x = cx + cw - 15
    num_y = cy + 5
    msp.add_text(
        str(num).zfill(2),
        dxfattribs={
            'layer': 'LABEL_ID',
            'color': 3,
            'height': 8.0,
            'insert': (num_x, num_y),
        }
    )


# ---------------------------------------------------------------------------
# DRAW: HEADER
# ---------------------------------------------------------------------------
def draw_header(msp, data, pid, cell_ox, cell_oy, cell_w, cell_h):
    """Header no topo da celula com PD, nivel saida, nivel chegada."""
    hx = cell_ox + cell_w - 10
    hy = cell_oy + cell_h - 5

    pav = data.get('pavimento', 'TERREO')
    pd = data.get('altura', 280)
    nivel_saida = data.get('nivel_saida', 280)
    nivel_chegada = data.get('nivel_chegada', 0)

    header_lines = [
        f"{pav} - PD: {pd:.2f}",
        f"NIVEL DE SAIDA: {nivel_saida:.2f}",
        f"NIVEL DE CHEGADA: {nivel_chegada:.2f}",
    ]

    for i, line in enumerate(header_lines):
        msp.add_text(
            line,
            dxfattribs={
                'layer': 'TEXTO_GERAL',
                'color': 2,
                'height': 3.0,
            }
        ).set_placement((hx, hy - i * 5), align=TextEntityAlignment.RIGHT)

    # Nome do pilar em grande
    name_x = cell_ox + MARGIN_X + 5
    name_y = cell_oy + cell_h - 12
    msp.add_text(
        pid,
        dxfattribs={
            'layer': 'NOMENCLATURA',
            'color': 1,
            'height': 10.0,
            'insert': (name_x, name_y),
        }
    )


# ---------------------------------------------------------------------------
# DRAW: PILAR COMPLETO (orquestrador)
# ---------------------------------------------------------------------------
def draw_pilar_completo(msp, pid, data, cell_ox, cell_oy, obra, pav, num):
    """Orquestra todo o desenho do pilar na celula."""
    cell_w, cell_h = calc_cell_size(data)

    b = max(data['comprimento'], data['largura'])
    h_small = min(data['comprimento'], data['largura'])

    # 1. BORDA DA CELULA
    border_pts = [
        (cell_ox, cell_oy), (cell_ox + cell_w, cell_oy),
        (cell_ox + cell_w, cell_oy + cell_h), (cell_ox, cell_oy + cell_h),
    ]
    draw_closed_poly(msp, border_pts, 'BORDA_CELULA', color=9)

    # 2. HEADER
    draw_header(msp, data, pid, cell_ox, cell_oy, cell_w, cell_h)

    # 3. CALCULAR POSICAO BASE DAS FACES (acima do carimbo + margem)
    faces_y_base = cell_oy + CARIMBO_H + MARGIN_Y + 10

    # Calcular max_h_total para nivel markers e layout
    max_h_total = 0
    for face in FACES_ORDER:
        _, fh1, fh2, fh3 = face_dims(data, face)
        ht = fh1 + fh2 + fh3
        if ht > max_h_total:
            max_h_total = ht

    # VDC (visao de cima) a ESQUERDA das faces — igual ao ALIMONTI real
    vdc_w, vdc_h = calc_vdc_size(data)
    vdc_cx = cell_ox + MARGIN_X + vdc_w / 2
    # VDC alinhada ao topo das faces
    vdc_y = faces_y_base + max_h_total - vdc_h + VDC_EXTRA / 2 + SARR_H + PANEL_THICK + 10

    # Posicao X de cada face (apos VDC + gap)
    faces_x_start = cell_ox + MARGIN_X + vdc_w + VDC_GAP

    face_positions = []  # [(face_letter, face_width, x0, fh1, fh2, fh3)]
    current_x = faces_x_start

    for face in FACES_ORDER:
        fw, fh1, fh2, fh3 = face_dims(data, face)
        face_positions.append((face, fw, current_x, fh1, fh2, fh3))
        current_x += fw + GAP_FACES

    # 4. DESENHAR VDC
    draw_visao_de_cima(msp, data, vdc_cx, vdc_y)

    # 5. DESENHAR CADA FACE
    for (face, fw, fx, fh1, fh2, fh3) in face_positions:
        draw_face_elevation(msp, pid, face, fw, fh1, fh2, fh3, fx, faces_y_base)

    # 6. COTAS a direita da ultima face
    last_face = face_positions[-1]
    _, last_fw, last_fx, last_h1, last_h2, last_h3 = last_face
    cota_x = last_fx + last_fw + 8
    draw_cotas(msp, last_h1, last_h2, last_h3, cota_x, faces_y_base)

    # 7. NIVEL MARKERS cobrindo VDC + faces
    nivel_x_start = cell_ox + MARGIN_X - 5
    nivel_x_end = last_fx + last_fw + 5
    h1_a = float(data.get('h1_A', 0) or 0)
    h2_a = float(data.get('h2_A', 0) or 0)
    h_saida = h1_a + h2_a  # transicao h2->h3 = nivel de saida
    draw_nivel_markers(msp, nivel_x_start, nivel_x_end, faces_y_base, max_h_total, h_saida)

    # 8. CARIMBO
    draw_carimbo(msp, cell_ox, cell_oy, cell_w, obra, pav, num, pid)

    return cell_w, cell_h


# ---------------------------------------------------------------------------
# BUILD COMBINED
# ---------------------------------------------------------------------------
def build_combined(json_dir, out_path, obra, pav, cols=5):
    """Grid de todos os pilares."""
    json_dir = Path(json_dir)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Carregar todos os JSONs
    json_files = sorted(json_dir.glob('P*.json'), key=lambda p: _sort_key(p.stem))
    if not json_files:
        print(f"ERRO: Nenhum JSON encontrado em {json_dir}")
        sys.exit(1)

    pilares = []
    for jf in json_files:
        with open(jf, 'r', encoding='utf-8') as f:
            data = json.load(f)
        pid = data.get('nome', jf.stem)
        pilares.append((pid, data))

    print(f"Carregados {len(pilares)} pilares de {json_dir}")

    doc, msp = setup_doc()

    # Pre-calcular tamanhos de cada celula
    cell_sizes = []
    for pid, data in pilares:
        cw, ch = calc_cell_size(data)
        cell_sizes.append((cw, ch))

    # Layout grid: agrupar em linhas de 'cols' colunas
    # Calcular max width por coluna e max height por linha
    rows_data = []
    for i in range(0, len(pilares), cols):
        row_slice = list(range(i, min(i + cols, len(pilares))))
        rows_data.append(row_slice)

    # Calcular dimensoes de cada linha
    row_heights = []
    col_widths = [0.0] * cols
    for row_indices in rows_data:
        max_h = 0
        for j, idx in enumerate(row_indices):
            cw, ch = cell_sizes[idx]
            if cw > col_widths[j]:
                col_widths[j] = cw
            if ch > max_h:
                max_h = ch
        row_heights.append(max_h)

    # Posicionar cada celula
    current_y = 0.0
    cell_num = 1

    for row_idx, row_indices in enumerate(rows_data):
        current_x = 0.0
        row_h = row_heights[row_idx]

        for j, idx in enumerate(row_indices):
            pid, data = pilares[idx]
            cell_ox = current_x
            cell_oy = current_y

            actual_w, actual_h = draw_pilar_completo(
                msp, pid, data, cell_ox, cell_oy, obra, pav, cell_num
            )

            current_x += col_widths[j] + GRID_GAP_X
            cell_num += 1

        current_y += row_h + GRID_GAP_Y

    # Salvar
    doc.saveas(str(out_path))
    print(f"DXF salvo: {out_path}")
    print(f"  Pilares: {len(pilares)}")
    print(f"  Grid: {len(rows_data)} linhas x {cols} colunas")
    print(f"  Layers: {', '.join(name for name, _ in LAYERS)}")

    return str(out_path), len(pilares)


def _sort_key(stem):
    """Extrai numero para ordenacao: P11 -> 11, P101 -> 101."""
    digits = ''.join(c for c in stem if c.isdigit())
    return int(digits) if digits else 0


# ---------------------------------------------------------------------------
# RENDER PNG (opcional, para verificacao visual)
# ---------------------------------------------------------------------------
def render_png(dxf_path, png_path, bg='#1a1a1a'):
    """Renderiza DXF para PNG usando matplotlib backend do ezdxf.
    Usa fundo escuro (bg='#1a1a1a') para replicar aparencia de CAD profissional."""
    try:
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        fig = plt.figure(figsize=(40, 30))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor(bg)
        fig.patch.set_facecolor(bg)

        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(msp)

        ax.set_aspect('equal')
        fig.savefig(str(png_path), dpi=100, bbox_inches='tight', facecolor=bg)
        plt.close(fig)
        print(f"PNG salvo: {png_path}")
        return True
    except ImportError as e:
        print(f"AVISO: render PNG nao disponivel ({e})")
        print("  Instale: pip install ezdxf[draw]")
        return False
    except Exception as e:
        print(f"AVISO: render PNG via RenderContext falhou: {e}")
        # Fallback: render simples com matplotlib puro
        return render_png_fallback(dxf_path, png_path)


def render_png_fallback(dxf_path, png_path):
    """Fallback: render simples iterando entidades do DXF."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        fig, ax = plt.subplots(1, 1, figsize=(50, 40), dpi=80)
        ax.set_aspect('equal')
        ax.set_facecolor('#f8f8f8')

        # Color map ACI -> matplotlib
        aci_colors = {
            1: '#ff0000', 2: '#ffff00', 3: '#00ff00', 4: '#00ffff',
            5: '#0000ff', 6: '#ff00ff', 7: '#000000', 8: '#808080',
            9: '#c0c0c0', 82: '#b8860b', 150: '#4a9eff', 253: '#505050',
        }

        def aci_to_color(c):
            return aci_colors.get(c, '#333333')

        for e in msp:
            dxf = e.dxf
            color = aci_to_color(dxf.get('color', 7))
            lw = 0.5

            if e.dxftype() == 'LINE':
                xs = [dxf.start.x, dxf.end.x]
                ys = [dxf.start.y, dxf.end.y]
                ls = '--' if dxf.get('linetype', '') == 'DASHED' else '-'
                ax.plot(xs, ys, color=color, linewidth=lw, linestyle=ls)

            elif e.dxftype() == 'LWPOLYLINE':
                pts = list(e.get_points(format='xy'))
                if e.closed:
                    pts.append(pts[0])
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                ax.plot(xs, ys, color=color, linewidth=lw)

            elif e.dxftype() == 'TEXT':
                text = dxf.get('text', '')
                insert = dxf.get('insert', (0, 0, 0))
                height = dxf.get('height', 3)
                rot = dxf.get('rotation', 0)
                ax.text(insert[0], insert[1], text,
                        fontsize=max(2, height * 0.8), color=color,
                        rotation=rot, va='bottom', ha='left')

            elif e.dxftype() == 'HATCH':
                try:
                    for path in e.paths:
                        if hasattr(path, 'vertices'):
                            verts = [(v[0], v[1]) for v in path.vertices]
                            if len(verts) >= 3:
                                patch = mpatches.Polygon(
                                    verts, closed=True,
                                    facecolor=color, edgecolor='none',
                                    alpha=0.4
                                )
                                ax.add_patch(patch)
                except Exception:
                    pass

        ax.autoscale()
        ax.margins(0.02)
        ax.set_title(f"Pilares Completo - {Path(dxf_path).stem}", fontsize=14)
        fig.savefig(str(png_path), dpi=80, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        print(f"PNG (fallback) salvo: {png_path}")
        return True
    except Exception as e2:
        print(f"ERRO: render fallback tambem falhou: {e2}")
        return False


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    default_obra = "Obra_TREINO_1"
    base_dir = Path(__file__).resolve().parent.parent
    default_json_dir = base_dir / "DADOS-OBRAS" / default_obra / "Fase-4_Sincronizacao" / "JSON_Pilares"
    default_out = base_dir / "DADOS-OBRAS" / default_obra / "Fase-5_Geracao_Scripts" / "DXF_Pilares" / f"combined_pilares_completo_{default_obra}.dxf"
    default_png = base_dir / "docs" / "pilares_completo_check.png"

    parser = argparse.ArgumentParser(description='Gera DXF completo de pilares')
    parser.add_argument('--json-dir', type=str, default=str(default_json_dir),
                        help='Diretorio com JSONs dos pilares')
    parser.add_argument('--out', type=str, default=str(default_out),
                        help='Caminho de saida do DXF')
    parser.add_argument('--obra', type=str, default=default_obra, help='Nome da obra')
    parser.add_argument('--pav', type=str, default='TERREO', help='Pavimento')
    parser.add_argument('--cols', type=int, default=5, help='Colunas no grid')
    parser.add_argument('--png', type=str, default=str(default_png),
                        help='Caminho de saida do PNG (verificacao)')
    parser.add_argument('--no-png', action='store_true', help='Nao gerar PNG')

    args = parser.parse_args()

    dxf_path, count = build_combined(
        json_dir=args.json_dir,
        out_path=args.out,
        obra=args.obra,
        pav=args.pav,
        cols=args.cols,
    )

    if not args.no_png:
        png_path = Path(args.png)
        png_path.parent.mkdir(parents=True, exist_ok=True)
        render_png(dxf_path, str(png_path))

    print(f"\nConcluido: {count} pilares gerados com sucesso.")


if __name__ == '__main__':
    main()
