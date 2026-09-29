"""Box do apontamento: entidades do estrutural limpo dentro/tocando a janela DXF."""
from pathlib import Path

import ezdxf

from portal.app.routers.viewer_routes import entidades_na_regiao


def _dxf(tmp_path: Path) -> Path:
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((10, 10), (20, 10), dxfattribs={"layer": "VIGA"})        # dentro
    msp.add_line((0, 15), (50, 15), dxfattribs={"layer": "VIGA"})         # atravessa
    msp.add_line((100, 100), (120, 100), dxfattribs={"layer": "VIGA"})    # fora
    msp.add_text("V306", dxfattribs={"layer": "TXT", "insert": (12, 12)})
    msp.add_text("V999", dxfattribs={"layer": "TXT", "insert": (200, 200)})
    caminho = tmp_path / "torre_1.dxf"
    doc.saveas(caminho)
    return caminho


def test_regiao_separa_dentro_toca_e_fora(tmp_path):
    r = entidades_na_regiao(_dxf(tmp_path), 5, 5, 30, 30)
    assert r["total"] == 3
    estados = sorted(e["e"] for e in r["entidades"])
    assert estados == ["d", "d", "t"]
    assert [t["texto"] for t in r["textos"]] == ["V306"]
    assert r["por_layer"] == {"VIGA": 2, "TXT": 1}


def test_regiao_aceita_cantos_invertidos(tmp_path):
    r = entidades_na_regiao(_dxf(tmp_path), 30, 30, 5, 5)
    assert r["regiao"] == [5, 5, 30, 30]
    assert r["total"] == 3
