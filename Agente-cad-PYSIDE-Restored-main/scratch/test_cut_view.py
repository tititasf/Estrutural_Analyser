import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from main import MainWindow

app = QApplication(sys.argv)
win = MainWindow()

def run_test():
    try:
        # We need some cut view data. Let's create dummy data.
        win._nav_combo_obra.setCurrentText("CONSULTENGE")
        app.processEvents()
        win._nav_combo_pav.setCurrentText("TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA")
        app.processEvents()
        
        # Trigger process_pillars_action manually to build the data
        win.process_pillars_action()
        
        # Now find the pre validation dialog and switch to tab 2
        from src.ui.widgets.pre_validation_dialog import PreValidationDialog
        for widget in app.topLevelWidgets():
            if isinstance(widget, PreValidationDialog):
                print("Found dialog! Switching to Tab 2...")
                widget._tabs.setCurrentIndex(2)
                app.processEvents()
                print("Switched successfully!")
                break
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
    
    app.quit()

from PySide6.QtCore import QTimer
QTimer.singleShot(1000, run_test)
app.exec()
