from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                               QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox, 
                               QListWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView,
                               QComboBox, QInputDialog, QMenu, QToolButton)
from PySide6.QtCore import Signal, Qt
import json
import os
from datetime import datetime

class ProjectManager(QWidget):
    project_selected = Signal(str, str, str)  # id, name, dxf_path

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.setup_ui()
        self.load_works_combo()
        self.load_projects()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Gerenciador de Projetos DXF")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(header)

        # --- Work Management Area ---
        work_layout = QHBoxLayout()
        work_layout.addWidget(QLabel("Filtrar por Obra:"))
        
        self.combo_works = QComboBox()
        self.combo_works.addItem("Todas as Obras", None)
        self.combo_works.currentIndexChanged.connect(self.load_projects)
        work_layout.addWidget(self.combo_works)
        
        # Tools Work
        btn_add_work = QPushButton("➕ Obra")
        btn_add_work.setToolTip("Criar nova Obra")
        btn_add_work.clicked.connect(self.add_work)
        
        btn_edit_work = QPushButton("✏️")
        btn_edit_work.setToolTip("Renomear Obra Selecionada")
        btn_edit_work.clicked.connect(self.rename_current_work)

        btn_del_work = QPushButton("🗑️")
        btn_del_work.setToolTip("Excluir Obra (Remove projetos da obra)")
        btn_del_work.clicked.connect(self.delete_current_work)

        work_layout.addWidget(btn_add_work)
        work_layout.addWidget(btn_edit_work)
        work_layout.addWidget(btn_del_work)
        work_layout.addStretch()
        
        layout.addLayout(work_layout)

        # --- Project Table ---
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Nome do Projeto", "Obra", "Arquivo DXF", "Ações"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 160)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.cellDoubleClicked.connect(self.on_table_double_click)
        layout.addWidget(self.table)

        # --- Main Actions ---
        btn_layout = QHBoxLayout()
        
        self.btn_new = QPushButton("Novo Projeto")
        self.btn_new.clicked.connect(self.create_new_project)
        self.btn_new.setStyleSheet("font-weight: bold; background-color: #007acc; color: white; padding: 6px;")
        btn_layout.addWidget(self.btn_new)
        
        self.btn_import = QPushButton("Importar Backup")
        self.btn_import.clicked.connect(self.import_project)
        btn_layout.addWidget(self.btn_import)
        
        self.btn_export = QPushButton("Exportar Selecionado")
        self.btn_export.clicked.connect(self.export_project)
        btn_layout.addWidget(self.btn_export)
        
        # Open Button
        self.btn_open = QPushButton("Abrir Selecionado")
        self.btn_open.clicked.connect(self.open_selected_project)
        btn_layout.addWidget(self.btn_open)

        layout.addLayout(btn_layout)

    def load_works_combo(self):
        curr_text = self.combo_works.currentText()
        self.combo_works.blockSignals(True)
        self.combo_works.clear()
        self.combo_works.addItem("Todas as Obras", None)
        
        works = self.db.get_all_works()
        for w in works:
            self.combo_works.addItem(w, w)
            
        # Restore selection
        idx = self.combo_works.findText(curr_text)
        if idx >= 0:
            self.combo_works.setCurrentIndex(idx)
        else:
            self.combo_works.setCurrentIndex(0)
            
        self.combo_works.blockSignals(False)

    def load_projects(self):
        self.table.setRowCount(0)
        projects = self.db.get_projects()
        
        filter_work = self.combo_works.currentData() # None = All
        
        row = 0
        for p in projects:
            p_work = p.get('work_name') or "Sem Obra"
            
            # Filter
            if filter_work and p.get('work_name') != filter_work:
                continue

            self.table.insertRow(row)
            
            # Name
            self.table.setItem(row, 0, QTableWidgetItem(p['name']))
            # Work
            self.table.setItem(row, 1, QTableWidgetItem(p_work))
            # DXF
            dxf_name = os.path.basename(p['dxf_path']) if p['dxf_path'] else "-"
            self.table.setItem(row, 2, QTableWidgetItem(dxf_name))
            
            # Actions Widget
            actions_widget = QWidget()
            h_layout = QHBoxLayout(actions_widget)
            h_layout.setContentsMargins(2, 2, 2, 2)
            h_layout.setSpacing(4)
            
            # Rename
            btn_ren = self._make_tool_btn("✏️", "Renomear", lambda checked=False, pid=p['id'], name=p['name']: self.rename_project_action(pid, name))
            h_layout.addWidget(btn_ren)

            # Move/Group
            btn_grp = self._make_tool_btn("📂", "Mover/Copiar para Obra", lambda checked=False, pid=p['id']: self.move_copy_project_action(pid))
            h_layout.addWidget(btn_grp)

            # Delete
            btn_del = self._make_tool_btn("🗑️", "Excluir", lambda checked=False, pid=p['id'], name=p['name']: self.delete_project_action(pid, name))
            h_layout.addWidget(btn_del)
            
            h_layout.addStretch()
            self.table.setCellWidget(row, 3, actions_widget)
            
            # Store ID in hidden role of first item
            self.table.item(row, 0).setData(Qt.UserRole, p)
            
            row += 1

    def _make_tool_btn(self, icon_text, tooltip, callback):
        btn = QToolButton()
        btn.setText(icon_text)
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        btn.setFixedSize(24, 24)
        return btn

    # --- Actions ---

    def add_work(self):
        text, ok = QInputDialog.getText(self, "Nova Obra", "Nome da Obra:")
        if ok and text:
            self.db.create_work(text)
            self.load_works_combo()
            
            # Select the new work
            idx = self.combo_works.findText(text)
            if idx >= 0:
                self.combo_works.setCurrentIndex(idx)

    def rename_current_work(self):
        current_work = self.combo_works.currentData()
        if not current_work:
            QMessageBox.warning(self, "Aviso", "Selecione uma Obra específica para renomear.")
            return
            
        new_name, ok = QInputDialog.getText(self, "Renomear Obra", f"Novo nome para '{current_work}':", text=current_work)
        if ok and new_name and new_name != current_work:
            self.db.rename_work(current_work, new_name)
            self.load_works_combo()
            self.load_projects()
            
            # Restore selection
            idx = self.combo_works.findText(new_name)
            if idx >= 0: self.combo_works.setCurrentIndex(idx)

    def delete_current_work(self):
        current_work = self.combo_works.currentData()
        if not current_work:
            return
            
        reply = QMessageBox.question(self, "Excluir Obra", 
                                     f"Isso removerá a Obra '{current_work}' e seus projetos ficarão 'Sem Obra'.\nContinuar?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.db.delete_work(current_work)
            self.load_works_combo()
            self.load_projects()

    def rename_project_action(self, pid, old_name):
        new_name, ok = QInputDialog.getText(self, "Renomear Projeto", "Novo Nome:", text=old_name)
        if ok and new_name:
            self.db.rename_project(pid, new_name)
            self.load_projects()

    def delete_project_action(self, pid, name):
        reply = QMessageBox.question(self, "Confirmar Exclusão", 
                                     f"Tem certeza que deseja excluir o projeto '{name}'?\nIsso apagará TODOS os dados (Pilares, Lajes, etc).",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.db.delete_project_fully(pid)
            self.load_projects()

    def move_copy_project_action(self, pid):
        # Dialog to choose Target Work and Action (Move vs Copy)
        works = self.db.get_all_works()
        if not works:
            QMessageBox.warning(self, "Aviso", "Não há obras cadastradas para destino.")
            return

        item, ok = QInputDialog.getItem(self, "Selecionar Obra de Destino", "Obra:", works, 0, False)
        if ok and item:
            # Ask Move or Copy
            msg = QMessageBox()
            msg.setWindowTitle("Ação")
            msg.setText(f"O que deseja fazer com o projeto para '{item}'?")
            btn_move = msg.addButton("Mover", QMessageBox.ActionRole) # Role 0
            btn_copy = msg.addButton("Copiar", QMessageBox.ActionRole) # Role 1
            msg.addButton("Cancelar", QMessageBox.RejectRole)
            
            msg.exec_()
            
            if msg.clickedButton() == btn_move:
                self.db.update_project_work(pid, item)
                self.load_projects()
            elif msg.clickedButton() == btn_copy:
                new_pid = self.db.duplicate_project(pid, target_work_name=item)
                if new_pid:
                    QMessageBox.information(self, "Sucesso", "Projeto copiado com sucesso!")
                    self.load_projects()
                else:
                    QMessageBox.critical(self, "Erro", "Falha ao copiar projeto.")


    def create_new_project(self):
        # 1. Select DXF
        fname, _ = QFileDialog.getOpenFileName(self, "Selecionar DXF", "", "DXF Files (*.dxf)")
        if not fname:
            return

        # --- INTERNAL REPO LOGIC ---
        # Garantir que o projeto seja copiado para o repositório interno
        import shutil
        repo_dir = os.path.join(os.getcwd(), 'projects_repo')
        if not os.path.exists(repo_dir):
            try:
                os.makedirs(repo_dir)
            except OSError as e:
                QMessageBox.critical(self, "Erro", f"Falha ao criar diretório de projetos: {e}")
                return

        base_name = os.path.basename(fname)
        target_path = os.path.join(repo_dir, base_name)
        
        # Se arquivo já existe, gerar nome único para evitar conflitos silenciosos
        if os.path.exists(target_path):
            name, ext = os.path.splitext(base_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_path = os.path.join(repo_dir, f"{name}_{timestamp}{ext}")

        try:
            shutil.copy2(fname, target_path)
            fname = target_path # Atualiza fname para usar o caminho interno
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao copiar DXF para o sistema: {e}")
            return
        # ---------------------------

        # 2. Name Project
        project_name = os.path.splitext(os.path.basename(fname))[0]
        
        # 3. Create ID
        pid = self.db.create_project(project_name, fname)
        if pid:
            # Assign current Obra if selected
            curr_work = self.combo_works.currentData()
            if curr_work:
                self.db.update_project_work(pid, curr_work)
                
            self.load_projects()
            self.project_selected.emit(pid, project_name, fname)
        else:
            QMessageBox.critical(self, "Erro", "Falha ao criar projeto no banco de dados.")

    def open_selected_project(self):
        row = self.table.currentRow()
        if row < 0: return
        
        p = self.table.item(row, 0).data(Qt.UserRole)
        self.project_selected.emit(p['id'], p['name'], p['dxf_path'])

    def on_table_double_click(self, row, col):
        if col == 3: return # Actions column
        self.open_selected_project()

    def export_project(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um projeto para exportar.")
            return

        p = self.table.item(row, 0).data(Qt.UserRole)
        data = self.db.export_project_data(p['id'])
        
        if not data:
            QMessageBox.critical(self, "Erro", "Não foi possível recuperar os dados do projeto.")
            return

        # Suggested filename
        safe_name = p['name'].replace(" ", "_").replace("/", "-")
        fname, _ = QFileDialog.getSaveFileName(self, "Salvar Backup de Projeto", f"{safe_name}_backup.cadproj", "Project Files (*.cadproj *.json)")
        if fname:
            try:
                with open(fname, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                QMessageBox.information(self, "Sucesso", "Projeto exportado com sucesso!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao salvar arquivo: {e}")

    def import_project(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Importar Backup", "", "Project Files (*.cadproj *.json)")
        if not fname: return

        try:
            with open(fname, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # --- FEATURE REQUEST: Use document name as saved at time of export ---
            # DB export saves data['project']['name']. DatabaseManager.import_project_data uses it.
            # So this is already handled if the export file contains the correct name.
            # But the user said: "importing... save with the name of the document saved AT THE TIME OF EXPORT"
            # Yes, data['project']['name'] IS the name at time of export. 
            # So I just pass data to DB.
            # However, I should check if the user wants to *override* the imported work name with current UI selection?
            # User didn't specify that. He said project name.
            
            # Additional: Ensure it appears in current "Obra" if one is selected and strict?
            # Or just import as is? I'll import as is.
            
            # Optional: If current Obra filter is active, maybe ask to auto-assign?
            # I'll stick to raw import.
            
            p_id = self.db.import_project_data(data)
            
            if p_id:
                self.load_works_combo() # In case a new work was imported
                self.load_projects()
                QMessageBox.information(self, "Sucesso", f"Projeto '{data['project']['name']}' importado com sucesso!")
            else:
                QMessageBox.critical(self, "Erro", "Falha estrutural ao importar projeto.")
                
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao ler arquivo de projeto: {e}")
