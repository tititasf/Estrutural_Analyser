#!/usr/bin/env python3
"""Compara DXF original vs reconstruído visualmente (matplotlib)."""
import sys, io, os, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon
from matplotlib.collections import LineCollection, PatchCollection
import numpy as np

TARGET_VIGA = 'V302'

# ── Caminhos ──────────────────────────────────────────────────────────
dxf_dir = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa'
orig_path = next(
    os.path.join(dxf_dir, f) for f in os.listdir(dxf_dir)
    if 'LV' in f and '13' in f and f.endswith('.dxf')
)
reco_path = 'D:/Agente-cad-PYSIDE/ANALISE_LV/reconstructed/Obra_TREINO_1_V302.dxf'

print(f"Original   : {os.path.basename(orig_path)}")
print(f"Reconstruído: {os.path.basename(reco_path)}")

# ── Extrair entidades da zona de V302 ─────────────────────────────────
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts')
import extrair_parametros_viga_v3 as ext

orig_doc = ezdxf.readfile(orig_path)
orig_msp = orig_doc.modelspace()
all_vigas = ext.find_all_inserts(orig_msp)
zone = ext.compute_zone(all_vigas, TARGET_VIGA)

# Margem ao redor da zona
margin = 150
_x_left = zone.get('x_left') or zone['insert_x']
X_MIN = min(zone['insert_x'] - 400, _x_left - margin)
X_MAX = (zone.get('x_right') or zone['insert_x'] + 1600) + margin
Y_MIN = zone['y_bot'] - margin + 900   # zoom na viga, não na linha de baixo
Y_MAX = zone['y_top'] + margin

print(f"Zona: x=[{X_MIN:.0f},{X_MAX:.0f}] y=[{Y_MIN:.0f},{Y_MAX:.0f}]")


def collect_draw(msp, x_min, x_max, y_min, y_max):
    """Coleta entidades visíveis na janela para desenho."""
    lines = []
    polys = []
    texts = []
    hatches = []

    def in_window(pts):
        return any(x_min - 50 <= p[0] <= x_max + 50 and y_min - 50 <= p[1] <= y_max + 50
                   for p in pts)

    for e in msp:
        t = e.dxftype()
        layer = e.dxf.layer if hasattr(e.dxf, 'layer') else '0'

        if t == 'LINE':
            s = (e.dxf.start.x, e.dxf.start.y)
            en = (e.dxf.end.x, e.dxf.end.y)
            if in_window([s, en]):
                lines.append((s, en, layer))

        elif t == 'LWPOLYLINE':
            pts = list(e.get_points(format='xy'))
            if pts and in_window(pts):
                polys.append((pts, layer, e.is_closed))

        elif t == 'HATCH':
            try:
                pattern = getattr(e.dxf, 'pattern_name', 'SOLID')
                all_pts = []
                for p in e.paths:
                    if hasattr(p, 'vertices'):
                        all_pts.extend([(v[0], v[1]) for v in p.vertices])
                    elif hasattr(p, 'edges'):
                        for edge in p.edges:
                            for attr in ('start', 'end', 'center'):
                                if hasattr(edge, attr):
                                    v = getattr(edge, attr)
                                    try: all_pts.append((v.x, v.y))
                                    except: pass
                if all_pts and in_window(all_pts):
                    hatches.append((all_pts, layer, pattern))
            except:
                pass

        elif t in ('TEXT', 'MTEXT'):
            try:
                x = e.dxf.insert.x
                y = e.dxf.insert.y
                if x_min <= x <= x_max and y_min <= y <= y_max:
                    txt = e.dxf.text if t == 'TEXT' else (e.text if hasattr(e, 'text') else '')
                    import re
                    txt = re.sub(r'\\[^;]+;', '', txt).replace('{', '').replace('}', '')
                    texts.append((x, y, txt[:20]))
            except:
                pass

    return lines, polys, texts, hatches


# Cores por layer
LAYER_COLORS = {
    'painéis': '#2196F3',  # azul
    'painis': '#2196F3',
    'pain': '#2196F3',
    'concreto': '#757575',  # cinza
    'sarr': '#FF9800',      # laranja
    'madeira': '#8D6E63',   # marrom
    'texto': '#9C27B0',     # roxo
    'cota': '#FFEB3B',      # amarelo
}

def layer_color(layer):
    low = layer.lower().replace('é', 'e').replace('ã', 'a').replace('ô', 'o').replace('ç', 'c')
    for k, c in LAYER_COLORS.items():
        if k in low:
            return c
    return '#FFFFFF'


def draw_on_ax(ax, lines, polys, texts, hatches, title):
    ax.set_facecolor('#1a1a1a')
    ax.set_xlim(X_MIN, X_MAX)
    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_title(title, color='white', fontsize=11, fontweight='bold')
    ax.set_aspect('equal')
    ax.tick_params(colors='#666', labelsize=6)
    ax.set_xlabel('X (mm)', color='#666', fontsize=7)
    ax.set_ylabel('Y (mm)', color='#666', fontsize=7)

    # Hatches first (background)
    for (pts, layer, pattern) in hatches:
        c = layer_color(layer)
        xs = [p[0] for p in pts] + [pts[0][0]]
        ys = [p[1] for p in pts] + [pts[0][1]]
        alpha = 0.25 if pattern == 'SOLID' else 0.15
        ax.fill(xs, ys, color=c, alpha=alpha)
        ax.plot(xs, ys, color=c, linewidth=0.3, alpha=0.4)

    for (s, e, layer) in lines:
        c = layer_color(layer)
        ax.plot([s[0], e[0]], [s[1], e[1]], color=c, linewidth=0.7, alpha=0.9)

    for (pts, layer, closed) in polys:
        c = layer_color(layer)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if closed:
            xs = xs + [xs[0]]
            ys = ys + [ys[0]]
        ax.plot(xs, ys, color=c, linewidth=0.8, alpha=0.85)

    for (x, y, txt) in texts:
        ax.text(x, y, txt, color='#CE93D8', fontsize=4, alpha=0.8)


# ── Figura comparativa ────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(20, 10))
fig.patch.set_facecolor('#0d0d0d')
fig.suptitle(f'Comparação V302: Original vs Reconstruído', color='white',
             fontsize=14, fontweight='bold', y=0.98)

# Original
orig_lines, orig_polys, orig_texts, orig_hatches = collect_draw(orig_msp, X_MIN, X_MAX, Y_MIN, Y_MAX)
draw_on_ax(axes[0], orig_lines, orig_polys, orig_texts, orig_hatches,
           f'ORIGINAL ({len(orig_lines)}L {len(orig_polys)}P {len(orig_hatches)}H)')

# Reconstruído
reco_doc = ezdxf.readfile(reco_path)
reco_msp = reco_doc.modelspace()
reco_lines, reco_polys, reco_texts, reco_hatches = collect_draw(reco_msp, X_MIN, X_MAX, Y_MIN, Y_MAX)
draw_on_ax(axes[1], reco_lines, reco_polys, reco_texts, reco_hatches,
           f'RECONSTRUÍDO ({len(reco_lines)}L {len(reco_polys)}P {len(reco_hatches)}H)')

# Legenda
legend_items = [
    mpatches.Patch(color='#2196F3', label='Painéis'),
    mpatches.Patch(color='#757575', label='Concreto'),
    mpatches.Patch(color='#FF9800', label='SARR_3.5x7'),
    mpatches.Patch(color='#8D6E63', label='Madeira'),
    mpatches.Patch(color='#9C27B0', label='Textos'),
]
fig.legend(handles=legend_items, loc='lower center', ncol=5,
           facecolor='#1a1a1a', edgecolor='#333',
           labelcolor='white', fontsize=8, framealpha=0.8)

plt.tight_layout(rect=[0, 0.04, 1, 0.96])
out = 'D:/Agente-cad-PYSIDE/ANALISE_LV/comparacao_V302.png'
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='#0d0d0d')
print(f"\nComparação salva: {out}")
print(f"Original   : {len(orig_lines)} lines, {len(orig_polys)} polys, {len(orig_hatches)} hatches, {len(orig_texts)} texts")
print(f"Reconstruido: {len(reco_lines)} lines, {len(reco_polys)} polys, {len(reco_hatches)} hatches, {len(reco_texts)} texts")
