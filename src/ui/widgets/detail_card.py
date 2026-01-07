from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                                QTabWidget, QTableWidget, QTableWidgetItem, 
                                QPushButton, QHeaderView, QFrame, QMessageBox,
                                QLineEdit, QFormLayout, QScrollArea, QComboBox, QGroupBox, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from .link_manager import LinkManager

class DetailCard(QWidget):
    """
    Ficha Técnica Master - Interface Especialista e Rotulagem de IA.
    Configurada para Pilares (Lados A-H), Vigas (Segmentos A/B) e Lajes.
    """
    data_validated = Signal(dict)
    data_invalidated = Signal(dict)
    element_focused = Signal(object) # (str para nome ou dict para link direto)
    pick_requested = Signal(str, str) # (field_id, type)
    focus_requested = Signal(str)    # (field_id) disparado pelo botão de lupa
    research_requested = Signal(str, str) # field_id, slot_id
    training_requested = Signal(str, dict) # field_id, train_data
    config_updated = Signal(str, list)      # field_key, slots_config
    
    # Estilos CSS Reutilizáveis
    STYLE_DEFAULT = "background: #252525; border: 1px solid #444; padding: 1px 4px; border-radius: 3px; color: #eee; font-size: 10px;"
    STYLE_VALID = "background: #252525; border: 1px solid #00cc66; padding: 1px 4px; border-radius: 3px; color: #eee; font-size: 10px; font-weight: bold;"

    def __init__(self, item_data: dict, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.fields = {} 
        self.indicators = {} 
        self.init_ui()

    def _add_linked_row(self, layout, label_text, field_id, pick_type='text', is_combo=False, combo_items=None, 
                        show_links=True, show_focus=True, hide_input=False):
        
        w = None
        btn_links = None
        btn_focus = None
        if not hide_input:
            if is_combo:
                w = QComboBox()
                if combo_items: w.addItems(combo_items)
                w.setFixedHeight(22)
                w.setMinimumWidth(20)
                w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                if "Pos." in label_text: # Lógica especial para posição da laje
                    w.currentTextChanged.connect(lambda t: self._on_position_changed(field_id, t))
            else:
                w = QLineEdit()
                w.setFixedHeight(22)
                w.setMinimumWidth(20)
                w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                
            w.setStyleSheet(self.STYLE_DEFAULT if field_id not in self.item_data.get('validated_fields', []) else self.STYLE_VALID)
            self.fields[field_id] = w
            
            # Tentar carregar valor inicial
            initial_val = self._get_initial_value(field_id)
            if initial_val is not None:
                if is_combo: w.setCurrentText(str(initial_val))
                else: w.setText(str(initial_val))
        else:
            # Placeholder invisível ou label para campos sem input de texto (como apenas segmentos)
            w = QLabel("Vínculo Pendente")
            w.setStyleSheet("color: #666; font-style: italic; font-size: 10px;")
            self.fields[field_id] = w
            
            # Se já tiver vínculos, mostrar contagem
            links = self.item_data.get('links', {}).get(field_id, {})
            count = 0
            if isinstance(links, dict):
                for sl_links in links.values(): count += len(sl_links)
            elif isinstance(links, list):
                count = len(links)
                
            if count > 0:
                w.setText(f"{count} Vínculo(s) Ok")
                w.setStyleSheet("color: #00cc66; font-weight: bold; font-size: 10px;")

        if show_links:
            btn_links = QPushButton("🔗")
            btn_links.setFixedSize(24, 20) # Menor ainda
            btn_links.setProperty("class", "FieldBtn")
            btn_links.setStyleSheet("font-size: 10px; padding: 0px;")
            btn_links.setCursor(Qt.PointingHandCursor)
            btn_links.setToolTip("Gerenciar Vínculos e Classes de IA")
            btn_links.clicked.connect(lambda checked=False, f_id=field_id, p_type=pick_type: self.open_link_manager(f_id, p_type))

        if show_focus:
            btn_focus = QPushButton("🔍")
            btn_focus.setFixedSize(24, 20) # Menor ainda
            btn_focus.setProperty("class", "FieldBtn")
            btn_focus.setStyleSheet("font-size: 10px; padding: 0px;")
            btn_focus.setCursor(Qt.PointingHandCursor)
            btn_focus.setToolTip("Localizar objeto no CAD")
            btn_focus.clicked.connect(lambda checked=False, f_id=field_id: self.focus_requested.emit(f_id))
        
        # --- LAYOUT HORIZONTAL ÚNICO ---
        # Garante que tudo fique em UMA linha só
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)

        # 1. Label (Largura um pouco maior e wrap)
        # label_text_clean = label_text.replace(":", "") 
        # (Removendo a limpeza agressiva de texto para manter o sentido, se desejado)
        
        lbl = QLabel(label_text)
        lbl.setFixedWidth(65) # Aumentado de 35 para 65
        lbl.setWordWrap(True) # Permitir quebra de linha
        lbl.setStyleSheet("font-size: 9px; color: #ccc; font-weight: bold;")
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_layout.addWidget(lbl)

        # 2. Input Field (Flexível, stretch=1)
        # O input vai ocupar todo o espaço que sobrar entre o label e os botões
        if w:
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            w.setMinimumWidth(10) # Permite encolher bastante se necessário
            row_layout.addWidget(w, stretch=1)
            
        # 3. Bloco de Ações (Fixo à direita)
        actions_frame = QWidget()
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(1)
        
        # Indicador Confiança
        conf_score = self.item_data.get('confidence_map', {}).get(field_id, 0.0)
        color = "#ff4444"
        if conf_score > 0.8: color = "#00c853"
        elif conf_score > 0.4: color = "#ffd600"
        
        conf_indicator = QLabel("●")
        conf_indicator.setFixedSize(8, 20) # Altura compatível com botões
        conf_indicator.setStyleSheet(f"color: {color}; font-size: 8px; margin-left: 2px;")
        actions_layout.addWidget(conf_indicator)
        
        if btn_links: 
            actions_layout.addWidget(btn_links)
            
            # Botão Express Validate (ao lado do link)
            btn_express = QPushButton("✔")
            btn_express.setFixedSize(24, 20)
            btn_express.setProperty("class", "FieldBtn")
            btn_express.setCursor(Qt.PointingHandCursor)
            btn_express.setToolTip("Validação Express: Aceita e Treina")
            # Estilo verde discreto
            btn_express.setStyleSheet("""
                QPushButton { color: #4CAF50; border: 1px solid #333; border-radius: 2px; }
                QPushButton:hover { background: #4CAF50; color: white; border: 1px solid #4CAF50; }
            """)
            btn_express.clicked.connect(lambda checked=False, f_id=field_id: self._on_express_validate(f_id))
            actions_layout.addWidget(btn_express)

        if btn_focus: actions_layout.addWidget(btn_focus)
        
        # Se não tiver botões, o frame fica bem pequeno só com indicador
        # Adicionamos ao layout principal com stretch=0 (fixo)
        row_layout.addWidget(actions_frame)

        layout.addRow(row_layout)

    def _on_position_changed(self, field_id, text):
        """Exibe campo de distância se for 'Centro'"""
        dist_field_id = field_id.replace("_p", "_dist_c")
        if dist_field_id in self.fields:
            field_widget = self.fields[dist_field_id]
            visible = (text == "Centro")
            field_widget.setEnabled(visible)
            if not visible: field_widget.setText("0.0")
            field_widget.setVisible(True)

    def open_link_manager(self, field_id, pick_type):
        """Abre a mini-lista de vínculos do campo usando Slots"""
        links_dict = self.item_data.setdefault('links', {})
        # links_dict[field_id] agora é um DICT de slots: { 'label': [...], 'geometry': [...] }
        current_links = links_dict.setdefault(field_id, {})
        
        # Migração sutil caso seja uma lista legada
        if isinstance(current_links, list):
            current_links = {'label': current_links}
            links_dict[field_id] = current_links

        if hasattr(self, 'active_link_dlg') and self.active_link_dlg:
            self.active_link_dlg.close()
            
        self.active_link_dlg = LinkManager(field_id, current_links, self)
        # MainWindow.on_pick_requested agora espera o slot_request formatado, mas precisamos manter o field_id contextualizado
        self.active_link_dlg.pick_requested.connect(lambda slot_req: self._on_manager_pick_requested(field_id, slot_req))
        self.active_link_dlg.focus_requested.connect(lambda l: self.element_focused.emit(l)) # Passa o link completo
        self.active_link_dlg.remove_requested.connect(lambda data: self._remove_link(field_id, data, self.active_link_dlg))
        
        # Novas conexões para curadoria
        self.active_link_dlg.research_requested.connect(lambda s_id: self.research_requested.emit(field_id, s_id))
        self.active_link_dlg.training_requested.connect(lambda t_data: self.training_requested.emit(field_id, t_data))
        self.active_link_dlg.config_changed.connect(lambda k, v: self.config_updated.emit(k, v))
        
        self.active_link_dlg.show()

    def _on_manager_pick_requested(self, field_id, slot_req):
        """Disparado quando um slot específico pede captura no canvas"""
        self.pick_requested.emit(field_id, slot_req)

    def _remove_link(self, field_id, data, dlg):
        """data is a dict: {'slot': slot_id, 'link': link_obj}"""
        slot_id = data.get('slot')
        link = data.get('link')
        
        links_dict = self.item_data.get('links', {})
        field_links = links_dict.get(field_id, {})
        
        if slot_id in field_links and link in field_links[slot_id]:
            field_links[slot_id].remove(link)
            # Remove validação se alterou o vínculo
            if field_id in self.item_data.get('validated_fields', []):
                self.item_data['validated_fields'].remove(field_id)
                self.refresh_validation_styles()
            dlg.refresh_list()

    def mark_field_validated(self, field_id, is_valid=True):
        """Aplica estilo visual de validação no widget do campo"""
        validated = self.item_data.setdefault('validated_fields', [])
        if is_valid:
            if field_id not in validated: validated.append(field_id)
        else:
            if field_id in validated: validated.remove(field_id)
        self.refresh_validation_styles()

    def _on_express_validate(self, field_id):
        """Valida o campo imediatamente, enviando para treino"""
        widget = self.fields.get(field_id)
        if not widget: return
        
        val = ""
        if isinstance(widget, QLineEdit): val = widget.text()
        elif isinstance(widget, QComboBox): val = widget.currentText()
        
        # Recuperar links existentes para treino
        links = self.item_data.get('links', {}).get(field_id, {})
        if isinstance(links, list): links = {'label': links}
        
        target_link = None
        target_slot = 'default'
        
        # Busca primeiro link disponível
        for slot, link_list in links.items():
            if link_list:
                target_link = link_list[0]
                target_slot = slot
                break
        
        if not target_link:
            # Cria synthetic link se não houver
            target_link = {
                'text': val, 
                'type': 'text', 
                'pos': self.item_data.get('pos', (0,0)), 
                'debug': 'Express Validation'
            }
            
        # Emite sinal de treino
        self.training_requested.emit(field_id, {
            'slot': target_slot,
            'link': target_link,
            'comment': "Expresso: Validado pelo usuário",
            'status': "valid",
            'propagate': False
        })
        
        # Marca e atualiza visual
        self.mark_field_validated(field_id, True)
        
    def refresh_validation_styles(self):
        """Varre campos e aplica borda verde nos validados"""
        validated_fields = self.item_data.get('validated_fields', [])
        for fid, w in self.fields.items():
            is_valid = fid in validated_fields
            if is_valid:
                w.setStyleSheet(self.STYLE_VALID)
            else:
                w.setStyleSheet(self.STYLE_DEFAULT)
            
            # Atualizar a bolinha (indicador)
            if fid in self.indicators:
                indicator = self.indicators[fid]
                if is_valid:
                    indicator.setStyleSheet("color: #00cc66; font-size: 14px; margin-right: 5px;")
                else:
                    # Restaurar cor baseada na confiança da IA original
                    conf_score = self.item_data.get('confidence_map', {}).get(fid, 0.0)
                    color = "#ff4444" 
                    if conf_score > 0.8: color = "#00c853"
                    elif conf_score > 0.4: color = "#ffd600"
                    indicator.setStyleSheet(f"color: {color}; font-size: 14px; margin-right: 5px;")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 5, 2, 5) # Margem mínima
        layout.setSpacing(3)
        
        # --- Cabeçalho Dinâmico ---
        header = QGroupBox("DADOS GERAIS - PILAR")
        header.setStyleSheet("QGroupBox { font-size: 10px; font-weight: bold; color: #ffb300; border: 1px solid #333; margin-top: 5px; padding-top: 8px; }")
        h_layout = QFormLayout(header)
        h_layout.setContentsMargins(2, 2, 2, 2)
        h_layout.setSpacing(1)
        
        self._add_linked_row(h_layout, "Nº Item:", "id_item", "text", show_links=False, show_focus=False)
        self._add_linked_row(h_layout, "Nome:", "name", "text")
        self._add_linked_row(h_layout, "Dimensão:", "dim", "text")
        self._add_linked_row(h_layout, "Segmentos:", "pilar_segs", "line", hide_input=True)
        
        # Formato como uma linha especial no FormLayout
        self.fields['format'] = QComboBox()
        self.fields['format'].addItems(["Retangular", "Circular", "Em L", "Em T", "Em U"])
        self.fields['format'].setCurrentText(self.item_data.get('format', 'Retangular'))
        self.fields['format'].setFixedHeight(24)
        self.fields['format'].setStyleSheet("background: #252525; border: 1px solid #444; border-radius: 3px; color: #eee;")
        
        h_layout.addRow("Formato:", self.fields['format'])
        
        layout.addWidget(header)

        # Container para conteúdo dinâmico (Abas que mudam com o formato)
        self.dynamic_container = QWidget()
        self.dynamic_layout = QVBoxLayout(self.dynamic_container)
        self.dynamic_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.dynamic_container)

        # Inicializa conteúdo dinâmico
        self._refresh_dynamic_content()
        
        # Conecta sinal de mudança de formato
        self.fields['format'].currentTextChanged.connect(self._on_format_changed)

        layout.addStretch()
        layout.addLayout(self._create_action_buttons())
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _setup_pilar_complex_view(self, layout):
        tabs = QTabWidget()
        tabs.setStyleSheet("QTabBar::tab { padding: 5px; font-size: 10px; }")
        shape = self.fields['format'].currentText()
        
        sides = ['A', 'B', 'C', 'D']
        if shape == "Circular": sides = ["Superior", "Inferior"]
        elif shape == "Em L": sides = ['A', 'B', 'C', 'D', 'E', 'F']
        elif shape in ["Em T", "Em U"]: sides = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

        for side in sides:
            tab = QWidget()
            tab_l = QVBoxLayout(tab)
            tab_l.setContentsMargins(5, 5, 5, 5)
            tab_l.setSpacing(2)
            
            # Lajes - Layout Vertical (Laje 2 abaixo da Laje 1) para compactar largura
            for i in [1, 2]:
                grp = QGroupBox(f"Laje {i}")
                grp.setStyleSheet("QGroupBox { font-size: 10px; font-weight: bold; border: 1px solid #333; margin-top: 5px; padding-top: 5px; }")
                f = QFormLayout(grp)
                f.setSpacing(1)
                f.setContentsMargins(2, 5, 2, 2)
                self._add_linked_row(f, "Nome:", f'p_s{side}_l{i}_n', "text")
                self._add_linked_row(f, "H:", f'p_s{side}_l{i}_h', "text")
                self._add_linked_row(f, "Nível:", f'p_s{side}_l{i}_v', "text")
                self._add_linked_row(f, "Pos.:", f'p_s{side}_l{i}_p', "text", is_combo=True, combo_items=["Topo", "Centro", "Fundo"])
                self._add_linked_row(f, "Dist. Centro:", f'p_s{side}_l{i}_dist_c', "line")
                
                # Inicialização de visibilidade
                self._on_position_changed(f'p_s{side}_l{i}_p', self.fields[f'p_s{side}_l{i}_p'].currentText())
                
                tab_l.addWidget(grp)

            # Categorias de Vigas
            beam_categories = [
                ("Viga Continuação Esq.", "esq", False),
                ("Viga Continuação Dir.", "dir", False),
                ("Viga Chegada 1", "ch1", True),
                ("Viga Chegada 2", "ch2", True),
                ("Viga Chegada 3", "ch3", True)
            ]
            
            for cat_name, cat_id, is_arrival in beam_categories:
                v_grp = QGroupBox(cat_name)
                v_grp.setStyleSheet("QGroupBox { font-size: 10px; color: #0078D4; border: 1px solid #333; margin-top: 10px; padding-top: 5px; }")
                vf = QFormLayout(v_grp)
                vf.setSpacing(1)
                vf.setContentsMargins(2, 5, 2, 2)
                
                id_pref = f'p_s{side}_v_{cat_id}'
                self._add_linked_row(vf, "Nome:", f'{id_pref}_n', "text")
                self._add_linked_row(vf, "Dim.:", f'{id_pref}_d', "text")
                self._add_linked_row(vf, "Seg.:", f'{id_pref}_segs', "line", hide_input=True)
                if is_arrival:
                    self._add_linked_row(vf, "Dist.:", f'{id_pref}_dist', "line")
                
                # Profundidade sem link, auto-calculado
                self._add_linked_row(vf, "Prof.:", f'{id_pref}_prof', "text", show_links=False)
                
                # Auto-update logic
                dim_widget = self.fields[f'{id_pref}_d']
                prof_widget = self.fields[f'{id_pref}_prof']
                dim_widget.textChanged.connect(lambda t, w=prof_widget: self._update_depth_from_dim(t, w))
                
                self._add_linked_row(vf, "Dif. Nível:", f'{id_pref}_diff_v', "text")
                tab_l.addWidget(v_grp)
                
            tabs.addTab(tab, f"Lado {side}")
            
        layout.addWidget(tabs)

    def _update_depth_from_dim(self, text, target_widget):
        """Calcula profundidade (maior valor) baseado no texto de dimensão (ex: '15x40')"""
        import re
        try:
            # Busca números, suportando decimais com ponto ou vírgula
            nums = [float(n.replace(',', '.')) for n in re.findall(r'\d+[.,]?\d*', text)]
            if len(nums) >= 2:
                # Se tiver pelo menos 2 números (ex: 15 e 40), pega o maior
                max_val = max(nums)
                # Formata removendo .0 se for inteiro
                txt_val = f"{int(max_val)}" if max_val.is_integer() else f"{max_val}"
                target_widget.setText(txt_val)
        except Exception:
            pass

    def _setup_viga_complex_view(self, layout):
        """Implementa detalhamento de Lado A, B e Fundo"""
        tabs = QTabWidget()
        # Definição das abas: (ID suffix, Label, IsBottom)
        sides_config = [('A', 'Lado A', False), ('B', 'Lado B', False), ('Fundo', 'Fundo', True)]
        
        for side, label, is_bottom in sides_config:
            tab = QWidget()
            tab_l = QVBoxLayout(tab)
            
            # Info Geral do Lado/Fundo
            info = QFormLayout()
            # Campos comuns
            label_prefix = f"viga_{side.lower()}"
            self._add_linked_row(info, "Local Inicial:", f'{label_prefix}_ini_name', "text")
            self._add_linked_row(info, "Local Final:", f'{label_prefix}_end_name', "text")
            self._add_linked_row(info, "Dimensão:", f'{label_prefix}_dim', "text")
            
            if is_bottom:
                # Fundo: Segmentos como lista (hide input), sem Prof/Diff
                self._add_linked_row(info, "Segmentos:", f'{label_prefix}_segs', "line", hide_input=True)
            else:
                # Lados A/B: Segmentos e Profundidade/Diff
                self._add_linked_row(info, "Segmentos:", f'{label_prefix}_segs', "line", hide_input=True)
                self._add_linked_row(info, "Profundidade:", f'{label_prefix}_prof', "text")
                self._add_linked_row(info, "Dif. Nível:", f'{label_prefix}_diff_v', "text")
            
            tab_l.addLayout(info)
            
            # Tabela apenas para A e B
            if not is_bottom:
                table = QTableWidget(0, 5)
                table.setHorizontalHeaderLabels(["Início", "Fim", "Tipo", "Tam.", "Laje"])
                table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                self.fields[f'{label_prefix}_table'] = table
                tab_l.addWidget(table)
                
                btn_add = QPushButton("+ Segmento")
                btn_add.clicked.connect(lambda t=table: t.insertRow(t.rowCount()))
                tab_l.addWidget(btn_add)
            
            tabs.addTab(tab, label)
        layout.addWidget(tabs)

    def _setup_laje_complex_view(self, layout):
        tabs = QTabWidget()
        tab = QWidget()
        l = QVBoxLayout(tab)
        
        # Grupo único para Laje
        grp = QGroupBox("Dados da Laje")
        grp.setStyleSheet("QGroupBox { font-size: 10px; font-weight: bold; border: 1px solid #444; margin-top: 5px; padding-top: 10px; }")
        form = QFormLayout(grp)
        form.setSpacing(5)
        
        # 1. Nome (com Vínculo/Zoom)
        self._add_linked_row(form, "Nome:", "laje_name", "text")
        
        # 2. Segmentos da Área (Linhas que definem o polígono) - Vínculo Visual
        # "NAO NECESSARIAMENTE UM CAMPO de escrever mas uma linha para poder vincular"
        # Usamos 'line' type para permitir selecionar linhas/polinhas no CAD
        self._add_linked_row(form, "Segmentos da Área:", "laje_outline_segs", "line", hide_input=True)
        
        l.addWidget(grp)
        l.addStretch() # Empurrar para cima
        
        tabs.addTab(tab, "Laje")
        layout.addWidget(tabs)

    def _get_initial_value(self, field_id):
        """Busca valor, priorizando links > sides_data > flat_key"""
        
        # 1. Prioridade: Valor do Vínculo (Se existir e for Texto/Line validado)
        links = self.item_data.get('links', {})
        if field_id in links:
            slots = links[field_id]
            if isinstance(slots, dict):
                 for s_list in slots.values():
                     if s_list and len(s_list) > 0:
                         return str(s_list[0].get('text', ''))
            elif isinstance(slots, list) and len(slots) > 0:
                 return str(slots[0].get('text', ''))

        # 2. Prioridade: Flat Key
        if field_id in self.item_data:
            return self.item_data[field_id]
        
        # 3. Prioridade: Nested Data (sides_data)
        if field_id.startswith('p_s'):
            try:
                parts = field_id.split('_', 2) 
                if len(parts) >= 3:
                    side = parts[1][1:] 
                    key = parts[2]
                    sides = self.item_data.get('sides_data', {})
                    side_content = sides.get(side, {})
                    return side_content.get(key)
            except Exception: pass
            
        return None

    def _create_action_buttons(self):
        # Layout Vertical para economizar largura no painel
        v = QVBoxLayout()
        v.setContentsMargins(0, 5, 0, 0)
        v.setSpacing(5)

        btn_valid = QPushButton("VALIDAR (TREINAR IA)")
        btn_valid.setObjectName("Success")
        btn_valid.setCursor(Qt.PointingHandCursor)
        btn_valid.setFixedHeight(35) # Altura menor
        btn_valid.setToolTip("Salva e treina o padrão atual no banco de dados")
        btn_valid.clicked.connect(self.on_validate)

        btn_invalid = QPushButton("MARCAR FALHA")
        btn_invalid.setObjectName("Danger")
        btn_invalid.setCursor(Qt.PointingHandCursor)
        btn_invalid.setFixedHeight(35) # Altura menor
        btn_invalid.setToolTip("Marca este item para revisão manual posterior")
        btn_invalid.clicked.connect(self.on_invalidate)

        v.addWidget(btn_valid)
        v.addWidget(btn_invalid)
        
        return v

    def on_validate(self):
        final_data = self.item_data.copy()
        validated = final_data.setdefault('validated_fields', [])
        
        # Ensure sides_data exists
        if 'sides_data' not in final_data: final_data['sides_data'] = {}
        
        for key, widget in self.fields.items():
            if isinstance(widget, QLineEdit): val = widget.text()
            elif isinstance(widget, QComboBox): val = widget.currentText()
            else: continue
            
            final_data[key] = val
            # Ao validar o card todo, todos os campos preenchidos ganham selo de validado
            if val and key not in validated:
                validated.append(key)
        
        self.refresh_validation_styles()
            
        self.data_validated.emit(final_data)
        QMessageBox.information(self, "IA Training", "Dados enviados para o banco de padrões!")

    def on_invalidate(self):
        self.data_invalidated.emit(self.item_data)
        QMessageBox.warning(self, "IA Training", "Item marcado para revisão manual.")

    def _on_format_changed(self, text):
        """Reage à mudança no ComboBox de formato"""
        self.item_data['format'] = text
        self._refresh_dynamic_content()

    def _refresh_dynamic_content(self):
        """Reconstrói a área dinâmica baseada no tipo e formato atual"""
        self._clear_dynamic_content()
        
        elem_type = self.item_data.get('type', '').lower()
        if 'pilar' in elem_type:
            # Garante que usamos o layout dinâmico
            self._setup_pilar_complex_view(self.dynamic_layout)
        elif 'viga' in elem_type:
            self._setup_viga_complex_view(self.dynamic_layout)
        elif 'laje' in elem_type:
            self._setup_laje_complex_view(self.dynamic_layout)

    def _clear_dynamic_content(self):
        """Remove widgets dinâmicos e limpa referências no self.fields"""
        # Identifica campos que pertencem ao container dinâmico para remover do self.fields
        to_remove = []
        for key, widget in self.fields.items():
            if self._is_descendant(widget, self.dynamic_container):
                to_remove.append(key)
        
        for k in to_remove:
            del self.fields[k]
            
        # Remove widgets do layout
        while self.dynamic_layout.count():
            item = self.dynamic_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Se for um layout aninhado, precisamos limpar recursivamente ou deletar o item
                # Layouts em Qt não são widgets, mas items layout.
                # O ideal é que tudo esteja dentro de widgets.
                # Como usamos .addWidget(tabs), tabs é um widget.
                pass

    def _is_descendant(self, widget, ancestor):
        """Verifica se widget é descendente de ancestor (para limpeza segura)"""
        p = widget
        while p:
            if p == ancestor: return True
            p = p.parentWidget()
        return False
