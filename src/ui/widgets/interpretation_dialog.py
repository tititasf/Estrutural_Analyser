from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPlainTextEdit, 
                               QDialogButtonBox, QWidget)
from PySide6.QtCore import Qt

class InterpretationDialog(QDialog):
    def __init__(self, parent=None, field_label="", current_prompt="", current_patterns=""):
        super().__init__(parent)
        self.setWindowTitle(f"Detalhamento e Padrões - {field_label}")
        self.resize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-weight: bold;
                font-size: 14px;
                margin-top: 10px;
            }
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #a0ffaa;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
                font-family: Consolas, monospace;
            }
            QPlainTextEdit:focus {
                border: 1px solid #00cc66;
            }
        """)

        layout = QVBoxLayout(self)
        
        # --- Prompt Descrição ---
        lbl_prompt = QLabel("Prompt Descrição (O que é este vínculo?):")
        self.txt_prompt = QPlainTextEdit()
        self.txt_prompt.setPlaceholderText("Descreva a função e as características visuais deste vínculo para auxiliar a IA...")
        self.txt_prompt.setPlainText(current_prompt)
        
        layout.addWidget(lbl_prompt)
        layout.addWidget(self.txt_prompt)
        
        # --- Padrões de Interpretação ---
        lbl_patterns = QLabel("Padrões de Interpretação (Curadoria da IDE):")
        self.txt_patterns = QPlainTextEdit()
        self.txt_patterns.setPlaceholderText("Espaço reservado para padrões aprendidos e validados pela IDE...")
        self.txt_patterns.setPlainText(current_patterns)
        
        layout.addWidget(lbl_patterns)
        layout.addWidget(self.txt_patterns)
        
        # --- Botões ---
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        """Retorna (prompt, patterns)"""
        return self.txt_prompt.toPlainText(), self.txt_patterns.toPlainText()
