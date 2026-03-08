import re
import os

# Mapping of old keys in Painel lists to New Keys in Dictionary
key_fixes = {
    'laje_a': 'laje_A', 'laje_b': 'laje_B', 'laje_c': 'laje_C', 'laje_d': 'laje_D',
    'posicao_laje_a': 'posicao_laje_A', 'posicao_laje_b': 'posicao_laje_B', 
    'posicao_laje_c': 'posicao_laje_C', 'posicao_laje_d': 'posicao_laje_D',
    
    'parafusos_p1_p2': 'parafuso_p1_p2', 'parafusos_p2_p3': 'parafuso_p2_p3',
    'parafusos_p3_p4': 'parafuso_p3_p4', 'parafusos_p4_p5': 'parafuso_p4_p5',
    'parafusos_p5_p6': 'parafuso_p5_p6', 'parafusos_p6_p7': 'parafuso_p6_p7',
    'parafusos_p7_p8': 'parafuso_p7_p8',
    'parafusos_p8_p9': 'parafuso_p8_p9',
}

def fix_key(k):
    if k in key_fixes: return key_fixes[k]
    k_new = k.replace('parafusos_', 'parafuso_')
    # Uppercase last segment if it is a single letter or panel suffix
    if k_new.endswith('_a'): k_new = k_new[:-2] + '_A'
    elif k_new.endswith('_b'): k_new = k_new[:-2] + '_B'
    elif k_new.endswith('_c'): k_new = k_new[:-2] + '_C'
    elif k_new.endswith('_d'): k_new = k_new[:-2] + '_D'
    return k_new

file_path = r'c:\Users\Ryzen\Desktop\GITHUB\Agente-cad-PYSIDE\_ROBOS_ABAS\Robo_Pilares\pilares-atualizado-09-25\src\interfaces\Painel_de_Controle.py'

if os.path.exists(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern: ('key', 123) or ('key', 123, 'ref')
    # Match group 2: key
    # Match group 4: number
    pattern = r"(\(')([^']+?)(',\s*)(\d+)(\s*(?:,\s*'[^']+')?)\)"

    def replace_tuple(m):
        key = m.group(2)
        val = m.group(4)
        extra = m.group(5) # , 'ref' or empty
        
        fixed_key = fix_key(key)
        
        # If val is a number (it is, per regex \d+)
        return f"('{fixed_key}', linhas_abcd['{fixed_key}']{extra})"

    new_content = re.sub(pattern, replace_tuple, content)

    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Refactored Painel_de_Controle.py lists")
    else:
        print("No changes needed in Painel_de_Controle.py lists")
else:
    print(f"File not found: {file_path}")
