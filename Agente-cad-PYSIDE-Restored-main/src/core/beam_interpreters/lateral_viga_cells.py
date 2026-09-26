"""Segmentacao SA (N1) das Laterais de Viga — as QUATRO celulas isoladas.

Autoridade: o guia do dono
``scripts/arete/html_fichas/.../laterais_viga/interpretacao_laterais.html`` e o
resumo em ``docs/CONTRATO-RIGIDO-MOTOR-LV-N3-N4.md`` §6.1. Cada regra abaixo
cita o item do guia que a manda. A cena medida vem de
``src/core/lv_beam_scene.py`` (topologia bruta); aqui so' se DECIDE.

Regras aplicadas, por celula (lado A/B x comportamento Para/Passa):

* G0 — face A = ``t_lo``, face B = ``t_hi``. Leitura: A da esquerda para a
  direita (vertical: de cima para baixo); B invertido. Segmento 1 e' o
  primeiro na ordem de leitura DAQUELE lado.
* G6/G9 — pilar que ocupa a face: ``Para`` interrompe a parede nas faces do
  pilar (o recuo de 11 cm vai como ajuste de ponta, aplicado no N3 — o SA
  desenha de face a face); ``Passa`` atravessa: o pilar fica INTEIRO dentro de
  UM segmento, que registra onde o pilar comeca e termina (distancias a partir
  do inicio do segmento) e a abertura ``comprimento + 22`` (G8). Nenhuma
  fronteira cai dentro de pilar em Passa (resposta do dono Q3, 2026-09-25).
* G7 — viga que toca a face decide-se por PROFUNDIDADE, nunca por Para/Passa:
  incidente menos profunda OU de mesma profundidade (Q2) -> a lateral passa
  pela abertura (+8 de largura / +4 de altura, G8; na mesma profundidade a
  abertura e' de altura inteira) e, pela regra do dono de 2026-09-14 (contrato
  §5.2.3), o segmento fecha na borda FINAL da abertura, com o seguinte
  encostado; incidente MAIS profunda -> a lateral termina na primeira face e
  recomeca na face oposta.
* G1 — cada segmento tem UMA secao: a troca de secao abre segmento novo,
  encostado no anterior (resposta do dono Q1, 2026-09-25).
* Caso 9 — encontro em T parte so' a face que recebe a viga.
* Caso 11 — lajes da face sao registradas por segmento, com nivel proprio.

Nada aqui le N2/N4 nem usa o fundo (FV) como lei.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.core.lv_beam_scene import LvScene

CELL_RULES_VERSION = "guia_lv_cells_v2"
PILLAR_OPENING_EXTRA = 11.0     # G8/G9: 11 cm de cada lado
BEAM_OPENING_EXTRA_W = 8.0      # G8: largura da viga incidente + 8
BEAM_OPENING_EXTRA_H = 4.0      # G8: altura + 4
MIN_SEGMENT = 1.0
# Invariante do dono (2026-09-25): o destaque tem de estar SOBRE linha real do
# estrutural. Passa por pilar/abertura interrompe a borda, por isso nao se exige 100%.
LINE_COVERAGE_MIN = 0.5


@dataclass
class CellSegment:
    index: int
    start: float          # coordenada de eixo onde o segmento COMECA (ordem de leitura)
    end: float
    length: float
    dim: str
    depth: Optional[float]
    sections: list[dict] = field(default_factory=list)
    support_start: dict = field(default_factory=dict)
    support_end: dict = field(default_factory=dict)
    pillar_openings: list[dict] = field(default_factory=list)
    beam_openings: list[dict] = field(default_factory=list)
    slabs: list[dict] = field(default_factory=list)
    level: str = ""
    adjustment_start: float = 0.0
    adjustment_end: float = 0.0
    line_coverage: float = 0.0
    flags: list[str] = field(default_factory=list)


def reading_ascending(scene: LvScene, side: str) -> bool:
    """G0: A esquerda->direita / cima->baixo; B invertido."""
    if scene.is_horizontal:
        return side == "A"
    return side == "B"


def _own_depth(scene: LvScene, a0: float, a1: float) -> Optional[float]:
    depths = [
        z["depth"] for z in scene.sections
        if z["end"] > a0 + 0.5 and z["start"] < a1 - 0.5
    ]
    if depths:
        return max(depths)
    zone = scene.section_at((a0 + a1) / 2.0)
    return zone["depth"] if zone else None


def _level_value(text: str) -> Optional[float]:
    try:
        return float(str(text).replace(",", "."))
    except (TypeError, ValueError):
        return None


def segment_cell(scene: LvScene, side: str, behavior: str) -> list[CellSegment]:
    behavior = behavior.lower()
    ascending = reading_ascending(scene, side)
    hard: list[tuple[float, float, dict]] = []
    soft: list[tuple[float, dict]] = []
    pillar_events: list[dict] = []
    flags_global: list[str] = []

    for pillar in scene.pillars[side]:
        if behavior == "para":
            hard.append((pillar["start"], pillar["end"], dict(pillar, type="pilar")))
        else:
            pillar_events.append(pillar)

    for inc in scene.incidents[side]:
        own = _own_depth(scene, inc["start"], inc["end"])
        inc_depth = inc.get("depth")
        info = dict(inc, type="viga")
        if own is None or inc_depth is None:
            info["rule"] = "G7_profundidade_desconhecida_termina"
            hard.append((inc["start"], inc["end"], info))
            flags_global.append(f"G7_sem_profundidade:{inc['name']}")
            continue
        if inc_depth > own + 0.01:
            info["rule"] = "G7_incidente_mais_profunda_termina"
            hard.append((inc["start"], inc["end"], info))
            continue
        info["own_depth"] = own
        info["rule"] = (
            "G7_mesma_profundidade_abertura_altura_inteira"
            if abs(inc_depth - own) <= 0.01
            else "G7_incidente_menos_profunda_passa_por_baixo"
        )
        far_edge = inc["end"] if ascending else inc["start"]
        soft.append((far_edge, info))

    # G1 (Q1): troca de secao abre segmento novo, encostado.
    zones_sorted = sorted(scene.sections, key=lambda z: z["start"])
    for left, right in zip(zones_sorted, zones_sorted[1:]):
        if abs(left["depth"] - right["depth"]) < 0.01 and left["dim"] == right["dim"]:
            continue
        pos = right["start"]
        soft.append((pos, {
            "type": "secao", "name": f"{left['dim']}->{right['dim']}",
            "start": pos, "end": pos, "boundary": "mudanca_de_secao",
            "rule": "G1_troca_de_secao_abre_segmento",
            "source": left.get("end_source", ""),
        }))

    # Q3: em Passa nenhuma fronteira cai dentro de pilar — ela vai para a face
    # final do pilar (na ordem de leitura), e o pilar fica inteiro no segmento.
    if pillar_events:
        moved = []
        for pos, info in soft:
            for pillar in pillar_events:
                if pillar["start"] + 0.5 < pos < pillar["end"] - 0.5:
                    pos = pillar["end"] if ascending else pillar["start"]
                    info = dict(info, moved_to_pillar_face=pillar["name"])
            moved.append((pos, info))
        soft = moved

    # Pedacos livres = extensao menos cortes duros.
    cuts = sorted(hard, key=lambda item: item[0])
    pieces: list[list[Any]] = []
    cursor = scene.start
    left_info: dict = {"type": "extremidade", "supports": scene.end_supports["start"]}
    for c0, c1, info in cuts:
        if c1 <= cursor + 0.01:
            continue  # corte contido em outro (V312 dentro do P42): a face e' do maior
        if c0 > cursor + MIN_SEGMENT:
            pieces.append([cursor, min(c0, scene.end), left_info, info])
        cursor = max(cursor, c1)
        left_info = info
        if cursor >= scene.end:
            break
    if scene.end - cursor > MIN_SEGMENT:
        pieces.append([cursor, scene.end, left_info, {"type": "extremidade", "supports": scene.end_supports["end"]}])

    # Fronteiras moles (borda final das aberturas de viga).
    split: list[list[Any]] = []
    for a0, a1, linfo, rinfo in pieces:
        # Abertura encostada numa ponta do pedaco (viga incidente na
        # extremidade: V310 no inicio da V303) pertence ao proprio segmento —
        # nao ha' segmento anterior para recebe-la (contrato §5.2.3).
        inner: dict[float, dict] = {}
        for pos, info in soft:
            if not (a0 + MIN_SEGMENT < pos < a1 - MIN_SEGMENT):
                continue
            if info["type"] == "viga" and not (
                info["start"] > a0 + MIN_SEGMENT and info["end"] < a1 - MIN_SEGMENT
            ):
                continue
            key = next((k for k in inner if abs(k - pos) < 0.5), round(pos, 3))
            inner.setdefault(key, info)
        cur, cur_left = a0, linfo
        for pos in sorted(inner):
            boundary = dict(inner[pos], boundary=inner[pos].get("boundary", "abertura_de_viga"))
            split.append([cur, pos, cur_left, boundary])
            cur, cur_left = pos, boundary
        split.append([cur, a1, cur_left, rinfo])

    if not ascending:
        split = [[a0, a1, rinfo, linfo] for a0, a1, linfo, rinfo in reversed(split)]

    segments: list[CellSegment] = []
    for index, (a0, a1, first_info, last_info) in enumerate(split, start=1):
        start, end = (a0, a1) if ascending else (a1, a0)
        zones = [
            {"start": max(z["start"], a0), "end": min(z["end"], a1), "dim": z["dim"],
             "depth": z["depth"], "source": z.get("end_source", "")}
            for z in scene.sections if z["end"] > a0 + 0.5 and z["start"] < a1 - 0.5
        ]
        governing = max(zones, key=lambda z: z["depth"]) if zones else None
        seg = CellSegment(
            index=index, start=start, end=end, length=round(a1 - a0, 2),
            dim=governing["dim"] if governing else "",
            depth=governing["depth"] if governing else None,
            sections=zones,
            support_start=_support_view(first_info, ascending),
            support_end=_support_view(last_info, ascending),
            flags=list(flags_global),
        )
        seg.line_coverage = round(scene.line_coverage(side, a0, a1), 3)
        if seg.line_coverage < LINE_COVERAGE_MIN:
            seg.flags.append("fora_da_linha_estrutural")
        if not zones:
            seg.flags.append("G1_secao_nao_lida")
        if len({z["dim"] for z in zones}) > 1:
            seg.flags.append("G1_degrau_de_secao_no_segmento")
        if behavior == "para":
            if first_info.get("type") == "pilar":
                seg.adjustment_start = -PILLAR_OPENING_EXTRA
            if last_info.get("type") == "pilar":
                seg.adjustment_end = -PILLAR_OPENING_EXTRA
        for pillar in pillar_events:
            if pillar["end"] <= a0 + 0.5 or pillar["start"] >= a1 - 0.5:
                continue
            p0, p1 = max(pillar["start"], a0), min(pillar["end"], a1)
            near = p0 - a0 if ascending else a1 - p1
            far = a1 - p1 if ascending else p0 - a0
            comp = p1 - p0
            # G8 e' fixo: abertura = pilar + 22 (11 de cada lado). Quando a
            # face do pilar coincide com a ponta do segmento, os 11 daquele
            # lado avancam no segmento vizinho — sinalizado, nao descartado.
            extra_near = extra_far = PILLAR_OPENING_EXTRA
            if near < PILLAR_OPENING_EXTRA or far < PILLAR_OPENING_EXTRA:
                seg.flags.append(f"G8_abertura_excede_segmento:{pillar['name']}")
            opening = {
                "name": pillar["name"],
                "comprimento": round(comp, 2),
                "abertura": round(comp + extra_near + extra_far, 2),
                # posicao do pilar medida a partir do INICIO do segmento
                "pos_inicio": round(near, 2),
                "pos_fim": round(near + comp, 2),
                "dist_face_inicio": round(near, 2),
                "dist_face_fim": round(far, 2),
                "dist_abertura_inicio": round(near - extra_near, 2),
                "dist_abertura_fim": round(far - extra_far, 2),
                "rule": "G8_passa_abertura_pilar_mais_22",
            }
            if comp + 0.5 < pillar["end"] - pillar["start"]:
                opening["pilar_partido_por_corte"] = True
                seg.flags.append(f"G8_pilar_partido:{pillar['name']}")
            seg.pillar_openings.append(opening)
        for pos, info in soft:
            if info.get("type") != "viga":
                continue
            overlap = min(info["end"], a1) - max(info["start"], a0)
            if overlap <= 0.5:
                continue
            width = float(info["end"] - info["start"])
            full_height = info.get("rule") == "G7_mesma_profundidade_abertura_altura_inteira"
            seg.beam_openings.append({
                "name": info["name"], "dim": info.get("dim", ""),
                "largura": round(width, 2),
                "abertura_largura": round(width + BEAM_OPENING_EXTRA_W, 2),
                "abertura_altura": (
                    round(info["depth"] + BEAM_OPENING_EXTRA_H, 2)
                    if info.get("depth") is not None else None
                ),
                "sobra": (
                    round(info["own_depth"] - info["depth"], 2)
                    if info.get("depth") is not None else None
                ),
                "altura_inteira": full_height,
                "pos_inicio": round((info["start"] - a0) if ascending else (a1 - info["end"]), 2),
                "rule": info.get("rule"),
            })
        slabs = [
            s for s in scene.slabs[side]
            if min(s["end"], a1) - max(s["start"], a0) > 5.0
        ]
        slabs.sort(key=lambda s: s["start"], reverse=not ascending)
        seg.slabs = [
            {"name": s["name"], "level": s["level"], "height": s["height"]} for s in slabs[:3]
        ]
        levels = [v for v in (_level_value(s["level"]) for s in slabs) if v is not None]
        seg.level = f"{max(levels):g}" if levels else ""
        segments.append(seg)
    return segments


def _support_view(info: dict, ascending: bool = True) -> dict:
    if not info:
        return {}
    if info.get("type") == "secao":
        left, _, right = str(info.get("name", "")).partition("->")
        name = f"{left}->{right}" if ascending else f"{right}->{left}"
        return {"type": "secao", "name": name, "dim": "", "rule": info.get("rule", "")}
    if info.get("type") == "extremidade":
        supports = info.get("supports") or []
        pillar = next((s for s in supports if s.get("type") == "pilar"), None)
        chosen = pillar or (supports[0] if supports else None)
        if not chosen:
            return {"type": "extremidade", "name": ""}
        return {"type": chosen.get("type"), "name": chosen.get("name", ""), "dim": chosen.get("dim", "")}
    return {
        "type": info.get("type"),
        "name": info.get("name", ""),
        "dim": info.get("dim", ""),
        "rule": info.get("rule", info.get("boundary", "")),
    }


def segment_all_cells(scene: LvScene) -> dict[str, list[CellSegment]]:
    return {
        f"{side}_{behavior.upper()}": segment_cell(scene, side, behavior)
        for side in ("A", "B")
        for behavior in ("para", "passa")
    }


# ------------------------------------------------------------- publicacao N1

_SUFFIX = {"para": "comprimento_total", "passa": "comp_total_passa"}


def _cell_is_frozen(beam: dict, side: str, behavior: str) -> bool:
    """Celula com segmento validado por humano nao e' recalculada.

    Validacao congela a topologia so' da celula correspondente (LV.md §5):
    validar A_PARA nao congela B_PARA/A_PASSA/B_PASSA.
    """
    kind = f"lateral_{side.lower()}_{behavior}|"
    decisions = beam.get("preficha_segmentos") or {}
    if isinstance(decisions, dict) and any(
        str(uid).startswith(kind) and (dec or {}).get("status") == "valid"
        for uid, dec in decisions.items()
    ):
        return True
    pattern = f"viga_{side.lower()}_seg_"
    suffix = _SUFFIX[behavior]
    for key in list(beam.get("validated_fields") or []) + list(beam.get("validated_segments") or []):
        text = str(key)
        if text.startswith(pattern) and text.endswith(suffix):
            return True
    return False


def _link_entry(scene: LvScene, side: str, behavior: str, seg: CellSegment) -> dict:
    points = [scene.point(seg.start, side), scene.point(seg.end, side)]
    return {
        "type": "poly",
        "points": points,
        "len": seg.length,
        "tag": f"Lado {side}",
        "geometry_role": "lateral",
        "geometry_source": CELL_RULES_VERSION,
        "side": side,
        "behavior": behavior.capitalize(),
        "contract_id": f"LV_{side}_{behavior.upper()}",
        "segment_index": seg.index,
        "source_slot": f"seg_side_{side.lower()}",
        "lv_dimensao": seg.dim,
        "lv_cell": {
            "rules": CELL_RULES_VERSION,
            "dim": seg.dim,
            "depth": seg.depth,
            "sections": seg.sections,
            "support_start": seg.support_start,
            "support_end": seg.support_end,
            "pillar_openings": seg.pillar_openings,
            "beam_openings": seg.beam_openings,
            "slabs": seg.slabs,
            "level": seg.level,
            "adjustment_start": seg.adjustment_start,
            "adjustment_end": seg.adjustment_end,
            "cobertura_linha": seg.line_coverage,
            "flags": seg.flags,
        },
    }


def apply_cells_to_beam(beam: dict, scene: "LvScene | list[LvScene]") -> dict[str, int]:
    """Substitui os vinculos laterais das celulas NAO congeladas desta viga.

    ``scene`` pode ser uma lista de TRECHOS (viga em "L"): os segmentos de cada
    celula saem trecho a trecho, na ordem dos trechos, com numeracao continua.
    """
    runs = scene if isinstance(scene, list) else [scene]
    scene = runs[0]
    links = beam.setdefault("links", {})
    counts: dict[str, int] = {}
    frozen: list[str] = []
    per_side_max = {"A": 0, "B": 0}
    for side in ("A", "B"):
        for behavior in ("para", "passa"):
            cell = f"{side}_{behavior.upper()}"
            suffix = _SUFFIX[behavior]
            if _cell_is_frozen(beam, side, behavior):
                frozen.append(cell)
                existing = [
                    k for k in links
                    if str(k).startswith(f"viga_{side.lower()}_seg_") and str(k).endswith(f"_{suffix}")
                ]
                counts[cell] = len(existing)
                per_side_max[side] = max(per_side_max[side], len(existing))
                continue
            for key in [
                k for k in links
                if str(k).startswith(f"viga_{side.lower()}_seg_") and str(k).endswith(f"_{suffix}")
            ]:
                del links[key]
            segments = []
            for run_index, run in enumerate(runs, start=1):
                for seg in segment_cell(run, side, behavior):
                    seg.index = len(segments) + 1
                    if len(runs) > 1:
                        seg.flags.append(f"trecho_{run_index}_de_{len(runs)}")
                    segments.append((run, seg))
            for run, seg in segments:
                key = f"viga_{side.lower()}_seg_{seg.index}_{suffix}"
                links[key] = {f"seg_side_{side.lower()}": [_link_entry(run, side, behavior, seg)]}
            counts[cell] = len(segments)
            per_side_max[side] = max(per_side_max[side], len(segments))
    for side in ("A", "B"):
        prefix = f"viga_{side.lower()}_seg_"
        for key in [k for k in list(beam) if str(k).startswith(prefix) and str(k).endswith("_exists")]:
            try:
                idx = int(str(key)[len(prefix):-len("_exists")])
            except ValueError:
                continue
            if idx > per_side_max[side]:
                beam.pop(key, None)
        for idx in range(1, per_side_max[side] + 1):
            beam[f"{prefix}{idx}_exists"] = True
    beam["lv_cells_version"] = CELL_RULES_VERSION
    beam["_lv_cells_meta"] = {
        "counts": counts,
        "frozen_cells": frozen,
        "band": {"is_horizontal": scene.is_horizontal, "t_lo": scene.t_lo, "t_hi": scene.t_hi,
                 "start": scene.start, "end": scene.end},
        "runs": [
            {"is_horizontal": r.is_horizontal, "t_lo": r.t_lo, "t_hi": r.t_hi,
             "start": r.start, "end": r.end}
            for r in runs
        ],
        "sections": [z for r in runs for z in r.sections],
        "provenance": scene.provenance,
    }
    return counts


def apply_lv_cells_all(
    beams: list[dict], texts: list[dict], lines: list[dict], pillar_report: Any, slabs: Any = None,
) -> dict[str, dict[str, int]]:
    """Passada global: cena de todas as vigas, depois as 4 celulas de cada uma.

    Vigas sem cena (rotulo diagonal ou orientacao mista) ficam intocadas e
    listadas em ``__sem_cena__`` para triagem — nunca recebem copia de outra.
    """
    from src.core.lv_beam_scene import build_scene_runs, _norm_name

    scenes = build_scene_runs(beams, texts, lines, pillar_report, slabs)
    report: dict[str, Any] = {}
    missing = []
    owners: dict[str, dict] = {}
    for beam in beams or []:
        if not isinstance(beam, dict):
            continue
        name = _norm_name(beam.get("parent_name") or beam.get("name"))
        scene = scenes.get(name) or scenes.get(_norm_name(beam.get("name")))
        if scene is None:
            missing.append(str(beam.get("name")))
            continue
        if name in owners:
            # Fragmento irmao da mesma viga: a cena ja' foi publicada no
            # primeiro registro. Aqui so' se esvaziam as celulas NAO
            # congeladas, senao os segmentos sairiam em duplicata.
            _clear_unfrozen_cells(beam)
            continue
        owners[name] = beam
        report[str(beam.get("name"))] = apply_cells_to_beam(beam, scene)
    report["__sem_cena__"] = missing
    return report


def _clear_unfrozen_cells(beam: dict) -> None:
    links = beam.get("links") or {}
    for side in ("A", "B"):
        for behavior, suffix in _SUFFIX.items():
            if _cell_is_frozen(beam, side, behavior):
                continue
            for key in [
                k for k in list(links)
                if str(k).startswith(f"viga_{side.lower()}_seg_") and str(k).endswith(f"_{suffix}")
            ]:
                del links[key]
    beam["lv_cells_version"] = CELL_RULES_VERSION
    beam["_lv_cells_meta"] = {"fragmento_irmao": True}
