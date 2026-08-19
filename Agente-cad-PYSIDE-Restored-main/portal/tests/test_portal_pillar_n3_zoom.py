"""Regressao do zoom das faces na ficha N3 de pilares."""

from pathlib import Path


PILLAR_FICHA_JS = (
    Path(__file__).resolve().parents[1] / "app" / "static" / "pillar_ficha.js"
)


def test_zoom_das_faces_permite_afastar_ate_dez_por_cento():
    javascript = PILLAR_FICHA_JS.read_text(encoding="utf-8")
    assert "var FACE_ZOOM_MIN = 0.1;" in javascript
    assert "Math.max(FACE_ZOOM_MIN" in javascript
    assert "Math.max(1,Math.min(5,scale" not in javascript
