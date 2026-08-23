import hashlib

from scripts.arete.headless_sa_analise import _publish_pl_n3_artifacts


def test_pl_production_artifacts_are_self_contained_and_hashed(tmp_path):
    obra = tmp_path / "obra"
    shared = obra / "Fase-6_Execucao_CAD" / "n3_variants" / "para"
    shared.mkdir(parents=True)
    for filename, value in (
        ("P1.json", b"{}"),
        ("PL_ABCD_preview_P1.dxf", b"abcd"),
        ("PL_GRADES_preview_P1.dxf", b"grades"),
    ):
        (shared / filename).write_bytes(value)
    production = tmp_path / "run"

    rows = _publish_pl_n3_artifacts(obra, ["P1_para", "bad"], production)

    assert len(rows) == 3
    assert all((production / row["path"]).is_file() for row in rows)
    assert all(
        row["sha256"] == hashlib.sha256((production / row["path"]).read_bytes()).hexdigest()
        for row in rows
    )
