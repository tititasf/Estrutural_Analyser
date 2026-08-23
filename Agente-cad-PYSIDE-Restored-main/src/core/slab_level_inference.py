"""Seleção conservadora de níveis de laje derivados de cortes e da planta."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def select_supported_cut_delta(
    candidates: list[dict[str, Any]], *, tolerance_cm: float = 0.25,
) -> dict[str, Any] | None:
    """Aceita fonte humana ou consenso independente; nunca encadeia palpite único.

    Um nível inferido usado como origem de outro delta tem confiança 0.55. Um
    único encadeamento desses pode deslocar uma laje em um pavimento inteiro.
    Duas fontes de corte independentes que chegam ao mesmo valor constituem
    consenso geométrico e podem ser aceitas.
    """
    usable = [row for row in candidates or [] if row.get("value") is not None]
    if not usable:
        return None
    direct = [row for row in usable if row.get("human_source") or float(row.get("confidence") or 0) >= 0.80]
    if direct:
        return sorted(direct, key=lambda row: float(row.get("confidence") or 0), reverse=True)[0]

    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    scale = 1.0 / max(float(tolerance_cm), 0.01)
    for row in usable:
        groups[round(float(row["value"]) * scale)].append(row)
    supported = [
        rows for rows in groups.values()
        if len({str(row.get("source_slab") or "") for row in rows}) >= 2
    ]
    if not supported:
        return None
    supported.sort(key=lambda rows: (len(rows), max(float(row.get("confidence") or 0) for row in rows)), reverse=True)
    return sorted(supported[0], key=lambda row: float(row.get("confidence") or 0), reverse=True)[0]


def _point_in_ring(ring: list[tuple[float, float]], point: tuple[float, float]) -> bool:
    x, y = point
    inside = False
    count = len(ring)
    for index in range(count):
        x1, y1 = ring[index]
        x2, y2 = ring[(index + 1) % count]
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
    return inside


def _ring(points: Any) -> list[tuple[float, float]]:
    try:
        ring = [(float(p[0]), float(p[1])) for p in points or []]
    except (TypeError, ValueError, IndexError):
        return []
    if len(ring) > 1 and math.dist(ring[0], ring[-1]) <= 1e-6:
        ring.pop()
    return ring if len(ring) >= 3 else []


def plausible_level_candidates(
    candidates: list[dict[str, Any]],
    *,
    reference_level: float | None = None,
    floor_height: float | None = None,
    fraction_of_floor: float = 0.25,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separa candidatos plausíveis dos distantes demais para o pavimento.

    Uma laje pode legitimamente estar em outro nível dentro do mesmo pavimento
    — rebaixo é rotina. O que não pode é adotar um valor a uma distância da
    ordem de um pé-direito, que só existe em outro pavimento ou em outra vista.

    A referência é o nível do pavimento, **nunca** a mediana dos candidatos da
    própria laje: quando todos os candidatos são cotas de dimensão, a mediana
    também é lixo e o filtro não separa nada. Sem referência e sem altura o
    conjunto passa inteiro, porque a escala do desenho não estaria estabelecida.
    """
    usable = [row for row in candidates or [] if row.get("value") is not None]
    if not usable or reference_level is None or not floor_height:
        return usable, []
    window = abs(float(floor_height)) * fraction_of_floor
    near, far = [], []
    for row in usable:
        target = near if abs(float(row["value"]) - float(reference_level)) <= window else far
        target.append(row)
    return near, far


def select_plan_level_annotation(
    slab_points: Any,
    candidates: list[dict[str, Any]],
    *,
    label_pos: tuple[float, float] | None = None,
    reference_level: float | None = None,
    floor_height: float | None = None,
    label_radius: float | None = None,
) -> dict[str, Any] | None:
    """Escolhe a anotação de nível da laje priorizando proveniência geométrica.

    Ordem de autoridade:

    1. ``contida`` — a anotação está dentro do contorno da laje. É a única que
       prova, pela geometria, que o nível se refere àquela laje;
    2. ``contida_ambigua`` — mais de uma anotação dentro do contorno: devolve a
       mais próxima do centro e registra as concorrentes;
    3. ``proximidade`` — nenhuma anotação dentro do contorno; cai para a mais
       próxima do rótulo, marcada como fraca para revisão humana.

    Cada candidato é ``{"value": float, "text": str, "pos": (x, y), ...}``.
    Candidatos implausíveis para o pavimento são descartados antes da escolha.
    """
    near, far = plausible_level_candidates(
        candidates, reference_level=reference_level, floor_height=floor_height,
    )
    if not near:
        return None
    ring = _ring(slab_points)
    contained = [row for row in near if ring and _point_in_ring(ring, tuple(row["pos"]))]

    def result(row, provenance, alternatives=()):
        return {
            **row,
            "provenance": provenance,
            "alternatives": [alt.get("text") for alt in alternatives],
            "discarded_out_of_range": [alt.get("text") for alt in far],
            "needs_human_review": provenance == "proximidade",
        }

    if len(contained) == 1:
        return result(contained[0], "contida")
    if contained:
        center = (
            sum(x for x, _ in ring) / len(ring),
            sum(y for _, y in ring) / len(ring),
        )
        ordered = sorted(contained, key=lambda row: math.dist(center, tuple(row["pos"])))
        return result(ordered[0], "contida_ambigua", ordered[1:])
    if label_pos is None:
        return None
    nearest = min(near, key=lambda row: math.dist(tuple(label_pos), tuple(row["pos"])))
    if label_radius is not None and math.dist(tuple(label_pos), tuple(nearest["pos"])) > label_radius:
        # Sem anotação no contorno e sem anotação perto do rótulo, não há base
        # geométrica nenhuma. Devolver a mais próxima do plano inteiro seria
        # inventar vínculo; quem chama mantém o valor que já tinha e sinaliza.
        return None
    return result(nearest, "proximidade")


def point_inside_ring(points: Any, point: tuple[float, float]) -> bool:
    """Ponto dentro do contorno fechado, ignorando repetição de fechamento."""
    ring = _ring(points)
    if not ring:
        return False
    return _point_in_ring(ring, (float(point[0]), float(point[1])))


#: Vão (cm) que ainda conta como vizinhança entre lajes: a viga que as separa.
NEIGHBOUR_GAP_CM = 25.0
#: Vantagem mínima de votos para herdar. Uma laje de canto tem poucas
#: vizinhas, e maioria de um voto só é frágil.
MIN_VOTE_MARGIN = 2
#: Folga (cm) para duas lajes contarem como a MESMA faixa de painel.
STRIP_MATCH_TOL_CM = 3.0
#: Só herda quem tem nível vindo de palpite por proximidade. Laje sem
#: evidência local nenhuma fica com o valor do banco, que carrega o resto do
#: pipeline de nível — `L303` e `L307` dependem disso.
INHERITABLE_PROVENANCE = ("proximidade",)


def _bbox(points: Any) -> tuple[float, float, float, float] | None:
    ring = _ring(points)
    if not ring:
        return None
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _are_neighbours(a, b, gap: float) -> bool:
    """Lajes lado a lado, aceitando a viga que passa entre elas."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    dx = max(bx0 - ax1, ax0 - bx1, 0.0)
    dy = max(by0 - ay1, ay0 - by1, 0.0)
    if dx > gap or dy > gap:
        return False
    # Encostadas num eixo e sobrepostas no outro: painéis da mesma fileira.
    overlap_x = min(ax1, bx1) - max(ax0, bx0)
    overlap_y = min(ay1, by1) - max(ay0, by0)
    return (dx <= gap and overlap_y > 0) or (dy <= gap and overlap_x > 0)


def _continues_strip(a, b, gap: float, tol: float = STRIP_MATCH_TOL_CM) -> bool:
    """A vizinha **continua a mesma faixa de painel**, em vez de ficar acima.

    Painel de laje é uma faixa entre duas vigas: comprido num eixo, estreito
    no outro. Quem continua a faixa encosta pelo lado **comprido** e tem a
    mesma largura; quem está na fileira de cima encosta pelo lado estreito.
    A distinção decide `L328` (segue `L327`/`L329`, 852.12) contra a vizinha
    empilhada `L321`, que está noutro nível.
    """
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    if (ax1 - ax0) >= (ay1 - ay0):
        return (
            max(bx0 - ax1, ax0 - bx1, 0.0) <= gap
            and abs(by0 - ay0) <= tol and abs(by1 - ay1) <= tol
        )
    return (
        max(by0 - ay1, ay0 - by1, 0.0) <= gap
        and abs(bx0 - ax0) <= tol and abs(bx1 - ax1) <= tol
    )


def _inherit_from_strip(
    name: str,
    box,
    boxes: dict,
    levels: dict[str, str],
    provenance: dict[str, str],
    gap: float,
) -> tuple[str, list[str]] | None:
    """Nível vindo de quem continua a **mesma faixa de painel**, sem rival.

    Vale só onde o nível atual é palpite por proximidade — a evidência mais
    fraca da escala. `L328` sai 852.19 por proximidade enquanto `L327` e
    `L329`, que continuam a faixa dela, trazem 852.12 anotado dentro do
    contorno; a vizinha empilhada `L321` está noutra fileira e noutro nível.
    """
    fontes = [
        other for other, other_box in boxes.items()
        if other != name
        and provenance.get(other) in ("contida", "contida_ambigua")
        and levels.get(other)
        and _continues_strip(box, other_box, gap)
    ]
    valores = {levels[other] for other in fontes}
    if len(valores) != 1:
        return None
    return valores.pop(), sorted(fontes)


def inherit_level_from_neighbours(
    slab_points_map: dict,
    levels: dict[str, str],
    provenance: dict[str, str],
    *,
    gap: float = NEIGHBOUR_GAP_CM,
) -> dict[str, tuple[str, list[str]]]:
    """Nível de laje sem anotação própria, herdado do painel vizinho.

    Uma laje que não traz anotação continua o nível de quem está ao lado. Só
    herda de vizinha com anotação **dentro do contorno**, a prova forte.

    O critério é **maioria com vantagem**, não unanimidade: uma laje faz
    fronteira com a fileira de cima e a de baixo, e a de cima pode estar noutro
    nível. Exigir unanimidade não herdava nada (medido: 0 de 10). Maioria
    simples herda demais — decide por um voto e erra. A vantagem mínima deixa
    passar só o caso claro.

    Palpite por **proximidade** é evidência mais fraca ainda: ali a faixa de
    painel decide sozinha, sem entrar nesta votação (`_inherit_from_strip`).
    """
    from collections import Counter
    boxes = {
        name: box for name, box in (
            (name, _bbox(points)) for name, points in (slab_points_map or {}).items()
        ) if box
    }
    inherited: dict[str, tuple[str, list[str]]] = {}
    for name, box in boxes.items():
        if provenance.get(name) not in (None, "", "sem_evidencia_local", "proximidade"):
            continue
        if provenance.get(name) == "proximidade":
            strip = _inherit_from_strip(name, box, boxes, levels, provenance, gap)
            if strip:
                inherited[name] = strip
            continue
        fontes = [
            other for other, other_box in boxes.items()
            if other != name
            and provenance.get(other) in ("contida", "contida_ambigua")
            and levels.get(other)
            and _are_neighbours(box, other_box, gap)
        ]
        contagem = Counter(levels[other] for other in fontes).most_common()
        valores = (
            {contagem[0][0]}
            if contagem and (
                len(contagem) == 1
                or contagem[0][1] - contagem[1][1] >= MIN_VOTE_MARGIN
            )
            else set()
        )
        if len(valores) == 1:
            inherited[name] = (valores.pop(), sorted(fontes))
    return inherited
