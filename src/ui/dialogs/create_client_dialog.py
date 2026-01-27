from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QFrame
from PySide6.QtCore import Qt
from src.ui.components.molecules_control import ClientFormGroup

class CreateClientDialog(QDialog):
    """
    Diálogo modal para cadastro manual de cliente.
    """
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Novo Cliente")
        self.setFixedSize(450, 650) # Increased size
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: white; }
            QLabel { color: white; }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30) # Increased margins
        layout.setSpacing(20) # Increased spacing
        
        header = QLabel("Cadastro de Cliente")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #0078d4;")
        layout.addWidget(header)
        
        # Forms
        self.form_name = ClientFormGroup("Nome *", "Nome completo ou Razão Social")
        self.form_company = ClientFormGroup("Empresa", "Nome da Construtora/Escritório")
        self.form_email = ClientFormGroup("Email", "email@exemplo.com")
        self.form_phone = ClientFormGroup("Telefone", "(11) 99999-9999")
        self.form_address = ClientFormGroup("Endereço", "Rua, Cidade - UF")
        self.form_size = ClientFormGroup("Tamanho", input_type="combo", options=["Pequeno", "Médio", "Grande", "Enterprise"])
        self.form_desc = ClientFormGroup("Descrição / Notas", "Observações sobre o cliente...", input_type="textarea")
        
        layout.addWidget(self.form_name)
        layout.addWidget(self.form_company)
        layout.addWidget(self.form_email)
        layout.addWidget(self.form_phone)
        layout.addWidget(self.form_address)
        layout.addWidget(self.form_size)
        layout.addWidget(self.form_desc)
        
        layout.addStretch()
        
        # Actions
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet("background: transparent; border: 1px solid #555; color: #aaa;")
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton("Salvar Cliente")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("background: #0078d4; color: white; border: none; font-weight: bold; padding: 8px;")
        btn_save.clicked.connect(self.save_client)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
    def save_client(self):
        data = {
            "name": self.form_name.get_value(),
            "company": self.form_company.get_value(),
            "email": self.form_email.get_value(),
            "phone": self.form_phone.get_value(),
            "address": self.form_address.get_value(),
            "size": self.form_size.get_value(),
            "description": self.form_desc.get_value()
        }
        
        if not data["name"]:
            QMessageBox.warning(self, "Erro", "O campo Nome é obrigatório.")
            return
            
        try:
            self.db.add_client(data)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao salvar: {e}")
