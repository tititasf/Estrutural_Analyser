import ezdxf

doc = ezdxf.readfile("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/FV_preview_V306.dxf")
msp = doc.modelspace()

print("=== ALL TEXT ENTITIES ===")
for entity in msp.query('TEXT MTEXT'):
    txt = entity.dxf.text
    x = round(entity.dxf.insert[0], 1) if hasattr(entity.dxf, 'insert') else '?'
    y = round(entity.dxf.insert[1], 1) if hasattr(entity.dxf, 'insert') else '?'
    layer = entity.dxf.layer
    rot = getattr(entity.dxf, 'rotation', 0)
    print(f"  text='{txt}' x={x} y={y} layer={layer} rot={rot}")

print()
print("=== LWPOLYLINE COUNT ===")
polys = list(msp.query('LWPOLYLINE'))
print(f"  {len(polys)} polylines")
for i, p in enumerate(polys):
    pts = list(p.get_points())
    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    print(f"  poly[{i}] x_range=[{min(xs):.1f}, {max(xs):.1f}] y_range=[{min(ys):.1f}, {max(ys):.1f}] layer={p.dxf.layer}")

print()
print("=== LINE COUNT ===")
lines = list(msp.query('LINE'))
print(f"  {len(lines)} lines")
