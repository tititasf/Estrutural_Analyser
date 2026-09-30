"""Serviço de sub-vistas classe-específicas (leitura pura).

Expõe as sub-vistas N3 (pilares: cima/abcd/grades; FV: camadas SA/C1-3/N3
por segmento; lajes: camadas SA/C1-3/N3; LV: camadas por lado A/B) que o
portal gera via ficha_reader + módulos de ficha, sem NENHUMA escrita.

Regra de fronteira: reusa APENAS módulos read-only do portal:
- ficha_reader (ler_estado_pavimento, listar_itens_n1, obter_item_n1, extrair_fotos_ficha)
- fv_ficha.montar_ficha_fv (read-only, monta dados a partir do estado)
- laje_ficha.montar_ficha_laje (idem)
- lv_ficha.montar_ficha_lv (idem)
- pillar_n3_ficha.load_ficha / build_ficha (idem)

NUNCA importa auth, access, repository ou qualquer módulo com escrita.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from portal.app import ficha_reader  # noqa: E402

from .ficha_service import classe_das_fotos, resolver_item_e_fichas  # noqa: E402


def _safe_import_fv_ficha():
    """Importa fv_ficha com tratamento de erro."""
    try:
        from portal.app import fv_ficha
        return fv_ficha
    except ImportError:
        return None


def _safe_import_laje_ficha():
    try:
        from portal.app import laje_ficha
        return laje_ficha
    except ImportError:
        return None


def _safe_import_lv_ficha():
    try:
        from portal.app import lv_ficha
        return lv_ficha
    except ImportError:
        return None


def obter_views(row, dados_obras_root: Path) -> Optional[dict]:
    """Retorna sub-vistas classe-específicas para a consulta pública.

    Para pilares: SVGs de cada vista N3 (cima, abcd-para/passa, grades-para/passa)
    Para FV: SVGs por camada (SA, C1..C3, N3) e dados de segmentos
    Para lajes: SVGs por camada (SA, C1..C3, N3)
    Para LV: SVGs por camada e lado

    Retorna None se o item não for encontrado ou não tiver dados.
    """
    resolvido = resolver_item_e_fichas(row)
    if resolvido is None:
        return None
    obra_dir, item, dir_fichas = resolvido

    # Validação de path
    try:
        obra_dir.resolve().relative_to(dados_obras_root.resolve())
    except ValueError:
        return None

    classe = row["classe"]
    tipo = row["tipo_elemento"]
    pavimento = row["pavimento"]

    estado = ficha_reader.ler_estado_pavimento(obra_dir, pavimento)
    if not estado:
        return None

    result = {
        "tipo": tipo,
        "classe": classe,
    }

    if tipo == "pilar":
        result["views"] = _views_pilar(obra_dir, pavimento, estado, item, dir_fichas, classe)
    elif tipo == "viga_fundo":
        result["views"] = _views_fv(obra_dir, pavimento, estado, item, dir_fichas, classe)
    elif tipo == "laje":
        result["views"] = _views_laje(obra_dir, pavimento, estado, item, dir_fichas, classe)
    elif tipo == "viga_lateral":
        result["views"] = _views_lv(obra_dir, pavimento, estado, item, dir_fichas, classe)
    else:
        result["views"] = {}


    # Estrutural limpo do pavimento
    try:
        from portal.app.ficha_reader import _fonte_estrutural_producao
        from portal.app.dxf_preview import renderizar_dxf_svg_cacheado
        
        estrutural = _fonte_estrutural_producao(obra_dir, pavimento)
        if estrutural:
            svg_bytes = renderizar_dxf_svg_cacheado(
                estrutural,
                Path(obra_dir) / ".previews" / "estrutural_limpo",
                largura_px=1400,
                altura_px=900,
                margem_pct=0.03,
            )
            result["views"]["estrutural_limpo"] = {"svg": svg_bytes.decode("utf-8", errors="replace"), "available": True}
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Erro ao gerar estrutural_limpo: %s", e)

    return result


def _views_pilar(
    obra_dir: Path, pavimento: str, estado: dict, item: dict,
    dir_fichas: Optional[Path], classe: str,
) -> dict:
    views: dict = {}
    item_id = str(item.get("item_id") or "")
    base_id = item_id.removesuffix("_Para").removesuffix("_Passa")

    try:
        from src.core import pillar_n3_ficha
        saved_root = pillar_n3_ficha.load_ficha(obra_dir, pavimento, base_id)
        if saved_root:
            ficha_data = saved_root.get("ficha")
            if ficha_data:
                views["_ficha_data"] = {
                    "special": ficha_data.get("special", False),
                    "source": saved_root.get("source"),
                }
    except (ImportError, FileNotFoundError, Exception):
        pass

    try:
        # Vistas N3 do pilar via ficha_reader
        for vista in ("cima", "abcd-para", "abcd-passa", "grades-para", "grades-passa"):
            resolved_mode = ficha_reader.modo_visual_n3(
                obra_dir, pavimento, classe, {"beam_name": base_id}, vista, None,
            )
            svg = ficha_reader.resolver_visualizacao_n3_pilar(
                obra_dir, {"beam_name": base_id, "pavimento": pavimento}, vista,
                resolved_mode,
            )
            if svg:
                views[vista] = {"svg": svg, "available": True}
            else:
                views[vista] = {"svg": None, "available": False}
    except Exception:
        pass

    # Fallback: N1 e N3 clássicos via extrair_fotos_ficha
    fotos = ficha_reader.extrair_fotos_ficha(dir_fichas, classe_das_fotos(classe), item)
    if fotos.get("n1") and "n1" not in views:
        views["n1"] = {"svg": fotos["n1"], "available": True}
    if fotos.get("n3") and "n3" not in views:
        views["n3"] = {"svg": fotos["n3"], "available": True}

    return views


def _views_fv(
    obra_dir: Path, pavimento: str, estado: dict, item: dict,
    dir_fichas: Optional[Path], classe: str,
) -> dict:
    """Sub-vistas de Fundo de Viga: camadas SA/C1-3/N3 com segmentos."""
    views: dict = {}
    beam_name = str(item.get("beam_name") or item.get("item_id") or "")

    fv_ficha = _safe_import_fv_ficha()
    if fv_ficha and beam_name:
        try:
            html_root = obra_dir.parent.parent / "scripts" / "arete" / "html_fichas" / obra_dir.name
            for mode in ("NOVA",):
                result = fv_ficha.montar_ficha_fv(
                    obra_dir, pavimento, beam_name, estado,
                    html_fichas_root=html_root,
                    visual_mode=mode,
                )
                # Extrair SVGs das camadas
                layers = result.get("context", {}).get("layers", {})
                for layer_name, layer_data in layers.items():
                    svg = layer_data.get("svg")
                    if svg:
                        views[layer_name] = {"svg": svg, "available": True}
                    else:
                        views[layer_name] = {"svg": None, "available": False}

                # Dados de segmentos (sem SVG, só metadados)
                segments = result.get("segments", [])
                views["_segments"] = [
                    {
                        "id": s.get("id"),
                        "index": s.get("index"),
                        "length_cm": s.get("length_cm"),
                        "width_cm": s.get("width_cm"),
                        "beam_height_cm": s.get("beam_height_cm"),
                        "level": s.get("level"),
                        "n3_available": bool(s.get("n3", {}).get("available")),
                    }
                    for s in segments
                ]
                views["_beam"] = {
                    "name": result.get("beam", {}).get("name"),
                    "segment_count": result.get("beam", {}).get("segment_count"),
                }
        except (ValueError, LookupError, Exception):
            pass

    # Fallback
    fotos = ficha_reader.extrair_fotos_ficha(dir_fichas, classe, item)
    if fotos.get("n1") and "n1" not in views:
        views["n1"] = {"svg": fotos["n1"], "available": True}
    if fotos.get("n3") and "n3" not in views:
        views["n3"] = {"svg": fotos["n3"], "available": True}

    return views


def _views_laje(
    obra_dir: Path, pavimento: str, estado: dict, item: dict,
    dir_fichas: Optional[Path], classe: str,
) -> dict:
    """Sub-vistas de Laje: camadas SA/C1-3/N3."""
    views: dict = {}
    item_id = str(item.get("item_id") or "")

    laje_ficha = _safe_import_laje_ficha()
    if laje_ficha and item_id:
        try:
            for include_svgs in (True,):
                result = laje_ficha.montar_ficha_laje(
                    obra_dir, pavimento, item_id, estado,
                    include_svgs=include_svgs,
                )
                # Extrair SVGs das camadas se disponíveis
                layers = result.get("layers", {})
                for layer_name, layer_data in layers.items():
                    svg = layer_data.get("svg") if isinstance(layer_data, dict) else None
                    if svg:
                        views[layer_name] = {"svg": svg, "available": True}

                # Dados N3
                n3 = result.get("n3", {})
                if n3:
                    views["_n3_data"] = {
                        "comprimento": n3.get("comprimento"),
                        "largura": n3.get("largura"),
                        "paineis_v": n3.get("linhas_verticais"),
                        "paineis_h": n3.get("linhas_horizontais"),
                    }
        except (ValueError, LookupError, Exception):
            pass

    # Fallback
    fotos = ficha_reader.extrair_fotos_ficha(dir_fichas, classe, item)
    if fotos.get("n1") and "n1" not in views:
        views["n1"] = {"svg": fotos["n1"], "available": True}
    if fotos.get("n3") and "n3" not in views:
        views["n3"] = {"svg": fotos["n3"], "available": True}

    return views


def _views_lv(
    obra_dir: Path, pavimento: str, estado: dict, item: dict,
    dir_fichas: Optional[Path], classe: str,
) -> dict:
    """Sub-vistas de Lateral de Viga: camadas por lado A/B."""
    views: dict = {}
    beam_name = str(item.get("beam_name") or item.get("item_id") or "")

    # Determinar behavior a partir da classe
    behavior_map = {
        "lateral_a_para": "viga_para",
        "lateral_a_passa": "viga_passa",
        "lateral_b_para": "viga_para",
        "lateral_b_passa": "viga_passa",
    }
    behavior = behavior_map.get(classe, "viga_para")

    lv_ficha = _safe_import_lv_ficha()
    if lv_ficha and beam_name:
        try:
            result = lv_ficha.montar_ficha_lv(
                obra_dir, pavimento, beam_name, behavior, estado,
                include_svgs=True,
            )
            # Dados por lado
            for side in ("A", "B"):
                side_data = result.get("sides", {}).get(side, {})
                side_svg = side_data.get("svg")
                if side_svg:
                    views[f"side_{side.lower()}"] = {"svg": side_svg, "available": True}
                segments = side_data.get("segments", [])
                views[f"_segments_{side.lower()}"] = [
                    {
                        "id": s.get("id"),
                        "index": s.get("index"),
                        "length_cm": s.get("length_cm"),
                    }
                    for s in segments
                ]
        except (ValueError, LookupError, Exception):
            pass

    # Fallback
    fotos = ficha_reader.extrair_fotos_ficha(dir_fichas, classe, item)
    if fotos.get("n1") and "n1" not in views:
        views["n1"] = {"svg": fotos["n1"], "available": True}
    if fotos.get("n3") and "n3" not in views:
        views["n3"] = {"svg": fotos["n3"], "available": True}

    return views
