"""FV curto e contorno em L: geometria, nunca comprimento, decide."""

from src.core.beam_tracer import _separate_one_sided_l_extensions


def _line(x0, x1, y):
    return {"line": [(x0, y), (x1, y)]}


def test_painel_de_um_centimetro_com_duas_faces_e_preservado():
    kept, extensions = _separate_one_sided_l_extensions(
        [(0.0, 1.0), (1.0, 101.0)],
        [_line(0.0, 101.0, 0.0), _line(0.0, 101.0, 19.0)],
        is_horizontal=True,
    )
    assert kept == [(0.0, 1.0), (1.0, 101.0)]
    assert extensions == []


def test_aba_de_uma_face_vira_evidencia_de_l_sem_limiar_de_tamanho():
    kept, extensions = _separate_one_sided_l_extensions(
        [(0.0, 75.0), (75.0, 175.0)],
        [_line(0.0, 175.0, 0.0), _line(75.0, 175.0, 19.0)],
        is_horizontal=True,
    )
    assert kept == [(75.0, 175.0)]
    assert extensions == [{
        "start": 0.0,
        "end": 75.0,
        "face": 0.0,
        "neighbor_index": 1,
        "side": "after",
        "geometry": "one_sided_l_extension",
    }]


def test_aba_em_l_de_um_centimetro_nao_ganha_face_so_por_encostar():
    kept, extensions = _separate_one_sided_l_extensions(
        [(0.0, 1.0), (1.0, 101.0)],
        [_line(0.0, 101.0, 0.0), _line(1.0, 101.0, 19.0)],
        is_horizontal=True,
    )
    assert kept == [(1.0, 101.0)]
    assert extensions == [{
        "start": 0.0,
        "end": 1.0,
        "face": 0.0,
        "neighbor_index": 1,
        "side": "after",
        "geometry": "one_sided_l_extension",
    }]


def test_trecho_isolado_de_uma_face_nao_some_por_tamanho():
    kept, extensions = _separate_one_sided_l_extensions(
        [(0.0, 1.0), (10.0, 110.0)],
        [_line(0.0, 1.0, 0.0), _line(10.0, 110.0, 0.0), _line(10.0, 110.0, 19.0)],
        is_horizontal=True,
    )
    assert kept == [(0.0, 1.0), (10.0, 110.0)]
    assert extensions == []
