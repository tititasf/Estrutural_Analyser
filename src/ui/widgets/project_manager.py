from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                                QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox, 
                                QListWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView,
                                 QComboBox, QInputDialog, QMenu, QToolButton, QTabWidget,
                                 QFrame, QScrollArea, QSplitter, QAbstractItemView, QProgressBar, QTextEdit, QGridLayout, QSizePolicy,
                                 QTreeWidget, QTreeWidgetItem)
from PySide6.QtCore import Signal, Qt, QSize, QEvent
from PySide6.QtGui import QIcon, QFont, QColor
import json
import os
import logging
import shutil
import uuid
from datetime import datetime
from src.core.services.auth_service import AuthService
from src.core.services.sync_service import SyncService
from src.ui.widgets.admin_dashboard import AdminDashboard
from src.ui.widgets.central_controle import CentralControle
from src.ui.widgets.dashboard_components import BreadcrumbWidget, MetricCard, DocumentItemWidget, DocumentationListWidget
from src.ui.components.project_cards import ProjectCard
from src.ui.dialogs.project_details_dialog import ProjectDetailsDialog
from src.ui.dialogs.document_upload_dialog import DocumentUploadDialog
from src.core.storage.project_storage import ProjectStorageManager

class ProjectManager(QWidget):
    project_selected = Signal(str, str, str)  # id, name, dxf_path
    project_created_globally = Signal(str, str, str) # work_name, project_name, project_id
    obra_created_globally = Signal(str) # work_name
    sync_complete_signal = Signal(bool, str) # success, project_id
    request_tab_switch = Signal(int) # index of tab to switch to

    # Estrutura de dados das 8 fases do pipeline
    # Estrutura de dados das 8 fases do pipeline - Agora espelhada do Storage
    PHASE_CLASSES = ProjectStorageManager.PHASE_CLASSES

    PHASE_DESCRIPTIONS = {
        1: "Entrada: 'Estrutural Bruto' (Recebido via E-mail). Contém: PDF misturado, plantas baixas, cortes, detalhamentos diversos.\n\nProcesso: Separação de documentos e Compreensão Semântica.\n\nSaída: Documentos classificados e separados por tipo.",
        2: "Entrada: Documentos classificados da Fase 1.\n\nProcesso: Higienização de ruídos (elementos não desejados) para facilitar a leitura da máquina.\n\nSaída: Estruturais Pavimentos Limpos e Detalhamentos Específicos (Nível, Pilar, Cortes) vinculados ao estrutural.",
        3: "Entrada: Estruturais Pavimentos Limpos. Processo de Inteligência e Extração dos Dados Técnicos de Engenharia.\n\nProcesso: Interpretação dos 'insights' de engenharia e cruzamento de dados.\n\nSaída: JSON Mestre. Uma lista estruturada vinculada ao pavimento.",
        4: "Entrada: JSON Mestre da Fase 3.\n\nProcesso: Sincronização dos dados com os Robôs de Detalhamento.\n\nSaída (4 Fluxos Paralelos): Dados populados prontos para geração de scripts.",
        5: "Entrada: Dados sincronizados da Fase 4.\n\nProcesso: Compilação e geração dos códigos-fonte (Scripts .SCR) para AutoCAD.\n\nSaída: Arquivos de comando individuais para desenho automático.",
        6: "Entrada: Arquivos de Script (.SCR).\n\nProcesso: Execução automática no motor CAD e conversão para geometria vetorial isolada.\n\nSaída: Arquivos .DXF individuais por elemento.",
        7: "Entrada: Milhares de arquivos DXF isolados.\n\nProcesso: Unificação lógica e espacial dos elementos no desenho final do pavimento.\n\nSaída: Desenho Completo do Pavimento montado.",
        8: "Entrada: Desenho Unificado.\n\nProcesso: Revisão automática de sobreposições, retoques finais e validação técnica.\n\nSaída: Pacote Final de Entrega validado."
    }

    def __init__(self, db_manager, memory_manager=None, auth_service=None):
        super().__init__()
        self.db = db_manager
        self.memory = memory_manager
        self.auth_service = auth_service
        # Estabilizar diretório base a partir do banco de dados (Garante encontrar os robôs)
        self.base_dir = os.path.dirname(os.path.abspath(self.db.db_path))
        logging.info(f"[ProjectManager] Diretório base estabilizado: {self.base_dir}")
        self.storage_manager = ProjectStorageManager(self.base_dir)
        self.sync_service = SyncService()
        self.current_project_id = None
        self.current_work_name = None
        self.sync_complete_signal.connect(self._on_sync_complete)
        
        # Window Setup
        self.setWindowTitle("Gerenciador de Projetos - Vision AI")
        self.resize(1400, 900)
        self.setWindowFlags(Qt.Window)
        self.setWindowState(Qt.WindowMaximized)
        
        self.apply_styles()
        self.setup_ui()
        self.load_works_combo()
        self.load_projects()

    def apply_styles(self):
        # Current app styles + specific premium project styles
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            }
            QPushButton#PrimaryButton {
                background-color: #00d4ff;
                color: #000;
                font-weight: bold;
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
            }
            QPushButton#PrimaryButton:hover { background-color: #00b8e6; }
            
            QTableWidget {
                background-color: #1e1e1e;
                border: 1px solid #333;
                gridline-color: #2a2a2a;
                font-size: 13px;
                border-radius: 8px;
            }
            QTableWidget::item { padding: 8px; }
            QHeaderView::section {
                background-color: #252528;
                color: #888;
                padding: 8px;
                border: none;
                font-weight: bold;
                text-transform: uppercase;
                font-size: 10px;
            }
        """)

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 1. Top Bar Premium
        self.top_bar = QFrame()
        self.top_bar.setFixedHeight(60)
        self.top_bar.setObjectName("TopBar")
        self.top_bar.setStyleSheet("""
            #TopBar { 
                background-color: #1a1a1a; 
                border-bottom: 2px solid #2d2d2d; 
            }
        """)
        
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(20, 0, 20, 0)
        
        logo_lbl = QLabel("VISION AI")
        logo_lbl.setStyleSheet("font-weight: bold; font-size: 18px; color: #00d4ff;")
        top_layout.addWidget(logo_lbl)
        
        top_layout.addSpacing(30)
        self.breadcrumbs = BreadcrumbWidget()
        top_layout.addWidget(self.breadcrumbs)
        
        top_layout.addStretch()
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar obras ou projetos...")
        self.search_box.setFixedWidth(250)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: #252528;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 6px 12px;
                color: #fff;
            }
            QLineEdit:focus { border-color: #00d4ff; }
        """)
        top_layout.addWidget(self.search_box)
        
        self.user_btn = QPushButton("ADMIN")
        self.user_btn.setStyleSheet("""
            QPushButton {
                background: #333;
                border-radius: 15px;
                padding: 0 15px;
                height: 30px;
                color: #aaa;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        top_layout.addWidget(self.user_btn)
        
        self.layout.addWidget(self.top_bar)

        # 2. Main Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("ProjectTabs")
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #1a1a1a; }
            QTabBar::tab {
                background: transparent;
                color: #666;
                padding: 12px 25px;
                font-weight: bold;
                font-size: 13px;
                border-bottom: 3px solid transparent;
            }
            QTabBar::tab:selected {
                color: #00d4ff;
                border-bottom: 3px solid #00d4ff;
            }
        """)
        
        self.local_tab = QWidget()
        self.setup_local_tab()
        self.tabs.addTab(self.local_tab, "MEUS PROJETOS")
        
        auth = AuthService()
        user = auth.get_current_user()
        is_admin = user and (user.role == 'admin' or user.email == 'thierry.tasf@gmail.com')
        
        if is_admin:
            self.community_tab = QWidget()
            self.setup_community_tab()
            self.tabs.addTab(self.community_tab, "🛡️ CURADORIA (ADMIN)")
            
            # 3. CENTRAL DE CONTROLE (Admin)
            self.central_tab = CentralControle(self.db, self.memory, self.auth_service)
            self.tabs.addTab(self.central_tab, "CENTRAL DE CONTROLE (Admin)")
            
        self.layout.addWidget(self.tabs)

    def setup_local_tab(self):
        layout = QHBoxLayout(self.local_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.local_splitter = QSplitter(Qt.Horizontal)
        self.local_splitter.setHandleWidth(1)
        self.local_splitter.setStyleSheet("QSplitter::handle { background: #2d2d2d; }")
        
        # --- SIDEBAR: OBRAS ---
        self.works_sidebar = QFrame()
        self.works_sidebar.setFixedWidth(280)
        self.works_sidebar.setObjectName("WorksSidebar")
        self.works_sidebar.setStyleSheet("""
            #WorksSidebar {
                background-color: #1a1a1b;
                border-right: 1px solid #2d2d2d;
            }
        """)
        sidebar_layout = QVBoxLayout(self.works_sidebar)
        sidebar_layout.setContentsMargins(15, 20, 15, 20)
        sidebar_layout.setSpacing(15)

        sidebar_header = QHBoxLayout()
        sidebar_title = QLabel("MINHAS OBRAS")
        sidebar_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #555; letter-spacing: 1px;")
        sidebar_header.addWidget(sidebar_title)
        
        sidebar_header.addStretch()
        
        self.btn_refresh_works = QPushButton("🔄")
        self.btn_refresh_works.setToolTip("Atualizar Lista de Obras")
        self.btn_refresh_works.setFixedSize(24, 24)
        self.btn_refresh_works.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #555;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #00d4ff;
                background: #252528;
                border-radius: 4px;
            }
        """)
        self.btn_refresh_works.clicked.connect(self.load_works_combo)
        sidebar_header.addWidget(self.btn_refresh_works)
        
        sidebar_layout.addLayout(sidebar_header)

        # Busca Obras
        self.edit_search_works = QLineEdit()
        self.edit_search_works.setPlaceholderText("🔍 Filtrar obras...")
        self.edit_search_works.setStyleSheet("""
            QLineEdit {
                background: #252528;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11px;
            }
        """)
        self.edit_search_works.textChanged.connect(self._filter_works_list)
        sidebar_layout.addWidget(self.edit_search_works)

        # Lista de Obras
        self.list_works = QListWidget()
        self.list_works.setObjectName("WorksList")
        self.list_works.setStyleSheet("""
            #WorksList {
                background: transparent;
                border: none;
                outline: none;
            }
            #WorksList::item {
                padding: 10px;
                border-radius: 6px;
                color: #aaa;
                margin-bottom: 2px;
            }
            #WorksList::item:selected {
                background-color: #2a2a2d;
                color: #00d4ff;
                font-weight: bold;
            }
            #WorksList::item:hover:!selected {
                background-color: #222225;
                color: #fff;
            }
        """)
        self.list_works.currentItemChanged.connect(self.load_projects)
        sidebar_layout.addWidget(self.list_works)

        # Botão + Obra na base da sidebar
        btn_add_work_sidebar = QPushButton("+ Criar Nova Obra")
        btn_add_work_sidebar.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px dashed #444;
                border-radius: 6px;
                color: #00d4ff;
                font-weight: bold;
                padding: 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #222;
                border-color: #00d4ff;
            }
        """)
        btn_add_work_sidebar.clicked.connect(self.add_work)
        sidebar_layout.addWidget(btn_add_work_sidebar)

        self.local_splitter.addWidget(self.works_sidebar)
        
        # --- CENTRAL AREA ---
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(25, 25, 25, 25)
        
        # --- HEADER (Agora mais limpo) ---
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(0, 0, 0, 15)
        
        # No lugar do combo, colocamos o nome da obra selecionada em destaque
        self.lbl_selected_work = QLabel("Selecione uma Obra")
        self.lbl_selected_work.setStyleSheet("font-size: 18px; font-weight: bold; color: #fff;")
        self.header_layout.addWidget(self.lbl_selected_work)
        
        self.header_layout.addStretch()
        
        # Botão de Remover Obra (inicialmente escondido)
        self.btn_delete_work = QPushButton("Remover Obra")
        self.btn_delete_work.setStyleSheet("""
            QPushButton { 
                background: #3a1c1c; 
                color: #ff6b6b; 
                border: 1px solid #ff4444; 
                border-radius: 4px; 
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background: #ff4444; color: white; }
        """)
        self.btn_delete_work.clicked.connect(self.delete_current_work)
        self.btn_delete_work.setVisible(False)
        self.btn_delete_work.setVisible(False)
        self.header_layout.addWidget(self.btn_delete_work)
        
        # Botão Sync Obra Completa
        self.btn_sync_work = QPushButton("Sincronizar Obra")
        self.btn_sync_work.setStyleSheet("""
            QPushButton {
                background: #1a324b;
                color: #00d4ff;
                border: 1px solid #00d4ff;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
                margin-left: 10px;
            }
            QPushButton:hover { background: #00d4ff; color: #000; }
        """)
        self.btn_sync_work.clicked.connect(self.sync_current_work)
        self.btn_sync_work.setVisible(False)
        self.header_layout.addWidget(self.btn_sync_work)

        self.header_layout.addStretch()
        
        self.btn_new_project = QPushButton("Novo Pavimento")
        self.btn_new_project.setObjectName("PrimaryButton")
        self.btn_new_project.clicked.connect(self.create_new_project)
        self.header_layout.addWidget(self.btn_new_project)
        
        central_layout.addLayout(self.header_layout)
        
        # Título da seção de documentos abaixo do nome da obra
        self.lbl_documents_title = QLabel("DOCUMENTOS")
        self.lbl_documents_title.setStyleSheet("""
            font-size: 24px; 
            font-weight: bold; 
            color: #00d4ff; 
            margin-top: 10px;
            margin-bottom: 5px;
            letter-spacing: 2px;
        """)
        central_layout.addWidget(self.lbl_documents_title)

        # Container para o fluxo de fases (antigo sub_tabs, mas agora tratado como corpo principal)
        # Mantendo o QTabWidget para as 8 fases, mas agora ele é o foco principal
        self.phase_tabs = QTabWidget()
        self.phase_tabs.setObjectName("PhaseTabs")
        self.phase_tabs.setStyleSheet("""
            QTabWidget::pane { 
                border: 1px solid #333; 
                background: #1a1a1a; 
                border-radius: 8px;
            }
            QTabBar::tab { 
                background: #252525; 
                color: #888; 
                padding: 12px 25px; 
                border: 1px solid #333; 
                border-bottom: none;
                margin-right: 2px;
                font-weight: bold;
                font-size: 11px;
            }
            QTabBar::tab:selected { 
                background: #1a1a1a; 
                color: #00d4ff; 
                border-bottom: 3px solid #00d4ff;
            }
            QTabBar::tab:hover:!selected {
                background: #2a2a2a;
                color: #aaa;
            }
        """)

        # Criar as 8 abas de fases (isso será movido daqui do loop para um método)
        self.phase_tab_widgets = {}
        for phase_num in range(1, 9):
            phase_tab = self._create_phase_tab(phase_num)
            phase_name = self._get_phase_name(phase_num)
            self.phase_tabs.addTab(phase_tab, f"{phase_num}. {phase_name}")
            self.phase_tab_widgets[phase_num] = phase_tab
            
        self.phase_tabs.setCurrentIndex(0) # Iniciar na Ingestão
        central_layout.addWidget(self.phase_tabs)
        self.local_splitter.addWidget(central_widget)
        
        self.local_splitter.setSizes([280, 1]) # Proporções [Sidebar, Central]
        layout.addWidget(self.local_splitter)

    def setup_pavimentos_container(self, parent_layout):
        """Prepara o container de pavimentos para ser inserido na Fase 2."""
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: 1px solid #333; background: #151515; border-radius: 8px; min-height: 400px; }
            QScrollBar:vertical {
                border: none; background: #1a1a1a; width: 8px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #333; min-height: 20px; border-radius: 4px;
            }
        """)
        
        self.cards_container = QWidget()
        self.cards_container.setObjectName("CardsContainer")
        self.cards_container.setStyleSheet("#CardsContainer { background: transparent; }")
        
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setSpacing(20)
        self.cards_layout.setContentsMargins(20, 20, 20, 20)
        self.cards_layout.setAlignment(Qt.AlignTop)
        
        self.scroll_area.setWidget(self.cards_container)
        parent_layout.addWidget(self.scroll_area)

    def setup_pavement_selector_combo(self, parent_layout, phase_num=3):
        """Prepara o seletor de pavimento (ComboBox) para a Fase 3, 4 ou 5."""
        container = QFrame()
        container.setStyleSheet("background: #1e1e1e; border: 1px solid #333; border-radius: 6px; padding: 10px;")
        layout = QHBoxLayout(container)
        
        phase_map = {3: 'INTERPRETAÇÃO/EXTRAÇÃO', 4: 'DADOS SYNC ROBOS', 5: 'SCRIPTS ROBOS SRC'}
        proc_text = phase_map.get(phase_num, 'PROCESSO')
        
        lbl = QLabel(f"📍 SELECIONE O PAVIMENTO PARA {proc_text}:")
        lbl.setStyleSheet("color: #00d4ff; font-weight: bold; font-size: 11px;")
        layout.addWidget(lbl)
        
        cmb = QComboBox()
        cmb.setStyleSheet("""
            QComboBox {
                background: #252528; border: 1px solid #333; border-radius: 4px;
                padding: 8px; color: #fff; font-size: 12px; min-width: 250px;
            }
            QComboBox:focus { border: 1px solid #00d4ff; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; border: none; }
        """)
        cmb.currentIndexChanged.connect(self._on_pavement_combo_changed)
        layout.addWidget(cmb)
        
        # Se for Fase 5, adicionar barra de progresso de scripts
        if phase_num == 5:
            layout.addSpacing(30)
            progress_container = QWidget()
            prog_layout = QVBoxLayout(progress_container)
            prog_layout.setContentsMargins(0, 0, 0, 0)
            prog_layout.setSpacing(2)
            
            lbl_prog = QLabel("📊 PROGRESSO DE SCRIPTS:")
            lbl_prog.setStyleSheet("color: #aaa; font-size: 9px; font-weight: bold;")
            prog_layout.addWidget(lbl_prog)
            
            self.progress_scripts = QProgressBar()
            self.progress_scripts.setFixedHeight(12)
            self.progress_scripts.setStyleSheet("""
                QProgressBar {
                    background: #111; border: 1px solid #333; border-radius: 6px;
                    text-align: center; color: transparent;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d4ff, stop:1 #00ffaa);
                    border-radius: 5px;
                }
            """)
            self.progress_scripts.setValue(0)
            prog_layout.addWidget(self.progress_scripts)
            layout.addWidget(progress_container)
            self.phase5_progress_bar = self.progress_scripts
            self.phase5_progress_label = lbl_prog

        layout.addStretch()
        
        parent_layout.addWidget(container)
        
        if phase_num == 3:
            self.cmb_pavements_extraction = cmb
            self.phase3_pavement_selector = container
        elif phase_num == 4:
            self.cmb_pavements_recognition = cmb
            self.phase4_pavement_selector = container
        elif phase_num == 5:
            self.cmb_pavements_validation = cmb
            self.phase5_pavement_selector = container

    def _on_pavement_combo_changed(self, index):
        """Handler para mudança de pavimento no combo da Fase 3, 4 ou 5."""
        if index < 0: return
        sender = self.sender()
        p_data = sender.itemData(index)
        if p_data and p_data.get('id') != self.current_project_id:
            # Seleciona o projeto
            self.on_project_card_clicked(p_data)
        
        # Disparar refresh das listas
        if sender == getattr(self, 'cmb_pavements_extraction', None):
            self._refresh_phase_tabs()
        elif sender == getattr(self, 'cmb_pavements_recognition', None):
            self._refresh_all_phase4_lists()
        elif sender == getattr(self, 'cmb_pavements_validation', None):
            self._refresh_all_phase5_lists()

    def setup_specs_container(self, parent_layout):
        """Prepara o formulário de especificações para ser inserido na Fase 1."""
        container = QFrame()
        container.setStyleSheet("background: #1e1e1e; border: 1px solid #333; border-radius: 8px;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("📝 ESPECIFICAÇÕES TÉCNICAS DA OBRA")
        title.setStyleSheet("color: #00d4ff; font-weight: bold; font-size: 14px; border: none; background: transparent;")
        layout.addWidget(title)

        # 1. Nome da Obra (Full Row)
        self.f_work_name = QLineEdit()
        self.f_work_name.setPlaceholderText("Nome da Obra")
        layout.addWidget(self._create_field_widget("🏢 NOME DA OBRA:", self.f_work_name))

        # 2. Metrics Grid (2 Rows x 3 Cols)
        grid = QGridLayout()
        grid.setSpacing(15)
        
        self.f_pavements = QLineEdit()
        self.f_pavements.setPlaceholderText("Ex: 15")
        grid.addWidget(self._create_field_widget("🏗️ PAVIMENTOS:", self.f_pavements), 0, 0)
        
        self.f_towers = QLineEdit()
        self.f_towers.setPlaceholderText("Ex: 2")
        grid.addWidget(self._create_field_widget("🏢 TORRES:", self.f_towers), 0, 1)

        self.f_pilares = QLineEdit()
        self.f_pilares.setPlaceholderText("Total estimado")
        grid.addWidget(self._create_field_widget("🟦 PILARES:", self.f_pilares), 0, 2)
        
        self.f_vigas = QLineEdit()
        self.f_vigas.setPlaceholderText("Total estimado")
        grid.addWidget(self._create_field_widget("🟩 VIGAS:", self.f_vigas), 1, 0)
        
        self.f_lajes = QLineEdit()
        self.f_lajes.setPlaceholderText("Total estimado")
        grid.addWidget(self._create_field_widget("🟪 LAJES:", self.f_lajes), 1, 1)

        # Empty cell at 1, 2 stays empty
        
        layout.addLayout(grid)
        
        # 3. Observations (Smaller)
        layout.addWidget(QLabel("📝 OBSERVAÇÕES E NOTAS TÉCNICAS:"))
        self.txt_specs = QTextEdit()
        self.txt_specs.setPlaceholderText("Especifique detalhes técnicos da obra aqui...")
        self.txt_specs.setStyleSheet("""
            QTextEdit {
                background: #1a1a1b; border: 1px solid #333; border-radius: 6px;
                color: #ccc; padding: 10px; font-size: 12px; min-height: 50px; max-height: 80px;
            }
        """)
        layout.addWidget(self.txt_specs)
        
        self.btn_save_work_specs = QPushButton("💾 SALVAR ESPECIFICAÇÕES")
        self.btn_save_work_specs.setCursor(Qt.PointingHandCursor)
        self.btn_save_work_specs.setFixedHeight(40)
        self.btn_save_work_specs.setStyleSheet("""
            QPushButton {
                background-color: #00d4ff; color: #000; font-weight: bold;
                border-radius: 6px; font-size: 11px;
            }
            QPushButton:hover { background-color: #00b8e6; }
        """)
        self.btn_save_work_specs.clicked.connect(self.save_work_metadata)
        layout.addWidget(self.btn_save_work_specs)
        
        parent_layout.addWidget(container)

    def _create_field_widget(self, label_text, widget):
        """Helper para criar um bloco Label + Input verticalmente ou horizontalmente."""
        # Se quiser "dentro dele normalmente", talvez Vertical seja melhor para campos estreitos.
        # Mas o usuário disse "os campos 2 linhas de 3 colunas", o que implica que eles tem espaço.
        # Vamos usar QVBoxLayout para garantir que o label fique acima do input, economizando largura.
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #888; font-weight: bold; font-size: 10px; border: none;")
        layout.addWidget(lbl)
        
        widget.setStyleSheet("""
            QLineEdit {
                background: #252528; border: 1px solid #333; border-radius: 4px;
                padding: 8px; color: #fff; font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid #00d4ff; }
        """)
        layout.addWidget(widget)
        
        return container

    def load_work_metadata(self, work_name):
        """Carrega os dados técnicos da obra no formulário."""
        if not work_name or work_name == "__NO_WORK__":
            # Limpar formulário
            self.f_work_name.setText("")
            self.f_pavements.setText("")
            self.f_towers.setText("")
            self.f_pilares.setText("")
            self.f_vigas.setText("")
            self.f_lajes.setText("")
            self.txt_specs.setText("")
            self.btn_save_work_specs.setEnabled(False)
            return

        self.btn_save_work_specs.setEnabled(True)
        data = self.db.get_work_data(work_name)
        if data:
            self.f_work_name.setText(str(data.get('name') or ""))
            self.f_pavements.setText(str(data.get('num_pavements') or ""))
            self.f_towers.setText(str(data.get('num_towers') or ""))
            self.f_pilares.setText(str(data.get('total_pilares') or ""))
            self.f_vigas.setText(str(data.get('total_vigas') or ""))
            self.f_lajes.setText(str(data.get('total_lajes') or ""))
            self.txt_specs.setText(str(data.get('technical_specs') or ""))
        else:
            # Se a obra existe mas não tem dados extra
            self.f_work_name.setText(work_name)
            self.f_pavements.setText("")
            self.f_towers.setText("")
            self.f_pilares.setText("")
            self.f_vigas.setText("")
            self.f_lajes.setText("")
            self.txt_specs.setText("")

    def save_work_metadata(self):
        """Salva as alterações do formulário de obra."""
        selected_item = self.list_works.currentItem()
        if not selected_item: return
        old_name = selected_item.data(Qt.UserRole)
        new_name = self.f_work_name.text().strip()
        
        if not new_name:
            QMessageBox.warning(self, "Aviso", "O nome da obra não pode ser vazio.")
            return

        try:
            # 1. Se mudou o nome, renomear (isso atualiza v_projects também no DB)
            if new_name != old_name and old_name != "__NO_WORK__":
                self.db.rename_work(old_name, new_name)
                # Atualizar item na lista
                selected_item.setText(f"📁 {new_name}")
                selected_item.setData(Qt.UserRole, new_name)
            
            # 2. Salvar metadados técnicos
            def _to_int(val):
                try: return int(val) if val else 0
                except: return 0

            meta = {
                "num_pavements": _to_int(self.f_pavements.text()),
                "num_towers": _to_int(self.f_towers.text()),
                "total_pilares": _to_int(self.f_pilares.text()),
                "total_vigas": _to_int(self.f_vigas.text()),
                "total_lajes": _to_int(self.f_lajes.text()),
                "technical_specs": self.txt_specs.toPlainText()
            }
            self.db.update_work_metadata(new_name, meta)
            
            QMessageBox.information(self, "Sucesso", "Especificações da obra salvas com sucesso!")
            self.load_projects() # Para atualizar o header se mudou nome
            
        except Exception as e:
            logging.error(f"Erro ao salvar specs da obra: {e}")
            QMessageBox.critical(self, "Erro", f"Falha ao salvar: {e}")
        
        btn_save_specs = QPushButton("Salvar Alterações")
        btn_save_specs.setStyleSheet("""
            QPushButton {
                background: #2a2a2d;
                color: #00d4ff;
                border: 1px solid #00d4ff;
                border-radius: 4px;
                padding: 8px 15px;
                font-size: 11px;
                margin-top: 10px;
            }
            QPushButton:hover { background: #00d4ff; color: #000; }
        """)
        btn_save_specs.clicked.connect(self.save_project_specs)
        layout.addWidget(btn_save_specs, 0, Qt.AlignRight)
        layout.addStretch()


    def _get_phase_name(self, phase_num):
        """Retorna o nome da fase."""
        names = {
            1: "1. INGESTÃO",
            2: "2. TRIAGEM",
            3: "3. INTERPRETACAO/EXTRACAO",
            4: "4. DADOS SYNC ROBOS",
            5: "5. SCRIPTS ROBOS SRC",
            6: "6. CONVERSAO SCRIPTS DXF",
            7: "7. UNIFICACAO DXF PAVIMENTO",
            8: "8. RETOQUES E REVISAO"
        }
        return names.get(phase_num, f"FASE {phase_num}")

    def _create_phase_tab(self, phase_num):
        """Cria uma aba de fase com descrição e classes de itens."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Injetar Especificações Técnicas na Fase 1
        if phase_num == 1:
            self.setup_specs_container(layout)
            layout.addSpacing(10)

        # Descrição da fase
        desc_label = QLabel(self.PHASE_DESCRIPTIONS.get(phase_num, ""))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("""
            QLabel {
                color: #aaa; font-size: 12px; padding: 15px;
                background: #1e1e1e; border: 1px solid #333; border-radius: 6px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(desc_label)

        # Injetar o ComboBox de seleção GLOBAL no topo da Fase 4 e 5
        if phase_num in [4, 5]:
            self.setup_pavement_selector_combo(layout, phase_num=phase_num)
            layout.addSpacing(10)
        
        # Classes de itens desta fase
        classes = self.PHASE_CLASSES.get(phase_num, [])
        for class_name in classes:
            class_widget = self._create_class_widget(phase_num, class_name)
            layout.addWidget(class_widget)
            
            # Injetar a grade de pavimentos na Fase 2 (TRIAGEM), classe Estruturais Pavimentos Limpos
            if phase_num == 2 and class_name == "Estruturais Pavimentos Limpos":
                # Adicionar container de pavimentos dentro do frame da classe para ficar contextualizado
                docs_container = class_widget.property("docs_container")
                if docs_container:
                    self.setup_pavimentos_container(docs_container.layout())
            
            # Injetar o ComboBox de seleção na Fase 3 (EXTRAÇÃO), classe Estruturais Pavimentos Limpos
            if phase_num == 3 and class_name == "Estruturais Pavimentos Limpos":
                docs_container = class_widget.property("docs_container")
                if docs_container:
                    self.setup_pavement_selector_combo(docs_container.layout(), phase_num=3)
        
        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _create_class_widget(self, phase_num, class_name):
        """Cria um widget para uma classe de itens com lista de documentos e botões de ação."""
        class_frame = QFrame()
        class_frame.setStyleSheet("""
            QFrame {
                background: #1e1e1e;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 0px;
            }
        """)
        
        class_layout = QVBoxLayout(class_frame)
        class_layout.setContentsMargins(15, 15, 15, 15)
        class_layout.setSpacing(10)
        
        # Header da classe com botões de ação
        header_layout = QHBoxLayout()
        
        class_title = QLabel(class_name)
        class_title.setStyleSheet("""
            QLabel {
                color: #00d4ff;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        header_layout.addWidget(class_title)
        header_layout.addStretch()
        
        # Botão Adicionar Documento
        btn_add = QPushButton("+ Adicionar")
        btn_add.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #00d4ff;
                border: 1px solid #00d4ff;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #00d4ff;
                color: #000;
            }
        """)
        btn_add.clicked.connect(lambda: self._add_document_to_class(phase_num, class_name))
        header_layout.addWidget(btn_add)
        
        # Na Fase 3, 4 e 5, para as classes com combo ou geradas automaticamente, escondemos o botão adicionar
        # Na Fase 3, NENHUMA classe tem botão adicionar manual
        if phase_num == 3 or \
           (phase_num == 4 and "JSON" in class_name) or \
           (phase_num == 5 and "Scripts" in class_name):
            btn_add.hide()
        
        class_layout.addLayout(header_layout)
        
        # Widget container para documentos (será populado dinamicamente)
        docs_container = QWidget()
        docs_container_layout = QVBoxLayout(docs_container)
        docs_container_layout.setContentsMargins(0, 0, 0, 0)
        docs_container_layout.setSpacing(5)
        
        # Armazenar referência ao layout para atualização
        class_frame.setProperty("phase_num", phase_num)
        class_frame.setProperty("class_name", class_name)
        class_frame.setProperty("docs_container", docs_container)
        
        class_layout.addWidget(docs_container)
        
        # --- PHASE 3, 4 & 5 LOGIC (DB ITEMS) ---
        is_phase3_db_class = phase_num == 3 and class_name in ["Pilares", "Vigas", "Lajes"]
        is_phase4_db_class = phase_num == 4 and class_name in ["JSON Pilares", "JSON Lajes", "JSON Vigas Laterais", "JSON Vigas Fundo"]
        is_phase5_db_class = phase_num == 5 and class_name in ["Scripts Pilares", "Scripts Lajes", "Scripts Vigas Laterais", "Scripts Vigas Fundo"]
        
        if is_phase3_db_class or is_phase4_db_class or is_phase5_db_class:
            # Container Lista DB
            db_list_container = QWidget()
            db_layout = QVBoxLayout(db_list_container)
            db_layout.setContentsMargins(0, 10, 0, 0)
            
            lbl_db = QLabel(f"🔢 {class_name} (Dados Vinculados)")
            lbl_db.setStyleSheet("color: #00d4ff; font-weight: bold; font-size: 11px;")
            db_layout.addWidget(lbl_db)
            
            # Tree Widget parecido com o do main.py
            tree = QTreeWidget()
            
            if class_name == "Scripts Pilares":
                tree.setHeaderLabels(["Item", "Nome", "Cima", "Grades", "ABCD", "Ação"])
                tree.setColumnWidth(0, 60)
                tree.setColumnWidth(1, 150)
                tree.setColumnWidth(2, 60)  # Cima
                tree.setColumnWidth(3, 60)  # Grades
                tree.setColumnWidth(4, 60)  # ABCD
            else:
                tree.setHeaderLabels(["Item", "Nome", "Status", "Ação"])
                tree.setColumnWidth(0, 60)
                tree.setColumnWidth(1, 150)
                tree.setColumnWidth(2, 80)
            
            tree.setStyleSheet("QTreeWidget { background: #151515; border: 1px solid #333; }")
            tree.setMinimumHeight(200)
            db_layout.addWidget(tree)
            
            class_layout.addWidget(db_list_container)
            
            # Salvar referencia na classe para popular depois
            class_frame.setProperty("db_tree", tree)
            
            # Botão de Refresh Específico
            btn_refresh = QPushButton("🔄 Atualizar")
            btn_refresh.setCursor(Qt.PointingHandCursor)
            btn_refresh.setStyleSheet("background: transparent; color: #888; border: none; font-size: 10px;")
            if phase_num == 3:
                btn_refresh.clicked.connect(lambda checked=False, cn=class_name, t=tree: self._refresh_phase3_data(cn, t))
            elif phase_num == 5:
                # Na fase 5, chame o refresh específico de scripts
                btn_refresh.clicked.connect(lambda checked=False, cn=class_name, t=tree: self._refresh_phase5_data(cn, t))
            else:
                btn_refresh.clicked.connect(lambda checked=False, cn=class_name, t=tree: self._refresh_phase4_data(cn, t))
            header_layout.addWidget(btn_refresh)
            
            # Botão Sincronizar Robô (Removido conforme solicitado - apenas listar dados)
            # if phase_num == 4:
            #     ...

        return class_frame

    def _refresh_phase3_data(self, class_name, tree_widget):
        """Carrega dados do SQLite para a lista"""
        if not self.current_project_id: return
        
        tree_widget.clear()
        items = []
        
        try:
            if "Pilar" in class_name:
                items = self.db.load_pillars(self.current_project_id)
            elif "Viga" in class_name:
                items = self.db.load_beams(self.current_project_id)
            elif "Laje" in class_name:
                items = self.db.load_slabs(self.current_project_id)
        except Exception as e:
            print(f"[Phase3] ❌ Erro ao carregar itens do banco para {class_name}: {e}")
            return

        if not items:
            print(f"[Phase3] ℹ️ Nenhum item do tipo {class_name} encontrado para projeto {self.current_project_id}")
            return

        print(f"[Phase3] 🔄 Populando {len(items)} itens em {class_name} (Projeto: {self.current_project_id})")

        # Ordenar
        import re
        def nat_key(x):
            name = str(x.get('name', x.get('nome', '')))
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]
        items.sort(key=nat_key)

        for i, item_data in enumerate(items):
            item_id = item_data.get('id_item', f"{i+1:02}")
            name = item_data.get('name', '?')
            status = "Validado" if item_data.get('is_validated') else "Pendente"
            
            tree_item = QTreeWidgetItem(tree_widget)
            tree_item.setText(0, item_id)
            tree_item.setText(1, name)
            tree_item.setText(2, status)
            
            if item_data.get('is_validated'):
                tree_item.setForeground(2, Qt.green)
            else:
                tree_item.setForeground(2, QColor("#ffd600"))
                
            # Botão Detalhes
            btn = QPushButton("Ver Detalhes")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("background: #333; color: white; border-radius: 4px; padding: 2px; font-size: 10px;")
            # Usar closure seguro
            btn.clicked.connect(lambda checked=False, d=item_data: self._open_detail_dialog(d))
            tree_widget.setItemWidget(tree_item, 3, btn)

    def _open_detail_dialog(self, item_data):
        from src.ui.dialogs.detail_dialog import DetailDialog
        # Abrir em modo leitura/edição (direto no objeto, mas sem redesenho de canvas pois nao tem canvas aqui)
        # Se salvar, o objeto é atualizado na mem. Precisa salvar no DB?
        # O DetailDialog atual edita o dict.
        # Precisamos de um botão "Salvar" no dialog se aberto daqui.
        # Ou instruir o usuário que aqui é visualização.
        
        dlg = DetailDialog(item_data, parent=self)
        dlg.exec_()
        
        # Opcional: Salvar no DB se houve alteração (DetailCard edita in-place)
        # Como DetailDialog não tem botão salvar explicito ainda (eu removi/ocultei), 
        # assumimos visualização ou auto-save se implementado.
        # O usuário pediu: "sempre ja estarao visiveis e carregadas".
        # Vamos assumir save-on-close ou read-only por segurança nesta etapa, 
        # mas se editar, deveria persistir.
        
        # Save back to DB to be safe if edited
        if "type" in item_data:
            t = item_data["type"].lower()
            if "pilar" in t: self.db.save_pillar(item_data, self.current_project_id)
            elif "laje" in t: self.db.save_slab(item_data, self.current_project_id)

    def _refresh_all_phase4_lists(self):
        """Atualiza todas as listas de dados de robôs na Fase 4."""
        phase_tab = self.phase_tab_widgets.get(4)
        if not phase_tab: return
        
        container = phase_tab.widget()
        if not container: return
        layout = container.layout()
        if not layout: return
        
        # Encontrar os frames de classe da Fase 4
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if widget:
                class_name = widget.property("class_name")
                tree = widget.property("db_tree")
                if class_name and tree:
                    self._refresh_phase4_data(class_name, tree)

    def _refresh_phase4_data(self, class_name, tree_widget):
        """Carrega dados para o reconhecimento (Fase 4). 
        Popula a lista com dados REAIS dos robôs para o pavimento selecionado."""
        if not self.current_project_id: return
        tree_widget.clear()
        
        # Pegar o pavimento selecionado no combo da fase 4
        pav_nome = ""
        # Tentar pegar do data do combo
        p_data = self.cmb_pavements_recognition.currentData()
        if isinstance(p_data, dict):
            pav_nome = p_data.get('name', p_data.get('pavement_name', ''))
            self.current_project_id = p_data.get('id')
        else:
            # Fallback robusto via texto (remove ícones/emojis)
            full_text = self.cmb_pavements_recognition.currentText()
            # Pega tudo após o primeiro espaço se houver emoji
            if " " in full_text:
                pav_nome = full_text.split(" ", 1)[-1].strip()
            else:
                pav_nome = full_text.strip()
        
        if not pav_nome:
            logging.info(f"[Phase4] ℹ️ Nome do pavimento vazio para {class_name}")
            return

        logging.info(f"[Phase4] 🔍 Buscando dados de '{class_name}' para o pavimento: '{pav_nome}'")
        
        items = []
        try:
            if "Pilares" in class_name:
                items = self._read_robot_pilares_data(pav_nome)
            elif "Lajes" in class_name:
                items = self._read_robot_lajes_data(pav_nome)
            elif "Laterais" in class_name:
                items = self._read_robot_laterais_data(pav_nome)
            elif "Fundo" in class_name:
                items = self._read_robot_fundos_data(pav_nome)
        except Exception as e:
            print(f"[Phase4] Erro ao ler dados do robô {class_name}: {e}")

        if not items:
            print(f"[Phase4] ℹ️ Nenhum dado encontrado para {class_name} ({pav_nome})")
            return

        print(f"[Phase4] ✅ Encontrados {len(items)} itens para {class_name}")

        # Ordenar itens
        import re
        def nat_key(x):
            name = str(x.get('nome', x.get('name', '')))
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]
        items.sort(key=nat_key)

        for i, item_data in enumerate(items):
            name = item_data.get('nome', item_data.get('name', f"Item {i+1}"))
            is_valid = item_data.get('is_validado', item_data.get('is_validated', False))
            status_val = "OK" if is_valid else "Proc."
            
            tree_item = QTreeWidgetItem(tree_widget)
            tree_item.setText(0, f"{i+1:02}")
            tree_item.setText(1, name)
            tree_item.setText(2, status_val)
            
            if is_valid:
                tree_item.setForeground(2, Qt.green)
            else:
                tree_item.setForeground(2, QColor("#00d4ff"))

            # Botão Detalhes com ficha específica do robô
            btn = QPushButton("Ver Ficha Robô")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("background: #004d73; color: white; border-radius: 4px; padding: 2px; font-size: 10px;")
            btn.clicked.connect(lambda checked=False, d=item_data: self._open_robot_ficha(d))
            tree_widget.setItemWidget(tree_item, 3, btn)

    def _open_robot_ficha(self, item_data):
        """Abre a ficha técnica específica do robô (Fase 4)."""
        from src.ui.dialogs.robot_ficha_dialog import RobotFichaDialog
        dlg = RobotFichaDialog(item_data, parent=self)
        dlg.exec_()

    def _read_robot_pilares_data(self, pav_nome):
        path = os.path.join(self.base_dir, "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25", "src", "core", "pilares_salvos.json")
        if not os.path.exists(path): 
            logging.warning(f"[Phase4] ❌ Arquivo não encontrado: {path}")
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            items = []
            target = pav_nome.upper()
            
            for key, val in data.items():
                # A chave costuma ser Obra_Pavimento_Nome
                if target in key.upper():
                    d = val.get('dados', val)
                    if isinstance(d, dict):
                        d["type"] = "Pilar (Robô)"
                        items.append(d)
            
            if items:
                logging.info(f"[Phase4] ✅ Encontrados {len(items)} pilares para '{pav_nome}'")
            return items
        except Exception as e: 
            logging.error(f"[Phase4] ❌ Erro ao ler pilares: {e}")
            return []

    def _read_robot_lajes_data(self, pav_nome):
        # Lajes salvam no projects_repo do projeto atual
        items = []
        seen_names = set()
        
        # Coletar todos os obras.json possíveis
        all_paths = []
        try:
            repo_base = os.path.join(self.base_dir, "projects_repo")
            if os.path.exists(repo_base):
                for p_id in os.listdir(repo_base):
                    p_path = os.path.join(repo_base, p_id, "laje_data", "obras.json")
                    if os.path.exists(p_path):
                        all_paths.append(p_path)
            logging.debug(f"[Phase4] 📂 Caminhos obras.json encontrados: {len(all_paths)}")
        except Exception as e: 
            logging.error(f"[Phase4] ❌ Erro ao listar diretórios de lajes: {e}")

        for p in all_paths:
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Busca recursiva por "pavimentos" e match flexível do pav_nome
                def search_pavs(curr_data):
                    if isinstance(curr_data, dict):
                        if "pavimentos" in curr_data:
                            for pav in curr_data["pavimentos"]:
                                p_nome = str(pav.get("nome", "")).upper()
                                target = pav_nome.upper()
                                if target in p_nome or p_nome in target:
                                    for laje in pav.get("lajes", []):
                                        name = laje.get('nome', laje.get('name'))
                                        if name and name not in seen_names:
                                            laje["type"] = "Laje (Robô)"
                                            items.append(laje)
                                            seen_names.add(name)
                        for v in curr_data.values():
                            search_pavs(v)
                    elif isinstance(curr_data, list):
                        for v in curr_data:
                            search_pavs(v)
                
                search_pavs(data)
            except: continue
        return items

    def _read_robot_laterais_data(self, pav_nome):
        path = os.path.join(self.base_dir, "_ROBOS_ABAS", "Robo_Laterais_de_Vigas", "dados_vigas_ultima_sessao.json")
        if not os.path.exists(path): 
            logging.warning(f"[Phase4] ❌ Arquivo não encontrado: {path}")
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            items = []
            target = pav_nome.upper()
            
            # A estrutura pode ser um dicionário de obras, que contém dicionários de pavimentos
            # ou uma lista de dicionários de vigas com 'pavimento' como chave.
            
            # Caso 1: Estrutura de dicionário aninhado (obra -> pavimento -> vigas)
            def scan_dict_recursive(current_dict):
                for key, value in current_dict.items():
                    if isinstance(value, dict):
                        # Check if key matches pavement name
                        if target in key.upper():
                            # Assume 'vigas' key contains the list of beam data
                            if 'vigas' in value and isinstance(value['vigas'], list):
                                for item in value['vigas']:
                                    if isinstance(item, dict):
                                        item["type"] = "Viga Lateral (Robô)"
                                        items.append(item)
                            # Also check if the dict itself contains beam data directly
                            elif 'nome' in value or 'name' in value: # Heuristic for beam data
                                value["type"] = "Viga Lateral (Robô)"
                                items.append(value)
                        scan_dict_recursive(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                # Check if list items are beam data or contain nested structures
                                if 'pavimento' in item and target in item['pavimento'].upper():
                                    item["type"] = "Viga Lateral (Robô)"
                                    items.append(item)
                                elif 'nome' in item or 'name' in item: # Heuristic for beam data
                                    item["type"] = "Viga Lateral (Robô)"
                                    items.append(item)
            
            if isinstance(data, dict):
                scan_dict_recursive(data)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'pavimento' in item and target in item['pavimento'].upper():
                        item["type"] = "Viga Lateral (Robô)"
                        items.append(item)
            
            if items:
                logging.info(f"[Phase4] ✅ Encontradas {len(items)} vigas laterais para '{pav_nome}'")
            return items
        except Exception as e: 
            logging.error(f"[Phase4] ❌ Erro ao ler vigas laterais: {e}")
            return []

    def _read_robot_fundos_data(self, pav_nome):
        path = os.path.join(self.base_dir, "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao", "fundos_salvos.json")
        if not os.path.exists(path): return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            items = []
            target = pav_nome.upper()
            seen = set()

            for obra_k, obra_v in data.items():
                if isinstance(obra_v, dict):
                    for pav_k, pav_v in obra_v.items():
                        if target in pav_k.upper():
                            if isinstance(pav_v, dict):
                                for vk, vv in pav_v.items():
                                    if isinstance(vv, dict):
                                        name = vv.get('nome', vv.get('name', vk))
                                        if name not in seen:
                                            vv["type"] = "Viga Fundo (Robô)"
                                            vv["name"] = name
                                            items.append(vv)
                                            seen.add(name)
                            elif isinstance(pav_v, list):
                                for d in pav_v:
                                    if isinstance(d, dict):
                                        name = d.get('nome', d.get('name', f"Viga {len(items)+1}"))
                                        if name not in seen:
                                            d["type"] = "Viga Fundo (Robô)"
                                            d["name"] = name
                                            items.append(d)
                                            seen.add(name)
            
            if items:
                logging.info(f"[Phase4] ✅ Encontrados {len(items)} fundos de vigas para '{pav_nome}'")
            return items
        except Exception as e:
            logging.error(f"[Phase4] ❌ Erro ao ler fundos de vigas: {e}")
            return []

    def _sync_project_from_robot(self, class_name, tree_widget):
        """Sincroniza os dados do robô (local) com o banco de dados central."""
        if not self.current_project_id: return
        
        project = self.db.get_project_by_id(self.current_project_id)
        if not project: return
        
        obra_nome = project.get('work_name')
        pav_nome = project.get('pavement_name') or project.get('name')
        
        if not obra_nome or not pav_nome:
            QMessageBox.warning(self, "Aviso", "O projeto deve ter Obra e Pavimento definidos para sincronizar.")
            return

        # Localizar o robô correto
        robot_json_path = ""
        if "Pilar" in class_name:
            robot_json_path = os.path.join(self.base_dir, "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25", "src", "core", "pilares_salvos.json")
        elif "Laje" in class_name:
            # Sincronização de Lajes
            found_count = 0
            robot_data_list = self._read_robot_lajes_data(pav_nome)
            for l_data in robot_data_list:
                self.db.save_slab(l_data, self.current_project_id)
                found_count += 1
            
            if found_count > 0:
                QMessageBox.information(self, "Sucesso", f"Sincronizadas {found_count} lajes do robô.")
                self._refresh_phase4_data(class_name, tree_widget)
            return

        elif "Laterais" in class_name:
            # Sincronização de Vigas Laterais
            found_count = 0
            robot_data_list = self._read_robot_laterais_data(pav_nome)
            for v_data in robot_data_list:
                # Garantir que o tipo está correto para o filtro posterior
                v_data['type'] = 'Lateral' 
                self.db.save_beam(v_data, self.current_project_id)
                found_count += 1
            
            if found_count > 0:
                QMessageBox.information(self, "Sucesso", f"Sincronizadas {found_count} vigas laterais do robô.")
                self._refresh_phase4_data(class_name, tree_widget)
            return

        elif "Fundo" in class_name:
            # Sincronização de Vigas de Fundo
            found_count = 0
            robot_data_list = self._read_robot_fundos_data(pav_nome)
            for v_data in robot_data_list:
                # Garantir que o tipo está correto para o filtro posterior
                v_data['type'] = 'Fundo'
                self.db.save_beam(v_data, self.current_project_id)
                found_count += 1
            
            if found_count > 0:
                QMessageBox.information(self, "Sucesso", f"Sincronizadas {found_count} vigas de fundo do robô.")
                self._refresh_phase4_data(class_name, tree_widget)
            return
        
        if not robot_json_path or not os.path.exists(robot_json_path):
            QMessageBox.information(self, "Informação", f"Arquivo do robô não encontrado em:\n{robot_json_path}")
            return
            
        try:
            with open(robot_json_path, 'r', encoding='utf-8') as f:
                robot_data = json.load(f)
            
            # Procurar itens deste pavimento (Formato: Obra_Pavimento_Nome ou similar)
            found_count = 0
            for key, val in robot_data.items():
                # No Robo_Pilares novo as chaves são Pavimento_Nome ou Obra_Pavimento_Nome
                if pav_nome in key:
                    pilar_data = val.get('dados', val) # Depende do robô
                    if pilar_data:
                        # Salvar no DB central
                        # Precisamos converter o formato do robô para o formato do DB se necessário
                        # Mas o DatabaseManager aceita dicts flexíveis em alguns pontos
                        self.db.save_pillar(pilar_data, self.current_project_id)
                        found_count += 1
            
            if found_count > 0:
                QMessageBox.information(self, "Sucesso", f"Sincronizados {found_count} itens do robô para este pavimento.")
                self._refresh_phase4_data(class_name, tree_widget)
            else:
                QMessageBox.information(self, "Informação", f"Nenhum dado encontrado para '{pav_nome}' no arquivo do robô.")
                
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro na sincronização: {e}")
            import traceback
            traceback.print_exc()



    def load_projects(self): # Override/Hook into existing load_projects logic
        # ... existing code ...
        # Preciso injetar o _load_phase3_initial após selecionar um projeto.
        # Mas load_projects carrega a grade de projetos.
        # Quando CLICA no projeto, aí sim carrega os dados.
        pass

    def _load_phase3_initial(self):
        """Carrega os dados iniciais da fase 3 após selecionar um projeto."""
        self._refresh_phase_tabs()

    def _on_project_card_clicked(self, p_id, p_name, dxf_path):
        """Ao entrar num projeto específico (chamado internamente)"""
        p_data = self.db.get_project_by_id(p_id)
        if p_data:
            self.on_project_card_clicked(p_data)

    def _classify_document(self, doc):
        """Classifica um documento em fase e classe baseado em nome, extensão ou valores persistidos."""
        # PRIORIDADE: Usar fase e categoria salvas no banco se existirem
        saved_phase = doc.get('phase')
        saved_cat = doc.get('category')
        if saved_phase and saved_cat:
            return (int(saved_phase), saved_cat)

        name = doc.get('name', '').lower()
        ext = doc.get('extension', '').lower()
        file_path = doc.get('file_path', '').lower()
        is_main = doc.get('is_main', False) or doc.get('id') == 'main_dxf'
        
        # Especial: Documento principal da obra sempre na fase 1, classe Estruturais Brutos
        if is_main:
            return (1, "Estruturais dos Pavimentos, Estado Bruto (.DXF)")

        # Fase 1: Ingestão
        if 'ata' in name or 'reuniao' in name or 'nota' in name or ext == '.md':
            return (1, "Documentos e Atas de Reunioes(.PDF/.MD)")
        if 'detalhe' in name or 'corte' in name or 'visao' in name:
            if ext in ['.dwg', '.pdf', '.dxf', '.md']:
                return (1, "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)")
        if ext == '.dwg' and ('bruto' in name or 'estrutural' in name):
            return (1, "Estruturais dos Pavimentos, Estado Bruto (.DWG)")
        if ext == '.dxf' and ('bruto' in name or 'estrutural' in name):
            return (1, "Estruturais dos Pavimentos, Estado Bruto (.DXF)")
        
        # Fase 2: Triagem
        if ext == '.dxf' and ('limpo' in name or 'clean' in name):
            return (2, "Estruturais Pavimentos Limpos")
        
        if 'detalhe' in name or 'corte' in name or 'visao' in name:
            return (2, "Detalhamentos Específicos")
            
        # Fallback para Fase 1 se for outro tipo não identificado
        return (1, "Documentos e Atas de Reunioes(.PDF/.MD)")
        
        # Fase 3: Pilares, Vigas, Lajes (análise)
        if 'pilar' in name and ext not in ['.json', '.scr', '.dxf']:
            return (3, "Pilares")
        if 'viga' in name and 'lateral' not in name and 'fundo' not in name and ext not in ['.json', '.scr', '.dxf']:
            return (3, "Vigas")
        if 'laje' in name and ext not in ['.json', '.scr', '.dxf']:
            return (3, "Lajes")
        
        # Fase 4: JSONs
        if ext == '.json':
            if 'pilar' in name: return (4, "JSON Pilares")
            elif 'laje' in name: return (4, "JSON Lajes")
            elif 'lateral' in name or ('viga' in name and 'fundo' not in name): return (4, "JSON Vigas Laterais")
            elif 'fundo' in name: return (4, "JSON Vigas Fundo")
        
        # Fase 5: Scripts SCR
        if ext == '.scr':
            if 'pilar' in name: return (5, "Scripts Pilares")
            elif 'laje' in name: return (5, "Scripts Lajes")
            elif 'lateral' in name or ('viga' in name and 'fundo' not in name): return (5, "Scripts Vigas Laterais")
            elif 'fundo' in name: return (5, "Scripts Vigas Fundo")
        
        # Fase 6: DXFs individuais
        if ext == '.dxf' and 'consolidado' not in name and 'final' not in name:
            if 'pilar' in name: return (6, "DXF Pilares")
            elif 'laje' in name: return (6, "DXF Lajes")
            elif 'lateral' in name or ('viga' in name and 'fundo' not in name): return (6, "DXF Vigas Laterais")
            elif 'fundo' in name: return (6, "DXF Vigas Fundo")
        
        # Fase 7: DXFs Consolidados
        if ext == '.dxf' and 'consolidado' in name:
            if 'pavimento' in name: return (7, "DXF Consolidado por Pavimento")
            else: return (7, "DXF Consolidado por Tipo")
        
        # Fase 8: DXF Final Validado
        if ext == '.dxf' and ('final' in name or 'validado' in name or 'entrega' in name):
            return (8, "DXF Final Validado")
        
        # Default fallback
        if ext == '.dxf':
            return (1, "Estruturais dos Pavimentos, Estado Bruto (.DXF)")
            
        if ext == '.pdf': return (1, "Documentos e Atas de Reunioes(.PDF/.MD)")
        return (1, "Documentos e Atas de Reunioes(.PDF/.MD)") # Fallback para Ingestão/Geral

    def _add_document_to_class(self, phase_num, class_name):
        """Adiciona um documento à classe especificada."""
        # Tenta obter o nome da obra atual
        work_name = self.current_work_name
        if not work_name:
            item = self.list_works.currentItem()
            if item:
                work_name = item.data(Qt.UserRole)

        if not self.current_project_id and not work_name:
            QMessageBox.warning(self, "Aviso", "Selecione um projeto ou uma obra primeiro.")
            return
        
        # Se não tem projeto selecionado, confirma se o usuário quer adicionar à Obra
        if not self.current_project_id and work_name:
             # Opcional: Warning ou permitir direto. Vamos permitir direto para Ingestão e Triagem.
             pass

        dialog = DocumentUploadDialog(class_name=class_name, parent=self)
        if dialog.exec_():
            data_list = dialog.get_data()
            if not isinstance(data_list, list):
                data_list = [data_list] # Fallback for backward compatibility just in case

            success_count = 0
            errors = []

            for data in data_list:
                file_path = data['path']
                display_name = data['name']
                
                ext = os.path.splitext(file_path)[1]
                try:
                    # Usa o ProjectStorageManager para salvar no local correto
                    target_path = self.storage_manager.save_file(
                        source_file_path=file_path,
                        work_name=work_name,
                        phase_id=phase_num,
                        class_name=class_name,
                        new_filename=f"{display_name}{ext}"  # Opcional: usar nome exibido ou nome sanitizado
                    )
                    
                    # Para compatibilidade com o DB que espera string
                    target_path_str = str(target_path)
                    
                    if self.current_project_id:
                        # Salva no DB vinculado ao Projeto
                        self.db.save_document(
                            project_id=self.current_project_id, 
                            name=display_name, 
                            file_path=target_path_str, 
                            extension=ext,
                            phase=phase_num,
                            category=class_name
                        )
                    else:
                        # Salva no DB vinculado à Obra
                        self.db.save_work_document(
                            work_name=work_name,
                            name=display_name,
                            file_path=target_path_str,
                            extension=ext,
                            storage_path=None, # Supabase path if needed
                            phase=phase_num,
                            category=class_name
                        )
                    success_count += 1
                except Exception as e:
                    logging.error(f"Erro ao adicionar documento {display_name}: {e}")
                    errors.append(f"{display_name}: {e}")

            self._refresh_phase_tabs()
            self.refresh_documents()  # Atualiza também o painel lateral
            
            if errors:
                msg = f"Importação concluída com avisos.\nSucessos: {success_count}\nFalhas: {len(errors)}\n\n" + "\n".join(errors)
                QMessageBox.warning(self, "Avisos na Importação", msg)
            else:
                QMessageBox.information(self, "Sucesso", f"{success_count} documentos adicionados.")


    def _delete_document_from_class(self, doc_id):
        """Exclui um documento da classe."""
        if QMessageBox.question(self, "Confirmar", "Deseja remover este documento?", 
                               QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.db.delete_document(doc_id)
            self._refresh_phase_tabs()

    def _open_project_main_dxf_from_card(self, project_data):
        """Abre o DXF principal a partir de um card de projeto."""
        fpath = project_data.get('dxf_path')
        if fpath and os.path.exists(fpath):
            import os
            os.startfile(fpath)
        else:
            QMessageBox.warning(self, "Erro", "Arquivo DXF não vinculado ou não encontrado.")

    def _delete_main_dxf(self):
        """Remove o DXF principal do projeto selecionado."""
        if not self.current_project_id: return
        
        if QMessageBox.question(self, "Confirmar", "Deseja remover o DXF Principal deste projeto?\nIsso não apagará o arquivo físico, apenas o desvinculará do pavimento.", 
                               QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                self.db.update_project_dxf(self.current_project_id, "")
                self._refresh_phase_tabs()
                logging.info(f"DXF Principal removido do projeto {self.current_project_id}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao remover DXF: {e}")

    def _refresh_phase_tabs(self):
        """Atualiza todas as abas de fases com os documentos atuais."""
        docs = []
        p_name = "Nenhum selecionado"
        
        work_name = self.current_work_name
        if not work_name:
            item = self.list_works.currentItem()
            if item:
                work_name = item.data(Qt.UserRole)

        try:
            if self.current_project_id:
                p_data = self.db.get_project_by_id(self.current_project_id)
                if p_data:
                    p_name = p_data.get('name', 'Sem nome')
                    
                    docs = self.db.get_project_documents(self.current_project_id)
                    
                    # Adicionar DXF principal se existir
                    if p_data.get('dxf_path'):
                        dxf_name = os.path.basename(p_data['dxf_path'])
                        already_in = any(d.get('name') == dxf_name for d in docs)
                        if not already_in:
                            docs.append({
                                'id': 'main_dxf',
                                'name': dxf_name + " (Principal)",
                                'file_path': p_data['dxf_path'],
                                'extension': '.dxf',
                                'is_main': True
                            })
            
            # Buscar documentos da Obra (nível superior, sem projeto específico)
            if work_name:
                work_docs = self.db.get_work_documents(work_name)
                # Filtrar para não duplicar se por acaso algo vier repetido
                existing_ids = set(d.get('id') for d in docs)
                for wd in work_docs:
                    if wd.get('id') not in existing_ids:
                        docs.append(wd)
            
            # Classificar documentos por fase/classe
            classified_docs = {}
            for doc in docs:
                phase_num, class_name = self._classify_document(doc)
                key = (phase_num, class_name)
                if key not in classified_docs:
                    classified_docs[key] = []
                classified_docs[key].append(doc)
            
            # Atualizar cada aba de fase
            for phase_num in range(1, 9):
                phase_tab = self.phase_tab_widgets.get(phase_num)
                if not phase_tab:
                    continue
                
                # Encontrar o container da fase
                scroll = phase_tab
                container = scroll.widget()
                if not container:
                    continue
                
                # Atualizar widgets de classes
                layout = container.layout()
                if not layout:
                    continue
                
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if not item:
                        continue
                    widget = item.widget()
                    if not widget:
                        continue
                    
                    # Verificar se é um widget de classe (QFrame com propriedade class_name)
                    class_name = widget.property("class_name")
                    if class_name:
                        # Encontrar o container de documentos
                        docs_container = widget.property("docs_container")
                        if docs_container:
                            docs_layout = docs_container.layout()
                            if docs_layout:
                                # Limpar documentos existentes (exceto container de pavimentos injetado)
                                for i in reversed(range(docs_layout.count())):
                                    child = docs_layout.itemAt(i)
                                    widget_to_check = child.widget()
                                    if widget_to_check:
                                        # Excluir containers especiais da limpeza
                                        is_special = False
                                        if hasattr(self, 'scroll_area') and widget_to_check == self.scroll_area: is_special = True
                                        if hasattr(self, 'phase3_pavement_selector') and widget_to_check == self.phase3_pavement_selector: is_special = True
                                        if hasattr(self, 'phase4_pavement_selector') and widget_to_check == self.phase4_pavement_selector: is_special = True
                                        if hasattr(self, 'phase5_pavement_selector') and widget_to_check == self.phase5_pavement_selector: is_special = True
                                        
                                        if is_special:
                                            continue
                                        docs_layout.takeAt(i)
                                        widget_to_check.deleteLater()
                                    else:
                                        # Remover spacers/stretches
                                        docs_layout.takeAt(i)
                                
                                # Agrupar DWG e DXF correspondentes
                                key = (phase_num, class_name)
                                class_docs = classified_docs.get(key, [])
                                
                                # Separar DXFs para busca rápida
                                dxfs_map = {} # Nome Base -> Doc
                                others = []
                                
                                # Primeiro passo: Separar DXFs convertidos automaticamente
                                for d in class_docs:
                                    name = d.get('name', '')
                                    ext = d.get('extension', '').lower()
                                    if ext == '.dxf' and '(Auto-DXF)' in name:
                                        # Remove sufixo para achar o pai
                                        base = name.replace(" (Auto-DXF)", "").strip()
                                        dxfs_map[base] = d
                                    else:
                                        others.append(d)
                                
                                # Segundo passo: Iterar sobre os outros e tentar casar
                                final_list = [] # Lista de (Parent, Child) ou (Single, None)
                                handled_dxfs_ids = set()
                                
                                for d in others:
                                    ext = d.get('extension', '').lower()
                                    name = d.get('name', '')
                                    
                                    child = None
                                    if ext == '.dwg':
                                        # Tenta achar um filho DXF
                                        if name in dxfs_map:
                                            child = dxfs_map[name]
                                            handled_dxfs_ids.add(child.get('id'))
                                    
                                    final_list.append((d, child))
                                
                                # Adicionar DXFs que sobraram (órfãos ou manuais que cairam no filtro de auto mas sem pai dwg na lista)
                                for base, d in dxfs_map.items():
                                    if d.get('id') not in handled_dxfs_ids:
                                        final_list.append((d, None))
                                        
                                # Renderizar
                                for parent_doc, child_doc in final_list:
                                    doc_widget = self._create_document_item_widget(parent_doc, child_doc)
                                    docs_layout.addWidget(doc_widget)
                                
                                docs_layout.addStretch()

                        # Se tiver uma árvore de banco de dados (Fase 3 ou 4), atualizar dados baseados no projeto atual
                        tree = widget.property("db_tree")
                        if tree:
                            if phase_num == 3:
                                self._refresh_phase3_data(class_name, tree)
                            elif phase_num == 4:
                                # Na fase 4, o refresh_phase4_data usa o pavimento selecionado no combo global
                                self._refresh_phase4_data(class_name, tree)
                            elif phase_num == 5:
                                # Na fase 5, o refresh_phase5_data usa o pavimento selecionado no combo global
                                self._refresh_phase5_data(class_name, tree)
                                self._update_script_progress()
        except Exception as e:
            logging.error(f"Erro ao atualizar abas de fases: {e}")

    def _refresh_all_phase5_lists(self):
        """Atualiza todas as listas de itens da Fase 5."""
        phase_tab = self.phase_tab_widgets.get(5)
        if not phase_tab: return
        
        container = phase_tab.widget()
        if not container: return
        layout = container.layout()
        
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if widget:
                class_name = widget.property("class_name")
                tree = widget.property("db_tree")
                if class_name and tree:
                    self._refresh_phase5_data(class_name, tree)
        
        self._update_script_progress()

    def _sync_pillar_scripts_from_disk(self, pav_nome):
        """Verifica se existem scripts gerados de pilares e atualiza o DB."""
        if not pav_nome: return
        try:
            base_dir = os.path.join(self.base_dir, "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25", "SCRIPTS_ROBOS")
            if not os.path.exists(base_dir): 
                logging.debug(f"[Phase5] 📂 Pasta de scripts de pilares não encontrada: {base_dir}")
                return

            # Normalizar pav_nome para busca em pastas (P-1 -> P_1)
            pav_search = pav_nome.replace("-", "_")
            
            # Tipos específicos suportados pelo robô
            types_map = {
                'pilar_cima': ("CIMA", "_CIMA.scr"),
                'pilar_grades': ("GRADES", "_GRADES.scr"),
                'pilar_abcd': ("ABCD", "_ABCD.scr")
            }

            pillars = self.db.load_pillars(self.current_project_id)
            found_total = 0
            
            for p in pillars:
                p_name = str(p.get('name', '')).strip()
                p_id = str(p.get('id', ''))
                
                for type_key, (suffix_folder, file_suffix) in types_map.items():
                    # Tentar pasta: <PAV>_<TIPO> (Ex: P_1_CIMA) ou apenas <TIPO>
                    possible_folders = [f"{pav_search}_{suffix_folder}", f"{pav_nome}_{suffix_folder}"]
                    
                    found_path = None
                    for pf in possible_folders:
                        folder_path = os.path.join(base_dir, pf)
                        if not os.path.exists(folder_path): continue
                        
                        # Opção 1: Nome+Sufixo (Ex: P1_CIMA.scr)
                        p1 = os.path.join(folder_path, f"{p_name}{file_suffix}")
                        if os.path.exists(p1): 
                            found_path = p1
                            break
                        
                        # Opção 2: Apenas Nome (Ex: P1.scr)
                        p2 = os.path.join(folder_path, f"{p_name}.scr")
                        if os.path.exists(p2):
                            found_path = p2
                            break
                    
                    if found_path:
                        self.db.save_generated_script(self.current_project_id, pav_nome, p_id, type_key, found_path)
                        found_total += 1
            
            if found_total > 0:
                logging.info(f"[Phase5] 🤖 Sincronizados {found_total} arquivos de script para pilares em '{pav_nome}'")
        except Exception as e:
            logging.error(f"Erro ao sincronizar scripts de pilares: {e}")

    def _sync_beam_scripts_from_disk(self, pav_nome):
        """Sincroniza scripts de vigas (Laterais e Fundo)."""
        if not pav_nome: return
        try:
            # 1. Laterais
            lat_dir = os.path.join(self.base_dir, "_ROBOS_ABAS", "Robo_Laterais_de_Vigas", "SCRIPTS")
            # 2. Fundos
            fun_dir = os.path.join(self.base_dir, "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao", "PASTAS-FUNDOS")
            
            beams = self.db.load_beams(self.current_project_id)
            found_count = 0
            
            for b in beams:
                b_name = b.get('name', '')
                b_id = b.get('id', '')
                b_type_db = str(b.get('type', '')).upper()
                
                # Sincronizar Lateral
                if "FUNDO" not in b_type_db:
                    # Tentar diversas variações de pasta de pavimento para Vigas Laterais
                    for pav_var in [pav_nome, pav_nome.replace("-", "_"), pav_nome.replace("-", " ")]:
                        p_dir = os.path.join(lat_dir, pav_var)
                        if os.path.exists(p_dir):
                            # Robô de viga às vezes gera V1.scr ou V1.A.scr
                            for f_name in [f"{b_name}.scr", f"{b_name}.A.scr", f"{b_name}.scr.scr"]:
                                script_path = os.path.join(p_dir, f_name)
                                if os.path.exists(script_path):
                                    self.db.save_generated_script(self.current_project_id, pav_nome, b_id, 'viga_lateral', script_path)
                                    found_count += 1
                                    break
                
                # Sincronizar Fundo
                if "LATERAL" not in b_type_db:
                    p_dir = os.path.join(fun_dir, pav_nome)
                    if not os.path.exists(p_dir): p_dir = os.path.join(fun_dir, pav_nome.replace("-", "_"))
                    
                    if os.path.exists(p_dir):
                        # Robô de fundo gera V1.scr ou V1_Fundo.scr
                        for f_name in [f"{b_name}.scr", f"{b_name}_Fundo.scr"]:
                            script_path = os.path.join(p_dir, f_name)
                            if os.path.exists(script_path):
                                self.db.save_generated_script(self.current_project_id, pav_nome, b_id, 'viga_fundo', script_path)
                                found_count += 1
                                break
            
            if found_count > 0:
                logging.info(f"[Phase5] 🤖 Sincronizados {found_count} scripts de vigas para '{pav_nome}'")
        except Exception as e:
            logging.error(f"Erro ao sincronizar scripts de vigas: {e}")

    def _sync_laje_scripts_from_disk(self, pav_nome):
        """Sincroniza scripts de lajes."""
        if not pav_nome: return
        try:
            base_dir = os.path.join(self.base_dir, "_ROBOS_ABAS", "Robo_Lajes", "laje_src", "output")
            if not os.path.exists(base_dir): return
            
            slabs = self.db.load_slabs(self.current_project_id)
            found_count = 0
            
            all_files = os.listdir(base_dir)
            
            for s in slabs:
                s_name = s.get('name', '')
                s_id = s.get('id', '')
                
                # Busca flexível no nome do arquivo
                target = f"_{s_name}.scr"
                for f in all_files:
                    if f.endswith(target):
                        script_path = os.path.join(base_dir, f)
                        self.db.save_generated_script(self.current_project_id, pav_nome, s_id, 'laje', script_path)
                        found_count += 1
                        break
            
            if found_count > 0:
                logging.info(f"[Phase5] 🤖 Sincronizados {found_count} scripts de lajes para '{pav_nome}'")
        except Exception as e:
            logging.error(f"Erro ao sincronizar scripts de lajes: {e}")

    def _refresh_phase5_data(self, class_name, tree_widget):
        """Carrega dados da Fase 5 (Scripts) mostrando o status de cada item."""
        if not self.current_project_id:
            tree_widget.clear()
            return

        pav_nome = ""
        if hasattr(self, 'cmb_pavements_validation'):
            p_data = self.cmb_pavements_validation.currentData()
            if p_data: pav_nome = p_data.get('name', '')

        tree_widget.clear()
        
        items = []
        item_type = ""
        if "Pilares" in class_name:
            items = self.db.load_pillars(self.current_project_id)
            item_type = 'pilar'
        elif "Lajes" in class_name:
            items = self.db.load_slabs(self.current_project_id)
            item_type = 'laje'
        elif "Laterais" in class_name:
            # Filtro flexível para vigas laterais (Case Insensitive)
            # Aceita 'Lateral' explícito OU 'Viga' genérico (que possui lateral)
            all_beams = self.db.load_beams(self.current_project_id)
            
            items = []
            for b in all_beams:
                b_type = str(b.get('type', '')).upper()
                # Se for Lateral ou Genérico (Viga), e não for Fundo explícito
                if ("LATERAL" in b_type or b_type == "VIGA") and "FUNDO" not in b_type:
                    items.append(b)
            
            item_type = 'viga_lateral'

        elif "Fundo" in class_name:
            # Filtro flexível para vigas de fundo (Case Insensitive)
            # Aceita 'Fundo' explícito OU 'Viga' genérico (que possui fundo)
            all_beams = self.db.load_beams(self.current_project_id)
            
            items = []
            for b in all_beams:
                b_type = str(b.get('type', '')).upper()
                # Se for Fundo ou Genérico (Viga), e não for Lateral explícito
                if ("FUNDO" in b_type or b_type == "VIGA") and "LATERAL" not in b_type:
                    items.append(b)
            
            item_type = 'viga_fundo'

        # Na Fase 5, se for Scripts Pilares, sincronizar arquivos do disco para o DB antes de carregar
        # Sincronização automática do disco para o DB antes de carregar
        if class_name == "Scripts Pilares":
            self._sync_pillar_scripts_from_disk(pav_nome)
        elif class_name == "Scripts Lajes":
            self._sync_laje_scripts_from_disk(pav_nome)
        elif "Vigas" in class_name:
            self._sync_beam_scripts_from_disk(pav_nome)

        generated_scripts = self.db.get_generated_scripts(self.current_project_id, pav_nome)
        generated_map = { f"{s['item_type']}_{s['item_id']}": s for s in generated_scripts }

        # Ordenar itens
        import re
        def nat_key(x):
            name = str(x.get('name', x.get('nome', '')))
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]
        items.sort(key=nat_key)

        for i, item in enumerate(items):
            tree_item = QTreeWidgetItem(tree_widget)
            item_db_id = item.get('id')
            item_id_label = item.get('id_item', f"{i+1:02}")
            name = str(item.get('name', 'N/A'))
            
            tree_item.setText(0, item_id_label)
            tree_item.setText(1, name)
            
            if class_name == "Scripts Pilares":
                for col, t_key in [(2, 'pilar_cima'), (3, 'pilar_grades'), (4, 'pilar_abcd')]:
                    s_info = generated_map.get(f"{t_key}_{item_db_id}")
                    if s_info:
                        dt = s_info.get('generated_at', '')
                        if dt and ' ' in dt: dt = dt.split(' ')[0]
                        label_dt = f"{dt[8:10]}/{dt[5:7]}" if len(dt) >= 10 else "Sim"
                        tree_item.setText(col, f"✅ {label_dt}")
                        tree_item.setForeground(col, QColor("#00ffaa"))
                        tree_item.setToolTip(col, f"Gerado em: {s_info.get('generated_at')}\nCaminho: {s_info.get('script_path')}")
                    else:
                        tree_item.setText(col, "⏳ Pend")
                        tree_item.setForeground(col, QColor("#ffaa00"))
            else:
                s_info = generated_map.get(f"{item_type}_{item_db_id}")
                if s_info:
                    dt = s_info.get('generated_at', '')
                    if dt and ' ' in dt: dt = dt.split(' ')[0]
                    label_dt = f"{dt[8:10]}/{dt[5:7]}" if len(dt) >= 10 else "Sim"
                    tree_item.setText(2, f"✅ GERADO ({label_dt})")
                    tree_item.setForeground(2, QColor("#00ffaa"))
                else:
                    tree_item.setText(2, "⏳ PENDENTE")
                    tree_item.setForeground(2, QColor("#ffaa00"))

            btn_action = QPushButton("📁")
            btn_action.setFixedSize(30, 22)
            btn_action.setCursor(Qt.PointingHandCursor)
            btn_action.setStyleSheet("background: #333; color: white; border-radius: 3px;")
            
            def make_open_fn(it_id):
                def open_fn():
                    found = False
                    for k, v in generated_map.items():
                        if it_id in k and os.path.exists(v['script_path']):
                            import os, subprocess
                            path = os.path.abspath(v['script_path'])
                            subprocess.Popen(f'explorer /select,"{path}"')
                            found = True
                            break
                    if not found:
                        QMessageBox.information(self, "Aviso", "Nenhum arquivo físico localizado para este item.")
                return open_fn

            btn_action.clicked.connect(make_open_fn(item_db_id))
            action_col = 5 if class_name == "Scripts Pilares" else 3
            tree_widget.setItemWidget(tree_item, action_col, btn_action)
            tree_item.setData(0, Qt.UserRole, item)

    def _update_script_progress(self):
        """Atualiza a barra de progresso de scripts da Fase 5."""
        if not self.current_project_id:
            if hasattr(self, 'phase5_progress_bar'): self.phase5_progress_bar.setValue(0)
            return
            
        pav_nome = ""
        if hasattr(self, 'cmb_pavements_validation'):
            p_data = self.cmb_pavements_validation.currentData()
            if p_data: pav_nome = p_data.get('name', '')
            
        if not pav_nome: return

        stats = self.db.get_script_generation_stats(self.current_project_id, pav_nome)
        
        if hasattr(self, 'phase5_progress_bar'):
            self.phase5_progress_bar.setValue(int(stats['percentage']))
            if hasattr(self, 'phase5_progress_label'):
                self.phase5_progress_label.setText(f"📊 PROGRESSO DE SCRIPTS: {stats['generated']}/{stats['total']} ({int(stats['percentage'])}%)")

    def _create_document_item_widget(self, doc, child_doc=None):
        """Cria um widget de item de documento para exibir na lista (suporta aninhamento)."""
        main_container = QFrame()
        # Se tiver filho, usamos layout vertical para empilhar. Se não, o estilo padrão.
        if child_doc:
            main_container.setStyleSheet("""
                QFrame#MainContainer {
                    background: #252528;
                    border: 1px solid #333;
                    border-radius: 4px;
                }
                QFrame#Row {
                    background: transparent;
                    border: none;
                }
                QFrame#Row:hover {
                    background: #2a2a2d;
                }
                QFrame#ChildRow {
                    background: #222225;
                    border-top: 1px solid #333;
                }
            """)
            main_container.setObjectName("MainContainer")
            container_layout = QVBoxLayout(main_container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
        else:
            main_container.setStyleSheet("""
                QFrame {
                    background: #252528;
                    border: 1px solid #333;
                    border-radius: 4px;
                    padding: 8px;
                }
                QFrame:hover {
                    background: #2a2a2d;
                    border-color: #444;
                }
            """)
            container_layout = QVBoxLayout(main_container) # Use VBox genericamente, mas com um item só
            container_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Helper para criar linha ---
        def create_row_widget(item_doc, is_child=False):
            row_frame = QFrame()
            if child_doc:
                row_frame.setObjectName("ChildRow" if is_child else "Row")
                if not is_child:
                    # Arredondar apenas topo
                    pass
            
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(10, 8, 10, 8)
            
            # Indentação para filho
            if is_child:
                icon_link = QLabel("↳")
                icon_link.setStyleSheet("color: #666; font-size: 16px; font-weight: bold; margin-right: 5px;")
                row_layout.addWidget(icon_link)

            # Nome do documento
            doc_name = item_doc.get('name', 'Sem nome')
            name_label = QLabel(doc_name)
            name_style = "color: #e0e0e0; font-size: 12px;"
            if is_child: name_style += " font-style: italic; color: #aaa;"
            name_label.setStyleSheet(name_style)
            row_layout.addWidget(name_label)
            
            # Formato
            ext = item_doc.get('extension', '')
            format_label = QLabel(ext.upper() if ext else "N/A")
            format_label.setStyleSheet("color: #888; font-size: 10px; padding: 2px 8px; background: #1a1a1a; border-radius: 3px;")
            row_layout.addWidget(format_label)
            
            row_layout.addStretch()
            
            # Botão Abrir
            btn_open = QPushButton(" EYE ") # Using text fallback if icon fails font support
            btn_open.setText("👁️")
            btn_open.setFixedSize(28, 28)
            btn_open.setCursor(Qt.PointingHandCursor)
            btn_open.setToolTip("Abrir documento")
            btn_open.setStyleSheet("""
                QPushButton {
                    background: #1a324b; color: #00d4ff; border: 1px solid #00d4ff;
                    border-radius: 4px; font-weight: bold; font-size: 14px;
                }
                QPushButton:hover { background: #00d4ff; color: #000; }
            """)
            fpath = item_doc.get('file_path')
            if fpath:
                import os
                btn_open.clicked.connect(lambda: os.startfile(fpath) if os.path.exists(fpath) else QMessageBox.warning(self, "Erro", "Arquivo não encontrado."))
            row_layout.addWidget(btn_open)

            # Botão Converter (Apenas para DWG Pai)
            if not is_child and ext.lower() == '.dwg':
                 btn_convert = QPushButton("🔄 Converter")
                 btn_convert.setCursor(Qt.PointingHandCursor)
                 btn_convert.setStyleSheet("""
                    QPushButton {
                        background: #1a324b; color: #00d4ff; border: 1px solid #00d4ff;
                        border-radius: 4px; padding: 4px 10px; font-size: 10px; font-weight: bold;
                    }
                    QPushButton:hover { background: #00d4ff; color: #000; }
                 """)
                 btn_convert.clicked.connect(lambda _, d=item_doc: self._convert_dwg_to_dxf(d))
                 row_layout.addWidget(btn_convert)

            # Botão excluir
            btn_delete = QPushButton("✕")
            btn_delete.setFixedSize(28, 28)
            btn_delete.setCursor(Qt.PointingHandCursor)
            btn_delete.setToolTip("Excluir documento")
            btn_delete.setStyleSheet("""
                QPushButton {
                    background: #3a1c1c; color: #ff6b6b; border: 1px solid #ff4444;
                    border-radius: 4px; font-weight: bold; font-size: 12px;
                }
                QPushButton:hover { background: #ff4444; color: white; }
            """)
            doc_id = item_doc.get('id')
            if doc_id == 'main_dxf':
                btn_delete.clicked.connect(lambda: self._delete_main_dxf())
            elif doc_id:
                # Se for filho, deleta normal. Se for pai, também.
                btn_delete.clicked.connect(lambda: self._delete_document_from_class(doc_id))
            
            row_layout.addWidget(btn_delete)
            return row_frame

        # Adicionar Pai
        container_layout.addWidget(create_row_widget(doc, is_child=False))
        
        # Adicionar Filho (se houver)
        if child_doc:
            container_layout.addWidget(create_row_widget(child_doc, is_child=True))
            
        return main_container

    def _convert_dwg_to_dxf(self, doc):
        """Converte um DWG para DXF usando aspose-cad."""
        dwg_path = doc.get('file_path')
        if not dwg_path or not os.path.exists(dwg_path):
            QMessageBox.warning(self, "Erro", "Arquivo fonte não encontrado.")
            return

        # Caminho de saída
        dir_path = os.path.dirname(dwg_path)
        base_name = os.path.splitext(os.path.basename(dwg_path))[0]
        # Garantir que o nome seja único removendo sufixos anteriores se existirem
        dxf_path = os.path.join(dir_path, f"{base_name}.dxf")
        
        # Se o DXF já existe, adiciona timestamp ou uuid para não sobrescrever o principal se for o caso
        if os.path.exists(dxf_path):
            dxf_path = os.path.join(dir_path, f"{base_name}_{uuid.uuid4().hex[:4]}.dxf")
        
        try:
            # Importação lazy
            import aspose.cad as cad
            from PySide6.QtCore import Qt
            
            self.setCursor(Qt.WaitCursor)
            logging.info(f"Iniciando conversão DWG -> DXF: {dwg_path}")
            
            # Carregar e salvar
            with cad.Image.load(dwg_path) as image:
                # Configurações de exportação para DXF
                options = cad.imageoptions.DxfOptions()
                image.save(dxf_path, options)
            
            # Salvar como novo documento no banco (Explicitamente na classe de Brutos DXF)
            # Salvar como novo documento no banco (Explicitamente na classe de Brutos DXF)
            if self.current_project_id:
                self.db.save_document(
                    project_id=self.current_project_id, 
                    name=f"{base_name} (Auto-DXF)", 
                    file_path=dxf_path, 
                    extension=".dxf",
                    phase=1,
                    category="Estruturais dos Pavimentos, Estado Bruto (.DXF)"
                )
            else:
                # Se não tem projeto selecionado, salva na Obra
                curr_work = self.current_work_name
                if not curr_work:
                    item = self.list_works.currentItem()
                    if item:
                        curr_work = item.data(Qt.UserRole)
                
                if curr_work:
                    self.db.save_work_document(
                        work_name=curr_work,
                        name=f"{base_name} (Auto-DXF)",
                        file_path=dxf_path,
                        extension=".dxf",
                        storage_path=None,
                        phase=1,
                        category="Estruturais dos Pavimentos, Estado Bruto (.DXF)"
                    )
                else:
                    logging.warning("Tentativa de salvar DXF convertido sem Projeto ou Obra definidos.")
            
            self.setCursor(Qt.ArrowCursor)
            QMessageBox.information(self, "Sucesso", f"Arquivo convertido com sucesso!\nNovo DXF adicionado à lista.")
            
            self._refresh_phase_tabs()
            
        except Exception as e:
            self.setCursor(Qt.ArrowCursor)
            logging.error(f"Erro na conversão: {e}")
            QMessageBox.critical(self, "Erro na Conversão", f"Falha ao converter ou biblioteca não compatível.\nDetalhes: {str(e)}")

    def setup_community_tab(self):
        layout = QVBoxLayout(self.community_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        self.admin_dashboard = AdminDashboard(self.db, self.memory)
        layout.addWidget(self.admin_dashboard)

    # --- Interaction Logic ---

    def load_works_combo(self):
        """Popula a lista de obras da sidebar."""
        self.list_works.blockSignals(True)
        self.list_works.clear()
        
        # REMOVIDO: "Todas as Obras" conforme pedido do usuário
        
        try:
            works = self.db.get_all_works()
            for w in works:
                item = QListWidgetItem(f"📁 {w}")
                item.setData(Qt.UserRole, w)
                self.list_works.addItem(item)
                
            # Adicionar item para "Pavimentos Sem Obra"
            item_orphaned = QListWidgetItem("⚠️ Pavimentos Sem Obra")
            item_orphaned.setData(Qt.UserRole, "__NO_WORK__")
            item_orphaned.setToolTip("Pavimentos que não estão vinculados a nenhuma obra")
            self.list_works.addItem(item_orphaned)
            
        except Exception as e:
            logging.error(f"Erro ao carregar obras: {e}")
            
        self.list_works.setCurrentRow(0)
        self.list_works.blockSignals(False)

    def _filter_works_list(self, text):
        """Filtra visualmente a lista de obras."""
        for i in range(self.list_works.count()):
            item = self.list_works.item(i)
            # Agora filtra todos os itens
            show = text.lower() in item.text().lower()
            item.setHidden(not show)

    def load_projects(self):
        """Carrega os pavimentos filtrando pela obra selecionada usando Cards."""
        # Limpar layout atual
        for i in reversed(range(self.cards_layout.count())):
            widget = self.cards_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        # Reset column stretch if previously set with multiple cols
        self.cards_layout.setColumnStretch(0, 1)
                
        selected_item = self.list_works.currentItem()
        filter_work = selected_item.data(Qt.UserRole) if selected_item else None
        
        self.current_work_name = filter_work if filter_work != "__NO_WORK__" else None
        
        # Mostrar botões de ação da obra (Esconder se for 'Sem Obra')
        has_work = bool(filter_work) and filter_work != "__NO_WORK__"
        self.btn_delete_work.setVisible(has_work)
        self.btn_sync_work.setVisible(has_work)
        
        # Atualiza o header
        display_text = selected_item.text().replace("📁 ", "").replace("🏢 ", "") if selected_item else "Selecione uma Obra"
        self.lbl_selected_work.setText(display_text)
        
        # Carregar metadados da obra na aba lateral
        self.load_work_metadata(filter_work)

        try:
            # Pega todos (poderia otimizar no SQL, mas ok)
            projects = self.db.get_projects()
        except Exception as e:
            logging.error(f"load_projects failed: {e}")
            return
            
        row = 0
        col = 0
        max_cols = 1 
        
        # Preparar lista para o Combo da Fase 3
        filtered_projects = []
        for p in projects:
            p_work = p.get('work_name') or ""
            if filter_work == "__NO_WORK__":
                if p_work: continue
            elif filter_work:
                if p_work != filter_work: continue
            filtered_projects.append(p)

        # Atualizar Combos das Fases 3, 4 e 5
        for combo_name in ['cmb_pavements_extraction', 'cmb_pavements_recognition', 'cmb_pavements_validation']:
            if hasattr(self, combo_name):
                cmb = getattr(self, combo_name)
                cmb.blockSignals(True)
                cmb.clear()
                icon = "✅" if combo_name == 'cmb_pavements_validation' else ("🤖" if combo_name == 'cmb_pavements_recognition' else "🏗️")
                for p in filtered_projects:
                    cmb.addItem(f"{icon} {p.get('name', 'N/A')}", p)
                cmb.blockSignals(False)

        first_project = None
        for p in filtered_projects:
            if not first_project:
                first_project = p

            card = ProjectCard(p)
            card.clicked.connect(self.on_project_card_clicked)
            card.action_ficha.connect(self.open_details_dialog)
            card.action_sync.connect(self.sync_single_project_card)
            card.action_move.connect(self.move_project_to_work)
            card.action_delete.connect(self.confirm_delete_project_card)
            card.action_open_dxf.connect(self._open_project_main_dxf_from_card)
            
            self.cards_layout.addWidget(card, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
                
        # Auto-selecionar o primeiro se existir
        if first_project:
            self.on_project_card_clicked(first_project)
        else:
            self.current_project_id = None
            self._refresh_phase_tabs() # Limpa as abas

    def on_project_card_clicked(self, p):
        """Manipula o clique no card do projeto ou seleção via combo."""
        self.current_project_id = p.get('id')
        self.current_project_name = p.get('name')

        # Sincronizar os Combos das Fases 3, 4 e 5 com esta seleção (se não foi ele que disparou)
        for combo_name in ['cmb_pavements_extraction', 'cmb_pavements_recognition', 'cmb_pavements_validation']:
            if hasattr(self, combo_name):
                cmb = getattr(self, combo_name)
                cmb.blockSignals(True)
                for i in range(cmb.count()):
                    p_item = cmb.itemData(i)
                    if p_item and p_item.get('id') == self.current_project_id:
                        cmb.setCurrentIndex(i)
                        break
                cmb.blockSignals(False)
        
        # Breadcrumbs Update
        self.breadcrumbs.set_path("Projetos", p.get('work_name') or "Sem Obra", p['name'])
        
        self._refresh_phase_tabs()

    def create_new_project(self):
        """Creates a new project (Pavimento) under the currently selected work."""
        selected_item = self.list_works.currentItem()
        current_work = selected_item.data(Qt.UserRole) if selected_item else None
        
        if not current_work or current_work == "__NO_WORK__":
            work_name, ok = QInputDialog.getText(self, "Nova Obra", "Digite o nome da Obra para este projeto:")
            if not ok or not work_name.strip(): return
            current_work = work_name.strip()
            
        name, ok = QInputDialog.getText(self, "Novo Pavimento", f"Nome do Pavimento (Obra: {current_work}):")
        if ok and name.strip():
            try:
                new_id = str(uuid.uuid4())
                self.db.create_project(
                    force_id=new_id,
                    name=name.strip(),
                    dxf_path="",  
                    work_name=current_work,
                    pavement_name=name.strip(),
                    description="Novo projeto criado via Gerenciador",
                    sync_status="pending"
                )
                
                self.load_works_combo() 
                items = self.list_works.findItems(f"📁 {current_work}", Qt.MatchContains)
                if items: self.list_works.setCurrentItem(items[0])
                
                self.load_projects()
                QMessageBox.information(self, "Sucesso", f"Pavimento '{name}' criado com sucesso!")
                
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao criar projeto: {e}")


    def _update_docs_tab_list(self, docs):
        """Método mantido para compatibilidade - agora redireciona para _refresh_phase_tabs()"""
        # Este método é chamado por código legado, mas agora usamos _refresh_phase_tabs()
        self._refresh_phase_tabs()

    def upload_document(self):
        if not self.current_project_id:
            QMessageBox.warning(self, "Aviso", "Selecione um projeto.")
            return
            
        dialog = DocumentUploadDialog(class_name="Geral", parent=self)
        if dialog.exec_():
            data = dialog.get_data()
            file_path = data['path']
            display_name = data['name']
            category = data['category']
            
            ext = os.path.splitext(file_path)[1]
            try:
                # Usa o ProjectStorageManager para salvar
                target_path = self.storage_manager.save_file(
                    source_file_path=file_path,
                    work_name=self.current_work_name, # Garante que usa o nome da obra atual
                    phase_id=1, # Default para upload genérico
                    class_name=category,
                    new_filename=f"{display_name}{ext}"
                )
                
                # Salva no DB
                self.db.save_document(
                    project_id=self.current_project_id, 
                    name=display_name, 
                    file_path=str(target_path), 
                    extension=ext,
                    phase=1,
                    category=category
                )
                self._refresh_phase_tabs()
                self.refresh_documents()  # Atualiza também o painel lateral
                
                logging.info(f"Documento '{display_name}' ({category}) enviado com sucesso.")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao processar upload: {e}")

    def delete_document_instance(self, doc_id):
        if QMessageBox.question(self, "Confirmar", "Deseja remover este documento?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.db.delete_document(doc_id)
            self._refresh_phase_tabs()
            self.refresh_documents()  # Atualiza também o painel lateral

    def on_open_clicked(self):
        """Abre o projeto selecionado e fecha o gerenciador."""
        if self.current_project_id:
            p = self.db.get_project_by_id(self.current_project_id)
            if p:
                self.project_selected.emit(p['id'], p['name'], p['dxf_path'])
                self.close()

    def _open_project_in_tab(self, tab_index):
        """Emits signal to open canvas and switch tab"""
        if self.current_project_id:
            p_data = self.db.get_project_by_id(self.current_project_id)
            if p_data:
                # 1. Load Project (Global)
                self.project_selected.emit(p_data['id'], p_data['name'], p_data['dxf_path'])
                # 2. Switch Tab
                self.request_tab_switch.emit(tab_index)

    def add_work(self):
        name, ok = QInputDialog.getText(self, "Nova Obra", "Nome da Obra:")
        if ok and name:
            try:
                self.storage_manager.initialize_work_structure(name)
                self.db.create_work(name)
                self.load_works_combo()
            except Exception as e:
                QMessageBox.critical(self, "Erro", str(e))

    def delete_current_work(self):
        """Exclui a obra selecionada após confirmação de segurança."""
        selected_item = self.list_works.currentItem()
        if not selected_item: return
        
        work_name = selected_item.data(Qt.UserRole)
        if not work_name: return

        # Confirmação de Segurança
        text, ok = QInputDialog.getText(
            self, 
            "Excluir Obra e Pavimentos", 
            f"ATENÇÃO: Isso excluirá a obra '{work_name}' e TODOS os seus pavimentos/dados locais.\n\nPara confirmar, digite 'EXCLUIR':"
        )
        
        if ok and text and text.strip().upper() == "EXCLUIR":
            try:
                # Chama a versão atualizada do delete_work que faz cascata
                self.db.delete_work(work_name)
                QMessageBox.information(self, "Sucesso", f"Obra '{work_name}' removida.")
                self.load_works_combo() # Recarrega a lista lateral
                # O load_works_combo seleciona a linha 0, que aciona load_projects, que limpa a UI
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao excluir obra: {e}")
        elif ok:
            QMessageBox.warning(self, "Cancelado", "A confirmação incorreta cancelou a operação.")

    def sync_selected_to_cloud(self):
        row = self.table.currentRow()
        if row < 0: return
        p = self.table.item(row, 0).data(Qt.UserRole)
        data = self.db.export_project_data(p['id'])
        if not data: return

        auth = AuthService()
        session = auth.get_session()
        if not session:
            QMessageBox.warning(self, "Login", "Faça login para sincronizar.")
            return

        sync = SyncService()
        import threading
        def do_sync():
            success = sync.sync_project(data, session)
            self.sync_complete_signal.emit(success, p['id'])
        threading.Thread(target=do_sync, daemon=True).start()

    def sync_single_project_card(self, project_data):
        """Sincroniza um projeto específico a partir do card."""
        pid = project_data.get('id')
        data = self.db.export_project_data(pid)
        if not data: return

        auth_session = self.auth_service.get_session()
        if not auth_session:
            QMessageBox.warning(self, "Login", "Faça login para sincronizar.")
            return

        sync = SyncService()
        import threading
        def do_sync():
            success = sync.sync_project(data, auth_session)
            self.sync_complete_signal.emit(success, pid)
        threading.Thread(target=do_sync, daemon=True).start()

    def _on_sync_complete(self, success, project_id):
        if success:
            self.db.update_project_sync_status(project_id, 'synced')
            self.load_projects()
            QMessageBox.information(self, "Sucesso", "Sincronizado!")
        else:
            QMessageBox.critical(self, "Erro", "Falha na sincronização.")

    def remove_selected_local(self):
        row = self.table.currentRow()
        if row < 0: return
        p = self.table.item(row, 0).data(Qt.UserRole)
        if QMessageBox.question(self, "Remover", f"Remover '{p['name']}' localmente?") == QMessageBox.Yes:
            self.db.delete_project_fully(p['id'])
            self.load_projects()
            self.detail_content.hide()
            self.lbl_no_selection.show()
    
    def sync_current_work(self):
        """Sincroniza TODOS os projetos e documentos da obra atual com a nuvem."""
        selected_item = self.list_works.currentItem()
        if not selected_item: return
        work_name = selected_item.data(Qt.UserRole)
        
        if not work_name: return

        reply = QMessageBox.question(
            self, 
            "Sincronizar Obra Completa", 
            f"Deseja enviar TODOS os pavimentos e documentos da obra '{work_name}' para a nuvem?\nIsso pode levar alguns minutos.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 1. Buscar todos os projetos dessa obra
                projects = [p for p in self.db.get_projects() if p.get('work_name') == work_name]
                if not projects:
                    QMessageBox.warning(self, "Aviso", "Nenhum projeto encontrado nesta obra.")
                    return

                # 2. Iterar e Sincronizar
                progress = QProgressBar(self) # Create transient progress dialog ideally, but simplified here
                pd = None
                try:
                    from PySide6.QtWidgets import QProgressDialog
                    pd = QProgressDialog(f"Sincronizando '{work_name}'...", "Cancelar", 0, len(projects), self)
                    pd.setWindowModality(Qt.WindowModal)
                    pd.show()
                except: pass

                success_count = 0
                for i, p in enumerate(projects):
                    if pd and pd.wasCanceled(): break
                    if pd: pd.setLabelText(f"Sincronizando {p.get('name')} ({i+1}/{len(projects)})...")
                    
                    auth_session = self.auth_service.get_session()
                    if not auth_session:
                        raise Exception("Sessão expirada. Faça login novamente.")

                    full_data = self.db.export_project_data(p['id'])
                    if self.sync_service.sync_project(full_data, auth_session):
                        self.db.update_project_sync_status(p['id'], 'synced')
                        success_count += 1
                    
                    if pd: pd.setValue(i + 1)
                
                QMessageBox.information(self, "Concluído", f"{success_count}/{len(projects)} pavimentos sincronizados com sucesso!")
                
            except Exception as e:
                logging.error(f"Erro sync work: {e}")
                QMessageBox.critical(self, "Erro", f"Falha na sincronização: {e}")

    def create_new_project(self):
        selected_item = self.list_works.currentItem()
        curr_work = selected_item.data(Qt.UserRole) if selected_item else None
        fname, _ = QFileDialog.getOpenFileName(self, "Selecionar DXF", "", "DXF Files (*.dxf)")
        if fname:
            try:
                base_name = os.path.basename(fname)
                project_name = os.path.splitext(base_name)[0]
                
                pid = self.db.create_project(project_name, fname, work_name=curr_work)
                self.load_projects()
                QMessageBox.information(self, "Sucesso", "Projeto criado!")
                
                self.project_created_globally.emit(curr_work or "Sem Obra", project_name, pid)
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao criar projeto: {e}")

    def move_project_to_work(self, project_data):
        """Move um projeto (pavimento) para outra obra."""
        pid = project_data.get('id')
        current_work = project_data.get('work_name') or "Sem Obra"
        project_name = project_data.get('name')
        
        # Obter lista de obras disponíveis
        works = self.db.get_all_works()
        if not works:
            QMessageBox.warning(self, "Aviso", "Não há obras disponíveis para mover.")
            return

        # Adicionar opção "Sem Obra" / "Remover da Obra" se já tiver obra
        if "Sem Obra" not in works:
            works.insert(0, "Sem Obra") # Opção para desvincular

        item, ok = QInputDialog.getItem(self, "Mover Pavimento", 
                                        f"Mover '{project_name}' de '{current_work}' para:", 
                                        works, 0, False)
        
        if ok and item:
            new_work = None if item == "Sem Obra" else item
            try:
                self.db.update_project_work(pid, new_work)
                self.load_projects() # Recarrega a view atual (o projeto vai sumir se o filtro for diferente)
                self.load_works_combo() # Atualiza contadores se existirem
                QMessageBox.information(self, "Sucesso", f"Projeto movido para '{item}'.")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao mover projeto: {e}")

    def confirm_delete_project_card(self, project_data):
        """Exclui um único projeto através do card."""
        pid = project_data.get('id')
        name = project_data.get('name')
        
        reply = QMessageBox.question(
            self, 
            "Excluir Pavimento", 
            f"Tem certeza que deseja excluir o pavimento '{name}'?\nEsta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_project_fully(pid)
                self.load_projects()
                QMessageBox.information(self, "Sucesso", "Pavimento excluído.")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao excluir: {e}")

    def export_project(self):
        row = self.table.currentRow()
        if row < 0: return
        p = self.table.item(row, 0).data(Qt.UserRole)
        data = self.db.export_project_data(p['id'])
        fname, _ = QFileDialog.getSaveFileName(self, "Exportar", f"{p['name']}.cadproj", "Project Files (*.cadproj)")
        if fname:
            with open(fname, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

    def import_project(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Importar", "", "Project Files (*.cadproj *.json)")
        if fname:
            try:
                with open(fname, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if self.db.import_project_data(data):
                    self.load_works_combo()
                    self.load_projects()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro: {e}")

    def open_details_dialog(self, project_data):
        """Abre o diálogo de detalhes (Ficha) com documentos."""
        project_id = project_data.get('id')
        documents = []
        if project_id:
            try:
                documents = self.db.get_project_documents(project_id)
            except Exception as e:
                print(f"Error fetching docs for dialog: {e}")
        
        # Ensure we have at least simulated DXF doc if real one not found but path exists?
        # For now just pass what we found
        
        dlg = ProjectDetailsDialog(project_data, documents=documents, parent=self)
        dlg.download_requested.connect(lambda doc_name: self.handle_dialog_download(project_id, doc_name, documents))
        dlg.exec()

    def handle_dialog_download(self, project_id, doc_name, documents):
        """Lida com solicitação de download vinda do diálogo."""
        doc = next((d for d in documents if d.get('name') == doc_name), None)
        # Fallback for main dxf if name mismatches but extension fits
        if not doc and doc_name.lower().endswith('.dxf'):
             doc = next((d for d in documents if d.get('name', '').lower().endswith('.dxf')), None)

        if doc:
            src_path = doc.get('path')
            if src_path and os.path.exists(src_path):
                dest, _ = QFileDialog.getSaveFileName(self, "Salvar Documento", doc_name, "All Files (*.*)")
                if dest:
                    try:
                        shutil.copy2(src_path, dest)
                        QMessageBox.information(self, "Sucesso", "Documento salvo com sucesso!")
                    except Exception as e:
                        QMessageBox.critical(self, "Erro", f"Falha ao salvar: {e}")
            else:
                 QMessageBox.warning(self, "Aviso", f"Arquivo não encontrado localmente:\\n{src_path}")
        else:
            QMessageBox.warning(self, "Aviso", "Registro do documento não encontrado.")

