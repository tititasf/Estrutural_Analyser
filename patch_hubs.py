import sys

# 1. diagnostic_hub.py
fpath_hub = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/src/ui/modules/diagnostic_hub.py'
try:
    content = open(fpath_hub, 'r', encoding='utf-8').read()
    import_stmt = 'from src.mcp.db_bridge import save_human_edit_event\n'
    if 'save_human_edit_event' not in content:
        content = 'import sys\n' + import_stmt + content.replace('import sys\n', '', 1)

    target_hub = "    def _save_current_crop(self):\n        if not self._current_item:"
    new_target_hub = '''    def _save_current_crop(self):
        if not self._current_item: return
        try:
            item_id = f"{self._current_item.get('classe', 'Unk')}_{self._current_item.get('numero', '0')}"
            save_human_edit_event(
                obra_id="N/A",
                classe=self._current_item.get("classe", "Unk"),
                item_id=item_id,
                fase_editada="PreHub_Edicao_Recorte",
                campo_alterado="dimensao_recorte",
                valor_antigo="N/A",
                valor_novo="Editado",
                nota_usuario="Recorte salvo via Diagnostic Hub Pre",
                source_agent="diagnostic_hub"
            )
        except Exception as e:
            print(f"Erro MCP db_bridge no Pre-Hub: {e}")
            
        if not self._current_item:'''
    if target_hub in content:
        content = content.replace(target_hub, new_target_hub)
        open(fpath_hub, 'w', encoding='utf-8').write(content)
        print("Patched diagnostic_hub.py")
    else:
        print("Target hub_crop nao encontrado.")
except Exception as e:
    print(f"Erro hub: {e}")

# 2. diagnostic_reverse_hub.py
fpath_rev = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/src/ui/modules/diagnostic_reverse_hub.py'
try:
    content_rev = open(fpath_rev, 'r', encoding='utf-8').read()
    if 'save_human_edit_event' not in content_rev:
        content_rev = 'import sys\n' + import_stmt + content_rev.replace('import sys\n', '', 1)

    target_rev = "    def _save_granular_dxf(self):"
    new_target_rev = '''    def _save_granular_dxf(self):
        try:
            item_id = f"{self._current_item.get('classe', 'Unk')}_{self._current_item.get('numero', '0')}" if hasattr(self, '_current_item') and self._current_item else "Unknown"
            save_human_edit_event(
                obra_id="N/A",
                classe=self._current_item.get("classe", "Unk") if hasattr(self, '_current_item') and self._current_item else "Unk",
                item_id=item_id,
                fase_editada="ReverseHub_Edicao_Recorte",
                campo_alterado="dimensao_recorte",
                valor_antigo="N/A",
                valor_novo="Editado",
                nota_usuario="Recorte salvo via Diagnostic Reverse Hub",
                source_agent="diagnostic_reverse_hub"
            )
        except Exception as e:
            print(f"Erro MCP db_bridge no Reverse-Hub: {e}")
'''
    if target_rev in content_rev:
        content_rev = content_rev.replace(target_rev, new_target_rev)
        open(fpath_rev, 'w', encoding='utf-8').write(content_rev)
        print("Patched diagnostic_reverse_hub.py")
    else:
        print("Target rev_crop nao encontrado.")
except Exception as e:
    print(f"Erro rev_hub: {e}")

