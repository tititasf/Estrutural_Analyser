#!/usr/bin/env python3
"""
gerar_lv_dxf_stog.py — Gerador STOG-quality LV DXF (Vigas Laterais, sem AutoCAD)
==================================================================================
Layout idêntico ao STOG LV original (engenharia reversa dos DXFs NIK SUNSET):
  - 4 LINE entities por painel (layer Painéis) — NOT LWPOLYLINE como no FV
  - SARR_3.5x7: pares de linhas VERTICAIS cobrindo h_lateral
    Padrão DXF: [inset=15cm] [antes/depois de cada divisor] [inset=15cm da direita]
  - Faces A e B lado a lado em X (mesmo Y base), detalhe de seção à esquerda
  - NOMENCLATURA 9cm acima do topo de cada face
  - COTA painéis individuais (1º nível, DIM_BELOW=37)
  - COTA total da viga (2º nível, DIM_TOTAL_BELOW=60)
  - COTA h_lateral vertical à direita (DIM_H_RIGHT=28)
  - Módulo painel LV = 122cm (eng. reversa: 122+58=180 para V22)
  - Vigas empilhadas verticalmente (1 linha por viga), ordenadas por b desc
  - Detalhe de seção transversal simplificado à esquerda de cada viga

JSON input (Fase-4_Sincronizacao/JSON_Vigas_Laterais/V*_A.json):
  total_width  = b   (largura da seção transversal, cm)
  total_height = h   (altura lateral dos painéis, cm)
  panels[].width = comprimento de cada segmento de painel original
  comprimento total = sum(p.width)

Uso:
  python scripts/gerar_lv_dxf_stog.py --obra DADOS-OBRAS/Obra_TREINO_21
  python scripts/gerar_lv_dxf_stog.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_21
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json, argparse, re
from pathlib import Path
import ezdxf

# ── Constantes de layout (calibradas nos DXFs STOG) ────────────────────────
GAP_ROW_LV     = 100    # gap vertical entre linhas de vigas (cm)
NOM_ABOVE      = 9      # y = painel_top + NOM_ABOVE → NOMENCLATURA
DIM_BELOW      = 37     # y = painel_bottom - DIM_BELOW → cotas painéis individuais
DIM_TOTAL_BELOW= 60     # y = painel_bottom - DIM_TOTAL_BELOW → cota total
DIM_H_RIGHT    = 28     # x = painel_right + DIM_H_RIGHT → cota h_lateral vertical
GAP_AB         = 50     # gap horizontal entre Face A (right) e Face B (left)
NOM_H          = 16.5   # altura texto NOMENCLATURA
PID_H          = 12.0   # altura texto panel-ID interno

# ── Módulo de painéis LV (engenharia reversa NIK SUNSET Laje Técnica) ───────
# V22: comprimento=180cm = 122+58 → módulo 122cm (metade do módulo FV 244)
PAINEL_MODULO_LV = 122   # módulo painel lateral STOG (cm)
PAINEL_MIN_LV    = 30    # largura mínima de painel (abaixo → agrega no anterior)

# ── SARR_3.5x7 — linhas verticais na vista lateral ─────────────────────────
# Eng. reversa V22 NIK SUNSET Laje Técnica (DXF confirmado):
#   Cada par: linha OUTER full-h, linha INNER altura h-2.2, bottom connector
#   Pares: [inset=15, inset+3.5] borda esq; [div-3.5,div]+[div,div+3.5] divisores;
#          [L-18.5,L-15] borda dir
#   SARR_2.2x7: single vertical a 7cm de cada fim; horizontal a y=h-2.2
LV_SARR_LAYER  = 'SARR_3.5x7'
LV_SARR_W      = 3.5    # largura de cada sarrafo (cm)
LV_SARR_INSET  = 15.0   # inset das bordas extremas (cm)
LV_SARR_END    = 7.0    # inset dos sarrafos simples SARR_2.2x7 das extremidades (cm)

# ── Detalhe de seção transversal ─────────────────────────────────────────────
SECT_W         = 160    # largura reservada para o detalhe de seção (cm)
SECT_GAP       = 30     # gap entre seção e Face A
SECT_PANEL_W   = 4      # espessura do painel na seção (Painéis layer)
SECT_BOARD_W   = 14     # espessura tábua externa (Madeira layer)

# ── Cards de folha ───────────────────────────────────────────────────────────
CARD_W     = 1485
CARD_H     = 1050
CARD_IN_DX = 75
CARD_IN_DY = 40
CARD_GAP   = 100
CARD_Y_GAP = 200

# ── Layers STOG LV ───────────────────────────────────────────────────────────
LAYERS = {
    'Painéis':          200,
    'COTA':             241,
    'NOMENCLATURA':       7,
    '5':                  5,
    'Folhas':           255,
    'CARIMBO':          255,
    LV_SARR_LAYER:       81,   # SARR_3.5x7 — cor confirmada no DXF STOG
    'SARR_2.2x7':        40,
    'CONCRETO':         251,
    'Hachura':          251,
    'Madeira':          126,
    'barrote':          126,
    'SCO-___-LAJ':      224,
    'TENSOR':           224,
    'presilha':         224,
    'Forcador':         224,
    'Escoras':          224,
    'Defpoints':          7,
    '0':                  7,
    'detalhes':           7,
    'Texto Seção':        7,
    'Cota Seção (2x)':  241,
    'texto':              7,
    'Reaproveitamento': 251,  # hachura ANSI31 nos painéis (padrão STOG)
}


# ──────────────────────────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────────────────────────

def setup_doc():
    doc = ezdxf.new('R2018')
    doc.header['$INSUNITS'] = 0   # sem unidades definidas (igual ao FV aprovado)
    for lname, color in LAYERS.items():
        if lname not in doc.layers:
            doc.layers.add(lname, color=color)

    # Dimstyle PAINEL — idêntico ao FV aprovado (eng. reversa NIK SUNSET)
    if 'PAINEL' not in doc.dimstyles:
        ds = doc.dimstyles.new('PAINEL')
    else:
        ds = doc.dimstyles.get('PAINEL')
    ds.set_arrows('OBLIQUE', 'OBLIQUE')   # traço oblíquo (não seta)
    ds.dxf.dimasz  = 3.0    # tamanho do tick
    ds.dxf.dimtxt  = 10.0   # altura do texto de cota
    ds.dxf.dimgap  = 3.0    # gap texto ↔ linha
    ds.dxf.dimexe  = 3.0    # extensão acima da dim line
    ds.dxf.dimexo  = 3.0    # offset da linha de extensão
    ds.dxf.dimclrd = 4      # cor linha de cota (cyan ACI 4)
    ds.dxf.dimclrt = 240    # cor texto
    ds.dxf.dimclre = 4      # cor linhas de extensão
    ds.dxf.dimtad  = 1      # texto ACIMA da linha
    ds.dxf.dimtih  = 0      # texto segue ângulo

    # Dimstyle SECAO2X — para cota de seção com texto 2x maior
    if 'SECAO2X' not in doc.dimstyles:
        ds2 = doc.dimstyles.new('SECAO2X')
    else:
        ds2 = doc.dimstyles.get('SECAO2X')
    ds2.set_arrows('OBLIQUE', 'OBLIQUE')
    ds2.dxf.dimasz  = 5.0    # STOG real: 5.0
    ds2.dxf.dimtxt  = 7.0    # STOG real: 7.0 (não 16 — era estimativa)
    ds2.dxf.dimgap  = 2.0    # STOG real: 2.0
    ds2.dxf.dimexe  = 3.0    # STOG real: 3.0
    ds2.dxf.dimexo  = 3.0    # STOG real: 3.0
    ds2.dxf.dimclrd = 4      # STOG real: 4 (cyan)
    ds2.dxf.dimclrt = 1      # STOG real: 1 (vermelho — não 240)
    ds2.dxf.dimclre = 4      # STOG real: 4
    ds2.dxf.dimtad  = 3      # STOG real: 3 (above with leader)
    ds2.dxf.dimtih  = 0

    return doc


# ──────────────────────────────────────────────────────────────────────────────
# Distribuição de painéis LV
# ──────────────────────────────────────────────────────────────────────────────

def extract_panels_from_json(panels_json, laje_central_alt_global=0.0):
    """Extrai dados reais dos painéis do JSON.
    Retorna lista de dicts: [{width, height1, height2, grade_h1, grade_h2, laje_central_alt}, ...]
    laje_central_alt_global: valor da raiz do JSON (propagado para todos os painéis).
    """
    panels = []
    for p in (panels_json or []):
        w = float(p.get('width', 0))
        if w <= 0:
            continue
        # laje_central_alt: por painel (override) ou global da raiz do JSON
        lca = float(p.get('laje_central_alt', laje_central_alt_global) or laje_central_alt_global)
        panels.append({
            'width':            w,
            'height1':          float(p.get('height1', 0)),
            'height2':          float(p.get('height2', 0)),
            'grade_h1':         float(p.get('grade_h1', 0) or 0),
            'grade_h2':         float(p.get('grade_h2', 0) or 0),
            'laje_central_alt': lca,
        })
    return panels


# ──────────────────────────────────────────────────────────────────────────────
# Primitivos de desenho
# ──────────────────────────────────────────────────────────────────────────────

def add_text(msp, x, y, text, height, layer, halign=0, valign=0):
    attribs = {'insert': (x, y), 'height': height, 'layer': layer}
    if halign or valign:
        attribs['halign'] = halign
        attribs['valign'] = valign
        attribs['align_point'] = (x, y)
    msp.add_text(text, dxfattribs=attribs)


def draw_panel_lines(msp, x0, y0, pw, h):
    """4 LINE entities por painel LV (borda inferior, superior, esquerda, direita)."""
    a = {'layer': 'Painéis'}
    msp.add_line((x0,    y0),   (x0+pw, y0),   dxfattribs=a)   # bottom
    msp.add_line((x0,    y0+h), (x0+pw, y0+h), dxfattribs=a)   # top
    msp.add_line((x0,    y0),   (x0,    y0+h), dxfattribs=a)   # left
    msp.add_line((x0+pw, y0),   (x0+pw, y0+h), dxfattribs=a)   # right


def draw_sarr_lv(msp, x0, y0, h, panel_widths):
    """SARR para uma face LV — padrão confirmado eng. reversa V22 DXF STOG.

    SARR_2.2x7 (layer='SARR_2.2x7'):
      - Single vertical a x=7cm do fim esquerdo (full h)
      - Single vertical a x=L-7cm do fim direito (full h)
      - Horizontal a y=h-2.2 dentro de cada seção de painel (entre pares 3.5x7)

    SARR_3.5x7 (layer='SARR_3.5x7', cor 81):
      Cada par [xl, xr=xl+3.5]:
        - Linha outer (mais perto do fim/divisor): full h
        - Linha inner (mais perto do interior): h-2.2 (top cortado 2.2cm)
        - Linha bottom connector a y=y0 ligando xl-xr
      Posições:
        - Borda esq: [inset=15, 18.5] — outer=x=15 (full h), inner=x=18.5 (h-2.2)
        - Antes de cada divisor: [div-3.5, div] — outer=div, inner=div-3.5
        - Após divisor: [div, div+3.5] — outer=div (full h), inner=div+3.5 (h-2.2)
        - Borda dir: [L-18.5, L-15] — inner=L-18.5 (h-2.2), outer=L-15 (full h)
    """
    L = sum(panel_widths)
    s35 = LV_SARR_LAYER    # 'SARR_3.5x7'
    s22 = 'SARR_2.2x7'
    h_inner = h - 2.2      # altura das linhas internas

    def line35(x_abs, h_use):
        """Linha vertical SARR_3.5x7."""
        msp.add_line((x_abs, y0), (x_abs, y0 + h_use), dxfattribs={'layer': s35})

    def bot35(xl_abs, xr_abs):
        """Bottom connector horizontal SARR_3.5x7."""
        msp.add_line((xl_abs, y0), (xr_abs, y0), dxfattribs={'layer': s35})

    def line22v(x_abs, h_use=None):
        """Linha vertical SARR_2.2x7."""
        top = y0 + (h if h_use is None else h_use)
        msp.add_line((x_abs, y0), (x_abs, top), dxfattribs={'layer': s22})

    def line22h(xa, xb):
        """Linha horizontal SARR_2.2x7 a y=h-2.2."""
        msp.add_line((xa, y0 + h_inner), (xb, y0 + h_inner), dxfattribs={'layer': s22})

    def draw_pair_left_edge(xl):
        """Par na borda esquerda: outer=xl (full h), inner=xl+sarr_w (h-2.2)."""
        xr = xl + LV_SARR_W
        if xr > L + 0.1: return
        line35(x0 + xl, h)           # outer (esquerda) full h
        line35(x0 + xr, h_inner)     # inner (direita) h-2.2
        bot35(x0 + xl, x0 + xr)

    def draw_pair_right_edge(xr):
        """Par na borda direita: inner=xr-sarr_w (h-2.2), outer=xr (full h)."""
        xl = xr - LV_SARR_W
        if xl < -0.1: return
        line35(x0 + xl, h_inner)     # inner (esquerda) h-2.2
        line35(x0 + xr, h)           # outer (direita) full h
        bot35(x0 + xl, x0 + xr)

    def draw_pair_before_div(div):
        """Par antes do divisor: [div-3.5, div] — outer=div (full h)."""
        xl = div - LV_SARR_W
        xr = div
        if xl < -0.1: return
        line35(x0 + xl, h_inner)     # inner h-2.2
        line35(x0 + xr, h)           # outer (flush com divisor) full h
        bot35(x0 + xl, x0 + xr)

    def draw_pair_after_div(div):
        """Par após divisor: [div, div+3.5] — outer=div (full h)."""
        xl = div
        xr = div + LV_SARR_W
        if xr > L + 0.1: return
        line35(x0 + xl, h)           # outer (flush com divisor) full h
        line35(x0 + xr, h_inner)     # inner h-2.2
        bot35(x0 + xl, x0 + xr)

    # ── Guard: skip sarrafos se face inteira menor que 2×inset ─────────────
    if L < 2 * LV_SARR_INSET:
        return

    # ── SARR_2.2x7 single verticals nas extremidades ──────────────────────
    if L > LV_SARR_END:
        line22v(x0 + LV_SARR_END)          # 7cm da esquerda
        line22v(x0 + L - LV_SARR_END)      # 7cm da direita

    # ── SARR_3.5x7 pares ──────────────────────────────────────────────────
    # Borda esquerda
    draw_pair_left_edge(LV_SARR_INSET)

    # Divisores: par antes + par após (skip se segmento < 2×inset)
    dividers = []
    xd = 0.0
    for pw in panel_widths[:-1]:
        xd += pw
        dividers.append(xd)

    prev_x = 0.0
    for div in dividers:
        seg_w = div - prev_x
        if seg_w >= 2 * LV_SARR_INSET:
            draw_pair_before_div(div)
        draw_pair_after_div(div)
        prev_x = div
    # Guard último segmento (entre último divisor e borda direita)
    last_seg = L - prev_x if dividers else L

    # Borda direita (skip se último segmento muito estreito)
    if last_seg >= 2 * LV_SARR_INSET:
        draw_pair_right_edge(L - LV_SARR_INSET)

    # ── SARR_2.2x7 horizontal a y=h-2.2 (dentro de cada seção de painel) ──
    # Fronteiras das seções: [0] + [div-3.5 para cada div] + [L]
    # Horizontal de [esq_do_par_esq] a [dir_do_par_dir] de cada seção
    # Seção 0: de inset (borda esq outer) até primeiro divisor ou borda dir
    section_rights = [div for div in dividers] + [L]  # right boundary de cada seção
    section_lefts  = [0.0] + [div for div in dividers]  # left boundary

    for i, (sl, sr) in enumerate(zip(section_lefts, section_rights)):
        # left boundary de sarrafo nesta seção
        if i == 0:
            xa = LV_SARR_INSET          # left outer do par esquerdo
        else:
            xa = sl                     # divisor (right outer do par após)
        # right boundary desta seção
        if i == len(section_lefts) - 1:
            xb = L - LV_SARR_INSET     # right outer do par direito
        else:
            xb = sr                    # vai até o divisor (união)

        if xb - xa > 1.0:
            line22h(x0 + xa, x0 + xb)


# ──────────────────────────────────────────────────────────────────────────────
# Cotas (dimensões)
# ──────────────────────────────────────────────────────────────────────────────

def dim_panel_lv(msp, x0, x1, y_base):
    """Cota horizontal de painel individual — 1º nível."""
    try:
        d = msp.add_linear_dim(
            base=(x0, y_base - DIM_BELOW),
            p1=(x0, y_base), p2=(x1, y_base),
            angle=0, dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


def dim_total_lv(msp, x0, x1, y_base):
    """Cota horizontal total da face — 2º nível."""
    try:
        d = msp.add_linear_dim(
            base=(x0, y_base - DIM_TOTAL_BELOW),
            p1=(x0, y_base), p2=(x1, y_base),
            angle=0, dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


def dim_h_lateral(msp, x_right, y0, h):
    """Cota vertical de h_lateral — lado direito."""
    if h <= 0:
        return
    try:
        x_base = x_right + DIM_H_RIGHT
        d = msp.add_linear_dim(
            base=(x_base, y0),
            p1=(x_right, y0), p2=(x_right, y0 + h),
            angle=90, dimstyle='PAINEL',
            dxfattribs={'layer': 'COTA'},
        )
        d.render()
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Detalhe de seção transversal
# ──────────────────────────────────────────────────────────────────────────────

def draw_section_detail(msp, x_center, y0, b, h, viga_nome='', b_alma=19):
    """Detalhe de seção transversal — TODOS os elementos STOG (eng. reversa DXF V22).

    y0      = base de Madeira/Painéis = topo do barrote
    x_center= centro horizontal do barrote
    b       = largura da laje/flange
    h       = altura da seção de concreto
    b_alma  = largura da alma (para título, default 19cm)
    """
    CAP_H = 4.4   # altura das caps/bases (confirmado DXF)

    # ── Âncoras X fixas (confirmadas DXF V22) ────────────────────────────
    x_ml_l = x_center - 32   # Madeira L esquerda
    x_ml_r = x_center - 18   # Madeira L direita / Painéis L esquerda
    x_pl_r = x_center - 14   # Painéis L dir = concreto left (x_cl)
    x_cl   = x_center - 14   # concreto left
    x_wr   = x_center + 24   # web right (x_cl + 38)
    x_pr_r = x_center + 28   # Painéis R direita
    x_mr_r = x_center + 42   # Madeira R direita
    x_fr   = x_center + 24 + b  # flange right (varia com b)

    h_left      = h + 8                       # altura Madeira/Painéis LEFT
    h_flange_bot = max(h - 16, CAP_H + 5)    # offset y do canto inferior direito da flange
    h_right     = max(h - 20, h_flange_bot)  # Madeira RIGHT ≥ flange_bot (vigas pequenas)

    la = {'layer': 'Madeira'}
    lp = {'layer': 'Painéis'}
    l0 = {'layer': '0'}

    # ═══════════════════════════════════════════════════════════════════════
    # 1. BARROTE (layer 'barrote') — base horizontal
    # ═══════════════════════════════════════════════════════════════════════
    bw2 = (140 + b) / 2
    msp.add_lwpolyline(
        [(x_center - bw2, y0-20), (x_center + bw2, y0-20),
         (x_center + bw2, y0),    (x_center - bw2, y0)],
        close=True, dxfattribs={'layer': 'barrote'}
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 2. SCO-___-LAJ (layer 'SCO-LAJ') — strip no topo do barrote
    # ═══════════════════════════════════════════════════════════════════════
    sco_l = x_center - bw2 + 19
    sco_r = x_center + bw2 - 9
    msp.add_lwpolyline(
        [(sco_l, y0-3.2), (sco_r, y0-3.2), (sco_r, y0), (sco_l, y0)],
        close=True, dxfattribs={'layer': 'SCO-___-LAJ'}
    )

    # ═══════════════════════════════════════════════════════════════════════
    # 3. MADEIRA — 9 LWPOLYLINEs (boards + caps + bases)
    # ═══════════════════════════════════════════════════════════════════════
    # 3a. Madeira LEFT main board (14cm × h+8)
    msp.add_lwpolyline(
        [(x_ml_l, y0), (x_ml_r, y0), (x_ml_r, y0+h_left), (x_ml_l, y0+h_left)],
        close=True, dxfattribs=la)
    # 3b. Madeira RIGHT main board (14cm × h-20)
    msp.add_lwpolyline(
        [(x_pr_r, y0), (x_mr_r, y0), (x_mr_r, y0+h_right), (x_pr_r, y0+h_right)],
        close=True, dxfattribs=la)
    # 3c. LEFT base plate (20cm × 4.4cm, extends left from board)
    msp.add_lwpolyline(
        [(x_ml_l-20, y0), (x_ml_l, y0), (x_ml_l, y0+CAP_H), (x_ml_l-20, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3d. RIGHT base plate (20cm × 4.4cm, extends right from board)
    msp.add_lwpolyline(
        [(x_mr_r, y0), (x_mr_r+20, y0), (x_mr_r+20, y0+CAP_H), (x_mr_r, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3e. LEFT board bottom cap (14cm × 4.4cm)
    msp.add_lwpolyline(
        [(x_ml_l, y0), (x_ml_r, y0), (x_ml_r, y0+CAP_H), (x_ml_l, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3f. LEFT board top cap (14cm × 4.4cm)
    msp.add_lwpolyline(
        [(x_ml_l, y0+h_left-CAP_H), (x_ml_r, y0+h_left-CAP_H),
         (x_ml_r, y0+h_left),       (x_ml_l, y0+h_left)],
        close=True, dxfattribs=la)
    # 3g. RIGHT board top cap (14cm × 4.4cm)
    msp.add_lwpolyline(
        [(x_pr_r, y0+h_right-CAP_H), (x_mr_r, y0+h_right-CAP_H),
         (x_mr_r, y0+h_right),       (x_pr_r, y0+h_right)],
        close=True, dxfattribs=la)
    # 3h. Concrete-left base (10cm × 4.4cm, supports concrete web base)
    msp.add_lwpolyline(
        [(x_cl, y0), (x_cl+10, y0), (x_cl+10, y0+CAP_H), (x_cl, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3i. Web-right base (10cm × 4.4cm, supports concrete web base)
    msp.add_lwpolyline(
        [(x_wr-10, y0), (x_wr, y0), (x_wr, y0+CAP_H), (x_wr-10, y0+CAP_H)],
        close=True, dxfattribs=la)

    # ═══════════════════════════════════════════════════════════════════════
    # 4. PAINÉIS — 4 LWPOLYLINEs
    # ═══════════════════════════════════════════════════════════════════════
    # 4a. Painéis LEFT (4cm × h+8)
    msp.add_lwpolyline(
        [(x_ml_r, y0), (x_pl_r, y0), (x_pl_r, y0+h_left), (x_ml_r, y0+h_left)],
        close=True, dxfattribs=lp)
    # 4b. Painéis RIGHT (4cm × h-20)
    msp.add_lwpolyline(
        [(x_wr, y0), (x_pr_r, y0), (x_pr_r, y0+h_right), (x_wr, y0+h_right)],
        close=True, dxfattribs=lp)
    # 4c. Painéis HORIZONTAL — tira base da flange (b × ~4cm)
    msp.add_lwpolyline(
        [(x_wr, y0+h_right),        (x_fr, y0+h_right),
         (x_fr, y0+h_flange_bot),   (x_wr, y0+h_flange_bot)],
        close=True, dxfattribs=lp)
    # 4d. Painéis BOTTOM STRIP — base do concreto (38cm × 3.6cm)
    msp.add_lwpolyline(
        [(x_cl, y0+CAP_H), (x_wr, y0+CAP_H), (x_wr, y0+8), (x_cl, y0+8)],
        close=True, dxfattribs=lp)

    # ═══════════════════════════════════════════════════════════════════════
    # 5. CONCRETO em L (layer 'CONCRETO') — polígono 6 vértices
    # ═══════════════════════════════════════════════════════════════════════
    conc_pts = [
        (x_cl, y0+8),             (x_cl, y0+h+8),
        (x_fr, y0+h+8),           (x_fr, y0+h_flange_bot),
        (x_wr, y0+h_flange_bot),  (x_wr, y0+8),
    ]
    msp.add_lwpolyline(conc_pts, close=True, dxfattribs={'layer': 'CONCRETO'})
    # Hachura concreto (ANSI31, escala sutil como STOG — layer COTA bylayer)
    hatch = msp.add_hatch(dxfattribs={'layer': 'COTA'})
    hatch.set_pattern_fill('ANSI31', scale=0.4)
    hatch.paths.add_polyline_path(conc_pts, is_closed=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 6. TENSOR linha + holders detalhados (16 LINEs layer '0')
    # ═══════════════════════════════════════════════════════════════════════
    y_tensor = y0 + 50
    msp.add_line(
        (x_center - 57, y_tensor), (x_fr - 2, y_tensor),
        dxfattribs={'layer': 'TENSOR'}
    )

    # Tensor holders — brackets complexos (eng. reversa 16 LINEs layer '0')
    # LEFT holder: rect [xc-52, xc-22] × [y0+44, y0+56] + inner slot + tab
    lx1, lx2 = x_center - 52, x_center - 22
    # RIGHT holder: rect [x_mr_r, x_mr_r+30] × [y0+44, y0+56] + inner slot + tab
    rx1, rx2 = x_mr_r, x_mr_r + 30
    yt, yb = y0 + 56, y0 + 44
    yi1, yi2 = y0 + 51, y0 + 49   # inner slot (2cm gap for tensor rod)

    for (a1, a2, tab_dir) in [(lx1, lx2, -1), (rx1, rx2, +1)]:
        # Outer rectangle (3 sides: top, bottom, outer vertical)
        msp.add_line((a1, yt), (a2, yt), dxfattribs=l0)        # top
        msp.add_line((a1, yb), (a2, yb), dxfattribs=l0)        # bottom
        outer_x = a1 if tab_dir == -1 else a2
        msp.add_line((outer_x, yt), (outer_x, yb), dxfattribs=l0)  # outer vertical
        # Inner slot (2 horizontal lines at y0+49, y0+51)
        msp.add_line((a1, yi2), (a2, yi2), dxfattribs=l0)      # inner top
        msp.add_line((a1, yi1), (a2, yi1), dxfattribs=l0)      # inner bottom
        # Tab (presilha-like extension, 2cm × 6cm)
        tx = outer_x + tab_dir * 2
        msp.add_line((outer_x, y0+47), (tx, y0+47), dxfattribs=l0)  # tab bottom
        msp.add_line((tx, y0+53), (tx, y0+47), dxfattribs=l0)       # tab vertical
        msp.add_line((outer_x, y0+53), (tx, y0+53), dxfattribs=l0)  # tab top

    # ═══════════════════════════════════════════════════════════════════════
    # 7. PRESILHA — aproximadas como linhas cruzadas (layer 'presilha')
    # ═══════════════════════════════════════════════════════════════════════
    lpr = {'layer': 'presilha'}
    for px in [x_center - 65, x_center + 75]:
        sz = 5
        msp.add_line((px-sz, y0-8-sz), (px+sz, y0-8+sz), dxfattribs=lpr)
        msp.add_line((px-sz, y0-8+sz), (px+sz, y0-8-sz), dxfattribs=lpr)

    # ═══════════════════════════════════════════════════════════════════════
    # 7b. HATCHING — Wood (ANSI31) + Panel solid fills (STOG reference: 7+4)
    # ═══════════════════════════════════════════════════════════════════════
    def _hatch_rect(x1, y1, x2, y2, pattern='ANSI31', scale=0.5,
                    layer='Hachura', color=None):
        att = {'layer': layer}
        if color is not None:
            att['color'] = color
        ht = msp.add_hatch(dxfattribs=att)
        ht.set_pattern_fill(pattern, scale=scale)
        ht.paths.add_polyline_path(
            [(x1,y1),(x2,y1),(x2,y2),(x1,y2)], is_closed=True)

    # Wood boards ANSI31 hatching (7 fills — eng. reversa STOG)
    _hatch_rect(x_ml_l, y0, x_ml_r, y0+h_left)                       # Left main board
    _hatch_rect(x_pr_r, y0, x_mr_r, y0+h_right)                      # Right main board
    _hatch_rect(x_ml_l-20, y0, x_ml_l, y0+CAP_H)                     # Left base plate
    _hatch_rect(x_mr_r, y0, x_mr_r+20, y0+CAP_H)                     # Right base plate
    _hatch_rect(x_ml_l, y0+h_left-CAP_H, x_ml_r, y0+h_left)          # Left top cap
    _hatch_rect(x_pr_r, y0+h_right-CAP_H, x_mr_r, y0+h_right)        # Right top cap
    _hatch_rect(x_cl, y0, x_cl+10, y0+CAP_H)                          # CL base support

    # Panel solid fills (4 fills — STOG)
    _hatch_rect(x_ml_r, y0, x_pl_r, y0+h_left, 'SOLID', 1.0, color=253)
    _hatch_rect(x_wr, y0, x_pr_r, y0+h_right, 'SOLID', 1.0, color=253)
    _hatch_rect(x_wr, y0+h_right, x_fr, y0+h-16, 'SOLID', 1.0, color=253)
    _hatch_rect(x_cl, y0+CAP_H, x_wr, y0+8, 'SOLID', 1.0, color=253)

    # ═══════════════════════════════════════════════════════════════════════
    # 8. TEXTOS 'detalhes' — labels a, b, c (layer 'detalhes')
    # ═══════════════════════════════════════════════════════════════════════
    add_text(msp, x_center - 29, y0 + 27.3, 'a', 9.6, 'detalhes')
    add_text(msp, x_center + 31, y0 + 27.3, 'b', 9.6, 'detalhes')
    add_text(msp, x_center - 4,  y0 + 10.5, 'c', 9.6, 'detalhes')

    # ═══════════════════════════════════════════════════════════════════════
    # 9. TEXTO SEÇÃO — título no topo (layer 'Texto Seção')
    # ═══════════════════════════════════════════════════════════════════════
    if viga_nome:
        add_text(msp, x_center + 15, y0 + h + 8, f'{viga_nome}.A',
                 13.0, 'Texto Seção')
        # Título (bxh) — STOG: "V22 (19x60)"
        # b_alma: para vigas retangulares = b (correto).
        # Para vigas L (flange > web), b_alma vem do JSON = flange width.
        # Sem dado de alma no JSON → mostrar b_alma × h_section.
        add_text(msp, x_center - 10, y0 + h + 24,
                 f'{viga_nome} ({int(b_alma)}x{int(h)})',
                 10.0, 'Texto Seção')

    # ═══════════════════════════════════════════════════════════════════════
    # 10. DIMENSÕES — 6 cotas da seção transversal (eng. reversa DXF V22)
    # ═══════════════════════════════════════════════════════════════════════
    dim_x_right = x_fr + 43   # posição X das cotas do lado direito

    def add_dim_v(p1, p2, base_x, layer='COTA', style='PAINEL'):
        """Adiciona cota vertical."""
        try:
            d = msp.add_linear_dim(
                base=(base_x, p1[1]), p1=p1, p2=p2,
                angle=90, dimstyle=style, dxfattribs={'layer': layer})
            d.render()
        except Exception:
            pass

    def add_dim_h(p1, p2, base_y, layer='COTA', style='PAINEL'):
        """Adiciona cota horizontal."""
        try:
            d = msp.add_linear_dim(
                base=(p1[0], base_y), p1=p1, p2=p2,
                angle=0, dimstyle=style, dxfattribs={'layer': layer})
            d.render()
        except Exception:
            pass

    # 10a. Full LEFT height (128cm = h+8): y0 to y0+h+8 — far left
    add_dim_v((x_ml_l-20, y0), (x_ml_l, y0+h_left),
              x_center - 108)
    # 10b. Concrete height (h): y0+8 to y0+h+8 — layer 'Cota Seção (2x)'
    add_dim_v((x_cl, y0+8), (x_cl, y0+h+8),
              x_center + 18, layer='Cota Seção (2x)', style='SECAO2X')
    # 10c. Tensor height (50cm): y0 to y0+50 — right side
    add_dim_v((x_mr_r, y0), (x_mr_r, y0+50),
              x_fr + 3)
    # 10d. Madeira RIGHT height (h-20): y0 to y0+h-20 — far right
    add_dim_v((x_mr_r, y0), (x_mr_r, y0+h_right),
              dim_x_right)
    # 10e. Flange height: y0+h_flange_bot to y0+h+8 — far right
    add_dim_v((x_fr, y0+h_flange_bot), (x_fr, y0+h+8),
              dim_x_right)
    # 10f. Web width (38cm): x_cl to x_wr — horizontal at bottom
    add_dim_h((x_cl, y0), (x_wr, y0),
              y0 - 45)


# ──────────────────────────────────────────────────────────────────────────────
# Face da viga (A ou B)
# ──────────────────────────────────────────────────────────────────────────────

def draw_lv_face(msp, x0, y0, panels, h, nome_face,
                 holes=None, pillar_left=None, pillar_right=None,
                 laje_sup=7.0, laje_inf=7.0):
    """Desenha uma face (A ou B) da viga lateral — todos elementos visuais.
    panels: lista de dicts [{width, height1, height2, grade_h1, grade_h2}, ...]
    holes: lista de aberturas [{active, width, height, position}, ...]
    pillar_left/right: dict {active, width, length}
    laje_sup/inf: alturas default de laje superior/inferior (cm)
    Retorna comprimento total da face.
    """
    panel_widths = [p['width'] for p in panels]
    comprimento = sum(panel_widths)
    n = len(panels)
    if comprimento <= 0 or h <= 0:
        return comprimento

    # ── 1. LAJE INFERIOR — retângulo fechado com hachura POR PAINEL ─────
    # STOG: hatches em layer COTA com cor bylayer (256), padrão sutil
    if laje_inf > 0:
        x_cur = x0
        for p in panels:
            pw = p['width']
            pts = [(x_cur, y0-laje_inf), (x_cur+pw, y0-laje_inf),
                   (x_cur+pw, y0), (x_cur, y0)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
            ht = msp.add_hatch(dxfattribs={'layer': 'COTA'})
            ht.set_pattern_fill('ANSI31', scale=0.5)
            ht.paths.add_polyline_path(pts, is_closed=True)
            x_cur += pw

    # ── 2. LAJE SUPERIOR — retângulo fechado com hachura POR PAINEL ─────
    if laje_sup > 0:
        x_cur = x0
        for p in panels:
            pw = p['width']
            pts = [(x_cur, y0+h), (x_cur+pw, y0+h),
                   (x_cur+pw, y0+h+laje_sup), (x_cur, y0+h+laje_sup)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
            ht = msp.add_hatch(dxfattribs={'layer': 'COTA'})
            ht.set_pattern_fill('ANSI31', scale=0.5)
            ht.paths.add_polyline_path(pts, is_closed=True)
            x_cur += pw

    # ── 3. Contornos dos painéis + lajes centrais + grade ───────────────
    x_cur = x0
    for idx, p in enumerate(panels):
        pw = p['width']
        h1 = p['height1']
        h2 = p['height2']
        gh1 = p['grade_h1']
        gh2 = p['grade_h2']
        is_first = (idx == 0)
        is_last  = (idx == n - 1)

        lc_alt = p.get('laje_central_alt', 0)
        has_laje_central = (lc_alt > 0) or (h1 > 0 and h2 > 0 and abs(h1 - h2) > 0.5)

        # Posições em espaço de desenho: escala proporcional quando dims reais > altura da face
        if lc_alt > 0:
            total_real = h1 + lc_alt + h2
            if total_real > 0:
                _s = h / total_real if total_real > h else 1.0
                h1_d   = h1 * _s
                lc_h_d = lc_alt * _s
            else:
                h1_d, lc_h_d = h1, lc_alt
        elif has_laje_central:
            h1_d   = h1
            lc_h_d = h - h1 - (h - h2) if h2 < h else h - h1
        else:
            h1_d, lc_h_d = h, 0  # usado apenas para posicionamento de grade abaixo

        # Contorno externo do painel
        draw_panel_lines(msp, x_cur, y0, pw, h)

        # Reaproveitamento hatch (ANSI31 escala 1.0) — padrão STOG: cobre painel inteiro
        _rpts = [(x_cur, y0), (x_cur+pw, y0), (x_cur+pw, y0+h), (x_cur, y0+h)]
        _rh = msp.add_hatch(dxfattribs={'layer': 'Reaproveitamento'})
        _rh.set_pattern_fill('ANSI31', scale=1.0)
        _rh.paths.add_polyline_path(_rpts, is_closed=True)

        if has_laje_central and lc_h_d > 0.5:
            # Laje central: retângulo fechado + hachura ANSI31 (bylayer como STOG)
            laje_y = y0 + h1_d
            pts_lc = [(x_cur, laje_y), (x_cur+pw, laje_y),
                      (x_cur+pw, laje_y+lc_h_d), (x_cur, laje_y+lc_h_d)]
            msp.add_lwpolyline(pts_lc, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
            ht = msp.add_hatch(dxfattribs={'layer': 'COTA'})
            ht.set_pattern_fill('ANSI31', scale=0.5)
            ht.paths.add_polyline_path(pts_lc, is_closed=True)

        # Grade H1
        if gh1 > 0:
            y_grade = y0 + h1_d if has_laje_central else y0 + h
            gh = 2.2
            x_gi = x_cur + (15 if is_first else 0)
            x_gf = x_cur + pw - (15 if is_last else 0)
            if x_gf > x_gi:
                msp.add_lwpolyline(
                    [(x_gi, y_grade-gh), (x_gf, y_grade-gh),
                     (x_gf, y_grade), (x_gi, y_grade)],
                    close=True, dxfattribs={'layer': 'SARR_2.2x7'})
                leg_w, leg_h = 3.5, min(gh1, h1_d if has_laje_central else h)
                msp.add_lwpolyline(
                    [(x_gi, y_grade-gh), (x_gi+leg_w, y_grade-gh),
                     (x_gi+leg_w, y_grade-gh-leg_h), (x_gi, y_grade-gh-leg_h)],
                    close=True, dxfattribs={'layer': 'SARR_3.5x7'})
                msp.add_lwpolyline(
                    [(x_gf-leg_w, y_grade-gh), (x_gf, y_grade-gh),
                     (x_gf, y_grade-gh-leg_h), (x_gf-leg_w, y_grade-gh-leg_h)],
                    close=True, dxfattribs={'layer': 'SARR_3.5x7'})

        # Grade H2 (só com laje central)
        if gh2 > 0 and has_laje_central:
            y_grade2 = y0 + h
            gh = 2.2
            x_gi = x_cur + (15 if is_first else 0)
            x_gf = x_cur + pw - (15 if is_last else 0)
            if x_gf > x_gi:
                msp.add_lwpolyline(
                    [(x_gi, y_grade2-gh), (x_gf, y_grade2-gh),
                     (x_gf, y_grade2), (x_gi, y_grade2)],
                    close=True, dxfattribs={'layer': 'SARR_2.2x7'})
                leg_w, leg_h = 3.5, min(gh2, h2)
                msp.add_lwpolyline(
                    [(x_gi, y_grade2-gh), (x_gi+leg_w, y_grade2-gh),
                     (x_gi+leg_w, y_grade2-gh-leg_h), (x_gi, y_grade2-gh-leg_h)],
                    close=True, dxfattribs={'layer': 'SARR_3.5x7'})
                msp.add_lwpolyline(
                    [(x_gf-leg_w, y_grade2-gh), (x_gf, y_grade2-gh),
                     (x_gf, y_grade2-gh-leg_h), (x_gf-leg_w, y_grade2-gh-leg_h)],
                    close=True, dxfattribs={'layer': 'SARR_3.5x7'})

        # Divisor entre painéis
        if not is_last:
            msp.add_line((x_cur+pw, y0), (x_cur+pw, y0+h),
                         dxfattribs={'layer': 'Painéis'})

        x_cur += pw

    # ── 4. SARR_3.5x7 — pares de linhas verticais + conectores ──────────
    draw_sarr_lv(msp, x0, y0, h, panel_widths)

    # ── 5. PILARES/OBSTÁCULOS — retângulos hachurados nas bordas ─────────
    def _draw_pillar(px, py, pw_p, ph_p):
        """Pilar como retângulo ANSI31 hachurado (rosa no robô → hachura no DXF)."""
        pts = [(px, py), (px+pw_p, py), (px+pw_p, py+ph_p), (px, py+ph_p)]
        msp.add_lwpolyline(pts, close=True,
                           dxfattribs={'layer': 'Painéis', 'linetype': 'DASHED'})
        ht = msp.add_hatch(dxfattribs={'layer': 'COTA'})
        ht.set_pattern_fill('ANSI31', scale=0.5)
        ht.paths.add_polyline_path(pts, is_closed=True)
        add_text(msp, px + pw_p/2, py + ph_p/2, 'PILAR',
                 5.0, '5', halign=1, valign=2)

    if pillar_left and pillar_left.get('active'):
        pw_pl = float(pillar_left.get('width', 0))
        pl_len = float(pillar_left.get('length', 0))
        if pw_pl > 0:
            _draw_pillar(x0 + pl_len, y0, pw_pl, h)

    if pillar_right and pillar_right.get('active'):
        pw_pr = float(pillar_right.get('width', 0))
        pr_len = float(pillar_right.get('length', 0))
        if pw_pr > 0:
            _draw_pillar(x0 + comprimento - pr_len - pw_pr, y0, pw_pr, h)

    # ── 6. NOMENCLATURA acima do topo ─────────────────────────────────────
    add_text(msp, x0 + 3, y0 + h + laje_sup + NOM_ABOVE, nome_face,
             NOM_H, 'NOMENCLATURA')

    # ── 7. IDs + info de painel + MTEXT ponteiro ─────────────────────────
    x_cur = x0
    for i, p in enumerate(panels):
        pw = p['width']
        cx = x_cur + pw / 2
        cy = y0 + h / 2
        add_text(msp, cx, cy + 4, str(i + 1), PID_H, '5', halign=1, valign=2)
        if pw >= 20:
            add_text(msp, cx, cy - PID_H + 2, f'{pw:.0f}',
                     7.0, '5', halign=1, valign=2)
        if pw >= 30:
            n_pont = max(2, round(pw / 24.4))
            msp.add_mtext(
                f'{n_pont} 1/2pont',
                dxfattribs={'layer': 'texto', 'char_height': 6.0,
                            'insert': (cx, cy - PID_H - 8, 0),
                            'attachment_point': 5})
        x_cur += pw

    # ── 8. Cotas horizontais individuais + total ─────────────────────────
    x_cur = x0
    for pw in panel_widths:
        dim_panel_lv(msp, x_cur, x_cur + pw, y0)
        x_cur += pw
    if len(panel_widths) > 1:
        dim_total_lv(msp, x0, x0 + comprimento, y0)

    # ── 9. COTAS VERTICAIS SEGMENTADAS (Laje Inf + Altura + Laje Sup) ────
    # Lado esquerdo (primeiro painel)
    def _dim_seg_v(x_base, segments, side='left'):
        """Cotas verticais segmentadas — robô pattern."""
        x_dim = x_base - DIM_H_RIGHT if side == 'left' else x_base + DIM_H_RIGHT
        y_cur = y0 - laje_inf
        for label, seg_h in segments:
            if seg_h <= 0:
                continue
            try:
                d = msp.add_linear_dim(
                    base=(x_dim, y_cur),
                    p1=(x_base, y_cur), p2=(x_base, y_cur + seg_h),
                    angle=90, dimstyle='PAINEL',
                    dxfattribs={'layer': 'COTA'})
                d.render()
            except Exception:
                pass
            y_cur += seg_h

    p0 = panels[0]
    h1_0, h2_0 = p0['height1'], p0['height2']
    lc_alt_0 = p0.get('laje_central_alt', 0)
    has_lc = (lc_alt_0 > 0) or (h1_0 > 0 and h2_0 > 0 and abs(h1_0 - h2_0) > 0.5)
    # Calcular alturas em espaço de desenho para as cotas segmentadas
    if lc_alt_0 > 0:
        total_real_0 = h1_0 + lc_alt_0 + h2_0
        _s0 = h / total_real_0 if (total_real_0 > h and total_real_0 > 0) else 1.0
        h1_0_d = h1_0 * _s0
        lc_h   = lc_alt_0 * _s0
        h2_0_d = h2_0 * _s0
    else:
        h1_0_d = h1_0
        h2_0_d = h2_0
        lc_h = (h - h1_0 - (h - h2_0)) if has_lc and h2_0 < h else 0
    seg_left = [
        ('Laje Inf', laje_inf),
        ('Altura 1', h1_0_d if has_lc else h),
        ('Laje Central', max(lc_h, 0)),
        ('Altura 2', h2_0_d if has_lc else 0),
        ('Laje Sup', laje_sup),
    ]
    _dim_seg_v(x0, seg_left, 'left')

    # Lado direito (último painel) — cota total
    dim_h_lateral(msp, x0 + comprimento, y0 - laje_inf,
                  h + laje_inf + laje_sup)

    # ── 10. ABERTURAS — retângulos fechados + hachura diagonal ────────────
    if holes:
        xr = x0 + comprimento
        for i, hole in enumerate(holes):
            if not hole.get('active'):
                continue
            hw = float(hole.get('width', 0))
            hh = float(hole.get('height', 0))
            hdist = float(hole.get('position', 0))
            if hw <= 0 or hh <= 0:
                continue
            # 4 cantos: 0=sup-esq, 1=inf-esq, 2=sup-dir, 3=inf-dir
            if i == 0:    hx, hy = x0, y0 + h - hdist - hh
            elif i == 1:  hx, hy = x0, y0 + hdist
            elif i == 2:  hx, hy = xr - hw, y0 + h - hdist - hh
            elif i == 3:  hx, hy = xr - hw, y0 + hdist
            else: continue
            pts = [(hx, hy), (hx+hw, hy), (hx+hw, hy+hh), (hx, hy+hh)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'Painéis', 'linetype': 'DASHED'})
            ht = msp.add_hatch(dxfattribs={'layer': 'COTA'})
            ht.set_pattern_fill('ANSI31', scale=0.5)
            ht.paths.add_polyline_path(pts, is_closed=True)
            add_text(msp, hx + hw/2, hy + hh/2, f'{hw:.0f}x{hh:.0f}',
                     7.0, '5', halign=1, valign=2)

    return comprimento


# ──────────────────────────────────────────────────────────────────────────────
# Viga lateral completa (seção + Face A + Face B)
# ──────────────────────────────────────────────────────────────────────────────

def draw_viga_lateral(msp, x_origin, y_top, viga_nome,
                      h_A, h_B, b, h_section=None, b_alma=19,
                      panels_A=None, panels_B=None,
                      holes_A=None, holes_B=None,
                      pillar_left_A=None, pillar_right_A=None,
                      pillar_left_B=None, pillar_right_B=None,
                      laje_sup=7.0, laje_inf=7.0):
    """Desenha uma viga lateral completa em uma linha horizontal.
    Posições: [Seção] [SECT_GAP] [Face A] [GAP_AB] [Face B]
    panels_A/panels_B: listas de dicts do JSON (larguras reais, alturas por painel).
    y_top: coordenada Y do topo dos painéis (base = y_top - h).
    Retorna (x_max, y_min) para tracking de limites.
    """
    h = max(h_A, h_B, 1.0)
    comp_A = sum(p['width'] for p in panels_A)
    comp_B = sum(p['width'] for p in panels_B)
    comprimento = max(comp_A, comp_B, 1.0)

    # Espaço dinâmico para seção (80cm extra à esquerda conforme STOG)
    sect_total = max(SECT_W + SECT_GAP, int(b) + 178)
    x_A = x_origin + sect_total
    x_sect_center = max(x_origin + 40, x_A - 124 - int(b))

    # Seção usa h_section (altura real do concreto), não h_A (altura do painel)
    h_sect = h_section if h_section else h_A
    y0_sect = y_top - h_A
    draw_section_detail(msp, x_sect_center, y0_sect, b, h_sect,
                        viga_nome=viga_nome, b_alma=b_alma)

    y0_A = y_top - h_A
    draw_lv_face(msp, x_A, y0_A, panels_A, h_A, f'{viga_nome}.A',
                 holes=holes_A,
                 pillar_left=pillar_left_A, pillar_right=pillar_right_A,
                 laje_sup=laje_sup, laje_inf=laje_inf)

    x_B  = x_A + comprimento + GAP_AB
    y0_B = y_top - h_B
    draw_lv_face(msp, x_B, y0_B, panels_B, h_B, f'{viga_nome}.B',
                 holes=holes_B,
                 pillar_left=pillar_left_B, pillar_right=pillar_right_B,
                 laje_sup=laje_sup, laje_inf=laje_inf)

    x_max = x_B + comprimento + DIM_H_RIGHT + 40
    y_min = min(y0_A, y0_B) - laje_inf - DIM_TOTAL_BELOW - 15
    return x_max, y_min


# ──────────────────────────────────────────────────────────────────────────────
# Cards de folha
# ──────────────────────────────────────────────────────────────────────────────

def draw_cards(msp, x0, y_bottom, obra_nome=''):
    """Desenha 2 blocos Folhas 1485×1050 (bordas + carimbo)."""
    for i in range(2):
        cx = x0 + i * (CARD_W + CARD_GAP)
        cy = y_bottom
        pts = [(cx, cy), (cx+CARD_W, cy), (cx+CARD_W, cy+CARD_H), (cx, cy+CARD_H)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': 'Folhas', 'lineweight': 50})
        cx2 = cx + CARD_IN_DX; cy2 = cy + CARD_IN_DY
        w2 = CARD_W - 2*CARD_IN_DX; h2 = CARD_H - 2*CARD_IN_DY
        msp.add_lwpolyline(
            [(cx2, cy2), (cx2+w2, cy2), (cx2+w2, cy2+h2), (cx2, cy2+h2)],
            close=True, dxfattribs={'layer': 'Folhas', 'lineweight': 25}
        )
        cab_h = 80
        msp.add_line((cx, cy+cab_h), (cx+CARD_W, cy+cab_h),
                     dxfattribs={'layer': 'CARIMBO', 'lineweight': 35})
        mid_x = cx + CARD_W / 2
        for txt, ty, th in [
            ('NOVA SISTEMAS CONSTRUTIVOS', cy+cab_h/2+30, 14),
            ('STOG',                       cy+cab_h/2+12, 12),
            (obra_nome,                    cy+cab_h/2-5,  12),
            ('LATERAL DE VIGAS',           cy+cab_h/2-22, 14),
        ]:
            msp.add_text(txt, dxfattribs={'insert': (mid_x, ty), 'height': th, 'layer': 'CARIMBO'})
        msp.add_text(str(i+1), dxfattribs={
            'insert': (cx+CARD_W-60, cy+cab_h/2), 'height': 40, 'layer': 'CARIMBO'})


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Gera LV DXF STOG-quality a partir de JSON_Vigas_Laterais/')
    parser.add_argument('--obra', required=True,
                        help='Caminho da obra (ex: DADOS-OBRAS/Obra_TREINO_21)')
    parser.add_argument('--max', type=int, default=999,
                        help='Máximo de vigas a processar')
    parser.add_argument('--simulate', action='store_true',
                        help='Injeta dados de teste na 1a viga (aberturas, pilares, h1!=h2)')
    args = parser.parse_args()

    obra_path = Path(args.obra)
    lv_dir    = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Laterais'
    vs_path   = obra_path / 'Fase-4_Sincronizacao' / 'vigas_salvas.json'
    out_dir   = obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    vigas_salvas = {}
    if vs_path.exists():
        vigas_salvas = json.load(open(vs_path, encoding='utf-8'))

    # Coletar arquivos V*_A.json e encontrar parceiro V*_B.json
    a_files = sorted(
        lv_dir.glob('V*_A.json'),
        key=lambda p: (re.search(r'\d+', p.stem).group().zfill(5), p.stem)
    )[:args.max]

    if not a_files:
        print(f'[ERRO] Nenhum V*_A.json em {lv_dir}')
        return

    vigas = []
    for af in a_files:
        # Nome base: V22_A → V22, V13B_A → V13B
        vname = re.sub(r'_A$', '', af.stem)
        bf    = af.parent / f'{vname}_B.json'

        da = json.load(open(af, encoding='utf-8'))
        db = json.load(open(bf, encoding='utf-8')) if bf.exists() else da

        # b (largura da flange/mesa): prioridade vigas_salvas → JSON total_width
        b = float(vigas_salvas.get(vname, {}).get('b', da.get('total_width', 14)))
        # b_alma (largura da alma para título): JSON total_width
        b_alma = float(da.get('total_width', b))

        # Comprimento: soma dos widths dos painéis
        comp_A = sum(float(p.get('width', 0)) for p in da.get('panels', []))
        comp_B = sum(float(p.get('width', 0)) for p in db.get('panels', []))
        comprimento = max(comp_A, comp_B, 1.0)

        # h_section: altura da seção de concreto = vigas_salvas.h / 2
        # (vigas_salvas.h = altura total de fôrma; seção = metade)
        # V22: h_salvas=120 → h_section=60 → STOG mostra (19x60) ✓
        h_raw = float(vigas_salvas.get(vname, {}).get('h', da.get('total_height', 38)))
        h_section = h_raw / 2.0
        # STOG panel heights derivados da seção: Face A = h_section + 4, Face B = h_section - 10
        h_A = h_section + 4   # painel A (lado da flange/laje) = mais alto
        h_B = max(h_section - 10, 10)  # painel B (lado do web/tensor) = mais baixo, min 10cm

        # Extrair painéis reais do JSON (larguras REAIS, não módulo fixo)
        # Propagar laje_central_alt da raiz do JSON para cada painel
        lca_A = float(da.get('laje_central_alt', 0) or 0)
        lca_B = float(db.get('laje_central_alt', 0) or 0)
        panels_A = extract_panels_from_json(da.get('panels', []), lca_A)
        panels_B = extract_panels_from_json(db.get('panels', []), lca_B)

        # Extrair pilares/obstáculos do JSON
        pl_A = da.get('pillar_left', {})
        pr_A = da.get('pillar_right', {})
        pl_B = db.get('pillar_left', {})
        pr_B = db.get('pillar_right', {})

        if comprimento > 0 and (h_A > 0 or h_B > 0) and (panels_A or panels_B):
            # Se falta um lado, usar o outro como fallback
            if not panels_A:
                panels_A = panels_B
            if not panels_B:
                panels_B = panels_A
            vigas.append({
                'nome':     vname,
                'b':        b,
                'b_alma':   b_alma,
                'comp':     comprimento,
                'h_section': h_section,
                'h_A':      max(h_A, 1.0),
                'h_B':      max(h_B, 1.0),
                'holes_A':  da.get('holes', []),
                'holes_B':  db.get('holes', []),
                'panels_A': panels_A,
                'panels_B': panels_B,
                'pl_A': pl_A, 'pr_A': pr_A,
                'pl_B': pl_B, 'pr_B': pr_B,
            })

    if not vigas:
        print('[ERRO] Nenhuma viga válida encontrada'); return

    # ── Injetar dados de simulação na 1ª viga (--simulate) ─────────────
    if args.simulate and vigas:
        v0 = vigas[0]
        print(f'[SIMULATE] Injetando dados de teste em {v0["nome"]}')
        # Aberturas: 4 cantos com tamanhos diferentes
        v0['holes_A'] = [
            {'active': True, 'width': 15, 'height': 10, 'position': 5},   # sup-esq
            {'active': True, 'width': 12, 'height': 8,  'position': 3},   # inf-esq
            {'active': True, 'width': 15, 'height': 10, 'position': 5},   # sup-dir
            {'active': True, 'width': 12, 'height': 8,  'position': 3},   # inf-dir
        ]
        # Pilares/obstáculos
        v0['pl_A'] = {'active': True, 'width': 20, 'length': 10}
        v0['pr_A'] = {'active': True, 'width': 25, 'length': 15}
        # h1 != h2 no segundo painel (laje central)
        if len(v0['panels_A']) >= 2:
            v0['panels_A'][1]['height1'] = v0['h_A'] * 0.6
            v0['panels_A'][1]['height2'] = v0['h_A'] * 0.8

    # Ordenar por b desc, comprimento desc (igual ao FV)
    vigas.sort(key=lambda v: (-v['b'], -v['comp']))
    print(f'Processando {len(vigas)} vigas laterais → LV_stog_quality.dxf')

    doc = setup_doc()
    msp = doc.modelspace()

    # ── Posicionamento ──────────────────────────────────────────────────────
    # Vigas empilhadas de cima para baixo (y_top decresce a cada viga)
    # Primeira viga: topo em y=0, base em y=-h_max
    y_cursor    = 0.0
    x_max_all   = 0.0
    y_min_all   = 0.0

    for v in vigas:
        panels_A = v['panels_A']
        panels_B = v['panels_B']
        if not panels_A:
            continue

        h_max = max(v['h_A'], v['h_B'])
        n_panels = max(len(panels_A), len(panels_B))
        pw_list = [f"{p['width']:.0f}" for p in panels_A]

        # y_top para esta viga: topos alinhados ao y_cursor
        x_max, y_min = draw_viga_lateral(
            msp,
            x_origin  = 0.0,
            y_top     = y_cursor,
            viga_nome = v['nome'],
            h_A       = v['h_A'],
            h_B       = v['h_B'],
            b         = v['b'],
            h_section = v.get('h_section'),
            b_alma    = v.get('b_alma', v['b']),
            panels_A  = panels_A,
            panels_B  = panels_B,
            holes_A   = v.get('holes_A'),
            holes_B   = v.get('holes_B'),
            pillar_left_A  = v.get('pl_A'),
            pillar_right_A = v.get('pr_A'),
            pillar_left_B  = v.get('pl_B'),
            pillar_right_B = v.get('pr_B'),
        )

        print(f'  {v["nome"]:8s}: comp={v["comp"]:.0f}cm  '
              f'h_A={v["h_A"]:.0f}  h_B={v["h_B"]:.0f}  '
              f'b={v["b"]:.0f}  painéis={n_panels}  widths=[{",".join(pw_list)}]')

        x_max_all = max(x_max_all, x_max)
        y_min_all = min(y_min_all, y_min)

        # Próxima viga: desce h_max + NOM_ABOVE + DIM_TOTAL_BELOW + GAP_ROW_LV
        y_cursor -= h_max + NOM_ABOVE + DIM_TOTAL_BELOW + GAP_ROW_LV

    # ── Cards de folha acima das vigas ─────────────────────────────────────
    obra_nome = obra_path.name.replace('_', ' ')
    draw_cards(msp, 0, CARD_Y_GAP, obra_nome=obra_nome)

    # ── Salvar DXF ─────────────────────────────────────────────────────────
    import time
    ts = time.strftime('%H%M%S')
    out_dxf = out_dir / f'LV_stog_{ts}.dxf'
    try:
        doc.saveas(str(out_dxf))
    except PermissionError:
        out_dxf = out_dir / f'LV_stog_{ts}_b.dxf'
        doc.saveas(str(out_dxf))
    print(f'\nDXF: {out_dxf}')

    # ── PNG preview ─────────────────────────────────────────────────────────
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        # Estimar primeira viga para zoom de detalhe
        v0 = vigas[0]
        h0 = max(v0['h_A'], v0['h_B'])
        y_first_bot = -(h0 + DIM_TOTAL_BELOW + 20)

        fig, axes = plt.subplots(1, 2, figsize=(28, 12), facecolor='#0a0a14')
        views = [
            # Primeiras 4 vigas
            ((-50, min(x_max_all + 50, 3000)),
             (y_cursor + (len(vigas)-4)*(h0+GAP_ROW_LV) - 50, 60),
             f'Detalhe — primeiras vigas'),
            # Vista completa
            ((-50, max(x_max_all + 50, CARD_W*2 + CARD_GAP + 100)),
             (y_min_all - 50, CARD_Y_GAP + CARD_H + 50),
             f'Vista completa — {len(vigas)} vigas'),
        ]
        for ax, (xlim, ylim, title) in zip(axes, views):
            ax.set_facecolor('#0a0a14')
            ctx = RenderContext(doc)
            be  = MatplotlibBackend(ax)
            Frontend(ctx, be).draw_layout(msp, finalize=True)
            ax.set_xlim(*xlim); ax.set_ylim(*ylim)
            ax.set_aspect('equal', adjustable='box')
            ax.set_title(title, color='white', fontsize=9, pad=4)

        plt.tight_layout()
        out_png = out_dir / 'LV_stog_quality.png'
        plt.savefig(str(out_png), dpi=120, bbox_inches='tight', facecolor='#0a0a14')
        plt.close()
        print(f'Preview: {out_png}')
    except Exception as ex:
        print(f'[WARN] PNG: {ex}')


if __name__ == '__main__':
    main()
