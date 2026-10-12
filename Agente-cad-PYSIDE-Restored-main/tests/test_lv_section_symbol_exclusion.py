"""Section-view entities cannot masquerade as walls or section dividers."""
import pytest
from src.core.lv_beam_scene import LvScene, _EdgeIndex, _sections, split_dimension_geometry
from src.core.beam_interpreters.lateral_viga_cells import segment_cell


@pytest.mark.parametrize('horizontal', [True, False])
@pytest.mark.parametrize('offset', [0, 3000])
def test_cut_divider_cannot_override_real_section_transition(horizontal, offset):
    point = lambda a, t: [a+offset, t+offset] if horizontal else [t+offset, a+offset]
    source = [dict(start=point(a, 0), end=point(a, 19), layer=layer)
              for a, layer in [(290, 'FACE-VIGA'), (250, 'MTH-LINHA-SEÇÃO'),
                               (270, 'SECTION-VIEW')]]
    edges, dimensions = split_dimension_geometry(source)
    assert len(edges) == 1 and not dimensions
    scene = LvScene('VX', horizontal, offset, offset+19, offset, offset+400)
    labels = [dict(pos=point(a, 25), text=f'19/{h}', section=(19, h),
                   rotation=0 if horizontal else 90) for a, h in [(100,120),(350,50)]]
    # A stale derived reference must lose to an actual source divider.
    beam = dict(links={'viga_fundo_seg_1_area_segs': dict(contour=[dict(points=[
        point(0,0), point(320,0), point(320,19), point(0,19)])])})
    _sections(scene, beam, labels, [], _EdgeIndex(edges))
    assert scene.sections[0]['end'] == 290+offset
    assert scene.sections[0]['end_source'] == 'structural_transverse_divider'
    assert len(segment_cell(scene, 'A', 'para')) == 2


def test_coincident_real_wall_is_preserved_without_blanket_spatial_mask():
    source = [dict(start=[0,0], end=[100,0], layer=layer)
              for layer in ['FACE-VIGA', 'LINHA-CORTE']]
    edges, _ = split_dimension_geometry(source)
    assert edges == [(0.,0.,100.,0.)]


def test_cut_polyline_cannot_supply_a_fake_beam_band():
    edges, dimensions = split_dimension_geometry([
        dict(points=[[0,0],[200,0],[200,19],[0,19],[0,0]], layer='CUT-VIEW')])
    assert not edges and not dimensions


def test_cached_portal_dividers_obey_same_source_filter(tmp_path):
    import ezdxf
    from src.core.fv_inverted_crossings import structural_lines_from_dxf
    doc = ezdxf.new()
    for layer in ['FACE-VIGA', 'LINHA-CORTE']:
        doc.layers.new(layer)
        doc.modelspace().add_line((30,0), (30,19), dxfattribs={'layer': layer})
    path = tmp_path/'source.dxf'
    doc.saveas(path)
    assert structural_lines_from_dxf(str(path), path.stat().st_mtime_ns) == ((30.,0.,30.,19.),)
