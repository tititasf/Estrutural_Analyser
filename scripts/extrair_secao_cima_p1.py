"""
Identifica a seção CIMA e geometria completa do P1.
Mapeia posição de cada face (P1.A..P1.D) e extrai linhas/polys ao redor.
Unidade: 1 unit = 1cm (calibrado PD=425 units = 4.25m)
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

# ── 1. Localizar cada face do P1 ──────────────────────────────────────
faces_p1 = {}
for e in msp:
    if e.dxftype() == 'TEXT' and e.dxf.layer == 'Texto Seção':
        txt = e.dxf.text.strip()
        m = re.match(r'^P1\.([A-H])$', txt)
        if m:
            face = m.group(1)
            pos = (e.dxf.insert[0], e.dxf.insert[1])
            faces_p1[face] = pos

print("Faces P1 (posição dos textos):")
for face in sorted(faces_p1):
    print(f"  P1.{face}: ({faces_p1[face][0]:.1f}, {faces_p1[face][1]:.1f})")

# Centro geral
if faces_p1:
    CX = sum(v[0] for v in faces_p1.values()) / len(faces_p1)
    CY = sum(v[1] for v in faces_p1.values()) / len(faces_p1)
    print(f"\nCentro P1: ({CX:.1f}, {CY:.1f})")
else:
    CX, CY = 5569, 14418
    print(f"\nUsando centro padrão: ({CX}, {CY})")

# ── 2. Para cada face, achar o retângulo (LINEs) que a rodeia ─────────
print("\n" + "="*70)
print("GEOMETRIA POR FACE (LINEs layer Painéis próximas a cada face):")
RAIO_FACE = 200  # ~200cm ao redor de cada texto de face

for face in sorted(faces_p1):
    fx, fy = faces_p1[face]
    print(f"\n  P1.{face} @ ({fx:.0f}, {fy:.0f}):")
    linhas_face = []
    for e in msp:
        if e.dxftype() != 'LINE':
            continue
        layer = e.dxf.layer
        if layer not in ('Painéis', 'CHAPA', 'Madeira'):
            continue
        mp = ((e.dxf.start[0]+e.dxf.end[0])/2, (e.dxf.start[1]+e.dxf.end[1])/2)
        if dist2d(mp, (fx, fy)) > RAIO_FACE:
            continue
        L = round(dist2d(e.dxf.start, e.dxf.end), 1)
        dx = abs(e.dxf.end[0] - e.dxf.start[0])
        dy = abs(e.dxf.end[1] - e.dxf.start[1])
        orient = 'H' if dx > dy else 'V'
        linhas_face.append((layer, L, orient, e.dxf.start, e.dxf.end))
        print(f"    [{layer:8s}] len={L:7.1f}  {orient}  from=({e.dxf.start[0]:.1f},{e.dxf.start[1]:.1f})  to=({e.dxf.end[0]:.1f},{e.dxf.end[1]:.1f})")

    # Bounding box das linhas desta face
    if linhas_face:
        all_xs = [l[3][0] for l in linhas_face] + [l[4][0] for l in linhas_face]
        all_ys = [l[3][1] for l in linhas_face] + [l[4][1] for l in linhas_face]
        w = max(all_xs) - min(all_xs)
        h = max(all_ys) - min(all_ys)
        print(f"    >>> BBOX linhas face {face}: {w:.0f} x {h:.0f}  (W x H em unidades = cm)")

# ── 3. LWPOLYLINEs em todos os layers com raio grande ─────────────────
print("\n" + "="*70)
print(f"LWPOLYLINES próximas do P1 (raio 1500):")
for e in msp:
    if e.dxftype() != 'LWPOLYLINE':
        continue
    pts = list(e.get_points())
    if not pts:
        continue
    cx_p = sum(p[0] for p in pts) / len(pts)
    cy_p = sum(p[1] for p in pts) / len(pts)
    d = dist2d((cx_p, cy_p), (CX, CY))
    if d > 1500:
        continue
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w = round(max(xs) - min(xs), 1)
    h = round(max(ys) - min(ys), 1)
    layer = e.dxf.layer
    closed = e.closed
    npts = len(pts)
    print(f"  [{layer:20s}]  bbox={w:.0f}x{h:.0f}  npts={npts}  closed={closed}  dist={d:.0f}")

# ── 4. INSERTs (blocos) de apoio próximos ─────────────────────────────
print("\n" + "="*70)
print(f"INSERTs próximos do P1 (raio 1500):")
for e in msp:
    if e.dxftype() != 'INSERT':
        continue
    pos = e.dxf.insert
    d = dist2d((pos[0], pos[1]), (CX, CY))
    if d > 1500:
        continue
    print(f"  bloco={e.dxf.name:30s}  pos=({pos[0]:.0f},{pos[1]:.0f})  dist={d:.0f}")

# ── 5. Cotas (DIMENSION) próximas ─────────────────────────────────────
print("\n" + "="*70)
print(f"DIMENSIONs próximas do P1 (raio 800):")
for e in msp:
    if e.dxftype() != 'DIMENSION':
        continue
    dp = e.dxf.defpoint
    d = dist2d((dp[0], dp[1]), (CX, CY))
    if d > 800:
        continue
    m = getattr(e.dxf, 'actual_measurement', None)
    txt = getattr(e.dxf, 'text', '')
    layer = e.dxf.layer
    m_str = f"{m:.1f}" if m is not None else "?"
    print(f"  [{layer:10s}]  meas={m_str:8s}  txt='{txt}'  defpt=({dp[0]:.0f},{dp[1]:.0f})  dist={d:.0f}")

# ── 6. Textos próximos ────────────────────────────────────────────────
print("\n" + "="*70)
print(f"Textos próximos do P1 (raio 800):")
for e in msp:
    if e.dxftype() not in ('TEXT', 'MTEXT'):
        continue
    pos = e.dxf.insert
    d = dist2d((pos[0], pos[1]), (CX, CY))
    if d > 800:
        continue
    txt = e.dxf.text.strip() if e.dxftype() == 'TEXT' else e.text.strip()
    layer = e.dxf.layer
    print(f"  [{layer:20s}]  '{txt[:80]}'  pos=({pos[0]:.0f},{pos[1]:.0f})  dist={d:.0f}")
