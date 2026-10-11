import pytest

from portal.app import lv_cut_map
from src.core import lv_n3_cut_contract

# Símbolo de corte do VF301 (13_PAV): viga 55×14 deitada + laje desenhada com
# 10 cm a 7 cm do topo (x=2203.8).  O mesmo T genérico serve à L303 (h=12) e à L306 (h=10).
T_VF301 = [[2203.8, 3207.0], [2258.8, 3207.0], [2258.8, 3193.0], [2220.8, 3193.0], [2220.8, 3163.0],
           [2210.8, 3163.0], [2210.8, 3193.0], [2203.8, 3193.0], [2203.8, 3207.0]]


def _frame(monkeypatch, slab_height):
    contract = {'slabs': {'A': [{'name': 'L', 'height_cm': slab_height, 'drop_cm': 7.0}], 'B': []}}
    monkeypatch.setattr(lv_n3_cut_contract, 'build_cut_contract', lambda cut: contract)
    return lv_cut_map.identified_frame({'source_cut': {'points': T_VF301}}, 14.0, 55.0)


@pytest.mark.parametrize('slab_height', [10.0, 12.0])
def test_generic_symbol_orients_by_slab_top(monkeypatch, slab_height):
    center, ex, ey, measured_h, _ = _frame(monkeypatch, slab_height)
    # Fundo na aresta x=2258.8, topo em x=2203.8: ey aponta do fundo ao topo.
    assert measured_h == pytest.approx(55.0)
    assert ey == pytest.approx([-1.0, 0.0])
    assert center == pytest.approx([2231.3, 3200.0])


def test_symbol_taller_than_sa_height_counts_drop_from_drawn_top(monkeypatch):
    # V408 (14_PAV, L419): símbolo 60×14, SA declara h=55; laje 10 a 7 cm do topo x=3124.
    v408 = [[3124.0, 2056.0], [3184.0, 2056.0], [3184.0, 2070.0], [3141.0, 2070.0], [3141.0, 2100.0],
            [3131.0, 2100.0], [3131.0, 2070.0], [3124.0, 2070.0], [3124.0, 2056.0]]
    contract = {'slabs': {'A': [], 'B': [{'name': 'L419', 'height_cm': 10.0, 'drop_cm': 7.0}]}}
    monkeypatch.setattr(lv_n3_cut_contract, 'build_cut_contract', lambda cut: contract)
    center, ex, ey, measured_h, _ = lv_cut_map.identified_frame({'source_cut': {'points': v408}}, 14.0, 55.0)
    assert measured_h == pytest.approx(60.0)
    assert ey == pytest.approx([-1.0, 0.0])
    assert center == pytest.approx([3154.0, 2063.0])


def test_slab_off_the_drawing_stays_blocked(monkeypatch):
    contract = {'slabs': {'A': [{'name': 'L', 'height_cm': 10.0, 'drop_cm': 20.0}], 'B': []}}
    monkeypatch.setattr(lv_n3_cut_contract, 'build_cut_contract', lambda cut: contract)
    with pytest.raises(ValueError, match='univocamente'):
        lv_cut_map.identified_frame({'source_cut': {'points': T_VF301}}, 14.0, 55.0)
