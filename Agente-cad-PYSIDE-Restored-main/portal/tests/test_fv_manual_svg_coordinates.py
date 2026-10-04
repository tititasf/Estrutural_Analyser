from portal.app.fv_operations import normalize_manual_sa_svg
from pathlib import Path


def test_matplotlib_points_overlay_maps_to_structural_units_without_changing_points():
    svg = ('<svg width="864pt" height="391.68pt" viewBox="0 0 864 391.68">'
           '<path id="structural" d="M85.32 256.32L120 294"/>'
           '<g class="fv-web-human-sa-layer"><g data-fv-seg="1">'
           '<polygon points="118.5,356 166,409"/></g></g></svg>')
    fixed = normalize_manual_sa_svg(svg)
    assert 'scale(0.72 0.72)' in fixed
    assert 'points="118.5,356 166,409"' in fixed
    assert 'd="M85.32 256.32L120 294"' in fixed
    assert 'stroke-width:2px!important' in fixed
    assert normalize_manual_sa_svg(fixed) == fixed
    # First vertex falls on the structural point, not below the drawing.
    assert abs(118.5 * .72 - 85.32) < 1e-9
    assert abs(356 * .72 - 256.32) < 1e-9


def test_nonzero_viewbox_and_pixel_svg():
    svg = ('<svg width="100px" height="50px" viewBox="10 20 200 100">'
           '<g class="fv-web-human-sa-layer"></g></svg>')
    assert 'translate(10 20) scale(2 2)' in normalize_manual_sa_svg(svg)


def test_automatic_and_agent_svgs_are_untouched():
    svg = '<svg width="100pt" height="50pt" viewBox="0 0 100 50"><polygon/></svg>'
    assert normalize_manual_sa_svg(svg) == svg


def test_focus_converts_local_bbox_to_root_coordinates():
    source = (Path(__file__).parents[1] / 'app/static/fv_ficha.js').read_text(encoding='utf-8')
    assert 'svg.getScreenCTM().inverse().multiply(target.getScreenCTM())' in source
    assert 'point.matrixTransform(matrix)' in source
