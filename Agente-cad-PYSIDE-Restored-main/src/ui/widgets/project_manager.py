from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                                QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox, 
                                QListWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView,
                                 QComboBox, QInputDialog, QMenu, QToolButton, QTabWidget,
                                 QFrame, QScrollArea, QSplitter, QAbstractItemView, QProgressBar, QTextEdit, QGridLayout, QSizePolicy,
                                 QTreeWidget, QTreeWidgetItem)
from PySide6.QtCore import Signal, Qt, QSize, QEvent, QTimer, QProcess
from PySide6.QtGui import QIcon, QFont, QColor
import json
import re
import os
import sys
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from src.core.services.auth_service import AuthService
from src.core.services.sync_service import SyncService
from src.ui.widgets.admin_dashboard import AdminDashboard
from src.ui.widgets.central_controle import CentralControle
from src.ui.widgets.data_pipeline import DataPipelineView
from src.ui.widgets.dashboard_components import BreadcrumbWidget, MetricCard, DocumentItemWidget, DocumentationListWidget
from src.ui.components.project_cards import ProjectCard
from src.ui.dialogs.project_details_dialog import ProjectDetailsDialog
from src.ui.dialogs.document_upload_dialog import DocumentUploadDialog
from src.core.storage.project_storage import ProjectStorageManager
from src.core.cad_utils import get_cad_version_info
from src.ui.theme import Colors, Fonts, Radius, Contextual, Text, Surface, Accent, Semantic, Border

import re as _css_re
def _resolve_css(css: str) -> str:
    return _css_re.sub(r'{Colors\.(\w+)}', lambda m: getattr(Colors, m.group(1), m.group(0)), css)


class ProjectManager(QWidget):
    project_selected = Signal(str, str, str)  # id, name, dxf_path
    project_created_globally = Signal(str, str, str) # work_name, project_name, project_id
    obra_created_globally = Signal(str) # work_name
    sync_complete_signal = Signal(bool, str) # success, project_id
    request_tab_switch = Signal(int)              # index of tab to switch to
    request_open_bruto = Signal(str, str)         # obra_name, file_path
    request_open_reverse_hub = Signal(str, str)   # obra_name, file_path

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
        self._auto_rag_process = None
        self._auto_rag_active_work = None
        self._auto_rag_pending_work = None
        self.sync_complete_signal.connect(self._on_sync_complete)
        # Lazy tab rendering — só renderiza o tab visível
        self._classified_docs_cache: dict = {}
        self._dirty_phases: set = set(range(1, 9))
        
        # Este componente vive dentro do QStackedWidget da janela principal.
        self.setWindowTitle("Gerenciador de Projetos - Vision AI")
        self.setWindowFlags(Qt.Widget)
        
        self.apply_styles()
        self.setup_ui()
        self.load_works_combo()
        self.load_projects()
        # Força refresh dos documentos após o event loop iniciar
        QTimer.singleShot(300, self._refresh_phase_tabs)

    def apply_styles(self):
        # DS v2.0 — tokens from src/ui/theme.py
        self.setStyleSheet(_resolve_css("""
            QWidget {
                background-color: {Colors.BG_DEEP};
                color: {Colors.TEXT_PRIMARY};
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                font-size: 11px;
            }
            QPushButton#PrimaryButton {
                background-color: {Colors.ACCENT_BLUE};
                color: {Colors.TEXT_BRIGHT};
                font-weight: bold;
                padding: 6px 14px;
                border: none;
                border-radius: 6px;
                font-size: 11px;
            }
            QPushButton#PrimaryButton:hover { background-color: {Colors.ACCENT_BLUE_HOVER}; }
            QTableWidget {
                background: transparent; 
                color: {Colors.TEXT_PRIMARY};
                font-size: 11px; 
                border: 1px solid rgba(255, 255, 255, 10);
                border-radius: 6px;
                gridline-color: transparent;
            }
            QTableWidget::item {
                border-bottom: 1px solid rgba(255, 255, 255, 5);
                padding: 6px 8px;
            }
            QTableWidget::item:alternate {
                background: rgba(255, 255, 255, 3);
            }
            QTableWidget::item:hover {
                background: rgba(180, 80, 200, 15);
            }
            QTableWidget::item:selected {
                background: rgba(180, 80, 200, 30);
                color: {Colors.TEXT_PRIMARY};
            }
            QHeaderView::section {
                background-color: {Colors.BG_SURFACE};
                color: {Colors.TEXT_SECONDARY};
                font-weight: bold; font-size: 11px;
                border: none;
                border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
                padding: 6px 8px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QScrollBar:vertical {
                border: none; background: {Colors.BG_PANEL}; width: 6px;
            }
            QScrollBar::handle:vertical {
                background: {Colors.BORDER_INPUT}; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar:horizontal {
                border: none; background: {Colors.BG_PANEL}; height: 6px;
            }
            QScrollBar::handle:horizontal {
                background: {Colors.BORDER_INPUT}; border-radius: 3px; min-width: 20px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QToolTip {
                background: {Colors.BG_CARD};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_ACCENT};
                font-size: 11px;
                padding: 4px 8px;
            }
        """))

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 1. Top Bar — DS: h=40px, logo 14px, margins 16/0
        self.top_bar = QFrame()
        self.top_bar.setFixedHeight(40)
        self.top_bar.setObjectName("TopBar")
        self.top_bar.setStyleSheet(_resolve_css("""
            #TopBar {
                background-color: {Colors.BG_DEEP};
                border-bottom: 1px solid {Colors.BORDER_DEFAULT};
            }
        """))

        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(16, 0, 16, 0)
        top_layout.setSpacing(12)

        logo_lbl = QLabel("GERENCIAR PROJETOS")
        logo_lbl.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {Colors.ACCENT_BRAND}; ")
        top_layout.addWidget(logo_lbl)
        
        top_layout.addSpacing(30)
        self.breadcrumbs = BreadcrumbWidget()
        top_layout.addWidget(self.breadcrumbs)
        
        top_layout.addStretch()
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar obras ou projetos...")
        self.search_box.setFixedWidth(220)
        self.search_box.setStyleSheet(_resolve_css("""
            QLineEdit {
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 4px 10px;
                color: {Colors.TEXT_PRIMARY};
                font-size: 11px;
            }
            QLineEdit:focus { border-color: {Colors.ACCENT_PRIMARY}; }
        """))
        top_layout.addWidget(self.search_box)

        self.user_btn = QPushButton("ADMIN")
        self.user_btn.setFixedHeight(24)
        self.user_btn.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_INPUT};
                border-radius: 12px;
                padding: 0 12px;
                color: {Colors.ACCENT_GOLD};
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { border-color: {Colors.ACCENT_GOLD}; }
        """))
        top_layout.addWidget(self.user_btn)
        
        self.layout.addWidget(self.top_bar)

        # 2. Main Tabs
        self.tabs = QTabWidget()
        self.tabs.setObjectName("ProjectTabs")
        self.tabs.setStyleSheet(_resolve_css("""
            QTabWidget::pane { border: none; border-top: 1px solid {Colors.BORDER_DEFAULT}; background: {Colors.BG_DEEP}; }
            QTabBar::tab {
                background: {Colors.BG_DEEP};
                color: {Colors.TEXT_SECONDARY};
                padding: 7px 18px;
                font-weight: 500;
                font-size: 11px;
                border: none;
                border-right: 1px solid {Colors.BORDER_DEFAULT};
                border-bottom: 2px solid transparent;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background: {Colors.BG_SECONDARY};
                color: {Colors.ACCENT_PRIMARY};
                border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
            }
            QTabBar::tab:hover:!selected {
                background: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }
        """))
        
        self.local_tab = QWidget()
        self.setup_local_tab()
        self.tabs.addTab(self.local_tab, "MEUS PROJETOS")
        
        self.community_tab = QWidget()
        self.setup_community_tab()
        self.tabs.addTab(self.community_tab, "CURADORIA RAG/MCP")

        self.central_tab = CentralControle(self.db, self.memory, self.auth_service)
        self.tabs.addTab(self.central_tab, "CENTRAL DE CONTROLE")

        # PM-008: DataPipelineView na navegação principal (antes estava em AdminDashboard admin-only)
        try:
            self.data_pipeline_tab = DataPipelineView()
            self.tabs.addTab(self.data_pipeline_tab, "📊 PIPELINE")
        except Exception:
            pass
            
        self.layout.addWidget(self.tabs)

    def setup_local_tab(self):
        layout = QHBoxLayout(self.local_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.local_splitter = QSplitter(Qt.Horizontal)
        self.local_splitter.setHandleWidth(1)
        self.local_splitter.setStyleSheet(f"QSplitter::handle {{ background: {Colors.BORDER_DEFAULT}; }}")
        
        # --- SIDEBAR: OBRAS — DS: 260px, margem 12/16 ---
        self.works_sidebar = QFrame()
        self.works_sidebar.setFixedWidth(260)
        self.works_sidebar.setObjectName("WorksSidebar")
        self.works_sidebar.setStyleSheet(_resolve_css("""
            #WorksSidebar {
                background-color: {Colors.BG_PANEL};
                border-right: 1px solid {Colors.BORDER_DEFAULT};
            }
        """))
        sidebar_layout = QVBoxLayout(self.works_sidebar)
        sidebar_layout.setContentsMargins(12, 14, 12, 14)
        sidebar_layout.setSpacing(8)

        sidebar_header = QHBoxLayout()
        sidebar_title = QLabel("MINHAS OBRAS")
        sidebar_title.setStyleSheet(f"font-weight: bold; font-size: 10px; color: {Colors.TEXT_SECONDARY}; ")
        sidebar_header.addWidget(sidebar_title)
        
        sidebar_header.addStretch()
        
        self.btn_refresh_works = QPushButton("🔄")
        self.btn_refresh_works.setToolTip("Atualizar Lista de Obras")
        self.btn_refresh_works.setFixedSize(24, 24)
        self.btn_refresh_works.setStyleSheet(_resolve_css("""
            QPushButton {
                background: transparent;
                border: none;
                color: {Colors.TEXT_MUTED};
                font-size: 14px;
            }
            QPushButton:hover {
                color: {Colors.ACCENT_PRIMARY};
                background: {Colors.BG_SURFACE};
                border-radius: 4px;
            }
        """))
        self.btn_refresh_works.clicked.connect(self.load_works_combo)
        sidebar_header.addWidget(self.btn_refresh_works)
        
        sidebar_layout.addLayout(sidebar_header)

        # Busca Obras
        self.edit_search_works = QLineEdit()
        self.edit_search_works.setPlaceholderText("Filtrar obras...")
        self.edit_search_works.setFixedHeight(26)
        self.edit_search_works.setStyleSheet(_resolve_css("""
            QLineEdit {
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                color: {Colors.TEXT_PRIMARY};
            }
            QLineEdit:focus { border-color: {Colors.ACCENT_PRIMARY}; }
        """))
        self.edit_search_works.textChanged.connect(self._filter_works_list)
        sidebar_layout.addWidget(self.edit_search_works)

        # Lista de Obras
        self.list_works = QListWidget()
        self.list_works.setObjectName("WorksList")
        self.list_works.setStyleSheet(_resolve_css("""
            #WorksList {
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
                outline: none;
            }
            #WorksList::item {
                padding: 7px 10px;
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
            }
            #WorksList::item:selected {
                background-color: {Colors.BG_SECONDARY};
                color: {Colors.ACCENT_PRIMARY};
                font-weight: bold;
                border-left: 2px solid {Colors.ACCENT_PRIMARY};
            }
            #WorksList::item:hover:!selected {
                background-color: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }
        """))
        self.list_works.currentItemChanged.connect(self.load_projects)
        sidebar_layout.addWidget(self.list_works)

        # Botão + Obra na base da sidebar
        btn_add_work_sidebar = QPushButton("+ Criar Nova Obra")
        btn_add_work_sidebar.setFixedHeight(28)
        btn_add_work_sidebar.setStyleSheet(_resolve_css("""
            QPushButton {
                background-color: transparent;
                border: 1px dashed {Colors.BORDER_INPUT};
                border-radius: 4px;
                color: {Colors.ACCENT_MINT};
                font-weight: bold;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: {Colors.BG_HOVER};
                border-color: {Colors.ACCENT_MINT};
            }
        """))
        btn_add_work_sidebar.clicked.connect(self.add_work)
        sidebar_layout.addWidget(btn_add_work_sidebar)

        self.local_splitter.addWidget(self.works_sidebar)
        
        # --- CENTRAL AREA ---
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(20, 16, 20, 16)
        central_layout.setSpacing(10)
        
        # --- HEADER (Agora mais limpo) ---
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(0, 0, 0, 8)
        self.header_layout.setSpacing(8)
        
        # No lugar do combo, colocamos o nome da obra selecionada em destaque
        self.lbl_selected_work = QLabel("Selecione uma Obra")
        self.lbl_selected_work.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Colors.TEXT_BRIGHT}; ")
        self.header_layout.addWidget(self.lbl_selected_work)

        # Código público (App de Consulta) — só aparece pra obras Drive já
        # publicadas; vazio/oculto pra obras locais ou ainda não sincronizadas
        # [2026-07-13].
        self.lbl_code_publico_obra = QLabel("")
        self.lbl_code_publico_obra.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED}; margin-left: 10px;")
        self.lbl_code_publico_obra.setVisible(False)
        self.header_layout.addWidget(self.lbl_code_publico_obra)

        self.header_layout.addStretch()
        
        # Botão de Remover Obra (inicialmente escondido)
        self.btn_delete_work = QPushButton("✕ Remover Obra")
        self.btn_delete_work.setFixedHeight(26)
        self.btn_delete_work.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BG_DANGER_DARK};
                color: {Colors.ACCENT_DANGER};
                border: 1px solid {Colors.ACCENT_DANGER};
                border-radius: 4px;
                padding: 3px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background: {Colors.ACCENT_DANGER}; color: {Colors.TEXT_BRIGHT}; }
        """))
        self.btn_delete_work.clicked.connect(self.delete_current_work)
        self.btn_delete_work.setVisible(False)
        self.btn_delete_work.setVisible(False)
        self.header_layout.addWidget(self.btn_delete_work)
        
        # Botão Sync Obra Completa
        self.btn_sync_work = QPushButton("⟳ Sincronizar Obra")
        self.btn_sync_work.setFixedHeight(26)
        self.btn_sync_work.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BG_CARD};
                color: {Colors.ACCENT_PRIMARY};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 4px;
                padding: 3px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DEEP}; }
        """))
        self.btn_sync_work.clicked.connect(self.sync_current_work)
        self.btn_sync_work.setVisible(False)
        self.header_layout.addWidget(self.btn_sync_work)

        self.header_layout.addStretch()
        
        central_layout.addLayout(self.header_layout)
        
        # Título da seção de documentos abaixo do nome da obra
        self.lbl_documents_title = QLabel("DOCUMENTOS DO PROJETO")
        self.lbl_documents_title.setStyleSheet(_resolve_css("""
            font-size: 10px;
            font-weight: bold;
            color: {Colors.ACCENT_PRIMARY};
            
            padding: 0;
            margin: 0;
        """))
        central_layout.addWidget(self.lbl_documents_title)

        # Container para o fluxo de fases (antigo sub_tabs, mas agora tratado como corpo principal)
        # Mantendo o QTabWidget para as 8 fases, mas agora ele é o foco principal
        self.phase_tabs = QTabWidget()
        self.phase_tabs.setObjectName("PhaseTabs")
        self.phase_tabs.setStyleSheet(_resolve_css("""
            QTabWidget::pane {
                border: 1px solid {Colors.BORDER_DEFAULT};
                background: {Colors.BG_DEEP};
                border-radius: 6px;
            }
            QTabBar::tab {
                background: {Colors.BG_PANEL};
                color: {Colors.TEXT_SECONDARY};
                padding: 6px 14px;
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-bottom: none;
                margin-right: 2px;
                font-weight: 500;
                font-size: 11px;
                border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected {
                background: {Colors.BG_SECONDARY};
                color: {Colors.ACCENT_PRIMARY};
                border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
            }
            QTabBar::tab:hover:!selected {
                background: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }
        """))

        # Criar abas de fases + Pré-ficha intercalada após fase 2
        # Layout: 1. Recepção | 2. Triagem | 2.1 Pré-ficha | 3. Pré-análise | … | 8. Revisão
        _FICHA_IDX = 2
        self.phase_tab_widgets = {}
        _QColor = __import__('PySide6.QtGui', fromlist=['QColor']).QColor

        # Fases 1-2
        for phase_num in range(1, 3):
            phase_tab = self._create_phase_tab(phase_num)
            phase_name = self._get_phase_name(phase_num)
            self.phase_tabs.addTab(phase_tab, f"{phase_num}. {phase_name}")
            self.phase_tab_widgets[phase_num] = phase_tab

        # ── 2.1 Pré-ficha Obra (índice 2) ────────────────────────────────────────
        ficha_tab = self._create_ficha_obra_tab()
        self.phase_tabs.addTab(ficha_tab, "2.1 Ficha Pré-Obra [F1]")
        self.phase_tab_widgets['ficha'] = ficha_tab
        self.phase_tabs.tabBar().setTabTextColor(_FICHA_IDX, _QColor(Contextual.GOLD))

        # Fases 3-8
        for phase_num in range(3, 9):
            phase_tab = self._create_phase_tab(phase_num)
            phase_name = self._get_phase_name(phase_num)
            self.phase_tabs.addTab(phase_tab, f"{phase_num}. {phase_name}")
            self.phase_tab_widgets[phase_num] = phase_tab

        # Spacer entre tabs 1-8 e a Ficha via stylesheet no tabBar
        # (obtido via setTabData para indicar separação visual)
        self.phase_tabs.setCurrentIndex(0)
        self.phase_tabs.currentChanged.connect(self._on_phase_tab_switched)
        central_layout.addWidget(self.phase_tabs)
        self.local_splitter.addWidget(central_widget)
        
        self.local_splitter.setSizes([260, 1])  # DS: sidebar 260px
        layout.addWidget(self.local_splitter)

    def setup_pavimentos_container(self, parent_layout):
        """Prepara o container de pavimentos (lista compacta) para Fase 2."""
        # ── Toolbar: reload ───────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 4, 0, 4)
        toolbar.setSpacing(6)

        self._lbl_pav_count = QLabel("Pavimentos Limpos")
        self._lbl_pav_count.setStyleSheet(_resolve_css(
            "color: {Colors.ACCENT_PRIMARY}; font-size: 11px; font-weight: bold;"
            " background: transparent; border: none;"
        ))
        toolbar.addWidget(self._lbl_pav_count)
        toolbar.addStretch()

        btn_reload_pav = QPushButton("↻ Recarregar")
        btn_reload_pav.setFixedHeight(24)
        btn_reload_pav.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                padding: 1px 10px; font-size: 10px;
            }
            QPushButton:hover { color: {Colors.TEXT_PRIMARY}; border-color: {Colors.ACCENT_PRIMARY}; }
        """))
        btn_reload_pav.clicked.connect(self.load_projects)
        toolbar.addWidget(btn_reload_pav)

        parent_layout.addLayout(toolbar)

        # ── Scroll area com lista compacta ────────────────────────────────────
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(_resolve_css("""
            QScrollArea {
                border: 1px solid {Colors.BORDER_DEFAULT};
                background: {Colors.BG_DEEP};
                border-radius: 6px;
            }
            QScrollBar:vertical { border: none; background: {Colors.BG_DEEP}; width: 6px; margin: 0; }
            QScrollBar::handle:vertical { background: {Colors.BG_CARD}; min-height: 16px; border-radius: 3px; }
        """))

        self.cards_container = QWidget()
        self.cards_container.setObjectName("CardsContainer")
        self.cards_container.setStyleSheet("#CardsContainer { background: transparent; }")

        # VBoxLayout compacto para linhas de cards
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(2)
        self.cards_layout.setContentsMargins(6, 6, 6, 6)
        self.cards_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.cards_container)
        parent_layout.addWidget(self.scroll_area)

    def setup_pavement_selector_combo(self, parent_layout, phase_num=3):
        """Prepara o seletor de pavimento (ComboBox) para as Fases 3–7."""
        container = QFrame()
        container.setStyleSheet(f"background: {Colors.BG_PANEL}; border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 6px; padding: 10px;")
        layout = QHBoxLayout(container)

        phase_map = {
            3: 'INTERPRETAÇÃO/EXTRAÇÃO',
            4: 'DADOS SYNC ROBOS',
            5: 'SCRIPTS ROBOS SRC',
            6: 'CONVERSÃO SCRIPTS DXF',
            7: 'UNIFICAÇÃO DXF PAVIMENTO',
        }
        proc_text = phase_map.get(phase_num, 'PROCESSO')
        
        lbl = QLabel(f"📍 SELECIONE O PAVIMENTO PARA {proc_text}:")
        lbl.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY}; font-weight: bold; font-size: 11px;")
        layout.addWidget(lbl)
        
        cmb = QComboBox()
        cmb.setStyleSheet(_resolve_css("""
            QComboBox {
                background: {Colors.BG_SURFACE}; border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                padding: 8px; color: {Colors.TEXT_BRIGHT}; font-size: 12px; min-width: 250px;
            }
            QComboBox:focus { border: 1px solid {Colors.ACCENT_PRIMARY}; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; border: none; }
        """))
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
            lbl_prog.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9px; font-weight: bold;")
            prog_layout.addWidget(lbl_prog)
            
            self.progress_scripts = QProgressBar()
            self.progress_scripts.setFixedHeight(12)
            self.progress_scripts.setStyleSheet(_resolve_css("""
                QProgressBar {
                    background: {Colors.BG_DEEP}; border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 6px;
                    text-align: center; color: transparent;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {Colors.ACCENT_PRIMARY}, stop:1 {Colors.ACCENT_MINT});
                    border-radius: 5px;
                }
            """))
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
        elif phase_num == 6:
            self.cmb_pavements_conversion = cmb
            self.phase6_pavement_selector = container
        elif phase_num == 7:
            self.cmb_pavements_unification = cmb
            self.phase7_pavement_selector = container

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
        elif sender in (getattr(self, 'cmb_pavements_conversion', None),
                        getattr(self, 'cmb_pavements_unification', None)):
            self._refresh_phase_tabs()

    def setup_specs_container(self, parent_layout):
        """Prepara o formulário de especificações para ser inserido na Fase 1."""
        container = QFrame()
        container.setStyleSheet(_resolve_css("""
            QFrame {
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 6px;
            }
        """))
        root = QVBoxLayout(container)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(0)

        # ── Header row ──────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 8)
        title_lbl = QLabel("Especificações da Obra")
        title_lbl.setStyleSheet(_resolve_css("""
            font-size: 11px; font-weight: 600;
            color: {Colors.TEXT_SECONDARY}; 
            border: none; background: transparent;
        """))
        hdr.addWidget(title_lbl)
        hdr.addStretch()

        self.btn_save_work_specs = QPushButton("Salvar")
        self.btn_save_work_specs.setCursor(Qt.PointingHandCursor)
        self.btn_save_work_specs.setFixedHeight(24)
        self.btn_save_work_specs.setStyleSheet(_resolve_css("""
            QPushButton {
                background-color: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT};
                border-radius: 3px; font-size: 10px; font-weight: 600; padding: 0 10px;
            }
            QPushButton:hover { background-color: {Colors.ACCENT_BLUE_HOVER}; }
            QPushButton:disabled { background-color: {Colors.BG_SURFACE}; color: {Colors.TEXT_MUTED}; }
        """))
        self.btn_save_work_specs.clicked.connect(self.save_work_metadata)
        hdr.addWidget(self.btn_save_work_specs)
        root.addLayout(hdr)

        # ── Separator ───────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(_resolve_css("border: none; border-top: 1px solid {Colors.BORDER_SUBTLE}; margin: 0;"))
        root.addWidget(sep)
        root.addSpacing(10)

        # ── Row 1: Nome da obra (full width) ────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        lbl_nome = QLabel("Obra")
        lbl_nome.setFixedWidth(52)
        lbl_nome.setStyleSheet(_resolve_css("font-size: 10px; color: {Colors.TEXT_MUTED}; border: none; background: transparent;"))
        self.f_work_name = QLineEdit()
        self.f_work_name.setPlaceholderText("Nome da obra")
        self.f_work_name.setFixedHeight(24)
        self.f_work_name.setStyleSheet(_resolve_css("""
            QLineEdit { background: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_SUBTLE};
                border-radius: 3px; padding: 0 8px; color: {Colors.TEXT_PRIMARY}; font-size: 11px; }
            QLineEdit:focus { border-color: {Colors.ACCENT_BLUE}; }
        """))
        row1.addWidget(lbl_nome)
        row1.addWidget(self.f_work_name)
        root.addLayout(row1)
        root.addSpacing(6)

        # ── Row 2: Pavimentos · Torres · Pilares ────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        def _inline_field(label, placeholder, attr_name):
            lbl = QLabel(label)
            lbl.setFixedWidth(52)
            lbl.setStyleSheet(_resolve_css("font-size: 10px; color: {Colors.TEXT_MUTED}; border: none; background: transparent;"))
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            inp.setFixedHeight(24)
            inp.setStyleSheet(_resolve_css("""
                QLineEdit { background: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_SUBTLE};
                    border-radius: 3px; padding: 0 8px; color: {Colors.TEXT_PRIMARY}; font-size: 11px; }
                QLineEdit:focus { border-color: {Colors.ACCENT_BLUE}; }
            """))
            setattr(self, attr_name, inp)
            return lbl, inp

        for label, placeholder, attr in [
            ("Pavimentos", "Ex: 15", "f_pavements"),
            ("Torres",     "Ex: 2",  "f_towers"),
            ("Pilares",    "—",      "f_pilares"),
        ]:
            lbl, inp = _inline_field(label, placeholder, attr)
            row2.addWidget(lbl)
            row2.addWidget(inp, 1)
        root.addLayout(row2)
        root.addSpacing(6)

        # ── Row 3: Vigas · Lajes ────────────────────────────────────
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        for label, placeholder, attr in [
            ("Vigas",  "—", "f_vigas"),
            ("Lajes",  "—", "f_lajes"),
        ]:
            lbl, inp = _inline_field(label, placeholder, attr)
            row3.addWidget(lbl)
            row3.addWidget(inp, 1)
        row3.addStretch(1)  # keep left-aligned
        root.addLayout(row3)
        root.addSpacing(8)

        # ── Notes ───────────────────────────────────────────────────
        lbl_notes = QLabel("Observações")
        lbl_notes.setStyleSheet(_resolve_css("font-size: 10px; color: {Colors.TEXT_MUTED}; border: none; background: transparent; margin-bottom: 2px;"))
        root.addWidget(lbl_notes)

        self.txt_specs = QTextEdit()
        self.txt_specs.setPlaceholderText("Notas técnicas, restrições, observações…")
        self.txt_specs.setFixedHeight(52)
        self.txt_specs.setStyleSheet(_resolve_css("""
            QTextEdit {
                background: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_SUBTLE}; border-radius: 3px;
                color: {Colors.TEXT_PRIMARY}; padding: 6px 8px; font-size: 11px;
            }
            QTextEdit:focus { border-color: {Colors.ACCENT_BLUE}; }
        """))
        root.addWidget(self.txt_specs)

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
        lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-weight: bold; font-size: 10px; border: none;")
        layout.addWidget(lbl)
        
        widget.setStyleSheet(_resolve_css("""
            QLineEdit {
                background: {Colors.BG_SURFACE}; border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                padding: 8px; color: {Colors.TEXT_BRIGHT}; font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid {Colors.ACCENT_PRIMARY}; }
        """))
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
        btn_save_specs.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BORDER_SUBTLE};
                color: {Colors.ACCENT_PRIMARY};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 4px;
                padding: 8px 15px;
                font-size: 11px;
                margin-top: 10px;
            }
            QPushButton:hover { background: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DEEP}; }
        """))
        btn_save_specs.clicked.connect(self.save_project_specs)
        layout.addWidget(btn_save_specs, 0, Qt.AlignRight)
        layout.addStretch()


    def _get_phase_name(self, phase_num):
        """Retorna o nome da fase."""
        names = {
            1: "INGESTÃO",
            2: "TRIAGEM",
            3: "INTERPRETACAO/EXTRACAO",
            4: "DADOS SYNC ROBOS",
            5: "SCRIPTS ROBOS SRC",
            6: "CONVERSAO SCRIPTS DXF",
            7: "UNIFICACAO DXF PAVIMENTO",
            8: "REVISAO E ENTREGA"
        }
        return names.get(phase_num, f"FASE {phase_num}")

    def _create_ficha_obra_tab(self) -> QWidget:
        """Aba Ficha da Obra — painel pré-interpretativo gerado após Pré-processar Todos."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        # ── Header ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        lbl_title = QLabel("📋  Ficha Pré-Obra [F1]")
        lbl_title.setStyleSheet(
            f"color: {Contextual.GOLD}; font-size: 15px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        hdr.addWidget(lbl_title)
        hdr.addStretch()

        btn_refresh_ficha = QPushButton("↻ Atualizar Ficha")
        btn_refresh_ficha.setFixedHeight(26)
        btn_refresh_ficha.setStyleSheet(f"""
            QPushButton {{
                background: rgba(230, 180, 0, 31); color: {Contextual.GOLD};
                border: 1px solid {Contextual.GOLD}; border-radius: 4px;
                padding: 1px 12px; font-size: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(230, 180, 0, 64); }}
        """)
        btn_refresh_ficha.clicked.connect(self._refresh_ficha_obra)
        hdr.addWidget(btn_refresh_ficha)
        lay.addLayout(hdr)

        # ── Descrição ────────────────────────────────────────────────────────
        desc = QLabel(
            "Esta ficha é gerada automaticamente após executar <b>⚡ Pré-processar Todos</b> "
            "no Diagnostic Hub. Consolida informações estruturais básicas da obra para "
            "orientar a Fase 3 de Interpretação/Extração."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(_resolve_css(
            "color: {Colors.TEXT_SECONDARY}; font-size: 11px;"
            " background: transparent; border: none;"
        ))
        lay.addWidget(desc)

        # ── Campos da ficha (labels dinâmicos) ───────────────────────────────
        fields_frame = QFrame()
        fields_frame.setStyleSheet(f"""
            QFrame {{
                background: {Surface.BASE};
                border: 1px solid {Contextual.BORDER_GOLD_DARK};
                border-radius: 8px;
            }}
        """)
        fields_lay = QVBoxLayout(fields_frame)
        fields_lay.setContentsMargins(16, 12, 16, 12)
        fields_lay.setSpacing(8)

        def _field_row(label: str, attr_name: str, default: str = "—") -> QLabel:
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent; border: none;")
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(12)
            lbl_k = QLabel(label)
            lbl_k.setFixedWidth(200)
            lbl_k.setStyleSheet(
                f"color: {Text.SECONDARY}; font-size: 11px; font-weight: bold;"
                " background: transparent; border: none;"
            )
            lbl_v = QLabel(default)
            lbl_v.setStyleSheet(
                f"color: {Text.PRIMARY}; font-size: 11px;"
                " background: transparent; border: none;"
            )
            lbl_v.setWordWrap(True)
            row_h.addWidget(lbl_k)
            row_h.addWidget(lbl_v, 1)
            fields_lay.addWidget(row_w)
            setattr(self, f'_ficha_{attr_name}', lbl_v)
            return lbl_v

        _field_row("Obra",                      "obra_nome")
        _field_row("Total de Pavimentos",        "total_pavimentos")
        _field_row("Pavimentos Aprovados",       "pavimentos_aprovados")
        _field_row("Pavimentos Processados",     "pavimentos_processados")
        _field_row("Recortes Torre (limpos)",    "recortes_torre")
        _field_row("Recortes Detalhe",           "recortes_detalhe")
        _field_row("Detalhes de Ingestão (DXF)", "detalhes_ingestao")
        _field_row("Docs de Ingestão (PDF/img)", "docs_ingestao")
        _field_row("Status Extração PIL",        "status_pil")
        _field_row("Status Extração VIG",        "status_vig")
        _field_row("Status Extração LAJ",        "status_laj")
        _field_row("Última execução pipeline",   "ultimo_pipeline")
        _field_row("Observações da obra",        "observacoes")

        lay.addWidget(fields_frame)

        # ── Log do último Pré-processar Todos ────────────────────────────────
        lbl_log_title = QLabel("Log — Último Pré-processamento")
        lbl_log_title.setStyleSheet(
            f"color: {Contextual.GOLD}; font-size: 11px; font-weight: bold;"
            " background: transparent; border: none; padding-top: 6px;"
        )
        lay.addWidget(lbl_log_title)

        from PySide6.QtWidgets import QPlainTextEdit
        self._ficha_log = QPlainTextEdit()
        self._ficha_log.setReadOnly(True)
        self._ficha_log.setMaximumHeight(180)
        self._ficha_log.setPlaceholderText(
            "Execute ⚡ Pré-processar Todos no Diagnostic Hub para gerar o log aqui."
        )
        self._ficha_log.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {Surface.DEEP}; color: {Text.SECONDARY};
                border: 1px solid {Contextual.BORDER_GOLD_DARK}; border-radius: 5px;
                font-size: 10px; font-family: monospace;
                padding: 6px;
            }}
        """)
        lay.addWidget(self._ficha_log)
        lay.addStretch()

        scroll.setWidget(container)
        return scroll

    def _refresh_ficha_obra(self):
        """Popula os campos da Ficha da Obra a partir do DB."""
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        obra = self.current_work_name or ""

        if not obra:
            if hasattr(self, '_ficha_obra_nome'):
                self._ficha_obra_nome.setText("— Selecione uma obra na sidebar")
            return

        try:
            conn = _sq3.connect(str(DB), timeout=5)
            conn.row_factory = _sq3.Row

            # Pavimentos
            cur = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE work_name=?", (obra,)
            )
            total_pav = cur.fetchone()[0]

            cur = conn.execute(
                "SELECT COUNT(*) FROM obra_triagem"
                " WHERE obra_name=? AND status='approved'"
                " AND suggested_category LIKE '%Bruto%'", (obra,)
            )
            pav_aprovados = cur.fetchone()[0]

            # Recortes
            cur = conn.execute(
                "SELECT recorte_type, COUNT(*) as n FROM obra_recortes"
                " WHERE obra_name=? GROUP BY recorte_type", (obra,)
            )
            recorte_counts = {r['recorte_type']: r['n'] for r in cur.fetchall()}

            # Processados (recortes com status=approved)
            cur = conn.execute(
                "SELECT COUNT(DISTINCT pavimento_name) FROM obra_recortes"
                " WHERE obra_name=? AND status='approved'", (obra,)
            )
            pav_processados = cur.fetchone()[0]

            # Detalhes ingestão
            cur = conn.execute(
                "SELECT COUNT(*) FROM project_documents"
                " WHERE work_name=? AND (category LIKE '%Detalhe%' OR category LIKE '%Detalhamento%')"
                " AND extension != '.dwg'", (obra,)
            )
            det_count = cur.fetchone()[0]

            cur = conn.execute(
                "SELECT COUNT(*) FROM project_documents"
                " WHERE work_name=? AND (category LIKE '%PDF%' OR category LIKE '%Reunio%')", (obra,)
            )
            docs_count = cur.fetchone()[0]

            # PIL/VIG/LAJ extraídos da Engenharia Reversa
            cur = conn.execute("SELECT COUNT(*) FROM reverse_eng_fichas WHERE obra_name=? AND classe='PL'", (obra,))
            pil_t = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM reverse_eng_fichas WHERE obra_name=? AND classe='PL' AND status='approved'", (obra,))
            pil_v = cur.fetchone()[0]

            cur = conn.execute("SELECT COUNT(*) FROM reverse_eng_fichas WHERE obra_name=? AND classe IN ('VL', 'VF')", (obra,))
            vig_t = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM reverse_eng_fichas WHERE obra_name=? AND classe IN ('VL', 'VF') AND status='approved'", (obra,))
            vig_v = cur.fetchone()[0]

            cur = conn.execute("SELECT COUNT(*) FROM reverse_eng_fichas WHERE obra_name=? AND classe='LAJ'", (obra,))
            laj_t = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM reverse_eng_fichas WHERE obra_name=? AND classe='LAJ' AND status='approved'", (obra,))
            laj_v = cur.fetchone()[0]

            # Último pipeline
            cur = conn.execute(
                "SELECT MAX(created_at) FROM obra_recortes WHERE obra_name=?", (obra,)
            )
            ultimo = (cur.fetchone()[0] or '—')[:16].replace('T', ' ')

            conn.close()

            def _set(attr, val):
                lbl = getattr(self, f'_ficha_{attr}', None)
                if lbl:
                    lbl.setText(str(val))

            _set('obra_nome',            obra)
            _set('total_pavimentos',     str(total_pav))
            _set('pavimentos_aprovados', str(pav_aprovados))
            _set('pavimentos_processados', str(pav_processados))
            _set('recortes_torre',       str(recorte_counts.get('torre', 0)))
            _set('recortes_detalhe',     str(recorte_counts.get('detalhe', 0)))
            _set('detalhes_ingestao',    str(det_count))
            _set('docs_ingestao',        str(docs_count))
            _set('status_pil',           f"{pil_v}/{pil_t} extraídos")
            _set('status_vig',           f"{vig_v}/{vig_t} extraídas")
            _set('status_laj',           f"{laj_v}/{laj_t} extraídas")
            _set('ultimo_pipeline',      ultimo)
            _set('observacoes',          "Ficha gerada automaticamente pelo sistema.")

        except Exception as e:
            if hasattr(self, '_ficha_obra_nome'):
                self._ficha_obra_nome.setText(f"Erro: {e}")

    def _create_phase_tab(self, phase_num):
        """Cria uma aba de fase com descrição e classes de itens."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Injetar Especificações Técnicas + botão Indexar na Fase 1
        if phase_num == 1:
            self.setup_specs_container(layout)
            layout.addSpacing(10)

            # Botão unificado: Indexar DB + RAG em sequência
            ingest_row = QHBoxLayout()
            ingest_row.setSpacing(10)
            ingest_row.setContentsMargins(0, 0, 0, 0)

            self._btn_ingest_all = QPushButton("⚡ Atualizar Obra (DB + RAG Local)")
            self._btn_ingest_all.setToolTip(
                "Executa duas etapas seguras em sequência:\n"
                "① Fase 1 → DB: registra arquivos físicos novos no banco\n"
                "② RAG local: atualiza o snapshot de contexto desta obra\n\n"
                "Dados em quarentena permanecem locais e nunca ensinam o RAG global."
            )
            self._btn_ingest_all.setStyleSheet(f"""
                QPushButton {{
                    background: {Colors.BG_CARD}; color: {Colors.ACCENT_MINT};
                    border: 1px solid {Colors.ACCENT_MINT}; border-radius: 4px;
                    padding: 5px 12px; font-size: 11px; font-weight: bold;
                }}
                QPushButton:hover {{ background: rgba(0, 230, 170, 31); }}
                QPushButton:disabled {{ color: {Colors.TEXT_DIM}; border-color: {Colors.BORDER_DEFAULT}; }}
            """)

            self._lbl_index_badge = QLabel("—")
            self._lbl_index_badge.setStyleSheet(
                f"color: {Colors.TEXT_DIM}; font-size: 11px; font-weight: bold;"
                " background: transparent; border: none; padding: 0 4px;"
            )
            self._lbl_index_badge.setToolTip("Arquivos indexados no DB para esta obra")

            self._lbl_rag_status = QLabel("—")
            self._lbl_rag_status.setStyleSheet(
                f"color: {Colors.TEXT_DIM}; font-size: 11px;"
                " background: transparent; border: none; padding: 0 4px;"
            )

            self._btn_ingest_all.clicked.connect(self._on_ingest_all_clicked)
            ingest_row.addWidget(self._btn_ingest_all)
            ingest_row.addWidget(self._lbl_index_badge)
            ingest_row.addStretch()
            ingest_row_w = QWidget()
            ingest_row_w.setLayout(ingest_row)
            layout.addWidget(ingest_row_w)

            # Status RAG (linha separada abaixo do botão)
            layout.addWidget(self._lbl_rag_status)
            layout.addSpacing(6)

            # Atualizar badges imediatamente
            self._refresh_index_badge()
            self._refresh_rag_badge()

        # Descrição da fase
        desc_label = QLabel(self.PHASE_DESCRIPTIONS.get(phase_num, ""))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(_resolve_css("""
            QLabel {
                color: {Colors.TEXT_SECONDARY}; font-size: 12px; padding: 15px;
                background: {Colors.BG_PANEL}; border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 6px;
                line-height: 1.6;
            }
        """))
        layout.addWidget(desc_label)

        # Painel IA Triagem — sugestões do RAG para Fase 2
        if phase_num == 2:
            self._build_triagem_panel(layout)
            layout.addSpacing(8)
            self._build_preprocess_panel(layout)
            layout.addSpacing(8)
            self._build_projetos_finalizados_panel(layout)
            layout.addSpacing(8)
            self._build_detalhamentos_especificos_panel(layout)
            layout.addSpacing(8)

        # Injetar o ComboBox de seleção GLOBAL no topo das Fases 4, 5, 6 e 7
        if phase_num in [4, 5, 6, 7]:
            self.setup_pavement_selector_combo(layout, phase_num=phase_num)
            layout.addSpacing(10)
        
        # Classes de itens desta fase
        classes = self.PHASE_CLASSES.get(phase_num, [])
        for class_name in classes:
            # Phase 2: Detalhamentos e Projetos tem panels dedicados acima
            if phase_num == 2 and class_name in (
                "Detalhamentos Específicos",
                "Projetos Finalizados para Engenharia Reversa"
            ):
                continue
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

            # PM-006: Injetar grid Eng. Reversa na Fase 2
            if phase_num == 2 and class_name == "Projetos Finalizados para Engenharia Reversa":
                docs_container = class_widget.property("docs_container")
                if docs_container:
                    self._build_eng_reversa_grid(docs_container.layout())

            # PM-004: Injetar grid DXF granular na Fase 6
            if phase_num == 6:
                docs_container = class_widget.property("docs_container")
                if docs_container:
                    self._build_fase6_class_grid(docs_container.layout(), class_name)

            # PM-005: Injetar grid consolidação na Fase 7
            if phase_num == 7:
                docs_container = class_widget.property("docs_container")
                if docs_container:
                    self._build_fase7_class_grid(docs_container.layout(), class_name)

            # PM-007: Injetar dashboard na Fase 8
            if phase_num == 8:
                docs_container = class_widget.property("docs_container")
                if docs_container:
                    self._build_fase8_dashboard(docs_container.layout())
        
        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _create_class_widget(self, phase_num, class_name):
        """Cria um widget para uma classe de itens com lista de documentos e botões de ação."""
        class_frame = QFrame()
        class_frame.setStyleSheet(_resolve_css("""
            QFrame {
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                padding: 0px;
            }
        """))
        
        class_layout = QVBoxLayout(class_frame)
        class_layout.setContentsMargins(15, 15, 15, 15)
        class_layout.setSpacing(10)
        
        # Header da classe com botões de ação
        header_layout = QHBoxLayout()
        
        class_title = QLabel(class_name)
        class_title.setStyleSheet(_resolve_css("""
            QLabel {
                color: {Colors.ACCENT_PRIMARY};
                font-weight: bold;
                font-size: 13px;
            }
        """))
        header_layout.addWidget(class_title)
        header_layout.addStretch()
        
        # Botão Converter Todos DWG → DXF 2018 (apenas para Fase 1)
        if phase_num == 1:
            btn_convert_all = QPushButton("⚡ Converter Todos → DXF 2018")
            btn_convert_all.setStyleSheet(_resolve_css("""
                QPushButton {
                    background: rgba(26, 77, 46, 1);
                    color: {Colors.ACCENT_SUCCESS_ALT};
                    border: 1px solid {Colors.ACCENT_SUCCESS_ALT};
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: {Colors.ACCENT_SUCCESS_ALT};
                    color: {Colors.BG_DEEP};
                }
            """))
            btn_convert_all.setToolTip("Converte todos os arquivos DWG desta classe para DXF 2018 ASCII")
            btn_convert_all.clicked.connect(lambda: self._convert_all_dwg_in_class(phase_num, class_name))
            header_layout.addWidget(btn_convert_all)

        # Badge de contagem — todas as 4 classes da Fase 1
        if phase_num == 1:
            count_badge = QLabel("—")
            count_badge.setFixedHeight(24)
            count_badge.setStyleSheet(
                f"color: {Colors.TEXT_DIM}; font-size: 11px; font-weight: bold;"
                f" padding: 0 8px; background: transparent; border: none;"
            )
            count_badge.setToolTip("Contagem de arquivos nesta categoria (DWG | DXF convertidos)")
            header_layout.addWidget(count_badge)
            class_frame.setProperty("count_badge", count_badge)

        # Botão Adicionar Documento
        btn_add = QPushButton("+ Adicionar")
        btn_add.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BORDER_SUBTLE};
                color: {Colors.ACCENT_PRIMARY};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: {Colors.ACCENT_PRIMARY};
                color: {Colors.BG_DEEP};
            }
        """))
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
        docs_container_layout.setSpacing(2)
        
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
            lbl_db.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY}; font-weight: bold; font-size: 11px;")
            db_layout.addWidget(lbl_db)

            def _make_tree(cn):
                t = QTreeWidget()
                if cn == "Scripts Pilares":
                    t.setHeaderLabels(["Item", "Nome", "Cima", "Grades", "ABCD", "Ação"])
                    t.setColumnWidth(0, 60); t.setColumnWidth(1, 150)
                    t.setColumnWidth(2, 60); t.setColumnWidth(3, 60); t.setColumnWidth(4, 60)
                else:
                    t.setHeaderLabels(["Item", "Nome", "Status", "Ação"])
                    t.setColumnWidth(0, 60); t.setColumnWidth(1, 150); t.setColumnWidth(2, 80)
                t.setStyleSheet(f"QTreeWidget {{ background: {Colors.BG_DEEP}; border: 1px solid {Colors.BORDER_DEFAULT}; }}")
                t.setMinimumHeight(200)
                return t

            # Fase 3 "Vigas" usa sub-abas Para / Passam
            if phase_num == 3 and class_name == "Vigas":
                lv_tabs = QTabWidget()
                lv_tabs.setStyleSheet(
                    f"QTabBar::tab {{ background:{Colors.BG_CARD}; color:{Colors.TEXT_SECONDARY};"
                    f" border-radius:3px; padding:3px 10px; margin-right:2px; }}"
                    f"QTabBar::tab:selected {{ background:{Contextual.FOREST}; color:{Text.BRIGHT}; font-weight:bold; }}"
                    f"QTabWidget::pane {{ border:1px solid {Colors.BORDER_DEFAULT}; }}"
                )
                tree_para  = _make_tree(class_name)
                tree_passa = _make_tree(class_name)
                lv_tabs.addTab(tree_para,  "Vigas Para")
                lv_tabs.addTab(tree_passa, "Vigas Passam")
                # Carregar só ao selecionar a sub-aba
                lv_tabs.currentChanged.connect(
                    lambda idx, cn=class_name, tp=tree_para, ts=tree_passa:
                        self._refresh_phase3_data(cn, tp, "Para") if idx == 0
                        else self._refresh_phase3_data(cn, ts, "Passa")
                )
                db_layout.addWidget(lv_tabs)
                tree = tree_para  # referência legacy (para refresh btn)
                class_frame.setProperty("db_tree_para",  tree_para)
                class_frame.setProperty("db_tree_passa", tree_passa)
                class_frame.setProperty("db_lv_tabs",    lv_tabs)
                class_frame.setProperty("db_tree", None)  # sem tree unificada
            else:
                tree = _make_tree(class_name)
                db_layout.addWidget(tree)
                class_frame.setProperty("db_tree", tree)

            class_layout.addWidget(db_list_container)

            # Botão de Refresh Específico
            btn_refresh = QPushButton("🔄 Atualizar")
            btn_refresh.setCursor(Qt.PointingHandCursor)
            btn_refresh.setStyleSheet(f"background: transparent; color: {Colors.TEXT_SECONDARY}; border: none; font-size: 10px;")
            if phase_num == 3:
                if class_name == "Vigas":
                    # Refresh: recarrega a sub-aba ativa
                    btn_refresh.clicked.connect(
                        lambda checked=False, cn=class_name, cf=class_frame:
                            self._refresh_lv_active_tab(cn, cf)
                    )
                else:
                    btn_refresh.clicked.connect(lambda checked=False, cn=class_name, t=tree: self._refresh_phase3_data(cn, t))
            elif phase_num == 5:
                btn_refresh.clicked.connect(lambda checked=False, cn=class_name, t=tree: self._refresh_phase5_data(cn, t))
            else:
                btn_refresh.clicked.connect(lambda checked=False, cn=class_name, t=tree: self._refresh_phase4_data(cn, t))
            header_layout.addWidget(btn_refresh)
            
            # Botão Sincronizar Robô (Removido conforme solicitado - apenas listar dados)
            # if phase_num == 4:
            #     ...

        return class_frame

    def _refresh_lv_active_tab(self, class_name: str, class_frame):
        """Recarrega a sub-aba LV ativa (Para ou Passa)."""
        lv_tabs = class_frame.property("db_lv_tabs")
        tree_para  = class_frame.property("db_tree_para")
        tree_passa = class_frame.property("db_tree_passa")
        if lv_tabs is None:
            return
        idx = lv_tabs.currentIndex()
        if idx == 0:
            self._refresh_phase3_data(class_name, tree_para, "Para")
        else:
            self._refresh_phase3_data(class_name, tree_passa, "Passa")

    def _refresh_phase3_data(self, class_name, tree_widget, pp_filter: str = ""):
        """Carrega dados do SQLite para a lista.

        pp_filter: "Para" | "Passa" | "" (sem filtro — pilares/lajes)
        """
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

        # CAD-15: carregar scores de completude em batch
        completude_scores: dict = {}
        try:
            from src.core.services.completude_cache import compute_completude_batch
            from pathlib import Path as _Path
            # Inferir obra_path a partir do projeto
            _obra_path = None
            try:
                projects = self.db.get_projects()
                proj = next((p for p in projects if str(p.get('id')) == str(self.current_project_id)), None)
                if proj:
                    _obra_root = _Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
                    _obra_path = str(_obra_root / proj.get('work_name', ''))
            except Exception:
                pass
            completude_scores = compute_completude_batch(
                items, obra_path=_obra_path, project_id=self.current_project_id
            )
        except Exception as _ce:
            print(f"[Phase3] ℹ️ Completude nao disponivel: {_ce}")

        # Ordenar
        def nat_key(x):
            name = str(x.get('name', x.get('nome', '')))
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]
        items.sort(key=nat_key)

        is_lv = "Lateral" in class_name or "LV" in class_name

        for i, item_data in enumerate(items):
            item_id = item_data.get('id_item', f"{i+1:02}")
            name = item_data.get('name', '?')
            validated = item_data.get('is_validated', False)
            status_label = "Validado" if validated else "Pendente"

            # CAD-15: badge de completude
            pct = completude_scores.get(item_id)
            if pct is not None:
                status_txt = f"[{pct:.0f}%] {status_label}"
            else:
                status_txt = status_label

            if is_lv:
                # LV com sub-abas: só mostra a classe Para ou Passa conforme pp_filter
                pp_classes = [pp_filter] if pp_filter in ("Para", "Passa") else ("Para", "Passa")
                parent_item = QTreeWidgetItem(tree_widget)
                parent_item.setText(0, f"{i+1:02}")
                parent_item.setText(1, f"LV-{name}")
                parent_item.setText(2, status_txt)
                parent_item.setExpanded(True)
                for pp in pp_classes:
                    pp_group = QTreeWidgetItem(parent_item)
                    pp_group.setText(0, "")
                    pp_group.setText(1, f"LV-{name} {pp}")
                    pp_group.setText(2, "")
                    pp_group.setExpanded(True)
                    for face in ("A", "B"):
                        leaf = QTreeWidgetItem(pp_group)
                        leaf.setText(0, "")
                        leaf.setText(1, f"LV-{name}.{face} {pp}")
                        leaf.setText(2, status_txt if face == "A" else "")
                        if validated:
                            leaf.setForeground(2, Qt.green)
                        elif pct is not None and pct >= 70:
                            leaf.setForeground(2, QColor("#80cbc4"))  # hardcoded-ok
                        else:
                            leaf.setForeground(2, QColor(Colors.ACCENT_INFO))
                        btn = QPushButton("Ver Detalhes")
                        btn.setCursor(Qt.PointingHandCursor)
                        btn.setStyleSheet(
                            f"background: {Colors.BG_CARD}; color: {Colors.TEXT_BRIGHT}; "
                            "border-radius: 4px; padding: 2px; font-size: 10px;")
                        btn.clicked.connect(lambda checked=False, d=item_data: self._open_detail_dialog(d))
                        tree_widget.setItemWidget(leaf, 3, btn)
                continue

            tree_item = QTreeWidgetItem(tree_widget)
            tree_item.setText(0, item_id)
            tree_item.setText(1, name)
            tree_item.setText(2, status_txt)

            if validated:
                tree_item.setForeground(2, Qt.green)
            elif pct is not None and pct >= 70:
                tree_item.setForeground(2, QColor("#80cbc4"))  # teal — boa completude  # hardcoded-ok
            else:
                tree_item.setForeground(2, QColor(Colors.ACCENT_INFO))

            # Botão Detalhes
            btn = QPushButton("Ver Detalhes")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"background: {Colors.BG_CARD}; color: {Colors.TEXT_BRIGHT}; border-radius: 4px; padding: 2px; font-size: 10px;")
            # Usar closure seguro
            btn.clicked.connect(lambda checked=False, d=item_data: self._open_detail_dialog(d))
            tree_widget.setItemWidget(tree_item, 3, btn)

    def _open_detail_dialog(self, item_data):
        from src.ui.dialogs.detail_dialog import DetailDialog
        # Se salvar, o objeto é atualizado na mem. Precisa salvar no DB?
        # O DetailDialog atual edita o dict.
        # Precisamos de um botão "Salvar" no dialog se aberto daqui.
        # Ou instruir o usuário que aqui é visualização.
        
        dlg = DetailDialog(item_data, parent=self)
        dlg.exec()
        
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
            elif "viga" in t or "fundo" in t: self.db.save_beam(item_data, self.current_project_id)
        
        try:
            self._refresh_all_phase3_lists()
        except Exception:
            pass

    def _refresh_all_phase3_lists(self):
        """Recarrega todas as listas da Fase 3 (após edição/save)."""
        phase_tab = self.phase_tab_widgets.get(3)
        if not phase_tab:
            return
        container = phase_tab.widget()
        if not container:
            return
        layout = container.layout()
        if not layout:
            return
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if not widget:
                continue
            class_name = widget.property("class_name")
            if not class_name:
                continue
            # LV usa duas sub-árvores separadas
            lv_tabs = widget.property("db_lv_tabs")
            if lv_tabs is not None:
                self._refresh_lv_active_tab(class_name, widget)
                continue
            tree = widget.property("db_tree")
            if tree:
                self._refresh_phase3_data(class_name, tree)

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

        is_lv_phase4 = "Lateral" in class_name or "LV" in class_name

        for i, item_data in enumerate(items):
            name = item_data.get('nome', item_data.get('name', f"Item {i+1}"))
            if is_lv_phase4:
                # Normaliza "LV V331.B Passa" → "LV-V331.B-Passa" (spaces → dashes)
                import re as _re
                name = _re.sub(
                    r'^LV\s+(V\d+[A-Z]?)\.([AB])\s+(Para|Passa)$',
                    r'LV-\1.\2-\3', str(name), flags=_re.IGNORECASE
                )
                name = _re.sub(
                    r'^LV\s+(V\d+[A-Z]?)\.([AB])$',
                    r'LV-\1.\2', str(name), flags=_re.IGNORECASE
                )
            is_valid = item_data.get('is_validado', item_data.get('is_validated', False))
            status_val = "OK" if is_valid else "Proc."

            tree_item = QTreeWidgetItem(tree_widget)
            tree_item.setText(0, f"{i+1:02}")
            tree_item.setText(1, name)
            tree_item.setText(2, status_val)
            
            if is_valid:
                tree_item.setForeground(2, Qt.green)
            else:
                tree_item.setForeground(2, QColor(Colors.ACCENT_PRIMARY))

            # Botão Detalhes com ficha específica do robô
            btn = QPushButton("Ver Ficha Robô")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"background: rgba(0, 77, 115, 1); color: {Colors.TEXT_BRIGHT}; border-radius: 4px; padding: 2px; font-size: 10px;")
            btn.clicked.connect(lambda checked=False, d=item_data: self._open_robot_ficha(d))
            tree_widget.setItemWidget(tree_item, 3, btn)

    def _open_robot_ficha(self, item_data):
        """Abre a ficha técnica específica do robô (Fase 4)."""
        from src.ui.dialogs.robot_ficha_dialog import RobotFichaDialog
        dlg = RobotFichaDialog(item_data, parent=self)
        dlg.exec()

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



    def _load_phase3_initial(self):
        """Carrega os dados iniciais da fase 3 após selecionar um projeto."""
        self._refresh_phase_tabs()

    def _on_project_card_clicked(self, p_id, p_name, dxf_path):
        """Ao entrar num projeto específico (chamado internamente)"""
        p_data = self.db.get_project_by_id(p_id)
        if p_data:
            self.on_project_card_clicked(p_data)

    # ─────────────────────────────────────────────────────────────────
    # PM-006: Fase 2 — Grid Eng. Reversa
    # ─────────────────────────────────────────────────────────────────

    _ER_TIPOS = ["—", "PIL", "VIG", "LAJ", "FV"]

    def _build_eng_reversa_grid(self, parent_layout):
        """Constrói grid de cards DXF de Eng. Reversa para a obra/pav selecionados."""
        work_name = self.current_work_name
        if not work_name:
            item = self.list_works.currentItem()
            if item:
                work_name = item.data(Qt.UserRole)
        if not work_name:
            parent_layout.addWidget(QLabel("Selecione uma obra para ver os DXFs de Eng. Reversa."))
            return

        dados_root = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
        folder = dados_root / work_name / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"

        if not folder.exists():
            lbl = QLabel(f"Pasta não encontrada:\n{folder}")
            lbl.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 11px;")
            parent_layout.addWidget(lbl)
            return

        dxfs = sorted(folder.glob("*.dxf")) + sorted(folder.glob("*.dwg"))
        if not dxfs:
            lbl = QLabel("Nenhum DXF/DWG encontrado nesta pasta.")
            lbl.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 11px;")
            parent_layout.addWidget(lbl)
            return

        # Ler classificações salvas (simple JSON sidecar)
        sidecar = folder / "_eng_reversa_classif.json"
        try:
            saved = json.loads(sidecar.read_text(encoding='utf-8')) if sidecar.exists() else {}
        except Exception:
            saved = {}

        grid = QWidget()
        grid_lay = QVBoxLayout(grid)
        grid_lay.setContentsMargins(0, 4, 0, 4)
        grid_lay.setSpacing(4)

        for f in dxfs:
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background: {Colors.BG_DEEP}; border: 1px solid {Colors.BORDER_SUBTLE};
                    border-radius: 4px; padding: 2px;
                }}
            """)
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(8, 4, 8, 4)
            row_lay.setSpacing(8)

            ext_badge = QLabel(f.suffix.upper())
            ext_badge.setFixedWidth(36)
            ext_badge.setAlignment(Qt.AlignCenter)
            color = Colors.ACCENT_BLUE if f.suffix.lower() == '.dxf' else Colors.ACCENT_WARNING
            ext_badge.setStyleSheet(
                f"background: {color}; color: {Colors.TEXT_BRIGHT}; font-size: 9px;"
                f" font-weight: bold; border-radius: 3px; padding: 1px 3px;"
            )
            row_lay.addWidget(ext_badge)

            lbl_name = QLabel(f.stem[:50] + ("…" if len(f.stem) > 50 else ""))
            lbl_name.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 11px;")
            lbl_name.setToolTip(str(f))
            row_lay.addWidget(lbl_name, 1)

            cmb_tipo = QComboBox()
            cmb_tipo.setFixedWidth(72)
            cmb_tipo.addItems(self._ER_TIPOS)
            saved_tipo = saved.get(f.name, "—")
            if saved_tipo in self._ER_TIPOS:
                cmb_tipo.setCurrentText(saved_tipo)
            cmb_tipo.setStyleSheet(f"""
                QComboBox {{
                    background: {Colors.BG_CARD}; color: {Colors.TEXT_PRIMARY};
                    border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 3px;
                    padding: 2px 4px; font-size: 11px;
                }}
            """)
            # Salvar ao mudar
            fname_cap = f.name  # captura para lambda
            sidecar_cap = sidecar
            saved_ref = saved

            def _save_tipo(text, _fname=fname_cap, _sc=sidecar_cap, _sv=saved_ref):
                _sv[_fname] = text
                try:
                    _sc.write_text(json.dumps(_sv, ensure_ascii=False, indent=2), encoding='utf-8')
                except Exception:
                    pass

            cmb_tipo.currentTextChanged.connect(_save_tipo)
            row_lay.addWidget(QLabel("Tipo:"))
            row_lay.addWidget(cmb_tipo)

            # Status visual
            status = "✅" if saved.get(f.name, "—") != "—" else "⚠"
            lbl_status = QLabel(status)
            lbl_status.setStyleSheet(f"font-size: 13px;")
            row_lay.addWidget(lbl_status)

            grid_lay.addWidget(row)

        parent_layout.addWidget(grid)

    # ─────────────────────────────────────────────────────────────────
    # PM-004: Fase 6 — DXF granular por classe
    # ─────────────────────────────────────────────────────────────────

    _FASE6_CLASS_MAP = {
        "DXF Pilares":         ("DXF_Pilares",        "gerar_pl_dxf_stog.py"),
        "DXF Vigas Laterais":  ("DXF_Vigas_Laterais", "gerar_lv_dxf_stog.py"),
        "DXF Vigas Fundo":     ("DXF_Vigas_Fundo",    "gerar_fv_dxf_stog.py"),
        "DXF Lajes":           ("DXF_Lajes",          "gerar_lj_dxf_stog.py"),
    }

    def _build_fase6_class_grid(self, parent_layout, class_name: str):
        """Grid de DXFs gerados para a classe na Fase 6, com botões Gerar/Abrir."""
        work_name = self.current_work_name or (
            self.list_works.currentItem().data(Qt.UserRole)
            if self.list_works.currentItem() else None
        )
        if not work_name:
            return

        folder_name, script_name = self._FASE6_CLASS_MAP.get(class_name, (None, None))
        if not folder_name:
            return

        dados_root  = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
        scripts_dir = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts")
        class_folder = dados_root / work_name / "Fase-6_Execucao_CAD" / folder_name

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(4)

        # Linha de cabeçalho: botão "Gerar Todos"
        hdr = QHBoxLayout()
        lbl_path = QLabel(str(class_folder) if class_folder.exists() else "⚠ pasta não encontrada")
        lbl_path.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 10px;")
        hdr.addWidget(lbl_path, 1)

        btn_gerar_todos = QPushButton("⚡ Gerar Todos")
        btn_gerar_todos.setFixedHeight(24)
        btn_gerar_todos.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT};
                border-radius: 3px; padding: 2px 8px; font-size: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {Colors.ACCENT_BLUE_HOVER}; }}
        """)
        script_path = scripts_dir / script_name
        btn_gerar_todos.clicked.connect(
            lambda _, sp=script_path, wn=work_name: self._run_generator_script(sp, wn)
        )
        hdr.addWidget(btn_gerar_todos)
        lay.addLayout(hdr)

        # Lista de DXFs existentes
        if class_folder.exists():
            dxfs = sorted(class_folder.glob("*.dxf"))
            if dxfs:
                for dxf in dxfs[:30]:  # limitar a 30 para não sobrecarregar
                    row = self._make_dxf_row(dxf, scripts_dir / script_name, work_name)
                    lay.addWidget(row)
            else:
                lay.addWidget(self._dim_label("Nenhum DXF gerado ainda. Clique em 'Gerar Todos'."))
        else:
            lay.addWidget(self._dim_label(f"Pasta não encontrada: {class_folder.name}"))

        parent_layout.addWidget(container)

    def _make_dxf_row(self, dxf: Path, script: Path, work_name: str) -> QFrame:
        row = QFrame()
        row.setStyleSheet(f"background: {Colors.BG_DEEP}; border-radius: 3px;")
        r = QHBoxLayout(row)
        r.setContentsMargins(6, 3, 6, 3)
        r.setSpacing(6)

        lbl = QLabel(dxf.name[:60])
        lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 11px;")
        lbl.setToolTip(str(dxf))
        r.addWidget(lbl, 1)

        size_kb = dxf.stat().st_size // 1024
        r.addWidget(self._dim_label(f"{size_kb} KB"))

        btn_open = QPushButton("📂 Abrir")
        btn_open.setFixedHeight(22)
        btn_open.setStyleSheet(f"font-size: 10px; padding: 1px 6px; background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY}; border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 3px;")
        btn_open.clicked.connect(lambda _, p=dxf: os.startfile(str(p)) if os.name == 'nt' else None)
        r.addWidget(btn_open)

        return row

    def _run_generator_script(self, script: Path, work_name: str):
        """Lança script gerador via subprocess."""
        if not script.exists():
            QMessageBox.warning(self, "Script", f"Script não encontrado:\n{script.name}")
            return
        import subprocess, sys as _sys, time as _time
        _t0 = _time.monotonic()
        # S5 — log estruturado de início de geração
        print(f"[ROBO_{script.stem.upper()}] iniciando para {work_name}", flush=True)
        proc = subprocess.Popen([_sys.executable, str(script), "--obra", work_name])
        QMessageBox.information(self, "Geração", f"Gerando DXFs para '{work_name}'...\nAguarde e recarregue a fase.")
        # Tenta logar duração se processo já terminou ao fechar o dialog
        if proc.poll() is not None:
            _dur = _time.monotonic() - _t0
            print(f"[ROBO_{script.stem.upper()}] concluído em {_dur:.1f}s", flush=True)

    def _dim_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 10px;")
        return lbl

    # ─────────────────────────────────────────────────────────────────
    # PM-005: Fase 7 — Consolidação DXF por pavimento
    # ─────────────────────────────────────────────────────────────────

    _FASE7_CLASS_MAP = {
        "DXF Consolidado por Pavimento": ("consolidado_pavimento", "consolidar_dxf_pav.py"),
        "DXF Consolidado por Tipo":      ("consolidado_tipo",      "consolidar_dxf_tipo.py"),
    }

    def _build_fase7_class_grid(self, parent_layout, class_name: str):
        """Grid de DXFs consolidados para Fase 7."""
        work_name = self.current_work_name or (
            self.list_works.currentItem().data(Qt.UserRole)
            if self.list_works.currentItem() else None
        )
        if not work_name:
            return

        folder_name, script_name = self._FASE7_CLASS_MAP.get(class_name, (None, None))
        if not folder_name:
            return

        dados_root  = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
        scripts_dir = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts")
        class_folder = dados_root / work_name / "Fase-7_Consolidacao" / folder_name

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        hdr.addWidget(self._dim_label(str(class_folder)), 1)

        script_path = scripts_dir / script_name
        btn_consolidar = QPushButton("🔗 Gerar Consolidado")
        btn_consolidar.setFixedHeight(24)
        btn_consolidar.setStyleSheet(f"""
            QPushButton {{
                background: rgba(160, 112, 255, 46); color: {Contextual.PURPLE};
                border: 1px solid {Contextual.PURPLE}; border-radius: 3px; padding: 2px 8px; font-size: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(160, 112, 255, 66); }}
        """)
        btn_consolidar.clicked.connect(
            lambda _, sp=script_path, wn=work_name: self._run_generator_script(sp, wn)
        )
        hdr.addWidget(btn_consolidar)
        lay.addLayout(hdr)

        if class_folder.exists():
            dxfs = sorted(class_folder.glob("*.dxf"))
            if dxfs:
                for dxf in dxfs[:20]:
                    row = self._make_dxf_row(dxf, script_path, work_name)
                    lay.addWidget(row)
            else:
                lay.addWidget(self._dim_label("Nenhum DXF consolidado. Clique em 'Gerar Consolidado'."))
        else:
            lay.addWidget(self._dim_label(f"Pasta '{folder_name}' ainda não criada."))

        parent_layout.addWidget(container)

    # ─────────────────────────────────────────────────────────────────
    # PM-007: Fase 8 — Dashboard de Revisão e Entrega
    # ─────────────────────────────────────────────────────────────────

    def _build_fase8_dashboard(self, parent_layout):
        """Dashboard por pavimento: score de completude, status DXF final, exportar."""
        work_name = self.current_work_name or (
            self.list_works.currentItem().data(Qt.UserRole)
            if self.list_works.currentItem() else None
        )
        if not work_name:
            parent_layout.addWidget(self._dim_label("Selecione uma obra."))
            return

        dados_root   = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
        val_dir      = Path("D:/Agente-cad-PYSIDE/validacao_visual")
        fase8_dir    = dados_root / work_name / "Fase-8_Revisao_Entrega"
        cert_json    = val_dir / f"consolidado_{work_name}.json"

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(6)

        # ── Scores de validação ────────────────────────────────────
        scores_row = QHBoxLayout()
        if cert_json.exists():
            try:
                cert_data = json.loads(cert_json.read_text(encoding='utf-8'))
                for pav_key, pav_data in cert_data.items():
                    resultados = pav_data.get("resultados", {})
                    pav_widget = QFrame()
                    pav_widget.setStyleSheet(
                        f"background: {Colors.BG_DEEP}; border: 1px solid {Colors.BORDER_DEFAULT};"
                        f" border-radius: 4px; padding: 4px;"
                    )
                    pv = QVBoxLayout(pav_widget)
                    pv.setSpacing(2)
                    pv.addWidget(QLabel(f"<b>{pav_key}</b>"))
                    for tipo in ["PL", "LV", "FV", "LJ"]:
                        sc = resultados.get(tipo, {}).get("score_final")
                        color = Colors.ACCENT_SUCCESS if sc and sc >= 75 else Colors.ACCENT_WARNING if sc else Colors.TEXT_DIM
                        txt = f"{sc:.1f}%" if sc else "—"
                        lbl = QLabel(f"{tipo}: {txt}")
                        lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
                        pv.addWidget(lbl)
                    scores_row.addWidget(pav_widget)
            except Exception as e:
                scores_row.addWidget(self._dim_label(f"Erro ao ler scores: {e}"))
        else:
            scores_row.addWidget(self._dim_label("Nenhuma validação encontrada. Execute a Fase-8 primeiro."))
        scores_row.addStretch()
        lay.addLayout(scores_row)

        # ── DXF Final Validado ─────────────────────────────────────
        if fase8_dir.exists():
            dxf_final_dir = fase8_dir / "DXF_Final_Validado"
            dxfs_finais = list(dxf_final_dir.glob("*.dxf")) if dxf_final_dir.exists() else []
            if dxfs_finais:
                lay.addWidget(QLabel(f"✅ DXFs Finais ({len(dxfs_finais)}):"))
                for dxf in dxfs_finais[:10]:
                    row = self._make_dxf_row(dxf, Path(), work_name)
                    lay.addWidget(row)
            else:
                lay.addWidget(self._dim_label("Pasta DXF_Final_Validado vazia."))

            # CERTIFICAÇÃO
            cert_final = fase8_dir / "CERTIFICACAO_FINAL.md"
            if cert_final.exists():
                cert_ok = QLabel("🏆 CERTIFICAÇÃO FINAL — arquivo presente")
                cert_ok.setStyleSheet(f"color: {Colors.ACCENT_SUCCESS}; font-weight: bold; font-size: 12px;")
                lay.addWidget(cert_ok)
        else:
            lay.addWidget(self._dim_label(f"Fase-8 não inicializada para {work_name}."))

        # ── Botão Exportar Pacote ──────────────────────────────────
        btn_export = QPushButton("📦 Exportar Pacote de Entrega")
        btn_export.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.ACCENT_SUCCESS}; color: {Colors.TEXT_BRIGHT};
                border-radius: 4px; padding: 6px 14px; font-weight: bold; font-size: 12px;
            }}
            QPushButton:hover {{ background: rgba(67, 160, 71, 1); }}
        """)
        btn_export.clicked.connect(lambda: QMessageBox.information(
            self, "Exportar", f"Pacote de entrega para '{work_name}':\n{fase8_dir}\n\n(pipeline de exportação a implementar)"
        ))
        lay.addWidget(btn_export)

        parent_layout.addWidget(container)

    # ─────────────────────────────────────────────────────────────────
    # PM-002: Auto-indexação Fase 1 (filesystem scan)
    # ─────────────────────────────────────────────────────────────────

    _FASE1_FOLDER_MAP = {
        "Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF":
            "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)",
        "Documentos_e_Atas_de_Reunioes_PDF_MD":
            "Documentos e Atas de Reunioes(.PDF/.MD)",
        "Detalhes_Estruturais_DWG_PDF_DXF_MD":
            "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)",
        # canonical name — must match PHASE_CLASSES[1] exactly
        "Projetos_Finalizados_para_Engenharia_Reversa":
            "Projetos Finalizados para Engenharia Reversa",
    }

    # Normalizes legacy/variant category strings → canonical PHASE_CLASSES names
    _CATEGORY_ALIASES = {
        "projetos finalizados para engenharia reversa (suporte a dwg e dxf)":
            "Projetos Finalizados para Engenharia Reversa",
        "projetos finais para engenharia reversa (suporte a dwg e dxf)":
            "Projetos Finalizados para Engenharia Reversa",
        "estruturais dos pavimentos, estado bruto (.dxf)":
            "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)",
    }
    _FASE1_EXTS = {'.dwg', '.dxf', '.pdf', '.md'}

    def _scan_phase1_filesystem(self, work_name: str, existing_paths: set) -> list:
        """Varre Fase-1_Ingestao e retorna arquivos não indexados como dicts."""
        dados_root = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
        fase1_dir  = dados_root / work_name / "Fase-1_Ingestao"
        if not fase1_dir.exists():
            return []
        found = []
        for folder_name, class_name in self._FASE1_FOLDER_MAP.items():
            folder = fase1_dir / folder_name
            if not folder.exists():
                continue
            for f in folder.iterdir():
                if f.suffix.lower() not in self._FASE1_EXTS:
                    continue
                fpath = str(f.resolve())
                if fpath in existing_paths:
                    continue
                found.append({
                    'id':          None,
                    'name':        f.name + '  ⚠ não indexado',
                    'file_path':   fpath,
                    'extension':   f.suffix.lower(),
                    'phase':       1,
                    'category':    class_name,
                    '_not_indexed': True,
                })
        return found

    # ── Index badge helpers ────────────────────────────────────────────────

    # ── RAG Pipeline ──────────────────────────────────────────────────────────

    def _ensure_local_rag_snapshot(self, work_name: str | None):
        """Atualiza silenciosamente o snapshot local ao selecionar uma obra."""
        work_name = str(work_name or "").strip()
        if not work_name or work_name == "__NO_WORK__":
            return

        if (
            self._auto_rag_process is not None
            and self._auto_rag_process.state() != QProcess.ProcessState.NotRunning
        ):
            if work_name != self._auto_rag_active_work:
                self._auto_rag_pending_work = work_name
            return

        import sys

        script = Path("D:/Agente-cad-PYSIDE/scripts/obra_rag_pipeline.py")
        if not script.exists():
            logging.warning("[RAG-LOCAL] pipeline ausente: %s", script)
            return

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(
            lambda p=process: logging.info(
                "[RAG-LOCAL] %s",
                bytes(p.readAllStandardOutput()).decode("utf-8", errors="replace").strip(),
            )
        )
        process.finished.connect(self._on_auto_rag_snapshot_finished)
        self._auto_rag_process = process
        self._auto_rag_active_work = work_name
        process.start(
            sys.executable,
            [str(script), "--obra", work_name, "--apply"],
        )

    def _on_auto_rag_snapshot_finished(self, exit_code: int, _exit_status):
        work_name = self._auto_rag_active_work
        if exit_code:
            logging.warning(
                "[RAG-LOCAL] snapshot automatico falhou para %s (exit=%s)",
                work_name,
                exit_code,
            )
        elif work_name == self.current_work_name:
            QTimer.singleShot(0, self._refresh_rag_badge)

        self._auto_rag_process = None
        self._auto_rag_active_work = None
        pending = self._auto_rag_pending_work
        self._auto_rag_pending_work = None
        if pending and pending != work_name:
            QTimer.singleShot(0, lambda obra=pending: self._ensure_local_rag_snapshot(obra))

    def _on_rag_pipeline_clicked(self):
        """Dispara o pipeline RAG semântico em QThread."""
        work_name = self.current_work_name or (
            self.list_works.currentItem().data(Qt.UserRole)
            if self.list_works.currentItem() else ""
        )
        if not work_name:
            QMessageBox.warning(self, "RAG", "Selecione uma obra antes de processar.")
            return

        from PySide6.QtCore import QThread, Signal as QSignal, QObject
        import sys

        class _Worker(QObject):
            progress = QSignal(int, str)
            finished = QSignal(dict)

            def __init__(self, obra: str):
                super().__init__()
                self._obra = obra

            def run(self):
                try:
                    _root = Path("D:/Agente-cad-PYSIDE")
                    if str(_root) not in sys.path:
                        sys.path.insert(0, str(_root))
                    from scripts.obra_rag_pipeline import run_pipeline
                    result = run_pipeline(
                        self._obra,
                        force=False,
                        progress_cb=lambda pct, msg: self.progress.emit(pct, msg),
                    )
                    self.finished.emit(result)
                except Exception as e:
                    self.finished.emit({"status": "error", "errors": [str(e)],
                                        "doc_chunks": 0, "dxf_indexed": 0,
                                        "triagem_rows": 0, "duration_s": 0})

        # Desabilitar botão durante execução
        sender_btn = self.sender()
        if sender_btn:
            sender_btn.setEnabled(False)

        if hasattr(self, '_lbl_rag_status'):
            self._lbl_rag_status.setText("🔄 Processando...")
            self._lbl_rag_status.setStyleSheet(
                f"color: {Colors.ACCENT_WARNING}; font-size: 11px;"
                " background: transparent; border: none; padding: 0 4px;"
            )

        self._rag_thread = QThread()
        self._rag_worker = _Worker(work_name)
        self._rag_worker.moveToThread(self._rag_thread)
        self._rag_thread.started.connect(self._rag_worker.run)

        def _on_progress(pct, msg):
            if hasattr(self, '_lbl_rag_status'):
                self._lbl_rag_status.setText(f"[{pct}%] {msg}")

        def _on_finished(result):
            self._rag_thread.quit()
            if sender_btn:
                sender_btn.setEnabled(True)
            # Atualiza badge com estado real do DB (substitui o spinner de progresso)
            QTimer.singleShot(100, self._refresh_rag_badge)
            # Restaurar botão unificado se existir
            if hasattr(self, '_btn_ingest_all'):
                self._btn_ingest_all.setEnabled(True)
                self._btn_ingest_all.setText("⚡ Atualizar Obra (DB + RAG Local)")
            if result.get("errors"):
                errs = "\n".join(result["errors"][:5])
                QMessageBox.warning(self, "RAG — Avisos", f"Pipeline concluído com avisos:\n\n{errs}")
            # Recarregar painel de triagem e navegar para Fase 2
            def _show_triagem_results():
                # Garantir aba externa "MEUS PROJETOS" (índice 0) está visível
                if hasattr(self, 'tabs'):
                    self.tabs.setCurrentIndex(0)
                # Garantir que o painel está expandido
                if hasattr(self, '_triagem_content_widget'):
                    self._triagem_content_widget.setVisible(True)
                if hasattr(self, '_btn_triagem_toggle'):
                    self._btn_triagem_toggle.setText("▲")
                # Navegar para a aba Fase 2 (índice 1) — dispara _on_phase_tab_switched
                if hasattr(self, 'phase_tabs'):
                    self.phase_tabs.setCurrentIndex(1)
                # Forçar refresh do painel (garante render mesmo se tab já estava em idx 1)
                if hasattr(self, '_triagem_list_layout'):
                    self._refresh_triagem_panel()

            QTimer.singleShot(200, _show_triagem_results)

        self._rag_worker.progress.connect(_on_progress)
        self._rag_worker.finished.connect(_on_finished)
        self._rag_thread.start()

    # Cache: {work_name: (timestamp, disco_count)}
    _fs_count_cache: dict = {}
    _FS_CACHE_TTL = 30  # segundos

    def _get_index_counts(self, work_name: str) -> tuple[int, int]:
        """Retorna (total_disco_fase1, total_db_fase1) para a obra atual.
        Conta apenas arquivos da Fase-1_Ingestao no disco e phase=1 no DB.
        Usa cache de 30s para o scan de disco (operação lenta).
        """
        import sqlite3 as _sq3
        import time as _time
        from pathlib import Path as _P
        EXTS = {'.dwg', '.dxf', '.pdf', '.md'}
        DADOS = _P("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
        DB    = _P("D:/Agente-cad-PYSIDE/project_data.vision")
        if not work_name:
            return 0, 0

        # Cache do scan de disco (evita rglob a cada troca de obra)
        now = _time.time()
        cached = self._fs_count_cache.get(work_name)
        if cached and (now - cached[0]) < self._FS_CACHE_TTL:
            disco = cached[1]
        else:
            fase1_path = DADOS / work_name / "Fase-1_Ingestao"
            if fase1_path.is_dir():
                # Contar apenas as 4 pastas canônicas (idêntico ao _scan_phase1_filesystem)
                import os as _os
                disco = 0
                for folder_name in self._FASE1_FOLDER_MAP:
                    folder = fase1_path / folder_name
                    if folder.is_dir():
                        for fn in _os.listdir(str(folder)):
                            if _os.path.splitext(fn)[1].lower() in EXTS:
                                disco += 1
            else:
                disco = 0
            self._fs_count_cache[work_name] = (now, disco)

        try:
            conn = _sq3.connect(str(DB))
            cur  = conn.cursor()
            # Filtra pelas mesmas extensões do scan de disco (bug: antes contava jpg/png)
            cur.execute(
                "SELECT COUNT(*) FROM project_documents"
                " WHERE work_name=? AND phase=1"
                " AND lower(extension) IN ('.dwg','.dxf','.pdf','.md')",
                (work_name,)
            )
            db_n = cur.fetchone()[0]
            conn.close()
        except Exception:
            db_n = 0
        return disco, db_n

    def _refresh_index_badge(self):
        """Atualiza o badge de contagem disco/DB ao lado do botão Indexar."""
        if not hasattr(self, '_lbl_index_badge'):
            return
        work_name = self.current_work_name or ""
        disco, db_n = self._get_index_counts(work_name)
        falta = disco - db_n
        if disco == 0:
            text  = "sem obra"
            color = Colors.TEXT_DIM
        elif db_n == disco:
            text  = f"✅ {db_n}/{disco} indexados"
            color = Colors.ACCENT_SUCCESS_ALT
        elif db_n > disco:
            # Mais entradas no DB do que arquivos no disco (indexações anteriores / multi-versão)
            text  = f"📦 {db_n} DB / {disco} disco"
            color = Colors.TEXT_SECONDARY
        elif db_n == 0:
            text  = f"❌ 0/{disco} indexados"
            color = Colors.ACCENT_DANGER
        else:
            text  = f"⚠ {db_n}/{disco}  (+{falta} faltando)"
            color = Colors.ACCENT_WARNING
        self._lbl_index_badge.setText(text)
        self._lbl_index_badge.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold;"
            " background: transparent; border: none; padding: 0 4px;"
        )

    def _get_rag_counts(self, work_name: str) -> tuple[int, int, int]:
        """Retorna triagem legada e itens presentes no snapshot RAG local."""
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        triagem_total   = 0
        triagem_pending = 0
        local_items     = 0
        if not work_name:
            return 0, 0, 0
        try:
            conn = _sq3.connect(str(DB))
            cur = conn.execute(
                "SELECT COUNT(*) FROM obra_triagem WHERE obra_name=?", (work_name,)
            )
            triagem_total = cur.fetchone()[0]
            cur = conn.execute(
                "SELECT COUNT(*) FROM obra_triagem WHERE obra_name=? AND status IN ('pending','review_required')",
                (work_name,)
            )
            triagem_pending = cur.fetchone()[0]
            conn.close()
        except Exception:
            pass
        # Snapshot local por obra. T0 pode aparecer aqui como contexto de trabalho,
        # mas nunca é promovido automaticamente ao RAG global.
        try:
            manifest_path = (
                Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
                / work_name
                / "obra_rag"
                / "manifest.json"
            )
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                local_items = int(manifest.get("counts", {}).get("reverse_fichas", 0))
        except Exception:
            pass
        return triagem_total, triagem_pending, local_items

    def _refresh_rag_badge(self):
        """Atualiza o badge do RAG local e da triagem legada."""
        if not hasattr(self, '_lbl_rag_status'):
            return
        work_name = self.current_work_name or ""
        triagem_total, triagem_pending, local_items = self._get_rag_counts(work_name)

        if triagem_total == 0 and local_items == 0:
            text  = "—"
            color = Colors.TEXT_DIM
        elif triagem_pending > 0:
            text  = f"⏳ {triagem_pending} pendentes / {triagem_total} triagem"
            if local_items:
                text += f" / {local_items} itens locais"
            color = Colors.ACCENT_WARNING
        else:
            # Tudo classificado
            text  = f"✅ {triagem_total} triagem"
            if local_items:
                text += f" / {local_items} itens locais"
            color = Colors.ACCENT_SUCCESS_ALT

        self._lbl_rag_status.setText(text)
        self._lbl_rag_status.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold;"
            " background: transparent; border: none; padding: 0 4px;"
        )

    # ── EPIC 2: Triagem IA ──────────────────────────────────────────────────

    _TRIAGEM_TO_FASE2 = {
        "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)": "Estruturais Pavimentos Limpos",
        "Projetos Finais Para Engenharia Reversa (suporte a dwg e dxf)": "Projetos Finalizados para Engenharia Reversa",
        "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)": "Detalhamentos Específicos",
        "Estruturais Pavimentos Limpos": "Estruturais Pavimentos Limpos",
        "Detalhamentos Específicos": "Detalhamentos Específicos",
        "Projetos Finalizados para Engenharia Reversa": "Projetos Finalizados para Engenharia Reversa",
    }

    def _build_triagem_panel(self, layout):
        """Painel colapsável de sugestões IA — injetado no topo da Fase 2."""
        outer = QFrame()
        outer.setObjectName("TriagemPanel")
        outer.setStyleSheet(_resolve_css("""
            QFrame#TriagemPanel {
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 8px;
            }
        """))
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(12, 10, 12, 10)
        outer_layout.setSpacing(8)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(8)

        self._lbl_triagem_summary = QLabel("🧠 Sugestões IA")
        self._lbl_triagem_summary.setStyleSheet(_resolve_css(
            "color: {Colors.ACCENT_PRIMARY}; font-size: 12px; font-weight: bold;"
            " background: transparent; border: none;"
        ))

        btn_approve_all = QPushButton("✓ Aprovar ≥ 80%")
        btn_approve_all.setToolTip("Aprova automaticamente todas as sugestões com confiança ≥ 80%")
        btn_approve_all.setStyleSheet(_resolve_css("""
            QPushButton {
                background: rgba(0, 200, 120, 38); color: {Colors.ACCENT_SUCCESS_ALT};
                border: 1px solid {Colors.ACCENT_SUCCESS_ALT}; border-radius: 4px;
                padding: 3px 10px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(0, 200, 120, 71); }
        """))

        btn_reload = QPushButton("↻")
        btn_reload.setToolTip("Recarregar sugestões da obra atual")
        btn_reload.setFixedWidth(28)
        btn_reload.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                padding: 3px; font-size: 13px;
            }
            QPushButton:hover { color: {Colors.TEXT_PRIMARY}; }
        """))

        self._btn_triagem_toggle = QPushButton("▲")
        self._btn_triagem_toggle.setFixedWidth(28)
        self._btn_triagem_toggle.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {Text.SECONDARY}; border: none; font-size: 11px; }}"
        )

        header.addWidget(self._lbl_triagem_summary)
        header.addStretch()
        header.addWidget(btn_approve_all)
        header.addWidget(btn_reload)
        header.addWidget(self._btn_triagem_toggle)
        outer_layout.addLayout(header)

        # Content (colapsável)
        self._triagem_content_widget = QWidget()
        content_layout = QVBoxLayout(self._triagem_content_widget)
        content_layout.setContentsMargins(0, 4, 0, 0)
        content_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setMaximumHeight(1040)
        scroll.setMinimumHeight(280)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(_resolve_css("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { border: none; background: {Colors.BG_DEEP}; width: 6px; margin: 0; }
            QScrollBar::handle:vertical { background: {Colors.BG_CARD}; min-height: 16px; border-radius: 3px; }
        """))

        self._triagem_list_container = QWidget()
        self._triagem_list_container.setStyleSheet("background: transparent;")
        self._triagem_list_layout = QVBoxLayout(self._triagem_list_container)
        self._triagem_list_layout.setSpacing(1)
        self._triagem_list_layout.setContentsMargins(0, 0, 0, 0)

        scroll.setWidget(self._triagem_list_container)
        content_layout.addWidget(scroll)
        outer_layout.addWidget(self._triagem_content_widget)

        layout.addWidget(outer)

        def _toggle():
            vis = not self._triagem_content_widget.isVisible()
            self._triagem_content_widget.setVisible(vis)
            self._btn_triagem_toggle.setText("▲" if vis else "▼")

        self._btn_triagem_toggle.clicked.connect(_toggle)
        btn_reload.clicked.connect(self._refresh_triagem_panel)
        btn_approve_all.clicked.connect(self._approve_all_high_confidence_triagem)

        self._refresh_triagem_panel()

    def _load_triagem_rows(self) -> list:
        """Carrega TODAS as sugestões de obra_triagem para a obra atual (todos os status)."""
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        work_name = self.current_work_name or ""
        if not work_name:
            return []
        try:
            conn = _sq3.connect(str(DB))
            conn.row_factory = _sq3.Row
            cur = conn.execute(
                "SELECT * FROM obra_triagem WHERE obra_name=?"
                " ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'review_required' THEN 1"
                " WHEN 'approved' THEN 2 ELSE 3 END,"
                " confidence DESC, suggested_order ASC",
                (work_name,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception:
            return []

    def _count_triagem_total(self) -> int:
        """Conta total de linhas em obra_triagem para a obra atual (qualquer status)."""
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        work_name = self.current_work_name or ""
        if not work_name:
            return 0
        try:
            conn = _sq3.connect(str(DB))
            cur = conn.execute(
                "SELECT COUNT(*) FROM obra_triagem WHERE obra_name=?", (work_name,)
            )
            total = cur.fetchone()[0]
            conn.close()
            return total
        except Exception:
            return 0

    def _refresh_triagem_panel(self):
        """Reconstrói a lista de cards de triagem."""
        if not hasattr(self, '_triagem_list_layout'):
            return
        while self._triagem_list_layout.count():
            item = self._triagem_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = self._load_triagem_rows()

        if not rows:
            work = self.current_work_name or "..."
            msg = (
                f"Nenhuma sugestão para {work}.\n"
                "A atualização do RAG local não gera triagem automaticamente."
            )
            summary_txt = "🧠 Sugestões IA — nenhuma pendente"
            lbl = QLabel(msg)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(_resolve_css(
                "color: {Colors.TEXT_DIM}; font-size: 11px; padding: 10px;"
                " background: transparent; border: none;"
            ))
            self._triagem_list_layout.addWidget(lbl)
            if hasattr(self, '_lbl_triagem_summary'):
                self._lbl_triagem_summary.setText(summary_txt)
        else:
            # Summary diferenciado por status
            n_pending  = sum(1 for r in rows if r['status'] in ('pending', 'review_required'))
            n_approved = sum(1 for r in rows if r['status'] == 'approved')
            n_rejected = sum(1 for r in rows if r['status'] == 'rejected')
            parts = []
            if n_pending:  parts.append(f"{n_pending} pendentes")
            if n_approved: parts.append(f"✅ {n_approved} aprovados")
            if n_rejected: parts.append(f"❌ {n_rejected} rejeitados")
            summary = "🧠 Sugestões IA — " + ("  |  ".join(parts) if parts else "nenhuma pendente")
            if hasattr(self, '_lbl_triagem_summary'):
                self._lbl_triagem_summary.setText(summary)
            # Agrupar por pavimento e ordenar canonicamente
            groups: dict = {}
            for row in rows:
                pav = self._get_row_pav(row)
                groups.setdefault(pav, []).append(row)
            sorted_groups = sorted(groups.items(), key=lambda kv: self._pav_sort_key(kv[0]))
            multi = len(sorted_groups) > 1
            for pav_name, pav_rows in sorted_groups:
                if multi:
                    hdr = self._make_pavimento_section_header(pav_name)
                    self._triagem_list_layout.addWidget(hdr)
                for row in pav_rows:
                    card = self._make_triagem_card(row)
                    self._triagem_list_layout.addWidget(card)

        self._triagem_list_layout.addStretch()

    # ── Constantes de opções para chips combo ───────────────────────────────

    _TRIAGEM_CAT_OPTIONS: list[tuple[str, str]] = [
        ("Bruto",       "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)"),
        ("Eng.Reversa", "Projetos Finalizados para Engenharia Reversa"),
        ("Detalhe",     "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)"),
        ("Limpas",      "Estruturais Pavimentos Limpos"),
    ]
    _PAV_OPTIONS: list[str] = [
        "FUNDAÇÃO", "1º SUBSOLO", "2º SUBSOLO", "SUBSOLO",
        "TÉRREO", "TIPO", "1º PAVIMENTO", "2º PAVIMENTO", "3º PAVIMENTO",
        "4º PAVIMENTO", "5º PAVIMENTO", "ÁTICO", "COBERTURA",
        "DECK", "BARRILETE", "CAIXA D'ÁGUA", "OUTROS",
    ]
    _ER_CLASS_OPTIONS: list[str] = ["Pilares", "Lateral de Viga", "Fundos de Viga", "Lajes", "GF", "Outros"]

    # Mapeamento short-code → label completo (compatibilidade com valores salvos)
    _ER_SHORT_TO_FULL: dict = {
        "PIL":    "Pilares",
        "LV":     "Lateral de Viga",
        "FV":     "Fundos de Viga",
        "LAJ":    "Lajes",
        "GF":     "GF",
        "OUTROS": "Outros",
        # já completos (para idempotência)
        "Pilares":         "Pilares",
        "Lateral de Viga": "Lateral de Viga",
        "Fundos de Viga":  "Fundos de Viga",
        "Lajes":           "Lajes",
        "Outros":          "Outros",
    }

    # Cor de fundo distinta por classe ER
    _ER_CLASS_COLORS: dict = {
        "Pilares":         Contextual.PURPLE,
        "Lateral de Viga": Accent.INTERACTIVE,
        "Fundos de Viga":  Semantic.WARNING,
        "Lajes":           Semantic.SUCCESS,
        "GF":              Semantic.DANGER,
        "Outros":          Text.SECONDARY,
    }

    def _make_combo_chip(
        self,
        label: str,
        bg_color: str,
        options: list,
        on_select,
        fixed_width: int = 82,
    ) -> "QPushButton":
        """Chip clicável que abre QMenu para seleção. on_select(str) chamado com o valor."""
        from PySide6.QtWidgets import QMenu
        btn = QPushButton(label)
        btn.setFixedHeight(20)
        if fixed_width:
            btn.setFixedWidth(fixed_width)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ color: {Colors.BG_DEEP}; background: {bg_color};"
            " border-radius: 3px; padding: 0 6px; font-size: 10px; font-weight: bold;"
            " border: none; text-align: center; }}"
            f"QPushButton:hover {{ background: {bg_color}; border: 1px solid white; }}"
        )
        menu = QMenu(btn)
        menu.setStyleSheet(_resolve_css("""
            QMenu { background: {Colors.BG_PANEL}; border: 1px solid {Colors.BORDER_DEFAULT};
                    color: {Colors.TEXT_PRIMARY}; font-size: 11px; }
            QMenu::item:selected { background: {Colors.BG_CARD}; }
        """))
        def _refresh_menu():
            menu.clear()
            for opt in options:
                act = menu.addAction(str(opt))
                act.triggered.connect(lambda checked=False, o=opt: on_select(o))
        _refresh_menu()
        btn.clicked.connect(lambda: menu.exec(btn.mapToGlobal(btn.rect().bottomLeft())))
        return btn

    def _make_chip_with_conf(
        self,
        parent_layout,
        chip_label: str,
        bg_color: str,
        options: list,
        on_select,
        chip_width: int,
        conf: float,
        conf_notes_key: str,
        row_id: str,
        notes: dict,
        on_conf_save,
    ):
        """Adiciona ao layout um par [chip combo] [conf%] independentes."""
        conf_color = (
            Colors.ACCENT_SUCCESS_ALT if conf >= 0.85 else
            Colors.ACCENT_WARNING     if conf >= 0.60 else
            Colors.ACCENT_DANGER      if conf > 0    else
            Colors.TEXT_DIM
        )
        chip = self._make_combo_chip(chip_label, bg_color, options, on_select, chip_width)
        lbl_c = QLabel(f"{conf:.0%}" if conf > 0 else "—%")
        lbl_c.setFixedWidth(30)
        lbl_c.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_c.setStyleSheet(
            f"color: {conf_color}; font-size: 10px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        parent_layout.addWidget(chip)
        parent_layout.addWidget(lbl_c)

    def _get_triagem_notes(self, row: dict) -> dict:
        """Lê notas JSON do row de triagem (pavimento, er_class etc.)."""
        import json as _json
        try:
            return _json.loads(row.get('notes') or '{}')
        except Exception:
            return {}

    def _save_triagem_field(self, row_id: str, field: str, value: str):
        """Salva campo em obra_triagem pelo id."""
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        try:
            conn = _sq3.connect(str(DB))
            conn.execute(f"UPDATE obra_triagem SET {field}=? WHERE id=?", (value, row_id))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _save_triagem_notes_field(self, row_id: str, notes_key: str, value: str, current_notes: dict):
        """Atualiza uma chave dentro do JSON notes de obra_triagem."""
        import json as _json
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        current_notes[notes_key] = value
        try:
            conn = _sq3.connect(str(DB))
            conn.execute("UPDATE obra_triagem SET notes=? WHERE id=?",
                         (_json.dumps(current_notes, ensure_ascii=False), row_id))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _make_triagem_card(self, row: dict) -> QWidget:
        """Cria um card para uma sugestão de triagem."""
        status = row.get('status', 'pending')

        card = QFrame()
        if status == 'approved':
            card_bg = "rgba(0, 200, 120, 15)"
        else:
            card_bg = Colors.BG_DEEP
        card.setStyleSheet(
            f"QFrame {{ background: {card_bg};"
            f" border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 5px; }}"
        )
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(8, 4, 8, 4)
        card_layout.setSpacing(8)

        conf = float(row.get('confidence', 0.0))
        conf_color = (
            Colors.ACCENT_SUCCESS_ALT if conf >= 0.85 else
            Colors.ACCENT_WARNING if conf >= 0.60 else
            Colors.ACCENT_DANGER
        )
        cat_color = Colors.ACCENT_WARNING if status == 'review_required' else Colors.ACCENT_PRIMARY

        # Filename
        fname = row.get('file_name', '')
        lbl_file = QLabel(fname)
        lbl_file.setToolTip(row.get('file_path', fname))
        fname_color = Colors.TEXT_DIM if status == 'rejected' else Colors.TEXT_PRIMARY
        lbl_file.setStyleSheet(
            f"color: {fname_color}; font-size: 11px; background: transparent; border: none;"
        )

        row_id    = row['id']
        file_name = row.get('file_name', '')
        file_path = row.get('file_path', '')
        notes     = self._get_triagem_notes(row)

        # ── Chips com % independentes ─────────────────────────────────────────
        cat = row.get('suggested_category', '')
        if "Bruto" in cat:       cat_short = "Bruto"
        elif "Reversa" in cat or "Engenharia" in cat: cat_short = "Eng.Reversa"
        elif "Detalhe" in cat:   cat_short = "Detalhe"
        elif "Limpos" in cat:    cat_short = "Limpas"
        else:                    cat_short = cat[:12]

        cat_options_labels = [lbl for lbl, _ in self._TRIAGEM_CAT_OPTIONS]

        # Classificador automático (usado como fallback quando notes vazio)
        inferred = self._classify_filename(file_name)

        def _on_cat_change(opt_label):
            full_cat = dict(self._TRIAGEM_CAT_OPTIONS).get(opt_label, opt_label)
            self._save_triagem_field(row_id, 'suggested_category', full_cat)
            self._save_triagem_field(row_id, 'confidence', '1.0')
            QTimer.singleShot(60, self._refresh_triagem_panel)

        # [Categoria] cat_conf%
        cat_conf = conf  # confidence do RAG = confiança da categoria
        self._make_chip_with_conf(
            card_layout, cat_short, cat_color, cat_options_labels, _on_cat_change,
            82, cat_conf, 'cat_confidence', row_id, notes, None
        )

        # [Classe ER] class_conf%  — mostrar se Eng.Reversa (manual ou inferido)
        is_er = ("Reversa" in cat or "Engenharia" in cat or
                 notes.get('er_class') or inferred['er_class'] != 'OUTROS')
        if is_er:
            er_class_current = notes.get('er_class') or inferred['er_class']
            # Converter short code → label completo para exibição
            er_class_display = self._ER_SHORT_TO_FULL.get(er_class_current, er_class_current)
            # Cor distinta por classe
            er_class_color = self._ER_CLASS_COLORS.get(er_class_display, Contextual.SLATE)
            cls_conf = float(notes.get('class_confidence', inferred['class_conf']))

            def _on_class_change(opt, _notes=notes):
                _notes['class_confidence'] = 1.0
                self._save_triagem_notes_field(row_id, 'er_class', opt, _notes)
                self._save_triagem_notes_field(row_id, 'class_confidence', 1.0, _notes)
                QTimer.singleShot(60, self._refresh_triagem_panel)

            self._make_chip_with_conf(
                card_layout, er_class_display, er_class_color,
                self._ER_CLASS_OPTIONS, _on_class_change,
                115, cls_conf, 'class_confidence', row_id, notes, None
            )

        # [Pavimento] pav_conf%
        pav_inferred = inferred['pav']
        pav_inferred_conf = inferred['pav_conf']
        pav_current = notes.get('pavimento') or pav_inferred
        pav_short   = pav_current[:11] if len(pav_current) > 11 else pav_current
        pav_conf    = float(notes.get('pav_confidence', pav_inferred_conf))

        def _on_pav_change(opt, _notes=notes):
            _notes['pav_confidence'] = 1.0
            self._save_triagem_notes_field(row_id, 'pavimento', opt, _notes)
            self._save_triagem_notes_field(row_id, 'pav_confidence', 1.0, _notes)
            QTimer.singleShot(60, self._refresh_triagem_panel)

        pav_chip = self._make_combo_chip(pav_short, Colors.BG_CARD, self._PAV_OPTIONS, _on_pav_change, 88)
        pav_chip.setStyleSheet(
            f"QPushButton {{ color: {Colors.TEXT_PRIMARY}; background: {Colors.BG_CARD};"
            f" border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 3px; padding: 0 5px;"
            " font-size: 10px; font-weight: bold; }}"
            f"QPushButton:hover {{ border-color: {Colors.ACCENT_PRIMARY}; }}"
        )
        pav_conf_color = (
            Colors.ACCENT_SUCCESS_ALT if pav_conf >= 0.85 else
            Colors.ACCENT_WARNING     if pav_conf >= 0.60 else
            Colors.TEXT_DIM
        )
        lbl_pav_conf = QLabel(f"{pav_conf:.0%}" if pav_conf > 0 else "—%")
        lbl_pav_conf.setFixedWidth(30)
        lbl_pav_conf.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_pav_conf.setStyleSheet(
            f"color: {pav_conf_color}; font-size: 10px; font-weight: bold;"
            " background: transparent; border: none;"
        )

        card_layout.addWidget(lbl_file, 1)
        card_layout.addWidget(pav_chip)
        card_layout.addWidget(lbl_pav_conf)

        if status == 'approved':
            lbl_badge = QLabel("✅")
            lbl_badge.setFixedWidth(20)
            lbl_badge.setStyleSheet("background: transparent; border: none;")
            card_layout.addWidget(lbl_badge)
        elif status == 'rejected':
            lbl_badge = QLabel("❌")
            lbl_badge.setFixedWidth(20)
            lbl_badge.setStyleSheet("background: transparent; border: none;")
            card_layout.addWidget(lbl_badge)
        else:
            # Pending / review_required — botoes de acao
            btn_ok = QPushButton("✓")
            btn_ok.setToolTip("Aprovar — adicionar à Fase 2")
            btn_ok.setFixedSize(28, 24)
            btn_ok.setStyleSheet(_resolve_css("""
                QPushButton {
                    background: rgba(0, 200, 120, 38); color: {Colors.ACCENT_SUCCESS_ALT};
                    border: 1px solid {Colors.ACCENT_SUCCESS_ALT}; border-radius: 4px;
                    font-size: 12px; font-weight: bold; padding: 0;
                }
                QPushButton:hover { background: rgba(0, 200, 120, 82); }
            """))

            btn_no = QPushButton("✗")
            btn_no.setToolTip("Rejeitar — não incluir na Fase 2")
            btn_no.setFixedSize(28, 24)
            btn_no.setStyleSheet(_resolve_css("""
                QPushButton {
                    background: rgba(255, 80, 80, 31); color: {Colors.ACCENT_DANGER};
                    border: 1px solid {Colors.ACCENT_DANGER}; border-radius: 4px;
                    font-size: 12px; font-weight: bold; padding: 0;
                }
                QPushButton:hover { background: rgba(255, 80, 80, 71); }
            """))

            sug_cat = row.get('suggested_category', '')
            btn_ok.clicked.connect(lambda _, rid=row_id, fn=file_name, fp=file_path,
                                   sc=sug_cat, c=card:
                                   self._approve_triagem_row(rid, fn, fp, sc, c))
            btn_no.clicked.connect(lambda _, rid=row_id, c=card:
                                   self._reject_triagem_row(rid, c))

            card_layout.addWidget(btn_ok)
            card_layout.addWidget(btn_no)

        return card

    def _approve_triagem_row(self, row_id: str, file_name: str, file_path: str,
                             suggested_category: str, card_widget):
        """Aprova uma sugestão: salva em project_documents fase=2 e atualiza triagem."""
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        work_name = self.current_work_name or ""
        if not work_name:
            return
        fase2_cat = self._TRIAGEM_TO_FASE2.get(suggested_category, "Estruturais Pavimentos Limpos")
        ext = Path(file_path).suffix.lower() if file_path else ""
        try:
            self.db.save_work_document(
                work_name=work_name,
                name=file_name,
                file_path=file_path,
                extension=ext,
                storage_path=None,
                phase=2,
                category=fase2_cat,
            )
        except Exception as e:
            QMessageBox.warning(self, "Triagem", f"Erro ao salvar documento:\n{e}")
            return
        try:
            conn = _sq3.connect(str(DB))
            conn.execute("UPDATE obra_triagem SET status='approved' WHERE id=?", (row_id,))
            conn.commit()
            conn.close()
        except Exception:
            pass
        QTimer.singleShot(100, self._refresh_triagem_panel)
        QTimer.singleShot(200, self._refresh_preprocess_panel)
        QTimer.singleShot(200, self._refresh_projetos_finalizados_panel)
        QTimer.singleShot(200, self._refresh_detalhamentos_panel)

    def _reject_triagem_row(self, row_id: str, card_widget):
        """Rejeita uma sugestão."""
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        try:
            conn = _sq3.connect(str(DB))
            conn.execute("UPDATE obra_triagem SET status='rejected' WHERE id=?", (row_id,))
            conn.commit()
            conn.close()
        except Exception:
            pass
        QTimer.singleShot(100, self._refresh_triagem_panel)

    def _refresh_triagem_summary(self):
        """Atualiza o label de summary sem reconstruir toda a lista."""
        rows = self._load_triagem_rows()
        if not hasattr(self, '_lbl_triagem_summary'):
            return
        if not rows:
            self._lbl_triagem_summary.setText("🧠 Sugestões IA — nenhuma pendente")
        else:
            high   = sum(1 for r in rows if r['confidence'] >= 0.80)
            review = sum(1 for r in rows if r['status'] == 'review_required')
            self._lbl_triagem_summary.setText(
                f"🧠 Sugestões IA — {len(rows)} pendentes  "
                f"({high} alta conf.  |  {review} revisar)"
            )

    def _approve_all_high_confidence_triagem(self):
        """Aprova em lote todas as sugestões com confiança >= 80%."""
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        work_name = self.current_work_name or ""
        if not work_name:
            QMessageBox.warning(self, "Triagem", "Selecione uma obra primeiro.")
            return
        rows = self._load_triagem_rows()
        high_rows = [r for r in rows if r['confidence'] >= 0.80]
        if not high_rows:
            QMessageBox.information(self, "Triagem", "Nenhuma sugestão com confiança ≥ 80%.")
            return
        approved = 0
        errors   = []
        for row in high_rows:
            fase2_cat = self._TRIAGEM_TO_FASE2.get(
                row.get('suggested_category', ''), "Estruturais Pavimentos Limpos"
            )
            ext = Path(row.get('file_path', '')).suffix.lower()
            try:
                self.db.save_work_document(
                    work_name=work_name,
                    name=row['file_name'],
                    file_path=row['file_path'],
                    extension=ext,
                    storage_path=None,
                    phase=2,
                    category=fase2_cat,
                )
                approved += 1
            except Exception as e:
                errors.append(str(e))
        if approved:
            try:
                conn = _sq3.connect(str(DB))
                placeholders = ','.join('?' * len(high_rows))
                conn.execute(
                    f"UPDATE obra_triagem SET status='approved' WHERE id IN ({placeholders})",
                    [r['id'] for r in high_rows],
                )
                conn.commit()
                conn.close()
            except Exception:
                pass
        msg = f"✅ {approved} arquivos aprovados e enviados para Fase 2."
        if errors:
            msg += f"\n\n⚠ {len(errors)} erros ao salvar."
        QMessageBox.information(self, "Triagem — Aprovação em Lote", msg)
        self._refresh_triagem_panel()
        QTimer.singleShot(200, self._refresh_preprocess_panel)
        QTimer.singleShot(200, self._refresh_projetos_finalizados_panel)

    # ── Helpers: Classificador de Filename ─────────────────────────────────

    def _classify_filename(self, filename: str) -> dict:
        """
        Classifica filename em pavimento, classe ER e categoria.
        Retorna: {pav, pav_conf, er_class, class_conf, category, cat_conf}
        Padrões aprendidos de dados reais (ALIMONTI, TMC, 1610.01, etc.)
        """
        import re
        import unicodedata

        # Normaliza acentos (É→E, Ã→A, etc.) antes de fazer .upper()
        stem = unicodedata.normalize('NFKD', filename)
        stem = ''.join(c for c in stem if not unicodedata.combining(c))
        stem = re.sub(r'\.\w+$', '', stem.upper())  # sem extensão
        # Normaliza sinais de grau/ordinal para 'O' (U+00B0=°, U+00BA=º nos filenames reais)
        stem = stem.replace('\u00b0', 'O').replace('\u00ba', 'O')

        result: dict = {
            'pav': 'OUTROS', 'pav_conf': 0.0,
            'er_class': 'OUTROS', 'class_conf': 0.0,
            'category': '', 'cat_conf': 0.0,
        }

        # ── Classe ER ──────────────────────────────────────────────────────
        # Tokens isolados por separadores (-, espaço) antes do Rev (R\d+)
        # PL ≠ PLA (PLA = PLANTA)
        ER_MAP = [
            (r'(?<![A-Z])FV(?![A-Z])', 'FV'),
            (r'(?<![A-Z])LV(?![A-Z])', 'LV'),
            (r'(?<![A-Z])LJ(?![A-Z])', 'LAJ'),
            (r'(?<![A-Z])LAJ(?![A-Z])', 'LAJ'),
            (r'(?<![A-Z])GF(?![A-Z])', 'GF'),
            # PL mas não PLA (e não EST-PL, etc.)
            (r'[-\s]PL[-\s.]|[-\s]PL$', 'PIL'),
        ]
        for pat, cls in ER_MAP:
            if re.search(pat, stem):
                result['er_class'] = cls
                result['class_conf'] = 0.90
                break

        # ── Categoria ──────────────────────────────────────────────────────
        # Eng.Reversa: tem classe ER isolada antes de revisão
        if re.search(r'[-\s](FV|LV|LJ|GF|LAJ)[-\s.]R\d|[-\s]PL[-\s.]R\d', stem):
            result['category'] = 'Eng.Reversa'
            result['cat_conf'] = 0.95
        elif re.search(r'EST[-.]?(LO|EX|PE)[-.]', stem):
            result['category'] = 'Bruto'
            result['cat_conf'] = 0.88
        elif re.search(r'\bLOC\b', stem):
            result['category'] = 'Bruto'
            result['cat_conf'] = 0.55

        # ── Pavimento (do mais específico ao mais genérico) ─────────────────

        # COB + DECK combo
        if re.search(r'COB\w*\s*[-E]\s*DECK|DECK\s*[-E]\s*COB', stem):
            result['pav'], result['pav_conf'] = 'COB/DECK', 0.95

        # TIPO N-M  ("TIPO - 3 AO 12 PAV" ou "TIPO 3-12")
        elif m := re.search(r'TIPO[-\s.]+(\d+)O?\s*AO\s*(\d+)', stem):
            result['pav'] = f"TIPO {m.group(1)}-{m.group(2)}"
            result['pav_conf'] = 0.93

        # TIPO N  (TIP1, TIP2, TIPO 1…)
        elif m := re.search(r'TIP[-\s.]?(\d+)\b|TIPO[-\s.]+(\d+)', stem):
            n = m.group(1) or m.group(2)
            result['pav'], result['pav_conf'] = f"TIPO {n}", 0.91

        # TIPO  (TIP\b, TIPO)
        elif re.search(r'\bTIPO\b|\bTIP\b', stem):
            result['pav'], result['pav_conf'] = 'TIPO', 0.88

        # N SUBSOLO  (1SUB, 2SUB, PLA-2SUB, 1º SUBSOLO…)
        elif m := re.search(r'PLA-(\d+)SUB|[-\s.](\d+)O?\s*SUB\b|[-\s.](\d+)SUB[-\s.]', stem):
            n = next(g for g in m.groups() if g)
            result['pav'], result['pav_conf'] = f"{n}º SUBSOLO", 0.93

        elif re.search(r'\bSUBSOL|\bSUB[-\s]SOL', stem):
            result['pav'], result['pav_conf'] = 'SUBSOLO', 0.85

        # FUNDAÇÃO  (FUN, FUND)
        elif re.search(r'\bFUN\b|\bFUND\b|\bFUNDA', stem):
            result['pav'], result['pav_conf'] = 'FUNDAÇÃO', 0.92

        # TÉRREO  (TER, TERR, TERRE)
        elif re.search(r'\bTERR\b|\bTERRE|\bTER\b', stem):
            result['pav'], result['pav_conf'] = 'TÉRREO', 0.91

        # COBERTURA  (COB, COBE)
        elif re.search(r'\bCOBE\b|\bCOBER|\bCOB\b', stem):
            result['pav'], result['pav_conf'] = 'COBERTURA', 0.91

        # ÁTICO  (ATC, ATICO)
        elif re.search(r'\bATC\b|\bATIC', stem):
            result['pav'], result['pav_conf'] = 'ÁTICO', 0.90

        # BARRILETE  (BARR, BARRI)
        elif re.search(r'\bBARRI|\bBARR\b|\bBAR\b', stem):
            result['pav'], result['pav_conf'] = 'BARRILETE', 0.90

        # DECK
        elif re.search(r'\bDECK\b', stem):
            result['pav'], result['pav_conf'] = 'DECK', 0.90

        # Nº PAVIMENTO explícito  (1PAV, 2PAV, 8PAV, PLA-1PAV, PLA-2PAV)
        elif m := re.search(
            r'PLA[-.](\d+)PAV|[-\s.](\d+)PAV\b|[-\s.](\d+)O?\s*PAV\b', stem
        ):
            n = next(g for g in m.groups() if g)
            result['pav'], result['pav_conf'] = f"{n}º PAVIMENTO", 0.92

        # Nº PV  (1PV, 2PV)
        elif m := re.search(r'[-\s.](\d+)PV\b', stem):
            result['pav'], result['pav_conf'] = f"{m.group(1)}º PAVIMENTO", 0.90

        # Nº P  curto — ex: "-13P-", "-14P-" (isolado com separadores)
        elif m := re.search(r'[-.](\d{1,2})P[-.]', stem):
            result['pav'], result['pav_conf'] = f"{m.group(1)}º PAVIMENTO", 0.86

        # Ordinal do estilo Eng.Reversa: "13° PAV" (° normalizado para O)
        elif m := re.search(r'(\d+)O[-.\s]*PAV', stem):
            result['pav'], result['pav_conf'] = f"{m.group(1)}º PAVIMENTO", 0.88

        # LOC = planta de localização
        elif re.search(r'\bLOC\b', stem):
            result['pav'], result['pav_conf'] = 'LOCALIZAÇÃO', 0.65

        # TAMPÃO
        elif re.search(r'\bTAMP\b', stem):
            result['pav'], result['pav_conf'] = 'TAMPÃO', 0.60

        return result

    def _infer_pav_from_filename(self, filename: str) -> str:
        """Wrapper legado — retorna só o nome do pavimento."""
        return self._classify_filename(filename)['pav']

    @staticmethod
    def _pav_sort_key(pav_name: str) -> tuple:
        """Chave de ordenação canônica para nomes de pavimento."""
        import re
        p = pav_name.upper().strip().replace('°', 'O').replace('º', 'O')
        if p in ('FUNDAÇÃO', 'FUNDACAO'):              return (0, 0)
        m = re.match(r'(\d+)O?\s*SUBSOLO', p)
        if m:                                           return (1, int(m.group(1)))
        if 'SUBSOLO' in p:                              return (1, 0)
        if p in ('TÉRREO', 'TERREO'):                   return (2, 0)
        m = re.match(r'(\d+)O?\s*PAVIMENTO', p)
        if m:                                           return (3, int(m.group(1)))
        m = re.match(r'TIPO\s*(\d+)-(\d+)', p)
        if m:                                           return (4, int(m.group(1)))
        m = re.match(r'TIPO\s*(\d+)', p)
        if m:                                           return (4, int(m.group(1)))
        if 'TIPO' in p:                                 return (4, 0)
        if p in ('ÁTICO', 'ATICO'):                     return (5, 0)
        if p == 'COBERTURA':                            return (6, 0)
        if p == 'COB/DECK':                             return (7, 0)
        if p == 'DECK':                                 return (8, 0)
        if p == 'BARRILETE':                            return (9, 0)
        if 'CAIXA' in p:                                return (10, 0)
        if p in ('LOCALIZAÇÃO', 'LOCALIZACAO', 'LOC'):  return (11, 0)
        if p in ('TAMPÃO', 'TAMPAO'):                   return (12, 0)
        return (99, 0)  # OUTROS

    def _get_row_pav(self, row: dict) -> str:
        """Pavimento do row: notes primeiro (correção manual), depois classifier."""
        notes = self._get_triagem_notes(row)
        pav = notes.get('pavimento', '')
        if pav and pav != 'OUTROS':
            return pav
        return self._classify_filename(row.get('file_name', ''))['pav']

    def _make_pavimento_section_header(self, pav_name: str) -> QWidget:
        """Cria um separador visual de secao por pavimento."""
        hdr = QWidget()
        hdr.setStyleSheet("background: transparent;")
        h = QHBoxLayout(hdr)
        h.setContentsMargins(0, 8, 0, 2)
        h.setSpacing(8)
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setStyleSheet(f"color: {Colors.BORDER_DEFAULT}; background: {Colors.BORDER_DEFAULT};")
        lbl = QLabel(pav_name)
        lbl.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 10px; font-weight: bold;"
            " background: transparent; border: none; padding: 0 6px;"
        )
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet(f"color: {Colors.BORDER_DEFAULT}; background: {Colors.BORDER_DEFAULT};")
        h.addWidget(line1, 1)
        h.addWidget(lbl)
        h.addWidget(line2, 1)
        return hdr

    # ── Pré-Processamento Panel ─────────────────────────────────────────────

    def _build_preprocess_panel(self, layout):
        """Painel 'Pré-Processamento Diagnostic Hub' — brutos aprovados aguardando recorte."""
        outer = QFrame()
        outer.setObjectName("PreprocessPanel")
        outer.setStyleSheet(_resolve_css("""
            QFrame#PreprocessPanel {
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.ACCENT_TEAL};
                border-radius: 8px;
            }
        """))
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(12, 10, 12, 10)
        outer_layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        self._lbl_preprocess_summary = QLabel("✂ Pré-Processamento — Estruturais Brutos Aprovados")
        self._lbl_preprocess_summary.setStyleSheet(_resolve_css(
            "color: {Colors.ACCENT_TEAL}; font-size: 12px; font-weight: bold;"
            " background: transparent; border: none;"
        ))

        btn_open_hub = QPushButton("▶ Abrir Diagnostic Hub")
        btn_open_hub.setToolTip("Navegar para o Diagnostic Hub para processar recortes")
        btn_open_hub.setStyleSheet(_resolve_css("""
            QPushButton {
                background: rgba(0, 180, 180, 38); color: {Colors.ACCENT_TEAL};
                border: 1px solid {Colors.ACCENT_TEAL}; border-radius: 4px;
                padding: 3px 12px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(0, 180, 180, 71); }
        """))

        btn_reload_pre = QPushButton("↻")
        btn_reload_pre.setToolTip("Recarregar lista de aprovados")
        btn_reload_pre.setFixedWidth(28)
        btn_reload_pre.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                padding: 3px; font-size: 13px;
            }
            QPushButton:hover { color: {Colors.TEXT_PRIMARY}; }
        """))

        self._btn_preprocess_toggle = QPushButton("▲")
        self._btn_preprocess_toggle.setFixedWidth(28)
        self._btn_preprocess_toggle.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {Text.SECONDARY}; border: none; font-size: 11px; }}"
        )

        header.addWidget(self._lbl_preprocess_summary)
        header.addStretch()
        header.addWidget(btn_open_hub)
        header.addWidget(btn_reload_pre)
        header.addWidget(self._btn_preprocess_toggle)
        outer_layout.addLayout(header)

        # Content colapsável
        self._preprocess_content_widget = QWidget()
        pre_content_layout = QVBoxLayout(self._preprocess_content_widget)
        pre_content_layout.setContentsMargins(0, 4, 0, 0)
        pre_content_layout.setSpacing(0)

        pre_scroll = QScrollArea()
        pre_scroll.setMaximumHeight(480)
        pre_scroll.setMinimumHeight(160)
        pre_scroll.setWidgetResizable(True)
        pre_scroll.setStyleSheet(_resolve_css("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { border: none; background: {Colors.BG_DEEP}; width: 6px; margin: 0; }
            QScrollBar::handle:vertical { background: {Colors.BG_CARD}; min-height: 16px; border-radius: 3px; }
        """))

        self._preprocess_list_container = QWidget()
        self._preprocess_list_container.setStyleSheet("background: transparent;")
        self._preprocess_list_layout = QVBoxLayout(self._preprocess_list_container)
        self._preprocess_list_layout.setSpacing(4)
        self._preprocess_list_layout.setContentsMargins(0, 0, 0, 0)

        pre_scroll.setWidget(self._preprocess_list_container)
        pre_content_layout.addWidget(pre_scroll)
        outer_layout.addWidget(self._preprocess_content_widget)

        layout.addWidget(outer)

        def _toggle_pre():
            vis = not self._preprocess_content_widget.isVisible()
            self._preprocess_content_widget.setVisible(vis)
            self._btn_preprocess_toggle.setText("▲" if vis else "▼")

        self._btn_preprocess_toggle.clicked.connect(_toggle_pre)
        btn_reload_pre.clicked.connect(self._refresh_preprocess_panel)
        btn_open_hub.clicked.connect(lambda: self.request_tab_switch.emit(1))

        self._refresh_preprocess_panel()

    def _load_approved_brutos(self) -> list:
        """Carrega brutos aprovados da obra atual a partir de obra_triagem."""
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        work_name = self.current_work_name or ""
        if not work_name:
            return []
        try:
            conn = _sq3.connect(str(DB))
            conn.row_factory = _sq3.Row
            cur = conn.execute(
                "SELECT * FROM obra_triagem WHERE obra_name=? AND status='approved'"
                " AND suggested_category LIKE '%Bruto%'"
                " ORDER BY suggested_order ASC, file_name ASC",
                (work_name,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception:
            return []

    def _refresh_preprocess_panel(self):
        """Reconstrói a lista de brutos aprovados no painel de pré-processamento."""
        if not hasattr(self, '_preprocess_list_layout'):
            return
        while self._preprocess_list_layout.count():
            item = self._preprocess_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = self._load_approved_brutos()

        if not rows:
            work = self.current_work_name or "..."
            lbl = QLabel(
                f"Nenhum bruto aprovado para {work}.\n"
                "Aprove DXFs brutos no painel acima para iniciar o pré-processamento."
            )
            lbl.setWordWrap(True)
            lbl.setStyleSheet(_resolve_css(
                "color: {Colors.TEXT_DIM}; font-size: 11px; padding: 10px;"
                " background: transparent; border: none;"
            ))
            self._preprocess_list_layout.addWidget(lbl)
            if hasattr(self, '_lbl_preprocess_summary'):
                self._lbl_preprocess_summary.setText(
                    "✂ Pré-Processamento — nenhum bruto aprovado"
                )
        else:
            if hasattr(self, '_lbl_preprocess_summary'):
                self._lbl_preprocess_summary.setText(
                    f"✂ Pré-Processamento — {len(rows)} brutos aprovados aguardando recorte"
                )
            # Agrupar por pavimento e ordenar canonicamente
            groups: dict = {}
            for row in rows:
                pav = self._get_row_pav(row)
                groups.setdefault(pav, []).append(row)
            sorted_groups = sorted(groups.items(), key=lambda kv: self._pav_sort_key(kv[0]))
            multi = len(sorted_groups) > 1
            for pav_name, pav_rows in sorted_groups:
                if multi:
                    hdr = self._make_pavimento_section_header(pav_name)
                    self._preprocess_list_layout.addWidget(hdr)
                for row in pav_rows:
                    card = self._make_preprocess_card(row)
                    self._preprocess_list_layout.addWidget(card)

        self._preprocess_list_layout.addStretch()

    def _make_preprocess_card(self, row: dict) -> QWidget:
        """Card de um bruto aprovado no painel de pré-processamento."""
        fname_pre = row.get('file_name', '')
        obra_pre  = row.get('obra_name', self.current_work_name or '')
        status_label_pre, _ = self._get_recorte_status(obra_pre, fname_pre)
        all_ok = "recortes OK" in status_label_pre
        card_bg = "rgba(0, 200, 120, 13)" if all_ok else Colors.BG_DEEP
        card_border = Colors.ACCENT_SUCCESS_ALT if all_ok else Colors.BORDER_DEFAULT

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {card_bg};"
            f" border: 1px solid {card_border}; border-radius: 5px; }}"
        )
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(8, 4, 8, 4)
        card_layout.setSpacing(8)

        fname = row.get('file_name', '')
        lbl_file = QLabel(fname)
        lbl_file.setToolTip(row.get('file_path', fname))
        lbl_file.setStyleSheet(_resolve_css(
            "color: {Colors.TEXT_PRIMARY}; font-size: 11px; background: transparent; border: none;"
        ))

        # Badge de status do recorte
        status_label, status_color = self._get_recorte_status(
            row.get('obra_name', self.current_work_name or ''), fname
        )
        lbl_status = QLabel(status_label)
        lbl_status.setStyleSheet(
            f"color: {status_color}; font-size: 10px; font-weight: bold;"
            " background: transparent; border: none; padding: 0 4px;"
        )

        btn_process = QPushButton("✂ Recortar")
        btn_process.setToolTip("Abrir no Diagnostic Hub para processar recortes")
        btn_process.setFixedWidth(90)
        btn_process.setStyleSheet(_resolve_css("""
            QPushButton {
                background: rgba(0, 180, 180, 31); color: {Colors.ACCENT_TEAL};
                border: 1px solid {Colors.ACCENT_TEAL}; border-radius: 4px;
                font-size: 10px; font-weight: bold; padding: 2px 6px;
            }
            QPushButton:hover { background: rgba(0, 180, 180, 64); }
        """))

        card_layout.addWidget(lbl_file, 1)
        card_layout.addWidget(lbl_status)
        card_layout.addWidget(btn_process)

        file_path = row.get('file_path', '')
        obra_name = row.get('obra_name', '')
        btn_process.clicked.connect(
            lambda _, fp=file_path, on=obra_name:
            self._open_hub_with_bruto(on, fp)
        )
        return card

    def _get_recorte_status(self, obra_name: str, file_name: str) -> tuple:
        """
        Consulta obra_recortes. Retorna (label, color) para badge do card.
        label: str  |  color: str (hex)
        """
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        try:
            conn = _sq3.connect(str(DB))
            row = conn.execute(
                "SELECT COUNT(*) AS total,"
                " SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved"
                " FROM obra_recortes WHERE obra_name=? AND dxf_bruto_path LIKE ?",
                (obra_name, f"%{file_name}%")
            ).fetchone()
            conn.close()
            total, approved = row[0], (row[1] or 0)
            if total == 0:
                return ("⬜ sem recorte", Colors.TEXT_DIM)
            if approved >= total:
                return (f"✅ {total} recortes OK", Colors.ACCENT_SUCCESS_ALT)
            return (f"🔶 {approved}/{total} aprovados", Colors.ACCENT_WARNING)
        except Exception:
            return ("⬜ sem recorte", Colors.TEXT_DIM)

    def _open_hub_with_bruto(self, obra_name: str, file_path: str):
        """Navega para Diagnostic Hub e sinaliza para carregar o bruto."""
        self.request_tab_switch.emit(1)
        # Emitir após tab switch para garantir que o hub está visível
        from PySide6.QtCore import QTimer
        QTimer.singleShot(150, lambda: self.request_open_bruto.emit(obra_name, file_path))

    # ── Projetos Finalizados Panel ──────────────────────────────────────────

    def _load_projetos_finalizados(self) -> list:
        """Carrega projetos finalizados aprovados de obra_triagem."""
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        work_name = self.current_work_name or ""
        if not work_name:
            return []
        try:
            conn = _sq3.connect(str(DB))
            conn.row_factory = _sq3.Row
            cur = conn.execute(
                "SELECT * FROM obra_triagem WHERE obra_name=? AND status='approved'"
                " AND (suggested_category LIKE '%Engenharia Reversa%'"
                "      OR suggested_category LIKE '%Projetos Finalizados%')"
                " ORDER BY file_name ASC",
                (work_name,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception:
            return []

    def _build_projetos_finalizados_panel(self, layout):
        """Painel colapsavel de Projetos Finalizados para Engenharia Reversa."""
        outer = QFrame()
        outer.setObjectName("ProjetosFinalizadosPanel")
        outer.setStyleSheet(_resolve_css("""
            QFrame#ProjetosFinalizadosPanel {
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 8px;
            }
        """))
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(12, 10, 12, 10)
        outer_layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        self._lbl_projetos_summary = QLabel("Projetos Finalizados para Engenharia Reversa")
        self._lbl_projetos_summary.setStyleSheet(_resolve_css(
            "color: {Colors.ACCENT_PRIMARY}; font-size: 12px; font-weight: bold;"
            " background: transparent; border: none;"
        ))

        btn_open_reverse = QPushButton("▶ Abrir Diagnostic Reverse Hub")
        btn_open_reverse.setToolTip("Navegar para o Diagnostic Reverse Hub para processar eng. reversa")
        btn_open_reverse.setStyleSheet(_resolve_css("""
            QPushButton {
                background: rgba(90, 40, 180, 38); color: {Colors.ACCENT_PRIMARY};
                border: 1px solid {Colors.ACCENT_PRIMARY}; border-radius: 4px;
                padding: 3px 12px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(90, 40, 180, 71); }
        """))

        btn_reload_proj = QPushButton("↻")
        btn_reload_proj.setToolTip("Recarregar lista de projetos finalizados")
        btn_reload_proj.setFixedWidth(28)
        btn_reload_proj.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                padding: 3px; font-size: 13px;
            }
            QPushButton:hover { color: {Colors.TEXT_PRIMARY}; }
        """))

        self._btn_projetos_toggle = QPushButton("▲")
        self._btn_projetos_toggle.setFixedWidth(28)
        self._btn_projetos_toggle.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {Text.SECONDARY}; border: none; font-size: 11px; }}"
        )

        header.addWidget(self._lbl_projetos_summary)
        header.addStretch()
        header.addWidget(btn_open_reverse)
        header.addWidget(btn_reload_proj)
        header.addWidget(self._btn_projetos_toggle)
        outer_layout.addLayout(header)

        # Content colapsavel
        self._projetos_content_widget = QWidget()
        proj_content_layout = QVBoxLayout(self._projetos_content_widget)
        proj_content_layout.setContentsMargins(0, 4, 0, 0)
        proj_content_layout.setSpacing(0)

        proj_scroll = QScrollArea()
        proj_scroll.setMaximumHeight(480)
        proj_scroll.setMinimumHeight(160)
        proj_scroll.setWidgetResizable(True)
        proj_scroll.setStyleSheet(_resolve_css("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { border: none; background: {Colors.BG_DEEP}; width: 6px; margin: 0; }
            QScrollBar::handle:vertical { background: {Colors.BG_CARD}; min-height: 16px; border-radius: 3px; }
        """))

        self._projetos_list_container = QWidget()
        self._projetos_list_container.setStyleSheet("background: transparent;")
        self._projetos_list_layout = QVBoxLayout(self._projetos_list_container)
        self._projetos_list_layout.setSpacing(4)
        self._projetos_list_layout.setContentsMargins(0, 0, 0, 0)

        proj_scroll.setWidget(self._projetos_list_container)
        proj_content_layout.addWidget(proj_scroll)
        outer_layout.addWidget(self._projetos_content_widget)

        layout.addWidget(outer)

        def _toggle_proj():
            vis = not self._projetos_content_widget.isVisible()
            self._projetos_content_widget.setVisible(vis)
            self._btn_projetos_toggle.setText("▲" if vis else "▼")

        self._btn_projetos_toggle.clicked.connect(_toggle_proj)
        btn_reload_proj.clicked.connect(self._refresh_projetos_finalizados_panel)
        btn_open_reverse.clicked.connect(lambda: self.request_tab_switch.emit(2))

        self._refresh_projetos_finalizados_panel()

    def _refresh_projetos_finalizados_panel(self):
        """Reconstroi a lista de projetos finalizados."""
        if not hasattr(self, '_projetos_list_layout'):
            return
        while self._projetos_list_layout.count():
            item = self._projetos_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = self._load_projetos_finalizados()

        if not rows:
            if hasattr(self, '_lbl_projetos_summary'):
                self._lbl_projetos_summary.setText("Projetos Finalizados — nenhum aprovado")
            lbl = QLabel("Nenhum projeto finalizado aprovado.")
            lbl.setWordWrap(True)
            lbl.setStyleSheet(_resolve_css(
                "color: {Colors.TEXT_DIM}; font-size: 11px; padding: 10px;"
                " background: transparent; border: none;"
            ))
            self._projetos_list_layout.addWidget(lbl)
        else:
            if hasattr(self, '_lbl_projetos_summary'):
                self._lbl_projetos_summary.setText(
                    f"Projetos Finalizados — {len(rows)} projetos finalizados"
                )
            # Agrupar por pavimento e subgrupo de classe
            # Agrupar por pavimento e ordenar canonicamente
            groups: dict = {}
            for row in rows:
                pav = self._get_row_pav(row)
                groups.setdefault(pav, []).append(row)
            sorted_groups = sorted(groups.items(), key=lambda kv: self._pav_sort_key(kv[0]))
            multi = len(sorted_groups) > 1
            for pav_name, pav_rows in sorted_groups:
                if multi:
                    hdr = self._make_pavimento_section_header(pav_name)
                    self._projetos_list_layout.addWidget(hdr)
                # Subgrupo por categoria
                sub_groups: dict = {}
                for row in pav_rows:
                    cat = row.get('suggested_category', 'Outros')
                    sub_groups.setdefault(cat, []).append(row)
                for cat_name, cat_rows in sub_groups.items():
                    if len(sub_groups) > 1:
                        lbl_sub = QLabel(cat_name)
                        lbl_sub.setStyleSheet(
                            f"color: {Colors.TEXT_DIM}; font-size: 10px;"
                            " background: transparent; border: none; padding: 2px 4px 0 4px;"
                        )
                        self._projetos_list_layout.addWidget(lbl_sub)
                    for row in cat_rows:
                        card = self._make_approved_item_card(row, show_er_class=True)
                        self._projetos_list_layout.addWidget(card)

        self._projetos_list_layout.addStretch()

    def _make_approved_item_card(self, row: dict, show_er_class: bool = False) -> QWidget:
        """Card harmonizado para items aprovados (Brutos e Projetos Finalizados)."""
        card = QFrame()
        card.setStyleSheet(_resolve_css("""
            QFrame {
                background: {Colors.BG_DEEP};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 5px;
            }
        """))
        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        row_id = row.get('id', '')
        fname  = row.get('file_name', '')
        notes  = self._get_triagem_notes(row)

        # Badge ✅
        lbl_badge = QLabel("✅")
        lbl_badge.setFixedWidth(18)
        lbl_badge.setStyleSheet("background: transparent; border: none; font-size: 12px;")

        # Filename
        lbl_file = QLabel(fname)
        lbl_file.setToolTip(row.get('file_path', fname))
        lbl_file.setStyleSheet(_resolve_css(
            "color: {Colors.TEXT_PRIMARY}; font-size: 11px; background: transparent; border: none;"
        ))

        cat = row.get('suggested_category', '')
        if "Bruto" in cat:       cat_short, cat_color = "Bruto",       Colors.ACCENT_WARNING
        elif "Reversa" in cat or "Engenharia" in cat: cat_short, cat_color = "Eng.Reversa", Colors.ACCENT_PRIMARY
        elif "Detalhe" in cat:   cat_short, cat_color = "Detalhe",     Colors.ACCENT_SUCCESS_ALT
        else:                    cat_short, cat_color = cat[:10],       Colors.TEXT_SECONDARY

        cat_options_labels = [lbl for lbl, _ in self._TRIAGEM_CAT_OPTIONS]
        inferred  = self._classify_filename(fname)
        cat_conf  = float(row.get('confidence', 0.0))
        pav_conf  = float(notes.get('pav_confidence', inferred['pav_conf']))
        cls_conf  = float(notes.get('class_confidence', inferred['class_conf']))

        def _on_cat_change(opt_label, _rid=row_id):
            full_cat = dict(self._TRIAGEM_CAT_OPTIONS).get(opt_label, opt_label)
            self._save_triagem_field(_rid, 'suggested_category', full_cat)
            self._save_triagem_field(_rid, 'confidence', '1.0')
            QTimer.singleShot(60, self._refresh_projetos_finalizados_panel)

        pav_current = notes.get('pavimento') or inferred['pav']
        pav_short   = pav_current[:11] if len(pav_current) > 11 else pav_current

        def _on_pav_change(opt, _rid=row_id, _notes=notes):
            _notes['pav_confidence'] = 1.0
            self._save_triagem_notes_field(_rid, 'pavimento', opt, _notes)
            self._save_triagem_notes_field(_rid, 'pav_confidence', 1.0, _notes)
            QTimer.singleShot(60, self._refresh_projetos_finalizados_panel)

        layout.addWidget(lbl_badge)
        layout.addWidget(lbl_file, 1)

        # [Categoria] cat_conf%
        self._make_chip_with_conf(
            layout, cat_short, cat_color, cat_options_labels, _on_cat_change,
            82, cat_conf, 'cat_confidence', row_id, notes, None
        )

        # [Classe ER] cls_conf%  (apenas para Eng.Reversa)
        if show_er_class:
            er_class_current = notes.get('er_class') or inferred['er_class']
            er_class_display  = self._ER_SHORT_TO_FULL.get(er_class_current, er_class_current)
            er_class_color    = self._ER_CLASS_COLORS.get(er_class_display, Contextual.SLATE)

            def _on_class_change(opt, _rid=row_id, _notes=notes):
                _notes['class_confidence'] = 1.0
                self._save_triagem_notes_field(_rid, 'er_class', opt, _notes)
                self._save_triagem_notes_field(_rid, 'class_confidence', 1.0, _notes)
                QTimer.singleShot(60, self._refresh_projetos_finalizados_panel)

            self._make_chip_with_conf(
                layout, er_class_display, er_class_color,
                self._ER_CLASS_OPTIONS, _on_class_change,
                115, cls_conf, 'class_confidence', row_id, notes, None
            )

        # [Pavimento] pav_conf%
        pav_chip = self._make_combo_chip(pav_short, Colors.BG_CARD, self._PAV_OPTIONS, _on_pav_change, 88)
        pav_chip.setStyleSheet(
            f"QPushButton {{ color: {Colors.TEXT_PRIMARY}; background: {Colors.BG_CARD};"
            f" border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 3px; padding: 0 5px;"
            " font-size: 10px; font-weight: bold; }}"
            f"QPushButton:hover {{ border-color: {Colors.ACCENT_PRIMARY}; }}"
        )
        pav_conf_color = (
            Colors.ACCENT_SUCCESS_ALT if pav_conf >= 0.85 else
            Colors.ACCENT_WARNING     if pav_conf >= 0.60 else
            Colors.TEXT_DIM
        )
        lbl_pav_conf = QLabel(f"{pav_conf:.0%}" if pav_conf > 0 else "—%")
        lbl_pav_conf.setFixedWidth(28)
        lbl_pav_conf.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_pav_conf.setStyleSheet(
            f"color: {pav_conf_color}; font-size: 10px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        layout.addWidget(pav_chip)
        layout.addWidget(lbl_pav_conf)

        # Botão "Recortar" — só para Projetos Finalizados (show_er_class=True)
        if show_er_class:
            btn_recortar = QPushButton("✂ Recortar")
            btn_recortar.setToolTip("Abrir no Diagnostic Reverse Hub para processar eng. reversa")
            btn_recortar.setFixedWidth(90)
            btn_recortar.setStyleSheet(_resolve_css("""
                QPushButton {
                    background: rgba(90, 40, 180, 31); color: {Colors.ACCENT_PRIMARY};
                    border: 1px solid {Colors.ACCENT_PRIMARY}; border-radius: 4px;
                    font-size: 10px; font-weight: bold; padding: 2px 6px;
                }
                QPushButton:hover { background: rgba(90, 40, 180, 71); }
            """))
            _fp = row.get('file_path', '')
            _on = row.get('obra_name', self.current_work_name or '')
            btn_recortar.clicked.connect(
                lambda _, fp=_fp, on=_on: self._open_reverse_hub_with_projeto(on, fp)
            )
            layout.addWidget(btn_recortar)

        return card

    def _open_reverse_hub_with_projeto(self, obra_name: str, file_path: str):
        """Navega para Diagnostic Reverse Hub e sinaliza a obra/arquivo."""
        self.request_tab_switch.emit(2)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(150, lambda: self.request_open_reverse_hub.emit(obra_name, file_path))

    # ── Detalhamentos Especificos Panel ─────────────────────────────────────

    # Extensions allowed in classes 2 and 3 (no DWG)
    _DET_ALLOWED_EXT = {'.dxf', '.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'}

    def _load_detalhamentos_3classes(self) -> dict:
        """Carrega detalhamentos em 3 classes separadas.

        Returns dict:
          'recortados': list  — obra_recortes tipo=detalhe, status=approved
          'triagem':    list  — obra_triagem approved categoria Detalhe (sem DWG)
          'ingestao':   list  — project_documents categoria Detalhe (sem DWG)
        """
        import sqlite3 as _sq3
        DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
        work_name = self.current_work_name or ""
        if not work_name:
            return {'recortados': [], 'triagem': [], 'ingestao': []}

        result = {'recortados': [], 'triagem': [], 'ingestao': []}
        try:
            conn = _sq3.connect(str(DB))
            conn.row_factory = _sq3.Row

            # ── Classe 1: Detalhes Recortados (obra_recortes) ─────────────────
            cur = conn.execute(
                "SELECT pavimento_name as file_name, output_path as file_path,"
                " recorte_type, status, dxf_bruto_path"
                " FROM obra_recortes WHERE obra_name=? AND recorte_type='detalhe'"
                " AND status='approved'"
                " ORDER BY pavimento_name ASC",
                (work_name,)
            )
            result['recortados'] = [dict(r) for r in cur.fetchall()]

            # ── Classe 2: Documentos de Ingestão (project_documents) ──────────
            cur = conn.execute(
                "SELECT name as file_name, file_path, extension, category, phase, id"
                " FROM project_documents"
                " WHERE work_name=?"
                " AND (category LIKE '%Detalhe%' OR category LIKE '%Detalhamento%')"
                " ORDER BY name ASC",
                (work_name,)
            )
            for r in cur.fetchall():
                row = dict(r)
                ext = (row.get('extension') or '').lower()
                if not ext.startswith('.'):
                    ext = '.' + ext
                if ext in self._DET_ALLOWED_EXT:
                    row['_det_class'] = 'ingestao'
                    result['ingestao'].append(row)

            # ── Classe 3: Detalhes de Ingestão (obra_triagem) ─────────────────
            cur = conn.execute(
                "SELECT *, 'triagem' as recorte_type FROM obra_triagem"
                " WHERE obra_name=? AND status='approved'"
                " AND (suggested_category LIKE '%Detalhe%'"
                "      OR suggested_category LIKE '%Detalhamento%')"
                " ORDER BY file_name ASC",
                (work_name,)
            )
            for r in cur.fetchall():
                row = dict(r)
                fp = row.get('file_path') or row.get('file_name', '')
                ext = Path(fp).suffix.lower() if fp else ''
                if ext in self._DET_ALLOWED_EXT:
                    row['_det_class'] = 'triagem'
                    result['triagem'].append(row)

            conn.close()
        except Exception:
            pass
        return result

    def _load_detalhamentos_approved(self) -> list:
        """Compatibilidade — retorna lista plana (usado por código legado)."""
        d = self._load_detalhamentos_3classes()
        return d['recortados'] + d['triagem'] + d['ingestao']

    def _build_detalhamentos_especificos_panel(self, layout):
        """Painel colapsavel de Detalhamentos Especificos."""
        outer = QFrame()
        outer.setObjectName("DetalhamentosPanel")
        outer.setStyleSheet(_resolve_css("""
            QFrame#DetalhamentosPanel {
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.ACCENT_WARNING};
                border-radius: 8px;
            }
        """))
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(12, 10, 12, 10)
        outer_layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        self._lbl_detalhamentos_summary = QLabel("Detalhamentos Especificos")
        self._lbl_detalhamentos_summary.setStyleSheet(_resolve_css(
            "color: {Colors.ACCENT_WARNING}; font-size: 12px; font-weight: bold;"
            " background: transparent; border: none;"
        ))

        btn_open_hub_det = QPushButton("▶ Abrir Diagnostic Hub")
        btn_open_hub_det.setToolTip("Abrir Diagnostic Hub para processar todos os detalhamentos")
        btn_open_hub_det.setStyleSheet(_resolve_css("""
            QPushButton {
                background: rgba(230, 180, 0, 38); color: {Colors.ACCENT_WARNING};
                border: 1px solid {Colors.ACCENT_WARNING}; border-radius: 4px;
                padding: 3px 12px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(230, 180, 0, 71); }
        """))

        btn_reload_det = QPushButton("↻")
        btn_reload_det.setToolTip("Recarregar lista de detalhamentos")
        btn_reload_det.setFixedWidth(28)
        btn_reload_det.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px;
                padding: 3px; font-size: 13px;
            }
            QPushButton:hover { color: {Colors.TEXT_PRIMARY}; }
        """))

        self._btn_detalhamentos_toggle = QPushButton("▲")
        self._btn_detalhamentos_toggle.setFixedWidth(28)
        self._btn_detalhamentos_toggle.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {Text.SECONDARY}; border: none; font-size: 11px; }}"
        )

        header.addWidget(self._lbl_detalhamentos_summary)
        header.addStretch()
        header.addWidget(btn_open_hub_det)
        header.addWidget(btn_reload_det)
        header.addWidget(self._btn_detalhamentos_toggle)
        outer_layout.addLayout(header)

        # Content colapsavel
        self._detalhamentos_content_widget = QWidget()
        det_content_layout = QVBoxLayout(self._detalhamentos_content_widget)
        det_content_layout.setContentsMargins(0, 4, 0, 0)
        det_content_layout.setSpacing(0)

        det_scroll = QScrollArea()
        det_scroll.setMaximumHeight(480)
        det_scroll.setMinimumHeight(160)
        det_scroll.setWidgetResizable(True)
        det_scroll.setStyleSheet(_resolve_css("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { border: none; background: {Colors.BG_DEEP}; width: 6px; margin: 0; }
            QScrollBar::handle:vertical { background: {Colors.BG_CARD}; min-height: 16px; border-radius: 3px; }
        """))

        self._detalhamentos_list_container = QWidget()
        self._detalhamentos_list_container.setStyleSheet("background: transparent;")
        self._detalhamentos_list_layout = QVBoxLayout(self._detalhamentos_list_container)
        self._detalhamentos_list_layout.setSpacing(4)
        self._detalhamentos_list_layout.setContentsMargins(0, 0, 0, 0)

        det_scroll.setWidget(self._detalhamentos_list_container)
        det_content_layout.addWidget(det_scroll)
        outer_layout.addWidget(self._detalhamentos_content_widget)

        layout.addWidget(outer)

        def _toggle_det():
            vis = not self._detalhamentos_content_widget.isVisible()
            self._detalhamentos_content_widget.setVisible(vis)
            self._btn_detalhamentos_toggle.setText("▲" if vis else "▼")

        self._btn_detalhamentos_toggle.clicked.connect(_toggle_det)
        btn_reload_det.clicked.connect(self._refresh_detalhamentos_panel)
        btn_open_hub_det.clicked.connect(self._open_hub_for_all_detalhamentos)

        self._refresh_detalhamentos_panel()

    def _refresh_detalhamentos_panel(self):
        """Reconstroi a lista de detalhamentos em 3 classes."""
        if not hasattr(self, '_detalhamentos_list_layout'):
            return
        while self._detalhamentos_list_layout.count():
            item = self._detalhamentos_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        classes = self._load_detalhamentos_3classes()
        recortados = classes['recortados']
        triagem    = classes['triagem']
        ingestao   = classes['ingestao']
        total      = len(recortados) + len(triagem) + len(ingestao)

        if hasattr(self, '_lbl_detalhamentos_summary'):
            if total == 0:
                self._lbl_detalhamentos_summary.setText("Detalhamentos Especificos — nenhum")
            else:
                self._lbl_detalhamentos_summary.setText(
                    f"Detalhamentos Especificos — {total} itens"
                )

        if total == 0:
            lbl = QLabel("Nenhum detalhamento disponivel.")
            lbl.setWordWrap(True)
            lbl.setStyleSheet(_resolve_css(
                "color: {Colors.TEXT_DIM}; font-size: 11px; padding: 10px;"
                " background: transparent; border: none;"
            ))
            self._detalhamentos_list_layout.addWidget(lbl)
            self._detalhamentos_list_layout.addStretch()
            return

        # Sub-section helper
        def _add_section(title: str, color: str, rows: list, badge: str):
            # Section header
            lbl_sec = QLabel(f"  {title}  ({len(rows)})")
            lbl_sec.setStyleSheet(
                f"color: {color}; font-size: 10px; font-weight: bold;"
                " background: transparent; border: none; padding: 4px 0 2px 0;"
            )
            self._detalhamentos_list_layout.addWidget(lbl_sec)

            if not rows:
                lbl_empty = QLabel("   Nenhum item.")
                lbl_empty.setStyleSheet(_resolve_css(
                    "color: {Colors.TEXT_DIM}; font-size: 10px;"
                    " background: transparent; border: none; padding: 2px 0;"
                ))
                self._detalhamentos_list_layout.addWidget(lbl_empty)
            else:
                for row in rows:
                    card = self._make_approved_item_card_detalhe(row, badge=badge)
                    self._detalhamentos_list_layout.addWidget(card)

        _add_section(
            "Detalhes Recortados", Contextual.GOLD,
            recortados, "✂"
        )
        _add_section(
            "Documentos de Ingestão", Accent.INTERACTIVE,
            ingestao, "📄"
        )
        _add_section(
            "Detalhes de Ingestão (DXF completos)", Semantic.SUCCESS,
            triagem, "📐"
        )

        self._detalhamentos_list_layout.addStretch()

    def _make_approved_item_card_detalhe(self, row: dict, badge: str = "✅") -> QWidget:
        """Card compacto para um item de detalhamento."""
        card = QFrame()
        card.setStyleSheet(_resolve_css("""
            QFrame {
                background: {Colors.BG_DEEP};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 5px;
            }
            QFrame:hover { border-color: {Colors.ACCENT_WARNING}; }
        """))
        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(6)

        # Badge
        lbl_badge = QLabel(badge)
        lbl_badge.setFixedWidth(18)
        lbl_badge.setStyleSheet("background: transparent; border: none; font-size: 11px;")

        # Filename
        fname = row.get('file_name', row.get('name', ''))
        fpath = row.get('file_path', row.get('output_path', fname))
        lbl_file = QLabel(fname)
        lbl_file.setToolTip(fpath)
        lbl_file.setStyleSheet(_resolve_css(
            "color: {Colors.TEXT_PRIMARY}; font-size: 11px; background: transparent; border: none;"
        ))

        # Extension badge (small)
        ext = Path(fpath).suffix.upper().lstrip('.') if fpath else ''
        if ext:
            lbl_ext = QLabel(ext)
            lbl_ext.setFixedWidth(32)
            lbl_ext.setAlignment(Qt.AlignCenter)
            lbl_ext.setStyleSheet(
                f"background: rgba(120, 120, 120, 46); color: {Text.SECONDARY};"
                " font-size: 9px; border-radius: 3px; border: none; padding: 1px 2px;"
            )
        else:
            lbl_ext = None

        # Open button
        btn_open = QPushButton("👁 Abrir")
        btn_open.setFixedHeight(22)
        btn_open.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 3px;
                padding: 1px 8px; font-size: 10px;
            }
            QPushButton:hover { color: {Colors.TEXT_PRIMARY}; border-color: {Colors.ACCENT_WARNING}; }
        """))

        def _open_file(checked=False, fp=fpath):
            if fp and Path(fp).exists():
                import subprocess, os
                os.startfile(fp) if hasattr(os, 'startfile') else subprocess.Popen(['xdg-open', fp])
            else:
                QMessageBox.warning(self, "Arquivo", f"Arquivo não encontrado:\n{fp}")

        btn_open.clicked.connect(_open_file)

        layout.addWidget(lbl_badge)
        layout.addWidget(lbl_file, 1)
        if lbl_ext:
            layout.addWidget(lbl_ext)
        layout.addWidget(btn_open)
        return card

    def _open_hub_for_all_detalhamentos(self):
        """Navega para Diagnostic Hub passando todos os detalhamentos das 3 classes."""
        classes = self._load_detalhamentos_3classes()
        all_paths = []
        for row in classes['recortados']:
            fp = row.get('file_path') or row.get('output_path', '')
            if fp and Path(fp).exists():
                all_paths.append(fp)
        for row in classes['ingestao'] + classes['triagem']:
            fp = row.get('file_path', '')
            if fp and Path(fp).exists():
                all_paths.append(fp)

        if not all_paths:
            QMessageBox.information(self, "Detalhamentos",
                "Nenhum arquivo de detalhamento encontrado no disco.")
            return

        # Navega para aba Diagnostic Hub
        self.request_tab_switch.emit(1)

        # Emite sinal para hub carregar a lista de detalhamentos
        from PySide6.QtCore import QTimer
        def _emit():
            if hasattr(self, 'request_load_file'):
                self.request_load_file.emit(all_paths[0])
        QTimer.singleShot(300, _emit)

    def _on_ingest_all_clicked(self):
        """Botão unificado: Fase1→DB + RAG + Triagem em sequência."""
        work_name = self.current_work_name or (
            self.list_works.currentItem().data(Qt.UserRole)
            if self.list_works.currentItem() else ""
        )
        if not work_name:
            QMessageBox.warning(self, "Ingestão", "Selecione uma obra antes de processar.")
            return
        if hasattr(self, '_btn_ingest_all'):
            self._btn_ingest_all.setEnabled(False)
            self._btn_ingest_all.setText("⏳ Indexando DB...")
        # Fase 1: indexar DB
        self._index_phase1_all(work_name)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, self._refresh_index_badge)
        # Fase 2: RAG (após badge refresh)
        def _start_rag():
            if hasattr(self, '_btn_ingest_all'):
                self._btn_ingest_all.setText("⏳ Gerando RAG Local...")
            self._on_rag_pipeline_clicked()
        QTimer.singleShot(3500, _start_rag)

    def _on_index_clicked(self):
        """Handler legado do botão Indexar (mantido para compatibilidade)."""
        work_name = self.current_work_name or (
            self.list_works.currentItem().data(Qt.UserRole)
            if self.list_works.currentItem() else ""
        )
        self._index_phase1_all(work_name)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, self._refresh_index_badge)

    def _index_phase1_all(self, work_name: str):
        """Registra arquivos físicos da Fase 1 da obra que ainda não estão no DB."""
        try:
            import sys, subprocess
            indexer = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/src/utils/auto_indexer.py")
            if indexer.exists():
                cmd = [sys.executable, str(indexer)]
                if work_name:
                    cmd.append(work_name)  # filtra pela obra atual
                subprocess.Popen(cmd)  # sem cwd — auto_indexer usa paths absolutos
                label = f"obra '{work_name}'" if work_name else "todas as obras"
                QMessageBox.information(
                    self, "Indexar",
                    f"Indexação iniciada para {label}.\n"
                    f"Apenas arquivos faltantes serão adicionados.\n"
                    f"O badge atualizará em ~3 segundos."
                )
            else:
                QMessageBox.warning(self, "Indexar", f"auto_indexer.py não encontrado:\n{indexer}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao indexar: {e}")

    def _classify_document(self, doc):
        """Classifica um documento em fase e classe baseado em nome, extensão ou valores persistidos."""
        # PRIORIDADE: Usar fase e categoria salvas no banco se existirem
        saved_phase = doc.get('phase')
        saved_cat = doc.get('category')
        if saved_phase and saved_cat:
            # "Detalhamentos Específicos" são documentos de ingestão (Fase 1) → Detalhes Estruturais
            # Mesmo que salvos com phase=2, devem aparecer na Fase 1 de exibição
            if 'detalhamento' in saved_cat.lower():
                return (1, "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)")
            # Normalize legacy/variant category names to canonical PHASE_CLASSES values
            canonical = self._CATEGORY_ALIASES.get(saved_cat.lower().strip())
            if canonical:
                saved_cat = canonical
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
            return (1, "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)")
        if ext == '.dxf' and ('bruto' in name or 'estrutural' in name):
            return (1, "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)")
        # Nova classe: Projetos Finalizados para Engenharia Reversa
        if ('finalizado' in name or 'reversa' in name or 'completo' in name or 'pronto' in name):
            return (1, "Projetos Finalizados para Engenharia Reversa")
        
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
            return (1, "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)")
            
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
        if dialog.exec():
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
                    
                    # Extrair versão se for DWG/DXF
                    file_version = None
                    if ext.lower() in ['.dwg', '.dxf']:
                        file_version = get_cad_version_info(target_path_str)
                    
                    if self.current_project_id:
                        # Salva no DB vinculado ao Projeto
                        self.db.save_document(
                            project_id=self.current_project_id, 
                            name=display_name, 
                            file_path=target_path_str, 
                            extension=ext,
                            phase=phase_num,
                            category=class_name,
                            file_version=file_version
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
                            category=class_name,
                            file_version=file_version
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


    def refresh_documents(self):
        """Método de compatibilidade para atualizar visualizações."""
        self._refresh_phase_tabs()

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

    # ── Lazy tab rendering ────────────────────────────────────────────────────────

    def _load_classified_docs(self) -> dict:
        """Carrega e classifica documentos da obra/projeto atual. Sem tocar em widgets."""
        docs = []
        work_name = self.current_work_name
        if not work_name:
            item = self.list_works.currentItem()
            if item:
                work_name = item.data(Qt.UserRole)

        try:
            if self.current_project_id:
                p_data = self.db.get_project_by_id(self.current_project_id)
                if p_data:
                    docs = self.db.get_project_documents(self.current_project_id)
                    if p_data.get('dxf_path'):
                        dxf_name = os.path.basename(p_data['dxf_path'])
                        if not any(d.get('name') == dxf_name for d in docs):
                            docs.append({
                                'id': 'main_dxf',
                                'name': dxf_name + " (Principal)",
                                'file_path': p_data['dxf_path'],
                                'extension': '.dxf',
                                'is_main': True,
                                'file_version': p_data.get('file_version'),
                            })

            if work_name:
                existing_ids = {d.get('id') for d in docs}
                for wd in self.db.get_work_documents(work_name):
                    if wd.get('id') not in existing_ids:
                        docs.append(wd)
                existing_paths = {d.get('file_path', '') for d in docs}
                docs.extend(self._scan_phase1_filesystem(work_name, existing_paths))

        except Exception as e:
            logging.error(f"[_load_classified_docs] {e}")

        classified: dict = {}
        for doc in docs:
            phase_num, class_name = self._classify_document(doc)
            classified.setdefault((phase_num, class_name), []).append(doc)
        return classified

    def _render_single_phase(self, phase_num: int, classified_docs: dict):
        """Reconstrói os widgets de UM tab de fase usando classified_docs já calculado."""
        phase_tab = self.phase_tab_widgets.get(phase_num)
        if not phase_tab:
            return
        container = phase_tab.widget()
        if not container:
            return
        layout = container.layout()
        if not layout:
            return

        try:
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if not item:
                    continue
                widget = item.widget()
                if not widget:
                    continue

                class_name = widget.property("class_name")
                if class_name:
                    docs_container = widget.property("docs_container")
                    if docs_container:
                        docs_layout = docs_container.layout()
                        if docs_layout:
                            # Limpar widgets existentes (preservar containers especiais)
                            for j in reversed(range(docs_layout.count())):
                                child = docs_layout.itemAt(j)
                                w = child.widget()
                                if w:
                                    is_special = (
                                        (hasattr(self, 'scroll_area') and w == self.scroll_area) or
                                        (hasattr(self, 'phase3_pavement_selector') and w == self.phase3_pavement_selector) or
                                        (hasattr(self, 'phase4_pavement_selector') and w == self.phase4_pavement_selector) or
                                        (hasattr(self, 'phase5_pavement_selector') and w == self.phase5_pavement_selector)
                                    )
                                    if not is_special:
                                        docs_layout.takeAt(j)
                                        w.deleteLater()
                                else:
                                    docs_layout.takeAt(j)

                            key = (phase_num, class_name)
                            class_docs = classified_docs.get(key, [])

                            # Badge
                            count_badge = widget.property("count_badge")
                            if count_badge:
                                dwg_n = sum(1 for d in class_docs if d.get('extension', '').lower() == '.dwg')
                                dxf_n = sum(1 for d in class_docs if d.get('extension', '').lower() == '.dxf')
                                total_n = len(class_docs)
                                if dwg_n > 0:
                                    if dxf_n >= dwg_n:
                                        badge_text, badge_color = f"{dwg_n} DWG  |  {dxf_n} DXF  OK", Colors.ACCENT_SUCCESS_ALT
                                    elif dxf_n > 0:
                                        badge_text, badge_color = f"{dwg_n} DWG  |  {dxf_n}/{dwg_n} DXF", Colors.ACCENT_WARNING
                                    else:
                                        badge_text, badge_color = f"{dwg_n} DWG  |  0 DXF", Colors.ACCENT_DANGER
                                elif dxf_n > 0:
                                    badge_text, badge_color = f"{dxf_n} DXF", Colors.ACCENT_SUCCESS_ALT
                                elif total_n > 0:
                                    badge_text, badge_color = f"{total_n} docs", Colors.TEXT_SECONDARY
                                else:
                                    badge_text, badge_color = "vazio", Colors.TEXT_DIM
                                count_badge.setText(badge_text)
                                count_badge.setStyleSheet(
                                    f"color: {badge_color}; font-size: 11px; font-weight: bold;"
                                    " padding: 0 8px; background: transparent; border: none;"
                                )

                            # Agrupar DWG↔DXF e renderizar
                            dxfs_map: dict = {}
                            others = []
                            for d in class_docs:
                                name = d.get('name', '')
                                ext = d.get('extension', '').lower()
                                match = re.search(r"^(.*?)\s*\(.*?\)$", name)
                                if ext == '.dxf' and match:
                                    base = match.group(1).strip()
                                    dxfs_map.setdefault(base, []).append(d)
                                else:
                                    others.append(d)

                            final_list = []
                            handled_ids: set = set()
                            for d in others:
                                ext = d.get('extension', '').lower()
                                name = d.get('name', '')
                                children = []
                                if ext == '.dwg' and name in dxfs_map:
                                    children = dxfs_map[name]
                                    for c in children:
                                        handled_ids.add(c.get('id'))
                                final_list.append((d, children[0] if children else None))
                            for base, ds in dxfs_map.items():
                                for d in ds:
                                    if d.get('id') not in handled_ids:
                                        final_list.append((d, None))

                            _skip_simple = (phase_num == 2 and class_name == "Estruturais Pavimentos Limpos")
                            if not _skip_simple:
                                for parent_doc, child_doc in final_list:
                                    docs_layout.addWidget(self._create_document_item_widget(parent_doc, child_doc))

                            docs_layout.addStretch()

                    # DB trees (fase 3/4/5)
                    tree = widget.property("db_tree")
                    if tree:
                        if phase_num == 3:
                            self._refresh_phase3_data(class_name, tree)
                        elif phase_num == 4:
                            self._refresh_phase4_data(class_name, tree)
                        elif phase_num == 5:
                            self._refresh_phase5_data(class_name, tree)
                            self._update_script_progress()

        except Exception as e:
            import traceback
            logging.error(f"[_render_single_phase] phase={phase_num} {e}\n{traceback.format_exc()}")

    def _on_phase_tab_switched(self, idx: int):
        """Renderiza o tab recém-selecionado se estiver dirty.
        Layout: idx 0→fase1, 1→fase2, 2→pré-ficha, 3→fase3, …, 8→fase8
        """
        if idx == 2:  # 2.1 Pré-ficha Obra
            self._refresh_ficha_obra()
            return
        # idx < 2  →  phase = idx + 1  (0→1, 1→2)
        # idx > 2  →  phase = idx      (3→3, 4→4, …, 8→8)
        phase_num = idx + 1 if idx < 2 else idx
        if phase_num in self._dirty_phases:
            self._render_single_phase(phase_num, self._classified_docs_cache)
            self._dirty_phases.discard(phase_num)

    def _refresh_phase_tabs(self):
        """Carrega documentos e renderiza apenas o tab visível. Os demais são lazy.
        Layout: idx 0→fase1, 1→fase2, 2→pré-ficha, 3→fase3, …, 8→fase8
        """
        try:
            self._classified_docs_cache = self._load_classified_docs()
            cur_idx = self.phase_tabs.currentIndex()
            if cur_idx == 2:  # pré-ficha — não é uma fase numérica
                self._refresh_ficha_obra()
                self._dirty_phases = set(range(1, 9))
            else:
                visible = cur_idx + 1 if cur_idx < 2 else cur_idx
                self._render_single_phase(visible, self._classified_docs_cache)
                # Marcar todos os outros como dirty — serão renderizados ao clicar
                self._dirty_phases = set(range(1, 9)) - {visible}
        except Exception as e:
            import traceback
            logging.error(f"Erro ao atualizar abas de fases: {e}\n{traceback.format_exc()}")

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
                        tree_item.setForeground(col, QColor(Colors.ACCENT_MINT))
                        tree_item.setToolTip(col, f"Gerado em: {s_info.get('generated_at')}\nCaminho: {s_info.get('script_path')}")
                    else:
                        tree_item.setText(col, "⏳ Pend")
                        tree_item.setForeground(col, QColor(Colors.ACCENT_WARNING_ALT))
            else:
                s_info = generated_map.get(f"{item_type}_{item_db_id}")
                if s_info:
                    dt = s_info.get('generated_at', '')
                    if dt and ' ' in dt: dt = dt.split(' ')[0]
                    label_dt = f"{dt[8:10]}/{dt[5:7]}" if len(dt) >= 10 else "Sim"
                    tree_item.setText(2, f"✅ GERADO ({label_dt})")
                    tree_item.setForeground(2, QColor(Colors.ACCENT_MINT))
                else:
                    tree_item.setText(2, "⏳ PENDENTE")
                    tree_item.setForeground(2, QColor(Colors.ACCENT_WARNING_ALT))

            btn_action = QPushButton("📁")
            btn_action.setFixedSize(30, 22)
            btn_action.setCursor(Qt.PointingHandCursor)
            btn_action.setStyleSheet(f"background: {Colors.BG_CARD}; color: {Colors.TEXT_BRIGHT}; border-radius: 3px;")
            
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
            main_container.setStyleSheet(_resolve_css("""
                QFrame#MainContainer {
                    background: {Colors.BG_SURFACE};
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: 4px;
                }
                QFrame#Row {
                    background: transparent;
                    border: none;
                }
                QFrame#Row:hover {
                    background: {Colors.BORDER_SUBTLE};
                }
                QFrame#ChildRow {
                    background: {Colors.BG_DEEP};
                    border-top: 1px solid {Colors.BORDER_DEFAULT};
                }
            """))
            main_container.setObjectName("MainContainer")
            container_layout = QVBoxLayout(main_container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
        else:
            main_container.setStyleSheet(_resolve_css("""
                QFrame {
                    background: {Colors.BG_DEEP};
                    border: 1px solid {Colors.BORDER_DEFAULT};
                    border-radius: 5px;
                }
                QFrame:hover {
                    border-color: {Colors.ACCENT_PRIMARY};
                }
            """))
            container_layout = QVBoxLayout(main_container)
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
            row_layout.setContentsMargins(8, 4, 8, 4)
            row_layout.setSpacing(6)

            # Indentação para filho
            if is_child:
                icon_link = QLabel("↳")
                icon_link.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 12px; font-weight: bold; margin-right: 4px;")
                row_layout.addWidget(icon_link)

            # Nome do documento
            doc_name = item_doc.get('name', 'Sem nome')
            name_label = QLabel(doc_name)
            name_label.setToolTip(doc_name)
            name_style = f"font-size: 11px; color: {Colors.TEXT_PRIMARY}; background: transparent; border: none;"
            if is_child: name_style += f" font-style: italic; color: {Colors.TEXT_SECONDARY};"
            name_label.setStyleSheet(name_style)
            row_layout.addWidget(name_label, 1)

            # Formato (Badge)
            ext = item_doc.get('extension', '')
            format_label = QLabel(ext.upper() if ext else "N/A")
            format_label.setFixedWidth(38)
            format_label.setAlignment(Qt.AlignCenter)
            format_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9px; font-weight: bold; padding: 1px 3px; background: {Colors.BG_CARD}; border-radius: 3px; border: 1px solid {Colors.BORDER_DEFAULT};")
            row_layout.addWidget(format_label)
            
            # Versão (Alinhada como coluna)
            version_val = item_doc.get('file_version')
            is_cad = ext.lower() in ['.dwg', '.dxf']
            
            if is_cad:
                version_label = QLabel()
                if not version_val:
                    version_text = "⚠️ Pendente Scan"
                    version_style = f"color: {Colors.ACCENT_WARNING}; background: rgba(255, 152, 0, 31); border: 1px solid {Colors.ACCENT_WARNING};"
                elif version_val == "Desconhecido":
                    version_text = "❓ Desconhecido"
                    version_style = f"color: {Colors.TEXT_DIM}; background: transparent; border: 1px solid {Colors.BORDER_DEFAULT};"
                else:
                    version_text = f"⚙️ {version_val}"
                    version_style = f"color: {Colors.ACCENT_SUCCESS_ALT}; background: rgba(0, 204, 102, 26); border: 1px solid {Colors.ACCENT_SUCCESS_ALT};"
                
                version_label.setText(version_text)
                version_label.setStyleSheet(f"""
                    font-size: 9px;
                    font-weight: bold;
                    padding: 1px 6px;
                    border-radius: 3px;
                    {version_style}
                """)
                version_label.setFixedWidth(120)
                version_label.setAlignment(Qt.AlignCenter)
                row_layout.addWidget(version_label)
            else:
                row_layout.addSpacing(120)
            
            row_layout.addStretch()
            
            # Botão Abrir
            btn_open = QPushButton("👁 Abrir")
            btn_open.setFixedHeight(22)
            btn_open.setCursor(Qt.PointingHandCursor)
            btn_open.setToolTip("Abrir documento")
            btn_open.setStyleSheet(_resolve_css("""
                QPushButton {
                    background: rgba(26, 50, 75, 1); color: {Colors.ACCENT_PRIMARY}; border: 1px solid {Colors.ACCENT_PRIMARY};
                    border-radius: 3px; padding: 1px 8px; font-size: 10px; font-weight: bold;
                }
                QPushButton:hover { background: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DEEP}; }
            """))
            fpath = item_doc.get('file_path')
            if fpath:
                import os
                btn_open.clicked.connect(lambda: os.startfile(fpath) if os.path.exists(fpath) else QMessageBox.warning(self, "Erro", "Arquivo não encontrado."))
            row_layout.addWidget(btn_open)

            # Botões de conversão (para DWG Pai)
            if not is_child and ext.lower() == '.dwg':
                 btn_quick_convert = QPushButton("⚡ DXF 2018")
                 btn_quick_convert.setFixedHeight(22)
                 btn_quick_convert.setCursor(Qt.PointingHandCursor)
                 btn_quick_convert.setToolTip("Conversão rápida para DXF 2018 ASCII")
                 btn_quick_convert.setStyleSheet(_resolve_css("""
                    QPushButton {
                        background: rgba(26, 77, 46, 1); color: {Colors.ACCENT_SUCCESS_ALT}; border: 1px solid {Colors.ACCENT_SUCCESS_ALT};
                        border-radius: 3px; padding: 1px 8px; font-size: 10px; font-weight: bold;
                    }
                    QPushButton:hover { background: {Colors.ACCENT_SUCCESS_ALT}; color: {Colors.BG_DEEP}; }
                 """))
                 btn_quick_convert.clicked.connect(lambda checked=False, d=item_doc: self._convert_to_specific_version(d, "R2018", "dxf", False))
                 row_layout.addWidget(btn_quick_convert)

                 btn_convert = QToolButton()
                 btn_convert.setText("Opções ▾")
                 btn_convert.setToolButtonStyle(Qt.ToolButtonTextOnly)
                 btn_convert.setPopupMode(QToolButton.InstantPopup)
                 btn_convert.setCursor(Qt.PointingHandCursor)
                 btn_convert.setStyleSheet(_resolve_css("""
                    QToolButton {
                        background: rgba(26, 50, 75, 1); color: {Colors.ACCENT_PRIMARY}; border: 1px solid {Colors.ACCENT_PRIMARY};
                        border-radius: 3px; padding: 1px 8px; font-size: 10px; font-weight: bold;
                    }
                    QToolButton::menu-indicator { width: 0; }
                    QToolButton:hover { background: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DEEP}; }
                 """))
                 
                 menu = QMenu(self)
                 menu.setStyleSheet(_resolve_css("""
                    QMenu { background-color: {Colors.BG_SURFACE}; color: {Colors.TEXT_PRIMARY}; border: 1px solid {Colors.BORDER_INPUT}; font-size: 11px; }
                    QMenu::item { padding: 8px 30px; }
                    QMenu::item:selected { background-color: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DEEP}; }
                    QMenu::separator { height: 1px; background: {Colors.BORDER_INPUT}; margin: 5px 0; }
                    QMenu::section { background-color: {Colors.BG_DEEP}; color: {Colors.ACCENT_PRIMARY}; padding: 6px; font-weight: bold; border-bottom: 1px solid {Colors.BORDER_DEFAULT}; }
                 """))
                 
                 # Opção especial: Converter para TODOS os formatos
                 menu.addSection("⚡ CONVERSÃO EM LOTE")
                 act_all = menu.addAction("🚀 Converter para TODOS os formatos")
                 act_all.triggered.connect(lambda checked=False, d=item_doc: self._convert_to_all_formats(d))
                 
                 menu.addSeparator()
                 
                 # DXF Versions (ASCII and Binary)
                 dxf_versions = [
                     ("R12 (AC1009) - Legado", "R12"),
                     ("R2000 (AC1015)", "R2000"),
                     ("R2004 (AC1018)", "R2004"),
                     ("R2007 (AC1021)", "R2007"),
                     ("R2010 (AC1024)", "R2010"),
                     ("R2013 (AC1027)", "R2013"),
                     ("R2018 (AC1032) - Atual", "R2018")
                 ]

                 menu.addSection("📐 CONVERTER PARA DXF")
                 for label, ver in dxf_versions:
                     # ASCII
                     act_ascii = menu.addAction(f"DXF {label} (ASCII)")
                     act_ascii.triggered.connect(lambda checked=False, v=ver, b=False, d=item_doc: self._convert_to_specific_version(d, v, "dxf", b))
                     
                     # Binary
                     act_bin = menu.addAction(f"DXF {label} (Binário)")
                     act_bin.triggered.connect(lambda checked=False, v=ver, b=True, d=item_doc: self._convert_to_specific_version(d, v, "dxf", b))
                     if ver != "R2018": menu.addSeparator()

                 menu.addSeparator()
                 menu.addSection("📦 CONVERTER PARA DWG")
                 # DWG Versions
                 act_dwg2018 = menu.addAction("DWG v2018 (AutoCAD 2018-2024)")
                 act_dwg2018.triggered.connect(lambda checked=False, d=item_doc: self._convert_to_specific_version(d, "R2018", "dwg"))
                 
                 btn_convert.setMenu(menu)
                 row_layout.addWidget(btn_convert)

            # Botão excluir
            btn_delete = QPushButton("✕")
            btn_delete.setFixedSize(22, 22)
            btn_delete.setCursor(Qt.PointingHandCursor)
            btn_delete.setToolTip("Excluir documento")
            btn_delete.setStyleSheet(_resolve_css("""
                QPushButton {
                    background: rgba(58, 28, 28, 1); color: {Colors.ACCENT_DANGER}; border: 1px solid {Colors.ACCENT_DANGER};
                    border-radius: 3px; font-weight: bold; font-size: 10px;
                }
                QPushButton:hover { background: {Colors.ACCENT_DANGER}; color: {Colors.TEXT_BRIGHT}; }
            """))
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
        """Método legado redirecionando para a versão R2018 padrão."""
        self._convert_to_specific_version(doc, "R2018", "dxf")

    def _convert_all_dwg_in_class(self, phase_num, class_name):
        """Converte todos os arquivos DWG de uma classe para DXF 2018 ASCII."""
        from PySide6.QtCore import Qt
        
        # Buscar todos os documentos da classe
        docs = []
        
        work_name = self.current_work_name
        if not work_name:
            item = self.list_works.currentItem()
            if item:
                work_name = item.data(Qt.UserRole)
        
        # Obter documentos do projeto ou obra
        if self.current_project_id:
            all_docs = self.db.get_project_documents(self.current_project_id)
        elif work_name:
            all_docs = self.db.get_work_documents(work_name)
        else:
            QMessageBox.warning(self, "Erro", "Nenhum projeto ou obra selecionado.")
            return
        
        # Filtrar apenas DWGs da classe específica
        for doc in all_docs:
            doc_phase, doc_class = self._classify_document(doc)
            if doc_phase == phase_num and doc_class == class_name:
                if doc.get('extension', '').lower() == '.dwg':
                    docs.append(doc)
        
        if not docs:
            QMessageBox.information(
                self,
                "Nenhum DWG Encontrado",
                f"Não há arquivos DWG na classe '{class_name}'."
            )
            return
        
        # Confirmar conversão
        reply = QMessageBox.question(
            self,
            "Converter Todos DWG",
            f"Encontrados {len(docs)} arquivo(s) DWG na classe '{class_name}'.\n\n"
            f"Converter todos para DXF 2018 ASCII?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.setCursor(Qt.WaitCursor)
        
        success_count = 0
        fail_count = 0
        
        try:
            for doc in docs:
                try:
                    self._convert_to_specific_version(doc, "R2018", "dxf", is_binary=False, silent=True)
                    success_count += 1
                except Exception as e:
                    logging.error(f"Erro ao converter {doc.get('name')}: {e}")
                    fail_count += 1
            
            self.setCursor(Qt.ArrowCursor)
            
            # Atualizar interface
            self._refresh_phase_tabs()
            
            QMessageBox.information(
                self,
                "Conversão Concluída",
                f"✅ {success_count} arquivo(s) convertido(s) com sucesso!\n"
                f"❌ {fail_count} falha(s)."
            )
            
        except Exception as e:
            self.setCursor(Qt.ArrowCursor)
            logging.error(f"Erro na conversão em lote da classe: {e}")
            QMessageBox.critical(self, "Erro", f"Erro na conversão:\n{str(e)}")

    def _convert_to_all_formats(self, doc):
        """Converte um DWG para TODOS os formatos disponíveis."""
        from PySide6.QtCore import Qt
        
        reply = QMessageBox.question(
            self, 
            "Conversão em Lote", 
            "Isso irá gerar 14 arquivos DXF (7 versões x ASCII/Binário).\n\nDeseja continuar?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.setCursor(Qt.WaitCursor)
        
        # Lista de todas as versões
        versions = ["R12", "R2000", "R2004", "R2007", "R2010", "R2013", "R2018"]
        
        success_count = 0
        fail_count = 0
        
        try:
            for version in versions:
                # ASCII
                try:
                    self._convert_to_specific_version(doc, version, "dxf", is_binary=False, silent=True)
                    success_count += 1
                except Exception as e:
                    logging.error(f"Erro ao converter {version} ASCII: {e}")
                    fail_count += 1
                
                # Binary
                try:
                    self._convert_to_specific_version(doc, version, "dxf", is_binary=True, silent=True)
                    success_count += 1
                except Exception as e:
                    logging.error(f"Erro ao converter {version} Binário: {e}")
                    fail_count += 1
            
            self.setCursor(Qt.ArrowCursor)
            
            # Atualizar interface após todas as conversões
            self._refresh_phase_tabs()
            
            QMessageBox.information(
                self, 
                "Conversão Concluída", 
                f"✅ {success_count} arquivos convertidos com sucesso!\n❌ {fail_count} falharam."
            )
            
        except Exception as e:
            self.setCursor(Qt.ArrowCursor)
            logging.error(f"Erro na conversão em lote: {e}")
            QMessageBox.critical(self, "Erro", f"Erro na conversão em lote:\n{str(e)}")

    def _convert_to_specific_version(self, doc, version, target_format="dxf", is_binary=False, silent=False):
        """Converte um DWG para uma versão específica DXF usando conversores open source.
        
        Args:
            doc: Documento a ser convertido
            version: Versão alvo (R12, R2000, etc)
            target_format: Formato de saída (dxf ou dwg)
            is_binary: Se True, gera DXF binário (apenas para DXF)
            silent: Se True, não mostra mensagens de sucesso/erro (para conversão em lote)
        """
        dwg_path = doc.get('file_path')
        if not dwg_path or not os.path.exists(dwg_path):
            if not silent:
                QMessageBox.warning(self, "Erro", "Arquivo fonte não encontrado.")
            return

        # Caminho de saída
        dir_path = os.path.dirname(dwg_path)
        base_name = os.path.splitext(os.path.basename(dwg_path))[0]
        ext = ".dxf" if target_format == "dxf" else ".dwg"
        
        # Nome inclui versão, tipo E biblioteca para facilitar testes
        format_type = ""
        if target_format == "dxf":
            format_type = "_Binario" if is_binary else "_ASCII"
        
        # Incluir biblioteca no nome
        v_suffix = f"_{version}{format_type}_ODA"
        dxf_path = os.path.join(dir_path, f"{base_name}{v_suffix}{ext}")
        
        if os.path.exists(dxf_path):
            dxf_path = os.path.join(dir_path, f"{base_name}{v_suffix}_{uuid.uuid4().hex[:4]}{ext}")
        
        temp_dxf = None
        try:
            from PySide6.QtCore import Qt
            import ezdxf
            import tempfile
            import subprocess
            
            if not silent:
                self.setCursor(Qt.WaitCursor)
            logging.info(f"Iniciando conversão ODA [{version}{format_type}]: {dwg_path}")
            
            if target_format == "dwg":
                if not silent:
                    QMessageBox.warning(self, "Não Suportado", "Conversão para DWG não implementada.\nUse apenas DXF.")
                return
            
            # Mapeamento de versões AutoCAD para ODA
            oda_version_map = {
                "R12": "ACAD12",
                "R2000": "ACAD2000",
                "R2004": "ACAD2004",
                "R2007": "ACAD2007",
                "R2010": "ACAD2010",
                "R2013": "ACAD2013",
                "R2018": "ACAD2018",
            }
            
            oda_version = oda_version_map.get(version, "ACAD2018")
            
            # Criar diretório temporário para conversão
            temp_dir = tempfile.mkdtemp()
            temp_output_dir = os.path.join(temp_dir, "output")
            os.makedirs(temp_output_dir, exist_ok=True)
            
            # Copiar arquivo DWG para temp (ODA precisa disso)
            temp_input = os.path.join(temp_dir, os.path.basename(dwg_path))
            shutil.copy2(dwg_path, temp_input)
            
            # Tentar usar ODA File Converter (linha de comando)
            # Procurar ODA File Converter em locais comuns (incluindo subpastas de versão)
            oda_paths = []
            
            # Adicionar caminhos base
            base_paths = [
                r"C:\Program Files\ODA",
                r"C:\Program Files (x86)\ODA",
                r"C:\ODA",
                os.path.expanduser("~/ODA"),
            ]
            
            # Para cada caminho base, procurar subpastas
            for base_path in base_paths:
                if os.path.exists(base_path):
                    try:
                        # Procurar ODAFileConverter.exe em subpastas
                        for root, dirs, files in os.walk(base_path):
                            if "ODAFileConverter.exe" in files:
                                oda_paths.append(os.path.join(root, "ODAFileConverter.exe"))
                    except:
                        pass
            
            oda_exe = None
            for path in oda_paths:
                if os.path.exists(path):
                    oda_exe = path
                    logging.info(f"🔍 ODA encontrado em: {oda_exe}")
                    break
            
            if not oda_exe:
                # Tentar encontrar no PATH
                try:
                    result = subprocess.run(["where", "ODAFileConverter.exe"], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        oda_exe = result.stdout.strip().split('\n')[0]
                except:
                    pass
            
            if oda_exe and os.path.exists(oda_exe):
                try:
                    # Executar ODA File Converter
                    # Sintaxe: ODAFileConverter.exe <input_folder> <output_folder> <output_version> <output_format> <recurse> <audit>
                    cmd = [
                        oda_exe,
                        temp_dir,           # Input folder
                        temp_output_dir,    # Output folder
                        oda_version,        # Output version (ACAD2018, etc)
                        "DXF",              # Output format
                        "0",                # Recurse (0=no)
                        "1"                 # Audit (1=yes)
                    ]
                    
                    logging.info(f"🔧 Executando ODA: {' '.join(cmd)}")
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=120,  # 2 minutos timeout
                        cwd=temp_dir
                    )
                    
                    if result.returncode == 0:
                        # Procurar arquivo DXF gerado
                        output_file = os.path.join(temp_output_dir, os.path.splitext(os.path.basename(dwg_path))[0] + ".dxf")
                        
                        if os.path.exists(output_file):
                            # Ajustar versão com ezdxf se necessário
                            try:
                                doc_dxf = ezdxf.readfile(output_file)
                                
                                # Verificar se precisa ajustar versão
                                acad_ver_map = {
                                    "R12": "AC1009",
                                    "R2000": "AC1015",
                                    "R2004": "AC1018",
                                    "R2007": "AC1021",
                                    "R2010": "AC1024",
                                    "R2013": "AC1027",
                                    "R2018": "AC1032",
                                }
                                target_acad_ver = acad_ver_map.get(version, "AC1032")
                                
                                if doc_dxf.dxfversion != target_acad_ver:
                                    # Converter para versão correta
                                    new_doc = ezdxf.new(target_acad_ver)
                                    
                                    # Copiar tudo
                                    for layer in doc_dxf.layers:
                                        try:
                                            new_doc.layers.new(layer.dxf.name, dxfattribs=layer.dxfattribs())
                                        except:
                                            pass
                                    
                                    # Copiar blocos
                                    for block in doc_dxf.blocks:
                                        if block.name not in new_doc.blocks:
                                            try:
                                                new_block = new_doc.blocks.new(block.name)
                                                for entity in block:
                                                    new_block.add_foreign_entity(entity)
                                            except:
                                                pass
                                    
                                    # Copiar modelspace
                                    msp_src = doc_dxf.modelspace()
                                    msp_tgt = new_doc.modelspace()
                                    for entity in msp_src:
                                        try:
                                            msp_tgt.add_foreign_entity(entity)
                                        except:
                                            pass
                                    
                                    new_doc.saveas(dxf_path)
                                else:
                                    shutil.copy2(output_file, dxf_path)
                                
                                logging.info(f"✅ Conversão ODA concluída: {version}{format_type}")
                                
                            except Exception as e_adjust:
                                # Se falhar ajuste, usar arquivo ODA direto
                                logging.warning(f"⚠️ Ajuste de versão falhou: {e_adjust}. Usando ODA direto.")
                                shutil.copy2(output_file, dxf_path)
                        else:
                            raise Exception(f"ODA não gerou arquivo de saída em {output_file}")
                    else:
                        raise Exception(f"ODA retornou erro: {result.stderr}")
                        
                except Exception as e_oda:
                    logging.error(f"❌ Erro ao usar ODA: {e_oda}")
                    if not silent:
                        QMessageBox.critical(
                            self,
                            "Erro na Conversão",
                            f"Erro ao usar ODA File Converter:\n\n{str(e_oda)}\n\n"
                            f"Verifique se o ODA File Converter está instalado corretamente."
                        )
                    return
                finally:
                    # Limpar diretório temporário
                    try:
                        shutil.rmtree(temp_dir)
                    except:
                        pass
            else:
                if not silent:
                    QMessageBox.critical(
                        self,
                        "ODA Não Encontrado",
                        "ODA File Converter não foi encontrado.\n\n"
                        "Baixe e instale de:\n"
                        "https://www.opendesign.com/guestfiles/oda_file_converter\n\n"
                        "Instale em: C:\\Program Files\\ODA\\ODAFileConverter\\"
                    )
                logging.error("❌ ODA File Converter não encontrado")
                return

            # Extrair versão do arquivo final
            real_version = get_cad_version_info(dxf_path)

            # Salvar no banco com nome correto incluindo biblioteca
            parent_category = doc.get('category', "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)")
            format_label = " Binário" if is_binary else " ASCII"
            save_name = f"{base_name} ({version}{format_label} - ODA)"
            
            if self.current_project_id:
                self.db.save_document(
                    project_id=self.current_project_id, 
                    name=save_name, 
                    file_path=dxf_path, 
                    extension=ext,
                    phase=1,
                    category=parent_category,
                    file_version=real_version
                )
            else:
                # Salva na Obra se não houver projeto
                curr_work = self.current_work_name or (self.list_works.currentItem().data(Qt.UserRole) if self.list_works.currentItem() else None)
                if curr_work:
                    self.db.save_work_document(
                        work_name=curr_work,
                        name=save_name,
                        file_path=dxf_path,
                        extension=ext,
                        storage_path=None,
                        phase=1,
                        category=parent_category,
                        file_version=real_version
                    )
            
            if not silent:
                self.setCursor(Qt.ArrowCursor)
                QMessageBox.information(
                    self, 
                    "Sucesso", 
                    f"✅ Arquivo convertido!\n\n"
                    f"Versão: {version}{format_label if target_format == 'dxf' else ''}\n"
                    f"Formato: {target_format.upper()}\n"
                    f"Versão detectada: {real_version}"
                )
                self._refresh_phase_tabs()
            
        except Exception as e:
            if not silent:
                self.setCursor(Qt.ArrowCursor)
                logging.error(f"❌ Erro na conversão: {e}", exc_info=True)
                QMessageBox.critical(self, "Erro na Conversão", f"Falha ao converter.\n\nDetalhes: {str(e)}")
                raise  # Re-raise apenas em modo não-silencioso
            else:
                # Em modo silencioso, apenas loga o erro sem interromper
                logging.error(f"❌ Erro na conversão {version}{format_type}: {e}")
        finally:
            # Limpar arquivo temporário
            if temp_dxf and os.path.exists(temp_dxf):
                try:
                    os.remove(temp_dxf)
                except:
                    pass

    def setup_community_tab(self):
        layout = QVBoxLayout(self.community_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.curadoria_rag_tabs = QTabWidget()
        self.curadoria_rag_tabs.setObjectName("CuradoriaRagTabs")
        self.curadoria_rag_tabs.setStyleSheet(_resolve_css("""
            QTabWidget::pane {
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                background: {Colors.BG_PANEL};
            }
            QTabBar::tab {
                background: {Colors.BG_DEEP};
                color: {Colors.TEXT_SECONDARY};
                padding: 7px 14px;
                border: none;
                border-right: 1px solid {Colors.BORDER_DEFAULT};
                min-width: 96px;
            }
            QTabBar::tab:selected {
                background: {Colors.BG_SECONDARY};
                color: {Colors.ACCENT_PRIMARY};
                border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
            }
        """))

        self._curadoria_metric_labels = {}
        self._curadoria_tables = {}

        self.curadoria_rag_tabs.setObjectName("CuradoriaRagTabs")
        self.curadoria_rag_tabs.addTab(self._build_curadoria_map_tab(), "Mapa RAG")
        self.curadoria_rag_tabs.addTab(self._build_curadoria_mcp_evidence_tab(), "Evidencias MCP")
        self.curadoria_rag_tabs.addTab(self._build_curadoria_encyclopedia_tab(), "Enciclopedia")
        self.curadoria_rag_tabs.addTab(self._build_curadoria_corpus_tab(), "Corpus")
        self.curadoria_rag_tabs.addTab(self._build_curadoria_pending_tab(), "Pendencias")
        self.curadoria_rag_tabs.addTab(self._build_curadoria_learning_tab(), "Aprendizado")
        self.curadoria_rag_tabs.addTab(self._build_curadoria_training_pipelines_tab(), "Pipelines de Treino")
        self.curadoria_rag_tabs.addTab(self._build_curadoria_vector_tab(), "Memoria Vetorial")
        self.curadoria_rag_tabs.addTab(self._build_curadoria_db_tab(), "Banco de Dados")

        self.admin_dashboard = AdminDashboard(self.db, self.memory)
        self.curadoria_rag_tabs.addTab(self.admin_dashboard, "Admin Legado")

        layout.addWidget(self.curadoria_rag_tabs)
        self._refresh_curadoria_rag_observer()

    def _make_curadoria_scroll_page(self):
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        scroll.setWidget(content)

        root.addWidget(scroll)
        return page, layout

    def _make_curadoria_header(self, title, subtitle):
        header = QFrame()
        header.setObjectName("CuradoriaHeader")
        header.setStyleSheet(_resolve_css("""
            #CuradoriaHeader {
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
            }
        """))
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(12)

        text_box = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Colors.TEXT_BRIGHT};")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_SECONDARY};")
        text_box.addWidget(title_label)
        text_box.addWidget(subtitle_label)

        refresh_btn = QPushButton("Atualizar")
        refresh_btn.setFixedHeight(28)
        refresh_btn.setToolTip("Recarrega metricas de leitura. Nao escreve no banco nem indexa fichas.")
        refresh_btn.clicked.connect(self._refresh_curadoria_rag_observer)
        refresh_btn.setStyleSheet(_resolve_css("""
            QPushButton {
                background: {Colors.BG_SECONDARY};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 5px;
                padding: 4px 12px;
                font-weight: 600;
            }
            QPushButton:hover { border-color: {Colors.ACCENT_PRIMARY}; }
        """))

        layout.addLayout(text_box, 1)
        layout.addWidget(refresh_btn)
        return header

    def _make_curadoria_metric_card(self, key, title, subtitle):
        card = QFrame()
        card.setObjectName("CuradoriaMetricCard")
        card.setMinimumHeight(78)
        card.setStyleSheet(_resolve_css("""
            #CuradoriaMetricCard {
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
            }
        """))
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(3)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {Colors.TEXT_SECONDARY};")
        value_label = QLabel("-")
        value_label.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {Colors.ACCENT_PRIMARY};")
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_MUTED};")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)
        self._curadoria_metric_labels[key] = value_label
        return card

    def _make_curadoria_compact_metric_card(self, key, title, subtitle):
        card = QFrame()
        card.setObjectName("CuradoriaCompactMetricCard")
        card.setFixedHeight(64)
        card.setStyleSheet(_resolve_css("""
            #CuradoriaCompactMetricCard {
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
            }
        """))
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        value_label = QLabel("-")
        value_label.setMinimumWidth(44)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {Colors.ACCENT_PRIMARY};")
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {Colors.TEXT_BRIGHT};")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_SECONDARY};")
        text_box.addWidget(title_label)
        text_box.addWidget(subtitle_label)

        layout.addWidget(value_label)
        layout.addLayout(text_box, 1)
        self._curadoria_metric_labels[key] = value_label
        return card

    def _make_curadoria_table(self, key, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.verticalHeader().setDefaultSectionSize(34)
        table.horizontalHeader().setStretchLastSection(True)
        for idx in range(len(headers)):
            table.horizontalHeader().setSectionResizeMode(idx, QHeaderView.Stretch)
        table.setStyleSheet(_resolve_css("""
            QTableWidget {
                background: {Colors.BG_DEEP};
                alternate-background-color: {Colors.BG_PANEL};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                gridline-color: transparent;
                selection-background-color: rgba(0, 212, 255, 34);
                selection-color: {Colors.TEXT_BRIGHT};
            }
            QTableWidget::item {
                padding: 7px 10px;
                border-bottom: 1px solid {Colors.BORDER_SUBTLE};
            }
            QTableWidget::item:hover {
                background: rgba(0, 212, 255, 22);
            }
            QHeaderView::section {
                background: {Colors.BG_SURFACE};
                color: {Colors.TEXT_SECONDARY};
                border: none;
                border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
                padding: 7px 10px;
                font-size: 10px;
                font-weight: bold;
            }
        """))
        self._curadoria_tables[key] = table
        return table

    def _make_training_cycle_card(self, code, title, subtitle, body, accent):
        card = QFrame()
        card.setObjectName("TrainingCycleCard")
        card.setMinimumHeight(148)
        card.setStyleSheet(f"""
            QFrame#TrainingCycleCard {{
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-top: 3px solid {accent};
                border-radius: 6px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)

        top = QHBoxLayout()
        top.setSpacing(8)
        badge = QLabel(code)
        badge.setFixedHeight(22)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"""
            QLabel {{
                background: {accent};
                color: #050505;  /* hardcoded-ok — near-black contraste sobre badge colorido */
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {Colors.TEXT_BRIGHT};")
        title_label.setWordWrap(True)
        top.addWidget(badge)
        top.addWidget(title_label, 1)
        layout.addLayout(top)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f"font-size: 10px; color: {Colors.ACCENT_PRIMARY}; font-weight: 600;")
        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_PRIMARY}; line-height: 135%;")
        layout.addWidget(subtitle_label)
        layout.addWidget(body_label, 1)
        return card

    def _build_curadoria_map_tab(self):
        page, layout = self._make_curadoria_scroll_page()
        layout.addWidget(self._make_curadoria_header(
            "Mapa RAG - Cerebro com barreira de confianca",
            "Fluxo observador: N1/N2/N3/N4 alimentam hipoteses, mas so T1/T2 entram no RAG global. TX representa conhecimento desvalidado por humano."
        ))

        grid = QGridLayout()
        grid.setSpacing(10)
        cards = [
            ("tier_t0", "T0 Quarentena", "Hipoteses em desenvolvimento. Nao entram no RAG global."),
            ("tier_t1", "T1 Validados", "Itens aprovados por humano. Podem ensinar o RAG."),
            ("tier_t2", "T2 Consolidados", "Padroes validados em mais de uma obra."),
            ("tier_tx", "TX Revogados", "Desvalidacoes humanas/tombstones. Ficam fora das consultas."),
            ("semantic_total", "Regras Semanticas", "semantic_rag_kb populada a partir do domain_knowledge."),
            ("crop_learning_total", "Recortes CROP-T1", "Recortes aprovados por humano. Ensinam crop, nao F5/N4."),
            ("training_events", "Training Events", "Historico de validacoes, rejeicoes e sinais de treino."),
            ("obra_rag_snapshots", "RAG por-obra", "Snapshots locais em DADOS-OBRAS/*/obra_rag."),
        ]
        for index, args in enumerate(cards):
            grid.addWidget(self._make_curadoria_metric_card(*args), index // 3, index % 3)
        layout.addLayout(grid)

        pipeline = QTextEdit()
        pipeline.setReadOnly(True)
        pipeline.setMinimumHeight(170)
        pipeline.setPlainText(
            "DXF bruto -> Structural Analyzer (N1/F7) ----\\\n"
            "                                               > Comparison Engine -> validacao humana -> BARREIRA DE TIER -> RAG Global\n"
            "STOG humano -> Motor Reverso (N2/F5) --------/\n\n"
            "Regras/semantica: podem entrar agora via domain_knowledge -> semantic_rag_kb.\n"
            "Instancias/fichas: so entram apos validacao humana (T1/T2).\n"
            "Recorte aprovado: alimenta CROP-T1 e melhora recorte por classe; nao valida F5/N2 nem N4.\n"
            "Desvalidacao humana: vira TX/tombstone, sai das consultas e permanece auditavel."
        )
        pipeline.setStyleSheet(_resolve_css("""
            QTextEdit {
                background: {Colors.BG_CARD};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                padding: 10px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
        """))
        layout.addWidget(pipeline)
        layout.addStretch()
        return page

    def _build_curadoria_encyclopedia_tab(self):
        page, layout = self._make_curadoria_scroll_page()
        layout.addWidget(self._make_curadoria_header(
            "Enciclopedia de Classes - 8 dimensoes",
            "Cobertura baseada em evidencias presentes no N1/F7, N2/F5 e nas regras semanticas. Ausencia de evidencia nao e preenchida por inferencia."
        ))

        layout.addWidget(self._make_curadoria_table(
            "encyclopedia",
            ["Classe", "F5/N2", "F7/N1", "T0", "T1", "T2", "TX", "Regras", "Dimensoes com evidencia", "Cobertura"],
        ))

        dimensions = QTextEdit()
        dimensions.setReadOnly(True)
        dimensions.setMinimumHeight(145)
        dimensions.setPlainText(
            "DIM-1 Visual estrutural N1  | DIM-2 Desenho dos robos N3/N4\n"
            "DIM-3 Dados e fichas        | DIM-4 Descricao, geometria e logica\n"
            "DIM-5 Obra/pavimento/item   | DIM-6 Engenharia reversa N2\n"
            "DIM-7 Layers/cores/historico| DIM-8 Corpus global entre obras\n\n"
            "A cobertura indica apenas fontes materializadas. Nao declara que a compreensao da classe esta correta."
        )
        dimensions.setStyleSheet(_resolve_css("""
            QTextEdit {
                background: {Colors.BG_CARD};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
                padding: 10px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
        """))
        layout.addWidget(dimensions)
        return page

    def _build_curadoria_corpus_tab(self):
        page, layout = self._make_curadoria_scroll_page()
        layout.addWidget(self._make_curadoria_header(
            "Corpus & Cobertura",
            "Visao das fichas F5/F7, tiers e cobertura. Esta aba nao valida, nao desvalida e nao indexa."
        ))

        grid = QGridLayout()
        grid.setSpacing(10)
        for index, args in enumerate([
            ("reverse_total", "F5/N2 Reverse", "Fichas granulares da engenharia reversa."),
            ("reverse_indexed", "F5 rag_indexed", "Quantidade marcada como indexada no banco."),
            ("fase3_total", "F7/N1 Structural", "Fichas do Structural Analyzer."),
            ("fase3_reviewed", "F7 revisadas", "Itens revisados por humano."),
        ]):
            grid.addWidget(self._make_curadoria_metric_card(*args), index // 4, index % 4)
        layout.addLayout(grid)

        layout.addWidget(QLabel("Cobertura por tabela / tier"))
        layout.addWidget(self._make_curadoria_table("coverage", ["Fonte", "Total", "T0", "T1", "T2", "TX", "Observacao"]))
        layout.addWidget(QLabel("semantic_rag_kb por classe"))
        layout.addWidget(self._make_curadoria_table("semantic_by_class", ["Classe", "Regras", "Contexto"]))
        return page

    def _build_curadoria_learning_tab(self):
        page, layout = self._make_curadoria_scroll_page()
        layout.addWidget(self._make_curadoria_header(
            "Aprendizado supervisionado por humano",
            "Historico observador dos sinais de treino. T0 e TX nunca contam como professores nem entram em retraining."
        ))

        grid = QGridLayout()
        grid.setSpacing(10)
        for index, args in enumerate([
            ("learning_total", "Eventos", "Total de training_events auditaveis."),
            ("learning_validations", "Validacoes", "Confirmacoes humanas registradas."),
            ("learning_rejections", "Rejeicoes", "Correcoes e recusas humanas."),
            ("learning_na", "N/A", "Campos marcados como nao aplicaveis."),
            ("learning_accuracy", "Accuracy media", "Media das transformation_rules existentes."),
        ]):
            grid.addWidget(self._make_curadoria_metric_card(*args), index // 5, index % 5)
        layout.addLayout(grid)

        layout.addWidget(QLabel("Eventos por tipo"))
        layout.addWidget(self._make_curadoria_table("learning_event_types", ["Tipo", "Eventos"]))
        layout.addWidget(QLabel("Campos com mais sinais humanos"))
        layout.addWidget(self._make_curadoria_table("learning_roles", ["Campo / role", "Eventos"]))
        layout.addWidget(QLabel("Regras de transformacao"))
        layout.addWidget(self._make_curadoria_table(
            "learning_rules",
            ["Tipo", "Regras", "Accuracy media", "Menor accuracy"],
        ))
        return page

    def _build_curadoria_training_pipelines_tab(self):
        page, layout = self._make_curadoria_scroll_page()
        layout.addWidget(self._make_curadoria_header(
            "Pipelines de Treino - Arete por classe",
            "Mapa mental dos ciclos que melhoram recorte, N2->N4, N2<->N1 e N1->N3. Esta aba e observadora: nao treina, nao indexa e nao promove dado."
        ))

        grid = QGridLayout()
        grid.setSpacing(8)
        for index, args in enumerate([
            ("train_docs_arete", "Docs Arete", "Masterplans e docs de treino encontrados."),
            ("train_scripts", "Loopers/Scripts", "Scripts de loop, runner e auditoria Arete."),
            ("train_runs", "Runs/Artefatos", "Artefatos de execucao encontrados em modo observador."),
            ("train_events", "Training Events", "Sinais humanos para treino supervisionado."),
            ("train_crop_events", "CROP-T1", "Recortes aprovados que ensinam crop por classe."),
            ("train_human_notes", "Notas humanas", "Alertas/atencoes humanas registrados para revisao."),
        ]):
            grid.addWidget(self._make_curadoria_compact_metric_card(*args), index // 3, index % 3)
        layout.addLayout(grid)

        flow = QGridLayout()
        flow.setSpacing(10)
        cycle_cards = [
            (
                "CROP",
                "Aprender a recortar",
                "Professor: recorte aprovado",
                "Ajusta janela, margem, classe, layers e falsos positivos. Nao valida ficha F5/N2 nem desenho N4.",
                Colors.ACCENT_SUCCESS,
            ),
            (
                "A",
                "N2 -> N4",
                "Professor: STOG humano + F5 validada",
                "Treina motor reverso e robo N4 ate o DXF gerado reproduzir o desenho humano validado.",
                Colors.ACCENT_PURPLE,
            ),
            (
                "B",
                "N2 <-> N1",
                "Professor externo: N2/F5",
                "Treina interpretacao do Structural Analyzer e o mapeamento N1 -> ficha de robo, sem copiar gabarito.",
                Colors.ACCENT_BLUE,
            ),
            (
                "C",
                "N1 -> N3",
                "Juiz externo: N4 validado",
                "N1 gera N3 sozinho. Comparison Engine mede N3 contra N4 e bloqueia qualquer vazamento de N2/N4.",
                Colors.ACCENT_WARNING,
            ),
            (
                "NOTAS",
                "Humano no loop",
                "Professor: decisao e atencao humana",
                "Aprovacao, rejeicao, N/A, desvalidacao e notas viram eventos auditaveis antes de qualquer regra global.",
                Colors.ACCENT_INFO,
            ),
        ]
        for index, args in enumerate(cycle_cards):
            flow.addWidget(self._make_training_cycle_card(*args), index // 3, index % 3)
        layout.addLayout(flow)

        contract = QFrame()
        contract.setObjectName("TrainingContract")
        contract.setStyleSheet(_resolve_css("""
            QFrame#TrainingContract {
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 6px;
            }
        """))
        contract_layout = QHBoxLayout(contract)
        contract_layout.setContentsMargins(14, 10, 14, 10)
        contract_layout.setSpacing(16)
        for title, body, color in [
            ("RAG", "Memoria consultavel. Nao e o treinador.", Colors.ACCENT_PRIMARY),
            ("Tiers", "T0 quarentena | T1 validado | T2 consolidado | TX revogado.", Colors.ACCENT_GOLD),
            ("Anti-vazamento", "N3 nunca recebe N2/N4 como entrada.", Colors.ACCENT_DANGER),
        ]:
            box = QVBoxLayout()
            label = QLabel(title)
            label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {color};")
            text = QLabel(body)
            text.setWordWrap(True)
            text.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_PRIMARY};")
            box.addWidget(label)
            box.addWidget(text)
            contract_layout.addLayout(box, 1)
        layout.addWidget(contract)

        layout.addWidget(QLabel("Ciclos operacionais"))
        layout.addWidget(self._make_curadoria_table(
            "training_pipelines",
            ["Ciclo", "Professor / juiz", "Motor treinado", "Gate humano / metrica", "Alimenta RAG/Dados", "Nao fazer"],
        ))
        layout.addWidget(QLabel("Cobertura por classe"))
        layout.addWidget(self._make_curadoria_table(
            "training_classes",
            ["Classe", "Partes", "Docs", "Loopers/Scripts", "Estado", "Proximo gate"],
        ))
        layout.addWidget(QLabel("Artefatos de execucao observados"))
        layout.addWidget(self._make_curadoria_table(
            "training_runs",
            ["Fonte", "Classe", "Artefatos", "Ultima atualizacao", "Status"],
        ))
        return page

    def _build_curadoria_pending_tab(self):
        page, layout = self._make_curadoria_scroll_page()
        layout.addWidget(self._make_curadoria_header(
            "Pendencias de consolidacao",
            "Fila deterministica do que precisa de validacao ou harmonizacao. Nao corrige, promove ou indexa dados automaticamente."
        ))

        grid = QGridLayout()
        grid.setSpacing(10)
        for index, args in enumerate([
            ("pending_high", "Prioridade alta", "Exige decisao ou validacao humana."),
            ("pending_medium", "Prioridade media", "Lacuna relevante para consolidacao."),
            ("pending_info", "Informativo", "Cobertura incompleta durante o desenvolvimento."),
        ]):
            grid.addWidget(self._make_curadoria_metric_card(*args), 0, index)
        layout.addLayout(grid)
        layout.addWidget(self._make_curadoria_table(
            "pending",
            ["Prioridade", "Area", "Achado", "Acao recomendada"],
        ))
        return page

    def _build_curadoria_mcp_evidence_tab(self):
        page, layout = self._make_curadoria_scroll_page()
        layout.addWidget(self._make_curadoria_header(
            "Evidencias MCP - Active Learning controlado",
            "Edicoes sao evidencias T0. Somente Aprovar proposta promove para T1; Salvar nunca valida."
        ))
        grid = QGridLayout()
        grid.setSpacing(8)
        for index, args in enumerate([
            ("mcp_captured", "Capturadas", "Edicoes aguardando analise."),
            ("mcp_proposed", "Propostas T0", "Hipoteses aguardando decisao humana."),
            ("mcp_approved", "Aprovadas T1", "Licoes autorizadas explicitamente."),
            ("mcp_indexed", "Indexadas", "Aprovadas materializadas no store MCP."),
            ("mcp_rejected", "Rejeitadas/TX", "Historico preservado fora das consultas."),
            ("mcp_failed", "Falhas", "Eventos reprocessaveis com erro auditavel."),
        ]):
            grid.addWidget(self._make_curadoria_compact_metric_card(*args), index // 3, index % 3)
        layout.addLayout(grid)

        actions = QGridLayout()
        actions.setSpacing(8)
        for index, (text, callback) in enumerate([
            ("Gerar propostas T0", lambda: self._run_mcp_background("daemon")),
            ("Analisar padroes", lambda: self._run_mcp_background("patterns")),
            ("Atualizar indice candidato", lambda: self._run_mcp_background("candidates")),
            ("Aprovar proposta", self._approve_selected_mcp_proposal),
            ("Rejeitar proposta", self._reject_selected_mcp_proposal),
            ("Indexar aprovadas T1", lambda: self._run_mcp_background("approved")),
        ]):
            button = QPushButton(text)
            button.setMinimumHeight(30)
            button.clicked.connect(callback)
            actions.addWidget(button, index // 3, index % 3)
        layout.addLayout(actions)
        self._mcp_evidence_status = QLabel("")
        self._mcp_evidence_status.setStyleSheet(f"color:{Colors.TEXT_SECONDARY}; font-size:11px;")
        layout.addWidget(self._mcp_evidence_status)
        layout.addWidget(self._make_curadoria_table(
            "mcp_evidence",
            ["ID", "Estado", "Tier", "Classe", "Item", "Fase", "Obra", "Motivo", "Atualizado"],
        ))
        return page

    def _selected_mcp_log_id(self):
        table = self._curadoria_tables.get("mcp_evidence")
        if not table or table.currentRow() < 0:
            return "", ""
        row = table.currentRow()
        id_item = table.item(row, 0)
        status_item = table.item(row, 1)
        return (
            id_item.text() if id_item else "",
            status_item.text() if status_item else "",
        )

    def _mcp_bridge(self):
        import sys
        repo_root = Path(getattr(self.db, "db_path", "D:/Agente-cad-PYSIDE/project_data.vision")).resolve().parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from src.mcp import db_bridge
        return db_bridge

    def _mcp_actor_id(self):
        user = getattr(self.auth_service, "current_user", None)
        if isinstance(user, dict):
            return str(user.get("email") or user.get("id") or "ui_operator")
        return str(getattr(user, "email", None) or getattr(user, "id", None) or "ui_operator")

    def _approve_selected_mcp_proposal(self):
        log_id, status = self._selected_mcp_log_id()
        if not log_id or status != "PROPOSED":
            QMessageBox.information(self, "Evidencias MCP", "Selecione uma proposta T0 em estado PROPOSED.")
            return
        reason, ok = QInputDialog.getText(
            self, "Aprovar proposta", "Justificativa humana obrigatoria:"
        )
        if not ok or not reason.strip():
            return
        try:
            changed = self._mcp_bridge().approve_event_candidate(
                log_id,
                approved_by=self._mcp_actor_id(),
                reason=reason.strip(),
                validation_origin="human_ui",
                db_path=Path(self.db.db_path),
            )
            if not changed:
                raise RuntimeError("a proposta mudou de estado antes da aprovacao")
            self._refresh_curadoria_rag_observer()
        except Exception as exc:
            QMessageBox.critical(self, "Aprovar proposta", str(exc))

    def _reject_selected_mcp_proposal(self):
        log_id, status = self._selected_mcp_log_id()
        if not log_id or status not in {"PROPOSED", "APPROVED"}:
            QMessageBox.information(self, "Evidencias MCP", "Selecione uma proposta PROPOSED ou APPROVED.")
            return
        reason, ok = QInputDialog.getText(
            self, "Rejeitar proposta", "Motivo obrigatorio:"
        )
        if not ok or not reason.strip():
            return
        try:
            changed = self._mcp_bridge().reject_event_candidate(
                log_id,
                rejected_by=self._mcp_actor_id(),
                reason=reason.strip(),
                db_path=Path(self.db.db_path),
            )
            if not changed:
                raise RuntimeError("a proposta mudou de estado antes da rejeicao")
            self._refresh_curadoria_rag_observer()
        except Exception as exc:
            QMessageBox.critical(self, "Rejeitar proposta", str(exc))

    def _run_mcp_background(self, mode):
        if getattr(self, "_mcp_learning_process", None):
            if self._mcp_learning_process.state() != QProcess.NotRunning:
                return
        repo_root = Path(getattr(self.db, "db_path", "D:/Agente-cad-PYSIDE/project_data.vision")).resolve().parent
        if mode == "daemon":
            script = repo_root / "scripts" / "mcp_active_learning_daemon.py"
            args = [str(script), "--db", str(self.db.db_path)]
        elif mode == "patterns":
            script = repo_root / "scripts" / "active_learning_patterns.py"
            args = [str(script), "--db", str(self.db.db_path)]
        else:
            script = repo_root / "scripts" / "rag_active_trainer.py"
            args = [str(script), "--db", str(self.db.db_path)]
            if mode == "approved":
                args.append("--approved")
        process = QProcess(self)
        process.setWorkingDirectory(str(repo_root))
        process.finished.connect(lambda code, _status: self._on_mcp_background_finished(code))
        self._mcp_learning_process = process
        self._mcp_evidence_status.setText(f"Executando {mode}...")
        process.start(sys.executable, args)

    def _on_mcp_background_finished(self, exit_code):
        process = getattr(self, "_mcp_learning_process", None)
        output = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace") if process else ""
        error = bytes(process.readAllStandardError()).decode("utf-8", errors="replace") if process else ""
        self._mcp_evidence_status.setText(
            ("Concluido. " + output.strip()) if exit_code == 0 else ("Falha: " + error.strip())
        )
        self._refresh_curadoria_rag_observer()

    def _build_curadoria_vector_tab(self):
        page, layout = self._make_curadoria_scroll_page()
        layout.addWidget(self._make_curadoria_header(
            "Memoria Vetorial",
            "Stores FAISS e tombstones. Vetores antigos sem validacao aparecem como T0 e ficam ocultos nas consultas T1+."
        ))
        grid = QGridLayout()
        grid.setSpacing(10)
        for index, args in enumerate([
            ("faiss_total", "FAISS meta", "Total de metadados nos arquivos *_meta.json."),
            ("faiss_t1_visible", "FAISS visivel T1+", "Vetores que podem responder como professor."),
            ("tombstones", "Tombstones", "Itens desvalidados humanamente."),
            ("legacy_t0", "FAISS legado T0", "Vetores existentes sem selo de validacao."),
        ]):
            grid.addWidget(self._make_curadoria_metric_card(*args), index // 4, index % 4)
        layout.addLayout(grid)
        layout.addWidget(self._make_curadoria_table("faiss_stores", ["Store", "Metas", "T0", "T1", "T2", "TX", "Arquivo"]))
        return page

    def _build_curadoria_db_tab(self):
        page, layout = self._make_curadoria_scroll_page()
        layout.addWidget(self._make_curadoria_header(
            "Banco de Dados",
            "Leitura direta de project_data.vision com alertas de integridade para o plano RAG."
        ))
        layout.addWidget(self._make_curadoria_table("db_tables", ["Tabela", "Rows", "Status", "Alerta"]))
        layout.addWidget(QLabel("Transformation rules"))
        layout.addWidget(self._make_curadoria_table("rules", ["Tipo", "Regras", "Accuracy media", "Menor accuracy"]))
        return page

    def _refresh_curadoria_rag_observer(self):
        metrics = self._collect_curadoria_rag_metrics()

        values = {
            "tier_t0": metrics["tiers"].get("T0", 0),
            "tier_t1": metrics["tiers"].get("T1", 0),
            "tier_t2": metrics["tiers"].get("T2", 0),
            "tier_tx": metrics["tiers"].get("TX", 0),
            "semantic_total": metrics["semantic_total"],
            "crop_learning_total": metrics["table_counts"].get("crop_learning_events", 0),
            "training_events": metrics["table_counts"].get("training_events", 0),
            "obra_rag_snapshots": metrics["obra_rag_snapshots"],
            "reverse_total": metrics["table_counts"].get("reverse_eng_fichas", 0),
            "reverse_indexed": metrics["reverse_indexed"],
            "fase3_total": metrics["table_counts"].get("fase3_fichas", 0),
            "fase3_reviewed": metrics["fase3_reviewed"],
            "faiss_total": metrics["faiss_total"],
            "faiss_t1_visible": metrics["faiss_visible"],
            "tombstones": metrics["tombstones"],
            "legacy_t0": metrics["faiss_tiers"].get("T0", 0),
            "learning_total": metrics["table_counts"].get("training_events", 0),
            "learning_validations": metrics["learning_counts"].get("user_validation", 0),
            "learning_rejections": metrics["learning_counts"].get("user_rejection", 0),
            "learning_na": metrics["learning_counts"].get("user_na", 0),
            "learning_accuracy": metrics["learning_accuracy"],
            "train_docs_arete": metrics["train_docs_arete"],
            "train_scripts": metrics["train_scripts"],
            "train_runs": metrics["train_runs"],
            "train_events": metrics["table_counts"].get("training_events", 0),
            "train_crop_events": metrics["table_counts"].get("crop_learning_events", 0),
            "train_artifacts": (
                f"{metrics['artifact_counts'].get('render_ready', 0)}/"
                f"{metrics['artifact_counts'].get('validated', 0)}"
            ),
            "train_human_notes": metrics["train_human_notes"],
            "mcp_captured": metrics["mcp_status_counts"].get("CAPTURED", 0),
            "mcp_proposed": metrics["mcp_status_counts"].get("PROPOSED", 0),
            "mcp_approved": metrics["mcp_status_counts"].get("APPROVED", 0),
            "mcp_indexed": metrics["mcp_status_counts"].get("INDEXED", 0),
            "mcp_rejected": (
                metrics["mcp_status_counts"].get("REJECTED", 0)
                + metrics["mcp_status_counts"].get("TEST_QUARANTINED", 0)
            ),
            "mcp_failed": metrics["mcp_status_counts"].get("FAILED", 0),
            "pending_high": metrics["pending_counts"].get("ALTA", 0),
            "pending_medium": metrics["pending_counts"].get("MEDIA", 0),
            "pending_info": metrics["pending_counts"].get("INFO", 0),
        }
        for key, value in values.items():
            label = self._curadoria_metric_labels.get(key)
            if label:
                label.setText(str(value))

        self._fill_curadoria_table("coverage", metrics["coverage_rows"])
        self._fill_curadoria_table("encyclopedia", metrics["encyclopedia_rows"])
        self._fill_curadoria_table("semantic_by_class", metrics["semantic_rows"])
        self._fill_curadoria_table("learning_event_types", metrics["learning_event_rows"])
        self._fill_curadoria_table("learning_roles", metrics["learning_role_rows"])
        self._fill_curadoria_table("learning_rules", metrics["rule_rows"])
        self._fill_curadoria_table("training_pipelines", metrics["training_pipeline_rows"])
        self._fill_curadoria_table("training_classes", metrics["training_class_rows"])
        self._fill_curadoria_table("training_runs", metrics["training_run_rows"])
        self._fill_curadoria_table("mcp_evidence", metrics["mcp_evidence_rows"])
        self._fill_curadoria_table("pending", metrics["pending_rows"])
        self._fill_curadoria_table("faiss_stores", metrics["faiss_rows"])
        self._fill_curadoria_table("db_tables", metrics["db_rows"])
        self._fill_curadoria_table("rules", metrics["rule_rows"])

    def _fill_curadoria_table(self, key, rows):
        table = self._curadoria_tables.get(key)
        if not table:
            return
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setToolTip(str(value))
                if key == "pending" and col_idx == 0:
                    priority_colors = {
                        "ALTA": Colors.ACCENT_DANGER,
                        "MEDIA": Colors.ACCENT_WARNING,
                        "INFO": Colors.ACCENT_INFO,
                    }
                    item.setForeground(QColor(priority_colors.get(str(value), Colors.TEXT_PRIMARY)))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                elif key in {"training_pipelines", "training_classes", "training_runs"} and col_idx == 0:
                    item.setForeground(QColor(Colors.ACCENT_PRIMARY))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                table.setItem(row_idx, col_idx, item)

    def _collect_curadoria_rag_metrics(self):
        import sqlite3
        import sys
        from collections import Counter, defaultdict

        repo_root = Path(getattr(self.db, "db_path", "D:/Agente-cad-PYSIDE/project_data.vision")).resolve().parent
        app_root = Path(__file__).resolve().parents[3]
        scripts_dir = repo_root / "scripts"
        app_repo_root = app_root.parent
        app_repo_scripts_dir = app_repo_root / "scripts"
        for candidate_scripts_dir in (scripts_dir, app_repo_scripts_dir):
            if candidate_scripts_dir.exists() and str(candidate_scripts_dir) not in sys.path:
                sys.path.insert(0, str(candidate_scripts_dir))

        try:
            from rag_tier import get_tier, load_tombstones, tier_at_least
        except Exception:
            def get_tier(row, tombstones=None):
                return "T0"
            def load_tombstones(path=None):
                return {}
            def tier_at_least(tier, min_tier="T1"):
                return tier in {"T1", "T2"}

        registry_error = ""
        try:
            from classe_registry import canonicalize_class, load_registry, registered_classes
            registry_path = repo_root / "data" / "classe_registry.json"
            if not registry_path.exists():
                registry_path = app_repo_root / "data" / "classe_registry.json"
            class_registry = load_registry(registry_path)
            canonical_classes = registered_classes(class_registry)

            def canonical_class(value):
                return canonicalize_class(value, class_registry)[0]
        except Exception as exc:
            registry_error = str(exc)
            canonical_classes = {"PIL", "LV", "FV", "LAJ"}

            def canonical_class(value):
                raw = str(value or "?").strip().upper()
                return {"PILAR": "PIL", "LAJE": "LAJ"}.get(raw, raw)

        db_path = Path(getattr(self.db, "db_path", repo_root / "project_data.vision"))
        faiss_dir = repo_root / "data" / "vectors" / "faiss"
        tombstones = load_tombstones(faiss_dir / "rag_tombstones.json")
        docs_dir = app_root / "docs"
        app_scripts_dir = app_root / "scripts"
        arete_docs = sorted(docs_dir.glob("*ARETE*.md")) if docs_dir.exists() else []
        loop_script_patterns = ["*loop*.py", "*runner*.py", "*arete*.py", "*audit*.py"]
        loop_scripts = []
        for scripts_root in {scripts_dir, app_scripts_dir}:
            if scripts_root.exists():
                for pattern in loop_script_patterns:
                    loop_scripts.extend(scripts_root.glob(pattern))
        loop_scripts = sorted({path.resolve() for path in loop_scripts})

        def _latest_mtime(paths):
            latest = 0
            for path in paths:
                try:
                    latest = max(latest, int(path.stat().st_mtime))
                except OSError:
                    pass
            return latest

        def _fmt_mtime(timestamp):
            if not timestamp:
                return "-"
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")

        def _collect_arete_artifacts():
            rows = []
            tmp_dir = app_root / "scripts" / "arete" / "tmp"
            if tmp_dir.exists():
                children = [p for p in tmp_dir.iterdir() if p.is_dir()]
                for classe in ["PIL", "LV", "FV", "LAJ"]:
                    class_dirs = [p for p in children if p.name.upper().startswith(f"{classe}_")]
                    if class_dirs:
                        rows.append([
                            "scripts/arete/tmp",
                            classe,
                            len(class_dirs),
                            _fmt_mtime(_latest_mtime(class_dirs)),
                            "Observado: resultado de looper, nao validacao humana",
                        ])
            lv_runs = app_root / "sandbox_lv_loop" / "runs"
            if lv_runs.exists():
                children = [p for p in lv_runs.iterdir()]
                rows.append([
                    "sandbox_lv_loop/runs",
                    "LV",
                    len(children),
                    _fmt_mtime(_latest_mtime(children)),
                    "Sandbox read-only na Curadoria",
                ])
            screenshots = app_root / "tests" / "screenshots"
            if screenshots.exists():
                pngs = list(screenshots.glob("*.png"))
                if pngs:
                    rows.append([
                        "tests/screenshots",
                        "QA",
                        len(pngs),
                        _fmt_mtime(_latest_mtime(pngs)),
                        "Evidencia visual; nao promove tier",
                    ])
            return rows

        metrics = {
            "tiers": Counter(),
            "faiss_tiers": Counter(),
            "table_counts": {},
            "semantic_total": 0,
            "reverse_indexed": 0,
            "fase3_reviewed": 0,
            "faiss_total": 0,
            "faiss_visible": 0,
            "tombstones": len(tombstones),
            "coverage_rows": [],
            "encyclopedia_rows": [],
            "semantic_rows": [],
            "learning_counts": Counter(),
            "artifact_counts": Counter(),
            "artifact_history_rows": [],
            "mcp_status_counts": Counter(),
            "mcp_evidence_rows": [],
            "learning_event_rows": [],
            "learning_role_rows": [],
            "learning_accuracy": "-",
            "pending_counts": Counter(),
            "pending_rows": [],
            "faiss_rows": [],
            "db_rows": [],
            "rule_rows": [],
            "training_pipeline_rows": [],
            "training_class_rows": [],
            "training_run_rows": _collect_arete_artifacts(),
            "train_docs_arete": len(arete_docs),
            "train_scripts": len(loop_scripts),
            "train_runs": 0,
            "train_human_notes": 0,
            "obra_rag_snapshots": 0,
            "latest_obra_rag": "",
            "registry_error": registry_error,
        }
        metrics["train_runs"] = sum(
            int(row[2]) for row in metrics["training_run_rows"] if str(row[2]).isdigit()
        )

        def table_exists(conn, table):
            return conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone() is not None

        def table_columns(conn, table):
            return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]

        def fetch_rows(conn, table):
            if not table_exists(conn, table):
                return []
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]

        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            try:
                tracked_tables = [
                    "reverse_eng_fichas",
                    "fase3_fichas",
                    "semantic_rag_kb",
                    "crop_learning_events",
                    "rag_artifact_validations",
                    "training_events",
                    "transformation_rules",
                    "item_attention_notes",
                    "human_event_logs",
                    "cache_fichas",
                ]
                for table in tracked_tables:
                    if table_exists(conn, table):
                        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        metrics["table_counts"][table] = count
                    else:
                        metrics["table_counts"][table] = 0

                reverse_rows = fetch_rows(conn, "reverse_eng_fichas")
                reverse_tiers = Counter(get_tier(row, tombstones=tombstones) for row in reverse_rows)
                metrics["tiers"].update(reverse_tiers)
                if table_exists(conn, "reverse_eng_fichas") and "rag_indexed" in table_columns(conn, "reverse_eng_fichas"):
                    metrics["reverse_indexed"] = conn.execute(
                        "SELECT COUNT(*) FROM reverse_eng_fichas WHERE COALESCE(rag_indexed, 0) != 0"
                    ).fetchone()[0]

                fase3_rows = fetch_rows(conn, "fase3_fichas")
                fase3_tiers = Counter(get_tier(row, tombstones=tombstones) for row in fase3_rows)
                metrics["tiers"].update(fase3_tiers)
                if table_exists(conn, "fase3_fichas") and "revisado" in table_columns(conn, "fase3_fichas"):
                    metrics["fase3_reviewed"] = conn.execute(
                        "SELECT COUNT(*) FROM fase3_fichas WHERE COALESCE(revisado, 0) != 0"
                    ).fetchone()[0]

                metrics["semantic_total"] = metrics["table_counts"].get("semantic_rag_kb", 0)
                if table_exists(conn, "rag_artifact_validations"):
                    artifact_columns = set(table_columns(conn, "rag_artifact_validations"))
                    if "status" in artifact_columns:
                        for status, count in conn.execute(
                            "SELECT status, COUNT(*) FROM rag_artifact_validations GROUP BY status"
                        ).fetchall():
                            metrics["artifact_counts"][str(status or "?")] = count
                    if "render_status" in artifact_columns:
                        metrics["artifact_counts"]["render_ready"] = conn.execute(
                            """
                            SELECT COUNT(*) FROM rag_artifact_validations
                            WHERE status='validated' AND render_status='ready'
                            """
                        ).fetchone()[0]
                    artifact_fields = [
                        "scope", "classe", "item_id", "obra_name", "pavimento",
                        "status", "render_status", "updated_at", "validated_at",
                    ]
                    projection = ", ".join(
                        field if field in artifact_columns else f"NULL AS {field}"
                        for field in artifact_fields
                    )
                    order_field = "updated_at" if "updated_at" in artifact_columns else "rowid"
                    metrics["artifact_history_rows"] = [
                        [
                            str(row[0] or "?").upper(),
                            row[1] or "?",
                            row[2] or "?",
                            row[3] or "?",
                            row[4] or "?",
                            str(row[5] or "?").upper(),
                            row[6] or "-",
                            row[7] or row[8] or "-",
                        ]
                        for row in conn.execute(
                            f"""
                            SELECT {projection} FROM rag_artifact_validations
                            ORDER BY {order_field} DESC LIMIT 200
                            """
                        ).fetchall()
                    ]
                if table_exists(conn, "semantic_rag_kb"):
                    semantic_by_class = Counter()
                    for classe, count in conn.execute(
                        "SELECT classe, COUNT(*) FROM semantic_rag_kb GROUP BY classe ORDER BY classe"
                    ).fetchall():
                        metrics["semantic_rows"].append([classe or "?", count, "domain_knowledge:field_semantics"])
                        semantic_by_class[canonical_class(classe)] += count
                else:
                    semantic_by_class = Counter()

                reverse_by_class = defaultdict(list)
                for row in reverse_rows:
                    reverse_by_class[canonical_class(row.get("classe"))].append(row)
                fase3_by_class = defaultdict(list)
                for row in fase3_rows:
                    fase3_by_class[canonical_class(row.get("tipo"))].append(row)

                classes = sorted(
                    set(reverse_by_class)
                    | set(fase3_by_class)
                    | set(semantic_by_class)
                    | set(canonical_classes)
                )
                for classe in classes:
                    class_rows = reverse_by_class[classe] + fase3_by_class[classe]
                    class_tiers = Counter(get_tier(row, tombstones=tombstones) for row in class_rows)
                    evidence = set()
                    if fase3_by_class[classe]:
                        evidence.update({1, 3})
                    if reverse_by_class[classe]:
                        evidence.update({3, 5, 6})
                    if semantic_by_class.get(classe, 0):
                        evidence.add(4)
                    evidence_text = ", ".join(str(dim) for dim in sorted(evidence)) or "-"
                    metrics["encyclopedia_rows"].append([
                        classe,
                        len(reverse_by_class[classe]),
                        len(fase3_by_class[classe]),
                        class_tiers.get("T0", 0),
                        class_tiers.get("T1", 0),
                        class_tiers.get("T2", 0),
                        class_tiers.get("TX", 0),
                        semantic_by_class.get(classe, 0),
                        evidence_text,
                        f"{len(evidence)}/8",
                    ])

                metrics["coverage_rows"] = [
                    [
                        "F5/N2 reverse_eng_fichas",
                        len(reverse_rows),
                        reverse_tiers.get("T0", 0),
                        reverse_tiers.get("T1", 0),
                        reverse_tiers.get("T2", 0),
                        reverse_tiers.get("TX", 0),
                        "Instancias so indexam se T1/T2",
                    ],
                    [
                        "F7/N1 fase3_fichas",
                        len(fase3_rows),
                        fase3_tiers.get("T0", 0),
                        fase3_tiers.get("T1", 0),
                        fase3_tiers.get("T2", 0),
                        fase3_tiers.get("TX", 0),
                        "Motor puro; revisao humana vira T1",
                    ],
                    [
                        "crop_learning_events",
                        metrics["table_counts"].get("crop_learning_events", 0),
                        0,
                        metrics["table_counts"].get("crop_learning_events", 0),
                        0,
                        0,
                        "Recortes aprovados: ensinam crop, nao validam F5/N4",
                    ],
                    [
                        "semantic_rag_kb",
                        metrics["semantic_total"],
                        0,
                        metrics["semantic_total"],
                        0,
                        0,
                        "Regras semanticas, nao fichas draft",
                    ],
                ]

                metrics["db_rows"] = []
                for table in tracked_tables:
                    count = metrics["table_counts"].get(table, 0)
                    alert = ""
                    status = "OK"
                    if table == "semantic_rag_kb" and count == 0:
                        status, alert = "ATENCAO", "Bridge semantica vazia"
                    elif table == "crop_learning_events" and count == 0:
                        status, alert = "INFO", "Sem recortes humanos CROP-T1 ainda"
                    elif table == "cache_fichas" and count == 0:
                        status, alert = "INFO", "Cache vazio"
                    elif table == "reverse_eng_fichas" and metrics["reverse_indexed"] == 0:
                        status, alert = "OK", "Correto por enquanto: sem bulk de T0"
                    metrics["db_rows"].append([table, count, status, alert])

                if table_exists(conn, "transformation_rules"):
                    cols = table_columns(conn, "transformation_rules")
                    if "entity_type" in cols and "accuracy_pct" in cols:
                        rows = conn.execute(
                            """
                            SELECT entity_type, COUNT(*), AVG(accuracy_pct), MIN(accuracy_pct)
                            FROM transformation_rules
                            GROUP BY entity_type
                            ORDER BY entity_type
                            """
                        ).fetchall()
                        for entity_type, count, avg_acc, min_acc in rows:
                            metrics["rule_rows"].append([
                                entity_type or "?",
                                count,
                                f"{(avg_acc or 0):.1f}%",
                                f"{(min_acc or 0):.1f}%",
                            ])
                        accuracies = [
                            row[0] for row in conn.execute(
                                "SELECT accuracy_pct FROM transformation_rules WHERE accuracy_pct IS NOT NULL"
                            ).fetchall()
                        ]
                        if accuracies:
                            metrics["learning_accuracy"] = f"{sum(accuracies) / len(accuracies):.1f}%"

                if table_exists(conn, "training_events"):
                    for event_type, count in conn.execute(
                        "SELECT type, COUNT(*) FROM training_events GROUP BY type ORDER BY COUNT(*) DESC"
                    ).fetchall():
                        key = str(event_type or "?")
                        metrics["learning_counts"][key] = count
                        metrics["learning_event_rows"].append([key, count])
                    for role, count in conn.execute(
                        """
                        SELECT role, COUNT(*) FROM training_events
                        GROUP BY role ORDER BY COUNT(*) DESC LIMIT 20
                        """
                    ).fetchall():
                        metrics["learning_role_rows"].append([role or "?", count])
                metrics["train_human_notes"] = metrics["table_counts"].get("item_attention_notes", 0)
                if table_exists(conn, "human_event_logs"):
                    human_columns = set(table_columns(conn, "human_event_logs"))
                    if "status" in human_columns:
                        for status, count in conn.execute(
                            "SELECT status, COUNT(*) FROM human_event_logs GROUP BY status"
                        ).fetchall():
                            metrics["mcp_status_counts"][str(status or "CAPTURED")] = count
                        fields = [
                            "log_id", "status", "tier", "classe", "item_id",
                            "fase_editada", "obra_id", "user_reason", "updated_at",
                        ]
                        projection = ", ".join(
                            field if field in human_columns else f"NULL AS {field}"
                            for field in fields
                        )
                        metrics["mcp_evidence_rows"] = [
                            [
                                row[0] or "?",
                                row[1] or "CAPTURED",
                                row[2] or "T0",
                                row[3] or "?",
                                row[4] or "?",
                                row[5] or "?",
                                row[6] or "?",
                                row[7] or "",
                                row[8] or "-",
                            ]
                            for row in conn.execute(
                                f"""
                                SELECT {projection} FROM human_event_logs
                                ORDER BY COALESCE(updated_at, timestamp) DESC
                                LIMIT 500
                                """
                            ).fetchall()
                        ]
            except Exception as exc:
                metrics["db_rows"].append(["project_data.vision", 0, "ERRO", str(exc)])
            finally:
                conn.close()
        else:
            metrics["db_rows"].append([str(db_path), 0, "ERRO", "Banco nao encontrado"])

        store_totals = defaultdict(Counter)
        for meta_path in sorted(faiss_dir.glob("*_meta.json")):
            if meta_path.name == "REGISTRY.json":
                continue
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                data = []
            rows = data if isinstance(data, list) else list(data.values()) if isinstance(data, dict) else []
            counts = Counter(get_tier(row if isinstance(row, dict) else {}, tombstones=tombstones) for row in rows)
            visible = sum(1 for row in rows if isinstance(row, dict) and tier_at_least(get_tier(row, tombstones=tombstones), "T1"))
            metrics["faiss_total"] += len(rows)
            metrics["faiss_visible"] += visible
            metrics["faiss_tiers"].update(counts)
            store_name = meta_path.name.replace("_meta.json", "")
            store_totals[store_name].update(counts)
            metrics["faiss_rows"].append([
                store_name,
                len(rows),
                counts.get("T0", 0),
                counts.get("T1", 0),
                counts.get("T2", 0),
                counts.get("TX", 0),
                meta_path.name,
            ])

        obras_root = repo_root / "DADOS-OBRAS"
        manifests = sorted(obras_root.glob("*/obra_rag/manifest.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0)
        metrics["obra_rag_snapshots"] = len(manifests)
        if manifests:
            metrics["latest_obra_rag"] = manifests[-1].parent.parent.name
            metrics["db_rows"].append([
                "obra_rag snapshots",
                len(manifests),
                "OK",
                f"ultimo: {metrics['latest_obra_rag']}",
            ])

        metrics["training_pipeline_rows"] = [
            [
                "CROP - recorte",
                "Recorte aprovado por humano",
                "Detector/perfil de recorte por classe, layer e pavimento",
                "CROP-T1: janela correta, classe correta, contexto correto",
                "crop_learning_events; exemplos visuais locais",
                "Nao validar F5/N2 nem N4 no clique de recorte",
            ],
            [
                "A - N2 -> N4",
                "F5/N2 validado + visual STOG humano",
                "motor_reverso_* + gerar_*_dxf_stog",
                "N4 visual/semantico passa no Comparison Engine",
                "training_events; FAISS/Chroma so T1+; domain_knowledge",
                "Nao copiar resultado para N1/N3; nao promover T0",
            ],
            [
                "B - N2 <-> N1",
                "N2/F5 como professor externo",
                "Structural Analyzer + conversor N1->ficha robo",
                "F7/N1 converge para F5/N2 por campo/geometria",
                "transformation_rules; eventos por role; notas humanas",
                "Nao sobrescrever validacao humana; nao usar N2 como input do N3",
            ],
            [
                "C - N1 -> N3",
                "N4 validado como juiz externo",
                "Conversor N1->N3 + robos por classe",
                "N3 ~= N4 sem vazamento de gabarito",
                "pares N3/N4 validados; scores; regressao visual",
                "Nao alimentar N3 com campos de N2/N4",
            ],
            [
                "Notas humanas",
                "Atencoes, rejeicoes e decisoes do operador",
                "Fila de revisao semantica e calibradores",
                "Nota vira regra so apos consenso/validacao",
                "item_attention_notes; domain_knowledge; pendencias",
                "Nao tratar nota solta como verdade global",
            ],
        ]

        def has_doc(*needles):
            names = [path.name.upper() for path in arete_docs]
            return any(all(needle.upper() in name for needle in needles) for name in names)

        def matching_scripts(*needles):
            matches = []
            for path in loop_scripts:
                name = path.name.lower()
                if all(needle.lower() in name for needle in needles):
                    matches.append(path.name)
            return matches

        class_rows = [
            [
                "PIL",
                "CIMA / GRADES / ABCD",
                "MASTERPLAN-ARETE-PILAR.md + SEMANTICA-PILAR-NOVA + testes Arete",
                "; ".join(matching_scripts("pil")[:4]) or "scripts/arete/test_n2_n4_abcd.py",
                "Loop existe em testes/scripts, mas precisa documento canônico A/B/C",
                "Validar gates por campo com T1 humano e comparar N3 vs N4 sem vazamento",
            ],
            [
                "LAJ",
                "Painel / outlines / aberturas / cotas",
                "MASTERPLAN-ARETE-LAJE.md" if has_doc("ARETE", "LAJE") else "Doc Arete LAJ nao encontrado",
                "; ".join((matching_scripts("laj") + matching_scripts("lj"))[:5]) or "laje_loop_runner.py",
                "A/B/C documentado: N2->N4, N2<->N1, N1->N3",
                "Rodar ciclos com T1+ e comparar N3 vs N4 sem vazamento",
            ],
            [
                "LV",
                "VC / lado A / lado B",
                "MASTERPLAN-ARETE-LATERAL-VIGA.md + MASTERPLAN-LOOP-LV-N2-VISION-N4.md",
                "; ".join(matching_scripts("lv")[:5]) or "lv_*_loop_runner.py",
                "A/B/C documentado com subdivisoes visuais",
                "Fechar equivalencia de vocabulario N1<->N2 por lado",
            ],
            [
                "FV",
                "Fundo / seções / eixo visual",
                "MASTERPLAN-ARETE-FUNDO-VIGA.md" if has_doc("ARETE", "FUNDO", "VIGA") else "Doc Arete FV nao encontrado",
                "; ".join(matching_scripts("fv")[:5]) or "fv_loop_runner.py",
                "A/B/C documentado; render/loop existem",
                "Validar N4 contra N2 antes de usar como juiz do N3",
            ],
            [
                "Nova classe",
                "Definir no classe_registry",
                "docs/ENCICLOPEDIA-SCHEMA.md + MASTERPLAN-ARETE-{CLASSE}.md",
                "motor_reverso_{classe}.py; gerar_{classe}_dxf_stog.py; loop_runner",
                "Precisa nascer com CROP, A, B e C separados",
                "Criar seed T1, gates e notas humanas antes de generalizar",
            ],
        ]
        metrics["training_class_rows"] = class_rows

        pending = []

        def add_pending(priority, area, finding, action):
            pending.append([priority, area, finding, action])
            metrics["pending_counts"][priority] += 1

        encyclopedia_by_class = {
            str(row[0]).upper(): row for row in metrics["encyclopedia_rows"]
        }
        for classe in sorted(canonical_classes):
            row = encyclopedia_by_class.get(classe)
            if row is None:
                add_pending(
                    "ALTA",
                    f"Classe {classe}",
                    "Nenhuma fonte materializada na Enciclopedia.",
                    "Revisar mapeamento N1/N2 e regras antes de criar conhecimento.",
                )
                continue
            if int(row[4]) + int(row[5]) == 0:
                add_pending(
                    "ALTA",
                    f"Classe {classe}",
                    "Nenhuma instancia T1/T2 validada por humano.",
                    "Validar casos dourados no fluxo operacional; nao fazer bulk.",
                )
            if int(row[7]) == 0:
                add_pending(
                    "MEDIA",
                    f"Classe {classe}",
                    "Sem regras em semantic_rag_kb.",
                    "Harmonizar domain_knowledge com o dono antes de publicar regras.",
                )
            coverage = int(str(row[9]).split("/", 1)[0])
            if coverage < 8:
                add_pending(
                    "INFO",
                    f"Classe {classe}",
                    f"{8 - coverage} das 8 dimensoes ainda sem evidencia materializada.",
                    "Completar com exemplos reais; nao inferir conteudo ausente.",
                )

        for classe in sorted(set(encyclopedia_by_class) - canonical_classes):
            add_pending(
                "MEDIA",
                "Taxonomia",
                f"Classe/categoria '{classe}' nao esta no registro canonico PIL/LV/FV/LAJ.",
                "Decidir se e alias, subclasse ou nova classe antes de consolidar.",
            )

        if metrics["registry_error"]:
            add_pending(
                "ALTA",
                "Registro de classes",
                f"classe_registry indisponivel ou invalido: {metrics['registry_error']}",
                "Corrigir o registro antes de consolidar aliases ou novas classes.",
            )

        legacy_t0 = metrics["faiss_tiers"].get("T0", 0)
        if legacy_t0:
            add_pending(
                "MEDIA",
                "Memoria Vetorial",
                f"{legacy_t0} metadados FAISS legados estao em T0.",
                "Manter ocultos de T1+; revisar individualmente quando necessario.",
            )
        if metrics["semantic_total"] == 0:
            add_pending(
                "ALTA",
                "Semantica",
                "semantic_rag_kb esta vazia.",
                "Popular somente regras confirmadas do domain_knowledge.",
            )
        if not manifests:
            add_pending(
                "INFO",
                "RAG por obra",
                "Nenhum snapshot local foi encontrado.",
                "Gerar ao iniciar uma obra, sem promocao global.",
            )

        severity_order = {"ALTA": 0, "MEDIA": 1, "INFO": 2}
        metrics["pending_rows"] = sorted(
            pending,
            key=lambda row: (severity_order.get(row[0], 9), row[1], row[2]),
        )

        return metrics

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

            # Masterplan OBRAS DRIVE (Fase 1): cabeçalho de categoria (não
            # selecionável, igual aos cabeçalhos de grupo do Diagnostic Hub) —
            # as obras de verdade são inseridas ABAIXO dele, cada uma como um
            # item normal, clicável igual uma obra local. Carregamento adiado
            # (QTimer) pra não travar a sidebar com I/O de rede síncrono.
            header_drive = QListWidgetItem("☁️ OBRAS DRIVE")
            header_drive.setFlags(header_drive.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
            self.list_works.addItem(header_drive)
            from PySide6.QtCore import QTimer as _QT_DRIVE

            _QT_DRIVE.singleShot(0, lambda h=header_drive: self._carregar_obras_drive_na_sidebar(h))

        except Exception as e:
            logging.error(f"Erro ao carregar obras: {e}")

        self.list_works.setCurrentRow(-1)
        self.list_works.blockSignals(False)

    def _carregar_obras_drive_na_sidebar(self, header_item: QListWidgetItem):
        """Busca as obras do portal (Masterplan OBRAS DRIVE) e insere, logo
        abaixo do cabeçalho "☁️ OBRAS DRIVE", 1 sub-cabeçalho por membro
        (dono vê todas as obras de todos — cada membro na sua própria
        sub-lista) + 1 item clicável por obra, no mesmo nível visual/funcional
        de uma obra local. Falha de rede/credenciais vira 1 item de aviso, não
        trava a sidebar."""
        try:
            from src.core.drive_client import obter_cliente_padrao

            obras = obter_cliente_padrao().listar_obras()
        except Exception as e:
            row = self.list_works.row(header_item) + 1
            aviso = QListWidgetItem(f"⚠ Portal indisponível: {e}")
            aviso.setFlags(aviso.flags() & ~Qt.ItemIsSelectable)
            self.list_works.insertItem(row, aviso)
            return

        grupos: dict[str, list[dict]] = {}
        for o in obras:
            membro = o.get("membro_nome") or o.get("membro_login") or "—"
            grupos.setdefault(membro, []).append(o)

        row = self.list_works.row(header_item) + 1
        for membro in sorted(grupos.keys()):
            sub = QListWidgetItem(f"    👤 {membro}")
            sub.setFlags(sub.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
            self.list_works.insertItem(row, sub)
            row += 1
            for o in grupos[membro]:
                item = QListWidgetItem(f"    ☁️ {o.get('nome', '(sem nome)')}")
                item.setData(Qt.UserRole, {"tipo": "drive", "obra": o})
                item.setToolTip(f"Obra do portal web — membro: {membro}")
                self.list_works.insertItem(row, item)
                row += 1

    def _filter_works_list(self, text):
        """Filtra visualmente a lista de obras."""
        for i in range(self.list_works.count()):
            item = self.list_works.item(i)
            # Agora filtra todos os itens
            show = text.lower() in item.text().lower()
            item.setHidden(not show)

    def _atualizar_code_publico_obra(self, obra_nome):
        """Busca (em background, nunca bloqueia a UI) o código público
        (App de Consulta) da obra Drive selecionada — some/oculta pra obras
        locais, ainda não publicadas, ou se o portal estiver offline
        [2026-07-13]. Regra de integridade: falha aqui NUNCA aparece pro
        usuário nem trava a navegação — é só um badge informativo a mais."""
        self.lbl_code_publico_obra.setVisible(False)
        self.lbl_code_publico_obra.setText("")

        if not obra_nome or not self.db.obra_e_drive(obra_nome):
            return
        portal_obra_id = self.db.obter_portal_obra_id(obra_nome)
        if not portal_obra_id:
            return

        from PySide6.QtCore import QThread
        from src.ui.workers.code_publico_worker import CodePublicoWorker

        thread = QThread()
        worker = CodePublicoWorker(portal_obra_id)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        if not hasattr(self, "_code_publico_threads"):
            self._code_publico_threads = []
        self._code_publico_threads.append(thread)

        def _limpar():
            if thread in self._code_publico_threads:
                self._code_publico_threads.remove(thread)

        def _on_code(code, _obra=obra_nome):
            # Obra pode ter sido trocada enquanto a busca rodava — nao aplica
            # um resultado tardio na obra errada.
            if code and self.current_work_name == _obra:
                self.lbl_code_publico_obra.setText(f"📱 Código de Obra: {code}")
                self.lbl_code_publico_obra.setVisible(True)
            thread.quit()

        def _on_error(_msg):
            thread.quit()

        worker.finished.connect(_on_code)
        worker.error.connect(_on_error)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(_limpar)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def load_projects(self):
        """Carrega os pavimentos filtrando pela obra selecionada usando Cards.

        Estratégia de performance:
          - Fase A (síncrona, <1ms): atualiza header/botões/estado
          - Fase B (QTimer 0ms): carrega cards + combos (leve)
          - Fase C (QTimer 50ms): badge + triagem (I/O leve diferido)
          - Fase D (QTimer 100ms): phase_tabs (I/O pesado, invisível ao user)
        """
        from PySide6.QtCore import QTimer as _QT

        # ── Fase A: UI imediata ─────────────────────────────────────────────
        for i in reversed(range(self.cards_layout.count())):
            widget = self.cards_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        selected_item = self.list_works.currentItem()
        filter_work = selected_item.data(Qt.UserRole) if selected_item else None

        if isinstance(filter_work, dict) and filter_work.get("tipo") == "drive":
            # Masterplan OBRAS DRIVE (Fase 1): obra do portal web selecionada.
            # Espelha TODA a obra (brutos + itens de recorte, sem baixar DXF
            # nenhum ainda — só metadados) e converte pro mesmo formato de
            # `filter_work` de uma obra local (string com o nome do espelho),
            # pra todo o resto desta função (cards/triagem/phase_tabs) tratar
            # exatamente igual — a obra Drive já espelhada É uma obra local
            # a partir daqui.
            try:
                from src.core.drive_client import obter_cliente_padrao
                from src.core.drive_mirror import espelhar_obra_completa_drive

                filter_work = espelhar_obra_completa_drive(
                    self.db, obter_cliente_padrao(), filter_work["obra"]
                )
            except Exception as e:
                logging.error(f"Erro ao espelhar obra Drive: {e}")
                self.lbl_selected_work.setText(f"⚠ Falha ao carregar obra do Drive: {e}")
                return

        self.current_work_name = filter_work if filter_work != "__NO_WORK__" else None
        if self.current_work_name:
            _QT.singleShot(
                150,
                lambda obra=self.current_work_name: self._ensure_local_rag_snapshot(obra),
            )

        has_work = bool(filter_work) and filter_work != "__NO_WORK__"
        self.btn_delete_work.setVisible(has_work)
        self.btn_sync_work.setVisible(has_work)

        display_text = (
            selected_item.text().strip().replace("📁 ", "").replace("🏢 ", "").replace("☁️ ", "")
            if selected_item else "Selecione uma Obra"
        )
        self.lbl_selected_work.setText(display_text)
        self._atualizar_code_publico_obra(self.current_work_name)

        self.load_work_metadata(filter_work)

        # ── Fase B: cards + combos (diferido, roda antes do próximo repaint) ─
        def _load_cards():
            try:
                projects = self.db.get_projects()
            except Exception as e:
                logging.error(f"load_projects failed: {e}")
                return

            filtered_projects = []
            for p in projects:
                p_work = p.get('work_name') or ""
                if filter_work == "__NO_WORK__":
                    if p_work: continue
                elif filter_work:
                    if p_work != filter_work: continue
                filtered_projects.append(p)

            for combo_name in ['cmb_pavements_extraction', 'cmb_pavements_recognition', 'cmb_pavements_validation']:
                if hasattr(self, combo_name):
                    cmb = getattr(self, combo_name)
                    cmb.blockSignals(True)
                    cmb.clear()
                    icon = "✅" if combo_name == 'cmb_pavements_validation' else ("🤖" if combo_name == 'cmb_pavements_recognition' else "🏗️")
                    for p in filtered_projects:
                        cmb.addItem(f"{icon} {p.get('name', 'N/A')}", p)
                    cmb.blockSignals(False)

            # Ordenar por pavement_name (canônico) → fallback por name
            def _pav_sort_key(p):
                pn = p.get('pavement_name') or p.get('name') or ''
                import re
                m = re.search(r'(\d+)', pn)
                return (int(m.group(1)) if m else 9999, pn.lower())

            filtered_projects = sorted(filtered_projects, key=_pav_sort_key)

            # Atualizar contador no label
            if hasattr(self, '_lbl_pav_count'):
                self._lbl_pav_count.setText(
                    f"Pavimentos Limpos — {len(filtered_projects)} pavimento(s)"
                )

            # Limpar layout VBox antes de popular
            while self.cards_layout.count():
                item = self.cards_layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)

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
                self.cards_layout.addWidget(card)

            self.cards_layout.addStretch()

            # Fase D: phase_tabs pesado — deferir mais para não bloquear render dos cards
            if first_project:
                _QT.singleShot(100, lambda p=first_project: self.on_project_card_clicked(p))
            else:
                self.current_project_id = None
                # Sem cards (comum pra obra Drive recém-espelhada: ainda não
                # tem pavimento processado no SA) — reseta o breadcrumb, senão
                # fica preso mostrando o último pavimento aberto antes de
                # trocar de obra, confundindo com dado de obra errada.
                self.breadcrumbs.set_path(
                    "Projetos", self.current_work_name or "—",
                    "Nenhum pavimento processado — veja a aba Triagem"
                )
                _QT.singleShot(100, self._refresh_phase_tabs)

        _QT.singleShot(0, _load_cards)

        # ── Fase C: badge (scan disco) + triagem (DB) — diferidos ───────────
        _QT.singleShot(50, self._refresh_index_badge)
        _QT.singleShot(80, self._refresh_rag_badge)
        if hasattr(self, '_triagem_list_layout'):
            _QT.singleShot(50, self._refresh_triagem_panel)
        _QT.singleShot(80, self._refresh_preprocess_panel)
        _QT.singleShot(80, self._refresh_projetos_finalizados_panel)
        _QT.singleShot(80, self._refresh_detalhamentos_panel)

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

        # Fix performance: defer phase tab rebuild para não travar o repaint do card
        QTimer.singleShot(0, self._refresh_phase_tabs)

    def _update_docs_tab_list(self, docs):
        """Método mantido para compatibilidade - agora redireciona para _refresh_phase_tabs()"""
        # Este método é chamado por código legado, mas agora usamos _refresh_phase_tabs()
        self._refresh_phase_tabs()

    def upload_document(self):
        if not self.current_project_id:
            QMessageBox.warning(self, "Aviso", "Selecione um projeto.")
            return
            
        dialog = DocumentUploadDialog(class_name="Geral", parent=self)
        if dialog.exec():
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

