"""Read-only real CAD audit; renders a formatted memory copy, never saves DXF."""
from pathlib import Path
import hashlib
import time
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from src.core.number_presentation import _symbol_level_handles, apply_dxf_number_presentation, display_level

root = Path(__file__).resolve().parents[2]
output = root / 'scripts/arete/relatorios/20261003_number_presentation'
output.mkdir(parents=True, exist_ok=True)
for floor, name, focus in [
    ('13', 'TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA.dxf', (2200, 2835, 2330, 2915)),
    ('14', 'TMC-EST-PE-7000-14P-R03.dxf', None),
]:
    source = next((root/'DADOS-OBRAS').rglob(name))
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    doc = ezdxf.readfile(source)
    msp = doc.modelspace()
    start = time.monotonic()
    handles = _symbol_level_handles(msp)
    labels = {e.dxf.handle: e.dxf.text for e in msp.query('TEXT') if e.dxf.handle in handles}
    elapsed = time.monotonic()-start
    apply_dxf_number_presentation(doc)
    assert all(doc.entitydb[h].dxf.text == display_level(raw) for h, raw in labels.items())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    if focus is None:
        label = doc.entitydb[next(iter(labels))]
        x, y = tuple(label.dxf.insert)[:2]
        focus = (x-50, y-40, x+100, y+50)
    fig, ax = plt.subplots(figsize=(10, 6))
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp, finalize=True)
    ax.set_xlim(focus[0], focus[2]); ax.set_ylim(focus[1], focus[3])
    fig.savefig(output/f'altitude-{floor}.png', dpi=140, facecolor='black')
    plt.close(fig)
    print(f'{floor}: {len(labels)} labels, {elapsed:.3f}s; source SHA256 unchanged: {before}')
