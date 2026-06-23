import sys
import os
from PySide6.QtWidgets import QApplication, QComboBox, QListWidget, QWidget

base_dir = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main'
sys.path.append(base_dir)
sys.path.append(os.path.join(base_dir, '_ROBOS_ABAS', 'Robo_Lajes'))
sys.path.append(os.path.join(base_dir, '_ROBOS_ABAS', 'contexto_ATUAL_pilares_PYSIDE'))
sys.path.append(os.path.join(base_dir, '_ROBOS_ABAS', 'Robo_Laterais_de_Vigas'))
sys.path.append(os.path.join(base_dir, '_ROBOS_ABAS', 'Robo_Fundos_de_Vigas'))

try:
    from laje_src.ui.main_window import MainWindow as LajeMainWindow
except:
    LajeMainWindow = None
try:
    from context_pilares import PilaresMainWindow
except:
    PilaresMainWindow = None
try:
    from LateralVigaWindow import MainWindow as VigaMainWindow
except:
    VigaMainWindow = None
try:
    from FundoVigaWindow import MainWindow as FundoMainWindow
except:
    FundoMainWindow = None

app = QApplication(sys.argv)

def inspect_widget(name, widget_class):
    if not widget_class:
        print(f"\n--- {name} --- ERROR: Class not imported")
        return
    try:
        w = widget_class()
        combos = w.findChildren(QComboBox)
        lists = w.findChildren(QListWidget)
        
        print(f"\n--- {name} ---")
        print("ComboBoxes:")
        for c in combos:
            print(f"  - objName: '{c.objectName()}', items: {c.count()}")
            
        print("ListWidgets:")
        for l in lists:
            print(f"  - objName: '{l.objectName()}', items: {l.count()}")
            
    except Exception as e:
        print(f"\n--- {name} --- ERROR: {e}")

inspect_widget("RoboLaje", LajeMainWindow)
inspect_widget("RoboPilares", PilaresMainWindow)
inspect_widget("RoboViga", VigaMainWindow)
inspect_widget("RoboFundo", FundoMainWindow)
