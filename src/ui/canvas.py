from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsSimpleTextItem, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QInputDialog, QLineEdit, QGraphicsLineItem, QGraphicsPathItem, QStyle, QStyleOptionGraphicsItem
from PySide6.QtCore import Qt, Signal, QMarginsF, QRectF, QPointF, QLineF
from PySide6.QtGui import QPainter, QWheelEvent, QTransform, QPen, QColor, QBrush, QPainterPath, QFont, QCursor
from src.ui.overlays import PillarGraphicsItem, SlabGraphicsItem
from src.ui.overlays_beams import BeamGraphicsItem
import math

class DXFLineItem(QGraphicsLineItem):
    """Custom Line Item that disables default selection dashed line"""
    def paint(self, painter, option, widget=None):
        # Disable default selection look (dashed box)
        option.state &= ~QStyle.State_Selected
        if self.isSelected():
            # Forçar pen de destaque se selecionado (backup do setPen)
            painter.setPen(self.pen()) 
        super().paint(painter, option, widget)

class DXFPathItem(QGraphicsPathItem):
    """Custom Path Item that disables default selection dashed line"""
    def paint(self, painter, option, widget=None):
        # Disable default selection look (dashed box)
        option.state &= ~QStyle.State_Selected
        super().paint(painter, option, widget)

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
        self.setBackgroundBrush(QColor(40, 40, 40)) # Dark Gray (não preto absoluto)
        
        # Estado
        self.interactive_items = {} # Map ID -> GraphicItem (Generic)
        self.item_groups = { # Store lists for bulk visibility toggling
            'pillar': [],
            'slab': [],
            'beam': [],
            'link': [] # Visual links (texts/lines)
        }
        self.beam_visuals = []      
        
        # Modo de Captação e Edição
        self.picking_mode = None    # 'text' | 'line'
        self.edit_mode = None       # 'select', 'line', 'text', 'circle', 'dim', 'move'
        self.pick_start = None
        self.dxf_entities = []
        self.snap_points = []       # Armazena todos os vértices para OSNAP
        self.snap_segments = []     # Armazena linhas para OSNAP dinâmico (nearest, perp)
        self.osnap_modes = ['endpoint', 'midpoint', 'center', 'intersection', 'nearest', 'perpendicular', 'extension', 'node']
        self.overlay_items = []     # Itens persistentes de vínculo
        self.temp_line = None
        self.temp_text = None
        self.temp_item = None
        self.snap_markers = {}      # Dicionário para marcadores {type: item}
        self.instruction_label = None # Mensagem de UX no topo
        
        # Edit State
        self.selected_items = []
        self.keyboard_buffer = ""
        self.input_label = None
        self.is_moving = False
        self._last_mouse_pos = QPointF()
        self.ortho_mode = False     # Restringe a 0, 90, 180, 270 graus
        self.selection_box = None   # Item visual do box de seleção
        self.box_start = None       # Ponto inicial do box (cena)
        self.deselect_box_start = None # Right click deselect box start (scene)
        self.deselect_box = None    # Right click visual box

        # Opções de Interação
        self.setMouseTracking(True)
        self._is_panning = False
        self._last_pan_pos = None

        # Polyline Picking State
        self.pick_poly_points = []
        self.poly_visual = None  # QGraphicsPathItem
        self.active_isolation = None # Current isolated item ID

        self._init_osnap_markers()
        self._init_instruction_overlay()
        self._init_cad_toolbar()
        self._init_input_overlay()
        
        # Conectar sinal de mudanca de selecao para realce visual
        self.scene.selectionChanged.connect(self._on_selection_changed)
    
    # Restoring imports and helper methods that might have been lost or displaced
    def _on_selection_changed(self):
        selected = self.scene.selectedItems()
        print(f"DEBUG: selectionChanged! Total selected in scene: {len(selected)}")
        
        # 1. Resetar itens que não estão mais selecionados (baseado na nossa tag _orig_pen)
        # Iteramos apenas os itens que temos certeza que alteramos no passado ou que estão na cena
        # Para ser robusto, limpamos o que não estiver no 'selected'
        for item in self.scene.items():
            if hasattr(item, '_orig_pen') and not item.isSelected():
                item.setPen(item._orig_pen)
                item.setZValue(item._orig_z)
                del item._orig_pen
                del item._orig_z
                item.update()

        # 2. Aplicar destaque nos selecionados
        for item in selected:
            # Ignorar itens complexos (pilares/lajes) que já tem seu próprio visual
            if hasattr(item, 'pillar_id') or isinstance(item, (PillarGraphicsItem, SlabGraphicsItem, BeamGraphicsItem)):
                continue
            
            if hasattr(item, 'setPen'):
                if not hasattr(item, '_orig_pen'):
                    item._orig_pen = item.pen()
                    item._orig_z = item.zValue()
                
                # Highlight VERMELHO MUITO GROSSO (10px) e COSMÉTICO (não muda com zoom)
                high_pen = QPen(QColor(255, 0, 0), 10, Qt.SolidLine)
                high_pen.setCosmetic(True)
                item.setPen(high_pen)
                item.setZValue(1999) # Quase no topo (abaixo apenas da toolbar/overlays de UI)
                item.update()

    def _init_input_overlay(self):
        self.input_label = QLabel(self)
        self.input_label.setStyleSheet("""
            background: rgba(20, 20, 20, 220); 
            color: #00ff00; 
            border: 1px solid #00ff00;
            padding: 8px; border-radius: 4px; 
            font-size: 14px;
            font-weight: bold; font-family: 'Consolas', monospace;
        """)
        self.input_label.hide()
        self.input_label.move(10, self.height() - 50)

    def _init_cad_toolbar(self):
        """Cria barra de ferramentas superior (Header) horizontal"""
        self.toolbar = QWidget(self)
        self.toolbar.setObjectName("CADToolbar")
        # Estilo Header: Glassmorphism horizontal no topo
        self.toolbar.setStyleSheet("""
            QWidget#CADToolbar {
                background: rgba(35, 35, 35, 240);
                border-bottom: 2px solid rgba(160, 112, 255, 100);
                border-radius: 0px;
            }
            QPushButton {
                background: rgba(60, 60, 60, 180);
                border: 1px solid #444;
                border-radius: 4px;
                color: #ddd;
                font-family: 'Segoe UI', Arial;
                font-size: 10px;
                text-align: center;
                padding: 2px;
            }
            QPushButton:hover {
                background: rgba(100, 100, 100, 255);
                border: 1px solid #777;
                color: white;
            }
            QPushButton[active="true"] {
                background: rgba(100, 50, 200, 220);
                border: 1px solid #a070ff;
                color: white;
                font-weight: bold;
            }
        """)
        
        layout = QHBoxLayout(self.toolbar)
        layout.setContentsMargins(15, 4, 15, 4)
        layout.setSpacing(10)

        self.tool_buttons = {}
        tools = [
            ("🖱️ SELECT", "select", "Selecionar (ESC)"),
            ("📏 LINHA", "line", "Linha (L)"),
            ("⭕ CIRC", "circle", "Círculo (C)"),
            ("📝 TEXTO", "text", "Texto (T)"),
            ("📐 COTA", "dim", "Cota (D)"),
            ("↔️ MOVER", "move", "Mover (M)"),
            ("🗑️ EXCLUIR", "delete", "Excluir (DEL)"),
            ("⚓ ORTHO", "ortho", "Alternar Ortho (F8)")
        ]

        for label, mode, tooltip in tools:
            btn = QPushButton(label)
            btn.setFixedSize(85, 32)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.PointingHandCursor)
            
            if mode == "delete":
                btn.clicked.connect(self._delete_selection)
                btn.setStyleSheet("QPushButton:hover { background: rgba(220, 50, 50, 255); border: 1px solid #ff4444; }")
            elif mode == "ortho":
                btn.clicked.connect(self.toggle_ortho)
                self.tool_buttons[mode] = btn
            else:
                btn.clicked.connect(lambda checked=False, m=mode: self.set_edit_mode(m))
                self.tool_buttons[mode] = btn
                
            layout.addWidget(btn)
        
        # Modo inicial
        self.set_edit_mode('select')

        # Ajuste inicial de posição e tamanho
        self.toolbar.setGeometry(0, 0, self.width(), 42)

    def toggle_ortho(self):
        """Liga/Desliga modo ortogonal"""
        self.ortho_mode = not self.ortho_mode
        if "ortho" in self.tool_buttons:
            btn = self.tool_buttons["ortho"]
            btn.setProperty("active", self.ortho_mode)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.log(f"Ortho Mode: {'ON' if self.ortho_mode else 'OFF'}")

    def set_edit_mode(self, mode):
        """Define o modo de edição atual"""
        # Se clicar no botão que já está ativo, volta para select (exceto no delete/ortho que são ações)
        if mode == self.edit_mode and mode != 'select':
            mode = 'select'

        self.edit_mode = mode
        self.set_picking_mode(None) 
        
        # Reset de estados de clique
        self.pick_start = None
        self.box_start = None
        self.is_moving = False
        if self.selection_box:
            self.scene.removeItem(self.selection_box)
            self.selection_box = None

        # Atualiza o estado visual dos botões
        for m, btn in self.tool_buttons.items():
            is_active = (m == mode) or (m == "ortho" and self.ortho_mode)
            btn.setProperty("active", is_active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        
        if mode and mode != 'select':
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)
            self.instruction_label.setText(f"<b>Ferramenta Ativa: {mode.upper()}</b>")
            self.instruction_label.show()
        else:
            # Select mode (default)
            self.edit_mode = 'select'
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(Qt.ArrowCursor)
            self.instruction_label.hide()
            if self.temp_item: 
                try: self.scene.removeItem(self.temp_item)
                except: pass
                self.temp_item = None

    def _delete_selection(self):
        """Remove itens selecionados"""
        for item in self.selected_items:
            try:
                self.scene.removeItem(item)
                if item in self.overlay_items: self.overlay_items.remove(item)
                # Também remover de beam_visuals se for o caso
                if item in self.beam_visuals: self.beam_visuals.remove(item)
            except: pass
        self.selected_items.clear()
        self.log("🗑️ Itens excluídos.")
        self.update() # Forçar repaint

    def log(self, msg):
        # Acessar MainWindow log se possível via parent
        curr = self.parent()
        while curr:
            if hasattr(curr, 'log'):
                curr.log(msg)
                return
            curr = curr.parent()
        print(f"Canvas: {msg}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'toolbar'):
            self.toolbar.setGeometry(0, 0, self.width(), 42)
        if hasattr(self, 'input_label'):
            self.input_label.move(10, self.height() - 50)

    def set_category_visibility(self, category_to_show, show_links=True):
        """Alterna visibilidade: 'pillar', 'slab', 'beam', 'all'"""
        self.active_isolation = None
        
        # Helper to toggle list
        def toggle_list(key, visible):
            stale_items = []
            for item in self.item_groups.get(key, []):
                try:
                    if visible: item.show()
                    else: item.hide()
                except RuntimeError:
                    # Objeto C++ já deletado
                    stale_items.append(item)
            
            # Limpar referências mortas
            for si in stale_items:
                if si in self.item_groups.get(key, []):
                    self.item_groups[key].remove(si)
                
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
        self.active_isolation = None
        
        # Hide all first
        self.set_category_visibility('none')
        
        # Show specific item
        if item_id in self.interactive_items:
            item = self.interactive_items[item_id]
            item.show()
            
            # Zoom to it with consistent margin
            rect = item.sceneBoundingRect()
            margin = 500
            self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.KeepAspectRatio)
            self.centerOn(rect.center())
            
    def clear_interactive(self):
        """Limpa apenas os itens de overlay interativo, mantendo o background DXF"""
        # Se estivermos usando cenas separadas por projeto, o scene.clear() já limpou tudo.
        # Mas mantemos aqui para compatibilidade com fluxos manuais.
        for item in self.interactive_items.values():
            try:
                if self.scene and item:
                    self.scene.removeItem(item)
            except (RuntimeError, Exception):
                pass 
        
        self.interactive_items.clear()
        for k in self.item_groups: self.item_groups[k] = []
        self.clear_beams()
        self.clear_overlay()

    def swap_project_state(self, project_data):
        """
        Troca instantaneamente o estado visual do canvas para um novo projeto.
        Garante isolamento total de cenas, coleções e auxiliares (Snap/Overlay).
        """
        # 1. Se o projeto não tem cena PRÓPRIA, criamos uma NOVA.
        if 'scene' not in project_data or project_data['scene'] is None:
             project_data['scene'] = QGraphicsScene(self)
             project_data['scene'].setBackgroundBrush(QColor(40, 40, 40))
             
             # Resetar coleções vinculadas a esta nova cena
             project_data['canvas_interactive_items'] = {}
             project_data['canvas_item_groups'] = {k: [] for k in ['pillar', 'slab', 'beam', 'link']}
             project_data['canvas_snap_points'] = []
             project_data['canvas_beam_visuals'] = []
             project_data['snap_markers'] = {}
             project_data['instruction_text'] = None
             project_data['scene_rendered'] = False 
        
        # 2. Trocar a cena no View
        self.scene = project_data['scene']
        self.setScene(self.scene)
        
        # RECONECTAR SINAL DE SELEÇÃO (Essencial!)
        try:
            self.scene.selectionChanged.disconnect(self._on_selection_changed)
        except:
            pass
        self.scene.selectionChanged.connect(self._on_selection_changed)
        
        # 3. Restaurar ponteiros de coleções e auxiliares para o projeto ativo
        self.interactive_items = project_data['canvas_interactive_items']
        self.item_groups = project_data['canvas_item_groups']
        self.snap_points = project_data['canvas_snap_points']
        self.beam_visuals = project_data['canvas_beam_visuals']
        self.snap_markers = project_data['snap_markers']
        self.instruction_text = project_data.get('instruction_text') # Pode ser None
        
        # Se a cena já foi renderizada mas faltam auxiliares, regeneramos no contexto correto
        if not self.snap_markers and project_data.get('scene_rendered'):
             self._init_osnap_markers()
        if not self.instruction_text and project_data.get('scene_rendered'):
             self._init_instruction_overlay()
             project_data['instruction_text'] = self.instruction_text
        
        # Forçar refresh visual
        self.viewport().update()

    def get_project_state_dict(self):
        """Retorna o estado visual atual para ser guardado no cache do projeto."""
        return {
            'scene': self.scene,
            'canvas_interactive_items': self.interactive_items,
            'canvas_item_groups': self.item_groups,
            'canvas_snap_points': self.snap_points,
            'canvas_beam_visuals': self.beam_visuals,
            'snap_markers': self.snap_markers,
            'instruction_text': self.instruction_text
        }

    def clear_beams(self):
        """Limpa os fios de viga (conflitos)"""
        for item in self.beam_visuals:
            try:
                if self.scene and item:
                    self.scene.removeItem(item)
            except:
                pass
        self.beam_visuals.clear()

    def clear_overlay(self):
        """Limpa itens persistentes de vínculo (linhas/retângulos de picking)"""
        for item in self.overlay_items:
            try:
                if self.scene and item:
                    self.scene.removeItem(item)
            except:
                pass
        self.overlay_items.clear()
        
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
        
    def _line_intersection(self, p1, p2, p3, p4, segment_only=True):
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        x4, y4 = p4
        
        denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
        if denom == 0: return None  # Paralelas
        
        ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
        ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom
        
        if segment_only:
            if 0 <= ua <= 1 and 0 <= ub <= 1:
                return (x1 + ua * (x2 - x1), y1 + ua * (y2 - y1))
        else:
            return (x1 + ua * (x2 - x1), y1 + ua * (y2 - y1))
        return None

        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                l1 = lines[i]
                l2 = lines[j]
                
                # Bounding box check rápido
                minx1, maxx1 = min(l1['start'][0], l1['end'][0]), max(l1['start'][0], l1['end'][0])
                minx2, maxx2 = min(l2['start'][0], l2['end'][0]), max(l2['start'][0], l2['end'][0])
                if maxx1 < minx2 or maxx2 < minx1: continue
                
                pt = self._line_intersection(l1['start'], l1['end'], l2['start'], l2['end'])
                if pt:
                    self._add_snap_point(pt, 'intersection')

    def add_dxf_entities(self, entities, progress_callback=None):
        """Renderiza geometria base (linhas, textos, etc) do DXF"""
        self.scene.clear()
        self.snap_markers = {} # Reset markers
        self.interactive_items = {}
        for k in self.item_groups: self.item_groups[k] = [] # Reset groups
        self.beam_visuals = []
        self.snap_points = []
        self.snap_segments = []
        
        # Consolidar todas as entidades para busca/picking
        self.dxf_entities = entities.get('texts', []).copy()
        for l in entities.get('lines', []):
            ent = l.copy()
            ent['points'] = [l['start'], l['end']] # Compatibilidade com busca de poly
            self.dxf_entities.append(ent)
        self.dxf_entities.extend(entities.get('polylines', []))
        self.dxf_entities.extend(entities.get('circles', []))
        
        total_steps = len(entities.get('lines', [])) + len(entities.get('polylines', [])) + \
                      len(entities.get('texts', [])) + len(entities.get('circles', []))
        current_step = 0

        def update_prog():
            nonlocal current_step
            current_step += 1
            if progress_callback and current_step % 50 == 0:
                progress_callback(int((current_step / total_steps) * 100))
        
        # Helper para criar Pen a partir de cor DXF
        def get_pen(color_tuple, width=1):
            pen = QPen(QColor(*color_tuple), width)
            pen.setCosmetic(True)
            return pen

        # Armazena linhas para cálculo de interseção
        calc_lines = []

        # Draw Circles and Arcs
        for circ in entities.get('circles', []):
            center = circ.get('center', circ.get('pos', (0,0)))
            cx, cy = center
            r = circ['radius']
            self._add_snap_point((cx, cy), 'center')
            self._add_snap_point((cx+r, cy), 'quadrant')
            self._add_snap_point((cx-r, cy), 'quadrant')
            self._add_snap_point((cx, cy+r), 'quadrant')
            self._add_snap_point((cx, cy-r), 'quadrant')

            if 'start_angle' in circ: # ARC
                path = QPainterPath()
                path.arcMoveTo(cx - r, cy - r, r * 2, r * 2, circ['start_angle'])
                path.arcTo(cx - r, cy - r, r * 2, r * 2, circ['start_angle'], circ['end_angle'] - circ['start_angle'])
                item = DXFPathItem(path)
                item.setPen(get_pen(circ['color']))
                self.scene.addItem(item)
            else: # CIRCLE
                from PySide6.QtWidgets import QGraphicsEllipseItem
                item = self.scene.addEllipse(cx - r, cy - r, r * 2, r * 2, get_pen(circ['color']))
                # Circle default selection style is box, user complained about lines/polylines. 
                # If circles also need custom highlight, we need DXFEllipseItem. 
                # For now applying to lines/polylines as requested.
                
            item.setFlag(QGraphicsItem.ItemIsSelectable)
            update_prog()

        # Draw Lines
        for line in entities.get('lines', []):
            s, e = line['start'], line['end']
            item = DXFLineItem(s[0], s[1], e[0], e[1])
            item.setPen(get_pen(line['color']))
            self.scene.addItem(item)
            item.setFlag(QGraphicsItem.ItemIsSelectable) 
            self.snap_segments.append((s, e))
            calc_lines.append(line)
            
            # Midpoint
            mid = ((s[0]+e[0])/2, (s[1]+e[1])/2)
            self._add_snap_point(mid, 'midpoint')
            self._add_snap_point(s, 'endpoint')
            self._add_snap_point(e, 'endpoint')
            update_prog()

        # Draw Polylines
        
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
                self.snap_segments.append((p_prev, p_curr))
                mid = ((p_prev[0]+p_curr[0])/2, (p_prev[1]+p_curr[1])/2)
                self._add_snap_point(mid, 'midpoint')
                self._add_snap_point(p_curr, 'endpoint')
            
            if poly.get('is_closed'):
                path.closeSubpath()
                p_last = points[-1]
                p_first = points[0]
                self.snap_segments.append((p_last, p_first))
                calc_lines.append({'start': p_last, 'end': p_first})
                mid = ((p_last[0]+p_first[0])/2, (p_last[1]+p_first[1])/2)
                self._add_snap_point(mid, 'midpoint')
            
            item = DXFPathItem(path)
            item.setPen(get_pen(poly['color']))
            self.scene.addItem(item)
            item.setFlag(QGraphicsItem.ItemIsSelectable) 
            update_prog()

        # Calcular Interseções (Otimização: Ignorar se houver muitos elementos)
        if len(calc_lines) < 1000:
            self._calculate_intersections(calc_lines)
        else:
            print(f"Skipping intersection calculation for {len(calc_lines)} lines (Performance protection).")

        # Draw Texts
        from PySide6.QtWidgets import QGraphicsSimpleTextItem
        from PySide6.QtGui import QFont
        
        for txt in entities.get('texts', []):
            content = txt['text']
            
            # --- CUSTOM OFFSET LOGIC (Parafuso 25/75) ---
            # User req: Shift from 20cm to 30cm (approx +10 relative if existing is base)
            # Assumption: "parafuso 25" e "parafuso 75" mapping to P25/P75 text
            pos_x, pos_y = txt['pos']
            if "P25" in content or "P75" in content: # Adjusted per analysis
                 # Assuming the user meant these specific labels
                 # Adding 10 units to X to shift from theoretical 20 to 30
                 pos_x += 10.0 
            
            item = QGraphicsSimpleTextItem(content)
            item.setPos(pos_x, pos_y)
            item.setBrush(QColor(*txt['color']))
            f = QFont("Arial")
            f.setPointSizeF(8)
            item.setFont(f)
            item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
            item.setFlag(QGraphicsItem.ItemIsSelectable)
            self.scene.addItem(item)
            self._add_snap_point((pos_x, pos_y), 'node')
            update_prog()
            
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
        for c in entities.get('circles', []):
            center = c.get('center', c.get('pos'))
            if center: pts.append(center)
            
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
        
        # Node: Círculo Verde com X
        node_path = QPainterPath()
        node_path.addEllipse(-4, -4, 8, 8)
        node_path.moveTo(-3, -3); node_path.lineTo(3, 3)
        node_path.moveTo(3, -3); node_path.lineTo(-3, 3)
        node = self.scene.addPath(node_path, QPen(QColor(0, 255, 0), 1))
        node.setZValue(200); node.hide(); node.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.snap_markers['node'] = node

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

        # Nearest: Ampulheta/X (Ampulheta simplificada)
        path = QPainterPath()
        path.moveTo(-4, -4); path.lineTo(4, 4); path.lineTo(-4, 4); path.lineTo(4, -4); path.closeSubpath()
        near = self.scene.addPath(path, QPen(QColor(0, 255, 0), 1))
        near.setZValue(200); near.hide(); near.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.snap_markers['nearest'] = near

        # Perpendicular: Símbolo de ângulo reto
        path = QPainterPath()
        path.moveTo(0, -6); path.lineTo(0, 0); path.lineTo(6, 0)
        perp = self.scene.addPath(path, QPen(QColor(0, 255, 0), 2))
        perp.setZValue(200); perp.hide(); perp.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.snap_markers['perpendicular'] = perp

        # Extension: X tracejado ou pequeno circulo
        ext_path = QPainterPath()
        ext_path.moveTo(-4, 0); ext_path.lineTo(4, 0)
        ext_path.moveTo(0, -4); ext_path.lineTo(0, 4)
        ext = self.scene.addPath(ext_path, QPen(QColor(0, 255, 0), 1, Qt.DashLine))
        ext.setZValue(200); ext.hide(); ext.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.snap_markers['extension'] = ext

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
            try:
                self.interactive_items[p_id].set_visual_status(status, confidence)
            except RuntimeError:
                pass # Item já deletado

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

    def draw_beams(self, beams_data: list):
        """Desenha labels de identificação para todas as vigas"""
        for b_data in beams_data:
            pos = b_data.get('pos')
            if pos:
                text = b_data.get('name', 'V?')
                item = QGraphicsSimpleTextItem(text)
                
                # Estilo: Destaque solicitado (Magenta/Bold)
                font = QFont("Inter", 12, QFont.Bold)
                item.setFont(font)
                item.setBrush(QBrush(QColor(255, 0, 255))) 
                
                # Centralizar levemente sobre o ponto
                item.setPos(pos[0], pos[1])
                item.setZValue(15) # Acima de tudo
                item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
                
                # Tooltip detalhado
                item.setToolTip(f"Viga: {text}\nID: {b_data.get('id_item', '??')}")

                self.scene.addItem(item)
                
                # Registrar no cache de grupo
                if 'id' in b_data:
                    self.interactive_items[b_data['id']] = item
                    self.item_groups['beam'].append(item)

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
        pen = QPen(QColor(255, 0, 0), 4) # Red
        pen.setCosmetic(True)
        
        item = None
        l_type = link.get('type')
        
        if l_type == 'text' and 'pos' in link:
            item = self.scene.addSimpleText(link['text'])
            item.setPos(link['pos'][0], link['pos'][1])
            item.setBrush(QBrush(QColor(255, 0, 0)))
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
                t_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
                self.beam_visuals.append(t_item)
                items_to_focus.append(t_item)

        # Fallback para textos soltos do DXF
        for ent in self.dxf_entities:
            if ent.get('text') == name:
                t_item = self.scene.addSimpleText(ent['text'])
                t_item.setPos(ent['pos'][0], ent['pos'][1])
                t_item.setBrush(QBrush(QColor(255, 0, 0)))
                t_item.setZValue(101)
                t_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
                self.beam_visuals.append(t_item)
                items_to_focus.append(t_item)

        if items_to_focus:
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

    def focus_on_beam_geometry(self, beam_data):
        """Foca na geometria completa de uma viga (linhas + textos)"""
        self.clear_beams() # Limpa destaques anteriores
        items_to_focus = []
        geo = beam_data.get('geometry', {})
        
        # 1. Determinar quais linhas desenhar
        # Prioridade: Vínculos em 'viga_segs' (Side A, B, Bottom)
        # Fallback: Geometria bruta do tracer
        line_sources = []
        links = beam_data.get('links', {})
        v_segs = links.get('viga_segs', {})
        
        if isinstance(v_segs, dict):
            for slot_id, link_list in v_segs.items():
                for lk in link_list:
                    if 'points' in lk:
                        line_sources.append(lk['points'])
        
        # Se não houver vínculos manuais ou auto-populados nos slots, usa a geometria bruta
        # Mas APENAS se o container de slots de viga não existir (fallback p/ itens legados/sem classificação).
        # Se o container existe mas está vazio, respeitamos a vontade do usuário (não desenha nada).
        if not line_sources and 'viga_segs' not in links:
            line_sources = geo.get('lines', [])

        # 2. Adicionar destaques temporários em vermelho (padrão de foco)
        pen = QPen(QColor(255, 0, 0), 4)
        pen.setCosmetic(True)
        
        # Desenhar linhas filtradas (vínculos ativos ou fallback)
        for points in line_sources:
             if len(points) >= 2:
                 path = QPainterPath()
                 path.moveTo(points[0][0], points[0][1])
                 for p in points[1:]: path.lineTo(p[0], p[1])
                 item = self.scene.addPath(path, pen)
                 item.setZValue(100)
                 self.beam_visuals.append(item)
                 items_to_focus.append(item)
        
        # Desenhar textos da viga
        for txt in geo.get('texts', []):
             found_text = txt.get('text', 'V?')
             t_item = self.scene.addSimpleText(found_text)
             t_item.setPos(txt['pos'][0], txt['pos'][1])
             t_item.setBrush(QBrush(QColor(255, 0, 0)))
             t_item.setZValue(101)
             t_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
             self.beam_visuals.append(t_item)
             items_to_focus.append(t_item)

        if items_to_focus:
            rect = items_to_focus[0].sceneBoundingRect()
            for item in items_to_focus[1:]:
                rect = rect.united(item.sceneBoundingRect())
            
            # Zoom suave no conjunto de itens da viga
            margin = 800
            self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.KeepAspectRatio)
            self.centerOn(rect.center())
        # Caso não tenha geometria complexa, tenta focar no label interativo
        elif beam_data.get('id') in self.interactive_items:
            self.focus_on_item(beam_data['id'])
            
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
            if hasattr(item, 'set_validated'):
                item.set_validated(status == 'validated')

    def update_slab_status(self, s_id: int, status: str):
        """Atualiza o estado visual de uma laje."""
        if s_id in self.interactive_items:
            try:
                item = self.interactive_items[s_id]
                if hasattr(item, 'set_validated'):
                    item.set_validated(status == 'validated')
            except RuntimeError:
                pass

    def update_beam_status(self, b_id: int, status: str):
        """Atualiza o estado visual de uma viga (label)."""
        if b_id in self.interactive_items:
            try:
                item = self.interactive_items[b_id]
                if status == 'validated':
                    item.setBrush(QBrush(QColor(76, 175, 80))) # Green
                else:
                    item.setBrush(QBrush(QColor(255, 0, 255))) # Default Magenta
            except RuntimeError:
                pass

    def set_picking_mode(self, mode, field_id=""):
        self.picking_mode = mode
        self.pick_start = None
        if mode: self.edit_mode = None # Cancela modo de edição se entrar em picking
        
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
        elif not self.edit_mode:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setCursor(Qt.ArrowCursor)
            self.instruction_label.hide()
            # Hide all markers
            for m in self.snap_markers.values(): m.hide()

    def get_snap(self, pos, threshold=3):
        """Retorna o dado de snap mais próximo {pos, type} ou None"""
        best_snap = None
        min_dist = threshold
        
        # 1. Checa pontos fixos (endpoint, center, midpoint, intersection, node)
        priority_map = {
            'intersection': 0, 'apparent_intersection': 0,
            'endpoint': 1, 'center': 1, 'quadrant': 1, 'node': 1,
            'midpoint': 2,
            'extension': 3,
            'perpendicular': 4,
            'nearest': 5
        }
        
        for s in self.snap_points:
            pt = s['pos']
            dist = ((pt[0]-pos.x())**2 + (pt[1]-pos.y())**2)**0.5
            
            if dist < min_dist:
                if best_snap and abs(dist - min_dist) < 2.0:
                    curr_prio = priority_map.get(s['type'], 99)
                    best_prio = priority_map.get(best_snap['type'], 99)
                    if curr_prio < best_prio:
                        best_snap = s
                        min_dist = dist
                else:
                    min_dist = dist
                    best_snap = s

        # 2. Snaps Dinâmicos (Nearest, Perpendicular, Apparent Intersection, Extension)
        if best_snap and min_dist < 10: # Se já achamos um ponto fixo muito perto, ignora dinâmico
            return best_snap

        # Encontrar segmentos próximos
        near_segments = []
        for s, e in self.snap_segments:
            px, py = pos.x(), pos.y()
            sx, sy = s[0], s[1]
            ex, ey = e[0], e[1]
            dx, dy = ex - sx, ey - sy
            mag_sq = dx*dx + dy*dy
            if mag_sq == 0: continue
            
            t = ((px - sx) * dx + (py - sy) * dy) / mag_sq
            t_clamped = max(0, min(1, t))
            proj = QPointF(sx + t_clamped * dx, sy + t_clamped * dy)
            dist = ((proj.x()-px)**2 + (proj.y()-py)**2)**0.5
            
            if dist < threshold:
                near_segments.append(((s, e), dist, t, proj))

        # Ordenar por distância
        near_segments.sort(key=lambda x: x[1])

        # Apparent Intersection (entre os 2 mais próximos)
        if len(near_segments) >= 2:
            s1, e1 = near_segments[0][0]
            s2, e2 = near_segments[1][0]
            pt = self._line_intersection(s1, e1, s2, e2, segment_only=False)
            if pt:
                dist_inter = ((pt[0]-pos.x())**2 + (pt[1]-pos.y())**2)**0.5
                if dist_inter < min_dist:
                    best_snap = {'pos': pt, 'type': 'intersection'} # Usa marker de intersection
                    min_dist = dist_inter

        # Perpendicular e Extension
        for seg_data in near_segments:
            (s, e), dist, t, proj = seg_data
            if dist < min_dist:
                # Extension: se t < 0 ou t > 1
                if t < 0 or t > 1:
                     # Se estivermos em modo de desenho, mostra extensão
                     if self.edit_mode in ('line', 'dim'):
                         best_snap = {'pos': (proj.x(), proj.y()), 'type': 'extension'}
                         min_dist = dist
                elif self.pick_start and 0 <= t <= 1:
                    if self.edit_mode in ('line', 'dim'):
                        best_snap = {'pos': (proj.x(), proj.y()), 'type': 'perpendicular'}
                        min_dist = dist
                else:
                    best_snap = {'pos': (proj.x(), proj.y()), 'type': 'nearest'}
                    min_dist = dist

        return best_snap

    def mousePressEvent(self, event):
        # 0. Right Click - Deselect Box or Cancel
        if event.button() == Qt.RightButton:
            # Se ja estiver fazendo algo (ex: line), cancela.
            if self.edit_mode != 'select':
                 self.set_edit_mode('select')
                 event.accept()
                 return

            if self.edit_mode == 'select':
                # [NOVO] Cancelamento Cruzado: Se estiver fazendo Box Azul (Left), Right Click cancela
                if self.box_start is not None:
                    if self.selection_box: self.scene.removeItem(self.selection_box)
                    self.selection_box = None
                    self.box_start = None
                    print("DEBUG: Selection Box Cancelled by Right Click")
                    event.accept()
                    return

                # Logica Box Deselecao (Vermelho)
                scene_pos = self.mapToScene(event.pos())
                if self.deselect_box_start is None:
                    self.deselect_box_start = scene_pos
                    self.deselect_box = self.scene.addRect(QRectF(scene_pos, scene_pos),
                                                          QPen(QColor(255, 50, 50), 1),
                                                          QBrush(QColor(255, 50, 50, 60)))
                    self.deselect_box.setZValue(2000)
                else:
                     # Finalizar Box Deselecao
                    rect = QRectF(self.deselect_box_start, scene_pos).normalized()
                    path = QPainterPath()
                    path.addRect(rect)
                    items = self.scene.items(path, Qt.IntersectsItemBoundingRect, Qt.DescendingOrder, QTransform())
                    
                    for i in items:
                        if i == self.deselect_box: continue
                        i.setSelected(False)
                        if i in self.selected_items: self.selected_items.remove(i)
                    
                    self._on_selection_changed() # Update visual for removed items
                    if self.deselect_box: self.scene.removeItem(self.deselect_box)
                    self.deselect_box = None
                    self.deselect_box_start = None
                
                event.accept()
                return

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
            # Apply Ortho if active and not the first point
            final_pos = snap_pos
            if self.ortho_mode and self.pick_poly_points:
                start_pt = QPointF(*self.pick_poly_points[-1])
                curr_pt = QPointF(*snap_pos)
                res_pt = self._apply_ortho(start_pt, curr_pt)
                final_pos = (res_pt.x(), res_pt.y())

            self.pick_poly_points.append(final_pos)
            path = QPainterPath()
            if self.pick_poly_points:
                path.moveTo(*self.pick_poly_points[0])
                for p in self.pick_poly_points[1:]: path.lineTo(*p)
            if not self.poly_visual:
                self.poly_visual = self.scene.addPath(path, QPen(QColor(0, 255, 255), 0, Qt.DashLine))
                self.poly_visual.setZValue(205)
            else:
                self.poly_visual.setPath(path)
                self.poly_visual.setPen(QPen(QColor(0, 255, 255), 0, Qt.DashLine))
            return

        # --- MODOS DE EDIÇÃO ---
        if self.edit_mode == 'select':
             # [NOVO] Cancelamento Cruzado: Se estiver fazendo Box Vermelho (Right), Left Click cancela
            if self.deselect_box_start is not None:
                if self.deselect_box: self.scene.removeItem(self.deselect_box)
                self.deselect_box = None
                self.deselect_box_start = None
                print("DEBUG: Deselection Box Cancelled by Left Click")
                event.accept()
                return

            # Calculate picking aperture in Scene Units (40 pixels equivalent - more tolerant)
            view_scale = self.transform().m11()
            if view_scale == 0: view_scale = 1 # Avoid div zero
            aperture_px = 5
            aperture_scene = aperture_px / view_scale
            
            p = scene_pos
            rect = QRectF(p.x() - aperture_scene/2, p.y() - aperture_scene/2, aperture_scene, aperture_scene)
            
            print(f"DEBUG click at: {p}, Scale: {view_scale:.4f}, Aperture: {aperture_scene:.2f}")

            # Manual hit test
            items_at_pos = self.scene.items(rect, Qt.IntersectsItemBoundingRect, Qt.DescendingOrder, QTransform())
            
            # Filter for our actionable items
            valid_items = []
            for i in items_at_pos:
                if i == self.selection_box: continue
                if isinstance(i, (DXFLineItem, DXFPathItem, QGraphicsSimpleTextItem, PillarGraphicsItem, SlabGraphicsItem, BeamGraphicsItem)):
                    valid_items.append(i)
                # Helper for standard items if any
                elif isinstance(i, (QGraphicsLineItem, QGraphicsPathItem)) and i.flags() & QGraphicsItem.ItemIsSelectable:
                     valid_items.append(i)

            print(f"DEBUG Valid Items count: {len(valid_items)}")
            if valid_items:
                 print(f"DEBUG First item type found: {type(valid_items[0])}")
            
            item = valid_items[0] if valid_items else None

            if item and not isinstance(item, QGraphicsScene):
                # Clique em objeto
                if event.modifiers() & Qt.ShiftModifier:
                    # Toggle
                    if item.isSelected():
                        item.setSelected(False)
                        if item in self.selected_items: self.selected_items.remove(item)
                    else:
                         item.setSelected(True)
                         if item not in self.selected_items: self.selected_items.append(item)
                else:
                    # Cumulative by default (User Request: "selecoes sejam cumulativas")
                    if not item.isSelected():
                        item.setSelected(True)
                        if item not in self.selected_items:
                            self.selected_items.append(item)
                
                # Forçar atualização visual para qualquer mudança
                self._on_selection_changed()
            else:
                # Clique em área vazia - Iniciar/Finalizar Box
                if self.box_start is None:
                    self.box_start = scene_pos
                    self.selection_box = self.scene.addRect(QRectF(scene_pos, scene_pos), 
                                                           QPen(QColor(0, 120, 215), 1), 
                                                           QBrush(QColor(0, 120, 215, 60)))
                    self.selection_box.setZValue(2000)
                else:
                    # Finalizar Box
                    rect = QRectF(self.box_start, scene_pos).normalized()
                    path = QPainterPath()
                    path.addRect(rect)
                    # Usar BoundingRect garante que linhas finas/cosméticas sejam capturadas
                    items = self.scene.items(path, Qt.IntersectsItemBoundingRect, Qt.DescendingOrder, QTransform())
                    if not (event.modifiers() & Qt.ShiftModifier):
                        # Se Nao tiver shift, o box ADICIONA (Cumulative logic requested)
                        pass
                    
                    for i in items:
                        # Selecionar itens que sao DXF ou Custom, mesmo sem Flag Selectable
                        if isinstance(i, (DXFLineItem, DXFPathItem, QGraphicsSimpleTextItem, PillarGraphicsItem, SlabGraphicsItem, BeamGraphicsItem)) or (i.flags() & QGraphicsItem.ItemIsSelectable):
                            i.setSelected(True)
                            if i not in self.selected_items: self.selected_items.append(i)
                    
                    self._on_selection_changed() # Force highlight update
                    self.scene.removeItem(self.selection_box)
                    self.selection_box = None
                    self.box_start = None
            return

        elif self.edit_mode == 'line':
            blue_pen = QPen(QColor(30, 144, 255), 2)
            if self.pick_start is None:
                self.pick_start = QPointF(*snap_pos)
                self.temp_item = self.scene.addLine(snap_pos[0], snap_pos[1], snap_pos[0], snap_pos[1], blue_pen)
            else:
                final_pos = self._apply_ortho(self.pick_start, QPointF(*snap_pos))
                line = self.scene.addLine(self.pick_start.x(), self.pick_start.y(), final_pos.x(), final_pos.y(), blue_pen)
                line.setZValue(50)
                line.setFlag(QGraphicsItem.ItemIsSelectable)
                self.overlay_items.append(line)
                self.pick_start = final_pos
                if self.temp_item: self.scene.removeItem(self.temp_item)
                self.temp_item = self.scene.addLine(final_pos.x(), final_pos.y(), final_pos.x(), final_pos.y(), blue_pen)
            return

        elif self.edit_mode == 'dim':
            # Cota Manual (2 cliques)
            red_pen = QPen(QColor(255, 50, 50), 1)
            if self.pick_start is None:
                self.pick_start = QPointF(*snap_pos)
                self.temp_item = self.scene.addLine(snap_pos[0], snap_pos[1], snap_pos[0], snap_pos[1], red_pen)
            else:
                final_pos = self._apply_ortho(self.pick_start, QPointF(*snap_pos))
                dist = math.sqrt((self.pick_start.x()-final_pos.x())**2 + (self.pick_start.y()-final_pos.y())**2)
                mid = QPointF((self.pick_start.x()+final_pos.x())/2, (self.pick_start.y()+final_pos.y())/2)
                
                line = self.scene.addLine(self.pick_start.x(), self.pick_start.y(), final_pos.x(), final_pos.y(), red_pen)
                txt = self.scene.addSimpleText(f"{dist:.1f}", QFont("Arial", 10))
                txt.setPos(mid.x(), mid.y())
                txt.setBrush(QBrush(QColor(255, 50, 50)))
                txt.setZValue(120); txt.setFlag(QGraphicsItem.ItemIgnoresTransformations)
                
                self.overlay_items.extend([line, txt])
                self.pick_start = None # Não contínuo para cota geralmente
                if self.temp_item: self.scene.removeItem(self.temp_item); self.temp_item = None
            return

        elif self.edit_mode == 'move':
            if not self.is_moving and self.selected_items:
                self.is_moving = True
                self._last_mouse_pos = scene_pos
            else:
                self.is_moving = False
            return
        
        # Manter outros modos (circle, text, etc) funcionando normalmente
        elif self.edit_mode == 'circle':
            blue_pen = QPen(QColor(30, 144, 255), 2)
            if self.pick_start is None:
                self.pick_start = QPointF(*snap_pos)
                self.temp_item = self.scene.addEllipse(snap_pos[0], snap_pos[1], 0, 0, blue_pen)
            else:
                r = math.sqrt((self.pick_start.x()-snap_pos[0])**2 + (self.pick_start.y()-snap_pos[1])**2)
                circle = self.scene.addEllipse(self.pick_start.x()-r, self.pick_start.y()-r, r*2, r*2, blue_pen)
                circle.setZValue(50); circle.setFlag(QGraphicsItem.ItemIsSelectable); self.overlay_items.append(circle)
                self.pick_start = None
                if self.temp_item: self.scene.removeItem(self.temp_item); self.temp_item = None
            return

        super().mousePressEvent(event)

        # --- PICKING MODES EXISTENTES ---
        if self.picking_mode == 'text':
            # Buscar texto mais próximo
            best_text = None
            min_dist = 5.0 # Raio de clique para texto (precisão extrema)
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
            # Como geometry mode não depende estritamente do OSNAP para selecionar OBJETO, mantemos a busca por proximidade
            best_ent = None
            min_dist = 5.0 
            
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
                elif 'radius' in ent and ('pos' in ent or 'center' in ent): # Circulo
                    p = ent.get('pos', ent.get('center'))
                    d_center = ((p[0]-scene_pos.x())**2 + (p[1]-scene_pos.y())**2)**0.5
                    dist = abs(d_center - ent['radius']) 
                
                if dist < min_dist:
                    min_dist = dist
                    best_ent = ent
            
            if best_ent:
                res = {
                    'type': best_ent.get('type', 'geometry'),
                    'text': best_ent.get('text', 'Entidade CAD'),
                    'pos': best_ent.get('pos', best_ent.get('center')),
                    'points': best_ent.get('points'),
                    'radius': best_ent.get('radius')
                }
                self.pick_completed.emit(res)
                self.set_picking_mode(None)
                return
                
        elif self.picking_mode == 'line':
            if self.pick_start is None:
                # Primeiro clique
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

    def _apply_ortho(self, start, current):
        """Aplica restrição ortogonal se ativa"""
        if not self.ortho_mode: return current
        dx = abs(current.x() - start.x())
        dy = abs(current.y() - start.y())
        if dx > dy: return QPointF(current.x(), start.y())
        else: return QPointF(start.x(), current.y())

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
        snap_pos = snap_data['pos'] if snap_data else (scene_pos.x(), scene_pos.y())
        
        # 2. Box Selection Preview
        if self.edit_mode == 'select' and self.box_start:
            if self.selection_box:
                self.selection_box.setRect(QRectF(self.box_start, scene_pos).normalized())
            return

        # 2b. Deselection Box Preview (Right Click)
        if self.edit_mode == 'select' and self.deselect_box_start:
             if self.deselect_box:
                 self.deselect_box.setRect(QRectF(self.deselect_box_start, scene_pos).normalized())
             return

        # OSNAP Visual
        if self.picking_mode or self.edit_mode:
            for m in self.snap_markers.values(): m.hide()
            if snap_data:
                marker = self.snap_markers.get(snap_data['type'], self.snap_markers.get('endpoint'))
                if marker:
                    marker.setPos(snap_data['pos'][0], snap_data['pos'][1])
                    marker.show()
        
        # 3. Tool Previews
        if self.edit_mode == 'line' and self.pick_start:
            if self.temp_item:
                final_pos = self._apply_ortho(self.pick_start, QPointF(*snap_pos))
                self.temp_item.setLine(QLineF(self.pick_start, final_pos))
                self.temp_item.setPen(QPen(QColor(255, 255, 255), 0))
        
        elif self.edit_mode == 'dim' and self.pick_start:
             if self.temp_item:
                final_pos = self._apply_ortho(self.pick_start, QPointF(*snap_pos))
                self.temp_item.setLine(QLineF(self.pick_start, final_pos))

        elif self.edit_mode == 'move' and self.is_moving:
            delta = scene_pos - self._last_mouse_pos
            for item in self.selected_items:
                item.moveBy(delta.x(), delta.y())
            self._last_mouse_pos = scene_pos

        elif self.edit_mode == 'circle' and self.pick_start:
            if self.temp_item:
                r = math.sqrt((self.pick_start.x()-snap_pos[0])**2 + (self.pick_start.y()-snap_pos[1])**2)
                self.temp_item.setRect(self.pick_start.x()-r, self.pick_start.y()-r, r*2, r*2)

        # Preview Polyline
        if self.picking_mode == 'poly' and self.pick_poly_points:
            from PySide6.QtGui import QPainterPath
            path = QPainterPath()
            path.moveTo(*self.pick_poly_points[0])
            for p in self.pick_poly_points[1:]:
                path.lineTo(*p)
            
            # Apply Ortho for the rubber band line
            final_snap_pos = snap_pos
            if self.ortho_mode and self.pick_poly_points:
                start_pt = QPointF(*self.pick_poly_points[-1])
                curr_pt = QPointF(*snap_pos)
                final_pt = self._apply_ortho(start_pt, curr_pt)
                final_snap_pos = (final_pt.x(), final_pt.y())
            
            path.lineTo(*final_snap_pos) # Rubber band to cursor

            if not self.poly_visual:
                 # Pen width 0 = Cosmetic (always 1 pixel wide regardless of zoom)
                 self.poly_visual = self.scene.addPath(path, QPen(QColor(0, 255, 255), 0, Qt.DashLine))
                 self.poly_visual.setZValue(205)
            else:
                 self.poly_visual.setPath(path)
                 self.poly_visual.setPen(QPen(QColor(0, 255, 255), 0, Qt.DashLine))

        # Preview da Linha
        if self.picking_mode == 'line' and self.pick_start:
            target = snap_pos
            self.temp_line.setLine(self.pick_start.x(), self.pick_start.y(), target[0], target[1])
            self.temp_line.setPen(QPen(QColor(255, 255, 0), 0))
            
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
            
        if self.edit_mode == 'select':
            event.accept()
            return

        # Desabilitado release para usar o 2-cliques system
        if not self.picking_mode:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        # 1. Finalizar Poly
        if self.picking_mode == 'poly' and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if len(self.pick_poly_points) >= 2:
                poly_data = {'text': 'Polyline', 'type': 'poly', 'points': self.pick_poly_points}
                path = QPainterPath()
                path.moveTo(*self.pick_poly_points[0])
                for p in self.pick_poly_points[1:]: path.lineTo(*p)
                path.closeSubpath()
                item = self.scene.addPath(path, QPen(QColor(255, 0, 0), 2), QBrush(QColor(255, 0, 0, 50)))
                self.overlay_items.append(item)
                self.pick_completed.emit(poly_data)
                self.set_picking_mode(None)
            return

        # 2. Atalhos de Ferramentas
        key = event.key()
        if key == Qt.Key_Escape:
            self.set_edit_mode(None)
            self.keyboard_buffer = ""
            self.input_label.hide()
        elif key == Qt.Key_L: self.set_edit_mode('line')
        elif key == Qt.Key_C: self.set_edit_mode('circle')
        elif key == Qt.Key_T: self.set_edit_mode('text')
        elif key == Qt.Key_D: self.set_edit_mode('dim')
        elif key == Qt.Key_M: self.set_edit_mode('move')
        elif key in (Qt.Key_Delete, Qt.Key_Backspace): self._delete_selection()
        
        # 3. Atalhos de Ação (Enter/F8)
        if key == Qt.Key_F8:
            self.toggle_ortho()
            return

        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self.edit_mode == 'move' and self.is_moving:
                self.is_moving = False
                self.set_edit_mode('select')
                return
            elif self.edit_mode == 'line' and not self.keyboard_buffer:
                 self.set_edit_mode('select')
                 return

        # 4. Entrada Numérica Direcional (CAD-Like) - Linha, Cota, Círculo
        if self.edit_mode in ('line', 'dim', 'circle') and self.pick_start:
            text = event.text()
            if text.isdigit() or text == '.':
                self.keyboard_buffer += text
                label_txt = "Raio: " if self.edit_mode == 'circle' else "Distância: "
                self.input_label.setText(f"{label_txt}{self.keyboard_buffer}")
                self.input_label.show()
                self.input_label.adjustSize()
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                if self.keyboard_buffer:
                    val = float(self.keyboard_buffer)
                    
                    if self.edit_mode == 'circle':
                        r = val
                        blue_pen = QPen(QColor(30, 144, 255), 2)
                        circle = self.scene.addEllipse(self.pick_start.x()-r, self.pick_start.y()-r, r*2, r*2, blue_pen)
                        circle.setZValue(50); circle.setFlag(QGraphicsItem.ItemIsSelectable); self.overlay_items.append(circle)
                        self.pick_start = None # Finaliza círculo
                    else:
                        dist = val
                        # Direção do mouse atual
                        mouse_scene = self.mapToScene(self.mapFromGlobal(QCursor.pos()))
                        angle = math.atan2(mouse_scene.y() - self.pick_start.y(), mouse_scene.x() - self.pick_start.x())
                        
                        if self.ortho_mode:
                            deg = math.degrees(angle) % 360
                            if (315 <= deg < 360) or (0 <= deg < 45): angle = 0
                            elif (45 <= deg < 135): angle = math.pi/2
                            elif (135 <= deg < 225): angle = math.pi
                            else: angle = 3*math.pi/2

                        target_x = self.pick_start.x() + dist * math.cos(angle)
                        target_y = self.pick_start.y() + dist * math.sin(angle)
                        target_pos = QPointF(target_x, target_y)

                        if self.edit_mode == 'line':
                            line = self.scene.addLine(self.pick_start.x(), self.pick_start.y(), target_x, target_y, QPen(QColor(30, 144, 255), 2))
                            line.setZValue(50); line.setFlag(QGraphicsItem.ItemIsSelectable); self.overlay_items.append(line)
                            self.pick_start = target_pos # Continuar da ponta
                        else: # dim
                            red_pen = QPen(QColor(255, 50, 50), 1)
                            line = self.scene.addLine(self.pick_start.x(), self.pick_start.y(), target_x, target_y, red_pen)
                            mid = QPointF((self.pick_start.x()+target_x)/2, (self.pick_start.y()+target_y)/2)
                            txt = self.scene.addSimpleText(f"{dist:.1f}", QFont("Arial", 10))
                            txt.setPos(mid.x(), mid.y()); txt.setBrush(QBrush(QColor(255, 50, 50)))
                            txt.setZValue(120); txt.setFlag(QGraphicsItem.ItemIgnoresTransformations)
                            self.overlay_items.extend([line, txt])
                            self.pick_start = None
                    
                    self.keyboard_buffer = ""
                    self.input_label.hide()
                    if self.temp_item:
                         if self.pick_start:
                            if self.edit_mode == 'line':
                                self.temp_item.setLine(QLineF(self.pick_start, self.pick_start))
                            else:
                                self.scene.removeItem(self.temp_item); self.temp_item = None
                         else:
                             self.scene.removeItem(self.temp_item); self.temp_item = None

        super().keyPressEvent(event)
    def wheelEvent(self, event):
        """Zoom in/out com scroll do mouse"""
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor

        # Se houver scroll vertical
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        self.scale(zoom_factor, zoom_factor)
        
        # Ignora propagação (evita scroll das barras)
        event.accept()
