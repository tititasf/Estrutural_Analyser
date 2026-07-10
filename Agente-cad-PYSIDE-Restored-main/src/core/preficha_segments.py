"""Contrato puro entre os segmentos produzidos pelo SA e a pre-ficha.

Este modulo nao depende de Qt. A UI apenas apresenta as entradas retornadas por
``collect_preficha_segments`` e devolve decisoes para
``apply_preficha_segment_decisions``. Assim, a geometria exibida e a mesma
referencia que permanece no objeto de viga depois da confirmacao.
"""

from __future__ import annotations

import copy
import math
import re
from typing import Any, Iterable


SEGMENT_TAB_SPECS: dict[str, dict[str, str]] = {
    "fundo": {
        "title": "Segmentos Fundos",
        "side": "Fundo",
        "behavior": "Fundo",
        "slot": "contour",
    },
    "lateral_a_para": {
        "title": "Segmentos Lateral A Para",
        "side": "A",
        "behavior": "Para",
        "slot": "seg_side_a",
    },
    "lateral_b_para": {
        "title": "Segmentos Lateral B Para",
        "side": "B",
        "behavior": "Para",
        "slot": "seg_side_b",
    },
    "lateral_a_passa": {
        "title": "Segmentos Lateral A Passa",
        "side": "A",
        "behavior": "Passa",
        "slot": "seg_side_a",
    },
    "lateral_b_passa": {
        "title": "Segmentos Lateral B Passa",
        "side": "B",
        "behavior": "Passa",
        "slot": "seg_side_b",
    },
}

_FUNDO_RE = re.compile(r"^viga_fundo_seg_(\d+)_area_segs$")
_LATERAL_RE = re.compile(
    r"^viga_([ab])_seg_(\d+)_(comprimento_total|comp_total_passa)$"
)
_DIMENSION_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _polyline_length(points: Iterable[Any]) -> float:
    clean: list[tuple[float, float]] = []
    for point in points or []:
        try:
            clean.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return sum(
        math.hypot(x2 - x1, y2 - y1)
        for (x1, y1), (x2, y2) in zip(clean, clean[1:])
    )


def _bbox_dimensions(points: Iterable[Any]) -> tuple[float, float]:
    """Retorna (comprimento, largura) pelo envelope do contorno.

    Para fundo de viga, comprimento não é perímetro nem soma de segmentos:
    é o maior eixo do contorno; largura é o menor eixo.
    """
    clean = _clean_points(points)
    if not clean:
        return 0.0, 0.0
    xs = [point[0] for point in clean]
    ys = [point[1] for point in clean]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    return max(dx, dy), min(dx, dy)


def _format_measure(value: float) -> str:
    if abs(value - round(value)) <= 1e-9:
        return str(int(round(value)))
    return str(round(value, 2))


def _clean_points(points: Iterable[Any]) -> list[tuple[float, float]]:
    clean: list[tuple[float, float]] = []
    for point in points or []:
        try:
            clean.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return clean


def _same_geometry(first: Iterable[Any], second: Iterable[Any], tolerance: float = 0.5) -> bool:
    a = _clean_points(first)
    b = _clean_points(second)
    if len(a) < 2 or len(b) < 2:
        return False

    def signature(points: list[tuple[float, float]]) -> tuple:
        endpoints = sorted((points[0], points[-1]))
        return tuple(round(value / tolerance) for point in endpoints for value in point)

    return signature(a) == signature(b)


def _lateral_edges_from_contour(points: Iterable[Any]) -> dict[str, list[tuple[float, float]]]:
    """Extrai as duas bordas longitudinais opostas de um contorno de fundo."""
    clean = _clean_points(points)
    if len(clean) < 3:
        return {}
    xs = [point[0] for point in clean]
    ys = [point[1] for point in clean]
    horizontal = (max(xs) - min(xs)) >= (max(ys) - min(ys))
    if horizontal:
        start, end = min(xs), max(xs)
        return {
            "a": [(start, max(ys)), (end, max(ys))],
            "b": [(start, min(ys)), (end, min(ys))],
        }
    start, end = min(ys), max(ys)
    return {
        "a": [(min(xs), start), (min(xs), end)],
        "b": [(max(xs), start), (max(xs), end)],
    }


def harmonize_lateral_segment_links(beams: list[dict] | None) -> int:
    """Repara fallbacks antigos que colocavam A e B sobre a mesma linha de fundo.

    A alteracao e feita nos proprios objetos de link. Assim, a geometria exibida
    na pre-ficha continua sendo exatamente a geometria consumida depois dela.
    Links A/B ja distintos, inclusive os editados manualmente, nao sao alterados.
    """
    repaired = 0

    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        links = beam.get("links") or {}
        if not isinstance(links, dict):
            continue
        for fundo_key, fundo_slots in list(links.items()):
            match = _FUNDO_RE.match(str(fundo_key))
            if not match or not isinstance(fundo_slots, dict):
                continue
            segment_index = int(match.group(1))
            contours = fundo_slots.get("contour") or []
            if not contours or not isinstance(contours[0], dict):
                continue
            edges = _lateral_edges_from_contour(contours[0].get("points") or [])
            if not edges:
                continue

            for suffix in ("comprimento_total", "comp_total_passa"):
                key_a = f"viga_a_seg_{segment_index}_{suffix}"
                key_b = f"viga_b_seg_{segment_index}_{suffix}"
                values_a = (links.get(key_a) or {}).get("seg_side_a") or []
                values_b = (links.get(key_b) or {}).get("seg_side_b") or []
                geometry_a = values_a[0].get("points") if values_a and isinstance(values_a[0], dict) else []
                geometry_b = values_b[0].get("points") if values_b and isinstance(values_b[0], dict) else []
                same_geometry = bool(geometry_a and geometry_b and _same_geometry(geometry_a, geometry_b))
                repair_a = same_geometry or (
                    not geometry_a and preficha_source_status(beam, key_a) != "ignore"
                )
                repair_b = same_geometry or (
                    not geometry_b and preficha_source_status(beam, key_b) != "ignore"
                )
                if not repair_a and not repair_b:
                    continue

                for side, key, slot, tag, current, should_repair in (
                    ("a", key_a, "seg_side_a", "Lado A", values_a, repair_a),
                    ("b", key_b, "seg_side_b", "Lado B", values_b, repair_b),
                ):
                    if not should_repair:
                        continue
                    points_side = edges[side]
                    if current and isinstance(current[0], dict):
                        link = current[0]
                    else:
                        links.setdefault(key, {}).setdefault(slot, [])
                        link = {"type": "poly"}
                        links[key][slot].append(link)
                    link.update({
                        "points": points_side,
                        "len": round(_polyline_length(points_side), 4),
                        "tag": tag,
                        "geometry_role": "lateral",
                        "geometry_source": "fundo_edge_fallback",
                    })
                    repaired += 1
    return repaired


def preficha_source_status(beam: dict, source_key: str) -> str:
    """Retorna a decisão da geometria atual, ignorando históricos de outro ID.

    Em análises incrementais um objeto pode carregar decisões antigas de uma
    viga homônima. O prefixo do UID impede que esse histórico afete o vínculo
    pertencente à instância atual.
    """
    parsed = _kind_for_link(str(source_key))
    if not parsed:
        return ""
    kind, segment_index, _ = parsed
    beam_identity = str(beam.get("id") or beam.get("name") or "")
    uid_prefix = f"{kind}|{beam_identity}|{segment_index}|"
    stored = beam.get("preficha_segmentos") or {}
    statuses = [
        str(decision.get("status") or "")
        for uid, decision in stored.items()
        if str(uid).startswith(uid_prefix)
        and isinstance(decision, dict)
        and decision.get("source_key") == source_key
    ]
    if "ignore" in statuses:
        return "ignore"
    if "valid" in statuses:
        return "valid"
    return ""


def preficha_geometry_policy(beam: dict, source_key: str) -> str:
    """Política para motores posteriores: ignore, preserve ou infer."""
    status = preficha_source_status(beam, source_key)
    if status == "ignore":
        return "ignore"
    if status == "valid":
        return "preserve"
    return "infer"


def _reviewed_fundo_topology(beam: dict) -> tuple[bool, list[str]]:
    """Retorna se houve validação humana real e os contornos autoritativos.

    ``preficha_segmentos``/``preficha_reviewed`` são somente triagem anterior à
    análise e não congelam geometria. A autoridade vem do selo do item, de campo,
    de slot ou do próprio link validado no card.
    """
    validated = False
    source_keys: set[str] = set()
    links = beam.get("links") or {}
    classified = (beam.get("geometry") or {}).get("classified") or {}
    is_horizontal = bool(beam.get("fv_is_h", beam.get("is_h", True)))
    axis = 0 if is_horizontal else 1
    current_spans = []
    for span in (
        classified.get("merged_bottom_groups_coords")
        or [
            coord
            for run in classified.get("bottom_runs") or []
            for coord in (run.get("coords") or [])
        ]
        or []
    ):
        try:
            start, end = sorted((float(span[0]), float(span[1])))
        except (TypeError, ValueError, IndexError):
            continue
        if end - start > 0.05:
            current_spans.append((start, end))

    def _contour_overlaps_current_span(source_key: str) -> bool:
        if not current_spans:
            return True
        slots = links.get(source_key) or {}
        contours = slots.get("contour") if isinstance(slots, dict) else []
        for contour in contours or []:
            if not isinstance(contour, dict):
                continue
            values = []
            for point in contour.get("points") or []:
                try:
                    values.append(float(point[axis]))
                except (TypeError, ValueError, IndexError):
                    continue
            if not values:
                continue
            c_min, c_max = min(values), max(values)
            c_len = c_max - c_min
            if c_len <= 0.05:
                continue
            for s_min, s_max in current_spans:
                overlap = min(c_max, s_max) - max(c_min, s_min)
                if overlap >= max(1.0, min(c_len, s_max - s_min) * 0.20):
                    return True
        return False

    def _has_authoritative_contour(source_key: str) -> bool:
        slots = links.get(source_key) or {}
        if not isinstance(slots, dict) or not _contour_overlaps_current_span(source_key):
            return False
        # Um contorno automático acompanha toda reanálise. Ele não pode, por si
        # só, transformar uma validação de dimensão/apoio em validação da
        # topologia: isso congelaria a viga com o número antigo de segmentos.
        # A geometria só é autoritativa aqui quando o próprio vínculo de área
        # foi validado pelo humano. A validação explícita do campo
        # ``*_area_segs`` continua sendo tratada logo abaixo pelos callers.
        return any(
            isinstance(contour, dict) and bool(contour.get("validated"))
            for contour in slots.get("contour") or []
        )

    if beam.get("is_validated"):
        validated = True
        source_keys.update(
            str(key)
            for key, slots in links.items()
            if _FUNDO_RE.match(str(key))
            and isinstance(slots, dict)
            and bool(slots.get("contour"))
        )

    for key, slots in links.items():
        source_key = str(key)
        if not _FUNDO_RE.match(source_key) or not isinstance(slots, dict):
            continue
        for link in slots.get("contour") or []:
            if not isinstance(link, dict):
                continue
            if link.get("validated"):
                validated = True
                source_keys.add(source_key)

    for field in beam.get("validated_fields") or []:
        field_name = str(field)
        match = re.match(r"^viga_fundo_seg_(\d+)_", field_name)
        if match:
            area_key = f"viga_fundo_seg_{match.group(1)}_area_segs"
            # Campos auxiliares (dim/local_ini/local_fim) validam aquele valor,
            # mas não congelam a topologia se a área ainda não existe. Isso
            # permite a reanálise preencher geometria ausente sem sobrescrever
            # o que o humano já validou. A topologia só trava quando há contorno
            # autoritativo ou o próprio campo de área foi validado.
            if field_name == area_key or _has_authoritative_contour(area_key):
                validated = True
                source_keys.add(area_key)

    validated_links = beam.get("validated_link_classes") or {}
    if isinstance(validated_links, dict):
        for field, slots in validated_links.items():
            field_name = str(field)
            match = re.match(r"^viga_fundo_seg_(\d+)_", field_name)
            if match and slots:
                area_key = f"viga_fundo_seg_{match.group(1)}_area_segs"
                if field_name == area_key or _has_authoritative_contour(area_key):
                    validated = True
                    source_keys.add(area_key)

    return validated, sorted(source_keys)


def fundo_topology_is_locked(beam: dict) -> bool:
    """Uma revisão humana FV fecha a topologia inteira daquela viga."""
    if beam.get("preficha_fundo_locked"):
        source_keys = [
            str(key)
            for key in beam.get("preficha_fundo_locked_source_keys") or []
            if _FUNDO_RE.match(str(key))
        ]
        if not source_keys:
            # Lock zero segmentos: caso explicito apos o humano ignorar todos
            # os fundos e validar o item. Deve continuar congelando vazio.
            return True
        expected_count = 0
        for candidate in (
            beam.get("seg_c"),
            (beam.get("fields") or {}).get("viga_count_c")
            if isinstance(beam.get("fields"), dict)
            else None,
        ):
            try:
                expected_count = max(expected_count, int(candidate or 0))
            except (TypeError, ValueError):
                continue
        if expected_count > len(source_keys):
            # Estado contaminado: a viga declara mais segmentos do que o lock
            # antigo preserva. Nao congelar topologia parcial.
            return False
        preficha_valid_sources = {
            str(decision.get("source_key") or "")
            for uid, decision in (beam.get("preficha_segmentos") or {}).items()
            if str(uid).startswith("fundo|")
            and isinstance(decision, dict)
            and str(decision.get("status") or "").casefold() == "valid"
            and _FUNDO_RE.match(str(decision.get("source_key") or ""))
        }
        if len(preficha_valid_sources) > len(source_keys):
            # Estado contaminado: o resumo granular sabe que existem mais
            # segmentos humanos válidos do que o lock antigo preserva. Não
            # congelar em subconjunto; deixar a análise reconstruir a topologia.
            return False
        links = beam.get("links") or {}
        classified = (beam.get("geometry") or {}).get("classified") or {}
        is_horizontal = bool(beam.get("fv_is_h", beam.get("is_h", True)))
        axis = 0 if is_horizontal else 1
        current_spans = []
        for span in (
            classified.get("merged_bottom_groups_coords")
            or [
                coord
                for run in classified.get("bottom_runs") or []
                for coord in (run.get("coords") or [])
            ]
            or []
        ):
            try:
                start, end = sorted((float(span[0]), float(span[1])))
            except (TypeError, ValueError, IndexError):
                continue
            if end - start > 0.05:
                current_spans.append((start, end))

        def _locked_contour_overlaps_current_span(source_key: str) -> bool:
            if not current_spans:
                return True
            slots = links.get(source_key) or {}
            contours = slots.get("contour") if isinstance(slots, dict) else []
            for contour in contours or []:
                if not isinstance(contour, dict):
                    continue
                values = []
                for point in contour.get("points") or []:
                    try:
                        values.append(float(point[axis]))
                    except (TypeError, ValueError, IndexError):
                        continue
                if not values:
                    continue
                c_min, c_max = min(values), max(values)
                c_len = c_max - c_min
                if c_len <= 0.05:
                    continue
                for s_min, s_max in current_spans:
                    overlap = min(c_max, s_max) - max(c_min, s_min)
                    if overlap >= max(1.0, min(c_len, s_max - s_min) * 0.20):
                        return True
            return False

        has_authoritative_contour = any(
            isinstance(links.get(source_key), dict)
            and bool((links.get(source_key) or {}).get("contour"))
            and _locked_contour_overlaps_current_span(source_key)
            for source_key in source_keys
        )
        if has_authoritative_contour:
            return True
        # Historico contaminado: lock aponta para area_segs, mas o contorno
        # salvo esta vazio/ausente. Nao congelar a topologia, pois isso impede
        # o motor de preencher a geometria faltante sem proteger dado humano.
        return False
    validated, _ = _reviewed_fundo_topology(beam)
    return validated


def lock_fundo_topology(beam: dict) -> None:
    """Registra o conjunto completo de segmentos FV aprovado pelo humano."""
    _, source_keys = _reviewed_fundo_topology(beam)
    allowed = set(source_keys)
    links = beam.get("links") or {}
    for key in list(links):
        source_match = re.match(r"^(viga_fundo_seg_\d+)_", str(key))
        if not source_match:
            continue
        area_key = f"{source_match.group(1)}_area_segs"
        if area_key not in allowed:
            links.pop(key, None)

    authoritative_contours = []
    for source_key in source_keys:
        authoritative_contours.extend(
            (links.get(source_key) or {}).get("contour") or []
        )
    links.setdefault("viga_segs", {})["seg_bottom"] = authoritative_contours

    for container in (beam, beam.get("fields") or {}):
        for key in list(container):
            source_match = re.match(r"^(viga_fundo_seg_\d+)_", str(key))
            if not source_match:
                continue
            area_key = f"{source_match.group(1)}_area_segs"
            if area_key not in allowed:
                container.pop(key, None)

    beam["preficha_fundo_locked"] = True
    beam["preficha_fundo_locked_version"] = 2
    beam["preficha_fundo_locked_source_keys"] = source_keys


def restore_locked_fundo_topology(target: dict, validated: dict) -> bool:
    """Substitui qualquer FV recém-inferido pelo conjunto humano preservado."""
    if not fundo_topology_is_locked(validated):
        return False

    target_links = target.setdefault("links", {})
    validated_links = validated.get("links") or {}
    if int(validated.get("preficha_fundo_locked_version") or 0) >= 2:
        source_keys = {
            str(key)
            for key in validated.get("preficha_fundo_locked_source_keys") or []
            if _FUNDO_RE.match(str(key))
        }
    else:
        _, reviewed_source_keys = _reviewed_fundo_topology(validated)
        source_keys = set(reviewed_source_keys)

    target_classified = (target.get("geometry") or {}).get("classified") or {}
    target_expected = max(
        len(target_classified.get("merged_bottom_groups_coords") or []),
        len(target_classified.get("merged_bottom_lengths") or []),
        len(
            [
                coord
                for run in target_classified.get("bottom_runs") or []
                for coord in (run.get("coords") or [])
            ]
        ),
    )
    if target_expected > len(source_keys):
        # O desenho atual detecta mais segmentos do que o lock preserva. Isso
        # indica lock parcial/stale; nao substituir a topologia recem-inferida.
        return False

    for key in list(target_links):
        if _FUNDO_RE.match(str(key)) or str(key).startswith("viga_fundo_seg_"):
            target_links.pop(key, None)
    for key, value in validated_links.items():
        source_match = re.match(r"^(viga_fundo_seg_\d+)_", str(key))
        area_key = (
            f"{source_match.group(1)}_area_segs" if source_match else ""
        )
        if area_key in source_keys:
            target_links[key] = copy.deepcopy(value)

    # A geometria bruta pode conter segmentos acrescentados depois da revisão.
    # O consumidor FV bloqueado usa somente os contornos autoritativos acima.
    target_links.setdefault("viga_segs", {})["seg_bottom"] = []

    for key in list(target):
        if str(key).startswith("viga_fundo_seg_"):
            target.pop(key, None)
    for key, value in validated.items():
        source_match = re.match(r"^(viga_fundo_seg_\d+)_", str(key))
        area_key = (
            f"{source_match.group(1)}_area_segs" if source_match else ""
        )
        if area_key in source_keys:
            target[key] = copy.deepcopy(value)

    target_fields = target.setdefault("fields", {})
    validated_fields = validated.get("fields") or {}
    for key in list(target_fields):
        if str(key).startswith("viga_fundo_seg_"):
            target_fields.pop(key, None)
    for key, value in validated_fields.items():
        source_match = re.match(r"^(viga_fundo_seg_\d+)_", str(key))
        area_key = (
            f"{source_match.group(1)}_area_segs" if source_match else ""
        )
        if area_key in source_keys:
            target_fields[key] = copy.deepcopy(value)

    for key in (
        "preficha_fundo_locked",
        "preficha_fundo_locked_version",
        "preficha_fundo_locked_source_keys",
        "preficha_segmentos",
        "seg_c",
        "seg_bottom",
    ):
        if key in validated:
            target[key] = copy.deepcopy(validated[key])
    if "comprimento_total_fundo" in validated_fields:
        target_fields["comprimento_total_fundo"] = copy.deepcopy(
            validated_fields["comprimento_total_fundo"]
        )
    target["preficha_fundo_locked"] = True
    target["preficha_fundo_locked_version"] = 2
    target["preficha_fundo_locked_source_keys"] = sorted(source_keys)
    return True


def _first_value(beam: dict, *keys: str) -> Any:
    fields = beam.get("fields") or {}
    for key in keys:
        for source in (beam, fields):
            value = source.get(key) if isinstance(source, dict) else None
            if value not in (None, "", [], {}):
                return value
    return ""


def _text_from_entity(entity: Any) -> str:
    if isinstance(entity, str):
        return entity.strip()
    if not isinstance(entity, dict):
        return ""
    fields = entity.get("fields") or {}
    for key in ("text", "name", "nome", "label", "id"):
        value = entity.get(key)
        if value not in (None, ""):
            return str(value).strip()
        value = fields.get(key) if isinstance(fields, dict) else None
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _dimension_height(value: Any) -> str:
    numbers = []
    for raw in _DIMENSION_RE.findall(str(value or "")):
        try:
            numbers.append(float(raw.replace(",", ".")))
        except ValueError:
            continue
    if not numbers:
        return ""
    height = max(numbers) if len(numbers) > 1 else numbers[0]
    return f"{height:g}"


def _structural_name(value: Any) -> str:
    match = re.search(r"\b([PV]\s*\d+[A-Z]?)\b", str(value or ""), re.IGNORECASE)
    return re.sub(r"\s+", "", match.group(1)).upper() if match else str(value or "").strip()


def _support_metadata(
    name: str,
    beam_lookup: dict[str, dict],
    pillar_report: dict | None,
    nivel_report: dict | None,
) -> tuple[str, str]:
    identity = _structural_name(name)
    if identity.startswith("P"):
        pillar = (pillar_report or {}).get(identity) or {}
        points = _clean_points(pillar.get("points") or []) if isinstance(pillar, dict) else []
        dimension = ""
        if points:
            width = max(point[0] for point in points) - min(point[0] for point in points)
            height = max(point[1] for point in points) - min(point[1] for point in points)
            dimension = f"{min(width, height):g}x{max(width, height):g}"
        nr_entry = ((nivel_report or {}).get("pilares") or {}).get(identity) or {}
        level = (
            nr_entry.get("level_str") or nr_entry.get("nivel_str")
            or nr_entry.get("level") or pillar.get("nivel_str") or ""
        )
        return dimension, str(level or "")

    beam_identity = re.sub(r"(?<=\d)[AB]$", "", identity) if identity.startswith("V") else identity
    support_beam = beam_lookup.get(identity) or beam_lookup.get(beam_identity) or {}
    if support_beam:
        fields = support_beam.get("fields") or {}
        dimension = fields.get("dimensao") or support_beam.get("dimensao") or ""
        if not dimension:
            contours = ((support_beam.get("links") or {}).get("viga_fundo_seg_1_area_segs") or {}).get("contour") or []
            ficha = contours[0].get("ficha") if contours and isinstance(contours[0], dict) else {}
            if ficha:
                width = ficha.get("largura_total_fundo") or ""
                height = ficha.get("altura_total") or ""
                dimension = f"{width}x{height}" if width and height else width or height
        level = fields.get("nivel_lado_a") or fields.get("nivel_viga") or ""
        return str(dimension or ""), str(level or "")
    return "", ""


def _support_info(
    beam: dict,
    prefix: str,
    which: str,
    beam_lookup: dict[str, dict],
    pillar_report: dict | None,
    nivel_report: dict | None,
) -> dict[str, str]:
    short = "ini" if which == "inicio" else "end"
    alt = "inicial" if which == "inicio" else "final"
    match = re.search(r"_seg_(\d+)$", prefix)
    segment_index = int(match.group(1)) if match else 1
    name = _first_value(
        beam,
        f"{prefix}_{short}_name",
        f"{prefix}_apoio_{alt}",
        f"{prefix}_local_{'ini' if which == 'inicio' else 'fim'}",
        f"viga_fundo_seg_{segment_index}_local_{'ini' if which == 'inicio' else 'fim'}",
    )
    support_values = ((beam.get("links") or {}).get("apoios") or {}).get(which) or []
    support = support_values[0] if support_values and isinstance(support_values[0], dict) else {}
    name = name or _text_from_entity(support)
    dimension = _first_value(
        beam,
        f"{prefix}_{short}_dim",
        f"{prefix}_apoio_{alt}_dim",
    ) or support.get("dimension") or support.get("dimensao") or ""
    level = _first_value(
        beam,
        f"{prefix}_{short}_nivel",
        f"{prefix}_apoio_{alt}_nivel",
    ) or support.get("level") or support.get("nivel") or ""
    inferred_dimension, inferred_level = _support_metadata(
        str(name or ""), beam_lookup, pillar_report, nivel_report
    )
    dimension = dimension or inferred_dimension
    level = level or inferred_level
    return {"name": str(name or ""), "dimension": str(dimension or ""), "level": str(level or "")}


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def _slab_info(slab: dict) -> dict[str, str]:
    fields = slab.get("fields") or {}
    name = slab.get("name") or slab.get("laje_name") or fields.get("nome") or ""
    height_raw = (
        fields.get("laje_dim") or slab.get("laje_dim") or slab.get("height")
        or slab.get("altura") or ""
    )
    level = fields.get("laje_nivel") or slab.get("laje_nivel") or slab.get("nivel") or ""
    return {
        "name": str(name),
        "level": str(level),
        "height": _dimension_height(height_raw),
    }


def _touching_slabs(points: list, side: str, slabs: list[dict] | None) -> list[dict[str, str]]:
    line = _clean_points(points)
    if len(line) < 2:
        return []
    first, last = line[0], line[-1]
    horizontal = abs(last[0] - first[0]) >= abs(last[1] - first[1])
    if horizontal:
        normal = (0.0, 1.0 if side == "A" else -1.0)
    else:
        normal = (-1.0 if side == "A" else 1.0, 0.0)
    line_midpoint = ((first[0] + last[0]) / 2.0, (first[1] + last[1]) / 2.0)
    ranked: list[tuple[int, dict[str, str]]] = []
    for slab in slabs or []:
        if not isinstance(slab, dict):
            continue
        polygon = _clean_points(slab.get("points") or [])
        if len(polygon) < 3:
            continue
        slab_center = (
            sum(point[0] for point in polygon) / len(polygon),
            sum(point[1] for point in polygon) / len(polygon),
        )
        # Uma laje que engloba geometricamente a faixa da viga ainda pertence
        # apenas ao lado onde esta o seu centro. Isso evita repetir a mesma laje
        # nos lados A e B por causa de contornos SA ligeiramente sobrepostos.
        if horizontal:
            on_requested_side = (
                slab_center[1] >= line_midpoint[1]
                if side == "A"
                else slab_center[1] <= line_midpoint[1]
            )
        else:
            on_requested_side = (
                slab_center[0] <= line_midpoint[0]
                if side == "A"
                else slab_center[0] >= line_midpoint[0]
            )
        if not on_requested_side:
            continue
        score = 0
        for ratio in (0.15, 0.5, 0.85):
            base = (
                first[0] + (last[0] - first[0]) * ratio,
                first[1] + (last[1] - first[1]) * ratio,
            )
            if any(_point_in_polygon(
                (base[0] + normal[0] * offset, base[1] + normal[1] * offset), polygon
            ) for offset in (2.0, 8.0, 16.0, 30.0)):
                score += 1
        if score:
            ranked.append((score, _slab_info(slab)))
    ranked.sort(key=lambda item: (-item[0], _natural_key(item[1]["name"])))
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, info in ranked:
        key = info["name"].casefold()
        if key and key not in seen:
            seen.add(key)
            unique.append(info)
        if len(unique) == 3:
            break
    return unique


def _linked_side_slabs(beam: dict, side: str) -> list[dict[str, str]]:
    values = ((beam.get("links") or {}).get("lajes") or {}).get(f"lado_{side.lower()}") or []
    result: list[dict[str, str]] = []
    for value in values:
        if isinstance(value, dict):
            result.append(_slab_info(value))
    return result[:3]


def _opening_names(beam: dict, prefix: str, entity_type: str) -> list[str]:
    links = beam.get("links") or {}
    names: list[str] = []
    global_values = ((links.get("aberturas") or {}).get(entity_type) or [])
    for value in global_values:
        text = _text_from_entity(value)
        if text:
            names.append(text)
    marker = f"{prefix}_abert_{entity_type}_"
    for key, slots in links.items():
        if not str(key).startswith(marker) or not isinstance(slots, dict):
            continue
        label_values = slots.get("arr_label") or slots.get("label") or []
        dimension_values = slots.get("arr_dim") or []
        label = next((_text_from_entity(value) for value in label_values if _text_from_entity(value)), "")
        dimension = next(
            (_text_from_entity(value) for value in dimension_values if _text_from_entity(value)), ""
        )
        if label:
            names.append(f"{label} ({dimension})" if dimension else label)
            continue
        for values in slots.values():
            text = next((_text_from_entity(value) for value in values or [] if _text_from_entity(value)), "")
            if text:
                names.append(text)
    return list(dict.fromkeys(names))


def _kind_for_link(link_key: str) -> tuple[str, int, str] | None:
    fundo_match = _FUNDO_RE.match(link_key)
    if fundo_match:
        return "fundo", int(fundo_match.group(1)), "contour"

    lateral_match = _LATERAL_RE.match(link_key)
    if not lateral_match:
        return None
    side, segment_index, suffix = lateral_match.groups()
    behavior = "para" if suffix == "comprimento_total" else "passa"
    return f"lateral_{side}_{behavior}", int(segment_index), f"seg_side_{side}"


def collect_preficha_segments(
    beams: list[dict] | None,
    slabs: list[dict] | None = None,
    pillar_report: dict | None = None,
    nivel_report: dict | None = None,
) -> dict[str, list[dict]]:
    """Normaliza os links SA nas cinco listas de segmentos da pre-ficha.

    Cada entrada conserva referencias internas para a viga e para o link. Essas
    referencias nao devem ser serializadas; elas garantem que aplicar uma decisao
    altere exatamente o objeto que foi exibido.
    """
    harmonize_lateral_segment_links(beams)
    result = {kind: [] for kind in SEGMENT_TAB_SPECS}
    beam_lookup: dict[str, dict] = {}
    for support_beam in beams or []:
        if not isinstance(support_beam, dict):
            continue
        for raw_name in (support_beam.get("name"), support_beam.get("parent_name")):
            identity = _structural_name(raw_name)
            if identity:
                beam_lookup.setdefault(identity, support_beam)
    for beam_index, beam in enumerate(beams or []):
        if not isinstance(beam, dict):
            continue
        beam_name = str(beam.get("parent_name") or beam.get("name") or f"Viga {beam_index + 1}")
        beam_identity = str(beam.get("id") or beam.get("name") or f"beam-{beam_index + 1}")
        stored = beam.get("preficha_segmentos") or {}
        links = beam.get("links") or {}
        if not isinstance(links, dict):
            continue
        lv_dimension_override = next(
            (
                str(link.get("lv_dimensao"))
                for slots in links.values()
                if isinstance(slots, dict)
                for values in slots.values()
                if isinstance(values, list)
                for link in values
                if isinstance(link, dict) and link.get("lv_dimensao")
            ),
            "",
        )

        for link_key, slots in links.items():
            parsed = _kind_for_link(str(link_key))
            if not parsed or not isinstance(slots, dict):
                continue
            kind, segment_index, slot = parsed
            raw_entries = slots.get(slot) or []
            if not isinstance(raw_entries, list):
                continue
            spec = SEGMENT_TAB_SPECS[kind]
            for occurrence, link in enumerate(raw_entries, start=1):
                if not isinstance(link, dict):
                    continue
                points = link.get("points") or []
                uid = f"{kind}|{beam_identity}|{segment_index}|{occurrence}"
                previous = stored.get(uid) if isinstance(stored, dict) else {}
                if kind == "fundo":
                    length, envelope_width = _bbox_dimensions(points)
                    measure_length = link.get("fv_measure_length")
                    try:
                        measure_length = float(measure_length)
                    except (TypeError, ValueError):
                        measure_length = 0.0
                    measure_width = link.get("fv_measure_width")
                    try:
                        measure_width = float(measure_width)
                    except (TypeError, ValueError):
                        measure_width = 0.0
                    if measure_length > 0.05:
                        length = measure_length
                    special_measure = str(link.get("fv_measure_source") or "").startswith(
                        "special_diagonal"
                    )
                    measure_width_text = (
                        _format_measure(measure_width) if measure_width > 0.05 else ""
                    )
                    envelope_width_text = (
                        _format_measure(envelope_width) if envelope_width else ""
                    )
                else:
                    envelope_width = 0.0
                    envelope_width_text = ""
                    measure_width_text = ""
                    special_measure = False
                    length = link.get("len")
                    try:
                        length = float(length)
                    except (TypeError, ValueError):
                        length = _polyline_length(points)
                ficha = dict(link.get("ficha") or {})
                fields = beam.get("fields") or {}
                width = (
                    (
                        link.get("lv_dimensao")
                        if kind != "fundo"
                        else None
                    )
                    or (lv_dimension_override if kind != "fundo" else None)
                    or (measure_width_text if special_measure else None)
                    or (ficha.get("largura_total_fundo") if special_measure else None)
                    or (
                        fields.get(f"viga_fundo_seg_{segment_index}_largura")
                        if special_measure
                        else None
                    )
                    or (
                        fields.get(f"viga_fundo_seg_{segment_index}_dim")
                        if special_measure
                        else None
                    )
                    or envelope_width_text
                    or (ficha.get("largura_total_fundo") if kind == "fundo" else None)
                    or fields.get(f"viga_fundo_seg_{segment_index}_largura")
                    or fields.get(f"viga_fundo_seg_{segment_index}_dim")
                    or ""
                )
                side_key = spec["side"].lower()
                prefix = f"viga_{side_key}_seg_{segment_index}" if kind != "fundo" else ""
                height = ""
                details: dict[str, Any] = {}
                if kind != "fundo":
                    dimension_raw = _first_value(
                        beam,
                        f"{prefix}_h1",
                        f"{prefix}_dim",
                        "altura_h1",
                    )
                    height = _dimension_height(dimension_raw)
                    if not height:
                        fundo_slots = links.get(f"viga_fundo_seg_{segment_index}_area_segs") or {}
                        fundo_links = fundo_slots.get("contour") or []
                        fundo_ficha = fundo_links[0].get("ficha") if fundo_links and isinstance(fundo_links[0], dict) else {}
                        height = _dimension_height((fundo_ficha or {}).get("altura_total"))
                    linked_slabs = _linked_side_slabs(beam, spec["side"])
                    touching_slabs = linked_slabs or _touching_slabs(points, spec["side"], slabs)
                    adjustment_initial = _first_value(beam, f"{prefix}_ajuste_inicial")
                    adjustment_final = _first_value(beam, f"{prefix}_ajuste_final")
                    adjustment_total = _first_value(beam, f"{prefix}_ajuste_comprimento")
                    details = {
                        "support_start": _support_info(
                            beam, prefix, "inicio", beam_lookup, pillar_report, nivel_report
                        ),
                        "support_end": _support_info(
                            beam, prefix, "fim", beam_lookup, pillar_report, nivel_report
                        ),
                        "beam_level": str(_first_value(
                            beam, f"{prefix}_nivel_viga", f"nivel_lado_{side_key}"
                        ) or ""),
                        "slabs": touching_slabs[:3],
                        "continuity": str(_first_value(beam, f"{prefix}_continuidade") or ""),
                        "adjustment": {
                            "initial": str(adjustment_initial or ""),
                            "final": str(adjustment_final or ""),
                            "total": str(adjustment_total or ""),
                        },
                        "passing_pillars": _opening_names(beam, prefix, "pilar"),
                        "beam_openings": _opening_names(beam, prefix, "viga"),
                    }
                result[kind].append({
                    "uid": uid,
                    "kind": kind,
                    "beam_name": beam_name,
                    "beam_identity": beam_identity,
                    "segment_index": segment_index,
                    "occurrence": occurrence,
                    "segment_label": (
                        str(segment_index)
                        if len(raw_entries) == 1
                        else f"{segment_index}.{occurrence}"
                    ),
                    "side": spec["side"],
                    "behavior": spec["behavior"],
                    "length": round(length, 2),
                    "height": str(height),
                    "width": str(width),
                    "points": points,
                    "measure_source": str(link.get("fv_measure_source") or ""),
                    "tag": str(link.get("tag") or spec["side"]),
                    "ficha": ficha,
                    "details": details,
                    "status": str((previous or {}).get("status") or "valid"),
                    "attention": str((previous or {}).get("attention") or ""),
                    "source_key": str(link_key),
                    "source_slot": slot,
                    "_beam_ref": beam,
                    "_link_ref": link,
                })

    for entries in result.values():
        entries.sort(key=lambda item: (
            _natural_key(item["beam_name"]),
            item["segment_index"],
            item["occurrence"],
        ))
    return result


def apply_preficha_segment_decisions(
    beams: list[dict] | None,
    decisions: dict[str, dict] | None,
) -> dict[str, int]:
    """Persiste notas/status e remove links ignorados dos mesmos objetos SA."""
    decisions = decisions or {}
    collected = collect_preficha_segments(beams)
    entries = [entry for values in collected.values() for entry in values]
    removed = 0
    reviewed = 0

    # Remover por identidade em uma segunda passagem evita deslocamento de indices.
    removals: list[tuple[dict, str, dict]] = []
    for entry in entries:
        if entry["uid"] not in decisions:
            continue
        decision = decisions.get(entry["uid"], {})
        status = str(decision.get("status") or entry.get("status") or "valid")
        attention = str(decision.get("attention") or "").strip()
        beam = entry["_beam_ref"]
        beam.setdefault("preficha_segmentos", {})[entry["uid"]] = {
            "status": status,
            "attention": attention,
            "source_key": entry["source_key"],
            "saved_by": "preficha_sa",
        }
        link_ref = entry["_link_ref"]
        link_ref["preficha_reviewed"] = True
        link_ref["preficha_status"] = status
        link_ref["preficha_uid"] = entry["uid"]
        reviewed += 1
        if status == "ignore":
            removals.append((beam, entry["source_key"], link_ref))

    for beam, source_key, link_ref in removals:
        slots = (beam.get("links") or {}).get(source_key) or {}
        parsed = _kind_for_link(source_key)
        if not parsed:
            continue
        kind, segment_index, slot_name = parsed
        values = slots.get(slot_name) or []
        for index in range(len(values) - 1, -1, -1):
            if values[index] is link_ref:
                values.pop(index)
                removed += 1
                break
        if values:
            continue
        if kind == "fundo":
            beam[f"viga_fundo_seg_{segment_index}_exists"] = False
            continue
        side = SEGMENT_TAB_SPECS[kind]["side"].lower()
        related_keys = (
            f"viga_{side}_seg_{segment_index}_comprimento_total",
            f"viga_{side}_seg_{segment_index}_comp_total_passa",
        )
        has_related_link = any(
            any((beam.get("links") or {}).get(key, {}).get(f"seg_side_{side}") or [])
            for key in related_keys
        )
        if not has_related_link:
            beam[f"viga_{side}_seg_{segment_index}_exists"] = False

    return {"reviewed": reviewed, "removed": removed}


def serializable_segment(entry: dict) -> dict:
    """Remove referencias internas para logs, HTML e testes."""
    return {key: value for key, value in entry.items() if not key.startswith("_")}


def _natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]
