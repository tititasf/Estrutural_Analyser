from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsItem
from PySide6.QtGui import QPen, QColor
from PySide6.QtCore import Qt

class BeamGraphicsItem(QGraphicsLineItem):
    """
    Representação visual de uma Viga (Raycasting) no Canvas.
    """
    def __init__(self, start_pt: tuple, end_pt: tuple, segments: list):
        super().__init__()
        self.setLine(start_pt[0], start_pt[1], end_pt[0], end_pt[1])
        
        # Pen padrão para o eixo
        pen = QPen(QColor(255, 0, 255, 180), 3) # Magenta
        pen.setCosmetic(True)
        self.setPen(pen)
        
        self.segments = segments
        self._init_segments()

    def _init_segments(self):
        """Cria sub-itens para mostrar onde há conflitos e onde há vão livre."""
        # Nota: Simplificando para o MVP, vamos desenhar pequenos marcadores ou mudar cor
        # Melhor: Adicionar linhas filhas com cores diferentes
        line = self.line()
        dx = line.x2() - line.x1()
        dy = line.y2() - line.y1()
        length = (dx**2 + dy**2)**0.5
        
        if length == 0: return
        
        ux, uy = dx/length, dy/length
        
        for seg in self.segments:
            s_dist = seg['start_dist']
            e_dist = seg['end_dist']
            
            p1 = (line.x1() + ux * s_dist, line.y1() + uy * s_dist)
            p2 = (line.x1() + ux * e_dist, line.y1() + uy * e_dist)
            
            seg_item = QGraphicsLineItem(p1[0], p1[1], p2[0], p2[1], self)
            
            color = QColor(0, 255, 0, 200) # Verde para Vão Livre
            if seg['type'] != 'Vão Livre':
                color = QColor(255, 0, 0, 255) # Vermelho para Conflito (Pilar/Parede)
            
            pen = QPen(color, 5)
            pen.setCosmetic(True)
            seg_item.setPen(pen)
            
            if seg['type'] != 'Vão Livre':
                seg_item.setToolTip(f"Conflito: {seg['type']} ({seg['length']:.1f} units)")
