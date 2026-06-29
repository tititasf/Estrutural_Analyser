import ezdxf

doc = ezdxf.readfile(r'D:\Agente-cad-PYSIDE\Desing-Visual-DXF\BASE-DESING-LAJES-L302-13PAV-OBRA-TREINO-1.dxf')
msp = doc.modelspace()

print('--- LWPOLYLINE/LINE Layers ---')
p_layers = {}
for e in msp.query('LWPOLYLINE LINE'):
    p_layers[e.dxf.layer] = p_layers.get(e.dxf.layer, 0) + 1
for k,v in p_layers.items(): print(f'{k}: {v}')

print('\n--- TEXT / MTEXT Layers ---')
t_layers = {}
for e in msp.query('TEXT MTEXT'):
    t_layers[e.dxf.layer] = t_layers.get(e.dxf.layer, 0) + 1
    if e.dxf.layer in ['NOMENCLATURA', 'PAINEIS', 'COTA']:
        print(f'Text in {e.dxf.layer}: {getattr(e.dxf, "text", getattr(e, "text", ""))} (H: {getattr(e.dxf, "height", "")})')
for k,v in t_layers.items(): print(f'{k}: {v}')

print('\n--- HATCH Properties ---')
for h in msp.query('HATCH')[:3]:
    print(f'Layer: {h.dxf.layer}, Pattern: {h.dxf.pattern_name}, Color: {h.dxf.color}')

print('\n--- DIMENSION Properties ---')
dims = msp.query('DIMENSION')
if dims:
    d = dims[0]
    print(f'Layer: {d.dxf.layer}')
    print(f'Color: {getattr(d.dxf, "color", "BYLAYER")}')
    print(f'Dimstyle: {d.dxf.dimstyle}')
    ds = doc.dimstyles.get(d.dxf.dimstyle)
    if ds:
        print(f'Dimtxt: {ds.dxf.dimtxt}')
        print(f'Dimasz: {ds.dxf.dimasz}')
        print(f'Dimexe: {getattr(ds.dxf, "dimexe", "N/A")}')
        print(f'Dimexo: {getattr(ds.dxf, "dimexo", "N/A")}')
