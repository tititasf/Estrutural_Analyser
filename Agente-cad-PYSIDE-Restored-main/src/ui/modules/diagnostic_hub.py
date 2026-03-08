import os
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QFrame,
                               QDialog, QDialogButtonBox, QRadioButton, 
                               QButtonGroup, QLabel, QMessageBox, QPushButton, QScrollArea)
from PySide6.QtCore import QThread
from src.ui.components.organisms import DiagnosticSidebar, TechSheetPanel
from src.ui.canvas import CADCanvas
from src.core.dxf_loader import RenderMode
from src.core.services.data_coordinator import get_coordinator


class RenderModeDialog(QDialog):
    """Diálogo para seleção de modo de renderização."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modo de Renderização")
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selecione a Estratégia de Limpeza (V1 - V20):"))
        
        # Scroll Area para muitos modos
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        self.button_group = QButtonGroup(self)
        
        modes = [
            (RenderMode.TRUE_GEOMETRY, "1. True Geometry", "Original sem filtros."),
            (RenderMode.EDGE_CLEANER, "2. Edge Cleaner", "Remove ruído e micro-segmentos."),
            (RenderMode.COLOR_BASIC, "3. Color Basic (1-4)", "SÓ Vermelho, Amarelo, Verde e Ciano."),
            (RenderMode.COLOR_EXTENDED, "4. Color Extended (1-7)", "Adiciona Azul, Magenta e Branco."),
            (RenderMode.COLOR_LAYERS, "5. Color + Whitelist", "Cores 1-4 + Filtro de Camadas (Pilar/Viga)."),
            (RenderMode.COLOR_ORTHO, "6. Color + Ortho", "Cores 1-4 + Somente Retas (H/V)."),
            (RenderMode.COLOR_FLATTEN, "7. Color + Flatten", "Cores 1-4 + Achatamento Z (Purga Links)."),
            (RenderMode.COLOR_BLOCKS, "8. Color + Blocks", "Cores 1-4 + Limpeza Interna de Blocos."),
            (RenderMode.COLOR_FAN, "9. Color + Global Purge", "Cores 1-4 + Detector de Leques Global."),
            (RenderMode.COLOR_OMEGA, "10. OMEGA COLOR", "Estratégia Definitiva Combinada."),
        ]
        
        for i, (mode, name, desc) in enumerate(modes):
            radio = QRadioButton(f"<b>{name}</b><br><font color='gray'>{desc}</font>")
            radio.setProperty("mode", mode)
            if i == 0:
                radio.setChecked(True)
            self.button_group.addButton(radio, i)
            scroll_layout.addWidget(radio)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.resize(400, 500)
        
    def get_selected_mode(self):
        checked = self.button_group.checkedButton()
        return checked.property("mode") if checked else RenderMode.TRUE_GEOMETRY


class DiagnosticHubModule(QWidget):
    """
    Página Principal do Módulo de Diagnóstico (Pré-Processamento).
    Layout: [Sidebar] [Canvas] [TechPanel]
    """
    def __init__(self, db=None):
        super().__init__()
        self.db = db
        self.coordinator = get_coordinator()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. Sidebar (Esquerda)
        self.sidebar = DiagnosticSidebar(db=self.db)
        self.sidebar.document_selected.connect(self._on_document_selected)
        layout.addWidget(self.sidebar)
        
        # 2. Canvas Center (Meio)
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0,0,0,0)
        
        self.canvas = CADCanvas()
        canvas_layout.addWidget(self.canvas)
        
        # [NOVO] Barra de ferramentas para troca de "Bibliotecas" de Texto
        style_toolbar = QHBoxLayout()
        style_toolbar.setContentsMargins(5, 5, 5, 5)
        style_toolbar.addWidget(QLabel("<b>Biblioteca de Texto:</b>"))
        
        for i in [1, 3]:
            btn = QPushButton(f"Estilo {i}")
            btn.setFixedWidth(80)
            btn.clicked.connect(lambda checked, idx=i: self._on_style_changed(idx))
            style_toolbar.addWidget(btn)
        
        style_toolbar.addSpacing(20)
        
        # [NOVO] Botão Selecionar Similares
        self.btn_similar = QPushButton("Selecionar Similares")
        self.btn_similar.setStyleSheet("background-color: #0d47a1; color: white; border-radius: 4px; padding: 4px 12px; font-weight: bold;")
        self.btn_similar.clicked.connect(self.canvas.select_similar)
        style_toolbar.addWidget(self.btn_similar)
        
        style_toolbar.addStretch()
        canvas_layout.addLayout(style_toolbar)
        
        layout.addWidget(canvas_container, 1) # Stretch factor 1
        
        # 3. Tech Panel (Direita)
        self.tech_panel = TechSheetPanel()
        self.tech_panel.filter_requested.connect(self._on_filter_requested)
        self.tech_panel.extract_requested.connect(self._on_extract_requested)
        layout.addWidget(self.tech_panel)
        
        # Connect Signals
        self.coordinator.project_changed.connect(self._on_project_changed)
        self.coordinator.work_changed.connect(lambda _: self.sidebar.refresh())

        # Thread State Management
        self._load_thread = None
        self._load_worker = None
        self._current_doc_data = None

    def set_database(self, db):
        self.db = db
        self.sidebar.set_database(db)
        
    def _on_document_selected(self, doc_data):
        """Carrega o documento selecionado no Canvas."""
        file_path = doc_data.get('file_path')
        if not file_path or not os.path.exists(file_path):
            print(f"[DiagnosticHub] Arquivo não encontrado: {file_path}")
            return
            
        print(f"[DiagnosticHub] Carregando Documento: {doc_data.get('name')}")
        
        # Prevent multiple threads running - ROBUST CHECK
        try:
            if self._load_thread and self._load_thread.isRunning():
                print("[DiagnosticHub] Thread already running, ignoring request.")
                return
        except (RuntimeError, AttributeError):
            # Se cair aqui, o objeto C++ foi deletado mas a ref Python resiste
            self._cleanup_thread()

        ext = file_path.lower()
        
        # --- CARREGAMENTO DXF ---
        if ext.endswith('.dxf'):
            # [NEW] Diálogo de seleção de modo de renderização
            dialog = RenderModeDialog(self)
            if dialog.exec() != QDialog.Accepted:
                return  # Usuário cancelou
            
            render_mode = dialog.get_selected_mode()
            doc_data['render_mode'] = render_mode
            print(f"[DiagnosticHub] Modo selecionado: {render_mode.name}")
            
            self.canvas.set_loading(True)
            from src.ui.workers import DXFLoadWorker
            
            # Setup Thread
            self._load_thread = QThread()
            self._load_worker = DXFLoadWorker(file_path, doc_data=doc_data, use_cache=True)
            self._load_worker.moveToThread(self._load_thread)
            
            # Connect Signals
            self._load_thread.started.connect(self._load_worker.run)
            self._load_worker.finished.connect(self._on_dxf_loaded)
            self._load_worker.error.connect(self._on_dxf_error)
            
            # Robust Cleanup
            self._load_worker.finished.connect(self._load_thread.quit)
            self._load_worker.finished.connect(self._load_worker.deleteLater)
            self._load_worker.error.connect(self._load_thread.quit)
            self._load_worker.error.connect(self._load_worker.deleteLater)
            
            # Ensure thread deletion and reference cleanup only after real thread termination
            self._load_thread.finished.connect(self._cleanup_thread)
            self._load_thread.finished.connect(self._load_thread.deleteLater)
            
            self._load_thread.start()

        # --- CARREGAMENTO PDF ---
        elif ext.endswith('.pdf'):
            self.canvas.set_loading(True)
            from src.ui.workers import PDFLoadWorker
            
            # Setup Thread
            self._load_thread = QThread()
            self._load_worker = PDFLoadWorker(file_path, doc_data=doc_data)
            self._load_worker.moveToThread(self._load_thread)
            
            # Connect Signals
            self._load_thread.started.connect(self._load_worker.run)
            self._load_worker.finished.connect(self._on_pdf_loaded)
            self._load_worker.error.connect(self._on_dxf_error) # Compartilha handler de erro
            
            # Robust Cleanup
            self._load_worker.finished.connect(self._load_thread.quit)
            self._load_worker.finished.connect(self._load_worker.deleteLater)
            self._load_worker.error.connect(self._load_thread.quit)
            self._load_worker.error.connect(self._load_worker.deleteLater)
            
            self._load_thread.finished.connect(self._cleanup_thread)
            self._load_thread.finished.connect(self._load_thread.deleteLater)
            
            self._load_thread.start()
            
    def _cleanup_thread(self):
        """Limpa referências Python para evitar RuntimeError no próximo acesso."""
        self._load_thread = None
        self._load_worker = None

    def _on_pdf_loaded(self, images, duration, doc_data):
        """Callback de sucesso do carregamento de PDF."""
        print(f"[DiagnosticHub] PDF carregado ({len(images)} páginas) em {duration:.2f}s")
        self._current_doc_data = doc_data
        
        # Exibir no Canvas
        if images:
            self.canvas.add_pdf_pages(images)
            
        self.canvas.set_loading(False)
            
    def _on_dxf_loaded(self, dxf_data, duration, doc_data):
        """Callback de sucesso do carregamento de DXF."""
        render_mode = doc_data.get('render_mode', RenderMode.TRUE_GEOMETRY)
        print(f"[DiagnosticHub] DXF carregado em {duration:.2f}s (Modo: {render_mode.name})")
        
        # Armazenar dados do documento ativo para uso em extrações
        self._current_doc_data = doc_data
        
        if dxf_data:
            self.canvas.add_dxf_entities(dxf_data, render_mode=render_mode, compute_snaps=False)
            print("[DiagnosticHub] LITE MODE: Snaps e Metadados desativados para performance.")
        
        # Atualizar filtros dinâmicos no painel lateral
        if hasattr(self.canvas, 'dxf_metadata'):
            self.tech_panel.update_dynamic_filters(self.canvas.dxf_metadata)
        
        # Notificar coordenador se tiver project_id (para vincular metadados)
        if doc_data.get('project_id'):
            self.coordinator.set_project(doc_data['project_id'], doc_data.get('name'))
            
        self.canvas.set_loading(False)

    def _on_dxf_error(self, err_msg):
        print(f"[DiagnosticHub] Erro no carregamento: {err_msg}")
        self.canvas.set_loading(False)
        
        # [NEW] Feedback visual para erro no arquivo
        QMessageBox.critical(
            self,
            "Erro de Carregamento",
            f"Não foi possível carregar o arquivo DXF.\n\nDetalhes: {err_msg}\n\nO arquivo pode estar corrompido ou em um formato incompatível."
        )

    
    def _on_style_changed(self, style_id):
        """Relata a troca de estilo para o Canvas."""
        self.canvas.switch_text_style(style_id)
        
    def _on_filter_requested(self, f_type, f_value):
        """Aplica filtros no Canvas."""
        self.canvas.apply_filter(f_type, f_value)
        
    def _on_extract_requested(self, mode):
        """
        Extrai itens selecionados do Canvas e salva como novo documento.
        Mode: 'clean' (Estrutural Limpo), 'detail' (Detalhamento) ou 'finalized' (Recortes Finalizados)
        """
        entities = self.canvas.get_selected_entities()
        if not entities:
            print("[DiagnosticHub] Nenhuma entidade selecionada para extração.")
            return
            
        print(f"[DiagnosticHub] Extraindo {len(entities)} entidades. Modo: {mode}")
        
        # Determinar categoria e sufixo
        if mode == 'clean':
            category = "Estruturais Pavimentos Limpos"
            suffix = "_clean"
            phase = 2
        elif mode == 'detail':
            category = "Detalhamentos Específicos"
            suffix = "_detail"
            phase = 2
        elif mode == 'finalized':
            category = "Recortes de Itens Finalizados"
            suffix = "_finalized"
            phase = 3
        else:
            print(f"[DiagnosticHub] Modo desconhecido: {mode}")
            return
        
        # Para 'finalized', usar a obra do DXF ativo (não o projeto global)
        if mode == 'finalized' and hasattr(self, '_current_doc_data') and self._current_doc_data:
            doc_data = self._current_doc_data
            work_name = doc_data.get('work_name')
            pid = doc_data.get('project_id')
            
            # Se não tem project_id direto, buscar pelo work_name
            if not pid and work_name:
                projects = self.db.get_projects()
                for p in projects:
                    if p.get('work_name') == work_name:
                        pid = p['id']
                        break
            
            # Diretório local para clips
            save_dir = os.path.join(os.getcwd(), "storage", "clips", work_name or "temp")
        else:
            pid = self.coordinator._current_project
            save_dir = os.path.join(os.getcwd(), "storage", "documents", pid or "temp")
        
        if not pid:
            print("[DiagnosticHub] ERRO: Nenhum projeto ativo para salvar extração.")
            return
            
        # Gerar DXF Físico
        import ezdxf
        import uuid
        
        try:
            new_doc = ezdxf.new()
            msp = new_doc.modelspace()
            
            # Copiar entidades (simplificado: recria based on stored data)
            for ent in entities:
                etype = ent.get('type')
                if etype == 'line':
                    p1, p2 = ent['points']
                    msp.add_line(p1, p2)
                elif etype == 'circle':
                    msp.add_circle(ent['center'], ent['radius'])
                # Adicionar outros tipos conforme necessário
                
            # Salvar Arquivo
            filename = f"extract_{uuid.uuid4().hex[:6]}{suffix}.dxf"
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, filename)
            
            new_doc.saveas(save_path)
            
            # Salvar no Banco
            self.db.save_document(
                project_id=pid,
                name=f"Extração {mode.capitalize()} ({len(entities)} ents)",
                file_path=save_path,
                extension=".dxf",
                phase=phase,
                category=category
            )
            
            print(f"[DiagnosticHub] Extração salva em: {save_path}")
            
            # Atualizar lista correspondente no TechPanel
            if mode == 'clean':
                self.tech_panel.list_clean_struct.addItem(filename)
            elif mode == 'detail':
                self.tech_panel.list_details.addItem(filename)
            elif mode == 'finalized':
                self.tech_panel.list_finalized.addItem(filename)
            
        except Exception as e:
            print(f"[DiagnosticHub] Erro na extração: {e}")
            import traceback
            traceback.print_exc()

    def _on_project_changed(self, pid, pname):
        print(f"[DiagnosticHub] Project Switched: {pname}")
        # Recarregar sidebar para garantir sincronia
        self.sidebar.refresh()
