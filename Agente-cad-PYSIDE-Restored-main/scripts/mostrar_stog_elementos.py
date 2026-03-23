#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

"""
Renderiza 1 elemento de cada classe do STOG para visualizacao.
Usa crop de bounding box para isolar cada card individualmente.
"""

from pathlib import Path
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import numpy as np

STOG_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_21/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa")
OUT_DIR = Path("D:/Agente-cad-PYSIDE/validacao_visual")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def render_dxf_full(doc, ax, title, crop=None):
    """Renderiza DXF num eixo, com crop opcional (xmin,xmax,ymin,ymax)."""
    try:
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        frontend = Frontend(ctx, out)
        frontend.draw_layout(doc.modelspace(), finalize=True)
        if crop:
            xmin, xmax, ymin, ymax = crop
            ax.set_xlim(xmin, xmax)
            ax.set_ylim(ymin, ymax)
        ax.set_title(title, fontsize=10, pad=6)
        ax.set_aspect('equal')
    except Exception as ex:
        ax.text(0.5, 0.5, f'Erro: {ex}', transform=ax.transAxes,
                ha='center', va='center', fontsize=8, color='red')
        ax.set_title(title, fontsize=10)


# ─────────────────────────────────────────────────────────────────────────────
# Fig 1: PL — Pilar (1 card zoom)
# O STOG PL tem ~33 pilares dispostos em grade: 4 colunas x ~8 linhas
# Cada card tem aprox 4800 x 6000 de dimensao no espaco DXF
# Origem do primeiro card: aprox (0, 0) ou inicio da grade
# ─────────────────────────────────────────────────────────────────────────────
print("Carregando PL STOG...")
pl_path = STOG_DIR / "STOG - NIK SUNSET - 12º PAVIMENTO - PL - R00_R2018_ASCII_ODA.dxf"
doc_pl = ezdxf.readfile(str(pl_path))

# Detectar extents dos elementos para encontrar 1 card
msp = doc_pl.modelspace()
xs, ys = [], []
for e in msp:
    try:
        if e.dxftype() == 'LWPOLYLINE':
            pts = list(e.get_points())
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
        elif e.dxftype() == 'LINE':
            xs += [e.dxf.start.x, e.dxf.end.x]
            ys += [e.dxf.start.y, e.dxf.end.y]
    except: pass

if xs:
    x0, y0 = min(xs), min(ys)
    print(f"  PL extents: x0={x0:.0f} y0={y0:.0f} xmax={max(xs):.0f} ymax={max(ys):.0f}")
    # Primeiro card: regiao inicial da grade
    # Calcular largura media de 1 card dividindo pelo numero de colunas
    xrange = max(xs) - x0
    yrange = max(ys) - y0
    # ~4 colunas x ~9 linhas para 33 pilares
    card_w = xrange / 4
    card_h = yrange / 9
    print(f"  Card estimado: {card_w:.0f} x {card_h:.0f}")
    crop_pl = (x0, x0 + card_w * 1.05, y0 + yrange - card_h * 1.1, y0 + yrange + card_h * 0.1)
else:
    crop_pl = None

fig1, ax1 = plt.subplots(1, 1, figsize=(10, 10))
fig1.patch.set_facecolor('#1a1a2e')
render_dxf_full(doc_pl, ax1,
    "PILAR (PL) — Exemplo 1 card do STOG\n(formwork: paineis, dimensoes, materiais, carimbo)",
    crop=crop_pl)
plt.tight_layout()
plt.savefig(str(OUT_DIR / "STOG_01_PILAR_exemplo.png"), dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  -> STOG_01_PILAR_exemplo.png")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 2: LV — Viga Lateral (1 card zoom)
# ─────────────────────────────────────────────────────────────────────────────
print("Carregando LV STOG...")
lv_path = STOG_DIR / "STOG - NIK SUNSET - 12º PAVIMENTO - LV - R00_R2018_ASCII_ODA.dxf"
doc_lv = ezdxf.readfile(str(lv_path))

msp = doc_lv.modelspace()
xs, ys = [], []
for e in msp:
    try:
        if e.dxftype() == 'LWPOLYLINE':
            pts = list(e.get_points())
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
        elif e.dxftype() == 'LINE':
            xs += [e.dxf.start.x, e.dxf.end.x]
            ys += [e.dxf.start.y, e.dxf.end.y]
    except: pass

if xs:
    x0, y0 = min(xs), min(ys)
    xrange = max(xs) - x0
    yrange = max(ys) - y0
    # LV: ~33 vigas, cada viga tem 2 faces (A+B) + fundo = 3 vistas por card
    # Estimar: 3 colunas x ~11 linhas
    card_w = xrange / 3
    card_h = yrange / 12
    print(f"  LV extents: {xrange:.0f} x {yrange:.0f}, card est: {card_w:.0f} x {card_h:.0f}")
    crop_lv = (x0, x0 + card_w * 1.1, y0 + yrange - card_h * 1.1, y0 + yrange + card_h * 0.1)
else:
    crop_lv = None

fig2, ax2 = plt.subplots(1, 1, figsize=(12, 8))
fig2.patch.set_facecolor('#1a1a2e')
render_dxf_full(doc_lv, ax2,
    "VIGA LATERAL (LV) — Exemplo 1 card do STOG\n(Face A + Face B com sarrafos, escoras, altura lateral)",
    crop=crop_lv)
plt.tight_layout()
plt.savefig(str(OUT_DIR / "STOG_02_VIGA_LATERAL_exemplo.png"), dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  -> STOG_02_VIGA_LATERAL_exemplo.png")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 3: FV — Viga Fundo (1 card zoom)
# ─────────────────────────────────────────────────────────────────────────────
print("Carregando FV STOG...")
fv_path = STOG_DIR / "STOG - NIK SUNSET - 12° PAV.- FV - R00_R2018_ASCII_ODA.dxf"
doc_fv = ezdxf.readfile(str(fv_path))

msp = doc_fv.modelspace()
xs, ys = [], []
for e in msp:
    try:
        if e.dxftype() == 'LWPOLYLINE':
            pts = list(e.get_points())
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
        elif e.dxftype() == 'LINE':
            xs += [e.dxf.start.x, e.dxf.end.x]
            ys += [e.dxf.start.y, e.dxf.end.y]
    except: pass

if xs:
    x0, y0 = min(xs), min(ys)
    xrange = max(xs) - x0
    yrange = max(ys) - y0
    # FV tem menos cards (algumas vigas nao tem fundo separado)
    card_w = xrange / 3
    card_h = yrange / 3
    print(f"  FV extents: {xrange:.0f} x {yrange:.0f}, card est: {card_w:.0f} x {card_h:.0f}")
    crop_fv = (x0, x0 + card_w * 1.1, y0 + yrange - card_h * 1.1, y0 + yrange + card_h * 0.1)
else:
    crop_fv = None

fig3, ax3 = plt.subplots(1, 1, figsize=(12, 8))
fig3.patch.set_facecolor('#1a1a2e')
render_dxf_full(doc_fv, ax3,
    "VIGA FUNDO (FV) — Exemplo 1 card do STOG\n(Vista de baixo: fundo da viga com compensado e sarrafos)",
    crop=crop_fv)
plt.tight_layout()
plt.savefig(str(OUT_DIR / "STOG_03_VIGA_FUNDO_exemplo.png"), dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  -> STOG_03_VIGA_FUNDO_exemplo.png")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 4: LJ — Laje (planta completa do pavimento)
# LJ e diferente: mostra a planta baixa do pavimento inteiro com todas as lajes
# ─────────────────────────────────────────────────────────────────────────────
print("Carregando LJ STOG...")
lj_path = STOG_DIR / "STOG - NIK SUNSET - 12° PAV.- LJ - R00_R2018_ASCII_ODA.dxf"
doc_lj = ezdxf.readfile(str(lj_path))

fig4, ax4 = plt.subplots(1, 1, figsize=(14, 10))
fig4.patch.set_facecolor('#1a1a2e')
render_dxf_full(doc_lj, ax4,
    "LAJE (LJ) — Planta baixa completa do pavimento no STOG\n(Posicao real de cada laje no edificio + pontaletes + sarrafos)",
    crop=None)
plt.tight_layout()
plt.savefig(str(OUT_DIR / "STOG_04_LAJE_exemplo.png"), dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  -> STOG_04_LAJE_exemplo.png")


# ─────────────────────────────────────────────────────────────────────────────
# Fig 5: Panorama — PL STOG completo (visao geral de todos os pilares)
# ─────────────────────────────────────────────────────────────────────────────
print("Gerando panorama PL completo...")
fig5, ax5 = plt.subplots(1, 1, figsize=(16, 12))
fig5.patch.set_facecolor('#1a1a2e')
render_dxf_full(doc_pl, ax5,
    "STOG PL COMPLETO — Todos os pilares do 12 PAV\n(cada retangulo colorido = 1 pilar com sua forma de concreto)",
    crop=None)
plt.tight_layout()
plt.savefig(str(OUT_DIR / "STOG_00_PL_COMPLETO.png"), dpi=120, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print("  -> STOG_00_PL_COMPLETO.png")

print("\nDone. Imagens em:", OUT_DIR)
