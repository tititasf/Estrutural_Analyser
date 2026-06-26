import sys, os, time
import cProfile, pstats
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from src.ui.widgets.pre_validation_dialog import PreValidationDialog

app = QApplication(sys.argv)

db_path = r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\project_data.vision"
if not os.path.isfile(db_path):
    db_path = r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\project_data.vision"

print("Loading test data...")
pillar_report = {f"P{i}": {"name": f"P{i}", "classification": "INDETERMINADO"} for i in range(1, 1500)}
slabs = [{"name": f"L{i}", "laje_dim": str(10+i)} for i in range(1, 400)]

def run():
    print("Running PreValidationDialog...")
    dlg = PreValidationDialog(
        pillar_report=pillar_report,
        nivel_report={},
        slabs=slabs,
        convention={},
        obra="CONSULTENGE",
        pavimento="TEST",
        beam_texts=[],
        canvas=None,
        convention_file=None,
        db_path=db_path,
        parent=None,
    )
    print("Showing dialog...")
    dlg.showMaximized()
    print("Switching to Pilares...")
    tabs = dlg.findChildren(type(dlg._tabs))
    if tabs:
        tabs[0].setCurrentIndex(1)
    app.processEvents()
    print("Done")

if __name__ == "__main__":
    profiler = cProfile.Profile()
    profiler.enable()
    run()
    profiler.disable()
    
    with open("scratch/profile_stats.txt", "w", encoding="utf-8") as f:
        stats = pstats.Stats(profiler, stream=f).sort_stats('cumtime')
        stats.print_stats(50)
    print("Profile saved to scratch/profile_stats.txt")
