from __future__ import annotations

from pathlib import Path

import ezdxf
from ezdxf import bbox as ezbbox

from scripts.obra_crop_engine import crop_dxf, crop_dxf_multi


def _criar_prancha(path: Path) -> None:
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    # Moldura enorme: o centro (50, 50) cai na seleção, mas a entidade inteira não.
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])
    msp.add_line((40, 40), (60, 60))
    msp.add_circle((50, 50), radius=3)
    msp.add_line((80, 80), (90, 90))
    doc.saveas(path)


def _extents(path: Path) -> tuple[float, float, float, float]:
    doc = ezdxf.readfile(path)
    box = ezbbox.extents(doc.modelspace())
    assert box.has_data
    return box.extmin.x, box.extmin.y, box.extmax.x, box.extmax.y


def test_recorte_manual_contained_nao_leva_moldura_da_prancha(tmp_path: Path) -> None:
    origem = tmp_path / "origem.dxf"
    centro = tmp_path / "centro.dxf"
    exato = tmp_path / "exato.dxf"
    _criar_prancha(origem)

    legado = crop_dxf(origem, centro, (35, 35, 65, 65), padding_pct=0.0)
    manual = crop_dxf(
        origem, exato, (35, 35, 65, 65), padding_pct=0.0,
        selection_mode="contained",
    )

    assert legado["error"] is None
    assert manual["error"] is None
    assert legado["entities_copied"] == 3  # inclui a moldura pelo centro
    assert manual["entities_copied"] == 2
    assert _extents(centro) == (0.0, 0.0, 100.0, 100.0)
    x0, y0, x1, y1 = _extents(exato)
    assert 35 <= x0 <= x1 <= 65
    assert 35 <= y0 <= y1 <= 65


def test_recorte_manual_multi_exige_entidade_contida_em_alguma_area(tmp_path: Path) -> None:
    origem = tmp_path / "origem.dxf"
    saida = tmp_path / "multi.dxf"
    _criar_prancha(origem)

    resultado = crop_dxf_multi(
        origem,
        saida,
        [(35, 35, 65, 65), (78, 78, 92, 92)],
        padding_pct=0.0,
        selection_mode="contained",
    )

    assert resultado["error"] is None
    assert resultado["entities_copied"] == 3
    assert all(e.dxftype() != "LWPOLYLINE" for e in ezdxf.readfile(saida).modelspace())


def test_recorte_manual_vazio_nao_substitui_arquivo_existente(tmp_path: Path) -> None:
    origem = tmp_path / "origem.dxf"
    saida = tmp_path / "existente.dxf"
    _criar_prancha(origem)
    saida.write_bytes(b"conteudo-anterior")

    resultado = crop_dxf(
        origem, saida, (200, 200, 220, 220), padding_pct=0.0,
        selection_mode="contained",
    )

    assert resultado["error"]
    assert saida.read_bytes() == b"conteudo-anterior"
