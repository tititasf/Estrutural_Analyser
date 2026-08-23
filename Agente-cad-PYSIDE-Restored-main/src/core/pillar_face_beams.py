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


def _traced_runs(beam: dict) -> list[tuple[float, float, float, float]]:
    """Corredores do traçador, ignorando o reparo pelo par de paredes."""
    sem_reparo = {k: v for k, v in beam.items() if k != "_recovered_corridor"}
    return beam_runs_from_entity(sem_reparo)


#: Folga (cm) para casar a separação de duas paredes com a seção declarada.
_WALL_PAIR_TOL = 3.0


def _merge_spans(
    spans: list[tuple[float, float]], gap: float = 1.0,
) -> list[tuple[float, float]]:
    ordenados = sorted(spans)
    saida: list[list[float]] = []
    for lo, hi in ordenados:
        if saida and lo <= saida[-1][1] + gap:
            saida[-1][1] = max(saida[-1][1], hi)
        else:
            saida.append([lo, hi])
    return [(lo, hi) for lo, hi in saida]


def runs_from_parallel_walls(
    seg_boxes: list[list[float]],
    *,
    horizontal: bool,
    width: float | None,
    tol: float = _WALL_PAIR_TOL,
) -> list[tuple[float, float, float, float]]:
    """Corredores formados pelas duas paredes **paralelas ao eixo** da viga.

    O agrupamento por proximidade colapsa num bbox único tudo que estiver
    perto, inclusive segmento de outra viga que encosta na ponta: `V329`
    (vertical, 19 cm) carregava dois trechos horizontais da `V304` e saía com
    68 cm de espessura. Parede de viga é paralela ao eixo dela; o resto é
    tampa ou vizinha.

    Quando só uma parede foi traçada, a **tampa** perpendicular do tamanho da
    seção diz onde está a outra.
    """
    if not seg_boxes or not width or width <= 0:
        return []
    paredes: dict[float, list[tuple[float, float]]] = {}
    tampas: list[tuple[float, float]] = []
    for x0, y0, x1, y1 in seg_boxes:
        largura_x, largura_y = x1 - x0, y1 - y0
        paralelo = largura_x >= largura_y if horizontal else largura_y >= largura_x
        if paralelo:
            coord = (y0 + y1) / 2.0 if horizontal else (x0 + x1) / 2.0
            span = (x0, x1) if horizontal else (y0, y1)
            chave = next(
                (k for k in paredes if abs(k - coord) <= tol), round(coord, 3),
            )
            paredes.setdefault(chave, []).append(span)
            continue
        transversal = (y0, y1) if horizontal else (x0, x1)
        if abs((transversal[1] - transversal[0]) - width) <= tol:
            tampas.append(transversal)

    # Duas paredes **desenhadas**. Inferir a segunda pela tampa foi medido e
    # revertido: numa viga que corre rente a uma fileira de pilares, o que
    # parece tampa é a aresta lateral do pilar, e o corredor sai deslocado
    # meia seção (`VF202` no 13_PAV: −21 células).
    coords = sorted(paredes)
    corredores: list[tuple[float, float, float, float]] = []
    for i, lo in enumerate(coords):
        for hi in coords[i + 1:]:
            if abs((hi - lo) - width) > tol:
                continue
            spans_lo = _merge_spans(paredes.get(lo) or [])
            spans_hi = _merge_spans(paredes.get(hi) or [])
            for a0, a1 in spans_lo or spans_hi:
                for b0, b1 in spans_hi or spans_lo:
                    i0, i1 = max(a0, b0), min(a1, b1)
                    if i1 - i0 <= tol:
                        continue
                    corredores.append(
                        (i0, lo, i1, hi) if horizontal else (lo, i0, hi, i1)
                    )
    return _merge_spans_boxes(corredores)


def _merge_spans_boxes(
    boxes: list[tuple[float, float, float, float]],
) -> list[tuple[float, float, float, float]]:
    saida: list[list[float]] = []
    for x0, y0, x1, y1 in sorted(boxes):
        for outro in saida:
            if (
                x0 <= outro[2] + 1.0 and x1 >= outro[0] - 1.0
                and y0 <= outro[3] + 1.0 and y1 >= outro[1] - 1.0
            ):
                outro[0] = min(outro[0], x0)
                outro[1] = min(outro[1], y0)
                outro[2] = max(outro[2], x1)
                outro[3] = max(outro[3], y1)
                break
        else:
            saida.append([x0, y0, x1, y1])
    return [tuple(b) for b in saida]


def beam_runs_from_entity(beam: dict) -> list[tuple[float, float, float, float]]:
    """Corredores contíguos (um bbox por trecho físico) da viga.

    Uma viga multi-trecho colapsada num bbox único vira um corredor fictício
    que atravessa pilares que nenhum trecho toca (ex.: V328×P35 no 13_PAV,
    onde fragmentos ao sul deslocavam o eixo médio para cima da banda do
    pilar e criavam um falso "passa"). Cada grupo de segmentos de fundo
    próximos vira um corredor independente; passa/para e wall-hits devem
    ser avaliados corredor a corredor.
    """
    # Corredor recuperado do par de paredes do DXF vence o traçado: ele é a
    # medição direta do desenho, e o traçado pode vir truncado ou deslocado.
    recovered = beam.get("_recovered_corridor")
    if isinstance(recovered, (list, tuple)) and len(recovered) == 4:
        try:
            return [tuple(float(value) for value in recovered)]
        except (TypeError, ValueError):
            pass
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

    # Uma tampa (segmento degenerado, sem espessura no eixo perpendicular ao
    # eixo dominante da viga) que fique inteiramente fora do corredor medido
    # no par de paredes do DXF não é parede desta viga: é o traçado colando
    # em elemento vizinho no ponto de contato (V331×P18 no 13_PAV — tampa a
    # y=2441 ligando a parede real do V331 até a face do pilar ao lado, fora
    # do corredor medido em y:[2460,2661]). Ao longo do eixo dominante a
    # viga pode legitimamente passar do trecho medido (o par de paredes só
    # amostra onde achou evidência); só a tampa perpendicular é vetada, e só
    # quando há medição independente pra contestá-la — sem isso o filtro não
    # se aplica (ex.: VF202, cuja geometria não forma par de paredes nenhum).
    measured_corridor = beam.get("_measured_corridor")
    if isinstance(measured_corridor, (list, tuple)) and len(measured_corridor) == 4:
        try:
            mx0, my0, mx1, my1 = (float(v) for v in measured_corridor)
        except (TypeError, ValueError):
            mx0 = my0 = mx1 = my1 = None
        if mx0 is not None:
            beam_is_h = beam_axis_is_horizontal(beam, fallback_bbox=beam_bbox_from_entity(beam))
            tol = 1.0
            kept_boxes = []
            for box in seg_boxes:
                w, h = box[2] - box[0], box[3] - box[1]
                is_cap = (w <= 1e-6) if beam_is_h else (h <= 1e-6)
                if is_cap:
                    disjoint = (
                        box[2] < mx0 - tol or box[0] > mx1 + tol
                        or box[3] < my0 - tol or box[1] > my1 + tol
                    )
                    if disjoint:
                        continue
                kept_boxes.append(box)
            if kept_boxes:
                seg_boxes = kept_boxes

    seg_originais = [list(box) for box in seg_boxes]

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

    # Corredor inflado: o agrupamento por proximidade engoliu segmento de
    # outra viga que encosta na ponta. `V329` (vertical, 19) carregava dois
    # trechos horizontais da `V304` e saía com 68 cm. Aí o par de paredes
    # **paralelas ao eixo** manda — só nesse caso, para não fragmentar os
    # corredores que já estão certos.
    section = beam_section_dim(beam)
    largura = beam_section_width(section)
    if largura and any(
        not _run_thickness_matches_section(
            min(abs(r[2] - r[0]), abs(r[3] - r[1])), section
        )
        for r in runs
    ):
        por_paredes = runs_from_parallel_walls(
            seg_originais,
            horizontal=beam_axis_is_horizontal(
                beam, fallback_bbox=beam_bbox_from_entity(beam)
            ),
            width=largura,
        )
        if por_paredes:
            return por_paredes
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


#: Folga (cm) somada ao limite de espessura do corredor, para o padding do
#: traçador (V312: seção 19, corredor 24).
RUN_THICKNESS_SLACK_CM = 15.0


def _bound_on_adjacent_faces(
    face_beams: dict, face_corners: dict, fid: str, name: str,
) -> bool:
    """A viga já ocupa alguma face vizinha desta?

    Faces vizinhas são as que compartilham canto com ``fid`` — para a curta C,
    as longas A e B.
    """
    neighbours = [
        other for other, corners in face_corners.items()
        if other != fid and any(str(corner)[-1:] == fid for corner in corners)
    ]
    for other in neighbours:
        bucket = face_beams.get(other) or {}
        for slot in ("passa_esq", "passa_dir"):
            if str((bucket.get(slot) or {}).get("name") or "") == name:
                return True
        for role in ("para", "interior"):
            if any(str(row.get("name") or "") == name for row in bucket.get(role) or []):
                return True
    return False


def _run_reaches_face(
    low: float, high: float, fixed: float, tol: float, outward: int,
    bridge: float = 0.0,
) -> bool:
    """O trecho atravessa a face, termina nela ou para a um vão dela?

    Atravessar e terminar são as duas formas diretas. A terceira é o vão:
    entre o fim da viga e a face pode não haver nada desenhado, porque ali
    passa outra viga e o trecho não é repetido — mas o vão é a continuação da
    viga, e ela chega na face do mesmo jeito (V313 × P29, com V306 no meio).
    ``bridge`` é o quanto desse vão pode ser fechado.
    """
    if low < fixed - tol and high > fixed + tol:
        return True
    if not outward:
        return False
    reach = max(tol, bridge)
    if outward > 0:
        return low >= fixed - tol and (low - fixed) <= reach and high > fixed + tol
    return high <= fixed + tol and (fixed - high) <= reach and low < fixed - tol


def _bridgeable_gap(
    beam_info: list, name: str, axis: str, fixed: float, outward: int,
    face_lo: float, face_hi: float, own_thickness: float, gap: float,
) -> float:
    """Quanto do vão até a face é ocupado por outras vigas, mais a própria seção.

    O vão só é continuação da viga enquanto o que está nele for viga. Somar a
    própria seção cobre o trecho de apoio que o desenho não repete.
    """
    occupied = 0.0
    for other in beam_info:
        if str(other.get("name") or "") == name:
            continue
        # O corredor medido no desenho responde melhor "o que há no vão" que o
        # trecho traçado, que pode parar num pilar bem antes (V306 é traçada
        # até x 1603 e medida até 3788, e é ela que ocupa o vão em P29).
        # Isto não muda a atribuição de viga nenhuma: só informa a ponte.
        corridors = other.get("measured_corridors") or other["runs"]
        for run in corridors:
            rx0, ry0, rx1, ry1 = run
            if axis == "H":
                across_lo, across_hi = rx0, rx1
                near_lo, near_hi = ry0, ry1
            else:
                across_lo, across_hi = ry0, ry1
                near_lo, near_hi = rx0, rx1
            if min(across_hi, face_hi) - max(across_lo, face_lo) <= 0:
                continue
            lo, hi = (
                (fixed, fixed + gap) if outward > 0 else (fixed - gap, fixed)
            )
            overlap = min(near_hi, hi) - max(near_lo, lo)
            if overlap > 0:
                occupied += overlap
    return occupied + own_thickness


def _run_thickness_matches_section(thickness: float, dim: Any) -> bool:
    """O corredor pode ser o trecho físico desta viga?

    O limite é **duas** larguras de seção mais folga, não uma: o contorno de
    fundo pode vir deslocado uma largura inteira (caso V304 documentado no
    CLAUDE.md), e nesse estado o corredor mede o dobro sem deixar de ser real.
    Acima disso não é mais deslocamento: é bbox de viga diagonal ou de trechos
    disjuntos colapsados, que atravessa pilares que trecho nenhum toca.

    Sem seção declarada não há como julgar, e a checagem não bloqueia.
    """
    width = beam_section_width(dim)
    if not width:
        return True
    return thickness <= 2.0 * width + RUN_THICKNESS_SLACK_CM


def beam_corridor_widths(beams: list) -> dict[str, float]:
    """Espessura medida do corredor de cada viga, por nome.

    É a evidência independente da seção declarada: se o corredor que toca a
    face mede 14 cm, nenhuma viga de 19 cm passa ali. O gate usa isso para
    separar erro de motor de célula de corpus que o desenho contradiz.
    """
    widths: dict[str, float] = {}
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = str(beam.get("name") or "").strip()
        bbox = beam_bbox_from_entity(beam)
        if not name or not bbox:
            continue
        is_h = beam_axis_is_horizontal(beam, fallback_bbox=bbox)
        runs = beam_runs_from_entity(beam) or [bbox]
        measured = [
            (run[3] - run[1]) if is_h else (run[2] - run[0]) for run in runs
        ]
        if measured:
            widths[name] = round(min(measured), 1)
    return widths


def apply_transversal_crossing_arrivals(
    face_beams: dict,
    *,
    beam_info: list,
    face_coords: dict,
    face_corners: dict,
    corner_side,
    tol: float,
    min_overlap: float,
    pillar_bbox: tuple[float, float, float, float] | None = None,
    end_tolerance: float = 1.0,
) -> int:
    """Registra como chegada a viga que cruza a face de through.

    O teste de contato por parede só reconhece viga **paralela** à face, cuja
    parede coincide com ela. Uma viga perpendicular que atravessa a face não
    alinha parede nenhuma e, quando também não cobre o pilar inteiro, não
    gerava contato algum — a face ficava sem a viga que nela chega (V312 em
    P42, V316 em P44, V320 em P46, V325 em P48).

    O canto sai da posição do cruzamento ao longo da face: encostado num
    extremo usa o canto daquele extremo; no meio usa o canto próprio da face,
    que é a marcação de "chega no meio" e implica duas lajes na face.
    """
    def outward_sign(axis: str, fixed: float) -> int:
        """+1 se o lado de fora da face é o das coordenadas maiores."""
        if not pillar_bbox:
            return 0
        px0, py0, px1, py1 = pillar_bbox
        center = (py0 + py1) / 2.0 if axis == "H" else (px0 + px1) / 2.0
        return 1 if fixed >= center else -1

    added = 0
    for fid, (axis, fixed, r0, r1) in face_coords.items():
        bucket = face_beams.get(fid)
        if bucket is None:
            continue
        c_esq, c_dir = face_corners[fid]
        mid_corner = f"{fid}{fid}"
        occupied = {
            str((bucket.get(slot) or {}).get("name") or "")
            for slot in ("passa_esq", "passa_dir")
        }
        occupied |= {str(row.get("name") or "") for row in bucket.get("para") or []}
        for bi in beam_info:
            name = str(bi.get("name") or "")
            if not name or name in occupied:
                continue
            for run in bi["runs"]:
                rx0, ry0, rx1, ry1 = run
                view = {**bi, "x0": rx0, "y0": ry0, "x1": rx1, "y1": ry1}
                lo_face, hi_face = min(r0, r1), max(r0, r1)
                if axis == "H":
                    if bi["is_h"]:
                        continue
                    near, far = ry0, ry1
                    thickness = rx1 - rx0
                    lo, hi = max(lo_face, rx0), min(hi_face, rx1)
                else:
                    if not bi["is_h"]:
                        continue
                    near, far = rx0, rx1
                    thickness = ry1 - ry0
                    lo, hi = max(lo_face, ry0), min(hi_face, ry1)
                crossing = near < fixed - tol and far > fixed + tol
                outward = outward_sign(axis, fixed)
                # R1 do dono: o vão entre o fim da viga e a face é continuação
                # da viga. `_bridgeable_gap` só o fecha enquanto o que estiver
                # nele for viga — medido no desenho, não no traçado.
                # R1 do dono: o vão entre o fim da viga e a face é continuação
                # da viga. `_bridgeable_gap` só o fecha enquanto o que estiver
                # dentro dele for viga — medido no desenho, não no traçado,
                # porque o traçado pode parar num pilar bem antes (V306 vai
                # traçada até x 1603 e medida até 3788, e é ela que ocupa o
                # vão em P29). Ver docs/INTERPRETACAO-VIGA-CHEGA-VAO-E-FACE.md.
                gap = (near - fixed) if outward > 0 else (fixed - far)
                bridge = 0.0
                if not crossing and outward and gap > tol:
                    bridge = _bridgeable_gap(
                        beam_info, name, axis, fixed, outward,
                        lo_face, hi_face, thickness, gap,
                    )
                if not _run_reaches_face(near, far, fixed, tol, outward, bridge):
                    continue
                if not crossing and _bound_on_adjacent_faces(
                    face_beams, face_corners, fid, name,
                ):
                    # Viga que corre paralela às faces vizinhas e morre neste
                    # canto já está vinculada nelas: aqui ela é interior, não
                    # uma chegada nova (P35/V308).
                    continue
                if not _run_thickness_matches_section(thickness, bi.get("dim")):
                    # Corredor mais grosso que a própria seção não é corredor:
                    # é o bbox de uma viga diagonal ou de trechos disjuntos, e
                    # atravessa pilares que nenhum trecho toca (VF202 no 13_PAV,
                    # 75 cm de "corredor" para uma seção de 14).
                    continue
                if hi - lo <= min_overlap:
                    continue
                # O lado esq/dir sai do mapeamento canônico da face; refazê-lo
                # aqui inverteria os cantos das faces longas verticais.
                if lo - lo_face > end_tolerance and hi_face - hi > end_tolerance:
                    corner = mid_corner
                else:
                    corner = (
                        c_esq
                        if corner_side(fid, axis, fixed, r0, r1, view) == "esq"
                        else c_dir
                    )
                bucket.setdefault("para", []).append({
                    "name": name,
                    "dim": bi["dim"],
                    "corner": corner,
                    "behavior": "para",
                    "source": "transversal_face_crossing",
                    **({"evidence_segments": copy.deepcopy(bi["evidence_segments"])}
                       if bi.get("evidence_segments") else {}),
                })
                occupied.add(name)
                added += 1
                break
    return added


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
            # A cota pode estar próxima da face sem que a viga a toque.
            # Materializar CA/CB exige contato do contorno, não apenas
            # pertencimento a uma faixa gráfica.
            contact_tol = min(tol, 3.0)
            wall_c = (
                abs(ry0 - face_c_y) <= contact_tol
                or abs(ry1 - face_c_y) <= contact_tol
            )
            if not wall_c:
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
        # 1) identidade do próprio trecho que provou o contato. Um rótulo
        # próximo pode pertencer a outra viga e não vence a geometria.
        pool = west_hits if side == "west" else east_hits
        geometric_names = [str(hit.get("name") or "").strip() for hit in pool]
        geometric_names = [item for item in geometric_names if item]
        if geometric_names:
            return geometric_names[0]
        # 2) rótulo V/VF na faixa do topo
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

    # Multi-segmento exige evidência geométrica nos DOIS lados. Cotas explicam
    # dimensão, mas não provam contato.
    # Um único lado = chega simples (já coberta pelo fluxo para[]) — não forçar C.
    side_w = bool(west_hits)
    side_e = bool(east_hits)
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

    # Uma viga não muda de seção na largura de um pilar: quando o mesmo nome
    # ocupa os dois cantos de C, a dimensão local escolhida por proximidade
    # pode ter capturado a cota da viga vizinha. A seção canônica da própria
    # viga desempata (V301 em P43/P45/P47: 19/55 local x 19/120 real).
    unify_esq, unify_dir = slots_c.get("passa_esq"), slots_c.get("passa_dir")
    if (
        isinstance(unify_esq, dict) and isinstance(unify_dir, dict)
        and unify_esq.get("name")
        and unify_esq.get("name") == unify_dir.get("name")
        and unify_esq.get("dim") != unify_dir.get("dim")
    ):
        beam_entity = next(
            (b for b in beams or []
             if isinstance(b, dict) and str(b.get("name") or "") == unify_esq["name"]),
            None,
        )
        canonical = canonical_fundo_section_dim(beam_entity) if beam_entity else ""
        if canonical:
            unify_esq["dim"] = canonical
            unify_dir["dim"] = canonical

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
        section = beam_section_dim(beam)
        runs = beam_runs_from_entity(beam) or [(x0, y0, x1, y1)]
        # Um corredor mais grosso que a própria seção não é corredor físico:
        # é o bbox de uma viga diagonal ou de trechos disjuntos colapsados, e
        # cria vínculo com pilares que trecho nenhum toca (VF202 no 13_PAV:
        # 75 cm de "corredor" para uma seção de 14).
        physical_runs = [
            run for run in runs
            if _run_thickness_matches_section(
                (run[3] - run[1]) if is_h else (run[2] - run[0]), section,
            )
        ]
        if not physical_runs:
            # Sem corredor com a espessura da viga não há trecho físico com que
            # julgar contato, e opinar produz vínculo com pilar que trecho
            # nenhum toca. Cair no bbox foi medido e rejeitado: devolve os
            # contatos fantasmas de VF202 em P18/P28–P32 (bbox de 2458 cm para
            # uma diagonal de ~110 cm) sem ganho em nenhum outro item.
            continue
        runs = physical_runs
        corridor_widths = [
            (run[3] - run[1]) if is_h else (run[2] - run[0]) for run in runs
        ]
        beam_info.append(
            {
                "name": str(beam.get("name") or "").strip(),
                "dim": section,
                # Espessura medida do corredor: prova independente da seção
                # declarada, que o gate usa para separar erro de motor de
                # corpus contradito pelo desenho.
                "corridor_width": round(min(corridor_widths), 1) if corridor_widths else None,
                "x0": x0,
                "x1": x1,
                "y0": y0,
                "y1": y1,
                "is_h": is_h,
                "runs": runs,
                # Trecho como o traçador entregou, sem reparo. O reparo pelo
                # par de paredes conserta posição transversal, mas pode
                # alongar a viga: `V332` sai traçada até 3103 (a face sul do
                # `P9`) e recuperada até 3323. Provar travessia exige o
                # traçado — o reparo não é prova de comprimento.
                "traced_runs": _traced_runs(beam),
                # Corredor medido no desenho, quando a recuperação o conhece.
                # Serve só para responder o que ocupa um vão; nunca atribui a
                # viga a uma face.
                "measured_corridors": (
                    [tuple(float(v) for v in beam["_measured_corridor"])]
                    if isinstance(beam.get("_measured_corridor"), (list, tuple))
                    and len(beam["_measured_corridor"]) == 4 else None
                ),
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
                # Só a face onde a viga encosta. Marcar também a oposta foi
                # medido e é catastrófico (97 → 165 células, PASS 23 → 12),
                # embora acerte P23 e P24. Ali a face oposta é interior porque
                # `V319` **atravessa** o pilar — o corredor dela vai até 2490 —
                # e não por simetria. Depende de estender corredor, o bloqueio
                # conhecido em docs/INTERPRETACAO-VIGA-CHEGA-VAO-E-FACE.md.
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
        # Viga axial bilateral: quando a mesma viga, com largura compatível com
        # a espessura transversal do pilar, alcança as DUAS tampas curtas, ela
        # ocupa os dois cantos de cada face longa. O caso aparece tanto como
        # dois corredores separados pelo próprio pilar quanto como um corredor
        # contínuo. A deduplicação geral por nome não pode apagar AC+AD ou
        # BC+BD, pois os cantos representam contatos geométricos distintos.
        # A regra é geométrica e não depende de item, obra ou pavimento.
        short_dim = ph if horizontal else pw
        for bi in beam_info:
            if not bi.get("name") or bool(bi.get("is_h")) != bool(horizontal):
                continue
            beam_width = beam_section_width(bi.get("dim"))
            if beam_width is None or abs(beam_width - short_dim) >= TOL_ALIGN:
                continue

            aligned_runs = []
            # Travessia axial se prova no traçado, não no reparo: o reparo
            # pelo par de paredes conserta a posição transversal e pode
            # alongar a viga por cima do pilar onde ela morre.
            for run in bi.get("traced_runs") or bi.get("runs") or []:
                rx0, ry0, rx1, ry1 = run
                walls_align = (
                    abs(ry0 - py0) < TOL_ALIGN
                    and abs(ry1 - py1) < TOL_ALIGN
                    if horizontal
                    else abs(rx0 - px0) < TOL_ALIGN
                    and abs(rx1 - px1) < TOL_ALIGN
                )
                if walls_align:
                    aligned_runs.append(run)

            if horizontal:
                reaches_c = any(
                    run[0] < px0 - MIN_OV and run[2] >= px0 - TOL_ALIGN
                    for run in aligned_runs
                )
                reaches_d = any(
                    run[2] > px1 + MIN_OV and run[0] <= px1 + TOL_ALIGN
                    for run in aligned_runs
                )
            else:
                reaches_d = any(
                    run[1] < py0 - MIN_OV and run[3] >= py0 - TOL_ALIGN
                    for run in aligned_runs
                )
                reaches_c = any(
                    run[3] > py1 + MIN_OV and run[1] <= py1 + TOL_ALIGN
                    for run in aligned_runs
                )
            if not (reaches_c and reaches_d):
                continue

            payload = {
                "name": bi["name"],
                "dim": bi["dim"],
                "behavior": "passa",
                "source": "axial_bilateral_runs",
                **({"evidence_segments": copy.deepcopy(bi["evidence_segments"])}
                   if bi.get("evidence_segments") else {}),
            }
            for long_face in ("A", "B"):
                corner_esq, corner_dir = FACE_CORNERS[long_face]
                for slot, corner in (
                    ("passa_esq", corner_esq),
                    ("passa_dir", corner_dir),
                ):
                    current = face_beams[long_face].get(slot)
                    if current and current.get("name") != bi["name"]:
                        continue
                    face_beams[long_face][slot] = {**payload, "corner": corner}

                # A viga axial já foi provada nos dois extremos. Remover a
                # chegada residual do mesmo nome evita o conflito passa+chega
                # criado por uma leitura parcial de parede antes desta prova.
                face_beams[long_face]["para"] = [
                    arrival
                    for arrival in face_beams[long_face]["para"]
                    if arrival.get("name") != bi["name"]
                ]

            # Nas tampas curtas a mesma viga é interior, não passa/chega.
            # Limpar os slots parciais antes de materializar o fato axial.
            for short_face in ("C", "D"):
                slots = face_beams[short_face]
                for slot in ("passa_esq", "passa_dir"):
                    if (slots.get(slot) or {}).get("name") == bi["name"]:
                        slots[slot] = None
                slots["para"] = [
                    arrival
                    for arrival in slots["para"]
                    if arrival.get("name") != bi["name"]
                ]
                if not any(
                    interior.get("name") == bi["name"]
                    for interior in slots["interior"]
                ):
                    slots["interior"].append({
                        "name": bi["name"],
                        "dim": bi["dim"],
                        "source": "axial_bilateral_runs",
                        **({"evidence_segments": copy.deepcopy(bi["evidence_segments"])}
                           if bi.get("evidence_segments") else {}),
                    })

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
            if slots["para"] or slots["interior"]:
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
                    occupied_names = {
                        (slots.get("passa_esq") or {}).get("name"),
                        (slots.get("passa_dir") or {}).get("name"),
                    } - {None}
                    if occupied_names and bi["name"] not in occupied_names:
                        continue
                    payload = {
                        "name": bi["name"],
                        "dim": bi["dim"],
                        "behavior": "passa",
                        **({"evidence_segments": copy.deepcopy(bi["evidence_segments"])}
                           if bi.get("evidence_segments") else {}),
                    }

                    # Uma viga pode vir materializada em dois trechos, um de
                    # cada lado do pilar (o vazio entre eles e o proprio
                    # pilar). Nesse caso ela realmente ocupa os DOIS cantos
                    # da face curta. A deduplicacao geral por nome nao se
                    # aplica: DA e DB (ou CA e CB) sao evidencias distintas.
                    # Exigimos dois trechos independentes para nao transformar
                    # um unico retangulo continuo em dois vinculos artificiais.
                    def run_touches_wall(run):
                        rx0, ry0, rx1, ry1 = run
                        if axis == "H":
                            return ry0 - TOL_ALIGN <= fixed <= ry1 + TOL_ALIGN
                        return rx0 - TOL_ALIGN <= fixed <= rx1 + TOL_ALIGN

                    # Preserve os trechos observacionais antes da agregacao de
                    # corredores: uma tolerancia de merge pode unir justamente
                    # o vao de 19 cm ocupado pelo pilar e apagar a bilateralidade.
                    evidence_runs = []
                    for evidence in bi.get("evidence_segments") or []:
                        evidence_points = evidence.get("points") or []
                        if len(evidence_points) < 2:
                            continue
                        exs = [float(point[0]) for point in evidence_points]
                        eys = [float(point[1]) for point in evidence_points]
                        evidence_runs.append((min(exs), min(eys), max(exs), max(eys)))
                    source_runs = evidence_runs if len(evidence_runs) >= 2 else (bi.get("runs") or [])
                    wall_runs = [run for run in source_runs if run_touches_wall(run)]
                    if axis == "H":
                        low_side = any(
                            run[0] < r0 - MIN_OV and abs(run[2] - r0) < TOL_ALIGN
                            for run in wall_runs
                        )
                        high_side = any(
                            run[2] > r1 + MIN_OV and abs(run[0] - r1) < TOL_ALIGN
                            for run in wall_runs
                        )
                    else:
                        low_side = any(
                            run[1] < r0 - MIN_OV and abs(run[3] - r0) < TOL_ALIGN
                            for run in wall_runs
                        )
                        high_side = any(
                            run[3] > r1 + MIN_OV and abs(run[1] - r1) < TOL_ALIGN
                            for run in wall_runs
                        )
                    bridges_both_corners = low_side and high_side

                    def along_center(run):
                        if axis == "H":
                            return (run[0] + run[2]) / 2.0
                        return (run[1] + run[3]) / 2.0

                    preferred_slot = "passa_esq"
                    if wall_runs:
                        best_run = min(
                            wall_runs,
                            key=lambda run: min(
                                abs(along_center(run) - r0),
                                abs(along_center(run) - r1),
                            ),
                        )
                        preferred_slot = (
                            "passa_esq"
                            if abs(along_center(best_run) - r0)
                            <= abs(along_center(best_run) - r1)
                            else "passa_dir"
                        )

                    if slots[preferred_slot] is None:
                        corner_key = "corner_esq" if preferred_slot == "passa_esq" else "corner_dir"
                        slots[preferred_slot] = {**payload, "corner": slots[corner_key]}
                    if bridges_both_corners:
                        slots["passa_esq"] = {**payload, "corner": slots["corner_esq"]}
                        slots["passa_dir"] = {**payload, "corner": slots["corner_dir"]}

                        # Dualidade dirigida: se a viga cobre DA+DB, as faces
                        # longas enxergam chegadas AD+BD. Para C, AC+BC.
                        # Sao chegadas (para[]), nao slots de viga passante.
                        for long_face in ("A", "B"):
                            reciprocal_corner = f"{long_face}{fid}"
                            arrivals = face_beams[long_face]["para"]
                            if not any(
                                arrival.get("name") == bi["name"]
                                and arrival.get("corner") == reciprocal_corner
                                for arrival in arrivals
                            ):
                                arrivals.append({
                                    "name": bi["name"],
                                    "dim": bi["dim"],
                                    "corner": reciprocal_corner,
                                    **({"evidence_segments": copy.deepcopy(bi["evidence_segments"])}
                                       if bi.get("evidence_segments") else {}),
                                })
                    break

        # Viga perpendicular que atravessa a face: chegada que o teste de
        # parede paralela não enxerga.
        apply_transversal_crossing_arrivals(
            face_beams,
            beam_info=beam_info,
            face_coords=face_coords,
            face_corners=FACE_CORNERS,
            corner_side=_corner_side,
            tol=TOL_ALIGN,
            min_overlap=MIN_OV,
            pillar_bbox=pillar_bbox,
        )

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

    _propagate_collinear_short_face_bands(report, beams=beams)


def _propagate_collinear_short_face_bands(report: dict, *, beams: list | None = None) -> int:
    """Propaga a identidade de uma faixa contínua ao longo de uma fila PIL.

    Em plantas estruturais o nome da viga/faixa é escrito uma única vez. O
    tracer pode guardar o pequeno retângulo junto ao texto, enquanto a mesma
    linha física cruza vários pilares colineares. Se uma fila de pelo menos
    três pilares compartilha exatamente o plano da face C e apenas o pilar da
    extremidade conhece a faixa, a identidade é propagada para os pilares
    seguintes. Não substitui nenhum contato já calculado e não usa nome de
    item, obra ou pavimento.
    """
    groups: dict[tuple[str, float], list[dict]] = {}
    for entry in (report or {}).values():
        if not isinstance(entry, dict):
            continue
        points = entry.get("points") or []
        try:
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
        except (TypeError, ValueError, IndexError):
            continue
        if not xs or not ys:
            continue
        width, height = max(xs) - min(xs), max(ys) - min(ys)
        orientation = "H" if width >= height else "V"
        fixed = max(xs) if orientation == "H" else max(ys)
        center = (min(xs) + max(xs)) / 2.0 if orientation == "V" else (min(ys) + max(ys)) / 2.0
        groups.setdefault((orientation, round(fixed, 2)), []).append({
            "entry": entry, "center": center,
            "axis_min": min(xs) if orientation == "V" else min(ys),
            "axis_max": max(xs) if orientation == "V" else max(ys),
            "face_fixed": fixed,
            "orientation": orientation,
        })

    dimension_facts, _ = _collect_top_band_facts(beams or [])

    def _local_dims(record: dict, moving_positive: bool, fallback: str) -> tuple[str, str]:
        """Dimensões de entrada/saída junto à face C do pilar.

        O nome de uma faixa pode ser escrito uma vez, mas a seção pode mudar
        junto a um apoio. A cota no lado de onde a faixa vem vale para o canto
        de entrada; a do lado oposto passa a ser a seção carregada adiante.
        """
        orientation = record["orientation"]
        center = record["center"]
        # Uma cota B/H do próprio pilar costuma ficar exatamente junto à
        # face C e tem a mesma gramática de uma seção de viga. Ela não é
        # evidência de mudança da faixa. Derivamos a seção do contorno alvo
        # (sem nome de obra/item) e a excluímos das candidatas locais.
        pillar_short = abs(float(record["face_fixed"]) - float(
            min(
                point[1] if orientation == "V" else point[0]
                for point in record["entry"].get("points") or []
            )
        ))
        pillar_long = float(record["axis_max"]) - float(record["axis_min"])

        def _numbers(dim: str) -> tuple[float, ...]:
            values = re.findall(r"\d+(?:[.,]\d+)?", str(dim or ""))
            return tuple(sorted(round(float(value.replace(",", ".")), 2) for value in values))

        pillar_section = tuple(sorted((round(pillar_short, 2), round(pillar_long, 2))))
        candidates = []
        for fact in dimension_facts:
            axis = fact["x"] if orientation == "V" else fact["y"]
            face = fact["y"] if orientation == "V" else fact["x"]
            if abs(face - record["face_fixed"]) > 80.0:
                continue
            if axis < record["axis_min"] - 180.0 or axis > record["axis_max"] + 180.0:
                continue
            dim = str(fact.get("dim") or "")
            if _numbers(dim) == pillar_section:
                continue
            candidates.append((axis, dim))

        lower = [row for row in candidates if row[0] <= center]
        upper = [row for row in candidates if row[0] >= center]
        lower_dim = min(lower, key=lambda row: abs(row[0] - center))[1] if lower else ""
        upper_dim = min(upper, key=lambda row: abs(row[0] - center))[1] if upper else ""
        # Uma única cota próxima pode pertencer a outra entidade do detalhe.
        # Mudança de seção ao apoio exige as duas margens (entrada e saída);
        # sem o par, conserva a seção já comprovada e carregada pela faixa.
        if not (lower_dim and upper_dim):
            return fallback, fallback
        if moving_positive:
            inbound, outbound = lower_dim, upper_dim
        else:
            inbound, outbound = upper_dim, lower_dim
        inbound = clean_beam_section_dim(inbound) or inbound or fallback
        outbound = clean_beam_section_dim(outbound) or outbound or inbound
        return inbound, outbound

    propagated = 0
    for records in groups.values():
        records.sort(key=lambda record: record["center"])
        if len(records) < 3:
            continue
        donors: list[tuple[int, dict]] = []
        for index, record in enumerate(records):
            face_beams = record["entry"].get("face_beams") or {}
            c_face = face_beams.get("C") or {}
            slots = [c_face.get("passa_esq"), c_face.get("passa_dir")]
            named = [slot for slot in slots if isinstance(slot, dict) and slot.get("name")]
            names = {str(slot.get("name")) for slot in named}
            if len(names) == 1:
                donors.append((index, named[0]))
        if len(donors) != 1:
            continue
        donor_index, donor = donors[0]
        if donor_index not in (0, len(records) - 1):
            continue
        targets = (
            records[donor_index + 1:]
            if donor_index == 0
            else list(reversed(records[:donor_index]))
        )
        moving_positive = donor_index == 0
        carried_dim = donor.get("dim") or ""
        for target_index, record in enumerate(targets):
            face_beams = record["entry"].get("face_beams") or {}
            if not all(face in face_beams for face in "ABC"):
                continue
            c_face = face_beams["C"]
            if (
                c_face.get("passa_esq") or c_face.get("passa_dir")
                or c_face.get("para") or c_face.get("interior")
            ):
                break
            inbound_dim, outbound_dim = _local_dims(record, moving_positive, carried_dim)
            carried_dim = outbound_dim
            payload = {
                "name": donor["name"], "dim": inbound_dim,
                "behavior": "passa", "source": "collinear_short_face_band",
                **({"evidence_segments": copy.deepcopy(donor["evidence_segments"])}
                   if donor.get("evidence_segments") else {}),
            }
            # Pilares internos recebem os dois contatos. No último pilar da
            # fila, a faixa termina: materializa apenas o contato voltado para
            # o interior. Isso evita inventar uma continuação além da
            # extremidade (ex.: CA/AC no extremo direito; CB/BC no esquerdo).
            is_row_endpoint = target_index == len(targets) - 1
            if not is_row_endpoint or donor_index > 0:
                c_face["passa_dir"] = {
                    **payload,
                    "dim": outbound_dim if moving_positive else inbound_dim,
                    "corner": "CB",
                }
            if not is_row_endpoint or donor_index == 0:
                c_face["passa_esq"] = {
                    **payload,
                    "dim": inbound_dim if moving_positive else outbound_dim,
                    "corner": "CA",
                }
            arrivals_to_add = (("A", "AC"), ("B", "BC"))
            if is_row_endpoint:
                arrivals_to_add = (
                    (("A", "AC"),) if donor_index == 0 else (("B", "BC"),)
                )
            for face, corner in arrivals_to_add:
                arrivals = face_beams[face].setdefault("para", [])
                if not any(
                    item.get("name") == donor["name"] and item.get("corner") == corner
                    for item in arrivals
                ):
                    arrivals.append({
                        "name": donor["name"],
                        "dim": (
                            inbound_dim if face == ("A" if moving_positive else "B")
                            else outbound_dim
                        ),
                        "corner": corner, "behavior": "para",
                        "source": "collinear_short_face_band",
                    })
            propagated += 1
    return propagated
