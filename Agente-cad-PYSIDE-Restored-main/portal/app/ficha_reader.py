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

CLASSES_N1 = (
    "pilares", "pilares_especiais", "lajes", "cortes",
    "fundo", "lateral_a_para", "lateral_b_para", "lateral_a_passa", "lateral_b_passa",
)

TITULOS_CLASSE = {
    "pilares": "Pilares",
    "pilares_especiais": "Pilares Especiais",
    "lajes": "Lajes",
    "cortes": "Visão de Cortes",
    "fundo": "Segmentos Fundos",
    "lateral_a_para": "Segmentos Lateral A Para",
    "lateral_b_para": "Segmentos Lateral B Para",
    "lateral_a_passa": "Segmentos Lateral A Passa",
    "lateral_b_passa": "Segmentos Lateral B Passa",
}


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


def _normalizar_pilar(p: dict) -> dict:
    return {
        "item_id": p.get("name") or p.get("key"),
        "titulo": p.get("name") or p.get("key"),
        "campos": {
            "Nome": p.get("name"),
            "Classificação SA": p.get("classification"),
            "Formato": p.get("orientation"),
            "Nível": p.get("nivel_str"),
            "Lado A": p.get("lado_A"),
            "Lado B": p.get("lado_B"),
            "Lado C": p.get("lado_C"),
            "Lado D": p.get("lado_D"),
        },
        "atencao": p.get("atencao") or "",
        "points": p.get("points") or [],
        "beam_name": p.get("name") or p.get("key"),
    }


def _normalizar_laje(s: dict) -> dict:
    return {
        "item_id": s.get("name"),
        "titulo": s.get("name"),
        "campos": {
            "Nome": s.get("name"),
            "Nível": s.get("nivel"),
            "Altura": s.get("height"),
        },
        "atencao": "",
        "points": s.get("points") or [],
        "beam_name": s.get("name"),
    }


def _normalizar_corte(c: dict) -> dict:
    return {
        "item_id": c.get("uid"),
        "titulo": c.get("beam_name") or c.get("uid"),
        "campos": {
            "Viga": c.get("beam_name"),
            "Laje própria": c.get("own_laje"),
            "Laje vizinha": c.get("neigh_laje"),
            "Altura viga": c.get("beam_h"),
            "Confiança": f"{c.get('conf_pct')}%" if c.get("conf_pct") is not None else None,
            "Status": c.get("status"),
        },
        "atencao": c.get("atencao") or "",
        "points": c.get("pts") or [],
        "beam_name": c.get("beam_name"),
    }


def _normalizar_segmento(s: dict) -> dict:
    return {
        "item_id": s.get("uid"),
        "titulo": f"{s.get('beam_name')} (segmento {s.get('segment_label')})",
        "campos": {
            "Nome": s.get("beam_name"),
            "Segmento": s.get("segment_label"),
            "Lado": s.get("side"),
            "Comportamento": s.get("behavior"),
            "Comprimento": s.get("length"),
            "Largura": s.get("width") or None,
            "Status": s.get("status"),
        },
        "atencao": s.get("atencao") or "",
        "points": s.get("points") or [],
        "beam_name": s.get("beam_name"),
    }


def listar_itens_n1(estado: dict, classe: str) -> list[dict]:
    """Itens normalizados (campos + geometria) de 1 classe, prontos pra listar."""
    if classe in ("pilares", "pilares_especiais"):
        return [_normalizar_pilar(p) for p in estado.get("pilares", [])]
    if classe == "lajes":
        return [_normalizar_laje(s) for s in estado.get("slabs", [])]
    if classe == "cortes":
        return [_normalizar_corte(c) for c in estado.get("cortes", [])]
    if classe == "fundo":
        return [_normalizar_segmento(s) for s in estado.get("segmentos", {}).get("fundo", [])]
    if classe in _SEGMENTO_LADO_SUFIXO:
        return [_normalizar_segmento(s) for s in estado.get("segmentos", {}).get(classe, [])]
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
