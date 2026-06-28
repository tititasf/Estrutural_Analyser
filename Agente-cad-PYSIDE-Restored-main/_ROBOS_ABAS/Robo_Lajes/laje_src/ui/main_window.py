import sys
import os
import json
import re
from pathlib import Path

LAJES_DEBUG = os.environ.get('LAJES_DEBUG', '0') == '1'

from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                               QMenuBar, QMenu, QMessageBox, QGroupBox, 
                               QStatusBar, QLabel, QPushButton)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from .widgets.laje_tab import LajeTab, _fmt_pav_label, _set_pav_cmb, _pav_cmb_raw
from .widgets.canvas_widget import CanvasWidget
# from .widgets.linhas_config import LinhasConfigWidget  # Removido - agora usa overlays no canvas
from .widgets.pavimentos_widget import PavimentosWidget
# CalculosModosWidget já está no canvas_widget
from .widgets.obra_control_widget import ObraControlWidget
from laje_src.services.file_manager import save_obra, load_obra, save_all_obras, load_all_obras, clear_all_data
from laje_src.services.calculo_modo1 import calcular_modo1, calcular_modo2
from .widgets.ai_feedback_widget import AIFeedbackWidget
from laje_src.models.obra import Obra
from typing import List
from .styles import DS


def _natural_laje_name_key(name: str):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(name or ""))]

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.obra_atual: Obra = None
        self.todas_obras: List[Obra] = []
        self._user_email = ""
        self._user_name = ""
        self._user_credits = 0.0
        self._updating_obra = False  # Flag para evitar loops infinitos
        self._auto_select_initial_obra = False
        self.init_ui()
        self.apply_standalone_style()  # Apply scoped style for integration
        self.setup_status_bar()
        self.setup_connections()
        # Carregar obras após UI estar completamente pronta
        self._obras_loaded = False
        
        # Timer para atualizar créditos periodicamente (desabilitado durante startup)
        self.credits_timer = QTimer(self)
        self.credits_timer.timeout.connect(self.refresh_credits)
        # Iniciar timer após um delay maior para não interferir no startup
        QTimer.singleShot(5000, lambda: self.credits_timer.start(60000))  # Atualizar a cada 60 segundos após 5s
    
    def apply_standalone_style(self):
        """Applies a scoped stylesheet to force a Fusion-like Dark Theme."""
        self.setObjectName("LajeMainWindowFull")
        
        style = """
        /* Force standard font */
        QWidget#LajeMainWindowFull, QWidget#LajeMainWindowFull * {
            font-family: 'Segoe UI', sans-serif;
            color: {DS.TEXT};
        }
        
        QWidget#LajeMainWindowFull {
            background-color: {DS.CARD};
        }

        /* Buttons */
        QWidget#LajeMainWindowFull QPushButton {
            border: 1px solid {DS.BORDER_STR};
            background-color: {DS.ELEVATED};
            color: {DS.TEXT};
            padding: 5px 12px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: normal;
            min-width: 50px;
        }
        QWidget#LajeMainWindowFull QPushButton:hover {
            background-color: {DS.BORDER_STR};
            border-color: {DS.SECONDARY};
        }
        QWidget#LajeMainWindowFull QPushButton:pressed {
            background-color: {DS.DEEP};
        }
        QWidget#LajeMainWindowFull QPushButton:disabled {
            background-color: {DS.CARD};
            color: {DS.MUTED};
            border-color: {DS.BORDER};
        }
        
        QWidget#LajeMainWindowFull QPushButton[text*="Salvar"], 
        QWidget#LajeMainWindowFull QPushButton[text*="Adicionar"] {
             background-color: {DS.INTERACTIVE};
             border: 1px solid {DS.INTERACTIVE};
             color: white;
             font-weight: bold;
        }

        QWidget#LajeMainWindowFull QPushButton[text="EXCLUIR"] {
             background-color: {DS.DANGER};
             border: 1px solid {DS.DANGER};
             color: white;
             font-weight: bold;
        }

        /* Inputs */
        QWidget#LajeMainWindowFull QLineEdit {
            background-color: {DS.DEEP};
            border: 1px solid {DS.BORDER_STR};
            color: {DS.TEXT};
            padding: 4px;
            border-radius: 2px;
        }
        
        /* ComboBox */
        QWidget#LajeMainWindowFull QComboBox {
            background-color: {DS.ELEVATED};
            border: 1px solid {DS.BORDER_STR};
            padding: 4px;
            border-radius: 2px;
        }

        /* GroupBox */
        QWidget#LajeMainWindowFull QGroupBox {
            border: 1px solid {DS.BORDER_STR};
            border-radius: 4px;
            margin-top: 1.2em;
        }
        
        /* Tree Widget */
        QWidget#LajeMainWindowFull QTreeWidget {
            background-color: {DS.DEEP};
            border: 1px solid {DS.BORDER_STR};
            color: {DS.TEXT};
        }
        QWidget#LajeMainWindowFull QHeaderView::section {
            background-color: {DS.BORDER};
            color: {DS.TEXT};
            padding: 4px;
            border: 1px solid {DS.BORDER_STR};
        }
        """
        self.setStyleSheet(style)

    def init_ui(self):
        self.setWindowTitle("Gerenciador de Lajes")
        self.setGeometry(100, 100, 1600, 900)
        
        # Menu Bar
        self.create_menu_bar()
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal horizontal (3 colunas)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(4, 4, 4, 4)
        
        # Instanciar LajeTab cedo pois é usada
        self.laje_tab = LajeTab()
        self.ai_feedback = AIFeedbackWidget()

        # COLUNA ESQUERDA (Controle e Listas - Antiga Direita)
        left_column = QWidget()
        left_column.setMaximumWidth(350)  
        left_layout = QVBoxLayout(left_column)
        left_layout.setSpacing(3)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Controle de Obra (no topo)
        self.obra_control = ObraControlWidget()
        left_layout.addWidget(self.obra_control)
        
        # Listagem de pavimentos
        self.pavimentos_widget = PavimentosWidget()
        left_layout.addWidget(self.pavimentos_widget, stretch=1)
        
        # Lista de Lajes
        lajes_group = QGroupBox("Lista de Lajes")
        lajes_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid {DS.BASE};
                border-radius: 6px;
                margin-top: 12px;
                background-color: {DS.DEEP};
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                background-color: {DS.ELEVATED};
                color: {DS.WHITE};
                padding: 2px 8px;
                border-radius: 3px;
                font-weight: 700;
                font-size: 9px;
                text-transform: uppercase;
                
                margin-left: 8px;
            }
        """)
        lajes_group_layout = QVBoxLayout()
        lajes_group_layout.setContentsMargins(6, 6, 6, 6)
        lajes_group_layout.setSpacing(4)
        
        # Botões ACIMA da lista
        # Tabela de lajes (do LajeTab)
        lajes_group_layout.addWidget(self.laje_tab.tree_widget, stretch=1)
        
        # Botões ABAIXO da lista
        lajes_buttons_layout = QHBoxLayout()
        lajes_buttons_layout.setSpacing(4)
        lajes_buttons_layout.addWidget(self.laje_tab.salvar_btn)
        lajes_buttons_layout.addWidget(self.laje_tab.delete_btn)
        lajes_group_layout.addLayout(lajes_buttons_layout)
        
        lajes_group.setLayout(lajes_group_layout)
        left_layout.addWidget(lajes_group, stretch=1)
        
        # COLUNA CENTRO: Canvas (Canvas ocupando todo o espaço central)
        center_column = QWidget()
        center_layout = QVBoxLayout(center_column)
        center_layout.setSpacing(0)
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        # Canvas ocupando todo o espaço
        self.canvas_widget = CanvasWidget()
        center_layout.addWidget(self.canvas_widget, stretch=1)

        
        # COLUNA DIREITA (Dados da Laje - Antiga Esquerda)
        right_column = QWidget()
        right_column.setMinimumWidth(300)
        right_column.setMaximumWidth(360)
        right_layout = QVBoxLayout(right_column)
        right_layout.setSpacing(5)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Campos de laje
        right_layout.addWidget(self.laje_tab, stretch=1)
        
        # Widget de Feedback IA
        right_layout.addWidget(self.ai_feedback)

        # Passar referência do canvas_widget para laje_tab (para acessar overlays)
        self.laje_tab.canvas_widget = self.canvas_widget
        
        # Adicionar colunas ao layout principal
        # Coluna esquerda reduzida em 60%: usar largura máxima fixa
        main_layout.addWidget(left_column, stretch=0)  # Largura fixa máxima 300px
        main_layout.addWidget(center_column, stretch=1)  # Canvas + Resumo dos Painéis
        main_layout.addWidget(right_column, stretch=0)  # Largura fixa máxima 350px
    
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # Menu Arquivo
        file_menu = menubar.addMenu("Arquivo")
        
        save_action = file_menu.addAction("Salvar Obra")
        save_action.triggered.connect(self.salvar_obra)
        
        load_action = file_menu.addAction("Importar Obra")
        load_action.triggered.connect(self.importar_obra)
        
        file_menu.addSeparator()
        
        clear_data_action = file_menu.addAction("Limpar Todos os Dados")
        clear_data_action.triggered.connect(self.limpar_todos_dados)
        
        file_menu.addSeparator()
        
        logout_action = file_menu.addAction("Logout")
        logout_action.triggered.connect(self.do_logout)
        
        # Menu Ajuda
        help_menu = menubar.addMenu("Ajuda")
        about_action = help_menu.addAction("Sobre")
        about_action.triggered.connect(self.show_about)
    
    def setup_status_bar(self):
        """Configura barra de status com informações do usuário e créditos"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Widget para informações do usuário
        self.user_label = QLabel("👤 -")
        self.user_label.setStyleSheet(f"color: {DS.SECONDARY}; padding: 0 10px;")
        
        # Widget para créditos
        self.credits_label = QLabel("💳 - m²")
        self.credits_label.setStyleSheet("""
            color: {DS.SUCCESS};
            font-weight: bold;
            padding: 0 15px;
            background-color: rgba(40, 167, 69, int(1/100*255));
            border-radius: 4px;
        """)
        
        # Botão de atualizar créditos
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(24, 24)
        self.refresh_btn.setToolTip("Atualizar créditos")
        self.refresh_btn.clicked.connect(self.refresh_credits)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, int(1/100*255));
                border-radius: 4px;
            }
        """)

        # Widget para Status de Conexão
        self.connection_label = QLabel("🌐 ONLINE")
        self.connection_label.setStyleSheet("""
            color: {DS.SUCCESS}; 
            font-weight: bold; 
            padding: 0 10px;
            border-right: 1px solid {DS.BASE};
        """)
        
        # Adicionar widgets à barra de status
        self.status_bar.addWidget(self.connection_label)
        self.status_bar.addPermanentWidget(self.user_label)
        self.status_bar.addPermanentWidget(self.credits_label)
        self.status_bar.addPermanentWidget(self.refresh_btn)
        
        # Timer para atualizar status de conexão periodicamente
        from PySide6.QtCore import QTimer
        self.connection_timer = QTimer(self)
        self.connection_timer.timeout.connect(self.update_connection_status)
        self.connection_timer.start(30000)  # Verificar a cada 30 segundos
        self.update_connection_status() # Atualização imediata
        
        # Estilo da barra de status
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: {DS.DEEP};
                border-top: 1px solid {DS.BASE};
            }
        """)
    
    def setup_connections(self):
        # Conectar sinais entre widgets
        self.laje_tab.laje_selecionada.connect(lambda laje, aplicar: self.on_laje_selecionada(laje, aplicar))
        self.laje_tab.obra_changed.connect(self.on_obra_changed)
        # Conectar sinal para salvar sem recálculos
        self.laje_tab.save_requested.connect(self.on_save_requested)
        # Linhas agora são gerenciadas pelos overlays do canvas
        # self.linhas_config.linhas_changed.connect(self.on_linhas_changed)
        # Conectar sinal de edição de linhas do canvas para atualizar campos e salvar
        self.canvas_widget.linhas_edited.connect(self.on_linhas_edited_from_canvas)
        self.pavimentos_widget.pavimento_selected.connect(self.on_pavimento_selected)
        self.pavimentos_widget.obra_changed.connect(self.on_obra_changed)
        self.pavimentos_widget.pavimento_adicionado.connect(self.on_pavimento_adicionado)
        self.pavimentos_widget.pavimento_removido.connect(self.on_pavimento_removido)
        # calculos_modos agora está no canvas_widget - conexão já feita lá
        # Conectar controle de obra
        self.obra_control.obra_changed.connect(self.on_obra_control_changed)
        # Conectar sinal de reaproveitamento do pavimentos_widget
        self.pavimentos_widget.reaproveitamento_aplicado.connect(self.on_reaproveitamento_aplicado)
        # Nota: checkboxes de reaproveitamento já estão conectados via salvar_preferencias_desenho em laje_tab
        
        # Conectar sinal de treinamento
        self.canvas_widget.training_example_created.connect(self.handle_training_example)
        self.laje_tab.lajes_deleted.connect(self.handle_lajes_deleted)
        
        # Conectar IA Feedback
        self.canvas_widget.ai_feedback_requested.connect(self.ai_feedback.show_request)
        self.canvas_widget.ai_status_message.connect(self.ai_feedback.set_status)
        self.ai_feedback.action_submitted.connect(self.canvas_widget.on_ai_feedback_response)
        self.canvas_widget.ai_feedback_finalize_requested.connect(self.ai_feedback.submit_comment)
    
    def sync_context(self, work_name, pavement_name, project_id=None):
        """
        Sincroniza o Robô Laje com o contexto da aplicação master (Structural Analyzer).
        Implementa isolamento por projeto e seleção automática.
        """
        if not work_name: return
        
        # 1. Isolar dados se project_id foi informado
        from laje_src.utils.path_helper import PathHelper
        project_changed = False
        if project_id and str(PathHelper.TARGET_PROJECT_ID) != str(project_id):
            print(f"[ROBO LAJE] Mudando contexto de dados para Projeto: {project_id}")
            # [CRÍTICO] Salvar obras atuais antes de mudar de projeto
            if hasattr(self, 'todas_obras') and self.todas_obras:
                print(f"[ROBO LAJE] Salvando {len(self.todas_obras)} obras antes de mudar de projeto")
                self.save_all_obras_auto()
            
            PathHelper.TARGET_PROJECT_ID = project_id
            project_changed = True
            
            # Recarregar Obras do novo diretório (isolado)
            # Usar QTimer para garantir que o salvamento anterior foi concluído
            from PySide6.QtCore import QTimer
            def recarregar_apos_salvar():
                self.load_obras_on_startup(callback=lambda: self._sync_obra_e_pavimento(work_name, pavement_name))
                # Após recarregar, selecionar ou criar obra
            QTimer.singleShot(200, recarregar_apos_salvar)
        else:
            if not self._obras_loaded:
                self.load_obras_on_startup(callback=lambda: self._sync_obra_e_pavimento(work_name, pavement_name))
                return
            # Se não mudou projeto, apenas sincronizar obra e pavimento
            self._sync_obra_e_pavimento(work_name, pavement_name)
    
    def _sync_obra_e_pavimento(self, work_name, pavement_name):
        """Helper para sincronizar obra e pavimento após carregamento"""
        # 2. Selecionar ou criar Obra
        # O add_obra_external já seleciona se existir
        self.obra_control.add_obra_external(work_name)
        
        # 3. Selecionar ou criar Pavimento
        if pavement_name:
            self.pavimentos_widget.select_or_create_pavimento(pavement_name)

    def load_obras_on_startup(self, callback=None):
        """Carrega todas as obras salvas ao iniciar a aplicação (com proteções)"""
        # Flag para evitar múltiplas execuções
        if hasattr(self, '_loading_obras'):
            return
        self._loading_obras = True
        
        try:
# print("[DEBUG] Carregando obras no startup...")
            sys.stdout.flush()
            
            # Usar QTimer para fazer carregamento assíncrono e não travar UI
            def carregar_obras():
                try:
                    # Limpar flag quando terminar
                    if hasattr(self, '_loading_obras'):
                        delattr(self, '_loading_obras')
                    
                    # [CRÍTICO] Preservar obras do combo que podem ter sido criadas dinamicamente
                    obras_do_combo = {}
                    combo_count = self.obra_control.obra_combo.count()
                    if LAJES_DEBUG:
                        print(f"[LOAD DEBUG] 🔍 Verificando combo box: {combo_count} itens no combo")
                    for i in range(combo_count):
                        obra = self.obra_control.obra_combo.itemData(i)
                        if obra and obra.nome:
                            obras_do_combo[obra.nome] = obra
                            if LAJES_DEBUG:
                                print(f"[LOAD DEBUG] 📦 Obra no combo: '{obra.nome}'")
                    if LAJES_DEBUG:
                        print(f"[LOAD DEBUG] 📦 Total de obras no combo: {len(obras_do_combo)}")
                    
                    # Carregar obras do arquivo
                    if LAJES_DEBUG:
                        print(f"[LOAD DEBUG] 🔄 Iniciando carregamento de obras do arquivo...")
                    obras_carregadas = load_all_obras()
                    print(f"[LOAD] {len(obras_carregadas)} obras carregadas do arquivo")
                    if LAJES_DEBUG:
                        print(f"[LOAD DEBUG] 📋 Obras carregadas: {[obra.nome for obra in obras_carregadas]}")
                    sys.stdout.flush()
                    
                    # [CRÍTICO] Mesclar obras carregadas com obras do combo (preservar obras criadas dinamicamente)
                    obras_mescladas = {}
                    
                    # Primeiro, adicionar obras carregadas do arquivo
                    for obra in obras_carregadas:
                        if obra and obra.nome:
                            obras_mescladas[obra.nome] = obra
                    
                    # Depois, adicionar obras do combo que não estão no arquivo (obras criadas dinamicamente)
                    for nome, obra in obras_do_combo.items():
                        if nome not in obras_mescladas:
                            print(f"[LOAD] Preservando obra criada dinamicamente '{nome}' que não está no arquivo")
                            obras_mescladas[nome] = obra
                    
                    # Converter para lista
                    self.todas_obras = list(obras_mescladas.values())
                    print(f"[LOAD] Total de obras após mesclagem: {len(self.todas_obras)}")
                    if LAJES_DEBUG:
                        print(f"[LOAD DEBUG] 📊 Resumo da mesclagem:")
                        print(f"[LOAD DEBUG]   - Obras do arquivo: {len(obras_carregadas)}")
                        print(f"[LOAD DEBUG]   - Obras do combo: {len(obras_do_combo)}")
                        print(f"[LOAD DEBUG]   - Obras após mesclagem: {len(self.todas_obras)}")

                    # [DEBUG] Verificar se pavimentos foram carregados corretamente
                    if LAJES_DEBUG:
                        for obra in self.todas_obras:
                            print(f"[LOAD DEBUG] Obra '{obra.nome}': {len(obra.pavimentos)} pavimentos")
                            for pav in obra.pavimentos:
                                print(f"[LOAD DEBUG]   - Pavimento '{pav.nome}': {len(pav.lajes)} lajes")
                    
                    if not self.todas_obras:
                        return  # Não fazer nada se não houver obras
                    
                    # Desabilitar sinais temporariamente para evitar loops
                    self.obra_control.obra_combo.blockSignals(True)
                    
                    try:
                        # Limpar combo e adicionar todas as obras mescladas
                        self.obra_control.obra_combo.clear()
                        
                        # Adicionar obras ao combo do controle de obra
                        for obra in self.todas_obras:
                            try:
                                if obra and obra.nome:
                                    self.obra_control.obra_combo.addItem(obra.nome, obra)
                            except Exception as e:
# print(f"[WARNING] Erro ao adicionar obra: {str(e)}")
                                continue
                        
                        # Selecionar primeira obra se existir
                        if self._auto_select_initial_obra and self.todas_obras and self.obra_control.obra_combo.count() > 0:
                            try:
                                # Desabilitar atualizações automáticas durante inicialização
                                self._updating_obra = True
                                
                                self.obra_control.obra_combo.setCurrentIndex(0)
                                self.obra_atual = self.todas_obras[0]
                                self.obra_control.obra_atual = self.obra_atual
                                self.laje_tab.obra_atual = self.obra_atual
                                self.pavimentos_widget.set_obra(self.obra_atual)
                                # Atualizar obra no canvas
                                self.canvas_widget.set_obra(self.obra_atual)
                                # Aplicar opções de desenho iniciais
                                self.laje_tab.atualizar_visualizacao_canvas()
                                
                                # Reabilitar após um pequeno delay
                                QTimer.singleShot(1000, lambda: setattr(self, '_updating_obra', False))
                                
                                # [DEBUG] Verificar estado final das lajes após carregamento completo
                                if LAJES_DEBUG:
                                    print(f"[LOAD DEBUG] 🔍 Verificação final após carregamento completo:")
                                    for obra in self.todas_obras:
                                        print(f"[LOAD DEBUG]   📋 Obra '{obra.nome}': {len(obra.pavimentos)} pavimentos")
                                        for pav in obra.pavimentos:
                                            print(f"[LOAD DEBUG]     📦 Pavimento '{pav.nome}': {len(pav.lajes)} lajes")
                                            for laje in pav.lajes:
                                                print(f"[LOAD DEBUG]       🏗️ Laje Nº{laje.numero} - '{laje.nome}' ({len(laje.coordenadas)} coordenadas)")
                            except Exception as e:
                                print(f"[ERROR] Erro ao configurar obra inicial: {str(e)}")
                                import traceback
                                traceback.print_exc()
                                self._updating_obra = False
                        self.obra_control.obra_combo.setCurrentIndex(-1)
                        self.obra_atual = None
                        self.obra_control.obra_atual = None
                        self.laje_tab.obra_atual = None
                        self.pavimentos_widget.set_obra(None)
                        self.canvas_widget.set_obra(None)
                    finally:
                        # Reabilitar sinais
                        self.obra_control.obra_combo.blockSignals(False)
                        self._obras_loaded = True
                        if callback:
                            callback()
                        print(f"[LOAD] ✅ Carregamento de obras concluído")
                    sys.stdout.flush()
                except Exception as e:
# print(f"[ERROR] Erro crítico ao carregar obras: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    # Continuar mesmo com erro para não travar aplicação
                    self.todas_obras = []
                    if hasattr(self, '_loading_obras'):
                        delattr(self, '_loading_obras')
            
            # Executar carregamento após um delay maior para garantir que UI está pronta
            QTimer.singleShot(500, carregar_obras)
            
        except Exception as e:
# print(f"[ERROR] Erro ao iniciar carregamento de obras: {str(e)}")
            import traceback
            traceback.print_exc()
            # Continuar mesmo com erro para não travar aplicação
            self.todas_obras = []
            if hasattr(self, '_loading_obras'):
                delattr(self, '_loading_obras')
    
    def save_all_obras_auto(self):
        """Salva automaticamente todas as obras"""
        # [CRÍTICO] Sincronizar cotas manuais da cena para o modelo antes de salvar
        if hasattr(self, 'canvas_widget'):
            self.canvas_widget.sync_manual_dimensions_to_model()

        # [CRÍTICO] Garantir que todas as obras estejam sincronizadas
        # Primeiro, atualizar self.todas_obras com obras do combo (pode ter novas obras)
        obras_do_combo = []
        for i in range(self.obra_control.obra_combo.count()):
            obra = self.obra_control.obra_combo.itemData(i)
            if obra:
                obras_do_combo.append(obra)
        
        # Mesclar obras do combo com self.todas_obras para não perder obras que não estão no combo
        obras_para_salvar = {}
        
        # Adicionar obras do combo (prioridade - podem ter sido modificadas)
        for obra in obras_do_combo:
            if obra and obra.nome:
                obras_para_salvar[obra.nome] = obra
        
        # Adicionar obras de self.todas_obras que não estão no combo (preservar obras não visíveis)
        if hasattr(self, 'todas_obras') and self.todas_obras:
            for obra in self.todas_obras:
                if obra and obra.nome and obra.nome not in obras_para_salvar:
                    print(f"[SAVE] Preservando obra '{obra.nome}' que não está no combo")
                    obras_para_salvar[obra.nome] = obra
        
        # Converter dict para lista mantendo ordem
        obras = list(obras_para_salvar.values())
        self.todas_obras = obras
        
        # [CRÍTICO] Verificar se há obras no combo que não estão em self.todas_obras
        for obra in obras_do_combo:
            if obra and obra.nome:
                obra_encontrada = False
                for o in self.todas_obras:
                    if o.nome == obra.nome:
                        obra_encontrada = True
                        break
                if not obra_encontrada:
                    print(f"[SAVE] ⚠️ Obra '{obra.nome}' está no combo mas não em self.todas_obras - adicionando")
                    self.todas_obras.append(obra)
        
        # [DEBUG] Verificar se pavimentos estão sendo preservados
        print(f"[SAVE] Salvando {len(obras)} obras")
        print(f"[SAVE DEBUG] 📊 Resumo antes de salvar:")
        print(f"[SAVE DEBUG]   - Obras do combo: {len(obras_do_combo)}")
        print(f"[SAVE DEBUG]   - Obras em self.todas_obras: {len(self.todas_obras) if hasattr(self, 'todas_obras') else 0}")
        print(f"[SAVE DEBUG]   - Obras a salvar (após mesclagem): {len(obras)}")
        for obra in obras:
            print(f"[SAVE] Obra '{obra.nome}': {len(obra.pavimentos)} pavimentos")
            for pav in obra.pavimentos:
                print(f"[SAVE]   - Pavimento '{pav.nome}': {len(pav.lajes)} lajes")
        
        save_all_obras(obras)
    
    def salvar_obra(self):
        """Salva obra atual em arquivo JSON"""
        # [CRÍTICO] Sincronizar cotas manuais da cena para o modelo antes de salvar
        if hasattr(self, 'canvas_widget'):
            self.canvas_widget.sync_manual_dimensions_to_model()

        if not self.obra_atual:
            QMessageBox.warning(self, "Aviso", "Nenhuma obra para salvar.")
            return
        
        if save_obra(self.obra_atual, self):
            QMessageBox.information(self, "Sucesso", "Obra salva com sucesso!")
    
    def importar_obra(self):
        """Carrega obra de arquivo JSON e adiciona à lista existente"""
        obra = load_obra(self)
        if obra:
            self.obra_atual = obra
            
            # Verificar se obra já existe na lista
            existing_index = -1
            for i in range(self.obra_control.obra_combo.count()):
                item_obra = self.obra_control.obra_combo.itemData(i)
                if item_obra and item_obra.nome == obra.nome:
                    existing_index = i
                    break
            
            if existing_index >= 0:
                # Obter a obra existente para verificar se é treino
                obra_existente = self.obra_control.obra_combo.itemData(existing_index)
# print(f"[DEBUG IMPORT] Obra Importada: '{obra.nome}' | Obra Existente: '{obra_existente.nome}'")
                
                # Verificação mais robusta (case insensitive e verificação de conteúdo)
                is_treino_name = "populacao_treino" in obra.nome.lower().replace(" ", "_")
                has_treino_pavements = any(p.nome.lower() in ["treino", "erros"] for p in obra.pavimentos)
# print(f"[DEBUG IMPORT] is_treino_name={is_treino_name}, has_treino_pavements={has_treino_pavements}")
                
                # Se for identificado como treino (pelo nome OU pelo conteúdo dos pavimentos)
                if (is_treino_name or has_treino_pavements) and obra_existente:
                    reply = QMessageBox.question(
                        self,
                        "Mesclar Treinos?",
                        f"Detectada obra de treino ('{obra.nome}').\n"
                        f"Deseja MESCLAR os dados importados com os existentes?\n"
                        f"(Sim = Soma itens | Não = Substitui a obra inteira)",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        # Logica de MESCLAGEM (Merge)
                        count_merged = 0
# print("[DEBUG IMPORT] Iniciando mesclagem...")
                        # Para cada pavimento na obra importada
                        for pav_novo in obra.pavimentos:
                            # Tentar encontrar pavimento correspondente na obra existente
                            pav_existente = next((p for p in obra_existente.pavimentos if p.nome == pav_novo.nome), None)
                            
                            if pav_existente:
                                # Adicionar lajes novas ao existente
# print(f"[DEBUG IMPORT] Mesclando pavimento '{pav_novo.nome}': {len(pav_novo.lajes)} itens adicionados.")
                                pav_existente.lajes.extend(pav_novo.lajes)
                                count_merged += len(pav_novo.lajes)
                            else:
                                # Se pavimento não existe, adiciona ele inteiro
# print(f"[DEBUG IMPORT] Adicionando novo pavimento '{pav_novo.nome}'.")
                                obra_existente.pavimentos.append(pav_novo)
                                count_merged += len(pav_novo.lajes)
                                
                        # Atualizar a referência 'obra' para a combinada
                        obra = obra_existente
                        
                        # IMPORTANTE: Atualizar a obra existente no combo box e na lista global
                        self.obra_control.obra_combo.setItemData(existing_index, obra)
                        for i, o in enumerate(self.todas_obras):
                            if o.nome == obra.nome:
                                self.todas_obras[i] = obra
                                break
                                
                        msg_sucesso = f"Dados de treino mesclados com sucesso! ({count_merged} itens adicionados)"
# print(f"[DEBUG IMPORT] Mesclagem concluída. Total itens: {count_merged}")
                    else:
                        # Se não mesclar, substitui (comportamento padrão)
# print("[DEBUG IMPORT] Usuário optou por substituir.")
                        self.obra_control.obra_combo.setItemData(existing_index, obra)
                        # Atualizar na lista self.todas_obras
                        for i, o in enumerate(self.todas_obras):
                            if o.nome == obra.nome:
                                self.todas_obras[i] = obra
                                break
                        msg_sucesso = f"Obra '{obra.nome}' substituída com sucesso!"
                else:
                    # Comportamento padrão para outras obras: Atualizar/Substituir
# print("[DEBUG IMPORT] Obra comum. Substituindo.")
                    self.obra_control.obra_combo.setItemData(existing_index, obra)
                    # Atualizar na lista self.todas_obras
                    for i, o in enumerate(self.todas_obras):
                        if o.nome == obra.nome:
                            self.todas_obras[i] = obra
                            break
                    msg_sucesso = f"Obra '{obra.nome}' atualizada com sucesso!"
                
                self.obra_control.obra_combo.setCurrentIndex(existing_index)
                
            else:
                # Adicionar nova obra
                self.obra_control.obra_combo.addItem(obra.nome, obra)
                self.obra_control.obra_combo.setCurrentIndex(self.obra_control.obra_combo.count() - 1)
                self.todas_obras.append(obra)
                msg_sucesso = f"Obra '{obra.nome}' importada com sucesso!"
            
            # Definir a obra atual (seja a nova, a substituída ou a mesclada)
            self.obra_atual = obra
            
            # Atualizar widgets
            self.obra_control.obra_atual = obra
            self.laje_tab.obra_atual = obra
            self.pavimentos_widget.set_obra(obra)
            self.canvas_widget.set_obra(obra)
            
            # Salvar todas as obras atualizadas
            self.save_all_obras_auto()
            
            QMessageBox.information(self, "Sucesso", msg_sucesso)
    
    def limpar_todos_dados(self):
        """Limpa todos os dados salvos (obras, pavimentos, lajes)"""
        reply = QMessageBox.question(
            self,
            "Confirmar Limpeza",
            "Tem certeza que deseja limpar TODOS os dados salvos?\n\n"
            "Esta ação irá remover:\n"
            "- Todas as obras\n"
            "- Todos os pavimentos\n"
            "- Todas as lajes\n\n"
            "Esta ação NÃO pode ser desfeita!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if clear_all_data():
                # Limpar interface
                self.obra_control.obra_combo.clear()
                self.obra_atual = None
                self.todas_obras = []
                self.laje_tab.obra_atual = None
                self.pavimentos_widget.set_obra(None)
                self.canvas_widget.set_obra(None)
                
                QMessageBox.information(
                    self,
                    "Dados Limpos",
                    "Todos os dados foram limpos com sucesso!"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Erro",
                    "Erro ao limpar dados. Verifique os logs para mais informações."
                )
    
    def show_about(self):
        QMessageBox.about(self, "Sobre", "Gerenciador de Lajes v1.0\n\nAplicativo para gerenciamento de lajes de concreto com integração AutoCAD.")
    
    def on_laje_selecionada(self, laje, aplicar_correcoes_automaticas: bool = False):
        """Atualiza canvas e outros widgets quando laje é selecionada
        
        Args:
            laje: Laje selecionada
            aplicar_correcoes_automaticas: Se True, executa correções automáticas (padrão False para seleção na lista)
        """
        self.canvas_widget.set_laje(laje, aplicar_correcoes_automaticas=aplicar_correcoes_automaticas)
        if laje:
            self.canvas_widget.set_linhas(laje.linhas_verticais, laje.linhas_horizontais)
    
    def on_obra_control_changed(self, obra):
        """Atualiza widgets quando obra é alterada no controle de obra"""
        # Proteção contra loops infinitos
        if self._updating_obra:
            return
        self._updating_obra = True
        
        try:
            self.obra_atual = obra
            self.laje_tab.on_obra_changed(obra)
            self.pavimentos_widget.set_obra(obra)
            # Atualizar obra no canvas
            self.canvas_widget.set_obra(obra)
            # Selecionar primeiro pavimento disponível ou limpar se não houver
            if obra and obra.pavimentos:
                self.pavimentos_widget.selecionar_primeiro_pavimento()
            else:
                # Limpar tabela de lajes se não houver pavimentos
                self.laje_tab._populate_tree([])
                # Limpar canvas e resumo
                self.canvas_widget.set_laje(None)
            self.save_all_obras_auto()
        finally:
            self._updating_obra = False
    
    def on_linhas_changed(self, verticais, horizontais):
        """Atualiza canvas e resumo de painéis quando linhas mudam (dos campos de texto)"""
        if self.laje_tab.laje_atual and self.obra_atual:
            # Fazer cópias das listas para evitar referências compartilhadas
            verticais_copy = list(verticais) if verticais else []
            horizontais_copy = list(horizontais) if horizontais else []
            
            # IMPORTANTE: Atualizar a laje na lista do pavimento primeiro
            # Encontrar o pavimento e a laje correspondente na lista
            pavimento_nome = self.laje_tab.laje_atual.pavimento
            if pavimento_nome:
                pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == pavimento_nome), None)
                if pavimento:
                    # Encontrar a laje na lista do pavimento pelo número e nome
                    laje_na_lista = next(
                        (l for l in pavimento.lajes 
                         if l.numero == self.laje_tab.laje_atual.numero 
                         and l.nome == self.laje_tab.laje_atual.nome),
                        None
                    )
                    if laje_na_lista:
                        # Atualizar a laje na lista com as novas linhas (cópias)
                        laje_na_lista.linhas_verticais = verticais_copy
                        laje_na_lista.linhas_horizontais = horizontais_copy
                        # Garantir que a referência local aponte para a mesma laje
                        self.laje_tab.laje_atual = laje_na_lista
                    else:
                        # Se não encontrou na lista, atualizar a laje atual diretamente
                        self.laje_tab.laje_atual.linhas_verticais = verticais_copy
                        self.laje_tab.laje_atual.linhas_horizontais = horizontais_copy
                else:
                    # Se não encontrou o pavimento, atualizar a laje atual diretamente
                    self.laje_tab.laje_atual.linhas_verticais = verticais_copy
                    self.laje_tab.laje_atual.linhas_horizontais = horizontais_copy
            else:
                # Se não tem pavimento, atualizar a laje atual diretamente
                self.laje_tab.laje_atual.linhas_verticais = verticais_copy
                self.laje_tab.laje_atual.linhas_horizontais = horizontais_copy
            
            self.canvas_widget.set_linhas(verticais, horizontais)
            # Atualizar total m² no controle de obra
            if self.obra_atual:
                self.obra_control.update_total_m2()
                # Salvar automaticamente quando linhas mudam
                self.save_all_obras_auto()
    
    def on_linhas_edited_from_canvas(self, verticais, horizontais):
        """Atualiza campos de linhas e salva quando linhas são editadas no canvas"""
        if self.laje_tab.laje_atual and self.obra_atual:
            # Fazer cópias das listas para evitar referências compartilhadas
            verticais_copy = list(verticais) if verticais else []
            horizontais_copy = list(horizontais) if horizontais else []
            
            # IMPORTANTE: Atualizar a laje na lista do pavimento primeiro
            pavimento_nome = self.laje_tab.laje_atual.pavimento
            if pavimento_nome:
                pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == pavimento_nome), None)
                if pavimento:
                    laje_na_lista = next(
                        (l for l in pavimento.lajes 
                         if l.numero == self.laje_tab.laje_atual.numero 
                         and l.nome == self.laje_tab.laje_atual.nome),
                        None
                    )
                    if laje_na_lista:
                        # Atualizar a laje na lista com as novas linhas (cópias)
                        laje_na_lista.linhas_verticais = verticais_copy
                        laje_na_lista.linhas_horizontais = horizontais_copy
                        self.laje_tab.laje_atual = laje_na_lista
                    else:
                        # Se não encontrou na lista, atualizar a laje atual diretamente
                        self.laje_tab.laje_atual.linhas_verticais = verticais_copy
                        self.laje_tab.laje_atual.linhas_horizontais = horizontais_copy
                else:
                    # Se não encontrou o pavimento, atualizar a laje atual diretamente
                    self.laje_tab.laje_atual.linhas_verticais = verticais_copy
                    self.laje_tab.laje_atual.linhas_horizontais = horizontais_copy
            else:
                # Se não tem pavimento, atualizar a laje atual diretamente
                self.laje_tab.laje_atual.linhas_verticais = verticais_copy
                self.laje_tab.laje_atual.linhas_horizontais = horizontais_copy
            
            # NÃO chamar set_linhas aqui para evitar loop - os overlays já estão atualizados
            # Apenas atualizar resumo de painéis e salvar
            
            # Atualizar total m² no controle de obra
            if self.obra_atual:
                self.obra_control.update_total_m2()
                # Salvar automaticamente quando linhas mudam
                self.save_all_obras_auto()
    
    def on_obra_changed(self, obra):
        """Atualiza widgets quando obra é alterada via sinal"""
        # Proteção contra loops infinitos
        if self._updating_obra:
            return
        
        # [CRÍTICO] Garantir que obras criadas dinamicamente sejam adicionadas a self.todas_obras
        if obra and obra.nome:
            obra_existe = False
            # Verificar se obra já está em self.todas_obras
            for i, o in enumerate(self.todas_obras):
                if o.nome == obra.nome:
                    # Atualizar referência (pode ter sido modificada)
                    self.todas_obras[i] = obra
                    obra_existe = True
                    break
            
            # Se obra não existe em self.todas_obras, adicionar
            if not obra_existe:
                print(f"[on_obra_changed] Adicionando obra criada dinamicamente '{obra.nome}' a self.todas_obras")
                self.todas_obras.append(obra)
            
            # Garantir que obra está no combo (pode ter sido criada externamente)
            obra_no_combo = False
            for i in range(self.obra_control.obra_combo.count()):
                obra_combo = self.obra_control.obra_combo.itemData(i)
                if obra_combo and obra_combo.nome == obra.nome:
                    # Atualizar referência no combo se necessário
                    if obra_combo is not obra:
                        self.obra_control.obra_combo.setItemData(i, obra)
                    obra_no_combo = True
                    break
            
            if not obra_no_combo:
                print(f"[on_obra_changed] Adicionando obra '{obra.nome}' ao combo")
                self.obra_control.obra_combo.addItem(obra.nome, obra)
                self.obra_control.obra_combo.setCurrentIndex(self.obra_control.obra_combo.count() - 1)
        
        self._updating_obra = True
        
        try:
            self.obra_atual = obra
            self.obra_control.set_obra(obra)
            self.obra_control.update_total_m2()
            # Atualizar lista de pavimentos SEM mexer na seleção atual
            # (evita voltar sempre para o primeiro pavimento ao criar/excluir lajes)
            self.pavimentos_widget.set_obra(obra)
            # Atualizar obra no canvas
            self.canvas_widget.set_obra(obra)
            # Se a obra NÃO tiver pavimentos, limpar listas/visuais.
            # Se tiver pavimentos, manter o pavimento já selecionado pelo usuário.
            if not (obra and obra.pavimentos):
                self.laje_tab._populate_tree([])
                self.canvas_widget.set_laje(None)
            
            # Salvar automaticamente quando obra é alterada
            self.save_all_obras_auto()
        finally:
            self._updating_obra = False
    
    def on_save_requested(self, obra):
        """Salva obra sem recálculos ou atualizações de widgets"""
        # Apenas salvar arquivo, sem atualizar widgets ou recalcular nada
        # Atualizar obra atual e lista de obras antes de salvar
        self.obra_atual = obra
        # Atualizar obra no combo se necessário (sem disparar sinais)
        for i in range(self.obra_control.obra_combo.count()):
            obra_no_combo = self.obra_control.obra_combo.itemData(i)
            if obra_no_combo and obra_no_combo.nome == obra.nome:
                # Substituir obra no combo pela atualizada (sem emitir sinais)
                self.obra_control.obra_combo.setItemData(i, obra)
                break
        # Salvar todas as obras
        self.save_all_obras_auto()

    def _n3_lajes_dir_for_current_obra(self) -> Path | None:
        if not self.obra_atual or not getattr(self.obra_atual, "nome", ""):
            return None
        return Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS") / self.obra_atual.nome / "Fase-4_Sincronizacao" / "JSON_Lajes"

    def _is_n3_laje_json_for_robo_sync(self, path: Path, data: dict, nome_pavimento: str) -> bool:
        stem = path.stem.upper()
        if not re.fullmatch(r"L\d+[A-Z]?", stem):
            return False

        nome = str(data.get("nome") or stem).strip().upper()
        if not re.fullmatch(r"L\d+[A-Z]?", nome):
            return False

        meta = data.get("_sa_meta") if isinstance(data.get("_sa_meta"), dict) else {}
        source = str(meta.get("source") or meta.get("n3_source") or "").lower()
        pav = str(data.get("pavimento") or meta.get("pavimento") or "").strip()

        if source in {"comparison_engine_n1", "robo_laje_shared_ficha"}:
            return True

        if pav and pav.lower() not in {"pavimento", nome_pavimento.lower()}:
            return False

        return not pav

    def _sync_n3_lajes_to_selected_pavimento(self, nome_pavimento: str) -> int:
        """Importa fichas N3/Comparison para o pavimento atual do Robo Laje sem sobrescrever edicoes."""
        if not self.obra_atual or not nome_pavimento:
            return 0

        n3_dir = self._n3_lajes_dir_for_current_obra()
        if not n3_dir or not n3_dir.exists():
            return 0

        pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == nome_pavimento), None)
        if not pavimento:
            return 0

        from laje_src.models.laje import Laje

        existentes = {str(getattr(laje, "nome", "")).strip().upper() for laje in pavimento.lajes}
        novas_lajes = []
        for json_path in sorted(n3_dir.glob("L*.json"), key=lambda p: _natural_laje_name_key(p.stem)):
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            if not self._is_n3_laje_json_for_robo_sync(json_path, data, nome_pavimento):
                continue

            nome = str(data.get("nome") or json_path.stem).strip().upper()
            if not nome or nome in existentes:
                continue

            laje_data = dict(data)
            laje_data["nome"] = nome
            laje_data["pavimento"] = nome_pavimento
            try:
                laje = Laje.from_dict(laje_data)
            except Exception:
                continue
            laje.pavimento = nome_pavimento
            novas_lajes.append(laje)
            existentes.add(nome)

        if not novas_lajes:
            return 0

        pavimento.lajes.extend(novas_lajes)
        pavimento.lajes.sort(key=lambda laje: (getattr(laje, "numero", 0), _natural_laje_name_key(getattr(laje, "nome", ""))))
        if hasattr(self, "pavimentos_widget"):
            self.pavimentos_widget.update_list()
        return len(novas_lajes)
    
    def on_pavimento_selected(self, nome_pavimento):
        """Atualiza widgets quando pavimento é selecionado"""
        # Atualizar combo de pavimentos
        self.laje_tab.pavimento_combo.setCurrentText(nome_pavimento)
        
        if not self.obra_atual:
            return
        
        # Encontrar o pavimento selecionado
        pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == nome_pavimento), None)
        if not pavimento:
            return

        imported_count = self._sync_n3_lajes_to_selected_pavimento(nome_pavimento)
        if imported_count:
            pavimento = next((p for p in self.obra_atual.pavimentos if p.nome == nome_pavimento), pavimento)
            self.save_all_obras_auto()
        
        # Limpar seleção anterior da tabela (evitar exclusão de lajes de outros pavimentos)
        self.laje_tab.tree_widget.clearSelection()
        
        # Filtrar tabela de lajes para mostrar apenas lajes do pavimento selecionado
        self.laje_tab._populate_tree(pavimento.lajes)
        
        # Atualizar canvas conforme modo de visualização
        modo_canvas = self.canvas_widget.modo_visualizacao
        if modo_canvas == "Pavimento":
            # Se estiver em modo Pavimento, atualizar para o pavimento selecionado
            self.canvas_widget.set_pavimento(nome_pavimento)
        elif modo_canvas == "Item":
            # Se estiver em modo Item, mostrar primeira laje do pavimento
            if pavimento.lajes:
                primeira_laje = pavimento.lajes[0]
                self.canvas_widget.set_laje(primeira_laje)
                self.laje_tab.laje_atual = primeira_laje
            else:
                # Se não houver lajes, limpar canvas
                self.canvas_widget.set_laje(None)
                self.laje_tab.laje_atual = None
        
        # Atualizar canvas conforme modo de visualização (final do método)


    
    def on_pavimento_adicionado(self, nome_pavimento):
        """Atualiza combobox quando pavimento é adicionado"""
        self.atualizar_combo_pavimentos()
    
    def on_pavimento_removido(self, nome_pavimento):
        """Atualiza combobox quando pavimento é removido"""
        self.atualizar_combo_pavimentos()
        # Se o pavimento removido estava selecionado, limpar seleção
        if _pav_cmb_raw(self.laje_tab.pavimento_combo) == nome_pavimento:
            self.laje_tab.pavimento_combo.setCurrentIndex(-1)
    
    def atualizar_combo_pavimentos(self):
        """Atualiza o combobox de pavimentos com os pavimentos da obra atual"""
        if self.obra_atual:
            # Salvar raw atual
            texto_atual = _pav_cmb_raw(self.laje_tab.pavimento_combo)

            # Limpar e recarregar
            self.laje_tab.pavimento_combo.clear()

            # Adicionar todos os pavimentos
            for pavimento in self.obra_atual.pavimentos:
                self.laje_tab.pavimento_combo.addItem(_fmt_pav_label(pavimento.nome), pavimento.nome)

            # Restaurar seleção se ainda existir
            if texto_atual:
                _set_pav_cmb(self.laje_tab.pavimento_combo, texto_atual)
            
            # Atualizar também a tabela de lajes respeitando filtro do pavimento
            self.laje_tab.atualizar_tabela_lajes()
    
    def on_modo_calculo_selecionado(self, modo_index: int):
        """Chamado quando um modo de cálculo é selecionado"""
        # Verificar se há uma laje selecionada com coordenadas
        if not self.laje_tab.laje_atual or not self.laje_tab.laje_atual.coordenadas:
            QMessageBox.warning(
                self, 
                "Aviso", 
                "Selecione uma laje com coordenadas antes de usar o cálculo automático."
            )
            return
        
        # Modo 0 = M1
        if modo_index == 0:
            # Calcular linhas usando o Modo 1
            coordenadas = self.laje_tab.laje_atual.coordenadas
            resultado = calcular_modo1(coordenadas)
            if resultado:
                verticais, horizontais = resultado
                # Verificar limites de segurança
                from laje_src.services.geometry_calculator import MAX_LINHAS_VERTICAIS, MAX_LINHAS_HORIZONTAIS
                if not verticais and not horizontais:
                    QMessageBox.warning(
                        self, "Aviso", 
                        f"Laje muito grande: número de linhas excede limites de segurança.\n"
                        f"Limite: {MAX_LINHAS_VERTICAIS} verticais, {MAX_LINHAS_HORIZONTAIS} horizontais."
                    )
                    return
                if len(verticais) > MAX_LINHAS_VERTICAIS or len(horizontais) > MAX_LINHAS_HORIZONTAIS:
                    QMessageBox.warning(
                        self, "Aviso", 
                        f"Laje muito grande: número de linhas excede limites.\n"
                        f"Verticais: {len(verticais)} (limite: {MAX_LINHAS_VERTICAIS})\n"
                        f"Horizontais: {len(horizontais)} (limite: {MAX_LINHAS_HORIZONTAIS})"
                    )
                    return
            else:
                verticais, horizontais = [], []
            
            # Aplicar as linhas calculadas
            self.canvas_widget.set_linhas(verticais, horizontais)
            
            QMessageBox.information(
                self,
                "Cálculo Automático M1 (Verticais)",
                f"Linhas calculadas:\n"
                f"Verticais: {len(verticais)} linhas\n"
                f"Horizontais: {len(horizontais)} linhas"
            )
        elif modo_index == 1:
            # Modo 1 = M2 (inverte a lógica do M1)
            # Calcular linhas usando o Modo 2
            coordenadas = self.laje_tab.laje_atual.coordenadas
            resultado = calcular_modo2(coordenadas)
            if resultado:
                verticais, horizontais = resultado
                # Verificar limites de segurança
                from laje_src.services.geometry_calculator import MAX_LINHAS_VERTICAIS, MAX_LINHAS_HORIZONTAIS
                if not verticais and not horizontais:
                    QMessageBox.warning(
                        self, "Aviso", 
                        f"Laje muito grande: número de linhas excede limites de segurança.\n"
                        f"Limite: {MAX_LINHAS_VERTICAIS} verticais, {MAX_LINHAS_HORIZONTAIS} horizontais."
                    )
                    return
                if len(verticais) > MAX_LINHAS_VERTICAIS or len(horizontais) > MAX_LINHAS_HORIZONTAIS:
                    QMessageBox.warning(
                        self, "Aviso", 
                        f"Laje muito grande: número de linhas excede limites.\n"
                        f"Verticais: {len(verticais)} (limite: {MAX_LINHAS_VERTICAIS})\n"
                        f"Horizontais: {len(horizontais)} (limite: {MAX_LINHAS_HORIZONTAIS})"
                    )
                    return
            else:
                verticais, horizontais = [], []
            
            # Aplicar as linhas calculadas
            self.canvas_widget.set_linhas(verticais, horizontais)
            
            QMessageBox.information(
                self,
                "Cálculo Automático M2 (Horizontais)",
                f"Linhas calculadas:\n"
                f"Verticais: {len(verticais)} linhas\n"
                f"Horizontais: {len(horizontais)} linhas"
            )
        else:
            # Outros modos ainda não implementados
            QMessageBox.information(
                self,
                "Modo não implementado",
                f"O modo {modo_index + 1} ainda não foi implementado."
            )
    
    def handle_training_example(self, nova_laje, comentario, feedback_type="positive"):
        """Recebe uma laje clonada do CanvasWidget e a salva na obra Populacao_Treino global"""
        try:
            from laje_src.models.obra import Obra
            from laje_src.models.pavimento import Pavimento
            
            # 1. Encontrar ou criar obra 'Populacao_Treino' na lista GLOBAL
            target_obra = next((o for o in self.todas_obras if o.nome == "Populacao_Treino"), None)
            
            if not target_obra:
                print("[INFO] Criando nova obra Populacao_Treino na lista global")
                target_obra = Obra(nome="Populacao_Treino")
                self.todas_obras.append(target_obra)
                # Atualizar combo box
                self.obra_control.set_obra(target_obra) # Adiciona ao combo se não existir
            
            # 2. Determinar nome do pavimento baseado em feedback_type e intelligence_mode
            mode = getattr(nova_laje, 'intelligence_mode', 0)
            
            if feedback_type == "positive":
                if mode == 1:
                    pav_nome = "Pavimento treino modo 2"
                else:
                    pav_nome = "Pavimento treino modo 1"
            elif feedback_type == "dimension_training":
                # Treino de Cotas
                dim_mode = getattr(nova_laje, 'dimension_training_mode', mode)
                if dim_mode == 1:
                    pav_nome = "Treino Cotas Modo 2"
                else:
                    pav_nome = "Treino Cotas Modo 1"
            elif feedback_type == "dimension_error":
                # Erro de Cotas
                dim_mode = getattr(nova_laje, 'dimension_training_mode', mode)
                if dim_mode == 1:
                    pav_nome = "Erro Cotas Modo 2"
                else:
                    pav_nome = "Erro Cotas Modo 1"
            else:
                if mode == 1:
                    pav_nome = "Pavimento erro modo 2"
                else:
                    pav_nome = "Pavimento erro modo 1"
            
            # 3. Encontrar ou criar o pavimento alvo
            target_pav = next((p for p in target_obra.pavimentos if p.nome == pav_nome), None)
            
            if not target_pav:
                print(f"[INFO] Criando pavimento {pav_nome} global")
                target_pav = Pavimento(nome=pav_nome)
                target_obra.pavimentos.append(target_pav)
            
            # 4. Adicionar Laje
            target_pav.lajes.append(nova_laje)
            print(f"[SUCCESS] Laje '{nova_laje.nome}' adicionada ao pavimento '{pav_nome}'. Total agora: {len(target_pav.lajes)}")

            # Feedback visual para o usuário
            feedback_msg = f"Salvo como exemplo {'positivo' if feedback_type=='positive' else 'negativo'} em '{pav_nome}'."
            self.canvas_widget.ai_status_message.emit(f"Aprendizado Registrado", feedback_msg, "{DS.SUCCESS}" if feedback_type=='positive' else "{DS.DANGER}")
            
            # 4. Salvar TUDO atomicamente
            self.save_all_obras_auto()
            
            # Se o usuário estiver visualizando esta obra, atualizar a tabela
            if self.obra_atual == target_obra:
                 self.pavimentos_widget.update_list()
                 if self.pavimentos_widget.table_model.rowCount() > 0:
                      # Opcional: recarregar detalhes
                      pass

        except Exception as e:
# print(f"[ERROR] Erro ao persistir treino no MainWindow: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Erro de Salvamento", f"Falha ao salvar treino: {e}")

    def handle_lajes_deleted(self, lajes_list):
        """Chamado quando lajes são excluídas no LajeTab.
        Se as lajes pertencem à obra de treinamento, remove-as também do DB da IA.
        """
        if not self.obra_atual or self.obra_atual.nome != "Populacao_Treino":
            return
# print(f"[AI] Detectada exclusão de {len(lajes_list)} itens da obra Populacao_Treino. Sincronizando com DB de IA...")
        learner = self.canvas_widget.learner
        
        removidos_db = 0
        for laje in lajes_list:
            # Tentar excluir do banco de dados SQLite do LayoutLearner
            succ = learner.delete_training_example(
                laje.coordenadas,
                laje.obstaculos,
                laje.modo_selecionado,
                laje.linhas_verticais,
                laje.linhas_horizontais
            )
            if succ:
                removidos_db += 1
        
        if removidos_db > 0:
            pass
            # print(f"[AI] SUCESSO: {removidos_db} exemplos removidos do banco de dados de inteligência.")
        else:
            pass
            # print("[AI] Nenhum exemplo correspondente encontrado no DB para as lajes excluídas (provavelmente já limpo ou padrão diferente).")

    def on_reaproveitamento_aplicado(self, resultado):
        """Chamado quando um reaproveitamento é aplicado ou limpo"""
        # Atualizar canvas para redesenhar com informações de REAP
        if self.laje_tab.laje_atual:
            self.canvas_widget.set_laje(self.laje_tab.laje_atual)
        
        # Salvar automaticamente
        self.save_all_obras_auto()
    
    def on_reaproveitamento_opcoes_changed(self, _state=None):
        """Chamado quando opções de visualização do REAP mudam (checkboxes em Opções de Desenho)"""
        # Obter opções dos checkboxes existentes
        opcoes = {
            "desenhar_nomes": self.laje_tab.checkbox_nomes_reaproveitamento.isChecked(),
            "mostrar_hatches": self.laje_tab.checkbox_hatchs_reaproveitamento.isChecked()
        }
        
        # Atualizar canvas com novas opções
        self.canvas_widget.set_reap_opcoes(opcoes)
        
        # Redesenhar canvas
        if self.laje_tab.laje_atual:
            self.canvas_widget.atualizar_visualizacao()
    
    def set_user_session(self, email: str, nome: str, credits: float):
        """Define informações da sessão do usuário"""
        self._user_email = email
        self._user_name = nome
        self._user_credits = credits
        self.update_credits_display()
        self.setWindowTitle(f"Lajes - {nome}")
    
    def update_credits_display(self):
        """Atualiza exibição de créditos na barra de status"""
        if hasattr(self, 'user_label'):
            self.user_label.setText(f"👤 {self._user_name or self._user_email}")
        
        if hasattr(self, 'credits_label'):
            credits = self._user_credits
            
            # Mudar cor baseado na quantidade de créditos
            if credits <= 0:
                color = f"{DS.DANGER}"  # Vermelho
                bg = "rgba(220, 53, 69, int(1/100*255))"
            elif credits < 100:
                color = f"{DS.GOLD}"  # Amarelo
                bg = "rgba(255, 193, 7, int(1/100*255))"
            else:
                color = f"{DS.SUCCESS}"  # Verde
                bg = "rgba(40, 167, 69, int(1/100*255))"
            
            self.credits_label.setText(f"💳 {credits:.2f} m²")
            self.credits_label.setStyleSheet(f"""
                color: {color};
                font-weight: bold;
                padding: 2px 15px;
                background-color: {bg};
                border-radius: 4px;
            """)
    
    def refresh_credits(self):
        """Atualiza créditos do servidor"""
        try:
            from laje_src.services.auth_service import auth_service
            from laje_src.config.secrets import DEBUG_MODE
            
            if DEBUG_MODE:
                return
            
            if auth_service.is_logged_in:
                success, credits = auth_service.get_credits()
                if success:
                    self._user_credits = credits
                    self.update_credits_display()
        except Exception as e:
            pass
            # print(f"Erro ao atualizar créditos: {e}")
            
    def update_connection_status(self):
        """Verifica e atualiza visualmente o status da conexão"""
        try:
            from laje_src.services.auth_service import auth_service
            is_off = auth_service.is_offline
            
            if is_off:
                self.connection_label.setText("🚫 OFFLINE")
                self.connection_label.setStyleSheet("""
                    color: {DS.DANGER}; 
                    font-weight: bold; 
                    padding: 0 10px;
                    border-right: 1px solid {DS.BASE};
                """)
                self.refresh_btn.setEnabled(False)
                self.refresh_btn.setToolTip("Indisponível em modo offline")
            else:
                self.connection_label.setText("🌐 ONLINE")
                self.connection_label.setStyleSheet("""
                    color: {DS.SUCCESS}; 
                    font-weight: bold; 
                    padding: 0 10px;
                    border-right: 1px solid {DS.BASE};
                """)
                self.refresh_btn.setEnabled(True)
                self.refresh_btn.setToolTip("Atualizar créditos")
        except Exception as e:
            pass
            # print(f"Erro ao atualizar status de conexão: {e}")
    
    def do_logout(self):
        """Realiza logout do usuário"""
        reply = QMessageBox.question(
            self,
            "Confirmar Logout",
            "Deseja realmente sair?\n\nA obra atual será salva automaticamente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Salvar antes de sair
            self.save_all_obras_auto()
            
            # Fazer logout
            try:
                from laje_src.services.auth_service import auth_service
                auth_service.logout()
            except Exception:
                pass
            
            # Fechar aplicação
            self.close()
    
    def closeEvent(self, event: QCloseEvent):
        """Salva automaticamente ao fechar a aplicação"""
        self.save_all_obras_auto()
        
        # Fazer logout ao fechar
        try:
            from laje_src.services.auth_service import auth_service
            auth_service.logout()
        except Exception:
            pass
        
        event.accept()

