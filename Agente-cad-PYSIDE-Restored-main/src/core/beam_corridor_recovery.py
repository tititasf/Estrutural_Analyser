"""Recupera o corredor físico de uma viga a partir do par de paredes do DXF.

O traçador entrega trechos que podem estar truncados, deslocados ou até
fabricados: no 13_PAV a viga ``VF203`` recebeu geometria em x 1038–1434, onde
o desenho não tem nada, enquanto o corredor real dela vai de x 1444 a 3788.

A âncora usada aqui é a que o próprio desenho oferece: o **rótulo** da viga e a
**seção declarada**. Duas paredes paralelas separadas exatamente pela largura
da seção, perto do rótulo, são o corredor daquela viga — e nada mais no
desenho tem essa assinatura naquele ponto. A extensão segue enquanto as duas
paredes continuam, o que faz o corredor parar sozinho onde a largura muda
(``VF203`` de 14 cm termina em ``P33``, onde começa ``V308`` de 19 cm).

O módulo não conhece obra, pavimento nem nome de item: recebe segmentos e
devolve corredores.
"""
from __future__ import annotations

from typing import Any, Iterable

#: Tolerância (cm) para considerar duas coordenadas a mesma reta.
COLLINEAR_TOL_CM = 0.6
#: Tolerância (cm) entre a separação das paredes e a seção declarada.
WIDTH_TOL_CM = 1.5
#: Vão máximo (cm) que o corredor atravessa sem parede — a interrupção que um
#: pilar causa nas duas paredes. Acima disso são dois corredores distintos.
MAX_GAP_CM = 130.0
#: Distância máxima (cm) entre o rótulo e o corredor que ele nomeia.
LABEL_REACH_CM = 220.0
#: Comprimento mínimo (cm) de um corredor recuperado.
MIN_CORRIDOR_CM = 20.0


def axis_aligned_segments(entities: Iterable[Any]) -> dict[str, dict[float, list[tuple[float, float]]]]:
    """Agrupa segmentos horizontais e verticais por coordenada fixa.

    ``entities`` são dicionários ``{"points": [(x, y), ...]}``. Segmentos
    oblíquos são ignorados: eles não formam parede de corredor ortogonal.
    """
    buckets: dict[str, dict[float, list[tuple[float, float]]]] = {"h": {}, "v": {}}
    for entity in entities or []:
        points = (entity or {}).get("points") or []
        for start, end in zip(points, points[1:]):
            try:
                x0, y0 = float(start[0]), float(start[1])
                x1, y1 = float(end[0]), float(end[1])
            except (TypeError, ValueError, IndexError):
                continue
            if abs(y1 - y0) <= COLLINEAR_TOL_CM and abs(x1 - x0) > COLLINEAR_TOL_CM:
                key = round((y0 + y1) / 2.0, 1)
                buckets["h"].setdefault(key, []).append((min(x0, x1), max(x0, x1)))
            elif abs(x1 - x0) <= COLLINEAR_TOL_CM and abs(y1 - y0) > COLLINEAR_TOL_CM:
                key = round((x0 + x1) / 2.0, 1)
                buckets["v"].setdefault(key, []).append((min(y0, y1), max(y0, y1)))
    return buckets


def _merge(intervals: list[tuple[float, float]], max_gap: float) -> list[tuple[float, float]]:
    """Une intervalos que se tocam ou que ficam a menos de ``max_gap``."""
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start - merged[-1][1] <= max_gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def _overlap(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Trechos cobertos pelas duas paredes ao mesmo tempo."""
    result = []
    for a0, a1 in a:
        for b0, b1 in b:
            lo, hi = max(a0, b0), min(a1, b1)
            if hi - lo > 0:
                result.append((lo, hi))
    return sorted(result)


def _wall_coords_near(bucket: dict[float, list[tuple[float, float]]], center: float, reach: float):
    return sorted(coord for coord in bucket if abs(coord - center) <= reach)


def blocking_supports(
    supports: Iterable[tuple[float, float, float, float]],
    low: float,
    high: float,
    *,
    horizontal: bool,
    tol: float = COLLINEAR_TOL_CM,
) -> list[tuple[float, float]]:
    """Apoios que **interrompem** o corredor, no eixo dele.

    Um pilar mais largo que o corredor na direção transversal deixa a viga
    embutida e ela sai do outro lado — ``VF203`` (14 cm) atravessa ``P28``
    (80 cm). Um pilar com exatamente a largura do corredor é o fim da viga:
    ela morre nele — ``V313`` (19 cm) termina em ``P20`` (19 cm).

    O critério é a largura, não o nome nem a camada.
    """
    blocks: list[tuple[float, float]] = []
    for x0, y0, x1, y1 in supports or []:
        across_lo, across_hi = (y0, y1) if horizontal else (x0, x1)
        along_lo, along_hi = (x0, x1) if horizontal else (y0, y1)
        if min(across_hi, high) - max(across_lo, low) <= tol:
            continue  # nem toca a faixa do corredor
        wider = (low - across_lo > tol) or (across_hi - high > tol)
        if not wider:
            blocks.append((along_lo, along_hi))
    return sorted(blocks)


def separating_blocks(
    blocks: list[tuple[float, float]],
    own_label: float,
    rival_labels: Iterable[float],
) -> list[tuple[float, float]]:
    """Dos apoios que interrompem, os que separam **duas vigas diferentes**.

    Um apoio da largura do corredor só termina a viga se do outro lado houver
    outra viga — e quem diz isso é o rótulo. ``V313`` morre em ``P20`` porque
    ``V314`` está do outro lado; ``V308`` atravessa ``P34`` porque do outro
    lado continua ela mesma.
    """
    rivals = list(rival_labels or [])
    if not rivals:
        return []
    separating = []
    for block_lo, block_hi in blocks:
        own_before = own_label <= block_lo
        if any(
            (rival >= block_hi) if own_before else (rival <= block_lo)
            for rival in rivals
        ):
            separating.append((block_lo, block_hi))
    return separating


def clip_to_traced_end(
    corridor: tuple[float, float, float, float],
    traced_runs: Iterable[tuple[float, float, float, float]],
    supports: Iterable[tuple[float, float, float, float]] | None,
    *,
    horizontal: bool,
    tol: float = COLLINEAR_TOL_CM,
) -> tuple[float, float, float, float]:
    """O reparo conserta a posição da viga; não a alonga.

    Onde o traçado termina **rente a um apoio da largura do corredor**, o
    desenho já disse que a viga morre ali. `V332` sai traçada até y 3103, a
    face sul do `P9` (19 cm, a mesma largura dela), e o par de paredes segue
    até 3323 porque as arestas do próprio pilar são colineares. Sem esse
    corte, a viga vira axial bilateral e ocupa os dois cantos de A e B.

    Só corta onde há apoio: fim de traçado no vazio continua sendo truncagem,
    e é justamente o que o reparo existe para consertar.
    """
    lista = [run for run in (traced_runs or []) if run]
    if not lista:
        return corridor
    x0, y0, x1, y1 = corridor
    start, end = (x0, x1) if horizontal else (y0, y1)
    low, high = (y0, y1) if horizontal else (x0, x1)
    spans = [
        (min(r[0], r[2]), max(r[0], r[2])) if horizontal
        else (min(r[1], r[3]), max(r[1], r[3]))
        for r in lista
    ]
    t0, t1 = min(s[0] for s in spans), max(s[1] for s in spans)
    for block_lo, block_hi in blocking_supports(
        supports or [], low, high, horizontal=horizontal, tol=tol,
    ):
        if abs(block_lo - t1) <= tol and end > block_lo:
            end = block_lo
        if abs(block_hi - t0) <= tol and start < block_hi:
            start = block_hi
    if end - start <= 0:
        return corridor
    return (start, low, end, high) if horizontal else (low, start, high, end)


def _cut_at_blocks(
    spans: list[tuple[float, float]], blocks: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Parte os trechos onde um apoio interrompe o corredor."""
    if not blocks:
        return spans
    result = list(spans)
    for block_lo, block_hi in blocks:
        cut: list[tuple[float, float]] = []
        for start, end in result:
            if block_hi <= start or block_lo >= end:
                cut.append((start, end))
                continue
            if start < block_lo:
                cut.append((start, block_lo))
            if end > block_hi:
                cut.append((block_hi, end))
        result = cut
    return [span for span in result if span[1] - span[0] > 0]


def recover_beam_corridor(
    segments: dict[str, dict[float, list[tuple[float, float]]]],
    label_pos: tuple[float, float] | None,
    section_width: float | None,
    *,
    horizontal: bool,
    supports: Iterable[tuple[float, float, float, float]] | None = None,
    rival_labels: Iterable[float] | None = None,
    max_gap: float = MAX_GAP_CM,
    label_reach: float = LABEL_REACH_CM,
) -> tuple[float, float, float, float] | None:
    """Corredor (x0, y0, x1, y1) da viga, ou None se o desenho não o sustenta.

    Escolhe o par de paredes separado pela seção declarada mais próximo do
    rótulo e o estende enquanto as duas continuarem.
    """
    if not label_pos or not section_width:
        return None
    axis = "h" if horizontal else "v"
    bucket = segments.get(axis) or {}
    if not bucket:
        return None
    label_along, label_across = (
        (label_pos[0], label_pos[1]) if horizontal else (label_pos[1], label_pos[0])
    )
    candidates = _wall_coords_near(bucket, label_across, label_reach)

    best = None
    for index, low in enumerate(candidates):
        for high in candidates[index + 1:]:
            if abs((high - low) - section_width) > WIDTH_TOL_CM:
                continue
            spans = _overlap(
                _merge(bucket[low], max_gap), _merge(bucket[high], max_gap),
            )
            # O corredor termina no apoio que a viga não atravessa — e só
            # quando do outro lado houver outra viga. Sem o corte, a varredura
            # passa direto por um pilar alinhado ao eixo, cujas arestas ficam
            # sobre as mesmas retas das paredes; sem a ressalva do rótulo, ela
            # pararia a viga no meio dela mesma.
            spans = _cut_at_blocks(spans, separating_blocks(
                blocking_supports(supports, low, high, horizontal=horizontal),
                label_along, rival_labels or [],
            ))
            for start, end in spans:
                if end - start < MIN_CORRIDOR_CM:
                    continue
                # O rótulo nomeia o corredor que ele alcança: distância ao
                # trecho, não ao seu centro, para não penalizar viga longa.
                along_gap = max(start - label_along, label_along - end, 0.0)
                across_gap = min(abs(label_across - low), abs(label_across - high))
                distance = along_gap + across_gap
                if distance > label_reach:
                    continue
                if best is None or distance < best[0]:
                    best = (distance, low, high, start, end)
    if best is None:
        return None
    _, low, high, start, end = best
    return (start, low, end, high) if horizontal else (low, start, high, end)


#: Distância (cm) entre o rótulo e as paredes para ele disputar o corredor.
PAIR_CLAIM_REACH_CM = 40.0
#: Fração do trecho que precisa ter parede desenhada para ele ser considerado
#: sustentado pelo DXF.
SUPPORT_RATIO = 0.5


def run_is_supported_by_walls(
    run: tuple[float, float, float, float],
    segments: dict[str, dict[float, list[tuple[float, float]]]],
    *,
    horizontal: bool,
    tol: float = 2.0,
) -> bool:
    """O trecho traçado tem parede desenhada ao longo dele?

    Um trecho sem parede nenhuma não foi medido no desenho — foi fabricado, e
    é o único caso em que vale substituí-lo pelo corredor recuperado. Trecho
    com parede fica como está: estender pelo par de paredes atravessaria
    elementos colineares que não são a viga.
    """
    x0, y0, x1, y1 = run
    along = (x0, x1) if horizontal else (y0, y1)
    length = abs(along[1] - along[0])
    if length <= 0:
        return False
    bucket = segments.get("h" if horizontal else "v") or {}
    walls = (y0, y1) if horizontal else (x0, x1)
    for wall in walls:
        covered = 0.0
        for coord, intervals in bucket.items():
            if abs(coord - wall) > tol:
                continue
            for start, end in _merge(intervals, 0.0):
                lo, hi = max(min(along), start), min(max(along), end)
                if hi > lo:
                    covered += hi - lo
        if covered >= length * SUPPORT_RATIO:
            return True
    return False


#: Folga (cm) para o rótulo contar como dentro do corredor. Ele é desenhado
#: rente à viga, às vezes logo acima da parede.
LABEL_INSIDE_CORRIDOR_TOL = 30.0


def _label_inside_corridor(
    corridor: tuple[float, float, float, float],
    label,
    horizontal: bool,
    tol: float = LABEL_INSIDE_CORRIDOR_TOL,
) -> bool:
    """O rótulo cai dentro (ou rente) ao corredor, nos dois eixos."""
    if not label or len(label) < 2:
        return True
    x0, y0, x1, y1 = corridor
    lx, ly = float(label[0]), float(label[1])
    dentro_x = min(x0, x1) - tol <= lx <= max(x0, x1) + tol
    dentro_y = min(y0, y1) - tol <= ly <= max(y0, y1) + tol
    return dentro_x and dentro_y


def recover_corridors_for_beams(
    beams: list[dict],
    segments: dict[str, dict[float, list[tuple[float, float]]]],
    *,
    section_width_of,
    label_pos_of,
    horizontal_of,
    supports=None,
    section_alternatives_of=None,
    split_by_labels: bool = True,
) -> dict[str, tuple[float, float, float, float]]:
    """Corredor recuperado por nome de viga, para as que o desenho sustenta.

    Duas regras de exclusividade, ambas vindas da semântica do desenho:

    - **um corredor, um rótulo**: quando duas vigas alcançam o mesmo par de
      paredes, ele é de quem está mais perto. Sem isso, uma diagonal cujo
      rótulo cai perto de outra viga rouba o corredor dela (VF202 × V306);
    - **dois rótulos na mesma linha são duas vigas**: o corredor de uma para
      antes do rótulo da outra. Sem isso, vigas empilhadas na mesma prumada
      recebem o mesmo corredor inteiro (V313 × V314).
    """
    claims: list[dict[str, Any]] = []
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = str(beam.get("name") or "").strip()
        label = label_pos_of(beam)
        width = section_width_of(beam)
        if not name or not label or not width:
            continue
        horizontal = bool(horizontal_of(beam))
        # A seção declarada pode vir corrompida na leitura (`V307` sai com
        # `192/60`, e o texto no desenho diz `19/60`). Se ela não encontra par
        # de paredes, as cotas vizinhas são tentadas: o desenho se autocorrige,
        # e só entra a largura que a geometria confirma.
        larguras = [width] + [
            alt for alt in (
                (section_alternatives_of(beam) if section_alternatives_of else []) or []
            ) if alt and abs(alt - (width or 0.0)) > WIDTH_TOL_CM
        ]
        corridor = None
        for tentativa in larguras:
            corridor = recover_beam_corridor(
                segments, label, tentativa, horizontal=horizontal, supports=supports,
                rival_labels=[
                    (other.get("pos") or (0.0, 0.0))[0 if horizontal else 1]
                    for other in beams
                    if isinstance(other, dict) and other is not beam
                    and other.get("pos")
                    and horizontal_of(other) == horizontal
                    # Seção ilegível não desqualifica o rival: o rótulo perto
                    # do corredor já diz que há outra viga ali. `V307` sai do
                    # traçador com `192/60` e, filtrada por largura, sumia
                    # como rival — e `V309` invadia o território dela.
                    and abs(
                        (other.get("pos") or (0.0, 0.0))[1 if horizontal else 0]
                        - label[1 if horizontal else 0]
                    ) <= LABEL_REACH_CM
                ],
            )
            # O corredor tem de **conter o rótulo**, ou é de outra viga. Sem
            # isto a primeira largura tentada ganhava mesmo estando errada:
            # `VF301` sai com a seção do pilar (`19/66`), e com 19 o par de
            # paredes encontrado é o da `V301`, 200 cm ao sul do rótulo dela.
            # Com 14 — a seção que o desenho traz — o par é a própria fileira
            # norte, de `P1` a `P9`.
            if corridor and _label_inside_corridor(corridor, label, horizontal):
                width = tentativa
                break
            corridor = None
        if not corridor:
            continue
        along, across = (
            (label[0], label[1]) if horizontal else (label[1], label[0])
        )
        low, high = (
            (corridor[1], corridor[3]) if horizontal else (corridor[0], corridor[2])
        )
        claims.append({
            "name": name, "horizontal": horizontal, "corridor": corridor,
            "along": float(along), "across": float(across),
            "low": low, "high": high,
            "distance": min(abs(across - low), abs(across - high)),
        })

    def same_pair(a: dict, b: dict) -> bool:
        return (
            a["horizontal"] == b["horizontal"]
            and abs(a["low"] - b["low"]) <= COLLINEAR_TOL_CM
            and abs(a["high"] - b["high"]) <= COLLINEAR_TOL_CM
        )

    def loses_pair(claim: dict, rivals: list[dict]) -> bool:
        return any(
            other["distance"] < claim["distance"] - COLLINEAR_TOL_CM
            and abs(other["along"] - claim["along"]) <= PAIR_CLAIM_REACH_CM
            for other in rivals
        )

    rivals_of = {
        id(claim): [o for o in claims if o is not claim and same_pair(claim, o)]
        for claim in claims
    }
    winners = [c for c in claims if not loses_pair(c, rivals_of[id(c)])]

    recovered: dict[str, tuple[float, float, float, float]] = {}
    for claim in winners:
        # Só quem ganhou o par de paredes corta o corredor. Cortar contra um
        # rival perdedor encolhia a viga por causa de um rótulo que nem é
        # daquele corredor (V306 ficava com 26 cm por causa de VF202).
        rivals = [o for o in winners if o is not claim and same_pair(claim, o)]
        start, end = (
            (claim["corridor"][0], claim["corridor"][2]) if claim["horizontal"]
            else (claim["corridor"][1], claim["corridor"][3])
        )
        if split_by_labels:
            for other in rivals:
                if not (start < other["along"] < end):
                    continue
                border = (claim["along"] + other["along"]) / 2.0
                if other["along"] > claim["along"]:
                    end = min(end, border)
                else:
                    start = max(start, border)
        if end - start < MIN_CORRIDOR_CM:
            continue
        low, high = claim["low"], claim["high"]
        recovered[claim["name"]] = (
            (start, low, end, high) if claim["horizontal"] else (low, start, high, end)
        )
    return recovered


#: Distância máxima (cm) entre o rótulo de uma viga e um texto de cota para a
#: cota contar como seção alternativa dela.
SECTION_TEXT_REACH_CM = 120.0
#: Folga (cm) para o rótulo cair fora do corredor **reparado** (depois dos
#: cortes por vizinha e por apoio) e ainda contar como daquela viga.
LABEL_INSIDE_TOL_CM = 20.0


def pillar_support_boxes(
    pillars: Iterable[dict],
) -> list[tuple[float, float, float, float]]:
    """Caixas dos pilares, que são os apoios onde uma viga pode terminar.

    Medido e revertido: decompor o L nos retângulos reais piora o resultado
    — a perna e o pé de um L são bandas da largura de uma viga, e a regra
    "mesma largura → a viga morre aqui" corta a viga que **é** aquela banda.
    O contorno real serve para medir face, não para tipificar apoio.
    """
    boxes: list[tuple[float, float, float, float]] = []
    for pillar in pillars or []:
        points = (pillar or {}).get("points") or []
        try:
            xs = [float(p[0]) for p in points]
            ys = [float(p[1]) for p in points]
        except (TypeError, ValueError, IndexError):
            continue
        if len(xs) >= 2:
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
    return boxes


def recover_pillar_beam_corridors(
    dxf_path: Any,
    beams: list[dict],
    supports: list[tuple[float, float, float, float]] | None = None,
    *,
    section_text_reach_cm: float = SECTION_TEXT_REACH_CM,
    label_inside_tol_cm: float = LABEL_INSIDE_TOL_CM,
) -> tuple[dict[str, tuple[float, float, float, float]], dict[str, tuple[float, float, float, float]]]:
    """Corredor físico de cada viga, medido no par de paredes do DXF.

    Devolve ``(reparado, medido)``: ``reparado`` substitui o traçado só onde
    ele não tem parede desenhada ao longo dele; ``medido`` é a leitura crua
    do desenho, usada para responder "o que ocupa este vão" sem mexer em
    atribuição nenhuma (a R1 do dono). Fonte única — usada tanto pelo motor
    de produção (``main.py``) quanto pelo comparador de QA.
    """
    from pathlib import Path as _Path

    if not dxf_path or not _Path(dxf_path).is_file():
        return {}, {}
    try:
        import ezdxf
    except ImportError:
        return {}, {}
    from src.core.pillar_face_beams import (
        beam_axis_is_horizontal, beam_bbox_from_entity, beam_runs_from_entity,
        beam_section_dim, beam_section_width,
    )

    entities: list[dict[str, Any]] = []
    section_texts: list[tuple[float, float, float]] = []
    for entity in ezdxf.readfile(str(dxf_path)).modelspace():
        if entity.dxftype() in ("TEXT", "MTEXT"):
            try:
                text = (
                    entity.plain_text() if entity.dxftype() == "MTEXT"
                    else entity.dxf.text
                ).strip()
                insert = entity.dxf.insert
            except Exception:
                continue
            largura = beam_section_width(text)
            if largura:
                section_texts.append((largura, float(insert[0]), float(insert[1])))
            continue
        if entity.dxftype() == "LINE":
            entities.append({"points": [
                (entity.dxf.start[0], entity.dxf.start[1]),
                (entity.dxf.end[0], entity.dxf.end[1]),
            ]})
        elif entity.dxftype() in ("LWPOLYLINE", "POLYLINE"):
            try:
                entities.append({"points": [(p[0], p[1]) for p in entity.get_points("xy")]})
            except Exception:
                continue
    segments = axis_aligned_segments(entities)

    def section_alternatives(beam: dict) -> list[float]:
        pos = beam.get("pos")
        if not pos:
            return []
        perto = sorted(
            (((x - pos[0]) ** 2 + (y - pos[1]) ** 2) ** 0.5, largura)
            for largura, x, y in section_texts
        )
        vistas: list[float] = []
        for distancia, largura in perto:
            if distancia > section_text_reach_cm:
                break
            if all(abs(largura - v) > 0.6 for v in vistas):
                vistas.append(largura)
        return vistas

    def is_horizontal(beam: dict) -> bool:
        return beam_axis_is_horizontal(beam, fallback_bbox=beam_bbox_from_entity(beam))

    recovered = recover_corridors_for_beams(
        beams, segments,
        section_width_of=lambda beam: beam_section_width(beam_section_dim(beam)),
        label_pos_of=lambda beam: beam.get("pos"),
        horizontal_of=is_horizontal,
        supports=supports,
        section_alternatives_of=section_alternatives,
    )
    for beam in beams:
        name = str(beam.get("name") or "")
        corridor = recovered.get(name)
        if not corridor:
            continue
        recovered[name] = clip_to_traced_end(
            corridor, beam_runs_from_entity(beam), supports,
            horizontal=is_horizontal(beam),
        )
    supported: list[tuple[str, bool, float, float, float, float]] = []
    broken: list[tuple[str, dict, bool]] = []
    for beam in beams:
        name = str(beam.get("name") or "")
        horizontal = is_horizontal(beam)
        runs = beam_runs_from_entity(beam) or []
        beam_supported = [
            run for run in runs
            if run_is_supported_by_walls(run, segments, horizontal=horizontal)
        ]
        for run in beam_supported:
            along = (run[0], run[2]) if horizontal else (run[1], run[3])
            across = (run[1], run[3]) if horizontal else (run[0], run[2])
            supported.append(
                (name, horizontal, across[0], across[1], along[0], along[1])
            )
        if not beam_supported and name in recovered:
            broken.append((name, beam, horizontal, None))

    repaired: dict[str, Any] = {}
    for name, beam, horizontal, pronto in broken:
        if pronto:
            repaired[name] = pronto
            continue
        corridor = recovered[name]
        start, end = (
            (corridor[0], corridor[2]) if horizontal else (corridor[1], corridor[3])
        )
        low, high = (
            (corridor[1], corridor[3]) if horizontal else (corridor[0], corridor[2])
        )
        for other, other_h, o_low, o_high, o_start, o_end in supported:
            if other == name or other_h != horizontal:
                continue
            if min(o_high, high) - max(o_low, low) <= 0:
                continue
            if o_start <= start and o_end > start:
                start = max(start, o_end)
            elif o_end >= end and o_start < end:
                end = min(end, o_start)
        if end - start <= 0:
            continue
        pos = beam.get("pos")
        if pos and len(pos) >= 2:
            ao_longo = float(pos[0] if horizontal else pos[1])
            if not (start - label_inside_tol_cm <= ao_longo <= end + label_inside_tol_cm):
                continue
        repaired[name] = (
            (start, low, end, high) if horizontal else (low, start, high, end)
        )
    return repaired, recovered
