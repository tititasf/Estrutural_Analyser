import sys
import os
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout
from PySide6.QtCore import Qt

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ui.components.organisms import DiagnosticSidebar, TechSheetPanel, DualCanvasManager

def create_organisms_demo():
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Visual Organisms Test")
    window.resize(1200, 800)
    
    layout = QHBoxLayout(window)
    layout.setSpacing(0)
    layout.setContentsMargins(0,0,0,0)
    
    # 1. Sidebar
    sidebar = DiagnosticSidebar()
    sidebar.add_floor("f1", "Ground Floor", "0.00 - 3.50")
    sidebar.add_floor("f2", "1st Floor", "3.50 - 7.00", "REVISÃO")
    sidebar.add_view("v1", "Viga Detalhe")
    layout.addWidget(sidebar)
    
    # 2. Dual Canvas (Center)
    dual = DualCanvasManager()
    layout.addWidget(dual, 1) # Stretch
    
    # 3. Tech Panel (Right)
    tech = TechSheetPanel()
    layout.addWidget(tech)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    create_organisms_demo()
