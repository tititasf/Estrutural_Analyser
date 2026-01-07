from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsSimpleTextItem
from PySide6.QtCore import Qt, Signal, QMarginsF, QRectF
from PySide6.QtGui import QPainter, QWheelEvent, QTransform, QPen, QColor, QBrush, QPainterPath
from src.ui.overlays import PillarGraphicsItem, SlabGraphicsItem
from src.ui.overlays_beams import BeamGraphicsItem

class CADCanvas(QGraphicsView):
    pillar_selected = Signal(int)
    pick_completed = Signal(dict) # Retorna dados estruturados do vínculo


    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Configs de Visualização
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Cores (Dark Mode cad-like)
        self.setBackgroundBrush(QColor(15, 15, 15)) # Preto profundo
        
        # Estado
        self.interactive_items = {} # Map ID -> GraphicItem (Generic)
        self.item_groups = { # Store lists for bulk visibility toggling
            'pillar': [],
            'slab': [],
            'beam': [],
            'link': [] # Visual links (texts/lines)
        }
        self.beam_visuals = []      
        
        # Modo de Captação (Vínculo)
        self.picking_mode = None    # 'text' | 'line'
        self.pick_start = None
        self.dxf_entities = []
        self.snap_points = []       # Armazena todos os vértices para OSNAP
        self.overlay_items = []     # Itens persistentes de vínculo
        self.temp_line = None
        self.temp_text = None
        self.snap_markers = {}      # Dicionário para marcadores {type: item}
        self.instruction_label = None # Mensagem de UX no topo

        # Opções de Interação
        self.setMouseTracking(True)
        self._is_panning = False
        self._last_pan_pos = None

        # Polyline Picking State
        self.pick_poly_points = []
        self.poly_visual = None  # QGraphicsPathItem
        self.active_isolation = None # Current isolated item ID

    def set_category_visibility(self, category_to_show, show_links=True):
        """Alterna visibilidade: 'pillar', 'slab', 'beam', 'all'"""
        self.active_isolation = None
        
        # Helper to toggle list
        def toggle_list(key, visible):
            for item in self.item_groups.get(key, []):
                if visible: item.show()
                else: item.hide()
                
        cats = ['pillar', 'slab', 'beam']
        for c in cats:
            should_show = (category_to_show == 'all') or (category_to_show == c)
            toggle_list(c, should_show)
            
        # Links cleaning/redraw logic could go here or be handled by main
        # For now we assume links are child items or part of the visuals handled above?
        # Actually links usually are drawn on demand. 
        # But if we have persistent link visuals, we should group them.
        self.clear_beams() # Limpa destaques temporários

    def isolate_item(self, item_id, category):
        """Oculta tudo, mostra apenas o item específico e seus vínculos"""
        self.active_isolation = item_id
        
        # Hide all first
        self.set_category_visibility('none')
        
        # Show specific item
        if item_id in self.interactive_items:
            self.interactive_items[item_id].show()
            
            # Zoom to it
            item = self.interactive_items[item_id]
            self.centerOn(item.sceneBoundingRect().center())
            
    def clear_interactive(self):
        """Limpa apenas os itens de overlay interativo, mantendo o background DXF"""
        for item in self.interactive_items.values():
            self.scene.removeItem(item)
        self.interactive_items.clear()
        
        # Clear grouped lists
        for k in self.item_groups:
            self.item_groups[k] = []
            
        self.clear_beams()

    def clear_beams(self):
        """Limpa os fios de viga (conflitos)"""
        for item in self.beam_visuals:
            try: self.scene.removeItem(item)
            except: pass
        self.beam_visuals.clear()
        
    def _add_snap_point(self, pt, type='endpoint'):
        # Evitar duplicatas exatas
        for s in self.snap_points:
            if abs(s['pos'][0] - pt[0]) < 0.001 and abs(s['pos'][1] - pt[1]) < 0.001:
                # Se já existe, atualiza prioridade se for Intersection
                if type == 'intersection': s['type'] = 'intersection'
                return
        self.snap_points.append({'pos': pt, 'type': type})

    def _calculate_intersections(self, lines):
        """Calcula intersecções entre todas as linhas (N^2 simplificado)."""
        # Formato lines: [{'start': (x,y), 'end': (x,y)}, ...]
        
        def line_intersection(p1, p2, p3, p4):
            x1, y1 = p1
            x2, y2 = p2
            x3, y3 = p3
            x4, y4 = p4
            
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            if denom == 0: return None  # Paralelas
            
            ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
            ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom
            
            if 0 <= ua <= 1 and 0 <= ub <= 1:
                x = x1 + ua * (x2 - x1)
                y = y1 + ua * (y2 - y1)
                return (x, y)
            return None

        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                l1 = lines[i]
                l2 = lines[j]
                
                # Bounding box check rápido
                minx1, maxx1 = min(l1['start'][0], l1['end'][0]), max(l1['start'][0], l1['end'][0])
                minx2, maxx2 = min(l2['start'][0], l2['end'][0]), max(l2['start'][0], l2['end'][0])
                if maxx1 < minx2 or maxx2 < minx1: continue
                
                pt = line_intersection(l1['start'], l1['end'], l2['start'], l2['end'])
                if pt:
                    self._add_snap_point(pt, 'intersection')

    def add_dxf_entities(self, entities):
        """Renderiza geometria base (linhas, textos, etc) do DXF"""
        self.scene.clear()
        self.snap_markers = {} # Reset markers
        self.interactive_items = {}
        self.beam_visuals = []
        self.snap_points = []
        self.dxf_entities = entities.get('texts', [])
        
        # Helper para criar Pen a partir de cor DXF
        def get_pen(color_tuple, width=1):
            pen = QPen(QColor(*color_tuple), width)
            pen.setCosmetic(True)
            return pen

        # Armazena linhas para cálculo de interseção
        calc_lines = []

        # Draw Lines
        for line in entities.get('lines', []):
            s, e = line['start'], line['end']
            self.scene.addLine(s[0], s[1], e[0], e[1], get_pen(line['color']))
            calc_lines.append(line)
            
            # Midpoint
            mid = ((s[0]+e[0])/2, (s[1]+e[1])/2)
            self._add_snap_point(mid, 'midpoint')
            self._add_snap_point(s, 'endpoint')
            self._add_snap_point(e, 'endpoint')

        # Draw Polylines
        from PySide6.QtGui import QPainterPath
        
        for poly in entities.get('polylines', []):
            points = poly['points']
            if not points: continue
            
            path = QPainterPath()
            path.moveTo(points[0][0], points[0][1])
            self._add_snap_point(points[0], 'endpoint')
            
            for i in range(1, len(points)):
                p_prev = points[i-1]
                p_curr = points[i]
                path.lineTo(p_curr[0], p_curr[1])
                
                # Segmento para interseção e Midpoint
                calc_lines.append({'start': p_prev, 'end': p_curr})
                mid = ((p_prev[0]+p_curr[0])/2, (p_prev[1]+p_curr[1])/2)
                self._add_snap_point(mid, 'midpoint')
                self._add_snap_point(p_curr, 'endpoint')
            
            if poly.get('is_closed'):
                path.closeSubpath()
                # Fechamento
                p_last = points[-1]
                p_first = points[0]
                calc_lines.append({'start': p_last, 'end': p_first})
                mid = ((p_last[0]+p_first[0])/2, (p_last[1]+p_first[1])/2)
                self._add_snap_point(mid, 'midpoint')
            
            self.scene.addPath(path, get_pen(poly['color']))

        # Calcular Interseções
        self._calculate_intersections(calc_lines)

        # Draw Circles e Arcs
        for circle in entities.get('circles', []):
            r = circle['radius']
            cx, cy = circle['center']
            self._add_snap_point((cx, cy), 'center')
            # Quadrantes
            self._add_snap_point((cx+r, cy), 'quadrant')
            self._add_snap_point((cx-r, cy), 'quadrant')
            self._add_snap_point((cx, cy+r), 'quadrant')
            self._add_snap_point((cx, cy-r), 'quadrant')
            
            if 'start_angle' in circle: # ARC
                path = QPainterPath()
                path.arcMoveTo(cx - r, cy - r, r * 2, r * 2, circle['start_angle'])
                path.arcTo(cx - r, cy - r, r * 2, r * 2, circle['start_angle'], circle['end_angle'] - circle['start_angle'])
                self.scene.addPath(path, get_pen(circle['color']))
            else:
                self.scene.addEllipse(cx - r, cy - r, r * 2, r * 2, get_pen(circle['color']))

        # Draw Texts
        from PySide6.QtWidgets import QGraphicsSimpleTextItem
        from PySide6.QtGui import QFont
        
        for txt in entities.get('texts', []):
            item = QGraphicsSimpleTextItem(txt['text'])
            item.setPos(txt['pos'][0], txt['pos'][1])
            self._add_snap_point(txt['pos'], 'endpoint') # Texto conta como endpoint
            item.setBrush(QColor(*txt['color']))
            
            f = QFont("Arial")
            f.setPointSizeF(8)
            item.setFont(f)
            item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
            self.scene.addItem(item)
            
        self._init_osnap_markers()
        self._init_instruction_overlay()
        
        # Smart View (Ignorar outliers do DXF como pontos no 0,0 ou infinito)
        pts = []
        for t in entities.get('texts', []): pts.append(t['pos'])
        for l in entities.get('lines', []): 
            pts.append(l['start'])
            pts.append(l['end'])
        for p in entities.get('polylines', []):
            for pt in p.get('points', []): pts.append(pt)
            
        if pts:
            xs = sorted([p[0] for p in pts])
            ys = sorted([p[1] for p in pts])
            # Pegar do percentil 2 ao 98 para evitar sujeira de borda do CAD
            idx_low = int(len(xs) * 0.02)
            idx_high = int(len(xs) * 0.98)
            
            if idx_high > idx_low:
                xmin, xmax = xs[idx_low], xs[idx_high]
                ymin, ymax = ys[idx_low], ys[idx_high]
                rect = QRectF(xmin, ymin, xmax - xmin, ymax - ymin)
                
                margin = (xmax - xmin) * 0.1 # 10% margem
                rect = rect.adjusted(-margin, -margin, margin, margin)
                
                self.fitInView(rect, Qt.KeepAspectRatio)
            else:
                self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        else:
            self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def _init_osnap_markers(self):
        """Prepara os marcadores de snap (Quadrado, Triângulo, X)"""
        # Endpoint/Center: Quadrado Verde
        sq = self.scene.addRect(-5, -5, 10, 10, QPen(QColor(0, 255, 0), 2))
        sq.setZValue(200); sq.hide(); sq.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.snap_markers['endpoint'] = sq
        self.snap_markers['center'] = sq # Reutiliza
        self.snap_markers['quadrant'] = sq # Reutiliza

        # Midpoint: Triângulo Ciano
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        tri_poly = QPolygonF([QPointF(0, -6), QPointF(-5, 4), QPointF(5, 4)])
        tri = self.scene.addPolygon(tri_poly, QPen(QColor(0, 255, 255), 2))
        tri.setZValue(200); tri.hide(); tri.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.snap_markers['midpoint'] = tri

        # Intersection: X Vermelho/Laranja
        path = QPainterPath()
        path.moveTo(-5, -5); path.lineTo(5, 5)
        path.moveTo(5, -5); path.lineTo(-5, 5)
        cross = self.scene.addPath(path, QPen(QColor(255, 100, 0), 2))
        cross.setZValue(200); cross.hide(); cross.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.snap_markers['intersection'] = cross

    def _init_instruction_overlay(self):
        """Mensagem fixa no topo do canvas para guiar o usuário"""
        from PySide6.QtWidgets import QLabel
        self.instruction_label = QLabel(self)
        self.instruction_label.setStyleSheet("""
            background: rgba(0, 40, 100, 220); 
            color: white; 
            padding: 12px; 
            border: 1px solid #0078d4; 
            border-radius: 6px;
            font-family: Arial;
            font-size: 11px;
        """)
        self.instruction_label.move(20, 20)
        self.instruction_label.hide()

    def draw_interactive_pillars(self, pillars_data: list):
        """Desenha pilares processados com suporte a heatmap de confiança/erro"""
        for p_data in pillars_data:
            points = p_data.get('points') 
            if points:
                item = PillarGraphicsItem(p_data['id'], points, p_data.get('name'))
                item.setZValue(10) # Pilares sempre acima
                item.proxy.clicked.connect(self.on_pillar_clicked)
                
                # Aplicar Status Inicial
                if p_data.get('is_validated'):
                    item.set_validated(True)
                elif p_data.get('issues'):
                    item.set_visual_status("error")
                else:
                    conf_map = p_data.get('confidence_map', {})
                    avg_conf = sum(conf_map.values()) / len(conf_map) if conf_map else 1.0
                    if avg_conf < 0.6:
                        item.set_visual_status("uncertain", avg_conf)
                
                self.scene.addItem(item)
                self.interactive_items[p_data['id']] = item
                self.item_groups['pillar'].append(item) # Control Group

    def update_pillar_visual_status(self, p_id, status, confidence=1.0):
        """Atualiza a cor de um pilar específico em tempo real"""
        if p_id in self.interactive_items:
            self.interactive_items[p_id].set_visual_status(status, confidence)

    def draw_slabs(self, slabs_data: list):
        """Desenha lajes identificadas"""
        for s_data in slabs_data:
            points = s_data.get('points')
            if points:
                item = SlabGraphicsItem(points, s_data.get('name'), s_data.get('area', 0))
                item.setZValue(1) # Acima do background, abaixo dos pilares
                self.scene.addItem(item)
                
                # Slabs também precisam ser 'interativos' para isolamento
                if 'id' in s_data:
                    self.interactive_items[s_data['id']] = item
                    self.item_groups['slab'].append(item)

    def draw_focus_beams(self, beams_visual_data: list):
        """Desenha vigas APENAS para o foco atual (pilar selecionado)"""
        self.clear_beams()
        # Suporte sutil para todos os apoios
        for b_data in beams_visual_data:
            pen = QPen(QColor(100, 100, 100, 100), 1, Qt.DashLine)
            pen.setCosmetic(True)
            line = self.scene.addLine(b_data['start'][0], b_data['start'][1], 
                               b_data['end'][0], b_data['end'][1], pen)
            self.beam_visuals.append(line)

    def highlight_link(self, link):
        """Destaque direto via objeto de vínculo (sem busca)"""
        if not link: return
        
        self.clear_beams()
        pen = QPen(QColor(255, 179, 0), 4) # Amber Master
        pen.setCosmetic(True)
        
        item = None
        l_type = link.get('type')
        
        if l_type == 'text' and 'pos' in link:
            item = self.scene.addSimpleText(link['text'])
            item.setPos(link['pos'][0], link['pos'][1])
            item.setBrush(QBrush(QColor(255, 179, 0)))
            item.setZValue(101)
            item.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations)
        elif (l_type == 'line' or l_type == 'poly' or l_type == 'geometry') and 'points' in link:
            from PySide6.QtGui import QPainterPath
            pts = link['points']
            if len(pts) >= 2:
                path = QPainterPath()
                path.moveTo(pts[0][0], pts[0][1])
                for p in pts[1:]: path.lineTo(p[0], p[1])
                # Se for um polígono fechado (ex: retângulo de pilar)
                if l_type == 'poly' or (len(pts) > 2 and pts[0] == pts[-1]):
                    path.closeSubpath()
                
                item = self.scene.addPath(path, pen)
                item.setZValue(100)
        elif l_type == 'circle' and 'pos' in link and 'radius' in link:
            r = link['radius']
            px, py = link['pos']
            item = self.scene.addEllipse(px-r, py-r, r*2, r*2, pen)
            item.setZValue(100)
            
        if item:
            self.beam_visuals.append(item)
            margin = 300
            rect = item.sceneBoundingRect()
            self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.KeepAspectRatio)
            self.centerOn(rect.center())

    def highlight_element_by_name(self, name, data_list=[]):
        """Destaca itens vinculados em VERMELHO. Se for Pilar, destaca formato."""
        from PySide6.QtWidgets import QGraphicsSimpleTextItem
        from PySide6.QtGui import QPainterPath
        
        self.clear_beams() 
        pen = QPen(QColor(255, 0, 0), 3) 
        pen.setCosmetic(True)
        
        target = next((d for d in data_list if d.get('name') == name), None)
        items_to_focus = []

        if target:
            # Caso especial: Pilar destaca contorno real
            if target.get('type') == 'Pilar' and 'points' in target:
                path = QPainterPath()
                pts = target['points']
                path.moveTo(pts[0][0], pts[0][1])
                for p in pts[1:]: path.lineTo(p[0], p[1])
                path.closeSubpath()
                item = self.scene.addPath(path, pen)
                item.setZValue(100)
                self.beam_visuals.append(item)
                items_to_focus.append(item)

            # Vínculos Genéricos salvos (LinkManager)
            links = target.get('links', {})
            for field_id, slots in links.items():
                # slots pode ser uma lista (legado) ou um dicionário de slots
                slots_to_process = slots.values() if isinstance(slots, dict) else [slots]
                
                for link_list in slots_to_process:
                    for link in link_list:
                        if link.get('type') == 'text':
                            t_item = self.scene.addSimpleText(link['text'])
                            t_item.setPos(link.get('pos', [0, 0])[0], link.get('pos', [0, 0])[1])
                            t_item.setBrush(QBrush(QColor(255, 0, 0)))
                            t_item.setZValue(101)
                            t_item.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations)
                            self.beam_visuals.append(t_item)
                            items_to_focus.append(t_item)
                        elif link.get('type') == 'line' and 'points' in link:
                            pts = link['points']
                            line = self.scene.addLine(pts[0][0], pts[0][1], pts[1][0], pts[1][1], pen)
                            line.setZValue(100)
                            self.beam_visuals.append(line)
                            items_to_focus.append(line)

            geo = target.get('geometry', {})
            for points in geo.get('lines', []):
                path = QPainterPath()
                path.moveTo(points[0][0], points[0][1])
                for p in points[1:]: path.lineTo(p[0], p[1])
                item = self.scene.addPath(path, pen)
                item.setZValue(100)
                self.beam_visuals.append(item)
                items_to_focus.append(item)
                
            for txt in geo.get('texts', []):
                t_item = self.scene.addSimpleText(txt['text'])
                t_item.setPos(txt['pos'][0], txt['pos'][1])
                t_item.setBrush(QBrush(QColor(255, 0, 0)))
                t_item.setZValue(101)
                t_item.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations)
                self.beam_visuals.append(t_item)
                items_to_focus.append(t_item)

        # Fallback para textos soltos do DXF
        for ent in self.dxf_entities:
            if ent.get('text') == name:
                t_item = self.scene.addSimpleText(ent['text'])
                t_item.setPos(ent['pos'][0], ent['pos'][1])
                t_item.setBrush(QBrush(QColor(255, 0, 0)))
                t_item.setZValue(101)
                t_item.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations)
                self.beam_visuals.append(t_item)
                items_to_focus.append(t_item)

        if items_to_focus:
            from PySide6.QtCore import QRectF
            rect = items_to_focus[0].sceneBoundingRect()
            for item in items_to_focus[1:]:
                rect = rect.united(item.sceneBoundingRect())
            
            # Zoom suave no conjunto de itens destacados
            margin = 500
            self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.KeepAspectRatio)
            self.centerOn(rect.center())

    def focus_on_item(self, item_id: int):
        """Centraliza e destaca um item"""
        if item_id in self.interactive_items:
            item = self.interactive_items[item_id]
            self.centerOn(item)
            # Zoom suave no pilar
            self.fitInView(item.boundingRect().marginsAdded(QMarginsF(300, 300, 300, 300)), Qt.KeepAspectRatio)
            
    def on_pillar_clicked(self, p_id):
        # Deselecionar outros
        for item_id, item in self.interactive_items.items():
            if item_id != p_id:
                item.setSelected(False)
            else:
                item.setSelected(True)
        self.pillar_selected.emit(p_id)

    def update_pillar_status(self, p_id: int, status: str):
        """Atualiza o estado visual de um pilar."""
        if p_id in self.interactive_items:
            item = self.interactive_items[p_id]
            item.set_validated(status == 'validated')

    def set_picking_mode(self, mode, field_id=""):
        self.picking_mode = mode
        self.pick_start = None
        
        # Reset Poly
        self.pick_poly_points = []
        if self.poly_visual:
            self.scene.removeItem(self.poly_visual)
            self.poly_visual = None

        if mode:
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)
            
            if mode == 'text':
                msg = "CLIQUE NO TEXTO EXATO"
            elif mode == 'poly':
                msg = "CLIQUE PONTO-A-PONTO. [ENTER] PARA FINALIZAR."
            else:
                msg = "MÉTODO 2-CLIQUES (USE SNAP)"

            self.instruction_label.setText(f"<b>Modo Curadoria Ativo</b><br>Campo: {field_id}<br><small>{msg}</small>")
            self.instruction_label.adjustSize()
            self.instruction_label.show()
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(Qt.ArrowCursor)
            self.instruction_label.hide()
            # Hide all markers
            for m in self.snap_markers.values(): m.hide()

    def get_snap(self, pos, threshold=40):
        """Retorna o dado de snap mais próximo {pos, type} ou None"""
        best_snap = None
        min_dist = threshold
        
        # Prioridade: Intersection (0) > Endpoint/Center (1) > Midpoint (2)
        priority_map = {
            'intersection': 0,
            'endpoint': 1, 'center': 1, 'quadrant': 1,
            'midpoint': 2
        }
        
        for s in self.snap_points:
            pt = s['pos']
            dist = ((pt[0]-pos.x())**2 + (pt[1]-pos.y())**2)**0.5
            
            if dist < min_dist:
                # Se for melhor distância, pega. Se for similar, checa prioridade.
                if best_snap and abs(dist - min_dist) < 2.0:
                    curr_prio = priority_map.get(s['type'], 99)
                    best_prio = priority_map.get(best_snap['type'], 99)
                    if curr_prio < best_prio:
                        best_snap = s
                        min_dist = dist
                else:
                    min_dist = dist
                    best_snap = s
                    
        return best_snap

    def mousePressEvent(self, event):
        # 1. Handle Pan (Middle Button)
        if event.button() == Qt.MiddleButton:
            self._is_panning = True
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        scene_pos = self.mapToScene(event.pos())
        snap_data = self.get_snap(scene_pos)
        snap_pos = snap_data['pos'] if snap_data else (scene_pos.x(), scene_pos.y())
        
        # 2. Handle Pick Modes
        if self.picking_mode == 'poly':
            from PySide6.QtGui import QPainterPath
            self.pick_poly_points.append(snap_pos)
            
            # Update Visual
            path = QPainterPath()
            if self.pick_poly_points:
                path.moveTo(*self.pick_poly_points[0])
                for p in self.pick_poly_points[1:]:
                    path.lineTo(*p)
            
            if not self.poly_visual:
                self.poly_visual = self.scene.addPath(path, QPen(QColor(0, 255, 255), 2, Qt.DashLine))
                self.poly_visual.setZValue(205)
            else:
                self.poly_visual.setPath(path)
            return

        if self.picking_mode == 'text':
            # Buscar texto mais próximo
            best_text = None
            min_dist = 60.0 # Raio de clique para texto
            for ent in self.dxf_entities:
                if 'text' in ent:
                    p = ent['pos']
                    dist = ((p[0]-scene_pos.x())**2 + (p[1]-scene_pos.y())**2)**0.5
                    if dist < min_dist:
                        min_dist = dist
                        best_text = ent
            
            if best_text:
                self.pick_completed.emit({
                    'text': best_text['text'], 
                    'type': 'text',
                    'pos': best_text['pos']
                })
                self.set_picking_mode(None)
                return

        elif self.picking_mode == 'geometry':
            # ... (código existente de geometry search - simplificado aqui para brevidade se não mudou)
            # Como geometry mode não depende estritamente do OSNAP para selecionar OBJETO, mantemos a busca por proximidade
            best_ent = None
            min_dist = 40.0 
            
            for ent in self.dxf_entities:
                dist = 99999.0
                if 'pos' in ent and 'text' in ent: # Texto
                    p = ent['pos']
                    dist = ((p[0]-scene_pos.x())**2 + (p[1]-scene_pos.y())**2)**0.5
                elif 'points' in ent: # Linha ou Poly
                    # Distância ao ponto mais próximo da poly (simplificado: aos vértices)
                    for p in ent['points']:
                        d = ((p[0]-scene_pos.x())**2 + (p[1]-scene_pos.y())**2)**0.5
                        if d < dist: dist = d
                elif 'radius' in ent and 'pos' in ent: # Circulo
                    p = ent['pos']
                    d_center = ((p[0]-scene_pos.x())**2 + (p[1]-scene_pos.y())**2)**0.5
                    dist = abs(d_center - ent['radius']) 
                
                if dist < min_dist:
                    min_dist = dist
                    best_ent = ent
            
            if best_ent:
                res = {
                    'type': best_ent.get('type', 'geometry'),
                    'text': best_ent.get('text', 'Entidade CAD'),
                    'pos': best_ent.get('pos'),
                    'points': best_ent.get('points'),
                    'radius': best_ent.get('radius')
                }
                self.pick_completed.emit(res)
                self.set_picking_mode(None)
                return
                
        elif self.picking_mode == 'line':
            if self.pick_start is None:
                # Primeiro clique
                from PySide6.QtCore import QPointF
                self.pick_start = QPointF(*snap_pos)
                self.temp_line = self.scene.addLine(snap_pos[0], snap_pos[1], snap_pos[0], snap_pos[1],
                                               QPen(QColor(0, 255, 255), 2, Qt.DashLine))
                self.temp_text = self.scene.addSimpleText("0.0")
                self.temp_text.setBrush(QBrush(QColor(0, 255, 255)))
                self.temp_text.setZValue(201)
                self.temp_line.setZValue(201)
                self.temp_text.setFlag(QGraphicsSimpleTextItem.ItemIgnoresTransformations)
            else:
                # Segundo clique - Finalizar
                dist = ((self.pick_start.x()-snap_pos[0])**2 + (self.pick_start.y()-snap_pos[1])**2)**0.5
                
                # Overlay Permanente
                overlay_line = self.scene.addLine(self.pick_start.x(), self.pick_start.y(), 
                                                snap_pos[0], snap_pos[1],
                                                QPen(QColor(255, 0, 0), 2))
                cota_text = self.scene.addSimpleText(f"{dist:.1f}")
                cota_text.setPos(snap_pos[0], snap_pos[1])
                cota_text.setBrush(QBrush(QColor(255, 0, 0)))
                cota_text.setZValue(101)
                cota_text.setFlag(QGraphicsItem.ItemIgnoresTransformations)
                
                self.overlay_items.extend([overlay_line, cota_text])
                
                self.pick_completed.emit({
                    'text': f"{dist:.1f}", 
                    'type': 'line',
                    'points': [(self.pick_start.x(), self.pick_start.y()), (snap_pos[0], snap_pos[1])]
                })
                
                # Cleanup
                if self.temp_line: self.scene.removeItem(self.temp_line)
                if self.temp_text: self.scene.removeItem(self.temp_text)
                self.temp_line = None
                self.temp_text = None
                self.pick_start = None
                self.set_picking_mode(None)
            return
            
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 1. Handle Pan
        if self._is_panning and self._last_pan_pos:
            delta = event.pos() - self._last_pan_pos
            self._last_pan_pos = event.pos()
            
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            event.accept()
            return

        scene_pos = self.mapToScene(event.pos())
        snap_data = self.get_snap(scene_pos)
        
        # OSNAP Visual
        if self.picking_mode:
            # Hide all first
            for m in self.snap_markers.values(): m.hide()
            
            if snap_data:
                stype = snap_data['type']
                spos = snap_data['pos']
                
                # Fallback para endpoint se marker não existir
                marker = self.snap_markers.get(stype, self.snap_markers.get('endpoint'))
                
                if marker:
                    marker.setPos(spos[0], spos[1])
                    marker.show()
        
        snap_pos = snap_data['pos'] if snap_data else (scene_pos.x(), scene_pos.y())

        # Preview Polyline
        if self.picking_mode == 'poly' and self.pick_poly_points:
            from PySide6.QtGui import QPainterPath
            path = QPainterPath()
            path.moveTo(*self.pick_poly_points[0])
            for p in self.pick_poly_points[1:]:
                path.lineTo(*p)
            path.lineTo(*snap_pos) # Rubber band to cursor
            
            if not self.poly_visual:
                 self.poly_visual = self.scene.addPath(path, QPen(QColor(0, 255, 255), 2, Qt.DashLine))
                 self.poly_visual.setZValue(205)
            else:
                 self.poly_visual.setPath(path)

        # Preview da Linha
        if self.picking_mode == 'line' and self.pick_start:
            target = snap_pos
            self.temp_line.setLine(self.pick_start.x(), self.pick_start.y(), target[0], target[1])
            
            dist = ((self.pick_start.x()-target[0])**2 + (self.pick_start.y()-target[1])**2)**0.5
            self.temp_text.setText(f"{dist:.1f}")
            self.temp_text.setPos(target[0], target[1])
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._is_panning = False
            self.setCursor(Qt.CrossCursor if self.picking_mode else Qt.ArrowCursor)
            event.accept()
            return
            
        # Desabilitado release para usar o 2-cliques system
        if not self.picking_mode:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self.picking_mode == 'poly' and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if len(self.pick_poly_points) >= 2:
                # Finalizar Poly
                poly_data = {
                    'text': 'Polyline',
                    'type': 'poly',
                    'points': self.pick_poly_points
                }
                
                # Desenha visual permanente rápido
                from PySide6.QtGui import QPolygonF, QPainterPath
                from PySide6.QtCore import QPointF
                
                # Visual Overlay (Closed Polygon or Open Path?)
                # User said "Area", so Polygon usually. But "beam bottom" might be path.
                # Let's check: if > 2 points and start~end, close it?
                # For now just draw the path/polygon as overlay.
                path = QPainterPath()
                path.moveTo(*self.pick_poly_points[0])
                for p in self.pick_poly_points[1:]: path.lineTo(*p)
                path.closeSubpath() # Assume area? Or maybe user wants open?
                # User: "desenhar a area da laje". Areas are closed.
                
                item = self.scene.addPath(path, QPen(QColor(255, 0, 0), 2), QBrush(QColor(255, 0, 0, 50)))
                self.overlay_items.append(item)

                self.pick_completed.emit(poly_data)
                self.set_picking_mode(None)
                
        super().keyPressEvent(event)
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            scale = zoom_in_factor
        else:
            scale = zoom_out_factor

        self.scale(scale, scale)
