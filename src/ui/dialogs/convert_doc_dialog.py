import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QMessageBox, QDateEdit, QTextEdit, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, QDate
from src.ui.components.molecules_control import ClientFormGroup

class ConvertDocDialog(QDialog):
    """
    Dialogo para converter um documento em uma nova Obra/Projeto.
    """
    def __init__(self, doc_data, db, parent=None):
        super().__init__(parent)
        self.doc_data = doc_data
        self.db = db
        self.setWindowTitle("Converter Documento em Obra")
        self.setFixedSize(450, 600)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: white; }
            QLabel { color: white; }
            QDateEdit { background: #252526; color: white; border: 1px solid #3e3e42; }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header Info
        header = QLabel("Vincular Documento à Obra")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #00d4ff;")
        layout.addWidget(header)
        
        doc_info = QLabel(f"Documento: <b>{self.doc_data.get('name')}</b>")
        doc_info.setStyleSheet("color: #aaa; font-style: italic;")
        layout.addWidget(doc_info)
        
        layout.addSpacing(10)
        
        # Fields
        self.field_work_name = ClientFormGroup("Nome da Obra (Nova ou Existente) *", "Ex: Edifício Horizonte")
        self.field_proj_name = ClientFormGroup("Nome do Projeto (Opcional)", "Deixe vazio para apenas vincular o documento")
        
        layout.addWidget(self.field_work_name)
        layout.addWidget(self.field_proj_name)
        
        # Dates
        date_layout = QHBoxLayout()
        
        lbl_d1 = QLabel("Data Solicitação:"); lbl_d1.setStyleSheet("color:#ccc; font-weight:bold; font-size:11px;")
        self.date_req = QDateEdit(QDate.currentDate())
        self.date_req.setCalendarPopup(True)
        
        lbl_d2 = QLabel("Data Entrega:"); lbl_d2.setStyleSheet("color:#ccc; font-weight:bold; font-size:11px;")
        self.date_del = QDateEdit(QDate.currentDate().addDays(7))
        self.date_del.setCalendarPopup(True)
        
        d1_wrap = QVBoxLayout(); d1_wrap.setSpacing(2); d1_wrap.addWidget(lbl_d1); d1_wrap.addWidget(self.date_req)
        d2_wrap = QVBoxLayout(); d2_wrap.setSpacing(2); d2_wrap.addWidget(lbl_d2); d2_wrap.addWidget(self.date_del)
        
        date_layout.addLayout(d1_wrap)
        date_layout.addLayout(d2_wrap)
        layout.addLayout(date_layout)
        
        # Extra Info
        self.field_obs = ClientFormGroup("Observações / Contexto", "Detalhes importantes...", input_type="textarea")
        
        layout.addWidget(self.field_obs)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet("background: transparent; border: 1px solid #555; color: #aaa;")
        btn_cancel.clicked.connect(self.reject)
        
        btn_confirm = QPushButton("Confirmar Vínculo")
        btn_confirm.setCursor(Qt.PointingHandCursor)
        btn_confirm.setStyleSheet("background: #0078d4; color: white; border: none; font-weight: bold; padding: 10px; border-radius: 4px;")
        btn_confirm.clicked.connect(self.confirm_conversion)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_confirm)
        layout.addLayout(btn_layout)

    def confirm_conversion(self):
        w_name = self.field_work_name.get_value()
        p_name = self.field_proj_name.get_value()
        
        if not w_name:
            QMessageBox.warning(self, "Atenção", "O nome da Obra é obrigatório.")
            return
            
        try:
            # 1. Create/Get Work
            client_id = self.doc_data.get('client_id')
            self.db.create_work(w_name, client_id)
            
            # 2. Get File Content (decoded base64 if virtual)
            content_b64 = ""
            if self.doc_data.get('comm_id'):
                content_b64 = self.db.get_attachment_data(self.doc_data['comm_id'], self.doc_data['name'])
            
            # 3. Decision: Create Project OR just Link Document to Work
            if p_name and p_name.strip():
                # Full Conversion: Obra + Pavimento
                dxf_path = self.doc_data.get('path', '') 
                pid = self.db.create_project(p_name, dxf_path)
                
                meta = {
                    'work_name': w_name,
                    'pavement_name': p_name,
                    'client_id': client_id,
                    'description': self.field_obs.get_value()
                }
                self.db.update_project_metadata(pid, meta)
                
                # Also save as project doc if content exists
                if content_b64:
                    # Categorizar baseado na extensão
                    ext = ".dxf" if "dxf" in self.doc_data['name'].lower() else ".dwg"
                    cat = "Estruturais dos Pavimentos, Estado Bruto (.DXF)" if ext == ".dxf" else "Estruturais dos Pavimentos, Estado Bruto (.DWG)"
                    
                    self.db.save_document(
                        project_id=pid, 
                        name=self.doc_data['name'], 
                        file_path="", 
                        extension=ext, 
                        phase=1,
                        category=cat,
                        file_data=content_b64
                    )
                
                msg = f"Obra '{w_name}' e Pavimento '{p_name}' criados!"
            else:
                # Direct Link: Just Obra + Documento
                self.db.save_work_document(
                    work_name=w_name,
                    name=self.doc_data['name'],
                    file_data=content_b64,
                    client_id=client_id
                )
                msg = f"Documento vinculado à Obra '{w_name}' com sucesso!"

            QMessageBox.information(self, "Sucesso", msg)
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao criar obra: {e}")


class ConvertToPavementDialog(QDialog):
    """
    Dialogo específico para converter um documento em um Pavimento (Projeto)
    vinculado a uma Obra existente ou nova.
    """
    def __init__(self, doc_data, db, parent=None):
        super().__init__(parent)
        self.doc_data = doc_data
        self.db = db
        self.setWindowTitle("Converter em Pavimento")
        self.setFixedSize(450, 400)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1b; color: white; }
            QLabel { color: #aaa; }
            QComboBox { background: #252528; color: white; border: 1px solid #333; padding: 6px; border-radius: 4px; }
            QLineEdit { background: #252528; color: white; border: 1px solid #333; padding: 6px; border-radius: 4px; }
        """)
        
        self.setup_ui()
        self.load_works()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)
        
        header = QLabel("Criar Pavimento a partir de Doc")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #28a745; margin-bottom: 5px;")
        layout.addWidget(header)
        
        # Nome do Pavimento
        v1 = QVBoxLayout(); v1.setSpacing(5)
        v1.addWidget(QLabel("Nome do Pavimento *"))
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Ex: Pavimento Tipo 01")
        # Pre-fill with filename without extension
        base_name = os.path.splitext(self.doc_data.get('name', ''))[0]
        self.edit_name.setText(base_name)
        v1.addWidget(self.edit_name)
        layout.addLayout(v1)
        
        # Seleção de Obra
        v2 = QVBoxLayout(); v2.setSpacing(5)
        v2.addWidget(QLabel("Vincular à Obra *"))
        
        h_work = QHBoxLayout(); h_work.setSpacing(10)
        self.combo_works = QComboBox()
        h_work.addWidget(self.combo_works, 1)
        
        btn_new_work = QPushButton("+")
        btn_new_work.setFixedSize(32, 32)
        btn_new_work.setToolTip("Criar Nova Obra")
        btn_new_work.setStyleSheet("background: #333; border: 1px solid #444; color: #00d4ff; font-weight: bold;")
        btn_new_work.clicked.connect(self.create_new_work)
        h_work.addWidget(btn_new_work)
        
        v2.addLayout(h_work)
        layout.addLayout(v2)
        
        layout.addStretch()
        
        # Ações
        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setStyleSheet("background: transparent; color: #888; border: none; padding: 8px;")
        
        self.btn_confirm = QPushButton("Criar Pavimento")
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setStyleSheet("background: #28a745; color: white; border: none; font-weight: bold; padding: 10px; border-radius: 4px;")
        self.btn_confirm.clicked.connect(self.handle_confirm)
        
        btns.addWidget(btn_cancel)
        btns.addWidget(self.btn_confirm)
        layout.addLayout(btns)

    def load_works(self):
        self.combo_works.clear()
        try:
            works = self.db.get_all_works()
            self.combo_works.addItems(works)
        except: pass

    def create_new_work(self):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "Nova Obra", "Nome da Obra:")
        if ok and text:
            self.db.create_work(text, self.doc_data.get('client_id'))
            self.load_works()
            self.combo_works.setCurrentText(text)

    def handle_confirm(self):
        p_name = self.edit_name.text()
        w_name = self.combo_works.currentText()
        
        if not p_name or not w_name:
            QMessageBox.warning(self, "Atenção", "Preencha todos os campos obrigatórios.")
            return
            
        try:
            # Create Project
            dxf_path = self.doc_data.get('path', '')
            pid = self.db.create_project(p_name, dxf_path)
            
            # Associate with Work
            client_id = self.doc_data.get('client_id')
            meta = {
                'work_name': w_name,
                'pavement_name': p_name,
                'client_id': client_id
            }
            self.db.update_project_metadata(pid, meta)
            
            # Save Base64 or Link File
            content_b64 = ""
            if self.doc_data.get('comm_id'):
                content_b64 = self.db.get_attachment_data(self.doc_data['comm_id'], self.doc_data['name'])
            
            if content_b64:
                # Categorizar baseado na extensão
                ext = ".dxf" if "dxf" in self.doc_data['name'].lower() else ".dwg"
                cat = "Estruturais dos Pavimentos, Estado Bruto (.DXF)" if ext == ".dxf" else "Estruturais dos Pavimentos, Estado Bruto (.DWG)"
                
                self.db.save_document(
                    project_id=pid, 
                    name=self.doc_data['name'], 
                    file_path="", 
                    extension=ext, 
                    phase=1,
                    category=cat,
                    file_data=content_b64
                )
            
            QMessageBox.information(self, "Sucesso", f"Pavimento '{p_name}' criado e vinculado à obra '{w_name}'.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao converter: {e}")

