from ..styles import DS
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsView, QComboBox, QHBoxLayout, QLabel, QRubberBand, QGraphicsTextItem
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, Signal, QEvent, QTimer
from PySide6.QtGui import QWheelEvent, QPainter, QMouseEvent, QKeyEvent
from ..models.graphics_scene import LajeGraphicsScene
from ..widgets.edition_toolbar import EditionToolbar, MoveCommandWidget, OffsetCommandWidget
from ..widgets.linhas_overlay import VerticalLinesOverlay, HorizontalLinesOverlay
from ..widgets.calculos_modos_widget import CalculosModosWidget
from laje_src.services.calculo_modo1 import calcular_modo1, calcular_modo2
from laje_src.models.laje import Laje
from laje_src.models.pavimento import Pavimento
from laje_src.models.obra import Obra
from typing import List, Optional, Any
from PySide6.QtWidgets import QMessageBox
from laje_src.ui.utils.undo_manager import UndoManager
from laje_src.services.ai.layout_learner import LayoutLearner
from PySide6.QtWidgets import QInputDialog, QLineEdit
from datetime import datetime
import copy
from laje_src.services.file_manager import load_all_obras, save_all_obras
from laje_src.ui.widgets.rules_dialog import RulesDialog

class CustomGraphicsView(QGraphicsView):
    """QGraphicsView customizado com zoom via scroll e drag melhorado"""
    def __init__(self, scene=None):
        super().__init__(scene)
        self._pan_start = QPoint()
        self._panning = False
        self._drag_mode = QGraphicsView.DragMode.NoDrag
        
        # Configurar para melhor performance e fluidez
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        
        # Configurar anchors para melhor controle de transformação
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        
        # NÃO habilitar drag por padrão - apenas com botão do meio
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        # Variáveis para seleção por retângulo (serão gerenciadas pelo CanvasWidget)
    
    def wheelEvent(self, event: QWheelEvent):
        """Controle de zoom via scroll do mouse com foco no mouse"""
        # Zoom com scroll do mouse (sem precisar de Ctrl)
        zoom_factor = 1.15
        if event.angleDelta().y() < 0:
            zoom_factor = 1.0 / zoom_factor
        
        # Zoom focado no ponto do mouse
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.scale(zoom_factor, zoom_factor)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Controle de drag apenas com botão do meio"""
        if event.button() == Qt.MouseButton.MiddleButton:
            # Botão do meio: iniciar pan
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            # Botão esquerdo e direito: passar para handler customizado (seleção)
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Melhorar movimento durante drag"""
        if self._panning:
            # Pan manual com botão do meio
            delta = event.pos() - self._pan_start
            if delta.manhattanLength() > 3:  # Threshold para evitar micro-movimentos
                h_bar = self.horizontalScrollBar()
                v_bar = self.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())
                self._pan_start = event.pos()
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Finalizar drag"""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event):
        """Alternar entre drag e seleção com teclas"""
        if event.key() == Qt.Key.Key_Space:
            # Espaço: alternar entre drag e seleção
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            else:
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            event.accept()
        else:
            super().keyPressEvent(event)

class CanvasWidget(QWidget):
    # Sinal emitido quando linhas são editadas
    linhas_edited = Signal(list, list)  # vertical_distances, horizontal_distances
    training_example_created = Signal(object, str, str)  # laje, comentario, feedback_type  # nova_laje, comentario
    
    # NOVOS SINAIS PARA FEEDBACK IA
    ai_feedback_requested = Signal(str, str, dict, float) # title, message, context, confidence
    ai_status_message = Signal(str, str, str) # title, message, color
    ai_feedback_finalize_requested = Signal() # Solicita que a UI envie o comentário atual (ENTER no canvas)
    
    def sum_list(self, l):
        """Helper para somar lista que pode conter dicts ou floats."""
        if not l: return 0.0
        return sum(x["value"] if isinstance(x, dict) else float(x) for x in l)

    def __init__(self):
        super().__init__()
        self.laje_atual: Laje = None
        self.obra_atual: Obra = None
        self.pavimento_atual: Optional[str] = None
        self.modo_visualizacao = "Item"  # Item, Pavimento, Obra
        self.edition_toolbar = None
        self.move_widget = None
        self.offset_widget = None
        # Variáveis para seleção por retângulo
        self._selection_start = None
        self._selection_rubber_band = None
        self._is_selecting = False
        self._is_deselecting = False
        self._feedback_error_mode = False # Flag para modo de seleção de erros de feedback
        self._updating_overlays = False  # Flag para evitar loops
        self._updating_visualization = False  # Flag para evitar loops na visualização
        self.show_panel_labels = True  # Flag para controlar visibilidade dos nomes
        self.show_auto_dimensions = True
        
        # Sistema de desfazer (undo)
        self.undo_manager = UndoManager(max_history=10)
        
        # IA de Interpretação
        self.learner = LayoutLearner()
        
        # Timer para debounce de atualização de visualização (performance)
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._do_atualizar_visualizacao)
        self._pending_update = False
        
        # Opções globais de desenho (aplicam a todos os modos: Item, Pavimento, Obra)
        self._opcoes_desenho = {
            "nomes_paineis": True,           # Desenhar nomes dos painéis
            "nomes_reaproveitamento": False,  # Desenhar tags REAP
            "hatches_reaproveitamento": False, # Desenhar hatches REAP
            "marco_laje": True,              # Desenhar marco da laje
            "unioes_hatch": True,            # Desenhar hatches nas uniões
            "cotas_automaticas": True        # Desenhar cotas automáticas (pink)
        }
        
        # Reaproveitamento (REAP) - mantido para compatibilidade
        self._reap_opcoes = {
            "desenhar_nomes": True,
            "mostrar_hatches": True
        }
        
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout(self) # Alterado para QVBoxLayout
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 1. Canvas no topo
        canvas_container = QWidget()
        canvas_container_layout = QHBoxLayout(canvas_container) # Layout horizontal para acomodar horizontais na esquerda
        canvas_container_layout.setContentsMargins(0, 0, 0, 0)
        canvas_container_layout.setSpacing(5)
        
        # Criar cena e view
        self.scene = LajeGraphicsScene()
        self.scene._canvas_widget_ref = self
        self.view = CustomGraphicsView(self.scene)
        
        # Criar "overlays" (agora widgets normais integrados ao layout)
        self.vertical_lines_overlay = VerticalLinesOverlay()
        self.horizontal_lines_overlay = HorizontalLinesOverlay()
        
        # Estilo para os widgets de linhas
        self.vertical_lines_overlay.setStyleSheet(f"""
            QWidget {{
                background-color: {DS.DEEP};
                border-radius: 5px;
                border: 1px solid {DS.BORDER_STR};
            }}
        """)
        self.horizontal_lines_overlay.setStyleSheet(f"""
            QWidget {{
                background-color: {DS.DEEP};
                border-radius: 5px;
                border: 1px solid {DS.BORDER_STR};
            }}
        """)
        
        # Definir tamanho mínimo inicial
        self.vertical_lines_overlay.setMinimumSize(200, 50)
        self.horizontal_lines_overlay.setMinimumSize(130, 200)
        
        # Montar layout do canvas: Esquerda (Horizontais) + Direita (View e Verticais abaixo)
        view_and_vert_layout = QVBoxLayout()
        view_and_vert_layout.setContentsMargins(0, 0, 0, 0)
        view_and_vert_layout.setSpacing(5)
        view_and_vert_layout.addWidget(self.view, stretch=1)
        view_and_vert_layout.addWidget(self.vertical_lines_overlay)
        
        canvas_container_layout.addWidget(self.horizontal_lines_overlay)
        canvas_container_layout.addLayout(view_and_vert_layout, stretch=1)
        
        main_layout.addWidget(canvas_container, stretch=1)
        
        # 2. Painéis Inferiores (Toolbar de Edição + Cálculos/Modos)
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)
        
        # Toolbar de edição
        self.edition_toolbar = EditionToolbar()
        bottom_layout.addWidget(self.edition_toolbar)
        
        # Cálculos Modos
        self.calculos_modos = CalculosModosWidget()
        self.calculos_modos.modo_selecionado.connect(self.on_modo_calculo_selecionado)
        self.calculos_modos.correcao_122_60_requested.connect(self.apply_correction_122_60)
        self.calculos_modos.correcao_122_20_requested.connect(self.apply_correction_122_20)
        self.calculos_modos.correcao_122_uniao_requested.connect(self.apply_correction_122_uniao)
        self.calculos_modos.correcao_20_uniao_requested.connect(self.apply_correction_122_uniao)
        self.calculos_modos.inverter_verticais_requested.connect(self.inverter_linhas_verticais)
        self.calculos_modos.inverter_horizontais_requested.connect(self.inverter_linhas_horizontais)
        self.calculos_modos.ajustar_sobra_requested.connect(self.ajustar_sobra)
        self.calculos_modos.unioes_ilhas_esquerda_changed.connect(self.on_unioes_ilhas_esquerda_changed)
        self.calculos_modos.unioes_ilhas_direita_changed.connect(self.on_unioes_ilhas_direita_changed)
        self.calculos_modos.unioes_set_all_requested.connect(self.set_all_unions_value)
        self.calculos_modos.checkbox_unioes_bordes.stateChanged.connect(self.on_unioes_bordes_changed)
        
        viz_container = QWidget()
        viz_layout = QHBoxLayout(viz_container)
        viz_layout.setContentsMargins(0, 0, 10, 0)
        viz_layout.setSpacing(5)
        viz_layout.addWidget(QLabel("Visualização:"))
        
        self.modo_combo = QComboBox()
        self.modo_combo.addItems(["Item", "Pavimento", "Obra"])
        self.modo_combo.setCurrentText("Item")
        self.modo_combo.currentTextChanged.connect(self.on_modo_changed)
        viz_layout.addWidget(self.modo_combo)
        self.calculos_modos.add_widget_to_bottom_row(viz_container)
        
        bottom_layout.addWidget(self.calculos_modos, stretch=1)
        
        main_layout.addLayout(bottom_layout)
        
        # Conectar sinais dos "overlays"
        self.vertical_lines_overlay.linhas_changed.connect(self.on_vertical_lines_changed)
        self.horizontal_lines_overlay.linhas_changed.connect(self.on_horizontal_lines_changed)
        
        # Conectar sinais do toolbar
        self.setup_edition_connections()
        
        # Configurar eventos de mouse e teclado
        self.view.setMouseTracking(True)
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Ativar modo de seleção automaticamente
        self.scene.activate_selection_mode()
        self.edition_toolbar.mode = 'select'
        self.edition_toolbar.update_button_states()
        

    
    def on_modo_changed(self, modo: str):
        """Atualiza visualização quando modo muda"""
        self.modo_visualizacao = modo
        self.atualizar_visualizacao()
    
    def set_obra(self, obra: Obra):
        """Define a obra atual"""
        self.obra_atual = obra
        self.atualizar_visualizacao()
    
    def set_show_labels(self, show: bool):
        """Define se deve mostrar nomes dos painéis"""
        self.show_panel_labels = show
        self.atualizar_visualizacao()
    
    def set_reap_opcoes(self, opcoes: dict):
        """Define opções de visualização de reaproveitamento (REAP)"""
        self._reap_opcoes = opcoes or {}
        # Atualizar scene se existir
        if hasattr(self, 'scene') and self.scene:
            self.scene.show_reap_labels = opcoes.get("desenhar_nomes", True)
            self.scene.show_reap_hatches = opcoes.get("mostrar_hatches", True)
        self.atualizar_visualizacao()
    
    def set_opcoes_desenho(self, opcoes: dict):
        """Define todas as opções globais de desenho (aplicam a todos os modos)"""
        if opcoes:
            self._opcoes_desenho.update(opcoes)
            
            # Atualizar flags relacionadas
            self.show_panel_labels = self._opcoes_desenho.get("nomes_paineis", True)
            self.show_auto_dimensions = self._opcoes_desenho.get("cotas_automaticas", True)
            
            # Atualizar opções de REAP
            self._reap_opcoes["desenhar_nomes"] = self._opcoes_desenho.get("nomes_reaproveitamento", False)
            self._reap_opcoes["mostrar_hatches"] = self._opcoes_desenho.get("hatches_reaproveitamento", False)
            
            # Atualizar scene se existir
            if hasattr(self, 'scene') and self.scene:
                self.scene.show_reap_labels = self._reap_opcoes.get("desenhar_nomes", False)
                self.scene.show_reap_hatches = self._reap_opcoes.get("mostrar_hatches", False)
            
            # Atualizar visualização
            self.atualizar_visualizacao()
    
    def get_opcoes_desenho(self) -> dict:
        """Retorna as opções atuais de desenho"""
        return self._opcoes_desenho.copy()
    
    def atualizar_visualizacao(self, immediate: bool = False):
        """Atualiza a visualização conforme o modo selecionado
        
        Args:
            immediate: Se True, atualiza imediatamente. Se False, usa debounce para melhor performance.
        """
        # Evitar loops infinitos
        if self._updating_visualization:
            return
        
        # Verificar se o widget está visível e pronto antes de atualizar
        if not self.isVisible() or not self.scene:
            return
        
        # Usar debounce para evitar múltiplas atualizações rápidas (melhor performance)
        if not immediate:
            self._pending_update = True
            self._update_timer.stop()  # Resetar timer se já estava rodando
            self._update_timer.start(50)  # Aguardar 50ms antes de atualizar
            return
        
        # Atualização imediata
        self._do_atualizar_visualizacao()
    
    def _do_atualizar_visualizacao(self):
        """Executa a atualização de visualização (método interno)"""
        # Evitar loops infinitos
        if self._updating_visualization:
            return
        
        # Verificar se o widget está visível e pronto antes de atualizar
        if not self.isVisible() or not self.scene:
            self._pending_update = False
            return
        
        self._updating_visualization = True
        self._pending_update = False
        
        try:
            if self.modo_visualizacao == "Item":
                # Modo Item: mostrar apenas laje atual
                if not self.laje_atual:
                    # Limpar canvas se não houver laje
                    # IMPORTANTE: Limpar também listas de cotas manuais para evitar que sejam herdadas
                    self.scene.manual_dimension_texts.clear()
                    self.scene.manual_dimension_data.clear()
                    self.scene.clear()
                elif self.laje_atual.coordenadas:
                    # Limpar tudo antes de desenhar (incluindo nomes de outras lajes)
                    # Remover textos de nomes antigos da cena antes de limpar listas
                    for text_item in self.scene.laje_name_texts[:]:
                        try:
                            self.scene.removeItem(text_item)
                        except (RuntimeError, AttributeError):
                            pass
                    for text_item in self.scene.pavimento_name_texts[:]:
                        try:
                            self.scene.removeItem(text_item)
                        except (RuntimeError, AttributeError):
                            pass
                    # Limpar listas
                    self.scene.laje_name_texts.clear()
                    self.scene.pavimento_name_texts.clear()
                    # IMPORTANTE: Limpar também listas de cotas manuais antes de limpar a cena
                    # Isso evita que cotas da laje anterior sejam herdadas pela nova laje
                    self.scene.manual_dimension_texts.clear()
                    self.scene.manual_dimension_data.clear()
                    # Limpar cena completamente
                    self.scene.clear()
                    
                    # Obter obstáculos da laje (se existirem)
                    obstaculos = getattr(self.laje_atual, 'obstaculos', [])
                    # Desenhar laje com obstáculos (sem o polígono do marco ainda)
                    # Primeiro desenhar apenas obstáculos e nome
                    if obstaculos:
                        for obstaculo_coords in obstaculos:
                            if len(obstaculo_coords) >= 3:
                                from PySide6.QtWidgets import QGraphicsPolygonItem
                                from PySide6.QtCore import QPointF
                                from PySide6.QtGui import QPolygonF, QBrush, QColor, QPen
                                polygon_qt = QPolygonF([QPointF(x, y) for x, y in obstaculo_coords])
                                hatch = QGraphicsPolygonItem(polygon_qt)
                                brush = QBrush(QColor(255, 255, 0, 120))
                                hatch.setBrush(brush)
                                hatch.setPen(QPen(QColor(f"{DS.WHITE}f00"), 2))
                                self.scene.addItem(hatch)
                                self.scene.union_hatches.append(hatch)
                    
                    # Desenhar nome da laje se fornecido
                    if self.laje_atual.nome:
                        self.scene.draw_laje_name(self.laje_atual.nome, self.laje_atual.coordenadas)
                    
                    # Limpar dados de linhas antigas para evitar segmentação excessiva
                    self.scene.reset_lines_data()
                    
                    # Desenhar linhas primeiro (para que o marco possa seccionar em cruzamentos)
                    if self.laje_atual.linhas_verticais:
                        self.scene.draw_vertical_lines(self.laje_atual.linhas_verticais, self.laje_atual.coordenadas, obstaculos)
                    if self.laje_atual.linhas_horizontais:
                        self.scene.draw_horizontal_lines(self.laje_atual.linhas_horizontais, self.laje_atual.coordenadas, obstaculos)
                    
                    # Desenhar marco como segmentos seccionados (após as linhas)
                    self.scene.draw_marco_segments(
                        self.laje_atual.coordenadas,
                        self.laje_atual.linhas_verticais if self.laje_atual.linhas_verticais else None,
                        self.laje_atual.linhas_horizontais if self.laje_atual.linhas_horizontais else None,
                        obstaculos
                    )
                    
                    # Sincronizar lista de cotas excluídas com a scene (antes de restaurar cotas manuais)
                    if hasattr(self.laje_atual, 'excluded_dimensions'):
                        self.scene.excluded_dimensions = self.laje_atual.excluded_dimensions.copy()
                    else:
                        self.scene.excluded_dimensions = []
                    
                    if self.laje_atual.linhas_verticais or self.laje_atual.linhas_horizontais:
                        # Pular draw_dimensions se for chamado durante interpretação IA de linhas
                        # (IA cotas será chamada depois separadamente)
                        if self.show_auto_dimensions and not getattr(self, '_skip_dimensions_during_update', False):
                            # Chamar join automático antes de gerar cotas para evitar processamento de segmentos indevidos
                            self.scene.join_automatico()
                            
                            # Sincronizar posições de join com a laje atual para persistência
                            self.laje_atual.marco_joined_positions = {
                                'vertical': list(self.scene.marco_joined_positions['vertical']),
                                'horizontal': list(self.scene.marco_joined_positions['horizontal'])
                            }
                            
                            self.scene.draw_dimensions(self.laje_atual.linhas_verticais, self.laje_atual.linhas_horizontais, self.laje_atual.coordenadas, self.laje_atual)
                        # Desenhar numeração dos painéis e cotas especiais (incluindo recortes)
                        obstaculos = getattr(self.laje_atual, 'obstaculos', [])
                        self.scene.draw_panel_labels_and_special_dimensions(
                            self.laje_atual.linhas_verticais,
                            self.laje_atual.linhas_horizontais, 
                            self.laje_atual.coordenadas,
                            self.laje_atual.pavimento,  # Nome do pavimento
                            self.laje_atual.nome,  # Nome da laje
                            obstaculos,  # Recortes (ilhas)
                            show_labels=self.show_panel_labels,
                            laje=self.laje_atual
                        )
                        
                        # Restaurar cotas manuais salvas (após desenhar tudo, para que fiquem por cima)
                        # IMPORTANTE: Só restaurar se realmente houver cotas manuais na laje
                        # E garantir que a lista não está vazia (para evitar restaurar cotas de laje anterior)
                        if (hasattr(self.laje_atual, 'manual_dimensions') and 
                            self.laje_atual.manual_dimensions and 
                            len(self.laje_atual.manual_dimensions) > 0):
                            self.scene.restore_manual_dimensions(self.laje_atual.manual_dimensions, self.laje_atual.coordenadas, self.laje_atual)
                        
                        # Desenhar elementos de reaproveitamento (REAP) se existirem dados
                        if hasattr(self.laje_atual, 'reaproveitamento_dados') and self.laje_atual.reaproveitamento_dados:
                            self.scene.set_reap_data(
                                self.laje_atual.reaproveitamento_dados,
                                show_labels=self._reap_opcoes.get("desenhar_nomes", True),
                                show_hatches=self._reap_opcoes.get("mostrar_hatches", True)
                            )
                            self.scene.draw_reap_elements(
                                self.laje_atual.coordenadas,
                                self.laje_atual.linhas_verticais,
                                self.laje_atual.linhas_horizontais
                            )
                        
                        # Desenhar insígnias (estrelas) nos painéis utilizados/passados
                        if self.obra_atual and self.laje_atual.pavimento:
                            pavimento = next(
                                (p for p in self.obra_atual.pavimentos if p.nome == self.laje_atual.pavimento),
                                None
                            )
                            if pavimento:
                                self.scene.set_paineis_status(
                                    pavimento.paineis_utilizados,
                                    pavimento.paineis_passados_adiante
                                )
                                self.scene.draw_panel_insignias(
                                    self.laje_atual.nome,
                                    self.laje_atual.coordenadas,
                                    self.laje_atual.linhas_verticais,
                                    self.laje_atual.linhas_horizontais
                                )
                    
                    if self.laje_atual.area_cm2 > 0:
                        self.scene.draw_area_label(self.laje_atual.area_cm2)
                    
                    # Armazenar dados para edição
                    self.scene.set_edition_data(
                        self.laje_atual.coordenadas,
                        self.laje_atual.linhas_verticais,
                        self.laje_atual.linhas_horizontais,
                        obstaculos
                    )
                    
                    # Restaurar posições unificadas do marco (joins) se existirem
                    if hasattr(self.laje_atual, 'marco_joined_positions') and self.laje_atual.marco_joined_positions:
                        self.scene.marco_joined_positions = {
                            'vertical': set(self.laje_atual.marco_joined_positions.get('vertical', [])),
                            'horizontal': set(self.laje_atual.marco_joined_positions.get('horizontal', []))
                        }
                    else:
                        # Limpar se não houver posições salvas
                        self.scene.marco_joined_positions = {'vertical': set(), 'horizontal': set()}
                    
                    # Calcular área válida e limpar objetos distantes
                    if self.laje_atual.coordenadas:
                        self.scene.calculate_valid_area(self.laje_atual.coordenadas)
                        self.scene.cleanup_distant_objects()
                    
                    # Definir sceneRect com padding de 200 unidades para permitir drag além dos limites
                    # Usar área válida se disponível, senão usar itemsBoundingRect
                    if self.scene.valid_area and not self.scene.valid_area.isEmpty():
                        items_rect = self.scene.valid_area
                    else:
                        items_rect = self.scene.itemsBoundingRect()
                    if not items_rect.isEmpty():
                        # Padding fixo de 1000 unidades em cada direção para máxima liberdade de drag
                        padding = 1000.0
                        scene_rect = QRectF(
                            items_rect.x() - padding,
                            items_rect.y() - padding,
                            items_rect.width() + (padding * 2),
                            items_rect.height() + (padding * 2)
                        )
                        self.scene.setSceneRect(scene_rect)
                        # Usar a área válida (sem padding extra) para fitInView - mais próximo e centralizado
                        self.view.fitInView(items_rect, Qt.AspectRatioMode.KeepAspectRatio)
            elif self.modo_visualizacao == "Pavimento":
                # Modo Pavimento: mostrar todas as lajes do pavimento atual
                if self.obra_atual:
                    # Usar pavimento_atual se definido, senão usar do laje_atual
                    pavimento_nome = self.pavimento_atual
                    if not pavimento_nome and self.laje_atual:
                        pavimento_nome = self.laje_atual.pavimento
                    
                    if pavimento_nome:
                        pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == pavimento_nome), None)
                        if pavimento and pavimento.lajes:
                            # Definir status dos painéis (utilizados/passados adiante) para insígnias
                            self.scene.set_paineis_status(
                                pavimento.paineis_utilizados,
                                pavimento.paineis_passados_adiante
                            )
                            
                            # Desenhar lajes com elementos REAP e insígnias
                            self.scene.draw_multiple_lajes_with_reap(
                                pavimento.lajes, 
                                show_laje_names=True,
                                show_reap_labels=self._reap_opcoes.get("desenhar_nomes", True),
                                show_reap_hatches=self._reap_opcoes.get("mostrar_hatches", True)
                            )
                            
                            # Calcular área válida e limpar objetos distantes
                            if pavimento and pavimento.lajes:
                                all_coords = []
                                for laje in pavimento.lajes:
                                    if laje.coordenadas:
                                        all_coords.extend(laje.coordenadas)
                                if all_coords:
                                    # Calcular bounding box de todas as coordenadas
                                    min_x = min(x for x, y in all_coords)
                                    max_x = max(x for x, y in all_coords)
                                    min_y = min(y for x, y in all_coords)
                                    max_y = max(y for x, y in all_coords)
                                    # Criar área válida
                                    valid_coords = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
                                    self.scene.calculate_valid_area(valid_coords)
                                    self.scene.cleanup_distant_objects()
                            
                            # Definir sceneRect com padding de 200 unidades para permitir drag além dos limites
                            # Usar área válida se disponível
                            if self.scene.valid_area and not self.scene.valid_area.isEmpty():
                                items_rect = self.scene.valid_area
                            else:
                                items_rect = self.scene.itemsBoundingRect()
                            
                            if not items_rect.isEmpty():
                                # Padding fixo de 1000 unidades em cada direção para máxima liberdade de drag
                                padding = 1000.0
                                scene_rect = QRectF(
                                    items_rect.x() - padding,
                                    items_rect.y() - padding,
                                    items_rect.width() + (padding * 2),
                                    items_rect.height() + (padding * 2)
                                )
                                self.scene.setSceneRect(scene_rect)
                                # Usar a área válida (sem padding extra) para fitInView - mais próximo e centralizado
                                self.view.fitInView(items_rect, Qt.AspectRatioMode.KeepAspectRatio)
                        else:
                            self.scene.clear()
                    else:
                        self.scene.clear()
            elif self.modo_visualizacao == "Obra":
                # Modo Obra: mostrar todas as lajes de todos os pavimentos com REAP e insígnias
                if self.obra_atual:
                    self.scene.draw_multiple_lajes_by_pavimento_with_reap(
                        self.obra_atual.pavimentos, 
                        show_laje_names=True, 
                        show_pavimento_names=True,
                        show_reap_labels=self._reap_opcoes.get("desenhar_nomes", True),
                        show_reap_hatches=self._reap_opcoes.get("mostrar_hatches", True)
                    )
                    # Calcular área válida baseada nas lajes e limpar objetos distantes
                    if self.obra_atual and self.obra_atual.pavimentos:
                        all_coords = []
                        for pavimento in self.obra_atual.pavimentos:
                            for laje in pavimento.lajes:
                                if laje.coordenadas:
                                    all_coords.extend(laje.coordenadas)
                        if all_coords:
                            # Calcular bounding box de todas as coordenadas
                            min_x = min(x for x, y in all_coords)
                            max_x = max(x for x, y in all_coords)
                            min_y = min(y for x, y in all_coords)
                            max_y = max(y for x, y in all_coords)
                            # Criar área válida
                            valid_coords = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
                            self.scene.calculate_valid_area(valid_coords)
                            self.scene.cleanup_distant_objects()
                    
                    # Definir sceneRect com padding de 200 unidades para permitir drag além dos limites
                    # Usar área válida se disponível
                    if self.scene.valid_area and not self.scene.valid_area.isEmpty():
                        items_rect = self.scene.valid_area
                    else:
                        items_rect = self.scene.itemsBoundingRect()
                    
                    if not items_rect.isEmpty():
                        # Padding fixo de 1000 unidades em cada direção para máxima liberdade de drag
                        padding = 1000.0
                        scene_rect = QRectF(
                            items_rect.x() - padding,
                            items_rect.y() - padding,
                            items_rect.width() + (padding * 2),
                            items_rect.height() + (padding * 2)
                        )
                        self.scene.setSceneRect(scene_rect)
                        # Usar a área válida (sem padding extra) para fitInView - mais próximo e centralizado
                        self.view.fitInView(items_rect, Qt.AspectRatioMode.KeepAspectRatio)
        except Exception as e:
            print(f"Erro ao atualizar visualização: {e}")
        finally:
            self._updating_visualization = False
            # Se havia uma atualização pendente, processar agora
            if self._pending_update:
                self._update_timer.start(50)
            # Forçar atualização apenas se o widget estiver visível
            if self.isVisible() and self.scene:
                try:
                    self.scene.update()
                except RuntimeError:
                    pass  # Ignorar erros de atualização se o widget foi destruído
    
    def determinar_modo_automatico(self, laje: Laje) -> int:
        """Determina o modo (0=M1 ou 1=M2) baseado em largura e altura da laje"""
        if not laje or not laje.coordenadas:
            return 0  # Padrão M1
        
        coords = laje.coordenadas
        min_x = min(x for x, y in coords)
        max_x = max(x for x, y in coords)
        min_y = min(y for x, y in coords)
        max_y = max(y for x, y in coords)
        
        largura = max_x - min_x
        altura = max_y - min_y
        
        # Modo 1 (Verticais): usar quando largura > altura
        # Modo 2 (Horizontais): usar quando altura > largura
        # Se iguais, usar Modo 1 como padrão
        modo = 0 if largura >= altura else 1
        return modo
    
    def aplicar_correcoes_automaticas(self, salvar: bool = True):
        """Aplica correções automáticas: 5x(122x60) e ajustar_sobra"""
        if not self.laje_atual:
            return
        
        # Aplicar correção 5x(122x60)
        self.apply_correction_122_60(5)
        
        # Usar QTimer para executar ajustar_sobra após as correções serem processadas
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._aplicar_ajustar_sobra_automatico(salvar))
    
    def _aplicar_ajustar_sobra_automatico(self, salvar: bool = True):
        """Aplica ajustar_sobra e salva se solicitado"""
        self.ajustar_sobra()
        
        if salvar:
            # Usar QTimer para salvar após ajustar_sobra ser processado
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._salvar_laje_atual)
    
    def _salvar_laje_atual(self):
        """Salva a laje atual"""
        if self.laje_atual and self.obra_atual:
            # Emitir sinal para salvar (será capturado em main_window)
            self.linhas_edited.emit(
                self.laje_atual.linhas_verticais or [],
                self.laje_atual.linhas_horizontais or []
            )
    
    def set_laje(self, laje: Laje, aplicar_correcoes_automaticas: bool = False):
        """Define a laje atual e atualiza o canvas
        
        Args:
            laje: Laje a ser definida
            aplicar_correcoes_automaticas: Se True, executa 5x(122x60) e ajustar_sobra após carregar
        """
        # Limpar histórico ao trocar de laje
        self.undo_manager.clear()
        
        self.laje_atual = laje
        
        # Salvar estado inicial da laje
        if laje:
            self.undo_manager.save_state(laje)
        
        # Atualizar overlays com as linhas da laje
        if laje:
            # Carregar modo e checkbox salvos
            modo_salvo = laje.modo_selecionado if hasattr(laje, 'modo_selecionado') else None
            unioes_salvo = laje.unioes_nos_bordes if hasattr(laje, 'unioes_nos_bordes') else False
            
            # Se não há modo salvo, determinar automaticamente
            if modo_salvo is None:
                modo_salvo = self.determinar_modo_automatico(laje)
                laje.modo_selecionado = modo_salvo
            
            # Desconectar checkbox temporariamente para evitar loops
            try:
                self.calculos_modos.checkbox_unioes_bordes.stateChanged.disconnect(self.on_unioes_bordes_changed)
            except:
                pass  # Pode não estar conectado ainda
            
            # Atualizar UI com valores salvos
            self.calculos_modos.set_modo(modo_salvo)
            _unioes_bool = bool(unioes_salvo[0] if isinstance(unioes_salvo, list) and unioes_salvo else unioes_salvo)
            self.calculos_modos.checkbox_unioes_bordes.setChecked(_unioes_bool)
            
            # Reconectar checkbox
            self.calculos_modos.checkbox_unioes_bordes.stateChanged.connect(self.on_unioes_bordes_changed)
            
            # Sincronizar lista de cotas excluídas com a scene
            if hasattr(laje, 'excluded_dimensions'):
                self.scene.excluded_dimensions = laje.excluded_dimensions.copy()
            else:
                self.scene.excluded_dimensions = []
            
            # Salvar valores atualizados na laje
            laje.modo_selecionado = modo_salvo
            laje.unioes_nos_bordes = unioes_salvo
            
            verticais = laje.linhas_verticais if laje.linhas_verticais else []
            horizontais = laje.linhas_horizontais if laje.linhas_horizontais else []
            self.set_linhas(verticais, horizontais)
            
            # Executar ações automáticas apenas se solicitado explicitamente
            # (normalmente ao criar/adicionar nova laje, não ao selecionar na lista)
            if aplicar_correcoes_automaticas:
                # INTERPRETAÇÃO INTELIGENTE AUTOMATIZADA
                # Quando selecionado via CAD, executamos apenas a dedução inteligente de layout
                # de forma silenciosa e automática.
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, lambda: self._perform_smart_interpret(silent=True))
        
        self.atualizar_visualizacao()
    
    def _aplicar_correcoes_apos_calcular(self):
        """Aplica cálculo de modo primeiro, depois correções"""
        if not self.laje_atual or not self.laje_atual.coordenadas:
            return
        
        # Calcular linhas com o modo selecionado
        modo = self.laje_atual.modo_selecionado
        coordenadas = self.laje_atual.coordenadas
        
        if modo == 0:
            resultado = calcular_modo1(coordenadas)
            if resultado:
                verticais, horizontais = resultado
                # Verificar limites de segurança
                from laje_src.services.geometry_calculator import MAX_LINHAS_VERTICAIS, MAX_LINHAS_HORIZONTAIS
                if not verticais and not horizontais or len(verticais) > MAX_LINHAS_VERTICAIS or len(horizontais) > MAX_LINHAS_HORIZONTAIS:
                    verticais, horizontais = [], []  # Não desenhar se exceder limites
            else:
                verticais, horizontais = [], []
        else:
            resultado = calcular_modo2(coordenadas)
            if resultado:
                verticais, horizontais = resultado
                # Verificar limites de segurança
                from laje_src.services.geometry_calculator import MAX_LINHAS_VERTICAIS, MAX_LINHAS_HORIZONTAIS
                if not verticais and not horizontais or len(verticais) > MAX_LINHAS_VERTICAIS or len(horizontais) > MAX_LINHAS_HORIZONTAIS:
                    verticais, horizontais = [], []  # Não desenhar se exceder limites
            else:
                verticais, horizontais = [], []
        
        self.set_linhas(verticais, horizontais)
        
        # Depois aplicar correções automáticas
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self.aplicar_correcoes_automaticas(salvar=True))
    
    def set_pavimento(self, nome_pavimento: str):
        """Define o pavimento atual e atualiza o canvas (para modo Pavimento)"""
        self.pavimento_atual = nome_pavimento
        if self.modo_visualizacao == "Pavimento" and self.obra_atual:
            pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == nome_pavimento), None)
            if pavimento and pavimento.lajes:
                # Definir primeira laje para referência (usada no modo Pavimento)
                self.laje_atual = pavimento.lajes[0]
            self.atualizar_visualizacao()
    
    def set_linhas(self, verticais: List[Any], horizontais: List[Any]):
        """Atualiza linhas verticais e horizontais"""
        # Evitar loop infinito
        if self._updating_overlays:
            return
        
        # Limpar flags de salvamento após aplicar mudanças
        if hasattr(self, '_correction_state_saved'):
            delattr(self, '_correction_state_saved')
        if hasattr(self, '_overlay_change_saved'):
            delattr(self, '_overlay_change_saved')
        
        self._updating_overlays = True
        
        try:
            # Desconectar sinais temporariamente para evitar loops
            self.vertical_lines_overlay.linhas_changed.disconnect()
            self.horizontal_lines_overlay.linhas_changed.disconnect()
            
            # Calcular dimensões totais da laje se disponível
            total_width = 0.0
            total_height = 0.0
            if self.laje_atual and self.laje_atual.coordenadas:
                coords = self.laje_atual.coordenadas
                min_x = min(x for x, y in coords)
                max_x = max(x for x, y in coords)
                min_y = min(y for x, y in coords)
                max_y = max(y for x, y in coords)
                total_width = max_x - min_x
                total_height = max_y - min_y
            
            # Atualizar overlays com dimensões totais
            # Passar flag para overlays evitarem cálculo de sobra durante IA
            if hasattr(self, '_skip_sobra_calculation') and self._skip_sobra_calculation:
                self.vertical_lines_overlay._skip_sobra_calculation = True
                self.horizontal_lines_overlay._skip_sobra_calculation = True
            
            self.vertical_lines_overlay.set_linhas(verticais if verticais else [], total_width)
            self.horizontal_lines_overlay.set_linhas(horizontais if horizontais else [], total_height)
            
            # Limpar flag após usar
            if hasattr(self, '_skip_sobra_calculation') and self._skip_sobra_calculation:
                self.vertical_lines_overlay._skip_sobra_calculation = False
                self.horizontal_lines_overlay._skip_sobra_calculation = False
            
            # Reconectar sinais (apenas se não for durante IA)
            # Durante IA, não queremos que mudanças disparem atualizações com cotas
            if not getattr(self, '_skip_sobra_calculation', False):
                self.vertical_lines_overlay.linhas_changed.connect(self.on_vertical_lines_changed)
                self.horizontal_lines_overlay.linhas_changed.connect(self.on_horizontal_lines_changed)
            
            # Reposicionar overlays após criar os campos
            from PySide6.QtCore import QTimer
            QTimer.singleShot(50, self.position_overlays)
        finally:
            self._updating_overlays = False
        
        if self.laje_atual and self.laje_atual.coordenadas:
            self.laje_atual.linhas_verticais = verticais
            self.laje_atual.linhas_horizontais = horizontais
            # Armazenar dados para edição
            obstaculos = getattr(self.laje_atual, 'obstaculos', [])
            
            # Reconectar sinais após atualizar modelo (se não foi durante IA)
            if not getattr(self, '_skip_sobra_calculation', False):
                # Garantir que sinais estejam conectados
                try:
                    self.vertical_lines_overlay.linhas_changed.disconnect()
                except:
                    pass
                try:
                    self.horizontal_lines_overlay.linhas_changed.disconnect()
                except:
                    pass
                self.vertical_lines_overlay.linhas_changed.connect(self.on_vertical_lines_changed)
                self.horizontal_lines_overlay.linhas_changed.connect(self.on_horizontal_lines_changed)
            self.scene.set_edition_data(
                self.laje_atual.coordenadas,
                verticais,
                horizontais,
                obstaculos
            )
            # Atualizar visualização (que vai redesenhar tudo conforme o modo)
            self.atualizar_visualizacao()
    
    def on_vertical_lines_changed(self, verticais: List[Any]):
        """Chamado quando linhas verticais mudam nos overlays"""
        # Evitar loops durante atualização programática
        if self._updating_overlays:
            return
        
        # Salvar estado antes de alterar (apenas uma vez por alteração manual)
        if self.laje_atual and not hasattr(self, '_overlay_change_saved'):
            self.undo_manager.save_state(self.laje_atual)
            self._overlay_change_saved = True
        
        horizontais = self.horizontal_lines_overlay.get_linhas()
        if self.laje_atual:
            self.laje_atual.linhas_verticais = verticais
            obstaculos = getattr(self.laje_atual, 'obstaculos', [])
            self.scene.set_edition_data(
                self.laje_atual.coordenadas,
                verticais,
                horizontais,
                obstaculos
            )
            # Atualizar visualização SEM cotas (cotas serão geradas pela IA cotas depois)
            self._skip_dimensions_during_update = True
            try:
                self.atualizar_visualizacao()
            finally:
                self._skip_dimensions_during_update = False
            # Emitir sinal para outros widgets
            self.linhas_edited.emit(verticais, horizontais)
    
    def on_horizontal_lines_changed(self, horizontais: List[Any]):
        """Chamado quando linhas horizontais mudam nos overlays"""
        # Evitar loops durante atualização programática
        if self._updating_overlays:
            return
        
        # Salvar estado antes de alterar (apenas uma vez por alteração manual)
        if self.laje_atual and not hasattr(self, '_overlay_change_saved'):
            self.undo_manager.save_state(self.laje_atual)
            self._overlay_change_saved = True
        
        verticais = self.vertical_lines_overlay.get_linhas()
        if self.laje_atual:
            self.laje_atual.linhas_horizontais = horizontais
            obstaculos = getattr(self.laje_atual, 'obstaculos', [])
            self.scene.set_edition_data(
                self.laje_atual.coordenadas,
                verticais,
                horizontais,
                obstaculos
            )
            # Atualizar visualização SEM cotas (cotas serão geradas pela IA cotas depois)
            self._skip_dimensions_during_update = True
            try:
                self.atualizar_visualizacao()
            finally:
                self._skip_dimensions_during_update = False
            # Emitir sinal para outros widgets
            self.linhas_edited.emit(verticais, horizontais)
    
    def setup_edition_connections(self):
        """Conecta sinais do toolbar de edição"""
        # Seleção
        self.edition_toolbar.select_mode_requested.connect(self.on_select_mode)
        
        # Fazer cota
        self.edition_toolbar.make_dimension_requested.connect(self.on_make_dimension)
        
        # Mover
        self.edition_toolbar.move_requested.connect(self.on_move_mode)
        
        # Offset
        self.edition_toolbar.offset_requested.connect(self.on_offset_mode)
        
        # Excluir
        self.edition_toolbar.delete_requested.connect(self.on_delete_lines)
        
        # Join
        self.edition_toolbar.join_requested.connect(self.on_join_lines)
        
        # Join Automático
        self.edition_toolbar.join_automatico_requested.connect(self.on_join_automatico)
        
        # Desfazer
        self.edition_toolbar.undo_requested.connect(self.on_undo)
        
        # Refazer Cotas Rosas
        self.edition_toolbar.refazer_cotas_requested.connect(self.refazer_cotas_rosas)
        
        # Eliminar Todas as Cotas
        self.edition_toolbar.delete_all_dimensions_requested.connect(self.delete_all_dimensions)
        
        # Alternar Vínculo (F)
        self.edition_toolbar.toggle_link_requested.connect(self.toggle_dimension_link)

        # Interpretação Inteligente
        self.edition_toolbar.smart_interpret_requested.connect(self.on_smart_interpret)

        # Validar como Treino
        self.edition_toolbar.train_validate_requested.connect(self.on_train_validate)
        self.edition_toolbar.validate_dimensions_training_requested.connect(self.on_validate_dimensions_training)

        # Regras de Interpretação
        self.edition_toolbar.rules_requested.connect(self.on_rules_requested)
        self.edition_toolbar.rules_dimensions_requested.connect(self.on_rules_dimensions_requested)

        # Cotas Inteligentes
        self.edition_toolbar.smart_dimensions_requested.connect(self.on_smart_dimensions_clicked)
        
        # Sobrescrever eventos de mouse do view
        self.view.mousePressEvent = self.on_view_mouse_press
        self.view.mouseMoveEvent = self.on_view_mouse_move
        self.view.mouseReleaseEvent = self.on_view_mouse_release
        self.view.keyPressEvent = self.on_view_key_press
    
    def on_select_mode(self):
        """Ativa modo de seleção"""
        self.scene.activate_selection_mode()
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        # Limpar seleção por retângulo se existir
        if self._selection_rubber_band:
            self._selection_rubber_band.hide()
        self._is_selecting = False
        self._is_deselecting = False
    
    def on_make_dimension(self):
        """Adiciona cotas para segmentos selecionados"""
        # Limpar linhas deletadas primeiro
        if hasattr(self.scene, 'selected_lines'):
            valid_lines = []
            for line in self.scene.selected_lines[:]:  # Usar cópia da lista
                try:
                    if line.scene() is not None:
                        valid_lines.append(line)
                except RuntimeError:
                    pass  # Objeto deletado, ignorar
            self.scene.selected_lines = valid_lines
        
        # Verificar especificamente se há linhas selecionadas (não apenas qualquer seleção)
        if not self.scene.selected_lines or len(self.scene.selected_lines) == 0:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Aviso",
                "Selecione uma ou mais linhas antes de fazer cotas.\n\n"
                "Use o botão 'Selecionar' e clique nas linhas que deseja cotar."
            )
            return
        
        try:
            self.scene.make_dimensions_for_selected()
            
            # Sincronizar imediatamente com o modelo para persistência
            self.sync_manual_dimensions_to_model()
            
            # Salvar estado para Undo
            if self.undo_manager:
                self.undo_manager.save_state(self.laje_atual)
            
            # Limpar seleção de forma robusta usando o método da cena
            self.scene.clear_selection()
            
            # Atualizar visualização para refletir as mudanças
            self.scene.update()
            # Não chamar atualizar_visualizacao() pois isso limparia as cotas recém-adicionadas
            # As cotas já foram adicionadas diretamente à cena
        except RuntimeError as e:
            # Se ainda houver erro, limpar seleção e mostrar mensagem
            self.scene.selected_lines.clear()
            print(f"[DEBUG] Erro ao fazer cotas: {e}")
    
    def on_move_mode(self):
        """Ativa modo de mover"""
        if not self.scene.has_selection():
            return
        
        if self.move_widget is None:
            self.move_widget = MoveCommandWidget()
            self.move_widget.move_requested.connect(self.on_move_lines)
            # Adicionar widget ao layout do toolbar
            self.edition_toolbar.layout().addWidget(self.move_widget)
        
        self.move_widget.setVisible(True)
        self.move_widget.distance_input.setFocus()
        self.edition_toolbar.mode = 'move'
        self.edition_toolbar.update_button_states()
        # Manter modo de seleção ativo na cena (não desativar)
    
    def on_offset_mode(self):
        """Ativa modo de offset"""
        if not self.scene.has_selection():
            return
        
        # Salvar estado antes de fazer offset
        if self.laje_atual:
            self.undo_manager.save_state(self.laje_atual)
        
        if self.offset_widget is None:
            self.offset_widget = OffsetCommandWidget()
            self.offset_widget.offset_requested.connect(self.on_offset_lines)
            # Adicionar widget ao layout do toolbar
            self.edition_toolbar.layout().addWidget(self.offset_widget)
        
        self.offset_widget.setVisible(True)
        self.offset_widget.distance_input.setFocus()
        self.edition_toolbar.mode = 'offset'
        self.edition_toolbar.update_button_states()
        # Manter modo de seleção ativo na cena (não desativar)
    
    def on_move_lines(self, distance: float, direction: str):
        """Move linhas selecionadas"""
        new_vert, new_horiz = self.scene.move_selected_lines(distance, direction)
        self.apply_line_changes(new_vert, new_horiz)
        # Voltar para modo de seleção após mover
        self.edition_toolbar.mode = 'select'
        self.edition_toolbar.update_button_states()
    
    def on_offset_lines(self, distance: float, direction: str):
        """Cria offset (cópia) das linhas selecionadas"""
        new_vert, new_horiz = self.scene.offset_selected_lines(distance, direction)
        self.apply_line_changes(new_vert, new_horiz)
        # Voltar para modo de seleção após offset
        self.edition_toolbar.mode = 'select'
        self.edition_toolbar.update_button_states()
    
    def on_join_lines(self):
        """Faz join de linhas selecionadas"""
        if not self.scene.has_selection():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Aviso",
                "Selecione duas ou mais linhas que sejam continuação uma da outra antes de fazer join."
            )
            return
        
        # Salvar estado antes de fazer join
        if self.laje_atual:
            self.undo_manager.save_state(self.laje_atual)
        
        # Fazer join das linhas selecionadas
        new_vert, new_horiz = self.scene.join_selected_lines()
        
        # Salvar posições unificadas na laje atual
        if self.laje_atual:
            # Converter sets para listas para salvar
            self.laje_atual.marco_joined_positions = {
                'vertical': list(self.scene.marco_joined_positions['vertical']),
                'horizontal': list(self.scene.marco_joined_positions['horizontal'])
            }
        
        # O join não altera as distâncias, apenas une segmentos visuais do marco
        # Apenas atualizar a cena para mostrar o join, sem recriar tudo
        self.scene.update()
    
    def on_join_automatico(self):
        """Faz join automático de linhas segmentadas"""
        # Salvar estado antes de fazer join automático
        if self.laje_atual:
            self.undo_manager.save_state(self.laje_atual)
        
        # Fazer join automático de todas as linhas
        new_vert, new_horiz = self.scene.join_automatico()
        
        # Salvar posições unificadas na laje atual
        if self.laje_atual:
            # Converter sets para listas para salvar
            self.laje_atual.marco_joined_positions = {
                'vertical': list(self.scene.marco_joined_positions['vertical']),
                'horizontal': list(self.scene.marco_joined_positions['horizontal'])
            }
        
        # O join não altera as distâncias, apenas une segmentos visuais do marco
        # Apenas atualizar a cena para mostrar o join, sem recriar tudo
        self.scene.update()
    
    def on_undo(self):
        """Desfaz a última ação"""
        if not self.laje_atual:
            return
        
        if self.undo_manager.undo(self.laje_atual):
            # Atualizar overlays primeiro (sem salvar estado durante atualização)
            if self.laje_atual:
                verticais = self.laje_atual.linhas_verticais if self.laje_atual.linhas_verticais else []
                horizontais = self.laje_atual.linhas_horizontais if self.laje_atual.linhas_horizontais else []
                # Usar set_linhas que já atualiza tudo
                self.set_linhas(verticais, horizontais)
                # Atualizar visualização completa
                self.atualizar_visualizacao()

    def refazer_cotas_rosas(self):
        """Refaz as cotas verticais (rosa), limpando posições manuais e reaplicando o ordenamento automático."""
        if not self.scene or not self.laje_atual:
            return
            
        # ATUALIZAÇÃO SOLICITADA: Remover confirmação e garantir recriação completa
        # Limpar posições manuais E lista de exclusões
        try:
            # Salvar estado para desfazer se necessário
            self.undo_manager.save_state(self.laje_atual)
            
            # Limpar posições salvas de cotas na cena
            if hasattr(self.scene, 'saved_dimension_positions'):
                self.scene.saved_dimension_positions = {}
                
            # Limpar cotas excluídas na cena (para que voltem a aparecer)
            if hasattr(self.scene, 'excluded_dimensions'):
                self.scene.excluded_dimensions = []
            
            # Limpar dados na laje atual
            if hasattr(self.laje_atual, 'dimension_positions'):
                self.laje_atual.dimension_positions = {}
                
            # IMPORTANTE: Limpar lista de exclusões para que cotas deletadas voltem
            if hasattr(self.laje_atual, 'excluded_dimensions'):
                self.laje_atual.excluded_dimensions = []
                print("[DEBUG] Lista de exclusões limpa - cotas devem reaparecer")
            
            # Atualizar visualização (irá redesenhar cotas automaticamente)
            self.atualizar_visualizacao(immediate=True)
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao refazer cotas: {str(e)}")
            import traceback
            traceback.print_exc()

    def delete_all_dimensions(self):
        """Exclui todas as cotas da laje atual (automáticas, especiais e manuais)."""
        if not self.scene or not self.laje_atual:
            return
            
        # ATUALIZAÇÃO SOLICITADA: Remover confirmação
        # Sem QMessageBox.question
            
        try:
            # Salvar estado para desfazer
            self.undo_manager.save_state(self.laje_atual)
            
            # 1. Identificar todas as cotas automáticas e especiais para excluí-las
            # Coletar dados completos para que o draw_dimensions possa ignorá-las via _should_draw_dimension
            exclusions_to_add = []
            for dim_text in self.scene.dimension_texts + self.scene.special_dimensions:
                if hasattr(dim_text, 'dimension_id') and dim_text.dimension_id:
                    pos = dim_text.pos()
                    dim_data = {
                        "type": getattr(dim_text, 'dim_type', 'auto'),
                        "x": round(pos.x(), 1),
                        "y": round(pos.y(), 1),
                        "value": dim_text.toPlainText(),
                        "rotation": round(dim_text.rotation(), 1),
                        "unique_id": dim_text.dimension_id
                    }
                    exclusions_to_add.append(dim_data)
            
            # 2. Limpar listas da laje_atual
            if self.laje_atual:
                # Converter para lista de exclusão para que não voltem no draw_dimensions
                if not hasattr(self.laje_atual, 'excluded_dimensions'):
                    self.laje_atual.excluded_dimensions = []
                
                # Criar um set de IDs existentes para evitar o TypeError de hash com dicionários
                existing_uids = set()
                for e in self.laje_atual.excluded_dimensions:
                    if isinstance(e, dict):
                        uid = e.get("unique_id")
                        if uid: existing_uids.add(uid)
                    elif isinstance(e, str):
                        existing_uids.add(e)
                
                # Adicionar novas exclusões no formato de dicionário
                for dim_dict in exclusions_to_add:
                    uid = dim_dict.get("unique_id")
                    if uid not in existing_uids:
                        self.laje_atual.excluded_dimensions.append(dim_dict)
                        existing_uids.add(uid)
                
                # Limpar dados permanentes de cotas manuais e modificações
                self.laje_atual.manual_dimensions = []
                self.laje_atual.dimension_positions = {}
                if hasattr(self.laje_atual, 'modified_dimensions'):
                    self.laje_atual.modified_dimensions = {}
            
            # 3. Limpar cena física e listas da cena
            for dim_text in self.scene.dimension_texts + self.scene.special_dimensions + self.scene.manual_dimension_texts:
                try:
                    if dim_text.scene() == self.scene:
                        self.scene.removeItem(dim_text)
                except:
                    pass
            
            self.scene.dimension_texts = []
            self.scene.special_dimensions = []
            self.scene.manual_dimension_texts = []
            self.scene.manual_dimension_data = {}
            self.scene.excluded_dimensions = list(self.laje_atual.excluded_dimensions) if self.laje_atual else []
            self.scene.saved_dimension_positions = {}
            
            # 4. Atualizar visualização
            self.atualizar_visualizacao(immediate=True)
            
            # QMessageBox.information(self, "Sucesso", "Todas as cotas foram removidas.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao excluir cotas: {str(e)}")
            import traceback
            traceback.print_exc()

    def toggle_dimension_link(self):
        """Alterna o status de vínculo (cor) das cotas selecionadas."""
        if not self.scene or not self.laje_atual:
            return
            
        selected_items = [item for item in self.scene.selectedItems() if isinstance(item, QGraphicsTextItem)]
        if not selected_items:
            return
            
        try:
            # Salvar estado para desfazer
            self.undo_manager.save_state(self.laje_atual)
            
            from PySide6.QtGui import QColor
            
            changed = False
            for item in selected_items:
                # Verificar se é uma cota válida
                if (item in self.scene.dimension_texts or 
                    item in self.scene.special_dimensions or 
                    item in self.scene.manual_dimension_texts):
                    
                    # Alternar a flag is_marco_special
                    is_special = getattr(item, 'is_marco_special', False)
                    new_special = not is_special
                    item.is_marco_special = new_special
                    
                    # Mudar cor do texto (Red para especial, Pink para normal)
                    # Nota: Algumas cotas (marco total) são verdes, mas o usuário quer alternar "vínculo"
                    # que geralmente é entre Rosa e Vermelho nas cotas automáticas.
                    if new_special:
                        item.setDefaultTextColor(QColor(f"{DS.DANGER}")) # Vermelho
                    else:
                        # Restaurar cor natural baseada no tipo
                        d_type = getattr(item, 'dim_type', '')
                        if d_type == 'marco':
                            item.setDefaultTextColor(QColor(f"{DS.SUCCESS}")) # Verde
                        elif d_type == 'special':
                            item.setDefaultTextColor(QColor(f"{DS.WHITE}f00")) # Amarelo
                        elif d_type == 'manual':
                            item.setDefaultTextColor(QColor(f"{DS.WHITE}f00")) # Amarelo (Cotas Manuais)
                        else:
                            item.setDefaultTextColor(QColor(f"{DS.MAGENTA}")) # Rosa (Auto)
                    
                    # Salvar no modified_dimensions da laje para persistência
                    if hasattr(item, 'dimension_id') and item.dimension_id:
                        if not hasattr(self.laje_atual, 'modified_dimensions'):
                            self.laje_atual.modified_dimensions = {}
                        self.laje_atual.modified_dimensions[item.dimension_id] = {
                            "is_marco_special": new_special,
                            "pos_x": round(item.pos().x(), 1),
                            "pos_y": round(item.pos().y(), 1),
                            "value": item.toPlainText(),
                            "rotation": round(item.rotation(), 1)
                        }
                    
                    changed = True
            
            if changed:
                # Se houver itens selecionados, forçar atualização do highlight do vínculo
                if hasattr(self.scene, '_on_selection_changed'):
                    self.scene._on_selection_changed()
                self.scene.update()
                
        except Exception as e:
            print(f"[ERRO] toggle_dimension_link: {e}")
    
    def on_delete_lines(self):
        """Exclui linhas e cotas selecionadas"""
        # Salvar estado antes de excluir
        if self.laje_atual:
            self.undo_manager.save_state(self.laje_atual)
        
        # Verificar se há cotas selecionadas - APENAS as que estão realmente selecionadas
        selected_dimensions = []
        for item in self.scene.items():
            # Verificar se é um QGraphicsTextItem e está selecionado
            if isinstance(item, QGraphicsTextItem):
                # Verificar se está realmente selecionado (dupla verificação)
                if item.isSelected():
                    # Verificar se é uma cota válida (está na lista de dimension_texts, special_dimensions ou manual_dimension_texts)
                    if (item in self.scene.dimension_texts or 
                        item in self.scene.special_dimensions or 
                        item in self.scene.manual_dimension_texts):
                        selected_dimensions.append(item)
        
        # Deletar cotas selecionadas e salvar identificadores
        if not hasattr(self.scene, 'laje_coords') or not self.scene.laje_coords:
            return
        
        for dim_text in selected_dimensions:
            # Determinar tipo da cota usando o novo atributo dim_type se disponível
            dim_type = getattr(dim_text, 'dim_type', 'manual')
            if not hasattr(dim_text, 'dim_type'):
                if dim_text in self.scene.dimension_texts:
                    dim_type = "auto"
                elif dim_text in self.scene.special_dimensions:
                    dim_type = "special"
            
            # Para cotas manuais, usar dados únicos armazenados
            if dim_type == "manual" and dim_text in self.scene.manual_dimension_data:
                dim_data = self.scene.manual_dimension_data[dim_text]
                # Criar identificador único usando dados da linha e ID único
                dim_id = {
                    "type": dim_type,
                    "unique_id": dim_data.get("unique_id", ""),
                    "line_coords": dim_data.get("line_coords", (0, 0, 0, 0)),
                    "x": dim_data.get("pos_x", 0),
                    "y": dim_data.get("pos_y", 0),
                    "value": dim_text.toPlainText(),
                    "rotation": dim_data.get("rotation", 0),
                    "length": dim_data.get("length", 0)
                }
            else:
                # Para cotas automáticas ou especiais, incluir dimension_id se disponível
                pos = dim_text.pos()
                value = dim_text.toPlainText()
                rotation = dim_text.rotation()
                dim_id = {
                    "type": dim_type,
                    "x": round(pos.x(), 2),  # Maior precisão
                    "y": round(pos.y(), 2),
                    "value": value,
                    "rotation": round(rotation, 2)
                }
                # Incluir dimension_id se a cota tiver esse atributo (importante para comparação precisa)
                if hasattr(dim_text, 'dimension_id') and dim_text.dimension_id:
                    dim_id["unique_id"] = dim_text.dimension_id

                # Se for do marco, garantir que o tipo seja "marco"
                # Incluir "marco_" em qualquer lugar do nome (cobre "marco_..." e "dim_line_marco_...")
                if dim_text.toPlainText() and hasattr(dim_text, 'dimension_id') and dim_text.dimension_id and ('marco_' in dim_text.dimension_id or 'dim_line_marco_' in dim_text.dimension_id):
                    dim_id["type"] = "marco"
                    dim_type = "marco"

            # Adicionar à lista de cotas excluídas na laje atual
            if self.laje_atual:
                # Para cotas com unique_id (manuais ou automáticas), usar comparação exata por ID
                if dim_id.get("unique_id"):
                    exists = False
                    for existing in self.laje_atual.excluded_dimensions:
                        if existing.get("unique_id") == dim_id.get("unique_id"):
                            exists = True
                            break
                else:
                    # Para cotas sem unique_id, usar comparação com tolerância
                    exists = False
                    for existing in self.laje_atual.excluded_dimensions:
                        if (existing.get("type") == dim_id["type"] and
                            abs(existing.get("x", 0) - dim_id["x"]) < 0.5 and
                            abs(existing.get("y", 0) - dim_id["y"]) < 0.5 and
                            existing.get("value", "").strip() == dim_id["value"].strip() and
                            abs(existing.get("rotation", 0) - dim_id["rotation"]) < 1.0):
                            exists = True
                            break
                
                if not exists:
                    self.laje_atual.excluded_dimensions.append(dim_id)
                    # Sincronizar com a scene também
                    if dim_id not in self.scene.excluded_dimensions:
                        self.scene.excluded_dimensions.append(dim_id)
            
            # Remover das listas
            if dim_text in self.scene.dimension_texts:
                self.scene.dimension_texts.remove(dim_text)
            if dim_text in self.scene.special_dimensions:
                self.scene.special_dimensions.remove(dim_text)
            if dim_text in self.scene.manual_dimension_texts:
                self.scene.manual_dimension_texts.remove(dim_text)
            # Remover dados únicos se for cota manual
            if dim_text in self.scene.manual_dimension_data:
                del self.scene.manual_dimension_data[dim_text]
            
            self.scene.removeItem(dim_text)
        
        # Verificar se há linhas selecionadas
        if not self.scene.has_selection():
            return
        
        new_vert, new_horiz = self.scene.delete_selected_lines()
        self.apply_line_changes(new_vert, new_horiz)
        self.scene.clear_selection()
        # Manter modo de seleção ativo
    
    def apply_line_changes(self, new_vert: List[float], new_horiz: List[float]):
        """Aplica mudanças nas linhas e atualiza"""
        # Limpar flag de move_state_saved após aplicar mudanças
        if hasattr(self.scene, '_move_state_saved'):
            delattr(self.scene, '_move_state_saved')
        
        if self.laje_atual:
            # Fazer cópias das listas para evitar referências compartilhadas
            new_vert_copy = list(new_vert) if new_vert else []
            new_horiz_copy = list(new_horiz) if new_horiz else []
            
            # Atualizar a laje atual com as cópias
            self.laje_atual.linhas_verticais = new_vert_copy
            self.laje_atual.linhas_horizontais = new_horiz_copy
            
            # Calcular dimensões totais para atualizar overlays corretamente
            total_width = 0.0
            total_height = 0.0
            if self.laje_atual.coordenadas:
                coords = self.laje_atual.coordenadas
                min_x = min(x for x, y in coords)
                max_x = max(x for x, y in coords)
                min_y = min(y for x, y in coords)
                max_y = max(y for x, y in coords)
                total_width = max_x - min_x
                total_height = max_y - min_y
            
            # Atualizar overlays com novos valores
            try:
                self._updating_overlays = True
                # Desconectar temporariamente
                self.vertical_lines_overlay.linhas_changed.disconnect()
                self.horizontal_lines_overlay.linhas_changed.disconnect()
                
                self.vertical_lines_overlay.set_linhas(new_vert_copy, total_width)
                self.horizontal_lines_overlay.set_linhas(new_horiz_copy, total_height)
                
                # Reconectar
                self.vertical_lines_overlay.linhas_changed.connect(self.on_vertical_lines_changed)
                self.horizontal_lines_overlay.linhas_changed.connect(self.on_horizontal_lines_changed)
                
                # Reposicionar overlays
                from PySide6.QtCore import QTimer
                QTimer.singleShot(50, self.position_overlays)
            except Exception as e:
                print(f"[ERRO] apply_line_changes: {e}")
            finally:
                self._updating_overlays = False
            
            obstaculos = getattr(self.laje_atual, 'obstaculos', [])
            self.scene.set_edition_data(
                self.laje_atual.coordenadas,
                new_vert_copy,
                new_horiz_copy,
                obstaculos
            )
            # Emitir sinal para atualizar campos de linhas (usar cópias)
            self.linhas_edited.emit(new_vert_copy, new_horiz_copy)
            # Atualizar visualização
            self.atualizar_visualizacao()
    
    def on_view_mouse_press(self, event: QMouseEvent):
        """Manipula eventos de mouse no view"""
        if self.scene.selection_mode:
            # Modo de seleção ativo
            if event.button() == Qt.MouseButton.LeftButton:
                # Botão esquerdo: iniciar seleção por retângulo
                # Obter item no ponto do clique (priorizar item do topo)
                scene_pos = self.view.mapToScene(event.pos())
                items_at_pos = self.scene.items(scene_pos, Qt.ItemSelectionMode.IntersectsItemBoundingRect)
                
                from PySide6.QtWidgets import QGraphicsLineItem
                
                # Encontrar o primeiro item relevante (cota ou linha)
                clicked_item = None
                is_dimension = False
                
                for item in items_at_pos:
                    # Priorizar cotas sobre linhas
                    if isinstance(item, QGraphicsTextItem) and \
                       (item in self.scene.dimension_texts or 
                        item in self.scene.special_dimensions or 
                        item in self.scene.manual_dimension_texts):
                        clicked_item = item
                        is_dimension = True
                        break
                    elif isinstance(item, QGraphicsLineItem) and \
                         (item in self.scene.vertical_lines or item in self.scene.horizontal_lines or 
                          item in self.scene.marco_segments):
                        clicked_item = item
                        is_dimension = False
                        break
                
                # Se não encontrou item exato, verificar se o clique está próximo a uma cota (área maior)
                if clicked_item is None:
                    tolerance = 5.0  # Tolerância em pixels da view
                    for item in self.scene.items():
                        if isinstance(item, QGraphicsTextItem) and \
                           (item in self.scene.dimension_texts or 
                            item in self.scene.special_dimensions or 
                            item in self.scene.manual_dimension_texts):
                            # Obter bounding rect na view
                            item_scene_rect = item.sceneBoundingRect()
                            item_view_rect = self.view.mapFromScene(item_scene_rect).boundingRect()
                            # Expandir área de clique
                            expanded_rect = item_view_rect.adjusted(-tolerance, -tolerance, tolerance, tolerance)
                            if expanded_rect.contains(event.pos()):
                                clicked_item = item
                                is_dimension = True
                                break
                
                if clicked_item:
                    if is_dimension:
                        # Clicou em uma cota
                        modifiers = event.modifiers()
                        
                        # Se a cota tem ItemIsMovable, permitir arrasto
                        if clicked_item.flags() & QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable:
                            if modifiers & Qt.KeyboardModifier.ControlModifier:
                                # Ctrl+Click: toggle seleção sem arrastar
                                if clicked_item.isSelected():
                                    clicked_item.setSelected(False)
                                else:
                                    clicked_item.setSelected(True)
                                event.accept()
                                return
                            else:
                                # Click simples: selecionar e permitir arrasto
                                # Deselecionar todas as cotas primeiro
                                for dim_item in self.scene.items():
                                    if isinstance(dim_item, QGraphicsTextItem):
                                        if (dim_item in self.scene.dimension_texts or 
                                            dim_item in self.scene.special_dimensions or 
                                            dim_item in self.scene.manual_dimension_texts):
                                            dim_item.setSelected(False)
                                # Selecionar a cota clicada
                                clicked_item.setSelected(True)
                                # NÃO interceptar o evento - deixar passar para o Qt gerenciar o arrasto
                                # Chamar o comportamento padrão do QGraphicsView (super da classe base)
                                # Isso permite que o Qt detecte o item selecionado e inicie o arrasto
                                QGraphicsView.mousePressEvent(self.view, event)
                                return
                        else:
                            # Cota não é movível - apenas selecionar
                            if modifiers & Qt.KeyboardModifier.ControlModifier:
                                # Ctrl+Click: toggle seleção
                                if clicked_item.isSelected():
                                    clicked_item.setSelected(False)
                                else:
                                    clicked_item.setSelected(True)
                            else:
                                # Click simples: selecionar apenas essa cota
                                for dim_item in self.scene.items():
                                    if isinstance(dim_item, QGraphicsTextItem):
                                        if (dim_item in self.scene.dimension_texts or 
                                            dim_item in self.scene.special_dimensions or 
                                            dim_item in self.scene.manual_dimension_texts):
                                            dim_item.setSelected(False)
                                clicked_item.setSelected(True)
                            event.accept()
                            return
                    else:
                        # Clicou em uma linha
                        self.scene.select_line(clicked_item)
                    event.accept()
                    return
                else:
                    # Clicou no vazio - iniciar seleção por retângulo
                    self._selection_start = event.pos()
                    self._is_selecting = True
                    self._is_deselecting = False
                    # Criar ou reutilizar rubber band
                    if self._selection_rubber_band is None:
                        self._selection_rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.view)
                        self._selection_rubber_band.setStyleSheet(f"border: 2px dashed {DS.WHITE}f00; background-color: rgba(255, 255, 0, 30);")
                    # Iniciar com retângulo mínimo
                    initial_rect = QRectF(self._selection_start, self._selection_start).toRect()
                    self._selection_rubber_band.setGeometry(initial_rect)
                    self._selection_rubber_band.show()
                    self._selection_rubber_band.raise_()  # Garantir que está no topo
                    event.accept()
                    return
            elif event.button() == Qt.MouseButton.RightButton:
                # Botão direito: iniciar deseleção por retângulo
                # Obter item no ponto do clique (priorizar item do topo)
                scene_pos = self.view.mapToScene(event.pos())
                items_at_pos = self.scene.items(scene_pos, Qt.ItemSelectionMode.IntersectsItemBoundingRect)
                
                from PySide6.QtWidgets import QGraphicsLineItem
                
                # Encontrar o primeiro item relevante (cota ou linha)
                clicked_item = None
                is_dimension = False
                
                for item in items_at_pos:
                    # Priorizar cotas sobre linhas
                    if isinstance(item, QGraphicsTextItem) and \
                       (item in self.scene.dimension_texts or 
                        item in self.scene.special_dimensions or 
                        item in self.scene.manual_dimension_texts):
                        clicked_item = item
                        is_dimension = True
                        break
                    elif isinstance(item, QGraphicsLineItem) and \
                         (item in self.scene.vertical_lines or item in self.scene.horizontal_lines or 
                          item in self.scene.marco_segments):
                        clicked_item = item
                        is_dimension = False
                        break
                
                # Se não encontrou item exato, verificar se o clique está próximo a uma cota (área maior)
                if clicked_item is None:
                    tolerance = 5.0  # Tolerância em pixels da view
                    for item in self.scene.items():
                        if isinstance(item, QGraphicsTextItem) and \
                           (item in self.scene.dimension_texts or 
                            item in self.scene.special_dimensions or 
                            item in self.scene.manual_dimension_texts):
                            # Obter bounding rect na view
                            item_scene_rect = item.sceneBoundingRect()
                            item_view_rect = self.view.mapFromScene(item_scene_rect).boundingRect()
                            # Expandir área de clique
                            expanded_rect = item_view_rect.adjusted(-tolerance, -tolerance, tolerance, tolerance)
                            if expanded_rect.contains(event.pos()):
                                clicked_item = item
                                is_dimension = True
                                break
                
                if clicked_item:
                    if is_dimension:
                        # Comportamento de clique em cota: Toggle selection se Shift/Ctrl ou apenas ADICIONAR se padrão (solicitado pelo usuário)
                        # O usuário pediu "seleções contínuas", ou seja, clicar em um novo não desmarca os outros
                        # Para desmarcar, clicar novamente nele
                        clicked_item.setSelected(not clicked_item.isSelected())
                        event.accept()
                        return
                    elif not is_dimension and clicked_item in self.scene.selected_lines:
                        # Clicou em uma linha JÁ selecionada - deselecionar (toggle)
                        self.scene.deselect_line(clicked_item)
                        event.accept()
                        return
                    # Se não clicou em item selecionado, iniciar deseleção por retângulo
                else:
                    # Clicou no vazio ou em linha não selecionada - iniciar deseleção por retângulo
                    self._selection_start = event.pos()
                    self._is_selecting = False
                    self._is_deselecting = True
                    # Criar ou reutilizar rubber band
                    if self._selection_rubber_band is None:
                        self._selection_rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.view)
                        self._selection_rubber_band.setStyleSheet(f"border: 2px dashed {DS.DANGER}; background-color: rgba(255, 0, 0, 30);")
                    # Iniciar com retângulo mínimo
                    initial_rect = QRectF(self._selection_start, self._selection_start).toRect()
                    self._selection_rubber_band.setGeometry(initial_rect)
                    self._selection_rubber_band.show()
                    self._selection_rubber_band.raise_()  # Garantir que está no topo
                    event.accept()
                    return
        
        # Comportamento padrão
        CustomGraphicsView.mousePressEvent(self.view, event)
    
    def on_view_mouse_move(self, event: QMouseEvent):
        """Manipula movimento do mouse para seleção por retângulo"""
        if self._is_selecting or self._is_deselecting:
            # Atualizar retângulo de seleção
            if self._selection_start and self._selection_rubber_band:
                # Criar retângulo normalizado
                start = self._selection_start
                end = event.pos()
                rect = QRectF(
                    min(start.x(), end.x()),
                    min(start.y(), end.y()),
                    abs(end.x() - start.x()),
                    abs(end.y() - start.y())
                ).toRect()
                self._selection_rubber_band.setGeometry(rect)
            event.accept()
            return
        
        # Comportamento padrão
        CustomGraphicsView.mouseMoveEvent(self.view, event)
    
    def on_view_mouse_release(self, event: QMouseEvent):
        """Manipula soltura do mouse para finalizar seleção por retângulo"""
        if self._is_selecting or self._is_deselecting:
            if self._selection_start and self._selection_rubber_band:
                # Converter retângulo da view para coordenadas da cena
                start_scene = self.view.mapToScene(self._selection_start)
                end_scene = self.view.mapToScene(event.pos())
                # Normalizar retângulo manualmente
                selection_rect_scene = QRectF(
                    min(start_scene.x(), end_scene.x()),
                    min(start_scene.y(), end_scene.y()),
                    abs(end_scene.x() - start_scene.x()),
                    abs(end_scene.y() - start_scene.y())
                )
                
                # Selecionar/deselecionar linhas dentro do retângulo
                from PySide6.QtWidgets import QGraphicsLineItem
                from shapely.geometry import LineString, Polygon
                lines_in_rect = []
                
                # Criar polígono do retângulo de seleção
                selection_poly = Polygon([
                    (selection_rect_scene.left(), selection_rect_scene.top()),
                    (selection_rect_scene.right(), selection_rect_scene.top()),
                    (selection_rect_scene.right(), selection_rect_scene.bottom()),
                    (selection_rect_scene.left(), selection_rect_scene.bottom())
                ])
                
                # Verificar linhas verticais
                for line in self.scene.vertical_lines:
                    line_item = line.line()
                    line_geom = LineString([
                        (line_item.x1(), line_item.y1()),
                        (line_item.x2(), line_item.y2())
                    ])
                    if selection_poly.intersects(line_geom):
                        lines_in_rect.append(line)
                
                # Verificar linhas horizontais
                for line in self.scene.horizontal_lines:
                    line_item = line.line()
                    line_geom = LineString([
                        (line_item.x1(), line_item.y1()),
                        (line_item.x2(), line_item.y2())
                    ])
                    if selection_poly.intersects(line_geom):
                        lines_in_rect.append(line)
                
                # Verificar segmentos do marco
                for line in self.scene.marco_segments:
                    line_item = line.line()
                    line_geom = LineString([
                        (line_item.x1(), line_item.y1()),
                        (line_item.x2(), line_item.y2())
                    ])
                    if selection_poly.intersects(line_geom):
                        lines_in_rect.append(line)
                
                # Verificar cotas dentro do retângulo
                dimensions_in_rect = []
                for item in self.scene.items():
                    if isinstance(item, QGraphicsTextItem):
                        if (item in self.scene.dimension_texts or 
                            item in self.scene.special_dimensions or 
                            item in self.scene.manual_dimension_texts):
                            # Obter bounding rect na cena (já considera rotação e posição)
                            item_scene_rect = item.sceneBoundingRect()
                            
                            # Verificar interseção com retângulo de seleção
                            if selection_rect_scene.intersects(item_scene_rect):
                                dimensions_in_rect.append(item)
                
                # Aplicar seleção/deseleção para linhas
                for line in lines_in_rect:
                    if self._is_selecting:
                        self.scene.select_line(line)
                    elif self._is_deselecting:
                        # Deselecionar apenas se a linha estiver selecionada
                        if line in self.scene.selected_lines:
                            self.scene.deselect_line(line)
                
                # Aplicar seleção/deseleção para cotas
                for dim_item in dimensions_in_rect:
                    if self._is_selecting:
                        dim_item.setSelected(True)
                    elif self._is_deselecting:
                        if dim_item.isSelected():
                            dim_item.setSelected(False)
                
                # Limpar retângulo de seleção
                self._selection_rubber_band.hide()
                self._selection_start = None
                self._is_selecting = False
                self._is_deselecting = False
            
            event.accept()
            return
        
        # Comportamento padrão
        CustomGraphicsView.mouseReleaseEvent(self.view, event)
    
    def on_view_key_press(self, event: QKeyEvent):
        """Manipula eventos de teclado no view"""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Verificar modo de erro de feedback
            if getattr(self, '_feedback_error_mode', False):
                # Emitir sinal para a MainWindow finalizar (pegar comentário do Widget)
                self.ai_feedback_finalize_requested.emit()
                event.accept()
                return

            # Enter: apenas limpa seleção, mas mantém modo de seleção ativo
            if self.scene.selection_mode:
                self.scene.clear_selection()
                # Limpar seleção por retângulo se estiver ativa
                if self._selection_rubber_band:
                    self._selection_rubber_band.hide()
                self._is_selecting = False
                self._is_deselecting = False
                event.accept()
                return
        elif event.key() == Qt.Key.Key_Escape:
            # ESC: cancela qualquer seleção
            self.scene.clear_selection()
            # Limpar seleção por retângulo se estiver ativa
            if self._selection_rubber_band:
                self._selection_rubber_band.hide()
            self._is_selecting = False
            self._is_deselecting = False
            event.accept()
            return
        
        # Comportamento padrão
        CustomGraphicsView.keyPressEvent(self.view, event)
    
    def eventFilter(self, obj, event):
        """Filtra eventos para reposicionar overlays quando container é redimensionado"""
        if obj == self.view_container and event.type() == QEvent.Type.Resize:
            self.position_overlays()
        return super().eventFilter(obj, event)
    
    def on_modo_calculo_selecionado(self, modo_index: int):
        """Chamado quando um modo de cálculo é selecionado"""
        # Verificar se há uma laje selecionada com coordenadas
        if not self.laje_atual or not self.laje_atual.coordenadas:
            return
        
        # Salvar modo na laje
        self.laje_atual.modo_selecionado = modo_index
        
        # Modo 0 = M1
        if modo_index == 0:
            # Calcular linhas usando o Modo 1
            coordenadas = self.laje_atual.coordenadas
            resultado = calcular_modo1(coordenadas)
            if resultado:
                verticais, horizontais = resultado
                # Verificar limites de segurança
                from laje_src.services.geometry_calculator import MAX_LINHAS_VERTICAIS, MAX_LINHAS_HORIZONTAIS
                if not verticais and not horizontais or len(verticais) > MAX_LINHAS_VERTICAIS or len(horizontais) > MAX_LINHAS_HORIZONTAIS:
                    verticais, horizontais = [], []  # Não desenhar se exceder limites
            else:
                verticais, horizontais = [], []
            
            # Aplicar as linhas calculadas
            self.set_linhas(verticais, horizontais)
        elif modo_index == 1:
            # Modo 1 = M2 (inverte a lógica do M1)
            # Calcular linhas usando o Modo 2
            coordenadas = self.laje_atual.coordenadas
            resultado = calcular_modo2(coordenadas)
            if resultado:
                verticais, horizontais = resultado
                # Verificar limites de segurança
                from laje_src.services.geometry_calculator import MAX_LINHAS_VERTICAIS, MAX_LINHAS_HORIZONTAIS
                if not verticais and not horizontais or len(verticais) > MAX_LINHAS_VERTICAIS or len(horizontais) > MAX_LINHAS_HORIZONTAIS:
                    verticais, horizontais = [], []  # Não desenhar se exceder limites
            else:
                verticais, horizontais = [], []
            
            # Aplicar as linhas calculadas
            self.set_linhas(verticais, horizontais)
    
    def on_unioes_bordes_changed(self, state: int):
        """Chamado quando o checkbox 'Uniões nos bordes' é alterado"""
        # Verificar se há uma laje selecionada
        if not self.laje_atual:
            return
        
        # Salvar estado do checkbox na laje (state é 0 (unchecked) ou 2 (checked))
        self.laje_atual.unioes_nos_bordes = (state == Qt.CheckState.Checked.value or state == 2)
        
        # Se há linhas calculadas, aplicar correções automáticas
        if self.laje_atual.linhas_verticais or self.laje_atual.linhas_horizontais:
            self.aplicar_correcoes_automaticas(salvar=True)
    
    def on_unioes_ilhas_esquerda_changed(self, state: int):
        """Chamado quando o checkbox 'Uniões Ilhas Esquerda/Fundo' é alterado"""
        # Verificar se há uma laje selecionada
        if not self.laje_atual:
            return
        
        # Se checkbox foi marcado, aplicar sequência automática: 5x(122x60) + ajustar_sobra
        # (o alinhamento de ilhas será aplicado durante esses processos)
        if state == Qt.CheckState.Checked.value or state == 2:
            # Verificar se há linhas para processar
            if self.laje_atual.linhas_verticais or self.laje_atual.linhas_horizontais:
                self.aplicar_correcoes_automaticas_com_ilhas(salvar=True)
            else:
                # Se não há linhas, tentar aplicar apenas o alinhamento
                self.alinhar_unioes_ilhas_esquerda()
    
    def on_unioes_ilhas_direita_changed(self, state: int):
        """Chamado quando o checkbox 'Uniões Ilhas Direita/Topo' é alterado"""
        # Verificar se há uma laje selecionada
        if not self.laje_atual:
            return
        
        # Se checkbox foi marcado, aplicar sequência automática: 5x(122x60) + ajustar_sobra
        # (o alinhamento de ilhas será aplicado durante esses processos)
        if state == Qt.CheckState.Checked.value or state == 2:
            # Verificar se há linhas para processar
            if self.laje_atual.linhas_verticais or self.laje_atual.linhas_horizontais:
                self.aplicar_correcoes_automaticas_com_ilhas(salvar=True)
            else:
                # Se não há linhas, tentar aplicar apenas o alinhamento
                self.alinhar_unioes_ilhas_direita()
    
    def aplicar_correcoes_automaticas_com_ilhas(self, salvar: bool = True):
        """Aplica correções automáticas com alinhamento de ilhas: 5x(122x60) e ajustar_sobra"""
        if not self.laje_atual:
            return
        
        # Aplicar correção 5x(122x60) - que já aplicará alinhamento de ilhas se checkboxes estiverem ativos
        self.apply_correction_122_60(5)
        
        # Usar QTimer para executar ajustar_sobra após as correções serem processadas
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self._aplicar_ajustar_sobra_automatico_com_ilhas(salvar))
    
    def _aplicar_ajustar_sobra_automatico_com_ilhas(self, salvar: bool = True):
        """Aplica ajustar_sobra (que já aplicará alinhamento de ilhas) e salva se solicitado"""
        self.ajustar_sobra()
        
        if salvar:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._salvar_laje_atual)

    def apply_correction_122_60(self, num_ciclos: int = 1):
        """Aplica a correção 122+60"""
        self._apply_generic_correction_122_X(60.0, num_ciclos)

    def apply_correction_122_20(self, num_ciclos: int = 1):
        """Aplica a correção 122+20"""
        self._apply_generic_correction_122_X(20.0, num_ciclos)

    def set_all_unions_value(self, value: float):
        """Define o valor de todas as uniões (is_union=True)"""
        if not self.laje_atual:
            return
            
        unioes_nos_bordes = self.calculos_modos.unioes_nos_bordes_ativado()
        
        # Obter valores diretamente dos overlays
        verticais = self.vertical_lines_overlay.get_linhas()
        horizontais = self.horizontal_lines_overlay.get_linhas()
        
        # Função auxiliar para atualizar lista
        def update_list(lines):
            # Normalizar
            normalized = []
            for item in lines:
                if isinstance(item, dict):
                    normalized.append(item.copy())
                else:
                    normalized.append({"value": float(item), "is_union": False}) # assumir falso se não tiver metadados
            
            # Identificar unioes e calcular diff
            current_union_sum = 0.0
            union_indices = []
            
            for i, item in enumerate(normalized):
                if item.get("is_union", False) or (20.0 <= item["value"] <= 30.0 and "is_union" not in item): # Fallback
                     item["is_union"] = True # Garantir flag
                     current_union_sum += item["value"]
                     union_indices.append(i)
            
            if not union_indices:
                return lines # Nada a fazer
                
            new_union_sum = len(union_indices) * value
            diff = current_union_sum - new_union_sum
            
            # Aplicar novo valor
            for idx in union_indices:
                normalized[idx]["value"] = value
                
            # Distribuir diferença para manter integridade (adicionar à sobra ou último elemento válido)
            if abs(diff) > 0.001:
                # Se houver sobra no final, usar ela
                if not normalized[-1]["is_union"] and normalized[-1]["value"] < 120.0: # Assumir que ultimo pequeno é sobra
                     normalized[-1]["value"] += diff
                else:
                     # Senao adicionar ao final como sobra
                     normalized.append({"value": diff, "is_union": False})
                     
            return normalized

        # Aplicar
        # Verificar qual modo está ativo para saber onde aplicar, ou aplicar onde houver unioes
        # Mas o botão é global. Vamos aplicar onde houver unioes.
        
        v_updated = update_list(verticais)
        h_updated = update_list(horizontais)
        
        self.laje_atual.linhas_verticais = v_updated
        self.laje_atual.linhas_horizontais = h_updated
        
        self.set_linhas(v_updated, h_updated)
        self.atualizar_visualizacao()

    def _apply_generic_correction_122_X(self, secondary_size: float, num_ciclos: int = 1):
        """
        Lógica genérica para criar N ciclos de Módulo Espelhado:
        [122, SEC, UNIAO, SEC, 122]
        Intercalados por UNIAO.
        """
        if not self.laje_atual:
            return
        
        # Salvar estado
        if not hasattr(self, '_correction_state_saved'):
            self.undo_manager.save_state(self.laje_atual)
            self._correction_state_saved = True
        
        unioes_nos_bordes = self.calculos_modos.unioes_nos_bordes_ativado()

        # Obter valores diretamente dos overlays e normalizar
        verticais_editaveis = self.vertical_lines_overlay.get_linhas()
        horizontais_editaveis = self.horizontal_lines_overlay.get_linhas()
        
        # Normalizar para floats
        verticais_floats = [x["value"] if isinstance(x, dict) else float(x) for x in verticais_editaveis]
        horizontais_floats = [x["value"] if isinstance(x, dict) else float(x) for x in horizontais_editaveis]
        
        # Detectar direção
        has_unions_v = any(20.0 <= x <= 30.0 for x in verticais_floats) if verticais_floats else False
        has_unions_h = any(20.0 <= x <= 30.0 for x in horizontais_floats) if horizontais_floats else False
        
        target_list_floats = None
        is_vertical = False
        
        if has_unions_v:
            target_list_floats = verticais_floats
            is_vertical = True
        elif has_unions_h:
            target_list_floats = horizontais_floats
            is_vertical = False
        elif verticais_floats:
            target_list_floats = verticais_floats
            is_vertical = True
        elif horizontais_floats:
            target_list_floats = horizontais_floats
            is_vertical = False
        else:
            QMessageBox.information(self, "Aviso", "Não há linhas para otimizar.")
            return
        
        lista_completa_floats = list(target_list_floats)
        
        # Adicionar sobra se necessário
        total_len = 0.0
        if is_vertical:
            coords = self.laje_atual.coordenadas if self.laje_atual.coordenadas else None
            if coords:
                min_x = min(x for x, y in coords)
                max_x = max(x for x, y in coords)
                total_len = max_x - min_x
        else:
            coords = self.laje_atual.coordenadas if self.laje_atual.coordenadas else None
            if coords:
                min_y = min(y for x, y in coords)
                max_y = max(y for x, y in coords)
                total_len = max_y - min_y
                
        if total_len > 0:
             soma_editaveis = sum(lista_completa_floats)
             sobra = total_len - soma_editaveis
             if abs(sobra) > 0.1:
                 lista_completa_floats.append(sobra)
        
        soma_original = sum(lista_completa_floats)
        
        # --- Lógica de Modificação usando Dicts ---
        new_list_dicts = []
        
        # Constantes
        TOLERANCE = 0.1
        LINHA_122 = 122.0
        LINHA_SEC = secondary_size
        UNION_MIN = 20.0
        UNION_MAX = 30.0
        UNION_MEAN = 25.0
        UNION_STEP = 5.0
        
        def create_item(val, is_u=False):
            return {"value": float(val), "is_union": bool(is_u)}

        def get_vals(l): return [x["value"] for x in l]
        
        # Tratamento Uniões Bordes (Inicio)
        uniao_inicio = 0.0
        uniao_fim = 0.0
        if unioes_nos_bordes:
            uniao_inicio = UNION_MEAN
            uniao_fim = UNION_MEAN
            soma_original -= (uniao_inicio + uniao_fim)
        
        resto_total = soma_original
        
        # Criar blocos solicitados alternados
        # 1x = [122, SEC]
        # 2x = [122, SEC] + U + [SEC, 122]
        # 3x = [122, SEC] + U + [SEC, 122] + U + [122, SEC]
        # etc.
        
        current_list = []
        for i in range(num_ciclos):
            if i > 0:
                 current_list.append(create_item(UNION_MEAN, True)) # União conectora
            
            # Alternar ordem
            if i % 2 == 0:
                current_list.append(create_item(LINHA_122, False))
                current_list.append(create_item(LINHA_SEC, False))
            else:
                current_list.append(create_item(LINHA_SEC, False))
                current_list.append(create_item(LINHA_122, False))
        
        # Calcular quanto temos vs quanto precisamos
        current_sum_fixed_parts = 0
        unions_indices = []
        
        for idx, item in enumerate(current_list):
            if item["is_union"]:
                unions_indices.append(idx)
            else:
                current_sum_fixed_parts += item["value"]
                
        # Espaço disponível para uniões e sobra
        available_space_for_unions = resto_total - current_sum_fixed_parts
        
        if available_space_for_unions < 0:
            # Não cabe nem os fixos! (Isso é raro se a laje for grande, mas ok)
            # Nesse caso, vamos apenas retornar o que couber ou avisar?
            # Vamos truncar a lista
             pass # logica de truncar seria complexa, vamos deixar estourar na sobra negativa por enquanto ou reduzir unioes a 0 (impossivel fisica)
        
        # Tentar distribuir o espaço nas uniões
        if unions_indices:
             avg_union = available_space_for_unions / len(unions_indices)
             
             # Se a media for valida (20-30), aplicar
             if UNION_MIN <= avg_union <= UNION_MAX:
                 for idx in unions_indices:
                     current_list[idx]["value"] = avg_union
             elif avg_union > UNION_MAX:
                  # Maximizar unioes e o resto vai para sobra
                  for idx in unions_indices:
                      current_list[idx]["value"] = UNION_MAX
             elif avg_union < UNION_MIN:
                  # Minimizar unioes (vai estourar o tamanho total, terá que haver ajuste negativo/sobra negativa?)
                  # Ou removemos blocos? O usuario PEDIU N ciclos. Vamos respeitar e deixar a sobra negativa se for o caso.
                  for idx in unions_indices:
                      current_list[idx]["value"] = UNION_MIN
        
        new_list_dicts = current_list
        
        # 6. Preencher restante com 122 + U
        soma_atual = sum(get_vals(new_list_dicts))
        diff_sobra = resto_total - soma_atual
        
        while diff_sobra >= (LINHA_122 + UNION_MIN):
             new_list_dicts.append(create_item(UNION_MEAN, True))
             new_list_dicts.append(create_item(LINHA_122, False))
             soma_atual = sum(get_vals(new_list_dicts))
             diff_sobra = resto_total - soma_atual
             
        # 7. Uniao Inicio
        if unioes_nos_bordes:
            new_list_dicts.insert(0, create_item(uniao_inicio, True))
            
        # 8. Sobra Final / Uniao Fim
        soma_atual = sum(get_vals(new_list_dicts))
        if unioes_nos_bordes:
             soma_total_target = soma_original + uniao_inicio + uniao_fim
             diff_final = soma_total_target - soma_atual
             # A diferenca deve ser coberta ajustando a uniao final e sobra
             new_list_dicts.append(create_item(diff_final, True)) # Usar como uniao fim/sobra
        else:
             # Sem unioes bordes, a sobra é explicita
             diff_final = soma_original - soma_atual
             if abs(diff_final) > TOLERANCE:
                  new_list_dicts.append(create_item(diff_final, False))

        # Aplicar
        if is_vertical:
            horizontais_originais = self.horizontal_lines_overlay.get_linhas()
            self.laje_atual.linhas_verticais = new_list_dicts
            self.set_linhas(new_list_dicts, horizontais_originais if horizontais_originais else [])
        else:
            verticais_originais = self.vertical_lines_overlay.get_linhas()
            self.laje_atual.linhas_horizontais = new_list_dicts
            self.set_linhas(verticais_originais if verticais_originais else [], new_list_dicts)
        
        self.atualizar_visualizacao()

    
    def apply_correction_122_uniao(self):
        """
        Aplica a correção apenas com 122 união (sem 122+60).
        Cria lista de dicionários explicita: {'value': float, 'is_union': bool}
        """
        if not self.laje_atual:
            return
        
        # Salvar estado antes de aplicar correção
        if not hasattr(self, '_correction_state_saved'):
            self.undo_manager.save_state(self.laje_atual)
            self._correction_state_saved = True
        
        unioes_nos_bordes = self.calculos_modos.unioes_nos_bordes_ativado()
        
        # Obter valores diretamente dos overlays
        verticais_editaveis = self.vertical_lines_overlay.get_linhas()
        horizontais_editaveis = self.horizontal_lines_overlay.get_linhas()
        
        # Normalizar para floats (extrair 'value' de dicionários)
        verticais_floats = [x["value"] if isinstance(x, dict) else float(x) for x in verticais_editaveis]
        horizontais_floats = [x["value"] if isinstance(x, dict) else float(x) for x in horizontais_editaveis]
        
        # Detectar direção
        has_unions_v = any(20.0 <= x <= 30.0 for x in verticais_floats) if verticais_floats else False
        has_unions_h = any(20.0 <= x <= 30.0 for x in horizontais_floats) if horizontais_floats else False
        
        target_list_floats = None
        is_vertical = False
        
        if has_unions_v:
            target_list_floats = verticais_floats
            is_vertical = True
        elif has_unions_h:
            target_list_floats = horizontais_floats
            is_vertical = False
        elif verticais_floats:
            target_list_floats = verticais_floats
            is_vertical = True
        elif horizontais_floats:
            target_list_floats = horizontais_floats
            is_vertical = False
        else:
            QMessageBox.information(self, "Aviso", "Não há linhas para otimizar.")
            return
        
        lista_completa_floats = list(target_list_floats)
        
        # Adicionar sobra se necessário
        if is_vertical:
            coords = self.laje_atual.coordenadas if self.laje_atual.coordenadas else None
            if coords:
                min_x = min(x for x, y in coords)
                max_x = max(x for x, y in coords)
                total_width = max_x - min_x
                soma_editaveis = sum(lista_completa_floats)
                sobra = total_width - soma_editaveis
                if abs(sobra) > 0.1:
                    lista_completa_floats.append(sobra)
        else:
            coords = self.laje_atual.coordenadas if self.laje_atual.coordenadas else None
            if coords:
                min_y = min(y for x, y in coords)
                max_y = max(y for x, y in coords)
                total_height = max_y - min_y
                soma_editaveis = sum(lista_completa_floats)
                sobra = total_height - soma_editaveis
                if abs(sobra) > 0.1:
                    lista_completa_floats.append(sobra)
        
        soma_original = sum(lista_completa_floats)
        
        # Constantes
        TOLERANCE = 0.1
        LINHA_122 = 122.0
        UNION_MIN = 20.0
        UNION_MAX = 30.0
        UNION_MEAN = 25.0
        UNION_STEP = 5.0

        def create_item(val, is_u=False):
            return {"value": float(val), "is_union": bool(is_u)}

        def get_vals(l): return [x["value"] for x in l]
        def set_val(l, idx, v): l[idx]["value"] = v
        
        def calcular_unioes_multiplos_5(valor_total: float, num_unioes: int) -> list:
            if num_unioes == 0: return []
            valor_por_uniao = valor_total / num_unioes
            uniao_base = round(valor_por_uniao / UNION_STEP) * UNION_STEP
            uniao_base = max(UNION_MIN, min(UNION_MAX, uniao_base))
            unioes = [uniao_base] * num_unioes
            soma_arredondada = uniao_base * num_unioes
            resto_fracoes = valor_total - soma_arredondada
            if abs(resto_fracoes) > TOLERANCE:
                unioes[0] = max(UNION_MIN, min(UNION_MAX, uniao_base + resto_fracoes))
            soma_atual = sum(unioes)
            diferenca = valor_total - soma_atual
            if abs(diferenca) > TOLERANCE:
                unioes[0] = max(UNION_MIN, min(UNION_MAX, unioes[0] + diferenca))
            return unioes
        
        # Se "Uniões nos bordes" estiver ativo, reservar espaço para uniões no início e fim
        uniao_inicio = 0.0
        uniao_fim = 0.0
        
        if unioes_nos_bordes:
            uniao_inicio = UNION_MEAN
            uniao_fim = UNION_MEAN
            soma_original -= (uniao_inicio + uniao_fim)
        
        # Criar padrão: 122, união, 122, união, ...
        new_list_dicts = []
        resto_total = soma_original
        
        # Distribuir como (122, união, 122, união, ...)
        while resto_total > TOLERANCE:
            if resto_total >= LINHA_122 - TOLERANCE:
                new_list_dicts.append(create_item(LINHA_122, False))
                resto_total -= LINHA_122
                
                if resto_total >= UNION_MIN - TOLERANCE:
                    unioes_temp = calcular_unioes_multiplos_5(resto_total, 1)
                    if unioes_temp and unioes_temp[0] >= UNION_MIN - TOLERANCE:
                        new_list_dicts.append(create_item(unioes_temp[0], True))
                        resto_total -= unioes_temp[0]
                        if abs(resto_total) < TOLERANCE: resto_total = 0.0
                    else: break
                else: break
            else: break
        
        # Se "Uniões nos bordes" está ativo, adicionar união no início
        if unioes_nos_bordes:
            new_list_dicts.insert(0, create_item(uniao_inicio, True))
        
        # Adicionar sobra no final se não houver "Uniões nos bordes"
        if resto_total > TOLERANCE and not unioes_nos_bordes:
            new_list_dicts.append(create_item(resto_total, False))
        
        # Se "Uniões nos bordes" está ativo, adicionar união no fim
        if unioes_nos_bordes:
            soma_atual = sum(get_vals(new_list_dicts)) + resto_total
            soma_esperada_com_unioes = sum(lista_completa_floats)
            diferenca_total = soma_esperada_com_unioes - soma_atual
            valor_uniao_fim = resto_total + diferenca_total
            
            val_final_u = valor_uniao_fim
            unioes_fim = calcular_unioes_multiplos_5(valor_uniao_fim, 1)
            
            if unioes_fim and UNION_MIN <= unioes_fim[0] <= UNION_MAX:
                val_final_u = unioes_fim[0]
            else:
                 val_arr = round(valor_uniao_fim / UNION_STEP) * UNION_STEP
                 if UNION_MIN <= val_arr <= UNION_MAX:
                     val_final_u = val_arr
                 else:
                     val_final_u = min(max(valor_uniao_fim, UNION_MIN), UNION_MAX)
            
            new_list_dicts.append(create_item(val_final_u, True))
        
        # Verificar e ajustar soma total
        soma_final = sum(get_vals(new_list_dicts))
        soma_original_final = sum(lista_completa_floats)
        diferenca = soma_original_final - soma_final
        
        if abs(diferenca) > TOLERANCE and new_list_dicts:
             if unioes_nos_bordes:
                  # Tentar jogar em alguma uniào
                  if new_list_dicts[-1]["is_union"]:
                      new_list_dicts[-1]["value"] += diferenca
                  elif len(new_list_dicts)>1 and new_list_dicts[-2]["is_union"]:
                      new_list_dicts[-2]["value"] += diferenca
                  else:
                      new_list_dicts[-1]["value"] += diferenca
             else:
                  new_list_dicts[-1]["value"] += diferenca

        # Aplicar mudanças
        if is_vertical:
            horizontais_originais = self.horizontal_lines_overlay.get_linhas()
            self.laje_atual.linhas_verticais = new_list_dicts
            self.set_linhas(new_list_dicts, horizontais_originais if horizontais_originais else [])
        else:
            verticais_originais = self.vertical_lines_overlay.get_linhas()
            self.laje_atual.linhas_horizontais = new_list_dicts
            self.set_linhas(verticais_originais if verticais_originais else [], new_list_dicts)
        
        self.atualizar_visualizacao()

    def ajustar_sobra(self):
        """
        Ajusta a sobra final para 60 ou 122, ajustando as uniões.
        Nova lógica:
        - Se sobra > 60: tenta subtrair das uniões para atingir 122, depois tenta 60
        """
        if not self.laje_atual:
            return
        
        # Salvar estado antes de ajustar sobra (apenas se não foi salvo por correção)
        if not hasattr(self, '_correction_state_saved'):
            self.undo_manager.save_state(self.laje_atual)
            self._correction_state_saved = True
        """
        if not self.laje_atual:
            return
        
        # Salvar estado antes de ajustar sobra (apenas se não foi salvo por correção)
        if not hasattr(self, '_correction_state_saved'):
            self.undo_manager.save_state(self.laje_atual)
            self._correction_state_saved = True
        - Se sobra < 60: tenta subtrair das uniões para atingir 60, ou verifica condições especiais
        """
        if not self.laje_atual:
            QMessageBox.warning(self, "Aviso", "Nenhuma laje selecionada.")
            return
        
        # Verificar qual modo está selecionado
        modo_selecionado = None
        for i, btn in enumerate(self.calculos_modos.buttons):
            if btn.isChecked():
                modo_selecionado = i
                break
        
        if modo_selecionado is None:
            QMessageBox.warning(self, "Aviso", "Selecione um modo de cálculo primeiro (M1 ou M2).")
            return
        
        # Determinar qual lado tem união baseado no modo
        # M1 (0) = Verticais com União
        # M2 (1) = Horizontais com União
        is_vertical = (modo_selecionado == 0)
        
        # Obter valores dos overlays
        verticais_editaveis = self.vertical_lines_overlay.get_linhas()
        horizontais_editaveis = self.horizontal_lines_overlay.get_linhas()
        
        # Obter lista completa
        if is_vertical:
            target_list = list(verticais_editaveis)
            coords = self.laje_atual.coordenadas if self.laje_atual.coordenadas else None
            if coords:
                min_x = min(x for x, y in coords)
                max_x = max(x for x, y in coords)
                total_length = max_x - min_x
        else:
            target_list = list(horizontais_editaveis)
            coords = self.laje_atual.coordenadas if self.laje_atual.coordenadas else None
            if coords:
                min_y = min(y for x, y in coords)
                max_y = max(y for x, y in coords)
                total_length = max_y - min_y
        
        if not coords:
            QMessageBox.warning(self, "Aviso", "Não há coordenadas da laje para calcular a sobra.")
            return
        
        # Verificar se checkbox "Uniões nos bordes" está ativo
        unioes_nos_bordes = self.calculos_modos.unioes_nos_bordes_ativado()
        
        # Helper para somar lista que pode conter dicts
        def sum_list(l):
            return sum(x["value"] if isinstance(x, dict) else float(x) for x in l)

        # Determinar índices corretos baseado em "Uniões nos bordes"
        if unioes_nos_bordes:
            # Último = penúltimo, penúltimo = antepenultimo
            if len(target_list) < 3:
                QMessageBox.warning(self, "Aviso", "Lista muito curta para ajustar sobra com 'Uniões nos bordes'.")
                return
            
            # Pegar valor da sobra
            item_sobra = target_list[-1]
            sobra_atual = item_sobra["value"] if isinstance(item_sobra, dict) else float(item_sobra)
            
            lista_completa = list(target_list)
            idx_penultimo = -2  # Penúltimo elemento (que na verdade é antepenultimo painel)
            idx_antepenultimo = -3  # Antepenultimo elemento
        else:
            soma_editaveis = sum_list(target_list)
            sobra_atual = total_length - soma_editaveis
            lista_completa = list(target_list)
            idx_penultimo = -1  # Penúltimo elemento
            idx_antepenultimo = -2  # Antepenultimo elemento
        
        
        # Constantes
        TOLERANCE = 0.1
        LINHA_60 = 60.0
        LINHA_122 = 122.0
        UNION_MIN = 20.0
        UNION_MAX = 30.0
        UNION_STEP = 5.0
        
        # Verificar se a sobra já é 60 ou 122
        if abs(sobra_atual - LINHA_60) < TOLERANCE or abs(sobra_atual - LINHA_122) < TOLERANCE:
            QMessageBox.information(self, "Ajustar Sobra", f"A sobra já está em um valor válido: {sobra_atual:.1f}cm")
            return
        
        # Encontrar todas as uniões na lista (valores entre 20-30)
        indices_unioes = []
        for i, item in enumerate(lista_completa):
            valor = item["value"] if isinstance(item, dict) else float(item)
            if UNION_MIN <= valor <= UNION_MAX:
                indices_unioes.append(i)
        
        if not indices_unioes:
            QMessageBox.warning(self, "Aviso", "Não foram encontradas uniões na lista para ajustar.")
            return
        
        # Identificar se sobra é maior ou menor que 60
        sobra_maior_que_60 = sobra_atual > LINHA_60 + TOLERANCE
        
        sucesso = False
        lista_final = list(lista_completa)
        sobra_final = sobra_atual
        
        def calcular_unioes_multiplos_5_ajuste(valor_total: float, num_unioes: int) -> list:
            """Calcula uniões usando múltiplos de 5, deixando frações na primeira"""
            if num_unioes == 0:
                return []
            
            valor_por_uniao = valor_total / num_unioes
            uniao_base = round(valor_por_uniao / UNION_STEP) * UNION_STEP
            if uniao_base < UNION_MIN:
                uniao_base = UNION_MIN
            elif uniao_base > UNION_MAX:
                uniao_base = UNION_MAX
            
            unioes = [uniao_base] * num_unioes
            soma_arredondada = uniao_base * num_unioes
            resto_fracoes = valor_total - soma_arredondada
            
            if abs(resto_fracoes) > TOLERANCE:
                unioes[0] = uniao_base + resto_fracoes
                if unioes[0] < UNION_MIN:
                    unioes[0] = UNION_MIN
                elif unioes[0] > UNION_MAX:
                    unioes[0] = UNION_MAX
            
            soma_atual = sum(unioes)
            diferenca = valor_total - soma_atual
            if abs(diferenca) > TOLERANCE:
                unioes[0] = unioes[0] + diferenca
                if unioes[0] < UNION_MIN:
                    unioes[0] = UNION_MIN
                elif unioes[0] > UNION_MAX:
                    unioes[0] = UNION_MAX
            
            return unioes
        
        if sobra_maior_que_60:
            # SOBRA > 60
            # PROCESSO 1: Tentar subtrair das uniões para atingir 122
            diferenca_para_122 = LINHA_122 - sobra_atual
            if diferenca_para_122 > 0:  # Precisa aumentar a sobra
                capacidade_total = 0.0
                for idx in indices_unioes:
                    valor = lista_completa[idx]["value"] if isinstance(lista_completa[idx], dict) else float(lista_completa[idx])
                    capacidade = valor - UNION_MIN
                    capacidade_total += capacidade
                
                if capacidade_total >= diferenca_para_122 - TOLERANCE:
                    # É possível! Subtrair das uniões
                    nova_lista = list(lista_completa)
                    resto_para_subtrair = diferenca_para_122
                    
                    for i, idx in enumerate(indices_unioes):
                        if resto_para_subtrair <= TOLERANCE:
                            break
                        
                        item = nova_lista[idx]
                        valor = item["value"] if isinstance(item, dict) else float(item)
                        capacidade = valor - UNION_MIN
                        
                        if capacidade > TOLERANCE:
                            subtrair = min(resto_para_subtrair, capacidade)
                            if i == 0:
                                novo_valor = valor - subtrair
                            else:
                                subtrair_arredondado = round(subtrair / UNION_STEP) * UNION_STEP
                                subtrair_arredondado = min(subtrair_arredondado, capacidade, resto_para_subtrair)
                                novo_valor = valor - subtrair_arredondado
                                subtrair = subtrair_arredondado
                            
                            if isinstance(nova_lista[idx], dict):
                                nova_lista[idx]["value"] = novo_valor
                            else:
                                nova_lista[idx] = novo_valor
                            
                            resto_para_subtrair -= subtrair
                    
                    if resto_para_subtrair > TOLERANCE and indices_unioes:
                        idx0 = indices_unioes[0]
                        v0 = nova_lista[idx0]["value"] if isinstance(nova_lista[idx0], dict) else float(nova_lista[idx0])
                        if isinstance(nova_lista[idx0], dict):
                            nova_lista[idx0]["value"] = v0 - resto_para_subtrair
                        else:
                            nova_lista[idx0] = v0 - resto_para_subtrair
                    
                    for idx in indices_unioes:
                        item = nova_lista[idx]
                        valor = item["value"] if isinstance(item, dict) else float(item)
                        if valor < UNION_MIN:
                            valor = UNION_MIN
                        elif valor > UNION_MAX:
                            valor = UNION_MAX
                        
                        if isinstance(nova_lista[idx], dict):
                            nova_lista[idx]["value"] = valor
                        else:
                            nova_lista[idx] = valor
                    
                    sucesso = True
                    lista_final = nova_lista
                    if unioes_nos_bordes:
                        lista_final[-1] = LINHA_122  # Último é a sobra
                    sobra_final = LINHA_122
            
            # PROCESSO 2: Se não conseguiu 122, tentar subtrair do 122 para chegar a 60
            if not sucesso:
                # Assumir que a sobra atual será 122 temporariamente e tentar ajustar para 60
                diferenca_de_122_para_60 = LINHA_122 - LINHA_60
                
                # Tentar distribuir essa diferença entre as uniões (limite até 30)
                capacidade_total = 0.0
                for idx in indices_unioes:
                    item = lista_completa[idx]
                    valor = item["value"] if isinstance(item, dict) else float(item)
                    capacidade = UNION_MAX - valor
                    capacidade_total += capacidade
                
                if capacidade_total >= diferenca_de_122_para_60 - TOLERANCE:
                    nova_lista = list(lista_completa)
                    resto_para_distribuir = diferenca_de_122_para_60
                    
                    for i, idx in enumerate(indices_unioes):
                        if resto_para_distribuir <= TOLERANCE:
                            break
                        
                        item = nova_lista[idx]
                        valor = item["value"] if isinstance(item, dict) else float(item)
                        capacidade = UNION_MAX - valor
                        
                        if capacidade > TOLERANCE:
                            adicionar = min(resto_para_distribuir, capacidad)
                            if i == 0:
                                novo_valor = valor + adicionar
                            else:
                                adicionar_arredondado = round(adicionar / UNION_STEP) * UNION_STEP
                                adicionar_arredondado = min(adicionar_arredondado, capacidade, resto_para_distribuir)
                                novo_valor = valor + adicionar_arredondado
                                adicionar = adicionar_arredondado
                            
                            if isinstance(nova_lista[idx], dict):
                                nova_lista[idx]["value"] = novo_valor
                            else:
                                nova_lista[idx] = novo_valor
                            
                            resto_para_distribuir -= adicionar
                    
                    if resto_para_distribuir > TOLERANCE and indices_unioes:
                        idx0 = indices_unioes[0]
                        v0 = nova_lista[idx0]["value"] if isinstance(nova_lista[idx0], dict) else float(nova_lista[idx0])
                        if isinstance(nova_lista[idx0], dict):
                            nova_lista[idx0]["value"] = v0 + resto_para_distribuir
                        else:
                            nova_lista[idx0] = v0 + resto_para_distribuir
                    
                    for idx in indices_unioes:
                        item = nova_lista[idx]
                        valor = item["value"] if isinstance(item, dict) else float(item)
                        if valor < UNION_MIN:
                            valor = UNION_MIN
                        elif valor > UNION_MAX:
                            valor = UNION_MAX
                        
                        if isinstance(nova_lista[idx], dict):
                            nova_lista[idx]["value"] = valor
                        else:
                            nova_lista[idx] = valor
                    
                    # Calcular quanto realmente conseguimos ajustar
                    soma_nova = sum(nova_lista[idx]["value"] if isinstance(nova_lista[idx], dict) else float(nova_lista[idx]) for idx in indices_unioes)
                    soma_velha = sum(lista_completa[idx]["value"] if isinstance(lista_completa[idx], dict) else float(lista_completa[idx]) for idx in indices_unioes)
                    ajuste_real = soma_nova - soma_velha
                    sobra_apos_ajuste = sobra_atual - ajuste_real
                    
                    if abs(sobra_apos_ajuste - LINHA_60) < TOLERANCE:
                        sucesso = True
                        lista_final = nova_lista
                        if unioes_nos_bordes:
                            lista_final[-1] = LINHA_60
                        sobra_final = LINHA_60
                    else:
                        # Não conseguiu chegar a 60, manter sobra como está
                        sucesso = False
        
        else:
            # SOBRA < 60
            # Tentar subtrair das uniões para atingir 60 (limite máximo subtrair até 20 cada)
            diferenca_para_60 = LINHA_60 - sobra_atual
            if diferenca_para_60 > 0:  # Precisa aumentar a sobra
                capacidade_total = 0.0
                for idx in indices_unioes:
                    item = lista_completa[idx]
                    valor = item["value"] if isinstance(item, dict) else float(item)
                    capacidade = valor - UNION_MIN
                    capacidade_total += capacidade
                
                if capacidade_total >= diferenca_para_60 - TOLERANCE:
                    nova_lista = list(lista_completa)
                    resto_para_subtrair = diferenca_para_60
                    
                    for i, idx in enumerate(indices_unioes):
                        if resto_para_subtrair <= TOLERANCE:
                            break
                            
                        item = nova_lista[idx]
                        valor = item["value"] if isinstance(item, dict) else float(item)
                        capacidade = valor - UNION_MIN
                        
                        capacidade_limite = min(capacidade, 20.0)  # Limite máximo de 20
                        if capacidade_limite > TOLERANCE:
                            subtrair = min(resto_para_subtrair, capacidade_limite)
                            if i == 0:
                                novo_valor = valor - subtrair
                            else:
                                subtrair_arredondado = round(subtrair / UNION_STEP) * UNION_STEP
                                subtrair_arredondado = min(subtrair_arredondado, capacidade_limite, resto_para_subtrair)
                                novo_valor = valor - subtrair_arredondado
                                subtrair = subtrair_arredondado
                            
                            if isinstance(nova_lista[idx], dict):
                                nova_lista[idx]["value"] = novo_valor
                            else:
                                nova_lista[idx] = novo_valor
                            
                            resto_para_subtrair -= subtrair
                    
                    if resto_para_subtrair > TOLERANCE and indices_unioes:
                        idx0 = indices_unioes[0]
                        v0 = nova_lista[idx0]["value"] if isinstance(nova_lista[idx0], dict) else float(nova_lista[idx0])
                        if isinstance(nova_lista[idx0], dict):
                            nova_lista[idx0]["value"] = v0 - resto_para_subtrair
                        else:
                            nova_lista[idx0] = v0 - resto_para_subtrair
                    
                    for idx in indices_unioes:
                        item = nova_lista[idx]
                        valor = item["value"] if isinstance(item, dict) else float(item)
                        if valor < UNION_MIN:
                            valor = UNION_MIN
                        elif valor > UNION_MAX:
                            valor = UNION_MAX
                        
                        if isinstance(nova_lista[idx], dict):
                            nova_lista[idx]["value"] = valor
                        else:
                            nova_lista[idx] = valor
                    
                    sucesso = True
                    lista_final = nova_lista
                    if unioes_nos_bordes:
                        lista_final[-1] = LINHA_60
                    sobra_final = LINHA_60
            
            # Se não conseguiu, verificar condições especiais
            if not sucesso:
                penultimo_valor_raw = lista_completa[idx_penultimo] if abs(idx_penultimo) <= len(lista_completa) else None
                antepenultimo_valor_raw = lista_completa[idx_antepenultimo] if abs(idx_antepenultimo) <= len(lista_completa) else None
                
                penultimo_valor = penultimo_valor_raw["value"] if isinstance(penultimo_valor_raw, dict) else (float(penultimo_valor_raw) if penultimo_valor_raw is not None else None)
                antepenultimo_valor = antepenultimo_valor_raw["value"] if isinstance(antepenultimo_valor_raw, dict) else (float(antepenultimo_valor_raw) if antepenultimo_valor_raw is not None else None)
                
                penultimo_eh_uniao = penultimo_valor is not None and UNION_MIN <= penultimo_valor <= UNION_MAX
                antepenultimo_eh_122 = antepenultimo_valor is not None and abs(antepenultimo_valor - LINHA_122) < TOLERANCE
                
                if penultimo_eh_uniao and antepenultimo_eh_122:
                    
                    # Definir todas as uniões em 20
                    nova_lista = list(lista_completa)
                    for idx in indices_unioes:
                        if isinstance(nova_lista[idx], dict):
                            nova_lista[idx]["value"] = UNION_MIN
                        else:
                            nova_lista[idx] = UNION_MIN  # 20
                    
                    # Calcular sobra final
                    if unioes_nos_bordes:
                        # Com "Uniões nos bordes", a sobra é o último elemento
                        # Após definir uniões em 20, recalcular sobra
                        soma_editaveis_nova = sum_list(nova_lista[:-1])  # Todos exceto último
                        sobra_final_nova = total_length - soma_editaveis_nova
                        if isinstance(nova_lista[-1], dict):
                             nova_lista[-1]["value"] = sobra_final_nova
                        else:
                             nova_lista[-1] = sobra_final_nova
                    else:
                        soma_editaveis_nova = sum_list(nova_lista)
                        sobra_final_nova = total_length - soma_editaveis_nova
                    
                    # Se sobra final < 40, eliminar penúltimo painel (união de 20) e somar à sobra
                    if sobra_final_nova < 40.0 - TOLERANCE:
                        
                        # Remover penúltimo elemento
                        # Com "Uniões nos bordes": penúltimo é -2, sobra é -1
                        # Sem "Uniões nos bordes": penúltimo é -1, sobra é calculada separadamente
                        
                        if unioes_nos_bordes:
                            # Remover antepenultimo (que é o penúltimo painel na lógica normal)
                            # índice -2 é o antepenultimo painel
                            item_removido = nova_lista.pop(-2)
                            valor_penultimo = item_removido["value"] if isinstance(item_removido, dict) else float(item_removido)
                            
                            # Soma ao último elemento (sobra)
                            v_sobra = nova_lista[-1]["value"] if isinstance(nova_lista[-1], dict) else float(nova_lista[-1])
                            if isinstance(nova_lista[-1], dict):
                                nova_lista[-1]["value"] = v_sobra + valor_penultimo
                            else:
                                nova_lista[-1] = v_sobra + valor_penultimo
                            
                            sobra_final = nova_lista[-1]["value"] if isinstance(nova_lista[-1], dict) else float(nova_lista[-1])
                        else:
                            # Remover penúltimo elemento da lista
                            item_removido = nova_lista.pop(-1)
                            valor_penultimo = item_removido["value"] if isinstance(item_removido, dict) else float(item_removido)
                            # Soma à sobra calculada
                            sobra_final = sobra_final_nova + valor_penultimo
                        
                        sucesso = True
                        lista_final = nova_lista
        
        # ÚLTIMA TENTATIVA: Se não conseguiu em ambos os casos, definir todas uniões em 30
        if not sucesso:
            
            # Definir todas as uniões em 30
            nova_lista = list(lista_completa)
            for idx in indices_unioes:
                if isinstance(nova_lista[idx], dict):
                    nova_lista[idx]["value"] = UNION_MAX
                else:
                    nova_lista[idx] = UNION_MAX  # 30
            
            # Calcular sobra final
            if unioes_nos_bordes:
                # Com "Uniões nos bordes", a sobra é o último elemento
                soma_editaveis_nova = sum_list(nova_lista[:-1])  # Todos exceto último
                sobra_final_nova = total_length - soma_editaveis_nova
                if isinstance(nova_lista[-1], dict):
                    nova_lista[-1]["value"] = sobra_final_nova
                else:
                    nova_lista[-1] = sobra_final_nova
            else:
                # Sem "Uniões nos bordes", sobra é calculada separadamente
                soma_editaveis_nova = sum_list(nova_lista)
                sobra_final_nova = total_length - soma_editaveis_nova
            
            # Se sobra final < 30, verificar se penúltimo é união antes de eliminar
            if sobra_final_nova < 30.0 - TOLERANCE:
                
                # Verificar se penúltimo é união (20-30)
                penultimo_valor = None
                if unioes_nos_bordes:
                    # Com "Uniões nos bordes": verificar antepenultimo (índice -2)
                    if len(nova_lista) >= 3:
                        penultimo_valor = nova_lista[-2]
                else:
                    # Sem "Uniões nos bordes": verificar penúltimo (índice -1)
                    if len(nova_lista) >= 2:
                        penultimo_valor = nova_lista[-1]
                
                penultimo_eh_uniao = penultimo_valor is not None and UNION_MIN <= penultimo_valor <= UNION_MAX
                
                if penultimo_eh_uniao:
                    if unioes_nos_bordes:
                        # Com "Uniões nos bordes": elimina antepenultimo (que é o penúltimo painel na lógica normal)
                        # índice -2 é o antepenultimo painel
                        valor_removido = nova_lista.pop(-2)  # Remove antepenultimo (união de 30)
                        v_pen = valor_removido["value"] if isinstance(valor_removido, dict) else float(valor_removido)
                        # Soma ao último elemento (sobra)
                        v_sobra = nova_lista[-1]["value"] if isinstance(nova_lista[-1], dict) else float(nova_lista[-1])
                        if isinstance(nova_lista[-1], dict):
                            nova_lista[-1]["value"] = v_sobra + v_pen
                        else:
                            nova_lista[-1] = v_sobra + v_pen
                        sobra_final = nova_lista[-1]["value"] if isinstance(nova_lista[-1], dict) else float(nova_lista[-1])
                        sucesso = True
                        lista_final = nova_lista
                    else:
                        # Sem "Uniões nos bordes": elimina penúltimo elemento (último elemento editável)
                        valor_penultimo = nova_lista.pop(-1)  # Remove último elemento editável (união de 30)
                        # Soma à sobra calculada
                        sobra_final = sobra_final_nova + valor_penultimo
                        sucesso = True
                        lista_final = nova_lista
                else:
                    # Penúltimo não é união, não elimina e não valida
                    sucesso = False
            else:
                # Sobra >= 30, não valida (vai para definir uniões em 20)
                sucesso = False
            
            # Se não validou nenhuma situação, apenas definir todas uniões em 20
            if not sucesso:
                
                nova_lista = list(lista_completa)
                for idx in indices_unioes:
                    nova_lista[idx] = UNION_MIN  # 20
                
                sucesso = True
                lista_final = nova_lista
                if unioes_nos_bordes:
                    # Recalcular sobra com uniões em 20
                    soma_editaveis_nova = sum_list(nova_lista[:-1])
                    sobra_final = total_length - soma_editaveis_nova
                    if isinstance(nova_lista[-1], dict):
                        nova_lista[-1]["value"] = sobra_final
                    else:
                        nova_lista[-1] = sobra_final
                else:
                    # Sobra será calculada automaticamente pelo overlay
                    sobra_final = None
        
        if not sucesso:
            QMessageBox.warning(self, "Ajustar Sobra", 
                              f"Não foi possível ajustar a sobra ({sobra_atual:.1f}cm) para 60, 122 ou < 30.\n"
                              f"Verifique se há uniões suficientes para ajustar.")
            return
        
        # Verificação final: Se sobra é diferente de 60 ou 122
        # Verificar se penúltimo/antepenúltimo painel é 122 e trocar de lugar
        if sucesso:
            if unioes_nos_bordes:
                # Com "Uniões nos bordes": a sobra é o penúltimo elemento (índice -2)
                # Verificar se o antepenúltimo (índice -3) é 122
                if len(lista_final) >= 3:
                    sobra_atual_final = lista_final[-2]  # Penúltimo é a sobra
                    
                    # Verificar se sobra é diferente de 60 ou 122
                    sobra_diferente = abs(sobra_atual_final - LINHA_60) > TOLERANCE and abs(sobra_atual_final - LINHA_122) > TOLERANCE
                    
                    if sobra_diferente:
                        # Verificar se antepenúltimo (índice -3) é 122
                        antepenultimo_painel = lista_final[-3]
                        antepenultimo_eh_122 = abs(antepenultimo_painel - LINHA_122) < TOLERANCE
                        
                        if antepenultimo_eh_122:
                            # Trocar de lugar: sobra vai para antepenúltimo (índice -3), 122 vai para penúltimo (índice -2)
                            valor_sobra = sobra_atual_final
                            lista_final[-3] = valor_sobra  # Coloca sobra no lugar do antepenúltimo (que era 122)
                            lista_final[-2] = LINHA_122  # Coloca 122 no penúltimo (onde estava a sobra)
            else:
                # Sem "Uniões nos bordes": a sobra é calculada automaticamente
                # Verificar se penúltimo painel (último elemento da lista) é 122
                soma_editaveis_final = sum_list(lista_final)
                sobra_atual_final = total_length - soma_editaveis_final
                
                # Verificar se sobra é diferente de 60 ou 122
                sobra_diferente = abs(sobra_atual_final - LINHA_60) > TOLERANCE and abs(sobra_atual_final - LINHA_122) > TOLERANCE
                
                if sobra_diferente:
                    # Verificar se penúltimo painel (último elemento da lista) é 122
                    if len(lista_final) >= 1:
                        penultimo_painel = lista_final[-1]
                        penultimo_eh_122 = abs(penultimo_painel - LINHA_122) < TOLERANCE
                        
                        if penultimo_eh_122:
                            # Trocar de lugar: sobra vai para penúltimo (último elemento da lista), 122 vai para final (vira nova sobra)
                            # O último elemento da lista (que é 122) será substituído pela sobra atual
                            # O 122 sai da lista e vira a nova sobra calculada
                            valor_sobra = sobra_atual_final
                            lista_final[-1] = valor_sobra  # Coloca sobra no lugar do último elemento (que era 122)
                            # O 122 fica como nova sobra (será calculada pelo overlay)
                            sobra_final = LINHA_122
        
        # Verificação adicional: Após último processo final, verificar se há painel diferente de 60
        # Tentar usar flexibilidade das uniões para fazer esse painel chegar a 60
        if sucesso:
            # Encontrar painéis diferentes de 60 (não são uniões, não são 122, e não são 60)
            paineis_diferentes_60 = []
            for i, valor in enumerate(lista_final):
                # Não considerar uniões (20-30) nem 122
                nao_eh_uniao = not (UNION_MIN <= valor <= UNION_MAX)
                nao_eh_122 = abs(valor - LINHA_122) > TOLERANCE
                nao_eh_60 = abs(valor - LINHA_60) > TOLERANCE
                
                if nao_eh_uniao and nao_eh_122 and nao_eh_60:
                    paineis_diferentes_60.append((i, valor))
            
            if paineis_diferentes_60:
                # Tentar ajustar cada painel diferente de 60 para 60 usando flexibilidade das uniões
                for idx_painel, valor_painel in paineis_diferentes_60:
                    diferenca_para_60 = LINHA_60 - valor_painel
                    
                    # Se diferença é positiva, precisa aumentar o painel (subtrair das uniões)
                    # Se diferença é negativa, precisa diminuir o painel (adicionar às uniões)
                    
                    # Encontrar índices das uniões atuais na lista_final
                    indices_unioes_finais = []
                    for i, val in enumerate(lista_final):
                        if UNION_MIN <= val <= UNION_MAX and i != idx_painel:
                            indices_unioes_finais.append(i)
                    
                    if not indices_unioes_finais:
                        continue
                    
                    if diferenca_para_60 > 0:  # Precisa aumentar o painel (subtrair das uniões)
                        capacidade_total = 0.0
                        for idx_uniao in indices_unioes_finais:
                            capacidade = lista_final[idx_uniao] - UNION_MIN
                            capacidade_total += capacidade
                        
                        if capacidade_total >= diferenca_para_60 - TOLERANCE:
                            # É possível! Subtrair das uniões
                            resto_para_subtrair = diferenca_para_60
                            
                            # Distribuir subtração usando múltiplos de 5, exceto primeira união
                            for i, idx_uniao in enumerate(indices_unioes_finais):
                                if resto_para_subtrair <= TOLERANCE:
                                    break
                                
                                capacidade = lista_final[idx_uniao] - UNION_MIN
                                if capacidade > TOLERANCE:
                                    if i == 0:
                                        # Primeira união pode não ser múltiplo de 5
                                        subtrair = min(resto_para_subtrair, capacidade)
                                        lista_final[idx_uniao] -= subtrair
                                        resto_para_subtrair -= subtrair
                                    else:
                                        # Demais uniões preferencialmente múltiplos de 5
                                        subtrair_max = min(resto_para_subtrair, capacidade)
                                        subtrair_arredondado = round(subtrair_max / UNION_STEP) * UNION_STEP
                                        subtrair_arredondado = max(0, min(subtrair_arredondado, capacidade, resto_para_subtrair))
                                        
                                        if subtrair_arredondado > TOLERANCE:
                                            lista_final[idx_uniao] -= subtrair_arredondado
                                            resto_para_subtrair -= subtrair_arredondado
                            
                            # Se sobrou algo, adicionar à primeira união
                            if resto_para_subtrair > TOLERANCE and indices_unioes_finais:
                                idx_primeira_uniao = indices_unioes_finais[0]
                                capacidade_restante = lista_final[idx_primeira_uniao] - UNION_MIN
                                subtrair_final = min(resto_para_subtrair, capacidade_restante)
                                lista_final[idx_primeira_uniao] -= subtrair_final
                                resto_para_subtrair -= subtrair_final
                            
                            # Garantir que uniões estão no range
                            for idx_uniao in indices_unioes_finais:
                                lista_final[idx_uniao] = max(UNION_MIN, min(UNION_MAX, lista_final[idx_uniao]))
                            
                            # Ajustar o painel para 60
                            if abs(resto_para_subtrair) < TOLERANCE:
                                lista_final[idx_painel] = LINHA_60
                            else:
                                # Ajustar parcialmente
                                ajuste_real = diferenca_para_60 - resto_para_subtrair
                                lista_final[idx_painel] += ajuste_real
                    
                    elif diferenca_para_60 < 0:  # Precisa diminuir o painel (adicionar às uniões)
                        diferenca_absoluta = abs(diferenca_para_60)
                        capacidade_total = 0.0
                        for idx_uniao in indices_unioes_finais:
                            capacidade = UNION_MAX - lista_final[idx_uniao]
                            capacidade_total += capacidade
                        
                        if capacidade_total >= diferenca_absoluta - TOLERANCE:
                            # É possível! Adicionar às uniões
                            resto_para_distribuir = diferenca_absoluta
                            
                            # Distribuir adição usando múltiplos de 5, exceto primeira união
                            for i, idx_uniao in enumerate(indices_unioes_finais):
                                if resto_para_distribuir <= TOLERANCE:
                                    break
                                
                                capacidade = UNION_MAX - lista_final[idx_uniao]
                                if capacidade > TOLERANCE:
                                    if i == 0:
                                        # Primeira união pode não ser múltiplo de 5
                                        adicionar = min(resto_para_distribuir, capacidade)
                                        lista_final[idx_uniao] += adicionar
                                        resto_para_distribuir -= adicionar
                                    else:
                                        # Demais uniões preferencialmente múltiplos de 5
                                        adicionar_max = min(resto_para_distribuir, capacidade)
                                        adicionar_arredondado = round(adicionar_max / UNION_STEP) * UNION_STEP
                                        adicionar_arredondado = max(0, min(adicionar_arredondado, capacidade, resto_para_distribuir))
                                        
                                        if adicionar_arredondado > TOLERANCE:
                                            lista_final[idx_uniao] += adicionar_arredondado
                                            resto_para_distribuir -= adicionar_arredondado
                            
                            # Se sobrou algo, adicionar à primeira união
                            if resto_para_distribuir > TOLERANCE and indices_unioes_finais:
                                idx_primeira_uniao = indices_unioes_finais[0]
                                capacidade_restante = UNION_MAX - lista_final[idx_primeira_uniao]
                                adicionar_final = min(resto_para_distribuir, capacidade_restante)
                                lista_final[idx_primeira_uniao] += adicionar_final
                                resto_para_distribuir -= adicionar_final
                            
                            # Garantir que uniões estão no range
                            for idx_uniao in indices_unioes_finais:
                                lista_final[idx_uniao] = max(UNION_MIN, min(UNION_MAX, lista_final[idx_uniao]))
                            
                            # Ajustar o painel para 60
                            if abs(resto_para_distribuir) < TOLERANCE:
                                lista_final[idx_painel] = LINHA_60
                            else:
                                # Ajustar parcialmente
                                ajuste_real = diferenca_absoluta - resto_para_distribuir
                                lista_final[idx_painel] -= ajuste_real
        
        # REVISÃO FINAL INDEPENDENTE:
        # Verificar condições específicas para ajuste final
        # 1. Sobra é 60 válido
        # 2. Penúltimo painel é união (20-30)
        # 3. Antepenúltimo painel é 60 válido
        # Determinar índices e valores baseado em "Uniões nos bordes"
        if unioes_nos_bordes:
            # Com "Uniões nos bordes": sobra = último elemento (índice -1)
            if len(lista_final) >= 3:
                sobra_atual_final = lista_final[-1]
                penultimo_valor_final = lista_final[-2]
                antepenultimo_valor_final = lista_final[-3]
            else:
                sobra_atual_final = None
                penultimo_valor_final = None
                antepenultimo_valor_final = None
        else:
            # Sem "Uniões nos bordes": sobra = calculada, penúltimo = último elemento (índice -1), antepenúltimo = índice -2
            if len(lista_final) >= 2:
                soma_editaveis_final = sum_list(lista_final)
                sobra_atual_final = total_length - soma_editaveis_final
                penultimo_valor_final = lista_final[-1]
                antepenultimo_valor_final = lista_final[-2] if len(lista_final) >= 2 else None
            else:
                sobra_atual_final = None
                penultimo_valor_final = None
                antepenultimo_valor_final = None
        
        # Verificar condições
        condicao1 = sobra_atual_final is not None and abs(sobra_atual_final - LINHA_60) < TOLERANCE
        condicao2 = penultimo_valor_final is not None and UNION_MIN <= penultimo_valor_final <= UNION_MAX
        condicao3 = antepenultimo_valor_final is not None and abs(antepenultimo_valor_final - LINHA_60) < TOLERANCE
        
        if condicao1 and condicao2 and condicao3:
            
            # Eliminar antepenúltimo de 60 e somar aos 60 válido do final
            valor_antepenultimo = LINHA_60  # Valor que será eliminado
            
            if unioes_nos_bordes:
                # Com "Uniões nos bordes": eliminar antepenúltimo (índice -3) e somar ao último (sobra)
                valor_removido = lista_final.pop(-3)  # Remove antepenúltimo de 60
                lista_final[-1] = lista_final[-1] + valor_removido  # Soma aos 60 do final (último = sobra)
                # Agora último elemento (sobra) é 120 (60 + 60)
                sobra_apos_eliminar = lista_final[-1]
            else:
                # Sem "Uniões nos bordes": eliminar antepenúltimo (índice -2) 
                # A sobra é calculada automaticamente, então ao remover um elemento de 60 da lista,
                # a sobra vai aumentar automaticamente de 60 para 120
                valor_removido = lista_final.pop(-2)  # Remove antepenúltimo de 60
                # A sobra será recalculada automaticamente como 120 (60 original + 60 removido)
                # Recalcular sobra
                soma_editaveis_apos = sum_list(lista_final)
                sobra_apos_eliminar = total_length - soma_editaveis_apos  # Deve ser 120
            
            # Tentar subtrair 2 de alguma união para completar 122, com limite de subtrair até 20
            diferenca_para_122 = LINHA_122 - sobra_apos_eliminar  # Precisa adicionar 2 (122 - 120 = 2)
            
            # Encontrar uniões disponíveis
            indices_unioes_finais_revisao = []
            for i, val in enumerate(lista_final):
                if UNION_MIN <= val <= UNION_MAX:
                    indices_unioes_finais_revisao.append(i)
            
            sucesso_revisao = False
            if indices_unioes_finais_revisao:
                # Tentar subtrair 2 de alguma união
                for idx_uniao in indices_unioes_finais_revisao:
                    capacidade = lista_final[idx_uniao] - UNION_MIN
                    # Limite máximo de subtrair até 20, mas neste caso só precisamos de 2
                    if capacidade >= 2.0 - TOLERANCE:
                        # Pode subtrair 2
                        lista_final[idx_uniao] -= 2.0
                        # Garantir que está no range
                        if lista_final[idx_uniao] < UNION_MIN:
                            lista_final[idx_uniao] = UNION_MIN
                        
                        # Ajustar sobra para 122
                        if unioes_nos_bordes:
                            # Com "Uniões nos bordes": ajustar último elemento (sobra)
                            lista_final[-1] = LINHA_122
                            sobra_final = LINHA_122
                        else:
                            # Sem "Uniões nos bordes": a sobra será recalculada automaticamente
                            # Ao subtrair 2 de uma união, a sobra aumenta automaticamente de 120 para 122
                            # Recalcular sobra
                            soma_editaveis_final_revisao = sum_list(lista_final)
                            sobra_final = total_length - soma_editaveis_final_revisao  # Deve ser 122
                        
                        sucesso_revisao = True
                        break
                
                if not sucesso_revisao:
                    # Manter 120 mesmo
                    if unioes_nos_bordes:
                        # Com "Uniões nos bordes": garantir que último elemento é 120 (já está correto)
                        sobra_final = lista_final[-1]
                    else:
                        # Sem "Uniões nos bordes": a sobra será recalculada automaticamente como 120
                        sobra_final = sobra_apos_eliminar
            else:
                if unioes_nos_bordes:
                    sobra_final = lista_final[-1]
                else:
                    sobra_final = sobra_apos_eliminar
        else:
            # Recalcular sobra_final se não foi definida pela revisão final
            if unioes_nos_bordes:
                sobra_final = lista_final[-1] if lista_final else sobra_final
            else:
                soma_editaveis_apos_revisao = sum_list(lista_final)
                sobra_final = total_length - soma_editaveis_apos_revisao
        
        # Aplicar mudanças
        # Com "Uniões nos bordes", a sobra já está no último elemento
        # Sem "Uniões nos bordes", a sobra será calculada automaticamente pelo overlay
        if not unioes_nos_bordes:
            # A sobra será recalculada automaticamente, mas precisamos garantir que a soma está correta
            # O overlay vai recalcular automaticamente
            # Se trocamos, o 122 está como sobra e será adicionado no final
            pass
        
        # ANTES de aplicar mudanças: verificar se checkboxes de ilhas estão ativos e aplicar alinhamento
        lista_completa_ajustar_sobra = list(lista_final)
        if not unioes_nos_bordes and abs(sobra_final) > 0.1:
            lista_completa_ajustar_sobra.append(sobra_final)
        elif unioes_nos_bordes:
            # A sobra já está em lista_final[-1]
            pass
        
        if self.calculos_modos.unioes_ilhas_esquerda_ativado() or self.calculos_modos.unioes_ilhas_direita_ativado():
            lista_final = self._aplicar_alinhamento_ilhas_em_lista(lista_final, is_vertical, lista_completa_ajustar_sobra)
        
        # Atualizar lista
        if is_vertical:
            horizontais_originais = self.horizontal_lines_overlay.get_linhas()
            self.laje_atual.linhas_verticais = lista_final
            self.set_linhas(lista_final, horizontais_originais if horizontais_originais else [])
        else:
            verticais_originais = self.vertical_lines_overlay.get_linhas()
            self.laje_atual.linhas_horizontais = lista_final
            self.set_linhas(verticais_originais if verticais_originais else [], lista_final)
        
        self.atualizar_visualizacao()
        QMessageBox.information(self, "Ajustar Sobra", 
                               f"Sobra ajustada com sucesso para {sobra_final:.1f}cm!")
    
    def inverter_linhas_verticais(self):
        """
        Inverte a ordem dos campos verticais (de trás para frente), incluindo a sobra.
        A sobra antiga vira o primeiro campo editável, e o que estava no início vira a nova sobra.
        """
        if not self.laje_atual or not self.laje_atual.coordenadas:
            return
        
        # Salvar estado antes de inverter
        self.undo_manager.save_state(self.laje_atual)
        
        # Obter valores editáveis dos overlays
        campos_editaveis = self.vertical_lines_overlay.get_linhas()
        horizontais = self.horizontal_lines_overlay.get_linhas()
        
        if not campos_editaveis:
            QMessageBox.information(self, "Aviso", "Não há linhas verticais para inverter.")
            return
        
        # Calcular largura total e sobra atual
        coords = self.laje_atual.coordenadas
        min_x = min(x for x, y in coords)
        max_x = max(x for x, y in coords)
        total_width = max_x - min_x
        
        # Calcular sobra atual (o que está faltando para completar o total)
        soma_editaveis = sum(x["value"] if isinstance(x, dict) else float(x) for x in campos_editaveis)
        sobra_antiga = total_width - soma_editaveis
        if abs(sobra_antiga) < 0.001:
            sobra_antiga = 0.0
        
        # Construir lista completa: [campos_editaveis] + [sobra]
        lista_completa = campos_editaveis + [sobra_antiga] if sobra_antiga > 0.001 else campos_editaveis
        
        if len(lista_completa) <= 1:
            QMessageBox.information(self, "Aviso", "Não há valores suficientes para inverter.")
            return
        
        # Separar sobra dos campos editáveis
        if sobra_antiga > 0.001:
            # Tem sobra: separar e inverter
            sobra_antiga = lista_completa[-1]  # Último valor (sobra)
            campos_editaveis = lista_completa[:-1]  # Todos exceto o último
            
            if not campos_editaveis:
                QMessageBox.information(self, "Aviso", "Não há campos editáveis para inverter.")
                return
            
            primeiro_valor = campos_editaveis[0]  # Primeiro valor original (vai virar nova sobra)
            
            # Inverter os campos editáveis (sem a sobra)
            campos_editaveis_invertidos = list(reversed(campos_editaveis))
            
            # Reconstruir: sobra antiga no início, depois campos invertidos, depois primeiro original
            # Exemplo: [122, 122, 60] (editáveis) + [50] (sobra) 
            # -> [50, 60, 122, 122] (após inverter campos + sobra no início)
            # -> [50, 60, 122, 122] (lista completa com primeiro original no final)
            # O primeiro original (122) está no final e será removido pelo set_linhas
            # e recalculado como a nova sobra
            verticais_invertidas = [sobra_antiga] + campos_editaveis_invertidos
            
            # Verificar se a soma bate com o total (deve bater se incluirmos o primeiro original)
            soma_com_primeiro = sum(x["value"] if isinstance(x, dict) else float(x) for x in verticais_invertidas)
            if abs(soma_com_primeiro - total_width) > 0.1:
                # Ajustar: o primeiro valor original deve estar no final para ser removido
                # e recalculado como sobra. Mas ele já está no final após inverter!
                # Então a lista está correta
                pass
        else:
            # Não tem sobra, apenas inverter tudo
            verticais_invertidas = list(reversed(campos_editaveis))
        
        # Aplicar as mudanças
        # O set_linhas vai verificar se sum(verticais_invertidas) == total_width
        # Se for, vai remover o último valor (que era o primeiro original) e recalcular como a nova sobra
        self.set_linhas(verticais_invertidas, horizontais)
    
    def inverter_linhas_horizontais(self):
        """
        Inverte a ordem dos campos horizontais (de trás para frente), incluindo a sobra.
        A sobra antiga vira o primeiro campo editável, e o que estava no início vira a nova sobra.
        """
        if not self.laje_atual or not self.laje_atual.coordenadas:
            return
        
        # Salvar estado antes de inverter
        self.undo_manager.save_state(self.laje_atual)
        
        # Obter valores editáveis dos overlays
        verticais = self.vertical_lines_overlay.get_linhas()
        campos_editaveis = self.horizontal_lines_overlay.get_linhas()
        
        if not campos_editaveis:
            QMessageBox.information(self, "Aviso", "Não há linhas horizontais para inverter.")
            return
        
        # Calcular altura total e sobra atual
        coords = self.laje_atual.coordenadas
        min_y = min(y for x, y in coords)
        max_y = max(y for x, y in coords)
        total_height = max_y - min_y
        
        # Calcular sobra atual (o que está faltando para completar o total)
        soma_editaveis = sum(x["value"] if isinstance(x, dict) else float(x) for x in campos_editaveis)
        sobra_antiga = total_height - soma_editaveis
        if abs(sobra_antiga) < 0.001:
            sobra_antiga = 0.0
        
        # Construir lista completa: [campos_editaveis] + [sobra]
        lista_completa = campos_editaveis + [sobra_antiga] if sobra_antiga > 0.001 else campos_editaveis
        
        if len(lista_completa) <= 1:
            QMessageBox.information(self, "Aviso", "Não há valores suficientes para inverter.")
            return
        
        # Separar sobra dos campos editáveis
        if sobra_antiga > 0.001:
            # Tem sobra: separar e inverter
            sobra_antiga = lista_completa[-1]  # Último valor (sobra)
            campos_editaveis = lista_completa[:-1]  # Todos exceto o último
            
            if not campos_editaveis:
                QMessageBox.information(self, "Aviso", "Não há campos editáveis para inverter.")
                return
            
            primeiro_valor = campos_editaveis[0]  # Primeiro valor original (vai virar nova sobra)
            
            # Inverter os campos editáveis (sem a sobra)
            campos_editaveis_invertidos = list(reversed(campos_editaveis))
            
            # Reconstruir: sobra antiga no início, depois campos invertidos, depois primeiro original
            # Exemplo: [122, 122, 60] (editáveis) + [50] (sobra) 
            # -> [50, 60, 122, 122] (após inverter campos + sobra no início)
            # -> [50, 60, 122, 122] (lista completa com primeiro original no final)
            # O primeiro original (122) está no final e será removido pelo set_linhas
            # e recalculado como a nova sobra
            horizontais_invertidas = [sobra_antiga] + campos_editaveis_invertidos
            
            # Verificar se a soma bate com o total (deve bater se incluirmos o primeiro original)
            soma_com_primeiro = self.sum_list(horizontais_invertidas)
            if abs(soma_com_primeiro - total_height) > 0.1:
                # Ajustar: o primeiro valor original deve estar no final para ser removido
                # e recalculado como sobra. Mas ele já está no final após inverter!
                # Então a lista está correta
                pass
        else:
            # Não tem sobra, apenas inverter tudo
            horizontais_invertidas = list(reversed(campos_editaveis))
        
        # Aplicar as mudanças
        # O set_linhas vai verificar se sum(horizontais_invertidas) == total_height
        # Se for, vai remover o último valor (que era o primeiro original) e recalcular como a nova sobra
        self.set_linhas(verticais, horizontais_invertidas)

    def position_overlays(self):
        pass

    def alinhar_unioes_ilhas_esquerda(self):
        """
        Alinha uniões com as paredes esquerdas das ilhas (obstáculos).
        Nova lógica reforçada:
        - Se a grossura da ilha for 19-30, a união terá essa grossura exata
        - Se for mais grossa (>30), alinha por dentro mantendo continuação da parede esquerda
        - Ajusta outras uniões (20-30) ou painéis (60/122) mais próximos para conseguir alinhar
        """
        self._alinhar_unioes_ilhas(lado_esquerdo=True)
    
    def alinhar_unioes_ilhas_direita(self):
        """
        Alinha uniões com as paredes direitas das ilhas (obstáculos).
        Nova lógica reforçada:
        - Se a grossura da ilha for 19-30, a união terá essa grossura exata
        - Se for mais grossa (>30), alinha por dentro mantendo continuação da parede direita
        - Ajusta outras uniões (20-30) ou painéis (60/122) mais próximos para conseguir alinhar
        """
        self._alinhar_unioes_ilhas(lado_esquerdo=False)
    
    def _alinhar_unioes_ilhas(self, lado_esquerdo: bool) -> Optional[List[float]]:
        """
        Função auxiliar que implementa a lógica de alinhamento de uniões com ilhas.
        Retorna a lista ajustada ou None se houver erro.
        
        Args:
            lado_esquerdo: True para esquerda/fundo, False para direita/topo
            - M1 (verticais): esquerda = parede esquerda, direita = parede direita
            - M2 (horizontais): esquerda = fundo (inferior), direita = topo (superior)
        """
        if not self.laje_atual:
            QMessageBox.warning(self, "Aviso", "Nenhuma laje selecionada.")
            return None
        
        # Verificar se existem ilhas (obstáculos)
        obstaculos = getattr(self.laje_atual, 'obstaculos', [])
        if not obstaculos:
            QMessageBox.information(self, "Aviso", "Não existem ilhas (obstáculos) no desenho.")
            return None
        
        # Obter modo selecionado
        modo_selecionado = self.calculos_modos.button_group.checkedId()
        if modo_selecionado < 0:
            QMessageBox.information(self, "Aviso", "Selecione um modo de cálculo primeiro.")
            return None
        
        # M1 = Verticais com União, M2 = Horizontais com União
        is_vertical = (modo_selecionado == 0)  # M1 = 0 (verticais)
        
        # Obter lista de linhas e coordenadas
        if is_vertical:
            target_list = self.vertical_lines_overlay.get_linhas()
            if not target_list:
                QMessageBox.information(self, "Aviso", "Não há linhas verticais para ajustar.")
                return None
            coords = self.laje_atual.coordenadas
            if not coords:
                QMessageBox.warning(self, "Aviso", "Laje sem coordenadas.")
                return None
            min_x = min(x for x, y in coords)
            min_y = min(y for x, y in coords)
            coord_min = min_x
        else:
            target_list = self.horizontal_lines_overlay.get_linhas()
            if not target_list:
                QMessageBox.information(self, "Aviso", "Não há linhas horizontais para ajustar.")
                return None
            coords = self.laje_atual.coordenadas
            if not coords:
                QMessageBox.warning(self, "Aviso", "Laje sem coordenadas.")
                return None
            min_x = min(x for x, y in coords)
            min_y = min(y for x, y in coords)
            coord_min = min_y
        
        # Helper local para pegar valor
        def get_v(x): return x["value"] if isinstance(x, dict) else float(x)

        # Verificar se há uniões (19-30)
        unioes_indices = [i for i, item in enumerate(target_list) if 19.0 <= get_v(item) <= 30.0]
        if not unioes_indices:
            QMessageBox.information(self, "Aviso", "Não há uniões (19-30) nas linhas.")
            return None
        
        # Calcular posições acumuladas (posição de início de cada elemento)
        positions = [coord_min]
        for item in target_list:
            positions.append(positions[-1] + get_v(item))
        
        # Para cada ilha, encontrar união mais próxima e processar
        new_list = list(target_list)
        UNION_MIN = 19.0
        UNION_MAX = 30.0
        LINHA_60 = 60.0
        LINHA_122 = 122.0
        TOLERANCE = 0.1
        
        def encontrar_uniao_mais_proxima(ilha_coords, lado_esquerdo, is_vertical):
            """Encontra a união mais próxima de uma ilha e calcula informações"""
            if is_vertical:
                # Modo M1: Verticais
                min_ilha = min(x for x, y in ilha_coords)
                max_ilha = max(x for x, y in ilha_coords)
                grossura_ilha = max_ilha - min_ilha
                # lado_esquerdo = True: parede esquerda (min_ilha)
                # lado_esquerdo = False: parede direita (max_ilha)
                parede_ilha = min_ilha if lado_esquerdo else max_ilha
            else:
                # Modo M2: Horizontais
                min_ilha = min(y for x, y in ilha_coords)
                max_ilha = max(y for x, y in ilha_coords)
                grossura_ilha = max_ilha - min_ilha
                # lado_esquerdo = True: fundo/inferior (min_ilha)
                # lado_esquerdo = False: topo/superior (max_ilha)
                parede_ilha = min_ilha if lado_esquerdo else max_ilha
            
            # Encontrar união mais próxima
            uniao_mais_proxima_idx = None
            distancia_minima = float('inf')
            
            for uniao_idx in unioes_indices:
                # Posição atual da parede da união que queremos alinhar
                if lado_esquerdo:
                    # Parede esquerda/fundo da união = início da união
                    pos_uniao_parede = positions[uniao_idx]
                else:
                    # Parede direita/topo da união = fim da união
                    pos_uniao_parede = positions[uniao_idx + 1] if uniao_idx + 1 < len(positions) else positions[-1]
                
                distancia = abs(parede_ilha - pos_uniao_parede)
                if distancia < distancia_minima:
                    distancia_minima = distancia
                    uniao_mais_proxima_idx = uniao_idx
            
            return uniao_mais_proxima_idx, grossura_ilha, parede_ilha, distancia_minima
        
        # Processar cada ilha (apenas 1 união por ilha)
        for obstaculo in obstaculos:
            if len(obstaculo) < 3:
                continue
            
            uniao_idx, grossura_ilha, parede_ilha, distancia = encontrar_uniao_mais_proxima(obstaculo, lado_esquerdo, is_vertical)
            
            if uniao_idx is None or distancia > 100.0:  # Tolerância de 100cm
                continue
            
            # Calcular posições atuais
            soma_anteriores = self.sum_list(new_list[:uniao_idx])
            posicao_atual_inicio_uniao = positions[uniao_idx]
            posicao_atual_fim_uniao = positions[uniao_idx + 1] if uniao_idx + 1 < len(positions) else positions[-1]
            uniao_atual_valor = get_v(new_list[uniao_idx])
            
            # Calcular posição desejada da parede da união (deve coincidir com parede_ilha)
            posicao_desejada_parede_uniao = parede_ilha - coord_min
            
            # Determinar valor da união e posição necessária
            if UNION_MIN <= grossura_ilha <= UNION_MAX:
                # Caso 1: Ilha tem 19-30cm, união terá essa grossura exata
                nova_uniao_valor = grossura_ilha
                
                # Calcular onde a união deve começar para que a parede desejada fique alinhada
                if lado_esquerdo:
                    # Parede esquerda/fundo da união = início da união = parede_ilha
                    posicao_desejada_inicio_uniao = posicao_desejada_parede_uniao
                else:
                    # Parede direita/topo da união = fim da união = parede_ilha
                    posicao_desejada_fim_uniao = posicao_desejada_parede_uniao
                    posicao_desejada_inicio_uniao = posicao_desejada_fim_uniao - nova_uniao_valor
                
                # Calcular diferença necessária
                diferenca_posicao = posicao_desejada_inicio_uniao - soma_anteriores
                
            else:
                # Caso 2: Ilha > 30cm, união fica dentro (máximo 30cm) e se alinha
                nova_uniao_valor = UNION_MAX  # Máximo 30cm
                
                # Calcular onde a união deve começar para que a parede desejada fique alinhada
                if lado_esquerdo:
                    # Parede esquerda/fundo da união = início da união = parede_ilha
                    posicao_desejada_inicio_uniao = posicao_desejada_parede_uniao
                else:
                    # Parede direita/topo da união = fim da união = parede_ilha
                    posicao_desejada_fim_uniao = posicao_desejada_parede_uniao
                    posicao_desejada_inicio_uniao = posicao_desejada_fim_uniao - nova_uniao_valor
                
                # Calcular diferença necessária
                diferenca_posicao = posicao_desejada_inicio_uniao - soma_anteriores
            
            # A diferença precisa ser compensada ajustando outras linhas
            # Se diferenca_posicao > 0: precisa aumentar linhas anteriores ou diminuir posteriores
            # Se diferenca_posicao < 0: precisa diminuir linhas anteriores ou aumentar posteriores
            
            # Aplicar ajustes para compensar a diferença
            if abs(diferenca_posicao) > TOLERANCE:
                # Estratégia: ajustar outras uniões primeiro, depois painéis 60/122
                outras_unioes = [idx for idx in unioes_indices if idx != uniao_idx]
                paineis_60_122 = [(i, get_v(item)) for i, item in enumerate(new_list) 
                                 if i != uniao_idx and (abs(get_v(item) - LINHA_60) < 5.0 or abs(get_v(item) - LINHA_122) < 5.0)]
                
                ajuste_restante = diferenca_posicao
                
                # Primeiro: tentar ajustar outras uniões
                if outras_unioes and abs(ajuste_restante) > TOLERANCE:
                    ajuste_por_uniao = ajuste_restante / len(outras_unioes)
                    for outra_idx in outras_unioes:
                        if abs(ajuste_restante) < TOLERANCE:
                            break
                        v_atual = get_v(new_list[outra_idx])
                        novo_valor = v_atual + ajuste_por_uniao
                        if UNION_MIN <= novo_valor <= UNION_MAX:
                            if isinstance(new_list[outra_idx], dict):
                                new_list[outra_idx]["value"] = novo_valor
                            else:
                                new_list[outra_idx] = novo_valor
                            ajuste_restante -= ajuste_por_uniao
                
                # Segundo: ajustar painéis 60/122 mais próximos
                if abs(ajuste_restante) > TOLERANCE and paineis_60_122:
                    # Ordenar por proximidade da união
                    paineis_60_122.sort(key=lambda x: abs(x[0] - uniao_idx))
                    
                    for painel_idx, painel_val in paineis_60_122:
                        if abs(ajuste_restante) < TOLERANCE:
                            break
                        
                        # Limite de ajuste por painel: 10cm
                        ajuste_painel = max(-10.0, min(10.0, ajuste_restante))
                        novo_valor = painel_val + ajuste_painel
                        if novo_valor > 0:
                            if isinstance(new_list[painel_idx], dict):
                                new_list[painel_idx]["value"] = novo_valor
                            else:
                                new_list[painel_idx] = novo_valor
                            ajuste_restante -= ajuste_painel
                
                # Se ainda sobrar diferença, ajustar a própria união (dentro dos limites)
                if abs(ajuste_restante) > TOLERANCE:
                    # Recalcular soma anterior após ajustes
                    soma_anteriores_ajustada = self.sum_list(new_list[:uniao_idx])
                    posicao_desejada_inicio_uniao = posicao_desejada_inicio_uniao # redundante mas ok
                    nova_uniao_valor_ajustada = posicao_desejada_inicio_uniao - soma_anteriores_ajustada
                    # Limitar ao range válido
                    nova_uniao_valor = max(UNION_MIN, min(UNION_MAX, nova_uniao_valor_ajustada))
            
            # Aplicar valor final da união
            if isinstance(new_list[uniao_idx], dict):
                new_list[uniao_idx]["value"] = nova_uniao_valor
            else:
                new_list[uniao_idx] = nova_uniao_valor
        
        return new_list  # Retornar lista ajustada
    
    def _aplicar_alinhamento_ilhas_em_lista(self, target_list: List[float], is_vertical: bool, lista_completa_original: List[float]) -> List[float]:
        """
        Aplica alinhamento de ilhas em uma lista já calculada.
        Esta função é chamada internamente por apply_correction_122_60 e ajustar_sobra
        quando os checkboxes de ilhas estão ativos.
        
        Args:
            target_list: Lista de distâncias já calculada
            is_vertical: True se são linhas verticais, False se horizontais
            lista_completa_original: Lista original completa (incluindo sobra) para preservar soma total
        
        Returns:
            Lista ajustada com alinhamento de ilhas aplicado
        """
        if not self.laje_atual:
            return target_list
        
        # Verificar se existem ilhas (obstáculos)
        obstaculos = getattr(self.laje_atual, 'obstaculos', [])
        if not obstaculos:
            return target_list  # Sem ilhas, retornar lista original
        
        # Helper local para pegar valor
        def get_v(x): return x["value"] if isinstance(x, dict) else float(x)

        # Verificar se há uniões (19-30)
        unioes_indices = [i for i, item in enumerate(target_list) if 19.0 <= get_v(item) <= 30.0]
        if not unioes_indices:
            return target_list  # Sem uniões, retornar lista original
        
        # Obter coordenadas e calcular posições
        coords = self.laje_atual.coordenadas
        if not coords:
            return target_list
        
        if is_vertical:
            coord_min = min(x for x, y in coords)
        else:
            coord_min = min(y for x, y in coords)
        
        # Calcular posições acumuladas
        positions = [coord_min]
        for item in target_list:
            positions.append(positions[-1] + get_v(item))
        
        # Criar cópia da lista para ajustar
        new_list = list(target_list)
        UNION_MIN = 19.0
        UNION_MAX = 30.0
        LINHA_60 = 60.0
        LINHA_122 = 122.0
        TOLERANCE = 0.1
        
        # Verificar qual checkbox está ativo
        lado_esquerdo_ativo = self.calculos_modos.unioes_ilhas_esquerda_ativado()
        lado_direita_ativo = self.calculos_modos.unioes_ilhas_direita_ativado()
        
        def encontrar_uniao_mais_proxima(ilha_coords, lado_esquerdo, is_vertical):
            """Encontra a união mais próxima de uma ilha e calcula informações"""
            if is_vertical:
                min_ilha = min(x for x, y in ilha_coords)
                max_ilha = max(x for x, y in ilha_coords)
                grossura_ilha = max_ilha - min_ilha
                parede_ilha = min_ilha if lado_esquerdo else max_ilha
            else:
                min_ilha = min(y for x, y in ilha_coords)
                max_ilha = max(y for x, y in ilha_coords)
                grossura_ilha = max_ilha - min_ilha
                parede_ilha = min_ilha if lado_esquerdo else max_ilha
            
            uniao_mais_proxima_idx = None
            distancia_minima = float('inf')
            
            for uniao_idx in unioes_indices:
                if lado_esquerdo:
                    pos_uniao_parede = positions[uniao_idx]
                else:
                    pos_uniao_parede = positions[uniao_idx + 1] if uniao_idx + 1 < len(positions) else positions[-1]
                
                distancia = abs(parede_ilha - pos_uniao_parede)
                if distancia < distancia_minima:
                    distancia_minima = distancia
                    uniao_mais_proxima_idx = uniao_idx
            
            return uniao_mais_proxima_idx, grossura_ilha, parede_ilha, distancia_minima
        
        # Processar cada ilha
        for obstaculo in obstaculos:
            if len(obstaculo) < 3:
                continue
            
            # Tentar alinhar com esquerda/fundo primeiro se checkbox estiver ativo
            if lado_esquerdo_ativo:
                uniao_idx, grossura_ilha, parede_ilha, distancia = encontrar_uniao_mais_proxima(obstaculo, True, is_vertical)
                if uniao_idx is not None and distancia <= 100.0:
                    new_list = self._aplicar_alinhamento_uniao_ilha(new_list, positions, uniao_idx, grossura_ilha, parede_ilha, True, is_vertical, coord_min, unioes_indices)
            
            # Tentar alinhar com direita/topo se checkbox estiver ativo (pode alinhar outra ilha ou mesma ilha do outro lado)
            if lado_direita_ativo:
                uniao_idx, grossura_ilha, parede_ilha, distancia = encontrar_uniao_mais_proxima(obstaculo, False, is_vertical)
                if uniao_idx is not None and distancia <= 100.0:
                    new_list = self._aplicar_alinhamento_uniao_ilha(new_list, positions, uniao_idx, grossura_ilha, parede_ilha, False, is_vertical, coord_min, unioes_indices)
        
        return new_list
    
    def _aplicar_alinhamento_uniao_ilha(self, new_list: List[float], positions: List[float], uniao_idx: int, 
                                       grossura_ilha: float, parede_ilha: float, lado_esquerdo: bool,
                                       is_vertical: bool, coord_min: float, unioes_indices: List[int]) -> List[float]:
        """
        Função auxiliar que aplica o alinhamento de uma união específica com uma ilha.
        Retorna a lista ajustada.
        """
        UNION_MIN = 19.0
        UNION_MAX = 30.0
        LINHA_60 = 60.0
        LINHA_122 = 122.0
        TOLERANCE = 0.1
        
        # Helper local para pegar valor
        def get_v(x): return x["value"] if isinstance(x, dict) else float(x)

        soma_anteriores = self.sum_list(new_list[:uniao_idx])
        posicao_desejada_parede_uniao = parede_ilha - coord_min
        
        # Determinar valor da união e posição necessária
        if UNION_MIN <= grossura_ilha <= UNION_MAX:
            nova_uniao_valor = grossura_ilha
            if lado_esquerdo:
                posicao_desejada_inicio_uniao = posicao_desejada_parede_uniao
            else:
                posicao_desejada_fim_uniao = posicao_desejada_parede_uniao
                posicao_desejada_inicio_uniao = posicao_desejada_fim_uniao - nova_uniao_valor
            diferenca_posicao = posicao_desejada_inicio_uniao - soma_anteriores
        else:
            nova_uniao_valor = UNION_MAX
            if lado_esquerdo:
                posicao_desejada_inicio_uniao = posicao_desejada_parede_uniao
            else:
                posicao_desejada_fim_uniao = posicao_desejada_parede_uniao
                posicao_desejada_inicio_uniao = posicao_desejada_fim_uniao - nova_uniao_valor
            diferenca_posicao = posicao_desejada_inicio_uniao - soma_anteriores
        
        # Aplicar ajustes para compensar a diferença
        if abs(diferenca_posicao) > TOLERANCE:
            outras_unioes = [idx for idx in unioes_indices if idx != uniao_idx]
            paineis_60_122 = [(i, get_v(item)) for i, item in enumerate(new_list) 
                             if i != uniao_idx and (abs(get_v(item) - LINHA_60) < 5.0 or abs(get_v(item) - LINHA_122) < 5.0)]
            
            ajuste_restante = diferenca_posicao
            
            # Primeiro: tentar ajustar outras uniões
            if outras_unioes and abs(ajuste_restante) > TOLERANCE:
                ajuste_por_uniao = ajuste_restante / len(outras_unioes)
                for outra_idx in outras_unioes:
                    if abs(ajuste_restante) < TOLERANCE:
                        break
                    v_atual = get_v(new_list[outra_idx])
                    novo_valor = v_atual + ajuste_por_uniao
                    if UNION_MIN <= novo_valor <= UNION_MAX:
                        if isinstance(new_list[outra_idx], dict):
                            new_list[outra_idx]["value"] = novo_valor
                        else:
                            new_list[outra_idx] = novo_valor
                        ajuste_restante -= ajuste_por_uniao
            
            # Segundo: ajustar painéis 60/122 mais próximos
            if abs(ajuste_restante) > TOLERANCE and paineis_60_122:
                paineis_60_122.sort(key=lambda x: abs(x[0] - uniao_idx))
                for painel_idx, painel_val in paineis_60_122:
                    if abs(ajuste_restante) < TOLERANCE:
                        break
                    ajuste_painel = max(-10.0, min(10.0, ajuste_restante))
                    novo_valor = painel_val + ajuste_painel
                    if novo_valor > 0:
                        if isinstance(new_list[painel_idx], dict):
                            new_list[painel_idx]["value"] = novo_valor
                        else:
                            new_list[painel_idx] = novo_valor
                        ajuste_restante -= ajuste_painel
            
            # Se ainda sobrar diferença, ajustar a própria união
            if abs(ajuste_restante) > TOLERANCE:
                soma_anteriores_ajustada = self.sum_list(new_list[:uniao_idx])
                nova_uniao_valor_ajustada = posicao_desejada_inicio_uniao - soma_anteriores_ajustada
                nova_uniao_valor = max(UNION_MIN, min(UNION_MAX, nova_uniao_valor_ajustada))
        
        # Aplicar valor final da união
        if isinstance(new_list[uniao_idx], dict):
            new_list[uniao_idx]["value"] = nova_uniao_valor
        else:
            new_list[uniao_idx] = nova_uniao_valor
        return new_list
    
    def alinhar_unioes_ilhas_esquerda(self):
        """
        Alinha uniões com as paredes esquerdas das ilhas (obstáculos).
        Mantém comportamento original como botão.
        """
        result_list = self._alinhar_unioes_ilhas(lado_esquerdo=True)
        
        # Aplicar mudanças se retornou lista válida
        if result_list is not None:
            modo_selecionado = self.calculos_modos.button_group.checkedId()
            is_vertical = (modo_selecionado == 0)
            
            if is_vertical:
                horizontais_originais = self.horizontal_lines_overlay.get_linhas()
                self.laje_atual.linhas_verticais = result_list
                self.set_linhas(result_list, horizontais_originais if horizontais_originais else [])
            else:
                verticais_originais = self.vertical_lines_overlay.get_linhas()
                self.laje_atual.linhas_horizontais = result_list
                self.set_linhas(verticais_originais if verticais_originais else [], result_list)
            
            self.atualizar_visualizacao()
            QMessageBox.information(self, "Alinhamento", "Uniões alinhadas com as paredes esquerda/fundo das ilhas.")
    
    def alinhar_unioes_ilhas_direita(self):
        """
        Alinha uniões com as paredes direitas das ilhas (obstáculos).
        Mantém comportamento original como botão.
        """
        result_list = self._alinhar_unioes_ilhas(lado_esquerdo=False)
        
        # Aplicar mudanças se retornou lista válida
        if result_list is not None:
            modo_selecionado = self.calculos_modos.button_group.checkedId()
            is_vertical = (modo_selecionado == 0)
            
            if is_vertical:
                horizontais_originais = self.horizontal_lines_overlay.get_linhas()
                self.laje_atual.linhas_verticais = result_list
                self.set_linhas(result_list, horizontais_originais if horizontais_originais else [])
            else:
                verticais_originais = self.vertical_lines_overlay.get_linhas()
                self.laje_atual.linhas_horizontais = result_list
                self.set_linhas(verticais_originais if verticais_originais else [], result_list)
            
            self.atualizar_visualizacao()
            QMessageBox.information(self, "Alinhamento", "Uniões alinhadas com as paredes direita/topo das ilhas.")

    def on_smart_interpret(self):
        """
        Dedução de layout baseado em aprendizado de máquina.
        Analisa o marco atual e busca configurações similares validadas.
        """
        if not self.laje_atual or not self.laje_atual.coordenadas:
            self.ai_status_message.emit(f"Aviso", "Nenhuma laje selecionada para interpretação.", "{DS.GOLD}")
            return

        # Executa a interpretação
        prediction = self._perform_smart_interpret()
        
        if not prediction:
            return

        confianca = prediction.get('confianca', 0)
        
        # Solicitar feedback via nova UI em vez de QMessageBox
        context = {
            'type': 'smart_interpret',
            'prediction': prediction
        }
        
        # Salvar contexto para processar a resposta
        self.current_ai_context = context
        
        self.ai_feedback_requested.emit(
            "Validação da Interpretação",
            f"O resultado está satisfatório?",
            context,
            confianca
        )

    def on_ai_feedback_response(self, action_id, comment):
        """Processa a resposta vinda do AIFeedbackWidget"""
        if not self.current_ai_context:
            return
            
        context = self.current_ai_context
        feedback_type = context.get('type')
        
        if feedback_type == 'smart_interpret':
            self._handle_smart_interpret_feedback(action_id, comment, context)
        elif feedback_type == 'smart_dimensions':
            self._handle_smart_dimensions_feedback(action_id, comment, context)
        elif feedback_type == 'train_validate':
            self._handle_train_validate_feedback(action_id, comment, context)
            
        # Limpar contexto apenas se não for o estado intermediário de seleção de erros
        if action_id != "selecionar_erros":
            self.current_ai_context = None

    def _handle_smart_interpret_feedback(self, action_id, comment, context):
        if action_id == "sim":
            # Feedback Positivo - Reforçar aprendizado
            self._save_current_as_training(feedback_type="positive", comentario="Validação Positiva Automática")
            self._clone_to_training_population("Validação Positiva Automática", feedback_type="positive")
            self.ai_status_message.emit(f"Sucesso", "Obrigado! O sistema aprendeu com este sucesso.", "{DS.SUCCESS}")
            
        elif action_id == "refinar":
            # Apenas registra o log
            print("[AI] Usuário optou por refinamento manual.")
            self.ai_status_message.emit(f"Refinamento", "Faça os ajustes manuais necessários.", "{DS.INTERACTIVE}")

        elif action_id == "selecionar_erros":
            # Estado intermediário: Apenas aguardar comentário do usuário
            # Para Linhas, não ativamos seleção visual, apenas texto.
            pass

        elif action_id == "nao":
            # Feedback Negativo - Aprender com erro
            # Salvar o que foi aplicado como EXEMPLO NEGATIVO no DB
            self._save_current_as_training(feedback_type="negative", comentario=f"REJEITADO: {comment}")
            # CLONAR TAMBÉM PARA A PASTA DE ERROS
            self._clone_to_training_population(comment, feedback_type="negative")
            
            # Perguntar se quer tentar novamente (via status/novo pedido ou apenas registrar)
            self.ai_status_message.emit(f"Erro Registrado", "Aprendi com este erro. Tente novamente se desejar.", "{DS.DANGER}")

    @property
    def current_ai_context(self):
        return getattr(self, '_current_ai_context', None)
    
    @current_ai_context.setter
    def current_ai_context(self, val):
        self._current_ai_context = val

    def on_smart_interpret_requested_from_signal(self, title, message, context, confidence):
        # Cache o contexto para quando a resposta vier
        self.current_ai_context = context
        # O sinal em si é repassado pela MainWindow para o FeedbackWidget


    def _perform_smart_interpret(self, silent=False):
        """Lógica interna de predição e aplicação"""
        obstaculos = getattr(self.laje_atual, 'obstaculos', [])
        
        try:
            # Obter modo de inteligência da toolbar
            intelligence_mode = self.edition_toolbar.get_selected_intelligence_mode()
            prediction = self.learner.predict_layout(self.laje_atual.coordenadas, obstaculos, intelligence_mode=intelligence_mode)
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "Erro", f"Falha na interpretação: {e}")
            print(f"[ERROR] Falha na interpretação inteligente: {e}")
            return None
            
        if not prediction:
            if not silent:
                QMessageBox.information(
                    self, 
                    "Interpretação Inteligente", 
                    "Ainda não tenho conhecimento suficiente para esta forma (ou apenas exemplos negativos).\n"
                    "Por favor, configure manualmente e use 'Validar como Treino' para me ensinar!"
                )
            return None
            
        # Aplicar configurações SILENCIOSAMENTE para evitar reações em cadeia da UI
        modo = prediction['modo_calculo']
        
        # Bloquear sinais para evitar que a UI dispare recálculos rígidos
        self.calculos_modos.blockSignals(True)
        try:
            self.calculos_modos.set_modo(modo)
            
            # Opções extras
            opcoes = prediction.get('opcoes_extras', {})
            unioes = opcoes.get('unioes_bordes', False)
            self.calculos_modos.checkbox_unioes_bordes.setChecked(unioes)
            
            # Atualiza apenas visualmente o estado do checkbox (sem disparar lógica)
            # Se houver outros elementos de UI para atualizar, faça aqui
        finally:
            self.calculos_modos.blockSignals(False)

        # Atualizar Modelo de Dados
        self.laje_atual.modo_selecionado = modo
        self.laje_atual.unioes_nos_bordes = unioes
        
        # Aplicar linhas sugeridas diretamente no modelo e overlays
        linhas_v = prediction['linhas_verticais']
        linhas_h = prediction['linhas_horizontais']
        
        self.laje_atual.linhas_verticais = linhas_v
        self.laje_atual.linhas_horizontais = linhas_h
        
        # Atualizar overlays SEM chamar correções de sobra (IA já acerta tudo)
        # Usar flag para evitar update_wall_value durante set_linhas
        self._skip_sobra_calculation = True
        try:
            self.set_linhas(linhas_v, linhas_h)
        finally:
            self._skip_sobra_calculation = False

        # Atualização final de visualização SEM cotas (IA cotas será chamada depois separadamente)
        # Usar flag para evitar draw_dimensions durante atualizar_visualizacao
        self._skip_dimensions_during_update = True
        try:
            self.atualizar_visualizacao()
        finally:
            self._skip_dimensions_during_update = False
        
        # Reconectar sinais após IA terminar (para que mudanças manuais funcionem)
        try:
            self.vertical_lines_overlay.linhas_changed.disconnect()
        except:
            pass
        try:
            self.horizontal_lines_overlay.linhas_changed.disconnect()
        except:
            pass
        self.vertical_lines_overlay.linhas_changed.connect(self.on_vertical_lines_changed)
        self.horizontal_lines_overlay.linhas_changed.connect(self.on_horizontal_lines_changed)
            
        return prediction
        
    def on_train_validate(self):
        """
        Ensina o sistema registrando o layout atual como exemplo positivo.
        """
        if not self.laje_atual or not self.laje_atual.coordenadas:
            self.ai_status_message.emit(f"Aviso", "Nenhuma laje selecionada para validação.", "{DS.GOLD}")
            return
            
        # Para validação manual (botão treinar), ainda podemos usar um input rápido 
        # ou mover para um modo de comentário no AIFeedbackWidget.
        # Vamos usar o AIFeedbackWidget para ser consistente.
        
        context = {
            'type': 'train_validate'
        }
        
        # Salvar contexto para processar a resposta
        self.current_ai_context = context
        
        self.ai_feedback_requested.emit(
            "Validar Treinamento",
            "Deseja salvar este layout como um exemplo positivo de treinamento?",
            context,
            1.0
        )

    def _handle_train_validate_feedback(self, action_id, comment, context):
        if action_id == "sim":
            if self._save_current_as_training(feedback_type="positive", comentario=comment):
                self._clone_to_training_population(comment, feedback_type="positive")
                mode = self.edition_toolbar.get_selected_intelligence_mode() + 1
                self.ai_status_message.emit("Sucesso", f"Layout aprendido e copiado para 'Pavimento Treino Modo {mode}'!", "{DS.SUCCESS}")
            else:
                self.ai_status_message.emit(f"Erro", "Falha ao salvar dados de treinamento.", "{DS.DANGER}")
        else:
            self.ai_status_message.emit(f"Cancelado", "Validação de treinamento cancelada.", "{DS.SECONDARY}")


    def _clone_to_training_population(self, comentario, feedback_type="positive"):
        """Clona a laje atual e emite sinal para MainWindow salvar na obra Populacao_Treino"""
        print(f"[DEBUG] Iniciando _clone_to_training_population ({feedback_type})...")
        try:
            # 1. Clonar Laje Atual
            # Sanitize manual_dimensions to prevent Pickle errors with QGraphicsItems
            if hasattr(self.laje_atual, 'manual_dimensions') and self.laje_atual.manual_dimensions:
                clean_dims = []
                for item in self.laje_atual.manual_dimensions:
                    if isinstance(item, dict):
                        # Filter only serializable types
                        clean_item = {k: v for k, v in item.items() 
                                    if isinstance(v, (str, int, float, bool, list, dict, type(None))) }
                        clean_dims.append(clean_item)
                
                # Temporarily replace with clean list for deepcopy
                original_dims = self.laje_atual.manual_dimensions
                self.laje_atual.manual_dimensions = clean_dims
                try:
                    nova_laje = copy.deepcopy(self.laje_atual)
                finally:
                    # Restore original list with UI objects if any were present
                    self.laje_atual.manual_dimensions = original_dims
            else:
                nova_laje = copy.deepcopy(self.laje_atual)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            tipo_prefix = "TREINO" if feedback_type == "positive" else "ERRO"
            suffix = f"_{comentario}" if comentario else ""
            nova_laje.nome = f"{self.laje_atual.nome}_{tipo_prefix}_{timestamp}{suffix}"
            
            # Garantir que as linhas (vetores) estejam explicitamente salvas no objeto
            nova_laje.linhas_verticais = self.vertical_lines_overlay.get_linhas()
            nova_laje.linhas_horizontais = self.horizontal_lines_overlay.get_linhas()
            nova_laje.modo_selecionado = self.calculos_modos.button_group.checkedId()
            
            # Adicionar metadado do modo de inteligência para o MainWindow saber onde salvar
            try:
                if hasattr(self, 'edition_toolbar') and self.edition_toolbar:
                    mode = self.edition_toolbar.get_selected_intelligence_mode()
                    nova_laje.intelligence_mode = mode
                    nova_laje.dimension_training_mode = mode # Garantir para cotas também
                else:
                    nova_laje.intelligence_mode = 0
                    nova_laje.dimension_training_mode = 0
            except Exception:
                nova_laje.intelligence_mode = 0
                nova_laje.dimension_training_mode = 0
            
            # Adicionar comentário à laje para referência
            nova_laje.observacoes = f"[{feedback_type.upper()}] {comentario}"
            
            # 2. Emitir sinal para MainWindow gerenciar a persistência na obra correta
            self.training_example_created.emit(nova_laje, comentario, feedback_type)
            
            print(f"[INFO] Sinal de clonagem emitido para: {nova_laje.nome} ({feedback_type})")
            
        except Exception as e:
            print(f"[ERROR] Falha ao preparar clone para Populacao_Treino: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Aviso", f"Não foi possível preparar cópia visual: {e}")


    def _save_current_as_training(self, feedback_type="positive", comentario="") -> bool:
        """Helper para salvar o estado atual como treino"""
        if not self.laje_atual or not self.laje_atual.coordenadas:
            return False
            
        # Coletar dados atuais
        obstaculos = getattr(self.laje_atual, 'obstaculos', [])
        modo_calculo = self.calculos_modos.button_group.checkedId()
        intelligence_mode = self.edition_toolbar.get_selected_intelligence_mode()
        
        # Pegar linhas dos overlays que podem ter sido editadas manualmente
        linhas_v = self.vertical_lines_overlay.get_linhas()
        linhas_h = self.horizontal_lines_overlay.get_linhas()
        
        opcoes_extras = {
            "unioes_bordes": self.calculos_modos.unioes_nos_bordes_ativado(),
            "alinhamento_ilhas_esq": self.calculos_modos.unioes_ilhas_esquerda_ativado(),
            "alinhamento_ilhas_dir": self.calculos_modos.unioes_ilhas_direita_ativado()
        }
        
        # Salvar
        return self.learner.save_training_example(
            self.laje_atual.coordenadas,
            obstaculos,
            modo_calculo,
            linhas_v,
            linhas_h,
            opcoes_extras,
            comentario,
            feedback_type,
            intelligence_mode
        )


    def on_rules_requested(self):
        """Abre o diálogo de gerenciamento de regras de LINHAS"""
        # Obter modo atual da toolbar inteligente (M1/M2)
        mode = self.edition_toolbar.ai_mode_group.checkedId()
        if mode == -1: mode = 0
            
        dialog = RulesDialog(self.learner, rule_type='line', intelligence_mode=mode, parent=self)
        dialog.exec()

    def on_rules_dimensions_requested(self):
        """Abre o diálogo de gerenciamento de regras de COTAS"""
        # Obter modo atual da toolbar inteligente (M1/M2)
        mode = self.edition_toolbar.ai_mode_group.checkedId()
        if mode == -1: mode = 0
            
        dialog = RulesDialog(self.learner, rule_type='dimension', intelligence_mode=mode, parent=self)
        dialog.exec()

    def on_smart_dimensions_clicked(self):
        """
        Solicita ajustes inteligentes de cotas para o layout atual.
        """
        if not self.laje_atual:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Selecione uma laje primeiro.")
            return

        # Executa a interpretação de cotas
        result = self._perform_smart_dimensions(silent=False)
        
        if not result:
            return

        count_kept = result['count_kept']
        count_removed = result['count_removed']
        
        # --- Feedback Interativo via Nova UI ---
        context = {
            'type': 'smart_dimensions',
            'count_kept': count_kept,
            'count_removed': count_removed
        }
        
        # Salvar contexto para processar a resposta
        self.current_ai_context = context
        
        self.ai_feedback_requested.emit(
            "Avaliação da IA",
            f"IA Sugeriu: {count_kept} mantidas / {count_removed} ocultadas.\nComo você avalia o resultado?",
            context,
            0.8 # Confiança estimada para cotas
        )

    def _perform_smart_dimensions(self, silent=True):
        """
        Lógica interna de predição e aplicação de cotas inteligentes.
        """
        from PySide6.QtWidgets import QApplication, QMessageBox
        from laje_src.services.ai.dimension_learner import DimensionLearner

        if not self.laje_atual:
            return None

        # 1. Garantir que DimensionLearner está inicializado
        if not hasattr(self, 'dimension_learner'):
            self.dimension_learner = DimensionLearner()

        # 2. Forçar regeneração de TODAS as cotas candidatas
        self.scene.generated_candidates = []
        
        # Garantir que cotas automáticas estão ativas para geração
        self.show_auto_dimensions = True 
        self.scene.show_auto_dimensions = True
        
        # Atualizar (síncrono se possível)
        self.atualizar_visualizacao(immediate=True)
        QApplication.processEvents()
        
        candidates = getattr(self.scene, 'generated_candidates', [])
        if not candidates:
            if not silent:
                self.ai_status_message.emit(f"Info", "Nenhuma cota foi gerada para análise.", "{DS.INTERACTIVE}")
            return None
            
        # 3. Context Data
        coords = self.laje_atual.coordenadas
        if not coords:
            return None

        min_x = min(x for x, y in coords)
        max_x = max(x for x, y in coords)
        min_y = min(y for x, y in coords)
        max_y = max(y for x, y in coords)
        width = max_x - min_x
        height = max_y - min_y
        
        context_data = {
            "slab_width": width,
            "slab_height": height,
            "min_x": min_x,
            "min_y": min_y
        }
        
        current_mode = self.calculos_modos.button_group.checkedId()
        # Mapear modo UI para modo learner
        mode_for_learner = current_mode if current_mode >= 0 else 0

        # 4. Prever (Batch)
        candidates_clean = []
        for c in candidates:
            # Remover itens não serializáveis e ajustar chaves se necessario para extração de features
            c_clean = {k:v for k,v in c.items() if k not in ['text_item', 'p1', 'p2']}
            candidates_clean.append(c_clean)
            
        predictions = self.dimension_learner.predict(candidates_clean, context_data, mode=mode_for_learner)
        
        # 5. Aplicar REGRAS TÉCNICAS (Heurísticas) sobre as predições
        self.learner.apply_dimension_rules(candidates_clean, mode=mode_for_learner)

        # Combinar candidatos com predições e aplicar diretamente
        count_kept = 0
        count_removed = 0
        
        # Resetar cotas excluídas (confiamos na IA)
        self.laje_atual.excluded_dimensions = []
        # Limpar da cena também para evitar desincronia
        if hasattr(self.scene, 'excluded_dimensions'):
            self.scene.excluded_dimensions = []
        
        for i, pred in enumerate(predictions):
            if i >= len(candidates): break
            cand = candidates[i]
            cand_clean = candidates_clean[i]
            dim_id = cand['dimension_id']
            
            # 1. Decisão de visibilidade (Predição vs Regra)
            should_keep = pred['keep']
            
            # Se a regra explicitamente marcou como False (ocultar), ela tem precedência
            if cand_clean.get('keep_by_rule') is False:
                should_keep = False
            
            if should_keep:
                count_kept += 1
                
                # 2. Aplicar OFFSSETS (Posicionamento Inteligente)
                if pred.get('confidence', 0) > 0.6:
                    off_x = pred.get('offset_x', 0.0)
                    off_y = pred.get('offset_y', 0.0)
                    
                    if abs(off_x) > 1.0 or abs(off_y) > 1.0:
                        new_pos_x = cand.get('pos_x', 0.0) + off_x
                        new_pos_y = cand.get('pos_y', 0.0) + off_y
                        
                        if not hasattr(self.laje_atual, 'dimension_positions') or self.laje_atual.dimension_positions is None:
                            self.laje_atual.dimension_positions = {}
                        
                        self.laje_atual.dimension_positions[dim_id] = {
                            "pos_x": new_pos_x,
                            "pos_y": new_pos_y
                        }
            else:
                excl_entry = {
                    "type": cand.get('type', 'auto'),
                    "unique_id": dim_id,
                    "value": cand.get('value', ''),
                    "x": cand.get('pos_x'),
                    "y": cand.get('pos_y'),
                    "rotation": cand.get('rotation', 0.0)
                }
                self.laje_atual.excluded_dimensions.append(excl_entry)
                count_removed += 1
        
        # Atualizar Visual Final
        self.atualizar_visualizacao(immediate=True)
        return {
            'count_kept': count_kept,
            'count_removed': count_removed,
            'predictions': predictions
        }


    def _handle_smart_dimensions_feedback(self, action_id, comment, context):
        if action_id == "sim": # "Boa"
            # Feedback Positivo: Salva o estado atual como correto
            self.on_validate_dimensions_training()
            self.ai_status_message.emit(f"Sucesso", "Obrigado! O sistema aprendeu com este ajuste.", "{DS.SUCCESS}")
            
        elif action_id == "refinar": # "Quase"
            # Usuário vai ajustar manualmente e depois validar
            self.ai_status_message.emit(f"Ajuste Manual", "Faça os ajustes necessários e depois use 'Validar Treino Cotas'.", "{DS.INTERACTIVE}")
            
        elif action_id == "selecionar_erros": # Clique inicial em "Ruim"
            # Modo de Erro: Usuário seleciona o que está errado
            self.start_dimension_error_selection_mode()
            
        elif action_id == "nao": # Clique em "Enviar Feedback" após comentário
            # Finaliza o processo com o comentário coletado no Widget
            self._finish_dimension_error_selection(comment)


    def start_dimension_error_selection_mode(self):
        """Inicia modo de seleção de erros"""
        self.ai_status_message.emit(f"Modo de Erro", "Selecione as cotas INCORRETAS no desenho e pressione ENTER.", "{DS.INTERACTIVE}")
        self.edition_toolbar.on_select_clicked() # Force select mode
        self.scene.clear_selection()
        self._feedback_error_mode = True

    def _finish_dimension_error_selection(self, comentario=None):
        """Finaliza a seleção de erros e salva o feedback"""
        from PySide6.QtWidgets import QMessageBox, QGraphicsTextItem, QGraphicsLineItem
        import math

        selected_items = self.scene.selectedItems()
        
        if not selected_items:
             self.ai_status_message.emit(f"Aviso", "Nenhuma cota selecionada para relato de erro.", "{DS.GOLD}")
             self._feedback_error_mode = False
             return

        # 1. Definir Comentário
        if not comentario:
            comentario = "Erro identificado pelo usuário via seleção direta no desenho."

        # 2. Preparar Batch de Treinamento
        if not hasattr(self, 'dimension_learner'):
            from laje_src.services.ai.dimension_learner import DimensionLearner
            self.dimension_learner = DimensionLearner()

        coords = self.laje_atual.coordenadas
        if not coords: return
        
        min_x = min(x for x, y in coords)
        max_x = max(x for x, y in coords)
        min_y = min(y for x, y in coords)
        max_y = max(y for x, y in coords)
        width = max_x - min_x
        height = max_y - min_y
        
        context_data = {
            "slab_width": width,
            "slab_height": height,
            "min_x": min_x,
            "min_y": min_y
        }
        
        mode_for_learner = self.edition_toolbar.ai_mode_group.checkedId()
        if mode_for_learner == -1: mode_for_learner = 0
            
        training_batch = []
        
        # Mapeamento robusto de seleção
        selected_ids = set()
        selected_positions = set()
        
        # Coletar IDs e Posições dos itens selecionados (Texto e Linhas)
        for item in selected_items:
            # Tentar obter ID direto
            if hasattr(item, 'dimension_id') and item.dimension_id:
                selected_ids.add(item.dimension_id)
            elif hasattr(item, 'line_id') and item.line_id:
                # Se for linha, tentar inferir ID da cota correspondente
                # Padrão comum: dim_line_{line_id}
                selected_ids.add(f"dim_line_{item.line_id}")
                # Ou adicionar o próprio ID da linha caso a cota use o mesmo ID
                selected_ids.add(item.line_id)
            
            # Adicionar posição para match visual (fuzzy)
            pos = item.scenePos() # Posição na cena
            # Normalizar para lista de tuplas para busca rápida (arredondado)
            # Mas usaremos distância euclidiana no loop para ser mais seguro
            
        visible_dims = self.scene.get_all_visible_dimensions(coords)
        
        count_errors = 0
        count_ok = 0
        
        # Lista de IDs que foram confirmados como erro (para remoção visual depois)
        confirmed_error_ids = set()

        for dim in visible_dims:
            d_x = dim.get('x', 0)
            d_y = dim.get('y', 0)
            uid = dim.get('unique_id') or dim.get('dimension_id')
            
            # Verificar se está selecionado por ID
            is_selected = False
            if uid and uid in selected_ids:
                is_selected = True
            
            # Se não bateu por ID, verificar por proximidade com qualquer item de texto selecionado
            if not is_selected:
                for item in selected_items:
                    if isinstance(item, QGraphicsTextItem):
                        ipos = item.scenePos()
                        # Distância tolerável de 5 unidades (cm?)
                        dist = math.sqrt((d_x - ipos.x())**2 + (d_y - ipos.y())**2)
                        if dist < 5.0:
                            is_selected = True
                            break
            
            if is_selected:
                training_batch.append({
                    "dimension_data": dim,
                    "context_data": context_data,
                    "action_keep": False, # ERRO: Deveria ter removido
                    "mode": mode_for_learner,
                    "feedback_type": "negative",
                    "source": f"error_report",
                    "comentario": comentario
                })
                count_errors += 1
                if uid: confirmed_error_ids.add(uid)
                
                # Adicionar à lista de exclusão do modelo para persistir a remoção
                excl_entry = dict(dim)
                excl_entry['unique_id'] = uid
                if not hasattr(self.laje_atual, 'excluded_dimensions'):
                    self.laje_atual.excluded_dimensions = []
                self.laje_atual.excluded_dimensions.append(excl_entry)
                
            else:
                training_batch.append({
                    "dimension_data": dim,
                    "context_data": context_data,
                    "action_keep": True, # OK: Manteve corretamente
                    "mode": mode_for_learner,
                    "feedback_type": "positive",
                    "source": "implicit_validation"
                })
                count_ok += 1
                
        # Also include previously excluded items as Negatives (implicit)
        excluded_dims = getattr(self.laje_atual, 'excluded_dimensions', [])
        for dim in excluded_dims:
             # Evitar duplicar o que acabamos de adicionar
             uid = dim.get('unique_id')
             if uid and uid in confirmed_error_ids:
                 continue
                 
             training_batch.append({
                "dimension_data": dim,
                "context_data": context_data,
                "action_keep": False, # Ja estava excluido
                "mode": mode_for_learner,
                "feedback_type": "negative",
                "source": "implicit_validation_excluded"
            })
        
        # Save
        if count_errors > 0 or count_ok > 0:
            self.dimension_learner.save_training_examples(training_batch)
            if hasattr(self.dimension_learner, 'train'):
                self.dimension_learner.train()
        
        # Remover visualmente as cotas marcadas como erro
        # Melhor estratégia: remover ITEMS da cena que deram match no ID
        items_to_remove = []
        for item in self.scene.items():
            if isinstance(item, QGraphicsTextItem):
                if hasattr(item, 'dimension_id') and item.dimension_id in confirmed_error_ids:
                    items_to_remove.append(item)
            # Também remover se for uma das selecionadas explicitamente (segurança)
            if item in selected_items and isinstance(item, QGraphicsTextItem):
                if item not in items_to_remove:
                    items_to_remove.append(item)

        for item in items_to_remove:
             if item.scene() == self.scene:
                 self.scene.removeItem(item)

        self._feedback_error_mode = False
        self.scene.clear_selection()
        self.edition_toolbar.on_select_clicked() # Reset mode
        self.atualizar_visualizacao(immediate=True) # Atualizar para garantir consistência
        
        # Clonar visualmente para obra de erros de cotas
        self._clone_to_training_population(f"{count_errors} erros reportados", feedback_type="dimension_error")
        
        self.ai_status_message.emit("Feedback Enviado", f"Registrados {count_errors} erros e {count_ok} acertos.", "{DS.SUCCESS}")


    def on_validate_dimensions_training(self):
        """Valida e salva o estado atual das cotas como exemplo de treinamento (feedback positivo/negativo)"""
        from PySide6.QtWidgets import QMessageBox
        from laje_src.services.ai.dimension_learner import DimensionLearner


        if not self.laje_atual:
             return

        if not hasattr(self, 'dimension_learner'):
            self.dimension_learner = DimensionLearner()

        coords = self.laje_atual.coordenadas
        if not coords: return
        min_x = min(x for x, y in coords)
        max_x = max(x for x, y in coords)
        min_y = min(y for x, y in coords)
        max_y = max(y for x, y in coords)
        width = max_x - min_x
        height = max_y - min_y
        
        context_data = {
            "slab_width": width,
            "slab_height": height,
            "min_x": min_x,
            "min_y": min_y
        }

        # Obter modo atual da toolbar inteligente (0=M1/1=M2)
        mode_for_learner = self.edition_toolbar.ai_mode_group.checkedId()
        if mode_for_learner == -1: mode_for_learner = 0

        # 3. Coletar Exemplos
        visible_dims = self.scene.get_all_visible_dimensions(coords)
        excluded_dims = getattr(self.laje_atual, 'excluded_dimensions', [])
        
        # Criar mapeamento de candidatos para cálculo de offset
        candidates_dict = {}
        if hasattr(self.scene, 'generated_candidates'):
            for c in self.scene.generated_candidates:
                if c.get('dimension_id'):
                    candidates_dict[c['dimension_id']] = c

        training_batch = []
        
        # Positivos
        for dim in visible_dims:
            uid = dim.get('unique_id')
            offset_x, offset_y = 0.0, 0.0
            dim_to_save = dim
            
            # Se temos o candidato original, calculamos o offset real que o usuário aplicou
            if uid and uid in candidates_dict:
                cand = candidates_dict[uid]
                # Características baseadas no candidato original
                offset_x = dim.get("pos_x", 0) - cand.get("pos_x", 0)
                offset_y = dim.get("pos_y", 0) - cand.get("pos_y", 0)
                
                dim_to_save = dim.copy()
                dim_to_save["pos_x"] = cand.get("pos_x")
                dim_to_save["pos_y"] = cand.get("pos_y")

            training_batch.append({
                "dimension_data": dim_to_save,
                "context_data": context_data,
                "action_keep": True,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "mode": mode_for_learner,
                "feedback_type": "positive"
            })
            
        # Negativos
        seen_excluded_ids = set()
        for dim in excluded_dims:
            if isinstance(dim, dict):
                uid = dim.get('unique_id')
                # Evitar duplicatas se o mesmo ID aparecer
                if uid:
                    if uid in seen_excluded_ids: continue
                    seen_excluded_ids.add(uid)
                elif dim.get('value'):
                     # Deduplicar por valor+pos se sem ID
                     key = f"{dim.get('value')}_{dim.get('x')}_{dim.get('y')}"
                     if key in seen_excluded_ids: continue
                     seen_excluded_ids.add(key)

                training_batch.append({
                    "dimension_data": dim,
                    "context_data": context_data,
                    "action_keep": False,
                    "mode": mode_for_learner,
                    "feedback_type": "negative"
                })
                
        if not training_batch:
            self.ai_status_message.emit(f"Info", "Não há cotas para validar.", "{DS.INTERACTIVE}")
            return
            
        try:
            self.dimension_learner.save_training_examples(training_batch)
            if hasattr(self.dimension_learner, 'train'):
                self.dimension_learner.train()
                
            # Clonar visualmente para obra de treino de cotas
            self._clone_to_training_population("Validação Cotas", feedback_type="dimension_training")
            
            self.ai_status_message.emit("Sucesso", f"Aprendizado salvo!\n{len(visible_dims)} cotas confirmadas\n{len(excluded_dims)} cotas rejeitadas", "{DS.SUCCESS}")
        except Exception as e:
            self.ai_status_message.emit("Erro", f"Falha ao salvar treinamento: {e}", "{DS.DANGER}")
            print(f"[ERROR] Validate Dimensions Training: {e}")


    def sync_manual_dimensions_to_model(self):
        """Sincroniza cotas manuais e exclusões da cena para o modelo Laje antes de salvar."""
        if not self.laje_atual or not self.scene:
            return

        # 1. Sincronizar Cotas Manuais
        manual_dims = []
        if hasattr(self.scene, 'manual_dimension_data'):
            for item, data in self.scene.manual_dimension_data.items():
                # Atualizar valores atuais (pois podem ter sido movidos)
                # Garantir que o item ainda está na cena
                if item.scene() != self.scene:
                    continue
                    
                data_copy = dict(data)
                data_copy['pos_x'] = round(item.pos().x(), 2)
                data_copy['pos_y'] = round(item.pos().y(), 2)
                data_copy['rotation'] = round(item.rotation(), 2)
                data_copy['text'] = item.toPlainText() 
                manual_dims.append(data_copy)
        
        self.laje_atual.manual_dimensions = manual_dims

        # 2. Sincronizar Cotas Excluídas (MUITO IMPORTANTE para persistência de un-delete)
        if hasattr(self.scene, 'excluded_dimensions'):
            # Atualizar modelo com o que temos na cena (que reflete exclusões e re-criações)
            self.laje_atual.excluded_dimensions = list(self.scene.excluded_dimensions)
            # print(f"[DEBUG SYNC] Sincronizadas {len(self.scene.excluded_dimensions)} exclusões para o modelo.")
        
        # print(f"[DEBUG SYNC] Sincronizadas {len(manual_dims)} cotas manuais para o modelo.")
