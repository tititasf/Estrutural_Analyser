import json
import os
from pathlib import Path

from scripts.arete.qa_fv_quadro_pavimento import _find_latest_diagnostic


def _write_diagnostic(path: Path, *, items: int, n1_items: int, n2_items: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "resumo": {
                "itens": items,
                "n1_itens": n1_items,
                "n2_itens": n2_items,
            },
            "itens": [],
        }),
        encoding="utf-8",
    )


def test_quadro_prefers_canonical_scoped_diagnostic_over_newer_raw_partial(tmp_path: Path):
    root = tmp_path / "repo"
    base = root / "scripts" / "arete" / "relatorios" / "diagnosticos_fv" / "Obra" / "13_PAV"
    canonical = base / "120000" / "diagnostico_fv_n1_n2.json"
    raw_partial = base / "130000" / "diagnostico_fv_n1_n2.json"
    _write_diagnostic(canonical, items=5, n1_items=5, n2_items=5)
    _write_diagnostic(raw_partial, items=26, n1_items=5, n2_items=26)
    os.utime(canonical, (100.0, 100.0))
    os.utime(raw_partial, (200.0, 200.0))

    path, report = _find_latest_diagnostic(root, "Obra", "13_PAV")

    assert path == canonical
    assert report["resumo"]["itens"] == 5


def test_quadro_falls_back_to_latest_when_no_scoped_diagnostic_exists(tmp_path: Path):
    root = tmp_path / "repo"
    base = root / "scripts" / "arete" / "relatorios" / "diagnosticos_fv" / "Obra" / "13_PAV"
    older = base / "120000" / "diagnostico_fv_n1_n2.json"
    newer = base / "130000" / "diagnostico_fv_n1_n2.json"
    _write_diagnostic(older, items=26, n1_items=5, n2_items=26)
    _write_diagnostic(newer, items=26, n1_items=6, n2_items=26)
    os.utime(older, (100.0, 100.0))
    os.utime(newer, (200.0, 200.0))

    path, report = _find_latest_diagnostic(root, "Obra", "13_PAV")

    assert path == newer
    assert report["resumo"]["n1_itens"] == 6
