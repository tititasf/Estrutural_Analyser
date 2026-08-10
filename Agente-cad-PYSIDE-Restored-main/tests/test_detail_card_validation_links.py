"""Regressão: validação express com links string e validated_fields dict."""

from src.core.validation_model import (
    ORIGEM_HUMANO_APP,
    adicionar_validacao_campo,
    campo_esta_validado,
    remover_validacao_campo,
)
from src.ui.widgets.detail_card import DetailCard


def test_normalize_slot_accepts_raw_dimension_string():
    assert DetailCard._normalize_slot_link_list("19/55") == [
        {"text": "19/55", "type": "text"}
    ]
    assert DetailCard._normalize_slot_link_list([{"text": "V1"}]) == [{"text": "V1"}]
    assert DetailCard._normalize_slot_link_list(["14/50"]) == [
        {"text": "14/50", "type": "text"}
    ]


def test_ensure_field_links_coerces_string_slot_in_place():
    item = {
        "links": {
            "p_sB_v_passa_esq_d": {"dim": "19/55", "label": [{"text": "V310"}]},
        }
    }
    links = DetailCard._ensure_field_links_dict(item, "p_sB_v_passa_esq_d")
    assert isinstance(links["dim"], list)
    assert links["dim"][0]["text"] == "19/55"
    # Mutação de validated não deve estourar TypeError
    for link in links["dim"]:
        link["validated"] = True
    assert links["dim"][0]["validated"] is True


def test_validated_fields_dict_remove_does_not_use_list_remove():
    validated = adicionar_validacao_campo({}, "p_sB_v_passa_esq_d:dim", ORIGEM_HUMANO_APP)
    assert campo_esta_validado(validated, "p_sB_v_passa_esq_d:dim")
    # O bug era validated.remove(field_id) com dict
    cleaned = remover_validacao_campo(validated, "p_sB_v_passa_esq_d:dim", origem=ORIGEM_HUMANO_APP)
    assert not campo_esta_validado(cleaned, "p_sB_v_passa_esq_d:dim")
    assert isinstance(cleaned, dict)
