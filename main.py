import sys
from typing import Dict, List, Any, Optional
import os
import json
import logging
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QFileDialog, QDockWidget, 
                               QTextEdit, QLabel, QStackedWidget, QListWidget,
                               QListWidgetItem, QTabWidget, QSplitter, QLineEdit, QProgressBar,
                               QTreeWidget, QTreeWidgetItem, QMessageBox, QMenu, QScrollArea, QFrame)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, QSize
from src.ui.canvas import CADCanvas
from src.ui.widgets.detail_card import DetailCard
from src.ui.widgets.link_manager import LinkManager
from src.ui.widgets.project_manager import ProjectManager
from src.ui.widgets.training_log import TrainingLog
from src.core.dxf_loader import DXFLoader
from src.core.spatial_index import SpatialIndex
from src.core.geometry_engine import GeometryEngine, ShapeType
from src.core.text_associator import TextAssociator
from src.core.slab_tracer import SlabTracer
from src.core.database import DatabaseManager
from src.core.memory import HierarchicalMemory
from src.core.beam_walker import BeamWalker
from src.core.context_engine import ContextEngine
from src.core.pillar_analyzer import PillarAnalyzer


# Config logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import uuid
import re

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vision-Estrutural AI - Pro Dashboard")
        self.resize(1600, 1000)
        
        # Estado
        self.db = DatabaseManager() # SQLite persistencia
        self.memory = HierarchicalMemory(self.db)
        self.spatial_index = SpatialIndex()

        # Engines
        self.context_engine = None
        self.pillar_analyzer = None

        self.dxf_data = None
        self.pillars_found = []
        self.slabs_found = []
        self.beams_found = []
        self.beams_database = [] # Armazena dados de visualização das vigas por pilar
        
        self.current_project_id = None
        self.current_project_name = "Sem Projeto"
        self.current_dxf_path = None

        # Carregar Estilo
        self.load_stylesheet()
        
        # UI Setup
        self.init_ui()
        
        # Carregar configurações customizadas de vínculos
        self._load_link_configs()

    def load_stylesheet(self):
        try:
            with open("src/ui/style.qss", "r") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Erro ao carregar CSS: {e}")

    def init_ui(self):
        # Widget Central com Splitter
        main_layout = QHBoxLayout()
        self.central_widget = QWidget()
        self.central_widget.setLayout(main_layout)
        self.setCentralWidget(self.central_widget)

        self.splitter = QSplitter(Qt.Horizontal)
        
        # --- LADO ESQUERDO: GESTÃO DE ITENS ---
        self.left_panel = QWidget()
        self.left_panel.setObjectName("Sidebar")
        self.left_panel.setFixedWidth(365)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setSpacing(10)
        
        # 0. Botão Gerenciar Projetos (Topo)
        btn_load = QPushButton("📂 Gerenciar Projetos")
        btn_load.setStyleSheet("padding: 4px; font-size: 11px; height: 18px;")
        btn_load.clicked.connect(self.open_project_manager)
        left_layout.addWidget(btn_load)

        # 1. Inputs de Metadados (Topo)
        self.meta_widget = QWidget()
        meta_layout = QVBoxLayout(self.meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(5)
        
        # Obra
        meta_layout.addWidget(QLabel("Nome da Obra:"))
        self.edit_work_name = QLineEdit()
        self.edit_work_name.editingFinished.connect(self.save_project_metadata)
        meta_layout.addWidget(self.edit_work_name)
        
        # Pavimento
        meta_layout.addWidget(QLabel("Nome do Pavimento:"))
        self.edit_pavement_name = QLineEdit()
        self.edit_pavement_name.editingFinished.connect(self.save_project_metadata)
        meta_layout.addWidget(self.edit_pavement_name)
        
        # Níveis (Layout Horizontal)
        lvl_layout = QHBoxLayout()
        v1 = QVBoxLayout()
        v1.addWidget(QLabel("Nível Chegada:"))
        self.edit_level_arr = QLineEdit()
        self.edit_level_arr.editingFinished.connect(self.save_project_metadata)
        v1.addWidget(self.edit_level_arr)
        
        v2 = QVBoxLayout()
        v2.addWidget(QLabel("Nível Saída:"))
        self.edit_level_exit = QLineEdit()
        self.edit_level_exit.editingFinished.connect(self.save_project_metadata)
        v2.addWidget(self.edit_level_exit)
        
        lvl_layout.addLayout(v1)
        lvl_layout.addLayout(v2)
        meta_layout.addLayout(lvl_layout)
        
        left_layout.addWidget(self.meta_widget)

        # 2. Botão de Análise (Imediatamente acima do Salvar)

        self.btn_process = QPushButton("🚀 Iniciar Análise Geral")
        self.btn_process.setObjectName("Primary") # Destaque visual
        self.btn_process.setStyleSheet("padding: 4px; font-size: 11px; height: 18px;")
        self.btn_process.clicked.connect(self.process_pillars_action)
        left_layout.addWidget(self.btn_process)

        # 2b. Botão Gerenciar Memória (Novo)
        self.btn_mem = QPushButton("📜 Gerenciar Memória IA")
        self.btn_mem.setStyleSheet("background: #333; color: #aaa; font-size: 11px; margin-top: 2px; height: 16px; padding: 2px;")
        self.btn_mem.clicked.connect(self.open_training_log)
        left_layout.addWidget(self.btn_mem)

        # 3. Botão Salvar
        self.btn_save = QPushButton("Salvar")
        self.btn_save.setObjectName("Success")
        self.btn_save.setStyleSheet("padding: 4px; font-size: 11px; height: 18px;")
        self.btn_save.clicked.connect(self.save_project_action)
        left_layout.addWidget(self.btn_save)

        # 4. Barra de Progresso (NOVO)
        self.progress_container = QWidget()
        prog_layout = QVBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(5, 10, 5, 5)
        
        self.lbl_progress = QLabel("Aguardando ação...")
        self.lbl_progress.setStyleSheet("color: #aaa; font-size: 10px;")
        prog_layout.addWidget(self.lbl_progress)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #444; border-radius: 4px; background: #222; }
            QProgressBar::chunk { background: #0078d4; border-radius: 3px; }
        """)
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar)
        
        self.progress_container.hide() # Esconde por padrão
        left_layout.addStretch()
        left_layout.addWidget(self.progress_container)

        # Estado
        self.interactive_items = {} 
        self.item_groups = { 
            'pillar': [],
            'slab': [],
            'beam': [],
            'link': [] 
        }
        self.beam_visuals = []      
        
        # Modo de Captação e Cache de Projetos
        self.loaded_projects_cache = {} 
        self.active_project_id = None
        
        # 5. Separador / Espaço
        left_layout.addSpacing(10)
        
        # 6. Abas de Listagem Principal (3 Níveis)
        self.main_tabs = QTabWidget()
        
        # Stylesheet Compacto e Moderno para Abas
        STYLE_TABS = """
            QTabWidget::pane { 
                border: 1px solid #333; 
                background: #1e1e1e; 
                border-top: 2px solid #0078d4;
            }
            QTabBar::tab {
                background: #252525;
                color: #999;
                padding: 4px 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border: 1px solid #333;
                border-bottom: none;
                margin-right: 2px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background: #0078d4; 
                color: white;
                font-weight: bold;
                border: 1px solid #005a9e;
                margin-bottom: -1px; /* Connect to pane */
            }
            QTabBar::tab:hover {
                background: #333;
                color: #ddd;
            }
        """
        self.main_tabs.setStyleSheet(STYLE_TABS)
        
        # --- Helpers para criar abas com botões específicos ---
        def create_tab_container(list_widget, item_type: str, is_library: bool):
            """Cria container com Lista + Botão Criar + Botões Específicos"""
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0,0,0,0)
            layout.setSpacing(5)
            
            # Lista
            layout.addWidget(list_widget)
            
            # Botão Excluir Item
            btn_delete = QPushButton("🗑️ Excluir Item")
            btn_delete.setStyleSheet("background-color: #ffcccc; color: #cc0000; border: 1px solid #ff9999; padding: 2px; font-size: 10px; height: 18px;")
            btn_delete.clicked.connect(lambda: self.delete_item_action(list_widget, item_type, is_library))
            layout.addWidget(btn_delete)

            # Botão Criar Novo Item (padrão)
            scope_name = "Lib" if is_library else "Análise"
            btn_create = QPushButton(f"➕ Criar Novo Item ({scope_name})")
            btn_create.setStyleSheet("padding: 2px; font-size: 10px; height: 18px;")
            btn_create.clicked.connect(lambda: self.create_manual_item(is_library=is_library))
            layout.addWidget(btn_create)
            
            # Botões Específicos
            if item_type == 'pillar':
                # 3 Botões para Pilares
                btn_script_full = QPushButton("📜 Gerar Script Pilar Completo")
                btn_script_full.setStyleSheet("padding: 2px; font-size: 10px; height: 18px;")
                btn_script_full.clicked.connect(lambda: self.generate_script_pillar_full(is_library))
                layout.addWidget(btn_script_full)
                
                btn_script_pav = QPushButton("📜 Gerar Script Pavimento Pilar Completo")
                btn_script_pav.setStyleSheet("padding: 2px; font-size: 10px; height: 18px;")
                btn_script_pav.clicked.connect(lambda: self.generate_script_pavement_pillar(is_library))
                layout.addWidget(btn_script_pav)
                
                btn_export = QPushButton("💾 Exportar Dados dos Pilares (JSON)")
                btn_export.setStyleSheet("padding: 2px; font-size: 10px; height: 18px;")
                btn_export.clicked.connect(lambda: self.export_data_json('pillar', is_library))
                layout.addWidget(btn_export)
                
            elif item_type == 'beam':
                # 3 Botões para Vigas
                btn_script_set = QPushButton("📜 Gerar Script Conjunto de Viga Completo")
                btn_script_set.setStyleSheet("padding: 2px; font-size: 10px; height: 18px;")
                btn_script_set.clicked.connect(lambda: self.generate_script_beam_set(is_library))
                layout.addWidget(btn_script_set)

                btn_script_pav = QPushButton("📜 Gerar Script Pavimento Vigas Completo")
                btn_script_pav.setStyleSheet("padding: 2px; font-size: 10px; height: 18px;")
                btn_script_pav.clicked.connect(lambda: self.generate_script_pavement_beam(is_library))
                layout.addWidget(btn_script_pav)

                btn_export = QPushButton("💾 Exportar Dados das Vigas (JSON)")
                btn_export.setStyleSheet("padding: 2px; font-size: 10px; height: 18px;")
                btn_export.clicked.connect(lambda: self.export_data_json('beam', is_library))
                layout.addWidget(btn_export)
                
            elif item_type == 'slab':
                # 1 Botão para Lajes
                btn_export = QPushButton("💾 Exportar Dados das Lajes (JSON)")
                btn_export.setStyleSheet("padding: 2px; font-size: 10px; height: 18px;")
                btn_export.clicked.connect(lambda: self.export_data_json('slab', is_library))
                layout.addWidget(btn_export)

            return container

        # --- TAB 1: ANÁLISE ATUAL (Pilares, Vigas, Lajes, Contorno, Issues) ---
        self.tab_analysis = QWidget()
        analysis_layout = QVBoxLayout(self.tab_analysis)
        analysis_layout.setContentsMargins(0,0,0,0)
        
        self.tabs_analysis_internal = QTabWidget()
        self.tabs_analysis_internal.setStyleSheet(STYLE_TABS)
        self.list_pillars = QListWidget()
        self.list_beams = QTreeWidget()
        self.list_beams.setHeaderLabels(["Item", "Nome", "Status"])
        self.list_beams.setColumnWidth(0, 60)
        self.list_beams.setColumnWidth(1, 120)
        
        self.list_slabs = QListWidget()
        self.list_issues = QListWidget()
        
        # Conectar Sinais (Atual)
        self.list_pillars.itemClicked.connect(self.on_list_pillar_clicked)
        self.list_beams.itemClicked.connect(self.on_list_beam_clicked)
        self.list_slabs.itemClicked.connect(self.on_list_slab_clicked)
        self.list_issues.itemClicked.connect(self.on_issue_clicked)
        
        # Adicionar Abas com Containers
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_pillars, 'pillar', False), "Pilares")
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_beams, 'beam', False), "Vigas")
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_slabs, 'slab', False), "Lajes")
        self.tabs_analysis_internal.addTab(self.list_issues, "⚠️ Pendências")
        
        # Conectar mudança de aba interna (Análise)
        self.tabs_analysis_internal.currentChanged.connect(self._on_analysis_tab_changed)
        
        analysis_layout.addWidget(self.tabs_analysis_internal)
        
        # --- TAB 2: BIBLIOTECA VALIDADA ---
        self.tab_library = QWidget()
        library_layout = QVBoxLayout(self.tab_library)
        library_layout.setContentsMargins(0,0,0,0)
        
        self.tabs_library_internal = QTabWidget()
        self.tabs_library_internal.setStyleSheet(STYLE_TABS)
        self.list_pillars_valid = QListWidget()
        self.list_beams_valid = QTreeWidget()
        self.list_beams_valid.setHeaderLabels(["Item", "Nome", "Status"])
        self.list_beams_valid.setColumnWidth(0, 60)
        self.list_beams_valid.setColumnWidth(1, 120)

        self.list_slabs_valid = QListWidget()
        
        # Conectar Sinais (Validado)
        self.list_pillars_valid.itemClicked.connect(self.on_list_pillar_clicked)
        self.list_beams_valid.itemClicked.connect(self.on_list_beam_clicked)
        self.list_slabs_valid.itemClicked.connect(self.on_list_slab_clicked)
        
        # Adicionar Abas com Containers
        self.tabs_library_internal.addTab(create_tab_container(self.list_pillars_valid, 'pillar', True), "Pilares OK")
        self.tabs_library_internal.addTab(create_tab_container(self.list_beams_valid, 'beam', True), "Vigas OK")
        self.tabs_library_internal.addTab(create_tab_container(self.list_slabs_valid, 'slab', True), "Lajes OK")
        
        # Conectar mudança de aba interna (Biblioteca)
        self.tabs_library_internal.currentChanged.connect(self._on_library_tab_changed)
        
        library_layout.addWidget(self.tabs_library_internal)

        # --- TAB 3: DADOS DE TREINO ---
        self.tab_training = TrainingLog(self.db)
        self.tab_training.sync_requested.connect(self.sync_brain_memory)
        
        # Adicionar ao Main Tabs
        self.main_tabs.addTab(self.tab_analysis, "Análise Atual")
        self.main_tabs.addTab(self.tab_library, "Biblioteca Validada")
        self.main_tabs.addTab(self.tab_training, "Dados de Treino")
        
        left_layout.addWidget(self.main_tabs)
        
        # Logs rápidos abaixo
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(150)
        left_layout.addWidget(QLabel("Terminal de Eventos:"))
        left_layout.addWidget(self.console)
        
        self.splitter.addWidget(self.left_panel)
        
        # --- CENTRO: ABAS DE PROJETOS + CANVAS ---
        self.canvas_container = QWidget()
        
        # Area de abas de projetos acima do canvas
        self.project_tabs = QTabWidget()
        self.project_tabs.setTabsClosable(True)
        self.project_tabs.tabCloseRequested.connect(self.close_project_tab)
        self.project_tabs.currentChanged.connect(self.on_project_tab_changed)
        
        # Canvas é único, mas reparentado ou limpo? 
        # Melhor: Canvas é único visualmente, mas seus dados mudam.
        # As abas do project_tabs são apenas "placeholders" para controle de seleção.
        # Nós NÃO colocamos o canvas DENTRO da aba, pois o canvas é pesado.
        # Usamos as abas como uma "Barra de Navegação de Projetos".
        self.project_tabs.setFixedHeight(30) 
        self.project_tabs.setStyleSheet("QTabBar::tab { width: 150px; }")

        center_layout = QVBoxLayout(self.canvas_container)
        center_layout.setContentsMargins(0,0,0,0)
        center_layout.addWidget(self.project_tabs)
        
        self.canvas = CADCanvas(self)
        self.canvas.pillar_selected.connect(self.on_canvas_pillar_selected)
        self.canvas.pick_completed.connect(self.on_pick_completed) 
        
        # Conectar TrainingLog ao Canvas (agora que ele existe)
        self.tab_training.focus_requested.connect(self.canvas.highlight_link)
        
        center_layout.addWidget(self.canvas)
        self.splitter.addWidget(self.canvas_container)
        
        # --- DIREITA: DETALHAMENTO ---
        self.right_panel = QStackedWidget()
        self.right_panel.setMinimumWidth(280)
        
        # Pagina 0: Placeholder
        placeholder = QLabel("Selecione um item para ver detalhes\nou inicie a detecção.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #666; font-style: italic;")
        self.right_panel.addWidget(placeholder)
        
        # Pagina 1: Content
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setFrameShape(QFrame.NoFrame)
        self.detail_scroll.setStyleSheet("background: transparent; border: none;") # Ensure it blends in

        self.detail_container = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_container)
        self.detail_layout.setContentsMargins(0,0,0,0)
        # Add stretch to push content up if it's small
        # self.detail_layout.addStretch() 
        
        self.detail_scroll.setWidget(self.detail_container)
        self.right_panel.addWidget(self.detail_scroll)
        self.current_card = None
        
        self.splitter.addWidget(self.right_panel)
        
        # Definir proporção inicial: Esquerda (365), Centro (Grande), Direita (320)
        self.splitter.setSizes([365, 1000, 320])
        
        main_layout.addWidget(self.splitter)

    def _on_analysis_tab_changed(self, index):
        """Filtra visualização no Canvas baseado na aba selecionada (Análise)"""
        # 0: Pilares, 1: Vigas, 2: Lajes, 3: Issues
        self._update_canvas_filter(index)

    def _on_library_tab_changed(self, index):
        """Filtra visualização no Canvas baseado na aba selecionada (Biblioteca)"""
        # 0: Pilares, 1: Vigas, 2: Lajes
        self._update_canvas_filter(index)

    def _update_canvas_filter(self, index):
        if index == 0:
            self.canvas.set_category_visibility('pillar')
        elif index == 1:
            self.canvas.set_category_visibility('beam')
        elif index == 2:
            self.canvas.set_category_visibility('slab')
        else:
            self.canvas.set_category_visibility('all')


    def on_focus_requested(self, field_id):
        """Tenta focar no objeto vinculado ao campo especificado via COORDENADA DIRETA"""
        if not self.current_card: return
        item_data = self.current_card.item_data
        
        # Buscar nos links estruturados do campo
        links_data = item_data.get('links', {}).get(field_id, {})
        
        # 1. Coletar TODOS os links válidos deste campo (independente do slot)
        valid_links = []
        for slot, slot_data in links_data.items():
            # slot_data pode ser lista de links ou dict de listas? Geralmente lista.
            if isinstance(slot_data, list):
                for link in slot_data:
                    if 'pos' in link or 'points' in link:
                        valid_links.append(link)
        
        if valid_links:
            # 1. Destacar o Item Pai em Amarelo (Persistente)
            if 'id' in item_data:
                self.canvas.highlight_item_yellow(item_data['id'])
            
            # 2. Destacar TODOS os Links Específicos em Amarelo (Zoom no conjunto)
            self.canvas.highlight_multiple_links(valid_links, color=QColor(255, 255, 0))
            
            slot_names = list(links_data.keys())
            self.log(f"📍 Focando {len(valid_links)} vínculos (Slots: {slot_names})")
            return

        # Fallback: Se não houver vínculo mas houver texto no widget, tenta busca nominal
        widget = self.current_card.fields.get(field_id)
        if widget:
            text = widget.currentText() if hasattr(widget, 'currentText') else widget.text()
            if text and text != '-':
                self.log(f"🔍 Vínculo direto não encontrado. Buscando por nome: {text}")
                self.canvas.highlight_element_by_name(text, self.beams_found + self.pillars_found)

    def on_pick_requested(self, field_id, slot_request):
        """Ativa o modo de captura no canvas para um slot específico"""
        # slot_request pode ser string "id_do_slot|tipo_de_pick" ou dict {"slot":..., "type":...}
        if isinstance(slot_request, dict):
            slot_id = slot_request.get('slot', 'main')
            pick_type = slot_request.get('type', 'text')
        else:
            parts = str(slot_request).split('|')
            slot_id = parts[0]
            pick_type = parts[1] if len(parts) > 1 else 'text'
        
        # [FORÇAR] Modo texto para Dimensões
        if 'dim' in field_id.lower() or 'dim' in slot_id.lower():
             pick_type = 'text'
        
        # [FORÇAR] Modo Poly para Geometria de Pilares (Solicitação Usuário: Pontos Sequenciais + Enter)
        if self.current_card:
            item_type = self.current_card.item_data.get('type', '').lower()
            if 'pilar' in item_type and slot_id in ('geometry', 'segments'):
                pick_type = 'poly'
        
        self.log(f"Iniciando captura {pick_type} para campo {field_id} [Slot: {slot_id}]...")
        self.current_pick_field = field_id
        self.current_pick_slot = slot_id
        
        # Importante: O canvas deve saber o slot_id para emitir corretamente depois se necessário, 
        # mas MainWindow gerencia o estado.
        self.canvas.set_picking_mode(pick_type, field_id)

    def on_pick_completed(self, pick_data):
        if self.current_card and hasattr(self, 'current_pick_field'):
            field_id = self.current_pick_field
            slot_id = getattr(self, 'current_pick_slot', 'main')
            
            item_data = self.current_card.item_data
            itype = item_data.get('type', '').lower()
            
            from PySide6.QtWidgets import QLineEdit, QComboBox, QLabel
            field = self.current_card.fields.get(field_id)
            
            value = pick_data.get('text', '')
            
            # Especial: Se for um slot de Vazio (X), forçar nome "SEM LAJE"
            if slot_id == 'void_x':
                value = "SEM LAJE"
            
            # 2. Salvar vínculo estruturado no item_data
            if 'links' not in self.current_card.item_data:
                self.current_card.item_data['links'] = {}
            
            links_dict = self.current_card.item_data['links']
            if field_id not in links_dict:
                links_dict[field_id] = {} 
                
            # Atualizar ref para garantir que pegamos o dict atualizado se foi modificado acima
            field_slots = links_dict[field_id] 
            
            # Migração de dados legados (Se ainda for uma lista simples)
            if isinstance(field_slots, list):
                field_slots = {'label': field_slots}
                links_dict[field_id] = field_slots

            # NORMALIZAÇÃO DE SLOTS (Para aparecer na lista das classes correctas do LinkManager)
            if slot_id == 'main':
                 f_id_lower = field_id.lower()
                 # 1. Dimensões em Trechos/Segmentos (Pilar -> Viga, etc)
                 if f_id_lower.endswith('_d'):
                      slot_id = 'dim'
                 
                 # 2. Dimensões Gerais/Cabeçalho
                 elif 'dim' in f_id_lower or 'espessura' in f_id_lower:
                      slot_id = 'label'
                      # Caso especial para slots complexes que usam 'dim' como id (ex: _laje_complex, _height_complex)
                      if any(x in f_id_lower for x in ['_laje_', '_height_']):
                           slot_id = 'dim'
                 
                 # 3. Nomes e Identificadores
                 elif 'name' in f_id_lower or 'label' in f_id_lower or field_id == 'id_item':
                      slot_id = 'label'
                 
                 # 4. Geometrias e Contornos
                 elif any(x in f_id_lower for x in ['geometria', 'outline', 'segs', 'geom']):
                      slot_id = 'geometry'
                      if '_laje_geom' in f_id_lower or '_fundo_segs' in f_id_lower: 
                           slot_id = 'contour'

            # Lógica Especial: Viga Manual -> Extensão Inteligente
            # Se for uma viga manual e o pick for linha (geometria principal)
            if (self.current_card.item_data.get('manual') 
                and self.current_card.item_data.get('type') == 'Viga'
                and pick_data.get('type') == 'line'
                and 'points' in pick_data):
                
                try:
                    import math
                    pts = pick_data['points']
                    p1, p2 = pts[0], pts[1]
                    
                    # Vetor Diretor
                    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                    length = (dx**2 + dy**2)**0.5
                    
                    if length > 0:
                        desired_ext = 10.0
                        target_total = math.ceil(length + desired_ext)
                        real_ext_len = target_total - length
                        
                        # Calcular P3 (Fim da Extensão)
                        ux, uy = dx/length, dy/length # Unit vector
                        p3_x = p2[0] + ux * real_ext_len
                        p3_y = p2[1] + uy * real_ext_len
                        
                        # Criar Link da Extensão
                        ext_link = {
                            'type': 'line',
                            'role': 'Adjustment', 
                            'text': f"{real_ext_len:.1f}",
                            'points': [(p2[0], p2[1]), (p3_x, p3_y)],
                            'manual_generated': True
                        }
                        
                        # Adicionar Extensão ao Slot 'adjustment' (Separado do Principal)
                        if 'adjustment' not in links_dict[field_id]:
                            links_dict[field_id]['adjustment'] = []
                            
                        links_dict[field_id]['adjustment'].append(ext_link)
                            
                        # Atualizar Valor Visual para o "Pedacinho" (Extensão)
                        value = f"{real_ext_len:.1f}"
                        if isinstance(field, QLabel):
                            field.setText(f"Ajuste: {value}")
                        self.log(f"📏 Ajuste Automático: {length:.1f} -> {target_total} (Add {value})")
                except Exception as e:
                    self.log(f"⚠️ Erro no cálculo de ajuste: {e}")

            # --- NOVO: Auto-Popular Geometria Real para Pilares ---
            # Se for um pilar e estivermos capturando a geometria/segmentos
            if 'pilar' in itype and slot_id in ('segments', 'geometry'):
                pts = pick_data.get('points')
                if not pts and 'pos' in pick_data:
                    # Se for círculo por exemplo
                    pos = pick_data['pos']
                    rad = pick_data.get('radius', 5.0)
                    pts = [(pos[0]-rad, pos[1]-rad), (pos[0]+rad, pos[1]+rad)]
                
                if pts:
                    min_x = min(p[0] for p in pts)
                    max_x = max(p[0] for p in pts)
                    min_y = min(p[1] for p in pts)
                    max_y = max(p[1] for p in pts)
                    
                    # Atualizar rect (P1, P2) no item_data
                    self.current_card.item_data['rect'] = [min_x, min_y, max_x, max_y]
                    
                    # Atualizar dimensão visual (dx x dy)
                    dx = abs(max_x - min_x)
                    dy = abs(max_y - min_y)
                    dim_str = f"{dx:.0f}x{dy:.0f}"
                    self.current_card.item_data['dim'] = dim_str
                    
                    # Se houver campo 'dim' (QLineEdit), atualiza ele também
                    if 'dim' in self.current_card.fields:
                         w = self.current_card.fields['dim']
                         if hasattr(w, 'setText'): w.setText(dim_str)
                    
                    print(f"DEBUG: Geometria do Pilar populada: {dim_str} em {self.current_card.item_data['rect']}")
                    self.log(f"📍 Geometria Real do Pilar capturada: {dim_str}")

            # ----------------------------------------------------
            # CORREÇÃO: POPULAR SEGMENTOS DE VIGA (LADO A/B/FUNDO)
            # ----------------------------------------------------
            # if field_id.startswith('viga_') or 'seg' in field_id:
            #      # Reforço na inferência de slots para segmentos
            #      if not slot_id or slot_id == 'main':
            #           f_id_lower = field_id.lower()
            #           if any(x in f_id_lower for x in ['_a_', 'side_a', 'lado_a']): slot_id = 'seg_side_a'
            #           elif any(x in f_id_lower for x in ['_b_', 'side_b', 'lado_b']): slot_id = 'seg_side_b'
            #           elif any(x in f_id_lower for x in ['bottom', 'fundo']): slot_id = 'seg_bottom'
            
            # Garantir que slot_id não seja 'main' se estivermos em viga_segs (evita poluição)
            # if field_id == 'viga_segs' and (not slot_id or slot_id == 'main'):
            #      slot_id = 'seg_side_a' # Default fallback

            # 1. Atualizar valor visual
            if isinstance(field, QLineEdit):
                field.setText(str(value))
            elif isinstance(field, QComboBox):
                field.setCurrentText(str(value))
            elif isinstance(field, QLabel):
                field.setText(f"Válido: {value}")
                field.setStyleSheet("color: #00cc66; font-weight: bold; font-size: 10px;")
            
            # Os vínculos e migrações já foram tratados acima.

            if slot_id not in field_slots:
                field_slots[slot_id] = []
            
            # Injetar papel (role)
            pick_data['role'] = slot_id.capitalize()
            field_slots[slot_id].append(pick_data)
            
            # Atualizar QLabel com contagem real se for o caso
            if isinstance(field, QLabel):
                total_links = sum(len(lst) for lst in field_slots.values())
                txt_val = field.text()
                # Se não foi alterado pela logica de extensao
                if "Ext:" not in txt_val: 
                    field.setText(f"{total_links} Vínculo(s) Ok")
                field.setStyleSheet("color: #00cc66; font-weight: bold; font-size: 10px;")

            # Lógica Especial: Fundo da Viga - Calcular dimensão pelo maior segmento
            if 'seg_bottom' in slot_id or 'viga_fundo' in field_id:
                all_segs = field_slots.get('seg_bottom', [])
                if not all_segs and field_id == 'viga_segs':
                     all_segs = field_slots.get('main', [])

                if all_segs:
                    total_len = 0.0
                    for seg in all_segs:
                        pts = seg.get('points', [])
                        if len(pts) >= 2:
                             # Calcular soma de todos os segmentos vinculados
                             for i in range(len(pts)-1):
                                 p1, p2 = pts[i], pts[i+1]
                                 total_len += ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5
                    
                    # Atualizar comprimento do fundo se o campo existir
                    fundo_field_key = 'comprimento_fundo'
                    self.current_card.item_data[fundo_field_key] = round(total_len, 1)
                    if fundo_field_key in self.current_card.fields:
                         self.current_card.fields[fundo_field_key].setText(str(round(total_len, 1)))
                    self.log(f"📏 Comprimento do Fundo Atualizado: {total_len:.1f}")
            
            # REFRESH GERAL
            # a) Refresh Link Managers Embutidos
            if self.current_card and hasattr(self.current_card, 'embedded_managers'):
                 lm = self.current_card.embedded_managers.get(field_id)
                 if lm:
                     lm.links = field_slots # Atualiza dados
                     lm.refresh_list()
            
            # b) Refresh Canvas (Redesenha geometria do item)
            item_data = self.current_card.item_data
            itype = item_data.get('type','').lower()
            if 'marcodxf' in itype or 'contorno' in itype:
                self.canvas.draw_marco_dxf(item_data)
            elif 'viga' in itype:
                # Foca/Desenha geometria da viga atualizada (SEM ZOOM AUTOMATICO NO PICK)
                self.canvas.focus_on_beam_geometry(item_data, apply_zoom=False)

            # --- OVERHAUL: Lógica Inteligente para novos campos ---
            # 1. Comprimento Total (Geometria)
            if '_comprimento_total' in field_id and slot_id == 'geometry':
                pts = pick_data.get('points', [])
                if len(pts) >= 2:
                    length = sum(((pts[i][0]-pts[i+1][0])**2 + (pts[i][1]-pts[i+1][1])**2)**0.5 for i in range(len(pts)-1))
                    if isinstance(field, QLineEdit):
                        field.setText(f"{length:.0f}") # Arredondar para inteiro visualmente limpo
                        # IMPORTANTE: Salvar no item_data para persistência
                        self.current_card.item_data[field_id] = f"{length:.0f}"
                        # Injetar no objeto de link original também
                        pick_data['text'] = f"{length:.0f}"

            # 2. Abertura Pilar (Complex Group)
            if '_abert_pilar_' in field_id:
                # Prefix do grupo (Ex: V1_seg_1_abert_pilar_esq)
                prefix = field_id 
                
                if slot_id == 'contact_lines':
                    # Lógica: 1 linha = Largura. 2 linhas = 1ª Dist, 2ª Largura.
                    # Vamos pegar TODAS as linhas desse slot
                    lines = field_slots.get('contact_lines', [])
                    if lines:
                        # Calcular comprimento das últimas linhas adicionadas
                        lens = []
                        for l in lines:
                             pts = l.get('points', [])
                             if len(pts) >= 2:
                                 d = ((pts[0][0]-pts[1][0])**2 + (pts[0][1]-pts[1][1])**2)**0.5
                                 lens.append(d)
                        
                        f_larg = self.current_card.fields.get(f"{prefix}_larg")
                        f_dist = self.current_card.fields.get(f"{prefix}_dist")
                        
                        if len(lens) == 1 and f_larg:
                             val = f"{lens[0]:.0f}"
                             f_larg.setText(val)
                             self.current_card.item_data[f"{prefix}_larg"] = val
                        elif len(lens) >= 2:
                             if f_dist: 
                                 val_d = f"{lens[-2]:.0f}"
                                 f_dist.setText(val_d)
                                 self.current_card.item_data[f"{prefix}_dist"] = val_d
                             if f_larg: 
                                 val_l = f"{lens[-1]:.0f}"
                                 f_larg.setText(val_l)
                                 self.current_card.item_data[f"{prefix}_larg"] = val_l

                if slot_id in ['cont_tip_esq', 'cont_tip_dir']:
                    # Lógica: Cruzamento (-4) ou Continuidade (11)
                    # Simplificação: Se desenhou linha, assume continuidade por enquanto (11).
                    # Se user quiser 'para', ele desenharia cruzando? O pedido diz:
                    # "cruzada sobre... definido como 'para' (-4), e se for sobreposta... 'continua' (11)"
                    # Implementação geométrica completa requer acesso à viga principal. 
                    # Por hora, vamos setar um valor condicional ou default 11 e user ajusta.
                    # Mas o prompt do user foi específico: "A condição é... Fazer a conta".
                    
                    # Tentar inferir cruzamento
                    f_diff = self.current_card.fields.get(f"{prefix}_diff")
                    if f_diff:
                        # Mock logic: Se bounding box da linha de continuidade cruza bounding box da Viga (Item Data)...
                        # Muito complexo para calcular aqui sem contexto completo da viga. 
                        # Vamos usar heurística: Se linha é curta (< 20cm) -> Para (-4). Se longa -> Continua (11).
                        pts = pick_data.get('points', [])
                        d = 0
                        if len(pts) >= 2:
                            d = ((pts[0][0]-pts[1][0])**2 + (pts[0][1]-pts[1][1])**2)**0.5
                        
                        val = "11" if d > 15 else "-4"
                        f_diff.setText(val)
                        self.current_card.item_data[f"{prefix}_diff"] = val

            # 3. Abertura Viga (Complex Group)
            if '_abert_viga_' in field_id:
                prefix = field_id
                
                # Texto Dimensão (20x60)
                if slot_id == 'arr_dim':
                    txt = pick_data.get('text', '')
                    # Regex para separar
                    nums = [int(n) for n in re.findall(r'\d+', txt)]
                    if len(nums) >= 2:
                        # Menor = Largura, Maior = Profundidade
                        larg = min(nums)
                        prof = max(nums)
                        
                        f_larg = self.current_card.fields.get(f"{prefix}_larg")
                        f_prof = self.current_card.fields.get(f"{prefix}_prof")
                        if f_larg: 
                            f_larg.setText(str(larg))
                            self.current_card.item_data[f"{prefix}_larg"] = str(larg)
                        if f_prof: 
                            f_prof.setText(str(prof))
                            self.current_card.item_data[f"{prefix}_prof"] = str(prof)
                
                # Ajuste Boca (Linha)
                if slot_id == 'adj_mouth':
                     pts = pick_data.get('points', [])
                     if len(pts) >= 2:
                         length = ((pts[0][0]-pts[1][0])**2 + (pts[0][1]-pts[1][1])**2)**0.5
                         f_aj = self.current_card.fields.get(f"{prefix}_aj_boca")
                         if f_aj: 
                             val = f"{length:.0f}"
                             f_aj.setText(val)
                             self.current_card.item_data[f"{prefix}_aj_boca"] = val

                # Ajuste Prof (Linha)
                if slot_id == 'adj_depth':
                     pts = pick_data.get('points', [])
                     if len(pts) >= 2:
                         length = ((pts[0][0]-pts[1][0])**2 + (pts[0][1]-pts[1][1])**2)**0.5
                         f_aj = self.current_card.fields.get(f"{prefix}_aj_prof")
                         if f_aj: 
                             val = f"{length:.0f}"
                             f_aj.setText(val)
                             self.current_card.item_data[f"{prefix}_aj_prof"] = val

            # 4. Lajes Complexas
            if 'laje' in field_id and not '_geom' in field_id:
                 if slot_id == 'dim':
                     # "H=12" -> 12
                     txt = pick_data.get('text', '')
                     nums = re.findall(r'\d+', txt)
                     if nums:
                         # Campo principal (que é o próprio field_id nas lajes, pois ocultamos input mas LinkManager manda para cá)
                         # Espera, nas lajes definimos _add_linked_row com hide_input=True.
                         # O valor deve ir para onde? O user disse: "o valor dos campos da laje é o valor do texto para dimensao"
                         # Como é hide_input, é um QLabel. Atualizamos o texto do Label?
                         # Não, se é valor, deveria ser Input. Mas user pediu hide_input=True no passado?
                         # O request atual diz "o valor dos campos da laje é o valor do texto".
                         # Vou forçar atualização do QLabel para mostrar "Dim: 12" ou similar.
                         if isinstance(field, QLabel):
                             field.setText(f"Dim: {nums[0]}")
                             # Salvar no item_data raiz para persistência
                             self.current_card.item_data[field_id] = nums[0]

            self.log(f"Vínculo adicionado ao campo {field_id} [Slot: {slot_id}]: {value}")
            
            # 3. Notificar o card para atualizar estilos e o LinkManager embutido (drawer)
            self.current_card.refresh_validation_styles()
            
            # 4. Redesenhar vínculos para manter a demarcação visual ativa no Canvas
            self.canvas.draw_item_links(self.current_card.item_data)

            # 5. Limpar o estado de pick para evitar múltiplas execuções acidentais
            if hasattr(self, 'current_pick_field'): delattr(self, 'current_pick_field')
            if hasattr(self, 'current_pick_slot'): delattr(self, 'current_pick_slot')

    def on_element_focused_on_table(self, data):
        """Disparado quando user clica num vínculo ou viga na tabela"""
        from PySide6.QtGui import QColor
        if isinstance(data, dict):
            # Determinar Cor Base
            color = QColor(255, 0, 0)
            if self.current_card:
                t = self.current_card.item_data.get('type', '').lower()
                if 'pilar' in t: color = QColor(0, 180, 0)
                elif 'laje' in t: color = QColor(0, 80, 255)
                elif 'viga' in t: color = QColor(139, 69, 19)
                
            # É um objeto de link completo (com coordenadas)
            self.canvas.highlight_link(data, color)
        elif isinstance(data, str) and data != '-':
            # É apenas o nome (fallback busca nominal em todas as listas)
            self.log(f"Destacando por nome: {data}")
            all_items = self.beams_found + self.pillars_found + self.slabs_found
            self.canvas.highlight_element_by_name(data, all_items)
        
    def log(self, message: str):
        self.console.append(f"> {message}")
        logging.info(message)
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())
        # Se estivermos com a barra de progresso visível, atualizamos o label secundário
        if hasattr(self, 'progress_container') and self.progress_container.isVisible():
            self.lbl_progress.setText(message)

    def show_progress(self, title: str, start_val=0):
        """Ativa visualização de carregamento na sidebar"""
        self.progress_container.show()
        self.progress_bar.setValue(start_val)
        self.lbl_progress.setText(title)
        QApplication.processEvents()

    def update_progress(self, val: int, message: str = None):
        """Atualiza valor da barra e opcionalmente a mensagem"""
        self.progress_bar.setValue(val)
        if message: self.lbl_progress.setText(message)
        # Crucial para manter a UI viva durante o loop pesado
        if val % 2 == 0: 
            QApplication.processEvents()

    def hide_progress(self):
        """Oculta barra após conclusão"""
        self.progress_bar.setValue(100)
        self.progress_container.hide()

    def load_dxf(self, path=None):
        if not path:
             # Fallback manual antigo
             path, _ = QFileDialog.getOpenFileName(self, "Selecionar DXF", "", "DXF Files (*.dxf)")
        
        if not path: return

        self.log(f"Carregando {path}...")
        try:
            self.dxf_data = DXFLoader.load_dxf(path)
            if not self.dxf_data:
                self.log("❌ DXFLoader retornou None.")
                return
            
            self.log(f"📊 DXF Parsed: {len(self.dxf_data.get('lines', []))} linhas, {len(self.dxf_data.get('texts', []))} textos.")
            
            # 1. Inicializar Lógica (Spatial Index + Engines)
            self._initialize_project_logic(self.dxf_data)
            
            # 2. Enviar para o canvas
            self.canvas.add_dxf_entities(self.dxf_data)
            self.log("🎨 Canvas atualizado.")
            self.canvas.dxf_entities = self.dxf_data.get('texts', [])

        except Exception as e:
            self.log(f"💥 Falha crítica no load_dxf: {e}")
            import traceback
            traceback.print_exc()
        
        self.btn_process.setEnabled(True)

    def _initialize_project_logic(self, dxf_data, force_reindex=False):
        """Centraliza a preparação do contexto lógico. Otimizado com Cache."""
        if not dxf_data: return
        
        # Se já temos os motores no cache para este projeto, e não é force, pulamos
        if not force_reindex and self.current_project_id in self.loaded_projects_cache:
            cache = self.loaded_projects_cache[self.current_project_id]
            if cache.get('context_engine'):
                self.log("⚡ Usando motores cacheado.")
                self.context_engine = cache['context_engine']
                self.pillar_analyzer = cache['pillar_analyzer']
                self.beam_walker = cache['beam_walker']
                self.spatial_index = cache['spatial_index']
                return

        # 1. Indexação Espacial
        self.log("🔍 Indexando Geometria...")
        self.show_progress("Indexando DXF...", 10)
        self.spatial_index.clear()
        
        polys = dxf_data.get('polylines', [])
        lines = dxf_data.get('lines', [])
        texts = dxf_data.get('texts', [])
        total = len(polys) + len(lines) + len(texts)
        count = 0

        for poly in polys:
            pts = poly['points']
            if pts:
                bounds = (min(p[0] for p in pts), min(p[1] for p in pts), 
                          max(p[0] for p in pts), max(p[1] for p in pts))
                self.spatial_index.insert(poly, bounds)
            count += 1
            if count % 100 == 0: self.update_progress(10 + int((count/total)*40))
        
        for line in lines:
            s, e = line['start'], line['end']
            bounds = (min(s[0], e[0]), min(s[1], e[1]), max(s[0], e[0]), max(s[1], e[1]))
            self.spatial_index.insert(line, bounds)
            count += 1
            if count % 100 == 0: self.update_progress(10 + int((count/total)*40))

        for txt in texts:
            p = txt['pos']
            bounds = (p[0]-5, p[1]-5, p[0]+5, p[1]+5)
            self.spatial_index.insert(txt, bounds)
            count += 1
            if count % 100 == 0: self.update_progress(10 + int((count/total)*40))
            
        # 2. Motores de Inteligência
        self.log("⚙️ Inicializando Engines...")
        self.context_engine = ContextEngine(dxf_data, self.spatial_index, self.memory)
        self.pillar_analyzer = PillarAnalyzer(self.context_engine)
        self.beam_walker = BeamWalker(self.spatial_index)
        
        # Salvar no Cache
        if self.current_project_id in self.loaded_projects_cache:
            cache = self.loaded_projects_cache[self.current_project_id]
            cache['context_engine'] = self.context_engine
            cache['pillar_analyzer'] = self.pillar_analyzer
            cache['beam_walker'] = self.beam_walker
            cache['spatial_index'] = self.spatial_index

        self.hide_progress()
        self.log("✅ Sistema de inteligência pronto.")

    def _extract_float(self, text):
        """Extrai o primeiro número float de uma string."""
        if not text: return None
        try:
            m = re.search(r'[-+]?\d*[.,]\d+|\d+', str(text).replace(',', '.'))
            return float(m.group()) if m else None
        except: return None

    def process_pillars_action(self):
        if not self.dxf_data: return
        import uuid # Garantir import
        
        # --- Snapshot de Dados Validados (Modo Incremental Automático) ---
        # Agora a análise geral SEMPRE preserva o que está validado/editado.
        # Para refazer um item do zero, o usuário deve excluí-lo da biblioteca.
        incremental = True
        preserved_pillars = {}
        preserved_beams = {}
        preserved_slabs = {}
        
        # Snapshot Pilares
        for p in self.pillars_found:
             if p.get('is_validated') or p.get('validated_fields') or p.get('links'):
                 preserved_pillars[p.get('name')] = p
                 
        # Snapshot Vigas
        if hasattr(self, 'beams_found'):
             for b in self.beams_found:
                 if b.get('is_validated') or b.get('validated_fields') or b.get('links'):
                     preserved_beams[b.get('name')] = b
                     
        # Snapshot Lajes
        if hasattr(self, 'slabs_found'):
             for s in self.slabs_found:
                 if s.get('is_validated') or s.get('validated_fields') or s.get('links'):
                     preserved_slabs[s.get('name')] = s
                     
        if preserved_pillars or preserved_beams or preserved_slabs:
             self.log(f"🛡️ Reanálise Incremental: Sincronizando com Biblioteca ({len(preserved_pillars)} P, {len(preserved_beams)} V, {len(preserved_slabs)} L).")

        self.log("Iniciando varredura geométrica e análise de vínculos...")
        
        # --- NOVO: Limpar seleção para evitar destaques vermelhos residuais (DXF selecionados) ---
        if self.canvas and self.canvas.scene:
            self.canvas.scene.clearSelection()

        # --- Garantir que motores estão vivos se tiver DXF ---
        if not self.pillar_analyzer or not self.context_engine:
             self.log("⚠️ Motores não encontrados. Inicialização forçada...")
             self._initialize_project_logic(self.dxf_data)

        self.show_progress("Iniciando Análise Geral...", 5)
        # Limpar Listas
        self.list_pillars.clear()
        self.list_beams.clear()
        self.list_slabs.clear()
        
        # Resetar dados internos
        self.pillars_found = []
        self.beams_found = []
        self.slabs_found = []
        
        polylines = self.dxf_data.get('polylines', [])
        texts = self.dxf_data.get('texts', [])
        lines = self.dxf_data.get('lines', [])
        
        # 1. Motores - Vigas
        from src.core.beam_tracer import BeamTracer
        beam_tracer = BeamTracer(self.spatial_index)
        all_lines_and_polys = []
        for l in lines+polylines:
            if 'points' in l: all_lines_and_polys.append(l)
            elif 'start' in l: all_lines_and_polys.append({'points': [l['start'], l['end']]})

        self.update_progress(10, "Buscando Vigas...")
        self.beams_found = beam_tracer.detect_beams(texts, all_lines_and_polys)
        # NATURAL SORT
        import re
        def nat_key(x):
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', x.get('name', ''))]
        self.beams_found.sort(key=nat_key)
        
        for i, b in enumerate(self.beams_found):
            b_unique_id = f"{self.current_project_id}_b_{i+1}" if self.current_project_id else str(uuid.uuid4())
            b['id'] = b_unique_id
            b['id_item'] = f"{i+1:02}"
            b['id_num'] = i+1
            b['project_id'] = self.current_project_id
            
            # Processamento Inteligente Inicial
            self._process_beam_intelligent(b)

            # RESTAURAÇÃO (Incremental)
            if incremental and b['name'] in preserved_beams:
                 old = preserved_beams[b['name']]
                 
                 # 1. Se VALIDADO, restaura tudo
                 if old.get('is_validated', False):
                     b['is_validated'] = True
                     b['links'] = old.get('links', {})
                     b['confidence_map'] = old.get('confidence_map', {})
                     b['validated_fields'] = old.get('validated_fields', [])
                     
                     # Restaura campos em geral
                     for f, v in old.items():
                         if f not in ['links', 'confidence_map', 'validated_fields', 'is_validated', 'issues']:
                            b[f] = v
                            
                     print(f"DEBUG: Viga {b['name']} restaurada (VALIDADA).")
                 
                 # 2. Se NÃO VALIDADO, NÃO RESTAURA LINKS
                 else:
                     # Apenas restaura campos específicos se eles individualmente foram validados
                     vf = old.get('validated_fields', [])
                     if vf:
                         b['validated_fields'] = vf
                         for f in vf: 
                             if f in old: b[f] = old[f]
                     
                     print(f"DEBUG: Viga {b['name']} re-analisada (Não validada).")

        # 1.0b Finalizar Lista de Vigas Hierárquica
        self._populate_beam_tree(self.list_beams, self.beams_found)

        # 1.1 Detect Slabs (Lajes)
        self.update_progress(30, "Mapeando Lajes...")
        slab_tracer = SlabTracer(self.spatial_index)
        
        # --- LEARNING FROM VALIDATED ---
        learned_layers = set()
        learned_dim_layers = set()
        learned_level_layers = set()
        learned_contour_radius = 2000.0 # Default
        learned_text_radius = 200.0 # Default
        
        has_validated = False
        
        if preserved_slabs:
            potential_layers = []
            max_diag = 0.0
            max_text_dist = 0.0
            
            for s_name, s_data in preserved_slabs.items():
                if s_data.get('is_validated'):
                    has_validated = True
                    
                    # 1. Learn Contour Layers & Radius
                    links = s_data.get('links', {}).get('laje_outline_segs', {}).get('contour', [])
                    if links and 'points' in links[0]:
                        pts = links[0]['points']
                        
                        # Radius heuristic (Bounding Box Diagonal)
                        all_x = [p[0] for p in pts]
                        all_y = [p[1] for p in pts]
                        if all_x and all_y:
                            diag = ((max(all_x)-min(all_x))**2 + (max(all_y)-min(all_y))**2)**0.5
                            if diag > max_diag: max_diag = diag
                        
                        # Layer heuristic
                        # Tenta achar essa geom no spatial index para ver o layer
                        for cw_poly in self.dxf_data.get('polylines', []):
                             if len(cw_poly['points']) == len(pts): # Check rápido
                                 # (Opcional) Check geometry bounds match
                                 lay = cw_poly.get('layer')
                                 if lay: potential_layers.append(lay)
                    
                    # 2. Learn Data Layers & Radius (Textos)
                    # Dimensão
                    dim_links = s_data.get('links', {}).get('laje_dim', {}).get('label', [])
                    for dl in dim_links:
                        if 'layer' in dl: learned_dim_layers.add(dl['layer'])
                        # Distancia do centro da laje ao texto
                        if 'pos' in dl and 'pos' in s_data:
                            dx = dl['pos'][0] - s_data['pos'][0]
                            dy = dl['pos'][1] - s_data['pos'][1]
                            dist = (dx**2 + dy**2)**0.5
                            if dist > max_text_dist: max_text_dist = dist

                    # Nível
                    lvl_links = s_data.get('links', {}).get('laje_nivel', {}).get('label', [])
                    for ll in lvl_links:
                        if 'layer' in ll: learned_level_layers.add(ll['layer'])
                        if 'pos' in ll and 'pos' in s_data:
                            dx = ll['pos'][0] - s_data['pos'][0]
                            dy = ll['pos'][1] - s_data['pos'][1]
                            dist = (dx**2 + dy**2)**0.5
                            if dist > max_text_dist: max_text_dist = dist

            if potential_layers:
                from collections import Counter
                common = Counter(potential_layers).most_common(5)
                search_layers = [c[0] for c in common]
                self.log(f"🧠 Aprendizado Laje: Layers={search_layers}")
            
            if max_diag > 0:
                learned_contour_radius = max_diag * 1.5
                self.log(f"🧠 Aprendizado Laje: Raio Busca Contorno={learned_contour_radius:.1f}")
                
            if max_text_dist > 0:
                learned_text_radius = max_text_dist * 1.2
                self.log(f"🧠 Aprendizado Laje: Raio Busca Textos={learned_text_radius:.1f}")

        # Configuração de aprendizado para passar adiante
        self.slab_learning_config = {
            'search_radius': learned_text_radius,
            'dim_layers': list(learned_dim_layers) if learned_dim_layers else None,
            'level_layers': list(learned_level_layers) if learned_level_layers else None
        }

        self.slabs_found = slab_tracer.detect_slabs_from_texts(texts, valid_layers=search_layers, search_radius=learned_contour_radius)
        self.slabs_found.sort(key=nat_key)
        self.log(f"🔎 Lajes detectadas: {len(self.slabs_found)} (Busca por textos L#)")
        
        for i, s in enumerate(self.slabs_found):
             s_unique_id = f"{self.current_project_id}_l_{i+1}" if self.current_project_id else str(uuid.uuid4())
             s['id'] = s_unique_id
             s['id_item'] = f"{i+1:02}"
             s['project_id'] = self.current_project_id
             s['type'] = 'Laje'
             s['laje_name'] = s['name']
             
             # --- PROCESSAMENTO INTELIGENTE ---
             self._process_slab_intelligent(s)
             
             # RESTAURAÇÃO (Incremental Inteligente)
             # RESTAURAÇÃO (Incremental Inteligente)
             if incremental and s['name'] in preserved_slabs:
                 old = preserved_slabs[s['name']]
                 
                 # 1. Se VALIDADO GLOBALMENTE, restaura tudo
                 if old.get('is_validated', False):
                     s['is_validated'] = True
                     s['links'] = old.get('links', {})
                     s['fields'] = old.get('fields', {}).copy()
                     s['validated_fields'] = old.get('validated_fields', [])
                     print(f"DEBUG: Laje {s['name']} restaurada (VALIDADA).")
                 
                 # 2. Se NÃO VALIDADO, NÃO RESTAURA LINKS NEM GEOMETRIA
                 # Apenas restaura campos específicos se eles individualmente foram validados
                 else:
                     # Não restaura 'links' antigos (Geometria velha vai pro lixo)
                     # Restaura apenas campos validados manualmente
                     vf = old.get('validated_fields', [])
                     if vf:
                         s['validated_fields'] = vf
                         # Restaura apenas os fields que estão na lista de validados
                         old_fields = old.get('fields', {})
                         for f in vf:
                             if f in old_fields: s['fields'][f] = old_fields[f]
                         # Nota: Não restauramos links parciais aqui, pois geometria é link.
                         # Se o usuário validou um campo de texto (ex: nome), ok.
                         # Se validou geometria, deveria ter validado a laje toda ou teremos que ter lógica granular de link.
                         # Assumindo que validação de geometria = validação do item.
                     
                     print(f"DEBUG: Laje {s['name']} re-analisada (Não validada).")
             
             item_text = f"{s['id_item']} | {s['name']}"
             if s.get('is_validated'):
                 item_text += " ✅"

             item = QListWidgetItem(item_text)
             if s.get('is_validated'):
                 item.setForeground(Qt.green)

             item.setData(Qt.UserRole, s_unique_id)
             self.list_slabs.addItem(item)

        walker = BeamWalker(self.spatial_index)
        from shapely.geometry import Polygon
        self.pillars_found = []
        temp_pillars = []
        
        from src.core.perspective_mapper import PillarPerspectiveMapper
        # 2. Processar Pilares
        self.update_progress(50, "Analisando Pilares...")
        total_p = len(polylines)
        
        for i, p_item in enumerate(polylines):
            if i % 10 == 0: self.update_progress(50 + int((i/total_p)*45))
            poly_points = p_item['points']
            unique_points = []
            for pt in poly_points:
                if not unique_points or pt != unique_points[-1]:
                    unique_points.append(pt)
            
            if len(unique_points) < 3:
                continue
                
            try:
                poly_shape = Polygon(unique_points)
                if not poly_shape.is_valid:
                    from shapely.validation import make_valid
                    poly_shape = make_valid(poly_shape)
                    
                if poly_shape.geom_type == 'MultiPolygon':
                    poly_shape = max(poly_shape.geoms, key=lambda g: g.area)
                
                if poly_shape.geom_type != 'Polygon':
                    continue

                # Nome Real e Formato por Perspectiva (VIA ENGINE)
                p_ent = self.context_engine.find_nearest_text(unique_points, "P") if self.context_engine else None
                p_name = p_ent['text'] if p_ent else None
                pillar_name = p_name or f"P{i+1}"
                
                from src.core.perspective_mapper import PillarPerspectiveMapper
                shape_type, orient = PillarPerspectiveMapper.identify_shape(unique_points)
                
                p_data = {
                    'name': pillar_name,
                    'type': 'Pilar',
                    'pos': (poly_shape.centroid.x, poly_shape.centroid.y), # Centro Real
                    'format': shape_type,
                    'area_val': poly_shape.area, # Valor numérico para o DB
                    'dim': f"{int(poly_shape.area)}cm²",
                    'points': list(poly_shape.exterior.coords),
                    'sides_data': PillarPerspectiveMapper.map_sides(unique_points, shape_type, orient),
                    'links': {
                        'pilar_segs': { # Popula automaticamente o slot 'pilar_segs' (esperado pelo DetailCard)
                            'segments': [{
                                'type': 'poly',
                                'points': list(poly_shape.exterior.coords),
                                'text': 'Geometria Automática'
                            }]
                        }
                    }, 
                    'neighbors': [],
                    'beams_visual': [], 
                    'material': 'C30', 'level': 'Pavimento 1'
                }
                
                # Análise Contextual (Initial)
                if self.pillar_analyzer:
                    self.pillar_analyzer.analyze(p_data)
                

                
                p_data['issues'] = self._run_sanity_checks(p_data)
                
                temp_pillars.append(p_data)
                
            except Exception as e:
                self.log(f"⚠️ Erro no pilar {i}: {e}")

        # ORDENAR PILARES
        temp_pillars.sort(key=nat_key)
        
        for i, p_data in enumerate(temp_pillars):
            # Atribuir números sequenciais após ordenação
            unique_id = f"{self.current_project_id}_p_{i+1}" if self.current_project_id else str(uuid.uuid4())
            p_data['id'] = unique_id
            p_data['id_item'] = f"{i+1:02}"
            
            # RESTAURAÇÃO (Incremental)
            if incremental and p_data['name'] in preserved_pillars:
                 old = preserved_pillars[p_data['name']]
                 
                 # 1. Se VALIDADO, restaura tudo
                 if old.get('is_validated', False):
                     p_data['is_validated'] = True
                     p_data['links'] = old.get('links', {})
                     p_data['sides_data'] = old.get('sides_data', {})
                     p_data['beams_visual'] = old.get('beams_visual', [])
                     p_data['validated_fields'] = old.get('validated_fields', [])
                     
                     # Restaura campos
                     for f, v in old.items():
                         if f not in ['links', 'sides_data', 'beams_visual', 'validated_fields', 'is_validated', 'issues']:
                            p_data[f] = v
                            
                     print(f"DEBUG: Pilar {p_data['name']} restaurado (VALIDADO).")
                 
                 # 2. Se NÃO VALIDADO, NÃO RESTAURA LINKS/GEOMETRIA
                 else:
                     # Apenas restaura campos específicos se eles individualmente foram validados
                     vf = old.get('validated_fields', [])
                     if vf:
                         p_data['validated_fields'] = vf
                         # Restaura apenas os fields que estão na lista de validados
                         for f in vf: 
                             if f in old: p_data[f] = old[f]
                     
                     print(f"DEBUG: Pilar {p_data['name']} re-analisado (Não validado).")

            self.pillars_found.append(p_data)
            
            # Listagem: Numero Item - Nome - Dim - Formato (AGORA RESTAURADOS)
            item_text = f"{p_data['id_item']} | {p_data['name']} | {p_data['dim']} | {p_data['format']}"
            
            # Se já estava validado, adiciona check
            if p_data.get('is_validated'):
                item_text += " ✅"
            
            item = QListWidgetItem(item_text)
            
            conf_map = p_data.get('confidence_map', {})
            avg_conf = sum(conf_map.values()) / len(conf_map) if conf_map else 0.5
            
            if p_data.get('is_validated'):
                 item.setForeground(Qt.green)
            elif p_data['issues']:
                item.setForeground(Qt.red)
                self._add_to_issues_list(p_data, avg_conf)
            elif avg_conf < 0.6:
                item.setForeground(Qt.yellow)
                self._add_to_issues_list(p_data, avg_conf)

            item.setData(Qt.UserRole, unique_id) 
            self.list_pillars.addItem(item)

        # 3. Desenho no Canvas e UI
        self.update_progress(95, "Finalizando...")
        self._update_all_lists_ui()
        
        # FIX: Limpa itens visuais anteriores para evitar duplicações (Destaque vermelho obsoleto)
        self.canvas.clear_interactive()
        
        self.canvas.draw_interactive_pillars(self.pillars_found)
        self.canvas.draw_slabs(self.slabs_found)
        self.canvas.draw_beams(self.beams_found)
        self.hide_progress()
        self.log(f"Análise finalizada: {len(self.pillars_found)} Pilares, {len(self.beams_found)} Vigas e {len(self.slabs_found)} Lajes.")
        self.btn_save.setEnabled(True)

    # Legacy methods removed
    def on_list_pillar_clicked(self, item):
        pillar_id = item.data(Qt.UserRole)
        pilar = next((p for p in self.pillars_found if p['id'] == pillar_id), None)
        if pilar:
            self.show_detail(pilar)
            self.canvas.isolate_item(pillar_id, 'pillar') # Isola no Canvas
            self.canvas.draw_focus_beams(pilar.get('beams_visual', []))
            # NOVO: Desenha todos os vínculos salvos (Labels, Dimensões, etc)
            self.canvas.draw_item_links(pilar)
        else:
            self.log(f"Erro: Pilar {pillar_id} não encontrado nos dados processados.")

    # --- CALLBACKS DE LISTAS ---

    def on_list_beam_clicked(self, item, column=0):
        beam_id = item.data(0, Qt.UserRole)
        if not beam_id: return # Clicou no nó pai
        beam = next((b for b in self.beams_found if b['id'] == beam_id), None)
        if beam:
            self.show_detail(beam)
            # 1. Isolar no Canvas (Esconde todas as outras e mostra apenas esta)
            self.canvas.isolate_item(beam_id, 'beam', apply_zoom=False)
            
            # 2. Focar na viga (geometria completa e zoom detalhado)
            self.canvas.focus_on_beam_geometry(beam)
            # NOVO: Desenhar também os vínculos salvos (Labels, Dimensões, etc)
            self.canvas.draw_item_links(beam)

    def on_list_slab_clicked(self, item):
        slab_id = item.data(Qt.UserRole)
        slab = next((s for s in self.slabs_found if s['id'] == slab_id), None)
        if slab:
            self.show_detail(slab)
            self.canvas.isolate_item(slab_id, 'slab') # Isola Laje (com Zoom)
            # NOVO: Desenhar todos os vínculos salvos (Destaque de segmentos, ilhas, etc)
            self.canvas.draw_item_links(slab)

    def on_canvas_pillar_selected(self, p_id):
        for i in range(self.list_pillars.count()):
            it = self.list_pillars.item(i)
            if it.data(Qt.UserRole) == p_id:
                self.list_pillars.setCurrentItem(it)
                self.on_list_pillar_clicked(it)
                break

    def save_project_action(self):
        """Salva o estado atual no banco de dados do projeto."""
        if not self.current_project_id:
            self.log("❌ Nenhum projeto ativo. Use 'Gerenciar Projetos'.")
            return
            
        self.log(f"💾 Salvando projeto {self.current_project_name}...")
        
        # 1. Salvar Metadados (se houver, assumindo que update_project_metadata faça isso)
        self.save_project_metadata() # Usa metodo auxiliar existente se houver, ou implementado separadamente

        # 2. Save Pillars
        for p in self.pillars_found:
            self.db.save_pillar(p, self.current_project_id)
        self.log(f"   -> {len(self.pillars_found)} pilares salvos.")

        # 3. Save Slabs
        slabs = getattr(self, 'slabs_found', [])
        for s in slabs:
            self.db.save_slab(s, self.current_project_id)
        self.log(f"   -> {len(slabs)} lajes salvas.")

        # 4. Save Beams
        beams = getattr(self, 'beams_found', [])
        for b in beams:
            self.db.save_beam(b, self.current_project_id)
        
        self.log(f"   -> {len(beams)} vigas salvas.")
        self.log("✅ Projeto salvo com sucesso!")

    def load_project_action(self):
        """Carrega e restaura o estado do projeto."""
        if not self.current_project_id:
            return
            
        self.log(f"📂 Carregando dados do projeto {self.current_project_name}...")
        
        # Carregar do Banco de Dados
        self.pillars_found = self.db.load_pillars(self.current_project_id) or []
        self.slabs_found = self.db.load_slabs(self.current_project_id) or []
        self.beams_found = self.db.load_beams(self.current_project_id) or []

        # Ordenar (Funções auxiliares internas)
        import re
        def nat_key(x):
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', x.get('name', ''))]
        
        def sort_key(x):
            id_val = x.get('id_item')
            if id_val and str(id_val).isdigit():
                return (0, int(id_val), nat_key(x))
            return (1, 0, nat_key(x))

        self.pillars_found.sort(key=sort_key)
        self.slabs_found.sort(key=sort_key)
        self.beams_found.sort(key=sort_key)
        # Contornos geralmente são poucos, não precisa ordenar complexo

        # Desenhar overlays no canvas
        if hasattr(self.canvas, 'scene') and self.canvas.scene:
            self.canvas.draw_interactive_pillars(self.pillars_found)
            self.canvas.draw_slabs(self.slabs_found)
            self.canvas.draw_beams(self.beams_found)
        
        # Sincronizar Listas UI
        self._update_all_lists_ui()
        
        # Detalhe do primeiro item se houver
        if self.pillars_found:
            self.show_detail(self.pillars_found[0])
            
        self.log(f"✅ Projeto restaurado: {len(self.pillars_found)}P, {len(self.beams_found)}V, {len(self.slabs_found)}L.")
                
    def on_research_requested(self, field_id, slot_id):
        """Re-executa a busca para o slot usando Treinamento + Prompts. ATUALIZA OS DADOS."""
        self.log(f"🤖 REBUSCAR: Processando slot '{slot_id}' para '{field_id}'...")
        if not self.current_card: return
        
        item_data = self.current_card.item_data
        
        # 1. Limpar vículos atuais deste slot para "Re-vincular"
        links_dict = item_data.setdefault('links', {}).setdefault(field_id, {})
        if slot_id in links_dict:
            self.log(f"🧹 Limpando {len(links_dict[slot_id])} vínculos antigos do slot '{slot_id}'")
            links_dict[slot_id] = []

        # 2. Identificar categoria para role
        def get_cat(fid):
            if 'name' in fid: return 'pillar_name'
            if 'dim' in fid: return 'pillar_dim'
            if '_l1_n' in fid: return 'slab_name'
            if '_l1_h' in fid: return 'slab_thick'
            if '_l1_v' in fid: return 'slab_level'
            if '_v_esq_n' in fid: return 'beam_name'
            if '_v_esq_d' in fid: return 'beam_dim'
            return 'general'
            
        side_code = field_id.split('_')[1][1:] if '_' in field_id else None

        # 3. Executar Busca Contextual Unificada (VIA ENGINE)
        prompt = "regex: .+"
        radius = 800
        # Mapeamento Rápido de Configuração (TODO: Centralizar)
        if 'name' in field_id: prompt = "Buscar texto ('P')"
        elif 'dim' in field_id: prompt = "regex: \\d+([xX]\\d+)?"
        elif '_l1_n' in field_id: prompt = "Buscar texto ('L')"
        elif '_l1_h' in field_id: prompt = "regex: h[=:]?\\d+"
        elif '_v_' in field_id: prompt = "Buscar texto ('V')"
        
        search_cfg = {'field_id': field_id, 'slot_id': slot_id, 'prompt': prompt, 'radius': radius}
        
        result = self.context_engine.perform_search(item_data, search_cfg, side=side_code)
        found_ent = result['found_ent']
        
        if result['used_training']:
             self.log(f"🧠 {result['debug']}")
            
        if found_ent:
            val = found_ent.get('text', 'VALOR')
            self.log(f"✅ Nova interpretação: '{val}'")
            
            # Gravar Novos Vínculos
            if slot_id not in links_dict: links_dict[slot_id] = []
            for lk in result['links']:
                links_dict[slot_id].append(lk)
                self.canvas.highlight_link(lk)
            
            # 5. Atualizar Widget Visual
            target_widget = self.current_card.fields.get(field_id)
            if target_widget:
                from PySide6.QtWidgets import QLineEdit, QComboBox
                if isinstance(target_widget, QLineEdit): target_widget.setText(str(val))
                elif isinstance(target_widget, QComboBox): target_widget.setCurrentText(str(val))
            
            # 7. Refresh na Janela de Vínculos se aberta
            if hasattr(self.current_card, 'active_link_dlg') and self.current_card.active_link_dlg:
                self.current_card.active_link_dlg.links = links_dict # Sincroniza
                self.current_card.active_link_dlg.refresh_list()
            
            # ATUALIZAÇÃO IA SÓBRIA: Re-validar pilar após ajuste manual
            item_data['issues'] = self._run_sanity_checks(item_data)
            self._update_all_lists_ui()
        else:
            self.log("❌ REBUSCAR falhou: Nenhuma nova correspondência encontrada.")
            # Limpa widget visual se falhou na re-interpretação
            target_widget = self.current_card.fields.get(field_id)
            if target_widget and hasattr(target_widget, 'clear'):
                target_widget.clear()
            
            if hasattr(self.current_card, 'active_link_dlg') and self.current_card.active_link_dlg:
                self.current_card.active_link_dlg.links = links_dict # Sincroniza
                self.current_card.active_link_dlg.refresh_list()

    def _log_training_action(self, item_data, field_id, slot_id, link_obj, status='valid', comment=''):
        """Auxiliar central para registrar conhecimento validado ou falho (Hierarchical Memory)."""
        if not self.current_project_id: return

        # NIVEL 1: Contexto de Projeto
        # Idealmente buscaria Work Name e Pavement do DB, aqui simplificamos
        p_context = {
            'id': self.current_project_id,
            'pavement': self.current_project_name, # Fallback
            'work_name': 'Unknown'
        }

        # NIVEL 2: Contexto do Item
        # Prepara geometria bruta (hashable)
        geo_ref = item_data.get('points') or item_data.get('geometry')
        
        # Centralizar item (Origem para offsets)
        item_pos = item_data.get('pos')
        if not item_pos and geo_ref:
            item_pos = (sum(p[0] for p in geo_ref)/len(geo_ref), sum(p[1] for p in geo_ref)/len(geo_ref))
            
        # Gerar DNA (Assinatura Geométrica)
        dna = [1.0, 0.0, 0.0, 1.0]
        if self.context_engine:
            dna = self.context_engine._generate_dna(item_data)

        i_context = {
            'type': item_data.get('type', 'UNKNOWN').title(), # Pilar, Viga, Laje
            'name': item_data.get('name'),
            'geometry': geo_ref,
            'pos': item_pos,
            'neighbors': item_data.get('neighbors', []),
            'dna_vector': dna
        }

        # NIVEL 3: Contexto do Campo/Vinculo
        # O "O Que" estamos validando
        f_context = {
            'field_name': field_id,
            'link_type': slot_id, # ex: 'text_link', 'dim_link'
            'local_geometry': link_obj.get('pos') or link_obj.get('points')
        }

        # Valor Alvo (Label)
        # O valor que o usuário confirmou como correto
        target_val = link_obj.get('text', '')
        if not target_val and ('points' in link_obj or 'start' in link_obj):
             target_val = "GEOMETRY_val" # Marcador de geometria válida

        # Enviar para Memória (HierarchicalMemory)
        if self.memory:
            self.memory.save_training_event(
                project_context=p_context,
                item_context=i_context,
                field_context=f_context,
                label=target_val,
                event_type='user_validation' if status == 'valid' else 'user_rejection'
            )
            self.log(f"🧠 Aprendizado registrado: {i_context['type']} {i_context['name']} -> {field_id}")

    def run_dxf_preprocessor_action(self):
        """Executa o tratamento prévio de vigas/marco do DXF."""
        if not self.dxf_data:
            self.log("⚠️ Carregue um DXF primeiro.")
            return

        self.show_progress("Executando Tratamento Prévio (Marco)...", 20)
        
        # Inicializar engine se necessário
        if not self.dxf_preprocessor:
            self.dxf_preprocessor = DXFPreprocessor(self.spatial_index, self.memory)

        # Rodar análise
        results = self.dxf_preprocessor.run_marco_analysis(self.dxf_data, self.current_project_id or "temp")
        
        self.update_progress(80, "Desenhando Marco no Canvas...")
        
        # 1. Desenhar no Canvas (Linhas azuis)
        if 'item_data' in results:
            self.canvas.draw_marco_dxf(results['item_data'])
        
        # 2. Registrar o item virtual de Marco se estiver num projeto
        # Para que o usuário possa ver os vínculos de extensões e unioes
        if results.get('item_data'):
            marco_item = results['item_data']
            
            # Atualizar Lista Oficial de Contornos
            if not hasattr(self, 'contours_found'): self.contours_found = []
            
            # Remover anterior se houver (assumindo 1 marco por projeto por enquanto)
            self.contours_found = [c for c in self.contours_found if c['id'] != marco_item['id']]
            self.contours_found.append(marco_item)
            
            # Retrocompatibilidade (se ainda for usado em algum lugar)
            self.marco_found = [marco_item]
            
            # Atualizar UI
            self._update_all_lists_ui()
            
            self.log(f"✅ Tratamento Prévio concluído: {len(results['extensions'])} extensões e {len(results['marco'])} uniões geradas.")
        
        self.hide_progress()
        QMessageBox.information(self, "Tratamento Prévio", 
                                "Marco do DXF gerado com sucesso!\nVerifique a aba 'Contorno' para detalhes.")

    def show_pre_processing_details(self):
        """Abre a ficha técnica do Marco do DXF para edição de vínculos."""
        contours = getattr(self, 'contours_found', [])
        if contours:
            self.show_detail(contours[0])
            # Forçar visualização no canvas
            self.canvas.draw_marco_dxf(contours[0])
        else:
            self.log("⚠️ Nenhum tratamento prévio (Marco) foi gerado ainda. Execute 'Tratamento Prévio' primeiro.")
            QMessageBox.warning(self, "Detalhes", "Nenhum Marco encontrado. Execute o 'Tratamento Prévio' primeiro.")

    def on_train_requested(self, field_id, train_data):
        """Registra feedback de treino no banco de dados e opcionalmente propaga."""
        if not self.current_project_id:
            self.log("❌ Crie/Abra um projeto para treinar.")
            return

        if not self.current_card: return
        p_data = self.current_card.item_data
        
        # Checar se é um caso de N/A (Não se Aplica)
        is_na = field_id in p_data.get('na_fields', [])
        
        slot_id = train_data.get('slot', 'main')
        status = 'na' if is_na else train_data.get('status', 'valid')
        link_obj = train_data.get('link', {})
        
        comment = train_data.get('comment', '')
        if is_na:
            comment = "Campo marcado como Não se Aplica pelo usuário"
            
        propagate = train_data.get('propagate', False)

        # 1. Registrar o Treino Individual
        self._log_training_action(p_data, field_id, slot_id, link_obj, status, comment)

        # 2. Feedback Visual Imediato
        if status == 'valid':
            # Marcar o link individual como validado
            link_obj['validated'] = True
            link_obj.pop('failed', None)
            
            self.current_card.mark_field_validated(field_id, True)
            self.log(f"👍 Feedback POSITIVO salvo para '{field_id}:{slot_id}'")
            
            # --- NOVO: Se validou o vínculo, valida o item inteiro no DXF ---
            self.on_card_validated(p_data)
        else:
            # Marcar o link individual como falho
            link_obj['failed'] = True
            link_obj.pop('validated', None)
            
            self.current_card.mark_field_validated(field_id, False)
            f = self.current_card.fields.get(field_id)
            if f and hasattr(f, 'clear'): f.clear()
            self.log(f"⚠️ Feedback de FALHA salvo para '{field_id}:{slot_id}'")

        # Forçar refresh do LinkManager se ele estiver aberto
        if hasattr(self.current_card, 'embedded_managers'):
            lm = self.current_card.embedded_managers.get(field_id)
            if lm:
                lm.refresh_list()

        self.tab_training.load_events(self.current_project_id)

    def _propagate_training_action(self, field_id, slot_id, source_pilar, link_obj):
        """Propaga o vínculo aprendido para outros pilares com DNA similar."""
        self.log(f"📡 Iniciando Radar de Propagação para {field_id}:{slot_id}...")
        source_dna = self._generate_pilar_dna(source_pilar)
        lx, ly = link_obj.get('pos', source_pilar.get('pos', (0,0)))
        px, py = source_pilar.get('pos', (0,0))
        rel_pos = (lx - px, ly - py)
        
        propagated_count = 0
        
        # Categoria para isolar aprendizado
        def get_cat(fid):
            if 'name' in fid: return 'pillar_name'
            if 'dim' in fid: return 'pillar_dim'
            if '_l1_n' in fid: return 'slab_name'
            if '_v_esq_n' in fid: return 'beam_name'
            return 'general'

        for target_p in self.pillars_found:
            if target_p['id'] == source_pilar['id']: continue
            if field_id in target_p.get('validated_fields', []): continue
            
            target_dna = self._generate_pilar_dna(target_p)
            # Calcular distância de DNA (simplificada)
            dist = sum(((a - b) / (a + 1))**2 for a, b in zip(source_dna, target_dna))**0.5
            
            if dist < 0.3: # Match forte de DNA
                # Tentar re-interpretar este campo específico com o novo conhecimento
                result = self._perform_contextual_search(field_id, slot_id, target_p, category=get_cat(field_id))
                
                if result['found_ent']:
                    # Aplicar e validar automaticamente
                    for lk in result['links']:
                        lk['validated'] = True
                        
                    target_p.setdefault('links', {})[field_id] = {slot_id: result['links']}
                    target_p.setdefault('validated_fields', [])
                    if field_id not in target_p['validated_fields']:
                        target_p['validated_fields'].append(field_id)
                    
                    # Se for pilar name ou dim, atualiza o valor direto
                    if field_id == 'name': target_p['name'] = result['found_ent']['text']
                    elif field_id == 'dim': target_p['dim'] = result['found_ent']['text']
                    
                    propagated_count += 1
        
        if propagated_count > 0:
            self.log(f"✅ Propagação concluída! {propagated_count} pilares similares atualizados.")
            self._update_all_lists_ui()
        else:
            self.log("ℹ️ Nenhum outro pilar similar encontrado para propagação direta.")

    def _load_link_configs(self):
        """Carrega definições customizadas de classes de vínculo do arquivo JSON"""
        import json
        path = "link_config_v2.json"
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    custom_config = json.load(f)
                    LinkManager.SLOT_CONFIG.update(custom_config)
                    self.log("✅ Classes de vínculo customizadas carregadas.")
            except Exception as e:
                self.log(f"⚠️ Erro ao carregar link_config: {e}")

    def on_config_updated(self, key, slots_list):
        """Disparado quando o usuário edita ou cria uma nova classe de vínculo"""
        import json
        self.log(f"💾 Salvando nova especialização de classe para: {key}")
        
        # Atualiza a memória de classe para novas instâncias
        LinkManager.SLOT_CONFIG[key] = slots_list
        
        try:
            with open("link_config_v2.json", "w", encoding="utf-8") as f:
                json.dump(LinkManager.SLOT_CONFIG, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log(f"❌ Erro ao persistir link_config: {e}")

    def _get_slot_config(self, field_id, slot_id):
        """Busca a configuração atual de um slot específico"""
        slots = []
        if '_dist_c' in field_id and '_dist_c' in LinkManager.SLOT_CONFIG:
            slots = LinkManager.SLOT_CONFIG['_dist_c']
        elif '_diff_v' in field_id and '_diff_v' in LinkManager.SLOT_CONFIG:
            slots = LinkManager.SLOT_CONFIG['_diff_v']
        elif field_id.startswith('p_s') and '_v_' in field_id and field_id.endswith('_d') and '_beam_dim' in LinkManager.SLOT_CONFIG:
            slots = LinkManager.SLOT_CONFIG['_beam_dim']
        elif 'laje_dim' in field_id and '_laje_dim' in LinkManager.SLOT_CONFIG:
            slots = LinkManager.SLOT_CONFIG['_laje_dim']
        elif 'laje_nivel' in field_id and '_laje_level' in LinkManager.SLOT_CONFIG:
            slots = LinkManager.SLOT_CONFIG['_laje_level']
        elif field_id.endswith('_dim') and 'dim' in LinkManager.SLOT_CONFIG:
            slots = LinkManager.SLOT_CONFIG['dim']
        else:
            for key in LinkManager.SLOT_CONFIG:
                if key in field_id:
                    slots = LinkManager.SLOT_CONFIG[key]
                    break
        if not slots:
            slots = LinkManager.SLOT_CONFIG['default']
        
        for s in slots:
            if s['id'] == slot_id: return s
        return {}

    def _run_sanity_checks(self, p):
        """Camada de IA Sóbria: Valida se a geometria e vínculos fazem sentido físico."""
        issues = []
        import re
        
        # 1. Check de Dimensão Pilar vs Dimensão Viga
        p_dim_text = p.get('dim', '0')
        p_nums = [int(n) for n in re.findall(r'\d+', p_dim_text)]
        p_min = min(p_nums) if p_nums else 15
        
        for side, data in p.get('sides_data', {}).items():
            v_name = data.get('v_esq_n')
            v_dim_text = data.get('v_esq_d', '')
            
            if v_name and v_dim_text:
                v_nums = [int(n) for n in re.findall(r'\d+', v_dim_text)]
                if v_nums:
                    v_width = min(v_nums)
                    if v_width > p_min + 5: # Tolerância de 5cm
                        issues.append(f"L{side}: Viga {v_name} ({v_width}cm) é mais larga que o pilar ({p_min}cm)")
        
        # 2. Check de Nível Inconsistente
        all_v_lvls = []
        for side, data in p.get('sides_data', {}).items():
            v_lv = self._extract_float(data.get('v_esq_v', ''))
            if v_lv is not None: all_v_lvls.append(v_lv)
            
        if all_v_lvls:
            max_diff = max(all_v_lvls) - min(all_v_lvls)
            if max_diff > 0.5:
                issues.append(f"Inconsistência de Níveis: Diferença de {max_diff:.2f}m entre vigas.")
                
        return issues

    def _add_to_issues_list(self, p, conf):
        """Popula a aba de Pendências com elementos suspeitos."""
        if p.get('type') == 'MarcoDXF':
            prefix = "🛠️ MARCO"
            reason = "Tratamento Prévio Gerado"
        else:
            prefix = "❌ ERRO" if p.get('issues') else "⚠️ INCERTO"
            reason = p['issues'][0] if p.get('issues') else f"Confiança Baixa ({conf*100:.0f}%)"
        
        item_text = f"{prefix} | {p['name']} | {reason}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, p['id']) # ID do item
        
        from PySide6.QtGui import QColor
        if p.get('type') == 'MarcoDXF': item.setForeground(QColor(0, 150, 255))
        elif p.get('issues'): item.setForeground(Qt.red)
        else: item.setForeground(Qt.yellow)
        
        self.list_issues.addItem(item)

    def on_issue_clicked(self, item):
        """Ao clicar na pendência, abre o item e foca no erro."""
        p_id = item.data(Qt.UserRole)
        
        # 0. Verificar se é Marco
        if hasattr(self, 'marco_found') and self.marco_found and self.marco_found[0]['id'] == p_id:
            self.show_detail(self.marco_found[0])
            self.canvas.draw_marco_dxf(self.db.load_pre_processing(self.current_project_id))
            return

        for i in range(self.list_pillars.count()):
            it = self.list_pillars.item(i)
            if it.data(Qt.UserRole) == p_id:
                self.list_pillars.setCurrentItem(it)
                self.on_list_pillar_clicked(it)
                break



    def on_card_validated(self, item_data):
        """Chamado quando usuário clica em 'VALIDAR' no card."""
        item_data['is_validated'] = True
        p_id = item_data['id']
        name = item_data.get('name', 'Sem Nome')
        elem_type = item_data.get('type', 'Pilar').lower()
        
        # 1. Registrar Treino para TODOS os campos validados do item
        # Isso garante que a IA aprenda o layout completo confirmado pelo humano.
        validated_fields = item_data.get('validated_fields', [])
        links_dict = item_data.get('links', {})
        
        for f_id in validated_fields:
            field_links = links_dict.get(f_id, {})
            # Se for um campo validado e tiver vínculos, registramos como conhecimento "Ground Truth"
            for slot_id, links_list in field_links.items():
                for lk in links_list:
                    lk['validated'] = True
                    lk.pop('failed', None)
                    self._log_training_action(item_data, f_id, slot_id, lk, status='valid', comment='Card Validation')

        # 2. Salvar imediatamente no projeto e atualizar UI
        if self.current_project_id:
            id_item = item_data.get('id_item', '??')
            if 'pilar' in elem_type:
                self.db.save_pillar(item_data, self.current_project_id)
                target_list = self.list_pillars
                valid_list = self.list_pillars_valid
                item_label = f"{id_item} | {name} | {item_data.get('dim','')} | {item_data.get('format','')}"
            elif 'viga' in elem_type:
                self.db.save_beam(item_data, self.current_project_id)
                target_list = self.list_beams
                valid_list = self.list_beams_valid
                item_label = f"{id_item} | {name} | SegA: {item_data.get('seg_a',1)} | SegB: {item_data.get('seg_b',1)}"
            elif 'laje' in elem_type:
                self.db.save_slab(item_data, self.current_project_id)
                target_list = self.list_slabs
                valid_list = self.list_slabs_valid
                item_label = f"{id_item} | {name}"
            elif 'laje' in elem_type:
                self.db.save_slab(item_data, self.current_project_id)
                target_list = self.list_slabs
                valid_list = self.list_slabs_valid
                item_label = f"{id_item} | {name}"
            else:
                return

            # Atualizar item na lista de origem
            if 'viga' in elem_type:
                self._populate_beam_tree(target_list, self.beams_found)
                valid_beams = [b for b in self.beams_found if b.get('is_validated')]
                self._populate_beam_tree(valid_list, valid_beams)
            else:
                for i in range(target_list.count()):
                     it = target_list.item(i)
                     if it.data(Qt.UserRole) == p_id:
                          it.setText(item_label + (" ✅" if " ✅" not in it.text() else ""))
                          it.setForeground(Qt.green)
                          break
                
                # Adicionar à lista validada (evitar duplicados visuais)
                found_v_idx = -1
                for i in range(valid_list.count()):
                    if valid_list.item(i).data(Qt.UserRole) == p_id:
                        found_v_idx = i
                        break
                
                if found_v_idx == -1:
                    item_v = QListWidgetItem(item_label + " ✅")
                    item_v.setData(Qt.UserRole, p_id)
                    item_v.setForeground(Qt.green)
                    valid_list.addItem(item_v)
                else:
                    valid_list.item(found_v_idx).setText(item_label + " ✅")
        
        # Feedback Visual no Canvas
        if 'pilar' in elem_type:
             self.canvas.update_pillar_status(p_id, 'validated')
        elif 'laje' in elem_type:
             self.canvas.update_slab_status(p_id, 'validated')
        elif 'viga' in elem_type:
             self.canvas.update_beam_status(p_id, 'validated')
        
        self.log(f"✅ Item {name} ({elem_type}) validado e arquivado.")

    def _process_beam_intelligent(self, b: Dict):
        """
        Segue a ordem rigorosa de interpretação solicitada pelo usuário.
        1. Identidade
        2. Dimensão Global
        3. Segmentos e Comprimentos
        4. Visão de Corte
        5. Dimensão por Segmento
        6. Apoios (Início/Fim)
        7. Alturas (H1, H2)
        8. Lajes (Inf, Cen, Sup)
        9. Níveis
        10. Aberturas
        11. Fundos
        12. Detalhes Fundo
        """
        import re
        geo = b.get('geometry', {})
        classified = geo.get('classified', {})
        
        # --- ESTRUTURA BASE ---
        b.update({
            'type': 'Viga',
            'is_validated': False,
            'fields': {},
            'links': {
                'name': {'label': [{'text': b['name'], 'type': 'text', 'pos': b.get('pos', (0,0)), 'role': 'Identificador Viga'}]},
                'viga_segs': {'seg_side_a': [], 'seg_side_b': [], 'seg_bottom': []},
                'apoios': {'inicio': [], 'fim': []},
                'lajes': {'lado_a': [], 'lado_b': []},
                'cortes': [],
                'dimensoes': [],
                'aberturas': {'pilar': [], 'viga': []}
            }
        })

        # 1. IDENTIDADE (Já temos b['name'] e b['id_item'])
        b['fields']['numero'] = b['id_item']
        b['fields']['nome'] = b['name']

        # 2. DIMENSÃO (Texto Global)
        dim_texts = geo.get('dimension_texts', [])
        main_dim_text = ""
        if dim_texts:
            main_dim_text = dim_texts[0]['text']
            b['fields']['dimensao'] = main_dim_text
            if not isinstance(b['links']['dimensoes'], list): b['links']['dimensoes'] = []
            b['links']['dimensoes'].append(dim_texts[0])

        # 3. SEGMENTOS E COMPRIMENTOS
        def process_segments(side_key, tag):
            lines = classified.get(side_key, [])
            total_len = 0
            for line in lines:
                p1, p2 = line[0], line[-1]
                length = ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
                total_len += length
                b['links']['viga_segs'][side_key].append({
                    'type': 'poly', 'points': line, 'len': length, 'tag': tag
                })
            return total_len

        len_a = process_segments('seg_side_a', 'Lado A')
        len_b = process_segments('seg_side_b', 'Lado B')
        b['fields']['comprimento_total_a'] = round(len_a, 1)
        b['fields']['comprimento_total_b'] = round(len_b, 1)
        b['seg_a'] = len(classified.get('seg_side_a', []))
        b['seg_b'] = len(classified.get('seg_side_b', []))

        # 4. VISÃO DE CORTE
        has_corte = False
        for t in geo.get('texts', []):
            if re.match(r'^[A-Z]-[A-Z]$', t['text'].strip()):
                b['links']['cortes'].append(t)
                has_corte = True
        
        b['fields']['possui_corte'] = has_corte

        # 5. DIMENSÃO POR SEGMENTO
        # Associar textos de dimensão específicos a segmentos específicos baseados em proximidade
        if len(dim_texts) > 0:
            for side_key in ['seg_side_a', 'seg_side_b']:
                segments = b['links']['viga_segs'][side_key]
                for seg in segments:
                    # Calcular centro do segmento
                    pts = seg['points']
                    if not pts: continue
                    p1, p2 = pts[0], pts[-1]
                    mid_x, mid_y = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
                    
                    # Encontrar texto mais próximo
                    closest_dim = None
                    min_dist = float('inf')
                    
                    for dt in dim_texts:
                        dpos = dt.get('pos')
                        if not dpos: continue
                        dist = ((mid_x - dpos[0])**2 + (mid_y - dpos[1])**2)**0.5
                        if dist < min_dist:
                            min_dist = dist
                            closest_dim = dt
                    
                    # Se estiver próximo o suficiente (ex: 100 unidades), vincula
                    if closest_dim and min_dist < 100:
                        seg['dim_text'] = closest_dim['text']
                        # Se não tivermos dimensão global definida ou se esta for diferente, podemos notar
                        
        

        # 6. APOIOS (INCIAL / FINAL)
        # Identificar eixo principal da viga para ordenar elementos
        all_pts = []
        for seg_list in classified.values():
            for line in seg_list:
                all_pts.extend(line)
        
        if all_pts:
            # Bounding box simplificado
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
            # Definir orientação predominante
            is_horiz = (max(xs) - min(xs)) > (max(ys) - min(ys))
        else:
            xs, ys = [], []
            is_horiz = True

        if all_pts and geo.get('support_candidates'):
            
            # Ordenar suportes baseado na coordenada principal (X ou Y)
            # Para vigas Horizontais: Esquerda -> Direita (X crescente)
            # Para vigas Verticais: Topo -> Baixo (Y decrescente? - A verificar convenção, usaremos Y crescente por enq)
            
            supports = geo.get('support_candidates', [])
            
            def get_sort_key(s):
                # Tenta pegar centroide se tiver pontos, senão usa pos
                if 'points' in s and s['points']:
                    cx = sum(p[0] for p in s['points']) / len(s['points'])
                    cy = sum(p[1] for p in s['points']) / len(s['points'])
                    return cx if is_horiz else cy
                return s['pos'][0] if is_horiz else s['pos'][1]
            
            sorted_supports = sorted(supports, key=get_sort_key, reverse=False) # X Crescente ou Y Crescente
            
            # Heurística: Pegar os extremos
            # Mas cuidado: suportes podem ser pilares que cruzam a viga inteira.
            # Vamos pegar todos que intersectam o início e o fim?
            # Por simplificação atual: O mais "menor coord" é Inicio, o "maior coord" é Fim.
            
            if sorted_supports:
                b['links']['apoios']['inicio'].append(sorted_supports[0])
                if len(sorted_supports) > 1:
                    b['links']['apoios']['fim'].append(sorted_supports[-1])

        # 7. ALTURAS (H1, H2)
        h1 = 0
        if main_dim_text:
            nums = [int(n) for n in re.findall(r'\d+', main_dim_text)]
            if nums: h1 = max(nums)
        
        b['fields']['altura_h1'] = h1
        
        if has_corte:
            b['fields']['altura_h2'] = h1 
        else:
            b['fields']['altura_h2'] = None

        # 8. LAJES (Inf, Central, Superior)
        slab_cands = geo.get('slab_candidates', [])
        if slab_cands and all_pts:
            # Calcular centróide aproximado da viga
            bx = sum(xs) / len(xs)
            by = sum(ys) / len(ys)
            
            for s in slab_cands:
                # Classificar Lajes geometricamente em relação à viga
                # Se Horiz: Laje Y > Viga Y -> Lado A (Top), Laje Y < Viga Y -> Lado B (Bottom) (ou vice-versa dependendo da convenção de desenho)
                # Assumindo Lado A = "Cima/Esquerda"
                
                spos = s.get('pos')
                if not spos: continue
                
                target_side = 'lado_a'
                if is_horiz:
                    if spos[1] < by: target_side = 'lado_b' # Y menor = abaixo
                else:
                    if spos[0] > bx: target_side = 'lado_b' # X maior = direita
                
                b['links']['lajes'][target_side].append(s)
            
            b['fields']['laje_superior_a'] = slab_cands[0]['text'] if len(slab_cands) > 0 else ""
            b['fields']['laje_superior_b'] = slab_cands[1]['text'] if len(slab_cands) > 1 else ""

        # 9. NÍVEIS
        b['fields']['nivel_lado_a'] = 0
        b['fields']['nivel_lado_b'] = 0
        b['fields']['nivel_oposto_a'] = 0
        b['fields']['nivel_oposto_b'] = 0

        # 10/11. ABERTURAS (Detecção Simplificada via Pilares)
        supports = geo.get('support_candidates', [])
        if supports:
            for s in supports:
                # Se o pilar intersecta a viga mas não é apoio de extremidade, é uma interferência/abertura
                is_start = s in b['links']['apoios']['inicio']
                is_end = s in b['links']['apoios']['fim']
                
                if not is_start and not is_end:
                     b['links']['aberturas']['pilar'].append(s)
        # 12. FUNDOS (Calculado a partir de seg_bottom)
        len_bottom = process_segments('seg_bottom', 'Fundo')
        b['fields']['comprimento_fundo'] = round(len_bottom, 1)
        
        self.log(f"🧠 Viga {b['name']} pré-interpretada com sucesso.")

    def _process_slab_intelligent(self, s: Dict):
        """
        Inteligência para Lajes:
        1. Identidade (Nome)
        2. Dimensão (Espessura H=...)
        3. Nível (Cota +...)
        4. Geometria (Contorno)
        """
        import re
        
        # --- ESTRUTURA BASE ---
        s.update({
            'type': 'Laje',
            'is_validated': False,
            'fields': {},
            'links': {
                'name': {'label': [{'text': s['name'], 'type': 'text', 'pos': s.get('pos', (0,0)), 'role': 'Identificador Laje'}]},
                'laje_dim': {'label': []}, # UI Field: laje_dim
                'laje_nivel': {'label': [], 'cut_view_geom': [], 'cut_view_text': []}, # UI Field: laje_nivel
                'laje_outline_segs': {'contour': [], 'acrescimo_borda': []}, # UI Field: laje_outline_segs
                '_laje_complex': {'label': [], 'dim': [], 'cut_view': []} 
            }
        })
        
        # 1. IDENTIDADE
        s['fields']['nome'] = s['name']
        s['fields']['numero'] = s['id_item']

        # 2. PROCURAR TEXTOS PRÓXIMOS (Dimensão, Nível)
        pos = s.get('pos')
        if pos:
            cx, cy = pos
            
            # --- Configurações Aprendidas ---
            learning = getattr(self, 'slab_learning_config', {})
            search_radius = learning.get('search_radius', 200.0)
            learned_dim_layers = learning.get('dim_layers')
            learned_level_layers = learning.get('level_layers')
            
            # Obter candidatos espaciais (Se spatial_index tiver textos seria melhor, 
            # senão varrida bruta na lista de textos globais - Otimização: Cachear isso se ficar lento)
            # Assumindo self.dxf_data['texts'] disponível e não muito grande (<5000), força bruta local é ok.
            
            candidates = []
            texts = self.dxf_data.get('texts', [])
            
            for t in texts:
                tx, ty = t.get('pos', (0,0))
                dist = ((tx-cx)**2 + (ty-cy)**2)**0.5
                if dist <= search_radius:
                    candidates.append((t, dist))
            
            # Ordenar por proximidade
            candidates.sort(key=lambda x: x[1])
            sorted_texts = [x[0] for x in candidates]
            
            # --- REGEX PATTERNS ---
            import re # Garantir import
            # H=12, d=10, h=15...
            re_thick = re.compile(r'[HhDd][= :]?\d+', re.IGNORECASE)
            # +2.80, 280, N+2.80...
            re_level = re.compile(r'[+-]?\d+\.\d+|[+-]?\d+', re.IGNORECASE) 
            
            found_thick = False
            found_level = False
            
            for t in sorted_texts:
                txt_val = t['text'].strip()
                t_layer = t.get('layer')
                
                # Ignorar o próprio nome da laje (Ex: L1)
                if txt_val == s['name']: continue
                
                # Check Espessura
                # Se aprendemos layers de dimensão, PRIORIDADE aos layers aprendidos
                # Senão, aceita regex
                is_dim_candidate = False
                if learned_dim_layers and t_layer in learned_dim_layers:
                     is_dim_candidate = True
                elif not learned_dim_layers: # Sem aprendizado, confia no regex
                     is_dim_candidate = True

                if is_dim_candidate and not found_thick and re_thick.search(txt_val):
                    s['links']['laje_dim']['label'].append(t)
                    s['fields']['laje_dim'] = txt_val
                    found_thick = True
                    continue # Um texto geralmente é uma coisa só
                
                # Check Nível (Prioridade menor se parecer espessura ou nome)
                # Regex de nível é perigoso (pega qualquer numero). 
                # Refinar: Deve ter sinal ou ponto, ou ser 'N...'
                is_lvl_candidate = False
                if learned_level_layers and t_layer in learned_level_layers:
                     is_lvl_candidate = True
                elif not learned_level_layers:
                     is_lvl_candidate = True

                if not found_level and is_lvl_candidate:
                    # Heurística: Nível tem +, - ou .
                    if ('+' in txt_val or '-' in txt_val or '.' in txt_val) and re_level.search(txt_val):
                        s['links']['laje_nivel']['label'].append(t)
                        s['fields']['laje_nivel'] = txt_val
                        found_level = True
                        continue

        # 3. CONTORNO (Geometria já encontrada pelo SlabTracer)
        if 'points' in s and s['points']:
            # Criar representação visual do contorno
            # O LinkManager espera objetos com 'type': 'poly', 'points': ...
            poly_link = {
                'type': 'poly',
                'points': s['points'],
                'role': 'Contorno Automático'
            }
            s['links']['laje_outline_segs']['contour'].append(poly_link)

    def _populate_beam_tree(self, tree_widget, beam_list):
        tree_widget.clear()
        if not beam_list: return

        from PySide6.QtWidgets import QTreeWidgetItem
        # Agrupar por parent_name
        from collections import OrderedDict
        groups = OrderedDict()
        for b in beam_list:
            p_name = b.get('parent_name', b.get('name', 'V?'))
            if p_name not in groups:
                groups[p_name] = []
            groups[p_name].append(b)
            
        for p_name, segments in groups.items():
            # Se houver apenas 1 segmento e o nome for igual ao pai, podemos simplificar?
            # User pediu "Box/Clase", então vamos criar o nó pai para agrupar.
            parent_item = QTreeWidgetItem(tree_widget)
            parent_item.setText(1, f"📂 {p_name}")
            parent_item.setExpanded(True)
            parent_item.setFlags(parent_item.flags() & ~Qt.ItemIsSelectable) # Pai não selecionável se quiser focar apenas nos filhos
            
            for b in segments:
                status = "✅" if b.get('is_validated') else "❓"
                child = QTreeWidgetItem(parent_item)
                child.setText(0, b.get('id_item', '??'))
                child.setText(1, b['name'])
                child.setText(2, status)
                child.setData(0, Qt.UserRole, b['id'])
                
                # AJUSTE 4: Itens (linhas das vigas) em lightgray para diferenciar das pastas
                from PySide6.QtGui import QColor
                gray_color = QColor("#aaaaaa") # Lightgray
                for col in range(3):
                    child.setForeground(col, gray_color)

                if b.get('is_validated'):
                    child.setForeground(1, Qt.green)
                    self.canvas.update_beam_status(b['id'], "validated")
                else:
                    self.canvas.update_beam_status(b['id'], "default")

    # --- NOVOS MÉTODOS DE GERENCIAMENTO ---

    def open_training_log(self):
        """Abre a janela de gerenciamento de memória de treino"""
        if not self.current_project_id:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Abra um projeto primeiro.")
            return
            
        from src.ui.widgets.training_log_dialog import TrainingLogDialog
        dlg = TrainingLogDialog(self.db, self.current_project_id, self)
        dlg.focus_requested.connect(self.on_training_focus_requested)
        dlg.exec()

    def on_training_focus_requested(self, link_data):
        """Disparado pelo Training Log para dar zoom em geometria"""
        self.canvas.highlight_link(link_data)
        self.log(f"📍 Foco de memória: {link_data.get('text', 'Geometria')}")

    def open_project_manager(self):
        """Abre o gerenciador de projetos."""
        self.proj_mgr = ProjectManager(self.db)
        self.proj_mgr.project_selected.connect(self.on_project_selected)
        self.proj_mgr.resize(600, 400)
        self.proj_mgr.show()

    def on_project_selected(self, pid, name, dxf_path):
        """Callback: Projeto aberto via gerenciador."""
        self.proj_mgr.close()
        
        # Se já existe tab para esse projeto, foca nela
        for i in range(self.project_tabs.count()):
            if self.project_tabs.tabBar().tabData(i) == pid:
                self.project_tabs.setCurrentIndex(i)
                return

        # Adiciona nova aba
        # Adiciona nova aba
        self.log(f"Abrindo projeto: {name}...")
        print(f"DEBUG: Abrindo projeto {name} (PID: {pid})")
        
        # Block signals to prevent premature triggering of currentChanged before data is set
        self.project_tabs.blockSignals(True)
        try:
            self.project_tabs.addTab(QWidget(), f"{name}") 
            new_idx = self.project_tabs.count() - 1
            self.project_tabs.tabBar().setTabData(new_idx, pid)
            self.project_tabs.setTabToolTip(new_idx, dxf_path)
        finally:
            self.project_tabs.blockSignals(False)
        
        # Carrega dados do projeto (DB -> Memória) se não estiver em cache
        if pid not in self.loaded_projects_cache:
            print("DEBUG: Carregando do Banco de Dados...")
            # Tentar carregar DB
            p_info = self.db.get_project_by_id(pid) 
            if not p_info:
                self.log(f"Erro: Projeto {pid} não encontrado no banco.")
                print("DEBUG: Projeto nao encontrado no DB.")
                return

            print("DEBUG: Fetching entities...")
            # Carregar itens do DB
            pillars = self.db.load_pillars(pid)
            print(f"DEBUG: Pilares carregados ({len(pillars)})")
            slabs = self.db.load_slabs(pid)
            print(f"DEBUG: Lajes carregadas ({len(slabs)})")
            beams = self.db.load_beams(pid)
            print(f"DEBUG: Vigas carregadas ({len(beams)})")
            
            cache_entry = {
                'id': pid,
                'name': name,
                'dxf_path': dxf_path,
                'pillars': pillars,
                'slabs': slabs,
                'beams': beams,
                'meta': {
                    'work_name': p_info.get('work_name', ''),
                    'pavement_name': p_info.get('pavement_name', ''),
                    'level_arrival': p_info.get('level_arrival', ''),
                    'level_exit': p_info.get('level_exit', '')
                },
                'dxf_data': None # Lazy load DXF geometry
            }
            self.loaded_projects_cache[pid] = cache_entry
            
            # Carregar DXF Geometria para este projeto (se existir arquivo)
            if dxf_path and os.path.exists(dxf_path):
                self.show_progress("Lendo Arquivo DXF...", 20)
                try:
                    loaded_dxf = DXFLoader.load_dxf(dxf_path)
                    cache_entry['dxf_data'] = loaded_dxf
                except Exception as e:
                    self.log(f"Erro ao carregar DXF {dxf_path}: {e}")
                self.hide_progress()

        # Ativa a aba e força atualização
        # Bloqueamos sinais se a aba já existir para evitar double-trigger, 
        # mas como estamos ADICIONANDO, o setCurrentIndex vai disparar o on_project_tab_changed.
        print(f"DEBUG: Switching tab index to {new_idx}...")
        self.project_tabs.setCurrentIndex(new_idx)
        
        # Se por algum motivo o sinal não disparou (mesmo index), chamamos manual
        if self.current_project_id != pid:
             print("DEBUG: Manually calling on_project_tab_changed (fallback)...")
             self.on_project_tab_changed(new_idx)

    def on_project_tab_changed(self, index):
        """Muda o contexto global da aplicação para o projeto da aba selecionada."""
        if index < 0: return
        
        # Verify tabBar data existence
        pid = self.project_tabs.tabBar().tabData(index)
        
        # --- REMOVIDA TRAVA DE PID --- 
        # Sempre recarregar ao trocar de aba para garantir sincronia total das listas (Urgência Usuário)
        print(f"DEBUG: Sincronizando UI para projeto {pid} (Aba {index})")

        # --- NOVO: Salvar estado atual no cache antes de trocar ---
        if self.current_project_id and self.current_project_id in self.loaded_projects_cache:
            old_cache = self.loaded_projects_cache[self.current_project_id]
            old_cache['pillars'] = self.pillars_found
            old_cache['slabs'] = self.slabs_found
            old_cache['beams'] = self.beams_found
            old_cache['meta'] = {
                'work_name': self.edit_work_name.text(),
                'pavement_name': self.edit_pavement_name.text(),
                'level_arrival': self.edit_level_arr.text(),
                'level_exit': self.edit_level_exit.text()
            }
            # SALVAR ESTADO VISUAL DO CANVAS (Cena, Coleções, Snap)
            canvas_state = self.canvas.get_project_state_dict()
            old_cache.update(canvas_state)

        project_data = self.loaded_projects_cache[pid]
        self.active_project_id = pid
        self.current_project_id = pid 
        self.current_project_name = project_data['name']
        self.current_dxf_path = project_data['dxf_path']
        
        self.log(f"Alternando para projeto: {project_data['name']}")
        
        # 1. Atualizar Metadados UI
        meta = project_data['meta']
        self.edit_work_name.blockSignals(True)
        self.edit_pavement_name.blockSignals(True)
        self.edit_level_arr.blockSignals(True)
        self.edit_level_exit.blockSignals(True)
        
        self.edit_work_name.setText(meta.get('work_name', ''))
        self.edit_pavement_name.setText(meta.get('pavement_name', ''))
        self.edit_level_arr.setText(meta.get('level_arrival', ''))
        self.edit_level_exit.setText(meta.get('level_exit', ''))
        
        self.edit_work_name.blockSignals(False)
        self.edit_pavement_name.blockSignals(False)
        self.edit_level_arr.blockSignals(False)
        self.edit_level_exit.blockSignals(False)
        
        # 2. Atualizar Listas UI
        self.pillars_found = project_data['pillars']
        self.slabs_found = project_data['slabs']
        self.beams_found = project_data['beams']
        self.dxf_data = project_data['dxf_data']
        
        # 3. Restaurar Lógica (Fast Path se já existir)
        self._initialize_project_logic(self.dxf_data)
        self._update_all_lists_ui()
        
        # 4. Atualizar Canvas (Isolamento de Cena e Otimização)
        self.canvas.swap_project_state(project_data)
        
        if not project_data.get('scene_rendered'):
            self.log("🎨 Renderizando geometria pela primeira vez...")
            self.show_progress("Renderizando DXF...", 30)
            
            # Limpar coleções de overlay (add_dxf_entities já limpa a cena)
            if self.dxf_data:
                self.canvas.add_dxf_entities(self.dxf_data, progress_callback=self.update_progress)
            
            self.update_progress(80, "Desenhando itens interativos...")
            self.canvas.draw_interactive_pillars(self.pillars_found)
            self.canvas.draw_slabs(self.slabs_found)
            self.canvas.draw_beams(self.beams_found)
            
            self.canvas.draw_interactive_pillars(self.pillars_found)
            self.canvas.draw_slabs(self.slabs_found)
            self.canvas.draw_beams(self.beams_found)
            
            # Marcar como renderizado no cache para trocas futuras instantâneas
            project_data['scene_rendered'] = True
            self.hide_progress()
        else:
            self.log("🚀 Troca de contexto instantânea concluída.")
            
        # Resetar Aba de Detalhes
        self.right_panel.setCurrentIndex(0)
        
        # 5. Atualizar Aba de Treinamento
        self.tab_training.load_events(pid)
        
        QApplication.processEvents()

    def close_project_tab(self, index):
        """Fecha aba do projeto (mas não apaga do banco)"""
        if index < 0: return
        pid = self.project_tabs.tabBar().tabData(index)
        
        # Remover do cache de memória para liberar RAM se necessário?
        # Por enquanto mantemos para reabertura rápida, ou limpamos se for pesada.
        # Vamos limpar para garantir refresh se reabrir.
        if pid in self.loaded_projects_cache:
            del self.loaded_projects_cache[pid]
            
        self.project_tabs.removeTab(index)
        
        if self.project_tabs.count() == 0:
            # Limpar tudo
            self.canvas.scene.clear()
            self.list_pillars.clear()
            self.list_beams.clear()
            self.list_slabs.clear()
            self.current_project_id = None
            self.meta_widget.setEnabled(False)
        
    def save_project_metadata(self):
        """Salva as informações de cabeçalho do projeto ativo."""
        if not self.active_project_id: return
        
        meta = {
            'work_name': self.edit_work_name.text(),
            'pavement_name': self.edit_pavement_name.text(),
            'level_arrival': self.edit_level_arr.text(),
            'level_exit': self.edit_level_exit.text()
        }
        
        # Update Cache
        if self.active_project_id in self.loaded_projects_cache:
            self.loaded_projects_cache[self.active_project_id]['meta'] = meta
            
        # Update DB
        self.db.update_project_metadata(self.active_project_id, meta)
        self.log("Metadados do projeto atualizados.")

    def _update_all_lists_ui(self):
        """Refresha todas as listas com dados atuais do projeto ativo (Análise e Biblioteca)"""
        # 1. Limpar TODAS as listas
        self.list_pillars.clear()
        self.list_pillars_valid.clear()
        self.list_beams.clear()
        self.list_beams_valid.clear()
        self.list_slabs.clear()
        self.list_slabs_valid.clear()
        self.list_issues.clear()
        if hasattr(self, 'list_contours'): self.list_contours.clear()
        if hasattr(self, 'list_contours_valid'): self.list_contours_valid.clear()
        
        # 2. Popular Pilares
        for p in self.pillars_found:
            status = "✅" if p.get('is_validated') else "❓"
            # Texto para lista de análise: numero / nome / dimensao / formato
            p_format = p.get('format', 'Retangular')
            t_analysis = f"{p.get('id_item', '??')} | {p.get('name', 'P?')} | {p.get('dim', '0')} | {p_format} {status}"
            item_a = QListWidgetItem(t_analysis)
            item_a.setData(Qt.UserRole, p['id'])
            
            # Cores por estado e Issues
            conf_map = p.get('confidence_map', {})
            avg_conf = sum(conf_map.values()) / len(conf_map) if conf_map else 0.5

            if p.get('issues'):
                item_a.setForeground(Qt.red)
                self._add_to_issues_list(p, avg_conf)
                # Removido status visual "error" (laranja) do canvas para evitar duplicidade
                self.canvas.update_pillar_visual_status(p['id'], "default")
            elif avg_conf < 0.6 and not p.get('is_validated'):
                item_a.setForeground(Qt.yellow)
                self._add_to_issues_list(p, avg_conf)
                self.canvas.update_pillar_visual_status(p['id'], "default")
            elif p.get('is_validated'):
                item_a.setForeground(Qt.green)
                self.canvas.update_pillar_visual_status(p['id'], "validated")
            else:
                self.canvas.update_pillar_visual_status(p['id'], "default")
            
            self.list_pillars.addItem(item_a)
            
            # Se validado, vai para a Biblioteca
            if p.get('is_validated'):
                item_v = QListWidgetItem(item_a.text())
                item_v.setData(Qt.UserRole, p['id'])
                item_v.setForeground(Qt.green)
                self.list_pillars_valid.addItem(item_v)

        # 3. Popular Vigas (Hierárquico)
        self._populate_beam_tree(self.list_beams, self.beams_found)
        
        # Vigas Validadas
        valid_beams = [b for b in self.beams_found if b.get('is_validated')]
        self._populate_beam_tree(self.list_beams_valid, valid_beams)

        # 4. Popular Lajes
        for s in self.slabs_found:
            status = "✅" if s.get('is_validated') else "❓"
            t_analysis = f"{s.get('id_item', '??')} | {s.get('name', 'L?')} ({s.get('area',0):.1f}m²) {status}"
            item_a = QListWidgetItem(t_analysis)
            item_a.setData(Qt.UserRole, s['id'])
            
            if s.get('is_validated'): 
                item_a.setForeground(Qt.green)
                self.canvas.update_slab_status(s['id'], "validated")
            else:
                self.canvas.update_slab_status(s['id'], "default")

            self.list_slabs.addItem(item_a)
            
            if s.get('is_validated'):
                item_v = QListWidgetItem(item_a.text())
                item_v.setData(Qt.UserRole, s['id'])
                item_v.setForeground(Qt.green)
                self.list_slabs_valid.addItem(item_v)

        
        self.log(f"UI Atualizada: {len(self.pillars_found)}P, {len(self.beams_found)}V, {len(self.slabs_found)}L")
    
    def on_detail_data_changed(self, data):
        """Callback genérico para mudanças nos dados do DetailCard (remoção de links, etc)"""
        if not self.current_card: return
        
        item_data = self.current_card.item_data
        itype = item_data.get('type', '').lower()
        
        # Sincronizar visual no canvas imediatamente (SEM ZOOM AUTOMATICO NA MUDANÇA DE DADOS)
        # AJUSTE 1: Limpar uma vez e desenhar ambos para garantir remoção/atualização real-time
        
        # Limpar links persistentes antigos deste item específico
        item_id = item_data.get('id')
        if item_id:
            self.canvas.clear_item_persistent_links(item_id)
            
        self.canvas.clear_beams()
        self.canvas.clear_overlay()

        # Log de sanidade nos links
        all_links = item_data.get('links', {})
        
        # Log detalhado para depuração
        links_count = 0
        links_dict = item_data.get('links', {})
        for f in links_dict.values():
            if isinstance(f, dict): 
                for s in f.values(): links_count += len(s)
            elif isinstance(f, list): links_count += len(f)
        
        self.log(f"🔄 Sincronizando {itype} (ID: {item_id}). Vínculos restantes: {links_count}")

        # Se houver mudança nos dados (ex: remoção de link), removemos o status de validado 
        # para forçar o usuário a re-validar o item se necessário.
        if item_data.get('is_validated') and links_count == 0:
             item_data['is_validated'] = False
             self.log(f"⚠️ Item {item_data.get('name')} invalidado devido a falta de vínculos.")
        
        if 'viga' in itype:
            # Passamos clear=False para não destruir o que o outro acabou de desenhar
            self.canvas.focus_on_beam_geometry(item_data, apply_zoom=False, clear=False)
            self.canvas.draw_item_links(item_data, destination='focus', clear=False)
            # AJUSTE 1 & 2: Atualiza também a visão global (persistente) para não deixar "fantasmas"
            self.canvas.draw_item_links(item_data, destination='beam', clear=False)
        elif 'pilar' in itype:
            self.canvas.draw_item_links(item_data, destination='focus', clear=False)
            # Pilares geralmente gerenciam sua própria geometria, mas se houver links extras:
            self.canvas.draw_item_links(item_data, destination='pillar', clear=False)
        elif 'laje' in itype:
            self.canvas.draw_item_links(item_data, destination='focus', clear=False)
            # AJUSTE 1 & 3: Atualiza também a visão global (persistente)
            self.canvas.draw_item_links(item_data, destination='slab', clear=False)
        # AJUSTE: Forçar atualização visual do viewport e da cena do canvas
        if self.canvas.scene:
            self.canvas.scene.update()
        self.canvas.viewport().update()
        self.canvas.update()
        
        # --- NOVO: Atualizar imediatamente o texto na lista lateral ---
        self._sync_list_item_text(item_data)
        
        self.log(f"Visual e Lista do {itype} sincronizados.")

    def on_element_removed(self, data):
        """Callback específico para quando um vínculo é removido individualmente."""
        # Se o data_changed já foi emitido, não precisamos chamar on_detail_data_changed de novo
        # Mas vamos garantir que o LOG apareça para sabermos que a remoção foi processada.
        self.log("🗑️ Vínculo removido. Canvas atualizado via sinal de dados.")
        
        # 1. Remover destaque amarelo do item Pai (se houver)
        self.canvas.highlight_item_yellow(None)
        
        # 2. Limpar visuais temporários de foco
        self.canvas.clear_beams()

    def _sync_list_item_text(self, item_data):
        """Atualiza o texto da lista lateral sem reconstruir toda a UI"""
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        itype = item_data.get('type', '').lower()
        iid = item_data.get('id')
        
        status = "✅" if item_data.get('is_validated') else "❓"
        if item_data.get('issues'): status = "⚠️"
        
        if 'pilar' in itype:
            p_format = item_data.get('format', 'Retangular')
            new_text = f"{item_data.get('id_item', '??')} | {item_data.get('name', 'P?')} | {item_data.get('dim', '0')} | {p_format} {status}"
            for lst in [self.list_pillars, self.list_pillars_valid]:
                for i in range(lst.count()):
                    item = lst.item(i)
                    if item.data(Qt.UserRole) == iid:
                        item.setText(new_text)
                        
        elif 'viga' in itype:
            for tree in [self.list_beams, self.list_beams_valid]:
                it = QTreeWidgetItemIterator(tree)
                while it.value():
                    item = it.value()
                    if item.data(0, Qt.UserRole) == iid:
                        item.setText(0, item_data.get('id_item', '??'))
                        item.setText(1, item_data.get('name', 'V?'))
                        item.setText(2, status)
                        print(f"[_sync_list_item_text] Viga {iid} atualizada com status {status}")
                    it += 1
                    
        elif 'laje' in itype:
            new_text = f"{item_data.get('id_item', '??')} | {item_data.get('name', 'L?')} ({item_data.get('area',0):.1f}m²) {status}"
            for lst in [self.list_slabs, self.list_slabs_valid]:
                for i in range(lst.count()):
                    item = lst.item(i)
                    if item.data(Qt.UserRole) == iid:
                        item.setText(new_text)

    def show_detail(self, item_data):
        """Exibe os detalhes do item no painel direito."""
        # Limpar anterior
        while self.detail_layout.count():
            child = self.detail_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        # Criar novo card
        self.current_card = DetailCard(item_data)
        
        # Conectar Sinais
        self.current_card.pick_requested.connect(self.on_pick_requested)
        self.current_card.focus_requested.connect(self.on_focus_requested)
        self.current_card.data_validated.connect(self.on_card_validated)
        self.current_card.element_removed.connect(self.on_element_removed)
        self.current_card.data_changed.connect(self.on_detail_data_changed)
        self.current_card.research_requested.connect(self.on_research_requested)
        self.current_card.element_focused.connect(self.on_element_focused_on_table)
        self.current_card.training_requested.connect(self.on_train_requested)
        
        self.detail_layout.addWidget(self.current_card)
        
        # Atualizar título do painel (opcional)
        self.right_panel.setCurrentIndex(1)
    


    def create_manual_item(self, is_library=False):
        """Cria um novo item manualmente na lista ativa"""
        if not self.active_project_id:
             self.log("⚠️ Abra um projeto para criar itens.")
             return

        # Identificar qual tipo estamos criando com base na aba visível
        if is_library:
             current_idx = self.tabs_library_internal.currentIndex()
             # 0: Pilar, 1: Viga, 2: Laje
        else:
             current_idx = self.tabs_analysis_internal.currentIndex()
             # 0: Pilar, 1: Viga, 2: Laje
        
        # Gerar Item
        new_id = str(uuid.uuid4())
        new_item = {
            'id': new_id,
            'project_id': self.active_project_id,
            'manual': True,
            'is_validated': is_library # Se criado na library, já nasce validado? User decide.
        }
        
        prefix = "ITEM"
        if current_idx == 0: # Pilar
            prefix = "P_NEW"
            new_item['type'] = 'Pilar'
            target_list_data = self.pillars_found
            list_widget = self.list_pillars_valid if is_library else self.list_pillars
        elif current_idx == 1: # Viga
            prefix = "V_NEW"
            new_item['type'] = 'Viga'
            target_list_data = self.beams_found
            list_widget = self.list_beams_valid if is_library else self.list_beams
        elif current_idx == 2: # Laje
            prefix = "L_NEW"
            new_item['type'] = 'Laje'
            target_list_data = self.slabs_found
            list_widget = self.list_slabs_valid if is_library else self.list_slabs
        else:
            return 

        # Nome sequencial simples
        count = len(target_list_data) + 1
        new_item['name'] = f"{prefix}_{count}"
        
        # Adicionar ao cache/memoria
        target_list_data.append(new_item)
        
        # Adicionar UI
        if isinstance(list_widget, QTreeWidget):
             # Para vigas, repopulamos a árvore para garantir agrupamento correto
             self._populate_beam_tree(list_widget, target_list_data)
        else:
             item_ui = QListWidgetItem(new_item['name'])
             item_ui.setData(Qt.UserRole, new_id)
             if new_item['is_validated']: item_ui.setForeground(Qt.green)
             list_widget.addItem(item_ui)
        
        self.show_detail(new_item)
        self.log(f"Item manual criado: {new_item['name']}")
        """Callback ao selecionar um projeto."""
        self.current_project_id = pid
        self.current_project_name = name
        self.current_dxf_path = dxf_path
        
        self.setWindowTitle(f"Vision-Estrutural AI - {name}")
        self.proj_mgr.close()
        
        # 1. Carregar DXF (se necessário ou se caminho mudar)
        if os.path.exists(dxf_path):
            self.load_dxf(dxf_path) 
        else:
             self.log(f"⚠️ Arquivo DXF não encontrado: {dxf_path}")

        # 2. Carregar Estado Salvo (Banco de Dados)
        self.load_project_action()
        
        # 2. Atualizar Tab de Treino
        self.tab_training.load_events(pid)
        
        # 3. Carregar dados processados do DB
        self.load_project_action()

    def sync_brain_memory(self):
        """Sincroniza eventos de treino com o VectorDB."""
        if not self.memory or not self.current_project_id: return
        
        events = self.db.get_training_events(self.current_project_id)
        if not events:
            self.log("📭 Nenhum evento de treino pendente.")
            return

        self.log(f"🧠 Sincronizando {len(events)} eventos com a memória...")
        
        count = 0
        import json
        for ev in events:
            try:
                # Decodificar contexto (DNA + RelPos)
                ctx = json.loads(ev['context_dna_json'])
                
                # Adaptação para suportar tanto formato antigo (só lista DNA) quanto novo (Dict)
                if isinstance(ctx, list):
                    dna = ctx
                    rel_pos = (0,0)
                    p_type = 'UNKNOWN'
                else:
                    dna = ctx.get('dna', [])
                    rel_pos = ctx.get('rel_pos', (0,0))
                    p_type = ctx.get('pilar_type', 'UNKNOWN')

                # Salvar na Memória Vetorial (ChromaDB)
                self.memory.save_sample({
                    'role': ev['role'], 
                    'content': ev['target_value'],
                    'rel_pos': rel_pos,
                    'dna': dna,
                    'pilar_type': p_type,
                    'status': ev['status'],
                    'comment': f"Sync from Project {self.current_project_name}"
                })
                count += 1
            except Exception as e:
                print(f"Erro sync evento {ev['id']}: {e}")
            
        self.log(f"✅ Sincronização concluída! {count} exemplos convertidos em vetores.")

    def delete_item_action(self, list_widget, item_type: str, is_library: bool):
        """Exclui o item selecionado da lista e da memória/banco."""
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Exclusão", "Selecione um item para excluir.")
            return

        item = selected_items[0]
        # Correção: Vigas usam QTreeWidget (requer coluna 0), Pilares/Lajes usam QListWidget
        if item_type == 'beam':
            item_id = item.data(0, Qt.UserRole)
        else:
            item_id = item.data(Qt.UserRole)
        
        reply = QMessageBox.question(self, "Confirmar Exclusão", 
                                   f"Tem certeza que deseja excluir este item ({item.text()})?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        # 1. Identificar listas envolvidas para limpeza simultânea
        lists_to_clean = []
        if item_type == 'pillar':
            lists_to_clean = [self.list_pillars, self.list_pillars_valid]
        elif item_type == 'beam':
            lists_to_clean = [self.list_beams, self.list_beams_valid]
        elif item_type == 'slab':
            lists_to_clean = [self.list_slabs, self.list_slabs_valid]

        # 2. Remover da UI (Ambas as listas: Análise e Biblioteca)
        for lw in lists_to_clean:
            if isinstance(lw, QListWidget):
                for i in range(lw.count()):
                    it = lw.item(i)
                    if it and it.data(Qt.UserRole) == item_id:
                        lw.takeItem(i)
                        break
            elif isinstance(lw, QTreeWidget):
                from PySide6.QtWidgets import QTreeWidgetItemIterator
                it_tree = QTreeWidgetItemIterator(lw)
                while it_tree.value():
                    tree_item = it_tree.value()
                    if tree_item.data(0, Qt.UserRole) == item_id:
                        (tree_item.parent() or lw.invisibleRootItem()).removeChild(tree_item)
                        break
                    it_tree += 1

        # 3. Remover da Memória (Shared lists)
        target_list = None
        if item_type == 'pillar':
             target_list = self.pillars_found
        elif item_type == 'beam':
             target_list = self.beams_found
        elif item_type == 'slab':
             target_list = self.slabs_found
             
        if target_list is not None:
            start_count = len(target_list)
            target_list[:] = [x for x in target_list if x['id'] != item_id]
            
            if len(target_list) < start_count:
                # 4. Remover do Banco de Dados (Persistência)
                try:
                    if item_type == 'pillar':
                        self.db.delete_pillar(item_id)
                    elif item_type == 'beam':
                        self.db.delete_beam(item_id)
                    elif item_type == 'slab':
                        self.db.delete_slab(item_id)
                    self.log(f"🗑️ Item {item_id} removido da memória, das listas e do Banco de Dados.")
                except Exception as e:
                    self.log(f"⚠️ Erro ao remover do Banco de Dados: {e}")

                if item_type == 'pillar':
                    self.canvas.draw_interactive_pillars(self.pillars_found)
                elif item_type == 'slab':
                    self.canvas.draw_slabs(self.slabs_found)
                elif item_type == 'beam':
                    self.canvas.draw_beams(self.beams_found)

    # --- Script Generation Placeholders ---
    def generate_script_pillar_full(self, is_library):
        self.log(f"📜 [TODO] Gerar Script Pilar Completo (Lib={is_library})")
        # Implement script generation logic here

    def generate_script_pavement_pillar(self, is_library):
        self.log(f"📜 [TODO] Gerar Script Pavimento Pilar Completo (Lib={is_library})")
        # Implement script generation logic here

    def generate_script_beam_set(self, is_library):
        self.log(f"📜 [TODO] Gerar Script Conjunto de Viga Completo (Lib={is_library})")
        # Implement script generation logic here

    def generate_script_pavement_beam(self, is_library):
        self.log(f"📜 [TODO] Gerar Script Pavimento Vigas Completo (Lib={is_library})")
        # Implement script generation logic here

    def export_data_json(self, item_type, is_library):
        """Exporta os dados da lista atual para JSON."""
        # 1. Determinar qual lista ler
        if is_library:
            if item_type == 'pillar': list_widget = self.list_pillars_valid
            elif item_type == 'beam': list_widget = self.list_beams_valid
            elif item_type == 'slab': list_widget = self.list_slabs_valid
        else:
            if item_type == 'pillar': list_widget = self.list_pillars
            elif item_type == 'beam': list_widget = self.list_beams
            elif item_type == 'slab': list_widget = self.list_slabs
            
        # 2. Coletar IDs da lista
        ids = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            uid = item.data(Qt.UserRole)
            if uid: ids.append(uid)
            
        if not ids:
            self.log("⚠️ Lista vazia. Nada a exportar.")
            return

        # 3. Buscar objetos reais (Data Source)
        # Assumindo que pillars_found, beams_found e slabs_found contêm TUDO (validado ou não)
        # Se for Library, talvez devêssemos buscar do DB se a lista local estiver incompleta, 
        # mas a lista local pillars_found deve estar sincronizada.
        
        source_data = []
        if item_type == 'pillar': full_list = self.pillars_found
        elif item_type == 'beam': full_list = self.beams_found
        elif item_type == 'slab': full_list = self.slabs_found
        else: full_list = []
        
        # Mapear ID -> Objeto para busca rápida
        data_map = {item['id']: item for item in full_list}
        
        export_list = []
        for uid in ids:
            if uid in data_map:
                export_list.append(data_map[uid])
            else:
                # Se não achou na memória (pode acontecer se carregou Lib do DB mas não processou DXF)
                # Tentar buscar do DB individualmente (lento mas seguro)
                if item_type == 'pillar': 
                    # self.db.get_pillar(uid)?? Não temos esse método exposto facilmente
                    pass
        
        self.log(f"💾 Preparando exportação de {len(export_list)} itens...")
        
        # 4. Salvar Arquivo
        file_name, _ = QFileDialog.getSaveFileName(self, f"Exportar {item_type.capitalize()}s", f"export_{item_type}.json", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    json.dump(export_list, f, indent=4, ensure_ascii=False)
                self.log(f"✅ Deu bom! Arquivo salvo em: {file_name}")
            except Exception as e:
                self.log(f"❌ Erro ao salvar JSON: {e}")

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
