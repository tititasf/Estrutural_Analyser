#!/usr/bin/env python3
"""
gerar_pavimento_demo.py — CAD-ANALYZER
Gera DXF completo de pavimento-tipo com dados reais do corpus Obra_TREINO_1.

Planta: grid 4×5 pilares, vigas conectando, laje preenchendo vãos.
Dimensões reais do corpus FAISS (228 pilares / 11 obras).
"""
import sys, math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import ezdxf
from ezdxf import colors as dxf_colors

OUT = Path('D:/Agente-cad-PYSIDE/docs/fichas/pavimento_demo_treino1.dxf')
OUT.parent.mkdir(parents=True, exist_ok=True)

# ── DADOS REAIS Obra_TREINO_1 (corpus FAISS) ──────────────────────────────────
# 23 pilares reais — b, h em cm, alt=280cm, pe_direito=280cm
PILARES_DADOS = [
    {'id': 'P11', 'b': 46.0, 'h': 56.0, 'alt': 280.0, 'conf': 0.9},
    {'id': 'P12', 'b': 19.0, 'h': 64.0, 'alt': 280.0, 'conf': 0.9},
    {'id': 'P13', 'b': 24.0, 'h': 64.0, 'alt': 280.0, 'conf': 0.9},
    {'id': 'P15', 'b': 25.5, 'h': 34.0, 'alt': 280.0, 'conf': 0.8},
    {'id': 'P16', 'b': 16.0, 'h': 24.0, 'alt': 280.0, 'conf': 0.4},
    {'id': 'P17', 'b': 19.0, 'h': 24.0, 'alt': 280.0, 'conf': 0.4},
    {'id': 'P18', 'b': 34.0, 'h': 54.0, 'alt': 280.0, 'conf': 0.8},
    {'id': 'P19', 'b': 27.6, 'h': 54.0, 'alt': 280.0, 'conf': 0.9},
    {'id': 'P20', 'b': 16.0, 'h': 54.0, 'alt': 280.0, 'conf': 0.4},
    {'id': 'P21', 'b': 16.0, 'h': 19.0, 'alt': 280.0, 'conf': 0.8},
    {'id': 'P23', 'b': 17.0, 'h': 64.0, 'alt': 280.0, 'conf': 0.8},
    {'id': 'P24', 'b': 16.0, 'h': 19.0, 'alt': 280.0, 'conf': 0.9},
    {'id': 'P25', 'b': 19.0, 'h': 24.0, 'alt': 280.0, 'conf': 0.8},
    {'id': 'P26', 'b': 25.0, 'h': 50.0, 'alt': 280.0, 'conf': 0.9},
    {'id': 'P27', 'b': 14.0, 'h': 34.0, 'alt': 280.0, 'conf': 0.8},
    {'id': 'P28', 'b': 19.0, 'h': 60.0, 'alt': 280.0, 'conf': 0.9},
    {'id': 'P29', 'b': 46.0, 'h': 56.0, 'alt': 280.0, 'conf': 0.9},
    {'id': 'P30', 'b': 25.0, 'h': 50.0, 'alt': 280.0, 'conf': 0.8},
    {'id': 'P31', 'b': 14.0, 'h': 34.0, 'alt': 280.0, 'conf': 0.8},
    {'id': 'P32', 'b': 34.0, 'h': 54.0, 'alt': 280.0, 'conf': 0.9},
    {'id': 'P33', 'b': 16.0, 'h': 24.0, 'alt': 280.0, 'conf': 0.7},
    {'id': 'P34', 'b': 19.0, 'h': 64.0, 'alt': 280.0, 'conf': 0.9},
    {'id': 'P35', 'b': 25.5, 'h': 34.0, 'alt': 280.0, 'conf': 0.8},
]

# Grid de posições para os pilares (mm — DXF usa mm por padrão)
# Vãos típicos residenciais: 350-500cm
GRID_X = [0, 3500, 7000, 11000]       # 4 colunas: vãos 3.5m, 3.5m, 4.0m
GRID_Y = [0, 3500, 7000, 10500, 14000] # 5 fileiras: vãos 3.5m cada

# Mapear pilares no grid (4x5 = 20 posições, usar os 20 primeiros)
POSICOES = []
for row, y in enumerate(GRID_Y):
    for col, x in enumerate(GRID_X):
        idx = row * len(GRID_X) + col
        if idx < len(PILARES_DADOS):
            p = PILARES_DADOS[idx].copy()
            p['x'] = x
            p['y'] = y
            POSICOES.append(p)

# ── DXF SETUP ────────────────────────────────────────────────────────────────
doc = ezdxf.new('R2010')
msp = doc.modelspace()

# Layers
LAYERS = [
    ('PILARES',       2,  'CONTINUOUS'),   # amarelo
    ('PILARES-HAT',   2,  'CONTINUOUS'),
    ('PILARES-TXT',   7,  'CONTINUOUS'),   # branco/preto
    ('VIGAS',         5,  'CONTINUOUS'),   # azul
    ('VIGAS-TXT',     7,  'CONTINUOUS'),
    ('LAJE',          3,  'CONTINUOUS'),   # verde
    ('LAJE-TXT',      7,  'CONTINUOUS'),
    ('COTAS',         1,  'CONTINUOUS'),   # vermelho
    ('EIXOS',         8,  'DASHED'),       # cinza
    ('BORDA',         7,  'CONTINUOUS'),
    ('INFO',          7,  'CONTINUOUS'),
]
for name, color, lt in LAYERS:
    if name not in doc.layers:
        doc.layers.add(name, color=color, linetype=lt if lt == 'CONTINUOUS' else 'DASHED')

# Estilo de texto
if 'ROMANS' not in doc.styles:
    doc.styles.add('ROMANS', font='romans.shx')
txt_style = 'Standard'

# ── HELPERS ──────────────────────────────────────────────────────────────────

def add_rect(msp, cx, cy, bw, bh, layer, close=True):
    """Retângulo centrado em (cx, cy) com largura bw e altura bh."""
    x0 = cx - bw/2; x1 = cx + bw/2
    y0 = cy - bh/2; y1 = cy + bh/2
    pts = [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    pl = msp.add_lwpolyline(pts, dxfattribs={'layer': layer, 'closed': True})
    return pl, (x0, y0, x1, y1)

def add_hatch(msp, x0, y0, x1, y1, layer, pattern='SOLID', color=None):
    hatch = msp.add_hatch(dxfattribs={'layer': layer})
    if color: hatch.dxf.color = color
    hatch.paths.add_polyline_path(
        [(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)],
        is_closed=True
    )
    return hatch

def add_text(msp, x, y, text, height=150, layer='PILARES-TXT', halign=1):
    """Texto centrado."""
    txt = msp.add_text(
        text,
        dxfattribs={
            'layer': layer,
            'height': height,
            'color': 7,
        }
    )
    txt.set_placement((x, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    return txt

def add_dim_linear(msp, p1, p2, offset, layer='COTAS'):
    """Cota linear entre dois pontos."""
    dist = abs(p2[0] - p1[0]) if abs(p2[0]-p1[0]) > abs(p2[1]-p1[1]) else abs(p2[1]-p1[1])
    dim = msp.add_linear_dim(
        base=(p1[0], p1[1] + offset) if abs(p2[0]-p1[0]) > abs(p2[1]-p1[1]) else (p1[0]+offset, p1[1]),
        p1=p1, p2=p2,
        angle=0 if abs(p2[0]-p1[0]) > abs(p2[1]-p1[1]) else 90,
        dxfattribs={'layer': layer, 'color': 1}
    )
    dim.render()
    return dim

# ── EIXOS (linhas de referência) ─────────────────────────────────────────────
MARGIN = 1000  # margem para eixos
for i, gx in enumerate(GRID_X):
    msp.add_line(
        (gx, -MARGIN), (gx, GRID_Y[-1]+MARGIN),
        dxfattribs={'layer': 'EIXOS', 'color': 8, 'linetype': 'DASHED'}
    )
    add_text(msp, gx, GRID_Y[-1]+MARGIN+300,
             chr(65+i),   # A, B, C, D
             height=250, layer='INFO')

for i, gy in enumerate(GRID_Y):
    msp.add_line(
        (-MARGIN, gy), (GRID_X[-1]+MARGIN, gy),
        dxfattribs={'layer': 'EIXOS', 'color': 8, 'linetype': 'DASHED'}
    )
    add_text(msp, -MARGIN-300, gy,
             str(i+1),
             height=250, layer='INFO')

# ── LAJE (polígono de fundo) ──────────────────────────────────────────────────
laje_margin = 0
LX0 = GRID_X[0];  LX1 = GRID_X[-1]
LY0 = GRID_Y[0];  LY1 = GRID_Y[-1]

# Contorno externo da laje
laje_pts = [(LX0,LY0),(LX1,LY0),(LX1,LY1),(LX0,LY1)]
msp.add_lwpolyline(
    laje_pts,
    dxfattribs={'layer': 'LAJE', 'color': 3, 'closed': True, 'const_width': 20}
)
# Hatch leve da laje
hatch = msp.add_hatch(dxfattribs={'layer': 'LAJE-HAT', 'color': 3})
hatch.dxf.solid_fill = 0
hatch.set_pattern_fill('ANSI31', scale=200, angle=45)
hatch.paths.add_polyline_path(
    [(LX0,LY0),(LX1,LY0),(LX1,LY1),(LX0,LY1),(LX0,LY0)],
    is_closed=True
)
# Label laje
add_text(msp, (LX0+LX1)/2, (LY0+LY1)/2,
         'L1  esp=12cm  area=154m2',
         height=200, layer='LAJE-TXT')

# ── VIGAS ────────────────────────────────────────────────────────────────────
VGA_B = 14    # cm largura
VGA_H = 50    # cm altura
VGA_W = VGA_B * 10  # mm para DXF (1cm = 10mm)

viga_count = 0
for row_i, gy in enumerate(GRID_Y):
    for col_i in range(len(GRID_X)-1):
        gx0 = GRID_X[col_i];  gx1 = GRID_X[col_i+1]
        cx  = (gx0+gx1)/2;   cy  = gy
        comp = (gx1-gx0)/10  # em cm
        viga_count += 1
        vid = f'V{row_i+1}{col_i+1}'

        # Linha de eixo da viga
        msp.add_line(
            (gx0+PILARES_DADOS[col_i]['b']*5, gy),  # sai da face do pilar
            (gx1-PILARES_DADOS[col_i+1]['b']*5, gy),
            dxfattribs={'layer': 'VIGAS', 'color': 5,
                        'lineweight': 50}
        )
        # Retângulo espessura da viga (viga LV — lateral)
        for sinal in [-1, 1]:
            offset_y = sinal * VGA_W/2
            msp.add_line(
                (gx0+PILARES_DADOS[col_i]['b']*5, gy+offset_y),
                (gx1-PILARES_DADOS[col_i+1]['b']*5, gy+offset_y),
                dxfattribs={'layer': 'VIGAS', 'color': 5}
            )
        # Label
        add_text(msp, cx, gy-VGA_W-150,
                 f'{vid} {VGA_B}x{VGA_H}  L={comp:.0f}cm',
                 height=130, layer='VIGAS-TXT')

# Vigas na direção Y (entre fileiras)
for col_i, gx in enumerate(GRID_X):
    for row_i in range(len(GRID_Y)-1):
        gy0 = GRID_Y[row_i]; gy1 = GRID_Y[row_i+1]
        idx = row_i * len(GRID_X) + col_i
        if idx < len(PILARES_DADOS):
            pb = PILARES_DADOS[idx]['h'] * 5  # metade h em mm
        else:
            pb = 200
        comp = (gy1-gy0)/10
        vid = f'VY{col_i+1}{row_i+1}'

        msp.add_line(
            (gx, gy0+pb), (gx, gy1-pb),
            dxfattribs={'layer': 'VIGAS', 'color': 5, 'lineweight': 50}
        )
        for sinal in [-1, 1]:
            msp.add_line(
                (gx+sinal*VGA_W/2, gy0+pb),
                (gx+sinal*VGA_W/2, gy1-pb),
                dxfattribs={'layer': 'VIGAS', 'color': 5}
            )

# ── PILARES ──────────────────────────────────────────────────────────────────
for p in POSICOES:
    cx = p['x'];  cy = p['y']
    bw = p['b'] * 10;  bh = p['h'] * 10  # cm → mm

    # Retângulo do pilar
    x0 = cx - bw/2; x1 = cx + bw/2
    y0 = cy - bh/2; y1 = cy + bh/2

    msp.add_lwpolyline(
        [(x0,y0),(x1,y0),(x1,y1),(x0,y1)],
        dxfattribs={'layer': 'PILARES', 'color': 2, 'closed': True, 'const_width': 15}
    )

    # Hatch sólido do pilar (representa concreto)
    hatch_p = msp.add_hatch(dxfattribs={'layer': 'PILARES-HAT', 'color': 254})
    hatch_p.dxf.solid_fill = 1
    hatch_p.paths.add_polyline_path(
        [(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)],
        is_closed=True
    )

    # Diagonal (marca estrutural de pilar)
    msp.add_line((x0,y0),(x1,y1), dxfattribs={'layer': 'PILARES', 'color': 2})
    msp.add_line((x1,y0),(x0,y1), dxfattribs={'layer': 'PILARES', 'color': 2})

    # Label ID
    conf_tag = '' if p['conf'] >= 0.7 else '?'
    add_text(msp, cx, cy+bh/2+200,
             f'{p["id"]}{conf_tag}',
             height=160, layer='PILARES-TXT')
    # Dimensões
    add_text(msp, cx, cy,
             f'{p["b"]:.0f}x{p["h"]:.0f}',
             height=120, layer='PILARES-TXT')

# ── COTAS ────────────────────────────────────────────────────────────────────
# Cotas horizontais (vãos entre pilares)
cota_y_base = GRID_Y[-1] + 800
for i in range(len(GRID_X)-1):
    x0 = GRID_X[i]; x1 = GRID_X[i+1]
    vao = (x1-x0)/10  # cm
    # Linha de cota
    msp.add_line((x0, cota_y_base), (x1, cota_y_base),
                 dxfattribs={'layer': 'COTAS', 'color': 1})
    msp.add_line((x0, GRID_Y[-1]), (x0, cota_y_base+100),
                 dxfattribs={'layer': 'COTAS', 'color': 1})
    msp.add_line((x1, GRID_Y[-1]), (x1, cota_y_base+100),
                 dxfattribs={'layer': 'COTAS', 'color': 1})
    add_text(msp, (x0+x1)/2, cota_y_base+200,
             f'{vao:.0f}cm',
             height=180, layer='COTAS')

# Cotas verticais (vãos entre fileiras)
cota_x_base = GRID_X[-1] + 800
for i in range(len(GRID_Y)-1):
    y0 = GRID_Y[i]; y1 = GRID_Y[i+1]
    vao = (y1-y0)/10
    msp.add_line((cota_x_base, y0), (cota_x_base, y1),
                 dxfattribs={'layer': 'COTAS', 'color': 1})
    msp.add_line((GRID_X[-1], y0), (cota_x_base+100, y0),
                 dxfattribs={'layer': 'COTAS', 'color': 1})
    msp.add_line((GRID_X[-1], y1), (cota_x_base+100, y1),
                 dxfattribs={'layer': 'COTAS', 'color': 1})
    add_text(msp, cota_x_base+350, (y0+y1)/2,
             f'{vao:.0f}cm',
             height=180, layer='COTAS')

# ── BORDA E CARIMBO ────────────────────────────────────────────────────────────
# Borda da folha (A1 simplificado)
BX0 = -2000; BY0 = -2500
BX1 = GRID_X[-1]+2500; BY1 = GRID_Y[-1]+2500
msp.add_lwpolyline(
    [(BX0,BY0),(BX1,BY0),(BX1,BY1),(BX0,BY1)],
    dxfattribs={'layer': 'BORDA', 'color': 7, 'closed': True, 'const_width': 25}
)

# Carimbo
cam_y = BY0 - 100
add_text(msp, (BX0+BX1)/2, cam_y - 300,
         'CAD-ANALYZER v7  |  OBRA: Obra_TREINO_1  |  PAVIMENTO TIPO  |  ESC 1:50',
         height=200, layer='INFO')
add_text(msp, (BX0+BX1)/2, cam_y - 650,
         f'Pilares: {len(POSICOES)}  |  Vigas X: {(len(GRID_Y))*(len(GRID_X)-1)}  |  Vigas Y: {len(GRID_X)*(len(GRID_Y)-1)}  |  Lajes: 1  |  Pe-direito: 280cm',
         height=160, layer='INFO')
add_text(msp, (BX0+BX1)/2, cam_y - 950,
         'Corpus RAG: 228 pilares / 351 vigas / 220 lajes / 11 obras de treino  |  Score CEO-AUDIT: 92.0/100',
         height=140, layer='INFO')

# Legenda
leg_x = BX0 + 300; leg_y = BY0 + 1800
add_text(msp, leg_x, leg_y,       'LEGENDA:',       height=200, layer='INFO')
add_text(msp, leg_x, leg_y - 350, '[2] PILARES  — cor amarela, hatch solido', height=160, layer='INFO')
add_text(msp, leg_x, leg_y - 600, '[5] VIGAS    — cor azul, LV+FV', height=160, layer='INFO')
add_text(msp, leg_x, leg_y - 850, '[3] LAJE     — cor verde, hatch ANSI31', height=160, layer='INFO')
add_text(msp, leg_x, leg_y-1100,  '[8] EIXOS    — tracejado cinza', height=160, layer='INFO')
add_text(msp, leg_x, leg_y-1350,  '[1] COTAS    — vermelho', height=160, layer='INFO')
add_text(msp, leg_x, leg_y-1600,  'P?? = pilar com confidence < 0.7 (RAG: REVISAO)', height=160, layer='INFO')

# ── SALVAR ────────────────────────────────────────────────────────────────────
doc.saveas(str(OUT))
print(f'[OK] DXF gerado: {OUT}')
print(f'     Pilares: {len(POSICOES)}')
print(f'     Vigas X: {(len(GRID_Y))*(len(GRID_X)-1)}')
print(f'     Vigas Y: {len(GRID_X)*(len(GRID_Y)-1)}')
print(f'     Laje:    1 (154 m2)')
print(f'     Tamanho: {OUT.stat().st_size//1024} KB')
