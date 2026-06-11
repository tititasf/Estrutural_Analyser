"""
Extrai dados completos do Pilar P1 do DXF real.
Identifica comprimento, largura, altura e faces.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import ezdxf, math, re
from collections import defaultdict

DXF = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/ALIMONTI - PARAISO - 1° PAV.- PL - R00.dxf"

doc = ezdxf.readfile(DXF)
msp = doc.modelspace()

def dist2d(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

# ── Coleta todos os textos de seção (P1.A, P1.B, etc.) ───────────────────────
secao_textos = []
for e in msp:
    if e.dxftype() in ('TEXT', 'MTEXT') and e.dxf.layer == 'Texto Seção':
        txt = e.dxf.text.strip() if e.dxftype() == 'TEXT' else e.text.strip()
        pos = e.dxf.insert
        secao_textos.append({'txt': txt, 'x': pos[0], 'y': pos[1]})

# Agrupa por pilar
pilares = defaultdict(list)
for t in secao_textos:
    m = re.match(r'^(P\d+)\.([A-H])', t['txt'])
    if m:
        pilares[m.group(1)].append({'face': m.group(2), 'x': t['x'], 'y': t['y']})

print(f"Pilares com faces identificadas: {sorted(pilares.keys())[:20]}")

# ── Foca no P1 ────────────────────────────────────────────────────────────────
p1_faces = sorted(pilares['P1'], key=lambda x: x['face'])
print(f"\nP1 - faces encontradas: {[f['face'] for f in p1_faces]}")
for f in p1_faces:
    print(f"  Face {f['face']}: ({f['x']:.1f}, {f['y']:.1f})")

# Centro do P1 (média das posições das faces)
cx = sum(f['x'] for f in p1_faces) / len(p1_faces)
cy = sum(f['y'] for f in p1_faces) / len(p1_faces)
print(f"\n  Centro estimado P1: ({cx:.1f}, {cy:.1f})")

# ── Cotas próximas do P1 (raio de busca) ─────────────────────────────────────
RAIO = 600  # mm
dims = [e for e in msp if e.dxftype() == 'DIMENSION']
p1_dims = []
for d in dims:
    dp = d.dxf.defpoint
    if dist2d((dp[0], dp[1]), (cx, cy)) < RAIO:
        p1_dims.append(d)

print(f"\n  Cotas dentro de {RAIO}mm do centro P1: {len(p1_dims)}")
medidas = set()
for d in p1_dims:
    meas = getattr(d.dxf, 'actual_measurement', None)
    if meas and meas > 0:
        medidas.add(round(meas, 1))
print(f"  Medidas encontradas nas cotas: {sorted(medidas)}")

# ── Linhas de Painéis próximas do P1 ─────────────────────────────────────────
paineis = [e for e in msp if e.dxftype() == 'LINE' and e.dxf.layer == 'Painéis']
p1_lines = []
for l in paineis:
    mp = ((l.dxf.start[0]+l.dxf.end[0])/2, (l.dxf.start[1]+l.dxf.end[1])/2)
    if dist2d(mp, (cx, cy)) < RAIO:
        comprimento_linha = dist2d(l.dxf.start, l.dxf.end)
        if comprimento_linha > 1:
            p1_lines.append(round(comprimento_linha, 1))

p1_lines.sort()
from collections import Counter
print(f"\n  Comprimentos de linhas de Painéis próximas P1:")
for v, n in sorted(Counter(p1_lines).items()):
    print(f"    {v:.1f} mm  x{n}")

# ── Altura via PD no texto de NOMENCLATURA mais próximo ──────────────────────
for e in msp:
    if e.dxftype() == 'MTEXT' and e.dxf.layer == 'NOMENCLATURA':
        pos = e.dxf.insert
        if dist2d((pos[0], pos[1]), (cx, cy)) < 2000:
            txt = e.text
            m = re.search(r'PD:\s*([\d.]+)', txt)
            if m:
                pd = float(m.group(1))
                print(f"\n  PD (pé direito) mais próximo: {pd}m = {pd*100:.0f}cm")
                break

# ── LWPOLYLINEs de Painéis (contorno do pilar) ───────────────────────────────
polys = [e for e in msp if e.dxftype() == 'LWPOLYLINE' and e.dxf.layer == 'Painéis']
p1_polys = []
for p in polys:
    pts = list(p.get_points())
    if not pts:
        continue
    cx_p = sum(pt[0] for pt in pts) / len(pts)
    cy_p = sum(pt[1] for pt in pts) / len(pts)
    if dist2d((cx_p, cy_p), (cx, cy)) < RAIO:
        xs = [pt[0] for pt in pts]
        ys = [pt[1] for pt in pts]
        w = round(max(xs) - min(xs), 1)
        h = round(max(ys) - min(ys), 1)
        p1_polys.append({'w': w, 'h': h, 'npts': len(pts)})

print(f"\n  LWPOLYLINEs de Painéis próximas P1 ({len(p1_polys)}):")
for p in p1_polys:
    print(f"    bbox: {p['w']:.1f} x {p['h']:.1f} mm  ({p['npts']} pts)")
