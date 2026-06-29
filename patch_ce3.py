import sys

fpath = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/src/ui/modules/comparison_engine.py'
content = open(fpath, 'r', encoding='utf-8').read()

import_stmt = 'from src.mcp.db_bridge import save_human_edit_event\n'
if 'save_human_edit_event' not in content:
    content = 'import sys\n' + import_stmt + content.replace('import sys\n', '')

old_func_start = "    def _on_save_sa_clicked(self):\n        # Disparado ao clicar"
new_func = '''    def _on_save_sa_clicked(self):
        if self._attention_callback:
            self._attention_callback()
            
        try:
            nota = self._attention_text.toPlainText()
            item_id = self._score_label.text().split()[0] if self._score_label.text() else "Item"
            save_human_edit_event(
                obra_id="Obra_Atual",
                classe="SA",
                item_id=item_id,
                fase_editada="SA_Atenção",
                campo_alterado="nota_atencao",
                valor_antigo="N/A",
                valor_novo=nota,
                nota_usuario="Botão salvar clicado no SA",
                source_agent="comparison_engine"
            )
        except Exception as e:
            print(f"Erro salvando db_bridge: {e}")
            
        self._btn_save_sa.setText("✅ Salvo!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._btn_save_sa.setText("💾 Salvar Alterações"))

'''

lines = content.splitlines()
out_lines = []
skip = False
found = False

for line in lines:
    if line.startswith("    def _on_save_sa_clicked(self):"):
        skip = True
        found = True
        out_lines.append(new_func)
        continue
    
    if skip:
        # Pula até a próxima função ou classe
        if line.startswith("    def ") or line.startswith("class ") or line.startswith("    # "):
            if not "QTimer.singleShot" in line and not "_btn_save_sa.setText" in line:
                skip = False
    
    if not skip:
        out_lines.append(line)

if found:
    open(fpath, 'w', encoding='utf-8').write('\n'.join(out_lines))
    print('Sucesso injetando no comparison engine sem regex!')
else:
    print('Função não encontrada.')

