"""Test async DXF loading with QThread to prevent freezing."""
import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QGraphicsScene
from PySide6.QtCore import QThread, Signal, Qt
import time

class DXFReadThread(QThread):
    finished = Signal(object)
    
    def __init__(self, dxf_path):
        super().__init__()
        self.dxf_path = dxf_path
        
    def run(self):
        print(f"[THREAD] Starting ezdxf.readfile({self.dxf_path})")
        t0 = time.perf_counter()
        try:
            import ezdxf
            doc = ezdxf.readfile(self.dxf_path)
            print(f"[THREAD] Loaded in {time.perf_counter() - t0:.2f}s")
            self.finished.emit(doc)
        except Exception as e:
            print(f"[THREAD] Error: {e}")
            self.finished.emit(None)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DXF Async Test")
        self.resize(600, 400)
        
        cw = QWidget()
        self.lay = QVBoxLayout(cw)
        self.setCentralWidget(cw)
        
        self.lbl = QLabel("Loading DXF in background...")
        self.lbl.setAlignment(Qt.AlignCenter)
        self.lay.addWidget(self.lbl)
        
        dxf_path = os.path.join(os.path.dirname(__file__), "test_dxf.dxf")
            
        if not os.path.isfile(dxf_path):
            self.lbl.setText("No DXF found to test.")
            return
            
        print(f"[MAIN] Starting thread for: {dxf_path}")
        self.thread = DXFReadThread(dxf_path)
        self.thread.finished.connect(self.on_loaded)
        self.thread.start()
        
    def on_loaded(self, doc):
        print(f"[MAIN] Received doc: {doc}")
        if not doc:
            self.lbl.setText("Failed to load doc.")
            return
            
        self.lbl.setText("DXF loaded! Now drawing to scene (main thread)...")
        
        t0 = time.perf_counter()
        try:
            scene = QGraphicsScene()
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.pyqt import PyQtBackend
            
            msp = doc.modelspace()
            ctx = RenderContext(doc)
            out = PyQtBackend(scene)
            Frontend(ctx, out).draw_layout(msp)
            print(f"[MAIN] Draw layout in {time.perf_counter() - t0:.2f}s")
            self.lbl.setText(f"Success! Draw took {time.perf_counter() - t0:.2f}s")
        except Exception as e:
            self.lbl.setText(f"Draw failed: {e}")
            print(f"[MAIN] Draw failed: {e}")
            
        # Exit after a short delay
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, QApplication.quit)

app = QApplication(sys.argv)
win = MainWindow()
win.show()
app.exec()
