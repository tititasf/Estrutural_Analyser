import sys
fpath = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/src/ui/modules/comparison_engine.py'
with open(fpath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "# Linha 2: campo de nota compacto (3 linhas, scroll, max 3000 chars)" in line:
        new_lines.append("        # Linha 2: Botão Salvar (Event Sourcing)\n")
        new_lines.append("        self._btn_save_sa = QPushButton(\"💾 Salvar Alterações\")\n")
        new_lines.append("        self._btn_save_sa.setToolTip(\"Salva as edições atuais da ficha e gera log de aprendizado\")\n")
        new_lines.append("        self._btn_save_sa.setStyleSheet(\n")
        new_lines.append("            f\"background-color: {Colors.ACCENT_SUCCESS}; color: white; \"\n")
        new_lines.append("            f\"border: none; border-radius: 3px; font-weight: bold; font-size: 10px; padding: 4px;\"\n")
        new_lines.append("        )\n")
        new_lines.append("        self._btn_save_sa.clicked.connect(self._on_save_sa_clicked)\n")
        new_lines.append("        att_inline_lay.addWidget(self._btn_save_sa)\n\n")
    new_lines.append(line)
    
    if "def _emit_attention_changed(self):" in line:
        new_lines.append("""
    def _on_save_sa_clicked(self):
        # Disparado ao clicar no botão salvar inline
        if self._attention_callback:
            self._attention_callback()
        
        # Opcional: Se desejar dar um feedback visual no botão de salvo
        self._btn_save_sa.setText("✅ Salvo!")
        QTimer.singleShot(2000, lambda: self._btn_save_sa.setText("💾 Salvar Alterações"))

""")

with open(fpath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Patch applied to comparison_engine.py successfully!")
