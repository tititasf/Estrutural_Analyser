import re

def main():
    path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\_ROBOS_ABAS\Robo_Lajes\laje_src\ui\widgets\edition_toolbar.py'
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    replacement = '''    def setup_ui(self):
        """Configurar interface do painel refinada (UX/UI Harmony)"""
        layout = QGridLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        
        btn_min_height = 36
        color_btn_height = 36
        
        # --- Instanciação dos Botões ---
        
        # Geometria
        self.btn_select = QPushButton("Selecionar\\n(S)")
        self.btn_select.setMinimumHeight(btn_min_height)
        self.btn_select.clicked.connect(self.on_select_clicked)
        
        self.btn_move = QPushButton("Mover\\n(M)")
        self.btn_move.setMinimumHeight(btn_min_height)
        self.btn_move.clicked.connect(self.on_move_clicked)
        
        self.btn_offset = QPushButton("Offset\\n(O)")
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
        self.btn_dimension = QPushButton("Fazer cota\\n(D)")
        self.btn_dimension.setMinimumHeight(btn_min_height)
        self.btn_dimension.clicked.connect(self.on_dimension_clicked)
        
        self.btn_refazer_cotas = QPushButton("Cotas Automáticas\\nSemi-Inteligentes")
        self.btn_refazer_cotas.setMinimumHeight(color_btn_height)
        self.btn_refazer_cotas.setStyleSheet("""
            QPushButton {
                background-color: {DS.GOLD}; color: black;
                border: 1px solid {DS.WARNING}; border-radius: 4px; padding: 4px; font-weight: bold; font-size: 9px;
            }
            QPushButton:hover { background-color: {DS.WARNING}; }
        """)
        self.btn_refazer_cotas.clicked.connect(self.on_refazer_cotas_clicked)
        
        self.btn_delete_all_dims = QPushButton("Limpar Todas\\nas Cotas")
        self.btn_delete_all_dims.setObjectName("btn_delete_all_dims")
        self.btn_delete_all_dims.setMinimumHeight(color_btn_height)
        self.btn_delete_all_dims.setStyleSheet("""
            QPushButton {
                background-color: {DS.DANGER}; color: black;
                border: 1px solid {DS.DANGER}; border-radius: 4px; padding: 4px; font-weight: bold; font-size: 9px;
            }
            QPushButton:hover { background-color: {DS.DANGER}; }
        """)
        self.btn_delete_all_dims.clicked.connect(self.on_delete_all_dimensions_clicked)
        
        # Inteligência Artificial - Modos
        self.ai_mode_group = QButtonGroup(self)
        self.ai_mode_group.setExclusive(True)
        
        modo_base_style = """
            QPushButton { background-color: {DS.BORDER}; color: {DS.TEXT}; border: 1px solid {DS.BORDER_STR};
                border-radius: 6px; padding: 4px; font-weight: bold; font-size: 9px; }
            QPushButton:hover { background-color: {DS.BORDER_STR}; }
        """
        
        self.btn_ai_m1 = QPushButton("MODO 1\\n(122X60)")
        self.btn_ai_m1.setToolTip("Modo 1: Geral/Verticais (122X60)")
        self.btn_ai_m1.setCheckable(True)
        self.btn_ai_m1.setChecked(True)
        self.btn_ai_m1.setMinimumHeight(color_btn_height)
        self.btn_ai_m1.setStyleSheet(modo_base_style + """
            QPushButton:checked { background-color: {DS.PURPLE}; color: white; border: 2px solid {DS.PURPLE}; }
        """)
        self.ai_mode_group.addButton(self.btn_ai_m1, 0)
        
        self.btn_ai_m2 = QPushButton("MODO 2\\n(122X20)") 
        self.btn_ai_m2.setToolTip("Modo 2: Específico/Horizontais (122X20)")
        self.btn_ai_m2.setCheckable(True)
        self.btn_ai_m2.setMinimumHeight(color_btn_height)
        self.btn_ai_m2.setStyleSheet(modo_base_style + """
            QPushButton:checked { background-color: {DS.MAGENTA}; color: white; border: 2px solid {DS.MAGENTA}; }
        """)
        self.ai_mode_group.addButton(self.btn_ai_m2, 1)
        
        # Inteligência Artificial - Linhas (Azul)
        style_linhas = """
            QPushButton { background-color: {DS.INTERACTIVE}; color: white; border: 1px solid {DS.INTERACTIVE};
                border-radius: 4px; padding: 4px; font-weight: bold; font-size: 9px; }
            QPushButton:hover { background-color: #3b82f6; }
        """
        self.btn_smart_interpret = QPushButton("IA Linhas")
        self.btn_smart_interpret.setMinimumHeight(color_btn_height)
        self.btn_smart_interpret.setStyleSheet(style_linhas)
        self.btn_smart_interpret.clicked.connect(self.on_smart_interpret_clicked)
        
        self.btn_train_validate = QPushButton("Validar Treino\\nLinhas")
        self.btn_train_validate.setMinimumHeight(color_btn_height)
        self.btn_train_validate.setStyleSheet(style_linhas)
        self.btn_train_validate.clicked.connect(self.on_train_validate_clicked)
        
        self.btn_rules = QPushButton("Regras de\\nInterpretação Linhas")
        self.btn_rules.setMinimumHeight(color_btn_height)
        self.btn_rules.setStyleSheet(style_linhas)
        self.btn_rules.clicked.connect(self.on_rules_clicked)
        
        # Inteligência Artificial - Cotas (Verde)
        style_cotas = """
            QPushButton { background-color: {DS.SUCCESS}; color: white; border: 1px solid {DS.SUCCESS};
                border-radius: 4px; padding: 4px; font-weight: bold; font-size: 9px; }
            QPushButton:hover { background-color: #22c55e; }
        """
        self.btn_smart_dimensions = QPushButton("IA Cotas")
        self.btn_smart_dimensions.setMinimumHeight(color_btn_height)
        self.btn_smart_dimensions.setStyleSheet(style_cotas)
        self.btn_smart_dimensions.clicked.connect(self.on_smart_dimensions_clicked)
        
        self.btn_validate_dims_train = QPushButton("Validar Treino\\nCotas")
        self.btn_validate_dims_train.setMinimumHeight(color_btn_height)
        self.btn_validate_dims_train.setStyleSheet(style_cotas)
        self.btn_validate_dims_train.clicked.connect(self.on_validate_dimensions_training_clicked)
        
        self.btn_rules_dims = QPushButton("Regras de\\nInterpretação Cotas")
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
        layout.addWidget(self.btn_delete_all_dims, 1, 4, 1, 3)
        
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
        """)'''

    text = re.sub(r'    def setup_ui\(self\):.*?    def setup_shortcuts', replacement + '\n\n    def setup_shortcuts', text, flags=re.DOTALL)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

if __name__ == '__main__':
    main()
