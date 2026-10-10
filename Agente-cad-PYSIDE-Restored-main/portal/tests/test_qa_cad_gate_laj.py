import ezdxf
import pytest
from pathlib import Path

from portal.app import qa_cad_gate as gate


def _slab_dxf(tmp_path, texts, mtexts=None):
    """Helper que gera um arquivo DXF para testes de laje com TEXTs e MTEXTs opcionais."""
    doc = ezdxf.new()
    ms = doc.modelspace()
    for text, at in texts:
        ms.add_text(text, dxfattribs={'insert': at, 'height': 3})
    for mtext, at in (mtexts or []):
        ms.add_mtext(mtext, dxfattribs={'insert': at, 'char_height': 3})
    path = tmp_path / 'laj_test.dxf'
    doc.saveas(path)
    return path


def _slab(**changes):
    """Gera um snapshot sintético de laje com valores padrão customizáveis."""
    slab = dict(
        name='L1',
        nivel='852.12',
        height='12',
        slab_steps=[],
        points=[[0, 0], [100, 0], [100, 100], [0, 100]],
    )
    slab.update(changes)
    return {'classe': 'LAJ', 'collections': {'lajes': [slab]}}


def test_laj_single_nominal_match(tmp_path):
    """Caso 1: Polígono 100x100, L1 em (50, 50), h=12 em (50, 40), 852.19 em (50, 60). Coincide com SA."""
    dxf_path = _slab_dxf(tmp_path, [
        ('L1', (50, 50)),
        ('h=12', (50, 40)),
        ('852.19', (50, 60)),
    ])
    snapshot = _slab(name='L1', height='12', nivel='852.19')

    report = gate.measure_slabs(dxf_path, snapshot)
    assert report['schema'] == 'cad.qa_original_slabs/v1'
    assert gate.errors(report) == []
    assert len(report['contacts']) == 3
    assert all(c['status'] == 'measured' for c in report['contacts'])
    aspects = {c['aspect']: c for c in report['contacts']}
    assert aspects['rótulo']['values'] == ['L1']
    assert aspects['espessura']['values'] == [12.0]
    assert aspects['nível']['values'] == [852.19]


def test_laj_thickness_divergence(tmp_path):
    """Caso 2: L1 em (50, 50), h=14 em (50, 40), 852.19 em (50, 60). SA declara h=12 -> erro de divergência."""
    dxf_path = _slab_dxf(tmp_path, [
        ('L1', (50, 50)),
        ('h=14', (50, 40)),
        ('852.19', (50, 60)),
    ])
    snapshot = _slab(name='L1', height='12', nivel='852.19')

    report = gate.measure_slabs(dxf_path, snapshot)
    errs = gate.errors(report)
    assert any('h=14' in e and 'difere da espessura declarada 12' in e for e in errs)
    h_contact = next(c for c in report['contacts'] if c['aspect'] == 'espessura')
    assert h_contact['status'] == 'measured'
    assert 'dimensoes_espessura' in h_contact['errors']


def test_laj_multiple_thicknesses_spatial_cluster(tmp_path):
    """Caso 3: L309 em (50, 50), h=13 em (52, 45) [dist 5.4], h=10 em (10, 10) [rebaixo]. SA declara h=13."""
    dxf_path = _slab_dxf(tmp_path, [
        ('L309', (50, 50)),
        ('h=13', (52, 45)),
        ('h=10', (10, 10)),
        ('852.19', (50, 60)),
    ])
    snapshot = _slab(name='L309', height='13', nivel='852.19')

    report = gate.measure_slabs(dxf_path, snapshot)
    assert gate.errors(report) == []
    h_main = next(c for c in report['contacts'] if c['aspect'] == 'espessura')
    assert h_main['status'] == 'measured'
    assert h_main['values'] == [13.0]

    h_drop = next(c for c in report['contacts'] if c['aspect'] == 'rebaixo espessura')
    assert h_drop['status'] == 'measured'
    assert h_drop['values'] == [10.0]


def test_laj_multiple_levels_nominal_and_drop(tmp_path):
    """Caso 4: L309 em (50, 50), 852.19 em (50, 65) [dist 15], 852.16 em (10, 10) [dist 56.6]. SA declara n=852.19."""
    dxf_path = _slab_dxf(tmp_path, [
        ('L309', (50, 50)),
        ('h=13', (52, 45)),
        ('852.19', (50, 65)),
        ('852.16', (10, 10)),
    ])
    snapshot = _slab(name='L309', height='13', nivel='852.19')

    report = gate.measure_slabs(dxf_path, snapshot)
    assert gate.errors(report) == []
    n_main = next(c for c in report['contacts'] if c['aspect'] == 'nível')
    assert n_main['status'] == 'measured'
    assert n_main['values'] == [852.19]

    n_drop = next(c for c in report['contacts'] if c['aspect'] == 'rebaixo nível')
    assert n_drop['status'] == 'measured'
    assert n_drop['values'] == [852.16]
    assert n_drop['delta_m'] == -0.03


def test_laj_isolated_drop_level_not_confused_with_main(tmp_path):
    """Caso 5: L312 em (50, 50), h=13 em (52, 45), h=10 em (10, 10), 852.16 em (12, 12). SA declara h=13, n=852.19.
    A cota única 852.16 está no rebaixo junto a h=10. Não contamina nível nominal (fica E1 ausente) nem gera falso FAIL."""
    dxf_path = _slab_dxf(tmp_path, [
        ('L312', (50, 50)),
        ('h=13', (52, 45)),
        ('h=10', (10, 10)),
        ('852.16', (12, 12)),
    ])
    snapshot = _slab(name='L312', height='13', nivel='852.19')

    report = gate.measure_slabs(dxf_path, snapshot)
    assert gate.errors(report) == []
    n_main = next(c for c in report['contacts'] if c['aspect'] == 'nível')
    assert n_main['status'] == 'uncertain'
    assert 'E1 ausente' in n_main['reason']

    n_drop = next(c for c in report['contacts'] if c['aspect'] == 'rebaixo nível')
    assert n_drop['status'] == 'measured'
    assert n_drop['values'] == [852.16]

    blocked = gate.errors(report, [{'id': 'niveis', 'status': 'pass'}])
    assert len(blocked) == 1 and 'E1 ausente' in blocked[0]


def test_laj_no_written_level_blocks_only_level_pass(tmp_path):
    """Caso 6: L1 em (50, 50), h=12 em (50, 40), sem cota de nível escrita. E1 ausente em nível."""
    dxf_path = _slab_dxf(tmp_path, [
        ('L1', (50, 50)),
        ('h=12', (50, 40)),
    ])
    snapshot = _slab(name='L1', height='12', nivel='852.12')

    report = gate.measure_slabs(dxf_path, snapshot)
    assert gate.errors(report) == []
    n_contact = next(c for c in report['contacts'] if c['aspect'] == 'nível')
    assert n_contact['status'] == 'uncertain'
    assert 'E1 ausente' in n_contact['reason']

    blocked = gate.errors(report, [{'id': 'niveis', 'status': 'pass'}])
    assert len(blocked) == 1 and 'E1 ausente' in blocked[0]
    assert gate.errors(report, [{'id': 'niveis', 'status': 'uncertain'}, {'id': 'identidade_contorno', 'status': 'pass'}]) == []


def test_laj_combined_mtext_annotation(tmp_path):
    """Caso 7: Anotação combinada no mesmo MTEXT: 'L309\\nh=13'. Parser extrai rótulo e espessura."""
    dxf_path = _slab_dxf(
        tmp_path,
        texts=[('852.19', (50, 60))],
        mtexts=[('L309\nh=13', (50, 50))]
    )
    snapshot = _slab(name='L309', height='13', nivel='852.19')

    report = gate.measure_slabs(dxf_path, snapshot)
    assert gate.errors(report) == []
    lbl_c = next(c for c in report['contacts'] if c['aspect'] == 'rótulo')
    assert lbl_c['status'] == 'measured'
    assert lbl_c['values'] == ['L309']

    h_c = next(c for c in report['contacts'] if c['aspect'] == 'espessura')
    assert h_c['status'] == 'measured'
    assert h_c['values'] == [13.0]


def test_laj_foreign_label_divergence(tmp_path):
    """Caso 8: Contorno de L1 contém texto 'L2'. Divergência em identidade_contorno."""
    dxf_path = _slab_dxf(tmp_path, [
        ('L2', (50, 50)),
        ('h=12', (50, 40)),
        ('852.19', (50, 60)),
    ])
    snapshot = _slab(name='L1', height='12', nivel='852.19')

    report = gate.measure_slabs(dxf_path, snapshot)
    errs = gate.errors(report)
    assert any('rótulo contido L2 difere da laje L1' in e for e in errs)
    lbl_c = next(c for c in report['contacts'] if c['aspect'] == 'rótulo')
    assert 'identidade_contorno' in lbl_c['errors']


def test_laj_degenerate_contour(tmp_path):
    """Caso 9: Contorno degenerado (área zero / 2 pontos). Retorna status uncertain com motivo explícito."""
    dxf_path = _slab_dxf(tmp_path, [
        ('L1', (50, 50)),
        ('h=12', (50, 40)),
    ])
    snapshot = _slab(name='L1', height='12', nivel='852.12', points=[[0, 0], [100, 0], [0, 0]])

    report = gate.measure_slabs(dxf_path, snapshot)
    assert any(c['aspect'] == 'contorno' and c['status'] == 'uncertain' for c in report['contacts'])
    blocked = gate.errors(report, [{'id': 'identidade_contorno', 'status': 'pass'}])
    assert any('degenerado' in b for b in blocked)


def test_laj_step_regions_subregions(tmp_path):
    """Caso 10: Laje com slab_steps explícito no snapshot. Região principal e degrau medidos independentemente."""
    step = dict(
        uid='slab-step:L1:BD1',
        points=[[60, 0], [100, 0], [100, 50], [60, 50]],
        height_cm=10.0,
        level_m=852.16
    )
    snapshot = _slab(
        name='L1',
        height='12',
        nivel='852.12',
        points=[[0, 0], [100, 0], [100, 50], [0, 50]],
        slab_steps=[step]
    )
    dxf_path = _slab_dxf(tmp_path, [
        ('L1', (20, 20)),
        ('h=12', (30, 20)),
        ('852.12', (40, 20)),
        ('h=10', (70, 20)),
        ('852.16', (80, 20)),
    ])

    report = gate.measure_slabs(dxf_path, snapshot)
    assert gate.errors(report) == []
    assert all(c['status'] == 'measured' for c in report['contacts'])

    wrong_snap = _slab(
        name='L1',
        height='12',
        nivel='852.12',
        points=[[0, 0], [100, 0], [100, 50], [0, 50]],
        slab_steps=[dict(step, level_m=852.12)]
    )
    wrong_report = gate.measure_slabs(dxf_path, wrong_snap)
    assert any('852,16 (degrau BD1)' in e for e in gate.errors(wrong_report))
