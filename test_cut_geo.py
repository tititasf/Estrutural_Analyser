"""
Headless test: simula _auto_fill_cut_view_ficha CORRIGIDA para 13 PAV.
Verifica:
  1. Neighbor name nao e mais nulo (fix _opposite_direction_key)
  2. beam_height correto
  3. dist_fundo + slab_h + dist_topo = beam_height
"""
import sqlite3, json
from shapely.geometry import Polygon

DB = 'D:/Agente-cad-PYSIDE/project_data.vision'
PAV = 'TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA'


# ─── Replicas das funcoes corrigidas ────────────────────────────────────────

def polygon_y_at_x(pts, x_mid):
    ys = []
    n = len(pts)
    for i in range(n):
        x1,y1 = float(pts[i][0]), float(pts[i][1])
        x2,y2 = float(pts[(i+1)%n][0]), float(pts[(i+1)%n][1])
        if x1 == x2: continue
        if min(x1,x2) <= x_mid <= max(x1,x2):
            ys.append(y1 + (x_mid - x1)*(y2 - y1)/(x2 - x1))
    return ys

def polygon_x_at_y(pts, y_mid):
    xs = []
    n = len(pts)
    for i in range(n):
        x1,y1 = float(pts[i][0]), float(pts[i][1])
        x2,y2 = float(pts[(i+1)%n][0]), float(pts[(i+1)%n][1])
        if y1 == y2: continue
        if min(y1,y2) <= y_mid <= max(y1,y2):
            xs.append(x1 + (y_mid - y1)*(x2 - x1)/(y2 - y1))
    return xs

def slab_cut_direction(slab_bbox, pts):
    xs_p = [p[0] for p in pts]; ys_p = [p[1] for p in pts]
    sb = slab_bbox
    sx=(sb[0]+sb[2])/2; sy=(sb[1]+sb[3])/2
    cx=(min(xs_p)+max(xs_p))/2; cy=(min(ys_p)+max(ys_p))/2
    dx,dy = cx-sx, cy-sy
    if abs(dx) > abs(dy):
        return 'Leste' if dx > 0 else 'Oeste'
    return 'Norte' if dy > 0 else 'Sul'

def direction_to_ortho_key(direction):
    d = str(direction or '').lower()
    if d.startswith('n'): return 'top'
    if d.startswith('s'): return 'bottom'
    if d.startswith('l') or d.startswith('e'): return 'right'
    if d.startswith('o') or d.startswith('w'): return 'left'
    return ''

def parse_cut_corrected(pts, direction):
    d = str(direction or '').strip().lower()
    ns_cut = d.startswith('n') or d.startswith('s')
    all_xs = [float(p[0]) for p in pts]
    all_ys = [float(p[1]) for p in pts]

    if ns_cut:
        ys_uniq = sorted(set(round(float(p[1]), 2) for p in pts))
        bands = []
        for i in range(len(ys_uniq)-1):
            y_mid = (ys_uniq[i]+ys_uniq[i+1])/2
            xv = polygon_x_at_y(pts, y_mid)
            if len(xv) >= 2:
                bands.append({'coord_min':ys_uniq[i],'coord_max':ys_uniq[i+1],
                              'span':ys_uniq[i+1]-ys_uniq[i],'width':max(xv)-min(xv)})
        if not bands: return {}
        beam = max(bands, key=lambda b: b['width'])
        x_min = min(all_xs); x_max = max(all_xs)
        beam_height = round(x_max - x_min, 1)
        bw = round(beam['span'], 1)
        ntpos = d.startswith('n')
        if ntpos:
            tab_n = [b for b in bands if b['coord_min'] >= beam['coord_max']]
            tab_o = [b for b in bands if b['coord_max'] <= beam['coord_min']]
        else:
            tab_n = [b for b in bands if b['coord_max'] <= beam['coord_min']]
            tab_o = [b for b in bands if b['coord_min'] >= beam['coord_max']]
        def _tab(tab_bands):
            if not tab_bands: return None
            b = min(tab_bands, key=lambda bb: abs((bb['coord_min']+bb['coord_max'])/2-(beam['coord_min']+beam['coord_max'])/2))
            y_mid = (b['coord_min']+b['coord_max'])/2
            xv = polygon_x_at_y(pts, y_mid)
            if len(xv) < 2: return None
            tx_min=min(xv); tx_max=max(xv)
            return dict(slab_h=round(tx_max-tx_min,1),
                        dist_topo=round(tx_min-x_min,1),
                        dist_fundo=round(x_max-tx_max,1),
                        overhang=round(sum(bb['span'] for bb in tab_bands),1))
    else:
        xs_uniq = sorted(set(round(float(p[0]), 2) for p in pts))
        bands = []
        for i in range(len(xs_uniq)-1):
            x_mid = (xs_uniq[i]+xs_uniq[i+1])/2
            yv = polygon_y_at_x(pts, x_mid)
            if len(yv) >= 2:
                bands.append({'coord_min':xs_uniq[i],'coord_max':xs_uniq[i+1],
                              'span':xs_uniq[i+1]-xs_uniq[i],'width':max(yv)-min(yv)})
        if not bands: return {}
        beam = max(bands, key=lambda b: b['width'])
        y_min = min(all_ys); y_max = max(all_ys)
        beam_height = round(y_max - y_min, 1)
        bw = round(beam['span'], 1)
        ntpos = d.startswith('l') or d.startswith('e')
        if ntpos:
            tab_n = [b for b in bands if b['coord_min'] >= beam['coord_max']]
            tab_o = [b for b in bands if b['coord_max'] <= beam['coord_min']]
        else:
            tab_n = [b for b in bands if b['coord_max'] <= beam['coord_min']]
            tab_o = [b for b in bands if b['coord_min'] >= beam['coord_max']]
        def _tab(tab_bands):
            if not tab_bands: return None
            b = min(tab_bands, key=lambda bb: abs((bb['coord_min']+bb['coord_max'])/2-(beam['coord_min']+beam['coord_max'])/2))
            x_mid = (b['coord_min']+b['coord_max'])/2
            yv = polygon_y_at_x(pts, x_mid)
            if len(yv) < 2: return None
            ty_min=min(yv); ty_max=max(yv)
            return dict(slab_h=round(ty_max-ty_min,1),
                        dist_topo=round(y_max-ty_max,1),
                        dist_fundo=round(ty_min-y_min,1),
                        overhang=round(sum(bb['span'] for bb in tab_bands),1))

    return dict(beam_height=beam_height, bw=bw, own=_tab(tab_o), neigh=_tab(tab_n))

def orthogonal_neighbor(target_name, target_poly, target_bbox, all_slabs_poly, max_dist=85.0):
    """Replica _orthogonal_neighbor_slabs."""
    ta = target_bbox
    tcx=(ta[0]+ta[2])/2; tcy=(ta[1]+ta[3])/2
    tw=max(1.,ta[2]-ta[0]); th=max(1.,ta[3]-ta[1])
    results = []
    for name, (poly, bbox) in all_slabs_poly.items():
        if name == target_name: continue  # exclui própria laje
        dist = float(target_poly.distance(poly))
        if dist > max_dist: continue
        ob = bbox
        ocx=(ob[0]+ob[2])/2; ocy=(ob[1]+ob[3])/2
        ow=max(1.,ob[2]-ob[0]); oh=max(1.,ob[3]-ob[1])
        x_overlap = max(0., min(ta[2],ob[2]) - max(ta[0],ob[0]))
        y_overlap = max(0., min(ta[3],ob[3]) - max(ta[1],ob[1]))
        vertical   = x_overlap >= min(tw,ow)*0.12 and abs(ocy-tcy) >= abs(ocx-tcx)
        horizontal = y_overlap >= min(th,oh)*0.12 and abs(ocx-tcx) >= abs(ocy-tcy)
        if not (vertical or horizontal): continue
        dir_key = ('top' if ocy > tcy else 'bottom') if vertical else ('right' if ocx > tcx else 'left')
        results.append((dist, dir_key, name, bbox))
    return sorted(results, key=lambda x: (x[1], x[0]))

# ─── Carrega dados do DB ─────────────────────────────────────────────────────

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row
cur = db.cursor()
cur.execute("""
    SELECT s.laje_nome, s.campos_json
    FROM slab_elements s
    JOIN projects p ON s.project_id = p.id
    WHERE p.pavement_name = ?
""", (PAV,))
rows = {r['laje_nome']: dict(r) for r in cur.fetchall()}
db.close()

print(f"Lajes carregadas: {len(rows)}")

# Cria poly_map a partir de 'coordenadas' em campos_json
poly_map = {}
for lname, row in rows.items():
    try:
        cj = json.loads(row['campos_json'])
        coords = cj.get('coordenadas')
        if coords and len(coords) >= 3:
            p = Polygon([(float(c[0]), float(c[1])) for c in coords])
            poly_map[lname] = (p, list(p.bounds))
    except Exception:
        pass

print(f"Poly map: {len(poly_map)} lajes com poligono")

# ─── Simula _auto_fill_cut_view_ficha para lajes de interesse ───────────────
TARGET_LAJES = ['L311', 'L310', 'L309', 'L303']

print("\n" + "="*70)
print("RESULTADO COM CORRECOES APLICADAS")
print("="*70)

for lname in TARGET_LAJES:
    row = rows.get(lname)
    if not row:
        print(f"\n{lname}: NAO ENCONTRADO no DB")
        continue
    cj = json.loads(row['campos_json'])
    bbox = cj['bbox']
    own_poly, _ = poly_map.get(lname, (None, None))
    if own_poly is None:
        print(f"\n{lname}: sem poligono")
        continue

    print(f"\n{'='*60}")
    print(f"LAJE: {lname}  bbox=[{','.join(str(round(v,1)) for v in bbox)}]")

    cvs = cj.get('cut_views', [])
    for i, cv in enumerate(cvs[:6]):
        pts = cv.get('points', [])
        if not pts: continue
        xs_p=[p[0] for p in pts]; ys_p=[p[1] for p in pts]
        W=max(xs_p)-min(xs_p); H=max(ys_p)-min(ys_p)
        direction = slab_cut_direction(bbox, pts)
        target_key = direction_to_ortho_key(direction)

        # Encontra vizinho
        neighbors = orthogonal_neighbor(lname, own_poly, bbox, poly_map, max_dist=85.0)
        neighbor_name = next((n for d,dk,n,_ in neighbors if dk == target_key), None)

        geo = parse_cut_corrected(pts, direction)
        own_d   = geo.get('own')
        neigh_d = geo.get('neigh')
        bh = geo.get('beam_height', 0)
        bw = geo.get('bw', 0)

        print(f"\n  CV{i}: W={W:.1f} H={H:.1f}  dir={direction}  vizinho={neighbor_name or 'NULO'}")
        print(f"    beam_height={bh}  bw={bw}")
        if own_d:
            chk = own_d['dist_fundo']+own_d['slab_h']+own_d['dist_topo']
            ok = 'OK' if abs(chk - bh) < 0.5 else 'FAIL'
            print(f"    own:  slab_h={own_d['slab_h']}  dist_topo={own_d['dist_topo']}  dist_fundo={own_d['dist_fundo']}  [{chk:.1f}={bh} {ok}]")
        else:
            print(f"    own:  sem tab")
        if neigh_d:
            chk = neigh_d['dist_fundo']+neigh_d['slab_h']+neigh_d['dist_topo']
            ok = 'OK' if abs(chk - bh) < 0.5 else 'FAIL'
            print(f"    neigh:slab_h={neigh_d['slab_h']}  dist_topo={neigh_d['dist_topo']}  dist_fundo={neigh_d['dist_fundo']}  [{chk:.1f}={bh} {ok}]")
        else:
            print(f"    neigh:sem tab (laje vizinha sem aba neste corte)")

print("\n" + "="*70)
print("RESUMO - vizinhos encontrados vs nulos:")
total_cvs = 0; found = 0
for lname in TARGET_LAJES:
    row = rows.get(lname)
    if not row: continue
    cj = json.loads(row['campos_json'])
    bbox = cj['bbox']
    own_poly, _ = poly_map.get(lname, (None, None))
    if own_poly is None: continue
    cvs = cj.get('cut_views', [])
    for i, cv in enumerate(cvs[:6]):
        pts = cv.get('points', [])
        if not pts: continue
        direction = slab_cut_direction(bbox, pts)
        target_key = direction_to_ortho_key(direction)
        neighbors = orthogonal_neighbor(lname, own_poly, bbox, poly_map, max_dist=85.0)
        neighbor_name = next((n for d,dk,n,_ in neighbors if dk == target_key), None)
        total_cvs += 1
        if neighbor_name: found += 1
        status = neighbor_name or '---NULO---'
        print(f"  {lname} CV{i} ({direction}): vizinho = {status}")

print(f"\nTotal CVs testados: {total_cvs}, com vizinho: {found}, nulos: {total_cvs-found}")
