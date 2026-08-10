#!/usr/bin/env python3
"""Adaptadores CAD independentes para FV e LV (QA Global).

Re-derivam prova a partir de geometria e contratos no payload N1, sem confiar
no booleano/texto isolado. Isolados de LAJ/PIL: não importam regras de laje/pilar
além de consulta consultiva de existência de apoio (nome em pillars/beams).
"""
from __future__ import annotations

import hashlib
import math
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable

from scripts.arete.qa_evidence_auditor import (
    Decision,
    nearly_equal,
    parse_number,
    point_bbox,
    polygon_metrics,
    safe_list,
)


_DIM_SPLIT = re.compile(r"[xX/]")
_PILLAR_RE = re.compile(r"^P\d+", re.IGNORECASE)
_BEAM_RE = re.compile(r"^V\d+", re.IGNORECASE)


def _sha_id(*parts: str) -> str:
    return "qaev-" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _contour_points(area_link: Any) -> list:
    if not isinstance(area_link, dict):
        return []
    contour = area_link.get("contour")
    if isinstance(contour, list) and contour:
        first = contour[0]
        if isinstance(first, dict) and first.get("points"):
            return list(first.get("points") or [])
        if isinstance(first, (list, tuple)) and len(first) >= 2:
            return list(contour)
    if area_link.get("points"):
        return list(area_link.get("points") or [])
    return []


def _poly_closed_positive(points: list) -> dict | None:
    metrics = polygon_metrics(points)
    bbox = point_bbox(points)
    if not metrics or not bbox:
        return None
    area, perimeter = metrics
    if area <= 0 or perimeter <= 0:
        return None
    if (bbox[2] - bbox[0]) <= 0 or (bbox[3] - bbox[1]) <= 0:
        return None
    return {"kind": "polygon", "area": area, "perimeter": perimeter, "bbox": list(bbox), "vertices": len(points)}


def _parse_dim_pair(raw: Any) -> tuple[float, float] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    parts = [parse_number(p) for p in _DIM_SPLIT.split(text)]
    parts = [p for p in parts if p is not None]
    if len(parts) < 2:
        return None
    return float(parts[0]), float(parts[1])


def _dim_matches_bbox(dim: tuple[float, float], bbox: tuple[float, float, float, float], tol: float = 2.0) -> bool:
    """Dimensão de seção/painel vs bbox em planta.

    Aceita (1) match total ordem-insensível ou (2) a menor cota batendo com a
    menor aresta do contorno (espessura do fundo), sem exigir que a altura de
    seção iguale o comprimento axial do painel.
    """
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    declared = sorted(dim)
    observed = sorted([w, h])
    if all(nearly_equal(a, b, tol=tol) for a, b in zip(declared, observed)):
        return True
    # espessura em planta ≈ menor cota da dimensão
    return nearly_equal(declared[0], observed[0], tol=tol)


def _classified_structure_lines(beam_data: dict) -> list:
    """Linhas DXF classificadas do fundo (faces) — prova de posição no estrutural."""
    classified = (beam_data.get("geometry") or {}).get("classified") or {}
    if not isinstance(classified, dict):
        return []
    lines: list = []
    for key in ("seg_bottom", "seg_side_a", "seg_side_b"):
        for line in classified.get(key) or []:
            if isinstance(line, (list, tuple)) and len(line) >= 2:
                lines.append(line)
    return lines


def _contour_overlays_structure(
    points: list,
    structure_lines: list,
    *,
    tolerance: float = 0.75,
) -> tuple[bool, dict]:
    """True se o contorno tem borda sobre face DXF (não flutuando com tamanho certo).

    Sem faces classificadas, a prova de posição é incompleta — não autoriza
    CONFIRMAR/qa_agente (selo laranja) só por polígono fechado + bbox.
    """
    evidence: dict[str, Any] = {
        "kind": "overlay_structure",
        "faces_n": len(structure_lines),
        "tolerance_cm": tolerance,
    }
    clean: list[tuple[float, float]] = []
    for point in points or []:
        try:
            clean.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError, IndexError):
            continue
    if len(clean) < 3:
        evidence["status"] = "no_contour"
        return False, evidence
    if not structure_lines:
        evidence["status"] = "no_dxf_faces"
        return False, evidence
    xs = [p[0] for p in clean]
    ys = [p[1] for p in clean]
    is_horizontal = (max(xs) - min(xs)) >= (max(ys) - min(ys))
    evidence["is_horizontal"] = is_horizontal
    try:
        from src.core.beam_interpreters.fundo_viga import FundoVigaInterpreter
    except ImportError:
        # fallback relativo ao repo quando scripts/arete roda com sys.path curto
        from core.beam_interpreters.fundo_viga import FundoVigaInterpreter  # type: ignore
    ok = FundoVigaInterpreter.contour_overlays_boundary_lines(
        clean,
        structure_lines,
        is_horizontal=is_horizontal,
        tolerance=tolerance,
    )
    evidence["status"] = "overlay_ok" if ok else "floating_or_misaligned"
    evidence["overlay"] = ok
    return ok, evidence


@dataclass
class BeamRecord:
    id: str
    project_id: str
    name: str
    data: dict
    links: dict
    validated_fields: set[str]
    na_fields: set[str]
    is_validated: bool
    snapshot_hash: str

    @property
    def fields(self) -> dict:
        value = self.data.get("fields")
        return value if isinstance(value, dict) else {}


def _json_load(raw: Any, default: Any) -> Any:
    import json
    if raw in (None, ""):
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def beam_mutable_columns(con: sqlite3.Connection) -> list[str]:
    """Colunas mutáveis presentes em ``beams`` (sem exigir extra_data_json)."""
    existing = {row[1] for row in con.execute("PRAGMA table_info(beams)")}
    preferred = (
        "links_json", "validated_fields_json", "na_fields_json",
        "validated_link_classes_json", "na_link_classes_json", "na_reasons_json",
        "is_validated",
    )
    return [c for c in preferred if c in existing]


def beam_snapshot_hash(con: sqlite3.Connection, beam_id: str) -> str:
    """Mesmo contrato de hash usado no apply (colunas mutáveis existentes)."""
    import json
    cols = beam_mutable_columns(con)
    row = con.execute(
        f"SELECT id, {', '.join(cols)} FROM beams WHERE id=?",
        (beam_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"beam ausente: {beam_id}")
    payload = {"id": row[0]}
    for index, col in enumerate(cols, start=1):
        payload[col] = row[index]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def load_beam_records(con: sqlite3.Connection, project_id: str) -> list[BeamRecord]:
    con.row_factory = sqlite3.Row
    columns = {row[1] for row in con.execute("PRAGMA table_info(beams)")}
    select = ["id", "project_id", "name", "data_json", "is_validated"]
    for optional in (
        "links_json", "validated_fields_json", "na_fields_json",
        "validated_link_classes_json", "na_link_classes_json", "na_reasons_json",
    ):
        if optional in columns:
            select.append(optional)
    rows = con.execute(
        f"SELECT {', '.join(select)} FROM beams WHERE project_id=? ORDER BY name",
        (project_id,),
    ).fetchall()
    out: list[BeamRecord] = []
    for row in rows:
        payload = _json_load(row["data_json"], {})
        if not isinstance(payload, dict):
            payload = {}
        links = {}
        if "links_json" in row.keys() and row["links_json"]:
            links = _json_load(row["links_json"], {})
        if not isinstance(links, dict):
            links = {}
        # data_json.links tem a evidência rica FV/LV; merge sem apagar top-level links_json
        nested = payload.get("links") if isinstance(payload.get("links"), dict) else {}
        merged = dict(nested)
        for key, value in links.items():
            merged.setdefault(key, value)
        vf = _json_load(row["validated_fields_json"] if "validated_fields_json" in row.keys() else "[]", [])
        na = _json_load(row["na_fields_json"] if "na_fields_json" in row.keys() else "[]", [])
        if isinstance(vf, dict):
            vf_set = set(vf.keys())
        else:
            vf_set = set(vf or [])
        snap = beam_snapshot_hash(con, str(row["id"]))
        out.append(BeamRecord(
            id=str(row["id"]), project_id=str(row["project_id"]), name=str(row["name"] or "").strip(),
            data=payload, links=merged, validated_fields=vf_set, na_fields=set(na or []),
            is_validated=bool(row["is_validated"]), snapshot_hash=snap,
        ))
    return out


def load_name_index(con: sqlite3.Connection, project_id: str) -> dict[str, set[str]]:
    """Mapa de nomes de entidades do projeto (consulta de apoio, não semântica)."""
    con.row_factory = sqlite3.Row
    pillars = {
        str(row[0]).strip().upper()
        for row in con.execute("SELECT name FROM pillars WHERE project_id=?", (project_id,))
        if row[0]
    }
    beams = {
        str(row[0]).strip().upper()
        for row in con.execute("SELECT name FROM beams WHERE project_id=?", (project_id,))
        if row[0]
    }
    return {"PIL": pillars, "BEAM": beams}


class FvEvidenceAuditor:
    """Adaptador CAD FV: segmentos de fundo, área, dimensão e apoios locais."""

    def __init__(self, beams: list[BeamRecord], name_index: dict[str, set[str]], run_id: str):
        self.beams = beams
        self.name_index = name_index
        self.run_id = run_id
        self.findings: list[dict] = []
        self.questions: list[dict] = []

    def _decision(
        self, beam: BeamRecord, field_id: str, decision: str, confidence: str, reason: str,
        *, evidence: list[dict] | None = None, operations: list[dict] | None = None,
        requires_human: bool = False,
    ) -> Decision:
        return Decision(
            decision_id=_sha_id(self.run_id, beam.project_id, beam.name, field_id, decision, reason),
            run_id=self.run_id, project_id=beam.project_id, classe="FV", item=beam.name,
            field_id=field_id, decision=decision, confidence=confidence, reason=reason,
            evidence=evidence or [], operations=operations or [], requires_human=requires_human,
            snapshot_hash=beam.snapshot_hash,
        )

    def _ops(self, field_id: str, slots: Iterable[str] = ()) -> list[dict]:
        return [{"op": "validate_field", "field": field_id, "slots": sorted(set(slots))}]

    def _segment_indices(self, beam: BeamRecord) -> list[int]:
        indices: set[int] = set()
        bottom = (beam.links.get("viga_segs") or {}).get("seg_bottom") if isinstance(beam.links.get("viga_segs"), dict) else None
        if isinstance(bottom, list):
            for i, _ in enumerate(bottom, start=1):
                indices.add(i)
        for key in list(beam.links.keys()) + list(beam.fields.keys()):
            match = re.search(r"viga_fundo_seg_(\d+)", str(key))
            if match:
                indices.add(int(match.group(1)))
        return sorted(indices)

    def _seg_bottom(self, beam: BeamRecord, index: int) -> dict | None:
        bottom = (beam.links.get("viga_segs") or {}).get("seg_bottom") if isinstance(beam.links.get("viga_segs"), dict) else None
        if not isinstance(bottom, list) or index < 1 or index > len(bottom):
            return None
        entry = bottom[index - 1]
        return entry if isinstance(entry, dict) else None

    def _area_link(self, beam: BeamRecord, index: int) -> dict | None:
        key = f"viga_fundo_seg_{index}_area_segs"
        value = beam.links.get(key)
        return value if isinstance(value, dict) else None

    def _audit_name(self, beam: BeamRecord) -> Decision:
        field_name = str(beam.fields.get("nome") or beam.fields.get("name") or beam.name).strip().upper()
        if beam.name.upper() == field_name:
            ops = [] if "name" in beam.validated_fields else self._ops("name")
            return self._decision(beam, "name", "CONFIRMAR", "high", "nome do registro e campo coerentes", operations=ops)
        return self._decision(beam, "name", "REVISAR_HUMANO", "low", "nome diverge do campo", requires_human=True)

    def _audit_segment(self, beam: BeamRecord, index: int) -> list[Decision]:
        decisions: list[Decision] = []
        area = self._area_link(beam, index)
        seg = self._seg_bottom(beam, index)
        points = _contour_points(area) if area else []
        if not points and seg:
            points = list(seg.get("points") or [])
        geom = _poly_closed_positive(points)
        exists_field = f"viga_fundo_seg_{index}_exists"
        area_field = f"viga_fundo_seg_{index}_area_segs"
        dim_field = f"viga_fundo_seg_{index}_dim"
        ini_field = f"viga_fundo_seg_{index}_local_ini"
        fim_field = f"viga_fundo_seg_{index}_local_fim"

        structure_lines = _classified_structure_lines(beam.data)
        overlay_ok, overlay_ev = _contour_overlays_structure(points, structure_lines)

        if geom and overlay_ok:
            ops = [] if exists_field in beam.validated_fields else self._ops(exists_field)
            decisions.append(self._decision(
                beam, exists_field, "CONFIRMAR", "high",
                f"segmento {index}: polígono fechado com borda sobre face DXF classificada "
                f"(posição no estrutural, não só área positiva)",
                operations=ops, evidence=[geom, overlay_ev],
            ))
            ops_a = [] if area_field in beam.validated_fields else self._ops(area_field, ["contour"])
            decisions.append(self._decision(
                beam, area_field, "CONFIRMAR", "high",
                f"segmento {index}: area_segs alinhada/posicionada sobre linhas estruturais "
                f"(checklist N1-V contorno_posicao_sobre_estrutural)",
                operations=ops_a, evidence=[geom, overlay_ev],
            ))
        elif geom and not overlay_ok:
            # Tamanho certo + flutuando: NÃO autoriza qa_agente / selo laranja.
            status = overlay_ev.get("status") or "misaligned"
            reason_pos = (
                f"segmento {index}: contorno calculável mas SEM borda sobre face DXF "
                f"({status}) — posição/alinhamento no estrutural obrigatório para 🟠; "
                f"largura/área isoladas não bastam"
            )
            decisions.append(self._decision(
                beam, exists_field, "PENDENTE", "medium",
                reason_pos, evidence=[geom, overlay_ev],
            ))
            decisions.append(self._decision(
                beam, area_field, "PENDENTE", "medium",
                reason_pos, evidence=[geom, overlay_ev],
            ))
        else:
            decisions.append(self._decision(
                beam, exists_field, "PENDENTE", "low",
                f"segmento {index}: sem polígono fechado de área positiva em area_segs/seg_bottom",
            ))
            if area or seg:
                decisions.append(self._decision(
                    beam, area_field, "PENDENTE", "low",
                    f"segmento {index}: geometria de área insuficiente para prova CAD",
                ))

        dim_raw = beam.fields.get(dim_field) or beam.fields.get(f"viga_fundo_seg_{index}_dim")
        dim_pair = _parse_dim_pair(dim_raw)
        bbox = point_bbox(points) if points else None
        if dim_pair and bbox and _dim_matches_bbox(dim_pair, bbox, tol=5.0) and overlay_ok:
            ops = [] if dim_field in beam.validated_fields else self._ops(dim_field)
            decisions.append(self._decision(
                beam, dim_field, "CONFIRMAR", "high",
                f"segmento {index}: dimensão {dim_raw} coerente com bbox e contorno ancorado no estrutural",
                operations=ops,
                evidence=[
                    {"kind": "dim_vs_bbox", "dim": list(dim_pair), "bbox": list(bbox)},
                    overlay_ev,
                ],
            ))
        elif dim_pair and bbox and _dim_matches_bbox(dim_pair, bbox, tol=5.0) and not overlay_ok:
            decisions.append(self._decision(
                beam, dim_field, "PENDENTE", "medium",
                f"segmento {index}: dimensão {dim_raw} bate no contorno, mas contorno não está "
                f"sobre faces DXF — sem prova de posição, 🟠 bloqueado",
                evidence=[
                    {"kind": "dim_vs_bbox", "dim": list(dim_pair), "bbox": list(bbox)},
                    overlay_ev,
                ],
            ))
        elif dim_pair and bbox:
            decisions.append(self._decision(
                beam, dim_field, "PENDENTE", "medium",
                f"segmento {index}: dimensão {dim_raw} não bate com bbox {list(bbox)} na tolerância",
                evidence=[{"kind": "dim_vs_bbox", "dim": list(dim_pair), "bbox": list(bbox)}],
            ))
        elif dim_raw:
            decisions.append(self._decision(
                beam, dim_field, "PENDENTE", "low",
                f"segmento {index}: dimensão presente sem geometria comparável",
            ))

        for field_id, role in ((ini_field, "ini"), (fim_field, "fim")):
            support = str(beam.fields.get(field_id) or "").strip()
            if not support:
                continue
            ok = self._support_exists(support)
            if ok:
                ops = [] if field_id in beam.validated_fields else self._ops(field_id)
                decisions.append(self._decision(
                    beam, field_id, "CONFIRMAR", "high",
                    f"segmento {index} local_{role}: entidade {support} existe no projeto (consulta de identidade)",
                    operations=ops, evidence=[{"kind": "support_identity", "name": support, "role": role}],
                ))
            else:
                decisions.append(self._decision(
                    beam, field_id, "PENDENTE", "low",
                    f"segmento {index} local_{role}: entidade {support} não encontrada em pillars/beams do projeto",
                ))
        return decisions

    def _support_exists(self, name: str) -> bool:
        key = name.strip().upper()
        if _PILLAR_RE.match(key):
            return key in self.name_index.get("PIL", set())
        if _BEAM_RE.match(key):
            return key in self.name_index.get("BEAM", set())
        return key in self.name_index.get("PIL", set()) or key in self.name_index.get("BEAM", set())

    def _fundo_bboxes(self, beam: BeamRecord) -> list[tuple[float, float, float, float]]:
        boxes: list[tuple[float, float, float, float]] = []
        for index in self._segment_indices(beam):
            area = self._area_link(beam, index)
            seg = self._seg_bottom(beam, index)
            points = _contour_points(area) if area else []
            if not points and seg:
                points = list(seg.get("points") or [])
            bbox = point_bbox(points)
            if bbox:
                boxes.append(bbox)
        return boxes

    def _point_near_any_bbox(
        self,
        pos: Any,
        boxes: list[tuple[float, float, float, float]],
        tol: float = 80.0,
    ) -> dict | None:
        if not isinstance(pos, (list, tuple)) or len(pos) < 2 or not boxes:
            return None
        try:
            x, y = float(pos[0]), float(pos[1])
        except (TypeError, ValueError):
            return None
        best = None
        best_d = None
        for bbox in boxes:
            # distância ao retângulo
            dx = max(bbox[0] - x, 0.0, x - bbox[2])
            dy = max(bbox[1] - y, 0.0, y - bbox[3])
            d = (dx * dx + dy * dy) ** 0.5
            if best_d is None or d < best_d:
                best_d = d
                best = {"x": x, "y": y, "distance": round(d, 3), "bbox": list(bbox)}
        if best is not None and best_d is not None and best_d <= tol:
            return best
        return None

    def _entry_geometry(self, entry: dict) -> dict | None:
        """Extrai polígono fechado ou ponto com prova mínima de furo/recorte.

        Aceita points/contour/poly/geometry.poly; se houver polígono válido,
        anexa centróide para âncora near_fundo mesmo sem `pos` explícito.
        """
        pts = (
            entry.get("points")
            or entry.get("contour")
            or entry.get("poly")
            or ((entry.get("geometry") or {}).get("poly") if isinstance(entry.get("geometry"), dict) else None)
        )
        if isinstance(pts, list) and pts:
            if pts and isinstance(pts[0], dict) and pts[0].get("points"):
                pts = pts[0].get("points")
            poly = _poly_closed_positive(list(pts))
            if poly:
                try:
                    xs = [float(p[0]) for p in pts]
                    ys = [float(p[1]) for p in pts]
                    poly["centroid"] = [sum(xs) / len(xs), sum(ys) / len(ys)]
                except (TypeError, ValueError, IndexError, ZeroDivisionError):
                    pass
                return {"kind": "polygon_hole", **poly}
            bbox = point_bbox(pts)
            if bbox:
                return {
                    "kind": "polyline_bbox",
                    "bbox": list(bbox),
                    "centroid": [
                        (bbox[0] + bbox[2]) / 2.0,
                        (bbox[1] + bbox[3]) / 2.0,
                    ],
                }
        pos = entry.get("pos") or entry.get("point") or entry.get("anchor")
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            try:
                return {"kind": "anchor_point", "pos": [float(pos[0]), float(pos[1])]}
            except (TypeError, ValueError):
                return None
        return None

    def _audit_cortes(self, beam: BeamRecord) -> Decision:
        """possui_corte + links.cortes — preferir polígono; ponto só com contexto."""
        possui = beam.fields.get("possui_corte")
        if possui is None and "possui_corte" not in beam.fields:
            possui = beam.data.get("possui_corte")
        cortes = beam.links.get("cortes")
        entries = safe_list(cortes) if not isinstance(cortes, dict) else [
            item for value in cortes.values() for item in safe_list(value)
        ]
        poly_entries = []
        weak_entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            geom = self._entry_geometry(entry)
            if not geom:
                continue
            if geom["kind"] == "polygon_hole":
                poly_entries.append(geom)
            else:
                weak_entries.append(geom)
        if poly_entries:
            ops = [] if "cortes" in beam.validated_fields else self._ops("cortes")
            return self._decision(
                beam, "cortes", "CONFIRMAR", "high",
                f"{len(poly_entries)} corte(s)/furo(s) com polígono fechado de área positiva",
                operations=ops,
                evidence=poly_entries[:16],
            )
        if weak_entries and possui is not False:
            return self._decision(
                beam, "cortes", "PENDENTE", "medium",
                f"{len(weak_entries)} corte(s) só com ponto/bbox fraco — falta polígono de furo",
                evidence=weak_entries[:16],
            )
        if possui is True and not poly_entries:
            return self._decision(
                beam, "cortes", "PENDENTE", "medium",
                "possui_corte=true mas links.cortes sem polígono de furo",
            )
        if "cortes" in beam.na_fields or possui is False or not entries:
            ops = [{"op": "mark_na", "field": "cortes", "reason": "sem cortes/recortes com geometria no N1"}]
            if "cortes" in beam.na_fields:
                ops = []
            return self._decision(
                beam, "cortes", "N/A_CONFIRMADO", "high",
                "sem cortes/recortes geométricos no snapshot N1",
                operations=ops,
            )
        return self._decision(beam, "cortes", "PENDENTE", "low", "cortes presentes sem prova geométrica clara")

    def _audit_aberturas(self, beam: BeamRecord) -> list[Decision]:
        """links.aberturas.* — identidade + âncora espacial vs segmentos de fundo."""
        decisions: list[Decision] = []
        aberturas = beam.links.get("aberturas")
        if not isinstance(aberturas, dict) or not any(aberturas.values()):
            ops = [{"op": "mark_na", "field": "aberturas", "reason": "sem aberturas nomeadas no N1"}]
            if "aberturas" in beam.na_fields:
                ops = []
            decisions.append(self._decision(
                beam, "aberturas", "N/A_CONFIRMADO", "high",
                "sem aberturas nomeadas no snapshot N1",
                operations=ops,
            ))
            return decisions
        named: list[dict] = []
        missing: list[str] = []
        far: list[str] = []
        boxes = self._fundo_bboxes(beam)
        for kind, entries in aberturas.items():
            for entry in safe_list(entries):
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name") or entry.get("text") or "").strip().upper()
                if not name:
                    continue
                ok = self._support_exists(name)
                geom = self._entry_geometry(entry)
                anchor = entry.get("pos") or entry.get("point") or entry.get("anchor")
                if not anchor and isinstance(geom, dict):
                    anchor = geom.get("centroid") or geom.get("pos")
                near = self._point_near_any_bbox(anchor, boxes) if anchor else None
                rec = {
                    "kind": kind, "name": name, "exists": ok,
                    "geom": geom, "near_fundo": near,
                }
                named.append(rec)
                if not ok:
                    missing.append(name)
                elif anchor and boxes and near is None:
                    far.append(name)
        if named and not missing and not far:
            ops = [] if "aberturas" in beam.validated_fields else self._ops("aberturas", list(aberturas.keys()))
            poly_n = sum(1 for n in named if (n.get("geom") or {}).get("kind") == "polygon_hole")
            decisions.append(self._decision(
                beam, "aberturas", "CONFIRMAR", "high",
                f"{len(named)} abertura(s): entidade existe"
                + (f"; {poly_n} com polígono" if poly_n else "; âncora pos próxima ao fundo"),
                operations=ops, evidence=named[:32],
            ))
        elif named and missing:
            decisions.append(self._decision(
                beam, "aberturas", "PENDENTE", "medium",
                f"aberturas com entidade ausente no projeto: {sorted(set(missing))[:8]}",
                evidence=named[:32],
            ))
        elif named and far:
            decisions.append(self._decision(
                beam, "aberturas", "PENDENTE", "medium",
                f"aberturas com pos longe do contorno de fundo: {sorted(set(far))[:8]}",
                evidence=named[:32],
            ))
        else:
            decisions.append(self._decision(
                beam, "aberturas", "PENDENTE", "low",
                "bloco aberturas sem nomes rastreáveis",
            ))
        return decisions

    def audit(self, selected: set[str] | None = None, include_sealed: bool = False) -> list[Decision]:
        decisions: list[Decision] = []
        for beam in self.beams:
            if selected and beam.name not in selected:
                continue
            if beam.is_validated and not include_sealed:
                continue
            # Só audita itens com evidência de fundo (evita LV-puro sem segmentos)
            indices = self._segment_indices(beam)
            if not indices and not any(str(k).startswith("viga_fundo") for k in beam.fields):
                continue
            decisions.append(self._audit_name(beam))
            for index in indices:
                decisions.extend(self._audit_segment(beam, index))
            decisions.append(self._audit_cortes(beam))
            decisions.extend(self._audit_aberturas(beam))
        return decisions


class LvEvidenceAuditor:
    """Adaptador CAD LV: identidade, dims por lado e 4 contratos PARA/PASSA × A/B."""

    def __init__(self, beams: list[BeamRecord], name_index: dict[str, set[str]], run_id: str):
        self.beams = beams
        self.name_index = name_index
        self.run_id = run_id
        self.findings: list[dict] = []
        self.questions: list[dict] = []

    def _decision(
        self, beam: BeamRecord, field_id: str, decision: str, confidence: str, reason: str,
        *, evidence: list[dict] | None = None, operations: list[dict] | None = None,
        requires_human: bool = False,
    ) -> Decision:
        return Decision(
            decision_id=_sha_id(self.run_id, beam.project_id, beam.name, field_id, decision, reason),
            run_id=self.run_id, project_id=beam.project_id, classe="LV", item=beam.name,
            field_id=field_id, decision=decision, confidence=confidence, reason=reason,
            evidence=evidence or [], operations=operations or [], requires_human=requires_human,
            snapshot_hash=beam.snapshot_hash,
        )

    def _ops(self, field_id: str) -> list[dict]:
        return [{"op": "validate_field", "field": field_id, "slots": []}]

    def _contracts(self, beam: BeamRecord) -> dict:
        value = beam.data.get("lv_generation_contracts")
        if isinstance(value, dict):
            return value
        nested = (beam.links or {}).get("lv_generation_contracts")
        return nested if isinstance(nested, dict) else {}

    def _audit_name(self, beam: BeamRecord) -> Decision:
        field_name = str(beam.fields.get("nome") or beam.fields.get("name") or beam.name).strip().upper()
        if beam.name.upper() == field_name:
            ops = [] if "name" in beam.validated_fields else self._ops("name")
            return self._decision(beam, "name", "CONFIRMAR", "high", "nome do registro e campo coerentes", operations=ops)
        return self._decision(beam, "name", "REVISAR_HUMANO", "low", "nome diverge do campo", requires_human=True)

    def _audit_side_dim(self, beam: BeamRecord, side: str) -> Decision:
        field_id = f"viga_{side.lower()}_seg_1_dim"
        raw = beam.fields.get(field_id)
        pair = _parse_dim_pair(raw)
        if pair:
            ops = [] if field_id in beam.validated_fields else self._ops(field_id)
            return self._decision(
                beam, field_id, "CONFIRMAR", "high",
                f"dimensão própria do lado {side} presente e parseável (não espelhada de FV)",
                operations=ops, evidence=[{"kind": "side_dim", "side": side, "dim": list(pair)}],
            )
        return self._decision(beam, field_id, "PENDENTE", "low", f"dimensão do lado {side} ausente ou ilegível")

    def _audit_contract(self, beam: BeamRecord, behavior: str, side: str) -> Decision:
        contracts = self._contracts(beam)
        node = ((contracts.get(behavior) or {}).get(side) if isinstance(contracts.get(behavior), dict) else None)
        field_id = f"lv_contract_{behavior.upper()}_{side}"
        expected_id = f"LV_{side}_{behavior.upper()}"
        if not isinstance(node, dict):
            return self._decision(beam, field_id, "PENDENTE", "low", f"contrato {behavior}/{side} ausente")
        cid = str(node.get("contract_id") or "")
        got_side = str(node.get("side") or "").upper()
        got_behavior = str(node.get("behavior") or "").upper()
        ready = bool(node.get("generation_ready"))
        meta = node.get("_sa_meta") if isinstance(node.get("_sa_meta"), dict) else {}
        isolated = meta.get("behavior_isolated")
        fv_fallback = meta.get("fv_dimension_fallback")
        segs = node.get("structural_segments") if isinstance(node.get("structural_segments"), list) else []
        source_keys = [str(s.get("source_key") or "") for s in segs if isinstance(s, dict)]
        source_slots = [str(s.get("source_slot") or "") for s in segs if isinstance(s, dict)]
        expected_slot = f"seg_side_{side.lower()}"
        key_pat = (
            re.compile(rf"^viga_{side.lower()}_seg_\d+_comprimento_total$")
            if behavior.lower() == "para"
            else re.compile(rf"^viga_{side.lower()}_seg_\d+_comp_total_passa$")
        )
        keys_ok = bool(source_keys) and all(key_pat.match(k) for k in source_keys)
        slots_ok = bool(source_slots) and all(s == expected_slot for s in source_slots)
        geom_ok = False
        geom_evidence = []
        for seg in segs:
            if not isinstance(seg, dict):
                continue
            pts = seg.get("points") or []
            bbox = point_bbox(pts)
            if bbox and (bbox[2] - bbox[0] > 0 or bbox[3] - bbox[1] > 0):
                geom_ok = True
                geom_evidence.append({"source_key": seg.get("source_key"), "bbox": list(bbox)})
        ok = (
            cid == expected_id
            and got_side == side
            and got_behavior in {behavior.upper(), behavior.capitalize(), behavior}
            and ready
            and keys_ok
            and slots_ok
            and isolated is not False
            and fv_fallback is not True
        )
        if ok and (geom_ok or not segs):
            ops = [] if field_id in beam.validated_fields else self._ops(field_id)
            return self._decision(
                beam, field_id, "CONFIRMAR", "high",
                f"contrato {cid}: side/behavior/ready/source_key/slot e isolamento OK"
                + ("; geometria estrutural presente" if geom_ok else "; sem segs estruturais para provar geometria"),
                operations=ops,
                evidence=[{
                    "kind": "lv_contract", "contract_id": cid, "side": got_side,
                    "behavior": got_behavior, "generation_ready": ready,
                    "behavior_isolated": isolated, "fv_dimension_fallback": fv_fallback,
                    "source_keys": source_keys, "source_slots": source_slots,
                    "geometry": geom_evidence,
                }],
            )
        return self._decision(
            beam, field_id, "PENDENTE", "medium",
            f"contrato {behavior}/{side} incompleto ou inconsistente "
            f"(id={cid!r}, side={got_side!r}, behavior={got_behavior!r}, ready={ready}, "
            f"keys_ok={keys_ok}, slots_ok={slots_ok}, isolated={isolated}, fv_fallback={fv_fallback})",
            evidence=[{"kind": "lv_contract_raw", "node_keys": sorted(node.keys())}],
        )

    def _audit_support(self, beam: BeamRecord) -> Decision | None:
        for key in ("viga_a_seg_1_end_name", "viga_a_seg_1_ini_name", "viga_b_seg_1_end_name", "viga_b_seg_1_ini_name"):
            name = str(beam.fields.get(key) or "").strip()
            if not name:
                continue
            key_u = name.upper()
            exists = key_u in self.name_index.get("PIL", set()) or key_u in self.name_index.get("BEAM", set())
            if exists:
                ops = [] if key in beam.validated_fields else self._ops(key)
                return self._decision(
                    beam, key, "CONFIRMAR", "high",
                    f"apoio/extremo {name} existe no projeto",
                    operations=ops, evidence=[{"kind": "support_identity", "name": name}],
                )
            return self._decision(
                beam, key, "PENDENTE", "low",
                f"apoio/extremo {name} não encontrado no projeto",
            )
        return None

    def _opening_bases(self, beam: BeamRecord) -> dict[str, dict[str, Any]]:
        """Agrupa viga_[ab]_seg_N_abert_pilar_(esq|dir)(+_dist|_larg)."""
        bases: dict[str, dict[str, Any]] = {}
        pattern = re.compile(
            r"^(viga_[ab]_seg_\d+_abert_pilar_(?:esq|dir))(?:_(dist|larg))?$",
            re.IGNORECASE,
        )
        for key, value in beam.fields.items():
            match = pattern.match(str(key))
            if not match:
                continue
            base = match.group(1)
            kind = match.group(2) or "flag"
            bases.setdefault(base, {})[kind] = value
            # label de identidade no links
            link = beam.links.get(base)
            if isinstance(link, dict) and "label" not in bases[base]:
                labels = safe_list(link.get("label"))
                if labels and isinstance(labels[0], dict):
                    bases[base]["label"] = str(labels[0].get("name") or labels[0].get("text") or "").strip()
        return bases

    def _audit_openings(self, beam: BeamRecord) -> list[Decision]:
        decisions: list[Decision] = []
        bases = self._opening_bases(beam)
        if not bases:
            return decisions
        for base, parts in sorted(bases.items()):
            dist = parse_number(parts.get("dist"))
            larg = parse_number(parts.get("larg"))
            label = str(parts.get("label") or "").strip()
            # slot vazio / nulo em todos os componentes → N/A
            if dist is None and larg is None and not label and parts.get("flag") in (None, "", False):
                continue
            if dist is None and larg is None:
                # campos presentes mas nulos
                if all(parts.get(k) in (None, "") for k in ("dist", "larg", "flag")):
                    ops = [{"op": "mark_na", "field": base, "reason": "abertura sem dist/larg no N1"}]
                    if base in beam.na_fields:
                        ops = []
                    decisions.append(self._decision(
                        beam, base, "N/A_CONFIRMADO", "high",
                        "abertura sem dist/larg materializados",
                        operations=ops,
                    ))
                    continue
            label_ok = True
            if label:
                key_u = label.upper()
                label_ok = key_u in self.name_index.get("PIL", set()) or key_u in self.name_index.get("BEAM", set())
            measures_ok = dist is not None and larg is not None and larg > 0 and dist >= 0
            if measures_ok and label_ok:
                ops = [] if base in beam.validated_fields else self._ops(base)
                decisions.append(self._decision(
                    beam, base, "CONFIRMAR", "high",
                    f"abertura {base}: dist={dist} larg={larg}"
                    + (f" entidade {label}" if label else " (sem rótulo de entidade)"),
                    operations=ops,
                    evidence=[{
                        "kind": "lv_opening", "base": base, "dist": dist, "larg": larg,
                        "label": label or None, "label_ok": label_ok,
                    }],
                ))
            elif measures_ok and not label_ok:
                decisions.append(self._decision(
                    beam, base, "PENDENTE", "medium",
                    f"abertura {base} com medidas ok mas entidade {label!r} ausente no projeto",
                ))
            else:
                decisions.append(self._decision(
                    beam, base, "PENDENTE", "low",
                    f"abertura {base}: medidas incompletas (dist={parts.get('dist')!r}, larg={parts.get('larg')!r})",
                ))
        return decisions

    def audit(self, selected: set[str] | None = None, include_sealed: bool = False) -> list[Decision]:
        decisions: list[Decision] = []
        for beam in self.beams:
            if selected and beam.name not in selected:
                continue
            if beam.is_validated and not include_sealed:
                continue
            has_lv = bool(self._contracts(beam)) or any(
                str(k).startswith(("viga_a_", "viga_b_", "lv_")) for k in beam.fields
            )
            if not has_lv:
                continue
            decisions.append(self._audit_name(beam))
            decisions.append(self._audit_side_dim(beam, "A"))
            decisions.append(self._audit_side_dim(beam, "B"))
            for behavior in ("Para", "Passa"):
                for side in ("A", "B"):
                    decisions.append(self._audit_contract(beam, behavior, side))
            support = self._audit_support(beam)
            if support:
                decisions.append(support)
            decisions.extend(self._audit_openings(beam))
        return decisions
