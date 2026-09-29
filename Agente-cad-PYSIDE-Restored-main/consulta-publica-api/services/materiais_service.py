"""Materiais e Construção — quantitativo MEDIDO no DXF N3 desenhado [2026-09-28].

O pedido do dono é quantificar painéis e sarrafos por item. A fonte é o N3
que a equipe recebe: cada gerador já aplica as regras dele (módulo de 244 cm,
barra de sarrafo ≤ 300 cm, posições por altura...). Reescrever essas regras
aqui criaria uma segunda verdade que diverge do desenho. Medir o desenho
garante que a lista é exatamente o que foi desenhado.

Convenções dos geradores (verificadas nos DXFs de produção):
- painel = célula fechada pelas linhas da layer `Painéis`/`PAINEIS`;
- sarrafo = 1 entidade por peça (linha de centro ou retângulo), com a bitola
  no nome da layer (`SARR_2.2x7`, `SARR_3.5x7`, `SARR_2.2x10`,
  `Sarrafo de Pressão`, `SARRAFO_2_2X7`);
- entidade idêntica sobreposta é a mesma peça desenhada 2x (a LV duplica os
  sarrafos horizontais): conta uma vez.

O que NÃO é quantificado, por decisão do dono: vista Cima do pilar e Corte da
LV (são só perspectiva).
"""

from __future__ import annotations

import logging
import math
import re
import sys
import threading
from collections import Counter
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.ficha_service import payload_do_row, resolver_item_e_fichas

log = logging.getLogger(__name__)

_PAINEL = re.compile(r"^(pain[eé]is|paineis)$", re.I)
_SARRAFO = re.compile(r"^(sarr_|sarrafo)", re.I)
_BITOLA = re.compile(r"(\d+(?:[.,]\d+)?)\s*x\s*(\d+(?:[.,]\d+)?)", re.I)
_TOL = 1  # casas decimais (cm) para agrupar/deduplicar


def _segmentos_da_entidade(e) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    t = e.dxftype()
    if t == "LINE":
        return [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))]
    if t == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in e.get_points("xy")]
        if e.closed and pts:
            pts.append(pts[0])
        return list(zip(pts, pts[1:]))
    return []


def _assinatura(e) -> tuple:
    if e.dxftype() == "INSERT":
        return (e.dxf.name, round(e.dxf.insert.x, _TOL), round(e.dxf.insert.y, _TOL),
                round(e.dxf.rotation, _TOL))
    pts = [tuple(round(v, _TOL) for v in p) for s in _segmentos_da_entidade(e) for p in s]
    return tuple(sorted(pts))


def _comprimento_sarrafo(e) -> float:
    t = e.dxftype()
    if t == "INSERT":
        from ezdxf import bbox

        ext = bbox.extents([e])
        return max(ext.size.x, ext.size.y) if ext.has_data else 0.0
    if t == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in e.get_points("xy")]
        if e.closed and len(pts) >= 4:  # peça desenhada como retângulo: lado maior
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            return max(max(xs) - min(xs), max(ys) - min(ys))
    return sum(math.dist(a, b) for a, b in _segmentos_da_entidade(e))


def _nome_bitola(layer: str) -> str:
    low = layer.lower()
    if "press" in low:
        return "Sarrafo de pressão 2.2 x 7 cm"  # D-67: desenhado só pelo eixo
    # FV: SARR_5cm (viga 10–14 cm) e SARR_CONTORNO_10cm (viga < 10 cm).
    m = re.search(r"(\d+)\s*cm", low)
    if m:
        return f"Sarrafo 2.2 x {m.group(1)} cm"
    m = _BITOLA.search(layer.replace("_", "."))
    if m:
        a, b = (v.replace(",", ".") for v in m.groups())
        return f"Sarrafo {a} x {b} cm"
    return layer


def medir_dxf(path: Path) -> dict:
    """Painéis e sarrafos desenhados em 1 DXF N3."""
    import ezdxf
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union

    from ezdxf import bbox

    msp = ezdxf.readfile(str(path)).modelspace()
    linhas: list = []
    hachuras: list[tuple[float, float, float, float]] = []
    textos: list[tuple[float, float, str]] = []
    # peça de sarrafo = (bitola, comprimento, bbox)
    pecas_sarr: list[tuple[str, float, tuple[float, float, float, float]]] = []
    linhas_sarr: dict[str, list] = {}
    vistas: set = set()
    duplicados = 0
    for e in msp:
        layer = e.dxf.layer
        t = e.dxftype()
        if t == "HATCH":
            ext = bbox.extents([e])
            if ext.has_data:
                hachuras.append((ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y))
        elif t == "TEXT" and layer.upper() == "NOMENCLATURA":
            textos.append((e.dxf.insert.x, e.dxf.insert.y, e.dxf.text.strip()))
        elif _PAINEL.match(layer):
            linhas += [LineString(s) for s in _segmentos_da_entidade(e) if math.dist(*s) > 0.5]
        elif _SARRAFO.match(layer) and t in ("LINE", "LWPOLYLINE", "INSERT"):
            chave = (layer, t, _assinatura(e))
            if chave in vistas:
                duplicados += 1
                continue
            vistas.add(chave)
            if t == "LINE":  # as grades desenham cada peça como 4 LINEs
                linhas_sarr.setdefault(layer, []).append(e)
                continue
            comp = _comprimento_sarrafo(e)
            ext = bbox.extents([e])
            if comp > 0.5 and ext.has_data:
                pecas_sarr.append((_nome_bitola(layer), round(comp, _TOL),
                                   (ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y)))
    for layer, ents in linhas_sarr.items():
        pecas_sarr += _pecas_de_linhas(_nome_bitola(layer), ents)

    # 1 linha por painel físico, em ordem de leitura do desenho (de cima p/
    # baixo, da esquerda p/ a direita): o nº e o ID seguem o que se vê no N3.
    celulas: list[tuple] = []
    recortados = 0
    area_cm2 = 0.0
    if linhas:
        for pol in polygonize(unary_union(linhas)):
            x0, y0, x1, y1 = pol.bounds
            w, h = x1 - x0, y1 - y0
            if pol.area < 50 or min(w, h) < 3:
                continue
            retangulo = abs(pol.area - w * h) < 0.02 * w * h
            recortados += 0 if retangulo else 1
            area_cm2 += pol.area
            c = pol.representative_point()
            # Tira de escoramento: a LJ hachura a faixa estreita da união
            # (`_add_narrow_panel_hatches`, layer Hachura/REAPROVEITAMENTO).
            tira = any(a - 0.5 <= c.x <= b + 0.5 and d - 0.5 <= c.y <= e + 0.5
                       for a, d, b, e in hachuras)
            # Recortado: contorno real (cm, origem no canto inferior esquerdo do
            # retângulo envolvente) — plano de corte e 3D desenham a abertura.
            forma = None if retangulo else {"partes": _partes_locais([pol], x0, y0)}
            celulas.append((-round(y1), round(x0), round(w, _TOL), round(h, _TOL), not retangulo, tira,
                            (x0, y0, x1, y1), forma))
    celulas.sort(key=lambda c: c[:2])
    return {
        "paineis": [
            {"largura_cm": w, "altura_cm": h, "quantidade": 1, "recortado": rec, "tira": tira, "_bbox": bb,
             **(forma or {})}
            for _, _, w, h, rec, tira, bb, forma in celulas
        ],
        "paineis_total": len(celulas),
        "paineis_recortados": recortados,
        "paineis_area_m2": round(area_cm2 / 1e4, 2),
        "sarrafos": _resumo_sarrafos(pecas_sarr),
        "_pecas_sarrafo": pecas_sarr,
        "_textos": textos,
        "sarrafos_duplicados_ignorados": duplicados,
    }


def _partes_locais(pols: list, x0: float, y0: float) -> list[dict]:
    """Peças reais de um painel recortado: contorno + furos em cm locais
    (origem no canto inferior esquerdo do retângulo cortado da chapa, y p/ cima)."""
    local = lambda cs: [[round(x - x0, 1), round(y - y0, 1)] for x, y in list(cs)[:-1]]
    out = []
    for pol in pols:
        p = pol.simplify(0.05)
        out.append({"contorno": local(p.exterior.coords), "furos": [local(i.coords) for i in p.interiors]})
    return out


def _hachuras_poligonos(msp) -> list:
    """Área de cada HATCH como polígono (sem olhar layer): no ABCD do pilar é o
    concreto da viga/laje que chega na face — ali não há painel."""
    from ezdxf import path as dxfpath
    from shapely.geometry import Polygon

    pols = []
    for h in msp.query("HATCH"):
        for pa in dxfpath.from_hatch(h):
            vs = [(v.x, v.y) for v in pa.flattening(0.5)]
            if len(vs) >= 3:
                pol = Polygon(vs).buffer(0)
                if pol.area > 1:
                    pols.append(pol)
    return pols


def _pecas_de_linhas(bitola: str, ents: list) -> list[tuple]:
    """LINEs de uma layer de sarrafo. As grades desenham cada peça como um
    retângulo de 4 LINEs com cantos coincidentes: vira 1 peça (comprimento =
    lado maior). Só vale o retângulo cujos 4 lados são LINEs inteiras — duas
    barras paralelas próximas com os montantes das pontas também "fecham" um
    retângulo (FV: 447 x 5), mas são 4+ peças. LINE fora de retângulo = 1 peça."""
    r = lambda v: round(v, _TOL)
    segs = []
    for e in ents:
        (x0, y0), (x1, y1) = sorted([(r(e.dxf.start.x), r(e.dxf.start.y)), (r(e.dxf.end.x), r(e.dxf.end.y))])
        if math.dist((x0, y0), (x1, y1)) > 0.05:
            segs.append((x0, y0, x1, y1))
    existe = set(segs)
    usados: set = set()
    pecas: list[tuple] = []
    horiz = sorted((s for s in segs if s[1] == s[3]), key=lambda s: (s[0], s[2], s[1]))
    for base in horiz:
        if base in usados:
            continue
        x0, y0, x1, _ = base
        # parceira: mesma extensão em x, logo acima, a ≤ 12,5 cm
        for topo in horiz:
            y1 = topo[1]
            if topo is base or topo in usados or topo[0] != x0 or topo[2] != x1 or not 0 < y1 - y0 <= 12.5:
                continue
            esq, dir_ = (x0, y0, x0, y1), (x1, y0, x1, y1)
            if esq in existe and dir_ in existe and esq not in usados and dir_ not in usados:
                usados.update((base, topo, esq, dir_))
                pecas.append((bitola, r(max(x1 - x0, y1 - y0)), (x0, y0, x1, y1)))
                break
    # retângulo em pé (lados verticais longos)
    vert = sorted((s for s in segs if s[0] == s[2] and s not in usados), key=lambda s: (s[1], s[3], s[0]))
    for esq in vert:
        if esq in usados:
            continue
        x0, y0, _, y1 = esq
        for dir_ in vert:
            x1 = dir_[0]
            if dir_ is esq or dir_ in usados or dir_[1] != y0 or dir_[3] != y1 or not 0 < x1 - x0 <= 12.5:
                continue
            base, topo = (x0, y0, x1, y0), (x0, y1, x1, y1)
            if base in existe and topo in existe and base not in usados and topo not in usados:
                usados.update((base, topo, esq, dir_))
                pecas.append((bitola, r(max(x1 - x0, y1 - y0)), (x0, y0, x1, y1)))
                break
    for sg in segs:
        if sg not in usados:
            usados.add(sg)
            pecas.append((bitola, r(math.dist(sg[:2], sg[2:])), sg))
    return pecas


def _resumo_sarrafos(pecas: list[tuple]) -> list[dict]:
    por: dict[str, list[float]] = {}
    for bitola, comp, _ in pecas:
        por.setdefault(bitola, []).append(comp)
    return [
        {
            "bitola": bitola,
            "pecas": len(comps),
            "total_m": round(sum(comps) / 100, 2),
            "cortes": [{"comprimento_cm": c, "quantidade": n}
                       for c, n in sorted(Counter(comps).items(), reverse=True)],
        }
        for bitola, comps in sorted(por.items())
    ]


def _sobreposicao(p: tuple, c: tuple) -> float:
    """Quanto da peça `p` (bbox) corre dentro da célula `c` (bbox), medido no
    eixo longo da peça; -1 se não se tocam."""
    t = 0.5
    ix = min(p[2], c[2] + t) - max(p[0], c[0] - t)
    iy = min(p[3], c[3] + t) - max(p[1], c[1] - t)
    if ix < 0 or iy < 0:
        return -1.0
    return ix if (p[2] - p[0]) >= (p[3] - p[1]) else iy


def associar_sarrafos(grupo: dict) -> None:
    """Cada sarrafo vai para o painel sobre o qual ele mais corre: o painel
    passa a listar os próprios sarrafos. Sem painel que o contenha → `avulsos`."""
    paineis = [p for p in grupo.get("paineis") or [] if p.get("_bbox")]
    por_painel: dict[int, list[tuple]] = {}
    avulsos: list[tuple] = []
    for peca in grupo.get("_pecas_sarrafo") or []:
        melhor, idx = 0.5, None
        for i, p in enumerate(paineis):
            s = _sobreposicao(peca[2], p["_bbox"])
            if s > melhor:
                melhor, idx = s, i
        (por_painel.setdefault(idx, []) if idx is not None else avulsos).append(peca)
    todas: list[tuple] = list(avulsos)
    for i, p in enumerate(paineis):
        pecas = _parear_linhas(por_painel.get(i, []), p["_bbox"], _bordas_do_recorte(p))
        todas += pecas
        p["sarrafos"] = _cortes(pecas)
        p["montagem"] = _montagem(pecas, p["_bbox"])
    grupo["sarrafos_avulsos"] = _cortes(avulsos)
    grupo["sarrafos"] = _resumo_sarrafos(todas)


def _secao(bitola: str) -> tuple[float, float]:
    """(espessura, largura) da bitola; sem número na layer → 2,2 x 7."""
    m = _BITOLA.search(bitola)
    return tuple(sorted(float(v.replace(",", ".")) for v in m.groups())) if m else (2.2, 7.0)


def _bordas_do_recorte(painel: dict) -> list[tuple]:
    """Arestas retas das partes de um painel recortado, em coordenadas do
    desenho: ("h"|"v", coord, ini, fim). A linha de sarrafo junto do entalhe
    faz par com essa aresta, como faria com a borda do painel."""
    x0, y0 = painel["_bbox"][:2]
    out = []
    for parte in painel.get("partes") or []:
        for anel in [parte["contorno"], *parte.get("furos", [])]:
            for (ax, ay), (bx, by) in zip(anel, anel[1:] + anel[:1]):
                if abs(ay - by) < 0.1:
                    out.append(("h", y0 + ay, x0 + min(ax, bx), x0 + max(ax, bx)))
                elif abs(ax - bx) < 0.1:
                    out.append(("v", x0 + ax, y0 + min(ay, by), y0 + max(ay, by)))
    return out


def _parear_linhas(pecas: list[tuple], painel: tuple, bordas: list[tuple] = ()) -> list[tuple]:
    """No painel (LV, FV, ABCD) o sarrafo é desenhado pelas duas BORDAS: duas
    linhas paralelas = 1 sarrafo; a linha sozinha junto da borda do painel faz
    par com a própria borda. O par escolhido é o de distância mais próxima da
    largura da bitola (FV: linhas em 7 e 12 num painel de 19 são 2 sarrafos de
    7 contra as bordas, não 1 de 5). Linha sem par fica como está (1 peça)."""
    TOL = 1.5
    linhas, outras = [], []
    for pc in pecas:
        a, b, c, d = pc[2]
        if d - b < 0.5:
            linhas.append((pc, "h", b, a, c))
        elif c - a < 0.5:
            linhas.append((pc, "v", a, b, d))
        else:
            outras.append(pc)
    px0, py0, px1, py1 = painel
    cands = []
    for i, (pa, oa, ca, ia, fa) in enumerate(linhas):
        larg = _secao(pa[0])[1]
        # bordas do painel + arestas do recorte que correm ao lado da linha
        paredes = list((py0, py1) if oa == "h" else (px0, px1)) + [c for o, c, a, b in bordas
                                   if o == oa and min(fa, b) - max(ia, a) >= 0.8 * (fa - ia)]
        for parede in paredes:
            dist = abs(ca - parede)
            if abs(dist - larg) <= TOL:
                cands.append((abs(dist - larg), i, None, parede))
        for j in range(i + 1, len(linhas)):
            pb, ob, cb, ib, fb = linhas[j]
            if ob != oa or ("press" in pa[0].lower()) != ("press" in pb[0].lower()):
                continue
            sobre = min(fa, fb) - max(ia, ib)
            if sobre < 0.8 * min(fa - ia, fb - ib):
                continue
            dist = abs(ca - cb)
            if dist > 0.5 and abs(dist - larg) <= TOL:
                cands.append((abs(dist - larg), i, j, cb))
    usadas: set = set()
    out = list(outras)
    for _, i, j, outro in sorted(cands, key=lambda k: (k[0], k[2] is not None)):
        if i in usadas or (j is not None and j in usadas):
            continue
        usadas.add(i)
        pa, o, ca, ia, fa = linhas[i]
        if j is not None:
            usadas.add(j)
            ia, fa = min(ia, linhas[j][3]), max(fa, linhas[j][4])
        c0, c1 = sorted((ca, outro))
        bb = (ia, c0, fa, c1) if o == "h" else (c0, ia, c1, fa)
        out.append((pa[0], round(fa - ia, _TOL), bb))
    out += [linhas[i][0] for i in range(len(linhas)) if i not in usadas]
    return out


def _montagem(pecas: list[tuple], painel: tuple) -> list[dict]:
    """Posição de cada sarrafo no painel (cm, origem no canto inferior
    esquerdo do painel, y para cima), na ordem de montagem: primeiro os
    longos, por posição; pressão por último — ele é pregado na face de TRÁS
    do painel (linha HIDDEN no desenho). Linha que ficou sem par ganha a
    largura da bitola centrada nela."""
    x0, y0 = painel[0], painel[1]
    out = []
    for bitola, comp, (a, b, c, d) in pecas:
        esp, larg = _secao(bitola)
        w, h = c - a, d - b
        if w < 0.5:
            a, w = a - larg / 2, larg
        if h < 0.5:
            b, h = b - larg / 2, larg
        out.append({"bitola": bitola, "comprimento_cm": comp, "espessura_cm": esp,
                    "face": "tras" if "press" in bitola.lower() else "frente",
                    "x": round(a - x0, 1), "y": round(b - y0, 1), "w": round(w, 1), "h": round(h, 1)})
    out.sort(key=lambda s: (s["face"] == "tras", -max(s["w"], s["h"]), s["y"], s["x"]))
    return out


def _cortes(pecas: list[tuple]) -> list[dict]:
    c = Counter((b, comp) for b, comp, _ in pecas)
    return [{"bitola": b, "comprimento_cm": comp, "quantidade": n}
            for (b, comp), n in sorted(c.items(), key=lambda kv: (kv[0][0], -kv[0][1]))]


def separar_grades(grupo: dict) -> None:
    """Grades do pilar: cada grade é rotulada no desenho (`P1.A`, `P1.B`) à
    esquerda dela; a peça pertence ao rótulo mais próximo à sua esquerda."""
    rotulos = sorted((x, y, t) for x, y, t in grupo.get("_textos") or [] if re.search(r"\.[A-H]$", t))
    if not rotulos:
        return
    por: dict[str, list[tuple]] = {t: [] for _, _, t in rotulos}
    for peca in grupo.get("_pecas_sarrafo") or []:
        x0 = peca[2][0]
        esq = [r for r in rotulos if r[0] <= x0 + 1] or rotulos[:1]
        por[max(esq)[2]].append(peca)
    grupo["grades"] = [{"rotulo": t, "face": t.rsplit(".", 1)[-1], "pecas": _cortes_por_sentido(ps)}
                       for t, ps in por.items() if ps]


def _cortes_por_sentido(pecas: list[tuple]) -> list[dict]:
    """Peças da grade agrupadas por sentido: verticais primeiro, depois
    horizontais; dentro de cada sentido por bitola e comprimento (maior antes)."""
    def sentido(bb):
        return "vertical" if (bb[3] - bb[1]) > (bb[2] - bb[0]) else "horizontal"
    c = Counter((sentido(bb), b, comp) for b, comp, bb in pecas)
    return [{"sentido": st, "bitola": b, "comprimento_cm": comp, "quantidade": n}
            for (st, b, comp), n in sorted(c.items(), key=lambda kv: (kv[0][0] != "vertical", kv[0][1], -kv[0][2]))]


_FACES = "ABCDEFGH"


def _colunas_das_faces(path: Path) -> list[tuple[float, float, float]]:
    """Coluna de cada face no ABCD, da esquerda p/ a direita: (x0, x1, base).
    A largura vem da linha de painel mais baixa (inclui o encosto que o
    desenho soma); a base é o y dessa linha, de onde a pilha sobe."""
    import ezdxf

    horizontais = []
    for e in ezdxf.readfile(str(path)).modelspace().query("LINE"):
        if _PAINEL.match(e.dxf.layer) and abs(e.dxf.start.y - e.dxf.end.y) < 0.5:
            x0, x1 = sorted((e.dxf.start.x, e.dxf.end.x))
            horizontais.append((round(x0, _TOL), round(x1, _TOL), e.dxf.start.y))
    colunas: dict[tuple[float, float], float] = {}
    for x0, x1, y in horizontais:
        colunas[(x0, x1)] = min(y, colunas.get((x0, x1), y))
    # Colunas que se sobrepõem em x são a mesma face (painéis em 2 colunas).
    faces: list[list[float]] = []
    for (x0, x1), y in sorted(colunas.items()):
        if faces and x0 < faces[-1][1] - 0.5:
            faces[-1][1] = max(faces[-1][1], x1)
            faces[-1][2] = min(faces[-1][2], y)
        else:
            faces.append([x0, x1, y])
    return [(x0, x1, y) for x0, x1, y in faces]


def _paineis_do_contrato_pilar(dxf: Path) -> Optional[dict]:
    """Painéis do ABCD pela pilha que o gerador desenhou.

    O DXF do ABCD omite linhas de painel onde a viga chega/passa, então as
    células não fecham e a geometria sozinha subconta. O contrato ao lado do
    DXF (`P{n}.json`, mesma pasta) traz `paineis_intervals_{face}` — a pilha
    de alturas que o gerador usou — e a largura vem da face desenhada.
    """
    import json

    nome = dxf.stem.split("_preview_", 1)[-1]
    contrato = dxf.with_name(f"{nome}.json")
    try:
        pj = json.loads(contrato.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    # Pilar retangular carrega E..H com pilha mas largura 0: face inexistente.
    faces = [f for f in _FACES if pj.get(f"paineis_intervals_{f}")
             and sum(float(pj.get(f"larg{k}_{f}") or 0) for k in (1, 2, 3)) > 0]
    if not faces:
        return None
    import ezdxf
    from shapely.geometry import MultiPolygon, box
    from shapely.ops import unary_union

    colunas = _colunas_das_faces(dxf)
    casou = len(colunas) == len(faces)
    hachura = unary_union(_hachuras_poligonos(ezdxf.readfile(str(dxf)).modelspace())) if casou else None
    paineis: list[dict] = []
    recortados = 0
    area = 0.0
    for i, f in enumerate(faces):
        largura = round(colunas[i][1] - colunas[i][0], _TOL) if casou else round(sum(
            float(pj.get(f"larg{k}_{f}") or 0) for k in (1, 2, 3)), _TOL)
        y = colunas[i][2] if casou else 0.0
        for h in pj[f"paineis_intervals_{f}"]:  # pilha de baixo p/ cima
            h = round(float(h or 0), _TOL)
            if h >= 3:
                bb = (colunas[i][0], y, colunas[i][1], y + h) if casou else None
                painel = {"face": f, "largura_cm": largura, "altura_cm": h,
                          "quantidade": 1, "recortado": False, "_bbox": bb}
                real = largura * h
                # Viga chegando (HATCH) sobre a pilha: o painel é o retângulo
                # menos a viga — entalhe, ou 2 peças quando a viga cruza a face.
                if hachura is not None and not hachura.is_empty:
                    ret = box(*bb)
                    resto = ret.difference(hachura)
                    if ret.area - resto.area > 1:
                        pols = [q for q in (resto.geoms if isinstance(resto, MultiPolygon) else [resto])
                                if q.area >= 20 and min(q.bounds[2] - q.bounds[0], q.bounds[3] - q.bounds[1]) >= 1]
                        if not pols:  # face toda tomada pela viga: sem painel
                            y += h
                            continue
                        # Corta-se o retângulo que envolve as peças reais (viga
                        # tomando a largura toda de um lado = painel mais estreito).
                        bb = unary_union(pols).bounds
                        real = sum(q.area for q in pols)
                        painel.update(largura_cm=round(bb[2] - bb[0], _TOL), altura_cm=round(bb[3] - bb[1], _TOL),
                                      _bbox=bb)
                        if len(pols) > 1 or real < (bb[2] - bb[0]) * (bb[3] - bb[1]) - 1:
                            painel.update(recortado=True, partes=_partes_locais(pols, bb[0], bb[1]))
                            recortados += 1
                paineis.append(painel)
                area += real
                y += h
    return {
        "paineis": paineis,
        "paineis_total": len(paineis),
        "paineis_recortados": recortados,
        "paineis_area_m2": round(area / 1e4, 2),
        "largura_da_face": "desenhada" if casou else "ficha (desenho não separou as faces)",
    }


_fontes = threading.local()  # DXFs medidos (cache do reaproveitamento)


def _grupo(titulo: str, dxf: Optional[Path], *, com_paineis: bool = True) -> dict:
    if dxf is None:
        return {"titulo": titulo, "disponivel": False}
    if getattr(_fontes, "lista", None) is not None:
        _fontes.lista.append(str(dxf))
    try:
        medido = medir_dxf(dxf)
    except Exception as exc:  # noqa: BLE001 — DXF ilegível não derruba a ficha
        log.warning("materiais: falha ao medir %s: %s", dxf.name, exc)
        return {"titulo": titulo, "disponivel": False}
    if not com_paineis:
        medido.update(paineis=[], paineis_total=0, paineis_recortados=0, paineis_area_m2=0.0)
    return {"titulo": titulo, "disponivel": True, **medido}


def obter_materiais(row, dados_obras_root: Path) -> Optional[dict]:
    from portal.app import ficha_reader

    resolvido = resolver_item_e_fichas(row)
    if resolvido is None:
        return None
    obra_dir, item, _ = resolvido
    try:
        obra_dir.resolve().relative_to(dados_obras_root.resolve())
    except ValueError:
        return None

    tipo, classe, pavimento = row["tipo_elemento"], row["classe"], row["pavimento"]
    grupos: list[dict] = []
    if tipo == "pilar":
        modo = "passa" if classe == "pilares_n3_passa" else "para"
        base = str(item.get("beam_name") or row["item_id"]).removesuffix("_Para").removesuffix("_Passa")
        ref = {"beam_name": base, "pavimento": pavimento}
        dxf_abcd = ficha_reader._pilar_n3_dxf(obra_dir, ref, f"abcd-{modo}")
        abcd = _grupo("ABCD", dxf_abcd)
        if abcd.get("disponivel"):
            pilha = _paineis_do_contrato_pilar(dxf_abcd)
            if pilha is not None:
                abcd.update(pilha)
        grupos.append(abcd)
        grupos.append(_grupo("Grades", ficha_reader._pilar_n3_dxf(obra_dir, ref, f"grades-{modo}"),
                             com_paineis=False))
    elif tipo == "viga_lateral":
        # O N3 da LV é 1 DXF por viga×lado (VIEW_A/VIEW_B) com todos os
        # segmentos daquele lado: mede cada DXF uma vez só.
        por_lado: dict[str, Optional[Path]] = {}
        for seg in payload_do_row(row).get("segmentos") or []:
            lado = f"Lado {seg.get('lado') or '?'}"
            if por_lado.get(lado) is not None:
                continue
            r = resolver_item_e_fichas(row, classe=seg.get("classe"), item_id=seg.get("item_id"))
            por_lado[lado] = (ficha_reader._n3_dxf_producao(r[0], pavimento, seg.get("classe"), r[1])
                              if r else None)
        grupos += [_grupo(lado, dxf) for lado, dxf in sorted(por_lado.items())]
    elif tipo in ("viga_fundo", "laje"):
        dxf = ficha_reader._n3_dxf_producao(obra_dir, pavimento, classe, item)
        grupo = _grupo("Fundo" if tipo == "viga_fundo" else "Painéis", dxf)
        if tipo == "laje":  # laje é só painel (decisão do dono)
            grupo.update(sarrafos=[], _pecas_sarrafo=[], sarrafos_duplicados_ignorados=0)
        grupos.append(grupo)
    else:
        return {"tipo": tipo, "grupos": []}
    from services.plano_de_corte import compra_de_grupos

    for g in grupos:
        if not g.get("disponivel"):
            continue
        if g.get("paineis"):
            associar_sarrafos(g)
        elif g["titulo"] == "Grades":
            separar_grades(g)
        for p in g.get("paineis") or []:
            p.pop("_bbox", None)
        g.pop("_pecas_sarrafo", None)
        g.pop("_textos", None)
    prefixo = prefixo_id_painel(row)
    identificar_paineis(grupos, prefixo, laje=tipo == "laje")
    for g in grupos:
        for p in g.get("paineis") or []:
            p.pop("tira", None)
    return {"tipo": tipo, "fonte": "medido no DXF N3 desenhado", "prefixo_id": prefixo,
            "grupos": grupos, "compra": compra_de_grupos(grupos, prefixo)}


_CLASSE_ID = {"pilar": "PIL", "viga_lateral": "LV", "viga_fundo": "FV", "laje": "LAJ"}


def _token(s: str) -> str:
    return re.sub(r"[^A-Z0-9.]", "", str(s).upper())


def _campo(row, nome: str) -> str:
    return str(row[nome] or "") if nome in row.keys() else ""


def prefixo_id_painel(row) -> str:
    """`{OBRA}-{PAV}-{CLASSE}-{ITEM}`: identifica de onde o painel saiu, para
    rastrear o reaproveitamento no próximo pavimento. Usa os nomes legíveis
    (rótulo da obra, título do item), não os ids internos. Pilar e LV levam o
    modo (P1.PASSA ≠ P1.PARA); fundo leva o segmento (V309A.S1)."""
    obra = _campo(row, "obra_rotulo") or Path(_campo(row, "obra_dir")).name or _campo(row, "obra_id")
    obra = re.sub(r"^OBRA[_-]?", "", obra.upper())
    obra = re.sub(r"[^A-Z0-9_]", "", obra.replace("-", "_")) or "OBRA"
    tipo = row["tipo_elemento"]
    titulo = _campo(row, "titulo_publico") or _campo(row, "item_id")
    m = re.match(r"^\s*(\S+)\s*\(segmento\s*(\d+)\)", titulo, re.I)
    item = f"{m.group(1)}.S{m.group(2)}" if m else titulo
    if tipo == "pilar":
        item = item.removesuffix("_Para").removesuffix("_Passa")
        item += ".PASSA" if row["classe"] == "pilares_n3_passa" else ".PARA"
    elif tipo == "viga_lateral":
        payload = payload_do_row(row)
        modo = str(payload.get("modo") or "").lower()
        item = str(payload.get("viga") or item)
        if modo:
            item += ".PASSA" if modo.startswith("passa") else ".PARA"
    return "-".join([obra, _token(row["pavimento"]), _CLASSE_ID.get(tipo, _token(tipo)), _token(item)])


def identificar_paineis(grupos: list[dict], prefixo: str, *, laje: bool = False) -> None:
    """Numera cada painel do item (1..N, através dos grupos) e dá o ID
    `{prefixo}-P{nn}`. Na laje, a faixa hachurada é tira de escoramento: não
    volta para o estoque; painel comum pode ser reaproveitado."""
    n = 0
    for g in grupos:
        if not g.get("disponivel"):
            continue
        for p in g.get("paineis") or []:
            n += 1
            p["numero"] = n
            p["id"] = f"{prefixo}-P{n:02d}"
            tira = laje and bool(p.get("tira"))
            p["classe"] = "Tira de escoramento" if tira else "Painel comum"
            p["reaproveitavel"] = not tira
