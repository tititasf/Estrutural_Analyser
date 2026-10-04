import math
import subprocess
from pathlib import Path

import ezdxf
import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from src.core.fv_generation_contract import build_fv_generation_contract
from src.core.fv_dimension_presentation import format_fv_n3_dimensions


@pytest.mark.parametrize('angle', [0, 43, 90, 225])
@pytest.mark.parametrize('reverse', [False, True])
def test_chamfer_contour_is_exact_stock_join_is_on_straight_body(angle, reverse):
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    points = [(100+x*c-y*s, 200+x*s+y*c) for x, y in
              [(0, 0), (254.104, 0), (254.104, 19), (7.566315, 19), (0, 0)]]
    if reverse:
        points.reverse()
    contract = build_fv_generation_contract('V987', {'segmentos_fundo': [
        {'length':254.104, 'dim_width':19, 'geometry':points}]})
    segment = contract['segments_rich'][0]
    assert segment['source_geometry'] == 'sa_chamfer'
    panels = segment['panels']
    assert len(panels) == 2
    assert panels[0]['chanfros']['te'] == 7.6
    assert not panels[1].get('chanfros')
    assert not any(p.get('angled_l') for p in panels)
    restored = []
    for panel in panels:
        ux, uy = panel['sa_local_frame']['axis']
        ox, oy = panel['sa_local_frame']['origin']
        restored.append(Polygon([(ox+v['x']*ux-v['y']*uy,
                                  oy+v['x']*uy+v['y']*ux) for v in panel['vertices']]))
        assert panel['width'] <= 244
    assert unary_union(restored).symmetric_difference(Polygon(points)).area < 1e-7


def test_dimension_labels_round_only_presentation(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    for length in (417.98, 417.88, 244.0):
        d = msp.add_linear_dim(base=(0,-10), p1=(0,0), p2=(length,0))
        d.render()
    path = tmp_path/'n3.dxf'
    doc.saveas(path)
    assert format_fv_n3_dimensions(path) == 3
    rendered = ezdxf.readfile(path)
    dimensions = list(rendered.modelspace().query('DIMENSION'))
    assert [d.get_measurement() for d in dimensions] == [417.98,417.88,244.0]
    labels = []
    for dimension in dimensions:
        labels.extend(e.dxf.text for e in rendered.blocks[dimension.dxf.geometry]
                      if e.dxftype() == 'MTEXT')
    assert labels == ['418', '417,9', '244']


def test_web_length_format_and_unedited_panel_precision():
    js = (Path(__file__).resolve().parents[1]/'portal/app/static/fv_ficha.js').read_text(encoding='utf-8')
    start = js.index('  function lengthText(')
    end = js.index('  function cleanSvg(', start)
    code = js[start:end] + """
const assert = require('assert');
const esc = String, shown = String;
assert.equal(lengthText(417.98), '418');
assert.equal(lengthText(417.88), '417,9');
assert.equal(lengthText(418), '418');
assert.equal(lengthText(null), '—');
let input = {value:'418,0', getAttribute:k=>k==='data-display-length'?'418,0':'417.98'};
assert.equal(panelLengthValue(input), '417.98');
input.value='417,9'; assert.equal(panelLengthValue(input), '417.9');
"""
    subprocess.run(['node', '-e', code], check=True)


def test_chamfer_contract_reaches_generator_and_dimension_export(tmp_path):
    import importlib.util
    import sys
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location('fv_decimal_generator', scripts/'gerar_fv_dxf_stog.py')
    fv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fv)
    contract = build_fv_generation_contract('V987', {'segmentos_fundo': [{
        'length':254.104, 'dim_width':19, 'geometry':[
            (0,0),(254.104,0),(254.104,19),(7.566315,19),(0,0)]}]})
    doc = fv.setup_doc()
    fv.draw_viga(doc.modelspace(), 0, 0, contract['segments_rich'], 19, 'V987',
                 label_left='', label_right='')
    dimensions = list(doc.modelspace().query('DIMENSION'))
    assert any(abs(d.get_measurement()-7.6)<1e-6 for d in dimensions)
    path = tmp_path/'chamfer.dxf'
    doc.saveas(path)
    format_fv_n3_dimensions(path)
    doc = ezdxf.readfile(path)
    labels = [e.dxf.text for d in doc.modelspace().query('DIMENSION')
              for e in doc.blocks[d.dxf.geometry] if e.dxftype()=='MTEXT']
    assert '7,6' in labels
