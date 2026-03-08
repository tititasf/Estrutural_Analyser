from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout, QScrollArea, QWidget, QLabel
from PySide6.QtCore import Qt
from src.ui.widgets.detail_card import DetailCard

class DetailDialog(QDialog):
    """
    Dialogo modal para exibir os detalhes de um item (Pilar, Viga, Laje).
    Reutiliza o DetailCard para consistência.
    """
    def __init__(self, item_data, parent=None, read_only=False):
        super().__init__(parent)
        self.item_data = item_data
        self.read_only = read_only
        self.setWindowTitle(f"Detalhamento: {item_data.get('name', 'Item')}")
        self.resize(500, 700)
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #e0e0e0; }
            QLabel { color: #e0e0e0; }
        """)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #252528; border-bottom: 1px solid #333;")
        header.setFixedHeight(50)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(15, 0, 15, 0)
        
        title = QLabel(f"{self.item_data.get('type', 'Item').upper()} | {self.item_data.get('name', '')}")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #00d4ff;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        
        if self.read_only:
            lbl_ro = QLabel("👁️ Modo Leitura")
            lbl_ro.setStyleSheet("background: #333; padding: 4px 8px; border-radius: 4px; font-size: 10px; color: #aaa;")
            h_layout.addWidget(lbl_ro)
            
        layout.addWidget(header)
        
        # Scroll Area for Card
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        # Container wrapper
        # DetailCard expects to be in a layout or widget, we'll embed it directly.
        # Note: DetailCard might have signals we need to handle if we want persistence here.
        self.card = DetailCard(self.item_data)
        
        if self.read_only:
            self.card.setEnabled(False) 
            # Or better, iterate fields and setReadOnly, but disabling whole card works for "offline view"
            
        scroll.setWidget(self.card)
        layout.addWidget(scroll)
        
        # Footer Actions
        footer = QWidget()
        footer.setStyleSheet("background-color: #252528; border-top: 1px solid #333;")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(15, 10, 15, 10)
        f_layout.addStretch()
        
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.accept)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #444; color: white; border: none; padding: 8px 16px; border-radius: 4px;
            }
            QPushButton:hover { background: #555; }
        """)
        f_layout.addWidget(btn_close)
        
        if not self.read_only:
            btn_save = QPushButton("Salvar Alterações") # Na verdade o Card edita o dict in-place
            # Mas podemos ter um botão explícito se precisarmos de ação de DB
            # Por enquanto, o card edita 'item_data' que é referencia.
            btn_save.hide() 
            f_layout.addWidget(btn_save)

        layout.addWidget(footer)
