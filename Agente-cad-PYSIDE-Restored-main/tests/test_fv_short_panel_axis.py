"""Short FV panels keep their physical beam axis through clipping and export."""
import copy
import pytest
from portal.app.qa_cad_gate import _fv_rectangle_axis, errors, measure_beams
from src.core.preficha_segments import collect_preficha_segments
from src.core.beam_interpreters.fundo_viga_lateral_ref import resolve_automatic_overlaps_all
from scripts.analise_geral_headless import process_beam_fv


def panel(a, b, horizontal, validated=False):
    points = [(a, 0), (b, 0), (b, 22), (a, 22), (a, 0)]
    if not horizontal:
        points = [(y, x) for x, y in points]
    return dict(points=points, closed=True, type='poly',
                fv_axis_is_horizontal=horizontal, validated=validated,
                ficha={'largura_total_fundo': '22'})


@pytest.mark.parametrize('horizontal', [True, False])
def test_overlap_clipping_and_preficha_preserve_short_panel_axis(horizontal):
    owner = dict(name='OWNER', fv_is_h=horizontal, links={
        'viga_fundo_seg_1_area_segs': {'contour': [panel(0,90,horizontal,True)]}})
    beam = dict(name='BEAM', fv_is_h=horizontal, links={
        'viga_fundo_seg_1_area_segs': {'contour': [panel(0,100,horizontal)]}})
    resolve_automatic_overlaps_all([beam, owner])
    row = collect_preficha_segments([beam])['fundo'][0]
    assert row['length'] == 10
    assert float(row['width']) == 22
    link = beam['links']['viga_fundo_seg_1_area_segs']['contour'][0]
    assert link['len'] == 10
    assert float(link['ficha']['comprimento_total_fundo']) == 10


@pytest.mark.parametrize('horizontal', [True, False])
def test_locked_export_keeps_short_panel_axis_without_touching_polygon(horizontal):
    link = panel(700,710,horizontal,True)
    original = copy.deepcopy(link['points'])
    beam = dict(name='BEAM', links={'viga_fundo_seg_1_area_segs': {'contour': [link]}})
    result = process_beam_fv(beam)
    assert result['segmentos_fundo'][0]['length'] == 10
    assert link['ficha']['largura_total_fundo'] == '22'
    assert link['points'] == original


@pytest.mark.parametrize('horizontal', [True, False])
def test_qa_axis_uses_original_wall_pair_not_longest_bbox(horizontal):
    axis, cross = ('x','y') if horizontal else ('y','x')
    bounds = (700,710,400,422) if horizontal else (400,422,700,710)
    walls = [dict(axis=axis,pos=p,lo=700,hi=710,handle=str(p)) for p in (400,422)]
    walls.append(dict(axis=cross,pos=710,lo=400,hi=422,handle='end'))
    assert _fv_rectangle_axis(bounds,walls) == axis
    # Missing one source wall cannot be silently replaced by a candidate hint.
    assert _fv_rectangle_axis(bounds,walls[1:]) == cross
    # Closed four-sided box is ambiguous; no inferred alternative corridor.
    walls.append(dict(axis=cross,pos=700,lo=400,hi=422,handle='start'))
    assert _fv_rectangle_axis(bounds,walls) == cross


def test_incomplete_original_measurement_is_reported_without_crashing_or_approving():
    report = {'contacts': [dict(unit_path='/collections/fundo/0', item='BEAM',
                               aspect='limite', status='uncertain', errors={})]}
    assert errors(report) == [
        'CAD original /collections/fundo/0 BEAM limite: '
        'medição original inconclusiva sem motivo registrado; revisar evidência']


@pytest.mark.parametrize('horizontal', [True, False])
def test_complete_end_caps_do_not_rotate_interrupted_longitudinal_walls(horizontal):
    axis, cross = ('x','y') if horizontal else ('y','x')
    bounds = (0,789,0,19) if horizontal else (0,19,0,789)
    walls = [dict(axis=axis,pos=0,lo=0,hi=789),
             dict(axis=axis,pos=19,lo=0,hi=402.5),
             dict(axis=axis,pos=19,lo=421.5,hi=789)]
    walls += [dict(axis=cross,pos=p,lo=0,hi=19) for p in (0,789)]
    assert _fv_rectangle_axis(bounds,walls) == axis


@pytest.mark.parametrize('horizontal', [True, False])
def test_original_dxf_short_panel_edges_and_consistency(tmp_path, horizontal):
    import ezdxf
    doc = ezdxf.new()
    def xy(x, y):
        return (x,y) if horizontal else (y,x)
    for y in (0,22):
        doc.modelspace().add_line(xy(0,y),xy(100,y))
    doc.modelspace().add_line(xy(100,0),xy(100,22))
    path = tmp_path/'original.dxf'
    doc.saveas(path)
    row = dict(beam_name='BEAM', segment_label='1', points=panel(90,100,horizontal)['points'],
               length=10, width='22', status='uncertain', level_source='unresolved')
    report = measure_beams(path,{'collections':{'fundo':[row]}})
    evidence = {r['aspect']:r for r in report['contacts']}
    assert evidence['arestas']['coverage'] == [1,1]
    assert not evidence['arestas']['errors']
    assert not evidence['coerência']['errors']
    row['width'] = '10'  # The independent axis must still expose wrong claims.
    report = measure_beams(path,{'collections':{'fundo':[row]}})
    assert any(r['errors'].get('consistencia_alertas') for r in report['contacts'])


def test_union_below_inverted_with_pending_level_is_uncertain_not_divergent(tmp_path):
    # VF301 fundos 8+9 sob a V330: L308 852,12 × L317 852,19; o SA deixa o nível pendente (FV.md).
    import ezdxf
    doc = ezdxf.new()
    for y in (0,22):
        doc.modelspace().add_line((0,y),(100,y))
    path = tmp_path/'original.dxf'
    doc.saveas(path)
    row = dict(beam_name='BEAM', segment_label='8', points=panel(0,100,True)['points'], length=100, width='22',
               status='valid', level='', level_source='unresolved_local_slab_references',
               level_slabs=['L308','L317'], merged_source_segments=[dict(level='852.12'), dict(level='852.19')])
    evidence = {r['aspect']:r for r in measure_beams(path,{'collections':{'fundo':[row]}})['contacts']}
    assert not evidence['coerência']['errors']
    assert evidence['nível']['status'] == 'uncertain' and evidence['nível']['blocks_promotion'] and '852.12' in evidence['nível']['reason']
    row.pop('merged_source_segments')  # Sem união declarada, nível vazio continua incoerente.
    evidence = {r['aspect']:r for r in measure_beams(path,{'collections':{'fundo':[row]}})['contacts']}
    assert 'status valid sem nível' in evidence['coerência']['errors']['consistencia_alertas']
