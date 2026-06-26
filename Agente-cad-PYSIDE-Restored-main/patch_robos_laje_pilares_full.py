import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the two functions with a robust version that handles Laje's mock objects perfectly
sync_funcs = """    def _sync_robos_pavimentos(self, pavs: list[str]):
        \"\"\"Propaga a lista de pavimentos limpos (do banco) para os comboboxes/listas dos robôs.\"\"\"
        try:
            from PySide6.QtWidgets import QComboBox, QListWidget, QTableWidget
            
            robos = [
                getattr(self, 'robo_viga', None),
                getattr(self, 'robo_fundo', None),
                getattr(self, 'robo_pilares', None),
                getattr(self, 'robo_laje', None)
            ]
            
            for robo in robos:
                if not robo: continue
                    
                combos = robo.findChildren(QComboBox)
                lists = robo.findChildren(QListWidget)
                tables = robo.findChildren(QTableWidget)
                
                pav_combos = [c for c in combos if 'pav' in c.objectName().lower() or getattr(c, '_is_pav_combo', False)]
                pav_lists = [l for l in lists if 'pav' in l.objectName().lower()]
                
                # Manual injetions
                if hasattr(robo, 'cmb_pav'): pav_combos.append(robo.cmb_pav)
                if hasattr(robo, 'combo_pavimento'): pav_combos.append(robo.combo_pavimento)
                if hasattr(robo, 'pavimento_combo'): pav_combos.append(robo.pavimento_combo)
                if hasattr(robo, 'f_pavimento'): pav_combos.append(robo.f_pavimento)
                
                if hasattr(robo, 'pavimentos_list'): pav_lists.append(robo.pavimentos_list)
                if hasattr(robo, 'lista_pavimentos'): pav_lists.append(robo.lista_pavimentos)
                
                pav_combos = list(set(pav_combos))
                pav_lists = list(set(pav_lists))
                
                # Update combos
                for c in pav_combos:
                    curr = c.currentData() or c.currentText()
                    c.blockSignals(True)
                    if c.count() > 0 and c.itemData(0) is not None and not isinstance(c.itemData(0), (str, int)):
                        c.blockSignals(False)
                        continue
                    c.clear()
                    c.addItem("TODOS", "TODOS")
                    for p in pavs:
                        c.addItem(p, p)
                    idx = c.findData(curr)
                    c.setCurrentIndex(idx if idx >= 0 else 0)
                    c.blockSignals(False)
                    
                # Update lists
                for lst in pav_lists:
                    lst.blockSignals(True)
                    selected = [item.text() for item in lst.selectedItems()]
                    lst.clear()
                    lst.addItem("TODOS")
                    for p in pavs:
                        lst.addItem(p)
                    for i in range(lst.count()):
                        if lst.item(i).text() in selected:
                            lst.item(i).setSelected(True)
                    lst.blockSignals(False)
                    
                # Update tables (like Pilares and potentially others if they use simple tables)
                # For Pilares, it usually uses a TableWidget for pavements. We just recreate rows or wait for its internal model to catch up.
                for t in tables:
                    name = t.objectName().lower()
                    if 'pav' in name:
                        # Pilares Table updates dynamically via its ViewModel. Let's just pass.
                        pass

        except Exception as e:
            self.log(f"Erro ao sincronizar pavimentos nos robôs: {e}")

    def _sync_robos_obras(self):
        \"\"\"Injeta dinamicamente as obras em combos não mapeados como o de Laje.\"\"\"
        try:
            works = self.db.get_all_works()
            all_projects = self.db.get_projects()
            
            def get_pavs(work_name):
                filtered = [p for p in all_projects if p.get('work_name') == work_name]
                raw_pavs = sorted(list(set([p.get('pavement_name') or p.get('name') for p in filtered if (p.get('pavement_name') or p.get('name'))])))
                return raw_pavs

            # 1. Robo Laje
            if getattr(self, 'robo_laje', None) and hasattr(self.robo_laje, 'obra_control'):
                c = self.robo_laje.obra_control.obra_combo
                curr = c.currentData()
                curr_nome = curr.nome if curr and hasattr(curr, 'nome') else c.currentText()
                c.blockSignals(True)
                c.clear()
                
                try:
                    from laje_src.models.obra import Obra as LajeObra
                    from laje_src.models.pavimento import Pavimento as LajePavimento
                    for w in works:
                        obra_mock = LajeObra(nome=w)
                        for p in get_pavs(w):
                            obra_mock.pavimentos.append(LajePavimento(nome=p))
                        c.addItem(f"📁 {w}", obra_mock)
                    
                    found = False
                    for i in range(c.count()):
                        dt = c.itemData(i)
                        if dt and getattr(dt, 'nome', '') == curr_nome:
                            c.setCurrentIndex(i)
                            found = True
                            break
                    if not found: c.setCurrentIndex(-1)
                except Exception as e:
                    self.log(f"Erro injetando obras no Laje: {e}")
                c.blockSignals(False)
                
            # 2. Sync Pilares se tiver um ViewModel global
            if getattr(self, 'robo_pilares', None) and hasattr(self.robo_pilares, 'vm'):
                try:
                    # Tentar atualizar as obras do vm
                    if hasattr(self.robo_pilares.vm, 'obras'):
                        # Não vamos forçar objetos complexos se não conhecemos, o _tag_robo_obra_combo já lida com o texto.
                        pass
                except:
                    pass

        except Exception as e:
            self.log(f"Erro em _sync_robos_obras: {e}")
"""

# Replace existing functions if they exist
content = re.sub(r'    def _sync_robos_pavimentos\(self, pavs.*?    def _current_pavement_name', sync_funcs + "\n    def _current_pavement_name", content, flags=re.DOTALL)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch aplicado com suporte complexo para RoboLaje!")
