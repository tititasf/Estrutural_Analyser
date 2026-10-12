import ezdxf
import pytest

from portal.app import qa_cad_gate as gate


def test_pillar_oriented_chirality_face_b(tmp_path):
    """Testa quiralidade na Face B (observador caminhando no sentido -X em direção ao pilar).
    Esquerda é -Y (bottom - low), Direita é +Y (high - top).
    """
    doc = ezdxf.new()
    ms = doc.modelspace()
    # Pilar 19x66: X de 0 a 19, Y de 0 a 66
    ms.add_lwpolyline([(0, 0), (19, 0), (19, 66), (0, 66)], close=True)
    # Viga VF301 de largura 14 cm tocando a Face B (X=19): de Y=52 a Y=66
    ms.add_line((19, 52), (100, 52))
    ms.add_line((19, 66), (100, 66))
    ms.add_text('VF301', dxfattribs={'insert': (30, 68), 'height': 3})
    ms.add_text('14/55', dxfattribs={'insert': (50, 60), 'height': 3})
    path = tmp_path / 'pil_face_b.dxf'
    doc.saveas(path)

    snapshot = {
        'classe': 'PIL',
        'collections': {
            'pilares': [{
                'points': [[0, 0], [19, 0], [19, 66], [0, 66]],
                'interpretacao_abcd': {
                    'faces': {
                        'B': {
                            'chega': [{
                                'nome': 'VF301',
                                'dim': '14/55',
                                'dist_esq': '52cm',
                                'dist_dir': '0cm'
                            }]
                        }
                    }
                }
            }]
        }
    }
    report = gate.measure(path, snapshot)
    contact = report['contacts'][0]
    assert contact['status'] == 'measured'
    assert contact['width_cm'] == 14.0
    assert contact['face_length_cm'] == 66.0
    # Quiralidade orientada comprovada:
    assert contact['dist_esq_cm'] == 52.0
    assert contact['dist_dir_cm'] == 0.0
    # Compatibilidade retroativa com distances_cm ordenada:
    assert contact['distances_cm'] == [0.0, 52.0]
    # Conservação dimensional:
    assert contact['dist_esq_cm'] + contact['width_cm'] + contact['dist_dir_cm'] == contact['face_length_cm']
    assert not gate.errors(report)


def test_asymmetric_walls_at_opposite_end_are_accepted(tmp_path):
    """Testa vigas com extremidades assimétricas no lado oposto (ex: 320 cm vs 311 cm).
    Ambas tocam rigorosamente o pilar na Face B (X=20), mas terminam em X diferente.
    O gate evoluído deve aceitar e medir.
    """
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline([(0, 0), (20, 0), (20, 60), (0, 60)], close=True)
    # Parede 1 termina em X=100 (comprimento 80)
    ms.add_line((20, 20), (100, 20))
    # Parede 2 termina em X=90 (comprimento 70)
    ms.add_line((20, 34), (90, 34))
    ms.add_text('V302', dxfattribs={'insert': (30, 25), 'height': 3})
    ms.add_text('14/55', dxfattribs={'insert': (50, 25), 'height': 3})
    path = tmp_path / 'asymmetric.dxf'
    doc.saveas(path)

    snapshot = {
        'classe': 'PIL',
        'collections': {
            'pilares': [{
                'points': [[0, 0], [20, 0], [20, 60], [0, 60]],
                'interpretacao_abcd': {
                    'faces': {
                        'B': {
                            'chega': [{
                                'nome': 'V302',
                                'dim': '14/55',
                                'dist_esq': '20cm',
                                'dist_dir': '26cm'
                            }]
                        }
                    }
                }
            }]
        }
    }
    report = gate.measure(path, snapshot)
    contact = report['contacts'][0]
    assert contact['status'] == 'measured'
    assert contact['width_cm'] == 14.0
    assert contact['dist_esq_cm'] == 20.0
    assert contact['dist_dir_cm'] == 26.0
    assert not gate.errors(report)


def test_beam_section_validated_with_name_in_own_span(tmp_path):
    """Testa viga com seção e nome anotados no vão próprio."""
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline([(0, 0), (20, 0), (20, 60), (0, 60)], close=True)
    ms.add_line((20, 10), (120, 10))
    ms.add_line((20, 29), (120, 29))
    # Nome e seção ambos no vão próprio.
    ms.add_text('V312', dxfattribs={'insert': (30, 15), 'height': 3})
    ms.add_text('19/55', dxfattribs={'insert': (40, 15), 'height': 3})
    path = tmp_path / 'span_sec.dxf'
    doc.saveas(path)

    snapshot = {
        'classe': 'PIL',
        'collections': {
            'pilares': [{
                'points': [[0, 0], [20, 0], [20, 60], [0, 60]],
                'interpretacao_abcd': {
                    'faces': {
                        'B': {
                            'chega': [{
                                'nome': 'V312',
                                'dim': '19/55',
                                'dist_esq': '10cm',
                                'dist_dir': '31cm'
                            }]
                        }
                    }
                }
            }]
        }
    }
    report = gate.measure(path, snapshot)
    contact = report['contacts'][0]
    assert contact['status'] == 'measured'
    assert contact['width_cm'] == 19.0
    assert contact['dist_esq_cm'] == 10.0
    assert contact['dist_dir_cm'] == 31.0
    assert contact['section'] == '19/55'
    assert not gate.errors(report)


def test_pillar_ghost_link_case1_beam_already_measured_on_another_face(tmp_path):
    """Testa detecção do Caso 1: VF301 comprovada na Face B; Face C possui zero paredes no CAD."""
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline([(0, 0), (19, 0), (19, 66), (0, 66)], close=True)
    # Paredes e textos na Face B (X=19)
    ms.add_line((19, 52), (100, 52))
    ms.add_line((19, 66), (100, 66))
    ms.add_text('VF301', dxfattribs={'insert': (30, 68), 'height': 3})
    ms.add_text('14/55', dxfattribs={'insert': (50, 60), 'height': 3})
    # Face C (Y=66): NENHUMA parede desenhada
    path = tmp_path / 'ghost_case1.dxf'
    doc.saveas(path)

    snapshot = {
        'classe': 'PIL',
        'collections': {
            'pilares': [{
                'points': [[0, 0], [19, 0], [19, 66], [0, 66]],
                'interpretacao_abcd': {
                    'faces': {
                        'B': {'chega': [{'nome': 'VF301', 'dim': '14/55', 'dist_esq': '52cm', 'dist_dir': '0cm'}]},
                        'C': {'chega': [{'nome': 'VF301', 'dim': '14/55', 'dist_esq': '5cm', 'dist_dir': '0cm'}]}
                    }
                }
            }]
        }
    }
    report = gate.measure(path, snapshot)
    assert len(report['contacts']) == 2
    c_b, c_c = report['contacts'][0], report['contacts'][1]

    # Face B medida com perfeição
    assert c_b['status'] == 'measured'
    assert c_b['face'] == 'B'
    assert c_b['width_cm'] == 14.0

    # Face C sem paredes: suspeita, nunca divergência nem remoção automática
    assert c_c['status'] == 'uncertain'
    assert c_c['face'] == 'C'
    assert c_c['ghost_suspect'] is True
    assert c_c['proven_face'] == 'B'
    assert 'aplicar' not in c_c and 'veredito' not in c_c
    assert 'possível vínculo inexistente' in c_c['reason']
    assert not hasattr(gate, 'remove_ghost_links')

    # Bloqueia promoção até alguém conferir no CAD
    errs = gate.errors(report)
    assert any('possível vínculo inexistente' in e for e in errs)


def test_pillar_ghost_link_case2_zero_walls_on_face(tmp_path):
    """Testa detecção do Caso 2: P42 com V312 na Face A sem paredes no DXF."""
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline([(0, 0), (50, 0), (50, 19), (0, 19)], close=True)
    # Face A (X=0): NENHUMA parede desenhada
    path = tmp_path / 'ghost_case2.dxf'
    doc.saveas(path)

    snapshot = {
        'classe': 'PIL',
        'collections': {
            'pilares': [{
                'points': [[0, 0], [50, 0], [50, 19], [0, 19]],
                'interpretacao_abcd': {
                    'faces': {
                        'A': {'chega': [{'nome': 'V312', 'dim': '19/120', 'dist_esq': '15.5cm', 'dist_dir': '15.5cm'}]}
                    }
                }
            }]
        }
    }
    report = gate.measure(path, snapshot)
    assert len(report['contacts']) == 1
    c_a = report['contacts'][0]
    assert c_a['status'] == 'uncertain'
    assert c_a['ghost_suspect'] is True
    assert 'proven_face' not in c_a
    assert 'nenhuma parede de viga chega ou atravessa a face A' in c_a['reason']


def test_pillar_beam_passing_through_same_width_is_measured(tmp_path):
    """Viga 19 que atravessa pilar 50x19 (P42/P46 13_PAV): paredes contínuas passam pelas
    faces C/D.  Antes virava 'link fantasma'; agora mede e o rótulo vem do 1º vão."""
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline([(0, 0), (50, 0), (50, 19), (0, 19)], close=True)
    ms.add_line((-250, 0), (300, 0))
    ms.add_line((-250, 19), (300, 19))
    # Original named closed support bounds the first span.
    ms.add_lwpolyline([(-109, 0), (-90, 0), (-90, 40), (-109, 40)], close=True)
    ms.add_text('P2', dxfattribs={'insert': (-100, 10), 'height': 3})
    ms.add_text('V312', dxfattribs={'insert': (-60, 10), 'height': 3})
    ms.add_text('V312', dxfattribs={'insert': (100, 10), 'height': 3})
    ms.add_text('19/120', dxfattribs={'insert': (-40, 22), 'height': 3})
    ms.add_text('19/55', dxfattribs={'insert': (-200, 22), 'height': 3})
    ms.add_text('19/120', dxfattribs={'insert': (120, 22), 'height': 3})
    path = tmp_path / 'passa.dxf'
    doc.saveas(path)
    link = {'nome': 'V312', 'dim': '19/120', 'dist_esq': '0cm', 'dist_dir': '0cm'}
    snapshot = {'classe': 'PIL', 'collections': {'pilares': [{
        'points': [[0, 0], [50, 0], [50, 19], [0, 19]],
        'interpretacao_abcd': {'orientation': 'horizontal', 'faces': {'C': {'chega': [dict(link)]}, 'D': {'chega': [dict(link)]}}}}]}}
    report = gate.measure(path, snapshot)
    assert [c['status'] for c in report['contacts']] == ['measured', 'measured']
    assert all(c['section'] == '19/120' and c['distances_cm'] == [0.0, 0.0] for c in report['contacts'])
    assert not gate.errors(report)

    # Distâncias copiadas de outra face (15,5/15,5 numa face de 19) são divergência medida
    for face in 'CD':
        snapshot['collections']['pilares'][0]['interpretacao_abcd']['faces'][face]['chega'][0].update(
            dist_esq='15.5cm', dist_dir='15.5cm')
    assert any('distâncias' in e for e in gate.errors(gate.measure(path, snapshot)))


def test_pillar_ambiguous_walls_remain_uncertain_not_ghost(tmp_path):
    """Testa que paredes reais existentes no CAD sem rótulo unívoco continuam 'uncertain' e NÃO ghost_link."""
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline([(0, 0), (20, 0), (20, 60), (0, 60)], close=True)
    # 2 paredes existem no CAD, mas sem texto de seção
    ms.add_line((20, 20), (100, 20))
    ms.add_line((20, 34), (100, 34))
    path = tmp_path / 'ambiguous.dxf'
    doc.saveas(path)

    snapshot = {
        'classe': 'PIL',
        'collections': {
            'pilares': [{
                'points': [[0, 0], [20, 0], [20, 60], [0, 60]],
                'interpretacao_abcd': {
                    'faces': {
                        'B': {'chega': [{'nome': 'V305', 'dim': '14/55'}]}
                    }
                }
            }]
        }
    }
    report = gate.measure(path, snapshot)
    c_b = report['contacts'][0]
    assert c_b['status'] == 'uncertain'
    assert c_b['status'] != 'ghost_link'
    assert 'ausente ou ambíguo' in c_b['reason']


def test_pillar_regression_existing_measured_pillars_intact(tmp_path):
    """Assegura compatibilidade reversa estrita com ligações válidas e comprovadas."""
    doc = ezdxf.new()
    ms = doc.modelspace()
    ms.add_lwpolyline([(0, 0), (20, 0), (20, 60), (0, 60)], close=True)
    ms.add_line((20, 10), (120, 10))
    ms.add_line((20, 29), (120, 29))
    ms.add_text('V312', dxfattribs={'insert': (40, 32), 'height': 3})
    ms.add_text('19/55', dxfattribs={'insert': (40, 15), 'height': 3})
    path = tmp_path / 'clean_measured.dxf'
    doc.saveas(path)

    snapshot = {
        'classe': 'PIL',
        'collections': {
            'pilares': [{
                'points': [[0, 0], [20, 0], [20, 60], [0, 60]],
                'interpretacao_abcd': {
                    'faces': {
                        'B': {'chega': [{'nome': 'V312', 'dim': '19/55', 'dist_esq': '10cm', 'dist_dir': '31cm'}]}
                    }
                }
            }]
        }
    }
    report = gate.measure(path, snapshot)
    assert report['contacts'][0]['status'] == 'measured'
    assert not gate.errors(report)

