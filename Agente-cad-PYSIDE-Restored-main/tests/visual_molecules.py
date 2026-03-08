import sys
import os
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea
from PySide6.QtCore import Qt

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui.components.molecules_diagnostic import FloorListItem, ViewShortcutItem, EntityRow
from src.ui.components.molecules_comparison import ScenarioSelector, ConflictCard, StressBarChart

def create_molecules_demo():
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Visual Molecules Test")
    window.setStyleSheet("background-color: #1e1e1e;")
    window.resize(500, 700)
    
    main_layout = QVBoxLayout(window)
    
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setSpacing(20)
    
    # 1. Diagnostic Molecules
    layout.addWidget(QLabel("--- Diagnostic Molecules ---", alignment=Qt.AlignCenter))
    
    # Floors
    layout.addWidget(FloorListItem("f1", "1st Floor", "0.00 - 3.50m", "VALID", active=True))
    layout.addWidget(FloorListItem("f2", "2nd Floor", "3.50 - 7.00m", "REVISÃO"))
    
    # Views
    layout.addWidget(ViewShortcutItem("v1", "Viga-01 Detail", is_locked=True))
    layout.addWidget(ViewShortcutItem("v2", "Corte A-A"))
    
    # Entity Rows
    layout.addWidget(EntityRow("Classification", "Structural Beam", editable=True))
    layout.addWidget(EntityRow("Material", "Concrete C30"))
    
    # 2. Comparison Molecules
    layout.addWidget(QLabel("--- Comparison Molecules ---", alignment=Qt.AlignCenter))
    
    h_cen = QHBoxLayout()
    h_cen.addWidget(ScenarioSelector("Base Scenario"))
    h_cen.addWidget(ScenarioSelector("Comparison Scenario"))
    layout.addLayout(h_cen)
    
    layout.addWidget(ConflictCard("Column P-102", "20x20", "25x25", 15.6))
    layout.addWidget(ConflictCard("Beam V-10", "300kg", "280kg", -6.5))
    
    layout.addWidget(StressBarChart())
    
    layout.addStretch()
    scroll.setWidget(content)
    main_layout.addWidget(scroll)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    create_molecules_demo()
