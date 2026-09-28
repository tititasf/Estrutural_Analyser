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
        return "Sarrafo de pressão"
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

    msp = ezdxf.readfile(str(path)).modelspace()
    linhas: list = []
    pecas: dict[str, list[float]] = {}
    vistas: set = set()
    duplicados = 0
    for e in msp:
        layer = e.dxf.layer
        if _PAINEL.match(layer):
            linhas += [LineString(s) for s in _segmentos_da_entidade(e) if math.dist(*s) > 0.5]
        elif _SARRAFO.match(layer) and e.dxftype() in ("LINE", "LWPOLYLINE", "INSERT"):
            chave = (layer, e.dxftype(), _assinatura(e))
            if chave in vistas:
                duplicados += 1
                continue
            vistas.add(chave)
            comp = _comprimento_sarrafo(e)
            if comp > 0.5:
                pecas.setdefault(_nome_bitola(layer), []).append(round(comp, _TOL))

    paineis: Counter = Counter()
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
            paineis[(round(w, _TOL), round(h, _TOL), retangulo)] += 1
    return {
        "paineis": [
            {"largura_cm": w, "altura_cm": h, "quantidade": n, "recortado": not ret}
            for (w, h, ret), n in sorted(paineis.items(), key=lambda kv: (-kv[0][0] * kv[0][1]))
        ],
        "paineis_total": sum(paineis.values()),
        "paineis_recortados": recortados,
        "paineis_area_m2": round(area_cm2 / 1e4, 2),
        "sarrafos": [
            {
                "bitola": bitola,
                "pecas": len(comps),
                "total_m": round(sum(comps) / 100, 2),
                "cortes": [{"comprimento_cm": c, "quantidade": n}
                           for c, n in sorted(Counter(comps).items(), reverse=True)],
            }
            for bitola, comps in sorted(pecas.items())
        ],
        "sarrafos_duplicados_ignorados": duplicados,
    }


_FACES = "ABCDEFGH"


def _larguras_desenhadas_das_faces(path: Path) -> list[float]:
    """Largura de cada face no ABCD, da esquerda p/ a direita, pela linha de
    painel mais baixa de cada coluna (inclui o encosto que o desenho soma)."""
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
    for x0, x1 in sorted(colunas):
        if faces and x0 < faces[-1][1] - 0.5:
            faces[-1][1] = max(faces[-1][1], x1)
        else:
            faces.append([x0, x1])
    return [round(x1 - x0, _TOL) for x0, x1 in faces]


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
    larguras = _larguras_desenhadas_das_faces(dxf)
    casou = len(larguras) == len(faces)
    contagem: Counter = Counter()
    area = 0.0
    for i, f in enumerate(faces):
        largura = larguras[i] if casou else round(sum(
            float(pj.get(f"larg{k}_{f}") or 0) for k in (1, 2, 3)), _TOL)
        for h in pj[f"paineis_intervals_{f}"]:
            h = round(float(h or 0), _TOL)
            if h >= 3:
                contagem[(f, largura, h)] += 1
                area += largura * h
    return {
        "paineis": [
            {"face": f, "largura_cm": w, "altura_cm": h, "quantidade": n, "recortado": False}
            for (f, w, h), n in sorted(contagem.items())
        ],
        "paineis_total": sum(contagem.values()),
        "paineis_recortados": 0,
        "paineis_area_m2": round(area / 1e4, 2),
        "largura_da_face": "desenhada" if casou else "ficha (desenho não separou as faces)",
    }


def _grupo(titulo: str, dxf: Optional[Path], *, com_paineis: bool = True) -> dict:
    if dxf is None:
        return {"titulo": titulo, "disponivel": False}
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
            grupo.update(sarrafos=[], sarrafos_duplicados_ignorados=0)
        grupos.append(grupo)
    else:
        return {"tipo": tipo, "grupos": []}
    from services.plano_de_corte import compra_de_grupos

    return {"tipo": tipo, "fonte": "medido no DXF N3 desenhado", "grupos": grupos,
            "compra": compra_de_grupos(grupos)}
