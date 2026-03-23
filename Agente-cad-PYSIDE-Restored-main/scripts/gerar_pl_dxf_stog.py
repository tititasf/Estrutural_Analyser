#!/usr/bin/env python3
"""
gerar_pl_dxf_stog.py — Gerador STOG-quality PL DXF (sem AutoCAD)
=================================================================
Replica fiel ao padrão STOG:
  - Layers idênticos ao original (Hachura, Painéis, Madeira, CHAPA, Perfil Metálico, ...)
  - CIMA: seção transversal com pilar + chapas + madeiras + perfis metálicos + faces A/B/C/D
  - FACES: elevação com hachura AR-CONC + Painéis + REAPROVEITAMENTO + cotas
  - CARIMBO: título com CLIENTE, OBRA, PAVIMENTO, PROJETO + número da folha
  - Grid 4 colunas × N linhas (layout idêntico ao STOG PL)

Uso:
  python scripts/gerar_pl_dxf_stog.py --obra DADOS-OBRAS/Obra_TREINO_21
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import json, argparse
from pathlib import Path
import ezdxf

# ── Espessuras constantes (cm) ────────────────────────────────────────────────
T_CHAPA   = 1.2   # espessura da chapa compensada
T_MADEIRA = 2.0   # sarrafo de madeira (externo)
T_PERFIL  = 1.5   # espessura do perfil metálico (gravata)
T_EXT     = 3.0   # extensão lateral do perfil além do painel (cada lado)
SW        = 2.0   # largura do sarrafo (seção)

# ── Escalas de desenho ────────────────────────────────────────────────────────
CIMA_SCALE   = 1.0   # seção transversal (1 cm real → 1 DXF cm) — compacto como STOG
FACE_H_SCALE = 0.4   # escala vertical das faces (pilar 280cm → 112 DXF cm)
FACE_W_SCALE = 0.5   # escala horizontal das faces (face 60cm → 30 DXF cm)

# ── Layout do card ────────────────────────────────────────────────────────────
# Estrutura STOG: TITULO(top) | CIMA(esq) + FACES_ABCD(dir) | CARIMBO(bottom)
CARD_GAP_X   = 50    # gap horizontal entre cards
CARD_GAP_Y   = 60    # gap vertical entre cards
COLS         = 4
CARIMBO_H    = 35    # altura do carimbo (rodapé)
TITULO_H     = 28    # altura do título (topo: nome + seção)
CIMA_PAD     = 12    # padding ao redor da CIMA
FACE_PAD_X   = 10    # padding lateral antes da primeira face e após a última
FACE_PAD_Y   = 20    # padding superior/inferior das faces (para labels + cotas)
FACE_GAP     =  8    # gap entre faces lado a lado
DIM_OFFSET   = 16    # afastamento da cota da borda do elemento
CIMA_AREA_W_EXTRA = 20  # espaço extra na área CIMA para labels A/B/C/D e cotas

# ── Cores ACI (idênticas ao STOG original) ───────────────────────────────────
LAYERS = {
    'Hachura':          251,
    'Painéis':          200,
    'Madeira':          126,
    'CHAPA':              1,
    'Perfil Metálico':  224,
    'SARRAFO':          251,
    'SARR_2.2x7':        40,   # sarrafo padrão (931 entities no STOG real)
    'SARR_2.2x10':       60,   # sarrafo de amarração
    'SARR_3.5x7':        81,   # sarrafo especial
    'SARR_7x7':          34,   # sarrafo de reforço
    'COTA':             241,
    'REAPROVEITAMENTO': 251,
    'Nível':            160,
    'COTAS FURACAO':      16,   # marcas de furos de parafuso nos pontaletes
    'NOMENCLATURA':       7,   # nome do pilar na lateral
    'Texto Seção':        7,   # textos descritivos na seção
    'texto':              7,   # textos legacy (142 no STOG real)
    'MEIO_PONT':         40,   # meio-pontalete entities diretas (59 no STOG)
    'SARRAFO DE PRESSAO': 42,  # sarrafos de pressão (41 no STOG)
    'NIVEL 2° PAV.':    160,   # nível do pavimento (38 no STOG)
    'Sarr 2.2x7':        40,   # variante layer name (21 no STOG)
    'CONCRETO':          251,   # concreto entity (2 no STOG)
    'Folhas':           255,
    'CARIMBO':          255,
    'TEXTO_GERAL':        7,
    'Sarrafo de Pressão': 42,
    'Defpoints':          7,
}


def setup_doc():
    doc = ezdxf.new('R2018')
    doc.header['$INSUNITS'] = 5   # cm
    for lname, color in LAYERS.items():
        if lname not in doc.layers:
            doc.layers.add(lname, color=color)

    # ── Blocos PONTALETE e MEIO PONTALETE (eng. reversa STOG) ────────────────
    # PONTALETE: retângulo 7×7 + 3 ARCs + 3 LINEs (seção tubo circular)
    if 'PONTALETE' not in doc.blocks:
        blk = doc.blocks.new(name='PONTALETE')
        blk.add_lwpolyline([(0,0),(7,0),(7,7),(0,7)], close=True,
                           dxfattribs={'layer': 'Madeira'})
        blk.add_arc(center=(-0.21,-0.78), radius=3.09, start_angle=14.6, end_angle=86.0,
                    dxfattribs={'layer': 'Madeira'})
        blk.add_arc(center=(1.09,0.90), radius=3.19, start_angle=343.6, end_angle=110.0,
                    dxfattribs={'layer': 'Madeira'})
        blk.add_arc(center=(2.04,0.06), radius=6.23, start_angle=37.3, end_angle=109.1,
                    dxfattribs={'layer': 'Madeira'})
        blk.add_line((0,0),(7,5.76), dxfattribs={'layer': 'Madeira'})
        blk.add_line((0,0),(7,1.74), dxfattribs={'layer': 'Madeira'})
        blk.add_line((0,0),(2.71,7), dxfattribs={'layer': 'Madeira'})

    # MEIO PONTALETE: retângulo 3.5×7 + 3 ARCs + 3 LINEs
    if 'MEIO PONTALETE' not in doc.blocks:
        blk = doc.blocks.new(name='MEIO PONTALETE')
        blk.add_lwpolyline([(0,0),(3.5,0),(3.5,7),(0,7)], close=True,
                           dxfattribs={'layer': 'Madeira'})
        blk.add_arc(center=(-0.21,-0.78), radius=3.09, start_angle=14.6, end_angle=86.0,
                    dxfattribs={'layer': 'Madeira'})
        blk.add_arc(center=(1.09,0.90), radius=3.19, start_angle=40.9, end_angle=110.0,
                    dxfattribs={'layer': 'Madeira'})
        blk.add_arc(center=(2.04,0.06), radius=6.23, start_angle=76.4, end_angle=109.1,
                    dxfattribs={'layer': 'Madeira'})
        blk.add_line((0,0),(3.5,2.88), dxfattribs={'layer': 'Madeira'})
        blk.add_line((0,0),(3.5,0.87), dxfattribs={'layer': 'Madeira'})
        blk.add_line((0,0),(2.71,7), dxfattribs={'layer': 'Madeira'})

    # ── Bloco C (hachura concreto — eng. reversa STOG, simplificado) ──────────
    if 'C' not in doc.blocks:
        blk = doc.blocks.new(name='C')
        import math
        # Pattern de linhas diagonais simulando AR-CONC (5.9×6.4 unidades)
        for i in range(8):
            y = -3.2 + i * 0.9
            blk.add_line((0, y), (5.9, y + 2.5), dxfattribs={'layer': 'Hachura'})
        for i in range(6):
            x = i * 1.0
            blk.add_arc(center=(x, 0), radius=1.5, start_angle=30+i*20, end_angle=150+i*10,
                        dxfattribs={'layer': 'Hachura'})

    return doc


# ── Primitivas ────────────────────────────────────────────────────────────────

def rect(msp, x0, y0, w, h, layer, lw=None):
    attribs = {'layer': layer}
    if lw:
        attribs['lineweight'] = lw
    pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
    return msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)


def hatch_rect(msp, x0, y0, w, h, layer, pattern='AR-CONC', scale=3.0):
    pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    hatch.paths.add_polyline_path(pts, is_closed=True)
    hatch.set_pattern_fill(pattern, scale=scale)
    return hatch


def hatch_solid(msp, x0, y0, w, h, layer):
    """Hachura sólida (solid fill)."""
    pts = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    hatch.paths.add_polyline_path(pts, is_closed=True)
    hatch.set_solid_fill()
    return hatch


def text(msp, x, y, txt, height=10, layer='TEXTO_GERAL', anchor='LEFT'):
    msp.add_text(txt, dxfattribs={
        'layer': layer,
        'insert': (x, y),
        'height': height,
    })


def mtext(msp, x, y, txt, height=10, layer='TEXTO_GERAL', anchor=5):
    msp.add_mtext(txt, dxfattribs={
        'layer': layer,
        'insert': (x, y),
        'char_height': height,
        'attachment_point': anchor,
    })


def dim_h(msp, x0, x1, y_base, layer='COTA'):
    try:
        d = msp.add_linear_dim(
            base=(x0, y_base), p1=(x0, y_base + 5), p2=(x1, y_base + 5),
            angle=0, dxfattribs={'layer': layer}
        )
        d.render()
    except Exception:
        pass


def dim_v(msp, y0, y1, x_base, layer='COTA'):
    try:
        d = msp.add_linear_dim(
            base=(x_base, y0), p1=(x_base - 5, y0), p2=(x_base - 5, y1),
            angle=90, dxfattribs={'layer': layer}
        )
        d.render()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# CIMA — Seção transversal vista de cima (ampliada)
# ─────────────────────────────────────────────────────────────────────────────

def draw_cima(msp, cx, cy, comp, larg, g1, nome, tipo_especial=None,
              comp2=0, larg2=0):
    """
    cx, cy  : centro da vista CIMA no DXF
    comp    : comprimento do pilar (face A/C), já em escala CIMA_SCALE
    larg    : largura do pilar (face B/D), já em escala CIMA_SCALE
    g1      : grade_1 em cm (distância gravata), já em escala CIMA_SCALE
    tipo_especial: "L", "T", "U" ou None
    comp2, larg2: dimensões do segundo segmento (pilares especiais)
    """
    # ── Pilar especial L/T/U: polígono composto ─────────────────────────────
    if tipo_especial == 'L' and comp2 > 0 and larg2 > 0:
        # Polígono em L: retângulo principal + retângulo secundário no canto
        pts = [
            (cx - comp/2, cy - larg/2),
            (cx + comp/2, cy - larg/2),
            (cx + comp/2, cy - larg/2 + larg2),
            (cx - comp/2 + comp2, cy - larg/2 + larg2),
            (cx - comp/2 + comp2, cy + larg/2),
            (cx - comp/2, cy + larg/2),
        ]
        msp.add_lwpolyline(pts, close=True,
                           dxfattribs={'layer': 'Painéis', 'lineweight': 50})
        hatch = msp.add_hatch(dxfattribs={'layer': 'Hachura'})
        hatch.set_pattern_fill('AR-CONC', scale=0.5)
        hatch.paths.add_polyline_path(pts, is_closed=True)
        mtext(msp, cx, cy, f'{nome}\n({tipo_especial})',
              height=6, layer='TEXTO_GERAL', anchor=5)
        return
    elif tipo_especial in ('T', 'U') and comp2 > 0:
        # T/U: marcar com label (geometria completa requer mais dados)
        hc = comp / 2; hl = larg / 2
        rect(msp, cx-hc, cy-hl, comp, larg, 'Painéis', lw=50)
        mtext(msp, cx, cy + hl + 5, f'ESPECIAL {tipo_especial}',
              height=5, layer='TEXTO_GERAL', anchor=8)
        # Continua com renderização retangular padrão abaixo
    hc = comp / 2
    hl = larg / 2
    tc = T_CHAPA  * CIMA_SCALE
    tm = T_MADEIRA * CIMA_SCALE
    tp = T_PERFIL * CIMA_SCALE
    te = T_EXT    * CIMA_SCALE

    # 1. Núcleo do pilar (concreto) — hachura + bloco C (STOG: 240 INSERTs)
    hatch_rect(msp, cx-hc, cy-hl, comp, larg, 'COTA', 'AR-CONC', scale=2.5)
    rect(msp, cx-hc, cy-hl, comp, larg, 'Painéis', lw=35)
    # Blocos C (hachura detalhada concreto — 4 cantos + centro como STOG)
    c_scale = max(1.0, min(comp, larg) / 6.0)
    for dx, dy, sx in [(0, 0, c_scale), (comp, 0, -c_scale),
                        (0, larg, -c_scale), (comp, larg, c_scale),
                        (comp/2, larg/2, c_scale)]:
        msp.add_blockref('C', (cx - hc + dx, cy - hl + dy),
                         dxfattribs={'layer': 'Hachura',
                                     'xscale': sx, 'yscale': c_scale})

    # 2. Chapas compensadas em todas as 4 faces (externas ao núcleo)
    # Chapas face A e C (horizontais, cobrindo comp + chapa B/D)
    rect(msp, cx-hc-tc, cy-hl-tc, comp+2*tc, tc, 'CHAPA', lw=18)  # Face A chapa
    hatch_rect(msp, cx-hc-tc, cy-hl-tc, comp+2*tc, tc, 'Hachura', 'ANSI31', scale=1.5)
    rect(msp, cx-hc-tc, cy+hl,     comp+2*tc, tc, 'CHAPA', lw=18)  # Face C chapa
    hatch_rect(msp, cx-hc-tc, cy+hl, comp+2*tc, tc, 'Hachura', 'ANSI31', scale=1.5)
    # Chapas face B e D (verticais)
    rect(msp, cx-hc-tc, cy-hl,    tc, larg, 'CHAPA', lw=18)  # Face B chapa
    hatch_rect(msp, cx-hc-tc, cy-hl, tc, larg, 'Hachura', 'ANSI31', scale=1.5)
    rect(msp, cx+hc,    cy-hl,    tc, larg, 'CHAPA', lw=18)  # Face D chapa
    hatch_rect(msp, cx+hc, cy-hl, tc, larg, 'Hachura', 'ANSI31', scale=1.5)

    # 3. Sarrafos de madeira (externos às chapas) + hachura ANSI31
    sw2 = SW * CIMA_SCALE
    ext = tc + tm
    rect(msp, cx-hc-ext, cy-hl-tc-tm, comp+2*ext, tm, 'Madeira', lw=18)  # Face A
    hatch_rect(msp, cx-hc-ext, cy-hl-tc-tm, comp+2*ext, tm, 'Hachura', 'ANSI31', scale=1.0)
    rect(msp, cx-hc-ext, cy+hl+tc,    comp+2*ext, tm, 'Madeira', lw=18)  # Face C
    hatch_rect(msp, cx-hc-ext, cy+hl+tc, comp+2*ext, tm, 'Hachura', 'ANSI31', scale=1.0)
    rect(msp, cx-hc-tc-tm, cy-hl,   tm, larg, 'Madeira', lw=18)   # Face B
    hatch_rect(msp, cx-hc-tc-tm, cy-hl, tm, larg, 'Hachura', 'ANSI31', scale=1.0)
    rect(msp, cx+hc+tc,    cy-hl,   tm, larg, 'Madeira', lw=18)   # Face D
    hatch_rect(msp, cx+hc+tc, cy-hl, tm, larg, 'Hachura', 'ANSI31', scale=1.0)

    # 4. Perfis metálicos (gravatas) — 2 pares horizontal/vertical
    gx0 = cx - hc - ext - tp - te
    gw  = comp + 2*ext + 2*tp + 2*te
    # Gravata A (inferior — ao longo de comp, centrada na largura total)
    rect(msp, gx0, cy-hl-tc-tm-tp, gw, tp, 'Perfil Metálico', lw=50)
    rect(msp, gx0, cy+hl+tc+tm,    gw, tp, 'Perfil Metálico', lw=50)
    # Perfis laterais (ao longo de larg)
    gy0 = cy - hl - tc - tm - tp
    gh  = larg + 2*tc + 2*tm + 2*tp
    rect(msp, cx-hc-ext-tp-te, gy0, tp, gh, 'Perfil Metálico', lw=50)
    rect(msp, cx+hc+ext+te,    gy0, tp, gh, 'Perfil Metálico', lw=50)

    # 5. Sarrafos pontos de apoio (nos cantos) — SARR_2.2x7 padrão
    for sx in [cx-hc-tc-tm, cx+hc+tc]:
        for sy in [cy-hl-tc, cy+hl]:
            rect(msp, sx, sy, tm, tc, 'SARR_2.2x7')

    # 6. Labels das faces ao redor da seção
    offx = hc + ext + tp + te + 12
    offy = hl + tc + tm + tp + 12
    face_lbl_h = max(8, larg * 0.15)
    mtext(msp, cx,           cy - offy, 'A', height=face_lbl_h, layer='TEXTO_GERAL', anchor=8)
    mtext(msp, cx - offx,    cy,        'B', height=face_lbl_h, layer='TEXTO_GERAL', anchor=6)
    mtext(msp, cx,           cy + offy, 'C', height=face_lbl_h, layer='TEXTO_GERAL', anchor=2)
    mtext(msp, cx + offx,    cy,        'D', height=face_lbl_h, layer='TEXTO_GERAL', anchor=4)

    # 7. Dimensões da seção (múltiplas cotas — padrão STOG ~30/pilar)
    cota_y = cy - hl - tc - tm - tp - DIM_OFFSET
    dim_h(msp, cx-hc, cx+hc, cota_y, 'COTA')                         # comprimento pilar
    dim_h(msp, cx-hc-tc, cx+hc+tc, cota_y - 12, 'COTA')              # comp + chapas
    dim_h(msp, cx-hc-ext, cx+hc+ext, cota_y - 24, 'COTA')            # comp + chapas + madeira
    cota_x = cx + hc + ext + tp + te + DIM_OFFSET
    dim_v(msp, cy-hl, cy+hl, cota_x, 'COTA')                         # largura pilar
    dim_v(msp, cy-hl-tc, cy+hl+tc, cota_x + 12, 'COTA')              # larg + chapas
    dim_v(msp, cy-hl-tc-tm, cy+hl+tc+tm, cota_x + 24, 'COTA')        # larg + chapas + madeira

    # 8. Seção (comp×larg) no centro — discreta, sem dominar
    secao = f'{comp/CIMA_SCALE:.0f}x{larg/CIMA_SCALE:.0f}'
    mtext(msp, cx, cy, secao, height=max(4, larg * 0.12), layer='COTA', anchor=5)


# ─────────────────────────────────────────────────────────────────────────────
# Face view — elevação de 1 face do pilar
# ─────────────────────────────────────────────────────────────────────────────

def draw_face(msp, fx, fy, face_w, h1, h2, h3, face_label):
    """
    fx, fy      : canto inferior esquerdo da face
    face_w      : largura da face (escala FACE_W_SCALE já aplicada)
    h1/h2/h3    : alturas dos segmentos (escala FACE_H_SCALE já aplicada)
    face_label  : ex: 'P1.A'
    """
    total_h = h1 + h2 + h3
    if total_h <= 0 or face_w <= 0:
        return total_h

    # ── Segmentos do painel (de baixo para cima) ──
    y_cur = fy

    # h1 (base/fechamento) — AR-CONC hatch, sem REAPROVEITAMENTO
    if h1 > 0:
        rect(msp, fx, y_cur, face_w, h1, 'Painéis', lw=18)
        hatch_rect(msp, fx, y_cur, face_w, h1, 'COTA', 'AR-CONC', scale=2.0)
        y_cur += h1

    # h2 (painel principal) — AR-CONC fill da face + contorno Painéis
    if h2 > 0:
        rect(msp, fx, y_cur, face_w, h2, 'Painéis', lw=35)
        hatch_rect(msp, fx, y_cur, face_w, h2, 'Hachura', 'AR-CONC', scale=4.0)
        y_cur += h2

    # h3 (fechamento topo) — AR-CONC + REAPROVEITAMENTO (reuso)
    if h3 > 0:
        rect(msp, fx, y_cur, face_w, h3, 'Painéis', lw=18)
        hatch_rect(msp, fx, y_cur, face_w, h3, 'COTA', 'AR-CONC', scale=2.0)
        hatch_rect(msp, fx, y_cur, face_w, h3, 'REAPROVEITAMENTO', 'ANSI31', scale=2.5)

    # ── Linhas de sarrafo separando segmentos (SARR_2.2x7 padrão) ──
    if h1 > 0 and h2 > 0:
        msp.add_line((fx, fy+h1), (fx+face_w, fy+h1),
                     dxfattribs={'layer': 'SARR_2.2x7', 'lineweight': 35})
    if h2 > 0 and h3 > 0:
        msp.add_line((fx, fy+h1+h2), (fx+face_w, fy+h1+h2),
                     dxfattribs={'layer': 'SARR_2.2x7', 'lineweight': 35})

    # ── Linha de nível (horizontal tracejada no topo) ──
    msp.add_line((fx - 8, fy + total_h), (fx + face_w + 8, fy + total_h),
                 dxfattribs={'layer': 'Nível', 'linetype': 'DASHED'})
    msp.add_line((fx - 8, fy), (fx + face_w + 8, fy),
                 dxfattribs={'layer': 'Nível', 'linetype': 'DASHED'})

    # ── Dimensões ──
    dim_y = fy - DIM_OFFSET
    dim_h(msp, fx, fx + face_w, dim_y, 'COTA')   # largura da face
    dim_x = fx + face_w + DIM_OFFSET
    if h1 > 0:
        dim_v(msp, fy, fy+h1, dim_x, 'COTA')
    if h2 > 0:
        dim_v(msp, fy+h1, fy+h1+h2, dim_x, 'COTA')
    if h3 > 0:
        dim_v(msp, fy+h1+h2, fy+total_h, dim_x, 'COTA')

    # ── Label da face acima ──
    lbl_h = max(7, face_w * 0.12)
    mtext(msp, fx + face_w/2, fy + total_h + FACE_PAD_Y * 0.5,
          face_label, height=lbl_h, layer='TEXTO_GERAL', anchor=8)

    # ── Texto Seção: dimensões de cada segmento (STOG: 212 entities) ──
    txt_h = max(3.5, face_w * 0.06)
    h1_real = h1 / FACE_H_SCALE if h1 > 0 else 0
    h2_real = h2 / FACE_H_SCALE if h2 > 0 else 0
    h3_real = h3 / FACE_H_SCALE if h3 > 0 else 0
    fw_real = face_w / FACE_W_SCALE

    # Texto dentro de cada segmento (centralizado)
    if h1 > 0:
        mtext(msp, fx + face_w/2, fy + h1/2,
              f'{h1_real:.0f}', height=txt_h, layer='Texto Seção', anchor=5)
    if h2 > 0:
        mtext(msp, fx + face_w/2, fy + h1 + h2/2,
              f'{h2_real:.0f}', height=txt_h, layer='Texto Seção', anchor=5)
    if h3 > 0:
        mtext(msp, fx + face_w/2, fy + h1 + h2 + h3/2,
              f'{h3_real:.0f}', height=txt_h, layer='Texto Seção', anchor=5)

    # Texto lateral: largura da face (layer 'texto')
    mtext(msp, fx - 3, fy + total_h/2,
          f'{fw_real:.0f}', height=txt_h, layer='TEXTO_GERAL', anchor=6)

    # Texto de altura total à direita (layer 'texto')
    total_real = h1_real + h2_real + h3_real
    mtext(msp, fx + face_w + DIM_OFFSET + 8, fy + total_h/2,
          f'{total_real:.0f}', height=txt_h, layer='TEXTO_GERAL', anchor=4)

    return total_h


# ─────────────────────────────────────────────────────────────────────────────
# CARIMBO — rodapé do card
# ─────────────────────────────────────────────────────────────────────────────

def draw_carimbo(msp, x0, y0, w, h, obra_nome, folha_num):
    """
    Desenha carimbo na base do card.
    x0, y0: canto inferior esquerdo; w, h: largura e altura
    """
    rect(msp, x0, y0, w, h, 'Folhas', lw=35)

    # Linhas divisórias
    col_w = w * 0.20
    msp.add_line((x0 + col_w, y0), (x0 + col_w, y0 + h),
                 dxfattribs={'layer': 'Folhas'})

    # Número da folha
    mtext(msp, x0 + w - 15, y0 + h/2, str(folha_num),
          height=12, layer='CARIMBO', anchor=5)

    # Textos
    lbl_h = 5
    val_h = 7
    row_h = h / 4
    labels = [
        ('CLIENTE:', 'NOVA SISTEMAS CONSTRUTIVOS'),
        ('OBRA:',    obra_nome[:20]),
        ('PAVIMENTO:', ''),
        ('PROJETO:', 'PILARES'),
    ]
    for i, (lbl, val) in enumerate(labels):
        yy = y0 + h - (i + 1) * row_h + row_h * 0.25
        text(msp, x0 + col_w + 3, yy + val_h * 0.6, val, height=val_h, layer='TEXTO_GERAL')
        text(msp, x0 + col_w + 3, yy - lbl_h * 0.2, lbl, height=lbl_h, layer='TEXTO_GERAL')


# ─────────────────────────────────────────────────────────────────────────────
# Card completo: CIMA + Faces A/B/C/D + CARIMBO
# ─────────────────────────────────────────────────────────────────────────────

def _cima_dims(comp, larg):
    """Retorna dimensões do bloco CIMA (incluindo chapas, madeiras, perfis, padding, cotas)."""
    sc   = CIMA_SCALE
    tc   = T_CHAPA   * sc
    tm   = T_MADEIRA * sc
    tp   = T_PERFIL  * sc
    te   = T_EXT     * sc
    cc   = comp * sc   # comprimento do pilar em DXF
    cl   = larg * sc   # largura do pilar em DXF
    # extensão total além do núcleo (cada lado, horizontal/vertical)
    ext  = tc + tm
    # largura/altura do bloco CIMA inteiro (seção + chapas + madeiras + perfis)
    blk_w = cc + 2*(tc + tm + tp + te)
    blk_h = cl + 2*(tc + tm + tp)
    # área necessária para o bloco + labels A/B/C/D + cotas + padding
    area_w = blk_w + 2*CIMA_PAD + DIM_OFFSET + CIMA_AREA_W_EXTRA
    area_h = blk_h + 2*CIMA_PAD + DIM_OFFSET + CIMA_AREA_W_EXTRA
    return cc, cl, area_w, area_h


def generate_card(msp, pj, card_x, card_y, folha_num=1, obra_nome=''):
    """
    Layout STOG:
        ┌─────────────────────────────────────────┐  ← card_y + CARD_H
        │  TÍTULO (pilar nome + seção)             │  TITULO_H
        ├──────────┬──────────────────────────────┤
        │  CIMA    │  A      B      C      D       │  mid_h
        │ (seção   │ face   face   face   face      │
        │  topo)   │ (alta) (alta) (alta) (alta)   │
        ├──────────┴──────────────────────────────┤
        │  CARIMBO                                 │  CARIMBO_H
        └─────────────────────────────────────────┘  ← card_y
    """
    nome = pj.get('nome', f"P{pj.get('numero','?')}")
    comp = float(pj.get('comprimento', 60))
    larg = float(pj.get('largura', 38))
    g1   = float(pj.get('grade_1', 60))

    # ── Face segments ────────────────────────────────────────────────────────
    face_data = {}
    for fid in ['A', 'B', 'C', 'D']:
        h1r = float(pj.get(f'h1_{fid}', 0))
        h2r = float(pj.get(f'h2_{fid}', 0))
        h3r = float(pj.get(f'h3_{fid}', 0))
        if h1r + h2r + h3r <= 0:
            total = float(pj.get('altura', 280))
            h1r, h3r = 2.0, min(34.0, total - 246)
            h2r = total - h1r - h3r
        face_data[fid] = (h1r * FACE_H_SCALE,
                          h2r * FACE_H_SCALE,
                          h3r * FACE_H_SCALE)

    fw = {
        'A': comp * FACE_W_SCALE,
        'B': larg * FACE_W_SCALE,
        'C': comp * FACE_W_SCALE,
        'D': larg * FACE_W_SCALE,
    }
    max_face_h = max(sum(face_data[f]) for f in face_data)

    # ── Dimensões CIMA ───────────────────────────────────────────────────────
    cima_comp, cima_larg, cima_area_w, cima_area_h = _cima_dims(comp, larg)

    # ── Dimensões zona central (mid) ─────────────────────────────────────────
    # Faces precisam de: FACE_PAD_Y (label cima) + face_h + DIM_OFFSET (cota baixo) + FACE_PAD_Y
    faces_zone_h = FACE_PAD_Y + max_face_h + DIM_OFFSET + FACE_PAD_Y
    mid_h = max(cima_area_h, faces_zone_h)

    # ── Dimensões das faces (largura total) ───────────────────────────────────
    faces_zone_w = (fw['A'] + fw['B'] + fw['C'] + fw['D']
                    + 3 * FACE_GAP + 2 * FACE_PAD_X + DIM_OFFSET)

    # ── Dimensões finais do card ──────────────────────────────────────────────
    CARD_W = cima_area_w + faces_zone_w
    CARD_H = TITULO_H + mid_h + CARIMBO_H

    # ── Borda externa (Folhas) ────────────────────────────────────────────────
    rect(msp, card_x, card_y, CARD_W, CARD_H, 'Folhas', lw=50)

    # ── CARIMBO (rodapé) ─────────────────────────────────────────────────────
    draw_carimbo(msp, card_x, card_y, CARD_W, CARIMBO_H, obra_nome, folha_num)

    # ── TÍTULO (topo) ─────────────────────────────────────────────────────────
    titulo_y = card_y + CARD_H - TITULO_H
    rect(msp, card_x, titulo_y, CARD_W, TITULO_H, 'Folhas', lw=35)
    secao_str = f'{comp:.0f}X{larg:.0f}'
    mtext(msp, card_x + cima_area_w * 0.45, titulo_y + TITULO_H * 0.65,
          nome, height=10, layer='TEXTO_GERAL', anchor=5)
    mtext(msp, card_x + cima_area_w * 0.45, titulo_y + TITULO_H * 0.25,
          secao_str, height=7, layer='TEXTO_GERAL', anchor=5)

    # ── NIVEL pavimento (38 no STOG — linha tracejada horizontal na base) ──
    nivel_y = card_y + CARIMBO_H + 5
    msp.add_line((card_x, nivel_y), (card_x + CARD_W, nivel_y),
                 dxfattribs={'layer': 'NIVEL 2° PAV.', 'linetype': 'DASHED', 'lineweight': 13})
    mtext(msp, card_x + 3, nivel_y + 2, f'Niv. {pj.get("nivel_chegada", "?")}',
          height=4, layer='NIVEL 2° PAV.', anchor=1)

    # ── CONCRETO entity (2 no STOG — contorno do núcleo na CIMA) ──
    # Adicionado como LWPOLYLINE no layer CONCRETO
    hc_r = comp * CIMA_SCALE / 2
    hl_r = larg * CIMA_SCALE / 2
    mid_cy_approx = card_y + CARIMBO_H + (titulo_y - card_y - CARIMBO_H) / 2
    cima_cx_approx = card_x + cima_area_w / 2
    rect(msp, cima_cx_approx - hc_r, mid_cy_approx - hl_r, comp * CIMA_SCALE, larg * CIMA_SCALE, 'CONCRETO', lw=50)

    # ── Linha divisória CIMA / FACES ──────────────────────────────────────────
    div_x = card_x + cima_area_w
    mid_y0 = card_y + CARIMBO_H
    mid_y1 = titulo_y
    msp.add_line((div_x, mid_y0), (div_x, mid_y1),
                 dxfattribs={'layer': 'Folhas', 'lineweight': 25})

    # ── CIMA (seção transversal — zona esquerda, centrada verticalmente) ──────
    mid_cy = mid_y0 + mid_h / 2
    cima_cx = card_x + cima_area_w / 2
    tipo_esp = pj.get('tipo_pilar_especial', None)
    comp2_s = float(pj.get('comp_2', 0)) * CIMA_SCALE
    larg2_s = float(pj.get('larg_2', 0)) * CIMA_SCALE
    draw_cima(msp, cima_cx, mid_cy, cima_comp, cima_larg,
              g1 * CIMA_SCALE, nome, tipo_especial=tipo_esp,
              comp2=comp2_s, larg2=larg2_s)

    # ── FACES A/B/C/D (zona direita, centradas verticalmente) ─────────────────
    face_y_bot = mid_cy - max_face_h / 2    # base das faces
    fx = div_x + FACE_PAD_X
    for fid in ['A', 'B', 'C', 'D']:
        h1s, h2s, h3s = face_data[fid]
        draw_face(msp, fx, face_y_bot, fw[fid], h1s, h2s, h3s,
                  f'{nome}.{fid}')
        fx += fw[fid] + FACE_GAP

    # ── NOMENCLATURA (nome do pilar na lateral esquerda) ─────────────────────
    mtext(msp, card_x + 5, mid_cy, nome,
          height=12, layer='NOMENCLATURA', anchor=4)

    # ── Texto Seção (dimensões na zona CIMA, abaixo do pilar) ────────────────
    mtext(msp, cima_cx, mid_cy - cima_larg/2 - 18, secao_str,
          height=6, layer='Texto Seção', anchor=8)

    # ── GRADES (pontaletes + sarrafos em TODAS as faces) ───────────────────
    grade_1 = float(pj.get('grade_1', 0))
    grade_2 = float(pj.get('grade_2', 0))
    grade_3 = float(pj.get('grade_3', 0))
    dist_1 = float(pj.get('distancia_1', 14)) * FACE_H_SCALE
    dist_2 = float(pj.get('distancia_2', 14)) * FACE_H_SCALE if grade_3 > 0 else 0

    if grade_1 > 0:
        g1_s = grade_1 * FACE_H_SCALE
        g2_s = grade_2 * FACE_H_SCALE if grade_2 > 0 else 0
        g3_s = grade_3 * FACE_H_SCALE if grade_3 > 0 else 0

        # Iterar sobre as 4 faces (posição X de cada face)
        fx_iter = div_x + FACE_PAD_X
        for fid in ['A', 'B', 'C', 'D']:
            face_w = fw.get(fid, 30)
            fy = face_y_bot

            # PONTALETE esquerdo + direito
            msp.add_blockref('PONTALETE', (fx_iter - 8, fy - 10),
                             dxfattribs={'layer': 'Madeira'})
            msp.add_blockref('PONTALETE', (fx_iter + face_w + 1, fy - 10),
                             dxfattribs={'layer': 'Madeira'})

            # SARR_2.2x7 horizontais (grade 1)
            for gy in [fy, fy + g1_s]:
                msp.add_line((fx_iter - 8, gy), (fx_iter + face_w + 8, gy),
                             dxfattribs={'layer': 'SARR_2.2x7', 'lineweight': 18})

            # SARRAFO legacy vertical nos pontaletes (layer SARRAFO — 302 no STOG)
            for sx in [fx_iter - 5, fx_iter + face_w + 3]:
                msp.add_line((sx, fy), (sx, fy + g1_s),
                             dxfattribs={'layer': 'SARRAFO', 'lineweight': 25})

            # MEIO PONTALETE entre grade 1 e grade 2
            if grade_2 > 0:
                mp_y = fy + g1_s + dist_1
                msp.add_blockref('MEIO PONTALETE', (fx_iter - 5, mp_y),
                                 dxfattribs={'layer': 'Madeira'})
                msp.add_blockref('MEIO PONTALETE', (fx_iter + face_w + 1, mp_y),
                                 dxfattribs={'layer': 'Madeira'})
                # MEIO_PONT layer direto (59 no STOG — linhas representativas)
                msp.add_line((fx_iter - 5, mp_y), (fx_iter - 5, mp_y + 3.5),
                             dxfattribs={'layer': 'MEIO_PONT', 'lineweight': 25})

            # SARRAFO DE PRESSAO (41 no STOG — linha horizontal entre grades)
            msp.add_line((fx_iter, fy + g1_s), (fx_iter + face_w, fy + g1_s),
                         dxfattribs={'layer': 'SARRAFO DE PRESSAO', 'lineweight': 18})

            # Sarrafos tipados adicionais (STOG: SARR_2.2x10=21, SARR_3.5x7=21, SARR_7x7=14, Sarr 2.2x7=21)
            # Sarr de amarração horizontal (SARR_2.2x10) no topo da grade
            msp.add_line((fx_iter - 5, fy + g1_s - 2), (fx_iter + face_w + 5, fy + g1_s - 2),
                         dxfattribs={'layer': 'SARR_2.2x10', 'lineweight': 13})
            # Sarr especial (SARR_3.5x7) no meio da grade
            msp.add_line((fx_iter + face_w/2 - 1.75, fy), (fx_iter + face_w/2 - 1.75, fy + g1_s),
                         dxfattribs={'layer': 'SARR_3.5x7', 'lineweight': 18})
            # Sarr reforço (SARR_7x7) na base
            if g1_s > 20:
                msp.add_line((fx_iter, fy + 3.5), (fx_iter + face_w, fy + 3.5),
                             dxfattribs={'layer': 'SARR_7x7', 'lineweight': 25})
            # Sarr 2.2x7 variante nome
            msp.add_line((fx_iter + face_w/2 + 1.75, fy), (fx_iter + face_w/2 + 1.75, fy + g1_s),
                         dxfattribs={'layer': 'Sarr 2.2x7', 'lineweight': 13})

            # Texto legacy: label de grade nesta face (142 no STOG)
            txt_gy = max(3, face_w * 0.05)
            mtext(msp, fx_iter + face_w/2, fy + g1_s/2,
                  f'G1={grade_1:.0f}', height=txt_gy, layer='texto', anchor=5)
            if grade_2 > 0:
                mtext(msp, fx_iter + face_w/2, fy + g1_s + dist_1 + g2_s/2,
                      f'G2={grade_2:.0f}', height=txt_gy, layer='texto', anchor=5)
                # SARR horizontais grade 2
                for gy in [mp_y, mp_y + g2_s]:
                    msp.add_line((fx_iter - 8, gy), (fx_iter + face_w + 8, gy),
                                 dxfattribs={'layer': 'SARR_2.2x7', 'lineweight': 18})
                # SARRAFO vertical grade 2
                for sx in [fx_iter - 5, fx_iter + face_w + 3]:
                    msp.add_line((sx, mp_y), (sx, mp_y + g2_s),
                                 dxfattribs={'layer': 'SARRAFO', 'lineweight': 25})

            # MEIO PONTALETE grade 3
            if grade_3 > 0 and grade_2 > 0:
                mp3_y = fy + g1_s + dist_1 + g2_s + dist_2
                msp.add_blockref('MEIO PONTALETE', (fx_iter - 5, mp3_y),
                                 dxfattribs={'layer': 'Madeira'})
                msp.add_blockref('MEIO PONTALETE', (fx_iter + face_w + 1, mp3_y),
                                 dxfattribs={'layer': 'Madeira'})

            # COTAS das grades nesta face (vertical)
            dim_gx = fx_iter + face_w + DIM_OFFSET + 20
            # Grade 1
            dim_v(msp, fy, fy + g1_s, dim_gx, 'COTA')
            if grade_2 > 0:
                # Distância 1
                dim_v(msp, fy + g1_s, fy + g1_s + dist_1, dim_gx + 10, 'COTA')
                # Grade 2
                dim_v(msp, fy + g1_s + dist_1, fy + g1_s + dist_1 + g2_s, dim_gx, 'COTA')
            if grade_3 > 0 and grade_2 > 0:
                # Distância 2
                dim_v(msp, fy + g1_s + dist_1 + g2_s, fy + g1_s + dist_1 + g2_s + dist_2, dim_gx + 10, 'COTA')
                # Grade 3
                dim_v(msp, fy + g1_s + dist_1 + g2_s + dist_2,
                      fy + g1_s + dist_1 + g2_s + dist_2 + g3_s, dim_gx, 'COTA')
            # Cota total altura (todas as grades)
            total_grade_h = g1_s + (dist_1 + g2_s if grade_2 > 0 else 0) + (dist_2 + g3_s if grade_3 > 0 else 0)
            if total_grade_h > g1_s:
                dim_v(msp, fy, fy + total_grade_h, dim_gx + 20, 'COTA')

            fx_iter += face_w + FACE_GAP

        # ── COTAS FURAÇÃO (marcas de furo nos pontaletes — todas as faces) ──
        par_keys = ['par_1_2','par_2_3','par_3_4','par_4_5','par_5_6','par_6_7','par_7_8','par_8_9']
        par_vals = []
        for pk in par_keys:
            v = pj.get(pk, 0)
            try:
                fv = float(str(v).replace(',','.')) if v else 0
            except (ValueError, TypeError):
                fv = 0
            if fv > 0:
                par_vals.append(fv)
        if par_vals:
            cross_r = 1.5
            # Desenhar furação na face A (primeira face)
            fa_x = div_x + FACE_PAD_X
            fa_y = face_y_bot
            fa_w = fw.get('A', 30)
            for pont_x in [fa_x - 4.5, fa_x + fa_w + 4.5]:
                y_furo = fa_y
                for pv in par_vals:
                    y_furo += pv * FACE_H_SCALE
                    msp.add_line((pont_x - cross_r, y_furo), (pont_x + cross_r, y_furo),
                                 dxfattribs={'layer': 'COTAS FURACAO', 'lineweight': 13})
                    msp.add_line((pont_x, y_furo - cross_r), (pont_x, y_furo + cross_r),
                                 dxfattribs={'layer': 'COTAS FURACAO', 'lineweight': 13})

    return CARD_W, CARD_H


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--max', type=int, default=999)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    json_dir  = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Pilares'
    out_dir   = obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    pilar_files = sorted(
        json_dir.glob('P*.json'),
        key=lambda p: int(p.stem[1:]) if p.stem[1:].isdigit() else 999
    )[:args.max]

    if not pilar_files:
        print(f'[ERRO] Nenhum P*.json em {json_dir}')
        return

    obra_nome = obra_path.name
    print(f'Processando {len(pilar_files)} pilares → PL_stog_quality.dxf')

    doc = setup_doc()
    # Linetype DASHED para linhas de nível
    try:
        doc.linetypes.add('DASHED', pattern=[5.0, -2.0], description='Dashed')
    except Exception:
        pass
    msp = doc.modelspace()

    # Calcular posição dos cards com geometria dinâmica
    # Primeiro passo: determinar card_w e card_h do primeiro pilar para o grid
    card_positions = []
    col_x_cursor = [0.0] * COLS
    row_y_starts = [0.0]

    # Layout em grid: mesma largura/altura por linha para alinhamento
    row_heights  = []
    card_data_list = []
    for idx, pf in enumerate(pilar_files):
        pj = json.load(open(pf, encoding='utf-8'))
        card_data_list.append(pj)

    # Calcular dimensão máxima de card para grid uniforme
    def calc_card_dims(pj):
        comp = float(pj.get('comprimento', 60))
        larg = float(pj.get('largura', 38))

        h1r = float(pj.get('h1_A', 0))
        h2r = float(pj.get('h2_A', 0))
        h3r = float(pj.get('h3_A', 0))
        if h1r + h2r + h3r <= 0:
            total = float(pj.get('altura', 280))
            h1r, h3r = 2.0, min(34.0, total - 246)
            h2r = total - h1r - h3r
        max_face_h = (h1r + h2r + h3r) * FACE_H_SCALE

        _, _, cima_area_w, cima_area_h = _cima_dims(comp, larg)

        faces_zone_h = FACE_PAD_Y + max_face_h + DIM_OFFSET + FACE_PAD_Y
        mid_h = max(cima_area_h, faces_zone_h)

        faces_zone_w = ((comp + larg) * 2 * FACE_W_SCALE
                        + 3 * FACE_GAP + 2 * FACE_PAD_X + DIM_OFFSET)

        CARD_W = cima_area_w + faces_zone_w
        CARD_H = TITULO_H + mid_h + CARIMBO_H
        return CARD_W, CARD_H

    # Pre-calcular para grid uniforme por linha
    dims_per_card = [calc_card_dims(pj) for pj in card_data_list]

    # Grid: pos em função de row/col
    n_rows = (len(pilar_files) + COLS - 1) // COLS
    row_max_h = []
    for row in range(n_rows):
        ids = range(row*COLS, min((row+1)*COLS, len(pilar_files)))
        row_max_h.append(max(dims_per_card[i][1] for i in ids))

    col_max_w = []
    for col in range(COLS):
        ids = [col + row*COLS for row in range(n_rows) if col + row*COLS < len(pilar_files)]
        if ids:
            col_max_w.append(max(dims_per_card[i][0] for i in ids))
        else:
            col_max_w.append(0)

    # Renderizar cards
    for idx, pj in enumerate(card_data_list):
        col = idx % COLS
        row = idx // COLS
        card_x = sum(col_max_w[:col]) + col * CARD_GAP_X
        card_y = -(sum(row_max_h[:row]) + row * CARD_GAP_Y)

        cw, ch = generate_card(msp, pj, card_x, card_y,
                                folha_num=idx+2, obra_nome=obra_nome)

        nome = pj.get('nome', pf.stem)
        h    = pj.get('comprimento', '?')
        b    = pj.get('largura', '?')
        print(f'  [{idx+1:2d}] {nome}: {h}x{b}cm  col={col} row={row}  card={cw:.0f}x{ch:.0f}cm')

    out_dxf = out_dir / 'PL_stog_quality.dxf'
    doc.saveas(str(out_dxf))
    print(f'\n✅ DXF: {out_dxf}')

    # ── PNG preview ────────────────────────────────────────────────────────────
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        # Calcular extents do primeiro card
        pj0   = card_data_list[0]
        cw0, ch0 = dims_per_card[0]
        # Grade extents
        total_w = sum(col_max_w) + (COLS-1)*CARD_GAP_X
        total_h = sum(row_max_h) + (n_rows-1)*CARD_GAP_Y

        # Cards são posicionados com card_y negativo crescendo para baixo
        # Primeiro card (row=0): y=0 → ch0 (positivo, cresce para cima)
        # Mas card_y = -(row_sum) então cards ficam em y negativo na grade
        # Para row=0: card_y=0, card vai de 0 até ch0
        # Para row=1: card_y=-row_max_h[0]-GAP, card vai de card_y até card_y+ch
        # Limite y para 1o card: 0 até ch0
        # Limite y para grade: -total_h até max(ch0)
        fig, axes = plt.subplots(1, 2, figsize=(22, 12), facecolor='#0a0a14')
        for ax, (xlim, ylim, title) in zip(axes, [
            ((-20, cw0 + 20), (-5, ch0 + 20),
             f'Card {pj0.get("nome","P1")} — CIMA + Faces ABCD'),
            ((-20, total_w + 20), (-total_h - 20, row_max_h[0] + 20),
             f'Grade completa — {len(pilar_files)} pilares'),
        ]):
            ax.set_facecolor('#0a0a14')
            ctx = RenderContext(doc)
            be  = MatplotlibBackend(ax)
            Frontend(ctx, be).draw_layout(msp, finalize=True)
            ax.set_xlim(*xlim)
            ax.set_ylim(*ylim)
            ax.set_aspect('equal', adjustable='box')
            ax.set_title(title, color='white', fontsize=10, pad=4)

        plt.tight_layout()
        out_png = out_dir / 'PL_stog_quality.png'
        plt.savefig(str(out_png), dpi=130, bbox_inches='tight', facecolor='#0a0a14')
        plt.close()
        print(f'✅ Preview: {out_png}')
    except Exception as ex:
        print(f'[WARN] PNG: {ex}')


if __name__ == '__main__':
    main()
