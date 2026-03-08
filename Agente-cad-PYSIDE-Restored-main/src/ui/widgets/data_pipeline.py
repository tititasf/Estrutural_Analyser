import logging
from typing import Dict, List, Any, Optional
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                                QFrame, QScrollArea, QPushButton, QProgressBar,
                                QSizePolicy, QSpacerItem)
from PySide6.QtCore import Qt, QSize, Signal, Property, QRect, QPoint, QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QPolygon, QFont, QLinearGradient

class DiamondNode(QWidget):
    clicked = Signal()
    
    def __init__(self, phase_name: str, value: str, subtext: str, color: str = "#00d4ff"):
        super().__init__()
        self.phase_name = phase_name
        self.value = value
        self.subtext = subtext
        self.color = color
        self.is_hovered = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(180, 160)
        self.setMaximumWidth(180)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Geometry
        width = self.width()
        height = self.height()
        center_x = width // 2
        center_y = height // 2
        diamond_size = 110
        
        # Glow Effect if hovered
        if self.is_hovered:
            glow_color = QColor(self.color)
            glow_color.setAlpha(40)
            painter.setBrush(glow_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center_x - 70, center_y - 70, 140, 140)

        # Draw Diamond
        diamond = QPolygon([
            QPoint(center_x, center_y - (diamond_size // 2)),    # Top
            QPoint(center_x + (diamond_size // 2), center_y),    # Right
            QPoint(center_x, center_y + (diamond_size // 2)),    # Bottom
            QPoint(center_x - (diamond_size // 2), center_y)     # Left
        ])
        
        # Border
        pen_width = 3 if self.is_hovered else 2
        pen = QPen(QColor(self.color), pen_width)
        painter.setPen(pen)
        
        # Gradient Fill
        grad = QLinearGradient(center_x, center_y - 50, center_x, center_y + 50)
        bg_col = QColor("#1a1a1a")
        grad.setColorAt(0, bg_col)
        grad.setColorAt(1, QColor("#121212"))
        painter.setBrush(grad)
        
        painter.drawPolygon(diamond)
        
        # Text Rendering
        # Phase Name (Top Small)
        font_small = QFont("Inter", 7, QFont.Bold)
        painter.setFont(font_small)
        painter.setPen(QColor("#666"))
        painter.drawText(QRect(0, center_y - 42, width, 12), Qt.AlignCenter, self.phase_name.upper())
        
        # Value (Center Large)
        font_large = QFont("Outfit", 14, QFont.Bold)
        painter.setFont(font_large)
        painter.setPen(QColor(self.color))
        painter.drawText(QRect(0, center_y - 12, width, 24), Qt.AlignCenter, str(self.value))
        
        # Subtext (Bottom Small)
        painter.setFont(font_small)
        painter.setPen(QColor("#888"))
        painter.drawText(QRect(0, center_y + 12, width, 12), Qt.AlignCenter, self.subtext.upper())

class DetailPanel(QFrame):
    def __init__(self, title: str, details: Dict[str, Any], color: str = "#00d4ff"):
        super().__init__()
        self.details = details
        self.color = color
        self.title = title
        self.setup_ui()
        self.setObjectName("DetailPanel")
        self.setStyleSheet(f"""
            #DetailPanel {{
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-left: 3px solid {color};
                border-radius: 8px;
                margin: 10px 0px;
            }}
            #TitleLbl {{ color: white; font-weight: bold; font-size: 14px; margin-bottom: 5px; }}
            QLabel {{ color: #aaa; font-size: 12px; }}
            .detail-value {{ color: {color}; font-weight: bold; font-family: 'Consolas'; font-size: 13px; }}
        """)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(6)
        
        title_lbl = QLabel(self.title)
        title_lbl.setObjectName("TitleLbl")
        layout.addWidget(title_lbl)
        
        for key, value in self.details.items():
            h_layout = QHBoxLayout()
            lbl_key = QLabel(key)
            lbl_value = QLabel(str(value))
            lbl_value.setProperty("class", "detail-value")
            lbl_value.setAlignment(Qt.AlignRight)
            
            h_layout.addWidget(lbl_key)
            h_layout.addStretch()
            h_layout.addWidget(lbl_value)
            layout.addLayout(h_layout)

    def toggle(self, expanded: bool):
        # Keep for compatibility but we start expanded
        pass

class PipelineConnector(QWidget):
    def __init__(self, color: str = "#333"):
        super().__init__()
        self.color = color
        self.setMinimumHeight(40)
        self.setMaximumWidth(180)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center_x = self.width() // 2
        pen = QPen(QColor(self.color), 2, Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(center_x, 0, center_x, self.height())

class DataPipelineView(QWidget):
    def __init__(self):
        super().__init__()
        self.nodes = []
        self.panels = []
        self.setup_ui()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(0)
        self.main_layout.setAlignment(Qt.AlignTop)

    def _add_connector(self, color):
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        
        conn = PipelineConnector(color)
        h_layout.addWidget(conn)
        h_layout.addStretch()
        
        self.main_layout.addLayout(h_layout)

    def refresh(self, stats: Dict[str, Any]):
        # Clear existing
        for i in reversed(range(self.main_layout.count())):
            item = self.main_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                # Clear nested layouts
                l = item.layout()
                for j in reversed(range(l.count())):
                    w = l.itemAt(j).widget()
                    if w: w.setParent(None)
        
        self.nodes = []
        self.panels = []
        
        if not stats:
            self.main_layout.addWidget(QLabel("Nenhum dado disponível para o pipeline."))
            return

        # Phase 1: Ingestão
        self._add_phase(
            name="FASE 01",
            title="INGESTÃO",
            value=f"{stats.get('ingestion', {}).get('works', 0)} OBRAS",
            subtext=f"{stats.get('ingestion', {}).get('documents', 0)} DOCS",
            color="#00d4ff",
            details=stats.get('ingestion', {}).get('details', {})
        )
        
        self._add_connector("#00d4ff")
        
        # Phase 2: Triagem
        self._add_phase(
            name="FASE 02",
            title="TRIAGEM",
            value=f"{stats.get('triage', {}).get('processed', 0)} DXF",
            subtext="VALIDADOS",
            color="#28a745",
            details=stats.get('triage', {}).get('details', {})
        )
        
        self._add_connector("#28a745")
        
        # Phase 3: Extração/Detecção
        self._add_phase(
            name="FASE 03",
            title="EXTRAÇÃO",
            value=f"{stats.get('detection', {}).get('total_items', 0)} ITENS",
            subtext="IDENTIFICADOS",
            color="#a333c8",
            details=stats.get('detection', {}).get('details', {})
        )
        
        self._add_connector("#a333c8")
        
        # Phase 4: Reconhecimento (Johnson Robôs)
        self._add_phase(
            name="FASE 04",
            title="RECONHECIMENTO",
            value=f"{stats.get('recognition', {}).get('total_johnson', 0)} JSONS",
            subtext="JOHNSON ROBÔS",
            color="#fbbd08",
            details=stats.get('recognition', {}).get('details', {})
        )
        
        self._add_connector("#fbbd08")
        
        # Phase 5: Robot Feed (.SCR)
        self._add_phase(
            name="FASE 05",
            title="ROBOT FEED",
            value=f"{stats.get('robot_feed', {}).get('total_scripts', 0)} .SCR",
            subtext="GERADOS",
            color="#db2828",
            details=stats.get('robot_feed', {}).get('details', {})
        )

        self._add_connector("#db2828")

        # Phase 6: Conversão (SCR -> DXF)
        self._add_phase(
            name="FASE 06",
            title="CONVERSÃO",
            value=f"{stats.get('conversion', {}).get('total_dxf', 0)} DXF",
            subtext="POPULADOS",
            color="#2185d0",
            details=stats.get('conversion', {}).get('details', {})
        )

        self._add_connector("#2185d0")

        # Phase 7: Unificação DXF
        self._add_phase(
            name="FASE 07",
            title="UNIFICAÇÃO",
            value=f"{stats.get('unification', {}).get('total_unified', 0)} UNIF",
            subtext="PAVIMENTOS",
            color="#e03997",
            details=stats.get('unification', {}).get('details', {})
        )

        self._add_connector("#e03997")

        # Phase 8: Entrega
        self._add_phase(
            name="FASE 08",
            title="ENTREGA",
            value=f"{stats.get('delivery', {}).get('total_reviewed', 0)} PROJ",
            subtext="REVISADOS",
            color="#b5cc18",
            details=stats.get('delivery', {}).get('details', {})
        )

        self.main_layout.addStretch()

    def _add_phase(self, name, title, value, subtext, color, details):
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(20)
        
        node = DiamondNode(name, value, subtext, color)
        panel = DetailPanel(f"{name}: {title}", details, color)
        
        h_layout.addWidget(node)
        h_layout.addWidget(panel)
        h_layout.addStretch()
        
        self.main_layout.addLayout(h_layout)
        self.nodes.append(node)
        self.panels.append(panel)
