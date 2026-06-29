import re

path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\gerar_dxf_lajes.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Update color constants and setup_layers
text = text.replace('COR_OBST     = 1', 'COR_OBST     = 1\nCOR_HATCH    = 8')
text = text.replace('("Contorno",        COR_CONTORNO),', '("Contorno",        COR_CONTORNO),\n        ("Hatch",           COR_HATCH),')

# Replace draw_panels to draw lines instead of rectangles to avoid overlap
new_draw_panels = '''def draw_panels(msp, comp: float, larg: float,
                linhas_v: list, linhas_h: list):
    """Desenha as divisorias internas sem sobrepor o contorno externo."""
    xs = sorted(set([float(l["value"]) for l in linhas_v]))
    ys = sorted(set([float(l["value"]) for l in linhas_h]))

    for x in xs:
        if 0 < x < comp:
            msp.add_line((x, 0), (x, larg), dxfattribs={"layer": "Paineis"})
    
    for y in ys:
        if 0 < y < larg:
            msp.add_line((0, y), (comp, y), dxfattribs={"layer": "Paineis"})
'''
text = re.sub(r'def draw_panels.*?layer = "Paineis"\n', new_draw_panels, text, flags=re.DOTALL)

# Add Hatch and fix cotas inside gerar_dxf_laje
new_gerar = '''    # Hatch
    if coords and len(coords) >= 3:
        hatch = msp.add_hatch(color=8, dxfattribs={"layer": "Hatch"})
        hatch.set_pattern_fill("ANSI31", scale=0.5)
        hatch.paths.add_polyline_path([(c[0], c[1]) for c in coords], is_closed=True)
    else:
        hatch = msp.add_hatch(color=8, dxfattribs={"layer": "Hatch"})
        hatch.set_pattern_fill("ANSI31", scale=0.5)
        hatch.paths.add_polyline_path(rect, is_closed=True)

    # Paineis internos
    draw_panels(msp, comp, larg, linhas_v, linhas_h)'''
text = re.sub(r'# Paineis internos\s+draw_panels\(msp, comp, larg, linhas_v, linhas_h\)', new_gerar, text)

# Fix Cotas section
old_cotas = '''# DIMENSION entities (cotas horizontais e verticais)
    dim_y = -25.0
    try:
        d = msp.add_linear_dim(
            base=(0.0, dim_y), p1=(0.0, 0.0), p2=(comp, 0.0),
            angle=0, dimstyle="COTA_LJ", dxfattribs={"layer": "COTA"})
        d.render()
    except Exception:
        pass
    dim_x = comp + 20.0
    try:
        d = msp.add_linear_dim(
            base=(dim_x, 0.0), p1=(comp, 0.0), p2=(comp, larg),
            angle=90, dimstyle="COTA_LJ", dxfattribs={"layer": "COTA"})
        d.render()
    except Exception:
        pass
    # Cotas por painel
    for i in range(len(xs) - 1):
        sw = xs[i+1] - xs[i]
        if sw > 1:
            try:
                d = msp.add_linear_dim(
                    base=(xs[i], dim_y - 20), p1=(xs[i], 0.0), p2=(xs[i+1], 0.0),
                    angle=0, dimstyle="COTA_LJ", dxfattribs={"layer": "COTA"})
                d.render()
            except Exception:
                pass'''

new_cotas = '''# DIMENSION entities (cotas horizontais e verticais)
    dim_y_overall = -20.0
    dim_y_panels = -40.0
    dim_x_overall = comp + 20.0
    dim_x_panels = comp + 40.0

    # Cota total horizontal
    try:
        d = msp.add_linear_dim(
            base=(comp/2, dim_y_overall), p1=(0.0, 0.0), p2=(comp, 0.0),
            angle=0, dimstyle="COTA_LJ", dxfattribs={"layer": "COTA"})
        d.render()
    except Exception:
        pass

    # Cota total vertical
    try:
        d = msp.add_linear_dim(
            base=(dim_x_overall, larg/2), p1=(comp, 0.0), p2=(comp, larg),
            angle=90, dimstyle="COTA_LJ", dxfattribs={"layer": "COTA"})
        d.render()
    except Exception:
        pass

    # Cotas por painel horizontal
    for i in range(len(xs) - 1):
        sw = xs[i+1] - xs[i]
        if sw > 1:
            try:
                d = msp.add_linear_dim(
                    base=(xs[i] + sw/2, dim_y_panels), p1=(xs[i], 0.0), p2=(xs[i+1], 0.0),
                    angle=0, dimstyle="COTA_LJ", dxfattribs={"layer": "COTA"})
                d.render()
            except Exception:
                pass

    # Cotas por painel vertical
    for j in range(len(ys) - 1):
        sh = ys[j+1] - ys[j]
        if sh > 1:
            try:
                d = msp.add_linear_dim(
                    base=(dim_x_panels, ys[j] + sh/2), p1=(comp, ys[j]), p2=(comp, ys[j+1]),
                    angle=90, dimstyle="COTA_LJ", dxfattribs={"layer": "COTA"})
                d.render()
            except Exception:
                pass'''

text = text.replace(old_cotas, new_cotas)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print('gerar_dxf_lajes.py updated successfully')
