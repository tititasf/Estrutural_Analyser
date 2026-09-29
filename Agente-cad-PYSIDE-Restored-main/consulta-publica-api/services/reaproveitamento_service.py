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
Estoque acumula e se gasta (D-72) na ordem cadastrada pelo dono (D-74).
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
import tempfile
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from pathlib import Path
from typing import Optional

from services import materiais_service as ms
from services.plano_de_corte import PERDA_CORTE, compra_de_grupos, material_da_bitola
from services.resolve_service import resolver_code
from services.obra_context import comportamento_obra, pavimentos_ordenados

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


def ordem_pavimento(pav: str) -> tuple:
    """Posição do pavimento na obra, de baixo para cima: subsolos (2SS abaixo
    do 1SS), térreo, pavimentos numerados e, por fim, os nomeados (cobertura,
    deck…). Provisório até o portal de fôrmas gravar a ordem da obra (anterior/
    próximo por pavimento, com o tipo 2–10 como um pavimento só)."""
    s = str(pav or "").upper()
    m = re.search(r"(\d+)\s*_?\s*(SS|SUB)", s)
    if m or "SUB" in s:
        return (0, -int(m.group(1)) if m else -1, s)
    n = numero_pavimento(pav)
    if n is not None:
        return (1, n, s)
    return (2, 0, s)


def cadeia(conn, obra_id: str, pav: str) -> list[str]:
    """Todos os pavimentos da obra até `pav`, na ordem da obra (de baixo para
    cima). Pavimento que não existe no cadastro não quebra a sequência: o
    anterior é o que vem antes na ordem (dono, 29/09)."""
    ordem_dono = [r["pavimento"] for r in pavimentos_ordenados(obra_id)]
    if ordem_dono:
        if pav not in ordem_dono:
            return [pav]
        return ordem_dono[:ordem_dono.index(pav) + 1]
    pavs = {r[0] for r in conn.execute(
        "SELECT DISTINCT pavimento FROM public_codes WHERE obra_id = ? AND kind = 'item' AND revoked = 0",
        (obra_id,))} | {pav}
    ordem = sorted(pavs, key=ordem_pavimento)
    return ordem[: ordem.index(pav) + 1]


def ocorrencias_pavimentos(conn, obra_id: str, pav: str) -> list[tuple[str, str, str | None]]:
    """Expande somente no cálculo o TIPO cadastrado uma vez no portal.

    Cada repetição consome o estoque da anterior. O terceiro campo identifica
    as peças que saem da repetição, evitando confundir dois painéis com o mesmo
    ID físico no estoque acumulado. A ficha do TIPO representa a última
    repetição da faixa, já com o reaproveitamento das anteriores.
    """
    cadastro = {r["pavimento"]: r for r in pavimentos_ordenados(obra_id)}
    resultado = []
    for nome in cadeia(conn, obra_id, pav):
        tipo = (cadastro.get(nome) or {}).get("tipo")
        if tipo and isinstance(tipo.get("de"), int) and isinstance(tipo.get("ate"), int) \
                and 1 <= tipo["de"] <= tipo["ate"]:
            resultado.extend((nome, f"{nome} ({n}º)", f"{nome}@{n}")
                             for n in range(tipo["de"], tipo["ate"] + 1))
        else:
            resultado.append((nome, nome, None))
    return resultado


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


def alocar_pavimento(classes: dict[str, list[dict]], anterior: dict, antigo: dict) -> dict:
    """Aloca um pavimento inteiro de um cenário (Para ou Passa, D-78).

    `classes` = {classe: itens}. `anterior`/`antigo` = estoque:
        montados  {classe: [...]}  painel montado — só volta na própria classe
        limpas    [...]            sobra limpa de chapa (sem sarrafo) — qualquer classe (D-75)
        da_classe {classe: [...]}  retalho de painel montado (leva sarrafo) — só na classe
        barras    {classe: [...]}  sobra de barra (sarrafo)
    Montados: etapas por classe. Sobras: os maiores painéis pendentes de TODAS
    as classes escolhem primeiro (D-77). As listas de sobras são consumidas e
    estendidas aqui (o resto de uma sobra cortada continua no estoque)."""
    aloc: dict[str, dict] = {}
    retalhos: dict[str, list[dict]] = {c: [] for c in classes}
    usados: set[str] = set()

    def registra(p, etapa, fonte, info, tipo_fonte, cls):
        aloc[p["id"]] = {"etapa": etapa, "fonte_id": fonte.get("id"), "fonte_tipo": tipo_fonte,
                         "fonte_item": fonte.get("titulo") or fonte.get("item"),
                         "fonte_pavimento": fonte.get("pavimento"),
                         "fonte_classe": fonte.get("classe"),
                         "fonte_medida": [fonte.get("largura_cm"), fonte.get("altura_cm")],
                         "corte": info.get("corte")}
        usados.add(fonte.get("id"))
        if tipo_fonte == "montado":  # retalho de painel montado leva sarrafo: fica na classe
            for n, (rw, rh) in enumerate(info.get("retalhos") or [], 1):
                retalhos[cls].append({"id": f"{fonte.get('id')}-R{n}", "tipo": "chapa",
                                      "material": "Retalho de painel montado", "classe": cls,
                                      "largura_cm": rw, "altura_cm": rh, "retalho_de": fonte.get("id")})

    def melhor_montado(tipo, p, pool, cortar):
        cand = []
        for s in pool:
            if s["id"] in usados:
                continue
            info = encaixe(tipo, s, p, cortar)
            if info is not None:
                cand.append((_area(s), s, info))
        return min(cand, key=lambda c: c[0])[1:] if cand else None

    def pendentes(itens, maiores_primeiro=False):
        ps = [p for it in itens for p in it["paineis"] if p["id"] not in aloc]
        return sorted(ps, key=_area, reverse=True) if maiores_primeiro else ps

    def tipo_de(itens):
        return itens[0]["tipo"] if itens else ""

    # 1 / 1.5 — próprio item; 2 / 2.5 — montados que os donos não usaram.
    # Cada etapa roda para todos os itens da classe antes da seguinte.
    for cls, itens in classes.items():
        montados = [s for s in anterior["montados"].get(cls, []) if s.get("reaproveitavel", True)]
        por_chave: dict[str, list[dict]] = {}
        for s in montados:
            por_chave.setdefault(s["chave"], []).append(s)
        for etapa, cortar in (("1", False), ("1.5", True)):
            for it in itens:
                for p in sorted([p for p in it["paineis"] if p["id"] not in aloc], key=_area, reverse=cortar):
                    achado = melhor_montado(tipo_de(itens), p, por_chave.get(it["chave"], []), cortar)
                    if achado:
                        registra(p, etapa, achado[0], achado[1], "montado", cls)
        temporaria = [s for s in montados if s["id"] not in usados]
        for etapa, cortar in (("2", False), ("2.5", True)):
            for p in pendentes(itens, cortar):
                achado = melhor_montado(tipo_de(itens), p, temporaria, cortar)
                if achado:
                    registra(p, etapa, achado[0], achado[1], "montado", cls)

    def por_sobras(etapa_ig, etapa_corte, est):
        for etapa, cortar in ((etapa_ig, False), (etapa_corte, True)):
            pend = sorted(((cls, p) for cls, itens in classes.items() for p in pendentes(itens)),
                          key=lambda cp: _area(cp[1]), reverse=True)
            for cls, p in pend:
                cand = []
                for pool in (est["limpas"], est["da_classe"].setdefault(cls, [])):
                    for s in pool:
                        if s["id"] in usados:
                            continue
                        info = _encaixe_sobra(s, p, cortar)
                        if info is not None:
                            W, H = _ret_sobra(s)
                            cand.append((W * H, s["id"], s, info, pool))
                if not cand:
                    continue
                _, _, s, info, pool = min(cand, key=lambda c: (c[0], c[1]))
                registra(p, etapa, s, info, "sobra", cls)
                # O resto da sobra continua disponível, com a mesma natureza.
                filhos = sum(1 for c in pool if c["id"].startswith(s["id"] + "."))
                for n, (rw, rh) in enumerate(info["retalhos"], filhos + 1):
                    pool.append({"id": f"{s['id']}.{n}", "tipo": "chapa", "material": s.get("material"),
                                 "classe": s.get("classe"), "largura_cm": rw, "altura_cm": rh,
                                 "pavimento": s.get("pavimento")})

    por_sobras("3", "3.5", anterior)
    # 4 / 4.5 — estoque antigo: montados (por classe), depois sobras.
    for cls, itens in classes.items():
        antigos = [s for s in antigo["montados"].get(cls, []) if s.get("reaproveitavel", True)]
        for etapa, cortar in (("4", False), ("4.5", True)):
            for p in pendentes(itens, cortar):
                achado = melhor_montado(tipo_de(itens), p, antigos, cortar)
                if achado:
                    registra(p, etapa, achado[0], achado[1], "montado", cls)
    por_sobras("4", "4.5", antigo)

    # Material novo + sarrafos (sobras de barra da classe primeiro).
    tem_estoque = any(anterior["montados"].values()) or any(antigo["montados"].values()) \
        or bool(anterior["limpas"] or antigo["limpas"])
    compras: dict[str, dict] = {}
    barras_restantes: dict[str, list[dict]] = {}
    for cls, itens in classes.items():
        barras = [dict(b) for b in anterior["barras"].get(cls, []) + antigo["barras"].get(cls, [])]
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
            # "-N" separa esta compra da "Preparação com materiais novos";
            # sem estoque as duas coincidem e os IDs também.
            compra = compra_de_grupos(grupos_novo, prefixo + ("-N" if tem_estoque else ""))
            compra["barras_de_sobra"] = de_sobra
            compras[item["code"]] = compra
        barras_restantes[cls] = barras
    return {"alocacao": aloc, "compras": compras, "retalhos": retalhos, "usados": usados,
            "barras_restantes": barras_restantes}


# --------------------------------------------------------------------------- #
# Cenários (D-78) e cadeia de pavimentos
# --------------------------------------------------------------------------- #

CENARIOS = ("para", "passa")


def cenarios_da_classe(classe: str) -> list[str]:
    """Pilares e laterais têm modo; fundo e laje entram nos dois cenários."""
    if classe.endswith("_para"):
        return ["para"]
    if classe.endswith("_passa"):
        return ["passa"]
    return list(CENARIOS)


def classes_do_cenario(conn, obra_id: str, cenario: str) -> list[str]:
    cls = {r[0] for r in conn.execute(
        "SELECT DISTINCT classe FROM public_codes WHERE obra_id = ? AND kind = 'item' AND revoked = 0",
        (obra_id,))}
    return sorted(c for c in cls if c and cenario in cenarios_da_classe(c))


def vazio(classes) -> dict:
    return {"montados": {c: [] for c in classes}, "limpas": [],
            "da_classe": {c: [] for c in classes}, "barras": {c: [] for c in classes}}


def _estoque_do_pavimento(classes: dict[str, list[dict]], pav: str, r: dict,
                         repeticao: str | None = None) -> dict:
    """O que o pavimento deixa ao ser desformado: painéis montados
    reaproveitáveis, sobras do que foi comprado (chapa = limpa, circula entre
    classes) e retalhos de montados (ficam na classe)."""
    est = vazio(classes)
    for cls, itens in classes.items():
        est["montados"][cls] = [{**p, "pavimento": pav, "classe": cls}
                                for it in itens for p in it["paineis"] if p.get("reaproveitavel", True)]
        for it in itens:
            for s in (r["compras"].get(it["code"]) or {}).get("sobras") or []:
                if s.get("tipo") == "chapa":
                    est["limpas"].append({**s, "pavimento": pav, "classe": cls})
                else:
                    est["barras"][cls].append({**s, "pavimento": pav})
        est["da_classe"][cls] = [{**x, "pavimento": pav} for x in r["retalhos"].get(cls, [])]
    if repeticao:
        # Um TIPO é um único cadastro, mas cada concretagem produz peças
        # distintas. Sem IDs por ocorrência, a etapa 4 poderia reutilizar a
        # mesma peça de repetições diferentes como se fosse uma só.
        for grupo in ("montados", "da_classe", "barras"):
            for pecas in est[grupo].values():
                for peca in pecas:
                    peca["id"] = f"{repeticao}|{peca['id']}"
        for peca in est["limpas"]:
            peca["id"] = f"{repeticao}|{peca['id']}"
    return est


def calcular_cenario(conn, obra_id: str, pav: str, cenario: str, root: Path) -> Optional[dict]:
    ocorrencias = ocorrencias_pavimentos(conn, obra_id, pav)
    pavs = [nome for nome, _, _ in ocorrencias]
    classes = classes_do_cenario(conn, obra_id, cenario)
    invs = {p: {c: inventario(conn, obra_id, p, c, root) for c in classes}
            for p in dict.fromkeys(pavs)}
    chave = hashlib.sha1(json.dumps(["cenario-2", obra_id, cenario, ocorrencias, [
        [c, i["code"], [q["id"] + str(q["largura_cm"]) + str(q["altura_cm"]) for q in i["paineis"]]]
        for p in pavs for c in classes for i in invs[p][c]]], sort_keys=True).encode()).hexdigest()
    with _lock:
        if chave in _memoria:
            return _memoria[chave]
    anterior, antigo = vazio(classes), vazio(classes)
    res = None
    for k, (p, rotulo, repeticao) in enumerate(ocorrencias):
        disponivel = {"anterior": copy.deepcopy(anterior), "antigo": copy.deepcopy(antigo)}
        r = alocar_pavimento(invs[p], anterior, antigo)
        if k == len(ocorrencias) - 1:
            res = {"pavimento": p, "pavimentos": [rot for _, rot, _ in ocorrencias],
                   "cenario": cenario, "classes": invs[p],
                   "disponivel": disponivel, **r}
            break
        u = r["usados"]
        # Sobe para o próximo: o que não foi usado vira estoque antigo.
        antigo = {
            "montados": {c: [s for s in anterior["montados"][c] + antigo["montados"][c] if s["id"] not in u]
                         for c in classes},
            "limpas": [s for s in anterior["limpas"] + antigo["limpas"] if s["id"] not in u],
            "da_classe": {c: [s for s in anterior["da_classe"][c] + antigo["da_classe"][c] if s["id"] not in u]
                          for c in classes},
            "barras": r["barras_restantes"],
        }
        anterior = _estoque_do_pavimento(invs[p], rotulo, r, repeticao)
    with _lock:
        _memoria[chave] = res
        while len(_memoria) > 4:  # o estoque de um cenário é grande
            _memoria.pop(next(iter(_memoria)))
    return res


# --------------------------------------------------------------------------- #
# Cálculo em segundo plano: a 1ª medição de um cenário leva minutos
# --------------------------------------------------------------------------- #

FRESCO_S = 300
_resultados: dict[tuple, tuple[float, Optional[dict]]] = {}
_em_curso: set[tuple] = set()
_fila = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reaproveitamento")


def _caminho_db(conn) -> str:
    return conn.execute("PRAGMA database_list").fetchone()[2]


def _disparar(chave: tuple, db: str, root: Path) -> None:
    with _lock:
        if chave in _em_curso:
            return
        _em_curso.add(chave)

    def trabalho():
        try:
            c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, check_same_thread=False)
            c.row_factory = sqlite3.Row
            try:
                res = calcular_cenario(c, *chave[:3], root)
            finally:
                c.close()
            with _lock:
                _resultados[chave] = (time.time(), res)
        except Exception:  # noqa: BLE001 — registra; o próximo pedido tenta de novo
            log.exception("reaproveitamento %s falhou", chave)
        finally:
            with _lock:
                _em_curso.discard(chave)

    _fila.submit(trabalho)


def resultado_cenario(conn, obra_id: str, pav: str, cenario: str, root: Path) -> tuple[bool, Optional[dict]]:
    """(pronto, resultado). Um resultado com mais de FRESCO_S continua servido
    enquanto é recalculado em segundo plano."""
    # Uma edição da ordem ou da faixa TIPO invalida o resultado imediatamente,
    # sem esperar o TTL de cinco minutos do cálculo anterior.
    chave = (obra_id, pav, cenario, tuple(ocorrencias_pavimentos(conn, obra_id, pav)))
    with _lock:
        pronto = _resultados.get(chave)
    if pronto is None or time.time() - pronto[0] > FRESCO_S:
        _disparar(chave, _caminho_db(conn), root)
    return (pronto is not None, pronto[1] if pronto else None)


# --------------------------------------------------------------------------- #
# Resposta da ficha
# --------------------------------------------------------------------------- #

def _publico_montado(p: dict) -> dict:
    return {k: p.get(k) for k in ("id", "largura_cm", "altura_cm", "pontas", "tipo", "grupo")}


def montar_resposta(res: dict, row) -> Optional[dict]:
    pav, classe, code = row["pavimento"], row["classe"], row["code"]
    itens = res["classes"].get(classe) or []
    item = next((i for i in itens if i["code"] == code), None)
    if item is None:
        return None
    aloc = res["alocacao"]
    usado_por = {a["fonte_id"]: pid for pid, a in aloc.items() if a.get("fonte_id")}
    for its in res["classes"].values():  # sobra de barra cortada em sarrafo
        for it in its:
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

    def publica(s, limpa):
        return {k: s[k] for k in ("id", "tipo", "material", "largura_cm", "altura_cm", "comprimento_cm", "util")
                if s.get(k) is not None} | {"usado_por": usado_por.get(s["id"]), "limpa": limpa}

    estoques = (disp["anterior"], disp["antigo"])
    sobras = ([publica(s, True) for e in estoques for s in e["limpas"]]
              + [publica(s, False) for e in estoques for s in e["da_classe"].get(classe, [])]
              + [publica(s, False) for e in estoques for s in e["barras"].get(classe, [])])
    paineis = []
    for p in item["paineis"]:
        a = aloc.get(p["id"], {"etapa": "novo"})
        paineis.append({"id": p["id"], "numero": p["numero"], "grupo": p["grupo"],
                        "largura_cm": p["largura_cm"], "altura_cm": p["altura_cm"],
                        "pontas": p["pontas"], "tipo": p["tipo"], **a})
    ids_classe = {p["id"] for it in itens for p in it["paineis"]}
    anteriores = res["pavimentos"][:-1]
    return {
        "pavimento": pav,
        "pavimento_anterior": anteriores[-1] if anteriores else None,
        "pavimentos_cadeia": res["pavimentos"],
        # Fundo e laje valem para os dois cenários: não citam Para/Passa (D-78).
        "cenario": res["cenario"] if len(cenarios_da_classe(classe)) == 1 else None,
        "etapas": ETAPAS,
        "item": {"titulo": item["titulo"], "chave": item["chave"]},
        "paineis": paineis,
        "resumo_item": dict(Counter(p["etapa"] for p in paineis)),
        "resumo_pavimento": dict(Counter(a["etapa"] for pid, a in aloc.items() if pid in ids_classe)),
        "compra": res["compras"].get(code),
        "disponiveis": {
            "sobras": sobras,
            "itens": itens_disponiveis([s for e in estoques for s in e["montados"].get(classe, [])]),
        },
    }


def obter_reaproveitamento(conn, row, root: Path) -> Optional[dict]:
    """Resposta da ficha, ou {"calculando": True} enquanto o cenário é medido.
    Fundo/laje usam o modo da obra; Misto mantém o cenário Para padrão."""
    cenarios = cenarios_da_classe(row["classe"])
    modo = comportamento_obra(conn, row["obra_id"])
    cenario = ("passa" if modo == "passa" and "passa" in cenarios else cenarios[0])
    pronto, res = resultado_cenario(conn, row["obra_id"], row["pavimento"], cenario, root)
    if not pronto:
        return {"calculando": True}
    return montar_resposta(res, row) if res else None
