import os

path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Atualizar a assinatura de show_detail
old_sig = "def show_detail(self, item_data):"
new_sig = "def show_detail(self, item_data, override_type=None):"
content = content.replace(old_sig, new_sig)

# 2. Atualizar a lógica do override_type
old_logic = '''        display_data = item_data
        
        # Limpar anterior'''

old_logic_2 = '''        display_data = item_data
        if override_type:
            display_data = item_data.copy()
            display_data['type'] = override_type
        
        # Limpar anterior'''

new_logic = '''        display_data = item_data
        if override_type:
            display_data = item_data.copy()
            display_data['type'] = override_type
            orig_name = display_data.get('name', 'V?')
            if override_type == 'viga_lateral_a': display_data['name'] = f'L.{orig_name}.A'
            elif override_type == 'viga_lateral_b': display_data['name'] = f'L.{orig_name}.B'
            elif override_type == 'viga_fundo_c': display_data['name'] = f'F.{orig_name}.C-1'
            
        # Limpar anterior'''

# Tentar substituir
if "if override_type:" in content and "orig_name =" not in content:
    # Caso onde o override_type existe mas o titulo nao
    content = content.replace(old_logic_2, new_logic)
elif "if override_type:" not in content:
    content = content.replace(old_logic, new_logic)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch aplicado com sucesso!")
