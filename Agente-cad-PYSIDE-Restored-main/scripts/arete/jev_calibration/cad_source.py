"""Neighborhood CAD lookup from B3 or a DXF parser. The whole file stays on disk."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from scripts.arete.qa_session_index import (
    DEFAULT_GRID_CELL,
    _check_dxf_path_allowed,
    _entity_geometry,
    _sha256_file,
)

from .leakage import assert_source_path_allowed


@dataclass(frozen=True)
class CadEntity:
    handle: str
    etype: str
    layer: str | None
    minx: float
    miny: float
    maxx: float
    maxy: float
    text: str | None
    points: list[list[float]]
    closed: bool | None = None

    @property
    def xy(self) -> list[float]:
        cx = (self.minx + self.maxx) / 2.0
        cy = (self.miny + self.maxy) / 2.0
        if self.points:
            cx = sum(p[0] for p in self.points) / len(self.points)
            cy = sum(p[1] for p in self.points) / len(self.points)
        return [round(cx, 3), round(cy, 3)]

    def as_candidate(self) -> dict[str, Any]:
        payload = {
            "handle": self.handle,
            "etype": self.etype,
            "layer": self.layer,
            "xy": self.xy,
        }
        if self.text is not None:
            payload["text"] = self.text
        return payload


class CadSource(Protocol):
    dxf_path: Path
    dxf_sha256: str

    def texts_in_bbox(self, minx: float, miny: float, maxx: float, maxy: float) -> list[CadEntity]: ...
    def entities_near(self, x: float, y: float, radius: float, types: list[str] | None = None) -> list[CadEntity]: ...
    def entities_of_type(self, etype: str, bbox: list[float] | None = None) -> list[CadEntity]: ...
    def by_handle(self, handle: str) -> CadEntity | None: ...
    def known_handles(self) -> set[str]: ...
    def texts_with_value(self, text: str) -> list[CadEntity]: ...


def _row_to_entity(row: dict) -> CadEntity:
    points = row.get("points") or json.loads(row.get("points_json") or "[]")
    return CadEntity(
        handle=str(row.get("handle") or ""),
        etype=str(row.get("etype") or ""),
        layer=row.get("layer_meta") or row.get("layer"),
        minx=float(row["minx"]), miny=float(row["miny"]),
        maxx=float(row["maxx"]), maxy=float(row["maxy"]),
        text=row.get("text_content") or row.get("text"),
        points=[[float(p[0]), float(p[1])] for p in points],
        closed=_infer_closed(points, etype=str(row.get("etype") or "")),
    )


def _infer_closed(points: list, *, etype: str, flagged: bool | None = None) -> bool | None:
    if flagged is True:
        return True
    pts = [[float(p[0]), float(p[1])] for p in points or []]
    if len(pts) >= 4 and abs(pts[0][0] - pts[-1][0]) < 0.05 and abs(pts[0][1] - pts[-1][1]) < 0.05:
        return True
    if flagged is False:
        return False
    return None


class SessionIndexCadSource:
    def __init__(self, index) -> None:
        b3 = index.manifest.get("b3") or {}
        if not b3.get("enabled") or not b3.get("dxf"):
            raise ValueError("SessionIndex has no B3 DXF; factory needs B3 or a parser")
        self.dxf_path = Path(b3["dxf"])
        assert_source_path_allowed(self.dxf_path)
        self.dxf_sha256 = str(index.manifest["dxf_sha256"])
        self._index = index

    def texts_in_bbox(self, minx: float, miny: float, maxx: float, maxy: float) -> list[CadEntity]:
        return [_row_to_entity(row) for row in self._index.b3_texts_in_bbox(minx, miny, maxx, maxy)]

    def entities_near(self, x: float, y: float, radius: float, types: list[str] | None = None) -> list[CadEntity]:
        return [_row_to_entity(row) for row in self._index.b3_entities_near(x, y, radius, types)]

    def entities_of_type(self, etype: str, bbox: list[float] | None = None) -> list[CadEntity]:
        return [_row_to_entity(row) for row in self._index.b3_entities_of_type(etype, bbox)]

    def by_handle(self, handle: str) -> CadEntity | None:
        row = self._index.con.execute(
            "SELECT * FROM b3_entities WHERE handle=?", (handle,)
        ).fetchone()
        if row is None:
            return None
        payload = dict(row)
        payload["points"] = json.loads(payload.pop("points_json"))
        return _row_to_entity(payload)

    def known_handles(self) -> set[str]:
        rows = self._index.con.execute("SELECT handle FROM b3_entities").fetchall()
        return {str(row[0]) for row in rows if row[0]}

    def texts_with_value(self, text: str) -> list[CadEntity]:
        rows = self._index.con.execute(
            "SELECT * FROM b3_entities WHERE etype IN ('TEXT','MTEXT') AND text_content=?",
            (text,),
        ).fetchall()
        out = []
        for row in rows:
            payload = dict(row)
            payload["points"] = json.loads(payload.pop("points_json"))
            out.append(_row_to_entity(payload))
        return out


class DxfParserCadSource:
    """In-memory spatial index of one Fase-1 (or frozen) DXF. Queries return slices."""

    def __init__(self, dxf_path: Path, *, grid_cell: float = DEFAULT_GRID_CELL) -> None:
        import ezdxf

        self.dxf_path = Path(dxf_path)
        _check_dxf_path_allowed(self.dxf_path)
        assert_source_path_allowed(self.dxf_path)
        self.dxf_sha256 = _sha256_file(self.dxf_path)
        self.grid_cell = float(grid_cell)
        doc = ezdxf.readfile(str(self.dxf_path))
        self.insunits = None
        try:
            self.insunits = int(doc.header.get("$INSUNITS"))
        except Exception:
            self.insunits = None
        self._entities: list[CadEntity] = []
        self._by_handle: dict[str, CadEntity] = {}
        self._grid: dict[tuple[int, int], list[int]] = {}
        for entity in doc.modelspace():
            points, text = _entity_geometry(entity)
            if not points:
                continue
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            flagged = None
            try:
                if entity.dxftype() == "LWPOLYLINE":
                    flagged = bool(entity.closed)
                elif entity.dxftype() == "POLYLINE":
                    flagged = bool(entity.is_closed)
            except Exception:
                flagged = None
            cad = CadEntity(
                handle=str(entity.dxf.handle),
                etype=entity.dxftype(),
                layer=getattr(entity.dxf, "layer", None),
                minx=min(xs), miny=min(ys), maxx=max(xs), maxy=max(ys),
                text=text,
                points=[[float(p[0]), float(p[1])] for p in points],
                closed=_infer_closed(points, etype=entity.dxftype(), flagged=flagged),
            )
            eid = len(self._entities)
            self._entities.append(cad)
            self._by_handle[cad.handle] = cad
            for cx in range(int(cad.minx // self.grid_cell), int(cad.maxx // self.grid_cell) + 1):
                for cy in range(int(cad.miny // self.grid_cell), int(cad.maxy // self.grid_cell) + 1):
                    self._grid.setdefault((cx, cy), []).append(eid)

    def _candidates_for_bbox(self, minx: float, miny: float, maxx: float, maxy: float) -> list[CadEntity]:
        eids: set[int] = set()
        for cx in range(int(minx // self.grid_cell), int(maxx // self.grid_cell) + 1):
            for cy in range(int(miny // self.grid_cell), int(maxy // self.grid_cell) + 1):
                eids.update(self._grid.get((cx, cy), ()))
        out = []
        for eid in eids:
            ent = self._entities[eid]
            if ent.maxx >= minx and ent.minx <= maxx and ent.maxy >= miny and ent.miny <= maxy:
                out.append(ent)
        return out

    def texts_in_bbox(self, minx: float, miny: float, maxx: float, maxy: float) -> list[CadEntity]:
        return [e for e in self._candidates_for_bbox(minx, miny, maxx, maxy)
                if e.etype in {"TEXT", "MTEXT"}]

    def entities_near(self, x: float, y: float, radius: float, types: list[str] | None = None) -> list[CadEntity]:
        found = []
        for ent in self._candidates_for_bbox(x - radius, y - radius, x + radius, y + radius):
            if types and ent.etype not in types:
                continue
            dx = max(ent.minx - x, 0.0, x - ent.maxx)
            dy = max(ent.miny - y, 0.0, y - ent.maxy)
            if math.hypot(dx, dy) <= radius:
                found.append(ent)
        found.sort(key=lambda e: math.hypot(e.xy[0] - x, e.xy[1] - y))
        return found

    def entities_of_type(self, etype: str, bbox: list[float] | None = None) -> list[CadEntity]:
        if bbox:
            return [e for e in self._candidates_for_bbox(bbox[0], bbox[1], bbox[2], bbox[3]) if e.etype == etype]
        return [e for e in self._entities if e.etype == etype]

    def by_handle(self, handle: str) -> CadEntity | None:
        return self._by_handle.get(handle)

    def known_handles(self) -> set[str]:
        return set(self._by_handle)

    def texts_with_value(self, text: str) -> list[CadEntity]:
        wanted = (text or "").strip()
        return [e for e in self._entities if e.etype in {"TEXT", "MTEXT"} and (e.text or "").strip() == wanted]
