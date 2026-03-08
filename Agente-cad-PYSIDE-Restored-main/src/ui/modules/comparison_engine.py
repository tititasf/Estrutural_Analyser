from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from src.ui.components.organisms import DualCanvasManager, TechSheetPanel

class ComparisonEngineModule(QWidget):
    """
    Página Principal do Módulo de Comparação (Pós-Processamento).
    Layout: [DualCanvas] [AnalyticsPanel]
    """
    def __init__(self):
        super().__init__()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. Dual Canvas (Esquerda/Centro)
        self.dual_canvas = DualCanvasManager()
        layout.addWidget(self.dual_canvas, 1) # Stretch
        
        # 2. Analytics Panel (Reusando TechPanel por enquanto ou criando específico)
        # Vamos usar um placeholder ou adaptar TechPanel
        self.analytics_panel = TechSheetPanel() 
        # TODO: Custom Analytics Sidebar se necessário diferente do TechSheet
        layout.addWidget(self.analytics_panel)
