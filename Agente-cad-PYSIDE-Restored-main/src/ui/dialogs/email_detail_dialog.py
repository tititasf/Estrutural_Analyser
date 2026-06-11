from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QTextEdit, QPushButton, QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt
from src.ui.components.atoms import AttachmentChip
from src.ui.theme import Colors, Fonts, Radius

class EmailDetailDialog(QDialog):
    """
    Dialogo para visualizar detalhes do email (Corpo, Anexos, Metadados).
    """
    def __init__(self, email_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Visualização de Email")
        self.setMinimumSize(600, 700)
        self.setStyleSheet("""
            QDialog { background-color: {Colors.BG_PANEL}; color: {Colors.TEXT_BRIGHT}; }
            QLabel { color: {Colors.TEXT_BRIGHT}; }
            QTextEdit { background-color: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_INPUT}; color: {Colors.TEXT_BRIGHT}; padding: 10px; }
            QScrollArea { border: none; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 1. Header (Subject, Sender, Date)
        header_frame = QFrame()
        header_frame.setStyleSheet(f"background-color: {Colors.BORDER_PANEL}; border-radius: 6px;")
        h_layout = QVBoxLayout(header_frame)
        
        # Subject
        lbl_subj = QLabel(email_data.get('subject', '(Sem Assunto)'))
        lbl_subj.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Colors.TEXT_BRIGHT};")
        lbl_subj.setWordWrap(True)
        h_layout.addWidget(lbl_subj)
        
        # Meta line
        meta_layout = QHBoxLayout()
        sender = email_data.get('sender', 'Unknown')
        date = email_data.get('date', 'Unknown')
        
        lbl_sender = QLabel(f"De: <span style='color: {Colors.ACCENT_TEAL};'>{sender}</span>")
        lbl_sender.setTextFormat(Qt.RichText)
        meta_layout.addWidget(lbl_sender)
        
        meta_layout.addStretch()
        
        lbl_date = QLabel(f"{date}")
        lbl_date.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        meta_layout.addWidget(lbl_date)
        
        h_layout.addLayout(meta_layout)
        layout.addWidget(header_frame)
        
        # 2. Attachments (if any)
        attachments = email_data.get('attachments', [])
        if attachments:
            att_label = QLabel(f"Anexos ({len(attachments)}):")
            att_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
            layout.addWidget(att_label)
            
            att_cont = QWidget()
            att_flow = QHBoxLayout(att_cont)
            att_flow.setContentsMargins(0, 0, 0, 0)
            att_flow.setAlignment(Qt.AlignLeft)
            
            for att in attachments:
                # Handle dirty data
                if isinstance(att, dict):
                    name = att.get('name', 'Anexo')
                else:
                    name = str(att)
                    
                chip = AttachmentChip(name)
                att_flow.addWidget(chip)
                
            layout.addWidget(att_cont)
            
        # 3. Body
        body_label = QLabel("Mensagem:")
        body_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        layout.addWidget(body_label)
        
        self.body_view = QTextEdit()
        self.body_view.setReadOnly(True)
        # Try to show HTML, simplistic
        content = email_data.get('body', '')
        if '<html' in content.lower() or '<body' in content.lower() or '<div' in content.lower():
            self.body_view.setHtml(content)
        else:
            self.body_view.setPlainText(content)
            
        layout.addWidget(self.body_view)
        
        # 4. Footer Actions
        footer = QHBoxLayout()
        footer.addStretch()
        
        btn_close = QPushButton("Fechar")
        btn_close.setFixedSize(100, 35)
        btn_close.clicked.connect(self.accept)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_HOVER}; border: 1px solid {Colors.BORDER_INPUT}; color: {Colors.TEXT_BRIGHT}; border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {Colors.BG_CARD}; }}
        """)
        footer.addWidget(btn_close)
        
        layout.addLayout(footer)
