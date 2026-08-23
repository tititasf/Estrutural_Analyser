from src.core.slab_level_inference import select_supported_cut_delta


def test_single_chained_inference_is_rejected():
    assert select_supported_cut_delta([
        {"value": 845.19, "confidence": 0.55, "source_slab": "L311", "human_source": False},
    ]) is None


def test_human_source_or_two_independent_cuts_are_supported():
    direct = {"value": 852.19, "confidence": 0.80, "source_slab": "L1", "human_source": True}
    assert select_supported_cut_delta([direct]) is direct
    a = {"value": 852.19, "confidence": 0.55, "source_slab": "L1", "human_source": False}
    b = {"value": 852.20, "confidence": 0.55, "source_slab": "L2", "human_source": False}
    assert select_supported_cut_delta([a, b]) in (a, b)


from src.core.slab_level_inference import (  # noqa: E402
    plausible_level_candidates,
    point_inside_ring,
    select_plan_level_annotation,
)

# Laje retangular de 400x300 com o rótulo no canto inferior esquerdo.
SLAB = [[0, 0], [400, 0], [400, 300], [0, 300], [0, 0]]


def _cand(value, x, y):
    return {"value": float(value), "text": str(value), "pos": (x, y)}


def test_anotacao_dentro_do_contorno_vence_a_mais_proxima_do_rotulo():
    # Caso L312: o rótulo fica mais perto da anotação da laje vizinha.
    selected = select_plan_level_annotation(
        SLAB,
        [_cand("852.19", -50, -50), _cand("852.16", 200, 150)],
        label_pos=(10, 10),
        floor_height=3.21,
    )

    assert selected["text"] == "852.16"
    assert selected["provenance"] == "contida"
    assert selected["needs_human_review"] is False


def test_duas_anotacoes_dentro_do_contorno_ficam_ambiguas():
    selected = select_plan_level_annotation(
        SLAB,
        [_cand("852.16", 40, 40), _cand("852.19", 200, 150)],
        label_pos=(10, 10),
        floor_height=3.21,
    )

    assert selected["provenance"] == "contida_ambigua"
    assert selected["text"] == "852.19"          # mais próxima do centro
    assert selected["alternatives"] == ["852.16"]


def test_sem_anotacao_no_contorno_cai_para_proximidade_marcada():
    selected = select_plan_level_annotation(
        SLAB, [_cand("852.12", 450, 320)], label_pos=(400, 300),
        floor_height=3.21, label_radius=200.0,
    )

    assert selected["provenance"] == "proximidade"
    assert selected["needs_human_review"] is True


def test_sem_anotacao_no_contorno_e_longe_do_rotulo_nao_inventa_vinculo():
    assert select_plan_level_annotation(
        SLAB, [_cand("852.12", 5000, 5000)], label_pos=(10, 10),
        floor_height=3.21, label_radius=200.0,
    ) is None


def test_nivel_a_um_pe_direito_de_distancia_e_descartado():
    # Caso L317/L324: 855.12 e 859.12 não existem neste pavimento.
    near, far = plausible_level_candidates(
        [_cand("852.19", 0, 0), _cand("852.12", 1, 1), _cand("855.12", 2, 2)],
        reference_level=852.19, floor_height=3.21,
    )

    assert [row["text"] for row in near] == ["852.19", "852.12"]
    assert [row["text"] for row in far] == ["855.12"]


def test_cota_de_dimensao_nao_vira_nivel_mesmo_sendo_maioria():
    # Regressão do defeito real: com a mediana dos próprios candidatos como
    # referência, um conjunto só de cotas (305.5, 311.5, 15.5) passava inteiro
    # porque a mediana também era lixo. A âncora é o nível do pavimento.
    near, far = plausible_level_candidates(
        [_cand("305.5", 0, 0), _cand("311.5", 1, 1), _cand("15.5", 2, 2),
         _cand("852.16", 3, 3)],
        reference_level=852.19, floor_height=3.21,
    )

    assert [row["text"] for row in near] == ["852.16"]
    assert sorted(row["text"] for row in far) == ["15.5", "305.5", "311.5"]


def test_sem_referencia_ou_altura_nada_e_descartado_por_valor():
    candidates = [_cand("852.19", 0, 0), _cand("855.12", 1, 1)]

    for kwargs in ({"reference_level": 852.19}, {"floor_height": 3.21}, {}):
        near, far = plausible_level_candidates(candidates, **kwargs)
        assert len(near) == 2
        assert far == []


def test_point_inside_ring_ignora_ponto_de_fechamento():
    assert point_inside_ring(SLAB, (200, 150)) is True
    assert point_inside_ring(SLAB, (500, 150)) is False
    assert point_inside_ring([[0, 0], [1, 1]], (0, 0)) is False


from src.core.slab_level_inference import inherit_level_from_neighbours  # noqa: E402


def _painel(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# Fileira de baixo (A, B, C) e uma laje da fileira de cima (D), separadas
# pela viga de 19 cm — a geometria de L313/L314/L315 × L306.
PAINEIS = {
    "A": _painel(2933, 2680, 3351, 2991),
    "B": _painel(3370, 2680, 3788, 2991),
    "C": _painel(3807, 2680, 4225, 2991),
    "D": _painel(3370, 3010, 3788, 3193),
    "E": _painel(3370, 2450, 3788, 2661),
}


def test_laje_sem_anotacao_herda_o_nivel_do_painel():
    herdado = inherit_level_from_neighbours(
        PAINEIS,
        {"A": "852.19", "C": "852.19", "E": "852.19", "D": "852.12"},
        {"B": "sem_evidencia_local", "A": "contida", "C": "contida",
         "D": "contida", "E": "contida"},
    )

    assert herdado["B"][0] == "852.19"
    assert herdado["B"][1] == ["A", "C", "D", "E"]


def test_maioria_de_um_voto_so_nao_herda():
    # L303/L328: 2×1 é frágil demais e discorda do humano.
    herdado = inherit_level_from_neighbours(
        PAINEIS,
        {"A": "852.12", "D": "852.12", "C": "852.19"},
        {"B": "sem_evidencia_local", "A": "contida", "C": "contida",
         "D": "contida", "E": "sem_evidencia_local"},
    )

    assert "B" not in herdado


def test_so_herda_de_vizinha_com_anotacao_no_contorno():
    herdado = inherit_level_from_neighbours(
        PAINEIS,
        {"A": "852.19", "C": "852.19", "D": "852.19", "E": "852.19"},
        {"B": "sem_evidencia_local", "A": "proximidade", "C": "proximidade",
         "D": "proximidade", "E": "proximidade"},
    )

    assert herdado == {}


def test_laje_com_anotacao_propria_nao_herda():
    herdado = inherit_level_from_neighbours(
        PAINEIS,
        {"A": "852.19", "B": "852.16", "C": "852.19", "D": "852.19",
         "E": "852.19"},
        {"B": "contida", "A": "contida", "C": "contida", "D": "contida",
         "E": "contida"},
    )

    assert "B" not in herdado


def test_laje_distante_nao_e_vizinha():
    longe = {"A": _painel(0, 0, 100, 100), "B": _painel(500, 0, 600, 100)}

    assert inherit_level_from_neighbours(
        longe, {"A": "852.19"}, {"A": "contida", "B": "sem_evidencia_local"},
    ) == {}


def _quad(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def test_palpite_por_proximidade_cede_para_a_faixa_de_painel():
    """L328: 852.19 por proximidade, entre L327 e L329 (852.12 anotado).

    A vizinha empilhada L321 está noutra fileira e noutro nível — antes ela
    empatava a votação e nada era herdado.
    """
    from src.core.slab_level_inference import inherit_level_from_neighbours

    lajes = {
        "L328": _quad(2059.4, 1977.0, 2477.4, 2048.0),
        "L327": _quad(1622.5, 1977.0, 2040.4, 2048.0),
        "L329": _quad(2496.5, 1977.0, 2914.4, 2048.0),
        "L321": _quad(2059.4, 2067.0, 2477.4, 2490.0),
    }
    niveis = {"L327": "852.12", "L329": "852.12", "L321": "852.19"}
    proveniencia = {
        "L328": "proximidade", "L327": "contida",
        "L329": "contida", "L321": "contida",
    }

    herdado = inherit_level_from_neighbours(lajes, niveis, proveniencia)

    assert herdado["L328"][0] == "852.12"
    assert herdado["L328"][1] == ["L327", "L329"]


def test_faixa_dividida_nao_herda():
    from src.core.slab_level_inference import inherit_level_from_neighbours

    lajes = {
        "L328": _quad(2059.4, 1977.0, 2477.4, 2048.0),
        "L327": _quad(1622.5, 1977.0, 2040.4, 2048.0),
        "L329": _quad(2496.5, 1977.0, 2914.4, 2048.0),
    }
    niveis = {"L327": "852.12", "L329": "852.19"}
    proveniencia = {"L328": "proximidade", "L327": "contida", "L329": "contida"}

    assert inherit_level_from_neighbours(lajes, niveis, proveniencia) == {}


def test_laje_sem_evidencia_local_nao_usa_a_regra_da_faixa():
    """`L303` está a 852.19 no meio de uma faixa de 852.12 — o desenho traz um
    degrau de 7 cm ali. Sem evidência local, o valor do banco fica."""
    from src.core.slab_level_inference import inherit_level_from_neighbours

    lajes = {
        "L303": _quad(2059.4, 3010.0, 2477.4, 3193.0),
        "L302": _quad(1622.4, 3010.0, 2040.4, 3193.0),
        "L304": _quad(2496.4, 3010.0, 2914.4, 3193.0),
        "L311": _quad(2059.4, 2680.0, 2477.4, 2991.0),
    }
    niveis = {"L302": "852.12", "L304": "852.12", "L311": "852.19"}
    proveniencia = {
        "L303": "sem_evidencia_local", "L302": "contida",
        "L304": "contida", "L311": "contida",
    }

    # 2×1 não atinge a vantagem mínima: nada é herdado.
    assert inherit_level_from_neighbours(lajes, niveis, proveniencia) == {}


def test_continuar_a_faixa_distingue_vizinha_lateral_de_empilhada():
    from src.core.slab_level_inference import _continues_strip

    alvo = (2059.4, 1977.0, 2477.4, 2048.0)          # faixa comprida em x
    lateral = (1622.5, 1977.0, 2040.4, 2048.0)        # mesma faixa
    empilhada = (2059.4, 2067.0, 2477.4, 2490.0)      # fileira de cima

    assert _continues_strip(alvo, lateral, 25.0) is True
    assert _continues_strip(alvo, empilhada, 25.0) is False
