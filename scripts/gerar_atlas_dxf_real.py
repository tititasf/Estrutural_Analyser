#!/usr/bin/env python3
"""
Atlas DXF Real -- renderiza geometria DIRETA dos DXFs de engenharia reversa.
Produz 3 PDFs: atlas_pilares_real.pdf, atlas_vigas_real.pdf, atlas_lajes_real.pdf

Executa: python scripts/gerar_atlas_dxf_real.py
"""
import sys
import math
import os
import traceback
from pathlib import Path
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Arc, Polygon, FancyBboxPatch
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
REV  = "Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa"
OUT_DIR = Path("D:/Agente-cad-PYSIDE/docs/fichas")
OUT_DIR.mkdir(parents=True, exist_ok=True)

import ezdxf

# -- DXF file lists ----------------------------------------------------------
FILES_PL = [
    BASE / "Obra_TREINO_1"  / REV / "ALIMONTI - PARAISO - TIPO - 3\u00b0 AO 12\u00b0 PAV.- PL - R00.dxf",
    BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-PL-R01_R2018_ASCII_ODA.dxf",
    BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TIPO - PL - R00_R2018_ASCII_ODA.dxf",
]
FILES_LV = [
    BASE / "Obra_TREINO_1"  / REV / "ALIMONTI - PARAISO - TIPO - 3\u00b0 AO 12\u00b0 PAV.- LV - R00.dxf",
    BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-LV-R00_R2018_ASCII_ODA.dxf",
    BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TIPO  - LV - R00_R2018_ASCII_ODA.dxf",
]
FILES_LJ = [
    BASE / "Obra_TREINO_1"  / REV / "ALIMONTI - PARAISO - TIPO - 3\u00b0 AO 12\u00b0 PAV.- LJ - R00.dxf",
    BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-LJ-R00_R2018_ASCII_ODA.dxf",
    BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TIPO - LJ - R00_R2018_ASCII_ODA.dxf",
]
FILES_FV = [
    BASE / "Obra_TREINO_1"  / REV / "ALIMONTI - PARAISO - TIPO - 3\u00b0 AO 12\u00b0 PAV.- FV - R00.dxf",
    BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-FV-R00_R2018_ASCII_ODA.dxf",
]

OBRA_NAMES = {
    'Obra_TREINO_1':  'ALIMONTI Paraiso (Tipo 3-12 Pav)',
    'Obra_TREINO_11': 'NOVA-SCHWARTZ GWT (Tipo)',
    'Obra_TREINO_13': 'SKR LEAF (Tipo)',
}

def obra_label(path):
    """Extract obra short name from path."""
    for key, val in OBRA_NAMES.items():
        if key in str(path):
            return val
    return Path(path).stem[:30]

# ---------------------------------------------------------------------------
# LAYER COLORS (real ACI extractions)
# ---------------------------------------------------------------------------
LAYER_COLORS = {
    '0':                  '#ffffff',
    'Pain\u00e9is':       '#888888',
    'Paineis':            '#888888',
    'SARRAFO':            '#5b5b5b',
    'SARR_2.2x7':         '#ffbf00',
    'SARR_2.2x10':        '#7fff00',
    'SARR_2.2x15':        '#888888',
    'SARR_2.2x20':        '#00ff7f',
    'SARR_3.5x7':         '#888888',
    'SARR_7x7':           '#ffbf00',
    'SARR_7x10':          '#ff007f',
    'SARR_EDITAR':        '#888888',
    'Sarr 2.2x7':         '#ffbf00',
    'SARRAFO DE PRESSAO': '#5b5b5b',
    'Sarrafo de Press\u00e3o': '#888888',
    'Madeira':            '#888888',
    'MEIO_PONT':          '#888888',
    'PONTALETE':          '#ffffff',
    'CHAPA':              '#ff0000',
    'Perfil Met\u00e1lico':'#888888',
    'BARRA ANCORAGEM':    '#5b5b5b',
    'BARRA DE ANCORAGEM': '#5b5b5b',
    'CONCRETO':           '#5b5b5b',
    'COTA':               '#888888',
    'cotas':              '#00ffff',
    'Hachura':            '#5b5b5b',
    'Demarca\u00e7\u00e3o 1': '#5b5b5b',
    'Demarca\u00e7\u00e3o 2': '#d6d6d6',
    'NOMENCLATURA':       '#ffffff',
    'texto':              '#ffffff',
    'TEXTO_GERAL':        '#ffffff',
    'Texto Se\u00e7\u00e3o': '#ffffff',
    'Texto N\u00edvel':    '#5b5b5b',
    'NIVEL':              '#ffffff',
    'N\u00edvel':          '#3b3b3b',
    'Laje_Perimetro':     '#ffffff',
    'Folhas':             '#ffffff',
    'CARIMBO':            '#ffffff',
    'GARFOS':             '#ffffff',
    'HACHURA MADEIRAS':   '#ff0000',
    'Escoras':            '#ffff00',
    'Forcador':           '#5b5b5b',
    'TENSOR':             '#00ff00',
    'presilha':           '#ff0000',
    'fundo':              '#007fff',
    'barrote':            '#5b5b5b',
    '5':                  '#0000ff',
    'REAPROVEITAMENTO':   '#ffff00',
    'Pilares':            '#888888',
    'VIGAS':              '#888888',
    'FOLHA':              '#ffffff',
    'FELIPE':             '#ffff00',
    'GRAVATA':            '#ffff00',
    '1-2 PONTALETE':      '#ffffff',
    'va165-sec':          '#0000ff',
    '00 - FELIPE':        '#ffff00',
}

ACI_COLORS = {
    1: '#ff0000', 2: '#ffff00', 3: '#00ff00', 4: '#00ffff', 5: '#0000ff',
    6: '#ff00ff', 7: '#ffffff', 8: '#808080', 9: '#c0c0c0',
    40: '#ffbf00', 41: '#888888', 60: '#7fff00', 61: '#888888',
    80: '#00ff7f', 81: '#888888', 93: '#888888', 100: '#007fff',
    111: '#888888', 121: '#888888', 126: '#888888', 140: '#ff007f',
    141: '#888888', 160: '#333333', 200: '#888888', 224: '#888888',
    241: '#888888', 251: '#5b5b5b', 254: '#d6d6d6', 255: '#ffffff',
}

def aci_to_hex(aci):
    if aci == 0:
        return '#ffffff'
    if aci < 0:
        aci = -aci
    return ACI_COLORS.get(aci, '#888888')

# ---------------------------------------------------------------------------
# STYLE
# ---------------------------------------------------------------------------
BG = '#0a0a14'
FG = '#e0e0e0'
plt.rcParams.update({
    'figure.facecolor': BG,
    'axes.facecolor': BG,
    'axes.edgecolor': '#333355',
    'text.color': FG,
    'xtick.color': '#666666',
    'ytick.color': '#666666',
    'font.family': 'monospace',
    'figure.max_open_warning': 100,
})

# ---------------------------------------------------------------------------
# ZOOM REGIONS
# ---------------------------------------------------------------------------
PL_ZOOM_P1P2 = (4280, 12060, 6040, 12760)
PL_ZOOM_FULL = (2600, 11900, 8700, 12800)
PL_AREA_ALL  = (2600, 600, 8700, 12800)

LV_ZOOM_1    = (3000, 5500, 6000, 7100)
LV_AREA_ALL  = (3000, 700, 9100, 7100)

LJ_AREA_ALL  = (3500, 1500, 7200, 2900)

# ---------------------------------------------------------------------------
# FIGURE HELPERS
# ---------------------------------------------------------------------------
def fig_a3_landscape(title=''):
    """A3 landscape: 42 x 29.7 cm."""
    fig = plt.figure(figsize=(16.54, 11.69))
    fig.patch.set_facecolor(BG)
    if title:
        fig.text(0.5, 0.98, title, ha='center', va='top',
                 fontsize=11, color='#e8b84b', fontweight='bold', fontfamily='monospace')
    return fig

def fig_a4_portrait(title=''):
    """A4 portrait: 21 x 29.7 cm."""
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(BG)
    if title:
        fig.text(0.5, 0.98, title, ha='center', va='top',
                 fontsize=11, color='#e8b84b', fontweight='bold', fontfamily='monospace')
    return fig

def setup_ax(ax, title=''):
    ax.set_facecolor(BG)
    ax.set_aspect('equal')
    ax.tick_params(colors='#666666', labelsize=6)
    for spine in ax.spines.values():
        spine.set_color('#333355')
    if title:
        ax.set_title(title, color='#cccccc', fontsize=9, pad=4, fontfamily='monospace')

# ---------------------------------------------------------------------------
# ENTITY RENDERERS
# ---------------------------------------------------------------------------
def _get_entity_color(e, layer_name, dxf_layer_colors):
    """Resolve entity color: entity override > LAYER_COLORS dict > DXF layer > fallback."""
    # Entity-level color override
    try:
        ec = getattr(e.dxf, 'color', 256)
        if ec not in (0, 256) and ec > 0:
            c = aci_to_hex(ec)
            if c != '#888888':
                return c
    except Exception:
        pass
    # Our lookup table first
    c = LAYER_COLORS.get(layer_name)
    if c:
        return c
    # DXF layer color
    c = dxf_layer_colors.get(layer_name)
    if c:
        return c
    return '#888888'

def _resolve_linestyle(layer_name):
    """Return matplotlib linestyle from layer name hints."""
    up = layer_name.upper()
    if 'PRESSAO' in up or 'PRESS' in up or 'DASHED' in up or 'HIDDEN' in up:
        return '--'
    if 'va165-sec' in layer_name:
        return '--'
    return '-'

def _resolve_linewidth(layer_name, etype):
    """Return appropriate linewidth by layer and entity type."""
    if layer_name in ('Pain\u00e9is', 'Paineis', 'PAINEL'):
        return 1.0
    if layer_name in ('CHAPA',):
        return 0.8
    if layer_name.startswith('SARR_') or layer_name == 'SARRAFO':
        return 0.8
    if layer_name in ('CONCRETO',):
        return 0.6
    if layer_name in ('Perfil Met\u00e1lico',):
        return 0.7
    if etype == 'LINE':
        return 0.3
    if etype == 'ARC':
        return 0.4
    return 0.5

def render_entities(ax, entities, dxf_layer_colors, show_layers=None, hide_layers=None,
                    max_text=5000, alpha_override=None):
    """Render a list of DXF entities onto matplotlib ax."""
    text_count = 0
    for e in entities:
        try:
            layer = getattr(e.dxf, 'layer', '0') if hasattr(e, 'dxf') else '0'
            if show_layers and layer not in show_layers:
                continue
            if hide_layers and layer in hide_layers:
                continue

            color = _get_entity_color(e, layer, dxf_layer_colors)
            if color in ('#000000', '#0a0a14', '#080808'):
                color = '#444444'

            etype = e.dxftype()
            lw = _resolve_linewidth(layer, etype)
            ls = _resolve_linestyle(layer)
            a = alpha_override if alpha_override else 0.9

            if etype == 'LWPOLYLINE':
                pts = list(e.get_points('xy'))
                if not pts:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                if e.is_closed:
                    xs.append(xs[0])
                    ys.append(ys[0])
                ax.plot(xs, ys, color=color, lw=lw, solid_capstyle='round',
                        linestyle=ls, alpha=a, zorder=2)

            elif etype == 'LINE':
                x1, y1 = e.dxf.start.x, e.dxf.start.y
                x2, y2 = e.dxf.end.x, e.dxf.end.y
                ax.plot([x1, x2], [y1, y2], color=color, lw=lw, linestyle=ls,
                        alpha=a, zorder=2)

            elif etype == 'ARC':
                cx, cy = e.dxf.center.x, e.dxf.center.y
                r = e.dxf.radius
                sa = e.dxf.start_angle
                ea = e.dxf.end_angle
                arc_patch = Arc((cx, cy), 2 * r, 2 * r, angle=0,
                                theta1=sa, theta2=ea, color=color, lw=lw, alpha=a)
                ax.add_patch(arc_patch)

            elif etype == 'CIRCLE':
                cx, cy = e.dxf.center.x, e.dxf.center.y
                r = e.dxf.radius
                circ = plt.Circle((cx, cy), r, fill=False, edgecolor=color, lw=lw, alpha=a)
                ax.add_patch(circ)

            elif etype == 'HATCH':
                pattern = getattr(e.dxf, 'pattern_name', '')
                ha = 0.15 if pattern == 'ANSI31' else 0.25 if pattern == 'SOLID' else 0.1
                if alpha_override:
                    ha = min(ha, alpha_override * 0.3)
                for bp in e.paths:
                    pts_h = []
                    if hasattr(bp, 'vertices'):
                        pts_h = [(v[0], v[1]) for v in bp.vertices]
                    elif hasattr(bp, 'edges'):
                        for edge in bp.edges:
                            if hasattr(edge, 'start'):
                                pts_h.append((edge.start[0], edge.start[1]))
                            if hasattr(edge, 'end'):
                                pts_h.append((edge.end[0], edge.end[1]))
                    if len(pts_h) >= 3:
                        poly = Polygon(pts_h, closed=True, facecolor=color,
                                       alpha=ha, edgecolor='none', zorder=1)
                        ax.add_patch(poly)

            elif etype in ('TEXT', 'MTEXT'):
                text_count += 1
                if text_count > max_text:
                    continue
                if etype == 'TEXT':
                    txt = e.dxf.text
                    x, y = e.dxf.insert.x, e.dxf.insert.y
                    h = e.dxf.height
                else:
                    txt = e.plain_mtext() if hasattr(e, 'plain_mtext') else ''
                    if '\n' in txt:
                        txt = txt.split('\n')[0]
                    txt = txt[:30]
                    x, y = e.dxf.insert.x, e.dxf.insert.y
                    h = getattr(e.dxf, 'char_height', 50)
                fontsize = max(3, min(8, h / 15))
                ax.text(x, y, txt[:20], color=color, fontsize=fontsize,
                        ha='left', va='bottom', clip_on=True, alpha=a, zorder=3)

            elif etype == 'INSERT':
                # Render block references at insert position
                pass  # Block inserts handled separately when needed

            elif etype == 'POINT':
                px, py = e.dxf.location.x, e.dxf.location.y
                ax.plot(px, py, '.', color=color, markersize=1, alpha=a)

            elif etype == 'SPLINE':
                try:
                    pts = list(e.flattening(0.5))
                    if pts:
                        xs = [p.x for p in pts]
                        ys = [p.y for p in pts]
                        ax.plot(xs, ys, color=color, lw=lw, alpha=a, zorder=2)
                except Exception:
                    pass

        except Exception:
            continue

def render_block(ax, block, dxf_layer_colors, offset=(0, 0), scale=1.0):
    """Render block entities with offset and scale."""
    for e in block:
        try:
            layer = getattr(e.dxf, 'layer', '0') if hasattr(e, 'dxf') else '0'
            color = _get_entity_color(e, layer, dxf_layer_colors)
            if color in ('#000000', '#0a0a14'):
                color = '#444444'
            etype = e.dxftype()
            ox, oy = offset

            if etype == 'LINE':
                x1 = e.dxf.start.x * scale + ox
                y1 = e.dxf.start.y * scale + oy
                x2 = e.dxf.end.x * scale + ox
                y2 = e.dxf.end.y * scale + oy
                ax.plot([x1, x2], [y1, y2], color=color, lw=0.5)

            elif etype == 'ARC':
                cx = e.dxf.center.x * scale + ox
                cy = e.dxf.center.y * scale + oy
                r = e.dxf.radius * scale
                sa, ea = e.dxf.start_angle, e.dxf.end_angle
                arc_p = Arc((cx, cy), 2 * r, 2 * r, angle=0,
                            theta1=sa, theta2=ea, color=color, lw=0.5)
                ax.add_patch(arc_p)

            elif etype == 'CIRCLE':
                cx = e.dxf.center.x * scale + ox
                cy = e.dxf.center.y * scale + oy
                r = e.dxf.radius * scale
                circ = plt.Circle((cx, cy), r, fill=False, edgecolor=color, lw=0.5)
                ax.add_patch(circ)

            elif etype == 'LWPOLYLINE':
                pts = list(e.get_points('xy'))
                if not pts:
                    continue
                xs = [p[0] * scale + ox for p in pts]
                ys = [p[1] * scale + oy for p in pts]
                if e.is_closed:
                    xs.append(xs[0])
                    ys.append(ys[0])
                ax.plot(xs, ys, color=color, lw=0.5)

        except Exception:
            continue

# ---------------------------------------------------------------------------
# DXF LOADER
# ---------------------------------------------------------------------------
def load_dxf(path):
    """Load DXF and return (doc, msp, layer_colors, entity_list, layer_stats)."""
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    lc = {}
    for layer in doc.layers:
        name = layer.dxf.name
        aci = layer.dxf.color
        lc[name] = aci_to_hex(aci)

    entities = list(msp)
    stats = defaultdict(int)
    for e in entities:
        ly = getattr(e.dxf, 'layer', '0') if hasattr(e, 'dxf') else '0'
        stats[ly] += 1

    return doc, msp, lc, entities, stats

def compute_bbox(entities, show_layers=None, hide_layers=None, max_coord=50000):
    """Compute bounding box of given entities, ignoring far-off outlier coordinates."""
    xmin, ymin = float('inf'), float('inf')
    xmax, ymax = float('-inf'), float('-inf')

    def add_pt(x, y):
        nonlocal xmin, xmax, ymin, ymax
        # Skip far-off outliers (e.g., SARRAFO DE PRESSAO blocks at -95637, -33898)
        if abs(x) > max_coord or abs(y) > max_coord:
            return
        xmin, xmax = min(xmin, x), max(xmax, x)
        ymin, ymax = min(ymin, y), max(ymax, y)

    for e in entities:
        try:
            layer = getattr(e.dxf, 'layer', '0') if hasattr(e, 'dxf') else '0'
            if show_layers and layer not in show_layers:
                continue
            if hide_layers and layer in hide_layers:
                continue
            etype = e.dxftype()
            if etype == 'LWPOLYLINE':
                for p in e.get_points('xy'):
                    add_pt(p[0], p[1])
            elif etype == 'LINE':
                for pt in (e.dxf.start, e.dxf.end):
                    add_pt(pt.x, pt.y)
            elif etype in ('ARC', 'CIRCLE'):
                cx, cy, r = e.dxf.center.x, e.dxf.center.y, e.dxf.radius
                add_pt(cx - r, cy - r)
                add_pt(cx + r, cy + r)
            elif etype in ('TEXT', 'MTEXT', 'INSERT', 'POINT'):
                pt = e.dxf.insert if hasattr(e.dxf, 'insert') else (
                    e.dxf.location if hasattr(e.dxf, 'location') else None)
                if pt:
                    add_pt(pt.x, pt.y)
        except Exception:
            continue

    if xmin == float('inf'):
        return (0, 0, 100, 100)
    margin = max((xmax - xmin), (ymax - ymin)) * 0.02
    return (xmin - margin, ymin - margin, xmax + margin, ymax + margin)

def render_dxf(ax, path, crop_bbox=None, show_layers=None, hide_layers=None, title=None,
               max_text=5000, alpha_override=None):
    """Full DXF render onto axes."""
    doc, msp, lc, entities, stats = load_dxf(path)
    render_entities(ax, entities, lc, show_layers=show_layers, hide_layers=hide_layers,
                    max_text=max_text, alpha_override=alpha_override)
    if crop_bbox:
        ax.set_xlim(crop_bbox[0], crop_bbox[2])
        ax.set_ylim(crop_bbox[1], crop_bbox[3])
    else:
        bbox = compute_bbox(entities, show_layers=show_layers, hide_layers=hide_layers)
        ax.set_xlim(bbox[0], bbox[2])
        ax.set_ylim(bbox[1], bbox[3])
    setup_ax(ax, title)

def render_dxf_layers_only(ax, path, layers, title=None, crop_bbox=None):
    """Render only specific layers."""
    render_dxf(ax, path, crop_bbox=crop_bbox, show_layers=set(layers), title=title)

# ---------------------------------------------------------------------------
# PAGE BUILDERS -- COVER & INDEX
# ---------------------------------------------------------------------------
def page_cover(pdf, atlas_type, file_list):
    """Cover page for an atlas."""
    fig = fig_a4_portrait()
    fig.text(0.5, 0.85, f'ATLAS DXF REAL', ha='center', va='center',
             fontsize=24, color='#e8b84b', fontweight='bold', fontfamily='monospace')
    type_labels = {'PL': 'PILARES', 'LV': 'VIGAS (Laterais + Fundos)', 'LJ': 'LAJES'}
    fig.text(0.5, 0.78, type_labels.get(atlas_type, atlas_type),
             ha='center', va='center', fontsize=18, color='#ffffff', fontfamily='monospace')
    fig.text(0.5, 0.72, f'Geometria Renderizada dos DXFs de Engenharia Reversa',
             ha='center', va='center', fontsize=10, color='#aaaaaa', fontfamily='monospace')
    fig.text(0.5, 0.67, f'Gerado: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
             ha='center', va='center', fontsize=9, color='#888888', fontfamily='monospace')

    y = 0.55
    fig.text(0.1, y, 'ARQUIVOS FONTE:', color='#e8b84b', fontsize=10, fontweight='bold',
             fontfamily='monospace')
    y -= 0.04
    for i, f in enumerate(file_list):
        name = Path(f).name if len(str(f)) > 60 else str(f)
        fig.text(0.12, y, f'{i+1}. {name[:70]}',
                 color='#cccccc', fontsize=7, fontfamily='monospace')
        y -= 0.025

    y -= 0.03
    fig.text(0.1, y, 'SISTEMA:', color='#e8b84b', fontsize=10, fontweight='bold',
             fontfamily='monospace')
    y -= 0.035
    for line in [
        'Renderizacao direta via ezdxf + matplotlib',
        'Cores reais extraidas das layers ACI do DXF',
        'Fundo escuro (#0a0a14) para contraste maximo',
        f'Total: {len(file_list)} DXFs processados',
    ]:
        fig.text(0.12, y, f'  {line}', color='#aaaaaa', fontsize=8, fontfamily='monospace')
        y -= 0.025

    pdf.savefig(fig)
    plt.close(fig)

def page_layer_index(pdf, path, title=''):
    """Page showing all layers with colors and entity counts."""
    doc, msp, lc, entities, stats = load_dxf(path)
    fig = fig_a4_portrait(f'Indice de Layers - {title}')

    sorted_layers = sorted(stats.items(), key=lambda x: -x[1])
    ax = fig.add_axes([0.05, 0.05, 0.9, 0.88])
    ax.set_facecolor(BG)
    ax.axis('off')

    y = 0.95
    # Header
    ax.text(0.02, y, 'Layer', color='#e8b84b', fontsize=8, fontweight='bold',
            transform=ax.transAxes, fontfamily='monospace')
    ax.text(0.45, y, 'Cor', color='#e8b84b', fontsize=8, fontweight='bold',
            transform=ax.transAxes, fontfamily='monospace')
    ax.text(0.60, y, 'ACI', color='#e8b84b', fontsize=8, fontweight='bold',
            transform=ax.transAxes, fontfamily='monospace')
    ax.text(0.75, y, 'Entidades', color='#e8b84b', fontsize=8, fontweight='bold',
            transform=ax.transAxes, fontfamily='monospace')
    y -= 0.015
    ax.plot([0.02, 0.95], [y, y], color='#444444', lw=0.5,
            transform=ax.transAxes, clip_on=False)
    y -= 0.02

    for name, count in sorted_layers[:40]:
        color = LAYER_COLORS.get(name, lc.get(name, '#888888'))
        # Color swatch as a small colored marker
        ax.plot(0.46, y, 's', color=color, markersize=6,
                transform=ax.transAxes, clip_on=False)
        ax.text(0.02, y, name[:30], color='#cccccc', fontsize=6.5,
                transform=ax.transAxes, fontfamily='monospace', va='center')
        ax.text(0.60, y, color, color='#aaaaaa', fontsize=6,
                transform=ax.transAxes, fontfamily='monospace', va='center')
        ax.text(0.78, y, str(count), color='#ffffff', fontsize=6.5,
                transform=ax.transAxes, fontfamily='monospace', va='center')
        y -= 0.022
        if y < 0.02:
            break

    pdf.savefig(fig)
    plt.close(fig)

# ---------------------------------------------------------------------------
# PAGE BUILDERS -- DXF RENDERS
# ---------------------------------------------------------------------------
def page_full_render(pdf, path, title, crop=None, page_num=None, total=None):
    """Full DXF rendering page (A3 landscape)."""
    tag = f'[Pg {page_num}/{total}]' if page_num else ''
    print(f'  {tag} {title}', flush=True)
    fig = fig_a3_landscape(title)
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.92])
    render_dxf(ax, path, crop_bbox=crop, title=None)
    pdf.savefig(fig)
    plt.close(fig)

def page_zoom_render(pdf, path, title, crop, page_num=None, total=None):
    """Zoomed DXF rendering page (A3 landscape)."""
    tag = f'[Pg {page_num}/{total}]' if page_num else ''
    print(f'  {tag} {title}', flush=True)
    fig = fig_a3_landscape(title)
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.92])
    render_dxf(ax, path, crop_bbox=crop, title=None)
    pdf.savefig(fig)
    plt.close(fig)

def page_layer_detail(pdf, path, layers, title, page_num=None, total=None, crop=None):
    """Render only specific layers (A3 landscape)."""
    tag = f'[Pg {page_num}/{total}]' if page_num else ''
    print(f'  {tag} {title}', flush=True)
    fig = fig_a3_landscape(title)
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.92])
    render_dxf(ax, path, crop_bbox=crop, show_layers=set(layers), title=None)
    # Add legend
    handles = []
    for ly in layers:
        c = LAYER_COLORS.get(ly, '#888888')
        handles.append(Line2D([0], [0], color=c, lw=2, label=ly))
    if handles:
        leg = ax.legend(handles=handles, loc='upper right', fontsize=6,
                        facecolor='#1a1a2e', edgecolor='#444444', labelcolor='#cccccc')
    pdf.savefig(fig)
    plt.close(fig)

def page_comparison_3(pdf, paths, title, page_num=None, total=None):
    """3 obras side by side (A3 landscape)."""
    tag = f'[Pg {page_num}/{total}]' if page_num else ''
    print(f'  {tag} {title}', flush=True)
    fig = fig_a3_landscape(title)
    n = len(paths)
    for i, p in enumerate(paths):
        ax = fig.add_subplot(1, n, i + 1)
        try:
            render_dxf(ax, p, title=obra_label(p), max_text=1000)
        except Exception as ex:
            setup_ax(ax, f'ERRO: {ex}')
    fig.subplots_adjust(wspace=0.1, left=0.02, right=0.98, top=0.92, bottom=0.03)
    pdf.savefig(fig)
    plt.close(fig)

def page_block_detail(pdf, doc, block_names, title, page_num=None, total=None):
    """Render specific blocks with labels (A4 portrait)."""
    tag = f'[Pg {page_num}/{total}]' if page_num else ''
    print(f'  {tag} {title}', flush=True)
    fig = fig_a4_portrait(title)

    lc = {}
    for layer in doc.layers:
        lc[layer.dxf.name] = aci_to_hex(layer.dxf.color)

    valid_blocks = []
    for bn in block_names:
        try:
            blk = doc.blocks.get(bn)
            if blk:
                valid_blocks.append((bn, blk))
        except Exception:
            pass

    n = max(len(valid_blocks), 1)
    rows = math.ceil(n / 2)
    cols = min(n, 2)

    for idx, (bn, blk) in enumerate(valid_blocks):
        ax = fig.add_subplot(rows, cols, idx + 1)
        setup_ax(ax, f'Bloco: {bn}')
        render_block(ax, blk, lc)
        ax.autoscale()
        ax.set_aspect('equal')

    fig.subplots_adjust(hspace=0.3, wspace=0.3, top=0.92, bottom=0.05)
    pdf.savefig(fig)
    plt.close(fig)

def page_dimension_table(pdf, path, title, page_num=None, total=None):
    """Table of extracted real dimensions by layer (A4 portrait)."""
    tag = f'[Pg {page_num}/{total}]' if page_num else ''
    print(f'  {tag} {title}', flush=True)

    doc, msp, lc, entities, stats = load_dxf(path)
    fig = fig_a4_portrait(title)
    ax = fig.add_axes([0.05, 0.05, 0.9, 0.88])
    ax.set_facecolor(BG)
    ax.axis('off')

    # Collect dimensions per layer from LWPOLYLINE bounding boxes
    layer_dims = defaultdict(list)
    for e in entities:
        try:
            if e.dxftype() != 'LWPOLYLINE':
                continue
            layer = getattr(e.dxf, 'layer', '0')
            pts = list(e.get_points('xy'))
            if len(pts) < 2:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if w > 0.1 or h > 0.1:
                layer_dims[layer].append((w, h))
        except Exception:
            continue

    y = 0.95
    ax.text(0.02, y, 'Layer', color='#e8b84b', fontsize=8, fontweight='bold',
            transform=ax.transAxes, fontfamily='monospace')
    ax.text(0.30, y, 'Count', color='#e8b84b', fontsize=8, fontweight='bold',
            transform=ax.transAxes, fontfamily='monospace')
    ax.text(0.42, y, 'W min', color='#e8b84b', fontsize=8, fontweight='bold',
            transform=ax.transAxes, fontfamily='monospace')
    ax.text(0.55, y, 'W max', color='#e8b84b', fontsize=8, fontweight='bold',
            transform=ax.transAxes, fontfamily='monospace')
    ax.text(0.68, y, 'H min', color='#e8b84b', fontsize=8, fontweight='bold',
            transform=ax.transAxes, fontfamily='monospace')
    ax.text(0.82, y, 'H max', color='#e8b84b', fontsize=8, fontweight='bold',
            transform=ax.transAxes, fontfamily='monospace')
    y -= 0.015
    ax.plot([0.02, 0.95], [y, y], color='#444444', lw=0.5,
            transform=ax.transAxes, clip_on=False)
    y -= 0.022

    for layer_name in sorted(layer_dims.keys()):
        dims = layer_dims[layer_name]
        ws = [d[0] for d in dims]
        hs = [d[1] for d in dims]
        color = LAYER_COLORS.get(layer_name, '#888888')
        ax.text(0.02, y, layer_name[:25], color=color, fontsize=6.5,
                transform=ax.transAxes, fontfamily='monospace', va='center')
        ax.text(0.33, y, str(len(dims)), color='#ffffff', fontsize=6.5,
                transform=ax.transAxes, fontfamily='monospace', va='center')
        ax.text(0.42, y, f'{min(ws):.0f}', color='#aaaaaa', fontsize=6.5,
                transform=ax.transAxes, fontfamily='monospace', va='center')
        ax.text(0.55, y, f'{max(ws):.0f}', color='#aaaaaa', fontsize=6.5,
                transform=ax.transAxes, fontfamily='monospace', va='center')
        ax.text(0.68, y, f'{min(hs):.0f}', color='#aaaaaa', fontsize=6.5,
                transform=ax.transAxes, fontfamily='monospace', va='center')
        ax.text(0.82, y, f'{max(hs):.0f}', color='#aaaaaa', fontsize=6.5,
                transform=ax.transAxes, fontfamily='monospace', va='center')
        y -= 0.022
        if y < 0.02:
            break

    pdf.savefig(fig)
    plt.close(fig)

def page_histogram(pdf, path, title, page_num=None, total=None):
    """Histograms of poly dimensions (A4 portrait)."""
    tag = f'[Pg {page_num}/{total}]' if page_num else ''
    print(f'  {tag} {title}', flush=True)

    doc, msp, lc, entities, stats = load_dxf(path)
    fig = fig_a4_portrait(title)

    # Collect widths and heights
    widths_by_layer = defaultdict(list)
    heights_by_layer = defaultdict(list)
    target_layers = ['Pain\u00e9is', 'Paineis', 'SARRAFO', 'SARR_2.2x7', 'SARR_3.5x7',
                     'CONCRETO', 'CHAPA', 'Madeira']
    for e in entities:
        try:
            if e.dxftype() != 'LWPOLYLINE':
                continue
            layer = getattr(e.dxf, 'layer', '0')
            if layer not in target_layers:
                continue
            pts = list(e.get_points('xy'))
            if len(pts) < 2:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if w > 0.1:
                widths_by_layer[layer].append(w)
            if h > 0.1:
                heights_by_layer[layer].append(h)
        except Exception:
            continue

    all_layers = sorted(set(widths_by_layer.keys()) | set(heights_by_layer.keys()))
    n = len(all_layers)
    if n == 0:
        ax = fig.add_subplot(1, 1, 1)
        ax.text(0.5, 0.5, 'Sem dados de LWPOLYLINE', color='#888888',
                ha='center', va='center', transform=ax.transAxes)
        setup_ax(ax)
        pdf.savefig(fig)
        plt.close(fig)
        return

    rows = min(n, 4)
    for idx, ly in enumerate(all_layers[:4]):
        ax1 = fig.add_subplot(rows, 2, idx * 2 + 1)
        ws = widths_by_layer.get(ly, [])
        if ws:
            ax1.hist(ws, bins=min(30, len(ws)), color=LAYER_COLORS.get(ly, '#888888'),
                     alpha=0.7, edgecolor='#333333')
        setup_ax(ax1, f'{ly} - Larguras (mm)')
        ax1.set_aspect('auto')
        ax1.tick_params(labelsize=5)

        ax2 = fig.add_subplot(rows, 2, idx * 2 + 2)
        hs = heights_by_layer.get(ly, [])
        if hs:
            ax2.hist(hs, bins=min(30, len(hs)), color=LAYER_COLORS.get(ly, '#888888'),
                     alpha=0.7, edgecolor='#333333')
        setup_ax(ax2, f'{ly} - Alturas (mm)')
        ax2.set_aspect('auto')
        ax2.tick_params(labelsize=5)

    fig.subplots_adjust(hspace=0.4, wspace=0.3, top=0.93, bottom=0.05)
    pdf.savefig(fig)
    plt.close(fig)

def page_synthesis(pdf, path, title, page_num=None, total=None):
    """Final synthesis: all layers overlaid (A3 landscape)."""
    tag = f'[Pg {page_num}/{total}]' if page_num else ''
    print(f'  {tag} {title}', flush=True)
    fig = fig_a3_landscape(title)
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.92])
    render_dxf(ax, path, title=None, alpha_override=0.7)
    # Add layer count annotation
    _, _, lc, entities, stats = load_dxf(path)
    top5 = sorted(stats.items(), key=lambda x: -x[1])[:5]
    info = '  |  '.join([f'{n}: {c}' for n, c in top5])
    ax.text(0.02, 0.02, f'Top layers: {info}', transform=ax.transAxes,
            color='#888888', fontsize=6, fontfamily='monospace')
    pdf.savefig(fig)
    plt.close(fig)

def page_insert_positions(pdf, path, layer_name, title, page_num=None, total=None, crop=None):
    """Show INSERT positions for a specific layer (A3 landscape)."""
    tag = f'[Pg {page_num}/{total}]' if page_num else ''
    print(f'  {tag} {title}', flush=True)

    doc, msp, lc, entities, stats = load_dxf(path)
    fig = fig_a3_landscape(title)
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.92])

    # Render base geometry faintly
    render_entities(ax, entities, lc, alpha_override=0.15, max_text=500)

    # Highlight inserts
    insert_xs, insert_ys, insert_names = [], [], []
    for e in entities:
        try:
            if e.dxftype() != 'INSERT':
                continue
            ly = getattr(e.dxf, 'layer', '0')
            if layer_name and ly != layer_name:
                # Also check block name
                bn = getattr(e.dxf, 'name', '')
                if bn != layer_name:
                    continue
            x, y = e.dxf.insert.x, e.dxf.insert.y
            insert_xs.append(x)
            insert_ys.append(y)
            insert_names.append(getattr(e.dxf, 'name', '?'))
        except Exception:
            continue

    if insert_xs:
        ax.scatter(insert_xs, insert_ys, c='#ff5555', s=15, marker='x', zorder=5, alpha=0.8)
        # Label a few
        for i in range(min(20, len(insert_xs))):
            ax.text(insert_xs[i], insert_ys[i], insert_names[i][:10],
                    color='#ff5555', fontsize=5, ha='left', va='bottom', zorder=6)

    bbox = compute_bbox(entities)
    if crop:
        ax.set_xlim(crop[0], crop[2])
        ax.set_ylim(crop[1], crop[3])
    else:
        ax.set_xlim(bbox[0], bbox[2])
        ax.set_ylim(bbox[1], bbox[3])
    setup_ax(ax)
    pdf.savefig(fig)
    plt.close(fig)

def page_text_layer(pdf, path, layer_names, title, page_num=None, total=None, crop=None):
    """Show text entities from specific layers (A4 portrait)."""
    tag = f'[Pg {page_num}/{total}]' if page_num else ''
    print(f'  {tag} {title}', flush=True)

    doc, msp, lc, entities, stats = load_dxf(path)
    fig = fig_a4_portrait(title)
    ax = fig.add_axes([0.05, 0.05, 0.9, 0.88])
    ax.set_facecolor(BG)
    ax.axis('off')

    y = 0.95
    for ln in layer_names:
        ax.text(0.02, y, f'Layer: {ln}', color='#e8b84b', fontsize=9, fontweight='bold',
                transform=ax.transAxes, fontfamily='monospace')
        y -= 0.025

    texts = []
    for e in entities:
        try:
            ly = getattr(e.dxf, 'layer', '0')
            if ly not in layer_names:
                continue
            et = e.dxftype()
            if et == 'TEXT':
                texts.append((ly, e.dxf.text, e.dxf.insert.x, e.dxf.insert.y))
            elif et == 'MTEXT':
                txt = e.plain_mtext() if hasattr(e, 'plain_mtext') else ''
                texts.append((ly, txt[:60], e.dxf.insert.x, e.dxf.insert.y))
        except Exception:
            continue

    for ly, txt, x, yp in texts[:50]:
        color = LAYER_COLORS.get(ly, '#ffffff')
        ax.text(0.05, y, f'({x:.0f}, {yp:.0f})  {txt[:55]}',
                color=color, fontsize=6, transform=ax.transAxes, fontfamily='monospace')
        y -= 0.018
        if y < 0.02:
            break

    pdf.savefig(fig)
    plt.close(fig)

def page_cota_layer(pdf, path, title, page_num=None, total=None):
    """Render COTA/cotas layer detail (A3 landscape)."""
    cota_layers = {'COTA', 'cotas', 'Cota'}
    page_layer_detail(pdf, path, cota_layers, title, page_num=page_num, total=total)

def page_layer_separated(pdf, path, title, page_num=None, total=None):
    """Single pillar detail showing all layers separated with labels (A4 portrait)."""
    tag = f'[Pg {page_num}/{total}]' if page_num else ''
    print(f'  {tag} {title}', flush=True)

    doc, msp, lc, entities, stats = load_dxf(path)
    fig = fig_a4_portrait(title)

    # Pick key layers to show individually
    key_layers = [
        ('Pain\u00e9is', 'Paineis'),
        ('CONCRETO',),
        ('SARR_2.2x7', 'Sarr 2.2x7'),
        ('CHAPA',),
        ('Perfil Met\u00e1lico',),
        ('Madeira', 'PONTALETE', 'MEIO_PONT'),
    ]
    labels = ['Paineis', 'Concreto', 'Sarrafos', 'Chapa', 'Perfil Met.', 'Madeira/Pont.']

    crop = PL_ZOOM_P1P2  # zoom on P1/P2 area
    n = len(key_layers)
    rows = math.ceil(n / 2)
    cols = 2

    for idx, (layer_set, label) in enumerate(zip(key_layers, labels)):
        ax = fig.add_subplot(rows, cols, idx + 1)
        render_entities(ax, entities, lc, show_layers=set(layer_set))
        ax.set_xlim(crop[0], crop[2])
        ax.set_ylim(crop[1], crop[3])
        setup_ax(ax, label)

    fig.subplots_adjust(hspace=0.25, wspace=0.15, top=0.93, bottom=0.03)
    pdf.savefig(fig)
    plt.close(fig)

# ---------------------------------------------------------------------------
# GENERATE ATLAS PILARES REAL (30 pages)
# ---------------------------------------------------------------------------
def generate_atlas_pilares(pdf_path):
    print(f'\n=== ATLAS PILARES REAL ({pdf_path.name}) ===', flush=True)
    T = 30
    pl0, pl1, pl2 = FILES_PL[0], FILES_PL[1], FILES_PL[2]

    with PdfPages(str(pdf_path)) as pdf:
        # Pg 1: CAPA
        print(f'  [Pg 1/{T}] Capa', flush=True)
        page_cover(pdf, 'PL', FILES_PL)

        # Pg 2: Indice de layers (Obra 1)
        print(f'  [Pg 2/{T}] Indice Layers Obra 1', flush=True)
        page_layer_index(pdf, pl0, obra_label(pl0))

        # Pg 3-5: DXF PL Obra 1 completo + zooms
        page_full_render(pdf, pl0, f'{obra_label(pl0)} - PL - Vista Completa',
                         page_num=3, total=T)
        page_zoom_render(pdf, pl0, f'{obra_label(pl0)} - PL - Linha Superior',
                         PL_ZOOM_FULL, page_num=4, total=T)
        page_zoom_render(pdf, pl0, f'{obra_label(pl0)} - PL - Zoom P1/P2',
                         PL_ZOOM_P1P2, page_num=5, total=T)

        # Pg 6-8: Zoom em pilares especificos areas
        # Compute midpoint regions for more zooms
        page_zoom_render(pdf, pl0, f'{obra_label(pl0)} - PL - Regiao Central',
                         (3500, 6000, 7500, 9000), page_num=6, total=T)
        page_zoom_render(pdf, pl0, f'{obra_label(pl0)} - PL - Regiao Inferior',
                         (3000, 600, 7000, 3500), page_num=7, total=T)
        page_zoom_render(pdf, pl0, f'{obra_label(pl0)} - PL - Regiao Detalhada',
                         (4500, 10000, 6500, 12000), page_num=8, total=T)

        # Pg 9: Detalhe de UM pilar - layers separadas
        page_layer_separated(pdf, pl0,
                             f'{obra_label(pl0)} - Detalhe Pilar por Camada',
                             page_num=9, total=T)

        # Pg 10: Legenda dos blocos
        doc0 = ezdxf.readfile(str(pl0))
        page_block_detail(pdf, doc0,
                          ['C', 'PONTALETE', 'MEIO PONTALETE', 'Fura\u00e7\u00e3o',
                           'titulo1', '9999999999'],
                          'Blocos Definidos no DXF PL', page_num=10, total=T)

        # Pg 11-13: DXF PL Obra 2 (GWT)
        page_full_render(pdf, pl1, f'{obra_label(pl1)} - PL - Vista Completa',
                         page_num=11, total=T)
        # Auto-detect bbox for obra 2
        _, _, _, ent1, _ = load_dxf(pl1)
        bb1 = compute_bbox(ent1)
        cx = (bb1[0] + bb1[2]) / 2
        cy = (bb1[1] + bb1[3]) / 2
        rng = max(bb1[2] - bb1[0], bb1[3] - bb1[1]) / 3
        page_zoom_render(pdf, pl1, f'{obra_label(pl1)} - PL - Zoom Centro',
                         (cx - rng, cy - rng, cx + rng, cy + rng), page_num=12, total=T)
        page_zoom_render(pdf, pl1, f'{obra_label(pl1)} - PL - Zoom Topo',
                         (bb1[0], bb1[3] - rng * 1.5, bb1[2], bb1[3]),
                         page_num=13, total=T)

        # Pg 14-16: DXF PL Obra 3 (LEAF)
        page_full_render(pdf, pl2, f'{obra_label(pl2)} - PL - Vista Completa',
                         page_num=14, total=T)
        _, _, _, ent2, _ = load_dxf(pl2)
        bb2 = compute_bbox(ent2)
        cx2 = (bb2[0] + bb2[2]) / 2
        cy2 = (bb2[1] + bb2[3]) / 2
        rng2 = max(bb2[2] - bb2[0], bb2[3] - bb2[1]) / 3
        page_zoom_render(pdf, pl2, f'{obra_label(pl2)} - PL - Zoom Centro',
                         (cx2 - rng2, cy2 - rng2, cx2 + rng2, cy2 + rng2),
                         page_num=15, total=T)
        page_zoom_render(pdf, pl2, f'{obra_label(pl2)} - PL - Zoom Detalhe',
                         (cx2 - rng2 / 2, cy2, cx2 + rng2 / 2, cy2 + rng2),
                         page_num=16, total=T)

        # Pg 17: Comparacao 3 obras
        page_comparison_3(pdf, FILES_PL, 'Comparacao 3 Obras - PL (Pilares)',
                          page_num=17, total=T)

        # Pg 18: Tabela dimensoes
        page_dimension_table(pdf, pl0, f'{obra_label(pl0)} - Dimensoes Reais Extraidas',
                             page_num=18, total=T)

        # Pg 19: CHAPA + Perfil Metalico
        page_layer_detail(pdf, pl0,
                          {'CHAPA', 'Perfil Met\u00e1lico'},
                          f'{obra_label(pl0)} - CHAPA + Perfil Metalico',
                          page_num=19, total=T, crop=PL_ZOOM_P1P2)

        # Pg 20: Hachura detail
        page_layer_detail(pdf, pl0,
                          {'Hachura', 'HACHURA MADEIRAS'},
                          f'{obra_label(pl0)} - Hachuras (ANSI31, SOLID, AR-CONC)',
                          page_num=20, total=T, crop=PL_ZOOM_P1P2)

        # Pg 21: Sarrafos por tipo
        page_layer_detail(pdf, pl0,
                          {'SARR_2.2x7', 'Sarr 2.2x7', 'SARR_3.5x7', 'SARR_7x7',
                           'SARR_7x10', 'SARR_2.2x10', 'SARR_2.2x15', 'SARR_2.2x20'},
                          f'{obra_label(pl0)} - Sarrafos por Tipo',
                          page_num=21, total=T, crop=PL_ZOOM_P1P2)

        # Pg 22: Blocos INSERT detalhados (positions)
        page_insert_positions(pdf, pl0, 'PONTALETE',
                              f'{obra_label(pl0)} - Posicoes INSERT (PONTALETE, C, etc.)',
                              page_num=22, total=T)

        # Pg 23: CONCRETO + BARRA ANCORAGEM
        page_layer_detail(pdf, pl0,
                          {'CONCRETO', 'BARRA ANCORAGEM', 'BARRA DE ANCORAGEM'},
                          f'{obra_label(pl0)} - Concreto + Barra Ancoragem',
                          page_num=23, total=T, crop=PL_ZOOM_P1P2)

        # Pg 24: NOMENCLATURA
        page_text_layer(pdf, pl0,
                        ['NOMENCLATURA', 'TEXTO_GERAL'],
                        f'{obra_label(pl0)} - Nomenclatura (PD, Nivel)',
                        page_num=24, total=T)

        # Pg 25: Texto Secao
        page_text_layer(pdf, pl0,
                        ['Texto Se\u00e7\u00e3o', 'TEXTO_GERAL'],
                        f'{obra_label(pl0)} - Texto Secao (P1.A, P1.B, etc.)',
                        page_num=25, total=T)

        # Pg 26: MEIO_PONT positions
        page_insert_positions(pdf, pl0, 'MEIO_PONT',
                              f'{obra_label(pl0)} - MEIO_PONT Posicoes',
                              page_num=26, total=T)

        # Pg 27: COTA layer
        page_cota_layer(pdf, pl0,
                        f'{obra_label(pl0)} - COTA (Dimensionamentos)',
                        page_num=27, total=T)

        # Pg 28: Histogramas
        page_histogram(pdf, pl0,
                       f'{obra_label(pl0)} - Analise Estatistica Dimensoes',
                       page_num=28, total=T)

        # Pg 29: Layers raras
        page_layer_detail(pdf, pl0,
                          {'GRAVATA', 'FELIPE', '00 - FELIPE', 'va165-sec',
                           'GARFOS', 'Forcador', '1-2 PONTALETE'},
                          f'{obra_label(pl0)} - Layers Raras',
                          page_num=29, total=T)

        # Pg 30: Sintese final
        page_synthesis(pdf, pl0,
                       f'{obra_label(pl0)} - Sintese Final (Todos Layers)',
                       page_num=30, total=T)

    print(f'  OK: {pdf_path}', flush=True)

# ---------------------------------------------------------------------------
# GENERATE ATLAS VIGAS REAL (30 pages)
# ---------------------------------------------------------------------------
def generate_atlas_vigas(pdf_path):
    print(f'\n=== ATLAS VIGAS REAL ({pdf_path.name}) ===', flush=True)
    T = 30
    lv0, lv1, lv2 = FILES_LV[0], FILES_LV[1], FILES_LV[2]
    fv0, fv1 = FILES_FV[0], FILES_FV[1]

    with PdfPages(str(pdf_path)) as pdf:
        # Pg 1: CAPA
        print(f'  [Pg 1/{T}] Capa', flush=True)
        page_cover(pdf, 'LV', FILES_LV + FILES_FV)

        # Pg 2: Indice layers LV
        print(f'  [Pg 2/{T}] Indice Layers LV Obra 1', flush=True)
        page_layer_index(pdf, lv0, f'{obra_label(lv0)} - LV')

        # Pg 3-5: DXF LV Obra 1
        page_full_render(pdf, lv0, f'{obra_label(lv0)} - LV - Vista Completa',
                         page_num=3, total=T)
        _, _, _, entlv0, _ = load_dxf(lv0)
        bblv0 = compute_bbox(entlv0)
        cx_lv = (bblv0[0] + bblv0[2]) / 2
        cy_lv = (bblv0[1] + bblv0[3]) / 2
        rng_lv = max(bblv0[2] - bblv0[0], bblv0[3] - bblv0[1]) / 3
        page_zoom_render(pdf, lv0, f'{obra_label(lv0)} - LV - Zoom Superior',
                         (bblv0[0], cy_lv, bblv0[2], bblv0[3]),
                         page_num=4, total=T)
        page_zoom_render(pdf, lv0, f'{obra_label(lv0)} - LV - Zoom Detalhe',
                         (cx_lv - rng_lv / 2, cy_lv - rng_lv / 2,
                          cx_lv + rng_lv / 2, cy_lv + rng_lv / 2),
                         page_num=5, total=T)

        # Pg 6-8: DXF LV Obra 2
        page_full_render(pdf, lv1, f'{obra_label(lv1)} - LV - Vista Completa',
                         page_num=6, total=T)
        _, _, _, entlv1, _ = load_dxf(lv1)
        bblv1 = compute_bbox(entlv1)
        cx1 = (bblv1[0] + bblv1[2]) / 2
        cy1 = (bblv1[1] + bblv1[3]) / 2
        rng1 = max(bblv1[2] - bblv1[0], bblv1[3] - bblv1[1]) / 3
        page_zoom_render(pdf, lv1, f'{obra_label(lv1)} - LV - Zoom Centro',
                         (cx1 - rng1, cy1 - rng1, cx1 + rng1, cy1 + rng1),
                         page_num=7, total=T)
        page_zoom_render(pdf, lv1, f'{obra_label(lv1)} - LV - Zoom Detalhe',
                         (cx1 - rng1 / 2, cy1, cx1 + rng1 / 2, cy1 + rng1),
                         page_num=8, total=T)

        # Pg 9-11: DXF LV Obra 3
        page_full_render(pdf, lv2, f'{obra_label(lv2)} - LV - Vista Completa',
                         page_num=9, total=T)
        _, _, _, entlv2, _ = load_dxf(lv2)
        bblv2 = compute_bbox(entlv2)
        cx2 = (bblv2[0] + bblv2[2]) / 2
        cy2 = (bblv2[1] + bblv2[3]) / 2
        rng2 = max(bblv2[2] - bblv2[0], bblv2[3] - bblv2[1]) / 3
        page_zoom_render(pdf, lv2, f'{obra_label(lv2)} - LV - Zoom Centro',
                         (cx2 - rng2, cy2 - rng2, cx2 + rng2, cy2 + rng2),
                         page_num=10, total=T)
        page_zoom_render(pdf, lv2, f'{obra_label(lv2)} - LV - Zoom Detalhe',
                         (cx2 - rng2 / 2, cy2, cx2 + rng2 / 2, cy2 + rng2),
                         page_num=11, total=T)

        # Pg 12: Detalhe paineis
        page_layer_detail(pdf, lv0,
                          {'Pain\u00e9is', 'Paineis'},
                          f'{obra_label(lv0)} - LV - Paineis (distribuicao W,H)',
                          page_num=12, total=T)

        # Pg 13: SARR_2.2x7
        page_layer_detail(pdf, lv0,
                          {'SARR_2.2x7', 'Sarr 2.2x7'},
                          f'{obra_label(lv0)} - LV - SARR_2.2x7 (Linhas Laterais)',
                          page_num=13, total=T)

        # Pg 14: CONCRETO
        page_layer_detail(pdf, lv0,
                          {'CONCRETO'},
                          f'{obra_label(lv0)} - LV - CONCRETO (Secao Viga)',
                          page_num=14, total=T)

        # Pg 15: PRESILHA METALICA blocos
        doc_lv0 = ezdxf.readfile(str(lv0))
        page_block_detail(pdf, doc_lv0,
                          ['PRESILHA MET\u00c1LICA 1', 'PRESILHA MET\u00c1LICA 2',
                           'PRESILHA METALICA 1', 'PRESILHA METALICA 2',
                           'HT20CT'],
                          f'{obra_label(lv0)} - Blocos Vigas (Presilha, HT20CT)',
                          page_num=15, total=T)

        # Pg 16: HT20CT insert positions
        page_insert_positions(pdf, lv0, 'HT20CT',
                              f'{obra_label(lv0)} - LV - HT20CT (Escora) Posicoes',
                              page_num=16, total=T)

        # Pg 17: Comparacao 3 obras LV
        page_comparison_3(pdf, FILES_LV,
                          'Comparacao 3 Obras - LV (Laterais Vigas)',
                          page_num=17, total=T)

        # Pg 18: FV DXF Obra 1
        page_full_render(pdf, fv0, f'{obra_label(fv0)} - FV - Fundo Viga Completo',
                         page_num=18, total=T)

        # Pg 19: FV DXF Obra 2
        page_full_render(pdf, fv1, f'{obra_label(fv1)} - FV - Fundo Viga Completo',
                         page_num=19, total=T)

        # Pg 20: Layer '5' (BLUE) - labels P1/V9
        page_layer_detail(pdf, lv0,
                          {'5'},
                          f'{obra_label(lv0)} - LV - Layer 5 (Labels P1/V9)',
                          page_num=20, total=T)

        # Pg 21: SARR_3.5x7 vs SARR_2.2x7
        page_layer_detail(pdf, lv0,
                          {'SARR_3.5x7', 'SARR_2.2x7', 'Sarr 2.2x7'},
                          f'{obra_label(lv0)} - LV - SARR_3.5x7 vs SARR_2.2x7',
                          page_num=21, total=T)

        # Pg 22: REAPROVEITAMENTO
        page_layer_detail(pdf, lv0,
                          {'REAPROVEITAMENTO'},
                          f'{obra_label(lv0)} - LV - REAPROVEITAMENTO',
                          page_num=22, total=T)

        # Pg 23: Escoras e Forcador
        page_layer_detail(pdf, lv0,
                          {'Escoras', 'Forcador'},
                          f'{obra_label(lv0)} - LV - Escoras + Forcador',
                          page_num=23, total=T)

        # Pg 24: TENSOR + GARFOS
        page_layer_detail(pdf, lv0,
                          {'TENSOR', 'GARFOS'},
                          f'{obra_label(lv0)} - LV - TENSOR (verde) + GARFOS',
                          page_num=24, total=T)

        # Pg 25-27: Detalhes adicionais de cada obra (dimensions)
        page_dimension_table(pdf, lv0, f'{obra_label(lv0)} - LV - Dimensoes',
                             page_num=25, total=T)
        page_dimension_table(pdf, lv1, f'{obra_label(lv1)} - LV - Dimensoes',
                             page_num=26, total=T)
        page_dimension_table(pdf, lv2, f'{obra_label(lv2)} - LV - Dimensoes',
                             page_num=27, total=T)

        # Pg 28: Hachura vigas
        page_layer_detail(pdf, lv0,
                          {'Hachura', 'HACHURA MADEIRAS'},
                          f'{obra_label(lv0)} - LV - Hachuras',
                          page_num=28, total=T)

        # Pg 29: Estatisticas
        page_histogram(pdf, lv0,
                       f'{obra_label(lv0)} - LV - Analise Dimensional',
                       page_num=29, total=T)

        # Pg 30: Sintese
        page_synthesis(pdf, lv0,
                       f'{obra_label(lv0)} - LV - Sintese Final',
                       page_num=30, total=T)

    print(f'  OK: {pdf_path}', flush=True)

# ---------------------------------------------------------------------------
# GENERATE ATLAS LAJES REAL (15 pages)
# ---------------------------------------------------------------------------
def generate_atlas_lajes(pdf_path):
    print(f'\n=== ATLAS LAJES REAL ({pdf_path.name}) ===', flush=True)
    T = 15
    lj0, lj1, lj2 = FILES_LJ[0], FILES_LJ[1], FILES_LJ[2]

    with PdfPages(str(pdf_path)) as pdf:
        # Pg 1: CAPA
        print(f'  [Pg 1/{T}] Capa', flush=True)
        page_cover(pdf, 'LJ', FILES_LJ)

        # Pg 2: DXF LJ Obra 1 completo
        page_full_render(pdf, lj0, f'{obra_label(lj0)} - LJ - Vista Completa',
                         page_num=2, total=T)

        # Pg 3: DXF LJ Obra 2
        page_full_render(pdf, lj1, f'{obra_label(lj1)} - LJ - Vista Completa',
                         page_num=3, total=T)

        # Pg 4: DXF LJ Obra 3
        page_full_render(pdf, lj2, f'{obra_label(lj2)} - LJ - Vista Completa',
                         page_num=4, total=T)

        # Pg 5: Comparacao 3 obras
        page_comparison_3(pdf, FILES_LJ, 'Comparacao 3 Obras - LJ (Lajes)',
                          page_num=5, total=T)

        # Pg 6: Layer Pilares
        page_layer_detail(pdf, lj0,
                          {'Pilares'},
                          f'{obra_label(lj0)} - LJ - Pilares (contornos na laje)',
                          page_num=6, total=T)

        # Pg 7: Layer VIGAS
        page_layer_detail(pdf, lj0,
                          {'VIGAS'},
                          f'{obra_label(lj0)} - LJ - VIGAS',
                          page_num=7, total=T)

        # Pg 8: Layer SARRAFO DE PRESSAO
        page_layer_detail(pdf, lj0,
                          {'SARRAFO DE PRESSAO', 'Sarrafo de Press\u00e3o'},
                          f'{obra_label(lj0)} - LJ - Sarrafo de Pressao',
                          page_num=8, total=T)

        # Pg 9: Layer REAPROVEITAMENTO
        page_layer_detail(pdf, lj0,
                          {'REAPROVEITAMENTO'},
                          f'{obra_label(lj0)} - LJ - Reaproveitamento',
                          page_num=9, total=T)

        # Pg 10: Paineis da laje
        page_layer_detail(pdf, lj0,
                          {'Pain\u00e9is', 'Paineis'},
                          f'{obra_label(lj0)} - LJ - Paineis (W, H)',
                          page_num=10, total=T)

        # Pg 11: Hatches
        page_layer_detail(pdf, lj0,
                          {'Hachura', 'HACHURA MADEIRAS'},
                          f'{obra_label(lj0)} - LJ - Hachuras',
                          page_num=11, total=T)

        # Pg 12: COTA
        page_cota_layer(pdf, lj0,
                        f'{obra_label(lj0)} - LJ - Dimensionamentos (COTA)',
                        page_num=12, total=T)

        # Pg 13: Legenda completa dos layers (Obra 2 for variety)
        print(f'  [Pg 13/{T}] Indice Layers Obra 2', flush=True)
        page_layer_index(pdf, lj1, f'{obra_label(lj1)} - LJ')

        # Pg 14: Analise dimensional
        page_dimension_table(pdf, lj0,
                             f'{obra_label(lj0)} - LJ - Dimensoes Extraidas',
                             page_num=14, total=T)

        # Pg 15: Sintese
        page_synthesis(pdf, lj0,
                       f'{obra_label(lj0)} - LJ - Sintese Final',
                       page_num=15, total=T)

    print(f'  OK: {pdf_path}', flush=True)

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print('=' * 60)
    print('ATLAS DXF REAL -- Renderizacao Direta de DXFs')
    print(f'Data: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)

    # Validate all files exist
    all_files = FILES_PL + FILES_LV + FILES_LJ + FILES_FV
    missing = [f for f in all_files if not f.exists()]
    if missing:
        print(f'\nATENCAO: {len(missing)} arquivo(s) nao encontrado(s):')
        for f in missing:
            print(f'  FALTANDO: {f}')
        # Continue with available files
        available_pl = [f for f in FILES_PL if f.exists()]
        available_lv = [f for f in FILES_LV if f.exists()]
        available_lj = [f for f in FILES_LJ if f.exists()]
        available_fv = [f for f in FILES_FV if f.exists()]
        if not available_pl and not available_lv and not available_lj:
            print('\nERRO: Nenhum DXF disponivel. Abortando.')
            sys.exit(1)
    else:
        print(f'\nTodos os {len(all_files)} DXFs encontrados.')

    # Generate atlases
    try:
        if all(f.exists() for f in FILES_PL):
            generate_atlas_pilares(OUT_DIR / 'atlas_pilares_real.pdf')
        else:
            print('\nSKIP atlas_pilares_real.pdf (DXFs PL faltando)')
    except Exception as ex:
        print(f'\nERRO atlas pilares: {ex}')
        traceback.print_exc()

    try:
        if all(f.exists() for f in FILES_LV) and all(f.exists() for f in FILES_FV):
            generate_atlas_vigas(OUT_DIR / 'atlas_vigas_real.pdf')
        else:
            print('\nSKIP atlas_vigas_real.pdf (DXFs LV/FV faltando)')
    except Exception as ex:
        print(f'\nERRO atlas vigas: {ex}')
        traceback.print_exc()

    try:
        if all(f.exists() for f in FILES_LJ):
            generate_atlas_lajes(OUT_DIR / 'atlas_lajes_real.pdf')
        else:
            print('\nSKIP atlas_lajes_real.pdf (DXFs LJ faltando)')
    except Exception as ex:
        print(f'\nERRO atlas lajes: {ex}')
        traceback.print_exc()

    print('\n' + '=' * 60)
    print('CONCLUIDO')
    for name in ['atlas_pilares_real.pdf', 'atlas_vigas_real.pdf', 'atlas_lajes_real.pdf']:
        p = OUT_DIR / name
        if p.exists():
            size_mb = p.stat().st_size / (1024 * 1024)
            print(f'  {p}  ({size_mb:.1f} MB)')
        else:
            print(f'  {p}  (NAO GERADO)')
    print('=' * 60)

if __name__ == '__main__':
    main()
