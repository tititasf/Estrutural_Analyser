"""Cotas consultivas das faces PIL no portal, sem modificar o snapshot N1."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from src.core.pillar_abcd_tables import span_dists_on_face


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value))
    if not match:
        return None
    try:
        number = float(match.group().replace(",", "."))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _values(rows, field):
    return {round(value, 4) for row in rows if (value := _number(row.get(field))) is not None}


def _bbox(points):
    if not points:
        return None
    try:
        return (min(float(p[0]) for p in points), min(float(p[1]) for p in points),
                max(float(p[0]) for p in points), max(float(p[1]) for p in points))
    except (TypeError, ValueError, IndexError):
        return None


def _touches_pillar(segment, pillar_bbox, tolerance=0.5):
    segment_bbox = _bbox(segment.get("points"))
    if pillar_bbox is None or segment_bbox is None:
        return False
    return (segment_bbox[0] <= pillar_bbox[2] + tolerance
            and segment_bbox[2] >= pillar_bbox[0] - tolerance
            and segment_bbox[1] <= pillar_bbox[3] + tolerance
            and segment_bbox[3] >= pillar_bbox[1] - tolerance)


def _dimension(value):
    match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*", str(value or ""))
    if not match:
        return None
    width, height = (float(part.replace(",", ".")) for part in match.groups())
    if not (0 < width <= 500 and 0 < height <= 500):
        return None
    return width, height


@lru_cache(maxsize=16)
def _dimension_texts_cached(db_path: str, mtime_ns: int, project_id: str) -> dict:
    del mtime_ns
    found = {}
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name,data_json FROM beams WHERE project_id=?", (project_id,))
        for name, data_json in rows:
            data = json.loads(data_json or "{}")
            found[name] = [entry for entry in data.get("dimension_texts") or []
                           if isinstance(entry, dict) and _dimension(entry.get("text"))]
    return found


def load_beam_dimension_texts(estado: dict) -> dict:
    """Texto de dimensão no DXF associado à viga, com posição para vínculo local."""
    path = Path(str(estado.get("db_path") or ""))
    if not path.is_file():
        return {}
    uid = next((str(s.get("uid") or "") for s in ((estado.get("segmentos") or {}).get("fundo") or [])
                if re.search(r"\|[a-f0-9-]{36}_b_", str(s.get("uid") or ""))), "")
    match = re.search(r"\|([a-f0-9-]{36})_b_", uid)
    if not match:
        return {}
    try:
        return _dimension_texts_cached(str(path), path.stat().st_mtime_ns, match.group(1))
    except (OSError, ValueError, sqlite3.Error, TypeError):
        return {}


def _distance_to_box(position, bbox):
    if not bbox or not position or len(position) < 2:
        return math.inf
    try:
        x, y = float(position[0]), float(position[1])
    except (TypeError, ValueError):
        return math.inf
    return math.hypot(max(bbox[0] - x, x - bbox[2], 0),
                      max(bbox[1] - y, y - bbox[3], 0))


def _fmt_dimension(width, height):
    def part(value):
        return f"{value:g}" if value is not None else "?"
    return f"{part(width)}/{part(height)}"


def _near_face(face, pillar_bbox, element_bbox, tolerance=0.6):
    if not pillar_bbox or not element_bbox:
        return False
    vertical = (pillar_bbox[3] - pillar_bbox[1]) >= (pillar_bbox[2] - pillar_bbox[0])
    if vertical:
        edge = pillar_bbox[0] if face == "A" else pillar_bbox[2] if face == "B" else pillar_bbox[3] if face == "C" else pillar_bbox[1]
        low, high = (element_bbox[0], element_bbox[2]) if face in "AB" else (element_bbox[1], element_bbox[3])
    else:
        edge = pillar_bbox[1] if face == "A" else pillar_bbox[3] if face == "B" else pillar_bbox[0] if face == "C" else pillar_bbox[2]
        low, high = (element_bbox[1], element_bbox[3]) if face in "AB" else (element_bbox[0], element_bbox[2])
    return low - tolerance <= edge <= high + tolerance


def _check_distance(row, role, face, pillar_bbox, element_bbox=None):
    if role == "passa":
        if row.get("dist_esq") not in (None, "", "—") or row.get("dist_dir") not in (None, "", "—"):
            row["dist_status"] = "conflict"
            row["dist_motivo"] = "Viga passante não usa d.esq/d.dir na convenção ABCD."
        return
    if not pillar_bbox:
        return
    vertical = (pillar_bbox[3] - pillar_bbox[1]) >= (pillar_bbox[2] - pillar_bbox[0])
    face_len = (pillar_bbox[3] - pillar_bbox[1]) if (face in "AB") == vertical else (pillar_bbox[2] - pillar_bbox[0])
    de, dd = _number(row.get("dist_esq")), _number(row.get("dist_dir"))
    if (de is None or dd is None) and element_bbox and _near_face(face, pillar_bbox, element_bbox):
        measured = span_dists_on_face(face, pillar_bbox, element_bbox, vertical=vertical)
        if measured[0] is not None and measured[1] is not None:
            row["dist_esq"] = f"{measured[0]:.2f}cm"
            row["dist_dir"] = f"{measured[1]:.2f}cm"
            de, dd = measured
            row["dist_status"] = "inferred"
            row["dist_motivo"] = "Distâncias medidas pelo contorno associado; conferir no DXF."
    if de is None or dd is None:
        row["dist_status"] = "missing"
        row["dist_motivo"] = "Distâncias da ocupação nesta face não identificadas."
    elif de < -0.5 or dd < -0.5 or de + dd > face_len + 0.6:
        row["dist_status"] = "conflict"
        row["dist_motivo"] = f"Distâncias incompatíveis com a face de {face_len:g}cm."
    elif element_bbox and _near_face(face, pillar_bbox, element_bbox):
        measured = span_dists_on_face(face, pillar_bbox, element_bbox, vertical=vertical)
        if measured[0] is not None and (abs(de - measured[0]) > 1.5 or abs(dd - measured[1]) > 1.5):
            row["dist_status"] = "conflict"
            row["dist_motivo"] = (f"Distâncias da tabela {de:g}/{dd:g}cm divergem do contorno "
                                   f"{measured[0]:.2f}/{measured[1]:.2f}cm; conferir no DXF.")


def load_preprocess_slab_levels(obra_dir: Path, pavimento: str) -> dict[str, set[float]]:
    """Lê somente o pacote fixado no último SA produtivo do pavimento."""
    root = obra_dir / "Fase-6_Execucao_CAD" / "production_sa" / pavimento
    manifests = sorted(root.glob("*/production_manifest.json"))
    if not manifests:
        return {}
    try:
        manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
        receipt = manifest.get("preprocess_context") or {}
        run_id = str(receipt.get("context_run_id") or "")
        if not re.fullmatch(r"[a-f0-9-]{36}", run_id):
            return {}
        run_dir = obra_dir / "preprocessamento" / "v1" / pavimento / "runs" / run_id
        floor = json.loads((run_dir / "floor.json").read_text(encoding="utf-8"))
        source_id = (receipt.get("scope") or {}).get("recorte_id")
        tower = (floor.get("towers") or {}).get(source_id) or {}
        path = (run_dir / str(tower.get("path") or "")).resolve()
        if not path.is_relative_to(run_dir.resolve()):
            return {}
        package = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, KeyError):
        return {}
    found: dict[str, set[float]] = defaultdict(set)
    for fact in package.get("levels") or []:
        if fact.get("field") != "slab_level" or fact.get("status") != "observed_text":
            continue
        value = _number(fact.get("value"))
        name = str(fact.get("display_name") or "").strip()
        if name and value is not None:
            found[name].add(round(value, 4))
    return dict(found)


def enrich_pillar_abcd_levels(tables: dict, estado: dict, arrival, preprocess_slabs=None,
                              pillar_name=None, beam_dim_texts=None) -> dict:
    """Cruza níveis N1 por nome; sem vínculo de segmento, usa chegada com alerta."""
    result = deepcopy(tables)
    fallback = _number(arrival)
    preprocess_slabs = preprocess_slabs or {}
    beam_dim_texts = beam_dim_texts or {}
    slabs: dict[str, list[dict]] = defaultdict(list)
    for row in estado.get("slabs") or []:
        name = str(row.get("name") or "").strip()
        if name:
            slabs[name].append(row)
    beams: dict[str, list[dict]] = defaultdict(list)
    for row in ((estado.get("segmentos") or {}).get("fundo") or []):
        name = str(row.get("beam_name") or "").strip()
        if name:
            beams[name].append(row)
    laterals: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for family, entries in (estado.get("segmentos") or {}).items():
        if not family.startswith("lateral_"):
            continue
        for segment in entries or []:
            name = str(segment.get("beam_name") or "").strip()
            if name:
                laterals[(name, str(segment.get("segment_label") or ""))].append(segment)
    cuts: dict[str, list[dict]] = defaultdict(list)
    for cut in estado.get("cortes") or []:
        name = str(cut.get("beam_name") or "").strip()
        if name:
            cuts[name].append(cut)
    slab_geometry = {str(s.get("name") or "").strip(): _bbox(s.get("points"))
                     for s in estado.get("slabs") or []}
    pillar = next((p for p in estado.get("pilares") or []
                   if p.get("name") == pillar_name or p.get("key") == pillar_name), None)
    pillar_bbox = _bbox(pillar.get("points")) if pillar else None
    for face_id, face in (result.get("faces") or {}).items():
        for role in ("lajes", "passa", "chega", "interior"):
            for row in face.get(role) or []:
                name = str(row.get("nome") or "").strip()
                if name in ("", "—", "nenhuma"):
                    continue
                if role == "lajes":
                    if not slabs[name]:
                        row["nome_status"] = "missing"
                        row["nome_motivo"] = "Nome da laje não encontrado nos itens SA deste pavimento."
                    elif pillar_bbox and slab_geometry.get(name) and not _near_face(face_id, pillar_bbox, slab_geometry[name]):
                        row["nome_status"] = "conflict"
                        row["nome_motivo"] = "Contorno da laje não confirma contato com esta face."
                    candidates = _values(slabs[name], "nivel")
                    if not candidates:
                        existing = _number(row.get("nivel"))
                        candidates = {round(existing, 4)} if existing is not None else set()
                    if len(candidates) == 1:
                        value = next(iter(candidates))
                        status, reason = "sa", "Cota da laje registrada no SA/N1."
                        crossing = preprocess_slabs.get(name) or set()
                        if crossing and (len(crossing) != 1 or abs(value - next(iter(crossing))) > 0.005):
                            status = "conflict"
                            reason = ("SA/N1 e pré-processamento divergem; conferir no DXF. "
                                      f"SA: {value:.2f}; pré-processamento: "
                                      + ", ".join(f"{v:.2f}" for v in sorted(crossing)) + ".")
                    else:
                        value = fallback
                        status = "ambiguous" if candidates else "fallback"
                        reason = ("Mais de uma cota para a mesma laje no SA/N1."
                                  if candidates else "Cota própria da laje não identificada.")
                    _check_distance(row, role, face_id, pillar_bbox, slab_geometry.get(name))
                else:
                    all_segments = beams[name]
                    segments = all_segments
                    touching = [segment for segment in segments
                                if _touches_pillar(segment, pillar_bbox)]
                    unlinked = bool(pillar_bbox and segments and not touching
                                    and any(_bbox(segment.get("points")) for segment in segments))
                    if not segments:
                        row["nome_status"] = "missing"
                        row["nome_motivo"] = "Nome da viga não encontrado nos fundos SA deste pavimento."
                    elif unlinked:
                        row["nome_status"] = "inferred"
                        row["nome_motivo"] = "Viga encontrada por nome, mas sem contato geométrico com este pilar."
                    if touching:
                        segments = touching
                    candidates = _values(segments, "level")
                    if len(candidates) == 1:
                        value = next(iter(candidates))
                        direct = all(str(s.get("level_source") or "") == "explicit_beam_or_side"
                                     and str(s.get("status") or "") == "valid" for s in segments)
                        status = "sa" if direct and not unlinked else "inferred"
                        reason = ("Não foi possível vincular geometricamente a viga a este pilar; "
                                  "cota da viga exibida com ressalva."
                                  if unlinked else "Cota explícita da viga no SA/N1."
                                  if direct else "Há segmentos com nível inferido de laje; conferir o vínculo no DXF.")
                    else:
                        value = fallback
                        status = "ambiguous" if candidates else "fallback"
                        reason = ("Segmentos desta viga têm cotas distintas ("
                                  + ", ".join(f"{v:.2f}" for v in sorted(candidates))
                                  + "); a face não identifica qual trecho."
                                  if candidates else "Cota própria da viga não identificada no SA/N1.")
                    _check_distance(row, role, face_id, pillar_bbox,
                                    _bbox(segments[0].get("points")) if len(segments) == 1 else None)
                    widths = {_number(s.get("width")) for s in segments}
                    widths.discard(None)
                    labels = {str(s.get("segment_label") or "") for s in segments}
                    lateral_rows = [s for label in labels for s in laterals[(name, label)]]
                    dimensions = {_dimension(s.get("width")) for s in lateral_rows}
                    dimensions.discard(None)
                    pillar_section = None
                    if pillar_bbox:
                        pillar_section = tuple(sorted((pillar_bbox[2] - pillar_bbox[0],
                                                       pillar_bbox[3] - pillar_bbox[1])))
                    nearby_text_dims = set()
                    for entry in beam_dim_texts.get(name) or []:
                        dimension = _dimension(entry.get("text"))
                        if not dimension or (pillar_section and all(
                            abs(a - b) <= 1.6 for a, b in zip(sorted(dimension), pillar_section)
                        )):
                            continue
                        if any(_distance_to_box(entry.get("pos"), _bbox(s.get("points"))) <= 40
                               for s in segments):
                            nearby_text_dims.add(dimension)
                    local_cuts = [cut for cut in cuts[name]
                                  if _touches_pillar({"points": cut.get("pts")}, pillar_bbox, tolerance=5.0)]
                    cut_heights = {_number(c.get("beam_h")) for c in local_cuts}
                    cut_heights.discard(None)
                    prior_dim = _dimension(row.get("dim"))
                    if len(dimensions) == 1:
                        width, height = next(iter(dimensions))
                        dim = _fmt_dimension(width, height)
                        reasons = []
                        if widths and (len(widths) != 1 or abs(next(iter(widths)) - width) > 0.6):
                            reasons.append("largura do fundo diverge da lateral")
                        if prior_dim and prior_dim != (width, height):
                            reasons.append(f"leitura anterior {row.get('dim')} diverge da lateral {dim}")
                        if cut_heights and (len(cut_heights) != 1 or abs(next(iter(cut_heights)) - height) > 0.6):
                            reasons.append("altura do corte diverge da lateral")
                        if nearby_text_dims and (width, height) not in nearby_text_dims:
                            alternatives = ", ".join(_fmt_dimension(*d) for d in sorted(nearby_text_dims))
                            reasons.append(f"texto de dimensão próximo ({alternatives}) diverge da lateral")
                        if not cut_heights and (width, height) not in nearby_text_dims:
                            reasons.append("altura da lateral sem corte independente para confirmar")
                        row["dim"] = dim
                        row["dim_status"] = "conflict" if prior_dim and prior_dim != (width, height) else "inferred" if reasons else "sa"
                        row["dim_motivo"] = ("; ".join(reasons) + "; revisar no DXF."
                                             if reasons else "Dimensão da lateral confirmada pelo texto local ou corte e largura do fundo.")
                    elif len(dimensions) > 1:
                        row["dim"] = _fmt_dimension(next(iter(widths)) if len(widths) == 1 else None, None)
                        row["dim_status"] = "ambiguous"
                        row["dim_motivo"] = "Laterais vinculadas ao pilar têm dimensões divergentes: " + ", ".join(
                            _fmt_dimension(*d) for d in sorted(dimensions)) + "."
                    elif len(nearby_text_dims) == 1:
                        width, height = next(iter(nearby_text_dims))
                        row["dim"] = _fmt_dimension(width, height)
                        row["dim_status"] = "inferred"
                        row["dim_motivo"] = "Texto de dimensão próximo ao segmento, sem lateral independente para confirmar."
                    else:
                        row["dim"] = _fmt_dimension(next(iter(widths)) if len(widths) == 1 else None,
                                                     next(iter(cut_heights)) if len(cut_heights) == 1 else None)
                        row["dim_status"] = "missing"
                        row["dim_motivo"] = "Sem dimensão independente de lateral; dimensão anterior da tabela não foi reutilizada como prova da viga."
                if value is None:
                    row["nivel"] = "?"
                    reason += " Nível de chegada do pilar indisponível."
                else:
                    row["nivel"] = f"{value:.2f}"
                    if status in ("fallback", "ambiguous"):
                        reason += " Exibido provisoriamente o nível de chegada do pilar."
                row["nivel_status"] = status
                row["nivel_motivo"] = reason
    return result
