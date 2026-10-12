"""A break line only invalidates the cut measurements that cross it."""
from shapely.geometry import LineString, Polygon, box, mapping
from shapely.ops import unary_union

from portal.app.preprocessamento.segment_levels import (
    break_spares_top, cut_owner_level, cut_region_source)

# Upright T: wings 0..80 (top 60, bottom 47), stem 30..50 down to 0 (shortened deep beam).
T = Polygon([(0, 60), (80, 60), (80, 47), (50, 47), (50, 0), (30, 0), (30, 47), (0, 47)])
STEM_BREAK = unary_union([LineString([(25, 20), (55, 26)]), LineString([(25, 23), (55, 29)])])


def test_break_in_stem_keeps_top_offset():
    read = break_spares_top(T, [STEM_BREAK], 0.0)
    assert read['drawn_top_offsets_cm'] == [0.0] and read['wing_bottom_above_break_cm'] > 0


def test_break_reaching_wings_rejects():
    high = unary_union([LineString([(25, 45), (55, 51)])])
    assert break_spares_top(T, [high], 0.0) is None


def test_stated_offset_must_be_drawn():
    assert break_spares_top(T, [STEM_BREAK], 7.0) is None


def test_beam_above_slab_wing_measured_from_outline():
    # Stem rises 7 above both wings.
    raised = Polygon([(0, 53), (30, 53), (30, 60), (50, 60), (50, 53), (80, 53), (80, 40),
                      (50, 40), (50, 0), (30, 0), (30, 40), (0, 40)])
    assert break_spares_top(raised, [STEM_BREAK], 7.0)['drawn_top_offsets_cm'] == [7.0]


def test_edge_beam_l_section():
    l_section = Polygon([(0, 60), (60, 60), (60, 47), (20, 47), (20, 0), (0, 0)])
    brk = unary_union([LineString([(-5, 20), (25, 26)])])
    assert break_spares_top(l_section, [brk], 0.0)['drawn_top_offsets_cm'] == [0.0]


def test_section_without_wing_rejects():
    assert break_spares_top(box(0, 0, 20, 60), [STEM_BREAK], 0.0) is None


def region(rid, value, geom):
    return dict(fact_id='S:'+rid, field='slab_region_level', region_id=rid, value=value,
                status='sa_evidence', confidence_pct=95, region_geometry=mapping(geom))


def test_multipart_slab_cut_reads_touched_region():
    item = dict(levels=[region('principal', 852.19, box(0, 0, 100, 100)),
                        region('step', 852.16, box(120, 0, 200, 100))])
    assert cut_region_source(item, box(100, 40, 110, 60))['region_id'] == 'principal'


def test_multipart_slab_cut_touching_two_levels_rejects():
    item = dict(levels=[region('principal', 852.19, box(0, 0, 100, 100)),
                        region('step', 852.16, box(100, 0, 200, 100))])
    assert cut_region_source(item, box(95, 40, 105, 60)) is None


def test_cut_on_voted_principal_ignores_the_rebaixo_scalar():
    principal = region('principal', 855.25, box(0, 0, 100, 80))
    principal.update(method='slab_neighbor_continuity_without_step_cut', status='inferred', confidence_pct=85)
    step = region('step', 855.22, box(0, 80, 40, 140))
    scalar = dict(fact_id='S:slab', field='slab_level', value=855.22, method='cad_level_inside_slab',
                  status='sa_evidence', confidence_pct=95)
    item = dict(levels=[scalar, principal, step])
    own = cut_owner_level('S', box(90, 10, 110, 30), {'S': scalar}, {'S': item})
    assert own['region_id'] == 'principal' and own['value'] == 855.25


def test_measured_step_does_not_replace_the_scalar():
    step = region('step', 852.16, box(0, 60, 40, 100))
    step.update(method='slab_step_cut_scoped_level', status='inferred')
    scalar = dict(fact_id='S:slab', field='slab_level', value=852.19,
                  method='slab_neighbor_continuity_without_step_cut', status='inferred', confidence_pct=85)
    item = dict(levels=[scalar, step])
    own = cut_owner_level('S', box(5, 70, 15, 90), {'S': scalar}, {'S': item})
    assert own is scalar
