"""Leitor nativo de fichas N1/N3 do portal (2026-07-06).

O portal NÃO reusa o HTML gerado pelo headless como tela final — isso é
matéria-prima. Este módulo lê 2 fontes REAIS já produzidas pelo SA:

1. ``<obra_dir>/estado_<pavimento>.json`` — estado estruturado do SA
   (pilares/slabs/cortes/segmentos), com todos os campos de texto E a
   geometria (`points`) de cada item. Fonte de verdade dos CAMPOS.
2. As fichas HTML já geradas em
   ``<obra_dir>/<pavimento>_<run_id>/{pilares,lajes,fundos_viga,
   laterais_viga,pilares_especiais}/...`` — cada item tem um ou mais
   ``.evidence-card`` auto-descritivos (achado real, não documentado em
   lugar nenhum antes): o texto do card já diz o nível ("N1 / SA
   disponível...", "N3 / NOVA disponível...", "N2 ausente", "N4 ausente")
   e, quando há lado, "(lado A)"/"(lado B)" ou "Lateral A"/"Lateral B".
   Cards "ausente" não têm `<svg>` dentro — nunca inventamos imagem.
   Fonte de verdade das FOTOS (N1 e, quando existir, N3 — N4 nunca
   aparece no portal, é exclusivo do app desktop).

Nada aqui grava no `project_data.vision` nem em qualquer tabela de
curadoria — só leitura de artefatos já produzidos (mesma fronteira do
resto do portal).
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

log = logging.getLogger("portal.ficha_reader")

# classe (chave usada nas rotas do portal) -> subpasta real das fichas HTML
_SUBPASTA_POR_CLASSE = {
    "pilares": "pilares",
    "pilares_especiais": "pilares_especiais",
    "convencao_pilares": "convencao_pilares",
    "convencao_niveis_lajes": "convencao_niveis",
    "lajes": "lajes",
    "fundo": "fundos_viga",
    "lateral_a_para": "laterais_viga",
    "lateral_b_para": "laterais_viga",
    "lateral_a_passa": "laterais_viga",
    "lateral_b_passa": "laterais_viga",
}

# classe de segmento -> (lado, sufixo do nome de arquivo)
_SEGMENTO_LADO_SUFIXO = {
    "lateral_a_para": ("A", "Para"),
    "lateral_b_para": ("B", "Para"),
    "lateral_a_passa": ("A", "Passa"),
    "lateral_b_passa": ("B", "Passa"),
}

# [2026-07-13, harmonização de validação Fase 3.1] label exibida -> field_id
# REAL do app desktop (`src/ui/widgets/detail_card.py`) — só entram aqui
# campos que já têm um field_id 1:1 estável dos dois lados. Campos sem
# equivalente conhecido (Orientação/Nível Relativo do pilar, Altura da laje)
# ficam de fora de propósito — gap documentado em
# docs/CONVENCAO-SELOS-VALIDACAO.md, não um esquecimento. Lado A-D e Lajes
# Contíguas do pilar são tratados à parte (granularidade própria, Fase 3.3).
_FIELD_ID_PILAR = {
    "Nome": "name",
    "Classificação": "classification",
}

_FIELD_ID_LAJE = {
    "Nome": "name",
    "Nível": "laje_nivel",
}

# [2026-07-13, Fase 3.4] classe de segmento -> {label: valor}. Valores que
# começam com "_" são SUFIXOS relativos ao seg_uid (`{prefix}_seg_{idx}`,
# resolvido só no lado do app desktop via título "V101 (segmento N)" — ver
# `main.py::_sincronizar_selo_rosa_drive`); valores sem "_" na frente são
# field_id ABSOLUTO (compartilhado com o header do item, ex. "name").
# "Largura"/"Comprimento" em fundo mapeiam pro MESMO `_dim` (SA não separa
# largura de comprimento nesse segmento — aproximação documentada).
_FIELD_ID_SEGMENTO_SUFIXO = {
    "fundo": {"Nome": "name", "Comprimento": "_dim", "Largura": "_dim"},
    "lateral_a_para": {"Nome": "name", "Comprimento": "_comprimento_total"},
    "lateral_b_para": {"Nome": "name", "Comprimento": "_comprimento_total"},
    "lateral_a_passa": {"Nome": "name", "Comprimento": "_comp_total_passa"},
    "lateral_b_passa": {"Nome": "name", "Comprimento": "_comp_total_passa"},
}


def _com_field_id(campos: dict, mapa: dict) -> dict:
    """Subconjunto de `campos` que tem field_id real conhecido do SA —
    devolvido como `{label: field_id}` ao lado de `campos` (que continua só
    pra exibição). O JS usa isso pra validar campo com o field_id certo em
    vez do label cru."""
    return {label: mapa[label] for label in campos if label in mapa}

CLASSES_N1 = (
    "convencao_pilares", "convencao_niveis_lajes",
    "pilares", "pilares_especiais", "lajes", "cortes",
    "fundo", "lateral_a_para", "lateral_b_para", "lateral_a_passa", "lateral_b_passa",
    "pilares_n3_para", "pilares_n3_passa",
)

TITULOS_CLASSE = {
    "convencao_pilares": "Convenção de Pilares",
    "convencao_niveis_lajes": "Convenção de Níveis",
    "pilares": "Pilares Normais",
    "pilares_especiais": "Pilares Especiais",
    "lajes": "Lajes",
    "cortes": "Visão de Cortes",
    "fundo": "Segmentos Fundos",
    "lateral_a_para": "Segmentos Lateral A Para",
    "lateral_b_para": "Segmentos Lateral B Para",
    "lateral_a_passa": "Segmentos Lateral A Passa",
    "lateral_b_passa": "Segmentos Lateral B Passa",
    "pilares_n3_para": "Pilares N3 (Para)",
    "pilares_n3_passa": "Pilares N3 (Passa)",
}

# Classes de N3 que sao so uma re-projecao do N1 (mesmo item_id) — hoje so'
# rastreiam validacao (n3_ok), sem lista propria. Pilares sao diferentes: TODO
# pilar gera 2 fichas N3 (Para/Passa), mesma interpretacao SA, resultados
# diferentes (contrato `n3_variants/{para,passa}/PL_ABCD_preview_{pilar}.dxf`
# do robo gerar_pl_dxf_stog.py, hoje so materializado pelo desktop). O sufixo
# `_Para`/`_Passa` no item_id replica a convencao ja usada pelo desktop em
# `comparison_engine.py` (`_pil_strip_pp`/`_pil_pp_from_id`).
_PILARES_N3_VARIANTE = {"pilares_n3_para": "Para", "pilares_n3_passa": "Passa"}


_PAVIMENTO_LABELS = {
    "TERREO": "Térreo",
    "TIPO": "Pavimento Tipo",
    "COBERTURA": "Cobertura",
    "ATICO": "Ático",
    "FUNDACAO": "Fundação",
}


def pavimento_label(pavimento: str) -> str:
    """Rótulo amigável do pavimento — nunca a string crua interna
    (`"13_PAV"`) exposta sem formatação [2026-07-13, portado de
    `consulta-publica-api/services/ficha_service.py::pavimento_label` —
    mesma lógica, cópia isolada pra evitar acoplar o portal ao processo da
    Consulta Pública; usada nas referências legíveis ao lado de cada
    código público]."""
    pav = str(pavimento or "").strip()
    if pav in _PAVIMENTO_LABELS:
        return _PAVIMENTO_LABELS[pav]
    if pav.upper().endswith("_PAV"):
        numero = pav.upper().removesuffix("_PAV")
        if numero.isdigit():
            return f"{numero}º Pavimento"
    return pav.replace("_", " ").title() or "Pavimento"


def descobrir_pavimentos(obra_dir: Path) -> list[str]:
    """Pavimentos com estado real salvo (`estado_<pav>.json` no root da obra)."""
    if not obra_dir.exists():
        return []
    return sorted(p.stem.removeprefix("estado_") for p in obra_dir.glob("estado_*.json"))


def ler_estado_pavimento(obra_dir: Path, pavimento: str) -> Optional[dict]:
    """Lê `estado_<pavimento>.json` (estado real do SA). None se não existe ainda."""
    caminho = obra_dir / f"estado_{pavimento}.json"
    if not caminho.is_file():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("estado_%s.json ilegível em %s: %s", pavimento, obra_dir, exc)
        return None


def _pilar_lajes_granular(p: dict, lajes_por_nome: dict) -> tuple[dict, dict]:
    """[2026-07-13, Fase 3.3] Quebra `p['lajes']` (lista de
    `{'laje','side','face'}`, `main.py:14854`) em campos granulares POR
    lado × índice (1/2) — MESMO field_id que o app desktop já usa
    (`p_s{lado}_l{i}_n/h/v`, `detail_card.py:1875-1892`), zero tradução
    necessária. "Lado A-D" e "Lajes contíguas" continuam existindo como
    texto agregado (não removidos, só complementados) — são a MESMA fonte
    de dado (`p['lajes']`), só formatada agregada; a granular é que fica
    validável campo a campo."""
    campos: dict[str, object] = {}
    field_ids: dict[str, str] = {}
    por_lado: dict[str, list] = {}
    for entrada in (p.get("lajes") or []):
        if not isinstance(entrada, dict):
            continue
        lado = str(entrada.get("side") or "").strip().upper()
        if not lado:
            continue
        por_lado.setdefault(lado, []).append(entrada)
    for lado, entradas in por_lado.items():
        for i, entrada in enumerate(entradas[:2], start=1):
            nome = (entrada.get("laje") or "").strip()
            laje = lajes_por_nome.get(nome) or {}
            rotulo_n = f"Laje {lado} #{i} — Nome"
            campos[rotulo_n] = nome or "Nenhuma"
            field_ids[rotulo_n] = f"p_s{lado}_l{i}_n"
            if nome:
                rotulo_h = f"Laje {lado} #{i} — Altura"
                campos[rotulo_h] = laje.get("height") or ""
                field_ids[rotulo_h] = f"p_s{lado}_l{i}_h"
                rotulo_v = f"Laje {lado} #{i} — Nível"
                campos[rotulo_v] = laje.get("nivel") or ""
                field_ids[rotulo_v] = f"p_s{lado}_l{i}_v"
    return campos, field_ids


def _normalizar_pilar(p: dict, lajes_por_nome: Optional[dict] = None) -> dict:
    lajes_por_nome = lajes_por_nome or {}
    campos = {
        "Nome": p.get("name"),
        "Classificação": p.get("classification"),
        "Orientação": p.get("orientation"),
        "Nível Relativo": p.get("nivel_str"),
        "Lado A": p.get("lado_A"),
        "Lado B": p.get("lado_B"),
        "Lado C": p.get("lado_C"),
        "Lado D": p.get("lado_D"),
        "Lajes contíguas": (
            ", ".join(
                (l.get("laje") or str(l)) if isinstance(l, dict) else str(l)
                for l in p["lajes"]
            )
            if p.get("lajes") else "Nenhuma"
        ),
    }
    field_ids = dict(_com_field_id(campos, _FIELD_ID_PILAR))
    campos_granular, field_ids_granular = _pilar_lajes_granular(p, lajes_por_nome)
    campos.update(campos_granular)
    field_ids.update(field_ids_granular)
    return {
        "item_id": p.get("name") or p.get("key"),
        "titulo": p.get("name") or p.get("key"),
        "campos": campos,
        "campos_field_id": field_ids,
        "atencao": p.get("atencao") or "",
        "points": p.get("points") or [],
        "beam_name": p.get("name") or p.get("key"),
    }


def _normalizar_pilar_n3_variante(p: dict, variante: str, lajes_por_nome: Optional[dict] = None) -> dict:
    """Ficha N3 do pilar pra 1 variante (Para/Passa) — mesma interpretacao SA
    do N1 (`_normalizar_pilar`), mas item_id/titulo com sufixo pra nao colidir
    com a ficha N1 nem com a outra variante."""
    base = _normalizar_pilar(p, lajes_por_nome)
    nome_base = base["item_id"]
    base["item_id"] = f"{nome_base}_{variante}"
    base["titulo"] = f"{nome_base} ({variante})"
    base["campos"] = {"Variante N3": variante, **base["campos"]}
    return base  # campos_field_id herdado sem alteração ("Variante N3" não tem field_id)


def _normalizar_laje(s: dict) -> dict:
    campos = {
        "Nome": s.get("name"),
        "Nível": s.get("nivel"),
        "Altura": s.get("height"),
    }
    return {
        "item_id": s.get("name"),
        "titulo": s.get("name"),
        "campos": campos,
        "campos_field_id": _com_field_id(campos, _FIELD_ID_LAJE),
        "atencao": "",
        "points": s.get("points") or [],
        "beam_name": s.get("name"),
    }


def _laje_ref_texto(nome: Optional[str], lajes_por_nome: dict) -> Optional[str]:
    """Formata a referência a uma laje (própria/vizinha) do corte incluindo
    Nível/Altura da própria ficha da laje — permite validar, a partir do
    corte, se a interpretação bate com a perspectiva de cada laje (mesmos
    dados de `_normalizar_laje`), sem precisar abrir a ficha da laje à parte."""
    nome = (nome or "").strip()
    if not nome or nome in ("-", "—", "�"):
        return "Nenhuma"
    laje = lajes_por_nome.get(nome)
    if not laje:
        return nome
    nivel = laje.get("nivel") or "?"
    altura = laje.get("height") or "?"
    return f"{nome} (Nível {nivel}, Altura {altura})"


def _normalizar_corte(c: dict, lajes_por_nome: Optional[dict] = None) -> dict:
    lajes_por_nome = lajes_por_nome or {}
    return {
        "item_id": c.get("uid"),
        "titulo": c.get("beam_name") or c.get("uid"),
        "campos": {
            "Viga": c.get("beam_name"),
            "Laje própria": _laje_ref_texto(c.get("own_laje"), lajes_por_nome),
            "Laje vizinha": _laje_ref_texto(c.get("neigh_laje"), lajes_por_nome),
            "Altura viga": c.get("beam_h"),
            "Confiança": f"{c.get('conf_pct')}%" if c.get("conf_pct") is not None else None,
            "Status": c.get("status"),
        },
        # [2026-07-13, Fase 3.5] nomes CRUS (não formatados) das lajes que
        # esse corte referencia — usados pelo motor de cruzamento do app
        # desktop (main.py) pra saber quais lajes marcar `laje_visao_corte`
        # validado quando TODOS os cortes delas forem confirmados no Portal.
        "own_laje": (c.get("own_laje") or "").strip() or None,
        "neigh_laje": (c.get("neigh_laje") or "").strip() or None,
        "atencao": c.get("atencao") or "",
        "points": c.get("pts") or [],
        "beam_name": c.get("beam_name"),
    }


def _normalizar_segmento(s: dict, classe: Optional[str] = None) -> dict:
    campos = {
        "Nome": s.get("beam_name"),
        "Segmento": s.get("segment_label"),
        "Lado": s.get("side"),
        "Comportamento": s.get("behavior"),
        "Comprimento": s.get("length"),
        "Largura": s.get("width") or None,
        "Status": s.get("status"),
    }
    mapa = _FIELD_ID_SEGMENTO_SUFIXO.get(classe or "", {})
    return {
        "item_id": s.get("uid"),
        "titulo": f"{s.get('beam_name')} (segmento {s.get('segment_label')})",
        "campos": campos,
        "campos_field_id": _com_field_id(campos, mapa),
        "atencao": s.get("atencao") or "",
        "points": s.get("points") or [],
        "beam_name": s.get("beam_name"),
    }


def _pilar_formato(pts: list) -> str:
    if not pts:
        return 'Especial'
    try:
        clean = list(pts)
        if len(clean) > 1:
            if (abs(float(clean[0][0]) - float(clean[-1][0])) < 0.5
                    and abs(float(clean[0][1]) - float(clean[-1][1])) < 0.5):
                clean = clean[:-1]

        changed = True
        while changed and len(clean) > 3:
            changed = False
            new: list = []
            nc = len(clean)
            for i in range(nc):
                p0 = clean[(i - 1) % nc]
                p1 = clean[i]
                p2 = clean[(i + 1) % nc]
                vert  = (abs(float(p0[0]) - float(p1[0])) < 0.5
                         and abs(float(p1[0]) - float(p2[0])) < 0.5)
                horiz = (abs(float(p0[1]) - float(p1[1])) < 0.5
                         and abs(float(p1[1]) - float(p2[1])) < 0.5)
                if vert or horiz:
                    changed = True
                else:
                    new.append(p1)
            if new:
                clean = new

        n = len(clean)
        if n == 4:
            return 'Retangular'
        if n == 6:
            return 'em L'
        if n == 8:
            return 'em U'

        if n >= 8:
            import math as _math
            cx = sum(float(p[0]) for p in clean) / n
            cy = sum(float(p[1]) for p in clean) / n
            dists = [_math.sqrt((float(p[0]) - cx) ** 2 + (float(p[1]) - cy) ** 2)
                     for p in clean]
            md = sum(dists) / n
            if md > 0 and (max(dists) - min(dists)) / md < 0.15:
                return 'Circular'

        return 'Especial'
    except Exception:
        return 'Especial'

def listar_itens_n1(estado: dict, classe: str) -> list[dict]:
    """Itens normalizados (campos + geometria) de 1 classe, prontos pra listar."""
    if classe == "convencao_pilares":
        return [{
            "item_id": "convencao_pilares",
            "titulo": "Convenção de Pilares",
            "campos": {"Descrição": "Critérios extraídos pelo SA para pilares."},
            "atencao": "",
            "points": [],
            "beam_name": "interpretacao_pilares"
        }]
    if classe == "convencao_niveis_lajes":
        return [{
            "item_id": "convencao_niveis",
            "titulo": "Convenção de Níveis",
            "campos": {"Descrição": "Critérios extraídos pelo SA para níveis e lajes."},
            "atencao": "",
            "points": [],
            "beam_name": "interpretacao_niveis"
        }]
    if classe in ("pilares", "pilares_especiais") or classe in _PILARES_N3_VARIANTE:
        lajes_por_nome = {s.get("name"): s for s in estado.get("slabs", []) if s.get("name")}
        if classe == "pilares":
            return [_normalizar_pilar(p, lajes_por_nome) for p in estado.get("pilares", []) if _pilar_formato(p.get("points", [])) == 'Retangular']
        if classe == "pilares_especiais":
            return [_normalizar_pilar(p, lajes_por_nome) for p in estado.get("pilares", []) if _pilar_formato(p.get("points", [])) != 'Retangular']
        variante = _PILARES_N3_VARIANTE[classe]
        return [_normalizar_pilar_n3_variante(p, variante, lajes_por_nome) for p in estado.get("pilares", [])]
    if classe == "lajes":
        return [_normalizar_laje(s) for s in estado.get("slabs", [])]
    if classe == "cortes":
        lajes_por_nome = {s.get("name"): s for s in estado.get("slabs", []) if s.get("name")}
        return [_normalizar_corte(c, lajes_por_nome) for c in estado.get("cortes", [])]
    if classe == "fundo":
        return [_normalizar_segmento(s, classe) for s in estado.get("segmentos", {}).get("fundo", [])]
    if classe in _SEGMENTO_LADO_SUFIXO:
        return [_normalizar_segmento(s, classe) for s in estado.get("segmentos", {}).get(classe, [])]
    return []


def obter_item_n1(estado: dict, classe: str, item_id: str) -> Optional[dict]:
    for item in listar_itens_n1(estado, classe):
        if item["item_id"] == item_id:
            return item
    return None


def _classificar_svg(svg, texto_contexto: str) -> Optional[tuple[str, Optional[str]]]:
    """Deriva (nivel, lado) de 1 <svg> de foto — via texto do card ao redor
    quando existe (achado real: vigas/lajes usam `.evidence-card`, pilares usam
    `.face-card` — nomes de container diferentes, mesmo conceito), ou via
    class/aria-label do proprio svg como fallback. Nunca classifica como N2/N4
    (N4 e' exclusivo do app desktop, por decisao explicita do dono)."""
    baixo = texto_contexto.lower()
    aria = (svg.get("aria-label") or "").upper()
    classe_svg = svg.get("class") or []

    if texto_contexto.startswith("N1") or "img-geo" in classe_svg or aria.startswith("N1"):
        nivel = "N1"
    elif texto_contexto.startswith("N3") or "N3" in aria:
        nivel = "N3"
    else:
        return None

    lado = None
    if "lado a" in baixo or "lateral a" in baixo:
        lado = "A"
    elif "lado b" in baixo or "lateral b" in baixo:
        lado = "B"
    return nivel, lado


@lru_cache(maxsize=64)
def _parse_html_cache(caminho_str: str, mtime: float) -> list[dict]:
    """Cacheado por (caminho, mtime) — reparseia só quando o arquivo muda."""
    from bs4 import BeautifulSoup

    texto = Path(caminho_str).read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(texto, "html.parser")
    cartas = []
    for svg in soup.select("svg.img-geo, svg.img-n4, svg.img-n3"):
        # card ao redor (achado real: nome da classe do container varia por
        # tipo de item — evidence-card em vigas/lajes, face-card em pilares).
        card = svg.find_parent(class_=lambda c: bool(c) and (
            "card" in " ".join(c) if isinstance(c, list) else "card" in c
        ))
        texto_card = card.get_text(" ", strip=True) if card else ""
        if "ausente" in texto_card.lower():
            continue
        classificado = _classificar_svg(svg, texto_card)
        if classificado is None:
            continue
        nivel, lado = classificado
        cartas.append({"nivel": nivel, "lado": lado, "svg": str(svg)})
    return cartas


def _localizar_ficha_html(dir_fichas: Path, classe: str, beam_name: str, side_suffix: str = "") -> Optional[Path]:
    subpasta_nome = _SUBPASTA_POR_CLASSE.get(classe, classe)
    subpasta = dir_fichas / subpasta_nome
    
    # Bypass para convencoes
    if classe == "convencao_pilares":
        c = subpasta / "interpretacao_pilares.html"
        return c if c.exists() else None
    if classe == "convencao_niveis_lajes":
        c = subpasta / "interpretacao_niveis.html"
        return c if c.exists() else None
        
    if not subpasta.exists():
        return None
    if side_suffix:
        candidatos = sorted(subpasta.rglob(f"{beam_name}-{side_suffix}.html"))
    else:
        candidatos = sorted(subpasta.rglob(f"{beam_name}.html"))
    return candidatos[0] if candidatos else None


def extrair_fotos_ficha(
    dir_fichas: Optional[Path], classe: str, item: dict,
) -> dict[str, Optional[str]]:
    """Fotos N1/N3 (svg embutido, já renderizado pelo SA) do item — None quando
    ainda não geradas ("ausente" no card, ou a ficha HTML não existe ainda).
    """
    resultado: dict[str, Optional[str]] = {"n1": None, "n3": None}
    if dir_fichas is None:
        return resultado

    beam_name = item.get("beam_name") or ""
    if not beam_name:
        return resultado

    side_suffix = ""
    lado_alvo = None
    if classe in _SEGMENTO_LADO_SUFIXO:
        lado_alvo, side_suffix = _SEGMENTO_LADO_SUFIXO[classe]

    caminho = _localizar_ficha_html(dir_fichas, classe, beam_name, side_suffix)
    if caminho is None:
        return resultado

    try:
        mtime = caminho.stat().st_mtime
    except OSError:
        return resultado
    cartas = _parse_html_cache(str(caminho), mtime)

    for carta in cartas:
        if lado_alvo is not None and carta["lado"] != lado_alvo:
            continue
        chave = carta["nivel"].lower()
        if resultado.get(chave) is None:
            resultado[chave] = carta["svg"]
    return resultado
