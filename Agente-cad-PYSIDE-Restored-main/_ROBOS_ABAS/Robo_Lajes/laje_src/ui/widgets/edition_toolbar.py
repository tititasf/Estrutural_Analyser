from ..styles import DS
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLineEdit, QHBoxLayout, QLabel, QButtonGroup, 
                               QFrame, QTextEdit, QSizePolicy, QGridLayout)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from typing import Optional
from .calculos_modos_widget import RoundButton


class EditionToolbar(QWidget):
    """Painel de botões de edição no lado esquerdo do canvas"""
    
    # Sinais emitidos quando botões são clicados ou teclas são pressionadas
    # Sinais emitidos quando botões são clicados ou teclas são pressionadas
    select_mode_requested = Signal()
    make_dimension_requested = Signal()
    move_requested = Signal()
    offset_requested = Signal()
    delete_requested = Signal()
    join_requested = Signal()
    join_automatico_requested = Signal()
    undo_requested = Signal()
    refazer_cotas_requested = Signal()
    delete_all_dimensions_requested = Signal()
    toggle_link_requested = Signal()
    smart_interpret_requested = Signal()
    train_validate_requested = Signal()
    rules_requested = Signal()
    rules_dimensions_requested = Signal() # Novo sinal para regras de cotas
    smart_dimensions_requested = Signal() # Novo sinal para cotas inteligentes
    
    validate_dimensions_training_requested = Signal() # Novo sinal para validar cotas treino
    
    # Sinais de Feedback AI (Novos)
    dimension_feedback_approved = Signal()
    dimension_feedback_manual = Signal()
    dimension_feedback_errors = Signal(str) # Envia comentário do erro

    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_shortcuts()
        self.mode = None  # 'select', 'move', 'offset'
        self.move_widget = None
        self.offset_widget = None
        self.feedback_widget = None # Widget de feedback dinâmico

    
    def setup_ui(self):
        """Configurar interface do painel refinada (UX/UI Harmony)"""
        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(3)
        
        btn_min_height = 24
        color_btn_height = 24
        
        # --- Instanciação dos Botões ---
        
        # Geometria
        self.btn_select = QPushButton("Sel (S)")
        self.btn_select.setMinimumHeight(btn_min_height)
        self.btn_select.clicked.connect(self.on_select_clicked)
        
        self.btn_move = QPushButton("Mov (M)")
        self.btn_move.setMinimumHeight(btn_min_height)
        self.btn_move.clicked.connect(self.on_move_clicked)
        
        self.btn_offset = QPushButton("Off (O)")
        self.btn_offset.setMinimumHeight(btn_min_height)
        self.btn_offset.clicked.connect(self.on_offset_clicked)
        
        self.btn_join = QPushButton("Join (J)")
        self.btn_join.setMinimumHeight(btn_min_height)
        self.btn_join.clicked.connect(self.on_join_clicked)
        
        self.btn_join_auto = QPushButton("Join Auto")
        self.btn_join_auto.setMinimumHeight(btn_min_height)
        self.btn_join_auto.clicked.connect(self.on_join_automatico_clicked)
        
        self.btn_delete = QPushButton("Excluir (Del)")
        self.btn_delete.setMinimumHeight(btn_min_height)
        self.btn_delete.clicked.connect(self.on_delete_clicked)
        
        self.btn_toggle_link = QPushButton("Vínculo (F)")
        self.btn_toggle_link.setMinimumHeight(btn_min_height)
        self.btn_toggle_link.clicked.connect(self.on_toggle_link_clicked)
        
        self.btn_undo = QPushButton("Voltar (Z)")
        self.btn_undo.setObjectName("btn_undo")
        self.btn_undo.setMinimumHeight(btn_min_height)
        self.btn_undo.clicked.connect(self.on_undo_clicked)
        
        # Cotas Manuais / Globais
        self.btn_dimension = QPushButton("Cota (D)")
        self.btn_dimension.setMinimumHeight(btn_min_height)
        self.btn_dimension.clicked.connect(self.on_dimension_clicked)
        
        self.btn_refazer_cotas = QPushButton("Cotas Auto")
        self.btn_refazer_cotas.setMinimumHeight(color_btn_height)
        self.btn_refazer_cotas.setStyleSheet(f"""
            QPushButton {{
                background-color: {DS.GOLD}; color: black;
                border: 1px solid {DS.WARNING}; border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px;
            }}
            QPushButton:hover {{ background-color: {DS.WARNING}; }}
        """)
        self.btn_refazer_cotas.clicked.connect(self.on_refazer_cotas_clicked)
        
        self.btn_delete_all_dims = QPushButton("Limpar Cotas")
        self.btn_delete_all_dims.setObjectName("btn_delete_all_dims")
        self.btn_delete_all_dims.setMinimumHeight(color_btn_height)
        self.btn_delete_all_dims.setStyleSheet(f"""
            QPushButton {{
                background-color: {DS.DANGER}; color: white;
                border: 1px solid {DS.DANGER}; border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px;
            }}
            QPushButton:hover {{ background-color: #e53935; }}
        """)
        self.btn_delete_all_dims.clicked.connect(self.on_delete_all_dimensions_clicked)
        
        # Inteligência Artificial - Modos
        self.ai_mode_group = QButtonGroup(self)
        self.ai_mode_group.setExclusive(True)
        
        modo_base_style = f"""
            QPushButton {{ background-color: {DS.BORDER}; color: {DS.TEXT}; border: 1px solid {DS.BORDER_STR};
                border-radius: 6px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px; }}
            QPushButton:hover {{ background-color: {DS.BORDER_STR}; }}
        """
        
        self.btn_ai_m1 = QPushButton("M1 (122×60)")
        self.btn_ai_m1.setToolTip("Modo 1: Geral/Verticais (122X60)")
        self.btn_ai_m1.setCheckable(True)
        self.btn_ai_m1.setChecked(True)
        self.btn_ai_m1.setMinimumHeight(color_btn_height)
        self.btn_ai_m1.setStyleSheet(modo_base_style + f"""
            QPushButton:checked {{ background-color: {DS.PURPLE}; color: white; border: 2px solid {DS.PURPLE}; }}
        """)
        self.ai_mode_group.addButton(self.btn_ai_m1, 0)
        
        self.btn_ai_m2 = QPushButton("M2 (122×20)")
        self.btn_ai_m2.setToolTip("Modo 2: Específico/Horizontais (122X20)")
        self.btn_ai_m2.setCheckable(True)
        self.btn_ai_m2.setMinimumHeight(color_btn_height)
        self.btn_ai_m2.setStyleSheet(modo_base_style + f"""
            QPushButton:checked {{ background-color: {DS.MAGENTA}; color: white; border: 2px solid {DS.MAGENTA}; }}
        """)
        self.ai_mode_group.addButton(self.btn_ai_m2, 1)
        
        # Inteligência Artificial - Linhas (Azul)
        style_linhas = f"""
            QPushButton {{ background-color: {DS.INTERACTIVE}; color: white; border: 1px solid {DS.INTERACTIVE};
                border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px; }}
            QPushButton:hover {{ background-color: #3b82f6; }}
        """
        self.btn_smart_interpret = QPushButton("IA Linhas")
        self.btn_smart_interpret.setMinimumHeight(color_btn_height)
        self.btn_smart_interpret.setStyleSheet(style_linhas)
        self.btn_smart_interpret.clicked.connect(self.on_smart_interpret_clicked)
        
        self.btn_train_validate = QPushButton("Val. Linhas")
        self.btn_train_validate.setMinimumHeight(color_btn_height)
        self.btn_train_validate.setStyleSheet(style_linhas)
        self.btn_train_validate.clicked.connect(self.on_train_validate_clicked)
        
        self.btn_rules = QPushButton("Regras Lin.")
        self.btn_rules.setMinimumHeight(color_btn_height)
        self.btn_rules.setStyleSheet(style_linhas)
        self.btn_rules.clicked.connect(self.on_rules_clicked)
        
        # Inteligência Artificial - Cotas (Verde)
        style_cotas = f"""
            QPushButton {{ background-color: {DS.SUCCESS}; color: white; border: 1px solid {DS.SUCCESS};
                border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px; }}
            QPushButton:hover {{ background-color: #22c55e; }}
        """
        self.btn_smart_dimensions = QPushButton("IA Cotas")
        self.btn_smart_dimensions.setMinimumHeight(color_btn_height)
        self.btn_smart_dimensions.setStyleSheet(style_cotas)
        self.btn_smart_dimensions.clicked.connect(self.on_smart_dimensions_clicked)
        
        self.btn_validate_dims_train = QPushButton("Val. Cotas")
        self.btn_validate_dims_train.setMinimumHeight(color_btn_height)
        self.btn_validate_dims_train.setStyleSheet(style_cotas)
        self.btn_validate_dims_train.clicked.connect(self.on_validate_dimensions_training_clicked)
        
        self.btn_rules_dims = QPushButton("Regras Cot.")
        self.btn_rules_dims.setMinimumHeight(color_btn_height)
        self.btn_rules_dims.setStyleSheet(style_cotas)
        self.btn_rules_dims.clicked.connect(self.on_rules_dimensions_clicked)
        
        # Feedback Container
        self.feedback_container = QWidget()
        self.feedback_layout = QVBoxLayout(self.feedback_container)
        self.feedback_layout.setContentsMargins(0, 0, 0, 0)
        self.feedback_layout.setSpacing(0)
        
        # --- Montagem do Grid Refinado ---
        
        # Linha 0: Ferramentas Básicas
        layout.addWidget(self.btn_select, 0, 0)
        layout.addWidget(self.btn_move, 0, 1)
        layout.addWidget(self.btn_offset, 0, 2)
        layout.addWidget(self.btn_join, 0, 3)
        layout.addWidget(self.btn_join_auto, 0, 4)
        layout.addWidget(self.btn_delete, 0, 5)
        layout.addWidget(self.btn_toggle_link, 0, 6)
        layout.addWidget(self.btn_undo, 0, 7)
        
        # Linha 1: Ferramentas de Cota
        layout.addWidget(self.btn_dimension, 1, 0)
        layout.addWidget(self.btn_refazer_cotas, 1, 1, 1, 3)
        layout.addWidget(self.btn_delete_all_dims, 1, 4, 1, 4)
        
        # Linha 2: IA de Linhas (Modo 1 + Botões Azuis)
        layout.addWidget(self.btn_ai_m1, 2, 0)
        layout.addWidget(self.btn_smart_interpret, 2, 1, 1, 2)
        layout.addWidget(self.btn_train_validate, 2, 3, 1, 2)
        layout.addWidget(self.btn_rules, 2, 5, 1, 3)
        
        # Linha 3: IA de Cotas (Modo 2 + Botões Verdes)
        layout.addWidget(self.btn_ai_m2, 3, 0)
        layout.addWidget(self.btn_smart_dimensions, 3, 1, 1, 2)
        layout.addWidget(self.btn_validate_dims_train, 3, 3, 1, 2)
        layout.addWidget(self.btn_rules_dims, 3, 5, 1, 3)
        
        # Linha 4: Espaço de Feedback
        layout.addWidget(self.feedback_container, 4, 0, 1, 8)
        layout.setRowStretch(4, 1)
        
        # Estilo Global
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {DS.DEEP};
            }}
            QPushButton {{
                background-color: {DS.BORDER};
                color: {DS.TEXT};
                border: 1px solid {DS.BORDER_STR};
                border-radius: 4px;
                padding: 2px 4px;
                font-weight: bold;
                font-size: 8px;
                text-align: center;
                max-height: 22px;
            }}
            QPushButton:hover {{
                background-color: {DS.BORDER_STR};
                border: 1px solid {DS.MUTED};
                color: {DS.WHITE};
            }}
            QPushButton:pressed {{
                background-color: {DS.DEEP};
                border: 1px solid {DS.INTERACTIVE};
            }}
            QPushButton:checked {{
                background-color: {DS.INTERACTIVE};
                color: white;
                border: 1px solid {DS.INTERACTIVE};
            }}
            #btn_undo {{ color: {DS.GOLD}; }}
        """)

    def setup_shortcuts(self):
        """Configurar atalhos de teclado"""
        # Tecla S: Selecionar
        self.shortcut_select = QShortcut(QKeySequence("S"), self)
        self.shortcut_select.activated.connect(self.on_select_clicked)
        
        # Tecla D: Fazer cota
        self.shortcut_dimension = QShortcut(QKeySequence("D"), self)
        self.shortcut_dimension.activated.connect(self.on_dimension_clicked)
        
        # Tecla M: Mover
        self.shortcut_move = QShortcut(QKeySequence("M"), self)
        self.shortcut_move.activated.connect(self.on_move_clicked)
        
        # Tecla O: Offset
        self.shortcut_offset = QShortcut(QKeySequence("O"), self)
        self.shortcut_offset.activated.connect(self.on_offset_clicked)
        
        # Tecla Del: Excluir
        self.shortcut_delete = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        self.shortcut_delete.activated.connect(self.on_delete_clicked)
        
        # Tecla J: Join
        self.shortcut_join = QShortcut(QKeySequence("J"), self)
        self.shortcut_join.activated.connect(self.on_join_clicked)
        
        # Ctrl+Z: Desfazer
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.on_undo_clicked)

        # Tecla F: Alternar Vínculo
        self.shortcut_toggle_link = QShortcut(QKeySequence("F"), self)
        self.shortcut_toggle_link.activated.connect(self.on_toggle_link_clicked)
    
    def on_select_clicked(self):
        """Ativa modo de seleção"""
        self.mode = 'select'
        self.update_button_states()
        self.select_mode_requested.emit()
    
    def on_dimension_clicked(self):
        """Ativa modo de fazer cota"""
        self.make_dimension_requested.emit()
    
    def on_move_clicked(self):
        """Ativa modo de mover"""
        self.move_requested.emit()
    
    def on_offset_clicked(self):
        """Ativa modo de offset"""
        self.offset_requested.emit()
    
    def on_delete_clicked(self):
        """Exclui linhas selecionadas"""
        self.delete_requested.emit()
    
    def on_join_clicked(self):
        """Faz join de linhas selecionadas"""
        self.join_requested.emit()
    
    def on_join_automatico_clicked(self):
        """Faz join automático de linhas segmentadas"""
        self.join_automatico_requested.emit()
    
    def on_undo_clicked(self):
        """Emite sinal quando botão Desfazer é clicado"""
        self.undo_requested.emit()
    
    def on_refazer_cotas_clicked(self):
        """Emite sinal quando botão Refazer Cotas é clicado"""
        self.refazer_cotas_requested.emit()
    
    def on_delete_all_dimensions_clicked(self):
        """Emite sinal quando botão Eliminar Todas as Cotas é clicado"""
        self.delete_all_dimensions_requested.emit()

    def on_toggle_link_clicked(self):
        """Emite sinal quando botão Alternar Vínculo é clicado"""
        self.toggle_link_requested.emit()

    def on_smart_interpret_clicked(self):
        """Emite sinal para interpretação inteligente"""
        self.smart_interpret_requested.emit()

    def on_smart_dimensions_clicked(self):
        """Emite sinal para ajuste inteligente de cotas"""
        self.smart_dimensions_requested.emit()

    def on_train_validate_clicked(self):
        """Emite sinal para validar treino"""
        self.train_validate_requested.emit()

    def on_validate_dimensions_training_clicked(self):
        """Emite sinal para validar treino de cotas"""
        self.validate_dimensions_training_requested.emit()

    def on_rules_clicked(self):
        """Emite sinal para abrir regras de interpretação de linhas"""
        self.rules_requested.emit()

    def on_rules_dimensions_clicked(self):
        """Emite sinal para abrir regras de interpretação de cotas"""
        self.rules_dimensions_requested.emit()
    
    def update_button_states(self):
        """Atualiza estados visuais dos botões"""
        # Resetar todos principais
        for btn in [self.btn_select, self.btn_move, self.btn_offset]:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {DS.ELEVATED};
                    color: {DS.WHITE};
                    border: 1px solid {DS.BORDER_STR};
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 8px;
                    max-height: 22px;
                }}
            """)
        
        # Destacar botão ativo
        if self.mode == 'select':
            self.btn_select.setStyleSheet(f"""
                QPushButton {{
                    background-color: {DS.INTERACTIVE};
                    color: {DS.WHITE};
                    border: 2px solid {DS.INTERACTIVE};
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 8px;
                    max-height: 22px;
                }}
            """)
        elif self.mode == 'move':
            self.btn_move.setStyleSheet(f"""
                QPushButton {{
                    background-color: {DS.INTERACTIVE};
                    color: {DS.WHITE};
                    border: 2px solid {DS.INTERACTIVE};
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 8px;
                    max-height: 22px;
                }}
            """)
        elif self.mode == 'offset':
            self.btn_offset.setStyleSheet(f"""
                QPushButton {{
                    background-color: {DS.INTERACTIVE};
                    color: {DS.WHITE};
                    border: 2px solid {DS.INTERACTIVE};
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 8px;
                    max-height: 22px;
                }}
            """)
    
    def setup_shortcuts(self):
        """Configurar atalhos de teclado"""
        # Tecla S: Selecionar
        self.shortcut_select = QShortcut(QKeySequence("S"), self)
        self.shortcut_select.activated.connect(self.on_select_clicked)
        
        # Tecla D: Fazer cota
        self.shortcut_dimension = QShortcut(QKeySequence("D"), self)
        self.shortcut_dimension.activated.connect(self.on_dimension_clicked)
        
        # Tecla M: Mover
        self.shortcut_move = QShortcut(QKeySequence("M"), self)
        self.shortcut_move.activated.connect(self.on_move_clicked)
        
        # Tecla O: Offset
        self.shortcut_offset = QShortcut(QKeySequence("O"), self)
        self.shortcut_offset.activated.connect(self.on_offset_clicked)
        
        # Tecla Del: Excluir
        self.shortcut_delete = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        self.shortcut_delete.activated.connect(self.on_delete_clicked)
        
        # Tecla J: Join
        self.shortcut_join = QShortcut(QKeySequence("J"), self)
        self.shortcut_join.activated.connect(self.on_join_clicked)
        
        # Ctrl+Z: Desfazer
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.on_undo_clicked)

        # Tecla F: Alternar Vínculo
        self.shortcut_toggle_link = QShortcut(QKeySequence("F"), self)
        self.shortcut_toggle_link.activated.connect(self.on_toggle_link_clicked)
    
    def on_select_clicked(self):
        """Ativa modo de seleção"""
        self.mode = 'select'
        self.update_button_states()
        self.select_mode_requested.emit()
    
    def on_dimension_clicked(self):
        """Ativa modo de fazer cota"""
        self.make_dimension_requested.emit()
    
    def on_move_clicked(self):
        """Ativa modo de mover"""
        self.move_requested.emit()
    
    def on_offset_clicked(self):
        """Ativa modo de offset"""
        self.offset_requested.emit()
    
    def on_delete_clicked(self):
        """Exclui linhas selecionadas"""
        self.delete_requested.emit()
    
    def on_join_clicked(self):
        """Faz join de linhas selecionadas"""
        self.join_requested.emit()
    
    def on_join_automatico_clicked(self):
        """Faz join automático de linhas segmentadas"""
        self.join_automatico_requested.emit()
    
    def on_undo_clicked(self):
        """Emite sinal quando botão Desfazer é clicado"""
        self.undo_requested.emit()
    
    def on_refazer_cotas_clicked(self):
        """Emite sinal quando botão Refazer Cotas é clicado"""
        self.refazer_cotas_requested.emit()
    
    def on_delete_all_dimensions_clicked(self):
        """Emite sinal quando botão Eliminar Todas as Cotas é clicado"""
        self.delete_all_dimensions_requested.emit()

    def on_toggle_link_clicked(self):
        """Emite sinal quando botão Alternar Vínculo é clicado"""
        self.toggle_link_requested.emit()

    def on_smart_interpret_clicked(self):
        """Emite sinal para interpretação inteligente"""
        self.smart_interpret_requested.emit()

    def on_smart_dimensions_clicked(self):
        """Emite sinal para ajuste inteligente de cotas"""
        self.smart_dimensions_requested.emit()

    def on_train_validate_clicked(self):
        """Emite sinal para validar treino"""
        self.train_validate_requested.emit()

    def on_validate_dimensions_training_clicked(self):
        """Emite sinal para validar treino de cotas"""
        self.validate_dimensions_training_requested.emit()

    def on_rules_clicked(self):
        """Emite sinal para abrir regras de interpretação de LINHAS"""
        self.rules_requested.emit()

    def on_rules_dimensions_clicked(self):
        """Emite sinal para abrir regras de interpretação de COTAS"""
        self.rules_dimensions_requested.emit()
    

    
    def update_button_states(self):
        """Atualiza estados visuais dos botões"""
        # Resetar todos
        for btn in [self.btn_select, self.btn_move, self.btn_offset]:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {DS.ELEVATED};
                    color: {DS.WHITE};
                    border: 1px solid {DS.BORDER_STR};
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 8px;
                    max-height: 22px;
                }}
            """)
        
        # Destacar botão ativo
        if self.mode == 'select':
            self.btn_select.setStyleSheet(f"""
                QPushButton {{
                    background-color: {DS.INTERACTIVE};
                    color: {DS.WHITE};
                    border: 2px solid {DS.INTERACTIVE};
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 8px;
                    max-height: 22px;
                }}
            """)
        elif self.mode == 'move':
            self.btn_move.setStyleSheet(f"""
                QPushButton {{
                    background-color: {DS.INTERACTIVE};
                    color: {DS.WHITE};
                    border: 2px solid {DS.INTERACTIVE};
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 8px;
                    max-height: 22px;
                }}
            """)
        elif self.mode == 'offset':
            self.btn_offset.setStyleSheet(f"""
                QPushButton {{
                    background-color: {DS.INTERACTIVE};
                    color: {DS.WHITE};
                    border: 2px solid {DS.INTERACTIVE};
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 8px;
                    max-height: 22px;
                }}
            """)

    def deactivate_select_mode(self):
        """Desativa modo de seleção (Enter)"""
        if self.mode == 'select':
            self.mode = None
            self.update_button_states()
    
    def set_move_widget(self, widget):
        """Define widget de mover"""
        self.move_widget = widget
    
    def set_offset_widget(self, widget):
        """Define widget de offset"""
        self.offset_widget = widget

    def get_selected_intelligence_mode(self) -> int:
        """Retorna o modo de inteligência selecionado (0=M1, 1=M2)"""
        return self.ai_mode_group.checkedId()


class MoveCommandWidget(QWidget):
    """Widget de comando para mover linhas"""
    move_requested = Signal(float, str)  # distância, direção ('up', 'down', 'left', 'right')
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_shortcuts()
    
    def setup_ui(self):
        """Configurar interface do painel refinada (UX/UI Harmony)"""
        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(3)
        
        btn_min_height = 24
        color_btn_height = 24
        
        # --- Instanciação dos Botões ---
        
        # Geometria
        self.btn_select = QPushButton("Sel (S)")
        self.btn_select.setMinimumHeight(btn_min_height)
        self.btn_select.clicked.connect(self.on_select_clicked)
        
        self.btn_move = QPushButton("Mov (M)")
        self.btn_move.setMinimumHeight(btn_min_height)
        self.btn_move.clicked.connect(self.on_move_clicked)
        
        self.btn_offset = QPushButton("Off (O)")
        self.btn_offset.setMinimumHeight(btn_min_height)
        self.btn_offset.clicked.connect(self.on_offset_clicked)
        
        self.btn_join = QPushButton("Join (J)")
        self.btn_join.setMinimumHeight(btn_min_height)
        self.btn_join.clicked.connect(self.on_join_clicked)
        
        self.btn_join_auto = QPushButton("Join Auto")
        self.btn_join_auto.setMinimumHeight(btn_min_height)
        self.btn_join_auto.clicked.connect(self.on_join_automatico_clicked)
        
        self.btn_delete = QPushButton("Excluir (Del)")
        self.btn_delete.setMinimumHeight(btn_min_height)
        self.btn_delete.clicked.connect(self.on_delete_clicked)
        
        self.btn_toggle_link = QPushButton("Vínculo (F)")
        self.btn_toggle_link.setMinimumHeight(btn_min_height)
        self.btn_toggle_link.clicked.connect(self.on_toggle_link_clicked)
        
        self.btn_undo = QPushButton("Voltar (Z)")
        self.btn_undo.setObjectName("btn_undo")
        self.btn_undo.setMinimumHeight(btn_min_height)
        self.btn_undo.clicked.connect(self.on_undo_clicked)
        
        # Cotas Manuais / Globais
        self.btn_dimension = QPushButton("Cota (D)")
        self.btn_dimension.setMinimumHeight(btn_min_height)
        self.btn_dimension.clicked.connect(self.on_dimension_clicked)
        
        self.btn_refazer_cotas = QPushButton("Cotas Auto")
        self.btn_refazer_cotas.setMinimumHeight(color_btn_height)
        self.btn_refazer_cotas.setStyleSheet(f"""
            QPushButton {{
                background-color: {DS.GOLD}; color: black;
                border: 1px solid {DS.WARNING}; border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px;
            }}
            QPushButton:hover {{ background-color: {DS.WARNING}; }}
        """)
        self.btn_refazer_cotas.clicked.connect(self.on_refazer_cotas_clicked)
        
        self.btn_delete_all_dims = QPushButton("Limpar Cotas")
        self.btn_delete_all_dims.setObjectName("btn_delete_all_dims")
        self.btn_delete_all_dims.setMinimumHeight(color_btn_height)
        self.btn_delete_all_dims.setStyleSheet(f"""
            QPushButton {{
                background-color: {DS.DANGER}; color: white;
                border: 1px solid {DS.DANGER}; border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px;
            }}
            QPushButton:hover {{ background-color: #e53935; }}
        """)
        self.btn_delete_all_dims.clicked.connect(self.on_delete_all_dimensions_clicked)
        
        # Inteligência Artificial - Modos
        self.ai_mode_group = QButtonGroup(self)
        self.ai_mode_group.setExclusive(True)
        
        modo_base_style = f"""
            QPushButton {{ background-color: {DS.BORDER}; color: {DS.TEXT}; border: 1px solid {DS.BORDER_STR};
                border-radius: 6px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px; }}
            QPushButton:hover {{ background-color: {DS.BORDER_STR}; }}
        """
        
        self.btn_ai_m1 = QPushButton("M1 (122×60)")
        self.btn_ai_m1.setToolTip("Modo 1: Geral/Verticais (122X60)")
        self.btn_ai_m1.setCheckable(True)
        self.btn_ai_m1.setChecked(True)
        self.btn_ai_m1.setMinimumHeight(color_btn_height)
        self.btn_ai_m1.setStyleSheet(modo_base_style + f"""
            QPushButton:checked {{ background-color: {DS.PURPLE}; color: white; border: 2px solid {DS.PURPLE}; }}
        """)
        self.ai_mode_group.addButton(self.btn_ai_m1, 0)
        
        self.btn_ai_m2 = QPushButton("M2 (122×20)")
        self.btn_ai_m2.setToolTip("Modo 2: Específico/Horizontais (122X20)")
        self.btn_ai_m2.setCheckable(True)
        self.btn_ai_m2.setMinimumHeight(color_btn_height)
        self.btn_ai_m2.setStyleSheet(modo_base_style + f"""
            QPushButton:checked {{ background-color: {DS.MAGENTA}; color: white; border: 2px solid {DS.MAGENTA}; }}
        """)
        self.ai_mode_group.addButton(self.btn_ai_m2, 1)
        
        # Inteligência Artificial - Linhas (Azul)
        style_linhas = f"""
            QPushButton {{ background-color: {DS.INTERACTIVE}; color: white; border: 1px solid {DS.INTERACTIVE};
                border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px; }}
            QPushButton:hover {{ background-color: #3b82f6; }}
        """
        self.btn_smart_interpret = QPushButton("IA Linhas")
        self.btn_smart_interpret.setMinimumHeight(color_btn_height)
        self.btn_smart_interpret.setStyleSheet(style_linhas)
        self.btn_smart_interpret.clicked.connect(self.on_smart_interpret_clicked)
        
        self.btn_train_validate = QPushButton("Val. Linhas")
        self.btn_train_validate.setMinimumHeight(color_btn_height)
        self.btn_train_validate.setStyleSheet(style_linhas)
        self.btn_train_validate.clicked.connect(self.on_train_validate_clicked)
        
        self.btn_rules = QPushButton("Regras Lin.")
        self.btn_rules.setMinimumHeight(color_btn_height)
        self.btn_rules.setStyleSheet(style_linhas)
        self.btn_rules.clicked.connect(self.on_rules_clicked)
        
        # Inteligência Artificial - Cotas (Verde)
        style_cotas = f"""
            QPushButton {{ background-color: {DS.SUCCESS}; color: white; border: 1px solid {DS.SUCCESS};
                border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px; }}
            QPushButton:hover {{ background-color: #22c55e; }}
        """
        self.btn_smart_dimensions = QPushButton("IA Cotas")
        self.btn_smart_dimensions.setMinimumHeight(color_btn_height)
        self.btn_smart_dimensions.setStyleSheet(style_cotas)
        self.btn_smart_dimensions.clicked.connect(self.on_smart_dimensions_clicked)
        
        self.btn_validate_dims_train = QPushButton("Val. Cotas")
        self.btn_validate_dims_train.setMinimumHeight(color_btn_height)
        self.btn_validate_dims_train.setStyleSheet(style_cotas)
        self.btn_validate_dims_train.clicked.connect(self.on_validate_dimensions_training_clicked)
        
        self.btn_rules_dims = QPushButton("Regras Cot.")
        self.btn_rules_dims.setMinimumHeight(color_btn_height)
        self.btn_rules_dims.setStyleSheet(style_cotas)
        self.btn_rules_dims.clicked.connect(self.on_rules_dimensions_clicked)
        
        # Feedback Container
        self.feedback_container = QWidget()
        self.feedback_layout = QVBoxLayout(self.feedback_container)
        self.feedback_layout.setContentsMargins(0, 0, 0, 0)
        self.feedback_layout.setSpacing(0)
        
        # --- Montagem do Grid Refinado ---
        
        # Linha 0: Ferramentas Básicas
        layout.addWidget(self.btn_select, 0, 0)
        layout.addWidget(self.btn_move, 0, 1)
        layout.addWidget(self.btn_offset, 0, 2)
        layout.addWidget(self.btn_join, 0, 3)
        layout.addWidget(self.btn_join_auto, 0, 4)
        layout.addWidget(self.btn_delete, 0, 5)
        layout.addWidget(self.btn_toggle_link, 0, 6)
        layout.addWidget(self.btn_undo, 0, 7)
        
        # Linha 1: Ferramentas de Cota
        layout.addWidget(self.btn_dimension, 1, 0)
        layout.addWidget(self.btn_refazer_cotas, 1, 1, 1, 3)
        layout.addWidget(self.btn_delete_all_dims, 1, 4, 1, 4)
        
        # Linha 2: IA de Linhas (Modo 1 + Botões Azuis)
        layout.addWidget(self.btn_ai_m1, 2, 0)
        layout.addWidget(self.btn_smart_interpret, 2, 1, 1, 2)
        layout.addWidget(self.btn_train_validate, 2, 3, 1, 2)
        layout.addWidget(self.btn_rules, 2, 5, 1, 3)
        
        # Linha 3: IA de Cotas (Modo 2 + Botões Verdes)
        layout.addWidget(self.btn_ai_m2, 3, 0)
        layout.addWidget(self.btn_smart_dimensions, 3, 1, 1, 2)
        layout.addWidget(self.btn_validate_dims_train, 3, 3, 1, 2)
        layout.addWidget(self.btn_rules_dims, 3, 5, 1, 3)
        
        # Linha 4: Espaço de Feedback
        layout.addWidget(self.feedback_container, 4, 0, 1, 8)
        layout.setRowStretch(4, 1)
        
        # Estilo Global
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {DS.DEEP};
            }}
            QPushButton {{
                background-color: {DS.BORDER};
                color: {DS.TEXT};
                border: 1px solid {DS.BORDER_STR};
                border-radius: 4px;
                padding: 2px 4px;
                font-weight: bold;
                font-size: 8px;
                text-align: center;
                max-height: 22px;
            }}
            QPushButton:hover {{
                background-color: {DS.BORDER_STR};
                border: 1px solid {DS.MUTED};
                color: {DS.WHITE};
            }}
            QPushButton:pressed {{
                background-color: {DS.DEEP};
                border: 1px solid {DS.INTERACTIVE};
            }}
            QPushButton:checked {{
                background-color: {DS.INTERACTIVE};
                color: white;
                border: 1px solid {DS.INTERACTIVE};
            }}
            #btn_undo {{ color: {DS.GOLD}; }}
        """)

    def setup_shortcuts(self):
        """Configurar atalhos de teclado para setas"""
        from PySide6.QtGui import QShortcut
        
        # Seta para cima
        self.shortcut_up = QShortcut(QKeySequence(Qt.Key.Key_Up), self)
        self.shortcut_up.activated.connect(lambda: self.on_arrow_clicked('up'))
        
        # Seta para baixo
        self.shortcut_down = QShortcut(QKeySequence(Qt.Key.Key_Down), self)
        self.shortcut_down.activated.connect(lambda: self.on_arrow_clicked('down'))
        
        # Seta para esquerda
        self.shortcut_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.shortcut_left.activated.connect(lambda: self.on_arrow_clicked('left'))
        
        # Seta para direita
        self.shortcut_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.shortcut_right.activated.connect(lambda: self.on_arrow_clicked('right'))
    
    def on_arrow_clicked(self, direction: str):
        """Chamado quando uma seta é clicada ou tecla pressionada"""
        try:
            distance = float(self.distance_input.text() or "0")
            if distance > 0:
                self.move_requested.emit(distance, direction)
        except ValueError:
            pass
    
    def get_distance(self) -> float:
        """Retorna distância digitada"""
        try:
            return float(self.distance_input.text() or "0")
        except ValueError:
            return 0.0


class OffsetCommandWidget(QWidget):
    """Widget de comando para offset (cópia) de linhas"""
    offset_requested = Signal(float, str)  # distância, direção
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_shortcuts()
    
    def setup_ui(self):
        """Configurar interface do painel refinada (UX/UI Harmony)"""
        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(3)
        
        btn_min_height = 24
        color_btn_height = 24
        
        # --- Instanciação dos Botões ---
        
        # Geometria
        self.btn_select = QPushButton("Sel (S)")
        self.btn_select.setMinimumHeight(btn_min_height)
        self.btn_select.clicked.connect(self.on_select_clicked)
        
        self.btn_move = QPushButton("Mov (M)")
        self.btn_move.setMinimumHeight(btn_min_height)
        self.btn_move.clicked.connect(self.on_move_clicked)
        
        self.btn_offset = QPushButton("Off (O)")
        self.btn_offset.setMinimumHeight(btn_min_height)
        self.btn_offset.clicked.connect(self.on_offset_clicked)
        
        self.btn_join = QPushButton("Join (J)")
        self.btn_join.setMinimumHeight(btn_min_height)
        self.btn_join.clicked.connect(self.on_join_clicked)
        
        self.btn_join_auto = QPushButton("Join Auto")
        self.btn_join_auto.setMinimumHeight(btn_min_height)
        self.btn_join_auto.clicked.connect(self.on_join_automatico_clicked)
        
        self.btn_delete = QPushButton("Excluir (Del)")
        self.btn_delete.setMinimumHeight(btn_min_height)
        self.btn_delete.clicked.connect(self.on_delete_clicked)
        
        self.btn_toggle_link = QPushButton("Vínculo (F)")
        self.btn_toggle_link.setMinimumHeight(btn_min_height)
        self.btn_toggle_link.clicked.connect(self.on_toggle_link_clicked)
        
        self.btn_undo = QPushButton("Voltar (Z)")
        self.btn_undo.setObjectName("btn_undo")
        self.btn_undo.setMinimumHeight(btn_min_height)
        self.btn_undo.clicked.connect(self.on_undo_clicked)
        
        # Cotas Manuais / Globais
        self.btn_dimension = QPushButton("Cota (D)")
        self.btn_dimension.setMinimumHeight(btn_min_height)
        self.btn_dimension.clicked.connect(self.on_dimension_clicked)
        
        self.btn_refazer_cotas = QPushButton("Cotas Auto")
        self.btn_refazer_cotas.setMinimumHeight(color_btn_height)
        self.btn_refazer_cotas.setStyleSheet(f"""
            QPushButton {{
                background-color: {DS.GOLD}; color: black;
                border: 1px solid {DS.WARNING}; border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px;
            }}
            QPushButton:hover {{ background-color: {DS.WARNING}; }}
        """)
        self.btn_refazer_cotas.clicked.connect(self.on_refazer_cotas_clicked)
        
        self.btn_delete_all_dims = QPushButton("Limpar Cotas")
        self.btn_delete_all_dims.setObjectName("btn_delete_all_dims")
        self.btn_delete_all_dims.setMinimumHeight(color_btn_height)
        self.btn_delete_all_dims.setStyleSheet(f"""
            QPushButton {{
                background-color: {DS.DANGER}; color: white;
                border: 1px solid {DS.DANGER}; border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px;
            }}
            QPushButton:hover {{ background-color: #e53935; }}
        """)
        self.btn_delete_all_dims.clicked.connect(self.on_delete_all_dimensions_clicked)
        
        # Inteligência Artificial - Modos
        self.ai_mode_group = QButtonGroup(self)
        self.ai_mode_group.setExclusive(True)
        
        modo_base_style = f"""
            QPushButton {{ background-color: {DS.BORDER}; color: {DS.TEXT}; border: 1px solid {DS.BORDER_STR};
                border-radius: 6px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px; }}
            QPushButton:hover {{ background-color: {DS.BORDER_STR}; }}
        """
        
        self.btn_ai_m1 = QPushButton("M1 (122×60)")
        self.btn_ai_m1.setToolTip("Modo 1: Geral/Verticais (122X60)")
        self.btn_ai_m1.setCheckable(True)
        self.btn_ai_m1.setChecked(True)
        self.btn_ai_m1.setMinimumHeight(color_btn_height)
        self.btn_ai_m1.setStyleSheet(modo_base_style + f"""
            QPushButton:checked {{ background-color: {DS.PURPLE}; color: white; border: 2px solid {DS.PURPLE}; }}
        """)
        self.ai_mode_group.addButton(self.btn_ai_m1, 0)
        
        self.btn_ai_m2 = QPushButton("M2 (122×20)")
        self.btn_ai_m2.setToolTip("Modo 2: Específico/Horizontais (122X20)")
        self.btn_ai_m2.setCheckable(True)
        self.btn_ai_m2.setMinimumHeight(color_btn_height)
        self.btn_ai_m2.setStyleSheet(modo_base_style + f"""
            QPushButton:checked {{ background-color: {DS.MAGENTA}; color: white; border: 2px solid {DS.MAGENTA}; }}
        """)
        self.ai_mode_group.addButton(self.btn_ai_m2, 1)
        
        # Inteligência Artificial - Linhas (Azul)
        style_linhas = f"""
            QPushButton {{ background-color: {DS.INTERACTIVE}; color: white; border: 1px solid {DS.INTERACTIVE};
                border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px; }}
            QPushButton:hover {{ background-color: #3b82f6; }}
        """
        self.btn_smart_interpret = QPushButton("IA Linhas")
        self.btn_smart_interpret.setMinimumHeight(color_btn_height)
        self.btn_smart_interpret.setStyleSheet(style_linhas)
        self.btn_smart_interpret.clicked.connect(self.on_smart_interpret_clicked)
        
        self.btn_train_validate = QPushButton("Val. Linhas")
        self.btn_train_validate.setMinimumHeight(color_btn_height)
        self.btn_train_validate.setStyleSheet(style_linhas)
        self.btn_train_validate.clicked.connect(self.on_train_validate_clicked)
        
        self.btn_rules = QPushButton("Regras Lin.")
        self.btn_rules.setMinimumHeight(color_btn_height)
        self.btn_rules.setStyleSheet(style_linhas)
        self.btn_rules.clicked.connect(self.on_rules_clicked)
        
        # Inteligência Artificial - Cotas (Verde)
        style_cotas = f"""
            QPushButton {{ background-color: {DS.SUCCESS}; color: white; border: 1px solid {DS.SUCCESS};
                border-radius: 4px; padding: 2px 4px; font-weight: bold; font-size: 8px; max-height: 22px; }}
            QPushButton:hover {{ background-color: #22c55e; }}
        """
        self.btn_smart_dimensions = QPushButton("IA Cotas")
        self.btn_smart_dimensions.setMinimumHeight(color_btn_height)
        self.btn_smart_dimensions.setStyleSheet(style_cotas)
        self.btn_smart_dimensions.clicked.connect(self.on_smart_dimensions_clicked)
        
        self.btn_validate_dims_train = QPushButton("Val. Cotas")
        self.btn_validate_dims_train.setMinimumHeight(color_btn_height)
        self.btn_validate_dims_train.setStyleSheet(style_cotas)
        self.btn_validate_dims_train.clicked.connect(self.on_validate_dimensions_training_clicked)
        
        self.btn_rules_dims = QPushButton("Regras Cot.")
        self.btn_rules_dims.setMinimumHeight(color_btn_height)
        self.btn_rules_dims.setStyleSheet(style_cotas)
        self.btn_rules_dims.clicked.connect(self.on_rules_dimensions_clicked)
        
        # Feedback Container
        self.feedback_container = QWidget()
        self.feedback_layout = QVBoxLayout(self.feedback_container)
        self.feedback_layout.setContentsMargins(0, 0, 0, 0)
        self.feedback_layout.setSpacing(0)
        
        # --- Montagem do Grid Refinado ---
        
        # Linha 0: Ferramentas Básicas
        layout.addWidget(self.btn_select, 0, 0)
        layout.addWidget(self.btn_move, 0, 1)
        layout.addWidget(self.btn_offset, 0, 2)
        layout.addWidget(self.btn_join, 0, 3)
        layout.addWidget(self.btn_join_auto, 0, 4)
        layout.addWidget(self.btn_delete, 0, 5)
        layout.addWidget(self.btn_toggle_link, 0, 6)
        layout.addWidget(self.btn_undo, 0, 7)
        
        # Linha 1: Ferramentas de Cota
        layout.addWidget(self.btn_dimension, 1, 0)
        layout.addWidget(self.btn_refazer_cotas, 1, 1, 1, 3)
        layout.addWidget(self.btn_delete_all_dims, 1, 4, 1, 4)
        
        # Linha 2: IA de Linhas (Modo 1 + Botões Azuis)
        layout.addWidget(self.btn_ai_m1, 2, 0)
        layout.addWidget(self.btn_smart_interpret, 2, 1, 1, 2)
        layout.addWidget(self.btn_train_validate, 2, 3, 1, 2)
        layout.addWidget(self.btn_rules, 2, 5, 1, 3)
        
        # Linha 3: IA de Cotas (Modo 2 + Botões Verdes)
        layout.addWidget(self.btn_ai_m2, 3, 0)
        layout.addWidget(self.btn_smart_dimensions, 3, 1, 1, 2)
        layout.addWidget(self.btn_validate_dims_train, 3, 3, 1, 2)
        layout.addWidget(self.btn_rules_dims, 3, 5, 1, 3)
        
        # Linha 4: Espaço de Feedback
        layout.addWidget(self.feedback_container, 4, 0, 1, 8)
        layout.setRowStretch(4, 1)
        
        # Estilo Global
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {DS.DEEP};
            }}
            QPushButton {{
                background-color: {DS.BORDER};
                color: {DS.TEXT};
                border: 1px solid {DS.BORDER_STR};
                border-radius: 4px;
                padding: 2px 4px;
                font-weight: bold;
                font-size: 8px;
                text-align: center;
                max-height: 22px;
            }}
            QPushButton:hover {{
                background-color: {DS.BORDER_STR};
                border: 1px solid {DS.MUTED};
                color: {DS.WHITE};
            }}
            QPushButton:pressed {{
                background-color: {DS.DEEP};
                border: 1px solid {DS.INTERACTIVE};
            }}
            QPushButton:checked {{
                background-color: {DS.INTERACTIVE};
                color: white;
                border: 1px solid {DS.INTERACTIVE};
            }}
            #btn_undo {{ color: {DS.GOLD}; }}
        """)

    def setup_shortcuts(self):
        """Configurar atalhos de teclado para setas"""
        from PySide6.QtGui import QShortcut

        # Seta para cima
        self.shortcut_up = QShortcut(QKeySequence(Qt.Key.Key_Up), self)
        self.shortcut_up.activated.connect(lambda: self.on_arrow_clicked('up'))
        
        # Seta para baixo
        self.shortcut_down = QShortcut(QKeySequence(Qt.Key.Key_Down), self)
        self.shortcut_down.activated.connect(lambda: self.on_arrow_clicked('down'))
        
        # Seta para esquerda
        self.shortcut_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.shortcut_left.activated.connect(lambda: self.on_arrow_clicked('left'))
        
        # Seta para direita
        self.shortcut_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.shortcut_right.activated.connect(lambda: self.on_arrow_clicked('right'))
    
    def on_arrow_clicked(self, direction: str):
        """Chamado quando uma seta é clicada ou tecla pressionada"""
        try:
            distance = float(self.distance_input.text() or "0")
            if distance > 0:
                self.offset_requested.emit(distance, direction)
        except ValueError:
            pass
    
    def get_distance(self) -> float:
        """Retorna distância digitada"""
        try:
            return float(self.distance_input.text() or "0")
        except ValueError:
            return 0.0


