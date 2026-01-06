from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                               QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox, QListWidgetItem)
from PySide6.QtCore import Signal, Qt
import json
import os

class ProjectManager(QWidget):
    project_selected = Signal(str, str, str)  # id, name, dxf_path

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.setup_ui()
        self.load_projects()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Gerenciador de Projetos DXF")
        header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)

        # List of Projects
        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(self.open_project)
        layout.addWidget(QLabel("Projetos Recentes:"))
        layout.addWidget(self.project_list)

        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        
        self.btn_new = QPushButton("Novo Projeto")
        self.btn_new.clicked.connect(self.create_new_project)
        btn_layout.addWidget(self.btn_new)
        
        self.btn_import = QPushButton("Importar Backup")
        self.btn_import.clicked.connect(self.import_project)
        self.btn_import.setStyleSheet("background-color: #2a2a2a; color: #00d4ff; border: 1px dashed #00d4ff;")
        btn_layout.addWidget(self.btn_import)
        
        self.btn_export = QPushButton("Exportar Selecionado")
        self.btn_export.clicked.connect(self.export_project)
        self.btn_export.setStyleSheet("background-color: #2a2a2a; color: #ffb300; border: 1px solid #ffb300;")
        btn_layout.addWidget(self.btn_export)

        layout.addLayout(btn_layout)
        
        # Open Button
        self.btn_open = QPushButton("Abrir Projeto Selecionado")
        self.btn_open.setFixedHeight(40)
        self.btn_open.setStyleSheet("font-weight: bold; background-color: #007acc; color: white;")
        self.btn_open.clicked.connect(self.open_project)
        layout.addWidget(self.btn_open)

    def load_projects(self):
        self.project_list.clear()
        projects = self.db.get_projects()
        for p in projects:
            display_text = f"{p['name']} ({os.path.basename(p['dxf_path'])})"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, p)
            self.project_list.addItem(item)

    def create_new_project(self):
        # 1. Select DXF
        fname, _ = QFileDialog.getOpenFileName(self, "Selecionar DXF", "", "DXF Files (*.dxf)")
        if not fname:
            return

        # 2. Name Project
        project_name = os.path.splitext(os.path.basename(fname))[0]
        
        # 3. Create in ID
        pid = self.db.create_project(project_name, fname)
        if pid:
            self.load_projects()
            # Auto-select the new project
            self.project_selected.emit(pid, project_name, fname)
        else:
            QMessageBox.critical(self, "Erro", "Falha ao criar projeto no banco de dados.")

    def open_project(self):
        item = self.project_list.currentItem()
        if not item:
            return
        
        p = item.data(Qt.UserRole)
        self.project_selected.emit(p['id'], p['name'], p['dxf_path'])

    def export_project(self):
        item = self.project_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Aviso", "Selecione um projeto para exportar.")
            return

        p = item.data(Qt.UserRole)
        data = self.db.export_project_data(p['id'])
        
        if not data:
            QMessageBox.critical(self, "Erro", "Não foi possível recuperar os dados do projeto.")
            return

        fname, _ = QFileDialog.getSaveFileName(self, "Salvar Backup de Projeto", f"{p['name']}_backup.cadproj", "Project Files (*.cadproj *.json)")
        if fname:
            try:
                with open(fname, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                QMessageBox.information(self, "Sucesso", "Projeto exportado com sucesso!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao salvar arquivo: {e}")

    def import_project(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Importar Backup", "", "Project Files (*.cadproj *.json)")
        if not fname:
            return

        try:
            with open(fname, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            p_id = self.db.import_project_data(data)
            
            if p_id:
                self.load_projects()
                QMessageBox.information(self, "Sucesso", "Projeto importado com sucesso!")
            else:
                QMessageBox.critical(self, "Erro", "Falha estrutural ao importar projeto (ID inválido ou erro de DB).")
                
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao ler arquivo de projeto: {e}")
