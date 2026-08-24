from scripts.arete.qa_pil_approved_corpus import (
    _rows_semantically_equal,
    compare_semantics,
    highest_approved_layer,
)


def _row(**overrides):
    row = {
        "familia": "viga", "nome": "V1", "dim": "19/55",
        "nivel_cm": "", "canto": "AA", "papel": "chega",
        "dist_esq_cm": "", "dist_dir_cm": "",
    }
    row.update(overrides)
    return row


def test_omitted_measurement_is_unknown_not_empty_assertion():
    assert _rows_semantically_equal(
        [_row()],
        [_row(nivel_cm="852.19", dist_esq_cm="28", dist_dir_cm="28")],
    )


def test_present_measurement_and_identity_remain_strict():
    assert not _rows_semantically_equal(
        [_row(dist_esq_cm="0")], [_row(dist_esq_cm="10")],
    )
    assert not _rows_semantically_equal(
        [_row()], [_row(canto="AC")],
    )
    assert not _rows_semantically_equal(
        [_row()], [_row(), _row(nome="V2")],
    )


def test_blank_geometry_type_is_unknown_not_expected_empty_value():
    expected = {
        "orientation": "vertical", "geometry_type": "", "face_ids": ["A"],
        "faces": {},
    }
    actual = {
        "orientation": "vertical", "geometry_type": "rectangle",
        "face_ids": ["A"], "faces": {},
    }

    assert compare_semantics(expected, actual)["status"] == "PASS"


def test_beam_dimension_copied_from_pillar_section_is_not_confirmatory():
    expected = {
        "orientation": "vertical", "geometry_type": "", "face_ids": ["A"],
        "geometry_points": [],
        "faces": {"A": {"lajes": [], "passa": [], "interior": [], "chega": [
            _row(nome="V1", canto="AC", dim="19/66", dist_esq_cm="19"),
        ]}},
    }
    actual = {
        "orientation": "vertical", "geometry_type": "rectangle", "face_ids": ["A"],
        "geometry_points": [[0, 0], [19, 0], [19, 66], [0, 66], [0, 0]],
        "faces": {"A": {"lajes": [], "passa": [], "interior": [], "chega": [
            _row(nome="V1", canto="AC", dim="14/55", dist_esq_cm="0"),
        ]}},
    }

    result = compare_semantics(expected, actual)

    assert result["status"] == "PASS"
    assert result["authority_exclusions"][0]["tier"] == "T0_UNPROVEN"


def test_prior_human_approval_remains_eligible_after_later_invalid_attempt():
    item_doc = {
        "history": {
            "_hl_l1_human_verdict": "validou",
            "_hl_l2_human_verdict": "invalidou",
        },
    }

    approved_layer, verdicts = highest_approved_layer(item_doc)

    assert approved_layer == "L1"
    assert verdicts == {"L1": "validou", "L2": "invalidou"}


def _slab_payload(level: str):
    return {
        "orientation": "vertical", "geometry_type": "rectangular",
        "face_ids": ["A"], "geometry_points": [],
        "faces": {"A": {
            "lajes": [{
                "familia": "laje", "nome": "L1", "dim": "12", "nivel_cm": level,
                "canto": "AA", "papel": "laje", "dist_esq_cm": "0", "dist_dir_cm": "0",
            }],
            "passa": [], "chega": [], "interior": [],
        }},
    }


def test_slab_level_outside_pavement_vocabulary_is_tiered_not_counted():
    result = compare_semantics(
        _slab_payload("859.12"), _slab_payload("852.19"),
        slab_levels={"852.12", "852.19"},
    )

    assert result["status"] == "PASS"
    exclusion = result["authority_exclusions"][0]
    assert exclusion["tier"] == "T0_UNDERIVABLE"
    assert exclusion["identity"] == "L1"
    assert exclusion["value"] == "859.12"


def test_slab_level_inside_vocabulary_stays_in_the_gate():
    result = compare_semantics(
        _slab_payload("852.19"), _slab_payload("852.16"),
        slab_levels={"852.12", "852.16", "852.19"},
    )

    assert result["status"] == "FAIL"
    assert not result["authority_exclusions"]


def test_slab_level_vocabulary_comes_from_the_whole_pavement():
    from scripts.arete.qa_pil_approved_corpus import slab_level_vocabulary

    assert slab_level_vocabulary(
        [_slab_payload("852.19"), _slab_payload("852.12")],
    ) == {"852.19", "852.12"}


def _slab_payload_with_provenance(level, provenance=None):
    payload = _slab_payload(level)
    if provenance:
        payload["slab_level_provenance"] = {"L1": provenance}
    return payload


def test_anotacao_contida_no_contorno_vence_o_nivel_do_corpus():
    # Decisão de 2026-08-19: L312/L316/L322 contêm a própria anotação; é o
    # corpus que envelheceu, não o motor que errou.
    result = compare_semantics(
        _slab_payload("852.19"),
        _slab_payload_with_provenance("852.16", "contida"),
        slab_levels={"852.12", "852.16", "852.19"},
    )

    assert result["status"] == "PASS"
    exclusion = result["authority_exclusions"][0]
    assert exclusion["tier"] == "T0_SUPERSEDED_BY_CONTAINED_ANNOTATION"
    assert exclusion["identity"] == "L1"
    assert exclusion["actual"] == "852.16"


def test_nivel_por_proximidade_nao_vence_o_corpus():
    result = compare_semantics(
        _slab_payload("852.19"),
        _slab_payload_with_provenance("852.16", "proximidade"),
        slab_levels={"852.12", "852.16", "852.19"},
    )

    assert result["status"] == "FAIL"
    assert not result["authority_exclusions"]


def test_nivel_sem_evidencia_local_nao_vence_o_corpus():
    result = compare_semantics(
        _slab_payload("852.19"),
        _slab_payload_with_provenance("852.12", "sem_evidencia_local"),
        slab_levels={"852.12", "852.16", "852.19"},
    )

    assert result["status"] == "FAIL"


def test_deferencia_nao_apaga_divergencia_de_canto_ou_nome():
    actual = _slab_payload_with_provenance("852.16", "contida")
    actual["faces"]["A"]["lajes"][0]["canto"] = "AC"

    result = compare_semantics(
        _slab_payload("852.19"), actual,
        slab_levels={"852.12", "852.16", "852.19"},
    )

    assert result["status"] == "FAIL"


def _reach_payload(nome, face="A", role="chega", reach=None):
    payload = {
        "orientation": "vertical", "geometry_type": "rectangular",
        "face_ids": ["A"], "geometry_points": [],
        "faces": {"A": {"lajes": [], "passa": [], "chega": [], "interior": []}},
    }
    payload["faces"][face][role] = [{
        "familia": "viga", "nome": nome, "dim": "19/55", "nivel_cm": "",
        "canto": "AC", "papel": role, "dist_esq_cm": "", "dist_dir_cm": "",
    }]
    if reach is not None:
        payload["face_beam_reach"] = {"A": reach}
    return payload


def test_viga_longe_da_face_sai_do_gate():
    # P9: o corpus nomeia VF301 numa face a 3390 cm do corredor dela.
    esperado = _reach_payload("VF301")
    motor = _reach_payload("X", reach=["X"])
    motor["faces"]["A"]["chega"] = []

    result = compare_semantics(esperado, motor)

    assert result["status"] == "PASS"
    assert result["authority_exclusions"][0]["tier"] == "T0_OUT_OF_REACH"
    assert result["authority_exclusions"][0]["identity"] == "VF301"


def test_viga_que_o_motor_poe_na_face_continua_no_gate():
    # Se o motor colocou a viga ali, a divergência é de papel ou canto — não
    # de impossibilidade, e o tier não pode encobrir isso.
    esperado = _reach_payload("V1", role="chega")
    motor = _reach_payload("V1", role="passa", reach=[])

    result = compare_semantics(esperado, motor)

    assert result["status"] == "FAIL"
    assert not any(
        e["tier"] == "T0_OUT_OF_REACH" for e in result["authority_exclusions"]
    )


def test_sem_medicao_de_alcance_nada_e_tierado():
    result = compare_semantics(_reach_payload("V1"), _reach_payload("X"))

    assert not any(
        e["tier"] == "T0_OUT_OF_REACH" for e in result["authority_exclusions"]
    )


def _semantic(faces, **extra):
    payload = {
        "orientation": "vertical",
        "geometry_type": "",
        "face_ids": sorted(faces),
        "faces": {
            fid: {role: list(bucket.get(role) or [])
                  for role in ("lajes", "passa", "chega", "interior")}
            for fid, bucket in faces.items()
        },
    }
    payload.update(extra)
    return payload


def test_chegada_sem_ocupacao_da_face_sai_do_gate():
    """P12/V314: a viga morre na face curta e ocupa ZERO da face longa.

    Precedente medido no `P20` (verde): a viga que morre numa face aparece
    como `passa` nas vizinhas, nunca como `chega`.
    """
    expected = _semantic({"A": {"chega": [_row(nome="V314", canto="AC")]}})
    actual = _semantic(
        {"A": {"chega": [_row(nome="V302", canto="AD")]}},
        face_beam_span_overlap={"A": ["V302"]},
    )

    result = compare_semantics(expected, actual)

    tiers = [e["tier"] for e in result["authority_exclusions"]]
    assert "T0_NO_FACE_OCCUPANCY" in tiers
    # A célula inteira fica sem julgamento: o corpus dela foi rebaixado.
    assert result["differences"] == []


def test_chegada_que_ocupa_a_face_continua_no_gate():
    expected = _semantic({"A": {"chega": [_row(nome="V313", canto="AC")]}})
    actual = _semantic(
        {"A": {"chega": [_row(nome="V306", canto="AC")]}},
        face_beam_span_overlap={"A": ["V313", "V306"]},
    )

    result = compare_semantics(expected, actual)

    assert result["authority_exclusions"] == []
    assert [d["field"] for d in result["differences"]] == ["faces.A.chega"]


def test_face_sem_medicao_de_ocupacao_nao_e_rebaixada():
    # Faces E/F dos especiais não entram no critério.
    expected = _semantic({"E": {"chega": [_row(nome="V9", canto="EA")]}})
    actual = _semantic({"E": {"chega": []}}, face_beam_span_overlap={"A": ["V1"]})

    result = compare_semantics(expected, actual)

    assert [e["tier"] for e in result["authority_exclusions"]] == []


def test_alcance_que_esvazia_a_celula_tira_o_julgamento_dela():
    expected = _semantic({"D": {"passa": [_row(nome="V314", canto="DA", papel="passa")]}})
    actual = _semantic(
        {"D": {"passa": [_row(nome="V302", canto="DA", papel="passa")]}},
        face_beam_reach={"D": ["V302"]},
    )

    result = compare_semantics(expected, actual)

    assert [e["tier"] for e in result["authority_exclusions"]] == ["T0_OUT_OF_REACH"]
    assert result["differences"] == []


def test_secao_de_viga_que_copia_pilar_cai_no_corpus_inteiro():
    """V318 sai `19/98` (a seção de P14) em P5 e P45, e `19/120` no P14."""
    from scripts.arete.qa_pil_approved_corpus import _collect_unproven_beam_dims

    corpus = {"items": [
        {"item": "P14", "semantic": _semantic({
            "B": {"passa": [_row(nome="V318", dim="19/98", papel="passa")]},
            "C": {"passa": [_row(nome="V318", dim="19/120", papel="passa")]},
        })},
        {"item": "P5", "semantic": _semantic({
            "A": {"passa": [_row(nome="V318", dim="19/98", papel="passa")]},
        })},
    ]}
    parsed = {
        "P14": {"geometry_points": [(0, 0), (19, 0), (19, 98), (0, 98)]},
        "P5": {"geometry_points": [(0, 0), (50, 0), (50, 19), (0, 19)]},
    }

    assert _collect_unproven_beam_dims(corpus, parsed) == {("V318", "19/98")}


def test_secao_consistente_no_corpus_nao_e_rebaixada():
    from scripts.arete.qa_pil_approved_corpus import _collect_unproven_beam_dims

    corpus = {"items": [
        {"item": "P14", "semantic": _semantic({
            "B": {"passa": [_row(nome="V9", dim="19/98", papel="passa")]},
        })},
    ]}
    parsed = {"P14": {"geometry_points": [(0, 0), (19, 0), (19, 98), (0, 98)]}}

    assert _collect_unproven_beam_dims(corpus, parsed) == set()


def test_distancia_compara_como_numero_nao_como_texto():
    from scripts.arete.qa_pil_approved_corpus import _clean_distance

    assert _clean_distance("66.0") == _clean_distance("66") == "66"
    assert _clean_distance("2,50") == "2.5"
    assert _clean_distance("") == ""
    assert _clean_distance("—") == ""


def test_passa_de_viga_que_morre_encostada_na_face_sai_do_gate():
    """P12/V314 desce do norte e para no topo — não atravessa nada.

    Precedente medido: `P20` (verde) registra a gêmea `V313`, que morre na
    face D dele, como `interior` — nunca como `passa`.
    """
    expected = _semantic({"C": {"passa": [_row(nome="V314", canto="CA", papel="passa")]}})
    actual = _semantic(
        {"C": {"interior": [_row(nome="V314", canto="CC", papel="interior")]}},
        face_beam_crosses={"C": []},
    )

    result = compare_semantics(expected, actual)

    assert [e["tier"] for e in result["authority_exclusions"]] == [
        "T0_NO_PASSAGE_THROUGH_FACE"
    ]
    # O papel da mesma viga na mesma face fica sem julgamento.
    assert result["differences"] == []


def test_passa_de_viga_que_atravessa_continua_no_gate():
    expected = _semantic({"C": {"passa": [_row(nome="V303", canto="CA", papel="passa")]}})
    actual = _semantic({"C": {"passa": []}}, face_beam_crosses={"C": ["V303"]})

    result = compare_semantics(expected, actual)

    assert result["authority_exclusions"] == []
    assert [d["field"] for d in result["differences"]] == ["faces.C.passa"]


def test_papel_registrado_pelo_corpus_na_mesma_face_continua_julgado():
    # Se o corpus registrou a viga em outro papel ali, existe prova: o motor
    # continua sendo cobrado por ela.
    expected = _semantic({"C": {
        "passa": [_row(nome="V314", canto="CA", papel="passa")],
        "interior": [_row(nome="V314", canto="CC", papel="interior")],
    }})
    actual = _semantic({"C": {"interior": []}}, face_beam_crosses={"C": []})

    result = compare_semantics(expected, actual)

    assert [d["field"] for d in result["differences"]] == ["faces.C.interior"]


def _laje(**overrides):
    row = {
        "familia": "laje", "nome": "L310", "dim": "12", "nivel_cm": "852.19",
        "canto": "AA", "papel": "laje", "dist_esq_cm": "0", "dist_dir_cm": "0",
    }
    row.update(overrides)
    return row


def test_contato_de_laje_que_o_poligono_desmente_sai_do_gate():
    """P12/L310: o corpus diz face cheia; a laje para 19 cm antes, na viga."""
    expected = _semantic({"A": {"lajes": [_laje()]}})
    actual = _semantic(
        {"A": {"lajes": [_laje(canto="AC", dist_dir_cm="19")]}},
        face_slab_contact={"A": {"L310": [0.0, 18.96]}},
    )

    result = compare_semantics(expected, actual)

    assert [e["tier"] for e in result["authority_exclusions"]] == [
        "T0_CONTRADICTED_BY_SLAB_POLYGON"
    ]
    assert result["differences"] == []


def test_contato_de_laje_que_o_poligono_confirma_continua_no_gate():
    expected = _semantic({"A": {"lajes": [_laje()]}})
    actual = _semantic(
        {"A": {"lajes": [_laje(canto="AC")]}},
        face_slab_contact={"A": {"L310": [0.0, 0.0]}},
    )

    result = compare_semantics(expected, actual)

    assert result["authority_exclusions"] == []
    assert [d["field"] for d in result["differences"]] == ["faces.A.lajes"]


def test_laje_sem_medida_no_corpus_nao_e_rebaixada():
    expected = _semantic({"A": {"lajes": [_laje(dist_esq_cm="", dist_dir_cm="")]}})
    actual = _semantic(
        {"A": {"lajes": [_laje(dist_dir_cm="19")]}},
        face_slab_contact={"A": {"L310": [0.0, 18.96]}},
    )

    result = compare_semantics(expected, actual)

    assert result["authority_exclusions"] == []


def test_canto_longe_do_corredor_sai_do_gate():
    """P24/V321 morre na face D: encosta na face A, mas o canto `AC` fica a
    80 cm dela. O `P20` (verde) registra a gêmea só em `AD`."""
    expected = _semantic({"A": {"passa": [
        _row(nome="V321", canto="AC", papel="passa"),
        _row(nome="V321", canto="AD", papel="passa"),
    ]}})
    actual = _semantic(
        {"A": {"passa": [_row(nome="V321", canto="AD", papel="passa")]}},
        face_corner_reach={"AC": [], "AD": ["V321"]},
    )

    result = compare_semantics(expected, actual)

    assert [e["tier"] for e in result["authority_exclusions"]] == [
        "T0_CORNER_OUT_OF_REACH"
    ]
    assert result["differences"] == []


def test_canto_onde_o_motor_poe_a_mesma_viga_continua_no_gate():
    # Mesmo canto nos dois lados: a discussão é de papel ou medida.
    expected = _semantic({"A": {"passa": [_row(nome="V321", canto="AC", papel="passa")]}})
    actual = _semantic(
        {"A": {"chega": [_row(nome="V321", canto="AC", papel="chega")]}},
        face_corner_reach={"AC": []},
    )

    result = compare_semantics(expected, actual)

    assert result["authority_exclusions"] == []


def test_canto_sem_medicao_nao_rebaixa():
    expected = _semantic({"E": {"passa": [_row(nome="V9", canto="EB", papel="passa")]}})
    actual = _semantic({"E": {"passa": []}}, face_corner_reach={"AC": ["V1"]})

    result = compare_semantics(expected, actual)

    assert result["authority_exclusions"] == []


def test_tier_de_viga_embutida_omitida_so_liga_com_o_corpus_a_favor():
    """O tier se calibra sozinho: só vale onde o corpus demonstra registrar a
    viga embutida no resto do pavimento. No 13_PAV a taxa é 0,77 e ele fica
    desligado — as sobras restantes são do motor mesmo."""
    from scripts.arete.qa_pil_approved_corpus import (
        _exclude_embedded_beam_omitted_by_corpus, embedded_beam_naming_rate,
    )

    expected = _semantic({"A": {"passa": []}})
    actual = _semantic(
        {"A": {"chega": [_row(nome="V302", canto="AD", papel="chega")]}},
        embedded_beams=["V302"],
    )

    desligado, sem = _exclude_embedded_beam_omitted_by_corpus(
        expected, actual, enabled=False,
    )
    assert sem == []
    assert desligado["faces"]["A"]["chega"]

    ligado, com = _exclude_embedded_beam_omitted_by_corpus(
        expected, actual, enabled=True,
    )
    assert [e["tier"] for e in com] == ["T0_EMBEDDED_BEAM_OMITTED"]
    assert ligado["faces"]["A"]["chega"] == []

    corpus = {"items": [
        {"item": "P20", "semantic": _semantic(
            {"A": {"passa": [_row(nome="V303", papel="passa")]}})},
        {"item": "P12", "semantic": _semantic({"A": {"passa": []}})},
    ]}
    parsed = {
        "P20": {"embedded_beams": ["V303"]},
        "P12": {"embedded_beams": ["V302"]},
    }
    taxa, total = embedded_beam_naming_rate(corpus, parsed)
    assert (round(taxa, 2), total) == (0.5, 2)


def test_travessia_inexistente_na_tampa_curta_sai_do_gate():
    """`V314` desce do norte e para no topo do `P12`: não atravessa a tampa.

    O critério vale **só nas faces curtas**. Na longa, `passa` é como o
    corpus registra a viga que corre na prumada do pilar, atravessando ou
    morrendo nele.
    """
    expected = _semantic({"C": {"passa": [_row(nome="V314", canto="CA", papel="passa")]}})
    actual = _semantic(
        {"C": {"passa": []}},
        face_beam_crosses={"C": []},
        face_geometry_span={"A": 98.0, "B": 98.0, "C": 19.0, "D": 19.0},
    )

    result = compare_semantics(expected, actual)

    assert [e["tier"] for e in result["authority_exclusions"]] == [
        "T0_NO_PASSAGE_THROUGH_FACE"
    ]
    assert result["differences"] == []


def test_passa_em_face_longa_de_viga_que_morre_continua_no_gate():
    """`P1`, `P10` e `P15` (verdes) listam a viga que morre encostada como
    `passa` na face longa. O critério de travessia não vale ali."""
    expected = _semantic({"B": {"passa": [_row(nome="V309A", canto="BC", papel="passa")]}})
    actual = _semantic(
        {"B": {"passa": []}},
        face_beam_crosses={"B": []},
        face_geometry_span={"A": 60.0, "B": 60.0, "C": 19.0, "D": 19.0},
    )

    result = compare_semantics(expected, actual)

    assert [e["tier"] for e in result["authority_exclusions"]] == []
    assert [d["field"] for d in result["differences"]] == ["faces.B.passa"]


def test_interior_com_folga_dos_dois_lados_sai_do_gate():
    """Regra do dono (2026-08-22): interior é a face inteira dentro da viga.

    Folga dos dois lados nega a cobertura total. Das 46 linhas de interior do
    corpus, só `V312` no `P2` tem folga dos dois — e a medição diz que ali a
    viga cobre a face inteira.
    """
    expected = _semantic({"D": {"interior": [
        _row(nome="V312", canto="DD", papel="interior",
             dist_esq_cm="3", dist_dir_cm="3"),
    ]}})
    actual = _semantic(
        {"D": {"interior": [
            _row(nome="V312", canto="DD", papel="interior",
                 dist_esq_cm="0", dist_dir_cm="0"),
        ]}},
        face_beam_covering={"D": ["V312"]},
    )

    result = compare_semantics(expected, actual)

    assert [e["tier"] for e in result["authority_exclusions"]] == [
        "T0_INTERIOR_WITH_GAP_BOTH_SIDES"
    ]
    assert result["differences"] == []


def test_interior_com_folga_de_um_lado_so_continua_no_gate():
    # `7/0` é o padrão do corpus em sete itens verdes: não é folga dos dois.
    expected = _semantic({"D": {"interior": [
        _row(nome="V309", canto="DD", papel="interior",
             dist_esq_cm="7", dist_dir_cm="0"),
    ]}})
    actual = _semantic(
        {"D": {"interior": [
            _row(nome="V309", canto="DD", papel="interior",
                 dist_esq_cm="0", dist_dir_cm="0"),
        ]}},
        face_beam_covering={"D": ["V309"]},
    )

    result = compare_semantics(expected, actual)

    assert result["authority_exclusions"] == []
    assert [d["field"] for d in result["differences"]] == ["faces.D.interior"]


def test_registro_minoritario_de_faixa_embutida_sai_do_gate():
    """P28 registra a mesma VF203 que P29–P32, verdes, omitem."""
    from scripts.arete.qa_pil_approved_corpus import (
        _collect_minority_embedded_registrations,
    )

    assinatura = [24, True, "inicio"]
    corpus = {"items": [
        {"item": "P28", "semantic": _semantic({
            "A": {"chega": [_row(nome="VF203", canto="AD")]}})},
        {"item": "P29", "semantic": _semantic({"A": {"chega": []}})},
        {"item": "P30", "semantic": _semantic({"A": {"chega": []}})},
        {"item": "P31", "semantic": _semantic({"A": {"chega": []}})},
    ]}
    parsed = {
        pid: {"embedded_at_start": {"VF203": assinatura}}
        for pid in ("P28", "P29", "P30", "P31")
    }

    assert _collect_minority_embedded_registrations(corpus, parsed) == {
        ("P28", "VF203")
    }


def test_maioria_que_registra_nao_e_rebaixada():
    from scripts.arete.qa_pil_approved_corpus import (
        _collect_minority_embedded_registrations,
    )

    assinatura = [19, True, "inicio"]
    corpus = {"items": [
        {"item": f"P{n}", "semantic": _semantic({
            "A": {"chega": [_row(nome="V302", canto="AD")]}})}
        for n in (20, 21, 22)
    ]}
    parsed = {
        f"P{n}": {"embedded_at_start": {"V302": assinatura}}
        for n in (20, 21, 22)
    }

    assert _collect_minority_embedded_registrations(corpus, parsed) == set()


def test_interior_de_viga_paralela_que_nao_contem_a_face_sai_do_gate():
    """P48: o corpus nomeia V325 na face C, e ela passa 15 cm ao lado.

    `interior` nomeia ou a viga perpendicular à face (o caso axial) ou a que
    contém a face. Paralela que passa ao lado não é nem uma nem outra.
    """
    expected = _semantic({"C": {"interior": [
        _row(nome="V325", canto="CC", papel="interior"),
    ]}})
    actual = _semantic(
        {"C": {"interior": [_row(nome="V301", canto="CC", papel="interior")]}},
        beam_axis_horizontal={"V325": False, "V301": True},
        face_axis_horizontal={"C": False},
        face_beam_containing={"C": ["V301"]},
    )

    result = compare_semantics(expected, actual)

    assert [e["tier"] for e in result["authority_exclusions"]] == [
        "T0_INTERIOR_PARALLEL_NOT_CONTAINING"
    ]
    assert result["differences"] == []


def test_interior_axial_perpendicular_continua_no_gate():
    # P23/V319: a viga corre na prumada do pilar e morre antes da face — é
    # perpendicular a ela, e o corpus a registra como interior.
    expected = _semantic({"C": {"interior": [
        _row(nome="V319", canto="CC", papel="interior"),
    ]}})
    actual = _semantic(
        {"C": {"interior": []}},
        beam_axis_horizontal={"V319": False},
        face_axis_horizontal={"C": True},
        face_beam_containing={"C": []},
    )

    result = compare_semantics(expected, actual)

    assert result["authority_exclusions"] == []
    assert [d["field"] for d in result["differences"]] == ["faces.C.interior"]


def test_viga_do_braco_em_ambas_e_f_sai_do_gate_no_pilar_espelhado():
    """V305×P27 (2026-08-24): viga contínua sob o braço de P26 E P27.

    O corpus de 19/08 só nomeou V305 no P26; o motor a registra em ambas
    as faces longas do braço (E e F) de P27 também — decisão do dono via
    ficha de dúvida (opção A: registra nos dois pilares mesmo)."""
    expected = _semantic({
        "E": {"passa": [_row(nome="V329", canto="EB")]},
        "F": {"passa": [_row(nome="V329", canto="FD")]},
    })
    actual = _semantic({
        "E": {"passa": [
            _row(nome="V329", canto="EB"),
            _row(nome="V305", canto="EB"),
        ]},
        "F": {"passa": [
            _row(nome="V329", canto="FD"),
            _row(nome="V305", canto="FD"),
        ]},
    })

    result = compare_semantics(expected, actual)

    assert [e["tier"] for e in result["authority_exclusions"]] == [
        "T0_ARM_BEAM_SHARED_WITH_MIRRORED_PILLAR",
        "T0_ARM_BEAM_SHARED_WITH_MIRRORED_PILLAR",
    ]
    assert result["differences"] == []


def test_viga_so_numa_face_do_braco_continua_no_gate():
    # Sem a viga aparecer nas DUAS faces longas do braço (E e F), não há
    # prova estrutural do padrão de braço compartilhado — continua julgada.
    expected = _semantic({"E": {"passa": [_row(nome="V329", canto="EB")]}})
    actual = _semantic({"E": {"passa": [
        _row(nome="V329", canto="EB"),
        _row(nome="V305", canto="EB"),
    ]}})

    result = compare_semantics(expected, actual)

    assert result["authority_exclusions"] == []
    assert [d["field"] for d in result["differences"]] == ["faces.E.passa"]
