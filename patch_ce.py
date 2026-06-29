import sys
fpath = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/src/ui/modules/comparison_engine.py'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

import_stmt = "from src.mcp.db_bridge import save_human_edit_event\n"
if "save_human_edit_event" not in content[:3000] and "import json" in content:
    content = content.replace("import json\n", "import json\n" + import_stmt)

def_old = """    def _on_save_sa_clicked(self):
        # Disparado ao clicar no botão salvar inline
        if self._attention_callback:
            self._attention_callback()
        
        # Opcional: Se desejar dar um feedback visual no botão de salvo
        self._btn_save_sa.setText("✅ Salvo!")
        QTimer.singleShot(2000, lambda: self._btn_save_sa.setText("💾 Salvar Alterações"))"""

def_new = """    def _on_save_sa_clicked(self):
        # Disparado ao clicar no botão salvar inline
        if self._attention_callback:
            self._attention_callback()
            
        try:
            # Pegando contexto da UI
            nota = self._attention_text.toPlainText()
            item_id = self._score_label.text().split()[0] if self._score_label.text() else "Item"
            
            save_human_edit_event(
                obra_id="N/A",  # Ou extrair do context manager se disponível
                classe="Estrutural",
                item_id=item_id,
                fase_editada="SA_Atenção",
                campo_alterado="nota_atencao",
                valor_antigo="N/A",
                valor_novo=nota,
                nota_usuario="Salvo pelo SA Comparison Engine",
                source_agent="agente_estrutural"
            )
        except Exception as e:
            print(f"Erro ao salvar evento MCP: {e}")
            
        # Opcional: Se desejar dar um feedback visual no botão de salvo
        self._btn_save_sa.setText("✅ Salvo!")
        QTimer.singleShot(2000, lambda: self._btn_save_sa.setText("💾 Salvar Alterações"))"""

if def_old in content:
    content = content.replace(def_old, def_new)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patch applied to comparison_engine.py successfully (save_human_edit_event injected)!")
else:
    print("def_old not found in comparison_engine.py")

