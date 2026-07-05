from scripts.arete.arete_runner import _proximo_fail


def test_proximo_fail_handles_generator_error_without_field_diff():
    result = _proximo_fail(
        [
            {
                "elemento_id": "L1",
                "g1": {
                    "resultado": "FAIL",
                    "diffs": [],
                    "erro": "Gerador falhou",
                },
            }
        ]
    )
    assert result == "Atacar G1-FAIL em L1: Gerador falhou."
