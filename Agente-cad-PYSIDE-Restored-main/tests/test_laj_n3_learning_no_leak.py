from src.core.laj_n3_learning import apply_learning_to_ficha, predict_lines


def _pattern(source: str, *, value: float = 60.0) -> dict:
    return {
        "nome": "L1",
        "comprimento": 200.0,
        "largura": 100.0,
        "area_cm2": 20000.0,
        "coordenadas": [[0.0, 0.0], [200.0, 0.0], [200.0, 100.0], [0.0, 100.0]],
        "linhas_verticais": [{"value": value, "is_union": False}],
        "linhas_horizontais": [],
        "_hlaz": [],
        "source": source,
    }


def test_n3_prediction_rejects_n4_and_n2_patterns():
    patterns = [
        _pattern("N4_DXF:Obra:L1"),
        _pattern("N2/N4:Obra:13_PAV:L1"),
        _pattern("N2/N4_validated"),
    ]

    assert predict_lines(
        200.0,
        100.0,
        nome="L1",
        patterns=patterns,
        allow_gabarito_patterns=False,
    ) is None


def test_n3_prediction_rejects_gabarito_prefix_case_insensitively():
    assert predict_lines(
        200.0,
        100.0,
        nome="L1",
        patterns=[_pattern("n4_dxf:obra:L1")],
        allow_gabarito_patterns=False,
    ) is None


def test_n3_prediction_can_use_non_gabarito_algorithmic_pattern():
    prediction = predict_lines(
        200.0,
        100.0,
        nome="L1",
        patterns=[_pattern("algorithmic:panel_distribution")],
        allow_gabarito_patterns=False,
    )

    assert prediction is not None
    assert prediction["linhas_verticais"][0]["value"] == 60.0
    assert prediction["source"] == "learned_algorithmic_patterns"


def test_apply_learning_preserves_n1_when_only_gabarito_exists(monkeypatch):
    monkeypatch.setattr(
        "src.core.laj_n3_learning.load_patterns",
        lambda: [_pattern("N4_DXF:Obra:L1")],
    )
    ficha = {
        "nome": "L1",
        "comprimento": 200.0,
        "largura": 100.0,
        "coordenadas": [[0.0, 0.0], [200.0, 0.0], [200.0, 100.0], [0.0, 100.0]],
        "linhas_verticais": [],
        "linhas_horizontais": [],
    }

    result = apply_learning_to_ficha(
        ficha,
        teacher=None,
        record_teacher=False,
        allow_gabarito_patterns=False,
    )

    assert result == ficha
    assert "_sa_meta" not in result
