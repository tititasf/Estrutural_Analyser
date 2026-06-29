import sys

fpath = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/_ROBOS_ABAS/Robo_Laterais_de_Vigas/robo_laterais_viga_pyside.py'
content = open(fpath, 'r', encoding='utf-8', errors='ignore').read()

import_stmt = 'from src.mcp.db_bridge import save_human_edit_event\n'
if 'save_human_edit_event' not in content:
    content = 'import sys\n' + import_stmt + content.replace('import sys\n', '', 1)

target = '''        # Auto-save session
        self.save_session_data()'''

new_target = '''        # Auto-save session
        self.save_session_data()
        
        try:
            save_human_edit_event(
                obra_id=self.current_obra or "Desconhecida",
                classe="Vigas",
                item_id=name_key,
                fase_editada="RoboLaterais_EdiçãoManual",
                campo_alterado="ficha_viga",
                valor_antigo="N/A",
                valor_novo="Salvo",
                nota_usuario="Ficha da Viga atualizada via Interface Gráfica",
                source_agent="Robo_Laterais_Vigas"
            )
        except Exception as e:
            print(f"Erro MCP db_bridge: {e}")
'''

if target in content:
    content = content.replace(target, new_target)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Sucesso! save_human_edit_event injetado no Laterais!")
else:
    print("Target nao encontrado.")
