"""Campos de nível explícitos: sem datum não há preenchimento assistido."""


def item_levels(pillars, labels):
    facts = []
    for item in pillars + labels:
        fields = ("base", "top") if "hatch_signature" in item else (
            ("slab_level",) if item.get("item_class") == "slab" else ("beam_top", "beam_bottom")
        )
        for field in fields:
            facts.append({"fact_id": f"{item['item_id']}:{field}", "item_id": item["item_id"],
                          "display_name": item["display_name"], "field": field,
                          "value": None, "unit": None, "datum_id": None,
                          "status": "unknown", "evidence_ids": [], "derived_from": [],
                          "warnings": ["item_level_and_reference_not_proven"]})
    return facts
