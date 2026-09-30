from __future__ import annotations

import json

import pytest

from portal.app.preprocessamento.contracts import (
    Confidence,
    ContextEnvelope,
    ContextFact,
    ContractError,
    GeometryReference,
    Review,
    ScopeIdentity,
)


REV_A = "a" * 64
REV_B = "b" * 64


def _scope(recorte: str = "rec:doc:torre_1") -> ScopeIdentity:
    return ScopeIdentity(
        obra_id="obra-1",
        pavimento_id="14_PAV",
        recorte_id=recorte,
        source_revision=REV_A,
    )


def test_envelope_preserva_zero_e_desconhecido_como_casos_distintos():
    envelope = ContextEnvelope(
        run_id="run-1",
        scope=_scope(),
        status="partial",
        created_at="2026-09-22T12:00:00Z",
        items=(
            ContextFact(item_id="L1:nivel", display_name="L1", field="nivel", value=0.0),
            ContextFact(item_id="L2:nivel", display_name="L2", field="nivel", value=None),
        ),
    )

    encoded = json.loads(json.dumps(envelope.to_dict(), allow_nan=False))

    assert encoded["items"][0]["value"] == 0.0
    assert encoded["items"][1]["value"] is None
    assert encoded["status"] == "partial"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_contrato_rejeita_valor_nao_finito(value):
    with pytest.raises(ContractError, match="finito"):
        ContextFact(item_id="L1", display_name="L1", field="nivel", value=value)


def test_escopo_incompleto_ou_revisao_nao_sha_sao_rejeitados():
    with pytest.raises(ContractError, match="obra_id"):
        ScopeIdentity("", "14_PAV", "rec:doc:torre_1", REV_A)
    with pytest.raises(ContractError, match="SHA-256"):
        ScopeIdentity("obra-1", "14_PAV", "rec:doc:torre_1", "nome-do-arquivo")


def test_geometria_exige_referencial_e_rejeita_coordenada_nao_finita():
    with pytest.raises(ContractError, match="coordinate_system"):
        GeometryReference("", geometry={"type": "Point", "coordinates": [1, 2]})
    with pytest.raises(ContractError, match="finito"):
        GeometryReference(
            "dxf:modelspace:mm",
            geometry={"type": "Point", "coordinates": [float("nan"), 2]},
        )


def test_confianca_nao_inventa_percentual_e_valida_escala():
    assert Confidence().value is None
    assert Confidence(value=0.0, kind="heuristic").value == 0.0
    with pytest.raises(ContractError, match="entre 0 e 1"):
        Confidence(value=1.01, kind="calibrated")
    with pytest.raises(ContractError, match="kind"):
        Confidence(value=0.95)


def test_duas_torres_com_mesmo_nome_de_item_nao_colidem():
    item_a = ContextFact(item_id="P1:classe", display_name="P1", field="classe", value="NASCE")
    item_b = ContextFact(item_id="P1:classe", display_name="P1", field="classe", value="MORRE")
    envelope_a = ContextEnvelope("run-a", _scope("rec:doc:torre_1"), "complete", "2026-09-22T12:00:00Z", (item_a,))
    envelope_b = ContextEnvelope("run-b", _scope("rec:doc:torre_2"), "complete", "2026-09-22T12:00:00Z", (item_b,))

    assert envelope_a.scope.recorte_id != envelope_b.scope.recorte_id
    assert envelope_a.to_dict()["items"][0]["value"] != envelope_b.to_dict()["items"][0]["value"]


def test_revisao_humana_confirmada_exige_autor_data_e_revisao():
    with pytest.raises(ContractError, match="author_id"):
        Review(status="confirmed", source_revision=REV_B)


def test_item_id_duplicado_no_mesmo_envelope_e_rejeitado():
    item = ContextFact(item_id="P1:classe", display_name="P1", field="classe", value=None)
    with pytest.raises(ContractError, match="duplicado"):
        ContextEnvelope(
            "run-1", _scope(), "complete", "2026-09-22T12:00:00Z", (item, item)
        )
