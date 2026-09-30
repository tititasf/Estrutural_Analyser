from __future__ import annotations

import json
from pathlib import Path

from portal.app.config import Settings
from portal.app import pipeline_runner


P26_POINTS = [
    [3936.3825, 2242.038], [4101.3825, 2242.038],
    [4101.3825, 2261.038], [3955.3825, 2261.038],
    [3955.3825, 2460.038], [3936.3825, 2460.038],
]


def test_granular_cima_regenerates_only_both_cima_variants(tmp_path, monkeypatch):
    obra_dir = tmp_path / "Obra"
    payload = {
        "nome": "P26", "subtipo_pil": "L", "geometry_points": P26_POINTS,
        "comprimento": 50, "largura": 19, "altura": 321,
    }
    for mode in ("para", "passa"):
        variant = obra_dir / "Fase-6_Execucao_CAD" / "n3_variants" / mode
        variant.mkdir(parents=True)
        (variant / "P26.json").write_text(
            json.dumps(payload), encoding="utf-8",
        )
    monkeypatch.setattr(pipeline_runner, "_obra_dir", lambda *_args: obra_dir)

    result = pipeline_runner.regenerar_n3_cima_item(
        Settings(repo_root=Path(__file__).resolve().parents[1]),
        {"id": "obra"}, item="P26", pav="13_PAV",
    )

    assert result.ok, result.log_tail
    assert "para:" in result.log_tail and "passa:" in result.log_tail
    for mode in ("para", "passa"):
        variant = obra_dir / "Fase-6_Execucao_CAD" / "n3_variants" / mode
        assert (variant / "PL_CIMA_preview_P26.dxf").stat().st_size > 1000
        assert not (variant / "PL_ABCD_preview_P26.dxf").exists()
        persisted = json.loads((variant / "P26.json").read_text(encoding="utf-8"))
        assert persisted["nome"] == "P26"


def test_granular_ini_accumulates_without_overwriting_nova_legacy(tmp_path, monkeypatch):
    obra_dir = tmp_path / "Obra"
    payload = {
        "nome": "P26", "subtipo_pil": "L", "geometry_points": P26_POINTS,
        "comprimento": 50, "largura": 19, "altura": 321,
    }
    legacy_bytes = b"NOVA-LEGACY-SENTINEL"
    for semantic in ("para", "passa"):
        variant = obra_dir / "Fase-6_Execucao_CAD" / "n3_variants" / semantic
        variant.mkdir(parents=True)
        (variant / "P26.json").write_text(json.dumps(payload), encoding="utf-8")
        (variant / "PL_CIMA_preview_P26.dxf").write_bytes(legacy_bytes)
    monkeypatch.setattr(pipeline_runner, "_obra_dir", lambda *_args: obra_dir)

    result = pipeline_runner.regenerar_n3_cima_item(
        Settings(repo_root=Path(__file__).resolve().parents[1]),
        {"id": "obra"}, item="P26", pav="13_PAV", visual_mode="INI",
    )

    assert result.ok, result.log_tail
    for semantic in ("para", "passa"):
        legacy = obra_dir / "Fase-6_Execucao_CAD" / "n3_variants" / semantic
        typed = obra_dir / "Fase-6_Execucao_CAD" / "n3_modes" / "INI" / "pilares" / semantic
        assert (legacy / "PL_CIMA_preview_P26.dxf").read_bytes() == legacy_bytes
        assert (typed / "PL_CIMA_preview_P26.dxf").stat().st_size > 1000
        persisted = json.loads((typed / "P26.json").read_text(encoding="utf-8"))
        assert persisted["_visual_modes"]["cima"] == "INI"
