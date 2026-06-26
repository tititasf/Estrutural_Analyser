from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFrame
from PySide6.QtCore import Qt
from .atoms import DeltaBadge
from src.ui.theme import Colors, Fonts, Radius

class ScenarioSelector(QWidget):
    """
    Selector de Cenário (Versão A vs Versão B).
    """
    def __init__(self, label="Scenario A"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(2)
        
        self.lbl = QLabel(label)
        self.lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px; font-weight: bold;")
        layout.addWidget(self.lbl)
        
        self.combo = QComboBox()
        self.combo.addItems(["Base Model (V1)", "Revised Model (V2)", "Proposal A", "Proposal B"])
        self.combo.setStyleSheet("""
            QComboBox {
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_INPUT};
                color: {Colors.TEXT_BRIGHT};
                padding: 4px;
                border-radius: 4px;
            }
            QComboBox::drop-down { border: none; }
        """)
        layout.addWidget(self.combo)

class ConflictCard(QFrame):
    """
    Card detalhando um conflito de comparação.
    Mostra Entidade, Valores Antigo/Novo e Delta.
    """
    def __init__(self, entity_name, val_a, val_b, delta_pct):
        super().__init__()
        self.setStyleSheet("""
            ConflictCard {
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Info
        v_layout = QVBoxLayout()
        v_layout.setSpacing(2)
        
        lbl_name = QLabel(entity_name)
        lbl_name.setStyleSheet(f"color: {Colors.TEXT_BRIGHT}; font-weight: bold; font-size: 11px;")
        
        lbl_diff = QLabel(f"{val_a} ➝ {val_b}")
        lbl_diff.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
        
        v_layout.addWidget(lbl_name)
        v_layout.addWidget(lbl_diff)
        
        layout.addLayout(v_layout)
        layout.addStretch()
        
        # Delta
        badge = DeltaBadge(delta_pct)
        layout.addWidget(badge)

class StressBarChart(QFrame):
    """
    Widget placeholder para gráfico de barras simples.
    """
    def __init__(self):
        super().__init__()
        self.setFixedHeight(100)
        self.setStyleSheet(f"background: {Colors.BG_CARD}; border-radius: 4px;")
        
        layout = QHBoxLayout(self)
        label = QLabel("Stress Distribution Graph\n(Placeholder)")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        layout.addWidget(label)
