"""
Validacao visual do DXF V306_n4er gerado pela simulacao da UI.
"""
import ezdxf

doc = ezdxf.readfile("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/FV_preview_V306_n4er.dxf")
msp = doc.modelspace()

print("=== POLYLINES (paineis) ===")
polys = list(msp.query('LWPOLYLINE'))
for i, p in enumerate(polys):
    pts = list(p.get_points())
    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    n_verts = len(pts)
    chanfro = " << CHANFRO" if n_verts > 4 else ""
    print(f"  poly[{i}] x=[{min(xs):.1f}, {max(xs):.1f}] w={w:.1f}cm  y=[{min(ys):.1f}, {max(ys):.1f}] h={h:.1f}cm  verts={n_verts}{chanfro}")

print(f"\n=== TEXTOS ===")
for entity in msp.query('TEXT MTEXT'):
    txt = entity.dxf.text
    x = round(entity.dxf.insert[0], 1)
    y = round(entity.dxf.insert[1], 1)
    layer = entity.dxf.layer
    rot = getattr(entity.dxf, 'rotation', 0)
    print(f"  '{txt}' at ({x}, {y}) layer={layer} rot={rot}")

print(f"\n=== LINHAS ===")
lines = list(msp.query('LINE'))
sarr_lines = [l for l in lines if 'SARR' in l.dxf.layer.upper()]
other_lines = [l for l in lines if 'SARR' not in l.dxf.layer.upper()]
print(f"  Total: {len(lines)} (sarrafos: {len(sarr_lines)}, outros: {len(other_lines)})")

print(f"\n=== DIMENSIONS ===")
dims = list(msp.query('DIMENSION'))
for d in dims:
    try:
        m = d.dxf.actual_measurement
        print(f"  dim measurement={m:.1f}")
    except:
        print(f"  dim (no measurement)")

print(f"\n=== RESUMO ===")
poly_xs = []
for p in polys:
    pts = list(p.get_points())
    poly_xs.extend([pt[0] for pt in pts])
if poly_xs:
    total_span = max(poly_xs) - min(poly_xs)
    print(f"  Span total dos paineis: {min(poly_xs):.1f} a {max(poly_xs):.1f} = {total_span:.1f}cm")
    
    # Check for gaps between panels
    poly_ranges = []
    for p in polys:
        pts = list(p.get_points())
        xs = [pt[0] for pt in pts]
        poly_ranges.append((min(xs), max(xs)))
    poly_ranges.sort()
    
    for i in range(len(poly_ranges) - 1):
        gap = poly_ranges[i+1][0] - poly_ranges[i][1]
        if gap > 1:
            print(f"  GAP entre poly[{i}] e poly[{i+1}]: {gap:.1f}cm (pilar cruzado)")
        elif gap < -1:
            print(f"  OVERLAP entre poly[{i}] e poly[{i+1}]: {abs(gap):.1f}cm *** BUG! ***")
        else:
            print(f"  poly[{i}] e poly[{i+1}] tocam (gap={gap:.1f}cm)")
