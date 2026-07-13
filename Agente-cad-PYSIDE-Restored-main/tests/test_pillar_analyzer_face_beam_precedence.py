from src.core.pillar_analyzer import PillarAnalyzer


class _FakeContext:
    """Registra pesquisas e sempre devolve um falso vizinho textual."""

    def __init__(self):
        self.calls = []

    def perform_search(self, _p_data, config, side=None):
        self.calls.append((config["field_id"], side))
        return {
            "found_ent": {"text": "P35"},
            "links": [{"text": "P35"}],
            "confidence": 0.1,
        }


def test_face_beam_slots_do_not_get_overwritten_by_generic_text_search():
    ctx = _FakeContext()
    data = {
        "identity_locked": True,
        "sides_data": {
            "A": {
                "v_passa_esq_n": "V309",
                "v_passa_esq_d": "19/55",
                "v_passa_dir_n": "VF301",
                "v_passa_dir_d": "14/50",
            }
        },
        "links": {},
        "confidence_map": {},
        "_face_beam_authoritative_fields": {
            "p_sA_v_passa_esq_n",
            "p_sA_v_passa_esq_d",
            "p_sA_v_passa_dir_n",
            "p_sA_v_passa_dir_d",
        },
    }

    PillarAnalyzer(ctx).analyze(data)

    assert data["sides_data"]["A"]["v_passa_esq_n"] == "V309"
    assert data["sides_data"]["A"]["v_passa_esq_d"] == "19/55"
    assert data["sides_data"]["A"]["v_passa_dir_n"] == "VF301"
    assert data["sides_data"]["A"]["v_passa_dir_d"] == "14/50"
    searched = {field for field, _side in ctx.calls}
    assert "p_sA_v_passa_esq_n" not in searched
    assert "p_sA_v_passa_esq_d" not in searched
    assert "p_sA_v_passa_dir_n" not in searched
    assert "p_sA_v_passa_dir_d" not in searched


def test_non_authoritative_face_slot_keeps_generic_search_as_fallback():
    ctx = _FakeContext()
    data = {
        "identity_locked": True,
        "sides_data": {"A": {}},
        "links": {},
        "confidence_map": {},
    }

    PillarAnalyzer(ctx).analyze(data)

    searched = {field for field, _side in ctx.calls}
    assert "p_sA_v_passa_esq_n" in searched
    assert "p_sA_v_passa_esq_d" in searched
