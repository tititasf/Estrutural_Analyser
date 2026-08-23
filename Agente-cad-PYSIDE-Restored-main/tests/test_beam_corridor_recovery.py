"""Recuperação do corredor físico da viga pelo par de paredes do DXF.

Casos reais do 13_PAV: `VF203` recebeu do traçador geometria em x 1038–1434,
onde o desenho não tem nada, enquanto seu corredor real vai de 1445 a 3788 —
onde `P33` marca a mudança de largura para `V308`.
"""
from src.core.beam_corridor_recovery import (
    axis_aligned_segments,
    recover_beam_corridor,
    recover_corridors_for_beams,
    run_is_supported_by_walls,
)


def _wall(y, x0, x1):
    return {"points": [(x0, y), (x1, y)]}


# Corredor de 14 cm de 1445 a 3788, interrompido por um pilar em 1601..1625,
# e de 19 cm a partir de 3788 — a assinatura de VF203 x V308.
ENTITIES = [
    _wall(1963.04, 1445, 1601), _wall(1963.04, 1601, 1625), _wall(1963.04, 1625, 3788),
    _wall(1977.04, 1445, 1601), _wall(1977.04, 1625, 3788),
    _wall(1963.04, 3788, 4552), _wall(1982.04, 3788, 4552),
]
SEGS = axis_aligned_segments(ENTITIES)


def test_corredor_para_onde_a_largura_muda():
    corridor = recover_beam_corridor(
        SEGS, (1450.3, 1941.0), 14.0, horizontal=True,
    )

    assert corridor is not None
    x0, y0, x1, y1 = corridor
    # As paredes são agrupadas com uma casa decimal.
    assert round(y0, 1) == 1963.0 and round(y1, 1) == 1977.0
    assert round(x0) == 1445 and round(x1) == 3788


def test_a_viga_larga_pega_o_outro_par_de_paredes():
    corridor = recover_beam_corridor(
        SEGS, (3895.2, 1944.9), 19.0, horizontal=True,
    )

    assert corridor is not None
    x0, y0, x1, y1 = corridor
    assert round(y0, 1) == 1963.0 and round(y1, 1) == 1982.0
    assert round(x0) == 3788


def test_corredor_atravessa_a_interrupcao_do_pilar():
    # A parede de cima não existe dentro do pilar; o corredor não se parte ali.
    corridor = recover_beam_corridor(SEGS, (1450.3, 1941.0), 14.0, horizontal=True)

    assert round(corridor[2]) == 3788


def test_sem_par_de_paredes_com_a_secao_nao_ha_corredor():
    assert recover_beam_corridor(SEGS, (1450.3, 1941.0), 60.0, horizontal=True) is None
    assert recover_beam_corridor(SEGS, (1450.3, 1941.0), None, horizontal=True) is None
    assert recover_beam_corridor(SEGS, None, 14.0, horizontal=True) is None


def test_trecho_sem_parede_desenhada_nao_e_sustentado():
    # O trecho fabricado de VF203 (x 1038..1434 em y 1951..1975).
    assert run_is_supported_by_walls(
        (1038.0, 1951.0, 1434.0, 1975.0), SEGS, horizontal=True,
    ) is False
    assert run_is_supported_by_walls(
        (1445.0, 1963.04, 3788.0, 1977.04), SEGS, horizontal=True,
    ) is True


def test_corredor_e_de_quem_esta_mais_perto_das_paredes():
    beams = [
        {"name": "VF203", "pos": (1450.3, 1941.0)},
        {"name": "DIAGONAL", "pos": (1450.3, 1900.0)},
    ]
    recovered = recover_corridors_for_beams(
        beams, SEGS,
        section_width_of=lambda b: 14.0,
        label_pos_of=lambda b: b["pos"],
        horizontal_of=lambda b: True,
    )

    assert "VF203" in recovered
    assert "DIAGONAL" not in recovered


def test_apoio_da_largura_da_viga_termina_o_corredor():
    # V313 × P20: o pilar tem exatamente a largura do corredor; a viga morre
    # nele. Sem isso a varredura passa direto, porque as arestas do pilar
    # ficam sobre as mesmas retas das paredes.
    from src.core.beam_corridor_recovery import blocking_supports

    pilar_da_largura = (2040.4, 2423.0, 2059.4, 2509.0)
    assert blocking_supports(
        [pilar_da_largura], 2040.4, 2059.4, horizontal=False,
    ) == [(2423.0, 2509.0)]


def test_apoio_mais_largo_que_a_viga_e_atravessado():
    # VF203 × P28: corredor de 14 cm dentro de um pilar de 80 cm.
    from src.core.beam_corridor_recovery import blocking_supports

    pilar_largo = (1600.9, 1963.0, 1624.9, 2043.0)
    assert blocking_supports(
        [pilar_largo], 1963.0, 1977.0, horizontal=True,
    ) == []


def test_apoio_fora_da_faixa_do_corredor_nao_interrompe():
    from src.core.beam_corridor_recovery import blocking_supports

    longe = (2040.4, 2423.0, 2059.4, 2509.0)
    assert blocking_supports([longe], 3000.0, 3019.0, horizontal=False) == []


def test_corredor_recuperado_para_no_apoio_que_separa_outra_viga():
    entidades = [_wall(1963.04, 1445, 3788), _wall(1977.04, 1445, 3788)]
    segs = axis_aligned_segments(entidades)
    # Um apoio de 14 cm — a largura do corredor — no meio do caminho.
    apoio = [(2000.0, 1963.04, 2024.0, 1977.04)]

    corridor = recover_beam_corridor(
        segs, (1450.3, 1941.0), 14.0, horizontal=True, supports=apoio,
        rival_labels=[3000.0],
    )

    assert corridor is not None
    assert round(corridor[0]) == 1445 and round(corridor[2]) == 2000


def test_apoio_sem_outra_viga_do_outro_lado_nao_para_o_corredor():
    entidades = [_wall(1963.04, 1445, 3788), _wall(1977.04, 1445, 3788)]
    segs = axis_aligned_segments(entidades)
    apoio = [(2000.0, 1963.04, 2024.0, 1977.04)]

    corridor = recover_beam_corridor(
        segs, (1450.3, 1941.0), 14.0, horizontal=True, supports=apoio,
    )

    assert round(corridor[2]) == 3788


def test_apoio_so_termina_a_viga_se_houver_outra_do_outro_lado():
    # V313 morre em P20 porque V314 está do outro lado.
    from src.core.beam_corridor_recovery import separating_blocks

    apoio = [(2423.0, 2509.0)]
    assert separating_blocks(apoio, own_label=2082.0, rival_labels=[2800.0]) == apoio


def test_apoio_no_meio_da_propria_viga_nao_a_termina():
    # V308 atravessa P34: do outro lado continua ela mesma.
    from src.core.beam_corridor_recovery import separating_blocks

    assert separating_blocks([(4141.0, 4201.0)], own_label=3895.0, rival_labels=[]) == []
    # Rival do mesmo lado que o rótulo também não separa.
    assert separating_blocks(
        [(4141.0, 4201.0)], own_label=3895.0, rival_labels=[3800.0],
    ) == []


def test_rival_antes_do_apoio_termina_a_viga_que_vem_depois():
    from src.core.beam_corridor_recovery import separating_blocks

    apoio = [(2423.0, 2509.0)]
    assert separating_blocks(apoio, own_label=2800.0, rival_labels=[2082.0]) == apoio


def test_secao_corrompida_e_corrigida_pela_geometria():
    """V307 sai do traçador com `192/60`; o desenho diz `19/60`.

    Nenhum par de paredes fica 192 cm apart; o de 19 existe. A cota vizinha
    é aceita porque a geometria a confirma — não porque está perto.
    """
    entidades = [_wall(1963.04, 1445, 3788), _wall(1977.04, 1445, 3788)]
    segs = axis_aligned_segments(entidades)
    viga = {"name": "V307", "pos": (1450.3, 1941.0)}

    sem_alternativa = recover_corridors_for_beams(
        [viga], segs,
        section_width_of=lambda b: 192.0,
        label_pos_of=lambda b: b["pos"],
        horizontal_of=lambda b: True,
    )
    com_alternativa = recover_corridors_for_beams(
        [viga], segs,
        section_width_of=lambda b: 192.0,
        label_pos_of=lambda b: b["pos"],
        horizontal_of=lambda b: True,
        section_alternatives_of=lambda b: [14.0],
    )

    assert sem_alternativa == {}
    assert round(com_alternativa["V307"][0]) == 1445


def test_alternativa_sem_par_de_paredes_nao_e_adotada():
    entidades = [_wall(1963.04, 1445, 3788), _wall(1977.04, 1445, 3788)]
    segs = axis_aligned_segments(entidades)

    assert recover_corridors_for_beams(
        [{"name": "VX", "pos": (1450.3, 1941.0)}], segs,
        section_width_of=lambda b: 192.0,
        label_pos_of=lambda b: b["pos"],
        horizontal_of=lambda b: True,
        section_alternatives_of=lambda b: [77.0, 88.0],
    ) == {}


def test_reparo_nao_alonga_a_viga_alem_do_apoio_onde_o_tracado_morre():
    """V332 × P9: traçado morre em y 3103, par de paredes segue até 3323.

    As arestas do próprio pilar são colineares com o corredor, então a
    varredura não vê interrupção. O fim do traçado rente a um apoio da
    largura da viga é a prova que falta.
    """
    from src.core.beam_corridor_recovery import clip_to_traced_end

    corredor = (4649.9, 2680.0, 4668.9, 3323.1)
    tracado = [(4656.9, 2661.0, 4680.9, 3103.0)]
    p9 = (4649.9, 3103.0, 4668.9, 3207.0)

    assert clip_to_traced_end(
        corredor, tracado, [p9], horizontal=False,
    ) == (4649.9, 2680.0, 4668.9, 3103.0)


def test_reparo_continua_alongando_quando_o_tracado_morre_no_vazio():
    from src.core.beam_corridor_recovery import clip_to_traced_end

    corredor = (4649.9, 2680.0, 4668.9, 3323.1)
    tracado = [(4656.9, 2661.0, 4680.9, 2900.0)]  # fim longe de qualquer apoio
    p9 = (4649.9, 3103.0, 4668.9, 3207.0)

    assert clip_to_traced_end(
        corredor, tracado, [p9], horizontal=False,
    ) == corredor


def test_apoio_mais_largo_que_o_corredor_nao_corta():
    # Pilar largo deixa a viga embutida: ela sai do outro lado.
    from src.core.beam_corridor_recovery import clip_to_traced_end

    corredor = (4649.9, 2680.0, 4668.9, 3323.1)
    tracado = [(4656.9, 2661.0, 4680.9, 3103.0)]
    largo = (4600.0, 3103.0, 4700.0, 3207.0)

    assert clip_to_traced_end(
        corredor, tracado, [largo], horizontal=False,
    ) == corredor


def test_sem_tracado_o_corredor_fica_como_esta():
    from src.core.beam_corridor_recovery import clip_to_traced_end

    corredor = (4649.9, 2680.0, 4668.9, 3323.1)
    assert clip_to_traced_end(corredor, [], [], horizontal=False) == corredor


def test_corredor_recuperado_tem_de_conter_o_proprio_rotulo():
    """VF301 sai com a seção do pilar (19/66); com 19 o par de paredes achado
    é o da V301, 200 cm ao sul do rótulo dela."""
    from src.core.beam_corridor_recovery import _label_inside_corridor

    rotulo = (1209.8, 3210.8)
    da_v301 = (1197.9, 2991.0, 4552.4, 3010.0)
    dela = (1197.9, 3193.0, 4649.9, 3207.0)

    assert not _label_inside_corridor(da_v301, rotulo, True)
    assert _label_inside_corridor(dela, rotulo, True)


def test_rotulo_desenhado_rente_a_viga_continua_valendo():
    # V305: rótulo 20 cm abaixo do corredor — é como o desenho anota.
    from src.core.beam_corridor_recovery import _label_inside_corridor

    assert _label_inside_corridor(
        (3955.4, 2242.0, 4533.4, 2261.0), (4104.4, 2222.0), True,
    )
