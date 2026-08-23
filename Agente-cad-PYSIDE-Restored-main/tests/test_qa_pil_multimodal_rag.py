import hashlib
import json

from scripts.arete.qa_pil_multimodal_rag import build_pack


def _artifact(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def test_visual_and_semantic_authority_are_independent(tmp_path):
    html = tmp_path / "P1.html"
    svg = tmp_path / "P1.svg"
    tables = tmp_path / "P1.json"
    for path in (html, svg, tables):
        path.write_text(path.name, encoding="utf-8")
    corpus_path = tmp_path / "corpus.json"
    corpus = {
        "items": [
            {"item": "P1", "approved_layer": "L1", "semantic_source_kind": "layer_sidecar",
             "semantic": {"face_ids": ["A", "B", "C", "D"], "faces": {}},
             "artifacts": {"html": _artifact(html), "svg": _artifact(svg), "tables": _artifact(tables)}},
            {"item": "P2", "approved_layer": "SA", "semantic_source_kind": "sa_semantic_surrogate_l1",
             "semantic": {"face_ids": ["A", "B", "C", "D"], "faces": {}},
             "artifacts": {"html": _artifact(html), "svg": _artifact(svg), "tables": _artifact(tables)}},
        ],
        "pending_items": [{"item": "P3", "current_layer": "L3"}],
        "negative_examples": [{"item": "P4", "layer": "L1"}],
    }
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    payload = build_pack(corpus, corpus_path)

    assert payload["counts"] == {
        "semantic_t1_candidate": 1, "visual_t1_candidate": 2, "t0": 2, "tx": 1,
    }
    assert payload["records"][1]["channels"]["semantic"]["tier"] == "T0"
    assert payload["records"][1]["channels"]["visual"]["tier"] == "T1_CANDIDATE"
    assert payload["promotion_state"] == "NOT_PROMOTED"
