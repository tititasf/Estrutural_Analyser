import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import ezdxf

from scripts.motor_fase4 import MotorFase4
from src.core.fv_generation_contract import (
    FV_ENGINE_ID,
    build_fv_generation_contract,
    materialize_fv_contract_from_db,
    merge_fv_source_results,
    normalize_fv_generation_contract,
    overlay_fv_state_measurements,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gerar_fv_dxf_stog.py"


def _source():
    return {
        "dim_text": "19/55",
        "segmentos_fundo": [
            {
                "length": 286,
                "dim_width": 19,
                "dim_height": 55,
                "dim_text": "19/55",
                "apoio_inicial": "P26",
                "apoio_final": "P27",
            },
            {
                "length": 254,
                "dim_width": 19,
                "dim_height": 55,
                "dim_text": "19/55",
                "apoio_inicial": "P27",
                "apoio_final": "P28",
            },
        ],
    }


def _fingerprint(path: Path):
    doc = ezdxf.readfile(path)
    result = []
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind == "LINE":
            values = (
                entity.dxf.start.x, entity.dxf.start.y,
                entity.dxf.end.x, entity.dxf.end.y,
            )
        elif kind == "LWPOLYLINE":
            values = tuple(v for point in entity.get_points("xy") for v in point)
        elif kind in {"TEXT", "MTEXT"}:
            continue
        else:
            values = ()
        result.append((kind, tuple(round(float(v), 4) for v in values)))
    return sorted(result)


def _panel_geometry_count(path: Path) -> int:
    doc = ezdxf.readfile(path)
    return sum(
        1
        for entity in doc.modelspace()
        if entity.dxftype() in {"LINE", "LWPOLYLINE"}
        and entity.dxf.layer in {"Painéis", "Paineis"}
    )


def test_contract_preserves_segments_dimensions_and_supports():
    contract = build_fv_generation_contract("V305.C", _source(), floor="13 PAV")
    assert contract["motor_id"] == FV_ENGINE_ID
    assert contract["total_width"] == 19
    assert contract["total_height"] == 55
    assert [s["total_width"] for s in contract["segments_rich"]] == [286, 254]
    assert contract["segments_rich"][1]["row_break"] is True
    assert "panels" not in contract["segments_rich"][0]
    assert contract["label_left"] == "P26"
    assert contract["label_right"] == "P28"


def test_duplicate_beam_occurrences_are_merged_in_sa_order():
    occurrences = [
        {
            "viga_nome": "V301.C",
            "is_horizontal": True,
            "segmentos_fundo": [
                {"seg_index": 1, "coord": [300, 400], "length": 100},
                {"seg_index": 2, "coord": [500, 600], "length": 100},
            ],
        },
        {
            "viga_nome": "V301-1",
            "is_horizontal": True,
            "segmentos_fundo": [
                {"seg_index": 1, "coord": [0, 200], "length": 200},
                {"seg_index": 2, "coord": [700, 850], "length": 150},
            ],
        },
    ]

    merged = merge_fv_source_results(occurrences)

    assert len(merged) == 1
    assert merged[0]["viga_nome"] == "V301"
    assert [segment["length"] for segment in merged[0]["segmentos_fundo"]] == [
        100, 100, 200, 150,
    ]
    assert [segment["seg_index"] for segment in merged[0]["segmentos_fundo"]] == [1, 2, 3, 4]


def test_structured_sa_state_overlays_lengths_without_losing_supports():
    merged = merge_fv_source_results([{"viga_nome": "V301", "segmentos_fundo": [
        {"length": 318, "apoio_inicial": "P1", "apoio_final": "P2"},
        {"length": 106.5, "apoio_inicial": "P2", "apoio_final": "P3"},
    ]}])

    overlaid = overlay_fv_state_measurements(merged, [
        {"beam_name": "V301", "length": 304.47, "width": "19", "status": "valid",
         "level": "852.19", "level_source": "highest_touching_slab", "level_slabs": ["L301"]},
        {"beam_name": "V301", "length": 93.61, "width": "19", "status": "valid"},
    ])

    segments = overlaid[0]["segmentos_fundo"]
    assert [row["length"] for row in segments] == [304.47, 93.61]
    assert [(row["apoio_inicial"], row["apoio_final"]) for row in segments] == [
        ("P1", "P2"), ("P2", "P3"),
    ]
    assert segments[0]["nivel"] == "852.19"
    assert segments[0]["nivel_origem"] == "highest_touching_slab"
    assert segments[0]["nivel_lajes"] == ["L301"]


def test_n1_adapter_delegates_panel_rules_to_the_current_fv_engine():
    contract = build_fv_generation_contract("V305", _source())
    assert all("panels" not in segment for segment in contract["segments_rich"])

    explicit = _source()
    explicit["segmentos_fundo"][0]["panels"] = [
        {"width": 286, "tiers": [[244, 42], [286]]}
    ]
    preserved = build_fv_generation_contract("V305", explicit)
    assert preserved["segments_rich"][0]["panels"] == [
        {"width": 286, "tiers": [[244, 42], [286]]}
    ]


def test_n3_and_n4_use_the_same_fv_ficha_schema_without_losing_n4_details():
    n3 = build_fv_generation_contract("V305", _source(), floor="13 PAV")
    rich_panel = {
        "width": 286,
        "vertices": [[0, 0], [286, 0], [286, 19], [0, 19]],
        "tiers": [[244, 42], [286]],
        "texts": [{"text": "REFINADO N4"}],
    }
    n4 = normalize_fv_generation_contract(
        "V305",
        {
            "name": "V305",
            "floor": "13 PAV",
            "total_width": 19,
            "total_height": 55,
            "segments_rich": [{"total_width": 286, "panels": [rich_panel]}],
        },
    )

    canonical_keys = {
        "contract_version", "motor_id", "number", "name", "floor", "side",
        "total_width", "total_height", "panels", "segments_rich", "holes",
        "label_left", "label_right", "pillar_left", "pillar_right",
        "sarrafo_left_id", "sarrafo_right_id",
    }
    assert canonical_keys <= n3.keys()
    assert canonical_keys <= n4.keys()
    assert n3["motor_id"] == n4["motor_id"] == FV_ENGINE_ID
    assert n4["segments_rich"][0]["panels"][0] == rich_panel
    assert n4["panels"] is n4["segments_rich"]


def test_contract_preserves_every_segment_published_by_sa():
    source = _source()
    source["segmentos_fundo"].insert(
        0,
        {
            "length": 19,
            "dim_width": 19,
            "dim_height": 60,
            "apoio_inicial": "V307",
            "apoio_final": "V307",
        },
    )
    contract = build_fv_generation_contract("V305", source)
    assert [s["total_width"] for s in contract["segments_rich"]] == [19, 286, 254]


def test_contract_preserves_only_available_short_segment():
    source = {
        "dim_text": "19/60",
        "segmentos_fundo": [{
            "length": 30.7,
            "dim_width": 19,
            "dim_height": 60,
            "apoio_inicial": "V309",
            "apoio_final": "V309",
        }],
    }

    contract = build_fv_generation_contract("V307", source)

    assert [s["total_width"] for s in contract["segments_rich"]] == [30.7]
    assert "quality_warnings" not in contract


def test_segment_dimensions_override_stale_beam_header_dimensions():
    source = _source()
    source["dim_text"] = "14/55"

    contract = build_fv_generation_contract("V305", source)

    assert contract["total_width"] == 19
    assert contract["total_height"] == 55


def test_current_sa_length_overrides_stale_segment_ficha_length():
    source = _source()
    source["segmentos_fundo"][0]["ficha"] = {
        "comprimento_total_fundo": 318,
    }

    contract = build_fv_generation_contract("V305", source)

    assert contract["segments_rich"][0]["comprimento_total_fundo"] == 286


def test_n1_database_record_materializes_a_filled_n3_ficha(tmp_path):
    db_path = tmp_path / "project_data.vision"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE beam_elements ("
            "project_id TEXT, classe TEXT, viga_nome TEXT, campos_json TEXT, "
            "updated_at TEXT)"
        )
        connection.execute(
            "INSERT INTO beam_elements VALUES (?, 'FV', ?, ?, ?)",
            (
                "project-13",
                "V305.C",
                json.dumps(_source(), ensure_ascii=False),
                "2026-07-01T12:00:00",
            ),
        )

    target = materialize_fv_contract_from_db(
        db_path=db_path,
        project_id="project-13",
        item_id="V305",
        output_dir=tmp_path / "JSON_Vigas_Fundo",
        floor="13 PAV",
    )

    assert target == tmp_path / "JSON_Vigas_Fundo" / "V305_fundo.json"
    ficha = json.loads(target.read_text(encoding="utf-8"))
    assert ficha["name"] == "V305"
    assert ficha["floor"] == "13 PAV"
    assert ficha["total_width"] == 19
    assert ficha["total_height"] == 55
    assert [segment["total_width"] for segment in ficha["segments_rich"]] == [286, 254]
    assert ficha["panels"] == ficha["segments_rich"]
    assert ficha["sarrafo_left_id"] == ficha["sarrafo_right_id"] == 0


def test_sa_fase4_sync_resolves_full_cad_pavement_and_writes_fv_contract(
    tmp_path,
):
    obra = tmp_path / "Obra_TREINO_1"
    db_path = tmp_path / "project_data.vision"
    project_id = "project-13-current"
    full_pavement = "TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE projects (id TEXT, work_name TEXT, "
            "pavement_name TEXT, updated_at TEXT)"
        )
        connection.execute(
            "CREATE TABLE beam_elements (project_id TEXT, classe TEXT, "
            "viga_nome TEXT, n_segmentos INTEGER, campos_json TEXT)"
        )
        connection.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?)",
            (project_id, obra.name, full_pavement, "2026-07-01T19:19:40"),
        )
        connection.execute(
            "INSERT INTO beam_elements VALUES (?, 'FV', 'V305.C', 2, ?)",
            (project_id, json.dumps(_source(), ensure_ascii=False)),
        )

    motor = MotorFase4(
        str(obra),
        pavimento=full_pavement,
        project_id=project_id,
        db_path=str(db_path),
    )
    written = motor._write_fv_json_from_beam_elements({})

    target = (
        obra / "Fase-4_Sincronizacao" / "JSON_Vigas_Fundo"
        / "V305_fundo.json"
    )
    assert written == 1
    ficha = json.loads(target.read_text(encoding="utf-8"))
    assert ficha["motor_id"] == FV_ENGINE_ID
    assert ficha["contract_version"] >= 3
    assert len(ficha["segments_rich"]) == 2


def test_sa_fase4_sync_keeps_vf_beam_names(tmp_path):
    obra = tmp_path / "Obra_TREINO_1"
    db_path = tmp_path / "project_data.vision"
    project_id = "project-vf"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE projects (id TEXT, work_name TEXT, "
            "pavement_name TEXT, updated_at TEXT)"
        )
        connection.execute(
            "CREATE TABLE beam_elements (project_id TEXT, classe TEXT, "
            "viga_nome TEXT, n_segmentos INTEGER, campos_json TEXT)"
        )
        connection.execute(
            "INSERT INTO projects VALUES (?, ?, '13_PAV', '2026-07-01')",
            (project_id, obra.name),
        )
        connection.execute(
            "INSERT INTO beam_elements VALUES (?, 'FV', 'VF202.C', 2, ?)",
            (project_id, json.dumps(_source(), ensure_ascii=False)),
        )

    motor = MotorFase4(
        str(obra), pavimento="13_PAV", project_id=project_id,
        db_path=str(db_path),
    )

    assert motor._write_fv_json_from_beam_elements({}) == 1
    target = (
        obra / "Fase-4_Sincronizacao" / "JSON_Vigas_Fundo"
        / "VF202_fundo.json"
    )
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8"))["name"] == "VF202"


def test_n3_and_n4_identical_contract_generate_identical_geometry(tmp_path):
    obra = tmp_path / "obra"
    input_n3 = tmp_path / "n3_input"
    input_n4 = tmp_path / "n4_input"
    output_n3 = tmp_path / "n3_output"
    output_n4 = tmp_path / "n4_output"
    for directory in (obra, input_n3, input_n4, output_n3, output_n4):
        directory.mkdir()
    contract = build_fv_generation_contract("V305", _source())
    payload = json.dumps(contract, ensure_ascii=False)
    (input_n3 / "V305_fundo.json").write_text(payload, encoding="utf-8")
    (input_n4 / "V305_fundo.json").write_text(payload, encoding="utf-8")

    for input_dir, output_dir in (
        (input_n3, output_n3),
        (input_n4, output_n4),
    ):
        result = subprocess.run(
            [
                sys.executable, str(SCRIPT), "--obra", str(obra),
                "--item", "V305", "--visual-mode", "NOVA",
                "--input-dir", str(input_dir), "--output-dir", str(output_dir),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr or result.stdout

    assert _fingerprint(output_n3 / "FV_preview_V305.dxf") == _fingerprint(
        output_n4 / "FV_preview_V305.dxf"
    )
    assert _panel_geometry_count(output_n3 / "FV_preview_V305.dxf") > 0
    assert _panel_geometry_count(output_n4 / "FV_preview_V305.dxf") > 0
