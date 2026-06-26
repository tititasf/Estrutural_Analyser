import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the old _sync_robos_obras entirely and replace it with a robust central sync
old_sync_obras_match = re.search(r'    def _sync_robos_obras\(self\).*?(?=    def )', content, re.DOTALL)
if old_sync_obras_match:
    content = content.replace(old_sync_obras_match.group(0), "")

old_sync_pavs_match = re.search(r'    def _sync_robos_pavimentos\(self, pavs: list\[str\]\).*?(?=    def )', content, re.DOTALL)
if old_sync_pavs_match:
    content = content.replace(old_sync_pavs_match.group(0), "")

new_sync_logic = """    def _sync_robos_obras_e_pavimentos(self, global_work_name=None):
        \"\"\"
        Sincronização central e robusta de TODOS os robôs com o banco de dados.
        Preenche as obras (baseado em db.get_all_works) e os pavimentos (db.get_projects).
        Se global_work_name for passado, força a seleção desta obra nos robôs.
        \"\"\"
        try:
            works = self.db.get_all_works()
            all_projects = self.db.get_projects()
            
            def get_pavs(work_name):
                filtered = [p for p in all_projects if p.get('work_name') == work_name]
                raw_pavs = sorted(list(set([p.get('pavement_name') or p.get('name') for p in filtered if (p.get('pavement_name') or p.get('name'))])))
                return raw_pavs

            # ----- Laje -----
            if getattr(self, 'robo_laje', None) and hasattr(self.robo_laje, 'obra_control'):
                try:
                    c = self.robo_laje.obra_control.obra_combo
                    c.blockSignals(True)
                    curr_nome = global_work_name if global_work_name else (c.currentData().nome if c.currentData() and hasattr(c.currentData(), 'nome') else c.currentText())
                    c.clear()
                    from laje_src.models.obra import Obra as LajeObra
                    from laje_src.models.pavimento import Pavimento as LajePavimento
                    for w in works:
                        obra_mock = LajeObra(nome=w)
                        for p in get_pavs(w):
                            obra_mock.pavimentos.append(LajePavimento(nome=p))
                        c.addItem(f"📁 {w}", obra_mock)
                    
                    # Restaurar/Forçar seleção
                    found = False
                    for i in range(c.count()):
                        dt = c.itemData(i)
                        if dt and getattr(dt, 'nome', '') == curr_nome:
                            c.setCurrentIndex(i)
                            found = True
                            break
                    if not found: c.setCurrentIndex(0 if c.count() > 0 else -1)
                    c.blockSignals(False)
                    
                    # Força atualização da aba (dispara o evento manualmente se estivermos setando do global)
                    if global_work_name and found:
                        if hasattr(self.robo_laje.obra_control, 'obra_changed'):
                            self.robo_laje.obra_control.obra_changed.emit(c.currentData())
                except Exception as e:
                    self.log(f"Erro Laje: {e}")

            # ----- Pilares -----
            if getattr(self, 'robo_pilares', None):
                try:
                    import sys
                    pil_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25", "src")
                    if pil_path not in sys.path: sys.path.append(pil_path)
                    
                    from models.obra_model import ObraModel as PilaresObra
                    from models.pavimento_model import PavimentoModel as PilaresPavimento
                    from PySide6.QtWidgets import QComboBox
                    
                    combos = self.robo_pilares.findChildren(QComboBox)
                    combo_obra = next((c for c in combos if c.objectName() == 'combo_obra' or getattr(c, '_is_obra_combo', False)), None)
                    if not combo_obra and hasattr(self.robo_pilares, 'panels') and hasattr(self.robo_pilares.panels, 'combo_obra'):
                        combo_obra = self.robo_pilares.panels.combo_obra
                        
                    if combo_obra:
                        combo_obra.blockSignals(True)
                        curr_nome = global_work_name if global_work_name else (combo_obra.currentData().nome if combo_obra.currentData() and hasattr(combo_obra.currentData(), 'nome') else combo_obra.currentText())
                        combo_obra.clear()
                        
                        obras_models = []
                        for w in works:
                            obra_mock = PilaresObra(nome=w)
                            for p in get_pavs(w):
                                obra_mock.pavimentos.append(PilaresPavimento(nome=p))
                            combo_obra.addItem(f"📁 {w}", obra_mock)
                            obras_models.append(obra_mock)
                            
                        # Atualizar a VM global do Pilares
                        if hasattr(self.robo_pilares, 'vm') and hasattr(self.robo_pilares.vm, 'obras'):
                            self.robo_pilares.vm.obras = obras_models

                        found = False
                        for i in range(combo_obra.count()):
                            dt = combo_obra.itemData(i)
                            if dt and getattr(dt, 'nome', '') == curr_nome:
                                combo_obra.setCurrentIndex(i)
                                found = True
                                break
                        if not found: combo_obra.setCurrentIndex(0 if combo_obra.count() > 0 else -1)
                        combo_obra.blockSignals(False)
                        
                        # Dispara evento para renderizar tabela
                        if global_work_name and found:
                            if hasattr(self.robo_pilares, 'panels') and hasattr(self.robo_pilares.panels, 'on_obra_changed'):
                                self.robo_pilares.panels.on_obra_changed(combo_obra.currentIndex())
                except Exception as e:
                    self.log(f"Erro Pilares: {e}")

            # ----- Viga e Fundo (Combos Simples) -----
            for robo, is_viga in [(getattr(self, 'robo_viga', None), True), (getattr(self, 'robo_fundo', None), False)]:
                if not robo: continue
                try:
                    from PySide6.QtWidgets import QComboBox
                    combos = robo.findChildren(QComboBox)
                    cmb_obra = next((c for c in combos if 'obra' in c.objectName().lower()), None)
                    cmb_pav = next((c for c in combos if 'pav' in c.objectName().lower()), None)
                    
                    if not cmb_obra and hasattr(robo, 'cmb_obra'): cmb_obra = robo.cmb_obra
                    if not cmb_obra and hasattr(robo, 'combo_obra'): cmb_obra = robo.combo_obra
                    
                    if not cmb_pav and hasattr(robo, 'cmb_pav'): cmb_pav = robo.cmb_pav
                    if not cmb_pav and hasattr(robo, 'combo_pavimento'): cmb_pav = robo.combo_pavimento
                    
                    if cmb_obra:
                        cmb_obra.blockSignals(True)
                        curr_obra = global_work_name if global_work_name else (cmb_obra.currentData() or cmb_obra.currentText())
                        if str(curr_obra).startswith("📁 "): curr_obra = str(curr_obra).replace("📁 ", "")
                        cmb_obra.clear()
                        for w in works:
                            cmb_obra.addItem(f"📁 {w}", w)
                        idx = cmb_obra.findData(curr_obra)
                        if idx >= 0: cmb_obra.setCurrentIndex(idx)
                        elif cmb_obra.count() > 0: cmb_obra.setCurrentIndex(0)
                        cmb_obra.blockSignals(False)
                        
                        # Set current obra correctly for the next step
                        curr_obra = cmb_obra.currentData()
                        
                        # Disconnect internal on_obra_changed so it doesn't overwrite our pavements!
                        if hasattr(robo, 'on_obra_changed'):
                            try: cmb_obra.currentIndexChanged.disconnect(robo.on_obra_changed)
                            except: pass
                            try: cmb_obra.currentTextChanged.disconnect(robo.on_obra_changed)
                            except: pass
                        
                        # Populate pavements explicitly
                        if cmb_pav and curr_obra:
                            cmb_pav.blockSignals(True)
                            curr_pav = cmb_pav.currentData() or cmb_pav.currentText()
                            cmb_pav.clear()
                            cmb_pav.addItem("TODOS", "TODOS")
                            for p in get_pavs(curr_obra):
                                cmb_pav.addItem(p, p)
                            idx_pav = cmb_pav.findData(curr_pav)
                            cmb_pav.setCurrentIndex(idx_pav if idx_pav >= 0 else 0)
                            cmb_pav.blockSignals(False)

                except Exception as e:
                    self.log(f"Erro Viga/Fundo: {e}")

        except Exception as e:
            self.log(f"Erro geral _sync_robos_obras_e_pavimentos: {e}")

"""

content = content.replace("    def _current_pavement_name", new_sync_logic + "\n    def _current_pavement_name")

# Modify _on_work_changed to use the new unified sync
old_on_work_changed_end = """        # Sincroniza pavimentos e obras extras com os Robôs
        raw_pavs = [p.get('pavement_name') or p.get('name') for p in filtered]
        self._sync_robos_pavimentos(raw_pavs)

        # Nao auto-selecionar pavimento: carregar projeto apenas apos escolha explicita."""

new_on_work_changed_end = """        # Força todos os robôs a espelharem a Obra global e seus pavimentos limpos
        self._sync_robos_obras_e_pavimentos(global_work_name=work_name)

        # Nao auto-selecionar pavimento: carregar projeto apenas apos escolha explicita."""

content = content.replace(old_on_work_changed_end, new_on_work_changed_end)

# In _refresh_nav_combos, call the new sync instead of the old ones
content = content.replace("self._sync_robos_obras()", "self._sync_robos_obras_e_pavimentos()")

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch super robusto aplicado! Viga/Fundo desconectados de lógicas antigas, Pilares e Laje forçados a atualizar tabelas/views.")
