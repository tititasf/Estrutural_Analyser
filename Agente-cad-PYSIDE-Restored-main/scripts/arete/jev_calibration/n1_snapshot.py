"""Read-only N1 identity used only to detect discordance and fill baseline."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.arete.qa_n1_sources import json_value, load_item_sources, raw_snapshot_hash, table_columns

from .hashing import sha256_file, sha256_json


@dataclass(frozen=True)
class N1Item:
    classe: str
    name: str
    points: list[list[float]]
    sa_value: Any
    sa_field: str
    snapshot_hash: str
    extras: dict[str, Any]


def _bbox(points: list[list[float]]) -> list[float] | None:
    if not points:
        return None
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _center(points: list[list[float]]) -> list[float] | None:
    box = _bbox(points)
    if not box:
        return None
    return [round((box[0] + box[2]) / 2.0, 3), round((box[1] + box[3]) / 2.0, 3)]


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


class N1Snapshot:
    def __init__(self, *, project_id: str, pavimento: str, source: str,
                 fingerprint_sha256: str, items: dict[tuple[str, str], N1Item]) -> None:
        self.project_id = project_id
        self.pavimento = pavimento
        self.source = source
        self.fingerprint_sha256 = fingerprint_sha256
        self.items = items

    def get(self, classe: str, name: str) -> N1Item | None:
        return self.items.get((classe.upper(), name))

    def names(self, classe: str) -> list[str]:
        wanted = classe.upper()
        return sorted(name for (cls, name) in self.items if cls == wanted)

    def item_hash(self, classe: str, name: str) -> str | None:
        item = self.get(classe, name)
        return item.snapshot_hash if item else None


def _fv_extras(data: dict, links: dict, points: list) -> dict[str, Any]:
    segs = ((links.get("viga_segs") or {}).get("seg_bottom") or [])
    segments = []
    claims = []
    for index, seg in enumerate(segs, 1):
        ficha = seg.get("ficha") or {}
        statement = str(ficha.get("abertura_especial") or "")
        segments.append({
            "index": index, "points": seg.get("points") or [],
            "statement": statement, "width": (ficha.get("largura") or seg.get("width")),
        })
        if "interferencia" in statement:
            claims.append(statement)
    global_names = sorted({
        str(p.get("name") or p.get("text"))
        for p in ((links.get("aberturas") or {}).get("pilar") or [])
        if p.get("name") or p.get("text")
    })
    repeated = len(segments) > 1 and len(claims) == len(segments) and len(set(claims)) == 1
    return {
        "segments": segments, "global_opening_names": global_names,
        "repeated_claim": claims[0] if repeated else None,
        "bbox": _bbox(points), "center": _center(points),
        "is_h": data.get("is_h"), "lv_is_h": data.get("lv_is_h"),
    }


def _lv_extras(data: dict, links: dict, points: list) -> dict[str, Any]:
    contracts = data.get("lv_generation_contracts") or {}
    cells = []
    ready = []
    for behavior, sides in contracts.items():
        if not isinstance(sides, dict):
            continue
        for side, cell in sides.items():
            ready.append(bool((cell or {}).get("generation_ready")))
            for entry in ((cell or {}).get("structural_segments") or []):
                cells.append({
                    "kind": f"lateral_{str(side).lower()}_{str(behavior).lower()}",
                    "side": side, "behavior": behavior,
                    "index": entry.get("index") or entry.get("segment_index"),
                    "points": entry.get("points") or [],
                    "width": entry.get("width"),
                    "generation_ready": (cell or {}).get("generation_ready"),
                })
    fundo = ((links.get("viga_segs") or {}).get("seg_bottom") or [])
    return {
        "cells": cells,
        "fundo": [{"index": i, "points": s.get("points") or []} for i, s in enumerate(fundo, 1)],
        "generation_ready": all(ready) if ready else None,
        "is_h": data.get("is_h"), "lv_is_h": data.get("lv_is_h"),
        "bbox": _bbox(points), "center": _center(points),
    }


def _points_from_beam(data: dict, links: dict, classe: str) -> list:
    if classe == "FV":
        segs = ((links.get("viga_segs") or {}).get("seg_bottom") or [])
        pts: list = []
        for seg in segs:
            pts.extend(seg.get("points") or [])
        return pts
    contracts = data.get("lv_generation_contracts") or {}
    pts = []
    for sides in contracts.values():
        if not isinstance(sides, dict):
            continue
        for cell in sides.values():
            for entry in ((cell or {}).get("structural_segments") or []):
                pts.extend(entry.get("points") or [])
    return pts


def load_snapshot_from_db(db_path: Path, project_id: str, pavimento: str) -> N1Snapshot:
    con = _connect_ro(db_path)
    try:
        items: dict[tuple[str, str], N1Item] = {}
        fingerprint_payload: dict[str, Any] = {}
        for classe, table in (("PIL", "pillars"), ("LAJ", "slabs")):
            available = table_columns(con, table)
            cols = [c for c in ("id", "name", "points_json", "links_json", "extra_data_json", "sides_data_json")
                    if c in available]
            rows = con.execute(
                f"SELECT {', '.join(cols)} FROM {table} WHERE project_id=? ORDER BY name, id",
                (project_id,),
            ).fetchall()
            fingerprint_payload[table] = [dict(row) for row in rows]
            for row in rows:
                name = str(row["name"] or "")
                if not name:
                    continue
                points = json_value(row["points_json"] if "points_json" in row.keys() else "[]") or []
                links = json_value(row["links_json"] if "links_json" in row.keys() else "{}") or {}
                extra = json_value(row["extra_data_json"] if "extra_data_json" in row.keys() else "{}") or {}
                if classe == "PIL":
                    sa_field, sa_value = "dim", extra.get("dim") or (links.get("dimensao") or {}).get("label")
                else:
                    labels = ((links.get("laje_nivel") or {}).get("label") or [])
                    first = labels[0] if labels else None
                    sa_value = first.get("text") if isinstance(first, dict) else first
                    sa_field = "laje_nivel"
                values = {k: row[k] for k in row.keys()}
                items[(classe, name)] = N1Item(
                    classe=classe, name=name, points=points, sa_value=sa_value,
                    sa_field=sa_field, snapshot_hash=raw_snapshot_hash(values),
                    extras={"links": links, "extra": extra, "bbox": _bbox(points), "center": _center(points)},
                )
        if "beams" in {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
            available = table_columns(con, "beams")
            cols = [c for c in ("id", "name", "data_json", "links_json") if c in available]
            rows = con.execute(
                f"SELECT {', '.join(cols)} FROM beams WHERE project_id=? ORDER BY name, id",
                (project_id,),
            ).fetchall()
            fingerprint_payload["beams"] = [dict(row) for row in rows]
            for row in rows:
                name = str(row["name"] or "")
                if not name:
                    continue
                data = json_value(row["data_json"] if "data_json" in row.keys() else "{}") or {}
                links = data.get("links") or json_value(row["links_json"] if "links_json" in row.keys() else "{}") or {}
                values = {k: row[k] for k in row.keys()}
                fv_pts = _points_from_beam(data, links, "FV")
                lv_pts = _points_from_beam(data, links, "LV")
                fv_ex = _fv_extras(data, links, fv_pts)
                lv_ex = _lv_extras(data, links, lv_pts)
                items[("FV", name)] = N1Item(
                    classe="FV", name=name, points=fv_pts, sa_value=fv_ex.get("repeated_claim"),
                    sa_field="fv_segment_local_proof", snapshot_hash=raw_snapshot_hash(values),
                    extras=fv_ex,
                )
                items[("LV", name)] = N1Item(
                    classe="LV", name=name, points=lv_pts, sa_value=lv_ex.get("generation_ready"),
                    sa_field="lv_cell", snapshot_hash=raw_snapshot_hash(values), extras=lv_ex,
                )
        fingerprint = sha256_json(fingerprint_payload)
    finally:
        con.close()
    return N1Snapshot(project_id=project_id, pavimento=pavimento,
                      source=f"sqlite:{db_path}", fingerprint_sha256=fingerprint, items=items)


def _estado_beam_items(state: dict) -> dict[tuple[str, str], N1Item]:
    segs = state.get("segmentos") or {}
    by_beam: dict[str, dict[str, list]] = {}
    for kind, rows in segs.items():
        for row in rows or []:
            name = str(row.get("beam_name") or "")
            if name:
                by_beam.setdefault(name, {}).setdefault(kind, []).append(row)
    items: dict[tuple[str, str], N1Item] = {}
    for name, kinds in by_beam.items():
        fundo = kinds.get("fundo") or []
        fv_pts = []
        fv_segs = []
        for row in fundo:
            fv_pts.extend(row.get("points") or [])
            fv_segs.append({
                "index": row.get("segment_label"), "points": row.get("points") or [],
                "statement": "", "width": row.get("width"), "length": row.get("length"),
            })
        fv_ex = {
            "segments": fv_segs, "global_opening_names": [], "repeated_claim": None,
            "bbox": _bbox(fv_pts), "center": _center(fv_pts), "estado_kind": "fundo",
        }
        items[("FV", name)] = N1Item(
            classe="FV", name=name, points=fv_pts, sa_value=None,
            sa_field="fv_segment_local_proof", snapshot_hash=sha256_json(fundo), extras=fv_ex,
        )
        cells = []
        lv_pts = []
        for kind, rows in kinds.items():
            if not str(kind).startswith("lateral_"):
                continue
            for row in rows:
                lv_pts.extend(row.get("points") or [])
                cells.append({
                    "kind": kind, "side": row.get("side"), "behavior": row.get("behavior"),
                    "index": row.get("segment_label"), "points": row.get("points") or [],
                    "width": row.get("width"), "length": row.get("length"),
                    "generation_ready": None,
                })
        lv_ex = {
            "cells": cells,
            "fundo": [{"index": r.get("segment_label"), "points": r.get("points") or []} for r in fundo],
            "generation_ready": None, "bbox": _bbox(lv_pts), "center": _center(lv_pts),
        }
        items[("LV", name)] = N1Item(
            classe="LV", name=name, points=lv_pts, sa_value=None,
            sa_field="lv_cell", snapshot_hash=sha256_json(cells), extras=lv_ex,
        )
    return items


def load_snapshot_from_estado(path: Path, project_id: str, pavimento: str) -> N1Snapshot:
    state = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    items: dict[tuple[str, str], N1Item] = {}
    for row in state.get("slabs") or []:
        name = str(row.get("name") or "")
        points = row.get("points") or []
        items[("LAJ", name)] = N1Item(
            classe="LAJ", name=name, points=points, sa_value=row.get("nivel"),
            sa_field="laje_nivel", snapshot_hash=sha256_json(row),
            extras={"bbox": _bbox(points), "center": _center(points), "height": row.get("height")},
        )
    for row in state.get("pilares") or state.get("pillars") or []:
        name = str(row.get("name") or row.get("key") or "")
        points = row.get("points") or []
        dim = row.get("dim") or ((row.get("extra") or {}).get("dim") if isinstance(row.get("extra"), dict) else None)
        items[("PIL", name)] = N1Item(
            classe="PIL", name=name, points=points, sa_value=dim, sa_field="dim",
            snapshot_hash=sha256_json(row),
            extras={"bbox": _bbox(points), "center": _center(points)},
        )
    items.update(_estado_beam_items(state))
    return N1Snapshot(
        project_id=project_id, pavimento=pavimento,
        source=f"estado_json:{path}",
        fingerprint_sha256=sha256_file(path),
        items=items,
    )


def attach_scope_audits(snapshot: N1Snapshot, *, lv_audit: Path | None = None,
                        fv_audit: Path | None = None) -> dict[str, Any]:
    """Overlay frozen productive audits as discord detectors only (not Jev evidence)."""
    attached = {"lv": None, "fv": None}
    if lv_audit and Path(lv_audit).is_file():
        payload = json.loads(Path(lv_audit).read_text(encoding="utf-8-sig"))
        attached["lv"] = {"path": str(lv_audit), "schema": payload.get("schema")}
        for row in payload.get("results") or []:
            item = snapshot.get("LV", row.get("item"))
            if item is not None:
                item.extras["lv_audit_cells"] = row.get("cells") or []
                item.extras["lv_audit_remote"] = row.get("remote_cells")
    if fv_audit and Path(fv_audit).is_file():
        payload = json.loads(Path(fv_audit).read_text(encoding="utf-8-sig"))
        attached["fv"] = {"path": str(fv_audit), "schema": payload.get("schema")}
        for row in payload.get("results") or []:
            item = snapshot.get("FV", row.get("item"))
            if item is not None:
                item.extras["scope_audit"] = row
                item.extras["repeated_claim"] = (
                    row["segments"][0]["statement"] if row.get("repeated_same_claim_across_segments")
                    and row.get("segments") else None
                )
                if item.extras.get("repeated_claim"):
                    # dataclass is frozen; extras dict remains mutable for overlay.
                    pass
    return attached


def load_item_row(db_path: Path, project_id: str, classe: str, item: str) -> dict[str, Any]:
    con = _connect_ro(db_path)
    try:
        sources = ("payload", "geometry", "extra", "sides")
        return load_item_sources(con, project_id=project_id, classe=classe, item=item,
                                 requested_sources=sources)
    finally:
        con.close()
