
import os
import pickle
import time
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage
try:
    import fitz # PyMuPDF
except ImportError:
    fitz = None

from src.core.dxf_loader import DXFLoader, RenderMode

class DXFLoadWorker(QObject):
    """
    Worker para carregar arquivos DXF em background.
    """
    finished = Signal(dict, float, dict) # entities, duration, doc_data
    error = Signal(str)
    
    def __init__(self, file_path, doc_data=None, use_cache=True):
        super().__init__()
        self.file_path = file_path
        self.doc_data = doc_data or {}
        self.use_cache = use_cache
        
    @Slot()
    def run(self):
        try:
            start_time = time.time()
            data = None
            
            # Obtém o modo de renderização solicitado
            mode = self.doc_data.get('render_mode', RenderMode.TRUE_GEOMETRY)
            
            # 1. Tentar Cache (.pkl) - Adicionado sufixo do modo para evitar colisões
            cache_path = self.file_path + f".{mode.name}.pkl"
            
            if self.use_cache and os.path.exists(cache_path):
                dxf_mtime = os.path.getmtime(self.file_path)
                pkl_mtime = os.path.getmtime(cache_path)
                if pkl_mtime > dxf_mtime:
                    try:
                        with open(cache_path, 'rb') as f:
                            data = pickle.load(f)
                    except: pass

            # 2. Se não carregou do cache, carregar do DXF passando o modo
            if not data:
                data = DXFLoader.load_dxf(self.file_path, mode=mode)
                
                if data and self.use_cache:
                    try:
                        with open(cache_path, 'wb') as f:
                            pickle.dump(data, f)
                    except: pass

            duration = time.time() - start_time
            
            if data:
                self.finished.emit(data, duration, self.doc_data)
            else:
                self.error.emit("Falha ao carregar dados do DXF (retorno vazio).")
                
        except Exception as e:
            self.error.emit(str(e))

class PDFLoadWorker(QObject):
    """
    Worker para carregar e renderizar páginas de PDF como imagens.
    Gera QImages em background para não travar a UI.
    """
    finished = Signal(list, float, dict) # images (list of QImage), duration, doc_data
    error = Signal(str)
    
    def __init__(self, file_path, doc_data=None):
        super().__init__()
        self.file_path = file_path
        self.doc_data = doc_data or {}
        
    @Slot()
    def run(self):
        try:
            if fitz is None:
                self.error.emit("Biblioteca 'pymupdf' não instalada. Use 'pip install pymupdf'.")
                return
                
            start_time = time.time()
            doc = fitz.open(self.file_path)
            images = []
            
            # Renderizar páginas com 2.0x zoom (144 DPI) para boa legibilidade
            mat = fitz.Matrix(2.0, 2.0)
            
            for page in doc:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                # Formato RGB888 é compatível com Pixmap.fromImage
                img = QImage(bytes(pix.samples), pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                images.append(img.copy()) # Copy crucial para garantir persistência dos dados
                
            doc.close()
            duration = time.time() - start_time
            self.finished.emit(images, duration, self.doc_data)
            
        except Exception as e:
            self.error.emit(f"Erro ao carregar PDF: {str(e)}")
