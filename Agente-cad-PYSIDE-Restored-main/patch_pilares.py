import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove Pilares from _tag_robo_obra_combo so we can handle it manually
content = content.replace("self._tag_robo_obra_combo(self.robo_pilares, 'robo_obra_combo_pl')", "# self._tag_robo_obra_combo(self.robo_pilares, 'robo_obra_combo_pl')")

# Expand _sync_robos_obras to handle Pilares just like Laje!
old_sync_obras = """            # 2. Sync Pilares se tiver um ViewModel global
            if getattr(self, 'robo_pilares', None) and hasattr(self.robo_pilares, 'vm'):
                try:
                    # Tentar atualizar as obras do vm
                    if hasattr(self.robo_pilares.vm, 'obras'):
                        # Não vamos forçar objetos complexos se não conhecemos, o _tag_robo_obra_combo já lida com o texto.
                        pass
                except:
                    pass"""

new_sync_obras = """            # 2. Sync Pilares - usa ObraModel como data no combo_obra
            if getattr(self, 'robo_pilares', None):
                try:
                    import sys
                    pil_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25", "src")
                    if pil_path not in sys.path:
                        sys.path.append(pil_path)
                    
                    from models.obra_model import ObraModel as PilaresObra
                    from models.pavimento_model import PavimentoModel as PilaresPavimento
                    
                    # Achar o panel que contém o combo_obra
                    from PySide6.QtWidgets import QComboBox
                    combos = self.robo_pilares.findChildren(QComboBox)
                    combo_obra = next((c for c in combos if c.objectName() == 'combo_obra' or getattr(c, '_is_obra_combo', False)), None)
                    
                    # Pilares não seta objectName as vezes, vamos pegar o que tem as obras
                    if not combo_obra and hasattr(self.robo_pilares, 'panels') and hasattr(self.robo_pilares.panels, 'combo_obra'):
                        combo_obra = self.robo_pilares.panels.combo_obra
                        
                    if combo_obra:
                        curr = combo_obra.currentData()
                        curr_nome = curr.nome if curr and hasattr(curr, 'nome') else combo_obra.currentText()
                        
                        combo_obra.blockSignals(True)
                        combo_obra.clear()
                        
                        for w in works:
                            obra_mock = PilaresObra(nome=w)
                            for p in get_pavs(w):
                                obra_mock.pavimentos.append(PilaresPavimento(nome=p))
                            combo_obra.addItem(f"📁 {w}", obra_mock)
                            
                        # Restaurar selecao
                        found = False
                        for i in range(combo_obra.count()):
                            dt = combo_obra.itemData(i)
                            if dt and getattr(dt, 'nome', '') == curr_nome:
                                combo_obra.setCurrentIndex(i)
                                found = True
                                break
                        if not found: combo_obra.setCurrentIndex(-1)
                        combo_obra.blockSignals(False)
                        
                        # Atualizar a lista de obras na VM do Pilares
                        if hasattr(self.robo_pilares, 'vm') and hasattr(self.robo_pilares.vm, 'obras'):
                            self.robo_pilares.vm.obras = [combo_obra.itemData(i) for i in range(combo_obra.count()) if combo_obra.itemData(i)]
                except Exception as e:
                    self.log(f"Erro injetando obras no Pilares: {e}")"""

content = content.replace(old_sync_obras, new_sync_obras)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("main.py patched to support RoboPilares works and pavements!")
