"""Plano de corte: peças medidas no N3 → material de compra [2026-09-28].

Convenção do dono (chat 28/09, D-66):
- painéis são cortados de chapa 244 x 122 cm;
- sarrafos são cortados de barra de 3 m na mesma seção (2,2 x 7; variantes
  2,2 x 10 e 2,2 x 5); grades de viga e pilar usam meio pontalete de 3 m.

Heurísticas determinísticas (não ótimas, mas estáveis e explicáveis):
- 1D (barras): First Fit Decreasing; peça maior que a barra vira emenda
  (barras inteiras + resto), e a emenda é contada à parte;
- 2D (chapas): guilhotina com "best short side fit" e rotação livre; peça que
  não cabe na chapa em nenhuma orientação é dividida em faixas de 244/122 e
  contada como emenda.
Sem perda de serra (kerf = 0) e sem % de quebra: o número é o mínimo físico
para cortar o que está desenhado.
"""

from __future__ import annotations

import math

CHAPA_W, CHAPA_H = 244.0, 122.0
BARRA_CM = 300.0


def barras_necessarias(pecas_cm: list[float], barra: float = BARRA_CM) -> dict:
    emendas = 0
    itens: list[float] = []
    for p in pecas_cm:
        if p > barra + 0.05:
            inteiras = int(p // barra)
            resto = p - inteiras * barra
            emendas += 1
            itens += [barra] * inteiras + ([resto] if resto > 0.5 else [])
        else:
            itens.append(p)
    sobras: list[float] = []  # espaço livre de cada barra aberta
    for p in sorted(itens, reverse=True):
        for i, livre in enumerate(sobras):
            if p <= livre + 0.05:
                sobras[i] = livre - p
                break
        else:
            sobras.append(barra - p)
    usado = sum(itens)
    n = len(sobras)
    return {
        "barras": n,
        "comprimento_barra_cm": barra,
        "aproveitamento": round(usado / (n * barra), 3) if n else 0.0,
        "emendas": emendas,
    }


def _encaixa(w: float, h: float, W: float, H: float) -> bool:
    return w <= W + 0.05 and h <= H + 0.05


def chapas_necessarias(pecas: list[tuple]) -> dict:
    """pecas = [(largura, altura[, rotulo, origem]), ...] em cm.

    Devolve também o `layout`: por chapa, onde cada peça é cortada (x, y a
    partir do canto superior esquerdo, já na orientação de corte) e as sobras.
    Peça maior que a chapa vira faixas `7a`, `7b`... (emenda)."""
    emendas = 0
    itens: list[tuple[float, float, str, str]] = []
    for i, pc in enumerate(pecas):
        w, h = float(pc[0]), float(pc[1])
        rotulo = str(pc[2]) if len(pc) > 2 else str(i + 1)
        origem = str(pc[3]) if len(pc) > 3 else ""
        if _encaixa(w, h, CHAPA_W, CHAPA_H) or _encaixa(h, w, CHAPA_W, CHAPA_H):
            itens.append((w, h, rotulo, origem))
            continue
        # Maior que a chapa: faixas pelo lado maior (≤244) e pelo menor (≤122).
        emendas += 1
        a, b = max(w, h), min(w, h)
        na, nb = math.ceil(a / CHAPA_W - 1e-6), math.ceil(b / CHAPA_H - 1e-6)
        k = 0
        for ia in range(na):
            for jb in range(nb):
                itens.append((min(CHAPA_W, a - ia * CHAPA_W), min(CHAPA_H, b - jb * CHAPA_H),
                              f"{rotulo}{chr(97 + k)}", origem))
                k += 1

    # Por chapa: retângulos livres (x, y, W, H) e peças cortadas.
    livres: list[list[tuple[float, float, float, float]]] = []
    cortes: list[list[dict]] = []
    for w, h, rotulo, origem in sorted(itens, key=lambda r: (-max(r[:2]), -min(r[:2]))):
        melhor = None
        for ci, rects in enumerate(livres):
            for ri, (_, _, W, H) in enumerate(rects):
                for pw, ph in ((w, h), (h, w)):
                    if _encaixa(pw, ph, W, H):
                        folga = min(W - pw, H - ph)
                        if melhor is None or folga < melhor[0]:
                            melhor = (folga, ci, ri, pw, ph)
        if melhor is None:
            livres.append([(0.0, 0.0, CHAPA_W, CHAPA_H)])
            cortes.append([])
            ci, ri = len(livres) - 1, 0
            pw, ph = (w, h) if _encaixa(w, h, CHAPA_W, CHAPA_H) else (h, w)
        else:
            _, ci, ri, pw, ph = melhor
        x, y, W, H = livres[ci].pop(ri)
        cortes[ci].append({"rotulo": rotulo, "origem": origem, "x": round(x, 1), "y": round(y, 1),
                           "largura_cm": round(pw, 1), "altura_cm": round(ph, 1),
                           "girado": abs(pw - w) > 0.05})
        # Corte guilhotina pelo eixo da sobra menor (mantém a maior inteira).
        if W - pw < H - ph:
            novos = [(x + pw, y, W - pw, ph), (x, y + ph, W, H - ph)]
        else:
            novos = [(x + pw, y, W - pw, H), (x, y + ph, pw, H - ph)]
        livres[ci] += [r for r in novos if r[2] > 0.5 and r[3] > 0.5]
    area = sum(w * h for w, h, _, _ in itens)
    n = len(livres)
    layout = []
    for ci in range(n):
        usada = sum(c["largura_cm"] * c["altura_cm"] for c in cortes[ci])
        layout.append({
            "chapa": ci + 1,
            "aproveitamento": round(usada / (CHAPA_W * CHAPA_H), 3),
            "pecas": cortes[ci],
            "sobras": [{"x": round(x, 1), "y": round(y, 1), "largura_cm": round(W, 1),
                        "altura_cm": round(H, 1)} for x, y, W, H in livres[ci]],
        })
    return {
        "chapas": n,
        "chapa_cm": [CHAPA_W, CHAPA_H],
        "aproveitamento": round(area / (n * CHAPA_W * CHAPA_H), 3) if n else 0.0,
        "emendas": emendas,
        "layout": layout,
    }


def material_da_bitola(bitola: str) -> str:
    """Nome de compra da barra que corta a peça daquela bitola."""
    b = bitola.lower()
    if "3.5" in b:
        return "Meio pontalete (barra 3 m)"
    if "press" in b:
        return "Sarrafo 2,2 x 7 cm (barra 3 m)"  # a confirmar com o dono
    return bitola.replace(".", ",") + " (barra 3 m)"


def compra_de_grupos(grupos: list[dict]) -> dict:
    """Material de compra de 1 item: as peças de todos os grupos saem do
    mesmo estoque (sobra de um lado corta peça do outro)."""
    paineis: list[tuple] = []
    por_material: dict[str, list[float]] = {}
    numero = 0
    for g in grupos:
        if not g.get("disponivel"):
            continue
        # Numeração única dos painéis no item (1..N), gravada na linha da
        # lista (`numeros`) para casar com o rótulo no desenho da chapa.
        for p in g.get("paineis") or []:
            nums = list(range(numero + 1, numero + int(p["quantidade"]) + 1))
            numero += len(nums)
            p["numeros"] = nums
            origem = g["titulo"] + (f" · face {p['face']}" if p.get("face") else "")
            paineis += [(p["largura_cm"], p["altura_cm"], n, origem) for n in nums]
        for s in g.get("sarrafos") or []:
            mat = material_da_bitola(s["bitola"])
            for c in s["cortes"]:
                por_material.setdefault(mat, []).extend([c["comprimento_cm"]] * int(c["quantidade"]))
    out: dict = {"chapas": None, "barras": []}
    if paineis:
        out["chapas"] = {"material": "Chapa compensado 244 x 122 cm", **chapas_necessarias(paineis)}
    for mat, pecas in sorted(por_material.items()):
        out["barras"].append({"material": mat, "pecas": len(pecas),
                              "total_m": round(sum(pecas) / 100, 2), **barras_necessarias(pecas)})
    return out
