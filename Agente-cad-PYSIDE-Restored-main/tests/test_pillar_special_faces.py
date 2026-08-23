from src.core.pillar_special_faces import (
    classify_pillar_geometry,
    enrich_special_pillar_tables,
    physical_ring,
    special_l_face_segments,
)


POINTS = [
    [0, 0], [165, 0], [165, 19], [19, 19], [19, 218], [0, 218], [0, 0],
]


def _base_tables():
    return {
        "faces": {
            fid: {"label": fid, "lajes": [], "passa": [], "chega": [], "interior": []}
            for fid in "ABCD"
        },
        "orientation": "vertical",
    }


def test_l_shape_segments_are_physical_and_mirror_independent():
    segments = special_l_face_segments(POINTS)
    assert set(segments) == set("ABCDEF")
    assert round(segments["E"]["length"], 3) == 165.0
    assert round(segments["F"]["length"], 3) == 146.0
    assert round(segments["C"]["length"], 3) == 19.0


def test_special_faces_materialize_e_and_exclusive_f_pass():
    pillar = {
        "name": "PX",
        "points": POINTS,
        "sides_data": {
            "E": {
                "l1_n": "L9",
                "v_passa_esq_n": "VX",
                "v_passa_dir_n": "VX",
            },
            "D": {"v_ch1_n": "VY", "v_ch1_d": "14/50"},
        },
    }
    beams = [
        {"name": "VX", "dim": "19/55"},
        {"name": "VY", "dim": "14/50"},
    ]
    tables = enrich_special_pillar_tables(
        _base_tables(), pillar,
        slab_height_map={"L9": "12"}, slab_nivel_map={"L9": "852.19"},
        beams=beams, nivel_viga_default="852.19cm",
    )

    assert tables["face_ids"] == list("ABCDEF")
    assert tables["geometry_type"] == "L_special_6_faces"
    assert tables["faces"]["E"]["lajes"][0]["nome"] == "L9"
    assert len(tables["faces"]["E"]["passa"]) == 2
    assert [row["canto"] for row in tables["faces"]["F"]["passa"]] == ["FD"]
    assert len(tables["faces"]["E"]["chega"]) == 1
    assert tables["special_geometry_source"].startswith("SA/N1")


def test_rectangular_payload_remains_abcd():
    tables = enrich_special_pillar_tables(
        _base_tables(),
        {"points": [[0, 0], [19, 0], [19, 98], [0, 98], [0, 0]]},
    )
    assert tables["face_ids"] == list("ABCD")
    assert tables["geometry_type"] == "rectangular"


def test_collinear_vertices_do_not_create_extra_faces():
    # Vértice extra no meio de uma aresta não cria face nova.
    points = [[0, 0], [19, 0], [19, 50], [19, 98], [0, 98], [0, 0]]
    assert len(physical_ring(points)) == 4
    assert classify_pillar_geometry(points) == "rectangular"
    assert special_l_face_segments(points) == {}


def test_l_shape_classification_uses_physical_contour():
    assert classify_pillar_geometry(POINTS) == "L_special_6_faces"


def test_unknown_contour_is_not_disguised_as_rectangular():
    points = [[0, 0], [50, 0], [50, 30], [30, 30], [30, 60], [10, 60], [10, 30], [0, 30]]
    assert classify_pillar_geometry(points) == "poly_8_faces"


def _viga(nome, x0, y0, x1, y1, dim):
    return {
        "name": nome, "dim": dim,
        "geometry": {"classified": {"seg_bottom": [
            {"points": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]},
        ]}},
    }


# Braço horizontal de P26: E em y=2242 (x 3936..4101), F em y=2261 (x 3955..4101).
P26_POINTS = [
    [3936, 2242], [4101, 2242], [4101, 2261],
    [3955, 2261], [3955, 2460], [3936, 2460],
]


def test_face_e_vem_da_geometria_e_nao_do_sides_data():
    from src.core.pillar_special_faces import beams_running_along_edge

    segmentos = special_l_face_segments(P26_POINTS)
    # V305 corre na banda do braço: parede sobre E e sobre F.
    v305 = _viga("V305", 3955, 2242, 4533, 2261, "19/55")

    assert [row["name"] for row in beams_running_along_edge(segmentos["E"], [v305])] == ["V305"]
    assert [row["name"] for row in beams_running_along_edge(segmentos["F"], [v305])] == ["V305"]


def test_viga_com_corredor_inflado_nao_encosta_na_aresta():
    from src.core.pillar_special_faces import beams_running_along_edge

    segmentos = special_l_face_segments(P26_POINTS)
    # V323: seção 19/50 e corredor de 67 cm — bbox de trechos disjuntos.
    v323 = _viga("V323", 3888, 1963, 3955, 2242, "19/50")

    assert beams_running_along_edge(segmentos["E"], [v323]) == []


def test_viga_do_braco_sai_das_faces_longas_da_caixa():
    pillar = {"name": "P26", "points": P26_POINTS, "sides_data": {}}
    tables = {
        "faces": {
            "A": {"lajes": [], "passa": [
                {"familia": "viga", "nome": "V305", "canto": "AD", "papel": "passa"},
            ], "chega": [], "interior": []},
            "B": {"lajes": [], "passa": [], "chega": [], "interior": []},
            "C": {"lajes": [], "passa": [], "chega": [], "interior": []},
            "D": {"lajes": [], "passa": [], "chega": [], "interior": []},
        },
        "orientation": "vertical",
    }

    enriched = enrich_special_pillar_tables(
        tables, pillar, beams=[_viga("V305", 3955, 2242, 4533, 2261, "19/55")],
        nivel_viga_default="852.19cm",
    )

    assert enriched["faces"]["A"]["passa"] == []
    assert [row["nome"] for row in enriched["faces"]["E"]["passa"]] == ["V305", "V305"]
    assert [row["canto"] for row in enriched["faces"]["E"]["passa"]] == ["EA", "ED"]


def test_a_tampa_curta_d_nao_perde_a_viga_do_braco():
    pillar = {"name": "P26", "points": P26_POINTS, "sides_data": {}}
    tables = {
        "faces": {
            fid: {"lajes": [], "passa": [], "chega": [], "interior": []}
            for fid in "ABCD"
        },
        "orientation": "vertical",
    }
    tables["faces"]["D"]["interior"] = [
        {"familia": "viga", "nome": "V305", "canto": "DD", "papel": "interior"},
    ]

    enriched = enrich_special_pillar_tables(
        tables, pillar, beams=[_viga("V305", 3955, 2242, 4533, 2261, "19/55")],
        nivel_viga_default="852.19cm",
    )

    assert [row["nome"] for row in enriched["faces"]["D"]["interior"]] == ["V305"]


P27_L = [
    (4552.4, 2242.0), (4552.4, 2460.0), (4533.4, 2460.0),
    (4533.4, 2261.0), (4387.4, 2261.0), (4387.4, 2242.0),
]


def test_decomposicao_do_L_devolve_os_retangulos_reais():
    """A caixa envolvente do P27 cobre o vazio da dobra; o corpo real são
    duas peças — o pé e a perna."""
    from src.core.pillar_special_faces import rectangular_pieces

    assert rectangular_pieces(P27_L) == [
        (4387.4, 2242.0, 4533.4, 2261.0),   # pé
        (4533.4, 2242.0, 4552.4, 2460.0),   # perna
    ]


def test_decomposicao_de_retangular_devolve_ele_mesmo():
    from src.core.pillar_special_faces import rectangular_pieces

    assert rectangular_pieces(
        [(0.0, 0.0), (50.0, 0.0), (50.0, 19.0), (0.0, 19.0)]
    ) == [(0.0, 0.0, 50.0, 19.0)]


def test_geometria_de_face_do_L_cobre_as_seis_faces():
    """Sem E e F medidas, todo tier as ignorava — foi o que deixou `V329`
    nomeada nas faces do pé do `P27`, a 218 cm de distância."""
    from scripts.arete.qa_pil_approved_corpus import face_geometry

    geo = face_geometry({"points": P27_L})

    assert sorted(geo) == ["A", "B", "C", "D", "E", "F"]
    # C é o topo da perna: 19 cm de comprimento, em y=2460.
    assert geo["C"]["axis"] == "x"
    assert (geo["C"]["f0"], geo["C"]["f1"], geo["C"]["fixed"]) == (4533.4, 4552.4, 2460.0)
    # E é a base do pé; o corpo abaixo dela vai de 2242 a 2460 (pé + perna).
    assert geo["E"]["axis"] == "x"
    assert geo["E"]["fixed"] == 2242.0
    assert (geo["E"]["body_lo"], geo["E"]["body_hi"]) == (2242.0, 2460.0)


def test_geometria_de_face_do_retangular_nao_muda():
    from scripts.arete.qa_pil_approved_corpus import face_geometry

    geo = face_geometry({"points": [(0.0, 0.0), (19.0, 0.0), (19.0, 98.0), (0.0, 98.0)]})

    assert sorted(geo) == ["A", "B", "C", "D"]
    assert geo["A"]["axis"] == "y" and geo["A"]["fixed"] == 0.0
    assert geo["C"]["axis"] == "x" and geo["C"]["fixed"] == 98.0


def test_correr_ao_longo_da_aresta_exige_eixo_paralelo():
    """V323 é vertical e morre encostada no pé horizontal do P26.

    Ela tem parede na linha da aresta, mas não corre nela — virava passante
    das faces E e F.
    """
    from src.core.pillar_special_faces import (
        beams_running_along_edge, special_l_face_segments,
    )

    segs = special_l_face_segments(P26_L)
    vertical = {
        "name": "V323", "dim": "19/50",
        "geometry": {"classified": {"seg_bottom": [
            {"points": [(3936.4, 1982.0), (3936.4, 2242.0)]},
            {"points": [(3955.4, 1982.0), (3955.4, 2242.0)]},
        ]}},
    }
    horizontal = {
        "name": "V305", "dim": "19/55",
        "geometry": {"classified": {"seg_bottom": [
            {"points": [(3955.4, 2242.0), (4533.4, 2242.0)]},
            {"points": [(3955.4, 2261.0), (4533.4, 2261.0)]},
        ]}},
    }

    nomes = [r["name"] for r in beams_running_along_edge(segs["E"], [vertical, horizontal])]

    assert nomes == ["V305"]


P26_L = [
    (3936.4, 2242.0), (4101.4, 2242.0), (4101.4, 2261.0),
    (3955.4, 2261.0), (3955.4, 2460.0), (3936.4, 2460.0),
]
