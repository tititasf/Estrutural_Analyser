import ezdxf

doc = ezdxf.readfile("d:/Agente-cad-PYSIDE/Exemplos Modos/FORMASCIA/LATERAIS DE VIGA PAINEIS A B FORMASCIA.dxf")
msp = doc.modelspace()

print("Bounding box:")
from ezdxf import bbox
b = bbox.extents(msp)
print(f"extmin: {b.extmin}, extmax: {b.extmax}, size: {b.size}")

# Texts and titles
texts = [(t.dxf.text, t.dxf.insert, t.dxf.layer, t.dxf.height, t.dxf.color) for t in msp.query('TEXT')]
print(f"Total texts: {len(texts)}")
for t in texts[:20]:
    print(" ", t)

# Mlines
mlines = list(msp.query('MLINE'))
print(f"Total mlines: {len(mlines)}")
for ml in mlines[:10]:
    pts = [tuple(round(c, 2) for c in v.location) for v in ml.vertices]
    print(f"  style={ml.dxf.style_name}, layer={ml.dxf.layer}, scale={ml.dxf.scale_factor}, just={ml.dxf.justification}, pts={pts}")

# Circles
circles = [(c.dxf.center, c.dxf.radius, c.dxf.layer, c.dxf.color) for c in msp.query('CIRCLE')]
print(f"Total circles: {len(circles)}")
for c in circles[:10]:
    print(" ", c)
