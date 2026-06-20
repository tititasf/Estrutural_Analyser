import os

path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Ajustar _populate_beam_tree (evitar dupes de F.V301)
old_1 = '''        for p_name, segments in groups.items():
            parent_item = QTreeWidgetItem(tree_widget)
            prefix = "F." if list_type == 'fundo' else "L."'''

new_1 = '''        for p_name, segments in groups.items():
            parent_item = QTreeWidgetItem(tree_widget)
            
            clean_name = p_name
            if clean_name.startswith('F.'): clean_name = clean_name[2:]
            elif clean_name.startswith('L.'): clean_name = clean_name[2:]
            
            prefix = "F." if list_type == 'fundo' else "L."'''

if old_1 in content:
    content = content.replace(old_1, new_1)
    # E substituir p_name por clean_name apenas na criacao dos nomes visuais
    content = content.replace('f"📁 {prefix}{p_name}"', 'f"📁 {prefix}{clean_name}"')
    content = content.replace('f"{prefix}{p_name}.A"', 'f"{prefix}{clean_name}.A"')
    content = content.replace('f"{prefix}{p_name}.B"', 'f"{prefix}{clean_name}.B"')
    content = content.replace('f"{prefix}{p_name}.C-1"', 'f"{prefix}{clean_name}.C-1"')
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Arvore Limpa com Sucesso!')
else:
    print('Nao processado. Pode ja estar limpo ou o padrao nao bateu.')
