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
