import os

path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

start_sig = "def show_detail(self, item_data, override_type=None):"
if start_sig in content:
    idx = content.find("display_data['type'] = override_type")
    if idx != -1:
        insert_code = """
            orig_name = display_data.get('name', 'V?')
            if override_type == 'viga_lateral_a': display_data['name'] = f'L.{orig_name}.A'
            elif override_type == 'viga_lateral_b': display_data['name'] = f'L.{orig_name}.B'
            elif override_type == 'viga_fundo_c': display_data['name'] = f'F.{orig_name}.C-1'
"""
        # Só insere se ainda não foi inserido
        if "orig_name = display_data" not in content:
            content = content[:idx+38] + insert_code + content[idx+38:]
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("Titulo sincronizado via patch!")
        else:
            print("Já estava sincronizado.")
