def setup_ui(self):
        """Configurar interface do painel"""
        layout = QGridLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)
        
        self._grid_row = 0
        self._grid_col = 0
        self._max_cols = 8
        def add_to_grid(w):
            layout.addWidget(w, self._grid_row, self._grid_col)
            self._grid_col += 1
            if self._grid_col >= self._max_cols:
                self._grid_col = 0
                self._grid_row += 1
        
        # Botões Principais (Cinzas e Compactos)
        btn_min_height = 32
        
        # Botão 1: Selecionar
        self.btn_select = QPushButton("Selecionar\n(S)")
        self.btn_select.setMinimumHeight(btn_min_height)
        self.btn_select.clicked.connect(self.on_select_clicked)
        add_to_grid(self.btn_select)
        
        # Botão 2: Fazer cota
        self.btn_dimension = QPushButton("Fazer cota\n(D)")
        self.btn_dimension.setMinimumHeight(btn_min_height)
        self.btn_dimension.clicked.connect(self.on_dimension_clicked)
        add_to_grid(self.btn_dimension)
        
        # Botão 11: Alternar Cor do Vínculo (Movido para cá e agora cinza)
        self.btn_toggle_link = QPushButton("Vínculo (F)")
        self.btn_toggle_link.setMinimumHeight(btn_min_height)
        self.btn_toggle_link.clicked.connect(self.on_toggle_link_clicked)
        add_to_grid(self.btn_toggle_link)
        
        # Botão 3: Mover
        self.btn_move = QPushButton("Mover\n(M)")
        self.btn_move.setMinimumHeight(btn_min_height)
        self.btn_move.clicked.connect(self.on_move_clicked)
        add_to_grid(self.btn_move)
        
        # Botão 4: Offset
        self.btn_offset = QPushButton("Offset\n(O)")
        self.btn_offset.setMinimumHeight(btn_min_height)
        self.btn_offset.clicked.connect(self.on_offset_clicked)
        add_to_grid(self.btn_offset)
        
        # Botão 5: Excluir Linha
        self.btn_delete = QPushButton("Excluir (Del)")
        self.btn_delete.setMinimumHeight(btn_min_height)
        self.btn_delete.clicked.connect(self.on_delete_clicked)
        add_to_grid(self.btn_delete)
        
        # Botão 6: Join / Join Auto (Compactado em um container se necessário, mas manter individual por enquanto)
        self.btn_join = QPushButton("Join (J)")
        self.btn_join.setMinimumHeight(btn_min_height)
        self.btn_join.clicked.connect(self.on_join_clicked)
        add_to_grid(self.btn_join)
        
        self.btn_join_auto = QPushButton("Join Auto")
        self.btn_join_auto.setMinimumHeight(btn_min_height)
        self.btn_join_auto.clicked.connect(self.on_join_automatico_clicked)
        add_to_grid(self.btn_join_auto)
        
        # Botão 8: Desfazer
        self.btn_undo = QPushButton("Voltar (Z)")
        self.btn_undo.setObjectName("btn_undo")
        self.btn_undo.setMinimumHeight(btn_min_height)
        self.btn_undo.clicked.connect(self.on_undo_clicked)
        add_to_grid(self.btn_undo)
        
        #--- Botões Coloridos (Mantendo min_height original ou levemente menor) ---
        color_btn_height = 36
        
        # Ajustar Cotas Rosas
        # Cotas Automáticas Semi-Inteligentes (Laranja Claro)
        self.btn_refazer_cotas = QPushButton("Cotas Automaticas\nSemi-Inteligentes")
        self.btn_refazer_cotas.setMinimumHeight(color_btn_height)
        self.btn_refazer_cotas.setStyleSheet("""
            QPushButton {
                background-color: {DS.GOLD}; /* Laranja Claro */
                color: black;
                border: 1px solid {DS.WARNING};
                border-radius: 4px;
                padding: 4px;
                font-weight: bold;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: {DS.WARNING};
            }
        """)
        self.btn_refazer_cotas.clicked.connect(self.on_refazer_cotas_clicked)
        add_to_grid(self.btn_refazer_cotas)
        
        # Eliminar Todas as Cotas
        # Eliminar Todas as Cotas (Vermelho Claro)
        self.btn_delete_all_dims = QPushButton("Limpar Todas\nas Cotas")
        self.btn_delete_all_dims.setObjectName("btn_delete_all_dims")
        self.btn_delete_all_dims.setMinimumHeight(color_btn_height)
        self.btn_delete_all_dims.setStyleSheet("""
            QPushButton {
                background-color: {DS.DANGER}; /* Vermelho Claro */
                color: black;
                border: 1px solid {DS.DANGER};
                border-radius: 4px;
                padding: 4px;
                font-weight: bold;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: {DS.DANGER};
            }
        """)
        self.btn_delete_all_dims.clicked.connect(self.on_delete_all_dimensions_clicked)
        add_to_grid(self.btn_delete_all_dims)
        
        #--- Modos de Inteligência (MODO 1 e MODO 2) ---
        self.ai_mode_group = QButtonGroup(self)
        self.ai_mode_group.setExclusive(True)
        
        modes_container = QWidget()
        modes_layout = QVBoxLayout(modes_container)
        modes_layout.setContentsMargins(0, 5, 0, 5)
        modes_layout.setSpacing(4)
        
        self.btn_ai_m1 = QPushButton("MODO 1\n(122X60)")
        self.btn_ai_m1.setToolTip("Modo 1: Geral/Verticais (122X60)")
        self.btn_ai_m1.setCheckable(True)
        self.btn_ai_m1.setChecked(True)
        self.btn_ai_m1.setMinimumHeight(45)
        self.btn_ai_m1.setStyleSheet("""
            QPushButton {
                background-color: {DS.BORDER};
                color: {DS.TEXT};
                border: 1px solid {DS.BORDER_STR};
                border-radius: 22px;
                padding: 4px;
                font-weight: bold;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: {DS.BORDER_STR};
            }
            QPushButton:checked {
                background-color: {DS.PURPLE}; /* Roxo */
                color: white;
                border: 2px solid {DS.PURPLE};
            }
        """)
        self.ai_mode_group.addButton(self.btn_ai_m1, 0)
        modes_layout.addWidget(self.btn_ai_m1)
        
        self.btn_ai_m2 = QPushButton("MODO 2\n(122X20)") 
        self.btn_ai_m2.setToolTip("Modo 2: Específico/Horizontais (122X20)")
        self.btn_ai_m2.setCheckable(True)
        self.btn_ai_m2.setMinimumHeight(45)
        self.btn_ai_m2.setStyleSheet("""
            QPushButton {
                background-color: {DS.BORDER};
                color: {DS.TEXT};
                border: 1px solid {DS.BORDER_STR};
                border-radius: 22px;
                padding: 4px;
                font-weight: bold;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: {DS.BORDER_STR};
            }
            QPushButton:checked {
                background-color: {DS.MAGENTA}; /* Magenta */
                color: white;
                border: 2px solid {DS.MAGENTA};
            }
        """)
        self.ai_mode_group.addButton(self.btn_ai_m2, 1)
        modes_layout.addWidget(self.btn_ai_m2)
        
        add_to_grid(modes_container)

        #--- Botões de Execução IA (Abaixo dos Modos) ---
        # Estilo para botões de LINHAS (AZUL)
        style_linhas = f"""
            QPushButton {{
                background-color: {DS.INTERACTIVE};
                color: white;
                border: 1px solid {DS.INTERACTIVE};
                border-radius: 4px;
                padding: 4px;
                font-weight: bold;
                font-size: 9px;
            }}
            QPushButton:hover {{
                background-color: {DS.INTERACTIVE};
            }}
        """
        
        # Estilo para botões de COTAS (VERDE)
        style_cotas = f"""
            QPushButton {{
                background-color: {DS.SUCCESS};
                color: white;
                border: 1px solid {DS.SUCCESS};
                border-radius: 4px;
                padding: 4px;
                font-weight: bold;
                font-size: 9px;
            }}
            QPushButton:hover {{
                background-color: {DS.SUCCESS};
            }}
        """

        # IA Linhas
        self.btn_smart_interpret = QPushButton("IA Linhas")
        self.btn_smart_interpret.setMinimumHeight(color_btn_height)
        self.btn_smart_interpret.setStyleSheet(style_linhas)
        self.btn_smart_interpret.clicked.connect(self.on_smart_interpret_clicked)
        add_to_grid(self.btn_smart_interpret)

        # Validar Treino Linhas
        self.btn_train_validate = QPushButton("Validar Treino\nLinhas")
        self.btn_train_validate.setMinimumHeight(color_btn_height)
        self.btn_train_validate.setStyleSheet(style_linhas)
        self.btn_train_validate.clicked.connect(self.on_train_validate_clicked)
        add_to_grid(self.btn_train_validate)
        
        # Regras de Interpretação Linhas
        self.btn_rules = QPushButton("Regras de\nInterpretação Linhas")
        self.btn_rules.setMinimumHeight(color_btn_height)
        self.btn_rules.setStyleSheet(style_linhas)
        self.btn_rules.clicked.connect(self.on_rules_clicked)
        add_to_grid(self.btn_rules)
        
        # IA Cotas
        self.btn_smart_dimensions = QPushButton("IA Cotas")
        self.btn_smart_dimensions.setMinimumHeight(color_btn_height)
        self.btn_smart_dimensions.setStyleSheet(style_cotas)
        self.btn_smart_dimensions.clicked.connect(self.on_smart_dimensions_clicked)
        add_to_grid(self.btn_smart_dimensions)
 
        # Validar Treino Cotas
        self.btn_validate_dims_train = QPushButton("Validar Treino\nCotas")
        self.btn_validate_dims_train.setMinimumHeight(color_btn_height)
        self.btn_validate_dims_train.setStyleSheet(style_cotas)
        self.btn_validate_dims_train.clicked.connect(self.on_validate_dimensions_training_clicked)
        add_to_grid(self.btn_validate_dims_train)
 
        # Regras de Interpretação Cotas
        self.btn_rules_dims = QPushButton("Regras de\nInterpretação Cotas")
        self.btn_rules_dims.setMinimumHeight(color_btn_height)
        self.btn_rules_dims.setStyleSheet(style_cotas)
        self.btn_rules_dims.clicked.connect(self.on_rules_dimensions_clicked)
        add_to_grid(self.btn_rules_dims)
        
        
        # Placeholder para Widget de Feedback (inicialmente invisível)
        self.feedback_container = QWidget()
        self.feedback_layout = QVBoxLayout(self.feedback_container)
        self.feedback_layout.setContentsMargins(0, 0, 0, 0)
        self.feedback_layout.setSpacing(0)
        add_to_grid(self.feedback_container)
        layout.setRowStretch(self._grid_row, 1)
        
        # Estilo Global (Cinzas e Premium)
        self.setStyleSheet("""
            QWidget { 
                background-color: {DS.DEEP};
            }
            QPushButton {
                background-color: {DS.BORDER};
                color: {DS.TEXT};
                border: 1px solid {DS.BORDER_STR};
                border-radius: 4px;
                padding: 4px;
                font-weight: bold;
                font-size: 9px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: {DS.BORDER_STR};
                border: 1px solid {DS.MUTED};
                color: {DS.WHITE};
            }
            QPushButton:pressed {
                background-color: {DS.DEEP};
                border: 1px solid {DS.INTERACTIVE};
            }
            QPushButton:checked {
                background-color: {DS.INTERACTIVE};
                color: white;
                border: 1px solid {DS.INTERACTIVE};
            }
            #btn_undo { color: {DS.GOLD}; }
        """)
    
