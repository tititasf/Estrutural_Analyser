from pathlib import Path

from scripts.arete import g2v_harness


def test_resolver_html_ficha_uses_selected_lv_list(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(g2v_harness, "ARETE_ROOT", tmp_path)
    class_dir = (
        tmp_path
        / "html_fichas"
        / "Obra_TREINO_1"
        / "run_20260705"
        / "laterais_viga"
    )
    para = class_dir / "LV-PARA" / "V301-Para.html"
    passa = class_dir / "LV-PASSA" / "V301-Passa.html"
    para.parent.mkdir(parents=True)
    passa.parent.mkdir(parents=True)
    para.write_text("para", encoding="utf-8")
    passa.write_text("passa", encoding="utf-8")
    (class_dir.parent / "arete_manifest.json").write_text(
        "{}", encoding="utf-8"
    )

    assert g2v_harness.resolver_html_ficha(
        "Obra_TREINO_1", "LV", "V301"
    ) == passa
    assert g2v_harness.resolver_html_ficha(
        "Obra_TREINO_1", "LV", "V301", lista_lv="para"
    ) == para


def test_cli_pass_requires_every_visual_check():
    verdict = g2v_harness.avaliar_cli(Path(__file__), "prompt")
    verdict["veredito"] = "PASS"

    valid, reason = g2v_harness.validar_veredito_cli(verdict)

    assert not valid
    assert "checklist" in reason
    verdict["checklist_visual"] = {
        key: True for key in verdict["checklist_visual"]
    }
    valid, reason = g2v_harness.validar_veredito_cli(verdict)
    assert valid
    assert reason == ""


def test_lv_dxf_n3_requires_html_to_preserve_corte_a_b(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(g2v_harness, "get_recorte_path", lambda *_args, **_kwargs: tmp_path / "n2.dxf")
    monkeypatch.setattr(g2v_harness, "get_real_n4_path", lambda *_args, **_kwargs: tmp_path / "n4.dxf")
    for name in ("n2.dxf", "n4.dxf"):
        (tmp_path / name).write_text("0\nEOF\n", encoding="utf-8")
    for suffix in ("CORTE", "VIEW_A", "VIEW_B"):
        (tmp_path / f"LV_preview_V301_Passa_{suffix}.dxf").write_text("0\nEOF\n", encoding="utf-8")

    result = g2v_harness.avaliar_item(
        {"classe": "LV", "elemento_id": "V301", "obra_name": "Obra_TREINO_1"},
        ["cli"], tmp_path / "out", fonte_imagem="dxf", par="n3xn4",
        n3_dir=tmp_path, lista_lv="passa",
    )

    assert result["n3_path"] is None
    assert len(result["n3_views"]) == 3
    assert "Corte/A/B independentes" in result["erro"]
