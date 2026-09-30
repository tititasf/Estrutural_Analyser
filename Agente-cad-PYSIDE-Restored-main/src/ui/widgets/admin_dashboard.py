import base64
import json

# Helper de ofuscação corrigido
def _get_obf_str(key):
    """Retorna string ofuscada (Versão Corrigida)"""
    try:
        _obf_map = {
            "script.google.com": base64.b64decode("=02bj5SZsd2bvdmL0BXayN2c"[::-1].encode()).decode(),
            "macros/s/": base64.b64decode("vM3Lz9mcjFWb"[::-1].encode()).decode(),
            "AKfycbz": base64.b64decode("==geiNWemtUQ"[::-1].encode()).decode(),
            "credit": base64.b64decode("0lGZlJ3Y"[::-1].encode()).decode(),
            "saldo": base64.b64decode("=8GZsF2c"[::-1].encode()).decode(),
            "consumo": base64.b64decode("==wbtV3cu92Y"[::-1].encode()).decode(),
            "api_key": base64.b64decode("==Qelt2XpBXY"[::-1].encode()).decode(),
            "user_id": base64.b64decode("==AZp9lclNXd"[::-1].encode()).decode(),
            "calcular_creditos": base64.b64decode("=M3b0lGZlJ3YfJXYsV3YsF2Y"[::-1].encode()).decode(),
            "confirmar_consumo": base64.b64decode("=8Wb1NnbvN2XyFWbylmZu92Y"[::-1].encode()).decode(),
            "consultar_saldo": base64.b64decode("vRGbhN3XyFGdsV3cu92Y"[::-1].encode()).decode(),
            "debitar_creditos": base64.b64decode("==wcvRXakVmcj9lchRXaiVGZ"[::-1].encode()).decode(),
            "CreditManager": base64.b64decode("==gcldWYuFWT0lGZlJ3Q"[::-1].encode()).decode(),
            "obter_hwid": base64.b64decode("==AZpdHafJXZ0J2b"[::-1].encode()).decode(),
            "generate_signature": base64.b64decode("lJXd0Fmbnl2cfVGdhJXZuV2Z"[::-1].encode()).decode(),
            "encrypt_string": base64.b64decode("=cmbpJHdz9Fdwlncj5WZ"[::-1].encode()).decode(),
            "decrypt_string": base64.b64decode("=cmbpJHdz9FdwlncjVGZ"[::-1].encode()).decode(),
            "integrity_check": base64.b64decode("rNWZoN2X5RXaydWZ05Wa"[::-1].encode()).decode(),
            "security_utils": base64.b64decode("=MHbpRXdflHdpJXdjV2c"[::-1].encode()).decode(),
            "https://": base64.b64decode("=8yL6MHc0RHa"[::-1].encode()).decode(),
            "google.com": base64.b64decode("==QbvNmLlx2Zv92Z"[::-1].encode()).decode(),
            "apps.script": base64.b64decode("=QHcpJ3Yz5ycwBXY"[::-1].encode()).decode(),
        }
        return _obf_map.get(key, key)
    except Exception:
        return key


import logging
from typing import Dict, List, Any
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                                QFrame, QScrollArea, QTabWidget, QGridLayout, 
                                QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QProgressBar,
                                QSplitter, QListWidget, QListWidgetItem, QTextEdit, QMessageBox)
from PySide6.QtCore import Qt, QSize
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
from PySide6.QtGui import QPainter, QLinearGradient, QColor, QGradient
from src.ui.dialogs.project_details_dialog import ProjectDetailsDialog
from src.ui.components.project_cards import CuradoriaCard
from src.ui.widgets.data_pipeline import DataPipelineView
from src.ui.theme import Colors, Fonts, Radius

class DashboardCard(QFrame):
    def __init__(self, title: str, value: str, subtext: str = "", color: str = Colors.ACCENT_BLUE):
        super().__init__()
        self.setObjectName("DashboardCard")
        self.setFrameShape(QFrame.StyledPanel)
        
        layout = QVBoxLayout(self)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 14px; font-weight: bold;")
        layout.addWidget(lbl_title)
        
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"color: {color}; font-size: 32px; font-weight: bold; margin-top: 5px;")
        layout.addWidget(self.lbl_value)
        
        if subtext:
            lbl_sub = QLabel(subtext)
            lbl_sub.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 12px;")
            layout.addWidget(lbl_sub)
            
        self.setStyleSheet(f"""
            #DashboardCard {{
                background-color: {Colors.BG_CARD};
                border-radius: 12px;
                padding: 15px;
                border: 1px solid {Colors.BORDER_DEFAULT};
            }}
            #DashboardCard:hover {{
                border: 1px solid {color};
            }}
        """)

class AdminDashboard(QWidget):
    def __init__(self, db_manager, memory_manager=None):
        super().__init__()
        self.db = db_manager
        self.memory = memory_manager
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        header = QLabel("🛡️ Hub do Administrador - Inteligência da Comunidade")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Colors.ACCENT_BLUE};")
        layout.addWidget(header)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid {Colors.BORDER_DEFAULT}; background: {Colors.BG_DEEP}; border-radius: 8px; }
            QTabBar::tab { background: {Colors.BG_CARD}; padding: 12px 25px; color: {Colors.TEXT_SECONDARY}; font-weight: bold; }
            QTabBar::tab:selected { background: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT}; border-bottom: 2px solid #fff; }
        """)
        
        # 0. Community Projects List (Existing logic moved here)
        self.curadoria_tab = QWidget()
        self.setup_curadoria_tab()
        self.tabs.addTab(self.curadoria_tab, "📋 Lista de Curadoria")

        # 1. Database Dashboard
        self.db_tab = QWidget()
        self.setup_db_tab()
        self.tabs.addTab(self.db_tab, "📊 Banco de Dados")
        
        # 2. Vector Intelligence
        self.vector_tab = QWidget()
        self.setup_vector_tab()
        self.tabs.addTab(self.vector_tab, "🧠 Memória Vetorial")
        
        # 3. Accuracy & Comprehension
        self.accuracy_tab = QWidget()
        self.setup_accuracy_tab()
        self.tabs.addTab(self.accuracy_tab, "🎯 Acurácia & IA")
        
        layout.addWidget(self.tabs)

    def setup_curadoria_tab(self):
        """Nova UI: Lista de Obras (Esq) | Abas Detalhes (Dir)"""
        main_layout = QHBoxLayout(self.curadoria_tab)
        main_layout.setContentsMargins(0,0,0,0)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # --- PAINEL ESQUERDO: Lista de Obras em Nuvem ---
        self.left_panel = QFrame()
        self.left_panel.setStyleSheet(f"background: {Colors.BG_PANEL}; border-right: 1px solid {Colors.BORDER_DEFAULT};")
        self.left_panel.setMinimumWidth(250)
        self.left_panel.setMaximumWidth(350)
        
        left_layout = QVBoxLayout(self.left_panel)
        
        lbl_works = QLabel("Obras em Nuvem")
        lbl_works.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {Colors.TEXT_SECONDARY}; margin-bottom: 5px;")
        left_layout.addWidget(lbl_works)
        
        self.list_cloud_works = QListWidget()
        self.list_cloud_works.setStyleSheet("""
            QListWidget { background: {Colors.BG_CARD}; border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 4px; padding: 5px; }
            QListWidget::item { padding: 10px; color: {Colors.TEXT_PRIMARY}; border-bottom: 1px solid {Colors.BORDER_DEFAULT}; }
            QListWidget::item:selected { background: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT}; border-radius: 4px; }
        """)
        self.list_cloud_works.itemClicked.connect(self.on_cloud_work_selected)
        left_layout.addWidget(self.list_cloud_works)
        
        btn_layout = QHBoxLayout()
        self.btn_refresh_cloud = QPushButton("🔄 Atualizar Lista")
        self.btn_refresh_cloud.setStyleSheet("""
            QPushButton { background: {Colors.BG_CARD}; color: {Colors.TEXT_BRIGHT}; border: 1px solid {Colors.BORDER_INPUT}; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background: {Colors.BORDER_INPUT}; }
        """)
        self.btn_refresh_cloud.clicked.connect(self.load_community_projects)
        btn_layout.addWidget(self.btn_refresh_cloud)
        
        self.btn_sync_full_work = QPushButton("☁️ Baixar Obra Completa")
        self.btn_sync_full_work.setToolTip("Baixa todos os itens desta obra para o PC local.")
        self.btn_sync_full_work.setStyleSheet("""
            QPushButton { background: rgba(26, 50, 75, 1); color: {Colors.ACCENT_PRIMARY}; border: 1px solid {Colors.ACCENT_PRIMARY}; padding: 6px; border-radius: 4px; font-weight: bold;}
            QPushButton:hover { background: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DEEP}; }
        """)
        self.btn_sync_full_work.clicked.connect(self.download_full_work)
        self.btn_sync_full_work.setVisible(False)
        btn_layout.addWidget(self.btn_sync_full_work)
        
        left_layout.addLayout(btn_layout)
        
        # --- PAINEL DIREITO: Abas da Obra Selecionada ---
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # Header da Obra
        self.lbl_selected_cloud_work = QLabel("Selecione uma Obra")
        self.lbl_selected_cloud_work.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {Colors.TEXT_BRIGHT};")
        right_layout.addWidget(self.lbl_selected_cloud_work)
        
        # Abas de Detalhes
        self.work_tabs = QTabWidget()
        self.work_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid {Colors.BORDER_DEFAULT}; background: {Colors.BG_DEEP}; }
            QTabBar::tab { background: {Colors.BG_PANEL}; color: {Colors.TEXT_SECONDARY}; padding: 8px 16px; margin-right: 2px; }
            QTabBar::tab:selected { background: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT}; }
        """)
        
        # Aba 1: Pavimentos (Cards)
        self.tab_cloud_projects = QWidget()
        self.tab_cloud_projects_layout = QVBoxLayout(self.tab_cloud_projects)
        
        self.cloud_scroll = QScrollArea()
        self.cloud_scroll.setWidgetResizable(True)
        self.cloud_scroll.setStyleSheet("background: transparent; border: none;")
        
        self.cloud_cards_container = QWidget()
        self.cloud_cards_layout = QGridLayout(self.cloud_cards_container)
        self.cloud_cards_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.cloud_cards_layout.setSpacing(15)
        
        self.cloud_scroll.setWidget(self.cloud_cards_container)
        self.tab_cloud_projects_layout.addWidget(self.cloud_scroll)
        
        self.work_tabs.addTab(self.tab_cloud_projects, "🏗️ Pavimentos")
        
        # Aba 2: Especificações Técnicas (ReadOnly)
        self.tab_cloud_specs = QWidget()
        self.specs_layout = QVBoxLayout(self.tab_cloud_specs)
        self.txt_cloud_specs = QTextEdit()
        self.txt_cloud_specs.setReadOnly(True)
        self.txt_cloud_specs.setStyleSheet(f"background: {Colors.BG_PANEL}; color: {Colors.TEXT_BRIGHT}; border: 1px solid {Colors.BORDER_DEFAULT}; padding: 10px;")
        self.txt_cloud_specs.setPlaceholderText("Selecione uma obra para ver as especificações globais.")
        self.specs_layout.addWidget(self.txt_cloud_specs)
        self.work_tabs.addTab(self.tab_cloud_specs, "📝 Especificações Técnicas")
        
        # Aba 3: Documentos (Lista Simples)
        self.tab_cloud_docs = QWidget()
        self.docs_layout = QVBoxLayout(self.tab_cloud_docs)
        self.list_cloud_docs = QListWidget()
        self.list_cloud_docs.setStyleSheet(f"background: {Colors.BG_PANEL}; color: {Colors.TEXT_BRIGHT}; border: 1px solid {Colors.BORDER_DEFAULT};")
        self.docs_layout.addWidget(self.list_cloud_docs)
        self.work_tabs.addTab(self.tab_cloud_docs, "📂 Documentos")
        
        right_layout.addWidget(self.work_tabs)
        
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setStretchFactor(1, 1)

    def on_cloud_work_selected(self, item):
        """Ao clicar numa obra na lista da esquerda."""
        work_name = item.data(Qt.UserRole)
        self.lbl_selected_cloud_work.setText(f"🏢 {work_name}")
        self.btn_sync_full_work.setVisible(True)
        
        # Filtrar projetos desta obra
        filtered_projects = [p for p in self.all_cloud_projects 
                             if p.get('metadata', {}).get('work_name') == work_name]
        
        # 1. Popular Cards de Pavimentos
        for i in reversed(range(self.cloud_cards_layout.count())):
            widget = self.cloud_cards_layout.itemAt(i).widget()
            if widget: widget.setParent(None)
            
        row, col = 0, 0
        max_cols = 3
        
        aggregated_specs = ""
        aggregated_docs = []
        
        # Primeiro loop para coletar dados e criar cards
        for p in filtered_projects:
            card = CuradoriaCard(p)
            card.train_requested.connect(self.import_for_training)
            card.details_requested.connect(self.open_project_details)
            card.sync_requested.connect(self.handle_sync_request)
            self.cloud_cards_layout.addWidget(card, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
            
            # Coletar especificações de pavimentos
            p_specs = p.get('metadata', {}).get('specifications', '') or ''
            if p_specs:
                aggregated_specs += f"--- {p.get('project_name')} ---\n{p_specs}\n\n"
            
            # Coletar documentos
            w_docs = p.get('metadata', {}).get('work_documents', [])
            for wd in w_docs:
                if wd not in aggregated_docs: aggregated_docs.append(wd)

        # 2. Popular Specs - Priorizando Informação da Obra
        work_info_text = "Nenhuma especificação estrutural da obra encontrada."
        for p in filtered_projects:
            w_info = p.get('metadata', {}).get('work_info')
            if w_info:
                specs = w_info.get('specs') or ""
                work_info_text = f"📊 ESPECIFICAÇÕES TÉCNICAS DA OBRA:\n"
                work_info_text += "--------------------------------\n"
                work_info_text += f"🏗️ PAVIMENTOS: {w_info.get('pavements') or '--'}\n"
                work_info_text += f"🏢 TORRES: {w_info.get('towers') or '--'}\n"
                work_info_text += f"🟦 TOTAL PILARES: {w_info.get('total_pilares') or '--'}\n"
                work_info_text += f"🟩 TOTAL VIGAS: {w_info.get('total_vigas') or '--'}\n"
                work_info_text += f"🟪 TOTAL LAJES: {w_info.get('total_lajes') or '--'}\n\n"
                work_info_text += f"📝 NOTAS TÉCNICAS GERAIS:\n{specs if specs else 'Nenhuma nota adicional.'}\n"
                break
        
        self.txt_cloud_specs.setText(work_info_text)
        
        if aggregated_specs:
             self.txt_cloud_specs.append("\n" + "="*40 + "\n📜 NOTAS POR PAVIMENTO:\n\n" + aggregated_specs)
        
        # 3. Popular Documentos
        self.list_cloud_docs.clear()
        if aggregated_docs:
            for d in aggregated_docs:
                self.list_cloud_docs.addItem(f"📄 {d.get('name', 'Sem Nome')} ({d.get('category', 'Geral')})")
        else:
             self.list_cloud_docs.addItem("Nenhum documento de obra sincronizado.")
             self.list_cloud_docs.addItem("Nenhum documento de obra sincronizado.")

    def download_full_work(self):
        """Baixa a obra completa selecionada."""
        item = self.list_cloud_works.currentItem()
        if not item: return
        work_name = item.data(Qt.UserRole)
        
        reply = QMessageBox.question(self, "Baixar Obra Completa", 
            f"Deseja baixar TODOS os dados da obra '{work_name}'?\nIsso pode sobrescrever dados locais se já existirem.",
            QMessageBox.Yes | QMessageBox.No)
            
        if reply == QMessageBox.Yes:
            # Reutiliza a lógica de sync individual num loop
            projects = [p for p in self.all_cloud_projects 
                        if p.get('metadata', {}).get('work_name') == work_name]
            
            success_count = 0
            for p in projects:
                # Mockando o objeto project_data para o handler
                try:
                    self.handle_sync_request(p)
                    success_count += 1
                except Exception as e:
                    print(f"Erro ao baixar {p.get('project_name')}: {e}")
            
            QMessageBox.information(self, "Concluído", f"{success_count}/{len(projects)} itens processados.")

    def setup_db_tab(self):
        layout = QVBoxLayout(self.db_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Area de Rolagem para o Pipeline (pode ser longo)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        self.pipeline_view = DataPipelineView()
        scroll.setWidget(self.pipeline_view)
        
        layout.addWidget(scroll)

    def setup_vector_tab(self):
        layout = QVBoxLayout(self.vector_tab)
        self.vector_info = QLabel("Calculando volume de embeddings...")
        self.vector_info.setWordWrap(True)
        layout.addWidget(self.vector_info)
        
        self.vector_chart_view = QChartView()
        layout.addWidget(self.vector_chart_view)

    def setup_accuracy_tab(self):
        layout = QVBoxLayout(self.accuracy_tab)
        
        info = QLabel("Compreensão do Sistema: Como a IA interpreta os vínculos estruturais.")
        info.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        layout.addWidget(info)
        
        # Strategic Summary
        self.lbl_explanation = QLabel("Carregando análise estratégica...")
        self.lbl_explanation.setStyleSheet(f"background: {Colors.BG_CARD}; padding: 15px; border-radius: 8px; color: {Colors.TEXT_PRIMARY};")
        self.lbl_explanation.setWordWrap(True)
        layout.addWidget(self.lbl_explanation)
        
        self.accuracy_chart_view = QChartView()
        layout.addWidget(self.accuracy_chart_view)

    def refresh_data(self):
        stats = self.db.get_admin_stats()
        accuracy = self.db.get_accuracy_report()
        
        # Update Data Pipeline
        self.pipeline_view.refresh(stats)

        # Update Vector Dashboard
        if self.memory:
            local_count = 0
            if self.memory.local_collection:
                local_count = self.memory.local_collection.count()
            
            global_count = 0
            if self.memory.global_collection:
                global_count = self.memory.global_collection.count()
                
            self.vector_info.setText(f"Inteligência Distribuída: {local_count} embeddings locais | {global_count} globais.")
            
            pie = QPieSeries()
            pie.append("Local Intelligence", local_count)
            pie.append("Global Experience", global_count)
            
            v_chart = QChart()
            v_chart.addSeries(pie)
            v_chart.setTitle("Distribuição de Peso da Memória")
            v_chart.setBackgroundVisible(False)
            v_chart.setTitleBrush(QColor(Colors.TEXT_BRIGHT))
            self.vector_chart_view.setChart(v_chart)

        # Accuracy Explanation
        explanation = (
            "<b>Estratégia de Compreensão:</b><br><br>"
            "1. <b>Vínculos Pilar-Viga:</b> A IA utiliza um raio de busca dinâmico (800px base) ajustado por 'Learned Offsets'. "
            "Se o sistema detecta falha repetitiva em um pilar específico, o vetor de 'DNA' é atualizado globalmente.<br>"
            "2. <b>Vetores de Atributos:</b> Cada campo (ex: Seção, Nome) possui um slot de confiança. "
            "Atualmente, a taxa de acerto em nomes de vigas é a mais alta devido à padronização de prefixos.<br>"
            "3. <b>Feedback Loop:</b> Toda validação manual alimenta o ChromaDB, refinando a similaridade de cosseno para futuros projetos."
        )
        self.lbl_explanation.setText(explanation)
        
        # Accuracy Chart
        a_series = QPieSeries()
        success = sum(a['count'] for a in accuracy if a['status'] == 'valid')
        errors = sum(a['count'] for a in accuracy if a['status'] == 'error')
        
        a_series.append("Acertos Confirmados", success)
        a_series.append("Ajustes Manuais", errors)
        
        a_chart = QChart()
        a_chart.addSeries(a_series)
        a_chart.setTitle("Taxa de Precisão da IA (Active Learning)")
        a_chart.setBackgroundVisible(False)
        a_chart.setTitleBrush(QColor(Colors.TEXT_BRIGHT))
        self.accuracy_chart_view.setChart(a_chart)

    def import_for_training(self, project_id, total_items_fallback):
        """Simula a importação para treino e atualiza o banco com estatísticas reais (Itens e Links)."""
        print(f"Importing project {project_id} for training...")
        
        from src.core.services.sync_service import SyncService
        from datetime import datetime
        
        try:
            sync = SyncService()
            
            # 1. Fetch current full metadata
            res = sync.supabase.table("cloud_projects").select("metadata").eq("id", project_id).single().execute()
            current_meta = res.data.get('metadata') or {}
            
            # 2. Calculate Stats using robust helper
            stats = self._calculate_project_stats(current_meta)
            print(f"Stats Calculated: {stats}")

            # 3. Update Metadata
            current_meta['last_training_at'] = datetime.now().isoformat()
            
            # Updated Stats Block (New Standard)
            current_meta['stats'] = stats
            
            # Legacy fields for backward compat
            current_meta['training_items_count'] = stats['total_items']
            current_meta['fully_validated_count'] = stats['finished_items']
            current_meta['partially_validated_count'] = stats['started_items']
            
            # 4. Push update
            sync.supabase.table("cloud_projects").update({"metadata": current_meta}).eq("id", project_id).execute()
            
            # Refresh UI
            self.load_community_projects()
            print(f"Training metadata updated for {project_id}")
            
        except Exception as e:
            print(f"Error importing: {e}")
            import traceback
            traceback.print_exc()

    def _calculate_project_stats(self, meta: dict) -> dict:
        """
        Calcula estatísticas detalhadas de progresso para usar nos cards.
        Retorna: {
            'total_items', 'started_items', 'finished_items', 
            'total_links_expected', 'total_links_validated'
        }
        """
        pillars = meta.get('pillars', []) or []
        beams = meta.get('beams', []) or []
        slabs = meta.get('slabs', []) or []
        
        all_items = pillars + beams + slabs
        total_items = len(all_items)
        
        started_items = 0
        finished_items = 0
        
        total_links_expected = 0
        total_links_validated = 0
        
        for item in all_items:
            # Heuristic Type Detection & Expected Fields
            itype = 'pillar'
            if 'points' in item and 'section' not in item: itype = 'slab'
            elif 'section' not in item: itype = 'beam'
            
            # Estimated Field Counts (se não tiver schema)
            expected = 10 
            if itype == 'pillar': expected = 12
            elif itype == 'slab': expected = 6
            elif itype == 'beam': expected = 15
            
            total_links_expected += expected
            
            # Count validated + NA fields
            v_fields = item.get('validated_fields', {})
            na_fields = item.get('na_fields', {})
            
            # Unique valid/NA keys
            done_keys = set(v_fields.keys()) | set(na_fields.keys())
            count_done = len(done_keys)
            
            total_links_validated += count_done
            
            # Determine Status
            # Finished: Explicito E todos campos
            is_explicit_finish = item.get('is_fully_validated', False)
            
            # Regra: Se tiver explicitamente marcado como validado OU (se tiver campos suficientes e não for recém criado)
            # Usuário pediu: "tem todos os campos validados/naose aplica ja configurados considerado ja feito 100%"
            if is_explicit_finish or count_done >= expected:
                finished_items += 1
                # FIX: Legacy items might lack fields but be validated. Force link count to 100%
                if count_done < expected:
                    total_links_validated += (expected - count_done) if (expected - count_done) > 0 else 0

            # Inclusive Started: If it has progress OR is finished, it counts as Started
            if count_done > 0 or is_explicit_finish:
                started_items += 1
                
        return {
            'total_items': total_items,
            'started_items': started_items,
            'finished_items': finished_items,
            'total_links_expected': total_links_expected,
            'total_links_validated': total_links_validated
        }

    def _create_progress_bar(self, value: int, total: int, color_full=Colors.ACCENT_PRIMARY, color_partial=Colors.ACCENT_SUCCESS):
        """Helper para criar barra de progresso com texto 'Val / Total'"""
        pct = 0
        if total > 0:
            pct = (value / total) * 100
        
        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(int(pct))
        pbar.setFormat(f"{value}/{total} ({int(pct)}%)")
        pbar.setAlignment(Qt.AlignCenter)
        
        # Cor baseada na completude (Azul se 100%, Verde se parcial)
        chunk_color = color_full if pct >= 100 else color_partial
        
        pbar.setStyleSheet(f"""
            QProgressBar {{ 
                border: 0px; border-radius: 2px; text-align: center; color: {Colors.TEXT_BRIGHT}; background: {Colors.BG_CARD};
                font-size: 10px; font-weight: bold;
            }}
            QProgressBar::chunk {{ 
                background-color: {chunk_color}; 
            }}
        """)
        return pbar

    def load_community_projects(self):
        """Busca projetos da nuvem e agrupa por obras."""
        self.list_cloud_works.clear()
        self.btn_sync_full_work.setVisible(False)
        self.lbl_selected_cloud_work.setText("Selecione uma Obra")
        
        # Limpar cards
        for i in reversed(range(self.cloud_cards_layout.count())):
            self.cloud_cards_layout.itemAt(i).widget().setParent(None)
        
        try:
            from src.core.services.sync_service import SyncService
            sync = SyncService()
            self.all_cloud_projects = sync.list_community_projects()
        except Exception as e:
            print(f"Erro ao buscar projetos da nuvem: {e}")
            self.all_cloud_projects = []
            
        # Agrupar Obras Únicas
        works = set()
        for p in self.all_cloud_projects:
            # Processar Stats (mesma lógica de antes, mantida para garantir cards ricos)
            self._enrich_project_stats(p)
            
            meta = p.get('metadata') or {}
            w_name = meta.get('work_name') or "Sem Obra"
            logging.info(f"[DEBUG] Found Cloud Work: {w_name} (Project ID: {p.get('id')})")
            works.add(w_name)
            
        # Popular Lista Esquerda
        for w in sorted(list(works)):
            item = QListWidgetItem(f"🏢 {w}")
            item.setData(Qt.UserRole, w)
            self.list_cloud_works.addItem(item)

    def _enrich_project_stats(self, p):
        """Helper para calcular stats se faltarem no JSON."""
        try:
            meta = p.get('metadata', {}) or {}
            p['metadata'] = meta # Ensure exist
            
            # Recalculate stats if possible to ensure consistency
            if 'pillars' in meta or 'beams' in meta or 'slabs' in meta:
                 meta['stats'] = self._calculate_project_stats(meta)
            
            stats = meta.get('stats', {})
            
            # Fallback Doc Stats se não vier do servidor
            if 'doc_stats' not in meta:
                 meta['doc_stats'] = { "ESTRUTURAL": 0, "DETALHES E VISÕES DE CORTES": 0, "PILARES": 0, "LATERAIS DE VIGAS": 0, "LAJES": 0 }
        except Exception as e:
            print(f"Error enriching stats: {e}")

    def open_project_details(self, project_data):
        """Abre a ficha técnica do projeto"""
        # Se for necessário buscar dados completos (caso o list não traga o JSON completo de pillars/etc)
        # Por enquanto assumimos que 'project_data' tem o que precisamos ou buscaremos sob demanda.
        
        # O 'list_community_projects' traz tudo (*), então 'project_data' deve ter metadata completo.
        try:
            dialog = ProjectDetailsDialog(project_data, self)
            dialog.exec()
        except Exception as e:
            print(f"Erro ao abrir ficha técnica: {e}")
            import traceback
            traceback.print_exc()

    def handle_sync_request(self, project_data: dict):
        """
        Lida com o pedido de 'Sincronizar' (Baixar) do CuradoriaCard.
        Verifica se o projeto existe localmente. Se não, baixa.
        Verifica se a Obra existe localmente. Se não, cria.
        """
        try:
            print(f"Iniciando Download/Sync do projeto {project_data.get('id')}...")
            project_id = project_data.get('id')
            project_name = project_data.get('project_name')
            storage_path = project_data.get('storage_path')
            
            meta = project_data.get('metadata', {})
            work_name = meta.get('work_name') or "Sem Obra"
            client_email = meta.get('user_email')
            
            # 1. Verificar se já existe Local
            local_proj = self.db.get_project_by_id(project_id)
            if local_proj:
                print(f"Projeto [{project_name}] já existe localmente (ID: {project_id}).")
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Já existe", f"O projeto '{project_name}' já está na sua base local.")
                return

            print(f"Projeto não encontrado localmente. Baixando de {storage_path}...")
            
            # 2. Baixar JSON da Nuvem (SyncService)
            from src.core.services.sync_service import SyncService
            sync_service = SyncService()
            
            full_data_json = sync_service.download_project(storage_path)
            
            if not full_data_json:
                print(f"Erro: Falha ao baixar ou JSON inválido para {storage_path}")
                return

            print("Download concluído. Processando estrutura...")

            # 3. Garantir que a Obra Exista Localmente
            conn = self.db._get_conn()
            try:
                cur = conn.execute("SELECT name FROM works WHERE name = ?", (work_name,))
                if not cur.fetchone():
                    print(f"Obra '{work_name}' não existe localmente. Criando...")
                    client_id = None
                    if client_email:
                        cur_cli = conn.execute("SELECT id FROM clients WHERE email = ?", (client_email,))
                        row_cli = cur_cli.fetchone()
                        if row_cli:
                            client_id = row_cli[0]
                    self.db.create_work(work_name, client_id)
                else:
                    print(f"Obra '{work_name}' já existe. Vinculando.")
            finally:
                conn.close()

            # 4. Importar Projeto Completo (Mantendo ID Original)
            if 'project' in full_data_json:
                 full_data_json['project']['id'] = project_id 
                 full_data_json['project']['work_name'] = work_name

            new_local_id = self.db.import_project_data(full_data_json)
            
            if new_local_id == project_id:
                print(f"Sucesso! Projeto '{project_name}' importado com ID original {new_local_id}")
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Sucesso", f"Projeto '{project_name}' baixado com sucesso!")
                self.load_community_projects()
            else:
                print(f"Aviso: Projeto importado mas ID mudou? {new_local_id} != {project_id}")

        except Exception as e:
            print(f"Erro no fluxo de Download: {e}")
            import traceback
            traceback.print_exc()
