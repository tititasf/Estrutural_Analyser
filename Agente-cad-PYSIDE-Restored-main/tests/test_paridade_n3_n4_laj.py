from scripts.arete.paridade_n3_n4_laj import clean_n3_ficha, gabarito_references


def test_gabarito_guard_is_recursive_and_case_insensitive():
    value = {"_sa_meta": {"pattern": "n4_dxf:Obra:L1"}}
    assert gabarito_references(value) == ["$._sa_meta.pattern=n4_dxf:Obra:L1"]


def test_clean_n3_uses_raw_outline_without_gabarito(monkeypatch):
    monkeypatch.setattr(
        "src.core.laj_n3_learning.load_patterns",
        lambda: [
            {
                "nome": "L1",
                "comprimento": 999,
                "largura": 999,
                "coordenadas": [[0, 0], [999, 0], [999, 999], [0, 999]],
                "linhas_verticais": [{"value": 333}],
                "linhas_horizontais": [],
                "source": "N4_DXF:Obra:L1",
            }
        ],
    )
    raw = {
        "name": "L1",
        "points": [[10, 20], [110, 20], [110, 70], [10, 70]],
        "area_cm2": 5000,
        "links": {
            "laje_outline_segs": {
                "contour": [{"points": [[10, 20], [110, 20], [110, 70], [10, 70]]}]
            }
        },
    }
    ficha = clean_n3_ficha(raw)
    assert ficha["comprimento"] == 100
    assert ficha["largura"] == 50
    assert ficha["linhas_verticais"] == [{"value": 50.0, "is_union": False}]
    assert all(line["value"] != 333 for line in ficha["linhas_verticais"])
    assert ficha["_stog_pose"] == {"x": 10.0, "y": 20.0}
    assert gabarito_references(ficha) == []
