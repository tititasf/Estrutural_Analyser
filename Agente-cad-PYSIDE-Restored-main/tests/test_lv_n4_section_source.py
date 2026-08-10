"""Regressão do roteamento da Visão Corte LV N2 → N4."""

from pathlib import Path
from unittest.mock import Mock, patch
import importlib.util
import sys


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gerar_lv_dxf_stog.py"
sys.path.insert(0, str(_SCRIPT.parent))
_SPEC = importlib.util.spec_from_file_location("gerar_lv_dxf_stog_test", _SCRIPT)
lv = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(lv)


def _section_view():
    return {
        "b": 14.0,
        "h_section": 50.0,
        "h_A": 54.0,
        "h_B": 54.0,
        "raw": {"visual_primitives": [{"kind": "line", "layer": "CONCRETO", "points": [[0, 0], [1, 1]]}]},
    }


def test_n4_section_prefers_n2_vector_primitives_over_procedural_fallback():
    """N4 deve preservar a seção aprovada do recorte quando ela existe."""
    msp = Mock()
    visual = Mock(return_value=True)
    detail = Mock()
    with patch.object(lv, "draw_section_visual_primitives", visual), patch.object(lv, "draw_section_detail", detail):
        lv.draw_viga_lateral_face_units(
            msp, 0.0, 0.0, "V327", [], [_section_view()], 14.0,
            view="CORTE", n1_contract=False,
        )
    visual.assert_called_once()
    detail.assert_not_called()


def test_n3_section_never_reads_n2_vector_primitives():
    """A separação N1 → N3 continua intacta mesmo quando há vetor N2."""
    msp = Mock()
    n1 = Mock(return_value=True)
    visual = Mock(return_value=True)
    with patch.object(lv, "draw_section_n1_contract_clean", n1), patch.object(lv, "draw_section_visual_primitives", visual):
        lv.draw_viga_lateral_face_units(
            msp, 0.0, 0.0, "V327", [], [_section_view()], 14.0,
            view="CORTE", n1_contract=True,
        )
    n1.assert_called_once()
    visual.assert_not_called()
