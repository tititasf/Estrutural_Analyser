import json
import sys
from pathlib import Path
from types import MethodType, SimpleNamespace

from shapely.geometry import Polygon

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import main as main_module
from main import MainWindow
from src.core.pillar_analyzer import PillarAnalyzer


def _main_window_logic(**attrs):
    obj = SimpleNamespace(**attrs)
    for name in (
        "_plan_area_bbox",
        "_collect_plan_pillar_names",
        "_find_pillar_geom_near_text",
        "_pillar_face_from_edge_overlap",
        "_pillar_laje_entries",
        "_reconcile_canonical_pillar_links",
        "_build_pillar_report",
        "_build_complete_pillar_report",
    ):
        setattr(obj, name, MethodType(getattr(MainWindow, name), obj))
    obj._is_pillar_like_polygon = MainWindow._is_pillar_like_polygon
    obj._pillar_points_sig = MainWindow._pillar_points_sig
    return obj


def test_complete_report_keeps_all_names_and_accepts_special_l_pillar():
    slab_points = [(0, 0), (500, 0), (500, 500), (0, 500), (0, 0)]
    rectangle = [(50, 50), (90, 50), (90, 90), (50, 90), (50, 50)]
    special_l = [
        (200, 200), (365, 200), (365, 219),
        (219, 219), (219, 418), (200, 418), (200, 200),
    ]
    slabs = [{
        "name": "L1",
        "points": slab_points,
        "links": {
            "laje_pilares_apoio": {"pillar_geom": []},
            "laje_visao_corte": {
                "cut_view_geom": [{"points": special_l, "type": "poly"}]
            },
        },
    }]
    dxf_data = {
        "texts": [
            {"text": "P1", "pos": (70, 70)},
            {"text": "P2", "pos": (260, 240)},
        ],
        "polylines": [
            {"points": rectangle, "layer": "PIL"},
            {"points": special_l, "layer": "PIL"},
        ],
    }
    logic = _main_window_logic(dxf_data=dxf_data, slabs_found=slabs)

    report = logic._build_complete_pillar_report(slabs)

    assert set(report) == {"P1", "P2"}
    assert all(not item["needs_geometry"] for item in report.values())
    assert report["P2"]["shape_type"] == "Em L"
    assert MainWindow._is_pillar_like_polygon(Polygon(special_l), special_l)
    assert slabs[0]["links"]["laje_visao_corte"]["cut_view_geom"] == []
    assert any(
        link.get("ficha", {}).get("pillar_name") == "P2"
        for link in slabs[0]["links"]["laje_pilares_apoio"]["pillar_geom"]
    )


def test_pillar_analyzer_does_not_replace_locked_canonical_name():
    class FakeContext:
        def __init__(self):
            self.fields = []

        def perform_search(self, _item, config, side=None):
            self.fields.append(config["field_id"])
            return {"found_ent": None, "links": [], "confidence": 0.0}

    context = FakeContext()
    pillar = {
        "name": "P26",
        "canonical_name": "P26",
        "identity_locked": True,
        "points": [(0, 0), (20, 0), (20, 20), (0, 20), (0, 0)],
        "pos": (10, 10),
        "area_val": 400,
        "type": "Pilar",
        "sides_data": {},
        "links": {},
        "confidence_map": {},
        "neighbors": [],
    }

    PillarAnalyzer(context).analyze(pillar)

    assert pillar["name"] == "P26"
    assert "name" not in context.fields
    assert "dim" in context.fields


def test_preficha_rejection_removes_only_rejected_pillar_geometry():
    p1 = [(0, 0), (20, 0), (20, 20), (0, 20), (0, 0)]
    p2 = [(50, 0), (70, 0), (70, 20), (50, 20), (50, 0)]
    slab = {
        "links": {
            "laje_pilares_apoio": {
                "pillar_geom": [{"points": p1}, {"points": p2}]
            }
        }
    }
    logic = SimpleNamespace(
        pavimento_preprocess={},
        pavimento_pillar_report={
            "P1": {"name": "P1", "points": p1},
            "P2": {"name": "P2", "points": p2},
        },
        slabs_found=[slab],
    )
    logic._pillar_points_sig = MainWindow._pillar_points_sig
    logic._apply_pre_validation_result = MethodType(
        MainWindow._apply_pre_validation_result, logic
    )

    logic._apply_pre_validation_result({
        "pillar_overrides": {
            "P1": {"classification": "SEGUE", "physical_type": "continues"},
            "P2": {
                "classification": "NÃO PILAR — OBJETO SÓLIDO",
                "physical_type": "not_pillar",
                "is_invalid": True,
            },
        },
        "invalid_pillar_keys": {"P2"},
    })

    remaining = slab["links"]["laje_pilares_apoio"]["pillar_geom"]
    assert logic.pavimento_pillar_report["P2"]["is_invalid"] is True
    assert len(remaining) == 1
    assert remaining[0]["points"] == p1


def test_preficha_history_restores_nasce_as_visual_only_before_beams(tmp_path, monkeypatch):
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    monkeypatch.setattr(main_module, "__file__", str(fake_repo / "main.py"))
    history_dir = tmp_path / "DADOS-OBRAS" / "Obra_TREINO_1"
    history_dir.mkdir(parents=True)
    history = history_dir / "preficha_history_TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA.json"
    history.write_text(
        json.dumps({
            "pilares": {
                "3335.9,2991.0,3385.9,3010.0": {
                    "geo_key": "3335.9,2991.0,3385.9,3010.0",
                    "last_name": "P46",
                    "classification": "NASCE",
                    "physical_type": "visual_only",
                }
            },
            "cut_views": {},
            "beam_segments": {},
        }),
        encoding="utf-8",
    )
    logic = SimpleNamespace(
        pavimento_preprocess={"obra": "Obra_TREINO_1", "pavimento": "13_PAV"},
        pavimento_pillar_report={},
    )
    logic.log = lambda *_args, **_kwargs: None
    logic._apply_preficha_rejections = MethodType(
        MainWindow._apply_preficha_rejections, logic
    )
    report = {
        "P46": {
            "name": "P46",
            "classification": "INDETERMINADO",
            "ignore_in_beams": False,
            "points": [
                (3335.8825, 2991.038),
                (3385.8825, 2991.038),
                (3385.8825, 3010.038),
                (3335.8825, 3010.038),
                (3335.8825, 2991.038),
            ],
        }
    }

    logic._apply_preficha_rejections(report)

    assert report["P46"]["classification"] == "NASCE"
    assert report["P46"]["physical_type"] == "visual_only"
    assert report["P46"]["ignore_in_beams"] is True
    assert report["P46"]["preficha_reviewed"] is True


def test_fundo_support_repair_removes_unvalidated_nasce_text_support():
    logic = SimpleNamespace(
        pillars_found=[],
        beams_found=[],
        pavimento_pillar_report={
            "P50": {
                "name": "P50",
                "classification": "NASCE",
                "physical_type": "visual_only",
                "ignore_in_beams": True,
                "points": [(0, 0), (50, 0), (50, 19), (0, 19), (0, 0)],
            }
        },
    )
    logic.get_pillar_report = MethodType(MainWindow.get_pillar_report, logic)
    logic.is_pillar_nasce = MethodType(MainWindow.is_pillar_nasce, logic)
    logic._repair_fundo_support_fields = MethodType(
        MainWindow._repair_fundo_support_fields, logic
    )
    beam = {
        "name": "V320",
        "fields": {"viga_fundo_seg_1_local_ini": "P50"},
        "validated_fields": [],
        "links": {
            "viga_fundo_seg_1_area_segs": {
                "contour": [{
                    "points": [(0, 0), (120, 0), (120, 19), (0, 19), (0, 0)]
                }]
            },
            "viga_fundo_seg_1_local_ini": {
                "label": [{"text": "P50", "role": "Apoio fundo de viga"}]
            },
        },
    }

    logic._repair_fundo_support_fields(beam)

    assert "viga_fundo_seg_1_local_ini" not in beam["fields"]
    assert "viga_fundo_seg_1_local_ini" not in beam["links"]


def test_headless_fv_support_text_ignores_nasce_labels():
    from scripts.analise_geral_headless import _find_support_text

    class FakeSpatialIndex:
        def query_bbox(self, _bbox):
            return [
                {"text": "P50", "pos": (0.0, 0.0)},
                {"text": "P14", "pos": (20.0, 0.0)},
            ]

    support = _find_support_text(
        (0.0, 0.0),
        FakeSpatialIndex(),
        current_beam="V320",
        ignored_labels={"P50"},
    )

    assert support["text"] == "P14"
