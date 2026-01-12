from PySide6.QtWidgets import QGraphicsPolygonItem, QGraphicsSimpleTextItem, QGraphicsItem
from PySide6.QtGui import QPolygonF, QBrush, QPen, QColor, QFont
from PySide6.QtCore import Qt, Signal, QObject, QPointF

class SignalProxy(QObject):
    """Proxy para emitir sinais de itens gráficos que não herdam de QObject"""
    clicked = Signal(int) # ID do item

class PillarGraphicsItem(QGraphicsPolygonItem):
    """
    Representação visual de um Pilar no Canvas.
    Suporta Hover e Click para seleção.
    """
    def __init__(self, pillar_id: int, points: list, label: str = None):
        super().__init__()
        self.pillar_id = pillar_id
        
        # Construir polígono
        poly = QPolygonF()
        for x, y in points:
            poly.append(QPointF(x, y))
        self.setPolygon(poly)
        
        # Estilo Base
        # Estilo Base (Mais suave)
        self.default_brush = QBrush(QColor(0, 100, 255, 30)) 
        self.hover_brush = QBrush(QColor(0, 150, 255, 60))
        self.selected_brush = QBrush(QColor(255, 165, 0, 40)) 
        
        self.is_validated = False
        self.setBrush(self.default_brush)
        
        # Pens de contorno (Destaque principal solicitado)
        self.default_pen = QPen(Qt.NoPen)
        self.hover_pen = QPen(QColor(0, 150, 255), 2)
        self.hover_pen.setCosmetic(True)
        
        self.selected_pen = QPen(QColor(255, 165, 0), 4) # Laranja grosso no contorno
        self.selected_pen.setCosmetic(True)
        
        self.validated_pen = QPen(QColor(76, 175, 80), 3)
        self.validated_pen.setCosmetic(True)

        self.uncertain_pen = self.default_pen # Desativado visual laranja/amarelo por solicitação
        self.error_pen = self.default_pen # Desativado visual laranja/amarelo por solicitação
        
        self.setPen(self.default_pen)

        self.visual_status = "default" # "default", "uncertain", "error", "validated"
        self.confidence = 1.0

        # Interatividade
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        
        # Proxy de Sinais (QGraphicsItem não emite sinais nativamente)
        self.proxy = SignalProxy()
        
        # Label (Opcional)
        if label:
            self.text_item = QGraphicsSimpleTextItem(label, self)
            font = QFont("Inter", 10, QFont.Bold) 
            self.text_item.setFont(font)
            self.text_item.setBrush(QBrush(Qt.white))
            center = poly.boundingRect().center()
            self.text_item.setPos(center.x(), center.y())
            self.text_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)

    def set_visual_status(self, status: str, confidence: float = 1.0):
        """Atualiza a estética baseada na saúde dos dados da IA/Engenharia"""
        self.visual_status = status
        self.confidence = confidence
        self._apply_current_style()

    def set_validated(self, validated: bool):
        self.is_validated = validated
        self.visual_status = "validated" if validated else "default"
        self._apply_current_style()

    def _apply_current_style(self):
        """Centraliza a lógica de cores para evitar redundância"""
        if self.isSelected():
            self.setBrush(self.selected_brush)
            self.setPen(self.selected_pen)
            return

        if self.visual_status == "error":
            self.setBrush(QBrush(QColor(255, 0, 0, 60)))
            self.setPen(self.error_pen)
        elif self.visual_status == "uncertain":
            self.setBrush(QBrush(QColor(255, 215, 0, 50)))
            self.setPen(self.uncertain_pen)
        elif self.visual_status == "validated":
            self.setBrush(QBrush(QColor(76, 175, 80, 50)))
            self.setPen(self.validated_pen)
        else:
            self.setBrush(self.default_brush)
            self.setPen(self.default_pen)

    def hoverEnterEvent(self, event):
        if not self.isSelected():
            self.setBrush(self.hover_brush)
            self.setPen(self.hover_pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if not self.isSelected():
            self._apply_current_style()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self.proxy.clicked.emit(self.pillar_id)
        super().mousePressEvent(event)

    def paint(self, painter, option, widget=None):
        # Desativa visual padrão de seleção do Qt (bounding box tracejada)
        from PySide6.QtWidgets import QStyle
        option.state &= ~QStyle.State_Selected
        super().paint(painter, option, widget)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange:
            # Força reaplicação de estilo ao selecionar/deselecionar
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._apply_current_style)
        return super().itemChange(change, value)

class SlabGraphicsItem(QGraphicsPolygonItem):
    """
    Representação visual de uma Laje.
    """
    def __init__(self, points: list, label: str = None, area: float = 0.0):
        super().__init__()
        
        poly = QPolygonF()
        for x, y in points:
            poly.append(QPointF(x, y))
        self.setPolygon(poly)
        
        # Estilos Base
        self.default_brush = QBrush(QColor(200, 200, 200, 50))
        self.validated_brush = QBrush(QColor(76, 175, 80, 50))
        self.default_pen = QPen(QColor(100, 100, 100, 100), 1, Qt.DashLine)
        self.validated_pen = QPen(QColor(76, 175, 80), 3)
        self.validated_pen.setCosmetic(True)

        self.is_validated = False
        
        # Estilo Laje (Transparente, preenchimento suave)
        self.setBrush(self.default_brush) 
        self.setPen(self.default_pen)
        
        if label:
            self.setToolTip(f"{label}\nÁrea: {area:.2f}m²") 
        
        # Label Text (Centralizado)
        if label:
            self.text_item = QGraphicsSimpleTextItem(label, self)
            font = QFont("Arial", 16, QFont.Bold) 
            self.text_item.setFont(font)
            self.text_item.setBrush(QBrush(QColor(200, 200, 200))) # Text claro
            
            center = poly.boundingRect().center()
            self.text_item.setPos(center.x(), center.y())
            self.text_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)

    def set_validated(self, validated: bool):
        self.is_validated = validated
        if validated:
            self.setBrush(self.validated_brush)
            self.setPen(self.validated_pen)
            if hasattr(self, 'text_item'):
                self.text_item.setBrush(QBrush(QColor(76, 175, 80)))
        else:
            self.setBrush(self.default_brush)
            self.setPen(self.default_pen)
            if hasattr(self, 'text_item'):
                 self.text_item.setBrush(QBrush(QColor(200, 200, 200)))

