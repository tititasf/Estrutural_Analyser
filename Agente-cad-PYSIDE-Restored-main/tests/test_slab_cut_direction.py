"""Corte de laje: a direção vem da borda onde o símbolo foi desenhado.

Caso L318 do 13_PAV (2026-09-27): laje longa (x 1394..4533), corte da viga
horizontal V314 desenhado sobre a borda sul perto da ponta oeste. Pelo centro
da laje a direção saía "Oeste": fatiava no eixo errado e lia o corpo da viga
como aba de laje, gerando −30 cm fictício contra a L319.
"""

import pytest

pytest.importorskip("PySide6")
from main import MainWindow  # noqa: E402

L318 = [[3807.5, 2460.0], [3807.5, 2509.0], [1394.4, 2509.0], [1394.4, 2661.0],
        [4533.4, 2661.0], [4533.4, 2460.0]]
# Seção da V314 (T girado): barra da laje x 2204..2216, nervura 55 em X.
C0 = [[2204, 2460], [2216, 2460], [2216, 2490], [2259, 2490], [2259, 2509],
      [2216, 2509], [2216, 2539], [2204, 2539], [2204, 2460]]
# V318 em L318 norte: laje vizinha 3 cm abaixo (852.19 x 852.16).
C4 = [[2799, 2710], [2799, 2680], [2841, 2680], [2841, 2661], [2798, 2661],
      [2798, 2623], [2786, 2623], [2786, 2680], [2789, 2680], [2789, 2710],
      [2799, 2710]]


class _Host:
    pass


for _n in ("_polygon_x_at_y", "_polygon_y_at_x", "_parse_cut_poly_sections",
           "_slab_bounds", "_points_bbox_tuple", "_bbox_center_tuple",
           "_slab_cut_direction", "_slab_cut_direction_by_edge",
           "_slab_cut_direction_by_center"):
    setattr(_Host, _n, getattr(MainWindow, _n))


def test_corte_na_borda_sul_de_laje_longa_e_sul_nao_oeste():
    h = _Host()
    slab = {"points": L318}
    assert h._slab_cut_direction_by_center(slab, C0) == "Oeste"  # o bug
    assert h._slab_cut_direction(slab, C0) == "Sul"
    geo = h._parse_cut_poly_sections(C0, "Sul")
    assert geo["own_dist_topo"] == 0.0 and geo["neigh_dist_topo"] == 0.0
    assert geo["own_slab_h"] == 12.0 and geo["neigh_slab_h"] == 12.0


def test_corte_na_borda_norte_le_os_3_cm_da_vizinha():
    h = _Host()
    direction = h._slab_cut_direction({"points": L318}, C4)
    assert direction == "Norte"
    geo = h._parse_cut_poly_sections(C4, direction)
    assert geo["own_dist_topo"] == 0.0 and geo["neigh_dist_topo"] == 3.0


def test_corte_longe_de_qualquer_borda_cai_no_centro():
    h = _Host()
    longe = [[3000, 2580], [3010, 2580], [3010, 2590], [3000, 2590]]
    slab = {"points": L318}
    assert h._slab_cut_direction(slab, longe) == h._slab_cut_direction_by_center(slab, longe)
