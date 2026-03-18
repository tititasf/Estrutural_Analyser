#!/usr/bin/env python3
"""Render top problematic cells from the combined DXF, showing clusters visually.

For each cell:
- Main cluster entities in blue
- Secondary (isolated) cluster entities in red
- Cell boundary in gray dashed
- Legend with cell label, cluster sizes, and distance

Output: PNG images in vision_v37/ directory.
"""
import sys, io, math
if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import defaultdict
from pathlib import Path

# --- Config ---
DXF_FILE = Path('D:/Agente-cad-PYSIDE/ANALISE_LV/combined/combined_v37.dxf')
OUT_DIR = Path('D:/Agente-cad-PYSIDE/ANALISE_LV/vision_v37')
CELL_W = 2900
CELL_H = 1800
EPS = 250
TOP_N = 12
IGNORE_LAYERS = {'CELL_BORDER', 'LABEL_ID', 'COTA', 'COTA_H',
                 'Cota Se\u00e7\u00e3o (2x)', 'Texto Se\u00e7\u00e3o'}


class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx == ry: return
        if self.rank[rx] < self.rank[ry]: rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]: self.rank[rx] += 1


def extract_entity_points(entity):
    """Extract points from a DXF entity."""
    etype = entity.dxftype()
    points = []
    if etype == 'LINE':
        p1 = entity.dxf.start; p2 = entity.dxf.end
        points = [(p1.x, p1.y), (p2.x, p2.y)]
    elif etype == 'LWPOLYLINE':
        with entity.points('xy') as pts:
            points = [(p[0], p[1]) for p in pts]
    elif etype in ('TEXT', 'MTEXT'):
        ins = entity.dxf.insert
        points = [(ins.x, ins.y)]
    elif etype == 'HATCH':
        try:
            for path in entity.paths:
                if hasattr(path, 'vertices'):
                    for v in path.vertices:
                        points.append((v[0], v[1]))
                elif hasattr(path, 'edges'):
                    for edge in path.edges:
                        if hasattr(edge, 'start'):
                            points.append((edge.start[0], edge.start[1]))
                        if hasattr(edge, 'end'):
                            points.append((edge.end[0], edge.end[1]))
        except Exception:
            pass
    return points


def cluster_entities(entities, eps):
    """Run Union-Find spatial clustering on entity points."""
    all_pts = []
    for idx, ent in enumerate(entities):
        for p in ent['points']:
            all_pts.append((p[0], p[1], idx))

    if len(all_pts) < 2:
        return {0: set(range(len(entities)))}, 0

    n = len(all_pts)
    uf = UnionFind(n)

    grid = defaultdict(list)
    for i, (x, y, _) in enumerate(all_pts):
        gx, gy = int(x // eps), int(y // eps)
        grid[(gx, gy)].append(i)

    for i, (x1, y1, _) in enumerate(all_pts):
        gx, gy = int(x1 // eps), int(y1 // eps)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), []):
                    if j <= i: continue
                    x2, y2 = all_pts[j][0], all_pts[j][1]
                    if (x1 - x2)**2 + (y1 - y2)**2 <= eps**2:
                        uf.union(i, j)

    entity_clusters = defaultdict(lambda: defaultdict(int))
    for i, (_, _, eidx) in enumerate(all_pts):
        cl = uf.find(i)
        entity_clusters[eidx][cl] += 1

    entity_to_cluster = {}
    for eidx, cl_counts in entity_clusters.items():
        entity_to_cluster[eidx] = max(cl_counts, key=cl_counts.get)

    cluster_entity_sets = defaultdict(set)
    for eidx, cl in entity_to_cluster.items():
        cluster_entity_sets[cl].add(eidx)

    main_cluster = max(cluster_entity_sets, key=lambda c: len(cluster_entity_sets[c]))

    # Compute min distance from each secondary cluster to main
    main_pts = [(all_pts[i][0], all_pts[i][1]) for i in range(n)
                if entity_to_cluster.get(all_pts[i][2]) == main_cluster]

    sec_dists = {}
    for cl, ents in cluster_entity_sets.items():
        if cl == main_cluster:
            continue
        sec_pts = [(all_pts[i][0], all_pts[i][1]) for i in range(n)
                   if entity_to_cluster.get(all_pts[i][2]) == cl]
        min_d = float('inf')
        for sx, sy in sec_pts:
            for mx, my in main_pts:
                d = math.sqrt((sx - mx)**2 + (sy - my)**2)
                if d < min_d:
                    min_d = d
                    if d <= eps:
                        break
            if min_d <= eps:
                break
        if min_d > eps:
            sec_dists[cl] = min_d

    return cluster_entity_sets, main_cluster, entity_to_cluster, sec_dists


def render_cell(entities, cell_key, label, cluster_entity_sets, main_cluster,
                entity_to_cluster, sec_dists, out_path):
    """Render a cell with clusters color-coded."""
    col, row = cell_key
    cell_x_min = col * CELL_W
    cell_x_max = (col + 1) * CELL_W
    cell_y_min = -row * CELL_H
    cell_y_max = -(row - 1) * CELL_H

    fig, ax = plt.subplots(1, 1, figsize=(12, 8))

    # Draw cell boundary
    rect = plt.Rectangle((cell_x_min, cell_y_min), CELL_W, CELL_H,
                          fill=False, edgecolor='gray', linewidth=1.5, linestyle='--')
    ax.add_patch(rect)

    # Color map: main=blue, secondary with dist>eps=red, other=green
    colors = {'main': '#2196F3', 'isolated': '#F44336', 'near': '#4CAF50'}

    for idx, ent in enumerate(entities):
        cl = entity_to_cluster.get(idx, -1)
        if cl == main_cluster:
            color = colors['main']
            alpha = 0.5
            lw = 0.8
        elif cl in sec_dists:
            color = colors['isolated']
            alpha = 0.9
            lw = 1.5
        else:
            color = colors['near']
            alpha = 0.6
            lw = 0.8

        pts = ent['points']
        if len(pts) == 1:
            ax.plot(pts[0][0], pts[0][1], 'o', color=color, alpha=alpha, markersize=4)
        elif len(pts) == 2:
            ax.plot([pts[0][0], pts[1][0]], [pts[0][1], pts[1][1]],
                    color=color, alpha=alpha, linewidth=lw)
        else:
            xs_p = [p[0] for p in pts] + [pts[0][0]]
            ys_p = [p[1] for p in pts] + [pts[0][1]]
            ax.plot(xs_p, ys_p, color=color, alpha=alpha, linewidth=lw)

    # Padding
    all_xs = [p[0] for e in entities for p in e['points']]
    all_ys = [p[1] for e in entities for p in e['points']]
    if all_xs and all_ys:
        pad = 50
        ax.set_xlim(min(all_xs) - pad, max(all_xs) + pad)
        ax.set_ylim(min(all_ys) - pad, max(all_ys) + pad)

    # Legend
    main_count = len(cluster_entity_sets[main_cluster])
    sec_total = sum(len(cluster_entity_sets[cl]) for cl in sec_dists)
    sec_info_parts = []
    for cl, dist in sorted(sec_dists.items(), key=lambda x: -x[1]):
        cnt = len(cluster_entity_sets[cl])
        sec_info_parts.append(f'{cnt}@{dist:.0f}u')
    sec_info = ', '.join(sec_info_parts[:4])

    main_patch = mpatches.Patch(color=colors['main'], label=f'Main cluster ({main_count} elem)')
    iso_patch = mpatches.Patch(color=colors['isolated'],
                                label=f'Isolated ({sec_total} elem): {sec_info}')
    ax.legend(handles=[main_patch, iso_patch], loc='upper right', fontsize=8)

    ax.set_title(f'Cell [{col},{row}] - {label}\n'
                 f'Main: {main_count} | Isolated: {sec_total} | eps={EPS}',
                 fontsize=10)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(str(out_path), dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved: {out_path.name}')


def main():
    print(f'Loading DXF: {DXF_FILE}')
    doc = ezdxf.readfile(str(DXF_FILE))
    msp = doc.modelspace()

    # Collect entities per cell
    cell_entities = defaultdict(list)
    cell_labels = {}

    for entity in msp:
        etype = entity.dxftype()
        layer = entity.dxf.layer if hasattr(entity.dxf, 'layer') else '0'
        points = extract_entity_points(entity)
        if not points:
            continue

        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        col = int(cx // CELL_W)
        row = math.ceil(-cy / CELL_H) if cy < 0 else 0
        cell_key = (col, row)

        if layer == 'LABEL_ID' and etype in ('TEXT', 'MTEXT'):
            text = entity.dxf.text if hasattr(entity.dxf, 'text') else ''
            if hasattr(entity, 'text'):
                text = entity.text
            cell_labels[cell_key] = text
            continue

        if layer in IGNORE_LAYERS:
            continue

        cell_entities[cell_key].append({
            'points': points,
            'layer': layer,
            'etype': etype
        })

    print(f'Found {len(cell_entities)} cells with entities')

    # Find problematic cells and rank by total isolated count
    problems = []
    for cell_key in sorted(cell_entities.keys()):
        entities = cell_entities[cell_key]
        if len(entities) < 2:
            continue

        result = cluster_entities(entities, EPS)
        if len(result) == 2:
            continue
        cluster_sets, main_cl, e2c, sec_dists = result
        if not sec_dists:
            continue

        total_isolated = sum(len(cluster_sets[cl]) for cl in sec_dists)
        max_dist = max(sec_dists.values())
        label = cell_labels.get(cell_key, f'({cell_key[0]},{cell_key[1]})')

        problems.append({
            'cell_key': cell_key,
            'label': label,
            'entities': entities,
            'cluster_sets': cluster_sets,
            'main_cl': main_cl,
            'e2c': e2c,
            'sec_dists': sec_dists,
            'total_isolated': total_isolated,
            'max_dist': max_dist
        })

    # Sort by total_isolated descending
    problems.sort(key=lambda p: -p['total_isolated'])

    print(f'Found {len(problems)} problematic cells')
    print(f'Rendering top {TOP_N}...')
    print()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for i, prob in enumerate(problems[:TOP_N]):
        ck = prob['cell_key']
        rank = i + 1
        fname = f'{rank:02d}_cell_{ck[0]}_{ck[1]}_{prob["label"].replace("|","").replace(" ","_").strip("_")}.png'
        out_path = OUT_DIR / fname
        render_cell(
            prob['entities'], ck, prob['label'],
            prob['cluster_sets'], prob['main_cl'], prob['e2c'], prob['sec_dists'],
            out_path
        )

    print()
    print(f'Done. {min(TOP_N, len(problems))} images saved to {OUT_DIR}')


if __name__ == '__main__':
    main()
