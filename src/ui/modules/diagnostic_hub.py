import os
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFrame
from src.ui.components.organisms import DiagnosticSidebar, TechSheetPanel
from src.ui.canvas import CADCanvas
from src.core.services.data_coordinator import get_coordinator

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
        
        layout.addWidget(canvas_container, 1) # Stretch factor 1
        
        # 3. Tech Panel (Direita)
        self.tech_panel = TechSheetPanel()
        self.tech_panel.filter_requested.connect(self._on_filter_requested)
        self.tech_panel.extract_requested.connect(self._on_extract_requested)
        layout.addWidget(self.tech_panel)
        
        # Connect Signals
        self.coordinator.project_changed.connect(self._on_project_changed)
        self.coordinator.work_changed.connect(lambda _: self.sidebar.refresh())

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
        
        # Se for um DXF (esperado), carregar no canvas usando worker
        if file_path.lower().endswith('.dxf'):
            # Preparar UI de carregamento (opcional: spinner)
            self.canvas.set_loading(True) # Assumes Canvas has a generic loading state or overlay
            
            from src.ui.workers import DXFLoadWorker
            
            # Setup Thread
            self.thread = QThread()
            self.worker = DXFLoadWorker(file_path, use_cache=True)
            self.worker.moveToThread(self.thread)
            
            # Connect Signals
            self.thread.started.connect(self.worker.run)
            self.worker.finished.connect(lambda data, dur: self._on_dxf_loaded(data, dur, doc_data))
            self.worker.error.connect(self._on_dxf_error)
            
            # Cleanup
            self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)
            self.worker.error.connect(self.thread.quit)
            self.worker.error.connect(self.worker.deleteLater)
            
            # Start
            self.thread.start()
            
    def _on_dxf_loaded(self, dxf_data, duration, doc_data):
        """Callback de sucesso do carregamento."""
        print(f"[DiagnosticHub] DXF carregado em {duration:.2f}s")
        if dxf_data:
            self.canvas.add_dxf_entities(dxf_data)
        
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

    
    def _on_filter_requested(self, f_type, f_value):
        """Aplica filtros no Canvas."""
        self.canvas.apply_filter(f_type, f_value)
        
    def _on_extract_requested(self, mode):
        """
        Extrai itens selecionados do Canvas e salva como novo documento na Fase 2.
        Mode: 'clean' (Estrutural Limpo) ou 'detail' (Detalhamento Específico)
        """
        entities = self.canvas.get_selected_entities()
        if not entities:
            print("[DiagnosticHub] Nenhuma entidade selecionada para extração.")
            return
            
        print(f"[DiagnosticHub] Extraindo {len(entities)} entidades. Modo: {mode}")
        
        # Determinar categoria
        if mode == 'clean':
            category = "Estruturais Pavimentos Limpos"
            suffix = "_clean"
        else:
            category = "Detalhamentos Específicos"
            suffix = "_detail"
            
        # Nomear arquivo
        # Tenta pegar project_id do coordenador ou assume 'temp'
        pid = self.coordinator._current_project
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
            # TODO: Melhorar cloning exato usando ezdxf se possível, mas aqui usamos os metadados do canvas
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
            save_dir = os.path.join(os.getcwd(), "storage", "documents", pid)
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, filename)
            
            new_doc.saveas(save_path)
            
            # Salvar no Banco
            self.db.save_document(
                project_id=pid,
                name=f"Extração {mode.capitalize()} ({len(entities)} ents)",
                file_path=save_path,
                extension=".dxf",
                phase=2,
                category=category
            )
            
            print(f"[DiagnosticHub] Extração salva em: {save_path}")
            # Opcional: Atualizar lista no TechSheet
            
        except Exception as e:
            print(f"[DiagnosticHub] Erro na extração: {e}")
            import traceback
            traceback.print_exc()

    def _on_project_changed(self, pid, pname):
        print(f"[DiagnosticHub] Project Switched: {pname}")
        # Recarregar sidebar para garantir sincronia
        self.sidebar.refresh()
