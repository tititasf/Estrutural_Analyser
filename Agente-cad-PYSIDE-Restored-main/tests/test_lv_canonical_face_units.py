"""Regressão: deduplicação de face_units e crop por unidade primária."""

from pathlib import Path
import importlib.util
import sys

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gerar_lv_dxf_stog.py"
sys.path.insert(0, str(_SCRIPT.parent))
_SPEC = importlib.util.spec_from_file_location("gerar_lv_dxf_stog_test", _SCRIPT)
lv = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_stdout = sys.stdout
try:
    _SPEC.loader.exec_module(lv)
finally:
    sys.stdout = _stdout


def _seg(width, height1=109, reuse=False, regions=None):
    return {
        "width": width,
        "height1": height1,
        "reuse": reuse,
        "reuse_regions": regions or [],
    }


def test_select_canonical_keeps_each_distinct_segment_geometry():
    units = [
        {
            "side": "A",
            "label": "V301.A",
            "bbox": {"x_left": 0, "y_top": 200},
            "h_body": 109,
            "panels": [_seg(244, 44), _seg(50.5, 44), _seg(111), _seg(161.5)],
        },
        {
            "side": "A",
            "label": "",
            "bbox": {"x_left": 10, "y_top": 200},
            "h_body": 110,
            "panels": [_seg(244, 44), _seg(34.7, 44), _seg(117.5)],
        },
        {
            "side": "A",
            "label": "CONT. V301.A",
            "bbox": {"x_left": 0, "y_top": 100},
            "h_body": 109,
            "label_source": "text",
            "panels": [
                _seg(244, 43.6, reuse=True, regions=[{"y_offset": 65.4}]),
                _seg(41.2, 43.6),
                _seg(21.8, 43.6),
                _seg(111),
                _seg(19),
                _seg(21.2),
            ],
        },
        {
            "side": "A",
            "label": "CONT. V301.A",
            "bbox": {"x_left": 5, "y_top": 100},
            "h_body": 109,
            "panels": [
                _seg(244, 43.6),
                _seg(34.7, 43.6),
                _seg(21.8, 43.6),
                _seg(117.5),
                _seg(19),
                _seg(21.2),
            ],
        },
    ]

    canon = lv.select_canonical_face_units(units, viga_nome="V301")
    labels = [u["label"] for u in canon]

    assert labels == ["V301.A", "", "CONT. V301.A", "CONT. V301.A"]
    assert any(u["panels"][0].get("reuse") for u in canon)


def test_layout_primary_unit_starts_at_origin_for_view_a():
    units = [
        {
            "side": "A",
            "label": "V301.A",
            "bbox": {"x_left": 0, "y_top": 200},
            "h_body": 109,
            "panels": [_seg(244, 44), _seg(50.5, 44)],
        },
        {
            "side": "A",
            "label": "CONT. V301.A",
            "bbox": {"x_left": 0, "y_top": 100},
            "h_body": 109,
            "panels": [_seg(458.2, 44)],
        },
    ]
    layouts = lv.layout_lv_face_unit_bboxes(units, view="A")
    assert layouts[0]["label"] == "V301.A"
    assert layouts[0]["bbox"][0] == -25.0
    assert layouts[1]["bbox"][0] > layouts[0]["bbox"][2]


def test_draw_names_unlabeled_distinct_segment_instead_of_dropping_it(monkeypatch):
    calls = []

    def record_face(_msp, x0, _y0, panels, _height, label, **_kwargs):
        calls.append((x0, sum(p["width"] for p in panels), label))

    monkeypatch.setattr(lv, "draw_lv_face", record_face)
    units = [
        {
            "side": "A",
            "label": "V1.A",
            "bbox": {"x_left": 0, "y_top": 200},
            "h_body": 40,
            "panels": [{"width": 100}],
        },
        {
            "side": "A",
            "label": "",
            "bbox": {"x_left": 0, "y_top": 150},
            "h_body": 40,
            "panels": [{"width": 90}],
        },
    ]
    lv.draw_viga_lateral_face_units(None, 0, 0, "V1", units, view="A")
    assert [c[2] for c in calls] == ["V1.A", "V1.A#2"]
