import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from main import MainWindow

app = QApplication(sys.argv)
win = MainWindow()

def run_test():
    print("Obtendo obras...")
    obras = win.db_manager.get_obras()
    target_obra = None
    target_pav = None
    
    for o in obras:
        pavs = win.db_manager.get_pavimentos(o)
        for p in pavs:
            if "13" in p.upper() or "13" in p:
                target_obra = o
                target_pav = p
                break
        if target_obra:
            break
            
    if not target_obra:
        target_obra = "CONSULTENGE"
        target_pav = "TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA"
        
    print(f"Testando Obra: {target_obra}, Pavimento: {target_pav}")
    win._nav_combo_obra.setCurrentText(target_obra)
    app.processEvents()
    win._nav_combo_pav.setCurrentText(target_pav)
    app.processEvents()
    
    print("Iniciando analise...")
    win.process_pillars_action()
    print("Processamento finalizado. O dialog de pre-validacao deve ter aberto.")
    
    QTimer.singleShot(5000, app.quit)

QTimer.singleShot(1000, run_test)
app.exec()
