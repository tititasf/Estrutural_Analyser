"""Contrato transversal dos modos de desenho N3/N5 no portal."""

from pathlib import Path

import ezdxf

from portal.app import ficha_reader, pipeline_runner


STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_headless_recebe_modo_ini_explicitamente(settings, tmp_path):
    obra = {"nome": "Obra_TESTE", "local_path": str(tmp_path / "Obra_TESTE")}
    cmd = pipeline_runner.montar_comando_headless(
        settings, obra, secao=["pilares"], pav="13_PAV", visual_mode="INI",
    )
    index = cmd.index("--visual-mode")
    assert cmd[index + 1] == "INI"


def test_frontend_pergunta_modo_e_mostra_badge_em_n3_e_n5():
    helper = (STATIC / "drawing_mode.js").read_text(encoding="utf-8")
    drill = (STATIC / "drill_grade.js").read_text(encoding="utf-8")
    laje = (STATIC / "laje_ficha.js").read_text(encoding="utf-8")
    fundo = (STATIC / "fv_ficha.js").read_text(encoding="utf-8")
    pilar = (STATIC / "pillar_ficha.js").read_text(encoding="utf-8")
    template = (TEMPLATES / "obra_detalhe.html").read_text(encoding="utf-8")

    assert "Escolha o modo de desenho" in helper
    assert "Modo de desenho: " in helper
    assert "window.escolherModoDesenho" in drill
    assert "body.visual_mode = visualMode" in drill
    assert "window.escolherModoDesenho" in laje
    assert "window.escolherModoDesenho" in fundo
    assert "window.escolherModoDesenho" in pilar
    assert "window.aplicarTagModoDesenho" in laje
    assert "window.aplicarTagModoDesenho" in fundo
    assert "window.aplicarTagModoDesenho" in pilar
    assert 'data-drawing-mode="{{ release.visual_mode }}"' in template
    assert "/static/drawing_mode.js" in template
    assert "onChange" in helper
    assert "window.atualizarModoDesenhoUrl" in helper
    assert "history.replaceState" in helper
    assert "modo_desenho" in template


def _preview(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.new("R2018")
    doc.modelspace().add_text(label, dxfattribs={"insert": (0, 0), "height": 10})
    doc.saveas(path)


def test_n3_laje_acumula_e_resolve_os_dois_modos(tmp_path):
    obra = tmp_path / "Obra"
    root = obra / "Fase-6_Execucao_CAD" / "production_sa" / "13_PAV"
    for run_name, mode in (("001-nova", "NOVA"), ("002-ini", "INI")):
        run = root / run_name
        _preview(run / "n3" / "dxf" / "LJ_preview_L1.dxf", mode)
        (run / "production_manifest.json").write_text(
            '{"visual_mode":"' + mode + '"}', encoding="utf-8",
        )

    item = {"beam_name": "L1"}
    nova = ficha_reader._n3_dxf_producao(obra, "13_PAV", "lajes", item, "NOVA")
    ini = ficha_reader._n3_dxf_producao(obra, "13_PAV", "lajes", item, "INI")

    assert nova and "001-nova" in str(nova)
    assert ini and "002-ini" in str(ini)
    assert ficha_reader.modos_visuais_n3_disponiveis(
        obra, "13_PAV", "lajes", item,
    ) == ["NOVA", "INI"]


def test_n3_pilar_modo_ausente_nao_reutiliza_legacy(tmp_path):
    obra = tmp_path / "Obra"
    legacy = obra / "Fase-6_Execucao_CAD" / "n3_variants" / "para" / "PL_CIMA_preview_P1.dxf"
    _preview(legacy, "NOVA")

    item = {"beam_name": "P1", "pavimento": "13_PAV"}
    assert ficha_reader._pilar_n3_dxf(obra, item, "cima", "NOVA") == legacy
    assert ficha_reader._pilar_n3_dxf(obra, item, "cima", "INI") is None


def test_n3_pilar_acumula_variantes_e_resolve_cada_modo(tmp_path):
    obra = tmp_path / "Obra"
    root = obra / "Fase-6_Execucao_CAD" / "n3_modes"
    nova = root / "NOVA" / "pilares" / "para" / "PL_CIMA_preview_P1.dxf"
    ini = root / "INI" / "pilares" / "para" / "PL_CIMA_preview_P1.dxf"
    _preview(nova, "NOVA")
    _preview(ini, "INI")

    item = {"beam_name": "P1", "pavimento": "13_PAV"}
    assert ficha_reader._pilar_n3_dxf(obra, item, "cima", "NOVA") == nova
    assert ficha_reader._pilar_n3_dxf(obra, item, "cima", "INI") == ini
    assert ficha_reader.modos_visuais_n3_disponiveis(
        obra, "13_PAV", "pilares", item, vista="cima",
    ) == ["NOVA", "INI"]
