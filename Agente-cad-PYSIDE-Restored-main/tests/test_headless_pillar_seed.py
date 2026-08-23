from scripts.arete.headless_sa_analise import _pillar_entities_from_report


def test_fast_path_seeds_pillars_from_canonical_report_for_empty_database():
    report = {
        "P2": {
            "name": "P2",
            "points": [[10, 0], [29, 0], [29, 66], [10, 66], [10, 0]],
            "classification": "CONTINUA",
            "orientation": "vertical",
        },
        "P1": {
            "name": "P1",
            "points": [[0, 0], [19, 0], [19, 55], [0, 55], [0, 0]],
        },
    }

    entities = _pillar_entities_from_report(report, "project-clean")

    assert [row["name"] for row in entities] == ["P1", "P2"]
    assert entities[0]["project_id"] == "project-clean"
    assert entities[0]["area"] == 19 * 55
    assert entities[0]["validated_fields"] == {}
    assert entities[0]["is_validated"] is False
