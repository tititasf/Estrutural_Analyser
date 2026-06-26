import glob
from pathlib import Path
from scripts.train_real_bottom_beams import process_tracer_on_dxf, BottomBeamLearningStore
import src.core.beam_tracer as bt

f = glob.glob(r'D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-2_Triagem\recortes_reversos\*FV*\FV_V302_motor_*.dxf')[-1]
store = BottomBeamLearningStore('teste')
original = bt.BeamTracer._classify_lines

def debug_classify(self, pos, lines):
    closed_lines = []
    for line in lines:
        is_closed = len(line) >= 4 and abs(line[0][0] - line[-1][0]) < 1.0 and abs(line[0][1] - line[-1][1]) < 1.0
        if is_closed:
            closed_lines.append(line)
    print(f'TOTAL LINES: {len(lines)}, CLOSED POLYS: {len(closed_lines)}')
    result = original(self, pos, lines)
    return result

bt.BeamTracer._classify_lines = debug_classify
print(process_tracer_on_dxf(Path(f), store, 'V302'))
