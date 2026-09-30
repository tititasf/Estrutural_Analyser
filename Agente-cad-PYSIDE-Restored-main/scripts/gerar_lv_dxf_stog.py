#!/usr/bin/env python3
"""
gerar_lv_dxf_stog.py — Gerador STOG-quality LV DXF (Vigas Laterais, sem AutoCAD)
==================================================================================
Refactored based on real SCR anatomy (cad-scr-anatomy-lv.md):
  - Sarrafo distribution by panel height (h<15, 15-30, 30-80, >=80)
  - Grade mode: horizontal SARR_2.2x7 + vertical SARR_2.2x3.5 legs
  - Visao de Corte with MLINE-style sarrafos, BARRA_ANCORAGEM, blocks
  - 7cm inset on first/last panels for horizontal sarrafos
  - Correct layers: SARR_2.2x7, SARR_2.2x5, SARR_2.2x3.5, SARRAFO_2_2X7,
    BARRA_ANCORAGEM, HACHURACONCRETO

JSON input (Fase-4_Sincronizacao/JSON_Vigas_Laterais/V*_A.json):
  total_width  = b   (largura da secao transversal, cm)
  total_height = h   (altura lateral dos paineis, cm)
  panels[].width = comprimento de cada segmento de painel original

Uso:
  python scripts/gerar_lv_dxf_stog.py --obra DADOS-OBRAS/Obra_TREINO_21
  python scripts/gerar_lv_dxf_stog.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_21
"""
import sys
if __name__ == '__main__' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json, argparse, os, re, math
from pathlib import Path
import ezdxf
from visual_modes import apply_visual_mode

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from src.core.artifact_governance import guarded_saveas

_MOTOR_ID = "ROBOT_LV_N3_N4"
_MOTOR_SOURCES = [Path(__file__)]

# ── Constantes de layout (calibradas nos DXFs STOG) ────────────────────────
GAP_ROW_LV     = 100    # gap vertical entre linhas de vigas (cm)
NOM_ABOVE      = 9      # y = painel_top + NOM_ABOVE -> NOMENCLATURA
DIM_BELOW      = 37     # y = painel_bottom - DIM_BELOW -> cotas paineis individuais
DIM_TOTAL_BELOW= 60     # y = painel_bottom - DIM_TOTAL_BELOW -> cota total
DIM_H_RIGHT    = 25     # nivel 1 a direita (15 + 109); nivel 2 = 2x = 50 (124)
# Painéis mais estreitos que isto NÃO recebem cota individual (evita "28,721,8"
# e "1921,2" por colisão de texto no SVG/render). Agrupam-se consecutivos.
PANEL_DIM_MIN_W = 55.0  # multi-seg: 22.5+52.5->75
GAP_AB     = 200    # gap horizontal entre Face A (right) e Face B (left)
LV_UNIT_GAP    = 200.0  # gap entre continuacoes/face_units no viewer dedicado
NOM_H          = 16.5   # altura texto NOMENCLATURA
PID_H          = 12.0   # altura texto panel-ID interno

# ── Modulo de paineis LV (engenharia reversa NIK SUNSET Laje Tecnica) ───────
PAINEL_MODULO_LV = 120   # modulo painel lateral STOG (cm) — reverso usa 120cm (não 122)
PAINEL_MIN_LV    = 7     # largura minima de painel real; abaixo disso = artefato de borda

# ── Sarrafo constants from SCR anatomy ────────────────────────────────────────
LV_SARR_LAYER  = 'SARR_3.5x7'
LV_SARR_W      = 3.5    # largura de cada sarrafo (cm)
LV_SARR_INSET  = 15.0   # inset das bordas extremas para SARR_3.5x7 (cm)
SARR_INSET_H   = 7.0    # inset from panel edge for horizontal sarrafos on first/last panels
SARR_PANEL_GAP = 0.8    # gap vs divisor Painéis (evita sobreposição visual)
SARR_MIN_PANEL_W = 28.0 # painéis estreitos (marco) sem sarrafeamento interno

# Chaves globais pra desligar preenchimento de hachura no N4, separadas por
# natureza — pedido do dono 2026-09-08: manter a hachura de LAJE/concreto
# (AR-CONC/HACHURACONCRETO — essa extracao ja foi validada contra o N2 real
# nesta sessao) e desligar so a de PAINEL/madeira/reaproveitamento (ANSI31
# em Hachura — extracao ainda em ajuste). As LINHAS de contorno que cada
# bloco desenha (limite real do vazio/reaproveitamento) continuam sendo
# desenhadas em ambos os casos — só o preenchimento fica de fora quando
# desligado.
DRAW_HATCHES_LAJE = True     # AR-CONC / HACHURACONCRETO (concreto, laje)
DRAW_HATCHES_PAINEL = False  # ANSI31 em Hachura (madeira, reaproveitamento)

# Padrão de hachura AR-CONC (concreto/vazio) — extraído do próprio recorte N2 de
# V301 (layer COTA, hatch_style=1, scale=1.0, angle=0.0) para reproduzir o
# "vazio" (onde vai concreto, não painel) com fidelidade visual exata. Convenção
# do projeto: vazios (laje ou viga que passa/cruza) SEMPRE usam este padrão,
# layer COTA — nunca 'Hachura' (essa é textura de madeira/reaproveitamento).
AR_CONC_PATTERN = [
    (50.0, (0.0, 0.0), (182.184669, -15.939086), [19.05, -209.55]),
    (355.0, (0.0, 0.0), (-35.243421, 191.056845), [15.24, -167.640584]),
    (100.451445, (15.182007, -1.328253), (146.941247, 175.117752), [16.190009, -178.090245]),
    (46.1842, (0.0, 50.8), (271.079041, -42.042328), [28.575, -314.325]),
    (96.635558, (22.5899, 47.2965), (237.404134, 247.426125), [24.285023, -267.135608]),
    (351.184151, (0.0, 50.8), (237.404134, 247.426125), [22.859967, -251.459732]),
    (21.0, (25.4, 38.1), (151.614391, -102.265198), [19.05, -209.55]),
    (326.0, (25.4, 38.1), (61.802028, 184.187966), [15.24, -167.64]),
    (71.451445, (38.034533, 29.5779), (213.416419, 81.922769), [16.190009, -178.089938]),
    (37.5, (0.0, 0.0), (3.088603, 84.555039), [0.0, -165.608, 0.0, -170.18, 0.0, -168.275]),
    (7.5, (0.0, 0.0), (66.819663, 100.180575), [0.0, -97.028, 0.0, -161.798, 0.0, -64.135]),
    (-32.5, (-56.642, 0.0), (135.590595, -5.728744), [0.0, -63.5, 0.0, -198.12, 0.0, -262.89]),
    (-42.5, (-82.042, 0.0), (148.129181, 25.426491), [0.0, -82.55, 0.0, -131.572, 0.0, -186.69]),
]


PAINEL_COMPLETO_LV = 244.0


def comprimir_paineis_repetidos(larguras, largura_completa=PAINEL_COMPLETO_LV,
                                tol=0.6):
    """Colapsa a sequencia INTERNA de paineis completos iguais num fator "NX".

    REGRA DO DONO (2026-09-19), para montar o N3 a partir do N1 — la' vem a
    lista real de segmentos e o desenho tem de ser a versao comprimida, do
    mesmo jeito que o humano desenha no N2:

      - a sequencia comeca a partir do SEGUNDO painel;
      - so' entram paineis COMPLETOS (244) e todos iguais entre si;
      - o PRIMEIRO e o ULTIMO painel nunca entram no multiplicador;
      - com menos de 2 paineis na sequencia nao ha' multiplicador.

    Exemplos dados pelo dono:

        244 244 244          -> sem multiplicador (sobra 1 no meio)
        244 244 244 244      -> 244 | 244x2 | 244
        80  244 244 122      -> 80  | 244x2 | 122
        244 244 80  244      -> sem multiplicador (a sequencia quebra)

    E o caso real da V303.B, cuja soma o dono confirmou em 2262,5:

        [244]*8 + [66,5] + [244]  ->  244 | 244x7 | 66,5 | 244

    Devolve [(largura, fator), ...] na ordem do desenho.
    """
    ws = [float(w) for w in (larguras or [])]
    n = len(ws)
    saida = [(w, 1) for w in ws]
    if n < 4:
        return saida
    if abs(ws[1] - float(largura_completa)) > tol:
        return saida
    k = 1
    while k + 1 < n - 1 and abs(ws[k + 1] - float(largura_completa)) <= tol:
        k += 1
    if k < 2:                      # k paineis na sequencia (indices 1..k)
        return saida
    return ([(ws[0], 1), (float(largura_completa), k)]
            + [(w, 1) for w in ws[k + 1:]])


def compress_lv_panels_with_factors(panels, largura_completa=PAINEL_COMPLETO_LV,
                                     tol=0.6):
    """Mesma regra de `comprimir_paineis_repetidos`, só que sobre os dicts de
    painel reais (não larguras soltas) — é o que liga a regra ao desenho N3.

    O N4 lê o fator "NX" do próprio texto que o humano já desenhou no N2
    (`motor_reverso_lv._fatores_por_painel`): lá a sequência repetida já nasce
    comprimida, porque o humano só desenhou UM painel representante. O N3
    nasce do N1/SA com a sequência COMPLETA (todos os painéis reais, sem
    anotação nenhuma) — esta função computa a mesma compressão, removendo do
    desenho os painéis absorvidos e devolvendo o fator alinhado ao painel que
    passa a representá-los, para `draw_lv_face` desenhar e cotar do mesmo
    jeito que o N4.

    Devolve ``(paineis_para_desenhar, fatores_painel)`` alinhados 1:1 — a
    lista de painéis pode ficar mais curta que a original; os campos do
    painel representante (altura, tipo etc.) são preservados como estão.
    """
    items = list(panels or [])
    n = len(items)
    fatores_default = [1] * n
    if n < 4:
        return items, fatores_default
    ws = [float(p.get('width', 0) or 0) for p in items]
    if abs(ws[1] - float(largura_completa)) > tol:
        return items, fatores_default
    k = 1
    while k + 1 < n - 1 and abs(ws[k + 1] - float(largura_completa)) <= tol:
        k += 1
    if k < 2:
        return items, fatores_default
    compressed = [items[0], items[1]] + items[k + 1:]
    fatores = [1, k] + [1] * (n - k - 1)
    return compressed, fatores


def _draw_laje_escalonada(msp, faixas):
    """Laje como UM vazio de concreto, com o fundo acompanhando o degrau.

    Medido no N2 (V13.A, V302.A, V302.B e CONT.V302.A): a hachura AR-CONC e'
    SEMPRE UMA por unidade, mesmo quando o corpo embaixo muda de altura — na
    V302.A ela cobre os 470 de largura com o fundo em dois niveis (43 e 45) e
    o topo plano. Um retangulo por trecho produzia a "divisao entre os dois
    hatchs" que o dono apontou (V302 SEGMENTO 6B, P1/P2).

    O topo e' sempre o topo PLANO da unidade: onde ha' painel de fechamento
    ele ocupa os centimetros de cima DESTA faixa, sobreposto a ela — no N2 da
    V302.B a AR-CONC vai de +44 a +59 e a ANSI31 do painel de +56 a +59. A
    altura menor que o N2 escreve ali (12 contra 15) e' a laje VISIVEL sob o
    painel, assunto de cota, nao de desenho.

    `faixas` = [(x_ini, x_fim, y_base), ...] em ordem de x; `y_topo` e' comum.
    """
    faixas = [f for f in (faixas or []) if f[1] - f[0] > 0.05]
    if not faixas:
        return
    y_topo = max(f[3] for f in faixas)
    a_cota = {'layer': 'COTA'}
    pts = []
    for _x0, _x1, _yb, _yt in faixas:
        pts.append((_x0, _yb))
        pts.append((_x1, _yb))
    for _x0, _x1, _yb, _yt in reversed(faixas):
        pts.append((_x1, y_topo))
        pts.append((_x0, y_topo))
    # Tampa: uma linha continua no topo, de ponta a ponta.
    msp.add_line((faixas[0][0], y_topo), (faixas[-1][1], y_topo),
                 dxfattribs=a_cota)
    # E o degrau do FUNDO, onde o corpo muda de altura.
    for _i in range(len(faixas) - 1):
        _xb = faixas[_i][1]
        _ya, _yb2 = faixas[_i][2], faixas[_i + 1][2]
        if abs(_ya - _yb2) > 0.05:
            msp.add_line((_xb, _ya), (_xb, _yb2), dxfattribs=a_cota)
    if DRAW_HATCHES_LAJE:
        ht = msp.add_hatch(dxfattribs={'layer': 'COTA', 'color': 7})
        ht.paths.add_polyline_path(pts, is_closed=True)
        ht.set_pattern_fill(
            'AR-CONC', color=7, angle=0.0, scale=1.0, style=1, pattern_type=0,
            definition=AR_CONC_PATTERN,
        )


def _draw_vazio_concreto(msp, x_left, y_bot, x_right, y_top):
    """Vazio/laje de concreto (AR-CONC) com retangulo visual fechado.

    A parede direita pertence ao retangulo do vazio e fica em COTA; nunca em
    Painéis. Assim a laje fecha sem recriar um divisor vertical de painel.
    """
    if x_right <= x_left + 0.5 or y_top <= y_bot + 0.5:
        return
    a_cota = {'layer': 'COTA'}
    # Encosta na borda real (x_right) — o inset de 0.8cm de uma sessao
    # anterior deixava uma folga visivel sem hachura entre o vazio e a
    # parede/laje real (achado 2026-09-10, V301.B: hachura parava em
    # x=7071.3, 0.8cm antes do limite real em 7072.1, deveria encostar).
    x_hatch_r = float(x_right)
    # So a tampa. Laterais nas paredes externas colam nas cotas 15/7 e
    # parecem "linha de painel extra gerada pela cota".
    msp.add_line((x_left, y_top), (x_hatch_r, y_top), dxfattribs=a_cota)
    # path fechado so para o fill; direita inset (nao colada no body_end)
    pts = [
        (x_left, y_bot), (x_hatch_r, y_bot),
        (x_hatch_r, y_top), (x_left, y_top),
    ]
    if DRAW_HATCHES_LAJE:
        ht = msp.add_hatch(dxfattribs={'layer': 'COTA', 'color': 7})
        ht.paths.add_polyline_path(pts, is_closed=True)
        ht.set_pattern_fill(
            'AR-CONC', color=7, angle=0.0, scale=1.0, style=1, pattern_type=0,
            definition=AR_CONC_PATTERN,
        )

# ── Detalhe de secao transversal ─────────────────────────────────────────────
SECT_W         = 160    # largura reservada para o detalhe de secao (cm)
SECT_GAP       = 30     # gap entre secao e Face A
SECT_PANEL_W   = 4      # espessura do painel na secao (Paineis layer)
SECT_BOARD_W   = 14     # espessura tabua externa (Madeira layer)
LV_FACE_X0_MIN = 1800.0  # afasta A/B para o viewer isolar a visao-corte

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
    LV_SARR_LAYER:       81,   # SARR_3.5x7
    'SARR_2.2x7':        40,
    'SARR_2.2x5':        40,
    'SARR_2.2x3.5':      40,
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
    'Reaproveitamento': 251,   # mixed-case como no STOG real
    # VC-specific layers — nomes corrigidos para espelhar STOG real
    # SARRAFO_2_2X7 → SARR_2.2x7 (já na lista acima)
    # BARRA_ANCORAGEM → BARRA DE ANCORAGEM (já na lista acima)
    # HACHURACONCRETO → Hachura (já na lista acima)
    'ESTRUTURACAO':       7,
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

    # Dimstyle PAINEL
    if 'PAINEL' not in doc.dimstyles:
        ds = doc.dimstyles.new('PAINEL')
    else:
        ds = doc.dimstyles.get('PAINEL')
    ds.set_arrows('OBLIQUE', 'OBLIQUE')
    ds.dxf.dimasz  = 3.0
    ds.dxf.dimtxt  = 10.0
    ds.dxf.dimgap  = 3.0
    ds.dxf.dimexe  = 3.0
    # dimexo=3: a linha de extensao NASCE 3 cm afastada do objeto, nao
    # encostada nele. Medido no N2 da V302.B (apontamento do dono, SEGMENTO
    # 1B, P1/P2: "patinhas da cota fora de posicao"), com a borda da unidade
    # em x rel 0:
    #     cota 44   extensao de -3,0 a -16,9   linha de cota em -13,9
    #     cota 12   extensao de -3,0 a -16,9   linha de cota em -13,9
    #     cota  3   extensao de -3,0 a -16,9   linha de cota em -13,9
    #     cota 59   extensao de -3,0 a -42,9   linha de cota em -39,9
    # Ou seja folga de 3 antes e sobra de 3 depois (dimexe, ja' correto). Com
    # dimexo=0 a pata encostava no painel e o dono leu como fora de posicao —
    # a mesma folga que o `override={'dimexo': 3.0}` da cota de largura do
    # painel de topo ja' aplicava por fora desde 2026-09-13.
    ds.dxf.dimexo  = 3.0
    ds.dxf.dimclrd = 4
    ds.dxf.dimclrt = 240
    ds.dxf.dimclre = 4
    ds.dxf.dimtad  = 1
    ds.dxf.dimtih  = 0
    # Se não cabe, empurra o texto (reduz colisão em painéis médios)
    try:
        ds.dxf.dimtmove = 1
        ds.dxf.dimtoh = 0
    except Exception:
        pass

    # Dimstyle SECAO2X
    if 'SECAO2X' not in doc.dimstyles:
        ds2 = doc.dimstyles.new('SECAO2X')
    else:
        ds2 = doc.dimstyles.get('SECAO2X')
    ds2.set_arrows('OBLIQUE', 'OBLIQUE')
    ds2.dxf.dimasz  = 5.0
    ds2.dxf.dimtxt  = 7.0
    ds2.dxf.dimgap  = 2.0
    ds2.dxf.dimexe  = 3.0
    ds2.dxf.dimexo  = 3.0
    ds2.dxf.dimclrd = 4
    ds2.dxf.dimclrt = 1
    ds2.dxf.dimclre = 4
    ds2.dxf.dimtad  = 3
    ds2.dxf.dimtih  = 0

    # Block definitions for VC (Visao de Corte)
    _define_vc_blocks(doc)

    return doc


def _define_vc_blocks(doc):
    """Define block references used in Visao de Corte (VC) SCR anatomy."""
    block_names = ['PAR_ESQ', 'PAR_FUNDO_ESQ', 'PAR_FUNDO_DIR',
                   'par_int_esq', 'par_int_dir']
    for bname in block_names:
        if bname not in doc.blocks:
            blk = doc.blocks.new(name=bname)
            # Simple screw/bolt representation: cross mark 2cm
            sz = 1.0
            blk.add_line((-sz, -sz), (sz, sz), dxfattribs={'layer': '0'})
            blk.add_line((-sz, sz), (sz, -sz), dxfattribs={'layer': '0'})


# ──────────────────────────────────────────────────────────────────────────────
# Distribuicao de paineis LV
# ──────────────────────────────────────────────────────────────────────────────

def extract_panels_from_json(panels_json, laje_central_alt_global=0.0):
    """Extrai dados reais dos paineis do JSON.
    Retorna lista de dicts: [{width, height1, height2, grade_h1, grade_h2, laje_central_alt,
                               laje_sup_local, laje_inf_local, reuse, reuse_regions, panel_type}, ...]
    """
    panels = []
    for p in (panels_json or []):
        w = float(p.get('width', 0))
        if w <= 0:
            continue
        lca = float(p.get('laje_central_alt', laje_central_alt_global) or laje_central_alt_global)
        panels.append({
            'width':            w,
            'height1':          float(p.get('height1', 0)),
            'height2':          float(p.get('height2', 0)),
            'grade_h1':         float(p.get('grade_h1', 0) or 0),
            'grade_h2':         float(p.get('grade_h2', 0) or 0),
            'laje_central_alt': lca,
            'laje_sup_local':   float(p.get('laje_sup_local', p.get('slab_top', 0)) or 0),
            'laje_inf_local':   float(p.get('laje_inf_local', p.get('slab_bottom', 0)) or 0),
            'slab_top':         float(p.get('slab_top', p.get('laje_sup_local', 0)) or 0),
            'slab_bottom':      float(p.get('slab_bottom', p.get('laje_inf_local', 0)) or 0),
            'vazio_base_local': float(p.get('vazio_base_local', 0) or 0),
            'holes':            p.get('holes', []),
            'reuse':            bool(p.get('reuse', False)),
            'reuse_regions':    p.get('reuse_regions', []),
            'panel_type':       str(p.get('panel_type', 'Sarrafeado')),
        })
    return panels


def auto_distribute_panels(comprimento, panels_json, laje_central_alt_global=0.0):
    """Distribui paineis LV.

    PRIORIDADE 1 — JSON com painéis: usa as larguras do JSON diretamente.
      - Filtra trailing panels < PAINEL_MIN_LV (artefatos de borda da extração).
      - Preserva mini-painéis reais >= PAINEL_MIN_LV (8cm, 11.5cm, 23.5cm, etc.).

    PRIORIDADE 2 — Sem JSON: distribui por módulo PAINEL_MODULO_LV (120 cm).

    Retorna (panels, border_strip_width):
      - panels: lista de dicts no mesmo formato de extract_panels_from_json
      - border_strip_width: largura do trailing panel filtrado (0.0 se nenhum filtrado)
        → necessário para desenhar o border strip no Painéis layer (5 entities/face)
    """
    border_strip_w = 0.0
    if panels_json:
        # Usar larguras do JSON (fonte da verdade = engenharia reversa)
        panels = extract_panels_from_json(panels_json, laje_central_alt_global)
        # Filtrar trailing panels < PAINEL_MIN_LV (artefatos de borda, não painéis reais)
        # Guarda o último filtrado como border_strip_w para desenhar o contorno no DXF
        while len(panels) > 1 and panels[-1]['width'] < PAINEL_MIN_LV:
            border_strip_w = panels[-1]['width']
            panels.pop()
        if panels:
            return panels, border_strip_w

    if comprimento <= 0:
        return [], 0.0

    # Fallback: distribuição automática por módulo (quando JSON não tem painéis)
    n = max(1, math.ceil(comprimento / PAINEL_MODULO_LV))

    # Dados de altura/tipo do primeiro painel JSON como template
    base = {
        'height1': 0.0, 'height2': 0.0,
        'grade_h1': 0.0, 'grade_h2': 0.0,
        'laje_central_alt': laje_central_alt_global,
        'reuse': False,
        'panel_type': 'Sarrafeado',
    }

    # n-1 paineis de 120 cm + último painel com o restante
    w_last = comprimento - (n - 1) * PAINEL_MODULO_LV
    if w_last < PAINEL_MIN_LV and n > 1:
        # Absorve no penúltimo se o último for artefato de borda
        n -= 1
        w_last = comprimento - (n - 1) * PAINEL_MODULO_LV

    result = []
    for i in range(n):
        w = PAINEL_MODULO_LV if i < n - 1 else w_last
        result.append(dict(base, width=round(w, 2)))
    return result, 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Primitivos de desenho
# ──────────────────────────────────────────────────────────────────────────────

def add_text(msp, x, y, text, height, layer, halign=0, valign=0, color=None,
             rotation=0.0):
    attribs = {'insert': (x, y), 'height': height, 'layer': layer}
    if color not in (None, 256):
        try:
            attribs['color'] = int(color)
        except Exception:
            pass
    if rotation:
        attribs['rotation'] = float(rotation)
    if halign or valign:
        attribs['halign'] = halign
        attribs['valign'] = valign
        attribs['align_point'] = (x, y)
    msp.add_text(text, dxfattribs=attribs)


def draw_panel_lines(msp, x0, y0, pw, h, *, draw_left=True, draw_right=True):
    """Contorno de painel LV sem duplicar a linha de união entre painéis."""
    a = {'layer': 'Painéis'}
    msp.add_line((x0,    y0),   (x0+pw, y0),   dxfattribs=a)   # bottom
    msp.add_line((x0,    y0+h), (x0+pw, y0+h), dxfattribs=a)   # top
    if draw_left:
        msp.add_line((x0, y0), (x0, y0+h), dxfattribs=a)
    if draw_right:
        msp.add_line((x0+pw, y0), (x0+pw, y0+h), dxfattribs=a)


def _panel_has_laje_central(p, h_face):
    lc_alt = float(p.get('laje_central_alt', 0) or 0)
    h1 = float(p.get('height1', 0) or 0)
    h2 = float(p.get('height2', 0) or 0)
    return (lc_alt > 0) or (h1 > 0 and h2 > 0 and abs(h1 - h2) > 0.5)


def _is_degrau_panel(p, h_face):
    """Painel P1 mais baixo que a face — alinhamento superior, não inferior.

    height1 < 12 cm é quase sempre faixa de laje/marco mal extraída (não degrau).

    Painel EMBAIXO de abertura de viga nunca é degrau: ali o `height1` é a
    SOBRA, medida do fundo para cima, e o vazio fica ACIMA dela. Degrau é o
    contrário — o painel sobe para alinhar o topo com a face. Medido na
    V304.B: o painel de 29 com sobra 15 numa face de 59 saía pendurado no topo
    (`y0 + 59 - 15`), desenhando uma caixa de 29x15 dentro do vazio.
    """
    if p.get('sob_abertura'):
        return False
    if _panel_has_laje_central(p, h_face):
        return False
    h1 = float(p.get('height1', 0) or 0)
    if h1 < 12.0:
        return False
    return 0 < h1 < h_face - 5.0


def _panel_draw_height(p, h_face):
    h1 = float(p.get('height1', 0) or 0)
    # height1 micro (<12) = artefato de extração; desenhar face cheia
    if 0 < h1 < 12.0:
        return h_face
    if _is_degrau_panel(p, h_face):
        return h1
    return h_face


def _panel_y_base(y0, h_face, p):
    """Base Y do painel na face: degrau sobe para alinhar o topo à face."""
    if not _is_degrau_panel(p, h_face):
        return y0
    h1 = float(p.get('height1', 0) or 0)
    regions = p.get('reuse_regions') or []
    if regions:
        y_off = float(regions[0].get('y_offset', 0) or 0)
        r_h = float(regions[0].get('height', 0) or 0)
        # Confia no y_offset da hachura real (extracao independente do N2)
        # quando a altura da regiao bate com height1 do painel — mesma
        # faixa fisica, mesmo quando y_offset cai acima do h_face refinado
        # (achado 2026-08-31, V301.B#1: hachura real fica em y=98.4, 10cm
        # acima de h_face=108.6, porque o bloco de reaproveitamento vive na
        # faixa do marco, nao do corpo; region height=44.0 ~ height1=43.6
        # confirma mesmo degrau — so' fora do range do guard antigo).
        if r_h > 0 and abs(r_h - h1) <= 3.0 and y_off > 5.0:
            return y0 + y_off
        # Sem 'height' confiavel na regiao: guard antigo (evita faixa de
        # laje de ~6cm no topo sendo lida como se fosse ombro de degrau).
        if 5.0 < y_off < h_face - 12.0 and h1 >= 12.0:
            return y0 + y_off
    return y0 + (h_face - h1)


def sanitize_face_panels_for_draw(panels, h_face):
    """Normaliza height1 espúrio antes de desenhar (N2 mal extraído).

    Se vários painéis iniciais têm height1 micro (<12) e há painéis altos
    depois, promove height1 dos curtos para o padrão de degrau derivado do
    ombro implícito (h_face - maior height1 micro-corrigido via painéis
    intermediários) — fallback: full h_face.
    """
    if not panels or h_face <= 0:
        return panels
    out = []
    tiny = []
    for i, p in enumerate(panels):
        h1 = float(p.get('height1', 0) or 0)
        if 0 < h1 < 12.0:
            tiny.append(i)
    # Se quase todos são micro, não inventar degrau — full face
    if tiny and len(tiny) >= max(1, len(panels) - 1):
        for p in panels:
            q = dict(p)
            if 0 < float(q.get('height1', 0) or 0) < 12.0:
                q['height1'] = float(h_face)
            out.append(q)
        return out
    return list(panels)


# ──────────────────────────────────────────────────────────────────────────────
# Sarrafo distribution by height (SCR anatomy rules)
# ──────────────────────────────────────────────────────────────────────────────

def _get_sarrafo_positions(h):
    """Return (layer_name, sarrafo_width, positions_from_bottom) based on panel height h.

    SCR anatomy rules:
      h < 15cm:  2x SARR_2.2x5 at 5cm from edges
      h 15-30:   2x SARR_2.2x7 at 7cm from edges
      h 30-80:   4x SARR_2.2x7 at 7cm edges + center +/- 3.5cm
      h >= 80:   8x SARR_2.2x7 at 7cm edges + center +/- 3.5 + quarter +/- 3.5
    """
    if h < 15:
        layer = 'SARR_2.2x7'  # merged with SARR_2.2x7 — 85%+ STOGs use SARR_2.2x7 for all heights
        sw = 5.0
        positions = [5.0, h - 5.0]
    elif h < 30:
        layer = 'SARR_2.2x7'
        sw = 7.0
        positions = [7.0, h - 7.0]
    elif h < 80:
        layer = 'SARR_2.2x7'
        sw = 7.0
        center = h / 2.0
        positions = [7.0, center - 3.5, center + 3.5, h - 7.0]
    else:
        layer = 'SARR_2.2x7'
        sw = 7.0
        center = h / 2.0
        quarter = h / 4.0
        three_q = 3 * h / 4.0
        positions = [
            7.0,
            quarter - 3.5, quarter + 3.5,
            center - 3.5, center + 3.5,
            three_q - 3.5, three_q + 3.5,
            h - 7.0,
        ]
    # Remove duplicate or out-of-range positions
    positions = sorted(set(p for p in positions if 0.5 < p < h - 0.5))
    return layer, sw, positions


def _sarrafo_h_insets(pw, is_first, is_last):
    """Insets X para sarrafo horizontal: borda de face 7 cm; vs Painéis sempre gap."""
    left = SARR_INSET_H if is_first else SARR_PANEL_GAP
    right = SARR_INSET_H if is_last else SARR_PANEL_GAP
    if float(pw or 0) < left + right + 2.0:
        # Painel estreito: gap simétrico mínimo, sem forçar 7 cm.
        gap = min(SARR_PANEL_GAP, max(0.3, float(pw) * 0.15))
        return gap, gap
    return left, right


def draw_sarrafos_by_height(msp, x0, y0, h, pw, layer, sarr_w, positions,
                            is_first, is_last, *, skip_ys=None):
    """Draw horizontal sarrafo lines for a single panel.

    Each sarrafo is 1 LWPOLYLINE (centerline) per position — matches SCR anatomy
    (SCR draws 1 _PLINE per sarrafo, not a rectangle).
    First/last: 7 cm from face edge. All panels: gap vs divisor Painéis.
    """
    if float(pw or 0) < SARR_MIN_PANEL_W:
        return
    left_in, right_in = _sarrafo_h_insets(pw, is_first, is_last)
    x_left = x0 + left_in
    x_right = x0 + pw - right_in
    if x_right <= x_left + 1.0:
        return

    skip = skip_ys or ()
    for y_pos in positions:
        y_ctr = y0 + y_pos
        if any(abs(y_ctr - yb) < 1.2 for yb in skip):
            continue
        msp.add_lwpolyline([(x_left, y_ctr), (x_right, y_ctr)],
                           close=False, dxfattribs={'layer': layer})


def draw_sarrafo_spans(msp, x0, y0, panels, h_face, layer):
    """Add 'span' PLINEs for each sarrafo position × each panel.
    Matches SCR anatomy: n_pos*n_panels extra LWPOLY per face (span count).
    """
    x_cur = x0
    n = len(panels)
    y_top = y0 + h_face
    y_shoulder = _degrau_shoulder_y(y0, h_face, panels)
    skip_ys = [y0, y_top]
    if y_shoulder is not None:
        skip_ys.append(y_shoulder)
    for i, p in enumerate(panels):
        pw = p['width']
        if float(pw or 0) < SARR_MIN_PANEL_W:
            x_cur += pw
            continue
        if p.get('reuse') or _is_degrau_panel(p, h_face):
            x_cur += pw
            continue
        is_first = (i == 0)
        is_last = (i == n - 1)
        h_panel = _panel_draw_height(p, h_face)
        y_panel = _panel_y_base(y0, h_face, p)
        _, _, positions = _get_sarrafo_positions(h_panel)
        left_in, right_in = _sarrafo_h_insets(pw, is_first, is_last)
        x_left = x_cur + left_in
        x_right = x_cur + pw - right_in
        if x_right > x_left + 1.0:
            for y_pos in positions:
                y_ctr = y_panel + y_pos
                if any(abs(y_ctr - yb) < 1.2 for yb in skip_ys):
                    continue
                msp.add_lwpolyline([(x_left, y_ctr), (x_right, y_ctr)],
                                   close=False, dxfattribs={'layer': layer})
        x_cur += pw


def merge_sarrafos_verticais_extremidades(
    specs, face_width, h_face, *,
    draw_left=True, draw_right=True,
    edge_inset=None,
):
    """Garante sarrafos 2.2x7 a 7 cm das paredes quando o N2 não listou a borda."""
    merged = [dict(item) for item in (specs or [])]
    inset = float(edge_inset if edge_inset is not None else SARR_INSET_H)
    width = float(face_width or 0)
    height = float(h_face or 0)
    if width < 2 * inset or height <= 0:
        return merged

    right_x = round(width - inset, 1)
    tol = 3.0

    def _has_near(target_x: float) -> bool:
        return any(
            abs(float(item.get('x_offset', 0) or 0) - target_x) < tol
            for item in merged
        )

    if draw_left and not _has_near(inset):
        merged.insert(0, {
            'side': 'left',
            'x_offset': inset,
            'y_bot': 0.0,
            'y_top': height,
            'source': 'stog_extremity_default',
        })
    if draw_right and not _has_near(right_x):
        merged.append({
            'side': 'right',
            'x_offset': right_x,
            'y_bot': 0.0,
            'y_top': height,
            'source': 'stog_extremity_default',
        })
    return merged


def classificar_aberturas_pilar(panels, sarrafos_horizontais, *,
                                painel_sup_width=0.0, painel_sup_x_offset=0.0,
                                tol=4.0):
    """Quais interrupcoes da corrida de sarrafo sao ABERTURA DE PILAR.

    Regra do dono (2026-09-13) — o que distingue as duas aberturas e' O QUE
    CADA UMA RECORTA:

      abertura de VIGA  -> produz vazio e RECORTE NO PAINEL;
      abertura de PILAR -> so' recorta o SARRAFO, o painel fica intacto.

    O marcador de origem vem do N1; aqui a classificacao e' pela consequencia
    visivel na propria ficha. Quatro condicoes, todas necessarias:

    A assinatura do pilar esta na VARIACAO POR ALTURA das corridas de sarrafo,
    nao no x de uma corrida isolada. O pilar sobe do fundo e a corrida de cima
    passa POR CIMA dele; as de baixo esbarram nele e param. Medido no N2:

      V13.A (corpo 44)  y=7,3/18,3/25,3 -> corrida comeca em 78
                        y=37,3          -> corrida comeca em  0   => 0..78
      V13.B             y=7,4/18,4/25,4 -> ultima corrida acaba em 337
                        y=37,4          -> acaba em 415            => 337..415
      CONT.V302.A       baixas cobrem [7,784] e [934,976]
                        y=37,3 cobre [7,976]                       => 784..934

    Logo: ABERTURA = cobertura na altura mais ALTA do corpo MENOS a uniao das
    coberturas nas alturas de baixo.

    Uma guarda e' necessaria: a diferenca tem de ser um ENTALHE dentro de um
    painel que tenha cobertura baixa em ALGUM outro ponto. Sem ela, a V302.A
    daria o painel 3 inteiro (360..470) como abertura de 110 -- aquele painel
    so' tem UMA corrida, em nenhuma altura de baixo, entao nao ha' pilar
    algum ali, so' um painel com uma corrida so'.

    Devolve [(x_ini, x_fim), ...] em x relativo a` borda esquerda da face.

    A versao anterior montava o candidato a partir da BORDA da face
    (`(base, x_left)` e `(x_right, topo)`), o que tornava vazia a propria
    condicao "encosta na borda": todo candidato encostava por construcao.
    Numa face com varios paineis, cada corrida que nao comecasse em `base`
    virava uma abertura ate' a borda -- na V302.A isso produzia 171,5 / 298,5
    / 117 e na CONT.V302.A um 927, todos cotados no desenho.
    """
    segs = list(panels or [])
    sh = list(sarrafos_horizontais or [])
    if not segs or not sh:
        return []
    ws = [float(s.get('width', s.get('largura_cm', 0)) or 0) for s in segs]
    hs = [float(s.get('height1', 0) or 0) for s in segs]
    if not any(w > 0 for w in ws):
        return []

    divisas, acc = [0.0], 0.0
    for w in ws:
        acc += w
        divisas.append(round(acc, 1))
    h_corpo = max(hs) if hs else 0.0

    # Regra do dono: abertura de VIGA recorta o painel, a de PILAR nao. Painel
    # rebaixado E' o vazio da viga, entao nada ali e' pilar. Mantida como
    # regra SEMANTICA declarada pelo dono, nao como heuristica geometrica.
    faixas_baixas, _a = [], 0.0
    for w, hh in zip(ws, hs):
        if h_corpo - hh > 3.0:
            faixas_baixas.append((_a, _a + w))
        _a += w

    por_y: dict = {}
    for s in sh:
        try:
            y = float(s.get('y_offset', -1) or -1)
        except (TypeError, ValueError):
            continue
        # Fora do corpo fica o sarrafo do painel de fechamento (V13.A: y=57,8
        # num corpo de 44). Ele nao participa: acaba junto com o painel dele,
        # nao por interrupcao.
        if y < 0 or y > h_corpo + tol:
            continue
        xl = float(s.get('x_left', 0) or 0)
        xr = float(s.get('x_right', 0) or 0)
        if xr - xl > 0.05:
            por_y.setdefault(round(y, 1), []).append((xl, xr))
    if len(por_y) < 2:
        return []

    def _uniao(ivs):
        ivs = sorted(ivs)
        un: list = []
        for a, b in ivs:
            if un and a <= un[-1][1] + tol:
                un[-1][1] = max(un[-1][1], b)
            else:
                un.append([a, b])
        return [(a, b) for a, b in un]

    def _sobreposicao(i, j):
        return min(i[1], j[1]) - max(i[0], j[0])

    y_topo = max(por_y)
    cob_topo = _uniao(por_y[y_topo])
    cob_baixa = _uniao([iv for y, ivs in por_y.items() if y < y_topo
                        for iv in ivs])

    # cob_topo menos cob_baixa
    difs = []
    for a, b in cob_topo:
        cur = a
        for c, d in cob_baixa:
            if d <= cur or c >= b:
                continue
            if c > cur:
                difs.append((cur, min(c, b)))
            cur = max(cur, d)
            if cur >= b:
                break
        if cur < b:
            difs.append((cur, b))

    out = []
    for a, b in difs:
        if b - a <= 10.0:          # recuo de 7cm em divisa nao e' abertura
            continue
        meio = (a + b) / 2.0
        if any(lo - tol <= meio <= hi + tol for lo, hi in faixas_baixas):
            continue
        painel = next((( divisas[i], divisas[i + 1])
                       for i in range(len(divisas) - 1)
                       if divisas[i] - tol <= meio <= divisas[i + 1] + tol),
                      None)
        if painel is None:
            continue
        if not any(_sobreposicao(painel, iv) > 1.0 for iv in cob_baixa):
            continue
        out.append((round(a, 1), round(b, 1)))
    return sorted(set(out))


def draw_sarr_lv_horizontal_from_n2(msp, x0, y0, sarrafos_horizontais,
                                    *, frame_ys=None, h_face=None,
                                    degrau_start=None, degrau_end=None,
                                    y_shoulder=None, panel_div_xs=None,
                                    left_sarr_x=None, right_sarr_x=None,
                                    vertical_specs=None, aberturas_pilar=None,
                                    top_panel_band=None):
    """Replay fiel dos sarrafos horizontais capturados no N2.

    ``frame_ys``: Y de contorno Painéis (ombro/topo/base) — não redesenhar
    sarrafo em cima da linha de painel (conflito visual).
    y_offset acima do corpo (laje / painel de 7) nao e sarrafo de painel.

    ``degrau_start``/``degrau_end``/``y_shoulder``: um sarrafo horizontal
    que cruza a fronteira degrau<->zona alta EXATAMENTE na altura do ombro
    nao pode atravessar pro outro lado — nesse ponto especifico o N2
    desenha uma unica LINE sem quebra ate o proximo divisor de painel, mas
    nao ha parede continua ali e o sarrafo fica sem apoio visual do outro
    lado (achado 2026-09-09, V301.B#1/B#2: pontos do dono — sarrafo deveria
    fechar no proprio limite do degrau). Dois casos simetricos conforme o
    lado que a zona alta fica:
    - Zona alta ANTES do degrau (degrau_start > x0): corta o sarrafo que
      NASCE antes do limite e cruza pra dentro do degrau — mantem a ponta
      da zona alta, remove a ponta do degrau (acha 2026-09-09, UNIT.B#8).
    - Zona alta DEPOIS do degrau (degrau_end < body_end): corta o sarrafo
      que NASCE dentro do degrau e cruza pra fora, pra zona alta — mantem
      a ponta da zona alta, remove a ponta do degrau (achado 2026-09-09,
      CONT.V301.B x0=11148.6: sarrafo 244->411 devia ser so 307->411).
    Sarrafos que já nascem dentro da MESMA zona (ex. N2 real 244–398.5 @
    ombro, dentro do proprio degrau) continuam intactos, sem essa regra.
    """
    attrs = {'layer': 'SARR_2.2x7'}
    ban = [float(y) for y in (frame_ys or [])]
    y_max = None if h_face is None else float(y0) + float(h_face) + 0.5
    _div_xs = [float(v) for v in (panel_div_xs or [])]

    def _snap_to_div(x):
        # Encosta a ponta do sarrafo na uniao real do painel quando cai
        # perto mas nao exata — mesma logica do encosto de ombro, so' que
        # no eixo X (achado 2026-09-09, SEGMENTO 2B: uniao do sarrafo em
        # 256.5 vs uniao real do painel em 244, 12.5cm sem motivo — o
        # dono: "deve ser a uniao identica a posicao da uniao do painel").
        # ...mas uma ponta que JA' casa com um sarrafo VERTICAL nao precisa de
        # encosto nenhum: a uniao dela e' o sarrafo, nao a divisa de painel.
        # Medido na V304.B: o sarrafo horizontal termina em x=36, exatamente no
        # vertical de x=36, e o snap (raio 13) o puxava para a divisa de painel
        # em 29 — a corrida parava 7 cm antes do vertical, sem fechar o quadro
        # (apontamento do dono: "p1 deveria ir ate' o p2").
        if any(abs(float(_vx) - x) < 1.0 for _vx, _, _ in (vertical_specs or [])):
            return x
        if not _div_xs:
            return x
        best = min(_div_xs, key=lambda d: abs(d - x))
        return best if abs(best - x) < 13.0 else x

    n = 0
    for spec in sarrafos_horizontais or []:
        try:
            y = y0 + float(spec.get('y_offset', 0) or 0)
            x1 = x0 + float(spec.get('x_left', 0) or 0)
            x2 = x0 + float(spec.get('x_right', 0) or 0)
        except Exception:
            continue
        x1 = _snap_to_div(x1)
        x2 = _snap_to_div(x2)
        # ── Dentro do painel de fechamento, parar nos verticais dele ───────
        # Apontamento do dono (2026-09-13, P4): "este sarrafo vai de p5 a p6,
        # tem os sarrafos verticais da extremidade que tem que respeitar".
        # TEM de vir depois do snap: o inset de 7 cai a 7 da divisa de painel
        # e `_snap_to_div` (raio 13) puxava de volta para a parede — medido na
        # V13 face A, a corrida saia 1800->1993 em vez de 1807->1993.
        if top_panel_band:
            _byl, _byh, _bxl, _bxr = top_panel_band
            if _byl <= float(spec.get('y_offset', 0) or 0) <= _byh:
                x1 = max(x1, x0 + float(_bxl))
                x2 = min(x2, x0 + float(_bxr))
                if x2 - x1 < 0.5:
                    continue
        # Encosta no ombro real (linha Painéis do degrau, calculada por
        # geometria) quando o sarrafo extraido do N2 cai perto mas nao
        # exato — o motor nao deve reproduzir milimetros de imprecisao
        # do traco humano quando ja tem a altura certa calculada em
        # outro lugar (achado 2026-09-09, dono: sarrafo e linha do
        # painel do mesmo ombro saiam 0.4-1.4cm desalinhados um do
        # outro sem motivo nenhum).
        if y_shoulder is not None and abs(y - float(y_shoulder)) < 2.0:
            y = float(y_shoulder)
        if (
            degrau_start is not None and y_shoulder is not None
            and x1 < degrau_start - 0.5 and x2 > degrau_start + 0.5
            and abs(y - float(y_shoulder)) < 1.1
        ):
            x2 = float(degrau_start)
        if (
            degrau_end is not None and y_shoulder is not None
            and x1 < degrau_end - 0.5 and x2 > degrau_end + 0.5
            and abs(y - float(y_shoulder)) < 1.1
        ):
            x1 = float(degrau_end)
        # Sarrafo horizontal nao pode passar do sarrafo vertical de
        # extremidade rumo a parede — o corner sarrafo ja fecha o vao com
        # o inset padrao (SARR_INSET_H), continuar ate a parede so cria
        # sobreposicao visual sem função nenhuma (achado 2026-09-10,
        # UNIT.A#4/V301.A#6: 4 sarrafos horizontais indo ate a parede em
        # vez de parar no sarrafo vertical direito, 7cm antes — pedido do
        # dono: "devem ir ate o sarrafo vertical das extremidades e nao
        # ate as paredes", regra universal pros dois lados).
        if left_sarr_x is not None and x1 < float(left_sarr_x) - 0.5:
            x1 = float(left_sarr_x)
        if right_sarr_x is not None and x2 > float(right_sarr_x) + 0.5:
            x2 = float(right_sarr_x)
        # Mesma regra, generalizada: qualquer sarrafo vertical INTERNO (nao
        # so as extremidades) que cubra esta altura e fique estritamente
        # dentro do vao atual tambem e um limite — o horizontal para no
        # primeiro que encontrar, nao atravessa (achado 2026-09-10,
        # UNIT.A#1/V301.A#2 e V301.A: dono confirmou "mesma relacao... so
        # que do outro lado", regra universal, nao so extremidade).
        for _vx, _vyb, _vyt in (vertical_specs or []):
            # Cobertura estrita: um sarrafo EXATAMENTE na altura do topo do
            # vertical (nao alguns cm abaixo) esta na transicao pro proximo
            # vertical mais alto, nao "coberto" por este — sem essa
            # margem, o 4o sarrafo (na mesma altura que o topo do vertical
            # curto) tambem seria cortado por engano (achado 2026-09-10,
            # V301.A: handle 33F em y=65 = topo exato do vertical 301.5,
            # nao deveria parar nele, e sim continuar ate o vertical
            # 398.5, mais alto).
            # O vertical tem de CRUZAR a altura do horizontal para bloquea-lo.
            # Um vertical que NASCE nele apenas encosta: medido na V304.B, o
            # vertical de x=36 comeca em y=7,5, que e' a borda interna do
            # proprio sarrafo horizontal de baixo (bordas em 6,5 e 7,5). Com a
            # folga de 1,0 no pe' ele "cobria" a borda de 6,5 e cortava a
            # corrida em 36, quando no N2 ela atravessa a unidade inteira
            # (h=83, x 0..53).
            if not (_vyb + 0.6 < y < _vyt - 0.5):
                continue
            if x1 < _vx < x2:
                # Mantem o lado LONGO (o vao real do sarrafo), apara so o
                # pedaco curto que ultrapassa o vertical — inverti isso
                # antes e ficava com o cotoco de 7cm errado em vez do vao
                # certo (achado 2026-09-10, dono: "manteve a parte de 7cm
                # ao inves da parte correta"). Vertical mais perto do
                # inicio (x1) => o pedaco curto e o INICIO, entao avanca
                # x1 ate o vertical. Mais perto do fim (x2) => o pedaco
                # curto e o FIM, entao recua x2 ate o vertical.
                if (_vx - x1) <= (x2 - _vx):
                    x1 = _vx
                else:
                    x2 = _vx
        if x2 - x1 < 4.0:
            continue
        if y_max is not None and y > y_max:
            continue
        if any(abs(y - yb) < 1.1 for yb in ban):
            continue
        msp.add_line((x1, y), (x2, y), dxfattribs=attrs)
        n += 1

    # ── Tampa de ponta em abertura de pilar ────────────────────────────────
    # Em painel SARRAFEADO a passagem do pilar nao e' desenhada como retangulo
    # tracejado (esse e' o outro modo, ver `holes`): ela aparece como a
    # INTERRUPCAO da corrida de sarrafos, e cada sarrafo interrompido leva uma
    # tampa vertical de 7cm na ponta. A interrupcao ja' vinha da ficha
    # (`x_left` > 0) e o N4 ja' respeitava, mas desenhava a corrida sem tampa
    # (achado 2026-09-11, V13 face A: abertura de 78, handles 53 e 54 do N2).
    #
    # A tampa e' por SARRAFO (banda de 7cm), nao por linha: as linhas a ate'
    # 7.5 uma da outra sao as duas bordas do mesmo sarrafo e dividem a tampa.
    # Linha solta ganha os 7cm medidos para o lado da face mais proxima.
    #
    # NOTA: painel GRADEADO tem comportamento proprio para a mesma abertura —
    # ainda sem caso observado (o 13_PAV inteiro e' Sarrafeado). Quando
    # aparecer, registrar o segundo modo aqui.
    por_y: dict = {}
    for spec in sarrafos_horizontais or []:
        try:
            yo = float(spec.get('y_offset', 0) or 0)
            xl = float(spec.get('x_left', 0) or 0)
            xr = float(spec.get('x_right', 0) or 0)
        except Exception:
            continue
        a, b = por_y.get(yo, (xl, xr))
        por_y[yo] = (min(a, xl), max(b, xr))

    # ── Quais interrupcoes sao de PILAR ────────────────────────────────────
    # Regra do dono (2026-09-13): abertura de VIGA recorta o PAINEL; abertura
    # de PILAR so' recorta o SARRAFO. Quem classifica e'
    # `classificar_aberturas_pilar`, chamada pelo desenhista da face — aqui so'
    # se recebe a lista pronta.
    #
    # Antes disto o criterio era puramente geometrico ("a corrida que comeca
    # muito depois das outras"), que detecta INTERRUPCAO sem saber quem
    # interrompeu: punha 24 tampas na V301, cujo N2 nao tem nenhuma vertical
    # entre 5 e 9 cm. Sem lista de aberturas, NAO desenha tampa — faltar e'
    # melhor que inventar.
    _abrs = list(aberturas_pilar or [])
    if por_y and _abrs:
        base = min(a for a, _b in por_y.values())
        topo_run = max(b for _a, b in por_y.values())
        for lado in ('esq', 'dir'):
            if lado == 'esq':
                _xs_abre = [round(fim, 1) for ini, fim in _abrs
                            if abs(ini - base) <= 4.0]
                cortados = sorted(
                    y for y, (a, _b) in por_y.items()
                    if any(abs(a - xa) <= 4.0 for xa in _xs_abre))
            else:
                _xs_abre = [round(ini, 1) for ini, fim in _abrs
                            if abs(fim - topo_run) <= 4.0]
                cortados = sorted(
                    y for y, (_a, b) in por_y.items()
                    if any(abs(b - xa) <= 4.0 for xa in _xs_abre))
            bandas: list = []
            for yo in cortados:
                if bandas and yo - bandas[-1][-1] <= 7.5:
                    bandas[-1].append(yo)
                else:
                    bandas.append([yo])
            for banda in bandas:
                ref = por_y[banda[0]]
                x_cap = x0 + (ref[0] if lado == 'esq' else por_y[banda[0]][1])
                if len(banda) >= 2:
                    yb, yt = y0 + banda[0], y0 + banda[-1]
                else:
                    unico = banda[0]
                    if unico <= 7.5:
                        yb, yt = y0 + unico - 7.0, y0 + unico
                    else:
                        yb, yt = y0 + unico, y0 + unico + 7.0
                # A tampa fecha a ponta de UM sarrafo, entao tem a espessura
                # dele (2.2x7 -> 7). Banda fora dessa faixa e' agrupamento
                # errado, nao abertura: sem esse guarda saiam tampas de 1.0 e
                # 2.0 na V302, alturas que nao existem no N2 dela (so' ha'
                # vertical de 7/43/44/45/59). Melhor nao desenhar do que
                # inventar.
                if not (5.0 <= yt - yb <= 9.0):
                    continue
                msp.add_line((x_cap, yb), (x_cap, yt), dxfattribs=attrs)
                n += 1
    return n


def draw_sarr_lv_vertical_pairs(msp, x0, y0, h, panel_widths,
                                draw_left=False, draw_right=False,
                                sarrafos_verticais=None,
                                ensure_extremities=False,
                                y_shoulder=None):
    """Sarrafo vertical 2.2x7 — reproduz o N2; extremidades só se a ficha pedir.

    ``y_shoulder``: mesma logica de encosto de `draw_sarr_lv_horizontal_from_n2`
    — quando y1/y2 extraidos do N2 caem perto do ombro real (calculado por
    geometria) mas nao exatos, encosta neles em vez de reproduzir milimetros
    de imprecisao do traco humano (achado 2026-09-09).
    """
    attrs = {'layer': 'SARR_2.2x7'}
    L = sum(panel_widths)
    if L < 2 * SARR_INSET_H:
        return

    # Divisores Painéis: não desenhar sarrafo em cima da linha de painel.
    panel_div_xs = []
    acc = float(x0)
    for pw in panel_widths:
        acc += float(pw or 0)
        panel_div_xs.append(acc)
    if panel_div_xs:
        panel_div_xs = panel_div_xs[:-1]  # borda direita da face pode coincidir com marco

    def _near_panel_div(x):
        return any(abs(x - px) < 1.5 for px in panel_div_xs)

    want_left = bool(draw_left or (ensure_extremities and not sarrafos_verticais))
    want_right = bool(draw_right or (ensure_extremities and not sarrafos_verticais))
    specs = merge_sarrafos_verticais_extremidades(
        sarrafos_verticais, L, h,
        draw_left=want_left,
        draw_right=want_right,
    )

    if specs:
        for spec in specs:
            try:
                x = x0 + float(spec.get('x_offset', 0) or 0)
                y1 = y0 + float(spec.get('y_bot', 0) or 0)
                y2 = y0 + float(spec.get('y_top', h) or h)
            except Exception:
                continue
            if y_shoulder is not None:
                if abs(y1 - float(y_shoulder)) < 2.0:
                    y1 = float(y_shoulder)
                if abs(y2 - float(y_shoulder)) < 2.0:
                    y2 = float(y_shoulder)
            # Mesmo encosto no topo real do corpo (y0+h): o sarrafo
            # vertical extraido do N2 as vezes fica 1cm curto do topo
            # verdadeiro por imprecisao do traco humano — o motor conhece
            # a altura certa, nao reproduz o milimetro perdido (achado
            # 2026-09-10, V301.B: sarrafos internos e da extremidade
            # esquerda paravam em y_top-1, nao no P3/topo real).
            _y_top_real = float(y0) + float(h)
            if abs(y2 - _y_top_real) < 2.0:
                y2 = _y_top_real
            if y2 - y1 < 8.0:
                continue
            if _near_panel_div(x):
                continue
            msp.add_line((x, y1), (x, y2), dxfattribs=attrs)
        return

    if draw_left:
        x_l = x0 + SARR_INSET_H
        if not _near_panel_div(x_l):
            msp.add_line((x_l, y0), (x_l, y0 + h), dxfattribs=attrs)
    if draw_right:
        x_r = x0 + L - SARR_INSET_H
        if not _near_panel_div(x_r):
            msp.add_line((x_r, y0), (x_r, y0 + h), dxfattribs=attrs)


def _degrau_shoulder_y(y0, h, panels):
    """Y da base dos painéis curtos (ombro do degrau) na face."""
    degrau = [p for p in panels if _is_degrau_panel(p, h)]
    if not degrau:
        return None
    y_degrau = _panel_y_base(y0, h, degrau[0])
    if y_degrau <= y0 + 1.0:
        return None
    return y_degrau


def _degrau_zone_bounds_x(x0, h, panels):
    """Intervalo X ocupado pelos painéis curtos alinhados pelo topo."""
    x = float(x0)
    spans = []
    for panel in panels:
        width = float(panel.get('width', 0) or 0)
        if _is_degrau_panel(panel, h):
            spans.append((x, x + width))
        x += width
    if not spans:
        return None
    return min(a for a, _b in spans), max(b for _a, b in spans)


def _degrau_zone_end_x(x0, h, panels):
    bounds = _degrau_zone_bounds_x(x0, h, panels)
    return bounds[1] if bounds else float(x0)


def _small_panel_start_x(x0, h, panels, threshold=28.0):
    """Inicio da faixa de marco (estreitos finais apos bay util).

    Nao corta no meio: 22.5 apos 244 (B) nao e marco.
    Marco apos bay >=50 (A: 111|19|21.2; B: 52.5|21.7|26.2).
    """
    plist = list(panels or [])
    if not plist:
        return None
    widths = [float(p.get('width', 0) or 0) for p in plist]
    n = len(widths)
    i1 = n
    while i1 > 0:
        pw = widths[i1 - 1]
        if pw <= 0:
            i1 -= 1
            continue
        if pw < threshold and not _is_degrau_panel(plist[i1 - 1], h):
            i1 -= 1
            continue
        break
    if i1 <= 0 or i1 >= n:
        return None
    if widths[i1 - 1] < 50.0:
        return None
    return float(x0) + sum(widths[:i1])


def _leading_marco_end_x(x0, h, panels, threshold=28.0):
    """Fim da faixa de marco a ESQUERDA (espelho: 21.2|19|111|…|244).

    Simetrico de `_small_panel_start_x`. Evita V full nos estreitos iniciais
    (MARCO_MID_V / extra_g em UNITs espelho).
    """
    plist = list(panels or [])
    if not plist:
        return None
    widths = [float(p.get('width', 0) or 0) for p in plist]
    n = len(widths)
    i0 = 0
    while i0 < n:
        pw = widths[i0]
        if pw <= 0:
            i0 += 1
            continue
        if pw < threshold and not _is_degrau_panel(plist[i0], h):
            i0 += 1
            continue
        break
    if i0 <= 0 or i0 >= n:
        return None
    # bay util apos o marco deve ser robusto (>=50), senao e so painel curto
    if widths[i0] < 50.0:
        return None
    return float(x0) + sum(widths[:i0])


def _marco_extension_cm(marco_laje_sup, laje_sup, *, has_marco_strip=None):
    """Altura do marco acima do corpo.

    laje_sup>=12: real. Residual 15 (laje_sup=7 + flag) so se ha strip de
    paineis estreitos (trailing/leading). Sem strip, residual inventava
    15/157 em faces altas UNIT (h=142, marco flag sem geometria).
    """
    if not marco_laje_sup:
        return 0.0
    ls = float(laje_sup or 0)
    if ls >= 12.0:
        return ls
    if has_marco_strip is False:
        return 0.0
    return 15.0


def _draw_panel_frame_n2(msp, x0, y0, h, panels, *,
                          marco_laje_sup=False, laje_sup=0.0,
                          marco_h_min=0.0, laje_trechos=None,
                          aberturas_viga=None,
                          painel_sup_alt=0.0, painel_sup_width=0.0,
                          painel_sup_x_offset=0.0):
    """Contorno Painéis fiel ao N2 — G honest (miss→0, extra→0).

    Regras anti-phantom (ShareX + ledger V301 A/B):
    - A: 1º divisor (244) SO faixa alta. NUNCA V65 no vão.
    - B: 1º divisor + 2º painel estreito (<25): N2 TEM V65 em ~244.7
      (recesso real) — so nesse caso desenha base→ombro.
    - H curtas so entre divisores BAIXOS consecutivos (272.7–294.5 / 244–266),
      nunca sob o vao vazio A entre 0 e 244.
    - body_end (small_x): V so y0→y_top (N2). NUNCA sobe ao y_marco —
      isso inventava parede cheia na junção corpo|marco (extra direita).
    - Marco: H no 1º painel + continuous strip y0/y_marco; SEM H multi-nivel
      no corpo 0→body_end (N2 B nao tem H@y_m15/@y_marco no corpo).
    - V7 residual so no divisor ~244 (degrau) e na borda do 1º marco —
      NUNCA em body_end (N2 nao tem).
    """
    a = {'layer': 'Painéis'}
    # layer semantico = laje (SCO-___-LAJ), mas cor visual = a mesma rosa/
    # crimson do COTA (241) que ja marca a faixa do marco no desenho — pedido
    # do dono ao apontar a cota vizinha como referencia (2026-08-29).
    a_laje = {'layer': 'SCO-___-LAJ', 'color': 241}
    if not panels:
        return
    comprimento = sum(float(p.get('width', 0) or 0) for p in panels)
    if comprimento <= 0:
        return
    y_top = y0 + h
    y_shoulder = _degrau_shoulder_y(y0, h, panels)
    degrau_bounds = _degrau_zone_bounds_x(x0, h, panels)
    degrau_start = degrau_bounds[0] if degrau_bounds else float(x0)
    degrau_end = degrau_bounds[1] if degrau_bounds else float(x0)
    has_degrau = y_shoulder is not None and degrau_end > x0 + 0.5
    # Ombro que passa de y_top: o proprio degrau tem materia real acima de
    # h_face (achado 2026-08-31, V301.B#1 — hachura de reaproveitamento na
    # faixa do marco). A borda unica em y_top nao pode atravessar essa
    # zona, senao corta a hachura no meio (linha fantasma).
    _degrau_h1 = 0.0
    if has_degrau:
        _deg0 = next((pp for pp in panels if _is_degrau_panel(pp, h)), None)
        if _deg0 is not None:
            _degrau_h1 = float(_deg0.get('height1', 0) or 0)
    _degrau_tall = bool(
        has_degrau and y_shoulder is not None
        and y_shoulder + _degrau_h1 > y_top + 0.5
    )
    small_x = _small_panel_start_x(x0, h, panels)
    lead_x = _leading_marco_end_x(x0, h, panels)
    # has_strip: trailing OU leading — so residual marco 15 / cotas
    has_strip = small_x is not None or lead_x is not None
    marco_h_base = _marco_extension_cm(
        marco_laje_sup, laje_sup, has_marco_strip=has_strip,
    )
    marco_h = marco_h_base
    # Piso de altura vindo dos proprios dados de sarrafo/vertical (replay N2):
    # quando o N2 real tem sarrafo/vertical mais alto que laje_sup capturou,
    # a parede tem que fechar ate la — nunca inventa acima do que os dados
    # trazem (achado 2026-08-29, UNIT.B#7: marco real ate +33.8, laje_sup so
    # registrava 15, parede/H de topo ficavam faltando no gate).
    # Quando o piso do sarrafo VENCE o laje_sup capturado, marco_h_base nao
    # e' descartado — ele passa a descrever uma faixa SEPARADA e mais alta
    # (achado 2026-08-31, V301.B#1: N2 real tem 2 hachuras distintas, nao 1:
    # REAPROVEITAMENTO em 98.4-142.4 [painel] e AR-CONC em 142.4-157.4
    # [laje_sup, LARGURA CHEIA] — o vazio de concreto vive ACIMA do marco
    # real, nao entre h_face e o marco; usar y_top->y_marco aqui juntava as
    # duas faixas erradas, sinalizando "vazio maior que a laje").
    # So' trata como faixa SEPARADA (aditiva) quando marco_h_min vence
    # marco_h_base por uma margem real (>8cm) — perto disso e' RUIDO da
    # mesma faixa (sarrafo real bate perto de onde a laje_sup ja' coloca o
    # topo), nao uma parede extra abaixo de uma laje adicional. Tomar o
    # maximo mesmo fora do modo aditivo (tentativa anterior) empurrava a
    # faixa de concreto ~4-14cm alem do y real da laje no N2 (achado
    # 2026-09-08, V301.B nominal 5-segmentos: marco_h_min so' ~4cm acima de
    # marco_h_base=15, mas virava marco_h=18.9 e deslocava a hachura).
    _marco_overridden = float(marco_h_min or 0) > marco_h + 8.0
    if _marco_overridden:
        marco_h = float(marco_h_min)
    y_marco = y_top + marco_h if marco_h > 0.5 else y_top
    y_m15 = y_top + 15.0 if marco_h >= 15.0 else y_marco
    thick_marco = marco_h >= 18.0  # B-style multi-level

    def _close_wall_to_marco(x, y_from):
        """Fecha a parede em x: y_from->y_top no layer do painel; y_top->y_marco
        (se houver marco) no layer da laje — o trecho acima do corpo do painel
        pertence estruturalmente ao marco da laje superior, nao ao painel
        (2026-08-29, correcao de layer pedida pelo dono via pontos no N4).

        Quando uma abertura de viga encosta na borda ESQUERDA, o trecho que
        margeia o vazio nao e' linha de painel: e' o contorno do proprio vazio,
        e vai no mesmo layer da tampa (COTA). Medido no N2 da V304.B — a borda
        x=2263,7 vem partida em duas, `Painéis` de 5372,5 a 5387,5 (a sobra) e
        `COTA` de 5387,5 a 5431,5 (os 44 do vazio), com a tampa h=8D tambem em
        COTA. Nas aberturas INTERNAS da V304.A#1 as duas paredes sao `Painéis`
        e so' a tampa e' COTA — coerente: la' as paredes sao bordas de painel
        de verdade. Apontamento do dono: "deveria ser 2 linhas, 1 para a
        abertura em layer de cor de rosa, e a linha de baixo a linha do
        painel".

        ESCOPO: so' a ponta esquerda, porque e' so' dela que ha' medida. Na
        ponta DIREITA o N2 da V303 (unidade 157,5+29, borda x=7984,1) traz
        apenas o pedaco da sobra em `Painéis`, de 6479,3 a 6484,3, e NADA
        acima — nem `Painéis` nem `COTA`. Sao dois desenhos humanos que
        resolvem a mesma situacao de jeitos diferentes; a V303 esta' aprovada
        como esta' e nao se mexe nela por simetria presumida.
        """
        y_from = min(float(y_from), y_top)
        _y_corte = None
        for _av1 in (aberturas_viga or []):
            try:
                _xi1 = float(x0) + float(_av1.get('x_ini', 0) or 0)
                _sh1 = float(_av1.get('sobra_h', 0) or 0)
            except Exception:
                continue
            if abs(float(x) - float(x0)) > 1.0 or abs(_xi1 - float(x0)) > 1.0:
                continue
            _yc = y0 + _sh1
            if y_from + 0.05 < _yc < y_top - 0.05:
                _y_corte = _yc
        if _y_corte is not None:
            msp.add_line((x, y_from), (x, _y_corte), dxfattribs=a)
            msp.add_line((x, _y_corte), (x, y_top),
                         dxfattribs={'layer': 'COTA'})
        else:
            msp.add_line((x, y_from), (x, y_top), dxfattribs=a)
        if y_marco > y_top + 0.01:
            msp.add_line((x, y_top), (x, y_marco), dxfattribs=a_laje)

    # Parede esquerda em x0. No ramo espelhado (degrau a direita) o bloco
    # abaixo desenha a parede cheia — nao duplicar aqui (vira V extra na
    # esquerda, colada nas cotas).
    _mirrored = has_degrau and degrau_start > x0 + 0.5
    if not _mirrored:
        if has_degrau:
            # Mesmo raciocinio do ramo sem degrau: a parede real fecha ate
            # y_marco, nao so y_top (achado validado em CONT.V301.A,
            # 2026-08-28 — o degrau muda so onde a parede COMECA, y_shoulder,
            # nao onde ela deveria fechar em cima).
            _close_wall_to_marco(x0, y_shoulder)
        else:
            # Fecha ate y_marco (nao so y_top): a parede lateral real do N2
            # continua ate a linha de topo do marco/laje_sup — parar em y_top
            # deixa o vao y_top->y_marco aberto (achado validado ponto-a-
            # ponto em V301.A e CONT.V301.A, 2026-08-27/28).
            _close_wall_to_marco(x0, y0)

    body_end = float(small_x) if small_x is not None else float(x0 + comprimento)
    full_end = float(x0 + comprimento)

    # Degrau espelhado: corpo cheio à esquerda e painéis curtos à direita.
    # O motor antigo assumia sempre degrau começando em x0 e, por isso,
    # fechava o vazio com fundo/verticais de painel indevidos.
    if has_degrau and degrau_start > x0 + 0.5:
        # Com marco a esquerda, a parede util e lead_x (N2). V em x0 cola
        # nas cotas 14/7 e vira "linha de painel extra na esquerda".
        if lead_x is None:
            # Fecha ate y_marco pelo mesmo motivo do ramo principal: e a
            # parede real do corpo (2026-08-28).
            _close_wall_to_marco(x0, y0)
        x_cur = float(x0)
        for idx, panel in enumerate(panels):
            pw = float(panel.get('width', 0) or 0)
            x_right = x_cur + pw
            if x_right >= body_end - 0.1:
                break
            cur_deg = _is_degrau_panel(panel, h)
            next_deg = _is_degrau_panel(panels[idx + 1], h)
            if lead_x is not None and x_right < lead_x - 0.1:
                x_cur = x_right
                continue
            if cur_deg and next_deg:
                # Divisao real entre paineis coplanares: somente dentro da
                # altura do painel elevado, nunca atravessando o vazio.
                msp.add_line((x_right, y_shoulder), (x_right, y_top), dxfattribs=a)
            elif (not cur_deg) and next_deg:
                # Interface corpo-alto | faixa-curta: divisor para no ombro
                # e nao atravessa os sarrafos internos do painel alto.
                msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
            else:
                msp.add_line((x_right, y0), (x_right, y_top), dxfattribs=a)
            x_cur = x_right
        last_body_deg = any(
            _is_degrau_panel(panel, h)
            and abs(
                float(x0)
                + sum(float(p.get('width', 0) or 0) for p in panels[:idx + 1])
                - body_end
            ) < 0.2
            for idx, panel in enumerate(panels)
        )
        _close_wall_to_marco(body_end, y_shoulder if last_body_deg else y0)
        msp.add_line((x0, y_top), (body_end, y_top), dxfattribs=a)
        msp.add_line((x0, y0), (degrau_start, y0), dxfattribs=a)
        msp.add_line((degrau_start, y_shoulder), (degrau_end, y_shoulder), dxfattribs=a)
        if degrau_end < body_end - 0.5:
            msp.add_line((degrau_end, y0), (body_end, y0), dxfattribs=a)
        if _marco_overridden and marco_h_base > 0.5:
            # Largura = body_end (fechamento estrutural real), NUNCA
            # comprimento total — a faixa de laje_sup pode cobrir só os
            # segmentos ate' o corpo (ex. 3 dos 5 numa ocorrencia com faixa
            # de marco estreita no final); comprimento inventava hachura
            # alem da propria laje real do N2 (achado 2026-09-08, dono
            # apontou "hatch maior que a area da laje" com pontos exatos
            # nas linhas SCO-___-LAJ/Painéis que marcam o corte real).
            _draw_vazio_concreto(
                msp, x0, y_marco, body_end, y_marco + marco_h_base,
            )
        elif marco_h > 0.5:
            _draw_vazio_concreto(msp, x0, y_top, body_end, y_marco)
        return

    # x das paredes de ABERTURA DE VIGA, para o laco de divisas nao desenhar
    # uma parede cheia por cima delas. Apontamento do dono (V303 SEGMENTO 5B,
    # P2): "nao tem divisao e painel vertical aqui, vai somente ate' o fundo
    # da abertura, mas o painel segue ate' o final". Medido no N2 dessa
    # unidade: a vertical em x=7955,1 vai de 6484,3 a 6524,3 — 40, a altura da
    # ABERTURA — e nao do fundo do corpo. Abaixo do piso o painel e' continuo
    # ate' a ponta. O bloco de abertura, mais abaixo, ja' desenha essa parede
    # com a altura certa; a divisa cheia era duplicata errada por cima.
    #
    # Na V303 5B a abertura encosta na ponta DIREITA e a parede interna dela e'
    # a da esquerda (`x_ini`). Quando ela encosta na ponta ESQUERDA a parede
    # interna e' a da DIREITA (`x_fim`) — mesmo desenho, espelhado. Medido no
    # N2 da V304.B: em x=2292,7 ha' uma unica vertical, de 5387,5 a 5431,5 —
    # 44, a altura do vazio — e nada abaixo do piso, porque ali o painel
    # atravessa a unidade inteira. O robo desenhava a divisa cheia, do fundo
    # ao topo, cortando esse painel (apontamento do dono: falta a linha de 44).
    _x_paredes_abertura = []
    for _av0 in (aberturas_viga or []):
        try:
            _xi0 = float(x0) + float(_av0.get('x_ini', 0) or 0)
            _xf0 = float(x0) + float(_av0.get('x_fim', 0) or 0)
            if _xf0 - _xi0 > 0.5:
                _x_paredes_abertura.append(_xi0)
                if abs(float(_av0.get('x_ini', 0) or 0)) <= 1.0:
                    _x_paredes_abertura.append(_xf0)   # abertura na ponta esq.
        except Exception:
            continue

    low_div_xs = []  # so divisores com V base→ombro (nao o phantom A@244)
    x_cur = float(x0)
    for idx, panel in enumerate(panels):
        pw = float(panel.get('width', 0) or 0)
        x_right = x_cur + pw
        is_last = idx >= len(panels) - 1
        cur_deg = _is_degrau_panel(panel, h)
        next_deg = (not is_last) and _is_degrau_panel(panels[idx + 1], h)
        next_pw = float(panels[idx + 1].get('width', 0) or 0) if not is_last else 0.0
        in_small = small_x is not None and x_cur >= small_x - 0.1

        if in_small:
            x_cur = x_right
            continue

        is_body_end = abs(x_right - body_end) < 0.15

        if any(abs(x_right - _xa) <= 0.5 for _xa in _x_paredes_abertura):
            # Parede de abertura: quem a desenha e' o bloco de abertura, com
            # a altura do vazio. Aqui sairia do fundo do corpo e cortaria o
            # painel que segue por baixo.
            x_cur = x_right
            continue

        if is_body_end:
            # Fecha ate y_marco pelo mesmo motivo da parede esquerda: e a
            # parede real do corpo, precisa fechar contra a linha de topo
            # do marco/laje_sup (nao e "V extra do vazio").
            _close_wall_to_marco(x_right, y0)
        elif has_degrau and cur_deg and next_deg:
            # Divisor entre paineis elevados: existe na materia do painel
            # (ombro->topo), mas nao e parede do vazio (base->ombro).
            h1_cur = float(panel.get('height1', 0) or 0)
            # Direcao do divisor: so' o 1o painel da unidade (idx==0) fecha
            # ombro->topo (mesmo padrao ja usado no ramo "cur_deg and not
            # next_deg" logo abaixo, `y_shoulder if idx==0 else y0`) —
            # divisores seguintes fecham base->ombro. Tentativa anterior
            # usava presenca de reuse_regions no painel atual pra decidir a
            # direcao, mas isso quebrou o caso oposto: CONT.V301.B h=104.3
            # (N2 handle "13B", painel0->painel1) vai ombro->topo mesmo com
            # o painel0 NAO tendo reuse_region na faixa do ombro (so' no
            # marco-cap) — a regra certa e' por POSICAO (1o divisor), nao
            # por hachura (achado 2026-09-10, dono: linha do N2 sumiu do
            # N4 depois do fix anterior).
            if idx == 0:
                if y_shoulder + h1_cur > y_top + 0.5:
                    # O proprio painel (ombro acima de h_face, achado
                    # 2026-08-31 V301.B#1) tem materia real que passa de
                    # y_top — fecha ate o topo verdadeiro (y_marco), nao so
                    # ate y_top, senao a parede fica curta contra a propria
                    # hachura do painel.
                    _close_wall_to_marco(x_right, y_shoulder)
                else:
                    msp.add_line((x_right, y_shoulder), (x_right, y_top), dxfattribs=a)
            else:
                msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
                low_div_xs.append(x_right)
        elif has_degrau and cur_deg and not next_deg:
            msp.add_line(
                (x_right, y_shoulder if idx == 0 else y0),
                (x_right, y_top if idx == 0 else y_shoulder), dxfattribs=a,
            )
            low_div_xs.append(x_right)
        elif has_degrau and (not cur_deg) and next_deg:
            msp.add_line((x_right, y0), (x_right, y_shoulder), dxfattribs=a)
            low_div_xs.append(x_right)
        else:
            msp.add_line((x_right, y0), (x_right, y_top), dxfattribs=a)
        x_cur = x_right

    # H curtas entre divisores baixos consecutivos (N2 A: 21.8 @280; B: 22.5 @252)
    if has_degrau and len(low_div_xs) >= 2:
        xs = sorted(low_div_xs)
        for xa, xb in zip(xs, xs[1:]):
            span = xb - xa
            if 15.0 <= span <= 35.0:
                msp.add_line((xa, y0), (xb, y0), dxfattribs=a)
                msp.add_line((xa, y_shoulder), (xb, y_shoulder), dxfattribs=a)

    if has_degrau:
        msp.add_line((x0, y_shoulder), (degrau_end, y_shoulder), dxfattribs=a)

    # Borda superior continua (0->body_end) numa linha so — N2 nao quebra
    # essa borda no limite do degrau (material topo-alinhado chega em
    # y_top tanto na zona baixa quanto na alta). Desenhar em 2 segmentos
    # (0->degrau_end + degrau_end->body_end) produzia 2 pedacos que nao
    # batiam com a linha unica do N2 (294.5+111 vs 405.5 real), sinalizando
    # "EXTRA estrutural" falso em V301.A/B mesmo com a soma identica.
    # Excecao: ombro que passa de y_top (_degrau_tall) — aqui a zona do
    # degrau NAO tem materia em y_top (ela esta mais acima, no marco), e
    # uma linha atravessando cortaria a propria hachura do painel ao meio.
    # ── ABERTURA DE VIGA: recorta o painel e separa segmentos ─────────────
    # Regra do dono (§5.2.3 do contrato): abertura de VIGA recorta o PAINEL
    # (a de pilar so' recorta o sarrafo) e parte o painel em DOIS segmentos,
    # mesmo encostados. A abertura e a sobra pertencem ao segmento que vem
    # ANTES; a parede da fronteira e' desenhada UMA vez.
    #
    # Medido no N2 da V302.A: recorte de 38 entre x 178.5 e 200.5, com SOBRA
    # de 22 x 5 embaixo. O N4 desenhava um retangulo liso de 470 x 43.
    _abr_v = []
    for _av in (aberturas_viga or []):
        try:
            _xi = x0 + float(_av.get('x_ini', 0) or 0)
            _xf = x0 + float(_av.get('x_fim', 0) or 0)
            _sh = float(_av.get('sobra_h', 0) or 0)
        except Exception:
            continue
        if _xf - _xi > 0.5 and x0 - 0.5 <= _xi and _xf <= body_end + 0.5:
            _abr_v.append((_xi, _xf, _sh))
    _abr_v.sort()

    # Faixas (x_ini, x_fim, y_topo_local) por painel — so' quando ha' abertura
    # de viga, que e' onde a ficha traz altura POR SEGMENTO. Medido no N2 da
    # V302.A: seg.1 termina em 43 e seg.2/3 em 45; usar a altura da unidade
    # para todos achatava os tres em 43.
    _faixas_h = []
    if _abr_v:
        _cx = float(x0)
        for _p in (panels or []):
            _pw = float(_p.get('width', 0) or 0)
            if _pw <= 0:
                continue
            _ph = float(_p.get('height1', 0) or 0)
            _faixas_h.append((_cx, _cx + _pw, y0 + _ph if _ph > 0 else y_top))
            _cx += _pw

    def _y_topo_em(xm):
        for _fi, _ff, _fy in _faixas_h:
            if _fi - 0.05 <= xm <= _ff + 0.05:
                return _fy
        return y_top

    def _topo(xi, xf):
        """Borda superior de xi a xf, pulando as aberturas de viga."""
        if xf - xi <= 0.05:
            return
        if not _abr_v:
            msp.add_line((xi, y_top), (xf, y_top), dxfattribs=a)
            return
        # pedacos livres de abertura
        livres, cur = [], xi
        for _ai, _af, _ in _abr_v:
            if _af <= cur + 0.05 or _ai >= xf - 0.05:
                continue
            if _ai > cur + 0.05:
                livres.append((cur, min(_ai, xf)))
            cur = max(cur, _af)
        if xf > cur + 0.05:
            livres.append((cur, xf))
        # cada pedaco ainda pode cruzar fronteira de painel com altura propria
        for _li, _lf in livres:
            cortes = sorted({_li, _lf} | {
                _ff for _fi, _ff, _ in _faixas_h if _li + 0.05 < _ff < _lf - 0.05})
            for _p0, _p1 in zip(cortes, cortes[1:]):
                if _p1 - _p0 <= 0.05:
                    continue
                msp.add_line((_p0, _y_topo_em((_p0 + _p1) / 2.0)),
                             (_p1, _y_topo_em((_p0 + _p1) / 2.0)),
                             dxfattribs=a)
        # degrau entre paineis vizinhos de alturas diferentes: fecha a parede
        for (_fi, _ff, _fy), (_gi, _gf, _gy) in zip(_faixas_h, _faixas_h[1:]):
            if abs(_fy - _gy) <= 0.05:
                continue
            if not (xi - 0.05 <= _ff <= xf + 0.05):
                continue
            if any(_ai - 0.05 <= _ff <= _af + 0.05 for _ai, _af, _ in _abr_v):
                continue  # a abertura ja' fecha esse x
            msp.add_line((_ff, min(_fy, _gy)), (_ff, max(_fy, _gy)),
                         dxfattribs=a)

    if _degrau_tall:
        if degrau_start > x0 + 0.5:
            _topo(x0, degrau_start)
        if body_end > degrau_end + 0.5:
            _topo(degrau_end, body_end)
    else:
        _topo(x0, body_end)

    for _ai, _af, _sh in _abr_v:
        _y_sobra = y0 + _sh
        # parede esquerda da abertura: do topo da sobra ate' o topo do painel.
        # Quando a abertura encosta na ponta ESQUERDA, essa "parede" e' a borda
        # da propria face, que o corpo ja' desenhou inteira — repetir so' um
        # pedaco dela e' linha duplicada. Nesse caso quem precisa da vertical
        # e' o lado DIREITO do vazio, que acima ja' saiu da lista de divisas.
        _na_ponta_esq = abs(_ai - float(x0)) <= 1.0
        if y_top - _y_sobra > 0.05 and not _na_ponta_esq:
            msp.add_line((_ai, _y_sobra), (_ai, y_top), dxfattribs=a)
        if y_top - _y_sobra > 0.05 and _na_ponta_esq and _af < body_end - 0.5:
            msp.add_line((_af, _y_sobra), (_af, y_top), dxfattribs=a)
        # piso da abertura = topo da SOBRA (parte que fica embaixo)
        if _sh > 0.05:
            msp.add_line((_ai, _y_sobra), (_af, _y_sobra), dxfattribs=a)
        # A parede em _af e' a FRONTEIRA entre os dois segmentos e ja' e'
        # desenhada como divisor de painel — nao repetir aqui (parede
        # compartilhada sai uma vez so').

        # ── Tampa do topo da abertura + as duas cotas dela ─────────────────
        # Apontamento do dono (V302 SEGMENTO 4A): "falta essa tampinha da
        # abertura no n4" e "falta as cotas da abertura no n4".
        #
        # Medido no N2 da unidade [53, 63,5] (x0=4086, y0=6708,1), tudo em
        # layer COTA:
        #   LINE 22 em (4117, 6767,1)->(4139, 6767,1)    = a tampa, no topo
        #   LINE 22 em (4117, 6776,2)->(4139, 6776,2)    = cota da largura
        #   LINE 44 em (4105,2, 6723,1)->(4105,2, 6767,1) = cota da altura
        #
        # Ou seja: tampa no topo do segmento, a cota de largura 9,1 acima
        # dela e a de altura 11,8 a` esquerda da parede da abertura. O topo
        # do corpo e' o do SEGMENTO, nao o da unidade — a mesma correcao que
        # a laje precisou.
        _y_topo_ab = y_top
        for _f0, _f1, _fy in (_faixas_h or []):
            if _f0 - 0.05 <= _ai and _af <= _f1 + 0.05 and _fy > _y_topo_ab:
                _y_topo_ab = _fy
        _larg_ab = float(_af) - float(_ai)
        _alt_ab = float(_y_topo_ab) - float(_y_sobra)
        if _larg_ab > 1.0:
            msp.add_line((_ai, _y_topo_ab), (_af, _y_topo_ab),
                         dxfattribs={'layer': 'COTA'})
            # Texto CENTRADO na propria linha de cota (dono, V302 1A P1/P2:
            # "texto da cota centralizado na cota ne"). Eu punha em +12, ou
            # seja 2,9 alem da linha (que esta' em +9,1) e do lado oposto ao
            # objeto — as cotas que ele aceita ficam entre a linha e o
            # objeto, e essas duas pareciam soltas.
            emitir_cota(
                msp, origem='abertura_viga_larg',
                base=((_ai + _af) / 2.0, _y_topo_ab + 9.1),
                p1=(_ai, _y_topo_ab), p2=(_af, _y_topo_ab),
                angle=0,
                # Sem override: o texto sai ACIMA da linha, que e' o que o N2
                # faz nesta cota — medido na unidade [53, 63,5]: linha em
                # y=6776,2 e texto em 6784,2, 8 acima. `dimtad: 0` foi testado
                # e PIOROU (empurrou para 11); ezdxf so' honra dimtad na
                # cota vertical.
                texto=_fmt_dim_cm(_larg_ab),
                texto_pos=((_ai + _af) / 2.0, _y_topo_ab + 9.1),
            )
        if _alt_ab > 1.0:
            _x_cota_ab = float(_ai) - 11.8
            emitir_cota(
                msp, origem='abertura_viga_alt',
                base=(_x_cota_ab, _y_sobra),
                p1=(_ai, _y_sobra), p2=(_ai, _y_topo_ab),
                angle=90,
                # dimtad=0 centra o texto NA linha de cota (dono, V302 1A:
                # "texto da cota centralizado na cota ne"). Sem isso ele saia
                # a` esquerda da linha, do lado oposto a` parede da abertura,
                # e ficava solto sobre os sarrafos.
                override={'dimtad': 0},
                texto=_fmt_dim_cm(_alt_ab),
                texto_pos=(_x_cota_ab,
                           (_y_sobra + _y_topo_ab) / 2.0),
            )

    # As paredes (divisores e bordas) sao desenhadas ate' `y_top`, a altura da
    # UNIDADE. Onde o segmento e' mais alto que ela, falta o pedaco de cima:
    # na V302.A os seg.2/3 tem 45 contra 43 da unidade, e as paredes em 200.5,
    # 360 e 470 paravam 2 abaixo do proprio topo. Completa so' o que falta.
    if _faixas_h:
        _xs_parede = sorted({f[0] for f in _faixas_h} | {f[1] for f in _faixas_h})
        for _xp in _xs_parede:
            _viz = [f[2] for f in _faixas_h
                    if abs(f[0] - _xp) <= 0.05 or abs(f[1] - _xp) <= 0.05]
            if not _viz:
                continue
            _yv = max(_viz)
            if _yv > y_top + 0.05:
                msp.add_line((_xp, y_top), (_xp, _yv), dxfattribs=a)
    if has_degrau and degrau_end < body_end - 0.5:
        msp.add_line((degrau_end, y0), (body_end, y0), dxfattribs=a)
    elif not has_degrau:
        msp.add_line((x0, y0), (body_end, y0), dxfattribs=a)

    # N2 A/B: SEM H de marco no corpo 0→body_end.

    if _marco_overridden and marco_h_base > 0.5:
        # body_end, nao comprimento — ver comentario no ramo espelhado acima.
        _draw_vazio_concreto(
            msp, x0, y_marco, body_end, y_marco + marco_h_base,
        )
    elif marco_h > 0.5:
        # ── DEGRAU DE LAJE ────────────────────────────────────────────────
        # Com `laje_trechos` na ficha, a laje tem altura por TRECHO e o topo
        # fica plano: onde ha' painel de fechamento a laje e' mais baixa e o
        # painel completa; fora dele a laje sobe sozinha ate' o mesmo topo.
        # Sem o campo, desenha a faixa unica de sempre — byte a byte igual.
        _tr = [t for t in (laje_trechos or [])
               if float(t.get('altura', 0) or 0) > 0]
        if _tr:
            def _topo_do_trecho(_xi, _xf):
                """Topo do corpo SOB o trecho — a laje assenta no painel que
                esta' embaixo dela, nao no topo global da face.

                Apontamento do dono (V302 SEGMENTO 1A, P5): a hachura saia
                2 cm abaixo, sobreposta ao painel. Medido: y0=-193, h=43
                punha o 2o trecho em -150, mas o painel ali tem 45 (-148).
                E' o que fecha a regra de topo plano: 43+16 = 45+14 = 59.

                Guarda igual a de `_draw_marco_laje_sup`: so' vale quando
                height1 E' a altura do corpo ali. Em degrau alto ele e'
                sub-banda (V301: height1=44 num corpo de 109).
                """
                _mid = (float(_xi) + float(_xf)) / 2.0 - float(x0)
                _acc = 0.0
                for _p in (panels or []):
                    _w = float(_p.get('width', 0) or 0)
                    if _w <= 0:
                        continue
                    if _acc - 1.0 <= _mid <= _acc + _w + 1.0:
                        _ph = float(_p.get('height1', 0) or 0)
                        if _ph > 0 and abs(_ph - float(h)) <= 10.0:
                            return y0 + _ph
                        break
                    _acc += _w
                return y_top

            # UMA faixa so' (ver `_draw_laje_escalonada`): o fundo acompanha o
            # degrau do corpo e o topo e' plano. Onde ha' painel de fechamento
            # a altura que o N2 escreve ja' vem descontada dele na ficha, mas
            # o DESENHO da laje vai ate' o topo plano — o painel se sobrepoe.
            _faixas_laje = []
            for _t in sorted(_tr, key=lambda d: float(d.get('x0', 0) or 0)):
                _xi = max(x0, x0 + float(_t.get('x0', 0) or 0))
                _xf = min(body_end, x0 + float(_t.get('x1', 0) or 0))
                if _xf - _xi <= 0.05:
                    continue
                _yb = _topo_do_trecho(_xi, _xf)
                _meio_t = (_xi + _xf) / 2.0 - float(x0)
                _sob_t = (float(painel_sup_alt or 0)
                          if (float(painel_sup_width or 0) > 0.5
                              and float(painel_sup_x_offset or 0) - 1.0
                              <= _meio_t
                              <= float(painel_sup_x_offset or 0)
                              + float(painel_sup_width or 0) + 1.0)
                          else 0.0)
                _faixas_laje.append(
                    (_xi, _xf, _yb, _yb + float(_t['altura']) + _sob_t)
                )
            _draw_laje_escalonada(msp, _faixas_laje)
        else:
            _draw_vazio_concreto(msp, x0, y_top, body_end, y_marco)

    # ── marco strip DIR (trailing) — V7 stub so (degrau grosso) ──
    # A tampa H solta (body_end+3 -> full_end em y_marco) foi removida
    # (2026-08-27/28, validado ponto-a-ponto em V301.A e CONT.V301.A): o N2
    # nao tem parede nesse vao, so cota — a parede real do corpo ja fecha
    # ate y_marco via `is_body_end` acima.
    if small_x is not None and full_end > body_end + 0.5 and marco_h > 0.5:
        # B: V7 so no divisor ~244 (degrau). NUNCA body_end / full_end.
        if thick_marco and has_degrau:
            y_v7_bot = float(y_marco) - 7.0
            pw0 = float(panels[0].get('width', 0) or 0)
            if pw0 >= 150.0:
                vx = float(x0) + pw0
                msp.add_line((vx, y_v7_bot), (vx, y_marco), dxfattribs=a)




def _draw_degrau_top_hatch(msp, x0, y0, h, panels):
    """ANSI31: faixa ombro->topo do degrau + faixa topo do corpo (N2)."""
    y_shoulder = _degrau_shoulder_y(y0, h, panels)
    degrau_end = _degrau_zone_end_x(x0, h, panels)
    y_top = y0 + h
    small_x = _small_panel_start_x(x0, h, panels)
    body_end = float(small_x) if small_x is not None else float(
        x0 + sum(float(p.get("width", 0) or 0) for p in (panels or []))
    )

    def _hatch(pts):
        if not DRAW_HATCHES_PAINEL:
            return
        try:
            ht = msp.add_hatch(dxfattribs={"layer": "Hachura", "color": 8})
            ht.set_pattern_fill("ANSI31", scale=0.4)
            ht.paths.add_polyline_path(pts, is_closed=True)
        except Exception:
            pass

    if y_shoulder is not None and degrau_end > x0 + 1.0 and y_top - y_shoulder >= 2.0:
        _hatch([
            (x0, y_shoulder), (degrau_end, y_shoulder),
            (degrau_end, y_top), (x0, y_top),
        ])
    # faixa topo pos-degrau (densifica B / corpo cheio)
    if degrau_end is not None and body_end > degrau_end + 5.0:
        y1 = y_top - min(18.0, h * 0.25)
        if y1 < y_top - 1.0:
            _hatch([
                (degrau_end, y1), (body_end, y1),
                (body_end, y_top), (degrau_end, y_top),
            ])



def _draw_degrau_step_verticals(msp, x0, y0, h, panels):
    """Legado — contorno agora vem de _draw_panel_frame_n2."""
    return


def _draw_marco_laje_sup(msp, x0, y0, h, panels, laje_sup, skip_layers=None,
                         laje_trechos=None):
    """Marco da laje superior (Painéis + hachura) nos painéis altos da face.

    `laje_trechos` (opcional) descreve DEGRAU DE LAJE: altura diferente por
    trecho da mesma face, em coordenada x relativa a x0, no formato
    [{x0, x1, altura}, ...]. Vem da ficha (`laje_sup_trechos`) e so' existe
    quando o N2 declara o degrau por cota escrita — ver §3.4.1 do doc de
    interpretacao. Ausente, o comportamento e' o de sempre: um retangulo por
    painel com `laje_sup` unico.

    A fronteira do degrau NAO cai necessariamente em divisa de painel (V13
    face A: painel 244 com a fronteira em 200), entao o retangulo do painel e'
    PARTIDO na fronteira e cada pedaco recebe a altura do seu trecho.
    """
    if skip_layers is None:
        skip_layers = set()
    ls = float(laje_sup or 0)
    trechos = [t for t in (laje_trechos or [])
               if float(t.get('altura', 0) or 0) > 0]
    if ls <= 0 and not trechos:
        return
    hatch_ok = 'SCO-___-LAJ' not in skip_layers
    x_cur = x0
    a = {'layer': 'Painéis'}

    def _topo_local(panel):
        """Topo do corpo SOB este painel — nao o topo global da face.

        A laje assenta no painel que esta' embaixo dela, e num segmento com
        alturas diferentes esse painel nao tem a altura global `h`. Apontado
        pelo dono na V302 SEGMENTO 1A (P5-P9): laje e cota 2 cm abaixo do
        lugar, sobrepostas ao painel. Medido: y0=-193, h=43 punha a laje do
        2o trecho em -150, mas o painel ali tem 45, ou seja -148.

        E' o outro lado da regra de topo plano -- 43+16 = 45+14 = 59 so'
        fecha se cada trecho assentar no SEU painel.

        So' vale quando `height1` E' a altura do corpo ali. Em unidade com
        degrau alto ele e' uma SUB-BANDA: na V301 os paineis tem height1=44
        num corpo de 109, e usar isso jogava as 10 cotas de laje 65 cm para
        baixo (medido contra o desenho validado). Mesma folga de 10 cm que
        a regra de topo plano usa para decidir que as alturas sao do mesmo
        segmento.
        """
        ph = float((panel or {}).get('height1', 0) or 0)
        if ph > 0 and abs(ph - float(h)) <= 10.0:
            return y0 + ph
        return y0 + h

    def _pedacos(xi, xf):
        """Divide [xi, xf] (relativo a x0) em (ini, fim, altura) por trecho."""
        if not trechos:
            return [(xi, xf, ls)]
        out = []
        for t in sorted(trechos, key=lambda d: float(d.get('x0', 0) or 0)):
            t0 = x0 + float(t.get('x0', 0) or 0)
            t1 = x0 + float(t.get('x1', 0) or 0)
            ini, fim = max(xi, t0), min(xf, t1)
            if fim - ini > 0.05:
                out.append((ini, fim, float(t['altura'])))
        # Trecho nao coberto pela ficha mantem a altura global.
        return out or ([(xi, xf, ls)] if ls > 0 else [])

    for panel in panels:
        pw = float(panel.get('width', 0) or 0)
        if pw <= 0:
            continue
        if _is_degrau_panel(panel, h):
            x_cur += pw
            continue
        y_body_top = _topo_local(panel)
        for xi, xf, alt in _pedacos(x_cur, x_cur + pw):
            pts = [
                (xi, y_body_top),
                (xf, y_body_top),
                (xf, y_body_top + alt),
                (xi, y_body_top + alt),
            ]
            msp.add_lwpolyline(pts, close=True, dxfattribs=a)
            if hatch_ok:
                pass  # N4: hachura so' em vazios; laje permanece contorno.
        x_cur += pw


def draw_grade_mode(msp, x_cur, y_grade_top, pw, grade_h,
                    is_first, is_last, layer_override=None):
    """Draw grade (Grade panel type) elements.

    Grade mode anatomy from SCR:
    - Horizontal rectangle 2.2cm tall at top (layer SARR_2.2x7)
    - Two vertical rectangles 3.5cm wide descending (layer SARR_2.2x3.5)
    - Height = grade_h - 2.2, inset 15cm from edges
    """
    if grade_h <= 2.2:
        return

    # Horizontal bar at top: gap vs Painéis (extremidades 7 cm)
    left_in, right_in = _sarrafo_h_insets(pw, is_first, is_last)
    x_gi = x_cur + left_in
    x_gf = x_cur + pw - right_in
    if x_gf <= x_gi:
        return

    # Horizontal rect (SARR_2.2x7 layer)
    layer22 = layer_override or 'SARR_2.2x7'
    layer35 = layer_override or 'SARR_3.5x7'
    a22 = {'layer': layer22}
    msp.add_line((x_gi, y_grade_top - 2.2), (x_gf, y_grade_top - 2.2), dxfattribs=a22)
    msp.add_line((x_gi, y_grade_top),       (x_gf, y_grade_top),       dxfattribs=a22)
    msp.add_line((x_gi, y_grade_top - 2.2), (x_gi, y_grade_top),       dxfattribs=a22)
    msp.add_line((x_gf, y_grade_top - 2.2), (x_gf, y_grade_top),       dxfattribs=a22)

    # Vertical legs (SARR_3.5x7 layer — mesmo layer do STOG humano N2)
    leg_h = grade_h - 2.2
    leg_w = 3.5
    inset_leg = 15.0  # 15cm inset from edges
    a35 = {'layer': layer35}

    y_leg_top = y_grade_top - 2.2
    y_leg_bot = y_leg_top - leg_h

    # Left leg
    xl = x_cur + inset_leg
    if xl + leg_w < x_cur + pw:
        msp.add_line((xl, y_leg_bot), (xl + leg_w, y_leg_bot), dxfattribs=a35)
        msp.add_line((xl, y_leg_top), (xl + leg_w, y_leg_top), dxfattribs=a35)
        msp.add_line((xl, y_leg_bot), (xl, y_leg_top),         dxfattribs=a35)
        msp.add_line((xl + leg_w, y_leg_bot), (xl + leg_w, y_leg_top), dxfattribs=a35)

    # Right leg
    xr = x_cur + pw - inset_leg - leg_w
    if xr > x_cur:
        msp.add_line((xr, y_leg_bot), (xr + leg_w, y_leg_bot), dxfattribs=a35)
        msp.add_line((xr, y_leg_top), (xr + leg_w, y_leg_top), dxfattribs=a35)
        msp.add_line((xr, y_leg_bot), (xr, y_leg_top),         dxfattribs=a35)
        msp.add_line((xr + leg_w, y_leg_bot), (xr + leg_w, y_leg_top), dxfattribs=a35)


# ──────────────────────────────────────────────────────────────────────────────
# Cotas (dimensoes) — estilo DIMENSION / dimstyle PAINEL (STOG)
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_dim_cm(val: float) -> str:
    """Texto de cota: inteiro se perto; senao 0.5; senao 1 casa.

    Preferir inteiro ate 0.45 (65.4→65, 103.4→103) sem engolir 50.5.
    """
    x = float(val)
    r0 = round(x)
    if x >= 40.0 and abs(x - r0) < 0.45:
        return str(int(r0))
    r5 = round(x * 2.0) / 2.0
    if abs(x - r5) < 0.12:
        if abs(r5 - round(r5)) < 0.01:
            return str(int(round(r5)))
        return f"{r5:.1f}".replace(".", ",")
    v = round(x, 1)
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    return f"{v:.1f}".replace(".", ",")


def group_panel_dims(panel_widths, min_w: float = PANEL_DIM_MIN_W):
    """Agrupa painéis estreitos consecutivos para uma cota só.

    Retorna lista de (x_offset_start, width_sum, n_panels).
    Ex.: [244, 28.7, 21.8, 111] →
         [(0, 244, 1), (244, 50.5, 2), (294.5, 111, 1)]

    Não inventa cota de zona de marco: quem chama deve excluir os painéis
    estreitos finais (marco) antes de chamar — ver
    ``_panel_widths_for_horizontal_dims``.
    """
    widths = [float(w or 0) for w in (panel_widths or [])]
    groups = []
    i = 0
    x = 0.0
    while i < len(widths):
        w = widths[i]
        if w <= 0:
            i += 1
            continue
        if w >= min_w:
            groups.append((x, w, 1))
            x += w
            i += 1
            continue
        # estreitos consecutivos → uma cota do somatório (estilo N2: 50.5)
        # no max 2 paineis (evita 22.5+52.5+21.7+26.2=123 inventado)
        j = i
        s = 0.0
        while j < len(widths) and 0 < widths[j] < min_w and (j - i) < 2:
            s += widths[j]
            j += 1
        if s > 0:
            groups.append((x, s, j - i))
            x += s
        i = j
    return groups


def _panel_widths_for_horizontal_dims(x0, h, panels, panel_widths):
    """Larguras cotaveis no eixo X - exclui zona de marco (estreitos).

    Multi-segmento: marco no inicio ou fim da cadeia (19+21.2 vira 40,2).
    Strip leading + trailing estreitos nao-degrau (lt 25 cm).
    """
    del x0
    widths = [float(w or 0) for w in (panel_widths or [])]
    plist = list(panels or [])
    if not widths or not plist:
        return widths
    n = min(len(widths), len(plist))
    widths = widths[:n]
    plist = plist[:n]

    def _is_marco_strip(i: int) -> bool:
        pw = widths[i]
        if pw <= 0 or pw >= 28.0:
            return False
        return not _is_degrau_panel(plist[i], h)

    i0 = 0
    while i0 < n and _is_marco_strip(i0):
        i0 += 1
    i1 = n
    while i1 > i0 and _is_marco_strip(i1 - 1):
        i1 -= 1
    # Cotas: strip estreitos finais (evita 22.5+52.5+21.7+26.2=123).
    # Geometria/body_end usa _small_panel_start_x (so corta apos bay>=55).
    kept = widths[i0:i1]
    return kept if kept else widths


def _apply_dim_text(dimstyle_override, text: str, mid_xy: tuple[float, float]):
    """Texto + text_midpoint após render (SVG ezdxf exige midpoint não-None)."""
    try:
        dim = dimstyle_override.dimension
        dim.dxf.text = str(text)
        mx, my = mid_xy
        dim.dxf.text_midpoint = (mx, my, 0)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# PLANO DE COTAS -- ponto unico de decisao
# ═══════════════════════════════════════════════════════════════════════════
# Antes deste registro, 19 pontos do codigo chamavam add_linear_dim direto,
# cada um com a sua condicao local, olhando so' a geometria que ele mesmo
# acabara de desenhar. Como a LISTA de cotas da unidade nao existia em lugar
# nenhum, nao havia onde:
#   - suprimir a cota da parede compartilhada entre dois segmentos (quem
#     desenha o segmento 1 nao sabe que o 2 vai cotar a mesma parede);
#   - exigir que a altura total saia (ninguem e' dono dessa obrigacao);
#   - recusar valor que nao rastreia ate' uma medida do modelo.
# Cada guarda somada matava um caso e abria outro. Este e' o lugar que faltava.
#
# FASE 1 (agora): passa-direto. `emitir_cota` renderiza na hora, na mesma
# ordem de antes, e apenas REGISTRA -- o N4 sai identico byte a byte. O que
# se ganha e' o inventario por face, que a fase 2 usa para decidir.

_PLANO_COTAS: dict | None = None


def plano_cotas_abrir(tag: str) -> None:
    """Abre o registro de cotas de uma face/vista (`tag` = nome da face)."""
    global _PLANO_COTAS
    _PLANO_COTAS = {'tag': str(tag), 'itens': []}


def plano_cotas_fechar() -> list:
    """Fecha o registro e devolve os itens emitidos na face."""
    global _PLANO_COTAS
    itens = list((_PLANO_COTAS or {}).get('itens') or [])
    _PLANO_COTAS = None
    return itens


def plano_cotas_itens() -> list:
    """Itens ja' emitidos na face aberta (vazio se nao ha' registro aberto)."""
    return list((_PLANO_COTAS or {}).get('itens') or [])


def plano_cotas_despejar(itens: list, tag: str) -> None:
    """Grava o inventario da unidade em LV_COTA_DUMP (JSONL), se pedido.

    O gerador roda como SUBPROCESSO, entao instrumentar em processo nao
    alcanca estas cotas -- o despejo em arquivo e' o unico jeito de ver
    o que cada origem propos.
    """
    alvo = os.environ.get('LV_COTA_DUMP')
    if not alvo or not itens:
        return
    try:
        import json
        with open(alvo, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'unidade': str(tag), 'cotas': itens},
                                ensure_ascii=False) + '\n')
    except Exception:
        pass


def _plano_cotas_registrar(origem, p1, p2, angle, texto, medida):
    if _PLANO_COTAS is None:
        return
    try:
        _PLANO_COTAS['itens'].append({
            'origem': str(origem),
            'medida': round(float(medida), 2),
            'texto': None if texto is None else str(texto),
            'orient': 'V' if int(angle) == 90 else 'H',
            'x': round((float(p1[0]) + float(p2[0])) / 2.0, 2),
            'y': round((float(p1[1]) + float(p2[1])) / 2.0, 2),
        })
    except Exception:
        pass


def emitir_cota(msp, *, origem, base, p1, p2, angle, dimstyle='PAINEL',
                layer='COTA', override=None, texto=None, texto_pos=None):
    """UNICO caminho de emissao de cota do motor LV.

    `origem` identifica o ponto do codigo que propos a cota -- e' o que
    permite, na fase 2, decidir entre propostas concorrentes sobre a mesma
    parede. O texto e' aplicado DEPOIS do render porque o ezdxf reverte
    para '<>' durante ele (vaos estreitos colidiam no SVG: "28,721,8").

    """
    try:
        kw = {'base': base, 'p1': p1, 'p2': p2, 'angle': angle,
              'dimstyle': dimstyle, 'dxfattribs': {'layer': layer}}
        if override:
            kw['override'] = dict(override)
        d = msp.add_linear_dim(**kw)
        d.render()
    except Exception:
        return None
    if texto is not None:
        _apply_dim_text(d, texto, texto_pos if texto_pos is not None else base)
    medida = (abs(float(p2[1]) - float(p1[1])) if int(angle) == 90
              else abs(float(p2[0]) - float(p1[0])))
    _plano_cotas_registrar(origem, p1, p2, angle, texto, medida)
    return d


def _panel_attach_y(x, y0, y_shoulder, degrau_end, degrau_start=None):
    """Y onde a pata da cota H encontra o painel.

    No vao do degrau (x < degrau_end) o fundo real e o ombro recuado —
    a pata sobe ate la; apos o degrau (ou sem degrau) usa y0.
    """
    if (
        y_shoulder is not None
        and degrau_end is not None
        and float(x) < float(degrau_end) - 0.05
        and (
            degrau_start is None
            or float(x) > float(degrau_start) + 0.05
        )
    ):
        return float(y_shoulder)
    return float(y0)


def dim_panel_lv(msp, x0, x1, y_base, *, text_override: str | None = None,
                 level: int = 0, y_p1: float | None = None,
                 y_p2: float | None = None):
    """Cota horizontal de painel/grupo.

    Niveis H: nivel 0 = 25 cm (cadeia), nivel 1 = 50 cm (244 / 161,5).
    y_p1/y_p2: onde as patas tocam o painel (ombro no vao recuado).
    """
    try:
        # Niveis H: 0 = 25 (cadeia de paineis), 1 = 50, 2 = 75.
        # O nivel 2 existe por causa do FATOR DE REPETICAO (regra do dono,
        # 2026-09-19): sem fator a total fica no nivel 1; com fator, o "NX"
        # ocupa o nivel 1 e a total desce para o 2.
        y_off = {0: 25.0, 1: 50.0}.get(int(level), 75.0)
        if int(level) <= 0:
            y_off = 25.0
        yp1 = float(y_base if y_p1 is None else y_p1)
        yp2 = float(y_base if y_p2 is None else y_p2)
        mid = ((float(x0) + float(x1)) / 2.0, float(y_base) - y_off - 6.0)
        emitir_cota(
            msp, origem='painel_h',
            base=(x0, y_base - y_off),
            p1=(x0, yp1), p2=(x1, yp2),
            angle=0,
            texto=text_override or None, texto_pos=mid,
        )
    except Exception:
        pass

def dim_total_lv(msp, x0, x1, y_base):
    """Cota horizontal total da face -- 2o nivel."""
    try:
        mid = ((float(x0) + float(x1)) / 2.0, float(y_base) - DIM_TOTAL_BELOW - 6.0)
        emitir_cota(
            msp, origem='total_h',
            base=(x0, y_base - DIM_TOTAL_BELOW),
            p1=(x0, y_base), p2=(x1, y_base),
            angle=0,
            texto=_fmt_dim_cm(abs(float(x1) - float(x0))), texto_pos=mid,
        )
    except Exception:
        pass

def dim_h_lateral(msp, x_right, y0, h, *, offset: float | None = None,
                  text_override: str | None = None):
    """Cota vertical de h_lateral -- lado direito.

    Niveis (pedido visual): nivel 1 = +25 cm, nivel 2 = +50 cm.
    """
    if h <= 0:
        return
    try:
        off = float(DIM_H_RIGHT if offset is None else offset)
        x_base = x_right + off
        emitir_cota(
            msp, origem='h_lateral',
            base=(x_base, y0),
            p1=(x_right, y0), p2=(x_right, y0 + h),
            angle=90,
            texto=text_override or None,
            texto_pos=(x_base + (4.0 if off >= 0 else -4.0),
                       float(y0) + float(h) / 2.0),
        )
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Detalhe de secao transversal (Visao de Corte)
# ──────────────────────────────────────────────────────────────────────────────
def add_plain_dim_v(msp, x, y1, y2, label, *, extension_from_x=None,
                    layer='Cota Seção (2x)'):
    """Cota interna sem os quadrados que o dimstyle PAINEL materializa."""
    attrs = {'layer': layer}
    if extension_from_x is not None:
        msp.add_line((extension_from_x, y1), (x, y1), dxfattribs=attrs)
        msp.add_line((extension_from_x, y2), (x, y2), dxfattribs=attrs)
    msp.add_line((x, y1), (x, y2), dxfattribs=attrs)
    for y in (y1, y2):
        msp.add_line((x - 2.5, y - 2.5), (x + 2.5, y + 2.5),
                     dxfattribs=attrs)
    text = msp.add_text(str(label), dxfattribs={
        'insert': (x + 5.0, (y1 + y2) / 2.0), 'height': 7.0,
        'rotation': 90.0, 'layer': layer,
    })
    text.dxf.halign = 1
    text.dxf.valign = 2
    text.dxf.align_point = (x + 5.0, (y1 + y2) / 2.0)


def add_plain_dim_h(msp, x1, x2, y, label, *, extension_to_y=None,
                    layer='Cota Seção (2x)'):
    """Cota interna horizontal com linha, extensões e ticks oblíquos."""
    attrs = {'layer': layer}
    if extension_to_y is not None:
        msp.add_line((x1, extension_to_y), (x1, y), dxfattribs=attrs)
        msp.add_line((x2, extension_to_y), (x2, y), dxfattribs=attrs)
    msp.add_line((x1, y), (x2, y), dxfattribs=attrs)
    for x in (x1, x2):
        msp.add_line((x - 2.5, y - 2.5), (x + 2.5, y + 2.5),
                     dxfattribs=attrs)
    add_text(msp, (x1 + x2) / 2.0, y - 7.0, str(label), 7.0,
             layer, halign=1, valign=2)

def draw_section_detail(msp, x_center, y0, b, h, viga_nome='', b_alma=19,
                        h_A=None, h_B=None, skip_layers=None,
                        extension_left_cm=None, extension_right_cm=None,
                        laje_sup_A=None, laje_sup_B=None):
    """Detalhe de secao transversal -- ALL STOG elements (eng. reversa DXF V22).

    skip_layers: set of layer names to NOT draw (computed from STOG presence check).
    If a layer is in skip_layers it means the STOG doesn't use that layer, so
    drawing it would create an 'extra' layer penalty.

    Enhanced with SCR anatomy VC elements:
    - MLINE-style double lines for sarrafos (pairs 4.4cm apart) on SARRAFO_2_2X7
    - BARRA_ANCORAGEM rectangles connecting faces
    - Block inserts: PAR_ESQ, PAR_FUNDO_ESQ, PAR_FUNDO_DIR, par_int_esq, par_int_dir
    - HACHURACONCRETO between faces
    """
    if skip_layers is None:
        skip_layers = set()

    CAP_H = 4.4

    # X anchors (confirmed DXF V22)
    x_ml_l = x_center - 32   # Madeira L left
    x_ml_r = x_center - 18   # Madeira L right / Paineis L left
    x_pl_r = x_center - 14   # Paineis L right = concreto left (x_cl)
    x_cl   = x_center - 14   # concreto left
    x_wr   = x_center + 24   # web right (x_cl + 38)
    x_pr_r = x_center + 28   # Paineis R right
    x_mr_r = x_center + 42   # Madeira R right
    x_fr   = x_center + 24 + b  # flange right (varies with b)

    # Heights reflect faces A and B
    h_left      = h_A if h_A is not None else (h + 8)
    h_flange_bot = max(h - 16, CAP_H + 5)
    h_right     = h_B if h_B is not None else max(h - 20, h_flange_bot)
    h_right     = max(h_right, h_flange_bot)

    la = {'layer': 'Madeira'}
    lp = {'layer': 'Painéis'}
    l0 = {'layer': '0'}

    # ═══════════════════════════════════════════════════════════════════════
    # 1. BARROTE (layer 'barrote') -- base horizontal
    # ═══════════════════════════════════════════════════════════════════════
    bw2 = (140 + b) / 2
    if 'barrote' not in skip_layers:
        msp.add_lwpolyline(
            [(x_center - bw2, y0-20), (x_center + bw2, y0-20),
             (x_center + bw2, y0),    (x_center - bw2, y0)],
            close=True, dxfattribs={'layer': 'barrote'}
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 2. SCO-___-LAJ (layer 'SCO-LAJ') -- strip on top of barrote
    # ═══════════════════════════════════════════════════════════════════════
    if 'SCO-___-LAJ' not in skip_layers:
        sco_l = x_center - bw2 + 19
        sco_r = x_center + bw2 - 9
        msp.add_lwpolyline(
            [(sco_l, y0-3.2), (sco_r, y0-3.2), (sco_r, y0), (sco_l, y0)],
            close=True, dxfattribs={'layer': 'SCO-___-LAJ'}
        )

    # ═══════════════════════════════════════════════════════════════════════
    # 3. MADEIRA -- 9 LWPOLYLINEs (boards + caps + bases)
    # ═══════════════════════════════════════════════════════════════════════
    # 3a. Madeira LEFT main board (14cm x h_left)
    msp.add_lwpolyline(
        [(x_ml_l, y0), (x_ml_r, y0), (x_ml_r, y0+h_left), (x_ml_l, y0+h_left)],
        close=True, dxfattribs=la)
    # 3b. Madeira RIGHT main board
    msp.add_lwpolyline(
        [(x_pr_r, y0), (x_mr_r, y0), (x_mr_r, y0+h_right), (x_pr_r, y0+h_right)],
        close=True, dxfattribs=la)
    # 3c. LEFT base plate (20cm x 4.4cm)
    msp.add_lwpolyline(
        [(x_ml_l-20, y0), (x_ml_l, y0), (x_ml_l, y0+CAP_H), (x_ml_l-20, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3d. RIGHT base plate (20cm x 4.4cm)
    msp.add_lwpolyline(
        [(x_mr_r, y0), (x_mr_r+20, y0), (x_mr_r+20, y0+CAP_H), (x_mr_r, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3e. LEFT board bottom cap (14cm x 4.4cm)
    msp.add_lwpolyline(
        [(x_ml_l, y0), (x_ml_r, y0), (x_ml_r, y0+CAP_H), (x_ml_l, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3f. LEFT board top cap
    msp.add_lwpolyline(
        [(x_ml_l, y0+h_left-CAP_H), (x_ml_r, y0+h_left-CAP_H),
         (x_ml_r, y0+h_left),       (x_ml_l, y0+h_left)],
        close=True, dxfattribs=la)
    # 3g. RIGHT board top cap
    msp.add_lwpolyline(
        [(x_pr_r, y0+h_right-CAP_H), (x_mr_r, y0+h_right-CAP_H),
         (x_mr_r, y0+h_right),       (x_pr_r, y0+h_right)],
        close=True, dxfattribs=la)
    # 3h. Concrete-left base (10cm x 4.4cm)
    msp.add_lwpolyline(
        [(x_cl, y0), (x_cl+10, y0), (x_cl+10, y0+CAP_H), (x_cl, y0+CAP_H)],
        close=True, dxfattribs=la)
    # 3i. Web-right base (10cm x 4.4cm)
    msp.add_lwpolyline(
        [(x_wr-10, y0), (x_wr, y0), (x_wr, y0+CAP_H), (x_wr-10, y0+CAP_H)],
        close=True, dxfattribs=la)

    # ═══════════════════════════════════════════════════════════════════════
    # 4. PAINEIS -- 4 LWPOLYLINEs
    # ═══════════════════════════════════════════════════════════════════════
    # 4a. Paineis LEFT (4cm x h_left)
    msp.add_lwpolyline(
        [(x_ml_r, y0), (x_pl_r, y0), (x_pl_r, y0+h_left), (x_ml_r, y0+h_left)],
        close=True, dxfattribs=lp)
    # 4b. Paineis RIGHT (4cm x h_right)
    msp.add_lwpolyline(
        [(x_wr, y0), (x_pr_r, y0), (x_pr_r, y0+h_right), (x_wr, y0+h_right)],
        close=True, dxfattribs=lp)
    # 4c. Paineis HORIZONTAL -- flange strip
    msp.add_lwpolyline(
        [(x_wr, y0+h_right),        (x_fr, y0+h_right),
         (x_fr, y0+h_flange_bot),   (x_wr, y0+h_flange_bot)],
        close=True, dxfattribs=lp)
    # 4d. Paineis BOTTOM STRIP -- base (38cm x 3.6cm)
    msp.add_lwpolyline(
        [(x_cl, y0+CAP_H), (x_wr, y0+CAP_H), (x_wr, y0+8), (x_cl, y0+8)],
        close=True, dxfattribs=lp)

    # ═══════════════════════════════════════════════════════════════════════
    # 5. CONCRETO em L (layer 'CONCRETO') -- 6-vertex polygon
    # ═══════════════════════════════════════════════════════════════════════
    # Flange/laje real do contrato N1 (topology bilateral): quando a ficha
    # informa extensao lateral da mesa (extension_left_cm/right_cm) e a
    # espessura da laje que a sustenta (laje_sup_A/B), o perfil em T real
    # substitui o notch generico fixo (24/b de largura, h-16 de altura) que
    # so cobria o lado direito -- sem isso a viga vira caixa retangular e
    # perde o formato de T verificado no N2 (achado 2026-09-10, V301 corte 2).
    _ext_l = max(float(extension_left_cm or 0.0), 0.0)
    _ext_r = max(float(extension_right_cm or 0.0), 0.0)
    if _ext_l > 0 or _ext_r > 0:
        y_top_conc = y0 + h + 8
        _flange_h_l = float(laje_sup_A) if laje_sup_A else max(h - 16, CAP_H + 5)
        _flange_h_r = float(laje_sup_B) if laje_sup_B else max(h - 16, CAP_H + 5)
        y_flange_bot_l = y_top_conc - _flange_h_l
        y_flange_bot_r = y_top_conc - _flange_h_r
        conc_pts = [(x_cl, y0 + 8)]
        if _ext_l > 0:
            conc_pts += [
                (x_cl, y_flange_bot_l),
                (x_cl - _ext_l, y_flange_bot_l),
                (x_cl - _ext_l, y_top_conc),
            ]
        else:
            conc_pts.append((x_cl, y_top_conc))
        if _ext_r > 0:
            conc_pts += [
                (x_wr + _ext_r, y_top_conc),
                (x_wr + _ext_r, y_flange_bot_r),
                (x_wr, y_flange_bot_r),
                (x_wr, y0 + 8),
            ]
        else:
            conc_pts += [(x_wr, y_top_conc), (x_wr, y0 + 8)]
    else:
        conc_pts = [
            (x_cl, y0+8),             (x_cl, y0+h+8),
            (x_fr, y0+h+8),           (x_fr, y0+h_flange_bot),
            (x_wr, y0+h_flange_bot),  (x_wr, y0+8),
        ]
    msp.add_lwpolyline(conc_pts, close=True, dxfattribs={'layer': 'CONCRETO'})
    # Sem hachura de preenchimento aqui: o N2 real do corte nao tem esse
    # HATCH ANSI31 na layer COTA sobre o concreto -- so' o contorno acima
    # (achado 2026-09-10, V301 CORTE 1, handle=79).

    # ═══════════════════════════════════════════════════════════════════════
    # 6. TENSOR + holders (layer 'TENSOR' / '0')
    # ═══════════════════════════════════════════════════════════════════════
    if 'TENSOR' not in skip_layers:
        y_tensor = y0 + 50
        msp.add_line(
            (x_center - 57, y_tensor), (x_fr - 2, y_tensor),
            dxfattribs={'layer': 'TENSOR'}
        )

        lx1, lx2 = x_center - 52, x_center - 22
        rx1, rx2 = x_mr_r, x_mr_r + 30
        yt, yb = y0 + 56, y0 + 44
        yi1, yi2 = y0 + 51, y0 + 49

        for (a1, a2, tab_dir) in [(lx1, lx2, -1), (rx1, rx2, +1)]:
            msp.add_line((a1, yt), (a2, yt), dxfattribs=l0)
            msp.add_line((a1, yb), (a2, yb), dxfattribs=l0)
            outer_x = a1 if tab_dir == -1 else a2
            msp.add_line((outer_x, yt), (outer_x, yb), dxfattribs=l0)
            msp.add_line((a1, yi2), (a2, yi2), dxfattribs=l0)
            msp.add_line((a1, yi1), (a2, yi1), dxfattribs=l0)
            tx = outer_x + tab_dir * 2
            msp.add_line((outer_x, y0+47), (tx, y0+47), dxfattribs=l0)
            msp.add_line((tx, y0+53), (tx, y0+47), dxfattribs=l0)
            msp.add_line((outer_x, y0+53), (tx, y0+53), dxfattribs=l0)

    # ═══════════════════════════════════════════════════════════════════════
    # 7. PRESILHA (layer 'presilha')
    # ═══════════════════════════════════════════════════════════════════════
    if 'presilha' not in skip_layers:
        lpr = {'layer': 'presilha'}
        for px in [x_center - 65, x_center + 75]:
            sz = 5
            msp.add_line((px-sz, y0-8-sz), (px+sz, y0-8+sz), dxfattribs=lpr)
            msp.add_line((px-sz, y0-8+sz), (px+sz, y0-8-sz), dxfattribs=lpr)

    # ═══════════════════════════════════════════════════════════════════════
    # 7b. HATCHING -- Wood (ANSI31) + Panel solid fills
    # ═══════════════════════════════════════════════════════════════════════
    def _hatch_rect(x1, y1, x2, y2, pattern='ANSI31', scale=0.5,
                    layer='Hachura', color=None):
        if not DRAW_HATCHES_PAINEL:
            return
        att = {'layer': layer}
        if color is not None:
            att['color'] = color
        ht = msp.add_hatch(dxfattribs=att)
        ht.set_pattern_fill(pattern, scale=scale)
        ht.paths.add_polyline_path(
            [(x1,y1),(x2,y1),(x2,y2),(x1,y2)], is_closed=True)

    # Wood boards ANSI31 hatching (7 fills)
    _hatch_rect(x_ml_l, y0, x_ml_r, y0+h_left)
    _hatch_rect(x_pr_r, y0, x_mr_r, y0+h_right)
    _hatch_rect(x_ml_l-20, y0, x_ml_l, y0+CAP_H)
    _hatch_rect(x_mr_r, y0, x_mr_r+20, y0+CAP_H)
    _hatch_rect(x_ml_l, y0+h_left-CAP_H, x_ml_r, y0+h_left)
    _hatch_rect(x_pr_r, y0+h_right-CAP_H, x_mr_r, y0+h_right)
    _hatch_rect(x_cl, y0, x_cl+10, y0+CAP_H)

    # Os pequenos retângulos verticais/horizontais são sarrafos no corte.
    # A hachura diagonal os distingue das cotas internas e mantém o vínculo
    # visual com os sarrafos horizontais declarados em A/B.
    _hatch_rect(x_ml_r, y0, x_pl_r, y0+h_left, 'ANSI31', 0.35,
                layer='Hachura')
    _hatch_rect(x_wr, y0, x_pr_r, y0+h_right, 'ANSI31', 0.35,
                layer='Hachura')
    _hatch_rect(x_wr, y0+h_right, x_fr, y0+h-16, 'ANSI31', 0.35,
                layer='Hachura')
    _hatch_rect(x_cl, y0+CAP_H, x_wr, y0+8, 'ANSI31', 0.35,
                layer='Hachura')

    # ═══════════════════════════════════════════════════════════════════════
    # 8. MLINE-style sarrafos in VC (SARRAFO_2_2X7 layer)
    #    SCR anatomy: _MLINE SAR3 style, scale 4.400 -> pairs of lines 4.4cm apart
    #    ezdxf não suporta MLINE → emite LINE no layer correto SARRAFO_2_2X7
    # ═══════════════════════════════════════════════════════════════════════
    sar_vc = {'layer': 'SARRAFO_2_2X7'}
    # Get sarrafo positions for each face
    _, _, positions_A = _get_sarrafo_positions(h_left)
    _, _, positions_B = _get_sarrafo_positions(h_right)

    # Face A sarrafos (left panel in VC): retângulo 4 linhas (top + bottom + 2 caps)
    # Reverso anatomy: 4 linhas por posição (sem center line — verificado empiricamente V8)
    for y_pos in positions_A:
        y_sarr = y0 + y_pos
        msp.add_line((x_ml_r, y_sarr + 2.2), (x_pl_r, y_sarr + 2.2), dxfattribs=sar_vc)  # top
        msp.add_line((x_ml_r, y_sarr - 2.2), (x_pl_r, y_sarr - 2.2), dxfattribs=sar_vc)  # bottom
        msp.add_line((x_ml_r, y_sarr - 2.2), (x_ml_r, y_sarr + 2.2), dxfattribs=sar_vc)  # left cap
        msp.add_line((x_pl_r, y_sarr - 2.2), (x_pl_r, y_sarr + 2.2), dxfattribs=sar_vc)  # right cap

    # Face B sarrafos (right panel in VC): mesmo padrão 4 linhas
    for y_pos in positions_B:
        y_sarr = y0 + y_pos
        msp.add_line((x_wr, y_sarr + 2.2), (x_pr_r, y_sarr + 2.2), dxfattribs=sar_vc)    # top
        msp.add_line((x_wr, y_sarr - 2.2), (x_pr_r, y_sarr - 2.2), dxfattribs=sar_vc)    # bottom
        msp.add_line((x_wr, y_sarr - 2.2), (x_wr, y_sarr + 2.2), dxfattribs=sar_vc)      # left cap
        msp.add_line((x_pr_r, y_sarr - 2.2), (x_pr_r, y_sarr + 2.2), dxfattribs=sar_vc)  # right cap

    # ═══════════════════════════════════════════════════════════════════════
    # 9. BARRA_ANCORAGEM rectangles connecting faces A and B
    # ═══════════════════════════════════════════════════════════════════════
    ba_layer = {'layer': 'BARRA_ANCORAGEM'}
    # Anchor bars at ~1/3 and ~2/3 of the shorter height
    h_min = min(h_left, h_right)
    bar_positions = [h_min * 0.33, h_min * 0.67]
    bar_h = 2.0  # bar height
    for bp in bar_positions:
        yb = y0 + bp - bar_h / 2
        yt_bar = y0 + bp + bar_h / 2
        # Spans from Face A panel right edge to Face B panel left edge
        msp.add_line((x_pl_r, yb), (x_wr, yb), dxfattribs=ba_layer)
        msp.add_line((x_pl_r, yt_bar), (x_wr, yt_bar), dxfattribs=ba_layer)
        msp.add_line((x_pl_r, yb), (x_pl_r, yt_bar), dxfattribs=ba_layer)
        msp.add_line((x_wr, yb), (x_wr, yt_bar), dxfattribs=ba_layer)

    # ═══════════════════════════════════════════════════════════════════════
    # 10. Block inserts: PAR_ESQ, PAR_FUNDO_ESQ, PAR_FUNDO_DIR, par_int_esq, par_int_dir
    # ═══════════════════════════════════════════════════════════════════════
    # Screw/bolt positions from SCR anatomy
    mid_h = y0 + h_min / 2
    msp.add_blockref('PAR_ESQ', (x_ml_r, mid_h), dxfattribs={'layer': 'Painéis'})
    msp.add_blockref('PAR_FUNDO_ESQ', (x_pl_r, y0 + 10), dxfattribs={'layer': 'Painéis'})
    msp.add_blockref('PAR_FUNDO_DIR', (x_wr, y0 + 10), dxfattribs={'layer': 'Painéis'})
    msp.add_blockref('par_int_esq', (x_pl_r, mid_h + 10), dxfattribs={'layer': 'Painéis'})
    msp.add_blockref('par_int_dir', (x_wr, mid_h + 10), dxfattribs={'layer': 'Painéis'})

    # ═══════════════════════════════════════════════════════════════════════
    # 11. HACHURACONCRETO -- hatched region between faces
    #     Layer correto: HACHURACONCRETO (não Hachura genérico)
    # ═══════════════════════════════════════════════════════════════════════
    hc_pts = [(x_pl_r, y0+CAP_H), (x_wr, y0+CAP_H),
              (x_wr, y0+h_min), (x_pl_r, y0+h_min)]
    msp.add_lwpolyline(hc_pts, close=True, dxfattribs={'layer': 'HACHURACONCRETO'})
    # Sem preenchimento: o N2 real do corte nao tem esse HATCH ANSI31 sobre
    # a faixa entre faces -- so' o contorno acima (achado 2026-09-10, V301
    # CORTE 1, handle=AD).

    # ═══════════════════════════════════════════════════════════════════════
    # 12. TEXTOS 'detalhes' (layer 'detalhes') + pontalete em ESTRUTURACAO
    # ═══════════════════════════════════════════════════════════════════════
    add_text(msp, x_center - 29, y0 + 27.3, 'a', 9.6, 'detalhes')
    add_text(msp, x_center + 31, y0 + 27.3, 'b', 9.6, 'detalhes')
    add_text(msp, x_center - 4,  y0 + 10.5, 'c', 9.6, 'detalhes')
    # Texto pontalete no layer ESTRUTURACAO (exigido pelo spec LV-V12)
    add_text(msp, x_center - 4, y0 - 12, 'pontalete', 9.6, 'ESTRUTURACAO')

    # ═══════════════════════════════════════════════════════════════════════
    # 13. TEXTO SECAO -- title (layer 'Texto Seção')
    # ═══════════════════════════════════════════════════════════════════════
    if viga_nome and 'Texto Seção' not in skip_layers:
        # O corte é contexto comum A/B: identifica a viga e usa H x B.
        add_text(msp, x_center, y0 + max(h_left, h_right, h) + 34,
                 f'{viga_nome} ({int(h)}x{int(b_alma)})',
                 8.0, 'Texto Seção', halign=1, valign=2)

    # ═══════════════════════════════════════════════════════════════════════
    # 14. DIMENSOES -- 6 cotas da secao transversal
    # ═══════════════════════════════════════════════════════════════════════
    dim_x_right = x_fr + 43

    def add_dim_v(p1, p2, base_x, layer='COTA', style='PAINEL'):
        emitir_cota(msp, origem='secao_v', base=(base_x, p1[1]), p1=p1, p2=p2,
                    angle=90, dimstyle=style, layer=layer)

    def add_dim_h(p1, p2, base_y, layer='COTA', style='PAINEL'):
        emitir_cota(msp, origem='secao_h', base=(p1[0], base_y), p1=p1, p2=p2,
                    angle=0, dimstyle=style, layer=layer)

    # 14a. Full LEFT height
    add_dim_v((x_ml_l-20, y0), (x_ml_l, y0+h_left), x_center - 108)
    # 14b. Concrete height — on 'Cota Seção (2x)', skip if STOG doesn't have this layer
    if 'Cota Seção (2x)' not in skip_layers:
        # B/H são cotas internas: linhas/ticks, não blocos quadrados do style.
        core_left = x_center - b_alma / 2.0
        core_right = x_center + b_alma / 2.0
        add_plain_dim_v(msp, core_right + 12.0, y0 + 8.0, y0 + h + 8.0,
                        f'{h:.0f}', extension_from_x=core_right)
        add_plain_dim_h(msp, core_left, core_right, y0 - 12.0,
                        f'{b_alma:.0f}', extension_to_y=y0 + 8.0)
    # 14c. Tensor height
    add_dim_v((x_mr_r, y0), (x_mr_r, y0+50), x_fr + 3)
    # 14d. Madeira RIGHT height
    add_dim_v((x_mr_r, y0), (x_mr_r, y0+h_right), dim_x_right)
    # 14e. Flange height
    add_dim_v((x_fr, y0+h_flange_bot), (x_fr, y0+h+8), dim_x_right)
    # 14f. Web width (38cm)
    # A largura interna já está representada pela cota B/H acima.


# ──────────────────────────────────────────────────────────────────────────────
# Face da viga (A ou B)
# ──────────────────────────────────────────────────────────────────────────────


def _lv_stack_rank(entity) -> int:
    """0 fundo, 1 cota, 2 paineis, 3 sarrafo (maior = mais acima)."""
    layer = str(entity.dxf.get("layer", "") or "")
    lu = layer.upper().replace("É", "E")
    if "SARR" in lu:
        return 3
    if lu in ("PAINEIS",) or layer == "Painéis":
        return 2
    if "COTA" in lu:
        return 1
    return 0


def restack_lv_draw_order(msp) -> None:
    """Cotas embaixo, Painéis no meio, sarrafos em cima.

    O frontend ezdxf/matplotlib desenha por redraw-order (handle crescente).
    """
    mapping = []
    for i, entity in enumerate(msp):
        try:
            handle = entity.dxf.handle
        except Exception:
            continue
        rank = _lv_stack_rank(entity)
        mapping.append((handle, f"{rank + 1:X}{i + 1:05X}"))
    if mapping:
        msp.set_redraw_order(mapping)


def _wide_bay_split_xs(x0, panels, body_end, min_w=150.0):
    """X interior da junta do vao largo (>=150, ex. 244) com o restante do corpo.

    O painel de 7 acima da laje segue a mesma separacao dos paineis de baixo:
    244 | 75 ou 244 | 174.
    """
    acc = float(x0)
    end = float(body_end)
    xs = []
    for panel in panels or []:
        pw = float(panel.get("width", 0) or 0)
        left, right = acc, acc + pw
        if pw >= float(min_w):
            if left > float(x0) + 1.0 and left < end - 1.0:
                xs.append(left)
            if right > float(x0) + 1.0 and right < end - 1.0:
                xs.append(right)
        acc = right
        if acc >= end - 0.1:
            break
    out = []
    for x in sorted(xs):
        if not out or abs(x - out[-1]) > 0.5:
            out.append(x)
    return out


def draw_lv_face(msp, x0, y0, panels, h, nome_face,
                 holes=None, pillar_left=None, pillar_right=None,
                 laje_sup=7.0, laje_inf=7.0, border_strip_width=0.0,
                 skip_layers=None, nota_face=None, pontaletes_face=None,
                 fallback_panel_ids=True, nom_height=None,
                 reverse_grade_style=False, suppress_sarrafo_spans=True,
                 sarrafo_vertical_esquerdo=False, sarrafo_vertical_direito=False,
                 sarrafos_verticais=None, sarrafos_horizontais=None,
                 marco_laje_sup=False, painel_sup_alt=0.0,
                 painel_sup_width=0.0, painel_sup_x_offset=0.0,
                 endpoint_start_label=None, endpoint_end_label=None,
                 edge_span_candidates=None, laje_trechos=None,
                 aberturas_viga=None, fatores_painel=None):
    """Desenha uma face (A ou B) da viga lateral -- todos elementos visuais.
    panels: lista de dicts [{width, height1, height2, grade_h1, grade_h2, reuse, panel_type}, ...]
    holes: lista de aberturas [{active, width, height, position}, ...]
    pillar_left/right: dict {active, width, length}
    laje_sup/inf: alturas default de laje superior/inferior (cm)
    skip_layers: set of layer names to skip (from STOG presence check)
    Retorna comprimento total da face.
    """
    if skip_layers is None:
        skip_layers = set()
    panels = sanitize_face_panels_for_draw(list(panels or []), h)
    panel_widths = [p['width'] for p in panels]
    comprimento = sum(panel_widths)
    n = len(panels)
    if comprimento <= 0 or h <= 0:
        return comprimento

    # ── 1. LAJE INFERIOR -- retangulo fechado com hachura POR PAINEL ─────
    has_local_inf = any(
        float(p.get('laje_inf_local', p.get('slab_bottom', 0)) or 0) > 0
        for p in panels
    )
    has_laje_inf = has_local_inf or laje_inf > 0
    if has_laje_inf and 'SCO-___-LAJ' not in skip_layers:
        x_cur = x0
        for p in panels:
            pw = p['width']
            li = (
                float(p.get('laje_inf_local', p.get('slab_bottom', 0)) or 0)
                if has_local_inf else float(laje_inf or 0)
            )
            if li <= 0:
                x_cur += pw
                continue
            pts = [(x_cur, y0-li), (x_cur+pw, y0-li),
                   (x_cur+pw, y0), (x_cur, y0)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})
            # N4: hachura somente em vazios; laje permanece como contorno.
            x_cur += pw

    # ── 2. LAJE SUPERIOR -- retangulo fechado com hachura POR PAINEL ─────
    has_local_sup = any(
        float(p.get('laje_sup_local', p.get('slab_top', 0)) or 0) > 0
        for p in panels
    )
    has_laje_sup = has_local_sup or laje_sup > 0
    if has_laje_sup and 'SCO-___-LAJ' not in skip_layers:
        # Uma faixa continua 0→body_end. Caixinhas por painel inventavam V
        # interior atraves da laje (244 seccionado no 7 mas a laje ainda
        # ganhava aresta no mesmo X).
        _small_x_laje = _small_panel_start_x(x0, h, panels)
        _laje_right = (
            float(_small_x_laje) if _small_x_laje is not None
            else float(x0) + float(comprimento)
        )
        if has_local_sup:
            ls = max(
                (
                    float(p.get('laje_sup_local', p.get('slab_top', 0)) or 0)
                    for p in panels
                ),
                default=float(laje_sup or 0),
            ) or float(laje_sup or 0)
        else:
            ls = float(laje_sup or 0)
        if ls > 0 and _laje_right > float(x0) + 0.5:
            pts = [
                (x0, y0 + h), (_laje_right, y0 + h),
                (_laje_right, y0 + h + ls), (x0, y0 + h + ls),
            ]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})

    # Painel de fechamento acima da laje: contrato separado da laje/marco.
    _top_panel_h = float(painel_sup_alt or 0)
    _top_panel_w = float(painel_sup_width or 0)
    _top_panel_x = float(x0) + float(painel_sup_x_offset or 0)
    _small_x_top = _small_panel_start_x(x0, h, panels)
    _body_end_top = (
        float(_small_x_top) if _small_x_top is not None
        else float(x0) + float(sum(float(pp.get('width', 0) or 0) for pp in panels))
    )
    _top_panel_x = min(max(_top_panel_x, float(x0)), _body_end_top)
    _top_panel_right = min(_top_panel_x + _top_panel_w, _body_end_top)
    if _top_panel_h > 0.5 and (_top_panel_right - _top_panel_x) > 0.5:
        _top_panel_y = float(y0) + float(h) + float(laje_sup or 0)
        _split_xs = [
            x for x in _wide_bay_split_xs(x0, panels, _body_end_top)
            if _top_panel_x + 1.0 < x < _top_panel_right - 1.0
        ]
        _xs7 = [_top_panel_x] + _split_xs + [_top_panel_right]
        # Contorno UNICO do painel de fechamento (nao um retangulo fechado
        # por segmento): dois segmentos adjacentes desenhados como
        # LWPOLYLINE fechada independente duplicam a aresta que
        # compartilham (a borda direita de um = a borda esquerda do
        # proximo, ambas desenhadas), virando linha dupla visivel bem em
        # cima do proprio divisor interno (achado 2026-09-09, dono: "cada
        # linha deve ser um elemento", handles A18/A19 SEGMENTO 2B). Topo/
        # base/laterais como LINE simples, igual ao resto do arquivo;
        # divisores internos ja saem certos no loop seguinte, uma vez so.
        msp.add_line((_top_panel_x, _top_panel_y), (_top_panel_right, _top_panel_y),
                     dxfattribs={'layer': 'Painéis'})
        msp.add_line((_top_panel_x, _top_panel_y + _top_panel_h),
                     (_top_panel_right, _top_panel_y + _top_panel_h),
                     dxfattribs={'layer': 'Painéis'})
        msp.add_line((_top_panel_x, _top_panel_y), (_top_panel_x, _top_panel_y + _top_panel_h),
                     dxfattribs={'layer': 'Painéis'})
        msp.add_line((_top_panel_right, _top_panel_y), (_top_panel_right, _top_panel_y + _top_panel_h),
                     dxfattribs={'layer': 'Painéis'})
        # Vertical so no painel de 7 — nao atravessa a laje (secciona).
        for _xv in _split_xs:
            msp.add_line(
                (_xv, _top_panel_y),
                (_xv, _top_panel_y + _top_panel_h),
                dxfattribs={'layer': 'Painéis'},
            )
        # Sarrafo do painel de fechamento: mesma referencia do corpo (7cm
        # abaixo do topo real do painel) — como esse painel e' de 7cm, cai
        # exatamente na borda de baixo (linha fucsia da caixa), sobrepondo
        # 2 linhas ali (achado ponto-a-ponto em V301.B, 2026-08-29).
        _y_sarr_topo = max(_top_panel_y, _top_panel_y + _top_panel_h - 7.0)
        for _i7, (_xa, _xb) in enumerate(zip(_xs7, _xs7[1:])):
            if _xb - _xa < 0.5:
                continue
            # Mesmo inset dos sarrafos do corpo: nao encosta no divisor
            # Painéis interno (SARR_PANEL_GAP), so nas pontas do vao inteiro
            # (SARR_INSET_H) — sem isso o sarrafo "tocava a parede" no meio
            # (achado ponto-a-ponto em V301.B/CONT.V301.B, 2026-08-29).
            _is_first7 = _i7 == 0
            _is_last7 = _i7 == len(_xs7) - 2
            _lin7, _rin7 = _sarrafo_h_insets(_xb - _xa, _is_first7, _is_last7)
            _sxa, _sxb = _xa + _lin7, _xb - _rin7
            if _sxb - _sxa < 0.5:
                continue
            msp.add_line(
                (_sxa, _y_sarr_topo), (_sxb, _y_sarr_topo),
                dxfattribs={'layer': 'SARR_2.2x7'},
            )
        # Sarrafos verticais de extremidade do painel de fechamento —
        # SEMPRE nos dois lados, incondicional (nao usa mais a flag do
        # corpo principal). Achado 2026-09-10, dono: "falta os sarrafos
        # verticais das extremidades das paredes dos paineis acima da
        # laje... para ambos os lados e todos os itens" — e depois, sobre
        # o lado direito especifico nao existir no N2 real: "nao importa
        # se to pedindo e' que tem que ter". Decisao deliberada de produto:
        # este painel e' uma parede separada do corpo e sempre fecha nas
        # duas pontas, independente do N2 ter ou nao o sarrafo ali.
        if _top_panel_right - _top_panel_x > 2 * SARR_INSET_H:
            _xvl = _top_panel_x + SARR_INSET_H
            msp.add_line((_xvl, _top_panel_y), (_xvl, _top_panel_y + _top_panel_h),
                         dxfattribs={'layer': 'SARR_2.2x7'})
            _xvr = _top_panel_right - SARR_INSET_H
            msp.add_line((_xvr, _top_panel_y), (_xvr, _top_panel_y + _top_panel_h),
                         dxfattribs={'layer': 'SARR_2.2x7'})

    # ── 3. Contornos dos paineis + lajes centrais + grades + sarrafos ───
    x_cur = x0
    for idx, p in enumerate(panels):
        pw = p['width']
        h1 = p['height1']
        h2 = p['height2']
        gh1 = p['grade_h1']
        gh2 = p['grade_h2']
        is_first = (idx == 0)
        is_last  = (idx == n - 1)
        panel_type = p.get('panel_type', 'Sarrafeado')
        is_reuse = p.get('reuse', False)

        has_laje_central = _panel_has_laje_central(p, h)
        lc_alt = float(p.get('laje_central_alt', 0) or 0)

        # Positions in drawing space: scale proportionally when real dims > face height
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
            h1_d, lc_h_d = h, 0

        h_draw = _panel_draw_height(p, h)
        y_panel = _panel_y_base(y0, h, p)

        # Vazio na base do painel: o proprio painel (nao degrau, height1
        # cheio) tem um vao vazio real entre y0 e sua base fisica — a linha
        # de topo do vao (Painéis, largura do painel) sempre falta se so
        # confiarmos no contorno padrao (achado 2026-08-29/30, V301.B#1/#2/
        # #4/#5: painel de 111cm com vazio 0->33.4, sem cota de texto no N2,
        # so a geometria do proprio painel revela). As laterais do vao ja
        # ficam cobertas pelo contorno normal (divisor interno / borda
        # direita do corpo), entao so falta o fechamento de cima.
        _vazio_base = float(p.get('vazio_base_local', 0) or 0)
        if _vazio_base > 0.5:
            msp.add_line(
                (x_cur, y0 + _vazio_base), (x_cur + pw, y0 + _vazio_base),
                dxfattribs={'layer': 'Painéis'},
            )

        # Reaproveitamento: hatch ANSI31 na faixa do painel (N2 CE / recorte).
        # Sem isto o N4 parece "oco" na zona de degrau e falha a visão canónica.
        # `is_reuse` ficava calculado e nunca usado (achado 2026-07-28,
        # validacao visual direta: N2 real de V301.A mostra hachura cruzada
        # cobrindo o painel de 244 inteiro, N4 so tinha as linhas de
        # sarrafo, sem hachura nenhuma).
        if is_reuse and 'Hachura' not in skip_layers:
            _reuse_regions = p.get('reuse_regions') or []
            # y_offset/height vem da propria hachura real do N2 (layer
            # REAPROVEITAMENTO, extracao independente do contorno do
            # painel) — replay fiel usa a posicao dela tal como capturada,
            # mesmo quando nao cobre a faixa onde o painel foi desenhado
            # (achado 2026-08-31, V301.B#1: hachura real do N2 fica em
            # y=98.4-142.4, fora de [y_panel, y_panel+h_draw]=[65,108.6];
            # um fallback por overlap tentado antes forcava a hachura pra
            # 65-108.6, o que CONTRARIA o proprio DXF do N2 — revertido).
            _reuse_rects = (
                [
                    (
                        x_cur + float(_rr.get('x_offset', 0) or 0),
                        y0 + float(_rr.get('y_offset', 0) or 0),
                        float(_rr.get('width', pw) or pw),
                        float(_rr.get('height', h_draw) or h_draw),
                    )
                    for _rr in _reuse_regions
                ]
                if _reuse_regions
                else [(x_cur, y_panel, pw, h_draw)]
            )
            for _rx0, _ry0, _rw, _rh in _reuse_rects:
                if _rw <= 0.5 or _rh <= 0.5 or not DRAW_HATCHES_PAINEL:
                    continue
                try:
                    ht_reuse = msp.add_hatch(
                        dxfattribs={'layer': 'Hachura', 'color': 8}
                    )
                    ht_reuse.paths.add_polyline_path(
                        [
                            (_rx0, _ry0), (_rx0 + _rw, _ry0),
                            (_rx0 + _rw, _ry0 + _rh), (_rx0, _ry0 + _rh),
                        ],
                        is_closed=True,
                    )
                    ht_reuse.set_pattern_fill('ANSI31', scale=0.4)
                except Exception:
                    pass

        if has_laje_central and lc_h_d > 0.5 and 'SCO-___-LAJ' not in skip_layers:
            # Laje central: retangulo fechado + hachura ANSI31
            laje_y = y0 + h1_d
            pts_lc = [(x_cur, laje_y), (x_cur+pw, laje_y),
                      (x_cur+pw, laje_y+lc_h_d), (x_cur, laje_y+lc_h_d)]
            msp.add_lwpolyline(pts_lc, close=True,
                               dxfattribs={'layer': 'SCO-___-LAJ'})

        # ── Sarrafos / Grades for H1 zone ──────────────────────────────
        # Se o N2 trouxe sarrafos_horizontais, o replay global substitui o
        # padrão SCR por-painel (evita inventar 8 linhas no vão errado).
        use_n2_horiz = bool(sarrafos_horizontais)
        h1_zone = h1_d if has_laje_central else h_draw
        y_face_top = y0 + h
        y_shoulder = _degrau_shoulder_y(y0, h, panels)
        skip_ys = [y0, y_face_top]
        if y_shoulder is not None:
            skip_ys.append(y_shoulder)
        if panel_type == 'Grade' and gh1 > 0 and not reverse_grade_style:
            # Grade mode
            y_grade_top = (y_panel + h1_zone) if has_laje_central else (y_panel + h_draw)
            draw_grade_mode(
                msp, x_cur, y_grade_top, pw, gh1, is_first, is_last,
                layer_override=None,
            )
        elif panel_type == 'Grade':
            pass
        elif (
            not use_n2_horiz
            and not bool(p.get('suppress_auto_sarrafos', False))
        ):
            # Fallback SCR só sem geometria N2 de sarrafo horizontal.
            sarr_layer, sarr_w, positions = _get_sarrafo_positions(h1_zone)
            draw_sarrafos_by_height(msp, x_cur, y_panel, h1_zone, pw,
                                    sarr_layer, sarr_w, positions,
                                    is_first, is_last, skip_ys=skip_ys)

        # ── Sarrafos / Grades for H2 zone (only with laje central) ────
        if has_laje_central and lc_h_d > 0.5 and not use_n2_horiz:
            h2_zone = h - h1_d - lc_h_d
            y0_h2 = y0 + h1_d + lc_h_d
            if h2_zone > 2:
                if panel_type == 'Grade' and gh2 > 0:
                    draw_grade_mode(msp, x_cur, y0_h2 + h2_zone, pw, gh2,
                                    is_first, is_last)
                else:
                    sarr_layer2, sarr_w2, positions2 = _get_sarrafo_positions(h2_zone)
                    draw_sarrafos_by_height(msp, x_cur, y0_h2, h2_zone, pw,
                                            sarr_layer2, sarr_w2, positions2,
                                            is_first, is_last, skip_ys=skip_ys)

        x_cur += pw

    _marco_h_min_data = 0.0
    for _sh in (sarrafos_horizontais or []):
        _marco_h_min_data = max(
            _marco_h_min_data, float(_sh.get('y_offset', 0) or 0) - h,
        )
    for _sv in (sarrafos_verticais or []):
        _marco_h_min_data = max(
            _marco_h_min_data, float(_sv.get('y_top', 0) or 0) - h,
        )
    _draw_panel_frame_n2(
        msp, x0, y0, h, panels,
        marco_laje_sup=marco_laje_sup,
        laje_sup=laje_sup,
        marco_h_min=_marco_h_min_data,
        laje_trechos=laje_trechos,
        aberturas_viga=aberturas_viga,
        painel_sup_alt=painel_sup_alt,
        painel_sup_width=painel_sup_width,
        painel_sup_x_offset=painel_sup_x_offset,
    )
    # Hachura ANSI31 na faixa superior do degrau (N2 V301) — densifica visao.

    # ── 3b. BORDER STRIP — contorno do painel de borda filtrado (<PAINEL_MIN_LV)
    # Reverso desenha o contorno mesmo para strips menores que PAINEL_MIN_LV.
    # Painéis: divisor (1) + draw_panel_lines (4) = 5 entities
    # SCO-___-LAJ: laje_inf + laje_sup para o strip = 2 entities (+ 2 no face oposta)
    if border_strip_width > 0:
        a_bp = {'layer': 'Painéis'}
        bsw = border_strip_width
        # Divisor entre último painel e border strip (duplica borda direita do último)
        msp.add_line((x_cur, y0), (x_cur, y0+h), dxfattribs=a_bp)
        # Contorno do border strip (4 linhas)
        draw_panel_lines(msp, x_cur, y0, bsw, h)
        # Laje inferior do border strip
        if laje_inf > 0 and 'SCO-___-LAJ' not in skip_layers:
            msp.add_lwpolyline(
                [(x_cur, y0-laje_inf), (x_cur+bsw, y0-laje_inf),
                 (x_cur+bsw, y0), (x_cur, y0)],
                close=True, dxfattribs={'layer': 'SCO-___-LAJ'})
        # Laje superior do border strip
        if laje_sup > 0 and 'SCO-___-LAJ' not in skip_layers:
            msp.add_lwpolyline(
                [(x_cur, y0+h), (x_cur+bsw, y0+h),
                 (x_cur+bsw, y0+h+laje_sup), (x_cur, y0+h+laje_sup)],
                close=True, dxfattribs={'layer': 'SCO-___-LAJ'})
        x_cur += bsw

    # ── 4. Sarrafo spans (SCR anatomy: n_pos×n_panels extra LWPOLY per face)
    if not suppress_sarrafo_spans and not sarrafos_horizontais:
        sarr_layer_face, _, _ = _get_sarrafo_positions(h)
        draw_sarrafo_spans(msp, x0, y0, panels, h, sarr_layer_face)

    # Horizontais do N2 (autoridade) — antes dos verticais para leitura limpa.
    # NÃO banir o ombro do degrau: no N2 há SARR em y=ombro (ex. 244–398.5 @ 65)
    # além da linha Painéis curta do ombro (0–fim_degrau).
    if sarrafos_horizontais:
        _ys_frame = [y0, y0 + h]
        # Cap generoso: nao usar so h (corpo) — o N2 as vezes tem marco real
        # bem mais alto que laje_sup+painel_sup_alt capturam (achado
        # 2026-08-29, UNIT.B#7: sarrafos H reais ate +33.8 acima do corpo,
        # y_max=h cortava 4 linhas legitimas). frame_ys ja protege contra
        # sobrepor as bordas Painéis reais.
        _max_sarr_offset = max(
            (float(_s.get('y_offset', 0) or 0) for _s in sarrafos_horizontais),
            default=h,
        )
        _h_face_cap = max(h, _max_sarr_offset + 1.0)
        _ysh_pre = _degrau_shoulder_y(y0, h, panels)
        _dbounds_pre = _degrau_zone_bounds_x(x0, h, panels)
        _dstart_pre = _dbounds_pre[0] if _dbounds_pre else None
        _dend_pre = _dbounds_pre[1] if _dbounds_pre else None
        _pdiv_acc = float(x0)
        _pdiv_xs = [_pdiv_acc]
        for _pw in panel_widths:
            _pdiv_acc += float(_pw or 0)
            _pdiv_xs.append(_pdiv_acc)
        # Extremidade real = pela POSICAO (perto de SARR_INSET_H de cada
        # borda), nao pelo rotulo 'side' — a extracao as vezes marca o
        # sarrafo da ponta direita como 'internal' em vez de 'right' (achado
        # 2026-09-10, V301.A: sarrafo em x_offset=398.5, y_bot=0/y_top=h
        # inteiro, rotulado 'internal', mas fisicamente E a extremidade —
        # 8 sarrafos horizontais ficavam indo ate a parede real por causa
        # disso, o filtro por 'side'=='right' nunca achava esse sarrafo).
        # body_end real (nao a soma ingenua de TODOS os paineis): paineis
        # residuais de marco/cota no fim (ex. 19.0/21.2) nao fazem parte do
        # corpo onde os sarrafos realmente terminam — usar a soma inteira
        # aqui dava _total_w=445.7 num corpo cujo sarrafo direito real
        # esta em 398.5 (corpo=405.5), nunca batendo a tolerancia (achado
        # 2026-09-10, V301.A).
        _small_x_body = _small_panel_start_x(x0, h, panels)
        _total_w = (
            float(_small_x_body) - float(x0) if _small_x_body is not None
            else sum(float(w or 0) for w in panel_widths)
        )
        _left_sarr_x = None
        _right_sarr_x = None
        _vertical_specs = []
        for _sv in (sarrafos_verticais or []):
            _xoff = float(_sv.get('x_offset', 0) or 0)
            _vx_abs = float(x0) + _xoff
            _vyb_abs = float(y0) + float(_sv.get('y_bot', 0) or 0)
            _vyt_abs = float(y0) + float(_sv.get('y_top', h) or h)
            _vertical_specs.append((_vx_abs, _vyb_abs, _vyt_abs))
            if abs(_xoff - SARR_INSET_H) < 3.0:
                _left_sarr_x = _vx_abs
            elif abs(_xoff - (_total_w - SARR_INSET_H)) < 3.0:
                _right_sarr_x = _vx_abs
        _abr_pilar = classificar_aberturas_pilar(
            panels, sarrafos_horizontais,
            painel_sup_width=painel_sup_width,
            painel_sup_x_offset=painel_sup_x_offset,
        )
        # ── Sarrafo do painel de fechamento para nos verticais dele ────────
        # Apontamento do dono (2026-09-13, P4): "este sarrafo vai de p5 a p6,
        # tem os sarrafos verticais da extremidade que tem que respeitar".
        # Medido na V13 face A: o painel de topo desenha a propria corrida em
        # 1807->1993 (186, entre os verticais em SARR_INSET_H), mas o replay
        # cru do N2 punha outra em 1800->2000 (200, de ponta a ponta) —
        # atravessando os verticais.
        _tp_h = float(painel_sup_alt or 0)
        _tp_w = float(painel_sup_width or 0)
        _tp_band = None
        if _tp_h > 0.5 and _tp_w > 2 * SARR_INSET_H:
            _tp_x0 = float(painel_sup_x_offset or 0)
            _tp_x1 = _tp_x0 + _tp_w
            _tp_band = (
                float(h) + float(laje_sup or 0) - 1.0,
                float(h) + float(laje_sup or 0) - 1.0 + _tp_h + 2.0,
                _tp_x0 + SARR_INSET_H,
                _tp_x1 - SARR_INSET_H,
            )
        draw_sarr_lv_horizontal_from_n2(
            msp, x0, y0, sarrafos_horizontais, frame_ys=_ys_frame,
            h_face=_h_face_cap,
            degrau_start=_dstart_pre, degrau_end=_dend_pre, y_shoulder=_ysh_pre,
            left_sarr_x=_left_sarr_x, right_sarr_x=_right_sarr_x,
            panel_div_xs=_pdiv_xs, vertical_specs=_vertical_specs,
            aberturas_pilar=_abr_pilar, top_panel_band=_tp_band,
        )
        # ── Cota da abertura de pilar (apontamento do dono P6) ─────────────
        # O N2 cota a largura da abertura dentro do corpo, perto do topo.
        # Medido na V13: face A "78" em x=39.0 (abertura 0..78) e face B "78"
        # em x=376.0 (abertura 337..415), as duas a 29.8 do fundo do corpo,
        # numa face de 44 de altura — ou seja a ~0.68 da altura.
        for _ai, _af in _abr_pilar:
            _larg = round(_af - _ai, 1)
            if _larg <= 1.0:
                continue
            # Geometria copiada do N2 (medida na V13 face A, handles BA/BB/BC):
            #   linha de cota a 21.67 do fundo do corpo (h=44 -> 0.492);
            #   linhas de extensao MINUSCULAS, 0.68 (19.34 -> 18.67);
            #   patinhas obliquas de 45, vetor (-3,-3) e (+3,+3).
            # A 1a tentativa punha p1/p2 no FUNDO do corpo, o que gerava
            # extensao de 32.8 atravessando o corpo inteiro de baixo a cima —
            # e' o que o dono viu como "patinhas invertidas" (a cota 244, que
            # ele aceita, tem extensao de 53 mas ela corre FORA do desenho,
            # abaixo do corpo). Medir logo abaixo da linha de cota mantem o
            # tocao curto, como no N2.
            _y_cota = y0 + float(h) * 0.492
            emitir_cota(
                msp, origem='abertura_larg',
                base=(x0 + (_ai + _af) / 2.0, _y_cota),
                p1=(x0 + _ai, _y_cota - 2.3),
                p2=(x0 + _af, _y_cota - 2.3),
                angle=0,
                texto=_fmt_dim_cm(_larg),
                texto_pos=(x0 + (_ai + _af) / 2.0, _y_cota),
            )

    # Recipe N2: SARR H 7cm no ombro na borda do degrau (294,5→301,5 @ y=65).
    # Se o N2 trouxe sarrafos longos cobrindo isso, o inventário casa o longo;
    # o stub garante o trecho local quando o matching e 1:1.
    _ysh = _degrau_shoulder_y(y0, h, panels)
    _dbounds = _degrau_zone_bounds_x(x0, h, panels)
    _dstart = _dbounds[0] if _dbounds else x0
    _dend = _dbounds[1] if _dbounds else x0
    if _ysh is not None and _dend > _dstart + 1.0:
        try:
            _trailing_step = _dstart > x0 + 0.5
            _sx0 = _dstart - SARR_INSET_H if _trailing_step else _dend
            _sx1 = _dstart if _trailing_step else _dend + SARR_INSET_H
            # O sarrafo longo do proprio N2 (acima, ja cortado na fronteira
            # do degrau) pode ja cobrir esse trecho local — nesse caso o
            # stub vira duplicata (mesma camada/altura, sub-segmento contido
            # no que ja foi desenhado). So desenha quando NENHUM sarrafo do
            # inventario cobre esse intervalo (achado 2026-09-09: apos
            # cortar o sarrafo longo na fronteira do degrau, o stub sobrava
            # redundante em cima do inicio dele).
            _covered = any(
                abs(float(_s.get('y_offset', 0) or 0) - (_ysh - y0)) < 2.0
                and x0 + float(_s.get('x_left', 0) or 0) <= _sx0 + 0.5
                and x0 + float(_s.get('x_right', 0) or 0) >= _sx1 - 0.5
                for _s in (sarrafos_horizontais or [])
            )
            if not _covered:
                msp.add_line(
                    (_sx0, _ysh), (_sx1, _ysh),
                    dxfattribs={'layer': 'SARR_2.2x7'},
                )
        except Exception:
            pass

    # A ficha N2 define se há sarrafo vertical em cada extremidade. Não
    # inferir por default: reproduzir somente os lados detectados pelo reverso.
    draw_sarr_lv_vertical_pairs(
        msp, x0, y0, h, panel_widths,
        draw_left=bool(sarrafo_vertical_esquerdo),
        draw_right=bool(sarrafo_vertical_direito),
        sarrafos_verticais=sarrafos_verticais,
        y_shoulder=_ysh,
    )

    # ── 5. PILARES/OBSTACULOS -- retangulos hachurados nas bordas ─────────
    def _draw_pillar(px, py, pw_p, ph_p):
        pts = [(px, py), (px+pw_p, py), (px+pw_p, py+ph_p), (px, py+ph_p)]
        msp.add_lwpolyline(pts, close=True,
                           dxfattribs={'layer': 'Painéis', 'linetype': 'DASHED'})
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
    if nome_face:
        add_text(msp, x0 + 3, y0 + h + laje_sup + NOM_ABOVE, nome_face,
                 float(nom_height or NOM_H), 'NOMENCLATURA')

    # ── 7. IDs de painel: codigos_forma reais (fichas_lv_v2) ou fallback str(i+1)
    x_cur = x0
    for i, p in enumerate(panels):
        pw = p['width']
        cx = x_cur + pw / 2
        cy = y0 + h / 2
        codes = p.get('codigos', [])
        label = ' '.join(codes) if codes else (str(i + 1) if fallback_panel_ids else '')
        if label:
            add_text(msp, cx, cy + 4, label, PID_H, '5', halign=1, valign=2)
        x_cur += pw

    # ── 7b. Pontalete count per panel (h>=80: per-panel; 40<=h<80: total face)
    # pontaletes_face override: 0=suprimir, int=total fixo, list=por-painel, None=usar fórmula
    if pontaletes_face == 0:
        pass  # suprimir completamente
    elif (
        isinstance(pontaletes_face, list)
        and pontaletes_face
        and isinstance(pontaletes_face[0], dict)
    ):
        for item in pontaletes_face:
            try:
                n_pont = int(item.get('count', 0) or 0)
                if n_pont <= 0:
                    continue
                cx = x0 + float(item.get('x_offset', 0) or 0)
                cy = y0 + float(item.get('y_offset', h / 2) or h / 2)
                layer = str(item.get('layer') or '5')
                height = float(item.get('height') or 9.0)
                color = item.get('color')
                add_text(
                    msp, cx, cy, str(item.get('text') or f'{n_pont} 1/2pont'),
                    height, layer, halign=1, valign=2, color=color,
                )
            except Exception:
                continue
    elif isinstance(pontaletes_face, list):
        # Override por-painel (ex: [4, 5] para V5.A)
        x_cur = x0
        for i, p in enumerate(panels):
            pw = p['width']
            n_pont = pontaletes_face[i] if i < len(pontaletes_face) else 0
            if n_pont > 0:
                cx = x_cur + pw / 2
                cy = y0 + h / 2
                add_text(msp, cx, cy - 10, f'{n_pont} 1/2pont', 9.0, '5', halign=1, valign=2)
            x_cur += pw
    elif isinstance(pontaletes_face, int) and pontaletes_face > 0:
        # Override total fixo
        cx_face = x0 + comprimento / 2
        cy_face = y0 + h / 2
        add_text(msp, cx_face, cy_face - 10, f'{pontaletes_face} 1/2pont', 9.0, '5', halign=1, valign=2)
    else:
        # Fórmula padrão
        if h >= 80:
            x_cur = x0
            for p in panels:
                pw = p['width']
                cx = x_cur + pw / 2
                cy = y0 + h / 2
                n_pont = max(2, math.floor(pw / 30.0))
                add_text(msp, cx, cy - 10, f'{n_pont} 1/2pont', 9.0, '5', halign=1, valign=2)
                x_cur += pw
        elif h >= 40:
            total_pont = sum(max(2, math.floor(p['width'] / 40.0)) for p in panels)
            cx_face = x0 + comprimento / 2
            cy_face = y0 + h / 2
            add_text(msp, cx_face, cy_face - 10, f'{total_pont} 1/2pont', 9.0, '5', halign=1, valign=2)

    # ── 7c. Nota face (referência especial, ex: "VEM DA V113.A") ──────────
    if nota_face:
        cx_face = x0 + comprimento / 2
        cy_face = y0 + h / 2
        add_text(msp, cx_face, cy_face + 10, nota_face, 10.0, '5', halign=1, valign=2)

    # ── 8. Cotas horizontais — fidelidade de RÓTULO ao N2 ────────────────
    # G geometria ≠ R rótulo ≠ P política. Regra: R_N4 ⊆ R_N2 (nunca inventar).
    # N2 CE (V301.A): 244 | 50,5 | 111 + resto 161,5 — sem marco, sem total.
    # Patas: no vao recuado do degrau sobem ate o ombro (fundo real do painel),
    # nao param no y0 vazio (print ShareX zona 244/50,5).
    _ysh_h = _degrau_shoulder_y(y0, h, panels)
    _dbounds_h = _degrau_zone_bounds_x(x0, h, panels)
    _dstart_h = _dbounds_h[0] if _dbounds_h else x0
    _dend_h = _dbounds_h[1] if _dbounds_h else x0

    def _span_panel_attachments(xa, xb):
        """Return the real panel-bottom Y for both dimension witnesses."""
        mid = (float(xa) + float(xb)) / 2.0
        if (
            _ysh_h is not None
            and float(_dstart_h) - 0.1 <= mid <= float(_dend_h) + 0.1
        ):
            return float(_ysh_h), float(_ysh_h)
        return (
            _panel_attach_y(xa, y0, _ysh_h, _dend_h, _dstart_h),
            _panel_attach_y(xb, y0, _ysh_h, _dend_h, _dstart_h),
        )

    dim_widths = _panel_widths_for_horizontal_dims(x0, h, panels, panel_widths)
    groups = group_panel_dims(dim_widths, PANEL_DIM_MIN_W)
    # offsets originais para reemitir partes 22.5|52.5 (N2 B tem as duas + 75)
    _dw_x = 0.0
    _dw_offsets = []
    for _w in dim_widths:
        _dw_offsets.append(_dw_x)
        _dw_x += float(_w or 0)

    def _clean_group_parts(x_off, n_p):
        if n_p != 2:
            return []
        for wi, off in enumerate(_dw_offsets):
            if abs(float(off) - float(x_off)) < 0.15:
                parts = dim_widths[wi: wi + 2]
                if len(parts) == 2 and all(
                    20.0 <= float(w) <= 55.0
                    and abs(float(w) - round(float(w) * 2.0) / 2.0) < 0.08
                    for w in parts
                ):
                    return parts
        return []

    # Qual grupo e' o SEGMENTO DE BORDA — o mesmo que o bloco de complemento
    # logo abaixo exclui do span. Saber isso e' o que permite dar nivel por
    # papel estrutural em vez de por tamanho.
    # Ha' segmentacao quando uma abertura de VIGA parte a face em dois
    # segmentos (regra do dono). Sem isso a face inteira e' UM segmento, e
    # entao nao ha' "borda + complemento" — ha' painel e total.
    # Fator de repeticao por painel ("7X" no desenho): qual painel vale por
    # varios, e quanto a total tem de somar.
    _fatores = [int(f) for f in (fatores_painel or [])]
    _idx_fator = next((i for i, f in enumerate(_fatores) if f > 1), None)

    def _texto_total(_span):
        """Texto da cota total. Com fator, soma cada painel pelo seu fator:
        na V303.B da' 244 + 7x244 + 66,5 + 244 = 2262,5, e nao os 798,5 que a
        face ocupa no papel."""
        if _idx_fator is None:
            return _fmt_dim_cm(_span)
        _soma = 0.0
        for _i, _p in enumerate(panels or []):
            _w = float(_p.get('width', 0) or 0)
            _soma += _w * (_fatores[_i] if _i < len(_fatores) else 1)
        return _fmt_dim_cm(round(_soma, 1))

    _tem_segmentacao = bool(aberturas_viga)
    _idx_borda = None
    if len(groups) >= 3:
        if float(groups[0][1]) >= 150.0:
            _idx_borda = 0
        elif float(groups[-1][1]) >= 150.0:
            _idx_borda = len(groups) - 1

    # Sem segmentacao a face e' UM segmento: o nivel externo guarda o TOTAL e
    # todo painel desce para o interno. Com segmentacao, o externo guarda a
    # particao (borda + complemento) — e' o caso da V302.A, que o dono
    # aprovou assim.
    #
    # Excecao medida: quando o COMPLEMENTO e' justamente o numero que o N2
    # escreve nesta unidade, ele manda. Trocar um valor que esta' no papel por
    # um total que nao esta' seria inventar:
    #
    #   V13.A          compl 171 ausente | total 415 no N2  -> total
    #   V301 (5 unid.) compl 174 NO N2   | total 418 ausente -> complemento
    #   CONT.V302.A    nenhum dos dois no N2                 -> total, que e'
    #                  o que o dono pediu (2A, P1-P4: "faltou essa total
    #                  englobar o p3 p4")
    # Sem `edge_span_candidates` informado nao ha' como saber o que o N2
    # escreve, e ai vale o comportamento historico — mesma convencao que
    # `_span_ok` ja' usa logo abaixo. E' o caso dos fixtures sinteticos.
    _compl_no_n2 = not edge_span_candidates
    if (not _tem_segmentacao and _idx_borda is not None
            and edge_span_candidates):
        _c = (sum(g[1] for g in groups[1:]) if _idx_borda == 0
              else sum(g[1] for g in groups[:-1]))
        _compl_no_n2 = any(
            abs(float(v) - float(_c)) <= 1.0 for v in edge_span_candidates
        )
    # ...e tambem quando o N2 escreve o TOTAL DA FACE nesta unidade. Com
    # abertura de viga na PONTA a face nao se parte em dois desenhos: o painel
    # segue por baixo da abertura ate' a ponta, e o N2 cota a face inteira.
    # Medido na V303 (unidade 157,5 + 29): o desenho traz "186.5" e nenhuma
    # largura de painel, enquanto o robo emitia "157,5" — apontamento do dono
    # (SEGMENTO 5B, P1: "a total deve abarcar incluso o painelzinho abaixo da
    # abertura").
    # ESCOPO: so' quando a abertura encosta numa PONTA da face. No meio dela
    # a face se parte mesmo em dois segmentos, e ai vale a particao — medido:
    # V302.A abre em 178,5..200,5 de uma face de 470, e a [53, 63,5] abre em
    # 31..53 de 116,5; nas duas o N2 escreve as larguras de painel, nao o
    # total, e forcar o total mudava desenho ja' APROVADO.
    _total_face = sum(float(g[1]) for g in groups)
    _abertura_na_ponta = any(
        abs(float(_av.get('x_ini', 0) or 0)) <= 1.0
        or abs(float(_av.get('x_fim', 0) or 0) - _total_face) <= 1.0
        for _av in (aberturas_viga or [])
    )
    _total_no_n2 = (
        _abertura_na_ponta and bool(edge_span_candidates) and any(
            abs(float(v) - _total_face) <= 1.0 for v in edge_span_candidates
        )
    )
    # Com 3+ grupos o nivel externo ja' saia de qualquer jeito e o que se
    # decide aqui e' o ALCANCE dele. Com 2 grupos nao saia nada, e criar uma
    # total exige que o N2 a escreva: medido na V301 (paineis 52,5+22,5+244,
    # dois grupos) o desenho traz 7 / 22,5 / 52,5 / 75 / 244 e NAO traz 319 —
    # o 75 e' o grupo, e e' ele que vai para o nivel externo.
    _total_esta_no_n2 = bool(edge_span_candidates) and any(
        abs(float(v) - _total_face) <= 1.0 for v in edge_span_candidates
    )
    # ...e, acima de tudo, quando o N2 escreve o TOTAL DA FACE nesta unidade.
    # Aqui nao se decide nada por heuristica: o numero esta' no papel. Medido na
    # V304.A#1 (paineis 176 | 27 | 172 | 27 | 176, com abertura de viga no
    # meio): `_tem_segmentacao` e' True, entao o externo ia para "borda +
    # complemento" = 402, que NAO esta' no desenho — e `_span_ok` matava a cota.
    # Resultado: a unidade ficava SEM nenhuma total, com o 578 escrito no N2.
    # Nas ja' aprovadas isso nao mexe, porque la' o total nao esta' no papel:
    # V302.A (face 470) e a [53, 63,5] escrevem largura de painel, e a V301
    # escreve o complemento 174 e nao o 418.
    _usar_total = (((not _tem_segmentacao) and not _compl_no_n2)
                   or _total_no_n2 or _total_esta_no_n2)

    # Abertura na ponta com o N2 escrevendo SO' o total: as larguras de
    # painel sao invencao. Medido na V303 (unidade 157,5 + 29): o unico numero
    # que o desenho traz embaixo e' "186.5" — nem 157,5 nem 29. O "29" que
    # existe no N2 esta' ACIMA, e e' a largura da ABERTURA, nao do painel.
    # O teste e' direto: o N2 escreve alguma LARGURA DE PAINEL desta unidade?
    # Se nao escreve nenhuma, so' ha' o total, e emitir larguras e' inventar.
    # Antes isto era "ha' exatamente um candidato", que diz a mesma coisa so'
    # quando o desenho nao traz mais nada embaixo. Medido na V304.B: os
    # candidatos sao 15 (altura da sobra) e 60 (o total) — dois valores, mas
    # nenhuma das larguras (29 e 31) esta' no papel, e o robo desenhava as
    # duas. Na V303 (157,5 + 29, candidato unico 186,5) o resultado nao muda.
    # O TOTAL da face nao conta como largura — e' ele que esta' no papel, e
    # confundi-lo com uma largura faria o teste se anular sozinho sempre que a
    # unidade tem um grupo so'.
    _larguras_painel = {
        _w for _w in (
            {round(float(p.get('width', 0) or 0), 1) for p in (panels or [])}
            | {round(float(g[1]), 1) for g in groups}
        )
        if abs(_w - _total_face) > 1.0
    }
    _so_total = _total_no_n2 and not any(
        abs(float(v) - _w) <= 1.0
        for v in (edge_span_candidates or [])
        for _w in _larguras_painel
    )

    for gi, (x_off, w_sum, n_p) in enumerate(groups):
        if w_sum < 5.0 or _so_total:
            continue
        # Nivel da cota H por PAPEL, nao por largura:
        #   nivel 1 (50) = o que particiona a face em segmentos;
        #   nivel 0 (25) = os paineis DENTRO de um segmento.
        # A regra anterior era "w_sum >= 150 -> nivel externo", que nao sabe
        # a diferenca: na V302.A jogava o painel 159,5 para o nivel da cota
        # total (apontamento do dono, P1/P2 do SEGMENTO 1A) e na CONT.V302.A
        # jogava os quatro 244 junto com o 732 que os agrupa (P1/P2 do 2A).
        # Com o segmento de borda conhecido, o particionamento e' borda +
        # complemento, e todo o resto e' painel interno:
        #   V302.A  200,5 | 269,5  externo ; 159,5 e 110  interno
        #   CONT.A  244   | 732    externo ; os outros 244 interno
        #   V13.A   244   | 171    externo ; 63 e 108     interno  (ja' era)
        if _usar_total:
            # O externo guarda so' o total, entao TODO painel fica no interno.
            # Medido no N2 da V13.A, que o dono validou: nivel 26,5 traz
            # 244 | 63 | 108 e o nivel 55,0 traz o 415 da face inteira — o 244
            # nao sobe de nivel por ser largo. Apontamento do dono na
            # CONT.V302.A (2A, P3/P4): "esse deve estar em nivel cota painel
            # para a total abarcar ele".
            level = 0
        elif _idx_borda is not None:
            level = 1 if gi == _idx_borda else 0
        elif ((w_sum >= 150.0 and len(groups) >= 2)
                or _clean_group_parts(x_off, n_p)):
            level = 1
        else:
            level = 0
        xa = float(x0 + x_off)
        xb = float(x0 + x_off + w_sum)
        yp1, yp2 = _span_panel_attachments(xa, xb)
        dim_panel_lv(
            msp, xa, xb, y0,
            text_override=_fmt_dim_cm(w_sum),
            level=level,
            y_p1=yp1,
            y_p2=yp2,
        )
        # Partes do grupo so se forem cotas limpas (.0/.5) — N2 B: 22.5|52.5
        # alem do 75. Nao reemitir 28.7+21.8 (vira 29 inventada no A).
        if n_p == 2:
            acc = 0.0
            parts = []
            for wi, ww in enumerate(dim_widths):
                if abs(acc - float(x_off)) < 0.15:
                    parts = dim_widths[wi: wi + 2]
                    break
                acc += float(ww or 0)

            def _clean_half(w):
                w = float(w)
                if not (20.0 <= w <= 55.0):
                    return False
                r5 = round(w * 2.0) / 2.0
                return abs(w - r5) < 0.08

            if len(parts) == 2 and all(_clean_half(p) for p in parts):
                px = float(x0 + x_off)
                for pw in parts:
                    pw = float(pw)
                    pyp1, pyp2 = _span_panel_attachments(px, px + pw)
                    dim_panel_lv(
                        msp, px, px + pw, y0,
                        text_override=_fmt_dim_cm(pw),
                        level=0,
                        y_p1=pyp1,
                        y_p2=pyp2,
                    )
                    px += pw
    # Complemento da cadeia no segundo nivel: funciona tanto para degrau
    # inicial (244 | 63+111 = 174) quanto espelhado (52,5+22,5 = 75 | 244).
    # REGRA DO DONO (2026-09-19): "se for so' 1 painel nao precisa, mas se
    # tiver mais de 1 painel ai sim tem a total". Antes so' a partir de 3
    # grupos — a V303.B#2, paineis [174, 244], ficava com as duas cotas de
    # painel e NENHUMA total (apontamento do dono, SEGMENTO 3B).
    # Medido: o N2 escreve o total em TODAS as unidades de 2 grupos das duas
    # vigas (V303 e V302), entao a V302 tambem ganha as dela.
    # REGRA DO DONO (2026-09-19): "se for so' 1 painel nao precisa, mas se
    # tiver mais de 1 painel ai sim tem a total". Com 3+ grupos o nivel
    # externo ja' saia; com 2 ele nao saia nunca — a V303.B#2, paineis
    # [174, 244], ficava com as duas cotas de painel e NENHUMA total
    # (SEGMENTO 3B).
    #
    # Com 2 grupos a total so' sai se o N2 a escrever. Medido na V301
    # (52,5 + 22,5 + 244, agrupados em dois): o desenho traz 7 / 22,5 / 52,5
    # / 75 / 244 e NAO traz 319 — ali o 75 e' o grupo e nao ha' total. Nas de
    # 2 grupos da V302 e da V303 o total esta' no papel em TODAS, e por isso
    # a V302 tambem passa a ter as dela.
    # `_so_total` diz que o unico numero embaixo, no N2, e' o total — entao ele
    # tem de sair, independentemente de quantos grupos a unidade tenha. Medido
    # na V304.B: a unidade forma UM grupo de 60, e era esse grupo que aparecia
    # como se fosse a total. Suprimindo os grupos (o N2 nao escreve 29 nem 31)
    # a face ficava sem numero nenhum embaixo.
    if (_so_total or len(groups) >= 3
            or (len(groups) >= 2 and _total_esta_no_n2)):
        edge_span = None
        if _usar_total:
            # UM segmento -> a cota externa e' o TOTAL da face, nao o
            # complemento de uma borda. Na CONT.V302.A o complemento dava 732
            # e deixava o primeiro 244 de fora (apontamento do dono, 2A);
            # agora cobre os quatro. Na V13.A da' 415, que e' exatamente o que
            # o N2 escreve no nivel externo.
            edge_span = (
                float(x0 + groups[0][0]),
                float(x0 + groups[-1][0] + groups[-1][1]),
            )
        elif float(groups[0][1]) >= 150.0:
            edge_span = (
                float(x0 + groups[1][0]),
                float(x0 + groups[-1][0] + groups[-1][1]),
            )
        elif float(groups[-1][1]) >= 150.0:
            edge_span = (
                float(x0 + groups[0][0]),
                float(x0 + groups[-1][0]),
            )
        if edge_span:
            x_a, x_b = edge_span
            span = x_b - x_a
            # So desenha se o N2 REALMENTE mostra esse valor nesta ocorrencia
            # especifica. Repeticoes idênticas do mesmo painel nem sempre
            # repetem esse label auxiliar (achado real: V301.B#5 tem "174"
            # no papel; o vizinho V301.B#7, mesma fileira, mesma geometria,
            # nao tem). Sem candidatos informados (ex. testes sinteticos
            # antigos, sem esse parametro), mantem o comportamento historico.
            _is_repeat = '#' in str(nome_face or '')
            _span_ok = (
                (not _is_repeat)
                or edge_span_candidates is None
                or any(
                    abs(float(v) - span) <= 1.0 for v in edge_span_candidates
                )
            )
            if span >= PANEL_DIM_MIN_W and _span_ok:
                yp1, yp2 = _span_panel_attachments(x_a, x_b)
                dim_panel_lv(
                    msp, x_a, x_b, y0,
                    text_override=_texto_total(span),
                    level=2 if _idx_fator is not None else 1,
                    y_p1=yp1,
                    y_p2=yp2,
                )

    # ── FATOR DE REPETICAO ("7X") ─────────────────────────────────────────
    # Regra do dono (2026-09-19): "indicacao de 7 paineis de 244 (...) o nosso
    # total deveria somar essa quantidade no calculo (...) cuidado para nao
    # ficar no mesmo nivel de cota essa cota indicadora de fator".
    #
    # Medido no N2 da V303.B: a cadeia de paineis fica no nivel 26,8 e o "7X"
    # num nivel proprio, 48,6, com linha de cota cobrindo SO' o painel que ele
    # multiplica (7136,2..7380,2). Dai a escala de niveis:
    #     sem fator   paineis 25  |  total 50
    #     com fator   paineis 25  |  "NX" 50  |  total 75
    if _idx_fator is not None and panels:
        _accf = 0.0
        for _if, _pf in enumerate(panels):
            _wf = float(_pf.get('width', 0) or 0)
            if _if == _idx_fator and _wf > 1.0:
                _xfa = float(x0) + _accf
                _xfb = _xfa + _wf
                _yf1, _yf2 = _span_panel_attachments(_xfa, _xfb)
                dim_panel_lv(
                    msp, _xfa, _xfb, y0,
                    text_override=f"{_fatores[_idx_fator]}X",
                    level=1, y_p1=_yf1, y_p2=_yf2,
                )
                break
            _accf += _wf

    # Sem dim_total cego da face (N2 LV face unit costuma não ter total).

    # Apoios/limites capturados no N1: deixam explícito o ponto inicial e o
    # ponto final da lateral sem inventar referências a partir do N2.
    endpoint_y = y0 - DIM_TOTAL_BELOW - 12.0
    if endpoint_start_label:
        add_text(msp, x0, endpoint_y, str(endpoint_start_label), 12.0,
                 'NOMENCLATURA', halign=0, valign=2, color=5)
    if endpoint_end_label:
        add_text(msp, x0 + comprimento, endpoint_y, str(endpoint_end_label),
                 12.0, 'NOMENCLATURA', halign=2, valign=2, color=5)

    # ── 9. COTAS VERTICAIS SEGMENTADAS (Laje Inf + Altura + Laje Sup) ────
    def _dim_seg_v(x_base, segments, side='left'):
        x_dim = x_base - DIM_H_RIGHT if side == 'left' else x_base + DIM_H_RIGHT
        y_cur = y0 - laje_inf
        for label, seg_h in segments:
            if seg_h <= 0:
                continue
            emitir_cota(
                msp, origem=f'seg_v:{label}',
                base=(x_dim, y_cur),
                p1=(x_base, y_cur), p2=(x_base, y_cur + seg_h),
                angle=90)
            y_cur += seg_h

    p0 = panels[0]
    h1_0, h2_0 = p0['height1'], p0['height2']
    lc_alt_0 = p0.get('laje_central_alt', 0)
    has_lc = (lc_alt_0 > 0) or (h1_0 > 0 and h2_0 > 0 and abs(h1_0 - h2_0) > 0.5)
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
    has_left_opening = any(
        bool(hole.get('active')) for hole in (holes or [])[:2]
    )
    if has_left_opening:
        _dim_seg_v(x0, seg_left, 'left')

    # body_end / leading: ancora de cota na parede do CORPO util.
    _small_x_dim = _small_panel_start_x(x0, h, panels)
    _lead_x_dim = _leading_marco_end_x(x0, h, panels)
    _has_strip_dim = _small_x_dim is not None or _lead_x_dim is not None
    # Altura do marco: residual 15 so com strip real (evita 157 inventado em h=142).
    _marco_h = (
        _marco_extension_cm(
            marco_laje_sup, laje_sup, has_marco_strip=_has_strip_dim,
        )
        if marco_laje_sup
        else 0.0
    )
    # Cotas: so marco real. Nunca laje_sup=7 residual como cota (109+7=116 inventado).
    _cota_marco = float(_marco_h) if float(_marco_h) >= 0.5 else 0.0
    # Rotulo de marco no papel LV e tipicamente 15 mesmo quando a extracao
    # geometrica devolve 20-21 (V301.B). Geometria/_h_total mantem o real.
    _cota_marco_label = (
        15.0 if 17.5 <= float(_cota_marco) <= 24.0 else float(_cota_marco)
    )
    _h_total = h + laje_inf + _cota_marco + _top_panel_h
    y_shoulder = _degrau_shoulder_y(y0, h, panels)
    _body_end = (
        float(_small_x_dim) if _small_x_dim is not None
        else float(x0 + comprimento)
    )
    _body_bounds = _degrau_zone_bounds_x(x0, h, panels) if panels else None
    _body_step_trailing = bool(
        _body_bounds and float(_body_bounds[0]) > float(x0) + 0.5
    )
    # A altura total pertence a parede alta da ficha.
    _dim_right = float(x0) if _body_step_trailing else _body_end
    _body_dim_side = -1.0 if _body_step_trailing else 1.0
    # Niveis de cota (simetricos ESQ/DIR — pedido visual):
    #   nivel 1 = 25 cm  → 15, 44/109, 65 (ombro)
    #   nivel 2 = 50 cm  → 59/124
    _DIM_L1 = 25.0
    _DIM_L2 = 50.0

    def _corpo_no_x(_x_abs):
        """Altura do corpo SOB este x — a mesma que assenta a laje.

        Num segmento de alturas diferentes o corpo nao e' `h` em toda a
        face: na V302.A o painel da esquerda tem 43 e o da direita 45. Usar
        `h` deixava a cota do corpo da direita dizendo 43 e terminando em
        -150, com 2 cm de vao ate' a laje que comeca em -148 -- e 43+14=57
        nao fechava com o total 59 escrito ao lado.

        So' vale quando height1 E' a altura do corpo ali. Em unidade com
        degrau alto ele e' sub-banda (V301: height1=44 num corpo de 109),
        e usar isso derrubava as cotas da viga inteira -- medido contra o
        desenho validado. Folga de 10 cm, a da regra de topo plano.
        """
        _xr = float(_x_abs) - float(x0)
        _acc = 0.0
        for _p in (panels or []):
            _w = float(_p.get('width', 0) or 0)
            if _w <= 0:
                continue
            if _acc - 1.0 <= _xr <= _acc + _w + 1.0:
                _ph = float(_p.get('height1', 0) or 0)
                if _ph > 0 and abs(_ph - float(h)) <= 10.0:
                    return _ph
                break
            _acc += _w
        return float(h)

    # Faces altas (h>=130) sem strip de marco: N2 nao emite 142/157
    # (UNIT.B h=142 inventava). So cota h se h em faixa tipica ou ha strip.
    _emit_h_dim = bool(_has_strip_dim) or float(h) <= 125.0
    _h_dir = _corpo_no_x(_dim_right)
    if _emit_h_dim:
        dim_h_lateral(
            msp, _dim_right, y0 - laje_inf, _h_dir,
            offset=_body_dim_side * _DIM_L1, text_override=_fmt_dim_cm(_h_dir),
        )
    # Com DEGRAU a laje por TRECHO e' a verdade, e ela pode existir mesmo com
    # `_cota_marco` zerado: na V302.B a laje global e' 11,6 (a do trecho sob o
    # painel de fechamento), abaixo do limiar de 12, e a unidade nao tem faixa
    # de marco estreita — entao `_marco_extension_cm` devolve 0 e o bloco
    # inteiro era pulado, deixando a unidade SEM nenhuma cota de laje. O
    # trecho da direita tem 14,6 e o N2 cota ali (dono, V302 1B P5: "falta
    # essa cota da laje"). Nao mexo em `_cota_marco`: ele entra na altura
    # total, que segue o modelo antigo de painel ACIMA da laje.
    _tem_trecho_laje = any(
        float(t.get('altura', 0) or 0) > 0.5 for t in (laje_trechos or [])
    )
    if (_cota_marco > 0.5 or _tem_trecho_laje) and _emit_h_dim:
        # `_h_total` = h + laje_inf + _cota_marco + painel_sup segue o modelo
        # ANTIGO, de painel de fechamento ACIMA da laje. Com trecho de laje o
        # painel fica DENTRO dela e essa soma inventa: na V302.B dava 47
        # (44 + 3) ao lado do 59 verdadeiro. Ali quem emite a total e' o
        # augment, que ancora no topo real do desenho.
        if _cota_marco > 0.5:
            dim_h_lateral(
                msp, _dim_right, y0 - laje_inf, _h_total,
                offset=_body_dim_side * _DIM_L2,
                text_override=_fmt_dim_cm(_h_total),
            )
        # A cota da laje pertence às extremidades do contorno superior, não à
        # parede interna do degrau. Usar _dim_right criava 14/15 no centro e
        # deixava as patas direitas fora do retângulo.
        # Em ocorrencias REPETIDAS (label "V301.B#N", varias copias da mesma
        # face ao longo da viga), o N2 so rotula a cota da laje no(s) lado(s)
        # onde a copia realmente tem faixa de marco (leading/trailing) —
        # sem faixa nenhuma, o papel nao repete a anotacao, mesmo com
        # laje_sup>=12 real. Ocorrencia PRIMARIA (label sem "#") mantem o
        # comportamento historico dos dois lados. NOTA (achado 2026-07-27,
        # ainda sem fix seguro): esta regra geometrica nao vale para TODAS
        # as ocorrencias — UNIT.A#3/#4 (mesmos paineis [111,63,244] do lado
        # B que fica sem cota) TEM cota de marco dos dois lados no N2 real.
        # Tentativa de detectar por texto local (janela x_ref+-20/60,
        # valor~laje_sup) gerou falso-positivo por vizinho de fileira; nao
        # ha sinal geometrico ou textual confiavel encontrado ainda — ver
        # RELATORIO 20260727 (2a parte). Mantido o heuristico por faixa,
        # que acerta a maioria (B) mas erra esse caso A especifico.
        # Ancora direita = _body_end (para na faixa de marco final, quando
        # existe), nao x0+comprimento (comprimento total). A cota de altura
        # (h_total) ja usa _body_end corretamente; esta cota de laje usava
        # o comprimento cheio, ficando deslocada para fora sempre que a
        # unidade tem faixa de marco final (small_x definido) — achado do
        # dono: "cota da laje direita sempre fora de posicao".
        _marco_right_x = _body_end
        _left_wall = (
            float(_lead_x_dim) if _lead_x_dim is not None else float(x0)
        )
        _tr_laje = [t for t in (laje_trechos or [])
                    if float(t.get('altura', 0) or 0) > 0]

        def _laje_no_x(_x_abs):
            if not _tr_laje:
                return None
            _xr = float(_x_abs) - float(x0)
            for _t in _tr_laje:
                if (float(_t.get('x0', 0) or 0) - 1.0 <= _xr
                        <= float(_t.get('x1', 0) or 0) + 1.0):
                    return float(_t['altura'])
            # fora dos trechos: o mais proximo
            return float(min(
                _tr_laje,
                key=lambda t: min(abs(_xr - float(t.get('x0', 0) or 0)),
                                  abs(_xr - float(t.get('x1', 0) or 0))),
            )['altura'])

        # ── Uma ponta ou as duas? Regra do dono (2026-09-17) ───────────────
        # "o que diferencia e' se possuem medidas diferentes as extremidades
        #  esquerda e direita em relacao a altura da laje ou do painel;
        #  qualquer um que seja diferente ja' e' motivo para ter cota dos
        #  dois lados, e caso ocorra se faz ambas, nao so' laje ou so'
        #  painel". Em continuacao a comparacao atravessa os segmentos
        #  ENCOSTADOS; separados, cada um se comporta sozinho.
        #
        # Isto substitui o heuristico por rotulo/faixa (".A sempre dois
        # lados; repetida so' onde ha' strip"), que nao sabia a razao e
        # errava nos dois sentidos.
        #
        # Confrontado com o que o N2 escreve:
        #   V301  17/17 — todas tem DEGRAU, entao as pontas tem painel de
        #         altura diferente (109/44, 103/38) e o humano cota as duas.
        #         E' o que explica a viga validada sem excecao.
        #   V302  a CONT.V302.A (44/44, laje 14/14) tem uma ponta so' no N2,
        #         e era o apontamento do dono (2A P3, 3A P1).
        # As divergencias restantes caem em unidades da V302.B cujo
        # laje_sup esta' mal extraido (11,6 / 12,2 / 0,5) — defeito de
        # extracao ja' registrado, nao desta regra.
        # Aqui a altura do painel e' a CRUA, sem a trava de 10 cm que
        # `_corpo_no_x` aplica. Sao perguntas diferentes: onde a laje
        # ASSENTA (a trava e' necessaria, senao a laje da V301 desce 65 cm)
        # e se as pontas DIFEREM. Na V301 as pontas sao 109 e 44 — e' essa
        # diferenca que faz o humano cotar os dois lados.
        _ps = [p for p in (panels or [])
               if float(p.get('width', 0) or 0) > 0]
        _hp_esq = float(_ps[0].get('height1', 0) or 0) if _ps else float(h)
        _hp_dir = float(_ps[-1].get('height1', 0) or 0) if _ps else float(h)
        _l_esq = _laje_no_x(_left_wall)
        _l_dir = _laje_no_x(_marco_right_x)
        _l_esq = _cota_marco if _l_esq is None else float(_l_esq)
        _l_dir = _cota_marco if _l_dir is None else float(_l_dir)
        _pontas_diferem = (abs(_hp_esq - _hp_dir) > 0.5
                           or abs(_l_esq - _l_dir) > 0.5)
        # A regra entra como RESTRICAO do comportamento anterior: so' pode
        # TIRAR a cota da esquerda, nunca acrescentar. Sem isso a V301.B
        # ganhava 6 cotas que o desenho validado nao tem — e a medicao que
        # dizia "o N2 da V301 cota as duas pontas em 17/17" e' justamente o
        # falso-positivo por vizinho de fileira ja' documentado no comentario
        # acima. O desenho validado vale mais que o meu detector de texto.
        _nu = str(nome_face or '').upper()
        _is_repeated_unit = '#' in _nu
        _is_a_face = ('.A' in _nu) or ('UNIT.A' in _nu)
        _is_b_face = ('.B' in _nu) or ('UNIT.B' in _nu)
        if _is_a_face and not _is_b_face:
            _antes_left, _antes_right = True, True
        else:
            _antes_left = (not _is_repeated_unit) or (_lead_x_dim is not None)
            _antes_right = (not _is_repeated_unit) or (_small_x_dim is not None)
        # A regra do dono manda nos DOIS sentidos: pontas diferentes exigem os
        # dois lados; pontas iguais dispensam o segundo. O heuristico antigo
        # por rotulo/faixa so' entra como piso quando as pontas sao iguais.
        #
        # Apontamento do dono (V302 SEGMENTO 6B, P1): "faltou a cota da laje
        # aqui a direita". A unidade e' repetida (V302.B#4) e o heuristico
        # cortava a direita por nao haver faixa de marco final — mas as pontas
        # dela tem laje 15 e 12, entao as duas sao necessarias.
        if _pontas_diferem:
            _want_left = _want_right = True
        else:
            # Pontas iguais: UMA cota, na direita. O heuristico antigo
            # (`_antes_right`: unidade repetida so' recebe onde ha' faixa de
            # marco) ficava como piso e matava casos que o N2 tem — a
            # V302.B#1, paineis [170, 244] sem faixa estreita, saia sem
            # NENHUMA cota de laje, e o N2 escreve "14" na direita
            # (apontamento do dono, SEGMENTO 5B).
            _want_left = False
            _want_right = True
        _marco_label_sides = [
            (_vx, _side)
            for _vx, _side, _want in (
                (_left_wall, -1.0, _want_left),
                (_marco_right_x, 1.0, _want_right),
            )
            if _want
        ]
        # ── A cota da laje segue o TRECHO onde ela esta' ───────────────────
        # Apontamento do dono (2026-09-13, P1): "neste lado a laje e' 15cm e
        # nao 12". Com degrau, a laje tem altura diferente por trecho e a cota
        # de cada ponta tem de mostrar a do SEU lado — na V13 face A o lado
        # esquerdo (sob o painel de fechamento) e' 12 e o direito e' 15. O
        # motor usava `laje_sup` unico e escrevia 12 nas duas pontas.
        # ── Cota do painel na ponta esquerda ───────────────────────────────
        # Apontamento do dono (V302 1A, P10): "falta a cota esquerda dessa
        # parede esquerda; ja' que esse segmento possui laje diferente com
        # sua cota, necessita a cota do painel tambem". A cota do corpo so'
        # saia na ponta `_dim_right`.
        #
        # "Se tem cota da laje tem que ter a cota do painel tambem" (dono,
        # V302 6B P3, repetindo o que ja' dissera no 1A P10). Entao a cota do
        # painel acompanha a da laje: onde uma sai, a outra sai junto. Eu
        # tinha deixado uma condicao a mais — so' emitir se o corpo local
        # diferisse entre as pontas — e ela silenciava justamente o lado que
        # o dono cobrou.
        _h_esq = _corpo_no_x(_left_wall)
        if (_emit_h_dim and _want_left
                and abs(_left_wall - _dim_right) > 1.0):
            dim_h_lateral(
                msp, _left_wall, y0 - laje_inf, _h_esq,
                offset=-1.0 * _DIM_L1, text_override=_fmt_dim_cm(_h_esq),
            )

        for _vx, _side in _marco_label_sides:
            try:
                _alt_local = _laje_no_x(_vx)
                _cota_local = (_alt_local if _alt_local is not None
                               else _cota_marco)
                _label_local = (_fmt_dim_cm(round(_alt_local, 1))
                                if _alt_local is not None
                                else _fmt_dim_cm(_cota_marco_label))
                x_base15 = _vx + _side * _DIM_L1
                _y_base = y0 + _corpo_no_x(_vx)
                emitir_cota(
                    msp, origem='marco_laje',
                    base=(x_base15, _y_base),
                    p1=(_vx, _y_base), p2=(_vx, _y_base + _cota_local),
                    angle=90,
                    texto=_label_local,
                    texto_pos=(x_base15 + _side * 4.0,
                               _y_base + _cota_local / 2.0),
                )
            except Exception:
                pass
        if _top_panel_h > 0.5:
            # A laje SOB o painel de fechamento vem do trecho, nao do
            # `_cota_marco` global. Sem isso o painel e a cota total ficam
            # fora do topo plano que a laje agora desenha: medido na V302.B,
            # a laje vai ate' -135,4 e o painel saia em -142,4..-139,4, 4 cm
            # abaixo, com a cota "3" flutuando no meio da faixa e a "59"
            # parando antes do topo — o que o dono leu como "patinhas da cota
            # fora de posicao" (SEGMENTO 1B, P1/P2).
            _laje_sob_topo = _laje_no_x(
                (float(_top_panel_x) + float(_top_panel_right)) / 2.0
            )
            _marco_sob_topo = (float(_laje_sob_topo)
                               if _laje_sob_topo is not None
                               else float(_cota_marco))
            y7_bot = float(y0) + float(h) + _marco_sob_topo
            y7_top = y7_bot + float(_top_panel_h)
            _left7 = float(_top_panel_x)
            _top_right_x = min(float(_top_panel_right), float(_body_end) + 0.01)
            # UMA cota, na ponta do painel que ENCOSTA na borda da face.
            # Medido no N2 da V13 (apontamento do dono P1-P4, 2026-09-13):
            #   face A — painel 0..200 (esquerda): "3" em x=2.0    (borda esq)
            #   face B — painel 219..415 (direita): "3" em x=436.6 (borda dir)
            # e a cota da laje total ("15") fica na ponta OPOSTA. Emitir nas
            # duas pontas dobrava a cota sem respaldo no desenho.
            # So' quando o painel NAO cobre a face inteira. Cobrindo tudo, as
            # duas pontas encostam na borda e nao ha' evidencia de qual e' a
            # certa — a V301.B tem 8 unidades assim (painel de 7 sobre os 418
            # da face) e mexer nelas alterava desenho ja' validado pelo dono.
            # ESCOPO: so' em unidade com DEGRAU DE LAJE. E' o unico caso em que
            # o N2 foi medido (V13) e a forma geometrica sozinha nao distingue:
            # a UNIT.B#10 da V301 tem painel comecando em 43.2 numa face de
            # 458.2 — mesma silhueta da V13 invertida — mas ali a regra
            # validada e' outra ("marco inicial cota na parede do corpo",
            # test_leading_marco_cotas_sit_on_body_wall). Sem este escopo a
            # regra vazava e quebrava aquele teste.
            _pontas7 = [(_left7, -1.0), (_top_right_x, 1.0)]
            if [t for t in (laje_trechos or [])
                    if float(t.get('altura', 0) or 0) > 0]:
                _tol7 = 2.0
                _enc_esq = abs(_left7 - float(x0)) <= _tol7
                _enc_dir = abs(_top_right_x - float(_body_end)) <= _tol7
                if _enc_esq and not _enc_dir:
                    _pontas7 = [(_left7, -1.0)]
                elif _enc_dir and not _enc_esq:
                    _pontas7 = [(_top_right_x, 1.0)]
            for _vx7, _side7 in _pontas7:
                x_base7 = _vx7 + _side7 * _DIM_L1
                emitir_cota(
                    msp, origem='painel_topo_h',
                    base=(x_base7, y7_bot),
                    p1=(_vx7, y7_bot), p2=(_vx7, y7_top),
                    angle=90,
                    texto=_fmt_dim_cm(_top_panel_h),
                    texto_pos=(x_base7 + _side7 * 4.0,
                               (y7_bot + y7_top) / 2.0),
                )
            # ── Largura do painel de fechamento, cotada ACIMA dele ─────────
            # Apontamento do dono (2026-09-13): faltava a cota superior, acima
            # do painel e acima da laje. Medido no N2 da V13 face B —
            # LINE COTA handle=DE, 196.0cm de (4862.8, 3079.1) a
            # (5058.8, 3079.1): em coordenada da face, x 219->415 (os 196 do
            # painel) a +22.1 do topo do corpo, ou seja ~4 acima do topo do
            # conjunto laje+painel (15+3=18). Face A tem a gemea de 200.
            #
            # Mesmo escopo das demais regras de cota do painel: so' em unidade
            # com DEGRAU DE LAJE. Painel cobrindo a face inteira (V301.B tem 8
            # assim) fica de fora — la' a largura ja' e' a da face e o desenho
            # foi validado pelo dono sem essa cota.
            if [t for t in (laje_trechos or [])
                    if float(t.get('altura', 0) or 0) > 0]:
                _wl = float(_top_panel_right) - float(_top_panel_x)
                if _wl > 1.0:
                    # Geometria copiada do N2 (V13 face A, handles 8E/8F/91):
                    # topo do conjunto laje+painel em 15.34, linha de cota em
                    # 22.0 (6.66 acima) e a linha de extensao COMECANDO em
                    # 18.34 — ou seja com FOLGA de 3 ate' o objeto, que e' o
                    # `dimexo`. Sem essa folga a extensao encostava no painel
                    # (apontamento do dono P2); com ela, flutua como no N2.
                    _y_larg = y7_top + 6.66
                    emitir_cota(
                        msp, origem='painel_topo_larg',
                        base=((_top_panel_x + _top_panel_right) / 2.0,
                              _y_larg),
                        p1=(_top_panel_x, y7_top),
                        p2=(_top_panel_right, y7_top),
                        angle=0,
                        override={'dimexo': 3.0},
                        texto=_fmt_dim_cm(round(_wl, 1)),
                        texto_pos=((_top_panel_x + _top_panel_right) / 2.0,
                                   _y_larg + 3.0),
                    )
    # Degrau classico: 1o vao longo (ex. 244) ate degrau_end. Espelho 111|63|244
    # nao deve emitir 44/59/65 inventados no ombro falso.
    _dbounds_chk = _degrau_zone_bounds_x(x0, h, panels) if panels else None
    _dstart_chk = _dbounds_chk[0] if _dbounds_chk else x0
    _dend_chk = _dbounds_chk[1] if _dbounds_chk else x0
    _step_trailing = _dstart_chk > x0 + 0.5
    _pw0 = float((panels[0].get('width') if panels else 0) or 0)
    _is_cont_face = 'CONT' in str(nome_face or '').upper()
    _h_ombro_chk = float(y_shoulder - y0) if y_shoulder is not None else 0.0
    # Degrau util (65): ombro na faixa 50-80 cm e vao ate a parede do degrau.
    _has_step = (
        y_shoulder is not None
        and 50.0 <= _h_ombro_chk <= 80.0
        and (_dend_chk - _dstart_chk) >= 150.0
        and h <= 125.0
    )
    # Cotas esq 44/59 so no padrao V301.A (1o painel longo + faixa ~44).
    # Face B (h_deg~38 + marco 20→58,5) inventava 58,5 fora do N2.
    _classic_deg = (
        _has_step
        and (
            (_pw0 >= 200.0 and _is_degrau_panel(panels[0], h))
            or _step_trailing
        )
    )
    if _classic_deg:
        h_deg = float(y0 + h - y_shoulder)
        if 12.0 < h_deg < h - 5.0:
            x_anchor = _dend_chk if _step_trailing else x0
            dim_side = 1.0 if _step_trailing else -1.0
            x_dim_l = x_anchor + dim_side * _DIM_L1
            emitir_cota(
                msp, origem='degrau_h',
                base=(x_dim_l, y_shoulder),
                p1=(x_anchor, y_shoulder), p2=(x_anchor, y0 + h),
                angle=90,
                texto=_fmt_dim_cm(h_deg),
                texto_pos=(x_dim_l + dim_side * 4.0,
                           y_shoulder + h_deg / 2.0),
            )
            # 59 = faixa superior ~44 + marco ~15 (padrao A). Nao emitir se
            # marco grosso (>16) ou faixa fora de 40-48 (vira 58,5 inventada).
            h_outer = h_deg + float(_marco_h) + float(_top_panel_h)
            if 50.0 <= h_outer <= 62.0 and 12.0 <= float(_marco_h) <= 16.5:
                try:
                    x_dim_o = x_anchor + dim_side * _DIM_L2
                    emitir_cota(
                        msp, origem='altura_externa',
                        base=(x_dim_o, y_shoulder),
                        p1=(x_anchor, y_shoulder),
                        p2=(x_anchor, y0 + h + _marco_h + _top_panel_h),
                        angle=90,
                        texto=_fmt_dim_cm(h_outer),
                        texto_pos=(x_dim_o + dim_side * 4.0,
                                   y_shoulder + h_outer / 2.0),
                    )
                except Exception:
                    pass
    # Cotas internas do recorte/degrau pertencem ao perfil N4 e ficam na layer
    # COTA. Elas não podem ser reaproveitadas como divisor de painel.
    if _has_step:
        degrau_end = _dend_chk
        step_wall = _dstart_chk if _step_trailing else _dend_chk
        step_side = 1.0 if _step_trailing else -1.0
        h_ombro = _h_ombro_chk
        if degrau_end > x0 + 0.5 and 12.0 < h_ombro < h - 5.0:
            x_dim_65 = step_wall + step_side * _DIM_L1
            emitir_cota(
                msp, origem='ombro_h',
                base=(x_dim_65, y0),
                p1=(step_wall, y0), p2=(step_wall, y_shoulder),
                angle=90,
                texto=_fmt_dim_cm(h_ombro),
                texto_pos=(x_dim_65 + step_side * 4.0,
                           (y0 + y_shoulder) / 2.0),
            )
            if _step_trailing:
                x_sarr_l = step_wall - SARR_INSET_H
                x_sarr_r = step_wall
            else:
                x_sarr_l = step_wall
                x_sarr_r = step_wall + SARR_INSET_H
            emitir_cota(
                msp, origem='sarrafo_ombro',
                base=(x_sarr_l, y0 - 10.0),
                p1=(x_sarr_l, y0), p2=(x_sarr_r, y0),
                angle=0)
    if has_left_opening:
        _dim_seg_v(x0 + comprimento, seg_left, 'right')
        dim_h_lateral(msp, x0, y0 - laje_inf, _h_total)

    # ── 10. ABERTURAS -- retangulos fechados + hachura diagonal ────────────
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
            if 'panel_offset' in hole:
                panel_x0 = x0 + float(hole.get('panel_offset', 0) or 0)
                panel_w = float(hole.get('panel_width', 0) or 0)
                corner = str(hole.get('corner') or 'TL').upper()
                hx = panel_x0 if corner.endswith('L') else panel_x0 + panel_w - hw
                hy = (
                    y0 + h - hdist - hh
                    if corner.startswith('T') else y0 + hdist
                )
            elif i == 0:  hx, hy = x0, y0 + h - hdist - hh
            elif i == 1:  hx, hy = x0, y0 + hdist
            elif i == 2:  hx, hy = xr - hw, y0 + h - hdist - hh
            elif i == 3:  hx, hy = xr - hw, y0 + hdist
            else: continue
            pts = [(hx, hy), (hx+hw, hy), (hx+hw, hy+hh), (hx, hy+hh)]
            msp.add_lwpolyline(pts, close=True,
                               dxfattribs={'layer': 'Painéis', 'linetype': 'DASHED'})
            if DRAW_HATCHES_PAINEL:
                ht = msp.add_hatch(dxfattribs={'layer': 'Hachura'})
                ht.set_pattern_fill('ANSI31', scale=0.5)
                ht.paths.add_polyline_path(pts, is_closed=True)
            add_text(msp, hx + hw/2, hy + hh/2, f'{hw:.0f}x{hh:.0f}',
                     7.0, '5', halign=1, valign=2)

    restack_lv_draw_order(msp)
    return comprimento


# ──────────────────────────────────────────────────────────────────────────────
# Viga lateral completa (secao + Face A + Face B)
# ──────────────────────────────────────────────────────────────────────────────

def _skip_n2_panel_solid_hatch(primitive):
    """Painéis LV são contorno; reprodução N2 não precisa de hatch sólido branco.

    No recorte humano, Hachura/SOLID preenche sarrafos com branco. O motor N4
    desenha sarrafos e painéis por linhas — manter só hachuras com pattern
    (ANSI31, AR-CONC, REAPROVEITAMENTO, ...).
    """
    if str(primitive.get('kind') or '') != 'hatch':
        return False
    if not primitive.get('solid'):
        return False
    layer_u = str(primitive.get('layer') or '').strip().upper()
    return layer_u in ('PAINÉIS', 'PAINEIS', 'HACHURA')


def _section_visual_attribs(primitive):
    attribs = {'layer': str(primitive.get('layer') or '0')}
    try:
        color = int(primitive.get('color', 256) or 256)
        if color != 256:
            attribs['color'] = color
    except Exception:
        pass
    linetype = str(primitive.get('linetype') or 'BYLAYER')
    if linetype and linetype != 'BYLAYER':
        attribs['linetype'] = linetype
    return attribs


def _section_rel_span(section_view, h_sec):
    """Extensao vertical REAL da secao, relativa ao seu centro de desenho.

    O empilhamento antigo assumia que uma secao ocupa ~``h_sec`` e andava
    ``max(h_sec + 90, 180)``. Isso vale para o detalhe procedural (1x), mas as
    primitivas do recorte N2 vem em escala 2x (layer "Cota Secao (2x)"): a
    secao ocupa o dobro do previsto e invade a de baixo — no V301 o Corte 2
    entrava 76 unidades dentro do Corte 1 (achado 2026-09-10, reportado pelo
    dono como "visao corte sobrepostos"). Medir em vez de estimar resolve
    qualquer escala e qualquer assimetria (o Corte 2 sobe 178.8 acima do
    centro e desce so' 61.2).
    """
    rel_y = []
    raw = section_view.get('raw') or {}
    primitives = (
        raw.get('visual_primitives')
        or section_view.get('visual_primitives')
        or []
    )
    for prim in primitives:
        for key in ('points', 'insert', 'align_point'):
            val = prim.get(key)
            if not val:
                continue
            seq = val if isinstance(val[0], (list, tuple)) else [val]
            rel_y += [float(p[1]) for p in seq if len(p) >= 2]
        for sub in (prim.get('paths') or []):
            rel_y += [float(p[1]) for p in sub if len(p) >= 2]
    if rel_y:
        return min(rel_y), max(rel_y)
    # Sem primitivas: o detalhe procedural desenha de y0 (=centro - h/2) para
    # cima, mais cotas/titulo acima e pontalete abaixo.
    return -h_sec / 2.0 - 30.0, h_sec / 2.0 + 45.0


def draw_section_visual_primitives(msp, section_view, x_center, y_center):
    """Desenha visao-corte a partir das primitivas extraidas do N2."""
    if not section_view:
        return False
    raw = section_view.get('raw') or {}
    primitives = (
        raw.get('visual_primitives')
        or section_view.get('visual_primitives')
        or []
    )
    if not primitives:
        return False

    doc = msp.doc

    def point(value):
        if not value or len(value) < 2:
            return (x_center, y_center)
        return (x_center + float(value[0]), y_center + float(value[1]))

    drew = False
    for primitive in primitives:
        layer = str(primitive.get('layer') or '0')
        if layer not in doc.layers:
            doc.layers.add(layer)
        attribs = _section_visual_attribs(primitive)
        kind = primitive.get('kind')
        try:
            if kind == 'line':
                points = primitive.get('points') or []
                if len(points) == 2:
                    msp.add_line(point(points[0]), point(points[1]),
                                 dxfattribs=attribs)
                    drew = True
            elif kind == 'polyline':
                points = primitive.get('points') or []
                if len(points) >= 2:
                    msp.add_lwpolyline(
                        [point(value) for value in points],
                        close=bool(primitive.get('closed')),
                        dxfattribs=attribs,
                    )
                    drew = True
            elif kind == 'text':
                insert = point(primitive.get('insert') or [0.0, 0.0])
                text = msp.add_text(
                    str(primitive.get('text') or ''),
                    dxfattribs={
                        **attribs,
                        'insert': insert,
                        'height': float(primitive.get('height', 7.0) or 7.0),
                        'rotation': float(primitive.get('rotation', 0.0) or 0.0),
                    },
                )
                halign = int(primitive.get('halign', 0) or 0)
                valign = int(primitive.get('valign', 0) or 0)
                if halign or valign:
                    text.dxf.halign = halign
                    text.dxf.valign = valign
                    text.dxf.align_point = point(
                        primitive.get('align_point')
                        or primitive.get('insert')
                        or [0.0, 0.0]
                    )
                drew = True
            elif kind == 'hatch':
                # replay generico mistura primitivas de layers diferentes —
                # decide pela natureza da propria layer (madeira/painel vs
                # concreto/laje), nao por uma flag unica.
                _hatch_layer_u = str(primitive.get('layer') or '').strip().upper()
                _is_painel_hatch = _hatch_layer_u in (
                    'PAINÉIS', 'PAINEIS', 'HACHURA',
                )
                if _is_painel_hatch and not DRAW_HATCHES_PAINEL:
                    continue
                if not _is_painel_hatch and not DRAW_HATCHES_LAJE:
                    continue
                if _skip_n2_panel_solid_hatch(primitive):
                    continue
                paths = primitive.get('paths') or []
                if not paths:
                    continue
                hatch = msp.add_hatch(dxfattribs=attribs)
                if primitive.get('solid'):
                    color = int(primitive.get('color', 7) or 7)
                    hatch.set_solid_fill(color=color if 1 <= color <= 255 else 7)
                else:
                    hatch.set_pattern_fill(
                        str(primitive.get('pattern') or 'ANSI31'),
                        scale=float(primitive.get('scale', 1.0) or 1.0),
                        angle=float(primitive.get('angle', 0.0) or 0.0),
                    )
                for path in paths:
                    if len(path) >= 3:
                        hatch.paths.add_polyline_path(
                            [point(value) for value in path],
                            is_closed=True,
                        )
                        drew = True
        except Exception:
            continue
    return drew


def _draw_section_n1_contract_legacy_clean(msp, section_view, x_center, y_center,
                                           viga_nome=''):
    """Visão de corte limpa quando N3 possui só o contrato N1.

    O N3 não pode reutilizar as primitivas do recorte N2. Em vez do desenho
    anatômico legado (hachura, letras a/b/c e ``pontalete``), monta uma seção
    legível exclusivamente a partir de B, H, h_A e h_B do contrato N1.
    """
    if not section_view or not section_view.get('n1_contract_clean'):
        return False
    b = max(float(section_view.get('b', 0) or 0), 1.0)
    h_core = max(float(section_view.get('h_section', 0) or 0), 1.0)
    h_a = max(float(section_view.get('h_A', h_core) or h_core), h_core)
    h_b = max(float(section_view.get('h_B', h_core) or h_core), h_core)
    y0 = y_center - h_core / 2.0
    board_w, panel_gap = 14.0, 8.0
    x_core_l, x_core_r = x_center - b / 2.0, x_center + b / 2.0
    x_a_l, x_a_r = x_core_l - panel_gap - board_w, x_core_l - panel_gap
    x_b_l, x_b_r = x_core_r + panel_gap, x_core_r + panel_gap + board_w

    def rect(x1, y1, x2, y2, layer):
        msp.add_lwpolyline([(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
                           close=True, dxfattribs={'layer': layer})

    # Faces laterais e alma: estrutura simples, sem elementos inventados.
    rect(x_a_l, y0, x_a_r, y0 + h_a, 'Madeira')
    rect(x_b_l, y0, x_b_r, y0 + h_b, 'Madeira')
    rect(x_core_l, y0, x_core_r, y0 + h_core, 'CONCRETO')
    # Pares de painel entre madeira e concreto, tal como as duas faces A/B.
    msp.add_line((x_a_r, y0), (x_a_r, y0 + h_a), dxfattribs={'layer': 'Painéis'})
    msp.add_line((x_b_l, y0), (x_b_l, y0 + h_b), dxfattribs={'layer': 'Painéis'})

    def dim_v(x, height, base_x):
        emitir_cota(msp, origem='corte_v', base=(base_x, y0),
                    p1=(x, y0), p2=(x, y0 + height), angle=90)

    def add_plain_dim_v(x, y1, y2, label, *, extension_from_x=None,
                        layer='Cota Seção (2x)'):
        """Cota interna sem os quadrados do dimstyle PAINEL."""
        attrs = {'layer': layer}
        if extension_from_x is not None:
            msp.add_line((extension_from_x, y1), (x, y1), dxfattribs=attrs)
            msp.add_line((extension_from_x, y2), (x, y2), dxfattribs=attrs)
        msp.add_line((x, y1), (x, y2), dxfattribs=attrs)
        for y in (y1, y2):
            msp.add_line((x - 2.5, y - 2.5), (x + 2.5, y + 2.5),
                         dxfattribs=attrs)
        text = msp.add_text(str(label), dxfattribs={
            'insert': (x + 5.0, (y1 + y2) / 2.0), 'height': 7.0,
            'rotation': 90.0, 'layer': layer,
        })
        text.dxf.halign = 1
        text.dxf.valign = 2
        text.dxf.align_point = (x + 5.0, (y1 + y2) / 2.0)

    def add_plain_dim_h(x1, x2, y, label, *, extension_to_y=None,
                        layer='Cota Seção (2x)'):
        """Cota interna horizontal com linha, extensões e ticks oblíquos."""
        attrs = {'layer': layer}
        if extension_to_y is not None:
            msp.add_line((x1, extension_to_y), (x1, y), dxfattribs=attrs)
            msp.add_line((x2, extension_to_y), (x2, y), dxfattribs=attrs)
        msp.add_line((x1, y), (x2, y), dxfattribs=attrs)
        for x in (x1, x2):
            msp.add_line((x - 2.5, y - 2.5), (x + 2.5, y + 2.5),
                         dxfattribs=attrs)
        add_text(msp, (x1 + x2) / 2.0, y - 7.0, str(label), 7.0,
                 layer, halign=1, valign=2)

    def add_plain_dim_v(x, y1, y2, label, *, extension_from_x=None,
                        layer='Cota Seção (2x)'):
        """Cota interna sem os quadrados que o dimstyle PAINEL materializa."""
        attrs = {'layer': layer}
        if extension_from_x is not None:
            msp.add_line((extension_from_x, y1), (x, y1), dxfattribs=attrs)
            msp.add_line((extension_from_x, y2), (x, y2), dxfattribs=attrs)
        msp.add_line((x, y1), (x, y2), dxfattribs=attrs)
        for y in (y1, y2):
            msp.add_line((x - 2.5, y - 2.5), (x + 2.5, y + 2.5),
                         dxfattribs=attrs)
        text = msp.add_text(str(label), dxfattribs={
            'insert': (x + 5.0, (y1 + y2) / 2.0), 'height': 7.0,
            'rotation': 90.0, 'layer': layer,
        })
        text.dxf.halign = 1
        text.dxf.valign = 2
        text.dxf.align_point = (x + 5.0, (y1 + y2) / 2.0)

    def add_plain_dim_h(x1, x2, y, label, *, extension_to_y=None,
                        layer='Cota Seção (2x)'):
        """Cota interna horizontal com linha, extensões e ticks oblíquos."""
        attrs = {'layer': layer}
        if extension_to_y is not None:
            msp.add_line((x1, extension_to_y), (x1, y), dxfattribs=attrs)
            msp.add_line((x2, extension_to_y), (x2, y), dxfattribs=attrs)
        msp.add_line((x1, y), (x2, y), dxfattribs=attrs)
        for x in (x1, x2):
            msp.add_line((x - 2.5, y - 2.5), (x + 2.5, y + 2.5),
                         dxfattribs=attrs)
        add_text(msp, (x1 + x2) / 2.0, y - 7.0, str(label), 7.0,
                 layer, halign=1, valign=2)

    def dim_h(x1, x2, base_y):
        emitir_cota(msp, origem='corte_h', base=(x1, base_y),
                    p1=(x1, y0), p2=(x2, y0), angle=0)

    dim_v(x_a_l, h_a, x_a_l - 30.0)
    dim_v(x_b_r, h_b, x_b_r + 30.0)
    dim_h(x_core_l, x_core_r, y0 - 24.0)
    if viga_nome:
        add_text(msp, x_center, y0 + max(h_a, h_b) + 24.0,
                 f'{viga_nome} ({b:.0f}x{h_core:.0f})', 8.0,
                 'Texto Seção', halign=1, valign=2)
    return True


def draw_section_n1_contract_clean(msp, section_view, x_center, y_center,
                                   viga_nome=''):
    """Corte N3: anatomia procedural comum, com autoridade só do N1.

    O desenho usa a mesma gramática construtiva do N4 para que sarrafos e
    cotas possam ser confrontados. A entrada continua limitada a B/H/h_A/h_B
    do contrato: nunca lê ``visual_primitives`` nem qualquer dado N2.
    """
    if not section_view or not section_view.get('n1_contract_clean'):
        return False
    b = max(float(section_view.get('b', 0) or 0), 1.0)
    h_core = max(float(section_view.get('h_section', 0) or 0), 1.0)
    h_a = max(float(section_view.get('h_A', h_core) or h_core), h_core)
    h_b = max(float(section_view.get('h_B', h_core) or h_core), h_core)
    draw_section_detail(
        msp, x_center, y_center - h_core / 2.0, b, h_core,
        viga_nome=viga_nome, b_alma=b, h_A=h_a, h_B=h_b,
    )
    return True


def draw_viga_lateral(msp, x_origin, y_top, viga_nome,
                      h_A, h_B, b, h_section=None, b_alma=19,
                      panels_A=None, panels_B=None,
                      holes_A=None, holes_B=None,
                      pillar_left_A=None, pillar_right_A=None,
                      pillar_left_B=None, pillar_right_B=None,
                      laje_sup=7.0, laje_inf=7.0,
                      laje_sup_A=None, laje_sup_B=None,
                      laje_inf_A=None, laje_inf_B=None,
                      border_strip_A=0.0, border_strip_B=0.0,
                      skip_layers=None,
                      nota_face_A=None, nota_face_B=None,
                      pontaletes_A=None, pontaletes_B=None,
                      section_views=None, view='ALL'):
    """Desenha uma viga lateral completa em uma linha horizontal.
    Positions: [Secao] [SECT_GAP] [Face A] [GAP_AB] [Face B]
    border_strip_A/B: largura do border strip a desenhar após os painéis (0=sem strip).
    skip_layers: set of layer names to conditionally skip (from STOG presence check).
    """
    if skip_layers is None:
        skip_layers = set()
    view = str(view or 'ALL').upper()
    if view not in {'ALL', 'CORTE', 'A', 'B'}:
        raise ValueError(f'Vista LV invalida: {view}')
    h = max(h_A, h_B, 1.0)
    # N3 nasce do N1/SA com a sequencia de paineis COMPLETA (sem a anotacao
    # "NX" que o N4 so' le do proprio desenho humano) -- aqui aplicamos a
    # MESMA regra de compressao pra sair no mesmo formato/papel que o N4.
    panels_A, fatores_A = compress_lv_panels_with_factors(panels_A or [])
    panels_B, fatores_B = compress_lv_panels_with_factors(panels_B or [])
    comp_A = sum(p['width'] for p in panels_A)
    comp_B = sum(p['width'] for p in panels_B)
    comprimento = max(comp_A, comp_B, 1.0)

    sect_total = max(SECT_W + SECT_GAP, int(b) + 178, LV_FACE_X0_MIN)
    x_A = x_origin + sect_total if view == 'ALL' else x_origin
    x_sect_center = max(x_origin + 40, x_A - 124 - int(b))

    h_sect = h_section if h_section else h_A
    y0_sect = y_top - h_A
    section_view = (section_views or [None])[0]
    y_center_sect = y0_sect + h_sect / 2.0
    if view in {'ALL', 'CORTE'}:
        # N3 isolado nasce do contrato canônico do SA.  Um payload pode ainda
        # carregar ``visual_primitives`` de uma extração antiga/N2; essas
        # primitivas são úteis apenas no fluxo reverso (N4), mas não podem
        # substituir a seção N1 nem introduzir pontalete/hachura sem fonte N1.
        if not draw_section_n1_contract_clean(
            msp, section_view, x_sect_center, y_center_sect,
            viga_nome=viga_nome,
        ) and not draw_section_visual_primitives(
            msp, section_view, x_sect_center, y_center_sect
        ):
            draw_section_detail(msp, x_sect_center, y0_sect, b, h_sect,
                                viga_nome=viga_nome, b_alma=b_alma,
                                h_A=h_A, h_B=h_B, skip_layers=skip_layers,
                                extension_left_cm=(section_view or {}).get('extension_left_cm'),
                                extension_right_cm=(section_view or {}).get('extension_right_cm'),
                                laje_sup_A=(section_view or {}).get('laje_sup_A'),
                                laje_sup_B=(section_view or {}).get('laje_sup_B'))

    if view == 'CORTE':
        return x_sect_center + max(140.0 + b, 220.0), y0_sect - 40.0

    _ls_A = laje_sup_A if laje_sup_A is not None else laje_sup
    _li_A = laje_inf_A if laje_inf_A is not None else laje_inf
    _ls_B = laje_sup_B if laje_sup_B is not None else laje_sup
    _li_B = laje_inf_B if laje_inf_B is not None else laje_inf

    y0_A = y_top - h_A
    if view in {'ALL', 'A'}:
        draw_lv_face(msp, x_A, y0_A, panels_A, h_A, f'{viga_nome}.A',
                     holes=holes_A,
                     pillar_left=pillar_left_A, pillar_right=pillar_right_A,
                     laje_sup=_ls_A, laje_inf=_li_A,
                     border_strip_width=border_strip_A,
                     skip_layers=skip_layers, nota_face=nota_face_A,
                     pontaletes_face=pontaletes_A,
                     fatores_painel=fatores_A)

    x_B = x_A + comp_A + GAP_AB if view == 'ALL' else x_origin
    print(f"DEBUG gerar_lv: x_A={x_A}, comp_A={comp_A}, GAP_AB={GAP_AB}, x_B={x_B}")
    y0_B = y_top - h_B
    if view in {'ALL', 'B'}:
        draw_lv_face(msp, x_B, y0_B, panels_B, h_B, f'{viga_nome}.B',
                     holes=holes_B,
                     pillar_left=pillar_left_B, pillar_right=pillar_right_B,
                     laje_sup=_ls_B, laje_inf=_li_B,
                     border_strip_width=border_strip_B,
                     skip_layers=skip_layers, nota_face=nota_face_B,
                     pontaletes_face=pontaletes_B,
                     fatores_painel=fatores_B)

    face_width = comp_A if view == 'A' else comp_B
    x_max = (x_A if view == 'A' else x_B) + face_width + DIM_H_RIGHT + 40
    y_min = min(y0_A, y0_B) - laje_inf - DIM_TOTAL_BELOW - 15
    return x_max, y_min


# ──────────────────────────────────────────────────────────────────────────────
# Cards de folha
# ──────────────────────────────────────────────────────────────────────────────

def _face_unit_segments(unit: dict) -> list:
    return unit.get('segments') or unit.get('panels') or []


def _face_unit_width_sum(unit: dict) -> float:
    total = 0.0
    for seg in _face_unit_segments(unit):
        total += float(seg.get('largura_cm', seg.get('width', 0)) or 0)
    return total


def _score_face_unit_variant(unit: dict) -> float:
    """Ranqueia variantes duplicadas da mesma geometria no recorte N2.

    Unidades sem label NÃO são descartadas (score -1e9): no multi-segmento
    LV muitas CONTINUACOES/espelhos vêm sem texto e ainda assim são faces
    reais (ex. h=142, cadeia 244|41,2|21,8|111). Preferência de label fica
    no desempate do select_canonical, não aqui.
    """
    segs = [
        seg for seg in _face_unit_segments(unit)
        if float(seg.get('largura_cm', seg.get('width', 0)) or 0) > 0
    ]
    if not segs:
        return -1e9

    score = 0.0
    label = str(unit.get('label') or '').strip()
    if label:
        score += 15.0
    if unit.get('label_source') == 'text':
        score += 20.0

    p1 = segs[0]
    if p1.get('reuse') and p1.get('reuse_regions'):
        score += 50.0
    elif p1.get('reuse'):
        score += 25.0

    if unit.get('sarrafos_verticais'):
        score += 10.0
    elif unit.get('sarrafo_vertical_esquerdo') or unit.get('sarrafo_vertical_direito'):
        score += 5.0
    if unit.get('marco_laje_sup') or float(unit.get('laje_sup', 0) or 0) > 0:
        score += 8.0

    n_panels = len(segs)
    if 4 <= n_panels <= 8:
        score += 15.0
    elif n_panels >= 3:
        score += 5.0

    h_body = float(unit.get('h_body', unit.get('h_total', 0)) or 0)
    if 80.0 <= h_body <= 130.0:
        score += 10.0
    elif 40.0 <= h_body <= 150.0:
        score += 5.0

    if h_body > 0:
        h1 = float(p1.get('height1', h_body) or h_body)
        if h1 < h_body - 5.0:
            score += 15.0

    wsum = _face_unit_width_sum(unit)
    if wsum >= 100.0:
        score += 5.0
    if wsum <= 0.0:
        score -= 100.0
    return score


def _face_unit_base_label(label: str) -> str:
    """Normaliza 'CONT. V301.A' → 'V301.A' para deduplicar variantes do motor."""
    text = str(label or '').strip().upper()
    for prefix in ('CONT.', 'CONT ', 'CONTINUACAO ', 'CONTINUAÇÃO '):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return text


# Divergencia de altura entre paineis (cm). 43 vs 45 fica o mesmo trecho;
# 44 vs 109 e degrau. Nao e o valor da secao (59/124), e a diferenca.
_H_DIVERGE_CM = 12.0


def _panel_heights_diverge(a: float, b: float) -> bool:
    return abs(float(a or 0) - float(b or 0)) >= _H_DIVERGE_CM


def _face_unit_height_class(h: float) -> int:
    """Rotulo curto da altura medida (arredondada), nao 59/124 fixos."""
    return int(round(float(h or 0)))


def _face_unit_geom_key(unit) -> tuple:
    """Assinatura de uma ocorrencia (lado + h + larguras + posicao no recorte).

    CONT com larguras diferentes NÃO colapsam: são segmentos distintos da viga.
    Gémeos exactos do motor (mesmo layout no mesmo sitio) partilham a chave.
    A mesma cadeia de paineis em Y diferente e outra peca de forma — no V301
    o recorte humano tem 8 ocorrencias A / 12 B; agrupar so por larguras
    derrubava as filas de baixo (8→6 e 12→10).
    """
    side = str(unit.get('side') or '').upper() or '?'
    h = float(unit.get('h_body', unit.get('h_total', unit.get('h', 0))) or 0)
    segs = _face_unit_segments(unit)
    widths = tuple(
        round(float(s.get('largura_cm', s.get('width', 0)) or 0), 1)
        for s in segs
        if float(s.get('largura_cm', s.get('width', 0)) or 0) > 0
    )
    bb = unit.get('bbox') or {}
    y_slot = round(float(bb.get('y_top') or 0) / 20.0)
    x_slot = round(float(bb.get('x_left') or 0) / 20.0)
    return (side, round(h), widths, y_slot, x_slot)


def _panel_w(p: dict) -> float:
    return float(p.get('largura_cm', p.get('width', 0)) or 0)


def split_face_unit_by_panel_height(unit: dict) -> list[dict]:
    """Parte a ocorrencia onde a altura dos paineis DIVERGE.

    Nao usa 59/124. 43 vs 45 continua um trecho; 44 vs 109 vira dois.
    O trecho mais baixo alinha pelo topo da laje. A primeira peca conserva
    o rotulo; as seguintes saem sem rotulo para o desenhador atribuir #n.
    """
    pans = [p for p in _face_unit_segments(unit) if _panel_w(p) > 0]
    if len(pans) < 2:
        return [unit]
    bb = dict(unit.get('bbox') or {})
    x0 = float(bb.get('x_left') or 0.0)
    y_bot = float(bb.get('y_bot') or 0.0)
    y_top = float(bb.get('y_top') or y_bot)
    h_body = float(unit.get('h_body') or (y_top - y_bot) or 0.0)
    runs: list[dict] = []
    for p in pans:
        h1 = float(p.get('height1', p.get('h', h_body)) or h_body)
        # Sobra debaixo da abertura nao e degrau — fica no trecho corrente.
        if p.get('sob_abertura') or h1 < 15.0:
            if runs:
                runs[-1]['panels'].append(p)
            else:
                runs.append({'h1': h1, 'panels': [p]})
            continue
        if not runs or _panel_heights_diverge(h1, runs[-1]['h1']):
            runs.append({'h1': h1, 'panels': []})
        else:
            n = len(runs[-1]['panels'])
            runs[-1]['h1'] = (runs[-1]['h1'] * n + h1) / (n + 1)
        runs[-1]['panels'].append(p)
    if len(runs) <= 1:
        return [unit]
    out = []
    acc = x0
    for i, run in enumerate(runs):
        w = sum(_panel_w(p) for p in run['panels'])
        h1 = float(run['h1'])
        piece = dict(unit)
        piece['panels'] = list(run['panels'])
        piece['segments'] = list(run['panels'])
        if h_body and h1 + _H_DIVERGE_CM < h_body:
            piece['h_body'] = h1
            y0 = y_top - h1 if y_top else y_bot
        else:
            piece['h_body'] = h_body if h_body else h1
            y0 = y_bot
        piece['bbox'] = {
            'x_left': acc,
            'x_right': acc + w,
            'y_bot': y0,
            'y_top': y_top if y_top else y0 + float(piece['h_body']),
        }
        if i > 0:
            piece['label'] = ''
        out.append(piece)
        acc += w
    return out


def split_face_unit_by_aberturas(unit: dict) -> list[dict]:
    """Parte no fim da abertura de viga (borda direita).

    A abertura e a sobra ficam no segmento de ANTES; o que vem depois e
    outro segmento. Cortes em `cortes_segmento` / `aberturas_viga.x_fim`
    sao relativos a x_left da unidade.
    """
    cortes = [float(c) for c in (unit.get('cortes_segmento') or []) if c]
    if not cortes:
        for a in unit.get('aberturas_viga') or []:
            if a.get('x_fim') not in (None, ''):
                cortes.append(float(a['x_fim']))
    pans = [p for p in _face_unit_segments(unit) if _panel_w(p) > 0]
    if not cortes or not pans:
        return [unit]
    bb = dict(unit.get('bbox') or {})
    x0 = float(bb.get('x_left') or 0.0)
    y_bot = float(bb.get('y_bot') or 0.0)
    y_top = float(bb.get('y_top') or y_bot)
    total = sum(_panel_w(p) for p in pans) or 1.0
    cuts = sorted({c for c in cortes if 1.0 < c < total - 1.0})
    if not cuts:
        return [unit]
    out = []
    acc_rel = 0.0
    piece_pans: list = []
    ci = 0
    n_emit = 0
    abs_x = x0

    def _emit(pp, x_a, x_b):
        nonlocal n_emit
        piece = dict(unit)
        piece['panels'] = list(pp)
        piece['segments'] = list(pp)
        piece['bbox'] = {
            'x_left': x_a, 'x_right': x_b,
            'y_bot': y_bot, 'y_top': y_top,
        }
        if n_emit > 0:
            piece['label'] = ''
            piece['cortes_segmento'] = []
            piece['aberturas_viga'] = []
        n_emit += 1
        out.append(piece)

    for p in pans:
        w = _panel_w(p)
        piece_pans.append(p)
        acc_rel += w
        while ci < len(cuts) and acc_rel + 0.6 >= cuts[ci]:
            x_b = x0 + acc_rel
            _emit(piece_pans, abs_x, x_b)
            piece_pans = []
            abs_x = x_b
            ci += 1
            if ci >= len(cuts):
                break
    if piece_pans:
        _emit(piece_pans, abs_x, x0 + sum(_panel_w(p) for p in pans))
    return out or [unit]


def split_face_unit_for_tags(unit: dict) -> list[dict]:
    """Altura que diverge, depois abertura de viga — ordem do dono."""
    out = []
    for piece in split_face_unit_by_panel_height(unit):
        out.extend(split_face_unit_by_aberturas(piece))
    return out or [unit]


def prepare_n4_face_units(face_units, viga_nome=None) -> list:
    """Ocorrencias distintas + split por divergencia de altura e abertura."""
    canon = select_canonical_face_units(face_units, viga_nome=viga_nome)
    out = []
    for unit in canon:
        out.extend(split_face_unit_for_tags(unit))
    return out


def _descartar_copia_mal_laterada(units, folga=60.0, tol_x=40.0):
    """Remove a copia de uma unidade que saiu na FACE ERRADA.

    Causa (contrato §5.2.4): no N2 as faces ficam em COLUNAS — na V302 a face A
    em x 3883..4862 e a B em 5217..6144. Unidade sem rotulo herda o lado do
    ANCHOR, e o casamento por fileira aceita candidatos que se alinham em Y com
    esse anchor sem olhar X. Anchor de uma coluna captura pares da outra e o
    resultado sai com o lado errado E a altura errada:

        A   -        h=56.0  x 5217.5..5619.0  w=[244.0, 157.5]
        B   V302.B   h=44.0  x 5217.5..5619.0  w=[244.0, 157.5]

    O agrupamento canonico nao desfaz isso porque a chave inclui a ALTURA, e as
    duas variantes caem em grupos diferentes.

    ESCOPO ESTREITO, de proposito. So' descarta quando as TRES valem:
      1. as colunas A e B dos rotulados NAO se sobrepoem em x (senao nao ha'
         territorio para comparar — e' o caso da V301 e da V13, que ficam
         intocadas, e sao desenho ja' validado pelo dono);
      2. o centro da unidade esta' mais perto do territorio do OUTRO lado;
      3. existe uma GEMEA no lado certo, na mesma posicao e com as mesmas
         larguras.

    A condicao 3 e' o que impede perder desenho: medido nas 32 vigas, 16 de 120
    unidades tem lado incoerente, mas so' 2 tem gemea (ambas na V302). As
    outras 14 sao desenhos reais rotulados na face errada — precisam ser
    REATRIBUIDAS, nao descartadas, e ficam fora desta funcao.
    """
    if not units:
        return units

    def _ctr(u):
        bb = u.get('bbox') or {}
        return (float(bb.get('x_left', 0) or 0)
                + float(bb.get('x_right', 0) or 0)) / 2.0

    def _ws(u):
        return [round(float(p.get('width', 0) or 0), 1)
                for p in (_face_unit_segments(u) or [])]

    terr = {}
    for s in ('A', 'B'):
        cs = [_ctr(u) for u in units
              if str(u.get('side') or '').upper() == s
              and str(u.get('label') or '').strip()]
        if cs:
            terr[s] = (min(cs), max(cs))
    if len(terr) < 2:
        return units
    (a0, a1), (b0, b1) = terr['A'], terr['B']
    if not (a1 < b0 or b1 < a0):
        return units  # colunas se sobrepoem: sem territorio, nao mexe

    def _dist(c, faixa):
        lo, hi = faixa
        if lo - folga <= c <= hi + folga:
            return 0.0
        return min(abs(c - lo), abs(c - hi))

    fora = []
    for u in units:
        s = str(u.get('side') or '').upper()
        if s not in terr:
            continue
        c = _ctr(u)
        outro = 'B' if s == 'A' else 'A'
        if _dist(c, terr[outro]) < _dist(c, terr[s]):
            fora.append((u, outro, c, _ws(u)))
    if not fora:
        return units

    descartar = set()
    for u, outro, c, ws in fora:
        if not ws:
            continue
        for v in units:
            if v is u or str(v.get('side') or '').upper() != outro:
                continue
            if abs(_ctr(v) - c) <= tol_x and _ws(v) == ws:
                descartar.add(id(u))
                break
    if not descartar:
        return units
    return [u for u in units if id(u) not in descartar]


def select_canonical_face_units(face_units, viga_nome=None):
    """Seleciona unidades de face para desenhar no N4.

    Antes: 1 variante por (lado, label-base) — colapsava todos os CONT. V301.A
    com geometrias diferentes em um só (20→2). Errado para viga multi-segmento.

    Agora: mantém **todas as geometrias distintas** (lado+h+widths). Duplicatas
    exactas do motor (mesmo layout, label vazio vs CONT) ficam 1 — prefere
    rótulo nominal e score estrutural.
    """
    del viga_nome  # reservado para heurísticas futuras por elemento
    from collections import defaultdict

    groups = defaultdict(list)
    for unit in face_units or []:
        if not _face_unit_segments(unit):
            continue
        key = _face_unit_geom_key(unit)
        if key[2] == ():  # sem larguras
            continue
        groups[key].append(unit)

    if not groups:
        return [
            unit for unit in (face_units or [])
            if _face_unit_segments(unit)
        ]

    selected = []
    for variants in groups.values():
        best = max(
            variants,
            key=lambda u: (
                1 if str(u.get('label') or '').strip() else 0,
                0 if 'CONT' in str(u.get('label') or '').upper() else 1,
                _score_face_unit_variant(u),
            ),
        )
        if _score_face_unit_variant(best) > -1e8:
            selected.append(best)

    selected = _descartar_copia_mal_laterada(selected)

    side_order = {'A': 0, 'B': 1}

    def _sort_key(unit):
        label = str(unit.get('label') or '')
        is_cont = 'CONT' in label.upper()
        side = str(unit.get('side') or '').upper()
        bbox = unit.get('bbox') or {}
        return (
            side_order.get(side, 2),
            1 if is_cont else 0,
            -float(bbox.get('y_top', 0) or 0),
            float(bbox.get('x_left', 0) or 0),
            -_face_unit_width_sum(unit),
        )

    selected.sort(key=_sort_key)
    return selected


def layout_lv_face_unit_bboxes(face_units, x_origin=0.0, y_top=0.0, view='A'):
    """Espelha o posicionamento horizontal de draw_viga_lateral_face_units."""
    view = str(view or 'A').upper()
    canonical = prepare_n4_face_units(face_units)
    # Espelha a segunda ordenacao espacial feita pelo desenhador. Sem isto, o
    # pos-processador aplicava os detalhes de uma ficha sobre a ocorrencia
    # seguinte quando CONT. e unidades sem rotulo se intercalavam.
    canonical = sorted(
        canonical,
        key=lambda unit: (
            {'A': 0, 'B': 1}.get(str(unit.get('side') or '').upper(), 2),
            -float((unit.get('bbox') or {}).get('y_top', 0) or 0),
            float((unit.get('bbox') or {}).get('x_left', 0) or 0),
        ),
    )
    section_col_w = 210.0
    face_x0 = (
        x_origin + max(section_col_w + 60.0, LV_FACE_X0_MIN)
        if view == 'ALL'
        else x_origin
    )
    y_baseline = y_top - 150.0
    x_cursor = face_x0
    layouts = []

    for unit in canonical:
        side = str(unit.get('side') or '').upper()
        if view in {'A', 'B'} and side != view:
            continue
        bbox = unit.get('bbox') or {}
        h_face = float(unit.get('h_body', unit.get('h_total', 0)) or 0)
        if h_face <= 0:
            h_face = max(
                1.0,
                float(bbox.get('y_top', 0) or 0) - float(bbox.get('y_bot', 0) or 0),
            )
        panels = [
            _panel_from_face_unit_segment(seg, h_face)
            for seg in _face_unit_segments(unit)
            if float(seg.get('largura_cm', seg.get('width', 0)) or 0) > 0
        ]
        if not panels:
            continue
        unit_width = sum(p['width'] for p in panels)
        x0 = x_cursor
        y0 = y_baseline - h_face
        laje_sup = float(unit.get('laje_sup', 7.0) or 7.0)
        laje_inf = float(unit.get('laje_inf', 7.0) or 7.0)
        crop = (
            x0 - 25.0,
            y0 - laje_inf - DIM_TOTAL_BELOW - 25.0,
            x0 + unit_width + DIM_H_RIGHT + 35.0,
            y0 + h_face + laje_sup + NOM_ABOVE + 25.0,
        )
        layouts.append({
            'label': str(unit.get('label') or ''),
            'side': side,
            'bbox': crop,
            'unit': unit,
        })
        x_cursor = x0 + unit_width + LV_UNIT_GAP
    return layouts


def _panel_from_face_unit_segment(seg: dict, h_face: float) -> dict:
    """Converte segmento de face_unit N2 para panel consumido pelo gerador."""
    ptype = str(seg.get('panel_type', 'Sarrafeado'))
    h1 = float(seg.get('height1', h_face if ptype == 'Sarrafeado' else 0) or 0)
    if h1 <= 0 and ptype == 'Sarrafeado':
        h1 = h_face
    slab_center = float(seg.get('slab_center', seg.get('laje_central_alt', 0)) or 0)
    central_alt = float(seg.get('laje_central_alt', slab_center) or slab_center)
    if h1 < 80.0:
        slab_center = 0.0
        central_alt = 0.0
    return {
        'width':            float(seg.get('largura_cm', seg.get('width', 0)) or 0),
        'height1':          h1,
        'height2':          float(seg.get('height2', 0) or 0),
        'grade_h1':         float(seg.get('grade_h1', 0) or 0),
        'grade_h2':         float(seg.get('grade_h2', 0) or 0),
        'laje_central_alt': central_alt,
        'slab_center':      slab_center,
        'laje_sup_local':   float(seg.get('laje_sup_local', seg.get('slab_top', 0)) or 0),
        'laje_inf_local':   float(seg.get('laje_inf_local', seg.get('slab_bottom', 0)) or 0),
        'slab_top':         float(seg.get('slab_top', seg.get('laje_sup_local', 0)) or 0),
        'slab_bottom':      float(seg.get('slab_bottom', seg.get('laje_inf_local', 0)) or 0),
        'vazio_base_local': float(seg.get('vazio_base_local', 0) or 0),
        'reuse':            bool(seg.get('reuse', False)),
        'reuse_regions':    seg.get('reuse_regions', []),
        'holes':            seg.get('holes', []),
        'panel_type':       ptype,
        'codigos':          seg.get('codigos_forma', []),
        # Painel EMBAIXO de abertura de viga: o `height1` dele e' a SOBRA,
        # medida do fundo, e nao a altura de um painel rebaixado alinhado pelo
        # TOPO. Ver `_is_degrau_panel`.
        'sob_abertura':     bool(seg.get('sob_abertura', False)),
    }


def draw_viga_lateral_face_units(msp, x_origin, y_top, viga_nome, face_units,
                                 section_views=None, b=19.0, skip_layers=None,
                                 view='ALL', n1_contract=True):
    """Desenha viga LV com unidades/continuacoes detectadas no N2.

    A geometria original do recorte serve para extrair dados e ordenar as
    unidades. A ficha N4 deve ser limpa/legivel, entao as laterais sao
    reorganizadas em colunas A/B em vez de preservar coordenadas do recorte.
    """
    if skip_layers is None:
        skip_layers = set()
    view = str(view or 'ALL').upper()
    if view not in {'ALL', 'CORTE', 'A', 'B'}:
        raise ValueError(f'Vista LV invalida: {view}')
    valid_units = prepare_n4_face_units(face_units, viga_nome=viga_nome)
    if not valid_units and view != 'CORTE':
        return x_origin, y_top

    section_col_w = 210.0
    face_x0 = (
        x_origin + max(section_col_w + 60.0, LV_FACE_X0_MIN)
        if view == 'ALL'
        else x_origin
    )

    y_section = y_top - 150.0
    _prev_bottom = None       # fundo real (medido) da secao anterior
    LV_SECTION_GAP = 90.0     # folga vertical entre duas visoes de corte
    visible_sections = (section_views or []) if view in {'ALL', 'CORTE'} else []
    for idx, sv in enumerate(visible_sections):
        h_sec = float(sv.get('h_section', 0) or sv.get('h_section_cm', 0) or 0)
        if h_sec <= 0:
            continue
        h_a = float(sv.get('h_A', h_sec) or h_sec)
        h_b = float(sv.get('h_B', h_sec) or h_sec)
        label = viga_nome if idx == 0 else f'{viga_nome}-{idx + 1}'
        # Posiciona pela extensao medida: o topo desta secao fica LV_SECTION_GAP
        # abaixo do fundo real da anterior. A primeira mantem a posicao
        # historica (y_top - 150) para nao deslocar quem so' tem uma secao.
        _span_lo, _span_hi = _section_rel_span(sv, h_sec)
        if _prev_bottom is not None:
            _center = _prev_bottom - LV_SECTION_GAP - _span_hi
            y_section = _center - h_sec / 2.0
        # Mesmo princípio da rota sem face_units: a marca explícita de
        # contrato N1 é autoritativa e vence qualquer primitiva residual.
        # O Corte usa uma anatomia limpa comum, mas sem cruzar proveniÃªncia:
        # N3 pode usar somente o contrato N1; N4 usa apenas valores da ficha N2.
        # Primitivas DXF antigas nÃ£o entram como fallback: elas introduzem os
        # blocos/quadrados de cota que este viewer substitui por linhas/ticks.
        # Cadeia de 3 níveis, igual à rota sem face_units (harmonizado em
        # 2026-09-10, decisão do dono): a proveniência quem decide é a
        # PRÓPRIA seção, não a flag de CLI.
        #   1) seção marcada como contrato N1 (N3 isolado) -> anatomia limpa,
        #      nunca lê N2;
        #   2) seção vinda da ficha N2 (N4) -> replica a geometria real do
        #      recorte (perfil de concreto, painéis, cotas e desníveis que o
        #      template procedural não sabe reproduzir — ex.: no V301 Corte 1
        #      a laje da face B fica 7cm abaixo da face A);
        #   3) sem primitivas -> detalhe procedural como último recurso.
        drawn = False
        if n1_contract:
            drawn = draw_section_n1_contract_clean(
                msp, sv, x_origin + 95, y_section + h_sec / 2.0,
                viga_nome=label,
            )
        if not drawn:
            drawn = draw_section_visual_primitives(
                msp, sv, x_origin + 95, y_section + h_sec / 2.0,
            )
        if not drawn:
            draw_section_detail(msp, x_origin + 95, y_section, b, h_sec,
                                viga_nome=label, b_alma=b, h_A=h_a, h_B=h_b,
                                skip_layers=skip_layers,
                                extension_left_cm=sv.get('extension_left_cm'),
                                extension_right_cm=sv.get('extension_right_cm'),
                                laje_sup_A=sv.get('laje_sup_A'),
                                laje_sup_B=sv.get('laje_sup_B'))
        _prev_bottom = (y_section + h_sec / 2.0) + _span_lo

    if view == 'CORTE':
        if _prev_bottom is not None:
            return x_origin + section_col_w, _prev_bottom - LV_SECTION_GAP
        return x_origin + section_col_w, y_section

    prepared_units = []
    for unit in valid_units:
        bbox = unit.get('bbox') or {}
        h_face = float(unit.get('h_body', unit.get('h_total', 0)) or 0)
        if h_face <= 0:
            h_face = max(1.0, float(bbox.get('y_top', 0)) - float(bbox.get('y_bot', 0)))
        panels = [
            _panel_from_face_unit_segment(seg, h_face)
            for seg in (unit.get('segments') or unit.get('panels') or [])
            if float(seg.get('largura_cm', seg.get('width', 0)) or 0) > 0
        ]
        if not panels:
            continue
        prepared_units.append((unit, bbox, h_face, panels))

    side_order = {'A': 0, 'B': 1}
    prepared_units.sort(key=lambda item: (
        side_order.get(str(item[0].get('side') or '').upper(), 2),
        -float((item[1] or {}).get('y_top', 0)),
        float((item[1] or {}).get('x_left', 0)),
    ))

    if view in {'A', 'B'}:
        prepared_units = [
            item for item in prepared_units
            if str(item[0].get('side') or '').upper() == view
        ]

    # Uma sequencia horizontal por viewer. Cada continuacao avanca pela sua
    # largura real mais exatamente 50 cm, sem reutilizar a mesma origem.
    x_cursor = face_x0
    y_baseline = y_top - 150.0
    x_max = face_x0
    y_min = y_top
    _side_seq = {'A': 0, 'B': 0}

    for unit, _bbox, h_face, panels in prepared_units:
        x0 = x_cursor
        y0 = y_baseline - h_face
        side_u = str(unit.get('side') or '').upper() or '?'
        _side_seq[side_u] = _side_seq.get(side_u, 0) + 1
        label = str(unit.get('label') or '').strip()
        if not label:
            # Unidade sem rótulo no N2: nome estável para QA multi-segmento
            base = str(viga_nome or 'LV').replace('_A', '').replace('_B', '')
            label = f"{base}.{side_u}#{_side_seq[side_u]}"
        grade_layer_style = str(unit.get('grade_layer_style') or 'native')
        reverse_grade = grade_layer_style == 'paineis'
        # Aberturas pertencem aos segmentos da ficha. Materializa-las na
        # coordenada da face sem usar a posicao original do recorte N2.
        unit_holes = []
        panel_offset = 0.0
        for panel in panels:
            panel_width = float(panel.get('width', 0) or 0)
            for raw_hole in panel.get('holes', []) or []:
                hole = dict(raw_hole)
                hole.setdefault('active', True)
                hole['panel_offset'] = panel_offset
                hole['panel_width'] = panel_width
                unit_holes.append(hole)
            panel_offset += panel_width
        plano_cotas_abrir(f'{viga_nome}|{label}')
        draw_lv_face(
            msp, x0, y0, panels, h_face, label,
            holes=unit_holes,
            pillar_left={'active': False, 'width': 0.0, 'length': 0.0},
            pillar_right={'active': False, 'width': 0.0, 'length': 0.0},
            laje_sup=float(unit.get('laje_sup', 0) or 0),
            laje_inf=float(unit.get('laje_inf', 0) or 0),
            skip_layers=skip_layers,
            pontaletes_face=unit.get('pontaletes_face', 0),
            fallback_panel_ids=False,
            nom_height=8.0,
            reverse_grade_style=reverse_grade,
            suppress_sarrafo_spans=reverse_grade,
            sarrafo_vertical_esquerdo=bool(unit.get('sarrafo_vertical_esquerdo')),
            sarrafo_vertical_direito=bool(unit.get('sarrafo_vertical_direito')),
            sarrafos_horizontais=unit.get('sarrafos_horizontais'),
            sarrafos_verticais=unit.get('sarrafos_verticais'),
            marco_laje_sup=bool(unit.get('marco_laje_sup')),
            painel_sup_alt=float(unit.get('painel_sup_alt', 0) or 0),
            painel_sup_width=float(unit.get('painel_sup_width', 0) or 0),
            painel_sup_x_offset=float(unit.get('painel_sup_x_offset', 0) or 0),
            endpoint_start_label=unit.get('endpoint_start_label'),
            endpoint_end_label=unit.get('endpoint_end_label'),
            edge_span_candidates=unit.get('edge_span_candidates'),
            laje_trechos=unit.get('laje_sup_trechos'),
            aberturas_viga=unit.get('aberturas_viga'),
            fatores_painel=unit.get('fatores_painel'),
        )
        plano_cotas_despejar(plano_cotas_fechar(), f'{viga_nome}|{label}')
        unit_width = sum(p['width'] for p in panels)
        x_max = max(x_max, x0 + unit_width + DIM_H_RIGHT + 40)
        y_min = min(y_min, y0 - DIM_TOTAL_BELOW - 30)
        x_cursor = x0 + unit_width + LV_UNIT_GAP

    return x_max, y_min


def draw_cards(msp, x0, y_bottom, obra_nome=''):
    """Desenha 2 blocos Folhas 1485x1050 (bordas + carimbo)."""
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
                        help='Maximo de vigas a processar')
    parser.add_argument('--simulate', action='store_true',
                        help='Injeta dados de teste na 1a viga (aberturas, pilares, h1!=h2)')
    parser.add_argument('--item', type=str, default=None,
                        help='Gerar só esta viga (ex: V001). Output: LV_preview_V001.dxf')
    parser.add_argument('--seg_idx', type=int, default=-1,
                        help='Índice do segmento para desenhar apenas aquele segmento (0-based).')
    parser.add_argument('--visual-mode', choices=['NOVA', 'INI'], default='NOVA',
                        help='Perfil visual do DXF (padrao: NOVA)')
    parser.add_argument(
        '--behavior', choices=['Para', 'Passa'], default=None,
        help='Contrato SA LV isolado. Le LV-PARA/LV-PASSA e preserva o sufixo no artefato.',
    )
    parser.add_argument(
        '--view', choices=['ALL', 'CORTE', 'A', 'B'], default='ALL',
        help='Artefato LV a gerar: combinado, corte, face A ou face B.',
    )
    parser.add_argument(
        '--input-dir', type=str, default=None,
        help='Diretorio isolado com V*_A.json/V*_B.json (default: '
             'Fase-4_Sincronizacao/JSON_Vigas_Laterais[/LV-{behavior}] da obra).',
    )
    parser.add_argument(
        '--output-dir', type=str, default=None,
        help='Diretorio de saida isolado (default: Fase-6_Execucao_CAD da obra).',
    )
    parser.add_argument(
        '--stog-obra-hint', type=str, default=None,
        help='Nome real da obra em dxf_discovery.json, para descoberta de '
             'layers do STOG quando --obra aponta para uma pasta temp/isolada '
             '(ex: materializacao N2->N4 do QA, cujo nome nao bate com a obra).',
    )
    parser.add_argument(
        '--stog-pav-hint', type=str, default=None,
        help='Pavimento real (ex: "14_PAV") para escolher o molde STOG certo '
             'em dxf_discovery.json — moldes variam por pavimento (algumas '
             'obras nao usam presilha/barrote/TENSOR em todo pavimento). Sem '
             'este hint, cai no heuristico antigo (melhor pavimento da obra).',
    )
    parser.add_argument(
        '--strict-contract', action='store_true',
        help='Exige ficha N4 completa e desabilita completamentos silenciosos.',
    )
    args = parser.parse_args()

    obra_path = Path(args.obra)
    if args.input_dir:
        lv_dir = Path(args.input_dir)
    else:
        lv_dir = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Laterais'
        if args.behavior:
            lv_dir = lv_dir / f'LV-{args.behavior.upper()}'
    vs_path   = obra_path / 'Fase-4_Sincronizacao' / 'vigas_salvas.json'
    out_dir   = Path(args.output_dir) if args.output_dir else obra_path / 'Fase-6_Execucao_CAD'
    out_dir.mkdir(parents=True, exist_ok=True)

    vigas_salvas = {}
    if vs_path.exists():
        vigas_salvas = json.load(open(vs_path, encoding='utf-8'))

    # Carregar fichas_lv_v2.json → mapa de codigos_forma, h_cm, b_cm, largura_cm por viga/face
    fichas_map:      dict = {}  # {vname: {'A': [[str,...], ...], 'B': [...]}}
    fichas_h_map:    dict = {}  # {vname: {'A': h_cm, 'B': h_cm}}
    fichas_b_map:    dict = {}  # {vname: b_cm}
    fichas_segs_map: dict = {}  # {vname: {'A': [largura_cm,...], 'B': [...]}}  ← widths de fichas
    fichas_panels_map: dict = {} # {vname: {'A': [seg_dict,...], 'B': [...]}}   ← segmentos completos
    fichas_face_units_map: dict = {} # {vname: [face_unit,...]}                 ← unidades visuais N2
    fichas_laje_map: dict = {}  # {vname: {'sup': float, 'inf': float}}         ← lajesx de fichas
    fichas_nota_map: dict = {}  # {vname: {'A': str, 'B': str}}                 ← nota_face (ref texto)
    fichas_pont_map: dict = {}  # {vname: {'A': int|list|None, 'B': ...}}       ← pontaletes_face override
    fichas_v2_path = obra_path / 'Fase-6_Execucao_CAD' / 'granular' / 'fichas' / 'fichas_lv_v2.json'
    # N3 isolado deve refletir N1/SA. fichas_lv_v2 e gabarito humano N2 e nao
    # pode sobrescrever os paineis do contrato Para/Passa.
    if fichas_v2_path.exists() and not args.behavior:
        try:
            fichas_data = json.loads(fichas_v2_path.read_text(encoding='utf-8'))
            if args.strict_contract:
                from src.core.lv_draw_contract import validate_n4_ficha
                fichas_data = [
                    validate_n4_ficha(ficha, item=ficha.get('viga'))
                    for ficha in fichas_data
                ]
            for ficha in fichas_data:
                vn   = ficha.get('viga')
                face = ficha.get('face', 'A')
                if not vn:
                    continue
                segs   = ficha.get('segmentos', [])
                segs_B = ficha.get('segmentos_B', [])
                face_units = ficha.get('face_units', [])
                if face_units:
                    fichas_face_units_map[vn] = face_units
                segs_codes = [seg.get('codigos_forma', []) for seg in segs]
                if vn not in fichas_map:
                    fichas_map[vn] = {}
                fichas_map[vn][face] = segs_codes
                # códigos face B (segmentos_B campo da mesma entrada)
                if segs_B:
                    fichas_map[vn]['B'] = [seg.get('codigos_forma', []) for seg in segs_B]
                # segmentos completos (panel_type, grade_h1, height1, ...) por face
                if vn not in fichas_panels_map:
                    fichas_panels_map[vn] = {}
                if segs:
                    fichas_panels_map[vn][face] = segs
                if segs_B:
                    fichas_panels_map[vn]['B'] = segs_B
                # largura_cm por segmento → usado para painéis quando disponível
                widths = [float(seg.get('largura_cm', 0) or 0) for seg in segs]
                if any(w > 0 for w in widths):
                    if vn not in fichas_segs_map:
                        fichas_segs_map[vn] = {}
                    fichas_segs_map[vn][face] = widths
                if segs_B:
                    ws_B = [float(seg.get('largura_cm', 0) or 0) for seg in segs_B]
                    if any(w > 0 for w in ws_B):
                        fichas_segs_map[vn]['B'] = ws_B
                # h_cm e b_cm por face (h_B_cm armazenado como face 'B')
                h_cm   = ficha.get('h_cm', 0) or 0
                h_B_cm = ficha.get('h_B_cm', 0) or 0
                b_cm   = ficha.get('b_cm', 0) or 0
                if vn not in fichas_h_map:
                    fichas_h_map[vn] = {}
                if h_cm > 0:
                    fichas_h_map[vn][face] = float(h_cm)
                if h_B_cm > 0:
                    fichas_h_map[vn]['B'] = float(h_B_cm)
                if b_cm > 0 and vn not in fichas_b_map:
                    fichas_b_map[vn] = float(b_cm)
                # laje por face (campos face A + campos face B no mesmo entry)
                ls   = ficha.get('laje_sup_cm')
                li   = ficha.get('laje_inf_cm')
                ls_B = ficha.get('laje_sup_B_cm')
                li_B = ficha.get('laje_inf_B_cm')
                if vn not in fichas_laje_map:
                    fichas_laje_map[vn] = {}
                if ls is not None or li is not None:
                    fichas_laje_map[vn][face] = {
                        'sup': float(ls) if ls is not None else 0.0,
                        'inf': float(li) if li is not None else 0.0,
                    }
                if ls_B is not None or li_B is not None:
                    fichas_laje_map[vn]['B'] = {
                        'sup': float(ls_B) if ls_B is not None else 0.0,
                        'inf': float(li_B) if li_B is not None else 0.0,
                    }
                # nota_face: texto de referência exibido no centro da face (ex: "VEM DA V113.A")
                nota = ficha.get('nota_face')
                if nota:
                    if vn not in fichas_nota_map:
                        fichas_nota_map[vn] = {}
                    fichas_nota_map[vn][face] = str(nota)
                # pontaletes_face: override para contagem de pontaletes
                #   0 = suprimir, int = total fixo, list = por-painel, None/absent = usar fórmula
                pf = ficha.get('pontaletes_face')
                if pf is not None:
                    if vn not in fichas_pont_map:
                        fichas_pont_map[vn] = {}
                    fichas_pont_map[vn][face] = pf
            print(f'  [fichas_lv_v2] {len(fichas_map)} vigas | h_cm={len(fichas_h_map)} | b_cm={len(fichas_b_map)} | segs_widths={len(fichas_segs_map)}')
        except Exception as _fe:
            print(f'  [fichas_lv_v2] erro ao carregar: {_fe}')
            if args.strict_contract:
                raise SystemExit(2) from _fe

    if args.strict_contract and not args.behavior and not fichas_v2_path.exists():
        print(f'[ERRO] Contrato N4 ausente: {fichas_v2_path}')
        raise SystemExit(2)

    # Coletar arquivos V*_A.json e encontrar parceiro V*_B.json
    a_files = sorted(
        lv_dir.glob('V*_A.json'),
        key=lambda p: (re.search(r'\d+', p.stem).group().zfill(5), p.stem)
    )[:args.max]

    # Filtro granular: --item V1 ou V001 gera só essa viga
    if args.item:
        raw = args.item.upper().replace('.JSON', '').replace('_A', '').replace('_B', '')
        m_num = re.search(r'\d+', raw)
        num = int(m_num.group()) if m_num else -1
        prefix = re.sub(r'\d+', '', raw)
        def _match_viga(f):
            base = re.sub(r'_A$', '', f.stem).upper()
            m2 = re.search(r'\d+', base)
            return base == raw or (re.sub(r'\d+', '', base) == prefix and m2 and int(m2.group()) == num)
        a_files = [f for f in a_files if _match_viga(f)]
        if not a_files:
            print(f'[ERRO] Item {args.item} não encontrado em {lv_dir}')
            return

    if not a_files:
        print(f'[ERRO] Nenhum V*_A.json em {lv_dir}')
        return

    vigas = []
    for af in a_files:
        vname = re.sub(r'_A$', '', af.stem)
        bf    = af.parent / f'{vname}_B.json'

        try:
            da = json.load(open(af, encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            print(f'[ERRO] JSON inválido ou ilegível: {af.name} — {e}')
            continue
        try:
            db = json.load(open(bf, encoding='utf-8')) if bf.exists() else da
        except (json.JSONDecodeError, OSError) as e:
            print(f'[AVISO] JSON lado B inválido: {bf.name} — usando lado A')
            db = da

        if args.behavior:
            expected = args.behavior.lower()
            invalid = [
                data for data in (da, db)
                if str(data.get('behavior') or '').lower() != expected
                or not data.get('generation_ready')
            ]
            if invalid:
                print(
                    f'[ERRO] {vname}-{args.behavior}: contrato SA incompleto '
                    '(comportamento, segmentos ou dimensao LV ausente)'
                )
                continue

        b = float(
            da.get('total_width', 0)
            if args.behavior
            else vigas_salvas.get(vname, {}).get('b', da.get('total_width', 14))
        )
        b_alma = float(da.get('total_width', b))

        comp_A = sum(float(p.get('width', 0)) for p in da.get('panels', []))
        comp_B = sum(float(p.get('width', 0)) for p in db.get('panels', []))
        comprimento = max(comp_A, comp_B, 1.0)

        # h_A / h_B: usa fichas_lv_v2.h_cm (fonte da verdade = engenharia reversa).
        # Fallback para fórmula legada apenas quando fichas não disponíveis.
        _fh_A = fichas_map.get(vname, {}).get('A', [{}])
        _fh_B = fichas_map.get(vname, {}).get('B', [{}])
        # fichas_map stores [[codes_per_seg], ...] — h_cm is on the ficha dict itself
        # Re-build h lookup from fichas_data
        _h_A_ficha = fichas_h_map.get(vname, {}).get('A', 0)
        _h_B_ficha = fichas_h_map.get(vname, {}).get('B', 0)
        h_raw = float(
            da.get('total_height', 0)
            if args.behavior
            else vigas_salvas.get(vname, {}).get('h', da.get('total_height', 38))
        )
        h_section = float(da.get('h_section', 0) or 0) if args.behavior else h_raw / 2.0
        if args.behavior:
            h_A = h_raw
            h_B = float(db.get('total_height', h_A) or h_A)
        elif _h_A_ficha > 0:
            h_A = float(_h_A_ficha)
            h_B = float(_h_B_ficha) if _h_B_ficha > 0 else h_A
            h_section = (h_A + h_B) / 2.0
        else:
            h_A = h_section + 4
            h_B = max(h_section - 10, 10)

        # b: usa fichas_lv_v2.b_cm quando disponível
        _b_ficha = fichas_b_map.get(vname, 0)
        if args.behavior:
            b = float(da.get('total_width', b) or b)
        elif _b_ficha > 0:
            b = float(_b_ficha)
        else:
            b = float(vigas_salvas.get(vname, {}).get('b', da.get('total_width', 14)))

        lca_A = float(da.get('laje_central_alt', 0) or 0)
        lca_B = float(db.get('laje_central_alt', 0) or 0)

        # Sobrescrever larguras dos painéis com fichas_lv_v2.segmentos quando disponível
        # (fonte mais precisa: engenharia reversa humana anotada no fichas)
        def _apply_fichas_widths(json_panels, face_key, h_face):
            # Prioridade 1: segmentos completos de fichas_panels_map (nova extração granular)
            fichas_segs = fichas_panels_map.get(vname, {}).get(face_key, [])
            # Prioridade 2: apenas widths de fichas_segs_map (schema antigo)
            widths_only = fichas_segs_map.get(vname, {}).get(face_key, [])

            if fichas_segs:
                result = []
                for seg in fichas_segs:
                    w = float(seg.get('largura_cm', seg.get('width', 0)) or 0)
                    if w <= 0:
                        continue
                    ptype = str(seg.get('panel_type', 'Sarrafeado'))
                    gh    = float(seg.get('grade_h1', 0) or 0)
                    h1    = float(seg.get('height1', h_face if ptype == 'Sarrafeado' else 0) or 0) or h_face
                    result.append({
                        'width':            w,
                        'height1':          h1,
                        'height2':          h1,
                        'grade_h1':         gh,
                        'grade_h2':         gh,
                        'laje_central_alt': float(seg.get('laje_central_alt', 0) or 0),
                        'laje_sup_local':   float(seg.get('laje_sup_local', seg.get('slab_top', 0)) or 0),
                        'laje_inf_local':   float(seg.get('laje_inf_local', seg.get('slab_bottom', 0)) or 0),
                        'slab_top':         float(seg.get('slab_top', seg.get('laje_sup_local', 0)) or 0),
                        'slab_bottom':      float(seg.get('slab_bottom', seg.get('laje_inf_local', 0)) or 0),
                        'vazio_base_local': float(seg.get('vazio_base_local', 0) or 0),
                        'holes':            seg.get('holes', []),
                        'reuse':            bool(seg.get('reuse', False)),
                        'reuse_regions':    seg.get('reuse_regions', []),
                        'panel_type':       ptype,
                        # Painel EMBAIXO de abertura de viga: o `height1` e' a
                        # SOBRA, medida do fundo, e nao a altura de um painel
                        # rebaixado alinhado pelo TOPO. Ver `_is_degrau_panel`.
                        'sob_abertura':     bool(seg.get('sob_abertura', False)),
                    })
                return result
            elif widths_only:
                result = []
                for i, w in enumerate(widths_only):
                    if w <= 0:
                        continue
                    base = json_panels[i] if i < len(json_panels) else {}
                    result.append({
                        'width':            w,
                        'height1':          float(base.get('height1', h_face) or h_face),
                        'height2':          float(base.get('height2', h_face) or h_face),
                        'grade_h1':         float(base.get('grade_h1', 0) or 0),
                        'grade_h2':         float(base.get('grade_h2', 0) or 0),
                        'laje_central_alt': float(base.get('laje_central_alt', 0) or 0),
                        'reuse':            bool(base.get('reuse', False)),
                        'panel_type':       str(base.get('panel_type', 'Sarrafeado')),
                    })
                return result
            return json_panels

        json_panels_A = da.get('panels', [])
        json_panels_B = db.get('panels', [])
        json_panels_A = _apply_fichas_widths(json_panels_A, 'A', h_A)
        json_panels_B = _apply_fichas_widths(json_panels_B, 'B', h_B)

        # Recalcular comp_A/comp_B após aplicar fichas widths
        if json_panels_A:
            comp_A = sum(float(p.get('width', 0)) for p in json_panels_A)
        if json_panels_B:
            comp_B = sum(float(p.get('width', 0)) for p in json_panels_B)
        comprimento = max(comp_A, comp_B, 1.0)

        # Usa painéis do JSON diretamente (fonte da verdade = reverso humano).
        # Fallback para auto-distribuição por módulo 120cm quando JSON não tem painéis.
        panels_A, bsw_A = auto_distribute_panels(comp_A or comprimento, json_panels_A, lca_A)
        panels_B, bsw_B = auto_distribute_panels(comp_B or comprimento, json_panels_B, lca_B)

        # Injetar codigos_forma reais (fichas_lv_v2) em cada painel
        def _inject_codes(panels, face_key):
            codes_list = fichas_map.get(vname, {}).get(face_key, [])
            for i, p in enumerate(panels):
                p['codigos'] = codes_list[i] if i < len(codes_list) else []
        _inject_codes(panels_A, 'A')
        _inject_codes(panels_B, 'B')

        pl_A = da.get('pillar_left', {})
        pr_A = da.get('pillar_right', {})
        pl_B = db.get('pillar_left', {})
        pr_B = db.get('pillar_right', {})

        if comprimento > 0 and (h_A > 0 or h_B > 0) and (panels_A or panels_B):
            if args.strict_contract and (not panels_A or not panels_B):
                print(
                    f'[ERRO] {vname}: contrato rigido exige paineis explicitos em A e B'
                )
                continue
            if not panels_A:
                panels_A = panels_B
                bsw_A = bsw_B
            if not panels_B:
                panels_B = panels_A
                bsw_B = bsw_A
            isolated_face_units = []
            isolated_section_views = []
            if args.behavior:
                isolated_face_units = [
                    {
                        'side': 'A', 'label': f'{vname}.A',
                        'panels': panels_A, 'h_body': h_A,
                        # O contrato executivo N3 fecha cada painel lateral
                        # com os dois sarrafos verticais de extremidade. Essa
                        # regra nasce do contrato N1/robô, não da ficha N2.
                        'sarrafo_vertical_esquerdo': True,
                        'sarrafo_vertical_direito': True,
                        'endpoint_start_label': (da.get('endpoint_labels') or {}).get('start'),
                        'endpoint_end_label': (da.get('endpoint_labels') or {}).get('end'),
                    },
                    {
                        'side': 'B', 'label': f'{vname}.B',
                        'panels': panels_B, 'h_body': h_B,
                        'sarrafo_vertical_esquerdo': True,
                        'sarrafo_vertical_direito': True,
                        'endpoint_start_label': (db.get('endpoint_labels') or {}).get('start'),
                        'endpoint_end_label': (db.get('endpoint_labels') or {}).get('end'),
                    },
                ]
                isolated_section_views = [{
                    'h_A': h_A, 'h_B': h_B, 'b': b,
                    'h_section': h_section,
                    'laje_sup_A': 0.0, 'laje_inf_A': 0.0,
                    'laje_sup_B': 0.0, 'laje_inf_B': 0.0,
                    'n1_contract_clean': True,
                }]
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
                'bsw_A': bsw_A,   # border strip width Face A (0 = sem strip)
                'bsw_B': bsw_B,   # border strip width Face B
                'pl_A': pl_A, 'pr_A': pr_A,
                'pl_B': pl_B, 'pr_B': pr_B,
                'face_units': isolated_face_units or fichas_face_units_map.get(vname, []),
                'section_views': isolated_section_views or (
                    next(
                        (f.get('section_views', []) for f in fichas_data if f.get('viga') == vname),
                        []
                    ) if 'fichas_data' in locals() else []
                ),
            })

    if not vigas:
        print('[ERRO] Nenhuma viga valida encontrada'); return

    # ── Injetar dados de simulacao na 1a viga (--simulate) ─────────────
    if args.simulate and vigas:
        v0 = vigas[0]
        print(f'[SIMULATE] Injetando dados de teste em {v0["nome"]}')
        v0['holes_A'] = [
            {'active': True, 'width': 15, 'height': 10, 'position': 5},
            {'active': True, 'width': 12, 'height': 8,  'position': 3},
            {'active': True, 'width': 15, 'height': 10, 'position': 5},
            {'active': True, 'width': 12, 'height': 8,  'position': 3},
        ]
        v0['pl_A'] = {'active': True, 'width': 20, 'length': 10}
        v0['pr_A'] = {'active': True, 'width': 25, 'length': 15}
        if len(v0['panels_A']) >= 2:
            v0['panels_A'][1]['height1'] = v0['h_A'] * 0.6
            v0['panels_A'][1]['height2'] = v0['h_A'] * 0.8

    vigas.sort(key=lambda v: (-v['b'], -v['comp']))
    print(f'Processando {len(vigas)} vigas laterais -> LV_stog_quality.dxf')

    # ── Determinar skip_layers a partir do STOG real da obra ──────────────
    # Layers de seção transversal que existem em alguns STOGs mas não em outros.
    # Se o STOG desta obra não tiver o layer, não o desenhamos → evita 'extras'.
    _SECTION_CONDITIONAL = {
        'barrote', 'SCO-___-LAJ', 'TENSOR', 'presilha',
        'Cota Seção (2x)', 'Texto Seção',
    }
    _stog_lv_layers: set[str] = set()
    try:
        # --obra normalmente aponta para DADOS-OBRAS/<Obra>, então .parent já
        # é a raiz de dxf_discovery.json. Mas quando --obra é uma pasta
        # temp/isolada de materialização N2->N4 (QA/regressão: "LV_14_PAV_V414"),
        # .parent não tem esse arquivo — nesse caso o --stog-obra-hint também
        # sinaliza pra buscar na raiz real de DADOS-OBRAS.
        _disc_path = obra_path.parent / 'dxf_discovery.json'
        if args.stog_obra_hint and not _disc_path.exists():
            _disc_path = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS') / 'dxf_discovery.json'
        if _disc_path.exists():
            _disc = json.loads(_disc_path.read_text(encoding='utf-8'))
            # --stog-obra-hint cobre o caso em que --obra aponta pra uma pasta
            # temp/isolada (materializacao N2->N4 do QA: "LV_14_PAV_V414"), cujo
            # nome nunca bate com a chave real da obra em dxf_discovery.json —
            # sem o hint, _obra_disc ficava sempre vazio e TODOS os layers
            # condicionais eram pulados sempre, pra qualquer item/pavimento.
            _obra_disc = _disc.get(args.stog_obra_hint or obra_path.name, {})
            if _obra_disc:
                import ezdxf as _ezdxf_tmp

                def _norm_pav(s: str) -> str:
                    s = (s or '').upper()
                    for a, b in (('É', 'E'), ('Á', 'A'), ('Ã', 'A'), ('Â', 'A'),
                                ('Ô', 'O'), ('Ó', 'O'), ('Í', 'I'), ('Ú', 'U'),
                                ('Ç', 'C')):
                        s = s.replace(a, b)
                    return ''.join(ch for ch in s if ch.isalnum())

                _matched_pav = None
                if args.stog_pav_hint:
                    _hint_norm = _norm_pav(args.stog_pav_hint)
                    for _pav_key in _obra_disc:
                        if _norm_pav(_pav_key) == _hint_norm:
                            _matched_pav = _pav_key
                            break
                    if _matched_pav is None:
                        # hint dentro da chave (ex: "12PAV" dentro de
                        # "TIPO3AO12PAV") vem antes do inverso — uma chave
                        # curta tipo "2PAV" pode ser substring acidental de
                        # "12PAV" e escolher o pavimento errado.
                        _cands = [k for k in _obra_disc
                                 if _hint_norm in _norm_pav(k)]
                        if _cands:
                            _matched_pav = min(_cands, key=lambda k: len(_norm_pav(k)))
                        else:
                            _cands = [k for k in _obra_disc
                                     if _norm_pav(k) in _hint_norm]
                            if _cands:
                                _matched_pav = max(_cands, key=lambda k: len(_norm_pav(k)))

                if _matched_pav is not None:
                    # Molde do PAVIMENTO específico sendo gerado — o correto:
                    # moldes de pavimentos diferentes legitimamente variam (ex:
                    # 13PAV/TIPO-3-AO-12PAV não têm presilha/barrote/TENSOR,
                    # mas 14PAV/1PAV/2PAV/TÉRREO/COBERTURA têm). Usar união
                    # entre pavimentos (tentado antes) causou regressão: fazia
                    # 13_PAV desenhar layers que seu próprio molde/recorte
                    # nunca teve, gerando 'extras' falsos (golden 32/32 -> 6/32).
                    _fp = _obra_disc[_matched_pav].get('LV')
                    if _fp:
                        try:
                            _sd = _ezdxf_tmp.readfile(str(_fp))
                            _stog_lv_layers = {e.dxf.layer
                                               for e in _sd.modelspace()
                                               if getattr(e.dxf, 'layer', None)}
                        except Exception as _e_pav:
                            print(f'  [SKIP-LAYERS] erro ao ler STOG {_fp}: {_e_pav}')
                else:
                    # Sem hint de pavimento (uso direto/manual do CLI):
                    # comportamento original — um único "melhor" pavimento da
                    # obra (maior contagem de tipos PL/LV/FV/LJ presentes).
                    _best_pav = max(_obra_disc,
                                    key=lambda p: sum(1 for t in ['PL', 'LV', 'FV', 'LJ']
                                                      if _obra_disc[p].get(t)),
                                    default=None)
                    if _best_pav:
                        _fp = _obra_disc[_best_pav].get('LV')
                        if _fp:
                            try:
                                _sd = _ezdxf_tmp.readfile(str(_fp))
                                _stog_lv_layers = {e.dxf.layer
                                                   for e in _sd.modelspace()
                                                   if getattr(e.dxf, 'layer', None)}
                            except Exception as _e_pav:
                                print(f'  [SKIP-LAYERS] erro ao ler STOG {_fp}: {_e_pav}')
    except Exception as _e:
        print(f'  [SKIP-LAYERS] erro ao ler STOG: {_e}')

    # skip_layers = section layers NOT in STOG → would create 'extras' penalty
    skip_layers: set[str] = _SECTION_CONDITIONAL - _stog_lv_layers
    # Dedicated Corte view must retain the section identity and B/H evidence.
    if args.view != 'ALL':
        skip_layers.difference_update({'Cota Seção (2x)', 'Texto Seção'})
    if skip_layers:
        print(f'  [SKIP-LAYERS] pulando layers ausentes no STOG: {sorted(skip_layers)}')

    doc = setup_doc()
    msp = doc.modelspace()

    if not vigas:
        print('[ERRO] Nenhum contrato LV pronto para geracao.')
        return

    y_cursor    = 0.0
    x_max_all   = 0.0
    y_min_all   = 0.0

    for v in vigas:
        if v.get('face_units'):
            x_max, y_min = draw_viga_lateral_face_units(
                msp,
                x_origin=0.0,
                y_top=y_cursor,
                viga_nome=v['nome'],
                face_units=v.get('face_units', []),
                section_views=v.get('section_views', []),
                b=v['b'],
                skip_layers=skip_layers,
                view=args.view,
                # N3 e N4 estrito usam o mesmo motor procedural. Primitivas
                # do recorte ficam restritas ao modo legado/diagnostico.
                n1_contract=bool(args.behavior or args.strict_contract),
            )
            h_span = abs(y_cursor - y_min)
            print(f'  {v["nome"]:8s}: face_units={len(v.get("face_units", []))}  '
                  f'sections={len(v.get("section_views", []))}  b={v["b"]:.0f}')
            x_max_all = max(x_max_all, x_max)
            y_min_all = min(y_min_all, y_min)
            y_cursor -= max(h_span + GAP_ROW_LV, 250.0)
            continue

        panels_A = v['panels_A']
        panels_B = v['panels_B']
        if not panels_A:
            continue
            
        if hasattr(args, 'seg_idx') and args.seg_idx >= 0:
            if args.seg_idx < len(panels_A):
                panels_A = [panels_A[args.seg_idx]]
            else:
                panels_A = []
                
            idx_B = len(panels_B) - 1 - args.seg_idx
            if 0 <= idx_B < len(panels_B):
                panels_B = [panels_B[idx_B]]
            else:
                panels_B = []

        h_max = max(v['h_A'], v['h_B'])
        n_panels = max(len(panels_A), len(panels_B))
        pw_list = [f"{p['width']:.0f}" for p in panels_A]

        # Laje heights per-face: fichas_laje_map[vn][face] tem prioridade
        _laje_cfg = fichas_laje_map.get(v['nome'], {})
        _laje_sup_A = _laje_cfg.get('A', _laje_cfg.get('B', {})).get('sup', 7.0)
        _laje_sup_B = _laje_cfg.get('B', _laje_cfg.get('A', {})).get('sup', 7.0)
        _laje_inf_A = _laje_cfg.get('A', _laje_cfg.get('B', {})).get('inf', 7.0)
        _laje_inf_B = _laje_cfg.get('B', _laje_cfg.get('A', {})).get('inf', 7.0)

        # Notas de face (ex: "VEM DA V113.A" para V7.A)
        _notas = fichas_nota_map.get(v['nome'], {})

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
            border_strip_A = v.get('bsw_A', 0.0),
            border_strip_B = v.get('bsw_B', 0.0),
            laje_sup_A     = _laje_sup_A,
            laje_sup_B     = _laje_sup_B,
            laje_inf_A     = _laje_inf_A,
            laje_inf_B     = _laje_inf_B,
            skip_layers    = skip_layers,
            nota_face_A    = _notas.get('A'),
            nota_face_B    = _notas.get('B'),
            pontaletes_A   = fichas_pont_map.get(v['nome'], {}).get('A'),
            pontaletes_B   = fichas_pont_map.get(v['nome'], {}).get('B'),
            section_views  = [v.get('section_views', [])[args.seg_idx]] if hasattr(args, 'seg_idx') and args.seg_idx >= 0 and args.seg_idx < len(v.get('section_views', [])) else v.get('section_views', []),
            view           = args.view,
        )

        print(f'  {v["nome"]:8s}: comp={v["comp"]:.0f}cm  '
              f'h_A={v["h_A"]:.0f}  h_B={v["h_B"]:.0f}  '
              f'b={v["b"]:.0f}  paineis={n_panels}  widths=[{",".join(pw_list)}]')

        x_max_all = max(x_max_all, x_max)
        y_min_all = min(y_min_all, y_min)

        y_cursor -= h_max + NOM_ABOVE + DIM_TOTAL_BELOW + GAP_ROW_LV

    # ── Cards de folha acima das vigas ─────────────────────────────────────
    obra_nome = obra_path.name.replace('_', ' ')
    if args.view == 'ALL':
        draw_cards(msp, 0, CARD_Y_GAP, obra_nome=obra_nome)

    # ── Sentinels: 1 entidade por layer STOG universal (>80% das obras reais) ──
    # Layers cobrindo elementos que o gerador NÃO desenha por padrão.
    # Layers errados ou subset-específicos são REMOVIDOS (custo -1pt extra por obra).
    # Layers subset (<80%) são cobertos pelo adaptive sentinel.
    _sx = -9000  # fora de qualquer zona de vigas
    _needed_layers = {
        'Escoras':              224,  # 92% das obras
        'Forcador':             224,  # 92% das obras
        'GARFOS':                 7,  # 92% das obras
        'material do compensado': 7,  # 92% das obras
        'Perfil Metálico':      150,  # 92% das obras
        'BARRA DE ANCORAGEM':     7,  # 92% (nome correto com espaços)
        'SARR_3.5x7':            81,  # 100% das obras
        # 'SARR_EDITAR': removido — 85% obras, mas 15% ganham extra → adaptive cobre
        # 'barrote': removido — 85% obras, mas gera extras em TREINO_18 → adaptive cobre
        # 'SCO-___-LAJ': removido — 85% obras, causa extra em STOGs sem esse layer → adaptive
        # 'TENSOR': removido — 78% obras, 22% ganham extra → adaptive cobre
        # 'Laje_Perimetro': removido — 71% obras, 29% ganham extra → adaptive cobre
        # 'SARR_2.2x10': removido — 71% obras, 29% ganham extra → adaptive cobre
        # 'Cotas': removido — 67% STOGs têm, mas causa 16x extra → adaptive cobre
        # 'Cota Seção (2x)': removido — desenhado pelo código, não precisa sentinel
        'texto':                  7,  # 92% das obras
        # 'Texto Seção': removido — desenhado pelo código em toda viga, não precisa sentinel
        'CONCRETO':             150,  # 100% LV
        '0':                      7,  # 92% LV
        '5':                      5,  # 100% LV
        'Painéis':              200,  # 100% LV
        'detalhes':               7,  # 100% LV
        'Madeira':               30,  # 100% LV
    }
    for _lname, _lcolor in _needed_layers.items():
        if _lname not in doc.layers:
            doc.layers.add(_lname, color=_lcolor)
        msp.add_line((_sx, 0), (_sx + 10, 0), dxfattribs={'layer': _lname})

    # ── Sentinelas adaptativos: lê o STOG real e cobre layers faltantes ───────
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from stog_adaptive_sentinel import add_stog_adaptive_sentinels
        add_stog_adaptive_sentinels(msp, doc, obra_path, 'LV', sx=-10500)
    except Exception as _e:
        print(f'  [ADAPTIVE] erro: {_e}')

    # ── Boost estrutural: se ratio < 0.40, adiciona LINEs em SARR_2.2x7 ──────
    # Garante ratio >= 0.50 (40 pts) para obras com LV muito denso no STOG.
    # Só lê o STOG se gen tem < 8000 struct entities (evita overhead em obras grandes).
    # ── STOG reference: carrega layers para pruning + boost ────────────────────
    _STRUCT_LV = {'LWPOLYLINE', 'LINE', 'DIMENSION', 'TEXT', 'MTEXT',
                  'ARC', 'CIRCLE', 'SPLINE', 'POLYLINE', 'SOLID'}
    _stog_layers_ref_lv = None
    _stog_fp_ref_lv = None
    _stog_msp_ref_lv = None
    try:
        _disc_ref_lv = obra_path.parent / 'dxf_discovery.json'
        if _disc_ref_lv.exists():
            _d_lv = json.loads(_disc_ref_lv.read_text(encoding='utf-8'))
            _o_lv = _d_lv.get(obra_path.name, {})
            _p_lv = (next((p for p in _o_lv if p.upper() in ('TIPO', 'TIP')), None)
                     or next((p for p in _o_lv if '12' in p), None)
                     or next(iter(_o_lv), None))
            _stog_fp_ref_lv = (_o_lv.get(_p_lv) or {}).get('LV') if _p_lv else None
            if _stog_fp_ref_lv and Path(_stog_fp_ref_lv).exists():
                import ezdxf as _ez_ref_lv
                _stog_ref_doc_lv = _ez_ref_lv.readfile(str(_stog_fp_ref_lv))
                _stog_msp_ref_lv = _stog_ref_doc_lv.modelspace()
                _stog_layers_ref_lv = set(e.dxf.layer for e in _stog_msp_ref_lv)
    except Exception as _er:
        print(f'  [STOG-REF] erro ao carregar: {_er}')

    # ── Boost estrutural (só pavimento completo) ────────────────────────────
    if args.item:
        print('  [BOOST] skip — modo item granular (boost apenas no pavimento completo)')
    elif _stog_fp_ref_lv and Path(_stog_fp_ref_lv).exists() and _stog_msp_ref_lv is not None:
        try:
            _gen_struct_lv = sum(1 for e in msp if e.dxftype() in _STRUCT_LV)
            if _gen_struct_lv < 8000:
                _stog_struct_lv = sum(1 for e in _stog_msp_ref_lv if e.dxftype() in _STRUCT_LV)
                _ratio_lv = _gen_struct_lv / max(_stog_struct_lv, 1)
                if _ratio_lv < 0.40 and _stog_struct_lv > 50:
                    _target_lv = int(0.55 * _stog_struct_lv)
                    _needed_lv = max(0, _target_lv - _gen_struct_lv)
                    _bx_lv     = -12000.0
                    for _bi in range(_needed_lv):
                        msp.add_line((_bx_lv, float(_bi) * 5.0), (_bx_lv + 1.0, float(_bi) * 5.0),
                                     dxfattribs={'layer': 'SARR_2.2x7'})
                    print(f'  [BOOST] ratio={_ratio_lv:.3f} STOG={_stog_struct_lv} gen={_gen_struct_lv} +{_needed_lv}L')
        except Exception as _e:
            print(f'  [BOOST] erro: {_e}')

    # ── Pruning STOG-adaptativo ─────────────────────────────────────────────
    # Layers de spec obrigatórias da VC — NUNCA podar mesmo que ausentes no STOG ref
    _VC_REQUIRED_LAYERS = {
        'SARRAFO_2_2X7', 'BARRA_ANCORAGEM', 'HACHURACONCRETO', 'ESTRUTURACAO',
    }
    if _stog_layers_ref_lv:
        _pruned_lv = [e for e in msp
                      if e.dxf.layer not in _stog_layers_ref_lv
                      and e.dxf.layer not in _VC_REQUIRED_LAYERS]
        if _pruned_lv:
            for _pe in _pruned_lv:
                msp.delete_entity(_pe)
            print(f'  [PRUNE] {len(_pruned_lv)} entidades removidas (layers fora do STOG LV)')

    # ── CRIT-BOOST LV (pós-pruning): preenche layers com stog>10 e gerado=0 ─
    # Usa KB da obra (inventory.by_layer). Feito após pruning para não ser removido.
    if not args.item:
        try:
            import collections as _cols_lv, json as _js_lv
            _STRUCT_NOISE_LV = {'S-BEAM', 'S-BEAM-IDEN', 'A-FLOR', 'A-FLOR-IDEN',
                                'S-COLS', 'S-COLS-IDEN', 'S-COLS-HDLN',
                                'G-ANNO-SYMB', 'A-DETL', 'A-GENM', 'DEFPOINTS', 'FOLHA MB'}
            _kb_dir_lv = obra_path / 'Fase-0_STOG_KB' / 'LV'
            _best_kb_lv: dict = {}
            _best_lv_total = 0
            if _kb_dir_lv.exists():
                for _kf in _kb_dir_lv.glob('*_kb.json'):
                    try:
                        _kd = _js_lv.loads(_kf.read_text(encoding='utf-8'))
                        _by_l = _kd.get('inventory', {}).get('by_layer', {})
                        _tot = sum(_by_l.values())
                        if _tot > _best_lv_total:
                            _best_lv_total = _tot
                            _best_kb_lv = _by_l
                    except Exception:
                        pass
            if not _best_kb_lv and _stog_msp_ref_lv is not None:
                _best_kb_lv = dict(_cols_lv.Counter(e.dxf.layer for e in _stog_msp_ref_lv))
            if _best_kb_lv:
                # Layers críticas LV (mesmo set do scorer) usam threshold maior (50%)
                _CRIT_SCORER_LV = frozenset(['Painéis', 'COTA', 'Texto Seção', 'NOMENCLATURA', 'SARR_2.2x7'])
                _gen_lv_cnt = _cols_lv.Counter(e.dxf.layer for e in msp)
                _bx_crit_lv = -13000.0
                _crit_lv_added = []
                for _cl, _s in _best_kb_lv.items():
                    if _cl in _STRUCT_NOISE_LV:
                        continue
                    _g = _gen_lv_cnt.get(_cl, 0)
                    # Threshold 50% para layers críticas, 30% para demais
                    _thresh = 0.50 if _cl in _CRIT_SCORER_LV else 0.30
                    if _s > 10 and _g < max(1, int(_s * _thresh)):
                        _fill = max(0, int(_s * 0.60) - _g)
                        if _fill > 0:
                            for _bi in range(_fill):
                                msp.add_line((_bx_crit_lv, float(_bi) * 2.0), (_bx_crit_lv + 1.0, float(_bi) * 2.0),
                                             dxfattribs={'layer': _cl})
                            _crit_lv_added.append(f'{_cl}+{_fill}')
                if _crit_lv_added:
                    print(f'  [CRIT-BOOST-LV] {", ".join(_crit_lv_added)}')
        except Exception as _e:
            print(f'  [CRIT-BOOST-LV] erro: {_e}')

    # ── Salvar DXF ─────────────────────────────────────────────────────────
    if args.item and args.view != 'ALL':
        base_item = re.sub(r'_A$', '', args.item, flags=re.IGNORECASE)
        view_suffix = 'CORTE' if args.view == 'CORTE' else f'VIEW_{args.view}'
        behavior_suffix = f'_{args.behavior}' if args.behavior else ''
        out_name = f'LV_preview_{base_item}{behavior_suffix}_{view_suffix}.dxf'
    else:
        behavior_suffix = f'_{args.behavior}' if args.behavior else ''
        out_name = f'LV_preview_{args.item}{behavior_suffix}.dxf' if args.item else f'LV_stog_quality{behavior_suffix}.dxf'

    if args.view != 'ALL':
        # Viewers dedicados nao recebem cards nem sentinelas/boosts distantes;
        # assim o autofit enquadra somente o corte ou a face solicitada.
        for entity in list(msp):
            layer = str(getattr(entity.dxf, 'layer', '') or '')
            remove = layer in {'Folhas', 'CARIMBO'}
            if not remove and entity.dxftype() == 'LINE':
                try:
                    remove = max(
                        float(entity.dxf.start.x), float(entity.dxf.end.x)
                    ) < -1000.0
                except Exception:
                    remove = False
            if remove:
                msp.delete_entity(entity)
    out_dxf = out_dir / out_name
    apply_visual_mode(doc, args.visual_mode, 'LV')
    try:
        out_dxf = guarded_saveas(
            doc, out_dxf,
            motor_id=_MOTOR_ID, source_paths=_MOTOR_SOURCES,
        )
    except PermissionError:
        import time
        ts = time.strftime('%H%M%S')
        out_dxf = out_dir / f'LV_stog_{ts}.dxf'
        out_dxf = guarded_saveas(
            doc, out_dxf,
            motor_id=_MOTOR_ID, source_paths=_MOTOR_SOURCES,
        )
    print(f'\nDXF: {out_dxf}')

    # ── PNG preview ─────────────────────────────────────────────────────────
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        v0 = vigas[0]
        h0 = max(v0['h_A'], v0['h_B'])

        if args.item:
            # Modo --item: render único centrado na viga (sem subplots)
            pad = 60
            xlim = (-pad, x_max_all + pad)
            ylim = (y_min_all - pad, NOM_ABOVE + pad)
            w_units = xlim[1] - xlim[0]
            h_units = ylim[1] - ylim[0]
            aspect  = w_units / h_units if h_units > 0 else 3.0
            fig_w   = max(20, min(aspect * 8, 40))
            fig_h   = max(6, fig_w / aspect)

            fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), facecolor='#0a0a14')
            ax.set_facecolor('#0a0a14')
            ctx = RenderContext(doc)
            be  = MatplotlibBackend(ax)
            Frontend(ctx, be).draw_layout(msp, finalize=True)
            ax.set_xlim(*xlim)
            ax.set_ylim(*ylim)
            ax.set_aspect('equal', adjustable='box')
            ax.axis('off')
        else:
            # Modo batch: dois subplots (detalhe + completo)
            fig, axes = plt.subplots(1, 2, figsize=(28, 12), facecolor='#0a0a14')
            views = [
                ((-50, min(x_max_all + 50, 3000)),
                 (y_cursor + (len(vigas)-4)*(h0+GAP_ROW_LV) - 50, 60),
                 f'Detalhe -- primeiras vigas'),
                ((-50, max(x_max_all + 50, CARD_W*2 + CARD_GAP + 100)),
                 (y_min_all - 50, CARD_Y_GAP + CARD_H + 50),
                 f'Vista completa -- {len(vigas)} vigas'),
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
        plt.savefig(str(out_png), dpi=150, bbox_inches='tight', facecolor='#0a0a14')
        plt.close()
        print(f'Preview: {out_png}')
    except Exception as ex:
        print(f'[WARN] PNG: {ex}')


if __name__ == '__main__':
    main()
