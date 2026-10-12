"""Physical contact coverage must survive rotation of the source drawing."""
import pytest
from shapely.affinity import rotate, translate
from shapely.geometry import box, LineString, MultiLineString, Point, Polygon

from portal.app.preprocessamento.segment_levels import projected_coverage


@pytest.mark.parametrize('angle', [0, 30, 43.42729839142739, 90, 137, 180])
def test_rotated_beam_keeps_longitudinal_coverage(angle):
    target = box(0, 0, 125, 14)
    span = LineString([(0, 14), (102, 14)])
    def moved(shape):
        return translate(rotate(shape, angle, origin=(0, 0)), 500000, -700000)
    assert projected_coverage(moved(target), [moved(span)]) == pytest.approx(102/125)


@pytest.mark.parametrize('angle', [0, 43, 90])
def test_disconnected_contacts_preserve_gap_and_duplicates(angle):
    target = box(0, 0, 100, 14)
    span = MultiLineString([[(0, 14), (30, 14)], [(70, 14), (100, 14)]])
    target, span = [rotate(shape, angle, origin=(0, 0)) for shape in (target, span)]
    assert projected_coverage(target, [span, span]) == pytest.approx(.6)


@pytest.mark.parametrize('angle', [0, 43, 90])
def test_short_contact_remains_below_existing_eighty_percent_gate(angle):
    target = box(0, 0, 100, 14)
    span = LineString([(0, 14), (79, 14)])
    target, span = [rotate(shape, angle, origin=(0, 0)) for shape in (target, span)]
    assert projected_coverage(target, [span]) == pytest.approx(.79)
    assert projected_coverage(target, [span]) < .8


def test_line_target_clips_outside_station_and_unions_overlap():
    target = LineString([(0, 0), (0, 100)])
    spans = [LineString([(0, -10), (0, 50)]), LineString([(0, 30), (0, 80)])]
    assert projected_coverage(target, spans) == pytest.approx(.8)
    assert projected_coverage(target, [Point(0, 50)]) == 0


def test_empty_and_degenerate_targets_have_no_coverage():
    assert projected_coverage(Point(0, 0), [box(-1, -1, 1, 1)]) == 0
    assert projected_coverage(box(0, 0, 100, 14), []) == 0


def test_oblique_chamfered_fund_and_local_l417_contact():
    # Physical diagonal profile frozen from the audited 14_PAV source. The
    # caller still owns datum/identity validation; this test checks stations.
    target = Polygon([
        (2364.8367228341162,2070), (2364.8377504189652,2069.999027333486),
        (2364.8553015752123,2069.982414182781), (2359.262649304637,2055.998990236546),
        (2269.472612121236,2140.9902807567755), (2269.486438,2141.025),
        (2270.9855748188093,2144.789599468077), (2283.3775804663323,2150.525),
        (2289.7025529326647,2141.025), (2289.828243575052,2140.999719480752)])
    side = LineString([(2364.8377504189652,2069.999027333486),
                       (2290.595199546205,2140.2737527721365)])
    span = side.intersection(target.buffer(1))
    assert projected_coverage(target, [span]) == pytest.approx(.8168499746213962)
    assert projected_coverage(target, [span]) > .8
