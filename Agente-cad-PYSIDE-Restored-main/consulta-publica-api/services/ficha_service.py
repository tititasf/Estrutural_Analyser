"""Montagem da ficha pública de 1 item (STORY-05).

Reusa DIRETAMENTE `portal.app.ficha_reader` (módulo já puro — zero import de
auth/access/repository, confirmado por inspeção estática) em vez de copiar a
lógica de leitura de `estado_<pav>.json`/fichas HTML. Escape hatch aplicado
só para `encontrar_dir_fichas`: essa função vive em `portal.app.pipeline_runner`,
um módulo MUITO maior com subprocess/DB (fora do escopo de reuso seguro aqui,
mesmo não estando na blacklist literal de imports) — copiada isolada, com
teste de paridade contra o original (`test_ficha_reader_paridade.py`).

SVG nunca é embutido aqui — só a URL (`/ficha/{code}/svg/{nivel}`, STORY-06).
`tem_lv` é só checagem de existência de arquivo, nunca lê/executa o motor LV.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from portal.app import ficha_reader  # noqa: E402

_PAVIMENTO_LABELS = {
    "TERREO": "Térreo",
    "TIPO": "Pavimento Tipo",
    "COBERTURA": "Cobertura",
    "ATICO": "Ático",
    "FUNDACAO": "Fundação",
}


def encontrar_dir_fichas(obra_dir: Path) -> Optional[Path]:
    """Cópia isolada de `portal.app.pipeline_runner.encontrar_dir_fichas`
    (escape hatch — ver docstring do módulo). Acha o diretório de fichas
    HTML mais recente gerado pelo SA real: `<obra_dir>/<pavimento>_<run_id>/`
    (timestamp por rodada), identificável pelo `arete_manifest.json` dentro.
    Runs mais recentes ordenam por último (timestamp no nome ordena
    lexicograficamente)."""
    if not obra_dir.exists():
        return None
    candidatos = sorted(
        (d for d in obra_dir.iterdir() if d.is_dir() and (d / "arete_manifest.json").is_file()),
        key=lambda d: d.name,
    )
    return candidatos[-1] if candidatos else None


def pavimento_label(pavimento: str) -> str:
    """Rótulo amigável do pavimento — nunca a string crua interna
    (`"13_PAV"`) exposta sem formatação (AC 6)."""
    pav = str(pavimento or "").strip()
    if pav in _PAVIMENTO_LABELS:
        return _PAVIMENTO_LABELS[pav]
    if pav.upper().endswith("_PAV"):
        numero = pav.upper().removesuffix("_PAV")
        if numero.isdigit():
            return f"{numero}º Pavimento"
    return pav.replace("_", " ").title() or "Pavimento"


def tem_lv(obra_dir: Path, beam_name: str) -> bool:
    """Existe contrato LV persistido pra esta viga (Fase-4)? Só checagem de
    arquivo — leitura completa é a STORY-12 (AC 5)."""
    if not beam_name:
        return False
    base = obra_dir / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais"
    for behavior_dir in ("LV-PARA", "LV-PASSA"):
        for side in ("A", "B"):
            if (base / behavior_dir / f"{beam_name}_{side}.json").is_file():
                return True
    return False


def resolver_item_e_fichas(row) -> Optional[tuple[Path, dict, Optional[Path]]]:
    """Resolve `(obra_dir, item, dir_fichas)` a partir de uma linha de
    `public_codes` (`kind='item'`) — núcleo comum reusado por `montar_ficha`
    (STORY-05) e `svg_service.obter_svg` (STORY-06). Retorna None se
    `kind != 'item'` ou se o item não existir mais na fonte real."""
    if row["kind"] != "item":
        return None

    obra_dir = Path(row["obra_dir"])
    pavimento = row["pavimento"]
    classe = row["classe"]
    item_id = row["item_id"]

    estado = ficha_reader.ler_estado_pavimento(obra_dir, pavimento)
    if not estado:
        return None
    item = ficha_reader.obter_item_n1(estado, classe, item_id)
    if item is None:
        return None

    dir_fichas = encontrar_dir_fichas(obra_dir)
    return obra_dir, item, dir_fichas


def montar_ficha(row) -> Optional[dict]:
    """Monta a resposta pública de `/ficha/{code}` a partir da linha
    resolvida de `public_codes` (STORY-03). Retorna None se o item não for
    encontrado na fonte real (estado_<pav>.json pode ter mudado desde a
    publicação) — o router trata isso como 404 genérico, igual código
    inexistente (nunca revela a diferença)."""
    resolvido = resolver_item_e_fichas(row)
    if resolvido is None:
        return None
    obra_dir, item, dir_fichas = resolvido
    classe = row["classe"]
    fotos = ficha_reader.extrair_fotos_ficha(dir_fichas, classe, item)

    code = row["code"]
    beam_name = item.get("beam_name") or row["item_id"]

    return {
        "code": code,
        "tipo": row["tipo_elemento"],
        "titulo": row["titulo_publico"] or item["titulo"],
        "obra_rotulo": row["obra_rotulo"],
        "pavimento_label": pavimento_label(row["pavimento"]),
        "campos": item["campos"],
        "atencao": item["atencao"],
        "svg": {
            "n1": f"/api/v1/ficha/{code}/svg/n1" if fotos.get("n1") else None,
            "n3": f"/api/v1/ficha/{code}/svg/n3" if fotos.get("n3") else None,
        },
        "tem_lv": tem_lv(obra_dir, beam_name),
    }
