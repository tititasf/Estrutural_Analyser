from __future__ import annotations

import json
from pathlib import Path

import pytest

from portal.app import fv_ficha


def _estado_v301() -> dict:
    return {
        "segmentos": {
            "fundo": [
                {
                    "uid": "fv-v301-s1",
                    "beam_name": "V301",
                    "segment_label": "1",
                    "behavior": "Fundo",
                    "length": 305.5,
                    "width": 19,
                    "points": [[0, 0], [305.5, 0], [305.5, 19], [0, 19]],
                },
                {
                    "uid": "fv-v301-s2",
                    "beam_name": "V301",
                    "segment_label": "2",
                    "behavior": "Fundo",
                    "length": 100,
                    "width": 19,
                    "points": [[306, 0], [406, 0], [406, 19], [306, 19]],
                },
                {
                    "uid": "fv-v302-s1",
                    "beam_name": "V302",
                    "segment_label": "1",
                    "behavior": "Fundo",
                    "length": 90,
                    "width": 20,
                    "points": [[0, 30], [90, 30], [90, 50], [0, 50]],
                },
            ]
        }
    }


def _write_hifi(root: Path, *, include_extra_segment: bool = True) -> Path:
    folder = root / "pack_hifi_v20" / "fundos_viga"
    (folder / "n3").mkdir(parents=True)
    (folder / "propostas").mkdir()
    (folder / "n3" / "V301_n3.svg").write_text(
        '<svg viewBox="0 0 50 20"><g class="fv-n3-seg" data-n3-seg="1"><path d="M0 0H10V5Z"/></g></svg>',
        encoding="utf-8",
    )
    (folder / "propostas" / "V301_qa_proposta_c1.svg").write_text(
        '<svg viewBox="0 0 50 20"><path d="M0 0L5 5"/></svg>', encoding="utf-8",
    )
    (folder / "propostas" / "V301_qa_proposta_c1.json").write_text(
        json.dumps({"beam": "V301", "proposed": [
            {"label": "1", "points": [[0, 0], [10, 0], [10, 2], [0, 2], [0, 0]]},
            {"label": "2", "points": [[12, 0], [22, 0], [22, 2], [12, 2], [12, 0]]},
        ]}), encoding="utf-8",
    )
    html = """
    <div class="fv-seg-table-wrap"><table class="fv-seg-table"><tbody>
      <tr class="fv-seg-item" data-seg="1"><td>›</td><td>1</td><td>305.5</td><td>19</td><td>55</td><td>852.19</td><td>P1</td><td>V312</td><td>2</td></tr>
      <tr class="fv-seg-detail" data-seg="1"><td colspan="9"><div class="fv-seg-body">
        <div class="fv-mini-block"><div class="fv-mini-title">Painéis N3</div><table class="fv-panel-table"><tbody>
          <tr><td>1</td><td>244</td><td>19</td></tr><tr><td>2</td><td>61.5</td><td>19</td></tr>
        </tbody></table></div>
        <div class="fv-mini-block"><div class="fv-mini-title">Chanfros</div><div class="fv-mini-field"><span>Esq. topo</span><b>—</b></div></div>
        <div class="fv-mini-block"><div class="fv-mini-title">Aberturas</div><div class="fv-mini-field"><span>Topo esq.</span><b>12</b></div></div>
      </div></td></tr>
      <tr class="fv-seg-item" data-seg="2"><td>›</td><td>2</td><td>100</td><td>19</td><td>120</td><td>852.19</td><td>V312</td><td>P11</td><td>1</td></tr>
      <tr class="fv-seg-detail" data-seg="2"><td colspan="9"><div class="fv-mini-block"><div class="fv-mini-title">Painéis N3</div><table class="fv-panel-table"><tbody><tr><td>1</td><td>100</td><td>19</td></tr></tbody></table></div></td></tr>
      {extra_segment}
    </tbody></table></div>
    <div class="fv-layer fv-layer-sa"><svg viewBox="0 0 100 40"><text>S1</text></svg></div>
    <div class="fv-layer fv-layer-c1" data-proposal-src="propostas/V301_qa_proposta_c1.svg"></div>
    <div class="fv-layer fv-layer-c2"></div><div class="fv-layer fv-layer-c3"></div>
    <div class="fv-layer fv-layer-n3" data-n3-src="n3/V301_n3.svg"></div>
    """
    extra_segment = (
        '<tr class="fv-seg-item" data-seg="99"><td>›</td><td>99</td><td>999</td>'
        '<td>19</td><td>99</td><td>0</td><td>—</td><td>—</td><td>0</td></tr>'
        if include_extra_segment else ""
    )
    html = html.format(extra_segment=extra_segment)
    path = folder / "V301.html"
    path.write_text(html, encoding="utf-8")
    return path


def _write_current_contract(obra: Path) -> Path:
    run = obra / "Fase-6_Execucao_CAD" / "production_sa" / "13_PAV" / "20260910_120000_1"
    (run / "n3" / "contracts").mkdir(parents=True)
    (run / "production_manifest.json").write_text('{"schema":"cad.sa.production/v1"}', encoding="utf-8")
    contract = {
        "name": "V301", "total_width": 19, "total_height": 55,
        "segments_rich": [
            {"comprimento_total_fundo": 305.5, "largura_total_fundo": 19,
             "altura_total": 55, "texto_esq": "P1", "texto_dir": "V312"},
            {"comprimento_total_fundo": 100, "largura_total_fundo": 19,
             "altura_total": 120, "texto_esq": "V312", "texto_dir": "P11"},
        ],
    }
    path = run / "n3" / "contracts" / "V301_fundo.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    return path


def test_montar_ficha_fv_agrupa_viga_e_enriquece_com_contrato_atual(tmp_path):
    html_path = _write_hifi(tmp_path / "html")
    contract_path = _write_current_contract(tmp_path / "obra")
    result = fv_ficha.montar_ficha_fv(
        tmp_path / "obra", "13_PAV", "V301", _estado_v301(),
        html_fichas_root=tmp_path / "html",
    )

    assert result["schema"] == "portal.fv.ficha/v1"
    assert result["beam"] == {
        "name": "V301", "position": 1, "total_beams": 2,
        "segment_count": 2, "previous": None, "next": "V302",
    }
    assert [segment["index"] for segment in result["segments"]] == [1, 2]
    first = result["segments"][0]
    assert first["beam_height_cm"] == 55
    assert first["level"] is None
    assert first["support_start"] == "P1"
    assert first["support_end"] == "V312"
    assert first["n3"]["panels"] == [
        {"index": 1, "length_cm": 244, "width_cm": 19},
        {"index": 2, "length_cm": 61.5, "width_cm": 19},
    ]
    assert first["n3"]["openings"] == {}
    assert first["enrichment_status"] == "matched"
    assert result["context"]["layers"]["sa"]["available"] is True
    assert [row["index"] for row in result["context"]["layers"]["c1"]["segments"]] == [1, 2]
    assert result["context"]["layers"]["n3"]["available"] is False
    assert result["source"]["contract"] == str(contract_path)
    assert result["source"]["legacy_html_reference"] == html_path.name
    assert result["source"]["segment_enrichment"] == {
        "matched": 2, "mismatch": 0, "absent": 0,
    }


def test_ficha_hifi_nao_cria_segmento_que_nao_existe_no_estado(tmp_path):
    _write_hifi(tmp_path / "html")
    result = fv_ficha.montar_ficha_fv(
        tmp_path / "obra", "13_PAV", "V301", _estado_v301(),
        html_fichas_root=tmp_path / "html",
    )
    assert 99 not in {segment["index"] for segment in result["segments"]}


def test_ficha_fv_usa_svg_sa_contextual_como_camada_visual(tmp_path):
    _write_hifi(tmp_path / "html", include_extra_segment=False)
    result = fv_ficha.montar_ficha_fv(
        tmp_path / "obra", "13_PAV", "V301", _estado_v301(),
        html_fichas_root=tmp_path / "html",
    )

    assert result["source"]["sa_visual_origin"] == "hifi_contextual"
    assert "<text>S1</text>" in result["context"]["layers"]["sa"]["svg"]


def test_ficha_fv_deriva_nivel_do_segmento_de_snapshot_antigo(tmp_path):
    estado = _estado_v301()
    estado["slabs"] = [{
        "name": "L301", "nivel": "852.19",
        "points": [[0, 19], [305.5, 19], [305.5, 80], [0, 80]],
    }]
    result = fv_ficha.montar_ficha_fv(tmp_path / "obra", "13_PAV", "V301", estado)

    assert result["segments"][0]["level"] == 852.19
    assert result["segments"][0]["level_source"] == "highest_touching_slab"
    assert result["segments"][0]["level_slabs"] == ["L301"]


def test_ficha_fv_nunca_substitui_contextual_por_poligono_minimo(tmp_path):
    _write_hifi(tmp_path / "html", include_extra_segment=True)
    result = fv_ficha.montar_ficha_fv(
        tmp_path / "obra", "13_PAV", "V301", _estado_v301(),
        html_fichas_root=tmp_path / "html",
    )

    assert result["source"]["sa_visual_origin"] == "hifi_contextual"
    assert "<text>S1</text>" in result["context"]["layers"]["sa"]["svg"]
    assert "geometria N1 persistida" not in result["context"]["layers"]["sa"]["svg"]


def test_nome_de_viga_invalido_falha_fechado(tmp_path):
    with pytest.raises(ValueError, match="invalido"):
        fv_ficha.montar_ficha_fv(tmp_path, "13_PAV", "../V301", _estado_v301())


def test_html_de_outra_segmentacao_nao_sobrescreve_sa_atual():
    base = {
        "index": 1, "length_cm": 382, "width_cm": 19,
        "beam_height_cm": None, "level": None,
        "support_start": None, "support_end": None,
        "n3": {"available": False, "panels": [], "chamfers": {}, "openings": {}},
    }
    rich = {
        "index": 1, "length_cm": 232, "width_cm": 19,
        "beam_height_cm": 50, "level": 852.19,
        "support_start": "P1", "support_end": "P2",
        "n3": {"available": True, "panels": [{"index": 1}]},
    }
    merged = fv_ficha._merge_segment(base, rich)
    assert merged["length_cm"] == 382
    assert merged["beam_height_cm"] is None
    assert merged["n3"]["available"] is False
    assert merged["enrichment_status"] == "mismatch"
    assert merged["hifi_reference"] == {"length_cm": 232, "width_cm": 19}


def test_frontend_fv_usa_viewbox_e_esta_ligado_ao_template():
    repo = Path(__file__).resolve().parents[2]
    js = (repo / "portal" / "app" / "static" / "fv_ficha.js").read_text(encoding="utf-8")
    template = (repo / "portal" / "app" / "templates" / "obra_detalhe.html").read_text(encoding="utf-8")
    assert "setAttribute('viewBox'" in js
    assert "transform: scale" not in js
    assert "['sa', 'n3'].indexOf(name)" not in js
    assert "SA atual preservado" in js
    assert "FvFicha.mount" in template
    assert "/static/fv_ficha.js" in template
    assert "/static/fv_ficha.css" in template
    assert "Adotar Camada Agentica como SA" in js
    assert "Excluir Camada Agentica" in js
    assert "Validar Todos Segmentos" in js
    assert "Validar Segmento" in js
    assert "Desvalidar Segmento" in js
    assert "Desvalidar segmento" in js
    assert "JSON.stringify({validado: validado})" in js
    assert "Editar Segmento" in js
    assert "Excluir Segmento" in js
    assert "data-fv-segtabs" in js
    assert "data-fv-toggle-highlight" in js
    assert "Ocultar destaque" in js
    assert "data-fv-edit-ortho" in js
    assert "OSNAP automático" in js
    assert "event.button === 1" in js
    assert "canvas.addEventListener('mousedown'" in js
    assert "window.addEventListener('mousemove'" in js
    assert "window.addEventListener('mouseup'" in js
    assert "event.stopPropagation()" in js
    assert "canvas.addEventListener('pointerdown'" not in js
    assert "isDragging: function" in js
    assert "Botão do meio arrasta o viewer" in js
    assert "window.nearestSnapClient = nearestSnapClient" in template
    assert "window.screenPxToSvgUnits = screenPxToSvgUnits" in template
