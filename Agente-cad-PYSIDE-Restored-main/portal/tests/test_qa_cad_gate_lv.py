import ezdxf
import pytest
from pathlib import Path

from portal.app import qa_cad_gate as gate


def _create_sample_beam_dxf(path, length=300, bw=19, height=55, beam_name='V301'):
    """Helper que gera um DXF com viga retangular de 0 a length em X e 0 a bw em Y."""
    doc = ezdxf.new()
    ms = doc.modelspace()
    # Paredes longitudinais da viga (Face A em Y=19, Face B em Y=0)
    ms.add_line((0, 0), (length, 0))
    ms.add_line((0, bw), (length, bw))
    # Paredes de fechamento nas extremidades (apoios)
    ms.add_line((0, 0), (0, bw))
    ms.add_line((length, 0), (length, bw))
    # Rótulo e seção
    ms.add_text(beam_name, dxfattribs={'insert': (20, bw + 10), 'height': 3})
    ms.add_text(f'{bw}/{height}', dxfattribs={'insert': (50, bw / 2), 'height': 3})
    doc.saveas(path)
    return doc


def test_lv_correct_segment_with_slab_discount_passes(tmp_path):
    """T1: Viga 19/55, Face A com laje L1 (h=12). Segmento declara h_útil = 43 cm (55 - 12)."""
    dxf_path = tmp_path / 'viga_lv1.dxf'
    _create_sample_beam_dxf(dxf_path, length=300, bw=19, height=55, beam_name='V301')

    snapshot = {
        'classe': 'LV',
        'collections': {
            'laterais': [{
                'beam_name': 'V301',
                'face': 'A',
                'segment_label': '1',
                'points': [[0, 19], [300, 19]],
                'length': '300cm',
                'height': '43cm',
                'slabs': [{'name': 'L1', 'height': 12.0}],
            }]
        }
    }
    report = gate.measure_lateral_beams(dxf_path, snapshot)
    assert report['schema'] == 'cad.qa_original_laterais/v1'
    h_contact = next(c for c in report['contacts'] if c['aspect'] == 'altura útil')
    assert h_contact['status'] == 'measured'
    assert h_contact['h_viga'] == 55.0
    assert h_contact['h_laje'] == 12.0
    assert h_contact['h_util_medida'] == 43.0
    assert h_contact['h_util_declarada'] == 43.0
    assert not gate.errors(report)


def test_lv_segment_without_slab_discount_fails_altura_util(tmp_path):
    """T2: Viga 19/55, Face A com laje L1 (h=12). Segmento declara h_útil = 55 cm (sem desconto)."""
    dxf_path = tmp_path / 'viga_lv2.dxf'
    _create_sample_beam_dxf(dxf_path, length=300, bw=19, height=55, beam_name='V301')

    snapshot = {
        'classe': 'LV',
        'collections': {
            'laterais': [{
                'beam_name': 'V301',
                'face': 'A',
                'segment_label': '1',
                'points': [[0, 19], [300, 19]],
                'length': '300cm',
                'height': '55cm',  # Erro: deveria ser 43 cm
                'slabs': [{'name': 'L1', 'height': 12.0}],
            }]
        }
    }
    report = gate.measure_lateral_beams(dxf_path, snapshot)
    h_contact = next(c for c in report['contacts'] if c['aspect'] == 'altura útil')
    assert h_contact['status'] == 'measured'
    assert 'altura_util' in h_contact['errors']
    errs = gate.errors(report)
    assert any('difere da medida 43' in e for e in errs)


def test_lv_segment_facing_void_keeps_full_beam_height(tmp_path):
    """T3: Viga 19/55, Face B voltada para vazio. Segmento declara h_útil = 55 cm (sem desconto)."""
    dxf_path = tmp_path / 'viga_lv3.dxf'
    _create_sample_beam_dxf(dxf_path, length=300, bw=19, height=55, beam_name='V301')

    snapshot = {
        'classe': 'LV',
        'collections': {
            'laterais': [{
                'beam_name': 'V301',
                'face': 'B',
                'segment_label': '1',
                'points': [[0, 0], [300, 0]],
                'length': '300cm',
                'height': '55cm',
                'slabs': [],  # Face para vazio
            }]
        }
    }
    report = gate.measure_lateral_beams(dxf_path, snapshot)
    h_contact = next(c for c in report['contacts'] if c['aspect'] == 'altura útil')
    assert h_contact['status'] == 'measured'
    assert h_contact['h_laje'] == 0.0
    assert h_contact['h_util_medida'] == 55.0
    assert not gate.errors(report)


def test_lv_segment_facing_void_with_spurious_discount_fails(tmp_path):
    """T4: Viga 19/55, Face B para vazio. Segmento declara h_útil = 43 cm (desconto indevido)."""
    dxf_path = tmp_path / 'viga_lv4.dxf'
    _create_sample_beam_dxf(dxf_path, length=300, bw=19, height=55, beam_name='V301')

    snapshot = {
        'classe': 'LV',
        'collections': {
            'laterais': [{
                'beam_name': 'V301',
                'face': 'B',
                'segment_label': '1',
                'points': [[0, 0], [300, 0]],
                'length': '300cm',
                'height': '43cm',  # Erro: não tem laje
                'slab': 'vazio',
            }]
        }
    }
    report = gate.measure_lateral_beams(dxf_path, snapshot)
    h_contact = next(c for c in report['contacts'] if c['aspect'] == 'altura útil')
    assert 'altura_util' in h_contact['errors']
    errs = gate.errors(report)
    assert any('difere da medida 55' in e for e in errs)


def test_lv_cut_symbol_does_not_segment_lateral_passes(tmp_path):
    """T5: Viga com símbolo de corte desenhado no meio (X=100..112). Lateral contínua (0..300) passa sem erro."""
    dxf_path = tmp_path / 'viga_lv5.dxf'
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_line((0, 0), (300, 0))
    ms.add_line((0, 19), (300, 19))
    ms.add_line((0, 0), (0, 19))
    ms.add_line((300, 0), (300, 19))
    ms.add_text('V301', dxfattribs={'insert': (20, 25), 'height': 3})
    ms.add_text('19/55', dxfattribs={'insert': (50, 10), 'height': 3})
    # Símbolo de corte desenhado em layer CORTE no meio do vão
    ms.add_line((100, -5), (100, 25), dxfattribs={'layer': 'CORTE'})
    ms.add_line((112, -5), (112, 25), dxfattribs={'layer': 'CORTE'})
    doc.saveas(dxf_path)

    snapshot = {
        'classe': 'LV',
        'collections': {
            'laterais': [{
                'beam_name': 'V301',
                'face': 'A',
                'segment_label': '1',
                'points': [[0, 19], [300, 19]],
                'length': '300cm',
                'height': '55cm',
                'slabs': [],
            }]
        }
    }
    report = gate.measure_lateral_beams(dxf_path, snapshot)
    cut_contact = next(c for c in report['contacts'] if c['aspect'] == 'visão corte')
    assert cut_contact['status'] == 'measured'
    assert 'atravessa a lateral sem interrompê-la' in cut_contact['basis']
    assert not gate.errors(report)


def test_lv_spurious_segmentation_at_cut_symbol_fails(tmp_path):
    """T6: Símbolo de corte em X=100..112. SA seccionou indevidamente a lateral em 2 segmentos."""
    dxf_path = tmp_path / 'viga_lv6.dxf'
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_line((0, 0), (300, 0))
    ms.add_line((0, 19), (300, 19))
    ms.add_line((0, 0), (0, 19))
    ms.add_line((300, 0), (300, 19))
    ms.add_text('V301', dxfattribs={'insert': (20, 25), 'height': 3})
    ms.add_text('19/55', dxfattribs={'insert': (50, 10), 'height': 3})
    ms.add_line((100, -5), (100, 25), dxfattribs={'layer': 'CORTE'})
    ms.add_line((112, -5), (112, 25), dxfattribs={'layer': 'CORTE'})
    doc.saveas(dxf_path)

    snapshot = {
        'classe': 'LV',
        'collections': {
            'laterais': [
                {
                    'beam_name': 'V301',
                    'face': 'A',
                    'segment_label': '1',
                    'points': [[0, 19], [100, 19]],
                    'length': '100cm',
                    'height': '55cm',
                    'slabs': [],
                },
                {
                    'beam_name': 'V301',
                    'face': 'A',
                    'segment_label': '2',
                    'points': [[112, 19], [300, 19]],
                    'length': '188cm',
                    'height': '55cm',
                    'slabs': [],
                }
            ]
        }
    }
    report = gate.measure_lateral_beams(dxf_path, snapshot)
    errs = gate.errors(report)
    assert any('coincide com símbolo de visão de corte' in e for e in errs)
    assert any('LV-VISAO-CORTE-NAO-SECCIONA-20261008' in e for e in errs)


def test_lv_exploded_dimension_tick_does_not_segment_lateral(tmp_path):
    """T7: Tique de cota explodida em 45° corta falso segmento; deve falhar em apoios_limites."""
    dxf_path = tmp_path / 'viga_lv7.dxf'
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_line((0, 0), (300, 0))
    ms.add_line((0, 19), (300, 19))
    ms.add_line((0, 0), (0, 19))
    ms.add_line((300, 0), (300, 19))
    ms.add_text('V301', dxfattribs={'insert': (20, 25), 'height': 3})
    ms.add_text('19/55', dxfattribs={'insert': (50, 10), 'height': 3})
    # Tique oblíquo a 45° em X=150, Y=19 (dx=3, dy=3)
    ms.add_line((148.5, 17.5), (151.5, 20.5))
    doc.saveas(dxf_path)

    snapshot = {
        'classe': 'LV',
        'collections': {
            'laterais': [{
                'beam_name': 'V301',
                'face': 'A',
                'segment_label': '1',
                'points': [[0, 19], [150, 19]],  # Interrompido no tique de cota
                'length': '150cm',
                'height': '55cm',
                'slabs': [],
            }]
        }
    }
    report = gate.measure_lateral_beams(dxf_path, snapshot)
    errs = gate.errors(report)
    assert any('cota explodida' in e for e in errs)


def test_lv_overlapping_segments_fail_inventory(tmp_path):
    """T8: Dois segmentos na mesma face sobrepostos longitudinalmente por 50 cm falham inventário."""
    dxf_path = tmp_path / 'viga_lv8.dxf'
    _create_sample_beam_dxf(dxf_path, length=300, bw=19, height=55, beam_name='V301')

    snapshot = {
        'classe': 'LV',
        'collections': {
            'laterais': [
                {
                    'beam_name': 'V301',
                    'face': 'A',
                    'segment_label': '1',
                    'points': [[0, 19], [150, 19]],
                    'length': '150cm',
                    'height': '55cm',
                    'slabs': [],
                },
                {
                    'beam_name': 'V301',
                    'face': 'A',
                    'segment_label': '2',
                    'points': [[100, 19], [250, 19]],  # Sobreposição de 100 a 150 (50 cm)
                    'length': '150cm',
                    'height': '55cm',
                    'slabs': [],
                }
            ]
        }
    }
    report = gate.measure_lateral_beams(dxf_path, snapshot)
    errs = gate.errors(report)
    assert any('segmento sobreposto' in e for e in errs)


def test_lv_segment_offset_from_beam_wall_fails_identity(tmp_path):
    """T9: Segmento lateral posicionado em Y=25 (fora da parede Y=19) falha em identidade_contorno."""
    dxf_path = tmp_path / 'viga_lv9.dxf'
    _create_sample_beam_dxf(dxf_path, length=300, bw=19, height=55, beam_name='V301')

    snapshot = {
        'classe': 'LV',
        'collections': {
            'laterais': [{
                'beam_name': 'V301',
                'face': 'A',
                'segment_label': '1',
                'points': [[0, 25], [300, 25]],  # Y=25 não tem traço original
                'length': '300cm',
                'height': '55cm',
                'slabs': [],
            }]
        }
    }
    report = gate.measure_lateral_beams(dxf_path, snapshot)
    errs = gate.errors(report)
    assert any('identidade_contorno' in e for e in errs)


def test_lv_for_snapshot_dispatch_integration(tmp_path, monkeypatch):
    """T10: LV não é despachada por for_snapshot (fora do gate de adoção)."""
    dxf_path = tmp_path / 'viga_lv10.dxf'
    _create_sample_beam_dxf(dxf_path, length=300, bw=19, height=55, beam_name='V301')

    from portal.app import ficha_reader
    monkeypatch.setattr(ficha_reader, '_fonte_estrutural_producao', lambda obra, pav: dxf_path)
    monkeypatch.setattr(ficha_reader, 'ler_estado_pavimento', lambda obra, pav: {})
    monkeypatch.setattr(ficha_reader, 'listar_itens_n1', lambda state, key: [])

    snapshot = {
        'classe': 'LV',
        'collections': {
            'laterais': [{
                'beam_name': 'V301',
                'face': 'A',
                'segment_label': '1',
                'points': [[0, 19], [300, 19]],
                'length': '300cm',
                'height': '55cm',
                'slabs': [],
            }]
        }
    }
    # LV fica fora do gate de adoção até deixar de usar nome de layer e laje
    # por proximidade; measure_lateral_beams segue testável isoladamente.
    assert gate.for_snapshot(tmp_path, '13_PAV', snapshot) is None
