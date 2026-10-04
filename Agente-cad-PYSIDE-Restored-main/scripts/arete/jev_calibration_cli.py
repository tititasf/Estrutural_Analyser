#!/usr/bin/env python3
"""G0 manifesto, G2 factory and G3 batch runner. Default is dry-run; never writes N1."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.arete.jev_calibration.cad_source import DxfParserCadSource, SessionIndexCadSource
from scripts.arete.jev_calibration.corpus import write_json
from scripts.arete.jev_calibration.factory import run_factory, write_dry_run
from scripts.arete.jev_calibration.import_known import import_known_corpus
from scripts.arete.jev_calibration.leakage import assert_source_path_allowed
from scripts.arete.jev_calibration.manifest import build_run_manifest, load_manifest
from scripts.arete.jev_calibration.catalog_v1 import CATALOG
from scripts.arete.jev_calibration.catalog_v2 import CATALOG_V2_REVISION
from scripts.arete.jev_calibration.catalog_v3 import CATALOG_V3_REVISION
from scripts.arete.jev_calibration.n1_snapshot import (
    attach_scope_audits, load_snapshot_from_db, load_snapshot_from_estado,
)
from scripts.arete.jev_sa_second_read import verify_source_dxf

DEFAULT_DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_REPORT_ROOT = ROOT / "scripts" / "arete" / "relatorios"


def _new_out(prefix: str, out: Path | None) -> Path:
    if out:
        path = Path(out)
        path.mkdir(parents=True, exist_ok=True)
        return path
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = DEFAULT_REPORT_ROOT / f"{stamp}_{prefix}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _load_source(dxf: Path, index_dir: Path | None):
    from scripts.arete.jev_calibration.hashing import sha256_file

    assert_source_path_allowed(dxf)
    if index_dir:
        from scripts.arete.qa_session_index import SessionIndex
        idx = SessionIndex(Path(index_dir))
        source = SessionIndexCadSource(idx)
        if source.dxf_sha256 != sha256_file(dxf):
            raise ValueError("SessionIndex B3 DXF hash does not match --dxf")
        return source, idx
    return DxfParserCadSource(dxf), None


def cmd_manifest(args) -> int:
    dxf = Path(args.dxf)
    assert_source_path_allowed(dxf)
    from scripts.arete.jev_calibration.hashing import sha256_file
    verify_source_dxf(dxf, sha256_file(dxf))
    estado = Path(args.n1_state_json) if args.n1_state_json else None
    db = Path(args.db) if args.db else None
    if estado:
        snap = load_snapshot_from_estado(estado, args.project_id, args.pav)
        n1_source = snap.source
        fingerprint = snap.fingerprint_sha256
    elif db:
        snap = load_snapshot_from_db(db, args.project_id, args.pav)
        n1_source = snap.source
        fingerprint = snap.fingerprint_sha256
    else:
        n1_source = "unspecified"
        fingerprint = ""
        snap = None
    parser = DxfParserCadSource(dxf)
    out = _new_out("jev_calibracao_manifest", Path(args.out) if args.out else None)
    manifest = build_run_manifest(
        project_id=args.project_id, obra=args.obra, pavimento=args.pav, dxf_path=dxf,
        n1_source=n1_source, n1_fingerprint_sha256=fingerprint,
        command=sys.argv, config={"mode": "manifest", "classes": args.classe},
        qa_manifest_path=Path(args.qa_manifest) if args.qa_manifest else None,
        db_path=db, estado_path=estado, cad_insunits=parser.insunits,
    )
    if snap is not None:
        manifest["n1_snapshot"]["item_counts"] = {
            "PIL": len(snap.names("PIL")), "LAJ": len(snap.names("LAJ")),
        }
    write_json(out / "run_manifest.json", manifest)
    print(json.dumps({
        "status": "WROTE_MANIFEST",
        "out": str(out / "run_manifest.json"),
        "dxf_sha256": manifest["source_dxf"].get("sha256"),
        "comparison_blocked": manifest["local_vs_recorded_vps"]["comparison_blocked"],
        "parity_claimed": False,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_dry_run(args) -> int:
    manifest = load_manifest(Path(args.manifest)) if args.manifest else None
    raw_dxf = args.dxf or (manifest["source_dxf"]["path"] if manifest else None)
    if not raw_dxf:
        raise SystemExit("--dxf is required unless --manifest supplies source_dxf.path")
    dxf = Path(raw_dxf)
    if not dxf.exists():
        dxf = ROOT / raw_dxf
    if not dxf.exists():
        raise SystemExit(f"DXF not found: {raw_dxf}")
    project_id = args.project_id or (manifest["identity"]["project_id"] if manifest else None)
    pav = args.pav or (manifest["identity"]["pavimento"] if manifest else None)
    if not project_id or not pav:
        raise SystemExit("--project-id and --pav are required unless --manifest supplies them")
    source, idx = _load_source(dxf, Path(args.index) if args.index else None)
    if args.n1_state_json:
        snapshot = load_snapshot_from_estado(Path(args.n1_state_json), project_id, pav)
    else:
        snapshot = load_snapshot_from_db(Path(args.db), project_id, pav)
    overlay = attach_scope_audits(
        snapshot,
        lv_audit=Path(args.lv_audit) if getattr(args, "lv_audit", None) else None,
        fv_audit=Path(args.fv_audit) if getattr(args, "fv_audit", None) else None,
    )
    classes = [c.strip().upper() for c in args.classe.split(",") if c.strip()]
    items = [x.strip() for x in args.items.split(",") if x.strip()] if args.items else None
    catalog = str(getattr(args, "catalog", "v1") or "v1").lower()
    identity_base = {"project_id": project_id, "pavimento": pav, "obra": args.obra or (manifest or {}).get("identity", {}).get("obra")}
    audit = run_factory(snapshot=snapshot, source=source, classes=classes, items=items,
                        identity_base=identity_base, limit=args.limit, catalog=catalog)
    out = _new_out("jev_calibracao_dryrun", Path(args.out) if args.out else None)
    run_manifest = manifest or build_run_manifest(
        project_id=project_id, obra=identity_base.get("obra"), pavimento=pav, dxf_path=dxf,
        n1_source=snapshot.source, n1_fingerprint_sha256=snapshot.fingerprint_sha256,
        command=sys.argv, config={"mode": "dry-run", "classes": classes, "items": items,
                                  "discord_overlay": overlay,
                                  "catalog": (
                                      CATALOG_V3_REVISION if catalog == "v3"
                                      else CATALOG_V2_REVISION if catalog == "v2"
                                      else CATALOG["revision"]
                                  )},
        db_path=Path(args.db) if not args.n1_state_json else None,
        estado_path=Path(args.n1_state_json) if args.n1_state_json else None,
        cad_insunits=getattr(source, "insunits", None),
    )
    try:
        paths = write_dry_run(out, audit, run_manifest)
    except RuntimeError as exc:
        raise SystemExit(f"dry-run request-file invariant failed: {exc}") from exc
    if idx is not None:
        idx.close()
    print(json.dumps({
        "status": "DRY_RUN",
        "scanned": audit["scanned"], "packed": audit["packed"],
        "unpackable": audit["unpackable"], "discarded": audit["discarded"],
        "discard_reasons": audit["discard_reasons"],
        "unpackable_reasons": audit.get("unpackable_reasons") or {},
        "n1_relevance_counts": audit.get("n1_relevance_counts") or {},
        "catalog": audit.get("catalog"),
        "catalog_revision": audit.get("catalog_revision"),
        "paths": paths, "jev_api_called": False,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_import_known(args) -> int:
    out = _new_out("jev_calibracao_corpus", Path(args.out) if args.out else None)
    summary = import_known_corpus(out)
    print(json.dumps({"status": "IMPORTED", "out": str(out), **summary}, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_catalog(args) -> int:
    from scripts.arete.jev_calibration.catalog_v1 import catalog_hash
    from scripts.arete.jev_calibration.corpus import write_json

    out = _new_out("jev_calibracao_catalog", Path(args.out) if args.out else None)
    write_json(out / "catalog_v1.json", CATALOG)
    print(json.dumps({
        "status": "WROTE_CATALOG",
        "revision": CATALOG["revision"],
        "sha256": catalog_hash(),
        "out": str(out / "catalog_v1.json"),
        "jev_api_called": False,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_batch(args) -> int:
    from scripts.arete.jev_calibration.runner import run_batch

    out = _new_out("jev_calibracao_g3_batch", Path(args.out) if args.out else None)
    cache = Path(args.cache_dir) if args.cache_dir else out / "cache"
    summary = run_batch(
        requests_dir=Path(args.requests_dir),
        source_dxf=Path(args.source_dxf),
        out_dir=out,
        execute=bool(args.execute),
        max_cases=args.max_cases,
        max_calls=args.max_calls,
        cache_dir=cache,
        diagnostics=bool(args.diagnostics),
    )
    print(json.dumps({
        "status": "BATCH_EXECUTED" if args.execute else "BATCH_DRY_RUN",
        "out": str(out),
        "eligible": summary["eligible"],
        "selected": summary["selected"],
        "calls_reserved": summary.get("calls_reserved"),
        "calls_completed": summary.get("calls_completed"),
        "calls_made": summary["calls_made"],
        "calls_actual_unknown": summary.get("calls_actual_unknown"),
        "technical_errors": summary["technical_errors"],
        "jev_api_attempted": summary.get("jev_api_attempted"),
        "jev_api_called": summary["jev_api_called"],
        "affects_qa_or_n1": False,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_g1_render(args) -> int:
    from scripts.arete.jev_calibration.adjudicate import write_g1_scaffold
    from scripts.arete.jev_calibration.filenames import list_visible_json
    from scripts.arete.jev_calibration.runner import load_request

    out = _new_out("jev_calibracao_g1", Path(args.out) if args.out else None)
    files = list_visible_json(Path(args.requests_dir))
    requests = [(path, load_request(path)) for path in files]
    summary = write_g1_scaffold(requests=requests, dxf=Path(args.source_dxf), out_dir=out)
    print(json.dumps({
        "status": "G1_RENDERED",
        "out": str(out),
        "rows": len(summary["rows"]),
        "jev_api_called": False,
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_man = sub.add_parser("manifest", help="write G0 run_manifest.json with local/VPS hash comparison")
    p_man.add_argument("--project-id", required=True)
    p_man.add_argument("--obra")
    p_man.add_argument("--pav", required=True)
    p_man.add_argument("--dxf", required=True)
    p_man.add_argument("--db", default=str(DEFAULT_DB))
    p_man.add_argument("--n1-state-json")
    p_man.add_argument("--qa-manifest")
    p_man.add_argument("--classe", default="PIL,LAJ")
    p_man.add_argument("--out")
    p_man.set_defaults(func=cmd_manifest)

    p_dry = sub.add_parser("dry-run", help="discover PIL/LAJ packets, validate anti-leakage, write JSONL")
    p_dry.add_argument("--manifest")
    p_dry.add_argument("--project-id")
    p_dry.add_argument("--obra")
    p_dry.add_argument("--pav")
    p_dry.add_argument("--dxf")
    p_dry.add_argument("--db", default=str(DEFAULT_DB))
    p_dry.add_argument("--n1-state-json")
    p_dry.add_argument("--index", help="existing qa_session_index directory with B3")
    p_dry.add_argument("--classe", default="PIL,LAJ")
    p_dry.add_argument("--items", help="comma-separated item names")
    p_dry.add_argument("--limit", type=int)
    p_dry.add_argument("--lv-audit", help="read-only LV cell geometry audit JSON (discord detector)")
    p_dry.add_argument("--fv-audit", help="read-only FV scope audit JSON (discord detector)")
    p_dry.add_argument("--out")
    p_dry.add_argument("--catalog", default="v1", choices=["v1", "v2", "v3"],
                       help="v1 = nearby parallel line (regression); v2 = locator-seeded wall (fail-closed); v3 = source-first encounter")
    p_dry.set_defaults(func=cmd_dry_run)

    p_imp = sub.add_parser("import-known", help="import published L410 example/audit into corpus JSONL")
    p_imp.add_argument("--out")
    p_imp.set_defaults(func=cmd_import_known)

    p_cat = sub.add_parser("catalog", help="write catalog v1 JSON for this revision")
    p_cat.add_argument("--out")
    p_cat.set_defaults(func=cmd_catalog)

    p_batch = sub.add_parser("batch", help="G3 runner: validate packets, optional capped Jev calls")
    p_batch.add_argument("--requests-dir", required=True)
    p_batch.add_argument("--source-dxf", required=True)
    p_batch.add_argument("--execute", action="store_true", help="call Jev; default only validates")
    p_batch.add_argument("--max-cases", type=int, default=2)
    p_batch.add_argument("--max-calls", type=int, default=4)
    p_batch.add_argument("--cache-dir")
    p_batch.add_argument("--diagnostics", action="store_true",
                         help="attach optional Noul/Score companions; they do not vote")
    p_batch.add_argument("--out")
    p_batch.set_defaults(func=cmd_batch)

    p_g1 = sub.add_parser("g1-render", help="render full DXF PNG and local crop; does not seal a visual verdict")
    p_g1.add_argument("--requests-dir", required=True)
    p_g1.add_argument("--source-dxf", required=True)
    p_g1.add_argument("--out")
    p_g1.set_defaults(func=cmd_g1_render)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
