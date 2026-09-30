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
  incidente MENOS profunda -> a lateral passa pela abertura (+8 de largura /
  +4 de altura, G8) e, pela regra do dono de 2026-09-14 (contrato §5.2.3), o
  segmento fecha na borda FINAL da abertura, com o seguinte encostado;
  incidente de MESMA profundidade ou MAIS profunda -> a lateral termina na
  primeira face e recomeca na face oposta (mesma altura nao se atravessa —
  dono 2026-09-26, revendo o Q2 no cruzamento V301 x V312).
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

CELL_RULES_VERSION = "guia_lv_cells_v7"
PILLAR_OPENING_EXTRA = 11.0     # G8/G9: 11 cm de cada lado
BEAM_OPENING_EXTRA_W = 8.0      # G8: largura da viga incidente + 8
BEAM_OPENING_EXTRA_H = 4.0      # G8: altura + 4
MIN_SEGMENT = 1.0
# Invariante do dono (2026-09-25): o destaque tem de estar SOBRE linha real do
# estrutural. Passa por pilar/abertura interrompe a borda, por isso nao se exige 100%.
LINE_COVERAGE_MIN = 0.5
DIMENSION_OVERLAP_MAX = 0.05


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
    dimension_overlap: float = 0.0
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


def segment_cell(
    scene: LvScene,
    side: str,
    behavior: str,
    *,
    minimum_segment: float = MIN_SEGMENT,
) -> list[CellSegment]:
    behavior = behavior.lower()
    ascending = reading_ascending(scene, side)
    hard: list[tuple[float, float, dict]] = []
    soft: list[tuple[float, dict]] = []
    pillar_events: list[dict] = []
    flags_global: list[str] = []

    measured_passa = behavior == "passa" and scene.passa_pillars is not None
    pillar_source = scene.passa_pillars[side] if measured_passa else scene.pillars[side]
    for pillar in pillar_source:
        # Para para na face do pilar; Passa corre pela PAREDE do pilar, mas se a
        # face passaria pelo MIOLO do pilar, para tambem (dono 2026-09-26).
        # G10/D-48 (dono 2026-09-28): Para NUNCA para nas faces C/D (curtas) —
        # so' nas A/B/E/F/G/H. A letra e' a da face por onde a lateral CORRE
        # (pilar colinear corre pela A/B -> para); na C/D o pilar e' Passa.
        g10 = behavior == "para" and pillar.get("face_lateral_curta") is True
        if (behavior == "para" and not g10) or pillar.get("miolo"):
            info = dict(pillar, type="pilar")
            if behavior == "passa" or g10:
                info["rule"] = "passa_nao_atravessa_miolo_do_pilar"
            hard.append((pillar["start"], pillar["end"], info))
        else:
            pillar_events.append(dict(pillar, rule="G10_face_curta_CD_sempre_passa") if g10 else pillar)

    # Passa ENGLOBA o pilar (dono 2026-09-26): tambem o pilar da PONTA entra no
    # segmento — a lateral vai ate' a face de fora dele (V309A 1-A / 3-B no P1).
    # Para continua terminando na face do pilar — exceto face C/D (G10).
    # Diagonal (Caso 8): cada face ate' onde a propria linha vai.
    ext_start, ext_end = scene.face_extent.get(side, (scene.start, scene.end))
    if measured_passa:
        # Extend along a connected exterior wall, never across a core or a
        # pillar ceded to the deeper collinear beam.
        ceded = {s["name"] for end in scene.end_supports.values() for s in end
                 if s.get("type") == "pilar" and s.get("cede_para")}
        inherited = {s["name"]: (s.get("engloba_ini", s["start"]), s.get("engloba_fim", s["end"]))
                     for end in scene.end_supports.values() for s in end
                     if s.get("type") == "pilar" and not s.get("cede_para")
                     and ("engloba_ini" in s or "engloba_fim" in s)}
        pillar_events = [p for p in pillar_events if p["name"] not in ceded
                         and ((p["end"] >= ext_start - 1.0 and p["start"] <= ext_end + 1.0)
                              or (p["name"] in inherited and p["end"] >= inherited[p["name"]][0]
                                  and p["start"] <= inherited[p["name"]][1]))]
        for p in pillar_events:
            ext_start = min(ext_start, p["start"])
            ext_end = max(ext_end, p["end"])

    def _wall(sup: dict) -> bool:
        if measured_passa:
            return False  # Full per-face wall/core intervals already measured.
        # Pilar entre duas vigas colineares: so' a mais profunda o engloba
        # (dono 2026-09-28); a que cede para na face.
        if sup.get("cede_para"):
            return False
        if (sup.get("miolo_por_lado") or {}).get(side, False):
            return False
        # G10/D-48: no Para, so' a ponta que bate numa face C/D (curta) engloba.
        return behavior == "passa" or bool((sup.get("face_curta_por_lado") or {}).get(side))

    for sup in scene.end_supports["start"]:
        if (sup.get("type") == "pilar" and sup.get("end", -1e9) >= scene.start - 1.0
                and _wall(sup)):
            ext_start = min(ext_start, sup.get("engloba_ini", sup["start"]))
            pillar_events.append(dict(sup, extremidade="inicio"))
    for sup in scene.end_supports["end"]:
        if (sup.get("type") == "pilar" and sup.get("start", 1e9) <= scene.end + 1.0
                and _wall(sup)):
            ext_end = max(ext_end, sup.get("engloba_fim", sup["end"]))
            pillar_events.append(dict(sup, extremidade="fim"))
    # Ponta que termina NA FACE de um pilar de apoio (nao englobado).
    stops_at_pillar = {
        "start": any(
            s.get("type") == "pilar" and not _wall(s) and abs(s.get("end", -1e9) - ext_start) < 1.0
            for s in scene.end_supports["start"]
        ),
        "end": any(
            s.get("type") == "pilar" and not _wall(s) and abs(s.get("start", 1e9) - ext_end) < 1.0
            for s in scene.end_supports["end"]
        ),
    }

    incident_source = scene.passa_incidents[side] if measured_passa else scene.incidents[side]
    for inc in incident_source:
        own = _own_depth(scene, inc["start"], inc["end"])
        inc_depth = inc.get("depth")
        if measured_passa and (inc["end"] <= scene.start + 0.5 or inc["start"] >= scene.end - 0.5):
            # Existing endpoint supports stay supports. Retain the shallow
            # junctions encountered only after following a pillar wall.
            if own is None or inc_depth is None or inc_depth >= own - 0.01:
                continue
        info = dict(inc, type="viga")
        if own is None or inc_depth is None:
            info["rule"] = "G7_profundidade_desconhecida_termina"
            hard.append((inc["start"], inc["end"], info))
            flags_global.append(f"G7_sem_profundidade:{inc['name']}")
            continue
        if inc_depth >= own - 0.01:
            # Dono (2026-09-26, revendo o Q2 no portal, cruzamento V301 x
            # V312): vigas de MESMA altura nao se atravessam — cada lateral
            # para na primeira face da outra, como diante da mais profunda.
            info["rule"] = (
                "G7_mesma_profundidade_termina"
                if abs(inc_depth - own) <= 0.01
                else "G7_incidente_mais_profunda_termina"
            )
            hard.append((inc["start"], inc["end"], info))
            continue
        info["own_depth"] = own
        info["rule"] = "G7_incidente_menos_profunda_passa_por_baixo"
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

    # Passa: viga que chega DENTRO de um pilar (V302 no P10 da V309A) nao
    # corta a lateral — o pilar e' englobado inteiro; a viga vira abertura
    # desse segmento e a fronteira vai para a face final do pilar (Q3).
    if pillar_events:
        kept = []
        for c0, c1, info in hard:
            host = next(
                (pl for pl in pillar_events
                 if info.get("type") == "viga" and info.get("embedded_in_pillar", True)
                 and pl["start"] - 0.5 <= c0 and c1 <= pl["end"] + 0.5),
                None,
            )
            if host is None:
                kept.append((c0, c1, info))
                continue
            absorbed = dict(info, rule="G7_viga_dentro_do_pilar_englobada_no_passa",
                            own_depth=_own_depth(scene, c0, c1))
            soft.append((host["end"] if ascending else host["start"], absorbed))
        hard = kept

    # Q3: em Passa nenhuma fronteira cai dentro de pilar — ela vai para a face
    # final do pilar (na ordem de leitura), e o pilar fica inteiro no segmento.
    if pillar_events:
        moved = []
        for pos, info in soft:
            for pillar in pillar_events:
                if info.get("embedded_in_pillar", True) and pillar["start"] + 0.5 < pos < pillar["end"] - 0.5:
                    pos = pillar["end"] if ascending else pillar["start"]
                    info = dict(info, moved_to_pillar_face=pillar["name"])
            moved.append((pos, info))
        soft = moved

    # Pedacos livres = extensao menos cortes duros.
    cuts = sorted((item for item in hard if not measured_passa
                   or (item[1] > ext_start and item[0] < ext_end)), key=lambda item: item[0])
    pieces: list[list[Any]] = []
    cursor = ext_start
    left_info: dict = {"type": "extremidade", "supports": scene.end_supports["start"]}
    for c0, c1, info in cuts:
        if c1 <= cursor + 0.01:
            continue  # corte contido em outro (V312 dentro do P42): a face e' do maior
        if c0 > cursor + minimum_segment:
            pieces.append([cursor, min(c0, ext_end), left_info, info])
        cursor = max(cursor, c1)
        left_info = info
        if cursor >= ext_end:
            break
    if ext_end - cursor > minimum_segment:
        pieces.append([cursor, ext_end, left_info, {"type": "extremidade", "supports": scene.end_supports["end"]}])

    # Fronteiras moles (borda final das aberturas de viga).
    split: list[list[Any]] = []
    for a0, a1, linfo, rinfo in pieces:
        # Abertura encostada numa ponta do pedaco (viga incidente na
        # extremidade: V310 no inicio da V303) pertence ao proprio segmento —
        # nao ha' segmento anterior para recebe-la (contrato §5.2.3).
        inner: dict[float, dict] = {}
        for pos, info in soft:
            if not (a0 + minimum_segment < pos < a1 - minimum_segment):
                continue
            if info["type"] == "viga" and not (
                info["start"] > a0 + minimum_segment and info["end"] < a1 - minimum_segment
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

    def _outside_pillars(a0: float, a1: float) -> list[tuple[float, float]]:
        parts = [(a0, a1)]
        for pl in pillar_events:
            nxt = []
            for x, y in parts:
                if pl["end"] <= x or pl["start"] >= y:
                    nxt.append((x, y))
                    continue
                if pl["start"] > x:
                    nxt.append((x, pl["start"]))
                if pl["end"] < y:
                    nxt.append((pl["end"], y))
            parts = nxt
        return [(x, y) for x, y in parts if y - x > 0.01]

    # Pedaco que, tirando o pilar englobado, nao tem viga (< 10 cm) e' fantasma:
    # a viga nao alcanca aquele pilar (V311 termina na V306; o P28 vem depois).
    if pillar_events:
        split = [
            item for item in split
            if sum(y - x for x, y in _outside_pillars(item[0], item[1])) >= 10.0
            or (measured_passa and any(info.get("type") == "viga"
                                      and info.get("embedded_in_pillar") is False
                                      for info in item[2:]))
        ]

    if not ascending:
        split = [[a0, a1, rinfo, linfo] for a0, a1, linfo, rinfo in reversed(split)]

    segments: list[CellSegment] = []
    section_source = scene.sections
    if measured_passa and scene.sections:
        section_source = [dict(z) for z in sorted(scene.sections, key=lambda z: z["start"])]
        section_source[0]["start"] = min(section_source[0]["start"], ext_start)
        section_source[-1]["end"] = max(section_source[-1]["end"], ext_end)
    for index, (a0, a1, first_info, last_info) in enumerate(split, start=1):
        start, end = (a0, a1) if ascending else (a1, a0)
        zones = [
            {"start": max(z["start"], a0), "end": min(z["end"], a1), "dim": z["dim"],
             "depth": z["depth"], "source": z.get("end_source", "")}
            for z in section_source if z["end"] > a0 + 0.5 and z["start"] < a1 - 0.5
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
        # Trecho sobre pilar englobado (Passa) e' parede CONHECIDA pelo poligono
        # do pilar; a auditoria de linha/cota olha so' a parte fora dos pilares.
        free = _outside_pillars(a0, a1) if pillar_events else [(a0, a1)]
        free_len = sum(y - x for x, y in free)
        if free_len > 0.01:
            seg.line_coverage = round(sum(
                scene.line_coverage(side, x, y) * (y - x) for x, y in free
            ) / free_len, 3)
            seg.dimension_overlap = round(sum(
                scene.dimension_overlap(side, x, y) * (y - x) for x, y in free
            ) / free_len, 3)
        else:
            seg.line_coverage, seg.dimension_overlap = 1.0, 0.0
        if seg.line_coverage < LINE_COVERAGE_MIN:
            seg.flags.append("fora_da_linha_estrutural")
        # Antialucinacao (dono 2026-09-26): segmento sobre LINHA DE COTA e' erro.
        if seg.dimension_overlap > DIMENSION_OVERLAP_MAX:
            seg.flags.append("sobre_linha_de_cota")
        if not zones:
            seg.flags.append("G1_secao_nao_lida")
        if len({z["dim"] for z in zones}) > 1:
            seg.flags.append("G1_degrau_de_secao_no_segmento")
        if behavior == "para":
            # G9: Para recua 11 onde TERMINA na face de pilar — no meio da viga
            # e tambem na ponta (pilar de apoio nao englobado pelo G10).
            lo_stop = abs(a0 - ext_start) < 0.5 and stops_at_pillar["start"]
            hi_stop = abs(a1 - ext_end) < 0.5 and stops_at_pillar["end"]
            start_stop, end_stop = (lo_stop, hi_stop) if ascending else (hi_stop, lo_stop)
            if first_info.get("type") == "pilar" or start_stop:
                seg.adjustment_start = -PILLAR_OPENING_EXTRA
            if last_info.get("type") == "pilar" or end_stop:
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
                external_junction = measured_passa and any(
                    info.get("type") == "viga" and info.get("embedded_in_pillar") is False
                    for info in (first_info, last_info)
                )
                if not external_junction:
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
            full_height = (
                info.get("depth") is not None and info.get("own_depth") is not None
                and info["depth"] >= info["own_depth"] - 0.01
            )
            seg.beam_openings.append({
                "name": info["name"], "dim": info.get("dim", ""),
                "largura": round(width, 2),
                "abertura_largura": round(width + BEAM_OPENING_EXTRA_W, 2),
                "abertura_altura": (
                    round(info["depth"] + BEAM_OPENING_EXTRA_H, 2)
                    if info.get("depth") is not None else None
                ),
                "sobra": (
                    round(max(0.0, info["own_depth"] - info["depth"]), 2)
                    if info.get("depth") is not None and info.get("own_depth") is not None else None
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
            "sobre_cota": seg.dimension_overlap,
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
        "band": {"is_horizontal": scene.is_horizontal, "angle": scene.angle, "t_lo": scene.t_lo, "t_hi": scene.t_hi,
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
    from src.core.lv_beam_scene import _slab_polygons
    slab_polys = _slab_polygons(slabs)
    for beam in owners.values():
        estimate_missing_cell_levels(beam, slab_polys)
    report["__sem_cena__"] = missing
    return report


def _cell_entries(beam: dict):
    for key, slots in (beam.get("links") or {}).items():
        if not (str(key).startswith("viga_") and isinstance(slots, dict)):
            continue
        for entries in slots.values():
            for entry in entries if isinstance(entries, list) else []:
                if isinstance(entry, dict) and isinstance(entry.get("lv_cell"), dict) \
                        and entry.get("geometry_role") == "lateral":
                    yield entry


def estimate_missing_cell_levels(beam: dict, slab_polys: list) -> int:
    """D-61 (dono 2026-09-27) nas celulas LV: segmento sem laje encostada recebe
    nivel ESTIMADO, marcado em ``lv_cell['level_estimado']`` (nunca vira medido).
    Ordem: outro segmento da mesma viga com nivel medido (mesmo lado primeiro,
    o mais perto) -> laje com nivel mais proxima.
    """
    from shapely.geometry import Point

    def _mid(entry):
        pts = entry.get("points") or []
        if len(pts) < 2:
            return None
        return ((pts[0][0] + pts[-1][0]) / 2.0, (pts[0][1] + pts[-1][1]) / 2.0)

    entries = list(_cell_entries(beam))
    measured = [
        e for e in entries
        if e["lv_cell"].get("level") and not e["lv_cell"].get("level_estimado")
    ]
    count = 0
    for entry in entries:
        cell = entry["lv_cell"]
        if cell.get("level"):
            continue
        if _cell_is_frozen(beam, str(entry.get("side") or ""), str(entry.get("behavior") or "").lower()):
            continue  # celula validada por humano nao e' reescrita
        mid = _mid(entry)
        if mid is None:
            continue

        def _dist(other):
            m = _mid(other)
            return ((m[0] - mid[0]) ** 2 + (m[1] - mid[1]) ** 2) ** 0.5 if m else 1e18

        src = None
        for same_side in (True, False):
            pool = [e for e in measured if (e.get("side") == entry.get("side")) == same_side]
            if pool:
                src = min(pool, key=_dist)
                break
        if src is not None:
            cell["level"] = src["lv_cell"]["level"]
            cell["level_estimado"] = {
                "origem": "outro_segmento",
                "de": f"{src.get('contract_id')} seg {src.get('segment_index')}",
            }
            count += 1
            continue
        best = None
        for slab, poly in slab_polys:
            fields = slab.get("fields") or {}
            raw = fields.get("laje_nivel") or slab.get("laje_nivel") or slab.get("nivel")
            if _level_value(raw) is None:
                continue
            d = poly.distance(Point(mid))
            if best is None or d < best[0]:
                best = (d, slab, raw)
        if best is not None:
            cell["level"] = f"{_level_value(best[2]):g}"
            cell["level_estimado"] = {
                "origem": "laje_mais_proxima",
                "laje": str(best[1].get("name") or (best[1].get("fields") or {}).get("nome") or ""),
                "distancia_cm": round(best[0], 1),
            }
            count += 1
    return count


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
