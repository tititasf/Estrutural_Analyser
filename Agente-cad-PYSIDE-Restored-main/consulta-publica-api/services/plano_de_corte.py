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
import re

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


def barras_necessarias(pecas_cm: list[float], barra: float = BARRA_CM, prefixo_id: str = "") -> dict:
    """`prefixo_id` (ex. `…-V309A.PARA-S7`) numera a sobra de cada barra:
    `{prefixo}-B01` — rastreável p/ reaproveitamento."""
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
        "sobras": [{"id": f"{prefixo_id}-B{i + 1:02d}" if prefixo_id else f"B{i + 1}",
                    "barra": i + 1, "comprimento_cm": round(L, 1)}
                   for i, L in enumerate(livres) if L > 0.5],
        "comprimento_barra_cm": barra,
        "perda_corte_cm": PERDA_CORTE,
        "aproveitamento": round(sum(itens) / (n * barra), 3) if n else 0.0,
        "emendas": emendas,
    }


# ─── 2D: chapas ──────────────────────────────────────────────────────────────
# Painel recortado (entalhe/abertura): corta-se o retângulo e a parte que sai
# (retângulo − contorno) é SOBRA — nada é descarte (D-68). Encostada numa sobra
# do plano, as duas viram uma peça só; e ali pode entrar peça de outra chapa.

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


def _empacotar(itens, ordem, encaixe, divisao, partes=None, cache=None):
    """Guilhotina. Painel recortado posto na chapa abre, dentro do próprio
    retângulo, o espaço do recorte (maior retângulo útil de cada pedaço): peça
    menor que vem depois pode ser cortada ali (`em_sobra`)."""
    partes = partes or {}
    cache = {} if cache is None else cache
    livres: list[list[tuple[float, float, float, float]]] = []
    recs: list[list[tuple[float, float, float, float]]] = []  # espaço nos recortes
    cortes: list[list[dict]] = []
    pontuar = _ENCAIXES[encaixe]
    for w, h, rotulo, origem in sorted(itens, key=_ORDENS[ordem]):
        melhor = None
        for ci in range(len(livres)):
            for lista, rects in ((0, livres[ci]), (1, recs[ci])):
                for ri, (_, _, W, H) in enumerate(rects):
                    for pw, ph in ((w, h), (h, w)):
                        if _encaixa(pw, ph, W, H):
                            s = pontuar(W, H, pw, ph)
                            if melhor is None or s < melhor[0]:
                                melhor = (s, ci, lista, ri, pw, ph)
        if melhor is None:
            livres.append([(0.0, 0.0, CHAPA_W, CHAPA_H)])
            recs.append([])
            cortes.append([])
            ci, lista, ri = len(livres) - 1, 0, 0
            pw, ph = (w, h) if _encaixa(w, h, CHAPA_W, CHAPA_H) else (h, w)
        else:
            _, ci, lista, ri, pw, ph = melhor
        alvo = (livres, recs)[lista][ci]
        x, y, W, H = alvo.pop(ri)
        c = {"rotulo": rotulo, "origem": origem, "x": round(x, 1), "y": round(y, 1),
             "largura_cm": round(pw, 1), "altura_cm": round(ph, 1), "girado": abs(pw - w) > _EPS}
        if lista:
            c["em_sobra"] = True
        cortes[ci].append(c)
        # Guilhotina: cada corte come PERDA_CORTE da sobra ao lado dele.
        k = PERDA_CORTE
        if _cortar(W, H, pw, ph, divisao):
            novos = [(x + pw + k, y, W - pw - k, H), (x, y + ph + k, pw, H - ph - k)]
        else:
            novos = [(x + pw + k, y, W - pw - k, ph), (x, y + ph + k, W, H - ph - k)]
        alvo += [r for r in novos if r[2] > 0.5 and r[3] > 0.5]
        if rotulo in partes:
            chave = (rotulo, c["girado"])
            if chave not in cache:
                cache[chave] = [_retangulo_util(g) for g in _recortes({**c, "x": 0.0, "y": 0.0}, partes)]
            recs[ci] += [(c["x"] + rx, c["y"] + ry, rw, rh) for rx, ry, rw, rh in cache[chave]
                         if rw > 0.5 and rh > 0.5]
    return livres, cortes


def _recortes(c: dict, partes: dict) -> list:
    """O que sai do retângulo cortado de um painel recortado (já descontada a
    serra em volta das peças reais), em pedaços."""
    from shapely.geometry import box
    from shapely.ops import unary_union

    ret = box(c["x"], c["y"], c["x"] + c["largura_cm"], c["y"] + c["altura_cm"])
    rec = ret.difference(unary_union([p.buffer(PERDA_CORTE, join_style=2) for p in _poligonos_da_peca(c, partes)]))
    return [r for r in getattr(rec, "geoms", [rec]) if not r.is_empty and r.area >= 1]


def _nota(livres) -> tuple:
    """Menos chapas; no empate, sobra mais concentrada (Σ área² maior)."""
    return (len(livres), -sum((r[2] * r[3]) ** 2 for rects in livres for r in rects))


def chapas_necessarias(pecas: list[tuple], prefixo_id: str = "") -> dict:
    """pecas = [(largura, altura[, rotulo, origem]), ...] em cm.

    Devolve também o `layout`: por chapa, onde cada peça é cortada (x, y a
    partir do canto superior esquerdo, já na orientação de corte) e as sobras
    numeradas S1, S2... (maior primeiro)."""
    emendas = 0
    itens: list[tuple[float, float, str, str]] = []
    ids: dict[str, str] = {}  # rótulo → ID do painel (a faixa herda o ID + letra)
    partes: dict[str, list] = {}  # rótulo → peças reais do painel recortado
    for i, pc in enumerate(pecas):
        w, h = float(pc[0]), float(pc[1])
        rotulo = str(pc[2]) if len(pc) > 2 else str(i + 1)
        origem = str(pc[3]) if len(pc) > 3 else ""
        pid = str(pc[4]) if len(pc) > 4 else ""
        if _encaixa(w, h, CHAPA_W, CHAPA_H) or _encaixa(h, w, CHAPA_W, CHAPA_H):
            itens.append((w, h, rotulo, origem))
            ids[rotulo] = pid
            if len(pc) > 5 and pc[5]:
                partes[rotulo] = pc[5]
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

    cache: dict = {}
    area = sum(w * h for w, h, _, _ in itens)
    limite = math.ceil(area / (CHAPA_W * CHAPA_H) - 1e-9) if itens else 0
    melhor = None
    for ordem in _ORDENS:
        for encaixe in _ENCAIXES:
            for divisao in _DIVISOES:
                livres, cortes = _empacotar(itens, ordem, encaixe, divisao, partes, cache)
                nota = _nota(livres)
                if melhor is None or nota < melhor[0]:
                    melhor = (nota, livres, cortes)
        # Atingiu o limite de área e uma chapa só tem sobra: não há melhor.
        if melhor and len(melhor[1]) <= limite:
            break
    livres, cortes = (melhor[1], melhor[2]) if melhor else ([], [])

    for c in (c for ch in cortes for c in ch):
        c["id"] = ids.get(c["rotulo"], "")
    regioes = _regioes_livres(livres, cortes, partes)
    n = len(cortes)
    layout = []
    area = 0.0
    for ci in range(n):
        usada = sum(_area_real(c, partes) for c in cortes[ci])
        area += usada
        layout.append({
            "chapa": ci + 1,
            "aproveitamento": round(usada / (CHAPA_W * CHAPA_H), 3),
            "pecas": cortes[ci],
            "sobras": _sobras(regioes[ci], cortes[ci], partes),
        })
    # Chapa mais cheia primeiro: a última concentra a sobra.
    layout.sort(key=lambda c: -c["aproveitamento"])
    for i, c in enumerate(layout):
        c["chapa"] = i + 1
        # Sobra rastreável p/ reaproveitamento: {prefixo}-CH02-S1.
        for s in c["sobras"]:
            s["id"] = f"{prefixo_id}-CH{i + 1:02d}-{s['rotulo']}" if prefixo_id else f"CH{i + 1}-{s['rotulo']}"
    return {
        "chapas": n,
        "chapa_cm": [CHAPA_W, CHAPA_H],
        "perda_corte_cm": PERDA_CORTE,
        "aproveitamento": round(area / (n * CHAPA_W * CHAPA_H), 3) if n else 0.0,
        "emendas": emendas,
        "layout": layout,
    }


def _no_corte(c: dict, anel) -> list[tuple[float, float]]:
    """Anel local do painel (y p/ cima) → coordenadas da chapa (y p/ baixo)."""
    h = c["largura_cm"] if c["girado"] else c["altura_cm"]
    x, y = c["x"], c["y"]
    return [(x + ly, y + lx) if c["girado"] else (x + lx, y + (h - ly)) for lx, ly in anel]


def _poligonos_da_peca(c: dict, partes: dict) -> list:
    from shapely.geometry import Polygon, box

    ps = partes.get(c["rotulo"])
    if not ps:
        return [box(c["x"], c["y"], c["x"] + c["largura_cm"], c["y"] + c["altura_cm"])]
    return [Polygon(_no_corte(c, p["contorno"]), [_no_corte(c, f) for f in p.get("furos") or []]).buffer(0)
            for p in ps]


def _area_real(c: dict, partes: dict) -> float:
    return sum(p.area for p in _poligonos_da_peca(c, partes))


def _regioes_livres(livres, cortes, partes) -> list:
    """Por chapa, a área livre como geometria: sobras do guilhotina + recortes
    (menos as peças que foram cortadas dentro deles)."""
    from shapely.geometry import box
    from shapely.ops import unary_union

    k = PERDA_CORTE
    out = []
    for rects, cs in zip(livres, cortes):
        geoms = [box(x, y, x + W, y + H) for x, y, W, H in rects]
        dentro = [box(c["x"], c["y"], c["x"] + c["largura_cm"], c["y"] + c["altura_cm"]).buffer(k, join_style=2)
                  for c in cs if c.get("em_sobra")]
        for c in cs:
            if c["rotulo"] not in partes:
                continue
            for r in _recortes(c, partes):
                if dentro:
                    r = r.difference(unary_union(dentro))
                for r in getattr(r, "geoms", [r]):
                    if r.is_empty or r.area < 1:
                        continue
                    # Recorte encostado (a 1 corte de serra) numa sobra: esse
                    # corte não se faz — os dois viram uma sobra só.
                    for i, g in enumerate(geoms):
                        if g is not None and g.distance(r) <= k + 0.05:
                            r = unary_union([g.buffer(0.6 * k, join_style=2), r.buffer(0.6 * k, join_style=2)]
                                            ).buffer(-0.6 * k, join_style=2)
                            geoms[i] = None
                    geoms = [g for g in geoms if g is not None] + [r]
        out.append(geoms)
    return out


def _retangulo_util(g) -> tuple[float, float, float, float]:
    """Maior retângulo alinhado que cabe na sobra (x, y, w, h)."""
    from shapely.geometry import box

    vs = [pt for p in getattr(g, "geoms", [g]) for pt in p.exterior.coords]
    xs = sorted({round(x, 1) for x, _ in vs})
    ys = sorted({round(y, 1) for _, y in vs})
    folga = g.buffer(0.02, join_style=2)
    melhor = (0.0, 0.0, 0.0, 0.0)
    for i, x0 in enumerate(xs):
        for x1 in xs[i + 1:]:
            for j, y0 in enumerate(ys):
                for y1 in ys[j + 1:]:
                    if (x1 - x0) * (y1 - y0) > melhor[2] * melhor[3] and folga.contains(box(x0, y0, x1, y1)):
                        melhor = (x0, y0, x1 - x0, y1 - y0)
    return melhor


def _sobras(geoms, cs, partes) -> list[dict]:
    """Sobras numeradas S1, S2... (maior primeiro). Não retangular (recorte,
    ou recorte + sobra vizinha) leva o contorno e o maior retângulo útil."""
    from shapely.geometry import box

    rec_de = [(c["id"] or c["rotulo"], box(c["x"], c["y"], c["x"] + c["largura_cm"], c["y"] + c["altura_cm"]))
              for c in cs if c["rotulo"] in partes]
    out = []
    for g in sorted((g for g in geoms if not g.is_empty), key=lambda g: -g.area):
        x0, y0, x1, y1 = g.bounds
        if x1 - x0 <= 0.5 or y1 - y0 <= 0.5:
            continue
        s = {"x": round(x0, 1), "y": round(y0, 1), "largura_cm": round(x1 - x0, 1),
             "altura_cm": round(y1 - y0, 1)}
        if g.area < (x1 - x0) * (y1 - y0) - 1:
            p = g.simplify(0.05)
            s["contorno"] = [[round(x, 1), round(y, 1)] for x, y in list(p.exterior.coords)[:-1]]
            s["area_cm2"] = round(g.area)
            ux, uy, uw, uh = _retangulo_util(g)
            s["util"] = {"x": ux, "y": uy, "largura_cm": round(uw, 1), "altura_cm": round(uh, 1)}
        de = [pid for pid, b in rec_de if b.intersection(g).area > 1]
        if de:
            s["recorte_de"] = de
        out.append(s)
    for j, s in enumerate(out):
        s["rotulo"] = f"S{j + 1}"
    return out


def material_da_bitola(bitola: str) -> str:
    """Nome de compra da barra que corta a peça daquela bitola."""
    b = bitola.lower()
    if "3.5" in b:
        return "Meio pontalete (barra 3 m)"
    if "press" in b:
        return "Sarrafo 2,2 x 7 cm (barra 3 m)"  # D-67
    return bitola.replace(".", ",") + " (barra 3 m)"


def _token_material(mat: str) -> str:
    """Barra de compra → token do ID da sobra: MP (meio pontalete), S7, S10..."""
    if "pontalete" in mat.lower():
        return "MP"
    m = re.search(r"x\s*(\d+)", mat)
    return f"S{m.group(1)}" if m else "BAR"


def compra_de_grupos(grupos: list[dict], prefixo_id: str = "") -> dict:
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
                paineis.append((p["largura_cm"], p["altura_cm"], p["numero"], origem, p.get("id", ""),
                                p.get("partes")))
                continue
            p["numeros"] = list(range(len(paineis) + 1, len(paineis) + 1 + int(p.get("quantidade", 1))))
            paineis += [(p["largura_cm"], p["altura_cm"], n, origem, "") for n in p["numeros"]]
        for s in g.get("sarrafos") or []:
            mat = material_da_bitola(s["bitola"])
            for c in s["cortes"]:
                por_material.setdefault(mat, []).extend([c["comprimento_cm"]] * int(c["quantidade"]))
    out: dict = {"chapas": None, "barras": [], "sobras": []}
    if paineis:
        mat = "Chapa compensado 244 x 122 cm"
        out["chapas"] = {"material": mat, **chapas_necessarias(paineis, prefixo_id)}
        for c in out["chapas"]["layout"]:
            out["sobras"] += [{"id": s["id"], "tipo": "chapa", "material": mat, "origem": f"Chapa {c['chapa']}",
                               "largura_cm": s["largura_cm"], "altura_cm": s["altura_cm"],
                               **{k: s[k] for k in ("contorno", "area_cm2", "util", "recorte_de") if k in s}}
                              for s in c["sobras"]]
    for mat, pecas in sorted(por_material.items()):
        pref = f"{prefixo_id}-{_token_material(mat)}" if prefixo_id else _token_material(mat)
        b = barras_necessarias(pecas, prefixo_id=pref)
        out["barras"].append({"material": mat, "pecas": len(pecas), "total_m": round(sum(pecas) / 100, 2), **b})
        out["sobras"] += [{"id": s["id"], "tipo": "barra", "material": mat, "origem": f"Barra {s['barra']}",
                           "comprimento_cm": s["comprimento_cm"]} for s in b["sobras"]]
    return out
