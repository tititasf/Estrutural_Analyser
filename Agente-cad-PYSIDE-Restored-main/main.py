import numpy as np # Force early initialization for Nuitka standalone
import sys
import os

# ── Diagnóstico de crashes nativos (faulthandler) ─────────────────────────────
import faulthandler
_fault_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', 'fault_native.log')
try:
    _fault_log_file = open(_fault_log_path, 'w', encoding='utf-8', buffering=1)
    faulthandler.enable(file=_fault_log_file, all_threads=True)
except Exception:
    faulthandler.enable(file=sys.stderr, all_threads=True)

import atexit
import signal

def _crash_handler(sig, frame):
    import traceback
    print(f"\n[CRASH-HANDLER] Sinal recebido: {sig}", flush=True)
    traceback.print_stack(frame)
    sys.stdout.flush()
    sys.stderr.flush()

if hasattr(signal, 'SIGABRT'):
    signal.signal(signal.SIGABRT, _crash_handler)
# ─────────────────────────────────────────────────────────────────────────────

# Configurar encoding UTF-8 para terminal (resolve problemas no Cursor)
if sys.platform == 'win32':
    import io
    # Forçar stdout/stderr para UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    # Configurar variável de ambiente
    os.environ['PYTHONIOENCODING'] = 'utf-8'
# Adicionar caminho do Robo Laterais
robo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ROBOS_ABAS", "Robo_Laterais_de_Vigas")
if robo_path not in sys.path:
    sys.path.append(robo_path)

# Tentar importar o robo
try:
    from robo_laterais_viga_pyside import VigaMainWindow  # type: ignore
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
from src.core.item_attention_store import has_attention, load_attention, save_attention

# Tentar importar o robo Lajes (laje_src)
try:
    from laje_src.ui.main_window import MainWindow as LajeMainWindow  # type: ignore
except ImportError as e:
    print(f"Erro ao importar Robo Lajes: {e}")
    LajeMainWindow = None

# Adicionar caminho do Robo Fundos
robo_fundos_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao")
if robo_fundos_path not in sys.path:
    sys.path.append(robo_fundos_path)

# Tentar importar o robo Fundos
try:
    from fundo_pyside import FundoMainWindow  # type: ignore
except ImportError as e:
    print(f"Erro ao importar Robo Fundos: {e}")
    FundoMainWindow = None


from typing import Dict, List, Any, Optional, TYPE_CHECKING
import os
import json
import logging
import sqlite3

if TYPE_CHECKING:
    # Stub para DXFPreprocessor - classe será implementada futuramente
    class DXFPreprocessor:
        def __init__(self, spatial_index: Any, memory: Any) -> None:
            ...
        def run_marco_analysis(self, dxf_data: Any, project_id: str) -> Dict[str, Any]:
            ...
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QFileDialog, QDockWidget, 
                               QTextEdit, QLabel, QStackedWidget, QListWidget,
                               QListWidgetItem, QTabWidget, QSplitter, QLineEdit, QProgressBar,
                               QTreeWidget, QTreeWidgetItem, QMessageBox, QMenu, QScrollArea, QFrame,
                               QComboBox, QTabBar, QRadioButton, QButtonGroup, QSizePolicy)
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
from src.ui.modules.diagnostic_hub import DiagnosticHubModule
from src.ui.modules.diagnostic_reverse_hub import DiagnosticReverseHub
from src.ui.modules.comparison_engine import ComparisonEngineModule
from src.core.services.data_coordinator import get_coordinator
from src.ui.theme import Colors, Fonts



# Adicionar caminho do Robo Pilares (NOVO) - MOVED down to avoid shadowing 'src'
robo_pilares_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25")
if robo_pilares_path not in sys.path:
    sys.path.append(robo_pilares_path)

# Adicionar também o diretório src para imports diretos (models, services, etc.)
robo_pilares_src_path = os.path.join(robo_pilares_path, "src")
if robo_pilares_src_path not in sys.path:
    sys.path.append(robo_pilares_src_path)

try:
    from bootstrap import create_pilares_widget  # type: ignore
except ImportError as e:
    print(f"Erro ao importar Robo Pilares: {e}")
    create_pilares_widget = None

# Config logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import uuid
import re
from src import config

class LicensingProxy:
    """Proxy para integrar o sistema de licenças central aos robôs legados."""
    def __init__(self, main_window):
        self.main_window = main_window
    
    @property
    def user_data(self):
        user = getattr(self.main_window, 'user_profile', None)
        if not user: return None
        return {
            'nome': user.full_name or user.email,
            'creditos': getattr(user, 'credits', 0.0)
        }
        
    def consume_credits(self, amount):
        # Libera por enquanto conforme solicitado ("libera por enquanto")
        print(f"[LicensingProxy] Consumo de {amount:.2f} m² solicitado. Autorizando gratuitamente.")
        return True, "Liberado (Modo Temporário)"

    # Interface para o Robo Fundos (credit_manager)
    def calcular_area_total(self, dados_fundo):
        try:
            largura = float(str(dados_fundo.get('largura', 0)).replace(',', '.'))
            comprimento = float(str(dados_fundo.get('comprimento', 0)).replace(',', '.'))
            return (largura * comprimento) / 10000.0
        except: return 0.0

    def consultar_saldo(self, force_refresh=False):
        data = self.user_data
        if not data: return False, 0.0
        return True, data['creditos']

    def debitar_multiplos_fundos(self, fundos_lista):
        # Libera por enquanto
        return True, "Débito Liberado (Temporário)"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vision-Estrutural AI - Pro Dashboard")
        self.resize(1600, 1000)
        
        # Estado
        # Garantir que o banco seja criado no diretório do main.py
        main_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_dir = main_dir
        # DB real fica um nível acima (D:/Agente-cad-PYSIDE/project_data.vision)
        parent_db = os.path.join(os.path.dirname(main_dir), "project_data.vision")
        local_db  = os.path.join(main_dir, "project_data.vision")
        db_path = parent_db if os.path.exists(parent_db) and os.path.getsize(parent_db) > 200_000 else local_db
        self.db = DatabaseManager(db_path=db_path) # SQLite persistencia
        self.memory = HierarchicalMemory(self.db)
        self.auth_service = AuthService() # Initialize AuthService
        self.spatial_index = SpatialIndex()

        # Engines
        self.context_engine = None
        self.pillar_analyzer = None

        self.dxf_data = None
        self.pillars_found = []
        self.slabs_found = []
        self.beams_found = []
        self.beams_database = [] # Armazena dados de visualização das vigas por pilar
        
        # Cache de Widgets de Item da Árvore para atualização O(1)
        self.tree_item_map = {} # {item_id: [QTreeWidgetItem, ...]}
        
        self.current_project_id = None
        self.current_project_name = "Sem Projeto"
        self.current_dxf_path = None

        # Perfil do Usuário
        self.user_profile = None
        self.licensing_proxy = LicensingProxy(self)

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
                    qss_content = f.read()
                    print(f"[QSS DEBUG] Loaded {len(qss_content)} bytes from {style_path}")
                    try:
                        self.setStyleSheet(qss_content)
                        print("[QSS DEBUG] Global stylesheet applied successfully")
                    except Exception as parse_err:
                        print(f"[QSS DEBUG] ERROR: {parse_err}")
                        import traceback
                        traceback.print_exc()
            else:
                print(f"[MainWindow] Aviso: Arquivo de estilo não encontrado em {style_path}")
        except Exception as e:
            print(f"Erro ao carregar CSS: {e}")

    # --- UI OVERHAUL METHODS ---
    def _setup_top_bar(self):
        """Configura a barra superior (Logotipo, Projeto, Obra/Pavimento)."""
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_bar.setFixedHeight(38)
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(10, 0, 20, 0)
        layout.setSpacing(10)

        # 0. Logo & Perfil (Esquerda/Direita)
        self.user_hbox = QHBoxLayout()
        self.user_hbox.setSpacing(10)

        # 1. Logo
        lbl_logo = QLabel("TSF PROJETOS")
        lbl_logo.setObjectName("LogoLabel")
        layout.addWidget(lbl_logo)

        # Separator  (botão Gerenciar Projetos removido — agora é Tab 0)
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("border: 1px solid #444;")
        layout.addWidget(line)

        # 3. Combo Obras — oculto no topo, controlado pelo SA sidebar
        self.cmb_works = QComboBox()
        self.cmb_works.setPlaceholderText("Selecione a Obra...")
        self.cmb_works.setFixedWidth(200)
        self.cmb_works.currentIndexChanged.connect(self._on_work_changed)
        self.cmb_works.setVisible(False)

        # Botão de refresh (mantido oculto — SA sidebar tem sua própria lógica)
        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedSize(30, 25)
        btn_refresh.clicked.connect(self._refresh_nav_combos)
        btn_refresh.setVisible(False)

        # 4. Combo Pavimentos — oculto no topo
        self.cmb_pavements = QComboBox()
        self.cmb_pavements.setPlaceholderText("Selecione o Pavimento...")
        self.cmb_pavements.setFixedWidth(200)
        self.cmb_pavements.currentIndexChanged.connect(self._on_pavement_changed)
        self.cmb_pavements.setVisible(False)

        # 5. Níveis — ocultos no topo, controlados pelo SA sidebar
        self.edit_level_arr = QLineEdit()
        self.edit_level_arr.setFixedWidth(60)
        self.edit_level_arr.setPlaceholderText("0.00")
        self.edit_level_arr.editingFinished.connect(self.save_project_metadata)
        self.edit_level_arr.setVisible(False)

        self.edit_level_exit = QLineEdit()
        self.edit_level_exit.setFixedWidth(60)
        self.edit_level_exit.setPlaceholderText("3.00")
        self.edit_level_exit.editingFinished.connect(self.save_project_metadata)
        self.edit_level_exit.setVisible(False)

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
        """Navega para a tab 0 (Gerenciar Projetos — agora embutida na interface)."""
        self.switch_to_tab(0)
        
    def on_global_obra_created(self, work_name):
        self.log(f"🏠 Sincronizando Obra Global: {work_name}")
        self._refresh_nav_combos()

    def switch_to_tab(self, index):
        """Alterna para a aba solicitada.
        Índices (com Gerenciar Projetos como tab 0):
          0=Gerenciar Projetos, 1=Diagnostic Hub, 2=Diagnostic Reverse Hub,
          3=Structural Analyzer, 4=Comparison Engine, 5=Robo Pilares,
          6=Robo LV, 7=Robo FV, 8=Robo Laje
        """
        if hasattr(self, 'module_tabs') and index < self.module_tabs.count():
            self.module_tabs.setCurrentIndex(index)
            self.raise_()
            self.activateWindow()
        # Sincronização centralizada - usar obra atual se disponível
        if hasattr(self, 'current_work_name') and self.current_work_name:
            self.sync_robots_with_master_context(self.current_work_name)

    def _on_module_tab_changed(self, index: int):
        """Atualiza a faixa de descrição de fase quando a aba muda."""
        if hasattr(self, '_fase_desc_label') and hasattr(self, '_FASE_DESCS'):
            self._fase_desc_label.setText(self._FASE_DESCS.get(index, ""))
        
    def on_global_project_created(self, work_name, project_name, project_id=None):
        self.log(f"🏗️ Sincronizando Projeto/Pavimento Global: {project_name} em {work_name} (ID: {project_id})")
        self._refresh_nav_combos()
        # Sincronização centralizada
        self.sync_robots_with_master_context(work_name, project_name, project_id)

    def sync_robots_with_master_context(self, work_name, pavement_name=None, project_id=None):
        """Propaga o contexto de Obra e Pavimento para todos os robôs integrados."""
        if project_id is None:
             project_id = self.current_project_id

        # Evita cascata de LOAD/SAVE quando o contexto já é o mesmo
        _ctx = (work_name, pavement_name, str(project_id or ''))
        if getattr(self, '_last_robot_sync_ctx', None) == _ctx:
            return
        self._last_robot_sync_ctx = _ctx

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

        # Sync Legacy Data first
        # DESABILITADO: Sincronização reversa (Robô -> Banco)
        # O "gerenciar projetos" é a hierarquia máxima e popula os robôs.
        # Quando criar passo de reversão, reativar aqui.
        # self._sync_legacy_works()

        current_work = self.cmb_works.currentText()
        self.cmb_works.blockSignals(True)
        self.cmb_works.clear()
        
        try:
            works = self.db.get_all_works()
            self.cmb_works.addItems(works)
            # Só loga se houver obras ou mudou (evita spam de "0 obras" no startup)
            if works:
                self.log(f"📋 {len(works)} obra(s) no banco: {', '.join(works[:5])}{'...' if len(works)>5 else ''}")
            # Sincronizar combo do Diagnostic Reverse Hub
            if hasattr(self, 'diagnostic_reverse_module'):
                self.diagnostic_reverse_module.refresh_obras(works)
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

        # Preencher combos de TODOS os robôs — só na primeira chamada para evitar spam de DB
        if not getattr(self, '_robos_initial_sync_done', False):
            try:
                self._sync_robos_obras_e_pavimentos(global_work_name=self.cmb_works.currentText() or None)
                self._robos_initial_sync_done = True
            except Exception as _e:
                self.log(f"[sync_robos] erro: {_e}")

    def _debug_works_pavements_documents(self, works: list):
        """Depura todas as obras, seus pavimentos e documentos."""
        print("\n" + "="*80)
        print("🔍 DEBUG: DEPURAÇÃO DE OBRAS, PAVIMENTOS E DOCUMENTOS")
        print("="*80)
        
        # DEBUG: Verificar TODOS os documentos na tabela (independente de vínculo)
        print("\n📋 VERIFICAÇÃO COMPLETA DA TABELA project_documents:")
        print("-" * 80)
        conn = self.db._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            # Verificar estrutura da tabela
            cursor = conn.execute("PRAGMA table_info(project_documents)")
            columns = cursor.fetchall()
            print("  Estrutura da tabela:")
            for col in columns:
                print(f"    - {col[1]} ({col[2]})")
            
            # Buscar TODOS os documentos
            cursor = conn.execute("SELECT * FROM project_documents")
            all_docs = cursor.fetchall()
            print(f"\n  📊 Total de documentos na tabela: {len(all_docs)}")
            
            if all_docs:
                print("  📄 Documentos encontrados:")
                for doc in all_docs:
                    doc_dict = dict(doc)
                    doc_id = doc_dict.get('id', 'N/A')
                    doc_name = doc_dict.get('name', 'Sem nome')
                    project_id = doc_dict.get('project_id') or 'NULL'
                    work_name = doc_dict.get('work_name') or 'NULL'
                    file_path = doc_dict.get('file_path') or 'NULL'
                    print(f"    - {doc_name}")
                    print(f"      ID: {doc_id}")
                    print(f"      project_id: {project_id}")
                    print(f"      work_name: {work_name}")
                    if file_path and file_path != 'NULL':
                        print(f"      file_path: {file_path}")
                        
                # Verificar especificamente o projeto P-1
                p1_id = "43b93bed-8af8-473f-9d27-0d99b4d0764a"
                print(f"\n  🔍 Buscando documentos para P-1 (ID: {p1_id}):")
                cursor = conn.execute("SELECT * FROM project_documents WHERE project_id = ?", (p1_id,))
                p1_docs = cursor.fetchall()
                print(f"    Encontrados: {len(p1_docs)}")
                if p1_docs:
                    for doc in p1_docs:
                        doc_dict = dict(doc)
                        print(f"      - {doc_dict.get('name', 'Sem nome')} (ID: {doc_dict.get('id', 'N/A')})")
                else:
                    print("    ⚠️ Nenhum documento encontrado com project_id = P-1")
                    
                # Verificar documentos com work_name = OBRA-TESTE1
                print(f"\n  🔍 Buscando documentos para OBRA-TESTE1 (work_name):")
                cursor = conn.execute("SELECT * FROM project_documents WHERE work_name = ?", ('OBRA-TESTE1',))
                obra_docs = cursor.fetchall()
                print(f"    Encontrados: {len(obra_docs)}")
                if obra_docs:
                    for doc in obra_docs:
                        doc_dict = dict(doc)
                        print(f"      - {doc_dict.get('name', 'Sem nome')} (ID: {doc_dict.get('id', 'N/A')}, project_id: {doc_dict.get('project_id', 'NULL')})")
                else:
                    print("    ⚠️ Nenhum documento encontrado com work_name = OBRA-TESTE1")
                    
                # Verificar documentos sem project_id mas com work_name
                print(f"\n  🔍 Buscando documentos sem project_id mas com work_name:")
                cursor = conn.execute("SELECT * FROM project_documents WHERE (project_id IS NULL OR project_id = '') AND work_name IS NOT NULL AND work_name != ''")
                orphan_docs = cursor.fetchall()
                print(f"    Encontrados: {len(orphan_docs)}")
                if orphan_docs:
                    for doc in orphan_docs:
                        doc_dict = dict(doc)
                        print(f"      - {doc_dict.get('name', 'Sem nome')} (work_name: {doc_dict.get('work_name', 'NULL')}, project_id: {doc_dict.get('project_id', 'NULL')})")
            else:
                print("  ⚠️ NENHUM documento encontrado na tabela!")
        except Exception as e:
            print(f"  ❌ Erro ao verificar documentos: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()
        
        all_projects = self.db.get_projects()
        
        for work_name in works:
            print(f"\n📁 OBRA: {work_name}")
            print("-" * 80)
            
            # Documentos da obra
            work_docs = self.db.get_work_documents(work_name)
            print(f"  📄 Documentos da Obra: {len(work_docs) if work_docs else 0}")
            if work_docs:
                for doc in work_docs:
                    print(f"    - {doc.get('name', 'Sem nome')} (ID: {doc.get('id', 'N/A')})")
                    if doc.get('file_path'):
                        print(f"      Caminho: {doc.get('file_path')}")
            else:
                print("    ⚠️ Nenhum documento encontrado")
            
            # Pavimentos da obra
            obra_projects = [p for p in all_projects if p.get('work_name') == work_name]
            print(f"  🏗️ Pavimentos: {len(obra_projects)}")
            
            if obra_projects:
                for proj in obra_projects:
                    pav_name = proj.get('pavement_name') or proj.get('name', 'Sem nome')
                    project_id = proj.get('id', 'N/A')
                    print(f"\n    🏢 PAVIMENTO: {pav_name} (ID: {project_id})")
                    
                    # Documentos do pavimento
                    proj_docs = self.db.get_project_documents(project_id)
                    print(f"      📄 Documentos: {len(proj_docs) if proj_docs else 0}")
                    if proj_docs:
                        for doc in proj_docs:
                            print(f"        - {doc.get('name', 'Sem nome')} (ID: {doc.get('id', 'N/A')})")
                            if doc.get('file_path'):
                                print(f"          Caminho: {doc.get('file_path')}")
                    else:
                        print("        ⚠️ Nenhum documento encontrado")
                    
                    # Dados do projeto
                    if hasattr(self.db, 'load_pillars'):
                        try:
                            pilares = self.db.load_pillars(project_id)
                            vigas = self.db.load_beams(project_id) if hasattr(self.db, 'load_beams') else []
                            lajes = self.db.load_slabs(project_id) if hasattr(self.db, 'load_slabs') else []
                            print(f"      📊 Dados: {len(pilares) if pilares else 0}P, {len(vigas) if vigas else 0}V, {len(lajes) if lajes else 0}L")
                        except Exception as e:
                            print(f"      ⚠️ Erro ao carregar dados: {e}")
            else:
                print("    ⚠️ Nenhum pavimento encontrado")
        
        print("\n" + "="*80)
        print("✅ FIM DA DEPURAÇÃO")
        print("="*80 + "\n")

    def _sync_legacy_works(self):
        """Sincroniza obras legadas carregadas pelo Robo Pilares para o DB principal."""
        if not hasattr(self, 'robo_pilares') or not self.robo_pilares:
            self.log("⚠️ Robo Pilares não disponível para sincronização")
            return

        try:
            # Acessar VM do Robo Pilares
            if hasattr(self.robo_pilares, 'vm'):
                # Obras legadas carregadas (Lista de ObraModel)
                legacy_obras = getattr(self.robo_pilares.vm, 'obras_collection', [])
                self.log(f"🔍 Encontradas {len(legacy_obras)} obras legadas no Robo Pilares")
                if not legacy_obras:
                    self.log("⚠️ Nenhuma obra legada encontrada")
                    return
                
                # Cache do estado atual do DB
                db_works = set(self.db.get_all_works())
                all_projects = self.db.get_projects()
                # Lookup: (work_name, pavement_name) -> project_id
                existing_projs = {}
                for p in all_projects:
                    wn = p.get('work_name')
                    pn = p.get('pavement_name') or p.get('name')
                    existing_projs[(wn, pn)] = p['id']

                changes_made = False

                for obra in legacy_obras:
                    # 1. Obra
                    if obra.nome not in db_works:
                        self.log(f"📦 Importando Obra Legada: {obra.nome}")
                        self.db.create_work(obra.nome)
                        changes_made = True

                    # 2. Pavimentos (Projetos)
                    if hasattr(obra, 'pavimentos'):
                        for pav in obra.pavimentos:
                            key = (obra.nome, pav.nome)
                            if key not in existing_projs:
                                # print(f"[SYNC] Criando Projeto Legado: {pav.nome} em {obra.nome}")
                                new_id = self.db.create_project(
                                    name=pav.nome,
                                    dxf_path="", # Não temos path no legado fácil?
                                    author_name="Legacy Sync"
                                )
                                if new_id:
                                    self.db.update_project_metadata(new_id, {
                                        'work_name': obra.nome,
                                        'pavement_name': pav.nome
                                    })
                                    changes_made = True
                
                if changes_made:
                    self.log(f"✅ Sincronização de obras legadas concluída")
                else:
                    self.log(f"ℹ️ Nenhuma nova obra para sincronizar")

        except Exception as e:
            print(f"[SYNC ERROR] Falha ao sincronizar legado: {e}")

    def _on_open_reverse_hub(self, obra_name: str, file_path: str):
        """Navega para o Diagnostic Reverse Hub, define a obra e seleciona o item."""
        if hasattr(self, 'diagnostic_reverse_module'):
            hub = self.diagnostic_reverse_module
            hub.set_obra(obra_name)
            # Seleciona o item específico na lista esquerda após a lista recarregar
            from PySide6.QtCore import QTimer
            QTimer.singleShot(80, lambda: hub._left.select_item_by_path(file_path))

    def _on_ce_obra_pav_changed(self, obra: str, pav: str):
        """CE-005: CE mudou obra/pav → sincroniza top bar sem loop."""
        if self.cmb_works.currentText() != obra:
            self.cmb_works.blockSignals(True)
            idx = self.cmb_works.findText(obra)
            if idx >= 0:
                self.cmb_works.setCurrentIndex(idx)
            self.cmb_works.blockSignals(False)
        # PM-009: propagar para Gerenciar Projetos se aberto
        self._sync_project_manager_obra(obra)

    def _sync_project_manager_obra(self, obra: str):
        """PM-009: Sincroniza a lista de obras no Gerenciar Projetos com a obra ativa."""
        pm = getattr(self, 'project_manager', None)
        if pm is None:
            return
        try:
            lw = pm.list_works
            for i in range(lw.count()):
                item = lw.item(i)
                if item and item.data(Qt.UserRole) == obra:
                    lw.blockSignals(True)
                    lw.setCurrentItem(item)
                    lw.blockSignals(False)
                    pm.load_projects()
                    break
        except Exception:
            pass

    def _on_work_changed(self):
        """Filtra os pavimentos baseados na Obra selecionada."""
        work_name = self.cmb_works.currentText()
        print(f"[WORK_CHANGED] work_name='{work_name}'", flush=True)
        self.cmb_pavements.blockSignals(True)
        self.cmb_pavements.clear()

        if not work_name:
            self.cmb_pavements.blockSignals(False)
            return

        # Notificar Coordenador Central
        get_coordinator().set_work(work_name)

        # Busca todos os projetos e filtra por 'work_name'
        all_projects = self.db.get_projects()

        # Filtra projetos que pertencem a esta Obra
        filtered = [p for p in all_projects if p.get('work_name') == work_name]

        for p in filtered:
            raw_name = p.get('pavement_name') or p.get('name')
            fmt = getattr(self, '_pav_card_label', lambda n: n)(raw_name)
            self.cmb_pavements.addItem(fmt, (p['id'], raw_name))

        self.cmb_pavements.blockSignals(False)
        self.sync_robots_with_master_context(work_name)

        # CE-005/PM-009: propagar para CE, Reverse Hub e Gerenciar Projetos
        if hasattr(self, 'comparison_module'):
            self.comparison_module.fase8_panel.set_obra(work_name)
        if hasattr(self, 'diagnostic_reverse_module'):
            self.diagnostic_reverse_module.set_obra(work_name)
        self._sync_project_manager_obra(work_name)

        # Reverse sync: SA sidebar combo de obras
        if hasattr(self, 'sa_cmb_obras'):
            sa_idx = self.sa_cmb_obras.findText(work_name)
            if sa_idx >= 0:
                self.sa_cmb_obras.blockSignals(True)
                self.sa_cmb_obras.setCurrentIndex(sa_idx)
                self.sa_cmb_obras.blockSignals(False)
            # Sempre repopula os pavimentos do SA ao mudar obra (sinal foi bloqueado)
            if hasattr(self, '_sa_populate_pavimentos'):
                self._sa_populate_pavimentos(work_name)

        # Auto-selecionar primeiro pavimento (blockSignals impediu que currentIndexChanged fosse emitido)
        if self.cmb_pavements.count() > 0:
            self._on_pavement_changed()

    def _sync_robos_obras_e_pavimentos(self, global_work_name=None):
        """
        Sincronização central e robusta de TODOS os robôs com o banco de dados.
        Preenche as obras (baseado em db.get_all_works) e os pavimentos (db.get_projects).
        Se global_work_name for passado, força a seleção desta obra nos robôs.
        """
        try:
            works = self.db.get_all_works()
            all_projects = self.db.get_projects()
            
            def get_pavs(work_name):
                filtered = [p for p in all_projects if p.get('work_name') == work_name]
                raw_pavs = sorted(list(set([p.get('pavement_name') or p.get('name') for p in filtered if (p.get('pavement_name') or p.get('name'))])))
                return raw_pavs

            # ----- Laje -----
            if getattr(self, 'robo_laje', None) and hasattr(self.robo_laje, 'obra_control'):
                try:
                    c = self.robo_laje.obra_control.obra_combo
                    c.blockSignals(True)
                    curr_nome = global_work_name if global_work_name else (c.currentData().nome if c.currentData() and hasattr(c.currentData(), 'nome') else c.currentText())
                    c.clear()
                    from laje_src.models.obra import Obra as LajeObra
                    from laje_src.models.pavimento import Pavimento as LajePavimento
                    for w in works:
                        obra_mock = LajeObra(nome=w)
                        for p in get_pavs(w):
                            obra_mock.pavimentos.append(LajePavimento(nome=p))
                        c.addItem(f"📁 {w}", obra_mock)
                    
                    found = False
                    for i in range(c.count()):
                        dt = c.itemData(i)
                        if dt and getattr(dt, 'nome', '') == curr_nome:
                            c.setCurrentIndex(i)
                            found = True
                            break
                    if not found: c.setCurrentIndex(0 if c.count() > 0 else -1)
                    c.blockSignals(False)
                    
                    if global_work_name and found:
                        if hasattr(self.robo_laje.obra_control, 'obra_changed'):
                            self.robo_laje.obra_control.obra_changed.emit(c.currentData())
                except Exception as e:
                    self.log(f"Erro Laje: {e}")

            # ----- Pilares -----
            # Usa add_global_obra (API pública: vm.sync_global_context) para cada obra,
            # depois chama populate_filters no SidebarWidget para atualizar o combo_obra.
            if getattr(self, 'robo_pilares', None) and hasattr(self.robo_pilares, 'add_global_obra'):
                try:
                    for w in works:
                        self.robo_pilares.add_global_obra(w)

                    # Atualizar combo_obra da UI via SidebarWidget.populate_filters
                    from PySide6.QtWidgets import QWidget as _QW2
                    for _sw in self.robo_pilares.findChildren(_QW2):
                        if hasattr(_sw, 'populate_filters') and callable(_sw.populate_filters):
                            _sw.populate_filters()
                            # Se há obra alvo, selecionar
                            if global_work_name and hasattr(_sw, 'combo_obra'):
                                _cmb = _sw.combo_obra
                                for _i in range(_cmb.count()):
                                    _d = _cmb.itemData(_i)
                                    if _d and getattr(_d, 'nome', '') == global_work_name:
                                        _cmb.setCurrentIndex(_i)
                                        break
                            break
                except Exception as e:
                    self.log(f"Erro Pilares: {e}")

            # ----- Viga Lateral (LV) — usa project_data interno -----
            if getattr(self, 'robo_viga', None) and hasattr(self.robo_viga, 'project_data'):
                try:
                    for w in works:
                        if w not in self.robo_viga.project_data:
                            self.robo_viga.project_data[w] = {}
                        for p in get_pavs(w):
                            if p not in self.robo_viga.project_data[w]:
                                self.robo_viga.project_data[w][p] = {
                                    'vigas': {},
                                    'metadata': {'in': '', 'out': '', 'segment_classes': ['Lista Geral']}
                                }
                    self.robo_viga.update_obra_combo()   # reconstrói cmb_obra a partir de project_data
                    if global_work_name:
                        # garante seleção da obra e carrega pav
                        self.robo_viga.add_global_obra(global_work_name)
                except Exception as e:
                    self.log(f"Erro Viga: {e}")

            # ----- Fundo de Viga (FV) — usa obras_metadata interno -----
            if getattr(self, 'robo_fundo', None) and hasattr(self.robo_fundo, 'obras_metadata'):
                try:
                    for w in works:
                        if w not in self.robo_fundo.obras_metadata:
                            self.robo_fundo.obras_metadata[w] = set()
                        for p in get_pavs(w):
                            self.robo_fundo.obras_metadata[w].add(p)
                    curr = self.robo_fundo.combo_obra.currentText()
                    self.robo_fundo.combo_obra.blockSignals(True)
                    self.robo_fundo.combo_obra.clear()
                    self.robo_fundo.combo_obra.addItems(sorted(works))
                    target = global_work_name or curr
                    idx = self.robo_fundo.combo_obra.findText(target)
                    self.robo_fundo.combo_obra.setCurrentIndex(idx if idx >= 0 else 0)
                    self.robo_fundo.combo_obra.blockSignals(False)
                    self.robo_fundo._update_combo_pavimentos()
                except Exception as e:
                    self.log(f"Erro Fundo: {e}")

        except Exception as e:
            self.log(f"Erro geral _sync_robos_obras_e_pavimentos: {e}")


    def _current_pavement_name(self) -> str:
        """Retorna o nome raw do pavimento selecionado no cmb_pavements."""
        d = self.cmb_pavements.currentData()
        return d[1] if isinstance(d, tuple) and len(d) > 1 else self.cmb_pavements.currentText()

    def _on_pavement_changed(self):
        """Carrega o projeto selecionado (ABRE EM ABA)."""
        idx = self.cmb_pavements.currentIndex()
        print(f"[PAV_CHANGED] idx={idx} text='{self.cmb_pavements.currentText()}'", flush=True)
        if idx < 0: return
        
        _pav_data = self.cmb_pavements.itemData(idx)
        project_id = _pav_data[0] if isinstance(_pav_data, tuple) else _pav_data
        project_name = _pav_data[1] if isinstance(_pav_data, tuple) else self.cmb_pavements.currentText()

        # Reverse sync: SA sidebar combo de pavimentos (busca por raw_name no userData)
        if hasattr(self, 'sa_cmb_pavimentos'):
            sa_pav_idx = -1
            for _i in range(self.sa_cmb_pavimentos.count()):
                _d = self.sa_cmb_pavimentos.itemData(_i)
                if _d and _d[1] == project_name:
                    sa_pav_idx = _i
                    break
            if sa_pav_idx >= 0 and self.sa_cmb_pavimentos.currentIndex() != sa_pav_idx:
                self.sa_cmb_pavimentos.blockSignals(True)
                self.sa_cmb_pavimentos.setCurrentIndex(sa_pav_idx)
                self.sa_cmb_pavimentos.blockSignals(False)

        # Notificar Coordenador Central
        get_coordinator().set_pavement(project_id, project_name)
        
        # Sincronizar robôs
        work_name = self.cmb_works.currentText()
        self.sync_robots_with_master_context(work_name, project_name, project_id)
        
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

    @staticmethod
    def _tab_label_for(project_name: str) -> str:
        """Formata o nome da aba com prefixo de nível numérico."""
        import re as _re
        m = _re.search(r'[-_](\d{3,5})[-_]', project_name)
        prefix = f"[{m.group(1)}] " if m else ""
        return f"{prefix}{project_name}"

    def _open_project_tab(self, project_id, project_name):
        """Abre uma nova aba de projeto ou foca na existente."""
        tab_label = self._tab_label_for(project_name)
        # Check if already open
        count = self.project_tabs.count()
        for i in range(count):
            pid = self.project_tabs.tabToolTip(i)
            if pid == project_id:
                self.project_tabs.setCurrentIndex(i)
                self._load_project_into_view(project_id)
                return

        # Create new tab
        self.project_tabs.blockSignals(True)
        try:
            page = QWidget()
            idx = self.project_tabs.addTab(page, tab_label)
            pid_str = str(project_id)
            self.project_tabs.setTabToolTip(idx, pid_str)
            self.project_tabs.setCurrentIndex(idx)
            self.project_tabs.show()   # exibe o painel de abas agora que tem conteúdo
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

    def _on_project_tab_close_and_hide(self, index):
        """Fecha aba e esconde o painel quando não resta nenhuma aba aberta."""
        self._on_project_tab_close(index)
        if self.project_tabs.count() == 0:
            self.project_tabs.hide()

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
            self._show_lists_empty_state()
            return

    def _show_lists_empty_state(self, message: str = "Nenhum projeto aberto"):
        """Limpa as listas de análise e exibe placeholder de estado vazio."""
        for tree in (self.list_pillars, self.list_beams, self.list_slabs):
            tree.clear()
            placeholder = QTreeWidgetItem([message])
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(0, QColor(Colors.TEXT_MUTED))
            tree.addTopLevelItem(placeholder)
        if hasattr(self, 'list_issues'):
            self.list_issues.clear()

    def _load_project_into_view(self, project_id):
        """Carrega efetivamente o projeto ID na View Unica (com Cache Swap)."""
        if getattr(self, '_analysis_in_progress', False):
            print(f"[GUARD] _load_project_into_view bloqueado: análise em andamento (PID={project_id})", flush=True)
            return
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
                 
            # 4.1. Carregar APENAS dados estruturais do banco principal
            # NÃO migrar dados dos robôs - cada robô mantém seus próprios dados separados
            self.load_project_action() # Lógica existente de povoar lists/canvas

        # 5. Atualizar Top Bar UI para refletir o projeto carregado (Fundamental para sync de abas)
        self._update_top_bar_UI(project_id)

        # Atualizar pipeline status bar
        self._refresh_pipeline_status()

        # Sincronizar Tab 2 (Fase-8) com a obra ativa
        if hasattr(self, 'comparison_module') and self.comparison_module:
            try:
                proj = self.db.get_project_by_id(project_id)
                if proj:
                    self.comparison_module.fase8_panel.set_obra(
                        proj.get('work_name', ''),
                        proj.get('pavement_name', ''),
                    )
            except Exception:
                pass

        # 6. Atualizar documentos no ProjectManager se estiver aberto
        if hasattr(self, 'project_manager') and self.project_manager:
            if hasattr(self.project_manager, 'current_project_id') and self.project_manager.current_project_id != project_id:
                # Se o projeto atual do ProjectManager é diferente, atualizar
                self.project_manager.current_project_id = project_id
                if hasattr(self.project_manager, 'refresh_documents'):
                    self.project_manager.refresh_documents()
                    self.log(f"📄 Documentos atualizados no ProjectManager para projeto {project_id}")

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
            raw_name = p.get('pavement_name') or p.get('name')
            fmt = getattr(self, '_pav_card_label', lambda n: n)(raw_name)
            self.cmb_pavements.addItem(fmt, (p['id'], raw_name))
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
            _d = self.cmb_pavements.itemData(i)
            _pid = _d[0] if isinstance(_d, tuple) else _d
            if str(_pid) == str(project_id):
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
        self.left_panel.setFixedWidth(345)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(3)

        # ── Painel de Contexto: Obra / Pavimento / Níveis ────────────────────
        _SS_COMBO = f"""
            QComboBox {{
                background: {Colors.BG_CARD}; color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 3px;
                padding: 2px 5px; font-size: 10px; max-height: 20px;
            }}
            QComboBox:hover {{ border-color: {Colors.ACCENT_PRIMARY}; }}
            QComboBox::drop-down {{ border: none; width: 16px; }}
            QComboBox QAbstractItemView {{
                background: {Colors.BG_CARD}; color: {Colors.TEXT_PRIMARY};
                selection-background-color: {Colors.ACCENT_BLUE};
            }}
        """
        _SS_EDIT = f"""
            QLineEdit {{
                background: {Colors.BG_CARD}; color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 3px;
                padding: 2px 4px; font-size: 10px; max-height: 20px;
            }}
            QLineEdit:focus {{ border-color: {Colors.ACCENT_PRIMARY}; }}
        """

        ctx_frame = QFrame()
        ctx_frame.setObjectName("SAContextFrame")
        ctx_frame.setStyleSheet(f"""
            QFrame#SAContextFrame {{
                background: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
            }}
        """)
        ctx_lay = QVBoxLayout(ctx_frame)
        ctx_lay.setContentsMargins(7, 4, 7, 5)
        ctx_lay.setSpacing(3)

        _lbl_sec = QLabel("OBRA  &  PAVIMENTO")
        _lbl_sec.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9px; font-weight: bold; letter-spacing: 1px;"
        )
        ctx_lay.addWidget(_lbl_sec)

        self.sa_cmb_obras = QComboBox()
        self.sa_cmb_obras.setPlaceholderText("Selecione a Obra...")
        self.sa_cmb_obras.setStyleSheet(_SS_COMBO)
        try:
            _works = self.db.get_all_works()
            self.sa_cmb_obras.addItems(_works)
        except Exception:
            pass
        ctx_lay.addWidget(self.sa_cmb_obras)

        self.sa_cmb_pavimentos = QComboBox()
        self.sa_cmb_pavimentos.setPlaceholderText("Selecione o Pavimento...")
        self.sa_cmb_pavimentos.setStyleSheet(_SS_COMBO)
        ctx_lay.addWidget(self.sa_cmb_pavimentos)

        _niveis_row = QHBoxLayout()
        _niveis_row.setSpacing(6)
        _lbl_cheg = QLabel("Cheg.:")
        _lbl_cheg.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
        self.sa_edit_nivel_cheg = QLineEdit("0.00")
        self.sa_edit_nivel_cheg.setFixedWidth(60)
        self.sa_edit_nivel_cheg.setStyleSheet(_SS_EDIT)
        _lbl_saida = QLabel("Saída:")
        _lbl_saida.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 10px;")
        self.sa_edit_nivel_saida = QLineEdit("3.00")
        self.sa_edit_nivel_saida.setFixedWidth(60)
        self.sa_edit_nivel_saida.setStyleSheet(_SS_EDIT)
        _niveis_row.addWidget(_lbl_cheg)
        _niveis_row.addWidget(self.sa_edit_nivel_cheg)
        _niveis_row.addStretch()
        _niveis_row.addWidget(_lbl_saida)
        _niveis_row.addWidget(self.sa_edit_nivel_saida)
        ctx_lay.addLayout(_niveis_row)

        left_layout.addWidget(ctx_frame)

        # ── Sync helpers ──────────────────────────────────────────────────────
        import re as _re

        def _pav_card_label(name: str) -> str:
            """Extrai classificação do pavimento e formata como badge + nome curto."""
            up = name.upper()
            # Nome curto: remove sufixo _R20XX_ASCII_ODA e extensão .DXF/.DWG
            short = _re.sub(r'_R\d{4}_ASCII_ODA.*$', '', name, flags=_re.I)
            short = _re.sub(r'\.(DXF|DWG)$', '', short, flags=_re.I).strip()

            # ── Detectar classificação de pavimento ──────────────────────────
            # Número + P/PV/PAV: 13P, 14P, 1PV, 2PV, 1PAV, 8PAV
            m_num = _re.search(r'[-_ ](\d{1,2})P(?:AV?|V)?(?:[-_ ]|$)', up)
            if not m_num: m_num = _re.match(r'^(\d{1,2})\s*PAV', up)
            if not m_num: m_num = _re.match(r'^PAV\s*(\d{1,2})(?:\s|$)', up)
            if m_num:
                n = m_num.group(1)
                return f"[{n}º PAV]  {short}"
            # Terreo
            if _re.search(r'[-_]TER[-_]|TERREO|TÉRREO', up):
                return f"[TÉRREO]  {short}"
            # Fundação
            if _re.search(r'[-_]FUN[-_]|FUNDA', up):
                return f"[FUNDAÇÃO]  {short}"
            # Tipo
            if _re.search(r'[-_]TIP[-_]|TIPO', up):
                return f"[TIPO]  {short}"
            # Cobertura
            if _re.search(r'[-_]COB[E_-]|COBER|DECK|BARR', up):
                return f"[COBERTURA]  {short}"
            # Ático
            if _re.search(r'[-_]ATC[-_]|ATICO|ÁTICO', up):
                return f"[ÁTICO]  {short}"
            # Subsolo
            if _re.search(r'[-_]SUB[-_]|SUBSOLO', up):
                return f"[SUBSOLO]  {short}"
            # Fallback: código numérico original
            m_id = _re.search(r'[-_](\d{3,5})[-_]', name)
            if m_id:
                return f"[{m_id.group(1)}]  {short}"
            return short

        self._pav_card_label = _pav_card_label  # expõe para outros métodos

        def _sa_populate_pavimentos(obra_name: str):
            self.sa_cmb_pavimentos.blockSignals(True)
            self.sa_cmb_pavimentos.clear()
            try:
                projects = [p for p in self.db.get_projects() if (p.get('work_name') or '') == obra_name]
                added = set()       # project IDs já inseridos
                added_names = set() # pavement_names já inseridos (evita duplicata com IDs diferentes)
                try:
                    import sqlite3 as _sql
                    conn = _sql.connect(getattr(self.db, "db_path", "D:/Agente-cad-PYSIDE/project_data.vision"))
                    conn.row_factory = _sql.Row
                    rows = conn.execute(
                        "SELECT file_name, file_path FROM obra_triagem "
                        "WHERE obra_name=? AND status='approved' "
                        "AND suggested_category LIKE '%Bruto%' "
                        "ORDER BY suggested_order ASC, file_name ASC",
                        (obra_name,),
                    ).fetchall()
                    conn.close()
                    for row in rows:
                        fname = row["file_name"] or ""
                        fpath = row["file_path"] or ""
                        fname_base = fname.rsplit('.', 1)[0] if fname else ""
                        match = None
                        for p in projects:
                            pname = p.get('pavement_name') or p.get('name') or ''
                            if fname_base and fname_base == pname:
                                match = p; break
                            if fname and fname in (pname or p.get('dxf_path') or ''):
                                match = p; break
                            if fpath and fpath == (p.get('dxf_path') or ''):
                                match = p; break
                        if match:
                            if str(match['id']) in added:
                                continue
                            nm = match.get('pavement_name') or match.get('name') or fname
                            if nm in added_names:
                                continue
                            display = _pav_card_label(fname or nm)
                            self.sa_cmb_pavimentos.addItem(display, (match['id'], nm))
                            added.add(str(match['id']))
                            added_names.add(nm)
                except Exception:
                    pass
                for p in projects:
                    if str(p.get('id')) in added:
                        continue
                    nm = p.get('pavement_name') or p.get('name') or ''
                    if nm in added_names:
                        continue
                    display = _pav_card_label(nm)
                    # userData = (project_id, raw_name) para busca precisa
                    self.sa_cmb_pavimentos.addItem(display, (p['id'], nm))
                    added.add(str(p['id']))
                    added_names.add(nm)
            except Exception:
                pass
            self.sa_cmb_pavimentos.blockSignals(False)

        # Store for reverse-sync
        self._sa_populate_pavimentos = _sa_populate_pavimentos

        def _on_sa_obra_changed():
            obra = self.sa_cmb_obras.currentText()
            if not obra:
                return
            
            import PySide6.QtWidgets
            PySide6.QtWidgets.QApplication.processEvents()
            
            # Feedback visual rápido
            self.sa_cmb_pavimentos.blockSignals(True)
            self.sa_cmb_pavimentos.clear()
            self.sa_cmb_pavimentos.addItem("⏳ Carregando pavimentos...")
            self.sa_cmb_pavimentos.blockSignals(False)
            PySide6.QtWidgets.QApplication.processEvents()
            
            def _do_obra():
                # Popula SA primeiro, depois sincroniza top bar
                _sa_populate_pavimentos(obra)
                top_idx = self.cmb_works.findText(obra)
                if top_idx >= 0 and self.cmb_works.currentIndex() != top_idx:
                    self.cmb_works.setCurrentIndex(top_idx)
                    
            from PySide6.QtCore import QTimer
            QTimer.singleShot(150, _do_obra)

        def _on_sa_pav_changed():
            data = self.sa_cmb_pavimentos.currentData()
            if not data:
                return
            project_id, raw_name = data

            import PySide6.QtWidgets
            PySide6.QtWidgets.QApplication.processEvents()

            # Exibe feedback na própria combobox para clareza
            idx = self.sa_cmb_pavimentos.currentIndex()
            if idx >= 0:
                self.sa_cmb_pavimentos.setItemText(idx, f"⏳ Lendo {raw_name}...")
            
            # Exibe feedback na topbar ou log para o usuário saber que começou
            self.log(f"⏳ Carregando dados do pavimento: {raw_name}...")
            PySide6.QtWidgets.QApplication.processEvents()
            
            def _do_pav():
                # Restaura texto normal
                if idx >= 0 and getattr(self, '_sa_populate_pavimentos', None):
                    display = _pav_card_label(raw_name)
                    self.sa_cmb_pavimentos.setItemText(idx, display)

                # Sincroniza top bar pelo nome raw
                top_idx = self.cmb_pavements.findText(raw_name)
                if top_idx >= 0:
                    if self.cmb_pavements.currentIndex() != top_idx:
                        # Signal _on_pavement_changed dispara e carrega DXF
                        self.cmb_pavements.setCurrentIndex(top_idx)
                    else:
                        # Mesmo índice: signal não re-dispara, forçar carga
                        self._open_project_tab(project_id, raw_name)
                else:
                    # Não encontrou no top bar — carrega direto pelo project_id
                    self.log(f"[SA] Forçando carregamento via combo: {raw_name}")
                    obra = self.sa_cmb_obras.currentText()
                    self.sync_robots_with_master_context(obra, raw_name, project_id)
                    self._open_project_tab(project_id, raw_name)

            from PySide6.QtCore import QTimer
            QTimer.singleShot(150, _do_pav)

        def _on_sa_nivel_cheg():
            v = self.sa_edit_nivel_cheg.text()
            if self.edit_level_arr.text() != v:
                self.edit_level_arr.setText(v)
                self.save_project_metadata()

        def _on_sa_nivel_saida():
            v = self.sa_edit_nivel_saida.text()
            if self.edit_level_exit.text() != v:
                self.edit_level_exit.setText(v)
                self.save_project_metadata()

        self.sa_cmb_obras.currentIndexChanged.connect(lambda _: _on_sa_obra_changed())
        self.sa_cmb_pavimentos.currentIndexChanged.connect(lambda _: _on_sa_pav_changed())
        self.sa_edit_nivel_cheg.editingFinished.connect(_on_sa_nivel_cheg)
        self.sa_edit_nivel_saida.editingFinished.connect(_on_sa_nivel_saida)

        # Popula pavimentos para a obra já selecionada no combo (items foram adicionados
        # antes da conexão do sinal, então currentIndexChanged nunca disparou)
        if self.sa_cmb_obras.count() > 0:
            _on_sa_obra_changed()

        # ── Separador visual ──────────────────────────────────────────────────
        _sep = QFrame()
        _sep.setFrameShape(QFrame.HLine)
        _sep.setFixedHeight(1)
        _sep.setStyleSheet(f"background: {Colors.BORDER_DEFAULT}; border: none;")
        left_layout.addWidget(_sep)

        # ── Tipo Geral de Vigas (redesign DS) ────────────────────────────────
        _vigas_frame = QFrame()
        _vigas_frame.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_DEFAULT};
                border-radius: 4px;
            }}
        """)
        _vigas_lay = QHBoxLayout(_vigas_frame)
        _vigas_lay.setContentsMargins(6, 3, 6, 3)
        _vigas_lay.setSpacing(6)

        # 1.5. Round Buttons Gerais - Tipo de Vigas (Visibilidade Constante)
        h_radio_layout_geral = QHBoxLayout()
        h_radio_layout_geral.setContentsMargins(0, 0, 0, 5)
        
        lbl_radio_geral = QLabel("Tipo Geral de Vigas:")
        lbl_radio_geral.setStyleSheet("font-size: 10px; color: #ccc; font-weight: bold;")
        h_radio_layout_geral.addWidget(lbl_radio_geral)
        
        self.rb_vigas_passam = QRadioButton("Vigas Passam")
        self.rb_vigas_passam.setObjectName("rb_vigas_passam")
        self.rb_vigas_passam.setStyleSheet("QRadioButton { font-size: 10px; color: #ccc; padding: 2px; }")
        
        self.rb_vigas_param = QRadioButton("Vigas Param")
        self.rb_vigas_param.setObjectName("rb_vigas_param")
        self.rb_vigas_param.setStyleSheet("QRadioButton { font-size: 10px; color: #ccc; padding: 2px; }")
        
        # ButtonGroup para garantir seleção única
        self.btn_group_geral_vigas = QButtonGroup()
        self.btn_group_geral_vigas.addButton(self.rb_vigas_passam, 0)  # 0 = Passam
        self.btn_group_geral_vigas.addButton(self.rb_vigas_param, 1)  # 1 = Param
        
        # Nenhum selecionado por padrão (permite edição manual individual)
        self.rb_vigas_passam.setChecked(False)
        self.rb_vigas_param.setChecked(False)
        
        # Conectar mudanças para atualizar todos os itens
        def on_tipo_geral_changed(checked):
            if checked:
                tipo = 'passa' if self.btn_group_geral_vigas.checkedId() == 0 else 'para'
                self._update_all_beams_tipo_comp(tipo)
        
        self.rb_vigas_passam.toggled.connect(on_tipo_geral_changed)
        self.rb_vigas_param.toggled.connect(on_tipo_geral_changed)
        
        _vigas_lay.addWidget(lbl_radio_geral)
        _vigas_lay.addWidget(self.rb_vigas_passam)
        _vigas_lay.addWidget(self.rb_vigas_param)
        _vigas_lay.addStretch()
        left_layout.addWidget(_vigas_frame)

        # ── Seção: Ações de Análise ───────────────────────────────────────────
        _lbl_acoes = QLabel("ANÁLISE")
        _lbl_acoes.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9px; font-weight: bold;"
            " letter-spacing: 1px; margin-top: 2px;"
        )
        left_layout.addWidget(_lbl_acoes)

        _BTN_H = "max-height: 22px; min-height: 20px; padding: 2px 6px; font-size: 10px; border-radius: 3px;"

        self.btn_process = QPushButton("🚀 Iniciar Análise Geral")
        self.btn_process.setObjectName("btn_iniciar_analise")
        self.btn_process.setAccessibleName("Iniciar Analise")
        self.btn_process.setToolTip(
            "Analisa o DXF carregado e detecta pilares, vigas e lajes.\n"
            "Requer DXF carregado no Tab 0 (Diagnostic Hub).\n"
            "Alternativa: use '▶ Interpretar DXF' no Tab 0 para dados Fase-3."
        )
        self.btn_process.setStyleSheet(
            f"{_BTN_H} background: {Colors.ACCENT_BLUE}; color: #fff;"
            f" border: none;"
        )
        self.btn_process.clicked.connect(self.process_pillars_action)
        left_layout.addWidget(self.btn_process)

        self.btn_process_with_context = QPushButton("🧠 Consultar Contexto RAG")
        self.btn_process_with_context.setObjectName("btn_interpretar_contexto")
        self.btn_process_with_context.setToolTip(
            "Consulta regras semanticas e exemplos T1/T2 para o item atual. "
            "Somente leitura: nao executa Analise Geral, nao altera fichas e nao gera DXF."
        )
        self.btn_process_with_context.setStyleSheet(
            f"{_BTN_H} background: #1a3a2a; color: #5dcfa0;"
            f" border: 1px solid #2d6a4a;"
        )
        self.btn_process_with_context.clicked.connect(self._process_with_obra_context)
        left_layout.addWidget(self.btn_process_with_context)

        self.btn_process_reverse = QPushButton("⚙️ Interpretar com Eng. Reversa")
        self.btn_process_reverse.setObjectName("btn_interpretar_reversa")
        self.btn_process_reverse.setText("Analisar com Eng Reversa (F5/N2)")
        self.btn_process_reverse.setToolTip(
            "Consulta fichas N2/F5 da Engenharia Reversa. "
            "Nao gera DXF e nao roda o motor da Analise Geral."
        )
        self.btn_process_reverse.setStyleSheet(
            f"{_BTN_H} background: #3a1a3a; color: #cf5da0;"
            f" border: 1px solid #6a2d6a;"
        )
        self.btn_process_reverse.clicked.connect(self._process_with_reverse_engineering)
        left_layout.addWidget(self.btn_process_reverse)

        self.btn_refresh_data = QPushButton("🔄 Atualizar Listas")
        self.btn_refresh_data.setObjectName("Secondary")
        self.btn_refresh_data.setToolTip("Recarregar dados do projeto e atualizar listas (Pillars, Beams, Slabs)")
        self.btn_refresh_data.setStyleSheet(
            f"{_BTN_H} background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY};"
            f" border: 1px solid {Colors.BORDER_DEFAULT};"
        )
        self.btn_refresh_data.clicked.connect(self.refresh_lists_action)
        left_layout.addWidget(self.btn_refresh_data)

        self.btn_fase4_sync = QPushButton("⚙ Fase-4: Sincronizar")
        self.btn_fase4_sync.setToolTip(
            "Roda motor_fase4.py — transforma dados Fase-3 para formato dos robôs\n"
            "Necessário antes de usar os Robôs (Tabs 3-6)"
        )
        self.btn_fase4_sync.setStyleSheet(
            f"{_BTN_H} background: #1a3a5c; color: #7ab3e0; border: 1px solid #2a5a8c;"
        )
        self.btn_fase4_sync.clicked.connect(self._run_fase4_sync)
        left_layout.addWidget(self.btn_fase4_sync)

        # 2e. Log inline SA — colapsável
        from PySide6.QtWidgets import QTextEdit as _QTextEdit
        self.sa_inline_log = _QTextEdit()
        self.sa_inline_log.setReadOnly(True)
        self.sa_inline_log.setFixedHeight(48)
        self.sa_inline_log.setStyleSheet(
            f"background: {Colors.BG_DEEP}; color: {Colors.TEXT_DIM}; "
            f"border: 1px solid {Colors.BORDER_SUBTLE}; border-radius: 3px; "
            f"font-size: {Fonts.SIZE_XS}; font-family: {Fonts.FAMILY_MONO};"
        )
        self.sa_inline_log.setPlaceholderText("log SA...")
        self.sa_inline_log.setVisible(False)  # oculto por padrão

        _h_log_btns = QHBoxLayout()
        _h_log_btns.setContentsMargins(0, 0, 0, 0)
        _btn_toggle_log = QPushButton("▸ Log")
        _btn_toggle_log.setFixedHeight(16)
        _btn_toggle_log.setStyleSheet(
            f"background: transparent; color: {Colors.TEXT_MUTED}; "
            f"border: none; font-size: {Fonts.SIZE_XS}; padding: 0 4px; text-align: left;"
        )
        def _toggle_log():
            vis = not self.sa_inline_log.isVisible()
            self.sa_inline_log.setVisible(vis)
            _btn_toggle_log.setText("▾ Log" if vis else "▸ Log")
        _btn_toggle_log.clicked.connect(_toggle_log)

        _btn_clear_log = QPushButton("limpar")
        _btn_clear_log.setFixedHeight(16)
        _btn_clear_log.setStyleSheet(
            f"background: transparent; color: {Colors.TEXT_MUTED}; "
            f"border: none; font-size: {Fonts.SIZE_XS}; padding: 0 4px;"
        )
        _btn_clear_log.clicked.connect(lambda: self.sa_inline_log.clear())
        _h_log_btns.addWidget(_btn_toggle_log)
        _h_log_btns.addStretch()
        _h_log_btns.addWidget(_btn_clear_log)
        left_layout.addLayout(_h_log_btns)
        left_layout.addWidget(self.sa_inline_log)

        # 3. Botão Salvar
        self.btn_save = QPushButton("💾 Salvar Projeto")
        self.btn_save.setObjectName("Success")
        self.btn_save.setStyleSheet(
            f"{_BTN_H} background: {Colors.ACCENT_SUCCESS}; color: #fff; border: none;"
        )
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

            # LV "Análise Atual": substituir lista única por sub-abas Para/Passam
            if item_type == 'beam' and not is_library:
                _STYLE_LV_TABS = (
                    f"QTabBar::tab {{ background:{Colors.BG_CARD}; color:{Colors.TEXT_SECONDARY};"
                    f" border-radius:3px; padding:3px 10px; margin-right:2px; }}"
                    f"QTabBar::tab:selected:nth-child(1) {{ background:#1B5E20; color:#fff; font-weight:bold; }}"
                    f"QTabBar::tab:selected:nth-child(2) {{ background:#4A148C; color:#fff; font-weight:bold; }}"
                    f"QTabBar::tab:selected {{ background:#1B5E20; color:#fff; font-weight:bold; }}"
                    f"QTabWidget::pane {{ border:1px solid {Colors.BORDER_DEFAULT}; }}"
                )
                lv_analysis_tabs = QTabWidget()
                lv_analysis_tabs.setStyleSheet(_STYLE_LV_TABS)
                lv_analysis_tabs.addTab(self.list_beams_para,  "Vigas Para")
                lv_analysis_tabs.addTab(self.list_beams_passa, "Vigas Passam")
                lv_analysis_tabs.currentChanged.connect(self._on_lv_analysis_subtab_changed)
                self._lv_analysis_tabs = lv_analysis_tabs
                layout.addWidget(lv_analysis_tabs)
            else:
                # Lista normal
                layout.addWidget(list_widget)
            
            # Botões de Ação Básica
            h_layout = QHBoxLayout()
            h_layout.setContentsMargins(0,0,0,0)
            
            _UTIL_BTN = "max-height: 20px; min-height: 18px; padding: 1px 6px; font-size: 10px; border-radius: 3px;"
            # Botão Excluir Item
            btn_delete = QPushButton("🗑 Excluir")
            btn_delete.setStyleSheet(f"{_UTIL_BTN} background: #331111; color: #e07070; border: 1px solid #552222;")
            btn_delete.setToolTip("Excluir item selecionado")
            btn_delete.clicked.connect(lambda: self.delete_item_action(list_widget, item_type, is_library))
            h_layout.addWidget(btn_delete)

            # Botão Criar Novo Item (padrão)
            scope_name = "Lib" if is_library else "Análise"
            btn_create = QPushButton(f"➕ Novo ({scope_name})")
            btn_create.setStyleSheet(f"{_UTIL_BTN} background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY}; border: 1px solid {Colors.BORDER_DEFAULT};")
            btn_create.setToolTip(f"Criar novo item ({scope_name})")
            btn_create.clicked.connect(lambda: self.create_manual_item(is_library=is_library))
            h_layout.addWidget(btn_create)
            
            layout.addLayout(h_layout)

            _ROBO_BTN = "max-height: 22px; min-height: 20px; padding: 2px 6px; font-size: 10px; font-weight: bold; border-radius: 3px; border: none;"

            # Botão Sincronizar Robo Laje (apenas para Laje na aba de Análise)
            if item_type == 'slab' and not is_library:
                btn_sync_robo = QPushButton("🤖 Sincronizar Robo Laje")
                btn_sync_robo.setStyleSheet(f"{_ROBO_BTN} background: #4a1d96; color: #d4b8ff;")
                btn_sync_robo.setToolTip("Envia as lajes desta lista para o módulo Robo Lajes, calculando a geometria unificada (Marco + Extensões).")
                btn_sync_robo.clicked.connect(self.sync_slabs_to_robo_laje_action)
                layout.addWidget(btn_sync_robo)

            # Botão Sincronizar Robo Vigas (apenas para Vigas na aba de Análise)
            if item_type == 'beam' and not is_library:
                btn_laterais = QPushButton("🤖 Sincronizar Laterais de Vigas")
                btn_laterais.setStyleSheet(f"{_ROBO_BTN} background: #4a1d96; color: #d4b8ff;")
                btn_laterais.clicked.connect(self.sync_beams_to_laterais_action)
                layout.addWidget(btn_laterais)

                btn_fundo = QPushButton("🤖 Sincronizar Fundo de Vigas")
                btn_fundo.setStyleSheet(f"{_ROBO_BTN} background: #4a1d96; color: #d4b8ff;")
                btn_fundo.clicked.connect(self.sync_beams_to_fundo_action)
                layout.addWidget(btn_fundo)

            # Botão Sincronizar Robo Pilares (apenas para Pilar na aba de Análise)
            if item_type == 'pillar' and not is_library:
                btn_sync_pilar = QPushButton("🤖 Sincronizar Robo Pilares")
                btn_sync_pilar.setStyleSheet(f"{_ROBO_BTN} background: #4a1d96; color: #d4b8ff;")
                btn_sync_pilar.setToolTip("Envia os pilares desta lista para o módulo Robo Pilares, calculando dimensões e níveis automaticamente.")
                btn_sync_pilar.clicked.connect(self.sync_pillars_to_robo_pilares_action)
                layout.addWidget(btn_sync_pilar)

            # Botão Criar Comando LISP — OCULTO a pedido do usuário (libera espaço
            # para a lista de pilares; funcionalidade mantida, basta reabilitar)
            # if not is_library:
            #     btn_create_lisp = QPushButton("📜 Criar Comando LISP")
            #     btn_create_lisp.clicked.connect(lambda: self._create_laz_command_files())
            #     layout.addWidget(btn_create_lisp)

            return container

        # --- TAB 1: ANÁLISE ATUAL (Pilares, Vigas, Lajes, Contorno, Issues) ---
        self.tab_analysis = QWidget()
        analysis_layout = QVBoxLayout(self.tab_analysis)
        analysis_layout.setContentsMargins(0,0,0,0)
        
        self.tabs_analysis_internal = QTabWidget()
        self.tabs_analysis_internal.setStyleSheet(STYLE_TABS)
        self.list_pillars = QTreeWidget()
        self.list_pillars.setHeaderLabels(["Item", "Nome", "Status", "%", "Classificação"])
        self.list_pillars.setColumnWidth(0, 50)
        self.list_pillars.setColumnWidth(1, 150)
        self.list_pillars.setColumnWidth(2, 55)
        self.list_pillars.setColumnWidth(3, 40)  # %
        self.list_pillars.setColumnWidth(4, 95)  # NASCE/SEGUE/MORRE/PASSA…

        self.list_beams = QTreeWidget()
        self.list_beams.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams.setColumnWidth(0, 50)
        self.list_beams.setColumnWidth(1, 150)
        self.list_beams.setColumnWidth(2, 60)
        self.list_beams.setColumnWidth(3, 40)

        # Sub-listas LV — Vigas Para / Vigas Passam (sub-abas da aba "Lat. de Vigas")
        self.list_beams_para = QTreeWidget()
        self.list_beams_para.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams_para.setColumnWidth(0, 50)
        self.list_beams_para.setColumnWidth(1, 150)
        self.list_beams_para.setColumnWidth(2, 60)
        self.list_beams_para.setColumnWidth(3, 40)

        self.list_beams_passa = QTreeWidget()
        self.list_beams_passa.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams_passa.setColumnWidth(0, 50)
        self.list_beams_passa.setColumnWidth(1, 150)
        self.list_beams_passa.setColumnWidth(2, 60)
        self.list_beams_passa.setColumnWidth(3, 40)

        self.list_beams_fundo = QTreeWidget()
        self.list_beams_fundo.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams_fundo.setColumnWidth(0, 50)
        self.list_beams_fundo.setColumnWidth(1, 150)
        self.list_beams_fundo.setColumnWidth(2, 60)
        self.list_beams_fundo.setColumnWidth(3, 40)
        
        self.list_slabs = QTreeWidget()
        self.list_slabs.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_slabs.setColumnWidth(0, 50)
        self.list_slabs.setColumnWidth(1, 140)
        self.list_slabs.setColumnWidth(2, 50)
        self.list_slabs.setColumnWidth(3, 50)

        self.list_issues = QListWidget()
        
        # Conectar Sinais (Atual)
        # Conectar Sinais (Atual) - Mouse e Teclado (Setinhas)
        self.list_pillars.itemClicked.connect(lambda item, col: self.on_list_pillar_clicked(item))
        # self.list_pillars.currentItemChanged.connect(lambda curr, prev: # self.on_list_pillar_clicked(curr) if curr else None)
        
        self.list_beams.itemClicked.connect(self.on_list_beam_clicked)
        # self.list_beams.currentItemChanged.connect(lambda curr, prev: # self.on_list_beam_clicked(curr, 0) if curr else None)
        self.list_beams_para.itemClicked.connect(self.on_list_beam_clicked)
        # self.list_beams_para.currentItemChanged.connect(lambda curr, prev: # self.on_list_beam_clicked(curr, 0) if curr else None)
        self.list_beams_passa.itemClicked.connect(self.on_list_beam_clicked)
        # self.list_beams_passa.currentItemChanged.connect(lambda curr, prev: # self.on_list_beam_clicked(curr, 0) if curr else None)

        self.list_beams_fundo.itemClicked.connect(self.on_list_beam_fundo_clicked)
        # self.list_beams_fundo.currentItemChanged.connect(lambda curr, prev: # self.on_list_beam_fundo_clicked(curr, 0) if curr else None)
        
        self.list_slabs.itemClicked.connect(lambda item, col: self.on_list_slab_clicked(item))
        # self.list_slabs.currentItemChanged.connect(lambda curr, prev: # self.on_list_slab_clicked(curr) if curr else None)
        
        self.list_issues.itemClicked.connect(self.on_issue_clicked)
        # self.list_issues.currentItemChanged.connect(lambda curr, prev: # self.on_issue_clicked(curr) if curr else None)
        
        # Adicionar Abas com Containers
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_pillars, 'pillar', False), "Pilares")
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_beams, 'beam', False), "Lat. de Vigas")
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_beams_fundo, 'beam_fundo', False), "Fun. de Vigas")
        self.tabs_analysis_internal.addTab(create_tab_container(self.list_slabs, 'slab', False), "Lajes")
        self.tabs_analysis_internal.addTab(self.list_issues, "⚠️ Pendências")

        # Estado vazio inicial (antes de qualquer projeto ser aberto)
        self._show_lists_empty_state("Selecione ou abra um projeto")

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
        self.list_pillars_valid.setHeaderLabels(["Item", "Nome", "Status", "%", "Classificação"])
        self.list_pillars_valid.setColumnWidth(0, 50)
        self.list_pillars_valid.setColumnWidth(1, 150)
        self.list_pillars_valid.setColumnWidth(2, 55)
        self.list_pillars_valid.setColumnWidth(3, 40)
        self.list_pillars_valid.setColumnWidth(4, 95)

        self.list_beams_valid = QTreeWidget()
        self.list_beams_valid.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams_valid.setColumnWidth(0, 50)
        self.list_beams_valid.setColumnWidth(1, 150)
        self.list_beams_valid.setColumnWidth(2, 60)
        self.list_beams_valid.setColumnWidth(3, 40)

        self.list_beams_fundo_valid = QTreeWidget()
        self.list_beams_fundo_valid.setHeaderLabels(["Item", "Nome", "Status", "%"])
        self.list_beams_fundo_valid.setColumnWidth(0, 50)
        self.list_beams_fundo_valid.setColumnWidth(1, 150)
        self.list_beams_fundo_valid.setColumnWidth(2, 60)
        self.list_beams_fundo_valid.setColumnWidth(3, 40)

        self.list_slabs_valid = QTreeWidget()
        self.list_slabs_valid.setHeaderLabels(["Item", "Nome", "Status", "%", "Ação"])
        self.list_slabs_valid.setColumnWidth(0, 50)
        self.list_slabs_valid.setColumnWidth(1, 120)
        self.list_slabs_valid.setColumnWidth(2, 50)
        self.list_slabs_valid.setColumnWidth(3, 50)
        
        # Conectar Sinais (Validado)
        # Conectar Sinais (Validado) - Mouse e Teclado
        self.list_pillars_valid.itemClicked.connect(lambda item, col: self.on_list_pillar_clicked(item))
        # self.list_pillars_valid.currentItemChanged.connect(lambda curr, prev: # self.on_list_pillar_clicked(curr) if curr else None)
        
        self.list_beams_valid.itemClicked.connect(self.on_list_beam_clicked)
        # self.list_beams_valid.currentItemChanged.connect(lambda curr, prev: # self.on_list_beam_clicked(curr, 0) if curr else None)
        
        self.list_beams_fundo_valid.itemClicked.connect(self.on_list_beam_fundo_clicked)
        # self.list_beams_fundo_valid.currentItemChanged.connect(lambda curr, prev: # self.on_list_beam_fundo_clicked(curr, 0) if curr else None)
        
        self.list_slabs_valid.itemClicked.connect(lambda item, col: self.on_list_slab_clicked(item))
        # self.list_slabs_valid.currentItemChanged.connect(lambda curr, prev: # self.on_list_slab_clicked(curr) if curr else None)
        
        # Adicionar Abas com Containers
        self.tabs_library_internal.addTab(create_tab_container(self.list_pillars_valid, 'pillar', True), "Pilares OK")
        self.tabs_library_internal.addTab(create_tab_container(self.list_beams_valid, 'beam', True), "Lat. Vigas OK")
        self.tabs_library_internal.addTab(create_tab_container(self.list_beams_fundo_valid, 'beam_fundo', True), "Fun. Vigas OK")
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
        # Terminal de Eventos oculto (libera espaço para a lista); console vivo pois self.log() usa append()
        self._console_label = QLabel("Terminal de Eventos:")
        self._console_label.setVisible(False)
        self.console.setVisible(False)
        left_layout.addWidget(self._console_label)
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
        self.right_panel.setMinimumWidth(580)
        
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
        
        # Definir proporção inicial: Esquerda (365), Centro (Grande), Direita (670)
        self.splitter.setSizes([365, 840, 670])
        
        
        
        main_layout.addWidget(self.splitter)
        
        # Add content area to module layout
        module_layout.addWidget(content_area)
        
        return module_container

    def sync_slabs_to_robo_laje_action(self, confirm: bool = True, switch_to_tab: bool = True, run_ai: bool = True):
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
            
        pavimento_nome = self._current_pavement_name()
        if not pavimento_nome:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Aviso", "Selecione um Pavimento na barra superior.")
            return
            
        # IMPORTANTE: Garantir que a obra está no combo do robo_laje para ser salva corretamente
        if hasattr(self.robo_laje, 'obra_control'):
            obra_no_combo = False
            for i in range(self.robo_laje.obra_control.obra_combo.count()):
                obra_combo = self.robo_laje.obra_control.obra_combo.itemData(i)
                if obra_combo and obra_combo.nome == obra_robo.nome:
                    # Atualizar obra no combo com a versão atualizada
                    self.robo_laje.obra_control.obra_combo.setItemData(i, obra_robo)
                    obra_no_combo = True
                    break
            if not obra_no_combo:
                # Adicionar obra ao combo se não estiver lá
                self.robo_laje.obra_control.obra_combo.addItem(obra_robo.nome, obra_robo)
                # Adicionar à lista de obras também
                if hasattr(self.robo_laje, 'todas_obras'):
                    if obra_robo not in self.robo_laje.todas_obras:
                        self.robo_laje.todas_obras.append(obra_robo)
            
        # Encontrar Pavimento no Robo
        pavimento_alvo = next((p for p in obra_robo.pavimentos if p.nome == pavimento_nome), None)
        if not pavimento_alvo:
            # Tentar criar se não existir (embora o sync automatico devesse ter criado)
            from laje_src.models.pavimento import Pavimento  # type: ignore
            pavimento_alvo = Pavimento(nome=pavimento_nome)
            obra_robo.pavimentos.append(pavimento_alvo)
            # Atualizar lista de pavimentos no robo
            if hasattr(self.robo_laje, 'pavimentos_widget'):
                self.robo_laje.pavimentos_widget.update_list()
                self.robo_laje.pavimentos_widget.select_or_create_pavimento(pavimento_nome)

        # 3. Preparar Dados das Lajes (Structural Analyzer -> Robo Lajes)
        from laje_src.models.laje import Laje  # type: ignore
        
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
            try:
                ficha_n1 = self._slab_to_n1_robot_ficha(slab_data)
                ficha_n3 = self._merge_lj_n3_teacher(ficha_n1, {})
                coords = ficha_n3.get("coordenadas") or coords
                comp = float(ficha_n3.get("comprimento") or 0.0)
                larg = float(ficha_n3.get("largura") or 0.0)
                area_robot = float(ficha_n3.get("area_cm2") or (area_m2 * 10000))
                linhas_v = list(ficha_n3.get("linhas_verticais") or [])
                linhas_h = list(ficha_n3.get("linhas_horizontais") or [])
                obstaculos = list(ficha_n3.get("obstaculos") or [])
                modo = int(float(ficha_n3.get("modo_selecionado") or 0))
                unioes = bool(ficha_n3.get("unioes_nos_bordes") or False)
                observacoes = str(ficha_n3.get("observacoes") or "")
            except Exception:
                comp = 0.0
                larg = 0.0
                area_robot = area_m2 * 10000
                linhas_v = []
                linhas_h = []
                obstaculos = []
                modo = 0
                unioes = False
                observacoes = ""

            nova_laje = Laje(
                numero=numero,
                nome=name,
                comprimento=comp,
                largura=larg,
                pavimento=pavimento_nome,
                coordenadas=coords,
                area_cm2=area_robot,
                linhas_verticais=linhas_v,
                linhas_horizontais=linhas_h,
                obstaculos=obstaculos,
                modo_selecionado=modo,
                unioes_nos_bordes=unioes,
                observacoes=observacoes,
            )
            
            novas_lajes_robo.append(nova_laje)
            count += 1

        if not novas_lajes_robo:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Aviso", "Nenhuma laje encontrada na lista de análise para sincronizar.")
            return

        # 4. Substituir/Popular no Pavimento Alvo
        from PySide6.QtWidgets import QMessageBox
        if confirm:
            reply = QMessageBox.question(
                self,
                "Sincronizar Robo Lajes",
                f"Isso irá SUBSTITUIR todas as lajes do pavimento '{pavimento_nome}' no Robo Lajes \n"
                f"pelas {count} lajes da Análise Atual.\n\n"
                "Deseja continuar?",
                QMessageBox.Yes | QMessageBox.No
            )
        else:
            reply = QMessageBox.Yes
        
        if reply == QMessageBox.Yes:
            pavimento_alvo.lajes = novas_lajes_robo
            
            # 5. Atualizar UI do Robo Lajes e Iniciar Automação IA
            if hasattr(self, 'robo_laje') and self.robo_laje is not None and hasattr(self.robo_laje, 'laje_tab'):
                # Trocar para a aba do Robo Laje para visualização do processo
                if switch_to_tab and hasattr(self, 'module_tabs'):
                    self.module_tabs.setCurrentIndex(8)  # Robo Laje é a 9ª aba (índice 8)
                if switch_to_tab and hasattr(self, 'module_stack'):
                    self.module_stack.setCurrentIndex(8)  # Robo Laje é o 9º módulo (índice 8)
                
                # Forçar atualização da tabela
                if hasattr(self.robo_laje, 'pavimentos_widget'):
                    self.robo_laje.pavimentos_widget.select_or_create_pavimento(pavimento_nome)
                
                self.robo_laje.laje_tab.atualizar_tabela_lajes()
                
                # Emitir sinal obra_changed para atualizar a UI
                if hasattr(self.robo_laje.laje_tab, 'obra_changed'):
                    self.robo_laje.laje_tab.obra_changed.emit(obra_robo)

                                # Iniciar Processamento IA Automatizado (Linhas + Cotas)
                if run_ai and hasattr(self.robo_laje.laje_tab, 'automate_ai_for_all_lajes'):
                    self.show_progress("Processando Lajes pela IA...", 0)
                    
                    def prog_cb(pct, msg):
                        self.update_progress(pct, msg)
                        from PySide6.QtWidgets import QApplication
                        QApplication.processEvents()

                    self.robo_laje.laje_tab.automate_ai_for_all_lajes(progress_callback=prog_cb)
                    self.hide_progress()
                else:
                    # Sem IA: salvar uma vez após sincronização
                    if hasattr(self.robo_laje, 'save_all_obras_auto'):
                        self.robo_laje.save_all_obras_auto()
                        print(f"[SYNC] ✅ Dados salvos após sincronização de {count} lajes")
                
                if confirm:
                    QMessageBox.information(self, "Sucesso", f"{count} lajes sincronizadas e processadas pela IA!")

        self.statusBar.showMessage(f"Sincronização concluída: {count} lajes enviadas.", 5000)

    def _auto_sync_beams_to_laterais_silent(self):
        """Versão silenciosa (sem dialogs) do sync para Robo LV, chamada após análise."""
        try:
            if not getattr(self, 'robo_viga', None):
                return
            obra_nome = self.cmb_works.currentText()
            pavimento_nome = self._current_pavement_name()
            if not obra_nome or not pavimento_nome:
                return
            if not getattr(self, 'beams_found', None):
                return
            self.robo_viga.add_global_pavimento(obra_nome, pavimento_nome)
            import re as _re
            def _nat(s): return [int(t) if t.isdigit() else t.lower() for t in _re.split(r'(\d+)', str(s))]
            sorted_beams = sorted(self.beams_found, key=lambda x: _nat(x.get('name', '')))
            viga_list = []
            for b in sorted_beams:
                base_name = b.get('name', '')
                number = b.get('id_item', base_name)
                for pp in ("Para", "Passa"):
                    for face in ("A", "B"):
                        viga_list.append({
                            'name': f"{base_name}_{pp}_{face}",
                            'display_name': f"{base_name}.{face}",
                            'base_beam': base_name,
                            'number': number,
                            'parent_name': pp,
                            'face': face,
                        })
            if viga_list:
                self.robo_viga.add_viga_bulk(viga_list)
                self.log(f"🔗 Auto-sync Robo LV: {len(sorted_beams)} vigas → {len(viga_list)} entradas.")
        except Exception as _e:
            self.log(f"[auto-sync LV] {_e}")

    def sync_beams_to_laterais_action(self):
        """Sincroniza as vigas da análise para o Robo Laterais."""
        if not hasattr(self, 'robo_viga') or not self.robo_viga:
            QMessageBox.warning(self, "Erro", "Módulo Robo Laterais não está carregado.")
            return

        # Contexto
        obra_nome = self.cmb_works.currentText()
        pavimento_nome = self._current_pavement_name()
        
        if not obra_nome or not pavimento_nome:
            QMessageBox.warning(self, "Aviso", "Selecione Obra e Pavimento.")
            return
            
        # Garantir contexto no robo
        self.robo_viga.add_global_pavimento(obra_nome, pavimento_nome)
        
        # Ordenação Natural (1, 2, ..., 10, 11...)
        import re
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower()
                    for text in re.split(r'(\d+)', str(s))]

        # Preparar Lista Ordenada
        sorted_beams = sorted(self.beams_found, key=lambda x: natural_sort_key(x.get('name', '')))
        
        viga_list = []
        for b in sorted_beams:
            base_name = b.get('name', '')
            number = b.get('id_item', base_name)
            # Cada viga gera 4 entradas: Para/Passa × Face A/B
            for pp in ("Para", "Passa"):
                for face in ("A", "B"):
                    viga_list.append({
                        'name': f"{base_name}_{pp}_{face}",   # chave única
                        'display_name': f"{base_name}.{face}",  # exibição no robot
                        'base_beam': base_name,
                        'number': number,
                        'parent_name': pp,   # segment_class = "Para" ou "Passa"
                        'face': face,
                    })

        if not viga_list:
             QMessageBox.information(self, "Aviso", "Nenhuma viga encontrada na análise.")
             return

        res = self.robo_viga.add_viga_bulk(viga_list)
        # Se retornar um dict, usamos. Se retornar int (legado), tratamos.
        if isinstance(res, dict):
            beams_count = len(sorted_beams)
            count = res.get('added', 0)
            skipped = res.get('skipped', 0)
            msg = (f"{beams_count} vigas → {count} entradas criadas (Para A/B + Passa A/B).\n"
                   f"({skipped} entradas já existiam no Robo Laterais)")
        else:
            count = res
            msg = f"{count} novas entradas sincronizadas com Robo Laterais."

        self.log(f"🔗 Sincronização Robo Laterais: {count} novos, {len(viga_list)} total.")
        QMessageBox.information(self, "Sucesso", msg)

    def _extract_beam_bottom_boundary(self, beam):
        """
        Extrai e converte seg_bottom para formato de coordenadas do boundary.
        PRESERVA TODAS AS DEFORMIDADES (recortes, chanfros, etc.) mantendo todos os pontos.
        
        Args:
            beam: Dicionário da viga com links['viga_segs']['seg_bottom']
        
        Returns:
            Lista plana de coordenadas [x1, y1, x2, y2, ...] ou None se não disponível
        """
        links = beam.get('links', {})
        viga_segs = links.get('viga_segs', {})
        seg_bottom_list = viga_segs.get('seg_bottom', [])
        
        if not seg_bottom_list:
            return None
        
        # Coletar TODOS os pontos de TODOS os segmentos, preservando ordem e deformidades
        todos_pontos = []
        for seg in seg_bottom_list:
            if 'points' in seg and seg['points']:
                pts = seg['points']
                # Validar e converter pontos (remover Z se 3D)
                if len(pts) >= 2:
                    pts_2d = [(float(p[0]), float(p[1])) for p in pts if len(p) >= 2]
                    if len(pts_2d) >= 2:
                        # Adicionar todos os pontos deste segmento
                        todos_pontos.append(pts_2d)
        
        if not todos_pontos:
            return None
        
        # Função auxiliar para verificar se dois pontos são próximos
        def pontos_proximos(p1, p2, tol=1e-3):
            """Verifica se dois pontos são próximos (mesmo ponto)"""
            return abs(p1[0] - p2[0]) < tol and abs(p1[1] - p2[1]) < tol
        
        # Se há apenas um segmento, usar diretamente preservando todos os pontos
        if len(todos_pontos) == 1:
            pontos = todos_pontos[0]
        else:
            # Múltiplos segmentos: unir preservando TODOS os pontos na ordem correta
            # Estratégia: conectar segmentos mantendo todos os pontos intermediários
            pontos = todos_pontos[0].copy()
            restantes = todos_pontos[1:]
            
            # Tentar conectar segmentos preservando todos os pontos
            while restantes:
                progresso = False
                for idx, seg in enumerate(restantes):
                    # Tentar conectar no final da sequência atual
                    if pontos_proximos(pontos[-1], seg[0]):
                        # Conectar: adicionar todos os pontos do segmento (exceto o primeiro que já está)
                        pontos.extend(seg[1:])
                        restantes.pop(idx)
                        progresso = True
                        break
                    elif pontos_proximos(pontos[-1], seg[-1]):
                        # Segmento invertido: adicionar todos os pontos na ordem reversa
                        pontos.extend(reversed(seg[:-1]))
                        restantes.pop(idx)
                        progresso = True
                        break
                    # Tentar conectar no início da sequência atual
                    elif pontos_proximos(pontos[0], seg[-1]):
                        # Conectar no início: adicionar segmento antes do primeiro ponto
                        pontos = seg[:-1] + pontos
                        restantes.pop(idx)
                        progresso = True
                        break
                    elif pontos_proximos(pontos[0], seg[0]):
                        # Segmento invertido no início
                        pontos = list(reversed(seg[1:])) + pontos
                        restantes.pop(idx)
                        progresso = True
                        break
                
                if not progresso:
                    # Não conseguiu conectar automaticamente
                    # Adicionar o primeiro segmento restante (pode ser descontínuo, mas preserva geometria)
                    if restantes:
                        pontos.extend(restantes[0])
                        restantes.pop(0)
                    else:
                        break
        
        if len(pontos) < 3:  # Mínimo para formar polígono
            return None
        
        # Remover APENAS duplicatas consecutivas exatas (preservar deformidades próximas)
        # Usar tolerância muito pequena para não perder deformidades reais
        pontos_limpos = [pontos[0]]
        for i, p in enumerate(pontos[1:], 1):
            # Só remover se for exatamente o mesmo ponto (tolerância muito pequena)
            # Isso preserva recortes, chanfros e outras deformidades
            if not pontos_proximos(p, pontos_limpos[-1], tol=1e-6):
                pontos_limpos.append(p)
        
        # Garantir que está fechado (se primeiro e último não são iguais, fechar)
        if len(pontos_limpos) >= 3:
            # Verificar se já está fechado (com tolerância pequena)
            if not pontos_proximos(pontos_limpos[0], pontos_limpos[-1], tol=1e-6):
                pontos_limpos.append(pontos_limpos[0])
        
        if len(pontos_limpos) < 3:
            return None
        
        # Converter para formato plano [x1, y1, x2, y2, ...] PRESERVANDO TODOS OS PONTOS
        coords = []
        for point in pontos_limpos:
            coords.extend([float(point[0]), float(point[1])])
        
        return coords

    def sync_beams_to_fundo_action(self):

        """Sincroniza as vigas da análise para o Robo Fundo."""
        if not hasattr(self, 'robo_fundo') or not self.robo_fundo:
            QMessageBox.warning(self, "Erro", "Módulo Robo Fundo não está carregado.")
            return

        # Contexto
        obra_nome = self.cmb_works.currentText()
        pavimento_nome = self._current_pavement_name()
        
        if not obra_nome or not pavimento_nome:
            QMessageBox.warning(self, "Aviso", "Selecione Obra e Pavimento.")
            return
            
        # Garantir contexto no robo
        if hasattr(self.robo_fundo, 'sync_context'):
            self.robo_fundo.sync_context(obra_nome, pavimento_nome)
        
        # Ordenação Natural
        import re
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower()
                    for text in re.split(r'(\d+)', str(s))]

        # Preparar Lista Ordenada
        sorted_beams = sorted(self.beams_found, key=lambda x: natural_sort_key(x.get('name', '')))

        if not sorted_beams:
             QMessageBox.information(self, "Aviso", "Nenhuma viga encontrada na análise.")
             return
        
        # Processar item por item para processar boundary automaticamente
        count_new = 0
        count_processed = 0
        count_skipped = 0
        
        # Mostrar progresso
        self.show_progress("Sincronizando Fundos de Vigas...", 0)
        total = len(sorted_beams)
        
        for idx, b in enumerate(sorted_beams):
            # Atualizar progresso
            progress = int((idx / total) * 100)
            self.update_progress(progress, f"Processando {b.get('name', 'V?')} ({idx+1}/{total})...")
            
            # Extrair boundary
            boundary_coords = self._extract_beam_bottom_boundary(b)
            
            # Preparar dados da viga
            # Garantir que number seja sempre um número, não o nome
            id_item = b.get('id_item')
            name = b.get('name', '')
            
            # Se id_item não existe ou é igual ao nome, extrair número do nome
            if not id_item or str(id_item) == str(name):
                import re
                nums = re.findall(r'\d+', str(name))
                number = nums[0] if nums else None
            else:
                number = str(id_item)
            
            # Se ainda não tem número válido, usar None para que add_viga_with_boundary extraia
            viga_data = {
                'name': name,
                'number': number if number else None,
                'parent_name': b.get('parent_name', b.get('name', 'V?'))
            }
            
            # Adicionar viga com boundary
            result = self.robo_fundo.add_viga_with_boundary(viga_data, boundary_coords)
            
            if result['success']:
                if result['processed']:
                    count_processed += 1
                    self.log(f"✅ {viga_data['name']}: Criada e boundary processado")
                else:
                    if boundary_coords:
                        self.log(f"⚠️ {viga_data['name']}: Criada mas boundary não processado")
                    else:
                        self.log(f"ℹ️ {viga_data['name']}: Criada sem boundary")
                count_new += 1
            else:
                count_skipped += 1
                self.log(f"⏭️ {viga_data['name']}: {result.get('message', 'Já existe ou erro')}")
        
        # Finalizar progresso
        self.hide_progress()
        
        # Resumo
        msg = f"Sincronização concluída:\n"
        msg += f"- {count_new} vigas processadas\n"
        if count_processed > 0:
            msg += f"- {count_processed} boundaries analisados e preenchidos automaticamente\n"
        if count_skipped > 0:
            msg += f"- {count_skipped} vigas já existiam\n"
        
        self.log(f"🔗 Sincronização Robo Fundo: {count_new} processadas, {count_processed} com boundary, {count_skipped} já existiam.")
        QMessageBox.information(self, "Sincronização Concluída", msg)


    def sync_pillars_to_robo_pilares_action(self):
        """Sincroniza os pilares da lista de análise para o Robo Pilares."""
        # 1. Verificar disponibilidade do Robo
        if not hasattr(self, 'robo_pilares') or not self.robo_pilares:
            QMessageBox.warning(self, "Erro", "Módulo Robo Pilares não está carregado.")
            return

        # 2. Verificar Contexto (Obra/Pavimento)
        obra_nome = self.cmb_works.currentText()
        pavimento_nome = self._current_pavement_name()

        if not obra_nome or not pavimento_nome:
            QMessageBox.warning(self, "Aviso", "Selecione uma Obra e um Pavimento na barra superior.")
            return

        # 3. Obter Níveis da UI
        try:
            nivel_cheg = float(self.edit_level_arr.text().replace(',', '.') or "0.0")
            nivel_saida = float(self.edit_level_exit.text().replace(',', '.') or "0.0")
        except:
            nivel_cheg = 0.0
            nivel_saida = 0.0

        altura_pilar = abs(nivel_saida - nivel_cheg)

        # 4. Preparar Dados dos Pilares (Structural Analyzer -> Robo Pilares)
        # O caminho está configurado no sys.path para pilares-atualizado-09-25/src
        from models.pilar_model import PilarModel  # type: ignore
        
        novos_pilares_robo = []
        count = 0
        
        for p_data in self.pillars_found:
            name = p_data.get('name', 'P?')
            
            # Extrair número (ex: "P22" -> "22")
            nums = re.findall(r'\d+', name)
            numero = nums[0] if nums else "0"
            
            # ============================================
            # BUSCAR DIMENSÃO DO VÍNCULO "texto dimensao pilar"
            # OBRIGATÓRIO: Deve conter 2 números válidos
            # ============================================
            comprimento = None
            largura = None
            dim_text_valido = None
            
            # 1. Buscar no vínculo 'dim' (classe de vínculo "texto dimensao pilar")
            links = p_data.get('links', {})
            dim_links = links.get('dim', {})
            
            # Tentar acessar o texto do vínculo (pode estar em 'label' ou diretamente)
            if isinstance(dim_links, dict):
                # Formato: {'label': [{'text': '30x60'}]}
                label_list = dim_links.get('label', [])
                if label_list and len(label_list) > 0:
                    dim_text_valido = str(label_list[0].get('text', '')).strip()
            elif isinstance(dim_links, list) and len(dim_links) > 0:
                # Formato: [{'text': '30x60'}]
                dim_text_valido = str(dim_links[0].get('text', '')).strip()
            
            # 2. Se não encontrou no vínculo, tentar campo 'dim' direto (mas validar)
            if not dim_text_valido:
                dim_text_raw = p_data.get('dim', '')
                if dim_text_raw:
                    # Verificar se é um texto válido (não área em cm²)
                    dim_str = str(dim_text_raw).strip()
                    # Se contém "cm²" ou é só um número, não é válido
                    if 'cm²' not in dim_str.lower() and not dim_str.replace('.', '').replace(',', '').isdigit():
                        dim_text_valido = dim_str
            
            # 3. Validar e extrair 2 números do texto
            if dim_text_valido:
                # Regex para encontrar 2 números (suporta: 30x60, 30/60, (150x20), (30 x 250), etc.)
                # Remove parênteses e espaços extras
                dim_clean = dim_text_valido.replace('(', '').replace(')', '').strip()
                
                # Buscar padrão: número [separador] número
                # Separadores aceitos: x, X, /, espaço
                match = re.search(r'(\d+(?:[.,]\d+)?)\s*[xX/\s]\s*(\d+(?:[.,]\d+)?)', dim_clean)
                
                if match:
                    try:
                        v1_str = match.group(1).replace(',', '.')
                        v2_str = match.group(2).replace(',', '.')
                        v1 = float(v1_str)
                        v2 = float(v2_str)
                        
                        # Validar que são números válidos e positivos
                        if v1 > 0 and v2 > 0:
                            comprimento = max(v1, v2)
                            largura = min(v1, v2)
                            print(f"[sync_pillars] ✅ Dimensão válida para {name}: {dim_text_valido} → {comprimento}x{largura}")
                        else:
                            print(f"[sync_pillars] ⚠️ Dimensão inválida para {name}: números não positivos em '{dim_text_valido}'")
                    except (ValueError, TypeError) as e:
                        print(f"[sync_pillars] ⚠️ Erro ao converter dimensão para {name}: '{dim_text_valido}' - {e}")
                else:
                    print(f"[sync_pillars] ⚠️ Texto de dimensão não contém 2 números válidos para {name}: '{dim_text_valido}'")
            else:
                print(f"[sync_pillars] ⚠️ Nenhum vínculo de dimensão encontrado para {name}")

            # 4. Criar Objeto Pilar do Robo
            # Se dimensões válidas foram encontradas, usar. Caso contrário, deixar 0.0
            nova_p = PilarModel(
                numero=numero,
                nome=name,
                comprimento=float(comprimento) if comprimento is not None else 0.0,
                largura=float(largura) if largura is not None else 0.0,
                pavimento=pavimento_nome,
                nivel_chegada=nivel_cheg,
                nivel_saida=nivel_saida,
                altura=altura_pilar,
                modo_distribuicao="NOVA"
            )
            
            # Log informativo se dimensões não foram preenchidas
            if comprimento is None or largura is None:
                print(f"[sync_pillars] ℹ️ Pilar {name} criado sem dimensões (apenas número e nome)")
            
            # Sincronizar Alturas Detalhadas (h1-h5)
            # Isso garante que h1 seja 2.0 (se >2m) e o resto distribuído
            # Só executar se as dimensões foram preenchidas (comprimento > 0)
            if nova_p.comprimento > 0 and nova_p.largura > 0:
                try:
                    # Tentar importar Service (pode não estar no path se rodando isolado, mas main.py configura sys.path)
                    from services.pilar_service import PilarService  # type: ignore
                    # 1. Distribuir Altura Total nas Faces (h1..h5)
                    PilarService.distribute_face_heights(nova_p, altura_pilar)
                    # 2. Sincronizar Alturas Absolutas (Grades)
                    PilarService.sync_pilar_heights(nova_p)
                except ImportError:
                    print(f"[sync_pillars] Aviso: PilarService não encontrado para distribuir alturas em {name}.")
                except Exception as e:
                    print(f"[sync_pillars] Erro ao distribuir alturas no pilar {name}: {e}")
            else:
                print(f"[sync_pillars] ⚠️ Pular distribuição de alturas para {name} (dimensões inválidas)")
            
            novos_pilares_robo.append(nova_p)
            count += 1

        if not novos_pilares_robo:
            QMessageBox.information(self, "Aviso", "Nenhum pilar encontrado na lista de análise para sincronizar.")
            return

        # 5. Confirmar e Substituir
        reply = QMessageBox.question(
            self, 
            "Sincronizar Robo Pilares",
            f"Isso irá SUBSTITUIR todos os pilares do pavimento '{pavimento_nome}' no Robo Pilares \n"
            f"pelos {count} pilares da Análise Atual.\n\n"
            "Deseja continuar?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Garantir contexto no ViewModel do Robo
            self.robo_pilares.vm.sync_global_context(obra_nome, pavimento_nome)
            
            # Popular Pilares
            if self.robo_pilares.vm.current_pavimento:
                # PROCESSAR CADA PILAR INDIVIDUALMENTE, UM POR UM
                self.robo_pilares.vm.current_pavimento.pilares = novos_pilares_robo
                
                # Trocar para a aba do Robo Pilares ANTES de processar
                self.module_tabs.setCurrentIndex(5)
                self.module_stack.setCurrentIndex(5)
                QApplication.processEvents()
                
                # Processar cada pilar passo a passo (ROBUSTEZ-02: progress bar)
                processados = 0
                total = len(novos_pilares_robo)

                from PySide6.QtWidgets import QProgressBar as _QProgressBar
                _sync_progress = _QProgressBar()
                _sync_progress.setRange(0, total)
                _sync_progress.setValue(0)
                _sync_progress.setFormat("Processando %v/%m")
                _sync_progress.setStyleSheet(
                    f"QProgressBar {{ background: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_DEFAULT}; "
                    f"border-radius: 3px; text-align: center; color: {Colors.TEXT_PRIMARY}; "
                    f"font-size: {Fonts.SIZE_SM}; height: 16px; }}"
                    f"QProgressBar::chunk {{ background: {Colors.ACCENT_PRIMARY}; border-radius: 2px; }}"
                )
                # Insert progress bar at top of left_layout if available
                if hasattr(self, 'left_panel') and self.left_panel.layout():
                    self.left_panel.layout().insertWidget(0, _sync_progress)
                QApplication.processEvents()

                for idx, pilar in enumerate(novos_pilares_robo):
                    try:
                        print(f"\n[sync_pillars] === Processando pilar {idx+1}/{total}: {pilar.nome} ===")
                        
                        # PASSO 1: Definir pilar selecionado
                        print(f"  [1/4] Definindo pilar selecionado...")
                        self.robo_pilares.vm.selected_pilar = pilar
                        # Processar eventos múltiplas vezes para garantir atualização
                        for _ in range(3):
                            QApplication.processEvents()
                        
                        # PASSO 2: Aguardar UI atualizar completamente
                        print(f"  [2/4] Aguardando UI atualizar...")
                        from PySide6.QtCore import QTimer
                        # Usar QTimer para delay não-bloqueante
                        loop_count = 0
                        max_loops = 10
                        while loop_count < max_loops:
                            QApplication.processEvents()
                            loop_count += 1
                        
                        # PASSO 3: Acionar bindings automáticos
                        if hasattr(self.robo_pilares, 'form_panel'):
                            try:
                                print(f"  [3/4] Acionando cálculos automáticos...")
                                self.robo_pilares.form_panel.trigger_auto_calculations()
                                # Processar eventos múltiplas vezes após cálculos
                                for _ in range(5):
                                    QApplication.processEvents()
                                print(f"  ✅ Cálculos automáticos concluídos")
                            except Exception as e:
                                print(f"  ⚠️ Erro ao acionar cálculos automáticos: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # PASSO 4: Salvar pilar individual
                        try:
                            print(f"  [4/4] Salvando pilar...")
                            if hasattr(self.robo_pilares.vm, 'auto_save_data'):
                                self.robo_pilares.vm.auto_save_data()
                                # Processar eventos após salvar
                                for _ in range(3):
                                    QApplication.processEvents()
                                print(f"  ✅ Pilar salvo")
                            else:
                                print(f"  ⚠️ Método auto_save_data não encontrado")
                        except Exception as e:
                            print(f"  ⚠️ Erro ao salvar pilar: {e}")
                            import traceback
                            traceback.print_exc()
                        
                        processados += 1
                        _sync_progress.setValue(processados)
                        _sync_progress.setFormat(f"Processando {pilar.nome} ({processados}/{total})")
                        QApplication.processEvents()
                        print(f"  ✅✅ Pilar {pilar.nome} processado completamente ({processados}/{total})")
                        
                    except Exception as e:
                        print(f"  ❌❌ Erro ao processar pilar {pilar.nome}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                # Hide progress bar (ROBUSTEZ-02)
                _sync_progress.hide()
                _sync_progress.deleteLater()

                # Notificar mudança no pavimento após todos os pilares serem processados
                self.robo_pilares.vm.notify_property_changed("current_pavimento", self.robo_pilares.vm.current_pavimento)
                QApplication.processEvents()
                
                # Selecionar o primeiro pilar para exibição
                if novos_pilares_robo:
                    self.robo_pilares.vm.selected_pilar = novos_pilares_robo[0]
                    QApplication.processEvents()
                
                print(f"\n[sync_pillars] === PROCESSAMENTO CONCLUÍDO ===")
                print(f"  Total processado: {processados}/{count}")
                
                QMessageBox.information(
                    self, 
                    "Sincronização Concluída", 
                    f"✅ {processados} de {count} pilares sincronizados e processados com sucesso!\n\n"
                    f"Cada pilar teve:\n"
                    f"  • Cálculos automáticos executados\n"
                    f"  • Alturas distribuídas (h1-h5)\n"
                    f"  • Parafusos recalculados\n"
                    f"  • Grades atualizadas\n"
                    f"  • Dados salvos individualmente"
                )



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
        self.project_tabs.setStyleSheet(f"background: {Colors.BG_DEEP}; border: none;")
        self.project_tabs.setFixedHeight(28)
        self.project_tabs.hide()   # Oculto até que alguma aba de projeto seja aberta

        # Conectar Sinais
        self.project_tabs.currentChanged.connect(self._on_project_tab_changed)
        self.project_tabs.tabCloseRequested.connect(self._on_project_tab_close_and_hide)

        root_layout.addWidget(self.project_tabs)

        # 2. Navegação de Módulos (Abas Superiores)
        self.module_tabs = QTabBar()
        self.module_tabs.setObjectName("ModuleNav")
        self.module_tabs.setDrawBase(False)
        self.module_tabs.setStyleSheet(f"""
            QTabBar#ModuleNav::tab {{
                background: {Colors.BG_DEEP};
                color: {Colors.TEXT_SECONDARY};
                padding: 4px 16px;
                font-size: 11px;
                font-weight: 500;
                border: none;
                border-right: 1px solid {Colors.BORDER_DEFAULT};
                min-width: 60px;
                height: 28px;
            }}
            QTabBar#ModuleNav::tab:selected {{
                background: {Colors.BG_SECONDARY};
                color: {Colors.ACCENT_PRIMARY};
                border-bottom: 2px solid {Colors.ACCENT_PRIMARY};
            }}
            QTabBar#ModuleNav::tab:hover:!selected {{
                background: {Colors.BG_HOVER};
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        # Tab 0 — FASE 1
        self.module_tabs.addTab("Gerenciar Projetos")          # 0
        # Tab 1 — FASE 2
        self.module_tabs.addTab("Diagnostic Hub (Pré)")        # 1
        # Tab 2 — FASE 2.5 (Engenharia Reversa)
        self.module_tabs.addTab("Diagnostic Reverse Hub")      # 2
        # Tab 3 — FASE 3
        self.module_tabs.addTab("Structural Analyzer")         # 3
        # Tab 4 — FASES 7+8
        self.module_tabs.addTab("Comparison Engine (Pós)")     # 4
        # Tabs 5-8 — FASES 4,5,6
        self.module_tabs.addTab("Robo Pilares")                # 5
        self.module_tabs.addTab("Robo Laterais de Viga")       # 6
        self.module_tabs.addTab("Robo Fundo de Vigas")         # 7
        self.module_tabs.addTab("Robo Laje")                   # 8

        # Tooltips dos módulos
        self.module_tabs.setTabToolTip(0, "Etapa 1 — Ingestão: Cadastro de obras, importação de DXFs e documentos.")
        self.module_tabs.setTabToolTip(1, "Etapa 2 — Triagem: Separação estrutural/detalhes, recorte e limpeza de DXFs.")
        self.module_tabs.setTabToolTip(2, "Etapa 2.5 — Engenharia Reversa: Motor Reverso granular STOG→Ficha (N2), aprovação e alimentação do CE.")
        self.module_tabs.setTabToolTip(3, "Etapa 3 — Interpretação Semântica: Leitura dos DXFs limpos e geração de fichas.")
        self.module_tabs.setTabToolTip(4, "Etapas 7+8 — Validação: N1=Estrutura Real | N2=STOG Eng.Rev. | N3=Robot via Ficha SA | N4=Robot via Ficha Eng.Rev.")
        self.module_tabs.setTabToolTip(5, "Etapas 4,5,6 — Robô Pilares: gera DXF STOG para pilares (PL).")
        self.module_tabs.setTabToolTip(6, "Etapas 4,5,6 — Robô Laterais de Viga (LV): gera faces laterais em DXF STOG.")
        self.module_tabs.setTabToolTip(7, "Etapas 4,5,6 — Robô Fundo de Vigas (FV): gera fundo/sofito das vigas.")
        self.module_tabs.setTabToolTip(8, "Etapas 4,5,6 — Robô Laje (LJ): gera painéis de laje em DXF STOG.")

        # ── Faixa de Fase (acima das tabs) ──────────────────────────
        # Descreve a fase ativa para clareza do operador
        _FASE_DESCS = {
            0: "FASE 1  ·  INGESTÃO  —  Cadastro de obras, importação de DXFs e documentos estruturais",
            1: "FASE 2  ·  TRIAGEM  —  Separação estrutural/detalhes, recorte e limpeza de DXFs",
            2: "FASE 2.5  ·  ENGENHARIA REVERSA  —  Motor Reverso granular STOG→Ficha (N2) | Aprovação → alimenta CE Aba 2",
            3: "FASE 3  ·  INTERPRETAÇÃO SEMÂNTICA  —  Leitura dos DXFs limpos e geração de fichas por elemento",
            4: "FASES 7+8  ·  VALIDAÇÃO  —  N1=Estrutura Real | N2=STOG Eng.Rev. | N3=Robot via Ficha SA | N4=Robot via Ficha Eng.Rev.",
            5: "FASES 4-6  ·  GERAÇÃO GRANULAR  —  Transformação das fichas em SCR/DXF: Robô Pilares",
            6: "FASES 4-6  ·  GERAÇÃO GRANULAR  —  Transformação das fichas em SCR/DXF: Robô Laterais de Viga",
            7: "FASES 4-6  ·  GERAÇÃO GRANULAR  —  Transformação das fichas em SCR/DXF: Robô Fundo de Vigas",
            8: "FASES 4-6  ·  GERAÇÃO GRANULAR  —  Transformação das fichas em SCR/DXF: Robô Laje",
        }
        self._fase_desc_bar = QFrame()
        self._fase_desc_bar.setFixedHeight(18)
        self._fase_desc_bar.setStyleSheet(
            "background: #060e1a; border-bottom: 1px solid #0f2040;"
        )
        _fdb_lay = QHBoxLayout(self._fase_desc_bar)
        _fdb_lay.setContentsMargins(14, 0, 12, 0)
        _fdb_lay.setSpacing(0)
        self._fase_desc_label = QLabel(_FASE_DESCS.get(0, ""))
        self._fase_desc_label.setStyleSheet(
            "color: #3a7fd4; font-size: 9px; font-weight: bold; background: transparent;"
        )
        _fdb_lay.addWidget(self._fase_desc_label)
        _fdb_lay.addStretch()
        self._FASE_DESCS = _FASE_DESCS

        # Container para abas — compacto
        tabs_container = QWidget()
        tabs_container.setFixedHeight(30)
        tabs_container.setStyleSheet(
            f"background-color: {Colors.BG_DEEP}; border-bottom: 1px solid {Colors.BG_HOVER};"
        )
        t_layout = QHBoxLayout(tabs_container)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.addWidget(self.module_tabs)
        t_layout.setContentsMargins(20, 0, 0, 0)

        root_layout.addWidget(self._fase_desc_bar)
        root_layout.addWidget(tabs_container)

        # 3. Stack de Conteúdo
        self.module_stack = QStackedWidget()
        root_layout.addWidget(self.module_stack)

        # 4. Pipeline Status Bar (base da janela)
        self._pipeline_status_bar = self._build_pipeline_status_bar()
        root_layout.addWidget(self._pipeline_status_bar)

        # --- MÓDULO 0: GERENCIAR PROJETOS (Tab nova — antes era janela flutuante) ---
        self.project_manager = ProjectManager(self.db, self.memory, self.auth_service)
        self.project_manager.setWindowFlags(Qt.Widget)  # embed como widget inline
        self.project_manager.project_selected.connect(lambda pid, name, path: self._open_project_tab(pid, name))
        self.project_manager.obra_created_globally.connect(self.on_global_obra_created)
        self.project_manager.project_created_globally.connect(self.on_global_project_created)
        self.project_manager.request_tab_switch.connect(self.switch_to_tab)
        self.module_stack.addWidget(self.project_manager)   # index 0

        # --- MÓDULO 1: DIAGNOSTIC HUB (Novo) ---
        self.diagnostic_module = DiagnosticHubModule(self.db)
        self.module_stack.addWidget(self.diagnostic_module)
        # Conectar sinal de abertura de bruto direto no hub
        self.project_manager.request_open_bruto.connect(self.diagnostic_module.open_bruto)
        self.project_manager.request_open_reverse_hub.connect(self._on_open_reverse_hub)

        # Inicializar dados da sidebar
        self.diagnostic_module.sidebar.refresh()

        # Conectar Fase-3: ao concluir extração, mudar para Tab 2 e recarregar listas
        self.diagnostic_module.fase3_complete.connect(self._on_fase3_complete)

        # Conectar PreProcess: ao concluir, refreshar combos e ir para Structural Analyzer
        self.diagnostic_module.preprocess_complete.connect(self._on_preprocess_complete)

        # --- MÓDULO 2: DIAGNOSTIC REVERSE HUB (Engenharia Reversa) ---
        self.diagnostic_reverse_module = DiagnosticReverseHub()
        self.module_stack.addWidget(self.diagnostic_reverse_module)

        # --- MÓDULO 3: STRUCTURAL ANALYZER (Legacy) ---
        structural_widget = self._setup_structural_analyzer_area()
        self.module_stack.addWidget(structural_widget)

        # --- MÓDULO 4: COMPARISON ENGINE (Novo) ---
        self.comparison_module = ComparisonEngineModule()
        self.module_stack.addWidget(self.comparison_module)
        # CE-002/CE-006: conectar signals do CE ao Structural Analyzer
        self.comparison_module.analise_geral_requested.connect(
            lambda obra, pav: self.process_pillars_action()
        )
        self.comparison_module.fase4_sync_requested.connect(
            lambda obra, pav: self._run_fase4_sync()
        )
        # CE-005: CE → top bar (bidirecional, sem loop: set_obra usa blockSignals internamente)
        self.comparison_module.obra_pav_changed.connect(self._on_ce_obra_pav_changed)

        # --- MÓDULOS ROBÔS ---

        # 1. Robo Pilares (INTEGRADO)
        if create_pilares_widget:
            try:
                self.robo_pilares = create_pilares_widget(db_manager=self.db)
                self.robo_pilares.setWindowFlags(Qt.Widget)
                self._tag_robo_obra_combo(self.robo_pilares, 'robo_obra_combo_pl')
                wrapper = self._build_robo_dxf_wrapper(self.robo_pilares, 'PL', 'P', 'gerar_pl_dxf_stog.py')
                self.module_stack.addWidget(wrapper)
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
                self.robo_viga.licensing_service = self.licensing_proxy
                self.robo_viga.setWindowFlags(Qt.Widget)
                self._tag_robo_obra_combo(self.robo_viga, 'robo_obra_combo_lv')
                wrapper = self._build_robo_dxf_wrapper(self.robo_viga, 'LV', 'V', 'gerar_lv_dxf_stog.py')
                self.module_stack.addWidget(wrapper)
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
                self.robo_fundo.setWindowFlags(Qt.Widget)
                self._tag_robo_obra_combo(self.robo_fundo, 'robo_obra_combo_fv')
                wrapper = self._build_robo_dxf_wrapper(self.robo_fundo, 'FV', 'V', 'gerar_fv_dxf_stog.py')
                self.module_stack.addWidget(wrapper)
                QTimer.singleShot(200, self._setup_fv_dxf_viewer)
                QTimer.singleShot(250, self._setup_lv_dxf_viewer)

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
                self.robo_laje.setWindowFlags(Qt.Widget)
                self._tag_robo_obra_combo(self.robo_laje, 'robo_obra_combo_lj')
                wrapper = self._build_robo_dxf_wrapper(self.robo_laje, 'LJ', 'L', 'gerar_lj_dxf_stog.py')
                self.module_stack.addWidget(wrapper)
            except Exception as e:
                self.module_stack.addWidget(QLabel(f"Erro ao carregar Robo Laje: {e}"))
                self.robo_laje = None
        else:
            self.module_stack.addWidget(QLabel("Robo Laje não encontrado / Erro de importação."))
            self.robo_laje = None

        # Conectar Navegação
        self.module_tabs.currentChanged.connect(self.module_stack.setCurrentIndex)
        # Atualizar faixa de descrição de fase ao mudar de tab
        self.module_tabs.currentChanged.connect(self._on_module_tab_changed)

        # Inicializar Dados dos Combos (Obras e Pavimentos)
        QTimer.singleShot(500, self._refresh_nav_combos)

    # ─────────────────────────────────────────────
    # Robo DXF Generation Toolbar (Granular + Pavimento)
    # ─────────────────────────────────────────────

    def _tag_robo_obra_combo(self, robo_widget, obj_name: str) -> None:
        """Aplica setObjectName + setAccessibleName no combo de obra do robô.

        Busca recursivamente em sub-widgets pelos atributos conhecidos (combo_obra,
        cmb_obra, obra_combo). Fallback: combo com mais itens (maior chance de ser
        o de obras) entre os QComboBox visíveis.
        Isso permite que UIA/pywinauto encontre o combo por window_text no teste.
        """
        from PySide6.QtWidgets import QComboBox, QWidget
        combo = None

        # 1. Busca atributos conhecidos no widget raiz e em todos os sub-widgets
        ATTR_NAMES = ('combo_obra', 'cmb_obra', 'obra_combo', 'cmb_work', 'work_combo')
        for w in [robo_widget] + list(robo_widget.findChildren(QWidget)):
            for attr in ATTR_NAMES:
                c = getattr(w, attr, None)
                if isinstance(c, QComboBox):
                    combo = c
                    break
            if combo is not None:
                break

        # 2. Laje: obra_control_widget.obra_combo (caminho especial)
        if combo is None and hasattr(robo_widget, 'obra_control_widget'):
            combo = getattr(robo_widget.obra_control_widget, 'obra_combo', None)

        # 3. Fallback: combo com MAIS itens (geralmente o de obras tem 5+ itens)
        if combo is None:
            children = robo_widget.findChildren(QComboBox)
            if children:
                combo = max(children, key=lambda c: c.count())

        if combo is not None:
            combo.setObjectName(obj_name)
            combo.setAccessibleName(obj_name)

    def _setup_fv_dxf_viewer(self):
        """Substitui FundoCanvas pelo DXFVectorView no robô FV e conecta sinais."""
        if not getattr(self, 'robo_fundo', None):
            return
        try:
            from src.ui.modules.comparison_engine import DXFVectorView
        except Exception as _e:
            self.log(f"[FV Viewer] Não foi possível importar DXFVectorView: {_e}")
            return

        canvas = getattr(self.robo_fundo, 'canvas', None)
        if canvas is None:
            return

        parent = canvas.parent()
        if parent is None:
            return
        layout = parent.layout()
        if layout is None:
            return

        idx = layout.indexOf(canvas)
        canvas.setVisible(False)

        self._fv_dxf_viewer = DXFVectorView(bg='#0d1117')
        self._fv_dxf_viewer.setMinimumHeight(400)
        # idx==-1 significa canvas não é filho direto do layout; adicionar no fim
        if idx >= 0:
            layout.insertWidget(idx, self._fv_dxf_viewer, stretch=1)
        else:
            layout.addWidget(self._fv_dxf_viewer, stretch=1)

        self._fv_current_item = None

        # Seleção de item → carregar DXF N3 existente
        self.robo_fundo.item_loaded.connect(self._on_fv_item_loaded)

        # Salvar segmento → regenerar DXF com dados override
        self.robo_fundo.save_done.connect(self._on_fv_save_done)

        # Debounce: edição de campos → regenerar DXF → recarregar viewer (1.5s)
        self._fv_regen_timer = QTimer(self)
        self._fv_regen_timer.setSingleShot(True)
        self._fv_regen_timer.setInterval(1500)
        self._fv_regen_timer.timeout.connect(self._on_fv_fields_regen)

        for fw in self.robo_fundo.fields.values():
            fw.textChanged.connect(self._fv_regen_timer.start)
        for pf in getattr(self.robo_fundo, 'paineis_fields', []):
            pf.textChanged.connect(self._fv_regen_timer.start)
        for cf in getattr(self.robo_fundo, 'chanfros_fields', []):
            cf.textChanged.connect(self._fv_regen_timer.start)
        for row in getattr(self.robo_fundo, 'aberturas_fields', []):
            for af in row:
                af.textChanged.connect(self._fv_regen_timer.start)
        for lf in getattr(self.robo_fundo, 'l_fields', {}).values():
            lf.textChanged.connect(self._fv_regen_timer.start)
        for cf in getattr(self.robo_fundo, 'l_chanfros_fields', []):
            cf.textChanged.connect(self._fv_regen_timer.start)
        for row in getattr(self.robo_fundo, 'l_aberturas_fields', []):
            for af in row:
                af.textChanged.connect(self._fv_regen_timer.start)
        # Botão Atualizar → regen imediato (sem debounce)
        self.robo_fundo.regen_requested.connect(self._on_fv_fields_regen)

        self.log("[FV Viewer] DXFVectorView instalado no Robô Fundo de Vigas")

    def _setup_lv_dxf_viewer(self):
        """Conecta eventos de regeneração para o DXFVectorView do Robo Laterais de Viga."""
        if not getattr(self, 'robo_viga', None):
            return

        viewer = getattr(self.robo_viga, 'preview', None)
        if viewer is None:
            return
            
        parent = viewer.parent()
        if parent is None:
            return
        layout = parent.layout()
        if layout is None:
            return
            
        idx = layout.indexOf(viewer)
        viewer.setVisible(False)
        
        try:
            from src.ui.modules.comparison_engine import DXFVectorView
        except ImportError as _e:
            self.log(f"[LV Viewer] Não foi possível importar DXFVectorView: {_e}")
            return
            
        self.robo_viga.preview = DXFVectorView(bg='#0d1117')
        self.robo_viga.preview.setMinimumHeight(400)
        
        if idx >= 0:
            layout.insertWidget(idx, self.robo_viga.preview, stretch=1)
        else:
            layout.addWidget(self.robo_viga.preview, stretch=1)

        self._lv_current_item = None

        # Sinais da arvore
        self.robo_viga.tree1.itemSelectionChanged.connect(self._on_lv_item_loaded)
        
        self._lv_regen_timer = QTimer(self)
        self._lv_regen_timer.setSingleShot(True)
        self._lv_regen_timer.setInterval(1500)
        self._lv_regen_timer.timeout.connect(self._on_lv_fields_regen)

        for fw in self.robo_viga.fields.values():
            fw.textChanged.connect(self._lv_regen_timer.start)

        # Para painéis (tabela genérica não tem sinais diretos, então a gente pode ligar cellChanged)
        if hasattr(self.robo_viga, 'table_panels'):
            self.robo_viga.table_panels.itemChanged.connect(self._lv_regen_timer.start)

        self.log("[LV Viewer] Integração do motor N3/N4 ao Robo Laterais de Viga")

    def _on_lv_item_loaded(self):
        items = getattr(self.robo_viga, 'tree1', None).selectedItems() if getattr(self, 'robo_viga', None) else []
        if not items:
            return
        
        item = items[0]
        vdata = item.data(0, Qt.UserRole)
        if not vdata: return
        vname = vdata.get('key')
        if not vname: return
        
        # A vname pode ser 'FV-V309.C' ou 'FV-V309.C.A' (Face)
        # O script stog espera o base name, ou a face? O Robo Fundo espera 'V301'.
        self._lv_current_item = vname
        self._lv_regen_timer.stop()
        
        # The viewer will update when DXF is generated
        # Generate immediately
        self._on_lv_fields_regen()

    def _on_lv_fields_regen(self):
        if not getattr(self, 'robo_viga', None): return
        
        # O Robo Laterais já tem o modelo pendente
        items = self.robo_viga.tree1.selectedItems()
        if not items: return
        
        item = items[0]
        vdata = item.data(0, Qt.UserRole)
        if not vdata: return
        vname = vdata.get('key')
        
        obra = self.robo_viga.current_obra
        pav = self.robo_viga.current_pavimento
        if not obra or not pav: return
        
        import re as _re
        base_nome = vname
        seg_idx = vdata.get('panel_idx', -1)
        
        # Fallback if someone passed it in vname
        if '.seg' in base_nome:
            parts = base_nome.split('.seg')
            base_nome = parts[0]
            try:
                if seg_idx == -1:
                    seg_idx = int(parts[1]) - 1
            except:
                pass
                
        if '.' in base_nome:
            parts = base_nome.split('.')
            if parts[-1].upper() in ['A', 'B', 'C']:
                base_nome = '.'.join(parts[:-1])
                
        m = _re.search(r'\d+', base_nome)
        if m:
            from pathlib import Path as _Path
            self.robo_viga.save_session_data()
            self.robo_viga._do_dxf_regeneration()  # Força gerar JSON Fase-4
            
            extra_args = []
            if seg_idx >= 0:
                extra_args.extend(['--seg_idx', str(seg_idx)])
            
            # Executar STOG DXF
            self._run_robo_dxf(
                'LV', 'gerar_lv_dxf_stog.py',
                item_id=base_nome, open_canvas=False,
                extra_args=extra_args,
                _after_dxf=lambda p: self._lv_dxf_viewer_reload(base_nome, seg_idx)
            )

    def _lv_dxf_viewer_reload(self, base_nome, seg_idx=-1):
        obra = self.robo_viga.current_obra
        pav = self.robo_viga.current_pavimento
        from pathlib import Path as _Path
        
        dados_ext = _Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')
        dados_loc = _Path(self.base_dir) / 'DADOS-OBRAS'
        
        dxf_name = f"LV_preview_{base_nome}.dxf"
        if seg_idx >= 0:
            dxf_name = f"LV_preview_{base_nome}_seg{seg_idx + 1}.dxf"
            
        for root in (dados_ext, dados_loc):
            fase6 = root / obra / 'Fase-6_Execucao_CAD'
            if fase6.exists():
                dxf_path = fase6 / dxf_name
                if dxf_path.exists():
                    self.robo_viga.preview.load_dxf(str(dxf_path))
                    return
                # Fallback to load_zones (if using legacy viewer)
                if hasattr(self.robo_viga.preview, 'load_zones'):
                    self.robo_viga.preview.load_zones(str(fase6), base_nome)
                return

    def _fv_obra_atual(self) -> str:
        """Retorna a obra selecionada no robô FV (ou no combo principal como fallback)."""
        robo = getattr(self, 'robo_fundo', None)
        if robo:
            combo = getattr(robo, 'combo_obra', None)
            if combo:
                v = combo.currentText().strip()
                if v:
                    return v
        return (self.cmb_works.currentText() if hasattr(self, 'cmb_works') else '').strip()

    @staticmethod
    def _fv_parse_item(item_nome: str):
        """Retorna (base_nome, seg_idx). Ex: 'V301|seg2' → ('V301', 2); 'V301' → ('V301', -1)."""
        if '|seg' in item_nome:
            base, seg_part = item_nome.split('|seg', 1)
            try:
                return base.strip(), int(seg_part.strip())
            except ValueError:
                return item_nome, -1
        return item_nome, -1

    def _fv_override_dir(self, obra: str) -> Path:
        return Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS') / obra / 'Fase-6_Execucao_CAD' / 'fundo_override'

    def _fv_write_override_from_ui(self, obra: str, base_nome: str, seg_idx: int):
        """Escreve robot_json com TODOS os campos da UI para regeneração DXF em tempo real.

        O arquivo V{n:03d}_robot.json é passado via --robot_json ao gerador,
        que converte chanfros→vértices, aberturas→loose, painel L→loose, etc.
        """
        try:
            import re as _re, json as _js
            robo = self.robo_fundo
            dados = robo.get_current_data()
            dados['nome'] = base_nome  # garantir nome correto
            m = _re.search(r'\d+', base_nome)
            if not m:
                return
            n = int(m.group())
            override_dir = self._fv_override_dir(obra)
            override_dir.mkdir(parents=True, exist_ok=True)
            rj_path = override_dir / f'V{n:03d}_robot.json'
            rj_path.write_text(_js.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
            self.log(f'[FV] robot_json escrito: {rj_path.name}')
        except Exception as e:
            self.log(f'[FV] Erro ao escrever robot_json da UI: {e}')

    def _on_fv_save_done(self, item_nome: str):
        """Após salvar segmento/viga no robô: regenera DXF com dados do override."""
        self._fv_regen_timer.stop()
        self._fv_gerar_e_carregar(item_nome, use_override=True)

    def _on_fv_item_loaded(self, item_nome: str):
        """Ao selecionar item no robô FV: carrega DXF N3 no viewer."""
        self._fv_current_item = item_nome
        self._fv_regen_timer.stop()  # cancelar regen pendente
        obra = self._fv_obra_atual()
        if not obra:
            self.log("[FV Viewer] obra não identificada — viewer não carregado")
            return
        base_nome, seg_idx = self._fv_parse_item(item_nome)
        if seg_idx >= 0:
            dxf_fname = f'FV_preview_{base_nome}_seg{seg_idx}.dxf'
        else:
            dxf_fname = f'FV_preview_{base_nome}.dxf'
        dados_ext = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')
        dados_loc = Path(self.base_dir) / 'DADOS-OBRAS'
        for root in (dados_ext, dados_loc):
            dxf = root / obra / 'Fase-6_Execucao_CAD' / dxf_fname
            if dxf.exists():
                self.log(f"[FV Viewer] carregando {dxf.name}")
                self._fv_dxf_viewer.load_dxf(str(dxf))
                return
        # DXF não existe ainda → gerar agora
        self.log(f"[FV Viewer] DXF não encontrado para {item_nome} em {obra} — gerando")
        self._fv_gerar_e_carregar(item_nome)

    def _fv_robot_json_path(self, obra: str, base_nome: str) -> 'Path | None':
        """Retorna o caminho do robot_json se existir, None caso contrário."""
        import re as _re
        m = _re.search(r'\d+', base_nome)
        if not m:
            return None
        n = int(m.group())
        p = self._fv_override_dir(obra) / f'V{n:03d}_robot.json'
        return p if p.exists() else None

    def _fv_gerar_e_carregar(self, item_nome: str, use_override: bool = False):
        """Gera DXF N3 para o item e carrega no viewer.

        Se existir V{n:03d}_robot.json no override_dir, usa --robot_json (modo rico:
        chanfros, aberturas, painel L, sarrafos condicionais).
        Caso contrário, usa --override_dir (compatibilidade retroativa) ou Fase-4 JSON.
        """
        obra = self._fv_obra_atual()
        base_nome, seg_idx = self._fv_parse_item(item_nome)
        if obra and hasattr(self, 'cmb_works'):
            idx = self.cmb_works.findText(obra)
            if idx >= 0:
                self.cmb_works.setCurrentIndex(idx)

        extra = []
        if obra:
            rj_path = self._fv_robot_json_path(obra, base_nome) if use_override else None
            if rj_path:
                extra += ['--robot_json', str(rj_path)]
            else:
                if seg_idx >= 0:
                    extra += ['--seg_idx', str(seg_idx)]
                override_dir = self._fv_override_dir(obra)
                if use_override or override_dir.exists():
                    extra += ['--override_dir', str(override_dir)]
        else:
            if seg_idx >= 0:
                extra += ['--seg_idx', str(seg_idx)]

        self._run_robo_dxf(
            'FV', 'gerar_fv_dxf_stog.py',
            item_id=base_nome, open_canvas=False,
            _after_dxf=lambda p: self._fv_dxf_viewer.load_dxf(p),
            extra_args=extra,
        )

    def _on_fv_fields_regen(self):
        """Ao editar campos do robô FV: escreve robot_json, regera DXF e atualiza viewer."""
        item = self._fv_current_item
        if not item:
            return
        obra = self._fv_obra_atual()
        base_nome, seg_idx = self._fv_parse_item(item)

        # Sempre escreve robot_json com todos os campos (inclui chanfros, aberturas, L-panel)
        if obra:
            self._fv_write_override_from_ui(obra, base_nome, seg_idx)
            import re as _re
            m = _re.search(r'\d+', base_nome)
            if m:
                from pathlib import Path as _Path
                rj_path = self._fv_override_dir(obra) / f'V{int(m.group()):03d}_robot.json'
                if rj_path.exists():
                    self._run_robo_dxf(
                        'FV', 'gerar_fv_dxf_stog.py',
                        item_id=base_nome, open_canvas=False,
                        _after_dxf=lambda p: self._fv_dxf_viewer.load_dxf(p),
                        extra_args=['--robot_json', str(rj_path)],
                    )
                    return

        # Fallback: override_dir legacy
        extra = ['--seg_idx', str(seg_idx)] if seg_idx >= 0 else []
        if obra:
            override_dir = self._fv_override_dir(obra)
            if override_dir.exists():
                extra += ['--override_dir', str(override_dir)]
        self._run_robo_dxf(
            'FV', 'gerar_fv_dxf_stog.py',
            item_id=base_nome, open_canvas=False,
            _after_dxf=lambda p: self._fv_dxf_viewer.load_dxf(p),
            extra_args=extra,
        )

    def _build_robo_dxf_wrapper(self, robo_widget, tipo, item_prefix, script_name):
        """Envolve um widget de Robô com uma toolbar de geração DXF granular.

        Args:
            robo_widget:  O widget do Robô (Pilares/LV/FV/Laje)
            tipo:         'PL' | 'LV' | 'FV' | 'LJ'
            item_prefix:  'P' | 'V' | 'L'  (prefixo dos JSONs)
            script_name:  nome do script gerador em scripts/
        """
        from PySide6.QtWidgets import QLineEdit, QCheckBox
        container = QWidget()
        vlay = QVBoxLayout(container)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # ── Toolbar de geração ──────────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setFixedHeight(36)
        toolbar.setStyleSheet(
            "background: #0d1117; border-bottom: 1px solid #30363d;"
        )
        hlay = QHBoxLayout(toolbar)
        hlay.setContentsMargins(8, 2, 8, 2)
        hlay.setSpacing(6)

        lbl = QLabel(f"Gerar DXF [{tipo}]")
        lbl.setStyleSheet("color: #58a6ff; font-size: 10px; font-weight: bold;")
        hlay.addWidget(lbl)

        sep = QFrame(); sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #30363d;"); hlay.addWidget(sep)

        lbl_item = QLabel("Item:")
        lbl_item.setStyleSheet("color: #8b949e; font-size: 10px;")
        hlay.addWidget(lbl_item)

        item_edit = QLineEdit()
        item_edit.setPlaceholderText(f"{item_prefix}001")
        item_edit.setFixedWidth(70)
        item_edit.setFixedHeight(22)
        item_edit.setToolTip(f"ID do item para geração granular (ex: {item_prefix}001)")
        item_edit.setStyleSheet(
            "background:#161b22; color:#e6edf3; border:1px solid #30363d;"
            "border-radius:3px; padding:1px 4px; font-size:10px;"
        )
        hlay.addWidget(item_edit)

        btn_item = QPushButton("⚙ DXF Item")
        btn_item.setFixedHeight(24)
        btn_item.setToolTip(f"Gera DXF só deste item ({item_prefix}XXX) sem sobrescrever o pavimento completo")
        btn_item.setStyleSheet(
            "background:#1f6feb; color:white; border:none; border-radius:3px;"
            "padding:0 8px; font-size:10px; font-weight:bold;"
        )
        hlay.addWidget(btn_item)

        btn_pav = QPushButton("⚙⚙ DXF Pav.")
        btn_pav.setFixedHeight(24)
        btn_pav.setToolTip(f"Gera {tipo}_stog_quality.dxf com todos os itens do pavimento selecionado")
        btn_pav.setStyleSheet(
            "background:#238636; color:white; border:none; border-radius:3px;"
            "padding:0 8px; font-size:10px; font-weight:bold;"
        )
        hlay.addWidget(btn_pav)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color: #30363d;"); hlay.addWidget(sep2)

        # ── Botões SCR (abrem Fase-5 no explorador) ─────────────────────────
        btn_scr_item = QPushButton("▶ SCR Item")
        btn_scr_item.setFixedHeight(24)
        btn_scr_item.setToolTip(
            f"Abre o SCR do item gerado pelo Robô (Fase-5).\n"
            f"Use os botões 'Gerar' no painel abaixo para produzir o SCR primeiro."
        )
        btn_scr_item.setStyleSheet(
            "background:#6f42c1; color:white; border:none; border-radius:3px;"
            "padding:0 8px; font-size:10px; font-weight:bold;"
        )
        hlay.addWidget(btn_scr_item)

        btn_scr_pav = QPushButton("▶▶ SCR Pav.")
        btn_scr_pav.setFixedHeight(24)
        btn_scr_pav.setToolTip(
            f"Abre a pasta Fase-5 da obra — contém todos os SCRs gerados pelo Robô {tipo}."
        )
        btn_scr_pav.setStyleSheet(
            "background:#5a32a3; color:white; border:none; border-radius:3px;"
            "padding:0 8px; font-size:10px; font-weight:bold;"
        )
        hlay.addWidget(btn_scr_pav)

        sep3 = QFrame(); sep3.setFrameShape(QFrame.VLine)
        sep3.setStyleSheet("color: #30363d;"); hlay.addWidget(sep3)

        # Checkbox opcional: abrir preview no canvas do Tab 0
        chk_preview = QCheckBox("Abrir no canvas")
        chk_preview.setChecked(False)
        chk_preview.setToolTip(
            "Ao concluir a geração, abre o DXF gerado no canvas do Tab 0 (Diagnostic Hub)\n"
            "para visualização imediata. Não afeta o arquivo salvo."
        )
        chk_preview.setStyleSheet(
            "color:#8b949e; font-size:10px;"
            "QCheckBox::indicator { width:12px; height:12px; }"
        )
        hlay.addWidget(chk_preview)

        # Botão de índice semântico (abre dialog com summary do tipo)
        btn_sem = QPushButton("S")
        btn_sem.setFixedSize(22, 22)
        btn_sem.setToolTip("Ver índice semântico deste tipo (variedades, score médio, histórico)")
        btn_sem.setStyleSheet(
            "background:#21262d; color:#8b949e; border:1px solid #30363d;"
            "border-radius:3px; font-size:9px; font-weight:bold;"
        )
        hlay.addWidget(btn_sem)

        hlay.addStretch()

        # Label de status inline
        self._dxf_status_labels = getattr(self, '_dxf_status_labels', {})
        status_lbl = QLabel("")
        status_lbl.setObjectName(f"dxf_score_lbl_{tipo}")
        status_lbl.setStyleSheet("color:#3fb950; font-size:10px;")
        self._dxf_status_labels[tipo] = status_lbl
        hlay.addWidget(status_lbl)

        # Painel ocultado a pedido do usuário
        # vlay.addWidget(toolbar)
        vlay.addWidget(robo_widget, stretch=1)

        # ── Conexões ────────────────────────────────────────────────────────
        # Definir handler compartilhado para botão e Enter no campo
        def _trigger_dxf_item(t=tipo, s=script_name, ed=item_edit, chk=chk_preview):
            self._run_robo_dxf(t, s, item_id=ed.text().strip() or None,
                               open_canvas=chk.isChecked())

        btn_item.clicked.connect(lambda _=False: _trigger_dxf_item())
        # Enter no campo de item também dispara (UX + automação de testes)
        item_edit.returnPressed.connect(_trigger_dxf_item)
        btn_pav.clicked.connect(
            lambda _=False, t=tipo, s=script_name, chk=chk_preview:
                self._run_robo_dxf(t, s, item_id=None,
                                   open_canvas=chk.isChecked())
        )
        btn_scr_item.clicked.connect(
            lambda _=False, t=tipo, ed=item_edit:
                self._open_scr_file(t, ed.text().strip() or None)
        )
        btn_scr_pav.clicked.connect(
            lambda _=False, t=tipo:
                self._open_scr_folder(t)
        )
        btn_sem.clicked.connect(
            lambda _=False, t=tipo:
                self._show_semantic_dialog(t)
        )

        return container

    def _show_semantic_dialog(self, tipo):
        """Exibe dialog com o índice semântico do tipo selecionado.

        Mostra:
          - Summary: count, score_avg, score_min/max
          - Variedades (seção para PL, comprimento para LV/FV, área para LJ)
          - Tabela dos últimos 20 itens gerados do tipo
        """
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                        QLabel, QTableWidget, QTableWidgetItem,
                                        QPushButton, QHeaderView)
        from PySide6.QtCore import Qt

        idx_path = self._SEMANTIC_INDEX_PATH
        if not idx_path.exists():
            self.log(f"[Sem] Índice ainda vazio — gere alguns itens primeiro.")
            return

        try:
            idx = json.loads(idx_path.read_text(encoding='utf-8'))
        except Exception as _e:
            self.log(f"[Sem] Erro ao ler índice: {_e}")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Índice Semântico — {tipo}")
        dlg.resize(700, 480)
        dlg.setStyleSheet(
            "background:#0d1117; color:#e6edf3;"
            "QDialog { background:#0d1117; }"
        )
        layout = QVBoxLayout(dlg)

        # ── Summary ──────────────────────────────────────────────────────
        summary = idx.get('summary', {}).get(tipo, {})
        s_count = summary.get('count', 0)
        s_avg   = summary.get('score_avg', 0)
        s_min   = summary.get('score_min', 0)
        s_max   = summary.get('score_max', 0)

        lbl_sum = QLabel(
            f"<b>{tipo}</b>  |  {s_count} itens gerados  |  "
            f"score médio: <b>{s_avg:.1f}</b>  "
            f"(min {s_min} / max {s_max})"
        )
        lbl_sum.setStyleSheet("color:#58a6ff; font-size:11px; padding:4px;")
        layout.addWidget(lbl_sum)

        # Variedades semânticas
        varieties_str = ''
        if tipo == 'PL':
            vs = summary.get('varieties_secao', {})
            br = summary.get('b_range', [])
            varieties_str = '  '.join(f"{k}×{v}" for k, v in sorted(vs.items()))
            if br:
                varieties_str += f"  |  b={br[0]}-{br[1]}cm"
        elif tipo in ('LV', 'FV'):
            cr = summary.get('comp_range', [])
            wh = summary.get('with_holes', 0)
            varieties_str = (f"comprimento {cr[0]}-{cr[1]}cm" if cr else "")
            if wh:
                varieties_str += f"  |  {wh} com furos"
        elif tipo == 'LJ':
            ar = summary.get('area_range_cm2', [])
            varieties_str = f"área {ar[0]}-{ar[1]} cm²" if ar else ""

        if varieties_str:
            lbl_var = QLabel(f"Variedades: {varieties_str}")
            lbl_var.setStyleSheet("color:#8b949e; font-size:10px; padding:2px 4px;")
            layout.addWidget(lbl_var)

        # ── Tabela de itens recentes ─────────────────────────────────────
        items_t = [i for i in idx.get('items', []) if i.get('tipo') == tipo]
        items_t = sorted(items_t, key=lambda x: x.get('ts', ''), reverse=True)[:30]

        cols = ['ID', 'Obra', 'Semântica', 'Score', 'Missing L.', 'Extra L.', 'Data']
        table = QTableWidget(len(items_t), len(cols), dlg)
        table.setHorizontalHeaderLabels(cols)
        table.setStyleSheet(
            "QTableWidget { background:#161b22; color:#e6edf3; gridline-color:#21262d; }"
            "QHeaderView::section { background:#21262d; color:#8b949e; font-size:10px; }"
        )
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setVisible(False)

        for row, it in enumerate(items_t):
            sc   = it.get('score', {})
            sem  = it.get('sem', {})
            sem_s = self._sem_short(tipo, sem)

            def _cell(val):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                return item

            score_val = sc.get('score', 0)
            table.setItem(row, 0, _cell(it.get('id', '')))
            table.setItem(row, 1, _cell(it.get('obra', '')))
            table.setItem(row, 2, QTableWidgetItem(sem_s))
            score_cell = _cell(score_val)
            color = '#3fb950' if score_val >= 70 else '#e3b341' if score_val >= 40 else '#f85149'
            score_cell.setForeground(__import__('PySide6.QtGui', fromlist=['QColor']).QColor(color))
            table.setItem(row, 3, score_cell)
            table.setItem(row, 4, _cell(sc.get('missing_layers', '-')))
            table.setItem(row, 5, _cell(sc.get('extra_layers', '-')))
            table.setItem(row, 6, _cell(it.get('ts', '')[:16]))

        layout.addWidget(table)

        # ── Botão fechar ──────────────────────────────────────────────────
        hb = QHBoxLayout()
        hb.addStretch()
        btn_close = QPushButton("Fechar")
        btn_close.setStyleSheet(
            "background:#21262d; color:#8b949e; border:1px solid #30363d;"
            "padding:4px 16px; border-radius:3px;"
        )
        btn_close.clicked.connect(dlg.accept)
        hb.addWidget(btn_close)
        layout.addLayout(hb)

        dlg.exec()

    def _open_scr_file(self, tipo, item_id=None):
        """Abre o SCR de um item específico ou o mais recente do tipo na Fase-5."""
        import subprocess
        obra_nome = self.cmb_works.currentText() if hasattr(self, 'cmb_works') else ''
        if not obra_nome:
            self.log(f"[SCR {tipo}] Selecione uma obra primeiro.")
            return
        obra_path = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS') / obra_nome
        f5 = obra_path / 'Fase-5_Geracao_Scripts'
        if not f5.exists():
            self.log(f"[SCR {tipo}] Fase-5 não encontrada em {obra_path.name}")
            return
        # Busca SCR do item ou o mais recente do tipo
        candidates = sorted(f5.rglob(f'*{tipo}*.scr'), key=lambda p: p.stat().st_mtime, reverse=True)
        if item_id:
            # Tenta achar arquivo com o item_id no nome
            by_id = [c for c in candidates if item_id.upper() in c.stem.upper()]
            if by_id:
                candidates = by_id
        if not candidates:
            self.log(f"[SCR {tipo}] Nenhum SCR encontrado em Fase-5 para {tipo}")
            return
        scr = candidates[0]
        self.log(f"[SCR {tipo}] Abrindo: {scr.name}")
        try:
            subprocess.Popen(['notepad.exe', str(scr)])
        except Exception as _e:
            self.log(f"[SCR {tipo}] Erro ao abrir: {_e}")

    def _open_scr_folder(self, tipo):
        """Abre a pasta Fase-5 da obra no explorador."""
        import subprocess
        obra_nome = self.cmb_works.currentText() if hasattr(self, 'cmb_works') else ''
        if not obra_nome:
            self.log(f"[SCR {tipo}] Selecione uma obra primeiro.")
            return
        obra_path = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS') / obra_nome
        f5 = obra_path / 'Fase-5_Geracao_Scripts'
        target = str(f5) if f5.exists() else str(obra_path)
        self.log(f"[SCR {tipo}] Abrindo pasta: {target}")
        try:
            subprocess.Popen(['explorer.exe', target])
        except Exception as _e:
            self.log(f"[SCR {tipo}] Erro ao abrir pasta: {_e}")

    def _run_robo_dxf(self, tipo, script_name, item_id=None, open_canvas=False, _after_dxf=None, extra_args=None):
        """Executa gerar_*_dxf_stog.py via QProcess para um item ou o pavimento completo.

        Args:
            open_canvas: Se True e geração OK, abre o DXF no canvas do Tab 0 automaticamente.
        """
        import sys

        obra_nome = self.cmb_works.currentText() if hasattr(self, 'cmb_works') else ''
        if not obra_nome:
            QMessageBox.warning(self, "Gerar DXF", "Selecione uma obra na barra superior.")
            return

        # Resolver caminho da obra — prioriza DADOS-OBRAS externo (tem todas as fases)
        dados_dir_local = Path(self.base_dir) / 'DADOS-OBRAS'
        dados_dir_ext   = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')
        obra_path_local = dados_dir_local / obra_nome
        obra_path_ext   = dados_dir_ext   / obra_nome

        def _has_fase4(p):
            return (p / 'Fase-4_Sincronizacao').exists()

        # Escolher: externo com Fase-4 > local com Fase-4 > qualquer existente
        if obra_path_ext.exists() and _has_fase4(obra_path_ext):
            obra_path = obra_path_ext
        elif obra_path_local.exists() and _has_fase4(obra_path_local):
            obra_path = obra_path_local
        elif obra_path_ext.exists():
            obra_path = obra_path_ext
        elif obra_path_local.exists():
            obra_path = obra_path_local
        else:
            obra_path = obra_path_ext  # fallback para mensagem de erro legível

        if not obra_path.exists():
            QMessageBox.warning(self, "Gerar DXF", f"Caminho da obra não encontrado:\n{obra_path}")
            return

        # Limpar preview anterior para evitar arquivos órfãos
        if item_id:
            f6 = obra_path / 'Fase-6_Execucao_CAD'
            if f6.exists():
                for old_preview in f6.glob(f'{tipo}_preview_{item_id.upper()}*.dxf'):
                    try:
                        old_preview.unlink()
                        self.log(f"[DXF {tipo}] Removido preview anterior: {old_preview.name}")
                    except Exception:
                        pass

        script = Path(self.base_dir) / 'scripts' / script_name
        modo = f"item={item_id}" if item_id else "pavimento completo"
        self.log(f"[DXF {tipo}] Gerando {modo}: {obra_nome}")

        status_lbl = getattr(self, '_dxf_status_labels', {}).get(tipo)
        if status_lbl:
            # Ler _sa_meta.completude_pct antes de rodar o robô
            _sa_badge = self._get_sa_completude_badge(tipo, obra_path, item_id)
            _sa_prefix = f"SA{_sa_badge} | " if _sa_badge else ""
            status_lbl.setText(f"{_sa_prefix}Gerando {modo}...")
            status_lbl.setStyleSheet("color:#e3b341; font-size:10px;")

        from PySide6.QtCore import QProcess
        proc = QProcess(self)
        proc.setProgram(sys.executable)
        proc.setArguments(
            [str(script), '--obra', str(obra_path)] +
            (['--item', item_id] if item_id else []) +
            (extra_args or [])
        )
        proc.setWorkingDirectory(str(Path(self.base_dir)))

        def on_finish(exit_code, _exit_status):
            out = bytes(proc.readAllStandardOutput()).decode('utf-8', errors='replace')
            err = bytes(proc.readAllStandardError()).decode('utf-8', errors='replace')
            # Extrai caminho do DXF gerado da saída ("DXF: C:\...")
            dxf_path = None
            for line in out.splitlines():
                if 'DXF' in line and ':' in line:
                    candidate = line.split(':', 1)[-1].strip()
                    if candidate.endswith('.dxf') and Path(candidate).exists():
                        dxf_path = candidate
                        break

            if exit_code == 0:
                # Score estrutural inline (sem subprocess)
                score_info = self._score_preview_dxf_inline(dxf_path, tipo, obra_path, item_id=item_id) if dxf_path else None

                # Semântica do item (só para geração granular)
                sem = self._extract_item_semantics(tipo, obra_path, item_id) if item_id else {}

                # Persiste no índice semântico global
                if item_id and score_info is not None:
                    self._update_semantic_index({
                        'id': item_id, 'tipo': tipo,
                        'obra': obra_nome, 'modo': modo,
                        'sem': sem, 'score': score_info,
                    })

                # Monta label de status enriquecido
                score_txt = f"score={score_info['score']}" if score_info else "OK"
                sem_txt = self._sem_short(tipo, sem)
                ratio_txt = f"ratio={score_info['ratio']:.2f}" if score_info else ""
                sa_badge = self._get_sa_completude_badge(tipo, obra_path, item_id)
                sa_txt = f"SA{sa_badge}" if sa_badge else ""
                status_parts = [s for s in [score_txt, sem_txt, ratio_txt, sa_txt] if s]
                status_str = " | ".join(status_parts)

                self.log(f"[DXF {tipo}] {status_str}")
                if status_lbl:
                    status_lbl.setText(status_str)
                    color = "#3fb950" if (score_info and score_info['score'] >= 70) else \
                            "#e3b341" if (score_info and score_info['score'] >= 40) else "#f85149"
                    status_lbl.setStyleSheet(f"color:{color}; font-size:10px;")

                # Callback pós-geração (ex: recarregar viewer FV)
                if _after_dxf and dxf_path:
                    try:
                        _after_dxf(dxf_path)
                    except Exception as _cb_e:
                        self.log(f"[DXF {tipo}] callback _after_dxf falhou: {_cb_e}")

                # Abrir no canvas do Tab 0 (opcional)
                if open_canvas and dxf_path:
                    try:
                        self.module_tabs.setCurrentIndex(0)
                        self.load_dxf(dxf_path)
                        self.log(f"[DXF {tipo}] Preview no canvas: {Path(dxf_path).name}")
                    except Exception as _e:
                        self.log(f"[DXF {tipo}] canvas falhou: {_e}")
            else:
                self.log(f"[DXF {tipo}] ERRO (code={exit_code}): {err[:200]}")
                if status_lbl:
                    status_lbl.setText("ERRO")
                    status_lbl.setStyleSheet("color:#f85149; font-size:10px;")

        def on_error(error):
            err_names = {0:'FailedToStart', 1:'Crashed', 2:'Timedout', 4:'ReadError', 5:'WriteError', 6:'UnknownError'}
            self.log(f"[DXF {tipo}] Processo falhou: {err_names.get(error, str(error))}")
            if status_lbl:
                status_lbl.setText("ERRO")
                status_lbl.setStyleSheet("color:#f85149; font-size:10px;")

        proc.finished.connect(on_finish)
        proc.errorOccurred.connect(on_error)
        proc.start()

    # ─────────────────────────────────────────────
    # SA Inline Log (ROBUSTEZ-01)
    # ─────────────────────────────────────────────

    def _sa_log_append(self, text: str):
        """Append colorized line to the SA inline log widget."""
        if not hasattr(self, 'sa_inline_log') or self.sa_inline_log is None:
            return
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            if '[ERRO]' in stripped.upper() or 'ERROR' in stripped.upper():
                color = Colors.ACCENT_DANGER
            elif '[AVISO]' in stripped.upper() or 'WARNING' in stripped.upper():
                color = Colors.ACCENT_WARNING_ALT
            elif '[INFO]' in stripped and '✅' in stripped:
                color = Colors.ACCENT_SUCCESS
            else:
                color = Colors.TEXT_PRIMARY
            self.sa_inline_log.append(
                f'<span style="color:{color}">{stripped}</span>'
            )

    # ─────────────────────────────────────────────
    # SA Completude Badge
    # ─────────────────────────────────────────────

    def _get_sa_completude_badge(self, tipo: str, obra_path, item_id: str = None) -> str:
        """
        Lê _sa_meta.completude_pct do JSON Fase-4 correspondente ao item.
        Retorna string curta para exibição no status_lbl:
          100% → "100%✅"   ≥80% → "85%⚠"   <80% → "60%❌"
        Retorna "" se JSON não encontrado ou sem _sa_meta.
        """
        try:
            import re as _re
            f4 = Path(obra_path) / 'Fase-4_Sincronizacao'
            _dirs = {
                'PL': (f4 / 'JSON_Pilares',      'P*.json'),
                'LV': (f4 / 'JSON_Vigas_Laterais','V*_A.json'),
                'FV': (f4 / 'JSON_Vigas_Fundo',   'V*_fundo.json'),
                'LJ': (f4 / 'JSON_Lajes',         'L*.json'),
            }
            if tipo not in _dirs:
                return ""
            json_dir, glob_pat = _dirs[tipo]
            if not json_dir.exists():
                return ""

            jf = None
            if item_id:
                # Tentar match direto primeiro
                _raw = item_id.upper().replace('_A', '').replace('_B', '').replace('_FUNDO', '')
                _num_m = _re.search(r'\d+', _raw)
                if _num_m:
                    _num = int(_num_m.group())
                    for f in sorted(json_dir.glob(glob_pat)):
                        _fm = _re.search(r'\d+', f.stem)
                        if _fm and int(_fm.group()) == _num:
                            jf = f
                            break
            else:
                # Sem item_id: ler primeiro JSON disponível para mostrar completude geral
                candidates = sorted(json_dir.glob(glob_pat))
                jf = candidates[0] if candidates else None

            if not jf or not jf.exists():
                return ""

            data = json.loads(jf.read_text(encoding='utf-8'))
            meta = data.get('_sa_meta')
            if not meta:
                return "sem-SA"
            pct = meta.get('completude_pct', 0)
            if pct >= 100:
                return f"{pct:.0f}%✅"
            elif pct >= 80:
                return f"{pct:.0f}%⚠"
            else:
                return f"{pct:.0f}%❌"
        except Exception:
            return ""

    # ─────────────────────────────────────────────
    # Semantic Understanding — Score + Descriptors
    # ─────────────────────────────────────────────

    _SEMANTIC_INDEX_PATH = Path('D:/Agente-cad-PYSIDE/validacao_visual/semantic_index.json')
    _STRUCT_TYPES = {'LWPOLYLINE', 'LINE', 'DIMENSION', 'TEXT', 'MTEXT',
                     'ARC', 'CIRCLE', 'SPLINE', 'POLYLINE', 'SOLID'}

    def _score_preview_dxf_inline(self, dxf_path, tipo, obra_path, item_id=None):
        """Computa score_estrutural inline (ezdxf direto, sem subprocess).

        Modo pavimento completo (item_id=None):
          Compara gerado vs STOG via dxf_discovery.json → ratio + layer score.

        Modo item granular (item_id != None):
          Ratio contra STOG total é inválido (1 item ≠ N items).
          Usa 50pts de presença (DXF gerado com entidades) + layer_score (cobertura
          de layers contra o STOG completo). Layer_score mede se o gerador usa os
          layers corretos — é o sinal mais confiável por item.
          Max item score = 90 ("gerado corretamente, layers corretos").

        Retorna dict com score, ratio (raw), gen_struct, stog_struct, missing/extra layers.
        """
        try:
            import ezdxf as _ez
            gen_doc = _ez.readfile(str(dxf_path))
            gen_msp = gen_doc.modelspace()
            gen_struct = sum(1 for e in gen_msp if e.dxftype() in self._STRUCT_TYPES)
            gen_layers = set(e.dxf.layer for e in gen_msp)

            disc_path = obra_path.parent / 'dxf_discovery.json'
            if not disc_path.exists():
                return None
            disc = json.loads(disc_path.read_text(encoding='utf-8'))
            obra_disc = disc.get(obra_path.name, {})
            best_pav = (
                next((p for p in obra_disc if p.upper() in ('TIPO', 'TIP')), None)
                or next((p for p in obra_disc if '12' in p), None)
                or next(iter(obra_disc), None)
            )
            stog_fp = (obra_disc.get(best_pav) or {}).get(tipo) if best_pav else None
            if not stog_fp or not Path(stog_fp).exists():
                return None

            stog_doc = _ez.readfile(str(stog_fp))
            stog_msp = stog_doc.modelspace()
            stog_struct = sum(1 for e in stog_msp if e.dxftype() in self._STRUCT_TYPES)
            stog_layers = set(e.dxf.layer for e in stog_msp)

            raw_ratio = gen_struct / max(stog_struct, 1)
            missing = len(stog_layers - gen_layers)
            extra   = len(gen_layers - stog_layers)
            layer_score = max(0, 40 - missing * 3 - extra)

            if item_id:
                # Item mode: ratio inválido (1 item vs N no STOG).
                # 50pts de presença + layer_score (cobertura). Max=90.
                presence_pts = 50 if gen_struct > 0 else 0
                total_score = presence_pts + layer_score
                return {
                    'score': total_score,
                    'ratio': round(raw_ratio, 3),   # informativo apenas
                    'gen_struct': gen_struct,
                    'stog_struct': stog_struct,
                    'missing_layers': missing,
                    'extra_layers': extra,
                    'item_mode': True,
                    'presence_pts': presence_pts,
                }
            else:
                ratio_pts = (60 if 0.70 <= raw_ratio <= 1.30 else
                             40 if 0.50 <= raw_ratio <= 1.60 else
                             20 if 0.30 <= raw_ratio <= 2.00 else 5)
                return {
                    'score': ratio_pts + layer_score,
                    'ratio': round(raw_ratio, 3),
                    'gen_struct': gen_struct,
                    'stog_struct': stog_struct,
                    'missing_layers': missing,
                    'extra_layers': extra,
                    'item_mode': False,
                }
        except Exception as _e:
            self.log(f"[score_inline] {_e}")
            return None

    def _extract_item_semantics(self, tipo, obra_path, item_id):
        """Extrai descritores semânticos do JSON Fase-4 do item.
        Retorna dict com dimensões, complexidade e características estruturais.
        """
        import re as _re
        try:
            def _find_json(json_dir, glob_pat, raw_id):
                raw = raw_id.upper()
                m = _re.search(r'\d+', raw)
                num = int(m.group()) if m else -1
                prefix = _re.sub(r'\d+', '', raw)
                return next(
                    (f for f in sorted(json_dir.glob(glob_pat))
                     if _re.sub(r'\d+', '', f.stem.upper().split('_')[0]) == prefix and
                        _re.search(r'\d+', f.stem) and
                        int(_re.search(r'\d+', f.stem).group()) == num),
                    None
                )

            f4 = obra_path / 'Fase-4_Sincronizacao'

            if tipo == 'PL':
                jf = _find_json(f4 / 'JSON_Pilares', 'P*.json', item_id)
                if not jf: return {}
                d = json.loads(jf.read_text(encoding='utf-8'))
                b = float(d.get('largura', 0))
                h = float(d.get('comprimento', 0))
                alt = float(d.get('altura', 280))
                return {
                    'b': b, 'h': h, 'altura': alt,
                    'secao': f'{int(b)}x{int(h)}',
                    'area_cm2': round(b * h, 1),
                    'pavimento': d.get('pavimento', ''),
                }

            elif tipo == 'LV':
                raw_id = item_id.upper().replace('_A', '').replace('_B', '')
                jf = _find_json(f4 / 'JSON_Vigas_Laterais', 'V*_A.json', raw_id)
                if not jf: return {}
                d = json.loads(jf.read_text(encoding='utf-8'))
                panels = d.get('panels', [])
                comp = sum(float(p.get('width', 0)) for p in panels)
                return {
                    'b': float(d.get('total_width', 0)),
                    'h': float(d.get('total_height', 0)),
                    'comprimento': round(comp, 1),
                    'n_paineis': len(panels),
                    'has_holes': bool(d.get('holes')),
                    'has_pillar_left': bool(d.get('pillar_left')),
                    'has_pillar_right': bool(d.get('pillar_right')),
                }

            elif tipo == 'FV':
                raw_id = item_id.upper().replace('_FUNDO', '')
                jf = _find_json(f4 / 'JSON_Vigas_Fundo', 'V*_fundo.json', raw_id)
                if not jf: return {}
                d = json.loads(jf.read_text(encoding='utf-8'))
                panels = d.get('panels', [])
                comp = sum(float(p.get('width', 0)) for p in panels)
                return {
                    'b': float(d.get('total_width', 0)),
                    'comprimento': round(comp, 1),
                    'n_paineis': len(panels),
                    'has_holes': bool(d.get('holes')),
                }

            elif tipo == 'LJ':
                jf = _find_json(f4 / 'JSON_Lajes', 'L*.json', item_id)
                if not jf: return {}
                d = json.loads(jf.read_text(encoding='utf-8'))
                comp = float(d.get('comprimento', 0))
                larg = float(d.get('largura', 0))
                paineis = d.get('linhas_verticais', []) + d.get('linhas_horizontais', [])
                return {
                    'comprimento': comp,
                    'largura': larg,
                    'area_cm2': round(comp * larg, 1),
                    'n_linhas': len(paineis),
                    'modo': d.get('modo_selecionado', ''),
                }
        except Exception as _e:
            self.log(f"[sem] {_e}")
        return {}

    def _sem_short(self, tipo, sem):
        """Retorna string curta da semântica para o label de status."""
        if not sem: return ''
        if tipo == 'PL':
            return sem.get('secao', '')
        elif tipo in ('LV', 'FV'):
            b  = sem.get('b', 0)
            comp = sem.get('comprimento', 0)
            holes = ' furo' if sem.get('has_holes') else ''
            return f"{int(b)}x{int(comp)}cm{holes}"
        elif tipo == 'LJ':
            c = sem.get('comprimento', 0)
            l = sem.get('largura', 0)
            return f"{int(c)}x{int(l)}cm"
        return ''

    def _update_semantic_index(self, entry):
        """Persiste entry no índice semântico global e recalcula summary.

        Estratégia de crescimento:
          - Dedup por (tipo, obra, id): atualiza entry existente com novo score/sem.
            Isso garante que gerar o mesmo item novamente só atualiza, não acumula.
          - Cap global de 2000 itens (oldest-first). Cada (tipo,obra) contribui
            proporcionalmente — não há lock por tipo.
          - Summary sempre recalculado a partir dos items vigentes.

        Índice em: D:/Agente-cad-PYSIDE/validacao_visual/semantic_index.json
        Formato: { "items": [...], "summary": { "PL": {...}, ... } }
        """
        import datetime
        _MAX_ITEMS = 2000
        idx_path = self._SEMANTIC_INDEX_PATH
        try:
            idx = json.loads(idx_path.read_text(encoding='utf-8')) \
                  if idx_path.exists() else {'items': [], 'summary': {}}
        except Exception:
            idx = {'items': [], 'summary': {}}

        entry['ts'] = datetime.datetime.now().isoformat(timespec='seconds')

        # Dedup: remove entry anterior com mesmo (tipo, obra, id)
        _key = (entry.get('tipo'), entry.get('obra', ''), entry.get('id', ''))
        idx['items'] = [
            i for i in idx['items']
            if (i.get('tipo'), i.get('obra', ''), i.get('id', '')) != _key
        ]
        idx['items'].append(entry)

        # Cap global — descarta os mais antigos se ultrapassar limite
        if len(idx['items']) > _MAX_ITEMS:
            idx['items'] = idx['items'][-_MAX_ITEMS:]

        # Recalcula summary por tipo
        for t in ('PL', 'LV', 'FV', 'LJ'):
            items_t = [i for i in idx['items'] if i.get('tipo') == t]
            if not items_t:
                continue
            scores = [i['score']['score'] for i in items_t if i.get('score')]
            s = idx['summary'].get(t, {})
            s['count'] = len(items_t)
            if scores:
                s['score_avg'] = round(sum(scores) / len(scores), 1)
                s['score_min'] = min(scores)
                s['score_max'] = max(scores)
                s['score_dist'] = {
                    '0-40':  sum(1 for x in scores if x < 40),
                    '40-70': sum(1 for x in scores if 40 <= x < 70),
                    '70-100': sum(1 for x in scores if x >= 70),
                }
            # Variedades semânticas por tipo
            if t == 'PL':
                secoes = [i['sem'].get('secao', '?') for i in items_t if i.get('sem')]
                s['varieties_secao'] = {k: secoes.count(k) for k in set(secoes)}
                bs = [i['sem'].get('b', 0) for i in items_t if i.get('sem')]
                if bs:
                    s['b_range'] = [round(min(bs), 1), round(max(bs), 1)]
            elif t in ('LV', 'FV'):
                comps = [i['sem'].get('comprimento', 0) for i in items_t if i.get('sem')]
                if comps:
                    s['comp_range'] = [round(min(comps), 1), round(max(comps), 1)]
                s['with_holes'] = sum(1 for i in items_t if i.get('sem', {}).get('has_holes'))
            elif t == 'LJ':
                areas = [i['sem'].get('area_cm2', 0) for i in items_t if i.get('sem')]
                if areas:
                    s['area_range_cm2'] = [round(min(areas), 1), round(max(areas), 1)]
            idx['summary'][t] = s

        try:
            idx_path.parent.mkdir(parents=True, exist_ok=True)
            idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as _e:
            self.log(f"[sem_index] save error: {_e}")

    # ─────────────────────────────────────────────
    # Pipeline Status Bar (CAD-UI-4.1)
    # ─────────────────────────────────────────────

    def _build_pipeline_status_bar(self):
        """Barra de status de pipeline na base da janela (ETAPAº1…ETAPAº8 com checkmarks)."""
        bar = QFrame()
        bar.setFixedHeight(28)
        bar.setStyleSheet("background: #0d1117; border-top: 1px solid #21262d;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(6)

        self._lbl_pipeline_obra = QLabel("Obra: —")
        self._lbl_pipeline_obra.setStyleSheet("color: #7ab3e0; font-size: 10px; font-weight: bold;")
        lay.addWidget(self._lbl_pipeline_obra)

        sep = QFrame(); sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #333;"); lay.addWidget(sep)

        self._fase_labels = {}
        fase_names = {
            1: "ETAPAº1: Ingestão", 2: "ETAPAº2: Triagem", 3: "ETAPAº3: Interpretação",
            4: "ETAPAº4: Sincronização", 5: "ETAPAº5: Scripts", 6: "ETAPAº6: CAD",
            7: "ETAPAº7: Validação", 8: "ETAPAº8: Certificação",
        }
        for i in range(1, 9):
            lbl = QLabel(f"○ETAPAº{i}")   # ○ = etapa pendente (atualizado ao carregar obra)
            lbl.setToolTip(fase_names[i])
            lbl.setStyleSheet("color: #444; font-size: 10px; padding: 0 3px;")
            lay.addWidget(lbl)
            self._fase_labels[i] = lbl

        lay.addStretch()
        return bar

    def _refresh_pipeline_status(self, obra_path=None, work_name=None):
        """Atualiza a status bar de pipeline para a obra ativa."""
        from pathlib import Path as _Path  # noqa: already imported at top via Path

        if not obra_path and self.current_project_id and hasattr(self, 'db') and self.db:
            try:
                projects = self.db.get_projects()
                proj = next((p for p in projects if str(p.get('id')) == str(self.current_project_id)), None)
                if proj:
                    wn = proj.get('work_name', '')
                    work_name = wn
                    obra_path = str(_Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS") / wn)
            except Exception:
                pass

        if not obra_path:
            return

        self._lbl_pipeline_obra.setText(f"Obra: {work_name or _Path(obra_path).name}")

        fase_dirs = {
            1: "Fase-1_Ingestao",
            2: "Fase-2_Triagem",
            3: "Fase-3_Interpretacao_Extracao",
            4: "Fase-4_Sincronizacao",
            5: "Fase-5_Geracao_Scripts",
            6: "Fase-6_Execucao_CAD",
            7: "Fase-7_Validacao_Fidelidade",
            8: "Fase-8_Revisao_Entrega",
        }
        for fase_num, subdir in fase_dirs.items():
            lbl = self._fase_labels.get(fase_num)
            if not lbl:
                continue
            done = (_Path(obra_path) / subdir).exists()
            if done:
                lbl.setText(f"✓ETAPAº{fase_num}")
                lbl.setStyleSheet("color: #4caf50; font-size: 10px; padding: 0 3px;")
            else:
                lbl.setText(f"○ETAPAº{fase_num}")
                lbl.setStyleSheet("color: #444; font-size: 10px; padding: 0 3px;")

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
        # Tabs: 0=Pilares, 1=Lat. de Vigas, 2=Fun. de Vigas, 3=Lajes, else=All
        if index == 0:
            self.canvas.set_category_visibility('pillar')
        elif index == 1:
            self.canvas.set_category_visibility('beam')
            if hasattr(self, 'beams_found'): self.canvas.draw_beams(self.beams_found)
        elif index == 2:
            # Fun. de Vigas — realça polígonos de fundo (âmbar) no DXF
            print(f"[FV-TAB] antes set_vis: beam={len(self.canvas.item_groups.get('beam',[]))}, beam_fundo={len(self.canvas.item_groups.get('beam_fundo',[]))}, beam_visuals={len(self.canvas.beam_visuals)}")
            self.canvas.set_category_visibility('beam_fundo')
            print(f"[FV-TAB] após set_vis: beam={len(self.canvas.item_groups.get('beam',[]))}, beam_fundo={len(self.canvas.item_groups.get('beam_fundo',[]))}, beam_visuals={len(self.canvas.beam_visuals)}")
            if hasattr(self, 'beams_found'): self.canvas.draw_beam_fundos(self.beams_found)
            print(f"[FV-TAB] após draw_fundos: beam_fundo={len(self.canvas.item_groups.get('beam_fundo',[]))}")
        elif index == 3:
            self.canvas.set_category_visibility('slab')
            if hasattr(self, 'slabs_found'): self.canvas.draw_slabs(self.slabs_found)
        else:
            self.canvas.set_category_visibility('all')


    def on_focus_requested(self, field_id):
        """Tenta focar no objeto vinculado ao campo especificado via COORDENADA DIRETA"""
        if not self.current_card: return
        
        # [FIX] Se receber um objeto de link direto (do LinkManager), foca apenas nele
        if isinstance(field_id, dict):
            # É um link individual -> Highlight único
            self.canvas.highlight_link(field_id)
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
                        payload = dict(link)
                        payload['_field_id'] = field_id
                        payload['_slot_name'] = slot
                        valid_links.append(payload)
        
        if valid_links:
            # 1. Destacar o Item Pai em Amarelo (Persistente) -> REMOVIDO A PEDIDO DO CLIENTE
            # if 'id' in item_data:
            #     self.canvas.highlight_item_yellow(item_data['id'])
            
            # 2. Destacar TODOS os Links Específicos em Amarelo (Zoom no conjunto)
            self.canvas.highlight_multiple_links(valid_links)
            
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
            self.current_pick_request = dict(slot_request)
        else:
            parts = str(slot_request).split('|')
            slot_id = parts[0]
            pick_type = parts[1] if len(parts) > 1 else 'text'
            self.current_pick_request = {}
        
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
            pick_request = getattr(self, 'current_pick_request', {}) or {}
            
            item_data = self.current_card.item_data
            itype = item_data.get('type', '').lower()
            
            from PySide6.QtWidgets import QLineEdit, QComboBox, QLabel
            field = self.current_card.fields.get(field_id)
            
            value = pick_data.get('text', '')

            if isinstance(pick_request, dict) and pick_request.get('ficha_target'):
                links_dict = self.current_card.item_data.setdefault('links', {})
                field_slots = links_dict.setdefault(field_id, {})
                if isinstance(field_slots, list):
                    field_slots = {'label': field_slots}
                    links_dict[field_id] = field_slots
                target_link = None
                for lk in field_slots.get(slot_id, []) or []:
                    if isinstance(lk, dict) and lk.get('id') == pick_request.get('link_id'):
                        target_link = lk
                        break
                if target_link is not None:
                    ficha_key = pick_request.get('ficha_key')
                    target_link.setdefault('ficha_links', {}).setdefault(ficha_key, [])
                    pick_data['role'] = f"Ficha_{ficha_key}"
                    target_link['ficha_links'][ficha_key] = [pick_data]
                    if pick_data.get('text'):
                        target_link.setdefault('ficha', {})[ficha_key] = str(pick_data.get('text'))
                    elif pick_data.get('points'):
                        target_link.setdefault('ficha', {})[ficha_key] = 'Geometria vinculada'
                    if self.current_card and hasattr(self.current_card, 'embedded_managers'):
                        lm = self.current_card.embedded_managers.get(field_id)
                        if lm:
                            lm.links = field_slots
                            lm.refresh_list()
                    self.on_detail_validation_changed({'item': self.current_card.item_data, 'field_id': field_id, 'slot_id': slot_id, 'scope': 'ficha_link'})
                    self.canvas.draw_item_links(self.current_card.item_data)
                    self.log(f"Ficha do vinculo atualizada: {field_id}.{slot_id}.{ficha_key}")
                else:
                    self.log(f"⚠️ Vinculo alvo da ficha nao encontrado: {field_id}.{slot_id}")
                for attr in ('current_pick_field', 'current_pick_slot', 'current_pick_request'):
                    if hasattr(self, attr):
                        delattr(self, attr)
                return
            
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
                     lm.refresh_list(partial=True)
            
            # b) Refresh Canvas (Redesenha geometria do item)
            item_data = self.current_card.item_data
            itype = item_data.get('type','').lower()
            if 'marcodxf' in itype or 'contorno' in itype:
                self.canvas.draw_marco_dxf(item_data)
            elif 'viga' in itype:
                # Sub-itens LV/FV têm type='viga_lateral_a' etc.; para esses, não redesenhar via focus_on_beam_geometry
                if itype not in {'viga_lateral_a', 'viga_lateral_b', 'viga_fundo_c'}:
                    self.canvas.focus_on_beam_geometry(item_data, apply_zoom=False)

            # --- OVERHAUL: Lógica Inteligente para novos campos ---
            # 1. Comprimento Total (Geometria) - Campo "para"
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
            
            # 1b. Comp Total Viga Passa (seg_side_a ou seg_side_b) - Campo "passa"
            if 'comp_total_passa' in field_id and (slot_id == 'seg_side_a' or slot_id == 'seg_side_b'):
                pts = pick_data.get('points', [])
                if len(pts) >= 2:
                    # Calcular comprimento total da polyline
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
            if hasattr(self, 'current_pick_request'): delattr(self, 'current_pick_request')

    def on_element_focused_on_table(self, data):
        """Disparado quando user clica num vínculo ou viga na tabela"""
        from PySide6.QtGui import QColor
        if isinstance(data, dict):
            self.canvas.highlight_link(data)
            return
            # Se o link tem _field_id, redireciona para on_focus_requested para usar
            # item_data como fonte autoritativa (posição correta + cor via _semantic_highlight_color)
            f_id = data.get('_field_id')
            if f_id and self.current_card:
                self.on_focus_requested(f_id)
                return

            # Fallback: destaque direto do link (sem _field_id conhecido)
            color = QColor(255, 0, 0)
            if self.current_card:
                t = self.current_card.item_data.get('type', '').lower()
                _tag = str(data.get('tag', '')).lower()
                _fld = f_id.lower() if f_id else ''
                if 'fundo' in _tag or 'fundo' in _fld:
                    color = QColor(255, 120, 0)
                elif 'pilar' in t:
                    color = QColor(255, 213, 0)
                elif 'laje' in t:
                    color = QColor(0, 150, 255)
                else:
                    color = QColor(255, 213, 0)

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

    def _run_fase4_sync(self):
        """Executa motor_fase4.py — Fase-4 Sincronização (CAD-UI-3.3)."""
        if not self.current_project_id:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Fase-4", "Nenhum projeto/pavimento selecionado.")
            return

        try:
            projects = self.db.get_projects()
            proj = next((p for p in projects if str(p.get('id')) == str(self.current_project_id)), None)
            if not proj:
                return
            work_name = proj.get('work_name', '')
            pav       = proj.get('pavement_name', '1PV')
        except Exception:
            return

        from pathlib import Path
        obra_path = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS") / work_name
        script    = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/motor_fase4.py")

        if not script.exists():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Fase-4", f"Script não encontrado:\n{script}")
            return

        self.btn_fase4_sync.setEnabled(False)
        self.log(f"[Fase-4] Iniciando sincronização: {work_name} / {pav}")

        from PySide6.QtCore import QProcess
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)

        def _on_fase4_stdout():
            raw = bytes(proc.readAllStandardOutput()).decode('utf-8', 'replace').strip()
            self.log(raw)
            self._sa_log_append(raw)

        proc.readyReadStandardOutput.connect(_on_fase4_stdout)

        def on_finished(code, _):
            self.btn_fase4_sync.setEnabled(True)
            if code == 0:
                self.log(f"✅ [Fase-4] Sincronização concluída para {work_name}")
                self._sa_log_append("[INFO] ✅ Sincronização concluída")
            else:
                self.log(f"❌ [Fase-4] Erro (código {code})")
                self._sa_log_append(f"[ERRO] Fase-4 falhou (código {code})")

        proc.finished.connect(on_finished)
        proc.start(sys.executable, [str(script), "--obra", str(obra_path), "--pavimento", pav])

    def _on_preprocess_complete(self, obra_name: str):
        """Callback: PreProcessAll terminou — refreshar combos, auto-selecionar obra, ir para Structural Analyzer."""
        self.log(f"[PreProcess] {obra_name} concluído — atualizando combos e listas...")

        # 1. Refresh combos (inclui os projetos recém criados pelo worker)
        self._refresh_nav_combos()

        # 2. Auto-selecionar a obra processada no combo
        if obra_name:
            idx = self.cmb_works.findText(obra_name)
            if idx >= 0:
                # Forçar seleção — dispara _on_work_changed → popula cmb_pavements → auto-seleciona 1º pav
                self.cmb_works.setCurrentIndex(idx)
                if self.cmb_works.currentIndex() == idx:
                    # Se já estava selecionado, _on_work_changed não dispara — forçar manualmente
                    self._on_work_changed()
            else:
                self.log(f"[PreProcess] Obra '{obra_name}' não encontrada no combo após refresh")

        # 3. Ir para Structural Analyzer (Tab 3)
        self.module_tabs.setCurrentIndex(3)
        self.log(f"[PreProcess] Structural Analyzer carregado com dados de {obra_name}")

    def _on_fase3_complete(self, project_id: str):
        """Callback: Fase-3 terminou — mudar para Structural Analyzer e recarregar."""
        self.log(f"[Fase-3] Importação concluída para projeto {project_id}")

        # Navegar para Tab 3 (Structural Analyzer) automaticamente
        # module_tabs.currentChanged está conectado a module_stack.setCurrentIndex
        self.module_tabs.setCurrentIndex(3)

        # Recarregar listas — tanto para o projeto ativo quanto para projetos recém-importados
        if self.current_project_id and str(self.current_project_id) == str(project_id):
            self.refresh_lists_action()
        else:
            # Projeto diferente do ativo: tentar recarregar combos e selecionar o projeto importado
            self.log(f"[Fase-3] Sincronizando combos após importação de {project_id}")
            self._refresh_nav_combos()
            # Se ainda não há projeto ativo, refresh_lists_action usará o fallback de combo
            self.refresh_lists_action()

    def refresh_lists_action(self):
        """Recarrega os dados do banco e repovoa todas as listas da UI."""
        if not self.current_project_id:
            # Fallback: tentar forçar carregamento a partir do combo atual.
            # Necessário quando seleção foi feita via automação (UIA/pywinauto)
            # que não dispara currentIndexChanged do Qt nativamente.
            work_text = self.cmb_works.currentText()
            if work_text and not work_text.startswith('Selecione'):
                self.log(f"[Atualizar] Forçando carregamento via combo: {work_text}")
                self._on_work_changed()          # popula cmb_pavements
                if self.cmb_pavements.count() > 0:
                    self.cmb_pavements.setCurrentIndex(0)  # dispara _on_pavement_changed
                    # _on_pavement_changed é síncrono → já setou current_project_id
            if not self.current_project_id:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Aviso", "Nenhum projeto/pavimento selecionado para atualizar.")
                return

        self.log(f"🔄 Atualizando listas do projeto '{self.current_project_name}'...")

        # O load_project_action já faz:
        # 1. Sync dos robôs (se faltar algo)
        # 2. Re-query do DB principal (pillars, beams, slabs)
        # 3. Re-draw do Canvas
        # 4. Update de todas as listas na UI
        self.load_project_action()

        self.log("✅ Listas de projeto atualizadas com sucesso.")

    # ──────────────────────────────────────────────────────────────────────
    # PRÉ-PROCESSAMENTO DO PAVIMENTO (convenção de pilares do recorte detalhe)
    # ──────────────────────────────────────────────────────────────────────

    def _get_detail_cut_path(self, obra_name: str, pavimento_name: str) -> str | None:
        """Retorna o path do DXF de detalhe aprovado para obra/pavimento."""
        try:
            import sqlite3
            con = sqlite3.connect(r'D:/Agente-cad-PYSIDE/project_data.vision')
            row = con.execute(
                "SELECT output_path FROM obra_recortes "
                "WHERE obra_name=? AND pavimento_name=? AND recorte_type='detalhe' AND status='approved' "
                "ORDER BY recorte_index LIMIT 1",
                (obra_name, pavimento_name),
            ).fetchone()
            con.close()
            return row[0] if row else None
        except Exception:
            return None

    def _parse_pillar_convention(self, dxf_path: str) -> dict:
        """
        Lê o DXF de detalhe e extrai a convenção de pilares de forma genérica:
        - NÃO busca textos hardcoded (NASCE/SEGUE/MORRE).
        - Localiza o bloco de convenção pelo cabeçalho (texto contendo palavras
          estruturais como CONVENÇÃO, PILAR, LEGENDA) e coleta todos os textos
          dentro da área ao redor do bloco.
        - Para cada label encontrado, gera uma assinatura geométrica (CROSS/DIAG/EMPTY)
          analisando as linhas próximas.
        Retorna dict {label_da_prancha: {sig, diagonal_count, ...}}.
        """
        import math, re as _re, ezdxf as _ez

        # Palavras que identificam o cabeçalho da seção de convenção na prancha.
        # Genérico: qualquer projeto que tenha "CONVENÇÃO", "LEGENDA" ou "PILAR"
        # no título do bloco será reconhecido.
        HEADER_KEYWORDS = ('CONVEN', 'LEGENDA', 'CONVENTION', 'PILAR', 'PILLAR', 'SYMBOL')
        # Raio de busca ao redor de CADA label candidate para encontrar linhas vizinhas
        LABEL_LINE_R = 150.0
        # Raio ao redor do cabeçalho para encontrar labels candidatos
        HEADER_LABEL_R = 600.0
        ORTHO_TOL = 8.0

        try:
            doc = _ez.readfile(dxf_path)
        except Exception as e:
            return {'error': str(e)}

        msp = doc.modelspace()
        all_texts = []   # (text_str, pos_x, pos_y)
        all_lines = []   # {'s': (x,y), 'e': (x,y)}

        for e in msp:
            t = e.dxftype()
            if t == 'TEXT':
                try:
                    txt = e.dxf.text.strip()
                    ins = e.dxf.insert
                    all_texts.append((txt, float(ins.x), float(ins.y)))
                except Exception:
                    pass
            elif t == 'MTEXT':
                try:
                    txt = e.plain_mtext().strip()
                    ins = e.dxf.insert
                    all_texts.append((txt, float(ins.x), float(ins.y)))
                except Exception:
                    pass
            elif t == 'LINE':
                try:
                    s, en = e.dxf.start, e.dxf.end
                    all_lines.append({'s': (s.x, s.y), 'e': (en.x, en.y)})
                except Exception:
                    pass

        def dist(a, b):
            return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

        def lc(l):
            return ((l['s'][0] + l['e'][0]) / 2, (l['s'][1] + l['e'][1]) / 2)

        def angle(l):
            dx = l['e'][0] - l['s'][0]; dy = l['e'][1] - l['s'][1]
            return math.degrees(math.atan2(dy, dx)) % 180

        def geom_sig(lines_near):
            diagonals = [l for l in lines_near
                         if abs(angle(l)) > ORTHO_TOL
                         and abs(angle(l) - 90) > ORTHO_TOL
                         and abs(angle(l) - 180) > ORTHO_TOL]
            diag_angles = [round(angle(l)) for l in diagonals]
            cross = False
            parallel_diag = False
            if len(diagonals) >= 2:
                a_set = sorted(set(diag_angles))
                for i in range(len(a_set)):
                    for j in range(i + 1, len(a_set)):
                        if abs(a_set[i] + a_set[j] - 180) < 20:
                            cross = True
                if not cross and (max(diag_angles) - min(diag_angles)) < 20:
                    parallel_diag = True
            if cross:
                sig = 'CROSS'
            elif parallel_diag:
                sig = 'DIAG'
            elif not diagonals:
                sig = 'EMPTY'
            else:
                sig = f'DIAG_{len(diagonals)}'
            return sig, len(diagonals), diag_angles, cross, parallel_diag

        # 1. Localizar cabeçalho da seção de convenção
        header_pos = None
        for txt, px, py in all_texts:
            upper = txt.upper()
            if any(kw in upper for kw in HEADER_KEYWORDS):
                header_pos = (px, py)
                break

        # 2. Coletar labels candidatos ao redor do cabeçalho
        # Labels de legenda são palavras curtas (≤3 palavras) sem pontuação de heading.
        # Excluímos notas longas (frases) e cabeçalhos de seção (terminam em ':').
        if header_pos:
            def _is_legend_label(txt):
                t = txt.strip()
                if not t or len(t) <= 1:
                    return False
                if t.endswith(':') or t.endswith(')'):
                    return False
                if _re.fullmatch(r'[\d\s\.,;:\-/()]+', t):
                    return False
                words = t.split()
                if len(words) > 3:
                    return False
                # Exclui textos que começam com dígito seguido de ')' — nota numerada
                if _re.match(r'^\d+\)', t):
                    return False
                return True

            candidates = [
                (txt, px, py)
                for txt, px, py in all_texts
                if dist((px, py), header_pos) < HEADER_LABEL_R
                and not any(kw in txt.upper() for kw in HEADER_KEYWORDS)
                and _is_legend_label(txt)
            ]
        else:
            # Sem cabeçalho identificado: sem fallback hardcoded — retorna vazio com aviso
            return {'_warning': 'Cabeçalho de convenção não localizado no DXF de detalhe.'}

        # 3. Para cada label candidato, gerar assinatura geométrica
        convention = {}
        for txt, px, py in candidates:
            near = [l for l in all_lines if dist(lc(l), (px, py)) < LABEL_LINE_R]
            sig, diag_count, diag_angles, cross, parallel_diag = geom_sig(near)
            label_key = txt.strip().upper()
            convention[label_key] = {
                'label': txt.strip(),
                'label_pos': (px, py),
                'line_count': len(near),
                'diagonal_count': diag_count,
                'cross_pattern': cross,
                'parallel_diag': parallel_diag,
                'diag_angles': diag_angles,
                'sig': sig,
            }

        return convention

    def _pillar_geom_sig(self, pillar_pts: list) -> str:
        """Calcula a assinatura geométrica das linhas internas de um pilar do DXF do pavimento."""
        import math
        if not pillar_pts:
            return 'EMPTY'
        try:
            xs = [float(p[0]) for p in pillar_pts]; ys = [float(p[1]) for p in pillar_pts]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        except Exception:
            return 'EMPTY'

        MARGIN = 2.0
        ORTHO_TOL = 8.0

        def angle(l):
            dx = float(l['end'][0]) - float(l['start'][0])
            dy = float(l['end'][1]) - float(l['start'][1])
            return math.degrees(math.atan2(dy, dx)) % 180

        lines_in = []
        for l in (self.dxf_data.get('lines') or []):
            try:
                sx, sy = float(l['start'][0]), float(l['start'][1])
                ex, ey = float(l['end'][0]), float(l['end'][1])
            except Exception:
                continue
            mx, my = (sx + ex) / 2, (sy + ey) / 2
            if x0 - MARGIN <= mx <= x1 + MARGIN and y0 - MARGIN <= my <= y1 + MARGIN:
                lines_in.append(l)

        diagonals = [l for l in lines_in
                     if abs(angle(l)) > ORTHO_TOL
                     and abs(angle(l) - 90) > ORTHO_TOL
                     and abs(angle(l) - 180) > ORTHO_TOL]
        diag_angles = [round(angle(l)) for l in diagonals]

        cross = False
        parallel_diag = False
        if len(diagonals) >= 2:
            a_set = sorted(set(diag_angles))
            for i in range(len(a_set)):
                for j in range(i + 1, len(a_set)):
                    if abs(a_set[i] + a_set[j] - 180) < 20:
                        cross = True
            if not cross and (max(diag_angles) - min(diag_angles)) < 20:
                parallel_diag = True

        if cross: return 'CROSS'
        if parallel_diag: return 'DIAG'
        if not diagonals: return 'EMPTY'
        return f'DIAG_{len(diagonals)}'

    def _classify_pillar_hatch(self, pillar_pts: list, convention: dict) -> str:
        """
        Dado o polígono do pilar e a convenção extraída do detalhe,
        retorna o label exato da prancha (ex: 'NASCE', 'SEGUE', 'MORRE' ou qualquer
        outro texto que o escritório de projeto tenha usado) ou 'INDETERMINADO'.
        Não há nenhum texto hardcoded — o match é feito pela assinatura geométrica.
        """
        if not pillar_pts or not convention or '_warning' in convention or 'error' in convention:
            return 'INDETERMINADO'

        pillar_sig = self._pillar_geom_sig(pillar_pts)

        # Buscar na convenção da prancha qual label tem a mesma assinatura
        for label_key, info in convention.items():
            if isinstance(info, dict) and info.get('sig') == pillar_sig:
                return info.get('label', label_key)

        return 'INDETERMINADO'

    def _run_pavimento_preprocess(self) -> dict:
        """Extrai obra e pavimento do projeto atual via DB e roda o pré-processamento."""
        result = {'convention': {}, 'detalhe_path': None, 'obra': '', 'pavimento': ''}
        obra = ''
        pav = ''

        # Fonte primária: DB via current_project_id
        if self.current_project_id and hasattr(self, 'db') and self.db:
            try:
                projects = self.db.get_projects() or []
                proj = next((p for p in projects
                             if str(p.get('id')) == str(self.current_project_id)), None)
                if proj:
                    obra = (proj.get('work_name') or '').strip()
                    pav  = (proj.get('pavement_name') or proj.get('name') or '').strip()
            except Exception:
                pass

        # Fallback: current_project_name no formato "obra / pav" ou só "pav"
        if not obra or not pav:
            name = self.current_project_name or ''
            parts = name.split(' / ')
            if len(parts) >= 2:
                obra = obra or parts[0].strip()
                pav  = pav  or parts[1].strip()
            else:
                pav = pav or name.strip()

        result['obra'] = obra
        result['pavimento'] = pav
        if not pav:
            return result

        path = self._get_detail_cut_path(obra, pav)
        result['detalhe_path'] = path
        if path and __import__('os').path.exists(path):
            result['convention'] = self._parse_pillar_convention(path)
        return result

    def _show_convention_dialog(self, data: dict) -> dict:
        """
        Abre o diálogo moderno de Convenção de Pilares ANTES da análise.
        Retorna o term_type_map escolhido pelo usuário.
        """
        from src.ui.widgets.pre_validation_dialog import ConvencaoPilaresDialog
        from PySide6.QtWidgets import QDialog

        obra = data.get('obra') or ''
        pavimento = data.get('pavimento') or ''
        convention = data.get('convention') or {}

        _dados_root = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'DADOS-OBRAS')
        )
        convention_file: str | None = (
            os.path.join(_dados_root, obra, 'convencao_pilares.json') if obra else None
        )
        db_path = getattr(self.db, 'db_path', None)

        dlg = ConvencaoPilaresDialog(
            obra=obra,
            pavimento=pavimento,
            convention=convention,
            convention_file=convention_file,
            db_path=db_path,
            parent=self,
        )

        if dlg.exec() == QDialog.Accepted:
            result = dlg.get_result()
            return result.get('term_type_map') or {}
        return {}

    # ──────────────────────────────────────────────────────────────────────

    def process_pillars_action(self, skip_pre_validation: bool = False):
        if not self.dxf_data:
            # CAD-UI-4.3: feedback explícito — não silenciar
            self.log("⚠️ Nenhum DXF carregado. Carregue um DXF no Tab 0 (Diagnostic Hub) primeiro.")
            QMessageBox.information(
                self, "Análise Geral",
                "Nenhum arquivo DXF carregado.\n\n"
                "1. Vá para Tab 0 (Diagnostic Hub)\n"
                "2. Selecione um arquivo DXF na sidebar\n"
                "3. Volte aqui e clique em 'Iniciar Análise Geral'\n\n"
                "Alternativa: Use '▶ Interpretar DXF' (painel azul no Tab 0) para carregar dados da Fase-3."
            )
            return

        # Bloqueia qualquer reload de projeto durante a análise: processEvents() dentro
        # do loop de pilares e do AI automation de lajes podem disparar _load_project_into_view
        # ou load_project_action, que zerariam self.pillars_found antes do autosave.
        self._analysis_in_progress = True

        # ── Pré-processamento do pavimento (antes da análise pesada) ────────
        self.pavimento_preprocess = self._run_pavimento_preprocess()
        if 'term_type_map' not in self.pavimento_preprocess:
            self.pavimento_preprocess['term_type_map'] = {}
        # ──────────────────────────────────────────────────────────────────

        import uuid # Garantir import
        import re as _re_norm

        def _normalize_beam_name(name: str) -> str:
            """F.V305.C-1 → FV-V305.C | L.V305.A-1 → LV-V305.A"""
            if not name or name.startswith('FV-') or name.startswith('LV-'):
                return name
            m = _re_norm.match(r'^F\.(.+?)\.C(?:-\d+)?$', name)
            if m:
                return f'FV-{m.group(1)}.C'
            m = _re_norm.match(r'^F\.(.+?)(?:-\d+)?$', name)
            if m:
                return f'FV-{m.group(1)}.C'
            m = _re_norm.match(r'^L\.(.+?)\.([AB])(?:-\d+)?$', name)
            if m:
                return f'LV-{m.group(1)}.{m.group(2)}'
            m = _re_norm.match(r'^L\.(.+?)(?:-\d+)?$', name)
            if m:
                return f'LV-{m.group(1)}'
            return name

        # --- Snapshot de Dados Validados (Modo Incremental Automático) ---
        # Agora a análise geral SEMPRE preserva o que está validado/editado.
        # Para refazer um item do zero, o usuário deve excluí-lo da biblioteca.
        def _has_human_validation(item: dict) -> bool:
            """Validação humana REAL: is_validated OU validated_fields não-vazio.
            NUNCA usa 'links' — todo pilar tem links automáticos e isso ressuscitava
            itens obsoletos como "órfãos validados" falsos."""
            if not isinstance(item, dict):
                return False
            if item.get('is_validated'):
                return True
            vf = item.get('validated_fields')
            return bool(vf) and len(vf) > 0

        incremental = True
        preserved_pillars = {}
        preserved_beams = {}
        preserved_slabs = {}

        # Snapshot Pilares — só os com validação humana real
        for p in self.pillars_found:
             if _has_human_validation(p):
                 preserved_pillars[p.get('name')] = p

        # Snapshot Vigas (chave normalizada para migração de DB antigo F.V→FV-)
        if hasattr(self, 'beams_found'):
             for b in self.beams_found:
                 if _has_human_validation(b):
                     preserved_beams[_normalize_beam_name(b.get('name', ''))] = b

        # Snapshot Lajes
        if hasattr(self, 'slabs_found'):
             for s in self.slabs_found:
                 if _has_human_validation(s):
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
        self.list_beams_para.clear()
        self.list_beams_passa.clear()
        if hasattr(self, "list_beams_fundo"): self.list_beams_fundo.clear()
        self.list_slabs.clear()
        
        # Resetar dados internos
        self.pillars_found = []
        self.beams_found = []
        self.slabs_found = []
        
        polylines = self.dxf_data.get('polylines', [])
        texts = self.dxf_data.get('texts', [])
        lines = self.dxf_data.get('lines', [])
        # Snapshot dos textos do DXF no início da análise — garante que
        # processEvents() durante o loop de lajes não vai substituir self.dxf_data
        # e invalidar a coleta de nomes de pilares.
        self._analysis_texts = texts

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
                learned_layers = {c[0] for c in common}
                self.log(f"🧠 Aprendizado Laje: layers observadas={list(learned_layers)} (diagnostico; nao filtra N1)")
            
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

        # N2/F5 e layers aprendidas sao usados apenas como diagnostico/comparacao.
        # O N1 da Analise Geral deve detectar LAJ sem filtro duro de layer e sem
        # teacher_dims, mantendo coerencia com o loop headless de treino.
        import re as _re_nat
        def nat_key(x):
            return [int(t) if t.isdigit() else t.lower() for t in _re_nat.split(r'(\d+)', x.get('name', ''))]

        self.slabs_found = slab_tracer.detect_slabs_from_texts(
            texts,
            valid_layers=None,
            search_radius=learned_contour_radius,
            teacher_dims=None,
        )
        self.slabs_found.sort(key=nat_key)
        self.log(f"🔎 Lajes detectadas: {len(self.slabs_found)} (Busca por textos L#)")
        
        for i, s in enumerate(self.slabs_found):
             from PySide6.QtCore import QCoreApplication
             QCoreApplication.processEvents()
             
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
                 
                 # 2. Nao validado: restaura campos + links dos campos validados
                 else:
                     vf = old.get('validated_fields', [])
                     if vf:
                         s['validated_fields'] = list(vf)
                         # Restaura fields validados
                         old_fields = old.get('fields', {})
                         if 'fields' not in s:
                             s['fields'] = {}
                         for f in vf:
                             if f in old_fields:
                                 s['fields'][f] = old_fields[f]
                         # RESTAURA LINKS dos campos validados
                         old_links = old.get('links', {})
                         if 'links' not in s:
                             s['links'] = {}
                         for f in vf:
                             if f in old_links:
                                 s['links'][f] = old_links[f]

                     # Preserva validacoes humanas por slot mesmo quando o campo
                     # inteiro ainda nao foi validado. Isso e essencial para
                     # exemplos como visao de corte/pilares da laje, mesmo
                     # quando ainda nao ha validacao do campo completo.
                     old_vlc = old.get('validated_link_classes', {})
                     if isinstance(old_vlc, dict) and old_vlc:
                         s['validated_link_classes'] = dict(old_vlc)
                         old_links = old.get('links', {})
                         if 'links' not in s:
                             s['links'] = {}
                         for f, slots in old_vlc.items():
                             if f not in old_links:
                                 continue
                             if f not in s['links']:
                                 s['links'][f] = {}
                             if isinstance(old_links[f], dict):
                                 for slot in slots or []:
                                     if slot in old_links[f]:
                                         s['links'][f][slot] = old_links[f][slot]

                     old_nlc = old.get('na_link_classes', {})
                     if isinstance(old_nlc, dict) and old_nlc:
                         s['na_link_classes'] = dict(old_nlc)
                    
                     print(f"DEBUG: Laje {s['name']} re-analisada (Nao validada).")
             
             item_text = f"{s['id_item']} | {s['name']}"
             if s.get('is_validated'):
                 item_text += " ✅"

             item = QTreeWidgetItem([item_text])
             if s.get('is_validated'):
                 item.setForeground(0, Qt.green)

             item.setData(0, Qt.UserRole, s_unique_id)
             self.list_slabs.addTopLevelItem(item)

        # Preservar Lajes Validadas Órfãs
        detected_slab_names = {s['name'] for s in self.slabs_found}
        for name, old_s in preserved_slabs.items():
            if name not in detected_slab_names:
                self.slabs_found.append(old_s)
                self.log(f"🛡️ Mantendo laje validada órfã: {name}")

        self.slabs_found.sort(key=nat_key)
        
        # Reatribuir IDs posicionais limpos
        for i, s in enumerate(self.slabs_found):
             s_unique_id = f"{self.current_project_id}_l_{i+1}" if self.current_project_id else str(uuid.uuid4())
             s['id'] = s_unique_id
             s['id_item'] = f"{i+1:02}"

        self._infer_slab_levels_from_context(self.slabs_found)
        # Inventário canônico ANTES da pré-validação:
        # todo texto P# da planta entra no relatório, mesmo sem geometria.
        # Os vínculos das lajes enriquecem o inventário, mas não definem sua existência.
        self.pavimento_pillar_report = self._build_complete_pillar_report(self.slabs_found)
        # Aplica rejeições do histórico de pré-ficha antes da pré-validação
        self._apply_preficha_rejections(self.pavimento_pillar_report)
        n_report = len(self.pavimento_pillar_report)
        n_nasce = sum(1 for p in self.pavimento_pillar_report.values() if p.get('classification') == 'NASCE')
        self.log(f"📋 Relatório de pilares do pavimento: {n_report} pilar(es) detectados, {n_nasce} NASCE (a desconsiderar nas vigas/pilares).")

        # Part A — relatório consolidado de níveis
        self.pavimento_nivel_report = self._build_nivel_report(self.slabs_found, self.pavimento_pillar_report)
        nr_sum = self.pavimento_nivel_report.get('summary', {})
        n_confirms = nr_sum.get('confirmed', 0)
        n_inferred = nr_sum.get('inferred', 0)
        n_unknown = nr_sum.get('unknown', 0)
        n_hall = nr_sum.get('hallucination_suspects', 0)
        self.log(f"📐 Relatório de níveis: {n_confirms} confirmados, {n_inferred} inferidos, {n_unknown} desconhecidos" +
                 (f", {n_hall} suspeitos de alucinação" if n_hall else "") + ".")

        # ── Pré-validação interativa (Pilares + Visão de Cortes) ──────────────
        if not skip_pre_validation and not self._run_pre_validation_dialog():
            self.log("⚠ Pré-validação cancelada pelo usuário — análise interrompida.")
            self.update_progress(0, "Cancelado.")
            return

        walker = BeamWalker(self.spatial_index)
        from shapely.geometry import Polygon
        self.pillars_found = []
        temp_pillars = []
        
        from src.core.perspective_mapper import PillarPerspectiveMapper
        # === DIAGNOSTIC DUMP: SlabTracer detection analysis ===
        self._dump_slab_diagnostics()

        # 1. Motores - Vigas
        from src.core.beam_tracer import BeamTracer
        # N1 da Analise Geral precisa rodar cru, sem teacher N2 e sem parametros
        # aprendidos que possam virar atalho do gabarito. Feedback/learning fica
        # no comparador posterior e nas validacoes humanas preservadas.
        beam_tracer = BeamTracer(self.spatial_index)
        all_lines_and_polys = []
        for l in lines+polylines:
            if 'points' in l: all_lines_and_polys.append(l)
            elif 'start' in l: all_lines_and_polys.append({'points': [l['start'], l['end']]})

        self.update_progress(10, "Buscando Vigas...")

        # Coletar obstáculos visuais (Pilares e Cortes) para Fundo de Vigas
        visual_obstacles = []
        # 1. Pilares consolidados no report
        if hasattr(self, 'pavimento_pillar_report'):
            for p_name, p_data in self.pavimento_pillar_report.items():
                if p_data.get('classification') == 'NASCE' or p_data.get('is_invalid'):
                    continue
                bbox = p_data.get('bbox')
                if bbox:
                    visual_obstacles.append({'type': 'PILAR_SOLIDO', 'bbox': bbox})
        # 2. Cortes na laje validados/extraidos
        for s_item in getattr(self, 'slabs_found', []):
            cut_links = s_item.get('links', {}).get('laje_visao_corte', {}).get('cut_view_geom', [])
            for link in cut_links:
                pts = link.get('points', [])
                if pts:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    visual_obstacles.append({'type': 'VISAO_CORTE', 'bbox': (min(xs), min(ys), max(xs), max(ys))})
        self.beams_found = beam_tracer.detect_beams(texts, all_lines_and_polys, visual_obstacles=visual_obstacles)

        # Normalizar nomes: F.V305.C-1 → FV-V305.C | L.V305.A-1 → LV-V305.A
        for _b in self.beams_found:
            _b['name'] = _normalize_beam_name(_b['name'])

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
                     # Guardar links LV Para/Passa recém-gerados antes da sobrescrita
                     _fresh_lv_links = {
                         k: v for k, v in b.get('links', {}).items()
                         if ('comprimento_total' in k or 'comp_total_passa' in k) and 'viga_' in k
                     }
                     b['links'] = old.get('links', {})
                     # Injetar links LV Para/Passa que estavam ausentes ou vazios no DB antigo
                     for _lk, _lv in _fresh_lv_links.items():
                         _old_val = b['links'].get(_lk, {})
                         _old_has_data = any(bool(v) for v in _old_val.values()) if _old_val else False
                         if not _old_has_data and any(bool(v) for v in _lv.values()):
                             b['links'][_lk] = _lv
                     b['confidence_map'] = old.get('confidence_map', {})
                     b['validated_fields'] = old.get('validated_fields', [])
                     
                     # Restaura campos em geral
                     for f, v in old.items():
                         if f not in ['links', 'confidence_map', 'validated_fields', 'is_validated', 'issues']:
                            b[f] = v
                            
                     print(f"DEBUG: Viga {b['name']} restaurada (VALIDADA).")
                 
                 # 2. Nao validado: restaura campos + links dos campos validados
                 else:
                     vf = old.get('validated_fields', [])
                     if vf:
                         b['validated_fields'] = list(vf)
                         # Restaura fields validados
                         old_fields = old.get('fields', {})
                         if 'fields' not in b:
                             b['fields'] = {}
                         for f in vf:
                             if f in old_fields:
                                 b['fields'][f] = old_fields[f]
                         # RESTAURA LINKS dos campos validados
                         old_links = old.get('links', {})
                         if 'links' not in b:
                             b['links'] = {}
                         for f in vf:
                             if f in old_links:
                                 b['links'][f] = old_links[f]
                     
                     print(f"DEBUG: Viga {b['name']} re-analisada (Nao validada).")

        # 1.0a Preservar Vigas Validadas Órfãs (que sumiram do DXF)
        detected_beam_names = {b['name'] for b in self.beams_found}
        for name, old_b in preserved_beams.items():
            if name not in detected_beam_names:
                self.beams_found.append(old_b)
                self.log(f"🛡️ Mantendo viga validada órfã: {name}")

        # Reordenar para incluir as órfãs
        self.beams_found.sort(key=nat_key)
        
        # Reatribuir IDs posicionais limpos
        for i, b in enumerate(self.beams_found):
            b_unique_id = f"{self.current_project_id}_b_{i+1}" if self.current_project_id else str(uuid.uuid4())
            b['id'] = b_unique_id
            b['id_item'] = f"{i+1:02}"
            b['id_num'] = i+1
            b['project_id'] = self.current_project_id

        # 1.0b Finalizar Lista de Vigas Hierárquica
        self._populate_beam_tree(self.list_beams, self.beams_found, "lateral")
        self._populate_beam_tree(self.list_beams_fundo, self.beams_found, "fundo")
        # Sub-abas Para/Passam: limpar para populate lazy; popular a aba ativa se houver
        self.list_beams_para.clear()
        self.list_beams_passa.clear()
        if hasattr(self, '_lv_analysis_tabs'):
            _idx = self._lv_analysis_tabs.currentIndex()
            _tree = self.list_beams_para if _idx == 0 else self.list_beams_passa
            _pp   = "para"             if _idx == 0 else "passa"
            self._populate_beam_tree(_tree, self.beams_found, "lateral", _pp)

        # ── Pilares DIRIGIDOS POR NOME (name-driven) ──────────────────────────
        # Lista de pilares = nomes 'P<num>' da ÁREA DA PLANTA (1 por nome).
        # Para cada nome, resolve a geometria:
        #   (a) pré-análise (pavimento_pillar_report) com mesmo nome;
        #   (b) senão, busca a geometria perto do texto no estrutural limpo;
        #   (c) senão, entra SEM geometria, marcado p/ refino (needs_geometry).
        p_rep_all = getattr(self, 'pavimento_pillar_report', {}) or {}
        plan_names = self._collect_plan_pillar_names()
        # A pré-ficha é a fonte autoritativa após a confirmação. Inclui nomes
        # canônicos que possam ter ficado sem texto após algum ajuste de vínculo.
        for _key, _pre in p_rep_all.items():
            if str(_key).endswith('__ALT') or _pre.get('is_invalid'):
                continue
            _nm = str(_pre.get('name') or _key).strip().upper()
            if _nm:
                _anchor = _pre.get('name_positions') or []
                plan_names.setdefault(_nm, list(_anchor))
        _claimed_geom_ids: set = set()
        pillar_work_items: list = []
        _stat_report = _stat_search = _stat_nogeom = 0

        for nm in sorted(plan_names.keys(), key=lambda s: nat_key({'name': s})):
            positions = plan_names[nm]
            pre = p_rep_all.get(nm)
            if pre and pre.get('is_invalid'):
                self.log(f"🚫 Pilar {nm} removido pela decisão da pré-ficha.")
                continue
            geom_pts = None
            if pre and pre.get('points') and len(pre.get('points')) >= 3:
                geom_pts = pre['points']
                _stat_report += 1
            else:
                found_pts, found_id = self._find_pillar_geom_near_text(
                    positions, _claimed_geom_ids)
                if found_pts:
                    geom_pts = found_pts
                    _claimed_geom_ids.add(found_id)
                    _stat_search += 1
                else:
                    _stat_nogeom += 1
            pillar_work_items.append({
                'pillar_name':    nm,
                'points':         geom_pts,
                'anchor':         positions[0] if positions else None,
                'name_positions': positions,
                'pre_pillar':     pre,
                'needs_geometry': geom_pts is None,
            })

        self.log(
            f"🧱 Pilares por nome: {len(pillar_work_items)} nome(s) na planta "
            f"({_stat_report} c/ geometria da pré-análise, {_stat_search} "
            f"vinculados por proximidade, {_stat_nogeom} pendentes de geometria)."
        )

        # 2. Processar Pilares
        self.update_progress(50, "Analisando Pilares...")
        total_p = len(pillar_work_items)

        for i, work in enumerate(pillar_work_items):
            if total_p and i % 5 == 0:
                self.update_progress(50 + int((i / total_p) * 45))

            pillar_name = work['pillar_name']
            pre_pillar  = work.get('pre_pillar')
            n_rep = (getattr(self, 'pavimento_nivel_report', {}) or {}).get('pilares', {})

            # Normaliza p/ TUPLAS: geometria do report vem do JSON do DB como
            # listas [x,y], e PillarPerspectiveMapper faz set(points) (exige hashable)
            unique_points = []
            for pt in (work.get('points') or []):
                pt = tuple(pt) if isinstance(pt, (list, tuple)) else pt
                if not unique_points or pt != unique_points[-1]:
                    unique_points.append(pt)

            try:
                # ── PILAR SEM GEOMETRIA: entra na lista marcado p/ refino ──────
                if work.get('needs_geometry') or len(unique_points) < 3:
                    anchor = work.get('anchor') or (0.0, 0.0)
                    p_data = {
                        'name': pillar_name, 'type': 'Pilar',
                        'canonical_name': pillar_name, 'identity_locked': True,
                        'pos': (float(anchor[0]), float(anchor[1])),
                        'format': 'INDETERMINADO', 'area_val': 0.0, 'dim': '—',
                        'points': [], 'sides_data': {},
                        'links': {}, 'neighbors': [], 'beams_visual': [],
                        'material': 'C30', 'level': 'Pavimento 1',
                        'needs_geometry': True, 'fields': {},
                    }
                    if pre_pillar:
                        p_data['classification'] = pre_pillar.get('classification', 'INDETERMINADO')
                        p_data['physical_type'] = pre_pillar.get('physical_type', 'unknown')
                        p_data['lajes_adjacentes'] = list(pre_pillar.get('lajes') or [])
                        p_data['preficha_reviewed'] = True
                    p_data['issues'] = ['⚠ Geometria não localizada — refino pendente']
                    temp_pillars.append(p_data)
                    continue

                poly_shape = Polygon(unique_points)
                if not poly_shape.is_valid:
                    from shapely.validation import make_valid
                    poly_shape = make_valid(poly_shape)

                if poly_shape.geom_type == 'MultiPolygon':
                    poly_shape = max(poly_shape.geoms, key=lambda g: g.area)

                if poly_shape.geom_type != 'Polygon':
                    continue

                from src.core.perspective_mapper import PillarPerspectiveMapper
                shape_type, orient = PillarPerspectiveMapper.identify_shape(unique_points)

                p_data = {
                    'name': pillar_name,
                    'canonical_name': pillar_name,
                    'identity_locked': True,
                    'type': 'Pilar',
                    'pos': (poly_shape.centroid.x, poly_shape.centroid.y),
                    'format': shape_type,
                    'area_val': poly_shape.area,
                    'dim': f"{int(poly_shape.area)}cm²",
                    'points': list(poly_shape.exterior.coords),
                    'sides_data': PillarPerspectiveMapper.map_sides(unique_points, shape_type, orient),
                    'links': {
                        'pilar_segs': {
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

                # --- ENRIQUECIMENTO COM DADOS DA PRÉ-ANÁLISE ---
                cx, cy = poly_shape.centroid.x, poly_shape.centroid.y
                
                # 2. Dimensões do Pilar (Largura x Comprimento)
                minx, miny, maxx, maxy = poly_shape.bounds
                bw = round(maxx - minx, 1)
                bl = round(maxy - miny, 1)
                bw = int(bw) if abs(bw - int(bw)) < 0.1 else bw
                bl = int(bl) if abs(bl - int(bl)) < 0.1 else bl
                dimensao_pilar = f"{min(bw, bl)}x{max(bw, bl)}"
                if 'fields' not in p_data: p_data['fields'] = {}
                p_data['fields']['Dimensão (b x h)'] = dimensao_pilar
                
                if pre_pillar:
                    if pre_pillar.get('name') and pre_pillar['name'] != pillar_name:
                        pillar_name = pre_pillar['name']
                        p_data['name'] = pillar_name
                    
                    p_data['classification'] = pre_pillar.get('classification', 'INDETERMINADO')
                    p_data['physical_type'] = pre_pillar.get('physical_type', 'unknown')
                    p_data['preficha_reviewed'] = True
                    
                    # 3. Vincular Lajes Respectivas aos Lados e suas Alturas
                    adj_lajes = pre_pillar.get('lajes', [])
                    if adj_lajes:
                        p_data['lajes_adjacentes'] = adj_lajes
                        
                        laje_str = ", ".join(set([l['laje'] for l in adj_lajes]))
                        if 'connections' not in p_data['links']: p_data['links']['connections'] = {}
                        p_data['links']['connections']['lajes_conectadas'] = {
                            'value': laje_str,
                            'details': adj_lajes
                        }
                        
                        # Extrair detalhes lado a lado e Nível Mais Alto
                        highest_level = -99999.0
                        highest_level_str = None
                        lajes_details = []
                        
                        for l in adj_lajes:
                            s_name = l['laje']
                            s_side = l.get('side', '?')
                            s_h = ""
                            s_lvl_str = ""
                            for sl in getattr(self, 'slabs_found', []):
                                if sl['name'] == s_name:
                                    s_h = sl.get('height', '') or sl.get('dim', '')
                                    s_lvl_str = sl.get('nivel_str', '')
                                    try:
                                        lvl_val = float(s_lvl_str.replace(',', '.'))
                                        if lvl_val > highest_level:
                                            highest_level = lvl_val
                                            highest_level_str = s_lvl_str
                                    except Exception:
                                        pass
                                    break
                            
                            lajes_details.append(f"Lado {s_side}: {s_name}" + (f" (H={s_h})" if s_h else ""))
                        
                        p_data['fields']['Lajes por Face'] = " | ".join(lajes_details)
                        
                        # Definir Nível do Pilar pelo nível mais alto da laje que toca ele
                        if highest_level_str:
                            p_data['level'] = highest_level_str
                            p_data['fields']['Nível (Via Laje)'] = highest_level_str
                        else:
                            if pillar_name in n_rep:
                                p_data['level'] = str(n_rep[pillar_name].get('level_str') or 'Pavimento 1')
                else:
                    if pillar_name in n_rep:
                        p_data['level'] = str(n_rep[pillar_name].get('level_str') or 'Pavimento 1')

                # 4. Dimensão das Vigas que Chegam (Isso vai definir aberturas)
                from shapely.geometry import Polygon, LineString
                arriving_beams = []
                for beam in getattr(self, 'beams_found', []):
                    b_pts = beam.get('points') or (beam.get('geometry', {}).get('poly') if isinstance(beam.get('geometry'), dict) else None) or []
                    if len(b_pts) >= 2:
                        try:
                            b_shape = Polygon(b_pts) if len(b_pts) > 2 else LineString(b_pts)
                            if poly_shape.intersects(b_shape) or poly_shape.distance(b_shape) < 2.0:
                                b_name = beam.get('name', 'V?')
                                b_dim = beam.get('fields', {}).get('dimensao') or beam.get('dim', '')
                                arriving_beams.append(f"{b_name} ({b_dim})" if b_dim else b_name)
                        except Exception:
                            pass
                
                if arriving_beams:
                    p_data['fields']['Vigas Conectadas (Aberturas)'] = ", ".join(arriving_beams)
                    if 'connections' not in p_data['links']: p_data['links']['connections'] = {}
                    p_data['links']['connections']['vigas_conectadas'] = {
                        'value': ", ".join(arriving_beams),
                        'details': arriving_beams
                    }
                # ------------------------------------------------
                # ------------------------------------------------
                
                # --- FORÇAR VÍNCULOS REAIS DA PRÉ-FICHA ---
                # Evita alucinações de coordenadas e garante sincronia com o estrutural original
                if pre_pillar:
                    pts = pre_pillar.get('points')
                    if pts:
                        p_data['points'] = pts
                        if 'links' not in p_data: p_data['links'] = {}
                        p_data['links']['pilar_segs'] = {
                            'segments': [{'type': 'poly', 'points': pts, 'text': 'Geometria (Pré-Ficha)'}]
                        }
                        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                        pw = round(max(xs) - min(xs), 1); pl = round(max(ys) - min(ys), 1)
                        pw = int(pw) if abs(pw - int(pw)) < 0.1 else pw
                        pl = int(pl) if abs(pl - int(pl)) < 0.1 else pl
                        real_dim = f"{min(pw, pl)}x{max(pw, pl)}"
                        p_data['dim'] = real_dim
                        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2

                        best_dim_txt = None
                        for txt_ent in (self.dxf_data.get('texts', []) if self.dxf_data else []):
                            t = str(txt_ent.get('text', '')).replace(" ", "").lower()
                            if t == real_dim.lower():
                                tx = txt_ent.get('pos', [0, 0])[0]
                                ty = txt_ent.get('pos', [0, 0])[1]
                                if (tx - cx) ** 2 + (ty - cy) ** 2 < 4000000:
                                    best_dim_txt = txt_ent
                                    break
                        if best_dim_txt:
                            pts_txt = best_dim_txt.get('pos') or best_dim_txt.get('points', [])
                            if pts_txt and not isinstance(pts_txt[0], (list, tuple)): pts_txt = [pts_txt]
                            p_data['links']['dim'] = {'label': [{'type': 'text', 'text': best_dim_txt['text'], 'points': pts_txt, 'bbox': best_dim_txt.get('bbox')}]}
                        else:
                            p_data['links']['dim'] = {'label': [{'type': 'text', 'text': real_dim, 'points': [(cx, cy)], 'bbox': (cx, cy, cx, cy)}]}

                        real_name = pre_pillar.get('name')
                        if real_name:
                            p_data['name'] = real_name
                            pillar_name = real_name
                            best_txt = None
                            for txt_ent in (self.dxf_data.get('texts', []) if self.dxf_data else []):
                                if str(txt_ent.get('text', '')) == real_name:
                                    tx = txt_ent.get('pos', [0, 0])[0]
                                    ty = txt_ent.get('pos', [0, 0])[1]
                                    if (tx - cx) ** 2 + (ty - cy) ** 2 < 4000000:
                                        best_txt = txt_ent
                                        break
                            if best_txt:
                                pts_txt = best_txt.get('pos') or best_txt.get('points', [])
                                if pts_txt and not isinstance(pts_txt[0], (list, tuple)): pts_txt = [pts_txt]
                                p_data['links']['name'] = {'label': [{'type': 'text', 'text': best_txt['text'], 'points': pts_txt, 'bbox': best_txt.get('bbox')}]}
                            else:
                                p_data['links']['name'] = {'label': [{'type': 'text', 'text': real_name, 'points': [(cx, cy)], 'bbox': (cx, cy, cx, cy)}]}

                        if 'confidence_map' not in p_data: p_data['confidence_map'] = {}
                        p_data['confidence_map']['name'] = 1.0
                        p_data['confidence_map']['pilar_segs'] = 1.0
                        p_data['confidence_map']['dim'] = 1.0

                # Identidade é definida pelo inventário P# e confirmada na pré-ficha.
                # O analisador contextual pode enriquecer os demais campos, mas não
                # pode trocar P26 por um texto P# vizinho.
                _name_positions = work.get('name_positions') or []
                if _name_positions:
                    _np = _name_positions[0]
                    p_data.setdefault('links', {})['name'] = {
                        'label': [{
                            'type': 'text', 'text': pillar_name,
                            'points': [tuple(_np)], 'pos': tuple(_np),
                            'role': 'Identificador Pilar Canônico',
                        }]
                    }
                    p_data.setdefault('confidence_map', {})['name'] = 1.0

                # Análise Contextual (Initial)
                if self.pillar_analyzer:
                    self.pillar_analyzer.analyze(p_data)

                p_data['issues'] = self._run_sanity_checks(p_data)
                temp_pillars.append(p_data)

            except Exception as e:
                self.log(f"⚠️ Erro no pilar {work.get('pillar_name', i)}: {e}")

        _n_pend = sum(1 for p in temp_pillars if p.get('needs_geometry'))
        self.log(
            f"🧱 Pilares montados: {len(temp_pillars)} "
            f"({len(temp_pillars) - _n_pend} com geometria, {_n_pend} pendentes de refino)."
        )

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
                 
                 # 2. Nao validado: restaura campos + links dos campos validados
                 else:
                     vf = old.get('validated_fields', [])
                     if vf:
                         p_data['validated_fields'] = list(vf)
                         # Restaura fields validados
                         old_fields = old.get('fields', {})
                         if 'fields' not in p_data:
                             p_data['fields'] = {}
                         for f in vf:
                             if f in old_fields:
                                 p_data['fields'][f] = old_fields[f]
                         # RESTAURA LINKS dos campos validados
                         old_links = old.get('links', {})
                         if 'links' not in p_data:
                             p_data['links'] = {}
                         for f in vf:
                             if f in old_links:
                                 p_data['links'][f] = old_links[f]
                     
                     print(f"DEBUG: Pilar {p_data['name']} re-analisado (Nao validado).")

            self.pillars_found.append(p_data)

        # Preservar Pilares Validados Órfãos (só com validação humana real)
        detected_pillar_names = {p['name'] for p in self.pillars_found}
        for name, old_p in preserved_pillars.items():
            if name not in detected_pillar_names and _has_human_validation(old_p):
                self.pillars_found.append(old_p)
                self.log(f"🛡️ Mantendo pilar validado órfão: {name}")

        # Reordenar para incluir os órfãos
        self.pillars_found.sort(key=nat_key)
        
        # Reatribuir IDs
        for i, p in enumerate(self.pillars_found):
            unique_id = f"{self.current_project_id}_p_{i+1}" if self.current_project_id else str(uuid.uuid4())
            p['id'] = unique_id
            p['id_item'] = f"{i+1:02}"

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
        self._auto_sync_beams_to_laterais_silent()
        try:
            obra_f7 = self.cmb_works.currentText() if hasattr(self, "cmb_works") else ""
            pav_f7 = self._current_pavement_name() if hasattr(self, "cmb_pavements") else ""
            if self.current_project_id and hasattr(self.db, "save_fase3_fichas"):
                n_f7 = self.db.save_fase3_fichas(
                    self.current_project_id,
                    obra_f7,
                    pav_f7,
                    {
                        "PIL": self.pillars_found,
                        "LV": getattr(self, "beams_found", []),
                        "LAJ": getattr(self, "slabs_found", []),
                    },
                )
                self.log(f"F7/N1 materializada em fase3_fichas: {n_f7} ficha(s).")
        except Exception as ex:
            self.log(f"Erro ao materializar F7/N1: {ex}")
        try:
            if self.current_project_id:
                # ===== PRÉ-SAVE: merge DB → memória (2ª camada de proteção) =====
                # O DELETE abaixo invalida a proteção dentro de save_slab (que lê o DB
                # antes de salvar). Esta etapa garante que qualquer dado validado
                # humanamente que esteja no DB mas ausente na memória seja resgatado
                # ANTES do apagamento, indexando por NOME de laje/pilar/viga.
                try:
                    import sqlite3 as _sq3
                    _conn_bk = self.db._get_conn()
                    _conn_bk.row_factory = _sq3.Row
                    # Lajes
                    _slab_map = {s.get('name'): s for s in getattr(self, 'slabs_found', []) if s.get('name')}
                    for _row in _conn_bk.execute(
                        "SELECT name, validated_fields_json, validated_link_classes_json, "
                        "is_validated, links_json, na_link_classes_json "
                        "FROM slabs WHERE project_id=? "
                        "AND (is_validated=1 OR length(COALESCE(validated_fields_json,'[]'))>2 "
                        "     OR length(COALESCE(validated_link_classes_json,'{}'))>2)",
                        (self.current_project_id,)
                    ):
                        _tgt = _slab_map.get(_row['name'])
                        if not _tgt:
                            continue
                        if _row['is_validated'] and not _tgt.get('is_validated'):
                            _tgt['is_validated'] = True
                            _old_lk = json.loads(_row['links_json'] or '{}')
                            if _old_lk and not _tgt.get('links'):
                                _tgt['links'] = _old_lk
                        _db_vf = json.loads(_row['validated_fields_json'] or '[]')
                        if _db_vf:
                            _cur_vf = set(_tgt.get('validated_fields') or [])
                            _tgt['validated_fields'] = list(_cur_vf | set(_db_vf))
                        _db_vlc = json.loads(_row['validated_link_classes_json'] or '{}')
                        if isinstance(_db_vlc, dict) and _db_vlc:
                            _cur_vlc = _tgt.setdefault('validated_link_classes', {})
                            for _f, _slots in _db_vlc.items():
                                _s = _cur_vlc.setdefault(_f, [])
                                for _sl in (_slots or []):
                                    if _sl not in _s:
                                        _s.append(_sl)
                    # Pilares
                    _pil_map = {p.get('name'): p for p in getattr(self, 'pillars_found', []) if p.get('name')}
                    for _row in _conn_bk.execute(
                        "SELECT name, data_json FROM pillars WHERE project_id=?",
                        (self.current_project_id,)
                    ):
                        _tgt = _pil_map.get(_row['name'])
                        if not _tgt:
                            continue
                        try:
                            _pd = json.loads(_row['data_json'] or '{}')
                        except Exception:
                            continue
                        if _pd.get('is_validated') and not _tgt.get('is_validated'):
                            _tgt['is_validated'] = True
                        _db_vf = _pd.get('validated_fields', [])
                        if _db_vf:
                            _cur_vf = set(_tgt.get('validated_fields') or [])
                            _tgt['validated_fields'] = list(_cur_vf | set(_db_vf))
                    _conn_bk.close()
                except Exception as _e_bk:
                    self.log(f"⚠ Pré-save merge DB→mem: {_e_bk}")
                # ===== FIM PRÉ-SAVE =========================================

                # Salva primeiro e remove obsoletos somente após todos os UPSERTs.
                # Assim uma falha intermediária não deixa o projeto vazio.
                for p in getattr(self, 'pillars_found', []):
                    self.db.save_pillar(p, self.current_project_id)
                for s in getattr(self, 'slabs_found', []):
                    self.db.save_slab(s, self.current_project_id)
                try:
                    n_lj_json, n_lj_el = self._materialize_slabs_for_n1_n3_and_robo()
                    if n_lj_json:
                        self.log(f"🧩 Lajes SA→N1/N3/Robo: {n_lj_json} JSON_Lajes e {n_lj_el} slab_elements atualizados.")
                    if getattr(self, 'robo_laje', None):
                        # Backup antes do AI automation: processEvents() dentro pode zerar pillars_found
                        _pil_bak = list(self.pillars_found)
                        _slb_bak = list(self.slabs_found)
                        print(f"[GUARD] backup pré-sync: {len(_pil_bak)} pilares", flush=True)
                        self.sync_slabs_to_robo_laje_action(
                            confirm=False,
                            switch_to_tab=False,
                            run_ai=True,
                        )
                        # Restaura se processEvents() zerou durante o AI automation
                        if not self.pillars_found and _pil_bak:
                            self.pillars_found = _pil_bak
                            print(f"[GUARD] pillars_found restaurado pós-sync: {len(self.pillars_found)} pilares", flush=True)
                        if not self.slabs_found and _slb_bak:
                            self.slabs_found = _slb_bak
                except Exception as _e_lj_mat:
                    self.log(f"⚠️ Falha ao propagar lajes SA→N1/N3/Robo: {_e_lj_mat}")
                try:
                    from scripts.analise_geral_headless import process_beam_fv, upsert_beam_element_fv

                    # FASE 1: Processar dados FV e atualizar links em memória (sem acesso ao DB)
                    _fv_results = []
                    for b in getattr(self, 'beams_found', []):
                        fv_data = process_beam_fv(b, getattr(self, 'spatial_index', None), visual_obstacles)

                        if 'links' not in b:
                            b['links'] = {}

                        is_h = b.get('is_h', True)
                        b_pos = b.get('pos', [0, 0])
                        h_beam = fv_data.get('h_n1') or 20.0
                        half_h = h_beam / 2.0

                        segs = fv_data.get('segmentos_fundo', [])
                        print(f"Beam {b.get('name')} FV segments: {len(segs)}")

                        def _is_good_fv_contour(link):
                            if not isinstance(link, dict):
                                return False
                            if link.get('validated'):
                                return True
                            pts = link.get('points') or []
                            uniq = []
                            for pt in pts:
                                if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                                    continue
                                xy = (round(float(pt[0]), 3), round(float(pt[1]), 3))
                                if xy not in uniq:
                                    uniq.append(xy)
                            if len(uniq) < 4:
                                return False
                            xs = [p[0] for p in uniq]
                            ys = [p[1] for p in uniq]
                            min_x, max_x = min(xs), max(xs)
                            min_y, max_y = min(ys), max(ys)
                            if (max_x - min_x) <= 1.0 or (max_y - min_y) <= 1.0:
                                return False
                            tol = 2.0
                            corners = [
                                (min_x, min_y), (max_x, min_y),
                                (max_x, max_y), (min_x, max_y),
                            ]
                            return all(
                                any(abs(px - cx) <= tol and abs(py - cy) <= tol for px, py in uniq)
                                for cx, cy in corners
                            )

                        for seg in segs:
                            idx = seg.get('seg_index')
                            p_min, p_max = None, None
                            _coord = seg.get('coord')
                            if _coord is not None:
                                p_min, p_max = _coord

                            if idx and p_min is not None and p_max is not None:
                                if is_h:
                                    geom = [
                                        [p_min, b_pos[1] - half_h],
                                        [p_max, b_pos[1] - half_h],
                                        [p_max, b_pos[1] + half_h],
                                        [p_min, b_pos[1] + half_h]
                                    ]
                                else:
                                    geom = [
                                        [b_pos[0] - half_h, p_min],
                                        [b_pos[0] + half_h, p_min],
                                        [b_pos[0] + half_h, p_max],
                                        [b_pos[0] - half_h, p_max]
                                    ]
                                link_key = f"viga_fundo_seg_{idx}_area_segs"
                                if link_key not in b['links']:
                                    b['links'][link_key] = {}
                                # Não sobrescreve contour já populada por _process_beam_intelligent
                                existing_contour = b['links'][link_key].get('contour', [])
                                good_contour = next(
                                    (lk for lk in existing_contour if _is_good_fv_contour(lk)),
                                    None
                                )
                                if not good_contour:
                                    b['links'][link_key]['contour'] = [{
                                        'points': geom,
                                        'type': 'polygon',
                                        'tag': 'Fundo',
                                        'ficha': seg.get('ficha', {}),
                                        'len': seg.get('length'),
                                    }]
                                    print(f" -> Added {link_key} contour (bbox fallback) to Beam {b.get('name')}")
                                else:
                                    _ficha = dict(good_contour.get('ficha') or {})
                                    _ficha.update(seg.get('ficha') or {})
                                    good_contour['ficha'] = _ficha
                                    good_contour['tag'] = good_contour.get('tag') or 'Fundo'
                                    good_contour['len'] = good_contour.get('len') or seg.get('length')
                                    b['links'][link_key]['contour'] = [good_contour]
                                    print(f" -> Kept existing {link_key} contour for Beam {b.get('name')}")

                                field_prefix = f"viga_fundo_seg_{idx}"
                                b.setdefault('fields', {})
                                if seg.get('dim_text'):
                                    b['fields'][f'{field_prefix}_dim'] = seg.get('dim_text')
                                    if seg.get('dim_link'):
                                        b['links'][f'{field_prefix}_dim'] = {'label': [seg.get('dim_link')]}
                                if seg.get('apoio_inicial'):
                                    b['fields'][f'{field_prefix}_local_ini'] = seg.get('apoio_inicial')
                                    if seg.get('apoio_inicial_link'):
                                        b['links'][f'{field_prefix}_local_ini'] = {'label': [seg.get('apoio_inicial_link')]}
                                if seg.get('apoio_final'):
                                    b['fields'][f'{field_prefix}_local_fim'] = seg.get('apoio_final')
                                    if seg.get('apoio_final_link'):
                                        b['links'][f'{field_prefix}_local_fim'] = {'label': [seg.get('apoio_final_link')]}

                        _fv_results.append(fv_data)

                    # FASE 2: Salvar todos os beams (cada save_beam abre/fecha sua própria conexão)
                    for b in getattr(self, 'beams_found', []):
                        self.db.save_beam(b, self.current_project_id)

                    # FASE 3: Upsert FV na tabela headless (única conexão, sem conflito)
                    import sqlite3 as _sq3
                    with _sq3.connect(self.db.db_path) as _fv_conn:
                        for fv_data in _fv_results:
                            upsert_beam_element_fv(_fv_conn, self.current_project_id, fv_data["viga_nome"], fv_data["panels_n1"], fv_data)

                    try:
                        from pathlib import Path as _Path
                        from scripts.motor_fase4 import MotorFase4
                        _obra_nome = self.cmb_works.currentText() if hasattr(self, "cmb_works") else ""
                        _pav_nome = self._current_pavement_name() if hasattr(self, "_current_pavement_name") else ""
                        _obra_path = _Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS") / _obra_nome
                        _m4 = MotorFase4(str(_obra_path), pavimento=_pav_nome)
                        _n_fv_json = _m4._write_fv_json_from_beam_elements({})
                        if _n_fv_json:
                            self.log(f"🧩 Fundos SA→N1/N3/Robo: {_n_fv_json} JSON_Vigas_Fundo atualizados.")
                    except Exception as _e_fv_f4:
                        self.log(f"⚠ Falha ao materializar FV SA→N3/Robo: {_e_fv_f4}")

                except Exception as _fv_err:
                    import traceback
                    print(f"⚠ Erro ao popular dados Fundo de Viga: {_fv_err}")
                    print(traceback.format_exc())
                    self.log(f"⚠ Erro ao popular dados Fundo de Viga: {_fv_err}")
                    for b in getattr(self, 'beams_found', []):
                        self.db.save_beam(b, self.current_project_id)

                # Limpeza pós-save, em uma única transação. Só é alcançada quando
                # as três coleções já foram persistidas com sucesso/fallback.
                _conn_clean = self.db._get_conn()
                try:
                    for _table, _items in (
                        ('pillars', getattr(self, 'pillars_found', [])),
                        ('slabs', getattr(self, 'slabs_found', [])),
                        ('beams', getattr(self, 'beams_found', [])),
                    ):
                        _ids = [str(x.get('id')) for x in _items if x.get('id')]
                        if _ids:
                            _marks = ','.join('?' for _ in _ids)
                            _conn_clean.execute(
                                f"DELETE FROM {_table} WHERE project_id=? "
                                f"AND id NOT IN ({_marks})",
                                [self.current_project_id, *_ids],
                            )
                        else:
                            _conn_clean.execute(
                                f"DELETE FROM {_table} WHERE project_id=?",
                                (self.current_project_id,),
                            )
                    _conn_clean.commit()
                except Exception:
                    _conn_clean.rollback()
                    raise
                finally:
                    _conn_clean.close()
                
                self.log(
                    "💾 Autosave Análise Geral: "
                    f"{len(getattr(self, 'pillars_found', []))} pilares, "
                    f"{len(getattr(self, 'slabs_found', []))} lajes e "
                    f"{len(getattr(self, 'beams_found', []))} vigas salvos."
                )
        except Exception as ex:
            self.log(f"❌ Erro no autosave da Análise Geral: {ex}")
        print(f"[ANALISE] concluída: PL={len(self.pillars_found)} BM={len(getattr(self,'beams_found',[]))} SL={len(getattr(self,'slabs_found',[]))}", flush=True)
        self.log(f"Análise finalizada: {len(self.pillars_found)} Pilares, {len(self.beams_found)} Vigas e {len(self.slabs_found)} Lajes.")
        self.btn_save.setEnabled(True)
        self._analysis_texts = None  # Limpa snapshot para não vazar para próxima análise
        self._analysis_in_progress = False  # Libera reloads de projeto

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
        override_type = item.data(0, Qt.UserRole + 1)
        tipo_comp = item.data(0, Qt.UserRole + 2)  # 'para' ou 'passa', somente para LV
        if not beam_id: return # Clicou no nó pai
        beam = next((b for b in self.beams_found if b['id'] == beam_id), None)
        if beam:
            self.show_detail(beam, override_type=override_type, tipo_comp=tipo_comp)
            # 1. Isolar no Canvas (Esconde todas as outras e mostra apenas esta)
            self.canvas.isolate_item(beam_id, 'beam', apply_zoom=False)

            # Para sub-itens LV-A/LV-B, não chamar focus_on_beam_geometry (desenha tudo em marrom)
            # e usar display_data (com type correto) para filtragem no draw_item_links
            _is_lv = override_type in {'viga_lateral_a', 'viga_lateral_b'}
            _is_fv = override_type == 'viga_fundo_c'
            if not (_is_lv or _is_fv):
                self.canvas.focus_on_beam_geometry(beam)
                self.canvas.draw_item_links(beam)
            elif _is_lv:
                # draw_single_beam_lateral: desenha links filtrados + rótulos Segmento-NN
                if self.current_card:
                    self.canvas.draw_single_beam_lateral(self.current_card.item_data, beam)
            else:
                # FV: draw_item_links usa type do current_card.item_data
                if self.current_card:
                    self.canvas.draw_item_links(self.current_card.item_data)

    def _on_lv_analysis_subtab_changed(self, idx: int):
        """Popula lazy a sub-aba LV ativa (Para=0 / Passa=1) ao primeiro clique."""
        tree = self.list_beams_para if idx == 0 else self.list_beams_passa
        pp   = "para"             if idx == 0 else "passa"
        if not tree.topLevelItemCount() and hasattr(self, "beams_found") and self.beams_found:
            self._populate_beam_tree(tree, self.beams_found, "lateral", pp)

    def on_list_beam_fundo_clicked(self, item, column=0):
        """Clique em item da lista Fun. de Vigas: destaca APENAS o fundo desta viga + zoom."""
        if not item:
            return
        beam_id = item.data(0, Qt.UserRole)
        if not beam_id:
            return  # nó pai (grupo)
        beam = next((b for b in self.beams_found if b['id'] == beam_id), None)
        if beam:
            self.show_detail(beam, override_type='viga_fundo_c')
            self.canvas.draw_single_beam_fundo(beam, apply_zoom=True)

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

    # --- AUTO-SYNC ROBOTS LOGIC ---
    def _read_robot_pilares_data(self, pav_nome):
        path = os.path.join(self.base_dir, "_ROBOS_ABAS", "Robo_Pilares", "pilares-atualizado-09-25", "src", "core", "pilares_salvos.json")
        if not os.path.exists(path): return []
        try:
            with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
            items = []
            target = pav_nome.upper()
            
            for key, val in data.items():
                # A chave costuma ser Obra_Pavimento_Numero (ex: "22_Subsolo_1")
                if target in key.upper():
                    d = val.get('dados', val)
                    if isinstance(d, dict):
                        # Garantir ID único baseado na chave original se o objeto não tiver
                        d["id"] = val.get('id', key)
                        d["type"] = "Pilar (Robô)"
                        # Normalizar nome - GARANTIR STRING
                        name_val = d.get("name") or d.get("nome") or (f"P{d.get('numero')}" if d.get('numero') else str(key))
                        d["name"] = str(name_val)
                        
                        items.append(d)
            return items
        except Exception as e:
            print(f"Error reading robot pilares: {e}")
            return []

    def _read_robot_lajes_data(self, pav_nome):
        items = []
        seen_names = set()
        
        # 1. Caminhos para busca: Projetos e Global (AppData)
        paths = []
        
        # Global AppData
        app_data_path = os.path.join(os.environ.get("APPDATA", ""), "LajesApp", "obras.json")
        if os.path.exists(app_data_path):
            paths.append(app_data_path)
            
        # Projects Repo
        repo_base = os.path.join(self.base_dir, "projects_repo")
        if os.path.exists(repo_base):
            for project_id in os.listdir(repo_base):
                p_path = os.path.join(repo_base, project_id, "laje_data", "obras.json")
                if os.path.exists(p_path): paths.append(p_path)
        
        target_pav = pav_nome.upper()
        
        for p_path in paths:
            try:
                with open(p_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # A estrutura do obras.json de lajes costuma ser:
                # {"obras": [{"name": "...", "pavimentos": [{"nome": "...", "lajes": [...]}]}]}
                obras = data.get("obras", []) if isinstance(data, dict) else []
                
                for obra in obras:
                    for pav in obra.get("pavimentos", []):
                        p_nome = str(pav.get("nome", "")).upper()
                        # Debug Log para rastrear mismatch
                        if "P-1" in target_pav or "P-1" in p_nome:
                             print(f"[DEBUG SYNC] Comparando '{target_pav}' com '{p_nome}'")
                             
                        if target_pav in p_nome or p_nome in target_pav:
                            lajes_list = pav.get("lajes", [])
                            if lajes_list:
                                print(f"[DEBUG SYNC] Encontrado {len(lajes_list)} lajes para pavimento '{p_nome}'")
                            for laje in lajes_list:
                                if isinstance(laje, dict):
                                    name = laje.get('nome', laje.get('name'))
                                    if not name:
                                        name = f"L_{len(items)+1}"
                                    
                                    if name not in seen_names:
                                        laje["type"] = "Laje (Robô)"
                                        laje["name"] = str(name)
                                        # Garantir ID único (Obras.json de lajes pode não ter UUIDs)
                                        if not laje.get("id"):
                                             laje["id"] = f"LAJE_{obra.get('name')}_{pav.get('nome')}_{name}"
                                        items.append(laje)
                                        seen_names.add(name)
            except Exception as e:
                print(f"Error reading robot laje file {p_path}: {e}")
                continue
        return items

    def _read_robot_laterais_data(self, pav_nome):
        path = os.path.join(self.base_dir, "_ROBOS_ABAS", "Robo_Laterais_de_Vigas", "dados_vigas_ultima_sessao.json")
        if not os.path.exists(path): return []
        try:
            with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
            items = []
            target = pav_nome.upper()
            def scan_dict_recursive(current_dict):
                for key, value in current_dict.items():
                    if isinstance(value, dict):
                        if target in key.upper():
                            if 'vigas' in value and isinstance(value['vigas'], list):
                                for item in value['vigas']:
                                    if isinstance(item, dict): 
                                        item["type"] = "Viga Lateral (Robô)"
                                        items.append(item)
                        scan_dict_recursive(value)
                    elif isinstance(value, list) and target in str(key).upper():
                        for item in value:
                            if isinstance(item, dict):
                                item["type"] = "Viga Lateral (Robô)"
                                items.append(item)
            if isinstance(data, dict): scan_dict_recursive(data)
            return items
        except: return []

    def _read_robot_fundos_data(self, pav_nome):
        path = os.path.join(self.base_dir, "_ROBOS_ABAS", "Robo_Fundos_de_Vigas", "compactador-producao", "fundos_salvos.json")
        if not os.path.exists(path): return []
        try:
            with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
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
            return items
        except: return []


    def _process_with_reverse_engineering(self):
        """Consultar e utilizar fichas N2 existentes como base de conhecimento."""
        from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QPushButton, QTextEdit, QFrame
        import sqlite3
        import json
        import os
        import glob
        from src.core.ficha_utils import canonical_pavimento, ficha_id

        obra_nome = self.cmb_works.currentText() if hasattr(self, "cmb_works") else ""
        if (not obra_nome or obra_nome == 'Selecionar Obra...') and hasattr(self, "sa_cmb_obras"):
            obra_nome = self.sa_cmb_obras.currentText()
        pavimento_nome = self._current_pavement_name() if hasattr(self, "cmb_pavements") else ""
        if (not pavimento_nome or pavimento_nome == 'Selecionar Pavimento...') and hasattr(self, "sa_cmb_pavimentos"):
            data = self.sa_cmb_pavimentos.currentData()
            if isinstance(data, tuple) and len(data) > 1:
                pavimento_nome = data[1]
            else:
                pavimento_nome = self.sa_cmb_pavimentos.currentText()
        pavimento_db = canonical_pavimento(pavimento_nome) if pavimento_nome else ""

        if not obra_nome or obra_nome == 'Selecionar Obra...':
            QMessageBox.warning(self, 'Aviso', 'Selecione uma obra.')
            return

        # === ETAPA 1: BUSCAR FICHAS N2 ===
        self.log(f"🔍 Consultando fichas N2 para obra '{obra_nome}', pavimento '{pavimento_nome}'...")

        db_path = getattr(getattr(self, "db", None), "db_path", 'D:/Agente-cad-PYSIDE/project_data.vision')
        n2_report = {
            'PIL': {'fichas': 0, 'recortes': 0, 'com_dims': 0},
            'FV':  {'fichas': 0, 'recortes': 0, 'com_dims': 0},
            'LV':  {'fichas': 0, 'recortes': 0, 'com_dims': 0},
            'LAJ': {'fichas': 0, 'recortes': 0, 'obras_json': 0, 'com_coords': 0},
        }
        obra_ficha_info = None
        n2_available = False
        # N1 (Structural Analyzer / Fº7) — fichas, validados e SEGMENTOS por classe (4 classes)
        # Viga: 1 ficha FV + 1 ficha LV por viga; segmentos divergem (fundo=seg_bottom; lateral=seg_side_a+b).
        n1_report = {
            'PIL': {'label': 'Pilares',        'total': 0, 'validados': 0, 'segmentos': 0},
            'FV':  {'label': 'Vigas Fundo',    'total': 0, 'validados': 0, 'segmentos': 0},
            'LV':  {'label': 'Vigas Laterais', 'total': 0, 'validados': 0, 'segmentos': 0},
            'LAJ': {'label': 'Lajes',          'total': 0, 'validados': 0, 'segmentos': 0},
        }

        try:
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                c = conn.cursor()

                # 1a. reverse_eng_recortes - contagem por classe, apenas recortes validados
                query_rec = (
                    "SELECT classe, COUNT(*) FROM reverse_eng_recortes "
                    "WHERE (obra_name=? OR obra_name='') "
                    "AND status IN ('aprovado','auto_aprovado','approved')"
                )
                params = [obra_nome]
                if pavimento_db:
                    import re as _re_pav
                    rec_like = f"%{pavimento_db}%"
                    raw_like = f"%{pavimento_nome}%"
                    n_match = _re_pav.search(r"(\d+)_PAV", pavimento_db)
                    num_like = f"%{n_match.group(1)}%PAV%" if n_match else rec_like
                    query_rec += " AND (recorte_path LIKE ? OR recorte_path LIKE ? OR recorte_path LIKE ? OR projeto_id LIKE ?)"
                    params.extend([rec_like, raw_like, num_like, rec_like])
                query_rec += " GROUP BY classe"
                c.execute(query_rec, params)
                for row in c.fetchall():
                    cls = row[0]
                    if cls in n2_report:
                        n2_report[cls]['recortes'] = row[1]

                # 1b. reverse_eng_fichas - contagem por classe
                query_fic = "SELECT classe, COUNT(*) FROM reverse_eng_fichas WHERE obra_name=?"
                params_fic = [obra_nome]
                if pavimento_db:
                    query_fic += " AND pavimento=?"
                    params_fic.append(pavimento_db)
                query_fic += " GROUP BY classe"
                c.execute(query_fic, params_fic)
                for row in c.fetchall():
                    cls = row[0]
                    if cls in n2_report:
                        n2_report[cls]['fichas'] = row[1]
                        n2_available = True

                # 1c. Verificar granularidade - quantas fichas tem dims
                for cls in n2_report:
                    q_dims = "SELECT campos_json FROM reverse_eng_fichas WHERE obra_name=? AND classe=?"
                    p_dims = [obra_nome, cls]
                    if pavimento_db:
                        q_dims += " AND pavimento=?"
                        p_dims.append(pavimento_db)
                    c.execute(q_dims, p_dims)
                    for r in c.fetchall():
                        try:
                            campos = json.loads(r[0]) if r[0] else {}
                            if campos.get('b') or campos.get('h') or campos.get('total_width'):
                                n2_report[cls]['com_dims'] += 1
                        except:
                            pass

                # 1d. reverse_eng_obra_ficha - ficha geral da obra
                c.execute("SELECT total_pil, total_lv, total_fv, total_laj, confianca_media, resumo_json FROM reverse_eng_obra_ficha WHERE obra_name=?", [obra_nome])
                row = c.fetchone()
                if row:
                    obra_ficha_info = {
                        'total_pil': row[0], 'total_lv': row[1], 'total_fv': row[2],
                        'total_laj': row[3], 'confianca': row[4]
                    }
                    n2_available = True

                # 1f. N1 (Fº7) — itens salvos e validados por classe (estado persistido do pavimento)
                # PIL←pillars, LAJ←slabs. FV e LV derivam de `beams` (a viga N1 contém fundo+laterais).
                _pid = getattr(self, 'current_project_id', None)
                if _pid:
                    def _count_tbl(_tbl):
                        try:
                            c.execute(
                                f"SELECT COUNT(*), COALESCE(SUM(CASE WHEN is_validated=1 THEN 1 ELSE 0 END), 0) "
                                f"FROM {_tbl} WHERE project_id=?", [str(_pid)]
                            )
                            _rr = c.fetchone()
                            return (_rr[0] or 0, _rr[1] or 0) if _rr else (0, 0)
                        except Exception:
                            return (0, 0)
                    n1_report['PIL']['total'], n1_report['PIL']['validados'] = _count_tbl('pillars')
                    n1_report['LAJ']['total'], n1_report['LAJ']['validados'] = _count_tbl('slabs')
                    # Vigas: 1 ficha FV + 1 ficha LV por viga (split persistido em beam_elements).
                    # Sincroniza o split a partir dos beams persistidos (idempotente, derivado — não toca beams).
                    try:
                        if hasattr(self, "db") and hasattr(self.db, "materialize_beam_elements"):
                            self.db.materialize_beam_elements(_pid)
                    except Exception:
                        pass
                    try:
                        c.execute(
                            "SELECT classe, COUNT(*), COALESCE(SUM(n_segmentos),0), "
                            "COALESCE(SUM(CASE WHEN is_validated=1 THEN 1 ELSE 0 END),0) "
                            "FROM beam_elements WHERE project_id=? AND classe IN ('FV','LV') GROUP BY classe",
                            [str(_pid)]
                        )
                        for _cls, _n, _seg, _val in c.fetchall():
                            if _cls in ('FV', 'LV'):
                                n1_report[_cls]['total'] = _n
                                n1_report[_cls]['segmentos'] = _seg
                                n1_report[_cls]['validados'] = _val
                    except Exception:
                        pass

                conn.close()
        except Exception as e:
            self.log(f"❌ Erro ao consultar fichas N2: {e}")

        # 1e. Verificar obras.json (lajes com coordenadas)
        projects_repo = os.path.join(os.path.dirname(__file__), "projects_repo")
        obras_json_found = None
        for obras_path in glob.glob(os.path.join(projects_repo, "*", "laje_data", "obras.json")):
            try:
                with open(obras_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for obra in data.get("obras", []):
                    for pav in obra.get("pavimentos", []):
                        lajes = pav.get("lajes", [])
                        for laje in lajes:
                            if laje.get("coordenadas"):
                                n2_report['LAJ']['com_coords'] += 1
                        n2_report['LAJ']['obras_json'] += len(lajes)
                if n2_report['LAJ']['obras_json'] > 0 and not obras_json_found:
                    obras_json_found = obras_path
            except:
                pass

        if n2_report['LAJ']['obras_json'] > 0:
            n2_available = True

        # === ETAPA 2: RELATÓRIO ===
        report_lines = []
        report_lines.append(f"🔍 RELATÓRIO DE FICHAS N2\n")
        report_lines.append(f"Obra: {obra_nome}")
        report_lines.append(f"Pavimento: {pavimento_nome or 'Todos'}\n")

        if obra_ficha_info:
            report_lines.append(f"📊 Ficha da Obra (global):")
            report_lines.append(f"  Pilares: {obra_ficha_info['total_pil']}")
            report_lines.append(f"  Vigas Laterais: {obra_ficha_info['total_lv']}")
            report_lines.append(f"  Vigas Fundo: {obra_ficha_info['total_fv']}")
            report_lines.append(f"  Lajes: {obra_ficha_info['total_laj']}")
            report_lines.append(f"  Confiança média: {obra_ficha_info['confianca']:.1%}\n")

        report_lines.append("📋 Fichas Granulares N2:")
        for cls, label in [('PIL', 'Pilares'), ('FV', 'Vigas Fundo'), ('LV', 'Vigas Laterais'), ('LAJ', 'Lajes')]:
            info = n2_report[cls]
            if cls == 'LAJ':
                report_lines.append(f"  {label}: {info['fichas']} fichas, {info['recortes']} recortes, {info['obras_json']} no obras.json ({info['com_coords']} com coordenadas)")
            else:
                report_lines.append(f"  {label}: {info['fichas']} fichas, {info['recortes']} recortes ({info['com_dims']} com dims)")

        report_lines.append("")
        for cls, label in [('PIL', 'Pilares'), ('FV', 'Vigas Fundo'), ('LV', 'Vigas Laterais'), ('LAJ', 'Lajes')]:
            f4_id = ficha_id("F4", obra_nome, pavimento_db or pavimento_nome or "GERAL", cls)
            report_lines.append(f"ID F4 {label}: {f4_id}")
        report_lines.append(f"ID F6 Obra ER: {ficha_id('F6', obra_nome)}")
        report_lines.append(f"ID F7/N1 alvo: {ficha_id('F7', obra_nome, pavimento_db or pavimento_nome or 'GERAL', 'CLASSE', 'ITEM')}")

        # Verificar ficha do pavimento por classe
        report_lines.append("\n🏠 Ficha do Pavimento por Classe:")
        for cls, label in [('PIL', 'Pilares'), ('FV', 'Vigas Fundo'), ('LV', 'Vigas Laterais'), ('LAJ', 'Lajes')]:
            has_pav_ficha = n2_report[cls]['fichas'] > 0 or n2_report[cls]['recortes'] > 0
            status = "✅ Encontrada" if has_pav_ficha else "❌ Não encontrada"
            report_lines.append(f"  {label}: {status}")

        if not n2_available:
            report_lines.append("\n⚠️ Nenhuma ficha N2 encontrada para esta obra/pavimento.")
            report_lines.append("Execute o sistema de triagem Fase-2 primeiro para gerar as fichas N2.")

        report_text = "\n".join(report_lines)
        self.log(f"\n{report_text}\n")

        # === ETAPA 3: CONFIRMAÇÃO ===
        if not n2_available:
            QMessageBox.warning(self, "Fichas N2 Não Encontradas",
                f"Nenhuma ficha N2 encontrada para a obra '{obra_nome}'.\n\n"
                f"Execute a triagem Fase-2 primeiro para gerar as fichas N2.")
            return

        # Dialog de confirmação gigante
        dialog = QDialog(self)
        dialog.setWindowTitle("Auditoria de Fichas (Master Plan F1-F9) & Confirmação de Análise")
        dialog.resize(1100, 700)

        main_layout = QVBoxLayout(dialog)

        # Cabeçalho
        header = QLabel("<h3>Ecossistema de Conhecimento Estrutural (Fichas Fº1 a Fº9)</h3><p>Valide a coerência e os dados encontrados antes de injetar no Motor.</p>")
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)
        
        # Colunas
        grid = QGridLayout()
        
        def create_group(title, content_html, row, col, colspan=1):
            gb = QGroupBox(title)
            gb.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11px; border: 1px solid #3d4454; border-radius: 4px; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; color: #00ff9d; }")
            l = QVBoxLayout(gb)
            txt = QTextEdit()
            txt.setReadOnly(True)
            txt.setHtml(content_html)
            txt.setStyleSheet("background: #1e222d; border: none; font-size: 11px;")
            l.addWidget(txt)
            grid.addWidget(gb, row, col, 1, colspan)
        
        # --- Fase 1 ---
        html_f1 = f"""
        <b>ID:</b> <span style="color:#00c864">Fº1-OBRA</span><br><br>
        <i>Origem: Etapa 1 (Triagem/Ingestão)</i><br>
        <b>Status:</b> {'✅ Concluído' if obra_ficha_info else '⚠️ Pendente'}<br><br>
        <b>Métricas Macros:</b><br>
        Pilares: {obra_ficha_info.get('total_pil', 0) if obra_ficha_info else 0}<br>
        Lajes: {obra_ficha_info.get('total_laj', 0) if obra_ficha_info else 0}<br>
        Confiança: {obra_ficha_info.get('confianca', 0):.1%} se houver.
        """
        create_group("Fº1: Ficha Pré-Obra", html_f1, 0, 0)
        
        # --- Fase 2 ---
        html_f2_f3 = f"""
        <b>ID:</b> <span style="color:#00c864">Fº2-OBRA-PAVIMENTO</span><br>
        <i>Origem: Diagnostic Hub Pré</i><br>
        <b>Status:</b> Fichas iniciais geolocalizadas.<br><br>
        
        <b>ID:</b> <span style="color:#00c864">Fº3-OBRA</span><br>
        <i>Origem: Compreensão Global Motor</i><br>
        <b>Status:</b> <span style="color:#ffb800">🚀 Em Desenvolvimento</span><br>
        O Cérebro Global consolidado para análise de contexto futuro.
        """
        create_group("Fº2 & Fº3: Ficha Pavimento/Obra Global", html_f2_f3, 0, 1)
        
        # --- Fase 2.5 (N2) ---
        n2_str = ""
        for cls, label in [('PIL', 'Pilares'), ('FV', 'Vigas Fundo'), ('LV', 'Vigas Laterais'), ('LAJ', 'Lajes')]:
            info = n2_report[cls]
            n2_str += f"<b>{label}:</b> {info['fichas']} fichas / {info['recortes']} recortes<br>"
        
        html_f4_f5 = f"""
        <b>IDs:</b> <span style="color:#00c864">Fº4-OBRA-PAVIMENTO-CLASSE</span><br>
        <b>IDs:</b> <span style="color:#00c864">Fº5-OBRA-PAVIMENTO-CLASSE-ITEM</span><br>
        <i>Origem: Diagnostic Reverse (Teacher)</i><br>
        <b>Status:</b> {'✅ Gabaritos Encontrados' if n2_available else '❌ Não encontrados'}<br><br>
        {n2_str}
        <br>Gabaritos extraídos que populam a base N2 e N4.
        """
        create_group("Fº4 & Fº5: Engenharia Reversa (Teacher)", html_f4_f5, 0, 2)
        
        # --- Fº6: Obra Eng. Reversa (consolidação obra do gabarito N2) ---
        html_f6 = f"""
        <b>ID:</b> <span style="color:#00c864">Fº6-OBRA</span><br>
        <i>Origem: Diagnostic Reverse Hub (consolidação)</i><br>
        <b>Status:</b> {'✅ Consolidada' if obra_ficha_info else '⚠️ Pendente'}<br><br>
        Consolida as fichas Fº4/Fº5 de todos os pavimentos — a visão-OBRA do gabarito (N2).<br><br>
        Pilares: {obra_ficha_info.get('total_pil', 0) if obra_ficha_info else 0} |
        Lajes: {obra_ficha_info.get('total_laj', 0) if obra_ficha_info else 0}<br>
        Confiança: {obra_ficha_info.get('confianca', 0):.1%} se houver.
        """
        create_group("Fº6: Obra Engenharia Reversa", html_f6, 1, 0)

        # --- Fº7: Motor Structural Analyzer (N1) ---
        def _pct(d):
            return (d['validados'] / d['total'] * 100) if d['total'] else 0.0
        # PIL/LAJ contam itens próprios; FV/LV compartilham `beams` (não somar para o total)
        n1_total = n1_report['PIL']['total'] + n1_report['FV']['total'] + n1_report['LAJ']['total']
        n1_str = ""
        for _k in ('PIL', 'FV', 'LV', 'LAJ'):
            _d = n1_report[_k]
            _seg = f" · <b>{_d['segmentos']}</b> segmentos" if _k in ('FV', 'LV') else ""
            n1_str += f"<b>{_d['label']}:</b> {_d['total']} fichas — {_d['validados']} validados ({_pct(_d):.0f}%){_seg}<br>"
        html_f7 = f"""
        <b>ID:</b> <span style="color:#00c864">Fº7-OBRA-PAVIMENTO-CLASSE-ITEM</span><br>
        <i>Origem: Structural Analyzer (botão "Análise Geral")</i><br>
        <b>Status:</b> {'✅ Carregada do banco (estado salvo do pavimento)' if n1_total else '⚠️ Ainda não gerada — rode a "Análise Geral"'}<br><br>
        Interpretação do <b>motor</b> (o candidato, chamado <b>N1</b>) — a ser treinada até bater com o gabarito da Engenharia Reversa (Fº5/N2). É <b>(re)gerada</b> pela "Análise Geral" e <b>carregada do banco</b> ao abrir o pavimento (todos os itens salvos, com os campos já validados).<br><br>
        <b>Fichas por classe (validadas):</b><br>
        {n1_str}
        <span style="color:#7a8290; font-size:10px;">Cada viga gera 1 ficha de Fundo + 1 ficha de Lateral (por isso a contagem de fichas coincide). A divergência real está nos <b>segmentos dentro de cada ficha</b> (fundo; lados A/B + visões-corte) — o motor ainda não os extrai; isso vem com o refactor da viga (ver SPEC-VIGA-SPLIT-FV-LV).</span>
        """
        create_group("Fº7: Structural Analyzer — interpretação do motor (N1)", html_f7, 1, 1)

        # --- Fº8 & Fº9: Comparison Engine (N3 / N4) ---
        html_f8_f9 = f"""
        <b>ID:</b> <span style="color:#00c864">Fº8 / Fº9</span><br>
        <i>Origem: Comparison Engine (Robô)</i><br>
        <b>Status:</b> Pós-Conversão.<br><br>
        A Fº8 é a versão da Fº7 (N1) convertida pelo Robô → <b>N3</b>.<br>
        A Fº9 é a versão da Fº5 (N2) convertida pelo Robô → <b>N4</b> (O Gabarito Mestre).
        """
        create_group("Fº8 & Fº9: Comparison Engine Match", html_f8_f9, 1, 2)

        # --- Resumo/Avisos ---
        warn_txt = ""
        if not n2_available:
            warn_txt = "<span style='color:red;'>⚠️ ATENÇÃO: Nenhuma Ficha Fº4/Fº5 (Teacher N2) foi encontrada para ser usada! Motor rodará cego.</span>"
        else:
            warn_txt = "<span style='color:#00c864;'>✅ Fichas F5/N2 encontradas para consulta. O motor não será executado neste botão.</span>"

        html_warn = f"<b>Sumário:</b> Obra {obra_nome} | Pav: {pavimento_nome or 'Todos'}<br><br>{warn_txt}"
        create_group("Avisos", html_warn, 2, 0, colspan=3)
        
        main_layout.addLayout(grid)
        
        # Botões
        btn_layout = QHBoxLayout()
        btn_proceed = QPushButton("Confirmar consulta F5/N2")
        btn_proceed.setStyleSheet("background: #00c864; color: black; font-weight: bold; height: 30px;")
        btn_cancel = QPushButton("❌ Cancelar")
        btn_proceed.clicked.connect(lambda: dialog.accept())
        btn_cancel.clicked.connect(lambda: dialog.reject())
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_proceed)
        main_layout.addLayout(btn_layout)

        if dialog.exec() != QDialog.Accepted:
            self.log("Análise com Eng Reversa cancelada pelo usuário.")
            return

        # === ETAPA 4: CARREGAR CACHE N2 ===
        self.log("🔄 Carregando fichas N2 e executando Análise Geral para comparação FV...")

        self._reverse_eng_cache = {'PIL': {}, 'FV': {}, 'LV': {}, 'LAJ': {}}
        try:
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                query = "SELECT classe, elemento_id, campos_json FROM reverse_eng_fichas WHERE obra_name=?"
                params = [obra_nome]
                if pavimento_db:
                    query += " AND pavimento=?"
                    params.append(pavimento_db)
                c.execute(query, params)
                for row in c.fetchall():
                    cls, elem_id, campos_json = row
                    try:
                        self._reverse_eng_cache.setdefault(cls, {})[elem_id] = json.loads(campos_json)
                    except:
                        pass
                conn.close()
            n2_fv = self._reverse_eng_cache.get('FV', {})
            self.log(f"Cache Eng Reversa: {sum(len(v) for v in self._reverse_eng_cache.values())} fichas | FV={len(n2_fv)}")
        except Exception as e:
            self.log(f"❌ Erro ao carregar cache Eng Reversa: {e}")
            n2_fv = {}

        # === ETAPA 5: RODAR ANÁLISE GERAL + COMPARAR ===
        self.log("⚙️ Executando Análise Geral (motor FV)...")
        self.process_pillars_action(skip_pre_validation=True)
        # process_pillars_action é síncrona — comparar direto após retorno
        self._compare_fv_n1_n2(n2_fv)

        # Limpar o cache
        if hasattr(self, '_reverse_eng_cache'):
            del self._reverse_eng_cache

    def _compare_fv_n1_n2(self, n2_fv: dict):
        """Compara resultado do motor (N1) vs fichas N2 para Fundo de Vigas.
        Exibe painel de delta e grava eventos em engrev_fv_n1_interpretacao_learning.vision."""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                        QTableWidget, QTableWidgetItem, QPushButton,
                                        QHeaderView, QProgressBar)
        from PySide6.QtGui import QColor
        from PySide6.QtCore import Qt
        import re

        beams = getattr(self, 'beams_found', [])
        if not beams:
            self.log("⚠️ Nenhuma viga encontrada no motor para comparar com N2.")
            return
        if not n2_fv:
            self.log("⚠️ Cache N2 FV vazio — rode a Eng. Reversa (Fase-2) para esta obra/pavimento.")
            return

        # --- Comparação elemento a elemento ---
        rows = []
        matched = 0
        total_score = 0.0

        for b in beams:
            bname = b.get('name', b.get('parent_name', ''))
            # Normalizar: V301 → V301, F.V301 → V301
            clean = re.sub(r'^[FLfl]\.', '', bname).strip()
            n2 = n2_fv.get(clean) or n2_fv.get(bname)
            if not n2:
                rows.append({'name': bname, 'n2': False,
                             'n1_segs': b.get('seg_c', b.get('seg_bottom', 0)),
                             'n2_segs': '-', 'n1_comp': b.get('fields', {}).get('comprimento_total_fundo', 0),
                             'n2_comp': '-', 'n1_h': '', 'n2_h': '-', 'score': None})
                continue

            matched += 1
            n2_panels  = n2.get('panels', [])
            n2_segs    = len(n2_panels)
            n2_comp    = n2.get('total_height', 0)   # comprimento em unidades DXF
            n2_h       = n2.get('total_width', 0)    # espessura fundo (h)

            n1_segs    = b.get('seg_c', 0) or len([k for k in b.get('links', {}) if 'viga_fundo_seg' in k and 'area_segs' in k])
            n1_comp    = b.get('fields', {}).get('comprimento_total_fundo', 0) or 0
            # Parse h do texto de dimensão "20x60" → 20
            dim_text   = b.get('fields', {}).get('dimensao', '')
            m = re.search(r'(\d+)\s*[xX]\s*(\d+)', dim_text or '')
            n1_h       = float(m.group(1)) if m else 0.0

            # Score: até 3 critérios (segs, comprimento ±5%, h ±2)
            s = 0.0
            segs_ok = (n2_segs > 0 and n1_segs == n2_segs)
            comp_ok = (n2_comp > 0 and abs(n1_comp - n2_comp) / n2_comp < 0.05) if n2_comp else False
            h_ok    = (n2_h > 0 and abs(n1_h - n2_h) <= 2) if n2_h else False
            s += 33.3 if segs_ok else 0
            s += 33.3 if comp_ok else 0
            s += 33.3 if h_ok    else 0
            total_score += s

            rows.append({'name': bname, 'n2': True,
                         'n1_segs': n1_segs, 'n2_segs': n2_segs,
                         'n1_comp': round(n1_comp, 1), 'n2_comp': round(n2_comp, 1),
                         'n1_h': n1_h, 'n2_h': n2_h,
                         'segs_ok': segs_ok, 'comp_ok': comp_ok, 'h_ok': h_ok,
                         'score': round(s, 0)})

            # Feedback para engrev_fv learning store
            try:
                from src.core.engrev_fv_n1_interpretacao_learning_store import record_engrev_fv_n1_interpretacao_event
                pav_nome = self._current_pavement_name() if hasattr(self, '_current_pavement_name') else ''
                obra_n = getattr(self, '_current_obra_name', None) or ''
                record_engrev_fv_n1_interpretacao_event(
                    event_type='engrev_assisted_generated',
                    elemento_id=bname,
                    analysis_mode='engrev_assisted',
                    obra_name=obra_n,
                    pavimento=pav_nome,
                    features={
                        'panels_n1': n1_segs, 'panels_n2': n2_segs,
                        'comprimento_n1': n1_comp, 'comprimento_n2': n2_comp,
                        'h_n1': n1_h, 'h_n2': n2_h,
                        'segs_matched': 1 if segs_ok else 0,
                        'score': round(s, 1),
                    },
                )
            except Exception as _fe:
                self.log(f"[Learning FV] Erro feedback: {_fe}")

        avg_score = total_score / matched if matched else 0.0
        self.log(f"📊 Comparação FV: {matched}/{len(beams)} vigas matchadas N2 | Score médio: {avg_score:.0f}% | {matched} eventos gravados em engrev_fv learning store")

        # --- Dialog de comparação ---
        dlg = QDialog(self)
        dlg.setWindowTitle(f"FV Loop — Comparação N1 vs N2 ({matched} matchadas | Score: {avg_score:.0f}%)")
        dlg.resize(1100, 620)
        layout = QVBoxLayout(dlg)

        # Header score
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(avg_score))
        bar.setFormat(f"Score FV: {avg_score:.1f}% ({matched} vigas matchadas de {len(beams)})")
        bar.setStyleSheet("QProgressBar::chunk { background: #00c864; } QProgressBar { height: 22px; font-weight: bold; }")
        layout.addWidget(bar)

        # Tabela
        tbl = QTableWidget()
        tbl.setColumnCount(9)
        tbl.setHorizontalHeaderLabels(["Viga", "N2?", "Segs N1", "Segs N2", "✓S", "Comp N1", "Comp N2", "✓C", "Score"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl.setRowCount(len(rows))
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)

        green  = QColor("#1a472a")
        red    = QColor("#4a1a1a")
        yellow = QColor("#3a3a00")
        gray   = QColor("#2a2a2a")

        for i, r in enumerate(rows):
            def _item(txt, bg=None):
                it = QTableWidgetItem(str(txt))
                it.setTextAlignment(Qt.AlignCenter)
                if bg: it.setBackground(bg)
                return it

            tbl.setItem(i, 0, _item(r['name']))
            tbl.setItem(i, 1, _item("✓" if r['n2'] else "✗", green if r['n2'] else red))
            if r['n2']:
                tbl.setItem(i, 2, _item(r['n1_segs'], green if r.get('segs_ok') else red))
                tbl.setItem(i, 3, _item(r['n2_segs']))
                tbl.setItem(i, 4, _item("✓" if r.get('segs_ok') else "✗", green if r.get('segs_ok') else red))
                tbl.setItem(i, 5, _item(r['n1_comp'], green if r.get('comp_ok') else red))
                tbl.setItem(i, 6, _item(r['n2_comp']))
                tbl.setItem(i, 7, _item("✓" if r.get('comp_ok') else "✗", green if r.get('comp_ok') else red))
                score_bg = green if r['score'] >= 66 else (yellow if r['score'] >= 33 else red)
                tbl.setItem(i, 8, _item(f"{r['score']:.0f}%", score_bg))
            else:
                for col in range(2, 9):
                    tbl.setItem(i, col, _item("-", gray))

        layout.addWidget(tbl)

        from PySide6.QtCore import QTimer as _QT
        btn_rerun = QPushButton("🔄 Re-analisar com params atualizados")
        btn_rerun.setStyleSheet("background:#005a9e; color:white; font-weight:bold; height:28px;")
        def _rerun():
            dlg.accept()
            _QT.singleShot(200, lambda: (self.process_pillars_action(skip_pre_validation=True), self._compare_fv_n1_n2(n2_fv)))
        btn_rerun.clicked.connect(_rerun)
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(dlg.accept)
        hl = QHBoxLayout()
        hl.addWidget(btn_rerun)
        hl.addStretch()
        hl.addWidget(btn_close)
        layout.addLayout(hl)

        dlg.exec()

    def _process_with_obra_context(self):
        """Consulta contexto RAG T1+ sem executar ou alterar a Analise Geral."""
        from PySide6.QtWidgets import QMessageBox as _QMB
        try:
            import sys as _sys
            _scripts_dir = Path("D:/Agente-cad-PYSIDE/scripts")
            if str(_scripts_dir) not in _sys.path:
                _sys.path.insert(0, str(_scripts_dir))
            from rag_context_service import get_rag_context_for_item, format_context_text

            obra = self.sa_cmb_obras.currentText().strip()
            pavimento = self.sa_cmb_pavimentos.currentText().strip()
            item_data = (
                self.current_card.item_data
                if getattr(self, "current_card", None) is not None
                and isinstance(getattr(self.current_card, "item_data", None), dict)
                else {}
            )
            item_id = str(
                item_data.get("name")
                or item_data.get("nome")
                or item_data.get("id")
                or ""
            )
            raw_type = str(item_data.get("type") or item_data.get("tipo") or "").lower()
            if "pilar" in raw_type:
                classes = ["PL"]
            elif "laje" in raw_type:
                classes = ["LJ"]
            elif "fundo" in raw_type or item_data.get("fundo"):
                classes = ["FV"]
            elif "viga" in raw_type:
                classes = ["LV"]
            else:
                classes = ["PL", "LV", "FV", "LJ"]

            contexts = [
                get_rag_context_for_item(
                    classe=classe,
                    item_id=item_id,
                    obra=obra or None,
                    pavimento=pavimento or None,
                    min_tier="T1",
                )
                for classe in classes
            ]
            text = "\n\n".join(format_context_text(context) for context in contexts)
            _QMB.information(self, "Contexto RAG read-only", text)
            self.log(
                f"RAG read-only consultado: obra={obra or '-'} pav={pavimento or '-'} "
                f"item={item_id or '-'} classes={','.join(classes)}"
            )
        except Exception as exc:
            self.log(f"Erro ao consultar contexto RAG: {exc}")
            _QMB.warning(self, "Contexto RAG", f"Nao foi possivel consultar o RAG:\n{exc}")
        return
        if not self.dxf_data:
            from PySide6.QtWidgets import QMessageBox as _QMB
            _QMB.information(
                self, "Interpretar com Contexto",
                "Nenhum DXF carregado.\n\n"
                "1. Vá para Tab 1 (Diagnostic Hub)\n"
                "2. Selecione o DXF do pavimento\n"
                "3. Volte aqui e clique em '🧠 Interpretar com Contexto'"
            )
            return

        # Tentar carregar ficha da obra ativa
        obra_ctx = ""
        try:
            dados_root = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
            # Inferir obra a partir do projeto atual
            if self.current_project_name:
                parts = self.current_project_name.split(" / ")
                obra_name = parts[0] if parts else self.current_project_name
                estado_path = dados_root / obra_name / "pre_processamento_estado.json"
                if estado_path.exists():
                    import json as _json
                    estado = _json.loads(estado_path.read_text(encoding='utf-8'))
                    ficha  = estado.get('ficha', {})
                    totais = ficha.get('totais', {})
                    pavs   = ficha.get('pavimentos', [])
                    resumo = ficha.get('resumo_semantico', '')
                    obra_ctx = (
                        f"\n{'═'*50}\n"
                        f"🧠 CONTEXTO DA OBRA (Ficha Pré-Interpretativa)\n"
                        f"Obra: {ficha.get('obra', obra_name)}\n"
                        f"Total obra: {totais.get('pilares',0)} pilares | "
                        f"{totais.get('vigas',0)} vigas | {totais.get('lajes',0)} lajes\n"
                        f"Pavimentos: {len(pavs)}\n"
                    )
                    # Incluir contexto do pavimento atual se disponível
                    if self.current_project_name and " / " in self.current_project_name:
                        pav_name = parts[1] if len(parts) > 1 else ""
                        pav_data = next((p for p in pavs if p.get('nome','') == pav_name), None)
                        if pav_data:
                            obra_ctx += (
                                f"Pavimento atual '{pav_name}': "
                                f"{pav_data.get('n_pilares',0)}P / "
                                f"{pav_data.get('n_vigas',0)}V / "
                                f"{pav_data.get('n_lajes',0)}L\n"
                            )
                    if resumo:
                        obra_ctx += f"Resumo: {resumo}\n"
                    obra_ctx += f"{'═'*50}\n"
                else:
                    obra_ctx = (
                        "\n⚠ Ficha da Obra não encontrada. "
                        "Execute '⚡ Interpretar Obra Toda' no Tab 1 primeiro.\n"
                        "Prosseguindo com análise sem contexto...\n"
                    )
        except Exception as ctx_err:
            obra_ctx = f"\n⚠ Erro ao carregar contexto: {ctx_err}\n"

        if obra_ctx:
            self.log(obra_ctx)

        # Executar análise normal com contexto injetado no log
        self.process_pillars_action(skip_pre_validation=True)

    @staticmethod
    def _validate_structural_item(d: dict) -> bool:
        """Valida integridade minima de item estrutural antes de salvar no DB (ROBUSTEZ-03)."""
        try:
            comp = float(d.get("comprimento", d.get("comp", 0)) or 0)
            larg = float(d.get("largura", d.get("larg", d.get("b", 0))) or 0)
            alt = float(d.get("altura", d.get("h", d.get("height", 0))) or 0)
            # At least one non-zero dimension required
            return comp > 0 or larg > 0 or alt > 0
        except (ValueError, TypeError):
            return False

    def _auto_sync_robos_to_db(self, project_id, force=False):
        """Sincroniza automaticamente dados dos robôs para o analyzer."""
        p_data = self.db.get_project_by_id(project_id)
        if not p_data: return
        pav_nome = p_data.get('pavement_name') or p_data.get('name')
        if not pav_nome: return

        self.log(f"🤖 Sync: Verificando dados dos robôs para '{pav_nome}' (Force={force})...")

        # Sincronizar Pilares (ROBUSTEZ-03: validate before save)
        if force or not self.db.load_pillars(project_id):
            items = self._read_robot_pilares_data(pav_nome)
            valid_count = 0
            invalid_count = 0
            for item in items:
                if self._validate_structural_item(item):
                    self.db.save_pillar(item, project_id)
                    valid_count += 1
                else:
                    invalid_count += 1
                    self.log(f"   [AVISO] Pilar '{item.get('name', '?')}' ignorado (dimensoes invalidas)")
            if valid_count: self.log(f"   ✅ {valid_count} pilares sincronizados.")
            if invalid_count: self.log(f"   ⚠ {invalid_count} pilares ignorados (dimensoes invalidas).")

        # Sincronizar Lajes
        if force or not self.db.load_slabs(project_id):
            items = self._read_robot_lajes_data(pav_nome)
            valid_count = 0
            invalid_count = 0
            for item in items:
                if self._validate_structural_item(item):
                    self.db.save_slab(item, project_id)
                    valid_count += 1
                else:
                    invalid_count += 1
                    self.log(f"   [AVISO] Laje '{item.get('name', '?')}' ignorada (dimensoes invalidas)")
            if valid_count: self.log(f"   ✅ {valid_count} lajes sincronizadas.")
            if invalid_count: self.log(f"   ⚠ {invalid_count} lajes ignoradas.")

        # Sincronizar Vigas
        if force or not self.db.load_beams(project_id):
            lat = self._read_robot_laterais_data(pav_nome)
            valid_count = 0
            for item in lat:
                item['type'] = 'Lateral'
                if self._validate_structural_item(item):
                    self.db.save_beam(item, project_id)
                    valid_count += 1
            fun = self._read_robot_fundos_data(pav_nome)
            for item in fun:
                item['type'] = 'Fundo'
                if self._validate_structural_item(item):
                    self.db.save_beam(item, project_id)
                    valid_count += 1
            if valid_count: self.log(f"   ✅ {valid_count} vigas sincronizadas.")

    def load_project_action(self):
        """Carrega e restaura o estado do projeto."""
        if not self.current_project_id:
            return
        if getattr(self, '_analysis_in_progress', False):
            print(f"[GUARD] load_project_action bloqueado: análise em andamento", flush=True)
            return
        
        # --- AUTO SYNC FROM ROBOTS ---
        self._auto_sync_robos_to_db(self.current_project_id)
        
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
                     self.canvas.add_dxf_entities(self.dxf_data, source_dxf_path=dpath)
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
                             self.canvas.add_dxf_entities(self.dxf_data, source_dxf_path=dpath)
                             
                             # Atualizar Cache
                             if self.current_project_id not in self.loaded_projects_cache:
                                 self.loaded_projects_cache[self.current_project_id] = {}
                             self.loaded_projects_cache[self.current_project_id]['dxf_data'] = self.dxf_data
                             
                             dxf_bg_loaded = True
                     except Exception as e:
                         self.log(f"Erro ao carregar DXF de fundo: {e}")
                         QMessageBox.critical(
                             self,
                             "Erro de Carregamento",
                             f"Não foi possível carregar o arquivo DXF de fundo.\n\nDetalhes: {e}\n\nO arquivo pode estar corrompido ou inacessível."
                         )


        # 2. Carregar do Banco de Dados (Entidades Inteligentes - APENAS ESTRUTURAIS)
        # Os dados dos robôs NÃO são migrados para cá, cada robô mantém seus próprios dados
        self.pillars_found = self.db.load_pillars(self.current_project_id) or []
        self.slabs_found = self.db.load_slabs(self.current_project_id) or []
        self.beams_found = self.db.load_beams(self.current_project_id) or []
        
        # Migração automática de dados de vigas (estrutura antiga → nova)
        for beam in self.beams_found:
            self._migrate_beam_data(beam)

        # --- NOVA LÓGICA: Garantir geraçao de extensões de laje se ausentes (Retrocompatibilidade) ---
        if self.slabs_found:
            self.log("🔍 Verificando geometria de borda das lajes...")
            from shapely.geometry import Polygon
            count_ext_gen = 0
            for s in self.slabs_found:
                if 'links' not in s: s['links'] = {}
                self._ensure_slab_level_links(s)
                self._ensure_slab_cut_view_links(s)
                self._ensure_slab_neighbor_level_links(s)
                self._ensure_slab_support_pillar_links(s)
                
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
                # DESATIVADO: acrescimo_borda (foco em contorno puro)
                # if not out_segs.get('acrescimo_borda') and 'points' in s and s['points']:
                #     try:
                #         poly = Polygon(s['points'])
                #         extensions = self.slab_tracer.detect_extensions(poly)
                #         if extensions:
                #             out_segs['acrescimo_borda'] = extensions
                #             count_ext_gen += 1
                #     except Exception as e:
                #         print(f"Erro gerando extensão laje {s.get('name')}: {e}")
                
                # 3. Mapear Linhas Internas (Robo Laje -> Canvas) [TASK_002]
                if 'points' in s and s['points'] and (s.get('linhas_verticais') or s.get('linhas_horizontais')):
                    # Calcular Bounding Box para posicionar as linhas
                    x_vals = [p[0] for p in s['points']]
                    y_vals = [p[1] for p in s['points']]
                    min_x, max_x = min(x_vals), max(x_vals)
                    min_y, max_y = min(y_vals), max(y_vals)
                    
                    # Linhas Verticais
                    if s.get('linhas_verticais'):
                        if 'laje_v_lines' not in s['links']: s['links']['laje_v_lines'] = {'label': []}
                        v_links = s['links']['laje_v_lines']['label']
                        v_links.clear() # Evitar duplicidade no reparo
                        
                        curr_x = min_x
                        for dist in s['linhas_verticais']:
                            curr_x += dist
                            if curr_x >= max_x: break
                            v_links.append({
                                'type': 'poly',
                                'points': [(curr_x, min_y), (curr_x, max_y)],
                                'text': f'V-{dist}',
                                'role': 'internal_line_v'
                            })
                            
                    # Linhas Horizontais
                    if s.get('linhas_horizontais'):
                        if 'laje_h_lines' not in s['links']: s['links']['laje_h_lines'] = {'label': []}
                        h_links = s['links']['laje_h_lines']['label']
                        h_links.clear() # Evitar duplicidade no reparo
                        
                        curr_y = min_y
                        for dist in s['linhas_horizontais']:
                            curr_y += dist
                            if curr_y >= max_y: break
                            h_links.append({
                                'type': 'poly',
                                'points': [(min_x, curr_y), (max_x, curr_y)],
                                'text': f'H-{dist}',
                                'role': 'internal_line_h'
                            })
            
            if count_ext_gen > 0:
                self.log(f"✨ Extensões geradas para {count_ext_gen} lajes.")



        # Ordenar (Funções auxiliares internas)
        import re
        def nat_key(x):
            # FIX: Garantir que o nome seja string e tratar None
            name = str(x.get('name') or x.get('nome') or '')
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]
        
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
        
        # Override via Metadados (LinkManager) ou Config
        patterns_na = ""
        meta_override = item_data.get('field_metadata', {}).get(field_id, {}).get(slot_id, {})
        
        if meta_override.get('prompt'):
             prompt = meta_override['prompt']
        if meta_override.get('patterns_na'):
             patterns_na = meta_override['patterns_na']
             
        if not patterns_na:
             slot_cfg = self._get_slot_config(field_id, slot_id)
             patterns_na = slot_cfg.get('patterns_na', "")
        
        search_cfg = {'field_id': field_id, 'slot_id': slot_id, 'prompt': prompt, 'radius': radius, 'patterns_na': patterns_na}
        
        result = self.context_engine.perform_search(item_data, search_cfg, side=side_code)
        
        if result.get('status') == 'na':
             self.log(f"🚫 {result.get('debug', 'N/A Detectado')}")
             # Não criamos links se for N/A
             self.current_card.refresh_validation_styles()
             self._update_all_lists_ui()
             return

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

        # NOVO: Lógica de Remoção (Undo)
        if status == 'removed':
            role = f"{i_context['type'].upper()}_{field_id}"
            if self.memory:
                self.memory.remove_training_event(self.current_project_id, role, i_context['type'].upper())
            
            if hasattr(self, 'db'):
                self.db.delete_training_event_by_target(self.current_project_id, role, str(target_val))
            
            self.log(f"🗑️ Conhecimento removido: {i_context['type']} {i_context['name']} -> {field_id}")
            return

        # Enviar para Memória (HierarchicalMemory)
        if self.memory:
            role = f"{i_context['type'].upper()}_{field_id}"
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
            try:
                from src.core.dxf_preprocessor import DXFPreprocessor  # type: ignore
                self.dxf_preprocessor = DXFPreprocessor(self.spatial_index, self.memory)
            except ImportError:
                self.log("⚠️ DXFPreprocessor não está disponível. Funcionalidade desabilitada.")
                QMessageBox.warning(self, "Funcionalidade Indisponível", 
                                   "O módulo DXFPreprocessor não está implementado ainda.")
                self.hide_progress()
                return

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
        ui_refresh = train_data.get('ui_refresh', True)

        # 1. Registrar o Treino Individual
        self._log_training_action(p_data, field_id, slot_id, link_obj, status, comment)

        # 2. Feedback Visual Imediato
        if status == 'removed':
            link_obj.pop('validated', None)
            link_obj.pop('failed', None)
            self.log(f"🔄 Vínculo resetado para '{field_id}:{slot_id}'")
            self.current_card.refresh_validation_styles()
            if ui_refresh:
                self._update_all_lists_ui()
        elif status == 'valid':
            # Marcar o link individual como validado
            link_obj['validated'] = True
            link_obj.pop('failed', None)
            
            self.log(f"👍 Feedback POSITIVO salvo para '{field_id}:{slot_id}'")
            
            # Apenas atualizar visualmente sem marcar como "Validado Final"
            self.current_card.refresh_validation_styles()
            if ui_refresh:
                self._update_all_lists_ui()
        else:
            # Marcar o link individual como falho
            link_obj['failed'] = True
            link_obj.pop('validated', None)
            
            self.log(f"⚠️ Feedback de FALHA salvo para '{field_id}:{slot_id}'")
            self.current_card.refresh_validation_styles()

        # Forçar refresh do LinkManager se ele estiver aberto
        if hasattr(self.current_card, 'embedded_managers'):
            lm = self.current_card.embedded_managers.get(field_id)
            if lm:
                lm.refresh_list(partial=True)

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
        elif 'laje_visao_corte' in field_id and '_laje_cut_view' in LinkManager.SLOT_CONFIG:
            slots = LinkManager.SLOT_CONFIG['_laje_cut_view']
        elif 'laje_vizinhas_niveis' in field_id and '_laje_neighbor_levels' in LinkManager.SLOT_CONFIG:
            slots = LinkManager.SLOT_CONFIG['_laje_neighbor_levels']
        elif 'laje_pilares_apoio' in field_id and '_laje_support_pillars' in LinkManager.SLOT_CONFIG:
            slots = LinkManager.SLOT_CONFIG['_laje_support_pillars']
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

        for i in range(self.list_pillars.topLevelItemCount()):
            it = self.list_pillars.topLevelItem(i)
            if it and it.data(0, Qt.UserRole) == p_id:
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

        # 1b. Learning Store FV: gravar human_fundo_outline_validated ao validar viga_fundo_c
        if 'viga_fundo' in elem_type:
            try:
                from src.core.engrev_fv_n1_interpretacao_learning_store import record_human_fundo_outline_validated
                import re as _re
                fields = item_data.get('fields', {})
                pav_nome = self._current_pavement_name() if hasattr(self, '_current_pavement_name') else ''
                obra_n = getattr(self, '_current_obra_name', None) or ''
                dim_text = fields.get('dimensao', '')
                _m = _re.search(r'(\d+)\s*[xX]\s*(\d+)', dim_text or '')
                h_n1 = float(_m.group(1)) if _m else None
                record_human_fundo_outline_validated(
                    elemento_id=item_data.get('name', 'V?'),
                    obra_name=obra_n,
                    pavimento=pav_nome,
                    features={
                        'panels_n1': item_data.get('seg_c', item_data.get('seg_bottom', 0)),
                        'comprimento_n1': fields.get('comprimento_total_fundo'),
                        'h_n1': h_n1,
                    },
                    notes='card_validated_by_user',
                )
                self.log(f"🧠 Learning FV: human_fundo_outline_validated gravado para {item_data.get('name')}")
            except Exception as _e:
                self.log(f"[Learning FV] Erro ao gravar feedback: {_e}")

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
                    # Usar _sync_list_item_text que agora é O(1) via cache
                    self._sync_list_item_text(item_data)
                    
                    # Verificar se o item já existe na lista de validados
                    # Se não existir, aí sim fazemos o populate (ou poderíamos adicionar cirurgicamente)
                    is_in_valid_list = any(w.treeWidget() == valid_list for w in self.tree_item_map.get(p_id, []))
                    if not is_in_valid_list:
                        valid_beams = [b for b in self.beams_found if b.get('is_validated')]
                        self._populate_beam_tree(valid_list, valid_beams, "lateral")
                        self._populate_beam_tree(self.list_beams_fundo_valid, valid_beams, "fundo")
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
        
        # --- PROTEÇÃO DE DADOS ---
        # Se a viga já veio do Banco de Dados com vínculos processados, não podemos esmagar!
        has_links = len(b.get('links', {})) > 5  # Viga pré-processada tem muitos vínculos
        seg_bottom_empty = not b.get('links', {}).get('viga_segs', {}).get('seg_bottom', [])
        has_fundo_contours = any(
            b.get('links', {}).get(k, {}).get('contour')
            for k in b.get('links', {})
            if 'viga_fundo_seg' in k and '_area_segs' in k
        )

        def _fmt_fv_num(value):
            try:
                n = float(value)
            except Exception:
                return str(value or '')
            return str(int(n)) if abs(n - int(n)) < 0.05 else f"{n:.1f}"

        def _support_label(s):
            if not isinstance(s, dict):
                return ''
            for key in ('name', 'text', 'label', 'id_item', 'id'):
                val = s.get(key)
                if val:
                    return str(val)
            return ''

        def _link_points(link):
            pts = link.get('points') if isinstance(link, dict) else []
            return [tuple(p) for p in pts or [] if isinstance(p, (list, tuple)) and len(p) >= 2]

        def _dim_width_hint():
            dim_text = (
                b.get('fields', {}).get('dimensao')
                or b.get('fields', {}).get('dim')
                or b.get('dim')
                or ''
            )
            nums = [float(n.replace(',', '.')) for n in re.findall(r'\d+(?:[,.]\d+)?', str(dim_text))]
            return min(nums) if nums else None

        def _parse_dim_pair_text(text):
            m = re.search(r'\(?\s*(\d+(?:[,.]\d+)?)\s*[/xX]\s*(\d+(?:[,.]\d+)?)\s*\)?', str(text or ''))
            if not m:
                return None
            a = float(m.group(1).replace(',', '.'))
            c = float(m.group(2).replace(',', '.'))
            return min(a, c), max(a, c)

        def _is_support_text(text):
            txt = str(text or '').strip().upper()
            if not txt or _parse_dim_pair_text(txt):
                return False
            if txt == str(b.get('name') or '').upper():
                return False
            return bool(re.match(r'^(?:P|V|VF|VP|CONT)[A-Z0-9_.-]*\d[A-Z0-9_.-]*$', txt))

        def _nearest_text_to_point(point, predicate, radius=320.0):
            candidates = []
            if hasattr(self, 'spatial_index') and self.spatial_index and point:
                try:
                    raw = self.spatial_index.query_bbox((point[0]-radius, point[1]-radius, point[0]+radius, point[1]+radius))
                except Exception:
                    raw = []
            else:
                raw = []
            raw.extend(geo.get('texts', []) or [])
            raw.extend(geo.get('dimension_texts', []) or [])
            for item in raw:
                if not isinstance(item, dict) or 'text' not in item or not predicate(item.get('text', '')):
                    continue
                pos = item.get('pos')
                if not pos:
                    continue
                dist = ((float(pos[0]) - point[0]) ** 2 + (float(pos[1]) - point[1]) ** 2) ** 0.5
                if dist <= radius:
                    candidates.append((dist, item))
            if not candidates:
                return None
            link = dict(min(candidates, key=lambda x: x[0])[1])
            link['type'] = link.get('type') or 'text'
            return link

        def _score_text_to_points(pos, points):
            if not points or not pos:
                return float('inf')
            xs = [float(p[0]) for p in points]
            ys = [float(p[1]) for p in points]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            cx = min(max(float(pos[0]), min_x), max_x)
            cy = min(max(float(pos[1]), min_y), max_y)
            return ((float(pos[0]) - cx) ** 2 + (float(pos[1]) - cy) ** 2) ** 0.5

        def _nearest_dim_to_points(points):
            if not points:
                return None
            xs = [float(p[0]) for p in points]
            ys = [float(p[1]) for p in points]
            pad = 260.0
            raw = []
            if hasattr(self, 'spatial_index') and self.spatial_index:
                try:
                    raw = self.spatial_index.query_bbox((min(xs)-pad, min(ys)-pad, max(xs)+pad, max(ys)+pad))
                except Exception:
                    raw = []
            raw.extend(geo.get('texts', []) or [])
            raw.extend(geo.get('dimension_texts', []) or [])
            candidates = []
            for item in raw:
                if not isinstance(item, dict) or 'text' not in item:
                    continue
                pair = _parse_dim_pair_text(item.get('text'))
                if not pair or not item.get('pos'):
                    continue
                candidates.append((_score_text_to_points(item['pos'], points), item, pair))
            if not candidates:
                return None
            score, link, pair = min(candidates, key=lambda x: x[0])
            if score > pad * 1.5:
                return None
            out = dict(link)
            out['type'] = out.get('type') or 'text'
            out['role'] = 'Dimensao fundo de viga'
            return {'link': out, 'width': pair[0], 'height': pair[1], 'text': out.get('text', '')}

        def _fundo_geometry_metrics(points, length_hint=None):
            if not points:
                return _dim_width_hint(), length_hint or 0.0
            xs = [float(p[0]) for p in points]
            ys = [float(p[1]) for p in points]
            dx = max(xs) - min(xs) if xs else 0.0
            dy = max(ys) - min(ys) if ys else 0.0
            is_h = b.get('is_h', dx >= dy)
            largura = dy if is_h else dx
            comprimento = dx if is_h else dy
            if largura <= 0.1:
                largura = _dim_width_hint() or largura
            if length_hint:
                comprimento = float(length_hint)
            return largura, comprimento

        def _corner_flags(points):
            fields = {
                'chanfro_esq_top': 'N/A',
                'chanfro_esq_fun': 'N/A',
                'chanfro_dir_top': 'N/A',
                'chanfro_dir_fun': 'N/A',
                'abertura_topo_esq': 'N/A',
                'abertura_topo_dir': 'N/A',
                'abertura_fundo_esq': 'N/A',
                'abertura_fundo_dir': 'N/A',
            }
            if not points:
                return fields, ''
            uniq = []
            for p in points:
                if p not in uniq:
                    uniq.append(p)
            if len(uniq) <= 4:
                return fields, ''
            xs = [float(p[0]) for p in uniq]
            ys = [float(p[1]) for p in uniq]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            tol_x = max((max_x - min_x) * 0.12, 5.0)
            tol_y = max((max_y - min_y) * 0.12, 5.0)
            corners = {
                'chanfro_esq_top': (min_x, min_y),
                'chanfro_esq_fun': (min_x, max_y),
                'chanfro_dir_top': (max_x, min_y),
                'chanfro_dir_fun': (max_x, max_y),
            }
            for field, (cx, cy) in corners.items():
                has_corner = any(abs(float(x) - cx) <= 2.0 and abs(float(y) - cy) <= 2.0 for x, y in uniq)
                near_x = any(abs(float(x) - cx) <= tol_x and abs(float(y) - cy) > 2.0 for x, y in uniq)
                near_y = any(abs(float(y) - cy) <= tol_y and abs(float(x) - cx) > 2.0 for x, y in uniq)
                if not has_corner and near_x and near_y:
                    fields[field] = 'Detectado'
            return fields, f"{len(uniq) - 4} vertice(s) extra na geometria"

        def _refresh_fundo_link_fichas():
            links = b.setdefault('links', {})
            apoios = links.get('apoios', {}) if isinstance(links.get('apoios'), dict) else {}
            aberturas_map = links.get('aberturas', {}) if isinstance(links.get('aberturas'), dict) else {}
            aberturas = aberturas_map.get('pilar', [])
            abertura_txt = f"{len(aberturas)} interferencia(s) por pilar" if aberturas else ''
            for key, slots in list(links.items()):
                if not (isinstance(key, str) and key.startswith('viga_fundo_seg_') and key.endswith('_area_segs')):
                    continue
                contours = slots.get('contour') if isinstance(slots, dict) else None
                if not isinstance(contours, list):
                    continue
                seg_prefix = key[:-len('_area_segs')]
                for link in contours:
                    if not isinstance(link, dict):
                        continue
                    pts = _link_points(link)
                    largura, comprimento = _fundo_geometry_metrics(pts, link.get('len'))
                    dim_info = _nearest_dim_to_points(pts)
                    if dim_info:
                        largura = dim_info.get('width') or largura
                        b.setdefault('fields', {})[f'{seg_prefix}_dim'] = dim_info.get('text') or ''
                        links[f'{seg_prefix}_dim'] = {'label': [dim_info['link']]}
                    corner_data, corner_note = _corner_flags(pts)
                    ficha = dict(link.get('ficha') or {})
                    ficha.pop('apoio_inicial', None)
                    ficha.pop('apoio_final', None)
                    ficha.update({
                        'largura_total_fundo': _fmt_fv_num(largura),
                        'comprimento_total_fundo': _fmt_fv_num(comprimento),
                        'altura_total': _fmt_fv_num(dim_info.get('height')) if dim_info else ficha.get('altura_total', ''),
                        'abertura_especial': abertura_txt or corner_note or ficha.get('abertura_especial') or 'N/A',
                    })
                    for ck, cv in corner_data.items():
                        ficha[ck] = cv if cv != 'N/A' else ficha.get(ck) or cv
                    link['ficha'] = ficha
                    link['tag'] = link.get('tag') or 'Fundo'

            def _field_link_for_support(support):
                if not isinstance(support, dict):
                    return {}
                link = dict(support)
                slots = {}
                if link.get('text') or link.get('pos'):
                    slots['label'] = [dict(link)]
                if link.get('points'):
                    slots['geometry'] = [dict(link)]
                return slots

            fields = b.setdefault('fields', {})
            for key in list(links.keys()):
                if not (isinstance(key, str) and key.startswith('viga_fundo_seg_') and key.endswith('_area_segs')):
                    continue
                seg_prefix = key[:-len('_area_segs')]
                ini_key = f'{seg_prefix}_local_ini'
                fim_key = f'{seg_prefix}_local_fim'
                contours = links.get(key, {}).get('contour', [])
                pts = _link_points(contours[0]) if contours else []
                if pts:
                    is_h_pts = b.get('is_h', (max(p[0] for p in pts) - min(p[0] for p in pts)) >= (max(p[1] for p in pts) - min(p[1] for p in pts)))
                    start_pt = min(pts, key=lambda p: p[0] if is_h_pts else p[1])
                    end_pt = max(pts, key=lambda p: p[0] if is_h_pts else p[1])
                    start_text = _nearest_text_to_point(start_pt, _is_support_text)
                    end_text = _nearest_text_to_point(end_pt, _is_support_text)
                    if start_text:
                        fields[ini_key] = start_text.get('text', '')
                        links[ini_key] = {'label': [start_text]}
                    if end_text:
                        fields[fim_key] = end_text.get('text', '')
                        links[fim_key] = {'label': [end_text]}
                if apoios.get('inicio'):
                    fields[ini_key] = ', '.join(filter(None, [_support_label(s) for s in apoios.get('inicio', [])]))
                    links.setdefault(ini_key, _field_link_for_support(apoios['inicio'][0]))
                if apoios.get('fim'):
                    fields[fim_key] = ', '.join(filter(None, [_support_label(s) for s in apoios.get('fim', [])]))
                    links.setdefault(fim_key, _field_link_for_support(apoios['fim'][0]))

        def _run_lv_motors_patch():
            """Roda os motores LV Para e Passa para vigas já processadas que ainda não têm
            as chaves comprimento_total, ou que têm mais segmentos do que spans do bottom
            (fallback antigo criava 1 segmento por linha lateral em vez de 1 por span)."""
            _lengths_check = classified.get('merged_bottom_lengths', [])
            _expected_segs = len(_lengths_check) if _lengths_check else 1
            _existing_para = [k for k in b.get('links', {}) if 'comprimento_total' in k and 'viga_a' in k]
            if _existing_para:
                _existing_count = len(_existing_para)
                if _existing_count == _expected_segs:
                    _para_has_data = any(
                        any(bool(v) for v in b['links'].get(k, {}).values())
                        for k in _existing_para
                    )
                    if _para_has_data:
                        return  # Para já tem geometria real, não re-rodar
                # número errado (fallback antigo) — limpar e re-rodar
                for k in list(b.get('links', {}).keys()):
                    if 'comprimento_total' in k or ('comp_total_passa' in k and 'viga_' in k):
                        del b['links'][k]
                for k in list(b.keys()):
                    if '_seg_' in k and '_exists' in k and ('viga_a' in k or 'viga_b' in k):
                        del b[k]
            _lengths  = classified.get('merged_bottom_lengths', [])
            _coords   = classified.get('merged_bottom_groups_coords', [])
            _side_a   = classified.get('seg_side_a', [])
            _side_b   = classified.get('seg_side_b', [])
            _is_h     = b.get('is_h', True)
            _beam_pos = b.get('pos', (0, 0))

            def _lr(ln):
                if _is_h: return min(p[0] for p in ln), max(p[0] for p in ln)
                return min(p[1] for p in ln), max(p[1] for p in ln)

            def _best(raw_lines, smin, smax):
                best_r, best_l = 0.0, None
                for ln in raw_lines:
                    if len(ln) < 2: continue
                    lmin, lmax = _lr(ln)
                    ll = lmax - lmin
                    if ll <= 0: continue
                    ov = min(lmax, smax) - max(lmin, smin)
                    r = ov / ll
                    if r > 0.3 and r > best_r: best_r, best_l = r, ln
                return best_l

            def _run_motor(suffix):
                if _lengths and _coords:
                    for i, length in enumerate(_lengths, start=1):
                        smin, smax = _coords[i - 1]
                        for side_raw, tag, pk, sk in [
                            (_side_a, 'Lado A', 'viga_a', 'seg_side_a'),
                            (_side_b, 'Lado B', 'viga_b', 'seg_side_b'),
                        ]:
                            b[f'{pk}_seg_{i}_exists'] = True
                            tkey = f'{pk}_seg_{i}_{suffix}'
                            if tkey not in b['links']: b['links'][tkey] = {}
                            matched = _best(side_raw, smin, smax)
                            if matched is not None:
                                p1, p2 = matched[0], matched[-1]
                                sl = ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
                                b['links'][tkey][sk] = [{'type': 'poly', 'points': matched, 'len': sl, 'tag': tag}]
                            else:
                                synth = [(smin, _beam_pos[1]), (smax, _beam_pos[1])] if _is_h else [(_beam_pos[0], smin), (_beam_pos[0], smax)]
                                b['links'][tkey][sk] = [{'type': 'poly', 'points': synth, 'len': length, 'tag': tag}]
                else:
                    # Fallback: melhor linha única para seg_1
                    for side_raw, tag, pk, sk in [
                        (_side_a, 'Lado A', 'viga_a', 'seg_side_a'),
                        (_side_b, 'Lado B', 'viga_b', 'seg_side_b'),
                    ]:
                        lines_f = [ln for ln in side_raw if len(ln) >= 2]
                        if not lines_f: continue
                        best_ln = max(lines_f, key=lambda ln: ((ln[-1][0]-ln[0][0])**2+(ln[-1][1]-ln[0][1])**2)**0.5)
                        p1, p2 = best_ln[0], best_ln[-1]
                        sl = ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
                        b[f'{pk}_seg_1_exists'] = True
                        tkey = f'{pk}_seg_1_{suffix}'
                        if tkey not in b['links']: b['links'][tkey] = {}
                        b['links'][tkey][sk] = [{'type': 'poly', 'points': best_ln, 'len': sl, 'tag': tag}]
            _run_motor('comprimento_total')
            _run_motor('comp_total_passa')
            # Fallback: beam de DB com classified vazio → Para ficou sem geometria
            # mas Passa foi populado pela migração viga_segs. Copiar Passa → Para
            # (mesmo segmento lateral físico, só sufixo semântico difere).
            _links_now = b.get('links', {})
            _para_empty_after = not any(
                any(bool(v) for v in _links_now.get(k, {}).values())
                for k in _links_now if 'comprimento_total' in k and 'viga_' in k
            )
            if _para_empty_after:
                for _pk, _sv in list(_links_now.items()):
                    if 'comp_total_passa' in _pk and 'viga_' in _pk and any(bool(v) for v in _sv.values()):
                        _para_k = _pk.replace('comp_total_passa', 'comprimento_total')
                        _old_para = _links_now.get(_para_k, {})
                        _old_has = any(bool(v) for v in _old_para.values()) if _old_para else False
                        if not _old_has:
                            _links_now[_para_k] = {sk: list(sv) for sk, sv in _sv.items()}
            _refresh_fundo_link_fichas()

        if has_links and not seg_bottom_empty and has_fundo_contours:
            # Sincronizar name link com nome normalizado (se divergiu de DB antigo)
            _name_lbl = b.get('links', {}).get('name', {}).get('label', [])
            if _name_lbl and isinstance(_name_lbl, list) and _name_lbl[0].get('text') != b.get('name'):
                _name_lbl[0]['text'] = b['name']
            _run_lv_motors_patch()  # garante que motor Para também populou
            return  # Já processada com fundo OK — manter
        if has_links and not seg_bottom_empty and not has_fundo_contours:
            # seg_bottom populado (legado) mas fundo links ausentes — migrar
            existing_segs = b['links'].get('viga_segs', {}).get('seg_bottom', [])
            for seg_idx, seg_entry in enumerate(existing_segs, start=1):
                area_key = f'viga_fundo_seg_{seg_idx}_area_segs'
                if area_key not in b['links']:
                    b['links'][area_key] = {'contour': [seg_entry]}
                    b[f'viga_fundo_seg_{seg_idx}_exists'] = True
                elif not b['links'][area_key].get('contour'):
                    b['links'][area_key]['contour'] = [seg_entry]
            b['seg_c'] = len(existing_segs)
            # Sincronizar name link com nome normalizado
            _name_lbl = b['links'].get('name', {}).get('label', [])
            if _name_lbl and isinstance(_name_lbl, list) and _name_lbl[0].get('text') != b['name']:
                _name_lbl[0]['text'] = b['name']
            _run_lv_motors_patch()
            return
        if has_links and seg_bottom_empty:
            # Fundo ainda não processado (ou DB antigo) — só reprocessar fundos
            geo_inner = b.get('geometry', {})
            classified_inner = geo_inner.get('classified', {})
            b['links'].setdefault('viga_segs', {'seg_bottom': []})
            if 'seg_bottom' not in b['links']['viga_segs']:
                b['links']['viga_segs']['seg_bottom'] = []
            
            lengths_i = classified_inner.get('merged_bottom_lengths', [])
            coords_i = classified_inner.get('merged_bottom_groups_coords', [])
            seg_bottom_raw_i = classified_inner.get('seg_bottom', [])
            is_h_i = b.get('is_h', True)
            
            if lengths_i:
                for idx, length_i in enumerate(lengths_i, start=1):
                    b[f'viga_fundo_seg_{idx}_exists'] = True
                    area_key = f'viga_fundo_seg_{idx}_area_segs'
                    if area_key not in b['links']:
                        b['links'][area_key] = {'contour': []}
                    
                    # Construir geometria sintética ou associar real
                    if idx <= len(coords_i):
                        span_min, span_max = coords_i[idx - 1]
                        beam_pos = b.get('pos', (0, 0))
                        if is_h_i:
                            synth = [(span_min, beam_pos[1]), (span_max, beam_pos[1])]
                        else:
                            synth = [(beam_pos[0], span_min), (beam_pos[0], span_max)]
                        entry = {'type': 'poly', 'points': synth, 'len': length_i, 'tag': 'Fundo'}
                        b['links'][area_key]['contour'].append(entry)
                        b['links']['viga_segs']['seg_bottom'].append(entry)
            elif seg_bottom_raw_i:
                seg_idx = 0
                for raw_line in seg_bottom_raw_i:
                    if len(raw_line) < 2:
                        continue
                    p1, p2 = raw_line[0], raw_line[-1]
                    length_i = ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
                    if length_i < 30:
                        continue
                    seg_idx += 1
                    
                    b[f'viga_fundo_seg_{seg_idx}_exists'] = True
                    area_key = f'viga_fundo_seg_{seg_idx}_area_segs'
                    if area_key not in b['links']:
                        b['links'][area_key] = {'contour': []}
                        
                    entry = {'type': 'poly', 'points': raw_line, 'len': length_i, 'tag': 'Fundo'}
                    b['links'][area_key]['contour'].append(entry)
                    b['links']['viga_segs']['seg_bottom'].append(entry)
                    
            b['seg_c'] = len(b['links']['viga_segs']['seg_bottom'])
            _run_lv_motors_patch()
            return

        # --- ESTRUTURA BASE ---
        b.update({
            'type': 'Viga',
            'is_validated': False,
            'fields': {},
            'links': {
                'name': {'label': [{'text': b['name'], 'type': 'text', 'pos': b.get('pos', (0,0)), 'role': 'Identificador Viga'}]},
                'viga_segs': {'seg_bottom': []},  # Apenas seg_bottom (seg_side_a e seg_side_b vão para novos campos)
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
        # Inicializar chaves para seg_1 de ambos os motores (Para e Passa)
        if 'viga_a_seg_1_comp_total_passa' not in b['links']:
            b['links']['viga_a_seg_1_comp_total_passa'] = {'seg_side_a': []}
        if 'viga_b_seg_1_comp_total_passa' not in b['links']:
            b['links']['viga_b_seg_1_comp_total_passa'] = {'seg_side_b': []}
        if 'viga_a_seg_1_comprimento_total' not in b['links']:
            b['links']['viga_a_seg_1_comprimento_total'] = {'seg_side_a': []}
        if 'viga_b_seg_1_comprimento_total' not in b['links']:
            b['links']['viga_b_seg_1_comprimento_total'] = {'seg_side_b': []}
        
        def process_segments(side_key, tag, prefix_key, field_suffix):
            lines = classified.get(side_key, [])
            total_len = 0
            for i, line in enumerate(lines, start=1):
                p1, p2 = line[0], line[-1]
                length = ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
                total_len += length
                
                # Fatiamento para o Painel Direito
                # 1. Avisar que o segmento existe
                b[f'{prefix_key}_seg_{i}_exists'] = True
                
                # 2. Injetar a geometria na chave correta
                target_field_key = f'{prefix_key}_seg_{i}_{field_suffix}'
                
                if target_field_key not in b['links']:
                    b['links'][target_field_key] = {}
                
                if side_key not in b['links'][target_field_key]:
                    b['links'][target_field_key][side_key] = []
                    
                b['links'][target_field_key][side_key].append({
                    'type': 'poly', 'points': line, 'len': length, 'tag': tag
                })
            return total_len

        def is_closed_poly(pts):
            """Retorna True se a polyline é um polígono fechado (primeiro ~= último)."""
            if not pts or len(pts) < 4:
                return False
            dx = abs(pts[0][0] - pts[-1][0])
            dy = abs(pts[0][1] - pts[-1][1])
            return dx < 2.0 and dy < 2.0

        def _close_lines_to_polygon(lines, is_h, beam_offset=None):
            """Une 2+ linhas paralelas em 1 polígono fechado (área do fundo).
            Ordena por coordenada transversal: linha inferior primeiro.
            Com 1 linha e beam_offset disponível, cria retângulo com 4 pontos."""
            if len(lines) == 1:
                ln = list(lines[0])
                if beam_offset and beam_offset > 0:
                    # Orientar esq→dir (H) ou baixo→cima (V)
                    if is_h:
                        if ln[0][0] > ln[-1][0]: ln = list(reversed(ln))
                        ln2 = [(p[0], p[1] + beam_offset) for p in ln]
                    else:
                        if ln[0][1] > ln[-1][1]: ln = list(reversed(ln))
                        ln2 = [(p[0] + beam_offset, p[1]) for p in ln]
                    return ln + list(reversed(ln2))
                return ln
            def mid_transversal(ln):
                return sum(p[1] for p in ln) / len(ln) if is_h else sum(p[0] for p in ln) / len(ln)
            sorted_ln = sorted(lines, key=mid_transversal)
            ln1 = list(sorted_ln[0])   # linha inferior/esquerda
            ln2 = list(sorted_ln[-1])  # linha superior/direita
            # Garantir orientação: ln1 e ln2 percorridos na mesma direção (esq→dir ou baixo→cima)
            if is_h:
                if ln1 and ln1[0][0] > ln1[-1][0]: ln1 = list(reversed(ln1))
                if ln2 and ln2[0][0] > ln2[-1][0]: ln2 = list(reversed(ln2))
            else:
                if ln1 and ln1[0][1] > ln1[-1][1]: ln1 = list(reversed(ln1))
                if ln2 and ln2[0][1] > ln2[-1][1]: ln2 = list(reversed(ln2))
            # Polígono: ln1 esq→dir, ln2 dir→esq (fecha a área)
            return ln1 + list(reversed(ln2))

        def process_fundo_segments():
            """Popula segmentos de fundo usando merged_bottom_lengths/coords do BeamTracer.

            Hierarquia:
            1. merged_bottom_lengths + merged_bottom_groups_coords (dados reais do BeamTracer)
            2. seg_bottom bruto (fallback)

            Quando múltiplas linhas se sobrepõem ao mesmo span (linhas A e B do fundo),
            fecha-as em 1 polígono de área em vez de armazenar 2 vínculos de linha separados.
            """
            lengths_list = classified.get('merged_bottom_lengths', [])
            coords_list = classified.get('merged_bottom_groups_coords', [])
            seg_bottom_raw = classified.get('seg_bottom', [])
            is_h = b.get('is_h', True)

            # Altura da viga para criar retângulo quando só 1 linha é encontrada
            _dim_text = b.get('fields', {}).get('dimensao', '') or ''
            _m_dim = re.search(r'(\d+)\s*[xX]\s*(\d+)', _dim_text)
            h_beam = float(_m_dim.group(1)) if _m_dim else 20.0

            if lengths_list:
                # Caminho preferencial: usar os comprimentos/coords já calculados
                total_len = 0.0
                for i, length in enumerate(lengths_list, start=1):
                    total_len += length

                    b[f'viga_fundo_seg_{i}_exists'] = True
                    area_key = f'viga_fundo_seg_{i}_area_segs'
                    if area_key not in b['links']:
                        b['links'][area_key] = {'contour': []}

                    # Coletar TODAS as linhas que se sobrepõem >= 30% ao span
                    matching_lines = []
                    if i <= len(coords_list) and seg_bottom_raw:
                        span_min, span_max = coords_list[i - 1]
                        for raw_line in seg_bottom_raw:
                            if len(raw_line) < 2:
                                continue
                            if is_h:
                                line_min = min(p[0] for p in raw_line)
                                line_max = max(p[0] for p in raw_line)
                            else:
                                line_min = min(p[1] for p in raw_line)
                                line_max = max(p[1] for p in raw_line)
                            overlap = min(line_max, span_max) - max(line_min, span_min)
                            line_len = line_max - line_min
                            if line_len > 0 and overlap / line_len > 0.3:
                                matching_lines.append(raw_line)

                    if matching_lines:
                        # Fechar 2+ linhas em 1 polígono; 1 linha → retângulo com h_beam
                        pts = _close_lines_to_polygon(matching_lines, is_h, beam_offset=h_beam)
                        link_entry = {'type': 'poly', 'points': pts, 'len': length, 'tag': 'Fundo'}
                        b['links'][area_key]['contour'] = [link_entry]
                        b['links']['viga_segs']['seg_bottom'].append(link_entry)
                    elif i <= len(coords_list):
                        # Fallback sintético: retângulo de 4 pontos usando h_beam
                        span_min, span_max = coords_list[i - 1]
                        beam_pos = b.get('pos', (0, 0))
                        half_h = h_beam / 2.0
                        if is_h:
                            synth_line = [
                                (span_min, beam_pos[1] - half_h),
                                (span_max, beam_pos[1] - half_h),
                                (span_max, beam_pos[1] + half_h),
                                (span_min, beam_pos[1] + half_h),
                            ]
                        else:
                            synth_line = [
                                (beam_pos[0] - half_h, span_min),
                                (beam_pos[0] + half_h, span_min),
                                (beam_pos[0] + half_h, span_max),
                                (beam_pos[0] - half_h, span_max),
                            ]
                        link_entry = {'type': 'poly', 'points': synth_line, 'len': length, 'tag': 'Fundo'}
                        b['links'][area_key]['contour'] = [link_entry]
                        b['links']['viga_segs']['seg_bottom'].append(link_entry)
                    elif not coords_list and seg_bottom_raw:
                        raw_candidates = [s for s in seg_bottom_raw if len(s) >= 2]
                        if i - 1 < len(raw_candidates):
                            raw_line = raw_candidates[i - 1]
                            link_entry = {'type': 'poly', 'points': raw_line, 'len': length, 'tag': 'Fundo'}
                            b['links'][area_key]['contour'] = [link_entry]
                            b['links']['viga_segs']['seg_bottom'].append(link_entry)

                return total_len
            elif seg_bottom_raw:
                # Fallback: usar seg_bottom bruto
                total_len = 0.0
                seg_idx = 0
                for line in seg_bottom_raw:
                    if len(line) < 2:
                        continue
                    p1, p2 = line[0], line[-1]
                    length = ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
                    if not is_closed_poly(line) and length < 30:
                        continue  # ignora divisórias perpendiculares curtas
                    seg_idx += 1
                    total_len += length

                    b[f'viga_fundo_seg_{seg_idx}_exists'] = True
                    area_key = f'viga_fundo_seg_{seg_idx}_area_segs'
                    if area_key not in b['links']:
                        b['links'][area_key] = {'contour': []}

                    link_entry = {'type': 'poly', 'points': line, 'len': length, 'tag': 'Fundo'}
                    b['links'][area_key]['contour'].append(link_entry)
                    b['links']['viga_segs']['seg_bottom'].append(link_entry)
                return total_len
            else:
                return 0.0

        def _process_lv_base(target_suffix):
            """Motor base para laterais de viga. Cada motor especializado chama esta função
            com o sufixo de chave que deve ser populado.
            - 'comprimento_total'  → Motor Para  (vigas que param num apoio)
            - 'comp_total_passa'   → Motor Passa (vigas que passam por um apoio)
            """
            lengths_list = classified.get('merged_bottom_lengths', [])
            coords_list  = classified.get('merged_bottom_groups_coords', [])
            side_a_raw   = classified.get('seg_side_a', [])
            side_b_raw   = classified.get('seg_side_b', [])
            is_h         = b.get('is_h', True)
            beam_pos     = b.get('pos', (0, 0))

            def line_range(ln):
                if is_h:
                    return min(p[0] for p in ln), max(p[0] for p in ln)
                return min(p[1] for p in ln), max(p[1] for p in ln)

            def best_overlap(raw_lines, span_min, span_max):
                best, best_ratio = None, 0.0
                for ln in raw_lines:
                    if len(ln) < 2:
                        continue
                    lmin, lmax = line_range(ln)
                    ov = min(lmax, span_max) - max(lmin, span_min)
                    ll = lmax - lmin
                    if ll > 0:
                        r = ov / ll
                        if r > 0.3 and r > best_ratio:
                            best_ratio, best = r, ln
                return best

            total_a = total_b = 0.0

            if lengths_list and coords_list:
                for i, length in enumerate(lengths_list, start=1):
                    span_min, span_max = coords_list[i - 1]
                    for side_raw, tag, prefix_key, slot_key in [
                        (side_a_raw, 'Lado A', 'viga_a', 'seg_side_a'),
                        (side_b_raw, 'Lado B', 'viga_b', 'seg_side_b'),
                    ]:
                        b[f'{prefix_key}_seg_{i}_exists'] = True
                        target_key = f'{prefix_key}_seg_{i}_{target_suffix}'
                        if target_key not in b['links']:
                            b['links'][target_key] = {}
                        matched = best_overlap(side_raw, span_min, span_max)
                        if matched is not None:
                            p1, p2 = matched[0], matched[-1]
                            seg_len = ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
                            b['links'][target_key][slot_key] = [{'type': 'poly', 'points': matched, 'len': seg_len, 'tag': tag}]
                            if prefix_key == 'viga_a': total_a += seg_len
                            else: total_b += seg_len
                        else:
                            if is_h:
                                synth = [(span_min, beam_pos[1]), (span_max, beam_pos[1])]
                            else:
                                synth = [(beam_pos[0], span_min), (beam_pos[0], span_max)]
                            b['links'][target_key][slot_key] = [{'type': 'poly', 'points': synth, 'len': length, 'tag': tag}]
                            if prefix_key == 'viga_a': total_a += length
                            else: total_b += length
            else:
                # Fallback: sem spans do bottom, criar apenas seg_1 com a melhor linha (mais comprida)
                for side_raw_f, tag_f, pk_f, sk_f in [
                    (side_a_raw, 'Lado A', 'viga_a', 'seg_side_a'),
                    (side_b_raw, 'Lado B', 'viga_b', 'seg_side_b'),
                ]:
                    lines_f = [ln for ln in side_raw_f if len(ln) >= 2]
                    if not lines_f:
                        continue
                    best_ln = max(lines_f, key=lambda ln: ((ln[-1][0]-ln[0][0])**2+(ln[-1][1]-ln[0][1])**2)**0.5)
                    p1f, p2f = best_ln[0], best_ln[-1]
                    sl_f = ((p2f[0]-p1f[0])**2 + (p2f[1]-p1f[1])**2)**0.5
                    b[f'{pk_f}_seg_1_exists'] = True
                    tkey_f = f'{pk_f}_seg_1_{target_suffix}'
                    if tkey_f not in b['links']:
                        b['links'][tkey_f] = {}
                    b['links'][tkey_f][sk_f] = [{'type': 'poly', 'points': best_ln, 'len': sl_f, 'tag': tag_f}]
                    if pk_f == 'viga_a':
                        total_a += sl_f
                    else:
                        total_b += sl_f

            return total_a, total_b

        def process_lv_para_segments():
            """Motor LV — Vigas que Param: popula {prefix}_seg_{i}_comprimento_total."""
            return _process_lv_base('comprimento_total')

        def process_lv_passa_segments():
            """Motor LV — Vigas que Passam: popula {prefix}_seg_{i}_comp_total_passa."""
            return _process_lv_base('comp_total_passa')

        # Rodar os dois motores independentes
        len_a_para,  len_b_para  = process_lv_para_segments()
        len_a_passa, len_b_passa = process_lv_passa_segments()
        # Comprimento de referência: usar Passa como primário (tem vínculo geométrico)
        len_a = len_a_passa
        len_b = len_b_passa

        len_f = process_fundo_segments()
        
        b['fields']['comprimento_total_a'] = round(len_a, 1)
        b['fields']['comprimento_total_b'] = round(len_b, 1)
        b['fields']['comprimento_total_fundo'] = round(len_f, 1)
        
        b['seg_a'] = len(classified.get('seg_side_a', []))
        b['seg_b'] = len(classified.get('seg_side_b', []))
        b['seg_bottom'] = len(classified.get('seg_bottom', []))
        # seg_c = número real de painéis de fundo detectados (merged_bottom_groups ou polígonos fechados)
        b['seg_c'] = len(b['links']['viga_segs']['seg_bottom'])

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
            for side_key, prefix_key in [('seg_side_a', 'viga_a'), ('seg_side_b', 'viga_b')]:
                # varrer ate o limite razoavel de segmentos criados na memoria
                for i in range(1, 10):
                    field_key = f'{prefix_key}_seg_{i}_comp_total_passa'
                    if field_key not in b['links']:
                        continue
                    segments = b['links'][field_key].get(side_key, [])
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
        for key in ['seg_side_a', 'seg_side_b', 'seg_bottom']:
            for line in classified.get(key, []):
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

        _refresh_fundo_link_fichas()
        # --- CRUZAMENTO DE DADOS DA ENGENHARIA REVERSA ---
        is_reverse_eng = hasattr(self, '_reverse_eng_cache')
        if is_reverse_eng:
            b_name = b.get('name', '')
            c_name = b_name
            cls_key = 'LV'
            if b_name.startswith('FV-'):
                c_name = b_name[3:]          # FV-V305.C → V305.C
                c_name = c_name.removesuffix('.C')  # → V305
                cls_key = 'FV'
            elif b_name.startswith('LV-'):
                c_name = b_name[3:]          # LV-V305.A → V305.A
                c_name = c_name[:-2] if c_name.endswith(('.A', '.B')) else c_name  # → V305
                cls_key = 'LV'
            elif b_name.startswith('F.'):
                c_name = b_name[2:]
                import re as _re_rv
                c_name = _re_rv.sub(r'\.C(?:-\d+)?$', '', c_name)
                cls_key = 'FV'
            elif b_name.startswith('L.'):
                c_name = b_name[2:]
                cls_key = 'LV'

            f_data = self._reverse_eng_cache.get(cls_key, {}).get(c_name)
            if f_data:
                # 1. Marcar como Validado pela Eng. Reversa
                b['is_validated'] = True
                if 'validated_fields' not in b:
                    b['validated_fields'] = []
                
                # 2. Copiar as Dimensoes Globais
                b['fields']['dimensao'] = f"{f_data.get('total_width','')}x{f_data.get('total_height','')}"
                if 'dimensao' not in b['validated_fields']: b['validated_fields'].append('dimensao')
                
                # 3. Fatiar e Traduzir Segmentos
                segs = f_data.get('segments_rich', [])
                for i, seg in enumerate(segs, start=1):
                    comp_total = sum([p.get('width', 0) for p in seg.get('panels', [])])
                    if cls_key == 'FV':
                        b[f'viga_fundo_seg_{i}_exists'] = True
                        b['fields'][f'viga_fundo_seg_{i}_largura'] = str(seg.get('total_width', ''))
                        b['fields'][f'viga_fundo_seg_{i}_comprimento'] = str(comp_total)
                        if f'viga_fundo_seg_{i}_largura' not in b['validated_fields']: b['validated_fields'].append(f'viga_fundo_seg_{i}_largura')
                        if f'viga_fundo_seg_{i}_comprimento' not in b['validated_fields']: b['validated_fields'].append(f'viga_fundo_seg_{i}_comprimento')
                    else:
                        b[f'viga_a_seg_{i}_exists'] = True
                        b[f'viga_b_seg_{i}_exists'] = True
                        b['fields'][f'viga_a_seg_{i}_comp_total_passa'] = str(comp_total)
                        b['fields'][f'viga_b_seg_{i}_comp_total_passa'] = str(comp_total)
                        if f'viga_a_seg_{i}_comp_total_passa' not in b['validated_fields']: b['validated_fields'].append(f'viga_a_seg_{i}_comp_total_passa')
                        if f'viga_b_seg_{i}_comp_total_passa' not in b['validated_fields']: b['validated_fields'].append(f'viga_b_seg_{i}_comp_total_passa')
                
                self.log(f"✅ Cruzamento Efetuado: {cls_key} {c_name} (Eng. Reversa aplicou {len(segs)} segmentos).")

        self.log(f"🧠 Viga {b['name']} pré-interpretada com sucesso.")

    def _ensure_slab_level_links(self, slab: Dict) -> Dict:
        links = slab.setdefault('links', {})
        level_links = links.setdefault('laje_nivel', {})
        if not isinstance(level_links, dict):
            level_links = {}
            links['laje_nivel'] = level_links
        level_links.setdefault('label', [])
        return level_links

    def _append_unique_slab_link(self, target: list, link: dict) -> None:
        if not isinstance(target, list) or not isinstance(link, dict):
            return
        if link.get('points'):
            for existing in target:
                if isinstance(existing, dict) and self._same_cut_view_signature(link, existing):
                    return
        elif link in target:
            return
        target.append(link)

    def _same_text_link_signature(self, a: dict, b: dict, tol: float = 8.0) -> bool:
        if not isinstance(a, dict) or not isinstance(b, dict):
            return False
        if str(a.get('text') or '').strip() != str(b.get('text') or '').strip():
            return False
        if a.get('source_slab') and b.get('source_slab') and a.get('source_slab') != b.get('source_slab'):
            return False
        pa = a.get('pos')
        pb = b.get('pos')
        if pa and pb:
            try:
                return ((float(pa[0]) - float(pb[0])) ** 2 + (float(pa[1]) - float(pb[1])) ** 2) ** 0.5 <= tol
            except Exception:
                return False
        return bool(a.get('source_slab') and a.get('source_slab') == b.get('source_slab'))

    def _append_unique_neighbor_level_link(self, target: list, link: dict) -> bool:
        if not isinstance(target, list) or not isinstance(link, dict):
            return False
        for existing in target:
            if self._same_text_link_signature(existing, link):
                return False
        target.append(link)
        return True

    def _neighbor_direction_slot(self, direction: str) -> str:
        d = str(direction or '').strip().lower()
        mapping = {
            'top': 'neighbor_north',
            'north': 'neighbor_north',
            'norte': 'neighbor_north',
            'bottom': 'neighbor_south',
            'south': 'neighbor_south',
            'sul': 'neighbor_south',
            'right': 'neighbor_east',
            'east': 'neighbor_east',
            'leste': 'neighbor_east',
            'left': 'neighbor_west',
            'west': 'neighbor_west',
            'oeste': 'neighbor_west',
        }
        return mapping.get(d, 'neighbor_north')

    def _direction_from_link_pos(self, slab: Dict, link: dict) -> str:
        pos = link.get('pos') if isinstance(link, dict) else None
        pts = slab.get('points') or []
        if not pos or not pts:
            return 'north'
        try:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            cx = (min(xs) + max(xs)) / 2.0
            cy = (min(ys) + max(ys)) / 2.0
            dx = float(pos[0]) - cx
            dy = float(pos[1]) - cy
            if abs(dx) >= abs(dy):
                return 'east' if dx >= 0 else 'west'
            return 'north' if dy >= 0 else 'south'
        except Exception:
            return 'north'

    def _ensure_slab_neighbor_level_links(self, slab: Dict) -> Dict:
        links = slab.setdefault('links', {})
        neighbor_links = links.setdefault('laje_vizinhas_niveis', {})
        if not isinstance(neighbor_links, dict):
            neighbor_links = {}
            links['laje_vizinhas_niveis'] = neighbor_links
        for slot in ('neighbor_north', 'neighbor_east', 'neighbor_west', 'neighbor_south'):
            neighbor_links.setdefault(slot, [])

        # Migra textos antigos que ficavam dentro de laje_visao_corte.
        cut_links = links.get('laje_visao_corte', {})
        if isinstance(cut_links, dict):
            for old in cut_links.get('neighbor_level_text', []) or []:
                if not isinstance(old, dict):
                    continue
                direction = old.get('source_direction') or self._direction_from_link_pos(slab, old)
                slot = self._neighbor_direction_slot(direction)
                migrated = dict(old)
                migrated['role'] = slot
                self._append_unique_neighbor_level_link(neighbor_links[slot], migrated)

        validated = slab.setdefault('validated_link_classes', {})
        if isinstance(validated, dict):
            old_slots = set(validated.get('laje_visao_corte') or [])
            if 'neighbor_level_text' in old_slots:
                new_slots = set(validated.get('laje_vizinhas_niveis') or [])
                for slot, vals in neighbor_links.items():
                    if vals:
                        new_slots.add(slot)
                if new_slots:
                    validated['laje_vizinhas_niveis'] = sorted(new_slots)
        return neighbor_links

    def _ensure_slab_cut_view_links(self, slab: Dict) -> Dict:
        links = slab.setdefault('links', {})
        cut_links = links.setdefault('laje_visao_corte', {})
        if not isinstance(cut_links, dict):
            cut_links = {}
            links['laje_visao_corte'] = cut_links
        cut_links.setdefault('cut_view_geom', [])

        # Migra dados antigos sem apagar a fonte original. Assim as validacoes
        # humanas ja feitas em laje_nivel.cut_view_* continuam aproveitadas.
        old_level_links = links.get('laje_nivel', {})
        if isinstance(old_level_links, dict):
            for old in old_level_links.get('cut_view_geom', []) or []:
                self._append_unique_slab_link(cut_links['cut_view_geom'], old)

        validated = slab.setdefault('validated_link_classes', {})
        if isinstance(validated, dict):
            old_slots = set(validated.get('laje_nivel') or [])
            new_slots = set(validated.get('laje_visao_corte') or [])
            if 'cut_view_geom' in old_slots:
                new_slots.add('cut_view_geom')
            if new_slots:
                validated['laje_visao_corte'] = sorted(new_slots)
        return cut_links

    def _ensure_slab_support_pillar_links(self, slab: Dict) -> Dict:
        links = slab.setdefault('links', {})
        pillar_links = links.setdefault('laje_pilares_apoio', {})
        if not isinstance(pillar_links, dict):
            pillar_links = {}
            links['laje_pilares_apoio'] = pillar_links
        pillar_links.setdefault('pillar_geom', [])
        pillar_links.setdefault('pillar_label', [])
        return pillar_links

    def _parse_slab_level_value(self, raw):
        if raw is None:
            return None
        text = str(raw).strip()
        if not text or text.upper() in {'N/A', 'POLYLINE'}:
            return None
        upper = text.upper()
        if 'H=' in upper or upper.startswith('H') or upper.startswith('D='):
            return None
        import re
        m = re.search(r'[+-]?\d+(?:[\.,]\d+)?', text)
        if not m:
            return None
        try:
            return float(m.group(0).replace(',', '.'))
        except Exception:
            return None

    def _format_slab_level_value(self, value: float) -> str:
        text = f"{float(value):.2f}"
        return text.rstrip('0').rstrip('.') if '.' in text else text

    def _slab_cut_links(self, slab: Dict) -> list:
        cut_links = self._ensure_slab_cut_view_links(slab)
        cuts = []
        vals = cut_links.get('cut_view_geom', [])
        if isinstance(vals, list):
            cuts.extend(vals)
        return cuts

    def _slab_has_cut_view(self, slab: Dict) -> bool:
        return bool(self._slab_cut_links(slab))

    def _own_slab_level_links(self, slab: Dict) -> list:
        level_links = self._ensure_slab_level_links(slab)
        out = []
        for link in level_links.get('label', []) or []:
            if isinstance(link, dict) and self._parse_slab_level_value(link.get('text')) is not None:
                out.append(link)
        return out

    def _slab_name_dim_links(self, slab: Dict) -> list:
        links = slab.get('links', {}) if isinstance(slab.get('links'), dict) else {}
        out = []
        for field_id, slot_id in (('name', 'label'), ('laje_dim', 'label')):
            field_links = links.get(field_id, {})
            if not isinstance(field_links, dict):
                continue
            for link in field_links.get(slot_id, []) or []:
                if isinstance(link, dict) and link.get('text'):
                    out.append(link)
        return out

    def _slab_level_source(self, slab: Dict, include_neighbor_context: bool = True) -> dict | None:
        fields = slab.get('fields', {}) if isinstance(slab.get('fields'), dict) else {}
        level_links = self._ensure_slab_level_links(slab)
        neighbor_links = self._ensure_slab_neighbor_level_links(slab)
        validated_fields = slab.get('validated_fields', [])
        if isinstance(validated_fields, dict):
            validated_fields = list(validated_fields.keys())
        validated_fields = set(validated_fields or [])
        validated_slots = slab.get('validated_link_classes', {})
        level_valid_slots = set()
        if isinstance(validated_slots, dict):
            slots = validated_slots.get('laje_nivel', [])
            if isinstance(slots, list):
                level_valid_slots = set(slots)
        cut_valid_slots = set()
        if isinstance(validated_slots, dict):
            slots = validated_slots.get('laje_vizinhas_niveis', [])
            if isinstance(slots, list):
                cut_valid_slots = set(slots)

        raw_candidates = []
        if fields.get('laje_nivel') is not None:
            raw_candidates.append(('field', fields.get('laje_nivel'), 'laje_nivel' in validated_fields))
        if slab.get('laje_nivel') is not None:
            raw_candidates.append(('flat', slab.get('laje_nivel'), 'laje_nivel' in validated_fields))
        for link in level_links.get('label', []) or []:
            if not isinstance(link, dict):
                continue
            raw_candidates.append(('label', link.get('text'), bool(link.get('validated')) or 'label' in level_valid_slots))
        if include_neighbor_context:
            for slot in ('neighbor_north', 'neighbor_east', 'neighbor_west', 'neighbor_south'):
                for link in neighbor_links.get(slot, []) or []:
                    if isinstance(link, dict):
                        raw_candidates.append((slot, link.get('text'), bool(link.get('validated')) or slot in cut_valid_slots))

        best = None
        for kind, raw, is_human in raw_candidates:
            value = self._parse_slab_level_value(raw)
            if value is None:
                continue
            item = {'value': value, 'text': str(raw), 'kind': kind, 'human': bool(is_human)}
            if item['human']:
                return item
            if best is None:
                best = item
        return best

    def _slab_has_human_level(self, slab: Dict) -> bool:
        source = self._slab_level_source(slab, include_neighbor_context=False)
        return bool(source and source.get('human'))

    def _cut_link_bbox(self, link: dict):
        pts = link.get('points') if isinstance(link, dict) else None
        if not pts:
            return None
        try:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            return min(xs), min(ys), max(xs), max(ys)
        except Exception:
            return None

    def _same_cut_view_signature(self, a: dict, b: dict, tol: float = 25.0) -> bool:
        ba = self._cut_link_bbox(a)
        bb = self._cut_link_bbox(b)
        if not ba or not bb:
            return False
        ac = ((ba[0] + ba[2]) / 2.0, (ba[1] + ba[3]) / 2.0)
        bc = ((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)
        if ((ac[0] - bc[0]) ** 2 + (ac[1] - bc[1]) ** 2) ** 0.5 > tol:
            return False
        aw, ah = ba[2] - ba[0], ba[3] - ba[1]
        bw, bh = bb[2] - bb[0], bb[3] - bb[1]
        return abs(aw - bw) <= tol and abs(ah - bh) <= tol

    def _slab_polygon_map(self, slabs: list[Dict]) -> dict:
        from shapely.geometry import Polygon
        result = {}
        for slab in slabs:
            pts = slab.get('points') or []
            if len(pts) < 3:
                continue
            try:
                poly = Polygon(pts)
                if poly.is_valid and not poly.is_empty and poly.area > 0:
                    result[slab.get('id') or slab.get('name')] = poly
            except Exception:
                continue
        return result

    def _classify_slab_boundary_marker(self, pts: list, geom, bbox: tuple[float, float, float, float]) -> str:
        """Separa apoio compacto de pilar de marco de visao de corte."""
        if not pts or not bbox:
            return 'cut_view'
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if w <= 0 or h <= 0:
            return 'cut_view'
        closed = len(pts) >= 4 and pts[0] == pts[-1]
        aspect = max(w / max(h, 1.0), h / max(w, 1.0))
        fill_ratio = 0.0
        try:
            area = abs(float(getattr(geom, 'area', 0.0) or 0.0))
            fill_ratio = area / max(w * h, 1.0)
        except Exception:
            pass

        # Polígonos fechados quase sólidos com ≤6 pts são marcadores de apoio
        # (retângulos simples, incluindo os finos que escapariam do filtro de aspect).
        # T de visão de corte sempre têm fill ~0.5 (forma côncava) e ≥7 pts.
        if closed and fill_ratio >= 0.85 and len(pts) <= 6:
            return 'pillar'
        if closed and aspect <= 4.0 and len(pts) <= 6 and fill_ratio >= 0.70:
            return 'pillar'
        if closed and aspect <= 2.5 and len(pts) >= 10 and fill_ratio >= 0.65:
            return 'pillar'
        return 'cut_view'

    def _find_cut_view_web_extension(self, cut_pts: list) -> list | None:
        """
        Busca retângulo companheiro que completa o web do T no visão de corte.

        Visões de corte em T às vezes têm o fundo do web separado por linhas
        simbólicas da viga. O detector captura apenas a parte superior (T incompleto).
        Esta função localiza o retângulo compacto adjacente ao extremo do web
        e retorna os pontos do T estendidos para incluir o companheiro.
        Gap máximo tolerado: 8 unidades DXF.
        """
        if not cut_pts or len(cut_pts) < 7:
            return None
        if not getattr(self, 'dxf_data', None):
            return None
        try:
            from shapely.geometry import Polygon as _P
            xs = [float(p[0]) for p in cut_pts]
            ys = [float(p[1]) for p in cut_pts]
            main_minx, main_miny = min(xs), min(ys)
            main_maxx, main_maxy = max(xs), max(ys)
            main_w = main_maxx - main_minx
            main_h = main_maxy - main_miny
            GAP_MAX = 8.0

            def _edge_range(axis: str, side: str):
                frac = 0.40
                if axis == 'y':
                    lim = (main_miny + main_h * frac) if side == 'min' else (main_maxy - main_h * frac)
                    ep = [(float(p[0]), float(p[1])) for p in cut_pts
                          if (float(p[1]) <= lim if side == 'min' else float(p[1]) >= lim)]
                    if not ep:
                        return None, None, None
                    return (min(p[0] for p in ep), max(p[0] for p in ep),
                            main_miny if side == 'min' else main_maxy)
                else:
                    lim = (main_minx + main_w * frac) if side == 'min' else (main_maxx - main_w * frac)
                    ep = [(float(p[0]), float(p[1])) for p in cut_pts
                          if (float(p[0]) <= lim if side == 'min' else float(p[0]) >= lim)]
                    if not ep:
                        return None, None, None
                    return (min(p[1] for p in ep), max(p[1] for p in ep),
                            main_minx if side == 'min' else main_maxx)

            best_comp = None
            best_gap = float('inf')
            best_dir = None

            for axis in ('y', 'x'):
                for side in ('min', 'max'):
                    wr_min, wr_max, extreme = _edge_range(axis, side)
                    if wr_min is None:
                        continue
                    web_span = wr_max - wr_min
                    if web_span < 3.0:
                        continue
                    for item in self.dxf_data.get('polylines', []) or []:
                        p2 = item.get('points') or []
                        if len(p2) < 4 or len(p2) > 8 or p2[0] != p2[-1]:
                            continue
                        try:
                            cx = [float(q[0]) for q in p2]
                            cy = [float(q[1]) for q in p2]
                            c_minx, c_miny = min(cx), min(cy)
                            c_maxx, c_maxy = max(cx), max(cy)
                            cw, ch = c_maxx - c_minx, c_maxy - c_miny
                            if cw < 3 or ch < 3:
                                continue
                            fill = abs(float(_P(p2).area)) / max(cw * ch, 1.0)
                            if fill < 0.78:
                                continue
                            if axis == 'y':
                                overlap = min(c_maxx, wr_max) - max(c_minx, wr_min)
                                if overlap < web_span * 0.40:
                                    continue
                                if side == 'min':
                                    if c_maxy > extreme + 3:
                                        continue
                                    gap = extreme - c_maxy
                                else:
                                    if c_miny < extreme - 3:
                                        continue
                                    gap = c_miny - extreme
                            else:
                                overlap = min(c_maxy, wr_max) - max(c_miny, wr_min)
                                if overlap < web_span * 0.40:
                                    continue
                                if side == 'min':
                                    if c_maxx > extreme + 3:
                                        continue
                                    gap = extreme - c_maxx
                                else:
                                    if c_minx < extreme - 3:
                                        continue
                                    gap = c_minx - extreme
                            if 0 <= gap <= GAP_MAX and gap < best_gap:
                                best_gap = gap
                                best_comp = p2
                                best_dir = (axis, side)
                        except Exception:
                            continue
            if best_comp is None:
                return None
            return self._extend_t_with_companion(cut_pts, best_comp, best_dir)
        except Exception:
            return None

    def _extend_t_with_companion(self, t_pts: list, comp_pts: list, direction: tuple) -> list:
        """
        Estende os pontos do web do T até o fundo do retângulo companheiro.
        Substitui os pontos próximos ao extremo do web pela coordenada do companheiro.
        """
        try:
            axis, side = direction
            t_xs = [float(p[0]) for p in t_pts]
            t_ys = [float(p[1]) for p in t_pts]
            c_xs = [float(p[0]) for p in comp_pts]
            c_ys = [float(p[1]) for p in comp_pts]
            TOL = 5.0
            if axis == 'y' and side == 'min':
                t_ext, new_ext = min(t_ys), min(c_ys)
                return [[float(p[0]),
                         new_ext if abs(float(p[1]) - t_ext) < TOL else float(p[1])]
                        for p in t_pts]
            elif axis == 'y' and side == 'max':
                t_ext, new_ext = max(t_ys), max(c_ys)
                return [[float(p[0]),
                         new_ext if abs(float(p[1]) - t_ext) < TOL else float(p[1])]
                        for p in t_pts]
            elif axis == 'x' and side == 'min':
                t_ext, new_ext = min(t_xs), min(c_xs)
                return [[new_ext if abs(float(p[0]) - t_ext) < TOL else float(p[0]),
                         float(p[1])] for p in t_pts]
            else:
                t_ext, new_ext = max(t_xs), max(c_xs)
                return [[new_ext if abs(float(p[0]) - t_ext) < TOL else float(p[0]),
                         float(p[1])] for p in t_pts]
        except Exception:
            return list(t_pts)

    def _points_bbox_tuple(self, pts: list):
        if not pts:
            return None
        try:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            return min(xs), min(ys), max(xs), max(ys)
        except Exception:
            return None

    def _bbox_center_tuple(self, bbox):
        return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0) if bbox else (0.0, 0.0)

    def _slab_bounds(self, slab: Dict):
        return self._points_bbox_tuple(slab.get('points') or [])

    def _slab_cut_direction(self, slab: Dict, pts: list) -> str:
        sb = self._slab_bounds(slab)
        cb = self._points_bbox_tuple(pts)
        if not sb or not cb:
            return ''
        sx, sy = self._bbox_center_tuple(sb)
        cx, cy = self._bbox_center_tuple(cb)
        dx, dy = cx - sx, cy - sy
        if abs(dx) > abs(dy):
            return 'Leste' if dx > 0 else 'Oeste'
        return 'Norte' if dy > 0 else 'Sul'

    def _nearest_dxf_text(self, point, pattern=None, max_dist=900.0):
        import re
        if not getattr(self, 'dxf_data', None):
            return None
        best = None
        rx = re.compile(pattern, re.IGNORECASE) if pattern else None
        px, py = point
        for t in self.dxf_data.get('texts', []) or []:
            txt = str(t.get('text') or '').strip()
            if not txt:
                continue
            if rx and not rx.search(txt):
                continue
            pos = t.get('pos') or (0, 0)
            try:
                dist = ((float(pos[0]) - px) ** 2 + (float(pos[1]) - py) ** 2) ** 0.5
            except Exception:
                continue
            if dist <= max_dist and (best is None or dist < best[0]):
                best = (dist, t)
        return best[1] if best else None

    def _find_cut_view_cotas(self, pts: list, direction: str = '') -> dict:
        """
        Varre TODAS as cotas DXF (layer=2, h≈10, número isolado) próximas ao T e
        classifica cada uma por orientação e papel semântico.

        Classificação:
        - Texto LATERAL ao T (x fora, y dentro): cota VERTICAL
          → linhas horiz layer=9 dentro do y-range do T delimitam o span
          → se span cobre ≥70% da altura do T → beam_height
        - Texto ACIMA/ABAIXO do T: cota HORIZONTAL
          → se span ≤ largura do T → bw (largura nervura)
          → se span > largura do T → slab_extent (ignorar)
        - Distante ou marginal → unknown

        Retorna:
          beam_height_cota  – valor anotado da altura real (ex: 120.0)
          beam_height_span_dxf – span DXF correspondente (ex: 60.0)
          scale_v           – cota/geo ratio (ex: 2.0)
          bw_cota           – largura do web anotada (ex: 19.0)
          all_cotas         – lista completa para debug
        """
        import re as _re
        if not pts or not getattr(self, 'dxf_data', None):
            return {}

        all_texts = self.dxf_data.get('texts') or []
        all_lines = self.dxf_data.get('lines') or []

        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        tx0, ty0, tx1, ty1 = min(xs), min(ys), max(xs), max(ys)
        cx, cy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
        tw, th = tx1 - tx0, ty1 - ty0

        RX = max(tw * 3.0, 200.0)
        RY = max(th * 3.0, 200.0)
        _num_re = _re.compile(r'^\d+(?:[.,]\d+)?$')

        cota_texts = []
        for t in all_texts:
            if str(t.get('layer', '')) not in ('2', 2):
                continue
            h = float(t.get('height') or 0)
            if not (7.0 <= h <= 14.0):
                continue
            txt = str(t.get('text') or '').strip()
            if not _num_re.match(txt):
                continue
            val = float(txt.replace(',', '.'))
            pos = t.get('pos') or (0, 0)
            px, py = float(pos[0]), float(pos[1])
            if abs(px - cx) > RX or abs(py - cy) > RY:
                continue
            cota_texts.append({'val': val, 'x': px, 'y': py, 'raw': txt})

        if not cota_texts:
            return {}

        search_r = max(th, tw, 130.0)

        def _ext_lines(px, py):
            horiz, vert = [], []
            for l in all_lines:
                if str(l.get('layer', '')) not in ('9', 9):
                    continue
                s = l.get('start') or (0, 0)
                e = l.get('end') or (0, 0)
                sx, sy = float(s[0]), float(s[1])
                ex, ey = float(e[0]), float(e[1])
                dx, dy = abs(ex - sx), abs(ey - sy)
                mcx, mcy = (sx + ex) / 2, (sy + ey) / 2
                if abs(mcx - px) > search_r or abs(mcy - py) > search_r:
                    continue
                if dy < 2.0 and dx > 2.0:
                    horiz.append({'y': (sy + ey) / 2, 'x0': min(sx, ex), 'x1': max(sx, ex), 'len': dx})
                elif dx < 2.0 and dy > 2.0:
                    vert.append({'x': (sx + ex) / 2, 'y0': min(sy, ey), 'y1': max(sy, ey), 'len': dy})
            return horiz, vert

        classified = []
        for ct in cota_texts:
            px, py = ct['x'], ct['y']
            val = ct['val']
            horiz_lines, vert_lines = _ext_lines(px, py)

            info = dict(ct)
            info['n_horiz'] = len(horiz_lines)
            info['n_vert'] = len(vert_lines)

            left_of_T  = px < tx0 - 5
            right_of_T = px > tx1 + 5
            above_T    = py > ty1 + 5
            below_T    = py < ty0 - 5
            y_in_T     = ty0 - 12 <= py <= ty1 + 12
            x_in_T     = tx0 - 12 <= px <= tx1 + 12

            # ── COTA VERTICAL: texto lateral, y dentro do T ──────────────────
            if (left_of_T or right_of_T) and y_in_T:
                # Só inclui linhas horizontais que estejam dentro do y-range do T
                # (± margem estreita). Linhas de cotas de abas acima do T são excluídas.
                _y_margin = max(th * 0.25, 15.0)
                ys_span = sorted({
                    round(h_['y'], 2)
                    for h_ in horiz_lines
                    if ty0 - _y_margin <= h_['y'] <= ty1 + _y_margin
                })
                if len(ys_span) >= 2:
                    span_y0, span_y1 = ys_span[0], ys_span[-1]
                    span_dxf = span_y1 - span_y0
                    info['orientation'] = 'vertical'
                    info['span_y0'] = round(span_y0, 2)
                    info['span_y1'] = round(span_y1, 2)
                    info['span_dxf'] = round(span_dxf, 2)

                    ov_y0 = max(span_y0, ty0)
                    ov_y1 = min(span_y1, ty1)
                    ov_frac = max(0.0, ov_y1 - ov_y0) / max(th, 1)

                    if ov_frac >= 0.70 and 20 <= val <= 600 and span_dxf > 0:
                        info['role'] = 'beam_height'
                        info['scale_v'] = round(val / span_dxf, 4)
                    else:
                        info['role'] = 'vertical_other'
                else:
                    info['orientation'] = 'vertical_no_span'
                    info['role'] = 'unknown'

            # ── COTA HORIZONTAL: texto acima/abaixo do T ─────────────────────
            elif above_T or below_T:
                h_at_level = [h_ for h_ in horiz_lines if abs(h_['y'] - py) < max(th, 60.0)]
                if h_at_level:
                    best_h = min(h_at_level, key=lambda h_: abs(h_['len'] - val))
                    span_dxf = best_h['len']
                    info['orientation'] = 'horizontal'
                    info['span_x0'] = round(best_h['x0'], 2)
                    info['span_x1'] = round(best_h['x1'], 2)
                    info['span_dxf'] = round(span_dxf, 2)

                    within_T_x = (tx0 - 30 <= best_h['x0'] and best_h['x1'] <= tx1 + 30)
                    if within_T_x and span_dxf <= tw + 5 and 5 <= val:
                        info['role'] = 'bw'
                    elif span_dxf > tw * 0.8:
                        info['role'] = 'slab_extent'
                    else:
                        info['role'] = 'horizontal_other'
                else:
                    info['orientation'] = 'horizontal_no_span'
                    info['role'] = 'unknown'

            elif x_in_T and y_in_T:
                info['orientation'] = 'internal'
                info['role'] = 'internal'
            else:
                info['orientation'] = 'unknown'
                info['role'] = 'unknown'

            classified.append(info)

        result = {'all_cotas': classified}

        # Melhor beam_height: cota vertical com maior sobreposição com o T
        bh_cotas = [c for c in classified if c.get('role') == 'beam_height']
        if bh_cotas:
            best_bh = max(bh_cotas, key=lambda c: (
                max(0.0, min(c.get('span_y1', 0), ty1) - max(c.get('span_y0', 0), ty0)) / max(th, 1)
            ))
            result['beam_height_cota'] = best_bh['val']
            result['beam_height_span_dxf'] = best_bh.get('span_dxf', 0)
            result['scale_v'] = best_bh.get('scale_v', 1.0)

        # Melhor bw: cota horizontal mais próxima ao topo do T (logo acima da nervura)
        bw_cotas = [c for c in classified if c.get('role') == 'bw']
        if bw_cotas:
            result['bw_cota'] = min(bw_cotas, key=lambda c: abs(c['y'] - (ty1 + 30)))['val']

        return result

    def _slab_dim_text(self, slab: Dict) -> str:
        fields = slab.get('fields', {}) if isinstance(slab.get('fields'), dict) else {}
        raw = fields.get('laje_dim') or slab.get('laje_dim')
        if raw:
            return str(raw)
        links = slab.get('links', {}) if isinstance(slab.get('links'), dict) else {}
        for link in (links.get('laje_dim', {}) or {}).get('label', []) if isinstance(links.get('laje_dim', {}), dict) else []:
            if isinstance(link, dict) and link.get('text'):
                return str(link.get('text'))
        return ''

    def _slab_height_value(self, slab: Dict) -> str:
        import re
        raw = self._slab_dim_text(slab)
        m = re.search(r'\d+(?:[\.,]\d+)?', raw or '')
        return m.group(0).replace(',', '.') if m else raw

    def _opposite_direction_key(self, direction: str) -> str:
        # Mapeia direcao do corte para a chave usada por _orthogonal_neighbor_slabs.
        # O vizinho esta NO MESMO LADO que 'direction' (Norte -> laje vizinha ao norte -> 'top').
        d = str(direction or '').lower()
        if d.startswith('n'): return 'top'
        if d.startswith('s'): return 'bottom'
        if d.startswith('l') or d.startswith('e'): return 'right'
        if d.startswith('o') or d.startswith('w'): return 'left'
        return ''

    def _neighbor_by_direction(self, slab: Dict, slabs: list[Dict], poly_map: dict, direction: str):
        target_key = self._opposite_direction_key(direction)
        best = None
        for dist, dir_key, other in self._orthogonal_neighbor_slabs(slab, slabs, poly_map, max_dist=85.0):
            if dir_key == target_key and (best is None or dist < best[0]):
                best = (dist, other)
        return best[1] if best else None

    def _polygon_x_at_y(self, pts: list, y_mid: float) -> list:
        """Intersecoes em X do poligono fechado para a scanline Y=y_mid."""
        xs = []
        n = len(pts)
        for i in range(n):
            x1, y1 = float(pts[i][0]), float(pts[i][1])
            x2, y2 = float(pts[(i + 1) % n][0]), float(pts[(i + 1) % n][1])
            if y1 == y2:
                continue
            if min(y1, y2) <= y_mid <= max(y1, y2):
                xs.append(x1 + (y_mid - y1) * (x2 - x1) / (y2 - y1))
        return xs

    def _polygon_y_at_x(self, pts: list, x_mid: float) -> list:
        """Intersecoes em Y do poligono fechado para a scanline X=x_mid."""
        ys = []
        n = len(pts)
        for i in range(n):
            x1, y1 = float(pts[i][0]), float(pts[i][1])
            x2, y2 = float(pts[(i + 1) % n][0]), float(pts[(i + 1) % n][1])
            if x1 == x2:
                continue
            if min(x1, x2) <= x_mid <= max(x1, x2):
                ys.append(y1 + (x_mid - x1) * (y2 - y1) / (x2 - x1))
        return ys

    def _parse_cut_poly_sections(self, pts: list, direction: str) -> dict:
        """
        Decompoe o poligono em degrau da visao de corte.

        Retorna:
          beam_height      — altura estrutural real da viga (eixo de elevacao)
          bw               — largura da nervura da viga no plano
          own_slab_h       — espessura da laje propria (eixo de elevacao)
          neigh_slab_h     — espessura da laje vizinha
          own_dist_topo    — distancia do topo da laje propria ao topo da viga
          own_dist_fundo   — distancia do fundo da viga ao fundo da laje propria
          neigh_dist_topo  — idem para laje vizinha
          neigh_dist_fundo — idem para laje vizinha
          own_overhang     — saliencia horizontal da laje propria alem da nervura
          neigh_overhang   — saliencia horizontal da laje vizinha

        Convencao de eixos no DXF:
          Corte E-W (Leste/Oeste): Y = elevacao estrutural, maior Y = topo
          Corte N-S (Norte/Sul):   X = elevacao estrutural, menor X = topo
        """
        if not pts:
            return {}
        try:
            d = str(direction or '').strip().lower()
            ns_cut = d.startswith('n') or d.startswith('s')
            all_xs = [float(p[0]) for p in pts]
            all_ys = [float(p[1]) for p in pts]

            if ns_cut:
                # Fatias em Y; extensao X = eixo de elevacao (menor X = topo estrutural)
                ys_uniq = sorted(set(round(float(p[1]), 2) for p in pts))
                bands = []
                for i in range(len(ys_uniq) - 1):
                    y_mid = (ys_uniq[i] + ys_uniq[i + 1]) / 2
                    xv = self._polygon_x_at_y(pts, y_mid)
                    if len(xv) >= 2:
                        bands.append({
                            'coord_min': ys_uniq[i], 'coord_max': ys_uniq[i + 1],
                            'span': ys_uniq[i + 1] - ys_uniq[i],
                            'width': max(xv) - min(xv),
                        })
                if not bands:
                    return {}
                beam = max(bands, key=lambda b: b['width'])
                x_min = min(all_xs)
                x_max = max(all_xs)
                beam_height = round(x_max - x_min, 1)
                bw = round(beam['span'], 1)
                neighbor_toward_positive = d.startswith('n')
                if neighbor_toward_positive:
                    tab_n = [b for b in bands if b['coord_min'] >= beam['coord_max']]
                    tab_o = [b for b in bands if b['coord_max'] <= beam['coord_min']]
                else:
                    tab_n = [b for b in bands if b['coord_max'] <= beam['coord_min']]
                    tab_o = [b for b in bands if b['coord_min'] >= beam['coord_max']]

                def _tab_ns(tab_bands):
                    if not tab_bands:
                        return None
                    b = min(tab_bands, key=lambda bb: abs(
                        (bb['coord_min'] + bb['coord_max']) / 2
                        - (beam['coord_min'] + beam['coord_max']) / 2))
                    y_mid = (b['coord_min'] + b['coord_max']) / 2
                    xv = self._polygon_x_at_y(pts, y_mid)
                    if len(xv) < 2:
                        return None
                    tx_min = min(xv)
                    tx_max = max(xv)
                    return {
                        'slab_h': round(tx_max - tx_min, 1),
                        'dist_topo': round(tx_min - x_min, 1),
                        'dist_fundo': round(x_max - tx_max, 1),
                        'overhang': round(sum(bb['span'] for bb in tab_bands), 1),
                    }

                own_d = _tab_ns(tab_o)
                neigh_d = _tab_ns(tab_n)
            else:
                # Fatias em X; extensao Y = eixo de elevacao (maior Y = topo estrutural)
                xs_uniq = sorted(set(round(float(p[0]), 2) for p in pts))
                bands = []
                for i in range(len(xs_uniq) - 1):
                    x_mid = (xs_uniq[i] + xs_uniq[i + 1]) / 2
                    yv = self._polygon_y_at_x(pts, x_mid)
                    if len(yv) >= 2:
                        bands.append({
                            'coord_min': xs_uniq[i], 'coord_max': xs_uniq[i + 1],
                            'span': xs_uniq[i + 1] - xs_uniq[i],
                            'width': max(yv) - min(yv),
                        })
                if not bands:
                    return {}
                beam = max(bands, key=lambda b: b['width'])
                y_min = min(all_ys)
                y_max = max(all_ys)
                beam_height = round(y_max - y_min, 1)
                bw = round(beam['span'], 1)
                neighbor_toward_positive = d.startswith('l') or d.startswith('e')
                if neighbor_toward_positive:
                    tab_n = [b for b in bands if b['coord_min'] >= beam['coord_max']]
                    tab_o = [b for b in bands if b['coord_max'] <= beam['coord_min']]
                else:
                    tab_n = [b for b in bands if b['coord_max'] <= beam['coord_min']]
                    tab_o = [b for b in bands if b['coord_min'] >= beam['coord_max']]

                def _tab_ew(tab_bands):
                    if not tab_bands:
                        return None
                    b = min(tab_bands, key=lambda bb: abs(
                        (bb['coord_min'] + bb['coord_max']) / 2
                        - (beam['coord_min'] + beam['coord_max']) / 2))
                    x_mid = (b['coord_min'] + b['coord_max']) / 2
                    yv = self._polygon_y_at_x(pts, x_mid)
                    if len(yv) < 2:
                        return None
                    ty_min = min(yv)
                    ty_max = max(yv)
                    return {
                        'slab_h': round(ty_max - ty_min, 1),
                        'dist_topo': round(y_max - ty_max, 1),
                        'dist_fundo': round(ty_min - y_min, 1),
                        'overhang': round(sum(bb['span'] for bb in tab_bands), 1),
                    }

                own_d = _tab_ew(tab_o)
                neigh_d = _tab_ew(tab_n)

            return {
                'beam_height': beam_height,
                'bw': bw,
                'own_slab_h': (own_d or {}).get('slab_h', 0),
                'neigh_slab_h': (neigh_d or {}).get('slab_h', 0),
                'own_dist_topo': (own_d or {}).get('dist_topo', 0),
                'own_dist_fundo': (own_d or {}).get('dist_fundo', 0),
                'neigh_dist_topo': (neigh_d or {}).get('dist_topo', 0),
                'neigh_dist_fundo': (neigh_d or {}).get('dist_fundo', 0),
                'own_overhang': (own_d or {}).get('overhang', 0),
                'neigh_overhang': (neigh_d or {}).get('overhang', 0),
                # compatibilidade legado
                'beam_bottom_dim': bw,
                'own_tab_h': (own_d or {}).get('slab_h', 0),
                'neighbor_tab_h': (neigh_d or {}).get('slab_h', 0),
            }
        except Exception:
            return {}

    def _infer_slab_position(self, own_tab_h: float, own_h: float, beam_h: float) -> str:
        """Infere posicao da laje (topo/fundo/centro) com base nas abas do corte."""
        if own_h <= 0 or beam_h <= 0:
            return 'centro'
        flush_tol = own_h * 0.15
        if own_tab_h <= flush_tol:
            return 'topo'
        if abs(own_tab_h - own_h) <= flush_tol:
            return 'fundo'
        return 'centro'

    def _auto_fill_cut_view_ficha(self, slab: Dict, link: dict, slabs: list[Dict], poly_map: dict) -> None:
        if not isinstance(link, dict):
            return
        import re as _re
        ficha = link.setdefault('ficha', {})
        pts = link.get('points') or []
        bb = self._points_bbox_tuple(pts)
        center = self._bbox_center_tuple(bb)
        direction = ficha.get('direction') or self._slab_cut_direction(slab, pts)
        neighbor = self._neighbor_by_direction(slab, slabs, poly_map, direction) if direction else None
        own_h_str = self._slab_height_value(slab)
        neigh_h_str = self._slab_height_value(neighbor) if neighbor else ''

        ficha.setdefault('direction', direction)
        # Lado A = fundo/esquerda (Sul ou Oeste do beam), Lado B = topo/direita (Norte ou Leste do beam).
        # direction = direcao do centro da laje atual ate o poligono do corte:
        #   "Norte"/"Leste" → laje atual esta ao Sul/Oeste do beam → Lado A
        #   "Sul"/"Oeste"   → laje atual esta ao Norte/Leste do beam → Lado B
        _d = (direction or '').lower()
        _current_is_a = _d.startswith('n') or _d.startswith('l') or _d.startswith('e')
        if _current_is_a:
            ficha['side_a_laje_name']   = slab.get('name') or ''
            ficha['side_a_laje_height'] = self._slab_dim_text(slab) or own_h_str
            ficha['side_b_laje_name']   = (neighbor or {}).get('name') or 'nulo'
            ficha['side_b_laje_height'] = self._slab_dim_text(neighbor) if neighbor else 'nulo'
            ficha['beam_lajes_side_a']  = '1'
            ficha['beam_lajes_side_b']  = '1' if neighbor else '0'
        else:
            ficha['side_b_laje_name']   = slab.get('name') or ''
            ficha['side_b_laje_height'] = self._slab_dim_text(slab) or own_h_str
            ficha['side_a_laje_name']   = (neighbor or {}).get('name') or 'nulo'
            ficha['side_a_laje_height'] = self._slab_dim_text(neighbor) if neighbor else 'nulo'
            ficha['beam_lajes_side_a']  = '1' if neighbor else '0'
            ficha['beam_lajes_side_b']  = '1'
        ficha.setdefault('own_height', own_h_str)
        ficha.setdefault('neighbor_height', neigh_h_str or 'nulo')

        # --- COTAS DXF: lê TODAS as cotas anotadas próximas ao T (PRIMÁRIO) --------
        # Abordagem correta: medidas vêm das cotas anotadas, não da geometria bruta.
        # Cruzamento: beam_height (cota) × slab_height (laje) → dist_bottom/top.
        # Fallback: geometria × scale_v para casos sem cotas.
        cotas = self._find_cut_view_cotas(pts, direction)
        link['cotas_debug'] = {
            'n_cotas': len(cotas.get('all_cotas') or []),
            'beam_height_cota': cotas.get('beam_height_cota'),
            'scale_v': cotas.get('scale_v', 1.0),
            'bw_cota': cotas.get('bw_cota'),
        }

        # --- extrai dimensoes geometricas (FALLBACK / calibração) ----------------
        geo = self._parse_cut_poly_sections(pts, direction)
        if geo:
            beam_h_geo   = geo.get('beam_height', 0.0)
            bw           = geo.get('bw', 0.0)
            own_slab_h_geo   = geo.get('own_slab_h', 0.0)
            neigh_slab_h_geo = geo.get('neigh_slab_h', 0.0)
            own_dt_geo   = geo.get('own_dist_topo', 0.0)
            own_df_geo   = geo.get('own_dist_fundo', 0.0)
            neigh_dt_geo = geo.get('neigh_dist_topo', 0.0)
            neigh_df_geo = geo.get('neigh_dist_fundo', 0.0)

            # scale_v confirmado: só aplica se razão é coerente (0.5–4×).
            # Cota com razão > 4 é dimensão de andar/seção, não altura de viga → rejeita.
            bh_cota = cotas.get('beam_height_cota')
            scale_v = 1.0
            if bh_cota and beam_h_geo > 0:
                ratio = bh_cota / beam_h_geo
                if 0.5 <= ratio <= 4.0:
                    scale_v = ratio
                else:
                    bh_cota = None  # razão incoerente: cota de seção, não de viga
            link['cotas_debug']['scale_v_confirmed'] = round(scale_v, 4)

            try:
                own_h_val = float(own_h_str or 0)
            except Exception:
                own_h_val = 0.0
            try:
                neigh_h_val = float(neigh_h_str or 0)
            except Exception:
                neigh_h_val = 0.0

            # ── CRUZAMENTO: usa laje_height + beam_height_cota (mais preciso) ──
            # dist_bottom = beam_height - slab_height (resíduo abaixo da laje).
            # Atribuição direta (não setdefault) para sempre recompor com dados atuais.
            if bh_cota:
                beam_h = bh_cota
                if own_h_val > 0:
                    own_slab_h = own_h_val
                    own_dt = own_dt_geo
                    own_df = round(bh_cota - own_slab_h - own_dt, 1)
                else:
                    own_slab_h = round(own_slab_h_geo * scale_v, 1)
                    own_dt = round(own_dt_geo * scale_v, 1)
                    own_df = round(own_df_geo * scale_v, 1)

                if neigh_h_val > 0:
                    neigh_slab_h = neigh_h_val
                    neigh_dt = neigh_dt_geo
                    neigh_df = round(bh_cota - neigh_slab_h - neigh_dt, 1)
                else:
                    neigh_slab_h = round(neigh_slab_h_geo * scale_v, 1)
                    neigh_dt = round(neigh_dt_geo * scale_v, 1)
                    neigh_df = round(neigh_df_geo * scale_v, 1)
            else:
                # sem cota: aplica scale_v a todos os campos verticais
                beam_h = round(beam_h_geo * scale_v, 1)
                own_slab_h   = round(own_slab_h_geo * scale_v, 1)
                neigh_slab_h = round(neigh_slab_h_geo * scale_v, 1)
                own_dt       = round(own_dt_geo * scale_v, 1)
                own_df       = round(own_df_geo * scale_v, 1)
                neigh_dt     = round(neigh_dt_geo * scale_v, 1)
                neigh_df     = round(neigh_df_geo * scale_v, 1)
                # Fallback: geo não detectou aba mas temos dimensão real da laje →
                # usa laje_dim para own_slab_h e cruza para own_dist_bottom.
                if own_slab_h == 0.0 and own_h_val > 0 and beam_h > 0:
                    own_slab_h = own_h_val
                    own_dt = 0.0
                    own_df = round(beam_h - own_slab_h, 1)
                if neigh_slab_h == 0.0 and neigh_h_val > 0 and beam_h > 0:
                    neigh_slab_h = neigh_h_val
                    neigh_dt = 0.0
                    neigh_df = round(beam_h - neigh_slab_h, 1)

            # Campos informacionais são SEMPRE recomputados no re-analyze.
            # A proteção do link validado é geométrica (não duplica a geometria),
            # nunca informacional — o usuário confia no auto-preenchimento dos campos
            # e valida apenas que a geometria é a correta.
            ficha['beam_height']          = str(beam_h)
            ficha.setdefault('beam_bottom_dim', str(bw))
            ficha['scale_v']              = str(round(scale_v, 4))
            ficha['own_dist_top']         = str(own_dt)
            ficha['own_dist_bottom']      = str(own_df)
            ficha['neighbor_dist_top']    = str(neigh_dt)
            ficha['neighbor_dist_bottom'] = str(neigh_df)
            ficha['own_slab_height']      = str(own_slab_h)
            ficha['neigh_slab_height']    = str(neigh_slab_h) if neigh_slab_h else 'nulo'

            pos = self._infer_slab_position(own_dt, own_h_val or own_slab_h, beam_h)
            ficha['own_position']      = pos
            n_pos = self._infer_slab_position(neigh_dt, neigh_h_val or neigh_slab_h, beam_h) if (neigh_h_val or neigh_slab_h) else 'nulo'
            ficha['neighbor_position'] = n_pos if neighbor else 'nulo'
        else:
            ficha['own_position']         = 'centro'
            ficha['neighbor_position']    = 'centro' if neighbor else 'nulo'
            ficha['own_dist_top']         = ''
            ficha['own_dist_bottom']      = ''
            ficha['neighbor_dist_top']    = ''
            ficha['neighbor_dist_bottom'] = ''
            ficha['own_slab_height']      = ''
            ficha['neigh_slab_height']    = 'nulo'

        # --- nome e dimensoes da viga via textos DXF proximos ---
        beam_name = self._nearest_dxf_text(center, r'^(VF?\d+|V\d+)$', max_dist=1400.0)
        if beam_name:
            ficha.setdefault('beam_name', str(beam_name.get('text') or ''))
        beam_dim_txt = self._nearest_dxf_text(center, r'\d+\s*[xX/]\s*\d+', max_dist=450.0)
        if beam_dim_txt:
            txt = str(beam_dim_txt.get('text') or '')
            nums = _re.findall(r'\d+(?:[\.,]\d+)?', txt)
            if nums:
                ficha.setdefault('beam_bottom_dim', nums[0].replace(',', '.'))
            if len(nums) >= 2:
                ficha.setdefault('beam_height', nums[1].replace(',', '.'))
            fl = link.setdefault('ficha_links', {})
            for key in ('beam_bottom_dim', 'beam_height'):
                fl.setdefault(key, [])
                if not fl[key]:
                    lk = dict(beam_dim_txt)
                    lk['role'] = f'Ficha_{key}'
                    fl[key] = [lk]
        if beam_name:
            fl = link.setdefault('ficha_links', {})
            fl.setdefault('beam_name', [])
            if not fl['beam_name']:
                lk = dict(beam_name)
                lk['role'] = 'Ficha_beam_name'
                fl['beam_name'] = [lk]

        # --- altura da viga via label de cota standalone (ex: "120") ---
        # Cortes de detalhe desenhados em escala 1:2 têm a altura real anotada
        # como número isolado dentro ou muito próximo da bbox do T.
        # Esse label (ex: "120") é a medida real da viga em cm — mais confiável
        # que o valor geométrico bruto do DXF (que seria metade em escala 1:2).
        if bb:
            _tx0, _ty0, _tx1, _ty1 = bb
            _t_h = _ty1 - _ty0
            _label_txt = self._nearest_dxf_text(
                center, r'^\d+(?:[.,]\d+)?$', max_dist=max(80.0, _t_h * 1.5))
            if _label_txt:
                _lv = _label_txt.get('text') or ''
                try:
                    _lv_f = float(_lv.replace(',', '.'))
                    _lpos = _label_txt.get('pos') or center
                    # Aceitar apenas se o label está dentro ou encostado na bbox do T
                    # e o valor é compatível com altura de viga (20-600 cm)
                    _in_box = (_tx0 - 80 <= float(_lpos[0]) <= _tx1 + 80 and
                               _ty0 - 30 <= float(_lpos[1]) <= _ty1 + 30)
                    if _in_box and 20.0 <= _lv_f <= 600.0:
                        ficha['beam_height_label'] = str(_lv_f)
                        _old_bh_str = ficha.get('beam_height')
                        # Override beam_height com o valor anotado (mais preciso).
                        ficha['beam_height'] = str(_lv_f)
                        # Se o label mudou o beam_height, recomputa own e neigh dist_bottom.
                        # Estratégia own: usa height real da laje própria (já em ficha['own_slab_height']).
                        # Estratégia neigh: prefere height real (neighbor_height) ou, sem vizinho real,
                        # reescala valores geométricos na proporção label / old_bh.
                        try:
                            _old_bh_f = float(_old_bh_str) if _old_bh_str else None
                            if _old_bh_f is None or abs(_lv_f - _old_bh_f) > 0.5:
                                # --- own ---
                                _oh = float(ficha.get('own_slab_height') or 0)
                                _dt = float(ficha.get('own_dist_top') or 0)
                                if _oh > 0:
                                    ficha['own_dist_bottom'] = str(round(_lv_f - _oh - _dt, 1))
                                # --- neigh ---
                                _nh_real_str = ficha.get('neighbor_height') or ''
                                _nh_real = (float(_nh_real_str)
                                            if str(_nh_real_str) not in ('nulo', '', 'None') else 0.0)
                                _ndt = float(ficha.get('neighbor_dist_top') or 0)
                                if _nh_real > 0:
                                    # Laje vizinha real conhecida — apenas corrige dist_bottom
                                    ficha['neighbor_dist_bottom'] = str(round(_lv_f - _nh_real - _ndt, 1))
                                else:
                                    # Sem vizinha real: reescala valores geométricos
                                    _nh_geo_str = ficha.get('neigh_slab_height') or '0'
                                    _nh_geo = (float(_nh_geo_str)
                                               if str(_nh_geo_str) not in ('nulo', '', 'None') else 0.0)
                                    if _nh_geo > 0 and _old_bh_f and _old_bh_f > 0:
                                        _sc = _lv_f / _old_bh_f
                                        _nh_sc = round(_nh_geo * _sc, 1)
                                        _ndt_sc = round(_ndt * _sc, 1)
                                        ficha['neigh_slab_height'] = str(_nh_sc)
                                        ficha['neighbor_dist_top'] = str(_ndt_sc)
                                        ficha['neighbor_dist_bottom'] = str(round(_lv_f - _nh_sc - _ndt_sc, 1))
                        except (ValueError, TypeError):
                            pass
                        fl2 = link.setdefault('ficha_links', {})
                        fl2.setdefault('beam_height_label', [])
                        if not fl2['beam_height_label']:
                            lk2 = dict(_label_txt)
                            lk2['role'] = 'Ficha_beam_height_label'
                            fl2['beam_height_label'] = [lk2]
                except (ValueError, TypeError):
                    pass

        # Consistência final: garante h + dt + df == beam_height para own e neigh.
        # Necessário quando standalone label muda bh mas neigh_df já estava correto
        # da execução anterior (abs(old-new)=0 → recompute não disparou).
        try:
            _bh_f = float(ficha.get('beam_height') or 0)
            if _bh_f > 0:
                for _h_k, _dt_k, _df_k in [
                    ('own_slab_height', 'own_dist_top', 'own_dist_bottom'),
                    ('neigh_slab_height', 'neighbor_dist_top', 'neighbor_dist_bottom'),
                ]:
                    try:
                        _h_v = float(ficha.get(_h_k) or 0)
                        _dt_v = float(ficha.get(_dt_k) or 0)
                        _df_v = float(ficha.get(_df_k) or 0)
                        if _h_v > 0 and _dt_v >= 0 and _df_v >= 0:
                            if abs(_h_v + _dt_v + _df_v - _bh_f) > 1.0:
                                ficha[_df_k] = str(round(_bh_f - _h_v - _dt_v, 1))
                    except (ValueError, TypeError):
                        pass
        except (ValueError, TypeError):
            pass

        # --- Campos com painel (2 cm), sarrafo de fundo (+4 cm) e fórmulas explicativas ---
        # A distância TOPO e FUNDO têm como referência a ALTURA DA LAJE (H_laje),
        # não a espessura bruta do corte.
        # Fórmula: dist_fundo = beam_height − H_laje − dist_topo
        # Com painel (2 cm) e sarrafo+painel do fundo da viga (4 cm):
        # dist_fundo_c_painel = dist_fundo − 2 + 4
        _PAINEL = 2.0
        _FUNDO_VIGA = 4.0
        ficha['painel_espessura'] = str(_PAINEL)
        ficha['fundo_viga_acrescimo'] = str(_FUNDO_VIGA)
        try:
            _bh_p = float(ficha.get('beam_height') or 0)
            if _bh_p > 0:
                # ── Lado próprio ──
                _oh = 0.0
                _oh_str = ficha.get('own_slab_height') or ''
                if _oh_str and _oh_str not in ('nulo', '', 'None'):
                    try:
                        _oh = float(_oh_str)
                    except (ValueError, TypeError):
                        pass
                _odt_str = ficha.get('own_dist_top') or '0'
                _odf_str = ficha.get('own_dist_bottom') or '0'
                try:
                    _odt = float(_odt_str)
                except (ValueError, TypeError):
                    _odt = 0.0
                try:
                    _odf = float(_odf_str)
                except (ValueError, TypeError):
                    _odf = 0.0
                if _oh > 0:
                    ficha['own_slab_ref_c_painel'] = str(round(_oh + _PAINEL, 1))
                    ficha['own_dist_top_c_painel'] = _odt_str  # painel é abaixo → topo inalterado
                    ficha['own_dist_bottom_s_painel'] = _odf_str
                    ficha['own_dist_bottom_c_painel'] = str(round(_odf - _PAINEL + _FUNDO_VIGA, 1))
                    ficha['own_dist_topo_formula'] = (
                        f"bh({_bh_p:.0f}) − H_laje({_oh:.0f}) − d_fundo({_odf:.0f})"
                        f" = {_odt:.0f} cm"
                    )
                    ficha['own_dist_fundo_formula'] = (
                        f"bh({_bh_p:.0f}) − H_laje({_oh:.0f}) − d_topo({_odt:.0f})"
                        f" = {_odf:.0f} cm (sem painel)"
                        f" / {(_odf - _PAINEL + _FUNDO_VIGA):.0f} cm (−{_PAINEL:.0f}cm painel da laje + {_FUNDO_VIGA:.0f}cm sarrafo/fundo viga)"
                    )

                # ── Lado vizinho ──
                _nh_str = ficha.get('neigh_slab_height') or 'nulo'
                _ndt_str = ficha.get('neighbor_dist_top') or '0'
                _ndf_str = ficha.get('neighbor_dist_bottom') or '0'
                if _nh_str not in ('nulo', '', 'None'):
                    try:
                        _nh = float(_nh_str)
                        _ndt = float(_ndt_str)
                        _ndf = float(_ndf_str)
                        if _nh > 0:
                            ficha['neigh_slab_ref_c_painel'] = str(round(_nh + _PAINEL, 1))
                            ficha['neighbor_dist_top_c_painel'] = _ndt_str  # topo inalterado
                            ficha['neighbor_dist_bottom_s_painel'] = _ndf_str
                            ficha['neighbor_dist_bottom_c_painel'] = str(round(_ndf - _PAINEL + _FUNDO_VIGA, 1))
                            ficha['neigh_dist_topo_formula'] = (
                                f"bh({_bh_p:.0f}) − H_laje_viz({_nh:.0f}) − d_fundo({_ndf:.0f})"
                                f" = {_ndt:.0f} cm"
                            )
                            ficha['neigh_dist_fundo_formula'] = (
                                f"bh({_bh_p:.0f}) − H_laje_viz({_nh:.0f}) − d_topo({_ndt:.0f})"
                                f" = {_ndf:.0f} cm (sem painel)"
                                f" / {(_ndf - _PAINEL + _FUNDO_VIGA):.0f} cm (−{_PAINEL:.0f}cm painel da laje + {_FUNDO_VIGA:.0f}cm sarrafo/fundo viga)"
                            )
                    except (ValueError, TypeError):
                        pass
        except (ValueError, TypeError):
            pass

    def _pillar_face_from_edge_overlap(self, pillar_pts: list, slab_pts: list, horizontal: bool):
        """
        Determina a face do pilar (A/B/C/D) que coincide com a aresta da laje,
        usando sobreposição de arestas — não comparação de centroide.

        Convenção de faces:
          HORIZONTAL (pw >= ph):  A=baixo(y0)  B=cima(y1)  C=esq(x0)  D=dir(x1)
          VERTICAL   (ph >  pw):  A=esq(x0)   B=dir(x1)   C=cima(y1) D=baixo(y0)

        Retorna (lado, face_label) ou ('NULO','NULO') se só toca em canto.
        """
        try:
            pxs = [float(p[0]) for p in pillar_pts]
            pys = [float(p[1]) for p in pillar_pts]
        except Exception:
            return 'NULO', 'NULO'

        px0, px1, py0, py1 = min(pxs), max(pxs), min(pys), max(pys)

        # Arestas do pilar: (eixo, coord_fixa, range_min, range_max, label)
        if horizontal:
            p_edges = {
                'A': ('H', py0, px0, px1, 'BAIXO'),
                'B': ('H', py1, px0, px1, 'CIMA'),
                'C': ('V', px0, py0, py1, 'ESQ'),
                'D': ('V', px1, py0, py1, 'DIR'),
            }
        else:
            p_edges = {
                'A': ('V', px0, py0, py1, 'ESQ'),
                'B': ('V', px1, py0, py1, 'DIR'),
                'C': ('H', py1, px0, px1, 'CIMA'),
                'D': ('H', py0, px0, px1, 'BAIXO'),
            }

        # Arestas da laje separadas por orientação
        s_h, s_v = [], []
        n = len(slab_pts)
        TOL_AX = 3.0
        for i in range(n):
            x1s, y1s = float(slab_pts[i][0]), float(slab_pts[i][1])
            x2s, y2s = float(slab_pts[(i + 1) % n][0]), float(slab_pts[(i + 1) % n][1])
            if abs(y1s - y2s) < TOL_AX:
                s_h.append(((y1s + y2s) / 2, min(x1s, x2s), max(x1s, x2s)))
            elif abs(x1s - x2s) < TOL_AX:
                s_v.append(((x1s + x2s) / 2, min(y1s, y2s), max(y1s, y2s)))

        TOL_PERP = 4.0
        MIN_OVERLAP = 1.0  # sobreposição mínima para não contar apenas canto

        best_side, best_label, best_ov = 'NULO', 'NULO', 0.0

        for side, (axis, fixed, r0, r1, label) in p_edges.items():
            edges_to_check = s_h if axis == 'H' else s_v
            for s_fixed, s_r0, s_r1 in edges_to_check:
                if abs(fixed - s_fixed) < TOL_PERP:
                    ov = min(r1, s_r1) - max(r0, s_r0)
                    if ov > MIN_OVERLAP and ov > best_ov:
                        best_ov = ov
                        best_side = side
                        best_label = label

        return best_side, best_label

    def _auto_fill_pillar_ficha(self, slab: Dict, link: dict) -> None:
        if not isinstance(link, dict):
            return
        ficha = link.setdefault('ficha', {})
        pts = link.get('points') or []
        pb = self._points_bbox_tuple(pts)
        if not pb:
            return
        pw, ph = pb[2] - pb[0], pb[3] - pb[1]
        orientation = 'RETANGULAR HORIZONTAL' if pw >= ph else 'RETANGULAR VERTICAL'
        horizontal = pw >= ph

        # Detectar face por sobreposição de arestas (não por centroide)
        slab_pts = slab.get('points') or []
        side, face = self._pillar_face_from_edge_overlap(pts, slab_pts, horizontal)

        ficha.setdefault('pillar_orientation', orientation)
        ficha.setdefault('pillar_side', side)
        ficha.setdefault('touch_face', face)

        # Classificar hatch usando convenção pré-processada do detalhe
        convention = (getattr(self, 'pavimento_preprocess', None) or {}).get('convention', {})
        hatch_class = self._classify_pillar_hatch(pts, convention)
        ficha.setdefault('hatch_description', hatch_class)

        name_txt = self._nearest_dxf_text(self._bbox_center_tuple(pb), r'^P\d+', max_dist=140.0)
        if name_txt:
            ficha.setdefault('pillar_name', str(name_txt.get('text') or ''))
            fl = link.setdefault('ficha_links', {})
            fl.setdefault('pillar_name', [])
            if not fl['pillar_name']:
                lk = dict(name_txt)
                lk['role'] = 'Ficha_pillar_name'
                fl['pillar_name'] = [lk]

    def _extract_beam_texts(self) -> list[dict]:
        """
        Extrai textos do DXF que parecem nomes de vigas (ex: V301, V12).
        Retorna lista de {text, pos, layer}.
        """
        import re as _re
        BEAM_RE = _re.compile(r'^[Vv]\s*\d{2,}')
        result: list[dict] = []
        for t in (self.dxf_data or {}).get('texts', []) or []:
            txt = str(t.get('text') or '').strip()
            if not txt or not BEAM_RE.match(txt):
                continue
            pos = t.get('pos') or [0, 0]
            result.append({'text': txt, 'pos': list(pos), 'layer': t.get('layer', '')})
        return result

    def _run_pre_validation_dialog(self) -> bool:
        """
        Abre o diálogo de pré-validação (Pilares + Visão de Cortes).
        Retorna True se o usuário confirmou, False se cancelou.
        Aplica o resultado diretamente nas estruturas de dados.
        """
        from src.ui.widgets.pre_validation_dialog import PreValidationDialog

        preproc = getattr(self, 'pavimento_preprocess', {}) or {}
        obra = preproc.get('obra') or ''
        pavimento = preproc.get('pavimento') or ''
        convention = preproc.get('convention') or {}

        beam_texts = self._extract_beam_texts() if getattr(self, 'dxf_data', None) else []

        # Arquivo de convenção salva (um por obra em DADOS-OBRAS/{obra}/)
        _dados_root = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'DADOS-OBRAS')
        )
        _convention_file: str | None = (
            os.path.join(_dados_root, obra, 'convencao_pilares.json') if obra else None
        )

        _db_path = getattr(self.db, 'db_path', None)

        dlg = PreValidationDialog(
            pillar_report=self.pavimento_pillar_report,
            nivel_report=self.pavimento_nivel_report,
            slabs=self.slabs_found,
            convention=convention,
            obra=obra,
            pavimento=pavimento,
            beam_texts=beam_texts,
            canvas=getattr(self, 'canvas', None),
            convention_file=_convention_file,
            db_path=_db_path,
            parent=self,
        )

        from PySide6.QtWidgets import QDialog
        dlg.showMaximized()
        if dlg.exec() != QDialog.Accepted:
            return False

        result = dlg.get_result()
        self._apply_pre_validation_result(result)
        return True

    def _apply_pre_validation_result(self, result: dict) -> None:
        """
        Aplica as decisões do diálogo de pré-validação nas estruturas internas:
        - Atualiza pavimento_pillar_report com overrides de classificação
        - Grava term_type_map em pavimento_preprocess
        - Armazena cut_view_assignments nos fichas dos cortes das lajes
        - Remove de cut_view_geom cortes classificados como inválidos (não é VC)
          para evitar retrabalho de remoção manual nos vínculos de laje
        """
        term_map = result.get('term_type_map') or {}
        pillar_overrides = result.get('pillar_overrides') or {}
        invalid_pillar_keys: set = set(result.get('invalid_pillar_keys') or set())
        cut_assignments = result.get('cut_view_assignments') or {}
        invalid_cut_uids: set = result.get('invalid_cut_uids') or set()

        # Salva mapeamento de termos no preprocess para uso posterior.
        # Se o diálogo pós-análise não tinha combos (aba Convenção removida),
        # mantém o term_type_map já definido antes da análise.
        preproc = getattr(self, 'pavimento_preprocess', {}) or {}
        if term_map:
            preproc['term_type_map'] = term_map
        elif not preproc.get('term_type_map'):
            preproc['term_type_map'] = {}
        self.pavimento_preprocess = preproc

        # Aplica overrides de pilares
        for key, override in pillar_overrides.items():
            if key in self.pavimento_pillar_report:
                entry = self.pavimento_pillar_report[key]
                entry['classification'] = override.get('classification', entry.get('classification'))
                entry['physical_type'] = override.get('physical_type', 'unknown')
                entry['ignore_in_beams'] = bool(override.get('ignore_in_beams', False))
                entry['is_invalid'] = bool(override.get('is_invalid', key in invalid_pillar_keys))
                entry['preficha_reviewed'] = True

        rejected_geom_sigs = set()
        for key in invalid_pillar_keys:
            pts = (self.pavimento_pillar_report.get(key) or {}).get('points') or []
            if pts:
                rejected_geom_sigs.add(self._pillar_points_sig(pts))

        # Se a geometria original foi rejeitada e uma alternativa foi aprovada,
        # promove a alternativa para a chave/nome canônico.
        for key in list(self.pavimento_pillar_report):
            if not str(key).endswith('__ALT') or key in invalid_pillar_keys:
                continue
            alt = self.pavimento_pillar_report[key]
            original_key = alt.get('alt_for_original_key')
            if original_key not in invalid_pillar_keys:
                continue
            promoted = dict(alt)
            promoted['name'] = (
                self.pavimento_pillar_report.get(original_key, {}).get('name')
                or original_key
            )
            promoted['is_invalid'] = False
            promoted['geometry_promoted_from'] = key
            promoted['preficha_reviewed'] = True
            self.pavimento_pillar_report[original_key] = promoted
            invalid_pillar_keys.discard(original_key)

        self.pavimento_invalid_pillar_keys = set(invalid_pillar_keys)

        # Propaga rejeições humanas aos vínculos das lajes. Sem isto, uma
        # geometria recusada continuava reaparecendo no próximo relatório.
        invalid_geom_sigs = set(rejected_geom_sigs)
        for key in invalid_pillar_keys:
            entry = self.pavimento_pillar_report.get(key) or {}
            pts = entry.get('points') or []
            if pts:
                invalid_geom_sigs.add(self._pillar_points_sig(pts))
        if invalid_geom_sigs:
            for slab in self.slabs_found or []:
                p_links = (
                    slab.get('links', {})
                    .get('laje_pilares_apoio', {})
                    .get('pillar_geom', [])
                )
                if isinstance(p_links, list):
                    p_links[:] = [
                        link for link in p_links
                        if self._pillar_points_sig(link.get('points') or [])
                        not in invalid_geom_sigs
                    ]

        if not cut_assignments and not invalid_cut_uids:
            return

        # Constrói mapa de posição → assignment para propagar a TODAS as lajes com
        # o mesmo corte (o mesmo T polygon pode estar em >1 laje).
        # Chave = (round(cx), round(cy))
        pos_to_assign: dict[tuple, dict] = {}
        invalid_positions: set[tuple] = set()
        for uid, assign in cut_assignments.items():
            # uid = "slab_cx_cy" — extrai cx,cy como fallback
            parts = uid.rsplit('_', 2)
            try:
                pos = (int(parts[-2]), int(parts[-1]))
            except (ValueError, IndexError):
                continue
            pos_to_assign[pos] = assign
            if assign.get('is_invalid'):
                invalid_positions.add(pos)

        n_removed = 0
        # Aplica associações de viga e remove cortes inválidos dos vínculos
        for slab in (self.slabs_found or []):
            slab_name = slab.get('name') or '?'
            links = slab.get('links') or {}
            cut_links = links.get('laje_visao_corte', {})
            if not isinstance(cut_links, dict):
                continue
            geom_list = cut_links.get('cut_view_geom', []) or []
            to_remove = []
            for i, cut in enumerate(geom_list):
                if not isinstance(cut, dict):
                    continue
                pts = cut.get('points') or []
                try:
                    xs = [float(p[0]) for p in pts]
                    ys = [float(p[1]) for p in pts]
                    cx = (min(xs) + max(xs)) / 2.0
                    cy = (min(ys) + max(ys)) / 2.0
                    uid = f"{slab_name}_{round(cx)}_{round(cy)}"
                    pos = (round(cx), round(cy))
                except Exception:
                    continue

                # Cortes classificados como "não é VC" → remover do vínculo de TODAS as lajes
                if uid in invalid_cut_uids or pos in invalid_positions:
                    to_remove.append(i)
                    continue

                # Atribui beam_name via uid exato; fallback por posição geométrica
                assign = cut_assignments.get(uid) or pos_to_assign.get(pos)
                if assign and not assign.get('is_invalid'):
                    ficha = cut.setdefault('ficha', {})
                    ficha['beam_name'] = assign.get('beam_name') or ''
                    ficha['beam_name_confidence'] = assign.get('confidence', 0.0)
                    # NÃO marca validated_link_classes aqui — apenas ação humana deve
                    # incrementar essa lista (fonte da % de completude da lista esquerda)

            # Remove em ordem reversa para não deslocar índices
            for i in reversed(to_remove):
                geom_list.pop(i)
                n_removed += 1

        n_pil = sum(1 for k, v in pillar_overrides.items()
                    if v.get('classification') and v['classification'] != 'INDETERMINADO')
        n_cuts_assigned = sum(1 for a in cut_assignments.values() if a.get('beam_name'))
        self.log(f"✅ Pré-validação aplicada: {n_pil} pilar(es) com classificação, "
                 f"{n_cuts_assigned} corte(s) com viga associada, "
                 f"{n_removed} corte(s) inválido(s) removido(s) dos vínculos.")

    def _apply_preficha_rejections(self, pillar_report: dict) -> None:
        """
        Lê o histórico de pré-ficha do pavimento atual e, para cada pilar cujo
        geo_key (bbox) foi rejeitado anteriormente (classificação em _NAO_SE_APLICA),
        tenta encontrar uma geometria alternativa no relatório que tenha o mesmo nome
        mas bbox diferente.

        Comportamento:
          - Se encontrar alternativa → substitui os dados de geometria no report
            e marca 'geometry_swapped': True para a pré-ficha exibir.
          - Se não encontrar alternativa → apenas marca 'geometry_previously_rejected'
            para a pré-ficha exibir o aviso ⚠.
          - Em ambos os casos, NÃO apaga o entry — a pré-ficha decide o que mostrar.
        """
        import json as _json, re as _re

        preproc = getattr(self, 'pavimento_preprocess', {}) or {}
        obra     = preproc.get('obra') or ''
        pavimento = preproc.get('pavimento') or ''
        if not obra or not pavimento:
            return

        _dados_root = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'DADOS-OBRAS')
        )
        pav_slug = _re.sub(r'[^\w\-]', '_', pavimento)[:60]
        history_path = os.path.join(_dados_root, obra, f'preficha_history_{pav_slug}.json')

        if not os.path.isfile(history_path):
            return

        try:
            with open(history_path, encoding='utf-8') as fh:
                hist = _json.load(fh)
        except Exception:
            return

        rejected_pilares = hist.get('pilares', {})
        if not rejected_pilares:
            return

        _NAO_SE_APLICA = {
            'NÃO PILAR — OBJETO SÓLIDO', 'NÃO PILAR — APENAS VISUAL',
            'GEOMETRIA ERRADA — ATUAL SÓLIDA', 'GEOMETRIA ERRADA — ATUAL APENAS VISUAL',
        }

        # Mapa: nome_pilar → lista de (geo_key, entry) para busca de alternativa
        name_to_entries: dict[str, list[tuple[str, dict]]] = {}
        for key, entry in pillar_report.items():
            pts = entry.get('points') or []
            if not pts:
                continue
            try:
                xs = [float(p[0]) for p in pts]; ys = [float(p[1]) for p in pts]
                gk = f'{round(min(xs),1)},{round(min(ys),1)},{round(max(xs),1)},{round(max(ys),1)}'
            except Exception:
                continue
            name = (entry.get('name') or key).strip().upper()
            name_to_entries.setdefault(name, []).append((gk, key, entry))

        for key, entry in list(pillar_report.items()):
            pts = entry.get('points') or []
            if not pts:
                continue
            try:
                xs = [float(p[0]) for p in pts]; ys = [float(p[1]) for p in pts]
                geo_key = f'{round(min(xs),1)},{round(min(ys),1)},{round(max(xs),1)},{round(max(ys),1)}'
            except Exception:
                continue

            hist_entry = rejected_pilares.get(geo_key)
            if not hist_entry:
                continue
            if hist_entry.get('classification', '').upper() not in {c.upper() for c in _NAO_SE_APLICA}:
                continue

            # Esta geometria foi rejeitada para este nome
            entry['geometry_previously_rejected'] = True
            entry['rejected_geo_key'] = geo_key

            # Tenta achar alternativa: mesmo nome, bbox diferente
            name = (entry.get('name') or key).strip().upper()
            candidates = [
                (gk, alt_key, alt_entry)
                for gk, alt_key, alt_entry in name_to_entries.get(name, [])
                if gk != geo_key and alt_key != key
                and gk not in rejected_pilares
            ]
            if candidates:
                # Usa o candidato de menor área (mais específico)
                def _area(c):
                    try:
                        pts2 = c[2].get('points') or []
                        xs2=[float(p[0]) for p in pts2]; ys2=[float(p[1]) for p in pts2]
                        return (max(xs2)-min(xs2))*(max(ys2)-min(ys2))
                    except Exception:
                        return 1e12
                import copy as _copy
                best_gk, best_key, best_entry = min(candidates, key=_area)
                # Injeta linha alternativa na pré-ficha (não substitui — mostra ambas)
                alt_key = f'{key}__ALT'
                if alt_key not in pillar_report:
                    alt_entry = _copy.deepcopy(best_entry)
                    alt_entry['name']                 = entry.get('name') or key
                    alt_entry['geometry_alt_candidate'] = True
                    alt_entry['alt_for_original_key']   = key
                    alt_entry['classification'] = alt_entry.get('classification') or 'INDETERMINADO'
                    pillar_report[alt_key] = alt_entry
                self.log(
                    f"↺ Pré-ficha: candidato alt. para {key} injetado como {alt_key} "
                    f"(bbox: {best_gk})"
                )

    def _plan_area_bbox(self, margin_frac: float = 0.05, margin_min: float = 50.0):
        """bbox da ÁREA DA PLANTA = união das lajes detectadas + margem.
        Usado para descartar textos P# de cortes/legendas/detalhes (fora da planta)."""
        area = None
        for s in getattr(self, 'slabs_found', []) or []:
            pts = s.get('points') or []
            try:
                xs = [float(p[0]) for p in pts]; ys = [float(p[1]) for p in pts]
            except Exception:
                continue
            if not xs:
                continue
            b = (min(xs), min(ys), max(xs), max(ys))
            area = b if area is None else (
                min(area[0], b[0]), min(area[1], b[1]),
                max(area[2], b[2]), max(area[3], b[3]))
        if area is None:
            return None
        mx, my = area[2] - area[0], area[3] - area[1]
        marg = max(mx, my) * margin_frac + margin_min
        return (area[0] - marg, area[1] - marg, area[2] + marg, area[3] + marg)

    @staticmethod
    def _pillar_points_sig(points: list) -> str:
        """Assinatura posicional de um contorno, independente da direção dos pontos."""
        coords = []
        for point in points or []:
            try:
                coords.append((round(float(point[0]), 3), round(float(point[1]), 3)))
            except Exception:
                continue
        if coords and coords[0] == coords[-1]:
            coords.pop()
        if not coords:
            return 'EMPTY'
        return '|'.join(f'{x:.3f},{y:.3f}' for x, y in sorted(set(coords)))

    def _collect_plan_pillar_names(self) -> dict:
        """
        Coleta nomes de pilares (textos 'P<num>') que estão na ÁREA DA PLANTA,
        agrupados por nome único. Descarta textos de cortes/legendas/detalhes.
        Retorna {nome_upper: [(x,y), ...]} (posições do texto na planta).
        """
        import re as _re
        # Usa snapshot da análise em curso (evita leitura de dxf_data substituído
        # por processEvents() durante o loop de lajes).
        _snap = getattr(self, '_analysis_texts', None)
        texts = _snap if _snap is not None else (getattr(self, 'dxf_data', None) or {}).get('texts', []) or []
        area = self._plan_area_bbox()
        pat = _re.compile(r'^P\d+[A-Z]?$')
        names: dict = {}
        for t in texts:
            s = str(t.get('text', '')).strip().upper()
            if not pat.match(s):
                continue
            pos = t.get('pos') or t.get('points') or [None, None]
            if pos and isinstance(pos[0], (list, tuple)):
                pos = pos[0]
            try:
                x, y = float(pos[0]), float(pos[1])
            except (TypeError, ValueError, IndexError):
                continue
            if area and not (area[0] <= x <= area[2] and area[1] <= y <= area[3]):
                continue  # texto fora da planta (corte/legenda/detalhe)
            names.setdefault(s, []).append((x, y))
        return names

    @staticmethod
    def _is_pillar_like_polygon(sh, points: list | None = None) -> bool:
        """Aceita pilares compactos e polígonos ortogonais especiais (L/T/U).

        Geometria especial só é aceita no fluxo dirigido por um texto P#, portanto
        não transforma toda visão de corte côncava do desenho em pilar.
        """
        try:
            minx, miny, maxx, maxy = sh.bounds
        except Exception:
            return False
        w, h = maxx - minx, maxy - miny
        if w <= 0 or h <= 0:
            return False
        a = sh.area
        if a < 80 or a > 60000:           # ~10x10cm a ~200x300cm
            return False
        rect = w * h
        if max(w, h) / max(1e-6, min(w, h)) > 12:  # não é uma linha fina
            return False
        fill = a / rect if rect > 0 else 0.0
        if fill >= 0.5:
            return True

        # Pilar L/T/U: contorno ortogonal, côncavo e com quantidade controlada
        # de vértices. P26/P27 do 13P, por exemplo, têm fill≈0.19.
        raw = list(points or [])
        if raw and raw[0] == raw[-1]:
            raw = raw[:-1]
        if not (6 <= len(raw) <= 16) or fill < 0.12:
            return False
        axis_aligned = 0
        usable_edges = 0
        for i, p1 in enumerate(raw):
            p2 = raw[(i + 1) % len(raw)]
            try:
                dx = abs(float(p2[0]) - float(p1[0]))
                dy = abs(float(p2[1]) - float(p1[1]))
            except Exception:
                continue
            if dx <= 1e-6 and dy <= 1e-6:
                continue
            usable_edges += 1
            if dx <= 1.0 or dy <= 1.0:
                axis_aligned += 1
        return usable_edges >= 6 and axis_aligned / usable_edges >= 0.8

    def _find_pillar_geom_near_text(self, positions: list, claimed_ids: set,
                                    max_dist: float = 200.0):
        """
        Busca a polyline com cara de pilar mais próxima de alguma das posições do
        texto P# (estrutural limpo), para vincular geometria a um nome que NÃO
        tinha geometria na pré-análise. Prefere a que CONTÉM o texto.
        Retorna (points, poly_id) ou (None, None).
        """
        from shapely.geometry import Polygon, Point
        polys = (getattr(self, 'dxf_data', None) or {}).get('polylines', []) or []
        best = None; best_score = None
        for p in polys:
            pid = id(p)
            if pid in claimed_ids:
                continue
            raw = p.get('points') or []
            uniq = []
            for q in raw:
                if not uniq or q != uniq[-1]:
                    uniq.append(q)
            if len(uniq) < 3:
                continue
            try:
                sh = Polygon(uniq)
                if sh.geom_type != 'Polygon' or not sh.is_valid:
                    continue
            except Exception:
                continue
            if not self._is_pillar_like_polygon(sh, uniq):
                continue
            for (ax, ay) in positions:
                pt = Point(ax, ay)
                d = sh.distance(pt)
                if d > max_dist:
                    continue
                score = 0.0 if sh.contains(pt) else d
                if best_score is None or score < best_score:
                    best_score = score
                    best = (uniq, pid)
        if best:
            return best[0], best[1]
        return None, None

    def _pillar_laje_entries(self, points: list, slabs: list[Dict]) -> list[dict]:
        """Deriva lajes adjacentes para pilares encontrados pelo inventário P#."""
        if not points:
            return []
        from shapely.geometry import Polygon
        try:
            pillar_poly = Polygon(points)
            if not pillar_poly.is_valid:
                pillar_poly = pillar_poly.buffer(0)
        except Exception:
            return []
        entries: list[dict] = []
        horizontal = (pillar_poly.bounds[2] - pillar_poly.bounds[0]) >= (
            pillar_poly.bounds[3] - pillar_poly.bounds[1]
        )
        for slab in slabs or []:
            slab_pts = slab.get('points') or []
            if len(slab_pts) < 3:
                continue
            try:
                slab_poly = Polygon(slab_pts)
                distance = pillar_poly.distance(slab_poly)
            except Exception:
                continue
            if distance > 5.0 and not pillar_poly.intersects(slab_poly):
                continue
            side, face = self._pillar_face_from_edge_overlap(points, slab_pts, horizontal)
            entries.append({
                'laje': slab.get('name') or '?',
                'side': side,
                'face': face,
                'source': 'canonical_geometry_adjacency',
            })
        return entries

    def _build_complete_pillar_report(self, slabs: list[Dict]) -> dict:
        """Monta o inventário canônico P# usado pela pré-ficha.

        Existência vem dos textos P# da planta. Geometria/classificação/lajes
        vêm dos vínculos já interpretados e, como fallback, da busca geométrica
        dirigida pelo nome. Assim nenhum pilar some antes da pré-validação.
        """
        linked_report = self._build_pillar_report(slabs)
        plan_names = self._collect_plan_pillar_names()

        # Fallback: se coleta de textos falhou (dxf_data inválido ou textos não
        # correspondem ao padrão), usa nomes do linked_report (vínculos das lajes)
        # para não perder pilares — reproduz comportamento pré-refatoração.
        if not plan_names and linked_report:
            print(f"[WARN_PIL] plan_names vazio — fallback para {len(linked_report)} nomes do linked_report", flush=True)
            for _nm, _entry in linked_report.items():
                if not str(_nm).endswith('__ALT'):
                    plan_names[_nm] = list(_entry.get('name_positions') or [])

        result: dict = {}
        claimed_geom_ids: set = set()

        for name, positions in plan_names.items():
            linked = linked_report.get(name)
            points = list((linked or {}).get('points') or [])
            source = 'slab_support_links' if points else 'unresolved'
            if not points:
                points, geom_id = self._find_pillar_geom_near_text(
                    positions, claimed_geom_ids
                )
                if points:
                    claimed_geom_ids.add(geom_id)
                    points = list(points)
                    source = 'name_proximity'

            entry = dict(linked or {})
            entry.update({
                'name': name,
                'points': points or [],
                'name_positions': list(positions),
                'geometry_source': source,
                'needs_geometry': not bool(points),
                'classification': entry.get('classification') or 'INDETERMINADO',
                'ignore_in_beams': bool(entry.get('ignore_in_beams', False)),
            })
            if points:
                try:
                    xs = [float(p[0]) for p in points]
                    ys = [float(p[1]) for p in points]
                    entry['bbox'] = (min(xs), min(ys), max(xs), max(ys))
                    from src.core.perspective_mapper import PillarPerspectiveMapper
                    shape, orientation = PillarPerspectiveMapper.identify_shape(
                        [tuple(p) for p in points]
                    )
                    entry['shape_type'] = shape
                    entry['orientation'] = entry.get('orientation') or orientation
                except Exception:
                    entry['bbox'] = entry.get('bbox')
                derived_lajes = self._pillar_laje_entries(points, slabs)
                existing = {x.get('laje'): x for x in entry.get('lajes', [])}
                for item in derived_lajes:
                    existing.setdefault(item.get('laje'), item)
                entry['lajes'] = list(existing.values())
            else:
                entry['bbox'] = None
                entry['lajes'] = list(entry.get('lajes') or [])
            result[name] = entry

        self._reconcile_canonical_pillar_links(result, slabs)
        return result

    def _reconcile_canonical_pillar_links(self, report: dict,
                                          slabs: list[Dict]) -> None:
        """Remove pilares canônicos dos cortes e os registra como apoios das lajes."""
        by_sig = {}
        for name, entry in report.items():
            pts = entry.get('points') or []
            if pts:
                by_sig[self._pillar_points_sig(pts)] = (name, entry)
        if not by_sig:
            return

        for slab in slabs or []:
            links = slab.setdefault('links', {})
            cut_geom = (
                links.setdefault('laje_visao_corte', {})
                .setdefault('cut_view_geom', [])
            )
            if isinstance(cut_geom, list):
                cut_geom[:] = [
                    link for link in cut_geom
                    if self._pillar_points_sig(link.get('points') or []) not in by_sig
                ]

            support = (
                links.setdefault('laje_pilares_apoio', {})
                .setdefault('pillar_geom', [])
            )
            if not isinstance(support, list):
                continue
            existing = {
                self._pillar_points_sig(link.get('points') or [])
                for link in support if isinstance(link, dict)
            }
            slab_name = slab.get('name') or '?'
            for sig, (name, entry) in by_sig.items():
                if sig in existing:
                    continue
                adjacency = next(
                    (x for x in entry.get('lajes', [])
                     if x.get('laje') == slab_name),
                    None,
                )
                if not adjacency:
                    continue
                support.append({
                    'type': 'poly',
                    'points': entry.get('points') or [],
                    'text': 'Pilar canônico detectado por nome',
                    'role': 'Pillar_support_geom_canonical',
                    'source': entry.get('geometry_source'),
                    'is_inferred': True,
                    'ficha': {
                        'pillar_name': name,
                        'pillar_side': adjacency.get('side', 'NULO'),
                        'touch_face': adjacency.get('face', 'NULO'),
                        'pillar_orientation': entry.get('orientation', ''),
                        'hatch_description': entry.get(
                            'classification', 'INDETERMINADO'
                        ),
                    },
                })
                existing.add(sig)

    def _build_pillar_report(self, slabs: list[Dict]) -> dict:
        """
        Consolida, a partir dos vínculos das lajes, um relatório de todos os pilares
        detectados no pavimento.

        Estrutura retornada:
          { pillar_key: {
              'name': str,
              'bbox': (x0,y0,x1,y1),
              'points': list,
              'orientation': str,
              'classification': 'NASCE'|'SEGUE'|'MORRE'|'INDETERMINADO',
              'ignore_in_beams': bool,   # True se NASCE
              'lajes': [{'laje': str, 'side': str, 'face': str}],
          }}

        pillar_key = nome do pilar se disponível, senão hash da bbox arredondada.
        Pilares encontrados em múltiplas lajes são mesclados em uma única entrada.
        """
        report: dict = {}

        for slab in slabs:
            slab_name = slab.get('name') or '?'
            links = slab.get('links') or {}
            pillar_field = links.get('laje_pilares_apoio', {})
            if not isinstance(pillar_field, dict):
                continue
            for link in pillar_field.get('pillar_geom', []) or []:
                if not isinstance(link, dict):
                    continue
                pts = link.get('points') or []
                ficha = link.get('ficha') or {}
                name = ficha.get('pillar_name') or ''
                side = ficha.get('pillar_side') or 'NULO'
                face = ficha.get('touch_face') or 'NULO'
                orientation = ficha.get('pillar_orientation') or ''
                classification = ficha.get('hatch_description') or 'INDETERMINADO'

                # Chave de identidade: nome ou posição arredondada
                if name:
                    key = name.strip().upper()
                elif pts:
                    try:
                        xs = [float(p[0]) for p in pts]; ys = [float(p[1]) for p in pts]
                        key = f"bbox_{round(min(xs))}_{round(min(ys))}_{round(max(xs))}_{round(max(ys))}"
                    except Exception:
                        key = str(id(link))
                else:
                    continue

                laje_entry = {'laje': slab_name, 'side': side, 'face': face}

                if key in report:
                    # Mescla: adiciona laje se ainda não listada
                    existing_lajes = [e['laje'] for e in report[key]['lajes']]
                    if slab_name not in existing_lajes:
                        report[key]['lajes'].append(laje_entry)
                    # Atualiza classification se era INDETERMINADO
                    if report[key]['classification'] == 'INDETERMINADO' and classification != 'INDETERMINADO':
                        report[key]['classification'] = classification
                        report[key]['ignore_in_beams'] = (classification == 'NASCE')
                else:
                    bbox = None
                    if pts:
                        try:
                            xs = [float(p[0]) for p in pts]; ys = [float(p[1]) for p in pts]
                            bbox = (min(xs), min(ys), max(xs), max(ys))
                        except Exception:
                            pass
                    report[key] = {
                        'name': name or key,
                        'bbox': bbox,
                        'points': pts,
                        'orientation': orientation,
                        'classification': classification,
                        'ignore_in_beams': (classification == 'NASCE'),
                        'lajes': [laje_entry],
                    }

        return report

    def get_pillar_report(self) -> dict:
        """Acesso ao relatório de pilares do pavimento atual. Retorna {} se não gerado."""
        return getattr(self, 'pavimento_pillar_report', {})

    # ──────────────────────────────────────────────────────────────────────────
    # Part B — Inferência de nível via delta do corte de viga
    # ──────────────────────────────────────────────────────────────────────────

    def _cut_view_level_delta(self, cut_link: dict, own_position: str, neighbor_position: str,
                              slab: dict, neighbor: dict) -> float | None:
        """
        Calcula a diferença de nível (delta em cm) entre esta laje e a vizinha
        usando as abas geométricas do corte de viga.

        Positivo = esta laje está ACIMA da vizinha.
        Retorna None se não for possível calcular.

        Lógica:
          - own_dist_top = distância do topo da viga até o topo da aba desta laje
          - neighbor_dist_top = mesmo para a vizinha
          - Se as posições diferem, a diferença das dist_top dá o delta vertical.
        """
        if not isinstance(cut_link, dict):
            return None
        ficha = cut_link.get('ficha') or {}
        try:
            own_dt = float(ficha.get('own_dist_top') or 0)
            neigh_dt = float(ficha.get('neighbor_dist_top') or 0)
        except Exception:
            return None
        if own_dt == 0.0 and neigh_dt == 0.0:
            return None
        # delta positivo = esta laje está mais acima que a vizinha
        return round(neigh_dt - own_dt, 2)

    def _infer_slab_level_from_cut_deltas(self, slabs: list[Dict],
                                          level_sources: dict,
                                          poly_map: dict) -> int:
        """
        Para cada laje sem nível confirmado que tenha corte de viga:
        - encontra a laje vizinha no corte (ficha.side_a_laje_name)
        - se a vizinha tem nível confirmado, aplica delta
        - se não, marca para revisão com o delta disponível

        Retorna o número de lajes com nível aplicado por este método.
        """
        applied = 0
        for slab in slabs:
            if self._slab_has_human_level(slab):
                continue
            if level_sources.get(slab.get('id') or slab.get('name')):
                continue  # já tem nível por outro caminho

            cuts = self._slab_cut_links(slab)
            if not cuts:
                continue

            candidate_values: list[dict] = []
            for cut in cuts:
                if not isinstance(cut, dict):
                    continue
                ficha = cut.get('ficha') or {}
                neighbor_name = (ficha.get('side_a_laje_name') or '').strip()
                if not neighbor_name or neighbor_name.lower() == 'nulo':
                    continue

                # Localiza a laje vizinha pelo nome
                neighbor = next((s for s in slabs if (s.get('name') or '') == neighbor_name), None)
                if not neighbor:
                    continue

                n_src = level_sources.get(neighbor.get('id') or neighbor.get('name'))
                if not n_src:
                    continue

                own_pos = ficha.get('own_position') or 'centro'
                neigh_pos = ficha.get('neighbor_position') or 'centro'
                delta = self._cut_view_level_delta(cut, own_pos, neigh_pos, slab, neighbor)
                if delta is None:
                    continue

                calc_level = n_src['value'] + delta
                confidence = 0.80 if n_src.get('human') else 0.55
                candidate_values.append({
                    'value': round(calc_level, 2),
                    'confidence': confidence,
                    'delta': delta,
                    'source_slab': neighbor_name,
                    'source_level': n_src['value'],
                    'human_source': bool(n_src.get('human')),
                    'method': 'cut_view_delta',
                })

            if not candidate_values:
                continue

            # Escolhe o de maior confiança; em empate, usa a média
            candidate_values.sort(key=lambda x: x['confidence'], reverse=True)
            best = candidate_values[0]
            self._apply_inferred_slab_level(
                slab, best['value'],
                f"cut_view_delta from {best['source_slab']} (Δ={best['delta']:+.1f}cm)",
                candidate_values
            )
            # Enriquece o level_inference com metadados de confiança
            slab['level_inference']['confidence'] = best['confidence']
            slab['level_inference']['method'] = 'cut_view_delta'
            level_sources[slab.get('id') or slab.get('name')] = {
                'value': best['value'],
                'slab': slab.get('name'),
                'human': False,
                'kind': 'cut_view_delta',
                'confidence': best['confidence'],
            }
            applied += 1

        return applied

    # ──────────────────────────────────────────────────────────────────────────
    # Part A — Relatório consolidado de níveis do pavimento
    # ──────────────────────────────────────────────────────────────────────────

    def _build_nivel_report(self, slabs: list[Dict],
                            pillar_report: dict | None = None) -> dict:
        """
        Constrói e retorna o relatório consolidado de níveis para todas as lajes
        e todos os pilares do pavimento.

        Estrutura:
          {
            'lajes': {
              name: {
                'name': str,
                'level': float | None,
                'level_str': str,
                'confidence': float,           # 1.0=humano, 0.8=cut_delta_human_src, 0.55=inferido, 0.0=desconhecido
                'source_type': str,            # 'human_direct'|'text_label'|'cut_view_delta'|'neighbor_inferred'|'unknown'
                'inference': dict,             # cópia de slab['level_inference'] se existir
                'neighbors': dict,             # {north/south/east/west: name_or_level}
                'warnings': list[str],
                'has_cut_view': bool,
              }
            },
            'pilares': {
              key: {
                'name': str,
                'level': float | None,
                'level_str': str,
                'laje_source': str,
                'ignore_in_beams': bool,
                'classification': str,
                'warnings': list[str],
              }
            },
            'summary': {
              'total_lajes': int,
              'confirmed': int,
              'inferred': int,
              'unknown': int,
              'hallucination_suspects': int,
              'median_level': float | None,
            }
          }
        """
        import statistics

        lajes_report: dict = {}
        pilares_report: dict = {}

        # ── 1. Lajes ──────────────────────────────────────────────────────────
        all_levels: list[float] = []
        for slab in slabs:
            name = slab.get('name') or str(slab.get('id') or id(slab))

            src = self._slab_level_source(slab, include_neighbor_context=True)
            inference = slab.get('level_inference') or {}
            has_cut = self._slab_has_cut_view(slab)

            # Determina level/confidence/source_type
            if src:
                level_val = src['value']
                is_human = bool(src.get('human'))
                kind = src.get('kind', '')
                if is_human:
                    source_type = 'human_direct'
                    confidence = 1.0
                elif kind == 'cut_view_delta':
                    source_type = 'cut_view_delta'
                    confidence = float(inference.get('confidence', 0.80))
                elif kind in ('field', 'flat', 'label'):
                    source_type = 'text_label'
                    confidence = 0.90
                elif inference.get('status') == 'inferred':
                    source_type = 'neighbor_inferred'
                    confidence = float(inference.get('confidence', 0.55))
                else:
                    source_type = 'auto_linked'
                    confidence = 0.65
            else:
                level_val = None
                source_type = 'unknown'
                confidence = 0.0

            if level_val is not None:
                all_levels.append(level_val)

            # Direções dos vizinhos (nomes)
            neighbor_links = self._ensure_slab_neighbor_level_links(slab)
            neighbors: dict = {}
            for slot in ('neighbor_north', 'neighbor_south', 'neighbor_east', 'neighbor_west'):
                links_in_slot = neighbor_links.get(slot) or []
                names = [l.get('source_slab') for l in links_in_slot if isinstance(l, dict) and l.get('source_slab')]
                if names:
                    neighbors[slot.replace('neighbor_', '')] = names[0]

            lajes_report[name] = {
                'name': name,
                'level': level_val,
                'level_str': self._format_slab_level_value(level_val) if level_val is not None else '',
                'confidence': confidence,
                'source_type': source_type,
                'inference': inference,
                'neighbors': neighbors,
                'warnings': [],
                'has_cut_view': has_cut,
            }

        # ── 2. Quality gate — detecta níveis alucinados ───────────────────────
        known_levels = [e['level'] for e in lajes_report.values() if e['level'] is not None]
        median_level = statistics.median(known_levels) if known_levels else None
        OUTLIER_THRESHOLD_CM = 200.0

        for entry in lajes_report.values():
            if entry['level'] is None:
                continue
            if median_level is not None:
                delta = abs(entry['level'] - median_level)
                if delta > OUTLIER_THRESHOLD_CM:
                    entry['warnings'].append(
                        f"Nivel {entry['level_str']} diverge {delta:.0f}cm da mediana ({median_level:.2f}cm) — possivel alucinacao"
                    )
            if entry['confidence'] < 0.6 and entry['source_type'] not in ('unknown',):
                entry['warnings'].append("Confianca baixa na inferencia de nivel")

        # ── 3. Pilares ────────────────────────────────────────────────────────
        pr = pillar_report or {}
        for key, pillar in pr.items():
            # Nível do pilar = máximo nível das lajes que ele toca
            touching_levels: list[float] = []
            laje_src = ''
            for laje_entry in pillar.get('lajes', []):
                lj_name = laje_entry.get('laje') or ''
                rep = lajes_report.get(lj_name)
                if rep and rep['level'] is not None:
                    touching_levels.append(rep['level'])
                    if not laje_src or rep['confidence'] > lajes_report.get(laje_src, {}).get('confidence', 0):
                        laje_src = lj_name

            if touching_levels:
                p_level = max(touching_levels)
            else:
                p_level = None

            p_warnings = []
            if p_level is None:
                p_warnings.append("Sem laje com nivel confirmado nas adjacentes")

            pilares_report[key] = {
                'name': pillar.get('name') or key,
                'level': p_level,
                'level_str': self._format_slab_level_value(p_level) if p_level is not None else '',
                'laje_source': laje_src,
                'ignore_in_beams': bool(pillar.get('ignore_in_beams')),
                'classification': pillar.get('classification') or 'INDETERMINADO',
                'warnings': p_warnings,
            }

        # ── 4. Sumário ────────────────────────────────────────────────────────
        confirmed = sum(1 for e in lajes_report.values() if e['confidence'] >= 0.9)
        inferred = sum(1 for e in lajes_report.values() if 0.0 < e['confidence'] < 0.9)
        unknown = sum(1 for e in lajes_report.values() if e['confidence'] == 0.0)
        hallucination_suspects = sum(1 for e in lajes_report.values() if e['warnings'])

        return {
            'lajes': lajes_report,
            'pilares': pilares_report,
            'summary': {
                'total_lajes': len(lajes_report),
                'confirmed': confirmed,
                'inferred': inferred,
                'unknown': unknown,
                'hallucination_suspects': hallucination_suspects,
                'median_level': median_level,
            },
        }

    def get_nivel_report(self) -> dict:
        """Acesso ao relatório de níveis do pavimento atual. Retorna {} se não gerado."""
        return getattr(self, 'pavimento_nivel_report', {})

    def is_pillar_nasce(self, pillar_name: str) -> bool:
        """True se o pilar é NASCE neste pavimento (deve ser desconsiderado nas vigas)."""
        report = self.get_pillar_report()
        key = (pillar_name or '').strip().upper()
        entry = report.get(key)
        if entry:
            return bool(entry.get('ignore_in_beams'))
        return False

    def _auto_link_slab_cut_views(self, slabs: list[Dict]) -> tuple[int, int]:
        if not getattr(self, 'dxf_data', None):
            return 0, 0
        from shapely.geometry import LineString, Polygon
        poly_map = self._slab_polygon_map(slabs)
        added_cuts = 0
        added_pillars = 0
        candidates = []
        for item in self.dxf_data.get('polylines', []) or []:
            pts = item.get('points') or []
            if len(pts) < 5 or len(pts) > 24:
                continue
            try:
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                w, h = max(xs) - min(xs), max(ys) - min(ys)
                if w < 5 or h < 5 or w > 180 or h > 180:
                    continue
                if w / max(h, 1.0) > 5.0 or h / max(w, 1.0) > 5.0:
                    continue
                # Visões de corte (T-section) são sempre polígonos fechados.
                # Polylines abertas (zig-zag, marcadores de apoio) são descartadas.
                if pts[0] != pts[-1]:
                    continue
                geom = Polygon(pts)
                if geom.is_empty:
                    continue
                bbox = (min(xs), min(ys), max(xs), max(ys))
                marker_kind = self._classify_slab_boundary_marker(pts, geom, bbox)
                candidates.append((item, geom, bbox, marker_kind))
            except Exception:
                continue

        for slab in slabs:
            cut_links = self._ensure_slab_cut_view_links(slab)
            pillar_links = self._ensure_slab_support_pillar_links(slab)
            existing = cut_links.get('cut_view_geom', []) or []
            existing_pillars = pillar_links.get('pillar_geom', []) or []

            # Dedup existentes por centroide: prioriza versão extended_by_companion.
            # Rejeita polígonos não-validados com < 8 pontos (retângulos/companion soltos).
            _seen_cv: dict[tuple, int] = {}  # pos → index in _keep_cv
            _keep_cv: list = []
            for _e in existing:
                if not isinstance(_e, dict):
                    continue
                _epts = _e.get('points') or []
                _orig_epts = _e.get('original_pts') or _epts
                # Rejeita entradas com pontos insuficientes para T (apenas se não validado)
                if not _e.get('validated') and len(_epts) < 8 and len(_orig_epts) < 8:
                    continue
                try:
                    _exs = [float(p[0]) for p in _epts]
                    _eys = [float(p[1]) for p in _epts]
                    _epos = (round((min(_exs) + max(_exs)) / 2.0), round((min(_eys) + max(_eys)) / 2.0))
                except Exception:
                    _keep_cv.append(_e)
                    continue
                if _epos in _seen_cv:
                    prev_idx = _seen_cv[_epos]
                    prev = _keep_cv[prev_idx]
                    # Troca se novo é extended e anterior não, ou novo tem mais pontos
                    if (_e.get('extended_by_companion') and not prev.get('extended_by_companion')) or \
                       (len(_epts) > len(prev.get('points') or [])):
                        _keep_cv[prev_idx] = _e
                else:
                    _seen_cv[_epos] = len(_keep_cv)
                    _keep_cv.append(_e)
            if len(_keep_cv) != len(existing):
                cut_links['cut_view_geom'] = _keep_cv
                existing = _keep_cv

            for link in existing:
                # Tenta completar o T com o retângulo companheiro (fundo do web).
                if not link.get('extended_by_companion') and len(link.get('points') or []) >= 7:
                    _ext = self._find_cut_view_web_extension(link.get('points') or [])
                    if _ext:
                        link['original_pts'] = list(link.get('points') or [])
                        link['points'] = _ext
                        link['extended_by_companion'] = True
                self._auto_fill_cut_view_ficha(slab, link, slabs, poly_map)
            for link in existing_pillars:
                self._auto_fill_pillar_ficha(slab, link)
            has_validated_cut = any(isinstance(link, dict) and link.get('validated') for link in existing)
            poly = poly_map.get(slab.get('id') or slab.get('name'))
            if not poly:
                continue
            minx, miny, maxx, maxy = poly.bounds
            min_dim = max(1.0, min(maxx - minx, maxy - miny))
            max_dist = max(35.0, min(120.0, min_dim * 0.18))
            ranked = []
            for item, geom, _bbox, marker_kind in candidates:
                try:
                    dist = geom.distance(poly.boundary)
                    if dist <= max_dist and geom.distance(poly) <= max_dist:
                        ranked.append((dist, item, marker_kind))
                except Exception:
                    continue
            cut_count = 0
            pillar_count = 0
            for dist, item, marker_kind in sorted(ranked, key=lambda x: x[0])[:10]:
                pts = item.get('points') or []
                duplicate = False
                probe = {'points': pts}
                target_existing = existing_pillars if marker_kind == 'pillar' else existing
                for link in target_existing:
                    if not isinstance(link, dict):
                        continue
                    # Verifica contra pontos atuais E pontos originais (pré-extensão companion)
                    orig_link = {'points': link.get('original_pts') or link.get('points')}
                    if (self._same_cut_view_signature(probe, link) or
                            self._same_cut_view_signature(probe, orig_link)):
                        duplicate = True
                        break
                if duplicate:
                    continue

                # Visão de corte (T) precisa de ao menos 8 pontos de contorno
                if marker_kind != 'pillar' and len(pts) < 8:
                    continue

                if marker_kind == 'pillar':
                    if pillar_count >= 8:
                        continue
                    new_link = {
                        'type': 'poly',
                        'points': pts,
                        'text': 'Pilar de apoio detectado',
                        'role': 'Pillar_support_geom_auto',
                        'is_inferred': True,
                        'source': 'compact_geometry_near_slab_boundary',
                        'distance_to_slab': round(float(dist), 3),
                        'layer': item.get('layer'),
                    }
                    self._auto_fill_pillar_ficha(slab, new_link)
                    pillar_links['pillar_geom'].append(new_link)
                    pillar_count += 1
                    added_pillars += 1
                    continue

                if has_validated_cut:
                    continue
                if cut_count >= 4:
                    continue
                new_link = {
                    'type': 'poly',
                    'points': pts,
                    'text': 'Visao de corte detectada',
                    'role': 'Cut_view_geom_auto',
                    'is_inferred': True,
                    'source': 'geometry_near_slab_boundary',
                    'distance_to_slab': round(float(dist), 3),
                    'layer': item.get('layer'),
                }
                # Completa o T com o retângulo companheiro do fundo do web, se existir.
                if len(pts) >= 7:
                    _ext = self._find_cut_view_web_extension(pts)
                    if _ext:
                        new_link['original_pts'] = list(pts)
                        new_link['points'] = _ext
                        new_link['extended_by_companion'] = True
                self._auto_fill_cut_view_ficha(slab, new_link, slabs, poly_map)
                cut_links['cut_view_geom'].append(new_link)
                cut_count += 1
                added_cuts += 1
        return added_cuts, added_pillars

    def _neighbor_slabs(self, target: Dict, slabs: list[Dict], poly_map: dict, max_dist: float = 45.0) -> list[tuple[float, Dict]]:
        target_poly = poly_map.get(target.get('id') or target.get('name'))
        if not target_poly:
            return []
        result = []
        for other in slabs:
            if other is target:
                continue
            other_poly = poly_map.get(other.get('id') or other.get('name'))
            if not other_poly:
                continue
            try:
                dist = target_poly.distance(other_poly)
            except Exception:
                continue
            if dist <= max_dist:
                result.append((float(dist), other))
        result.sort(key=lambda x: x[0])
        return result

    def _orthogonal_neighbor_slabs(self, target: Dict, slabs: list[Dict], poly_map: dict, max_dist: float = 45.0) -> list[tuple[float, str, Dict]]:
        target_poly = poly_map.get(target.get('id') or target.get('name'))
        if not target_poly:
            return []
        try:
            ta = target_poly.bounds
            tcx = (ta[0] + ta[2]) / 2.0
            tcy = (ta[1] + ta[3]) / 2.0
            tw = max(1.0, ta[2] - ta[0])
            th = max(1.0, ta[3] - ta[1])
        except Exception:
            return []

        result = []
        for other in slabs:
            if other is target:
                continue
            other_poly = poly_map.get(other.get('id') or other.get('name'))
            if not other_poly:
                continue
            try:
                dist = float(target_poly.distance(other_poly))
                if dist > max_dist:
                    continue
                ob = other_poly.bounds
                ocx = (ob[0] + ob[2]) / 2.0
                ocy = (ob[1] + ob[3]) / 2.0
                ow = max(1.0, ob[2] - ob[0])
                oh = max(1.0, ob[3] - ob[1])
                x_overlap = max(0.0, min(ta[2], ob[2]) - max(ta[0], ob[0]))
                y_overlap = max(0.0, min(ta[3], ob[3]) - max(ta[1], ob[1]))
                vertical = x_overlap >= min(tw, ow) * 0.12 and abs(ocy - tcy) >= abs(ocx - tcx)
                horizontal = y_overlap >= min(th, oh) * 0.12 and abs(ocx - tcx) >= abs(ocy - tcy)
                if not (vertical or horizontal):
                    continue
                if vertical:
                    direction = 'top' if ocy > tcy else 'bottom'
                else:
                    direction = 'right' if ocx > tcx else 'left'
                result.append((dist, direction, other))
            except Exception:
                continue
        result.sort(key=lambda x: (x[1], x[0]))
        return result

    def _auto_link_slab_neighbor_level_texts(self, slabs: list[Dict], poly_map: dict) -> int:
        added = 0
        for slab in slabs:
            neighbor_links = self._ensure_slab_neighbor_level_links(slab)
            for dist, direction, other in self._orthogonal_neighbor_slabs(slab, slabs, poly_map):
                slot = self._neighbor_direction_slot(direction)
                neighbor_texts = neighbor_links.setdefault(slot, [])
                for level_link in self._own_slab_level_links(other):
                    new_link = dict(level_link)
                    new_link['type'] = new_link.get('type') or 'text'
                    new_link['role'] = slot
                    new_link['source'] = 'orthogonal_neighbor_level'
                    new_link['source_slab'] = other.get('name')
                    new_link['source_direction'] = direction
                    new_link['distance_to_slab'] = round(float(dist), 3)
                    new_link['is_inferred'] = True
                    new_link.pop('validated', None)
                    if self._append_unique_neighbor_level_link(neighbor_texts, new_link):
                        added += 1
                for text_link in self._slab_name_dim_links(other):
                    new_link = dict(text_link)
                    new_link['role'] = slot
                    new_link['source'] = 'orthogonal_neighbor_identity'
                    new_link['source_slab'] = other.get('name')
                    new_link['source_direction'] = direction
                    new_link['distance_to_slab'] = round(float(dist), 3)
                    new_link['is_inferred'] = True
                    new_link.pop('validated', None)
                    if self._append_unique_neighbor_level_link(neighbor_texts, new_link):
                        added += 1
        return added

    def _choose_consensus_level(self, sources: list[dict], tol: float = 0.05) -> dict | None:
        if not sources:
            return None
        groups = []
        for src in sources:
            placed = False
            for group in groups:
                if abs(group['value'] - src['value']) <= tol:
                    group['items'].append(src)
                    group['value'] = sum(i['value'] for i in group['items']) / len(group['items'])
                    placed = True
                    break
            if not placed:
                groups.append({'value': src['value'], 'items': [src]})
        groups.sort(key=lambda g: (sum(2 if i.get('human') else 1 for i in g['items']), len(g['items'])), reverse=True)
        best = groups[0]
        if len(groups) > 1 and abs(best['value'] - groups[1]['value']) > tol:
            best['ambiguous'] = True
        return best

    def _apply_inferred_slab_level(self, slab: Dict, value: float, reason: str, sources: list[dict]):
        text = self._format_slab_level_value(value)
        fields = slab.setdefault('fields', {})
        fields['laje_nivel'] = text
        slab['laje_nivel'] = text
        level_links = self._ensure_slab_level_links(slab)
        if not level_links.get('label'):
            src_name = sources[0].get('slab') if sources else None
            level_links['label'].append({
                'type': 'text',
                'text': text,
                'role': 'Nivel inferido',
                'is_inferred': True,
                'source': reason,
                'source_slab': src_name,
            })
        slab['level_inference'] = {
            'status': 'inferred',
            'reason': reason,
            'value': text,
            'sources': sources[:5],
        }

    def _infer_slab_levels_from_context(self, slabs: list[Dict]) -> None:
        if not slabs:
            return
        auto_cuts, auto_pillars = self._auto_link_slab_cut_views(slabs)
        poly_map = self._slab_polygon_map(slabs)
        auto_neighbor_levels = self._auto_link_slab_neighbor_level_texts(slabs, poly_map)

        level_sources = {}
        for slab in slabs:
            source = self._slab_level_source(slab, include_neighbor_context=False)
            if source:
                source = dict(source)
                source['slab'] = slab.get('name')
                source['has_cut'] = self._slab_has_cut_view(slab)
                level_sources[slab.get('id') or slab.get('name')] = source

        inferred_count = 0
        for slab in slabs:
            key = slab.get('id') or slab.get('name')
            if self._slab_has_human_level(slab):
                continue

            current_source = self._slab_level_source(slab, include_neighbor_context=False)
            level_links = self._ensure_slab_level_links(slab)
            has_explicit_level_label = any(
                isinstance(link, dict) and self._parse_slab_level_value(link.get('text')) is not None
                for link in (level_links.get('label', []) or [])
            )
            if current_source and (current_source.get('kind') == 'label' or has_explicit_level_label):
                # Existe texto explicito vinculado; deixa para validacao humana.
                continue

            has_cut = self._slab_has_cut_view(slab)
            sources = []
            reason = ''

            if has_cut:
                for own_cut in self._slab_cut_links(slab):
                    if not isinstance(own_cut, dict):
                        continue
                    for other in slabs:
                        if other is slab:
                            continue
                        other_src = level_sources.get(other.get('id') or other.get('name'))
                        if not other_src:
                            continue
                        for other_cut in self._slab_cut_links(other):
                            if isinstance(other_cut, dict) and self._same_cut_view_signature(own_cut, other_cut):
                                sources.append(dict(other_src))
                                break
                reason = 'cut_view_paired_with_validated_slab'
            else:
                for _dist, other in self._neighbor_slabs(slab, slabs, poly_map):
                    if self._slab_has_cut_view(other):
                        continue
                    src = level_sources.get(other.get('id') or other.get('name'))
                    if src:
                        sources.append(dict(src))
                reason = 'normal_neighbor_level_consensus'

            consensus = self._choose_consensus_level(sources)
            if consensus and not consensus.get('ambiguous'):
                self._apply_inferred_slab_level(slab, consensus['value'], reason, consensus['items'])
                inferred_count += 1
            elif has_cut:
                slab['level_inference'] = {
                    'status': 'needs_review',
                    'reason': 'cut_view_without_paired_level',
                    'cut_views': len(self._slab_cut_links(slab)),
                }

        # Part B — segunda passagem: usa delta geométrico dos cortes de viga
        delta_count = self._infer_slab_level_from_cut_deltas(slabs, level_sources, poly_map)

        if auto_cuts or auto_pillars or auto_neighbor_levels or inferred_count or delta_count:
            self.log(f"🧭 Lajes: {auto_cuts} visão(ões) de corte, {auto_pillars} pilar(es) de apoio, {auto_neighbor_levels} texto(s) de nível vizinho; {inferred_count} nível(is) por contexto, {delta_count} por delta de corte.")

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
                'laje_visao_corte': {'cut_view_geom': []}, # UI Field: laje_visao_corte
                'laje_vizinhas_niveis': {'neighbor_north': [], 'neighbor_east': [], 'neighbor_west': [], 'neighbor_south': []}, # UI Field: laje_vizinhas_niveis
                'laje_pilares_apoio': {'pillar_geom': [], 'pillar_label': []}, # UI Field: laje_pilares_apoio
                'laje_nivel': {'label': []}, # UI Field: laje_nivel
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


    def _scan_beam_segments(self, item_data):
        """Retorna contagem de segmentos (A, B, Fundo) baseada nas chaves do item_data."""
        seg_indices_a = {1}
        seg_indices_b = {1}
        seg_indices_fundo = {1}
        
        for key in item_data.keys():
            if '_seg_' not in key: continue
            try:
                # Ex: viga_a_seg_2_h1
                parts = key.split('_')
                if 'seg' in parts:
                    idx_pos = parts.index('seg') + 1
                    if idx_pos < len(parts):
                        idx = int(parts[idx_pos])
                        if key.startswith('viga_a_'): seg_indices_a.add(idx)
                        elif key.startswith('viga_b_'): seg_indices_b.add(idx)
                        elif key.startswith('viga_fundo_'): seg_indices_fundo.add(idx)
            except: pass
            
        return len(seg_indices_a), len(seg_indices_b), len(seg_indices_fundo)

    def _calculate_total_fields(self, item_data):
        """Calcula o total de campos esperados dinamicamente baseada na estrutura do item."""
        itype = str(item_data.get('type') or '').lower()
        
        if 'viga' in itype:
            # --- VIGAS ---
            # Campos Base: name, viga_segs (header), dim (fundo global)
            # Nota: 'dim' é adicionado no pack de fundo, mas como chave fixa, conta como 1 global.
            total = 2 
            
            # --- Segmentos Laterais (A e B) ---
            # Campos por segmento:
            # 1. comprimento_total
            # 2. comp_total_passa
            # 3. visao_corte
            # 4. ini_name
            # 5. end_name
            # 6. nivel_viga
            # 7. nivel_oposto
            # 8. laje_sup
            # 9. laje_cen
            # 10. laje_inf
            # 11. dim
            # 12. h1
            # 13. h2
            # (ajuste_comprimento é excuido)
            FIELDS_PER_SIDE_SEG = 13
            
            # --- Segmentos Fundo ---
            # Campos por segmento:
            # 1. area_segs
            # 2. largura
            # 3. comprimento
            # 4. local_ini
            # 5. local_fim
            # 6. abert_especial
            # 7. chanfro_esq_top
            # 8. chanfro_esq_fun
            # 9. chanfro_dir_top
            # 10. chanfro_dir_fun
            # (dim é global)
            FIELDS_PER_BOTTOM_SEG = 3
            
            # Contar Segmentos Ativos
            na, nb, nf = self._scan_beam_segments(item_data)
            
            total += na * FIELDS_PER_SIDE_SEG
            total += nb * FIELDS_PER_SIDE_SEG
            total += nf * FIELDS_PER_BOTTOM_SEG
            
            # Se houver fundo, adiciona 'dim' global
            if nf > 0:
                total += 1
                
            return total
            
        elif 'pilar' in itype:
            # --- PILARES ---
            # Header: name, dim, pilar_segs
            total = 3
            
            # Complex View: Shape Based
            shape = item_data.get('format', 'Retangular')
            sides = ['A', 'B', 'C', 'D']
            if shape == "Circular": sides = ["Superior", "Inferior"]
            elif shape == "Em L": sides = ['A', 'B', 'C', 'D', 'E', 'F']
            elif shape in ["Em T", "Em U"]: sides = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
            
            # Campos por Lado:
            # Laje 1: n, h, v, p, dist_c (5)
            # Laje 2: n, h, v, p, dist_c, dist_t (6)
            # Vigas (5 cats): n, d, segs, (dist? 3 sim, 2 nao), prof, diff_v
            #   Esq/Dir: n(1), d(1), segs(1), prof(0-nolink), diff(1) = 4
            #   Ch1/2/3: n(1), d(1), segs(1), dist(1), prof(0), diff(1) = 5
            # Viga Total = 2*4 + 3*5 = 8 + 15 = 23
            
            # Total por lado = 5 + 6 + 23 = 34
            FIELDS_PER_SIDE = 34
            
            total += len(sides) * FIELDS_PER_SIDE
            return total
            
        elif 'laje' in itype:
            # --- LAJES ---
            # name, laje_dim, laje_visao_corte, laje_vizinhas_niveis, laje_pilares_apoio,
            # laje_nivel, laje_outline_segs, laje_islands
            return 8
            
        return 10 # Default fallback

    def _calculate_completion(self, item_data, subtype=None):
        """Calcula % de completude dinâmico baseado no total de campos reais."""
        if not item_data: return 0.0
        itype = str(subtype or item_data.get('type') or '').lower()
        
        # 1. Se validado globalmente, 100%
        if item_data.get('is_fully_validated'):
            return 100.0

        # 2. Campos Validados ou N/A
        v_raw = item_data.get('validated_fields', [])
        n_raw = item_data.get('na_fields', [])
        
        val_fields = set(v_raw.keys()) if isinstance(v_raw, dict) else set(v_raw)
        na_fields = set(n_raw.keys()) if isinstance(n_raw, dict) else set(n_raw)
        done_fields = val_fields | na_fields

        if 'laje' in itype:
            laje_fields = {
                'name', 'laje_dim', 'laje_visao_corte', 'laje_vizinhas_niveis',
                'laje_pilares_apoio', 'laje_nivel', 'laje_outline_segs', 'laje_islands'
            }
            total_expected = len(laje_fields)
            total_done = len(done_fields & laje_fields)
            if total_expected <= 0: return 100.0
            return max(0.0, min(100.0, (total_done / total_expected) * 100))

        # ---- LÓGICA ISOLADA PARA SUB-ITENS DE VIGA ----
        is_sub_viga = itype in ['viga_lateral_a', 'viga_lateral_b', 'viga_fundo_c']
        if is_sub_viga:
            na_seg, nb_seg, nf_seg = self._scan_beam_segments(item_data)
            
            # Escolher qual prefixo procurar
            if itype == 'viga_lateral_a':
                prefix = 'viga_a_'
                seg_count = na_seg
            elif itype == 'viga_lateral_b':
                prefix = 'viga_b_'
                seg_count = nb_seg
            else:
                prefix = 'viga_fundo_'
                seg_count = nf_seg
                
            # 2 globais (nome, viga_segs) + 4 por segmento (geometria, dimensão, ap1, ap2)
            total_expected = 2 + (seg_count * 4)
            
            # Contar concluídos desta categoria
            total_done = 0
            if 'name' in done_fields: total_done += 1
            if 'viga_segs' in done_fields: total_done += 1
            
            for f in done_fields:
                if f.startswith(prefix):
                    total_done += 1
                    
            if total_expected <= 0: return 100.0
            pct = (total_done / total_expected) * 100
            return max(0.0, min(100.0, pct))
        # ------------------------------------------------

        total_done = len(done_fields)
        
        # 3. Bônus por Slots
        v_slots = item_data.get('validated_link_classes', {})
        n_slots = item_data.get('na_link_classes', {})
        done_slots_count = 0
        if isinstance(v_slots, dict) and isinstance(n_slots, dict):
            for field_key in done_fields:
                done_slots_count += len(v_slots.get(field_key, []))
                done_slots_count += len(n_slots.get(field_key, []))

        total_points = total_done + (done_slots_count * 0.1)
        
        total_expected = self._calculate_total_fields(item_data)
        if total_expected <= 0: return 100.0
        
        pct = (total_points / total_expected) * 100
        return max(0.0, min(100.0, pct))

    def _populate_generic_tree(self, tree_widget, items_list, item_type='pillar'):
        """Popula QTreeWidget com colunas: Item | Nome | Status | %"""
        # Limpar cache de itens deste widget específico antes de limpar o widget
        ids_to_clean = []
        for iid, widgets in self.tree_item_map.items():
            safe = []
            for w in widgets:
                try:
                    if w.treeWidget() != tree_widget:
                        safe.append(w)
                except RuntimeError:
                    pass  # objeto C++ já deletado
            self.tree_item_map[iid] = safe
        
        tree_widget.clear()
        
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtGui import QColor, QBrush
        
        for i, item_data in enumerate(items_list):
            if not item_data: continue
            # 1. Preparar Textos
            item_id_str = item_data.get('id_item', f"{i+1:02}")
            name = item_data.get('name', '?')
            
            # Info extra no nome
            if item_type == 'pillar':
                # CAD-UI-1.3: Badge de confiança B/H
                sides = item_data.get('sides_data', {})
                bh_conf = sides.get('bh_confidence') if sides else None
                b_val   = sides.get('b') if sides else None
                h_val   = sides.get('h') if sides else None
                if bh_conf is not None:
                    if bh_conf >= 0.7:
                        bh_badge = " ✓"   # verde — confiança alta
                    elif bh_conf >= 0.4:
                        bh_badge = " ⚠"   # amarelo — conferir
                    else:
                        bh_badge = " ?"   # vermelho — B/H incerto
                    if b_val and h_val:
                        display_name = f"{name}  {int(b_val)}×{int(h_val)}{bh_badge}"
                    else:
                        display_name = f"{name}{bh_badge}"
                else:
                    display_name = name
            elif item_type == 'slab':
                area = item_data.get('area', 0.0)
                # Tentar recalcular area se nao tiver
                if area == 0:
                     _, area = self._get_slab_real_geometry(item_data)
                try:
                    area = float(str(area).replace(',', '.'))
                except (ValueError, TypeError):
                    area = 0.0
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
            if self._sa_attention_has_note(item_type, item_data):
                status_icon = "⚠"
            
            # 3. % Completitude
            pct = self._calculate_completion(item_data)
            pct_str = f"{int(pct)}%"
            
            # Criar Item Tree
            tree_item = QTreeWidgetItem(tree_widget)
            tree_item.setText(0, str(item_id_str))
            tree_item.setText(1, str(display_name))
            tree_item.setText(2, str(status_icon))
            
            # Registrar no Cache para atualização ultra-rápida (Task_04)
            item_id = item_data.get('id') or item_data.get('id_item') or f"unknown_{i}"
            if item_id not in self.tree_item_map: self.tree_item_map[item_id] = []
            self.tree_item_map[item_id].append(tree_item)
            
            # 4. Colunas específicas
            if item_type == 'pillar':
                # Coluna "Classificação": NASCE / PASSA / SEGUE / MORRE / …
                classif = (
                    item_data.get('classification')
                    or (item_data.get('fields') or {}).get('Classificação')
                    or '—'
                )
                classif = str(classif).strip().upper() or '—'
                if classif in ('INDETERMINADO', ''):
                    classif = '—'
                tree_item.setText(3, str(pct_str))
                tree_item.setText(4, classif)
                _CLASSIF_COLORS = {
                    'NASCE':  '#4fc3f7',  # azul claro
                    'MORRE':  '#ef5350',  # vermelho
                    'PASSA':  '#ffb74d',  # laranja
                    'SEGUE':  '#81c784',  # verde
                    'CONTINUA': '#81c784',
                }
                _c = _CLASSIF_COLORS.get(classif)
                if _c:
                    tree_item.setForeground(4, QColor(_c))
                else:
                    tree_item.setForeground(4, QColor('#888'))

            if item_type == 'slab':
                tree_item.setText(3, str(pct_str))
                
                btn_detail = QPushButton("📋 Detalhes")
                btn_detail.setCursor(Qt.PointingHandCursor)
                btn_detail.setStyleSheet("background-color: #444; color: white; padding: 2px; border-radius: 3px; font-size: 10px;")
                btn_detail.clicked.connect(lambda checked=False, d=item_data: self.open_detail_window(d))
                tree_widget.setItemWidget(tree_item, 4, btn_detail)

            # Tooltip com detalhes (CAD-UI-1.3)
            if item_type == 'pillar':
                sides = item_data.get('sides_data', {})
                bh_conf = sides.get('bh_confidence') if sides else None
                tooltip_lines = [f"ID: {item_data.get('id_item', name)}"]
                if bh_conf is not None:
                    conf_pct = int(bh_conf * 100)
                    if bh_conf >= 0.7:
                        conf_label = f"Alta ({conf_pct}%)"
                    elif bh_conf >= 0.4:
                        conf_label = f"Média ({conf_pct}%) — confirmar"
                    else:
                        conf_label = f"Baixa ({conf_pct}%) — verificação manual"
                    tooltip_lines.append(f"Confiança B/H: {conf_label}")
                if sides:
                    b_v = sides.get('b')
                    h_v = sides.get('h')
                    if b_v and h_v:
                        tooltip_lines.append(f"Dimensões: {b_v}×{h_v} cm")
                    alt = sides.get('altura')
                    if alt:
                        tooltip_lines.append(f"Altura: {alt} cm")
                tree_item.setToolTip(0, "\n".join(tooltip_lines))
                tree_item.setToolTip(1, "\n".join(tooltip_lines))

            # Setup Data
            tree_item.setData(0, Qt.UserRole, item_id)

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

        # Ajusta coluna Nome ao conteúdo real (badge B/H pode ser mais largo)
        if item_type == 'pillar':
            tree_widget.resizeColumnToContents(1)


    def _populate_beam_tree(self, tree_widget, beam_list, list_type='lateral', pp_filter: str = ""):
        # Limpar cache de itens deste widget específico
        for iid, widgets in self.tree_item_map.items():
            safe = []
            for w in widgets:
                try:
                    if w.treeWidget() != tree_widget:
                        safe.append(w)
                except RuntimeError:
                    pass  # objeto C++ já deletado
            self.tree_item_map[iid] = safe

        tree_widget.clear()
        if not beam_list: return
        
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtGui import QColor

        import re
        def nat_key(name):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', name)]
            
        from collections import OrderedDict
        groups = OrderedDict()
        for b in beam_list:
            p_name = b.get('parent_name', b.get('name', 'V?'))
            if p_name not in groups:
                 groups[p_name] = []
            groups[p_name].append(b)
            
        sorted_groups = OrderedDict(sorted(groups.items(), key=lambda x: nat_key(x[0])))
            
        for p_name, segments in sorted_groups.items():
            parent_item = QTreeWidgetItem(tree_widget)
            
            clean_name = p_name
            if clean_name.startswith('F.'): clean_name = clean_name[2:]
            elif clean_name.startswith('L.'): clean_name = clean_name[2:]
            elif clean_name.startswith('FV-'): clean_name = clean_name[3:]
            elif clean_name.startswith('LV-'): clean_name = clean_name[3:]
            
            prefix = "FV-" if list_type == 'fundo' else "LV-"
            parent_item.setText(1, f"📁 {prefix}{clean_name}")
            parent_item.setExpanded(True)
            parent_item.setFlags(parent_item.flags() & ~Qt.ItemIsSelectable)
            
            for b in segments:
                # Status
                status = "⏱"
                if b.get('is_fully_validated'): status = "✔️"
                elif b.get('is_validated'): status = "✔️"
                elif b.get('issues'): status = "⚠️"
                if self._sa_attention_has_note("fundo" if list_type == "fundo" else "lateral", b):
                    status = "⚠"
                
                if list_type == 'lateral':
                    # pp_filter="para"/"passa" → sub-aba; "" → árvore completa (legado)
                    _pp_pairs = [('para', 'Para'), ('passa', 'Passa')]
                    if pp_filter:
                        _pp_pairs = [(tc, ts) for tc, ts in _pp_pairs if tc == pp_filter]

                    for tipo_comp, tipo_suffix in _pp_pairs:
                        if pp_filter:
                            # Sub-aba: sem sub_folder — direto no parent
                            _parent = parent_item
                        else:
                            sub_folder = QTreeWidgetItem(parent_item)
                            sub_folder.setText(1, f"📁 {prefix}{clean_name} {tipo_suffix}")
                            sub_folder.setExpanded(True)
                            sub_folder.setFlags(sub_folder.flags() & ~Qt.ItemIsSelectable)
                            _parent = sub_folder

                        child_a = QTreeWidgetItem(_parent)
                        child_a.setText(0, str(b.get('id_item', '00')))
                        child_a.setText(1, f"{prefix}{clean_name}.A {tipo_suffix}")
                        child_a.setText(2, str(status))
                        child_a.setText(3, f"{int(self._calculate_completion(b, subtype='viga_lateral_a'))}%")
                        child_a.setData(0, Qt.UserRole, str(b.get('id')))
                        child_a.setData(0, Qt.UserRole + 1, 'viga_lateral_a')
                        child_a.setData(0, Qt.UserRole + 2, tipo_comp)

                        child_b = QTreeWidgetItem(_parent)
                        child_b.setText(0, str(b.get('id_item', '00')))
                        child_b.setText(1, f"{prefix}{clean_name}.B {tipo_suffix}")
                        child_b.setText(2, str(status))
                        child_b.setText(3, f"{int(self._calculate_completion(b, subtype='viga_lateral_b'))}%")
                        child_b.setData(0, Qt.UserRole, str(b.get('id')))
                        child_b.setData(0, Qt.UserRole + 1, 'viga_lateral_b')
                        child_b.setData(0, Qt.UserRole + 2, tipo_comp)
                else:
                    # Fundo
                    child_f = QTreeWidgetItem(parent_item)
                    child_f.setText(0, str(b.get('id_item', '00')))
                    child_f.setText(1, f"{prefix}{clean_name}.C")
                    child_f.setText(2, str(status))
                    child_f.setText(3, f"{int(self._calculate_completion(b, subtype='viga_fundo_c'))}%")
                    child_f.setData(0, Qt.UserRole, str(b.get('id')))
                    child_f.setData(0, Qt.UserRole + 1, 'viga_fundo_c')

    def open_detail_window(self, item_data):
        """Abre a janela de detalhamento completa."""
        from src.ui.dialogs.detail_dialog import DetailDialog
        dlg = DetailDialog(item_data, parent=self)
        
        # Conectar sinais do card interno (se necessário propagar validações)
        # O DetailCard dentro do Dialog edita o item_data in-place.
        # Se validarmos algo lá, queremos atualizar a UI principal aqui.
        if hasattr(dlg.card, 'data_validated'):
            dlg.card.data_validated.connect(lambda: self._update_all_lists_ui())
        if hasattr(dlg.card, 'data_changed'):
            dlg.card.data_changed.connect(lambda: self.canvas.draw_item_links(item_data)) # Redesenha links
            
        dlg.exec()

        # Após fechar, garantir refresh
        self._update_all_lists_ui()

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
            self.list_beams_para.clear()
            self.list_beams_passa.clear()
            if hasattr(self, "list_beams_fundo"): self.list_beams_fundo.clear()
            self.list_slabs.clear()
            self.current_project_id = None
            self.meta_widget.setEnabled(False)
        

    def _slab_to_n1_robot_ficha(self, slab_data: dict) -> dict:
        """Converte uma laje do Structural Analyzer para o contrato do Robo/N3."""
        from src.core.laje_n1_to_robot_ficha import n1_laje_to_robot_ficha

        source = dict(slab_data or {})
        unified_poly, area_m2 = self._get_slab_real_geometry(source)
        if unified_poly:
            geom = unified_poly
            if getattr(geom, "geom_type", "") == "MultiPolygon":
                geom = max(geom.geoms, key=lambda g: g.area)
            try:
                coords = [[float(x), float(y)] for x, y in list(geom.exterior.coords)]
                if len(coords) > 1 and coords[0] == coords[-1]:
                    coords.pop()
                source["coordenadas"] = coords
                source["points"] = coords
                source["area_cm2"] = round(float(area_m2) * 10000.0, 2)
            except Exception:
                pass

        fields = source.get("fields") if isinstance(source.get("fields"), dict) else {}
        for key in (
            "laje_dim", "laje_nivel", "laje_linhas_v_count", "laje_linhas_h_count",
            "modo_selecionado", "unioes_nos_bordes", "observacoes",
            "pont_total", "pont_meio", "pont_linhas", "pont_colunas", "pont_tipo",
            "pont_altura_pav", "pont_comp_cm", "pont_larg_cm",
        ):
            if key not in source and key in fields:
                source[key] = fields[key]

        return n1_laje_to_robot_ficha(source)

    def _load_lj_n2_teacher_ficha(self, item_id: str) -> dict:
        """Lê ficha N2 aprovada/cacheada para treinar a ficha N3 da laje."""
        import json as _json
        import sqlite3 as _sqlite3

        obra_nome = None
        pav_nome = None
        try:
            obra_nome = self.cmb_works.currentData() or self.cmb_works.currentText()
            pav_nome = self._current_pavement_name()
        except Exception:
            pass
        if not obra_nome or not item_id:
            return {}

        try:
            conn = _sqlite3.connect(r"D:/Agente-cad-PYSIDE/project_data.vision")
            row = None
            if pav_nome:
                row = conn.execute(
                    "SELECT campos_json FROM reverse_eng_fichas "
                    "WHERE obra_name=? AND classe='LAJ' AND elemento_id=? AND pavimento LIKE ? "
                    "ORDER BY ROWID DESC LIMIT 1",
                    (obra_nome, item_id, f"%{pav_nome}%"),
                ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT campos_json FROM reverse_eng_fichas "
                    "WHERE obra_name=? AND classe='LAJ' AND elemento_id=? "
                    "ORDER BY ROWID DESC LIMIT 1",
                    (obra_nome, item_id),
                ).fetchone()
            conn.close()
            if row and row[0]:
                data = _json.loads(row[0])
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
        return {}

    def _load_lj_n4_teacher_ficha(self, item_id: str) -> dict:
        """Extrai ficha professora do DXF N4 quando não existe N2 salvo."""
        try:
            obra_nome = self.cmb_works.currentData() or self.cmb_works.currentText()
        except Exception:
            obra_nome = None
        if not obra_nome or not item_id:
            return {}
        try:
            from src.core.laj_n3_learning import extract_n4_dxf_ficha
            from pathlib import Path as _Path
            n4_path = (
                _Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
                / str(obra_nome)
                / "Fase-6_Execucao_CAD"
                / "n4"
                / f"LJ_preview_{item_id}.dxf"
            )
            if n4_path.exists():
                return extract_n4_dxf_ficha(n4_path, item_id)
        except Exception:
            return {}
        return {}

    @staticmethod
    def _merge_lj_n3_teacher(base_ficha: dict, teacher: dict) -> dict:
        """Gera ficha N3/Robo a partir do SA/N1, sem copiar gabarito N2/N4."""
        out = dict(base_ficha)
        try:
            from src.core.laj_n3_learning import apply_learning_to_ficha
            out = apply_learning_to_ficha(out, teacher=None, record_teacher=False)
        except Exception:
            pass
        meta = dict(out.get("_sa_meta") or {})
        meta["n3_source"] = "structural_analyzer_n1"
        meta["n3_teacher"] = None
        out["_sa_meta"] = meta
        return out

    def _materialize_slabs_for_n1_n3_and_robo(self) -> tuple[int, int]:
        """Materializa lajes SA em JSON_Lajes e slab_elements para N1/N3/loops."""
        if not getattr(self, "current_project_id", None):
            return 0, 0
        from pathlib import Path as _Path
        import json as _json
        import sqlite3 as _sqlite3
        from datetime import datetime as _dt

        obra_nome = None
        try:
            if hasattr(self, "cmb_works"):
                obra_nome = self.cmb_works.currentData() or self.cmb_works.currentText()
        except Exception:
            obra_nome = None
        obra_nome = obra_nome or "Obra_TREINO_1"
        obra_dir = _Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS") / str(obra_nome)
        json_dir = obra_dir / "Fase-4_Sincronizacao" / "JSON_Lajes"
        json_dir.mkdir(parents=True, exist_ok=True)

        fichas = []
        for slab in getattr(self, "slabs_found", []) or []:
            try:
                ficha = self._slab_to_n1_robot_ficha(slab)
                if not ficha.get("nome"):
                    continue
                ficha["_sa_meta"] = {
                    "source": "structural_analyzer",
                    "project_id": self.current_project_id,
                    "id_item": slab.get("id_item"),
                    "validated_fields": slab.get("validated_fields", []),
                    "validated_link_classes": slab.get("validated_link_classes", {}),
                }
                n3_ficha = self._merge_lj_n3_teacher(ficha, {})
                (json_dir / f"{ficha['nome']}.json").write_text(
                    _json.dumps(n3_ficha, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                fichas.append((slab, n3_ficha))
            except Exception as exc:
                self.log(f"⚠️ Laje {slab.get('name', '?')}: falha ao materializar N3 ({exc})")

        if not fichas:
            return 0, 0

        conn = self.db._get_conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS slab_elements (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    laje_nome TEXT,
                    classe TEXT DEFAULT 'LAJ',
                    campos_json TEXT,
                    n_linhas INTEGER DEFAULT 0,
                    is_validated BOOLEAN DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_slab_elements_project "
                "ON slab_elements(project_id, classe, laje_nome)"
            )
            now = _dt.now().isoformat(timespec="seconds")
            for slab, ficha in fichas:
                name = ficha["nome"]
                n_linhas = len(ficha.get("linhas_verticais") or []) + len(ficha.get("linhas_horizontais") or [])
                el_id = f"BE-LAJ-{self.current_project_id}-{name}"
                row = conn.execute(
                    "SELECT is_validated FROM slab_elements WHERE id=?",
                    (el_id,),
                ).fetchone()
                if row and int(row[0] or 0) == 1:
                    continue
                campos = dict(ficha)
                campos.update({
                    "laje_dim": (slab.get("fields") or {}).get("laje_dim") or slab.get("laje_dim"),
                    "laje_nivel": (slab.get("fields") or {}).get("laje_nivel") or slab.get("laje_nivel"),
                    "links": slab.get("links", {}),
                    "fields": slab.get("fields", {}),
                })
                conn.execute(
                    """
                    INSERT INTO slab_elements
                        (id, project_id, laje_nome, classe, campos_json, n_linhas,
                         is_validated, created_at, updated_at)
                    VALUES (?, ?, ?, 'LAJ', ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        campos_json=excluded.campos_json,
                        n_linhas=excluded.n_linhas,
                        is_validated=excluded.is_validated,
                        updated_at=excluded.updated_at
                    """,
                    (
                        el_id,
                        self.current_project_id,
                        name,
                        _json.dumps(campos, ensure_ascii=False),
                        int(n_linhas),
                        1 if slab.get("is_validated") else 0,
                        now,
                        now,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

        return len(fichas), len(fichas)

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
        import re
        def nat_key(x):
            # FIX: Garantir string e tratar None (evita crash TypeError no re.split)
            name = str(x.get('name') or x.get('nome') or '')
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]


        # Bloquear sinais das tree widgets para evitar selecao automatica
        trees = [self.list_slabs, self.list_slabs_valid, self.list_pillars, self.list_pillars_valid,
                 self.list_beams, self.list_beams_para, self.list_beams_passa,
                 self.list_beams_fundo, self.list_beams_valid, self.list_beams_fundo_valid]
        for tw in trees: tw.blockSignals(True)
        # 1. Limpar TODAS as listas (Já feito dentro dos populates, mas ok garantir)
        
        # 2. Popular Pilares
        if hasattr(self, 'pillars_found') and self.pillars_found:
             self.pillars_found.sort(key=nat_key)
        
        # Análise
        self._populate_generic_tree(self.list_pillars, self.pillars_found, 'pillar')
        
        # Biblioteca Validada (Pilares)
        valid_pillars = [p for p in self.pillars_found if p.get('is_validated')]
        valid_pillars.sort(key=nat_key)
        self._populate_generic_tree(self.list_pillars_valid, valid_pillars, 'pillar')

        # 3. Popular Vigas (Hierárquico)
        if hasattr(self, 'beams_found') and self.beams_found:
             self.beams_found.sort(key=nat_key)
        self._populate_beam_tree(self.list_beams, self.beams_found, "lateral")
        self._populate_beam_tree(self.list_beams_fundo, self.beams_found, "fundo")
        # Sub-abas Para/Passam: limpar para forçar populate lazy na próxima seleção
        self.list_beams_para.clear()
        self.list_beams_passa.clear()
        # Se há sub-aba ativa, popular imediatamente
        if hasattr(self, '_lv_analysis_tabs'):
            idx = self._lv_analysis_tabs.currentIndex()
            tree = self.list_beams_para if idx == 0 else self.list_beams_passa
            pp   = "para"             if idx == 0 else "passa"
            self._populate_beam_tree(tree, self.beams_found, "lateral", pp)

        # Vigas Validadas
        valid_beams = [b for b in self.beams_found if b.get('is_validated')]
        valid_beams.sort(key=nat_key)
        self._populate_beam_tree(self.list_beams_valid, valid_beams, "lateral")
        self._populate_beam_tree(self.list_beams_fundo_valid, valid_beams, "fundo")

        # 4. Popular Lajes
        if hasattr(self, 'slabs_found') and self.slabs_found:
             self.slabs_found.sort(key=nat_key)
        # Análise
        self._populate_generic_tree(self.list_slabs, self.slabs_found, 'slab')

        # Biblioteca Validada (Lajes)
        valid_slabs = [s for s in self.slabs_found if s.get('is_validated')]
        valid_slabs.sort(key=nat_key)
        self._populate_generic_tree(self.list_slabs_valid, valid_slabs, 'slab')
        
        # 5. Contornos / Issues
        self.list_issues.clear()
        if hasattr(self, 'list_contours'): self.list_contours.clear()
        
        self.log(f"📊 Listas UI Atualizadas: {len(self.pillars_found)}P, {len(self.beams_found)}V, {len(self.slabs_found)}L.")
             
        # Repopular Issues
        for p in self.pillars_found:
            conf_map = p.get('confidence_map', {})
            avg_conf = sum(conf_map.values()) / len(conf_map) if conf_map else 0.5
            if p.get('issues') or (avg_conf < 0.6 and not p.get('is_validated')):
                self._add_to_issues_list(p, avg_conf)
        
        # --- FIX: Sincronizar Aba de Treinamento ---
        if hasattr(self, 'tab_training') and self.tab_training:
             self.tab_training.current_project_id = self.current_project_id
             self.tab_training.refresh_list()
                
        self.log(f"UI Atualizada: {len(self.pillars_found)}P, {len(self.beams_found)}V, {len(self.slabs_found)}L")

        # --- FIX: CANVAS REDRAW PARA REMOVER FANTASMAS ---
        # Garantir que o canvas mostre exatamente o que está nos dados "healados" (points atualizados)
        if hasattr(self, 'canvas') and self.canvas:
             # Redesenha lajes para refletir geometrias atualizadas (sem fantasmas verdes)
             self.canvas.draw_slabs(self.slabs_found)
             # Redesenha pilares e vigas também para consistência
             self.canvas.draw_interactive_pillars(self.pillars_found)
             self.canvas.draw_beams(self.beams_found)
             
             self._update_canvas_filter(self.module_tabs.currentIndex())
        # -------------------------------------------------
        # Desbloquear sinais
        for tw in trees: tw.blockSignals(False)

    
    def _dump_slab_diagnostics(self):
        """Write detailed slab detection diagnostics to JSON file for analysis."""
        import json, datetime, os
        from pathlib import Path
        
        try:
            # Load N2 teacher data for comparison
            n2_data = {}
            try:
                projects_repo = os.path.join(os.path.dirname(__file__), "projects_repo")
                if self.current_project_id:
                    proj_n2_dir = os.path.join(projects_repo, self.current_project_id, "laje_data")
                    obras_json = os.path.join(proj_n2_dir, "obras.json")
                    if os.path.isfile(obras_json):
                        with open(obras_json, "r", encoding="utf-8") as f:
                            raw = json.load(f)
                        for obra in raw.get("obras", []):
                            for pav in obra.get("pavimentos", []):
                                for laje in pav.get("lajes", []):
                                    nome = laje.get("nome", "").upper()
                                    if nome:
                                        n2_data[nome] = laje
            except Exception as e:
                self.log(f"[DIAG] N2 load error: {e}")
            
            slabs_report = []
            for s in self.slabs_found:
                name = s.get("name", "?")
                entry = {
                    "name": name,
                    "id": s.get("id", "?"),
                    "validated": s.get("is_validated", False),
                    "validated_fields": s.get("validated_fields", []),
                    "area": None,
                    "points_count": 0,
                    "confidence_score": s.get("confidence_score"),
                    "confidence_level": s.get("confidence_level"),
                    "n2_teacher_matched": s.get("n2_teacher_matched", False),
                    "outline_source": s.get("outline_source", "?"),
                    "polygon_area": None,
                    "polygon_bounds": None,
                    "polygon_dims": None,
                    "internal_lines": {"h": 0, "v": 0},
                    "issues": s.get("issues", []),
                    "n2_comparison": None,
                }
                
                # Area
                area = s.get("area", 0)
                try:
                    entry["area"] = float(str(area).replace(",", "."))
                except:
                    entry["area"] = str(area)
                
                # Points and polygon info
                pts = s.get("points", [])
                if pts:
                    entry["points_count"] = len(pts)
                    from shapely.geometry import Polygon as ShapelyPolygon
                    try:
                        poly = ShapelyPolygon(pts)
                        if poly.is_valid and not poly.is_empty:
                            entry["polygon_area"] = round(poly.area, 2)
                            bounds = [round(v, 2) for v in poly.bounds]
                            entry["polygon_bounds"] = bounds
                            entry["polygon_dims"] = {
                                "width": round(bounds[2] - bounds[0], 2),
                                "height": round(bounds[3] - bounds[1], 2),
                            }
                    except:
                        pass
                
                # N2 comparison
                n2_entry = n2_data.get(name.upper())
                if n2_entry:
                    n2_comp = {
                        "comprimento_n2": n2_entry.get("comprimento"),
                        "largura_n2": n2_entry.get("largura"),
                        "area_n2_cm2": n2_entry.get("area_cm2"),
                        "has_coords": bool(n2_entry.get("coordenadas")),
                    }
                    if entry["polygon_dims"] and n2_comp.get("comprimento_n2") and n2_comp.get("largura_n2"):
                        pw = entry["polygon_dims"]["width"]
                        ph = entry["polygon_dims"]["height"]
                        tc = float(n2_comp["comprimento_n2"])
                        tl = float(n2_comp["largura_n2"])
                        # Best orientation match
                        d1 = min(abs(pw - tc) + abs(ph - tl), abs(pw - tl) + abs(ph - tc))
                        dim_delta = d1 / max(tc + tl, 1.0)
                        n2_comp["dim_delta"] = round(dim_delta, 4)
                        n2_comp["match_quality"] = "EXCELENTE" if dim_delta <= 0.02 else ("BOM" if dim_delta <= 0.05 else ("REGULAR" if dim_delta <= 0.10 else "RUIM"))
                        n2_comp["detected_width"] = pw
                        n2_comp["detected_height"] = ph
                    entry["n2_comparison"] = n2_comp
                
                # Internal lines
                entry["internal_lines"]["h"] = len(s.get("linhas_horizontais", []))
                entry["internal_lines"]["v"] = len(s.get("linhas_verticais", []))
                
                # Links summary
                links = s.get("links", {})
                entry["link_slots"] = list(links.keys())
                slabs_report.append(entry)
            
            # Summary statistics
            total = len(slabs_report)
            validated = [s for s in slabs_report if s["validated"]]
            non_validated = [s for s in slabs_report if not s["validated"]]
            
            # N2 match analysis
            n2_matched = [s for s in slabs_report if s.get("n2_comparison")]
            n2_excellent = [s for s in n2_matched if s["n2_comparison"].get("match_quality") == "EXCELENTE"]
            n2_bom = [s for s in n2_matched if s["n2_comparison"].get("match_quality") == "BOM"]
            n2_regular = [s for s in n2_matched if s["n2_comparison"].get("match_quality") == "REGULAR"]
            n2_ruim = [s for s in n2_matched if s["n2_comparison"].get("match_quality") == "RUIM"]
            
            report = {
                "timestamp": datetime.datetime.now().isoformat(),
                "project_id": getattr(self, "current_project_id", None),
                "total_slabs": total,
                "validated_count": len(validated),
                "non_validated_count": len(non_validated),
                "n2_available_count": len(n2_matched),
                "n2_quality": {
                    "excelente": len(n2_excellent),
                    "bom": len(n2_bom),
                    "ruim": len(n2_ruim),
                },
                "validated_slabs": [
                    {
                        "name": s["name"],
                    } for s in validated
                ],
                "non_validated_slabs": [
                    {
                        "name": s["name"],
                        "confidence": s["confidence_score"],
                        "confidence_level": s["confidence_level"],
                        "n2_quality": (s.get("n2_comparison") or {}).get("match_quality", "N/A"),
                        "dim_delta": (s.get("n2_comparison") or {}).get("dim_delta"),
                    }
                    for s in non_validated
                ],
                "slabs": slabs_report,
            }
            
            out_path = Path(__file__).parent / "debug_slab_pav13.json"
            out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            self.log(f"📊 Dump diagnostico: {total} lajes ({len(validated)} validadas, {len(n2_matched)} c/ N2) -> {out_path.name}")
            self.log(f"   N2: {len(n2_excellent)} excelente, {len(n2_bom)} bom, {len(n2_regular)} regular, {len(n2_ruim)} ruim")
        except Exception as e:
            print(f"[DIAG DUMP ERROR] {e}")
            import traceback
            traceback.print_exc()

    def on_detail_validation_changed(self, payload):
        """Sincronizacao leve para cliques de Validar por campo/slot."""
        if not self.current_card:
            return

        try:
            item_data = payload.get('item') if isinstance(payload, dict) else None
            if item_data is None:
                item_data = self.current_card.item_data

            itype = str(item_data.get('type') or '').lower()

            if self.current_project_id:
                if 'viga' in itype:
                    self.db.save_beam(item_data, self.current_project_id, trust_current_validation=True)
                elif 'pilar' in itype:
                    self.db.save_pillar(item_data, self.current_project_id, trust_current_validation=True)
                elif 'laje' in itype:
                    self.db.save_slab(item_data, self.current_project_id, trust_current_validation=True)

            self._sync_list_item_text(item_data)

            # [AJUSTE] Chamar draw_item_links para reconstruir as geometrias e aplicar a nova cor (verde)
            if self.canvas and self.canvas.scene:
                self.canvas.draw_item_links(item_data, clear=True, destination='focus')
                self.canvas.scene.update()
                self.canvas.viewport().update()
        except Exception as e:
            import traceback
            self.log(f"❌ Erro em on_detail_validation_changed: {e}")
            print(traceback.format_exc())

    def on_detail_data_changed(self, data):
        """Callback genérico para mudanças nos dados do DetailCard (remoção de links, etc)"""
        if not self.current_card: return
        
        try:
            item_data = self.current_card.item_data
            itype = str(item_data.get('type') or '').lower()
            
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
                if self.current_project_id: self.db.save_beam(item_data, self.current_project_id, trust_current_validation=True)
                # Sub-itens LV-A/LV-B/FV têm type='viga_lateral_a' etc.; evitar focus_on_beam_geometry
                # que desenharia todos os links em marrom causando duplo destaque com draw_item_links
                _is_viga_subitem = itype in {'viga_lateral_a', 'viga_lateral_b', 'viga_fundo_c'}
                if not _is_viga_subitem:
                    self.canvas.focus_on_beam_geometry(item_data, apply_zoom=False, clear=False)
                self.canvas.draw_item_links(item_data, destination='focus', clear=False)
                # AJUSTE 1 & 2: Atualiza também a visão global (persistente) para não deixar "fantasmas"
                self.canvas.draw_item_links(item_data, destination='beam', clear=False)
            elif 'pilar' in itype:
                if self.current_project_id: self.db.save_pillar(item_data, self.current_project_id, trust_current_validation=True)
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
                
                if self.current_project_id: self.db.save_slab(item_data, self.current_project_id, trust_current_validation=True)

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
        """Atualiza o texto da lista lateral sem reconstruir toda a UI - Versão O(1) Cache"""
        # from PySide6.QtWidgets import QTreeWidgetItemIterator # Desnecessário agora
        from PySide6.QtGui import QColor
        itype = str(item_data.get('type') or '').lower()
        iid = item_data.get('id')
        
        if iid not in self.tree_item_map or not self.tree_item_map[iid]:
            return # Item não está visível em nenhuma lista no momento
        
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
            # Sincronizado com a lógica de _populate_generic_tree
            display_name = new_name
        elif 'viga' in itype:
            display_name = new_name
        elif 'laje' in itype:
            area = item_data.get('area', 0.0)
            if area == 0: _, area = self._get_slab_real_geometry(item_data)
            try:
                area = float(str(area).replace(',', '.'))
            except (ValueError, TypeError):
                area = 0.0
            display_name = f"{new_name} ({area:.2f}m²)"
        
        # Atualizar todos os widgets em cache para este ID
        for item in self.tree_item_map[iid]:
            try:
                # Obter subtype específico da árvore se existir (ex: viga_lateral_a)
                subtype = item.data(0, Qt.UserRole + 1)
                if not subtype: subtype = itype
                
                # Recalcular % específico para a linha da árvore (Global, Fundo, ou Lateral)
                local_pct = self._calculate_completion(item_data, subtype=subtype)
                local_pct_str = f"{int(local_pct)}%"

                # Comum a todos: 1: Nome, 2: Status
                item.setText(1, display_name)
                item.setText(2, status)
                
                # Específico por tipo
                if 'pillar' in itype:
                    # Somente colunas 0, 1, 2
                    pass
                elif 'viga' in itype:
                    # 3: %, 4: Seg A, 5: Seg B (se existirem)
                    na, nb, _ = self._scan_beam_segments(item_data)
                    item.setText(3, local_pct_str)
                    
                    # Evitar erro de índice em árvores que não têm colunas 4 e 5 (como a de Fundo que foi reestruturada)
                    if item.treeWidget() and item.treeWidget().columnCount() > 4:
                        item.setText(4, str(na))
                        item.setText(5, str(nb))
                elif 'laje' in itype:
                    # 3: %, 4: Botão (não muda ao setar texto)
                    item.setText(3, local_pct_str)
                
                # Atualizar cor status
                color = QColor("#dddddd")
                if item_data.get('is_fully_validated'): color = QColor("#00d4ff")
                elif item_data.get('is_validated'): color = Qt.green
                elif item_data.get('issues'): color = Qt.red
                
                # Colorir dependendo do número de colunas do item
                max_col = 3 if 'pillar' in itype else 5
                for c in range(max_col):
                    item.setForeground(c, color)
            except RuntimeError:
                # Widget pode ter sido deletado se a aba mudou rapidamente
                pass

    def _migrate_beam_data(self, beam):
        """
        Migra dados de vigas da estrutura antiga para a nova estrutura.
        Move seg_side_a/seg_side_b de viga_segs para novos campos nas abas A/B.
        Move adjustment de comprimento_total para novos campos de ajuste.
        """
        if not beam or str(beam.get('type') or '').lower() != 'viga':
            return
        
        if 'links' not in beam:
            beam['links'] = {}
        
        links = beam['links']
        needs_migration = False
        
        # Verificar se precisa migrar: viga_segs contém seg_side_a ou seg_side_b
        viga_segs = links.get('viga_segs', {})
        if isinstance(viga_segs, dict):
            has_side_a = 'seg_side_a' in viga_segs and viga_segs['seg_side_a']
            has_side_b = 'seg_side_b' in viga_segs and viga_segs['seg_side_b']
            
            if has_side_a or has_side_b:
                needs_migration = True
        
        # Verificar se comprimento_total tem adjustment que precisa ser migrado
        # Verificar todos os segmentos (viga_a_seg_1, viga_b_seg_1, etc.)
        for field_key in list(links.keys()):
            if '_comprimento_total' in field_key:
                comp_total_links = links.get(field_key, {})
                if isinstance(comp_total_links, dict) and 'adjustment' in comp_total_links:
                    if comp_total_links['adjustment']:
                        needs_migration = True
                        break
        
        if not needs_migration:
            return
        
        # Executar migração
        migrated = False
        
        # 1. Migrar seg_side_a para viga_a_seg_1_comp_total_passa
        if isinstance(viga_segs, dict) and 'seg_side_a' in viga_segs:
            seg_side_a_data = viga_segs.get('seg_side_a', [])
            if seg_side_a_data:
                # Encontrar ou criar campo para segmento 1 do lado A
                field_key_a = 'viga_a_seg_1_comp_total_passa'
                if field_key_a not in links:
                    links[field_key_a] = {}
                if 'seg_side_a' not in links[field_key_a]:
                    links[field_key_a]['seg_side_a'] = []
                
                # Mover dados preservando metadata (treino, validação, etc)
                links[field_key_a]['seg_side_a'] = seg_side_a_data
                
                # Remover de viga_segs
                del viga_segs['seg_side_a']
                migrated = True
        
        # 2. Migrar seg_side_b para viga_b_seg_1_comp_total_passa
        if isinstance(viga_segs, dict) and 'seg_side_b' in viga_segs:
            seg_side_b_data = viga_segs.get('seg_side_b', [])
            if seg_side_b_data:
                # Encontrar ou criar campo para segmento 1 do lado B
                field_key_b = 'viga_b_seg_1_comp_total_passa'
                if field_key_b not in links:
                    links[field_key_b] = {}
                if 'seg_side_b' not in links[field_key_b]:
                    links[field_key_b]['seg_side_b'] = []
                
                # Mover dados preservando metadata
                links[field_key_b]['seg_side_b'] = seg_side_b_data
                
                # Remover de viga_segs
                del viga_segs['seg_side_b']
                migrated = True
        
        # 3. Migrar adjustment de comprimento_total para campos de ajuste
        # Procurar todos os campos de comprimento_total (pode haver múltiplos segmentos)
        for field_key in list(links.keys()):
            if '_comprimento_total' in field_key:
                comp_total_links = links.get(field_key, {})
                if isinstance(comp_total_links, dict) and 'adjustment' in comp_total_links:
                    adjustment_data = comp_total_links.get('adjustment', [])
                    if adjustment_data:
                        # Determinar se é lado A ou B baseado no field_key
                        if 'viga_a_' in field_key:
                            # Extrair índice do segmento (ex: viga_a_seg_1_comprimento_total -> 1)
                            try:
                                parts = field_key.split('_')
                                seg_idx = parts[parts.index('seg') + 1] if 'seg' in parts else '1'
                                ajuste_key = f'viga_a_seg_{seg_idx}_ajuste_comprimento'
                                
                                if ajuste_key not in links:
                                    links[ajuste_key] = {}
                                if 'adjustment' not in links[ajuste_key]:
                                    links[ajuste_key]['adjustment'] = []
                                
                                links[ajuste_key]['adjustment'] = adjustment_data
                                
                                # Remover adjustment de comprimento_total
                                del comp_total_links['adjustment']
                                migrated = True
                            except:
                                pass
                        elif 'viga_b_' in field_key:
                            try:
                                parts = field_key.split('_')
                                seg_idx = parts[parts.index('seg') + 1] if 'seg' in parts else '1'
                                ajuste_key = f'viga_b_seg_{seg_idx}_ajuste_comprimento'
                                
                                if ajuste_key not in links:
                                    links[ajuste_key] = {}
                                if 'adjustment' not in links[ajuste_key]:
                                    links[ajuste_key]['adjustment'] = []
                                
                                links[ajuste_key]['adjustment'] = adjustment_data
                                
                                # Remover adjustment de comprimento_total
                                del comp_total_links['adjustment']
                                migrated = True
                            except:
                                pass
        
        # 4. Garantir que viga_segs contenha apenas seg_bottom
        if isinstance(viga_segs, dict):
            # Remover qualquer seg_side_a ou seg_side_b que possa ter sobrado
            if 'seg_side_a' in viga_segs:
                del viga_segs['seg_side_a']
            if 'seg_side_b' in viga_segs:
                del viga_segs['seg_side_b']
            # Manter apenas seg_bottom (ou criar se não existir)
            if 'seg_bottom' not in viga_segs:
                viga_segs['seg_bottom'] = []
        
        # Salvar viga migrada de volta ao banco
        if migrated and self.current_project_id:
            try:
                self.db.save_beam(beam, self.current_project_id)
                self.log(f"✅ Viga {beam.get('name', 'N/A')} migrada automaticamente")
            except Exception as e:
                self.log(f"⚠️ Erro ao salvar viga migrada: {e}")

    def _attention_current_obra_pav(self):
        obra = ""
        pav = ""
        try:
            if hasattr(self, "sa_cmb_obras") and self.sa_cmb_obras.currentText():
                obra = self.sa_cmb_obras.currentText()
            else:
                obra = self.current_project_name or getattr(self, "project_name", "") or ""
        except Exception:
            pass
        try:
            if hasattr(self, "sa_cmb_pavimentos") and self.sa_cmb_pavimentos.currentData():
                data = self.sa_cmb_pavimentos.currentData()
                pav = data[1] if isinstance(data, tuple) and len(data) > 1 else self.sa_cmb_pavimentos.currentText()
            elif hasattr(self, "cmb_pavements"):
                pav = self._current_pavement_name()
            elif hasattr(self, "current_pavimento") and self.current_pavimento:
                pav = str(self.current_pavimento)
            elif hasattr(self, "pavimento_atual") and self.pavimento_atual:
                pav = str(self.pavimento_atual)
            elif hasattr(self, "selected_pavimento") and self.selected_pavimento:
                pav = str(self.selected_pavimento)
        except Exception:
            pass
        return obra, pav

    def _sa_attention_class_item(self, item_data, item_type_hint=None):
        typ = str(item_type_hint or item_data.get("type") or "").lower()
        name = str(item_data.get("name") or item_data.get("parent_name") or item_data.get("id_item") or item_data.get("id") or "")
        item_id = name
        if typ in ("pillar", "pilar") or "pilar" in typ:
            cls = "PL"
        elif typ in ("slab", "laje") or "laje" in typ:
            cls = "LJ"
        elif "fundo" in typ:
            cls = "FV"
        elif "lateral" in typ:
            cls = "LV"
        elif str(item_data.get("type") or "").lower() == "viga":
            cls = "FV" if item_type_hint == "fundo" else "LV"
        else:
            cls = str(item_data.get("class") or item_data.get("classe") or typ or "SA").upper()
        import re as _re_att
        item_id = _re_att.sub(r"^(?:FV-|LV-|F\.|L\.)", "", item_id, flags=_re_att.IGNORECASE)
        item_id = _re_att.sub(r"\.(?:A|B|C)(?:\s+(?:Para|Passa))?$", "", item_id, flags=_re_att.IGNORECASE)
        return cls, item_id or str(item_data.get("id") or "")

    def _sa_attention_has_note(self, item_type, item_data):
        try:
            obra, pav = self._attention_current_obra_pav()
            cls, item_id = self._sa_attention_class_item(item_data, item_type)
            return has_attention(obra, pav, cls, item_id, "SA")
        except Exception:
            return False

    def _build_sa_attention_widget(self, display_data):
        obra, pav = self._attention_current_obra_pav()
        cls, item_id = self._sa_attention_class_item(display_data, display_data.get("type"))
        meta = load_attention(obra, pav, cls, item_id, "SA")
        box = QFrame()
        box.setFixedHeight(86)
        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        box.setStyleSheet(
            "QFrame { background-color: #171717; border: 1px solid #444; border-radius: 3px; }"
            "QLabel { color: #ffb020; font-size: 10px; font-weight: bold; border: none; }"
            "QTextEdit { background-color: #222; color: #f0f0f0; border: 1px solid #555; "
            "border-radius: 3px; font-size: 10px; }"
        )
        lay = QVBoxLayout(box)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(3)
        lay.addWidget(QLabel("ATENÇÃO"))
        edit = QTextEdit()
        edit.setFixedHeight(46)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        edit.setPlaceholderText("Mensagem/instrucao persistente deste item para o chat...")
        edit.setPlainText(meta.get("note", ""))
        lay.addWidget(edit)

        def _save():
            note = edit.toPlainText()
            save_attention(obra, pav, cls, item_id, "SA", bool(note.strip()), note)
            try:
                display_data["attention_note"] = note
            except Exception:
                pass
            try:
                self._update_all_lists_ui()
            except Exception:
                pass

        edit.textChanged.connect(_save)
        return box

    def show_detail(self, item_data, override_type=None, tipo_comp=None):
        """Exibe os detalhes do item no painel direito."""
        # Migração automática se for viga (antes de exibir)
        if str(item_data.get('type') or '').lower() == 'viga':
            self._migrate_beam_data(item_data)

        # Limpar anterior
        while self.detail_layout.count():
            child = self.detail_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        # Injetar sincronização
        display_data = item_data
        if override_type:
            display_data = item_data.copy()
            # TÚNEL DE VALIDAÇÃO: Compartilhar as listas de validação na memória
            display_data['validated_fields'] = item_data.setdefault('validated_fields', [])
            display_data['validated_link_classes'] = item_data.setdefault('validated_link_classes', {})
            display_data['is_validated'] = item_data.get('is_validated', False)

            display_data['type'] = override_type
            # Tipo para/passa da subpasta LV (define qual campo "Linha Comprimento" mostrar)
            if tipo_comp:
                display_data['_tipo_comp'] = tipo_comp
            orig_name = display_data.get('name', 'V?')

            # Extrair nome base (sem prefixo FV-/LV-/F./L. e sem sufixo .C/.A/.B/-N)
            import re as _re_disp
            _m_base = _re_disp.match(r'^(?:FV-|LV-|F\.|L\.)(.+?)(?:\.(?:C|A|B)(?:-\d+)?)?$', orig_name)
            if _m_base:
                orig_name = _m_base.group(1)

            # Sufixo de tipo no nome do card (ex: "LV-V305.A Para" / "LV-V305.A Passa")
            _tipo_suffix = {'para': ' Para', 'passa': ' Passa'}.get(tipo_comp, '')
            if override_type == 'viga_lateral_a':
                display_data['name'] = f'LV-{orig_name}.A{_tipo_suffix}'
            elif override_type == 'viga_lateral_b':
                display_data['name'] = f'LV-{orig_name}.B{_tipo_suffix}'
            elif override_type and override_type.startswith('viga_fundo_c'):
                display_data['name'] = f'FV-{orig_name}.C'
                display_data['type'] = 'viga_fundo_c'

        # Criar novo card
        self.current_card = DetailCard(display_data)
        
        # Conectar Sinais
        self.current_card.pick_requested.connect(self.on_pick_requested)
        self.current_card.focus_requested.connect(self.on_focus_requested)
        self.current_card.data_validated.connect(self.on_card_validated)
        self.current_card.element_removed.connect(self.on_element_removed)
        self.current_card.data_changed.connect(self.on_detail_data_changed)
        self.current_card.validation_changed.connect(self.on_detail_validation_changed)
        self.current_card.research_requested.connect(self.on_research_requested)
        self.current_card.element_focused.connect(self.on_element_focused_on_table)
        self.current_card.training_requested.connect(self.on_train_requested)
        self.current_card.log_requested.connect(self.log)
        
        self.detail_layout.addWidget(self._build_sa_attention_widget(display_data))
        self.detail_layout.addWidget(self.current_card)
        
        # Atualizar título do painel (opcional)
        self.right_panel.setCurrentIndex(1)
    
    def _update_all_beams_tipo_comp(self, tipo: str):
        """Define o modo Para/Passa padrão de todas as vigas (sidebar global).
        Grava '_tipo_comp' na raiz de cada beam e salva no DB.
        Se houver um card LV aberto, recria-o com o novo tipo.
        tipo: 'para' ou 'passa'
        """
        if not self.beams_found:
            return

        updated_count = 0
        for beam in self.beams_found:
            if str(beam.get('type') or '').lower() != 'viga':
                continue
            beam['_tipo_comp'] = tipo  # chave raiz — lida por _add_rich_segment_pack
            updated_count += 1
            if self.current_project_id:
                try:
                    self.db.save_beam(beam, self.current_project_id)
                except Exception as e:
                    self.log(f"⚠️ Erro ao salvar viga {beam.get('name', 'N/A')}: {e}")

        # Recriar o card LV aberto com o novo tipo, se houver
        if self.current_card:
            card_type = str(self.current_card.item_data.get('type') or '').lower()
            if any(x in card_type for x in ('lateral_a', 'lateral_b')):
                beam_id = self.current_card.item_data.get('id')
                beam = next((bm for bm in self.beams_found if bm['id'] == beam_id), None)
                if beam:
                    self.show_detail(beam, override_type=card_type, tipo_comp=tipo)

        self.log(f"✅ {updated_count} vigas atualizadas para modo '{tipo}'")
    


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
        
        # Refresh training list to show updated state (if needed)
        if hasattr(self, 'tab_training'):
            self.tab_training.refresh_list()

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

    def _get_scripts_dir(self):
        """Retorna o diretório onde os scripts devem ser salvos (SCRIPTS_ROBOS)."""
        import sys
        from pathlib import Path

        # Sempre usar SCRIPTS_ROBOS na raiz do projeto
        if getattr(sys, 'frozen', False):
            # Modo compilado - usar diretório do executável
            base_dir = Path(sys.executable).parent
        else:
            # Modo desenvolvimento - usar raiz do projeto
            base_dir = Path(__file__).parent

        scripts_dir = base_dir / "SCRIPTS_ROBOS"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        return scripts_dir

    def _get_lisp_dir(self):
        """Retorna o diretório onde os comandos LISP devem ser salvos."""
        import sys
        from pathlib import Path

        # Sempre usar ferramentas_LOAD_LISP na raiz do projeto
        if getattr(sys, 'frozen', False):
            # Modo compilado - usar diretório do executável
            base_dir = Path(sys.executable).parent
        else:
            # Modo desenvolvimento - usar raiz do projeto
            base_dir = Path(__file__).parent

        lisp_dir = base_dir / "ferramentas_LOAD_LISP"
        lisp_dir.mkdir(parents=True, exist_ok=True)
        return lisp_dir

    def _create_laz_command_files(self, script_content=None):
        """Cria os arquivos comando_LAZ.lsp e script_LAZ.scr."""
        try:
            lisp_dir = self._get_lisp_dir()
            scripts_dir = self._get_scripts_dir()

            # Caminho absoluto para o AutoCAD usar
            scripts_absoluto = str(scripts_dir.as_posix())

            # Criar arquivo comando_LAZ.lsp
            comando_laz_path = lisp_dir / "comando_LAZ.lsp"
            with open(comando_laz_path, 'w', encoding='utf-8') as f:
                f.write('\ufeff')  # BOM UTF-8
                f.write(";; Comando para executar script SCR LAZ\n")
                f.write("(defun c:LAZ ()\n")
                f.write("  (setvar \"filedia\" 0)\n")
                f.write(f'  (command "_SCRIPT" "{scripts_absoluto}/script_LAZ.scr")\n')
                f.write("  (setvar \"filedia\" 1)\n")
                f.write("  (princ)\n")
                f.write(")\n")

            # Criar arquivo script_LAZ.scr
            script_laz_path = scripts_dir / "script_LAZ.scr"
            if script_content:
                with open(script_laz_path, 'w', encoding='utf-16-le') as f:
                    f.write('\ufeff')  # BOM UTF-16 LE
                    f.write(script_content)
            else:
                # Criar arquivo vazio se não houver conteúdo
                with open(script_laz_path, 'w', encoding='utf-16-le') as f:
                    f.write('\ufeff')  # BOM UTF-16 LE

            self.log(f"✅ Arquivos LAZ criados: {comando_laz_path}, {script_laz_path}")
            return True

        except Exception as e:
            self.log(f"❌ Erro ao criar arquivos LAZ: {e}")
            return False

    def generate_script_pillar_full(self, is_library):
        """Gera script completo para todos os pilares da obra."""
        self.log(f"📜 Gerando Script Pilar Completo (Lib={is_library})")

        # Verificar se Robo Pilares está disponível
        if not hasattr(self, 'robo_pilares') or not self.robo_pilares:
            QMessageBox.warning(self, "Erro", "Módulo Robo Pilares não está carregado.")
            return

        try:
            # Obter contexto da obra
            obra_nome = self.cmb_works.currentText()
            if not obra_nome:
                QMessageBox.warning(self, "Aviso", "Selecione uma obra na barra superior.")
                return
            
            print("\n" + ("=" * 100))
            print("[DEBUG-ULTRA-MAIN] ===== INÍCIO generate_script_pillar_full() =====")
            print(f"[DEBUG-ULTRA-MAIN] obra_nome_ui = {obra_nome!r}")
            print(f"[DEBUG-ULTRA-MAIN] scripts_dir_app = {self._get_scripts_dir()}")
            print(f"[DEBUG-ULTRA-MAIN] robo_pilares_loaded = {bool(getattr(self, 'robo_pilares', None))}")
            print(("=" * 100))

            # Usar o automation service do Robo Pilares
            if hasattr(self.robo_pilares, 'vm') and hasattr(self.robo_pilares.vm, 'automation_service'):
                service = self.robo_pilares.vm.automation_service
                print(f"[DEBUG-ULTRA-MAIN] automation_service = {service} (type={type(service)})")

                # Coletar todos os pavimentos da obra atual
                obra_model = None
                for obra in self.robo_pilares.vm.obras:
                    if obra.nome == obra_nome:
                        obra_model = obra
                        break

                if not obra_model or not obra_model.pavimentos:
                    QMessageBox.warning(self, "Aviso", f"Nenhum pavimento encontrado na obra '{obra_nome}'.")
                    return
                
                print(f"[DEBUG-ULTRA-MAIN] obra_model.nome = {getattr(obra_model, 'nome', None)!r}")
                print(f"[DEBUG-ULTRA-MAIN] obra_model.pavimentos = {len(getattr(obra_model, 'pavimentos', []) or [])}")

                generated_scripts = []
                for pavimento in obra_model.pavimentos:
                    if pavimento.pilares:
                        print("\n" + ("-" * 100))
                        print("[DEBUG-ULTRA-MAIN] Chamando generate_full_paviment_orchestration()")
                        print(f"[DEBUG-ULTRA-MAIN] pavimento.nome = {getattr(pavimento, 'nome', None)!r}")
                        print(f"[DEBUG-ULTRA-MAIN] pavimento.pilares_count = {len(getattr(pavimento, 'pilares', []) or [])}")
                        print("-" * 100)
                        result = service.generate_full_paviment_orchestration(pavimento, obra_model)
                        print(f"[DEBUG-ULTRA-MAIN] retorno_orquestracao = {result!r}")
                        if result:
                            generated_scripts.append(f"Pavimento {pavimento.nome}: {result}")

                if generated_scripts:
                    self._create_laz_command_files()
                    QMessageBox.information(self, "Sucesso",
                        f"Scripts gerados para obra '{obra_nome}':\n\n" +
                        "\n".join(generated_scripts) +
                        f"\n\nArquivos salvos em: {self._get_scripts_dir()}")
                else:
                    QMessageBox.information(self, "Aviso", "Nenhum script foi gerado.")
                
                print("\n" + ("=" * 100))
                print("[DEBUG-ULTRA-MAIN] ===== FIM generate_script_pillar_full() =====")
                print(("=" * 100) + "\n")
            else:
                QMessageBox.warning(self, "Erro", "Serviço de automação não disponível no Robo Pilares.")

        except Exception as e:
            self.log(f"❌ Erro ao gerar script completo: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao gerar script: {str(e)}")

    def generate_script_pavement_pillar(self, is_library):
        """Gera script para pilares do pavimento atual."""
        self.log(f"📜 Gerando Script Pavimento Pilar (Lib={is_library})")

        # Verificar se Robo Pilares está disponível
        if not hasattr(self, 'robo_pilares') or not self.robo_pilares:
            QMessageBox.warning(self, "Erro", "Módulo Robo Pilares não está carregado.")
            return

        try:
            # Obter contexto
            obra_nome = self.cmb_works.currentText()
            pavimento_nome = self._current_pavement_name()

            if not obra_nome or not pavimento_nome:
                QMessageBox.warning(self, "Aviso", "Selecione obra e pavimento na barra superior.")
                return
            
            print("\n" + ("=" * 100))
            print("[DEBUG-ULTRA-MAIN] ===== INÍCIO generate_script_pavement_pillar() =====")
            print(f"[DEBUG-ULTRA-MAIN] obra_nome_ui = {obra_nome!r}")
            print(f"[DEBUG-ULTRA-MAIN] pavimento_nome_ui = {pavimento_nome!r}")
            print(f"[DEBUG-ULTRA-MAIN] scripts_dir_app = {self._get_scripts_dir()}")
            print(("=" * 100))

            # Usar o automation service do Robo Pilares
            if hasattr(self.robo_pilares, 'vm') and hasattr(self.robo_pilares.vm, 'automation_service'):
                service = self.robo_pilares.vm.automation_service
                print(f"[DEBUG-ULTRA-MAIN] automation_service = {service} (type={type(service)})")

                # Encontrar o pavimento atual
                current_pavimento = self.robo_pilares.vm.current_pavimento
                if not current_pavimento:
                    QMessageBox.warning(self, "Aviso", "Nenhum pavimento selecionado no Robo Pilares.")
                    return
                
                print(f"[DEBUG-ULTRA-MAIN] current_pavimento.nome = {getattr(current_pavimento, 'nome', None)!r}")
                print(f"[DEBUG-ULTRA-MAIN] current_pavimento.pilares_count = {len(getattr(current_pavimento, 'pilares', []) or [])}")

                # Encontrar a obra
                obra_model = None
                for obra in self.robo_pilares.vm.obras:
                    if obra.nome == obra_nome:
                        obra_model = obra
                        break

                if not obra_model:
                    QMessageBox.warning(self, "Aviso", f"Obra '{obra_nome}' não encontrada.")
                    return
                
                print(f"[DEBUG-ULTRA-MAIN] obra_model.nome = {getattr(obra_model, 'nome', None)!r}")

                # Gerar script para o pavimento
                print("[DEBUG-ULTRA-MAIN] Chamando generate_full_paviment_orchestration() para o pavimento atual...")
                result = service.generate_full_paviment_orchestration(current_pavimento, obra_model)
                print(f"[DEBUG-ULTRA-MAIN] retorno_orquestracao = {result!r}")

                if result:
                    self._create_laz_command_files()
                    QMessageBox.information(self, "Sucesso",
                        f"Script gerado para pavimento '{pavimento_nome}':\n\n{result}\n\n"
                        f"Arquivos salvos em: {self._get_scripts_dir()}")
                else:
                    QMessageBox.information(self, "Aviso", "Nenhum script foi gerado.")
                
                print("\n" + ("=" * 100))
                print("[DEBUG-ULTRA-MAIN] ===== FIM generate_script_pavement_pillar() =====")
                print(("=" * 100) + "\n")
            else:
                QMessageBox.warning(self, "Erro", "Serviço de automação não disponível no Robo Pilares.")

        except Exception as e:
            self.log(f"❌ Erro ao gerar script do pavimento: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao gerar script: {str(e)}")

    def generate_script_beam_set(self, is_library):
        """Gera script completo para todas as vigas da obra."""
        self.log(f"📜 Gerando Script Conjunto de Viga Completo (Lib={is_library})")

        # Verificar se Robo Laterais está disponível
        if not hasattr(self, 'robo_viga') or not self.robo_viga:
            QMessageBox.warning(self, "Erro", "Módulo Robo Laterais de Viga não está carregado.")
            return

        try:
            # Obter contexto da obra
            obra_nome = self.cmb_works.currentText()
            if not obra_nome:
                QMessageBox.warning(self, "Aviso", "Selecione uma obra na barra superior.")
                return

            # Usar o método generate_conjunto_scripts do Robo de Vigas
            if hasattr(self.robo_viga, 'generate_conjunto_scripts'):
                self.robo_viga.generate_conjunto_scripts()
                self._create_laz_command_files()
                QMessageBox.information(self, "Sucesso",
                    f"Script completo gerado para obra '{obra_nome}'.\n\n"
                    f"Arquivos salvos em: {self._get_scripts_dir()}")
            else:
                QMessageBox.warning(self, "Erro", "Método de geração de conjunto não disponível no Robo Laterais de Viga.")

        except Exception as e:
            self.log(f"❌ Erro ao gerar script de vigas: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao gerar script: {str(e)}")

    def generate_script_pavement_beam(self, is_library):
        """Gera script para vigas do pavimento atual."""
        self.log(f"📜 Gerando Script Pavimento Vigas (Lib={is_library})")

        # Verificar se Robo Laterais está disponível
        if not hasattr(self, 'robo_viga') or not self.robo_viga:
            QMessageBox.warning(self, "Erro", "Módulo Robo Laterais de Viga não está carregado.")
            return

        try:
            # Obter contexto
            obra_nome = self.cmb_works.currentText()
            pavimento_nome = self._current_pavement_name()

            if not obra_nome or not pavimento_nome:
                QMessageBox.warning(self, "Aviso", "Selecione obra e pavimento na barra superior.")
                return

            # Sincronizar obra e pavimento no Robo de Vigas
            if hasattr(self.robo_viga, 'add_global_pavimento'):
                self.robo_viga.add_global_pavimento(obra_nome, pavimento_nome)

            # Usar o método generate_pavimento_scripts do Robo de Vigas
            if hasattr(self.robo_viga, 'generate_pavimento_scripts'):
                self.robo_viga.generate_pavimento_scripts()
                self._create_laz_command_files()
                QMessageBox.information(self, "Sucesso",
                    f"Script gerado para pavimento '{pavimento_nome}'.\n\n"
                    f"Arquivos salvos em: {self._get_scripts_dir()}")
            else:
                QMessageBox.warning(self, "Erro", "Método de geração de pavimento não disponível no Robo Laterais de Viga.")

        except Exception as e:
            self.log(f"❌ Erro ao gerar script do pavimento: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao gerar script: {str(e)}")

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
    # Hook global de exceções: impede que exceções Python não tratadas em slots Qt
    # fechem o processo silenciosamente. Registra no crash_log.txt e continua.
    import traceback as _tb, datetime as _dt
    def _excepthook(exc_type, exc_val, exc_tb):
        msg = ''.join(_tb.format_exception(exc_type, exc_val, exc_tb))
        ts  = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with open('crash_log.txt', 'a', encoding='utf-8') as _f:
                _f.write(f'\n[{ts}] UNHANDLED EXCEPTION:\n{msg}\n')
        except Exception:
            pass
        print(f'[EXCEPTION] {msg}', file=sys.stderr)
        # NÃO chamar sys.exit() — app continua rodando
    sys.excepthook = _excepthook

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # ── Watchdog de freeze (TEMPORÁRIO — diagnóstico de travamento) ────────────
    # A GUI thread pulsa _wd_beat a cada 500ms via QTimer. Uma thread daemon
    # verifica: se a GUI ficar >4s sem pulsar (== congelada), despeja o stack de
    # TODAS as threads em freeze_dump.log. Captura o ponto exato do freeze.
    try:
        import threading as _wd_threading
        import time as _wd_time
        import faulthandler as _wd_fault
        from PySide6.QtCore import QTimer as _WDTimer

        _wd_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'freeze_dump.log')
        _wd_state = {'last': _wd_time.time(), 'dumped': False}

        def _wd_pulse():
            _wd_state['last'] = _wd_time.time()
            _wd_state['dumped'] = False

        _wd_timer = _WDTimer()
        _wd_timer.timeout.connect(_wd_pulse)
        _wd_timer.start(500)
        app._wd_timer = _wd_timer  # impede GC do timer

        def _wd_monitor():
            while True:
                _wd_time.sleep(1.0)
                gap = _wd_time.time() - _wd_state['last']
                if gap > 4.0 and not _wd_state['dumped']:
                    _wd_state['dumped'] = True
                    try:
                        with open(_wd_log_path, 'a', encoding='utf-8') as _f:
                            _f.write(
                                f"\n===== FREEZE DETECTADO (GUI parada ha {gap:.1f}s) "
                                f"@ {_wd_time.strftime('%Y-%m-%d %H:%M:%S')} =====\n"
                            )
                            _wd_fault.dump_traceback(file=_f, all_threads=True)
                            _f.flush()
                        print(f"[WATCHDOG] FREEZE detectado ({gap:.1f}s) -> freeze_dump.log",
                              file=sys.stderr, flush=True)
                    except Exception:
                        pass

        _wd_thr = _wd_threading.Thread(target=_wd_monitor, daemon=True, name='freeze-watchdog')
        _wd_thr.start()
    except Exception as _wd_e:
        print(f"[WATCHDOG] nao instalado: {_wd_e}", file=sys.stderr)
    # ───────────────────────────────────────────────────────────────────────────

    # Suprimir warnings cosmÃ©ticos de QSS parse
    from PySide6.QtCore import qInstallMessageHandler, QtMsgType
    def _qss_msg_handler(msg_type, ctx, msg):
        if msg_type == QtMsgType.QtWarningMsg and 'stylesheet' in msg.lower():
            return
        if msg_type == QtMsgType.QtWarningMsg and 'parse' in msg.lower():
            return
        # Demais mensagens: comportamento padrÃ£o
        from PySide6.QtCore import QtMsgType as _t
        if msg_type == _t.QtCriticalMsg:
            print(f'[Qt Critical] {msg}', file=sys.stderr)
        elif msg_type == _t.QtFatalMsg:
            print(f'[Qt Fatal] {msg}', file=sys.stderr)
    qInstallMessageHandler(_qss_msg_handler)
    
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
        # Forçar geometria na tela primária antes de maximizar
        screen = app.primaryScreen().availableGeometry()
        window.setGeometry(screen.x() + 50, screen.y() + 50,
                           min(1600, screen.width() - 100),
                           min(1000, screen.height() - 100))
        window.showMaximized()
        window.raise_()
        window.activateWindow()
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

    # BYPASS LOGIN
    from src.core.auth.models import UserProfile, UserRole
    from datetime import datetime
    
    # Instancia de forma válida para o Pydantic
    dummy_user = UserProfile(
        id="local_admin_123",
        email="local.admin@pyside.cad",
        full_name="Local Admin",
        role=UserRole.ADMIN,
        credits=999,
        created_at=datetime.now()
    )
    
    start_app(dummy_user)
        
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
