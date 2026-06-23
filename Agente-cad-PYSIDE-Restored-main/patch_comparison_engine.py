import re

with open('src/ui/modules/comparison_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update _populate_obras to fetch from DB instead of filesystem
old_populate = """    def _populate_obras(self):
        \"\"\"Lista obras disponíveis ordenando TREINO primeiro, depois outras.\"\"\"
        self.cmb_obra.blockSignals(True)
        self.cmb_obra.clear()
        if not DADOS_OBRAS_ROOT.exists():
            self.cmb_obra.blockSignals(False)
            return

        all_obras = [d.name for d in DADOS_OBRAS_ROOT.iterdir()
                     if d.is_dir() and d.name.startswith("Obra_")]
        # TREINO primeiro (ordenadas numericamente), depois outras alfabeticamente
        treino = sorted([o for o in all_obras if "TREINO" in o],
                        key=lambda x: int(x.split("_")[-1]) if x.split("_")[-1].isdigit() else 999)
        outros = sorted([o for o in all_obras if "TREINO" not in o])
        obras = treino + outros

        for o in obras:
            self.cmb_obra.addItem(o)"""

new_populate = """    def _populate_obras(self):
        \"\"\"Lista obras disponíveis pegando do banco para manter consistência.\"\"\"
        self.cmb_obra.blockSignals(True)
        self.cmb_obra.clear()
        
        try:
            from core.database import DatabaseManager
            db = DatabaseManager('D:/Agente-cad-PYSIDE/project_data.vision')
            works = db.get_all_works()
        except Exception:
            works = []

        for o in works:
            self.cmb_obra.addItem(f"📁 {o}", o)"""

content = content.replace(old_populate, new_populate)

# 2. Fix _on_obra_changed signature to use the data instead of text
# Find: def _on_obra_changed(self, obra_name: str):
content = content.replace("def _on_obra_changed(self, obra_name: str):", 
                          "def _on_obra_changed(self, obra_name: str):\n        obra_name = self.cmb_obra.currentData() or obra_name")

# 3. Replace all .currentText() for combos with .currentData()
content = content.replace("self.cmb_obra.currentText()", "(self.cmb_obra.currentData() or self.cmb_obra.currentText())")
content = content.replace("self.fase8_panel.cmb_obra.currentText()", "(self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())")
content = content.replace("self.cmb_obra.findText(", "self.cmb_obra.findData(")
content = content.replace("self.fase8_panel.cmb_obra.findText(", "self.fase8_panel.cmb_obra.findData(")

# Also fix the initial selection logic in _populate_obras
old_initial = """        primeira_com_score = next(
            (o for o in treino
             if (VALIDACAO_DIR / f"consolidado_{o}.json").exists()),
            obras[0] if obras else None
        )
        if self._auto_select_initial_obra and primeira_com_score:
            idx = self.cmb_obra.findText(primeira_com_score)"""

new_initial = """        primeira_com_score = next(
            (o for o in works
             if (VALIDACAO_DIR / f"consolidado_{o}.json").exists()),
            works[0] if works else None
        )
        if self._auto_select_initial_obra and primeira_com_score:
            idx = self.cmb_obra.findData(primeira_com_score)"""

content = content.replace(old_initial, new_initial)

with open('src/ui/modules/comparison_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("comparison_engine.py patched successfully.")
