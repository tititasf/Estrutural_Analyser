import json

from portal.app.pillar_level_view import enrich_pillar_abcd_levels, load_preprocess_slab_levels
from src.core.pillar_abcd_tables import format_abcd_tables_portal_html


def _row(name, family):
    return {"nome": name, "familia": family, "nivel": "—"}


def test_levels_use_sa_segments_and_mark_fallback_and_disagreement():
    tables = {"faces": {"A": {
        "lajes": [_row("L410", "laje"), _row("L411", "laje")],
        "passa": [_row("V409", "viga"), _row("V401", "viga"), _row("V402", "viga")],
    }}}
    state = {
        "slabs": [{"name": "L410", "nivel": "855.22"}],
        "segmentos": {"fundo": [
            {"beam_name": "V409", "level": "855.25", "level_source": "explicit_beam_or_side", "status": "valid"},
            {"beam_name": "V401", "level": "855.18", "level_source": "explicit_beam_or_side", "status": "valid"},
            {"beam_name": "V401", "level": "855.25", "level_source": "highest_touching_slab", "status": "valid"},
            {"beam_name": "V402", "level": "855.25", "level_source": "nearest_levelled_slab", "status": "valid"},
        ]},
    }
    enriched = enrich_pillar_abcd_levels(tables, state, 855.25, {"L410": {855.25}})
    face = enriched["faces"]["A"]
    assert (face["lajes"][0]["nivel"], face["lajes"][0]["nivel_status"]) == ("855.22", "conflict")
    assert (face["lajes"][1]["nivel"], face["lajes"][1]["nivel_status"]) == ("855.25", "fallback")
    assert (face["passa"][0]["nivel"], face["passa"][0]["nivel_status"]) == ("855.25", "sa")
    assert (face["passa"][1]["nivel"], face["passa"][1]["nivel_status"]) == ("855.25", "ambiguous")
    assert (face["passa"][2]["nivel"], face["passa"][2]["nivel_status"]) == ("855.25", "inferred")
    assert tables["faces"]["A"]["passa"][0]["nivel"] == "—"
    html = format_abcd_tables_portal_html(enriched)
    assert html.count('class="abcd-level-attention"') >= 4
    assert "SA/N1 e pré-processamento divergem" in html


def test_preprocess_levels_only_from_consumed_run_and_matching_tower(tmp_path):
    obra = tmp_path / "obra"
    run_id = "50b3fe16-47dc-49e8-9137-4cabe63e0791"
    production = obra / "Fase-6_Execucao_CAD/production_sa/14_PAV/20260923_1"
    production.mkdir(parents=True)
    (production / "production_manifest.json").write_text(json.dumps({
        "preprocess_context": {"context_run_id": run_id, "scope": {"recorte_id": "tower-1"}},
    }), encoding="utf-8")
    run = obra / "preprocessamento/v1/14_PAV/runs" / run_id
    (run / "towers").mkdir(parents=True)
    (run / "floor.json").write_text(json.dumps({
        "towers": {"tower-1": {"path": "towers/one.json"}},
    }), encoding="utf-8")
    (run / "towers/one.json").write_text(json.dumps({"levels": [
        {"field": "slab_level", "status": "observed_text", "display_name": "L410", "value": 855.25},
        {"field": "slab_level", "status": "unknown", "display_name": "L411", "value": 855.18},
    ]}), encoding="utf-8")
    assert load_preprocess_slab_levels(obra, "14_PAV") == {"L410": {855.25}}
    (run / "towers/one.json").write_text(json.dumps({
        "level_inventory": {"items": [{"item_id": "implicit", "display_name": "L1", "item_class": "slab"}]},
        "levels": [
            {"item_id": "implicit", "field": "slab_level", "method": "cad_level_inside_slab",
             "status": "sa_evidence", "value": 0},
            {"item_id": "implicit", "field": "slab_level", "method": "nearest",
             "status": "inferred", "value": 3},
        ]}), encoding="utf-8")
    assert load_preprocess_slab_levels(obra, "14_PAV") == {"L1": {0}}


def test_beam_level_uses_segment_touching_pillar():
    tables = {"faces": {"A": {"passa": [_row("V401", "viga")]}}}
    state = {
        "pilares": [{"name": "P10", "points": [[0, 0], [20, 0], [20, 20], [0, 20]]}],
        "segmentos": {"fundo": [
            {"beam_name": "V401", "level": "855.25", "level_source": "explicit_beam_or_side",
             "status": "valid", "points": [[20, 5], [50, 5], [50, 15], [20, 15]]},
            {"beam_name": "V401", "level": "855.18", "level_source": "explicit_beam_or_side",
             "status": "valid", "points": [[100, 5], [150, 5], [150, 15], [100, 15]]},
        ]},
    }
    row = enrich_pillar_abcd_levels(tables, state, 855.25, pillar_name="P10")["faces"]["A"]["passa"][0]
    assert (row["nivel"], row["nivel_status"]) == ("855.25", "sa")


def test_dimension_uses_lateral_and_flags_previous_pillar_like_dimension():
    tables = {"faces": {"B": {"passa": [{"nome": "V409", "dim": "19/60", "nivel": "—", "canto": "BC"}]}}}
    state = {
        "pilares": [{"name": "P10", "points": [[0, 0], [19, 0], [19, 60], [0, 60]]}],
        "segmentos": {
            "fundo": [{"beam_name": "V409", "segment_label": "1", "width": "19", "level": "855.25",
                       "level_source": "explicit_beam_or_side", "status": "valid",
                       "points": [[19, 0], [100, 0], [100, 19], [19, 19]]}],
            "lateral_a_para": [{"beam_name": "V409", "segment_label": "1", "width": "19/55"}],
            "lateral_b_para": [{"beam_name": "V409", "segment_label": "1", "width": "19/55"}],
        },
    }
    row = enrich_pillar_abcd_levels(tables, state, 855.25, pillar_name="P10", beam_dim_texts={
        "V409": [
            {"text": "19/60", "pos": [0, 0]},  # seção do pilar: não confirma a viga
            {"text": "19/55", "pos": [25, 10]},
        ],
    })["faces"]["B"]["passa"][0]
    assert row["dim"] == "19/55"
    assert row["dim_status"] == "conflict"
    assert "leitura anterior 19/60" in row["dim_motivo"]
    assert "sem corte independente" not in row["dim_motivo"]


def test_slab_distances_use_face_geometry_with_review_warning():
    tables = {"faces": {"B": {"lajes": [{"nome": "L410", "dim": "14", "nivel": "—",
                                              "dist_esq": "—", "dist_dir": "—"}]}}}
    state = {
        "pilares": [{"name": "P10", "points": [[0, 0], [19, 0], [19, 60], [0, 60]]}],
        "slabs": [{"name": "L410", "nivel": "855.22",
                   "points": [[19, 0], [100, 0], [100, 41], [19, 41]]}],
    }
    row = enrich_pillar_abcd_levels(tables, state, 855.25, pillar_name="P10")["faces"]["B"]["lajes"][0]
    assert (row["dist_esq"], row["dist_dir"], row["dist_status"]) == ("0.00cm", "19.00cm", "inferred")


def test_old_face_scalar_cannot_confirm_missing_current_slab_level():
    tables = {"faces": {"C": {"lajes": [{"nome": "L9", "nivel": "6cm"}]}}}
    result = enrich_pillar_abcd_levels(tables, {"slabs": [{"name": "L9", "nivel": None}]}, None)
    assert result["faces"]["C"]["lajes"][0]["nivel"] == "?"


def test_sa_summary_does_not_use_old_n3_levels(tmp_path, monkeypatch):
    from portal.app.routers import n1_routes as routes
    monkeypatch.setattr(routes, "_robot_pilar", lambda *a: {"nivel_chegada_abs": 852.19, "nivel_saida_abs": 848.98, "altura": 321})
    monkeypatch.setattr(routes.pillar_level_view, "load_preprocess_pillar_levels", lambda *a: {})
    state = {"pilares": [{"name": "P8", "points": [[0,0],[19,0],[19,140],[0,140]]}]}
    result = routes._resumo_pilar_n1(state, tmp_path, "P8", "TIPO")
    assert result["nivel_chegada"] is None
    assert result["nivel_saida"] is None
    assert result["pe_direito"] is None


def test_pillar_context_keeps_zero_negative_and_rejects_conflicting_sources(tmp_path, monkeypatch):
    from portal.app import pillar_level_view as view
    package = {'level_inventory': {'items': [{'item_id': 'p', 'item_class': 'pillar', 'display_name': 'P1'}]},
               'levels': [{'item_id': 'p', 'field': 'top', 'status': 'floor_reference', 'value': 0},
                          {'item_id': 'p', 'field': 'base', 'status': 'observed_text', 'value': -3},
                          {'item_id': 'p', 'field': 'top', 'status': 'inferred', 'value': 9}]}
    monkeypatch.setattr(view, '_load_consumed_preprocess_package', lambda *args: package)
    assert view.load_preprocess_pillar_levels(tmp_path, 'TIPO', 'P1') == {'top': 0, 'base': -3}
    package['levels'].append({'item_id': 'p', 'field': 'top', 'status': 'observed_text', 'value': 1})
    assert view.load_preprocess_pillar_levels(tmp_path, 'TIPO', 'P1') == {'base': -3}
