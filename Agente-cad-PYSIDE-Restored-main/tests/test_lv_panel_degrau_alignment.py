"""Painéis degrau LV alinham pelo topo; sarrafos respeitam limites do painel."""

from pathlib import Path
import importlib.util
import sys

import ezdxf


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gerar_lv_dxf_stog.py"
sys.path.insert(0, str(_SCRIPT.parent))
_SPEC = importlib.util.spec_from_file_location("gerar_lv_dxf_stog_degrau", _SCRIPT)
lv = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(lv)


def _hline_ys(msp, x_min, x_max, layer='SARR_2.2x7'):
    ys = []
    for ent in msp:
        if ent.dxftype() != 'LWPOLYLINE' or ent.dxf.layer != layer:
            continue
        pts = list(ent.get_points('xy'))
        if len(pts) != 2:
            continue
        (x1, y1), (x2, y2) = pts
        if abs(y1 - y2) > 0.01:
            continue
        if x_min - 0.5 <= min(x1, x2) and max(x1, x2) <= x_max + 0.5:
            ys.append(round(y1, 3))
    return sorted(set(ys))


def _panel_top_bottom(msp, x_min, x_max):
    """Linhas H que cobrem (nao so ficam contidas em) a faixa [x_min,x_max].

    A borda superior do corpo agora e continua (0->body_end) numa unica
    linha quando o material topo-alinhado chega em y_top nas duas zonas
    (degrau + alta) — N2 real de V301.A confirma isso (linha unica de
    405.5cm, nao 2 segmentos). Overlap em vez de contencao estrita cobre
    tanto o caso continuo quanto o antigo caso segmentado.
    """
    tops, bots = [], []
    for ent in msp:
        if ent.dxftype() != 'LINE' or ent.dxf.layer != 'Painéis':
            continue
        x1, y1 = ent.dxf.start.x, ent.dxf.start.y
        x2, y2 = ent.dxf.end.x, ent.dxf.end.y
        if abs(y1 - y2) > 0.01:
            continue
        lo, hi = min(x1, x2), max(x1, x2)
        if hi <= x_min or lo >= x_max:
            continue
        y = round(y1, 3)
        if abs(x1 - x2) < 0.01:
            continue
        if y >= 100:
            tops.append(y)
        else:
            bots.append(y)
    return tops, bots


def test_degrau_panel_top_aligns_and_sarrafos_stay_inside():
    h_face = 109.0
    panels = [
        {
            'width': 244.0,
            'height1': 44.0,
            'height2': 0.0,
            'grade_h1': 0.0,
            'grade_h2': 0.0,
            'laje_central_alt': 0.0,
            'reuse': True,
            'reuse_regions': [{'x_offset': 0.0, 'y_offset': 65.0, 'width': 244.0, 'height': 44.0}],
            'panel_type': 'Sarrafeado',
        },
        {
            'width': 111.0,
            'height1': 109.0,
            'height2': 0.0,
            'grade_h1': 0.0,
            'grade_h2': 0.0,
            'laje_central_alt': 0.0,
            'reuse': False,
            'panel_type': 'Sarrafeado',
        },
    ]

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    y0 = 0.0
    lv.draw_lv_face(
        msp, 0.0, y0, panels, h_face, 'V301.A',
        laje_sup=0.0, laje_inf=0.0,
        suppress_sarrafo_spans=False,
    )

    short_tops, short_bots = _panel_top_bottom(msp, 0.0, 244.0)
    tall_tops, _ = _panel_top_bottom(msp, 244.0, 355.0)

    assert short_tops and tall_tops
    assert max(short_tops) == max(tall_tops) == y0 + h_face
    assert min(short_bots) == y0 + (h_face - 44.0)

    short_sarr = _hline_ys(msp, 7.0, 244.0)
    assert short_sarr
    assert min(short_sarr) >= y0 + 65.0 + 6.5
    assert max(short_sarr) <= y0 + h_face - 6.5

    tall_sarr = _hline_ys(msp, 244.0, 348.0)
    assert tall_sarr
    assert min(tall_sarr) >= y0 + 6.5
    assert max(tall_sarr) <= y0 + h_face - 6.5


def test_helpers_match_reuse_y_offset():
    p = {
        'height1': 44.0,
        'height2': 0.0,
        'laje_central_alt': 0.0,
        'reuse_regions': [{'y_offset': 65.0}],
    }
    assert lv._panel_draw_height(p, 109.0) == 44.0
    assert lv._panel_y_base(0.0, 109.0, p) == 65.0