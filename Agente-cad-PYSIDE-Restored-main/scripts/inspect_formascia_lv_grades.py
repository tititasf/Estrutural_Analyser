import ezdxf

doc = ezdxf.readfile("d:/Agente-cad-PYSIDE/Exemplos Modos/FORMASCIA/LATERAIS DE VIGA GRADES SOLTAS FORMASCIA.dxf")
msp = doc.modelspace()
from collections import Counter
c = Counter(e.dxftype() for e in msp)
print("Entity types:", c)
layer_counts = Counter(e.dxf.layer for e in msp)
print("Layer counts:", layer_counts)

# Mlines
mlines = list(msp.query('MLINE'))
print(f"Total mlines: {len(mlines)}")
for ml in mlines[:5]:
    pts = [tuple(round(co, 2) for co in v.location) for v in ml.vertices]
    print(f"  style={ml.dxf.style_name}, layer={ml.dxf.layer}, scale={ml.dxf.scale_factor}, just={ml.dxf.justification}, pts={pts}")

# Texts
texts = [(t.dxf.text, t.dxf.insert, t.dxf.layer, t.dxf.height) for t in msp.query('TEXT')][:15]
print("Sample texts:", texts)
