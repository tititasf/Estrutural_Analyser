"""
Análise Geral Headless — equivalente a process_pillars_action sem GUI/PySide6.

Fluxo:
  1. Lê DXF path do projeto no DB
  2. Carrega DXF via DXFLoader
  3. Constrói SpatialIndex
  4. Roda BeamTracer.detect_beams()
  5. Para cada beam FV extrai dados com fixes:
       - panels_n1 = len(merged_bottom_lengths)  [spans entre pilares, não links brutos]
       - comprimento  = sum(merged_bottom_lengths)
       - dim/h        = texto de dimensão MAIS PRÓXIMO do label (h = min do par)
  6. UPSERT em beam_elements (project_data.vision)
  7. Render headless do pavimento (limpo + vínculos) p/ inspeção visual
  8. Roda fv_loop_runner.run() para comparação automática

Uso:
    python -X utf8 scripts/analise_geral_headless.py --obra Obra_TREINO_1 --pav 13
    python -X utf8 scripts/analise_geral_headless.py --obra Obra_TREINO_1 --pav 13 --debug-beam V302
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")


# ── helpers ───────────────────────────────────────────────────────────────────

DIM_RE = re.compile(r"\(?\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*\)?")


def _parse_dim_pair(dim_text: str | None) -> tuple[float, float] | None:
    if not dim_text:
        return None
    m = DIM_RE.search(str(dim_text))
    if not m:
        return None
    first = float(m.group(1).replace(",", "."))
    second = float(m.group(2).replace(",", "."))
    return min(first, second), max(first, second)


def _parse_dim_text(texts: list, beam_pos: tuple | None = None) -> str | None:
    """Retorna o texto de dimensão mais próximo do beam (ou o primeiro válido).
    beam_pos: (x, y) da posição do label do beam no DXF.
    """
    candidates = []
    for t in texts:
        txt = t.get("text", "").strip()
        if _parse_dim_pair(txt):
            if beam_pos and "pos" in t:
                p = t["pos"]
                dist = math.sqrt((p[0] - beam_pos[0]) ** 2 + (p[1] - beam_pos[1]) ** 2)
                candidates.append((dist, txt))
            else:
                return txt
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    return None


def _parse_h(dim_text: str | None) -> float | None:
    """Extrai espessura h da viga a partir de texto tipo '19/55' ou '120/19'.
    Para FV (fundo de viga), h é sempre a dimensão MENOR (espessura da seção).
    Ex: '19/55' → min(19,55)=19  |  '120/19' → min(120,19)=19  |  '24/66' → min(24,66)=24
    """
    pair = _parse_dim_pair(dim_text)
    return pair[0] if pair else None


def _axis_point(coord_value: float, beam_pos: tuple, is_horizontal: bool) -> tuple[float, float]:
    return (coord_value, beam_pos[1]) if is_horizontal else (beam_pos[0], coord_value)


def _dist_point_to_axis_span(pos: tuple, coord: tuple, beam_pos: tuple, is_horizontal: bool) -> float:
    if is_horizontal:
        along = min(max(pos[0], coord[0]), coord[1])
        return math.hypot(pos[0] - along, pos[1] - beam_pos[1])
    along = min(max(pos[1], coord[0]), coord[1])
    return math.hypot(pos[0] - beam_pos[0], pos[1] - along)


def _query_texts(spatial_index, bbox: tuple) -> list[dict]:
    if not spatial_index:
        return []
    return [c for c in spatial_index.query_bbox(bbox) if isinstance(c, dict) and c.get("text")]


def _find_segment_dim(seg: dict, beam_pos: tuple, is_horizontal: bool, spatial_index) -> dict | None:
    coord = seg.get("coord")
    if not coord or not beam_pos:
        return None
    pad_axis = 120.0
    pad_trans = 260.0
    if is_horizontal:
        bbox = (coord[0] - pad_axis, beam_pos[1] - pad_trans, coord[1] + pad_axis, beam_pos[1] + pad_trans)
    else:
        bbox = (beam_pos[0] - pad_trans, coord[0] - pad_axis, beam_pos[0] + pad_trans, coord[1] + pad_axis)
    candidates = []
    for t in _query_texts(spatial_index, bbox):
        pair = _parse_dim_pair(t.get("text", ""))
        if not pair or not t.get("pos"):
            continue
        score = _dist_point_to_axis_span(t["pos"], coord, beam_pos, is_horizontal)
        candidates.append((score, t, pair))
    if not candidates:
        return None
    score, text_link, pair = min(candidates, key=lambda x: x[0])
    if score > pad_trans * 1.5:
        return None
    link = dict(text_link)
    link["type"] = link.get("type") or "text"
    link["role"] = "Dimensao fundo de viga"
    return {"text": link.get("text", ""), "link": link, "width": pair[0], "height": pair[1], "score": score}


def _choose_segment_dim(seg_dim: dict | None, dim_text: str | None, h_n1: float | None, seg_len: float | None) -> dict:
    """Prefere a dimensao vinculada ao segmento e usa a global apenas como fallback."""
    global_pair = _parse_dim_pair(dim_text)
    if not seg_dim:
        if not global_pair:
            return {"text": dim_text or "", "width": h_n1 or 0, "height": 0, "link": None}
        return {
            "text": dim_text or "",
            "width": global_pair[0],
            "height": global_pair[1],
            "link": None,
        }

    local_width = float(seg_dim.get("width") or 0)
    local_score = float(seg_dim.get("score") or 9999)
    global_width = float((global_pair or (h_n1 or 0, 0))[0] or 0)
    return {
        "text": seg_dim.get("text") or dim_text or "",
        "width": local_width or global_width,
        "height": float(seg_dim.get("height") or (global_pair[1] if global_pair else 0) or 0),
        "link": seg_dim.get("link"),
        "score": local_score,
        "source": "segment",
    }


def _is_support_label(
    text: str,
    current_beam: str = "",
    ignored_labels: set[str] | None = None,
) -> bool:
    txt = str(text or "").strip().upper()
    if not txt or _parse_dim_pair(txt):
        return False
    if current_beam and txt == current_beam.upper():
        return False
    if ignored_labels and txt in ignored_labels:
        return False
    return bool(re.match(r"^(?:P|V|VF|VP|CONT)[A-Z0-9_.-]*\d[A-Z0-9_.-]*$", txt))


def _find_support_text(
    endpoint: tuple,
    spatial_index,
    current_beam: str = "",
    ignored_labels: set[str] | None = None,
) -> dict | None:
    if not endpoint or not spatial_index:
        return None
    radius = 320.0
    bbox = (endpoint[0] - radius, endpoint[1] - radius, endpoint[0] + radius, endpoint[1] + radius)
    candidates = []
    for t in _query_texts(spatial_index, bbox):
        if not _is_support_label(t.get("text", ""), current_beam, ignored_labels):
            continue
        pos = t.get("pos")
        if not pos:
            continue
        dist = math.hypot(pos[0] - endpoint[0], pos[1] - endpoint[1])
        label = str(t.get("text") or "").strip().upper()
        # Rótulos VF* nomeiam fundos de viga e podem ficar geometricamente
        # próximos do encontro sem serem o apoio estrutural da extremidade.
        # P*/V* vencem; VF* permanece como fallback quando não há apoio melhor.
        priority = 1 if label.startswith("VF") else 0
        candidates.append((priority, dist, t))
    if not candidates:
        return None
    _, _, link = min(candidates, key=lambda x: (x[0], x[1]))
    out = dict(link)
    out["type"] = out.get("type") or "text"
    out["role"] = "Apoio fundo de viga"
    return out


def _seg_length_2pts(p1, p2) -> float:
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def _bbox_length_width(points: list | tuple | None) -> tuple[float, float]:
    """Retorna (comprimento, largura) pelo envelope físico do contorno FV."""
    clean: list[tuple[float, float]] = []
    for point in points or []:
        try:
            clean.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError, IndexError):
            continue
    if not clean:
        return 0.0, 0.0
    xs = [point[0] for point in clean]
    ys = [point[1] for point in clean]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    return max(dx, dy), min(dx, dy)


def _format_optional_measure(value: float | None) -> str:
    if value is None or value <= 0.05:
        return "N/A"
    rounded = round(float(value), 1)
    if abs(rounded - round(rounded)) <= 0.05:
        return str(int(round(rounded)))
    return str(rounded).replace(".", ",")


def _snap_chamfer_length(value: float | None) -> float | None:
    if value is None or value <= 0.05:
        return None
    snapped = round(float(value) * 2.0) / 2.0
    if abs(float(value) - snapped) <= 0.15:
        return snapped
    return None


def _has_declared_chamfer(
    chamfers: dict[str, str],
    *,
    structural_width: float | None = None,
) -> bool:
    """Aceita recuos de chanfro compatíveis com a seção do próprio fundo.

    A derivação geométrica pode enxergar uma face quebrada ou uma associação
    vizinha como dois ``cantos`` ausentes. Isso não é chanfro: valores enormes
    fariam o comprimento ser congelado por ``chamfer_half_cm_snap`` e
    esconderiam a perda de um trecho inteiro. Chanfros simples de término são
    locais; geometrias diagonais longas seguem o caminho explícito
    ``special_diagonal`` do interpretador.
    """
    values: list[float] = []
    for raw in (chamfers or {}).values():
        text = str(raw or "").strip().upper()
        if not text or text == "N/A":
            continue
        try:
            value = float(text.replace(",", "."))
        except ValueError:
            return False
        if value <= 0.05:
            continue
        values.append(value)
    if not values:
        return False
    try:
        width = float(structural_width or 0.0)
    except (TypeError, ValueError):
        width = 0.0
    max_local_recess = max(40.0, width * 2.0)
    return all(value <= max_local_recess + 0.05 for value in values)


def _derive_fundo_chamfers(
    points: list | tuple | None,
    is_horizontal: bool,
) -> dict[str, str]:
    """Deriva chanfros simples a partir do contorno fechado do fundo.

    Convenção usada pela ficha granular FV:
    - `*_top`: recuo na borda superior do painel.
    - `*_fun`: recuo na borda inferior/fundo.
    """
    clean: list[tuple[float, float]] = []
    for point in points or []:
        try:
            candidate = (float(point[0]), float(point[1]))
        except (TypeError, ValueError, IndexError):
            continue
        if candidate not in clean:
            clean.append(candidate)
    if len(clean) < 4:
        return {}

    axis = 0 if is_horizontal else 1
    transverse_axis = 1 - axis
    transverse_values = [point[transverse_axis] for point in clean]
    low = min(transverse_values)
    high = max(transverse_values)
    tol = max(0.25, (high - low) * 0.10)
    low_axis = [point[axis] for point in clean if abs(point[transverse_axis] - low) <= tol]
    high_axis = [point[axis] for point in clean if abs(point[transverse_axis] - high) <= tol]
    if not low_axis or not high_axis:
        return {}

    left_low = min(low_axis)
    left_high = min(high_axis)
    right_low = max(low_axis)
    right_high = max(high_axis)

    left_top = max(0.0, left_high - left_low)
    left_bottom = max(0.0, left_low - left_high)
    right_top = max(0.0, right_low - right_high)
    right_bottom = max(0.0, right_high - right_low)
    return {
        "chanfro_esq_top": _format_optional_measure(left_top),
        "chanfro_esq_fun": _format_optional_measure(left_bottom),
        "chanfro_dir_top": _format_optional_measure(right_top),
        "chanfro_dir_fun": _format_optional_measure(right_bottom),
    }


def _fundo_segment_contour(
    coord: tuple | list | None,
    beam_pos: tuple | None,
    is_horizontal: bool,
    width: float,
    raw_lines: list,
) -> list[tuple[float, float]]:
    if not coord or not beam_pos:
        return []
    try:
        span_min, span_max = sorted((float(coord[0]), float(coord[1])))
    except (TypeError, ValueError, IndexError):
        return []
    axis = 0 if is_horizontal else 1
    transverse_axis = 1 - axis
    span_length = span_max - span_min
    matching_lines: list[list[tuple[float, float]]] = []
    for line in raw_lines or []:
        clean = []
        for point in line or []:
            try:
                clean.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError, IndexError):
                continue
        if len(clean) < 2:
            continue
        line_min = min(point[axis] for point in clean)
        line_max = max(point[axis] for point in clean)
        overlap = min(line_max, span_max) - max(line_min, span_min)
        line_span = line_max - line_min
        # Face de fundo é paralela ao eixo do segmento. Caps e linhas
        # perpendiculares podem tocar o vão, mas não definem a posição lateral
        # da área. Exigir cobertura proporcional evita escolher vizinhos.
        if (
            overlap > 0.0
            and line_span >= max(0.05, span_length * 0.20)
        ):
            matching_lines.append(clean)
    if matching_lines:
        transverse_values = [
            point[transverse_axis]
            for line in matching_lines
            for point in line
        ]
        center = (min(transverse_values) + max(transverse_values)) / 2.0
    else:
        center = float(beam_pos[transverse_axis])
    from src.core.beam_interpreters.fundo_viga import FundoVigaInterpreter

    # Quando o tracer já aceitou um vão contínuo, uma face pode aparecer em
    # pedaços colineares por cruzar um pilar NASCE. Reconstituir o par de faces
    # paralelas pelo eixo transversal evita o polígono diagonal/torto; linhas
    # diagonais (chanfros) ficam fora desta regra e seguem o interpretador.
    face_positions: list[float] = []
    for line in matching_lines:
        transverse = [point[transverse_axis] for point in line]
        if max(transverse) - min(transverse) <= 0.05:
            position = sum(transverse) / len(transverse)
            if not any(abs(position - known) <= 0.05 for known in face_positions):
                face_positions.append(position)
    face_positions.sort()
    if len(face_positions) >= 2:
        expected_width = abs(float(width))
        pair = min(
            (
                (abs(right - left - expected_width), left, right)
                for index, left in enumerate(face_positions)
                for right in face_positions[index + 1:]
            ),
            default=None,
        )
        if pair and pair[0] <= max(0.05, expected_width * 0.15):
            _error, low_face, high_face = pair
            if is_horizontal:
                rectangle = [
                    (span_min, low_face), (span_max, low_face),
                    (span_max, high_face), (span_min, high_face),
                ]
            else:
                rectangle = [
                    (low_face, span_min), (low_face, span_max),
                    (high_face, span_max), (high_face, span_min),
                ]
            return rectangle + [rectangle[0]]

    # Uma única face longitudinal ainda é evidência física suficiente para a
    # largura conhecida da seção. Não a trate como eixo/centro: o rótulo da
    # viga indica de qual lado a segunda face deve ficar. Isso recompõe a área
    # inteira do vão N1 quando a face oposta foi quebrada por encontro/cap,
    # sem transformar um caso realmente diagonal em retângulo.
    has_diagonal_evidence = any(
        (max(point[axis] for point in line) - min(point[axis] for point in line)) > 0.05
        and (max(point[transverse_axis] for point in line) - min(point[transverse_axis] for point in line))
        > max(0.05, abs(float(width)) * 0.10)
        for line in matching_lines
        if line
    )
    if len(face_positions) == 1 and not has_diagonal_evidence:
        # Uma face real: borda do contorno sobre a linha DXF (não flutuando
        # em torno do centro sintético do rótulo).
        label_transverse = float(beam_pos[transverse_axis])
        return FundoVigaInterpreter.build_area_contour(
            axial_span=(span_min, span_max),
            width=width,
            is_horizontal=is_horizontal,
            transverse_center=label_transverse,
            boundary_lines=matching_lines,
            allow_synthetic=False,
        )

    return FundoVigaInterpreter.build_area_contour(
        axial_span=(span_min, span_max),
        width=width,
        is_horizontal=is_horizontal,
        transverse_center=center,
        boundary_lines=matching_lines,
        allow_synthetic=not matching_lines,
    )


def _format_measure(value: float) -> str:
    value = float(value)
    if abs(value - round(value)) <= 0.05:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _filter_fv_visual_obstacles(obstacles: list[dict] | None) -> list[dict]:
    """Mantém a marca NASCE para o tracer atravessar a lacuna corretamente."""
    normalized = []
    for obstacle in obstacles or []:
        item = dict(obstacle or {})
        if str(item.get("type") or "").strip().upper() == "NASCE":
            item["type"] = "PILAR_NASCENTE"
        normalized.append(item)
    return normalized


# ── DB helpers ─────────────────────────────────────────────────────────────────

def get_project(obra_name: str, pav_filter: str | None, db_path: Path):
    """Retorna (project_id, dxf_path) do projeto."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if pav_filter:
            row = conn.execute(
                "SELECT id, dxf_path FROM projects WHERE work_name=? AND pavement_name LIKE ?",
                [obra_name, f"%{pav_filter}%"],
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, dxf_path FROM projects WHERE work_name=? LIMIT 1",
                [obra_name],
            ).fetchone()
        if not row:
            return None, None
        return row["id"], row["dxf_path"]
    finally:
        conn.close()


def upsert_beam_element_fv(conn: sqlite3.Connection, project_id: str, viga_nome: str,
                            n_segmentos: int, campos: dict):
    """UPSERT cirúrgico em beam_elements para classe FV."""
    el_id = f"BE-FV-{project_id}-{viga_nome}"
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO beam_elements
            (id, project_id, parent_beam_id, viga_nome, classe,
             campos_json, n_segmentos, is_validated, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'FV', ?, ?, 0, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            campos_json  = excluded.campos_json,
            n_segmentos  = excluded.n_segmentos,
            updated_at   = excluded.updated_at
        """,
        (el_id, str(project_id), "", viga_nome,
         json.dumps(campos, ensure_ascii=False),
         n_segmentos, now, now),
    )


# ── motor FV (extração sem GUI) ───────────────────────────────────────────────

def process_beam_fv(b: dict, spatial_index=None, visual_obstacles=None) -> dict:
    """
    Extrai dados FV de um beam do BeamTracer.
    Fixes aplicados:
    - dim_text: usa texto de dimensão MAIS PRÓXIMO da posição do beam label
    - panels_n1: len(merged_bottom_lengths)
    - bridging: obstáculos visuais (Pilares NASCE, Visão Corte) são superados fundindo spans adjacentes
    """
    from src.core.preficha_segments import fundo_topology_is_locked

    if fundo_topology_is_locked(b):
        import re as _re_locked

        segmentos_fundo = []
        links = b.get("links") or {}
        fields = b.get("fields") or {}
        allowed_source_keys = set(
            b.get("preficha_fundo_locked_source_keys") or []
        )
        if int(b.get("preficha_fundo_locked_version") or 0) < 2:
            from src.core.preficha_segments import lock_fundo_topology
            lock_fundo_topology(b)
            allowed_source_keys = set(
                b.get("preficha_fundo_locked_source_keys") or []
            )
        for key in sorted(allowed_source_keys):
            slots = links.get(key) or {}
            match = _re_locked.match(
                r"^viga_fundo_seg_(\d+)_area_segs$", str(key)
            )
            if not match or not isinstance(slots, dict):
                continue
            contours = slots.get("contour") or []
            if not contours or not isinstance(contours[0], dict):
                continue
            link = contours[0]
            points = []
            for point in link.get("points") or []:
                try:
                    points.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError, IndexError):
                    continue
            if len(points) < 2:
                continue
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            horizontal = (max(xs) - min(xs)) >= (max(ys) - min(ys))
            coord = (
                (min(xs), max(xs))
                if horizontal
                else (min(ys), max(ys))
            )
            length, _width = _bbox_length_width(points)
            measure_source = str(link.get("fv_measure_source") or "")
            try:
                measure_length = float(link.get("fv_measure_length") or 0.0)
            except (TypeError, ValueError):
                measure_length = 0.0
            try:
                measure_width = float(link.get("fv_measure_width") or 0.0)
            except (TypeError, ValueError):
                measure_width = 0.0
            is_canonical_measure = (
                measure_source.startswith((
                    "special_diagonal",
                    "chamfer_half_cm_snap",
                ))
                and measure_length > 0.05
            )
            if is_canonical_measure:
                length = measure_length
            if length <= 0.05:
                length = abs(coord[1] - coord[0])
            if length > 0.05:
                link["len"] = length
                ficha = dict(link.get("ficha") or {})
                ficha["comprimento_total_fundo"] = _format_measure(length)
                if measure_source.startswith("special_diagonal") and measure_width > 0.05:
                    ficha["largura_total_fundo"] = _format_measure(measure_width)
                elif _width > 0.05:
                    ficha["largura_total_fundo"] = _format_measure(_width)
                link["ficha"] = ficha
            segment_index = int(match.group(1))
            segment = {
                "seg_index": segment_index,
                "length": length,
                "coord": coord,
                "geometry": points,
                "logical": True,
                "dim_text": fields.get(
                    f"viga_fundo_seg_{segment_index}_dim", ""
                ),
                "apoio_inicial": fields.get(
                    f"viga_fundo_seg_{segment_index}_local_ini", ""
                ),
                "apoio_final": fields.get(
                    f"viga_fundo_seg_{segment_index}_local_fim", ""
                ),
                "ficha": dict(link.get("ficha") or {}),
            }
            if is_canonical_measure:
                segment["measure_source"] = measure_source
                segment["measure_length"] = measure_length
                if measure_width > 0.05:
                    segment["measure_width"] = measure_width
            segmentos_fundo.append(segment)
        segmentos_fundo.sort(key=lambda item: item["seg_index"])
        dim_text = str(fields.get("dimensao") or "")
        viga_nome = str(b.get("name") or "?")
        if viga_nome != "?":
            if viga_nome.endswith("-1"):
                viga_nome = viga_nome[:-2] + ".C"
            elif not viga_nome.endswith(".C"):
                viga_nome += ".C"
        return {
            "viga_nome": viga_nome,
            "panels_n1": len(segmentos_fundo),
            "comprimento_fundo": round(
                sum(float(seg.get("length") or 0.0) for seg in segmentos_fundo),
                3,
            ),
            "dim_text": dim_text,
            "h_n1": _parse_h(dim_text),
            "is_horizontal": bool(b.get("fv_is_h", b.get("is_h", True))),
            "merged_groups_count": 0,
            "merged_lengths_count": len(segmentos_fundo),
            "seg_bottom_raw_count": len(segmentos_fundo),
            "segmentos_fundo": segmentos_fundo,
            "topologia_origem": "validacao_humana_bloqueada",
        }

    visual_obstacles = visual_obstacles or []
    ignored_support_labels = {
        str(label or "").strip().upper()
        for label in (b.get("_fv_ignored_support_labels") or [])
        if str(label or "").strip()
    }
    geo = b.get("geometry", {})
    classified = geo.get("classified", {})
    beam_pos = b.get("pos")
    dim_texts = []
    if beam_pos and spatial_index:
        cands = spatial_index.query_bbox((beam_pos[0]-300, beam_pos[1]-300, beam_pos[0]+300, beam_pos[1]+300))
        for cand in cands:
            if isinstance(cand, dict) and 'text' in cand:
                dim_texts.append(cand)

    merged_groups = classified.get("merged_bottom_groups", [])
    merged_lengths = classified.get("merged_bottom_lengths", [])
    merged_coords = classified.get("merged_bottom_groups_coords", [])
    seg_bottom_raw = classified.get("seg_bottom", [])

    # BRIDGING LOGIC: se houver coords, podemos fundir gaps que caem dentro de visual_obstacles
    if merged_coords and len(merged_coords) > 1 and visual_obstacles and beam_pos:
        is_h = b.get("is_h", True)
        new_coords = []
        new_lengths = []
        
        cur_min, cur_max = merged_coords[0]
        
        for i in range(1, len(merged_coords)):
            nxt_min, nxt_max = merged_coords[i]
            gap_mid = (cur_max + nxt_min) / 2.0
            
            # Ponto do gap a ser checado contra as bboxes
            gap_pt = (gap_mid, beam_pos[1]) if is_h else (beam_pos[0], gap_mid)
            
            bridged = False
            for obs in visual_obstacles:
                if str(obs.get("type") or "").upper() != "VISAO_CORTE":
                    continue
                bx1, by1, bx2, by2 = obs['bbox']
                # Expansão leve na bbox para capturar imperfeições
                if bx1 - 10 <= gap_pt[0] <= bx2 + 10 and by1 - 10 <= gap_pt[1] <= by2 + 10:
                    bridged = True
                    break
                    
            if bridged:
                cur_max = max(cur_max, nxt_max)
            else:
                new_coords.append((cur_min, cur_max))
                new_lengths.append(cur_max - cur_min)
                cur_min, cur_max = nxt_min, nxt_max
                
        new_coords.append((cur_min, cur_max))
        new_lengths.append(cur_max - cur_min)
        
        merged_coords = new_coords
        merged_lengths = new_lengths

    # FV possui orientação própria por ocorrência baseada em coordenadas do vão real
    if merged_coords and beam_pos:
        coord0 = merged_coords[0]
        coord_mid = (float(coord0[0]) + float(coord0[1])) / 2.0
        delta_y = abs(coord_mid - float(beam_pos[1]))
        delta_x = abs(coord_mid - float(beam_pos[0]))
        is_horizontal = delta_x < delta_y
    else:
        is_horizontal = bool(b.get('fv_is_h', b.get('is_h', True)))
    contour_lines = (
        list(seg_bottom_raw)
        + list(classified.get('seg_side_a') or [])
        + list(classified.get('seg_side_b') or [])
    )
    dim_text = _parse_dim_text(dim_texts, beam_pos=beam_pos)
    h_n1 = _parse_h(dim_text)
    
    if merged_lengths:
        panels_n1 = len(merged_lengths)
        comprimento = sum(merged_lengths)
        segmentos_fundo = []
        for i in range(len(merged_lengths)):
            coord = merged_coords[i] if i < len(merged_coords) else None
            if coord and not is_horizontal:
                # EXCLUSIVO FUNDOS DE VIGA (FV): Viga vertical tem Inicio = Cima (max Y) e Fim = Baixo (min Y)
                c0, c1 = float(coord[0]), float(coord[1])
                coord = (max(c0, c1), min(c0, c1))
            geometry = _fundo_segment_contour(
                coord,
                beam_pos,
                bool(is_horizontal),
                float(h_n1 or 20.0),
                contour_lines,
            )
            from src.core.beam_interpreters.fundo_viga import FundoVigaInterpreter
            provenance = FundoVigaInterpreter.build_provenance(
                contour=geometry,
                boundary_lines=contour_lines,
                is_horizontal=bool(is_horizontal),
                segment_index=i + 1,
            )
            segmentos_fundo.append({
                "seg_index": i + 1,
                "length": merged_lengths[i],
                "coord": coord,
                "geometry": geometry,
                "provenance": provenance,
                "logical": True,
            })
    elif merged_groups:
        panels_n1 = len(merged_groups)
        comprimento = sum(_seg_length_2pts(g[0][0], g[0][1]) for g in merged_groups if g and len(g[0]) >= 2)
        segmentos_fundo = []
        for i, grp in enumerate(merged_groups):
            p_min, p_max = None, None
            if grp and len(grp[0]) >= 2:
                if is_horizontal:
                    p_min = min(grp[0][0][0], grp[0][-1][0])
                    p_max = max(grp[0][0][0], grp[0][-1][0])
                else:
                    # EXCLUSIVO FUNDOS DE VIGA (FV): Viga vertical tem Inicio = Cima (max Y) e Fim = Baixo (min Y)
                    p_min = max(grp[0][0][1], grp[0][-1][1])
                    p_max = min(grp[0][0][1], grp[0][-1][1])
            segmentos_fundo.append({
                "seg_index": i + 1, 
                "geometry": grp[0] if grp else [], 
                "coord": (p_min, p_max) if p_min is not None else None, 
                "logical": True
            })
    else:
        panels_n1 = len(seg_bottom_raw)
        comprimento = sum(_seg_length_2pts(s[0], s[-1]) for s in seg_bottom_raw if len(s) >= 2)
        segmentos_fundo = []
        for i, s in enumerate(seg_bottom_raw):
            p_min, p_max = None, None
            if len(s) >= 2:
                if is_horizontal:
                    p_min = min(s[0][0], s[-1][0])
                    p_max = max(s[0][0], s[-1][0])
                else:
                    # EXCLUSIVO FUNDOS DE VIGA (FV): Viga vertical tem Inicio = Cima (max Y) e Fim = Baixo (min Y)
                    p_min = max(s[0][1], s[-1][1])
                    p_max = min(s[0][1], s[-1][1])
            segmentos_fundo.append({
                "seg_index": i + 1, 
                "geometry": s, 
                "coord": (p_min, p_max) if p_min is not None else None, 
                "logical": False
            })

    # dim: texto mais próximo da posição real do beam
    dim_text = _parse_dim_text(dim_texts, beam_pos=beam_pos)
    h_n1 = _parse_h(dim_text)
    apoio_inicial = ""
    apoio_final = ""
    supports = (b.get("geometry", {}) or {}).get("support_candidates", []) or []
    if supports:
        def _support_key(s):
            pts = s.get("points") or []
            if pts:
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                return cx if is_horizontal else cy
            pos = s.get("pos") or (0, 0)
            return pos[0] if is_horizontal else pos[1]

        def _support_label(s):
            for key in ("name", "text", "label", "id_item", "id"):
                if s.get(key):
                    return str(s.get(key))
            return ""

        supports = [
            s for s in supports
            if _support_label(s).strip().upper() not in ignored_support_labels
        ]
        # EXCLUSIVO FUNDOS DE VIGA (FV):
        # - Viga horizontal: Inicio = Esquerda (menor X) -> Fim = Direita (maior X)
        # - Viga vertical: Inicio = Cima (maior Y) -> Fim = Baixo (menor Y)
        if is_horizontal:
            ordered = sorted(supports, key=_support_key)
        else:
            ordered = sorted(supports, key=_support_key, reverse=True)

        apoio_inicial = _support_label(ordered[0]) if ordered else ""
        apoio_final = _support_label(ordered[-1]) if len(ordered) > 1 else ""

    for seg in segmentos_fundo:
        seg_len = seg.get("length")
        canonical_span_length = None
        _geometry_width = 0.0
        if seg_len is None and seg.get("coord"):
            try:
                seg_len = abs(float(seg["coord"][1]) - float(seg["coord"][0]))
            except Exception:
                seg_len = 0.0
        if seg.get("coord"):
            try:
                candidate = abs(float(seg["coord"][1]) - float(seg["coord"][0]))
                if candidate > 0.05:
                    canonical_span_length = candidate
            except Exception:
                pass
        explicit_special_measure = str(seg.get("measure_source") or "")
        if canonical_span_length is not None and not explicit_special_measure.startswith(
            "special_diagonal"
        ):
            # O intervalo consolidado do BeamTracer é a medida N1. Um bbox de
            # contorno parcial não pode encurtá-lo; ele é só evidência de
            # posição/forma a ser reparada, nunca substituto do vão.
            seg_len = canonical_span_length
        if seg.get("geometry"):
            geometry_length, _geometry_width = _bbox_length_width(seg.get("geometry"))
            if geometry_length > 0.05 and canonical_span_length is None:
                seg_len = geometry_length
        chamfers = _derive_fundo_chamfers(seg.get("geometry"), bool(is_horizontal))
        snapped_length = (
            _snap_chamfer_length(seg_len)
            if canonical_span_length is None and _has_declared_chamfer(
                chamfers,
                structural_width=_geometry_width,
            )
            else None
        )
        if snapped_length is not None:
            seg_len = snapped_length
            seg["measure_source"] = "chamfer_half_cm_snap"
            seg["measure_length"] = snapped_length
        if seg_len is not None:
            if abs(seg_len - round(seg_len)) <= 0.15:
                seg_len = float(round(seg_len))
            seg["length"] = seg_len

        seg_dim = _find_segment_dim(seg, beam_pos, is_horizontal, spatial_index) if beam_pos else None
        chosen_dim = _choose_segment_dim(seg_dim, dim_text, h_n1, seg_len)
        seg_dim_text = chosen_dim.get("text") or ""
        seg_width = chosen_dim.get("width") or 0
        seg_height = chosen_dim.get("height") or 0

        start_link = end_link = None
        if seg.get("coord") and beam_pos:
            start_pt = _axis_point(float(seg["coord"][0]), beam_pos, is_horizontal)
            end_pt = _axis_point(float(seg["coord"][1]), beam_pos, is_horizontal)
            start_link = _find_support_text(
                start_pt,
                spatial_index,
                b.get("name", ""),
                ignored_support_labels,
            )
            end_link = _find_support_text(
                end_pt,
                spatial_index,
                b.get("name", ""),
                ignored_support_labels,
            )

        seg["dim_text"] = seg_dim_text
        if chosen_dim.get("link"):
            seg["dim_link"] = chosen_dim.get("link")
        seg["dim_width"] = round(float(seg_width or 0), 1)
        seg["dim_height"] = round(float(seg_height or 0), 1)
        if chosen_dim.get("source"):
            seg["dim_source"] = chosen_dim.get("source")
        seg["apoio_inicial"] = (start_link or {}).get("text") or apoio_inicial
        seg["apoio_final"] = (end_link or {}).get("text") or apoio_final
        if start_link:
            seg["apoio_inicial_link"] = start_link
        if end_link:
            seg["apoio_final_link"] = end_link
        seg["ficha"] = {
            "largura_total_fundo": round(float(seg_width or 0), 1),
            "comprimento_total_fundo": round(float(seg_len or 0), 1),
            "altura_total": round(float(seg_height or 0), 1),
            "abertura_especial": "N/A",
            "chanfro_esq_top": "N/A",
            "chanfro_esq_fun": "N/A",
            "chanfro_dir_top": "N/A",
            "chanfro_dir_fun": "N/A",
            "abertura_topo_esq": "N/A",
            "abertura_topo_dir": "N/A",
            "abertura_fundo_esq": "N/A",
            "abertura_fundo_dir": "N/A",
        }
        seg["ficha"].update(chamfers)

    comprimento = sum(float(seg.get("length") or 0.0) for seg in segmentos_fundo)

    viga_nome = b.get("name", "?")
    if viga_nome != "?":
        if viga_nome.endswith("-1"):
            viga_nome = viga_nome[:-2] + ".C"
        elif not viga_nome.endswith(".C"):
            viga_nome = viga_nome + ".C"

    return {
        "viga_nome": viga_nome,
        "panels_n1": panels_n1,
        "comprimento_fundo": round(comprimento, 1),
        "dim_text": dim_text,
        "h_n1": h_n1,
        "is_horizontal": bool(is_horizontal),
        "merged_groups_count": len(merged_groups),
        "merged_lengths_count": len(merged_lengths),
        "seg_bottom_raw_count": len(seg_bottom_raw),
        "segmentos_fundo": segmentos_fundo,
    }


# ── runner principal ──────────────────────────────────────────────────────────

def run(
    obra_name: str,
    pav_filter: str | None = None,
    db_path: Path = DB_PATH,
    debug_beam: str | None = None,
):
    print(f"\n[Análise Geral Headless] obra={obra_name} pav={pav_filter or 'TODOS'}")

    # 1. Projeto
    project_id, dxf_path = get_project(obra_name, pav_filter, db_path)
    if not project_id:
        print("  [ERRO] Projeto não encontrado no DB.")
        return
    if not dxf_path or not Path(dxf_path).exists():
        print(f"  [ERRO] DXF não encontrado: {dxf_path}")
        return
    print(f"  project_id: {project_id}")
    print(f"  dxf_path:   {dxf_path}")

    # 2. DXF
    print("  Carregando DXF...")
    from src.core.dxf_loader import DXFLoader, RenderMode
    dxf_data = DXFLoader.load_dxf(dxf_path, mode=RenderMode.TRUE_GEOMETRY)
    if not dxf_data:
        print("  [ERRO] DXFLoader retornou None.")
        return
    lines = dxf_data.get("lines", [])
    polys = dxf_data.get("polylines", [])
    texts = dxf_data.get("texts", [])
    print(f"  DXF: {len(lines)} linhas, {len(polys)} polys, {len(texts)} textos")

    # 3. SpatialIndex
    print("  Construindo SpatialIndex...")
    from src.core.spatial_index import SpatialIndex
    spatial_index = SpatialIndex()
    for poly in polys:
        pts = poly.get("points", [])
        if pts:
            bounds = (
                min(p[0] for p in pts), min(p[1] for p in pts),
                max(p[0] for p in pts), max(p[1] for p in pts),
            )
            spatial_index.insert(poly, bounds)
    for line in lines:
        s, e = line["start"], line["end"]
        bounds = (min(s[0], e[0]), min(s[1], e[1]), max(s[0], e[0]), max(s[1], e[1]))
        spatial_index.insert(line, bounds)
    for txt in texts:
        p = txt["pos"]
        spatial_index.insert(txt, (p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5))
    print(f"  SpatialIndex: {spatial_index.counter} objetos indexados")

    # 4. BeamTracer
    print("  Executando BeamTracer...")
    from src.core.beam_tracer import BeamTracer
    all_lines_and_polys = []
    for l in lines + polys:
        if "points" in l:
            all_lines_and_polys.append(l)
        elif "start" in l:
            all_lines_and_polys.append({"points": [l["start"], l["end"]]})

    beam_tracer = BeamTracer(spatial_index)
    # 4.5 Obter Obstáculos Visuais
    print("  Carregando obstáculos visuais do DB...")
    try:
        from scripts.motor_reverso_fv import _get_visual_obstacles
        visual_obstacles = _filter_fv_visual_obstacles(_get_visual_obstacles(str(project_id)))
        print(f"  Obstáculos visuais encontrados: {len(visual_obstacles)}")
    except Exception as e:
        print(f"  [WARN] Falha ao carregar obstáculos visuais: {e}")
        visual_obstacles = []
    beams_found = beam_tracer.detect_beams(texts, all_lines_and_polys, visual_obstacles=visual_obstacles)
    print(f"  Beams detectados: {len(beams_found)}")

    # debug de um beam específico
    if debug_beam:
        for b in beams_found:
            if b.get("name") == debug_beam:
                classified = b.get("geometry", {}).get("classified", {})
                mbg = classified.get("merged_bottom_groups", [])
                mbl = classified.get("merged_bottom_lengths", [])
                sb = classified.get("seg_bottom", [])
                dt = b.get("geometry", {}).get("dimension_texts", [])
                print(f"\n  --- DEBUG {debug_beam} ---")
                print(f"  merged_bottom_groups: {len(mbg)}")
                print(f"  merged_bottom_lengths: {mbl}")
                print(f"  seg_bottom: {len(sb)}")
                print(f"  dimension_texts: {[t.get('text') for t in dt]}")
                for i, g in enumerate(mbg):
                    print(f"    group[{i}]: {len(g)} rects, len={mbl[i] if i<len(mbl) else '?'}")
                break
        else:
            print(f"\n  [WARN] Beam '{debug_beam}' não encontrado na análise.")


    # 4.8 Extrair Canais Globais DXF e Inicializar ChannelConfidenceScorer
    print("  Calculando pontuacoes de confianca de canais fisicos (ChannelConfidenceScorer)...")
    from src.core.beam_interpreters.global_channel_extractor import GlobalBeamChannelExtractor
    from src.core.beam_interpreters.channel_confidence_scorer import ChannelConfidenceScorer

    channel_extractor = GlobalBeamChannelExtractor()
    channel_mesh = channel_extractor.extract_channel_mesh(lines + polys, raw_texts=texts)
    confidence_scorer = ChannelConfidenceScorer()

    # 5. Processar cada beam FV e salvar no DB
    print("  Salvando resultados em beam_elements...")
    conn = sqlite3.connect(str(db_path))
    try:
        n_saved = 0
        for b in beams_found:
            name = b.get("name", "")
            # Excluir fragmentos L.* e F.*
            if re.match(r"^[LlFf]\.", name) or re.match(r"^[LF]V-", name):
                continue

            fv = process_beam_fv(b, spatial_index, visual_obstacles)

            # Avaliar score de confiança de cada segmento contra a malha de canais do DXF
            for seg in fv.get("segmentos_fundo", []):
                pts = seg.get("geometry", [])
                if len(pts) >= 2:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    s_bbox = (min(xs), min(ys), max(xs), max(ys))
                    s_width = float(seg.get("measure_width") or fv.get("h_n1") or 19.0)
                    s_is_h = bool(fv.get("is_horizontal", True))
                    c_res = confidence_scorer.score_segment(s_bbox, s_width, s_is_h, channel_mesh)
                    seg["channel_confidence"] = {
                        "score": c_res.confidence_score,
                        "status": c_res.status_flag,
                        "offset_cm": c_res.transverse_offset_cm,
                        "width_delta_cm": c_res.width_delta_cm,
                        "dim_text_dxf": c_res.dim_text_matched,
                    }

            campos = {
                "viga": name,
                "dim": fv["dim_text"],
                "segmentos_fundo": fv["segmentos_fundo"],
                "n_paineis_logicos": fv["panels_n1"],
                "comprimento_total_fundo": fv["comprimento_fundo"],
                "h_espessura": fv["h_n1"],
                "is_horizontal": fv.get("is_horizontal", True),
                "merged_groups_count": fv["merged_groups_count"],
                "merged_lengths_count": fv["merged_lengths_count"],
                "seg_bottom_raw_count": fv["seg_bottom_raw_count"],
            }

            upsert_beam_element_fv(conn, project_id, name, fv["panels_n1"], campos)
            n_saved += 1

        conn.commit()
        print(f"  Beam elements FV atualizados com Telemetria de Canais: {n_saved}")
    finally:
        conn.close()

    # 6. Render headless (limpo + vínculos) para inspeção visual
    try:
        from scripts.motor_fase4 import MotorFase4
        obra_path = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS") / obra_name
        m4 = MotorFase4(str(obra_path), pavimento=pav_filter or None)
        n_fv_json = m4._write_fv_json_from_beam_elements({})
        print(f"  JSON_Vigas_Fundo atualizados pelo SA: {n_fv_json}")
    except Exception as e:
        print(f"  [WARN] Propagacao FV para Fase-4/N3 falhou: {e}")

    # 6. Render headless (limpo + vinculos) para inspecao visual
    try:
        from scripts.fv_render_loop import render_pavimento
        render_dir = ROOT / "sandbox_fv_loop"
        prefix = f"fv_{obra_name}_{pav_filter or 'all'}".replace(" ", "_")
        pngs = render_pavimento(dxf_data, beams_found, render_dir, prefix=prefix)
        if pngs:
            print("\n  [Render visual]")
            print(f"    limpo:    {pngs.get('limpo')}")
            print(f"    vínculos: {pngs.get('vinculos')}  ({pngs.get('beams_desenhados')} vigas)")
    except Exception as e:
        print(f"  [WARN] Render visual falhou: {e}")

    # 7. fv_loop_runner comparação
    print("\n" + "=" * 60)
    print("  Rodando comparação FV (fv_loop_runner)...")
    print("=" * 60)
    import scripts.fv_loop_runner as fvr
    results = fvr.run(obra_name, pav_filter, db_path)
    return results


def main():
    parser = argparse.ArgumentParser(description="Análise Geral Headless — sem GUI")
    parser.add_argument("--obra", required=True, help="Nome da obra")
    parser.add_argument("--pav", default=None, help="Filtro parcial do pavimento (ex: 13)")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--debug-beam", default=None, help="Debug detalhado de um beam específico (ex: V302)")
    args = parser.parse_args()

    run(
        obra_name=args.obra,
        pav_filter=args.pav,
        db_path=Path(args.db),
        debug_beam=args.debug_beam,
    )


if __name__ == "__main__":
    main()
