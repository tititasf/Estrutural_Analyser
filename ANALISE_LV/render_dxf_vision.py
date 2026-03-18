"""
Renderiza combined_v32.dxf como imagem PNG para análise visual autônoma.
Gera: 1 imagem geral + imagens individuais de células suspeitas.
"""
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import os

DXF_PATH = r"D:\Agente-cad-PYSIDE\ANALISE_LV\combined\combined_v32.dxf"
OUT_DIR   = r"D:\Agente-cad-PYSIDE\ANALISE_LV\vision_renders"
os.makedirs(OUT_DIR, exist_ok=True)

CELL_W = 2900
CELL_H = 1800
MARGIN = 80
COLS   = 12

doc  = ezdxf.readfile(DXF_PATH)
msp  = doc.modelspace()

# --- coleta todas as entidades com bbox ---
def entity_bbox(e):
    """Retorna (xmin, ymin, xmax, ymax) ou None."""
    try:
        t = e.dxftype()
        if t == 'LINE':
            xs = [e.dxf.start.x, e.dxf.end.x]
            ys = [e.dxf.start.y, e.dxf.end.y]
        elif t in ('LWPOLYLINE','POLYLINE'):
            pts = list(e.vertices() if t == 'POLYLINE' else e.get_points())
            if not pts: return None
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
        elif t == 'HATCH':
            all_pts = []
            for path in e.paths:
                for edge in (path.edges if hasattr(path,'edges') else []):
                    if hasattr(edge,'start'): all_pts.append(edge.start)
                    if hasattr(edge,'end'):   all_pts.append(edge.end)
                if hasattr(path,'vertices'):
                    all_pts.extend(path.vertices)
            if not all_pts: return None
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
        elif t == 'INSERT':
            xs = [e.dxf.insert.x]; ys = [e.dxf.insert.y]
        elif t == 'TEXT':
            xs = [e.dxf.insert.x]; ys = [e.dxf.insert.y]
        elif t == 'MTEXT':
            xs = [e.dxf.insert.x]; ys = [e.dxf.insert.y]
        elif t == 'CIRCLE':
            cx,cy,r = e.dxf.center.x, e.dxf.center.y, e.dxf.radius
            xs = [cx-r, cx+r]; ys = [cy-r, cy+r]
        elif t == 'ARC':
            cx,cy,r = e.dxf.center.x, e.dxf.center.y, e.dxf.radius
            xs = [cx-r, cx+r]; ys = [cy-r, cy+r]
        elif t == 'DIMENSION':
            xs = [e.dxf.defpoint.x]; ys = [e.dxf.defpoint.y]
        elif t == 'SPLINE':
            cps = list(e.control_points)
            if not cps: return None
            xs = [p[0] for p in cps]; ys = [p[1] for p in cps]
        elif t == 'ELLIPSE':
            cx,cy = e.dxf.center.x, e.dxf.center.y
            r = max(abs(e.dxf.ratio), 1) * e.dxf.major_axis.magnitude
            xs = [cx-r, cx+r]; ys = [cy-r, cy+r]
        else:
            return None
        return min(xs), min(ys), max(xs), max(ys)
    except Exception:
        return None

# Agrupa por célula
cell_entities = {}  # (col, row) -> list of (bbox, layer)
for e in msp:
    bb = entity_bbox(e)
    if bb is None: continue
    cx = (bb[0] + bb[2]) / 2
    cy = (bb[1] + bb[3]) / 2
    col = int(cx // CELL_W)
    row = int(-cy // CELL_H)
    k = (col, row)
    if k not in cell_entities:
        cell_entities[k] = []
    try:
        lyr = e.dxf.layer
    except Exception:
        lyr = ''
    cell_entities[k].append((bb, lyr))

print(f"Total células com entidades: {len(cell_entities)}")

# --- Detecta células com "pedaços soltos" ---
# Critério: dentro da célula, há um grupo de entidades cujo centroide
# está separado por >= 600u do grupo principal
def find_isolated(bbs):
    """Retorna (isolated_bbs, main_bbs) baseado em gap."""
    offsets = sorted([(bb[0]+bb[2])/2 - col*CELL_W for bb, _ in bbs])
    if len(offsets) < 2: return [], bbs
    # maior gap
    gaps = [(offsets[i+1]-offsets[i], i) for i in range(len(offsets)-1)]
    max_gap, idx = max(gaps)
    if max_gap < 600: return [], bbs
    left_off  = offsets[:idx+1]
    right_off = offsets[idx+1:]
    # lado menor = isolado
    if len(left_off) <= len(right_off):
        isolated = [(bb,l) for bb,l in bbs
                    if (bb[0]+bb[2])/2 - col*CELL_W in left_off]
        main = [(bb,l) for bb,l in bbs
                if (bb[0]+bb[2])/2 - col*CELL_W not in left_off]
    else:
        isolated = [(bb,l) for bb,l in bbs
                    if (bb[0]+bb[2])/2 - col*CELL_W in right_off]
        main = [(bb,l) for bb,l in bbs
                if (bb[0]+bb[2])/2 - col*CELL_W not in right_off]
    return isolated, main

problem_cells = []
for (col, row), bbs in sorted(cell_entities.items()):
    isolated, main = find_isolated(bbs)
    if isolated:
        iso_offs = sorted([(bb[0]+bb[2])/2 - col*CELL_W for bb,_ in isolated])
        main_offs = sorted([(bb[0]+bb[2])/2 - col*CELL_W for bb,_ in main])
        layers_iso = list(set(l for _,l in isolated))
        gap = min(main_offs) - max(iso_offs) if max(iso_offs) < min(main_offs) else min(iso_offs) - max(main_offs)
        problem_cells.append((col, row, gap, iso_offs, main_offs, layers_iso))
        print(f"  PROBLEMA ({col},{row}): gap={gap:.0f} iso_offs={[f'{x:.0f}' for x in iso_offs]} layers={layers_iso}")

print(f"\nTotal células com fragmentos isolados: {len(problem_cells)}")

# --- Renderiza cada célula-problema como imagem ---
def render_cell(col, row, bbs, title, out_path):
    fig, ax = plt.subplots(figsize=(10, 6))
    cx_base = col * CELL_W
    cy_base = -row * CELL_H

    # borda da célula
    rect = patches.Rectangle((MARGIN, -(CELL_H-MARGIN)),
                               CELL_W-2*MARGIN, CELL_H-2*MARGIN,
                               linewidth=2, edgecolor='blue', facecolor='none', linestyle='--')
    # Translata para coordenadas relativas à célula
    rect2 = patches.Rectangle((cx_base+MARGIN, cy_base-(CELL_H-MARGIN)),
                               CELL_W-2*MARGIN, CELL_H-2*MARGIN,
                               linewidth=2, edgecolor='blue', facecolor='none', linestyle='--')
    ax.add_patch(rect2)

    colors = {'HATCH': 'orange', 'COTA': 'red', 'CONCRETO': 'green',
              'EIXO': 'cyan', 'Painéis': 'purple', '': 'gray'}
    for bb, lyr in bbs:
        color = colors.get(lyr, 'black')
        w = max(bb[2]-bb[0], 1)
        h = max(bb[3]-bb[1], 1)
        r = patches.Rectangle((bb[0], bb[1]), w, h,
                               linewidth=1, edgecolor=color, facecolor=color, alpha=0.4)
        ax.add_patch(r)

    ax.set_xlim(cx_base - 50, cx_base + CELL_W + 50)
    ax.set_ylim(cy_base - CELL_H - 50, cy_base + 50)
    ax.set_aspect('equal')
    ax.set_title(title, fontsize=10)
    ax.grid(True, alpha=0.3)

    # linha vertical da borda esquerda e direita da célula
    ax.axvline(cx_base, color='blue', alpha=0.5, linewidth=1)
    ax.axvline(cx_base + CELL_W, color='blue', alpha=0.5, linewidth=1)

    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight')
    plt.close()

for col, row, gap, iso_offs, main_offs, layers_iso in problem_cells:
    k = (col, row)
    bbs = cell_entities.get(k, [])
    title = f"Célula ({col},{row}) — gap={gap:.0f}u — layers isolados: {layers_iso}"
    out_path = os.path.join(OUT_DIR, f"cell_{col}_{row}.png")
    render_cell(col, row, bbs, title, out_path)
    print(f"  Salvo: {out_path}")

# --- Renderiza visão geral do grid ---
print("\nRenderizando visão geral...")
fig, ax = plt.subplots(figsize=(24, 80))
for (col, row), bbs in cell_entities.items():
    cx_base = col * CELL_W
    cy_base = -row * CELL_H
    for bb, lyr in bbs:
        color = 'black'
        w = max(bb[2]-bb[0], 0.5)
        h = max(bb[3]-bb[1], 0.5)
        r = patches.Rectangle((bb[0], bb[1]), w, h,
                               linewidth=0.3, edgecolor=color, facecolor='gray', alpha=0.3)
        ax.add_patch(r)

# Marca células problemáticas
for col, row, gap, iso_offs, main_offs, layers_iso in problem_cells:
    cx_base = col * CELL_W
    cy_base = -row * CELL_H
    rect = patches.Rectangle((cx_base, cy_base - CELL_H),
                               CELL_W, CELL_H,
                               linewidth=2, edgecolor='red', facecolor='red', alpha=0.1)
    ax.add_patch(rect)
    ax.text(cx_base + CELL_W/2, cy_base - CELL_H/2,
            f"({col},{row})", ha='center', va='center', fontsize=6, color='red')

ax.set_aspect('equal')
ax.autoscale()
ax.set_title(f'combined_v32.dxf — {len(problem_cells)} células problemáticas (vermelho)')
plt.tight_layout()
overview_path = os.path.join(OUT_DIR, "overview.png")
plt.savefig(overview_path, dpi=80, bbox_inches='tight')
plt.close()
print(f"Salvo: {overview_path}")
print("DONE")
