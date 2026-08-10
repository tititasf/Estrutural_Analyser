#!/usr/bin/env python3
"""Auditor CLI de evidências do Structural Analyzer.

Adaptadores validation_ready: LAJ, PIL, FV e LV (2026-07-16). O comando ``audit`` é
read-only e produz decisões, achados, perguntas e operações propostas.
``apply`` executa somente operações de alta confiança do mesmo snapshot,
dentro de uma transação e com rollback append-only. Nenhuma regra usa
identificador de item, obra ou pavimento. Cada classe grava exclusivamente na
própria tabela (``CLASS_REGISTRY[classe]["table"]``) — nunca uma junção ou
schema compartilhado entre classes.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
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

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.arete.qa_rag_evidence import load_partitioned_rag
from src.core.pillar_face_beams import enrich_pillar_report_with_beams
from src.core.validation_model import (
    AGENT_PENDING_KEY,
    ORIGEM_NA_AGENTE_MARCADOR,
    ORIGEM_QA_AGENTE,
    adicionar_validacao_campo,
    migrar_validated_fields_legado,
    remover_validacao_campo,
)


DEFAULT_DB = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")
DEFAULT_REPORT_ROOT = REPO_ROOT / "scripts" / "arete" / "relatorios" / "qa_evidencias"
DEFAULT_WEB_EVIDENCE_ROOT = REPO_ROOT / "scripts" / "arete" / "html_fichas"
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

# PIL: base fixa presente em todo item + p_s{face}_l1_n por face REALMENTE
# observada no payload (retangular = A-D; L/U/especial variam). Os campos
# de viga por face (p_s{face}_v_*) são confirmados quando presentes (ver
# PilEvidenceAuditor._audit_face_viga) mas ainda não bloqueiam o selo base
# nesta primeira versão do adaptador — ver docs/PROVENIENCIA-CAMPOS-PIL.md
# seção "Promoção".
REQUIRED_PIL_BASE_FIELDS = ("name", "pilar_segs", "dim", "connections")


def required_pil_fields_for_state(state: dict) -> set[str]:
    required = set(REQUIRED_PIL_BASE_FIELDS)
    links = state.get("links") or {}
    for face in "ABCDEFGH":
        if any(str(key).startswith(f"p_s{face}_") for key in links):
            required.add(f"p_s{face}_l1_n")
    return required


# Cada classe resolve seu próprio conjunto de campos obrigatórios: LAJ é uma
# tupla estática (schema fixo); PIL é uma função (schema varia com a
# geometria do item — faces não são as mesmas em pilar retangular vs L/U).
# Isolado por classe: nunca uma junção/schema compartilhado entre elas.
REQUIRED_FIELDS_BY_CLASS: dict[str, Any] = {
    "LAJ": REQUIRED_LAJ_FIELDS,
    "PIL": required_pil_fields_for_state,
}


def resolve_required_fields(classe: str, state: dict) -> set[str]:
    spec = REQUIRED_FIELDS_BY_CLASS.get(classe, REQUIRED_LAJ_FIELDS)
    return spec(state) if callable(spec) else set(spec)

# Registro global do agente.  O núcleo pode inspecionar todas as classes desde
# já; apenas um adaptador que tenha contrato de proveniência e gates completos
# pode escrever validações.  Isso evita que a facilidade de consulta vire um
# selo semântico prematuro em FV/PIL/LV.
CLASS_REGISTRY = {
    "LAJ": {
        "table": "slabs", "payload_column": "links_json", "geometry_column": "points_json",
        "validation_mode": "validation_ready", "provenance": "docs/PROVENIENCIA-CAMPOS-LAJ.md",
        "diagnostic": "scripts/arete/diagnostico_laj_n1_n2.py",
    },
    "PIL": {
        "table": "pillars", "payload_column": "links_json", "geometry_column": "points_json",
        # 2026-07-15: promovido de diagnostic_only para validation_ready —
        # adaptador PilEvidenceAuditor re-deriva faces/vigas do motor puro
        # (pillar_face_beams.py) e geometria/rótulo bruto (identity/dim/
        # laje). Isolado: escreve exclusivamente na tabela "pillars", nunca
        # cross-classe com LAJ/FV/LV.
        "validation_mode": "validation_ready", "provenance": "docs/PROVENIENCIA-CAMPOS-PIL.md",
        "diagnostic": "scripts/arete/diagnostico_pil_n1_n2.py",
    },
    "FV": {
        "table": "beams", "payload_column": "data_json", "geometry_column": None,
        # 2026-07-16: FvEvidenceAuditor — segmentos/área/dim/apoios locais com prova geométrica.
        # Apply em beams exige colunas de validação; selo completo ainda depende de golden/G2-V.
        "validation_mode": "validation_ready", "provenance": "docs/PROVENIENCIA-CAMPOS-FV.md",
        "diagnostic": "scripts/arete/diagnostico_fv_n1_n2.py",
    },
    "LV": {
        "table": "beams", "payload_column": "data_json", "geometry_column": None,
        # 2026-07-16: LvEvidenceAuditor — 4 contratos A/B×PARA/PASSA + dims e apoio.
        "validation_mode": "validation_ready", "provenance": "docs/PROVENIENCIA-CAMPOS-LV.md",
        "diagnostic": "scripts/arete/diagnostico_lv_n1_n2.py",
    },
}

# Contratos iniciais: descrevem qual família pode receber uma decisão
# *provisória de auditoria* quando há trilha N1 rastreável. Não alteram a
# autoridade dos adaptadores diagnostic_only e jamais liberam apply.
INITIAL_FAMILY_CONTRACTS = {
    "FV": {
        "fundo_exists": "a", "fundo_area": "a", "fundo_dim": "b",
        "fundo_local": "a", "fundo_meta": "c",
    },
    "PIL": {"pilar": "a", "name": "a", "dim": "b", "connections": "b", "face_": "a"},
    "LV": {"lado_": "a", "lv_meta": "c"},
}
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


def _label_text(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    labels = value.get("label") or []
    if not labels or not isinstance(labels[0], dict):
        return None
    text = str(labels[0].get("text") or "").strip()
    return text or None


def _explicit_null(value: Any) -> bool:
    text = (_label_text(value) or "").upper()
    return text in {"SEM LAJE", "NULO", "VAZIO (X)"} or "VAZIO" in text


def polygon_metrics(points: Iterable) -> tuple[float, float] | None:
    """Área e perímetro do contorno fechado, sem assumir retângulo."""
    pts = list(points or [])
    if len(pts) < 4:
        return None
    try:
        normalized = [(float(p[0]), float(p[1])) for p in pts]
    except (TypeError, ValueError, IndexError):
        return None
    if normalized[0] != normalized[-1]:
        normalized.append(normalized[0])
    area2 = sum(
        normalized[index][0] * normalized[index + 1][1]
        - normalized[index + 1][0] * normalized[index][1]
        for index in range(len(normalized) - 1)
    )
    perimeter = sum(
        math.hypot(
            normalized[index + 1][0] - normalized[index][0],
            normalized[index + 1][1] - normalized[index][1],
        )
        for index in range(len(normalized) - 1)
    )
    return abs(area2) / 2.0, perimeter


class WebEvidenceResolver:
    """Indexa fichas granulares que a interface web exibe, sem confiar no estado da UI.

    A ficha HTML é um artefato de apresentação. Ela entra no dossiê com hash,
    versão de arquivo e imagens SVG incorporadas; os dados persistidos/DXF continuam
    sendo a prova primária. Isso evita validação circular por checkbox/localStorage.
    """

    def __init__(self, root: Path, *, enabled: bool = True):
        self.root = root
        self.enabled = enabled
        self._index: dict[str, list[Path]] | None = None

    def _build_index(self) -> None:
        index: dict[str, list[Path]] = {}
        if self.enabled and self.root.exists():
            for path in self.root.rglob("*.html"):
                if path.parent.name.lower() != "lajes":
                    continue
                index.setdefault(path.stem.upper(), []).append(path)
        self._index = index

    @staticmethod
    def _cell_value(raw_html: str, label: str) -> str | None:
        pattern = rf">\s*{re.escape(label)}\s*</td>\s*<td[^>]*>(.*?)</td>"
        match = re.search(pattern, raw_html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        value = re.sub(r"<[^>]+>", " ", match.group(1))
        value = " ".join(html.unescape(value).split())
        return value or None

    def resolve_laj(self, item: str) -> dict:
        if not self.enabled:
            return {"evidence_id": f"web-laj-{item}", "item": item, "state": "disabled"}
        if self._index is None:
            self._build_index()
        candidates = (self._index or {}).get(item.upper(), [])
        if not candidates:
            return {"evidence_id": f"web-laj-{item}", "item": item, "state": "missing"}
        path = max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)
        raw = path.read_text(encoding="utf-8", errors="replace")
        text = html.unescape(raw)
        stages = re.findall(r'<div class="evidence-title"><b>([^<]+)</b>', text, flags=re.IGNORECASE)
        artifacts = re.findall(r'<div class="artifact-path">(.*?)</div>', text, flags=re.IGNORECASE | re.DOTALL)
        return {
            "evidence_id": "web-" + hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16],
            "item": item,
            "state": "available",
            "source_kind": "ficha_granular_html",
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
            "identity": {
                "name": self._cell_value(raw, "Nome"),
                "level": self._cell_value(raw, "Nível"),
                "thickness": self._cell_value(raw, "Espessura"),
                "area": self._cell_value(raw, "Área do contorno"),
            },
            "visual": {
                "embedded_svg_count": len(re.findall(r"<svg\b", raw, flags=re.IGNORECASE)),
                "stages": stages,
                "artifact_paths": [html.unescape(re.sub(r"<[^>]+>", "", value)).strip() for value in artifacts[:8]],
            },
            "authority": "presentation_only; compare with persisted N1/DXF; never read browser localStorage as evidence",
        }


def reconcile_web_evidence(slab: "Slab", evidence: dict) -> dict:
    """Reprova snapshot web que não representa mais a ficha N1 persistida."""
    result = copy.deepcopy(evidence)
    if result.get("state") != "available":
        return result
    identity = result.get("identity") or {}
    expected = {
        "name": slab.name,
        "level": slab.fields.get("laje_nivel") or slab.extra.get("laje_nivel"),
        "thickness": parse_number(slab.fields.get("laje_dim") or slab.extra.get("laje_dim")),
    }
    metrics = polygon_metrics(slab.points)
    expected["area"] = metrics[0] if metrics else None
    mismatches = []
    if identity.get("name") and str(identity["name"]).strip().upper() != slab.name.upper():
        mismatches.append({"field": "name", "persisted": slab.name, "web": identity["name"]})
    for key in ("level", "thickness", "area"):
        persisted = parse_number(expected.get(key))
        web_value = parse_number(identity.get(key))
        if persisted is None or web_value is None:
            continue
        tolerance = max(0.05, abs(persisted) * 0.002) if key == "area" else 0.05
        if abs(persisted - web_value) > tolerance:
            mismatches.append({"field": key, "persisted": persisted, "web": web_value, "tolerance": tolerance})
    result["persisted_comparison"] = {"expected": expected, "mismatches": mismatches}
    if mismatches:
        result["state"] = "stale"
        result["authority"] = "rejected_snapshot; regenerate or locate current granular HTML before visual evidence can support QA"
    return result


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
    def __init__(
        self,
        slabs: list[Slab],
        run_id: str,
        consultive_context: dict[str, dict] | None = None,
        web_evidence: dict[str, dict] | None = None,
    ):
        self.slabs = slabs
        self.by_name = {slab.name: slab for slab in slabs}
        self.run_id = run_id
        self.consultive_context = consultive_context or {}
        self.web_evidence = web_evidence or {}
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
            evidence=[*(evidence or []), *self._web_evidence_reference(slab)],
            operations=operations or [],
            rule_codes=rule_codes or [],
            requires_human=requires_human,
            snapshot_hash=slab.snapshot_hash,
        )

    def _web_evidence_reference(self, slab: Slab) -> list[dict]:
        evidence = self.web_evidence.get(slab.name)
        if not evidence or evidence.get("state") != "available":
            return []
        return [{
            "kind": "web_granular_ficha",
            "evidence_id": evidence["evidence_id"],
            "sha256": evidence["sha256"],
            "path": evidence["path"],
            "authority": "presentation_only",
        }]

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
        if not labels:
            # Sem rótulo vinculado não é evidência de "coerente" — é ausência
            # de prova. Correção do dono (2026-07-17): zero campo confirmado
            # sem 100% de certeza; CONFIRMAR sem nenhum label era falso PASS
            # por omissão, não confirmação real (mesma classe de bug já
            # corrigida em PilEvidenceAuditor._audit_name).
            return self._new_decision(slab, "name", "PENDENTE", "low", "sem rótulo vinculado para comparar com o registro")
        if slab.name.upper() == field_name and slab.name.upper() in texts:
            ops = [] if "name" in slab.validated_fields else self._validation_ops("name", ["label"])
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
        metrics = polygon_metrics(slab.points)
        valid = len(slab.points) >= 4 and bbox is not None and metrics is not None and metrics[0] > 0 and (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0
        if valid and contour:
            ops = [] if "laje_outline_segs" in slab.validated_fields else self._validation_ops("laje_outline_segs", ["contour"])
            return self._new_decision(
                slab, "laje_outline_segs", "CONFIRMAR", "high", "contorno fechado, área e perímetro calculáveis",
                operations=ops,
                evidence=[{"kind": "contour_metrics", "bbox": bbox, "area": metrics[0], "perimeter": metrics[1], "vertices": len(slab.points)}],
            )
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

    def _cut_calculation_issues(self, links: list[dict]) -> list[dict]:
        """Valida a aritmética explícita da ficha de visão de corte.

        Não compara a altura local de corte com a dimensão global da viga: são
        conceitos diferentes. Verifica somente as fórmulas que a própria ficha
        declara, evitando falso positivo entre FV/LV e o recorte da laje.
        """
        issues = []
        groups = (
            ("own", "own_slab_height", "own_dist_top", "own_dist_bottom"),
            ("neighbor", "neigh_slab_height", "neighbor_dist_top", "neighbor_dist_bottom"),
        )
        for index, link in enumerate(links):
            ficha = link.get("ficha") if isinstance(link.get("ficha"), dict) else {}
            beam_height = parse_number(ficha.get("beam_height"))
            for scope, height_key, top_key, bottom_key in groups:
                slab_height = parse_number(ficha.get(height_key))
                top = parse_number(ficha.get(top_key))
                bottom = parse_number(ficha.get(bottom_key))
                values = (beam_height, slab_height, top, bottom)
                if any(value is None for value in values):
                    continue
                calculated_top = beam_height - slab_height - bottom
                if abs(calculated_top - top) > 0.11:
                    issues.append({
                        "cut_index": index, "beam": ficha.get("beam_name"), "scope": scope,
                        "code": "formula_mismatch", "beam_height": beam_height,
                        "slab_height": slab_height, "top": top, "bottom": bottom,
                        "calculated_top": calculated_top,
                    })
                if top < -0.01 or bottom < -0.01:
                    issues.append({
                        "cut_index": index, "beam": ficha.get("beam_name"), "scope": scope,
                        "code": "negative_distance", "beam_height": beam_height,
                        "slab_height": slab_height, "top": top, "bottom": bottom,
                        "formula": ficha.get("neigh_dist_fundo_formula" if scope == "neighbor" else "own_dist_fundo_formula"),
                    })
        return issues

    def _remove_link_op(self, field_id: str, slot: str, link: dict) -> dict:
        return {"op": "remove_link", "field": field_id, "slot": slot, "fingerprint": link_fingerprint(link)}

    def _cut_semantic_repairs(self, links: list[dict], issues: list[dict]) -> list[dict]:
        """Propõe reparo somente quando a própria ficha preservou fonte semântica.

        A regra não escolhe altura por mediana, vizinho arbitrário ou N2. Exige que
        ``own_height``/``neighbor_height`` já identifique a laje correspondente,
        que contradiga a altura geométrica e que a recomposição física seja válida.
        """
        repairs = []
        for issue in issues:
            if issue.get("code") != "negative_distance":
                continue
            index = int(issue.get("cut_index", -1))
            if index < 0 or index >= len(links):
                continue
            link = links[index]
            ficha = link.get("ficha") if isinstance(link.get("ficha"), dict) else {}
            scope = str(issue.get("scope") or "")
            semantic_key = "neighbor_height" if scope == "neighbor" else "own_height"
            geometric_key = "neigh_slab_height" if scope == "neighbor" else "own_slab_height"
            bottom_key = "neighbor_dist_bottom" if scope == "neighbor" else "own_dist_bottom"
            top_key = "neighbor_dist_top" if scope == "neighbor" else "own_dist_top"
            semantic_height = parse_number(ficha.get(semantic_key))
            geometric_height = parse_number(ficha.get(geometric_key))
            beam_height = parse_number(ficha.get("beam_height"))
            top = parse_number(ficha.get(top_key))
            if None in (semantic_height, geometric_height, beam_height, top):
                continue
            repaired_bottom = round(float(beam_height) - float(semantic_height) - float(top), 1)
            if (
                semantic_height <= 0 or beam_height <= 0 or top < 0
                or repaired_bottom < -0.01 or nearly_equal(semantic_height, geometric_height)
            ):
                continue
            repairs.append({
                "op": "repair_cut_ficha", "field": "laje_visao_corte", "slot": "cut_view_geom",
                "fingerprint": link_fingerprint(link), "scope": scope,
                "semantic_key": semantic_key, "height_key": geometric_key,
                "top_key": top_key, "bottom_key": bottom_key,
                "semantic_height": round(float(semantic_height), 1),
                "previous_height": round(float(geometric_height), 1),
                "repaired_bottom": repaired_bottom,
            })
        return repairs

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
        calculation_issues = self._cut_calculation_issues(valid)
        if calculation_issues:
            repairs = self._cut_semantic_repairs(valid, calculation_issues)
            if repairs and len(repairs) == len({(issue.get("cut_index"), issue.get("scope")) for issue in calculation_issues if issue.get("code") == "negative_distance"}):
                self._add_finding(
                    slab, field_id, "LAJ-CUT-SEMANTIC-HEIGHT-REPAIR",
                    "altura geométrica contaminada contradiz altura semântica da laje e gera distância negativa",
                    repairs,
                )
                return self._new_decision(
                    slab, field_id, "CORRIGIR", "high",
                    "altura semântica da laje identificada permite recompor distância física sem negativa",
                    operations=[*operations, *repairs], evidence=repairs,
                    rule_codes=["LAJ-CUT-SEMANTIC-HEIGHT-REPAIR"],
                )
            first_issue = calculation_issues[0]
            cut_number = int(first_issue["cut_index"]) + 1
            beam_name = first_issue.get("beam") or "viga sem nome"
            scope_label = "lado da própria laje" if first_issue.get("scope") == "own" else "lado da laje vizinha"
            observed = (
                f"{slab.name}, recorte {cut_number}, {beam_name}, {scope_label}: "
                f"altura de viga={first_issue.get('beam_height', 'n/d')}, "
                f"altura de laje={first_issue.get('slab_height', 'n/d')}, "
                f"topo={first_issue.get('top', 'n/d')} e fundo={first_issue.get('bottom', 'n/d')}"
            )
            self._add_finding(
                slab, field_id, "LAJ-CUT-CALC-INCONSISTENT",
                "ficha de corte contém distância negativa ou fórmula interna inconsistente",
                calculation_issues,
            )
            self._add_question(
                slab, field_id, "LAJ-CUT-CALC-INCONSISTENT",
                f"{observed}. Recalculei a fórmula da ficha: ela fecha algebricamente, mas produz distância negativa; "
                "por isso recusei normalizá-la para zero e também recusei trocar a dimensão local pela dimensão global da viga. "
                "Qual é a regra geral de proveniência que deve prevalecer para escolher a altura local e impedir essa distância negativa?",
                calculation_issues,
                reasoning={
                    "observed": calculation_issues,
                    "attempted": ["recalcular a igualdade declarada pela própria ficha", "verificar sinal das distâncias", "confirmar contato geométrico do corte"],
                    "rejected": ["comparar diretamente altura local do corte com dimensão global da viga", "normalizar distância negativa para zero sem causa"],
                    "impasse": "A aritmética da ficha é inválida, mas a origem semântica da altura local não pode ser substituída por uma dimensão global de outra classe.",
                    "requested_rule": "Defina como o motor deve escolher a altura local de corte e impedir distância negativa para qualquer combinação laje/viga.",
                },
            )
            return self._new_decision(
                slab, field_id, "REVISAR_HUMANO", "low", "cálculo interno da ficha de corte inconsistente",
                evidence=calculation_issues, rule_codes=["LAJ-CUT-CALC-INCONSISTENT"], requires_human=True,
            )
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


# Faces A–D retangulares; E–H pilares especiais (L/U/multi-face) quando materializadas.
_PIL_FACES = ("A", "B", "C", "D", "E", "F", "G", "H")
_PIL_DIMENSION_RE = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*[/xX]\s*\d+(?:[.,]\d+)?\s*$")
_PIL_BEAM_NAME_RE = re.compile(r"^V[A-Z]*\d+[A-Z0-9._-]*$", re.IGNORECASE)


@dataclass
class Pillar:
    id: str
    project_id: str
    name: str
    points: list
    links: dict
    sides_data: dict
    extra: dict
    validated_fields: set[str]
    na_fields: set[str]
    validated_link_classes: dict
    na_link_classes: dict
    na_reasons: dict
    is_validated: bool
    raw_columns: dict[str, Any]

    @property
    def bbox(self) -> tuple[float, float, float, float] | None:
        return point_bbox(self.points)

    @property
    def snapshot_hash(self) -> str:
        payload = {"id": self.id, **self.raw_columns}
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def load_pillars(con: sqlite3.Connection, project_id: str) -> list[Pillar]:
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, project_id, name, points_json, links_json, sides_data_json, "
        "extra_data_json, validated_fields_json, na_fields_json, "
        "validated_link_classes_json, na_link_classes_json, na_reasons_json, "
        "is_validated FROM pillars WHERE project_id=? ORDER BY name",
        (project_id,),
    ).fetchall()
    pillars = []
    for row in rows:
        raw = {column: row[column] for column in MUTABLE_COLUMNS}
        pillars.append(Pillar(
            id=row["id"], project_id=row["project_id"], name=row["name"],
            points=json_load(row["points_json"], []),
            links=json_load(row["links_json"], {}),
            sides_data=json_load(row["sides_data_json"], {}),
            extra=json_load(row["extra_data_json"], {}),
            validated_fields=set(json_load(row["validated_fields_json"], [])),
            na_fields=set(json_load(row["na_fields_json"], [])),
            validated_link_classes=json_load(row["validated_link_classes_json"], {}),
            na_link_classes=json_load(row["na_link_classes_json"], {}),
            na_reasons=json_load(row["na_reasons_json"], {}),
            is_validated=bool(row["is_validated"]), raw_columns=raw,
        ))
    return pillars


def load_beams_for_project(con: sqlite3.Connection, project_id: str) -> list[dict]:
    """Vigas do projeto no formato que ``pillar_face_beams`` espera.

    Mesma tabela (``beams``) que alimenta a interpretação SA ao vivo — não é
    um schema paralelo criado só para o auditor.
    """
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT name, data_json, links_json FROM beams WHERE project_id=?",
        (project_id,),
    ).fetchall()
    beams: list[dict] = []
    for row in rows:
        beam = json_load(row["data_json"], {})
        if not isinstance(beam, dict):
            continue
        beam = dict(beam)
        beam["name"] = beam.get("name") or row["name"]
        links = json_load(row["links_json"], {})
        if isinstance(links, dict):
            merged = dict(beam.get("links") or {})
            for key, value in links.items():
                merged.setdefault(key, value)
            beam["links"] = merged
        beams.append(beam)
    return beams


class PilEvidenceAuditor:
    """Adaptador CAD independente para PIL.

    Cada ``_audit_*`` re-deriva o fato a partir de geometria/rótulo bruto
    (``pillar.points``/``pillar.links``, e o motor puro
    ``pillar_face_beams.enrich_pillar_report_with_beams`` para faces/vigas —
    o mesmo motor testado e persistido em produção em 2026-07-15), nunca
    confiando cegamente no que já está gravado. ``CONFIRMAR`` só nasce quando
    a re-derivação bate com o valor persistido.

    Isolado de ``LajEvidenceAuditor`` de propósito: infraestrutura comum
    (``_new_decision``/``_add_finding``) é duplicada, não compartilhada — uma
    mudança de regra em PIL nunca deve poder vazar pro caminho de LAJ.
    """

    def __init__(self, pillars: list[Pillar], beams: list[dict], slabs: list["Slab"], run_id: str):
        self.pillars = pillars
        self.beams = beams
        self.slabs = slabs
        self.run_id = run_id
        self.findings: list[dict] = []
        self.questions: list[dict] = []
        self._face_beams_cache: dict[str, dict] = {}

    def _new_decision(
        self, pillar: Pillar, field_id: str, decision: str, confidence: str, reason: str,
        *, evidence: list[dict] | None = None, operations: list[dict] | None = None,
        rule_codes: list[str] | None = None, requires_human: bool = False,
    ) -> Decision:
        key = f"{self.run_id}|{pillar.project_id}|{pillar.name}|{field_id}|{decision}|{reason}"
        decision_id = "qaev-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return Decision(
            decision_id=decision_id, run_id=self.run_id, project_id=pillar.project_id,
            classe="PIL", item=pillar.name, field_id=field_id, decision=decision,
            confidence=confidence, reason=reason, evidence=evidence or [],
            operations=operations or [], rule_codes=rule_codes or [],
            requires_human=requires_human, snapshot_hash=pillar.snapshot_hash,
        )

    def _add_finding(self, pillar: Pillar, field_id: str, code: str, message: str, evidence: list[dict]) -> None:
        key = f"{pillar.project_id}|{pillar.name}|{field_id}|{code}|{message}"
        self.findings.append({
            "finding_id": "qaev-f-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
            "run_id": self.run_id, "project_id": pillar.project_id, "classe": "PIL",
            "item": pillar.name, "field_id": field_id, "code": code, "message": message,
            "evidence": evidence,
        })

    def _validation_ops(self, *field_ids: str) -> list[dict]:
        return [{"op": "validate_field", "field": field_id, "slots": []} for field_id in field_ids]

    def _present_faces(self, pillar: Pillar) -> list[str]:
        faces = [
            face for face in _PIL_FACES
            if any(str(key).startswith(f"p_s{face}_") for key in pillar.links)
            or face in (pillar.sides_data or {})
        ]
        return faces

    def _geometry_class(self, pillar: Pillar) -> str:
        """Classifica contorno para rigor multi-geometria (ret/L/U/circular/especial)."""
        n = len(pillar.points or [])
        # pontos costumam repetir o fechamento
        unique = n - 1 if n >= 2 and pillar.points[0] == pillar.points[-1] else n
        faces = self._present_faces(pillar)
        metrics = polygon_metrics(pillar.points)
        bbox = pillar.bbox
        if metrics and bbox and unique >= 8:
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            if width > 0 and height > 0:
                aspect = max(width, height) / max(min(width, height), 1e-6)
                area, _perim = metrics
                # círculo inscrito aprox.: área ≈ π·(min/2)² e aspecto ~1
                r = min(width, height) / 2.0
                circle_area = math.pi * r * r
                if aspect <= 1.15 and circle_area > 0 and abs(area - circle_area) / circle_area <= 0.18:
                    return "circular_like"
        if unique <= 5 and len(faces) <= 4:
            return "rectangular"
        if unique in (6, 7) or len(faces) in (5, 6):
            return "L_or_U_like"
        if unique >= 8 or len(faces) >= 6:
            return "special_multi_face"
        return "irregular"

    def _edge_lengths(self, pillar: Pillar, *, min_len: float = 0.5) -> list[float]:
        """Comprimentos de arestas do contorno (prova de dim em L/U/especial)."""
        pts = list(pillar.points or [])
        if len(pts) < 2:
            return []
        try:
            normalized = [(float(p[0]), float(p[1])) for p in pts]
        except (TypeError, ValueError, IndexError):
            return []
        if normalized[0] != normalized[-1]:
            normalized.append(normalized[0])
        edges: list[float] = []
        for index in range(len(normalized) - 1):
            length = math.hypot(
                normalized[index + 1][0] - normalized[index][0],
                normalized[index + 1][1] - normalized[index][1],
            )
            if length >= min_len:
                edges.append(round(length, 1))
        return edges

    def _audit_pilar_segs(self, pillar: Pillar) -> Decision:
        metrics = polygon_metrics(pillar.points)
        bbox = pillar.bbox
        gclass = self._geometry_class(pillar)
        valid = (
            len(pillar.points) >= 4 and bbox is not None and metrics is not None
            and metrics[0] > 0 and (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0
        )
        segments = (pillar.links.get("pilar_segs") or {}).get("segments") or []
        if valid and segments:
            ops = [] if "pilar_segs" in pillar.validated_fields else self._validation_ops("pilar_segs")
            return self._new_decision(
                pillar, "pilar_segs", "CONFIRMAR", "high",
                f"polígono fechado ({gclass}), não degenerado e com segmento vinculado",
                operations=ops,
                evidence=[{
                    "kind": "contour_metrics", "geometry_class": gclass,
                    "bbox": bbox, "area": metrics[0], "perimeter": metrics[1],
                    "vertices": len(pillar.points), "faces": self._present_faces(pillar),
                }],
            )
        return self._new_decision(pillar, "pilar_segs", "PENDENTE", "low", "geometria insuficiente ou sem vínculo")

    def _audit_name(self, pillar: Pillar) -> Decision:
        labels = [x for x in safe_list((pillar.links.get("name") or {}).get("label")) if isinstance(x, dict)]
        texts = {str(x.get("text") or "").strip().upper() for x in labels}
        if not labels:
            # Sem rótulo vinculado não é evidência de "coerente" — é ausência
            # de prova. Correção do dono (2026-07-17): zero campo confirmado
            # sem 100% de certeza; CONFIRMAR sem nenhum label era falso PASS
            # por omissão, não confirmação real.
            return self._new_decision(pillar, "name", "PENDENTE", "low", "sem rótulo vinculado para comparar com o registro")
        if pillar.name.upper() in texts:
            ops = [] if "name" in pillar.validated_fields else self._validation_ops("name")
            return self._new_decision(pillar, "name", "CONFIRMAR", "high", "rótulo do pilar coerente com o registro", operations=ops)
        return self._new_decision(pillar, "name", "REVISAR_HUMANO", "low", "rótulo do pilar diverge do registro", requires_human=True)

    def _audit_dim(self, pillar: Pillar) -> Decision:
        # Fonte de verdade: geometria do polígono vs "Dimensão (b x h)" da ficha —
        # NÃO o link bruto "dim", que pode ter capturado o rótulo de uma
        # viga vizinha em vez da cota do próprio pilar (achado real: P35
        # tinha link "dim" apontando pro texto "V328").
        # Retangular: bbox b×h. L/U/especial: cada cota declarada deve aparecer
        # como aresta do contorno (bbox enganoso). Circular: diâmetro ≈ min(bbox).
        raw_dim = str((pillar.extra.get("fields") or {}).get("Dimensão (b x h)") or "").strip()
        match = _PIL_DIMENSION_RE.match(raw_dim)
        bbox = pillar.bbox
        gclass = self._geometry_class(pillar)
        link_label = _label_text(pillar.links.get("dim"))
        if link_label and _PIL_BEAM_NAME_RE.match(link_label):
            self._add_finding(
                pillar, "dim", "PIL-DIM-LINK-MISLABELED",
                f"link 'dim' aponta para um rótulo de viga ({link_label}), não para a cota do pilar",
                evidence=[{"kind": "label", "text": link_label}],
            )
            # Vínculo contaminado nunca autoriza CONFIRMAR, mesmo que o texto
            # solto de "Dimensão (b x h)" bata com o bbox por coincidência —
            # o próprio dado que a UI destaca pro campo está errado (achado
            # real: campo aprovado com link "dim" apontando pro rótulo de
            # uma viga vizinha). Correção do dono (2026-07-17): zero
            # tolerância a vínculo desconexo, sempre humano decide.
            return self._new_decision(
                pillar, "dim", "REVISAR_HUMANO", "low",
                f"vínculo 'dim' contaminado (aponta para rótulo de viga {link_label}) — não confiável mesmo com bbox coerente",
                requires_human=True,
                evidence=[{"kind": "label", "text": link_label}],
            )
        if not match or not bbox:
            return self._new_decision(
                pillar, "dim", "PENDENTE", "low",
                "dimensão ausente ou não coerente com a geometria",
                evidence=[{"kind": "geometry_class", "geometry_class": gclass}],
            )
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        declared = [parse_number(x) for x in re.split(r"[xX/]", raw_dim)]
        declared_sorted = sorted(d for d in declared if d is not None)
        observed_bbox = sorted([round(width, 1), round(height, 1)])
        edges = self._edge_lengths(pillar)
        evidence_base = {
            "kind": "dim_geometry",
            "geometry_class": gclass,
            "declared": raw_dim,
            "bbox": [round(width, 1), round(height, 1)],
            "edges": edges[:16],
        }

        if gclass == "rectangular":
            if len(declared_sorted) == len(observed_bbox) and all(
                nearly_equal(a, b, tol=1.0) for a, b in zip(declared_sorted, observed_bbox)
            ):
                ops = [] if "dim" in pillar.validated_fields else self._validation_ops("dim")
                return self._new_decision(
                    pillar, "dim", "CONFIRMAR", "high",
                    "dimensão declarada coerente com o bbox do polígono retangular",
                    operations=ops, evidence=[evidence_base],
                )
            return self._new_decision(
                pillar, "dim", "PENDENTE", "low",
                "dimensão retangular não coerente com o bbox",
                evidence=[evidence_base],
            )

        if gclass == "circular_like":
            # b×h iguais ou diâmetro ≈ menor lado do bbox
            diameter = min(width, height)
            if (
                len(declared_sorted) >= 1
                and all(nearly_equal(declared_sorted[0], d, tol=1.5) for d in declared_sorted)
                and nearly_equal(declared_sorted[0], diameter, tol=2.0)
            ):
                ops = [] if "dim" in pillar.validated_fields else self._validation_ops("dim")
                return self._new_decision(
                    pillar, "dim", "CONFIRMAR", "high",
                    "dimensão circular coerente com diâmetro do contorno (min bbox)",
                    operations=ops,
                    evidence=[{**evidence_base, "diameter_obs": round(diameter, 1)}],
                )
            return self._new_decision(
                pillar, "dim", "PENDENTE", "medium",
                "pilar circular_like: dimensão declarada não bate com diâmetro do contorno",
                evidence=[{**evidence_base, "diameter_obs": round(diameter, 1)}],
            )

        # L / U / especial / irregular: bbox NÃO autoriza CONFIRMAR
        if declared_sorted and edges:
            matched = all(
                any(nearly_equal(d, e, tol=1.5) for e in edges)
                for d in declared_sorted
            )
            if matched:
                ops = [] if "dim" in pillar.validated_fields else self._validation_ops("dim")
                return self._new_decision(
                    pillar, "dim", "CONFIRMAR", "high",
                    f"dimensão em geometria {gclass}: cotas declaradas presentes como arestas do contorno",
                    operations=ops, evidence=[evidence_base],
                )
            # bbox match acidental em L/U seria falso-positivo — reportar
            bbox_ok = len(declared_sorted) == 2 and all(
                nearly_equal(a, b, tol=1.0) for a, b in zip(declared_sorted, observed_bbox)
            )
            if bbox_ok:
                self._add_finding(
                    pillar, "dim", "PIL-DIM-NONRECT-BBOX-ONLY",
                    f"geometria {gclass}: bbox bate com b×h mas arestas do contorno não confirmam as cotas — "
                    "não usar bbox como prova em L/U/especial",
                    evidence=[evidence_base],
                )
            return self._new_decision(
                pillar, "dim", "PENDENTE", "medium",
                f"geometria {gclass}: cotas declaradas não encontradas como arestas do contorno",
                evidence=[evidence_base],
            )
        return self._new_decision(
            pillar, "dim", "PENDENTE", "low",
            f"dimensão {gclass} sem arestas mensuráveis ou declaração inválida",
            evidence=[evidence_base],
        )

    def _enriched_report_for(self, pillar: Pillar) -> dict:
        """Roda o motor puro uma vez por pilar e cacheia AMBAS as saídas.

        ``enrich_pillar_report_with_beams`` é a MESMA função que ``main.py``
        chama (``main.py:6407``) para montar ``connections.lajes_conectadas``
        — não há dois motores divergentes. Mas ela produz duas visões
        diferentes do mesmo fato: ``face_beams`` (só passa/para/interior por
        face) e ``lajes`` (a lista completa, incluindo vínculos por
        alinhamento de parede com ``source: beam_wall_alignment`` nas faces
        C/D, que NUNCA aparecem em ``face_beams`` — achado real 2026-07-16,
        P11 face D). Comparar ``connections`` persistido contra ``face_beams``
        ignora essas entradas e gera falso REVISAR_HUMANO; o campo certo pra
        comparar é ``lajes`` (mesma forma que ``connections.details``).
        """
        if pillar.name in self._face_beams_cache:
            return self._face_beams_cache[pillar.name]
        report = {pillar.name: {"name": pillar.name, "points": pillar.points, "lajes": []}}
        try:
            enrich_pillar_report_with_beams(report, self.beams)
        except Exception as exc:  # motor não pode derrubar o auditor
            self._add_finding(pillar, "connections", "PIL-MOTOR-ERROR", f"motor de faces falhou: {exc}", evidence=[])
            result = {"face_beams": {}, "lajes": []}
            self._face_beams_cache[pillar.name] = result
            return result
        entry = report.get(pillar.name, {})
        result = {"face_beams": entry.get("face_beams") or {}, "lajes": entry.get("lajes") or []}
        self._face_beams_cache[pillar.name] = result
        return result

    def _face_beams_for(self, pillar: Pillar) -> dict:
        return self._enriched_report_for(pillar)["face_beams"]

    def _slab_contacts_face(self, pillar: Pillar, face: str, slab_name: str) -> dict | None:
        try:
            from shapely.geometry import Polygon
        except Exception:
            return None
        slab = next((s for s in self.slabs if s.name == slab_name), None)
        if slab is None or len(slab.points) < 3 or len(pillar.points) < 3:
            return None
        try:
            pillar_poly = Polygon(pillar.points)
            slab_poly = Polygon(slab.points)
            if not pillar_poly.is_valid:
                pillar_poly = pillar_poly.buffer(0)
            if not slab_poly.is_valid:
                slab_poly = slab_poly.buffer(0)
            distance = pillar_poly.distance(slab_poly)
        except Exception:
            return None
        if distance > 5.0 and not pillar_poly.intersects(slab_poly):
            return None
        return {"kind": "slab_contact", "slab": slab_name, "distance": round(distance, 3)}

    def _audit_face_laje(self, pillar: Pillar, face: str) -> Decision:
        field_id = f"p_s{face}_l1_n"
        persisted = _label_text(pillar.links.get(field_id))
        explicit_null = _explicit_null(pillar.links.get(field_id))
        side_state = (pillar.sides_data.get(face) or {}).get("l1_n")
        side_is_null = isinstance(side_state, str) and side_state.strip().upper() in ("SEM LAJE", "N/A", "NULO")
        if explicit_null or side_is_null:
            ops = [] if field_id in pillar.validated_fields else self._validation_ops(field_id)
            return self._new_decision(pillar, field_id, "N/A_CONFIRMADO", "high", "face sem laje explicitamente marcada", operations=ops)
        laje_name = persisted or (side_state if isinstance(side_state, str) else None)
        if not laje_name:
            return self._new_decision(pillar, field_id, "PENDENTE", "low", f"face {face} sem estado explícito de laje")
        contact = self._slab_contacts_face(pillar, face, laje_name)
        if contact:
            ops = [] if field_id in pillar.validated_fields else self._validation_ops(field_id)
            return self._new_decision(
                pillar, field_id, "CONFIRMAR", "high", f"laje {laje_name} em contato geométrico com a face {face}",
                operations=ops, evidence=[contact],
            )
        return self._new_decision(pillar, field_id, "PENDENTE", "low", f"laje {laje_name} sem contato geométrico comprovado com a face {face}")

    def _audit_face_viga(self, pillar: Pillar, face: str) -> Decision:
        field_id = f"p_s{face}_v"
        expected = self._face_beams_for(pillar).get(face) or {}
        expected_names: set[str] = set()
        evidence: list[dict] = []
        for slot in ("passa_esq", "passa_dir"):
            beam = expected.get(slot)
            if isinstance(beam, dict) and beam.get("name"):
                expected_names.add(str(beam["name"]).strip().upper())
                if beam.get("evidence_segments"):
                    evidence.append({"kind": "beam_geometry", "slot": slot, "segments": beam["evidence_segments"]})
        for beam in expected.get("para") or []:
            if isinstance(beam, dict) and beam.get("name"):
                expected_names.add(str(beam["name"]).strip().upper())
                if beam.get("evidence_segments"):
                    evidence.append({"kind": "beam_geometry", "slot": "para", "segments": beam["evidence_segments"]})
        interior_names = {
            str(x.get("name")).strip().upper() for x in (expected.get("interior") or [])
            if isinstance(x, dict) and x.get("name")
        }
        persisted_names: set[str] = set()
        for key, value in pillar.links.items():
            if not (str(key).startswith(f"p_s{face}_v_") and str(key).endswith("_n")):
                continue
            text = _label_text(value)
            if text:
                persisted_names.add(text.strip().upper())

        if not expected_names and not interior_names:
            if not persisted_names:
                ops = [] if field_id in pillar.validated_fields else self._validation_ops(field_id)
                return self._new_decision(
                    pillar, field_id, "N/A_CONFIRMADO", "high",
                    f"face {face} sem viga vinculada (motor e persistido concordam)", operations=ops,
                )
            return self._new_decision(
                pillar, field_id, "REVISAR_HUMANO", "low",
                f"face {face} tem viga persistida ({sorted(persisted_names)}) mas o motor não encontra evidência geométrica",
                requires_human=True,
            )
        if interior_names and not expected_names and not persisted_names:
            # Caso 4 (INTERPRETACAO-PILARES-ABCD.md): face embutida no corpo
            # da viga; não se espera abertura/campo p_s{face}_v_* próprio.
            ops = [] if field_id in pillar.validated_fields else self._validation_ops(field_id)
            return self._new_decision(
                pillar, field_id, "CONFIRMAR", "high",
                f"face {face} interior à viga {sorted(interior_names)} (Caso 4); sem abertura própria esperada",
                operations=ops, evidence=[{"kind": "interior", "beams": sorted(interior_names)}],
            )
        if expected_names and expected_names == persisted_names:
            ops = [] if field_id in pillar.validated_fields else self._validation_ops(field_id)
            return self._new_decision(
                pillar, field_id, "CONFIRMAR", "high",
                f"viga(s) {sorted(expected_names)} confirmada(s) por geometria própria (motor) na face {face}",
                operations=ops, evidence=evidence,
            )
        return self._new_decision(
            pillar, field_id, "REVISAR_HUMANO", "low",
            f"face {face}: motor espera {sorted(expected_names or interior_names)}, persistido tem {sorted(persisted_names)} — reprocessar",
            requires_human=True,
        )

    def _audit_connections(self, pillar: Pillar) -> Decision:
        details = ((pillar.links.get("connections") or {}).get("lajes_conectadas") or {}).get("details") or []
        if not isinstance(details, list) or not details:
            return self._new_decision(pillar, "connections", "PENDENTE", "low", "connections sem detalhes vinculados")
        # expected_names por face = união de duas visões do MESMO motor
        # (enrich_pillar_report_with_beams, a mesma função que main.py chama):
        # face_beams (passa_esq/dir/para/interior, cobre A/B) + a lista
        # `lajes` fresca, filtrada só pras entradas source=beam_wall_alignment
        # (cobre C/D por alinhamento de parede, que NUNCA aparecem em
        # face_beams). Usar só face_beams perdia C/D (achado real 2026-07-16,
        # P11 face D); usar só `lajes` perdia A/B (face_beams é a fonte
        # estável pra passa/para — `lajes` de entrada vazia no auditor
        # super-gera wall-alignment pra faces que no cálculo real já estavam
        # cobertas por uma laje de verdade).
        enriched = self._enriched_report_for(pillar)
        face_beams = enriched["face_beams"]
        wall_alignment_by_side: dict[str, set[str]] = {}
        for entry in enriched["lajes"]:
            if not isinstance(entry, dict) or entry.get("source") != "beam_wall_alignment":
                continue
            side = entry.get("side")
            if side not in _PIL_FACES:
                continue
            name = str((entry.get("viga") or {}).get("name") or "").strip().upper()
            if name:
                wall_alignment_by_side.setdefault(side, set()).add(name)
        mismatches = []
        for entry in details:
            if not isinstance(entry, dict):
                continue
            side = entry.get("side")
            if side not in _PIL_FACES:
                continue
            viga = entry.get("viga") or {}
            observed_name = str(viga.get("name") or "").strip().upper()
            if not observed_name:
                continue
            expected = face_beams.get(side) or {}
            expected_names = {
                str((expected.get(slot) or {}).get("name")).strip().upper()
                for slot in ("passa_esq", "passa_dir") if isinstance(expected.get(slot), dict) and expected.get(slot, {}).get("name")
            } | {
                str(b.get("name")).strip().upper() for b in (expected.get("para") or [])
                if isinstance(b, dict) and b.get("name")
            } | {
                str(b.get("name")).strip().upper() for b in (expected.get("interior") or [])
                if isinstance(b, dict) and b.get("name")
            } | wall_alignment_by_side.get(side, set())
            if observed_name not in expected_names:
                mismatches.append({"side": side, "observed": observed_name, "expected": sorted(expected_names)})
        if mismatches:
            return self._new_decision(
                pillar, "connections", "REVISAR_HUMANO", "low",
                f"{len(mismatches)} face(s) de connections divergem do motor de faces",
                evidence=mismatches, requires_human=True,
            )
        ops = [] if "connections" in pillar.validated_fields else self._validation_ops("connections")
        return self._new_decision(
            pillar, "connections", "CONFIRMAR", "high",
            "connections derivado (categoria b) coerente com as faces já confirmadas pelo motor",
            operations=ops,
        )

    def audit(self, selected: set[str] | None = None, include_sealed: bool = False) -> list[Decision]:
        decisions: list[Decision] = []
        for pillar in self.pillars:
            if selected and pillar.name not in selected:
                continue
            if pillar.is_validated and not include_sealed:
                continue
            decisions.append(self._audit_pilar_segs(pillar))
            decisions.append(self._audit_name(pillar))
            decisions.append(self._audit_dim(pillar))
            faces = self._present_faces(pillar)
            gclass = self._geometry_class(pillar)
            if gclass != "rectangular" and len(faces) < 4:
                self._add_finding(
                    pillar, "faces", "PIL-SPECIAL-FACE-COVERAGE",
                    f"geometria {gclass} com apenas {len(faces)} face(s) materializada(s) no payload",
                    evidence=[{"faces": faces, "geometry_class": gclass}],
                )
            for face in faces:
                decisions.append(self._audit_face_laje(pillar, face))
                decisions.append(self._audit_face_viga(pillar, face))
            decisions.append(self._audit_connections(pillar))
        return decisions


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

_CONFIDENCE_SCORE = {"high": 1.0, "medium": 0.70, "low": 0.35}
_DECISION_SCORE = {
    "CONFIRMAR": 1.0, "N/A_CONFIRMADO": 0.95, "PENDENTE": 0.50,
    "TRILHA_N1_OBSERVADA": 0.50, "CORRIGIR": 0.25, "REVISAR_HUMANO": 0.20,
}


def _item_scorecards(decisions: list[Decision], findings: list[dict], questions: list[dict]) -> list[dict]:
    """Score explícito: confiança da evidência × segurança da decisão."""
    by_item: dict[tuple[str, str], list[Decision]] = {}
    for decision in decisions:
        by_item.setdefault((decision.classe, decision.item), []).append(decision)
    cards = []
    multi_class = len({decision.classe for decision in decisions}) > 1
    for (classe, item), rows in sorted(by_item.items()):
        values = [
            _CONFIDENCE_SCORE.get(row.confidence, 0.0) * _DECISION_SCORE.get(row.decision, 0.0)
            for row in rows
        ]
        item_findings = [x for x in findings if x.get("item") == item and x.get("classe", classe) == classe]
        item_questions = [x for x in questions if x.get("item") == item and x.get("classe", classe) == classe]
        uncertain = [row.field_id for row in rows if row.decision not in {"CONFIRMAR", "N/A_CONFIRMADO"}]
        score = round(100 * sum(values) / max(1, len(values)), 1)
        cards.append({
            "item": f"{classe}:{item}" if multi_class else item, "classe": classe, "item_original": item,
            "score_confianca": score,
            "faixa": "alta" if score >= 90 else "media" if score >= 70 else "baixa",
            "campos_revisados": len(rows), "campos_incerto": sorted(uncertain),
            "achados": [x.get("code") for x in item_findings],
            "perguntas": [x.get("question_id") for x in item_questions],
            "decisoes": {key: sum(row.decision == key for row in rows) for key in sorted({row.decision for row in rows})},
        })
    return cards


def _append_session_ledger(root: Path, entry: dict) -> None:
    """Ledger append-only entre execuções; cada run mantém também seu dossiê local."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / "registro_sessoes.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    rows = read_jsonl(root / "registro_sessoes.jsonl")
    recurrence: dict[str, int] = {}
    for row in rows:
        for fields in (row.get("campos_incerto") or {}).values():
            for field_id in fields:
                recurrence[field_id] = recurrence.get(field_id, 0) + 1
    (root / "recorrencias_duvidas.json").write_text(
        json.dumps({"updated_at": utc_now(), "total_sessoes": len(rows), "campos": recurrence}, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_final_session_summary(
    out_dir: Path, manifest: dict, decisions: list[Decision], findings: list[dict], questions: list[dict], scorecards: list[dict],
) -> None:
    proposed = [operation for decision in decisions for operation in decision.operations]
    uncertain = [card for card in scorecards if card["faixa"] != "alta"]
    lines = [
        "# Resumo final da sessão QA", "",
        f"- Sessão: `{manifest['run_id']}`", f"- Modo: `{manifest['mode']}`",
        f"- Interpretado: {len(decisions)} campos/vínculos em {len(scorecards)} item(ns).",
        f"- Ajustes propostos: {len(proposed)} (nenhum é aplicado nesta auditoria read-only).",
        f"- Achados: {len(findings)}; dúvidas humanas: {len(questions)}.",
        f"- Itens com confiança média/baixa: {len(uncertain)}.", "",
        "## Score por item", "",
    ]
    for card in scorecards:
        notes = []
        if card["campos_incerto"]:
            notes.append("incertos=" + ", ".join(card["campos_incerto"]))
        if card["achados"]:
            notes.append("achados=" + ", ".join(card["achados"]))
        lines.append(f"- {card['item']}: **{card['score_confianca']:.1f}/100** ({card['faixa']})" + (f" — {'; '.join(notes)}" if notes else ""))
    lines += ["", "## Rastreabilidade", "", "- Decisões: `decisoes.jsonl`; scores: `scores_itens.jsonl`; dúvidas: `perguntas.jsonl`; correções propostas: `fix_requests.md`.", "- O ledger global append-only está em `../registro_sessoes.jsonl`."]
    (out_dir / "resumo_final.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reports(
    out_dir: Path,
    manifest: dict,
    decisions: list[Decision],
    findings: list[dict],
    questions: list[dict],
    web_evidence: Iterable[dict] = (),
) -> None:
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "manifesto.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    write_jsonl(out_dir / "decisoes.jsonl", (asdict(x) for x in decisions))
    write_jsonl(out_dir / "achados.jsonl", findings)
    write_jsonl(out_dir / "perguntas.jsonl", questions)
    write_jsonl(out_dir / "evidencias_web.jsonl", web_evidence)
    scorecards = _item_scorecards(decisions, findings, questions)
    write_jsonl(out_dir / "scores_itens.jsonl", scorecards)

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
    out_abs = str(out_dir.resolve())
    summary = [
        "# Resumo — Agente QA de Evidências",
        "",
        f"- Run: `{manifest['run_id']}`",
        f"- Projeto: `{manifest['project_id']}`",
        f"- Itens: {len(manifest['items'])}",
        f"- Decisões: {len(decisions)}",
        f"- Achados: {len(findings)}",
        f"- Perguntas: {len(questions)}",
        f"- Dossiê (absoluto): `{out_abs}`",
        f"- Decisões JSONL: `{(out_dir / 'decisoes.jsonl').resolve()}`",
        f"- Achados JSONL: `{(out_dir / 'achados.jsonl').resolve()}`",
        f"- Manifesto: `{(out_dir / 'manifesto.json').resolve()}`",
        "",
        "## Decisões",
        "",
    ]
    summary += [f"- {key}: {value}" for key, value in sorted(counts.items())]
    summary += [
        "",
        "## Handoff",
        "",
        "- HTML/checkbox da app são apresentação; prova = este dossiê.",
        "- Checklist anti-super-selo: `squads/qa-global-evidencias/checklists/operational-anti-superselo-checklist.md`.",
        "- Abrir dossiê: `python scripts/arete/qa_open_latest_dossier.py --project-id "
        f"{manifest['project_id']} --open`.",
        "",
    ]
    # KPIs treino vs validação + quadro de pavimento (paths absolutos)
    try:
        from scripts.arete.qa_handoff_assets import handoff_extra_lines, kpis_treino_validacao

        kpis = kpis_treino_validacao(decisions, findings, questions)
        (out_dir / "kpis_treino_validacao.json").write_text(
            json.dumps(kpis, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        summary += handoff_extra_lines(
            classe=manifest.get("classe"),
            project_id=manifest.get("project_id"),
            decisions=decisions,
            findings=findings,
            questions=questions,
        )
        summary.append(f"- KPIs JSON: `{(out_dir / 'kpis_treino_validacao.json').resolve()}`")
        summary.append("")
    except Exception:
        pass
    (out_dir / "resumo.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    _write_final_session_summary(out_dir, manifest, decisions, findings, questions, scorecards)
    # Memória de erro tipada (cross-sessão) — não contamina classes
    if findings:
        try:
            from scripts.arete.qa_error_memory import append_errors
            append_errors(
                findings if isinstance(findings[0], dict) else [asdict(f) if hasattr(f, "__dict__") else f for f in findings],
                run_id=manifest.get("run_id"),
                project_id=manifest.get("project_id"),
                classe=manifest.get("classe") if manifest.get("classe") != "ALL" else None,
            )
        except Exception:
            pass
    _append_session_ledger(out_dir.parent, {
        "at": utc_now(), "run_id": manifest["run_id"], "mode": manifest["mode"],
        "project_id": manifest["project_id"], "classe": manifest["classe"],
        "items": manifest["items"], "decisions": counts, "findings": len(findings),
        "questions": len(questions), "scores": {x["item"]: x["score_confianca"] for x in scorecards},
        "campos_incerto": {x["item"]: x["campos_incerto"] for x in scorecards if x["campos_incerto"]},
        "out_dir": out_abs,
    })


def mutable_columns_for_table(con: sqlite3.Connection, table: str) -> list[str]:
    """Interseção entre MUTABLE_COLUMNS e colunas realmente existentes na tabela.

    `beams` não tem `extra_data_json`; forçar o conjunto completo quebrava
    apply/snapshot de FV/LV.
    """
    existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    cols = [column for column in MUTABLE_COLUMNS if column in existing]
    if not cols:
        raise RuntimeError(f"nenhuma coluna mutável conhecida em {table}")
    return cols


def current_snapshot(con: sqlite3.Connection, item_id: str, table: str = "slabs") -> tuple[str, dict[str, Any]]:
    """Hash+raw das colunas mutáveis do item, na tabela da SUA classe.

    ``table`` isola cada classe na própria tabela (``slabs``/``pillars``/
    ``beams``) — nunca uma junção cross-classe. ``MUTABLE_COLUMNS`` é o mesmo
    conjunto de nomes em todas (mesma convenção de schema do SA).
    """
    con.row_factory = sqlite3.Row
    columns = mutable_columns_for_table(con, table)
    row = con.execute(
        f"SELECT id, {', '.join(columns)} FROM {table} WHERE id=?",
        (item_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"item ausente em {table}: {item_id}")
    raw = {column: row[column] for column in columns}
    payload = {"id": row["id"], **raw}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest(), raw


def apply_operation(state: dict, operation: dict) -> None:
    op = operation["op"]
    links = state["links"]
    validated_fields: dict = state["validated_fields"]  # [2026-07-13] dict com origem, ver src/core/validation_model.py
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
        adicionar_validacao_campo(validated_fields, field_id, ORIGEM_QA_AGENTE)
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
        remover_validacao_campo(validated_fields, field_id, origem=ORIGEM_QA_AGENTE)
        validated_links.pop(field_id, None)
    elif op == "mark_na":
        # [2026-07-13] N/A não é "validado" por nenhuma origem — fica fora do
        # sistema de selo (calcular_selos_item já trata na_fields como
        # resolvido independente de origem), só o motivo em na_reasons importa.
        # [2026-07-17] O motivo grava o marcador de origem do agente (decisão
        # do dono: N/A decidido pelo agente aparece laranja no app, distinto
        # de N/A marcado manualmente por um humano) — ver
        # src/core/validation_model.py::ORIGEM_NA_AGENTE_MARCADOR.
        na_fields.add(field_id)
        reason = operation.get("reason") or "N/A confirmado pelo QA"
        na_reasons[field_id] = ORIGEM_NA_AGENTE_MARCADOR + reason
    elif op == "repair_cut_ficha":
        slot = operation["slot"]
        entries = safe_list((links.get(field_id) or {}).get(slot))
        target = next((entry for entry in entries if isinstance(entry, dict) and link_fingerprint(entry) == operation["fingerprint"]), None)
        if target is None:
            raise RuntimeError("corte alvo não encontrado para reparo de ficha")
        ficha = target.setdefault("ficha", {})
        height = float(operation["semantic_height"])
        bottom = float(operation["repaired_bottom"])
        top = float(ficha.get(operation["top_key"]) or 0)
        beam = float(ficha.get("beam_height") or 0)
        ficha[operation["height_key"]] = fmt_number(height)
        ficha[operation["bottom_key"]] = fmt_number(bottom)
        if operation["scope"] == "neighbor":
            ficha["neighbor_dist_bottom_s_painel"] = fmt_number(bottom)
            ficha["neighbor_dist_bottom_c_painel"] = fmt_number(bottom - 2.0 + 4.0)
            ficha["neigh_dist_fundo_formula"] = (
                f"bh({beam:.0f}) − H_laje_viz({height:.0f}) − d_topo({top:.0f}) = {bottom:.0f} cm "
                f"(sem painel) / {(bottom + 2.0):.0f} cm (−2cm painel da laje + 4cm sarrafo/fundo viga)"
            )
        else:
            ficha["own_dist_bottom_s_painel"] = fmt_number(bottom)
            ficha["own_dist_bottom_c_painel"] = fmt_number(bottom - 2.0 + 4.0)
            ficha["own_dist_fundo_formula"] = (
                f"bh({beam:.0f}) − H_laje({height:.0f}) − d_topo({top:.0f}) = {bottom:.0f} cm "
                f"(sem painel) / {(bottom + 2.0):.0f} cm (−2cm painel da laje + 4cm sarrafo/fundo viga)"
            )
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
    selected = set(args.item or []) or None
    selected_slabs = [x for x in slabs if (not selected or x.name in selected) and (args.include_sealed or not x.is_validated)]
    web_mode = getattr(args, "web_evidence", "auto")
    web_root = Path(getattr(args, "web_root", DEFAULT_WEB_EVIDENCE_ROOT))
    resolver = WebEvidenceResolver(web_root, enabled=web_mode != "off")
    web_evidence = {
        slab.name: reconcile_web_evidence(slab, resolver.resolve_laj(slab.name))
        for slab in selected_slabs
    }
    missing_web = [name for name, evidence in web_evidence.items() if evidence.get("state") != "available"]
    if web_mode == "required" and missing_web:
        raise SystemExit("ficha granular web ausente para: " + ", ".join(sorted(missing_web)))
    auditor = LajEvidenceAuditor(
        slabs,
        run_id,
        consultive_context=consultive_context,
        web_evidence=web_evidence,
    )
    decisions = auditor.audit(selected=selected, include_sealed=args.include_sealed)
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
        "web_evidence": {
            "mode": web_mode,
            "root": str(web_root.resolve()),
            "available": len(web_evidence) - len(missing_web),
            "missing": sorted(missing_web),
            "policy": "presentation_only; persisted N1/DXF remain primary evidence",
        },
    }
    write_reports(out_dir, manifest, decisions, auditor.findings, auditor.questions, web_evidence.values())
    print(json.dumps({
        "run_id": run_id,
        "out_dir": str(out_dir),
        "decisions": len(decisions),
        "findings": len(auditor.findings),
        "questions": len(auditor.questions),
        "web_evidence_available": len(web_evidence) - len(missing_web),
    }, ensure_ascii=False))
    return 0


def resolve_project_scope(
    con: sqlite3.Connection, *, project_id: str | None, obra: str | None, pav: str | None,
) -> str:
    """Resolve escopo sem adivinhar projeto quando a obra possui reprocessamentos."""
    if project_id:
        row = con.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            raise SystemExit(f"project_id inexistente: {project_id}")
        return str(row[0])
    if not obra or not pav:
        raise SystemExit("informe --project-id ou o par completo --obra e --pav")
    rows = con.execute(
        "SELECT id FROM projects WHERE lower(work_name)=lower(?) AND lower(pavement_name)=lower(?) "
        "ORDER BY updated_at DESC",
        (obra, pav),
    ).fetchall()
    if len(rows) != 1:
        raise SystemExit(
            f"escopo ambíguo ou ausente para obra={obra!r}, pav={pav!r}: "
            f"{len(rows)} projeto(s). Use --project-id explicitamente."
        )
    return str(rows[0][0])


def load_rag_consultations(
    con: sqlite3.Connection, classes: Iterable[str], *,
    family: str | None = None, field: str | None = None,
    tiers: Iterable[str] | None = None, obra: str | None = None,
    pav: str | None = None, limit: int = 50,
    require_tier: bool = False,
) -> dict[str, list[dict]]:
    """Consulta a memória semântica da app sem promovê-la a prova do item.

    O schema atual de ``semantic_rag_kb`` ainda não carrega tier/campo estruturado;
    por isso toda entrada é etiquetada como consulta contextual e só pode elevar
    hipótese depois que a evidência CAD local concordar.
    """
    return load_partitioned_rag(
        con, classes, family=family, field=field, tiers=tiers,
        obra=obra, pav=pav, limit=limit, require_tier=require_tier,
    )


def load_session_index_b1_context(
    index_dir: Path, classes: Iterable[str], *,
    family: str | None = None, field: str | None = None,
    tiers: Iterable[str] | None = None, obra: str | None = None,
    pav: str | None = None, limit: int = 8,
) -> tuple[dict[str, list[dict]], dict]:
    """Consulta B1 (qa_session_index, MASTERPLAN-MINIRAG-QA-N1.md fase D3) como
    camada extra, opcional e best-effort — nunca substitui nem bloqueia B2.

    Qualquer falha (índice ausente, stale, corrompido, dependência de
    embedding indisponível) devolve contexto vazio + status no manifesto; o
    caminho ``load_partitioned_rag`` (B2) segue 100% intocado. Por isso B1
    NUNCA participa do check de ``--rag-evidence required`` — required
    continua medindo só a partição exata de ``semantic_rag_kb``, como sempre
    mediu; mudar essa semântica quebraria o invariante do contrato QA↔RAG.
    """
    classes = list(classes)
    empty = {classe: [] for classe in classes}
    status: dict = {"path": str(index_dir), "available": False, "error": None}
    try:
        from scripts.arete.qa_session_index import SessionIndex
        idx = SessionIndex(index_dir)
    except Exception as exc:  # índice ausente/stale/corrompido: degrada, não bloqueia
        status["error"] = str(exc)
        return empty, status
    try:
        result: dict[str, list[dict]] = {}
        for classe in classes:
            hits = idx.b1_query(
                classe=classe, familia=family, field=field,
                tier=list(tiers) if tiers else None, obra=obra, pav=pav,
                top_k=limit,
            )
            for hit in hits:
                hit["kind"] = "rag_semantic_context_b1"
            result[classe] = hits
        status["available"] = True
        status["b1_manifest"] = idx.manifest.get("b1", {})
        return result, status
    finally:
        idx.close()


def _payload_geometry(payload: dict) -> list:
    return _context_points(payload)


def _class_payload_keys(payload: dict, classe: str) -> set[str]:
    """Separa as leituras de viga por contrato sem expor metadados internos.

    Em FV, ``fv_is_h`` e o escalar raiz ``seg_bottom`` são estado transitório
    do interpretador (orientação e contagem bruta antes da consolidação). A
    ficha/contrato público usa os slots ``viga_fundo_*`` e
    ``links.viga_segs.seg_bottom``. Auditar os escalares como campo criava
    pendência quando a consolidação legítima alterava a contagem de painéis.
    """
    keys = set(payload)
    for container in ("fields", "links"):
        value = payload.get(container)
        if isinstance(value, dict):
            keys.update(value)
    if classe == "FV":
        return {
            key for key in keys
            if key.startswith(("viga_fundo", "fv_")) and key != "fv_is_h"
        }
    if classe == "LV":
        return {key for key in keys if key.startswith(("viga_a_", "viga_b_", "lv_", "seg_a", "seg_b", "seg_c"))}
    return keys


def discover_class_inventory(
    con: sqlite3.Connection, *, project_id: str, classe: str, selected: set[str] | None,
    include_sealed: bool,
) -> dict:
    """Inventário read-only de contrato observado, destinado aos adaptadores em evolução."""
    spec = CLASS_REGISTRY[classe]
    con.row_factory = sqlite3.Row
    table_columns = {row[1] for row in con.execute(f"PRAGMA table_info({spec['table']})")}
    required = {"id", "project_id", "name", "is_validated", spec["payload_column"]}
    missing = sorted(required - table_columns)
    if missing:
        raise RuntimeError(f"schema de {classe} incompleto na tabela {spec['table']}: {missing}")
    rows = con.execute(
        f"SELECT * FROM {spec['table']} WHERE project_id=? ORDER BY name", (project_id,)
    ).fetchall()
    items = []
    field_frequency: dict[str, int] = {}
    for row in rows:
        if selected and row["name"] not in selected:
            continue
        if not include_sealed and bool(row["is_validated"]):
            continue
        payload = json_load(row[spec["payload_column"]], {})
        keys = _class_payload_keys(payload, classe)
        for key in keys:
            field_frequency[key] = field_frequency.get(key, 0) + 1
        points = json_load(row[spec["geometry_column"]], []) if spec["geometry_column"] else _payload_geometry(payload)
        metrics = polygon_metrics(points)
        items.append({
            "id": row["id"], "item": row["name"], "sealed": bool(row["is_validated"]),
            "fields": sorted(keys), "field_count": len(keys),
            "geometry": {
                "points": len(points), "bbox": point_bbox(points),
                "area": metrics[0] if metrics else None, "perimeter": metrics[1] if metrics else None,
            },
        })
    return {
        "classe": classe, "table": spec["table"], "payload_column": spec["payload_column"],
        "validation_mode": spec["validation_mode"], "provenance": spec["provenance"],
        "diagnostic": spec["diagnostic"], "items": items,
        "field_frequency": dict(sorted(field_frequency.items())),
        "schema_columns": sorted(table_columns),
    }


def cmd_discover(args: argparse.Namespace) -> int:
    """Produz um dossiê global de cobertura sem validar ou modificar a base."""
    db = Path(args.db)
    requested = list(CLASS_REGISTRY) if args.classe == "ALL" else [args.classe]
    with sqlite3.connect(db) as con:
        project_id = resolve_project_scope(
            con, project_id=args.project_id, obra=args.obra, pav=args.pav,
        )
        selected = set(args.item or []) or None
        inventories = [
            discover_class_inventory(
                con, project_id=project_id, classe=classe, selected=selected,
                include_sealed=args.include_sealed,
            )
            for classe in requested
        ]
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S") + "_global_" + uuid.uuid4().hex[:8]
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_REPORT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": 1, "run_id": run_id, "created_at": utc_now(),
        "mode": "global_read_only_discovery", "db": str(db.resolve()), "project_id": project_id,
        "classes": requested, "include_sealed": bool(args.include_sealed),
        "authority": "diagnostic_only except validation_ready adapters; no database mutation",
    }
    (out_dir / "manifesto.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "inventario_classes.json").write_text(json.dumps(inventories, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    lines = ["# Inventário global do Agente QA de Evidências", "", f"- Sessão: `{run_id}`", f"- Projeto: `{project_id}`", ""]
    for inventory in inventories:
        lines += [
            f"## {inventory['classe']} — {inventory['validation_mode']}", "",
            f"- Itens no escopo: {len(inventory['items'])}",
            f"- Campos observados: {len(inventory['field_frequency'])}",
            f"- Proveniência: `{inventory['provenance'] or 'PENDENTE: criar contrato por classe'}`",
            f"- Diagnóstico canônico: `{inventory['diagnostic']}`", "",
        ]
    (out_dir / "resumo_global.md").write_text("\n".join(lines), encoding="utf-8")
    _append_session_ledger(out_dir.parent, {
        "at": utc_now(), "run_id": run_id, "mode": manifest["mode"], "project_id": project_id,
        "classe": ",".join(requested), "items": [item["item"] for inv in inventories for item in inv["items"]],
        "inventories": {inv["classe"]: {"items": len(inv["items"]), "fields": len(inv["field_frequency"]), "mode": inv["validation_mode"]} for inv in inventories},
        "out_dir": str(out_dir),
    })
    print(json.dumps({"run_id": run_id, "out_dir": str(out_dir), "project_id": project_id, "classes": requested}, ensure_ascii=False))
    return 0


def _generic_snapshot(row: sqlite3.Row, columns: Iterable[str]) -> str:
    payload = {column: row[column] for column in columns if column in row.keys()}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _generic_link_entries(payload: dict, field_id: str) -> list[dict]:
    links = payload.get("links") if isinstance(payload.get("links"), dict) else payload
    value = links.get(field_id) if isinstance(links, dict) else None
    if not isinstance(value, dict):
        return []
    entries: list[dict] = []
    for slot, raw_entries in value.items():
        for entry in safe_list(raw_entries):
            if isinstance(entry, dict):
                entries.append({"slot": slot, **entry})
    return entries


def _fv_segment_area_trace(payload: dict, field_id: str) -> list[dict]:
    """Resolve a prova observacional do slot FV sem inventar semântica.

    ``viga_fundo_seg_N_exists`` é um marcador escalar legado: ele não possui
    pontos próprios. A entidade que materializa sua existência é o contorno
    local correspondente em ``viga_fundo_seg_N_area_segs.contour``. Esse
    vínculo continua sendo apenas trilha N1 (nunca uma confirmação CAD nem um
    selo) e só é aceito quando o próprio snapshot conserva um polígono fechado
    de área positiva. Assim o auditor não pede uma regra humana para todo
    segmento já representado, e também não confunde linha/parede com fundo.
    """
    match = re.fullmatch(r"viga_fundo_seg_(\d+)_exists", str(field_id))
    if not match:
        return []
    segment_index = int(match.group(1))
    links = payload.get("links") if isinstance(payload.get("links"), dict) else payload
    if not isinstance(links, dict):
        return []
    area_slots = links.get(f"viga_fundo_seg_{segment_index}_area_segs")
    if not isinstance(area_slots, dict):
        return []

    entries: list[dict] = []
    for raw in safe_list(area_slots.get("contour")):
        if not isinstance(raw, dict):
            continue
        points: list[tuple[float, float]] = []
        for point in safe_list(raw.get("points")):
            try:
                points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError, IndexError):
                continue
        if len(points) < 4 or points[0] != points[-1]:
            continue
        area2 = sum(
            first[0] * second[1] - second[0] * first[1]
            for first, second in zip(points, points[1:])
        )
        if abs(area2) * 0.5 <= 0.05:
            continue
        if raw.get("geometry_role") not in {None, "area_fundo"}:
            continue
        entries.append({
            "slot": "contour",
            **raw,
            "derived_from_field": f"viga_fundo_seg_{segment_index}_area_segs",
            "trace_role": "fv_closed_local_area",
        })
    return entries


def _generic_trace_entries(payload: dict, classe: str, field_id: str) -> list[dict]:
    """Obtém evidência do próprio campo ou de seu slot estrutural exclusivo."""
    direct = _generic_link_entries(payload, field_id)
    if direct or classe != "FV":
        return direct
    return _fv_segment_area_trace(payload, field_id)


def _field_family(field_id: str, classe: str) -> str:
    if classe == "PIL":
        match = re.match(r"p_s([A-H])_(.+)", field_id)
        return f"face_{match.group(1)}_{match.group(2).split('_')[0]}" if match else field_id.split("_", 1)[0]
    if classe == "FV":
        match = re.match(r"viga_fundo_seg_\d+_(.+)", field_id)
        return f"fundo_{match.group(1).split('_')[0]}" if match else (
            "fundo_meta" if field_id.startswith("viga_fundo") else field_id
        )
    if classe == "LV":
        match = re.match(r"viga_([ab])_seg_\d+_(.+)", field_id)
        return f"lado_{match.group(1).upper()}_{match.group(2).split('_')[0]}" if match else (
            "lv_meta" if field_id.startswith(("lv_", "seg_a", "seg_b", "seg_c")) else field_id
        )
    return field_id


def _initial_contract_category(classe: str, family: str) -> str | None:
    contracts = INITIAL_FAMILY_CONTRACTS.get(classe, {})
    if family in contracts:
        return contracts[family]
    return next((value for prefix, value in contracts.items() if family.startswith(prefix)), None)


def generic_class_review(
    con: sqlite3.Connection, *, project_id: str, classe: str, run_id: str,
    selected: set[str] | None, include_sealed: bool,
) -> tuple[list[Decision], list[dict], list[dict], list[dict]]:
    """Audita evidência observável de classes ainda sem permissão de escrita.

    Nenhuma decisão aqui contém operações. A ausência de contrato específico
    vira pendência explicada, não confirmação baseada no próprio payload N1.
    """
    spec = CLASS_REGISTRY[classe]
    con.row_factory = sqlite3.Row
    columns = [row[1] for row in con.execute(f"PRAGMA table_info({spec['table']})")]
    rows = con.execute(f"SELECT * FROM {spec['table']} WHERE project_id=? ORDER BY name", (project_id,)).fetchall()
    decisions: list[Decision] = []
    findings: list[dict] = []
    questions: list[dict] = []
    records: list[dict] = []
    missing_contracts: dict[str, list[dict]] = {}
    for row in rows:
        name = str(row["name"] or "").strip()
        if (selected and name not in selected) or (not include_sealed and bool(row["is_validated"])):
            continue
        payload = json_load(row[spec["payload_column"]], {})
        fields = sorted(_class_payload_keys(payload, classe))
        snapshot_hash = _generic_snapshot(row, columns)
        records.append({"id": row["id"], "name": name, "snapshot_hash": snapshot_hash, "classe": classe})
        if not name:
            fields = ["name", *fields]
        missing_by_family: dict[str, list[str]] = {}
        for field_id in fields:
            entries = _generic_trace_entries(payload, classe, field_id)
            family = _field_family(field_id, classe)
            category = _initial_contract_category(classe, family)
            has_trace = any(
                entry.get("source") or entry.get("points") or entry.get("pos") or entry.get("text")
                for entry in entries
            )
            prevalidated = field_id in set(json_load(row["validated_fields_json"], [])) if "validated_fields_json" in columns else False
            if has_trace and category:
                decision, confidence, reason = (
                    "TRILHA_N1_OBSERVADA", "medium",
                    f"contrato inicial categoria ({category}) e ligação interna N1 rastreável; sem adaptador CAD independente não confirma geometria ou vínculo",
                )
            elif has_trace:
                decision, confidence, reason = (
                    "PENDENTE", "medium",
                    "há ligação N1 rastreável, mas a família não consta no contrato inicial de proveniência",
                )
            elif field_id in set(json_load(row["na_fields_json"], [])) if "na_fields_json" in columns else False:
                decision, confidence, reason = (
                    "PENDENTE", "medium",
                    "campo está N/A no N1, porém a regra de inaplicabilidade da classe ainda não foi formalizada",
                )
            else:
                decision, confidence, reason = (
                    "PENDENTE", "low",
                    "campo não apresenta cadeia de evidência observável independente no snapshot N1",
                )
                missing_by_family.setdefault(family, []).append(field_id)
            key = f"{run_id}|{project_id}|{classe}|{name}|{field_id}|{decision}"
            decisions.append(Decision(
                decision_id="qaev-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
                run_id=run_id, project_id=project_id, classe=classe, item=name or "<sem_nome>",
                field_id=field_id, decision=decision, confidence=confidence, reason=reason,
                evidence=[{
                    "kind": "n1_persisted_link", "entries": len(entries), "prevalidated": prevalidated,
                    "contract_category": category, "contract": spec["provenance"],
                }],
                requires_human=False, snapshot_hash=snapshot_hash,
            ))
        if missing_by_family:
            for family, field_ids in missing_by_family.items():
                missing_contracts.setdefault(family, []).append({"item": name or "<sem_nome>", "fields": sorted(field_ids)})
    if missing_contracts:
        observed = {
            family: {"itens": len(rows), "exemplos": rows[:5]}
            for family, rows in sorted(missing_contracts.items())
        }
        reasoning = {
            "observed": observed,
            "attempted": ["ler vínculo persistido", "procurar texto/posição/geometria de origem", "respeitar N/A e validação humana existentes"],
            "rejected": ["usar o valor N1 como prova de si mesmo", "copiar convenção de LAJ", "inferir por proximidade ou por N2/N4"],
            "impasse": "O contrato inicial define a prova esperada, mas o snapshot N1 não preserva uma trilha direta para as famílias observadas.",
            "requested_rule": "Confirme qual entidade/campo de origem deve ser persistido para cada família, ou declare a condição N/A. O agente então poderá transformar estas pendências em decisões verificáveis sem alterar casos simples.",
        }
        question_key = f"{run_id}|{classe}|contract"
        questions.append({
            "question_id": "qaev-q-" + hashlib.sha256(question_key.encode("utf-8")).hexdigest()[:16],
            "classe": classe, "item": f"{classe}:contrato", "field_id": "contrato_de_proveniencia",
            "code": f"{classe}-CONTRACT-MISSING", "requires_human": True,
            "question": f"O contrato inicial de {classe} prevê evidência para {len(missing_contracts)} família(s), mas os itens abaixo não preservam trilha independente. Qual entidade CAD/ficha deve o motor registrar em cada família, ou quando ela é N/A?",
            "reasoning": reasoning,
        })
    return decisions, findings, questions, records


def cmd_review(args: argparse.Namespace) -> int:
    """Revisão global por item/campo; LAJ/PIL/FV/LV usam adaptadores com decisões confirmáveis."""
    db = Path(args.db)
    requested = list(CLASS_REGISTRY) if args.classe == "ALL" else [args.classe]
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S") + "_review_" + uuid.uuid4().hex[:8]
    selected = set(args.item or []) or None
    decisions: list[Decision] = []
    findings: list[dict] = []
    questions: list[dict] = []
    records: list[dict] = []
    rag_context: dict[str, list[dict]] = {}
    with sqlite3.connect(db) as con:
        project_id = resolve_project_scope(con, project_id=args.project_id, obra=args.obra, pav=args.pav)
        rag_context = load_rag_consultations(
            con, requested, family=args.rag_family, field=args.rag_field,
            tiers=args.rag_tier, obra=args.rag_obra, pav=args.rag_pav,
            limit=args.rag_limit,
            require_tier=bool(args.rag_evidence == "required" and args.rag_tier),
        ) if args.rag_evidence != "off" else {classe: [] for classe in requested}
        if args.rag_evidence == "required":
            missing = [classe for classe, entries in rag_context.items() if not entries]
            if missing:
                raise SystemExit("memória RAG ausente para: " + ", ".join(missing))
            degraded = [
                classe for classe, entries in rag_context.items()
                if any(not entry.get("partition", {}).get("exact", False) for entry in entries)
            ]
            if degraded:
                raise SystemExit("schema RAG não suporta partição requerida para: " + ", ".join(degraded))
        session_b1_context: dict[str, list[dict]] = {classe: [] for classe in requested}
        session_index_status: dict = {"path": None, "available": False, "error": None}
        if args.session_index and args.rag_evidence != "off":
            session_b1_context, session_index_status = load_session_index_b1_context(
                Path(args.session_index), requested,
                family=args.rag_family, field=args.rag_field, tiers=args.rag_tier,
                obra=args.rag_obra, pav=args.rag_pav, limit=args.rag_limit,
            )
            if session_index_status.get("error"):
                print(f"[review] B1 (session-index) indisponível, seguindo só com B2: "
                     f"{session_index_status['error']}", file=sys.stderr)
        for classe in requested:
            if classe == "LAJ":
                slabs = load_slabs(con, project_id)
                context = load_consultive_context(con, project_id, slabs)
                auditor = LajEvidenceAuditor(slabs, run_id, consultive_context=context)
                class_decisions = auditor.audit(selected=selected, include_sealed=args.include_sealed)
                decisions.extend(class_decisions)
                findings.extend(auditor.findings)
                questions.extend(auditor.questions)
                records.extend(
                    {"id": slab.id, "name": slab.name, "snapshot_hash": slab.snapshot_hash, "classe": "LAJ"}
                    for slab in slabs if (not selected or slab.name in selected)
                )
            elif classe == "PIL":
                pillars = load_pillars(con, project_id)
                beams = load_beams_for_project(con, project_id)
                slabs_ctx = load_slabs(con, project_id)
                auditor = PilEvidenceAuditor(pillars, beams, slabs_ctx, run_id)
                class_decisions = auditor.audit(selected=selected, include_sealed=args.include_sealed)
                decisions.extend(class_decisions)
                findings.extend(auditor.findings)
                questions.extend(auditor.questions)
                records.extend(
                    {"id": pillar.id, "name": pillar.name, "snapshot_hash": pillar.snapshot_hash, "classe": "PIL"}
                    for pillar in pillars if (not selected or pillar.name in selected)
                )
            elif classe == "FV":
                from scripts.arete.qa_fv_lv_adapters import FvEvidenceAuditor, load_beam_records, load_name_index
                beams = load_beam_records(con, project_id)
                names = load_name_index(con, project_id)
                auditor = FvEvidenceAuditor(beams, names, run_id)
                class_decisions = auditor.audit(selected=selected, include_sealed=args.include_sealed)
                decisions.extend(class_decisions)
                findings.extend(auditor.findings)
                questions.extend(auditor.questions)
                records.extend(
                    {"id": b.id, "name": b.name, "snapshot_hash": b.snapshot_hash, "classe": "FV"}
                    for b in beams if (not selected or b.name in selected)
                )
            elif classe == "LV":
                from scripts.arete.qa_fv_lv_adapters import LvEvidenceAuditor, load_beam_records, load_name_index
                beams = load_beam_records(con, project_id)
                names = load_name_index(con, project_id)
                auditor = LvEvidenceAuditor(beams, names, run_id)
                class_decisions = auditor.audit(selected=selected, include_sealed=args.include_sealed)
                decisions.extend(class_decisions)
                findings.extend(auditor.findings)
                questions.extend(auditor.questions)
                records.extend(
                    {"id": b.id, "name": b.name, "snapshot_hash": b.snapshot_hash, "classe": "LV"}
                    for b in beams if (not selected or b.name in selected)
                )
            else:
                class_decisions, class_findings, class_questions, class_records = generic_class_review(
                    con, project_id=project_id, classe=classe, run_id=run_id,
                    selected=selected, include_sealed=args.include_sealed,
                )
                decisions.extend(class_decisions); findings.extend(class_findings)
                questions.extend(class_questions); records.extend(class_records)
            # A mesma citação é anexada como contexto, não como evidência suficiente.
            # Limitamos a oito entradas por camada para o dossiê permanecer legível.
            citations = rag_context.get(classe, [])[:8] + session_b1_context.get(classe, [])[:8]
            if citations:
                for decision in class_decisions:
                    decision.evidence.extend(citations)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_REPORT_ROOT / run_id
    manifest = {
        "schema_version": 1, "run_id": run_id, "created_at": utc_now(), "mode": "global_read_only_review",
        "db": str(db.resolve()), "project_id": project_id, "classe": "ALL" if len(requested) > 1 else requested[0],
        "classes": requested, "items": [record["name"] for record in records],
        "snapshots": {
            record["name"]: {"id": record["id"], "hash": record["snapshot_hash"], "classe": record.get("classe")}
            for record in records
        },
        "authority": "read_only; apply path resolves table/columns per item from CLASS_REGISTRY[classe]; validation_ready classes only",
        "rag": {
            "mode": args.rag_evidence,
            "consultations": {classe: len(entries) for classe, entries in rag_context.items()},
            "filters": {
                "family": args.rag_family, "field": args.rag_field,
                "tiers": args.rag_tier, "obra": args.rag_obra, "pav": args.rag_pav,
                "limit": args.rag_limit,
            },
            "policy": "consultative_only; RAG never proves a field or authorizes apply",
            "session_index_b1": {
                **session_index_status,
                "consultations": {classe: len(entries) for classe, entries in session_b1_context.items()},
                "policy": ("consultative_only, best_effort; never participates in "
                          "--rag-evidence required; same_origin never counts as "
                          "confirmatory reinforcement (docs/MASTERPLAN-MINIRAG-QA-N1.md)"),
            },
        },
    }
    write_reports(out_dir, manifest, decisions, findings, questions)
    write_jsonl(
        out_dir / "rag_consultas.jsonl",
        (entry for entries in rag_context.values() for entry in entries),
    )
    write_jsonl(
        out_dir / "session_index_b1_consultas.jsonl",
        (entry for entries in session_b1_context.values() for entry in entries),
    )
    print(json.dumps({"run_id": run_id, "out_dir": str(out_dir), "decisions": len(decisions), "questions": len(questions), "classes": requested}, ensure_ascii=False))
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
                # Isolado por classe: a tabela vem do próprio snapshot (ou do
                # manifesto quando o run é de uma única classe, mantendo
                # compat com manifestos antigos que não gravavam "classe" por
                # item). Nunca uma tabela compartilhada/adivinhada.
                item_classe = snapshot.get("classe") or manifest.get("classe")
                if item_classe not in CLASS_REGISTRY:
                    raise RuntimeError(f"classe desconhecida para {item}: {item_classe!r}")
                table = CLASS_REGISTRY[item_classe]["table"]
                current_hash, old_raw = current_snapshot(con, snapshot["id"], table=table)
                if current_hash != snapshot["hash"]:
                    raise RuntimeError(f"snapshot obsoleto para {item}; rode audit/review novamente")
                row = con.execute(f"SELECT * FROM {table} WHERE id=? AND project_id=?", (snapshot["id"], args.project_id)).fetchone()
                if row is None:
                    raise RuntimeError(f"item fora do projeto: {item}")
                keys = set(row.keys())
                state = {
                    "links": json_load(row["links_json"] if "links_json" in keys else "{}", {}),
                    "validated_fields": migrar_validated_fields_legado(
                        json_load(row["validated_fields_json"] if "validated_fields_json" in keys else "[]", [])
                    ),
                    "na_fields": set(json_load(row["na_fields_json"] if "na_fields_json" in keys else "[]", [])),
                    "validated_link_classes": json_load(
                        row["validated_link_classes_json"] if "validated_link_classes_json" in keys else "{}", {}
                    ),
                    "na_link_classes": json_load(
                        row["na_link_classes_json"] if "na_link_classes_json" in keys else "{}", {}
                    ),
                    "na_reasons": json_load(row["na_reasons_json"] if "na_reasons_json" in keys else "{}", {}),
                    "extra": json_load(row["extra_data_json"] if "extra_data_json" in keys else "{}", {}),
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
                required_fields = resolve_required_fields(item_classe, state)
                complete = required_fields.issubset(set(state["validated_fields"]) | state["na_fields"])
                new_seal = 1 if args.seal_complete and complete else int(state["is_validated"])
                rollback_rows.append({"item": item, "id": snapshot["id"], "table": table, "old": old_raw})
                update_map = {
                    "links_json": canonical_json(state["links"]),
                    "validated_fields_json": canonical_json(state["validated_fields"]),
                    "na_fields_json": canonical_json(sorted(state["na_fields"])),
                    "validated_link_classes_json": canonical_json(state["validated_link_classes"]),
                    "na_link_classes_json": canonical_json(state["na_link_classes"]),
                    "na_reasons_json": canonical_json(state["na_reasons"]),
                    "extra_data_json": canonical_json(state["extra"]),
                    "is_validated": new_seal,
                }
                cols = mutable_columns_for_table(con, table)
                set_parts = [f"{col}=?" for col in cols]
                values = [update_map[col] for col in cols]
                values.extend([snapshot["id"], args.project_id])
                con.execute(
                    f"UPDATE {table} SET {', '.join(set_parts)} WHERE id=? AND project_id=?",
                    values,
                )
                applied.append({"item": item, "operations": len(operations), "complete": complete, "sealed": bool(new_seal)})
            con.commit()
        except Exception:
            con.rollback()
            raise
    write_jsonl(run_dir / "rollback.jsonl", rollback_rows)
    (run_dir / "apply_result.json").write_text(json.dumps({"applied_at": utc_now(), "project_id": args.project_id, "items": applied}, ensure_ascii=False, indent=2), encoding="utf-8")
    _append_session_ledger(run_dir.parent, {
        "at": utc_now(), "run_id": manifest["run_id"], "mode": "apply",
        "project_id": args.project_id, "classe": manifest.get("classe"),
        "items": [entry["item"] for entry in applied], "applied": applied,
        "rollback": str(run_dir / "rollback.jsonl"), "out_dir": str(run_dir),
    })
    print(json.dumps({"applied": applied, "rollback": str(run_dir / 'rollback.jsonl')}, ensure_ascii=False))
    return 0


def cmd_flag_pending(args: argparse.Namespace) -> int:
    """Persiste em ``extra_data_json['agent_pending']`` os campos que o
    agente olhou e concluiu que precisam de humano (decisão PENDENTE ou
    REVISAR_HUMANO no run) — a UI usa isso pra pintar o campo de roxo,
    distinguindo "agente tentou e não conseguiu" de "ninguém olhou ainda".

    [2026-07-17] Decisão do dono. Isolado de ``apply``: nunca confirma nada,
    nunca precisa de decisão "high", nunca passa pelo filtro de aprovação —
    é metadado de diagnóstico, sempre seguro de rodar de novo (substitui o
    estado anterior pelo mais recente do review; item que passou a
    CONFIRMAR em tudo fica com `agent_pending` vazio, limpando o roxo).
    """
    run_dir = Path(args.run)
    manifest = json.loads((run_dir / "manifesto.json").read_text(encoding="utf-8"))
    if manifest.get("project_id") != args.project_id:
        raise SystemExit("project_id não coincide com o manifesto")
    decisions = read_jsonl(run_dir / "decisoes.jsonl")
    pending_by_item: dict[str, dict[str, str]] = {}
    for decision in decisions:
        if decision.get("decision") not in ("PENDENTE", "REVISAR_HUMANO"):
            continue
        item = decision.get("item")
        field_id = decision.get("field_id")
        if not item or not field_id:
            continue
        pending_by_item.setdefault(item, {})[field_id] = decision.get("reason") or decision.get("decision")

    db = Path(args.db)
    updated = []
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        con.execute("BEGIN IMMEDIATE")
        try:
            for item, snapshot in manifest["snapshots"].items():
                item_classe = snapshot.get("classe") or manifest.get("classe")
                if item_classe not in CLASS_REGISTRY:
                    continue
                table = CLASS_REGISTRY[item_classe]["table"]
                current_hash, _ = current_snapshot(con, snapshot["id"], table=table)
                if current_hash != snapshot["hash"]:
                    continue  # snapshot obsoleto (mudou desde o review) — pula, nunca força
                row = con.execute(
                    f"SELECT extra_data_json FROM {table} WHERE id=? AND project_id=?",
                    (snapshot["id"], args.project_id),
                ).fetchone()
                if row is None:
                    continue
                extra = json_load(row["extra_data_json"], {})
                new_pending = pending_by_item.get(item, {})
                if extra.get(AGENT_PENDING_KEY) == new_pending:
                    continue
                extra[AGENT_PENDING_KEY] = new_pending
                con.execute(
                    f"UPDATE {table} SET extra_data_json=? WHERE id=? AND project_id=?",
                    (canonical_json(extra), snapshot["id"], args.project_id),
                )
                updated.append({"item": item, "pending_fields": sorted(new_pending)})
            con.commit()
        except Exception:
            con.rollback()
            raise
    print(json.dumps({"updated": updated}, ensure_ascii=False))
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
                # Compat: rollback.jsonl anterior a este fix não gravava
                # "table" (todo run era LAJ/slabs); manifestos novos sempre
                # gravam a tabela real do item, isolada por classe.
                table = entry.get("table") or "slabs"
                values = [old[column] for column in MUTABLE_COLUMNS]
                con.execute(
                    f"UPDATE {table} SET " + ", ".join(f"{column}=?" for column in MUTABLE_COLUMNS) + " WHERE id=? AND project_id=?",
                    (*values, entry["id"], args.project_id),
                )
            con.commit()
        except Exception:
            con.rollback()
            raise
    _append_session_ledger(run_dir.parent, {
        "at": utc_now(), "run_id": manifest["run_id"], "mode": "rollback",
        "project_id": args.project_id, "classe": manifest.get("classe"),
        "items": [entry["item"] for entry in rows], "out_dir": str(run_dir),
    })
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
    audit.add_argument(
        "--web-evidence", choices=("auto", "required", "off"), default="auto",
        help="anexa ficha granular HTML versionada; required falha fechado se ausente",
    )
    audit.add_argument(
        "--web-root", default=str(DEFAULT_WEB_EVIDENCE_ROOT),
        help="raiz dos snapshots HTML que a interface apresenta",
    )
    audit.add_argument("--run-id")
    audit.add_argument("--out-dir")
    audit.set_defaults(func=cmd_audit)

    discover = sub.add_parser(
        "discover",
        help="inventário global read-only de LAJ/PIL/FV/LV; nunca valida nem grava N1",
    )
    discover.add_argument("--db", default=str(DEFAULT_DB))
    scope = discover.add_mutually_exclusive_group(required=True)
    scope.add_argument("--project-id")
    scope.add_argument("--obra", help="requer --pav; falha se houver reprocessamento ambíguo")
    discover.add_argument("--pav", help="pavimento quando o escopo é informado por --obra")
    discover.add_argument("--classe", choices=(*CLASS_REGISTRY.keys(), "ALL"), default="ALL")
    discover.add_argument("--item", nargs="*")
    discover.add_argument("--include-sealed", action="store_true")
    discover.add_argument("--run-id")
    discover.add_argument("--out-dir")
    discover.set_defaults(func=cmd_discover)

    review = sub.add_parser(
        "review",
        help="revisa campos/vínculos de todas as classes; read-only fora dos adaptadores LAJ/PIL",
    )
    review.add_argument("--db", default=str(DEFAULT_DB))
    review_scope = review.add_mutually_exclusive_group(required=True)
    review_scope.add_argument("--project-id")
    review_scope.add_argument("--obra", help="requer --pav; falha se houver reprocessamento ambíguo")
    review.add_argument("--pav")
    review.add_argument("--classe", choices=(*CLASS_REGISTRY.keys(), "ALL"), default="ALL")
    review.add_argument("--item", nargs="*")
    review.add_argument("--include-sealed", action="store_true")
    review.add_argument(
        "--rag-evidence", choices=("auto", "off", "required"), default="auto",
        help="consulta semantic_rag_kb como contexto; required falha se não houver memória da classe",
    )
    review.add_argument("--rag-family", help="família/subclasse exata quando o schema RAG suportar")
    review.add_argument("--rag-field", help="campo exato quando o schema RAG suportar")
    review.add_argument("--rag-tier", action="append", choices=("T1", "T2", "T3"))
    review.add_argument("--rag-obra", help="obra_contexto exata para consulta RAG")
    review.add_argument("--rag-pav", help="pavimento exato quando o schema RAG suportar")
    review.add_argument("--rag-limit", type=int, default=50)
    review.add_argument(
        "--session-index",
        help="pasta do índice de sessão (qa_session_index.py build --out ...) "
             "para consultar B1 (docs/MASTERPLAN-MINIRAG-QA-N1.md fase D3); "
             "opcional, degrada em silêncio se ausente/stale",
    )
    review.add_argument("--run-id")
    review.add_argument("--out-dir")
    review.set_defaults(func=cmd_review)

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

    flag_pending = sub.add_parser(
        "flag-pending",
        help="grava em extra_data_json['agent_pending'] os campos PENDENTE/REVISAR_HUMANO do run (UI pinta de roxo)",
    )
    flag_pending.add_argument("--db", default=str(DEFAULT_DB))
    flag_pending.add_argument("--project-id", required=True)
    flag_pending.add_argument("--run", required=True)
    flag_pending.set_defaults(func=cmd_flag_pending)

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
