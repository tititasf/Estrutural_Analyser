import json

from scripts.arete.qa_pil_approved_corpus import (
    _inherit_unchanged_row_metadata,
    highest_approved_layer,
)


def test_delta_layer_inherits_only_blank_metadata_of_existing_rows(tmp_path):
    proposals = tmp_path / "propostas"
    proposals.mkdir()
    lower = {
        "orientation": "vertical",
        "faces": {
            "A": {
                "lajes": [], "passa": [], "interior": [],
                "chega": [{
                    "familia": "viga", "nome": "V1", "dim": "19/55",
                    "nivel": "852.19cm", "canto": "AC", "papel": "chega",
                    "dist_esq": "0cm", "dist_dir": "79cm",
                }],
            }
        },
    }
    (proposals / "P1_qa_L1_tables.json").write_text(
        json.dumps(lower), encoding="utf-8",
    )
    semantic = {
        "faces": {
            "A": {
                "lajes": [], "passa": [], "interior": [],
                "chega": [{
                    "familia": "viga", "nome": "V1", "dim": "19/55",
                    "nivel_cm": "", "canto": "AC", "papel": "chega",
                    "dist_esq_cm": "", "dist_dir_cm": "",
                }],
            }
        }
    }

    result = _inherit_unchanged_row_metadata(tmp_path, "P1", "L2", semantic)
    row = result["faces"]["A"]["chega"][0]
    assert row["nivel_cm"] == "852.19"
    assert row["dist_esq_cm"] == "0"
    assert row["dist_dir_cm"] == "79"
    # A função não cria uma linha que não existe no delta aprovado.
    assert result["faces"]["A"]["passa"] == []


def test_later_human_invalidation_does_not_revoke_older_approval():
    # Decisão humana de 2026-08-19: uma camada posterior invalidada é apenas
    # uma tentativa que falhou; a aprovação já dada continua valendo e é ela
    # que define a autoridade semântica do item.
    doc = {
        "aten_pil_hl_l1_human_obra_pav_P1": "validou",
        "aten_pil_hl_l2_human_obra_pav_P1": "invalidou",
    }

    approved, verdicts = highest_approved_layer(doc)

    assert approved == "L1"
    assert verdicts == {"L1": "validou", "L2": "invalidou"}


def test_highest_validated_layer_wins_over_older_approval():
    doc = {
        "aten_pil_hl_l1_human_obra_pav_P1": "validou",
        "aten_pil_hl_l2_human_obra_pav_P1": "invalidou",
        "aten_pil_hl_l3_human_obra_pav_P1": "validou",
    }

    approved, _ = highest_approved_layer(doc)

    assert approved == "L3"


def test_latest_human_approval_is_current_authority():
    doc = {
        "aten_pil_hl_sa_human_obra_pav_P1": "invalidou",
        "aten_pil_hl_l1_human_obra_pav_P1": "validou",
    }

    approved, _ = highest_approved_layer(doc)

    assert approved == "L1"
