"""Plano de corte: peças medidas no N3 → material de compra [2026-09-28].

Convenção do dono (chat 28/09, D-66):
- painéis são cortados de chapa 244 x 122 cm;
- sarrafos são cortados de barra de 3 m na mesma seção (2,2 x 7; variantes
  2,2 x 10 e 2,2 x 5); grades de viga e pilar usam meio pontalete de 3 m;
- **cada corte consome 1 cm**, na chapa (horizontal ou vertical) e na barra:
  102 + 20 não sai de uma faixa de 122 — no máximo 102 + 19.

Otimização (determinística — mesma entrada, mesmo plano):
- 2D (chapas): guilhotina com rotação livre, rodada em várias estratégias
  (ordem das peças × regra de encaixe × direção do corte). Vence a que usa
  MENOS chapas; no empate, a que deixa a sobra concentrada em pedaços maiores
  (sobra grande é reaproveitável, retalho não). Para cedo se atingir o limite
  inferior de área.
- 1D (barras): Best Fit Decreasing e First Fit Decreasing; vence a de menos
  barras.
Peça maior que a chapa/barra vira emenda (faixas `4a`, `4b`...). Sem % de quebra.
"""

from __future__ import annotations

import math

CHAPA_W, CHAPA_H = 244.0, 122.0
PERDA_CORTE = 1.0  # cm consumidos por corte (chapa e barra)
BARRA_CM = 300.0
_EPS = 0.05


# ─── 1D: barras ──────────────────────────────────────────────────────────────

def _barras(itens: list[float], barra: float, best_fit: bool) -> list[float]:
    """Espaço livre de cada barra aberta. Peça que não ocupa a barra até o fim
    exige um corte: consome a peça + PERDA_CORTE."""
    livres: list[float] = []
    for p in sorted(itens, reverse=True):
        cabe = [i for i, L in enumerate(livres) if p <= L + _EPS]
        if cabe:
            i = min(cabe, key=lambda j: livres[j]) if best_fit else cabe[0]
        else:
            livres.append(barra)
            i = len(livres) - 1
        livres[i] = max(0.0, livres[i] - p - PERDA_CORTE)
    return livres


def barras_necessarias(pecas_cm: list[float], barra: float = BARRA_CM) -> dict:
    emendas = 0
    itens: list[float] = []
    for p in pecas_cm:
        if p > barra + _EPS:
            inteiras = int(p // barra)
            resto = p - inteiras * barra
            emendas += 1
            itens += [barra] * inteiras + ([resto] if resto > 0.5 else [])
        else:
            itens.append(p)
    livres = min((_barras(itens, barra, bf) for bf in (True, False)), key=len)
    n = len(livres)
    return {
        "barras": n,
        "comprimento_barra_cm": barra,
        "perda_corte_cm": PERDA_CORTE,
        "aproveitamento": round(sum(itens) / (n * barra), 3) if n else 0.0,
        "emendas": emendas,
    }


# ─── 2D: chapas ──────────────────────────────────────────────────────────────

def _encaixa(w: float, h: float, W: float, H: float) -> bool:
    return w <= W + _EPS and h <= H + _EPS


_ORDENS = {
    "area": lambda r: (-r[0] * r[1], -max(r[0], r[1])),
    "lado_maior": lambda r: (-max(r[0], r[1]), -min(r[0], r[1])),
    "lado_menor": lambda r: (-min(r[0], r[1]), -max(r[0], r[1])),
    "perimetro": lambda r: (-(r[0] + r[1]), -max(r[0], r[1])),
    "altura": lambda r: (-r[1], -r[0]),
}
_ENCAIXES = {
    "lado_curto": lambda W, H, w, h: (min(W - w, H - h), max(W - w, H - h)),
    "lado_longo": lambda W, H, w, h: (max(W - w, H - h), min(W - w, H - h)),
    "area": lambda W, H, w, h: (W * H - w * h, min(W - w, H - h)),
}
_DIVISOES = ("sobra_menor", "sobra_maior", "horizontal", "vertical")


def _cortar(W: float, H: float, pw: float, ph: float, divisao: str) -> bool:
    """True = corte vertical primeiro (a sobra à direita fica com altura cheia)."""
    if divisao == "horizontal":
        return False
    if divisao == "vertical":
        return True
    menor_a_direita = W - pw < H - ph
    return not menor_a_direita if divisao == "sobra_menor" else menor_a_direita


def _empacotar(itens, ordem, encaixe, divisao):
    livres: list[list[tuple[float, float, float, float]]] = []
    cortes: list[list[dict]] = []
    pontuar = _ENCAIXES[encaixe]
    for w, h, rotulo, origem in sorted(itens, key=_ORDENS[ordem]):
        melhor = None
        for ci, rects in enumerate(livres):
            for ri, (_, _, W, H) in enumerate(rects):
                for pw, ph in ((w, h), (h, w)):
                    if _encaixa(pw, ph, W, H):
                        s = pontuar(W, H, pw, ph)
                        if melhor is None or s < melhor[0]:
                            melhor = (s, ci, ri, pw, ph)
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
                           "girado": abs(pw - w) > _EPS})
        # Guilhotina: cada corte come PERDA_CORTE da sobra ao lado dele.
        k = PERDA_CORTE
        if _cortar(W, H, pw, ph, divisao):
            novos = [(x + pw + k, y, W - pw - k, H), (x, y + ph + k, pw, H - ph - k)]
        else:
            novos = [(x + pw + k, y, W - pw - k, ph), (x, y + ph + k, W, H - ph - k)]
        livres[ci] += [r for r in novos if r[2] > 0.5 and r[3] > 0.5]
    return livres, cortes


def _nota(livres) -> tuple:
    """Menos chapas; no empate, sobra mais concentrada (Σ área² maior)."""
    return (len(livres), -sum((r[2] * r[3]) ** 2 for rects in livres for r in rects))


def chapas_necessarias(pecas: list[tuple]) -> dict:
    """pecas = [(largura, altura[, rotulo, origem]), ...] em cm.

    Devolve também o `layout`: por chapa, onde cada peça é cortada (x, y a
    partir do canto superior esquerdo, já na orientação de corte) e as sobras
    numeradas S1, S2... (maior primeiro)."""
    emendas = 0
    itens: list[tuple[float, float, str, str]] = []
    ids: dict[str, str] = {}  # rótulo → ID do painel (a faixa herda o ID + letra)
    for i, pc in enumerate(pecas):
        w, h = float(pc[0]), float(pc[1])
        rotulo = str(pc[2]) if len(pc) > 2 else str(i + 1)
        origem = str(pc[3]) if len(pc) > 3 else ""
        pid = str(pc[4]) if len(pc) > 4 else ""
        if _encaixa(w, h, CHAPA_W, CHAPA_H) or _encaixa(h, w, CHAPA_W, CHAPA_H):
            itens.append((w, h, rotulo, origem))
            ids[rotulo] = pid
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
                ids[f"{rotulo}{chr(97 + k)}"] = f"{pid}{chr(97 + k)}" if pid else ""
                k += 1

    area = sum(w * h for w, h, _, _ in itens)
    limite = math.ceil(area / (CHAPA_W * CHAPA_H) - 1e-9) if itens else 0
    melhor = None
    for ordem in _ORDENS:
        for encaixe in _ENCAIXES:
            for divisao in _DIVISOES:
                livres, cortes = _empacotar(itens, ordem, encaixe, divisao)
                nota = _nota(livres)
                if melhor is None or nota < melhor[0]:
                    melhor = (nota, livres, cortes)
        # Atingiu o limite de área e uma chapa só tem sobra: não há melhor.
        if melhor and len(melhor[1]) <= limite:
            break
    livres, cortes = (melhor[1], melhor[2]) if melhor else ([], [])

    n = len(livres)
    layout = []
    for c in (c for ch in cortes for c in ch):
        c["id"] = ids.get(c["rotulo"], "")
    for ci in range(n):
        usada = sum(c["largura_cm"] * c["altura_cm"] for c in cortes[ci])
        layout.append({
            "chapa": ci + 1,
            "aproveitamento": round(usada / (CHAPA_W * CHAPA_H), 3),
            "pecas": cortes[ci],
            "sobras": [{"rotulo": f"S{j + 1}", "x": round(x, 1), "y": round(y, 1),
                        "largura_cm": round(W, 1), "altura_cm": round(H, 1)}
                       for j, (x, y, W, H) in enumerate(sorted(livres[ci], key=lambda r: -r[2] * r[3]))],
        })
    # Chapa mais cheia primeiro: a última concentra a sobra.
    layout.sort(key=lambda c: -c["aproveitamento"])
    for i, c in enumerate(layout):
        c["chapa"] = i + 1
    return {
        "chapas": n,
        "chapa_cm": [CHAPA_W, CHAPA_H],
        "perda_corte_cm": PERDA_CORTE,
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
        return "Sarrafo 2,2 x 7 cm (barra 3 m)"  # D-67
    return bitola.replace(".", ",") + " (barra 3 m)"


def compra_de_grupos(grupos: list[dict]) -> dict:
    """Material de compra de 1 item: as peças de todos os grupos saem do
    mesmo estoque (sobra de um lado corta peça do outro). Painel já
    identificado (`numero`, `id`, 1 por linha — `materiais_service`) mantém o
    número; linha agrupada (`quantidade` > 1) recebe `numeros` aqui."""
    paineis: list[tuple] = []
    por_material: dict[str, list[float]] = {}
    for g in grupos:
        if not g.get("disponivel"):
            continue
        for p in g.get("paineis") or []:
            origem = g["titulo"] + (f" · face {p['face']}" if p.get("face") else "")
            if p.get("numero") is not None:
                paineis.append((p["largura_cm"], p["altura_cm"], p["numero"], origem, p.get("id", "")))
                continue
            p["numeros"] = list(range(len(paineis) + 1, len(paineis) + 1 + int(p.get("quantidade", 1))))
            paineis += [(p["largura_cm"], p["altura_cm"], n, origem, "") for n in p["numeros"]]
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
