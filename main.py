import sys
import os
import json
import logging
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QFileDialog, QDockWidget, 
                               QTextEdit, QLabel, QStackedWidget, QListWidget,
                               QListWidgetItem, QTabWidget, QSplitter, QLineEdit)
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
from src.core.beam_walker import BeamWalker
from src.ai.memory_store import MemoryStore

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
        try:
            self.memory = MemoryStore() # Vector DB
        except Exception as e:
            logging.warning(f"Vector DB init error: {e}")
            self.memory = None
            
        self.spatial_index = SpatialIndex()
        self.dxf_data = None
        self.pillars_found = []
        self.slabs_found = []
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
        self.btn_process.clicked.connect(self.process_pillars_action)
        # self.btn_process.setEnabled(False) # ANTERIORMENTE DESABILITADO - FIX: HABILITADO
        left_layout.addWidget(self.btn_process)

        # 3. Botão Salvar
        self.btn_save = QPushButton("Salvar")
        self.btn_save.setObjectName("Success")
        self.btn_save.clicked.connect(self.save_project_action)
        left_layout.addWidget(self.btn_save)

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
            btn_delete.setStyleSheet("background-color: #ffcccc; color: #cc0000; border: 1px solid #ff9999;")
            btn_delete.clicked.connect(lambda: self.delete_item_action(list_widget, item_type, is_library))
            layout.addWidget(btn_delete)

            # Botão Criar Novo Item (padrão)
            scope_name = "Lib" if is_library else "Análise"
            btn_create = QPushButton(f"➕ Criar Novo Item ({scope_name})")
            btn_create.clicked.connect(lambda: self.create_manual_item(is_library=is_library))
            layout.addWidget(btn_create)
            
            # Botões Específicos
            if item_type == 'pillar':
                # 3 Botões para Pilares
                btn_script_full = QPushButton("📜 Gerar Script Pilar Completo")
                btn_script_full.clicked.connect(lambda: self.generate_script_pillar_full(is_library))
                layout.addWidget(btn_script_full)
                
                btn_script_pav = QPushButton("📜 Gerar Script Pavimento Pilar Completo")
                btn_script_pav.clicked.connect(lambda: self.generate_script_pavement_pillar(is_library))
                layout.addWidget(btn_script_pav)
                
                btn_export = QPushButton("💾 Exportar Dados dos Pilares (JSON)")
                btn_export.clicked.connect(lambda: self.export_data_json('pillar', is_library))
                layout.addWidget(btn_export)
                
            elif item_type == 'beam':
                # 3 Botões para Vigas
                btn_script_set = QPushButton("📜 Gerar Script Conjunto de Viga Completo")
                btn_script_set.clicked.connect(lambda: self.generate_script_beam_set(is_library))
                layout.addWidget(btn_script_set)

                btn_script_pav = QPushButton("📜 Gerar Script Pavimento Vigas Completo")
                btn_script_pav.clicked.connect(lambda: self.generate_script_pavement_beam(is_library))
                layout.addWidget(btn_script_pav)

                btn_export = QPushButton("💾 Exportar Dados das Vigas (JSON)")
                btn_export.clicked.connect(lambda: self.export_data_json('beam', is_library))
                layout.addWidget(btn_export)
                
            elif item_type == 'slab':
                # 1 Botão para Lajes
                btn_export = QPushButton("💾 Exportar Dados das Lajes (JSON)")
                btn_export.clicked.connect(lambda: self.export_data_json('slab', is_library))
                layout.addWidget(btn_export)

            return container

        # --- TAB 1: ANÁLISE ATUAL ---
        self.tab_analysis = QWidget()
        analysis_layout = QVBoxLayout(self.tab_analysis)
        analysis_layout.setContentsMargins(0,0,0,0)
        
        self.tabs_analysis_internal = QTabWidget()
        self.list_pillars = QListWidget()
        self.list_beams = QListWidget()
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
        self.tabs_analysis_internal.addTab(self.list_issues, "⚠️ Pendências") # Issues não tem botões extras solicitados
        
        # Conectar mudança de aba interna (Análise)
        self.tabs_analysis_internal.currentChanged.connect(self._on_analysis_tab_changed)
        
        analysis_layout.addWidget(self.tabs_analysis_internal)
        
        # --- TAB 2: BIBLIOTECA VALIDADA ---
        self.tab_library = QWidget()
        library_layout = QVBoxLayout(self.tab_library)
        library_layout.setContentsMargins(0,0,0,0)
        
        self.tabs_library_internal = QTabWidget()
        self.list_pillars_valid = QListWidget()
        self.list_beams_valid = QListWidget()
        self.list_slabs_valid = QListWidget()
        
        # Conectar Sinais (Validado)
        self.list_pillars_valid.itemClicked.connect(self.on_list_pillar_clicked)
        
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
        
        center_layout.addWidget(self.canvas)
        self.splitter.addWidget(self.canvas_container)
        
        # --- DIREITA: DETALHAMENTO ---
        self.right_panel = QStackedWidget()
        self.right_panel.setMinimumWidth(220)
        
        # Pagina 0: Placeholder
        placeholder = QLabel("Selecione um item para ver detalhes\nou inicie a detecção.")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #666; font-style: italic;")
        self.right_panel.addWidget(placeholder)
        
        # Pagina 1: Content
        self.detail_container = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_container)
        self.detail_layout.setContentsMargins(0,0,0,0)
        self.current_card = None
        self.right_panel.addWidget(self.detail_container)
        
        self.splitter.addWidget(self.right_panel)
        
        # Definir proporção inicial: Esquerda (365), Centro (Grande), Direita (220)
        self.splitter.setSizes([365, 1000, 220])
        
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
            self.canvas.set_category_visibility('beam') # Future
        elif index == 2:
            self.canvas.set_category_visibility('slab')
        else:
            self.canvas.set_category_visibility('all')

    def create_manual_item(self, is_library=False):
        pass # Implementar depois

    def show_detail(self, data):
        """Exibe o card de detalhes para os dados fornecidos."""
        # Limpar anterior
        if self.current_card:
            self.detail_layout.removeWidget(self.current_card)
            self.current_card.deleteLater()
            
        self.current_card = DetailCard(data)
        # Conectamos sinais do novo card
        self.current_card.data_validated.connect(self.on_card_validated)
        self.current_card.element_focused.connect(self.on_element_focused_on_table)
        self.current_card.pick_requested.connect(self.on_pick_requested)
        self.current_card.focus_requested.connect(self.on_focus_requested)
        self.current_card.research_requested.connect(self.on_research_requested)
        self.current_card.training_requested.connect(self.on_train_requested)
        self.current_card.config_updated.connect(self.on_config_updated)
        
        # Log para depuração de links
        links = data.get('links', {})
        self.log(f"Abrindo {data.get('name')}. Vínculos carregados: {list(links.keys())}")
        
        self.detail_layout.addWidget(self.current_card)
        self.right_panel.setCurrentIndex(1)

    def on_focus_requested(self, field_id):
        """Tenta focar no objeto vinculado ao campo especificado via COORDENADA DIRETA"""
        if not self.current_card: return
        item_data = self.current_card.item_data
        
        # Buscar nos links estruturados do campo
        links_data = item_data.get('links', {}).get(field_id, {})
        
        # Prioridade de slots para foco visual
        for slot in ['label', 'geometry', 'thick', 'level', 'dim', 'dist_text', 'dist_line', 'diff_text', 'diff_line', 'main']:
            if slot in links_data and links_data[slot]:
                link = links_data[slot][0]
                if 'pos' in link or 'points' in link:
                    self.canvas.highlight_link(link)
                    self.log(f"📍 Focando via coordenada direta: {link.get('text', 'Geometria')}")
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
        # slot_request formato: "id_do_slot|tipo_de_pick"
        parts = slot_request.split('|')
        slot_id = parts[0]
        pick_type = parts[1] if len(parts) > 1 else 'text'
        
        self.log(f"Iniciando captura {pick_type} para campo {field_id} [Slot: {slot_id}]...")
        self.current_pick_field = field_id
        self.current_pick_slot = slot_id
        self.canvas.set_picking_mode(pick_type, field_id)

    def on_pick_completed(self, pick_data):
        if self.current_card and hasattr(self, 'current_pick_field'):
            field_id = self.current_pick_field
            slot_id = getattr(self, 'current_pick_slot', 'main')
            
            from PySide6.QtWidgets import QLineEdit, QComboBox, QLabel
            field = self.current_card.fields.get(field_id)
            
            value = pick_data.get('text', '')
            
            # Especial: Se for um slot de Vazio (X), forçar nome "SEM LAJE"
            if slot_id == 'void_x':
                value = "SEM LAJE"
            
            # 1. Atualizar valor visual
            if isinstance(field, QLineEdit):
                field.setText(str(value))
            elif isinstance(field, QComboBox):
                field.setCurrentText(str(value))
            elif isinstance(field, QLabel):
                field.setText(f"Válido: {value}")
                field.setStyleSheet("color: #00cc66; font-weight: bold; font-size: 10px;")
            
            # 2. Salvar vínculo estruturado no item_data
            if 'links' not in self.current_card.item_data:
                self.current_card.item_data['links'] = {}
            
            links_dict = self.current_card.item_data['links']
            if field_id not in links_dict:
                links_dict[field_id] = {} 
                
            field_slots = links_dict[field_id]
            # Migração de dados legados
            if isinstance(field_slots, list):
                field_slots = {'label': field_slots}
                links_dict[field_id] = field_slots

            if slot_id not in field_slots:
                field_slots[slot_id] = []
            
            # Injetar papel (role)
            pick_data['role'] = slot_id.capitalize()
            field_slots[slot_id].append(pick_data)
            
            # Atualizar QLabel com contagem real se for o caso
            if isinstance(field, QLabel):
                total_links = sum(len(lst) for lst in field_slots.values())
                field.setText(f"{total_links} Vínculo(s) Ok")
                field.setStyleSheet("color: #00cc66; font-weight: bold; font-size: 10px;")

            # Lógica Especial: Fundo da Viga - Calcular dimensão pelo maior segmento
            if field_id == 'viga_fundo_segs':
                all_segs = []
                for slot_list in field_slots.values():
                    all_segs.extend(slot_list)
                
                max_len = 0.0
                for seg in all_segs:
                    pts = seg.get('points', [])
                    if len(pts) >= 2:
                         p1, p2 = pts[0], pts[1]
                         dist = ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5
                         if dist > max_len: max_len = dist
                
                dim_field = self.current_card.fields.get('viga_fundo_dim')
                if dim_field:
                     # Converter unidades se necessário (assumindo DXF unitless, mas exibindo float puro por enquanto)
                     dim_field.setText(f"{max_len:.2f}")
                     self.current_card.item_data['viga_fundo_dim'] = f"{max_len:.2f}"
            
            self.log(f"Vínculo adicionado ao campo {field_id} [Slot: {slot_id}]: {value}")
            
            # 3. Restaurar a janela de vínculos com os novos dados
            if hasattr(self.current_card, 'active_link_dlg') and self.current_card.active_link_dlg:
                self.current_card.active_link_dlg.links = field_slots
                self.current_card.active_link_dlg.refresh_list()
                self.current_card.active_link_dlg.show()
                self.current_card.active_link_dlg.raise_()

            # 4. Limpar o estado de pick para evitar múltiplas execuções acidentais
            if hasattr(self, 'current_pick_field'): delattr(self, 'current_pick_field')
            if hasattr(self, 'current_pick_slot'): delattr(self, 'current_pick_slot')

    def on_element_focused_on_table(self, data):
        """Disparado quando user clica num vínculo ou viga na tabela"""
        if isinstance(data, dict):
            # É um objeto de link completo (com coordenadas)
            self.canvas.highlight_link(data)
        elif isinstance(data, str) and data != '-':
            # É apenas o nome (fallback busca nominal)
            self.log(f"Destacando por nome: {data}")
            self.canvas.highlight_element_by_name(data, self.beams_found)
        
    def on_card_validated(self, updated_data: dict):
        """Callback quando o usuário valida um pilar no card"""
        # Atualizar lista em memória
        for i, p in enumerate(self.pillars_found):
            if p['id'] == updated_data['id']:
                self.pillars_found[i] = updated_data
                break
        
        # Salvar DB
        self.log(f"Pilar {updated_data['name']} validado! Salvando...")
        self.db.save_pillar(updated_data)
        
        # Aprender (Vector DB)
        if self.memory:
            try:
                self.memory.add_memory(updated_data)
                self.log("Memória vetorial atualizada com novo padrão.")
            except Exception as e:
                self.log(f"Erro ao atualizar memória AI: {e}")
        
        # Feedback Visual no Canvas
        self.canvas.update_pillar_status(updated_data['id'], 'validated')

    def log(self, message: str):
        self.console.append(f"> {message}")
        logging.info(message)
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

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
            
            # Enviar para o canvas
            self.canvas.add_dxf_entities(self.dxf_data)
            self.log("🎨 Canvas atualizado.")
            
            self.canvas.dxf_entities = self.dxf_data.get('texts', [])
            
            # Indexação
            self.log("🔍 Iniciando indexação espacial...")
            self.spatial_index.clear()
            for poly in self.dxf_data.get('polylines', []):
                pts = poly['points']
                if pts:
                    bounds = (min(p[0] for p in pts), min(p[1] for p in pts), 
                                max(p[0] for p in pts), max(p[1] for p in pts))
                    self.spatial_index.insert(poly, bounds) # Indexar o dict original
            
            for line in self.dxf_data.get('lines', []):
                s, e = line['start'], line['end']
                bounds = (min(s[0], e[0]), min(s[1], e[1]), max(s[0], e[0]), max(s[1], e[1]))
                self.spatial_index.insert(line, bounds)

            for txt in self.dxf_data.get('texts', []):
                p = txt['pos']
                bounds = (p[0]-5, p[1]-5, p[0]+5, p[1]+5)
                self.spatial_index.insert(txt, bounds)
        
        except Exception as e:
            self.log(f"💥 Falha crítica no load_dxf: {e}")
            import traceback
            traceback.print_exc()
        
        self.btn_process.setEnabled(True)

    def process_pillars_action(self):
        if not self.dxf_data: return
        import uuid # Garantir import
        
        # --- NOVO: Confirmação de Sobrescrita ---
        if self.pillars_found or (hasattr(self, 'beams_found') and self.beams_found) or self.slabs_found:
             from PySide6.QtWidgets import QMessageBox
             res = QMessageBox.warning(
                 self, "Reanalisar Todo o Projeto?",
                 "⚠️ ATENÇÃO: Uma análise já foi realizada.\n\n"
                 "Deseja iniciar uma NOVA análise geral? Isso irá SOBREESCREVER todos os itens atuais que não foram validados na biblioteca.\n\n"
                 "Para manter o que já foi interpretado, use o botão 'Salvar' e valide os itens um a um.",
                 QMessageBox.Yes | QMessageBox.No
             )
             if res == QMessageBox.No:
                 return

        self.log("Iniciando varredura geométrica e análise de vínculos...")
        
        # Limpar Listas
        self.list_pillars.clear()
        self.list_beams.clear()
        self.list_slabs.clear()
        
        polylines = self.dxf_data.get('polylines', [])
        texts = self.dxf_data.get('texts', [])
        lines = self.dxf_data.get('lines', [])
        
        # 1. Motores
        from src.core.beam_tracer import BeamTracer
        beam_tracer = BeamTracer(self.spatial_index)
        all_lines_and_polys = []
        for l in lines+polylines:
            if 'points' in l: all_lines_and_polys.append(l)
            elif 'start' in l: all_lines_and_polys.append({'points': [l['start'], l['end']]})

        self.beams_found = beam_tracer.detect_beams(texts, all_lines_and_polys)
        for i, b in enumerate(self.beams_found):
            # Dados de listagem: Numero Item - nome - quantiade de segmentos
            b_unique_id = f"{self.current_project_id}_b_{i+1}" if self.current_project_id else str(uuid.uuid4())
            b.update({
                'id': b_unique_id,
                'id_item': f"{i+1:02}", # Unificado para Ficha Técnica
                'id_num': i+1,
                'type': 'Viga',
                'seg_a': 1, # Será calculado no walker
                'seg_b': 1,
                'links': {
                    'name': {'label': [{'text': b['name'], 'type': 'text', 'pos': b.get('pos', (0,0)), 'role': 'Identificador Viga'}]}
                }
            })
            item_text = f"{b['id_item']} | {b['name']} | SegA: {b['seg_a']} | SegB: {b['seg_b']}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, b_unique_id)
            self.list_beams.addItem(item)

        # 1.1 Detect Slabs (Lajes)
        slab_tracer = SlabTracer(self.spatial_index)
        self.slabs_found = slab_tracer.detect_slabs_from_texts(texts)
        self.log(f"🔎 Lajes detectadas: {len(self.slabs_found)} (Busca por textos L#)")
        
        for i, s in enumerate(self.slabs_found):
             s_unique_id = f"{self.current_project_id}_l_{i+1}" if self.current_project_id else str(uuid.uuid4())
             s['id'] = s_unique_id
             s['id_item'] = f"{i+1:02}"
             s['project_id'] = self.current_project_id
             
             item_text = f"{s['id_item']} | {s['name']}"
             item = QListWidgetItem(item_text)
             item.setData(Qt.UserRole, s_unique_id)
             self.list_slabs.addItem(item)

        walker = BeamWalker(self.spatial_index)
        from shapely.geometry import Polygon
        self.pillars_found = []
        
        from src.core.perspective_mapper import PillarPerspectiveMapper
        # 2. Processar Pilares
        for i, p_item in enumerate(polylines):
            poly_points = p_item['points']
            # Remover duplicatas mantendo ordem e garantir pelo menos 3 pontos únicos
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
                    logging.info(f"Pilar {i} ignorado: geometria degenerada ({poly_shape.geom_type})")
                    continue

                # Nome Real e Formato por Perspectiva
                p_ent = self._find_nearest_text_ent(unique_points, "P")
                p_name = p_ent['text'] if p_ent else None
                pillar_name = p_name or f"P{i+1}"
                shape_type, orient = PillarPerspectiveMapper.identify_shape(unique_points)
                
                # Gerar ID único vinculado ao projeto para evitar colisão no DB
                # Se não tiver projeto (modo 'sandboxing'), usa UUID
                unique_id = f"{self.current_project_id}_p_{i+1}" if self.current_project_id else str(uuid.uuid4())
                
                p_data = {
                    'id': unique_id,
                    'id_item': f"{i+1:02}",
                    'name': pillar_name,
                    'type': 'Pilar',
                    'pos': (poly_shape.centroid.x, poly_shape.centroid.y), # Centro Real
                    'format': shape_type,
                    'area_val': poly_shape.area, # Valor numérico para o DB
                    'dim': f"{int(poly_shape.area)}cm²",
                    'points': list(poly_shape.exterior.coords),
                    'sides_data': PillarPerspectiveMapper.map_sides(unique_points, shape_type, orient),
                    'links': {}, 
                    'beams_visual': [], 
                    'material': 'C30', 'level': 'Pavimento 1'
                }
                
                # --- INTERPRETAÇÃO AUTOMÁTICA DE VIZINHANÇA ---
                self._interpret_pillar_details(p_data)
                
                # SANITY CHECK: Validar se a interpretação faz sentido físico
                p_data['issues'] = self._run_sanity_checks(p_data)
                
                self.pillars_found.append(p_data)
                
                # Listagem: Numero Item - Nome - Dim - Formato
                item_text = f"{p_data['id_item']} | {pillar_name} | {p_data['dim']} | {shape_type}"
                item = QListWidgetItem(item_text)
                
                # Cores por Confiança/Issue
                conf_map = p_data.get('confidence_map', {})
                avg_conf = sum(conf_map.values()) / len(conf_map) if conf_map else 0.5
                
                if p_data['issues']:
                    item.setForeground(Qt.red)
                    self._add_to_issues_list(p_data, avg_conf)
                elif avg_conf < 0.6:
                    item.setForeground(Qt.yellow)
                    self._add_to_issues_list(p_data, avg_conf)

                item.setData(Qt.UserRole, unique_id) # Sincronizado com p_data['id']
                self.list_pillars.addItem(item)
                
            except Exception as e:
                logging.error(f"Erro no pilar {i}: {e}")

        # 3. Lajes
        tracer = SlabTracer(self.spatial_index)
        self.slabs_found = []
        for txt in texts:
            content = str(txt.get('text', '')).upper().strip()
            if content.startswith('L') and any(c.isdigit() for c in content):
                poly = tracer.trace_boundary(txt['pos'], 1200.0)
                if poly and poly.area > 500:
                    s_unique_id = f"{self.current_project_id}_s_{len(self.slabs_found)+1}" if self.current_project_id else str(uuid.uuid4())
                    s_data = {
                        'id': s_unique_id, 
                        'id_item': f"{len(self.slabs_found)+1:02}",
                        'name': content, 'type': 'Laje',
                        'area': poly.area/10000.0, 'points': list(poly.exterior.coords),
                        'h': '12', 'q_rev': '1.5', 'q_util': '2.0', 'material': 'C30', 'level': 'Pavimento 1', 'dim': 'm²',
                        'links': {
                            'name': [{'text': content, 'type': 'text', 'pos': txt['pos']}]
                        }
                    }
                    self.slabs_found.append(s_data)
                    item = QListWidgetItem(f"{s_data['id_item']} | {content}")
                    item.setData(Qt.UserRole, s_unique_id)
                    self.list_slabs.addItem(item)

        self.canvas.draw_interactive_pillars(self.pillars_found)
        self.canvas.draw_slabs(self.slabs_found)
        self.log(f"Análise finalizada: {len(self.pillars_found)} Pilares, {len(self.beams_found)} Vigas e {len(self.slabs_found)} Lajes.")
        self.btn_save.setEnabled(True)

    def _interpret_pillar_details(self, p_data):
        """Varre a vizinhança para preencher campos automaticamente usando a lógica unificada de busca."""
        sides_data = p_data['sides_data']
        if 'links' not in p_data: p_data['links'] = {}
        links = p_data['links']
        topo_pilar = None
        all_levels = []
        used_training_count = 0

        # Determinamos o "tipo" do campo para isolar o treinamento
        def get_cat(fid):
            if 'name' in fid: return 'pillar_name'
            if 'dim' in fid: return 'pillar_dim'
            if '_l1_n' in fid: return 'slab_name'
            if '_l1_h' in fid: return 'slab_thick'
            if '_l1_v' in fid: return 'slab_level'
            if '_v_esq_n' in fid: return 'beam_name'
            if '_v_esq_d' in fid: return 'beam_dim'
            return 'general'

        if 'confidence_map' not in p_data: p_data['confidence_map'] = {}
        conf_map = p_data['confidence_map']

        # 0. Identificador do Pilar (Nome)
        res_name = self._perform_contextual_search('name', 'label', p_data, category=get_cat('name'))
        if res_name['found_ent']:
            links['name'] = {'label': res_name['links']}
            conf_map['name'] = res_name['confidence']
            links['pilar_segs'] = {'segments': [{'text': f"Formato {p_data['format']}", 'type': 'line', 'points': p_data['points'], 'role': 'Base Geométrica'}]}
            if res_name['used_training']: used_training_count += 1

        # 1. Dimensão
        res_dim = self._perform_contextual_search('dim', 'label', p_data, category=get_cat('dim'))
        if res_dim['found_ent']:
            p_data['dim'] = res_dim['found_ent']['text']
            links['dim'] = {'label': res_dim['links']}
            conf_map['dim'] = res_dim['confidence']
            if res_dim['used_training']: used_training_count += 1
            
        # 2. Topo do Pilar (Nível)
        res_topo = self._perform_contextual_search('topo_nivel', 'level', p_data, category='pilar_level')
        if res_topo['found_ent']:
            p_data['topo_nivel'] = res_topo['found_ent']['text']
            conf_map['topo_nivel'] = res_topo['confidence']
            topo_pilar = self._extract_float(p_data['topo_nivel'])
            if topo_pilar is not None: all_levels.append(topo_pilar)
            if res_topo['used_training']: used_training_count += 1

        found_links_count = 0
        for side, content in sides_data.items():
            # Lajes: Nome
            f_id_n = f'p_s{side}_l1_n'
            res_l_n = self._perform_contextual_search(f_id_n, 'label', p_data, side=side, category=get_cat(f_id_n))
            
            if res_l_n['found_ent']:
                content['l1_n'] = res_l_n['found_ent']['text']
                links[f_id_n] = {'label': res_l_n['links']}
                conf_map[f_id_n] = res_l_n['confidence']
                found_links_count += 1
                if res_l_n['used_training']: used_training_count += 1
                
                # Espessura (Busca focada no texto da laje)
                p_laje_data = p_data.copy()
                p_laje_data['pos'] = res_l_n['found_ent']['pos']
                f_id_h = f'p_s{side}_l1_h'
                res_l_h = self._perform_contextual_search(f_id_h, 'thick', p_laje_data, initial_radius=300.0, side=side, category=get_cat(f_id_h))
                if res_l_h['found_ent']:
                    val_h = self._extract_float(res_l_h['found_ent']['text'])
                    content['l1_h'] = str(val_h) if val_h is not None else res_l_h['found_ent']['text']
                    links[f_id_h] = {'thick': res_l_h['links']}
                    conf_map[f_id_h] = res_l_h['confidence']
                    found_links_count += 1
                    if res_l_h['used_training']: used_training_count += 1

                # Nível da Laje
                f_id_lv = f'p_s{side}_l1_v'
                res_l_v = self._perform_contextual_search(f_id_lv, 'level', p_data, side=side, category=get_cat(f_id_lv))
                if res_l_v['found_ent']:
                    content['l1_v'] = res_l_v['found_ent']['text']
                    links[f_id_lv] = {'level': res_l_v['links']}
                    conf_map[f_id_lv] = res_l_v['confidence']
                    v_val = self._extract_float(content['l1_v'])
                    if v_val is not None: all_levels.append(v_val)
                    found_links_count += 1
                    if res_l_v['used_training']: used_training_count += 1
            else:
                # Vazio (X)
                res_void = self._perform_contextual_search(f_id_n, 'void_x', p_data, side=side, category='void_x')
                if res_void['found_ent']:
                    content['l1_n'] = "SEM LAJE"
                    links[f_id_n] = {'void_x': res_void['links']}
                    conf_map[f_id_n] = res_void['confidence']
                    found_links_count += 1
                    if res_void['used_training']: used_training_count += 1
                    
            # Vigas
            f_id_vn = f'p_s{side}_v_esq_n'
            res_v_n = self._perform_contextual_search(f_id_vn, 'label', p_data, side=side, category=get_cat(f_id_vn))
            if res_v_n['found_ent']:
                content['v_esq_n'] = res_v_n['found_ent']['text']
                links[f_id_vn] = {'label': res_v_n['links']}
                conf_map[f_id_vn] = res_v_n['confidence']
                found_links_count += 1
                if res_v_n['used_training']: used_training_count += 1

                # Dimensão da Viga
                f_id_vd = f'p_s{side}_v_esq_d'
                res_v_d = self._perform_contextual_search(f_id_vd, 'dim', p_data, side=side, category=get_cat(f_id_vd))
                if res_v_d['found_ent']:
                    content['v_esq_d'] = res_v_d['found_ent']['text']
                    links[f_id_vd] = {'dim': res_v_d['links']}
                    conf_map[f_id_vd] = res_v_d['confidence']
                    found_links_count += 1
                    if res_v_d['used_training']: used_training_count += 1
                    import re
                    nums = [int(n) for n in re.findall(r'\d+', content['v_esq_d'])]
                    if nums: content['v_esq_prof'] = str(max(nums))
                
                # Nível da Viga
                f_id_vv = f'p_s{side}_v_esq_v'
                res_v_v = self._perform_contextual_search(f_id_vv, 'level', p_data, side=side, category='beam_level')
                if res_v_v['found_ent']:
                    v_val = self._extract_float(res_v_v['found_ent']['text'])
                    if v_val is not None:
                        content['v_esq_v'] = res_v_v['found_ent']['text']
                        links[f_id_vv] = {'level': res_v_v['links']}
                        conf_map[f_id_vv] = res_v_v['confidence']
                        all_levels.append(v_val)
                        if topo_pilar is not None:
                            diff = topo_pilar - v_val
                            content['v_esq_diff_v'] = f"{diff:.2f}"
                        if res_v_v['used_training']: used_training_count += 1

        self.log(f"Pilar {p_data.get('name')}: {found_links_count} vínculos ({used_training_count} via mem vetorial).")

        # 3. Lógica de Posição Automática (Topo / Fundo / Centro)
        if all_levels:
            max_lv = max(all_levels)
            min_lv = min(all_levels)
            for side, content in sides_data.items():
                if 'l1_v' in content:
                    curr = self._extract_float(content['l1_v'])
                    if curr is not None:
                        if abs(curr - max_lv) < 0.05: content['l1_p'] = "Topo"
                        elif abs(curr - min_lv) < 0.05: content['l1_p'] = "Fundo"
                        else:
                            content['l1_p'] = "Centro"
                            content['l1_dist_c'] = f"{max_lv - curr:.2f}"
        
        self.log(f"Pilar {p_data.get('name')}: {found_links_count} vínculos automáticos mapeados.")

    def _find_nearest_text_pattern_ent(self, points, pattern, radius=500.0, side=None):
        """Busca entidade de texto via regex próximo à geometria, com filtro direcional opcional."""
        import re, math
        if not points or not self.dxf_data: return None
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        
        texts = self.dxf_data.get('texts', [])
        best_dist = radius
        best_ent = None
        
        for txt in texts:
            # Filtro Direcional (Setores)
            if side:
                tx, ty = txt['pos']
                angle = math.degrees(math.atan2(ty - cy, tx - cx))
                if side == "A" and not (45 <= angle <= 135): continue
                if side == "B" and not (-45 <= angle <= 45): continue
                if side == "C" and not (-135 <= angle <= -45): continue
                if side == "D" and not (angle > 135 or angle < -135): continue
                if side == "Superior" and not (ty > cy): continue
                if side == "Inferior" and not (ty <= cy): continue

            content = str(txt.get('text', '')).upper().strip()
            match = re.search(pattern, content)
            if match:
                tx, ty = txt['pos']
                dist = ((cx - tx)**2 + (cy - ty)**2)**0.5
                if dist < best_dist:
                    best_dist = dist
                    best_ent = txt
        return best_ent

    def _generate_pilar_dna(self, p_data):
        """Gera uma assinatura geométrica (DNA) para comparação semântica."""
        # 1. Dados Básicos
        area = p_data.get('area', 1.0)
        points = p_data.get('points', [])
        
        # 2. Complexidade Período/Area
        perim = 0
        for i in range(len(points)):
            p1, p2 = points[i], points[(i+1)%len(points)]
            perim += ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5
        complexity = perim / (area**0.5) if area > 0 else 0
        
        # 3. Vizinhança (Densidade)
        center = p_data.get('pos', (0,0))
        radius = 1500.0
        bbox = (center[0]-radius, center[1]-radius, center[0]+radius, center[1]+radius)
        nearby = self.spatial_index.query_bbox(bbox)
        
        num_texts = sum(1 for item in nearby if 'text' in item)
        num_lines = sum(1 for item in nearby if 'start' in item)
        
        # DNA Vector: [Area, Densidade Textos, Complexidade, Perímetro]
        return [float(area), float(num_texts), float(complexity), float(perim)]

    def _extract_float(self, text):
        """Extrai o primeiro número (float) de uma string de forma segura."""
        import re
        if not text: return None
        # Limpa espaços e substitui vírgula por ponto
        clean_text = text.replace(' ', '').replace(',', '.')
        match = re.search(r"[+-]?\d+\.?\d*", clean_text)
        if match:
            try:
                return float(match.group())
            except: return None
        return None

    def _find_vazio_x_lines(self, points, radius=800.0, side=None):
        """Busca linhas que podem formar um 'X' (vazio) no setor"""
        import math
        if not points: return []
        
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        
        bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
        nearby = self.spatial_index.query_bbox(bbox)
        
        found = []
        for item in nearby:
            if 'start' in item and 'end' in item:
                # Centro da linha
                sx, sy = item['start']
                ex, ey = item['end']
                mx, my = (sx+ex)/2, (sy+ey)/2
                
                if side:
                    angle = math.degrees(math.atan2(my - cy, mx - cx))
                    if side == "A" and not (45 <= angle <= 135): continue
                    if side == "B" and not (-45 <= angle <= 45): continue
                    if side == "C" and not (-135 <= angle <= -45): continue
                    if side == "D" and not (angle > 135 or angle < -135): continue
                
                # Opcional: Filtrar por comprimento ou ângulo do X (aprox 45/135)
                found.append(item)
        return found

    def _perform_contextual_search(self, field_id, slot_id, item_data, initial_radius=800.0, side=None, category=None):
        """
        Lógica unificada de busca que integra Treinamento (Memória Vetorial) + Geometria + DNA.
        """
        role = category if category else f"{field_id}_{slot_id}"
        points = item_data['points']
        center_p = item_data.get('pos')
        if not center_p:
            center_p = (sum(p[0] for p in points)/len(points), sum(p[1] for p in points)/len(points))
            
        pilar_type = item_data.get('type', 'UNKNOWN')
        
        # Gerar DNA para busca semântica
        current_dna = self._generate_pilar_dna(item_data)
        training_ctx = self.memory.get_training_context(role, pilar_type, current_dna=current_dna) if self.memory else None
        
        base_pos = center_p # Posição original do pilar
        search_center = center_p
        search_radius = initial_radius
        confidence = 0.5 # Base
        used_training = False
        debug_info = ""
        
        if training_ctx and training_ctx.get('samples', 0) > 0:
             offset_x, offset_y = training_ctx['avg_rel_pos']
             used_training = True
             sim = training_ctx.get('top_similarity', 0.5)
             debug_info = f"IA: Usando padrão aprendido (Conf: {sim*100:.0f}%, n={training_ctx['samples']})"
             search_center = (center_p[0] + offset_x, center_p[1] + offset_y)
             # Não restringimos o raio (mantemos original) para permitir tolerância ao offset
        
        blocklist = training_ctx.get('blocklist', []) if training_ctx else []

        slot_cfg = self._get_slot_config(field_id, slot_id)
        prompt = slot_cfg.get('prompt', '')
        
        import re
        prefix_match = re.search(r'["\']([PLV])["\']', prompt)
        regex_match = re.search(r'regex\s*[:=]\s*(.+)', prompt, re.I)
        
        found_ent = None
        new_links_list = []
        
        # Execução da Busca
        if slot_id == 'void_x':
            side_code = side or (field_id.split('_')[1][1:] if '_' in field_id else None)
            v_lines = self._find_vazio_x_lines([search_center], search_radius, side=side_code)
            if v_lines:
                for vl in v_lines[:2]:
                    new_links_list.append({'type': 'line', 'points': [vl['start'], vl['end']], 'text': 'Vazio (X)', 'role': 'Vazio (X)'})
                found_ent = {'text': 'SEM LAJE'}
                confidence += 0.2
        else:
            # 3. Executar Busca Espacial
            found_ent = None
            
            # Tenta busca com offset e raio padrão
            if regex_match:
                pattern = regex_match.group(1).strip()
                found_ent = self._find_nearest_text_pattern_ent([search_center], pattern, search_radius, side=side, ref_angle=base_pos, blocklist=blocklist)
            elif prefix_match:
                prefix = prefix_match.group(1)
                found_ent = self._find_nearest_text_ent([search_center], prefix, search_radius, side=side, ref_angle=base_pos, blocklist=blocklist)
            else:
                # Se for dimensão, espessura ou nível, e não tem prefixo explícito, aceita qualquer coisa
                prefix = None
                if 'name' in field_id or '_v_esq_n' in field_id or '_l1_n' in field_id:
                     prefix = 'V' if 'viga' in slot_id or '_v_' in field_id else ('L' if '_l1_' in field_id else 'P')
                
                found_ent = self._find_nearest_text_ent([search_center], prefix, search_radius, side=side, ref_angle=base_pos, blocklist=blocklist)
            
            # FALLBACK: Se falhou e está usando treino, tenta no raio original sem offset (IA pode estar enviesada)
            if not found_ent and used_training:
                if regex_match:
                    pattern = regex_match.group(1).strip()
                    found_ent = self._find_nearest_text_pattern_ent([base_pos], pattern, initial_radius * 1.5, side=side, ref_angle=base_pos, blocklist=blocklist)
                elif prefix_match:
                    prefix = prefix_match.group(1)
                    found_ent = self._find_nearest_text_ent([base_pos], prefix, initial_radius * 1.5, side=side, ref_angle=base_pos, blocklist=blocklist)
                else:
                    prefix = None
                    if 'name' in field_id or '_v_esq_n' in field_id or '_l1_n' in field_id:
                        prefix = 'V' if 'viga' in slot_id or '_v_' in field_id else ('L' if '_l1_' in field_id else 'P')
                    
                    found_ent = self._find_nearest_text_ent([base_pos], prefix, initial_radius * 1.5, side=side, ref_angle=base_pos, blocklist=blocklist)
                if found_ent:
                    debug_info += " (Recuperado via Fallback sem offset)"
            
            if found_ent:
                new_links_list.append({'text': found_ent['text'], 'type': 'text', 'pos': found_ent['pos'], 'role': slot_id})
                confidence += 0.2
            else:
                confidence = 0.0

        return {
            'found_ent': found_ent,
            'links': new_links_list,
            'confidence': min(1.0, confidence),
            'used_training': training_ctx is not None,
            'debug': f"C:{confidence:.2f} | R:{search_radius:.0f} | Role:{role}"
        }

    def _find_nearest_text_ent(self, points, prefix, radius=400.0, side=None, ref_angle=None, blocklist=None):
        """Busca entidade de texto com prefixo (P, V, L) próximo à geometria com filtro direcional."""
        import math, re
        if not points or not self.dxf_data: return None
        blocklist = blocklist or []
        
        # Normalização agressiva para matching de blocklist (remover P, espaços, etc para comparar a 'essência' se necessário)
        def clean(s): return re.sub(r'[^A-Z0-9/X]', '', str(s).upper())
        clean_blocklist = [clean(b) for b in blocklist]
        
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        rx, ry = (ref_angle[0], ref_angle[1]) if ref_angle else (cx, cy)
        
        texts = self.dxf_data.get('texts', [])
        best_dist = radius
        best_ent = None
        
        for txt in texts:
            tx, ty = txt['pos']
            content = str(txt.get('text', '')).strip()
            content_upper = content.upper()
            
            # Pular se estiver na blocklist
            if clean(content) in clean_blocklist:
                continue

            # Filtro Direcional (Setores)
            if side:
                angle = math.degrees(math.atan2(ty - ry, tx - rx))
                if side == "A" and not (45 <= angle <= 135): continue
                if side == "B" and not (-45 <= angle <= 45): continue
                if side == "C" and not (-135 <= angle <= -45): continue
                if side == "D" and not (angle > 135 or angle < -135): continue
                if side == "Superior" and not (ty > ry): continue
                if side == "Inferior" and not (ty <= ry): continue

            # Se prefixo for vazio, aceita qualquer coisa
            if not prefix or content_upper.startswith(prefix.upper()):
                dist = ((cx - tx)**2 + (cy - ty)**2)**0.5
                if dist < best_dist:
                    best_dist = dist
                    best_ent = txt
        return best_ent

    def _find_nearest_text_pattern_ent(self, points, pattern, radius=500.0, side=None, ref_angle=None, blocklist=None):
        """Busca entidade de texto via regex próximo à geometria, com filtro direcional opcional."""
        import re, math
        if not points or not self.dxf_data: return None
        blocklist = blocklist or []
        
        def clean(s): return re.sub(r'[^A-Z0-9/X]', '', str(s).upper())
        clean_blocklist = [clean(b) for b in blocklist]
        
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        rx, ry = (ref_angle[0], ref_angle[1]) if ref_angle else (cx, cy)
        
        texts = self.dxf_data.get('texts', [])
        best_dist = radius
        best_ent = None
        
        for txt in texts:
            tx, ty = txt['pos']
            content = str(txt.get('text', '')).strip()

            # Pular se estiver na blocklist
            if clean(content) in clean_blocklist:
                continue

            # Filtro Direcional (Setores)
            if side:
                angle = math.degrees(math.atan2(ty - ry, tx - rx))
                if side == "A" and not (45 <= angle <= 135): continue
                if side == "B" and not (-45 <= angle <= 45): continue
                if side == "C" and not (-135 <= angle <= -45): continue
                if side == "D" and not (angle > 135 or angle < -135): continue
                if side == "Superior" and not (ty > ry): continue
                if side == "Inferior" and not (ty <= ry): continue

            # Regex Match
            if re.search(pattern, content, re.I):
                dist = ((cx - tx)**2 + (cy - ty)**2)**0.5
                if dist < best_dist:
                    best_dist = dist
                    best_ent = txt
        return best_ent

    def on_list_pillar_clicked(self, item):
        pillar_id = item.data(Qt.UserRole)
        pilar = next((p for p in self.pillars_found if p['id'] == pillar_id), None)
        if pilar:
            self.show_detail(pilar)
            self.canvas.isolate_item(pillar_id, 'pillar') # Isola no Canvas
            self.canvas.draw_focus_beams(pilar.get('beams_visual', []))
        else:
            self.log(f"Erro: Pilar {pillar_id} não encontrado nos dados processados.")

    def on_list_beam_clicked(self, item):
        beam_id = item.data(Qt.UserRole)
        beam = next((b for b in self.beams_found if b['id'] == beam_id), None)
        if beam:
            self.show_detail(beam)
            # Focar na viga (geometria completa)
            # self.canvas.focus_on_geometry(beam['geometry']) # TODO

    def on_list_slab_clicked(self, item):
        slab_id = item.data(Qt.UserRole)
        slab = next((s for s in self.slabs_found if s['id'] == slab_id), None)
        if slab:
            self.show_detail(slab)
            self.canvas.isolate_item(slab_id, 'slab') # Isola Laje
            # self.canvas.focus_on_geometry(slab['points']) # TODO

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
        
        # Save Pillars
        for p in self.pillars_found:
            self.db.save_pillar(p, self.current_project_id)
        self.log(f"   -> {len(self.pillars_found)} pilares salvos.")

        # Save Slabs
        slabs = getattr(self, 'slabs_found', [])
        for s in slabs:
            self.db.save_slab(s, self.current_project_id)
        self.log(f"   -> {len(slabs)} lajes salvas.")

        # Save Beams
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
        
        saved_pillars = self.db.load_pillars(self.current_project_id)
        if not saved_pillars:
            self.log("⚠️ Nenhum dado salvo encontrado para este projeto.")
            return
            
        self.pillars_found = saved_pillars
        
        # Carregar Lajes
        saved_slabs = self.db.load_slabs(self.current_project_id)
        self.slabs_found = saved_slabs if saved_slabs else []

        # Carregar Vigas
        saved_beams = self.db.load_beams(self.current_project_id)
        self.beams_found = saved_beams if saved_beams else []

        # Limpar listas UI
        self.list_pillars.clear()
        self.list_beams.clear()
        self.list_slabs.clear()
        self.list_issues.clear()
        self.list_pillars_valid.clear()
        self.list_beams_valid.clear()
        self.list_slabs_valid.clear()
        
        # Reconstruir Lista de Pilares
        for i, p in enumerate(self.pillars_found):
            p['id_item'] = f"{i+1:02}"
            item_text = f"{p['id_item']} | {p['name']} | {p.get('dim', 'N/A')} | {p.get('format', 'N/A')}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, p['id'])
            self.list_pillars.addItem(item)
            
            if p.get('is_validated'):
                 item_v = QListWidgetItem(item_text + " ✅")
                 item_v.setData(Qt.UserRole, p['id'])
                 item_v.setForeground(Qt.green)
                 self.list_pillars_valid.addItem(item_v)

        # Reconstruir Lista de Vigas
        for i, b in enumerate(self.beams_found):
            b['id_item'] = f"{i+1:02}"
            item_text = f"{b['id_item']} | {b['name']} | SegA: {b.get('seg_a', 1)} | SegB: {b.get('seg_b', 1)}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, b['id'])
            self.list_beams.addItem(item)
            
            if b.get('is_validated'):
                 item_v = QListWidgetItem(item_text + " ✅")
                 item_v.setData(Qt.UserRole, b['id'])
                 item_v.setForeground(Qt.green)
                 self.list_beams_valid.addItem(item_v)

        # Reconstruir Lista de Lajes
        for i, s in enumerate(self.slabs_found):
            s['id_item'] = f"{i+1:02}"
            item_text = f"{s['id_item']} | {s['name']}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, s['id'])
            self.list_slabs.addItem(item)
        
        # Desenhar overlays no canvas
        self.canvas.draw_interactive_pillars(self.pillars_found)
        self.canvas.draw_slabs(self.slabs_found)
        
        # Sincronizar Heatmap e Pendências
        self._update_all_lists_ui()
        self.log(f"✅ {len(saved_pillars)} pilares restaurados.")
            
        if self.pillars_found:
            self.show_detail(self.pillars_found[0])
                
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

        # 3. Executar Busca Contextual Unificada
        result = self._perform_contextual_search(field_id, slot_id, item_data, side=side_code, category=get_cat(field_id))
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
        """Auxiliar central para registrar conhecimento validado ou falho."""
        if not self.current_project_id: return

        content = link_obj.get('text', '')
        if not content and ('points' in link_obj or 'start' in link_obj):
            content = "GEOMETRY_LINK"
        
        # 1. Dados de Contexto (DNA + Posição Relativa)
        px, py = item_data.get('pos', (0,0))
        lx, ly = link_obj.get('pos', (px, py))
        rel_pos = (lx - px, ly - py)
        dna = self._generate_pilar_dna(item_data)
        
        context_data = {
            'dna': dna,
            'rel_pos': rel_pos,
            'pilar_type': item_data.get('format', 'UNKNOWN'),
            'field_id': field_id,
            'comment': comment
        }
        
        event = {
            'project_id': self.current_project_id,
            'type': 'user_feedback',
            'role': slot_id,
            'dna': context_data,
            'value': content,
            'status': status
        }
        self.db.log_training_event(event)

    def on_train_requested(self, field_id, train_data):
        """Registra feedback de treino no banco de dados e opcionalmente propaga."""
        if not self.current_project_id:
            self.log("❌ Crie/Abra um projeto para treinar.")
            return

        if not self.current_card: return
        p_data = self.current_card.item_data
        
        slot_id = train_data.get('slot', 'main')
        status = train_data.get('status', 'valid')
        link_obj = train_data.get('link', {})
        comment = train_data.get('comment', '')
        propagate = train_data.get('propagate', False)

        # 1. Registrar o Treino Individual
        self._log_training_action(p_data, field_id, slot_id, link_obj, status, comment)

        # 2. Feedback Visual Imediato
        if status == 'valid':
            self.current_card.mark_field_validated(field_id, True)
            self.log(f"👍 Feedback POSITIVO salvo para '{field_id}:{slot_id}'")
            
            # --- NOVO: Se validou o vínculo, valida o item inteiro no DXF ---
            self.on_card_validated(p_data)
            
            # 3. Propagação (Radar de Aprendizado)
            if propagate:
                self._propagate_training_action(field_id, slot_id, p_data, link_obj)
        else:
            self.current_card.mark_field_validated(field_id, False)
            f = self.current_card.fields.get(field_id)
            if f and hasattr(f, 'clear'): f.clear()
            self.log(f"⚠️ Feedback de FALHA salvo para '{field_id}:{slot_id}'")

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
        prefix = "❌ ERRO" if p.get('issues') else "⚠️ INCERTO"
        reason = p['issues'][0] if p.get('issues') else f"Confiança Baixa ({conf*100:.0f}%)"
        
        item_text = f"{prefix} | {p['name']} | {reason}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, p['id']) # ID do pilar
        
        if p.get('issues'): item.setForeground(Qt.red)
        else: item.setForeground(Qt.yellow)
        
        self.list_issues.addItem(item)

    def on_issue_clicked(self, item):
        """Ao clicar na pendência, abre o pilar e foca no erro."""
        p_id = item.data(Qt.UserRole)
        for i in range(self.list_pillars.count()):
            it = self.list_pillars.item(i)
            if it.data(Qt.UserRole) == p_id:
                self.list_pillars.setCurrentItem(it)
                self.on_list_pillar_clicked(it)
                self.tabs.setCurrentIndex(0) # Volta pra aba Pilares
                break

    def _update_all_lists_ui(self):
        """Atualiza visual de todas as listas (cores e pendências)"""
        self.list_issues.clear()
        for i in range(self.list_pillars.count()):
            item = self.list_pillars.item(i)
            p_id = item.data(Qt.UserRole)
            p = next((x for x in self.pillars_found if x['id'] == p_id), None)
            if p:
                conf_map = p.get('confidence_map', {}).values()
                avg_conf = sum(conf_map) / len(conf_map) if conf_map else 0.5
                
                if p.get('issues'):
                    item.setForeground(Qt.red)
                    self._add_to_issues_list(p, avg_conf)
                    self.canvas.update_pillar_visual_status(p_id, "error")
                elif avg_conf < 0.6:
                    item.setForeground(Qt.yellow)
                    self._add_to_issues_list(p, avg_conf)
                    self.canvas.update_pillar_visual_status(p_id, "uncertain", avg_conf)
                else:
                    item.setForeground(Qt.white)
                    self.canvas.update_pillar_visual_status(p_id, "default")

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
                    self._log_training_action(item_data, f_id, slot_id, lk, status='valid', comment='Card Validation')

        # 2. Salvar imediatamente no projeto e atualizar UI
        if self.current_project_id:
            if 'pilar' in elem_type:
                self.db.save_pillar(item_data, self.current_project_id)
                target_list = self.list_pillars
                valid_list = self.list_pillars_valid
            elif 'viga' in elem_type:
                self.db.save_beam(item_data, self.current_project_id)
                target_list = self.list_beams
                valid_list = self.list_beams_valid
            elif 'laje' in elem_type:
                self.db.save_slab(item_data, self.current_project_id)
                target_list = self.list_slabs
                valid_list = self.list_slabs_valid
            else:
                return

            # Atualizar item na lista de origem
            for i in range(target_list.count()):
                 it = target_list.item(i)
                 if it.data(Qt.UserRole) == p_id:
                     if " ✅" not in it.text():
                        it.setText(it.text() + " ✅")
                     it.setForeground(Qt.green)
                     break
            
            # Adicionar à lista validada (evitar duplicados visuais)
            found_v = False
            for i in range(valid_list.count()):
                if valid_list.item(i).data(Qt.UserRole) == p_id:
                    found_v = True
                    break
            
            if not found_v:
                item_text = f"{name} (Validado)"
                item_v = QListWidgetItem(item_text)
                item_v.setData(Qt.UserRole, p_id)
                item_v.setForeground(Qt.green)
                valid_list.addItem(item_v)
        
        self.log(f"✅ Item {name} ({elem_type}) validado e arquivado.")

    # --- NOVOS MÉTODOS DE GERENCIAMENTO ---

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
                try:
                    print(f"DEBUG: Iniciando DXF Loader: {dxf_path}")
                    loaded_dxf = DXFLoader.load_dxf(dxf_path)
                    print("DEBUG: DXF Loader completado.")
                    cache_entry['dxf_data'] = loaded_dxf
                except Exception as e:
                    self.log(f"Erro ao carregar DXF {dxf_path}: {e}")
                    print(f"DEBUG: DXF Error: {e}")

        # Ativa a aba e Força atualização manual pois bloqueamos o sinal inicial
        print("DEBUG: Switching tab index...")
        self.project_tabs.setCurrentIndex(new_idx)
        print("DEBUG: Manually calling on_project_tab_changed...")
        self.on_project_tab_changed(new_idx)

    def on_project_tab_changed(self, index):
        """Muda o contexto global da aplicação para o projeto da aba selecionada."""
        print(f"DEBUG: on_project_tab_changed triggered with index={index}")
        if index < 0: 
            print("DEBUG: Index < 0. Ignoring.")
            return
        
        # Verify tabBar data existence
        pid = self.project_tabs.tabBar().tabData(index)
        print(f"DEBUG: Retrieved PID from tabData: {pid}")

        if not pid or pid not in self.loaded_projects_cache: 
            print(f"DEBUG: PID invalid or not in cache. PID={pid}, CacheKeys={list(self.loaded_projects_cache.keys())}")
            return
        
        # Salva estado do projeto anterior (opcional, se editável em tempo real)
        # self.save_project_action() # Talvez agressivo demais? Melhor manual.
        
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
        self.beams_found = project_data['beams'] # Beams ainda incompleto no parser, mas estrutura existe
        
        self.dxf_data = project_data['dxf_data'] # Geometria bruta

        self._update_all_lists_ui()
        
        # 3. Atualizar Canvas
        print("DEBUG: Updating Canvas...")
        self.canvas.clear_interactive()
        
        # Note: add_dxf_entities does scene.clear() internally
        
        # Redesenhar DXF Background
        if self.dxf_data:
            print("DEBUG: Drawing DXF entities...")
            self.canvas.add_dxf_entities(self.dxf_data)
        else:
            self.canvas.scene.clear()
            print("DEBUG: No DXF data to draw.")
        
        # Redesenhar Itens Interativos
        print(f"DEBUG: Drawing {len(self.pillars_found)} pillars...")
        self.canvas.draw_interactive_pillars(self.pillars_found)
        self.canvas.draw_slabs(self.slabs_found)
        # draw_beams if exists
        
        # Resetar visual
        self.right_panel.setCurrentIndex(0) # Placeholder
        print("DEBUG: Canvas update finished.")
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents() # Force UI refresh

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
        """Refresha todas as listas com dados atuais"""
        self.list_pillars.clear()
        self.list_pillars_valid.clear()
        self.list_slabs.clear()
        self.list_slabs_valid.clear()
        # Beams...
        
        for p in self.pillars_found:
            status = "✅" if p.get('is_validated') else "❓"
            if p.get('issues'): status = "⚠️"
            
            t = f"{p.get('name', '?')} {status}"
            item = QListWidgetItem(t)
            item.setData(Qt.UserRole, p['id'])
            if p.get('is_validated'): item.setForeground(Qt.green)
            
            self.list_pillars.addItem(item)
            if p.get('is_validated'):
                self.list_pillars_valid.addItem(QListWidgetItem(item)) # Clone
                
        for s in self.slabs_found:
             t = f"{s.get('name', 'Laje')} ({s.get('area',0):.1f}m²)"
             item = QListWidgetItem(t)
             item.setData(Qt.UserRole, s['id'])
             self.list_slabs.addItem(item)
    
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
        item_id = item.data(Qt.UserRole)
        
        reply = QMessageBox.question(self, "Confirmar Exclusão", 
                                   f"Tem certeza que deseja excluir este item ({item.text()})?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        # 1. Remover da UI
        row = list_widget.row(item)
        list_widget.takeItem(row)

        # 2. Remover da Memória (Análise ou Lib)
        target_list = None
        if item_type == 'pillar':
             target_list = self.pillars_found
        elif item_type == 'beam':
             target_list = self.beams_found
        elif item_type == 'slab':
             target_list = self.slabs_found
             
        if target_list is not None:
            # Remover do dict pelo ID
            start_count = len(target_list)
            target_list[:] = [x for x in target_list if x['id'] != item_id]
            
            if len(target_list) < start_count:
                self.log(f"🗑️ Item {item_id} removido da memória.")
                # Atualizar visualização no Canvas se necessário
                if item_type == 'pillar':
                    self.canvas.draw_interactive_pillars(self.pillars_found)
                elif item_type == 'slab':
                    self.canvas.draw_slabs(self.slabs_found)

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
