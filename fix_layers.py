import sys

scripts = [
    r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\gerar_dxf_lajes.py',
    r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\gerar_dxf_vigas.py'
]

for script in scripts:
    with open(script, 'r', encoding='utf-8') as f:
        text = f.read()
    
    text = text.replace("doc.layers.new(name)", "doc.layers.new(name, dxfattribs={'color': color})")
    
    with open(script, 'w', encoding='utf-8') as f:
        f.write(text)

print('Fixed layer colors in dxf generators')
