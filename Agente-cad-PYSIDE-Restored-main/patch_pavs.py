import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. First, we define a helper function inside MainApp to sync pavements to robots
sync_pavs_func = """    def _sync_robos_pavimentos(self, pavs: list[str]):
        \"\"\"Propaga a lista de pavimentos limpos (do banco) para os comboboxes/listas dos robôs.\"\"\"
        try:
            from PySide6.QtWidgets import QComboBox, QListWidget
            
            # Lista de atributos de robôs em main.py
            robos = [
                getattr(self, 'robo_viga', None),
                getattr(self, 'robo_fundo', None),
                getattr(self, 'robo_pilares', None),
                getattr(self, 'robo_laje', None)
            ]
            
            for robo in robos:
                if not robo:
                    continue
                    
                # Acha todos os QComboBox e QListWidget no robo
                combos = robo.findChildren(QComboBox)
                lists = robo.findChildren(QListWidget)
                
                # Filtra os que tem 'pav' no nome (como cmb_pav, combo_pavimento, etc)
                pav_combos = [c for c in combos if 'pav' in c.objectName().lower() or getattr(c, '_is_pav_combo', False)]
                pav_lists = [l for l in lists if 'pav' in l.objectName().lower()]
                
                # Mas para Laje e Pilares, o usuário pode estar referindo-se a atributos que não tem objectName
                # Vamos injetar manualmente se acharmos as propriedades conhecidas
                if hasattr(robo, 'cmb_pav'): pav_combos.append(robo.cmb_pav)
                if hasattr(robo, 'combo_pavimento'): pav_combos.append(robo.combo_pavimento)
                if hasattr(robo, 'pavimento_combo'): pav_combos.append(robo.pavimento_combo)
                
                if hasattr(robo, 'pavimentos_list'): pav_lists.append(robo.pavimentos_list)
                if hasattr(robo, 'lista_pavimentos'): pav_lists.append(robo.lista_pavimentos)
                
                # Remover duplicatas
                pav_combos = list(set(pav_combos))
                pav_lists = list(set(pav_lists))
                
                # Atualizar combos
                for c in pav_combos:
                    curr = c.currentData() or c.currentText()
                    c.blockSignals(True)
                    # Ignorar se usar DataUserData muito complexo (evitar crash)
                    if c.count() > 0 and c.itemData(0) is not None and not isinstance(c.itemData(0), (str, int)):
                        continue
                    c.clear()
                    c.addItem("TODOS", "TODOS") # Padrão para os robôs
                    for p in pavs:
                        c.addItem(p, p)
                    
                    idx = c.findData(curr)
                    c.setCurrentIndex(idx if idx >= 0 else 0)
                    c.blockSignals(False)
                    
                # Atualizar listas
                for lst in pav_lists:
                    lst.blockSignals(True)
                    # Salva seleção atual
                    selected = [item.text() for item in lst.selectedItems()]
                    lst.clear()
                    lst.addItem("TODOS")
                    for p in pavs:
                        lst.addItem(p)
                    
                    # Restaura seleção
                    for i in range(lst.count()):
                        if lst.item(i).text() in selected:
                            lst.item(i).setSelected(True)
                    lst.blockSignals(False)
                    
        except Exception as e:
            self.log(f"Erro ao sincronizar pavimentos nos robôs: {e}")

    def _sync_robos_obras(self):
        \"\"\"Injeta dinamicamente as obras em combos não mapeados como o de Laje.\"\"\"
        try:
            works = self.db.get_all_works()
            # 1. Robo Laje - tem o obra_control.obra_combo mas ignora porque usa Data complexo!
            # Vamos corrigir o Laje manualmente: Laje usa 'nome' e 'pavimentos'
            if getattr(self, 'robo_laje', None) and hasattr(self.robo_laje, 'obra_control'):
                c = self.robo_laje.obra_control.obra_combo
                curr = c.currentData()
                curr_nome = curr.nome if curr and hasattr(curr, 'nome') else c.currentText()
                c.blockSignals(True)
                c.clear()
                
                from laje_src.models.obra import Obra as LajeObra
                for w in works:
                    obra_mock = LajeObra(nome=w)
                    c.addItem(f"📁 {w}", obra_mock)
                
                # Tenta restaurar seleção
                found = False
                for i in range(c.count()):
                    dt = c.itemData(i)
                    if dt and getattr(dt, 'nome', '') == curr_nome:
                        c.setCurrentIndex(i)
                        found = True
                        break
                if not found: c.setCurrentIndex(-1)
                c.blockSignals(False)
        except Exception as e:
            pass

"""

if "def _sync_robos_pavimentos" not in content:
    content = content.replace("    def _current_pavement_name", sync_pavs_func + "\n    def _current_pavement_name")

# 2. Call this function in _on_work_changed
old_work_changed_end = """        if hasattr(self, 'sa_cmb_obras'):
            sa_idx = self.sa_cmb_obras.findData(work_name)
            if sa_idx >= 0 and self.sa_cmb_obras.currentIndex() != sa_idx:
                self.sa_cmb_obras.blockSignals(True)
                self.sa_cmb_obras.setCurrentIndex(sa_idx)
                self.sa_cmb_obras.blockSignals(False)

        # Nao auto-selecionar pavimento: carregar projeto apenas apos escolha explicita."""

new_work_changed_end = """        if hasattr(self, 'sa_cmb_obras'):
            sa_idx = self.sa_cmb_obras.findData(work_name)
            if sa_idx >= 0 and self.sa_cmb_obras.currentIndex() != sa_idx:
                self.sa_cmb_obras.blockSignals(True)
                self.sa_cmb_obras.setCurrentIndex(sa_idx)
                self.sa_cmb_obras.blockSignals(False)

        # Sincroniza pavimentos e obras extras com os Robôs
        raw_pavs = [p.get('pavement_name') or p.get('name') for p in filtered]
        self._sync_robos_pavimentos(raw_pavs)

        # Nao auto-selecionar pavimento: carregar projeto apenas apos escolha explicita."""

content = content.replace(old_work_changed_end, new_work_changed_end)

# Call _sync_robos_obras inside _refresh_nav_combos
old_refresh = """            # Tentar sincronizar comboboxes marcados dos robôs (caso existam e sejam baseados em strings)"""
new_refresh = """            self._sync_robos_obras()
            # Tentar sincronizar comboboxes marcados dos robôs (caso existam e sejam baseados em strings)"""

content = content.replace(old_refresh, new_refresh)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("main.py updated for robots' pavements and Laje works!")
