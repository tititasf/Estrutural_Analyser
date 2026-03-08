from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QFrame, QPushButton, QLineEdit, QComboBox, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont

from src.ui.components.atoms import EmailSourceIcon, AttachmentChip, UserAvatar, PriorityTag, StatusBadge

class EmailListItem(QFrame):
    """
    Linha da tabela de emails.
    Layout: [Icone] | Remetente (Bold) | Assunto | Anexos | Data
    """
    clicked = Signal(object) # Retorna email_data

    def __init__(self, email_data):
        super().__init__()
        self.email_data = email_data
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("EmailItem")
        self.setStyleSheet("""
            #EmailItem {
                background-color: transparent;
                border-bottom: 1px solid #333;
            }
            #EmailItem:hover {
                background-color: #2d2d30;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(15)
        
        # 1. Source Icon
        # Assuming source detection logic here or passed in data
        source = "Gmail" if "gmail" in email_data.get('sender', '').lower() else "Email"
        layout.addWidget(EmailSourceIcon(source))
        
        # 2. Sender
        lbl_sender = QLabel(email_data.get('sender', 'Unknown'))
        lbl_sender.setStyleSheet("color: #fff; font-weight: bold; font-size: 11px;")
        lbl_sender.setFixedWidth(150)
        layout.addWidget(lbl_sender)
        
        # 3. Subject
        lbl_subj = QLabel(email_data.get('subject', '(Sem Assunto)'))
        lbl_subj.setStyleSheet("color: #ccc; font-size: 11px;")
        layout.addWidget(lbl_subj)
        
        # 4. Attachments Chips
        att_layout = QHBoxLayout()
        att_layout.setSpacing(5)
        attachments = email_data.get('attachments', [])
        # Show max 2 attachments chips
        for att in attachments[:2]:
            # Robust check for dirty/legacy data
            name = att.get('name', 'Anexo') if isinstance(att, dict) else str(att)
            att_layout.addWidget(AttachmentChip(name))
        
        if len(attachments) > 2:
            lbl_more = QLabel(f"+{len(attachments)-2}")
            lbl_more.setStyleSheet("color: #888; font-size: 10px;")
            att_layout.addWidget(lbl_more)
            
        layout.addLayout(att_layout)
        
        # spacer
        layout.addStretch()
        
        # 5. Date
        date_str = email_data.get('date', '')
        # Simplification: just show raw string or format
        lbl_date = QLabel(str(date_str)[:16]) 
        lbl_date.setStyleSheet("color: #666; font-size: 10px;")
        lbl_date.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(lbl_date)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit(self.email_data)

class DocumentRowItem(QFrame):
    """
    Linha da lista de documentos.
    Layout: [Icone Tipo] | Nome (Bold) | Data | Tamanho | [Ações]
    """
    convert_requested = Signal(dict) # doc_data (Converter em Obra)
    convert_to_pavement_requested = Signal(dict) # doc_data (Converter em Pavimento)
    download_requested = Signal(dict)

    def __init__(self, doc_data):
        super().__init__()
        self.doc_data = doc_data
        self.setObjectName("DocRow")
        self.setStyleSheet("""
            #DocRow {
                background-color: #1e1e1e;
                border-radius: 4px;
                margin-bottom: 2px;
            }
            #DocRow:hover {
                background-color: #252526;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # Icon placeholder based on extension
        ext = doc_data.get('name', '').split('.')[-1].upper()
        lbl_ext = QLabel(ext)
        lbl_ext.setFixedSize(32, 32)
        lbl_ext.setAlignment(Qt.AlignCenter)
        lbl_ext.setStyleSheet("background: #333; color: #aaa; border-radius: 4px; font-weight: bold; font-size: 10px;")
        layout.addWidget(lbl_ext)
        
        # Info
        info_v = QVBoxLayout()
        info_v.setSpacing(2)
        lbl_name = QLabel(doc_data.get('name'))
        lbl_name.setStyleSheet("color: #fff; font-weight: bold; font-size: 12px;")
        info_v.addWidget(lbl_name)
        
        details = f"{doc_data.get('size_str', '0 KB')} • {doc_data.get('date', 'Hoje')}"
        lbl_det = QLabel(details)
        lbl_det.setStyleSheet("color: #888; font-size: 10px;")
        info_v.addWidget(lbl_det)
        layout.addLayout(info_v)
        
        layout.addStretch()
        
        # Actions
        btn_down = QPushButton("📥")
        btn_down.setFixedSize(30, 30)
        btn_down.setToolTip("Baixar")
        btn_down.clicked.connect(lambda: self.download_requested.emit(doc_data))
        
        # 1. Converter em Obra (Vincular Documentos)
        btn_convert_work = QPushButton("📂 Converter em Obra")
        btn_convert_work.setCursor(Qt.PointingHandCursor)
        btn_convert_work.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 120, 212, 0.1);
                border: 1px solid #444;
                color: #aaa;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold; font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(0, 120, 212, 0.3);
                color: #fff;
            }
        """)
        btn_convert_work.clicked.connect(lambda: self.convert_requested.emit(doc_data))
        
        # 2. Converter em Pavimento (Criar Projeto)
        btn_convert_pavement = QPushButton("🏗️ Converter em Pavimento")
        btn_convert_pavement.setCursor(Qt.PointingHandCursor)
        btn_convert_pavement.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 167, 69, 0.2);
                border: 1px solid #28a745;
                color: #28a745;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold; font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(40, 167, 69, 0.4);
            }
        """)
        btn_convert_pavement.clicked.connect(lambda: self.convert_to_pavement_requested.emit(doc_data))
        
        layout.addWidget(btn_down)
        layout.addWidget(btn_convert_work)
        layout.addWidget(btn_convert_pavement)

class UserStatusRow(QFrame):
    """
    Linha da lista de equipe.
    [Avatar] | [Nome + Role] | [Status Badge] 
    """
    def __init__(self, user_data): # user_data: UserProfile dict or obj
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Data mapping
        name = user_data.get('full_name') or user_data.get('email')
        status = "Online" # Placeholder logic, real logic handles 'status' field
        role = user_data.get('role', 'User')
        
        layout.addWidget(UserAvatar(name, status, size=28))
        
        info_v = QVBoxLayout()
        info_v.setSpacing(0)
        lbl_name = QLabel(name)
        lbl_name.setStyleSheet("color: #ddd; font-weight: bold; font-size: 11px;")
        info_v.addWidget(lbl_name)
        lbl_role = QLabel(role)
        lbl_role.setStyleSheet("color: #666; font-size: 9px;")
        info_v.addWidget(lbl_role)
        layout.addLayout(info_v)
        
        layout.addStretch()
        
        # Status dot
        dot = QLabel("●")
        color = "#4caf50" if status == "Online" else "#666"
        dot.setStyleSheet(f"color: {color}; font-size: 8px;")
        layout.addWidget(dot)

class ClientFormGroup(QWidget):
    """
    Label + Input Field para formulários.
    """
    def __init__(self, label, placeholder="", input_type="text", options=[]):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #ccc; font-size: 11px; font-weight: bold;")
        layout.addWidget(lbl)
        
        if input_type == "text":
            self.input = QLineEdit()
            self.input.setPlaceholderText(placeholder)
            self.input.setStyleSheet("background: #252526; border: 1px solid #3e3e42; color: #fff; padding: 6px; border-radius: 4px;")
            layout.addWidget(self.input)
        elif input_type == "combo":
            self.input = QComboBox()
            self.input.addItems(options)
            self.input.setStyleSheet("background: #252526; border: 1px solid #3e3e42; color: #fff; padding: 4px; border-radius: 4px;")
            layout.addWidget(self.input)
        elif input_type == "textarea":
            self.input = QTextEdit()
            self.input.setPlaceholderText(placeholder)
            self.input.setFixedHeight(60)
            self.input.setStyleSheet("background: #252526; border: 1px solid #3e3e42; color: #fff; padding: 6px; border-radius: 4px;")
            layout.addWidget(self.input)
            
    def get_value(self):
        if isinstance(self.input, QComboBox):
            return self.input.currentText()
        elif isinstance(self.input, QTextEdit):
            return self.input.toPlainText()
        return self.input.text()
