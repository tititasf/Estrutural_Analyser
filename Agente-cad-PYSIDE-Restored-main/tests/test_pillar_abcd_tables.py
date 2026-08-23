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


def test_format_abcd_tables_html_includes_e_f_for_special_pillar():
    payload = {
        "face_ids": list("ABCDEF"),
        "faces": {
            face: {
                "label": f"Face {face}", "lajes": [], "passa": [],
                "chega": [], "interior": [],
            }
            for face in "ABCDEF"
        },
    }
    payload["faces"]["E"]["chega"] = [
        {"nome": "V327", "dim": "14/50", "canto": "ED"}
    ]
    payload["faces"]["F"]["passa"] = [
        {"nome": "V329", "dim": "19/60", "canto": "FD"}
    ]
    rendered = format_abcd_tables_html(payload)
    assert "Face E" in rendered and "V327" in rendered
    assert "Face F" in rendered and "V329" in rendered


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


def _top_dual_tables(source):
    """C com passante de topo + interior de outra viga nas faces longas."""
    def row(nome, canto, papel, src=None):
        r = {
            "familia": "viga", "nome": nome, "dim": "19/55", "nivel": "852.19",
            "canto": canto, "papel": papel, "raw": "",
            "dist_esq": "—", "dist_dir": "—",
        }
        if src:
            r["_source"] = src
        return r

    return {
        "A": {"lajes": [], "passa": [row("V318", "AC", "passa")],
              "chega": [row("V301", "AC", "chega", source)], "interior": []},
        "B": {"lajes": [], "passa": [row("V318", "BC", "passa")],
              "chega": [row("V301", "BC", "chega", source)], "interior": []},
        "C": {"lajes": [],
              "passa": [row("V301", "CA", "passa", source),
                        row("V301", "CB", "passa", source)],
              "chega": [], "interior": [row("V318", "CC", "interior")]},
        "D": {"lajes": [], "passa": [], "chega": [], "interior": []},
    }


def test_interior_em_c_nao_desfaz_dual_afirmado_pela_topologia():
    # P18/P43/P45/P47: o interior em C é a viga longitudinal, outra viga que
    # não invalida o passante de topo reconhecido por multi-segmento.
    from src.core.pillar_abcd_tables import apply_c_interior_suppress_top_dual

    tables = _top_dual_tables("face_c_top_multi_segment")
    notes = apply_c_interior_suppress_top_dual(tables)

    assert notes == []
    assert [r["nome"] for r in tables["C"]["passa"]] == ["V301", "V301"]
    assert [r["nome"] for r in tables["A"]["chega"]] == ["V301"]
    assert [r["nome"] for r in tables["B"]["chega"]] == ["V301"]


def test_interior_em_c_ainda_desfaz_dual_sem_proveniencia():
    # P10: sem evidência de topologia, o dual é preenchimento por default e a
    # supressão continua valendo.
    from src.core.pillar_abcd_tables import apply_c_interior_suppress_top_dual

    tables = _top_dual_tables(None)
    notes = apply_c_interior_suppress_top_dual(tables)

    assert notes
    assert tables["C"]["passa"] == []
    assert tables["A"]["chega"] == []
    assert [r["canto"] for r in tables["A"]["passa"]] == ["AC", "AC"]


def test_proveniencia_da_topologia_chega_na_linha_da_tabela():
    from src.core.pillar_abcd_tables import _beam_from_slot

    row = _beam_from_slot(
        {"name": "V301", "dim": "19/55", "corner": "CA",
         "source": "face_c_top_multi_segment"},
        papel="passa",
    )

    assert row["_source"] == "face_c_top_multi_segment"
    assert _beam_from_slot({"name": "V9"}, papel="passa").get("_source") is None


def test_laje_que_apenas_tangencia_a_face_nao_e_laje_da_face():
    # P43/P45/P47: a laje começa onde a face termina; o "contato" de 0,038 cm
    # é o resíduo da coordenada, não uma aresta compartilhada.
    from src.core.pillar_abcd_tables import prune_slabs_without_face_contact

    pillar_bb = (2040.3825, 2960.038, 2059.3825, 3010.038)
    tables = {
        "A": {"lajes": [
            {"familia": "laje", "nome": "L310", "canto": "AD", "papel": "laje"},
            {"familia": "laje", "nome": "L302", "canto": "AC", "papel": "laje"},
        ]},
        "B": {"lajes": []}, "C": {"lajes": []}, "D": {"lajes": []},
    }
    slab_points = {
        "L310": [[1622.5, 2680.0], [2040.3825, 2680.0], [2040.3825, 2991.0], [1622.5, 2991.0]],
        "L302": [[1622.4, 3010.0], [2040.3825, 3010.0], [2040.3825, 3193.0], [1622.4, 3193.0]],
    }

    notes = prune_slabs_without_face_contact(tables, pillar_bb, slab_points)

    assert [r["nome"] for r in tables["A"]["lajes"]] == ["L310"]
    assert notes and "L302" in notes[0]


def test_contato_curto_porem_real_e_preservado():
    # P33.C: 5 cm é o menor contato aceito por humano no 13_PAV.
    from src.core.pillar_abcd_tables import prune_slabs_without_face_contact

    pillar_bb = (0.0, 0.0, 100.0, 19.0)
    tables = {"A": {"lajes": [{"familia": "laje", "nome": "L1", "canto": "AA", "papel": "laje"}]},
              "B": {"lajes": []}, "C": {"lajes": []}, "D": {"lajes": []}}
    slab_points = {"L1": [[95.0, -50.0], [100.0, -50.0], [100.0, 0.0], [95.0, 0.0]]}

    prune_slabs_without_face_contact(
        tables, pillar_bb, slab_points, vertical=False,
    )

    assert [r["nome"] for r in tables["A"]["lajes"]] == ["L1"]


def test_sem_geometria_da_laje_nada_e_removido():
    from src.core.pillar_abcd_tables import prune_slabs_without_face_contact

    tables = {"A": {"lajes": [{"familia": "laje", "nome": "L9", "canto": "AA", "papel": "laje"}]},
              "B": {"lajes": []}, "C": {"lajes": []}, "D": {"lajes": []}}

    assert prune_slabs_without_face_contact(tables, (0.0, 0.0, 19.0, 98.0), {}) == []
    assert [r["nome"] for r in tables["A"]["lajes"]] == ["L9"]


def test_face_curta_mais_larga_que_a_viga_e_chegada():
    """R2 do dono: V313 (19) na face C de P29 (24) chega, não é interior."""
    from src.core.pillar_abcd_tables import _short_face_role

    p29 = [[2037.9, 1963.0], [2061.9, 1963.0], [2061.9, 2029.0], [2037.9, 2029.0]]

    assert _short_face_role("19/55", p29, vertical=True) == "chega"


def test_face_curta_do_tamanho_da_viga_e_interior():
    """P35: V308 (19) numa face de 19 fica dentro do corpo da viga."""
    from src.core.pillar_abcd_tables import _short_face_role

    p35 = [[100.0, 0.0], [160.0, 0.0], [160.0, 19.0], [100.0, 19.0]]

    assert _short_face_role("19/55", p35, vertical=False) == "interior"


def test_contorno_em_l_fica_fora_da_regra_da_largura():
    """Em L, a caixa envolvente devolve o braço inteiro, não a face curta.

    Quem trata E/F é `enrich_special_pillar_tables`, pelo contorno real.
    """
    from src.core.pillar_abcd_tables import _short_face_role

    em_l = [[3936, 2242], [4101, 2242], [4101, 2261],
            [3955, 2261], [3955, 2460], [3936, 2460]]

    assert _short_face_role("19/55", em_l, vertical=True) == "interior"


def test_chegada_no_meio_da_face_tem_folga_simetrica():
    """P29: face de 24, viga de 19 — sobram 2,5 de cada lado."""
    from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar

    pillar = {
        "name": "P29",
        "points": [[2037.9, 1963.0], [2061.9, 1963.0],
                   [2061.9, 2029.0], [2037.9, 2029.0]],
        "face_beams": {
            "C": {"passa_esq": None, "passa_dir": None, "interior": [],
                  "para": [{"name": "V313", "dim": "19/55", "corner": "CC"}]},
            "A": {"passa_esq": None, "passa_dir": None, "para": [], "interior": []},
            "B": {"passa_esq": None, "passa_dir": None, "para": [], "interior": []},
            "D": {"passa_esq": None, "passa_dir": None, "para": [], "interior": []},
        },
    }

    tables = build_abcd_tables_from_pillar(pillar, nivel_viga_default="852.19cm")
    linha = tables["faces"]["C"]["chega"][0]

    assert linha["nome"] == "V313"
    assert linha["canto"] == "CC"
    assert linha["dist_esq"] == "2.5cm" and linha["dist_dir"] == "2.5cm"


def test_canto_de_chegada_inverte_esq_dir_no_pilar_deitado():
    """P35/V328: face B de pilar deitado é parametrizada oeste→leste.

    No pilar em pé o canto esquerdo de B é `BD`; no deitado é `BC`. A tabela
    de chegada usava só a convenção do pilar em pé e trocava os lados.
    Medido no corpus: 5 casos verticais em `BD` dão `0/x`, e o caso deitado
    do `P35` dá `x/0` — mesma face, orientações opostas.
    """
    from src.core.pillar_abcd_tables import _chega_dists_from_corner

    pbb = (0.0, 0.0, 60.0, 19.0)  # deitado: face B tem 60 de comprimento
    assert _chega_dists_from_corner("B", "BD", 19.0, pbb, vertical=False) == (41.0, 0.0)
    assert _chega_dists_from_corner("B", "BC", 19.0, pbb, vertical=False) == (0.0, 41.0)

    pbb_v = (0.0, 0.0, 19.0, 60.0)  # em pé: BD é o canto esquerdo
    assert _chega_dists_from_corner("B", "BD", 19.0, pbb_v, vertical=True) == (0.0, 41.0)
    assert _chega_dists_from_corner("B", "BC", 19.0, pbb_v, vertical=True) == (41.0, 0.0)


def test_canto_de_chegada_desconhecido_nao_inventa_medida():
    from src.core.pillar_abcd_tables import _chega_dists_from_corner

    pbb = (0.0, 0.0, 19.0, 60.0)
    assert _chega_dists_from_corner("A", "BC", 19.0, pbb) == (None, None)
    assert _chega_dists_from_corner("A", "", 19.0, pbb) == (None, None)


def test_dualidade_nao_inventa_chegada_em_face_que_a_viga_nao_alcanca():
    """P24/V304 corre toda a leste: não chega na face oeste.

    A dualidade `C.passa@CA → A.chega@AC` era cega à posição da viga e criava
    uma chegada do outro lado do pilar.
    """
    from src.core.pillar_abcd_tables import apply_c_dualidade, _row

    pbb = (3788.4, 2380.0, 3807.4, 2460.0)
    viga_leste = [{
        "name": "V304", "dim": "19/50",
        "geometry": {"classified": {"seg_bottom": [
            {"points": [(3807.4, 2441.0), (4601.4, 2441.0)]},
            {"points": [(3807.4, 2460.0), (4601.4, 2460.0)]},
        ]}},
    }]
    tables = {
        fid: {"lajes": [], "passa": [], "chega": [], "interior": []}
        for fid in "ABCD"
    }
    tables["C"]["passa"].append(
        _row("viga", nome="V304", dim="19/50", canto="CA", papel="passa")
    )

    apply_c_dualidade(tables, pbb, viga_leste, vertical=True)

    assert tables["A"]["chega"] == []


def test_dualidade_cria_a_chegada_quando_a_viga_vem_de_fora():
    from src.core.pillar_abcd_tables import apply_c_dualidade, _row

    pbb = (1178.9, 2960.0, 1197.9, 3010.0)
    viga_leste = [{
        "name": "V301", "dim": "19/120",
        "geometry": {"classified": {"seg_bottom": [
            {"points": [(1197.9, 2991.0), (2461.9, 2991.0)]},
            {"points": [(1197.9, 3010.0), (2461.9, 3010.0)]},
        ]}},
    }]
    tables = {
        fid: {"lajes": [], "passa": [], "chega": [], "interior": []}
        for fid in "ABCD"
    }
    tables["C"]["passa"].append(
        _row("viga", nome="V301", dim="19/120", canto="CB", papel="passa")
    )

    apply_c_dualidade(tables, pbb, viga_leste, vertical=True)

    assert [r["canto"] for r in tables["B"]["chega"]] == ["BC"]


def test_dualidade_sem_geometria_continua_propagando():
    from src.core.pillar_abcd_tables import apply_c_dualidade, _row

    tables = {
        fid: {"lajes": [], "passa": [], "chega": [], "interior": []}
        for fid in "ABCD"
    }
    tables["C"]["passa"].append(
        _row("viga", nome="V9", dim="19/55", canto="CA", papel="passa")
    )

    apply_c_dualidade(tables)

    assert [r["canto"] for r in tables["A"]["chega"]] == ["AC"]


def test_chegada_na_esquina_convive_com_a_passagem_do_lado_c():
    """Regra do dono (2026-08-22): são as duas informações ao mesmo tempo.

    "Ela chega na face B, na esquina BC, e por estar chegando na esquina C
    simultaneamente para o lado C é viga passa."

    A supressão por interior em C desfazia o dual e apagava as duas.
    """
    from src.core.pillar_abcd_tables import (
        apply_c_interior_suppress_top_dual, _row,
    )

    pbb = (1178.9, 2960.0, 1197.9, 3010.0)
    vinda_de_fora = [{
        "name": "V301", "dim": "19/120",
        "geometry": {"classified": {"seg_bottom": [
            {"points": [(1197.9, 2991.0), (2461.9, 2991.0)]},
            {"points": [(1197.9, 3010.0), (2461.9, 3010.0)]},
        ]}},
    }]
    tables = {
        fid: {"lajes": [], "passa": [], "chega": [], "interior": []}
        for fid in "ABCD"
    }
    tables["B"]["chega"].append(
        _row("viga", nome="V301", dim="19/120", canto="BC", papel="chega")
    )
    tables["C"]["passa"].append(
        _row("viga", nome="V301", dim="19/120", canto="CB", papel="passa")
    )
    tables["C"]["interior"].append(
        _row("viga", nome="V309A", dim="19/120", canto="CC", papel="interior")
    )

    apply_c_interior_suppress_top_dual(tables, pbb, vinda_de_fora, vertical=True)

    assert [r["nome"] for r in tables["B"]["chega"]] == ["V301"]
    assert [r["canto"] for r in tables["C"]["passa"]] == ["CB"]


def test_dual_sem_chegada_real_continua_sendo_desfeito():
    # Viga que não vem de fora não chega: o dual era propagação, e cai.
    from src.core.pillar_abcd_tables import (
        apply_c_interior_suppress_top_dual, _row,
    )

    pbb = (1178.9, 2960.0, 1197.9, 3010.0)
    dentro = [{
        "name": "VX", "dim": "19/120",
        "geometry": {"classified": {"seg_bottom": [
            {"points": [(1180.0, 2991.0), (1196.0, 2991.0)]},
            {"points": [(1180.0, 3010.0), (1196.0, 3010.0)]},
        ]}},
    }]
    tables = {
        fid: {"lajes": [], "passa": [], "chega": [], "interior": []}
        for fid in "ABCD"
    }
    tables["B"]["chega"].append(
        _row("viga", nome="VX", dim="19/120", canto="BC", papel="chega")
    )
    tables["C"]["passa"].append(
        _row("viga", nome="VX", dim="19/120", canto="CB", papel="passa")
    )
    tables["C"]["interior"].append(
        _row("viga", nome="VY", dim="19/120", canto="CC", papel="interior")
    )

    apply_c_interior_suppress_top_dual(tables, pbb, dentro, vertical=True)

    assert tables["B"]["chega"] == []
    assert [r for r in tables["C"]["passa"]] == []


def test_chegada_na_face_longa_exige_vir_de_fora():
    """V301 entra pela face A do P49 e morre rente à B: lá ela não chega."""
    from src.core.pillar_abcd_tables import _beam_comes_from_outside

    pbb = (4533.4, 2960.0, 4552.4, 3010.0)
    v301 = [{
        "name": "V301", "dim": "19/120",
        "geometry": {"classified": {"seg_bottom": [
            {"points": [(4259.9, 2991.0), (4552.4, 2991.0)]},
            {"points": [(4259.9, 3010.0), (4552.4, 3010.0)]},
        ]}},
    }]

    assert _beam_comes_from_outside("V301", "A", pbb, v301, vertical=True)
    assert not _beam_comes_from_outside("V301", "B", pbb, v301, vertical=True)


def test_faixa_embutida_na_ponta_inicial_e_reconhecida_com_assinatura():
    """A assinatura é largura transversal + ponta, não a altura: é o que
    compara P28 (24x80) com P29 (24x66)."""
    from src.core.pillar_abcd_tables import beams_embedded_at_start

    def _viga(nome, y0, y1):
        return {
            "name": nome, "dim": "14/55",
            "geometry": {"classified": {"seg_bottom": [
                {"points": [(1400.0, y0), (3800.0, y0)]},
                {"points": [(1400.0, y1), (3800.0, y1)]},
            ]}},
        }

    p28 = (1600.9, 1963.0, 1624.9, 2043.0)
    p29 = (2037.9, 1963.0, 2061.9, 2029.0)
    vf203 = [_viga("VF203", 1963.0, 1977.0)]
    quad28 = [(1600.9, 1963.0), (1624.9, 1963.0), (1624.9, 2043.0), (1600.9, 2043.0)]
    quad29 = [(2037.9, 1963.0), (2061.9, 1963.0), (2061.9, 2029.0), (2037.9, 2029.0)]

    a = beams_embedded_at_start(p28, vf203, quad28)
    b = beams_embedded_at_start(p29, vf203, quad29)

    assert a == b == {"VF203": [24, True, "inicio"]}


def test_faixa_embutida_na_ponta_final_nao_entra_na_regra():
    from src.core.pillar_abcd_tables import beams_embedded_at_start

    p20 = (2040.4, 2423.0, 2059.4, 2509.0)
    quad = [(2040.4, 2423.0), (2059.4, 2423.0), (2059.4, 2509.0), (2040.4, 2509.0)]
    v303 = [{
        "name": "V303", "dim": "19/55",
        "geometry": {"classified": {"seg_bottom": [
            {"points": [(1652.9, 2490.0), (3807.4, 2490.0)]},
            {"points": [(1652.9, 2509.0), (3807.4, 2509.0)]},
        ]}},
    }]

    assert beams_embedded_at_start(p20, v303, quad) == {}


def test_vem_de_fora_usa_o_corredor_recuperado_e_nao_a_caixa_do_tracador():
    """VF301: a caixa do traçador é o retângulo do rótulo, 100×24 junto ao
    P1; o corredor medido vai de P1 a P9. Medir na caixa dizia que ela não
    vinha de fora da face leste do P2."""
    from src.core.pillar_abcd_tables import _beam_comes_from_outside

    p2 = (1603.4, 3141.0, 1622.4, 3207.0)
    viga = [{
        "name": "VF301", "dim": "14/55",
        "_recovered_corridor": (1197.9, 3193.0, 4649.9, 3207.0),
        "geometry": {"classified": {"seg_bottom": [
            {"points": [(1159.8, 3198.8), (1259.8, 3198.8)]},
            {"points": [(1159.8, 3222.8), (1259.8, 3222.8)]},
        ]}},
    }]

    assert _beam_comes_from_outside("VF301", "A", p2, viga, vertical=True)
    assert _beam_comes_from_outside("VF301", "B", p2, viga, vertical=True)
