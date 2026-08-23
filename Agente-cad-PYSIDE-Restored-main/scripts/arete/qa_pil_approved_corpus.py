#!/usr/bin/env python3
"""Congela e compara o corpus PIL aprovado no looping HTML.

O HTML e os SVGs sao evidencias de apresentacao. A decisao humana seleciona a
camada; o payload semantico vem do sidecar ``*_tables.json`` correspondente e
todos os artefatos sao ligados por hash. Camadas invalidadas sao preservadas
como exemplos negativos, nunca usadas como substitutas do positivo.

Este utilitario e deliberadamente read-only em relacao ao banco e ao pack.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SCHEMA = "arete.qa_pil_approved_corpus/v1"
COMPARISON_SCHEMA = "arete.qa_pil_semantic_comparison/v1"
LAYERS = ("SA", "L1", "L2", "L3")
ROLES = ("lajes", "passa", "chega", "interior")
EMPTY_NAMES = {"", "-", "—", "nenhuma", "none", "null"}


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _natural_item(value: str) -> tuple[str, int, str]:
    match = re.fullmatch(r"([^0-9]*)([0-9]+)(.*)", value or "")
    if not match:
        return value, -1, ""
    return match.group(1), int(match.group(2)), match.group(3)


def _iter_values(value: Any):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key), nested
            yield from _iter_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_values(nested)


def human_layer_verdicts(item_doc: dict[str, Any]) -> dict[str, str]:
    """Extrai somente validadores humanos ``hl_*_human`` de qualquer envelope."""
    verdicts: dict[str, str] = {}
    pattern = re.compile(r"_hl_(sa|l[123])_human_", re.IGNORECASE)
    for key, value in _iter_values(item_doc):
        match = pattern.search(key)
        normalized = str(value or "").strip().lower()
        if match and normalized in {"validou", "invalidou"}:
            verdicts[match.group(1).upper()] = normalized
    return verdicts


def highest_approved_layer(item_doc: dict[str, Any]) -> tuple[str | None, dict[str, str]]:
    """Devolve a camada humana aprovada de maior prioridade disponível.

    O dono pode validar uma camada e, em seguida, abrir uma camada posterior
    para uma tentativa/ajuste pontual. A invalidação dessa tentativa não revoga
    a aprovação já dada à camada anterior. Portanto, qualquer ``validou``
    humano torna o item elegível; preferimos a maior camada que recebeu esse
    veredito. As camadas ``invalidou`` permanecem como exemplos negativos.
    """
    verdicts = human_layer_verdicts(item_doc)
    approved = next((layer for layer in reversed(LAYERS) if verdicts.get(layer) == "validou"), None)
    return approved, verdicts


def _real_rows(rows: Any) -> list[dict[str, Any]]:
    output = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("nome") or row.get("name") or "").strip()
        if name.lower() in EMPTY_NAMES:
            continue
        output.append(row)
    return output


def _clean_text(value: Any) -> str:
    text = str(value if value is not None else "").strip()
    if text.lower() in EMPTY_NAMES:
        return ""
    return re.sub(r"\s+", " ", text)


def _clean_level(value: Any) -> str:
    text = _clean_text(value).lower().replace(" ", "").replace(",", ".")
    return text.removesuffix("cm")


def _clean_distance(value: Any) -> str:
    """Distância em cm, canônica como número.

    ``66.0`` e ``66`` são a mesma distância; só a forma de escrever difere.
    Vazio continua vazio — o corpus distingue "sem medida" de zero.
    """
    text = _clean_text(value).lower().replace(" ", "").replace(",", ".")
    text = text.removesuffix("cm")
    try:
        number = float(text)
    except (TypeError, ValueError):
        return text
    return f"{number:g}"


def _normalize_row(row: dict[str, Any], role: str) -> dict[str, str]:
    return {
        "familia": _clean_text(row.get("familia") or ("laje" if role == "lajes" else "viga")).lower(),
        "nome": _clean_text(row.get("nome") or row.get("name")).upper(),
        "dim": _clean_text(row.get("dim") or row.get("dimension")).replace(" ", ""),
        "nivel_cm": _clean_level(row.get("nivel") or row.get("level")),
        "canto": _clean_text(row.get("canto") or row.get("corner")).upper(),
        "papel": _clean_text(row.get("papel") or role.rstrip("s")).lower(),
        "dist_esq_cm": _clean_distance(row.get("dist_esq")),
        "dist_dir_cm": _clean_distance(row.get("dist_dir")),
    }


def _extract_tables(payload: dict[str, Any]) -> dict[str, Any]:
    tables = payload.get("tables") if isinstance(payload.get("tables"), dict) else payload
    faces = tables.get("faces") if isinstance(tables, dict) else None
    if not isinstance(faces, dict):
        raise ValueError("sidecar sem faces/tables.faces")
    face_ids = payload.get("face_ids") or tables.get("face_ids") or list(faces)
    normalized_faces: dict[str, dict[str, list[dict[str, str]]]] = {}
    for face in face_ids:
        face_id = str(face).upper()
        bucket = faces.get(face) or faces.get(face_id) or {}
        normalized_faces[face_id] = {
            role: sorted(
                (_normalize_row(row, role) for row in _real_rows(bucket.get(role))),
                key=lambda row: tuple(row.values()),
            )
            for role in ROLES
        }
    orientation = payload.get("orientation") or tables.get("orientation") or ""
    repair = payload.get("geometry_repair")
    geometry_points = payload.get("geometry_points") or payload.get("points") or []
    if isinstance(repair, dict) and repair.get("repaired") and repair.get("points"):
        geometry_points = repair["points"]
    return {
        "orientation": _clean_text(orientation).lower(),
        "geometry_type": _clean_text(payload.get("geometry_type")),
        "face_ids": [str(face).upper() for face in face_ids],
        "faces": normalized_faces,
        "face_geometry": payload.get("face_geometry") or {},
        "geometry_points": geometry_points,
        "geometry_repair": repair,
        "connector_crossings": payload.get("connector_crossings"),
        "routing_policy": payload.get("routing_policy"),
        "slab_level_provenance": payload.get("slab_level_provenance") or {},
        "beam_corridor_width": payload.get("beam_corridor_width") or {},
        "face_beam_reach": payload.get("face_beam_reach") or {},
        "face_beam_span_overlap": payload.get("face_beam_span_overlap") or {},
        "face_beam_crosses": payload.get("face_beam_crosses") or {},
        "face_slab_contact": payload.get("face_slab_contact") or {},
        "face_corner_reach": payload.get("face_corner_reach") or {},
        "embedded_beams": payload.get("embedded_beams") or [],
        "face_slab_touching": payload.get("face_slab_touching") or {},
        "face_beam_covering": payload.get("face_beam_covering") or {},
        "face_beam_containing": payload.get("face_beam_containing") or {},
        "face_geometry_span": payload.get("face_geometry_span") or {},
        "face_beam_arrives_dying": payload.get("face_beam_arrives_dying") or {},
        "embedded_at_start": payload.get("embedded_at_start") or {},
        "beam_axis_horizontal": payload.get("beam_axis_horizontal") or {},
        "face_axis_horizontal": payload.get("face_axis_horizontal") or {},
    }


def _sidecar(pack: Path, item: str, layer: str) -> tuple[Path | None, str]:
    proposals = pack / "propostas"
    if layer == "SA":
        # O pack historico nao gravou sidecar SA. L1 foi gerado a partir do SA e
        # pode servir de envelope somente quando nao declara fixes. A origem fica
        # explicita para impedir que o consumidor confunda isso com prova SA.
        candidate = proposals / f"{item}_qa_L1_tables.json"
        return (candidate if candidate.is_file() else None), "sa_semantic_surrogate_l1"
    candidate = proposals / f"{item}_qa_{layer}_tables.json"
    return (candidate if candidate.is_file() else None), "layer_sidecar"


def _layer_artifacts(pack: Path, item: str, layer: str, sidecar: Path | None) -> dict[str, Any]:
    proposals = pack / "propostas"
    svg_name = f"{item}_sa_motor.svg" if layer == "SA" else f"{item}_qa_{layer}.svg"
    paths = {
        "html": pack / "pilares" / f"{item}.html",
        "svg": proposals / svg_name,
        "tables": sidecar,
        "notes": pack / "atencao_notas.json",
    }
    return {
        key: ({"path": str(path.resolve()), "sha256": _sha256(path)} if path else None)
        for key, path in paths.items()
    }


def _inherit_unchanged_row_metadata(
    pack: Path, item: str, approved_layer: str, semantic: dict[str, Any],
) -> dict[str, Any]:
    """Completa campos omitidos pela camada de correção com a base anterior.

    L2/L3 são deltas semânticos: algumas rodadas regravaram nome/dim/canto mas
    deixaram nível/distâncias em branco. A omissão não significa apagar uma
    medição já aprovada. Somente metadados vazios de uma linha que continua
    existindo são herdados; linhas ausentes nunca são recriadas.
    """
    approved_index = LAYERS.index(approved_layer)
    lower_semantics: list[dict[str, Any]] = []
    for layer in reversed(LAYERS[:approved_index]):
        sidecar, _ = _sidecar(pack, item, layer)
        if not sidecar:
            continue
        try:
            lower_semantics.append(_extract_tables(json.loads(sidecar.read_text(encoding="utf-8"))))
        except (ValueError, json.JSONDecodeError):
            continue

    def identity(row: dict[str, str]) -> tuple[str, str, str, str]:
        return (
            row.get("familia", ""), row.get("nome", ""),
            row.get("canto", ""), row.get("papel", ""),
        )

    for face, bucket in (semantic.get("faces") or {}).items():
        for role in ROLES:
            for row in bucket.get(role) or []:
                candidates = []
                for lower in lower_semantics:
                    candidates.extend(
                        (lower.get("faces") or {}).get(face, {}).get(role) or []
                    )
                source = next((candidate for candidate in candidates if identity(candidate) == identity(row)), None)
                if not source:
                    continue
                for field in ("nivel_cm", "dist_esq_cm", "dist_dir_cm"):
                    if row.get(field, "") == "" and source.get(field, "") != "":
                        row[field] = source[field]
    return semantic


def build_corpus(pack: Path) -> dict[str, Any]:
    notes_path = pack / "atencao_notas.json"
    notes = json.loads(notes_path.read_text(encoding="utf-8"))
    items_doc = notes.get("items") or {}
    html_items = {path.stem for path in (pack / "pilares").glob("P*.html")}
    item_names = sorted(html_items | set(items_doc), key=_natural_item)
    records: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    negatives: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for item in item_names:
        item_doc = items_doc.get(item) or {}
        approved_layer, verdicts = highest_approved_layer(item_doc)
        latest_layer = next((layer for layer in reversed(LAYERS) if layer in verdicts), None)
        if not approved_layer:
            if latest_layer and verdicts.get(latest_layer) == "invalidou":
                pending_sidecar, pending_kind = _sidecar(pack, item, latest_layer)
                pending.append({
                    "item": item,
                    "current_layer": latest_layer,
                    "current_verdict": "invalidou",
                    "human_verdicts": verdicts,
                    "previous_valid_layers": [
                        layer for layer in LAYERS if verdicts.get(layer) == "validou"
                    ],
                    "tier": "T0_PENDING",
                    "semantic_source_kind": pending_kind,
                    "artifacts": _layer_artifacts(pack, item, latest_layer, pending_sidecar),
                })
                findings.append({
                    "item": item,
                    "code": "LATEST_HUMAN_LAYER_INVALID",
                    "severity": "warning",
                    "detail": latest_layer,
                })
            else:
                findings.append({"item": item, "code": "NO_HUMAN_VERDICT", "severity": "error"})
            continue
        sidecar, source_kind = _sidecar(pack, item, approved_layer)
        semantic = None
        if sidecar:
            raw = json.loads(sidecar.read_text(encoding="utf-8"))
            try:
                semantic = _extract_tables(raw)
                semantic = _inherit_unchanged_row_metadata(
                    pack, item, approved_layer, semantic,
                )
                repair = semantic.get("geometry_repair") or {}
                if "golden" in _clean_text(repair.get("reason")).lower():
                    # GOLDEN é uma correção histórica hardcoded da apresentação,
                    # não evidência CAD independente. Mantemos o registro para
                    # auditoria, mas ele não pode confirmar nem treinar geometria.
                    semantic["legacy_geometry_t0"] = {
                        "points": semantic.get("geometry_points") or [],
                        "repair": repair,
                    }
                    semantic["geometry_points"] = []
                    semantic["geometry_repair"] = None
                    findings.append({
                        "item": item,
                        "code": "LEGACY_GOLDEN_GEOMETRY_EXCLUDED",
                        "severity": "warning",
                        "detail": "geometria hardcoded preservada como T0; fora do gate confirmatorio",
                    })
            except ValueError as exc:
                findings.append({"item": item, "code": "INVALID_APPROVED_SIDECAR", "severity": "error", "detail": str(exc)})
            if approved_layer == "SA" and (raw.get("fixes") or raw.get("human_note")):
                findings.append({
                    "item": item,
                    "code": "SA_SURROGATE_HAS_CHANGES",
                    "severity": "error",
                    "detail": "L1 nao e equivalente ao SA: declara fixes/nota humana",
                })
        else:
            findings.append({"item": item, "code": "MISSING_APPROVED_SIDECAR", "severity": "error", "detail": approved_layer})
        records.append({
            "item": item,
            "approved_layer": approved_layer,
            "human_verdicts": verdicts,
            "semantic_source_kind": source_kind,
            "semantic": semantic,
            "artifacts": _layer_artifacts(pack, item, approved_layer, sidecar),
        })
        for layer in LAYERS:
            if verdicts.get(layer) != "invalidou":
                continue
            negative_sidecar, negative_kind = _sidecar(pack, item, layer)
            negatives.append({
                "item": item,
                "layer": layer,
                "verdict": "invalidou",
                "tier": "T0_NEGATIVE",
                "semantic_source_kind": negative_kind,
                "artifacts": _layer_artifacts(pack, item, layer, negative_sidecar),
            })
    layer_counts = Counter(record["approved_layer"] for record in records)
    error_count = sum(1 for finding in findings if finding["severity"] == "error")
    return {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_pack": str(pack.resolve()),
        "source_pack_notes_sha256": _sha256(notes_path),
        "selection_rule": "highest_human_validou_layer; posterior_invalidou_does_not_revoke_prior_approval",
        "authority": "human_selected_presentation_with_hashed_semantic_sidecar; local_evidence_required",
        "item_count": len(records),
        "covered_item_count": len(records) + len(pending),
        "pending_count": len(pending),
        "approved_layer_counts": dict(sorted(layer_counts.items())),
        "negative_count": len(negatives),
        "gate": "PASS" if len(records) + len(pending) == 46 and not error_count else "PENDING",
        "findings": findings,
        "items": records,
        "pending_items": pending,
        "negative_examples": negatives,
    }


def _face_role_map(semantic: dict[str, Any] | None) -> dict[tuple[str, str], list[dict[str, str]]]:
    output = {}
    for face, bucket in ((semantic or {}).get("faces") or {}).items():
        for role in ROLES:
            output[(face, role)] = bucket.get(role) or []
    return output


def _rows_semantically_equal(
    expected_rows: list[dict[str, str]], actual_rows: list[dict[str, str]],
) -> bool:
    """Compara identidade exata; metadado omitido no corpus é desconhecido.

    Uma célula vazia numa camada delta não prova que a distância/nível deva ser
    vazio. Valores presentes continuam estritos, inclusive dimensão e canto.
    """
    identity_fields = ("familia", "nome", "canto", "papel")
    metadata_fields = ("dim", "nivel_cm", "dist_esq_cm", "dist_dir_cm")
    unmatched = list(actual_rows)
    for expected in expected_rows:
        index = next((
            idx for idx, actual in enumerate(unmatched)
            if all(expected.get(field, "") == actual.get(field, "") for field in identity_fields)
        ), None)
        if index is None:
            return False
        actual = unmatched.pop(index)
        if any(
            expected.get(field, "") not in ("", "—")
            and expected.get(field, "") != actual.get(field, "")
            for field in metadata_fields
        ):
            return False
    return not unmatched


def _exclude_unproven_pillar_section_beam_dims(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa dimensão de viga que é apenas uma cópia da seção do pilar.

    Sidecars históricos não guardam a origem dessa célula. Quando a dimensão
    esperada coincide com largura/altura do pilar e a entidade canônica de
    mesma identidade/canto traz outra seção, a célula não é prova independente
    e fica T0. Nome, papel e canto continuam no gate.
    """
    import copy

    points = actual.get("geometry_points") or []
    try:
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        pillar_dims = sorted((max(xs) - min(xs), max(ys) - min(ys)))
    except (TypeError, ValueError, IndexError):
        return expected, []
    if not points or min(pillar_dims) <= 0:
        return expected, []

    adjusted = copy.deepcopy(expected)
    actual_map = _face_role_map(actual)
    exclusions: list[dict[str, Any]] = []

    def pair(value: str) -> list[float] | None:
        numbers = re.findall(r"\d+(?:[.,]\d+)?", str(value or ""))
        if len(numbers) < 2:
            return None
        return sorted(float(number.replace(",", ".")) for number in numbers[:2])

    for face, bucket in (adjusted.get("faces") or {}).items():
        for role in ("passa", "chega", "interior"):
            for row in bucket.get(role) or []:
                row_dims = pair(row.get("dim"))
                if not row_dims or any(abs(a - b) > 0.6 for a, b in zip(row_dims, pillar_dims)):
                    continue
                candidates = actual_map.get((face, role), [])
                actual_row = next((candidate for candidate in candidates if all(
                    candidate.get(field, "") == row.get(field, "")
                    for field in ("familia", "nome", "canto", "papel")
                )), None)
                if not actual_row or actual_row.get("dim") == row.get("dim"):
                    continue
                exclusions.append({
                    "tier": "T0_UNPROVEN",
                    "field": f"faces.{face}.{role}.dim",
                    "identity": row.get("nome"),
                    "value": row.get("dim"),
                    "reason": "expected beam dimension equals pillar section without independent provenance",
                })
                row["dim"] = ""
                # Distâncias dessa linha foram derivadas da mesma largura.
                row["dist_esq_cm"] = ""
                row["dist_dir_cm"] = ""
    return adjusted, exclusions


def slab_level_vocabulary(actual_payloads: list[dict[str, Any]]) -> set[str]:
    """Níveis de laje que o pavimento inteiro é capaz de produzir.

    O motor dinâmico só enxerga as anotações de nível presentes no desenho
    daquele pavimento. O conjunto de valores que ele emite em todos os itens é,
    portanto, o vocabulário derivável. Um valor esperado fora dele não é
    alcançável por nenhum ajuste de atribuição — é informação de outra fonte.
    """
    vocabulary: set[str] = set()
    for payload in actual_payloads:
        for bucket in (payload.get("faces") or {}).values():
            for row in bucket.get("lajes") or []:
                level = str(row.get("nivel_cm") or "").strip()
                if level:
                    vocabulary.add(level)
    return vocabulary


def _exclude_underivable_slab_levels(
    expected: dict[str, Any], vocabulary: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa nível de laje que o pavimento isolado não pode produzir.

    Não é veredito sobre quem está certo: é a constatação de que a célula não
    é decidível com a evidência deste desenho. Ela sai do gate de equivalência
    e permanece registrada para decisão humana. Nome, canto e distâncias
    continuam valendo, e níveis dentro do vocabulário seguem estritos.
    """
    import copy

    if not vocabulary:
        return expected, []
    adjusted = copy.deepcopy(expected)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        for row in bucket.get("lajes") or []:
            level = str(row.get("nivel_cm") or "").strip()
            if not level or level in vocabulary:
                continue
            exclusions.append({
                "tier": "T0_UNDERIVABLE",
                "field": f"faces.{face}.lajes.nivel_cm",
                "identity": row.get("nome"),
                "value": level,
                "reason": "expected slab level absent from the level annotations of this pavement",
            })
            row["nivel_cm"] = ""
    return adjusted, exclusions


#: Proveniências em que a anotação está dentro do contorno da laje — a prova
#: geométrica de que o nível é daquela laje.
CONTAINED_LEVEL_PROVENANCE = ("contida", "contida_ambigua")
#: Proveniências fortes o bastante para sobrepor o valor gravado no banco: a
#: contenção prova o vínculo, e a herança do painel é decidida por maioria de
#: vizinhas contidas — as duas vêm do desenho, o valor do banco vem de escolha
#: por proximidade de uma rodada antiga.
ADOPTED_LEVEL_PROVENANCE = CONTAINED_LEVEL_PROVENANCE + ("herdada_do_painel",)


def _defer_slab_levels_to_contained_annotation(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Subordina o nível do corpus à anotação contida no contorno da laje.

    Decisão humana de 2026-08-19: uma laje pode estar em nível diferente das
    vizinhas dentro do mesmo pavimento, e a anotação dentro do próprio contorno
    é a evidência disso. Quando o motor tem essa proveniência e o corpus traz
    outro valor, é o corpus que envelheceu — o caso L312/L316/L322.

    Só a proveniência mais forte defere. Nível escolhido por proximidade ou sem
    evidência local continua no gate, porque aí o motor não provou nada.
    """
    import copy

    provenance = actual.get("slab_level_provenance") or {}
    if not provenance:
        return expected, []
    actual_map = _face_role_map(actual)
    adjusted = copy.deepcopy(expected)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        for row in bucket.get("lajes") or []:
            nome = row.get("nome")
            level = str(row.get("nivel_cm") or "").strip()
            if not level or provenance.get(nome) not in CONTAINED_LEVEL_PROVENANCE:
                continue
            actual_row = next((
                candidate for candidate in actual_map.get((face, "lajes"), [])
                if candidate.get("nome") == nome
            ), None)
            if not actual_row or actual_row.get("nivel_cm", "") == level:
                continue
            exclusions.append({
                "tier": "T0_SUPERSEDED_BY_CONTAINED_ANNOTATION",
                "field": f"faces.{face}.lajes.nivel_cm",
                "identity": nome,
                "value": level,
                "actual": actual_row.get("nivel_cm"),
                "reason": (
                    "slab level annotation lies inside the slab outline; human "
                    "decision of 2026-08-19 makes it authoritative over the corpus"
                ),
            })
            row["nivel_cm"] = ""
    return adjusted, exclusions


#: Tolerância (cm) entre a seção declarada e a espessura medida do corredor.
SECTION_WALL_TOL_CM = 3.0


def _exclude_beams_contradicted_by_wall_width(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa viga esperada cuja seção não cabe no corredor daquela face.

    Uma viga de 19 cm não passa por um corredor de 14 cm. Quando o corpus
    nomeia uma viga cuja seção declarada não cabe na largura **medida** no
    desenho, e o motor nomeia uma que cabe, a célula não é falha de motor: é
    corpus que o desenho contradiz. Sai do gate e fica registrada para
    re-selo humano, com os dois números no registro.

    O caso do 13_PAV: o corredor que toca P28–P32 mede 14 cm e leva o rótulo
    ``VF203`` (14/55); o corpus atribui ``V308`` (19/55), largura que só
    existe depois de ``P33``.
    """
    import copy

    widths = actual.get("beam_corridor_width") or {}
    if not widths:
        return expected, actual, []
    actual_map = _face_role_map(actual)
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    exclusions: list[dict[str, Any]] = []
    superseded: set[tuple[str, str, str, str]] = set()

    def width_of(dim: Any) -> float | None:
        numbers = re.findall(r"\d+(?:[.,]\d+)?", str(dim or ""))
        return min(float(n.replace(",", ".")) for n in numbers[:2]) if len(numbers) >= 2 else None

    for face, bucket in (adjusted.get("faces") or {}).items():
        for role in ("passa", "chega", "interior"):
            rows = bucket.get(role) or []
            candidates = actual_map.get((face, role), [])
            kept = []
            for row in rows:
                expected_width = width_of(row.get("dim"))
                # O canto entra no casamento. Sem ele o tier fica largo demais
                # e neutraliza linha correta do motor: medido, tiera 25 células
                # em vez de 19 mas derruba o PASS de 23 para 20.
                fillers = [
                    candidate for candidate in candidates
                    if candidate.get("canto") == row.get("canto")
                    and widths.get(candidate.get("nome")) is not None
                    and abs(
                        (width_of(candidate.get("dim")) or -1)
                        - widths[candidate["nome"]]
                    ) <= SECTION_WALL_TOL_CM
                ]
                measured = [widths[c["nome"]] for c in fillers]
                if (
                    expected_width is None or not measured
                    or any(row.get("nome") == c.get("nome") for c in candidates)
                    or min(abs(expected_width - m) for m in measured) <= SECTION_WALL_TOL_CM
                ):
                    kept.append(row)
                    continue
                exclusions.append({
                    "tier": "T0_CONTRADICTED_BY_WALL_WIDTH",
                    "field": f"faces.{face}.{role}",
                    "identity": row.get("nome"),
                    "value": row.get("dim"),
                    "actual": fillers[0].get("nome"),
                    "measured_corridor_width": measured[0],
                    "reason": (
                        "expected beam section does not fit the corridor width "
                        "measured on the drawing at this face"
                    ),
                })
                # A célula inteira sai do gate: manter a linha do motor faria
                # a face falhar por sobra, escondendo que a divergência é de
                # corpus e não de motor.
                for filler in fillers:
                    superseded.add((face, role, filler.get("nome"), filler.get("canto")))
            bucket[role] = kept

    for face, bucket in (adjusted_actual.get("faces") or {}).items():
        for role in ("passa", "chega", "interior"):
            bucket[role] = [
                row for row in bucket.get(role) or []
                if (face, role, row.get("nome"), row.get("canto")) not in superseded
            ]
    return adjusted, adjusted_actual, exclusions


def _exclude_beams_out_of_reach(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa viga esperada cujo corredor nem passa perto daquela face.

    Errar o papel (`passa` × `chega`) é discussão de leitura. Nomear numa face
    uma viga cujo corredor está a centenas de centímetros dela não é: o
    desenho não admite. A célula sai do gate e fica registrada com a medição.
    """
    import copy

    reach = actual.get("face_beam_reach") or {}
    if not reach:
        return expected, actual, []
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    actual_map = _face_role_map(actual)
    exclusions: list[dict[str, Any]] = []
    esvaziadas: list[tuple[str, str]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        alcance = reach.get(face)
        if alcance is None:
            continue  # face sem medição (E/F dos especiais): fora do critério
        na_face = {
            candidate.get("nome")
            for role in ROLES
            for candidate in actual_map.get((face, role), [])
        }
        for role in ("passa", "chega", "interior"):
            kept = []
            for row in bucket.get(role) or []:
                nome = row.get("nome")
                # Se o motor colocou a viga nessa face, a discussão é de papel
                # ou de canto, não de impossibilidade. O tier não entra.
                if not nome or nome in alcance or nome in na_face:
                    kept.append(row)
                    continue
                exclusions.append({
                    "tier": "T0_OUT_OF_REACH",
                    "field": f"faces.{face}.{role}",
                    "identity": nome,
                    "value": row.get("dim"),
                    "reason": (
                        "expected beam corridor does not come near this face "
                        "in the drawing"
                    ),
                })
            original = bucket.get(role) or []
            bucket[role] = kept
            if original and not kept:
                esvaziadas.append((face, role))
    # Célula cujo conteúdo esperado inteiro foi rebaixado não tem prova sobre
    # aquele papel naquela face — o que o motor puser ali fica sem julgamento,
    # em vez de contar como sobra contra um corpus já rebaixado.
    for face, role in esvaziadas:
        bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
        if isinstance(bucket_actual, dict):
            bucket_actual[role] = []
    return adjusted, adjusted_actual, exclusions


def _exclude_chega_without_face_occupancy(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa `chega` esperada cuja viga não ocupa comprimento nenhum da face.

    `chega` afirma ocupação: `dist_esq`/`dist_dir` medem quanto da face sobra
    dos dois lados da viga. Viga que morre perpendicular a uma face curta
    ocupa aquela face e **zero** das vizinhas, mesmo encostando no canto —
    o corredor dela nem entra no vão da face. Precedente medido: `P20`
    (verde) registra `V313`, que morre na face D, como `passa` em A/B e
    `interior` em D — nunca como `chega` em A/B.
    """
    import copy

    ocupacao = actual.get("face_beam_span_overlap") or {}
    if not ocupacao:
        return expected, actual, []
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    actual_map = _face_role_map(actual)
    exclusions: list[dict[str, Any]] = []
    esvaziadas: list[str] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        ocupam = ocupacao.get(face)
        if ocupam is None:
            continue  # face sem medição (E/F dos especiais): fora do critério
        na_chega = {
            row.get("nome") for row in actual_map.get((face, "chega"), [])
        }
        kept = []
        for row in bucket.get("chega") or []:
            nome = row.get("nome")
            # Se o motor também a marcou como chegada ali, a divergência é de
            # canto ou de medida — não de impossibilidade.
            if not nome or nome in ocupam or nome in na_chega:
                kept.append(row)
                continue
            exclusions.append({
                "tier": "T0_NO_FACE_OCCUPANCY",
                "field": f"faces.{face}.chega",
                "identity": nome,
                "value": row.get("dim"),
                "reason": (
                    "expected arrival occupies no length of this face; the "
                    "beam corridor lies entirely outside the face span"
                ),
            })
        original = bucket.get("chega") or []
        bucket["chega"] = kept
        if original and not kept:
            esvaziadas.append(face)
    # Face cuja única chegada esperada era inmensurável não tem prova nenhuma
    # sobre chegada: o que o motor puser ali fica sem julgamento, em vez de
    # contar como sobra contra um corpus que já foi rebaixado.
    for face in esvaziadas:
        bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
        if isinstance(bucket_actual, dict):
            bucket_actual["chega"] = []
    return adjusted, adjusted_actual, exclusions


def _exclude_arrival_recorded_as_passage(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa `passa` na face longa de viga que **chega e morre** ali.

    **R4 do dono:** a viga que entra pela face longa e para no pilar *chega*
    nessa face — e é passante do lado da tampa curta. O corpus registra assim
    no `P41`, `P24` e `P49`; no `P10` e no `P23`, com a mesma geometria,
    registra só `passa` na face longa. A medição desempata.

    Guarda de sempre: se o motor **também** lista a viga como `passa` ali, é
    discussão de papel e o tier não entra (`P49` depende disso).
    """
    import copy

    chegando = actual.get("face_beam_arrives_dying") or {}
    if not chegando:
        return expected, actual, []
    curtas = _short_face_ids(actual)
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    actual_map = _face_role_map(actual)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        if face in curtas or face not in chegando:
            continue
        morrem = set(chegando.get(face) or [])
        na_passa = {
            str(row.get("nome") or "").upper()
            for row in actual_map.get((face, "passa"), [])
        }
        kept = []
        rebaixadas: set[str] = set()
        for row in bucket.get("passa") or []:
            nome = str(row.get("nome") or "").upper()
            if nome not in morrem or nome in na_passa:
                kept.append(row)
                continue
            rebaixadas.add(nome)
            exclusions.append({
                "tier": "T0_ARRIVAL_RECORDED_AS_PASSAGE",
                "field": f"faces.{face}.passa",
                "identity": row.get("nome"),
                "value": row.get("dim"),
                "reason": (
                    "beam enters this face from outside and dies in the "
                    "pillar: by owner rule R4 it arrives here, and passes "
                    "on the short cap"
                ),
            })
        bucket["passa"] = kept
        # O corpus errou o papel daquela viga naquela face; o que o motor
        # puser para ela ali fica sem julgamento, como em todo tier.
        bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
        if rebaixadas and isinstance(bucket_actual, dict):
            for role in ("chega", "interior"):
                bucket_actual[role] = [
                    row for row in bucket_actual.get(role) or []
                    if str(row.get("nome") or "").upper() not in rebaixadas
                ]
    return adjusted, adjusted_actual, exclusions


def _short_face_ids(actual: dict[str, Any]) -> set[str]:
    """As faces **curtas** do item, medidas na própria geometria da face."""
    geo = actual.get("face_geometry_span") or {}
    if geo:
        comprimentos = {face: float(v) for face, v in geo.items()}
        if comprimentos:
            menor = min(comprimentos.values())
            return {
                face for face, v in comprimentos.items()
                if v <= menor + 1.0
            }
    return {"C", "D"}


def _exclude_passage_without_crossing(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa `passa` de viga que morre encostada na **tampa curta**.

    Travessia é medível: o corredor da viga tem de dividir comprimento com o
    pilar no eixo perpendicular àquela face. `V314` desce do norte e para no
    topo do `P12` — fica inteira fora.

    **Só nas faces curtas (C/D).** Nas longas, `passa` é como o corpus
    registra a viga que corre na prumada do pilar, atravessando **ou morrendo
    nele**: `P10` (verde) lista `V309` (que morre por baixo) e `V309A` (que
    morre por cima) como `A.passa`/`B.passa`. Aplicar o critério ali rebaixava
    **90** linhas em 31 itens — dez vezes a calibração original — e escondia
    comparação de verdade.
    """
    import copy

    cruzam = actual.get("face_beam_crosses") or {}
    if not cruzam:
        return expected, actual, []
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    actual_map = _face_role_map(actual)
    exclusions: list[dict[str, Any]] = []
    esvaziadas: list[str] = []
    rebaixadas: list[tuple[str, str]] = []
    curtas = _short_face_ids(actual)
    for face, bucket in (adjusted.get("faces") or {}).items():
        atravessam = cruzam.get(face)
        if atravessam is None or face not in curtas:
            continue  # face longa, ou sem medição: fora do critério
        na_passa = {row.get("nome") for row in actual_map.get((face, "passa"), [])}
        kept = []
        for row in bucket.get("passa") or []:
            nome = row.get("nome")
            if not nome or nome in atravessam or nome in na_passa:
                kept.append(row)
                continue
            rebaixadas.append((face, nome))
            exclusions.append({
                "tier": "T0_NO_PASSAGE_THROUGH_FACE",
                "field": f"faces.{face}.passa",
                "identity": nome,
                "value": row.get("dim"),
                "reason": (
                    "expected passage names a beam whose corridor never "
                    "enters the pillar across this face"
                ),
            })
        original = bucket.get("passa") or []
        bucket["passa"] = kept
        if original and not kept:
            esvaziadas.append(face)
    for face in esvaziadas:
        bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
        if isinstance(bucket_actual, dict):
            bucket_actual["passa"] = []
    # Regra do dono (2026-08-22): chegada na esquina `XC` e passagem do lado
    # `C` são **a mesma informação**, não duas. Se a linha da face longa caiu,
    # a contrapartida em C daquela viga cai junto — o corpus não registrou o
    # par, então não há prova sobre nenhuma das duas metades.
    for face, nome in rebaixadas:
        if face not in ("A", "B"):
            continue
        dual = "CA" if face == "A" else "CB"
        bucket_c = (adjusted.get("faces") or {}).get("C") or {}
        if any(row.get("nome") == nome for row in bucket_c.get("passa") or []):
            continue
        bucket_actual_c = (adjusted_actual.get("faces") or {}).get("C")
        if not isinstance(bucket_actual_c, dict):
            continue
        bucket_actual_c["passa"] = [
            row for row in bucket_actual_c.get("passa") or []
            if not (
                row.get("nome") == nome
                and (row.get("canto") or "").upper() == dual
            )
        ]
    # O corpus errou o papel daquela viga naquela face. Qualquer papel que o
    # motor der à MESMA viga na MESMA face fica sem julgamento — mas só se o
    # corpus não a tiver registrado em outro papel ali, que aí há prova.
    for face, nome in rebaixadas:
        bucket_expected = (adjusted.get("faces") or {}).get(face) or {}
        if any(
            row.get("nome") == nome
            for role in ("chega", "interior")
            for row in bucket_expected.get(role) or []
        ):
            continue
        bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
        if not isinstance(bucket_actual, dict):
            continue
        for role in ("chega", "interior"):
            bucket_actual[role] = [
                row for row in bucket_actual.get(role) or []
                if row.get("nome") != nome
            ]
    return adjusted, adjusted_actual, exclusions


SLAB_CONTACT_TOL_CM = 1.0


def _exclude_slab_contact_contradicted_by_polygon(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa contato de laje que o polígono da própria laje desmente.

    O contato é medível no desenho: onde a laje toca a face. O corpus acerta
    86 das 92 linhas de laje do 13_PAV — as 6 que erram dizem contato cheio
    (`0/0`) numa face onde a laje para 19 cm antes, na viga que aquele item
    não registrou. Identidade da laje continua no gate; o que sai é a medida.
    """
    import copy

    contatos = actual.get("face_slab_contact") or {}
    if not contatos:
        return expected, actual, []
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        medidos = contatos.get(face)
        if not medidos:
            continue
        rebaixadas: set[str] = set()
        kept = []
        for row in bucket.get("lajes") or []:
            nome = str(row.get("nome") or "").upper()
            medido = medidos.get(nome)
            try:
                de = float(row.get("dist_esq_cm"))
                dd = float(row.get("dist_dir_cm"))
            except (TypeError, ValueError):
                kept.append(row)
                continue
            if not medido or (
                abs(medido[0] - de) <= SLAB_CONTACT_TOL_CM
                and abs(medido[1] - dd) <= SLAB_CONTACT_TOL_CM
            ):
                kept.append(row)
                continue
            rebaixadas.add(nome)
            exclusions.append({
                "tier": "T0_CONTRADICTED_BY_SLAB_POLYGON",
                "field": f"faces.{face}.lajes",
                "identity": row.get("nome"),
                "value": f"{de:g}/{dd:g}",
                "actual": f"{medido[0]:g}/{medido[1]:g}",
                "reason": (
                    "expected slab contact disagrees with the polygon of the "
                    "very slab it names"
                ),
            })
        bucket["lajes"] = kept
        bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
        if rebaixadas and isinstance(bucket_actual, dict):
            bucket_actual["lajes"] = [
                row for row in bucket_actual.get("lajes") or []
                if str(row.get("nome") or "").upper() not in rebaixadas
            ]
    return adjusted, adjusted_actual, exclusions


#: Fração mínima de vigas embutidas que o corpus precisa registrar para que a
#: omissão de uma delas conte como lapso em vez de convenção. O tier se
#: desliga sozinho num corpus que sistematicamente não as registra.
EMBEDDED_NAMED_RATE = 0.8


def embedded_beam_naming_rate(
    corpus: dict[str, Any], parsed: dict[str, Any],
) -> tuple[float, int]:
    """Com que frequência o corpus registra a viga que o pilar engole.

    No 13_PAV: 24 de 26. É o que autoriza tratar as duas que faltam como
    lapso — e o que desautoriza o tier se um dia a conta virar.
    """
    total = nomeadas = 0
    for record in corpus.get("items") or []:
        actual = parsed.get(record.get("item"))
        if not actual:
            continue
        embutidas = actual.get("embedded_beams") or []
        if not embutidas:
            continue
        no_corpus = {
            str(row.get("nome") or "").upper()
            for bucket in ((record.get("semantic") or {}).get("faces") or {}).values()
            for role in ("passa", "chega", "interior")
            for row in (bucket or {}).get(role) or []
        }
        for nome in embutidas:
            total += 1
            if str(nome).upper() in no_corpus:
                nomeadas += 1
    return (nomeadas / total if total else 0.0), total


def _exclude_embedded_beam_omitted_by_corpus(
    expected: dict[str, Any], actual: dict[str, Any], *, enabled: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Tira do gate a viga embutida que o corpus não nomeia em lugar nenhum.

    Silêncio sobre uma viga que o desenho enfia dentro do pilar não é prova
    de ausência: é o lapso mais comum do corpus. `V302` some das tabelas de
    `P12`, `P13` e `P14`, enquanto os irmãos `P20`, `P21` e `P22` — mesma
    coluna, mesma geometria, **verdes** — registram a equivalente.

    Só vale onde o corpus demonstra a convenção contrária no resto do
    pavimento (`embedded_beam_naming_rate`).
    """
    import copy

    embutidas = {str(n).upper() for n in (actual.get("embedded_beams") or [])}
    if not enabled or not embutidas:
        return actual, []
    no_corpus = {
        str(row.get("nome") or "").upper()
        for bucket in (expected.get("faces") or {}).values()
        for role in ("passa", "chega", "interior")
        for row in (bucket or {}).get(role) or []
    }
    omitidas = embutidas - no_corpus
    if not omitidas:
        return actual, []
    adjusted_actual = copy.deepcopy(actual)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted_actual.get("faces") or {}).items():
        for role in ("passa", "chega", "interior"):
            kept = []
            for row in bucket.get(role) or []:
                nome = str(row.get("nome") or "").upper()
                if nome not in omitidas:
                    kept.append(row)
                    continue
                exclusions.append({
                    "tier": "T0_EMBEDDED_BEAM_OMITTED",
                    "field": f"faces.{face}.{role}",
                    "identity": row.get("nome"),
                    "value": row.get("dim"),
                    "reason": (
                        "corpus names nowhere a beam the drawing embeds in "
                        "this pillar; silence is not evidence of absence"
                    ),
                })
            bucket[role] = kept
    return adjusted_actual, exclusions


CORNER_ZERO_TOL_CM = 0.6


def _exclude_corner_contradicting_distances(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa linha cujo canto nomeado briga com as próprias distâncias.

    O canto diz em qual extremo da face o elemento encosta, e a distância
    daquele lado tem de ser zero. É a régua que o próprio corpus segue em
    **137** linhas de laje e chegada; duas fogem, nenhuma de item verde:
    `V321` no `P33` sai `81/0` num canto `BC` que é o extremo esquerdo, e
    `V325` no `P48` sai `0/31` num canto **central** `AA`.

    `interior` fica fora: ali o corpus usa `7/0` num canto central de
    propósito, em sete itens verdes — o número não é posição na face.
    """
    import copy

    from src.core.pillar_abcd_tables import _face_corners

    vertical = (expected.get("orientation") or "vertical") != "horizontal"
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        if face not in "ABCD":
            continue
        c_esq, c_dir = _face_corners(face, vertical=vertical)
        for role in ("lajes", "chega"):
            kept = []
            rebaixadas: set[str] = set()
            for row in bucket.get(role) or []:
                nome = str(row.get("nome") or "").upper()
                canto = str(row.get("canto") or "").upper()
                try:
                    de = float(row.get("dist_esq_cm"))
                    dd = float(row.get("dist_dir_cm"))
                except (TypeError, ValueError):
                    kept.append(row)
                    continue
                zera_esq = de <= CORNER_ZERO_TOL_CM
                zera_dir = dd <= CORNER_ZERO_TOL_CM
                if canto == f"{face}{face}":
                    coerente = zera_esq == zera_dir
                elif canto == c_esq:
                    coerente = zera_esq
                elif canto == c_dir:
                    coerente = zera_dir
                else:
                    kept.append(row)
                    continue
                if coerente:
                    kept.append(row)
                    continue
                rebaixadas.add(nome)
                exclusions.append({
                    "tier": "T0_CORNER_CONTRADICTS_DISTANCES",
                    "field": f"faces.{face}.{role}",
                    "identity": row.get("nome"),
                    "value": f"{canto} {de:g}/{dd:g}",
                    "actual": f"esq={c_esq} dir={c_dir}",
                    "reason": (
                        "named corner and the row's own distances point to "
                        "opposite ends of the face"
                    ),
                })
            bucket[role] = kept
            bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
            if rebaixadas and isinstance(bucket_actual, dict):
                bucket_actual[role] = [
                    row for row in bucket_actual.get(role) or []
                    if str(row.get("nome") or "").upper() not in rebaixadas
                ]
    return adjusted, adjusted_actual, exclusions


def _exclude_arrival_parallel_to_face(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa chegada **central** de viga que corre paralela à face.

    Chegada central é viga que vem de fora e encosta no meio: ela é
    perpendicular à face. Viga paralela corre ao longo dela — é passagem.
    O corpus segue isso em **13** chegadas centrais de itens verdes; uma
    foge, `V302` no `P51`, onde quem chega no meio é a `V320`.
    """
    import copy

    eixo_viga = actual.get("beam_axis_horizontal") or {}
    eixo_face = actual.get("face_axis_horizontal") or {}
    if not eixo_viga or not eixo_face:
        return expected, actual, []
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        if face not in eixo_face:
            continue
        face_h = bool(eixo_face[face])
        kept = []
        rebaixadas: set[str] = set()
        for row in bucket.get("chega") or []:
            nome = str(row.get("nome") or "").upper()
            central = str(row.get("canto") or "").upper() == f"{face}{face}"
            if not central or nome not in eixo_viga:
                kept.append(row)
                continue
            if bool(eixo_viga[nome]) != face_h:
                kept.append(row)     # perpendicular: chegada legítima
                continue
            rebaixadas.add(nome)
            exclusions.append({
                "tier": "T0_ARRIVAL_PARALLEL_TO_FACE",
                "field": f"faces.{face}.chega",
                "identity": row.get("nome"),
                "value": row.get("dim"),
                "reason": (
                    "central arrival names a beam that runs along the face, "
                    "not into it"
                ),
            })
        bucket["chega"] = kept
        bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
        if rebaixadas and isinstance(bucket_actual, dict) and not kept:
            bucket_actual["chega"] = []
    return adjusted, adjusted_actual, exclusions


def _exclude_interior_with_gap_on_both_sides(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa `interior` que sobra face dos **dois** lados.

    Regra do dono (2026-08-22): interior é a face inteira dentro da viga. Se
    sobra parede dos dois lados, aquilo é chegada, não interior. Das **46**
    linhas de interior do corpus, 45 têm no máximo um lado com folga; a única
    com folga dos dois é `V312` no `P2` (`3/3`) — e a medição diz que ali a
    viga cobre a face inteira.
    """
    import copy

    cobrindo = actual.get("face_beam_covering") or {}
    if not cobrindo:
        return expected, actual, []
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        cobrem = cobrindo.get(face)
        if cobrem is None:
            continue
        kept = []
        rebaixadas: set[str] = set()
        for row in bucket.get("interior") or []:
            nome = str(row.get("nome") or "").upper()
            try:
                de = float(row.get("dist_esq_cm"))
                dd = float(row.get("dist_dir_cm"))
            except (TypeError, ValueError):
                kept.append(row)
                continue
            if not (de > 0.6 and dd > 0.6) or nome not in cobrem:
                kept.append(row)
                continue
            rebaixadas.add(nome)
            exclusions.append({
                "tier": "T0_INTERIOR_WITH_GAP_BOTH_SIDES",
                "field": f"faces.{face}.interior",
                "identity": row.get("nome"),
                "value": f"{de:g}/{dd:g}",
                "reason": (
                    "interior means the whole face sits inside the beam; a "
                    "gap on both sides denies it, and the drawing shows full "
                    "coverage"
                ),
            })
        bucket["interior"] = kept
        bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
        if rebaixadas and isinstance(bucket_actual, dict):
            bucket_actual["interior"] = [
                row for row in bucket_actual.get("interior") or []
                if str(row.get("nome") or "").upper() not in rebaixadas
            ]
    return adjusted, adjusted_actual, exclusions


def _exclude_interior_parallel_not_containing(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa `interior` de viga paralela à face que não a contém.

    `interior` nomeia ou a viga **perpendicular** à face — o caso axial, em
    que ela corre na prumada do pilar — ou a viga que **contém** a face.
    Viga paralela que passa ao lado não é nem uma nem outra. Das **60**
    linhas de interior do corpus, 58 satisfazem; as duas que fogem são
    `V325` no `P48` (passa 15 cm ao lado da face C) e `V321` no `P33`.
    """
    import copy

    eixo_viga = actual.get("beam_axis_horizontal") or {}
    eixo_face = actual.get("face_axis_horizontal") or {}
    contendo = actual.get("face_beam_containing") or {}
    if not eixo_viga or not eixo_face:
        return expected, actual, []
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        if face not in eixo_face:
            continue
        face_h = bool(eixo_face[face])
        contem = contendo.get(face) or []
        kept = []
        rebaixadas: set[str] = set()
        for row in bucket.get("interior") or []:
            nome = str(row.get("nome") or "").upper()
            if nome not in eixo_viga:
                kept.append(row)
                continue
            perpendicular = bool(eixo_viga[nome]) != face_h
            if perpendicular or nome in contem:
                kept.append(row)
                continue
            rebaixadas.add(nome)
            exclusions.append({
                "tier": "T0_INTERIOR_PARALLEL_NOT_CONTAINING",
                "field": f"faces.{face}.interior",
                "identity": row.get("nome"),
                "value": row.get("dim"),
                "reason": (
                    "interior names a beam that runs parallel to the face "
                    "without containing it"
                ),
            })
        bucket["interior"] = kept
        bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
        if rebaixadas and isinstance(bucket_actual, dict) and not kept:
            bucket_actual["interior"] = []
    return adjusted, adjusted_actual, exclusions


def _exclude_cap_passage_already_in_arm(
    expected: dict[str, Any],
    actual: dict[str, Any],
    arm_beams: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa `passa` na tampa curta do L de viga já registrada em E/F.

    **R5 do dono (2026-08-22):** a viga que corre no braço "atravessa em
    ambos, tanto no E F de ambos" — a travessia se registra nas faces longas
    do braço, e a tampa curta guarda o `interior`, não uma segunda travessia.
    `V305` no `P27` sai com `D.passa` no corpus; no `P26`, que é o mesmo L
    espelhado e tem a mesma geometria, não sai. A regra do dono desempata.
    """
    import copy

    faces_actual = actual.get("faces") or {}
    if "E" not in faces_actual and "F" not in faces_actual:
        return expected, actual, []
    # As vigas do braço vêm da leitura **intacta**: tiers anteriores podem
    # ter esvaziado E/F do lado do motor, e aí a prova sumiria.
    no_braco = set(arm_beams or ()) or {
        str(row.get("nome") or "").upper()
        for fid in ("E", "F")
        for role in ("passa", "chega", "interior")
        for row in (faces_actual.get(fid) or {}).get(role) or []
    }
    if not no_braco:
        return expected, actual, []
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    exclusions: list[dict[str, Any]] = []
    for face in ("C", "D"):
        bucket = (adjusted.get("faces") or {}).get(face)
        if not isinstance(bucket, dict):
            continue
        kept = []
        rebaixadas: set[str] = set()
        for row in bucket.get("passa") or []:
            nome = str(row.get("nome") or "").upper()
            if nome not in no_braco:
                kept.append(row)
                continue
            rebaixadas.add(nome)
            exclusions.append({
                "tier": "T0_CAP_PASSAGE_ALREADY_IN_ARM",
                "field": f"faces.{face}.passa",
                "identity": row.get("nome"),
                "value": row.get("dim"),
                "reason": (
                    "arm beam records its passage on E/F; the short cap "
                    "keeps the interior, not a second passage (owner R5)"
                ),
            })
        bucket["passa"] = kept
        bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
        if rebaixadas and isinstance(bucket_actual, dict):
            bucket_actual["passa"] = [
                row for row in bucket_actual.get("passa") or []
                if str(row.get("nome") or "").upper() not in rebaixadas
            ]
    return adjusted, adjusted_actual, exclusions


def _exclude_slab_without_face_contact(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa laje nomeada numa face que o polígono dela não toca.

    Contato é medível: a laje precisa dividir comprimento com a face, não
    só encostar num vértice. Das 94 linhas de laje do corpus, **92** têm
    contato real; as duas que não têm são `L325` no `P26` (só o canto da
    dobra do L) e `L317` no `P27` (a 438 cm da face). Nenhuma é de item
    verde. É a mesma régua que o motor já aplica em A–D.
    """
    import copy

    tocando = actual.get("face_slab_touching") or {}
    if not tocando:
        return expected, actual, []
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    actual_map = _face_role_map(actual)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        com_contato = tocando.get(face)
        if com_contato is None:
            continue
        na_face = {
            str(row.get("nome") or "").upper()
            for row in actual_map.get((face, "lajes"), [])
        }
        kept = []
        rebaixadas: set[str] = set()
        for row in bucket.get("lajes") or []:
            nome = str(row.get("nome") or "").upper()
            if not nome or nome in com_contato or nome in na_face:
                kept.append(row)
                continue
            rebaixadas.add(nome)
            exclusions.append({
                "tier": "T0_SLAB_WITHOUT_FACE_CONTACT",
                "field": f"faces.{face}.lajes",
                "identity": row.get("nome"),
                "value": row.get("dim"),
                "reason": (
                    "expected slab shares no length with this face; it only "
                    "meets it at a vertex, or lies far from it"
                ),
            })
        bucket["lajes"] = kept
        bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
        if rebaixadas and isinstance(bucket_actual, dict):
            bucket_actual["lajes"] = [
                row for row in bucket_actual.get("lajes") or []
                if str(row.get("nome") or "").upper() not in rebaixadas
            ]
    return adjusted, adjusted_actual, exclusions


def _exclude_rows_at_unreachable_corner(
    expected: dict[str, Any], actual: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Rebaixa linha cujo **canto** nomeado está longe do corredor da viga.

    Alcance por face não separa os dois extremos dela. `V321` morre na face D
    do `P24`: encosta na face A, mas fica a 80 cm do canto `AC`. O `P20`
    (verde) registra a gêmea `V313` só em `AD`.

    A guarda é por canto, não por face: se o motor põe a mesma viga no mesmo
    canto, a divergência é de papel ou de medida e o tier não entra.
    """
    import copy

    cantos = actual.get("face_corner_reach") or {}
    if not cantos:
        return expected, actual, []
    adjusted = copy.deepcopy(expected)
    adjusted_actual = copy.deepcopy(actual)
    actual_map = _face_role_map(actual)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        no_canto = {
            (row.get("nome"), row.get("canto"))
            for role in ROLES
            for row in actual_map.get((face, role), [])
        }
        for role in ("passa", "chega", "interior"):
            kept = []
            rebaixadas: set[tuple[str, str]] = set()
            for row in bucket.get(role) or []:
                nome = row.get("nome")
                canto = (row.get("canto") or "").upper()
                perto = cantos.get(canto)
                if (
                    not nome
                    or perto is None            # canto sem medição
                    or nome in perto
                    or (nome, canto) in no_canto
                ):
                    kept.append(row)
                    continue
                rebaixadas.add((nome, canto))
                exclusions.append({
                    "tier": "T0_CORNER_OUT_OF_REACH",
                    "field": f"faces.{face}.{role}",
                    "identity": f"{nome}@{canto}",
                    "value": row.get("dim"),
                    "reason": (
                        "expected corner is far from the beam corridor; the "
                        "beam reaches the other end of this face"
                    ),
                })
            bucket[role] = kept
            bucket_actual = (adjusted_actual.get("faces") or {}).get(face)
            if rebaixadas and isinstance(bucket_actual, dict):
                # O corpus errou o canto daquela viga naquela face. Onde ele
                # não sobrou com outro canto para a mesma viga, o que o motor
                # puser para ela ali fica sem julgamento — senão a linha do
                # motor vira sobra contra um corpus já rebaixado.
                sem_prova = {
                    nome for nome, _canto in rebaixadas
                    if not any(row.get("nome") == nome for row in kept)
                }
                bucket_actual[role] = [
                    row for row in bucket_actual.get(role) or []
                    if row.get("nome") not in sem_prova
                    and (row.get("nome"), (row.get("canto") or "").upper())
                    not in rebaixadas
                ]
    return adjusted, adjusted_actual, exclusions


def compare_semantics(
    expected: dict[str, Any],
    actual: dict[str, Any],
    *,
    slab_levels: set[str] | None = None,
    unproven_beam_dims: set[tuple[str, str]] | None = None,
    embedded_omission_tier: bool = False,
) -> dict[str, Any]:
    arm_beams = {
        str(row.get("nome") or "").upper()
        for fid in ("E", "F")
        for role in ("passa", "chega", "interior")
        for row in ((actual.get("faces") or {}).get(fid) or {}).get(role) or []
        if str(row.get("nome") or "")
    }
    expected, authority_exclusions = _exclude_unproven_pillar_section_beam_dims(
        expected, actual,
    )
    expected, global_dim_exclusions = _exclude_globally_unproven_beam_dims(
        expected, unproven_beam_dims or set(),
    )
    authority_exclusions = authority_exclusions + global_dim_exclusions
    expected, level_exclusions = _exclude_underivable_slab_levels(
        expected, slab_levels or set(),
    )
    expected, contained_exclusions = _defer_slab_levels_to_contained_annotation(
        expected, actual,
    )
    expected, actual, wall_exclusions = _exclude_beams_contradicted_by_wall_width(
        expected, actual,
    )
    expected, actual, reach_exclusions = _exclude_beams_out_of_reach(
        expected, actual,
    )
    expected, actual, occupancy_exclusions = _exclude_chega_without_face_occupancy(
        expected, actual,
    )
    expected, actual, crossing_exclusions = _exclude_passage_without_crossing(
        expected, actual,
    )
    expected, actual, slab_contact_exclusions = (
        _exclude_slab_contact_contradicted_by_polygon(expected, actual)
    )
    expected, actual, corner_exclusions = _exclude_rows_at_unreachable_corner(
        expected, actual,
    )
    expected, actual, slab_contact_face_exclusions = (
        _exclude_slab_without_face_contact(expected, actual)
    )
    expected, actual, corner_dist_exclusions = (
        _exclude_corner_contradicting_distances(expected, actual)
    )
    expected, actual, parallel_exclusions = (
        _exclude_arrival_parallel_to_face(expected, actual)
    )
    expected, actual, interior_gap_exclusions = (
        _exclude_interior_with_gap_on_both_sides(expected, actual)
    )
    expected, actual, interior_par_exclusions = (
        _exclude_interior_parallel_not_containing(expected, actual)
    )
    expected, actual, cap_arm_exclusions = (
        _exclude_cap_passage_already_in_arm(expected, actual, arm_beams)
    )
    expected, actual, arrival_passage_exclusions = (
        _exclude_arrival_recorded_as_passage(expected, actual)
    )
    cap_arm_exclusions = cap_arm_exclusions + arrival_passage_exclusions
    interior_par_exclusions = interior_par_exclusions + cap_arm_exclusions
    interior_gap_exclusions = interior_gap_exclusions + interior_par_exclusions
    parallel_exclusions = parallel_exclusions + interior_gap_exclusions
    corner_dist_exclusions = corner_dist_exclusions + parallel_exclusions
    slab_contact_face_exclusions = (
        slab_contact_face_exclusions + corner_dist_exclusions
    )
    corner_exclusions = corner_exclusions + slab_contact_face_exclusions
    actual, embedded_exclusions = _exclude_embedded_beam_omitted_by_corpus(
        expected, actual, enabled=embedded_omission_tier,
    )
    corner_exclusions = corner_exclusions + embedded_exclusions
    authority_exclusions = (
        authority_exclusions + level_exclusions + contained_exclusions
        + wall_exclusions + reach_exclusions + occupancy_exclusions
        + crossing_exclusions + slab_contact_exclusions + corner_exclusions
    )
    differences: list[dict[str, Any]] = []
    for field in ("orientation", "geometry_type", "face_ids"):
        expected_value = expected.get(field)
        if field in ("orientation", "geometry_type") and expected_value in (None, ""):
            continue
        if expected_value != actual.get(field):
            differences.append({"family": "identity_geometry" if field != "face_ids" else "faces", "field": field, "expected": expected.get(field), "actual": actual.get(field)})
    expected_rows = _face_role_map(expected)
    actual_rows = _face_role_map(actual)
    for key in sorted(set(expected_rows) | set(actual_rows)):
        if not _rows_semantically_equal(
            expected_rows.get(key, []), actual_rows.get(key, []),
        ):
            face, role = key
            differences.append({
                "family": "faces" if role == "lajes" else role,
                "field": f"faces.{face}.{role}",
                "expected": expected_rows.get(key, []),
                "actual": actual_rows.get(key, []),
            })
    if expected.get("face_geometry") and expected.get("face_geometry") != actual.get("face_geometry"):
        differences.append({"family": "identity_geometry", "field": "face_geometry", "expected": expected.get("face_geometry"), "actual": actual.get("face_geometry")})
    if expected.get("geometry_points") and expected.get("geometry_points") != actual.get("geometry_points"):
        differences.append({"family": "identity_geometry", "field": "geometry_points", "expected": expected.get("geometry_points"), "actual": actual.get("geometry_points")})
    if expected.get("connector_crossings") == [] and actual.get("connector_crossings") not in (None, []):
        differences.append({"family": "readability", "field": "connector_crossings", "expected": [], "actual": actual.get("connector_crossings")})
    return {
        "schema": COMPARISON_SCHEMA,
        "status": "PASS" if not differences else "FAIL",
        "difference_count": len(differences),
        "differences": differences,
        "authority_exclusions": authority_exclusions,
    }


def compare_corpus(corpus: dict[str, Any], actual_dir: Path) -> dict[str, Any]:
    parsed: dict[str, dict[str, Any] | None] = {}
    for record in corpus.get("items") or []:
        item = record["item"]
        actual_path = actual_dir / f"{item}.json"
        parsed[item] = (
            _extract_tables(json.loads(actual_path.read_text(encoding="utf-8")))
            if actual_path.is_file() else None
        )
    vocabulary = slab_level_vocabulary([p for p in parsed.values() if p])

    unproven_dims = _collect_unproven_beam_dims(corpus, parsed)
    minoria_embutida = _collect_minority_embedded_registrations(corpus, parsed)
    embedded_rate, embedded_total = embedded_beam_naming_rate(corpus, parsed)
    embedded_tier = embedded_total > 0 and embedded_rate >= EMBEDDED_NAMED_RATE
    results = []
    for record in corpus.get("items") or []:
        item = record["item"]
        actual = parsed.get(item)
        if actual is None:
            results.append({"item": item, "status": "FAIL", "difference_count": 1, "differences": [{"family": "artifact", "field": "actual", "expected": "present", "actual": "missing"}]})
            continue
        semantic_ajustado, minoria_exclusions = _exclude_minority_embedded_rows(
            _recanonize_distances(record.get("semantic") or {}),
            actual, item, minoria_embutida,
        )
        result = compare_semantics(
            semantic_ajustado,
            actual,
            slab_levels=vocabulary,
            unproven_beam_dims=unproven_dims,
            embedded_omission_tier=embedded_tier,
        )
        if minoria_exclusions:
            result["authority_exclusions"] = (
                list(result.get("authority_exclusions") or []) + minoria_exclusions
            )
        results.append({"item": item, **{key: value for key, value in result.items() if key != "schema"}})
    failed = [row for row in results if row["status"] != "PASS"]
    return {
        "schema": COMPARISON_SCHEMA,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "PASS" if not failed else "FAIL",
        "item_count": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "slab_level_vocabulary": sorted(vocabulary),
        "embedded_beam_naming": {
            "rate": round(embedded_rate, 3),
            "cases": embedded_total,
            "tier_enabled": embedded_tier,
        },
        "results": results,
    }


def _dim_pair(value: Any) -> list[float] | None:
    numbers = re.findall(r"\d+(?:[.,]\d+)?", str(value or ""))
    if len(numbers) < 2:
        return None
    return sorted(float(number.replace(",", ".")) for number in numbers[:2])


def _collect_unproven_beam_dims(
    corpus: dict[str, Any], parsed: dict[str, Any],
) -> set[tuple[str, str]]:
    """Seções de viga que só repetem a seção de um pilar — no corpus inteiro.

    A seção é propriedade da **viga**, não do item: uma viga tem uma seção só
    no desenho. Quando o corpus dá duas seções para a mesma viga e uma delas
    é exatamente a seção do pilar em que ela encosta, essa é cópia do texto do
    pilar e não vale em item nenhum. `V318` sai `19/98` (a seção de `P14`) em
    `P5`, `P14` e `P45`, e `19/120` no próprio `P14`.
    """
    dims_por_viga: dict[str, set[str]] = {}
    for record in corpus.get("items") or []:
        for bucket in ((record.get("semantic") or {}).get("faces") or {}).values():
            for role in ("passa", "chega", "interior"):
                for row in (bucket or {}).get(role) or []:
                    nome = str(row.get("nome") or "").upper()
                    dim = str(row.get("dim") or "").strip()
                    if nome and nome != "NENHUMA" and dim:
                        dims_por_viga.setdefault(nome, set()).add(dim)

    suspeitas: set[tuple[str, str]] = set()
    for record in corpus.get("items") or []:
        actual = parsed.get(record.get("item"))
        if not actual:
            continue
        points = actual.get("geometry_points") or []
        try:
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
            pillar_dims = sorted((max(xs) - min(xs), max(ys) - min(ys)))
        except (TypeError, ValueError, IndexError):
            continue
        if not points or min(pillar_dims) <= 0:
            continue
        for bucket in ((record.get("semantic") or {}).get("faces") or {}).values():
            for role in ("passa", "chega", "interior"):
                for row in (bucket or {}).get(role) or []:
                    nome = str(row.get("nome") or "").upper()
                    dim = str(row.get("dim") or "").strip()
                    pares = _dim_pair(dim)
                    if not nome or not pares or len(dims_por_viga.get(nome, ())) < 2:
                        continue
                    if all(abs(a - b) <= 0.6 for a, b in zip(pares, pillar_dims)):
                        suspeitas.add((nome, dim))
    return suspeitas


def _exclude_globally_unproven_beam_dims(
    expected: dict[str, Any], unproven: set[tuple[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Aplica em todo item a seção já desqualificada em qualquer outro."""
    if not unproven:
        return expected, []
    import copy

    adjusted = copy.deepcopy(expected)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        for role in ("passa", "chega", "interior"):
            for row in bucket.get(role) or []:
                nome = str(row.get("nome") or "").upper()
                dim = str(row.get("dim") or "").strip()
                if not dim or (nome, dim) not in unproven:
                    continue
                exclusions.append({
                    "tier": "T0_UNPROVEN",
                    "field": f"faces.{face}.{role}.dim",
                    "identity": row.get("nome"),
                    "value": dim,
                    "reason": (
                        "beam section copies a pillar section and conflicts "
                        "with the same beam's section elsewhere in the corpus"
                    ),
                })
                row["dim"] = ""
                # As distâncias daquela linha saíram dessa mesma largura: com
                # a seção rebaixada, elas deixam de ser prova junto. `VF301`
                # em `P9` dá `0/85` (largura 19) contra `0/90` (largura 14) —
                # é a seção reescrita aparecendo como divergência de medida.
                row["dist_esq_cm"] = ""
                row["dist_dir_cm"] = ""
    return adjusted, exclusions


def _pillar_bbox_of(pillar: dict) -> tuple[float, float, float, float] | None:
    from src.core.pillar_abcd_tables import _pillar_bbox

    return _pillar_bbox(pillar.get("points") or [])


def _collect_minority_embedded_registrations(
    corpus: dict[str, Any], parsed: dict[str, Any],
) -> set[tuple[str, str]]:
    """(item, viga) em que o corpus registra faixa embutida na ponta inicial
    contra a maioria dos irmãos de mesma assinatura.

    Medido no 13_PAV: a faixa embutida na ponta **final** é registrada em 10
    de 10 itens; na ponta **inicial**, em 1 de 8. O único que registra é o
    `P28`, com a mesma `VF203` que `P29`–`P32` — todos verdes, mesma largura
    de pilar — omitem. É o corpus discordando de si mesmo sobre uma viga.
    """
    grupos: dict[tuple[Any, ...], list[tuple[str, str, bool]]] = {}
    for record in corpus.get("items") or []:
        item = record.get("item")
        actual = parsed.get(item)
        if not actual:
            continue
        embutidas = actual.get("embedded_at_start") or {}
        if not embutidas:
            continue
        nomes = {
            str(row.get("nome") or "").upper()
            for bucket in ((record.get("semantic") or {}).get("faces") or {}).values()
            for role in ("passa", "chega", "interior")
            for row in (bucket or {}).get(role) or []
        }
        for viga, assinatura in embutidas.items():
            chave = (viga.upper(), tuple(assinatura))
            grupos.setdefault(chave, []).append(
                (str(item), viga.upper(), viga.upper() in nomes)
            )
    minoria: set[tuple[str, str]] = set()
    for chave, linhas in grupos.items():
        if len(linhas) < 3:
            continue
        registram = [x for x in linhas if x[2]]
        if registram and len(registram) * 2 < len(linhas):
            minoria.update((item, viga) for item, viga, _ in registram)
    return minoria


def _exclude_minority_embedded_rows(
    expected: dict[str, Any], actual: dict[str, Any], item: str,
    minoria: set[tuple[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not minoria:
        return expected, []
    import copy

    alvos = {viga for it, viga in minoria if it == item}
    if not alvos:
        return expected, []
    adjusted = copy.deepcopy(expected)
    exclusions: list[dict[str, Any]] = []
    for face, bucket in (adjusted.get("faces") or {}).items():
        for role in ("passa", "chega", "interior"):
            kept = []
            for row in bucket.get(role) or []:
                if str(row.get("nome") or "").upper() not in alvos:
                    kept.append(row)
                    continue
                exclusions.append({
                    "tier": "T0_MINORITY_EMBEDDED_REGISTRATION",
                    "field": f"faces.{face}.{role}",
                    "identity": row.get("nome"),
                    "value": row.get("dim"),
                    "reason": (
                        "corpus registers this start-embedded beam against "
                        "the majority of siblings with the same signature"
                    ),
                })
            bucket[role] = kept
    return adjusted, exclusions


def _recanonize_distances(semantic: dict[str, Any]) -> dict[str, Any]:
    """Reaplica a forma canônica de distância às linhas já gravadas no corpus.

    O corpus foi construído com a normalização da época, que preservava
    ``66.0`` como texto. Comparar texto com ``66`` acusaria divergência onde
    a distância é a mesma. A canonização vale para os dois lados.
    """
    faces = semantic.get("faces")
    if not isinstance(faces, dict):
        return semantic
    for bucket in faces.values():
        if not isinstance(bucket, dict):
            continue
        for rows in bucket.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for field in ("dist_esq_cm", "dist_dir_cm"):
                    if field in row:
                        row[field] = _clean_distance(row[field])
    return semantic


def _extend_through_crossed_support(
    runs: list[tuple[float, float, float, float]],
    corridor: tuple[float, float, float, float],
    supports: list[tuple[float, float, float, float]],
    *,
    horizontal: bool,
    tol: float = 2.0,
) -> tuple[float, float, float, float] | None:
    """Estende o trecho através do pilar que a viga demonstravelmente cruza.

    Só quando as três coisas valem: a viga morre rente ao pilar, o pilar tem
    a largura dela na direção transversal (o desenho não repete o trecho
    dentro do apoio) e o corredor recuperado continua do outro lado.
    """
    if not runs:
        return None
    spans = [
        (run[0], run[2]) if horizontal else (run[1], run[3]) for run in runs
    ]
    across = [
        (run[1], run[3]) if horizontal else (run[0], run[2]) for run in runs
    ]
    start, end = min(s[0] for s in spans), max(s[1] for s in spans)
    low, high = min(a[0] for a in across), max(a[1] for a in across)
    corridor_start, corridor_end = (
        (corridor[0], corridor[2]) if horizontal else (corridor[1], corridor[3])
    )
    changed = False
    for x0, y0, x1, y1 in supports:
        s_lo, s_hi = (x0, x1) if horizontal else (y0, y1)
        a_lo, a_hi = (y0, y1) if horizontal else (x0, x1)
        if min(a_hi, high) - max(a_lo, low) <= tol:
            continue
        # O pilar tem a largura da viga: nem mais estreito, nem transbordando.
        if abs(a_lo - low) > tol or abs(a_hi - high) > tol:
            continue
        if abs(s_hi - start) <= tol and corridor_start <= s_lo + tol:
            start, changed = s_lo, True
        elif abs(s_lo - end) <= tol and corridor_end >= s_hi - tol:
            end, changed = s_hi, True
    if not changed:
        return None
    return (start, low, end, high) if horizontal else (low, start, high, end)


#: Alcance (cm) para uma cota do desenho ser candidata a seção de uma viga
#: cuja leitura veio corrompida.
SECTION_TEXT_REACH_CM = 120.0
#: Distância (cm) até a face dentro da qual uma viga ainda pode ter vínculo
#: com ela. Generosa de propósito: pela regra R1 do dono, o vão entre o fim da
#: viga e a face é continuação da viga, e no 13_PAV esse vão chega a 38 cm
#: (V313 × P29, com V306 no meio). O alcance precisa cobrir isso, senão o
#: gate marcaria como impossível justamente o que ele decidiu que vale.
#: Ver docs/INTERPRETACAO-VIGA-CHEGA-VAO-E-FACE.md.
FACE_REACH_CM = 60.0

#: Sobreposição mínima (cm) para contar como contato, e não como toque de
#: vértice.
FACE_SPAN_OVERLAP_CM = 1.0

#: Sobra mínima (cm) de pilar para a viga contar como engolida por ele.
EMBEDDED_MARGIN_CM = 5.0


def face_geometry(pillar: dict) -> dict[str, dict[str, Any]]:
    """Geometria de cada face para medir: onde ela está e até onde vai o corpo.

    Retangular sai da caixa (A–D); em L sai do **contorno real** (A–F), com o
    corpo do pilar tomado dos retângulos que a face toca. Sem isso, E e F
    ficam sem medição nenhuma e todo tier as ignora — foi o que deixou
    `V329` nomeada nas faces do pé do `P27`, a 218 cm de distância.

    Por face: ``axis`` é o eixo do comprimento dela, ``f0``/``f1`` os extremos
    nesse eixo, ``fixed`` a coordenada da face no eixo perpendicular e
    ``body_lo``/``body_hi`` o quanto o corpo do pilar ocupa nesse eixo.
    """
    from src.core.pillar_special_faces import (
        rectangular_pieces, special_l_face_segments,
    )

    points = pillar.get("points") or []
    try:
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
    except (TypeError, ValueError, IndexError):
        return {}
    if len(xs) < 2:
        return {}
    px0, py0, px1, py1 = min(xs), min(ys), max(xs), max(ys)

    segments = special_l_face_segments(points)
    if not segments:
        horizontal = (px1 - px0) >= (py1 - py0)
        bruto = (
            {"A": ("x", px0, px1, py0), "B": ("x", px0, px1, py1),
             "C": ("y", py0, py1, px0), "D": ("y", py0, py1, px1)}
            if horizontal else
            {"A": ("y", py0, py1, px0), "B": ("y", py0, py1, px1),
             "C": ("x", px0, px1, py1), "D": ("x", px0, px1, py0)}
        )
        return {
            face: {
                "axis": axis, "f0": f0, "f1": f1, "fixed": fixed,
                "body_lo": (py0 if axis == "x" else px0),
                "body_hi": (py1 if axis == "x" else px1),
            }
            for face, (axis, f0, f1, fixed) in bruto.items()
        }

    pieces = rectangular_pieces(points)
    geometria: dict[str, dict[str, Any]] = {}
    for face, edge in segments.items():
        (ex0, ey0), (ex1, ey1) = edge["p0"], edge["p1"]
        if abs(ey1 - ey0) <= abs(ex1 - ex0):
            axis, f0, f1, fixed = "x", min(ex0, ex1), max(ex0, ex1), (ey0 + ey1) / 2.0
        else:
            axis, f0, f1, fixed = "y", min(ey0, ey1), max(ey0, ey1), (ex0 + ex1) / 2.0
        # Corpo do pilar no eixo perpendicular, só nos pedaços que a face toca.
        tocados = []
        for qx0, qy0, qx1, qy1 in pieces:
            a0, a1 = (qx0, qx1) if axis == "x" else (qy0, qy1)
            if min(a1, f1) - max(a0, f0) <= 1e-6:
                continue
            tocados.append((qy0, qy1) if axis == "x" else (qx0, qx1))
        geometria[face] = {
            "axis": axis, "f0": f0, "f1": f1, "fixed": fixed,
            "body_lo": min((t[0] for t in tocados), default=py0 if axis == "x" else px0),
            "body_hi": max((t[1] for t in tocados), default=py1 if axis == "x" else px1),
        }
    return geometria


def beams_within_reach_of_faces(
    pillar: dict, beams: list[dict], *, reach: float = FACE_REACH_CM,
) -> dict[str, list[str]]:
    """Vigas cujo corredor chega perto de cada face do pilar.

    Não é o vínculo — é o **alcance**: se o corredor da viga nem passa perto
    da face, nenhuma leitura a coloca ali. Serve para separar erro de papel
    (o motor pode errar `passa` × `chega`) de célula impossível.
    """
    from src.core.pillar_face_beams import beam_bbox_from_entity, beam_runs_from_entity

    geometria = face_geometry(pillar)
    if not geometria:
        return {}
    faces = {
        face: (
            (dados["f0"], dados["fixed"], dados["f1"], dados["fixed"])
            if dados["axis"] == "x"
            else (dados["fixed"], dados["f0"], dados["fixed"], dados["f1"])
        )
        for face, dados in geometria.items()
    }
    reachable: dict[str, list[str]] = {face: [] for face in faces}
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = str(beam.get("name") or "").strip()
        bbox = beam_bbox_from_entity(beam)
        if not name or not bbox:
            continue
        for run in beam_runs_from_entity(beam) or [bbox]:
            rx0, ry0, rx1, ry1 = run
            for face, (fx0, fy0, fx1, fy1) in faces.items():
                if name in reachable[face]:
                    continue
                dx = max(min(fx0, fx1) - rx1, rx0 - max(fx0, fx1), 0.0)
                dy = max(min(fy0, fy1) - ry1, ry0 - max(fy0, fy1), 0.0)
                if (dx * dx + dy * dy) ** 0.5 <= reach:
                    reachable[face].append(name)
    return reachable


#: Afastamento máximo (cm) da laje à linha da face para o contato valer.
SLAB_FACE_SIDE_CM = 30.0


def slabs_touching_faces(
    pillar: dict,
    slab_points_map: dict,
    *,
    min_contact: float = FACE_SPAN_OVERLAP_CM,
    side: float = SLAB_FACE_SIDE_CM,
) -> dict[str, list[str]]:
    """Lajes com contato **ao longo** de cada face, não só num vértice.

    Mesma régua que o motor já usa internamente
    (`prune_slabs_without_face_contact`), agora medida também para as faces
    E e F do pilar em L. `L325` encosta no `P26` só pelo canto da dobra, e
    `L317` está a 438 cm da face que o corpus lhe dá.
    """
    from src.core.pillar_special_faces import _bbox_of

    geometria = face_geometry(pillar)
    if not geometria:
        return {}
    tocando: dict[str, list[str]] = {face: [] for face in geometria}
    for nome, points in (slab_points_map or {}).items():
        bbox = _bbox_of(points)
        if not bbox:
            continue
        sx0, sy0, sx1, sy1 = bbox
        for face, dados in geometria.items():
            if dados["axis"] == "x":
                contato = min(dados["f1"], sx1) - max(dados["f0"], sx0)
                lado = max(dados["fixed"] - sy1, sy0 - dados["fixed"], 0.0)
            else:
                contato = min(dados["f1"], sy1) - max(dados["f0"], sy0)
                lado = max(dados["fixed"] - sx1, sx0 - dados["fixed"], 0.0)
            if contato > min_contact and lado <= side:
                tocando[face].append(str(nome).upper())
    return tocando


def beams_embedded_in_pillar(
    pillar: dict, beams: list[dict], *, min_overlap: float = FACE_SPAN_OVERLAP_CM,
) -> list[str]:
    """Vigas cuja faixa cai **dentro** da pegada do pilar.

    O pilar engole a viga numa das direções: a base do `P12` (19×98) fica
    inteira dentro da faixa E–O da `V302`. É a configuração mais fácil de o
    corpus deixar passar, porque no desenho a viga some dentro da hachura.
    """
    from src.core.pillar_face_beams import beam_runs_from_entity, beam_bbox_from_entity

    points = pillar.get("points") or []
    try:
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
    except (TypeError, ValueError, IndexError):
        return []
    if len(xs) < 2:
        return []
    px0, py0, px1, py1 = min(xs), min(ys), max(xs), max(ys)
    embutidas: list[str] = []
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = str(beam.get("name") or "").strip()
        bbox = beam_bbox_from_entity(beam)
        if not name or not bbox or name in embutidas:
            continue
        for run in beam_runs_from_entity(beam) or [bbox]:
            rx0, ry0, rx1, ry1 = run
            a0, a1 = min(rx0, rx1), max(rx0, rx1)
            b0, b1 = min(ry0, ry1), max(ry0, ry1)
            if (min(px1, a1) - max(px0, a0) <= min_overlap
                    or min(py1, b1) - max(py0, b0) <= min_overlap):
                continue
            # Engolida de verdade: a faixa da viga cabe dentro do pilar
            # naquele eixo **e sobra pilar** de pelo menos um lado. Faixa que
            # coincide com o pilar (`V301` no `P48`, 19 contra 19) é outra
            # configuração — ali a viga é o próprio corpo do pilar.
            dentro_x = (
                a0 >= px0 - 1.0 and a1 <= px1 + 1.0
                and (a0 - px0 > EMBEDDED_MARGIN_CM or px1 - a1 > EMBEDDED_MARGIN_CM)
            )
            dentro_y = (
                b0 >= py0 - 1.0 and b1 <= py1 + 1.0
                and (b0 - py0 > EMBEDDED_MARGIN_CM or py1 - b1 > EMBEDDED_MARGIN_CM)
            )
            if dentro_x or dentro_y:
                embutidas.append(name)
                break
    return embutidas


def beams_near_face_corners(
    pillar: dict, beams: list[dict], *, reach: float = FACE_REACH_CM,
) -> dict[str, list[str]]:
    """Vigas cujo corredor chega perto de cada **canto** nomeável do pilar.

    O alcance por face não separa os dois extremos dela: `V321` morre na face
    D do `P24` e fica a 0 cm da face A — mas a 80 cm do canto `AC`, que é o
    outro extremo. Precedente medido: o `P20` (verde) registra a gêmea `V313`
    só no canto `AD`, nunca no `AC`.
    """
    import math

    from src.core.pillar_face_beams import beam_bbox_from_entity, beam_runs_from_entity

    geometria = face_geometry(pillar)
    if not geometria:
        return {}
    pontos: dict[str, tuple[float, float]] = {}
    for face, dados in geometria.items():
        for outra, vizinha in geometria.items():
            if outra == face or vizinha["axis"] == dados["axis"]:
                continue
            ponto = (
                (vizinha["fixed"], dados["fixed"]) if dados["axis"] == "x"
                else (dados["fixed"], vizinha["fixed"])
            )
            # O canto só existe se a face vizinha realmente termina ali.
            if not (dados["f0"] - 0.6 <= (ponto[0] if dados["axis"] == "x" else ponto[1])
                    <= dados["f1"] + 0.6):
                continue
            pontos[f"{face}{outra}"] = ponto
    perto: dict[str, list[str]] = {canto: [] for canto in pontos}
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = str(beam.get("name") or "").strip()
        bbox = beam_bbox_from_entity(beam)
        if not name or not bbox:
            continue
        for run in beam_runs_from_entity(beam) or [bbox]:
            rx0, ry0, rx1, ry1 = run
            for canto, (cx, cy) in pontos.items():
                if name in perto[canto]:
                    continue
                dx = max(min(rx0, rx1) - cx, cx - max(rx0, rx1), 0.0)
                dy = max(min(ry0, ry1) - cy, cy - max(ry0, ry1), 0.0)
                if math.hypot(dx, dy) <= reach:
                    perto[canto].append(name)
    return perto


def horizontal_beam(beam: dict) -> bool:
    from src.core.pillar_face_beams import (
        beam_axis_is_horizontal, beam_bbox_from_entity,
    )

    return beam_axis_is_horizontal(beam, fallback_bbox=beam_bbox_from_entity(beam))


def _run_thickness_matches_run(
    run: tuple[float, float, float, float], dim: Any, horizontal: bool,
) -> bool:
    from src.core.pillar_face_beams import _run_thickness_matches_section

    x0, y0, x1, y1 = run
    espessura = abs(y1 - y0) if horizontal else abs(x1 - x0)
    return _run_thickness_matches_section(espessura, dim)


def _run_thickness_is_inflated(
    runs: list[tuple[float, float, float, float]],
    dim: Any,
    *,
    horizontal: bool,
) -> bool:
    """O trecho traçado tem espessura que nenhuma viga daquela seção teria.

    Bbox de trechos disjuntos ou de diagonal engorda o corredor: `V329` sai
    com 68 cm para uma seção de 19, porque absorveu segmentos da `V304`.
    """
    from src.core.pillar_face_beams import _run_thickness_matches_section

    if not runs or not dim:
        return False
    for x0, y0, x1, y1 in runs:
        espessura = abs(y1 - y0) if horizontal else abs(x1 - x0)
        if not _run_thickness_matches_section(espessura, dim):
            return True
    return False


#: Folga (cm) para o rótulo cair fora do corredor reparado — ele é desenhado
#: rente à ponta da viga, às vezes um pouco além dela.
LABEL_INSIDE_TOL_CM = 20.0


def beams_overlapping_face_span(
    pillar: dict,
    beams: list[dict],
    *,
    min_overlap: float = FACE_SPAN_OVERLAP_CM,
    reach: float = FACE_REACH_CM,
) -> dict[str, list[str]]:
    """Vigas que ocupam algum comprimento da face, no eixo da própria face.

    Uma viga que **chega** ocupa parte da face: é isso que `dist_esq`/
    `dist_dir` medem. Viga que morre perpendicular a uma face curta ocupa
    aquela face — e ocupa **zero** das faces vizinhas, ainda que encoste no
    canto delas. Alcance (`beams_within_reach_of_faces`) não separa os dois
    casos, porque a distância é zero nos dois; a ocupação separa.
    """
    from src.core.pillar_face_beams import beam_runs_from_entity, beam_bbox_from_entity

    geometria = face_geometry(pillar)
    if not geometria:
        return {}
    # A viga precisa das duas coisas: estar naquela face e ocupar
    # comprimento dela.
    spans = {
        face: (dados["axis"], dados["f0"], dados["f1"], dados["fixed"])
        for face, dados in geometria.items()
    }
    occupying: dict[str, list[str]] = {face: [] for face in spans}
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = str(beam.get("name") or "").strip()
        bbox = beam_bbox_from_entity(beam)
        if not name or not bbox:
            continue
        for run in beam_runs_from_entity(beam) or [bbox]:
            rx0, ry0, rx1, ry1 = run
            for face, (axis, f0, f1, fixed) in spans.items():
                if name in occupying[face]:
                    continue
                if axis == "x":
                    r0, r1 = min(rx0, rx1), max(rx0, rx1)
                    t0, t1 = min(ry0, ry1), max(ry0, ry1)
                else:
                    r0, r1 = min(ry0, ry1), max(ry0, ry1)
                    t0, t1 = min(rx0, rx1), max(rx0, rx1)
                if min(f1, r1) - max(f0, r0) <= min_overlap:
                    continue
                if max(t0 - fixed, fixed - t1, 0.0) > reach:
                    continue
                occupying[face].append(name)
    return occupying


def measured_slab_contacts(
    pillar: dict, slab_points_map: dict, *, vertical: bool = True,
) -> dict[str, dict[str, list[float]]]:
    """Contato medido de cada laje em cada face, pelo polígono da própria laje.

    O corpus é fiel à medição em 86 das 92 linhas de laje do 13_PAV — quando
    diverge, é porque a laje para numa viga que aquele item não registrou.
    """
    from src.core.pillar_abcd_tables import (
        _bbox_from_points, _pillar_bbox, span_dists_on_face,
    )

    pbb = _pillar_bbox(pillar.get("points") or [])
    if not pbb:
        return {}
    contatos: dict[str, dict[str, list[float]]] = {face: {} for face in "ABCD"}
    for nome, points in (slab_points_map or {}).items():
        bbox = _bbox_from_points(points)
        if not bbox:
            continue
        for face in "ABCD":
            de, dd = span_dists_on_face(face, pbb, bbox, vertical=vertical)
            if de is None:
                continue
            contatos[face][str(nome).upper()] = [round(de, 2), round(dd, 2)]
    return contatos


def beams_covering_faces(
    pillar: dict, beams: list[dict], *, tol: float = 0.6,
) -> dict[str, list[str]]:
    """Vigas cujo corredor cobre a face **inteira**.

    Regra do dono (2026-08-22): "viga interior é que toda a face do pilar
    está dentro da viga; se for 0 a distância de cada parede, é totalmente
    interna". Cobertura total é medível — e é o que separa `interior` de uma
    chegada que sobra face dos dois lados.
    """
    from src.core.pillar_face_beams import beam_runs_from_entity, beam_bbox_from_entity

    geometria = face_geometry(pillar)
    if not geometria:
        return {}
    cobrindo: dict[str, list[str]] = {face: [] for face in geometria}
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        nome = str(beam.get("name") or "").strip()
        bbox = beam_bbox_from_entity(beam)
        if not nome or not bbox:
            continue
        for run in beam_runs_from_entity(beam) or [bbox]:
            if not run:
                continue
            rx0, ry0, rx1, ry1 = run
            for face, dados in geometria.items():
                if nome in cobrindo[face]:
                    continue
                a0, a1 = (
                    (min(rx0, rx1), max(rx0, rx1)) if dados["axis"] == "x"
                    else (min(ry0, ry1), max(ry0, ry1))
                )
                if a0 <= dados["f0"] + tol and a1 >= dados["f1"] - tol:
                    cobrindo[face].append(nome)
    return cobrindo


def beams_arriving_and_dying(
    pillar: dict, beams: list[dict], *, tol: float = 2.0,
) -> dict[str, list[str]]:
    """Vigas que entram por aquela face **vindas de fora** e morrem no pilar.

    É a configuração da R4 do dono: a viga chega na esquina daquela face e,
    por chegar na esquina, é passante do lado da tampa curta. Quem atravessa
    (sai pela face oposta) não entra aqui.
    """
    from src.core.pillar_face_beams import beam_runs_from_entity, beam_bbox_from_entity

    geometria = face_geometry(pillar)
    if not geometria:
        return {}
    oposta = {"A": "B", "B": "A", "C": "D", "D": "C"}
    saida: dict[str, list[str]] = {face: [] for face in geometria}
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        nome = str(beam.get("name") or "").strip()
        bbox = beam_bbox_from_entity(beam)
        if not nome or not bbox:
            continue
        trechos = [r for r in (beam_runs_from_entity(beam) or [bbox]) if r]
        for face, dados in geometria.items():
            outra = geometria.get(oposta.get(face, ""))
            if not outra:
                continue
            eixo = "x" if dados["axis"] == "y" else "y"
            de_fora = atravessa = False
            for rx0, ry0, rx1, ry1 in trechos:
                t0, t1 = (
                    (min(rx0, rx1), max(rx0, rx1)) if eixo == "x"
                    else (min(ry0, ry1), max(ry0, ry1))
                )
                if dados["fixed"] < outra["fixed"]:
                    if t0 < dados["fixed"] - tol:
                        de_fora = True
                    if t1 > outra["fixed"] + tol:
                        atravessa = True
                else:
                    if t1 > dados["fixed"] + tol:
                        de_fora = True
                    if t0 < outra["fixed"] - tol:
                        atravessa = True
            if de_fora and not atravessa:
                saida[face].append(nome)
    return saida


def beams_containing_face(
    pillar: dict, beams: list[dict], *, tol: float = 1.0,
) -> dict[str, list[str]]:
    """Vigas cujo corredor **contém** o segmento inteiro da face.

    Diferente de cobrir o vão da face: aqui a linha da face também tem de
    cair dentro da faixa transversal da viga. `V301` contém a face C do
    `P48`; `V325` passa 15 cm ao lado dela.
    """
    from src.core.pillar_face_beams import beam_runs_from_entity, beam_bbox_from_entity

    geometria = face_geometry(pillar)
    if not geometria:
        return {}
    contendo: dict[str, list[str]] = {face: [] for face in geometria}
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        nome = str(beam.get("name") or "").strip()
        bbox = beam_bbox_from_entity(beam)
        if not nome or not bbox:
            continue
        for run in beam_runs_from_entity(beam) or [bbox]:
            if not run:
                continue
            rx0, ry0, rx1, ry1 = run
            for face, dados in geometria.items():
                if nome in contendo[face]:
                    continue
                if dados["axis"] == "x":
                    ao_longo = (min(rx0, rx1), max(rx0, rx1))
                    transversal = (min(ry0, ry1), max(ry0, ry1))
                else:
                    ao_longo = (min(ry0, ry1), max(ry0, ry1))
                    transversal = (min(rx0, rx1), max(rx0, rx1))
                if (
                    ao_longo[0] <= dados["f0"] + tol
                    and ao_longo[1] >= dados["f1"] - tol
                    and transversal[0] <= dados["fixed"] + tol
                    and transversal[1] >= dados["fixed"] - tol
                ):
                    contendo[face].append(nome)
    return contendo


def beams_crossing_into_pillar(
    pillar: dict, beams: list[dict], *, min_overlap: float = FACE_SPAN_OVERLAP_CM,
) -> dict[str, list[str]]:
    """Vigas cujo corredor entra no pilar atravessando aquela face.

    `passa` afirma travessia: a viga entra por uma face e sai. Uma viga que
    morre **encostada** na face fica inteira do lado de fora — no eixo
    perpendicular à face, o corredor dela não divide um centímetro com o
    pilar. É o caso de `V314` em `P12`, que desce do norte e para no topo.
    Precedente medido: `P20` (verde) chama de `interior`, não de `passa`, a
    `V313` que morre na face D dele.
    """
    from src.core.pillar_face_beams import beam_runs_from_entity, beam_bbox_from_entity

    faces = face_geometry(pillar)
    if not faces:
        return {}
    # Por face: (eixo perpendicular, extremos do corpo nesse eixo,
    #            eixo do comprimento da face, extremos da face nesse eixo).
    geometria = {
        face: (
            ("y" if dados["axis"] == "x" else "x"),
            dados["body_lo"], dados["body_hi"],
            dados["axis"], dados["f0"], dados["f1"],
        )
        for face, dados in faces.items()
    }
    crossing: dict[str, list[str]] = {face: [] for face in geometria}
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = str(beam.get("name") or "").strip()
        bbox = beam_bbox_from_entity(beam)
        if not name or not bbox:
            continue
        # Trecho com espessura que não é daquela seção não prova travessia:
        # é bbox de pedaços disjuntos. `V329` sai com 68 cm para 19 porque
        # absorveu segmentos da `V304`. E o corredor **medido** também não
        # prova: no `P27` ele engole a perna do pilar, cujas arestas são as
        # próprias paredes do corredor.
        section = beam.get("dim") or beam.get("dimension")
        deitada = horizontal_beam(beam)
        for run in beam_runs_from_entity(beam) or [bbox]:
            if not run or not _run_thickness_matches_run(run, section, deitada):
                continue
            rx0, ry0, rx1, ry1 = run
            for face, (eixo, lo, hi, eixo_face, f0, f1) in geometria.items():
                if name in crossing[face]:
                    continue
                a0, a1 = (
                    (min(rx0, rx1), max(rx0, rx1)) if eixo == "x"
                    else (min(ry0, ry1), max(ry0, ry1))
                )
                if min(a1, hi) - max(a0, lo) <= min_overlap:
                    continue  # não entra no corpo do pilar
                b0, b1 = (
                    (min(rx0, rx1), max(rx0, rx1)) if eixo_face == "x"
                    else (min(ry0, ry1), max(ry0, ry1))
                )
                if min(b1, f1) - max(b0, f0) <= min_overlap:
                    continue  # entra, mas por outra face
                crossing[face].append(name)

    # O desenho **não repete** o trecho da viga dentro do pilar: o corredor
    # chega de um lado e recomeça do outro. Ter trechos alinhados nos dois
    # lados prova a travessia tão bem quanto um trecho por dentro — é a R1 do
    # dono aplicada aqui. Sem isto o tier passou de 7 para 90 linhas quando os
    # corredores viraram trechos precisos, e escondia erro de motor.
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = str(beam.get("name") or "").strip()
        bbox = beam_bbox_from_entity(beam)
        if not name or not bbox:
            continue
        section = beam.get("dim") or beam.get("dimension")
        deitada = horizontal_beam(beam)
        trechos = [
            run for run in (beam_runs_from_entity(beam) or [bbox])
            if run and _run_thickness_matches_run(run, section, deitada)
        ]
        for face, (eixo, lo, hi, eixo_face, f0, f1) in geometria.items():
            if name in crossing[face]:
                continue
            antes = depois = False
            for rx0, ry0, rx1, ry1 in trechos:
                b0, b1 = (
                    (min(rx0, rx1), max(rx0, rx1)) if eixo_face == "x"
                    else (min(ry0, ry1), max(ry0, ry1))
                )
                if min(b1, f1) - max(b0, f0) <= min_overlap:
                    continue  # não está alinhado com esta face
                a0, a1 = (
                    (min(rx0, rx1), max(rx0, rx1)) if eixo == "x"
                    else (min(ry0, ry1), max(ry0, ry1))
                )
                if a1 <= lo + min_overlap:
                    antes = True
                elif a0 >= hi - min_overlap:
                    depois = True
            if antes and depois:
                crossing[face].append(name)
    return crossing


def _pillar_supports(pillars: list[dict]) -> list[tuple[float, float, float, float]]:
    """Caixas dos pilares — delega à fonte única (`beam_corridor_recovery`).

    Compartilhada com o motor de produção (`main.py`): mesma medição nos
    dois lados, sem duplicar a lógica.
    """
    from src.core.beam_corridor_recovery import pillar_support_boxes

    return pillar_support_boxes(pillars)


def _recover_beam_corridors(
    dxf_path: Path | None, beams: list[dict],
    supports: list[tuple[float, float, float, float]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Corredor físico de cada viga — delega à fonte única.

    `src.core.beam_corridor_recovery.recover_pillar_beam_corridors` é a
    mesma função que o motor de produção (`main.py`) chama; este wrapper
    só fixa os limiares que o comparador de QA sempre usou, para não mudar
    resultado nenhum do 13_PAV com o refactor.
    """
    from src.core.beam_corridor_recovery import recover_pillar_beam_corridors

    return recover_pillar_beam_corridors(
        dxf_path, beams, supports,
        section_text_reach_cm=SECTION_TEXT_REACH_CM,
        label_inside_tol_cm=LABEL_INSIDE_TOL_CM,
    )


def _slab_label_positions(db_path: Path, project_id: str) -> dict[str, tuple[float, float]]:
    """Posição do rótulo de cada laje, usada só como evidência fraca."""
    import sqlite3

    positions: dict[str, tuple[float, float]] = {}
    connection = sqlite3.connect(str(db_path))
    try:
        for name, extra in connection.execute(
            "SELECT name, extra_data_json FROM slabs WHERE project_id=?", (project_id,),
        ):
            try:
                pos = (json.loads(extra or "{}") or {}).get("pos")
            except json.JSONDecodeError:
                continue
            if pos and len(pos) >= 2:
                positions[name] = (float(pos[0]), float(pos[1]))
    finally:
        connection.close()
    return positions


def recompute_slab_levels_from_dxf(
    dxf_path: Path | None,
    slab_points_map: dict,
    slab_pos_map: dict,
    *,
    reference_level: float | None,
    floor_height: float | None,
    label_radius: float = 200.0,
) -> tuple[dict[str, str], dict[str, str]]:
    """Reavalia o nível de cada laje pela autoridade geométrica da anotação.

    Devolve (nível por laje, proveniência por laje). Laje sem base geométrica
    fica sem nível: o gate precisa distinguir "o motor não sabe" de "o motor
    afirma", e herdar o valor do banco esconderia justamente essa diferença.
    """
    from src.core.slab_level_inference import select_plan_level_annotation

    levels: dict[str, str] = {}
    provenance: dict[str, str] = {}
    inherited_from: dict[str, list[str]] = {}
    if not dxf_path or not Path(dxf_path).is_file():
        return levels, provenance
    try:
        import ezdxf
    except ImportError:
        return levels, provenance

    doc = ezdxf.readfile(str(dxf_path))
    candidates: list[dict[str, Any]] = []
    for entity in doc.modelspace():
        if entity.dxftype() not in ("TEXT", "MTEXT"):
            continue
        try:
            text = (
                entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text
            ).strip()
            insert = entity.dxf.insert
        except Exception:
            continue
        if not re.fullmatch(r"[+-]?\d+[.,]\d+", text):
            continue
        candidates.append({
            "value": float(text.replace(",", ".")),
            "text": text,
            "pos": (float(insert[0]), float(insert[1])),
        })

    for name, points in (slab_points_map or {}).items():
        selected = select_plan_level_annotation(
            points, candidates,
            label_pos=slab_pos_map.get(name),
            reference_level=reference_level,
            floor_height=floor_height,
            label_radius=label_radius,
        )
        if selected:
            levels[name] = selected["text"]
            provenance[name] = selected["provenance"]
        else:
            provenance[name] = "sem_evidencia_local"

    # Laje sem anotação própria continua o nível do painel vizinho. É mais
    # forte que o valor herdado do banco, que veio da escolha por proximidade.
    from src.core.slab_level_inference import inherit_level_from_neighbours

    for name, (value, sources) in inherit_level_from_neighbours(
        slab_points_map, levels, provenance,
    ).items():
        levels[name] = value
        provenance[name] = "herdada_do_painel"
        inherited_from[name] = sources
    return levels, provenance


def export_db_semantics(
    db_path: Path,
    project_id: str,
    obra: str,
    pav: str,
    out_dir: Path,
    *,
    recompute_topology: bool = True,
) -> dict[str, Any]:
    """Exporta o builder canônico atual sem gerar HTML ou alterar o DB.

    Por padrão a topologia de faces é **recalculada** a partir da geometria,
    porque a pergunta do gate é o que o motor produz hoje. Lendo o
    ``face_beams`` gravado, a medição descreveria a rodada que povoou o banco,
    e um fix no motor não apareceria até alguém reprocessar. Use
    ``recompute_topology=False`` para inspecionar o que está persistido.
    """
    from scripts.arete.pil_agentic_highlight_draw import load_project
    from src.core.niveis_extractor import get_pavimento_niveis_abs
    from src.core.pillar_abcd_tables import (
        build_abcd_tables_from_pillar,
        validate_face_slab_beam_invariant,
    )
    from src.core.pillar_db_hydration import hydrate_pillar_lajes_from_db
    from src.core.pillar_special_faces import enrich_special_pillar_tables

    dxf_path, slab_h, slab_n, slab_points, beams, pillars = load_project(
        db_path, project_id, obra, pav,
    )
    hydrate_pillar_lajes_from_db(db_path, project_id, pillars)
    corridors: dict[str, Any] = {}
    if recompute_topology:
        from src.core.pillar_face_beams import enrich_pillar_report_with_beams

        corridors, measured = _recover_beam_corridors(
            dxf_path, beams, _pillar_supports(pillars),
        )
        for beam in beams:
            name = str(beam.get("name") or "")
            corridor = corridors.get(name)
            if corridor:
                beam["_recovered_corridor"] = corridor
            if measured.get(name):
                beam["_measured_corridor"] = measured[name]
        report = {}
        for pillar in pillars:
            pillar.setdefault(
                "lajes", pillar.get("lajes") or pillar.get("lajes_adjacentes") or [],
            )
            report[pillar["name"]] = pillar
        enrich_pillar_report_with_beams(report, beams)
    levels = get_pavimento_niveis_abs(obra, pav) or {}
    default_level = f"{levels.get('chegada_abs')}cm" if levels.get("chegada_abs") is not None else ""
    slab_level_provenance: dict[str, str] = {}
    if recompute_topology:
        slab_pos = _slab_label_positions(db_path, project_id)
        recomputed, slab_level_provenance = recompute_slab_levels_from_dxf(
            dxf_path, slab_points, slab_pos,
            reference_level=levels.get("chegada_abs"),
            floor_height=levels.get("altura_m"),
        )
        # A anotação contida sobrepõe, porque é a prova geométrica do vínculo.
        # Fora dela o valor do banco permanece: ele carrega o resto do
        # pipeline de nível (faixa do pavimento, contexto de corte) que esta
        # recomputação não reproduz, e descartá-lo mediria um motor menor do
        # que o real. A proveniência acompanha para o gate saber o que é prova.
        slab_n = {
            name: (
                recomputed[name]
                if slab_level_provenance.get(name) in ADOPTED_LEVEL_PROVENANCE
                and name in recomputed
                else slab_n.get(name, "")
            )
            for name in slab_points
        }
    from src.core.pillar_face_beams import beam_corridor_widths

    beam_widths = beam_corridor_widths(beams) if recompute_topology else {}
    out_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str | None] = {}
    incoherent: dict[str, int] = {}
    for pillar in pillars:
        tables = build_abcd_tables_from_pillar(
            pillar,
            slab_height_map=slab_h,
            slab_nivel_map=slab_n,
            slab_points_map=slab_points,
            beams=beams,
            nivel_viga_default=default_level,
        )
        tables = enrich_special_pillar_tables(
            tables, pillar,
            slab_height_map=slab_h,
            slab_nivel_map=slab_n,
            slab_points_map=slab_points,
            beams=beams,
            nivel_viga_default=default_level,
        )
        tables["item"] = pillar["name"]
        tables["geometry_points"] = pillar.get("points") or []
        # Coerência interna da própria leitura: não depende do corpus humano,
        # então localiza face incoerente mesmo em pavimento sem aprovação.
        tables["face_slab_beam_violations"] = validate_face_slab_beam_invariant(tables)
        if recompute_topology:
            tables["face_beam_reach"] = beams_within_reach_of_faces(pillar, beams)
            tables["face_beam_span_overlap"] = beams_overlapping_face_span(
                pillar, beams
            )
            tables["face_beam_crosses"] = beams_crossing_into_pillar(pillar, beams)
            tables["face_corner_reach"] = beams_near_face_corners(pillar, beams)
            tables["embedded_beams"] = beams_embedded_in_pillar(pillar, beams)
            tables["face_slab_touching"] = slabs_touching_faces(pillar, slab_points)
            tables["face_beam_covering"] = beams_covering_faces(pillar, beams)
            tables["face_beam_containing"] = beams_containing_face(pillar, beams)
            tables["face_beam_arrives_dying"] = beams_arriving_and_dying(
                pillar, beams
            )
            tables["face_geometry_span"] = {
                face: round(dados["f1"] - dados["f0"], 2)
                for face, dados in (face_geometry(pillar) or {}).items()
            }
            from src.core.pillar_abcd_tables import beams_embedded_at_start
            tables["embedded_at_start"] = beams_embedded_at_start(
                _pillar_bbox_of(pillar), beams, pillar.get("points") or [],
            )
            tables["beam_axis_horizontal"] = {
                str(beam.get("name") or ""): horizontal_beam(beam)
                for beam in beams or [] if beam.get("name")
            }
            tables["face_axis_horizontal"] = {
                face: dados["axis"] == "x"
                for face, dados in (face_geometry(pillar) or {}).items()
            }
            tables["face_slab_contact"] = measured_slab_contacts(
                pillar, slab_points, vertical=(tables.get("orientation") != "horizontal"),
            )
        if beam_widths:
            tables["beam_corridor_width"] = {
                name: width for name, width in beam_widths.items()
                if any(
                    row.get("nome") == name
                    for bucket in (tables.get("faces") or {}).values()
                    for role in ("passa", "chega", "interior")
                    for row in bucket.get(role) or []
                )
            }
        if slab_level_provenance:
            tables["slab_level_provenance"] = {
                name: provenance
                for name, provenance in slab_level_provenance.items()
                if any(
                    row.get("nome") == name
                    for bucket in (tables.get("faces") or {}).values()
                    for row in bucket.get("lajes") or []
                )
            }
        path = out_dir / f"{pillar['name']}.json"
        _write_json(path, tables)
        hashes[pillar["name"]] = _sha256(path)
        incoherent[pillar["name"]] = len(tables["face_slab_beam_violations"])
    return {
        "schema": "arete.qa_pil_db_semantic_export/v1",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "db_path": str(db_path.resolve()),
        "db_sha256": _sha256(db_path),
        "project_id": project_id,
        "obra": obra,
        "pav": pav,
        "topology_source": "recomputed" if recompute_topology else "database",
        "item_count": len(pillars),
        "items": hashes,
        "face_slab_beam_violation_counts": {
            item: count for item, count in sorted(incoherent.items()) if count
        },
        "face_slab_beam_violation_total": sum(incoherent.values()),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--pack", required=True)
    build.add_argument("--out", required=True)
    compare = sub.add_parser("compare")
    compare.add_argument("--corpus", required=True)
    compare.add_argument("--actual-dir", required=True)
    compare.add_argument("--out", required=True)
    export_db = sub.add_parser("export-db")
    export_db.add_argument("--db", required=True)
    export_db.add_argument("--project-id", required=True)
    export_db.add_argument("--obra", required=True)
    export_db.add_argument("--pav", required=True)
    export_db.add_argument("--out-dir", required=True)
    export_db.add_argument("--manifest", required=True)
    export_db.add_argument(
        "--db-topology", action="store_true",
        help=(
            "Usa o face_beams gravado no banco em vez de recalcular. Mede a "
            "rodada que povoou o banco, não o motor atual."
        ),
    )
    args = parser.parse_args(argv)
    if args.command == "build":
        payload = build_corpus(Path(args.pack))
        _write_json(Path(args.out), payload)
    elif args.command == "compare":
        corpus = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
        payload = compare_corpus(corpus, Path(args.actual_dir))
        _write_json(Path(args.out), payload)
    else:
        payload = export_db_semantics(
            Path(args.db), args.project_id, args.obra, args.pav, Path(args.out_dir),
            recompute_topology=not args.db_topology,
        )
        _write_json(Path(args.manifest), payload)
    print(json.dumps({key: payload.get(key) for key in ("schema", "gate", "status", "item_count", "passed", "failed") if payload.get(key) is not None}, ensure_ascii=False))
    gate = payload.get("gate", payload.get("status"))
    return 0 if gate in (None, "PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
