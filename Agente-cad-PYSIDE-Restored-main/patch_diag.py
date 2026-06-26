import re

with open('src/ui/modules/diagnostic_reverse_hub.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update _populate_obra_combo to add the emoji and set data
old_populate = """        for obra in obras:
            self.cmb_obra.addItem(obra)
        if current:
            idx = self.cmb_obra.findText(current)"""

new_populate = """        for obra in obras:
            self.cmb_obra.addItem(f"📁 {obra}", obra)
        if current:
            idx = self.cmb_obra.findData(current)"""

content = content.replace(old_populate, new_populate)

# 2. Fix _on_cmb_obra_changed to use currentData
old_changed = """    def _on_cmb_obra_changed(self, obra_name: str):
        if obra_name and obra_name != self._current_obra:"""

new_changed = """    def _on_cmb_obra_changed(self, obra_name: str):
        obra_name = self.cmb_obra.currentData() or obra_name
        if obra_name and obra_name != self._current_obra:"""

content = content.replace(old_changed, new_changed)

with open('src/ui/modules/diagnostic_reverse_hub.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("diagnostic_reverse_hub.py patched successfully.")
