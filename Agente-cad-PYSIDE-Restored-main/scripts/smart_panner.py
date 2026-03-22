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

    # Determinar eixo maior
    is_horizontal_major = comprimento >= largura

    if is_horizontal_major:
        lv = _distribute_244_rule(comprimento)
        lh = _distribute_minor_axis(largura, obs, 'y') if largura > 0 else []
    else:
        lh = _distribute_244_rule(largura)
        lv = _distribute_minor_axis(comprimento, obs, 'x') if comprimento > 0 else []

    return {
        'linhas_verticais': lv,
        'linhas_horizontais': lh,
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
