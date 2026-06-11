"""
Extrai P1 usando cluster correto de faces (mesma região do desenho).
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import ezdxf, math, re
from collections import defaultdict, Counter

DXF = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/ALIMONTI - PARAISO - 1° PAV.- PL - R00.dxf"

doc = ezdxf.readfile(DXF)
msp = doc.modelspace()

def dist2d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

# Coleta todos os "Texto Seção" com padrão Pn.X
secoes = {}
for e in msp:
    if e.dxftype() == 'TEXT' and e.dxf.layer == 'Texto Seção':
        txt = e.dxf.text.strip()
        m = re.match(r'^(P\d+)\.([A-H])$', txt)
        if m:
            pid, face = m.group(1), m.group(2)
            pos = (e.dxf.insert[0], e.dxf.insert[1])
            secoes.setdefault(pid, []).append({'face': face, 'pos': pos})

# Para P1, identifica clusters separados (pode ter 2 ocorrências no mesmo DXF)
p1_ocorrencias = secoes.get('P1', [])
print(f"P1 faces brutas: {len(p1_ocorrencias)}")
for o in p1_ocorrencias:
    print(f"  Face {o['face']}: {o['pos']}")

# Agrupa por proximidade (cluster < 1000mm entre si)
clusters = []
for o in p1_ocorrencias:
    colocado = False
    for cl in clusters:
        cx = sum(x['pos'][0] for x in cl) / len(cl)
        cy = sum(x['pos'][1] for x in cl) / len(cl)
        if dist2d(o['pos'], (cx, cy)) < 1500:
            cl.append(o)
            colocado = True
            break
    if not colocado:
        clusters.append([o])

print(f"\nClusters de P1: {len(clusters)}")
for i, cl in enumerate(clusters):
    cx = sum(x['pos'][0] for x in cl) / len(cl)
    cy = sum(x['pos'][1] for x in cl) / len(cl)
    faces = [x['face'] for x in cl]
    print(f"  Cluster {i+1}: faces={faces}  centro=({cx:.0f}, {cy:.0f})")

# Usa cluster 1 (primeiro)
cl = clusters[0]
cx = sum(x['pos'][0] for x in cl) / len(cl)
cy = sum(x['pos'][1] for x in cl) / len(cl)
print(f"\nUsando Cluster 1: centro=({cx:.0f}, {cy:.0f})")

# ── Cotas próximas (raio maior) ────────────────────────────────────────────────
RAIO = 1200
dims = [e for e in msp if e.dxftype() == 'DIMENSION']
p1_dims = [d for d in dims if dist2d((d.dxf.defpoint[0], d.dxf.defpoint[1]), (cx, cy)) < RAIO]
print(f"\nCotas dentro de {RAIO}mm: {len(p1_dims)}")
medidas = Counter()
for d in p1_dims:
    m = getattr(d.dxf, 'actual_measurement', None)
    if m and 1 < m < 10000:
        medidas[round(m, 0)] += 1
print("Medidas (valor: frequência):")
for v, n in sorted(medidas.items()):
    print(f"  {v:8.0f} mm ({v/10:.1f} cm)  x{n}")

# ── LWPOLYLINEs próximas ───────────────────────────────────────────────────────
polys_todas = [e for e in msp if e.dxftype() == 'LWPOLYLINE']
p1_polys = []
for p in polys_todas:
    pts = list(p.get_points())
    if not pts:
        continue
    pcx = sum(pt[0] for pt in pts) / len(pts)
    pcy = sum(pt[1] for pt in pts) / len(pts)
    if dist2d((pcx, pcy), (cx, cy)) < RAIO:
        xs = [pt[0] for pt in pts]
        ys = [pt[1] for pt in pts]
        w = round(max(xs) - min(xs), 0)
        h = round(max(ys) - min(ys), 0)
        layer = p.dxf.layer
        p1_polys.append({'w': w, 'h': h, 'npts': len(pts), 'layer': layer})

print(f"\nLWPOLYLINEs próximas ({len(p1_polys)}):")
for p in sorted(p1_polys, key=lambda x: -max(x['w'], x['h'])):
    print(f"  [{p['layer']:20s}]  {p['w']:6.0f} x {p['h']:6.0f} mm")

# ── Altura via PD ──────────────────────────────────────────────────────────────
for e in msp:
    if e.dxftype() == 'MTEXT' and e.dxf.layer == 'NOMENCLATURA':
        pos = e.dxf.insert
        if dist2d((pos[0], pos[1]), (cx, cy)) < 2000:
            txt = e.text
            m = re.search(r'PD:\s*([\d.]+)', txt)
            if m:
                pd = float(m.group(1))
                print(f"\nPé Direito mais próximo: {pd}m = {pd*100:.0f}cm")
            break

# ── Todos os pilares da obra (resumo) ─────────────────────────────────────────
print(f"\n{'='*50}")
print("TODOS os pilares encontrados no DXF:")
for pid in sorted(secoes.keys(), key=lambda x: int(re.search(r'\d+', x).group())):
    faces = sorted(set(f['face'] for f in secoes[pid]))
    print(f"  {pid:6s}  faces: {faces}")
