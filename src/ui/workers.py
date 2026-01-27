
import os
import pickle
import time
from PySide6.QtCore import QObject, QThread, Signal, Slot
from src.core.dxf_loader import DXFLoader

class DXFLoadWorker(QObject):
    """
    Worker para carregar arquivos DXF em background.
    Suporta cache via .pkl para carregamento ultra-rápido.
    """
    finished = Signal(dict, float) # data, duration
    error = Signal(str)
    
    def __init__(self, file_path, use_cache=True):
        super().__init__()
        self.file_path = file_path
        self.use_cache = use_cache
        
    @Slot()
    def run(self):
        try:
            start_time = time.time()
            data = None
            
            # 1. Tentar Cache (.pkl)
            cache_path = self.file_path + ".pkl"
            
            if self.use_cache and os.path.exists(cache_path):
                # Verificar se o cache é mais novo que o arquivo original
                dxf_mtime = os.path.getmtime(self.file_path)
                pkl_mtime = os.path.getmtime(cache_path)
                
                if pkl_mtime > dxf_mtime:
                    try:
                        with open(cache_path, 'rb') as f:
                            data = pickle.load(f)
                            # print(f"[Worker] Cache carregado: {cache_path}")
                    except Exception as e:
                        print(f"[Worker] Erro ao ler cache (será recriado): {e}")

            # 2. Se não carregou do cache, carregar do DXF
            if not data:
                data = DXFLoader.load_dxf(self.file_path)
                
                # Salvar Cache
                if data and self.use_cache:
                    try:
                        with open(cache_path, 'wb') as f:
                            pickle.dump(data, f)
                            # print(f"[Worker] Cache salvo: {cache_path}")
                    except Exception as e:
                        print(f"[Worker] Falha ao salvar cache: {e}")

            duration = time.time() - start_time
            
            if data:
                self.finished.emit(data, duration)
            else:
                self.error.emit("Falha ao carregar dados do DXF (retorno vazio).")
                
        except Exception as e:
            self.error.emit(str(e))
