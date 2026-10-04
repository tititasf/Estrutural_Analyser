from portal.app.pillar_abcd_review import apply_review, save_review


def test_review_persists_separately_and_requires_matching_source(tmp_path):
    original = {"faces": {"A": {"passa": [{"nome": "V409", "canto": "AC", "dim": "19/60", "nivel": "855.25"}]}}}
    revision = save_review(tmp_path, "14_PAV", "P10", original, [
        {"face": "A", "role": "passa", "index": 0, "field": "dim", "value": "19/55"},
    ])
    assert revision == 1
    assert original["faces"]["A"]["passa"][0]["dim"] == "19/60"
    enriched = {"faces": {"A": {"passa": [{"nome": "V409", "canto": "AC", "dim": "19/55", "nivel": "855.25"}]}}}
    applied = apply_review(enriched, tmp_path, "14_PAV", "P10")
    assert applied["faces"]["A"]["passa"][0]["dim_status"] == "human"
    changed = {"faces": {"A": {"passa": [{"nome": "V410", "canto": "AC", "dim": "19/60"}]}}}
    assert apply_review(changed, tmp_path, "14_PAV", "P10")["faces"]["A"]["passa"][0]["dim"] == "19/60"


def test_corner_review_is_normalized_and_persists_with_other_edits(tmp_path):
    original = {"faces": {"A": {"passa": [{"nome": "V409", "canto": "AC", "dim": "19/55"}]}}}
    assert save_review(tmp_path, "14_PAV", "P10", original, [
        {"face": "A", "role": "passa", "index": 0, "field": "canto", "value": "ad"},
    ]) == 1
    assert save_review(tmp_path, "14_PAV", "P10", original, [
        {"face": "A", "role": "passa", "index": 0, "field": "dim", "value": "19/50"},
    ]) == 2
    applied = apply_review(original, tmp_path, "14_PAV", "P10")["faces"]["A"]["passa"][0]
    assert applied["canto"] == "AD"
    assert applied["canto_status"] == "human"
    assert applied["dim"] == "19/50"
