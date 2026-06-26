import os
import re

path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Atualizar UI setup em __init__ ou _setup...
old_ui = '''        self.list_beams = QTreeWidget()
        self.list_beams.setHeaderLabels(["Item", "Nome", "Status", "%", "Seg. A", "Seg. B"])
        self.list_beams.setColumnWidth(0, 50)
        self.list_beams.setColumnWidth(1, 120)
        self.list_beams.setColumnWidth(2, 60)
        self.list_beams.setColumnWidth(3, 40)
        self.list_beams.setColumnWidth(4, 60)
        self.list_beams.setColumnWidth(5, 60)'''

new_ui = '''        self.list_beams = QTreeWidget()
        self.list_beams.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams.setColumnWidth(0, 50)
        self.list_beams.setColumnWidth(1, 150)
        self.list_beams.setColumnWidth(2, 60)
        self.list_beams.setColumnWidth(3, 40)

        self.list_beams_fundo = QTreeWidget()
        self.list_beams_fundo.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams_fundo.setColumnWidth(0, 50)
        self.list_beams_fundo.setColumnWidth(1, 150)
        self.list_beams_fundo.setColumnWidth(2, 60)
        self.list_beams_fundo.setColumnWidth(3, 40)'''

content = content.replace(old_ui, new_ui)

old_ui_valid = '''        self.list_beams_valid = QTreeWidget()
        self.list_beams_valid.setHeaderLabels(["Item", "Nome", "Status", "%", "Seg. A", "Seg. B"])
        self.list_beams_valid.setColumnWidth(0, 50)
        self.list_beams_valid.setColumnWidth(1, 120)
        self.list_beams_valid.setColumnWidth(2, 60)
        self.list_beams_valid.setColumnWidth(3, 40)
        self.list_beams_valid.setColumnWidth(4, 60)
        self.list_beams_valid.setColumnWidth(5, 60)'''

new_ui_valid = '''        self.list_beams_valid = QTreeWidget()
        self.list_beams_valid.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams_valid.setColumnWidth(0, 50)
        self.list_beams_valid.setColumnWidth(1, 150)
        self.list_beams_valid.setColumnWidth(2, 60)
        self.list_beams_valid.setColumnWidth(3, 40)

        self.list_beams_fundo_valid = QTreeWidget()
        self.list_beams_fundo_valid.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams_fundo_valid.setColumnWidth(0, 50)
        self.list_beams_fundo_valid.setColumnWidth(1, 150)
        self.list_beams_fundo_valid.setColumnWidth(2, 60)
        self.list_beams_fundo_valid.setColumnWidth(3, 40)'''

content = content.replace(old_ui_valid, new_ui_valid)

old_signals = '''        self.list_beams.itemClicked.connect(self.on_list_beam_clicked)
        self.list_beams.currentItemChanged.connect(lambda curr, prev: self.on_list_beam_clicked(curr, 0) if curr else None)'''

new_signals = '''        self.list_beams.itemClicked.connect(self.on_list_beam_clicked)
        self.list_beams.currentItemChanged.connect(lambda curr, prev: self.on_list_beam_clicked(curr, 0) if curr else None)
        
        self.list_beams_fundo.itemClicked.connect(self.on_list_beam_clicked)
        self.list_beams_fundo.currentItemChanged.connect(lambda curr, prev: self.on_list_beam_clicked(curr, 0) if curr else None)'''

content = content.replace(old_signals, new_signals)

old_signals_valid = '''        self.list_beams_valid.itemClicked.connect(self.on_list_beam_clicked)
        self.list_beams_valid.currentItemChanged.connect(lambda curr, prev: self.on_list_beam_clicked(curr, 0) if curr else None)'''

new_signals_valid = '''        self.list_beams_valid.itemClicked.connect(self.on_list_beam_clicked)
        self.list_beams_valid.currentItemChanged.connect(lambda curr, prev: self.on_list_beam_clicked(curr, 0) if curr else None)
        
        self.list_beams_fundo_valid.itemClicked.connect(self.on_list_beam_clicked)
        self.list_beams_fundo_valid.currentItemChanged.connect(lambda curr, prev: self.on_list_beam_clicked(curr, 0) if curr else None)'''

content = content.replace(old_signals_valid, new_signals_valid)

old_tabs = '''        self.tabs_analysis_internal.addTab(create_tab_container(self.list_pillars, 'pillar', False), "Pilares")
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_beams, 'beam', False), "Vigas")
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_slabs, 'slab', False), "Lajes")'''

new_tabs = '''        self.tabs_analysis_internal.addTab(create_tab_container(self.list_pillars, 'pillar', False), "Pilares")
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_beams, 'beam', False), "Lat. de Vigas")
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_beams_fundo, 'beam_fundo', False), "Fun. de Vigas")
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_slabs, 'slab', False), "Lajes")'''

content = content.replace(old_tabs, new_tabs)

old_tabs_valid = '''        self.tabs_library_internal.addTab(create_tab_container(self.list_pillars_valid, 'pillar', True), "Pilares OK")
        self.tabs_library_internal.addTab(create_tab_container(self.list_beams_valid, 'beam', True), "Vigas OK")
        self.tabs_library_internal.addTab(create_tab_container(self.list_slabs_valid, 'slab', True), "Lajes OK")'''

new_tabs_valid = '''        self.tabs_library_internal.addTab(create_tab_container(self.list_pillars_valid, 'pillar', True), "Pilares OK")
        self.tabs_library_internal.addTab(create_tab_container(self.list_beams_valid, 'beam', True), "Lat. Vigas OK")
        self.tabs_library_internal.addTab(create_tab_container(self.list_beams_fundo_valid, 'beam_fundo', True), "Fun. Vigas OK")
        self.tabs_library_internal.addTab(create_tab_container(self.list_slabs_valid, 'slab', True), "Lajes OK")'''

content = content.replace(old_tabs_valid, new_tabs_valid)

# 2. Atualizar todas as chamas para _populate_beam_tree
content = content.replace('self._populate_beam_tree(self.list_beams, self.beams_found)', 
                          'self._populate_beam_tree(self.list_beams, self.beams_found, "lateral")\n        self._populate_beam_tree(self.list_beams_fundo, self.beams_found, "fundo")')

content = content.replace('self._populate_beam_tree(self.list_beams_valid, valid_beams)', 
                          'self._populate_beam_tree(self.list_beams_valid, valid_beams, "lateral")\n        self._populate_beam_tree(self.list_beams_fundo_valid, valid_beams, "fundo")')

content = content.replace('self._populate_beam_tree(valid_list, valid_beams)', 
                          'self._populate_beam_tree(valid_list, valid_beams, "lateral")\n                        self._populate_beam_tree(self.list_beams_fundo_valid, valid_beams, "fundo")')


# Limpar arvore
content = content.replace('self.list_beams.clear()', 'self.list_beams.clear()\n        if hasattr(self, "list_beams_fundo"): self.list_beams_fundo.clear()')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch script 2 concluido!")
