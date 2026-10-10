"""Gate CAD LV: segmentos no formato real do SA (lateral_{a,b}_{para,passa})."""
import ezdxf

from portal.app import qa_cad_gate as gate
from portal.app import qa_cad_gate_run as run


def _dxf(path, extra=None):
    """Viga V301 19/55 de x=0 a 300 entre y=0 e y=19, fechada nos extremos."""
    doc = ezdxf.new()
    ms = doc.modelspace()
    for a, b in (((0, 0), (300, 0)), ((0, 19), (300, 19)), ((0, 0), (0, 19)), ((300, 0), (300, 19))):
        ms.add_line(a, b)
    ms.add_text('V301', dxfattribs={'insert': (20, 8), 'height': 3})
    ms.add_text('19/55', dxfattribs={'insert': (60, 8), 'height': 3})
    for text, insert in (extra or []):
        ms.add_text(text, dxfattribs={'insert': insert, 'height': 3})
    doc.saveas(path)
    return path


def _slab(steps=None):
    return {'name': 'L1', 'height': '12', 'points': [[0, 19], [300, 19], [300, 200], [0, 200]],
            'slab_steps': steps or []}


def _snapshot(y=19.0, slabs=({'name': 'L1', 'height': 'h=12'},)):
    row = {'beam_name': 'V301', 'behavior': 'Para', 'side': 'A', 'segment_label': '1', 'status': 'valid',
           'length': 300.0, 'level': '852.19', 'level_slabs': [s['name'] for s in slabs], 'width': '19/55',
           'points': [[0.0, y], [300.0, y]],
           'lv_cell': {'dim': '19/55', 'level': '852.19', 'slabs': list(slabs)}}
    return {'classe': 'LV', 'collections': {'lateral_a_para': [row], 'lateral_b_para': []}}


def _by_aspect(report, aspect):
    return next(c for c in report['contacts'] if c['aspect'] == aspect)


def test_segmento_correto_confere(tmp_path):
    report = gate.measure_lateral_beams(_dxf(tmp_path / 'a.dxf'), _snapshot(), [_slab()])
    assert report['schema'] == 'cad.qa_original_laterais/v2'
    assert not gate.errors(report)
    assert _by_aspect(report, 'laje da face')['status'] == 'measured'
    assert _by_aspect(report, 'seção')['status'] == 'measured'
    assert all(c['aspect'] != 'altura útil' for c in report['contacts'])


def test_regiao_rebaixada_nao_declarada_diverge(tmp_path):
    step = {'height_cm': 10.0, 'points': [[0, 19], [100, 19], [100, 120], [0, 120]]}
    report = gate.measure_lateral_beams(_dxf(tmp_path / 'b.dxf'), _snapshot(), [_slab([step])])
    assert 'laje_face' in _by_aspect(report, 'laje da face')['errors']


def test_laje_que_encosta_sem_declaracao_diverge(tmp_path):
    report = gate.measure_lateral_beams(_dxf(tmp_path / 'c.dxf'), _snapshot(slabs=()), [_slab()])
    assert 'L1' in _by_aspect(report, 'laje da face')['errors']['laje_face']


def test_face_deslocada_meio_centimetro_diverge(tmp_path):
    report = gate.measure_lateral_beams(_dxf(tmp_path / 'd.dxf'), _snapshot(y=18.5), [_slab()])
    assert '0,5 cm' in _by_aspect(report, 'arestas')['errors']['identidade_contorno']


def test_secao_de_pilar_na_faixa_nao_vale_para_viga(tmp_path):
    path = _dxf(tmp_path / 'e.dxf', extra=[('P8', (150, 27)), ('19/66', (150, 22))])
    report = gate.measure_lateral_beams(path, _snapshot(), [_slab()])
    sec = _by_aspect(report, 'seção')
    assert sec['status'] == 'measured' and not sec['errors']


def test_sa_antigo_sem_lv_cell_usa_level_slabs(tmp_path):
    snap = _snapshot()
    row = snap['collections']['lateral_a_para'][0]
    row.update(lv_cell=None, level='')
    report = gate.measure_lateral_beams(_dxf(tmp_path / 'f.dxf'), snap, [_slab()])
    assert not gate.errors(report)
    assert _by_aspect(report, 'laje da face')['status'] == 'measured'
    assert _by_aspect(report, 'coerência')['status'] == 'uncertain'


def test_item_lv_do_portal_e_viga_mais_comportamento():
    assert run.CLASSE_PORTAL['lateral_b_passa'] == 'LV'
    assert run.item_name('lateral_b_passa', 'lateral_b_passa|x|1|1', 'V301') == 'V301|passa'
    assert run.item_name('lateral_a_para', 'lateral_a_para|x|1|1', 'V301') == 'V301|para'
