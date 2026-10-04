"""Frozen identifiers for the G0 corpus and G2 packet factory."""
from __future__ import annotations

from pathlib import Path

from scripts.arete.jev_sa_second_read import MAX_STATE_BYTES, MODEL

SOURCE_PACKET_SCHEMA = "jev_calibration_source_packet/1"
BASELINE_SCHEMA = "jev_calibration_baseline/1"
ADJUDICATION_SCHEMA = "jev_calibration_adjudication/1"
RUN_MANIFEST_SCHEMA = "jev_calibration_run_manifest/1"
AUDIT_SCHEMA = "jev_calibration_dry_run_audit/1"
BATCH_SCHEMA = "jev_calibration_batch_run/1"
CACHE_SCHEMA = "jev_calibration_cache/1"
ADJUDICATION_RUN_SCHEMA = "jev_calibration_g1_run/1"
JEV_REQUEST_SCHEMA = "jev_sa_second_read_request/1"
CATALOG_REVISION = "v1-2026-09-29-g3-lv-polygon-context"
FACTORY_VERSION = "0.4.0-g3-lv-polygon-context"
CATALOG_SCHEMA = "jev_calibration_catalog/1"
JEV_MODEL = MODEL
MAX_PACKET_STATE_BYTES = MAX_STATE_BYTES

FORBIDDEN_EVIDENCE_KEYS = {
    "baseline_sa", "sa_value", "sa_level", "ground_truth", "qa_verdict",
    "expected_choice", "qa_score", "gabarito", "n1_value", "sa_choice",
}

REPO_ROOT = Path(__file__).resolve().parents[3]
VPS_PARITY_DIR = REPO_ROOT / "scripts" / "arete" / "relatorios" / "20260924_jev_14pav" / "vps_parity"

# Frozen 14_PAV productive identity from the 25/09 VPS parity report.
# These hashes are records, not proof that the live local tree still matches.
FROZEN_VPS_14PAV = {
    "project_id": "f28c3897-c8df-4bb9-a187-cb090f2c7ec7",
    "pavimento": "14_PAV",
    "source_dxf_sha256": "7ec8a5edd4e5aecc78d60002a7198906c83b0699a4a87084fb9fdc7ac5f36a3b",
    "estado_sha256": "06b1da0cff0dcadc5e75c554e30963f8e715fc70b43b1761340d50908b0df5ed",
    "frozen_dxf_relpath": "scripts/arete/relatorios/20260924_jev_14pav/vps_parity/torre_1.dxf",
    "frozen_estado_relpath": "scripts/arete/relatorios/20260924_jev_14pav/vps_parity/estado_14_PAV.json",
}

# Local 14_PAV copy that the same report proved is a different identity.
RECORDED_LOCAL_14PAV_DIVERGENT = {
    "project_id": "d4f298ab-1658-4e60-898d-ec666d54ba8c",
    "source_dxf_sha256": "cdec0cdaf33921c11535cb199792144691481f5b89200fb8589b0e409039466b",
}

MODULE_COMPARE_PAIRS = (
    ("src/core/beam_tracer.py", "scripts/arete/relatorios/20260924_jev_14pav/vps_parity/beam_tracer.py"),
    ("src/core/beam_interpreters/fundo_viga.py", "scripts/arete/relatorios/20260924_jev_14pav/vps_parity/fundo_viga.py"),
    ("scripts/analise_geral_headless.py", "scripts/arete/relatorios/20260924_jev_14pav/vps_parity/analise_geral_headless.py"),
    ("portal/app/pipeline_runner.py", "scripts/arete/relatorios/20260924_jev_14pav/vps_parity/pipeline_runner.py"),
)

EXECUTED_MODULE_RELS = (
    "scripts/arete/jev_sa_second_read.py",
    "scripts/arete/jev_qa_bridge.py",
    "scripts/arete/qa_session_index.py",
    "scripts/arete/qa_n1_sources.py",
    "scripts/arete/jev_calibration_cli.py",
    "scripts/arete/jev_calibration/factory.py",
    "scripts/arete/jev_calibration/adapters_pil.py",
    "scripts/arete/jev_calibration/adapters_laj.py",
    "scripts/arete/jev_calibration/adapters_lv.py",
    "scripts/arete/jev_calibration/adapters_lv_v2.py",
    "scripts/arete/jev_calibration/catalog_v2.py",
    "scripts/arete/jev_calibration/adapters_lv_v3.py",
    "scripts/arete/jev_calibration/catalog_v3.py",
    "scripts/arete/jev_calibration/geometry_util.py",
    "scripts/arete/jev_calibration/adapters_fv.py",
    "scripts/arete/jev_calibration/runner.py",
    "scripts/arete/jev_calibration/adjudicate.py",
)

ADJUDICATION_LABELS = (
    "CORRETO",
    "INCORRETO",
    "INDETERMINADO_POR_FONTE",
    "CONVENCAO_INDETERMINADA",
    "PENDENTE_G1",
)
