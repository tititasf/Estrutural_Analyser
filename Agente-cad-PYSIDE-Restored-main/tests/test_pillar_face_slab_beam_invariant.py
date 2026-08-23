"""Invariante de face: a viga que chega parte o contato da laje.

Regra do domínio confirmada no corpus humano do 13_PAV (56 faces sem exceção
nas duas primeiras cláusulas). Serve para achar face incoerente sem precisar
comparar contra o corpus.
"""
from src.core.pillar_abcd_tables import (
    face_slab_beam_violations,
    validate_face_slab_beam_invariant,
)


def _laje(canto):
    return {"familia": "laje", "nome": "L1", "canto": canto, "papel": "laje"}


def _chega(canto, nome="V1"):
    return {"familia": "viga", "nome": nome, "canto": canto, "papel": "chega"}


def _bucket(lajes=(), chega=()):
    return {"lajes": list(lajes), "passa": [], "chega": list(chega), "interior": []}


def test_chega_no_canto_exige_laje_no_canto_oposto():
    assert face_slab_beam_violations("A", _bucket([_laje("AD")], [_chega("AC")])) == []

    violations = face_slab_beam_violations("A", _bucket([_laje("AA")], [_chega("AC")]))
    assert [v["rule"] for v in violations] == ["chega_no_canto_exige_laje_no_oposto"]


def test_chega_no_meio_exige_duas_lajes_uma_em_cada_canto():
    ok = face_slab_beam_violations(
        "B", _bucket([_laje("BC"), _laje("BD")], [_chega("BB")]),
    )
    assert ok == []

    violations = face_slab_beam_violations("B", _bucket([_laje("BB")], [_chega("BB")]))
    assert [v["rule"] for v in violations] == ["chega_no_meio_exige_duas_lajes"]


def test_sem_chega_a_laje_cobre_a_face():
    assert face_slab_beam_violations("A", _bucket([_laje("AA")])) == []

    violations = face_slab_beam_violations("A", _bucket([_laje("AD")]))
    assert [v["rule"] for v in violations] == ["sem_chega_exige_laje_cobrindo_a_face"]


def test_face_sem_laje_real_nao_gera_violacao():
    assert face_slab_beam_violations("C", _bucket()) == []
    assert face_slab_beam_violations(
        "C", _bucket([{"nome": "nenhuma", "canto": "—"}]),
    ) == []


def test_orientacao_horizontal_usa_os_cantos_da_face_horizontal():
    # Face A horizontal tem extremidades AD/AC; a regra é a mesma.
    assert face_slab_beam_violations(
        "A", _bucket([_laje("AC")], [_chega("AD")]), vertical=False,
    ) == []


def test_validate_percorre_todas_as_faces_do_payload():
    payload = {
        "orientation": "vertical",
        "face_ids": ["A", "B"],
        "faces": {
            "A": _bucket([_laje("AD")], [_chega("AC")]),
            "B": _bucket([_laje("BB")], [_chega("BC")]),
        },
    }

    violations = validate_face_slab_beam_invariant(payload)

    assert [(v["face"], v["rule"]) for v in violations] == [
        ("B", "chega_no_canto_exige_laje_no_oposto"),
    ]
