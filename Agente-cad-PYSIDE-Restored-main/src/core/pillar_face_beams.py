"""Enriquecimento de faces de pilar com vigas (passa por esquina + chegadas).

Contrato cross-class (HANDOFF-PIL-LV-CROSSCLASS):
  - PIL é dono das faces; LV só lê.
  - passa_esq/dir = viga que PASSA (eixo continua nos dois lados do pilar).
  - para[] / v_ch* = viga que PARA (chegada no pilar).
  - dim do slot = seção B/H da viga, nunca nome de elemento.
"""
from __future__ import annotations

import copy
import re
from typing import Any


_SECTION_DIM_RE = re.compile(
    r"^\d+(?:[.,]\d+)?(?:\s*[/xX]\s*\d+(?:[.,]\d+)?)?$"
)
_NAME_LIKE_RE = re.compile(r"^(?:[PVLF]|VF|LV|FV)\d", re.I)


def is_beam_section_dim(txt: Any) -> bool:
    """True se texto parece seção (14/50, 20x60, 19) e não nome V/L/P."""
    s = str(txt or "").strip()
    if not s or _NAME_LIKE_RE.match(s):
        return False
    if re.fullmatch(r"[A-Za-z_./\-]+", s):
        return False
    return bool(_SECTION_DIM_RE.fullmatch(s))


def clean_beam_section_dim(txt: Any) -> str:
    s = str(txt or "").strip()
    return s if is_beam_section_dim(s) else ""


def beam_section_width(dim: Any) -> float | None:
    """Primeiro número de uma seção B/H (ex. "19/55" -> 19.0)."""
    cleaned = clean_beam_section_dim(dim)
    if not cleaned:
        return None
    match = re.match(r"^(\d+(?:[.,]\d+)?)", cleaned)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _format_section_number(value: Any) -> str:
    """Formata medida estrutural sem introduzir .0 no texto da ficha."""
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return ""
    if number <= 0:
        return ""
    return str(int(number)) if number.is_integer() else f"{number:g}"


def canonical_fundo_section_dim(beam: dict) -> str:
    """Obtém B/H da ficha geométrica do fundo da própria viga.

    Uma cota textual espacial pode ser uma dimensão de pilar ou de detalhe
    vizinho e ainda assim parecer uma seção (por exemplo ``100/19``). Já a
    ficha de ``links.viga_segs.seg_bottom`` pertence ao contorno identificado
    da própria viga; quando ela traz largura e altura, é a fonte canônica.
    """
    links = beam.get("links") if isinstance(beam.get("links"), dict) else {}
    viga_segs = links.get("viga_segs") if isinstance(links.get("viga_segs"), dict) else {}
    bottom = viga_segs.get("seg_bottom") if isinstance(viga_segs.get("seg_bottom"), list) else []
    candidates: list[str] = []
    for segment in bottom:
        if not isinstance(segment, dict):
            continue
        ficha = segment.get("ficha")
        if not isinstance(ficha, dict):
            continue
        width = _format_section_number(ficha.get("largura_total_fundo"))
        height = _format_section_number(ficha.get("altura_total"))
        if width and height:
            candidates.append(f"{width}/{height}")
    if candidates:
        # Segmentos de uma mesma viga normalmente repetem a seção. Em caso de
        # ficha incompleta, a moda evita eleger uma exceção isolada.
        return max(set(candidates), key=lambda value: (candidates.count(value), value))

    # Em algumas rotas a ficha espelho é preenchida depois da associação de
    # texto. O label `viga_fundo_seg_N_dim` continua sendo evidência direta do
    # próprio contorno (não é uma cota espacial solta), portanto é o fallback
    # canônico antes de qualquer fields.dimensao legado.
    for key, payload in links.items():
        if not re.fullmatch(r"viga_fundo_seg_\d+_dim", str(key)):
            continue
        labels = payload.get("label") if isinstance(payload, dict) else None
        for label in labels or []:
            text = label.get("text") if isinstance(label, dict) else None
            cleaned = clean_beam_section_dim(text)
            if cleaned and ("/" in cleaned or "x" in cleaned.lower()):
                candidates.append(cleaned)
    if not candidates:
        return ""
    # Segmentos de uma mesma viga normalmente repetem a seção. Em caso de
    # ficha incompleta, a moda evita eleger uma exceção isolada.
    return max(set(candidates), key=lambda value: (candidates.count(value), value))


def beam_axis_is_horizontal(beam: dict, *, fallback_bbox: tuple[float, float, float, float] | None = None) -> bool:
    """Lê o eixo da própria geometria de fundo antes do flag legado ``is_h``.

    ``is_h`` pode ter sido persistido quando o recorte ainda tinha poucos
    segmentos. ``bottom_runs`` e ``seg_bottom`` pertencem à geometria atual e
    por isso são a evidência espacial mais forte para PIL.
    """
    geo = beam.get("geometry") if isinstance(beam.get("geometry"), dict) else {}
    classified = geo.get("classified") if isinstance(geo.get("classified"), dict) else {}
    runs = classified.get("bottom_runs") if isinstance(classified.get("bottom_runs"), list) else []
    run_axes = [bool(run.get("is_h")) for run in runs if isinstance(run, dict) and "is_h" in run]
    if run_axes:
        return sum(run_axes) * 2 >= len(run_axes)

    horizontal_span = vertical_span = 0.0
    for line in classified.get("seg_bottom") or []:
        if not isinstance(line, (list, tuple)) or len(line) < 2:
            continue
        try:
            start, end = line[0], line[-1]
            dx = abs(float(end[0]) - float(start[0]))
            dy = abs(float(end[1]) - float(start[1]))
        except (TypeError, ValueError, IndexError):
            continue
        if dx >= dy:
            horizontal_span += dx
        else:
            vertical_span += dy
    if horizontal_span or vertical_span:
        return horizontal_span >= vertical_span

    if "is_h" in beam:
        return bool(beam.get("is_h"))
    if fallback_bbox:
        x0, y0, x1, y1 = fallback_bbox
        return (x1 - x0) >= (y1 - y0)
    return True


def reconcile_beam_fundo_facts(beams: list[dict]) -> int:
    """Repara fatos automáticos após a ficha FV estar completa.

    A análise cria primeiro os campos LV/textuais e só então fecha os
    contornos FV. Esta segunda passada fica no ponto temporal correto: usa a
    ficha FV já materializada para corrigir seção/altura/eixo automáticos antes
    de PIL consumir a viga e antes da persistência. Campos humanos validados
    permanecem imutáveis.
    """
    changed = 0
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        dim = canonical_fundo_section_dim(beam)
        if not dim:
            continue
        fields = beam.setdefault("fields", {})
        if not isinstance(fields, dict):
            continue
        validated = {
            str(value) for value in (beam.get("validated_fields") or [])
            if isinstance(value, str)
        }
        before = copy.deepcopy(beam)
        if "dimensao" not in validated:
            fields["dimensao"] = dim
            beam["dim"] = dim
        for field_name in list(fields):
            if (
                re.fullmatch(r"viga_fundo_seg_\d+_dim", str(field_name))
                and field_name not in validated
            ):
                fields[field_name] = dim
                beam[field_name] = dim
        nums = re.findall(r"\d+(?:[.,]\d+)?", dim)
        if len(nums) >= 2 and "altura_h1" not in validated:
            fields["altura_h1"] = float(nums[1].replace(",", "."))
            beam["altura_h1"] = fields["altura_h1"]
        axis = beam_axis_is_horizontal(beam)
        if "is_h" not in validated:
            beam["is_h"] = axis
        beam["_section_dimension_source"] = "fundo_ficha_geometrica"
        beam["_axis_source"] = "bottom_geometry"
        if beam != before:
            changed += 1
    return changed


_FACE_BEAM_SLOTS = (
    "v_passa_esq_n", "v_passa_esq_d", "v_passa_dir_n", "v_passa_dir_d",
    "v_ch1_n", "v_ch1_d", "v_ch2_n", "v_ch2_d", "v_ch3_n", "v_ch3_d",
    # Campos legados da mesma inferencia automatica: nao podem sobreviver a
    # uma leitura topologica que ja os desmentiu.
    "v_esq_n", "v_esq_d", "v_int_n", "v_int_d",
)


def _face_beam_field_is_validated(face: str, suffix: str, validated: set[str]) -> bool:
    """Aceita tanto o id plano quanto o id N1 completo de campo humano."""
    return suffix in validated or f"p_s{face}_{suffix}" in validated


def _face_beam_link_payload(value: str, evidence: dict | None = None) -> dict:
    """Cria o link N1 preservando tambem a geometria que decidiu o vinculo."""
    result = {
        "label": [{
            "text": value,
            "type": "text",
            "role": "label",
            "source": "pillar_face_beams_topology",
        }]
    }
    segments = (evidence or {}).get("evidence_segments")
    if isinstance(segments, list) and segments:
        result["geometry"] = copy.deepcopy(segments)
        result["evidence_source"] = "beam_bottom_geometry"
    return result


def materialize_face_beams_in_pillars(
    pillars: list[dict], report: dict, *, item_names: set[str] | None = None,
) -> int:
    """Reaplica ``face_beams`` apos o merge sem tocar decisao humana.

    O merge N1 preserva memoria, mas tambem pode restaurar slots automaticos de
    uma rodada antiga. A leitura topologica presente no relatorio e autoridade
    para passa/chega: limpa apenas esses slots nao validados e repopula os que
    a geometria atual confirma. ``item_names`` limita microciclos ao item.
    """
    if not isinstance(report, dict):
        return 0
    wanted = {str(v).strip().upper() for v in (item_names or set()) if str(v).strip()}
    report_by_name = {
        str(key or value.get("name") or "").strip().upper(): value
        for key, value in report.items() if isinstance(value, dict)
    }
    changed = 0
    for pillar in pillars or []:
        if not isinstance(pillar, dict):
            continue
        name = str(pillar.get("name") or pillar.get("key") or "").strip().upper()
        if wanted and name not in wanted:
            continue
        source = report_by_name.get(name)
        face_beams = source.get("face_beams") if isinstance(source, dict) else None
        # Sem uma leitura topologica nao apagamos memoria. Um dict vazio e'
        # valido: e' a conclusao de que nao ha viga vinculada naquela face.
        if not isinstance(face_beams, dict):
            continue

        before = copy.deepcopy(pillar)
        validated = {
            str(value) for value in (pillar.get("validated_fields") or [])
            if isinstance(value, str)
        }
        sides = pillar.setdefault("sides_data", {})
        if not isinstance(sides, dict):
            sides = {}
            pillar["sides_data"] = sides
        links = pillar.setdefault("links", {})
        if not isinstance(links, dict):
            links = {}
            pillar["links"] = links
        pillar["face_beams"] = copy.deepcopy(face_beams)

        for face in "ABCD":
            face_sides = sides.setdefault(face, {})
            if not isinstance(face_sides, dict):
                face_sides = {}
                sides[face] = face_sides
            face_slots = face_beams.get(face) or {}
            for suffix in _FACE_BEAM_SLOTS:
                if _face_beam_field_is_validated(face, suffix, validated):
                    continue
                field = f"p_s{face}_{suffix}"
                pillar.pop(field, None)
                face_sides.pop(suffix, None)
                links.pop(field, None)

            canonical: dict[str, str] = {}
            for source_slot, target_slot in (
                ("passa_esq", "v_passa_esq"),
                ("passa_dir", "v_passa_dir"),
            ):
                payload = face_slots.get(source_slot)
                if not isinstance(payload, dict):
                    continue
                beam_name = str(payload.get("name") or "").strip()
                if not beam_name:
                    continue
                canonical[f"{target_slot}_n"] = beam_name
                beam_dim = clean_beam_section_dim(payload.get("dim"))
                if beam_dim:
                    canonical[f"{target_slot}_d"] = beam_dim
            for index, payload in enumerate(face_slots.get("para") or [], 1):
                if index > 3 or not isinstance(payload, dict):
                    break
                beam_name = str(payload.get("name") or "").strip()
                if not beam_name:
                    continue
                canonical[f"v_ch{index}_n"] = beam_name
                beam_dim = clean_beam_section_dim(payload.get("dim"))
                if beam_dim:
                    canonical[f"v_ch{index}_d"] = beam_dim

            for suffix, value in canonical.items():
                if _face_beam_field_is_validated(face, suffix, validated):
                    continue
                field = f"p_s{face}_{suffix}"
                pillar[field] = value
                face_sides[suffix] = value
                source_slot = None
                if suffix.startswith("v_passa_esq"):
                    source_slot = face_slots.get("passa_esq")
                elif suffix.startswith("v_passa_dir"):
                    source_slot = face_slots.get("passa_dir")
                elif suffix.startswith("v_ch"):
                    match = re.match(r"v_ch(\d+)_", suffix)
                    index = int(match.group(1)) - 1 if match else -1
                    arrivals = face_slots.get("para") or []
                    if 0 <= index < len(arrivals):
                        source_slot = arrivals[index]
                links[field] = _face_beam_link_payload(value, source_slot)
        if pillar != before:
            changed += 1
    return changed


def _collect_xy_from_obj(obj: Any, out: list[tuple[float, float]]) -> None:
    if obj is None:
        return
    if isinstance(obj, (list, tuple)):
        if len(obj) >= 2 and all(isinstance(v, (int, float)) for v in obj[:2]):
            try:
                out.append((float(obj[0]), float(obj[1])))
            except (TypeError, ValueError):
                return
            return
        for item in obj:
            _collect_xy_from_obj(item, out)
        return
    if isinstance(obj, dict):
        for key in ("coords", "points", "poly", "segment", "segs", "xy"):
            if key in obj:
                _collect_xy_from_obj(obj[key], out)
        # classified often: list of segments [[x,y],[x,y]]
        for v in obj.values():
            if isinstance(v, (list, tuple, dict)):
                _collect_xy_from_obj(v, out)


def beam_bbox_from_entity(beam: dict) -> tuple[float, float, float, float] | None:
    """BBox (x0,y0,x1,y1) a partir de points, poly ou eixo de fundo.

    Classified colhe segs vizinhos (ruído). Preferir poly/points; senão
    **só** fundo/bottom da própria viga (eixo), expandido um pouco na
    transversão para gerar área de alinhamento de parede.
    """
    pts: list[tuple[float, float]] = []
    raw_pts = beam.get("points")
    if isinstance(raw_pts, (list, tuple)) and len(raw_pts) >= 3:
        _collect_xy_from_obj(raw_pts, pts)
        if len(pts) >= 3:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return (min(xs), min(ys), max(xs), max(ys))

    geo = beam.get("geometry") if isinstance(beam.get("geometry"), dict) else {}
    if isinstance(geo, dict):
        poly = geo.get("poly")
        if poly:
            poly_pts: list[tuple[float, float]] = []
            _collect_xy_from_obj(poly, poly_pts)
            if len(poly_pts) >= 3:
                xs = [p[0] for p in poly_pts]
                ys = [p[1] for p in poly_pts]
                return (min(xs), min(ys), max(xs), max(ys))

        classified = geo.get("classified")
        if isinstance(classified, dict):
            # Só polilinhas de fundo em 2D. NÃO usar bottom_runs /
            # merged_bottom_groups_coords: no SA eles guardam intervalos 1D
            # [y0,y1] ou [x0,x1] e corrompem o bbox (trocam eixos).
            axis_pts: list[tuple[float, float]] = []
            _collect_xy_from_obj(classified.get("seg_bottom"), axis_pts)
            if not axis_pts and classified.get("bottom_runs"):
                for run in classified.get("bottom_runs") or []:
                    if isinstance(run, dict):
                        is_h = bool(run.get("is_h"))
                        pos = run.get("pos") or [0.0, 0.0]
                        coords = run.get("coords") or []
                        for interval in coords:
                            if isinstance(interval, (list, tuple)) and len(interval) >= 2:
                                c0, c1 = float(interval[0]), float(interval[1])
                                if is_h:
                                    axis_pts.extend([(min(c0, c1), float(pos[1])), (max(c0, c1), float(pos[1]))])
                                else:
                                    axis_pts.extend([(float(pos[0]), min(c0, c1)), (float(pos[0]), max(c0, c1))])
            if len(axis_pts) >= 2:
                xs = [p[0] for p in axis_pts]
                ys = [p[1] for p in axis_pts]
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                # espessura mínima para wall-hit (~15–20 cm típico)
                pad = 12.0
                if (x1 - x0) <= (y1 - y0):
                    mid = (x0 + x1) / 2.0
                    x0, x1 = mid - pad, mid + pad
                else:
                    mid = (y0 + y1) / 2.0
                    y0, y1 = mid - pad, mid + pad
                return (x0, y0, x1, y1)

            # fallback: laterais só se fundo ausente
            side_pts: list[tuple[float, float]] = []
            for key in ("seg_side_a", "seg_side_b"):
                if key in classified:
                    _collect_xy_from_obj(classified[key], side_pts)
            if len(side_pts) >= 2:
                xs = [p[0] for p in side_pts]
                ys = [p[1] for p in side_pts]
                return (min(xs), min(ys), max(xs), max(ys))

    if len(pts) < 2:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


_RUN_MERGE_TOL = 25.0
_RUN_MIN_THICK = 5.0
_RUN_PAD = 12.0


def beam_runs_from_entity(beam: dict) -> list[tuple[float, float, float, float]]:
    """Corredores contíguos (um bbox por trecho físico) da viga.

    Uma viga multi-trecho colapsada num bbox único vira um corredor fictício
    que atravessa pilares que nenhum trecho toca (ex.: V328×P35 no 13_PAV,
    onde fragmentos ao sul deslocavam o eixo médio para cima da banda do
    pilar e criavam um falso "passa"). Cada grupo de segmentos de fundo
    próximos vira um corredor independente; passa/para e wall-hits devem
    ser avaliados corredor a corredor.
    """
    geo = beam.get("geometry") if isinstance(beam.get("geometry"), dict) else {}
    classified = geo.get("classified") if isinstance(geo, dict) else None
    seg_boxes: list[list[float]] = []
    if isinstance(classified, dict):
        for seg in classified.get("seg_bottom") or []:
            pts: list[tuple[float, float]] = []
            _collect_xy_from_obj(seg, pts)
            if len(pts) >= 2:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                seg_boxes.append([min(xs), min(ys), max(xs), max(ys)])
        if not seg_boxes and classified.get("bottom_runs"):
            pad = 12.0
            for run in classified.get("bottom_runs") or []:
                if isinstance(run, dict):
                    is_h = bool(run.get("is_h"))
                    pos = run.get("pos") or [0.0, 0.0]
                    coords = run.get("coords") or []
                    for interval in coords:
                        if isinstance(interval, (list, tuple)) and len(interval) >= 2:
                            c0, c1 = float(interval[0]), float(interval[1])
                            if is_h:
                                seg_boxes.append([min(c0, c1), float(pos[1]) - pad, max(c0, c1), float(pos[1]) + pad])
                            else:
                                seg_boxes.append([float(pos[0]) - pad, min(c0, c1), float(pos[0]) + pad, max(c0, c1)])
    if not seg_boxes:
        bbox = beam_bbox_from_entity(beam)
        return [tuple(bbox)] if bbox else []

    merged = True
    while merged:
        merged = False
        grouped: list[list[float]] = []
        for box in seg_boxes:
            for other in grouped:
                if (
                    box[0] - _RUN_MERGE_TOL <= other[2]
                    and box[2] + _RUN_MERGE_TOL >= other[0]
                    and box[1] - _RUN_MERGE_TOL <= other[3]
                    and box[3] + _RUN_MERGE_TOL >= other[1]
                ):
                    other[0] = min(other[0], box[0])
                    other[1] = min(other[1], box[1])
                    other[2] = max(other[2], box[2])
                    other[3] = max(other[3], box[3])
                    merged = True
                    break
            else:
                grouped.append(list(box))
        seg_boxes = grouped

    runs: list[tuple[float, float, float, float]] = []
    for x0, y0, x1, y1 in seg_boxes:
        # espessura mínima para wall-hit quando só o eixo foi extraído
        if (x1 - x0) <= (y1 - y0):
            if (x1 - x0) < _RUN_MIN_THICK:
                mid = (x0 + x1) / 2.0
                x0, x1 = mid - _RUN_PAD, mid + _RUN_PAD
        elif (y1 - y0) < _RUN_MIN_THICK:
            mid = (y0 + y1) / 2.0
            y0, y1 = mid - _RUN_PAD, mid + _RUN_PAD
        runs.append((x0, y0, x1, y1))
    return runs


def beam_section_dim(beam: dict) -> str:
    """Dimensão de seção preferida da viga (não cota linear longa)."""
    fields = beam.get("fields") if isinstance(beam.get("fields"), dict) else {}
    candidates = [
        # A ficha geométrica do fundo é vinculada ao próprio elemento. Deve
        # vencer campos globais antigos e textos próximos de outra entidade.
        canonical_fundo_section_dim(beam),
        fields.get("dimensao"),
        beam.get("dim"),
        fields.get("dim"),
        beam.get("viga_fundo_seg_1_dim"),
        beam.get("viga_a_seg_1_dim"),
        beam.get("viga_b_seg_1_dim"),
        (beam.get("_lv_cross_class") or {}).get("fundo_dim")
        if isinstance(beam.get("_lv_cross_class"), dict)
        else None,
    ]
    for c in candidates:
        cleaned = clean_beam_section_dim(c)
        if cleaned and ("/" in cleaned or "x" in cleaned.lower()):
            return cleaned
    for c in candidates:
        cleaned = clean_beam_section_dim(c)
        if cleaned:
            return cleaned
    return ""


def _beam_evidence_segments(beam: dict) -> list[dict]:
    """Extrai segmentos 2D compactos para o destaque do vinculo PIL<-viga."""
    geometry = beam.get("geometry") if isinstance(beam.get("geometry"), dict) else {}
    classified = (
        geometry.get("classified")
        if isinstance(geometry.get("classified"), dict)
        else {}
    )
    result: list[dict] = []
    for raw in classified.get("seg_bottom") or []:
        points: list[tuple[float, float]] = []
        _collect_xy_from_obj(raw, points)
        if len(points) < 2:
            continue
        result.append({
            "type": "line",
            "points": [[x, y] for x, y in points],
            "role": "beam_bottom_geometry",
            "source": "pillar_face_beams_topology",
        })
    return result


_BEAM_NAME_RE = re.compile(r"^(?:V|VF|F\.|LV|L\.)\s*[A-Z]?\d+", re.I)
_DIM_RE = re.compile(r"^\d+(?:[.,]\d+)?\s*[/xX]\s*\d+(?:[.,]\d+)?$")


def _norm_beam_label(raw: str) -> str:
    s = str(raw or "").strip().replace(" ", "")
    m = re.match(r"^F\.(.+?)(?:\.C)?(?:-\d+)?$", s, re.I)
    if m:
        return "VF" + re.sub(r"[^A-Za-z0-9]", "", m.group(1))
    m = re.match(r"^L\.(.+?)(?:\.[AB])?(?:-\d+)?$", s, re.I)
    if m:
        return "LV" + re.sub(r"[^A-Za-z0-9]", "", m.group(1))
    return s.upper()


def _iter_beam_text_items(beam: dict) -> list[dict]:
    """Textos e cotas ligados à entidade viga (geometry + raiz)."""
    items: list[dict] = []
    geo = beam.get("geometry") if isinstance(beam.get("geometry"), dict) else {}
    for key in ("texts", "dimension_texts"):
        for t in (geo.get(key) or []) + (beam.get(key) or []):
            if isinstance(t, dict):
                items.append(t)
    return items


def _collect_top_band_facts(beams: list) -> tuple[list[dict], list[dict]]:
    """Coleta cotas de seção e nomes de viga com posição (planta)."""
    dims: list[dict] = []
    names: list[dict] = []
    for beam in beams:
        if not isinstance(beam, dict):
            continue
        owner = str(beam.get("name") or "").strip()
        for t in _iter_beam_text_items(beam):
            raw = str(t.get("text") or "").strip()
            pos = t.get("pos") or []
            if len(pos) < 2:
                continue
            try:
                x, y = float(pos[0]), float(pos[1])
            except (TypeError, ValueError):
                continue
            if _DIM_RE.match(raw.replace(" ", "")):
                dims.append(
                    {
                        "dim": raw.replace(" ", "").replace(",", "."),
                        "x": x,
                        "y": y,
                        "owner": owner,
                    }
                )
            elif _BEAM_NAME_RE.match(raw):
                names.append(
                    {
                        "name": _norm_beam_label(raw),
                        "x": x,
                        "y": y,
                        "owner": owner or _norm_beam_label(raw),
                    }
                )
    return dims, names


def apply_face_c_top_multi_segment(
    face_beams: dict,
    *,
    beam_info: list,
    beams: list,
    px0: float,
    py0: float,
    px1: float,
    py1: float,
    horizontal: bool,
    tol: float = 15.0,
) -> None:
    """Preenche face C com passantes multi-segmento (CA/CB) na faixa do topo.

    Caso canônico (INTERPRETACAO-PILARES-ABCD, P2): viga E–W no topo do pilar
    vertical, com segmentos de profundidade diferentes à esq/dir (ex. 14/55 @ CA
    e 19/66 @ CB), mesma identidade (ex. VF301). Dualidade:
      passa C@CA ↔ chega A@AC
      passa C@CB ↔ chega B@BC

    Não hardcoda nomes de item; usa wall-align + cotas/nomes na faixa do topo.
    Modifica ``face_beams`` in-place.
    """
    if horizontal:
        # Pilar horizontal: face "topo longa" é B; multi-seg C/D fica para evolução.
        return
    if not isinstance(face_beams, dict) or "C" not in face_beams:
        return

    slots_c = face_beams["C"]
    # Se já há dois passantes distintos em C, não sobrescreve.
    if slots_c.get("passa_esq") and slots_c.get("passa_dir"):
        pe = (slots_c["passa_esq"] or {}).get("name")
        pd = (slots_c["passa_dir"] or {}).get("name")
        if pe and pd:
            # ainda assim garante cantos CA/CB
            slots_c["passa_esq"]["corner"] = "CA"
            slots_c["passa_dir"]["corner"] = "CB"
            return

    face_c_y = py1
    band = max(tol * 2.5, 40.0)  # faixa do topo (ex. 14 cm + folga de cota)
    cx = (px0 + px1) / 2.0
    dim_texts, name_texts = _collect_top_band_facts(beams)

    def _near_c_y(y: float) -> bool:
        return abs(y - face_c_y) <= band

    # Cotas na faixa do topo, lado esq (CA) e dir (CB)
    dims_ca = [
        d
        for d in dim_texts
        if _near_c_y(d["y"]) and d["x"] <= cx + tol and d["x"] >= px0 - 250.0
    ]
    dims_cb = [
        d
        for d in dim_texts
        if _near_c_y(d["y"]) and d["x"] >= cx - tol and d["x"] <= px1 + 250.0
    ]
    # Preferir cota mais próxima do canto AC / BC
    def _best_dim(cands: list[dict], tx: float, ty: float) -> dict | None:
        if not cands:
            return None
        return min(
            cands,
            key=lambda d: (d["x"] - tx) ** 2 + (d["y"] - ty) ** 2,
        )

    dim_ca = _best_dim(dims_ca, px0, face_c_y)
    dim_cb = _best_dim(dims_cb, px1, face_c_y)

    # Vigas H na faixa do topo: trecho a OESTE de A ou a LESTE de B
    # (não basta cruzar o interior do pilar — isso é chega simples, não multi-seg).
    west_hits: list[dict] = []
    east_hits: list[dict] = []
    for bi in beam_info:
        if not bi.get("is_h") or not bi.get("name"):
            continue
        for run in bi.get("runs") or []:
            rx0, ry0, rx1, ry1 = run
            in_y_band = min(ry0, ry1) - band <= face_c_y <= max(ry0, ry1) + band
            wall_c = abs(ry0 - face_c_y) < tol or abs(ry1 - face_c_y) < tol
            if not (in_y_band or wall_c):
                continue
            # Oeste: corpo do trecho predominantemente a oeste de A, tocando A
            west_body = rx1 <= px0 + tol and rx0 < px0 - 1.0
            west_touch = abs(rx1 - px0) < tol * 2 and rx0 < px0 - tol
            # Leste: predominantemente a leste de B
            east_body = rx0 >= px1 - tol and rx1 > px1 + 1.0
            east_touch = abs(rx0 - px1) < tol * 2 and rx1 > px1 + tol
            # Atravessa com gap no pilar (dois corredores ou um eixo longo)
            through = rx0 < px0 - tol and rx1 > px1 + tol
            if west_body or west_touch or through:
                west_hits.append({**bi, "_run": run, "_side": "west"})
            if east_body or east_touch or through:
                east_hits.append({**bi, "_run": run, "_side": "east"})

    def _beam_near_top(name: str) -> bool:
        """Owner de cota só vale se a viga for H e tiver trecho na faixa do topo do pilar."""
        if not name:
            return False
        for bi in beam_info:
            if bi.get("name") != name or not bi.get("is_h"):
                continue
            for run in bi.get("runs") or []:
                rx0, ry0, rx1, ry1 = run
                if not (min(ry0, ry1) - band <= face_c_y <= max(ry0, ry1) + band):
                    continue
                # trecho cruza a vizinhança X do pilar (não só outro vão distante)
                if rx1 >= px0 - 300.0 and rx0 <= px1 + 300.0:
                    return True
        return False

    def _pick_name(side: str, dim_hit: dict | None) -> str:
        tx = px0 if side == "west" else px1
        # 1) rótulo V/VF na faixa do topo (mais confiável que owner de cota compartilhada)
        near_names = [
            n
            for n in name_texts
            if _near_c_y(n["y"]) and abs(n["x"] - tx) < 400.0
        ]
        if near_names:
            best = min(near_names, key=lambda n: (n["x"] - tx) ** 2 + (n["y"] - face_c_y) ** 2)
            return best["name"]
        band_names = [n for n in name_texts if _near_c_y(n["y"])]
        if band_names:
            best = min(
                band_names,
                key=lambda n: abs(n["y"] - face_c_y) * 10 + abs(n["x"] - cx) * 0.02,
            )
            return best["name"]
        # 2) hit geométrico H no topo
        pool = west_hits if side == "west" else east_hits
        if pool:
            return str(pool[0].get("name") or "").strip()
        # 3) owner da cota só se a viga for realmente H na faixa deste pilar
        if dim_hit and dim_hit.get("owner") and _beam_near_top(str(dim_hit["owner"])):
            return str(dim_hit["owner"]).strip()
        return ""

    def _pick_dim(side: str, name: str) -> str:
        dim_hit = dim_ca if side == "west" else dim_cb
        if dim_hit and dim_hit.get("dim"):
            return clean_beam_section_dim(dim_hit["dim"]) or dim_hit["dim"]
        pool = west_hits if side == "west" else east_hits
        for h in pool:
            if h.get("name") == name and h.get("dim"):
                return str(h["dim"])
        # dim global da viga
        for bi in beam_info:
            if bi.get("name") == name and bi.get("dim"):
                return str(bi["dim"])
        return ""

    name_w = _pick_name("west", dim_ca)
    name_e = _pick_name("east", dim_cb)
    # Mesma viga nos dois lados quando um lado não tem nome
    if name_w and not name_e:
        name_e = name_w
    if name_e and not name_w:
        name_w = name_e
    # Se ambos vazios mas há cota + nome na faixa, usa o nome da faixa
    if not name_w and not name_e:
        band_names = [n for n in name_texts if _near_c_y(n["y"])]
        if band_names and (dim_ca or dim_cb or west_hits or east_hits):
            name_w = name_e = band_names[0]["name"]

    dim_w = _pick_dim("west", name_w) if name_w else ""
    dim_e = _pick_dim("east", name_e) if name_e else ""

    # Multi-segmento exige evidência nos DOIS lados (cota e/ou trecho).
    # Um único lado = chega simples (já coberta pelo fluxo para[]) — não forçar C.
    side_w = bool(dim_ca or west_hits)
    side_e = bool(dim_cb or east_hits)
    if not (side_w and side_e):
        return
    if not name_w and not name_e:
        return

    def _slot(name: str, dim: str, corner: str) -> dict:
        payload = {
            "name": name,
            "dim": dim or "",
            "corner": corner,
            "behavior": "passa",
            "source": "face_c_top_multi_segment",
        }
        # evidência da viga se existir
        for bi in beam_info:
            if bi.get("name") == name and bi.get("evidence_segments"):
                payload["evidence_segments"] = copy.deepcopy(bi["evidence_segments"])
                break
        return payload

    if name_w and not slots_c.get("passa_esq"):
        slots_c["passa_esq"] = _slot(name_w, dim_w, "CA")
    elif name_w and slots_c.get("passa_esq"):
        slots_c["passa_esq"]["corner"] = "CA"
        if dim_w and not slots_c["passa_esq"].get("dim"):
            slots_c["passa_esq"]["dim"] = dim_w

    if name_e and not slots_c.get("passa_dir"):
        # Se mesmo nome e mesmo dim do esq, ainda preenche dir com canto CB
        # (dois segmentos / duas direções).
        slots_c["passa_dir"] = _slot(name_e, dim_e or dim_w, "CB")
    elif name_e and slots_c.get("passa_dir"):
        slots_c["passa_dir"]["corner"] = "CB"
        if dim_e and not slots_c["passa_dir"].get("dim"):
            slots_c["passa_dir"]["dim"] = dim_e

    # Se só um slot preenchido e há cota no outro lado, espelha nome
    if slots_c.get("passa_esq") and not slots_c.get("passa_dir") and (dim_cb or east_hits):
        pe = slots_c["passa_esq"]
        slots_c["passa_dir"] = _slot(
            pe.get("name") or name_e or name_w,
            dim_e or pe.get("dim") or "",
            "CB",
        )
    if slots_c.get("passa_dir") and not slots_c.get("passa_esq") and (dim_ca or west_hits):
        pd = slots_c["passa_dir"]
        slots_c["passa_esq"] = _slot(
            pd.get("name") or name_w or name_e,
            dim_w or pd.get("dim") or "",
            "CA",
        )

    # Dualidade leve em A/B: chega AC/BC se ainda vazio de chega para esse nome
    # (slots para[] nas longas; passa_esq/dir de A/B da viga de baixo ficam intactos)
    for long_face, corner, c_slot in (
        ("A", "AC", "passa_esq"),
        ("B", "BC", "passa_dir"),
    ):
        src = slots_c.get(c_slot)
        if not isinstance(src, dict) or not src.get("name"):
            continue
        nm = src["name"]
        fl = face_beams.get(long_face) or {}
        already = (
            (fl.get("passa_esq") or {}).get("name") == nm
            or (fl.get("passa_dir") or {}).get("name") == nm
            or any(p.get("name") == nm for p in (fl.get("para") or []))
            or any(p.get("name") == nm for p in (fl.get("interior") or []))
        )
        # Se a viga de baixo já ocupa passa A/B (interior D), ainda podemos
        # anotar chega no canto de topo em para[] — identidade diferente do papel.
        if any(p.get("name") == nm and p.get("corner") == corner for p in (fl.get("para") or [])):
            continue
        # Não confundir com V312 interior: só adiciona se dim/source top
        if src.get("source") != "face_c_top_multi_segment" and already:
            continue
        if len(fl.get("para") or []) >= 3:
            continue
        fl.setdefault("para", []).append(
            {
                "name": nm,
                "dim": src.get("dim") or "",
                "corner": corner,
                "behavior": "para",
                "source": "face_c_top_multi_segment_dual",
            }
        )


def enrich_pillar_report_with_beams(report: dict, beams: list) -> None:
    """
    Classifica cada entrada 'lajes' do pilar como 'laje', 'viga' ou 'both',
    segundo os 5 casos de INTERPRETACAO-PILARES-ABCD.md.

    Modifica report in-place. Adiciona 'content_type' e 'viga' a cada entrada.
    Também cria entradas puras de viga para faces sem laje mas com parede alinhada.

    Novos slots por face (UI SA):
      - passa_esq / passa_dir — só behavior=passa, 1 viga distinta por canto
      - para[] — até 3 chegadas (behavior=para), não misturar com passa
    """
    if not report or not beams:
        return

    from src.core.beam_interpreters import (
        PilarComVigaParaInterpreter,
        PilarComVigaPassaInterpreter,
    )

    # 12–15 cm: cobre espessura de viga + pad do bbox offline (seg_bottom)
    TOL_ALIGN = 15.0
    MIN_OV = 1.0
    pilar_para = PilarComVigaParaInterpreter()
    pilar_passa = PilarComVigaPassaInterpreter()

    # Cantos: (esq, dir) — alinhado a aberturas NOVA / INTERPRETACAO-ABCD
    # Vertical: A oeste (esq=AC topo, dir=AD base); B leste (esq=BD base, dir=BC topo)
    # Horizontal: A sul E→W (esq=AC oeste, dir=AD leste); B norte E→W (esq=BC oeste, dir=BD leste)
    FACE_CORNERS_V = {
        "A": ("AC", "AD"),
        "B": ("BD", "BC"),
        "C": ("CA", "CB"),
        "D": ("DA", "DB"),
    }
    FACE_CORNERS_H = {
        "A": ("AC", "AD"),  # sul: oeste→leste
        "B": ("BC", "BD"),  # norte: oeste→leste (NÃO BD/BC do vertical)
        "C": ("CA", "CB"),  # oeste: sul→norte
        "D": ("DA", "DB"),  # leste: sul→norte
    }

    def _arrival_corner(
        fid: str,
        face_coords: dict,
        view: dict,
        ov: float,
    ) -> str:
        """Slot da chegada pela geometria: canto FX real ou central FF.

        O canto não é convenção visual esq/dir: é a extremidade curta que o
        trecho de chegada cobre. Cobertura dominante da face = chegada
        central (engole a face), como a viga que termina de frente.
        """
        axis, _fixed, r0, r1 = face_coords[fid]
        face_len = max(r1 - r0, 1e-6)
        if ov / face_len >= 0.6:
            return f"{fid}{fid}"
        if axis == "H":
            lo, hi = view["x0"], view["x1"]
        else:
            lo, hi = view["y0"], view["y1"]
        mid = (max(r0, lo) + min(r1, hi)) / 2.0
        third = face_len / 3.0
        if mid <= r0 + third:
            coord = r0
        elif mid >= r1 - third:
            coord = r1
        else:
            return f"{fid}{fid}"
        other_axis = "V" if axis == "H" else "H"
        for ofid, (oaxis, ofixed, _o0, _o1) in face_coords.items():
            if oaxis == other_axis and abs(ofixed - coord) < 1e-6:
                return f"{fid}{ofid}"
        return f"{fid}{fid}"

    def _corner_side(
        fid: str,
        axis: str,
        fixed: float,
        r0: float,
        r1: float,
        bi: dict,
    ) -> str:
        """esq|dir conforme qual extremo da face a viga cobre mais."""
        if axis == "H":
            mid = (max(r0, bi["x0"]) + min(r1, bi["x1"])) / 2.0
            return "esq" if mid <= (r0 + r1) / 2.0 else "dir"
        mid = (max(r0, bi["y0"]) + min(r1, bi["y1"])) / 2.0
        mid_face = (r0 + r1) / 2.0
        if fid == "A":
            return "esq" if mid >= mid_face else "dir"
        if fid == "B":
            return "esq" if mid <= mid_face else "dir"
        return "esq" if mid <= mid_face else "dir"

    beam_info = []
    for beam in beams:
        if not isinstance(beam, dict):
            continue
        bbox = beam_bbox_from_entity(beam)
        if not bbox:
            continue
        x0, y0, x1, y1 = bbox
        bw, bh = x1 - x0, y1 - y0
        is_h = beam_axis_is_horizontal(beam, fallback_bbox=(x0, y0, x1, y1))
        runs = beam_runs_from_entity(beam) or [(x0, y0, x1, y1)]
        beam_info.append(
            {
                "name": str(beam.get("name") or "").strip(),
                "dim": beam_section_dim(beam),
                "x0": x0,
                "x1": x1,
                "y0": y0,
                "y1": y1,
                "is_h": is_h,
                "runs": runs,
                "evidence_segments": _beam_evidence_segments(beam),
            }
        )

    def _run_view(bi: dict, run: tuple[float, float, float, float]) -> dict:
        """Projeção do vínculo no corredor: coords e eixo do trecho, não do todo."""
        rx0, ry0, rx1, ry1 = run
        run_is_h = bool(bi["is_h"])
        return {**bi, "x0": rx0, "y0": ry0, "x1": rx1, "y1": ry1,
                "is_h": run_is_h}

    for _nm, entry in report.items():
        pts = entry.get("points") or []
        if not pts:
            continue
        try:
            pxs = [float(p[0]) for p in pts]
            pys = [float(p[1]) for p in pts]
        except Exception:
            continue
        px0, px1 = min(pxs), max(pxs)
        py0, py1 = min(pys), max(pys)
        pw, ph = px1 - px0, py1 - py0
        horizontal = pw >= ph
        pillar_bbox = (px0, py0, px1, py1)

        beam_relations = []
        for bi in beam_info:
            # A relação é do TRECHO com o pilar, não do elemento inteiro:
            # a mesma viga pode passar por um pilar e parar em outro, e o
            # bbox global de trechos disjuntos não representa viga nenhuma.
            best_relation = None
            for run in bi["runs"]:
                view = _run_view(bi, run)
                run_bbox = (view["x0"], view["y0"], view["x1"], view["y1"])
                # passa tem prioridade semântica (atravessa); senão para (termina)
                if pilar_passa.matches(
                    pillar_bbox, run_bbox, view["is_h"], TOL_ALIGN
                ):
                    best_relation = {**view, "behavior": "passa"}
                    break
                if pilar_para.matches(
                    pillar_bbox, run_bbox, view["is_h"], TOL_ALIGN
                ) and best_relation is None:
                    best_relation = {**view, "behavior": "para"}
            if best_relation:
                beam_relations.append(best_relation)

        entry[pilar_para.contract.output_slot] = [
            {"name": bi["name"], "dim": bi["dim"]}
            for bi in beam_relations
            if bi["behavior"] == "para" and bi["name"]
        ]
        entry[pilar_passa.contract.output_slot] = [
            {"name": bi["name"], "dim": bi["dim"]}
            for bi in beam_relations
            if bi["behavior"] == "passa" and bi["name"]
        ]

        if horizontal:
            face_coords = {
                "A": ("H", py0, px0, px1),
                "B": ("H", py1, px0, px1),
                "C": ("V", px0, py0, py1),
                "D": ("V", px1, py0, py1),
            }
        else:
            face_coords = {
                "A": ("V", px0, py0, py1),
                "B": ("V", px1, py0, py1),
                "C": ("H", py1, px0, px1),
                "D": ("H", py0, px0, px1),
            }

        # hits: list of (bi, corner_side 'esq'|'dir', ov_len)
        face_hits: dict = {f: [] for f in face_coords}
        face_inside: dict = {f: False for f in face_coords}

        for bi in beam_info:
            hit_faces: set[str] = set()
            for run in bi["runs"]:
                view = _run_view(bi, run)
                inside = (
                    view["x0"] <= px0 + TOL_ALIGN
                    and view["x1"] >= px1 - TOL_ALIGN
                    and view["y0"] <= py0 + TOL_ALIGN
                    and view["y1"] >= py1 - TOL_ALIGN
                )
                for fid, (axis, fixed, r0, r1) in face_coords.items():
                    if fid in hit_faces:
                        continue
                    if inside:
                        side = _corner_side(fid, axis, fixed, r0, r1, view)
                        face_hits[fid].append((view, side, 999.0))
                        face_inside[fid] = True
                        hit_faces.add(fid)
                        continue
                    if axis == "H":
                        for wy in (view["y0"], view["y1"]):
                            if abs(fixed - wy) < TOL_ALIGN:
                                ov = min(r1, view["x1"]) - max(r0, view["x0"])
                                if ov > MIN_OV:
                                    side = _corner_side(
                                        fid, axis, fixed, r0, r1, view
                                    )
                                    face_hits[fid].append((view, side, ov))
                                    hit_faces.add(fid)
                                    break
                    else:
                        for wx in (view["x0"], view["x1"]):
                            if abs(fixed - wx) < TOL_ALIGN:
                                ov = min(r1, view["y1"]) - max(r0, view["y0"])
                                if ov > MIN_OV:
                                    side = _corner_side(
                                        fid, axis, fixed, r0, r1, view
                                    )
                                    face_hits[fid].append((view, side, ov))
                                    hit_faces.add(fid)
                                    break

        # face_beams: passa só behavior=passa; chegadas = behavior=para
        FACE_CORNERS = FACE_CORNERS_H if horizontal else FACE_CORNERS_V
        face_beams: dict = {}
        for fid in face_coords:
            c_esq, c_dir = FACE_CORNERS[fid]
            face_beams[fid] = {
                "passa_esq": None,
                "passa_dir": None,
                "corner_esq": c_esq,
                "corner_dir": c_dir,
                "para": [],
                "interior": [],
            }

        # Index behavior by name
        behavior_by_name = {
            br["name"]: br["behavior"]
            for br in beam_relations
            if br.get("name")
        }

        for fid, (axis, fixed, r0, r1) in face_coords.items():
            c_esq, c_dir = FACE_CORNERS[fid]
            # candidatos passa com hit nesta face, ordenados por overlap
            passa_hits = []
            for bi, side, ov in face_hits.get(fid, []):
                nm = bi.get("name") or ""
                if not nm:
                    continue
                if behavior_by_name.get(nm) != "passa":
                    continue
                passa_hits.append((bi, side, ov))
            passa_hits.sort(key=lambda t: -t[2])

            used_names: set[str] = set()
            for bi, side, ov in passa_hits:
                nm = bi["name"]
                if nm in used_names:
                    continue
                slot = "passa_esq" if side == "esq" else "passa_dir"
                # se o canto preferido ocupado, tenta o outro; nunca duplicar nome
                if face_beams[fid][slot] is not None:
                    alt = "passa_dir" if slot == "passa_esq" else "passa_esq"
                    if face_beams[fid][alt] is None:
                        slot = alt
                    else:
                        continue
                # se o outro canto já tem ESTE nome, skip
                other = "passa_dir" if slot == "passa_esq" else "passa_esq"
                other_nm = (face_beams[fid].get(other) or {}).get("name")
                if other_nm == nm:
                    continue
                face_beams[fid][slot] = {
                    "name": nm,
                    "dim": bi["dim"],
                    "corner": c_esq if slot == "passa_esq" else c_dir,
                    **({"evidence_segments": copy.deepcopy(bi["evidence_segments"])}
                       if bi.get("evidence_segments") else {}),
                }
                used_names.add(nm)

        # Uma viga que termina na face curta ainda alinha suas duas paredes às
        # faces longas adjacentes quando possui a mesma espessura transversal
        # do pilar. No painel A/B isso é uma abertura de canto da "viga que
        # para"; o slot físico continua sendo passa_esq/dir, mas preservamos o
        # comportamento no payload para não confundi-la com viga atravessante.
        # Ex.: término em C -> cantos AC e BC; término em D -> AD e BD.
        for br in beam_relations:
            if (
                br["behavior"] != "para"
                or not br.get("name")
                or bool(br["is_h"]) != bool(horizontal)
            ):
                continue
            if horizontal:
                walls_align = (
                    abs(br["y0"] - py0) < TOL_ALIGN
                    and abs(br["y1"] - py1) < TOL_ALIGN
                )
                short_distances = {
                    "C": min(abs(br["x0"] - px0), abs(br["x1"] - px0)),
                    "D": min(abs(br["x0"] - px1), abs(br["x1"] - px1)),
                }
            else:
                walls_align = (
                    abs(br["x0"] - px0) < TOL_ALIGN
                    and abs(br["x1"] - px1) < TOL_ALIGN
                )
                short_distances = {
                    "C": min(abs(br["y0"] - py1), abs(br["y1"] - py1)),
                    "D": min(abs(br["y0"] - py0), abs(br["y1"] - py0)),
                }
            terminal_face = min(short_distances, key=short_distances.get)
            if not walls_align or short_distances[terminal_face] >= TOL_ALIGN:
                continue

            # Caso 4 (INTERPRETACAO-PILARES-ABCD.md): quando a largura da
            # propria viga (dado confiavel, direto do "dim" da ficha, sem
            # depender de segmentos laterais que podem estar desatualizados)
            # aproxima a espessura transversal do pilar, a face curta onde
            # ela termina fica DENTRO do corpo da viga — nao e uma chegada
            # perpendicular (nenhuma viga cruza aquela face) nem uma face
            # livre. Achado do dono (P35: V308 19/55 termina no canto C;
            # 19 ~= espessura do pilar (19cm) -> C e interior, nao chegada).
            short_dim = ph if horizontal else pw
            beam_width = beam_section_width(br.get("dim"))
            is_interior = (
                beam_width is not None
                and abs(beam_width - short_dim) < TOL_ALIGN
            )
            if is_interior:
                face_beams[terminal_face]["interior"].append({
                    "name": br["name"],
                    "dim": br["dim"],
                    **({"evidence_segments": copy.deepcopy(br["evidence_segments"])}
                       if br.get("evidence_segments") else {}),
                })

            for long_face in ("A", "B"):
                if is_interior:
                    pilar_lajes = entry.get("lajes") or []
                    lajes_on_face = [l for l in pilar_lajes if l.get("lado") == long_face]
                    if lajes_on_face:
                        continue

                corner = f"{long_face}{terminal_face}"
                corner_esq, corner_dir = FACE_CORNERS[long_face]
                slot = "passa_esq" if corner == corner_esq else "passa_dir"
                current = face_beams[long_face].get(slot)
                if current and current.get("name") != br["name"]:
                    continue
                face_beams[long_face][slot] = {
                    "name": br["name"],
                    "dim": br["dim"],
                    "corner": corner,
                    "behavior": "para",
                    **({"evidence_segments": copy.deepcopy(br["evidence_segments"])}
                       if br.get("evidence_segments") else {}),
                }

            # Passante sem hit de parede nesta face: não força (outra face cuida)

        # Chegadas (para): vigas com hit em qualquer face onde ainda não estejam vinculadas (passa/interior/para)
        for br in beam_relations:
            if not br.get("name"):
                continue
            for fid, hits in face_hits.items():
                best_bi, best_side, best_ov = None, "esq", -1.0
                for bi, side, ov in hits:
                    if bi["name"] == br["name"] and ov > best_ov:
                        best_ov = ov
                        best_side = side
                        best_bi = bi
                if best_bi is None or best_ov <= MIN_OV:
                    continue

                already_linked = (
                    (face_beams[fid].get("passa_esq") or {}).get("name") == br["name"]
                    or (face_beams[fid].get("passa_dir") or {}).get("name") == br["name"]
                    or any(p["name"] == br["name"] for p in face_beams[fid]["para"])
                    or any(p["name"] == br["name"] for p in face_beams[fid]["interior"])
                )
                if already_linked:
                    continue

                if len(face_beams[fid]["para"]) < 3:
                    corner = _arrival_corner(fid, face_coords, best_bi, best_ov)
                    face_beams[fid]["para"].append(
                        {
                            "name": br["name"],
                            "dim": br["dim"],
                            "corner": corner,
                            **({"evidence_segments": copy.deepcopy(br["evidence_segments"])}
                               if br.get("evidence_segments") else {}),
                        }
                    )

        # "C/D sempre passa" (guia, tabela Viga passante): uma viga cujo
        # eixo e perpendicular as faces longas (ex. V328, vertical, num
        # pilar horizontal) pode nao atravessar a faixa do pilar no eixo
        # A/B — nem "passa" nem "para" nesse sentido — mas a PROPRIA PAREDE
        # dela ainda tampa fisicamente a face curta quando coincide com o
        # plano de C ou D. Sem isso a face curta ficava vazia mesmo com a
        # parede exatamente alinhada (achado do dono: motor puro nao
        # persistia nada em D, só a ficha sabia via segmentos frageis).
        for fid in ("C", "D"):
            slots = face_beams[fid]
            if slots["passa_esq"] or slots["passa_dir"] or slots["para"] or slots["interior"]:
                continue
            axis, fixed, r0, r1 = face_coords[fid]
            for bi in beam_info:
                if bool(bi["is_h"]) == bool(horizontal):
                    continue  # eixo paralelo a A/B: já coberto acima
                if axis == "V":
                    wall_lo, wall_hi = bi["x0"], bi["x1"]
                    span_lo, span_hi = bi["y0"], bi["y1"]
                else:
                    wall_lo, wall_hi = bi["y0"], bi["y1"]
                    span_lo, span_hi = bi["x0"], bi["x1"]
                touches_wall = (
                    abs(wall_lo - fixed) < TOL_ALIGN or abs(wall_hi - fixed) < TOL_ALIGN
                )
                adjacent = span_hi >= r0 - TOL_ALIGN and span_lo <= r1 + TOL_ALIGN
                if touches_wall and adjacent and bi.get("name"):
                    slots["passa_esq"] = {
                        "name": bi["name"],
                        "dim": bi["dim"],
                        "corner": slots["corner_esq"],
                        "behavior": "passa",
                        **({"evidence_segments": copy.deepcopy(bi["evidence_segments"])}
                           if bi.get("evidence_segments") else {}),
                    }
                    break

        # Face C multi-segmento (topo E–W): CA/CB com dims locais + dualidade AC/BC
        apply_face_c_top_multi_segment(
            face_beams,
            beam_info=beam_info,
            beams=beams,
            px0=px0,
            py0=py0,
            px1=px1,
            py1=py1,
            horizontal=horizontal,
            tol=TOL_ALIGN,
        )

        entry["face_beams"] = face_beams

        laje_entries = entry.get("lajes", [])
        covered: set = set()

        for le in laje_entries:
            fid = le.get("side", "NULO")
            covered.add(fid)
            hits = [h[0] for h in face_hits.get(fid, [])]
            is_long_face = fid in ("A", "B")
            has_laje = bool(le.get("laje"))
            if not hits:
                le["content_type"] = "laje"
            elif face_inside.get(fid) and not (is_long_face and has_laje):
                le["content_type"] = "viga"
                le["viga"] = {"name": hits[0]["name"], "dim": hits[0]["dim"]}
            elif is_long_face and has_laje:
                le["content_type"] = "both"
                le["viga"] = {"name": hits[0]["name"], "dim": hits[0]["dim"]}
            else:
                le["content_type"] = "viga"
                le["viga"] = {"name": hits[0]["name"], "dim": hits[0]["dim"]}

        for fid, hits in face_hits.items():
            if fid in covered or not hits:
                continue
            bi0 = hits[0][0]
            laje_entries.append(
                {
                    "laje": None,
                    "side": fid,
                    "face": "VIGA",
                    "content_type": "viga",
                    "viga": {"name": bi0["name"], "dim": bi0["dim"]},
                    "source": "beam_wall_alignment",
                }
            )

        entry["lajes"] = laje_entries
