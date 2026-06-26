import sys, os, time
import cProfile, pstats
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QGraphicsScene
from src.ui.widgets.pre_validation_dialog import PreValidationDialog

app = QApplication(sys.argv)
scene = QGraphicsScene()

pillar_report = {f"P{i}": {"name": f"P{i}", "classification": "INDETERMINADO", "points": [[0,0], [10,0], [10,10], [0,10]]} for i in range(1, 1000)}
slabs = [{"name": f"L{i}", "laje_dim": str(10+i)} for i in range(1, 10)]

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
        db_path=None,
        parent=None,
    )
    # Simulate that scene was loaded
    dlg._dxf_scene = scene
    
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
        stats.print_stats(30)
    print("Profile saved to scratch/profile_stats.txt")
