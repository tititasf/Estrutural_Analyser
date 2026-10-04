import json

import ezdxf

from portal.app import ficha_reader as fr
from portal.app.routers import viewer_routes


def test_cortes_contexto_real_prioriza_estrutural_e_preserva_fonte(tmp_path, monkeypatch):
    source = tmp_path / "torre_1.dxf"
    doc = ezdxf.new("R2018")
    doc.modelspace().add_lwpolyline([(0, 0), (1000, 0), (1000, 800), (0, 800)], close=True)
    doc.modelspace().add_text("CONTEXTO", dxfattribs={"insert": (400, 400), "height": 20})
    doc.saveas(source)
    original = source.read_bytes()
    run = tmp_path / "Fase-6_Execucao_CAD/production_sa/13_PAV/run-1"
    run.mkdir(parents=True)
    (run / "production_manifest.json").write_text(json.dumps({"source_dxf": str(source)}))
    item = {"item_id": "cut-1", "beam_name": "V1", "points": [[420, 420], [470, 420], [470, 450], [420, 450]]}
    monkeypatch.setattr(fr, "extrair_fotos_ficha", lambda *_: {"n1": '<svg id="isolado"/>', "n3": None})
    result = fr.resolver_fotos_portal(tmp_path, "13_PAV", "cortes", item)
    assert result["n1_origem"] == "recorte_contextual_estrutural"
    assert 'id="sa-corte-highlight"' in result["n1"]
    assert 'id="isolado"' not in result["n1"]
    assert 'cad-thin-strokes="1"' in result["n1"]
    assert '>V1</text>' in result["n1"]
    assert source.read_bytes() == original
    assert fr.resolver_foto_portal(tmp_path, "13_PAV", "cortes", item, "n1")["svg"] == result["n1"]


def test_corte_sem_estrutural_nao_finge_recorte(tmp_path):
    result = fr.resolver_foto_portal(tmp_path, "13_PAV", "cortes", {"points": [[0, 0], [10, 10]]}, "n1")
    assert result == {"svg": None, "origem": None}


def test_viewer_expoe_geometria_dos_cortes():
    class Transform:
        largura_px = altura_px = 1000

        def dxf_para_px(self, x, y):
            return (x, 1000 - y)

    estado = {"cortes": [{"uid": "cut-1", "beam_name": "V1", "pts": [[10, 20], [40, 20], [40, 50]]}]}
    assert ("cortes", "Visão de Cortes", ("cortes",)) in viewer_routes.GRUPOS_VIEWER
    items = viewer_routes._geometria_dos_itens(estado, "cortes", Transform())
    assert items[0]["item_id"] == "cut-1"
    assert items[0]["pontos_px"] == [(10, 980), (40, 980), (40, 950)]
