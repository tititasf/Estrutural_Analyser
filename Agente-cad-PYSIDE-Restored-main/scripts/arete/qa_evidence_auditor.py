#!/usr/bin/env python3
"""Auditor CLI de evidências do Structural Analyzer.

Primeiro adaptador: LAJ. O comando ``audit`` é read-only e produz decisões,
achados, perguntas e operações propostas. ``apply`` executa somente operações
de alta confiança do mesmo snapshot, dentro de uma transação e com rollback
append-only. Nenhuma regra usa identificador de item, obra ou pavimento.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sqlite3
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DB = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_ROOT = REPO_ROOT / "scripts" / "arete" / "relatorios" / "qa_evidencias"
REQUIRED_LAJ_FIELDS = (
    "name",
    "laje_dim",
    "laje_visao_corte",
    "laje_vizinhas_niveis",
    "laje_pilares_apoio",
    "laje_nivel",
    "laje_outline_segs",
    "laje_islands",
)
MUTABLE_COLUMNS = (
    "links_json",
    "validated_fields_json",
    "na_fields_json",
    "validated_link_classes_json",
    "na_link_classes_json",
    "na_reasons_json",
    "extra_data_json",
    "is_validated",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_load(raw: Any, default: Any) -> Any:
    if raw in (None, ""):
        return copy.deepcopy(default)
    if isinstance(raw, (dict, list)):
        return copy.deepcopy(raw)
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return copy.deepcopy(default)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_number(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.upper() in {"N/A", "NULO", "POLYLINE"}:
        return None
    if re.match(r"^[HhDd]\s*[:=]?", text):
        return None
    match = re.search(r"[+-]?\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def fmt_number(value: float) -> str:
    text = f"{float(value):.2f}"
    return text.rstrip("0").rstrip(".")


def nearly_equal(a: float | None, b: float | None, tol: float = 0.05) -> bool:
    return a is not None and b is not None and abs(a - b) <= tol


def safe_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def point_bbox(points: Iterable) -> tuple[float, float, float, float] | None:
    pts = list(points or [])
    if len(pts) < 2:
        return None
    try:
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
    except (TypeError, ValueError, IndexError):
        return None
    return min(xs), min(ys), max(xs), max(ys)


def bbox_distance(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def link_fingerprint(link: dict) -> str:
    payload = {
        key: link.get(key)
        for key in (
            "text", "role", "source", "source_slab", "source_direction",
            "distance_to_slab", "points", "ficha",
        )
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass
class Slab:
    id: str
    project_id: str
    name: str
    points: list
    links: dict
    validated_fields: set[str]
    na_fields: set[str]
    validated_link_classes: dict
    na_link_classes: dict
    na_reasons: dict
    extra: dict
    is_validated: bool
    raw_columns: dict[str, Any]

    @property
    def fields(self) -> dict:
        fields = self.extra.setdefault("fields", {})
        return fields if isinstance(fields, dict) else {}

    @property
    def bbox(self) -> tuple[float, float, float, float] | None:
        return point_bbox(self.points)

    @property
    def snapshot_hash(self) -> str:
        payload = {"id": self.id, **self.raw_columns}
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass
class Decision:
    decision_id: str
    run_id: str
    project_id: str
    classe: str
    item: str
    field_id: str
    decision: str
    confidence: str
    reason: str
    evidence: list[dict] = field(default_factory=list)
    operations: list[dict] = field(default_factory=list)
    rule_codes: list[str] = field(default_factory=list)
    requires_human: bool = False
    snapshot_hash: str = ""


class LajEvidenceAuditor:
    def __init__(self, slabs: list[Slab], run_id: str, consultive_context: dict[str, dict] | None = None):
        self.slabs = slabs
        self.by_name = {slab.name: slab for slab in slabs}
        self.run_id = run_id
        self.consultive_context = consultive_context or {}
        self.levels: dict[str, float] = {}
        self.level_reasons: dict[str, str] = {}
        self.findings: list[dict] = []
        self.questions: list[dict] = []
        self.sealed_level_conflicts: dict[str, list[dict]] = {
            slab.name: conflicts
            for slab in slabs
            if slab.is_validated and (conflicts := self._level_conflicts(slab))
        }
        self.blocked_level_sources: set[str] = set()
        self.trusted_level_layers = self._learn_trusted_level_layers()
        self.corroborated_level_clusters = self._build_corroborated_level_clusters()
        self.unresolved_level_sources = {
            slab.name for slab in slabs
            if slab.name in self.sealed_level_conflicts and not self._sealed_level_autocorrection(slab)
        }
        self._resolve_levels()

    def _new_decision(
        self,
        slab: Slab,
        field_id: str,
        decision: str,
        confidence: str,
        reason: str,
        *,
        evidence: list[dict] | None = None,
        operations: list[dict] | None = None,
        rule_codes: list[str] | None = None,
        requires_human: bool = False,
    ) -> Decision:
        key = f"{self.run_id}|{slab.project_id}|{slab.name}|{field_id}|{decision}|{reason}"
        decision_id = "qaev-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return Decision(
            decision_id=decision_id,
            run_id=self.run_id,
            project_id=slab.project_id,
            classe="LAJ",
            item=slab.name,
            field_id=field_id,
            decision=decision,
            confidence=confidence,
            reason=reason,
            evidence=evidence or [],
            operations=operations or [],
            rule_codes=rule_codes or [],
            requires_human=requires_human,
            snapshot_hash=slab.snapshot_hash,
        )

    def _add_finding(self, slab: Slab, field_id: str, code: str, message: str, evidence: list[dict]) -> None:
        key = f"{slab.project_id}|{slab.name}|{field_id}|{code}|{message}"
        self.findings.append({
            "finding_id": "qaev-f-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
            "run_id": self.run_id,
            "project_id": slab.project_id,
            "classe": "LAJ",
            "item": slab.name,
            "field_id": field_id,
            "code": code,
            "message": message,
            "evidence": evidence,
        })

    def _add_question(
        self,
        slab: Slab,
        field_id: str,
        code: str,
        question: str,
        evidence: list[dict],
        *,
        reasoning: dict | None = None,
    ) -> None:
        key = f"{slab.project_id}|{slab.name}|{field_id}|{code}|{question}"
        self.questions.append({
            "question_id": "qaev-q-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
            "run_id": self.run_id,
            "project_id": slab.project_id,
            "classe": "LAJ",
            "item": slab.name,
            "field_id": field_id,
            "code": code,
            "question": question,
            "evidence": evidence,
            "reasoning": reasoning or {
                "observed": evidence,
                "attempted": [],
                "rejected": [],
                "impasse": "Evidência insuficiente para mutação automática.",
                "requested_rule": "Informe a regra geral que diferencia este caso.",
            },
        })

    def _own_level_labels(self, slab: Slab) -> list[dict]:
        return [x for x in safe_list((slab.links.get("laje_nivel") or {}).get("label")) if isinstance(x, dict)]

    def _declared_level(self, slab: Slab) -> float | None:
        return parse_number(slab.fields.get("laje_nivel"))

    def _root_level(self, slab: Slab) -> float | None:
        return parse_number(slab.extra.get("laje_nivel"))

    def _learn_trusted_level_layers(self) -> set[str]:
        layers: set[str] = set()
        for slab in self.slabs:
            if not slab.is_validated or "laje_nivel" not in slab.validated_fields:
                continue
            if slab.name in self.sealed_level_conflicts:
                continue
            field_value = self._declared_level(slab)
            if field_value is None:
                continue
            for label in self._own_level_labels(slab):
                label_value = parse_number(label.get("text"))
                layer = label.get("layer")
                if bool(label.get("validated")) and layer is not None and nearly_equal(field_value, label_value):
                    layers.add(str(layer))
        return layers

    def _build_corroborated_level_clusters(self) -> dict[str, dict]:
        """Agrupa níveis provados por mais de uma fonte no corpus atual.

        O agrupamento é por valor tolerante e conta lajes, não rótulos: assim a
        repetição do mesmo texto numa única ficha não cria falsa maioria.
        """
        clusters: list[dict] = []
        for slab in self.slabs:
            field_value = self._declared_level(slab)
            root_value = self._root_level(slab)
            labels = [parse_number(x.get("text")) for x in self._own_level_labels(slab)]
            labels = [value for value in labels if value is not None]
            candidate = None
            if root_value is not None and any(nearly_equal(root_value, value) for value in labels):
                candidate = root_value
            elif field_value is not None and root_value is not None and nearly_equal(field_value, root_value):
                candidate = field_value
            if candidate is None:
                continue
            cluster = next((x for x in clusters if nearly_equal(x["value"], candidate)), None)
            if cluster is None:
                cluster = {"value": candidate, "slabs": set()}
                clusters.append(cluster)
            cluster["slabs"].add(slab.name)
        return {
            fmt_number(cluster["value"]): {
                "value": cluster["value"],
                "slabs": sorted(cluster["slabs"]),
                "count": len(cluster["slabs"]),
            }
            for cluster in clusters
        }

    def _cluster_for_level(self, value: float | None) -> dict | None:
        if value is None:
            return None
        return next(
            (cluster for cluster in self.corroborated_level_clusters.values() if nearly_equal(cluster["value"], value)),
            None,
        )

    def _neighbor_dependents(self, source_name: str) -> list[dict]:
        dependents = []
        for slab in self.slabs:
            neighbor_links = slab.links.get("laje_vizinhas_niveis") or {}
            for slot, entries in neighbor_links.items():
                for link in safe_list(entries):
                    if (
                        isinstance(link, dict)
                        and link.get("source") == "orthogonal_neighbor_identity"
                        and str(link.get("source_slab") or "").upper() == source_name.upper()
                    ):
                        dependents.append({"item": slab.name, "slot": slot})
                        break
        return dependents

    def _consultive_pillar_level_consensus(self, slab: Slab) -> dict | None:
        """Usa PIL apenas como prova auxiliar quando há contato e consenso.

        PIL não transfere campo para LAJ. O consenso só desempata um conflito
        já existente de LAJ quando dois ou mais pilares tocam seu contorno e
        convergem no mesmo nível. FV/LV são preservados no contexto para a
        explicação, mas não têm semântica suficiente para promover nível.
        """
        context = self.consultive_context.get(slab.name) or {}
        pillars = context.get("pillars") or []
        tol = self._geometry_tolerance(slab)
        groups: list[dict] = []
        for pillar in pillars:
            value = parse_number(pillar.get("level"))
            distance = pillar.get("distance")
            if value is None or distance is None or float(distance) > tol:
                continue
            group = next((x for x in groups if nearly_equal(x["value"], value)), None)
            if group is None:
                group = {"value": value, "pillars": []}
                groups.append(group)
            group["pillars"].append(pillar)
        if len(groups) != 1 or len(groups[0]["pillars"]) < 2:
            return None
        return {
            "value": groups[0]["value"],
            "pillars": groups[0]["pillars"],
            "beam_context": context.get("beams") or [],
        }

    def _sealed_level_cross_class_correction(self, slab: Slab) -> dict | None:
        current = self._declared_level(slab)
        root = self._root_level(slab)
        consensus = self._consultive_pillar_level_consensus(slab)
        if current is None or root is None or consensus is None:
            return None
        if nearly_equal(current, consensus["value"]) or not nearly_equal(root, consensus["value"]):
            return None
        return {"current": current, "expected": consensus["value"], **consensus}

    def _sealed_level_autocorrection(self, slab: Slab) -> dict | None:
        """Retorna correção somente quando o campo é outlier não corroborado.

        A regra não depende de item/pavimento: root e rótulo precisam concordar,
        o valor proposto precisa aparecer em pelo menos duas lajes corroboradas e
        o valor atual não pode pertencer a nenhum grupo corroborado.
        """
        current = self._declared_level(slab)
        root = self._root_level(slab)
        labels = [parse_number(x.get("text")) for x in self._own_level_labels(slab)]
        labels = [value for value in labels if value is not None]
        if current is None or root is None or not any(nearly_equal(root, value) for value in labels):
            return None
        expected_cluster = self._cluster_for_level(root)
        current_cluster = self._cluster_for_level(current)
        if (
            expected_cluster is None
            or expected_cluster["count"] < 2
            or current_cluster is not None
            or abs(current - root) < 1.0
        ):
            return None
        return {
            "expected": root,
            "current": current,
            "expected_cluster": expected_cluster,
            "current_cluster": current_cluster,
            "labels": [fmt_number(value) for value in labels],
        }

    def _direct_level_anchor(self, slab: Slab) -> tuple[float, str] | None:
        field_value = self._declared_level(slab)
        labels = self._own_level_labels(slab)
        direct = [x for x in labels if not x.get("source") and parse_number(x.get("text")) is not None]
        for label in direct:
            value = parse_number(label.get("text"))
            text = str(label.get("text") or "").strip()
            semantic = " ".join(str(label.get(key) or "") for key in ("role", "label")).lower()
            layer_is_trusted = label.get("layer") is not None and str(label.get("layer")) in self.trusted_level_layers
            human_is_trusted = slab.is_validated and "laje_nivel" in slab.validated_fields and bool(label.get("validated"))
            explicit_notation = text.startswith(("+", "-")) or any(token in semantic for token in ("nivel", "nível", "level"))
            if (layer_is_trusted or human_is_trusted or explicit_notation) and (field_value is None or nearly_equal(field_value, value)):
                return value, "rótulo CAD direto em contexto de nível confiável"
        return None

    def _resolve_levels(self) -> None:
        # Sementes independentes: rótulos CAD diretos. Campos e rótulos
        # extraídos juntos não se validam circularmente.
        for slab in self.slabs:
            if slab.name in self.sealed_level_conflicts:
                continue
            anchor = self._direct_level_anchor(slab)
            if anchor:
                self.levels[slab.name], self.level_reasons[slab.name] = anchor

        # Fontes humanas seladas só entram quando campo, root e/ou rótulo não
        # se contradizem. Contradições são tratadas durante a auditoria.
        for slab in self.slabs:
            if slab.name in self.levels or not slab.is_validated:
                continue
            field_value = self._declared_level(slab)
            root_value = self._root_level(slab)
            label_values = [parse_number(x.get("text")) for x in self._own_level_labels(slab)]
            label_values = [x for x in label_values if x is not None]
            if slab.name in self.sealed_level_conflicts:
                # Um selo histórico conflitante nunca é "resolvido" por
                # continuidade geométrica. Root+rótulo concordantes podem ser
                # usados somente como fonte provisória para auditar vizinhos;
                # o próprio campo continua exigindo decisão humana.
                agreeing_labels = [x for x in label_values if root_value is not None and nearly_equal(x, root_value)]
                if root_value is not None and agreeing_labels:
                    self.levels[slab.name] = root_value
                    self.level_reasons[slab.name] = "root+rótulo concordam; conflito selado aguarda decisão humana"
                else:
                    self.blocked_level_sources.add(slab.name)
                continue
            candidates = [x for x in (field_value, root_value) if x is not None] + label_values
            if candidates and max(candidates) - min(candidates) <= 0.05:
                self.levels[slab.name] = candidates[0]
                self.level_reasons[slab.name] = "campo humano selado e consistente"

        # Resolve cadeias explicitamente justificadas (pareamento, delta e
        # consenso) e depois propaga apenas por vizinhança horizontal coerente.
        for _ in range(max(4, len(self.slabs))):
            changed = False
            for slab in self.slabs:
                if slab.name in self.levels or slab.name in self.blocked_level_sources:
                    continue
                for label in self._own_level_labels(slab):
                    value = parse_number(label.get("text"))
                    source = str(label.get("source") or "").lower()
                    source_name = str(label.get("source_slab") or "")
                    if not source_name:
                        source_match = re.search(r"\bfrom\s+([a-z]+\d+)\b", source, re.IGNORECASE)
                        if source_match:
                            source_name = source_match.group(1).upper()
                    source_value = self.levels.get(source_name)
                    if value is None or source_value is None:
                        continue
                    if "delta" in source:
                        delta_match = re.search(r"[Δδd]\s*=\s*([+-]?\d+(?:[.,]\d+)?)", source, re.IGNORECASE)
                        if delta_match:
                            expected = source_value + float(delta_match.group(1).replace(",", "."))
                            if nearly_equal(value, expected):
                                self.levels[slab.name] = value
                                self.level_reasons[slab.name] = f"delta explícito desde {source_name}"
                                changed = True
                                break
                    elif "paired" in source or "consensus" in source:
                        if nearly_equal(value, source_value):
                            self.levels[slab.name] = value
                            self.level_reasons[slab.name] = f"inferência rastreável desde {source_name}"
                            changed = True
                            break
                if slab.name in self.levels:
                    continue
                horizontal_values = []
                neighbor_links = slab.links.get("laje_vizinhas_niveis") or {}
                for slot in ("neighbor_east", "neighbor_west"):
                    for link in safe_list(neighbor_links.get(slot)):
                        if not isinstance(link, dict) or link.get("source") != "orthogonal_neighbor_identity":
                            continue
                        source_name = str(link.get("source_slab") or "")
                        if source_name in self.levels:
                            horizontal_values.append((source_name, self.levels[source_name]))
                if horizontal_values:
                    groups: dict[str, list[tuple[str, float]]] = {}
                    for source_name, value in horizontal_values:
                        groups.setdefault(fmt_number(value), []).append((source_name, value))
                    best = max(groups.values(), key=len)
                    # Uma âncora horizontal basta apenas quando todas as âncoras
                    # conhecidas concordam; duas ou mais vencem fontes ausentes.
                    known_values = {fmt_number(v) for _, v in horizontal_values}
                    if len(known_values) == 1:
                        value = best[0][1]
                        self.levels[slab.name] = value
                        self.level_reasons[slab.name] = "continuidade horizontal desde " + ", ".join(x[0] for x in best)
                        changed = True
            if not changed:
                break

    def audit(self, selected: set[str] | None = None, include_sealed: bool = False) -> list[Decision]:
        decisions: list[Decision] = []
        for slab in self.slabs:
            if selected and slab.name not in selected:
                continue
            if slab.is_validated and not include_sealed:
                continue
            for field_id in REQUIRED_LAJ_FIELDS:
                decisions.append(self._audit_field(slab, field_id))
        return decisions

    def _audit_field(self, slab: Slab, field_id: str) -> Decision:
        method = getattr(self, f"_audit_{field_id}")
        return method(slab)

    def _validation_ops(self, field_id: str, slots: Iterable[str] = ()) -> list[dict]:
        return [{"op": "validate_field", "field": field_id, "slots": sorted(set(slots))}]

    def _already_done(self, slab: Slab, field_id: str, reason: str) -> Decision:
        return self._new_decision(slab, field_id, "CONFIRMAR", "high", reason)

    def _audit_name(self, slab: Slab) -> Decision:
        labels = [x for x in safe_list((slab.links.get("name") or {}).get("label")) if isinstance(x, dict)]
        texts = {str(x.get("text") or "").strip().upper() for x in labels}
        field_name = str(slab.fields.get("nome") or slab.fields.get("name") or slab.name).strip().upper()
        if slab.name.upper() == field_name and (slab.name.upper() in texts or not labels):
            ops = [] if "name" in slab.validated_fields else self._validation_ops("name", ["label"] if labels else [])
            return self._new_decision(slab, "name", "CONFIRMAR", "high", "nome do registro e rótulo estrutural coerentes", operations=ops)
        return self._new_decision(slab, "name", "REVISAR_HUMANO", "low", "nome do registro diverge do rótulo/campo", requires_human=True)

    def _audit_laje_dim(self, slab: Slab) -> Decision:
        raw = slab.fields.get("laje_dim")
        labels = [x for x in safe_list((slab.links.get("laje_dim") or {}).get("label")) if isinstance(x, dict)]
        raw_num = parse_number(str(raw).replace("h=", "").replace("H=", "")) if raw is not None else None
        label_nums = [parse_number(str(x.get("text") or "").replace("h=", "").replace("H=", "")) for x in labels]
        if raw_num is not None and (not label_nums or any(nearly_equal(raw_num, x) for x in label_nums)):
            ops = [] if "laje_dim" in slab.validated_fields else self._validation_ops("laje_dim", ["label"] if labels else [])
            return self._new_decision(slab, "laje_dim", "CONFIRMAR", "high", "espessura coerente com o rótulo da laje", operations=ops)
        return self._new_decision(slab, "laje_dim", "PENDENTE", "low", "espessura ausente ou sem rótulo coerente")

    def _audit_laje_outline_segs(self, slab: Slab) -> Decision:
        contour = [x for x in safe_list((slab.links.get("laje_outline_segs") or {}).get("contour")) if isinstance(x, dict)]
        bbox = slab.bbox
        valid = len(slab.points) >= 4 and bbox is not None and (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0
        if valid and contour:
            ops = [] if "laje_outline_segs" in slab.validated_fields else self._validation_ops("laje_outline_segs", ["contour"])
            return self._new_decision(slab, "laje_outline_segs", "CONFIRMAR", "high", "contorno fechado e vínculo geométrico presentes", operations=ops, evidence=[{"kind": "bbox", "value": bbox}])
        return self._new_decision(slab, "laje_outline_segs", "PENDENTE", "low", "contorno insuficiente ou sem vínculo geométrico")

    def _audit_laje_islands(self, slab: Slab) -> Decision:
        islands = slab.fields.get("laje_islands") or slab.extra.get("laje_islands")
        links = slab.links.get("laje_islands") or {}
        has_island = bool(islands) or any(safe_list(v) for v in links.values()) if isinstance(links, dict) else bool(islands)
        if has_island:
            ops = [] if "laje_islands" in slab.validated_fields else self._validation_ops("laje_islands", links.keys() if isinstance(links, dict) else [])
            return self._new_decision(slab, "laje_islands", "CONFIRMAR", "medium", "ilhas/furos explicitamente vinculados", operations=ops)
        if "laje_islands" in slab.na_fields:
            return self._already_done(slab, "laje_islands", "ausência de ilhas já marcada N/A")
        return self._new_decision(
            slab, "laje_islands", "N/A_CONFIRMADO", "high", "contorno sem ilhas/furos vinculados",
            operations=[{"op": "mark_na", "field": "laje_islands", "reason": "contorno sem ilhas/furos detectados"}],
        )

    def _geometry_tolerance(self, slab: Slab) -> float:
        bbox = slab.bbox
        if not bbox:
            return 1.0
        return max(1.0, min(bbox[2] - bbox[0], bbox[3] - bbox[1]) * 0.01)

    def _link_distance(self, slab: Slab, link: dict) -> float | None:
        recorded = link.get("distance_to_slab")
        try:
            if recorded is not None:
                return float(recorded)
        except (TypeError, ValueError):
            pass
        slab_bbox = slab.bbox
        geom_bbox = point_bbox(link.get("points") or [])
        if slab_bbox and geom_bbox:
            return bbox_distance(slab_bbox, geom_bbox)
        return None

    def _remove_link_op(self, field_id: str, slot: str, link: dict) -> dict:
        return {"op": "remove_link", "field": field_id, "slot": slot, "fingerprint": link_fingerprint(link)}

    def _audit_laje_visao_corte(self, slab: Slab) -> Decision:
        field_id = "laje_visao_corte"
        slot = "cut_view_geom"
        links = [x for x in safe_list((slab.links.get(field_id) or {}).get(slot)) if isinstance(x, dict)]
        tol = self._geometry_tolerance(slab)
        valid, invalid = [], []
        for link in links:
            distance = self._link_distance(slab, link)
            points = link.get("points") or []
            if len(points) >= 5 and distance is not None and distance <= tol:
                valid.append(link)
            else:
                invalid.append(link)
        operations = []
        for link in invalid:
            if link.get("is_inferred"):
                operations.append(self._remove_link_op(field_id, slot, link))
        if invalid:
            evidence = [{"distance": self._link_distance(slab, x), "bbox": point_bbox(x.get("points") or [])} for x in invalid]
            self._add_finding(slab, field_id, "LAJ-CUT-DISTANT", "geometria de corte distante/sem contato foi associada à laje", evidence)
        if valid:
            if field_id not in slab.validated_fields:
                operations += self._validation_ops(field_id, [slot])
            return self._new_decision(
                slab, field_id, "CONFIRMAR", "high", f"{len(valid)} geometria(s) de corte em contato; {len(invalid)} vínculo(s) distante(s) removível(is)",
                operations=operations, rule_codes=["LAJ-CUT-DISTANT"] if invalid else [],
                evidence=[{"kind": "cut_geom", "count": len(valid), "tolerance": tol}],
            )
        if not links or all(x.get("is_inferred") for x in invalid):
            if field_id in slab.na_fields:
                return self._already_done(slab, field_id, "ausência de visão de corte já marcada N/A")
            operations.append({"op": "mark_na", "field": field_id, "reason": "nenhuma geometria de corte em contato com a laje"})
            return self._new_decision(slab, field_id, "N/A_CONFIRMADO", "high", "nenhuma geometria de corte em contato", operations=operations)
        return self._new_decision(slab, field_id, "REVISAR_HUMANO", "low", "geometria de corte sem prova suficiente", requires_human=True)

    def _audit_laje_pilares_apoio(self, slab: Slab) -> Decision:
        field_id = "laje_pilares_apoio"
        slot = "pillar_geom"
        links = [x for x in safe_list((slab.links.get(field_id) or {}).get(slot)) if isinstance(x, dict)]
        tol = self._geometry_tolerance(slab)
        valid, invalid = [], []
        for link in links:
            ficha = link.get("ficha") if isinstance(link.get("ficha"), dict) else {}
            name = str(ficha.get("pillar_name") or "").strip()
            side = str(ficha.get("pillar_side") or "NULO").upper()
            face = str(ficha.get("touch_face") or "NULO").upper()
            distance = self._link_distance(slab, link)
            if name and side not in {"", "NULO", "N/A"} and face not in {"", "NULO", "N/A"} and distance is not None and distance <= tol:
                valid.append(link)
            else:
                invalid.append(link)
        operations = []
        for link in invalid:
            if link.get("is_inferred"):
                operations.append(self._remove_link_op(field_id, slot, link))
        if invalid:
            evidence = []
            for link in invalid:
                ficha = link.get("ficha") or {}
                evidence.append({
                    "pillar": ficha.get("pillar_name"),
                    "distance": self._link_distance(slab, link),
                    "pillar_side": ficha.get("pillar_side"),
                    "touch_face": ficha.get("touch_face"),
                })
            self._add_finding(slab, field_id, "LAJ-PILLAR-NOT-TOUCHING", "pilar distante ou sem face/lado foi associado como apoio", evidence)
        if valid:
            if field_id not in slab.validated_fields:
                operations += self._validation_ops(field_id, [slot, "pillar_label"])
            return self._new_decision(
                slab, field_id, "CONFIRMAR", "high", f"{len(valid)} apoio(s) nomeado(s) em contato; {len(invalid)} associação(ões) contaminada(s) removível(is)",
                operations=operations, rule_codes=["LAJ-PILLAR-NOT-TOUCHING"] if invalid else [],
                evidence=[{"kind": "pillar_support", "pillars": [(x.get("ficha") or {}).get("pillar_name") for x in valid], "tolerance": tol}],
            )
        if not links:
            self._add_question(
                slab, field_id, "LAJ-PILLAR-NONE",
                f"O agente não encontrou apoio direto comprovável para {slab.name}. Qual regra de projeto deve distinguir uma laje sem pilar de um apoio ausente na extração?",
                [],
                reasoning={
                    "observed": "Não há vínculo de pilar no campo laje_pilares_apoio.",
                    "attempted": ["busca por geometria de pilar", "validação de nome, lado, face e contato com o contorno"],
                    "rejected": ["inferir apoio apenas por proximidade", "criar pilar sem face de contato"],
                    "impasse": "Sem evidência geométrica ou semântica de apoio, marcar N/A alteraria a interpretação estrutural.",
                    "requested_rule": "Informe a regra geral que comprova 'sem pilar de apoio' neste tipo de laje.",
                },
            )
            return self._new_decision(slab, field_id, "REVISAR_HUMANO", "low", "nenhum pilar de apoio vinculado", requires_human=True)
        return self._new_decision(slab, field_id, "REVISAR_HUMANO", "low", "todos os pilares vinculados são distantes ou incompletos", operations=operations, requires_human=True)

    def _level_conflicts(self, slab: Slab) -> list[dict]:
        field_value = self._declared_level(slab)
        root_value = self._root_level(slab)
        labels = [(parse_number(x.get("text")), x) for x in self._own_level_labels(slab)]
        evidence = []
        if field_value is not None and root_value is not None and not nearly_equal(field_value, root_value):
            evidence.append({"kind": "field_vs_root", "field": field_value, "root": root_value})
        for value, link in labels:
            if value is not None and field_value is not None and not nearly_equal(value, field_value):
                evidence.append({"kind": "field_vs_label", "field": field_value, "label": value, "source": link.get("source")})
        if "laje_nivel" in slab.validated_fields and field_value is None:
            evidence.append({"kind": "validated_without_value"})
        return evidence

    def _audit_laje_nivel(self, slab: Slab) -> Decision:
        field_id = "laje_nivel"
        conflicts = self._level_conflicts(slab)
        expected = self.levels.get(slab.name)
        if conflicts and slab.is_validated:
            cross_correction = self._sealed_level_cross_class_correction(slab)
            if cross_correction:
                proposed = cross_correction["expected"]
                current = cross_correction["current"]
                pillars = cross_correction["pillars"]
                self._add_finding(
                    slab, field_id, "LAJ-LEVEL-PILLAR-CONSENSUS",
                    f"{len(pillars)} pilares em contato convergem em {fmt_number(proposed)} e confirmam o root",
                    [{"current": fmt_number(current), "expected": fmt_number(proposed), "pillars": pillars}],
                )
                return self._new_decision(
                    slab, field_id, "CORRIGIR", "high",
                    f"campo diverge do root e do consenso de pilares em contato; corrigir para {fmt_number(proposed)}",
                    operations=[{"op": "set_level", "value": fmt_number(proposed), "reason": "consenso PIL em contato + root"}],
                    evidence=[{
                        "kind": "consultive_pillar_level_consensus", "current": current,
                        "expected": proposed, "pillars": pillars,
                        "beams_consulted": cross_correction["beam_context"],
                    }],
                    rule_codes=["LAJ-LEVEL-PILLAR-CONSENSUS"],
                )
            autocorrection = self._sealed_level_autocorrection(slab)
            if autocorrection:
                proposed = autocorrection["expected"]
                current = autocorrection["current"]
                support = autocorrection["expected_cluster"]
                self._add_finding(
                    slab, field_id, "LAJ-LEVEL-OUTLIER-CORRECTION",
                    f"{fmt_number(current)} é nível isolado; root+rótulo e {support['count']} lajes corroboram {fmt_number(proposed)}",
                    [{
                        "current": fmt_number(current), "expected": fmt_number(proposed),
                        "root": fmt_number(proposed), "labels": autocorrection["labels"],
                        "corroborated_slabs": support["slabs"],
                        "rule": "root+rótulo concordantes + cluster corroborado + campo sem cluster",
                    }],
                )
                return self._new_decision(
                    slab, field_id, "CORRIGIR", "high",
                    f"campo de nível é outlier não corroborado; corrigir para {fmt_number(proposed)}",
                    operations=[{"op": "set_level", "value": fmt_number(proposed), "reason": "root+rótulo+cluster corroborado"}],
                    evidence=[{"kind": "level_outlier", "current": current, "expected": proposed, "support_count": support["count"], "supporting_slabs": support["slabs"]}],
                    rule_codes=["LAJ-LEVEL-OUTLIER-CORRECTION"],
                )
            self._add_question(
                slab, field_id, "LAJ-LEVEL-SEALED-CONFLICT",
                f"O agente preservou {slab.name}: campo e root discordam, mas ambos pertencem a níveis usados no corpus. Qual regra geral identifica a fonte canônica quando não há rótulo CAD próprio independente?",
                conflicts,
                reasoning={
                    "observed": {
                        "field": fmt_number(self._declared_level(slab)) if self._declared_level(slab) is not None else None,
                        "root": fmt_number(self._root_level(slab)) if self._root_level(slab) is not None else None,
                        "labels": [str(x.get("text")) for x in self._own_level_labels(slab)],
                        "field_cluster": self._cluster_for_level(self._declared_level(slab)),
                        "root_cluster": self._cluster_for_level(self._root_level(slab)),
                        "dependent_neighbors": self._neighbor_dependents(slab.name),
                    },
                    "attempted": ["comparar campo, root e rótulos próprios", "buscar grupo corroborado no pavimento", "propagar somente continuidade horizontal não circular"],
                    "rejected": ["usar o campo como sua própria prova", "usar root isolado como prova suficiente", "resolver pelo vizinho que depende da própria laje"],
                    "impasse": "Os dois candidatos pertencem a grupos reais; não existe rótulo próprio independente para desempatar sem circularidade.",
                    "requested_rule": "Explique qual proveniência deve vencer nesse padrão e qual sinal semântico torna essa proveniência canônica para qualquer obra.",
                },
            )
            return self._new_decision(
                slab, field_id, "REVISAR_HUMANO", "low", "item selado contém conflito de nível; preservado sem mutação",
                evidence=conflicts, rule_codes=["LAJ-LEVEL-SEALED-CONFLICT"], requires_human=True,
            )
        if expected is None:
            if conflicts and not slab.is_validated:
                ops = [{"op": "unvalidate_field", "field": field_id}]
            else:
                ops = []
            self._add_question(
                slab, field_id, "LAJ-LEVEL-NO-ANCHOR",
                f"O agente não promoveu nível para {slab.name}: não encontrou âncora independente. Qual regra geral deve provar o nível quando campo e rótulos não se confirmam?",
                conflicts,
                reasoning={
                    "observed": conflicts,
                    "attempted": ["rótulo CAD direto", "camada confiável", "delta rastreável", "continuidade horizontal coerente"],
                    "rejected": ["aceitar número de dimensão", "usar campo e rótulo extraídos juntos como prova circular"],
                    "impasse": "Nenhuma fonte independente atingiu o limiar de confiança.",
                    "requested_rule": "Defina a evidência mínima universal para promover um nível nesse cenário.",
                },
            )
            return self._new_decision(slab, field_id, "REVISAR_HUMANO", "low", "nível sem âncora independente", operations=ops, requires_human=True)

        operations = []
        current = self._declared_level(slab)
        if current is None or not nearly_equal(current, expected):
            operations.append({"op": "set_level", "value": fmt_number(expected), "reason": self.level_reasons.get(slab.name)})
            if current is not None:
                self._add_finding(slab, field_id, "LAJ-LEVEL-MISMATCH", f"nível {fmt_number(current)} diverge da evidência {fmt_number(expected)}", [{"reason": self.level_reasons.get(slab.name)}])
        labels = self._own_level_labels(slab)
        if not any(nearly_equal(parse_number(x.get("text")), expected) for x in labels):
            operations.append({
                "op": "add_link", "field": field_id, "slot": "label",
                "link": {"type": "text", "text": fmt_number(expected), "role": "Nivel inferido por QA", "source": "qa_evidence_level", "source_slab": None, "is_inferred": True},
            })
        if field_id not in slab.validated_fields or conflicts:
            operations += self._validation_ops(field_id, ["label"])
        return self._new_decision(
            slab, field_id, "CONFIRMAR", "high", f"nível {fmt_number(expected)} sustentado por {self.level_reasons.get(slab.name)}",
            operations=operations, evidence=[{"kind": "level", "value": expected, "reason": self.level_reasons.get(slab.name)}],
            rule_codes=["LAJ-LEVEL-MISMATCH"] if conflicts else [],
        )

    def _audit_laje_vizinhas_niveis(self, slab: Slab) -> Decision:
        field_id = "laje_vizinhas_niveis"
        neighbor_links = slab.links.get(field_id) if isinstance(slab.links.get(field_id), dict) else {}
        operations: list[dict] = []
        unresolved: list[dict] = []
        evidence: list[dict] = []
        occupied_slots = []

        for slot, raw_entries in neighbor_links.items():
            entries = [x for x in safe_list(raw_entries) if isinstance(x, dict)]
            identities: dict[str, list[dict]] = {}
            levels: dict[str, list[dict]] = {}
            for link in entries:
                source_name = str(link.get("source_slab") or "")
                if link.get("source") == "orthogonal_neighbor_identity" and str(link.get("text") or "").upper() == source_name.upper() and source_name in self.by_name:
                    identities.setdefault(source_name, []).append(link)
                elif link.get("source") == "orthogonal_neighbor_level":
                    levels.setdefault(source_name, []).append(link)
            if identities:
                occupied_slots.append(slot)
            for source_name in identities:
                expected = self.levels.get(source_name)
                source_levels = levels.get(source_name, [])
                if expected is None:
                    source_slab = self.by_name.get(source_name)
                    candidates = []
                    if source_slab is not None:
                        candidates = [
                            x for x in (
                                self._declared_level(source_slab),
                                self._root_level(source_slab),
                                *[parse_number(y.get("text")) for y in self._own_level_labels(source_slab)],
                            ) if x is not None
                        ]
                    for link in source_levels:
                        value = parse_number(link.get("text"))
                        if link.get("is_inferred") and value is not None and candidates and not any(nearly_equal(value, x) for x in candidates):
                            operations.append(self._remove_link_op(field_id, slot, link))
                            self._add_finding(
                                slab, field_id, "LAJ-NEIGHBOR-LEVEL-CONTAMINATION",
                                f"{link.get('text')} não corresponde a nenhuma evidência de nível de {source_name}",
                                [{"slot": slot, "source_slab": source_name, "wrong": link.get("text"), "candidates": [fmt_number(x) for x in candidates]}],
                            )
                    unresolved.append({"slot": slot, "source_slab": source_name, "reason": "fonte sem nível confiável"})
                    continue
                matching = [x for x in source_levels if nearly_equal(parse_number(x.get("text")), expected)]
                wrong = [x for x in source_levels if not nearly_equal(parse_number(x.get("text")), expected)]
                for link in wrong:
                    if link.get("is_inferred"):
                        operations.append(self._remove_link_op(field_id, slot, link))
                        self._add_finding(
                            slab, field_id, "LAJ-NEIGHBOR-LEVEL-CONTAMINATION",
                            f"{link.get('text')} não é o nível confiável de {source_name} ({fmt_number(expected)})",
                            [{"slot": slot, "source_slab": source_name, "wrong": link.get("text"), "expected": fmt_number(expected)}],
                        )
                    else:
                        unresolved.append({"slot": slot, "source_slab": source_name, "reason": "vínculo humano divergente"})
                if not matching:
                    operations.append({
                        "op": "add_link", "field": field_id, "slot": slot,
                        "link": {
                            "type": "text", "text": fmt_number(expected), "role": slot,
                            "source": "orthogonal_neighbor_level", "source_slab": source_name,
                            "source_direction": slot.replace("neighbor_", ""), "is_inferred": True,
                            "qa_source": self.level_reasons.get(source_name),
                        },
                    })
                evidence.append({"slot": slot, "source_slab": source_name, "level": fmt_number(expected)})

            # Um nível sem a identidade correspondente é órfão e não pode
            # sustentar o campo. Só removemos se for inferido.
            for source_name, source_levels in levels.items():
                if source_name in identities:
                    continue
                for link in source_levels:
                    if link.get("is_inferred"):
                        operations.append(self._remove_link_op(field_id, slot, link))
                        self._add_finding(slab, field_id, "LAJ-NEIGHBOR-ORPHAN-LEVEL", "nível vizinho sem identidade da laje-fonte no mesmo slot", [{"slot": slot, "source_slab": source_name, "text": link.get("text")}])
                    else:
                        unresolved.append({"slot": slot, "source_slab": source_name, "reason": "nível humano órfão"})

        if unresolved:
            for issue in unresolved:
                if issue["source_slab"] in self.unresolved_level_sources:
                    # A pergunta-raiz já explica o impasse e lista os dependentes.
                    # Repeti-la em cada vizinha transforma uma única decisão em ruído.
                    continue
                self._add_question(
                    slab, field_id, "LAJ-NEIGHBOR-UNRESOLVED",
                    f"O vínculo de {issue['source_slab']} em {issue['slot']} foi preservado, mas o nível-fonte não é canônico. Qual regra geral deve escolher a proveniência do nível antes de propagá-lo para vizinhas?",
                    [issue],
                    reasoning={
                        "observed": issue,
                        "attempted": ["validar identidade no mesmo slot", "ler nível da laje-fonte", "remover somente números inferidos sem evidência"],
                        "rejected": ["copiar um nível sem fonte canônica", "inferir a partir de dimensão numérica", "usar a própria vizinha como prova circular"],
                        "impasse": "A identidade geométrica existe, mas a laje-fonte ainda possui mais de uma proveniência plausível de nível.",
                        "requested_rule": "Defina qual fonte canônica o motor deve usar antes de publicar o par identidade+nível para vizinhas.",
                    },
                )
            return self._new_decision(
                slab, field_id, "REVISAR_HUMANO", "low", "há vizinho sem nível-fonte confiável",
                operations=operations, evidence=unresolved, requires_human=True,
            )
        if not occupied_slots:
            return self._new_decision(slab, field_id, "PENDENTE", "low", "nenhuma identidade de laje vizinha comprovada")
        if field_id not in slab.validated_fields:
            operations += self._validation_ops(field_id, occupied_slots)
        codes = sorted({f["code"] for f in self.findings if f["item"] == slab.name and f["field_id"] == field_id})
        return self._new_decision(
            slab, field_id, "CONFIRMAR", "high", "identidades vizinhas válidas e níveis coerentes com cada laje-fonte",
            operations=operations, evidence=evidence, rule_codes=codes,
        )


def load_slabs(con: sqlite3.Connection, project_id: str) -> list[Slab]:
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, project_id, name, points_json, links_json, validated_fields_json, "
        "na_fields_json, validated_link_classes_json, na_link_classes_json, "
        "na_reasons_json, extra_data_json, is_validated FROM slabs "
        "WHERE project_id=? ORDER BY CAST(SUBSTR(name, 2) AS INTEGER)",
        (project_id,),
    ).fetchall()
    slabs = []
    for row in rows:
        raw = {column: row[column] for column in MUTABLE_COLUMNS}
        slabs.append(Slab(
            id=row["id"], project_id=row["project_id"], name=row["name"],
            points=json_load(row["points_json"], []), links=json_load(row["links_json"], {}),
            validated_fields=set(json_load(row["validated_fields_json"], [])),
            na_fields=set(json_load(row["na_fields_json"], [])),
            validated_link_classes=json_load(row["validated_link_classes_json"], {}),
            na_link_classes=json_load(row["na_link_classes_json"], {}),
            na_reasons=json_load(row["na_reasons_json"], {}), extra=json_load(row["extra_data_json"], {}),
            is_validated=bool(row["is_validated"]), raw_columns=raw,
        ))
    return slabs


def _context_points(payload: dict) -> list:
    if not isinstance(payload, dict):
        return []
    geometry = payload.get("geometry") if isinstance(payload.get("geometry"), dict) else {}
    return payload.get("points") or payload.get("coordenadas") or geometry.get("poly") or []


def load_consultive_context(con: sqlite3.Connection, project_id: str, slabs: list[Slab]) -> dict[str, dict]:
    """Carrega contexto próximo PIL/FV/LV em modo somente consulta.

    A consulta é intencionalmente separada do adaptador LAJ: os registros das
    outras classes jamais são alterados, nem seus campos são copiados para a
    ficha da laje. Apenas PIL em contato e com consenso pode desempatar nível.
    """
    con.row_factory = sqlite3.Row
    context = {slab.name: {"pillars": [], "beams": []} for slab in slabs}
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    pillar_rows = con.execute(
        "SELECT name, points_json, extra_data_json, is_validated FROM pillars WHERE project_id=?",
        (project_id,),
    ).fetchall() if "pillars" in tables else []
    beam_rows = con.execute(
        "SELECT name, data_json, is_validated FROM beams WHERE project_id=?",
        (project_id,),
    ).fetchall() if "beams" in tables else []
    pillars = []
    for row in pillar_rows:
        extra = json_load(row["extra_data_json"], {})
        fields = extra.get("fields") if isinstance(extra.get("fields"), dict) else {}
        level = extra.get("level") or fields.get("nivel") or fields.get("Nível")
        bbox = point_bbox(json_load(row["points_json"], []))
        if bbox:
            pillars.append({"name": row["name"], "bbox": bbox, "level": level, "validated": bool(row["is_validated"])})
    beams = []
    for row in beam_rows:
        data = json_load(row["data_json"], {})
        fields = data.get("fields") if isinstance(data.get("fields"), dict) else {}
        level = fields.get("nivel") or data.get("nivel")
        bbox = point_bbox(_context_points(data))
        if bbox:
            beams.append({"name": row["name"], "bbox": bbox, "level": level, "validated": bool(row["is_validated"])})
    for slab in slabs:
        if not slab.bbox:
            continue
        tol = max(1.0, min(slab.bbox[2] - slab.bbox[0], slab.bbox[3] - slab.bbox[1]) * 0.01)
        for pillar in pillars:
            distance = bbox_distance(slab.bbox, pillar["bbox"])
            if distance <= tol:
                context[slab.name]["pillars"].append({
                    "name": pillar["name"], "level": pillar["level"],
                    "distance": distance, "validated": pillar["validated"],
                })
        for beam in beams:
            distance = bbox_distance(slab.bbox, beam["bbox"])
            if distance <= max(20.0, tol * 5):
                context[slab.name]["beams"].append({
                    "name": beam["name"], "level": beam["level"],
                    "distance": distance, "validated": beam["validated"],
                })
    return context


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


FIX_PROMPTS = {
    "LAJ-CUT-DISTANT": """Ajuste universal do detector LAJ: uma geometria de visão de corte só pode ser vinculada se tocar/intersectar o contorno da laje dentro de tolerância escalada pela dimensão local. Não use IDs de item/obra. Remova vínculos inferidos distantes, preserve vínculos humanos e crie regressão com casos de corte composto e geometrias de pilares próximas.""",
    "LAJ-PILLAR-NOT-TOUCHING": """Ajuste universal do detector de apoios LAJ: pilar de apoio exige nome canônico, geometria em contato com o contorno e face/lado determináveis. Pilares separados por viga/gap ou com touch_face/pillar_side NULO não podem entrar. A tolerância deve escalar com a laje; zero hardcode por item. Preserve vínculos humanos e adicione regressão cross-classe porque o tracer alimenta outros elementos.""",
    "LAJ-NEIGHBOR-LEVEL-CONTAMINATION": """Ajuste universal de vizinhos LAJ: nível vizinho deve vir do campo/rótulo semanticamente confiável da laje-fonte e estar no mesmo slot da identidade. Números de cotas/dimensões não provam nível. Remova apenas inferências contaminadas, preserve decisões humanas e teste valores de nível e dimensões numericamente parecidos.""",
    "LAJ-NEIGHBOR-ORPHAN-LEVEL": """Ajuste universal de vizinhos LAJ: proíba nível inferido sem identidade source_slab válida no mesmo slot direcional. Gere par identidade+nível atomicamente e teste múltiplas lajes na mesma direção.""",
    "LAJ-LEVEL-MISMATCH": """Ajuste universal de nível LAJ: não permita que field, root e label divirjam silenciosamente. Inferências precisam de âncora direta, delta explícito ou consenso geométrico rastreável. Em conflito, falhe fechado e gere pergunta; nunca faça média.""",
}


def write_reports(out_dir: Path, manifest: dict, decisions: list[Decision], findings: list[dict], questions: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "manifesto.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    write_jsonl(out_dir / "decisoes.jsonl", (asdict(x) for x in decisions))
    write_jsonl(out_dir / "achados.jsonl", findings)
    write_jsonl(out_dir / "perguntas.jsonl", questions)

    codes = sorted({code for finding in findings for code in [finding.get("code")] if code})
    fix_lines = ["# Fix requests gerados pelo Agente QA de Evidências", ""]
    for code in codes:
        related = [x for x in findings if x.get("code") == code]
        items = sorted({x["item"] for x in related})
        fix_lines += [f"## {code}", "", f"Itens observados: {', '.join(items)}", "", FIX_PROMPTS.get(code, "Investigue a causa geral e crie teste de regressão sem hardcode por item."), ""]
    (out_dir / "fix_requests.md").write_text("\n".join(fix_lines), encoding="utf-8")

    counts: dict[str, int] = {}
    for decision in decisions:
        counts[decision.decision] = counts.get(decision.decision, 0) + 1
    summary = [
        "# Resumo — Agente QA de Evidências",
        "",
        f"- Run: `{manifest['run_id']}`",
        f"- Projeto: `{manifest['project_id']}`",
        f"- Itens: {len(manifest['items'])}",
        f"- Decisões: {len(decisions)}",
        f"- Achados: {len(findings)}",
        f"- Perguntas: {len(questions)}",
        "",
        "## Decisões",
        "",
    ]
    summary += [f"- {key}: {value}" for key, value in sorted(counts.items())]
    (out_dir / "resumo.md").write_text("\n".join(summary) + "\n", encoding="utf-8")


def current_snapshot(con: sqlite3.Connection, slab_id: str) -> tuple[str, dict[str, Any]]:
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT id, " + ", ".join(MUTABLE_COLUMNS) + " FROM slabs WHERE id=?",
        (slab_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"slab ausente: {slab_id}")
    raw = {column: row[column] for column in MUTABLE_COLUMNS}
    payload = {"id": row["id"], **raw}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest(), raw


def apply_operation(state: dict, operation: dict) -> None:
    op = operation["op"]
    links = state["links"]
    validated_fields: set[str] = state["validated_fields"]
    na_fields: set[str] = state["na_fields"]
    validated_links: dict = state["validated_link_classes"]
    na_reasons: dict = state["na_reasons"]
    extra: dict = state["extra"]
    field_id = operation.get("field")

    if op == "remove_link":
        slot = operation["slot"]
        field_links = links.setdefault(field_id, {})
        entries = safe_list(field_links.get(slot))
        field_links[slot] = [x for x in entries if not isinstance(x, dict) or link_fingerprint(x) != operation["fingerprint"]]
    elif op == "add_link":
        slot = operation["slot"]
        entries = links.setdefault(field_id, {}).setdefault(slot, [])
        candidate = copy.deepcopy(operation["link"])
        fingerprint = link_fingerprint(candidate)
        if not any(isinstance(x, dict) and link_fingerprint(x) == fingerprint for x in entries):
            entries.append(candidate)
    elif op == "set_level":
        value = operation["value"]
        extra.setdefault("fields", {})["laje_nivel"] = value
        extra["laje_nivel"] = value
    elif op == "validate_field":
        validated_fields.add(field_id)
        na_fields.discard(field_id)
        na_reasons.pop(field_id, None)
        slots = operation.get("slots") or []
        if slots:
            current = validated_links.get(field_id, [])
            if isinstance(current, dict):
                current = list(current.keys())
            validated_links[field_id] = sorted(set(current or []) | set(slots))
            for slot in slots:
                for link in safe_list((links.get(field_id) or {}).get(slot)):
                    if isinstance(link, dict):
                        link["validated"] = True
    elif op == "unvalidate_field":
        validated_fields.discard(field_id)
        validated_links.pop(field_id, None)
    elif op == "mark_na":
        na_fields.add(field_id)
        validated_fields.add(field_id)
        na_reasons[field_id] = operation.get("reason") or "N/A confirmado pelo QA"
    else:
        raise RuntimeError(f"operação desconhecida: {op}")


def cmd_audit(args: argparse.Namespace) -> int:
    db = Path(args.db)
    with sqlite3.connect(db) as con:
        slabs = load_slabs(con, args.project_id)
        consultive_context = load_consultive_context(con, args.project_id, slabs)
    if not slabs:
        raise SystemExit(f"nenhuma LAJ encontrada para project_id={args.project_id}")
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    auditor = LajEvidenceAuditor(slabs, run_id, consultive_context=consultive_context)
    selected = set(args.item or []) or None
    decisions = auditor.audit(selected=selected, include_sealed=args.include_sealed)
    selected_slabs = [x for x in slabs if (not selected or x.name in selected) and (args.include_sealed or not x.is_validated)]
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_REPORT_ROOT / run_id
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": utc_now(),
        "mode": "read_only_audit",
        "db": str(db.resolve()),
        "project_id": args.project_id,
        "classe": "LAJ",
        "include_sealed": bool(args.include_sealed),
        "items": [x.name for x in selected_slabs],
        "snapshots": {x.name: {"id": x.id, "hash": x.snapshot_hash} for x in selected_slabs},
        "required_fields": list(REQUIRED_LAJ_FIELDS),
    }
    write_reports(out_dir, manifest, decisions, auditor.findings, auditor.questions)
    print(json.dumps({
        "run_id": run_id,
        "out_dir": str(out_dir),
        "decisions": len(decisions),
        "findings": len(auditor.findings),
        "questions": len(auditor.questions),
    }, ensure_ascii=False))
    return 0


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cmd_apply(args: argparse.Namespace) -> int:
    run_dir = Path(args.run)
    manifest = json.loads((run_dir / "manifesto.json").read_text(encoding="utf-8"))
    if manifest.get("project_id") != args.project_id:
        raise SystemExit("project_id não coincide com o manifesto")
    decisions = read_jsonl(run_dir / "decisoes.jsonl")
    approved_decisions = {"CONFIRMAR", "N/A_CONFIRMADO"}
    if getattr(args, "allow_sealed_corrections", False):
        approved_decisions.add("CORRIGIR")
    approved = {
        x["decision_id"] for x in decisions
        if x.get("confidence") == "high" and x.get("decision") in approved_decisions
    }
    if args.decision_file:
        supplied = json_load(Path(args.decision_file).read_text(encoding="utf-8"), [])
        approved &= set(supplied)
    if not approved:
        raise SystemExit("nenhuma decisão de alta confiança aprovada")

    by_item: dict[str, list[dict]] = {}
    for decision in decisions:
        if decision["decision_id"] in approved and decision.get("operations"):
            by_item.setdefault(decision["item"], []).extend(decision["operations"])

    db = Path(args.db)
    rollback_rows = []
    applied = []
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        con.execute("BEGIN IMMEDIATE")
        try:
            for item, operations in by_item.items():
                snapshot = manifest["snapshots"].get(item)
                if not snapshot:
                    raise RuntimeError(f"snapshot ausente para {item}")
                current_hash, old_raw = current_snapshot(con, snapshot["id"])
                if current_hash != snapshot["hash"]:
                    raise RuntimeError(f"snapshot obsoleto para {item}; rode audit novamente")
                row = con.execute("SELECT * FROM slabs WHERE id=? AND project_id=?", (snapshot["id"], args.project_id)).fetchone()
                if row is None:
                    raise RuntimeError(f"item fora do projeto: {item}")
                state = {
                    "links": json_load(row["links_json"], {}),
                    "validated_fields": set(json_load(row["validated_fields_json"], [])),
                    "na_fields": set(json_load(row["na_fields_json"], [])),
                    "validated_link_classes": json_load(row["validated_link_classes_json"], {}),
                    "na_link_classes": json_load(row["na_link_classes_json"], {}),
                    "na_reasons": json_load(row["na_reasons_json"], {}),
                    "extra": json_load(row["extra_data_json"], {}),
                    "is_validated": bool(row["is_validated"]),
                }
                if state["is_validated"] and not (
                    getattr(args, "allow_sealed_corrections", False)
                    and any(decision.get("decision") == "CORRIGIR" for decision in decisions if decision["decision_id"] in approved and decision["item"] == item)
                ):
                    # Itens selados são imutáveis por padrão. Correção de selo é
                    # opt-in e aceita somente decisão high CORRIGIR do snapshot.
                    continue
                for operation in operations:
                    apply_operation(state, operation)
                complete = set(REQUIRED_LAJ_FIELDS).issubset(state["validated_fields"] | state["na_fields"])
                new_seal = 1 if args.seal_complete and complete else int(state["is_validated"])
                rollback_rows.append({"item": item, "id": snapshot["id"], "old": old_raw})
                con.execute(
                    "UPDATE slabs SET links_json=?, validated_fields_json=?, na_fields_json=?, "
                    "validated_link_classes_json=?, na_link_classes_json=?, na_reasons_json=?, "
                    "extra_data_json=?, is_validated=? WHERE id=? AND project_id=?",
                    (
                        canonical_json(state["links"]), canonical_json(sorted(state["validated_fields"])),
                        canonical_json(sorted(state["na_fields"])), canonical_json(state["validated_link_classes"]),
                        canonical_json(state["na_link_classes"]), canonical_json(state["na_reasons"]),
                        canonical_json(state["extra"]), new_seal, snapshot["id"], args.project_id,
                    ),
                )
                applied.append({"item": item, "operations": len(operations), "complete": complete, "sealed": bool(new_seal)})
            con.commit()
        except Exception:
            con.rollback()
            raise
    write_jsonl(run_dir / "rollback.jsonl", rollback_rows)
    (run_dir / "apply_result.json").write_text(json.dumps({"applied_at": utc_now(), "project_id": args.project_id, "items": applied}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"applied": applied, "rollback": str(run_dir / 'rollback.jsonl')}, ensure_ascii=False))
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    run_dir = Path(args.run)
    manifest = json.loads((run_dir / "manifesto.json").read_text(encoding="utf-8"))
    if manifest.get("project_id") != args.project_id:
        raise SystemExit("project_id não coincide com o manifesto")
    rows = read_jsonl(run_dir / "rollback.jsonl")
    if not rows:
        raise SystemExit("rollback.jsonl ausente ou vazio")
    with sqlite3.connect(Path(args.db)) as con:
        con.execute("BEGIN IMMEDIATE")
        try:
            for entry in rows:
                old = entry["old"]
                values = [old[column] for column in MUTABLE_COLUMNS]
                con.execute(
                    "UPDATE slabs SET " + ", ".join(f"{column}=?" for column in MUTABLE_COLUMNS) + " WHERE id=? AND project_id=?",
                    (*values, entry["id"], args.project_id),
                )
            con.commit()
        except Exception:
            con.rollback()
            raise
    print(json.dumps({"rolled_back": [x["item"] for x in rows]}, ensure_ascii=False))
    return 0


def cmd_questions(args: argparse.Namespace) -> int:
    rows = read_jsonl(Path(args.run) / "perguntas.jsonl")
    if not rows:
        print("Nenhuma pergunta pendente.")
        return 0
    for index, row in enumerate(rows, 1):
        print(f"{index}. [{row['item']} / {row['field_id']}] {row['question']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="auditoria read-only")
    audit.add_argument("--db", default=str(DEFAULT_DB))
    audit.add_argument("--project-id", required=True)
    audit.add_argument("--item", nargs="*")
    audit.add_argument("--include-sealed", action="store_true")
    audit.add_argument("--run-id")
    audit.add_argument("--out-dir")
    audit.set_defaults(func=cmd_audit)

    apply_cmd = sub.add_parser("apply", help="aplica decisões high do mesmo snapshot")
    apply_cmd.add_argument("--db", default=str(DEFAULT_DB))
    apply_cmd.add_argument("--project-id", required=True)
    apply_cmd.add_argument("--run", required=True)
    apply_cmd.add_argument("--decision-file")
    apply_cmd.add_argument("--seal-complete", action="store_true")
    apply_cmd.add_argument(
        "--allow-sealed-corrections", action="store_true",
        help="permite corrigir item já selado somente para decisão high CORRIGIR do mesmo snapshot",
    )
    apply_cmd.set_defaults(func=cmd_apply)

    rollback = sub.add_parser("rollback", help="restaura valores pré-apply")
    rollback.add_argument("--db", default=str(DEFAULT_DB))
    rollback.add_argument("--project-id", required=True)
    rollback.add_argument("--run", required=True)
    rollback.set_defaults(func=cmd_rollback)

    questions = sub.add_parser("questions", help="lista perguntas do run")
    questions.add_argument("--run", required=True)
    questions.set_defaults(func=cmd_questions)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(2)
