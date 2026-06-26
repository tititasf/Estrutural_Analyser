import sys
import os
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui.components.atoms import StatusBadge, NavButton, MetricLabel, DeltaBadge, AISuggestionBox, SyncToggleButton

def create_demo():
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Visual Atoms Test")
    window.setStyleSheet("background-color: #1e1e1e;")
    window.resize(400, 600)
    
    layout = QVBoxLayout(window)
    layout.setSpacing(20)
    
    # 1. Badges
    layout.addWidget(QLabel("Badges:", alignment=Qt.AlignCenter))
    h1 = QHBoxLayout()
    h1.addWidget(StatusBadge("VALID"))
    h1.addWidget(StatusBadge("REVISÃO - CHECK"))
    h1.addWidget(StatusBadge("CRITICAL ERROR"))
    layout.addLayout(h1)
    
    # 2. Delta Badges
    layout.addWidget(QLabel("Delta Badges:", alignment=Qt.AlignCenter))
    h2 = QHBoxLayout()
    h2.addWidget(DeltaBadge(15.4)) # Ruim (Vermelho)
    h2.addWidget(DeltaBadge(-5.2)) # Bom (Verde)
    h2.addWidget(DeltaBadge(0.12, inverse=True)) # Bom (Verde)
    layout.addLayout(h2)
    
    # 3. Nav Buttons
    layout.addWidget(QLabel("Nav Buttons:", alignment=Qt.AlignCenter))
    v1 = QVBoxLayout()
    v1.addWidget(NavButton("01. Pavimentos"))
    v1.addWidget(NavButton("02. Visões Detalhadas", active=True))
    layout.addLayout(v1)
    
    # 4. Metric Labels
    layout.addWidget(QLabel("Metric Labels:", alignment=Qt.AlignCenter))
    mlbr = QWidget()
    mlbr.setStyleSheet("background: #252525; padding: 10px; border-radius: 4px;")
    ml = QVBoxLayout(mlbr)
    ml.addWidget(MetricLabel("Deformação Máx", "0.02", "mm", highlight=True))
    ml.addWidget(MetricLabel("Carga Crítica", "142.5", "kN"))
    layout.addWidget(mlbr)
    
    # 5. AI Box
    layout.addWidget(QLabel("AI Suggestion:", alignment=Qt.AlignCenter))
    layout.addWidget(AISuggestionBox("Reforço insuficiente na viga V-201. Sugere-se adicionar estribos Ø5 a cada 15cm."))
    
    # 6. Sync Toggle
    layout.addWidget(QLabel("Sync Toggle:", alignment=Qt.AlignCenter))
    layout.addWidget(SyncToggleButton(), alignment=Qt.AlignCenter)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    create_demo()
