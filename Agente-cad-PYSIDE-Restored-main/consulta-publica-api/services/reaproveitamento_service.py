"""Reaproveitamento entre pavimentos (D-70..D-73).

Fonte das regras: `docs/MATERIAIS-E-CONSTRUCAO.md` §12. O pavimento consome,
nesta ordem, cada etapa para TODOS os itens da classe antes da próxima:

    1   painel montado do próprio item (pavimento anterior), medida idêntica
    1.5 idem, outra medida, cortando conforme a regra da classe
    2   montados que os donos não usaram (lista temporária), idêntica
    2.5 idem, cortando
    3   sobra de chapa (inclusive recorte) na medida — monta com sarrafo novo
    3.5 sobra de chapa cortada
    4   estoque antigo (pavimentos mais abaixo) sem corte
    4.5 estoque antigo cortando
    novo  material novo, só do que faltou (plano de corte de sempre)

Regras de corte (o sarrafo é cortado junto com o painel, D-71):
    LV  mesmo tipo (gradeado/sarrafeado), comprimento igual, mesmas pontas com
        sarrafo; só a altura varia, cortando embaixo
    PIL largura igual; só a altura, cortando em cima
    FV  largura igual; só o comprimento, e a ponta cortada fica sem sarrafo
    LAJ tira de escoramento nunca volta; painel comum corta em qualquer direção
Nunca entre classes: a cadeia é por classe publicada (pilares Para ≠ Passa).
Estoque acumula e se gasta (D-72); a cadeia liga só pavimentos consecutivos
(buraco na numeração = estoque desconhecido, recomeça do zero).
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
import tempfile
import threading
from collections import Counter
from pathlib import Path
from typing import Optional

from services import materiais_service as ms
from services.plano_de_corte import PERDA_CORTE, compra_de_grupos, material_da_bitola
from services.resolve_service import resolver_code

log = logging.getLogger(__name__)

TOL = 1.0  # cm: "mesma medida"
ETAPAS = {
    "1": "Próprio item · medida idêntica",
    "1.5": "Próprio item · cortado",
    "2": "Outros itens · medida idêntica",
    "2.5": "Outros itens · cortado",
    "3": "Sobra de chapa na medida",
    "3.5": "Sobra de chapa cortada",
    "4": "Estoque antigo · sem corte",
    "4.5": "Estoque antigo · cortado",
    "novo": "Material novo",
}
_VERSAO = "reap-1"
_lock = threading.Lock()
_memoria: dict[str, dict] = {}


# --------------------------------------------------------------------------- #
# Pavimentos e itens
# --------------------------------------------------------------------------- #

def numero_pavimento(pav: str) -> Optional[int]:
    if str(pav).upper() in ("TERREO", "TÉRREO"):
        return 0
    m = re.fullmatch(r"(\d+)_PAV", str(pav or ""))
    return int(m.group(1)) if m else None


def cadeia(conn, obra_id: str, pav: str) -> list[str]:
    """Pavimentos consecutivos que terminam em `pav` (de baixo para cima)."""
    pavs = [r[0] for r in conn.execute(
        "SELECT DISTINCT pavimento FROM public_codes WHERE obra_id = ? AND kind = 'item' AND revoked = 0",
        (obra_id,))]
    por_numero = {numero_pavimento(p): p for p in pavs if numero_pavimento(p) is not None}
    n = numero_pavimento(pav)
    if n is None:
        return [pav]
    out = [pav]
    while n - 1 in por_numero:
        n -= 1
        out.insert(0, por_numero[n])
    return out


def _item_do_prefixo(prefixo: str) -> str:
    return prefixo.split("-", 3)[-1] if prefixo.count("-") >= 3 else prefixo


def chave_item(item: str) -> str:
    """Par "próprio item" entre pavimentos: viga e laje trocam o dígito do
    pavimento (V301 ↔ V401, L319 ↔ L419); pilar mantém o nome (P10 ↔ P10)."""
    return re.sub(r"^([A-Z]+)\d(\d\d)", r"\1\2", item)


def _natural(s: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


# --------------------------------------------------------------------------- #
# Inventário medido (com cache pelos DXFs que a medição abriu)
# --------------------------------------------------------------------------- #

def _dir_cache() -> Path:
    d = Path(os.environ.get("CONSULTA_REAPROVEITAMENTO_CACHE")
             or Path(tempfile.gettempdir()) / "consulta_reaproveitamento")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _assinatura(fontes: list[str], extra: str) -> str:
    h = hashlib.sha1((_VERSAO + extra).encode())
    for f in sorted(fontes):
        try:
            h.update(f"{f}:{os.stat(f).st_mtime_ns}".encode())
        except OSError:
            h.update(f"{f}:-".encode())
    return h.hexdigest()


def _materiais(row, code: str, root: Path) -> Optional[dict]:
    # publish_batch não entra: o auto-publish do portal o troca a cada rodada.
    extra = f"{code}|{row['pavimento']}|{row['classe']}"
    arq = _dir_cache() / f"mat_{hashlib.sha1(code.encode()).hexdigest()[:16]}.json"
    try:
        salvo = json.loads(arq.read_text(encoding="utf-8"))
        if salvo.get("assinatura") == _assinatura(salvo.get("fontes", []), extra):
            return salvo["materiais"]
    except (OSError, ValueError):
        pass
    ms._fontes.lista = []
    try:
        m = ms.obter_materiais(row, root)
        fontes = list(ms._fontes.lista)
    finally:
        ms._fontes.lista = None
    try:
        arq.write_text(json.dumps({"assinatura": _assinatura(fontes, extra), "fontes": fontes,
                                   "materiais": m}, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log.warning("reaproveitamento: cache não gravado: %s", exc)
    return m


def _painel(p: dict, grupo: str, item: dict) -> dict:
    mont = [s for s in p.get("montagem") or [] if s.get("face") != "tras"]
    W = p["largura_cm"]
    # Ponta com sarrafo: peça em pé encostada na borda esquerda/direita.
    esq = any(s["h"] > s["w"] and s["x"] <= 1.0 for s in mont)
    dir_ = any(s["h"] > s["w"] and s["x"] + s["w"] >= W - 1.0 for s in mont)
    grade = any(re.search(r"grade|pontalete", s["bitola"], re.I) for s in mont)
    return {
        "id": p.get("id", ""), "numero": p.get("numero"), "grupo": grupo,
        "item": item["item"], "chave": item["chave"], "titulo": item["titulo"],
        "largura_cm": W, "altura_cm": p["altura_cm"], "partes": p.get("partes"),
        "pontas": [esq, dir_], "tipo": "gradeado" if grade else "sarrafeado",
        "reaproveitavel": p.get("reaproveitavel", True), "classe_painel": p.get("classe"),
        "sarrafos": p.get("sarrafos") or [], "montagem": p.get("montagem") or [],
    }


def inventario(conn, obra_id: str, pav: str, classe: str, root: Path) -> list[dict]:
    rows = conn.execute(
        "SELECT code FROM public_codes WHERE obra_id = ? AND pavimento = ? AND classe = ? "
        "AND kind = 'item' AND revoked = 0", (obra_id, pav, classe)).fetchall()
    itens = []
    for (code,) in rows:
        row = resolver_code(conn, code)
        if row is None:
            continue
        m = _materiais(row, code, root)
        if not m or not m.get("grupos"):
            continue
        nome = _item_do_prefixo(m.get("prefixo_id") or code)
        titulo = (row["titulo_publico"] if "titulo_publico" in row.keys() else "") or nome
        item = {"code": code, "item": nome, "chave": chave_item(nome), "titulo": titulo,
                "pavimento": pav, "tipo": m.get("tipo"), "grupos": m["grupos"],
                "compra": m.get("compra") or {}}
        item["paineis"] = [_painel(p, g["titulo"], item) for g in m["grupos"] if g.get("disponivel")
                           for p in g.get("paineis") or []]
        itens.append(item)
    itens.sort(key=lambda i: _natural(i["item"]))
    return itens


# --------------------------------------------------------------------------- #
# Regras de encaixe por classe
# --------------------------------------------------------------------------- #

_formas: dict[str, object] = {}


def _forma(p: dict):
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    k = f"{p.get('id')}|{p['largura_cm']}|{p['altura_cm']}|{len(p.get('partes') or [])}"
    if k not in _formas:
        if p.get("partes"):
            _formas[k] = unary_union([Polygon(pt["contorno"], pt.get("furos") or []).buffer(0)
                                      for pt in p["partes"]])
        else:
            _formas[k] = box(0, 0, p["largura_cm"], p["altura_cm"])
    return _formas[k]


def _mesma_forma(a: dict, b: dict) -> bool:
    if not a.get("partes") and not b.get("partes"):
        return True
    fa, fb = _forma(a), _forma(b)
    return fa.symmetric_difference(fb).area <= 0.02 * max(fa.area, fb.area, 1.0)


def _cabe_na_janela(src: dict, dst: dict, y0: float) -> bool:
    """O painel destino (forma real) cabe no material do reaproveitado depois
    do corte: janela [y0, y0 + h] do reaproveitado, trazida para y = 0."""
    if not src.get("partes"):
        return True
    from shapely.affinity import translate
    from shapely.geometry import box
    mat = translate(_forma(src).intersection(box(0, y0, src["largura_cm"], y0 + dst["altura_cm"])), 0, -y0)
    return _forma(dst).difference(mat.buffer(0.5)).area < 1.0


def _ig(a: float, b: float) -> bool:
    return abs(a - b) <= TOL


def encaixe(tipo: str, src: dict, dst: dict, cortar: bool) -> Optional[dict]:
    """None se `src` (montado disponível) não serve para `dst`; senão o corte
    feito e os retalhos (largura, altura) que viram sobra."""
    W, H, w, h = src["largura_cm"], src["altura_cm"], dst["largura_cm"], dst["altura_cm"]
    k = PERDA_CORTE
    if not src.get("reaproveitavel", True):
        return None
    if tipo == "viga_lateral":
        if src["tipo"] != dst["tipo"] or not _ig(W, w) or src["pontas"] != dst["pontas"]:
            return None
        if _ig(H, h):
            return None if cortar or not _mesma_forma(src, dst) else {"corte": None, "retalhos": []}
        if not cortar or H < h or not _cabe_na_janela(src, dst, H - h):
            return None
        return {"corte": f"corta {H - h:.0f} cm embaixo",
                "retalhos": [(W, round(H - h - k, 1))] if H - h - k > 0.5 else []}
    if tipo == "pilar":
        if not _ig(W, w):
            return None
        if _ig(H, h):
            if not cortar:
                return {"corte": None, "retalhos": []} if _mesma_forma(src, dst) else None
            # Mesma medida, destino com recorte de viga que o reaproveitado não tem.
            if _mesma_forma(src, dst) or not _cabe_na_janela(src, dst, 0.0):
                return None
            return {"corte": "recorta a chegada de viga", "retalhos": []}
        if not cortar or H < h or not _cabe_na_janela(src, dst, 0.0):
            return None
        return {"corte": f"corta {H - h:.0f} cm em cima",
                "retalhos": [(W, round(H - h - k, 1))] if H - h - k > 0.5 else []}
    if tipo == "viga_fundo":
        if not _ig(H, h) or src.get("partes") or dst.get("partes"):
            return None
        if _ig(W, w):
            return None if cortar or src["pontas"] != dst["pontas"] else {"corte": None, "retalhos": []}
        if not cortar or W < w:
            return None
        # A ponta cortada fica sem sarrafo de extremidade.
        for lado, pontas in (("direita", [src["pontas"][0], False]), ("esquerda", [False, src["pontas"][1]])):
            if pontas == dst["pontas"]:
                return {"corte": f"corta {W - w:.0f} cm na ponta {lado}",
                        "retalhos": [(round(W - w - k, 1), H)] if W - w - k > 0.5 else []}
        return None
    if tipo == "laje":
        for gw, gh in ((W, H), (H, W)):
            if _ig(gw, w) and _ig(gh, h):
                if cortar:
                    return None
                if (gw, gh) == (W, H) and _mesma_forma(src, dst):
                    return {"corte": None, "retalhos": []}
                if not src.get("partes") and not dst.get("partes"):
                    return {"corte": None, "retalhos": []}
        if not cortar or src.get("partes"):
            return None
        for gw, gh in ((W, H), (H, W)):
            if gw >= w and gh >= h:
                ret = [(round(gw - w - k, 1), gh), (w, round(gh - h - k, 1))]
                return {"corte": f"corta de {gw:.0f} × {gh:.0f} para {w:.0f} × {h:.0f}",
                        "retalhos": [r for r in ret if min(r) > 0.5]}
        return None
    return None


# --------------------------------------------------------------------------- #
# Sobras de chapa: retângulo útil; guilhotina na etapa cortada
# --------------------------------------------------------------------------- #

def _ret_sobra(s: dict) -> tuple[float, float]:
    u = s.get("util") or s
    return float(u["largura_cm"]), float(u["altura_cm"])


def _encaixe_sobra(s: dict, dst: dict, cortar: bool) -> Optional[dict]:
    W, H = _ret_sobra(s)
    w, h = dst["largura_cm"], dst["altura_cm"]
    k = PERDA_CORTE
    for gw, gh, girado in ((W, H, False), (H, W, True)):
        if _ig(gw, w) and _ig(gh, h):
            return None if cortar else {"corte": None, "retalhos": [], "girado": girado}
    if not cortar:
        return None
    melhor = None
    for gw, gh, girado in ((W, H, False), (H, W, True)):
        if gw + TOL >= w and gh + TOL >= h:
            ret = [(round(gw - w - k, 1), gh), (w, round(gh - h - k, 1))]
            ret = [r for r in ret if min(r) > 0.5]
            sobra = gw * gh - w * h
            if melhor is None or sobra < melhor[0]:
                melhor = (sobra, {"corte": f"corta de {gw:.0f} × {gh:.0f}", "retalhos": ret, "girado": girado})
    return melhor[1] if melhor else None


# --------------------------------------------------------------------------- #
# Alocação de um pavimento
# --------------------------------------------------------------------------- #

def _area(p: dict) -> float:
    return p["largura_cm"] * p["altura_cm"]


def _pecas_sarrafo(sarrafos: list[dict]) -> list[tuple[str, float]]:
    return [(s["bitola"], float(s["comprimento_cm"])) for s in sarrafos for _ in range(int(s["quantidade"]))]


def _pecas_fora_de_painel(grupo: dict) -> list[tuple[str, float]]:
    """Sarrafos do grupo que não são de painel (avulsos, grades): sempre novos."""
    total = Counter((s["bitola"], float(c["comprimento_cm"]))
                    for s in grupo.get("sarrafos") or [] for c in s["cortes"] for _ in range(int(c["quantidade"])))
    total.subtract(Counter(pc for p in grupo.get("paineis") or [] for pc in _pecas_sarrafo(p.get("sarrafos") or [])))
    return [pc for pc, n in total.items() for _ in range(max(n, 0))]


def alocar_pavimento(tipo: str, itens: list[dict], anterior: dict, antigo: dict) -> dict:
    """`anterior`/`antigo` = {"montados": [...], "chapas": [...], "barras": [...]}
    (listas consumidas aqui). Devolve alocação por painel, compra por item e
    os retalhos novos."""
    aloc: dict[str, dict] = {}
    retalhos: list[dict] = []
    usados: set[str] = set()

    def pendentes(item, maiores_primeiro=False):
        ps = [p for p in item["paineis"] if p["id"] not in aloc]
        return sorted(ps, key=_area, reverse=True) if maiores_primeiro else ps

    def registra(p, etapa, fonte, info, tipo_fonte):
        aloc[p["id"]] = {"etapa": etapa, "fonte_id": fonte.get("id"), "fonte_tipo": tipo_fonte,
                         "fonte_item": fonte.get("titulo") or fonte.get("item"),
                         "fonte_pavimento": fonte.get("pavimento"),
                         "fonte_medida": [fonte.get("largura_cm"), fonte.get("altura_cm")],
                         "corte": info.get("corte")}
        usados.add(fonte.get("id"))
        for n, (rw, rh) in enumerate(info.get("retalhos") or [], 1):
            retalhos.append({"id": f"{fonte.get('id')}-R{n}", "tipo": "chapa", "material": "Retalho de painel",
                             "largura_cm": rw, "altura_cm": rh, "retalho_de": fonte.get("id")})

    def melhor_montado(p, pool, cortar):
        cand = []
        for s in pool:
            if s["id"] in usados:
                continue
            info = encaixe(tipo, s, p, cortar)
            if info is not None:
                cand.append((_area(s), s, info))
        return min(cand, key=lambda c: c[0])[1:] if cand else None

    montados_ant = [s for s in anterior.get("montados", []) if s.get("reaproveitavel", True)]
    por_chave: dict[str, list[dict]] = {}
    for s in montados_ant:
        por_chave.setdefault(s["chave"], []).append(s)

    # 1 / 1.5 — próprio item (todos os itens antes da etapa seguinte)
    for etapa, cortar in (("1", False), ("1.5", True)):
        for item in itens:
            for p in pendentes(item, cortar):
                achado = melhor_montado(p, por_chave.get(item["chave"], []), cortar)
                if achado:
                    registra(p, etapa, achado[0], achado[1], "montado")
    # Lista temporária: montados que os donos não usaram.
    temporaria = [s for s in montados_ant if s["id"] not in usados]
    for etapa, cortar in (("2", False), ("2.5", True)):
        for item in itens:
            for p in pendentes(item, cortar):
                achado = melhor_montado(p, temporaria, cortar)
                if achado:
                    registra(p, etapa, achado[0], achado[1], "montado")

    def por_sobras(etapa_ig, etapa_corte, chapas):
        for etapa, cortar in ((etapa_ig, False), (etapa_corte, True)):
            for item in itens:
                for p in pendentes(item, True):
                    cand = []
                    for s in chapas:
                        if s["id"] in usados:
                            continue
                        info = _encaixe_sobra(s, p, cortar)
                        if info is not None:
                            W, H = _ret_sobra(s)
                            cand.append((W * H, s, info))
                    if not cand:
                        continue
                    _, s, info = min(cand, key=lambda c: c[0])
                    registra(p, etapa, s, info, "sobra")
                    # O que sobra da sobra continua disponível na mesma etapa.
                    for rw, rh in info["retalhos"]:
                        chapas.append({"id": f"{s['id']}.{len([c for c in chapas if c['id'].startswith(s['id'] + '.')]) + 1}",
                                       "tipo": "chapa", "material": s.get("material"),
                                       "largura_cm": rw, "altura_cm": rh, "pavimento": s.get("pavimento")})
                    retalhos[:] = [r for r in retalhos if r.get("retalho_de") != s["id"]]

    chapas_ant = anterior.get("chapas", [])
    por_sobras("3", "3.5", chapas_ant)

    # 4 / 4.5 — estoque antigo: montados, depois sobras.
    antigos = [s for s in antigo.get("montados", []) if s.get("reaproveitavel", True)]
    for etapa, cortar in (("4", False), ("4.5", True)):
        for item in itens:
            for p in pendentes(item, cortar):
                achado = melhor_montado(p, antigos, cortar)
                if achado:
                    registra(p, etapa, achado[0], achado[1], "montado")
    chapas_antigas = antigo.get("chapas", [])
    por_sobras("4", "4.5", chapas_antigas)

    # Material novo + sarrafos (sobras de barra primeiro).
    barras = [dict(b) for b in anterior.get("barras", []) + antigo.get("barras", []) if b["id"] not in usados]
    compras: dict[str, dict] = {}
    for item in itens:
        pecas: list[tuple[str, float]] = []
        grupos_novo = []
        for g in item["grupos"]:
            if not g.get("disponivel"):
                continue
            novos = []
            for p in g.get("paineis") or []:
                a = aloc.get(p.get("id"))
                if a is None:
                    novos.append(p)
                    aloc[p["id"]] = {"etapa": "novo"}
                    pecas += _pecas_sarrafo(p.get("sarrafos") or [])
                elif a["fonte_tipo"] == "sobra":  # chapa reaproveitada, sarrafo novo
                    pecas += _pecas_sarrafo(p.get("sarrafos") or [])
            pecas += _pecas_fora_de_painel(g)
            grupos_novo.append({"titulo": g["titulo"], "disponivel": True, "paineis": novos, "sarrafos": []})
        de_sobra = []
        restantes: list[tuple[str, float]] = []
        for bitola, comp in sorted(pecas, key=lambda pc: -pc[1]):
            mat = material_da_bitola(bitola)
            b = next((b for b in barras if b["material"] == mat and b["comprimento_cm"] + 0.05 >= comp), None)
            if b is None:
                restantes.append((bitola, comp))
                continue
            de_sobra.append({"sobra_id": b["id"], "bitola": bitola, "comprimento_cm": comp})
            usados.add(b["id"])
            b["comprimento_cm"] = round(b["comprimento_cm"] - comp - PERDA_CORTE, 1)
            if b["comprimento_cm"] <= 0.5:
                barras.remove(b)
        por_bitola: dict[str, Counter] = {}
        for bitola, comp in restantes:
            por_bitola.setdefault(bitola, Counter())[comp] += 1
        if grupos_novo:
            grupos_novo[0]["sarrafos"] = [{"bitola": b, "cortes": [{"comprimento_cm": c, "quantidade": n}
                                                                   for c, n in sorted(cs.items(), reverse=True)]}
                                          for b, cs in sorted(por_bitola.items())]
        prefixo = item["paineis"][0]["id"].rsplit("-", 1)[0] if item["paineis"] else item["item"]
        # "-N" separa a compra deste cenário da "Preparação com materiais novos";
        # sem pavimento anterior as duas coincidem e os IDs também.
        tem_estoque = any(anterior.get(k) or antigo.get(k) for k in ("montados", "chapas", "barras"))
        compra = compra_de_grupos(grupos_novo, prefixo + ("-N" if tem_estoque else ""))
        compra["barras_de_sobra"] = de_sobra
        compras[item["code"]] = compra
    return {"alocacao": aloc, "compras": compras, "retalhos": retalhos, "usados": usados,
            "barras_restantes": barras}


# --------------------------------------------------------------------------- #
# Cadeia de pavimentos
# --------------------------------------------------------------------------- #

def _estoque_do_pavimento(itens: list[dict], pav: str, compras: dict[str, dict], retalhos: list[dict]) -> dict:
    """O que o pavimento deixa ao ser desformado: todos os painéis montados
    reaproveitáveis + sobras novas (plano de corte do que foi comprado e
    retalhos dos cortes)."""
    montados = [{**p, "pavimento": pav} for it in itens for p in it["paineis"] if p.get("reaproveitavel", True)]
    chapas, barras = [], []
    for c in compras.values():
        for s in c.get("sobras") or []:
            (chapas if s.get("tipo") == "chapa" else barras).append({**s, "pavimento": pav})
    chapas += [{**r, "pavimento": pav} for r in retalhos]
    return {"montados": montados, "chapas": chapas, "barras": barras}


def _vazio() -> dict:
    return {"montados": [], "chapas": [], "barras": []}


def calcular(conn, obra_id: str, pav: str, classe: str, root: Path) -> dict:
    pavs = cadeia(conn, obra_id, pav)
    invs = {p: inventario(conn, obra_id, p, classe, root) for p in pavs}
    chave = hashlib.sha1(json.dumps([obra_id, classe, pavs, [[i["code"], len(i["paineis"]),
                         [p["id"] + str(p["largura_cm"]) + str(p["altura_cm"]) for p in i["paineis"]]]
                         for p in pavs for i in invs[p]]], sort_keys=True).encode()).hexdigest()
    with _lock:
        if chave in _memoria:
            return _memoria[chave]
    anterior, antigo = _vazio(), _vazio()
    res = None
    for i, p in enumerate(pavs):
        itens = invs[p]
        tipo = itens[0]["tipo"] if itens else ""
        disponivel = {"anterior": copy.deepcopy(anterior), "antigo": copy.deepcopy(antigo)}
        r = alocar_pavimento(tipo, itens, anterior, antigo)
        if i == len(pavs) - 1:
            res = {"pavimento": p, "pavimentos": pavs, "itens": itens, "disponivel": disponivel, **r}
            break
        usados = r["usados"]
        # Sobe para o próximo: o que não foi usado vira estoque antigo.
        antigo = {
            "montados": [s for s in anterior["montados"] + antigo["montados"] if s["id"] not in usados],
            "chapas": [s for s in anterior["chapas"] + antigo["chapas"] if s["id"] not in usados],
            "barras": r["barras_restantes"],
        }
        anterior = _estoque_do_pavimento(itens, p, r["compras"], r["retalhos"])
    with _lock:
        _memoria[chave] = res
    return res


# --------------------------------------------------------------------------- #
# Resposta da ficha
# --------------------------------------------------------------------------- #

def _publico_montado(p: dict) -> dict:
    return {k: p.get(k) for k in ("id", "largura_cm", "altura_cm", "pontas", "tipo", "grupo")}


def obter_reaproveitamento(conn, row, root: Path) -> Optional[dict]:
    pav, classe, code = row["pavimento"], row["classe"], row["code"]
    res = calcular(conn, row["obra_id"], pav, classe, root)
    if res is None:
        return None
    item = next((i for i in res["itens"] if i["code"] == code), None)
    if item is None:
        return None
    aloc = res["alocacao"]
    usado_por = {a["fonte_id"]: pid for pid, a in aloc.items() if a.get("fonte_id")}
    for it in res["itens"]:  # sobra de barra cortada em sarrafo
        for b in (res["compras"].get(it["code"]) or {}).get("barras_de_sobra") or []:
            usado_por.setdefault(b["sobra_id"], f"sarrafo de {it['titulo']}")
    disp = res["disponivel"]

    def itens_disponiveis(montados):
        por: dict[tuple, dict] = {}
        for s in montados:
            k = (s.get("pavimento"), s["item"])
            por.setdefault(k, {"pavimento": s.get("pavimento"), "item": s["item"], "titulo": s.get("titulo"),
                               "proprio": s["chave"] == item["chave"], "paineis": []})
            por[k]["paineis"].append({**_publico_montado(s), "usado_por": usado_por.get(s["id"])})
        return sorted(por.values(), key=lambda d: (not d["proprio"], _natural(d["item"])))

    sobras = [{k: s[k] for k in ("id", "tipo", "material", "largura_cm", "altura_cm", "comprimento_cm", "util")
               if s.get(k) is not None} | {"usado_por": usado_por.get(s["id"])}
              for s in disp["anterior"]["chapas"] + disp["antigo"]["chapas"]
              + disp["anterior"]["barras"] + disp["antigo"]["barras"]]
    paineis = []
    for p in item["paineis"]:
        a = aloc.get(p["id"], {"etapa": "novo"})
        paineis.append({"id": p["id"], "numero": p["numero"], "grupo": p["grupo"],
                        "largura_cm": p["largura_cm"], "altura_cm": p["altura_cm"],
                        "pontas": p["pontas"], "tipo": p["tipo"], **a})
    resumo = Counter(a["etapa"] for a in aloc.values())
    resumo_item = Counter(p["etapa"] for p in paineis)
    anteriores = res["pavimentos"][:-1]
    return {
        "pavimento": pav,
        "pavimento_anterior": anteriores[-1] if anteriores else None,
        "pavimentos_cadeia": res["pavimentos"],
        "etapas": ETAPAS,
        "item": {"titulo": item["titulo"], "chave": item["chave"]},
        "paineis": paineis,
        "resumo_item": dict(resumo_item),
        "resumo_pavimento": dict(resumo),
        "compra": res["compras"].get(code),
        "disponiveis": {
            "sobras": sobras,
            "itens": itens_disponiveis(disp["anterior"]["montados"] + disp["antigo"]["montados"]),
        },
    }
