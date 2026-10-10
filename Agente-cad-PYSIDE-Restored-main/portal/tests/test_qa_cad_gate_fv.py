import copy

import ezdxf

from portal.app import qa_cad_gate as g


def _dxf(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    for y in (0, 19):  # V1 desenhada interrompida onde a V2 (mais funda) cruza
        msp.add_line((0, y), (100, y))
        msp.add_line((119, y), (300, y))
    msp.add_line((0, 0), (0, 19))
    msp.add_line((300, 0), (300, 19))
    for x in (100, 119):
        msp.add_line((x, -80), (x, 0))
        msp.add_line((x, 19), (x, 90))
    msp.add_text('V1', dxfattribs={'insert': (20, 22), 'height': 10})
    msp.add_text('19/55', dxfattribs={'insert': (200, 22), 'height': 10})
    path = tmp_path / 'pav.dxf'
    doc.saveas(path)
    return path


def _seg(label, x0, x1, width='19', y0=0, y1=19):
    return dict(beam_name='V1', segment_label=label, width=width, length=abs(x1-x0) if abs(x1-x0) >= abs(y1-y0) else abs(y1-y0),
                points=[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]])


SNAP = dict(classe='FV', collections={'fundo': [_seg('1', 0, 100), _seg('2', 119, 300)]})


def _errors(path, snap):
    return {(c['item'], c['aspect']): c['errors'] for c in g.measure_beams(path, snap)['contacts'] if c['errors']}


def test_correct_segments_measure_without_errors(tmp_path):
    report = g.measure_beams(_dxf(tmp_path), SNAP)
    assert not [c for c in report['contacts'] if c['errors']]
    status = {(c['item'], c['aspect']): c['status'] for c in report['contacts']}
    assert all(status[(f'V1 seg {s}', a)] == 'measured'
               for s in '12' for a in ('arestas', 'extremo início', 'extremo fim', 'seção', 'sobreposição'))


def test_rectangle_offset_by_one_width_fails_identity(tmp_path):
    snap = copy.deepcopy(SNAP)
    snap['collections']['fundo'][1] = _seg('2', 119, 300, y0=19, y1=38)
    errors = _errors(_dxf(tmp_path), snap)
    assert 'identidade_contorno' in errors[('V1 seg 2', 'arestas')]


def test_declared_width_differs_from_written_section(tmp_path):
    snap = copy.deepcopy(SNAP)
    snap['collections']['fundo'][0]['width'] = '14'
    assert 'dimensoes' in _errors(_dxf(tmp_path), snap)[('V1 seg 1', 'seção')]


def test_end_cut_by_label_instead_of_walls_fails_limits(tmp_path):
    snap = copy.deepcopy(SNAP)
    snap['collections']['fundo'][0] = _seg('1', 0, 87)
    errors = _errors(_dxf(tmp_path), snap)
    assert set(errors[('V1 seg 1', 'extremo fim')]) == {'apoios_limites', 'dimensoes'}


def test_overlapping_segments_fail_inventory(tmp_path):
    snap = copy.deepcopy(SNAP)
    snap['collections']['fundo'].append(_seg('3', 200, 300))
    errors = _errors(_dxf(tmp_path), snap)
    assert 'inventario_segmentos' in errors[('V1 seg 3', 'sobreposição')]


def test_unmeasured_aspects_never_block_without_pass_but_block_a_pass(tmp_path):
    snap = copy.deepcopy(SNAP)
    snap['collections']['fundo'][0]['points'] = [[0, 0], [100, 5], [100, 24], [0, 19]]
    report = g.measure_beams(_dxf(tmp_path), snap)
    assert g.errors(report) == []
    assert g.errors(report, [{'id': 'dimensoes', 'status': 'pass'}])


def _t_dxf(tmp_path, own='19/55', arriving='19/55', label=True, name='t'):
    """V1 em x 0–300; viga vertical chega por cima em x 100–119 (T); aresta de baixo contínua."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (300, 0))
    msp.add_line((0, 19), (100, 19))
    msp.add_line((119, 19), (300, 19))
    msp.add_line((0, 0), (0, 19))
    msp.add_line((300, 0), (300, 19))
    for x in (100, 119):
        msp.add_line((x, 19), (x, 300))
    if label:
        msp.add_text('V1', dxfattribs={'insert': (20, 22), 'height': 10})
    msp.add_text(own, dxfattribs={'insert': (200, 22), 'height': 10})
    if arriving:
        msp.add_text(arriving, dxfattribs={'insert': (112, 150), 'height': 10, 'rotation': 90})
    path = tmp_path / f'{name}.dxf'
    doc.saveas(path)
    return path


def _ends(path, snap):
    return {(c['item'], c['aspect']): c for c in g.measure_beams(path, snap)['contacts'] if 'extremo' in c['aspect']}


GAP = dict(classe='FV', collections={'fundo': [_seg('1', 0, 100), _seg('2', 119, 300)]})
JOINT = dict(classe='FV', collections={'fundo': [_seg('1', 0, 100), _seg('2', 100, 300)]})


def test_same_depth_t_arriving_beam_crosses_d90(tmp_path):
    ends = _ends(_t_dxf(tmp_path), GAP)
    for key in (('V1 seg 1', 'extremo fim'), ('V1 seg 2', 'extremo início')):
        assert ends[key]['status'] == 'measured' and not ends[key]['errors']
        assert 'D-90' in ends[key]['limit']


def test_deeper_beam_interrupted_by_shallower_fails(tmp_path):
    ends = _ends(_t_dxf(tmp_path, arriving='19/50'), GAP)
    assert 'apoios_limites' in ends[('V1 seg 1', 'extremo fim')]['errors']


def test_deeper_beam_passes_with_panel_change(tmp_path):
    ends = _ends(_t_dxf(tmp_path, arriving='19/50'), JOINT)
    for key in (('V1 seg 1', 'extremo fim'), ('V1 seg 2', 'extremo início')):
        assert ends[key]['status'] == 'measured' and not ends[key]['errors']
        assert 'FV.md §4' in ends[key]['limit']


def test_shallower_beam_joined_under_deeper_arrival_fails(tmp_path):
    ends = _ends(_t_dxf(tmp_path, own='19/50', arriving='19/55'), JOINT)
    assert 'apoios_limites' in ends[('V1 seg 1', 'extremo fim')]['errors']


def test_t_without_measured_depths_stays_uncertain(tmp_path):
    for path, snap in ((_t_dxf(tmp_path, arriving=None), GAP), (_t_dxf(tmp_path, name='t2'), JOINT)):
        end = _ends(path, snap)[('V1 seg 1', 'extremo fim')]
        assert end['status'] == 'uncertain' and not end['errors']


def test_single_section_without_any_beam_label_is_measured(tmp_path):
    report = g.measure_beams(_t_dxf(tmp_path, label=False), GAP)
    dims = [c for c in report['contacts'] if c['aspect'] == 'seção']
    assert all(c['status'] == 'measured' and c.get('basis') for c in dims)


def test_end_over_crossing_beam_band_fails_limits(tmp_path):
    snap = copy.deepcopy(SNAP)
    snap['collections']['fundo'][1] = _seg('2', 100, 300)
    errors = _errors(_dxf(tmp_path), snap)
    assert 'apoios_limites' in errors[('V1 seg 2', 'extremo início')]


def _pillar_dxf(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    for y in (0, 19):
        msp.add_line((0, y), (300, y))
    msp.add_line((0, 0), (0, 19))
    msp.add_line((300, 0), (300, 19))
    msp.add_lwpolyline([(100, -10), (119, -10), (119, 29), (100, 29)], close=True)  # pilar maior que a viga
    msp.add_text('V1', dxfattribs={'insert': (20, 22), 'height': 10})
    msp.add_text('19/55', dxfattribs={'insert': (200, 22), 'height': 10})
    path = tmp_path / 'pilar.dxf'
    doc.saveas(path)
    return path


def test_end_on_far_face_of_crossed_element_is_not_certified(tmp_path):
    path = _pillar_dxf(tmp_path)
    snap = dict(classe='FV', collections={'fundo': [_seg('1', 0, 119), _seg('2', 119, 300)]})
    end = _ends(path, snap)[('V1 seg 1', 'extremo fim')]
    assert end['status'] == 'uncertain' and not end['errors']
    snap = dict(classe='FV', collections={'fundo': [_seg('1', 0, 100), _seg('2', 119, 300)]})
    end = _ends(path, snap)[('V1 seg 1', 'extremo fim')]
    assert end['status'] == 'measured' and not end['errors']


def _interior_dxf(tmp_path, name, draw, original_only=lambda m: None):
    """Viga V1 0–300 contínua (19/55) com algo desenhado no interior do fundo.

    Grava recorte + DXF original Fase-1 (como no 13_PAV); `original_only` só vai ao original,
    porque o recorte descarta SOLID.
    """
    import json
    crop_dir = tmp_path / name / 'Fase-2_Triagem' / 'recortes' / 'P'
    raw_dir = tmp_path / name / 'Fase-1_Ingestao' / 'Brutos'
    crop_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    for path, extra in ((crop_dir / 'torre_1.dxf', None), (raw_dir / 'P.dxf', original_only)):
        doc = ezdxf.new()
        doc.linetypes.add('TRACO', pattern=[2.0, 1.5, -0.5])
        msp = doc.modelspace()
        for y in (0, 19):
            msp.add_line((0, y), (300, y))
        for x in (0, 300):
            msp.add_line((x, 0), (x, 19))
        msp.add_text('V1', dxfattribs={'insert': (20, 22), 'height': 10})
        msp.add_text('19/55', dxfattribs={'insert': (200, 22), 'height': 10})
        draw(msp)
        if extra:
            extra(msp)
        doc.saveas(path)
    (crop_dir / 'crop_result.json').write_text(json.dumps({'dxf_bruto': 'C:/obra/P.dxf'}), encoding='utf-8')
    return crop_dir / 'torre_1.dxf'


ONE = dict(classe='FV', collections={'fundo': [_seg('1', 0, 300)]})


def _aspect(path, aspect, snap=ONE):
    return next(c for c in g.measure_beams(path, snap)['contacts'] if c['aspect'] == aspect)


def test_empty_interior_proves_no_exception(tmp_path):
    c = _aspect(_interior_dxf(tmp_path, 'vazio', lambda m: None), 'aberturas')
    assert c['status'] == 'measured' and not c['errors']


def test_dashed_axis_through_fundo_is_annotation(tmp_path):
    path = _interior_dxf(tmp_path, 'eixo', lambda m: m.add_line((150, -200), (150, 200), dxfattribs={'linetype': 'TRACO'}))
    assert _aspect(path, 'aberturas')['status'] == 'measured'


def test_dashed_figure_inside_fundo_is_not_annotation(tmp_path):
    def draw(m):
        m.add_lwpolyline([(140, 5), (160, 5), (160, 14), (140, 14)], close=True, dxfattribs={'linetype': 'TRACO'})
    assert _aspect(_interior_dxf(tmp_path, 'projecao', draw), 'aberturas')['status'] == 'uncertain'


def test_solid_stroke_inside_fundo_blocks_pass(tmp_path):
    c = _aspect(_interior_dxf(tmp_path, 'furo', lambda m: m.add_line((120, 3), (180, 16))), 'aberturas')
    assert c['status'] == 'uncertain' and c['element_handles']
    assert g.errors(dict(contacts=[c]), [{'id': 'lajes_aberturas', 'status': 'pass'}])


def _pillar(cross):
    def draw(m):
        m.add_lwpolyline([(140, 0), (159, 0), (159, 19), (140, 19)], close=True)
        if cross:
            m.add_line((140, 0), (159, 19))
            m.add_line((140, 19), (159, 0))
    return draw


def _with_convention(monkeypatch):
    from portal.app import item_semantics

    def source(path):
        doc = ezdxf.readfile(path)
        lines = [dict(start=list(e.dxf.start), end=list(e.dxf.end), layer=e.dxf.layer) for e in doc.modelspace().query('LINE')]
        return dict(lines=lines, polylines=[]), {'NASCE': {'label': 'NASCE', 'sig': 'CROSS'}}
    monkeypatch.setattr(item_semantics, 'pillar_source', source)


def test_nasce_pillar_inside_fundo_is_ignored_d65(tmp_path, monkeypatch):
    _with_convention(monkeypatch)
    c = _aspect(_interior_dxf(tmp_path, 'nasce', _pillar(True)), 'aberturas')
    assert c['status'] == 'measured', c


def test_pillar_without_nasce_symbol_inside_fundo_is_not_certified(tmp_path, monkeypatch):
    _with_convention(monkeypatch)
    assert _aspect(_interior_dxf(tmp_path, 'solido', _pillar(False)), 'aberturas')['status'] == 'uncertain'


def test_x_pillar_without_convention_is_not_certified(tmp_path, monkeypatch):
    from portal.app import item_semantics
    monkeypatch.setattr(item_semantics, 'pillar_source', lambda path: ({'lines': [], 'polylines': []}, {}))
    assert _aspect(_interior_dxf(tmp_path, 'semconv', _pillar(True)), 'aberturas')['status'] == 'uncertain'


def test_declared_length_differs_from_contour_fails_consistency(tmp_path):
    snap = copy.deepcopy(ONE)
    snap['collections']['fundo'][0]['length'] = 280
    c = _aspect(_interior_dxf(tmp_path, 'coer', lambda m: None), 'coerência', snap)
    assert 'consistencia_alertas' in c['errors']


def _tags_case(tmp_path):
    """DXF com faixas horizontais e textos únicos + SVG SA desenhado pelo renderer real."""
    from src.ui.widgets.fv_hifi_n1_render import render_fv_hifi_n1_svg
    doc = ezdxf.new()
    msp = doc.modelspace()
    lines, texts = [], []
    for k in range(6):  # 6 vigas paralelas = 12 linhas horizontais
        for j, y in enumerate((100*k, 100*k+19)):
            x0, x1 = -3*k-j, 400+5*k+2*j  # vãos distintos: cada linha é reencontrável no SVG
            msp.add_line((x0, y), (x1, y))
            lines.append(dict(start=[x0, y], end=[x1, y]))
        msp.add_text(f'V{k+1}', dxfattribs={'insert': (60+50*k, 100*k+30), 'height': 10})
        texts.append(dict(text=f'V{k+1}', pos=[60+50*k, 100*k+30], height=10))
    path = tmp_path / 'tags.dxf'
    doc.saveas(path)
    segs = [dict(beam_name='V1', segment_label=str(i+1), width='19', length=190,
                 points=[[x0, 0], [x0+190, 0], [x0+190, 19], [x0, 19], [x0, 0]]) for i, x0 in enumerate((0, 210))]
    svg = render_fv_hifi_n1_svg(dict(lines=lines, texts=texts),
                                [dict(points=s['points'], label=s['segment_label']) for s in segs], mode='contextual')
    return path, dict(classe='FV', collections={'fundo': segs}), svg


def test_tags_point_into_own_segment(tmp_path):
    path, snap, svg = _tags_case(tmp_path)
    contacts = g.measure_fv_tags(path, snap, svg)
    assert [(c['status'], c['errors']) for c in contacts] == [('measured', {}), ('measured', {})]


def test_tags_from_stale_render_fail(tmp_path):
    path, snap, svg = _tags_case(tmp_path)
    moved = copy.deepcopy(snap)
    moved['collections']['fundo'][0]['points'] = [[x, y+19] for x, y in moved['collections']['fundo'][0]['points']]
    assert 'tags_lideres' in g.measure_fv_tags(path, moved, svg)[0]['errors']
    swapped = copy.deepcopy(snap)
    rows = swapped['collections']['fundo']
    rows[0]['segment_label'], rows[1]['segment_label'] = '2', '1'
    assert all('tags_lideres' in c['errors'] for c in g.measure_fv_tags(path, swapped, svg))


def test_evidence_report_carries_the_sa_tags(tmp_path, monkeypatch):
    from portal.app import ficha_reader
    path, snap, svg = _tags_case(tmp_path)
    monkeypatch.setattr(ficha_reader, '_fonte_estrutural_producao', lambda *_a, **_k: path)
    monkeypatch.setattr(ficha_reader, 'ler_estado_pavimento', lambda *_a, **_k: {'slabs': []})
    report = g.for_evidence(tmp_path, '13_PAV', snap, svg)
    tags = [c for c in report['contacts'] if c['aspect'] == 'tag']
    assert [c['status'] for c in tags] == ['measured', 'measured']
    assert all(not c['errors'] for c in tags)


def test_evidence_without_svg_leaves_tags_out(tmp_path, monkeypatch):
    from portal.app import ficha_reader
    path, snap, _svg = _tags_case(tmp_path)
    monkeypatch.setattr(ficha_reader, '_fonte_estrutural_producao', lambda *_a, **_k: path)
    monkeypatch.setattr(ficha_reader, 'ler_estado_pavimento', lambda *_a, **_k: {'slabs': []})
    report = g.for_evidence(tmp_path, '13_PAV', snap, None)
    assert report and not any(c['aspect'] == 'tag' for c in report['contacts'])


def test_passing_a_stale_tag_contradicts_the_dxf(tmp_path, monkeypatch):
    from portal.app import ficha_reader, qa_cad_gate
    path, snap, svg = _tags_case(tmp_path)
    monkeypatch.setattr(ficha_reader, '_fonte_estrutural_producao', lambda *_a, **_k: path)
    monkeypatch.setattr(ficha_reader, 'ler_estado_pavimento', lambda *_a, **_k: {'slabs': []})
    moved = copy.deepcopy(snap)
    moved['collections']['fundo'][0]['points'] = [[x, y + 19] for x, y in moved['collections']['fundo'][0]['points']]
    report = g.for_evidence(tmp_path, '13_PAV', moved, svg)
    scoped = dict(report, contacts=[c for c in report['contacts'] if c['unit_path'] == '/collections/fundo/0'])
    messages = qa_cad_gate.errors(scoped, [{'id': 'tags_lideres', 'status': 'pass'}])
    assert any('tags' in message or 'líder' in message or 'S' in message for message in messages)


def test_tags_without_measured_frame_are_not_certified(tmp_path):
    path, snap, svg = _tags_case(tmp_path)
    blind = svg.replace('>V1<', '>?<').replace('>V2<', '>?<').replace('>V3<', '>?<').replace('>V4<', '>?<')
    assert {c['status'] for c in g.measure_fv_tags(path, snap, blind)} == {'uncertain'}


def _t_solids(msp, x0, y_lo, y_hi, stem=12, length=55):
    """T preenchido: haste atravessa a faixa e a barra segue ao longo dela."""
    y_mid0, y_mid1 = min(y_lo, y_hi), max(y_lo, y_hi)
    msp.add_solid([(x0, y_mid0 - 30), (x0 + stem, y_mid0 - 30), (x0 + stem, y_mid1 + 30), (x0, y_mid1 + 30)])
    msp.add_solid([(x0 + stem, y_mid0), (x0 + length, y_mid0), (x0 + length, y_mid1), (x0 + stem, y_mid1)])


def test_filled_t_with_matching_cota_is_section_view(tmp_path):
    def original(m):
        _t_solids(m, 100, 0, 19)
        m.add_text('55', dxfattribs={'insert': (120, -40), 'height': 8})
    c = _aspect(_interior_dxf(tmp_path, 'visao', lambda m: None, original), 'aberturas')
    assert c['status'] == 'measured' and not c['errors'], c
    assert c['visao_corte_handles']
    assert 'visão corte' in c['basis']


def test_section_view_outline_does_not_open_the_beam(tmp_path):
    def draw(m):
        m.add_line((100, 0), (100, 19))
        m.add_line((155, 0), (155, 19))
        m.add_lwpolyline([(100, -30), (112, -30), (112, 0), (155, 0), (155, 19),
                          (112, 19), (112, 49), (100, 49), (100, -30)])

    def original(m):
        _t_solids(m, 100, 0, 19)
        m.add_text('55', dxfattribs={'insert': (120, -40), 'height': 8})

    c = _aspect(_interior_dxf(tmp_path, 'visao_contorno', draw, original), 'aberturas')
    assert c['status'] == 'measured' and not c['element_handles'], c
    assert c['visao_corte_handles']


def test_filled_t_without_cota_is_section_view(tmp_path):
    c = _aspect(_interior_dxf(tmp_path, 'visao_sem_cota', lambda m: None, lambda m: _t_solids(m, 100, 0, 19)), 'aberturas')
    assert c['status'] == 'measured' and c.get('visao_corte_handles'), c


def test_section_label_does_not_block_section_view(tmp_path):
    def original(m):
        _t_solids(m, 100, 0, 19)
        m.add_text('19/55', dxfattribs={'insert': (120, -40), 'height': 8})
    c = _aspect(_interior_dxf(tmp_path, 'visao_secao', lambda m: None, original), 'aberturas')
    assert c['status'] == 'measured' and c.get('visao_corte_handles'), c


def test_one_sided_t_is_section_view(tmp_path):
    def original(m):
        m.add_solid([(100, 0), (112, 0), (112, 49), (100, 49)])
        m.add_solid([(112, 0), (167, 0), (167, 19), (112, 19)])
    c = _aspect(_interior_dxf(tmp_path, 'visao_um_lado', lambda m: None, original), 'aberturas')
    assert c['status'] == 'measured' and c.get('visao_corte_handles'), c


def test_deep_section_flange_is_section_view(tmp_path):
    def original(m):
        m.add_solid([(100, -30), (133, -30), (133, 49), (100, 49)])
        m.add_solid([(133, 0), (193, 0), (193, 19), (133, 19)])
    c = _aspect(_interior_dxf(tmp_path, 'visao_120', lambda m: None, original), 'aberturas')
    assert c['status'] == 'measured' and c.get('visao_corte_handles'), c


def test_pillar_fill_across_the_beam_is_not_section_view(tmp_path):
    def original(m):
        m.add_solid([(100, -40), (140, -40), (140, 59), (100, 59)])
    c = _aspect(_interior_dxf(tmp_path, 'pilar_cheio', lambda m: None, original), 'aberturas')
    assert c['status'] == 'uncertain' and 'visao_corte_handles' not in c


def test_filled_t_on_vertical_beam_is_section_view(tmp_path):
    import json
    crop_dir = tmp_path / 'visao_y' / 'Fase-2_Triagem' / 'recortes' / 'P'
    raw_dir = tmp_path / 'visao_y' / 'Fase-1_Ingestao' / 'Brutos'
    crop_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    for path, extra in ((crop_dir / 'torre_1.dxf', False), (raw_dir / 'P.dxf', True)):
        doc = ezdxf.new()
        msp = doc.modelspace()
        for x in (0, 19):
            msp.add_line((x, 0), (x, 300))
        for y in (0, 300):
            msp.add_line((0, y), (19, y))
        msp.add_text('V1', dxfattribs={'insert': (22, 20), 'height': 10})
        msp.add_text('19/55', dxfattribs={'insert': (22, 200), 'height': 10})
        if extra:
            msp.add_solid([(0 - 30, 100), (19 + 30, 100), (19 + 30, 112), (0 - 30, 112)])
            msp.add_solid([(0, 112), (19, 112), (19, 155), (0, 155)])
            msp.add_text('55', dxfattribs={'insert': (-40, 120), 'height': 8})
        doc.saveas(path)
    (crop_dir / 'crop_result.json').write_text(json.dumps({'dxf_bruto': 'C:/obra/P.dxf'}), encoding='utf-8')
    snap = dict(classe='FV', collections={'fundo': [_seg('1', 0, 19, y0=0, y1=300)]})
    c = _aspect(crop_dir / 'torre_1.dxf', 'aberturas', snap)
    assert c['status'] == 'measured' and c.get('visao_corte_handles'), c


def test_stroke_beside_section_view_stays_uncertified(tmp_path):
    def original(m):
        _t_solids(m, 100, 0, 19)
        m.add_text('55', dxfattribs={'insert': (120, -40), 'height': 8})
    c = _aspect(_interior_dxf(tmp_path, 'visao_traco', lambda m: m.add_line((140, 3), (180, 16)), original), 'aberturas')
    assert c['status'] == 'uncertain' and c['element_handles']
    assert c['visao_corte_handles']


def test_fill_only_in_original_inside_fundo_is_not_certified(tmp_path):
    path = _interior_dxf(tmp_path, 'solido_original', lambda m: None,
                         lambda m: m.add_solid([(200, 0), (255, 0), (200, 19), (255, 19)]))
    c = _aspect(path, 'aberturas')
    assert c['status'] == 'uncertain' and c['element_handles']


def test_without_original_dxf_absence_is_not_proven(tmp_path):
    path = _interior_dxf(tmp_path, 'sem_original', lambda m: None)
    (path.parent / 'crop_result.json').unlink()
    assert _aspect(path, 'aberturas')['status'] == 'uncertain'
