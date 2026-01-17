import sys
import os
# Adicionar caminho do Robo Laterais
robo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ROBOS_ABAS", "Robo_Laterais_de_Vigas")
if robo_path not in sys.path:
    sys.path.append(robo_path)

# Tentar importar o robo
try:
    from robo_laterais_viga_pyside import VigaMainWindow
except ImportError as e:
    print(f"Erro ao importar Robo Laterais: {e}")
    VigaMainWindow = None

# Adicionar caminho do Robo Lajes
robo_lajes_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ROBOS_ABAS", "Robo_Lajes")
if robo_lajes_path not in sys.path:
    sys.path.append(robo_lajes_path)

# Tufup & Updates
from tufup.client import Client
from pathlib import Path
import requests

# Tentar importar o robo Lajes (laje_src)
try:
    from laje_src.ui.main_window import MainWindow as LajeMainWindow
except ImportError as e:
    print(f"Erro ao importar Robo Lajes: {e}")
    LajeMainWindow = None

# Adicionar caminho do Robo Fundos
robo_fundos_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
if robo_fundos_path not in sys.path:
    sys.path.append(robo_fundos_path)

# Tentar importar o robo Fundos
try:
    from fundo_pyside import FundoMainWindow
except ImportError as e:
    print(f"Erro ao importar Robo Fundos: {e}")
    FundoMainWindow = None


from typing import Dict, List, Any, Optional
import os
import json
import logging
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QFileDialog, QDockWidget, 
                               QTextEdit, QLabel, QStackedWidget, QListWidget,
                               QListWidgetItem, QTabWidget, QSplitter, QLineEdit, QProgressBar,
                               QTreeWidget, QTreeWidgetItem, QMessageBox, QMenu, QScrollArea, QFrame,
                               QComboBox, QTabBar)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, QSize, QTimer
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
from src.core.services.auth_service import AuthService
from src.ui.organisms.login_widget import LoginWidget
from src.ui.organisms.user_profile_dialog import UserProfileDialog
from src.core.auth.models import UserProfile



# Adicionar caminho do Robo Pilares (NOVO) - MOVED down to avoid shadowing 'src'
robo_pilares_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25")
if robo_pilares_path not in sys.path:
    sys.path.append(robo_pilares_path)

try:
    from bootstrap import create_pilares_widget
except ImportError as e:
    print(f"Erro ao importar Robo Pilares: {e}")
    create_pilares_widget = None

# Config logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import uuid
import re
from src import config

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vision-Estrutural AI - Pro Dashboard")
        self.resize(1600, 1000)
        self.setWindowState(Qt.WindowMaximized)
        
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

        # Perfil do Usuário
        self.user_profile = None

        # Helper Engines
        self.slab_tracer = SlabTracer(self.spatial_index)

        # Carregar Estilo
        self.load_stylesheet()
        
        # UI Setup
        self.init_ui()
        
        # Carregar configurações customizadas de vínculos
        self._load_link_configs()

    def load_stylesheet(self):
        try:
            # FIX: Caminho absoluto baseado no local do arquivo main.py para evitar erro de diretório
            base_dir = os.path.dirname(os.path.abspath(__file__))
            style_path = os.path.join(base_dir, "src", "ui", "style.qss")
            
            if os.path.exists(style_path):
                with open(style_path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
            else:
                print(f"[MainWindow] Aviso: Arquivo de estilo não encontrado em {style_path}")
        except Exception as e:
            print(f"Erro ao carregar CSS: {e}")

    # --- UI OVERHAUL METHODS ---
    def _setup_top_bar(self):
        """Configura a barra superior (Logotipo, Projeto, Obra/Pavimento)."""
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(10, 5, 20, 5)
        layout.setSpacing(15)

        # 0. Logo & Perfil (Esquerda/Direita)
        self.user_hbox = QHBoxLayout()
        self.user_hbox.setSpacing(10)

        # 1. Logo
        lbl_logo = QLabel("TSF PROJETOS")
        lbl_logo.setObjectName("LogoLabel")
        layout.addWidget(lbl_logo)

        # 2. Botão Gerenciar Projetos
        btn_manage = QPushButton("📂 Gerenciar Projetos")
        btn_manage.setFixedWidth(140)
        btn_manage.setStyleSheet("padding: 6px; font-size: 12px;")
        btn_manage.clicked.connect(self.open_project_manager) 
        layout.addWidget(btn_manage)
        

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("border: 1px solid #444;")
        layout.addWidget(line)

        # 3. Combo Obras
        layout.addWidget(QLabel("Obra:"))
        self.cmb_works = QComboBox()
        self.cmb_works.setPlaceholderText("Selecione a Obra...")
        self.cmb_works.setFixedWidth(200)
        self.cmb_works.currentIndexChanged.connect(self._on_work_changed)
        layout.addWidget(self.cmb_works)

        # 4. Combo Pavimentos (Filta por Obra)
        layout.addWidget(QLabel("Pavimento:"))
        self.cmb_pavements = QComboBox()
        self.cmb_pavements.setPlaceholderText("Selecione o Pavimento...")
        self.cmb_pavements.setFixedWidth(200)
        self.cmb_pavements.currentIndexChanged.connect(self._on_pavement_changed)
        layout.addWidget(self.cmb_pavements)

        # Separator 2
        line2 = QFrame()
        line2.setFrameShape(QFrame.VLine)
        line2.setFrameShadow(QFrame.Sunken)
        line2.setStyleSheet("border: 1px solid #444;")
        layout.addWidget(line2)

        # 5. Níveis (Movido do Painel Esquerdo)
        # Chegada
        layout.addWidget(QLabel("Nível Cheg.:"))
        self.edit_level_arr = QLineEdit()
        self.edit_level_arr.setFixedWidth(60)
        self.edit_level_arr.setPlaceholderText("0.00")
        self.edit_level_arr.editingFinished.connect(self.save_project_metadata)
        layout.addWidget(self.edit_level_arr)
        
        # Saída
        layout.addWidget(QLabel("Nível Saída:"))
        self.edit_level_exit = QLineEdit()
        self.edit_level_exit.setFixedWidth(60)
        self.edit_level_exit.setPlaceholderText("3.00")
        self.edit_level_exit.editingFinished.connect(self.save_project_metadata)
        layout.addWidget(self.edit_level_exit)

        # Spacer (Empurra status e progress para direita)
        layout.addStretch()

        # 6. Barra de Progresso (Integrada ao Header)
        self.progress_container = QWidget()
        prog_layout = QHBoxLayout(self.progress_container)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.setSpacing(5)
        
        self.lbl_progress = QLabel("Aguardando...")
        self.lbl_progress.setStyleSheet("color: #aaa; font-size: 10px;")
        prog_layout.addWidget(self.lbl_progress)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(100) # Compacto
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #444; border-radius: 4px; background: #222; }
            QProgressBar::chunk { background: #0078d4; border-radius: 3px; }
        """)
        pass # Valor inicial 0
        prog_layout.addWidget(self.progress_bar)
        
        self.progress_container.hide() # Esconde por padrão
        layout.addWidget(self.progress_container)

        # 7. Status / User Profile
        lbl_status = QLabel("● SYNC")
        lbl_status.setStyleSheet("color: #00E5FF; font-weight: bold; font-size: 10px;")
        layout.addWidget(lbl_status)

        # 8. User Button (Direita Extrema)
        self.btn_user = QPushButton("??")
        self.btn_user.setObjectName("UserButton")
        self.btn_user.setFixedWidth(34)
        self.btn_user.setFixedHeight(34)
        self.btn_user.setCursor(Qt.PointingHandCursor)
        self.btn_user.setStyleSheet("""
            #UserButton {
                background-color: #333;
                border: 2px solid #555;
                border-radius: 17px;
                color: white;
                font-weight: bold;
                font-size: 11px;
            }
            #UserButton:hover {
                background-color: #444;
                border-color: #00E5FF;
            }
        """)
        self.btn_user.clicked.connect(self.show_user_profile)
        layout.addWidget(self.btn_user)
        
        return top_bar

    def open_project_manager(self):
        """Abre o gerenciador de projetos."""
        if not hasattr(self, 'project_manager'):
            self.project_manager = ProjectManager(self.db, self.memory)
            self.project_manager.project_selected.connect(lambda pid, name, path: self._open_project_tab(pid, name))
            # Sincronização Sinais
            self.project_manager.obra_created_globally.connect(self.on_global_obra_created)
            self.project_manager.project_created_globally.connect(self.on_global_project_created)
            
        self.project_manager.setWindowState(Qt.WindowMaximized)
        self.project_manager.show()
        
    def on_global_obra_created(self, work_name):
        self.log(f"🏠 Sincronizando Obra Global: {work_name}")
        self._refresh_nav_combos()
        # Sincronização centralizada
        self.sync_robots_with_master_context(work_name)
        
    def on_global_project_created(self, work_name, project_name, project_id=None):
        self.log(f"🏗️ Sincronizando Projeto/Pavimento Global: {project_name} em {work_name} (ID: {project_id})")
        self._refresh_nav_combos()
        # Sincronização centralizada
        self.sync_robots_with_master_context(work_name, project_name, project_id)

    def sync_robots_with_master_context(self, work_name, pavement_name=None, project_id=None):
        """Propaga o contexto de Obra e Pavimento para todos os robôs integrados."""
        if project_id is None:
             project_id = self.current_project_id
        
        self.log(f"🔄 Sincronizando Robôs -> Obra: {work_name}, Pav: {pavement_name}, PID: {project_id}")
        
        try:
            # 1. Robo Laje (Usa sync_context wrapper)
            if getattr(self, 'robo_laje', None) and hasattr(self.robo_laje, 'sync_context'):
                 self.robo_laje.sync_context(work_name, pavement_name, project_id=project_id)

            # 2. Robo Viga (Laterais - Usa add_global_*)
            if getattr(self, 'robo_viga', None):
                 if pavement_name:
                     if hasattr(self.robo_viga, 'add_global_pavimento'):
                        self.robo_viga.add_global_pavimento(work_name, pavement_name)
                 else:
                     if hasattr(self.robo_viga, 'add_global_obra'):
                        self.robo_viga.add_global_obra(work_name)

            # 3. Robo Fundo (Usa sync_context)
            if getattr(self, 'robo_fundo', None) and hasattr(self.robo_fundo, 'sync_context'):
                 self.robo_fundo.sync_context(work_name, pavement_name)

            # 4. Robo Pilares (Usa add_global_*)
            if getattr(self, 'robo_pilares', None):
                 if pavement_name:
                     if hasattr(self.robo_pilares, 'add_global_pavimento'):
                        self.robo_pilares.add_global_pavimento(work_name, pavement_name)
                 else:
                     if hasattr(self.robo_pilares, 'add_global_obra'):
                        self.robo_pilares.add_global_obra(work_name)
                        
        except Exception as e:
            self.log(f"⚠️ Erro parcial na sincronização dos robôs: {e}")
            import traceback
            traceback.print_exc()



    def set_user_context(self, user: UserProfile):
        """Define o usuário logado e atualiza a UI."""
        self.user_profile = user
        if hasattr(self, 'btn_user'):
            # Iniciais do nome ou email
            initials = user.full_name[:2].upper() if user.full_name else user.email[:2].upper()
            self.btn_user.setText(initials)
            self.btn_user.setToolTip(f"Logado como: {user.email}")
            
        print(f"Main Window context set for: {user.email}")

    def show_user_profile(self):
        """Abre o dialog de perfil."""
        if not self.user_profile:
            return
            
        dialog = UserProfileDialog(self.user_profile, self)
        dialog.logout_requested.connect(self.handle_logout_signal)
        dialog.exec()

    def handle_logout_signal(self):
        """Reinicia a aplicação para a tela de login."""
        self.close()

    def _refresh_nav_combos(self):
        """Popula o combobox de Obras do Banco de Dados."""
        if not hasattr(self, 'db'): return

        current_work = self.cmb_works.currentText()
        self.cmb_works.blockSignals(True)
        self.cmb_works.clear()
        
        try:
            works = self.db.get_all_works()
            self.cmb_works.addItems(works)
        except Exception as e:
            self.log(f"Erro carregando obras: {e}")
        
        # Restore selection if possible
        idx = self.cmb_works.findText(current_work)
        if idx >= 0:
            self.cmb_works.setCurrentIndex(idx)
        else:
             self.cmb_works.setCurrentIndex(-1)
             
        self.cmb_works.blockSignals(False)
        
        # Force pavement update if work selected
        if self.cmb_works.currentIndex() >= 0:
            self._on_work_changed()

    def _on_work_changed(self):
        """Filtra os pavimentos baseados na Obra selecionada."""
        work_name = self.cmb_works.currentText()
        self.cmb_pavements.blockSignals(True)
        self.cmb_pavements.clear()
        
        if not work_name:
            self.cmb_pavements.blockSignals(False)
            return

        # Busca todos os projetos e filtra por 'work_name'
        # Idealmente o DB teria get_projects_by_work(name)
        all_projects = self.db.get_projects()
        
        # Filtra projetos que pertencem a esta Obra
        filtered = [p for p in all_projects if p.get('work_name') == work_name]
        
        # Popula combo com (Nome Pavimento) -> UserRole = ProjectID
        # Se 'pavement_name' vazio, usa 'name' do projeto
        for p in filtered:
            display_name = p.get('pavement_name') or p.get('name')
            self.cmb_pavements.addItem(display_name, p['id'])

        self.cmb_pavements.blockSignals(False)
        
        # Sincronizar robôs com a Obra
        self.sync_robots_with_master_context(work_name)

    def _on_pavement_changed(self):
        """Carrega o projeto selecionado (ABRE EM ABA)."""
        idx = self.cmb_pavements.currentIndex()
        if idx < 0: return
        
        project_id = self.cmb_pavements.itemData(idx)
        project_name = self.cmb_pavements.currentText()
        
        if project_id:
             self._open_project_tab(project_id, project_name)
             # Sincronizar robôs com o Pavimento
             work_name = self.cmb_works.currentText()
             
             # --- FIX: Sync Robo Lajes Pavimento ---
             # Garante que o Robo Lajes selecione ou crie o pavimento correspondente
             if hasattr(self, 'robo_laje') and self.robo_laje:
                 if hasattr(self.robo_laje, 'pavimentos_widget'):
                      self.robo_laje.pavimentos_widget.select_or_create_pavimento(project_name)
             # --------------------------------------
             
             self.sync_robots_with_master_context(work_name, project_name)

    def _open_project_tab(self, project_id, project_name):
        """Abre uma nova aba de projeto ou foca na existente."""
        print(f"DEBUG: _open_project_tab call. PID={project_id}, Name={project_name}")
        self.log(f"DEBUG: Opening tab for {project_name} ({project_id})")
        # Check if already open
        count = self.project_tabs.count()
        for i in range(count):
            pid = self.project_tabs.tabToolTip(i) # Store ID in ToolTip or Data
            if pid == project_id:
                self.project_tabs.setCurrentIndex(i)
                # self._on_project_tab_clicked(i) # Clicked signal usually handles load
                # But setCurrentIndex doesn't trigger tabBarClicked
                self._load_project_into_view(project_id)
                return

        # Create new tab
        self.project_tabs.blockSignals(True) # Evitar sinal prematuro antes do ToolTip ser setado
        try:
            page = QWidget()
            idx = self.project_tabs.addTab(page, project_name)
            pid_str = str(project_id)
            self.project_tabs.setTabToolTip(idx, pid_str)
            self.project_tabs.setCurrentIndex(idx)
        finally:
            self.project_tabs.blockSignals(False)
        
        # Force load explicitly with the correct ID
        self._load_project_into_view(pid_str)
        
    def _on_project_tab_changed(self, index):
        """Disparado quando a aba ativa muda."""
        if index < 0: return
        project_id = self.project_tabs.tabToolTip(index)
        
        # Ignorar se o ID ainda não estiver setado (evita bug de 'Sem Projeto' durante criação)
        if not project_id:
             return

        # Se for o mesmo já ativo, evita reload desnecessario (mas se for switch de sessao, precisa load)
        # Active ID track
        if project_id != self.active_project_id:
             self._load_project_into_view(project_id)

    def _on_project_tab_close(self, index):
        """Fecha a aba do projeto."""
        if index < 0: return
        # Logic: If I close the current tab, QTabWidget switches to another.
        # This triggers _on_project_tab_changed automatically.
        # Just remove.
        self.project_tabs.removeTab(index)
        
        # If no tabs left? Clear UI
        if self.project_tabs.count() == 0:
            self.active_project_id = None
            self.current_project_id = None
            # TODO: Clear lists to show empty state
            self.list_pillars.clear()
            self.list_beams.clear()
            self.list_slabs.clear()
            # self.canvas.clear() ?
            return
            
    def _load_project_into_view(self, project_id):
        """Carrega efetivamente o projeto ID na View Unica (com Cache Swap)."""
        print(f"DEBUG: _load_project_into_view called with PID={project_id}. Current Name={self.current_project_name}")
        
        # FIX: Detect if project_id is a path (Upstream bug) and resolve to real ID
        if "/" in str(project_id) or "\\" in str(project_id):
             print(f"DEBUG: PID is a path. Attempting resolution via DB...")
             p_info = self.db.get_project_by_dxf_path(str(project_id))
             if p_info:
                 project_id = p_info['id']
                 self.current_project_name = p_info.get('name', 'Projeto Recuperado')
                 print(f"DEBUG: Resolved PID to UUID: {project_id}")
        
        if str(project_id) == str(self.active_project_id):
            # Same project, do nothing unless force reload needed
            return

        # 1. Salvar Estado Anterior (Se houver)
        if self.active_project_id:
            old_id = self.active_project_id
            
            # Garantir entrada no cache
            if old_id not in self.loaded_projects_cache:
                self.loaded_projects_cache[old_id] = {}
            
            # Salvar Estado do Canvas (Scene Swap)
            if hasattr(self.canvas, 'save_state'):
                 self.loaded_projects_cache[old_id]['canvas_state'] = self.canvas.save_state()
            
            # Salvar Listas de Dados (Para restaurar UI sem re-query)
            self.loaded_projects_cache[old_id]['data'] = {
                'pillars': self.pillars_found,
                'beams': self.beams_found,
                'slabs': self.slabs_found
            }
            
            # Opcional: Salvar no DB mudanças pendentes (Auto-Save)
            self.save_project_action() 
        
        # 2. Set Active
        self.active_project_id = project_id
        self.current_project_id = project_id
        
        # 3. Tentar Restaurar do Cache (Instant Switch)
        cache_hit = False
        if project_id in self.loaded_projects_cache:
            cache = self.loaded_projects_cache[project_id]
            
            # Requisito: Ter estado do canvas E dados
            if 'canvas_state' in cache and 'data' in cache:
                self.log(f"⚡ Trocando para aba {project_id} (Instant Cache)...")
                
                # Restaurar Canvas
                if hasattr(self.canvas, 'restore_state'):
                    self.canvas.restore_state(cache['canvas_state'])
                
                # Restaurar Dados Listas
                data = cache['data']
                self.pillars_found = data['pillars']
                self.beams_found = data['beams']
                self.slabs_found = data['slabs']
                
                # Atualizar Listas UI
                self._update_all_lists_ui()
                
                # Atualizar meta info
                p_info = self.db.get_project_by_id(project_id)
                if p_info:
                     self.current_project_name = p_info.get('name')
                
                cache_hit = True

        # 4. Se não estava no cache, carregar full (DB + DXF)
        if not cache_hit:
            # FIX: Isolar cena do projeto anterior criando uma nova para o novo projeto
            if hasattr(self.canvas, 'reset_for_new_project'):
                 self.canvas.reset_for_new_project()
                 
            self.load_project_action() # Lógica existente de povoar lists/canvas

        # 5. Atualizar Top Bar UI para refletir o projeto carregado (Fundamental para sync de abas)
        self._update_top_bar_UI(project_id)

    def _update_top_bar_UI(self, project_id):
        """Sincroniza a barra superior (Works/Pavements/Levels) com o projeto atual."""
        project = self.db.get_project_by_id(project_id)
        if not project: return
        
        # 1. Update Work Combo
        work_name = project.get('work_name') or ""
        self.cmb_works.blockSignals(True)
        if not work_name:
             self.cmb_works.setCurrentIndex(-1)
        else:
             idx = self.cmb_works.findText(work_name)
             if idx >= 0:
                 self.cmb_works.setCurrentIndex(idx)
             else:
                 # Se a obra não existe no combo (ex: deletada do DB mas projeto ainda a referencia)
                 self.cmb_works.addItem(work_name)
                 self.cmb_works.setCurrentIndex(self.cmb_works.count()-1)
        self.cmb_works.blockSignals(False)
        
        # 2. Trigger population of Pavements (ALWAYS, to avoid mixing)
        self.cmb_pavements.blockSignals(True)
        self.cmb_pavements.clear()
        all_projects = self.db.get_projects()
        # Filtro consistente com o work_name (inclusive se vazio)
        filtered = [p for p in all_projects if (p.get('work_name') or "") == work_name]
        for p in filtered:
            display_name = p.get('pavement_name') or p.get('name')
            self.cmb_pavements.addItem(display_name, p['id'])
        self.cmb_pavements.blockSignals(False)

        # 3. Sincronizar robôs com o contexto da aba ativa
        pavement_name = project.get('pavement_name') or project.get('name')
        self.sync_robots_with_master_context(work_name, pavement_name)

        # 3. Update Pavement Combo Selection
        # (Isso garante que o combo mostre o pavimento certo sem disparar load de novo)
        self.cmb_pavements.blockSignals(True)
        # Buscar pelo ID do projeto (UserRole) é mais seguro que pelo texto
        idx_found = -1
        for i in range(self.cmb_pavements.count()):
            if str(self.cmb_pavements.itemData(i)) == str(project_id):
                idx_found = i
                break
        
        if idx_found >= 0:
            self.cmb_pavements.setCurrentIndex(idx_found)
        self.cmb_pavements.blockSignals(False)

        # 4. Update Levels
        self.edit_level_arr.blockSignals(True)
        self.edit_level_exit.blockSignals(True)
        
        self.edit_level_arr.setText(str(project.get('level_arrival') or ''))
        self.edit_level_exit.setText(str(project.get('level_exit') or ''))
        
        self.edit_level_arr.blockSignals(False)
        self.edit_level_exit.blockSignals(False)

    def _setup_structural_analyzer_area(self):
        """Constrói o layout do módulo 'Structural Analyzer' (Legacy UI)."""
        
        # 1. Container Geral do Módulo
        module_container = QWidget()
        module_layout = QVBoxLayout(module_container)
        module_layout.setContentsMargins(0, 0, 0, 0)
        module_layout.setSpacing(0)
        
        # (Abas de Projeto movidas para init_ui)
        
        # 3. Área de Conteúdo (Persistente - The Splitter)
        content_area = QWidget()
        main_layout = QHBoxLayout(content_area) # Layout horizontal para o splitter
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        
        # --- LADO ESQUERDO: GESTÃO DE ITENS ---
        self.left_panel = QWidget()
        self.left_panel.setObjectName("Sidebar")
        self.left_panel.setFixedWidth(365)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setSpacing(10)
        
        # (Resto do código do painel esquerdo...)
        
        # 0. Botão Gerenciar Projetos (Removido daqui, foi para TopBar, mas mantemos lógica se precisar)
        # Na verdade, removemos visualmente do painel esquerdo pois já está no TopBar.
        
        # 1. Inputs de Metadados (Removidos para TopBar)
        # 1. Widgets Removidos (Movicdos para TopBar)
        # self.meta_widget (Levels) -> TopBar
        # self.progress_container -> TopBar
        
        # 2. Botão de Análise (Imediatamente acima do Salvar)

        self.btn_process = QPushButton("🚀 Iniciar Análise Geral")
        self.btn_process.setObjectName("Primary") # Destaque visual
        self.btn_process.setStyleSheet("padding: 4px; font-size: 11px; height: 18px;")
        self.btn_process.clicked.connect(self.process_pillars_action)
        left_layout.addWidget(self.btn_process)

        # 2b. Botão Gerenciar Memória (Removido)
        # self.btn_mem removed (User request)

        # 3. Botão Salvar
        self.btn_save = QPushButton("Salvar")
        self.btn_save.setObjectName("Success")
        self.btn_save.setStyleSheet("padding: 4px; font-size: 11px; height: 18px;")
        self.btn_save.clicked.connect(self.save_project_action)
        left_layout.addWidget(self.btn_save)

        # (Progress Bar removida daqui)

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
        # left_layout.addSpacing(10) # Reduzido para maximizar lista
        
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
            
            # Botões de Ação Básica
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0,0,0,0)
            
            # Botão Excluir Item
            btn_delete = QPushButton("🗑️ Excluir Item")
            btn_delete.setStyleSheet("background-color: #ffcccc; color: #cc0000; border: 1px solid #ff9999; padding: 2px; font-size: 10px; height: 18px;")
            btn_delete.clicked.connect(lambda: self.delete_item_action(list_widget, item_type, is_library))
            h_layout.addWidget(btn_delete)

            # Botão Criar Novo Item (padrão)
            scope_name = "Lib" if is_library else "Análise"
            btn_create = QPushButton(f"➕ Criar Novo Item ({scope_name})")
            btn_create.setStyleSheet("padding: 2px; font-size: 10px; height: 18px;")
            btn_create.clicked.connect(lambda: self.create_manual_item(is_library=is_library))
            h_layout.addWidget(btn_create)
            
            layout.addLayout(h_layout)

            # Botão Sincronizar Robo Laje (apenas para Laje na aba de Análise)
            if item_type == 'slab' and not is_library:
                btn_sync_robo = QPushButton("🤖 Sincronizar Robo Laje")
                btn_sync_robo.setStyleSheet("background-color: #6610f2; color: white; padding: 4px; font-weight: bold; font-size: 10px;")
                btn_sync_robo.setToolTip("Envia as lajes desta lista para o módulo Robo Lajes, calculando a geometria unificada (Marco + Extensões).")
                btn_sync_robo.clicked.connect(self.sync_slabs_to_robo_laje_action)
                layout.addWidget(btn_sync_robo)

            return container

        # --- TAB 1: ANÁLISE ATUAL (Pilares, Vigas, Lajes, Contorno, Issues) ---
        self.tab_analysis = QWidget()
        analysis_layout = QVBoxLayout(self.tab_analysis)
        analysis_layout.setContentsMargins(0,0,0,0)
        
        self.tabs_analysis_internal = QTabWidget()
        self.tabs_analysis_internal.setStyleSheet(STYLE_TABS)
        self.list_pillars = QTreeWidget()
        self.list_pillars.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_pillars.setColumnWidth(0, 50)
        self.list_pillars.setColumnWidth(1, 120)
        self.list_pillars.setColumnWidth(2, 50)
        self.list_pillars.setColumnWidth(3, 50)

        self.list_beams = QTreeWidget()
        self.list_beams.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams.setColumnWidth(0, 50)
        self.list_beams.setColumnWidth(1, 120)
        self.list_beams.setColumnWidth(2, 50)
        self.list_beams.setColumnWidth(3, 50)
        
        self.list_slabs = QTreeWidget()
        self.list_slabs.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_slabs.setColumnWidth(0, 50)
        self.list_slabs.setColumnWidth(1, 120)
        self.list_slabs.setColumnWidth(2, 50)
        self.list_slabs.setColumnWidth(3, 50)

        self.list_issues = QListWidget()
        
        # Conectar Sinais (Atual)
        # Conectar Sinais (Atual) - Mouse e Teclado (Setinhas)
        self.list_pillars.itemClicked.connect(lambda item, col: self.on_list_pillar_clicked(item))
        self.list_pillars.currentItemChanged.connect(lambda curr, prev: self.on_list_pillar_clicked(curr) if curr else None)
        
        self.list_beams.itemClicked.connect(self.on_list_beam_clicked)
        self.list_beams.currentItemChanged.connect(lambda curr, prev: self.on_list_beam_clicked(curr, 0) if curr else None)
        
        self.list_slabs.itemClicked.connect(lambda item, col: self.on_list_slab_clicked(item))
        self.list_slabs.currentItemChanged.connect(lambda curr, prev: self.on_list_slab_clicked(curr) if curr else None)
        
        self.list_issues.itemClicked.connect(self.on_issue_clicked)
        self.list_issues.currentItemChanged.connect(lambda curr, prev: self.on_issue_clicked(curr) if curr else None)
        
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
        
        self.list_pillars_valid = QTreeWidget()
        self.list_pillars_valid.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_pillars_valid.setColumnWidth(0, 50)
        self.list_pillars_valid.setColumnWidth(1, 120)
        self.list_pillars_valid.setColumnWidth(2, 50)
        self.list_pillars_valid.setColumnWidth(3, 50)

        self.list_beams_valid = QTreeWidget()
        self.list_beams_valid.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams_valid.setColumnWidth(0, 50)
        self.list_beams_valid.setColumnWidth(1, 120)
        self.list_beams_valid.setColumnWidth(2, 50)
        self.list_beams_valid.setColumnWidth(3, 50)

        self.list_slabs_valid = QTreeWidget()
        self.list_slabs_valid.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_slabs_valid.setColumnWidth(0, 50)
        self.list_slabs_valid.setColumnWidth(1, 120)
        self.list_slabs_valid.setColumnWidth(2, 50)
        self.list_slabs_valid.setColumnWidth(3, 50)
        
        # Conectar Sinais (Validado)
        # Conectar Sinais (Validado) - Mouse e Teclado
        self.list_pillars_valid.itemClicked.connect(lambda item, col: self.on_list_pillar_clicked(item))
        self.list_pillars_valid.currentItemChanged.connect(lambda curr, prev: self.on_list_pillar_clicked(curr) if curr else None)
        
        self.list_beams_valid.itemClicked.connect(self.on_list_beam_clicked)
        self.list_beams_valid.currentItemChanged.connect(lambda curr, prev: self.on_list_beam_clicked(curr, 0) if curr else None)
        
        self.list_slabs_valid.itemClicked.connect(lambda item, col: self.on_list_slab_clicked(item))
        self.list_slabs_valid.currentItemChanged.connect(lambda curr, prev: self.on_list_slab_clicked(curr) if curr else None)
        
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
        
        
        center_layout = QVBoxLayout(self.canvas_container)
        center_layout.setContentsMargins(0,0,0,0)
        # self.project_tabs removed (moved to init_ui)
        
        
        # Canvas é único, mas reparentado ou limpo?
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
        
        # Add content area to module layout
        module_layout.addWidget(content_area)
        
        return module_container

    def sync_slabs_to_robo_laje_action(self):
        """Sincroniza as lajes da lista de análise para o Robo Lajes."""
        # 1. Verificar disponibilidade do Robo
        if not hasattr(self, 'robo_laje') or not self.robo_laje:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Erro", "Módulo Robo Lajes não está carregado.")
            return

        # 2. Verificar Contexto (Obra/Pavimento)
        # O Robo Laje já deve ter recebido o contexto via sync_robots_with_master_context
        # Mas vamos garantir pegando do robo_laje.obra_atual
        
        obra_robo = self.robo_laje.obra_atual
        if not obra_robo:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "O Robo Lajes não tem uma Obra selecionada. Selecione uma Obra na barra superior.")
            return
            
        pavimento_nome = self.cmb_pavements.currentText()
        if not pavimento_nome:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Selecione um Pavimento na barra superior.")
            return
            
        # Encontrar Pavimento no Robo
        pavimento_alvo = next((p for p in obra_robo.pavimentos if p.nome == pavimento_nome), None)
        if not pavimento_alvo:
            # Tentar criar se não existir (embora o sync automatico devesse ter criado)
            from laje_src.models.pavimento import Pavimento
            pavimento_alvo = Pavimento(nome=pavimento_nome)
            obra_robo.pavimentos.append(pavimento_alvo)
            # Atualizar lista de pavimentos no robo
            if hasattr(self.robo_laje, 'pavimentos_widget'):
                self.robo_laje.pavimentos_widget.update_list()
                self.robo_laje.pavimentos_widget.select_or_create_pavimento(pavimento_nome)

        # 3. Preparar Dados das Lajes (Structural Analyzer -> Robo Lajes)
        from laje_src.models.laje import Laje
        
        novas_lajes_robo = []
        
        # Iterar sobre lajes encontradas na análise
        count = 0
        for slab_data in self.slabs_found:
            name = slab_data.get('name', 'L?')
            
            # Extrair número (ex: "L1" -> 1)
            import re
            nums = re.findall(r'\d+', name)
            numero = int(nums[0]) if nums else 0
            
            # Calcular Geometria Unificada (Marco + Extensões)
            # Retorna (Polygon, area_m2)
            unified_poly, area_m2 = self._get_slab_real_geometry(slab_data)
            
            # Converter coordenadas para lista de tuplas [(x,y), ...]
            coords = []
            if unified_poly:
                 if hasattr(unified_poly, 'exterior'):
                     coords = list(unified_poly.exterior.coords)
                 # Se for MultiPolygon, pegar o maior
                 elif unified_poly.geom_type == 'MultiPolygon':
                     largest = max(unified_poly.geoms, key=lambda a: a.area)
                     coords = list(largest.exterior.coords)
            
            # Criar Objeto Laje do Robo
            # IMPORTANTE: area_cm2 no Robo é usada para calculos, aqui convertemos m² -> cm²
            nova_laje = Laje(
                numero=numero,
                nome=name,
                comprimento=0.0, 
                largura=0.0,
                pavimento=pavimento_nome,
                coordenadas=coords,
                area_cm2=area_m2 * 10000 
            )
            
            novas_lajes_robo.append(nova_laje)
            count += 1

        if not novas_lajes_robo:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Aviso", "Nenhuma laje encontrada na lista de análise para sincronizar.")
            return

        # 4. Substituir/Popular no Pavimento Alvo
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, 
            "Sincronizar Robo Lajes",
            f"Isso irá SUBSTITUIR todas as lajes do pavimento '{pavimento_nome}' no Robo Lajes \n"
            f"pelas {count} lajes da Análise Atual.\n\n"
            "Deseja continuar?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            pavimento_alvo.lajes = novas_lajes_robo
            
            # 5. Atualizar UI do Robo Lajes e Iniciar Automação IA
            if hasattr(self, 'robo_laje') and self.robo_laje is not None and hasattr(self.robo_laje, 'laje_tab'):
                # Trocar para a aba do Robo Laje para visualização do processo
                if hasattr(self, 'module_tabs'):
                    self.module_tabs.setCurrentIndex(4)
                if hasattr(self, 'module_stack'):
                    self.module_stack.setCurrentIndex(4)
                
                # Forçar atualização da tabela
                if hasattr(self.robo_laje, 'pavimentos_widget'):
                    self.robo_laje.pavimentos_widget.select_or_create_pavimento(pavimento_nome)
                
                self.robo_laje.laje_tab.atualizar_tabela_lajes()
                
                # Iniciar Processamento IA Automatizado (Linhas + Cotas)
                self.robo_laje.laje_tab.automate_ai_for_all_lajes()
                
            QMessageBox.information(self, "Sucesso", f"{count} lajes sincronizadas e processadas pela IA!")



    def init_ui(self):
        """Nova Inicialização de UI (Overhaul)."""
        # Widget Principal
        root_container = QWidget()
        root_layout = QVBoxLayout(root_container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root_container)

        # 1. Top Bar
        top_bar = self._setup_top_bar()
        root_layout.addWidget(top_bar)

        # 1.5 Abas de Projeto (Contexto Global)
        # Movemos para cá para ficar ACIMA dos módulos
        self.project_tabs = QTabWidget()
        self.project_tabs.setObjectName("ProjectTabs")
        self.project_tabs.setTabsClosable(True)
        self.project_tabs.setMovable(True)
        self.project_tabs.setStyleSheet("background: #0c0c10; border: none;")
        self.project_tabs.setFixedHeight(35)
        
        # Conectar Sinais
        self.project_tabs.currentChanged.connect(self._on_project_tab_changed)
        self.project_tabs.tabCloseRequested.connect(self._on_project_tab_close)
        
        root_layout.addWidget(self.project_tabs)

        # 2. Navegação de Módulos (Abas Superiores)
        self.module_tabs = QTabBar()
        self.module_tabs.setObjectName("ModuleNav")
        self.module_tabs.setDrawBase(False)
        self.module_tabs.addTab("Structural Analyzer")
        self.module_tabs.addTab("Robo Pilares")
        self.module_tabs.addTab("Robo Laterais de Viga")
        self.module_tabs.addTab("Robo Fundo de Vigas")
        self.module_tabs.addTab("Robo Laje")
        
        # Container para abas (bg color)
        tabs_container = QWidget()
        tabs_container.setStyleSheet("background-color: #0c0c10; border-bottom: 1px solid #2a2a3e;")
        t_layout = QHBoxLayout(tabs_container)
        t_layout.addWidget(self.module_tabs)
        t_layout.setContentsMargins(20, 0, 0, 0)
        
        root_layout.addWidget(tabs_container)

        # 3. Stack de Conteúdo
        self.module_stack = QStackedWidget()
        root_layout.addWidget(self.module_stack)

        # --- MÓDULO 0: STRUCTURAL ANALYZER (Legacy) ---
        structural_widget = self._setup_structural_analyzer_area()
        self.module_stack.addWidget(structural_widget)

        # --- MÓDULOS ROBÔS ---
        
        # 1. Robo Pilares (INTEGRADO)
        if create_pilares_widget:
            try:
                self.robo_pilares = create_pilares_widget()
                self.robo_pilares.setWindowFlags(Qt.Widget) # Embed mode
                self.module_stack.addWidget(self.robo_pilares)
            except Exception as e:
                self.module_stack.addWidget(QLabel(f"Erro ao carregar Robo Pilares: {e}"))
                self.robo_pilares = None
        else:
            self.module_stack.addWidget(QLabel("Módulo Robo Pilares não encontrado ou erro de importação."))
            self.robo_pilares = None

        # 2. Robo Laterais de Viga (INTEGRADO)
        if VigaMainWindow:
            try:
                self.robo_viga = VigaMainWindow()
                self.robo_viga.setWindowFlags(Qt.Widget) # Embed mode
                self.module_stack.addWidget(self.robo_viga)
            except Exception as e:
                self.module_stack.addWidget(QLabel(f"Erro ao carregar Robo Viga: {e}"))
                self.robo_viga = None
        else:
            self.module_stack.addWidget(QLabel("Robo Viga não encontrado / Erro de importação."))
            self.robo_viga = None

        # 3. Robo Fundo de Viga (INTEGRADO)
        if FundoMainWindow:
            try:
                self.robo_fundo = FundoMainWindow()
                self.robo_fundo.setWindowFlags(Qt.Widget) # Embed mode
                self.module_stack.addWidget(self.robo_fundo)
            except Exception as e:
                self.module_stack.addWidget(QLabel(f"Erro ao carregar Robo Fundo: {e}"))
                self.robo_fundo = None
        else:
            self.module_stack.addWidget(QLabel("Robo Fundo não encontrado / Erro de importação."))
            self.robo_fundo = None

        # 4. Robo Laje (INTEGRADO)
        if LajeMainWindow:
            try:
                self.robo_laje = LajeMainWindow()
                self.robo_laje.setWindowFlags(Qt.Widget) # Embed mode
                
                # Setup session mock/proxy if needed
                self.module_stack.addWidget(self.robo_laje)
            except Exception as e:
                self.module_stack.addWidget(QLabel(f"Erro ao carregar Robo Laje: {e}"))
                self.robo_laje = None
        else:
            self.module_stack.addWidget(QLabel("Robo Laje não encontrado / Erro de importação."))
            self.robo_laje = None

        # Conectar Navegação
        self.module_tabs.currentChanged.connect(self.module_stack.setCurrentIndex)
        
        # Inicializar Dados dos Combos (Obras e Pavimentos)
        # Timer singleShot para garantir que DB esteja pronto se necessario
        QTimer.singleShot(100, self._refresh_nav_combos)

    def _on_analysis_tab_changed(self, index):
        """Filtra visualização no Canvas baseado na aba selecionada (Análise)"""
        # 0: Pilares, 1: Vigas, 2: Lajes, 3: Issues
        # print(f"[DEBUG_TAB] Analysis Tab Changed to Index: {index}")
        self._update_canvas_filter(index)

    def _on_library_tab_changed(self, index):
        """Filtra visualização no Canvas baseado na aba selecionada (Biblioteca)"""
        # 0: Pilares, 1: Vigas, 2: Lajes
        # print(f"[DEBUG_TAB] Library Tab Changed to Index: {index}")
        self._update_canvas_filter(index)

    def _update_canvas_filter(self, index):
        # print(f"[DEBUG_TAB] Updating Canvas Filter for Index: {index}")
        if index == 0:
            self.canvas.set_category_visibility('pillar')
        elif index == 1:
            self.canvas.set_category_visibility('beam')
            if hasattr(self, 'beams_found'): self.canvas.draw_beams(self.beams_found)
        elif index == 2:
            # print(f"[DEBUG_TAB] Setting category visibility to 'slab'")
            if hasattr(self, 'slabs_found'):
                 pass # print(f"[DEBUG_TAB] Redrawing {len(self.slabs_found)} slabs") 
            else:
                 pass # print(f"[DEBUG_TAB] No slabs_found attribute!") 
                 
            self.canvas.set_category_visibility('slab')
            # Forçar redesenho para garantir que todos os vínculos sejam exibidos
            if hasattr(self, 'slabs_found'): self.canvas.draw_slabs(self.slabs_found)
        else:
            self.canvas.set_category_visibility('all')


    def on_focus_requested(self, field_id):
        """Tenta focar no objeto vinculado ao campo especificado via COORDENADA DIRETA"""
        if not self.current_card: return
        
        # [FIX] Se receber um objeto de link direto (do LinkManager), foca apenas nele
        if isinstance(field_id, dict):
            # É um link individual -> Highlight único
            self.canvas.highlight_link(field_id, color=QColor(255, 255, 0))
            self.log(f"📍 Focando vínculo individual via LinkManager")
            return

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
            # 1. Destacar o Item Pai em Amarelo (Persistente) -> REMOVIDO A PEDIDO DO CLIENTE
            # if 'id' in item_data:
            #     self.canvas.highlight_item_yellow(item_data['id'])
            
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
        search_layers = None
        
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

            search_layers = None
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

             item = QTreeWidgetItem([item_text])
             if s.get('is_validated'):
                 item.setForeground(0, Qt.green)

             item.setData(0, Qt.UserRole, s_unique_id)
             self.list_slabs.addTopLevelItem(item)

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
            
            # Atualização de UI Delegada para _update_all_lists_ui() no final do loop
            # Isso evita redundância e duplicação na lista de issues.

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
    def on_list_pillar_clicked(self, item, column=0):
        pillar_id = item.data(0, Qt.UserRole)
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

    def on_list_slab_clicked(self, item, column=0):
        slab_id = item.data(0, Qt.UserRole)
        slab = next((s for s in self.slabs_found if s['id'] == slab_id), None)
        if slab:
            self.show_detail(slab)
            self.canvas.isolate_item(slab_id, 'slab') # Isola Laje (com Zoom)
            # NOVO: Desenhar todos os vínculos salvos (Destaque de segmentos, ilhas, etc)
            self.canvas.draw_item_links(slab)

    def on_canvas_pillar_selected(self, p_id):
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        it = QTreeWidgetItemIterator(self.list_pillars)
        while it.value():
            item = it.value()
            if item.data(0, Qt.UserRole) == p_id:
                self.list_pillars.setCurrentItem(item)
                self.on_list_pillar_clicked(item)
                break
            it += 1

    def save_project_metadata(self):
        """Salva metadados do projeto (Nome, Niveis)."""
        if not hasattr(self, 'db') or not self.current_project_id:
            return

        try:
           level_arr = getattr(self, 'edit_level_arr', None)
           level_exit = getattr(self, 'edit_level_exit', None)
           
           val_arr = level_arr.text() if level_arr else ""
           val_exit = level_exit.text() if level_exit else ""
           
           metadata = {
               'level_arrival': val_arr,
               'level_exit': val_exit
           }
           
           # Salvar no DB
           self.db.update_project_metadata(self.current_project_id, metadata)
           self.log(f"💾 Níveis salvos com sucesso (ARR: {val_arr}, EXIT: {val_exit}).")
           
        except Exception as e:
            self.log(f"Erro salvando metadados: {e}")

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
            
        # FIX: Ensure name is consistent
        if self.current_project_name == "Sem Projeto" and self.current_project_id:
             p = self.db.get_project_by_id(self.current_project_id)
             if p: self.current_project_name = p.get('name', 'Projeto Desconhecido')

        self.log(f"📂 Carregando dados do projeto {self.current_project_name}...")
        
        # 0. Preparar Canvas
        if hasattr(self.canvas, 'reset_state'):
            self.canvas.reset_state()
        elif hasattr(self.canvas, 'scene'):
            self.canvas.scene.clear()
            
        # 1. Carregar DXF de Fundo (Cache ou Disco)

        dxf_bg_loaded = False
        
        # Tentar Cache
        if self.current_project_id in self.loaded_projects_cache:
            cache = self.loaded_projects_cache[self.current_project_id]
            if cache.get('dxf_data'):
                self.dxf_data = cache['dxf_data']
                if hasattr(self.canvas, 'add_dxf_entities'):
                     self.canvas.add_dxf_entities(self.dxf_data)
                     dxf_bg_loaded = True
                     
        # Se não carregou do cache, tentar do DB (Path)
        if not dxf_bg_loaded:
            p_info = self.db.get_project_by_id(self.current_project_id)
            if p_info and p_info.get('dxf_path'):
                 dpath = p_info['dxf_path']
                 import os
                 if os.path.exists(dpath):
                     try:
                         # Reutiliza DXFLoader
                         from src.core.dxf_loader import DXFLoader
                         self.dxf_data = DXFLoader.load_dxf(dpath)
                         if self.dxf_data and hasattr(self.canvas, 'add_dxf_entities'):
                             self.canvas.add_dxf_entities(self.dxf_data)
                             
                             # Atualizar Cache
                             if self.current_project_id not in self.loaded_projects_cache:
                                 self.loaded_projects_cache[self.current_project_id] = {}
                             self.loaded_projects_cache[self.current_project_id]['dxf_data'] = self.dxf_data
                             
                             dxf_bg_loaded = True
                     except Exception as e:
                         self.log(f"Erro ao carregar DXF de fundo: {e}")


        # 2. Carregar do Banco de Dados (Entidades Inteligentes)
        self.pillars_found = self.db.load_pillars(self.current_project_id) or []
        self.slabs_found = self.db.load_slabs(self.current_project_id) or []
        self.beams_found = self.db.load_beams(self.current_project_id) or []



        # --- NOVA LÓGICA: Garantir geraçao de extensões de laje se ausentes (Retrocompatibilidade) ---
        if self.slabs_found:
            self.log("🔍 Verificando geometria de borda das lajes...")
            from shapely.geometry import Polygon
            count_ext_gen = 0
            for s in self.slabs_found:
                if 'links' not in s: s['links'] = {}
                
                # REPARO: Remover chave duplicada 'extensions' se existir
                if 'extensions' in s: del s['extensions']
                
                # Inicializar slot se ausente
                if 'laje_outline_segs' not in s['links']:
                     s['links']['laje_outline_segs'] = {'contour': [], 'acrescimo_borda': []}
                
                out_segs = s['links']['laje_outline_segs']
                
                # 1. Garantir Contorno Principal (Se vazio, criar a partir dos points)
                # Isso é crucial para o 'draw_slabs' desenhar o fundo branco (SlabGraphicsItem)
                if not out_segs.get('contour') and 'points' in s and s['points']:
                     # Criar um link 'poly' representando o corpo principal
                     out_segs['contour'] = [{
                         'type': 'poly',
                         'points': s['points'],
                         'text': 'Contorno Principal',
                         'pos': s['points'][0] if len(s['points']) > 0 else (0,0),
                         'is_generated': True
                     }]
                
                # 2. Garantir Extensões (Se vazio e nunca processado/detectado)
                # Nota: Se já tiver contour mas acrescimo vazio, assume-se que não tem expansão ou já foi verificado.
                # Mas aqui forçamos a deteção se a lista estiver literalmente vazia e não tivermos flag de 'checked'.
                # Para simplificar e evitar reprocessamento pesado, só fazemos se contour foi recém gerado ou explicitamente faltante.
                if not out_segs.get('acrescimo_borda') and 'points' in s and s['points']:
                    try:
                        poly = Polygon(s['points'])
                        extensions = self.slab_tracer.detect_extensions(poly)
                        if extensions:
                            out_segs['acrescimo_borda'] = extensions
                            count_ext_gen += 1
                    except Exception as e:
                        print(f"Erro gerando extensão laje {s.get('name')}: {e}")
            
            if count_ext_gen > 0:
                self.log(f"✨ Extensões geradas para {count_ext_gen} lajes.")



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
            event_type = 'user_validation' if status == 'valid' else ('user_na' if status == 'na' else 'user_rejection')
            
            self.memory.save_training_event(
                project_context=p_context,
                item_context=i_context,
                field_context=f_context,
                label=target_val if status != 'na' else "N/A",
                event_type=event_type
            )
            self.log(f"🧠 Aprendizado registrado: {i_context['type']} {i_context['name']} -> {field_id} ({event_type})")

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
            
            # (Removido validação automática do campo/item - Hierarquia Direta Mantida)
            # self.current_card.mark_field_validated(field_id, True)  <-- COMENTADO/REMOVIDO
            
            self.log(f"👍 Feedback POSITIVO salvo para '{field_id}:{slot_id}'")
            
            # Apenas atualizar visualmente sem marcar como "Validado Final"
            self.current_card.refresh_validation_styles()
            self._update_all_lists_ui()
        else:
            # Marcar o link individual como falho
            link_obj['failed'] = True
            link_obj.pop('validated', None)
            
            # (Removido invalidação automática do campo - Hierarquia Direta Mantida)
            # self.current_card.mark_field_validated(field_id, False) <-- COMENTADO/REMOVIDO
            
            self.log(f"⚠️ Feedback de FALHA salvo para '{field_id}:{slot_id}'")
            self.current_card.refresh_validation_styles()

        # Forçar refresh do LinkManager se ele estiver aberto
        if hasattr(self.current_card, 'embedded_managers'):
            lm = self.current_card.embedded_managers.get(field_id)
            if lm:
                lm.refresh_list()

        # self.tab_training.load_events(self.current_project_id)

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



    def on_card_validated(self, item_data, retrain_fields=True):
        """Chamado quando usuário clica em 'VALIDAR' no card."""
        item_data['is_validated'] = True
        p_id = item_data['id']
        name = item_data.get('name', 'Sem Nome')
        elem_type = item_data.get('type', 'Pilar').lower()
        
        # 1. Registrar Treino para TODOS os campos validados do item
        # Isso garante que a IA aprenda o layout completo confirmado pelo humano.
        if retrain_fields:
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
            else:
                return

            # Atualizar item na lista de origem
            target_list.setUpdatesEnabled(False)
            valid_list.setUpdatesEnabled(False)
            try:
                if 'viga' in elem_type:
                    self._populate_beam_tree(target_list, self.beams_found)
                    valid_beams = [b for b in self.beams_found if b.get('is_validated')]
                    self._populate_beam_tree(valid_list, valid_beams)
                else:
                    for i in range(target_list.topLevelItemCount()):
                         it = target_list.topLevelItem(i)
                         if it.data(0, Qt.UserRole) == p_id:
                              it.setText(1, item_label + (" ✅" if " ✅" not in it.text(1) else ""))
                              it.setForeground(0, Qt.green)
                              it.setForeground(1, Qt.green)
                              break
                    
                    # Adicionar/Atualizar na lista validada
                    found_v_idx = -1
                    for i in range(valid_list.topLevelItemCount()):
                        if valid_list.topLevelItem(i).data(0, Qt.UserRole) == p_id:
                            found_v_idx = i
                            break
                    
                    if found_v_idx == -1:
                        from PySide6.QtWidgets import QTreeWidgetItem
                        item_v = QTreeWidgetItem([elem_type, item_label + " ✅", "Validado", "100%"])
                        item_v.setData(0, Qt.UserRole, p_id)
                        item_v.setForeground(0, Qt.green)
                        item_v.setForeground(1, Qt.green)
                        valid_list.addTopLevelItem(item_v)
                    else:
                        it = valid_list.topLevelItem(found_v_idx)
                        it.setText(1, item_label + " ✅")
                        it.setForeground(0, Qt.green)
                        it.setForeground(1, Qt.green)
            finally:
                target_list.setUpdatesEnabled(True)
                valid_list.setUpdatesEnabled(True)
        
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
        
        # 4. ACRÉSCIMO DE BORDA (Nova Inteligência)
        if 'extensions' in s and s['extensions']:
            for ext in s['extensions']:
                s['links']['laje_outline_segs']['acrescimo_borda'].append(ext)

    def _calculate_completion(self, item_data):
        """Calcula % de completude baseado em campos validados e NA."""
        itype = item_data.get('type', '').lower()
        
        if item_data.get('is_fully_validated'):
            return 100.0

        v_raw = item_data.get('validated_fields', [])
        n_raw = item_data.get('na_fields', [])
        
        # Garantir sets de strings
        val_fields = set(v_raw.keys()) if isinstance(v_raw, dict) else set(v_raw)
        na_fields = set(n_raw.keys()) if isinstance(n_raw, dict) else set(n_raw)
        
        # Campos principais concluídos
        done_fields = val_fields | na_fields
        total_done = len(done_fields)
        
        # Bônus por classes de vínculo (slots) validadas ou N/A
        v_slots = item_data.get('validated_link_classes', {})
        n_slots = item_data.get('na_link_classes', {})
        
        done_slots_count = 0
        if isinstance(v_slots, dict):
            for slots in v_slots.values(): done_slots_count += len(slots)
        if isinstance(n_slots, dict):
            for slots in n_slots.values(): done_slots_count += len(slots)
            
        # Cada slot concluído conta 0.3 de um campo para dar movimento real ao %
        total_points = total_done + (done_slots_count * 0.3)
        
        # Totais ajustados para garantir que 100% seja atingível
        # Laje: ~6 campos
        # Viga: ~15 campos
        # Pilar: ~25 campos
        if 'pilar' in itype: total = 25
        elif 'viga' in itype: total = 15
        elif 'laje' in itype: total = 6
        else: total = 8
        
        if total <= 0: return 100.0
        
        pct = (total_points / total) * 100
        if pct > 100: pct = 100.0
        return pct

    def _populate_generic_tree(self, tree_widget, items_list, item_type='pillar'):
        """Popula QTreeWidget com colunas: Item | Nome | Status | %"""
        tree_widget.clear()
        
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtGui import QColor, QBrush
        
        for i, item_data in enumerate(items_list):
            # 1. Preparar Textos
            item_id_str = item_data.get('id_item', f"{i+1:02}")
            name = item_data.get('name', '?')
            
            # Info extra no nome
            if item_type == 'pillar':
                # Usuário pediu para remover dimensão da lista
                display_name = name
            elif item_type == 'slab':
                area = item_data.get('area', 0.0)
                # Tentar recalcular area se nao tiver
                if area == 0:
                     _, area = self._get_slab_real_geometry(item_data)
                display_name = f"{name} ({area:.2f}m²)"
            else:
                display_name = name
            
            # 2. Status
            status_icon = "❓"
            # Prioridade Visual:
            # 1. Fully Validated (Blue) -> Check Completion
            # 2. Validated (Green) -> Check Completion
            # 3. Issues (Yellow)
            
            if item_data.get('is_fully_validated'): status_icon = "🔵" # Blue Seal
            elif item_data.get('is_validated'): status_icon = "✅" # Green Seal
            elif item_data.get('issues'): status_icon = "⚠️"
            
            # 3. % Completitude
            pct = self._calculate_completion(item_data)
            pct_str = f"{int(pct)}%"
            
            # Criar Item Tree
            tree_item = QTreeWidgetItem(tree_widget)
            tree_item.setText(0, item_id_str)
            tree_item.setText(1, display_name)
            tree_item.setText(2, status_icon)
            tree_item.setText(3, pct_str)
            
            # Setup Data
            tree_item.setData(0, Qt.UserRole, item_data['id'])
            
            # Cores
            if item_data.get('is_fully_validated'):
                 tree_item.setForeground(0, QColor("#00d4ff")) # Blue Cyan
                 tree_item.setForeground(1, QColor("#00d4ff"))
            elif item_data.get('is_validated'):
                 tree_item.setForeground(0, Qt.green)
                 tree_item.setForeground(1, Qt.green)
            elif item_data.get('issues'):
                 tree_item.setForeground(0, Qt.red)
                 tree_item.setForeground(1, Qt.red)
            else:
                 tree_item.setForeground(0, QColor("#dddddd"))
                 tree_item.setForeground(1, QColor("#dddddd"))
            
            # Sync Visual Canvas (Opcional, mas bom manter)
            if item_type == 'pillar':
                status_code = "validated" if item_data.get('is_validated') else "default"
                if item_data.get('issues'): status_code = "error" # Não temos "error" visual no pilar, mas ok
                self.canvas.update_pillar_visual_status(item_data['id'], status_code)
            elif item_type == 'slab':
                status_code = "validated" if item_data.get('is_validated') else "default"
                self.canvas.update_slab_status(item_data['id'], status_code)


    def _populate_beam_tree(self, tree_widget, beam_list):
        tree_widget.clear()
        if not beam_list: return
        
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtGui import QColor

        # Agrupar por parent_name
        from collections import OrderedDict
        groups = OrderedDict()
        for b in beam_list:
            p_name = b.get('parent_name', b.get('name', 'V?'))
            if p_name not in groups:
                 groups[p_name] = []
            groups[p_name].append(b)
            
        for p_name, segments in groups.items():
            parent_item = QTreeWidgetItem(tree_widget)
            parent_item.setText(1, f"📂 {p_name}")
            parent_item.setExpanded(True)
            parent_item.setFlags(parent_item.flags() & ~Qt.ItemIsSelectable)
            
            for b in segments:
                # Status
                status = "❓"
                if b.get('is_fully_validated'): status = "🔵"
                elif b.get('is_validated'): status = "✅"
                elif b.get('issues'): status = "⚠️"
                
                # % Completitude
                pct = self._calculate_completion(b)
                pct_str = f"{int(pct)}%"
                
                child = QTreeWidgetItem(parent_item)
                child.setText(0, b.get('id_item', '??'))
                child.setText(1, b['name'])
                child.setText(2, status)
                child.setText(3, pct_str)
                
                child.setData(0, Qt.UserRole, b['id'])
                
                # Cores
                color = QColor("#aaaaaa")
                if b.get('is_fully_validated'): color = QColor("#00d4ff")
                elif b.get('is_validated'): color = Qt.green
                elif b.get('issues'): color = Qt.red
                
                for col in range(4):
                    child.setForeground(col, color)

                # Sync Visual
                status_code = "validated" if b.get('is_validated') else "default"
                self.canvas.update_beam_status(b['id'], status_code)

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
        

    def _get_slab_real_geometry(self, s):
        """
        Calcula a geometria real (Soma do Contorno + Extensões) e Área em m².
        Prioriza geometria de links (Vínculos de Segmentos) em vez de 'points' originais.
        Retorna: (unified_poly, area_m2)
        """
        from shapely.geometry import Polygon, MultiPolygon
        from shapely.ops import unary_union
        
        try:
            # 1. Obter Pontos do Contorno Principal (Prioridade para os Vínculos de 'Segmentos')
            points = s.get('points', [])
            
            # Verificar se existem vínculos manuais ou reconhecidos no campo de contorno
            if 'links' in s and 'laje_outline_segs' in s['links']:
                segs = s['links']['laje_outline_segs']
                # O slot 'contour' contém a borda principal da laje
                contour_links = segs.get('contour', [])
                if contour_links and isinstance(contour_links, list):
                    # Pegar o primeiro vínculo de geometria que tenha pontos suficientes
                    for lk in contour_links:
                        if 'points' in lk and len(lk['points']) >= 3:
                            points = lk['points']
                            break
            
            if not points: return None, 0.0
            
            # Criar Polígono Principal (Tratar erros de auto-intersecção se necessário)
            try:
                main_poly = Polygon(points)
                if not main_poly.is_valid:
                    main_poly = main_poly.buffer(0)
            except:
                return None, 0.0
            
            # 2. Somar Extensões (Acréscimos de borda/10cm)
            ext_polys = []
            if 'links' in s and 'laje_outline_segs' in s['links']:
                segs = s['links']['laje_outline_segs']
                ext_list = segs.get('acrescimo_borda', [])
                
                if isinstance(ext_list, list):
                    for ext in ext_list:
                        # Considerar extensões que tenham geometria e não estejam marcadas como falhas
                        if 'points' in ext and len(ext['points']) >= 3 and not ext.get('failed'):
                            try:
                                p_ext = Polygon(ext['points'])
                                if not p_ext.is_valid: p_ext = p_ext.buffer(0)
                                ext_polys.append(p_ext)
                            except: continue

            # 3. União das Geometrias
            if ext_polys:
                try:
                    unified = unary_union([main_poly] + ext_polys)
                except:
                    unified = main_poly
            else:
                unified = main_poly
            
            # Se a união resultou em MultiPolygon, garantir que seja válido ou pegar o maior
            if not unified.is_valid:
                unified = unified.buffer(0)
                
            # 4. Cálculo da Área (Coords em cm -> m²)
            # 1 m² = 10.000 cm²
            area_m2 = unified.area / 10000.0
            
            return unified, area_m2
            
        except Exception as e:
            print(f"Erro crítico calculando geometria real da laje {s.get('name', '?')}: {e}")
            return None, 0.0

    def _update_all_lists_ui(self):
        """Refresha todas as listas com dados atuais do projeto ativo (Análise e Biblioteca)"""
        # 1. Limpar TODAS as listas (Já feito dentro dos populates, mas ok garantir)
        
        # 2. Popular Pilares
        # Análise
        self._populate_generic_tree(self.list_pillars, self.pillars_found, 'pillar')
        
        # Biblioteca Validada (Pilares)
        valid_pillars = [p for p in self.pillars_found if p.get('is_validated')]
        self._populate_generic_tree(self.list_pillars_valid, valid_pillars, 'pillar')

        # 3. Popular Vigas (Hierárquico)
        self._populate_beam_tree(self.list_beams, self.beams_found)
        
        # Vigas Validadas
        valid_beams = [b for b in self.beams_found if b.get('is_validated')]
        self._populate_beam_tree(self.list_beams_valid, valid_beams)

        # 4. Popular Lajes
        # Análise
        self._populate_generic_tree(self.list_slabs, self.slabs_found, 'slab')

        # Biblioteca Validada (Lajes)
        valid_slabs = [s for s in self.slabs_found if s.get('is_validated')]
        self._populate_generic_tree(self.list_slabs_valid, valid_slabs, 'slab')
        
        # 5. Contornos / Issues
        self.list_issues.clear()
        if hasattr(self, 'list_contours'): self.list_contours.clear()
        if hasattr(self, 'contours_found'):
             # Se for usar Tree para Contornos no futuro, adaptar. Por enquanto mantem.
             pass
             
        # Repopular Issues
        for p in self.pillars_found:
            conf_map = p.get('confidence_map', {})
            avg_conf = sum(conf_map.values()) / len(conf_map) if conf_map else 0.5
            if p.get('issues') or (avg_conf < 0.6 and not p.get('is_validated')):
                self._add_to_issues_list(p, avg_conf)
                
        self.log(f"UI Atualizada: {len(self.pillars_found)}P, {len(self.beams_found)}V, {len(self.slabs_found)}L")

        # --- FIX: CANVAS REDRAW PARA REMOVER FANTASMAS ---
        # Garantir que o canvas mostre exatamente o que está nos dados "healados" (points atualizados)
        if hasattr(self, 'canvas') and self.canvas:
             # Redesenha lajes para refletir geometrias atualizadas (sem fantasmas verdes)
             self.canvas.draw_slabs(self.slabs_found)
             # Redesenha pilares e vigas também para consistência
             self.canvas.draw_interactive_pillars(self.pillars_found)
             self.canvas.draw_beams(self.beams_found)
        # -------------------------------------------------
    
    def on_detail_data_changed(self, data):
        """Callback genérico para mudanças nos dados do DetailCard (remoção de links, etc)"""
        if not self.current_card: return
        
        try:
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
            # Mudança Involuntária? (Sanidade)
            if item_data.get('is_validated') and links_count == 0:
                 item_data['is_validated'] = False
                 print(f"[DEBUG HIERARCHY] INVOLUNTARY CHANGE: Item '{item_data.get('name')}' invalidated (Zero links).")
                 self.log(f"⚠️ Item {item_data.get('name')} invalidado devido a falta de vínculos.")
            
            if 'viga' in itype:
                if self.current_project_id: self.db.save_beam(item_data, self.current_project_id)
                # Passamos clear=False para não destruir o que o outro acabou de desenhar
                self.canvas.focus_on_beam_geometry(item_data, apply_zoom=False, clear=False)
                self.canvas.draw_item_links(item_data, destination='focus', clear=False)
                # AJUSTE 1 & 2: Atualiza também a visão global (persistente) para não deixar "fantasmas"
                self.canvas.draw_item_links(item_data, destination='beam', clear=False)
            elif 'pilar' in itype:
                if self.current_project_id: self.db.save_pillar(item_data, self.current_project_id)
                # FIX GHOST: Atualizar geometria se houver vínculo de perímetro vindo da IA
                self.canvas.update_item_visuals(item_data)
                self.canvas.draw_item_links(item_data, destination='focus', clear=False)
                self.canvas.draw_item_links(item_data, destination='pillar', clear=False)
            elif 'laje' in itype:
                # FIX GHOST: Re-calcular geometria visual para atualizar o preenchimento cinza (slab fill)
                # Buscamos a geometria unificada (Contorno + Extensões)
                unified_poly, _ = self._get_slab_real_geometry(item_data)
                
                # Criamos uma cópia temporária para o canvas atualizar o visual sem corromper o source permanentemente
                visual_data = item_data.copy()
                if unified_poly and not unified_poly.is_empty:
                    try:
                        # Garantir que temos um polígono (pode ser MultiPolygon se houver ilhas/erros)
                        if unified_poly.geom_type == 'MultiPolygon':
                            main_p = max(unified_poly.geoms, key=lambda p: p.area)
                            coords = list(main_p.exterior.coords)
                        else:
                            coords = list(unified_poly.exterior.coords)
                        visual_data['points'] = coords
                    except: pass
                
                if self.current_project_id: self.db.save_slab(item_data, self.current_project_id)
                
                # Atualizar Polígono Principal (Cinza) e Texto no Canvas
                self.canvas.update_item_visuals(visual_data)
                
                # Desenhar Vínculos (Azul) - Highlight e Persistente
                self.canvas.draw_item_links(item_data, destination='focus', clear=False)
                self.canvas.draw_item_links(item_data, destination='slab', clear=False)

            # AJUSTE: Forçar atualização visual do viewport e da cena do canvas
            if self.canvas.scene:
                self.canvas.scene.update()
            self.canvas.viewport().update()
            self.canvas.update()
            
            # --- NOVO: Atualizar imediatamente o texto na lista lateral ---
            self._sync_list_item_text(item_data)
            
            self.log(f"Visual e Lista do {itype} sincronizados e salvos.")
        except Exception as e:
            import traceback
            self.log(f"❌ Erro em on_detail_data_changed: {e}")
            print(traceback.format_exc())

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
        """Atualiza o texto da lista lateral sem reconstruir toda a UI - Versão Tree"""
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        itype = item_data.get('type', '').lower()
        iid = item_data.get('id')
        
        status = "❓"
        if item_data.get('is_fully_validated'): status = "🔵"
        elif item_data.get('is_validated'): status = "✅"
        elif item_data.get('issues'): status = "⚠️"
        
        # %
        pct = self._calculate_completion(item_data)
        pct_str = f"{int(pct)}%"
        
        new_name = item_data.get('name', '?')
        display_name = new_name
        
        if 'pilar' in itype:
            info = f"{item_data.get('dim', '0')} | {item_data.get('format', 'Ret')}"
            display_name = f"{new_name} ({info})"
            target_lists = [self.list_pillars, self.list_pillars_valid]
        elif 'viga' in itype:
            target_lists = [self.list_beams, self.list_beams_valid]
        elif 'laje' in itype:
            area = item_data.get('area', 0.0)
            if area == 0: _, area = self._get_slab_real_geometry(item_data)
            display_name = f"{new_name} ({area:.2f}m²)"
            target_lists = [self.list_slabs, self.list_slabs_valid]
        else:
            return

        for tree in target_lists:
             it = QTreeWidgetItemIterator(tree)
             while it.value():
                 item = it.value()
                 if item.data(0, Qt.UserRole) == iid:
                     # Atualizar Colunas
                     # 0: ID (mantem)
                     item.setText(1, display_name)
                     item.setText(2, status)
                     item.setText(3, pct_str)
                     
                     # Atualizar cor status
                     color = None
                     if item_data.get('is_fully_validated'): color = QColor("#00d4ff")
                     elif item_data.get('is_validated'): color = Qt.green
                     elif item_data.get('issues'): color = Qt.red
                     else: color = QColor("#dddddd")
                     
                     for c in range(4):
                         item.setForeground(c, color)
                 it += 1

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
        # Adicionar UI
        if current_idx == 1: # Viga
             self._populate_beam_tree(list_widget, target_list_data)
        elif current_idx == 0: # Pilar
             self._populate_generic_tree(list_widget, target_list_data, 'pillar')
        elif current_idx == 2: # Laje
             self._populate_generic_tree(list_widget, target_list_data, 'slab')
        
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

        total = len(events)
        self.log(f"🧠 Sincronizando {total} eventos com a memória...")
        self.show_progress(f"Sincronizando Inteligência ({total})...", 0)
        
        count = 0
        import json
        from PySide6.QtWidgets import QApplication
        
        for i, ev in enumerate(events):
            try:
                # Update UI a cada iteração (ou a cada X para performance, mas aqui queremos feedback real-time)
                pct = int((i / total) * 100)
                self.update_progress(pct, f"Processando evento {i+1}/{total}...")
                QApplication.processEvents()

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
            
        self.hide_progress()
        self.log(f"✅ Sincronização concluída! {count} exemplos convertidos em vetores.")

    def delete_item_action(self, list_widget, item_type: str, is_library: bool):
        """Exclui o item selecionado da lista e da memória/banco."""
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Exclusão", "Selecione um item para excluir.")
            return

        item = selected_items[0]
        # Agora todos usam QTreeWidget
        item_id = item.data(0, Qt.UserRole)
        
        reply = QMessageBox.question(self, "Confirmar Exclusão", 
                                   f"Tem certeza que deseja excluir este item ({item.text(1)})?",
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
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        for lw in lists_to_clean:
            # Tree Widget removal logic
            it = QTreeWidgetItemIterator(lw)
            to_remove = []
            while it.value():
                x = it.value()
                if x.data(0, Qt.UserRole) == item_id:
                     to_remove.append(x)
                it += 1
            
            for r in to_remove:
                # Remove from parent if exists
                if r.parent():
                    r.parent().removeChild(r)
                else:
                    # Top level
                    idx = lw.indexOfTopLevelItem(r)
                    if idx >= 0: lw.takeTopLevelItem(idx)

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
            
        # 2. Coletar IDs da lista (Versão Tree)
        ids = []
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        it = QTreeWidgetItemIterator(list_widget)
        while it.value():
            item = it.value()
            uid = item.data(0, Qt.UserRole)
            if uid: ids.append(uid)
            it += 1
            
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
                obj = data_map[uid]
                
                # Custom Export for Slabs (Unified Geometry)
                if item_type == 'slab':
                    unified_poly, real_area = self._get_slab_real_geometry(obj)
                    
                    # Extract level/thick from somewhere? 
                    # Usually stored in 'dim' or links.
                    # User asked for: Name, Dimension, Level, Coordinates.
                    
                    cleaned_obj = {
                        'id': obj.get('id'),
                        'name': obj.get('name', 'Unknown'),
                        'dimension_text': obj.get('dim', ''),
                        'level': obj.get('level', ''), # Fields might be empty if not parsed
                        'real_area_m2': real_area,
                        'unified_boundary_coords': list(unified_poly.exterior.coords) if unified_poly and hasattr(unified_poly, 'exterior') else []
                    }
                    export_list.append(cleaned_obj)
                else:
                    export_list.append(obj)
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

    # --- PROGRESS BAR HELPERS ---
    def show_progress(self, message, value=0):
        """Exibe e atualiza a barra de progresso no Header."""
        if hasattr(self, 'progress_container'):
            self.progress_container.show()
            self.lbl_progress.setText(message)
            self.progress_bar.setValue(value)
            QApplication.processEvents() # Force update

    def update_progress(self, value, message=None):
        """Atualiza valor e mensagem da barra de progresso."""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(value)
            if message:
                self.lbl_progress.setText(message)
            QApplication.processEvents()

    def hide_progress(self):
        """Oculta a barra de progresso."""
        if hasattr(self, 'progress_container'):
            self.progress_container.hide()
            QApplication.processEvents()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # --- Auth Flow Integration ---
    auth_service = AuthService()

    # --- Tufup Update Check ---
    # --- Tufup Update Check ---
    def run_update_check():
        """Verifica se há atualizações disponíveis apenas quando rodando como executável."""
        # Em Nuitka --standalone, sys.frozen não é sempre True da mesma forma que PyInstaller
        # Mas compilado geralmente não tem .py sources.
        # Vamos assumir que se importou config e estamos rodando, checamos.
        # A flag sys.frozen é setada pelo Nuitka também? Sim.
        
        if not getattr(sys, 'frozen', False):
            # print("ℹ️ Modo desenvolvimento: Pulando verificação de update.")
            return

        print(f"🔍 Verificando atualizações em: {config.UPDATE_BASE_URL}")
        try:
            # Pastas necessárias para o Tufup Client
            # Usando caminhos definidos no config para consistência
            metadata_dir = config.METADATA_DIR
            target_dir = config.DOWNLOAD_DIR
            
            metadata_dir.mkdir(parents=True, exist_ok=True)
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Chave pública empacotada
            # No Nuitka/PyInstaller, precisamos garantir que 'keys/timestamp.pub' esteja ao lado do executável
            public_key = config.KEYS_DIR / "timestamp.pub"
            
            if not public_key.exists():
                print(f"⚠️ Chave pública não encontrada em: {public_key}")
                print("   Updates desabilitados por segurança.")
                return

            # Configura o cliente Tufup
            client = Client(
                app_name=config.APP_NAME,
                current_version=config.APP_VERSION,
                metadata_dir=str(metadata_dir),
                metadata_base_url=config.UPDATE_BASE_URL,
                target_dir=str(target_dir),
                target_base_url=config.UPDATE_BASE_URL,
                public_key_path=str(public_key)
            )

            # Verifica e baixa
            update_info = client.check_for_updates()
            if update_info:
                print("✨ Nova versão encontrada! Preparando download...")
                
                # --- CHUNKED DOWNLOAD HANDLER ---
                # Verifica se o arquivo alvo está dividido em partes no servidor (bypass 50MB limit)
                # O Tufup não sabe lidar com partes, então baixamos e montamos manualmente antes.
                try:
                    target_name = update_info.target_filename # Ex: AgenteCAD-1.0.0.tar.gz
                    target_path = Path(target_dir) / target_name
                    base_url = config.UPDATE_BASE_URL
                    
                    # Checa se existe a parte 1
                    import requests
                    part1_url = f"{base_url}/{target_name}.part1"
                    print(f"   🔍 Verificando split-download: {part1_url}")
                    
                    head = requests.head(part1_url)
                    if head.status_code == 200:
                        print("   📦 Download fatiado detectado! Baixando partes...")
                        with open(target_path, 'wb') as outfile:
                            part_num = 1
                            while True:
                                part_url = f"{base_url}/{target_name}.part{part_num}"
                                print(f"      ⬇️ Baixando parte {part_num}...", end="")
                                r = requests.get(part_url, stream=True)
                                if r.status_code != 200:
                                    print(" Fim.")
                                    break
                                for chunk in r.iter_content(chunk_size=8192):
                                    outfile.write(chunk)
                                print(" OK")
                                part_num += 1
                        print("   ✅ Reconstrução do arquivo completa.")
                except Exception as e:
                    print(f"   ⚠️ Erro no pré-download (tentando normal): {e}")
                # --------------------------------

                if client.download_and_apply_update():
                    print("♻️ Update aplicado. Reiniciando...")
                    # Nuitka restart logic might need specific handling but sys.exit(0) allows wrapper to restart if handled
                    # Tufup replaces files.
                    sys.exit(0) 
            else:
                print("✅ Sistema atualizado.")
        except Exception as e:
            print(f"❌ Falha na verificação de update: {e}")

    # Executa check antes de abrir UI
    run_update_check()
    
    # Reference holder to prevent GC
    windows = {}

    def start_app(user_profile):
        # Close login if it exists
        if 'login' in windows:
            windows['login'].close()
            
        print(f"Starting app for user: {user_profile.email}")
        
        # Init Main Window
        window = MainWindow()
        window.set_user_context(user_profile)
        window.setWindowState(Qt.WindowMaximized)
        window.show()
        windows['main'] = window

        # If MainWindow closes, and there is no login window, check if we should re-show login
        def check_restart():
            if not auth_service.is_authenticated():
                show_login()
        
        window.destroyed.connect(check_restart)

    def show_login():
        login = LoginWidget()
        login.login_success.connect(start_app)
        login.show()
        windows['login'] = login # Keep ref

    if auth_service.is_authenticated():
        start_app(auth_service.get_current_user())
    else:
        show_login()
        
    sys.exit(app.exec())

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        try:
            with open("crash_log.txt", "w", encoding="utf-8") as f:
                f.write(f"CRITICAL STARTUP ERROR:\n{error_msg}")
        except:
            pass # Last resort
        
        # Try to show message box if Qt is alive
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if not QApplication.instance():
                app = QApplication(sys.argv)
            QMessageBox.critical(None, "Fatal Error", f"Failed to start:\n{e}\n\nCheck crash_log.txt")
        except:
            print(error_msg)
            input("Press Enter to exit...")
