from src.core.pillar_table_evidence import restore_trusted_face_beam_dimensions


def test_restores_distinct_corner_dimensions_from_trusted_topology():
    tables = {"faces": {
        "A": {"chega": [{"nome": "VF1", "canto": "AC", "dim": "14/55"}]},
        "B": {"chega": [{"nome": "VF1", "canto": "BC", "dim": "14/55"}]},
        "C": {"passa": [
            {"nome": "VF1", "canto": "CA", "dim": "14/55"},
            {"nome": "VF1", "canto": "CB", "dim": "14/55"},
        ]},
    }}
    pillar = {"face_beams": {
        "A": {"para": [{"name": "VF1", "corner": "AC", "dim": "14/55", "source": "collinear_short_face_band"}]},
        "B": {"para": [{"name": "VF1", "corner": "BC", "dim": "19/66", "source": "collinear_short_face_band"}]},
        "C": {
            "passa_esq": {"name": "VF1", "corner": "CA", "dim": "14/55", "source": "collinear_short_face_band"},
            "passa_dir": {"name": "VF1", "corner": "CB", "dim": "19/66", "source": "collinear_short_face_band"},
        },
    }}

    assert restore_trusted_face_beam_dimensions(tables, pillar) == 2
    assert tables["faces"]["B"]["chega"][0]["dim"] == "19/66"
    assert tables["faces"]["C"]["passa"][1]["dim"] == "19/66"
