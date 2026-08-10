#!/usr/bin/env python3
"""
smart_panner.py — Motor de Distribuição de Painéis para Lajes (Completo)
=========================================================================
Engenharia reversa COMPLETA do SmartPanner original
(Robo_Lajes/laje_src/services/ai/smart_panner.cpython-312.pyc).

7 métodos decompilados:
  suggest_layout        — entry point: decide eixo maior vs menor
  _distribute_244_rule  — eixo maior: 244 em 244, sobra < 60 → troca por 122
  _distribute_minor_axis — eixo menor < 200: small_side → align → elastic → greedy
  _distribute_small_side — 1 painel (122 ou 60) + GAP 20 + recorte
  _try_align_deformity  — alinha painel com borda de obstáculo
  _distribute_elastic   — 122/60 com uniões 15-30cm, score otimizado
  _distribute_greedy_fallback — fallback: 122 + gap 20

Constantes calibradas: 244/122/60cm, GAP 20 (15-30), SOBRA_MIN 60, LIMIAR 200
"""

# ── Constantes de engenharia (decompiladas do .pyc) ──────────────────────────
PAINEL_GRANDE  = 244.0
PAINEL_MEDIO   = 122.0
PAINEL_PEQUENO =  60.0
GAP_UNION      =  20.0
GAP_MIN        =  15.0
GAP_MAX        =  30.0
SOBRA_MIN      =  60.0
LIMIAR_MENOR   = 200.0


def panel_fits_sheet(side_a: float, side_b: float, tol: float = 0.51) -> bool:
    """Chapa NOVA 244×122 cm (pode girar).

    Regra inegociável: max(lados) ≤ 244 e min(lados) ≤ 122.
    Ex.: 244×122 OK · 244×169 FAIL · 238×122 OK · 169×122 OK.
    """
    a = float(side_a)
    b = float(side_b)
    if a <= 0.01 or b <= 0.01:
        return True
    return max(a, b) <= PAINEL_GRANDE + tol and min(a, b) <= PAINEL_MEDIO + tol


def _segments_from_lines(lines, total):
    """Lista (comprimento, is_union) dos trechos ao longo de um eixo."""
    items = sorted(
        (float(line.get("value", 0)), bool(line.get("is_union", False)))
        for line in (lines or [])
        if isinstance(line, dict)
    )
    edges = [0.0] + [v for v, _u in items] + [float(total)]
    # dedupe mantendo ordem
    clean = []
    for edge in edges:
        if not clean or abs(edge - clean[-1]) > 0.05:
            clean.append(edge)
    if len(clean) < 2:
        return [(float(total), False)] if float(total) > 0.01 else []

    line_at = {round(v, 1): u for v, u in items}
    segs = []
    for a, b in zip(clean, clean[1:]):
        length = b - a
        if length <= 0.05:
            continue
        end_union = bool(line_at.get(round(b, 1), False))
        is_union = end_union and (GAP_MIN - 1.0) <= length <= (GAP_MAX + 1.0)
        segs.append((length, is_union))
    return segs


def cells_fit_sheet(lv, lh, comprimento, largura, tol: float = 0.51) -> bool:
    """True se todas as células não-união cabem na chapa 244×122."""
    sx = _segments_from_lines(lv, comprimento) or [(float(comprimento), False)]
    sy = _segments_from_lines(lh, largura) or [(float(largura), False)]
    for w, wu in sx:
        for h, hu in sy:
            if wu or hu:
                continue
            if not panel_fits_sheet(w, h, tol=tol):
                return False
    return True


def _distribute_cap_medio(total_length):
    """Divide o eixo da face 122 cm: nenhum painel (não-união) > 122.

    Usado no eixo menor / quando o outro eixo já tem chapas de 244, para
    nunca gerar célula 244×169 (ou pior).
    """
    total = float(total_length)
    if total <= PAINEL_MEDIO + 0.01:
        return []

    lines = []
    pos = 0.0
    rem = total
    guard = 0
    while rem > PAINEL_MEDIO + 0.01 and guard < 40:
        guard += 1
        # Coloca chapa 122
        pos = round(pos + PAINEL_MEDIO, 1)
        lines.append({"value": pos, "is_union": False})
        rem = round(total - pos, 6)
        if rem <= PAINEL_MEDIO + 0.01:
            break
        # Ainda cabe mais painel: separa com união 20
        if rem > GAP_UNION + 0.01:
            pos = round(pos + GAP_UNION, 1)
            lines.append({"value": pos, "is_union": True})
            rem = round(total - pos, 6)
        else:
            break
    return lines


def _distribute_narrow_strip(length):
    """Divide tiras ate 75 cm sem gerar meia-medida desnecessaria."""
    if length <= PAINEL_PEQUENO:
        return []
    half = length / 2.0
    split = round(half / 5.0) * 5.0
    split = max(30.0, min(split, length - 30.0))
    split = round(split, 1)
    if abs(split - round(split)) < 1e-6:
        split = float(int(round(split)))
    return [{"value": split, "is_union": False}]


def _distribute_244_rule(total_length):
    """Eixo maior: distribui 244 em 244. Se sobra < 60, troca último 244 por 122."""
    if total_length <= 0.01:
        return []
    lines = []
    remaining = total_length
    step = PAINEL_GRANDE

    while remaining > step + 0.01:
        lines.append({"value": round(total_length - remaining + step, 1), "is_union": False})
        remaining -= step

    # Se sobra < 60, troca último de 244 para 122
    if remaining < SOBRA_MIN and len(lines) >= 1:
        last = lines[-2] if len(lines) >= 2 else None
        lines = lines[:-1]  # remove último
        # Recalcula com 122
        pos = lines[-1]["value"] if lines else 0.0
        lines.append({"value": round(pos + PAINEL_MEDIO - PAINEL_GRANDE + step, 1) if last else round(PAINEL_MEDIO, 1), "is_union": False})

    return lines


def _distribute_small_side(length):
    """Para < 200cm: 1 painel padrão (122 ou 60) + GAP 20 + Recorte."""
    GAP = GAP_UNION
    if length <= PAINEL_PEQUENO:
        return []

    # Faixas estreitas ate 90 cm usam uma divisao limpa perto do meio; acima
    # disso ja cabe preferir um painel de 60 cm e deixar a sobra no vizinho.
    if length <= 90.0:
        return _distribute_narrow_strip(length)

    # Quando o vão comporta uma faixa pequena de 61 cm e uma união, ancora
    # essas duas faixas na borda final. Isso preserva uma peça ampla no início.
    if 163.0 <= length < LIMIAR_MENOR:
        small_panel = 61.0
        first = length - GAP - small_panel
        return [
            {"value": round(first, 1), "is_union": False},
            {"value": round(first + GAP, 1), "is_union": True},
        ]

    # Tenta 122
    available = length - GAP
    if available >= PAINEL_MEDIO - 0.1:
        return [{"value": round(PAINEL_MEDIO, 1), "is_union": False}]

    # Tenta 60
    if available >= PAINEL_PEQUENO - 0.1:
        return [{"value": round(PAINEL_PEQUENO, 1), "is_union": False}]

    # Recorte único
    rem = length - GAP
    if rem > 40:
        return [{"value": round(rem, 1), "is_union": False}]
    return []


def _try_align_deformity(length, obstaculos, axis):
    """Alinha painel com borda de obstáculo relevante."""
    if not obstaculos:
        return None

    relevant_edges = []
    for obs in obstaculos:
        coords = obs.get('coords', obs)
        if isinstance(coords, dict):
            p = coords.get('x', 0) if axis == 'x' else coords.get('y', 0)
            min_c = p
            max_c = p + (coords.get('width', 0) if axis == 'x' else coords.get('height', 0))
        else:
            continue

        if min_c > 10:
            relevant_edges.append(min_c)
        if max_c > 10:
            relevant_edges.append(max_c)

    if not relevant_edges:
        return None

    relevant_edges = sorted(relevant_edges)
    target = relevant_edges[0]

    # Painel até a borda do obstáculo
    if target > PAINEL_MEDIO and target < length - 10:
        p1 = target
        remainder = length - target
        rest_dist = _distribute_greedy_fallback(remainder)
        return [{"value": round(p1, 1), "is_union": False}] + \
               [{"value": round(p1 + r["value"], 1), "is_union": r["is_union"]} for r in rest_dist]

    return None


def _distribute_elastic(total_length, obstaculos=None, axis='x'):
    """Regra elástica: painéis 122/60 com uniões 15-30cm, score otimizado."""
    # Vão 304–366: antes era 122 + união + residual (ex. 169 em 311).
    # Residual > 122 com o outro eixo em 244 gera célula 244×169 — proibido.
    # Cap na face 122: 122 + união + 122 + residual ≤ 122 (ex. 311 → … + 47).
    if 304.0 <= total_length < 366.0:
        return _distribute_cap_medio(total_length)

    # Um painel médio, união e painel pequeno; o recorte residual fecha o vão.
    if 264.0 <= total_length < 304.0:
        return [
            {"value": PAINEL_MEDIO, "is_union": False},
            {"value": PAINEL_MEDIO + GAP_UNION, "is_union": True},
            {"value": PAINEL_MEDIO + GAP_UNION + PAINEL_PEQUENO, "is_union": False},
        ]

    # Três painéis médios: distribuir igualmente a folga em duas uniões.
    if 3 * PAINEL_MEDIO + 2 * GAP_MIN <= total_length <= 3 * PAINEL_MEDIO + 2 * GAP_MAX:
        gap = (total_length - 3 * PAINEL_MEDIO) / 2.0
        return [
            {"value": PAINEL_MEDIO, "is_union": False},
            {"value": round(PAINEL_MEDIO + gap, 1), "is_union": True},
            {"value": round(2 * PAINEL_MEDIO + gap, 1), "is_union": False},
            {"value": round(2 * PAINEL_MEDIO + 2 * gap, 1), "is_union": True},
        ]

    solutions = []
    min_p = int(PAINEL_PEQUENO)   # 60
    max_p = int(PAINEL_MEDIO)     # 122

    for p in range(min_p, max_p + 1):
        required_panel_len = p
        remainder = total_length
        score = 0
        gap = GAP_UNION
        sol_steps = []

        i = 0
        while remainder > required_panel_len + gap + 0.1:
            sol_steps.append({"value": round(total_length - remainder + required_panel_len, 1),
                              "is_union": False})
            remainder -= required_panel_len
            # Gap
            if remainder > gap + min_p:
                sol_steps.append({"value": round(total_length - remainder + gap, 1),
                                  "is_union": True})
                remainder -= gap
            i += 1
            if i > 20:
                break

        # Score: prefer gap close to 20, panels close to 122
        s = abs(gap - GAP_UNION) + abs(required_panel_len - PAINEL_MEDIO) * 0.1
        score = -s  # higher is better (less deviation)
        solutions.append((score, sol_steps))

    if not solutions:
        return _distribute_greedy_fallback(total_length)

    # Sort by score descending, pick best
    solutions.sort(key=lambda x: x[0], reverse=True)

    # Filter valid (at least 1 step)
    valid_solutions = [(s, steps) for s, steps in solutions if steps]
    if valid_solutions:
        best_sol = valid_solutions[0][1]
        return best_sol

    return _distribute_greedy_fallback(total_length)


def _distribute_greedy_fallback(total_length):
    """Fallback: 122 + gap 20 repetidamente."""
    steps = []
    rem = total_length
    while rem > PAINEL_MEDIO + GAP_UNION:
        val = min(PAINEL_MEDIO, rem - GAP_UNION)
        steps.append({"value": round(total_length - rem + val, 1), "is_union": False})
        rem -= val
        gap = min(GAP_UNION, rem)
        if rem > gap + 10:
            steps.append({"value": round(total_length - rem + gap, 1), "is_union": True})
            rem -= gap
    return steps


def _distribute_minor_axis(length, obstaculos=None, axis='y'):
    """Eixo menor (< 200cm): tenta small_side → align → elastic → greedy."""
    if length < LIMIAR_MENOR:
        result = _distribute_small_side(length)
        if result:
            return result

    # Tenta alinhar com obstáculo
    if obstaculos:
        aligned_dist = _try_align_deformity(length, obstaculos, axis)
        if aligned_dist:
            return aligned_dist

    # Elástico
    return _distribute_elastic(length, obstaculos, axis)


def distribute_panels(comprimento, largura=0.0, obstaculos=None):
    """
    Entry point: calcula distribuição de painéis para uma laje.

    Lógica do SmartPanner original (decompilado):
      - Eixo maior (>= 200cm): _distribute_244_rule
      - Eixo menor (< 200cm): _distribute_minor_axis (small → align → elastic → greedy)
      - Se ambos >= 200: ambos usam 244_rule

    Args:
        comprimento: dimensão X em cm
        largura: dimensão Y em cm
        obstaculos: lista de dicts com coords de obstáculos

    Returns:
        dict: linhas_verticais + linhas_horizontais
    """
    obs = obstaculos or []

    # Tiras de até 75 cm são bipartidas no eixo estreito. No eixo longo segue
    # valendo a regra de chapas de 244 cm.
    if 0 < largura <= 75.0:
        return {
            'linhas_verticais': (
                [{"value": round(comprimento / 2.0, 1), "is_union": False}]
                if comprimento <= PAINEL_GRANDE else _distribute_244_rule(comprimento)
            ),
            'linhas_horizontais': _distribute_narrow_strip(largura),
        }
    if 0 < comprimento <= 75.0:
        return {
            'linhas_verticais': _distribute_narrow_strip(comprimento),
            'linhas_horizontais': (
                [{"value": round(largura / 2.0, 1), "is_union": False}]
                if largura <= PAINEL_GRANDE else _distribute_244_rule(largura)
            ),
        }

    # Determinar eixo maior
    is_horizontal_major = comprimento >= largura

    def _is_continuous_narrow_strip(minor: float) -> bool:
        """Tira sem junta transversal — face curta já é 1 chapa e não pede bipartição.

        - ≤90 cm: deixa ``_distribute_small_side`` bipartir (meia-medida limpa).
        - 90–122 cm: um painel único na face 122, sem linha artificial.
        - >122 cm: proibido (geraria 244×169 etc.); usa cap-médio.
        """
        return 90.0 < minor <= PAINEL_MEDIO + 0.01

    def _continuous_strip_hlaz(minor: float, major: float, axis: str):
        """Faixa de uniao de uma tira continua, em coordenadas locais."""
        strip_start = round(max(0.0, minor - GAP_UNION - (PAINEL_PEQUENO + 1.0)), 1)
        if axis == 'y':
            return [{"x": 0.0, "y": strip_start, "width": round(major, 1), "height": GAP_UNION}]
        return [{"x": strip_start, "y": 0.0, "width": GAP_UNION, "height": round(major, 1)}]

    if is_horizontal_major:
        lv = _distribute_244_rule(comprimento)
        continuous_strip = _is_continuous_narrow_strip(largura)
        lh = (
            [] if continuous_strip
            else _distribute_minor_axis(largura, obs, 'y') if largura > 0 else []
        )
        hlaz = _continuous_strip_hlaz(largura, comprimento, 'y') if continuous_strip else []
    else:
        lh = _distribute_244_rule(largura)
        continuous_strip = _is_continuous_narrow_strip(comprimento)
        lv = (
            [] if continuous_strip
            else _distribute_minor_axis(comprimento, obs, 'x') if comprimento > 0 else []
        )
        hlaz = _continuous_strip_hlaz(comprimento, largura, 'x') if continuous_strip else []

    # Gate final: se alguma célula não cabe na chapa 244×122, recorta o eixo
    # que tem face > 122 com a regra cap-médio (nunca 244×169).
    if not cells_fit_sheet(lv, lh, comprimento, largura):
        sx = _segments_from_lines(lv, comprimento) or [(float(comprimento), False)]
        sy = _segments_from_lines(lh, largura) or [(float(largura), False)]
        x_has_wide = any((not u) and length > PAINEL_MEDIO + 0.5 for length, u in sx)
        y_has_wide = any((not u) and length > PAINEL_MEDIO + 0.5 for length, u in sy)
        if x_has_wide and y_has_wide:
            # Ambos eixos com face > 122: o menor usa cap 122; o maior mantém 244.
            if comprimento >= largura:
                lh = _distribute_cap_medio(largura) if largura > 0 else []
            else:
                lv = _distribute_cap_medio(comprimento) if comprimento > 0 else []
            hlaz = []
        elif y_has_wide:
            lh = _distribute_cap_medio(largura) if largura > 0 else []
            hlaz = []
        elif x_has_wide:
            lv = _distribute_cap_medio(comprimento) if comprimento > 0 else []
            hlaz = []

    return {
        'linhas_verticais': lv,
        'linhas_horizontais': lh,
        'hlaz': hlaz,
    }


if __name__ == '__main__':
    import json
    tests = [
        (2154.4, 244.0, [], "L11 grande (2154x244)"),
        (500.0, 180.0, [], "L5 média (500x180)"),
        (413.0, 423.0, [], "L1 real (413x423)"),
        (1887.0, 152.0, [], "L17 strip (1887x152)"),
        (200.0, 100.0, [], "L small (200x100)"),
        (122.0, 60.0, [], "L tiny (122x60)"),
        (300.0, 150.0, [{"x": 80, "y": 0, "width": 40, "height": 150}], "L com obstáculo"),
    ]
    for comp, larg, obs, desc in tests:
        result = distribute_panels(comp, larg, obs)
        print(f"\n{desc}:")
        print(f"  V: {json.dumps(result['linhas_verticais'], ensure_ascii=False)}")
        print(f"  H: {json.dumps(result['linhas_horizontais'], ensure_ascii=False)}")
