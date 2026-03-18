#!/usr/bin/env python3
"""
detect_clusters_real.py -- Detecta fragmentos soltos em cada celula do combined DXF.

Para cada celula:
  1. Coleta TODOS os endpoints reais (x1,y1,x2,y2 para LINE; vertices para LWPOLYLINE;
     insert para TEXT/MTEXT)
  2. Clusteriza por proximidade espacial (Union-Find com eps=250)
  3. Cluster principal = maior por numero de elementos unicos
  4. Cluster secundario = qualquer grupo isolado com >= 1 elemento
  5. FLAG: se distancia minima entre cluster secundario e cluster principal > 250
  6. Report: (col, row, label_id, layers_in_secondary, count, distance)

Ignora layers: CELL_BORDER, LABEL_ID, COTA, Cota Secao, COTA_H
"""

import sys, io
if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

import ezdxf
import math
from collections import defaultdict
from pathlib import Path

# --- Config ---
DXF_FILE = Path('D:/Agente-cad-PYSIDE/ANALISE_LV/combined/combined_v35.dxf')
CELL_W = 2900
CELL_H = 1800
COLS = 12
EPS = 350          # max distance for same cluster
                   # 350u: section-zone polys can be 252-342u below face zone;
                   # COTA/Texto Secao bridge them visually but are ignored here.
                   # Y-overlap filter handles wide-formwork false positives.
IGNORE_LAYERS = {'CELL_BORDER', 'LABEL_ID', 'COTA', 'COTA_H',
                 'Cota Se\u00e7\u00e3o (2x)', 'Texto Se\u00e7\u00e3o',
                 'NOMENCLATURA', 'PONTALETE'}
# 'Cota Secao (2x)' and 'Texto Secao' are section-zone annotation layers.
# After compaction they move with the section but stay 250-700u from the face.
# They are excluded from cluster detection because their position relative to
# the main cluster is expected to be distant -- they annotate the section zone.
# 'NOMENCLATURA' and 'PONTALETE' are label/prop elements that can be placed
# anywhere in the cell; their distance to the main cluster is not meaningful.


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


def detect_clusters(dxf_path, cell_w=CELL_W, cell_h=CELL_H, cols=COLS, eps=EPS):
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    cell_entities = defaultdict(list)
    cell_labels = {}

    for entity in msp:
        etype = entity.dxftype()
        layer = entity.dxf.layer if hasattr(entity.dxf, 'layer') else '0'

        points = []
        if etype == 'LINE':
            p1 = entity.dxf.start
            p2 = entity.dxf.end
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
        else:
            continue

        if not points:
            continue

        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        col_idx = int(cx // cell_w)
        if cy >= 0:
            row_idx = 0
        else:
            # Row r spans y in [-(r)*cell_h, -(r-1)*cell_h)
            # For cy < 0: row = ceil(-cy / cell_h)
            row_idx = math.ceil(-cy / cell_h)

        cell_key = (col_idx, row_idx)

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

    results = []
    layer_problem_counts = defaultdict(int)

    for cell_key in sorted(cell_entities.keys()):
        col_idx, row_idx = cell_key
        entities = cell_entities[cell_key]
        label = cell_labels.get(cell_key, f'({col_idx},{row_idx})')

        if len(entities) < 2:
            continue

        # Flatten all points with element index
        all_pts = []
        for idx, ent in enumerate(entities):
            for p in ent['points']:
                all_pts.append((p[0], p[1], idx))

        if len(all_pts) < 2:
            continue

        # Union-Find clustering
        n = len(all_pts)
        uf = UnionFind(n)

        # Spatial grid for O(n) neighbor lookup
        grid = defaultdict(list)
        for i, (x, y, _) in enumerate(all_pts):
            gx, gy = int(x // eps), int(y // eps)
            grid[(gx, gy)].append(i)

        for i, (x1, y1, _) in enumerate(all_pts):
            gx, gy = int(x1 // eps), int(y1 // eps)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in grid.get((gx+dx, gy+dy), []):
                        if j <= i: continue
                        x2, y2 = all_pts[j][0], all_pts[j][1]
                        if (x1-x2)**2 + (y1-y2)**2 <= eps**2:
                            uf.union(i, j)

        # Map each entity to its dominant cluster
        entity_clusters = defaultdict(lambda: defaultdict(int))
        for i, (_, _, eidx) in enumerate(all_pts):
            cl = uf.find(i)
            entity_clusters[eidx][cl] += 1

        entity_to_cluster = {}
        for eidx, cl_counts in entity_clusters.items():
            entity_to_cluster[eidx] = max(cl_counts, key=cl_counts.get)

        # After initial assignment, merge clusters that share entities
        for eidx, cl_counts in entity_clusters.items():
            clusters_for_entity = list(cl_counts.keys())
            for k in range(1, len(clusters_for_entity)):
                # Find representative points for merging
                pass  # entity already assigned to dominant

        cluster_entity_sets = defaultdict(set)
        for eidx, cl in entity_to_cluster.items():
            cluster_entity_sets[cl].add(eidx)

        if len(cluster_entity_sets) <= 1:
            continue

        main_cluster = max(cluster_entity_sets, key=lambda c: len(cluster_entity_sets[c]))

        # Collect main cluster points
        main_points = []
        for i, (px, py, eidx) in enumerate(all_pts):
            if entity_to_cluster.get(eidx) == main_cluster:
                main_points.append((px, py))

        for sec_cl, sec_entities in cluster_entity_sets.items():
            if sec_cl == main_cluster:
                continue

            sec_points = []
            for i, (px, py, eidx) in enumerate(all_pts):
                if entity_to_cluster.get(eidx) == sec_cl:
                    sec_points.append((px, py))

            # Compute min distance between secondary and main
            min_dist = float('inf')
            for sx, sy in sec_points:
                for mx, my in main_points:
                    d = math.sqrt((sx-mx)**2 + (sy-my)**2)
                    if d < min_dist:
                        min_dist = d
                        if d <= eps:
                            break
                if min_dist <= eps:
                    break

            if min_dist > eps:
                # Y-overlap filter: if secondary cluster Y range overlaps >=30% with
                # main cluster Y range, it is part of a wide formwork (not a loose piece).
                # Genuine section-poly isolation has zero or near-zero Y overlap.
                main_ys = [py for px, py in main_points]
                sec_ys  = [py for px, py in sec_points]
                sec_y_min, sec_y_max = min(sec_ys), max(sec_ys)
                main_y_min, main_y_max = min(main_ys), max(main_ys)
                y_overlap = max(0.0, min(main_y_max, sec_y_max) - max(main_y_min, sec_y_min))
                sec_y_range = max(1.0, sec_y_max - sec_y_min)
                if y_overlap / sec_y_range >= 0.30:
                    continue  # Wide formwork — not a loose piece

                sec_layers = defaultdict(int)
                for eidx in sec_entities:
                    sec_layers[entities[eidx]['layer']] += 1

                for layer_name, cnt in sec_layers.items():
                    layer_problem_counts[layer_name] += cnt

                results.append({
                    'col': col_idx,
                    'row': row_idx,
                    'label': label,
                    'sec_layers': dict(sec_layers),
                    'sec_count': len(sec_entities),
                    'distance': round(min_dist, 1),
                    'main_count': len(cluster_entity_sets[main_cluster]),
                    'y_overlap_ratio': round(y_overlap / sec_y_range, 2),
                })

    return results, layer_problem_counts


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dxf', default=str(DXF_FILE), help='Path to combined DXF')
    parser.add_argument('--eps', type=float, default=EPS, help='Cluster distance threshold')
    args = parser.parse_args()

    dxf_path = Path(args.dxf)
    print(f'Analisando: {dxf_path}')
    print(f'Parametros: eps={args.eps}, CELL_W={CELL_W}, CELL_H={CELL_H}, COLS={COLS}')
    print(f'Layers ignorados: {sorted(IGNORE_LAYERS)}')
    print()

    results, layer_counts = detect_clusters(dxf_path, eps=args.eps)

    if not results:
        print('RESULTADO: 0 celulas com fragmentos isolados detectados.')
        return

    cell_results = defaultdict(list)
    for r in results:
        cell_results[(r['col'], r['row'])].append(r)

    print(f'=== CELULAS COM FRAGMENTOS ISOLADOS: {len(cell_results)} ===')
    print()

    for (col, row), frags in sorted(cell_results.items()):
        label = frags[0]['label']
        main_count = frags[0]['main_count']
        print(f'  [{col},{row}] {label}  (cluster principal: {main_count} elementos)')
        for f in frags:
            layers_str = ', '.join(f'{l}({c})' for l, c in sorted(f['sec_layers'].items()))
            print(f'    -> {f["sec_count"]} elem isolados  dist={f["distance"]}  layers: {layers_str}')
        print()

    print(f'=== ANALISE POR LAYER (top problematicos) ===')
    print()
    for layer, count in sorted(layer_counts.items(), key=lambda x: -x[1]):
        print(f'  {layer:30s} : {count} elementos em fragmentos isolados')

    print()
    print(f'Total: {len(cell_results)} celulas com fragmentos, {sum(r["sec_count"] for r in results)} elementos soltos')


if __name__ == '__main__':
    main()
