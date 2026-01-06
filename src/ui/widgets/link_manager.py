from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                                 QListWidgetItem, QPushButton, QLabel, QFrame, QTextEdit, 
                                 QScrollArea, QWidget, QLineEdit, QMessageBox)
from PySide6.QtCore import Qt, Signal

class LinkManager(QDialog):
    """
    Mini-janela para gerenciamento de vínculos com suporte a Classes (Slots) de objetos.
    Cada slot representa uma informação necessária para o campo.
    """
    focus_requested = Signal(dict)
    remove_requested = Signal(dict)
    pick_requested = Signal(str)      # "slot_id|type"
    research_requested = Signal(str)  # slot_id
    training_requested = Signal(dict) # {slot, link, comment, status}
    config_changed = Signal(str, list) # field_key, updated_slots_config

    # Configuração de slots por tipo de campo
    # id: identificador interno do slot
    # name: Nome amigável da classe
    # type: 'text' ou 'line'
    # help: Resumo explicativo da finalidade desta classe
    SLOT_CONFIG = {
        '_l1_n': [
            {'id': 'label', 'name': 'Identificador Laje', 'type': 'text', 'prompt': 'Busque textos "L" + numeral próximo ao pilar.', 'help': 'Texto "Lxx". Define qual painel de laje descarrega aqui.'},
            {'id': 'void_x', 'name': 'Vazio (X)', 'type': 'geometry', 'prompt': 'Selecione as linhas do "X" que indica vazio.', 'help': 'Marca este setor como "SEM LAJE" (Vazios/Shafts).'}
        ],
        '_l1_h': [
            {'id': 'thick', 'name': 'Texto de Espessura', 'type': 'text', 'prompt': 'Busque padrões "H=" ou "d=" próximo à laje. regex: ([Hd]=?\\d+)', 'help': 'Texto "H=12" ou "d=12". Define a altura da laje.'}
        ],
        '_l1_v': [
            {'id': 'level', 'name': 'Nível da Laje', 'type': 'text', 'prompt': 'Busque cotas de nível (+0.00) próximas. regex: ([+-]\\d+\\.\\d+)', 'help': 'Cota de nível (ex: +3.00). Define a base de apoio.'}
        ],
        '_segs': [ 
            {'id': 'segments', 'name': 'Geometria Real', 'type': 'geometry', 'prompt': 'Selecione polilinhas ou linhas que definem o contorno.', 'help': 'Linhas/Polilinhas no CAD que representam o corpo do objeto.'}
        ],
        '_v_': [ 
            {'id': 'label', 'name': 'Identificador Viga', 'type': 'text', 'prompt': 'Busque textos "V" + numeral cruzando o pilar.', 'help': 'Texto "Vxx". Identifica a viga de suporte.'}
        ],
        '_viga_': [ 
            {'id': 'label', 'name': 'Identificador Viga', 'type': 'text', 'prompt': 'Busque o nome da viga neste trecho.', 'help': 'Identificador da viga neste trecho.'}
        ],
        'name': [
            {'id': 'label', 'name': 'Identificador Primário', 'type': 'text', 'prompt': 'Busque o texto Pxx central ao pilar.', 'help': 'O texto "Pxx" que identifica o pilar.'}
        ],
        'dim': [
            {'id': 'label', 'name': 'Texto de Dimensão', 'type': 'text', 'prompt': 'Busque textos de seção (ex: 20x50, 15/40). regex: (\\d+[\\s]*[xX/][\\s]*\\d+)', 'help': 'Texto "20x50" que define a seção bruta.'}
        ],
        '_beam_dim': [
            {'id': 'dim', 'name': 'Texto de Dimensão', 'type': 'text', 'prompt': 'Busque textos com 2 números (ex: 20x50, 100/60, (10x40), (50/54)). regex: (\\d+\\s*[xX/]\\s*\\d+)', 'help': 'Texto de seção da viga.'}
        ],
        '_dist_c': [
            {'id': 'dist_text', 'name': 'Distância (Texto/Cota)', 'type': 'text', 'prompt': 'Busque texto/cota de distância próximo ao corte. regex: (\\d+[\\.,]?\\d*)', 'help': 'Valor numérico da distância ao centro.'},
            {'id': 'dist_line', 'name': 'Distância (Linha)', 'type': 'line', 'prompt': 'Desenhe a linha representando a distância.', 'help': 'Linha medida no CAD para extrair o valor.'}
        ],
        '_diff_v': [
            {'id': 'diff_text', 'name': 'Diferença de Nível (Texto/Cota)', 'type': 'text', 'prompt': 'Busque texto/cota de diferença de nível. regex: ([+-]?\\d+[\\.,]?\\d*)', 'help': 'Valor numérico da diferença de nível.'},
            {'id': 'diff_line', 'name': 'Diferença de Nível (Linha)', 'type': 'line', 'prompt': 'Desenhe a linha representando a diferença de nível.', 'help': 'Linha medida no CAD para extrair o valor.'}
        ],
        '_v_esq_segs': [
            {'id': 'seg_cont', 'name': 'Segmento de Continuação', 'type': 'line', 'prompt': 'Desenhe a linha sobre a viga de continuação (1 segmento).', 'help': 'Referência geométrica da viga que continua do pilar.'}
        ],
        '_v_dir_segs': [
            {'id': 'seg_cont', 'name': 'Segmento de Continuação', 'type': 'line', 'prompt': 'Desenhe a linha sobre a viga de continuação (1 segmento).', 'help': 'Referência geométrica da viga que continua do pilar.'}
        ],
        '_v_ch': [
            {'id': 'seg_1', 'name': 'Segmento Chegada 1', 'type': 'line', 'prompt': 'Desenhe a primeira linha da viga de chegada.', 'help': 'Segmento 1 da viga que chega no pilar.'},
            {'id': 'seg_2', 'name': 'Segmento Chegada 2', 'type': 'line', 'prompt': 'Desenhe a segunda linha da viga de chegada.', 'help': 'Segmento 2 da viga que chega no pilar.'}
        ],
        '_viga_segs': [
             {'id': 'main_seg', 'name': 'Segmento Principal', 'type': 'line', 'prompt': 'Desenhe a linha central da viga.', 'help': 'Eixo da viga.'},
             {'id': 'border_1', 'name': 'Borda 1', 'type': 'line', 'prompt': 'Desenhe a linha de borda 1.', 'help': 'Contorno lateral 1.'},
             {'id': 'border_2', 'name': 'Borda 2', 'type': 'line', 'prompt': 'Desenhe a linha de borda 2.', 'help': 'Contorno lateral 2.'}
        ],
        '_fundo_segs': [
             {'id': 'contour', 'name': 'Contorno Fundo', 'type': 'poly', 'prompt': 'Desenhe o perímetro do fundo (Polyline). [Enter] para finalizar.', 'help': 'Geometria do fundo da viga.'}
        ],
        '_laje_geom': [
             {'id': 'contour', 'name': 'Contorno Laje', 'type': 'poly', 'prompt': 'Desenhe o perímetro da laje. [Enter] para finalizar.', 'help': 'Geometria da área da laje.'}
        ],
        'default': [
            {'id': 'main', 'name': 'Vínculo Principal', 'type': 'text', 'prompt': 'Identifique o elemento principal no CAD.', 'help': 'Texto ou objeto que define o valor deste campo.'}
        ]
    }

    def __init__(self, field_id, current_links, parent=None):
        super().__init__(parent)
        self.field_id = field_id
        # links agora é um dicionário: {slot_id: [links...]}
        self.links = current_links if isinstance(current_links, dict) else {}
        self.setWindowTitle(f"Curadoria: {field_id}")
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(480)
        self.setMinimumHeight(500)
        self.init_ui()

    def _get_slots(self):
        field_id = self.field_id
        
        # Ordem de prioridade: das mais específicas para as mais genéricas
        if '_v_esq_segs' in field_id:
            return self.SLOT_CONFIG['_v_esq_segs']
        if '_v_dir_segs' in field_id:
            return self.SLOT_CONFIG['_v_dir_segs']
        if '_v_ch' in field_id and '_segs' in field_id:
            return self.SLOT_CONFIG['_v_ch']
        
        # New: Fundo e Laje Poly
        if 'viga_fundo' in field_id and '_segs' in field_id:
             return self.SLOT_CONFIG['_fundo_segs']
        if 'laje' in field_id and '_geom' in field_id:
             return self.SLOT_CONFIG['_laje_geom']

        if 'viga_' in field_id and '_segs' in field_id:
            return self.SLOT_CONFIG['_viga_segs']
        
        if '_dist_c' in field_id:
            return self.SLOT_CONFIG['_dist_c']
        if '_diff_v' in field_id:
            return self.SLOT_CONFIG['_diff_v']
        if field_id.startswith('p_s') and '_v_' in field_id and field_id.endswith('_d'):
            return self.SLOT_CONFIG['_beam_dim']
        if field_id.endswith('_dim'):
            return self.SLOT_CONFIG['dim']
        
        for key in self.SLOT_CONFIG:
            if key in field_id:
                return self.SLOT_CONFIG[key]
        return self.SLOT_CONFIG['default']

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        self.setStyleSheet("""
            QDialog { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e1e1e, stop:1 #121212); 
                border: 1px solid #333; 
                border-radius: 12px; 
            }
            QLabel { color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
            .HeaderLabel { font-size: 14px; font-weight: bold; color: #00d4ff; }
            
            QScrollArea { border: none; background: transparent; }
            .SlotFrame { background: #252525; border: 1px solid #3a3a3a; border-radius: 10px; padding: 12px; margin-bottom: 10px; }
            .SlotTitle { font-size: 11px; font-weight: bold; color: #00d4ff; letter-spacing: 1px; }
            .SlotHelp { font-size: 10px; color: #999; font-style: italic; line-height: 1.4; }
            
            .LinkItem { background: #1a1a1a; border: 1px solid #333; border-radius: 6px; padding: 6px; margin-top: 5px; }
            .LinkValue { color: #fff; font-size: 12px; font-family: 'Consolas', monospace; }
            
            QPushButton.AddBtn { 
                background: #1e1e1e; color: #ffb300; border: 1px solid #ffb300; border-radius: 6px; 
                padding: 8px 15px; font-size: 10px; font-weight: bold;
            }
            QPushButton.AddBtn:hover { background: #ffb300; color: #1e1e1e; }
            QPushButton.LineBtn { border: 1px solid #4CAF50; color: #4CAF50; }
            QPushButton.LineBtn:hover { background: #4CAF50; color: white; }
            
            QPushButton.IconBtn { background: #1e1e1e; border: 1px solid #ffb300; border-radius: 4px; color: #ffb300; }
            QPushButton.IconBtn:hover { background: #ffb300; color: #1e1e1e; }
            QPushButton.DelBtn { color: #ff5252; border: 1px solid #ff5252; }
            QPushButton.DelBtn:hover { background: #ff5252; color: white; }
            
            .FeedbackPanel { background: #1a1a1a; border-top: 1px solid #333; padding-top: 10px; margin-top: 10px; }
            QTextEdit { background: #121212; color: #ddd; border: 1px solid #333; border-radius: 4px; font-size: 10px; }
            
            QPushButton.CurationBtn { font-size: 9px; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
            QPushButton.TrainSuccess { background: #1e1e1e; color: #4CAF50; border: 1px solid #4CAF50; }
            QPushButton.TrainSuccess:hover { background: #4CAF50; color: white; }
            QPushButton.TrainFail { background: #1e1e1e; color: #ff5252; border: 1px solid #ff5252; }
            QPushButton.TrainFail:hover { background: #ff5252; color: white; }
            QPushButton.ResearchBtn { background: #1e1e1e; color: #ffb300; border: 1px solid #ffb300; }
            QPushButton.ResearchBtn:hover { background: #ffb300; color: #1e1e1e; }
        """)

        # Cabeçalho
        header_lbl = QLabel(f"📍 CURADORIA DE CAMPO: {self.field_id}")
        header_lbl.setProperty("class", "HeaderLabel")
        layout.addWidget(header_lbl)

        # Área de Scroll para os Slots
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        scroll_layout = QVBoxLayout(container)
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(0, 0, 10, 0)
        
        self.slots_container = scroll_layout
        
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # Botão para criar novo slot
        btn_new_slot = QPushButton("➕ ADICIONAR NOVA CLASSE DE VÍNCULO")
        btn_new_slot.setStyleSheet("""
            QPushButton { 
                background: #1a1a1a; color: #00d4ff; border: 1px dashed #00d4ff; 
                padding: 10px; border-radius: 8px; font-weight: bold; margin-top: 10px;
            }
            QPushButton:hover { background: #00d4ff; color: #1a1a1a; }
        """)
        btn_new_slot.clicked.connect(self._add_new_slot_template)
        layout.addWidget(btn_new_slot)

        self.refresh_list()

    def refresh_list(self):
        # Limpar slots anteriores
        while self.slots_container.count():
            item = self.slots_container.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        slots = self._get_slots()
        for slot in slots:
            slot_id = slot['id']
            slot_links = self.links.get(slot_id, [])
            is_empty = len(slot_links) == 0

            slot_frame = QFrame()
            slot_frame.setProperty("class", "SlotFrame")
            sf_layout = QVBoxLayout(slot_frame)
            sf_layout.setSpacing(12)

            # Header do Slot - EDITÁVEL
            sh_layout = QHBoxLayout()
            sh_info = QVBoxLayout()
            
            # Campo Nome do Slot
            st_edit = QLineEdit(slot['name'].upper())
            st_edit.setProperty("class", "SlotTitle")
            st_edit.setPlaceholderText("NOME DA CLASSE...")
            sh_info.addWidget(st_edit)
            
            # Campo Prompt (IA Hint)
            prompt_edit = QLineEdit(slot.get('prompt', ''))
            prompt_edit.setPlaceholderText("PROMPT IA: O que buscar?")
            prompt_edit.setStyleSheet("background: #1a1a1a; color: #ffb300; font-size: 10px; border: 1px solid #333; padding: 4px;")
            sh_info.addWidget(prompt_edit)

            # Campo Ajuda (Help)
            help_edit = QLineEdit(slot.get('help', ''))
            help_edit.setPlaceholderText("DESCRIÇÃO: Para que serve?")
            help_edit.setProperty("class", "SlotHelp")
            help_edit.setStyleSheet("background: #1a1a1a; color: #999; font-size: 10px; border: 1px solid #333; padding: 4px;")
            sh_info.addWidget(help_edit)
            
            # Botões de Ação do Header
            h_btns = QVBoxLayout()
            
            btn_research = QPushButton("🔄 REBUSCAR")
            btn_research.setToolTip("Pede à IA para tentar localizar o objeto ideal no CAD.")
            btn_research.setProperty("class", "CurationBtn ResearchBtn")
            btn_research.setFixedHeight(28)
            btn_research.setCursor(Qt.PointingHandCursor)
            btn_research.clicked.connect(lambda checked=False, s_id=slot_id: self.research_requested.emit(s_id))
            
            btn_save_def = QPushButton("💾 SALVAR DEFINIÇÃO")
            btn_save_def.setToolTip("Salva as alterações de Nome, Prompt e Descrição desta classe.")
            btn_save_def.setStyleSheet("font-size: 8px; color: #888; border: 1px solid #444; padding: 2px;")
            btn_save_def.clicked.connect(lambda checked=False, s=slot, ne=st_edit, pe=prompt_edit, he=help_edit: 
                                        self._save_slot_definition(s, ne.text(), pe.text(), he.text()))
            
            h_btns.addWidget(btn_research)
            h_btns.addWidget(btn_save_def)
            
            sh_layout.addLayout(sh_info, 1)
            sh_layout.addLayout(h_btns)
            sf_layout.addLayout(sh_layout)

            # Lista de Vínculos do Slot
            if is_empty:
                empty_lbl = QLabel("Aguardando vínculo desta classe...")
                empty_lbl.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
                sf_layout.addWidget(empty_lbl)
            else:
                for idx, link in enumerate(slot_links):
                    li_frame = QFrame()
                    li_frame.setProperty("class", "LinkItem")
                    li_v_layout = QVBoxLayout(li_frame)
                    
                    li_h_layout = QHBoxLayout()
                    val_text = str(link.get('text', 'ID Geometrico'))
                    val_lbl = QLabel(val_text)
                    val_lbl.setProperty("class", "LinkValue")
                    
                    btn_focus = QPushButton("🔍 FOCAR")
                    btn_focus.setFixedHeight(24)
                    btn_focus.setProperty("class", "IconBtn FieldBtn")
                    btn_focus.setCursor(Qt.PointingHandCursor)
                    btn_focus.clicked.connect(lambda checked=False, l=link: self.focus_requested.emit(l))
                    
                    btn_del = QPushButton("🗑️ APAGAR")
                    btn_del.setFixedHeight(24)
                    btn_del.setProperty("class", "IconBtn DelBtn FieldBtn")
                    btn_del.setCursor(Qt.PointingHandCursor)
                    btn_del.clicked.connect(lambda checked=False, s_id=slot_id, l=link: self._remove_link(s_id, l))
                    
                    li_h_layout.addWidget(val_lbl, 1)
                    li_h_layout.addWidget(btn_focus)
                    li_h_layout.addWidget(btn_del)
                    li_v_layout.addLayout(li_h_layout)

                    # --- Painel de Feedback e Treinamento (🧠) ---
                    feedback = QFrame()
                    feedback.setProperty("class", "FeedbackPanel")
                    f_layout = QVBoxLayout(feedback)
                    f_layout.setSpacing(5)
                    f_layout.setContentsMargins(0, 5, 0, 0)

                    # Badge de Insight Técnico (DNA/Confidence)
                    dna_badge = QLabel("📊 DNA Insight: Area/Densid. Match | Confiança: 85%")
                    dna_badge.setStyleSheet("font-size: 8px; color: #00d4ff; background: #1a1a1a; padding: 3px; border-radius: 4px; border: 1px solid #333;")
                    if 'debug' in link: dna_badge.setText(f"📊 {link['debug']}")
                    f_layout.addWidget(dna_badge)

                    comment_box = QTextEdit()
                    comment_box.setPlaceholderText("Por que este vínculo está correto ou errado? (Treina IA)")
                    comment_box.setFixedHeight(40)
                    f_layout.addWidget(comment_box)
                    
                    btns_train = QHBoxLayout()
                    btn_train_ok = QPushButton("🧠 VALIDAR INTERPRETAÇÃO (TREINAR E SALVAR ITEM NO DXF)")
                    btn_train_ok.setProperty("class", "CurationBtn TrainSuccess")
                    btn_train_ok.setCursor(Qt.PointingHandCursor)
                    btn_train_ok.clicked.connect(lambda checked=False, s=slot_id, l=link, c=comment_box: 
                                               self._on_train_clicked(s, l, c.toPlainText(), True))

                    # Novo: Botão de Propagação Inteligente
                    btn_propagate = QPushButton("📡 PROPAGAR")
                    btn_propagate.setToolTip("Aplica este treino a todos os pilares com DNA similar no projeto.")
                    btn_propagate.setStyleSheet("""
                        QPushButton { background: #1a1a1a; color: #ff00ff; border: 1px solid #ff00ff; font-size: 8px; font-weight: bold; }
                        QPushButton:hover { background: #ff00ff; color: white; }
                    """)
                    btn_propagate.setFixedWidth(70)
                    btn_propagate.clicked.connect(lambda checked=False, s=slot_id, l=link, c=comment_box: 
                                                self._on_train_clicked(s, l, c.toPlainText(), True, propagate=True))

                    btn_train_no = QPushButton("⚠️ MARCAR FALHA")
                    btn_train_no.setProperty("class", "CurationBtn TrainFail")
                    btn_train_no.setCursor(Qt.PointingHandCursor)
                    btn_train_no.clicked.connect(lambda checked=False, s=slot_id, l=link, c=comment_box: 
                                               self._on_train_clicked(s, l, c.toPlainText(), False))
                    
                    btns_train.addWidget(btn_train_no)
                    btns_train.addWidget(btn_train_ok)
                    btns_train.addWidget(btn_propagate) # Adicionado Propagar
                    f_layout.addLayout(btns_train)
                    
                    li_v_layout.addWidget(feedback)
                    sf_layout.addWidget(li_frame)

            # Botão de Adição específico para este Slot (Sempre visível no fundo)
            btn_add = QPushButton(f"+ CAPTURAR {slot['name'].upper()}")
            btn_add.setProperty("class", "AddBtn")
            if slot['type'] in ['line', 'geometry']: btn_add.setProperty("class", "AddBtn LineBtn")
            btn_add.setCursor(Qt.PointingHandCursor)
            btn_add.clicked.connect(lambda checked=False, s=slot: self._on_pick_clicked(s))
            sf_layout.addWidget(btn_add)

            self.slots_container.addWidget(slot_frame)
        
        self.slots_container.addStretch()

    def _on_pick_clicked(self, slot):
        self.hide()
        # Formato: "slot_id|pick_type"
        self.pick_requested.emit(f"{slot['id']}|{slot['type']}")

    def _remove_link(self, slot_id, link):
        if slot_id in self.links:
            self.links[slot_id].remove(link)
            self.remove_requested.emit({'slot': slot_id, 'link': link})
            self.refresh_list()

    def _on_train_clicked(self, slot, link, comment, is_valid, propagate=False):
        status = "valid" if is_valid else "fail"
        self.training_requested.emit({
            'slot': slot, 
            'link': link, 
            'comment': comment, 
            'status': status,
            'propagate': propagate
        })
        if not propagate:
            self.refresh_list()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Propagação", "IA analisando pilares similares para propagar este conhecimento...")

    def _save_slot_definition(self, slot, name, prompt, help_text):
        """Atualiza a configuração do slot e avisa o sistema para persistir"""
        slot['name'] = name
        slot['prompt'] = prompt
        slot['help'] = help_text
        
        # Encontrar qual chave do SLOT_CONFIG estamos editando
        found_key = 'default'
        for key in self.SLOT_CONFIG:
            if key in self.field_id:
                found_key = key
                break
        
        self.config_changed.emit(found_key, self.SLOT_CONFIG[found_key])
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Configuração Salva", f"Classe '{name}' atualizada com sucesso!")

    def _add_new_slot_template(self):
        """Adiciona um novo slot vazio para configuração"""
        found_key = 'default'
        for key in self.SLOT_CONFIG:
            if key in self.field_id:
                found_key = key
                break
        
        # Gerar um ID único simples
        new_id = f"custom_{len(self.SLOT_CONFIG[found_key])}"
        new_slot = {
            'id': new_id, 
            'name': 'NOVA CLASSE', 
            'type': 'text', 
            'prompt': 'Descreva o que buscar...', 
            'help': 'Explique a finalidade...'
        }
        
        self.SLOT_CONFIG[found_key].append(new_slot)
        self.refresh_list()
