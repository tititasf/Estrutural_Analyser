from pathlib import Path

import json

import ezdxf

from portal.app import dxf_preview as dp
from portal.app import ficha_reader as fr
from portal.app import laje_ficha


def _save_doc(path: Path, points, layer: str) -> None:
    doc = ezdxf.new("R2018")
    doc.modelspace().add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
    doc.saveas(path)


def test_recorte_contextual_laje_grande_usa_estrutural_inteiro():
    estrutural = (0.0, 0.0, 4000.0, 1800.0)
    assert fr._recorte_contextual_laje(
        (400.0, 700.0, 3400.0, 900.0), estrutural,
    ) == estrutural


def test_recorte_contextual_laje_normal_adiciona_margem_e_limita_na_planta():
    assert fr._recorte_contextual_laje(
        (100.0, 200.0, 500.0, 400.0), (0.0, 0.0, 4000.0, 1800.0),
    ) == (0.0, 0.0, 800.0, 700.0)


def test_sa_laje_renderiza_recorte_estrutural_contextual_com_cache(tmp_path):
    obra = tmp_path / "Obra"
    estrutural = tmp_path / "estrutural.dxf"
    _save_doc(estrutural, [(0, 0), (1000, 0), (1000, 600), (0, 600)], "ESTRUTURAL")
    run = obra / "Fase-6_Execucao_CAD" / "production_sa" / "13_PAV" / "run-1"
    run.mkdir(parents=True)
    (run / "production_manifest.json").write_text(
        json.dumps({"source_dxf": str(estrutural)}), encoding="utf-8",
    )

    svg = fr._svg_sa_laje_contextual(
        obra,
        "13_PAV",
        {"points": [[300, 200], [700, 200], [700, 400], [300, 400]]},
    )

    assert svg is not None and "<svg" in svg
    assert 'cad-thin-strokes="1"' in svg
    assert 'id="sa-laje-highlight"' in svg
    assert 'aria-label="Destaque SA Laje"' in svg
    cache = obra / ".previews" / "sa_laje_context"
    assert len(list(cache.glob("*.svg"))) == 1
    assert len(list(cache.glob("*.transform.json"))) == 1


def test_destaque_laje_mapeia_coordenadas_dxf_no_viewbox():
    svg = b'<svg viewBox="0 0 1000 500" xmlns="http://www.w3.org/2000/svg"></svg>'

    result = fr._destacar_laje_no_svg(
        svg,
        (0.0, 0.0, 200.0, 100.0),
        [[20.0, 20.0], [180.0, 20.0], [180.0, 80.0], [20.0, 80.0]],
        "L318",
    ).decode("utf-8")

    assert 'id="sa-laje-highlight"' in result
    assert 'aria-label="Destaque SA L318"' in result
    assert 'points="100.000,400.000 900.000,400.000 900.000,100.000 100.000,100.000"' in result
    assert '>L318</text>' in result


def test_fotos_laje_usam_contexto_no_sa_e_n3_compacto(monkeypatch, tmp_path):
    n3 = tmp_path / "LJ_preview_L318.dxf"
    n3.touch()
    calls = []
    monkeypatch.setattr(fr, "_svg_sa_laje_contextual", lambda *_: '<svg id="sa"/>')
    monkeypatch.setattr(fr, "_n3_dxf_producao", lambda *_: n3)

    def fake_render(path, cache_dir, **kwargs):
        calls.append((path, cache_dir, kwargs))
        return b'<svg id="n3"/>'

    monkeypatch.setattr(dp, "renderizar_dxf_svg_cacheado", fake_render)
    fotos = fr.extrair_fotos_producao(
        tmp_path,
        "13_PAV",
        "lajes",
        {"beam_name": "L318", "points": [[0, 0], [100, 0], [100, 20]]},
    )

    assert fotos == {"n1": '<svg id="sa"/>', "n3": '<svg id="n3"/>'}
    assert len(calls) == 1
    assert calls[0][0] == n3
    assert calls[0][1].name == "sa_production"
    assert calls[0][2]["margem_pct"] == 0.03


def test_camada_sa_sob_demanda_usa_recorte_contextual(monkeypatch, tmp_path):
    item = {"item_id": "L318", "points": [[0, 0], [100, 0], [100, 20]]}
    monkeypatch.setattr(fr, "obter_item_n1", lambda *_: item)
    monkeypatch.setattr(
        fr,
        "extrair_fotos_producao",
        lambda *_: {"n1": '<svg id="sa-contextual"/>', "n3": '<svg id="n3-compacto"/>'},
    )

    camada = laje_ficha.resolver_camada_laje(
        tmp_path, "13_PAV", "L318", {"items": []}, "sa",
    )

    assert camada == {
        "layer": "sa",
        "available": True,
        "svg": '<svg id="sa-contextual"/>',
        "origem": "recorte_contextual_estrutural",
    }
