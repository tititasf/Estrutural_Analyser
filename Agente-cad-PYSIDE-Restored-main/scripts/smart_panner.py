#!/usr/bin/env python3
"""
smart_panner.py — Motor de Distribuição de Painéis para Lajes
==============================================================
Engenharia reversa do SmartPanner original (Robo_Lajes/laje_src/services/ai/smart_panner.py).

Constantes calibradas do STOG real (ALIMONTI Paraiso):
  Painel padrão maior:  244 cm
  Painel padrão médio:  122 cm
  Painel padrão menor:   60 cm
  GAP união (sarrafo):   20 cm (preferencial), range 15-30 cm
  Sobra mínima:          60 cm

Uso:
  from smart_panner import distribute_panels
  linhas = distribute_panels(comprimento=2154.4, largura=244.0)
  # linhas = [{"value": 244.0, "is_union": false}, ...]
"""

# ── Constantes de engenharia (eng. reversa) ──────────────────────────────────
PAINEL_GRANDE  = 244.0   # módulo padrão STOG (380 ocorrências vs 53 de 122)
PAINEL_MEDIO   = 122.0   # meio painel
PAINEL_PEQUENO =  60.0   # painel curto
GAP_UNION      =  20.0   # sarrafo de pressão (junção entre painéis)
GAP_MIN        =  15.0
GAP_MAX        =  30.0
SOBRA_MIN      =  60.0   # abaixo disso, agrega no painel anterior
LIMIAR_MENOR   = 200.0   # abaixo: lógica especial de eixo menor


def _distribute_244_rule(total_length):
    """Regra principal: preenche com 244cm até caber.
    Se sobra < 60cm, troca último de 244 por 122.
    Retorna lista de (position, is_union).
    """
    if total_length <= 0:
        return []
    if total_length <= PAINEL_GRANDE:
        return []  # 1 painel único, sem divisão

    positions = []
    x = 0.0
    while x + PAINEL_GRANDE < total_length - 1:
        x += PAINEL_GRANDE
        sobra = total_length - x
        if sobra < SOBRA_MIN and x > PAINEL_GRANDE:
            # Troca último 244 por 122, sobra fica maior
            x -= PAINEL_GRANDE
            x += PAINEL_MEDIO
            positions.append({"value": round(x, 1), "is_union": False})
            x += GAP_UNION
            positions.append({"value": round(x, 1), "is_union": True})
            x += PAINEL_MEDIO
            if x < total_length - 1:
                positions.append({"value": round(x, 1), "is_union": False})
            return positions
        positions.append({"value": round(x, 1), "is_union": False})

    return positions


def _distribute_minor_axis(length):
    """Eixo menor (< 200cm): 1 painel padrão (122 ou 60) + GAP + recorte."""
    if length <= PAINEL_PEQUENO:
        return []  # painel único
    if length <= PAINEL_MEDIO + GAP_UNION:
        return []  # painel único (cabe sem gap)

    # 122 + gap 20 + recorte
    positions = [
        {"value": round(PAINEL_MEDIO, 1), "is_union": False},
    ]
    if length > PAINEL_MEDIO + GAP_UNION + 10:
        positions.append({"value": round(PAINEL_MEDIO + GAP_UNION, 1), "is_union": True})
    return positions


def distribute_panels(comprimento, largura=0.0):
    """
    Calcula distribuição de painéis para uma laje.

    Args:
        comprimento: dimensão X em cm
        largura: dimensão Y em cm (para decidir eixo menor)

    Returns:
        dict com:
          'linhas_verticais': lista de {"value": float, "is_union": bool}
          'linhas_horizontais': lista de {"value": float, "is_union": bool}
    """
    lv = _distribute_244_rule(comprimento)
    lh = []

    if largura > 0:
        if largura < LIMIAR_MENOR:
            lh = _distribute_minor_axis(largura)
        else:
            lh = _distribute_244_rule(largura)

    return {
        'linhas_verticais': lv,
        'linhas_horizontais': lh,
    }


if __name__ == '__main__':
    # Teste rápido
    import json
    tests = [
        (2154.4, 244.0, "L11 grande"),
        (500.0, 180.0, "L5 média"),
        (200.0, 100.0, "L small"),
        (122.0, 60.0, "L tiny"),
    ]
    for comp, larg, desc in tests:
        result = distribute_panels(comp, larg)
        print(f"\n{desc}: {comp}x{larg}cm")
        print(f"  V: {json.dumps(result['linhas_verticais'], ensure_ascii=False)}")
        print(f"  H: {json.dumps(result['linhas_horizontais'], ensure_ascii=False)}")
