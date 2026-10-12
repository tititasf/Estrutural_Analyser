import ezdxf
from ezdxf import bbox

doc = ezdxf.readfile("d:/Agente-cad-PYSIDE/Exemplos Modos/FORMASCIA/LATERAIS DE VIGA PAINEIS A B FORMASCIA.dxf")
msp = doc.modelspace()

texts = [t for t in msp.query('TEXT') if t.dxf.layer == 'BNC_TEXTO' and 'V15' in t.dxf.text]
for t in texts:
    print(f"Title: {t.dxf.text} at {t.dxf.insert}")
    tx, ty = t.dxf.insert.x, t.dxf.insert.y
    
    # inspect MLINEs near this beam
    mlines_near = []
    for ml in msp.query('MLINE'):
        b = bbox.extents([ml])
        if b.has_data and abs(b.center.x - tx) < 300 and abs(b.center.y - ty) < 300:
            mlines_near.append(ml)
    print(f" Nearby MLINEs count: {len(mlines_near)}")
    for ml in mlines_near[:10]:
        p0 = tuple(round(c, 1) for c in ml.vertices[0].location)
        p1 = tuple(round(c, 1) for c in ml.vertices[1].location)
        print(f"   MLINE: style={ml.dxf.style_name}, layer={ml.dxf.layer}, p0={p0}, p1={p1}, scale={ml.dxf.scale_factor}")
    
    # inspect circles (panel numbers)
    circles_near = []
    for c in msp.query('CIRCLE'):
        if abs(c.dxf.center.x - tx) < 300 and abs(c.dxf.center.y - ty) < 300:
            circles_near.append(c)
    print(f" Nearby circles count: {len(circles_near)}")
    for c in circles_near:
        print(f"   CIRCLE: center=({round(c.dxf.center.x, 1)}, {round(c.dxf.center.y, 1)}), r={c.dxf.radius}, layer={c.dxf.layer}, color={c.dxf.color}")
        # text inside circle?
        inside = [txt for txt in msp.query('TEXT') if abs(txt.dxf.insert.x - c.dxf.center.x) < 15 and abs(txt.dxf.insert.y - c.dxf.center.y) < 15]
        for it in inside:
            print(f"     TEXT inside: {it.dxf.text}, h={it.dxf.height}, layer={it.dxf.layer}, color={it.dxf.color}")
