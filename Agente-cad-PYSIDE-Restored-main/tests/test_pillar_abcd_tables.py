"""Testes das tabelas ABCD (laje/passa/chega/interior + dualidade CA/CB)."""
from src.core.pillar_abcd_tables import (
    apply_c_dualidade,
    apply_c_interior_suppress_top_dual,
    apply_interior_d_as_passa_ab,
    build_abcd_tables_from_pillar,
    fill_cantos_all_rows,
    format_abcd_tables_html,
    lines_from_tables,
)


def test_fill_cantos_laje_interior_passa():
    faces = {
        "A": {
            "lajes": [
                {
                    "nome": "L301",
                    "dim": "12",
                    "nivel": "852",
                    "canto": "—",
                    "dist_esq": "14cm",
                    "dist_dir": "0cm",
                }
            ],
            "passa": [
                {
                    "nome": "V312",
                    "dim": "19/120",
                    "nivel": "852",
                    "canto": "—",
                    "dist_esq": "—",
                    "dist_dir": "—",
                }
            ],
            "chega": [],
            "interior": [],
        },
        "B": {
            "lajes": [
                {
                    "nome": "L302",
                    "dim": "12",
                    "nivel": "852",
                    "canto": "",
                    "dist_esq": "0cm",
                    "dist_dir": "14cm",
                }
            ],
            "passa": [],
            "chega": [],
            "interior": [],
        },
        "C": {"lajes": [], "passa": [], "chega": [], "interior": []},
        "D": {
            "lajes": [],
            "passa": [],
            "chega": [],
            "interior": [
                {
                    "nome": "V312",
                    "dim": "19/120",
                    "nivel": "852",
                    "canto": "—",
                    "dist_esq": "0cm",
                    "dist_dir": "0cm",
                }
            ],
        },
    }
    fill_cantos_all_rows(faces, vertical=True)
    assert faces["A"]["lajes"][0]["canto"] == "AD"  # d.dir=0
    assert faces["B"]["lajes"][0]["canto"] == "BD"  # d.esq=0
    assert faces["A"]["passa"][0]["canto"] == "AA"  # passa mid
    assert faces["D"]["interior"][0]["canto"] == "DD"


def test_interior_d_promotes_passa_ab():
    tables = {
        "A": {"lajes": [], "passa": [], "chega": [], "interior": []},
        "B": {"lajes": [], "passa": [], "chega": [], "interior": []},
        "C": {"lajes": [], "passa": [], "chega": [], "interior": []},
        "D": {
            "lajes": [],
            "passa": [],
            "chega": [],
            "interior": [
                {
                    "familia": "viga",
                    "nome": "V312",
                    "dim": "19/120",
                    "nivel": "852.19cm",
                    "canto": "—",
                    "papel": "interior",
                    "raw": "",
                }
            ],
        },
    }
    apply_interior_d_as_passa_ab(tables)
    assert any(r["nome"] == "V312" for r in tables["A"]["passa"])
    assert any(r["nome"] == "V312" for r in tables["B"]["passa"])


def test_dualidade_ac_ca_not_for_interior():
    tables = {
        "A": {"lajes": [], "passa": [], "chega": [], "interior": []},
        "B": {"lajes": [], "passa": [], "chega": [], "interior": []},
        "C": {
            "lajes": [],
            "passa": [
                {
                    "familia": "viga",
                    "nome": "VF301",
                    "dim": "14/55",
                    "nivel": "852.19cm",
                    "canto": "CA",
                    "papel": "passa",
                    "raw": "",
                },
                {
                    "familia": "viga",
                    "nome": "VF301",
                    "dim": "19/66",
                    "nivel": "852.19cm",
                    "canto": "CB",
                    "papel": "passa",
                    "raw": "",
                },
            ],
            "chega": [],
            "interior": [],
        },
        "D": {
            "lajes": [],
            "passa": [],
            "chega": [],
            "interior": [
                {
                    "familia": "viga",
                    "nome": "V312",
                    "dim": "19/120",
                    "nivel": "852.19cm",
                    "canto": "—",
                    "papel": "interior",
                    "raw": "",
                }
            ],
        },
    }
    apply_c_dualidade(tables)
    assert any(r["nome"] == "VF301" and r["canto"] == "AC" for r in tables["A"]["chega"])
    assert any(r["nome"] == "VF301" and r["canto"] == "BC" for r in tables["B"]["chega"])
    # interior não vaza para C
    assert not any(r["nome"] == "V312" for r in tables["C"]["passa"])


def test_build_from_face_beams_p2_shape():
    pillar = {
        "name": "P2",
        "orientation": "vertical",
        "points": [[0, 0], [19, 0], [19, 66], [0, 66]],
        "lajes": [
            {"laje": "L301", "side": "A", "content_type": "laje"},
            {"laje": "L302", "side": "B", "content_type": "laje"},
        ],
        "face_beams": {
            "A": {
                "passa_esq": None,
                "passa_dir": {
                    "name": "V312",
                    "dim": "19/120",
                    "corner": "AD",
                    "behavior": "para",
                },
                "corner_esq": "AC",
                "corner_dir": "AD",
                "para": [],
                "interior": [],
            },
            "B": {
                "passa_esq": {
                    "name": "V312",
                    "dim": "19/120",
                    "corner": "BD",
                    "behavior": "para",
                },
                "passa_dir": None,
                "corner_esq": "BD",
                "corner_dir": "BC",
                "para": [],
                "interior": [],
            },
            "C": {
                "passa_esq": None,
                "passa_dir": None,
                "corner_esq": "CA",
                "corner_dir": "CB",
                "para": [],
                "interior": [],
            },
            "D": {
                "passa_esq": None,
                "passa_dir": None,
                "corner_esq": "DA",
                "corner_dir": "DB",
                "para": [],
                "interior": [{"name": "V312", "dim": "19/120"}],
            },
        },
    }
    payload = build_abcd_tables_from_pillar(
        pillar,
        slab_height_map={"L301": "12", "L302": "12"},
        slab_nivel_map={"L301": "852.12", "L302": "852.12"},
        nivel_viga_default="852.19cm",
    )
    faces = payload["faces"]
    assert faces["A"]["lajes"][0]["nome"] == "L301"
    assert any(r["nome"] == "V312" for r in faces["A"]["passa"])
    assert any(r["nome"] == "V312" for r in faces["D"]["interior"])
    # V312 interior não vira chega AC nem passa C
    assert not any(r["nome"] == "V312" for r in faces["A"]["chega"] if r["nome"] != "nenhuma")
    assert not any(r["nome"] == "V312" for r in faces["C"]["passa"] if r["nome"] != "nenhuma")
    html = format_abcd_tables_html(payload)
    assert "abcd-grid" in html
    lines = lines_from_tables(payload)
    assert lines["D"]["interior"]


def test_dist_esq_dir_laje_and_not_passa():
    """Laje parcial na face A: dist_esq/dir; passante sem distâncias."""
    # Pilar 19×66; laje toca face A só na metade superior (y 33..66)
    pillar = {
        "name": "PX",
        "orientation": "vertical",
        "points": [[0, 0], [19, 0], [19, 66], [0, 66]],
        "lajes": [{"laje": "L1", "side": "A", "content_type": "laje"}],
        "face_beams": {
            "A": {
                "passa_dir": {"name": "V9", "dim": "19/120", "corner": "AD", "behavior": "para"},
                "para": [{"name": "VF1", "dim": "14/55", "corner": "AC"}],
                "corner_esq": "AC",
                "corner_dir": "AD",
                "passa_esq": None,
                "interior": [],
            },
            "B": {"passa_esq": None, "passa_dir": None, "para": [], "interior": [],
                  "corner_esq": "BD", "corner_dir": "BC"},
            "C": {"passa_esq": None, "passa_dir": None, "para": [], "interior": [],
                  "corner_esq": "CA", "corner_dir": "CB"},
            "D": {
                "passa_esq": None,
                "passa_dir": None,
                "para": [],
                "interior": [{"name": "V9", "dim": "19/120"}],
                "corner_esq": "DA",
                "corner_dir": "DB",
            },
        },
    }
    payload = build_abcd_tables_from_pillar(
        pillar,
        slab_height_map={"L1": "12"},
        slab_nivel_map={"L1": "852.12"},
        slab_points_map={"L1": [[-100, 33], [0, 33], [0, 66], [-100, 66]]},
        beams=[{"name": "VF1", "dim": "14/55", "is_h": True,
                "points": [[-20, 52], [0, 52], [0, 66], [-20, 66]]}],
        nivel_viga_default="852.19cm",
    )
    laje = payload["faces"]["A"]["lajes"][0]
    assert laje["nome"] == "L1"
    # Face A: esq=AC (y=66), dir=AD (y=0). Laje y 33..66 → d.esq≈0, d.dir≈33
    assert laje["dist_esq"] in ("0cm", "0.0cm") or laje["dist_esq"].startswith("0")
    assert "33" in laje["dist_dir"] or laje["dist_dir"] != "—"
    passa = next(r for r in payload["faces"]["A"]["passa"] if r["nome"] == "V9")
    assert passa["dist_esq"] == "—" and passa["dist_dir"] == "—"
    chega = next(r for r in payload["faces"]["A"]["chega"] if r["nome"] == "VF1")
    # canto AC + faixa topo 14: d.esq=0, d.dir=52 (não bbox global)
    assert chega["dist_esq"] in ("0cm", "0")
    assert "52" in chega["dist_dir"]


def test_chega_ac_bc_same_band_not_19_from_dim():
    """A@AC 14/55 e B@BC 19/66: ambos usam faixa 14 cm → 0/52 e 52/0 (não 47)."""
    pillar = {
        "name": "P2",
        "orientation": "vertical",
        "points": [[1603.0, 3141.0], [1622.0, 3141.0], [1622.0, 3207.0], [1603.0, 3207.0]],
        "lajes": [
            {"laje": "L301", "side": "A", "content_type": "laje"},
            {"laje": "L302", "side": "B", "content_type": "laje"},
        ],
        "face_beams": {
            "A": {
                "passa_esq": None,
                "passa_dir": {"name": "V312", "dim": "19/120", "corner": "AD", "behavior": "para"},
                "para": [{"name": "VF301", "dim": "14/55", "corner": "AC"}],
                "interior": [],
                "corner_esq": "AC",
                "corner_dir": "AD",
            },
            "B": {
                "passa_esq": {"name": "V312", "dim": "19/120", "corner": "BD", "behavior": "para"},
                "passa_dir": None,
                "para": [{"name": "VF301", "dim": "19/66", "corner": "BC"}],
                "interior": [],
                "corner_esq": "BD",
                "corner_dir": "BC",
            },
            "C": {
                "passa_esq": {"name": "VF301", "dim": "14/55", "corner": "CA"},
                "passa_dir": {"name": "VF301", "dim": "19/66", "corner": "CB"},
                "para": [],
                "interior": [],
                "corner_esq": "CA",
                "corner_dir": "CB",
            },
            "D": {
                "passa_esq": None,
                "passa_dir": None,
                "para": [],
                "interior": [{"name": "V312", "dim": "19/120"}],
                "corner_esq": "DA",
                "corner_dir": "DB",
            },
        },
    }
    # lajes param em y=3193 → banda 3207-3193=14
    payload = build_abcd_tables_from_pillar(
        pillar,
        slab_height_map={"L301": "12", "L302": "12"},
        slab_nivel_map={"L301": "852.12", "L302": "852.12"},
        slab_points_map={
            "L301": [[1200, 3010], [1603, 3010], [1603, 3193], [1200, 3193]],
            "L302": [[1622, 3010], [2040, 3010], [2040, 3193], [1622, 3193]],
        },
        nivel_viga_default="852.19cm",
    )
    ca = next(r for r in payload["faces"]["A"]["chega"] if r["nome"] == "VF301")
    cb = next(r for r in payload["faces"]["B"]["chega"] if r["nome"] == "VF301")
    assert ca["dist_esq"] == "0cm" and ca["dist_dir"] == "52cm"
    assert cb["dist_esq"] == "52cm" and cb["dist_dir"] == "0cm"
    # não 47 (que vinha de 66-19 da dim 19/66)
    assert cb["dist_esq"] != "47cm"


def test_c_para_cc_becomes_interior():
    pillar = {
        "name": "P15",
        "orientation": "vertical",
        "points": [[0, 0], [19, 0], [19, 100], [0, 100]],
        "lajes": [
            {"laje": "L1", "side": "A", "content_type": "laje"},
            {"laje": "L2", "side": "B", "content_type": "laje"},
        ],
        "face_beams": {
            "A": {
                "passa_dir": {"name": "V320", "dim": "19/120", "corner": "AD", "behavior": "para"},
                "para": [],
                "interior": [],
                "corner_esq": "AC",
                "corner_dir": "AD",
            },
            "B": {
                "passa_esq": {"name": "V320", "dim": "19/120", "corner": "BD", "behavior": "para"},
                "para": [],
                "interior": [],
                "corner_esq": "BD",
                "corner_dir": "BC",
            },
            "C": {
                "passa_esq": None,
                "passa_dir": None,
                "para": [{"name": "V320", "dim": "19/120", "corner": "CC"}],
                "interior": [],
                "corner_esq": "CA",
                "corner_dir": "CB",
            },
            "D": {
                "para": [],
                "interior": [{"name": "V320", "dim": "19/120"}],
                "corner_esq": "DA",
                "corner_dir": "DB",
            },
        },
    }
    payload = build_abcd_tables_from_pillar(pillar, nivel_viga_default="852cm")
    assert any(
        r["nome"] == "V320" for r in payload["faces"]["C"]["interior"] if r["nome"] != "nenhuma"
    )


def test_long_face_central_para_becomes_chega_not_interior():
    """Chegada perpendicular no meio da face longa mantém descrição de chegada."""
    pillar = {
        "name": "PX",
        "orientation": "horizontal",
        "points": [[0, 0], [100, 0], [100, 19], [0, 19]],
        "face_beams": {
            "A": {"para": [], "interior": [], "corner_esq": "AD", "corner_dir": "AC"},
            "B": {
                "para": [{"name": "V325", "dim": "19/120", "corner": "BB"}],
                "interior": [],
                "corner_esq": "BC",
                "corner_dir": "BD",
            },
            "C": {"para": [], "interior": [], "corner_esq": "CA", "corner_dir": "CB"},
            "D": {"para": [], "interior": [], "corner_esq": "DA", "corner_dir": "DB"},
        },
    }
    payload = build_abcd_tables_from_pillar(pillar, nivel_viga_default="852cm")
    assert any(
        row["nome"] == "V325" and row["canto"] == "BB"
        for row in payload["faces"]["B"]["chega"]
    )
    assert not any(
        row["nome"] == "V325"
        for row in payload["faces"]["B"]["interior"]
        if row["nome"] != "nenhuma"
    )


def test_c_interior_suppresses_top_dual():
    tables = {
        "A": {
            "lajes": [],
            "passa": [],
            "chega": [
                {
                    "nome": "V303",
                    "dim": "19/55",
                    "canto": "AC",
                    "papel": "chega",
                    "dist_esq": "0cm",
                    "dist_dir": "80cm",
                }
            ],
            "interior": [],
        },
        "B": {
            "lajes": [],
            "passa": [],
            "chega": [
                {
                    "nome": "V329",
                    "dim": "19/60",
                    "canto": "BC",
                    "papel": "chega",
                    "dist_esq": "80cm",
                    "dist_dir": "0cm",
                }
            ],
            "interior": [],
        },
        "C": {
            "lajes": [],
            "passa": [
                {"nome": "V303", "dim": "19/55", "canto": "CA", "papel": "passa"},
                {"nome": "V329", "dim": "19/60", "canto": "CB", "papel": "passa"},
            ],
            "chega": [],
            "interior": [
                {"nome": "VX", "dim": "19/55", "canto": "CC", "papel": "interior"}
            ],
        },
        "D": {"lajes": [], "passa": [], "chega": [], "interior": []},
    }
    apply_c_interior_suppress_top_dual(tables)
    assert not any(
        r.get("canto") in ("CA", "CB")
        for r in tables["C"]["passa"]
        if r.get("nome") not in ("", "—", "nenhuma")
    )
    assert any(r["canto"] == "AC" and r["papel"] == "passa" for r in tables["A"]["passa"])
    assert any(r["canto"] == "BC" and r["papel"] == "passa" for r in tables["B"]["passa"])
    assert not any(r["nome"] == "V303" for r in tables["A"]["chega"] if r.get("nome") != "nenhuma")


def test_dual_topo_dim_not_pillar_section():
    """CB 19/66 (seção pilar) → 14/55 (peer CA / faixa laje)."""
    pillar = {
        "name": "P2",
        "orientation": "vertical",
        "points": [[1603.0, 3141.0], [1622.0, 3141.0], [1622.0, 3207.0], [1603.0, 3207.0]],
        "lajes": [
            {"laje": "L301", "side": "A", "content_type": "laje"},
            {"laje": "L302", "side": "B", "content_type": "laje"},
        ],
        "face_beams": {
            "A": {
                "passa_esq": None,
                "passa_dir": {"name": "V312", "dim": "19/120", "corner": "AD", "behavior": "para"},
                "para": [{"name": "VF301", "dim": "14/55", "corner": "AC"}],
                "interior": [],
                "corner_esq": "AC",
                "corner_dir": "AD",
            },
            "B": {
                "passa_esq": {"name": "V312", "dim": "19/120", "corner": "BD", "behavior": "para"},
                "passa_dir": None,
                "para": [{"name": "VF301", "dim": "19/66", "corner": "BC"}],
                "interior": [],
                "corner_esq": "BD",
                "corner_dir": "BC",
            },
            "C": {
                "passa_esq": {"name": "VF301", "dim": "14/55", "corner": "CA"},
                "passa_dir": {"name": "VF301", "dim": "19/66", "corner": "CB"},
                "para": [],
                "interior": [],
                "corner_esq": "CA",
                "corner_dir": "CB",
            },
            "D": {
                "passa_esq": None,
                "passa_dir": None,
                "para": [],
                "interior": [{"name": "V312", "dim": "19/120"}],
                "corner_esq": "DA",
                "corner_dir": "DB",
            },
        },
    }
    payload = build_abcd_tables_from_pillar(
        pillar,
        slab_height_map={"L301": "12", "L302": "12"},
        slab_nivel_map={"L301": "852.12", "L302": "852.12"},
        slab_points_map={
            "L301": [[1200, 3010], [1603, 3010], [1603, 3193], [1200, 3193]],
            "L302": [[1622, 3010], [2040, 3010], [2040, 3193], [1622, 3193]],
        },
        nivel_viga_default="852.19cm",
    )
    bc = next(r for r in payload["faces"]["B"]["chega"] if r["nome"] == "VF301")
    cb = next(
        r
        for r in payload["faces"]["C"]["passa"]
        if r["nome"] == "VF301" and r["canto"] == "CB"
    )
    assert bc["dim"] == "14/55"
    assert cb["dim"] == "14/55"


def test_prune_phantom_ac_when_no_laje_a():
    """P1-like: só laje em B + dual com dim seção-pilar → remove AC/CA."""
    pillar = {
        "name": "P1",
        "orientation": "vertical",
        "points": [[0.0, 0.0], [19.0, 0.0], [19.0, 66.0], [0.0, 66.0]],
        "lajes": [{"laje": "L301", "side": "B", "content_type": "laje"}],
        "face_beams": {
            "A": {
                "passa_esq": None,
                "passa_dir": {"name": "V309A", "dim": "19/120", "corner": "AD", "behavior": "para"},
                "para": [{"name": "VF301", "dim": "19/66", "corner": "AC"}],
                "interior": [],
                "corner_esq": "AC",
                "corner_dir": "AD",
            },
            "B": {
                "passa_esq": {"name": "V309A", "dim": "19/120", "corner": "BD", "behavior": "para"},
                "passa_dir": None,
                "para": [{"name": "VF301", "dim": "19/66", "corner": "BC"}],
                "interior": [],
                "corner_esq": "BD",
                "corner_dir": "BC",
            },
            "C": {
                "passa_esq": {"name": "VF301", "dim": "19/66", "corner": "CA"},
                "passa_dir": {"name": "VF301", "dim": "19/66", "corner": "CB"},
                "para": [],
                "interior": [],
                "corner_esq": "CA",
                "corner_dir": "CB",
            },
            "D": {
                "passa_esq": None,
                "passa_dir": None,
                "para": [],
                "interior": [{"name": "V309A", "dim": "19/120"}],
                "corner_esq": "DA",
                "corner_dir": "DB",
            },
        },
    }
    payload = build_abcd_tables_from_pillar(
        pillar,
        slab_height_map={"L301": "12"},
        slab_nivel_map={"L301": "852.12"},
        slab_points_map={
            "L301": [[19, 0], [100, 0], [100, 52], [19, 52]],  # top y=52 → band 14
        },
        beams=[{"name": "VF301", "dim": "14/55"}],
        nivel_viga_default="852.19cm",
    )
    assert not any(
        r["nome"] == "VF301" and r["canto"] == "AC"
        for r in payload["faces"]["A"]["chega"]
        if r["nome"] != "nenhuma"
    )
    assert not any(
        r["nome"] == "VF301" and r["canto"] == "CA"
        for r in payload["faces"]["C"]["passa"]
        if r["nome"] != "nenhuma"
    )
    bc = next(r for r in payload["faces"]["B"]["chega"] if r["nome"] == "VF301")
    assert bc["canto"] == "BC"
    assert bc["dim"] == "14/55"


def test_interior_multi_passa_keeps_slot_cantos():
    """P10-like: interior em C/D + passa A/B com AC/AD/BC/BD — não virar AA/BB."""
    pillar = {
        "name": "P10",
        "orientation": "vertical",
        "points": [[0.0, 0.0], [19.0, 0.0], [19.0, 60.0], [0.0, 60.0]],
        "lajes": [{"laje": "L319", "side": "B", "content_type": "laje"}],
        "face_beams": {
            "A": {
                "passa_esq": {
                    "name": "V309A",
                    "dim": "19/120",
                    "corner": "AC",
                    "behavior": "para",
                },
                "passa_dir": {
                    "name": "V309",
                    "dim": "19/55",
                    "corner": "AD",
                    "behavior": "para",
                },
                "para": [],
                "interior": [],
                "corner_esq": "AC",
                "corner_dir": "AD",
            },
            "B": {
                "passa_esq": {
                    "name": "V309",
                    "dim": "19/55",
                    "corner": "BD",
                    "behavior": "para",
                },
                "passa_dir": {
                    "name": "V309A",
                    "dim": "19/120",
                    "corner": "BC",
                    "behavior": "para",
                },
                "para": [{"name": "V302", "dim": "19/55", "corner": "BC"}],
                "interior": [],
                "corner_esq": "BD",
                "corner_dir": "BC",
            },
            "C": {
                "passa_esq": None,
                "passa_dir": None,
                "para": [],
                "interior": [{"name": "V309A", "dim": "19/120"}],
                "corner_esq": "CA",
                "corner_dir": "CB",
            },
            "D": {
                "passa_esq": None,
                "passa_dir": None,
                "para": [],
                "interior": [{"name": "V309", "dim": "19/55"}],
                "corner_esq": "DA",
                "corner_dir": "DB",
            },
        },
    }
    payload = build_abcd_tables_from_pillar(
        pillar,
        slab_height_map={"L319": "14"},
        slab_nivel_map={"L319": "852"},
        slab_points_map={"L319": [[19, 0], [80, 0], [80, 41], [19, 41]]},
        nivel_viga_default="852cm",
    )
    a_pass = {r["nome"]: r["canto"] for r in payload["faces"]["A"]["passa"] if r["nome"] != "nenhuma"}
    b_pass = {r["nome"]: r["canto"] for r in payload["faces"]["B"]["passa"] if r["nome"] != "nenhuma"}
    assert a_pass.get("V309A") == "AC"
    assert a_pass.get("V309") == "AD"
    assert b_pass.get("V309A") == "BC"
    assert b_pass.get("V309") == "BD"
    # não inventar chega AC/BC da multi-passa interior
    assert not any(
        r["nome"] == "V309A" for r in payload["faces"]["A"]["chega"] if r["nome"] != "nenhuma"
    )


def test_c_passa_with_ca_cb_labels():
    pillar = {
        "name": "P2",
        "orientation": "vertical",
        "points": [[0, 0], [19, 0], [19, 66], [0, 66]],
        "lajes": [],
        "face_beams": {
            "A": {"passa_esq": None, "passa_dir": None, "para": [], "interior": [],
                  "corner_esq": "AC", "corner_dir": "AD"},
            "B": {"passa_esq": None, "passa_dir": None, "para": [], "interior": [],
                  "corner_esq": "BD", "corner_dir": "BC"},
            "C": {
                "passa_esq": {"name": "VF301", "dim": "14/55", "corner": "CA"},
                "passa_dir": {"name": "VF301", "dim": "19/66", "corner": "CB"},
                "para": [],
                "interior": [],
                "corner_esq": "CA",
                "corner_dir": "CB",
            },
            "D": {"passa_esq": None, "passa_dir": None, "para": [], "interior": [],
                  "corner_esq": "DA", "corner_dir": "DB"},
        },
    }
    payload = build_abcd_tables_from_pillar(pillar, nivel_viga_default="852.19cm")
    passa_c = [r for r in payload["faces"]["C"]["passa"] if r["nome"] != "nenhuma"]
    assert len(passa_c) == 2
    cantos = {r["canto"] for r in passa_c}
    assert "CA" in cantos and "CB" in cantos
    assert any(r["canto"] == "AC" for r in payload["faces"]["A"]["chega"])
    assert any(r["canto"] == "BC" for r in payload["faces"]["B"]["chega"])
    lines = lines_from_tables(payload)
    assert any("passa CA" in x for x in lines["C"]["passa"])
    assert any("passa CB" in x for x in lines["C"]["passa"])
