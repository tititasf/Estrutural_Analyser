"""Development suppresses graphics on one real canvas, retaining CAD input."""
import os
from copy import deepcopy
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def test_actual_canvas_never_renders_or_changes_original_cad(monkeypatch):
    from PySide6.QtWidgets import QApplication
    from src.ui.canvas import CADCanvas, RenderMode
    from ezdxf.addons.drawing import Frontend
    import ezdxf
    from scripts.arete.headless_sa_analise import _suppress_development_canvas_rendering

    app = QApplication.instance() or QApplication([])
    canvas = CADCanvas()
    untouched = CADCanvas()
    window = SimpleNamespace(canvas=canvas)
    entities = {'texts': [{'text': 'V1', 'pos': [10, 20]}],
                'lines': [{'start': [0, 0], 'end': [100, 0], 'handle': 'W'}],
                'polylines': [{'points': [[0, 0], [100, 0], [100, 19], [0, 19]]}],
                'circles': [{'center': [20, 20], 'radius': 5}]}
    before = deepcopy(entities)
    initial_items = set(canvas.scene.items())
    native_calls = []
    source_reads = []
    monkeypatch.setattr(Frontend, 'draw_layout', lambda *a, **kw: native_calls.append(True))
    monkeypatch.setattr(ezdxf, 'readfile', lambda *a, **kw: source_reads.append(a))
    receipt = _suppress_development_canvas_rendering(window)
    canvas.add_dxf_entities(entities, source_dxf_path='must-not-be-read.dxf')
    canvas.draw_interactive_pillars([{'id': 'P1', 'name': 'P1', 'points': [[0, 0], [10, 0], [10, 10]]}])
    canvas.draw_slabs([{'id': 'L1', 'links': {}}])
    canvas.draw_beams([{'id': 'V1', 'name': 'V1', 'pos': [10, 20]}])
    canvas.draw_item_links({'id': 'V1', 'links': {}})
    canvas.focus_on_beam_geometry({'id': 'V1'})
    canvas.highlight_link({'type': 'text', 'text': 'V1', 'pos': [10, 20]})
    canvas.isolate_item('V1', 'beam')
    assert native_calls == []
    assert source_reads == []
    assert set(canvas.scene.items()) == initial_items
    assert entities == before
    assert canvas.last_entities is entities
    assert canvas.last_render_mode == RenderMode.TRUE_GEOMETRY
    assert canvas.source_dxf_path == 'must-not-be-read.dxf'
    assert canvas.dxf_entities == [entities['texts'][0],
                                  {**entities['lines'][0], 'points': [[0, 0], [100, 0]]},
                                  entities['polylines'][0], entities['circles'][0]]
    assert 'points' not in entities['lines'][0]
    assert receipt['suppressed_calls']['add_dxf_entities'] == 1
    assert receipt['suppressed_calls']['draw_beams'] == 1
    assert untouched.add_dxf_entities.__func__ is CADCanvas.add_dxf_entities
    assert _suppress_development_canvas_rendering(window) is receipt
    canvas.deleteLater()
    untouched.deleteLater()


def test_canvas_free_runner_preserves_canonical_collections():
    from scripts.arete.headless_sa_analise import _suppress_development_canvas_rendering
    collections = {'pillars': [{'name': 'P1'}], 'slabs': [], 'beams': [{'name': 'V1'}]}
    window = SimpleNamespace(**deepcopy(collections))
    receipt = _suppress_development_canvas_rendering(window)
    assert receipt == {'mode': 'NO_CANVAS', 'suppressed_calls': {}}
    assert {key: getattr(window, key) for key in collections} == collections
