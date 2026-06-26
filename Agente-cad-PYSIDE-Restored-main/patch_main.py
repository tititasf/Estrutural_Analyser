import os
import re

path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Modificar on_list_beam_clicked
old_click = '''    def on_list_beam_clicked(self, item, column=0):
        beam_id = item.data(0, Qt.UserRole)
        if not beam_id: return # Clicou no nó pai
        beam = next((b for b in self.beams_found if b['id'] == beam_id), None)
        if beam:
            self.show_detail(beam)'''
            
new_click = '''    def on_list_beam_clicked(self, item, column=0):
        beam_id = item.data(0, Qt.UserRole)
        override_type = item.data(0, Qt.UserRole + 1)
        if not beam_id: return # Clicou no nó pai
        beam = next((b for b in self.beams_found if b['id'] == beam_id), None)
        if beam:
            self.show_detail(beam, override_type=override_type)'''

content = content.replace(old_click.replace('ó', ''), new_click)
content = content.replace(old_click, new_click)

# 2. Modificar _populate_beam_tree signature e conteudo
# Vamos encontrar a def _populate_beam_tree e substituir até o final da funcao
def replace_populate(c):
    start_idx = c.find('    def _populate_beam_tree(self, tree_widget, beam_list):')
    if start_idx == -1: return c
    
    # Encontrar a proxima '    def '
    end_idx = c.find('    def ', start_idx + 10)
    if end_idx == -1: end_idx = len(c)
    
    new_func = '''    def _populate_beam_tree(self, tree_widget, beam_list, list_type='lateral'):
        # Limpar cache de itens deste widget específico
        for iid, widgets in self.tree_item_map.items():
            safe = []
            for w in widgets:
                try:
                    if w.treeWidget() != tree_widget:
                        safe.append(w)
                except RuntimeError:
                    pass  # objeto C++ já deletado
            self.tree_item_map[iid] = safe

        tree_widget.clear()
        if not beam_list: return
        
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtGui import QColor

        # Agrupar por parent_name
        from collections import OrderedDict
        groups = OrderedDict()
        for b in beam_list:
            p_name = b.get('parent_name', b.get('name', 'V?'))
            if p_name not in groups:
                 groups[p_name] = []
            groups[p_name].append(b)
            
        for p_name, segments in groups.items():
            parent_item = QTreeWidgetItem(tree_widget)
            prefix = "F." if list_type == 'fundo' else "L."
            parent_item.setText(1, f"📁 {prefix}{p_name}")
            parent_item.setExpanded(True)
            parent_item.setFlags(parent_item.flags() & ~Qt.ItemIsSelectable)
            
            for b in segments:
                # Status
                status = "⏱"
                if b.get('is_fully_validated'): status = "✔️"
                elif b.get('is_validated'): status = "✔️"
                elif b.get('issues'): status = "⚠️"
                
                # % Completitude
                pct = self._calculate_completion(b)
                pct_str = f"{int(pct)}%"
                
                if list_type == 'lateral':
                    # Lado A
                    child_a = QTreeWidgetItem(parent_item)
                    child_a.setText(0, str(b.get('id_item', '00')))
                    child_a.setText(1, f"{prefix}{p_name}.A")
                    child_a.setText(2, str(status))
                    child_a.setText(3, pct_str)
                    child_a.setData(0, Qt.UserRole, str(b.get('id')))
                    child_a.setData(0, Qt.UserRole + 1, 'viga_lateral_a')
                    # Lado B
                    child_b = QTreeWidgetItem(parent_item)
                    child_b.setText(0, str(b.get('id_item', '00')))
                    child_b.setText(1, f"{prefix}{p_name}.B")
                    child_b.setText(2, str(status))
                    child_b.setText(3, pct_str)
                    child_b.setData(0, Qt.UserRole, str(b.get('id')))
                    child_b.setData(0, Qt.UserRole + 1, 'viga_lateral_b')
                else:
                    # Fundo
                    child_f = QTreeWidgetItem(parent_item)
                    child_f.setText(0, str(b.get('id_item', '00')))
                    child_f.setText(1, f"{prefix}{p_name}.C-1")
                    child_f.setText(2, str(status))
                    child_f.setText(3, pct_str)
                    child_f.setData(0, Qt.UserRole, str(b.get('id')))
                    child_f.setData(0, Qt.UserRole + 1, 'viga_fundo_c')

'''
    return c[:start_idx] + new_func + c[end_idx:]

content = replace_populate(content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch script concluido!")
