import ezdxf

doc = ezdxf.readfile("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - TÉRREO - FV - R00/FV_V105_motor_178111354004.dxf")
msp = doc.modelspace()

print("V105 texts:")
for e in msp.query('TEXT MTEXT'):
    if e.dxf.layer.upper() in ('5', 'NOMENCLATURA'):
        print(f"  '{e.dxf.text}' at x={e.dxf.insert.x:.1f} y={e.dxf.insert.y:.1f} layer={e.dxf.layer}")

polys = list(msp.query('LWPOLYLINE'))
poly_paineis = [p for p in polys if p.dxf.layer.upper() == 'PAINÉIS' or p.dxf.layer.upper() == 'PAINEIS']
if poly_paineis:
    xs = []
    ys = []
    for p in poly_paineis:
        pts = list(p.get_points())
        xs.extend([pt[0] for pt in pts])
        ys.extend([pt[1] for pt in pts])
    print(f"\nPolys X range: {min(xs):.1f} to {max(xs):.1f}")
    print(f"Polys Y range: {min(ys):.1f} to {max(ys):.1f}")
    cy = (min(ys) + max(ys)) / 2
    print(f"Center Y: {cy:.1f}")
