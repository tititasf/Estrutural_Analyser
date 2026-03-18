"""
Renderiza combinado_v32.dxf usando o renderer REAL do ezdxf (matplotlib backend).
Renderiza o grid completo em seções verticais (linhas de células).
Identifica pedaços soltos detectando elementos fora do cluster principal.
"""
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os, math

DXF_PATH = r"D:\Agente-cad-PYSIDE\ANALISE_LV\combined\combined_v32.dxf"
OUT_DIR   = r"D:\Agente-cad-PYSIDE\ANALISE_LV\vision_real"
os.makedirs(OUT_DIR, exist_ok=True)

CELL_W = 2900
CELL_H = 1800
MARGIN = 80
COLS   = 12

doc  = ezdxf.readfile(DXF_PATH)
msp  = doc.modelspace()

# Identifica clusters por célula usando a coordenada real
# Convenção correta:
# Célula (col, row) tem target_y = -row*CELL_H
# Célula spans x=[col*CELL_W, col*CELL_W+CELL_W], y=[target_y, target_y+CELL_H]
def cell_for_point(px, py):
    col = int(px // CELL_W)
    # target_y = -row*CELL_H → row = -target_y/CELL_H
    # O ponto está na célula row R se: -R*CELL_H <= py <= -(R-1)*CELL_H
    # Equivalente: R*CELL_H >= -py >= (R-1)*CELL_H
    # target_y = -R*CELL_H → R = floor(-py / CELL_H) se py < 0
    # Para py >= 0: R = 0 (row 0 spans y=[0, CELL_H])
    if py >= 0:
        row = 0
    else:
        row = int((-py - 1) // CELL_H) + 1  # correct formula
    return col, row

# Coletar todos os pontos por célula (ex: centroide de cada entity)
def entity_centroid(e):
    try:
        t = e.dxftype()
        if t == 'LINE':
            return ((e.dxf.start.x+e.dxf.end.x)/2, (e.dxf.start.y+e.dxf.end.y)/2)
        elif t == 'LWPOLYLINE':
            pts = list(e.get_points())
            if pts: return (sum(p[0] for p in pts)/len(pts), sum(p[1] for p in pts)/len(pts))
        elif t == 'TEXT':
            return (e.dxf.insert.x, e.dxf.insert.y)
        elif t == 'MTEXT':
            return (e.dxf.insert.x, e.dxf.insert.y)
        elif t == 'INSERT':
            return (e.dxf.insert.x, e.dxf.insert.y)
        elif t == 'HATCH':
            all_pts = []
            for path in e.paths:
                if hasattr(path, 'vertices'): all_pts.extend(path.vertices)
                for edge in (path.edges if hasattr(path, 'edges') else []):
                    if hasattr(edge, 'start'): all_pts.append(edge.start)
                    if hasattr(edge, 'end'):   all_pts.append(edge.end)
            if all_pts: return (sum(p[0] for p in all_pts)/len(all_pts), sum(p[1] for p in all_pts)/len(all_pts))
        elif t == 'CIRCLE':
            return (e.dxf.center.x, e.dxf.center.y)
        elif t == 'ARC':
            return (e.dxf.center.x, e.dxf.center.y)
        elif t == 'DIMENSION':
            return (e.dxf.defpoint.x, e.dxf.defpoint.y)
    except:
        pass
    return None

# Coletar entidades por célula (excluindo CELL_BORDER e LABEL_ID)
from collections import defaultdict
cell_data = defaultdict(list)  # (col, row) -> list of (cx, cy, layer, etype)

SKIP_LAYERS = {'CELL_BORDER', 'LABEL_ID'}

for e in msp:
    try: lyr = e.dxf.layer
    except: lyr = ''
    if lyr in SKIP_LAYERS:
        continue
    c = entity_centroid(e)
    if c is None:
        continue
    cx, cy = c
    col, row = cell_for_point(cx, cy)
    if col < 0 or row < 0 or col >= COLS:
        continue
    # Offset relativo à célula
    target_y = -row * CELL_H
    off_x = cx - col * CELL_W
    off_y = cy - target_y  # relativo ao bottom da célula
    cell_data[(col, row)].append((off_x, off_y, lyr, e.dxftype()))

print(f"Total células com dados: {len(cell_data)}")

# Detectar pedaços soltos: elementos x-offset separados por >= 600u
# excluindo COTA (dimensões que tipicamente têm linha full-width)
IGNORE_FOR_GAP = {'COTA', 'Cota Seção (2x)', 'COTA_H'}
GAP_THRESHOLD = 600

problems = []
for (col, row), items in sorted(cell_data.items()):
    # Filtrar só elementos relevantes para gap (excluir COTA pq têm linhas de dimensão)
    relevant = [(ox, oy, lyr, t) for ox, oy, lyr, t in items
                if lyr not in IGNORE_FOR_GAP]
    if len(relevant) < 2:
        continue

    # Ordenar por off_x
    xs = sorted(ox for ox, oy, lyr, t in relevant)
    if not xs:
        continue

    # Encontrar maior gap em X
    gaps = [(xs[i+1] - xs[i], i) for i in range(len(xs)-1)]
    if not gaps:
        continue
    max_gap, gap_idx = max(gaps)

    if max_gap < GAP_THRESHOLD:
        continue

    left_max = xs[gap_idx]
    right_min = xs[gap_idx+1]

    # Identificar os elementos isolados (lado menor)
    left_items  = [(ox,oy,lyr,t) for ox,oy,lyr,t in relevant if ox <= left_max]
    right_items = [(ox,oy,lyr,t) for ox,oy,lyr,t in relevant if ox >= right_min]

    if len(left_items) <= len(right_items) and len(left_items) <= 3:
        isolated = left_items; main = right_items; side='left'
    elif len(right_items) <= len(left_items) and len(right_items) <= 3:
        isolated = right_items; main = left_items; side='right'
    else:
        continue  # Ambos os lados grandes — skip

    iso_layers = list(set(lyr for _,_,lyr,_ in isolated))
    iso_xs = sorted(ox for ox,_,_,_ in isolated)

    problems.append({
        'col': col, 'row': row, 'gap': max_gap,
        'iso_xs': iso_xs, 'iso_layers': iso_layers,
        'side': side
    })

print(f"\nProblemas detectados (excluindo COTA, gap>={GAP_THRESHOLD}u):")
for p in problems:
    print(f"  ({p['col']},{p['row']}) gap={p['gap']:.0f} side={p['side']} layers={p['iso_layers']} xs={[f'{x:.0f}' for x in p['iso_xs']]}")

print(f"\nTotal: {len(problems)} células problemáticas")

# Renderiza cada célula problemática usando ezdxf drawing engine
print("\nRenderizando células problemáticas...")

def render_cell_real(col, row, out_path):
    """Renderiza célula usando ezdxf drawing engine real."""
    target_x = col * CELL_W
    target_y = -row * CELL_H

    # Cria um doc temporário com apenas esta célula
    tdoc = ezdxf.new('R2000')
    # Copia layers
    for lname, ldef in doc.layers.items():
        if lname not in tdoc.layers:
            try: tdoc.layers.add(lname, color=ldef.dxf.color)
            except: pass
    tmsp = tdoc.modelspace()

    # Copia entidades dentro ou próximas da célula
    margin_ext = 100
    x0, x1 = target_x - margin_ext, target_x + CELL_W + margin_ext
    y0, y1 = target_y - margin_ext, target_y + CELL_H + margin_ext

    for e in msp:
        try: lyr = e.dxf.layer
        except: continue
        if lyr == 'CELL_BORDER':
            # Adiciona só o border desta célula
            c = entity_centroid(e)
            if c and abs(c[0] - (target_x + CELL_W/2)) < CELL_W/2 + 10:
                tmsp.add_lwpolyline(
                    [(target_x, target_y), (target_x+CELL_W, target_y),
                     (target_x+CELL_W, target_y+CELL_H), (target_x, target_y+CELL_H)],
                    close=True, dxfattribs={'layer': 'CELL_BORDER'})
            continue
        c = entity_centroid(e)
        if c and x0 <= c[0] <= x1 and y0 <= c[1] <= y1:
            try: tmsp.add_entity(e.copy())
            except: pass

    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(tdoc)
    out = MatplotlibBackend(ax)
    try:
        Frontend(ctx, out).draw_layout(tmsp)
    except Exception as ex:
        print(f"    draw error: {ex}")

    # Adicionar marcação da célula
    ax.set_xlim(target_x - 200, target_x + CELL_W + 200)
    ax.set_ylim(target_y - 200, target_y + CELL_H + 200)
    ax.set_aspect('equal')
    ax.set_facecolor('#1a1a1a')
    ax.set_title(f'Célula ({col},{row}) — real render', color='white', fontsize=9)
    fig.patch.set_facecolor('#1a1a1a')

    plt.savefig(out_path, dpi=120, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()

# Renderiza as top 15 células problemáticas
for i, p in enumerate(problems[:15]):
    out_path = os.path.join(OUT_DIR, f"real_cell_{p['col']}_{p['row']}.png")
    try:
        render_cell_real(p['col'], p['row'], out_path)
        print(f"  Salvo: {out_path}")
    except Exception as ex:
        print(f"  ERRO ({p['col']},{p['row']}): {ex}")

print("\nDONE")
