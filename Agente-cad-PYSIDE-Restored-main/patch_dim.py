import os
import re

path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern to replace
pattern = r"# 5\. DIMENSÃO POR SEGMENTO.*?segments = b\['links'\]\[field_key\]\.get\(side_key, \[\]\)"

replacement = """# 5. DIMENSÃO POR SEGMENTO
        # Associar textos de dimensão específicos a segmentos específicos baseados em proximidade
        if len(dim_texts) > 0:
            for side_key, prefix_key in [('seg_side_a', 'viga_a'), ('seg_side_b', 'viga_b')]:
                # varrer ate o limite razoavel de segmentos criados na memoria
                for i in range(1, 10):
                    field_key = f'{prefix_key}_seg_{i}_comp_total_passa'
                    if field_key not in b['links']:
                        continue
                    segments = b['links'][field_key].get(side_key, [])"""

if re.search(pattern, content, flags=re.DOTALL):
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Patch nas Dimensoes Aplicado!")
else:
    print("Nao achou o bloco de Dimensoes!")
