from pathlib import Path

from scripts.arete import diagnostico_fv_n1_n2, diagnostico_laj_n1_n2
from scripts.arete.headless_sa_analise import (
    _attach_lv_generation_contracts,
    _filter_fv_results_for_items,
    _publish_arete_manifest,
    _run_fv_diagnostic_postprocess,
    _run_section_diagnostics,
)


def test_fv_n3_item_filter_keeps_only_requested_beams():
    results = [
        {"viga_nome": "V309.C"},
        {"viga_nome": "V320.C"},
        {"viga_nome": "VF202.C"},
    ]

    filtered = _filter_fv_results_for_items(results, {"V309", "VF202"})

    assert [item["viga_nome"] for item in filtered] == ["V309.C", "VF202.C"]
    assert _filter_fv_results_for_items(results, None) == results


def test_headless_attaches_v327_generation_contract_for_sa_db():
    beam = {
        "name": "V327",
        "lv_is_h": False,
        "geometry": {"lv_dimension_text": {"text": "14/50"}},
        "links": {
            "viga_a_seg_1_comp_total_passa": {"seg_side_a": [{
                "points": [[4387.3825, 1982.038], [4387.3825, 2242.038]],
                "len": 260,
            }]},
            "viga_b_seg_1_comp_total_passa": {"seg_side_b": [{
                "points": [[4387.3825, 1982.038], [4387.3825, 2242.038]],
                "len": 260,
            }]},
        },
    }
    pillar = {
        "name": "P27",
        "points": [
            [4387.3825, 2242.038], [4552.3825, 2242.038],
            [4552.3825, 2460.038], [4387.3825, 2460.038],
        ],
    }

    assert _attach_lv_generation_contracts([beam], [pillar], "13_PAV") == 1
    assert beam["fields"]["lv_n3_passa_panels_A"] == [122.0, 134.0]
    assert beam["fields"]["lv_n3_passa_panels_B"] == [122.0, 138.0]
    assert beam["fields"]["lv_n3_passa_total_A"] == 256.0
    assert beam["fields"]["lv_n3_passa_total_B"] == 260.0


def test_fv_diagnostic_postprocess_returns_paths(monkeypatch, tmp_path: Path):
    expected_json = tmp_path / "diagnostico.json"
    expected_jsonl = tmp_path / "triagem.jsonl"
    calls = []

    def fake_run_diagnostic(**kwargs):
        calls.append(kwargs)
        return ({"resumo": {"alertas": 2}}, expected_json, expected_jsonl)

    monkeypatch.setattr(
        diagnostico_fv_n1_n2, "run_diagnostic", fake_run_diagnostic
    )
    result = _run_fv_diagnostic_postprocess(
        obra="Obra_TESTE",
        pavimento="13_PAV",
        state_path="estado.json",
        db_path="project_data.vision",
    )

    assert result == {
        "status": "ok",
        "run_id": None,
        "json_path": str(expected_json),
        "jsonl_path": str(expected_jsonl),
        "resumo": {"alertas": 2},
    }
    assert calls == [{
        "obra": "Obra_TESTE",
        "pavimento": "13_PAV",
        "state_path": "estado.json",
        "db_path": "project_data.vision",
    }]


def test_fv_diagnostic_postprocess_is_non_blocking(monkeypatch):
    def fail_diagnostic(**kwargs):
        raise RuntimeError("falha controlada")

    monkeypatch.setattr(
        diagnostico_fv_n1_n2, "run_diagnostic", fail_diagnostic
    )
    result = _run_fv_diagnostic_postprocess(
        obra="Obra_TESTE",
        pavimento="13_PAV",
        state_path="estado.json",
        db_path="project_data.vision",
    )

    assert result == {"status": "erro", "erro": "falha controlada"}


def test_manifest_links_run_and_publishes_collapsed_item_panel(tmp_path: Path):
    run_dir = tmp_path / "html_fichas" / "Obra_TESTE" / "13_PAV_20260703_010203"
    section = run_dir / "fundos_viga"
    section.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html><body>raiz</body></html>", encoding="utf-8")
    (section / "index.html").write_text("<html><body>fundos</body></html>", encoding="utf-8")
    (section / "V101.html").write_text("<html><body>V101</body></html>", encoding="utf-8")

    report_dir = tmp_path / "relatorios" / "20260703_010203"
    report_dir.mkdir(parents=True)
    json_path = report_dir / "diagnostico_fv_n1_n2.json"
    jsonl_path = report_dir / "triagem_auto_fv.jsonl"
    json_path.write_text(
        __import__("json").dumps({
            "run_id": "20260703_010203",
            "itens": [{
                "item": "V101",
                "causa_raiz": "extractor_bug",
                "causa_descricao": "Dimensões divergentes.",
                "evidencia": {
                    "classificacao": "RUIM",
                    "deltas": {"largura": 0.0, "comprimento_total": 0.25},
                },
            }],
        }),
        encoding="utf-8",
    )
    jsonl_path.write_text("{}\n", encoding="utf-8")

    manifest_path = _publish_arete_manifest(
        html_dir=run_dir,
        obra="Obra_TESTE",
        pavimento="13_PAV",
        diagnostics={
            "fundos_viga": {
                "status": "ok",
                "run_id": "20260703_010203",
                "json_path": str(json_path),
                "jsonl_path": str(jsonl_path),
                "resumo": {"alertas": 1},
            },
        },
    )

    manifest = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "20260703_010203"
    assert manifest["diagnosticos"]["fundos_viga"]["json_relative"]
    root_html = (run_dir / "index.html").read_text(encoding="utf-8")
    assert "arete_manifest.json" in root_html
    item_html = (section / "V101.html").read_text(encoding="utf-8")
    assert '<details class="arete-auto-diagnostic"' in item_html
    assert "Hipótese numérica automática" in item_html
    assert "RUIM" in item_html
    assert "25.00%" in item_html


def test_manifest_injects_laj_and_nested_pil_pages(tmp_path: Path):
    """PASS #2 da story: lajes/L318.html deve ganhar o mesmo bloco que fundos_viga/.

    Também cobre pilares/, cujas fichas ficam em subpasta
    (pilares/INDETERMINADO/P12.html) em vez de soltas na raiz da seção.
    """
    run_dir = tmp_path / "html_fichas" / "Obra_TESTE" / "13_PAV_20260703_010203"
    laj_dir = run_dir / "lajes"
    pil_dir = run_dir / "pilares" / "INDETERMINADO"
    laj_dir.mkdir(parents=True)
    pil_dir.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html><body>raiz</body></html>", encoding="utf-8")
    (laj_dir / "L318.html").write_text("<html><body>L318</body></html>", encoding="utf-8")
    (run_dir / "pilares" / "index.html").write_text("<html><body>pilares</body></html>", encoding="utf-8")
    (pil_dir / "P12.html").write_text("<html><body>P12</body></html>", encoding="utf-8")

    report_dir = tmp_path / "relatorios"
    report_dir.mkdir(parents=True)

    def write_report(name: str, item: str) -> Path:
        path = report_dir / name
        path.write_text(
            __import__("json").dumps({
                "run_id": "20260703_010203",
                "itens": [{
                    "item": item,
                    "causa_raiz": None,
                    "causa_descricao": "",
                    "evidencia": {"classificacao": "EXCELENTE", "deltas": {}},
                }],
            }),
            encoding="utf-8",
        )
        return path

    laj_json = write_report("diagnostico_laj.json", "L318")
    pil_json = write_report("diagnostico_pil.json", "P12")

    manifest_path = _publish_arete_manifest(
        html_dir=run_dir,
        obra="Obra_TESTE",
        pavimento="13_PAV",
        diagnostics={
            "lajes": {
                "status": "ok", "run_id": "20260703_010203",
                "json_path": str(laj_json), "jsonl_path": None,
                "resumo": {"alertas": 0},
            },
            "pilares": {
                "status": "ok", "run_id": "20260703_010203",
                "json_path": str(pil_json), "jsonl_path": None,
                "resumo": {"alertas": 0},
            },
        },
    )

    manifest = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
    assert set(manifest["diagnosticos"]) == {"lajes", "pilares"}

    laj_html = (laj_dir / "L318.html").read_text(encoding="utf-8")
    assert "Diagnóstico automático N1×N2" in laj_html

    pil_html = (pil_dir / "P12.html").read_text(encoding="utf-8")
    assert "Diagnóstico automático N1×N2" in pil_html


def test_run_section_diagnostics_skips_missing_and_tolerates_failure(monkeypatch, tmp_path: Path):
    """PASS #1 e #4: só roda o que existe no run; uma seção falhando não derruba as outras."""
    run_dir = tmp_path / "html_fichas" / "Obra_TESTE" / "13_PAV_x"
    (run_dir / "lajes").mkdir(parents=True)
    (run_dir / "fundos_viga").mkdir(parents=True)
    # laterais_viga/pilares NÃO existem neste run -> devem ser pulados sem erro.

    def fake_laj(**kwargs):
        return ({"resumo": {"alertas": 0}}, tmp_path / "laj.json", tmp_path / "laj.jsonl")

    def fake_fv(**kwargs):
        raise RuntimeError("DB path errado")

    monkeypatch.setattr(diagnostico_laj_n1_n2, "run_diagnostic", fake_laj)
    monkeypatch.setattr(diagnostico_fv_n1_n2, "run_diagnostic", fake_fv)

    result = _run_section_diagnostics(
        html_dir=run_dir,
        obra="Obra_TESTE",
        pavimento="13_PAV",
        state_path="estado.json",
        db_path="project_data.vision",
    )

    assert set(result) == {"lajes", "fundos_viga"}
    assert result["lajes"]["status"] == "ok"
    assert result["fundos_viga"] == {"status": "erro", "erro": "DB path errado"}
