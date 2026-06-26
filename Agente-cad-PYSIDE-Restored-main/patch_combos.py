import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix currentText and findText for sa_cmb_obras
content = content.replace("sa_idx = self.sa_cmb_obras.findText(work_name)", "sa_idx = self.sa_cmb_obras.findData(work_name)")
content = content.replace("obra = self.sa_cmb_obras.currentText()", "obra = self.sa_cmb_obras.currentData() or self.sa_cmb_obras.currentText()")
content = content.replace("obra_nome = self.sa_cmb_obras.currentText()", "obra_nome = self.sa_cmb_obras.currentData() or self.sa_cmb_obras.currentText()")

# Also initial setup of sa_cmb_obras in __init__
setup_old = """        _works = self.db.get_all_works()
        if _works:
            self.sa_cmb_obras.addItems(_works)"""
setup_new = """        _works = self.db.get_all_works()
        if _works:
            for w in _works:
                self.sa_cmb_obras.addItem(f"📁 {w}", w)"""
content = content.replace(setup_old, setup_new)

# Now, we inject the sync logic inside _refresh_nav_combos
sync_old = """            # Sincronizar combo do Diagnostic Reverse Hub
            if hasattr(self, 'diagnostic_reverse_module'):
                self.diagnostic_reverse_module.refresh_obras(works)
        except Exception as e:"""

sync_new = """            # Sincronizar combo do Diagnostic Reverse Hub
            if hasattr(self, 'diagnostic_reverse_module'):
                self.diagnostic_reverse_module.refresh_obras(works)

            # Sincronizar combo do Structural Analyzer
            if hasattr(self, 'sa_cmb_obras'):
                curr_sa = self.sa_cmb_obras.currentData()
                self.sa_cmb_obras.blockSignals(True)
                self.sa_cmb_obras.clear()
                for w in works:
                    self.sa_cmb_obras.addItem(f"📁 {w}", w)
                idx = self.sa_cmb_obras.findData(curr_sa)
                self.sa_cmb_obras.setCurrentIndex(idx if idx >= 0 else -1)
                self.sa_cmb_obras.blockSignals(False)

            # Tentar sincronizar comboboxes marcados dos robôs (caso existam e sejam baseados em strings)
            try:
                from PySide6.QtWidgets import QComboBox
                for tag in ['robo_obra_combo_lv', 'robo_obra_combo_fv', 'robo_obra_combo_pl']: # Excluí Laje por usar DataUserData complexo
                    c = self.findChild(QComboBox, tag)
                    if c:
                        curr = c.currentData() or c.currentText()
                        c.blockSignals(True)
                        
                        # Verifica se o combo usa objetos no data
                        if c.count() > 0 and c.itemData(0) is not None and not isinstance(c.itemData(0), (str, int)):
                            continue # Ignora se usar objetos complexos para não quebrar
                            
                        c.clear()
                        for w in works:
                            c.addItem(f"📁 {w}", w)
                        idx = c.findData(curr)
                        c.setCurrentIndex(idx if idx >= 0 else -1)
                        c.blockSignals(False)
            except Exception as e:
                self.log(f"Erro ao atualizar combos dos robôs: {e}")

        except Exception as e:"""

content = content.replace(sync_old, sync_new)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("main.py patched successfully.")
