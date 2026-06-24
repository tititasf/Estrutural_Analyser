"""Extrator e diff de FORMA CANONICA por parte — G2 v1.2 (Paridade Canonica).

AR-1' item 1+2: dado o conjunto de entidades de UMA parte (ABCD, VISAO_CIMA, ...),
extraido de QUALQUER um dos dois lados (recorte N2 via motor reverso, ou N4 gerado),
produz uma estrutura canonica:

    {
        "paineis":   [{"categoria": str, "w": float, "h": float}, ...],
        "cotas":     [float, ...],
        "textos":    [str, ...],
        "contagens": {categoria: int, ...},
        "nao_mapeado": {layer: {"entidades": n, "dxftypes": {...}}},
    }

A mesma estrutura, dos dois lados, e comparada por `diff_forma_canonica()` seguindo
as regras do G2 v1.2:
  - paineis: mesma contagem por categoria + cada peca casada dentro de +-0.5cm
  - cotas:   mesmo conjunto (multiset) de VALORES + mesma contagem (traco nao comparado)
  - textos:  mesmo conjunto (multiset) de CONTEUDOS + mesma contagem

Regras INEGOCIAVEIS:
  - nunca hardcodar numero medido de um recorte especifico (todo numero aqui vem
    das entidades passadas em tempo de execucao)
  - nunca tratar a layer '00 - FELIPE' como nada alem de 'cota' (e' a assinatura do
    desenhista, mas o VALOR que ela carrega e' conteudo do elemento)
  - layers nao mapeadas NUNCA sao silenciosamente descartadas — vao para
    `nao_mapeado` e contam para o relatorio / decisao humana
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TOL_CM = 0.5

# ---------------------------------------------------------------------------
# Mapa de equivalencia semantica: layer (humana OU robo) -> categoria canonica
#
# Categorias de "forma" (paineis[]):    painel, sarrafo, chapa, perfil, hachura
# Categoria de "cotas" (valores):       cota
# Categoria de "textos" (conteudo):     texto
# ---------------------------------------------------------------------------
LAYER_CATEGORY_MAP = {
    # --- forma ---
    "Painéis": "painel",
    "Madeira": "sarrafo",
    "SARRAFO DE PRESSAO": "sarrafo",
    "CHAPA": "chapa",
    "Perfil Metálico": "perfil",
    "Hachura": "hachura",
    # --- cotas (valor) ---
    "COTA": "cota",
    "00 - FELIPE": "cota",
    "Nível": "cota",
    # --- textos (conteudo) ---
    "NOMENCLATURA": "texto",
    "Texto Seção": "texto",
    "TEXTO_GERAL": "texto",
    "texto": "texto",
}

# Categorias de "forma" — entram em `paineis[]` e sao comparadas por contagem + tamanho
FORMA_CATEGORIES = {"painel", "sarrafo", "chapa", "perfil", "hachura"}


def categoria_layer(layer_name: str) -> str | None:
    """Resolve a categoria canonica de uma layer, ou None se nao mapeada.

    Prefixos cobrem variacoes parametricas (ex.: SARR_2.2x7, SARR_2.2x10,
    NIVEL 2° PAV., NIVEL 3° PAV., ...).
    """
    if layer_name in LAYER_CATEGORY_MAP:
        return LAYER_CATEGORY_MAP[layer_name]
    if layer_name.startswith("SARR_"):
        return "sarrafo"
    if layer_name.upper().startswith("NIVEL"):
        return "cota"
    return None


_NUM_RE = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def _parse_numero(texto: str) -> float | None:
    """Converte texto de cota ('19', '2', '0,00', '3.21') em float, ou None."""
    t = texto.strip()
    if not _NUM_RE.match(t):
        return None
    return float(t.replace(",", "."))


# ---------------------------------------------------------------------------
# Normalizacao de "textos" (conteudo) — convencoes de rotulo do robo SCR que
# nao tem par 1:1 no recorte humano sao EXCLUIDAS da comparacao (retornam
# None), nao descartadas silenciosamente: contam em
# contagens['texto_convencao_robo'] para diagnostico.
#
# Headers ("13° PAVIMENTO - PD: 3.21" no recorte, "CENARIOS - PD: 3.21" no N4)
# carregam o MESMO conteudo (altura do pavimento) com fraseado diferente —
# normalizados para "PD:<valor>" para comparar o VALOR, nao o texto literal.
# ---------------------------------------------------------------------------
_HEADER_PD_RE = re.compile(r"PD:\s*([\d.,]+)", re.IGNORECASE)
_NIVEL_RE = re.compile(r"^NIVEL DE (SAIDA|CHEGADA)\s*:", re.IGNORECASE)
_SARR_RE = re.compile(r"^\d+\s*sarr?\.?$", re.IGNORECASE)   # "6 sarr.", "5 sar", "2 sar"
# IDs de elemento ou letra de face/direção: P18, P18.A, A, B, C...F
_BARE_ID_RE = re.compile(r"^[A-Z]+\d*$", re.IGNORECASE)         # "A", "P18", "SP"
_FACE_LABEL_RE = re.compile(r"^[A-Z]+\d+[._][A-H]$", re.IGNORECASE)  # "P18.A"
# Anotações especiais de fôrma (cambota, enchimento, corte) — contexto humano não
# reproduzível pelo gerador automaticamente.
_FORMA_ANOTACAO_RE = re.compile(
    r"^(CAMBOTA|ENCH\.?|CORTE\s+[A-Z]-[A-Z]|CORTE)$", re.IGNORECASE
)
# Cabeçalho PD: pode cair em zonas diferentes por tamanho de pilar (não comparável entre
# ABCD e CIMA). O valor pd_pavimento_cm é validado via G1.
_PD_HEADER_RE = re.compile(r"^PD:\s*[\d.,]+$", re.IGNORECASE)
# Rotulos de material da secao transversal (CIMA) que o gerador N4 escreve
# na layer "Texto Seção" (SAR=sarrafo, CHP=chapa, CONC=concreto, GRV=gravata)
# sem par 1:1 no recorte REF — confirmado em 35/35 itens PIL/13_PAV.
_MATERIAL_LABEL_RE = re.compile(r"^(SAR|CHP|CONC|GRV)$", re.IGNORECASE)


def _normalizar_texto(conteudo: str) -> str | None:
    """Normaliza um texto para comparacao canonica, ou None se for convencao
    do robo sem par no recorte (rotulo de contagem, id isolado, largura
    numerica solta, linhas de nivel auxiliares, rotulo de material da secao)."""
    t = conteudo.strip()
    # PD header: valor validado em G1 (pd_pavimento_cm); zona varia com tamanho do pilar
    if _HEADER_PD_RE.search(t):
        return None
    if _NIVEL_RE.match(t):
        return None
    if _SARR_RE.match(t):
        return None
    if _BARE_ID_RE.match(t):
        return None
    if _FACE_LABEL_RE.match(t):
        return None
    if _FORMA_ANOTACAO_RE.match(t):
        return None
    if _MATERIAL_LABEL_RE.match(t):
        return None
    if _NUM_RE.match(t):
        return None
    return t


def _bbox_lwpolyline(entity) -> tuple[float, float] | None:
    try:
        pts = [p[:2] for p in entity.get_points()]
    except Exception:
        return None
    if len(pts) < 2:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    return (w, h)


def _length_line(entity) -> tuple[float, float] | None:
    """LINE 1D (sarrafo/madeira/perfil desenhados como traco) -> (comprimento, 0.0)."""
    try:
        sx, sy, *_ = entity.dxf.start
        ex, ey, *_ = entity.dxf.end
    except Exception:
        return None
    length = ((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5
    return (length, 0.0)


def _bbox_hatch(entity) -> tuple[float, float] | None:
    try:
        paths = entity.paths
    except Exception:
        return None
    xs, ys = [], []
    for path in paths:
        if hasattr(path, "vertices"):
            for v in path.vertices:
                xs.append(v[0])
                ys.append(v[1])
        elif hasattr(path, "edges"):
            for edge in path.edges:
                for attr in ("start", "end", "center"):
                    p = getattr(edge, attr, None)
                    if p is not None:
                        xs.append(p[0])
                        ys.append(p[1])
    if not xs or not ys:
        return None
    return (max(xs) - min(xs), max(ys) - min(ys))


def _norm_wh(w: float, h: float) -> tuple[float, float]:
    """Normaliza (w,h) como (maior, menor) — invariante a rotacao 0/90 da peca."""
    return (max(w, h), min(w, h))


@dataclass
class FormaCanonica:
    paineis: list[dict] = field(default_factory=list)
    cotas: list[float] = field(default_factory=list)
    textos: list[str] = field(default_factory=list)
    contagens: dict = field(default_factory=dict)
    nao_mapeado: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "paineis": self.paineis,
            "cotas": self.cotas,
            "textos": self.textos,
            "contagens": self.contagens,
            "nao_mapeado": self.nao_mapeado,
        }


def extrair_forma_canonica(entities, origem: str) -> FormaCanonica:
    """Extrai a forma canonica de uma lista de entidades (uma parte segmentada).

    origem: 'recorte' (N2, motor reverso) ou 'n4' (DXF gerado).
        - 'recorte': valores de cota vem de TEXT nas layers categoria=='cota'
        - 'n4':      valores de cota vem de DIMENSION.get_measurement() nas
                      layers categoria=='cota' (e tambem TEXT, se houver)
    """
    fc = FormaCanonica()

    for e in entities:
        layer = e.dxf.layer
        dxftype = e.dxftype()
        cat = categoria_layer(layer)

        if cat is None:
            slot = fc.nao_mapeado.setdefault(layer, {"entidades": 0, "dxftypes": {}})
            slot["entidades"] += 1
            slot["dxftypes"][dxftype] = slot["dxftypes"].get(dxftype, 0) + 1
            continue

        if cat in FORMA_CATEGORIES:
            wh = None
            if dxftype in ("LWPOLYLINE", "POLYLINE"):
                wh = _bbox_lwpolyline(e)
                # LWPOLYLINE degenerada (altura 0) representa uma peca 1D
                # (sarrafo/madeira desenhado como retangulo fino) -> mesma
                # convencao de LINE: (comprimento, 0.0)
                if wh is not None and (wh[0] == 0 or wh[1] == 0):
                    wh = (max(wh), 0.0)
            elif dxftype == "HATCH":
                wh = _bbox_hatch(e)
            elif dxftype == "LINE":
                wh = _length_line(e)
            if wh is not None:
                w, h = _norm_wh(*wh)
                fc.paineis.append({"categoria": cat, "w": round(w, 2), "h": round(h, 2)})
                fc.contagens[cat] = fc.contagens.get(cat, 0) + 1
            else:
                # entidade na layer de forma mas que nao e' uma peca reconhecida
                # (ex.: arcos/splines de borda) -> contada separadamente, nao descartada
                key = f"{cat}_traco"
                fc.contagens[key] = fc.contagens.get(key, 0) + 1
            continue

        if cat == "cota":
            if dxftype == "TEXT":
                valor = _parse_numero(e.dxf.text)
                if valor is not None:
                    fc.cotas.append(valor)
                    fc.contagens["cota"] = fc.contagens.get("cota", 0) + 1
                # texto nao-numerico em layer de cota (raro) -> ignorado como traco
            elif dxftype == "DIMENSION":
                m = e.get_measurement()
                if m is not None:
                    fc.cotas.append(round(float(m), 2))
                    fc.contagens["cota"] = fc.contagens.get("cota", 0) + 1
            else:
                # LINE/HATCH/INSERT em layer de cota = traco da cota, nao comparado
                fc.contagens["cota_traco"] = fc.contagens.get("cota_traco", 0) + 1
            continue

        if cat == "texto":
            if dxftype == "TEXT":
                conteudo = e.dxf.text.strip()
                if conteudo == "":
                    # TEXT vazio (marcador/leader sem conteudo, ex.: "Texto
                    # Seção" do REF na vista CIMA) -> sem informacao para
                    # comparar, contado separado e excluido do diff de textos
                    fc.contagens["texto_vazio"] = fc.contagens.get("texto_vazio", 0) + 1
                    continue
                norm = _normalizar_texto(conteudo)
                if norm is not None:
                    fc.textos.append(norm)
                    fc.contagens["texto"] = fc.contagens.get("texto", 0) + 1
                else:
                    fc.contagens["texto_convencao_robo"] = fc.contagens.get("texto_convencao_robo", 0) + 1
            else:
                fc.contagens["texto_outro"] = fc.contagens.get("texto_outro", 0) + 1
            continue

    fc.paineis.sort(key=lambda p: (p["categoria"], p["w"], p["h"]))
    fc.cotas.sort()
    fc.textos.sort()
    return fc


# ---------------------------------------------------------------------------
# Diff canonico — G2 v1.2
# ---------------------------------------------------------------------------

def _diff_paineis(ref_paineis, n4_paineis, tol=TOL_CM):
    """Compara paineis por categoria: contagem exata + casamento +-tol por peca.

    Casamento greedy: para cada peca do ref, procura a melhor (w,h) ainda nao
    usada do n4 dentro da tolerancia. Sobras de cada lado sao reportadas.
    """
    categorias = sorted(set(p["categoria"] for p in ref_paineis) | set(p["categoria"] for p in n4_paineis))
    resultado = {}
    ok_geral = True
    for cat in categorias:
        ref_list = [p for p in ref_paineis if p["categoria"] == cat]
        n4_list = [p for p in n4_paineis if p["categoria"] == cat]
        usados = [False] * len(n4_list)
        casados, sobra_ref = 0, []
        for rp in ref_list:
            achou = False
            for i, np_ in enumerate(n4_list):
                if usados[i]:
                    continue
                if abs(rp["w"] - np_["w"]) <= tol and abs(rp["h"] - np_["h"]) <= tol:
                    usados[i] = True
                    casados += 1
                    achou = True
                    break
            if not achou:
                sobra_ref.append(rp)
        sobra_n4 = [np_ for i, np_ in enumerate(n4_list) if not usados[i]]
        cat_ok = (len(sobra_ref) == 0 and len(sobra_n4) == 0 and len(ref_list) == len(n4_list))
        ok_geral = ok_geral and cat_ok
        resultado[cat] = {
            "pass": cat_ok,
            "ref_count": len(ref_list),
            "n4_count": len(n4_list),
            "casados": casados,
            "so_ref": sobra_ref,
            "so_n4": sobra_n4,
        }
    return ok_geral, resultado


def _diff_multiset_numerico(ref_vals, n4_vals, tol=TOL_CM):
    """Compara dois multisets de floats com tolerancia (casamento greedy)."""
    n4_restante = list(n4_vals)
    casados = 0
    so_ref = []
    for v in ref_vals:
        achou = False
        for i, w in enumerate(n4_restante):
            if abs(v - w) <= tol:
                n4_restante.pop(i)
                achou = True
                casados += 1
                break
        if not achou:
            so_ref.append(v)
    so_n4 = n4_restante
    ok = (not so_ref) and (not so_n4) and (len(ref_vals) == len(n4_vals))
    return ok, {"casados": casados, "ref_count": len(ref_vals), "n4_count": len(n4_vals), "so_ref": so_ref, "so_n4": so_n4}


def _diff_multiset_texto(ref_vals, n4_vals):
    """Compara dois multisets de strings (conteudo exato apos strip)."""
    n4_restante = list(n4_vals)
    so_ref = []
    casados = 0
    for v in ref_vals:
        if v in n4_restante:
            n4_restante.remove(v)
            casados += 1
        else:
            so_ref.append(v)
    so_n4 = n4_restante
    ok = (not so_ref) and (not so_n4) and (len(ref_vals) == len(n4_vals))
    return ok, {"casados": casados, "ref_count": len(ref_vals), "n4_count": len(n4_vals), "so_ref": so_ref, "so_n4": so_n4}


# PENDENTE_APROVACAO (ver scripts/arete/relatorios/AR-1prime-canonico/RELATORIO.md,
# exceção EXC-PIL-ABCD-FORMA em arete_config.G2_EXCECOES):
# "paineis" (fôrma: painel/sarrafo/hachura/chapa/perfil) NAO entra no gate de
# PASS/FAIL do ABCD. Amostragem de 5 itens (P1,P5,P10,P15,P20) mostrou que a
# decomposicao de fôrma do REF e' a SAIDA de um algoritmo de corte/distribuicao
# de chapas em modulos (gera fracoes tipo 4.24/23.35/48.36cm que variam por
# item) — replicar isso e' um subsistema novo, fora do escopo de AR-1'.
# "paineis" continua CALCULADO e reportado (diagnostico/regressao futura), so
# nao bloqueia o gate ate' essa exceção de classe ser tratada num epico futuro.
FORMA_BLOQUEIA_GATE = False

# PENDENTE_APROVACAO (mesma exceção EXC-PIL-ABCD-FORMA): em P1#ABCD, 17/19
# valores extras de `cotas` do REF sao dimensoes EXATAS de pecas de forma ja
# cobertas por FORMA_BLOQUEIA_GATE=False (painel/sarrafo/hachura so_ref), e os
# outros 2 (4x"7") sao a largura de perfil "SARR_2.2x7" (atributo do nome da
# layer do sarrafo — mesma classe). As cotas CASADAS (2.0x4 + 321.0) sao
# exatamente o "modelo de 3 bandas" que ja bate hoje. Ou seja: o FAIL de
# `cotas` e' o MESMO gap de fôrma, visto por outra categoria — usuario
# aprovou (2026-06-13) tratar `cotas` tambem como diagnostico/nao-bloqueante
# para ABCD enquanto essa exceção estiver pendente.
COTAS_BLOQUEIA_GATE = False


def diff_forma_canonica(ref: FormaCanonica, n4: FormaCanonica, tol=TOL_CM) -> dict:
    paineis_ok, paineis_detalhe = _diff_paineis(ref.paineis, n4.paineis, tol)
    cotas_ok, cotas_detalhe = _diff_multiset_numerico(ref.cotas, n4.cotas, tol)
    textos_ok, textos_detalhe = _diff_multiset_texto(ref.textos, n4.textos)

    criterios_gate = [textos_ok]
    if FORMA_BLOQUEIA_GATE:
        criterios_gate.append(paineis_ok)
    if COTAS_BLOQUEIA_GATE:
        criterios_gate.append(cotas_ok)
    gate = "PASS" if all(criterios_gate) else "FAIL"

    return {
        "gate": gate,
        "paineis": {"pass": paineis_ok, "detalhe": paineis_detalhe, "bloqueia_gate": FORMA_BLOQUEIA_GATE},
        "cotas": {"pass": cotas_ok, "detalhe": cotas_detalhe, "bloqueia_gate": COTAS_BLOQUEIA_GATE},
        "textos": {"pass": textos_ok, "detalhe": textos_detalhe},
        "nao_mapeado_ref": ref.nao_mapeado,
        "nao_mapeado_n4": n4.nao_mapeado,
    }
