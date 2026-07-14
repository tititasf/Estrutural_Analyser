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
    FACE_CORNERS = {
        "A": ("AC", "AD"),
        "B": ("BD", "BC"),
        "C": ("CA", "CB"),
        "D": ("DA", "DB"),
    }

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
        beam_info.append(
            {
                "name": str(beam.get("name") or "").strip(),
                "dim": beam_section_dim(beam),
                "x0": x0,
                "x1": x1,
                "y0": y0,
                "y1": y1,
                "is_h": is_h,
                "evidence_segments": _beam_evidence_segments(beam),
            }
        )

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
            beam_bbox = (bi["x0"], bi["y0"], bi["x1"], bi["y1"])
            relation = None
            # passa tem prioridade semântica (atravessa); senão para (termina)
            if pilar_passa.matches(
                pillar_bbox, beam_bbox, bi["is_h"], TOL_ALIGN
            ):
                relation = "passa"
            elif pilar_para.matches(
                pillar_bbox, beam_bbox, bi["is_h"], TOL_ALIGN
            ):
                relation = "para"
            if relation:
                beam_relations.append({**bi, "behavior": relation})

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
            inside = (
                bi["x0"] <= px0 + TOL_ALIGN
                and bi["x1"] >= px1 - TOL_ALIGN
                and bi["y0"] <= py0 + TOL_ALIGN
                and bi["y1"] >= py1 - TOL_ALIGN
            )
            for fid, (axis, fixed, r0, r1) in face_coords.items():
                if inside:
                    side = _corner_side(fid, axis, fixed, r0, r1, bi)
                    face_hits[fid].append((bi, side, 999.0))
                    face_inside[fid] = True
                    continue
                if axis == "H":
                    for wy in (bi["y0"], bi["y1"]):
                        if abs(fixed - wy) < TOL_ALIGN:
                            ov = min(r1, bi["x1"]) - max(r0, bi["x0"])
                            if ov > MIN_OV:
                                side = _corner_side(fid, axis, fixed, r0, r1, bi)
                                face_hits[fid].append((bi, side, ov))
                                break
                else:
                    for wx in (bi["x0"], bi["x1"]):
                        if abs(fixed - wx) < TOL_ALIGN:
                            ov = min(r1, bi["y1"]) - max(r0, bi["y0"])
                            if ov > MIN_OV:
                                side = _corner_side(fid, axis, fixed, r0, r1, bi)
                                face_hits[fid].append((bi, side, ov))
                                break

        # face_beams: passa só behavior=passa; chegadas = behavior=para
        face_beams: dict = {}
        for fid in face_coords:
            c_esq, c_dir = FACE_CORNERS[fid]
            face_beams[fid] = {
                "passa_esq": None,
                "passa_dir": None,
                "corner_esq": c_esq,
                "corner_dir": c_dir,
                "para": [],
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
            for long_face in ("A", "B"):
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

        # Chegadas (para): NÃO entram em passa_*; até 3 por face
        for br in beam_relations:
            if br["behavior"] != "para" or not br.get("name"):
                continue
            already_para = any(
                any(p["name"] == br["name"] for p in face_beams[f]["para"])
                for f in face_beams
            )
            if already_para:
                continue
            # melhor face = maior overlap de hit; senão face A
            best_f, best_ov, best_side = None, -1.0, "esq"
            for fid, hits in face_hits.items():
                for bi, side, ov in hits:
                    if bi["name"] == br["name"] and ov > best_ov:
                        best_ov = ov
                        best_f = fid
                        best_side = side
            if best_f is None:
                # sem wall hit: escolhe face cujo fixed está mais perto do endpoint
                best_f = "A"
                best_side = "esq"
            if len(face_beams[best_f]["para"]) >= 3:
                # tenta outra face com espaço
                for fid in face_coords:
                    if len(face_beams[fid]["para"]) < 3:
                        best_f = fid
                        break
            if len(face_beams[best_f]["para"]) < 3:
                c_esq, c_dir = FACE_CORNERS[best_f]
                face_beams[best_f]["para"].append(
                    {
                        "name": br["name"],
                        "dim": br["dim"],
                        "corner": c_esq if best_side == "esq" else c_dir,
                        **({"evidence_segments": copy.deepcopy(br["evidence_segments"])}
                           if br.get("evidence_segments") else {}),
                    }
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
