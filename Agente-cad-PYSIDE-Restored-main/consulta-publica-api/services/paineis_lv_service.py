"""Lista de painéis LV de um item (STORY-12).

Zero acoplamento com `src/core/lv_generation_contract.py` ou qualquer coisa
do motor PySide6 — o motor SA já materializa o contrato completo em disco
(`Fase-4_Sincronizacao/JSON_Vigas_Laterais/{LV-PARA,LV-PASSA}/{beam}_{A,B}.json`)
durante a Fase-4; esta API só faz `json.load()` do arquivo já persistido
(architecture.md §1 item 2, §4.1, §8 "zero coupling, max modularity").
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from services.ficha_service import resolver_item_e_fichas

# classe (ficha_reader.CLASSES_N1, mesmas usadas pelo Publisher em
# publisher/publish.py::_CLASSE_PARA_TIPO_ELEMENTO) -> subpasta de
# behavior. Cada item de classe viga_lateral representa 1 lado (A/B) de 1
# behavior (Para/Passa) — mas a ficha de Painéis mostra AMBOS os lados do
# mesmo behavior (front-end-spec §5.4 wireframe: "LADO A" + "LADO B" juntos).
_CLASSE_PARA_BEHAVIOR_DIR = {
    "lateral_a_para": "LV-PARA",
    "lateral_b_para": "LV-PARA",
    "lateral_a_passa": "LV-PASSA",
    "lateral_b_passa": "LV-PASSA",
}

_CAMPOS_PUBLICOS_PAINEL = ("width", "height1", "height2", "panel_type")


def _dentro_da_raiz(obra_dir: Path, dados_obras_root: Path) -> bool:
    try:
        obra_dir.resolve().relative_to(dados_obras_root.resolve())
        return True
    except ValueError:
        return False


def _filtrar_painel(painel: dict) -> dict:
    """Só os campos públicos citados no AC1 — nunca `points`/`contract_id`/
    `source_key`/`structural_segment_index` (dados internos de geometria do
    motor, não relevantes ao funcionário de campo)."""
    return {chave: painel.get(chave) for chave in _CAMPOS_PUBLICOS_PAINEL}


def obter_paineis_lv(row, dados_obras_root: Path) -> Optional[dict]:
    """Retorna `{total_width, h_section, paineis: {"A": [...], "B": [...]}}`
    ou None se: item não é `viga_lateral`, `obra_dir` foge da raiz permitida,
    ou nenhum arquivo de contrato existe para nenhum lado — o router trata
    tudo isso como o mesmo 404 genérico (nunca inventa dado, AC2)."""
    resolvido = resolver_item_e_fichas(row)
    if resolvido is None:
        return None
    obra_dir, item, _dir_fichas = resolvido

    if not _dentro_da_raiz(obra_dir, dados_obras_root):
        return None

    classe = row["classe"]
    behavior_dir = _CLASSE_PARA_BEHAVIOR_DIR.get(classe)
    if behavior_dir is None:
        return None

    beam_name = item.get("beam_name") or row["item_id"]
    base = obra_dir / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais" / behavior_dir

    paineis_por_lado: dict[str, list[dict]] = {}
    total_width = None
    h_section = None

    for lado in ("A", "B"):
        caminho = base / f"{beam_name}_{lado}.json"
        if not caminho.is_file():
            continue
        try:
            dado = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        paineis_por_lado[lado] = [_filtrar_painel(p) for p in dado.get("panels", [])]
        if total_width is None:
            total_width = dado.get("total_width")
        if h_section is None:
            h_section = dado.get("h_section")

    if not paineis_por_lado:
        return None

    return {"total_width": total_width, "h_section": h_section, "paineis": paineis_por_lado}
