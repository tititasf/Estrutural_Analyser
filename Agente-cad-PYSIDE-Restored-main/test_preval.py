import sys, json, os
from PySide6.QtWidgets import QApplication, QGraphicsScene
from src.ui.widgets.pre_validation_dialog import PreValidationDialog
app = QApplication(sys.argv)

class DummyCanvas:
    scene = QGraphicsScene()

canvas = DummyCanvas()

# Load real data if available
pillar_report = {}
slabs = []
db_path = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\project_data.vision"
obra = "Obra_TREINO_1"
pav = "TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA"
dlg = PreValidationDialog(pillar_report, {}, slabs, {}, obra, pav, [], canvas, None, db_path)
dlg.showMaximized()
app.exec()
