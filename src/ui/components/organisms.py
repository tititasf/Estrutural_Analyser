from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QSplitter, QLabel, QTreeWidget, QTreeWidgetItem, QListWidget, QPushButton
from PySide6.QtCore import Qt, Signal
from .atoms import NavButton, MetricLabel, AISuggestionBox, SyncToggleButton
from .molecules_diagnostic import FloorListItem, ViewShortcutItem, EntityRow
from .molecules_comparison import ScenarioSelector, ConflictCard, StressBarChart
from src.ui.canvas import CADCanvas

class DiagnosticSidebar(QFrame):
    """
    Sidebar Hierárquico do Módulo de Diagnóstico.
    Exibe a lista de Obras e, dentro delas, os documentos DXF Brutos (Ingestão).
    """
    document_selected = Signal(dict) # Emite os dados do documento (dict do DB)
    
    def __init__(self, db=None):
        super().__init__()
        self.db = db
        self.setFixedWidth(280)
        self.setStyleSheet("""
            DiagnosticSidebar { 
                background: #1e1e1e; 
                border-right: 1px solid #333; 
            }
            QTreeWidget {
                background: transparent;
                border: none;
                color: #ddd;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2a2a2a;
            }
            QTreeWidget::item:selected {
                background: #2a2a3e;
                color: #00d4ff;
            }
            QHeaderView::section {
                background: #252528;
                color: #666;
                padding: 5px;
                font-size: 10px;
                font-weight: bold;
                border: none;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. Header
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet("border-bottom: 1px solid #333; background: #252528;")
        head_layout = QHBoxLayout(header)
        lbl_head = QLabel("PROJETOS E ENTRADAS")
        lbl_head.setStyleSheet("color: #aaa; font-weight: bold; font-size: 11px;")
        head_layout.addWidget(lbl_head)
        layout.addWidget(header)
        
        # 2. Tree Widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("OBRAS / ARQUIVOS BRUTOS")
        self.tree.setIndentation(15)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)
        
        # 3. Footer / Stats
        self.lbl_stats = QLabel("Nenhuma obra carregada")
        self.lbl_stats.setStyleSheet("color: #555; font-size: 10px; padding: 10px;")
        layout.addWidget(self.lbl_stats)

    def set_database(self, db):
        self.db = db
        self.refresh()

    def refresh(self):
        """Atualiza a árvore com obras e documentos brutos filtrados."""
        if not self.db:
            return
            
        self.tree.clear()
        
    def refresh(self):
        """Atualiza a árvore com obras e documentos brutos filtrados."""
        if not self.db:
            return
            
        self.tree.clear()
        
        try:
            works = self.db.get_all_works()
            all_projects = self.db.get_projects()
            
            total_docs = 0
            # Categorias Alvo da Fase 1 (Ingestão)
            phase1_categories = [
                "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)",
                "Documentos e Atas de Reunioes(.PDF/.MD)",
                "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)"
            ]
            
            for work_name in works:
                work_item = QTreeWidgetItem(self.tree)
                work_item.setText(0, f"📁 {work_name.upper()}")
                work_item.setFlags(work_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                
                # Coletar documentos
                docs = self.db.get_work_documents(work_name)
                obra_projects = [p for p in all_projects if p.get('work_name') == work_name]
                for proj in obra_projects:
                    docs.extend(self.db.get_project_documents(proj['id']))

                filtered_docs = []
                for d in docs:
                    cat = d.get('category', '')
                    name = d.get('name', '').lower()
                    ext = d.get('extension', '').lower()
                    
                    # 1. Por categoria exata definida no ProjectManager
                    matches_class = cat in phase1_categories
                    
                    # 2. Por fallback robusto
                    is_dxf_dwg = ext in ['.dxf', '.dwg']
                    matches_fallback = is_dxf_dwg and any(k in name for k in ["(auto-dxf)", "bruto", "estrutural", "ingestao"])
                    
                    if matches_class or matches_fallback:
                        filtered_docs.append(d)
                
                # Adicionar à árvore
                for doc in filtered_docs:
                    doc_item = QTreeWidgetItem(work_item)
                    display_name = doc.get('name', 'Sem Nome')
                    doc_item.setText(0, f"📄 {display_name}")
                    doc_item.setData(0, Qt.UserRole, doc)
                    total_docs += 1
                
                if filtered_docs:
                    work_item.setExpanded(True)
                else:
                    # Se não tem documentos, mostrar um item informativo (opcional)
                    pass

            self.lbl_stats.setText(f"{len(works)} Obras | {total_docs} Arquivos DXF encontrados")
            
        except Exception as e:
            print(f"[DiagnosticSidebar] Erro ao carregar dados: {e}")

    def _on_item_double_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data:
            self.document_selected.emit(data)

class TechSheetPanel(QFrame):
    """
    Painel Direito de Processamento e Categorização (Fase 1 -> 2).
    Contém: Botões de Ação (IA), e Listas de Destino para recortes do DXF.
    """
    filter_requested = Signal(str, str) # type, value
    extract_requested = Signal(str) # mode ('clean' or 'detail')
    
    def __init__(self):
        super().__init__()
        self.setFixedWidth(300)
        self.setStyleSheet("background: #1e1e1e; border-left: 1px solid #333;")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. AI / Action Header
        btn_ai_fix = QPushButton("🤖 APPLY FIX (AI Analysis)")
        btn_ai_fix.setCursor(Qt.PointingHandCursor)
        btn_ai_fix.setFixedHeight(40)
        btn_ai_fix.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0078d4, stop:1 #00b4d4);
                color: white; font-weight: bold; border: none; border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background: #0099ff; }
        """)
        layout.addWidget(btn_ai_fix)
        
        layout.addWidget(self._create_divider())

        # 2. Listas de Saída (Stage 1 -> Stage 2)
        lbl_outputs = QLabel("OUTPUTS / TRIAGEM (FASE 2)")
        lbl_outputs.setStyleSheet("color: #aaa; font-weight: bold; font-size: 10px; margin-top: 10px;")
        layout.addWidget(lbl_outputs)
        
        # Lista A: Estruturais Limpos
        self.list_clean_struct = QListWidget()
        self.list_clean_struct.addItem("1-pavimento_clean.dxf (Exemplo)")
        self.list_clean_struct.setStyleSheet("background: #252528; border: 1px solid #444; border-radius: 4px;")
        
        layout.addWidget(QLabel("🏗️ Estruturais Pavimentos Limpos"))
        layout.addWidget(self.list_clean_struct)
        
        # Lista B: Detalhamentos
        self.list_details = QListWidget()
        self.list_details.setStyleSheet("background: #252528; border: 1px solid #444; border-radius: 4px;")
        
        layout.addWidget(QLabel("📐 Detalhamentos Específicos"))
        layout.addWidget(self.list_details)
        
        layout.addWidget(self._create_divider())
        
        # 3. Ferramentas de Extração
        lbl_tools = QLabel("FERRAMENTAS DE EXTRAÇÃO")
        lbl_tools.setStyleSheet("color: #aaa; font-weight: bold; font-size: 10px; margin-top: 5px;")
        layout.addWidget(lbl_tools)
        
        tools_layout = QHBoxLayout()
        btn_cut_clean = QPushButton("✂️ Recortar para\nEstrutural Limpo")
        btn_cut_detail = QPushButton("✂️ Recortar para\nDetalhamento")
        
        # Conectar sinais de recorte
        btn_cut_clean.clicked.connect(lambda: self.extract_requested.emit('clean'))
        btn_cut_detail.clicked.connect(lambda: self.extract_requested.emit('detail'))
        
        for btn in [btn_cut_clean, btn_cut_detail]:
            btn.setFixedHeight(45)
            btn.setStyleSheet("""
                QPushButton {
                    background: #2d2d30; border: 1px solid #555; color: #ddd; border-radius: 4px; font-size: 10px;
                }
                QPushButton:hover { background: #3e3e42; border-color: #777; }
            """)
            tools_layout.addWidget(btn)
            
        layout.addLayout(tools_layout)
        
        # 4. Filtros Rápidos (Container Dinâmico)
        layout.addWidget(self._create_divider())
        lbl_dynamic = QLabel("🎛️ TRIAGEM POR PADRÕES")
        lbl_dynamic.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 10px; margin-top: 5px;")
        layout.addWidget(lbl_dynamic)
        
        # Scroll para filtros se houver muitos layers
        filter_scroll = QScrollArea()
        filter_scroll.setWidgetResizable(True)
        filter_scroll.setFrameShape(QFrame.NoFrame)
        filter_scroll.setStyleSheet("background: transparent;")
        
        self.filters_widget = QWidget()
        self.filters_layout = QVBoxLayout(self.filters_widget)
        self.filters_layout.setSpacing(2)
        self.filters_layout.setContentsMargins(0,0,0,0)
        
        filter_scroll.setWidget(self.filters_widget)
        layout.addWidget(filter_scroll)
        
        layout.addStretch()

    def update_dynamic_filters(self, metadata):
        """Atualiza a lista de filtros com base no DXF atual."""
        # Limpar layout anterior
        while self.filters_layout.count():
            child = self.filters_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        # 1. Seção Layers
        if metadata.get('layers'):
            self._add_filter_group("🏙️ LAYERS", "layer", sorted(list(metadata['layers'])))
            
        # 2. Seção Cores
        if metadata.get('colors'):
            cols = sorted(list(metadata['colors']))
            col_labels = {1: "🔴 Red", 2: "🟡 Yellow", 3: "🟢 Green", 5: "🔵 Blue", 7: "⚪ White", 256: "🎨 ByLayer"}
            self._add_filter_group("🎨 CORES", "color", [c for c in cols if c in col_labels], labels=col_labels)
            
        # 3. Seção Espécies/Tipos
        if metadata.get('types'):
            self._add_filter_group("📋 ESPÉCIES/TIPOS", "type", sorted(list(metadata['types'])))

    def _add_filter_group(self, title, f_type, items, labels=None):
        lbl = QLabel(title)
        lbl.setStyleSheet("color: #777; font-size: 9px; font-weight: bold; margin-top: 8px; padding-left: 5px;")
        self.filters_layout.addWidget(lbl)
        
        for val in items:
            display_name = labels.get(val, str(val)) if labels else str(val)
            btn = QPushButton(display_name)
            btn.setToolTip(f"Filtrar por {f_type}: {val}")
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left; padding: 4px 8px; font-size: 10px;
                    background: #252528; border: 1px solid #333; color: #bbb;
                }
                QPushButton:hover { background: #333336; color: #fff; border-color: #00E5FF; }
            """)
            # Fix mapping for color filters
            btn.clicked.connect(lambda _, t=f_type, v=val: self.filter_requested.emit(t, str(v)))
            self.filters_layout.addWidget(btn)

    def _create_divider(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        frame.setStyleSheet("color: #333;")
        return frame

class DualCanvasManager(QWidget):
    """
    Gerenciador de Comparação com 2 Canvases e Sincronização.
    """
    def __init__(self):
        super().__init__()
        self.sync_enabled = False
        
        # Layout Principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        
        # Toolbar de Controle
        toolbar = QFrame()
        toolbar.setFixedHeight(45)
        toolbar.setStyleSheet("background: #252525; border-bottom: 1px solid #444;")
        tb_layout = QHBoxLayout(toolbar)
        
        tb_layout.addWidget(ScenarioSelector("BASE MODEL"))
        tb_layout.addStretch()
        
        self.btn_sync = SyncToggleButton()
        self.btn_sync.toggled.connect(self.toggle_sync)
        tb_layout.addWidget(self.btn_sync)
        
        tb_layout.addStretch()
        tb_layout.addWidget(ScenarioSelector("MODIFIED MODEL"))
        
        main_layout.addWidget(toolbar)
        
        # Splitter com 2 Canvases
        self.splitter = QSplitter(Qt.Horizontal)
        self.canvas_a = CADCanvas()
        self.canvas_b = CADCanvas()
        
        self.splitter.addWidget(self.canvas_a)
        self.splitter.addWidget(self.canvas_b)
        main_layout.addWidget(self.splitter)
        
        # Setup Sync Logic
        # Conectar scrollbars
        self.scroll_a_h = self.canvas_a.horizontalScrollBar()
        self.scroll_a_v = self.canvas_a.verticalScrollBar()
        self.scroll_b_h = self.canvas_b.horizontalScrollBar()
        self.scroll_b_v = self.canvas_b.verticalScrollBar()
        
        self.scroll_a_h.valueChanged.connect(self._sync_scroll_h_a)
        self.scroll_b_h.valueChanged.connect(self._sync_scroll_h_b)
        self.scroll_a_v.valueChanged.connect(self._sync_scroll_v_a)
        self.scroll_b_v.valueChanged.connect(self._sync_scroll_v_b)
        
        # TODO: Sync Zoom (Scale) requires overriding wheelEvent in CADCanvas or signal
        
    def toggle_sync(self, enabled):
        self.sync_enabled = enabled
        
    def _sync_scroll_h_a(self, val):
        if self.sync_enabled:
            self.scroll_b_h.setValue(val)
            
    def _sync_scroll_h_b(self, val):
        if self.sync_enabled:
            self.scroll_a_h.setValue(val)

    def _sync_scroll_v_a(self, val):
        if self.sync_enabled:
            self.scroll_b_v.setValue(val)
            
    def _sync_scroll_v_b(self, val):
        if self.sync_enabled:
            self.scroll_a_v.setValue(val)
