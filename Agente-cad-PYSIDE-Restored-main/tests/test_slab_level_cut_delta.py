"""Nível de laje por delta de corte: unidade (cm→m) e portões de coerência.

Casos reais do 13_PAV (Obra_TREINO_1) que o bug de unidade deslocou em 2026-09.
"""
from src.core.slab_level_inference import cut_delta_level, gate_cut_delta_level


def test_delta_em_cm_vira_metro():
    assert cut_delta_level(852.12, 7.0) == 852.19      # L324 (antes saía 859.12)
    assert cut_delta_level(852.12, 3.0) == 852.15      # L317 (antes 855.12)
    assert cut_delta_level(852.19, -30.0) == 851.89    # L318 (antes 822.19)


def test_planta_concorda_confirma():
    v = gate_cut_delta_level(852.19, 7.0, reference_level_m=852.12, own_label_level_m=852.19)
    assert v["accepted"] and v["status"] == "confirmed" and v["confirmed_by_label"]


def test_sem_planta_passa_como_inferido():
    v = gate_cut_delta_level(852.15, 3.0, reference_level_m=852.12)
    assert v["accepted"] and v["status"] == "inferred"
    assert any(g["gate"] == "P4_planta" and g["ok"] is None for g in v["gates"])


def test_valor_do_bug_e_barrado_pelo_pavimento():
    v = gate_cut_delta_level(859.12, 7.0, reference_level_m=852.12)
    assert not v["accepted"] and v["status"] == "needs_review"
    assert [g["gate"] for g in v["gates"] if g["ok"] is False] == ["P3_pavimento"]


def test_delta_absurdo_e_barrado_pela_magnitude():
    v = gate_cut_delta_level(852.12 + 1.5, 150.0, reference_level_m=852.12)
    assert not v["accepted"]
    assert any(g["gate"] == "P2_magnitude" and g["ok"] is False for g in v["gates"])


def test_planta_discorda_vai_para_revisao():
    v = gate_cut_delta_level(852.15, 3.0, reference_level_m=852.12, own_label_level_m=852.40)
    assert not v["accepted"] and v["status"] == "needs_review"
