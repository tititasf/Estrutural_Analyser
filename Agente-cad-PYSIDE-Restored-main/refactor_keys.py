import re
import os

files_to_process = [
    r'c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\src\interfaces\Abcd_Excel.py',
    r'c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\src\interfaces\Painel_de_Controle.py'
]

def replace_func(m):
    # m.group(1) = opening quote
    # m.group(2) = base name (e.g. laje)
    # m.group(3) = suffix (a, b...)
    # m.group(4) = closing quote
    # m.group(5) = separator (: or ])
    
    return f"{m.group(1)}{m.group(2)}_{m.group(3).upper()}{m.group(4)}{m.group(5)}"

rules = [
    # Replace dictionary keys and lookups ending in _a, _b, etc. with _A, _B
    # Patterns: 'something_a':, "something_a":, ['something_a'], ["something_a"]
    # We restrict base name to contain alphanumerics and underscores.
    # Excludes: things that shouldn't change.
    (r"(['\"])([a-zA-Z0-9_]+)_(a|b|c|d|e|f|g|h)(['\"])(\s*[:\]])", replace_func),
    
    # Specific fix for campos_altura access
    (r"campos_altura\['([a-h])'\]", lambda m: f"campos_altura['{m.group(1).upper()}']"),
    (r"campos_altura\[\"([a-h])\"\]", lambda m: f"campos_altura[\"{m.group(1).upper()}\"]"),
    
    # Specific fix for hatch_opcoes access (e.g. gerador.hatch_opcoes_a)
    (r"hatch_opcoes_([a-h])", lambda m: f"hatch_opcoes_{m.group(1).upper()}"),
    
    # Specific fix for abertura_laje access (e.g. self.abertura_laje['a'])
    (r"abertura_laje\['([a-h])'\]", lambda m: f"abertura_laje['{m.group(1).upper()}']"),
    (r"abertura_laje\[\"([a-h])\"\]", lambda m: f"abertura_laje[\"{m.group(1).upper()}\"]"),
    
    # Specific fix for abertura_topo2 access
    (r"abertura_topo2\['([a-h])'\]", lambda m: f"abertura_topo2['{m.group(1).upper()}']"),
    (r"abertura_topo2\[\"([a-h])\"\]", lambda m: f"abertura_topo2[\"{m.group(1).upper()}\"]"),
    
    # Fix for compX_a in campos_ab (e.g. 'comp1_a')
    (r"(['\"])comp([0-9])_([a-h])(['\"])", lambda m: f"{m.group(1)}comp{m.group(2)}_{m.group(3).upper()}{m.group(4)}"),
]

for file_path in files_to_process:
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        continue
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    original = content
    for pattern, replacement in rules:
        content = re.sub(pattern, replacement, content)
        
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {file_path}")
    else:
        print(f"No changes for {file_path}")
